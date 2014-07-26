=======
Bakthat
=======

I stopped working on bakthat, I'm now working on another backup-related project: `blobstash <https://github.com/tsileo/blobstash>`_/`blobsnap <https://github.com/tsileo/blobsnap>`_.
If somebody want to be a collaborator and continue development, please open an issue.

Bakthat is a MIT licensed backup framework written in Python, it's both a command line tool and a Python module that helps you manage backups on Amazon `S3 <http://aws.amazon.com/s3/>`_/`Glacier <http://aws.amazon.com/glacier/>`_ and OpenStack `Swift <http://swift.openstack.org>`_. It automatically compress, encrypt (symmetric encryption) and upload your files.

Here are some features:

* Compress with `tarfile <http://docs.python.org/library/tarfile.html>`_
* Encrypt with `beefish <http://pypi.python.org/pypi/beefish>`_ (**optional**)
* Upload/download to S3 or Glacier with `boto <http://pypi.python.org/pypi/boto>`_
* Local backups inventory stored in a SQLite database with `peewee <http://peewee.readthedocs.org/>`_
* Delete older than, and `Grandfather-father-son backup rotation <http://en.wikipedia.org/wiki/Backup_rotation_scheme#Grandfather-father-son>`_ supported
* Possibility to sync backups database between multiple clients via a centralized server
* Exclude files using .gitignore like file
* Extendable with plugins

You can restore backups **with** or **without** bakthat, you just have to download the backup, decrypt it with `Beefish <http://pypi.python.org/pypi/beefish>`_ command-line tool and untar it.

Check out `the documentation to get started <http://docs.bakthat.io>`_.


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


Changelog
---------

0.7.0
~~~~~

**Not released yet**, developed in the **develop** branch.

- Incremental backups support, with `Incremental-Backups-Tools <https://github.com/tsileo/incremental-backups-tools>`_.
- Revamped configuration handling
- Stronger unit tests
- Plugin architecture improved
- Switch from aaargh to cliff for the CLI handling

0.6.0
~~~~~

**June 5 2013**

- Event hooks handling
- Support for plugin

0.5.5
~~~~~

**May 26 2013**

- Support for excluding files, using .bakthatexclude/.gitignore file, or a custom file.
- Added support for reduced redundancy when using S3

0.5.4
~~~~~

**May 8 2013**

- Better log handling
- Allow more complex rotation scheme

0.5.3
~~~~~

**May 6 2013**

- Bugfix config

0.5.2
~~~~~

**May 6 2013**

- new BAKTHAT_PASSWORD environment variable to set password from command line.

0.5.1
~~~~~

**May 5 2013**

- New **-c**/**--config** argument.
- New periodic_backups command tied to `BakManager API <https://bakmanager.io>`_.

0.5.0
~~~~~

**April 21 2013**

- New Swift backend, thanks to @yoyama
- ls command removed in favor of the show command
- Compression can now be disabled with the compress setting
- Bugfix default destination 

0.4.5
~~~~~

**Mars 20 2013**

- bugfix configure (cancel of configure cmd cause empty yml), thanks to @yoyama
- new bakthat.helper.KeyValue
- BakSyncer improvement

0.4.4
~~~~~

**Mars 10 2013**

- bugfix (forgot to remove a dumptruck import)

0.4.3
~~~~~

**Mars 10 2013**

- bakthat show bugfix

0.4.2
~~~~~

**Mars 10 2013**

- Using `peewee <http://peewee.readthedocs.org/>`_ instead of dumptruck, should be Python2.6 compatible again.


0.4.1
~~~~~

**Mars 8 2013**

- small bugfix when restoring from glacier
- bakhelper now support custom configuration and profiles
- aligned date in show command

0.4.0
~~~~~

If you come from bakthat 0.3.x, you need to run:

::

    $ bakthat upgrade_to_dump_truck

And you also need to run again **bakthat configure**.

::

    $ cat ~/.bakthat.conf
    $ bakthat configure

**Changes:**

- The filename is now a positional argument for all command
- Using `DumpTruck <http://www.dumptruck.io/>`_ instead of `shelve <http://docs.python.org/library/shelve.html>`_
- Save backups metadata for both backends
- BakHelper to help build backup scripts
- BakSyncer to help keep you list sync over a custom REST API
- Now adding a dot between the original filename and the date component
- Tags support (-t/--tags argument)
- Profiles support (-p/--profile argument)
- New show command, with search support (tags/filename/destination)
- `Hosted documentation <http://docs.bakthat.io>`_


0.3.10
~~~~~

- bug fix glacier upload

0.3.9
~~~~~

- small bug fixes (when updating an existing configuration)

0.3.8
~~~~~

- Added **delete_older_than** command
- Added **rotate_backups** command (Grandfather-father-son backup rotation scheme)


Contributors
------------

- Eric Chamberlain
- Darius Braziunas
- Sławomir Żak
- Andreyev Dias de Melo
- Jake McGraw
- You Yamagata
- Jordi Funollet


License (MIT)
-------------

Copyright (c) 2012 Thomas Sileo

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
