# -*- encoding: utf-8 -*-
import yaml
import os
import logging

log = logging.getLogger(__name__)

CONFIG_FILE = os.path.expanduser("~/.bakthat.yml")
DATABASE = os.path.expanduser("~/.bakthat.sqlite")

DEFAULT_LOCATION = "us-east-1"
DEFAULT_DESTINATION = "s3"

# Read default config file
config = {}
if os.path.isfile(CONFIG_FILE):
    log.debug("Try loading default config file: {0}".format(CONFIG_FILE))
    config = yaml.load(open(CONFIG_FILE))
    if config:
        log.debug("Config loaded")
