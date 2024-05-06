from functools import lru_cache

from .enums import DefinedDateTime
from .....utils import exceptions, symbols, types_utils
from typing import Optional, Union


class Override:
    def __init__(
        self,
        *,
        year: Optional[int] = None,
        month: Optional[int] = None,
        day: Optional[int] = None,
        hour: Optional[int] = None,
        minute: Optional[int] = None,
        second: Optional[int] = None,
    ):
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self._validate_attributes()

    def __repr__(self):
        return "Override"

    def _validate_attributes(self):
        args_types = {
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "hour": self.hour,
            "minute": self.minute,
            "second": self.second,
        }
        if not any(arg is not None for arg in args_types.values()):
            raise exceptions.InvalidSmartContractError(
                f"{self} object needs to be populated with at least one attribute."
            )

        for name, value in args_types.items():
            types_utils.validate_type(
                value, int, hint="int", is_optional=True, prefix=f"Override.{name}"
            )

        if (
            (self.year is not None and self.year < 0)
            or (self.month is not None and (self.month <= 0 or self.month > 12))
            or (self.day is not None and (self.day <= 0 or self.day > 31))
            or (self.hour is not None and (self.hour < 0 or self.hour > 23))
            or (self.minute is not None and (self.minute < 0 or self.minute > 59))
            or (self.second is not None and (self.second < 0 or self.second > 59))
        ):
            raise exceptions.InvalidSmartContractError(f"Values of {self} object are out of range.")

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="year",
                type="Optional[int]",
                docstring="Override the year value (4-digit year).",
            ),
            types_utils.ValueSpec(
                name="month", type="Optional[int]", docstring="Override the month value (1-12)."
            ),
            types_utils.ValueSpec(
                name="day", type="Optional[int]", docstring="Override the day value (1-31)."
            ),
            types_utils.ValueSpec(
                name="hour", type="Optional[int]", docstring="Override the hour value (0-23)."
            ),
            types_utils.ValueSpec(
                name="minute", type="Optional[int]", docstring="Override the minute value (0-59)."
            ),
            types_utils.ValueSpec(
                name="second", type="Optional[int]", docstring="Override the second value (0-59)."
            ),
        ]

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="Override",
            docstring="""
                Override any part of a datetime in order to define an observation or interval
                parameter. This can be used in conjunction with [Shift](#classes-Shift)
                inside the [RelativeDateTime](#classes-RelativeDateTime) object.
                If any time attributes are overridden then the others will default to 0, otherwise
                the time will not be modified at all.
                Be aware that it is not possible to validate a date at parse time, in the event of
                an invalid date being reached (e.g. overriding day to 31 when the month is 2) an
                `InvalidSmartContractError` will be raised.
            """,  # noqa: E501
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),
            ),
        )


class Shift:
    def __init__(
        self,
        *,
        years: Optional[int] = None,
        months: Optional[int] = None,
        days: Optional[int] = None,
        hours: Optional[int] = None,
        minutes: Optional[int] = None,
        seconds: Optional[int] = None,
    ):
        self.years = years
        self.months = months
        self.days = days
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds
        self._validate_attributes()

    def __repr__(self):
        return "Shift"

    def _validate_attributes(self):
        args_types = {
            "years": self.years,
            "months": self.months,
            "days": self.days,
            "hours": self.hours,
            "minutes": self.minutes,
            "seconds": self.seconds,
        }
        if not any(arg is not None for arg in args_types.values()):
            raise exceptions.InvalidSmartContractError(
                f"{self} object needs to be populated with at least one attribute."
            )

        for name, value in args_types.items():
            types_utils.validate_type(
                value, int, hint="int", is_optional=True, prefix=f"Shift.{name}"
            )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="years", type="Optional[int]", docstring="Shift by specified number of years."
            ),
            types_utils.ValueSpec(
                name="months",
                type="Optional[int]",
                docstring="Shift by specified number of months.",
            ),
            types_utils.ValueSpec(
                name="days", type="Optional[int]", docstring="Shift by specified number of days."
            ),
            types_utils.ValueSpec(
                name="hours", type="Optional[int]", docstring="Shift by specified number of hours."
            ),
            types_utils.ValueSpec(
                name="minutes",
                type="Optional[int]",
                docstring="Shift by specified number of minutes.",
            ),
            types_utils.ValueSpec(
                name="seconds",
                type="Optional[int]",
                docstring="Shift by specified number of seconds.",
            ),
        ]

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        go_link = "[Golang `time` package](https://golang.org/pkg/time/#Date)"

        return types_utils.ClassSpec(
            name="Shift",
            docstring=f"""
                Shift a datetime by a specified amount of time. Can be used in conjunction with
                Override inside the RelativeDateTime object. Note this utilises the
                {go_link} so will normalise dates (e.g. shifting forward a month from
                October 31st will result in overflowing to December 1st) and apply all date shift
                parameters as a single operation. Time shift parameters will be applied in a
                separate single operation after the date shift has been applied. Note that all
                fields can be specified by a positive or negative integer, implying forwards and
                backwards shifts respectively.
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),
            ),
        )


class Next:
    def __init__(
        self,
        *,
        month: Optional[int] = None,
        day: int = None,
        hour: Optional[int] = None,
        minute: Optional[int] = None,
        second: Optional[int] = None,
    ):
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self._validate_attributes()

    def __repr__(self):
        return "Next"

    def _validate_attributes(self):
        args_types = {
            "month": self.month,
            "hour": self.hour,
            "minute": self.minute,
            "second": self.second,
        }

        types_utils.validate_type(self.day, int, hint="int", prefix="Next.day")

        for name, value in args_types.items():
            types_utils.validate_type(
                value, int, hint="int", is_optional=True, prefix=f"Next.{name}"
            )

        if (
            (self.month is not None and (self.month <= 0 or self.month > 12))
            or (self.day is not None and (self.day <= 0 or self.day > 31))
            or (self.hour is not None and (self.hour < 0 or self.hour > 23))
            or (self.minute is not None and (self.minute < 0 or self.minute > 59))
            or (self.second is not None and (self.second < 0 or self.second > 59))
        ):
            raise exceptions.InvalidSmartContractError("Values of Next object are out of range.")

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="month",
                type="Optional[int]",
                docstring="Shift datetime to the next given month (1-12).",
            ),
            types_utils.ValueSpec(
                name="day", type="int", docstring="Shift datetime to the next given day (1-31)."
            ),
            types_utils.ValueSpec(
                name="hour",
                type="Optional[int]",
                docstring="Shift datetime to the next given hour (0-23).",
            ),
            types_utils.ValueSpec(
                name="minute",
                type="Optional[int]",
                docstring="Shift datetime to the next given minute (0-59).",
            ),
            types_utils.ValueSpec(
                name="second",
                type="Optional[int]",
                docstring="Shift datetime to the next given second (0-59).",
            ),
        ]

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="Next",
            docstring="""
                Alter the datetime by shifting to the next instance of the given parameter. This
                object must include the `day` parameter, but all others are optional.
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),
            ),
        )


class Previous:
    def __init__(
        self,
        *,
        month: Optional[int] = None,
        day: int = None,
        hour: Optional[int] = None,
        minute: Optional[int] = None,
        second: Optional[int] = None,
    ):
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self._validate_attributes()

    def __repr__(self):
        return "Previous"

    def _validate_attributes(self):
        args_types = {
            "month": self.month,
            "hour": self.hour,
            "minute": self.minute,
            "second": self.second,
        }

        types_utils.validate_type(self.day, int, hint="int", prefix="Previous.day")

        for name, value in args_types.items():
            types_utils.validate_type(
                value, int, hint="int", is_optional=True, prefix=f"Previous.{name}"
            )

        if (
            (self.month is not None and (self.month <= 0 or self.month > 12))
            or (self.day is not None and (self.day <= 0 or self.day > 31))
            or (self.hour is not None and (self.hour < 0 or self.hour > 23))
            or (self.minute is not None and (self.minute < 0 or self.minute > 59))
            or (self.second is not None and (self.second < 0 or self.second > 59))
        ):
            raise exceptions.InvalidSmartContractError(
                "Values of Previous object are out of range."
            )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="month",
                type="Optional[int]",
                docstring="Shift datetime to the previous given month (1-12).",
            ),
            types_utils.ValueSpec(
                name="day", type="int", docstring="Shift datetime to the previous given day (1-31)."
            ),
            types_utils.ValueSpec(
                name="hour",
                type="Optional[int]",
                docstring="Shift datetime to the previous given hour (0-23).",
            ),
            types_utils.ValueSpec(
                name="minute",
                type="Optional[int]",
                docstring="Shift datetime to the previous given minute (0-59).",
            ),
            types_utils.ValueSpec(
                name="second",
                type="Optional[int]",
                docstring="Shift datetime to the previous given second (0-59).",
            ),
        ]

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="Previous",
            docstring="",
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="""
                    Alter the datetime by shifting to the previous instance of the given parameter.
                    This object must include the `day` parameter, but all others are optional.
                """,
                args=cls._public_attributes(language_code),
            ),
        )


class RelativeDateTime:
    def __init__(
        self,
        *,
        shift: Optional[Shift] = None,
        find: Optional[Union[Next, Previous, Override]] = None,
        origin: DefinedDateTime = None,
    ):
        self.shift = shift
        self.find = find
        self.origin = origin
        self._validate_attributes()

    def __repr__(self):
        return "RelativeDateTime"

    def _validate_attributes(self):
        types_utils.validate_type(
            self.shift, Shift, hint="Shift", is_optional=True, prefix="RelativeDateTime.shift"
        )

        types_utils.validate_type(
            self.find,
            (Next, Previous, Override),
            hint="Union[Next, Previous, Override]",
            is_optional=True,
            prefix="RelativeDateTime.find",
        )

        if self.shift is None and self.find is None:
            raise exceptions.InvalidSmartContractError(
                f"{self} Object requires either shift or find attributes to be populated"
            )

        if self.origin == DefinedDateTime.LIVE:
            raise exceptions.InvalidSmartContractError(
                f'{self} origin attribute does not support "DefinedDateTime.LIVE"'
            )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="shift",
                type="Optional[Shift]",
                docstring="""
                    Shift the datetime by some given parameters, relative to the given origin.
                """,
            ),
            types_utils.ValueSpec(
                name="find",
                type="Optional[Union[Next, Previous, Override]]",
                docstring="""
                    After the initial shift, alter the given values to find the appropriate
                    datetime.
                """,
            ),
            types_utils.ValueSpec(
                name="origin",
                type="DefinedDateTime",
                docstring="""
                    Define the starting point of any shift/find. The value `DefinedDateTime.LIVE`
                    is not allowed.
                """,
            ),
        ]

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="RelativeDateTime",
            docstring="Define a datetime relative to a given origin.",
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),
            ),
        )
