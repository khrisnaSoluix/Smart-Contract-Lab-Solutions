from datetime import datetime
from decimal import Decimal
import uuid

from ..types import (
    AddAccountNoteDirective,
    AmendScheduleDirective,
    EndOfMonthSchedule,
    EventTypeSchedule,
    HookDirectives,
    NoteType,
    Phase,
    PostingInstruction,
    PostingInstructionBatch,
    PostingInstructionBatchDirective,
    PostingInstructionType,
    RemoveSchedulesDirective,
    ScheduleSkip,
    UpdateAccountEventTypeDirective,
    WorkflowStartDirective,
)
from ....version_3100.common.tests.test_types import PublicCommonV3100TypesTestCase
from .....utils.exceptions import StrongTypingError, InvalidSmartContractError
from .....utils import symbols


class PublicCommonV3110TypesTestCase(PublicCommonV3100TypesTestCase):
    TS_3110 = datetime(year=2021, month=1, day=1)
    request_id_3110 = str(uuid.uuid4())
    account_id_3110 = "test_account_id_3110"

    def test_update_account_event_type_directive_can_be_created(self):
        update_account_event_type_directive = UpdateAccountEventTypeDirective(
            account_id=self.account_id_3110,
            event_type="event_type_1",
            end_datetime=self.TS_3110,
        )
        self.assertEqual(update_account_event_type_directive.account_id, self.account_id_3110)
        self.assertEqual(update_account_event_type_directive.event_type, "event_type_1")
        self.assertEqual(update_account_event_type_directive.end_datetime, self.TS_3110)

    def test_update_account_event_type_directive_no_end_datetime_or_schedule(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdateAccountEventTypeDirective(
                account_id=self.account_id_3110,
                event_type="event_type_1",
            )

        self.assertIn(
            "UpdateAccountEventTypeDirective object must have either an end_datetime, a schedule",
            str(ex.exception),
        )

    def test_update_account_event_type_directive_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            UpdateAccountEventTypeDirective(
                account_id=123,
                event_type="event_type_1",
                end_datetime=self.TS_3110,
            )

        self.assertIn("'account_id' expected str but got value 123", str(ex.exception))

    def test_update_account_event_type_directive_with_schedule_method(self):
        schedule_method = EndOfMonthSchedule(day=1)
        update_account_event_type_directive = UpdateAccountEventTypeDirective(
            account_id=self.account_id_3110,
            event_type="event_type_1",
            schedule_method=schedule_method,
        )
        self.assertEqual(update_account_event_type_directive.account_id, self.account_id_3110)
        self.assertEqual(update_account_event_type_directive.event_type, "event_type_1")
        self.assertEqual(update_account_event_type_directive.schedule_method, schedule_method)

    def test_update_account_event_type_directive_validation(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdateAccountEventTypeDirective(
                account_id=self.account_id_3110,
                event_type="event_type_1",
                schedule_method=EndOfMonthSchedule(day=1),
                schedule=EventTypeSchedule(day="1"),
            )
        self.assertEqual(
            "UpdateAccountEventTypeDirective cannot contain both"
            " schedule and schedule_method fields",
            str(ex.exception),
        )

    def test_hook_directives(self):
        hook_directives = HookDirectives(
            add_account_note_directives=[
                AddAccountNoteDirective(
                    idempotency_key=self.request_id_3110,
                    account_id=self.account_id_3110,
                    body="some_body",
                    note_type=NoteType.RAW_TEXT,
                    date=self.TS_3110,
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
                    request_id=self.request_id_3110,
                    account_id=self.account_id_3110,
                )
            ],
            remove_schedules_directives=[
                RemoveSchedulesDirective(
                    account_id=self.account_id_3110,
                    event_types=["event_type_1", "event_type_2"],
                    request_id=self.request_id_3110,
                )
            ],
            workflow_start_directives=[
                WorkflowStartDirective(
                    workflow="test_workflow",
                    context={"key": "value"},
                    account_id=self.account_id_3110,
                    idempotency_key=self.request_id_3110,
                )
            ],
            posting_instruction_batch_directives=[
                PostingInstructionBatchDirective(
                    request_id=self.request_id_3110,
                    posting_instruction_batch=PostingInstructionBatch(
                        batch_id="test",
                        batch_details={},
                        client_id="Visa",
                        client_batch_id="international-payment",
                        value_timestamp=self.TS_3110,
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
                                account_id=self.account_id_3110,
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
                    account_id=self.account_id_3110,
                    event_type="event_type_1",
                    end_datetime=self.TS_3110,
                    schedule_method=EndOfMonthSchedule(
                        day=5,
                    ),
                    skip=True,
                )
            ],
        )
        self.assertEqual(
            self.request_id_3110, hook_directives.add_account_note_directives[0].idempotency_key
        )
        self.assertEqual(
            self.request_id_3110, hook_directives.amend_schedule_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_3110, hook_directives.remove_schedules_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_3110, hook_directives.posting_instruction_batch_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_3110, hook_directives.workflow_start_directives[0].idempotency_key
        )
        self.assertEqual(
            self.account_id_3110, hook_directives.update_account_event_type_directives[0].account_id
        )

    def test_update_account_event_type_directive_skip_indefinitely(self):
        update_account_event_type_directive = UpdateAccountEventTypeDirective(
            account_id=self.account_id_3110,
            event_type="event_type_1",
            skip=True,
        )
        self.assertTrue(update_account_event_type_directive.skip)

    def test_update_account_event_type_directive_skip_some_time(self):
        update_account_event_type_directive = UpdateAccountEventTypeDirective(
            account_id=self.account_id_3110,
            event_type="event_type_1",
            skip=ScheduleSkip(end=datetime(year=2021, month=6, day=28)),
        )
        self.assertEqual(
            datetime(year=2021, month=6, day=28), update_account_event_type_directive.skip.end
        )

    def test_update_account_event_type_directive_unskip(self):
        update_account_event_type_directive = UpdateAccountEventTypeDirective(
            account_id=self.account_id_3110,
            event_type="event_type_1",
            skip=False,
        )
        self.assertFalse(update_account_event_type_directive.skip)

    def test_schedule_skip_with_end_datetime(self):
        skip_schedule = ScheduleSkip(end=datetime(year=2021, month=12, day=31))
        self.assertEqual(skip_schedule.end, datetime(year=2021, month=12, day=31))

    def test_schedule_skip_with_invalid_end_datetime(self):
        with self.assertRaises(StrongTypingError) as ex:
            ScheduleSkip(end="2021-12-31")
        self.assertIn("'end' expected datetime but got value '2021-12-31'", str(ex.exception))

    def test_schedule_skip_raises_with_end_datetime_none(self):
        with self.assertRaises(StrongTypingError) as ex:
            ScheduleSkip(end=None)
        self.assertIn("'end' expected datetime but got value None", str(ex.exception))

    def test_schedule_skip_raises_with_end_datetime_not_provided(self):
        with self.assertRaises(TypeError) as ex:
            ScheduleSkip()
        self.assertEqual(
            "ScheduleSkip.__init__() missing 1 required keyword-only argument: 'end'",
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
