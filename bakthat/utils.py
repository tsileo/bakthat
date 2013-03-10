# -*- encoding: utf-8 -*-
import logging
from datetime import timedelta
import re

log = logging.getLogger(__name__)


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
