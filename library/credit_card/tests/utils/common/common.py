# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
from datetime import datetime, timedelta
import logging
import os

log = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

__name__ = "common"


LOCAL_UTC_OFFSET = 0
DEFAULT_YEAR = 2019
DEFAULT_ADDRESS = "DEFAULT"
DEFAULT_DENOM = "GBP"
DEFAULT_ASSET = "COMMERCIAL_BANK_MONEY"


# TODO: merge simulator and unit methods once contracts can handle tz aware. Simulator must get tz
#  aware timestamps and contracts can't currently handle tz aware properly
def offset_datetime(year, month=None, day=None, hour=0, minute=0, second=0, microsecond=0):
    unoffset_datetime = datetime(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        second=second,
        microsecond=microsecond,
    )
    return unoffset_datetime - timedelta(hours=LOCAL_UTC_OFFSET)


def convert_utc_to_local_schedule(
    year=DEFAULT_YEAR, month=None, day=None, hour=None, minute=None, second=None
):
    """
    Converts a UTC schedule to a non-UTC-schedule, assuming fixed local-UTC offset. Only supports:
    - second, minute, hour, day, month parameters
    - integer schedule parameters and 'last' (i.e. no *)
    - positive and negative integer hour offsets from UTC
    WARNING: Does not validate schedule (e.g. if you try and pass in year and day it will not reject
    despite day being a day of month and no month being specified.
    :param schedule: Dict[str, str], UTC schedule
    :return: Dict[str, str], local utc-adjusted schedule
    """
    schedule = schedule_dict(year, month, day, hour, minute, second)

    if day == "last":
        temp_day = 1
        temp_month = int(month) % 12 + 1
        if temp_month == 1:
            year += 1
        utc_datetime = datetime(
            year=year,
            month=temp_month,
            day=temp_day,
            hour=int(hour),
            minute=int(minute),
            second=int(second),
        )
        utc_datetime = utc_datetime - timedelta(days=1)
    elif not month and not day:
        utc_datetime = datetime(
            year=year,
            month=1,
            day=1,
            hour=int(hour),
            minute=int(minute),
            second=int(second),
        )
    else:
        utc_datetime = datetime(
            year=year,
            month=int(month),
            day=int(day),
            hour=int(hour),
            minute=int(minute),
            second=int(second),
        )

    if LOCAL_UTC_OFFSET < 0:
        local_datetime = utc_datetime + timedelta(hours=-LOCAL_UTC_OFFSET)
    else:
        local_datetime = utc_datetime - timedelta(hours=LOCAL_UTC_OFFSET)

    local_changed_fields = {}

    date_offset_required = LOCAL_UTC_OFFSET != 0

    if date_offset_required:

        if month:
            local_changed_fields["month"] = str(local_datetime.month)

        if day:
            if int((local_datetime + timedelta(days=1)).month) > int(local_datetime.month):
                local_changed_fields["day"] = "last"
            else:
                local_changed_fields["day"] = str(local_datetime.day)

        if hour:
            local_changed_fields["hour"] = str(local_datetime.hour)

        if minute:
            local_changed_fields["minute"] = str(local_datetime.minute)

        if second:
            local_changed_fields["second"] = str(local_datetime.second)

        return local_changed_fields
    else:
        return schedule


def schedule_dict(year, month, day, hour, minute, second):
    schedule_dict = dict()
    if month:
        schedule_dict["month"] = month
    if day:
        schedule_dict["day"] = day
    if hour:
        schedule_dict["hour"] = hour
    if minute:
        schedule_dict["minute"] = minute
    if second:
        schedule_dict["second"] = second
    return schedule_dict


VALID_FORMATS = ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"]


def parse_datetime(text, formats=VALID_FORMATS):
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError("no valid date format found")
