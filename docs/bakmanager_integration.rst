.. _bakmanager-integration:

BakManager Integration
======================

.. versionadded:: 0.5.0

`BakManager <https://bakmanager.io>`_ is a monitoring service for periodic backups that notify you when a backup is not performed. It doesn't store your backups, just the key, the size and the host it comes from.

It also provides analytics and is tightly integrated with Bakthat.

.. figure::  https://bakamanager-io.s3.amazonaws.com/bakmanager_screen2.jpg
   :align:   center


Monitor your backups
--------------------

To monitor your periodic backups using bakthat, you just need to add your API token in your profile settings (located at ~/.bakthat.yml by default).

.. code-block:: yaml

    default:
        bakmanager_token: YOUR_BAKMANAGER_TOKEN
    [...]


Now when you want to monitor/setup periodic backups, just define a periodic backup key (the identifier of the backups) with the ``-k``/``--key`` parameter: 

.. code-block:: console

    $ bakthat backup mysqlbakdir -k sqldb1


That's it, now you can check your backups on your `BakManager <https://bakmanager.io>`_ account and define the interval between each backups.


Periodic backups status
-----------------------

.. versionadded:: 0.5.1

Bakthat makes use of `BakManager API <https://bakmanager.io/documentation#api-docs>`_ to let you check your periodic backups status directly from bakthat without leaving the command line.

.. code-block:: console

    $ bakthat periodic_backups
    myhost_mysql          status: LATE  interval: 2D     total: 2.7 MB     latest: 2013/05/01 11:40:31 
    myhost_mongodb        status: OK    interval: 1D     total: 4.6 GB     latest: 2013/05/01 14:31:27

