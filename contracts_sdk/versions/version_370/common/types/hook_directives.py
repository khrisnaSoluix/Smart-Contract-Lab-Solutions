from typing import List, Optional

from . import (
    AddAccountNoteDirective, AmendScheduleDirective, PostingInstructionBatchDirective,
    RemoveSchedulesDirective, WorkflowStartDirective
)
from ....version_360.common.types import hook_directives as hook_directives360


class HookDirectives(hook_directives360.HookDirectives):
    def __init__(
        self,
        *,
        add_account_note_directives: List[AddAccountNoteDirective],
        amend_schedule_directives: List[AmendScheduleDirective],
        remove_schedules_directives: List[RemoveSchedulesDirective],
        workflow_start_directives: List[WorkflowStartDirective],
        posting_instruction_batch_directives: List[PostingInstructionBatchDirective],
        _from_proto: Optional[bool] = False
    ):
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry, {
                    'add_account_note_directives': add_account_note_directives,
                    'amend_schedule_directives': amend_schedule_directives,
                    'remove_schedules_directives': remove_schedules_directives,
                    'workflow_start_directives': workflow_start_directives,
                    'posting_instruction_batch_directives': posting_instruction_batch_directives
                }
            )

        self.add_account_note_directives = add_account_note_directives
        self.amend_schedule_directives = amend_schedule_directives
        self.remove_schedules_directives = remove_schedules_directives
        self.workflow_start_directives = workflow_start_directives
        self.posting_instruction_batch_directives = posting_instruction_batch_directives
