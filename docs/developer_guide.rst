.. _developer-guide:

Developer's Guide
=================

Low level API
-------------

You can access low level API (the same used when using bakthat in command line mode) from **bakthat** root module.

.. code-block:: python

    import bakthat

    # roration is optional
    bakthat_conf = {'access_key': 'YOURACCESSKEY',
                    'secret_key': 'YOURSECRETKEY',
                    'glacier_vault': 'yourvault',
                    's3_bucket': 'yours3bucket',
                    'region_name': 'eu-west-1',
                    'rotation': {'days': 7,
                                'first_week_day': 5,
                                'months': 6,
                                'weeks': 6}}

    bakthat.backup("/dir/i/wanto/bak", conf=bakthat_conf)

    bakthat.backup("/dir/i/wanto/bak", conf=bakthat_conf, destination="glacier")

    # or if you want to have generated the configuration file with "bakthat configure" or created ~/.bakthat.yml
    bakthat.backup("/dir/i/wanto/bak")

    bakthat.ls()

    # restore in the current working directory
    bakthat.restore("bak", conf=bakthat_conf)

Helpers
-------

.. _keyvalue:

KeyValue
~~~~~~~~

KeyValue is a simple "key value store" that allows you to quickly store/retrieve strings/objects on Amazon S3.
All values are serialized with json, so **you can directly backup any json serializable value**.

It can also takes care of compressing (with gzip) and encrypting (optionnal).

Compression in enabled by default, you can disable it by passing compress=False when setting a key.

Also, backups stored with KeyValue can be restored with bakthat restore and show up in bakthat show.

.. code-block:: python

    from bakthat.helper import KeyValue
    import json

    bakthat_conf = {'access_key': 'YOURACCESSKEY',
                    'secret_key': 'YOURSECRETKEY',
                    'glacier_vault': 'yourvault',
                    's3_bucket': 'yours3bucket',
                    'region_name': 'es-east-1'}

    kv = KeyValue(conf=bakthat_conf)

    mydata = {"some": "data"}
    kv.set_key("mykey", mydata)

    mydata_restored = kv.get_key("mykey")

    data_url = kv.get_key_url("mykey", 60)  # url expires in 60 secondes

    kv.delete_key("mykey")

    kv.set_key("my_encrypted_key", "myvalue", password="mypassword")
    kv.get_key("my_encrypted_key", password="mypassword")

    # You can also disable gzip compression if you want:
    kv.set_key("my_non_compressed_key", {"my": "data"}, compress=False)


BakHelper
~~~~~~~~~

BakHelper is a context manager that makes create backup script with bakthat (and it works well with `sh <http://amoffat.github.com/sh/>`_) an easy task.

It takes care of create a temporary directory and make it the current working directory so you can just dump files to backup or call system command line tool lilke mysqldump/mongodump/and so on with the help of sh.

Here is a minimal example.

.. code-block:: python

    import logging
    logging.basicConfig(level=logging.INFO)

    from bakthat.helper import BakHelper

    with BakHelper("mybackup", tags=["mybackup"]) as bh:

        with open("myfile.txt", "w") as f:
            f.write("mydata")
        
        bh.backup()
        bh.rotate()


Now test the script:

::

    $ python mybackupscript.py
    INFO:root:Backing up /tmp/mybackup_JVTGOM
    INFO:root:Compressing...
    INFO:root:Uploading...
    INFO:bakthat.backends:Upload completion: 0%
    INFO:bakthat.backends:Upload completion: 100%    

You can also use it like a normal class:

.. code-block:: python

    import logging
    import sh
    logging.basicConfig(level=logging.INFO)

    from bakthat.helper import BakHelper

    bakthat_conf = {'access_key': 'YOURACCESSKEY',
                    'secret_key': 'YOURSECRETKEY',
                    'glacier_vault': 'yourvault',
                    's3_bucket': 'yours3bucket',
                    'region_name': 'eu-west-1',
                    'rotation': {'days': 7,
                                'first_week_day': 5,
                                'months': 6,
                                'weeks': 6}}

    bh = BakHelper(conf=bakthat_conf)
    with open("myfile.txt", "w") as f:
        f.write("mydata")
    bh.backup("myfile.txt")
    bh.rotate("myfile.txt")


Create a MySQL backup script with BakHelper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is a MySQL backup script, it makes use of `sh <http://amoffat.github.com/sh/>`_ to call system **mysqldump**.

.. code-block:: python

    import logging
    import sh
    logging.basicConfig(level=logging.INFO)

    from bakthat.helper import BakHelper

    BACKUP_NAME = "myhost_mysql"
    BACKUP_PASSWORD = "mypassword"
    MYSQL_USER = "root"
    MYSQL_PASSWORD = "mypassword"

    with BakHelper(BACKUP_NAME, password=BACKUP_PASSWORD, tags=["mysql"]) as bh:
        sh.mysqldump("-p{0}".format(MYSQL_PASSWORD),
                    u=MYSQL_USER,
                    all_databases=True,
                    _out="dump.sql")
        bh.backup()
        bh.rotate()


Accessing bakthat SQLite database
---------------------------------

Since bakthat stores custom backups metadata (see :ref:`stored-metadata`), you can execute custom SQL query.