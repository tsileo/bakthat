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


class BakthatTestCase(unittest.TestCase):

    def setUp(self):
        self.test_file = tempfile.NamedTemporaryFile()
        self.test_file.write("Bakthat Test File")
        self.test_file.seek(0)
        self.test_filename = self.test_file.name.split("/")[-1]
        self.test_hash = hashlib.sha1(self.test_file.read()).hexdigest()
        self.password = "bakthat_encrypted_test"

    def test_internals(self):
        with self.assertRaises(Exception):
            bakthat._interval_string_to_seconds("1z")

        self.assertEqual(bakthat._interval_string_to_seconds("2D1h"), 86400 * 2 + 3600)
        self.assertEqual(bakthat._interval_string_to_seconds("3M"), 3*30*86400)

    def test_keyvalue_helper(self):
        from bakthat.helper import KeyValue
        kv = KeyValue()
        test_string = "Bakthat Test str"
        test_key = "bakthat-unittest"
        test_key_enc = "bakthat-unittest-testenc"
        test_key2 = "itshouldfail"
        test_password = "bakthat-password"
        kv.set_key(test_key, test_string)
        kv.set_key(test_key_enc, test_string, password=test_password)
        self.assertEqual(test_string, kv.get_key(test_key))
        self.assertEqual(test_string, kv.get_key(test_key_enc, password=test_password))
        #from urllib2 import urlopen, HTTPError
        #test_url = kv.get_key_url(test_key, 10)
        #self.assertEqual(json.loads(urlopen(test_url).read()), test_string)
        #time.sleep(30)
        #with self.assertRaises(HTTPError):
        #    urlopen(test_url).read()
        kv.delete_key(test_key_enc)
        kv.delete_key(test_key)
        self.assertEqual(kv.get_key(test_key), None)
        self.assertEqual(kv.get_key(test_key2), None)


    def test_s3_backup_restore(self):
        backup_data = bakthat.backup(self.test_file.name, "s3", password="")
        log.info(backup_data)

        #self.assertEqual(bakthat.match_filename(self.test_filename, "s3")[0]["filename"],
        #                 self.test_filename)

        bakthat.restore(self.test_filename, "s3")

        restored_hash = hashlib.sha1(open(self.test_filename).read()).hexdigest()

        self.assertEqual(self.test_hash, restored_hash)

        os.remove(self.test_filename)

        bakthat.delete(self.test_filename, "s3")

        #self.assertEqual(bakthat.match_filename(self.test_filename), [])

    def test_s3_delete_older_than(self):
        backup_res = bakthat.backup(self.test_file.name, "s3", password="")

        #self.assertEqual(bakthat.match_filename(self.test_filename, "s3")[0]["filename"],
        #                 self.test_filename)

        bakthat.restore(self.test_filename, "s3")

        restored_hash = hashlib.sha1(open(self.test_filename).read()).hexdigest()

        self.assertEqual(self.test_hash, restored_hash)

        os.remove(self.test_filename)

        test_deleted = bakthat.delete_older_than(self.test_filename, "1Y", "s3")

        self.assertEqual(test_deleted, [])

        time.sleep(10)

        test_deleted = bakthat.delete_older_than(self.test_filename, "9s", "s3")

        key_deleted = test_deleted[0]

        self.assertEqual(key_deleted, backup_res["stored_filename"])

        #self.assertEqual(bakthat.match_filename(self.test_filename), [])

    def test_s3_encrypted_backup_restore(self):
        bakthat.backup(self.test_file.name, "s3", password=self.password)

        #self.assertEqual(bakthat.match_filename(self.test_filename, "s3")[0]["filename"],
        #                 self.test_filename)

        # Check if stored file is encrypted
        #self.assertTrue(bakthat.match_filename(self.test_filename, "s3")[0]["is_enc"])

        bakthat.restore(self.test_filename, "s3", password=self.password)

        restored_hash = hashlib.sha1(open(self.test_filename).read()).hexdigest()

        self.assertEqual(self.test_hash, restored_hash)

        os.remove(self.test_filename)

        bakthat.delete(self.test_filename, "s3")

        #self.assertEqual(bakthat.match_filename(self.test_filename), [])

    def test_glacier_backup_restore(self):
        if raw_input("Test glacier upload/download ? It can take up to 4 hours ! (y/N): ").lower() == "y":

            # Backup dummy file
            bakthat.backup(self.test_file.name, "glacier", password="")

            # Check that file is showing up in bakthat ls
            #self.assertEqual(bakthat.match_filename(self.test_filename, "glacier")[0]["filename"],
            #                self.test_filename)
            # TODO replace by a Backups.search

            # We initialize glacier backend
            # to check that the file appear in both local and remote (S3) inventory
            #glacier_backend = GlacierBackend(None)

            #archives = glacier_backend.load_archives()
            #archives_s3 = glacier_backend.load_archives_from_s3()

            # Check that local and remote custom inventory are equal
            #self.assertEqual(archives, archives_s3)

            # Next we check that the file is stored in both inventories
            #inventory_key_name = bakthat.match_filename(self.test_filename, "glacier")[0]["key"]

            #self.assertTrue(inventory_key_name in [a.get("filename") for a in archives])
            #self.assertTrue(inventory_key_name in [a.get("filename") for a in archives_s3])

            # Restore backup
            job = bakthat.restore(self.test_filename, "glacier", job_check=True)

            # Check that a job is initiated
            self.assertEqual(job.__dict__["action"], "ArchiveRetrieval")
            self.assertEqual(job.__dict__["status_code"], "InProgress")

            while 1:
                # Check every ten minutes if the job is done
                result = bakthat.restore(self.test_filename, "glacier")

                # If job is done, we can download the file
                if result:
                    restored_hash = hashlib.sha1(open(self.test_filename).read()).hexdigest()

                    # Check if the hash of the restored file is equal to inital file hash
                    self.assertEqual(self.test_hash, restored_hash)

                    os.remove(self.test_filename)

                    # Now, we can delete the restored file
                    bakthat.delete(self.test_filename, "glacier")

                    # Check that the file is deleted
                    #self.assertEqual(bakthat.match_filename(self.test_filename, "glacier"), [])
                    # TODO Backups.search

                    #archives = glacier_backend.load_archives()
                    #archives_s3 = glacier_backend.load_archives_from_s3()

                    # Check if the file has been removed from both archives
                    #self.assertEqual(archives, archives_s3)
                    #self.assertTrue(inventory_key_name not in archives)
                    #self.assertTrue(inventory_key_name not in archives_s3)

                    break
                else:
                    time.sleep(600)

if __name__ == '__main__':
    unittest.main()
