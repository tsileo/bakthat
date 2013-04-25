.. _bakmanager-integration:

BakManager Integration
======================

.. versionadded:: 0.5.0

`BakManager <https://bakmanager.io>`_ is a monitoring service for periodic backups, it also provides analytics and is tightly integrated with Bakthat.

.. figure::  https://bakamanager-io.s3.amazonaws.com/bakmanager_screen2.jpg
   :align:   center

   `BakManager <https://bakmanager.io>`_ screenshot.

To monitor your periodic backups using bakthat, you just need to add your API token in your profile settings (located at ~/.bakthat.yml by default).


.. code-block:: yaml

    default:
        bakmanager_token: YOUR_BAKMANAGER_TOKEN
    [...]


Now when you want to monitor/setup periodic backups, just define a periodic backup key (the identifier of the backups) with the **-k/--key** parameter: 

    $ bakthat backup mysqlbakdir -k sqldb1

That's it, now you can check backups on your `BakManager <https://bakmanager.io>`_ account and define the interval between each backups.

.. note::

    This hook is a first step towards full `BakManager <https://bakmanager.io>`_  integration, the next step is to have **bakthat periodic_backups** command that fetch periodic backups status from BakManager Keys API.
