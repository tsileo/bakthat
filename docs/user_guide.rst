.. _user_guide:

User Guide
==========

Everything you need to know as a user.

Getting Started
---------------

Basic usage, "bakthat -h" or "bakthat <command> -h" to show the help.

S3 is the default destination, to use Glacier just add "-d glacier" or "--destination glacier".

If you haven't configured bakthat yet, you should run:

::

    $ bakthat configure


Backup
~~~~~~

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


You can change the temp directory location by setting the TMPDIR, TEMP or TMP environment variables if the backup is too big to fit in the default temp directory.

::

    $ export TMP=/home/thomas

Restore
~~~~~~~

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
~~~~

::

    $ bakthat ls
    or 
    $ bakthat ls -d s3

    $ bakthat ls -d glacier


Delete
~~~~~~

::

    $ bakthat delete -f bak

    $ bakthat delete -f bak -d glacier

Info
~~~~

You can quickly check when was the last time you backed up a directory:

::

    $ bakthat info


Delete older than
-----------------

Delete backup older than the given interval.

- **s** seconds
- **m** minutes
- **h** hours
- **D** days
- **W** weeks
- **M** months
- **Y** Years

::

    $ bakthat remove_older_than -f bakname -i 3M

    $ bakthat remove_older_than -f bakname -i 3M2D8h20m5s

Backup rotation
---------------

Rotate backup using `Grandfather-father-son backup rotation <http://en.wikipedia.org/wiki/Backup_rotation_scheme#Grandfather-father-son>`_, you can set a default rotation configuration.

::

    $ bakthat configure_backups_rotation

Now you can rotate a backup set:

::

    $ bakthat rotate_backups -f bakname


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


S3 and Glacier IAM permissions
------------------------------

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
