import uuid
from datetime import datetime
from decimal import Decimal

from ..types import (
    AddAccountNoteDirective,
    AmendScheduleDirective,
    defaultAddress,
    defaultAsset,
    CalendarEvent,
    CalendarEvents,
    ClientTransaction,
    NoteType,
    HookDirectives,
    Phase,
    PostingInstruction,
    PostingInstructionBatch,
    PostingInstructionBatchDirective,
    PostingInstructionType,
    RemoveSchedulesDirective,
    WorkflowStartDirective,
    TransactionCode,
)
from .....utils import symbols
from .....utils.exceptions import InvalidSmartContractError, StrongTypingError
from ....version_360.common.tests.test_types import PublicCommonV360TypesTestCase


class PublicCommonV370TypesTestCase(PublicCommonV360TypesTestCase):
    TS_370 = datetime(year=2020, month=1, day=1)
    request_id_370 = str(uuid.uuid4())
    account_id_370 = "test_account_id"

    def test_calendar_event(self):
        calendar_event = CalendarEvent(
            id="test 1",
            calendar_id="123",
            start_timestamp=datetime(2015, 1, 1),
            end_timestamp=datetime(2015, 1, 2),
        )
        self.assertEqual("test 1", calendar_event.id)

    def test_calendar_event_wrong_date_type(self):
        with self.assertRaises(StrongTypingError):
            CalendarEvent(  # noqa: F841
                id="test 1",
                calendar_id="123",
                start_timestamp=-1,
                end_timestamp=datetime(2015, 1, 2),
            )

    def test_calendar_events(self):
        calendar_events = CalendarEvents(
            calendar_events=[
                CalendarEvent(
                    id="test 1",
                    calendar_id="123",
                    start_timestamp=datetime(2015, 1, 1),
                    end_timestamp=datetime(2015, 1, 2),
                ),
                CalendarEvent(
                    id="test 2",
                    calendar_id="124",
                    start_timestamp=datetime(2016, 1, 1),
                    end_timestamp=datetime(2016, 1, 2),
                ),
            ]
        )
        self.assertEqual(2, len(calendar_events))
        self.assertEqual("test 1", calendar_events[0].id)
        self.assertEqual("test 2", calendar_events[1].id)

    def test_calendar_events_wrong_calendar_id_type(self):
        with self.assertRaises(StrongTypingError):
            CalendarEvents(calendar_events=1)  # noqa: F841

    def test_transaction_code(self):
        transaction_code = TransactionCode(
            domain="Blossom",
            family="Buttercup",
            subfamily="Bubbles",
        )
        self.assertEqual("Blossom", transaction_code.domain)

    def test_posting_instruction_with_transaction_code(self):
        pi = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="xx",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id="1231234",
            account_address=defaultAddress.fixed_value,
            amount=Decimal(10),
            asset=defaultAsset.fixed_value,
            credit=False,
            denomination="GBP",
            override_all_restrictions=False,
            transaction_code=TransactionCode(
                domain="Blossom",
                family="Buttercup",
                subfamily="Bubbles",
            ),
        )
        self.assertTrue(hasattr(pi, "transaction_code"))
        self.assertEqual("Blossom", pi.transaction_code.domain)

    def test_posting_instruction_types(self):
        pi = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="xx",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id="1231234",
            account_address=defaultAddress.fixed_value,
            amount=Decimal(10),
            asset=defaultAsset.fixed_value,
            credit=False,
            denomination="GBP",
        )
        with self.assertRaises(NotImplementedError):
            pi.balances()

    def test_posting_instruction_missing_kwargs(self):
        with self.assertRaises(StrongTypingError):
            PostingInstruction(id="101", account_id="1234512", amount=Decimal(10))

    def test_client_transaction(self):
        post_one = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="out",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id="1231234",
            account_address=defaultAddress.fixed_value,
            amount=Decimal(10),
            asset=defaultAsset.fixed_value,
            credit=False,
            denomination="GBP",
        )
        post_two = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="in",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id="1231234",
            account_address=defaultAddress.fixed_value,
            amount=Decimal(0.1),
            asset=defaultAsset.fixed_value,
            credit=True,
            denomination="GBP",
        )
        trans = ClientTransaction([post_one, post_two])
        self.assertEqual("Missing implementation", str(trans.start_time))

    def test_posting_instruction_balances_not_implemented(self):
        pi = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="xx",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id=self.account_id_370,
            account_address=defaultAddress.fixed_value,
            amount=Decimal(10),
            asset=defaultAsset.fixed_value,
            credit=False,
            denomination="GBP",
            override_all_restrictions=False,
        )
        with self.assertRaises(NotImplementedError):
            pi.balances()

    def test_posting_instruction_advice_not_set(self):
        common_kwargs = {
            "id": "123",
            "client_transaction_id": "123",
            "pics": ["test"],
            "custom_instruction_grouping_key": "123",
            "account_id": "123",
            "account_address": "test",
            "asset": "test",
            "credit": True,
            "denomination": "GBP",
        }

        pi = PostingInstruction(type=PostingInstructionType.AUTHORISATION, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertFalse(pi.advice)

        pi = PostingInstruction(
            type=PostingInstructionType.AUTHORISATION_ADJUSTMENT, **common_kwargs
        )
        self.assertTrue(hasattr(pi, "advice"))
        self.assertFalse(pi.advice)

        pi = PostingInstruction(
            type=PostingInstructionType.CUSTOM_INSTRUCTION, phase=Phase.COMMITTED, **common_kwargs
        )
        self.assertFalse(hasattr(pi, "advice"))

        pi = PostingInstruction(type=PostingInstructionType.HARD_SETTLEMENT, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertFalse(pi.advice)

        pi = PostingInstruction(type=PostingInstructionType.RELEASE, **common_kwargs)
        self.assertFalse(hasattr(pi, "advice"))

        pi = PostingInstruction(
            type=PostingInstructionType.SETTLEMENT, final=False, **common_kwargs
        )
        self.assertFalse(hasattr(pi, "advice"))

        pi = PostingInstruction(type=PostingInstructionType.TRANSFER, **common_kwargs)
        self.assertFalse(hasattr(pi, "advice"))

    def test_posting_instruction_advice_set(self):
        common_kwargs = {
            "advice": True,
            "id": "123",
            "client_transaction_id": "123",
            "pics": ["test"],
            "custom_instruction_grouping_key": "123",
            "account_id": "123",
            "account_address": "test",
            "asset": "test",
            "credit": True,
            "denomination": "GBP",
        }

        pi = PostingInstruction(type=PostingInstructionType.AUTHORISATION, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertTrue(pi.advice)

        pi = PostingInstruction(
            type=PostingInstructionType.AUTHORISATION_ADJUSTMENT, **common_kwargs
        )
        self.assertTrue(hasattr(pi, "advice"))
        self.assertTrue(pi.advice)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(
                type=PostingInstructionType.CUSTOM_INSTRUCTION,
                phase=Phase.COMMITTED,
                **common_kwargs
            )

        pi = PostingInstruction(type=PostingInstructionType.HARD_SETTLEMENT, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertTrue(pi.advice)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(type=PostingInstructionType.RELEASE, **common_kwargs)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(type=PostingInstructionType.SETTLEMENT, final=False, **common_kwargs)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(type=PostingInstructionType.TRANSFER, **common_kwargs)

    def test_posting_instruction_batch_balances_not_implemented(self):
        posting_instruction_batch = PostingInstructionBatch(
            batch_id="batch_id",
            batch_details={},
            client_id="Visa",
            client_batch_id="international-payment",
            value_timestamp=self.TS_370,
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
                    account_id=self.account_id_370,
                    account_address=symbols.DEFAULT_ADDRESS,
                    asset=symbols.DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
        )

        with self.assertRaises(NotImplementedError):
            posting_instruction_batch.balances()

    def test_posting_instruction_batch_directive(self):
        posting_instr_batch = PostingInstructionBatch(
            batch_id="test",
            batch_details={},
            client_id="Visa",
            client_batch_id="international-payment",
            value_timestamp=self.TS_370,
            posting_instructions=[
                PostingInstruction(
                    custom_instruction_grouping_key="some_key",
                    client_transaction_id="the-main-payment-id",
                    denomination="GBP",
                    account_id=self.account_id_370,
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
            request_id=self.request_id_370,
            posting_instruction_batch=posting_instr_batch,
        )
        self.assertEqual(self.request_id_370, posting_instruction_batch_directive.request_id)

    def test_posting_instruction_advice_field(self):
        with self.assertRaises(StrongTypingError):
            PostingInstruction(
                id="100",
                type=PostingInstructionType.TRANSFER,
                client_transaction_id="xx",
                pics=[],
                custom_instruction_grouping_key="yy",
                account_id=self.account_id_370,
                account_address=defaultAddress.fixed_value,
                amount=Decimal(10),
                asset=defaultAsset.fixed_value,
                credit=False,
                denomination="GBP",
                advice="test",
            )

    def test_posting_instruction_override_all_restrictions(self):
        with self.assertRaises(StrongTypingError):
            PostingInstruction(
                id="100",
                type=PostingInstructionType.TRANSFER,
                client_transaction_id="xx",
                pics=[],
                custom_instruction_grouping_key="yy",
                account_id=self.account_id_370,
                account_address=defaultAddress.fixed_value,
                amount=Decimal(10),
                asset=defaultAsset.fixed_value,
                credit=False,
                denomination="GBP",
                override_all_restrictions="test",
            )

    def test_hook_directives(self):
        hook_directives = HookDirectives(
            add_account_note_directives=[
                AddAccountNoteDirective(
                    idempotency_key=self.request_id_370,
                    account_id=self.account_id_370,
                    body="some_body",
                    note_type=NoteType.RAW_TEXT,
                    date=self.TS_370,
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
                    request_id=self.request_id_370,
                    account_id=self.account_id_370,
                )
            ],
            remove_schedules_directives=[
                RemoveSchedulesDirective(
                    account_id=self.account_id_370,
                    event_types=["event_type_1", "event_type_2"],
                    request_id=self.request_id_370,
                )
            ],
            workflow_start_directives=[
                WorkflowStartDirective(
                    workflow="test_workflow",
                    context={"key": "value"},
                    account_id=self.account_id_370,
                    idempotency_key=self.request_id_370,
                )
            ],
            posting_instruction_batch_directives=[
                PostingInstructionBatchDirective(
                    request_id=self.request_id_370,
                    posting_instruction_batch=PostingInstructionBatch(
                        batch_id="test",
                        batch_details={},
                        client_id="Visa",
                        client_batch_id="international-payment",
                        value_timestamp=self.TS_370,
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
                                account_id=self.account_id_370,
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
            self.request_id_370, hook_directives.add_account_note_directives[0].idempotency_key
        )
        self.assertEqual(
            self.request_id_370, hook_directives.amend_schedule_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_370, hook_directives.remove_schedules_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_370, hook_directives.posting_instruction_batch_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_370, hook_directives.workflow_start_directives[0].idempotency_key
        )

    def test_posting_instruction_batch_rejects_invalid_insertion_timestamp(self):
        with self.assertRaises(StrongTypingError):
            PostingInstructionBatch(
                batch_details={},
                client_batch_id="international-payment",
                insertion_timestamp="bananas",
                value_timestamp=self.TS_370,
                posting_instructions=[],
            )

    def test_posting_instruction_batch_validation_is_skipped_if_from_proto(self):
        # This instantiation should not raise an error even though the arguments are
        # invalid, as _from_proto is set to True
        try:
            PostingInstructionBatch(
                batch_id=123,  # Invalid type, str expected
                batch_details={},
                client_id="client_id",
                client_batch_id="client_batch_id",
                value_timestamp=self.TS_300,
                posting_instructions=[
                    PostingInstruction(
                        id="123",
                        type=PostingInstructionType.AUTHORISATION,
                        client_transaction_id="123",
                        instruction_details={"test": "testy"},
                        pics=["test"],
                        custom_instruction_grouping_key="123",
                        account_id="123",
                        account_address=symbols.DEFAULT_ADDRESS,
                        asset=symbols.DEFAULT_ASSET,
                        credit=True,
                        denomination="GBP",
                    )
                ],
                _from_proto=True,  # Bypass validation
            )
        except Exception:
            self.fail("Creating PIB with _from_proto=True should not trigger type checks")
