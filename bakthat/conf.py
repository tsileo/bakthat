# -*- encoding: utf-8 -*-
import ConfigParser
import os
from dumptruck import DumpTruck

DEFAULT_LOCATION = "us-east-1"
DEFAULT_DESTINATION = "s3"

config = ConfigParser.SafeConfigParser()
config.read(os.path.expanduser("~/.bakthat.conf"))

dump_truck = DumpTruck(dbname=os.path.expanduser("~/.bakthat.dt"))

if not "backups" in dump_truck.tables():
    # We initialize DumpTruck, with dummy data that won't be inserted.
    dump_truck.create_table({'stored_filename': 'filename.20130227205616.tgz', 
                    'size': 1,
                    'metadata': {'is_enc': False},
                    'backup_date': 1361994976,
                    'filename': 'filename',
                    'backend': 's3',
                    'is_deleted': False}, "backups")
    dump_truck.create_index(["stored_filename"], "backups", unique=True)
