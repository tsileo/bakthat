# -*- encoding: utf-8 -*-
import logging
import tempfile
import sh
import os
import shutil
import time
import hashlib
import json
from StringIO import StringIO
from gzip import GzipFile

from beefish import encrypt, decrypt
from boto.s3.key import Key

import bakthat
from bakthat.conf import DEFAULT_DESTINATION
from bakthat.backends import S3Backend
from bakthat.models import Backups

log = logging.getLogger(__name__)


class KeyValue(S3Backend):
    """A Key Value store to store/retrieve object/string on S3.

    Data is gzipped and json encoded before uploading,
    compression can be disabled.
    """
    def __init__(self, conf={}, profile="default"):
        S3Backend.__init__(self, conf, profile)
        self.profile = profile

    def set_key(self, keyname, value, **kwargs):
        """Store a string as keyname in S3.

        :type keyname: str
        :param keyname: Key name

        :type value: str
        :param value: Value to save, will be json encoded.

        :type value: bool
        :keyword compress: Compress content with gzip,
            True by default
        """
        k = Key(self.bucket)
        k.key = keyname

        backup_date = int(time.time())
        backup = dict(filename=keyname,
                      stored_filename=keyname,
                      backup_date=backup_date,
                      last_updated=backup_date,
                      backend="s3",
                      is_deleted=False,
                      tags="",
                      metadata={"KeyValue": True,
                                "is_enc": False,
                                "is_gzipped": False})

        fileobj = StringIO(json.dumps(value))

        if kwargs.get("compress", True):
            backup["metadata"]["is_gzipped"] = True
            out = StringIO()
            f = GzipFile(fileobj=out, mode="w")
            f.write(fileobj.getvalue())
            f.close()
            fileobj = StringIO(out.getvalue())

        password = kwargs.get("password")
        if password:
            backup["metadata"]["is_enc"] = True
            out = StringIO()
            encrypt(fileobj, out, password)
            fileobj = out
        # Creating the object on S3
        k.set_contents_from_string(fileobj.getvalue())
        k.set_acl("private")
        backup["size"] = k.size

        access_key = self.conf.get("access_key")
        container_key = self.conf.get(self.container_key)
        backup["backend_hash"] = hashlib.sha512(access_key + container_key).hexdigest()
        Backups.upsert(**backup)

    def get_key(self, keyname, **kwargs):
        """Return the object stored under keyname.

        :type keyname: str
        :param keyname: Key name

        :type default: str
        :keyword default: Default value if key name does not exist, None by default

        :rtype: str
        :return: The key content as string, or default value.
        """
        k = Key(self.bucket)
        k.key = keyname
        if k.exists():
            backup = Backups.get(Backups.stored_filename % keyname, Backups.backend == "s3")
            fileobj = StringIO(k.get_contents_as_string())

            if backup.is_encrypted():
                out = StringIO()
                decrypt(fileobj, out, kwargs.get("password"))
                fileobj = out
                fileobj.seek(0)

            if backup.is_gzipped():
                f = GzipFile(fileobj=fileobj, mode="r")
                out = f.read()
                f.close()
                fileobj = StringIO(out)
            return json.loads(fileobj.getvalue())
        return kwargs.get("default")

    def delete_key(self, keyname):
        """Delete the given key.

        :type keyname: str
        :param keyname: Key name
        """
        k = Key(self.bucket)
        k.key = keyname
        if k.exists():
            k.delete()
        backup = Backups.match_filename(keyname, "s3", profile=self.profile)
        if backup:
            backup.set_deleted()
            return True

    def get_key_url(self, keyname, expires_in, method="GET"):
        """Generate a URL for the keyname object.

        Be careful, the response is JSON encoded.

        :type keyname: str
        :param keyname: Key name

        :type expires_in: int
        :param expires_in: Number of the second before the expiration of the link

        :type method: str
        :param method: HTTP method for access

        :rtype str:
        :return: The URL to download the content of the given keyname
        """
        k = Key(self.bucket)
        k.key = keyname
        if k.exists:
            return k.generate_url(expires_in, method)


class BakHelper:
    """Helper that makes building scripts with bakthat better faster stronger.

    Designed to be used as a context manager.

    :type backup_name: str
    :param backup_name: Backup name
        also the prefix for the created temporary directory.

    :type destination: str
    :keyword destination: Destination (glacier|s3)

    :type password: str
    :keyword password: Password (Empty string to disable encryption, disabled by default)

    :type profile: str
    :keyword profile: Profile name, only valid if no custom conf is provided

    :type conf: dict
    :keyword conf: Override profiles configuration

    :type tags: list
    :param tags: List of tags
    """
    def __init__(self, backup_name, **kwargs):
        self.backup_name = backup_name
        self.dir_prefix = "{0}_".format(backup_name)
        self.destination = kwargs.get("destination", DEFAULT_DESTINATION)
        self.password = kwargs.get("password", "")
        self.profile = kwargs.get("profile", "default")
        self.conf = kwargs.get("conf", {})
        self.tags = kwargs.get("tags", [])
        # Key for bakmanager.io hook
        self.key = kwargs.get("key", None)
        self.syncer = None

    def __enter__(self):
        """Save the old current working directory,
            create a temporary directory,
            and make it the new current working directory.
        """
        self.old_cwd = os.getcwd()
        self.tmpd = tempfile.mkdtemp(prefix=self.dir_prefix)
        sh.cd(self.tmpd)
        log.info("New current working directory: {0}.".format(self.tmpd))
        return self

    def __exit__(self, type, value, traceback):
        """Reseting the current working directory,
            and run synchronization if enabled.
        """
        sh.cd(self.old_cwd)
        log.info("Back to {0}".format(self.old_cwd))
        shutil.rmtree(self.tmpd)
        if self.syncer:
            log.debug("auto sync")
            self.sync()

    def sync(self):
        """Shortcut for calling BakSyncer."""
        if self.syncer:
            try:
                return self.syncer.sync()
            except Exception, exc:
                log.exception(exc)

    def enable_sync(self, api_url, auth=None):
        """Enable synchronization with :class:`bakthat.sync.BakSyncer` (optional).

        :type api_url: str
        :param api_url: Base API URL.

        :type auth: tuple
        :param auth: Optional, tuple/list (username, password) for API authentication.
        """
        log.debug("Enabling BakSyncer to {0}".format(api_url))
        from bakthat.sync import BakSyncer
        self.syncer = BakSyncer(api_url, auth)

    def backup(self, filename=None, **kwargs):
        """Perform backup.

        :type filename: str
        :param filename: File/directory to backup.

        :type password: str
        :keyword password: Override already set password.

        :type destination: str
        :keyword destination: Override already set destination.

        :type tags: list
        :keyword tags: Tags list

        :type profile: str
        :keyword profile: Profile name

        :type conf: dict
        :keyword conf: Override profiles configuration

        :rtype: dict
        :return: A dict containing the following keys: stored_filename, size, metadata and filename.
        """
        if filename is None:
            filename = self.tmpd

        return bakthat.backup(filename,
                              destination=kwargs.get("destination", self.destination),
                              password=kwargs.get("password", self.password),
                              tags=kwargs.get("tags", self.tags),
                              profile=kwargs.get("profile", self.profile),
                              conf=kwargs.get("conf", self.conf),
                              key=kwargs.get("key", self.key),
                              custom_filename=self.backup_name)

    def restore(self, filename, **kwargs):
        """Restore backup in the current working directory.

        :type filename: str
        :param filename: File/directory to backup.

        :type password: str
        :keyword password: Override already set password.

        :type destination: str
        :keyword destination: Override already set destination.

        :type profile: str
        :keyword profile: Profile name

        :type conf: dict
        :keyword conf: Override profiles configuration

        :rtype: bool
        :return: True if successful.
        """
        return bakthat.restore(filename,
                               destination=kwargs.get("destination", self.destination),
                               password=kwargs.get("password", self.password),
                               profile=kwargs.get("profile", self.profile),
                               conf=kwargs.get("conf", self.conf))

    def delete_older_than(self, filename=None, interval=None, **kwargs):
        """Delete backups older than the given interval string.

        :type filename: str
        :param filename: File/directory name.

        :type interval: str
        :param interval: Interval string like 1M, 1W, 1M3W4h2s...
            (s => seconds, m => minutes, h => hours, D => days, W => weeks, M => months, Y => Years).

        :type destination: str
        :keyword destination: Override already set destination.

        :type profile: str
        :keyword profile: Profile name

        :type conf: dict
        :keyword conf: Override profiles configuration

        :rtype: list
        :return: A list containing the deleted keys (S3) or archives (Glacier).
        """
        if filename is None:
            filename = self.tmpd

        return bakthat.delete_older_than(filename, interval,
                                         destination=kwargs.get("destination", self.destination),
                                         profile=kwargs.get("profile", self.profile),
                                         conf=kwargs.get("conf", self.conf))

    def rotate(self, filename=None, **kwargs):
        """Rotate backup using grandfather-father-son rotation scheme.

        :type filename: str
        :param filename: File/directory name.

        :type destination: str
        :keyword destination: Override already set destination.

        :type profile: str
        :keyword profile: Profile name

        :type conf: dict
        :keyword conf: Override profiles configuration

        :rtype: list
        :return: A list containing the deleted keys (S3) or archives (Glacier).
        """
        if filename is None:
            filename = self.backup_name

        return bakthat.rotate_backups(filename,
                                      destination=kwargs.pop("destination", self.destination),
                                      profile=kwargs.get("profile", self.profile),
                                      conf=kwargs.get("conf", self.conf))
