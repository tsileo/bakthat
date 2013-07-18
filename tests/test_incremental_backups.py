# -*- coding: utf-8 -*-
import logging
import unittest

log = logging.getLogger()

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
log_fmtr = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(log_fmtr)

log.addHandler(handler)
log.setLevel(logging.DEBUG)


class BakthatTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass
