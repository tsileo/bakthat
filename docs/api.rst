.. _api:

Bakthat API
===========

Bakthat
-------

These functions are called when using bakthat in command line mode and are the foundation of the bakthat module.


.. module:: bakthat

backup
~~~~~~

.. autofunction:: backup

restore
~~~~~~~

.. autofunction:: restore

ls
~~

.. autofunction:: ls

info
~~~~

.. autofunction:: info

show
~~~~

.. autofunction:: show

delete
~~~~~~

.. autofunction:: delete

delete_older_than
~~~~~~~~~~~~~~~~~

.. autofunction:: delete_older_than

rotate_backups
~~~~~~~~~~~~~~

.. autofunction:: rotate_backups


Backends
--------

BakthatBackend
~~~~~~~~~~~~~~

.. autoclass:: bakthat.backends.BakthatBackend
   :members:

GlacierBackend
~~~~~~~~~~~~~~

.. autoclass:: bakthat.backends.GlacierBackend
   :members:

S3Backend
~~~~~~~~~

.. autoclass:: bakthat.backends.S3Backend
   :members:

RotationConfig
~~~~~~~~~~~~~~

.. autoclass:: bakthat.backends.RotationConfig
   :members:

Helper
------

BakHelper
~~~~~~~~~

.. autoclass:: bakthat.helper.BakHelper
   :members:

Sync
----

BakSyncer
~~~~~~~~~

.. autoclass:: bakthat.sync.BakSyncer
   :members:


Utils
-----

.. autofunction:: bakthat.utils.dump_truck_delete_backup

.. autofunction:: bakthat.utils.prepare_backup

.. autofunction:: bakthat.utils.dump_truck_insert_backup

.. autofunction:: bakthat.utils.dump_truck_upsert_backup

.. autofunction:: bakthat.utils.dump_truck_backups_generator

.. autofunction:: bakthat.utils._get_query

.. autofunction:: bakthat.utils._timedelta_total_seconds

.. autofunction:: bakthat.utils._interval_string_to_seconds
