# -*- coding: utf-8 -*-
import yaml


class Config(object):
    """ Hybrid (dict/YAML stream) config handler.

    Start uninitialized, as we don't know yet how
    the configuration will be provided.

    TODO: find a way to handle default config.

    """
    def __init__(self, data=None):
        self.init(data)

    def init(self, data={}):
        """ Initialize the config with a dict. """
        self.data = data

    def init_from_file(self, name=None, fileobj=None):
        if not fileobj:
            fileobj = open(name, 'rb')
        self.data = yaml.load(fileobj)

    def __getattr__(self, attr):
        if not self.data:
            raise AttributeError('Config is not initialized yet.')
        return self.data.get(attr)

    def __setattr__(self, attr, value):
        raise AttributeError('Cannot set attribute on Config.')
