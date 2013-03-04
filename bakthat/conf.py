# -*- encoding: utf-8 -*-
import yaml
import os
from dumptruck import DumpTruck
import math
import logging

log = logging.getLogger(__name__)

CONFIG_FILE = os.path.expanduser("~/.bakthat.yml")

DEFAULT_LOCATION = "us-east-1"
DEFAULT_DESTINATION = "s3"

# Read default config file
config = {}
if os.path.isfile(CONFIG_FILE):
    log.debug("Try loading default config file: {0}".format(CONFIG_FILE))
    config = yaml.load(open(CONFIG_FILE))
    if config:
        log.debug("Config loaded")

# DumpTruck initialization
dump_truck = DumpTruck(dbname=os.path.expanduser("~/.bakthat.dt"), vars_table="config")

if not "backups" in dump_truck.tables():
    # We initialize DumpTruck, with dummy data that won't be inserted.
    dump_truck.create_table({'stored_filename': 'filename.20130227205616.tgz', 
                    'size': 1,
                    'metadata': {'is_enc': False},
                    'backup_date': 1361994976,
                    'filename': 'filename',
                    'backend': 's3',
                    'is_deleted': False,
                    'last_updated': 1361994976,
                    'tags': []}, "backups")
    dump_truck.create_index(["stored_filename"], "backups", unique=True)

if not "inventory" in dump_truck.tables():
    dump_truck.create_table({"filename": "filename", "archive_id": "glacier-archive-id"}, "inventory")
    dump_truck.create_index(["filename"], "inventory", unique=True)

if not "jobs" in dump_truck.tables():
    dump_truck.create_table({"filename": "filename", "job_id": "job_id"}, "jobs")
    dump_truck.create_index(["filename"], "jobs", unique=True)

if not "config" in dump_truck.tables():
    dump_truck.save_var("client_id", "")
    dump_truck.save_var("sync_ts", 0)
    dump_truck.save_var("tags", set())