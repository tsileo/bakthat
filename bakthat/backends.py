# -*- encoding: utf-8 -*-
import tempfile
import os
import logging
import shelve
import json
import socket
import httplib
import boto
from boto.s3.key import Key
import math
from boto.glacier.exceptions import UnexpectedHTTPResponseError
from boto.exception import S3ResponseError

from bakthat.conf import config, DEFAULT_LOCATION, CONFIG_FILE
from bakthat.models import Inventory, Jobs

log = logging.getLogger(__name__)


class glacier_shelve(object):
    """Context manager for shelve.

    Deprecated, here for backward compatibility.

    """

    def __enter__(self):
        self.shelve = shelve.open(os.path.expanduser("~/.bakthat.db"))

        return self.shelve

    def __exit__(self, exc_type, exc_value, traceback):
        self.shelve.close()


class BakthatBackend:
    """Handle Configuration for Backends.

    The profile is only useful when no conf is None.

    :type conf: dict
    :param conf: Custom configuration

    :type profile: str
    :param profile: Profile name

    """
    def __init__(self, conf={}, profile="default"):
        self.conf = conf
        if not conf:
            self.conf = config.get(profile)
            if not self.conf:
                log.error("No {0} profile defined in {1}.".format(profile, CONFIG_FILE))
            if not "access_key" in self.conf or not "secret_key" in self.conf:
                log.error("Missing access_key/secret_key in {0} profile ({1}).".format(profile, CONFIG_FILE))


class RotationConfig(BakthatBackend):
    """Hold backups rotation configuration."""
    def __init__(self, conf={}, profile="default"):
        BakthatBackend.__init__(self, conf, profile)
        self.conf = self.conf.get("rotation", {})


class S3Backend(BakthatBackend):
    """Backend to handle S3 upload/download."""
    def __init__(self, conf={}, profile="default"):
        BakthatBackend.__init__(self, conf, profile)

        con = boto.connect_s3(self.conf["access_key"], self.conf["secret_key"])

        region_name = self.conf["region_name"]
        if region_name == DEFAULT_LOCATION:
            region_name = ""

        try:
            self.bucket = con.get_bucket(self.conf["s3_bucket"])
        except S3ResponseError, e:
            if e.code == "NoSuchBucket":
                self.bucket = con.create_bucket(self.conf["s3_bucket"], location=region_name)
            else:
                raise e

        self.container = self.conf["s3_bucket"]
        self.container_key = "s3_bucket"

    def download(self, keyname):
        k = Key(self.bucket)
        k.key = keyname

        encrypted_out = tempfile.TemporaryFile()
        k.get_contents_to_file(encrypted_out)
        encrypted_out.seek(0)

        return encrypted_out

    def cb(self, complete, total):
        """Upload callback to log upload percentage."""
        percent = int(complete * 100.0 / total)
        log.info("Upload completion: {0}%".format(percent))

    def upload(self, keyname, filename, **kwargs):
        k = Key(self.bucket)
        k.key = keyname
        upload_kwargs = {"reduced_redundancy": kwargs.get("s3_reduced_redundancy", False)}
        if kwargs.get("cb", True):
            upload_kwargs = dict(cb=self.cb, num_cb=10)
        k.set_contents_from_filename(filename, **upload_kwargs)
        k.set_acl("private")

    def ls(self):
        return [key.name for key in self.bucket.get_all_keys()]

    def delete(self, keyname):
        k = Key(self.bucket)
        k.key = keyname
        self.bucket.delete_key(k)


class GlacierBackend(BakthatBackend):
    """Backend to handle Glacier upload/download."""
    def __init__(self, conf={}, profile="default"):
        BakthatBackend.__init__(self, conf, profile)

        con = boto.connect_glacier(aws_access_key_id=self.conf["access_key"], aws_secret_access_key=self.conf["secret_key"], region_name=self.conf["region_name"])

        self.vault = con.create_vault(self.conf["glacier_vault"])
        self.backup_key = "bakthat_glacier_inventory"
        self.container = self.conf["glacier_vault"]
        self.container_key = "glacier_vault"

    def load_archives(self):
        return []

    def backup_inventory(self):
        """Backup the local inventory from shelve as a json string to S3."""
        if config.get("aws", "s3_bucket"):
            archives = self.load_archives()

            s3_bucket = S3Backend(self.conf).bucket
            k = Key(s3_bucket)
            k.key = self.backup_key

            k.set_contents_from_string(json.dumps(archives))

            k.set_acl("private")

    def load_archives_from_s3(self):
        """Fetch latest inventory backup from S3."""
        s3_bucket = S3Backend(self.conf).bucket
        try:
            k = Key(s3_bucket)
            k.key = self.backup_key

            return json.loads(k.get_contents_as_string())
        except S3ResponseError, exc:
            log.error(exc)
            return {}

#    def restore_inventory(self):
#        """Restore inventory from S3 to DumpTruck."""
#        if config.get("aws", "s3_bucket"):
#            loaded_archives = self.load_archives_from_s3()

#            # TODO faire le restore
#        else:
#            raise Exception("You must set s3_bucket in order to backup/restore inventory to/from S3.")

    def restore_inventory(self):
        """Restore inventory from S3 to local shelve."""
        if config.get("aws", "s3_bucket"):
            loaded_archives = self.load_archives_from_s3()

            with glacier_shelve() as d:
                archives = {}
                for a in loaded_archives:
                    print a
                    archives[a["filename"]] = a["archive_id"]
                d["archives"] = archives
        else:
            raise Exception("You must set s3_bucket in order to backup/restore inventory to/from S3.")

    def upload(self, keyname, filename, **kwargs):
        archive_id = self.vault.concurrent_create_archive_from_file(filename, keyname)
        Inventory.create(filename=keyname, archive_id=archive_id)

        #self.backup_inventory()

    def get_job_id(self, filename):
        """Get the job_id corresponding to the filename.

        :type filename: str
        :param filename: Stored filename.

        """
        return Jobs.get_job_id(filename)

    def delete_job(self, filename):
        """Delete the job entry for the filename.

        :type filename: str
        :param filename: Stored filename.

        """
        job = Jobs.get(Jobs.filename == filename)
        job.delete_instance()

    def download(self, keyname, job_check=False):
        """Initiate a Job, check its status, and download the archive if it's completed."""
        archive_id = Inventory.get_archive_id(keyname)
        if not archive_id:
            log.error("{0} not found !")
            # check if the file exist on S3 ?
            return

        job = None

        job_id = Jobs.get_job_id(keyname)
        log.debug("Job: {0}".format(job_id))

        if job_id:
            try:
                job = self.vault.get_job(job_id)
            except UnexpectedHTTPResponseError:  # Return a 404 if the job is no more available
                self.delete_job(keyname)

        if not job:
            job = self.vault.retrieve_archive(archive_id)
            job_id = job.id
            Jobs.update_job_id(keyname, job_id)

        log.info("Job {action}: {status_code} ({creation_date}/{completion_date})".format(**job.__dict__))

        if job.completed:
            log.info("Downloading...")
            encrypted_out = tempfile.TemporaryFile()

            # Boto related, download the file in chunk
            chunk_size = 4 * 1024 * 1024
            num_chunks = int(math.ceil(job.archive_size / float(chunk_size)))
            job._download_to_fileob(encrypted_out, num_chunks, chunk_size, True, (socket.error, httplib.IncompleteRead))

            encrypted_out.seek(0)
            return encrypted_out
        else:
            log.info("Not completed yet")
            if job_check:
                return job
            return

    def retrieve_inventory(self, jobid):
        """Initiate a job to retrieve Galcier inventory or output inventory."""
        if jobid is None:
            return self.vault.retrieve_inventory(sns_topic=None, description="Bakthat inventory job")
        else:
            return self.vault.get_job(jobid)

    def retrieve_archive(self, archive_id, jobid):
        """Initiate a job to retrieve Galcier archive or download archive."""
        if jobid is None:
            return self.vault.retrieve_archive(archive_id, sns_topic=None, description='Retrieval job')
        else:
            return self.vault.get_job(jobid)

    def ls(self):
        return [ivt.filename for ivt in Inventory.select()]

    def delete(self, keyname):
        archive_id = Inventory.get_archive_id(keyname)
        if archive_id:
            self.vault.delete_archive(archive_id)
            archive_data = Inventory.get(Inventory.filename == keyname)
            archive_data.delete_instance()

            #self.backup_inventory()

    def upgrade_from_shelve(self):
        try:
            with glacier_shelve() as d:
                archives = d["archives"]
                if "archives" in d:
                    for key, archive_id in archives.items():
                        #print {"filename": key, "archive_id": archive_id}
                        Inventory.create(**{"filename": key, "archive_id": archive_id})
                        del archives[key]
                d["archives"] = archives
        except Exception, exc:
            log.exception(exc)

class SwiftBackend(BakthatBackend):
    """Backend to handle OpenStack Swift upload/download."""
    def __init__(self, conf={}, profile="default"):
        BakthatBackend.__init__(self, conf, profile)

        from swiftclient import Connection, ClientException

        self.con = Connection(self.conf["auth_url"], self.conf["access_key"], 
                              self.conf["secret_key"],
                              auth_version=self.conf["auth_version"],
                              insecure=True)

        region_name = self.conf["region_name"]
        if region_name == DEFAULT_LOCATION:
            region_name = ""

        try:
            self.con.head_container(self.conf["s3_bucket"])
        except ClientException, e:
            self.con.put_container(self.conf["s3_bucket"])

        self.container = self.conf["s3_bucket"]
        self.container_key = "s3_bucket"

    def download(self, keyname):
        headers, data = self.con.get_object(self.container, keyname,
                                            resp_chunk_size=65535)

        encrypted_out = tempfile.TemporaryFile()
        for chunk in data:
            encrypted_out.write(chunk)
        encrypted_out.seek(0)

        return encrypted_out

    def cb(self, complete, total):
        """Upload callback to log upload percentage."""
        """Swift client does not support callbak"""
        percent = int(complete * 100.0 / total)
        log.info("Upload completion: {0}%".format(percent))

    def upload(self, keyname, filename, **kwargs):
        fp = open(filename, "rb")
        self.con.put_object(self.container, keyname, fp)

    def ls(self):
        headers, objects = self.con.get_container(self.conf["s3_bucket"])
        return [key['name'] for key in objects]

    def delete(self, keyname):
        self.con.delete_object(self.container, keyname)
