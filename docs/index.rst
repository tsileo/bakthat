.. Bakthat documentation master file, created by
   sphinx-quickstart on Fri Mar  1 10:32:38 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Bakthat: Python backup framework and command line tool
======================================================

Release v\ |version|.

Bakthat is a MIT licensed backup framework written in Python, it's both a command line tool and a Python module that helps you manage backups on Amazon S3/Glacier. It automatically compress, encrypt (symmetric encryption) and upload your files.

Here are some features:

* Compress with `tarfile <http://docs.python.org/library/tarfile.html>`_
* Encrypt with `beefish <http://pypi.python.org/pypi/beefish>`_ (**optional**)
* Upload/download to S3 or Glacier with `boto <http://pypi.python.org/pypi/boto>`_
* Local backups inventory stored in a SQLite database with `peewee <http://peewee.readthedocs.org/>`_
* Delete older than, and `Grandfather-father-son backup rotation <http://en.wikipedia.org/wiki/Backup_rotation_scheme#Grandfather-father-son>`_ supported
* Possibility to sync backups database between multiple clients via a centralized server

You can restore backups **with** or **without** bakthat, you just have to download the backup, decrypt it with `Beefish <http://pypi.python.org/pypi/beefish>`_ command-line tool and untar it.


Requirements
------------

Bakthat requirements are automatically installed when installing bakthat, but if you want you can install them manually: 

::

    $ pip install -r requirements.txt


* `aaargh <http://pypi.python.org/pypi/aaargh>`_
* `pycrypto <https://www.dlitz.net/software/pycrypto/>`_
* `beefish <http://pypi.python.org/pypi/beefish>`_
* `boto <http://pypi.python.org/pypi/boto>`_
* `GrandFatherSon <https://pypi.python.org/pypi/GrandFatherSon>`_
* `peewee <http://peewee.readthedocs.org/>`_
* `byteformat <https://pypi.python.org/pypi/byteformat>`_
* `pyyaml <http://pyyaml.org>`_
* `sh <http://amoffat.github.com/sh/>`_
* `requests <http://docs.python-requests.org>`_

If you want to use OpenStack Swift, following additional packages are also required.

* `python-swiftclient <https://pypi.python.org/pypi/python-swiftclient>`_
* `python-keystoneclient <https://pypi.python.org/pypi/python-keystoneclient/>`_



Overview
--------

Bakthat command line tool
~~~~~~~~~~~~~~~~~~~~~~~~~

::

    $ pip install bakthat

    $ bakthat configure
    
    $ bakthat backup mydir
    Backing up mydir
    Password (blank to disable encryption): 
    Password confirmation: 
    Compressing...
    Encrypting...
    Uploading...
    Upload completion: 0%
    Upload completion: 100%

    or

    $ cd mydir
    $ bakthat backup
    
    $ bakthat show
    2013-03-05T19:36:15 s3  3.1 KB  mydir.20130305193615.tgz.enc

    $ bakthat restore mydir
    Restoring mydir.20130305193615.tgz.enc
    Password: 
    Downloading...
    Decrypting...
    Uncompressing...

    $ bakthat delete mydir.20130305193615.tgz.enc
    Deleting mydir.20130305193615.tgz.enc

Bakthat Python API
~~~~~~~~~~~~~~~~~~

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


Installation
------------

With pip/easy_install:

::

    $ pip install bakthat

From source:

::

    $ git clone https://github.com/tsileo/bakthat.git
    $ cd bakthat
    $ sudo python setup.py install


Next, you need to set your AWS credentials:

::

    $ bakthat configure


User Guide
----------

.. toctree::
   :maxdepth: 2

   user_guide

Developer's Guide
-----------------

.. toctree::
   :maxdepth: 2

   developer_guide


API Documentation
-----------------

.. toctree::
   :maxdepth: 2

   api


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
