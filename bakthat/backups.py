# -*- coding: utf-8 -*-
from contextlib import closing  # for Python2.6 compatibility
import tarfile
import tempfile

from dirtools import Dir, File
from incremental_backups_tools import DirIndex, DiffIndex, DiffData

import seccure

CURVE = 'secp256r1/nistp256'
PASSPHRASE = 'omg'
PUBKEY = str(seccure.passphrase_to_pubkey(PASSPHRASE, CURVE))

curve = seccure.Curve.by_name(CURVE)
privkey = curve.passphrase_to_privkey(PASSPHRASE)
# TODO trouver un moyen clean de gerer la demande de passphrase
# TODO trouver un moyen de gerer les deux passphrases:
# 	   - celle pour signer
# 	   - celel pour chiffrer


class File2(File):
    def signature(self):
        return privkey.sign(f._hash().digest(), seccure.SER_COMPACT)

    def verify(self, signature):
        p = curve.pubkey_from_string(PUBKEY, seccure.SER_COMPACT)
        return p.verify(f._hash().digest(), signature, seccure.SER_COMPACT)

f = File2('/tmp/testbakthat')
sig = f.signature()
print f.verify(sig)

"""
def get_pubkey(passphrase):
    pubkey = str(seccure.passphrase_to_pubkey(passphrase, CURVE))

class BackupInfo(object):
    pass

print seccure.sign(b'This message will be signed\n', PASSPHRASE)

class BackupManager(object):
    def __init__(self):
        pass
"""
# TODO un File object dans dirtools ?
