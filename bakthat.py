import tarfile
import tempfile
import os
import sys
import ConfigParser
from datetime import datetime
from getpass import getpass
import logging

import boto
from boto.s3.key import Key
import shelve
import boto.glacier
import boto.glacier.layer2
from boto.glacier.exceptions import UnexpectedHTTPResponseError
from beefish import decrypt, encrypt
import aaargh
import json

DEFAULT_LOCATION = "us-east-1"

app = aaargh.App(description="Compress, encrypt and upload files directly to Amazon S3/Glacier.")

log = logging.getLogger(__name__)

if not log.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

config = ConfigParser.SafeConfigParser()
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


class S3Backend:
    """
    Backend to handle S3 upload/download
    """
    def __init__(self, conf):
        if conf is None:
            try:
                access_key = config.get("aws", "access_key")
                secret_key = config.get("aws", "secret_key")
                bucket = config.get("aws", "s3_bucket")
                try:
                    region_name = config.get("aws", "region_name")
                except ConfigParser.NoOptionError:
                    region_name = DEFAULT_LOCATION
            except ConfigParser.NoOptionError:
                log.error("Configuration file not available.")
                log.info("Use 'bakthat configure' to create one.")
                return
        else:
            access_key = conf.get("access_key")
            secret_key = conf.get("secret_key")
            bucket = conf.get("bucket")
            region_name = conf.get("region_name", DEFAULT_LOCATION)

        con = boto.connect_s3(access_key, secret_key)
        if region_name == DEFAULT_LOCATION:
            region_name = ""
        self.bucket = con.create_bucket(bucket, location=region_name)
        self.container = "S3 Bucket: {}".format(bucket)

    def download(self, keyname):
        k = Key(self.bucket)
        k.key = keyname

        encrypted_out = tempfile.TemporaryFile()
        k.get_contents_to_file(encrypted_out)
        encrypted_out.seek(0)
        
        return encrypted_out

    def cb(self, complete, total):
        percent = int(complete * 100.0 / total)
        log.info("Upload completion: {}%".format(percent))

    def upload(self, keyname, filename, cb=True):
        k = Key(self.bucket)
        k.key = keyname
        upload_kwargs = {}
        if cb:
            upload_kwargs = dict(cb=self.cb, num_cb=10)
        k.set_contents_from_file(filename, **upload_kwargs)
        k.set_acl("private")

    def ls(self):
        return [key.name for key in self.bucket.get_all_keys()]

    def delete(self, keyname):
        k = Key(self.bucket)
        k.key = keyname
        self.bucket.delete_key(k)



class GlacierBackend:
    """
    Backend to handle Glacier upload/download
    """
    def __init__(self, conf):
        if conf is None:
            try:
                access_key = config.get("aws", "access_key")
                secret_key = config.get("aws", "secret_key")
                vault_name = config.get("aws", "glacier_vault")
                try:
                    region_name = config.get("aws", "region_name")
                except ConfigParser.NoOptionError:
                    region_name = DEFAULT_LOCATION
            except ConfigParser.NoOptionError:
                log.error("Configuration file not available.")
                log.info("Use 'bakthat configure' to create one.")
                return
        else:
            access_key = conf.get("access_key")
            secret_key = conf.get("secret_key")
            vault_name = conf.get("vault")
            region_name = conf.get("region_name", DEFAULT_LOCATION)

        con = boto.connect_glacier(aws_access_key_id=access_key,
                                    aws_secret_access_key=secret_key, region_name=region_name)

        self.conf = conf
        self.vault = con.create_vault(vault_name)
        self.backup_key = "bakthat_glacier_inventory"
        self.container = "Glacier vault: {}".format(vault_name)

    def backup_inventory(self):
        """
        Backup the local inventory from shelve as a json string to S3
        """
        with glacier_shelve() as d:
            if not d.has_key("archives"):
                d["archives"] = dict()

            archives = d["archives"]

        s3_bucket = S3Backend(self.conf).bucket
        k = Key(s3_bucket)
        k.key = self.backup_key

        k.set_contents_from_string(json.dumps(archives))

        k.set_acl("private")


    def restore_inventory(self):
        """
        Restore inventory from S3 to local shelve
        """
        s3_bucket = S3Backend(self.conf).bucket
        k = Key(s3_bucket)
        k.key = self.backup_key

        loaded_archives = json.loads(k.get_contents_as_string())

        with glacier_shelve() as d:
            if not d.has_key("archives"):
                d["archives"] = dict()

            archives = loaded_archives
            d["archives"] = archives


    def upload(self, keyname, filename):
        archive_id = self.vault.create_archive_from_file(file_obj=filename)

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

    def download(self, keyname):
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
                    del job[keyname]

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
            encrypted_out.write(job.get_output().read())
            encrypted_out.seek(0)
            return encrypted_out
        else:
            log.info("Not completed yet")
            return None

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

storage_backends = dict(s3=S3Backend, glacier=GlacierBackend)

@app.cmd(help="Backup a file or a directory, backup the current directory if no arg is provided.")
@app.cmd_arg('-f', '--filename', type=str, default=os.getcwd())
@app.cmd_arg('-d', '--destination', type=str, default="s3", help="s3|glacier")
def backup(filename, destination="s3", **kwargs):
    conf = kwargs.get("conf", None)
    storage_backend = storage_backends[destination](conf)

    log.info("Backing up " + filename)
    arcname = filename.split("/")[-1]
    stored_filename = arcname + datetime.now().strftime("%Y%m%d%H%M%S") + ".tgz"
    
    password = kwargs.get("password")
    if not password:
        password = getpass("Password (blank to disable encryption): ")

    log.info("Compressing...")
    out = tempfile.TemporaryFile()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        tar.add(filename, arcname=arcname)

    if password:
        log.info("Encrypting...")
        encrypted_out = tempfile.TemporaryFile()
        encrypt(out, encrypted_out, password)
        stored_filename += ".enc"
        out = encrypted_out

    log.info("Uploading...")
    out.seek(0)
    storage_backend.upload(stored_filename, out)


@app.cmd(help="Set AWS S3/Glacier credentials.")
def configure():
    config.add_section("aws")
    config.set("aws", "access_key", raw_input("AWS Access Key: "))
    config.set("aws", "secret_key", raw_input("AWS Secret Key: "))
    config.set("aws", "s3_bucket", raw_input("S3 Bucket Name: "))
    config.set("aws", "glacier_vault", raw_input("Glacier Vault Name: "))
    region_name = raw_input("Region Name (" + DEFAULT_LOCATION + "): ")
    if not region_name:
        region_name = DEFAULT_LOCATION
    config.set("aws", "region_name", region_name)
    config.write(open(os.path.expanduser("~/.bakthat.conf"), "w"))

    log.info("Config written in %s" % os.path.expanduser("~/.bakthat.conf"))


@app.cmd(help="Restore backup in the current directory.")
@app.cmd_arg('-f', '--filename', type=str, default="")
@app.cmd_arg('-d', '--destination', type=str, default="s3", help="s3|glacier")
def restore(filename, destination="s3", **kwargs):
    conf = kwargs.get("conf", None)
    storage_backend = storage_backends[destination](conf)

    if not filename:
        log.error("No file to restore, use -f to specify one.")
        return

    keys = [name for name in storage_backend.ls() if name.startswith(filename)]
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
    out = storage_backend.download(key_name)

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


@app.cmd(help="Delete a backup.")
@app.cmd_arg('-f', '--filename', type=str, default="")
@app.cmd_arg('-d', '--destination', type=str, default="s3", help="s3|glacier")
def delete(filename, destination="s3", **kwargs):
    conf = kwargs.get("conf", None)
    storage_backend = storage_backends[destination](conf)

    if not filename:
        log.error("No file to delete, use -f to specify one.")
        return

    keys = [name for name in storage_backend.ls() if name.startswith(filename)]
    if not keys:
        log.error("No file matched.")
        return

    key_name = sorted(keys, reverse=True)[0]
    log.info("Deleting " + key_name)

    storage_backend.delete(key_name)


@app.cmd(help="List stored backups.")
@app.cmd_arg('-d', '--destination', type=str, default="s3", help="s3|glacier")
def ls(destination="s3", **kwargs):
    conf = kwargs.get("conf", None)
    storage_backend = storage_backends[destination](conf)
    
    log.info(storage_backend.container)

    for filename in storage_backend.ls():
        log.info(filename)


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
