# -*- encoding: utf-8 -*-
import bakthat
import tempfile
import hashlib
import os
import time
import unittest
import logging

log = logging.getLogger()

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.addFilter(bakthat.BakthatFilter())
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
log.addHandler(handler)
log.setLevel(logging.DEBUG)


class BakthatSwiftBackendTestCase(unittest.TestCase):
    """This test cases use profile test_swift """

    def setUp(self):
        self.test_file = tempfile.NamedTemporaryFile()
        self.test_file.write("Bakthat Test File")
        self.test_file.seek(0)
        self.test_filename = self.test_file.name.split("/")[-1]
        self.test_hash = hashlib.sha1(self.test_file.read()).hexdigest()
        self.password = "bakthat_encrypted_test"
        self.test_profile = "test_swift"

    def test_swift_backup_restore(self):
        backup_data = bakthat.backup(self.test_file.name, "swift", password="",
                                     profile=self.test_profile)
        log.info(backup_data)

        #self.assertEqual(bakthat.match_filename(self.test_filename, "swift",
        #                                        profile=self.test_profile
        #                                        )[0]["filename"],
        #                 self.test_filename)

        bakthat.restore(self.test_filename, "swift", profile=self.test_profile)

        restored_hash = hashlib.sha1(
            open(self.test_filename).read()).hexdigest()

        self.assertEqual(self.test_hash, restored_hash)

        os.remove(self.test_filename)

        bakthat.delete(backup_data["stored_filename"], "swift", profile=self.test_profile)

        #self.assertEqual(bakthat.match_filename(self.test_filename, "swift",
        #                                        profile=self.test_profile), [])

    def test_swift_delete_older_than(self):
        backup_res = bakthat.backup(self.test_file.name, "swift", password="",
                                    profile=self.test_profile)

        #self.assertEqual(bakthat.match_filename(self.test_filename, "swift",
        #                                        profile=self.test_profile
        #                                        )[0]["filename"],
        #                 self.test_filename)

        bakthat.restore(self.test_filename, "swift",
                        profile=self.test_profile)

        restored_hash = hashlib.sha1(
            open(self.test_filename).read()).hexdigest()

        self.assertEqual(self.test_hash, restored_hash)

        os.remove(self.test_filename)

        test_deleted = bakthat.delete_older_than(self.test_filename, "1Y",
                                                 "swift",
                                                 profile=self.test_profile)

        self.assertEqual(test_deleted, [])

        time.sleep(10)

        test_deleted = bakthat.delete_older_than(self.test_filename, "9s",
                                                 "swift",
                                                 profile=self.test_profile)

        key_deleted = test_deleted[0]

        self.assertEqual(key_deleted, backup_res["stored_filename"])

        #self.assertEqual(bakthat.match_filename(self.test_filename,
        #                                        "swift",
        #                                        profile=self.test_profile),
        #                 [])

    def test_swift_encrypted_backup_restore(self):
        backup_data = bakthat.backup(self.test_file.name, "swift", password=self.password,
                                     profile=self.test_profile)

        #self.assertEqual(bakthat.match_filename(self.test_filename, "swift",
        #                                        profile=self.test_profile)
        #                 [0]["filename"], self.test_filename)

        # Check if stored file is encrypted
        #self.assertTrue(bakthat.match_filename(self.test_filename, "swift",
        #                                       profile=self.test_profile)
        #                [0]["is_enc"])

        bakthat.restore(self.test_filename, "swift", password=self.password,
                        profile=self.test_profile)

        restored_hash = hashlib.sha1(
            open(self.test_filename).read()).hexdigest()

        self.assertEqual(self.test_hash, restored_hash)

        os.remove(self.test_filename)

        bakthat.delete(backup_data["stored_filename"], "swift",
                       profile=self.test_profile)

        #self.assertEqual(bakthat.match_filename(self.test_filename,
        #                                        "swift",
        #                                        profile=self.test_profile),
        #                 [])

if __name__ == '__main__':
    unittest.main()
