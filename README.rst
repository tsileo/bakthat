=======
Bakthat
=======

Compress, encrypt (symmetric encryption) and upload files directly to Amazon S3 in a single command. Can also be used as a python module.

While navigating directories, I was tired of saying myself I should backup these #?!!* small files/directories.
Since I didn't found any solution that allows me to perform quickly encrypted backup on Amazon S3 from command-line, I wrote bakthat !

Here are some features:

* Hold everything in `StringIO <http://docs.python.org/library/stringio.html>`_ Objects
* Compress with `tarfile <http://docs.python.org/library/tarfile.html>`_
* Encrypt with `beefish <http://pypi.python.org/pypi/beefish>`_
* Upload/download to S3 with `boto <http://pypi.python.org/pypi/boto>`_

You can restore backups **with** or **without** bakthat, you just have to download the backup, decrypt it with `Beefish <http://pypi.python.org/pypi/beefish>`_ command-line tool and untar it.


Overview
========

::

    $ cd /dir/i/want/to/bak
    $ bakthat backup
    INFO: Backing up /dir/i/want/to/bak
    Password:
    $

    $ bakthat restore -f bak
    INFO: Restoring gene20120928.tgz.enc
    Password: 
    $

    $ bakthat ls
    INFO: S3 Bucket: bakthattest
    INFO: bak20120928.tgz.enc


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


Backup
------

::

    $ cd /dir/i/want/to/bak
    $ bakthat backup
    or
    $ bakthat backup -f /dir/i/want/to/bak

    you can also backup a single file
    $ bakthat backup -f /home/thomas/mysuperfile.txt


Restore
-------

You can restore the latest version of a backup just by specifying the begining of the filename.

::

    $ mo2s3 restore --f bak

    if you want to restore an older version
    $ mo2s3 restore --f bak20120927
    or
    $ mo2s3 restore --f bak20120927.tgz.enc


List
----

::

    $ bakthat ls


As a module
===========

::

    import bakthat
    aws_conf = {"access_key":"", "secret_key":"", "bucket": ""}

    bakthat.backup("/dir/i/wanto/bak", conf=aws_conf)

    # or if you want to have generated the configuration file with "bakthat configure"
    # and want to use this file:
    bakthat.backup("/dir/i/wanto/bak")

    # you can optionally pass a custom logger
    bakthat.backup("/dir/i/wanto/bak", logger=my_logger_instance, conf=aws_conf)

    # restore in the current working directory
    bakthat.restore("bak", logger=my_logger_instance, conf=aws_conf)


License (MIT)
=============

Copyright (c) 2012 Thomas Sileo

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.