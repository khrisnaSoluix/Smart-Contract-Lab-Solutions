from ...version_360.smart_contracts.types import *  # noqa: F401, F403
from ..common.types import (
    CalendarEvent,
    CalendarEvents,
    PostingInstruction,
    PostingInstructionBatch,
    PostingInstructionBatchDirective,
    HookDirectives,
    TransactionCode,
)
from ...version_360.smart_contracts import types as types360


def types_registry():
    TYPES = types360.types_registry()

    TYPES["CalendarEvent"] = CalendarEvent
    TYPES["CalendarEvents"] = CalendarEvents

    TYPES["PostingInstruction"] = PostingInstruction
    TYPES["PostingInstructionBatch"] = PostingInstructionBatch
    TYPES["PostingInstructionBatchDirective"] = PostingInstructionBatchDirective
    TYPES["HookDirectives"] = HookDirectives
    TYPES["TransactionCode"] = TransactionCode

    return TYPES
