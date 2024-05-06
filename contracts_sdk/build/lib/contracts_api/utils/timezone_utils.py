from datetime import datetime
from zoneinfo import ZoneInfo

from .exceptions import InvalidSmartContractError


def validate_dateime_is_timezone_aware(datetime: datetime, field_path: str, class_type: str):
    if datetime.tzinfo is None or datetime.tzinfo.utcoffset(datetime) is None:
        raise InvalidSmartContractError(f"'{field_path}' of {class_type} is not timezone aware.")


def validate_timezone_is_utc(datetime: datetime, field_path: str, class_type: str):
    validate_datetime_has_given_timezone(
        datetime,
        field_path,
        class_type,
        ZoneInfo("UTC"),
    )
    return datetime


def validate_and_convert_timezone_to_utc(
    datetime: datetime, field_path: str, class_type: str, events_timezone: ZoneInfo
):
    validate_datetime_has_given_timezone(
        datetime,
        field_path,
        class_type,
        events_timezone,
    )
    return datetime.astimezone(tz=ZoneInfo("UTC"))


def validate_datetime_has_given_timezone(
    datetime: datetime, field_path: str, class_type: str, timezone: ZoneInfo
):
    validate_dateime_is_timezone_aware(datetime, field_path, class_type)
    if not isinstance(datetime.tzinfo, ZoneInfo):
        raise InvalidSmartContractError(
            f"'{field_path}' of {class_type} must have timezone of type ZoneInfo, "
            f"currently {type(datetime.tzinfo)}."
        )
    if not (datetime.tzinfo == timezone):
        raise InvalidSmartContractError(
            f"'{field_path}' of {class_type} must have timezone {timezone}, "
            f"currently {datetime.tzinfo}."
        )
