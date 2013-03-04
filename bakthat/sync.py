# -*- encoding: utf-8 -*-
import logging
import hashlib
import bakthat
import socket
from bakthat.conf import (config, dump_truck,
                        DEFAULT_DESTINATION, DEFAULT_LOCATION)
from bakthat.utils import dump_truck_backups_generator, dump_truck_upsert_backup
from bakthat.backends import BakthatBackend

try:
    import requests
except ImportError, ie:
    raise Exception("You must install requests module in order to use sync.")
import json

log = logging.getLogger(__name__)


class BakSyncer(BakthatBackend):
    """Helper to synchronize change on a backup set via a REST API.

    No sensitive information is transmitted except (you should be using https):
    - API user/password
    - a hash (hashlib.sha512) of your access_key concatened with 
        your s3_bucket and glacier_vault, to be able to sync multiple
        client with the same configuration.

    :type api_url: str
    :param api_url: Base API URL

    :type auth: tuple
    :param auth: A tuple/list with credentials (username, password)
    """
    def __init__(self, api_url, auth=None, **kwargs):
        conf = kwargs.get("conf")
        BakthatBackend.__init__(self, conf, extra_conf=["glacier_vault", "s3_bucket"])

        # We generate the hash of the access key, to be able to sync multiple host with the same AWS config
        aws_config_hash = self.conf["access_key"] + self.conf["glacier_vault"] + self.conf["s3_bucket"]
        hashws = hashlib.sha512(aws_config_hash).hexdigest()

        self.api_url = api_url
        self.auth = auth
        self.request_kwargs = {}
        if self.auth:
            self.request_kwargs["auth"] = self.auth

        self.request_kwargs["headers"] = {'content-type': 'application/json',
                                        'bakthat-key': hashws,
                                        'bakthat-client': socket.gethostname()}


        self.get_resource = lambda x: self.api_url + "/{0}".format(x)

    def register(self):
        """Register/create the current host on the remote server if not already registered."""
        if not dump_truck.get_var("client_id"):
            r_kwargs = self.request_kwargs.copy()
            r = requests.post(self.get_resource("clients"), **r_kwargs)
            if r.status_code == 200:
                client = r.json()
                if client:
                    dump_truck.save_var("client_id", client["_id"])
            else:
                log.error("An error occured during sync: {0}".format(r.text))
        else:
            log.debug("Already registered ({0})".format(dump_truck.get_var("client_id")))

    def sync(self):
        """Draft for implementing bakthat clients (hosts) backups data synchronization.

        Synchronize Bakthat sqlite database via a HTTP POST request.

        Backups are never really deleted from sqlite database, we just update the is_deleted key.
        
        It sends the last server sync timestamp along with data updated since last sync.
        Then the server return backups that have been updated on the server since last sync.
        
        Both side (bakthat and the sync server) make upserts of the latest data avaible:
        - if it doesn't exist yet, it will be created.
        - if it has been modified (e.g deleted, since it's the only action we can take) we update it.
        """
        log.debug("Start syncing")

        self.register()
        
        last_sync_ts = dump_truck.get_var("sync_ts")
        to_insert_in_mongo = dump_truck.execute("SELECT stored_filename, last_updated FROM backups WHERE last_updated > {0:d}".format(last_sync_ts))
        data = dict(sync_ts=last_sync_ts, to_insert_in_mongo=to_insert_in_mongo)
        r_kwargs = self.request_kwargs.copy()
        log.debug("Initial payload: {0}".format(data))
        r_kwargs.update({"data": json.dumps(data)})
        r = requests.post(self.get_resource("backups/sync/status"), **r_kwargs)
        if r.status_code != 200:
            log.error("An error occured during sync: {0}".format(r.text))
            return

        log.debug("Sync result: {0}".format(r.json()))
        to_insert_in_bakthat = r.json().get("to_insert_in_bakthat")
        sync_ts = r.json().get("sync_ts")
        for newbackup in to_insert_in_bakthat:
            log.debug("Upsert {0}".format(newbackup))
            dump_truck_upsert_backup(newbackup)

        dump_truck.save_var("sync_ts", sync_ts)

        log.debug("Sync succcesful")
