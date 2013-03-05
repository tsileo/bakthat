# -*- encoding: utf-8 -*-
import logging
import json
import tempfile
import sh
import os
import shutil

import bakthat
from bakthat.conf import config, DEFAULT_DESTINATION, DEFAULT_LOCATION

log = logging.getLogger(__name__)


class BakHelper:
    """Context manager that makes building scripts with bakthat better faster stronger.
    
    :type dir_prefix: str
    :param dir_prefix: Prefix for the created temporary directory.

    :type destination: str
    :keyword destination: Destination (glacier|s3)
    
    :type password: str
    :keyword password: Password (Empty string to disable encryption, disabled by default)

    :type profile: str
    :keyword profile: Profile name

    :type tags: list
    :param tags: List of tags
    """
    def __init__(self, dir_prefix, **kwargs):
        self.dir_prefix = "{0}_".format(dir_prefix)
        self.destination = kwargs.get("destination", DEFAULT_DESTINATION)
        self.password = kwargs.get("password", "")
        self.profile = kwargs.get("profile", "default")
        self.tags = kwargs.get("tags", [])
        self.syncer = None

    def __enter__(self):
        """Save the old current working directory,
            create a temporary directory,
            and make it the new current working directory.
        """
        self.old_cwd = os.getcwd()
        self.tmpd = tempfile.mkdtemp(prefix=self.dir_prefix)
        sh.cd(self.tmpd)
        log.debug("New current working directory: {0}.".format(self.tmpd))
        return self

    def __exit__(self, type, value, traceback):
        """Reseting the current working directory,
            and run synchronization if enabled.
        """
        sh.cd(self.old_cwd)
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

        :rtype: dict
        :return: A dict containing the following keys: stored_filename, size, metadata and filename.
        """
        if filename is None:
            filename = self.tmpd

        return bakthat.backup(filename,
                                destination=kwargs.get("destination", self.destination),
                                password=kwargs.get("password", self.password),
                                tags=kwargs.get("tags", self.tags),
                                profile=kwargs.get("profile", self.profile))

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

        :rtype: bool
        :return: True if successful.
        """
        return bakthat.restore(filename,
                                destination=kwargs.get("destination", self.destination),
                                password=kwargs.get("password", self.password),
                                profile=kwargs.get("profile", self.profile))

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

        :rtype: list
        :return: A list containing the deleted keys (S3) or archives (Glacier).
        """
        if filename is None:
            filename = self.tmpd

        return bakthat.delete_older_than(filename, interval,
                                        destination=kwargs.get("destination", self.destination),
                                        profile=kwargs.get("profile", self.profile))

    def rotate(self, filename=None, **kwargs):
        """Rotate backup using grandfather-father-son rotation scheme.

        :type filename: str
        :param filename: File/directory name.

        :type destination: str
        :keyword destination: Override already set destination.
             
        :type profile: str
        :keyword profile: Profile name

        :rtype: list
        :return: A list containing the deleted keys (S3) or archives (Glacier).
        """
        if filename is None:
            filename = self.tmpd

        return bakthat.rotate_backups(filename,
                                        destination=kwargs.pop("destination", self.destination),
                                        profile=kwargs.get("profile", self.profile))
