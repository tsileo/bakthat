.. _bakmanager-integration:

BakManager Integration
======================

.. versionadded:: 0.5.0

`BakManager <https://bakmanager.io>`_ is a monitoring service for periodic backups, it also provides analytics and is tightly integrated with Bakthat.

To monitor your periodic backups using bakthat, you just need to add your API token in your profile settings (located at ~/.bakthat.yml by default).


.. code-block:: yaml

    default:
        bakmanager_token: YOUR_BAKMANAGER_TOKEN
    [...]


Now when you want to monitor backups, you have to specify the periodic backup key with the **-k/--key** parameter, for example:

    $ bakthat backup mysqlbakdir -k sql

That's it, now you can check backups on your `BakManager <https://bakmanager.io>`_ account.

.. note::

    This hook is a first step towards full `BakManager <https://bakmanager.io>`_  integration, the next step is to have **bakthat periodic_backups** command that fetch periodic backups status from BakManager Keys API.
