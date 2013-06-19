# encoding: utf-8
import peewee
from datetime import datetime
from bakthat.conf import config, load_config, DATABASE
import hashlib
import json
import sqlite3
import os
import requests
import logging
import uuid

from eve.utils import document_etag


log = logging.getLogger(__name__)
import time
DATABASEDEV = os.path.expanduser("~/.bakthat.sqlitedev{0}".format(time.time()))
database = peewee.SqliteDatabase(DATABASEDEV)
api_root = "http://localhost:2404/api/{0}/".format
api_resource = "http://localhost:2404/api/{0}/{1}/".format


def get_remote_history(model, last_sync=0):
    r = requests.get(api_root('history'),
                     params={"where": json.dumps({"ts": {"$gt": last_sync},
                                                  "model": model})})
    r.raise_for_status()
    return r.json().get("_items", [])


def delete_resource(model, pk, etag, raw_history=None):
    # TODO delete data
    r = requests.delete(api_resource(model, pk),
                        headers={"If-Match": etag})
    r.raise_for_status()
    resp = r.json()
    log.debug(resp)
    if resp.get("status") == "OK":
        del raw_history["id"]
        raw_history["ts"] = int(datetime.utcnow().strftime("%s"))
        post_resource("history", raw_history.get("uuid"), json.dumps(raw_history))
    elif resp.get("status") != "OK":
        log.error("Issue deleting: {0} <{1}>".format(model, pk))
        for issue in resp["issues"]:
            log.error(issue)


def patch_resource(model, pk, update, etag, raw_history=None):
    """ Patch a resource. """
    payload = {"data": update}
    r = requests.patch(api_resource(model, pk),
                       payload,
                       headers={"If-Match": etag})
    r.raise_for_status()
    resp = r.json().get("data")
    log.debug(resp)
    if resp.get("status") == "OK":
        if model != "history" and raw_history is not None:
            # Call post_resource itself for the history
            del raw_history["id"]  # Since we can't rely on autoincrement id, we use uuid
            # We also update the timestamp (ts)
            raw_history["ts"] = int(datetime.utcnow().strftime("%s"))
            post_resource("history", raw_history.get("uuid"), json.dumps(raw_history))
    elif resp.get("status") == "ERR":
        log.error("Issue patching: {0}".format(payload))
        for issue in resp["issues"]:
            log.error(issue)
    elif resp.get("status") != "OK":
        log.error("Issue patching {0}: {1}".format(payload, resp))


def post_resource(model, pk, data, raw_history=None):
    """ Create a resource,
    but verify if it doesn't exist yet before.
    """
    call_url = api_resource(model, pk)
    r = requests.get(call_url)
    if r.status_code == 404:
        payload = {"item": data}
        r = requests.post(api_root(model),
                          payload)
        #try:
        r.raise_for_status()
        resp = r.json().get("item")
        log.debug(resp)
        if resp.get("status") == "OK":
            if model != "history" and raw_history is not None:
                etag = resp.get("etag")
                # Call post_resource itself for the history
                del raw_history["id"]  # Since we can't rely on autoincrement id, we use uuid
                # We also update the timestamp (ts)
                raw_history["ts"] = int(datetime.utcnow().strftime("%s"))
                post_resource("history", raw_history.get("uuid"), json.dumps(raw_history))
                return etag
        elif resp.get("status") == "ERR":
            log.error("Issue posting: {0}".format(payload))
            for issue in resp["issues"]:
                log.error(issue)
        elif resp.get("status") != "OK":
            log.error("Issue posting {0}: {1}".format(payload, resp))
        #except Exception, exc:
        #    log.exception(exc)


def get_resource(model, pk):
    call_url = api_resource(model, pk)
    r = requests.get(call_url)
    r.raise_for_status()
    return r.json()


class JsonField(peewee.CharField):
    """Custom JSON field."""
    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        try:
            return json.loads(value)
        except:
            return value


class BaseModel(peewee.Model):
    class Meta:
        database = database


class SyncedModel(peewee.Model):
    class Meta:
        database = database

    def __repr__(self):
        return "<{0} {1} (sync)>".format(self._meta.name, self._data.get(self.Sync.pk))

    @classmethod
    def create(cls, **attributes):
        if cls._meta.name != "history":
            History.create(data=json.dumps(dict(**attributes)),
                           ts=int(datetime.utcnow().strftime("%s")),
                           action="create",
                           model=cls._meta.name,
                           pk=attributes.get(cls.Sync.pk))
        return super(SyncedModel, cls).create(**attributes)

    def update(self, **update):
        if self._meta.name != "history":
            History.create(data=json.dumps(dict(**update)),
                           ts=int(datetime.utcnow().strftime("%s")),
                           action="update",
                           model=self._meta.name,
                           pk=self._data.get(self.Sync.pk))
        return super(SyncedModel, self).update(**update)

    def delete_instance(self):
        if self._meta.name != "history":
            History.create(data={},
                           ts=int(datetime.utcnow().strftime("%s")),
                           action="delete",
                           model=self._meta.name,
                           pk=self._data.get(self.Sync.pk))
        return super(SyncedModel, self).delete_instance(self)

    @classmethod
    def get_pk(cls, pk):
        try:
            return cls.get(getattr(cls, cls.Sync.pk) == pk)
        except cls.DoesNotExist:
            return None

    @classmethod
    def sync(cls, debug=False):
        # 1. PUSH
        last_sync = Config.get_key("last_dev_eve_sync", 0)
        for history in History.select().where(History.model == cls._meta.name,
                                              History.ts > last_sync):
            print "local history", history
            if history.action == "create":
                etag = post_resource(history.model, history.pk, history.data, raw_history=history._data)
                if etag:
                    ETag.set(history.model, history.pk, etag)
            elif history.action == "update":
                etag = ETag.get_etag(history.model, history.pk)
                patch_resource(history.model, history.pk, history.data, etag, raw_history=history._data)
            elif history.action == "delete":
                etag = ETag.get_etag(history.model, history.pk)
                delete_resource(history.model, history.pk, etag, raw_history=history._data)
        # 2. PULL
        for history in get_remote_history(cls._meta.name, last_sync):
            print "remote history", history
            local = cls.get_pk(history["pk"])
            if history["action"] == "create":
                if not local:
                    print "create from remote"
                    # Create from history data
                    cls.create(**json.loads(history["data"]))
                    # Retrieve ETag from remote API
                    remote = get_resource(history["model"], history["pk"])
                    ETag.set(history["model"], history["pk"], remote["etag"])
            elif history["action"] == "update":
                if local:
                    local.update(**json.loads(history["data"]))
                    # Retrieve ETag from remote API
                    remote = get_resource(history["model"], history["pk"])
                    ETag.set(history["model"], history["pk"], remote["etag"])
                else:
                    print "item doesn't exists !"
            elif history["action"] == "delete":
                if local:
                    local.delete_instance()
                else:
                    print "item doesn't exists !"

        Config.set_key('last_dev_eve_sync', int(datetime.utcnow().strftime("%s")))
        # Faire l'appel a eve
        # ne pas oublier d'updater ETag

        # TODO cleaner le ETag model
        # TODO gerer la derniere date de sync
        # TODO sync ACK/confirmation
        # TODO => eve-client ?
        # TODO => peewee-eve-sync
        # TODO => tampon/buffer au cas ou API pas disponible
        # TODO => Ajouter des if debug: partout
        # TODO => tester le pk dans Meta au lieu de Sync
        return


class History(BaseModel):
    """History for sync."""
    data = JsonField()
    ts = peewee.IntegerField(index=True)
    action = peewee.CharField(index=True)
    model = peewee.CharField(index=True)
    pk = peewee.CharField(index=True)
    uuid = peewee.CharField(default=uuid.uuid4())

    def __repr__(self):
        return "<History: {model}/{action}/{uuid}>".format(**self._data)

    class Meta:
        db_table = 'history'


class Backups(SyncedModel):
    """Backups Model."""
    backend = peewee.CharField(index=True)
    backend_hash = peewee.CharField(index=True, null=True)
    backup_date = peewee.IntegerField(index=True)
    filename = peewee.TextField(index=True)
    is_deleted = peewee.BooleanField()
    last_updated = peewee.IntegerField()
    metadata = JsonField()
    size = peewee.IntegerField()
    stored_filename = peewee.TextField(index=True, unique=True)
    tags = peewee.CharField()

    @classmethod
    def match_filename(cls, filename, destination, **kwargs):
        conf = config
        if kwargs.get("config"):
            conf = load_config(kwargs.get("config"))

        profile = conf.get(kwargs.get("profile", "default"))

        s3_key = hashlib.sha512(profile.get("access_key") +
                                profile.get("s3_bucket")).hexdigest()
        glacier_key = hashlib.sha512(profile.get("access_key") +
                                     profile.get("glacier_vault")).hexdigest()

        try:
            fquery = "{0}*".format(filename)
            query = Backups.select().where(Backups.filename % fquery |
                                           Backups.stored_filename % fquery,
                                           Backups.backend == destination,
                                           Backups.backend_hash << [s3_key, glacier_key])
            query = query.order_by(Backups.backup_date.desc())
            return query.get()
        except Backups.DoesNotExist:
            return

    @classmethod
    def search(cls, query="", destination="", **kwargs):
        conf = config
        if kwargs.get("config"):
            conf = load_config(kwargs.get("config"))

        if not destination:
            destination = ["s3", "glacier"]
        if isinstance(destination, (str, unicode)):
            destination = [destination]

        query = "*{0}*".format(query)
        wheres = []

        if kwargs.get("profile"):
            profile = conf.get(kwargs.get("profile"))

            s3_key = hashlib.sha512(profile.get("access_key") +
                                    profile.get("s3_bucket")).hexdigest()
            glacier_key = hashlib.sha512(profile.get("access_key") +
                                         profile.get("glacier_vault")).hexdigest()

            wheres.append(Backups.backend_hash << [s3_key, glacier_key])

        wheres.append(Backups.filename % query |
                      Backups.stored_filename % query)
        wheres.append(Backups.backend << destination)
        wheres.append(Backups.is_deleted == False)

        older_than = kwargs.get("older_than")
        if older_than:
            wheres.append(Backups.backup_date < older_than)

        backup_date = kwargs.get("backup_date")
        if backup_date:
            wheres.append(Backups.backup_date == backup_date)

        last_updated_gt = kwargs.get("last_updated_gt")
        if last_updated_gt:
            wheres.append(Backups.last_updated >= last_updated_gt)

        tags = kwargs.get("tags", [])
        if tags:
            if isinstance(tags, (str, unicode)):
                tags = tags.split()
            tags_query = ["Backups.tags % '*{0}*'".format(tag) for tag in tags]
            tags_query = eval("({0})".format(" and ".join(tags_query)))
            wheres.append(tags_query)

        return Backups.select().where(*wheres).order_by(Backups.last_updated.desc())

    def set_deleted(self):
        self.is_deleted = True
        self.last_updated = int(datetime.utcnow().strftime("%s"))
        self.save()

    def is_encrypted(self):
        return self.stored_filename.endswith(".enc") or self.metadata.get("is_enc")

    def is_gzipped(self):
        return self.metadata.get("is_gzipped")

    @classmethod
    def upsert(cls, **backup):
        q = Backups.select()
        q = q.where(Backups.stored_filename == backup.get("stored_filename"))
        if q.count():
            del backup["stored_filename"]
            Backups.update(**backup).where(Backups.stored_filename == backup.get("stored_filename")).execute()
        else:
            Backups.create(**backup)

    class Meta:
        db_table = 'backups'

    class Sync:
        pk = 'stored_filename'


class Config(BaseModel):
    """key => value config store."""
    key = peewee.CharField(index=True, unique=True)
    value = JsonField()

    @classmethod
    def get_key(self, key, default=None):
        try:
            return Config.get(Config.key == key).value
        except Config.DoesNotExist:
            return default

    @classmethod
    def set_key(self, key, value=None):
        q = Config.select().where(Config.key == key)
        if q.count():
            Config.update(value=value).where(Config.key == key).execute()
        else:
            Config.create(key=key, value=value)

    class Meta:
        db_table = 'config'


class ETag(BaseModel):
    """key => value config store."""
    pk = peewee.CharField(index=True, unique=True)
    etag = peewee.CharField()
    model = peewee.CharField()

    @classmethod
    def get_etag(self, model, pk, default=None):
        try:
            return ETag.get(ETag.model == model,
                            ETag.pk == pk).etag
        except ETag.DoesNotExist:
            return default

    @classmethod
    def set(self, model, pk, etag):
        q = ETag.select().where(ETag.model == model,
                                ETag.pk == pk)
        if q.count():
            ETag.update(etag=etag).where(ETag.model == model,
                                         ETag.pk == pk).execute()
        else:
            ETag.create(model=model, pk=pk, etag=etag)

    class Meta:
        db_table = 'etag'


class Inventory(SyncedModel):
    """Filename => archive_id mapping for glacier archives."""
    archive_id = peewee.CharField(index=True, unique=True)
    filename = peewee.CharField(index=True)

    @classmethod
    def get_archive_id(self, filename):
        return Inventory.get(Inventory.filename == filename).archive_id

    class Meta:
        db_table = 'inventory'

    class Sync:
        pk = 'filename'


class Jobs(SyncedModel):
    """filename => job_id mapping for glacier archives."""
    filename = peewee.CharField(index=True)
    job_id = peewee.CharField()

    @classmethod
    def get_job_id(cls, filename):
        """Try to retrieve the job id for a filename.

        :type filename: str
        :param filename: Filename

        :rtype: str
        :return: Job Id for the given filename
        """
        try:
            return Jobs.get(Jobs.filename == filename).job_id
        except Jobs.DoesNotExist:
            return

    @classmethod
    def update_job_id(cls, filename, job_id):
        """Update job_id for the given filename.

        :type filename: str
        :param filename: Filename

        :type job_id: str
        :param job_id: New job_id

        :return: None
        """
        q = Jobs.select().where(Jobs.filename == filename)
        if q.count():
            Jobs.update(job_id=job_id).where(Jobs.filename == filename).execute()
        else:
            Jobs.create(filename=filename, job_id=job_id)

    class Meta:
        db_table = 'jobs'


for table in [Backups, Jobs, Inventory, Config, History, ETag]:
    if not table.table_exists():
        table.create_table()

"""
print "ok"
Backups.create(**{"backend": "s3", 
      "backend_hash": "bf58b225bf3fe29a94d1df0e5ca4533fd29cc9ed98a733b98915180dfea2059e5e84178cd6ac2c543dec5bc6e8a6c2a7d5bd6418490a12ff86f6f9f66eec9fcf", 
      "backup_date": 1369655146,
      "filename": "ooomg", 
      "is_deleted": False,
      "last_updated": 1369655146, 
      "metadata": {
        "client": "tomt0m", 
        "is_enc": False
      }, 
      "size": 205, 
      "stored_filename": "ooomg.20130527134546.tgz", 
      "tags": "",})
import time
time.sleep(1)"""
print
print [h._data for h in History.select()]
#print Backups.get_pk('ooomg.20130527134546.tgz')
print Backups.sync()
time.sleep(0.5)
print [h._data for h in History.select()]