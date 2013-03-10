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
------

::

    $ bakthat backup --help
    usage: bakthat backup [-h] [-d DESTINATION] [--prompt PROMPT] [-t TAGS]
                      [-p PROFILE]
                      [filename]

    positional arguments:
      filename

    optional arguments:
      -h, --help            show this help message and exit
      -d DESTINATION, --destination DESTINATION
                            s3|glacier
      --prompt PROMPT       yes|no
      -t TAGS, --tags TAGS  space separated tags
      -p PROFILE, --profile PROFILE
                            profile name (default by default)


When backing up file, bakthat store files in gzip format, under the following format: **originaldirname.utctime.tgz**, where utctime is a UTC datetime (%Y%m%d%H%M%S).

.. note::

    If you try to backup a file already gziped, bakthat will only rename it (change extention to .tgz and append utctime).

Bakthat let you tag backups to retrieve them faster, when backing up a file, just append the **--tags**/**-t** argument, tags are space separated, when adding multiple tags, just quote the whole string (e.g. **--tags "tag1 tag2 tag3"**)

If you don't specify a filename/dirname, bakthat will backup the current working directory.

::

    $ cd /dir/i/want/to/bak
    backup to S3
    $ bakthat backup
    or
    $ bakthat backup /dir/i/want/to/bak

    $ bakthat backup /my/dir -t "tag1 tag2"

    you can also backup a single file
    $ bakthat backup /home/thomas/mysuperfile.txt

    backup to Glacier
    $ bakthat backup -d glacier


.. note::

    You can change the temp directory location by setting the TMPDIR, TEMP or TMP environment variables if the backup is too big to fit in the default temp directory.

    ::

        $ export TMP=/home/thomas

Restore
-------

::

    $ bakthat restore --help
    usage: bakthat restore [-h] [-d DESTINATION] [-p PROFILE] filename

    positional arguments:
      filename

    optional arguments:
      -h, --help            show this help message and exit
      -d DESTINATION, --destination DESTINATION
                            s3|glacier
      -p PROFILE, --profile PROFILE
                            profile name (default by default)

When restoring a backup, you can:

- specify **filename**: the latest backups will be restored
- specify **stored filename** directly, if you want to restore an older version.

::

    $ bakthat restore bak

    if you want to restore an older version
    $ bakthat restore bak20120927
    or
    $ bakthat restore bak20120927.tgz.enc

    restore from Glacier
    $ bakthat restore bak -d glacier

.. note::

    When restoring from Glacier, the first time you call the restore command, the job is initiated, then you can check manually whether or not the job is completed (it takes 3-5h to complete), if so the file will be downloaded and restored.


Listing backups
---------------

Let's start with the help for the show subcommand:

::

    $ bakthat show --help
    usage: bakthat show [-h] [-d DESTINATION] [-t TAGS] [-p PROFILE] [query]

    positional arguments:
      query                 search filename for query

    optional arguments:
      -h, --help            show this help message and exit
      -d DESTINATION, --destination DESTINATION
                            glacier|s3, default both
      -t TAGS, --tags TAGS  tags space separated
      -p PROFILE, --profile PROFILE
                            profile name (all profiles are displayed by default)

So when listing backups, you can:

- filter by query (filename/stored filename)
- filter by destination (either glacier or s3)
- filter by tags
- filter by profile (if you manage multiple AWS/bucket/vault)

Example:

::

    show everything
    $ bakthat show

    search for a file stored on s3:
    $ bakthat show myfile -d s3


Delete
------

If the backup is not stored in the default destination, you have to specify it manually.

::

    $ bakthat delete bak

    $ bakthat delete bak -d glacier


Delete older than
-----------------

Delete backup older than the given string interval, like 1M for 1 month and so on.

- **s** seconds
- **m** minutes
- **h** hours
- **D** days
- **W** weeks
- **M** months
- **Y** Years

::

    $ bakthat remove_older_than bakname 3M

    $ bakthat remove_older_than bakname 3M2D8h20m5s

    $ bakthat remove_older_than bakname 3M -d glacier


Backup rotation
---------------

If you make automated with baktaht, it makes sense to rotate your backups.

Bakthat allows you to rotate backups using `Grandfather-father-son backup rotation <http://en.wikipedia.org/wiki/Backup_rotation_scheme#Grandfather-father-son>`_, you can set a default rotation configuration.

::

    $ bakthat configure_backups_rotation

Now you can rotate a backup set:

::

    $ bakthat rotate_backups bakname

Accessing bakthat Python API
----------------------------

Check out the :ref:`developer-guide`.


Configuration
-------------

Bakthat stores configuration in `YAML <http://yaml.org/>`_ format, to have the same configuration handling for both command line and Python module use.

You can also handle **multiples profiles** if you need to manage multiple AWs account or vaults/buckets.

By default, your configuration is stored in **~/.bakthat.yml**.

To get started, you can run **bakthat configure**.

::

    $ bakthat configure

Here is what a configuration object looks like:

.. code-block:: yaml

    access_key: YOUR_ACCESS_KEY
    secret_key: YOUR_SECRET_KEY
    region_name: us-east-1
    glacier_vault: myvault
    s3_bucket: mybucket

The **region_name** key is optionnal is you want to use **us-east-1**.


Managing profiles
~~~~~~~~~~~~~~~~~

Here is how profiles are stored, you can either create them manually or with command line.

.. code-block:: yaml

    default:
      access_key: YOUR_ACCESS_KEY
      secret_key: YOUR_SECRET_KEY
      region_name: us-east-1
      glacier_vault: myvault
      s3_bucket: mybucket
    myprofile:
      access_key: YOUR_ACCESS_KEY
      secret_key: YOUR_SECRET_KEY
      region_name: us-east-1
      glacier_vault: myvault
      s3_bucket: mybucket


To create a profile from command line with bakthat:

::

    $ bakthat configure --profile mynewprofile

    $ bakthat configure -h
    usage: bakthat configure [-h] [-p PROFILE]

    optional arguments:
      -h, --help            show this help message and exit
      -p PROFILE, --profile PROFILE
                            profile name (default by default)


Once your profile is configured, you can use it with **--profile**/**-p** argument.

::

    $ bakthat backup -p myprofile
    $ bakthat show -p myprofile

.. _stored-metadata:

Stored metadata
---------------

Batkthat stores some data about your backups in a SQLite database (using `peewee <http://peewee.readthedocs.org/>`_ as wrapper) for few reasons:

- to allow you to filter them efficiently.
- to avoid making a lot of requests to AWS.
- to let you sync your bakthat data with multiple servers.

Here is a example of data stored in the SQLite database:

.. code-block:: python

    {u'backend': u's3',
     u'backend_hash': u'9813aa99062d7a226f3327478eff3f63bf5603cd86999a42a2655f5d460e8e143c63822cb8e2f8998a694afee8d30c4924923dff695c6e5f739dffdd65768408',
     u'backup_date': 1362508575,
     u'filename': u'mydir',
     u'is_deleted': 0,
     u'last_updated': 1362508727,
     u'metadata': {u'is_enc': True},
     u'size': 3120,
     u'stored_filename': u'mydir.20130305193615.tgz.enc',
     u'tags': []}

All the keys are explicit, except **backend_hash**, which is the hash of your AWS access key concatenated with either the S3 bucket, either the Glacier vault. This key is used when syncing backups with multiple servers.


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
