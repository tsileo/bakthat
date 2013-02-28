# -*- encoding: utf-8 -*-
import logging

import bakthat
from bakthat.conf import config, dump_truck, DEFAULT_DESTINATION, DEFAULT_LOCATION

log = logging.getLogger(__name__)

def dump_truck_delete_backup(stored_filename):
    """Change status of is_deleted to 1 for the given stored_filename.

    :type stored_filename: str
    :param stored_filename: Filename

    """
    dump_truck.execute("UPDATE backups SET is_deleted = 1 WHERE stored_filename == '{0}'".format(stored_filename))
