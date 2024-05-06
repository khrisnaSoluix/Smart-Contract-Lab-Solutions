from ...version_390.contract_modules.types import *  # noqa: F401, F403
from ...version_390.contract_modules import types as types390
from ..common.types import (
    BalancesFilter,
    BalancesIntervalFetcher,
    BalancesObservation,
    BalancesObservationFetcher,
    DefinedDateTime,
    EndOfMonthSchedule,
    EventTypesGroup,
    HookDirectives,
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


def types_registry():
    TYPES = types390.types_registry()
    TYPES["BalancesFilter"] = BalancesFilter
    TYPES["BalancesIntervalFetcher"] = BalancesIntervalFetcher
    TYPES["BalancesObservation"] = BalancesObservation
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
    TYPES["UpdateAccountEventTypeDirective"] = UpdateAccountEventTypeDirective
    TYPES["HookDirectives"] = HookDirectives
    TYPES["EventTypesGroup"] = EventTypesGroup

    return TYPES
