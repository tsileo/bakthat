import tarfile
import os
import sys
import ConfigParser
from datetime import datetime
from cStringIO import StringIO
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

app = aaargh.App(description="Compress, encrypt and upload files directly to Amazon S3/Glacier.")

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
app_logger = logging

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
    def __init__(self, conf, logger):
        if conf is None:
            try:
                access_key = config.get("aws", "access_key")
                secret_key = config.get("aws", "secret_key")
                bucket = config.get("aws", "s3_bucket")
            except ConfigParser.NoOptionError:
                app_logger.error("Configuration file not available.")
                app_logger.info("Use 'bakthat configure' to create one.")
                return
        else:
            access_key = conf.get("access_key")
            secret_key = conf.get("secret_key")
            bucket = conf.get("bucket")

        con = boto.connect_s3(access_key, secret_key)
        self.bucket = con.create_bucket(bucket)
        self.container = "S3 Bucket: {}".format(bucket)

    def download(self, keyname):
        k = Key(self.bucket)
        k.key = keyname

        encrypted_out = StringIO()
        k.get_contents_to_file(encrypted_out)
        encrypted_out.seek(0)
        
        return encrypted_out

    def upload(self, keyname, filename):
        k = Key(self.bucket)
        k.key = keyname

        k.set_contents_from_file(filename)
        k.set_acl("private")

    def ls(self):
        return [key.name for key in self.bucket.get_all_keys()]


class GlacierBackend:
    """
    Backend to handle Glacier upload/download
    """
    def __init__(self, conf, logger):
        if conf is None:
            try:
                access_key = config.get("aws", "access_key")
                secret_key = config.get("aws", "secret_key")
                vault_name = config.get("aws", "glacier_vault")
            except ConfigParser.NoOptionError:
                app_logger.error("Configuration file not available.")
                app_logger.info("Use 'bakthat configure' to create one.")
                return
        else:
            access_key = conf.get("access_key")
            secret_key = conf.get("secret_key")
            vault_name = conf.get("vault")

        con = boto.connect_glacier(aws_access_key_id=access_key,
                                    aws_secret_access_key=secret_key)

        self.conf = conf
        self.vault = con.create_vault(vault_name)
        self.logger = logger
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

        s3_bucket = S3Backend(self.conf, self.logger).bucket
        k = Key(s3_bucket)
        k.key = self.backup_key

        k.set_contents_from_string(json.dumps(archives))
        print json.dumps(archives)
        k.set_acl("private")


    def restore_inventory(self):
        """
        Restore inventory from S3 to local shelve
        """
        s3_bucket = S3Backend(self.conf, self.logger).bucket
        k = Key(s3_bucket)
        k.key = self.backup_key

        print json.loads(k.get_contents_as_string())
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

        self.logger.info("Job {action}: {status_code} ({creation_date}/{completion_date})".format(**job.__dict__))

        if job.completed:
            self.logger.info("Downloading...")
            encrypted_out = StringIO()
            encrypted_out.write(job.get_output().read())
            encrypted_out.seek(0)
            return encrypted_out
        else:
            self.logger.info("Not completed yet")
            return None

    def ls(self):
        with glacier_shelve() as d:
            if not d.has_key("archives"):
                d["archives"] = dict()

            return d["archives"].keys()

storage_backends = dict(s3=S3Backend, glacier=GlacierBackend)

@app.cmd(help="Backup a file or a directory, backup the current directory if no arg is provided.")
@app.cmd_arg('-f', '--filename', type=str, default=os.getcwd())
@app.cmd_arg('-d', '--destination', type=str, default="s3", help="s3|glacier")
def backup(filename, destination="s3", **kwargs):
    log = kwargs.get("logger", app_logger)
    conf = kwargs.get("conf", None)
    storage_backend = storage_backends[destination](conf, log)

    log.info("Backing up " + filename)
    arcname = filename.split("/")[-1]
    
    out = StringIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        tar.add(filename, arcname=arcname)

    password = kwargs.get("password")
    if not password:
        password = getpass()

    encrypted_out = StringIO()
    encrypt(out, encrypted_out, password)
    encrypted_out.seek(0)

    stored_filename = arcname + datetime.now().strftime("%Y%m%d") + ".tgz.enc"

    storage_backend.upload(stored_filename, encrypted_out)


@app.cmd(help="Set AWS S3/Glacier credentials.")
def configure():
    config.add_section("aws")
    config.set("aws", "access_key", raw_input("AWS Access Key: "))
    config.set("aws", "secret_key", raw_input("AWS Secret Key: "))
    config.set("aws", "s3_bucket", raw_input("S3 Bucket Name: "))
    config.set("aws", "glacier_vault", raw_input("Glacier Vault Name: "))
    config.write(open(os.path.expanduser("~/.bakthat.conf"), "w"))

    app_logger.info("Config written in %s" % os.path.expanduser("~/.bakthat.conf"))


@app.cmd(help="Restore backup in the current directory.")
@app.cmd_arg('-f', '--filename', type=str, default="")
@app.cmd_arg('-d', '--destination', type=str, default="s3", help="s3|glacier")
def restore(filename, destination="s3", **kwargs):
    log = kwargs.get("logger", app_logger)
    conf = kwargs.get("conf", None)
    storage_backend = storage_backends[destination](conf, log)

    if not filename:
        log.error("No file to restore, use -f to specify one.")
        return

    keys = [name for name in storage_backend.ls() if name.startswith(filename)]
    if not keys:
        log.error("No file matched.")
        return

    key_name = sorted(keys, reverse=True)[0]
    log.info("Restoring " + key_name)

    encrypted_out = storage_backend.download(key_name)

    if encrypted_out:
        password = kwargs.get("password")
        if not password:
            password = getpass()

        out = StringIO()
        decrypt(encrypted_out, out, password)
        out.seek(0)

        tar = tarfile.open(fileobj=out)
        tar.extractall()
        tar.close()
        return True


@app.cmd(help="List stored backups.")
@app.cmd_arg('-d', '--destination', type=str, default="s3", help="s3|glacier")
def ls(destination="s3", **kwargs):
    log = kwargs.get("logger", app_logger)
    conf = kwargs.get("conf", None)
    storage_backend = storage_backends[destination](conf, log)
    
    log.info(storage_backend.container)

    for filename in storage_backend.ls():
        log.info(filename)


@app.cmd(help="Backup Glacier inventory to S3")
def backup_glacier_inventory(**kwargs):
    log = kwargs.get("logger", app_logger)
    conf = kwargs.get("conf", None)
    glacier_backend = GlacierBackend(conf, log)
    glacier_backend.backup_inventory()


@app.cmd(help="Restore Glacier inventory from S3")
def restore_glacier_inventory(**kwargs):
    log = kwargs.get("logger", app_logger)
    conf = kwargs.get("conf", None)
    glacier_backend = GlacierBackend(conf, log)
    glacier_backend.restore_inventory()


def main():
    app.run()

if __name__ == '__main__':
    main()
