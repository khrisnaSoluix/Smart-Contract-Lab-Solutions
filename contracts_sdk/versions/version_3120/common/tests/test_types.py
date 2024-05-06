from decimal import Decimal
import uuid

from ..types import (
    SupervisedHooks,
    SupervisionExecutionMode,
    AddAccountNoteDirective,
    AmendScheduleDirective,
    EndOfMonthSchedule,
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
    InstructAccountNotificationDirective,
)
from ....version_3110.common.tests.test_types import PublicCommonV3110TypesTestCase
from .....utils.exceptions import InvalidSmartContractError, StrongTypingError
from .....utils.feature_flags import (
    skip_if_not_enabled,
    PRE_POSTING_SUPERVISION,
    CONTRACTS_NOTIFICATION_EVENT,
)
from .....utils import symbols


class PublicCommonV3120TypesTestCase(PublicCommonV3110TypesTestCase):
    request_id_3120 = str(uuid.uuid4())
    account_id_3120 = "test_account_id_3120"

    @skip_if_not_enabled(feature_flag=PRE_POSTING_SUPERVISION)
    def test_supervision_execution_mode_enum(self):
        self.assertEqual(SupervisionExecutionMode.OVERRIDE, 1)
        self.assertEqual(SupervisionExecutionMode.INVOKED, 2)

    @skip_if_not_enabled(feature_flag=PRE_POSTING_SUPERVISION)
    def test_supervised_hooks(self):
        supervised_hooks = SupervisedHooks(pre_posting_code=SupervisionExecutionMode.OVERRIDE)
        self.assertEqual(supervised_hooks.pre_posting_code, SupervisionExecutionMode.OVERRIDE)

    @skip_if_not_enabled(feature_flag=PRE_POSTING_SUPERVISION)
    def test_supervised_hooks_wrong_type(self):
        with self.assertRaises(StrongTypingError) as e:
            SupervisedHooks(pre_posting_code="test")

        self.assertIn(
            "expected Optional[SupervisionExecutionMode] but got value 'test'", str(e.exception)
        )

    @skip_if_not_enabled(feature_flag=PRE_POSTING_SUPERVISION)
    def test_supervised_hooks_argument_required(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            SupervisedHooks()

        self.assertEqual(str(e.exception), "At least one hook supervision must be specified.")

    @skip_if_not_enabled(feature_flag=CONTRACTS_NOTIFICATION_EVENT)
    def test_hook_directives(self):
        hook_directives = HookDirectives(
            add_account_note_directives=[
                AddAccountNoteDirective(
                    idempotency_key=self.request_id_3120,
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
                    request_id=self.request_id_3120,
                    account_id=self.account_id_3120,
                )
            ],
            remove_schedules_directives=[
                RemoveSchedulesDirective(
                    account_id=self.account_id_3110,
                    event_types=["event_type_1", "event_type_2"],
                    request_id=self.request_id_3120,
                )
            ],
            workflow_start_directives=[
                WorkflowStartDirective(
                    workflow="test_workflow",
                    context={"key": "value"},
                    account_id=self.account_id_3120,
                    idempotency_key=self.request_id_3120,
                )
            ],
            posting_instruction_batch_directives=[
                PostingInstructionBatchDirective(
                    request_id=self.request_id_3120,
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
                                account_id=self.account_id_3120,
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
                    account_id=self.account_id_3120,
                    event_type="event_type_1",
                    end_datetime=self.TS_3110,
                    schedule_method=EndOfMonthSchedule(
                        day=5,
                    ),
                    skip=True,
                )
            ],
            instruct_account_notification_directives=[
                InstructAccountNotificationDirective(
                    account_id=self.account_id_3120,
                    notification_type="test_notification_type",
                    notification_details={"key1": "value1"},
                )
            ],
        )
        self.assertEqual(
            self.request_id_3120, hook_directives.add_account_note_directives[0].idempotency_key
        )
        self.assertEqual(
            self.request_id_3120, hook_directives.amend_schedule_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_3120, hook_directives.remove_schedules_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_3120, hook_directives.posting_instruction_batch_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_3120, hook_directives.workflow_start_directives[0].idempotency_key
        )
        self.assertEqual(
            self.account_id_3120, hook_directives.update_account_event_type_directives[0].account_id
        )
        self.assertEqual(
            self.account_id_3120,
            hook_directives.instruct_account_notification_directives[0].account_id,
        )

    @skip_if_not_enabled(feature_flag=CONTRACTS_NOTIFICATION_EVENT)
    def test_hook_directives_errors_with_previous_version_constructor_args(self):
        with self.assertRaises(TypeError) as ex:
            HookDirectives(
                add_account_note_directives=[
                    AddAccountNoteDirective(
                        idempotency_key=self.request_id_3120,
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
                        request_id=self.request_id_3120,
                        account_id=self.account_id_3120,
                    )
                ],
                remove_schedules_directives=[
                    RemoveSchedulesDirective(
                        account_id=self.account_id_3110,
                        event_types=["event_type_1", "event_type_2"],
                        request_id=self.request_id_3120,
                    )
                ],
                workflow_start_directives=[
                    WorkflowStartDirective(
                        workflow="test_workflow",
                        context={"key": "value"},
                        account_id=self.account_id_3120,
                        idempotency_key=self.request_id_3120,
                    )
                ],
                posting_instruction_batch_directives=[
                    PostingInstructionBatchDirective(
                        request_id=self.request_id_3120,
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
                                    account_id=self.account_id_3120,
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
                        account_id=self.account_id_3120,
                        event_type="event_type_1",
                        end_datetime=self.TS_3110,
                        schedule_method=EndOfMonthSchedule(
                            day=5,
                        ),
                        skip=True,
                    )
                ],
            )
        self.assertIn(
            (
                "__init__() missing 1 required keyword-only argument: "
                "'instruct_account_notification_directives'"
            ),
            str(ex.exception),
        )

    @skip_if_not_enabled(feature_flag=CONTRACTS_NOTIFICATION_EVENT)
    def test_hook_directives_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            HookDirectives(
                add_account_note_directives=[],
                amend_schedule_directives=[],
                remove_schedules_directives=[],
                workflow_start_directives=[],
                posting_instruction_batch_directives=[],
                update_account_event_type_directives=[],
                instruct_account_notification_directives="bad",
            )

        self.assertIn(
            (
                "'instruct_account_notification_directives' expected "
                "List[InstructAccountNotificationDirective] but got value 'bad'"
            ),
            str(ex.exception),
        )

    @skip_if_not_enabled(feature_flag=CONTRACTS_NOTIFICATION_EVENT)
    def test_instruct_account_notification_type_directive_fields(self):
        account_id = "account_id"
        notification_type = "type_1"
        notification_details = {"key1": "value1"}
        instruct_account_notification_directive = InstructAccountNotificationDirective(
            account_id=account_id,
            notification_type=notification_type,
            notification_details=notification_details,
        )
        self.assertEqual(account_id, instruct_account_notification_directive.account_id)
        self.assertEqual(
            notification_type, instruct_account_notification_directive.notification_type
        )
        self.assertEqual(
            notification_details, instruct_account_notification_directive.notification_details
        )
