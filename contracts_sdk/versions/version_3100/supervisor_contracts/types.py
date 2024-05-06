from functools import lru_cache
from ...version_390.supervisor_contracts.types import *  # noqa: F401, F403
from ...version_390.supervisor_contracts import types as types390
from ....utils.exceptions import InvalidSmartContractError
from ....utils import symbols, types_utils
from ..common.types import (
    BalancesFilter,
    BalancesIntervalFetcher,
    BalancesObservation,
    BalancesObservationFetcher,
    DefinedDateTime,
    HookDirectives,
    EndOfMonthSchedule,
    EventTypesGroup,
    ScheduleFailover,
    Next,
    Override,
    PostingInstruction,
    PostingInstructionBatch,
    PostingInstructionBatchDirective,
    PostingsIntervalFetcher,
    Previous,
    RelativeDateTime,
    ScheduledJob,
    Shift,
    UpdateAccountEventTypeDirective,
)


class UpdatePlanEventTypeDirective(types390.UpdatePlanEventTypeDirective):
    def __init__(
        self,
        *,
        plan_id,
        event_type,
        schedule=None,
        schedule_method=None,
        end_datetime=None,
        _from_proto=False,
        _validate_missing_params=True,
    ):
        if not _from_proto:
            if _validate_missing_params:
                if not schedule and not schedule_method and not end_datetime:
                    raise InvalidSmartContractError(
                        "UpdatePlanEventTypeDirective object has to have either an end_datetime, "
                        "a schedule or schedule_method defined"
                    )
            if schedule is not None and schedule_method is not None:
                raise InvalidSmartContractError(
                    "UpdatePlanEventTypeDirective cannot contain both"
                    " schedule and schedule_method fields"
                )
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
        self.schedule_method = schedule_method
        self.end_datetime = end_datetime

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        attributes = super()._public_attributes(language_code=language_code)
        return attributes + [
            types_utils.ValueSpec(
                name="schedule_method",
                type="Optional[EndOfMonthSchedule]",
                docstring="Optional [EndOfMonthSchedule](#classes-EndOfMonthSchedule).",
            ),
        ]


def types_registry():
    TYPES = types390.types_registry()
    TYPES["BalancesFilter"] = BalancesFilter
    TYPES["BalancesObservation"] = BalancesObservation
    TYPES["BalancesIntervalFetcher"] = BalancesIntervalFetcher
    TYPES["BalancesObservationFetcher"] = BalancesObservationFetcher
    TYPES["DefinedDateTime"] = DefinedDateTime
    TYPES["Next"] = Next
    TYPES["Override"] = Override
    TYPES["PostingsIntervalFetcher"] = PostingsIntervalFetcher
    TYPES["PostingInstruction"] = PostingInstruction
    TYPES["PostingInstructionBatch"] = PostingInstructionBatch
    TYPES["PostingInstructionBatchDirective"] = PostingInstructionBatchDirective
    TYPES["Previous"] = Previous
    TYPES["RelativeDateTime"] = RelativeDateTime
    TYPES["Shift"] = Shift
    TYPES["ScheduledJob"] = ScheduledJob
    TYPES["ScheduleFailover"] = ScheduleFailover
    TYPES["EndOfMonthSchedule"] = EndOfMonthSchedule
    TYPES["UpdatePlanEventTypeDirective"] = UpdatePlanEventTypeDirective
    TYPES["UpdateAccountEventTypeDirective"] = UpdateAccountEventTypeDirective
    TYPES["HookDirectives"] = HookDirectives
    TYPES["EventTypesGroup"] = EventTypesGroup

    return TYPES
