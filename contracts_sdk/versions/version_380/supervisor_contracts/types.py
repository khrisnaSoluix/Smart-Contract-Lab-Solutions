from functools import lru_cache

from ...version_370.supervisor_contracts.types import *  # noqa: F401, F403
from ..common.types import (
    EventTypeSchedule,
    HookDirectives,
    UpdateAccountEventTypeDirective,
)
from ...version_370.supervisor_contracts import types as types370
from ....utils import types_utils
from ....utils.exceptions import InvalidSmartContractError
from ....utils import symbols


class UpdatePlanEventTypeDirective:
    def __init__(self, *, plan_id, event_type, schedule=None, end_datetime=None, _from_proto=False):
        if not schedule and not end_datetime:
            raise InvalidSmartContractError(
                "UpdatePlanEventTypeDirective object has to have either an end_datetime or a "
                "schedule defined"
            )

        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "plan_id": plan_id,
                    "event_type": event_type,
                    "schedule": schedule,
                    "end_datetime": end_datetime,
                },
            )

        self.plan_id = plan_id
        self.event_type = event_type
        self.schedule = schedule
        self.end_datetime = end_datetime

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
                docstring=(
                    "A [HookDirective](#classes-HookDirectives) that instructs "
                    "updating a Plan Event Type. "
                    "**Only available in version 3.8.0+**"
                ),
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
                name="plan_id",
                type="str",
                docstring="The Plan ID of the `event_type` that will be modified.",
            ),
            types_utils.ValueSpec(
                name="event_type", type="str", docstring="The `event_type` that is to be modified."
            ),
            types_utils.ValueSpec(
                name="schedule",
                type="Optional[EventTypeSchedule]",
                docstring="Optional [EventTypeSchedule](#classes-EventTypeSchedule).",
            ),
            types_utils.ValueSpec(
                name="end_datetime",
                type="Optional[datetime]",
                docstring=(
                    "Optional datetime that indicates when the schedule should stop "
                    "executing. Must be based on the "
                    "[events_timezone](../../supervisor_contracts_api_reference3XX/metadata/#events_timezone) "
                    "field defined in the Contract metadata. "
                    "Note that once the end_datetime has been reached, the schedule can "
                    "**no longer** be updated or re-enabled."
                ),
            ),
        ]


def types_registry():
    TYPES = types370.types_registry()

    TYPES["EventTypeSchedule"] = EventTypeSchedule
    TYPES["UpdateAccountEventTypeDirective"] = UpdateAccountEventTypeDirective
    TYPES["HookDirectives"] = HookDirectives
    TYPES["UpdatePlanEventTypeDirective"] = UpdatePlanEventTypeDirective

    return TYPES
