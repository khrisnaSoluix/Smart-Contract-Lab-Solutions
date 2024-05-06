from ...version_330.smart_contracts.types import *  # noqa: F401, F403
from ..common.types import (
    AddAccountNoteDirective,
    AmendScheduleDirective,
    HookDirectives,
    PostingInstructionBatchDirective,
    RemoveSchedulesDirective,
    WorkflowStartDirective,
)
from ...version_330.smart_contracts import types as types330


def types_registry():
    TYPES = types330.types_registry()

    TYPES["AddAccountNoteDirective"] = AddAccountNoteDirective
    TYPES["AmendScheduleDirective"] = AmendScheduleDirective
    TYPES["HookDirectives"] = HookDirectives
    TYPES["PostingInstructionBatchDirective"] = PostingInstructionBatchDirective
    TYPES["RemoveSchedulesDirective"] = RemoveSchedulesDirective
    TYPES["WorkflowStartDirective"] = WorkflowStartDirective
    return TYPES
