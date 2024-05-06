from functools import lru_cache
from typing import List, Optional

from ....version_3110.common import types as types3110

from . import (
    AddAccountNoteDirective,
    AmendScheduleDirective,
    PostingInstructionBatchDirective,
    RemoveSchedulesDirective,
    WorkflowStartDirective,
    UpdateAccountEventTypeDirective,
)
from .instruct_account_notification_directive import InstructAccountNotificationDirective
from .....utils import symbols, types_utils


class HookDirectives(types3110.HookDirectives):
    def __init__(
        self,
        *,
        add_account_note_directives: List[AddAccountNoteDirective],
        amend_schedule_directives: List[AmendScheduleDirective],
        remove_schedules_directives: List[RemoveSchedulesDirective],
        workflow_start_directives: List[WorkflowStartDirective],
        posting_instruction_batch_directives: List[PostingInstructionBatchDirective],
        update_account_event_type_directives: List[UpdateAccountEventTypeDirective],
        instruct_account_notification_directives: List[InstructAccountNotificationDirective],
        _from_proto: Optional[bool] = False
    ):
        super().__init__(
            add_account_note_directives=add_account_note_directives,
            amend_schedule_directives=amend_schedule_directives,
            remove_schedules_directives=remove_schedules_directives,
            workflow_start_directives=workflow_start_directives,
            posting_instruction_batch_directives=posting_instruction_batch_directives,
            update_account_event_type_directives=update_account_event_type_directives,
            _from_proto=_from_proto,
        )

        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "instruct_account_notification_directives": instruct_account_notification_directives  # noqa: E501
                },
            )

        self.instruct_account_notification_directives = instruct_account_notification_directives

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        public_attributes = super()._public_attributes(language_code)
        public_attributes.append(
            types_utils.ValueSpec(
                name="instruct_account_notification_directives",
                type="List[InstructAccountNotificationDirective]",
                docstring="""
                        A list of
                        [InstructAccountNotificationDirective](#classes-InstructAccountNotificationDirective) objects.
                        **Only available in version 3.12+**
                    """,  # noqa: E501
            )
        )

        return public_attributes
