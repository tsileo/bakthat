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


Event Hooks
~~~~~~~~~~~

.. versionadded:: 0.6.0

You can configure hook to be executed on the following events:

* before_backup
* on_backup
* before_restore
* on_restore
* before_delete
* on_delete
* before_delete_older_than
* on_delete_older_than
* before_rotate_backups
* on_rotate_backups

So, **before_** events are executed at the beginning of the action, and **on_** events are executed just before the end.

For each action, a **session_id** (an uuid4) is assigned, so you can match up **before_** and **on_** events.

Every callback receive the session_id as first argument, and for **on_** callbacks, you can retrieve the result of the function, most of the time a Backup object or a list of Backup object, depending of the context.

.. code-block:: python

    from bakthat import backup, events

    def before_backup_callback(session_id):
        print session_id, "before_backup"

    def on_backup_callback(session_id, backup):
        print session_id, "on_backup", backup

    events.before_backup += before_backup_callback
    events.on_backup += on_backup_callback

    bakthat.backup("/home/thomas/mydir")


Bakthat makes use of `Events <https://github.com/nicolaiarocci/events>`_ to handle all the "event things".

Plugins
-------

.. versionadded:: 0.6.0

You can create plugins to extend bakthat features, all you need to do is to subclass ``bakthat.plugin.Plugin`` and implement an ``activate`` (and optionally ``deactivate``, executed just before exiting) method.

The ``activate`` and ``deactivate`` method is called only once. ``activate`` is called when the plugin is initialized, and ``deactivate`` (you can see it like a cleanup function) is called at exit.

.. note::

    For now, you can create new command yet, maybe in the future.


By default, plugins are stored in **~/.bakthat_plugins/** by default, but you can change the plugins location by setting the ``plugins_dir`` setting.

.. code-block:: yaml

    default:
      plugins_dir: /home/thomas/.bakthat_plugins


And to enable plugins, add it to the ``plugins`` array:

.. code-block:: yaml

    default:
      plugins: [test_plugin.TestPlugin, filename.MyPlugin]


You can access **raw profile configuration** using ``self.conf``, and **bakthat logger** using ``self.log`` (e.g. ``self.log.info("hello")``) and in any methods.
You can also hook events directly on ``self``, like ``self.on_backup += mycallback``.

Your First Plugin
~~~~~~~~~~~~~~~~~

Here is a basic plugin example, a ``TimerPlugin`` in **test_plugin.py**:

.. code-block:: python

    import time
    from bakthat.plugin import Plugin

    class TestPlugin(Plugin):
        def activate(self):
            self.start = {}
            self.stop = {}
            self.before_backup += self.before_backup_callback
            self.on_backup += self.on_backup_callback

        def before_backup_callback(self, session_id):
            self.start[session_id] = time.time()
            self.log.info("before_backup {0}".format(session_id))

        def on_backup_callback(self, session_id, backup):
            self.stop[session_id] = time.time()
            self.log.info("on_backup {0} {1}".format(session_id, backup))
            self.log.info("Job duration: {0}s".format(self.stop[session_id] - self.start[session_id]))


Now, we can enable it:

.. code-block:: yaml

    default:
      plugins: [test_plugin.TestPlugin]


Finally, we can check that our plugin is actually working:

::

    $ bakthat backup mydir
    before_backup 4028dfc7-7a17-4a99-b3fe-88f6e4879bda
    Backing up /home/thomas/mydir
    Password (blank to disable encryption): 
    Compressing...
    Uploading...
    Upload completion: 0%
    Upload completion: 100%
    Upload completion: 0%
    Upload completion: 100%
    on_backup 4028dfc7-7a17-4a99-b3fe-88f6e4879bda <Backup: mydir.20130604191055.tgz>
    Job duration: 4.34407806396s

Monkey Patching
~~~~~~~~~~~~~~~

With plugin, you have the ability to extend or modify everything in the ``activate function``.

Here is an example, which update the ``Backups`` model at runtime:

.. code-block:: python

    from bakthat.plugin import Plugin
    from bakthat.models import Backups


    class MyBackups(Backups):
        @classmethod
        def my_custom_method(self):
            return True


    class ChangeModelPlugin(Plugin):
        """ A basic plugin implementation. """
        def activate(self):
            global Backups
            self.log.info("Replace Backups")
            Backups = MyBackups


More on event hooks
~~~~~~~~~~~~~~~~~~~

See **Event Hooks** for more informations and `Events <https://github.com/nicolaiarocci/events>`_ documentation.


Helpers
-------

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

.. seealso::

    You can also check out a `MongoDB backup script example here <http://thomassileo.com/blog/2013/03/21/backing-up-mongodb-to-amazon-glacier-slash-s3-with-python-using-sh-and-bakthat/>`_.

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


.. _keyvalue:

KeyValue
~~~~~~~~

.. versionadded:: 0.4.5

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


Accessing bakthat SQLite database
---------------------------------

Since bakthat stores custom backups metadata (see :ref:`stored-metadata`), you can execute custom SQL query.