from functools import lru_cache

from .enums import ScheduleFailover
from .....utils import exceptions, symbols, types_utils


class EndOfMonthSchedule:
    def __init__(
        self,
        *,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        failover: "ScheduleFailover" = ScheduleFailover.FIRST_VALID_DAY_BEFORE,
    ):
        self._spec().assert_constructor_args(
            self._registry,
            {
                "day": day,
                "hour": hour,
                "minute": minute,
                "second": second,
                "failover": failover,
            },
        )

        for item_name, item, allowed_range in [
            ("day", day, range(1, 32)),
            ("hour", hour, range(0, 24)),
            ("minute", minute, range(0, 60)),
            ("second", second, range(0, 60)),
        ]:
            if item not in allowed_range:
                raise exceptions.InvalidSmartContractError(
                    f"Argument {item_name} of EndOfMonthSchedule object is"
                    f" out of range({allowed_range[0]}-{allowed_range[-1]})."
                )

        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self.failover = failover

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(name="day", type="int", docstring="Day of the month (1-31)."),
            types_utils.ValueSpec(
                name="hour", type="Optional[int]", docstring="Hour of the day (0-23)."
            ),
            types_utils.ValueSpec(
                name="minute", type="Optional[int]", docstring="Minute of the hour (0-59)."
            ),
            types_utils.ValueSpec(
                name="second", type="Optional[int]", docstring="Second of the minute (0-59)."
            ),
            types_utils.ValueSpec(
                name="failover",
                type="Optional[ScheduleFailover]",
                docstring="The failover strategy for this schedule.",
            ),
        ]

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="EndOfMonthSchedule",
            docstring="",
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="""
                Define a recurring monthly schedule that automatically handles the varying lengths
                of different months. You must place the definitions within the `schedule_method`
                attribute for a given event; define this event within [execution schedules](../../smart_contracts_api_reference3XX/hooks/#execution_schedules)
                or within the [update_event_type](../../smart_contracts_api_reference3XX/vault/#methods-update_event_type)
                directive, so that the schedule recurs on a monthly basis. This
                method is available for both Smart and Supervisor Contracts.
                **Only available in version 3.10.0+**.'

                Note: You can only use EndOfMonthSchedule with the Contract Metadata attribute
                events_timezone set to its default of UTC.

                """,  # noqa E501
                args=cls._public_attributes(language_code),
            ),
        )
