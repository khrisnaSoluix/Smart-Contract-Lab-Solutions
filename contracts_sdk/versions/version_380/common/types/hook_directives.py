from functools import lru_cache
from typing import List, Optional

from . import (
    AddAccountNoteDirective, AmendScheduleDirective, PostingInstructionBatchDirective,
    RemoveSchedulesDirective, WorkflowStartDirective
)
from .update_account_event_type_directive import UpdateAccountEventTypeDirective
from ....version_370.common import types as types370
from .....utils import symbols
from .....utils import types_utils


class HookDirectives(types370.HookDirectives):
    def __init__(
        self,
        *,
        add_account_note_directives: List[AddAccountNoteDirective],
        amend_schedule_directives: List[AmendScheduleDirective],
        remove_schedules_directives: List[RemoveSchedulesDirective],
        workflow_start_directives: List[WorkflowStartDirective],
        posting_instruction_batch_directives: List[PostingInstructionBatchDirective],
        update_account_event_type_directives: List[UpdateAccountEventTypeDirective],
        _from_proto: Optional[bool] = False
    ):
        super().__init__(
            add_account_note_directives=add_account_note_directives,
            amend_schedule_directives=amend_schedule_directives,
            remove_schedules_directives=remove_schedules_directives,
            workflow_start_directives=workflow_start_directives,
            posting_instruction_batch_directives=posting_instruction_batch_directives,
            _from_proto=_from_proto,
        )

        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry, {
                    'update_account_event_type_directives': update_account_event_type_directives
                }
            )

        self.update_account_event_type_directives = update_account_event_type_directives

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        public_attributes = super()._public_attributes(language_code)
        public_attributes.append(
            types_utils.ValueSpec(
                name='update_account_event_type_directives',
                type='List[UpdateAccountEventTypeDirective]',
                docstring=(
                    'A list of '
                    '[UpdateAccountEventTypeDirectives](#classes-UpdateAccountEventTypeDirective). '
                    '**Only available in version 3.8.0+**')
            )
        )

        return public_attributes
