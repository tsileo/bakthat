.. _developer_guide:

Developer's Guide
=================

Work in progress.

As a module
-----------

.. code-block:: python

    import bakthat
    aws_conf = {"access_key":"", "secret_key":"", "s3_bucket": "", "glacier_vault": ""}

    bakthat.backup("/dir/i/wanto/bak", conf=aws_conf)
    # return {'stored_filename': 'bak20130222171513.tgz', 'size': 154, 'metadata': {'is_enc': False}, 'filename': 'bak'}

    bakthat.backup("/dir/i/wanto/bak", conf=aws_conf, destination="glacier")

    # or if you want to have generated the configuration file with "bakthat configure"
    # and want to use this file:
    bakthat.backup("/dir/i/wanto/bak")

    bakthat.ls()

    # restore in the current working directory
    bakthat.restore("bak", conf=aws_conf)
