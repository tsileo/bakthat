=======
Bakthat
=======

Bakthat is a MIT licensed backup tools, it's both a friendly command line interface and a Python module that helps you manage backups on Amazon S3/Glacier.

It lets you compress, encrypt (symmetric encryption) and upload your files directly to Amazon S3/Glacier in a single command. It also make restoring backups a breeze.

Here are some features:

* Compress with `tarfile <http://docs.python.org/library/tarfile.html>`_
* Encrypt with `beefish <http://pypi.python.org/pypi/beefish>`_ (**optional**)
* Upload/download to S3 or Glacier with `boto <http://pypi.python.org/pypi/boto>`_
* Local Glacier inventory stored in a SQLite database with `DumpTruck <http://www.dumptruck.io/>`_
* Automatically handle/backup/restore a custom Glacier inventory to S3
* Delete older than, and `Grandfather-father-son backup rotation <http://en.wikipedia.org/wiki/Backup_rotation_scheme#Grandfather-father-son>`_ supported

You can restore backups **with** or **without** bakthat, you just have to download the backup, decrypt it with `Beefish <http://pypi.python.org/pypi/beefish>`_ command-line tool and untar it.

Be careful, if you want to be able to **backup/restore your glacier inventory**, you need **to setup a S3 Bucket even if you are planning to use bakthat exclusively with glacier**, all the archives ids are backed up in JSON format in a S3 Key.


Changelog
---------

0.4.0
~~~~~

__Not on pypi yet, I'm making final tests before releasing.__

If you come from bakthat 0.3.x, you need to run:

::

    $ bakthat upgrade_to_dump_truck


Changes:

- Using `DumpTruck <http://www.dumptruck.io/>`_ instead of `shelve <http://docs.python.org/library/shelve.html>`_
- Save backups metadata for both backends
- BakHelper to help build backup scripts
- BakSyncer to help keep you list sync over a custom REST API
- Now adding a dot between the original filename and the date component
- Tags support (-t/--tags argument)
- New show command, with search support (tags/filename/destination)
- Added documentation


0.3.10
~~~~~

- bug fix glacier upload

0.3.9
~~~~~

- small bug fixes (when updating an existing configuration)

0.3.8
~~~~~

- Added **remove_older_than** command
- Added **rotate_backups** command (Grandfather-father-son backup rotation scheme)


Contributors
------------

- Eric Chamberlain
- Darius Braziunas
- Sławomir Żak
- Andreyev Dias de Melo
- Jake McGraw


License (MIT)
-------------

Copyright (c) 2012 Thomas Sileo

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
