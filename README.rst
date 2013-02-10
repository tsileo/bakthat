=======
Bakthat
=======

Compress, encrypt (symmetric encryption) and upload files directly to Amazon S3/Glacier in a single command. Can also be used as a python module.

While navigating directories, I was tired of telling myself I should backup these #?!!* small files/directories.
Since I didn't found any solution that allows me to quickly perform encrypted backup on Amazon S3 from command-line, I wrote bakthat !

Here are some features:

* Compress with `tarfile <http://docs.python.org/library/tarfile.html>`_
* Encrypt with `beefish <http://pypi.python.org/pypi/beefish>`_ (**optional**)
* Upload/download to S3 or Glacier with `boto <http://pypi.python.org/pypi/boto>`_
* Local Glacier inventory stored with `shelve <http://docs.python.org/library/shelve.html>`_
* Automatically handle/backup/restore a custom Glacier inventory to S3

You can restore backups **with** or **without** bakthat, you just have to download the backup, decrypt it with `Beefish <http://pypi.python.org/pypi/beefish>`_ command-line tool and untar it.

Be careful, if you want to be able to **backup/restore your glacier inventory**, you need **to setup a S3 Bucket even if you are planning to use bakthat exclusively with glacier**, all the archives ids are stored under JSON format in a S3 Key.

Overview
========

::

    $ cd /dir/i/want/to/bak
    $ bakthat backup
    INFO: Backing up /dir/i/want/to/bak
    Password (blank to disable encryption): 
    2012-11-14 19:55:07,585 INFO: Compressing...
    2012-11-14 19:55:07,590 INFO: Encrypting...
    2012-11-14 19:55:07,597 INFO: Uploading...
    2012-11-14 19:55:07,615 INFO: Upload completion: 0%
    2012-11-14 19:55:07,616 INFO: Upload completion: 100%
    $

    $ bakthat backup -d glacier
    2012-11-14 19:55:44,043 INFO: Backing up /dir/i/want/to/bak
    Password (blank to disable encryption): 
    2012-11-14 19:55:48,385 INFO: Compressing...
    2012-11-14 19:55:48,390 INFO: Encrypting...
    2012-11-14 19:55:48,397 INFO: Uploading...

    $


    $ bakthat restore -f bak
    INFO: Restoring bak20120928.tgz.enc
    Password:
    2012-11-14 19:55:19,365 INFO: Downloading...
    2012-11-14 19:55:19,507 INFO: Decrypting...
    2012-11-14 19:55:19,508 INFO: Uncompressing... 
    $


    $ bakthat restore -f todo -d glacier
    2012-11-14 20:01:39,491 INFO: Restoring todo20121114195616.tgz
    2012-11-14 20:01:39,491 INFO: Downloading...
    2012-11-14 20:01:39,809 INFO: Job ArchiveRetrieval: InProgress (2012-11-14T19:01:32.288Z/None)
    2012-11-14 20:01:39,809 INFO: Not completed yet
    $

    $ bakthat ls
    2012-11-14 19:59:58,500 INFO: S3 Bucket: bakthattest
    2012-11-14 19:59:58,919 INFO: todo20121114195502.tgz.enc

    $ bakthat delete -f bak
    2012-11-14 19:55:30,148 INFO: Deleting todo20121114195502.tgz.enc

    $ bakthat info
    2013-02-08 13:37:07,407 INFO: Last backup date: 2012-12-11T11:02:33 (1 versions)

Requirements
============

* `Aaargh <http://pypi.python.org/pypi/aaargh>`_
* `Pycrypto <https://www.dlitz.net/software/pycrypto/>`_
* `Beefish <http://pypi.python.org/pypi/beefish>`_
* `Boto <http://pypi.python.org/pypi/boto>`_


Installation
============

::

    $ pip install bakthat

You need to set your AWS credentials:

::

    $ bakthat configure


Usage
=====

Basic usage, "bakthat -h" or "bakthat <command> -h" to show the help.

S3 is the default destination, to use Glacier just add "-d glacier" or "--destination glacier".

You can change the temp directory location by setting the TMPDIR, TEMP or TMP environment variables if the backup is too big to fit in the default temp directory.

Backup
------

::

    $ cd /dir/i/want/to/bak
    backup to S3
    $ bakthat backup
    or
    $ bakthat backup -f /dir/i/want/to/bak

    you can also backup a single file
    $ bakthat backup -f /home/thomas/mysuperfile.txt

    backup to Glacier
    $ bakthat backup -d glacier

Restore
-------

You can restore the latest version of a backup just by specifying the begining of the filename.

::

    $ bakthat restore -f bak

    if you want to restore an older version
    $ bakthat restore -f bak20120927
    or
    $ bakthat restore -f bak20120927.tgz.enc

    restore from Glacier
    $ bakthat restore -f bak -d glacier

When restoring from Glacier, the first time you call the restore command, the job is initiated, then you can check manually whether or not the job is completed (it takes 3-5h to complete), if so the file will be downloaded and restored.

List
----

::

    $ bakthat ls
    or 
    $ bakthat ls -d s3

    $ bakthat ls -d glacier


Delete
------

::

    $ bakthat delete -f bak

    $ bakthat delete -f bak -d glacier

Info
----

You can quickly check when was the last time you backed up a directory:

::

    $ bakthat info


Backup/Restore Glacier inventory
--------------------------------

Bakthat automatically backups the local Glacier inventory (a dict with filename => archive_id mapping) to your S3 bucket under the "bakthat_glacier_inventory" key.

You can retrieve bakthat custom inventory without waiting:

::

    $ bakthat show_glacier_inventory

or

::

    $ bakthat show_local_glacier_inventory

You can trigger a backup mannualy:

::

    $ bakthat backup_glacier_inventory

And here is how to restore the glacier inventory from S3:

::

    $ bakthat restore_glacier_inventory


As a module
===========

::

    import bakthat
    aws_conf = {"access_key":"", "secret_key":"", "bucket": "", "vault": ""}

    bakthat.backup("/dir/i/wanto/bak", conf=aws_conf)
    bakthat.backup("/dir/i/wanto/bak", conf=aws_conf, destination="glacier")

    # or if you want to have generated the configuration file with "bakthat configure"
    # and want to use this file:
    bakthat.backup("/dir/i/wanto/bak")

    bakthat.ls()

    # restore in the current working directory
    bakthat.restore("bak", conf=aws_conf)


S3 and Glacier IAM permissions
==============================================

::

	{       
	    "Statement": [
		{
		    "Effect": "Allow",
		    "Action": "s3:*",
		    "Resource": "arn:aws:s3:::S3_BUCKET_NAME*"
		},
		{
		    "Effect": "Allow",
		    "Action": "glacier:*"
		    "Resource": "arn:aws:glacier:AWS_REGION:AWS_ACCOUNT_ID:vaults/GLACIER_VAULT_NAME",
		}
	    ]
	}



Contributors
============

- Eric Chamberlain
- Darius Braziunas
- Sławomir Żak
- Andreyev Dias de Melo
- Jake McGraw


License (MIT)
=============

Copyright (c) 2012 Thomas Sileo

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
