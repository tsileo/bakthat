# -*- encoding: utf-8 -*-
import yaml
import os
import logging

from events import Events

log = logging.getLogger(__name__)

CONFIG_FILE = os.path.expanduser("~/.bakthat.yml")
PLUGINS_DIR = os.path.expanduser("~/.bakthat_plugins")
DATABASE = os.path.expanduser("~/.bakthat.sqlite")

DEFAULT_LOCATION = "us-east-1"
DEFAULT_DESTINATION = "s3"

EXCLUDE_FILES = [".bakthatexclude", ".gitignore"]


def load_config(config_file=CONFIG_FILE):
    """ Try to load a yaml config file. """
    config = {}
    if os.path.isfile(config_file):
        log.debug("Try loading config file: {0}".format(config_file))
        config = yaml.load(open(config_file))
        if config:
            log.debug("Config loaded")
    return config

# Read default config file
config = load_config()
events = Events()
