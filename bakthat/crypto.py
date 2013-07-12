# -*- coding: utf-8 -*-
import os
from dirtools import File

from simplejson import json
import seccure

CURVE = 'secp256r1/nistp256'


def generate_random_passphrase():
    return os.urandom(32).encode('hex')


class SeccureIdentity(object):
    """ Handle seccure identity, stored in JSON file. """
    def __init__(self, identity, **kwargs):
        self.identity = identity
        self.data = kwargs.get('data', {})
        filename = kwargs.get('filename', self.identity + '.json')
        if os.path.isfile(filename):
            with open(filename, 'r') as json_file:
                self.data = json.loads(json_file.read())
        self.filename = filename
        self.curve = seccure.Curve.by_name(CURVE)

    def __getattr__(self, attr):
        _r = self.data.get(attr)
        if isinstance(_r, unicode):
            _r = _r.encode('utf-8')
        return _r

    @property
    def privkey(self):
        return self.curve.passphrase_to_privkey(self.passphrase)

    @classmethod
    def new(cls, identity, passphrase=None):
        if passphrase is None:
            passphrase = generate_random_passphrase()
        pubkey = str(seccure.passphrase_to_pubkey(passphrase, CURVE))
        data = {'passphrase': passphrase, 'pubkey': pubkey}
        return cls(identity, data=data)

    def create_file(self, filename=None):
        if filename is None:
            filename = self.identity + '.json'
        with open(filename, 'w') as identity_file:
            identity_file.write(json.dumps(self.data))


class SignedFile(File):
    def __init__(self, path, identity):
        if not isinstance(identity, SeccureIdentity):
            identity = SeccureIdentity(identity)
        self.identity = identity
        return super(SignedFile, self).__init__(path)

    def _signature(self):
        return self.identity.privkey.sign(self._hash().digest(),
                                          seccure.SER_COMPACT)

    def _verify(self, signature):
        p = self.identity.curve.pubkey_from_string(self.identity.pubkey,
                                                   seccure.SER_COMPACT)
        return p.verify(self._hash().digest(), signature, seccure.SER_COMPACT)

    def generate_signature(self, sig_file=None):
        if sig_file is None:
            sig_file = self.path + '.sig'
        with open(sig_file, 'w') as sig:
            sig.write(self._signature())

    def verify_signature(self, sig_file=None):
        """ Check the signature integrety of a signed file. """
        if sig_file is None:
            sig_file = self.path + '.sig'
        if not os.path.isfile(sig_file):
            raise IOError('Signature file not found.')
        with open(sig_file, 'r') as sig:
            return self._verify(sig.read())
