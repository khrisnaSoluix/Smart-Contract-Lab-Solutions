from functools import lru_cache

from .....utils import symbols
from .....utils import types_utils
from .....utils.exceptions import InvalidSmartContractError


class EventTypeSchedule:
    def __init__(
        self,
        *,
        day=None,
        day_of_week=None,
        hour=None,
        minute=None,
        second=None,
        month=None,
        year=None,
        _from_proto=False
    ):

        if not _from_proto:
            if not any([day, day_of_week, hour, minute, second, month, year]):
                raise InvalidSmartContractError("Empty EventTypeSchedule object created")

            self._spec().assert_constructor_args(
                self._registry,
                {
                    "day": day,
                    "day_of_week": day_of_week,
                    "hour": hour,
                    "minute": minute,
                    "second": second,
                    "month": month,
                    "year": year,
                },
            )

        self.day = day
        self.day_of_week = day_of_week
        self.hour = hour
        self.minute = minute
        self.second = second
        self.month = month
        self.year = year

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="day", type="Optional[str]", docstring="Day of the month (1-31)."
            ),
            types_utils.ValueSpec(
                name="day_of_week",
                type="Optional[str]",
                docstring="Day of the week (0-6 or mon-sun).",
            ),
            types_utils.ValueSpec(name="hour", type="Optional[str]", docstring="Hour (0-23)."),
            types_utils.ValueSpec(name="minute", type="Optional[str]", docstring="Minute (0-59)."),
            types_utils.ValueSpec(name="second", type="Optional[str]", docstring="Second (0-59)."),
            types_utils.ValueSpec(name="month", type="Optional[str]", docstring="Month (1-12)."),
            types_utils.ValueSpec(
                name="year", type="Optional[str]", docstring="Year (4-digit year)."
            ),
        ]

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="EventTypeSchedule",
            docstring=(
                "The schedule definition associated with an Event Type. All schedule definition "
                "attributes must be based on the `events_timezone` field defined in the "
                "[Smart](../../smart_contracts_api_reference3XX/metadata/#events_timezone) "
                "and [Supervisor](../../supervisor_contracts_api_reference3XX/metadata/#events_timezone) Contract "
                "metadata. **Only available in version 3.8.0+**."
            ),
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring=(
                    "Constructs a new EventTypeSchedule. At least one of the optional attributes "
                    "must be provided."
                ),
                args=cls._public_attributes(language_code),
            ),
        )
