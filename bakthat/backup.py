# -*- coding: utf-8 -*-
from contextlib import closing  # for Python2.6 compatibility
import tarfile
import tempfile
import functools
from datetime import datetime
import os
import logging

from dirtools import Dir, File
from incremental_backups_tools.diff import DirIndex, DiffIndex, DiffData
from incremental_backups_tools import tarvolume
import simplejson as json
from bakthat.cache import cache, generate_filename as _generate_filename, get_ts
import seccure


def generate_filename(filename):
    return get_cache_path(_generate_filename(filename))


class IncrementalBackup(object):
    b_files = []
    b_key = None

    def __init__(self, path):
        self._dir = Dir(path)
        self._dir_index = DirIndex(self._dir)
        self.b_key = self._dir.directory

    def create(self):
        dt = datetime.utcnow()
        ts = get_ts(dt)

        latest_dir_index = cache.get_latest('{0}_dir_index'.format(self.b_key))
        if not latest_dir_index:
            raise Exception('Latest DirIndex not found.')

        dir_index = self._dir_index.data()
        diff_index = DiffIndex(dir_index, latest_dir_index).compute()

        if latest_dir_index['hashdir'] == diff_index['hashdir']:
            print "NO MODIF"
            return
        cache.create('{0}_dir_index'.format(self.b_key), dir_index, dt=dt)

        volumes, volume_index = DiffData(diff_index).create_archive('{0}.diff.{1}'.format(self.b_key, ts))

        cache.create('{0}_diff_index'.format(self.b_key), diff_index, dt=dt)
        cache.create('{0}_volume_index'.format(self.b_key), volume_index, dt=dt)
        self.b_files = volumes


class FullBackup(object):
    b_files = []
    b_key = None

    def __init__(self, path):
        self._dir = Dir(path)
        self.b_key = self._dir.directory

    def create(self):
        dt = datetime.utcnow()
        ts = get_ts(dt)

        tar = tarvolume.open('/tmp', '{0}.full.{1}'.format(self.b_key, ts), mode='w')
        volumes, volume_index = tar.addDir(self._dir)
        cache.create('{0}_volume_index'.format(self.b_key), volume_index, dt=dt)
        self.b_files = volumes
        tar.close()

        cache.create('{0}_dir_index'.format(self.b_key), DirIndex(self._dir).data(), dt=dt)


def make_full_backup(path):
    backup_dir = Dir(path)
    archive_path = backup_dir.compress_to()
    index_file = generate_filename(backup_dir.directory + '_index')
    DirIndex(backup_dir).to_file(index_file)
    # TODO => sha256 archive_path ?
    print index_file
    return archive_path

#backup = FullBackup('/work/writing')
backup = IncrementalBackup('/work/writing')
print backup.create()
print backup.b_files

# print generate_filename('omg')
# TODO trouver un moyen clean de gerer la demande de passphrase
# TODO trouver un moyen de gerer les deux passphrases:
#        - celle pour signer
#        - celel pour chiffrer
# TODO trouver un moyen de generer des clées super secure et expliquer comment la backuper
# voir Diffie Helman exchange avec seccure cli pour sync ?
# TODO brancher l'entropykey
# MAYBE dirtools-seccure ???? avec signature et verify pour file
# et encrypt_to / decrypt_to avec exclusion
# possibilité de set le content dans le __init__ du file ?
