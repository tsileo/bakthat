import bakthat
import tempfile
import hashlib
import os
import time
import unittest

class BakthatTestCase(unittest.TestCase):

    def setUp(self):
        self.test_file = tempfile.NamedTemporaryFile()
        self.test_file.write("Bakthat Test File")
        self.test_file.seek(0)
        self.test_filename = self.test_file.name.split("/")[-1]
        self.test_hash = hashlib.sha1(self.test_file.read()).hexdigest()
        self.password = "bakthat_encrypted_test"


    def test_s3_backup_restore(self):
        bakthat.backup(self.test_file.name, "s3", password="")

        self.assertEqual(bakthat.match_filename(self.test_filename, "s3")[0]["filename"],
                        self.test_filename)

        bakthat.restore(self.test_filename, "s3")
        
        restored_hash = hashlib.sha1(open(self.test_filename).read()).hexdigest()
        
        self.assertEqual(self.test_hash, restored_hash)

        os.remove(self.test_filename)

        bakthat.delete(self.test_filename, "s3")

        self.assertEqual(bakthat.match_filename(self.test_filename), [])


    def test_s3_encrypted_backup_restore(self):

        bakthat.backup(self.test_file.name, "s3", password=self.password)

        self.assertEqual(bakthat.match_filename(self.test_filename, "s3")[0]["filename"]
                        ,self.test_filename)

        # Check if stored file is encrypted
        self.assertTrue(bakthat.match_filename(self.test_filename, "s3")[0]["is_enc"])

        bakthat.restore(self.test_filename, "s3", password=self.password)

        restored_hash = hashlib.sha1(open(self.test_filename).read()).hexdigest()
        
        self.assertEqual(self.test_hash, restored_hash)

        os.remove(self.test_filename)

        bakthat.delete(self.test_filename, "s3")

        self.assertEqual(bakthat.match_filename(self.test_filename), [])


    def test_glacier_backup_restore(self):
        if raw_input("Test glacier upload/download ? It can take up to 4 hours ! (y/N): ").lower() == "y":

            bakthat.backup(self.test_file.name, "glacier", password="")

            self.assertEqual(bakthat.match_filename(self.test_filename, "glacier")[0]["filename"],
                            self.test_filename)

            job = bakthat.restore(self.test_filename, "glacier", job_check=True)
            
            self.assertEqual(job.__dict__["action"], "ArchiveRetrieval")
            self.assertEqual(job.__dict__["status_code"], "InProgress")

            while 1:
                result = bakthat.restore(self.test_filename, "glacier")
                if result:
                    restored_hash = hashlib.sha1(open(self.test_filename).read()).hexdigest()
        
                    self.assertEqual(self.test_hash, restored_hash)

                    os.remove(self.test_filename)

                    bakthat.delete(self.test_filename, "glacier")

                    self.assertEqual(bakthat.match_filename(self.test_filename, "glacier"), [])
                    break
                else:
                    time.sleep(600)

if __name__ == '__main__':
    unittest.main()
