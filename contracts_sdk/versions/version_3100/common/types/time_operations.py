from functools import lru_cache

from .enums import DefinedDateTime
from .....utils import exceptions, symbols, types_utils


class Override:
    def __init__(self, *, year=None, month=None, day=None, hour=None, minute=None, second=None):

        self._spec().assert_constructor_args(
            self._registry,
            {
                "year": year,
                "month": month,
                "day": day,
                "hour": hour,
                "minute": minute,
                "second": second,
            },
        )

        if not any(arg is not None for arg in [year, month, day, hour, minute, second]):
            raise exceptions.InvalidSmartContractError(
                "Override object needs to be populated with at least one attribute."
            )

        if (
            (year is not None and year < 0)
            or (month is not None and (month <= 0 or month > 12))
            or (day is not None and (day <= 0 or day > 31))
            or (hour is not None and (hour < 0 or hour > 23))
            or (minute is not None and (minute < 0 or minute > 59))
            or (second is not None and (second < 0 or second > 59))
        ):
            raise exceptions.InvalidSmartContractError(
                "Values of Override object are out of range."
            )

        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="year", type="Optional[int]", docstring="Override the year value."
            ),
            types_utils.ValueSpec(
                name="month", type="Optional[int]", docstring="Override the month value."
            ),
            types_utils.ValueSpec(
                name="day", type="Optional[int]", docstring="Override the day value."
            ),
            types_utils.ValueSpec(
                name="hour", type="Optional[int]", docstring="Override the hour value."
            ),
            types_utils.ValueSpec(
                name="minute", type="Optional[int]", docstring="Override the minute value."
            ),
            types_utils.ValueSpec(
                name="second", type="Optional[int]", docstring="Override the second value."
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
                parameter. This can be used in conjunction with [Shift](../types/#classes-Shift)
                inside the [RelativeDateTime](../types/#classes-RelativeDateTime) object.
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
        self, *, years=None, months=None, days=None, hours=None, minutes=None, seconds=None
    ):

        self._spec().assert_constructor_args(
            self._registry,
            {
                "years": years,
                "months": months,
                "days": days,
                "hours": hours,
                "minutes": minutes,
                "seconds": seconds,
            },
        )

        if not any([years, months, days, hours, minutes, seconds]):
            raise exceptions.InvalidSmartContractError(
                "Shift object needs to be populated with at least one attribute."
            )

        self.years = years
        self.months = months
        self.days = days
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds

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
                separate single operation after the date shift has been applied.
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),
            ),
        )


class Next:
    def __init__(self, *, month=None, day=None, hour=None, minute=None, second=None):

        self._spec().assert_constructor_args(
            self._registry,
            {
                "month": month,
                "day": day,
                "hour": hour,
                "minute": minute,
                "second": second,
            },
        )

        if (
            (month is not None and (month <= 0 or month > 12))
            or (day is not None and (day <= 0 or day > 31))
            or (hour is not None and (hour < 0 or hour > 23))
            or (minute is not None and (minute < 0 or minute > 59))
            or (second is not None and (second < 0 or second > 59))
        ):
            raise exceptions.InvalidSmartContractError("Values of Next object are out of range.")

        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="month",
                type="Optional[int]",
                docstring="Shift datetime to the next given month.",
            ),
            types_utils.ValueSpec(
                name="day", type="int", docstring="Shift datetime to the next given day."
            ),
            types_utils.ValueSpec(
                name="hour",
                type="Optional[int]",
                docstring="Shift datetime to the next given hour.",
            ),
            types_utils.ValueSpec(
                name="minute",
                type="Optional[int]",
                docstring="Shift datetime to the next given minute.",
            ),
            types_utils.ValueSpec(
                name="second",
                type="Optional[int]",
                docstring="Shift datetime to the next given second.",
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
    def __init__(self, *, month=None, day=None, hour=None, minute=None, second=None):

        self._spec().assert_constructor_args(
            self._registry,
            {
                "month": month,
                "day": day,
                "hour": hour,
                "minute": minute,
                "second": second,
            },
        )

        if (
            (month is not None and (month <= 0 or month > 12))
            or (day is not None and (day <= 0 or day > 31))
            or (hour is not None and (hour < 0 or hour > 23))
            or (minute is not None and (minute < 0 or minute > 59))
            or (second is not None and (second < 0 or second > 59))
        ):
            raise exceptions.InvalidSmartContractError(
                "Values of Previous object are out of range."
            )

        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="month",
                type="Optional[int]",
                docstring="Shift datetime to the previous given month.",
            ),
            types_utils.ValueSpec(
                name="day", type="int", docstring="Shift datetime to the previous given day."
            ),
            types_utils.ValueSpec(
                name="hour",
                type="Optional[int]",
                docstring="Shift datetime to the previous given hour.",
            ),
            types_utils.ValueSpec(
                name="minute",
                type="Optional[int]",
                docstring="Shift datetime to the previous given minute.",
            ),
            types_utils.ValueSpec(
                name="second",
                type="Optional[int]",
                docstring="Shift datetime to the previous given second.",
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
    def __init__(self, *, shift=None, find=None, origin=None):

        self._spec().assert_constructor_args(
            self._registry,
            {
                "shift": shift,
                "find": find,
                "origin": origin,
            },
        )

        if shift is None and find is None:
            raise exceptions.InvalidSmartContractError(
                "RelativeDateTime Object requires either shift or find attributes to be populated"
            )

        if origin == DefinedDateTime.LIVE:
            raise exceptions.InvalidSmartContractError(
                'RelativeDateTime origin attribute does not support "DefinedDateTime.LIVE"'
            )

        self.shift = shift
        self.find = find
        self.origin = origin

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
