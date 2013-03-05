.. _developer_guide:

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


BakHelper
---------

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

    bh = BakHelper()
    with open("myfile.txt", "w") as f:
        f.write("mydata")
    bh.backup("myfile.txt")
    bh.rotate("myfile.txt")


Accessing bakthat SQLite database
---------------------------------

Since bakthat stores custom backups metadata (see :ref:`stored-metadata`), you can execute custom SQL query with bakthat `DumpTruck <http://www.dumptruck.io/>`_ instance.

.. code-block:: python

    from bakthat.conf import dump_truck
    dump_truck.execute("SELECT * FROM backups")

