# -*- encoding: utf-8 -*-
import ConfigParser
import os

DEFAULT_LOCATION = "us-east-1"
DEFAULT_DESTINATION = "s3"

config = ConfigParser.SafeConfigParser()
config.read(os.path.expanduser("~/.bakthat.conf"))
