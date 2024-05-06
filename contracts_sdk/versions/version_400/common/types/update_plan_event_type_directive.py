from functools import lru_cache

from .....utils import symbols, types_utils
from .....utils.timezone_utils import validate_dateime_is_timezone_aware
from .....utils.exceptions import InvalidSmartContractError, StrongTypingError
from .event_types import ScheduleExpression, ScheduleSkip
from .schedules import EndOfMonthSchedule
from datetime import datetime
from typing import Union, Optional


class UpdatePlanEventTypeDirective:
    def __init__(
        self,
        *,
        event_type: str,
        expression: Optional[ScheduleExpression] = None,
        schedule_method: Optional[EndOfMonthSchedule] = None,
        end_datetime: Optional[datetime] = None,
        skip: Optional[Union[bool, ScheduleSkip]] = None,
        _from_proto: bool = False,
    ):
        self.event_type = event_type
        self.expression = expression
        self.schedule_method = schedule_method
        self.end_datetime = end_datetime
        self.skip = skip
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        if self.expression is not None:
            types_utils.validate_type(self.expression, ScheduleExpression)
        if self.schedule_method is not None:
            types_utils.validate_type(self.schedule_method, EndOfMonthSchedule)
        if self.end_datetime is not None:
            types_utils.validate_type(self.end_datetime, datetime)
            validate_dateime_is_timezone_aware(
                self.end_datetime,
                "end_datetime",
                "UpdatePlanEventTypeDirective",
            )
        if self.skip is None:
            if not self.expression and not self.schedule_method and not self.end_datetime:
                raise InvalidSmartContractError(
                    "UpdatePlanEventTypeDirective object has to have either an end_datetime, an "
                    "expression, schedule_method, or skip defined"
                )

        else:
            try:
                types_utils.validate_type(self.skip, bool)
            except StrongTypingError:
                types_utils.validate_type(
                    self.skip,
                    ScheduleSkip,
                    prefix="skip",
                    hint="Optional[Union[bool, ScheduleSkip]]",
                )

        if self.expression is not None and self.schedule_method is not None:
            raise InvalidSmartContractError(
                "UpdatePlanEventTypeDirective cannot contain both"
                " expression and schedule_method fields"
            )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return types_utils.ClassSpec(
            name="UpdatePlanEventTypeDirective",
            docstring="Specifies a directive to update an event type.",
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="""
                    A Hook Directive that instructs updating a Plan Event Type.
                """,
                args=cls._public_attributes(language_code),
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return [
            types_utils.ValueSpec(
                name="event_type", type="str", docstring="The `event_type` that is to be modified."
            ),
            types_utils.ValueSpec(
                name="expression",
                type="Optional[ScheduleExpression]",
                docstring="Optional [ScheduleExpression](#classes-ScheduleExpression).",
            ),
            types_utils.ValueSpec(
                name="schedule_method",
                type="Optional[EndOfMonthSchedule]",
                docstring="Optional [EndOfMonthSchedule](#classes-EndOfMonthSchedule).",
            ),
            types_utils.ValueSpec(
                name="end_datetime",
                type="Optional[datetime]",
                docstring="""
                    Optional datetime that indicates when the schedule should stop executing. Must
                    be timezone-aware using the ZoneInfo class, and be based on the
                    [events_timezone](../../smart_contracts_api_reference4XX/metadata/#events_timezone) field defined in the
                    Contract metadata. Note that once the end_datetime has been reached,
                    the schedule can **no longer** be updated or re-enabled.
                """,
            ),
            types_utils.ValueSpec(
                name="skip",
                type="Optional[Union[bool, ScheduleSkip]]",
                docstring="""
                    An optional flag to skip a schedule indefinitely (True), unskip a
                    Schedule (False), or to skip until a specified time (ScheduleSkip).
                """,
            ),
        ]
