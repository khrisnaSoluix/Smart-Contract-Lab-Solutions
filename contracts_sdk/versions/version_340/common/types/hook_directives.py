from functools import lru_cache
from typing import List, Optional

from .add_account_note_directive import AddAccountNoteDirective
from .amend_schedule_directive import AmendScheduleDirective
from .posting_instruction_batch_directive import PostingInstructionBatchDirective
from .remove_schedules_directive import RemoveSchedulesDirective
from .workflow_start_directive import WorkflowStartDirective

from .....utils import symbols
from .....utils import types_utils


class HookDirectives:

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

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError('Language not supported')
        return types_utils.ClassSpec(
            name='HookDirectives',
            docstring='''
                The outcomes of a hook run. These include new Account Notes, amended or removed
                Schedules, triggered Workflows and generated Posting Instruction Batches.
                **Only available in version 3.4.0+.**
            ''',
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring='Constructs a new HookDirectives',
                args=cls._public_attributes(language_code)
            )
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError('Language not supported')

        return [
            types_utils.ValueSpec(
                name='add_account_note_directives',
                type='List[AddAccountNoteDirective]',
                docstring='''
                    A list of [AddAccountNoteDirectives](#classes-AddAccountNoteDirective).
                '''
            ),
            types_utils.ValueSpec(
                name='amend_schedule_directives',
                type='List[AmendScheduleDirective]',
                docstring='''
                    A list of [AmendScheduleDirectives](#classes-AmendScheduleDirective).
                '''
            ),
            types_utils.ValueSpec(
                name='remove_schedules_directives',
                type='List[RemoveSchedulesDirective]',
                docstring='''
                    A list of [RemoveSchedulesDirectives](#classes-RemoveSchedulesDirective).
                '''
            ),
            types_utils.ValueSpec(
                name='workflow_start_directives',
                type='List[WorkflowStartDirective]',
                docstring='''
                    A list of [WorkflowStartDirectives](#classes-WorkflowStartDirective).
                '''
            ),
            types_utils.ValueSpec(
                name='posting_instruction_batch_directives',
                type='List[PostingInstructionBatchDirective]',
                docstring='''
                    A list of [PostingInstructionBatchDirectives](#classes-PostingInstructionBatchDirective).
                '''  # noqa: E501
            ),
        ]
