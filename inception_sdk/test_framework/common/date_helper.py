# standard libs
from datetime import datetime, timezone
from dateutil import parser
from dateutil.relativedelta import relativedelta


def extract_date(
    date_entry: str | dict[str, str | dict[str, str]] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> datetime:
    """
    Extract date from a parsed yaml object.
    :param date_entry: If string, this is expected to be 'start' or 'end', which correspond to the
     corresponding start and end parameter dates. Otherwise, it is parsed into a datetime. If dict,
     this can contain:
     - standard datetime kwargs (e.g. year, month, day etc). If these aren't specified,
     or if the date_dict isn't passed in, datetime.now() is used, with UTC timezone
     - delta, itself a dictionary whose kwargs are fed to relativedelta and added to the
     standard datetime, or datetime.now() with UTC timezone
    :param start: the datetime to use if the date_entry string is 'start'. If populated relative
     dates will be calculated from this date
    :param end: the datetime to use if the date_entry string is 'end'
    """

    delta = None
    date_entry = date_entry or {}

    if isinstance(date_entry, str):
        if date_entry == "start":
            return start
        elif date_entry == "end":
            return end
        else:
            return parser.parse(date_entry)
    else:
        date_entry = date_entry.copy()
        if date_entry.get("delta"):
            delta = date_entry.pop("delta")

        # date_entry could be an empty dict
        if date_entry:
            date = datetime(**date_entry, tzinfo=timezone.utc)
        else:
            date = start if start else datetime.now(tz=timezone.utc)
        if delta:
            date += relativedelta(**delta)

        return date
