# -*- encoding: utf-8 -*-
import logging
import socket
from bakthat.models import Backups, Config
from bakthat.conf import config
import requests
import json

log = logging.getLogger(__name__)


def bakmanager_periodic_backups(conf):
    """Fetch periodic backups info from bakmanager.io API."""
    if conf.get("bakmanager_token"):
        bakmanager_backups_endpoint = conf.get("bakmanager_api", "https://bakmanager.io/api/keys/")
        r = requests.get(bakmanager_backups_endpoint, auth=(conf.get("bakmanager_token"), ""))
        r.raise_for_status()
        for key in r.json().get("_items", []):
            latest_date = key.get("latest", {}).get("date_human")
            line = "{key:20} status: {status:5} interval: {interval_human:6} total: {total_size_human:10}".format(**key)
            line += " latest: {0} ".format(latest_date)
            log.info(line)
    else:
        log.error("No bakmanager_token setting for the current profile.")


def bakmanager_hook(conf, backup_data, key=None):
    """First version of a hook for monitoring periodic backups with BakManager
    (https://bakmanager.io).

    :type conf: dict
    :param conf: Current profile config

    :type backup_data: dict
    :param backup_data: Backup data (size)

    :type key: str
    :param key: Periodic backup identifier
    """
    try:
        if conf.get("bakmanager_token"):
            bakmanager_backups_endpoint = conf.get("bakmanager_api", "https://bakmanager.io/api/backups/")
            bak_backup = {"key": key, "host": socket.gethostname(), "size": backup_data["size"]}
            bak_payload = {"backup":  json.dumps(bak_backup)}
            r = requests.post(bakmanager_backups_endpoint, bak_payload, auth=(conf.get("bakmanager_token"), ""))
            r.raise_for_status()
        else:
            log.error("No bakmanager_token setting for the current profile.")
    except Exception, exc:
        log.error("Error while submitting periodic backup to BakManager.")
        log.exception(exc)


class BakSyncer():
    """Helper to synchronize change on a backup set via a REST API.

    No sensitive information is transmitted except (you should be using https):
    - API user/password
    - a hash (hashlib.sha512) of your access_key concatened with
        your s3_bucket or glacier_vault, to be able to sync multiple
        client with the same configuration stored as metadata for each bakckupyy.

    :type conf: dict
    :param conf: Config (url, username, password)
    """
    def __init__(self, conf=None):
        conf = {} if conf is None else conf
        sync_conf = dict(url=config.get("sync", {}).get("url"),
                         username=config.get("sync", {}).get("username"),
                         password=config.get("sync", {}).get("password"))
        sync_conf.update(conf)

        self.sync_auth = (sync_conf["username"], sync_conf["password"])
        self.api_url = sync_conf["url"]

        self.request_kwargs = dict(auth=self.sync_auth)

        self.request_kwargs["headers"] = {'content-type': 'application/json', 'bakthat-client': socket.gethostname()}

        self.get_resource = lambda x: self.api_url + "/{0}".format(x)

    def register(self):
        """Register/create the current host on the remote server if not already registered."""
        if not Config.get_key("client_id"):
            r_kwargs = self.request_kwargs.copy()
            r = requests.post(self.get_resource("clients"), **r_kwargs)
            if r.status_code == 200:
                client = r.json()
                if client:
                    Config.set_key("client_id", client["_id"])
            else:
                log.error("An error occured during sync: {0}".format(r.text))
        else:
            log.debug("Already registered ({0})".format(Config.get_key("client_id")))

    def sync(self):
        """Draft for implementing bakthat clients (hosts) backups data synchronization.

        Synchronize Bakthat sqlite database via a HTTP POST request.

        Backups are never really deleted from sqlite database, we just update the is_deleted key.

        It sends the last server sync timestamp along with data updated since last sync.
        Then the server return backups that have been updated on the server since last sync.

        On both sides, backups are either created if they don't exists or updated if the incoming version is newer.
        """
        log.debug("Start syncing")

        self.register()

        last_sync_ts = Config.get_key("sync_ts", 0)
        to_insert_in_mongo = [b._data for b in Backups.search(last_updated_gt=last_sync_ts)]
        data = dict(sync_ts=last_sync_ts, new=to_insert_in_mongo)
        r_kwargs = self.request_kwargs.copy()
        log.debug("Initial payload: {0}".format(data))
        r_kwargs.update({"data": json.dumps(data)})
        r = requests.post(self.get_resource("backups/sync"), **r_kwargs)
        if r.status_code != 200:
            log.error("An error occured during sync: {0}".format(r.text))
            return

        log.debug("Sync result: {0}".format(r.json()))
        to_insert_in_bakthat = r.json().get("updated", [])
        sync_ts = r.json().get("sync_ts")
        for newbackup in to_insert_in_bakthat:
            log.debug("Upsert {0}".format(newbackup))
            Backups.upsert(**newbackup)

        Config.set_key("sync_ts", sync_ts)

        log.debug("Sync succcesful")

    def reset_sync(self):
        log.debug("reset sync")
        Config.set_key("sync_ts", 0)
        Config.set_key("client_id", None)

    def sync_auto(self):
        """Trigger sync if autosync is enabled."""
        if config.get("sync", {}).get("auto", False):
            self.sync()
