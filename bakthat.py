#!/usr/bin/env python2
# -*- encoding: utf-8 -*-
import tarfile
import tempfile
import os
import sys
import ConfigParser
from datetime import datetime
from getpass import getpass
import logging
import shelve
import json
import re
import socket
import httplib
import math
import mimetypes

from contextlib import closing # for Python2.6 compatibility

import boto
from boto.s3.key import Key
import boto.glacier
import boto.glacier.layer2
from boto.glacier.exceptions import UnexpectedHTTPResponseError
from boto.exception import S3ResponseError
from beefish import decrypt, encrypt_file
import aaargh

__version__ = "0.3.7"

DEFAULT_LOCATION = "us-east-1"
DEFAULT_DESTINATION = "s3"

app = aaargh.App(description="Compress, encrypt and upload files directly to Amazon S3/Glacier.")

log = logging.getLogger(__name__)

if not log.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

config = ConfigParser.SafeConfigParser({"default_destination": DEFAULT_DESTINATION})
config.read(os.path.expanduser("~/.bakthat.conf"))

class glacier_shelve(object):
    """
    Context manager for shelve
    """

    def __enter__(self):
        self.shelve = shelve.open(os.path.expanduser("~/.bakthat.db"))

        return self.shelve

    def __exit__(self, exc_type, exc_value, traceback):
        self.shelve.close()


class BakthatBackend:
    """Handle Configuration for Backends."""
    def __init__(self, conf=None, extra_conf=[]):
        self.custom_conf = None
        self.conf = {}
        if conf is None:
            try:
                self.conf["access_key"] = config.get("aws", "access_key")
                self.conf["secret_key"] = config.get("aws", "secret_key")
                self.conf["region_name"] = config.get("aws", "region_name")

                for key in extra_conf:
                    try:
                        self.conf[key] = config.get("aws", key)
                    except Exception, exc:
                        log.exception(exc)
                        log.error("Missing configuration variable")
                        self.conf[key] = None

            except ConfigParser.NoOptionError:
                log.error("Configuration file not available.")
                log.info("Use 'bakthat configure' to create one.")
                return
        else:
            self.conf["access_key"] = conf.get("access_key")
            self.conf["secret_key"] = conf.get("secret_key")
            self.conf["region_name"] = conf.get("region_name", DEFAULT_LOCATION)

            for key in extra_conf:
                self.conf[key] = conf.get(key)


class S3Backend(BakthatBackend):
    """
    Backend to handle S3 upload/download
    """
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
    """
    Backend to handle Glacier upload/download
    """
    def __init__(self, conf=None):
        BakthatBackend.__init__(self, conf, extra_conf=["glacier_vault"])

        con = boto.connect_glacier(aws_access_key_id=self.conf["access_key"],
                                    aws_secret_access_key=self.conf["secret_key"],
                                    region_name=self.conf["region_name"])

        self.vault = con.create_vault(self.conf["glacier_vault"])
        self.backup_key = "bakthat_glacier_inventory"
        self.container = "Glacier vault: {0}".format(self.conf["glacier_vault"])


    def backup_inventory(self):
        """
        Backup the local inventory from shelve as a json string to S3
        """
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
        """
        Restore inventory from S3 to local shelve
        """
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
        """
        Get the archive_id corresponding to the filename
        """
        with glacier_shelve() as d:
            if not d.has_key("archives"):
                d["archives"] = dict()

            archives = d["archives"]

            if filename in archives:
                return archives[filename]

        return None

    def download(self, keyname, job_check=False):
        """
        Initiate a Job, check its status, and download the archive if it's completed.
        """
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
        """
        Initiate a job to retrieve Galcier inventory or output inventory
        """
        if jobid is None:
            return self.vault.retrieve_inventory(sns_topic=None, description="Bakthat inventory job")
        else:
            return self.vault.get_job(jobid)

    def retrieve_archive(self, archive_id, jobid):
        """
        Initiate a job to retrieve Galcier archive or download archive
        """
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

STORAGE_BACKEND = dict(s3=S3Backend, glacier=GlacierBackend)

def _get_store_backend(conf, destination=DEFAULT_DESTINATION):
    if not destination:
        destination = config.get("aws", "default_destination")
    return STORAGE_BACKEND[destination](conf)

def _match_filename(filename, destination=DEFAULT_DESTINATION, conf=None):
    storage_backend = _get_store_backend(conf, destination)

    keys = [name for name in storage_backend.ls() if name.startswith(filename)]
    keys.sort(reverse=True)
    return keys

def match_filename(filename, destination=DEFAULT_DESTINATION, conf=None):
    _keys = _match_filename(filename, destination, conf)
    regex_key = re.compile(r"(.+)(\d{14})\.tgz(\.enc)?")
    keys = []
    for key in _keys:
        try:
            filename, datestr, isenc = re.findall(regex_key, key)[0]
            keys.append(dict(filename=filename,
                        key=key,
                        backup_date=datetime.strptime(datestr, "%Y%m%d%H%M%S"),
                        is_enc=bool(isenc)))
        except:
            pass # If the file has been backed up with an older version of bakthat
    return keys


@app.cmd(help="Backup a file or a directory, backup the current directory if no arg is provided.")
@app.cmd_arg('-f', '--filename', type=str, default=os.getcwd())
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier")
@app.cmd_arg('-s', '--description', type=str, default=None)
@app.cmd_arg('-p', '--prompt', type=str, help="yes|no", default="yes")
def backup(filename, destination=None, description=None, prompt="yes", **kwargs):
    conf = kwargs.get("conf", None)
    storage_backend = _get_store_backend(conf, destination)

    log.info("Backing up " + filename)
    arcname = filename.strip('/').split('/')[-1]
    date_component = datetime.now().strftime("%Y%m%d%H%M%S")
    stored_filename = arcname +  date_component + ".tgz"
    
    password = kwargs.get("password")
    if password is None and prompt.lower() != "no":
        password = getpass("Password (blank to disable encryption): ")
        if password:
            password2 = getpass("Password confirmation: ")
            if password != password2:
                log.error("Password confirmation doesn't match")
                return

    if mimetypes.guess_type(arcname) == ('application/x-tar', 'gzip'):
        log.info("File already compressed")
        outname = filename

        new_arcname = re.sub(r'(\.t(ar\.)?gz)', '', arcname)
        stored_filename = new_arcname + date_component + ".tgz"

        bakthat_compression = False
    else:
        log.info("Compressing...")
        with tempfile.NamedTemporaryFile(delete=False) as out:
            with closing(tarfile.open(fileobj=out, mode="w:gz")) as tar:
                tar.add(filename, arcname=arcname)
            outname = out.name

        bakthat_compression = True

    if password:
        log.info("Encrypting...")
        encrypted_out = tempfile.NamedTemporaryFile(delete=False)
        encrypt_file(outname, encrypted_out.name, password)
        stored_filename += ".enc"
        os.remove(outname)  # remove non-encrypted tmp file
        outname = encrypted_out.name

    log.info("Uploading...")
    storage_backend.upload(stored_filename, outname)

    # We only remove the file if the archive is created by bakthat
    if bakthat_compression:
        os.remove(outname)

    return True


@app.cmd(help="Give informations about stored filename, current directory if no arg is provided.")
@app.cmd_arg('-f', '--filename', type=str, default=os.getcwd())
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier")
@app.cmd_arg('-s', '--description', type=str, default=None)
def info(filename, destination=None, description=None, **kwargs):
    conf = kwargs.get("conf", None)
    storage_backend = _get_store_backend(conf, destination)
    filename = filename.split("/")[-1]
    keys = match_filename(filename, destination if destination else DEFAULT_DESTINATION)
    if not keys:
        log.info("No matching backup found for " + str(filename))
        key = None
    else:
        key = keys[0]
        log.info("Last backup date: {0} ({1} versions)".format(key["backup_date"].isoformat(),
                                                    str(len(keys))))
    return key

@app.cmd(help="Set AWS S3/Glacier credentials.")
def configure():
    config.add_section("aws")
    config.set("aws", "access_key", raw_input("AWS Access Key: "))
    config.set("aws", "secret_key", raw_input("AWS Secret Key: "))
    config.set("aws", "s3_bucket", raw_input("S3 Bucket Name: "))
    while 1:
        default_destination = raw_input("Default destination ({0}): ".format(DEFAULT_DESTINATION))
        if default_destination:
            default_destination = default_destination.lower()
            if default_destination in ("s3", "glacier"):
                break
            else:
                log.error("Invalid default_destination, should be s3 or glacier, try again.")
        else:
            default_destination = DEFAULT_DESTINATION
    config.set("aws", "default_destination", default_destination)
    config.set("aws", "glacier_vault", raw_input("Glacier Vault Name: "))
    region_name = raw_input("Region Name ({0}): ".format(DEFAULT_LOCATION))
    if not region_name:
        region_name = DEFAULT_LOCATION
    config.set("aws", "region_name", region_name)
    config.write(open(os.path.expanduser("~/.bakthat.conf"), "w"))

    log.info("Config written in %s" % os.path.expanduser("~/.bakthat.conf"))


@app.cmd(help="Restore backup in the current directory.")
@app.cmd_arg('-f', '--filename', type=str, default="")
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier")
def restore(filename, destination=None, **kwargs):
    conf = kwargs.get("conf", None)
    storage_backend = _get_store_backend(conf, destination)

    if not filename:
        log.error("No file to restore, use -f to specify one.")
        return

    keys = _match_filename(filename, destination if destination else DEFAULT_DESTINATION)
    if not keys:
        log.error("No file matched.")
        return

    key_name = sorted(keys, reverse=True)[0]
    log.info("Restoring " + key_name)

    # Asking password before actually download to avoid waiting
    if key_name and key_name.endswith(".enc"):
        password = kwargs.get("password")
        if not password:
            password = getpass()

    log.info("Downloading...")
    
    download_kwargs = {}
    if kwargs.get("job_check"):
        download_kwargs["job_check"] = True
        log.info("Job Check: " + repr(download_kwargs))

    out = storage_backend.download(key_name, **download_kwargs)

    if kwargs.get("job_check"):
        log.info("Job Check Request")
        # If it's a job_check call, we return Glacier job data
        return out

    if out and key_name.endswith(".enc"):
        log.info("Decrypting...")
        decrypted_out = tempfile.TemporaryFile()
        decrypt(out, decrypted_out, password)
        out = decrypted_out

    if out:
        log.info("Uncompressing...")
        out.seek(0)
        tar = tarfile.open(fileobj=out)
        tar.extractall()
        tar.close()

        return True


@app.cmd(help="Delete a backup.")
@app.cmd_arg('-f', '--filename', type=str, default="")
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier")
def delete(filename, destination=None, **kwargs):
    conf = kwargs.get("conf", None)
    storage_backend = _get_store_backend(conf, destination)

    if not filename:
        log.error("No file to delete, use -f to specify one.")
        return

    keys = _match_filename(filename, destination, conf)
    if not keys:
        log.error("No file matched.")
        return

    # Get first matching keys => the most recent
    key_name = keys[0]

    log.info("Deleting " + key_name)

    storage_backend.delete(key_name)

    return True


@app.cmd(help="List stored backups.")
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier")
def ls(destination=None, **kwargs):
    conf = kwargs.get("conf", None)
    storage_backend = _get_store_backend(conf, destination)
    
    log.info(storage_backend.container)

    for filename in storage_backend.ls():
        log.info(filename)

@app.cmd(help="Show Glacier inventory from S3")
def show_glacier_inventory(**kwargs):
    if config.get("aws", "s3_bucket"):
        conf = kwargs.get("conf", None)
        glacier_backend = GlacierBackend(conf)
        loaded_archives = glacier_backend.load_archives_from_s3()
        log.info(json.dumps(loaded_archives, sort_keys=True, indent=4, separators=(',', ': ')))
    else:
        log.error("No S3 bucket defined.")

@app.cmd(help="Show local Glacier inventory (from shelve file)")
def show_local_glacier_inventory(**kwargs):
    conf = kwargs.get("conf", None)
    glacier_backend = GlacierBackend(conf)
    archives = glacier_backend.load_archives()
    log.info(json.dumps(archives, sort_keys=True, indent=4, separators=(',', ': ')))

@app.cmd(help="Backup Glacier inventory to S3")
def backup_glacier_inventory(**kwargs):
    conf = kwargs.get("conf", None)
    glacier_backend = GlacierBackend(conf)
    glacier_backend.backup_inventory()


@app.cmd(help="Restore Glacier inventory from S3")
def restore_glacier_inventory(**kwargs):
    conf = kwargs.get("conf", None)
    glacier_backend = GlacierBackend(conf)
    glacier_backend.restore_inventory()


def main():
    app.run()

if __name__ == '__main__':
    main()
