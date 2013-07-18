# -*- coding: utf-8 -*-
import logging
import unittest
import time

from bakthat.config import Config

log = logging.getLogger()

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
log_fmtr = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(log_fmtr)

log.addHandler(handler)
log.setLevel(logging.DEBUG)


class BakthatConfigTestCase(unittest.TestCase):
    def setUp(self):
        self.conf = Config()

    def tearDown(self):
        pass

    def test_init_from_dict(self):
        self.conf.init({'key': 'test_key'})
        self.assertEqual(self.conf.key, 'test_key')
        self.assertEqual(self.conf['key'], 'test_key')

    def test_uninitialized_config(self):
        with self.assertRaises(AttributeError):
            self.conf.key

    def test_init_from_filename(self):
        test_file = '/tmp/test_conf'
        with open(test_file, 'wb') as f:
            f.write('key: test_key')
        self.conf.init_from_file(test_file)
        self.assertEqual(self.conf.key, 'test_key')

    def test_init_from_fileobj(self):
        test_file = '/tmp/test_conf'
        with open(test_file, 'wb') as f:
            f.write('key: test_key')
        with open(test_file, 'rb') as f:
            self.conf.init_from_file(fileobj=f)
        self.assertEqual(self.conf.key, 'test_key')
