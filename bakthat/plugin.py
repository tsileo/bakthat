# -*- coding: utf-8 -*-
import importlib
import os
import sys
import logging
import atexit

from bakthat.conf import PLUGINS_DIR, events

log = logging.getLogger(__name__)
plugin_setup = False


def setup_plugins(conf=None):
    """ Add the plugin dir to the PYTHON_PATH,
    and activate them."""
    global plugin_setup
    if not plugin_setup:
        log.debug("Setting up plugins")
        plugins_dir = conf.get("plugins_dir", PLUGINS_DIR)

        if os.path.isdir(plugins_dir):
            log.debug("Adding {0} to plugins dir".format(plugins_dir))
            sys.path.append(plugins_dir)

        for plugin in conf.get("plugins", []):
            p = load_class(plugin)
            if issubclass(p, Plugin):
                load_plugin(p, conf)
            else:
                raise Exception("Plugin must be a bakthat.plugin.Plugin subclass!")
        plugin_setup = True


def load_class(full_class_string):
    """ Dynamically load a class from a string. """
    class_data = full_class_string.split(".")
    module_path = ".".join(class_data[:-1])
    class_str = class_data[-1]

    module = importlib.import_module(module_path)
    return getattr(module, class_str)


def load_plugin(plugin, conf):
    p = plugin(conf)
    log.debug("Activating {0}".format(p))
    p.activate()

    def deactivate_plugin():
        try:
            p.deactivate()
        except NotImplementedError:
            pass
    atexit.register(deactivate_plugin)


class Plugin(object):
    """ Abstract plugin class.
    Plugin should implement activate, and optionnaly deactivate.
    """
    def __init__(self, conf):
        self.conf = conf
        self.events = events
        self.log = log

    def __getattr__(self, attr):
        if attr in ["before_backup",
                    "on_backup",
                    "before_restore",
                    "on_restore",
                    "before_delete",
                    "on_delete",
                    "before_delete_older_than",
                    "on_delete_older_than",
                    "before_rotate_backups",
                    "on_rotate_backups"]:
            return getattr(self.events, attr)
        else:
            raise Exception("Event {0} does not exist!".format(attr))

    def __repr__(self):
        return "<Plugin bakthat: {0}>".format(self.__class__.__name__)

    def __str__(self):
        return self.__repr__()

    def activate(self):
        raise NotImplementedError("Plugin should implement this!")

    def deactivate(self):
        raise NotImplementedError("Plugin may implement this!")
