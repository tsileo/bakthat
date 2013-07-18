# -*- coding: utf-8 -*-
import os
import functools
from dirtools import Dir
import re
from datetime import datetime
import simplejson as json
import logging

FILENAME_DATE_FMT = '%Y-%m-%dT%H:%M:%S'
CACHE_PATH = os.path.expanduser('~/.cache/bakthat/')

log = logging.getLogger(__name__)


def get_ts(dt):
    if dt is None:
        dt = datetime.utcnow()
    return dt.strftime(FILENAME_DATE_FMT)


def generate_filename(filename, dt=None, ext="json"):
    """ Helper for generating filename for dump,

    >>> generate_filename('mydir_index')
    mydir_index.2013-07-03-22-20-58.json

    """
    ts = get_ts(dt)
    return '{0}.{1}.{2}'.format(filename, ts, ext)


def sort_filename(filename):
    date_str = re.search(r"\d+-\d+-\d+T\d+:\d+:\d+", filename)
    if date_str:
        dt = datetime.strptime(date_str.group(), FILENAME_DATE_FMT)
        return int(dt.strftime('%s'))
    return 0


class Cache(Dir):
    """ Dir wrapper with additional methods for loading/dumping json. """
    def __init__(self, directory):
        self._init_cache(directory)
        return super(Cache, self).__init__(directory)

    def _init_cache(self, cache_path):
        if not os.path.exists(cache_path):
            os.makedirs(cache_path)
        return functools.partial(os.path.join, cache_path)

    def get_latest(self, key):
        res = self.files(key + '*', sort_key=sort_filename, sort_reverse=True)
        if res:
            with open(os.path.join(self.path, res[0])) as f:
                return json.loads(f.read())

    def create(self, key, data, dt=None):
        file_path = os.path.join(self.path, generate_filename(key, dt))
        with open(file_path, 'w') as f:
            f.write(json.dumps(data))
