# -*- encoding: utf-8 -*-
import tempfile
import os
import logging
import shelve
import json
import re
import socket
import httplib
import ConfigParser
import boto
from boto.s3.key import Key
from boto.glacier.exceptions import UnexpectedHTTPResponseError
from boto.exception import S3ResponseError

from bakthat.conf import config, DEFAULT_DESTINATION, DEFAULT_LOCATION

log = logging.getLogger(__name__)

class glacier_shelve(object):
    """Context manager for shelve."""

    def __enter__(self):
        self.shelve = shelve.open(os.path.expanduser("~/.bakthat.db"))

        return self.shelve

    def __exit__(self, exc_type, exc_value, traceback):
        self.shelve.close()


class BakthatBackend:
    """Handle Configuration for Backends."""
    def __init__(self, conf=None, extra_conf=[], section="aws"):
        self.custom_conf = None
        self.conf = {}
        if not conf:
            try:
                if section == "aws":
                    self.conf["access_key"] = config.get(section, "access_key")
                    self.conf["secret_key"] = config.get(section, "secret_key")
                    self.conf["region_name"] = config.get(section, "region_name")

                for key in extra_conf:
                    try:
                        self.conf[key] = config.get(section, key)
                    except Exception, exc:
                        log.exception(exc)
                        log.error("Missing configuration variable.")
                        self.conf[key] = None

            except ConfigParser.NoOptionError:
                if section == "aws":
                    log.error("Configuration file not available.")
                    log.info("Use 'bakthat configure' to create one.")
                else:
                    log.error("No {0} section available in configuration file.".format(section))

        else:
            if section == "aws":
                self.conf["access_key"] = conf.get("access_key")
                self.conf["secret_key"] = conf.get("secret_key")
                self.conf["region_name"] = conf.get("region_name", DEFAULT_LOCATION)

            for key in extra_conf:
                self.conf[key] = conf.get(key)


class RotationConfig(BakthatBackend):
    """Hold backups rotation configuration."""
    def __init__(self, conf=None):
        BakthatBackend.__init__(self, conf, 
                                extra_conf=["days", "weeks", "months", "first_week_day"],
                                section="rotation")

class S3Backend(BakthatBackend):
    """Backend to handle S3 upload/download."""
    def __init__(self, conf=None):
        BakthatBackend.__init__(self, conf, extra_conf=["s3_bucket"])

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

        self.container = "S3 Bucket: {0}".format(self.conf["s3_bucket"])

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

    def upload(self, keyname, filename, cb=True):
        k = Key(self.bucket)
        k.key = keyname
        upload_kwargs = {}
        if cb:
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
    def __init__(self, conf=None):
        BakthatBackend.__init__(self, conf, extra_conf=["glacier_vault", "s3_bucket"])

        con = boto.connect_glacier(aws_access_key_id=self.conf["access_key"],
                                    aws_secret_access_key=self.conf["secret_key"],
                                    region_name=self.conf["region_name"])

        self.vault = con.create_vault(self.conf["glacier_vault"])
        self.backup_key = "bakthat_glacier_inventory"
        self.container = "Glacier vault: {0}".format(self.conf["glacier_vault"])


    def backup_inventory(self):
        """Backup the local inventory from shelve as a json string to S3."""
        if config.get("aws", "s3_bucket"):
            archives = self.load_archives()

            s3_bucket = S3Backend(self.conf).bucket
            k = Key(s3_bucket)
            k.key = self.backup_key

            k.set_contents_from_string(json.dumps(archives))

            k.set_acl("private")

    def load_archives(self):
        """Fetch local inventory (stored in shelve)."""
        with glacier_shelve() as d:
            if not d.has_key("archives"):
                d["archives"] = dict()

            return d["archives"]

    def load_archives_from_s3(self):
        """Fetch latest inventory backup from S3."""
        s3_bucket = S3Backend(self.conf).bucket
        try:
            k = Key(s3_bucket)
            k.key = self.backup_key

            return json.loads(k.get_contents_as_string())
        except S3ResponseError, exc:
            return {}

    def restore_inventory(self):
        """Restore inventory from S3 to local shelve."""
        if config.get("aws", "s3_bucket"):
            loaded_archives = self.load_archives_from_s3()

            with glacier_shelve() as d:
                if not d.has_key("archives"):
                    d["archives"] = dict()

                archives = loaded_archives
                d["archives"] = archives
        else:
            raise Exception("You must set s3_bucket in order to backup/restore inventory to/from S3.")


    def upload(self, keyname, filename):
        archive_id = self.vault.concurrent_create_archive_from_file(filename, keyname)

        # Storing the filename => archive_id data.
        with glacier_shelve() as d:
            if not d.has_key("archives"):
                d["archives"] = dict()

            archives = d["archives"]
            archives[keyname] = archive_id
            d["archives"] = archives

        self.backup_inventory()

    def get_archive_id(self, filename):
        """Get the archive_id corresponding to the filename."""
        with glacier_shelve() as d:
            if not d.has_key("archives"):
                d["archives"] = dict()

            archives = d["archives"]

            if filename in archives:
                return archives[filename]

        return None

    def download(self, keyname, job_check=False):
        """Initiate a Job, check its status, and download the archive if it's completed."""
        archive_id = self.get_archive_id(keyname)
        if not archive_id:
            return
        
        with glacier_shelve() as d:
            if not d.has_key("jobs"):
                d["jobs"] = dict()

            jobs = d["jobs"]
            job = None

            if keyname in jobs:
                # The job is already in shelve
                job_id = jobs[keyname]
                try:
                    job = self.vault.get_job(job_id)
                except UnexpectedHTTPResponseError: # Return a 404 if the job is no more available
                    del jobs[keyname]

            if not job:
                # Job initialization
                job = self.vault.retrieve_archive(archive_id)
                jobs[keyname] = job.id
                job_id = job.id

            # Commiting changes in shelve
            d["jobs"] = jobs

        log.info("Job {action}: {status_code} ({creation_date}/{completion_date})".format(**job.__dict__))

        if job.completed:
            log.info("Downloading...")
            encrypted_out = tempfile.TemporaryFile()

            # Boto related, download the file in chunk
            chunk_size = 4 * 1024 * 1024
            num_chunks = int(math.ceil(job.archive_size / float(chunk_size)))
            job._download_to_fileob(encrypted_out, num_chunks, chunk_size,
                                     True, (socket.error, httplib.IncompleteRead))

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
        with glacier_shelve() as d:
            if not d.has_key("archives"):
                d["archives"] = dict()

            return d["archives"].keys()

    def delete(self, keyname):
        archive_id = self.get_archive_id(keyname)
        if archive_id:
            self.vault.delete_archive(archive_id)
            with glacier_shelve() as d:
                archives = d["archives"]

                if keyname in archives:
                    del archives[keyname]

                d["archives"] = archives

            self.backup_inventory()
