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
        self.__dict__['data'] = data

    def init_from_file(self, name=None, fileobj=None):
        if not fileobj:
            fileobj = open(name, 'rb')
        self.__dict__['data'] = yaml.load(fileobj)

    def __getattr__(self, attr):
        if not self.data:
            raise AttributeError('Config is not initialized yet.')
        return self.__dict__['data'].get(attr)

    def __getitem__(self, val):
        """ To allow dict like access e.g. conf['key'] """
        return self.__getattr__(val)

    def __setattr__(self, attr, value):
        if attr != 'data':
            raise AttributeError('Cannot set attribute on Config.')
