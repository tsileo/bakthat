# -*- encoding: utf-8 -*-
import tarfile
import tempfile
import os
from datetime import datetime
from getpass import getpass
import logging
import hashlib
import uuid
import socket
import re
import fnmatch
import mimetypes
import calendar
import functools
from contextlib import closing  # for Python2.6 compatibility
from gzip import GzipFile

import yaml
from beefish import decrypt, encrypt_file
import aaargh
import grandfatherson
from byteformat import ByteFormatter

from bakthat.backends import GlacierBackend, S3Backend, RotationConfig, SwiftBackend
from bakthat.conf import config, events, load_config, DEFAULT_DESTINATION, DEFAULT_LOCATION, CONFIG_FILE, EXCLUDE_FILES
from bakthat.utils import _interval_string_to_seconds
from bakthat.models import Backups
from bakthat.sync import BakSyncer, bakmanager_hook, bakmanager_periodic_backups
from bakthat.plugin import setup_plugins, plugin_setup

__version__ = "0.6.0"

app = aaargh.App(description="Compress, encrypt and upload files directly to Amazon S3/Glacier/Swift.")

log = logging.getLogger("bakthat")


class BakthatFilter(logging.Filter):
    def filter(self, rec):
        if rec.name.startswith("bakthat") or rec.name == "root":
            return True
        else:
            return rec.levelno >= logging.WARNING


STORAGE_BACKEND = dict(s3=S3Backend, glacier=GlacierBackend, swift=SwiftBackend)


def _get_store_backend(conf, destination=None, profile="default"):
    if not isinstance(conf, dict):
        conf = load_config(conf)
    conf = conf.get(profile)
    setup_plugins(conf)
    if not destination:
        destination = conf.get("default_destination", DEFAULT_DESTINATION)
    return STORAGE_BACKEND[destination](conf, profile), destination, conf


@app.cmd(help="Delete backups older than the given interval string.")
@app.cmd_arg('filename', type=str, help="Filename to delete")
@app.cmd_arg('interval', type=str, help="Interval string like 1M, 1W, 1M3W4h2s")
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier|swift", default=None)
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
@app.cmd_arg('-c', '--config', type=str, default=CONFIG_FILE, help="path to config file")
def delete_older_than(filename, interval, profile="default", config=CONFIG_FILE, destination=None, **kwargs):
    """Delete backups matching the given filename older than the given interval string.

    :type filename: str
    :param filename: File/directory name.

    :type interval: str
    :param interval: Interval string like 1M, 1W, 1M3W4h2s...
        (s => seconds, m => minutes, h => hours, D => days, W => weeks, M => months, Y => Years).

    :type destination: str
    :param destination: glacier|s3|swift

    :type conf: dict
    :keyword conf: Override/set AWS configuration.

    :rtype: list
    :return: A list containing the deleted keys (S3) or archives (Glacier).

    """
    storage_backend, destination, conf = _get_store_backend(config, destination, profile)

    session_id = str(uuid.uuid4())
    events.before_delete_older_than(session_id)

    interval_seconds = _interval_string_to_seconds(interval)

    deleted = []

    backup_date_filter = int(datetime.utcnow().strftime("%s")) - interval_seconds
    for backup in Backups.search(filename, destination, older_than=backup_date_filter, profile=profile, config=config):
        real_key = backup.stored_filename
        log.info("Deleting {0}".format(real_key))

        storage_backend.delete(real_key)
        backup.set_deleted()
        deleted.append(backup)

    events.on_delete_older_than(session_id, deleted)

    return deleted


@app.cmd(help="Rotate backups using Grandfather-father-son backup rotation scheme.")
@app.cmd_arg('filename', type=str)
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier|swift", default=None)
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
@app.cmd_arg('-c', '--config', type=str, default=CONFIG_FILE, help="path to config file")
def rotate_backups(filename, destination=None, profile="default", config=CONFIG_FILE, **kwargs):
    """Rotate backup using grandfather-father-son rotation scheme.

    :type filename: str
    :param filename: File/directory name.

    :type destination: str
    :param destination: s3|glacier|swift

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
    storage_backend, destination, conf = _get_store_backend(config, destination, profile)
    rotate = RotationConfig(conf, profile)
    if not rotate:
        raise Exception("You must run bakthat configure_backups_rotation or provide rotation configuration.")

    session_id = str(uuid.uuid4())
    events.before_rotate_backups(session_id)

    deleted = []

    backups = Backups.search(filename, destination, profile=profile, config=config)
    backups_date = [datetime.fromtimestamp(float(backup.backup_date)) for backup in backups]

    rotate_kwargs = rotate.conf.copy()
    del rotate_kwargs["first_week_day"]
    for k, v in rotate_kwargs.iteritems():
        rotate_kwargs[k] = int(v)
    rotate_kwargs["firstweekday"] = int(rotate.conf["first_week_day"])
    rotate_kwargs["now"] = datetime.utcnow()

    to_delete = grandfatherson.to_delete(backups_date, **rotate_kwargs)
    for delete_date in to_delete:
        try:
            backup_date = int(delete_date.strftime("%s"))
            backup = Backups.search(filename, destination, backup_date=backup_date, profile=profile, config=config).get()

            if backup:
                real_key = backup.stored_filename
                log.info("Deleting {0}".format(real_key))

                storage_backend.delete(real_key)
                backup.set_deleted()
                deleted.append(backup)
        except Exception, exc:
            log.error("Error when deleting {0}".format(backup))
            log.exception(exc)

    events.on_rotate_backups(session_id, deleted)

    return deleted


def _get_exclude(exclude_file):
    """ Load a .gitignore like file to exclude files/dir from backups.

    :type exclude_file: str
    :param exclude_file: Path to the exclude file

    :rtype: function
    :return: A function ready to inject in tar.add(exlude=_exclude)

    """
    patterns = filter(None, open(exclude_file).read().split("\n"))

    def _exclude(filename):
        for pattern in patterns:
            if re.search(fnmatch.translate(pattern), filename):
                log.debug("{0} excluded".format(filename))
                return True
        return False
    return _exclude


@app.cmd(help="Backup a file or a directory, backup the current directory if no arg is provided.")
@app.cmd_arg('filename', type=str, default=os.getcwd(), nargs="?")
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier|swift", default=None)
@app.cmd_arg('--prompt', type=str, help="yes|no", default="yes")
@app.cmd_arg('-t', '--tags', type=str, help="space separated tags", default="")
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
@app.cmd_arg('-c', '--config', type=str, default=CONFIG_FILE, help="path to config file")
@app.cmd_arg('-k', '--key', type=str, default=None, help="Custom key for periodic backups (works only with BakManager.io hook.)")
@app.cmd_arg('--exclude-file', type=str, default=None)
@app.cmd_arg('--s3-reduced-redundancy', action="store_true")
def backup(filename=os.getcwd(), destination=None, profile="default", config=CONFIG_FILE, prompt="yes", tags=[], key=None, exclude_file=None, s3_reduced_redundancy=False, **kwargs):
    """Perform backup.

    :type filename: str
    :param filename: File/directory to backup.

    :type destination: str
    :param destination: s3|glacier|swift

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

    :type custom_filename: str
    :keyword custom_filename: Override the original filename (only in metadata)

    :rtype: dict
    :return: A dict containing the following keys: stored_filename, size, metadata, backend and filename.

    """
    storage_backend, destination, conf = _get_store_backend(config, destination, profile)
    backup_file_fmt = "{0}.{1}.tgz"

    session_id = str(uuid.uuid4())
    events.before_backup(session_id)

    # Check if compression is disabled on the configuration.
    if conf:
        compress = conf.get("compress", True)
    else:
        compress = config.get(profile).get("compress", True)

    if not compress:
        backup_file_fmt = "{0}.{1}"

    log.info("Backing up " + filename)

    if exclude_file and os.path.isfile(exclude_file):
        EXCLUDE_FILES.insert(0, exclude_file)

    _exclude = lambda filename: False
    if os.path.isdir(filename):
        join = functools.partial(os.path.join, filename)
        for efile in EXCLUDE_FILES:
            efile = join(efile)
            if os.path.isfile(efile):
                _exclude = _get_exclude(efile)
                log.info("Using {0} to exclude files.".format(efile))

    arcname = filename.strip('/').split('/')[-1]
    now = datetime.utcnow()
    date_component = now.strftime("%Y%m%d%H%M%S")
    stored_filename = backup_file_fmt.format(arcname, date_component)

    backup_date = int(now.strftime("%s"))
    backup_data = dict(filename=kwargs.get("custom_filename", arcname),
                       backup_date=backup_date,
                       last_updated=backup_date,
                       backend=destination,
                       is_deleted=False)

    # Useful only when using bakmanager.io hook
    backup_key = key

    password = kwargs.get("password", os.environ.get("BAKTHAT_PASSWORD"))
    if password is None and prompt.lower() != "no":
        password = getpass("Password (blank to disable encryption): ")
        if password:
            password2 = getpass("Password confirmation: ")
            if password != password2:
                log.error("Password confirmation doesn't match")
                return

    if not compress:
        log.info("Compression disabled")
        outname = filename
        with open(outname) as outfile:
            backup_data["size"] = os.fstat(outfile.fileno()).st_size
        bakthat_compression = False

    # Check if the file is not already compressed
    elif mimetypes.guess_type(arcname) == ('application/x-tar', 'gzip'):
        log.info("File already compressed")
        outname = filename

        # removing extension to reformat filename
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
                tar.add(filename, arcname=arcname, exclude=_exclude)
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
    if isinstance(tags, list):
        tags = " ".join(tags)

    backup_data["tags"] = tags

    backup_data["metadata"] = dict(is_enc=bakthat_encryption,
                                   client=socket.gethostname())
    backup_data["stored_filename"] = stored_filename

    access_key = storage_backend.conf.get("access_key")
    container_key = storage_backend.conf.get(storage_backend.container_key)
    backup_data["backend_hash"] = hashlib.sha512(access_key + container_key).hexdigest()

    log.info("Uploading...")
    storage_backend.upload(stored_filename, outname, s3_reduced_redundancy=s3_reduced_redundancy)

    # We only remove the file if the archive is created by bakthat
    if bakthat_compression or bakthat_encryption:
        os.remove(outname)

    log.debug(backup_data)

    # Insert backup metadata in SQLite
    backup = Backups.create(**backup_data)

    BakSyncer(conf).sync_auto()

    # bakmanager.io hook, enable with -k/--key paramter
    if backup_key:
        bakmanager_hook(conf, backup_data, backup_key)

    events.on_backup(session_id, backup)

    return backup


@app.cmd(help="Show backups list.")
@app.cmd_arg('query', type=str, default="", help="search filename for query", nargs="?")
@app.cmd_arg('-d', '--destination', type=str, default="", help="glacier|s3|swift, show every destination by default")
@app.cmd_arg('-t', '--tags', type=str, default="", help="tags space separated")
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (all profiles are displayed by default)")
@app.cmd_arg('-c', '--config', type=str, default=CONFIG_FILE, help="path to config file")
def show(query="", destination="", tags="", profile="default", config=CONFIG_FILE):
    backups = Backups.search(query, destination, profile=profile, tags=tags, config=config)
    _display_backups(backups)


def _display_backups(backups):
    bytefmt = ByteFormatter()
    for backup in backups:
        backup = backup._data
        backup["backup_date"] = datetime.fromtimestamp(float(backup["backup_date"])).isoformat()
        backup["size"] = bytefmt(backup["size"])
        if backup.get("tags"):
            backup["tags"] = "({0})".format(backup["tags"])

        log.info("{backup_date}\t{backend:8}\t{size:8}\t{stored_filename} {tags}".format(**backup))


@app.cmd(help="Set AWS S3/Glacier credentials.")
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
def configure(profile="default"):
    try:
        new_conf = config.copy()
        new_conf[profile] = config.get(profile, {})

        new_conf[profile]["access_key"] = raw_input("AWS Access Key: ")
        new_conf[profile]["secret_key"] = raw_input("AWS Secret Key: ")
        new_conf[profile]["s3_bucket"] = raw_input("S3 Bucket Name: ")
        new_conf[profile]["glacier_vault"] = raw_input("Glacier Vault Name: ")

        while 1:
            default_destination = raw_input("Default destination ({0}): ".format(DEFAULT_DESTINATION))
            if default_destination:
                default_destination = default_destination.lower()
                if default_destination in ("s3", "glacier", "swift"):
                    break
                else:
                    log.error("Invalid default_destination, should be s3 or glacier, swift, try again.")
            else:
                default_destination = DEFAULT_DESTINATION
                break

        new_conf[profile]["default_destination"] = default_destination
        region_name = raw_input("Region Name ({0}): ".format(DEFAULT_LOCATION))
        if not region_name:
            region_name = DEFAULT_LOCATION
        new_conf[profile]["region_name"] = region_name

        if default_destination in ("swift"):
            new_conf[profile]["auth_version"] = raw_input("Swift Auth Version: ")
            new_conf[profile]["auth_url"] = raw_input("Swift Auth URL: ")

        yaml.dump(new_conf, open(CONFIG_FILE, "w"), default_flow_style=False)

        log.info("Config written in %s" % CONFIG_FILE)
        log.info("Run bakthat configure_backups_rotation if needed.")
    except KeyboardInterrupt:
        log.error("Cancelled by user")


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
@app.cmd_arg('filename', type=str)
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier|swift", default=None)
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
@app.cmd_arg('-c', '--config', type=str, default=CONFIG_FILE, help="path to config file")
def restore(filename, destination=None, profile="default", config=CONFIG_FILE, **kwargs):
    """Restore backup in the current working directory.

    :type filename: str
    :param filename: File/directory to backup.

    :type destination: str
    :param destination: s3|glacier|swift

    :type profile: str
    :param profile: Profile name (default by default).

    :type conf: dict
    :keyword conf: Override/set AWS configuration.

    :rtype: bool
    :return: True if successful.
    """
    storage_backend, destination, conf = _get_store_backend(config, destination, profile)

    if not filename:
        log.error("No file to restore, use -f to specify one.")
        return

    backup = Backups.match_filename(filename, destination, profile=profile, config=config)

    if not backup:
        log.error("No file matched.")
        return

    session_id = str(uuid.uuid4())
    events.before_restore(session_id)

    key_name = backup.stored_filename
    log.info("Restoring " + key_name)

    # Asking password before actually download to avoid waiting
    if key_name and backup.is_encrypted():
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

    if out and backup.is_encrypted():
        log.info("Decrypting...")
        decrypted_out = tempfile.TemporaryFile()
        decrypt(out, decrypted_out, password)
        out = decrypted_out

    if out and (key_name.endswith(".tgz") or key_name.endswith(".tgz.enc")):
        log.info("Uncompressing...")
        out.seek(0)
        if not backup.metadata.get("KeyValue"):
            tar = tarfile.open(fileobj=out)
            tar.extractall()
            tar.close()
        else:
            with closing(GzipFile(fileobj=out, mode="r")) as f:
                with open(backup.stored_filename, "w") as out:
                    out.write(f.read())
    elif out:
        log.info("Backup is not compressed")
        with open(backup.filename, "w") as restored:
            out.seek(0)
            restored.write(out.read())

    events.on_restore(session_id, backup)

    return backup


@app.cmd(help="Delete a backup.")
@app.cmd_arg('filename', type=str)
@app.cmd_arg('-d', '--destination', type=str, help="s3|glacier|swift", default=None)
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
@app.cmd_arg('-c', '--config', type=str, default=CONFIG_FILE, help="path to config file")
def delete(filename, destination=None, profile="default", config=CONFIG_FILE, **kwargs):
    """Delete a backup.

    :type filename: str
    :param filename: stored filename to delete.

    :type destination: str
    :param destination: glacier|s3|swift

    :type profile: str
    :param profile: Profile name (default by default).

    :type conf: dict
    :keyword conf: A dict with a custom configuration.

    :type conf: dict
    :keyword conf: Override/set AWS configuration.

    :rtype: bool
    :return: True if the file is deleted.

    """
    if not filename:
        log.error("No file to delete, use -f to specify one.")
        return

    backup = Backups.match_filename(filename, destination, profile=profile, config=config)

    if not backup:
        log.error("No file matched.")
        return

    key_name = backup.stored_filename

    storage_backend, destination, conf = _get_store_backend(config, destination, profile)

    session_id = str(uuid.uuid4())
    events.before_delete(session_id)

    log.info("Deleting {0}".format(key_name))

    storage_backend.delete(key_name)
    backup.set_deleted()

    events.on_delete(session_id, backup)

    return backup


@app.cmd(help="Periodic backups status (bakmanager.io API)")
@app.cmd_arg('-p', '--profile', type=str, default="default", help="profile name (default by default)")
@app.cmd_arg('-c', '--config', type=str, default=CONFIG_FILE, help="path to config file")
def periodic_backups(config=CONFIG_FILE, profile="default"):
    conf = load_config(config).get(profile)
    bakmanager_periodic_backups(conf)


@app.cmd(help="Trigger synchronization")
def sync(**kwargs):
    """Trigger synchronization."""
    conf = kwargs.get("conf")
    BakSyncer(conf).sync()


@app.cmd(help="Reset synchronization")
def reset_sync(**kwargs):
    """Reset synchronization."""
    conf = kwargs.get("conf")
    BakSyncer(conf).reset_sync()


def main():

    if not log.handlers:
    #    logging.basicConfig(level=logging.INFO, format='%(message)s')
        handler = logging.StreamHandler()
        handler.addFilter(BakthatFilter())
        handler.setFormatter(logging.Formatter('%(message)s'))
        log.addHandler(handler)
        log.setLevel(logging.INFO)

    app.run()


if __name__ == '__main__':
    main()
