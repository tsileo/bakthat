# -*- encoding: utf-8 -*-
import logging
from datetime import datetime, timedelta
import bakthat
import hashlib
from bakthat.conf import config, dump_truck, DEFAULT_DESTINATION, DEFAULT_LOCATION
import re

log = logging.getLogger(__name__)

def dump_truck_delete_backup(stored_filename):
    """Change status of is_deleted to 1 for the given stored_filename.

    :type stored_filename: str
    :param stored_filename: Filename

    """
    dump_truck.execute("UPDATE backups SET is_deleted = 1, last_updated= {0} \
                    WHERE stored_filename == '{1}'".format(int(datetime.utcnow().strftime("%s")),
                                                        stored_filename))

def prepare_backup(backup):
    """Add some info before actually saving backup data.

    :type backup: dict
    :param backup: Backup data

    """
    backup["last_updated"] = int(datetime.utcnow().strftime("%s"))
    if backup.get("tags", []):
        tags_set = dump_truck.get_var("tags")
        tags_set.update(backup.get("tags"))
        dump_truck.save_var("tags", tags_set)
    return backup

def dump_truck_get_backup(filename, destination="", profile="default"):
    query = _get_query(destination=destination, stored_filename=filename)
    profile_query = _get_profile_query(profile)
    query = "SELECT stored_filename FROM backups \
            WHERE {0} AND {1} ORDER BY backup_date DESC LIMIT 0, 1".format(query, profile_query)
    print query
    backups = dump_truck.execute(query)
    if backups:
        return backups[0]

def dump_truck_insert_backup(backup):
    """Insert backup data into DumpTruck backups table.

    :type backup: dict
    :param backup: Backup data

    """
    backup = prepare_backup(backup)
    dump_truck.insert(backup, "backups")

def dump_truck_upsert_backup(backup):
    """Insert backup data into DumpTruck backups table.

    :type backup: dict
    :param backup: Backup data

    """
    backup = prepare_backup(backup)
    dump_truck.upsert(backup, "backups")

def dump_truck_backups_generator(per=50):
    """Generator for iterating user stored backups.

    :type per: int
    :param per: Number of backups in each DumpTruck (SQLite) request

    """
    cnt = dump_truck.execute("SELECT COUNT(*) FROM backups")[0]["COUNT(*)"]
    for i in range(int(math.ceil(cnt / float(per)))):
        limit = (i * per, (i + 1) * per)
        #for result in dump_truck.execute("SELECT * FROM backups LIMIT {0:d}, {1:d}".format(*limit)):
        #    yield result
        yield dump_truck.execute("SELECT * FROM backups LIMIT {0:d}, {1:d}".format(*limit))

def _get_tags_query(tags):
    if tags:
        tags = "%' OR tags LIKE '%".join(tags)
        return " (tags LIKE '%{0}%')".format(tags)
    return ""

def _get_search_query(query):
    if query:
        return " (stored_filename LIKE '%{0}%' OR filename LIKE '%{0}%')".format(query)
    return ""

def _get_destination_query(destination):
    if destination:
        return " backend == '{0}'".format(destination)
    return ""

def _get_stored_filename_query(stored_filename):
    if stored_filename:
        return " (stored_filename LIKE '{0}%' OR filename LIKE '{0}%')".format(stored_filename)
    return ""

def _get_is_deleted_query(is_deleted):
    if is_deleted:
        return " is_deleted == 1"
    return " is_deleted == 0"

def _get_profile_query(profile):
    if profile:
        profile_conf = config.get(profile)
        if profile_conf:
            s3_hash_key = hashlib.sha512(profile_conf.get("access_key") + \
                                profile_conf.get("s3_bucket")).hexdigest()
            glacier_hash_key = s3_hash_key = hashlib.sha512(profile_conf.get("access_key") + \
                                profile_conf.get("glacier_vault")).hexdigest()
            return " ((backend == 's3' AND backend_hash == '{0}') OR \
                    (backend == 'glacier' AND backend_hash == '{1}'))".format(s3_hash_key,
                                                                        glacier_hash_key)
        else:
            raise Exception("Profile {0} not found.".format(profile))
    return ""

def _get_query(**kwargs):
    """Return the final part of a SQLite query.

    All paramaters are disabled by default.

    :type tags: list of str
    :keyword tags: List of tags

    :type destination: str
    :keyword destination: Destination s3|glacier,
        an empty string disable destination filter

    :type query: query
    :keyword query: Query stored_filename and filename fields
        with LIKE operator.

    :type stored_filename: str
    :keyword stored_filename: find backup by full stored_filename.

    :type is_deleted: bool
    :keyword is_deleted: is_deleted status, 0 by default

    :type profile: str
    :keyword profile: Profile name, empty string to show all profiles.

    :rtype: str
    :return: A str to append after a WHERE
        when making SQLite query.

    """
    tags = kwargs.get("tags", [])
    if isinstance(tags, (unicode, str)):
        tags = tags.split()
    destination = kwargs.get("destination", "")
    query = kwargs.get("query", "")
    stored_filename = kwargs.get("stored_filename", "")
    is_deleted = kwargs.get("is_deleted", 0)
    profile = kwargs.get("profile", "")
    querys = [_get_tags_query(tags),
            _get_destination_query(destination),
            _get_search_query(query),
            _get_stored_filename_query(stored_filename),
            _get_is_deleted_query(is_deleted),
            _get_profile_query(profile)]
    querys = filter(None, querys)
    query = " AND".join(querys)
    log.debug("_get_query: {0}".format(query))
    return query

def _timedelta_total_seconds(td):
    """Python 2.6 backward compatibility function for timedelta.total_seconds.

    :type td: timedelta object
    :param td: timedelta object

    :rtype: float
    :return: The total number of seconds for the given timedelta object.

    """
    if hasattr(timedelta, "total_seconds"):
        return getattr(td, "total_seconds")()

    # Python 2.6 backward compatibility
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / float(10**6)


def _interval_string_to_seconds(interval_string):
    """Convert internal string like 1M, 1Y3M, 3W to seconds.

    :type interval_string: str
    :param interval_string: Interval string like 1M, 1W, 1M3W4h2s... 
        (s => seconds, m => minutes, h => hours, D => days, W => weeks, M => months, Y => Years).

    :rtype: int
    :return: The conversion in seconds of interval_string.

    """
    interval_exc = "Bad interval format for {0}".format(interval_string)
    interval_dict = {"s": 1, "m": 60, "h": 3600, "D": 86400,
                       "W": 7*86400, "M": 30*86400, "Y": 365*86400}

    interval_regex = re.compile("^(?P<num>[0-9]+)(?P<ext>[smhDWMY])")
    seconds = 0

    while interval_string:
        match = interval_regex.match(interval_string)
        if match:
            num, ext = int(match.group("num")), match.group("ext")
            if num > 0 and ext in interval_dict:
                seconds += num * interval_dict[ext]
                interval_string = interval_string[match.end():]
            else:
                raise Exception(interval_exc)
        else:
            raise Exception(interval_exc)
    return seconds
