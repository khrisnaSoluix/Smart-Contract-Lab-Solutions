import uuid
from datetime import datetime
from decimal import Decimal

from ..types import (
    AddAccountNoteDirective,
    AmendScheduleDirective,
    HookDirectives,
    NoteType,
    Phase,
    PostingInstruction,
    PostingInstructionBatch,
    PostingInstructionBatchDirective,
    PostingInstructionType,
    RemoveSchedulesDirective,
    WorkflowStartDirective,
)
from ....version_330.common.tests.test_types import PublicCommonV330TypesTestCase
from .....utils import symbols


class PublicCommonV340TypesTestCase(PublicCommonV330TypesTestCase):
    TS_340 = datetime(year=2020, month=1, day=1)
    request_id_340 = str(uuid.uuid4())
    account_id_340 = "test_account_id"

    def test_add_account_note_directive(self):
        add_account_note_directive = AddAccountNoteDirective(
            idempotency_key=self.request_id_340,
            account_id=self.account_id_340,
            body="some_body",
            note_type=NoteType.RAW_TEXT,
            date=self.TS_340,
            is_visible_to_customer=True,
        )
        self.assertEqual(self.request_id_340, add_account_note_directive.idempotency_key)

    def test_amend_schedule_directive(self):
        amend_schedule_directive = AmendScheduleDirective(
            event_type="event_type_1",
            new_schedule={
                "day": "1",
                "hour": "23",
                "year": "2020",
            },
            request_id=self.request_id_340,
            account_id=self.account_id_340,
        )
        self.assertEqual(self.request_id_340, amend_schedule_directive.request_id)

    def test_hook_directives(self):
        hook_directives = HookDirectives(
            add_account_note_directives=[
                AddAccountNoteDirective(
                    idempotency_key=self.request_id_340,
                    account_id=self.account_id_340,
                    body="some_body",
                    note_type=NoteType.RAW_TEXT,
                    date=self.TS_340,
                    is_visible_to_customer=True,
                )
            ],
            amend_schedule_directives=[
                AmendScheduleDirective(
                    event_type="event_type_1",
                    new_schedule={
                        "day": "1",
                        "hour": "23",
                        "year": "2020",
                    },
                    request_id=self.request_id_340,
                    account_id=self.account_id_340,
                )
            ],
            remove_schedules_directives=[
                RemoveSchedulesDirective(
                    account_id=self.account_id_340,
                    event_types=["event_type_1", "event_type_2"],
                    request_id=self.request_id_340,
                )
            ],
            workflow_start_directives=[
                WorkflowStartDirective(
                    workflow="test_workflow",
                    context={"key": "value"},
                    account_id=self.account_id_340,
                    idempotency_key=self.request_id_340,
                )
            ],
            posting_instruction_batch_directives=[
                PostingInstructionBatchDirective(
                    request_id=self.request_id_340,
                    posting_instruction_batch=PostingInstructionBatch(
                        batch_id="test",
                        batch_details={},
                        client_id="Visa",
                        client_batch_id="international-payment",
                        value_timestamp=self.TS_340,
                        posting_instructions=[
                            PostingInstruction(
                                custom_instruction_grouping_key="some_key",
                                client_transaction_id="the-main-payment-id",
                                pics=["INTERNATIONAL_PAYMENT"],
                                instruction_details={"TYPE": "PURCHASE"},
                                type=PostingInstructionType.CUSTOM_INSTRUCTION,
                                credit=True,
                                amount=Decimal(10),
                                denomination="GBP",
                                account_id=self.account_id_340,
                                account_address=symbols.DEFAULT_ADDRESS,
                                asset=symbols.DEFAULT_ASSET,
                                phase=Phase.COMMITTED,
                            ),
                        ],
                    ),
                )
            ],
        )
        self.assertEqual(
            self.request_id_340, hook_directives.add_account_note_directives[0].idempotency_key
        )
        self.assertEqual(
            self.request_id_340, hook_directives.amend_schedule_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_340, hook_directives.remove_schedules_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_340, hook_directives.posting_instruction_batch_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_340, hook_directives.workflow_start_directives[0].idempotency_key
        )

    def test_remove_schedules_directive(self):
        remove_schedules_directive = RemoveSchedulesDirective(
            account_id=self.account_id_340,
            event_types=["event_type_1", "event_type_2"],
            request_id=self.request_id_340,
        )
        self.assertEqual(self.request_id_340, remove_schedules_directive.request_id)

    def test_posting_instruction_batch_directive(self):
        posting_instr_batch = PostingInstructionBatch(
            batch_id="test",
            batch_details={},
            client_id="Visa",
            client_batch_id="international-payment",
            value_timestamp=self.TS_340,
            posting_instructions=[
                PostingInstruction(
                    custom_instruction_grouping_key="some_key",
                    client_transaction_id="the-main-payment-id",
                    denomination="GBP",
                    account_id=self.account_id_340,
                    type=PostingInstructionType.CUSTOM_INSTRUCTION,
                    pics=["INTERNATIONAL_PAYMENT"],
                    account_address=symbols.DEFAULT_ADDRESS,
                    asset=symbols.DEFAULT_ASSET,
                    credit=True,
                    phase=Phase.COMMITTED,
                ),
            ],
        )
        posting_instruction_batch_directive = PostingInstructionBatchDirective(
            request_id=self.request_id_340,
            posting_instruction_batch=posting_instr_batch,
        )
        self.assertEqual(self.request_id_340, posting_instruction_batch_directive.request_id)

    def test_workflow_start_directive(self):
        workflow_start_directive = WorkflowStartDirective(
            workflow="test_workflow",
            context={"key": "value"},
            account_id=self.account_id_340,
            idempotency_key=self.request_id_340,
        )
        self.assertEqual(self.request_id_340, workflow_start_directive.idempotency_key)
