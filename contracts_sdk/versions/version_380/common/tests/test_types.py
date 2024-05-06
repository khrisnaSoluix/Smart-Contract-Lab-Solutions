from datetime import datetime
from decimal import Decimal
import uuid

from ..types import (
    AddAccountNoteDirective,
    AmendScheduleDirective,
    EventTypeSchedule,
    HookDirectives,
    NoteType,
    Phase,
    PostingInstruction,
    PostingInstructionBatch,
    PostingInstructionBatchDirective,
    PostingInstructionType,
    RemoveSchedulesDirective,
    UpdateAccountEventTypeDirective,
    WorkflowStartDirective,
)
from ....version_370.common.tests.test_types import PublicCommonV370TypesTestCase
from .....utils import symbols
from .....utils.exceptions import InvalidSmartContractError, StrongTypingError


class PublicCommonV380TypesTestCase(PublicCommonV370TypesTestCase):
    TS_380 = datetime(year=2021, month=1, day=1)
    request_id_380 = str(uuid.uuid4())
    account_id_380 = "test_account_id_380"

    def test_event_type_schedule_can_be_created(self):
        event_type_schedule = EventTypeSchedule(day="day", year="year")
        self.assertEqual(event_type_schedule.day, "day")
        self.assertEqual(event_type_schedule.year, "year")

    def test_event_type_schedule_empty_schedule(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            EventTypeSchedule()
        self.assertIn("Empty EventTypeSchedule object created", str(ex.exception))

    def test_event_type_schedule_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            EventTypeSchedule(day=12, year="year")
        self.assertIn("'day' expected Optional[str] but got value 1", str(ex.exception))

    def test_hook_directives(self):
        hook_directives = HookDirectives(
            add_account_note_directives=[
                AddAccountNoteDirective(
                    idempotency_key=self.request_id_380,
                    account_id=self.account_id_380,
                    body="some_body",
                    note_type=NoteType.RAW_TEXT,
                    date=self.TS_380,
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
                    request_id=self.request_id_380,
                    account_id=self.account_id_380,
                )
            ],
            remove_schedules_directives=[
                RemoveSchedulesDirective(
                    account_id=self.account_id_380,
                    event_types=["event_type_1", "event_type_2"],
                    request_id=self.request_id_380,
                )
            ],
            workflow_start_directives=[
                WorkflowStartDirective(
                    workflow="test_workflow",
                    context={"key": "value"},
                    account_id=self.account_id_380,
                    idempotency_key=self.request_id_380,
                )
            ],
            posting_instruction_batch_directives=[
                PostingInstructionBatchDirective(
                    request_id=self.request_id_380,
                    posting_instruction_batch=PostingInstructionBatch(
                        batch_id="test",
                        batch_details={},
                        client_id="Visa",
                        client_batch_id="international-payment",
                        value_timestamp=self.TS_380,
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
                                account_id=self.account_id_380,
                                account_address=symbols.DEFAULT_ADDRESS,
                                asset=symbols.DEFAULT_ASSET,
                                phase=Phase.COMMITTED,
                            ),
                        ],
                    ),
                )
            ],
            update_account_event_type_directives=[
                UpdateAccountEventTypeDirective(
                    account_id=self.account_id_380,
                    event_type="event_type_1",
                    end_datetime=self.TS_380,
                )
            ],
        )
        self.assertEqual(
            self.request_id_380, hook_directives.add_account_note_directives[0].idempotency_key
        )
        self.assertEqual(
            self.request_id_380, hook_directives.amend_schedule_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_380, hook_directives.remove_schedules_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_380, hook_directives.posting_instruction_batch_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_380, hook_directives.workflow_start_directives[0].idempotency_key
        )
        self.assertEqual(
            self.account_id_380, hook_directives.update_account_event_type_directives[0].account_id
        )

    def test_hook_directives_errors_with_previous_version_constructor_args(self):
        with self.assertRaises(TypeError) as ex:
            HookDirectives(
                add_account_note_directives=[
                    AddAccountNoteDirective(
                        idempotency_key=self.request_id_380,
                        account_id=self.account_id_380,
                        body="some_body",
                        note_type=NoteType.RAW_TEXT,
                        date=self.TS_380,
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
                        request_id=self.request_id_380,
                        account_id=self.account_id_380,
                    )
                ],
                remove_schedules_directives=[
                    RemoveSchedulesDirective(
                        account_id=self.account_id_380,
                        event_types=["event_type_1", "event_type_2"],
                        request_id=self.request_id_380,
                    )
                ],
                workflow_start_directives=[
                    WorkflowStartDirective(
                        workflow="test_workflow",
                        context={"key": "value"},
                        account_id=self.account_id_380,
                        idempotency_key=self.request_id_380,
                    )
                ],
                posting_instruction_batch_directives=[
                    PostingInstructionBatchDirective(
                        request_id=self.request_id_380,
                        posting_instruction_batch=PostingInstructionBatch(
                            batch_id="test",
                            batch_details={},
                            client_id="Visa",
                            client_batch_id="international-payment",
                            value_timestamp=self.TS_380,
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
                                    account_id=self.account_id_380,
                                    account_address=symbols.DEFAULT_ADDRESS,
                                    asset=symbols.DEFAULT_ASSET,
                                    phase=Phase.COMMITTED,
                                ),
                            ],
                        ),
                    )
                ],
            )

        self.assertIn(
            (
                "__init__() missing 1 required keyword-only argument: "
                "'update_account_event_type_directives'"
            ),
            str(ex.exception),
        )

    def test_hook_directives_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            HookDirectives(
                add_account_note_directives=[],
                amend_schedule_directives=[],
                remove_schedules_directives=[],
                workflow_start_directives=[],
                posting_instruction_batch_directives=[],
                update_account_event_type_directives="bad",
            )

        self.assertIn(
            (
                "'update_account_event_type_directives' expected "
                "List[UpdateAccountEventTypeDirective] but got value 'bad'"
            ),
            str(ex.exception),
        )

    def test_update_account_event_type_directive_can_be_created(self):
        update_account_event_type_directive = UpdateAccountEventTypeDirective(
            account_id=self.account_id_380,
            event_type="event_type_1",
            end_datetime=self.TS_380,
        )
        self.assertEqual(update_account_event_type_directive.account_id, self.account_id_380)
        self.assertEqual(update_account_event_type_directive.event_type, "event_type_1")
        self.assertEqual(update_account_event_type_directive.end_datetime, self.TS_380)

    def test_update_account_event_type_directive_no_end_datetime_or_schedule(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdateAccountEventTypeDirective(
                account_id=self.account_id_380,
                event_type="event_type_1",
            )

        self.assertIn(
            (
                "UpdateAccountEventTypeDirective object has to have either an end_datetime or a "
                "schedule defined"
            ),
            str(ex.exception),
        )

    def test_update_account_event_type_directive_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            UpdateAccountEventTypeDirective(
                account_id=123,
                event_type="event_type_1",
                end_datetime=self.TS_380,
            )

        self.assertIn("'account_id' expected str but got value 123", str(ex.exception))

    def test_posting_instruction_batch_rejects_invalid_insertion_timestamp(self):
        with self.assertRaises(StrongTypingError):
            PostingInstructionBatch(
                batch_details={},
                client_batch_id="international-payment",
                insertion_timestamp="bananas",
                value_timestamp=self.TS_380,
                posting_instructions=[],
            )

    def test_posting_instruction_batch_directive(self):
        posting_instr_batch = PostingInstructionBatch(
            batch_id="test",
            batch_details={},
            client_id="Visa",
            client_batch_id="international-payment",
            value_timestamp=self.TS_380,
            posting_instructions=[
                PostingInstruction(
                    custom_instruction_grouping_key="some_key",
                    client_transaction_id="the-main-payment-id",
                    denomination="GBP",
                    account_id=self.account_id_380,
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
            request_id=self.request_id_380,
            posting_instruction_batch=posting_instr_batch,
        )
        self.assertEqual(self.request_id_380, posting_instruction_batch_directive.request_id)
