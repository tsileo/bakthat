# -*- encoding: utf-8 -*-
import tarfile
import tempfile
import os
import sys
import ConfigParser
from datetime import datetime, timedelta
from getpass import getpass
import logging
import json
import re
import mimetypes
import calendar
from contextlib import closing # for Python2.6 compatibility

import yaml
import boto
from beefish import decrypt, encrypt_file
import aaargh
import grandfatherson
from byteformat import ByteFormatter

from bakthat.backends import GlacierBackend, S3Backend, RotationConfig
from bakthat.conf import config, dump_truck, DEFAULT_DESTINATION, DEFAULT_LOCATION, CONFIG_FILE
from bakthat.utils import (dump_truck_delete_backup,
                            dump_truck_insert_backup,
                            dump_truck_get_backup,
                            _get_query,
                            _timedelta_total_seconds,
                            _interval_string_to_seconds)

__version__ = "0.4.0"

app = aaargh.App(description="Compress, encrypt and upload files directly to Amazon S3/Glacier.")

log = logging.getLogger()

STORAGE_BACKEND = dict(s3=S3Backend, glacier=GlacierBackend)

def _get_store_backend(conf, destination=DEFAULT_DESTINATION, profile="default"):
    if not destination:
        destination = config.get("aws", "default_destination")
    return STORAGE_BACKEND[destination](conf, profile)


def _match_filename(filename, destination=DEFAULT_DESTINATION, conf=None, profile="default"):
    """Return all stored backups keys for a given filename."""
    if not filename:
        raise Exception("Filename can't be blank")
    storage_backend = _get_store_backend(conf, destination, profile)

    keys = [name for name in storage_backend.ls() if name.startswith(filename)]
    keys.sort(reverse=True)
    return keys


def match_filename(filename, destination=DEFAULT_DESTINATION, conf=None, profile="default"):
    """Return a list of dict with backup_name, date_component, and is_enc."""
    _keys = _match_filename(filename, destination, conf, profile)
    regex_key = re.compile(r"(?P<backup_name>.+)\.(?P<date_component>\d{14})\.tgz(?P<is_enc>\.enc)?")

    # old regex for backward compatibility (for files without dot before the date component).
    old_regex_key = re.compile(r"(?P<backup_name>.+)(?P<date_component>\d{14})\.tgz(?P<is_enc>\.enc)?")
    
    keys = []
    for key in _keys:
        match = regex_key.match(key)

        # Backward compatibility
        if not match:
            match = old_regex_key.match(key)
        
        if match:
            keys.append(dict(filename=match.group("backup_name"),
                        key=key,
                        backup_date=datetime.strptime(match.group("date_component"), "%Y%m%d%H%M%S"),
                        is_enc=bool(match.group("is_enc"))))
    return keys


@app.cmd(help="Delete backups older than the given interval string.")
@app.cmd_arg('-f', '--filename', type=str, default=os.getcwd())
@app.cmd_arg('-i', '--interval', type=str, help="Interval string like 1M, 1W, 1M3W4h2s")
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier")
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
def delete_older_than(filename, interval, destination=DEFAULT_DESTINATION, profile="default", **kwargs):
    """Delete backups matching the given filename older than the given interval string.

    :type filename: str
    :param filename: File/directory name.

    :type interval: str
    :param interval: Interval string like 1M, 1W, 1M3W4h2s... 
        (s => seconds, m => minutes, h => hours, D => days, W => weeks, M => months, Y => Years).

    :type destination: str
    :param destination: glacier|s3

    :type conf: dict
    :keyword conf: Override/set AWS configuration.
        
    :rtype: list
    :return: A list containing the deleted keys (S3) or archives (Glacier).

    """
    conf = kwargs.get("conf")
    storage_backend = _get_store_backend(conf, destination, profile)
    interval_seconds = _interval_string_to_seconds(interval)

    deleted = []

    backup_date_filter = int(datetime.utcnow().strftime("%s")) - interval_seconds
    query = "SELECT stored_filename FROM backups WHERE backend == '{0}' \
             AND backup_date < {1:d} AND filename LIKE '{2}%' AND is_deleted == 0"
    for backup in dump_truck.execute(query.format(destination, backup_date_filter, filename)):
        real_key = backup.get("stored_filename")
        log.info("Deleting {0}".format(real_key))
        storage_backend.delete(real_key)
        dump_truck_delete_backup(real_key)
        deleted.append(real_key)

    return deleted

@app.cmd(help="Rotate backups using Grandfather-father-son backup rotation scheme.")
@app.cmd_arg('-f', '--filename', type=str, default=os.getcwd())
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier", default=DEFAULT_DESTINATION)
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
def rotate_backups(filename, destination=DEFAULT_DESTINATION, profile="default", **kwargs):
    """Rotate backup using grandfather-father-son rotation scheme.

    :type filename: str
    :param filename: File/directory name.

    :type destination: str
    :param destination: s3|glacier

    :type conf: dict
    :keyword conf: Override/set AWS configuration.

    :type days: int
    :keyword days: Number of days to keep.

    :type weeks: int
    :keyword weeks: Number of weeks to keep.

    :type months: int
    :keyword months: Number of months to keep.

    :type first_week_day: str
    :keyword first_week_day: First week day (to calculate wich weekly backup keep, saturday by default).
        
    :rtype: list
    :return: A list containing the deleted keys (S3) or archives (Glacier).

    """
    conf = kwargs.get("conf", None)
    storage_backend = _get_store_backend(conf, destination, profile)
    rotate = RotationConfig(kwargs, profile)
    if not rotate:
        raise Exception("You must run bakthat configure_backups_rotation or provide rotation configuration.")

    deleted = []

    query = "SELECT backup_date FROM backups WHERE backend == '{0}' \
            AND filename LIKE '{1}%' AND is_deleted == 0".format(destination, filename)

    backups = dump_truck.execute(query)
    backups_date = [datetime.fromtimestamp(float(backup["backup_date"])) for backup in backups]

    to_delete = grandfatherson.to_delete(backups_date, days=int(rotate.conf["days"]),
                                                    weeks=int(rotate.conf["weeks"]),
                                                    months=int(rotate.conf["months"]),
                                                    firstweekday=int(rotate.conf["first_week_day"]),
                                                    now=datetime.utcnow())
    
    for delete_date in to_delete:
        backup_date = int(delete_date.strftime("%s"))
        query = "SELECT stored_filename FROM backups WHERE backend == '{0}' \
                AND filename LIKE '{1}%' AND backup_date == {2:d} \
                AND is_deleted == 0".format(destination, filename, backup_date)
        backups = dump_truck.execute(query)
        if backups:
            real_key = backups[0].get("stored_filename")
            log.info("Deleting {0}".format(real_key))
            storage_backend.delete(real_key)
            dump_truck_delete_backup(real_key)
            deleted.append(real_key)

    return deleted

@app.cmd(help="Backup a file or a directory, backup the current directory if no arg is provided.")
@app.cmd_arg('-f', '--filename', type=str, default=os.getcwd())
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier", default=DEFAULT_DESTINATION)
@app.cmd_arg('--prompt', type=str, help="yes|no", default="yes")
@app.cmd_arg('-t', '--tags', type=str, help="space separated tags", default="")
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
def backup(filename, destination=None, prompt="yes", tags=[], profile="default", **kwargs):
    """Perform backup.

    :type filename: str
    :param filename: File/directory to backup.
            
    :type destination: str
    :param destination: s3|glacier

    :type prompt: str
    :param prompt: Disable password promp, disable encryption,
        only useful when using bakthat in command line mode.

    :type tags: str or list
    :param tags: Tags either in a str space separated,
        either directly a list of str (if calling from Python).

    :type password: str
    :keyword password: Password, empty string to disable encryption.

    :type conf: dict
    :keyword conf: Override/set AWS configuration.

    :rtype: dict
    :return: A dict containing the following keys: stored_filename, size, metadata, backend and filename.

    """
    conf = kwargs.get("conf", None)
    storage_backend = _get_store_backend(conf, destination, profile)
    backup_file_fmt = "{0}.{1}.tgz"

    log.info("Backing up " + filename)
    arcname = filename.strip('/').split('/')[-1]
    now = datetime.utcnow()
    date_component = now.strftime("%Y%m%d%H%M%S")
    stored_filename = backup_file_fmt.format(arcname, date_component)
    
    backup_data = dict(filename=arcname, 
                    backup_date=int(now.strftime("%s")),
                    backend=destination,
                    is_deleted=False)

    password = kwargs.get("password")
    if password is None and prompt.lower() != "no":
        password = getpass("Password (blank to disable encryption): ")
        if password:
            password2 = getpass("Password confirmation: ")
            if password != password2:
                log.error("Password confirmation doesn't match")
                return


    # Check if the file is not already compressed
    if mimetypes.guess_type(arcname) == ('application/x-tar', 'gzip'):
        log.info("File already compressed")
        outname = filename

        new_arcname = re.sub(r'(\.t(ar\.)?gz)', '', arcname)
        stored_filename = backup_file_fmt.format(new_arcname, date_component)
        
        with open(outname) as outfile:
            backup_data["size"] = os.fstat(outfile.fileno()).st_size

        bakthat_compression = False
    else:
        # If not we compress it
        log.info("Compressing...")
        with tempfile.NamedTemporaryFile(delete=False) as out:
            with closing(tarfile.open(fileobj=out, mode="w:gz")) as tar:
                tar.add(filename, arcname=arcname)
            outname = out.name
            out.seek(0)
            backup_data["size"] = os.fstat(out.fileno()).st_size
        bakthat_compression = True

    bakthat_encryption = False
    if password:
        bakthat_encryption = True
        log.info("Encrypting...")
        encrypted_out = tempfile.NamedTemporaryFile(delete=False)
        encrypt_file(outname, encrypted_out.name, password)
        stored_filename += ".enc"

        # We only remove the file if the archive is created by bakthat
        if bakthat_compression:
            os.remove(outname)  # remove non-encrypted tmp file

        outname = encrypted_out.name

        encrypted_out.seek(0)
        backup_data["size"] = os.fstat(encrypted_out.fileno()).st_size

    # Handling tags metadata
    if isinstance(tags, (str, unicode)):
        tags = tags.split()

    backup_data["tags"] = tags

    backup_data["metadata"] = dict(is_enc=bakthat_encryption)
    backup_data["stored_filename"] = stored_filename

    log.info("Uploading...")
    storage_backend.upload(stored_filename, outname)

    # We only remove the file if the archive is created by bakthat
    if bakthat_encryption:
        os.remove(outname)

    log.debug(backup_data)

    # Insert backup metadata in SQLite
    dump_truck_insert_backup(backup_data)
        
    return backup_data


@app.cmd(help="Give informations about stored filename, current directory if no arg is provided.")
@app.cmd_arg('-f', '--filename', type=str, default=os.getcwd())
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier")
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
def info(filename, destination=None, profile="default", **kwargs):
    conf = kwargs.get("conf", None)
    storage_backend = _get_store_backend(conf, destination, profile)
    filename = filename.split("/")[-1]
    keys = match_filename(filename, destination if destination else DEFAULT_DESTINATION, profile)
    if not keys:
        log.info("No matching backup found for " + str(filename))
        key = None
    else:
        key = keys[0]
        log.info("Last backup date: {0} ({1} versions)".format(key["backup_date"].isoformat(),
                                                    str(len(keys))))
    return key


@app.cmd(help="Show backups list.")
@app.cmd_arg('-q', '--query', type=str, default="", help="search filename for query")
@app.cmd_arg('-d', '--destination', type=str, default="", help="glacier|s3, default both")
@app.cmd_arg('-t', '--tags', type=str, default="", help="tags space separated")
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
def show(query="", destination=DEFAULT_DESTINATION, tags=[], profile="default"):
    query = _get_query(tags=tags, destination=destination, query=query)
    if query:
        query = "WHERE " + query
    backups = dump_truck.execute("SELECT * FROM backups {0}".format(query))
    _display_backups(backups)


def _display_backups(backups):
    bytefmt = ByteFormatter()
    for backup in backups:
        backup["backup_date"] = datetime.fromtimestamp(float(backup["backup_date"])).isoformat()
        backup["size"] = bytefmt(backup["size"])
        backup["tags"] = u", ".join(backup["tags"])

        log.info("{backup_date}\t{backend}\t{size}\t{stored_filename}\t{tags}".format(**backup))

@app.cmd(help="Set AWS S3/Glacier credentials.")
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
def configure(profile="default"):
    new_conf = config.copy()
    new_conf[profile] = config.get(profile, {})

    new_conf_file = open(CONFIG_FILE, "w")

    new_conf[profile]["access_key"] = raw_input("AWS Access Key: ")
    new_conf[profile]["secret_key"] = raw_input("AWS Secret Key: ")
    new_conf[profile]["s3_bucket"] = raw_input("S3 Bucket Name: ")
    new_conf[profile]["glacier_vault"] = raw_input("Glacier Vault Name: ")

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
            break

    new_conf[profile]["default_destination"] = default_destination
    region_name = raw_input("Region Name ({0}): ".format(DEFAULT_LOCATION))
    if not region_name:
        region_name = DEFAULT_LOCATION
    new_conf[profile]["region_name"] = region_name

    yaml.dump(new_conf, new_conf_file, default_flow_style=False)

    log.info("Config written in %s" % CONFIG_FILE)
    log.info("Run bakthat configure_backups_rotation if needed.")


@app.cmd(help="Configure backups rotation")
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
def configure_backups_rotation(profile="default"):
    rotation_conf = {"rotation": {}}
    rotation_conf["rotation"]["days"] = int(raw_input("Number of days to keep: "))
    rotation_conf["rotation"]["weeks"] = int(raw_input("Number of weeks to keep: "))
    rotation_conf["rotation"]["months"] = int(raw_input("Number of months to keep: "))
    while 1:
        first_week_day = raw_input("First week day (to calculate wich weekly backup keep, saturday by default): ")
        if first_week_day:
            if hasattr(calendar, first_week_day.upper()):
                first_week_day = getattr(calendar, first_week_day.upper())
                break
            else:
                log.error("Invalid first_week_day, please choose from sunday to saturday.")
        else:
            first_week_day = calendar.SATURDAY
            break
    rotation_conf["rotation"]["first_week_day"] = int(first_week_day)
    conf_file = open(CONFIG_FILE, "w")
    new_conf = config.copy()
    new_conf[profile].update(rotation_conf)
    yaml.dump(new_conf, conf_file, default_flow_style=False)
    log.info("Config written in %s" % CONFIG_FILE)


@app.cmd(help="Restore backup in the current directory.")
@app.cmd_arg('-f', '--filename', type=str, default="")
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier", default=DEFAULT_DESTINATION)
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
def restore(filename, destination=DEFAULT_DESTINATION, profile="default", **kwargs):
    """Restore backup in the current working directory.

    :type filename: str
    :param filename: File/directory to backup.
            
    :type destination: str
    :param destination: s3|glacier

    :type profile: str
    :param profile: Profile name (default by default).

    :type conf: dict
    :keyword conf: Override/set AWS configuration.

    :rtype: bool
    :return: True if successful.
    """
    conf = kwargs.get("conf", None)
    storage_backend = _get_store_backend(conf, destination, profile)

    if not filename:
        log.error("No file to restore, use -f to specify one.")
        return

    backup = dump_truck_get_backup(filename, destination)

    if not backup:
        log.error("No file matched.")
        return

    key_name = backup.get("stored_filename")
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
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier", default=DEFAULT_DESTINATION)
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
def delete(filename, destination=DEFAULT_DESTINATION, profile="default", **kwargs):
    """Delete a backup.

    :type filename: str
    :param filename: stored filename to delete.

    :type destination: str
    :param destination: glacier|s3

    :type profile: str
    :param profile: Profile name (default by default).

    :type conf: dict
    :keyword conf: A dict with a custom configuration.

    :type conf: dict
    :keyword conf: Override/set AWS configuration.

    :rtype: bool
    :return: True if the file is deleted.

    """
    conf = kwargs.get("conf", None)
    
    if not filename:
        log.error("No file to delete, use -f to specify one.")
        return

    backup = dump_truck_get_backup(filename, destination)
    if not backup:
        log.error("No file matched.")
        return

    key_name = backup.get("stored_filename")

    storage_backend = _get_store_backend(conf, destination, profile)

    log.info("Deleting {0}".format(key_name))

    storage_backend.delete(key_name)

    dump_truck_delete_backup(key_name)

    return True


@app.cmd(help="List stored backups.")
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier")
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
def ls(destination=None, profile="default", **kwargs):
    conf = kwargs.get("conf", None)
    storage_backend = _get_store_backend(conf, destination, profile)
    
    log.info(storage_backend.container)

    ls_result = storage_backend.ls()

    for filename in ls_result:
        log.info(filename)

    return ls_result

@app.cmd(help="Show Glacier inventory from S3")
def show_glacier_inventory(**kwargs):
    if config.get("aws", "s3_bucket"):
        conf = kwargs.get("conf", None)
        glacier_backend = GlacierBackend(conf)
        loaded_archives = glacier_backend.load_archives_from_s3()
        log.info(json.dumps(loaded_archives, sort_keys=True, indent=4, separators=(',', ': ')))
    else:
        log.error("No S3 bucket defined.")
    return loaded_archives


@app.cmd(help="Show local Glacier inventory (from shelve file)")
def show_local_glacier_inventory(**kwargs):
    conf = kwargs.get("conf", None)
    glacier_backend = GlacierBackend(conf)
    archives = glacier_backend.load_archives()
    log.info(json.dumps(archives, sort_keys=True, indent=4, separators=(',', ': ')))
    return archives


@app.cmd(help="Backup Glacier inventory to S3")
def backup_glacier_inventory(**kwargs):
    """Backup Glacier inventory to S3.

    :type conf: dict
    :keyword conf: Override/set AWS configuration.

    """
    conf = kwargs.get("conf", None)
    glacier_backend = GlacierBackend(conf)
    glacier_backend.backup_inventory()


@app.cmd(help="Restore Glacier inventory from S3")
def restore_glacier_inventory(**kwargs):
    """Restore custom Glacier inventory from S3.

    :type conf: dict
    :keyword conf: Override/set AWS configuration.

    """
    conf = kwargs.get("conf", None)
    glacier_backend = GlacierBackend(conf)
    glacier_backend.restore_inventory()

@app.cmd()
def upgrade_to_dump_truck():
    glacier_backend = GlacierBackend()
    glacier_backend.upgrade_to_dump_truck()

    s3_backend = S3Backend()

    regex_key = re.compile(r"(?P<backup_name>.+)\.(?P<date_component>\d{14})\.tgz(?P<is_enc>\.enc)?")

    # old regex for backward compatibility (for files without dot before the date component).
    old_regex_key = re.compile(r"(?P<backup_name>.+)(?P<date_component>\d{14})\.tgz(?P<is_enc>\.enc)?")
    
    for generator, backend in [(s3_backend, "s3"), (glacier_backend, "glacier")]:
        for key in generator.ls():
            match = regex_key.match(key)
            # Backward compatibility
            if not match:
                match = old_regex_key.match(key)
            if match:
                filename = match.group("backup_name")
                is_enc = bool(match.group("is_enc"))
                backup_date = int(datetime.strptime(match.group("date_component"), "%Y%m%d%H%M%S").strftime("%s"))
            else:
                filename = key
                is_enc = False
                backup_date = 0

            new_backup = dict(backend=backend,
                            is_deleted=0,
                            backup_date=backup_date,
                            tags=[],
                            stored_filename=key,
                            filename=filename,
                            last_updated=int(datetime.utcnow().strftime("%s")),
                            metadata=dict(is_enc=is_enc),
                            size=0)
            try:
                dump_truck_insert_backup(new_backup)
            except:
                pass


def main():
    app.run()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    main()
