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
from beefish import decrypt, encrypt
import aaargh

app = aaargh.App(description="Compress, encrypt and upload files directly to Amazon S3.")

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
app_logger = logging

config = ConfigParser.SafeConfigParser()
config.read(os.path.expanduser("~/.bakthat.conf"))


def get_bucket(conf):
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
    return con.create_bucket(bucket)


@app.cmd(help="Backup a file or a directory, backup the current directory if no arg is provided.")
@app.cmd_arg('-f', '--filename', type=str, default=os.getcwd())
def backup(filename, **kwargs):
    log = kwargs.get("logger", app_logger)
    conf = kwargs.get("conf", None)
    bucket= get_bucket(conf)
    if not bucket:
        return

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

    k = Key(bucket)
    k.key = arcname + datetime.now().strftime("%Y%m%d") + ".tgz.enc"
    k.set_contents_from_file(encrypted_out)
    k.set_acl("private")


@app.cmd(help="Set AWS S3 credentials.")
def configure():
    config.add_section("aws")
    config.set("aws", "access_key", raw_input("AWS Access Key: "))
    config.set("aws", "secret_key", raw_input("AWS Secret Key: "))
    config.set("aws", "s3_bucket", raw_input("S3 Bucket Name: "))
    config.write(open(os.path.expanduser("~/.bakthat.conf"), "w"))

    app_logger.info("Config written in %s" % os.path.expanduser("~/.bakthat.conf"))


@app.cmd(help="Restore backup in the current directory.")
@app.cmd_arg('-f', '--filename', type=str, default="")
def restore(filename, **kwargs):
    log = kwargs.get("logger", app_logger)
    conf = kwargs.get("conf", None)
    bucket= get_bucket(conf)
    if not bucket:
        return

    if not filename:
        log.error("No file to restore, use -f to specify one.")
        return

    keys = [key.name for key in bucket.get_all_keys() if key.name.startswith(filename)]
    if not keys:
        log.error("No file matched.")
        return

    key_name = sorted(keys, reverse=True)[0]
    log.info("Restoring " + key_name)

    k = Key(bucket)
    k.key = (key_name)

    encrypted_out = StringIO()
    k.get_contents_to_file(encrypted_out)
    encrypted_out.seek(0)

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
def ls(**kwargs):
    log = kwargs.get("logger", app_logger)
    conf = kwargs.get("conf", None)
    bucket= get_bucket(conf)
    if not bucket:
        return

    log.info("S3 Bucket: " + config.get("aws", "s3_bucket"))

    for key in bucket.get_all_keys():
        log.info(key.name)
    return True


def main():
    app.run()

if __name__ == '__main__':
    main()
