.. _developer_guide:

Developer's Guide
=================

Work in progress.

As a module
-----------

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
