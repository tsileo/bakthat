import bakthat
import tempfile
import hashlib
import os
import unittest

class TestSequenceFunctions(unittest.TestCase):

    def setUp(self):
        self.test_file = tempfile.NamedTemporaryFile()
        self.test_file.write("Bakthat Test File")
        self.test_file.seek(0)
        self.test_filename = self.test_file.name.split("/")[-1]
        self.test_hash = hashlib.sha1(self.test_file.read()).hexdigest()

    def tearDown(self):
        """Teardown."""
        pass

    def test_s3_backup_restore(self):
        bakthat.backup(self.test_file.name, "s3", password="")
        bakthat.restore(self.test_filename)
        restored_hash = hashlib.sha1(open(self.test_filename).read()).hexdigest()
        self.assertEqual(self.test_hash, restored_hash)
        os.remove(self.test_filename)


    def test_s3_encrypted_backup_restore(self):
        password = "bakthat_encrypted_test"

        bakthat.backup(self.test_file.name, "s3", password=password)

        bakthat.restore(self.test_filename, password=password)

        restored_hash = hashlib.sha1(open(self.test_filename).read()).hexdigest()
        self.assertEqual(self.test_hash, restored_hash)
        os.remove(self.test_filename)

if __name__ == '__main__':
    unittest.main()
