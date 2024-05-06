# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# library
from library.loan.contracts.template import loan
from library.loan.test.unit.test_loan_common import DEFAULT_DATETIME, LoanTestBase

# features
import library.features.v4.lending.lending_addresses as lending_addresses
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import Balance, ScheduledEventHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import ACCOUNT_ID
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    BalanceCoordinate,
    BalanceDefaultDict,
    CustomInstruction,
    Phase,
    Posting,
    PostingInstructionsDirective,
    ScheduledEventHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    DEFAULT_POSTINGS,
    SentinelAccountNotificationDirective,
    SentinelCustomInstruction,
    SentinelUpdateAccountEventTypeDirective,
)

ACCRUAL_EVENT = loan.interest_accrual.ACCRUAL_EVENT
DUE_AMOUNT_CALCULATION_EVENT = loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
BALLOON_PAYMENT_EVENT = loan.balloon_payments.BALLOON_PAYMENT_EVENT


@patch.object(loan, "_handle_interest_capitalisation")
@patch.object(loan, "_get_penalty_interest_accrual_custom_instruction")
@patch.object(loan, "_get_standard_interest_accrual_custom_instructions")
@patch.object(loan.utils, "get_parameter")
@patch.object(loan.flat_interest, "is_flat_interest_loan")
@patch.object(loan.rule_of_78, "is_rule_of_78_loan")
class LoanAccrualScheduledEventTest(LoanTestBase):
    def test_interest_accrual_with_accrual_instructions(
        self,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_standard_interest_accrual_custom_instructions: MagicMock,
        mock_get_penalty_interest_accrual_custom_instruction: MagicMock,
        mock_handle_interest_capitalisation: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": sentinel.amortisation}
        )
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False

        accrual_custom_instructions = [SentinelCustomInstruction("standard_accrual")]
        penalty_accrual_custom_instructions = [SentinelCustomInstruction("penalty_accrual")]
        interest_capitalisation_custom_instructions = [SentinelCustomInstruction("capitalisation")]
        mock_get_standard_interest_accrual_custom_instructions.return_value = (
            accrual_custom_instructions
        )
        mock_get_penalty_interest_accrual_custom_instruction.return_value = (
            penalty_accrual_custom_instructions
        )
        mock_handle_interest_capitalisation.return_value = (
            interest_capitalisation_custom_instructions
        )
        # construct expected result
        expected_postings = (
            penalty_accrual_custom_instructions
            + interest_capitalisation_custom_instructions
            + accrual_custom_instructions
        )
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_postings,  # type: ignore
                    client_batch_id=f"{loan.ACCOUNT_TYPE}_{ACCRUAL_EVENT}_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=ACCRUAL_EVENT
        )
        result = loan.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

        mock_get_standard_interest_accrual_custom_instructions.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            inflight_postings=interest_capitalisation_custom_instructions,
        )

    def test_interest_accrual_no_accrual_instructions(
        self,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_standard_interest_accrual_custom_instructions: MagicMock,
        mock_get_penalty_interest_accrual_custom_instruction: MagicMock,
        mock_handle_interest_capitalisation: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": sentinel.amortisation_method}
        )
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        mock_get_standard_interest_accrual_custom_instructions.return_value = []
        mock_get_penalty_interest_accrual_custom_instruction.return_value = []
        mock_handle_interest_capitalisation.return_value = []

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=ACCRUAL_EVENT
        )
        self.assertIsNone(loan.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args))
        mock_get_standard_interest_accrual_custom_instructions.assert_called_once_with(
            vault=sentinel.vault,
            hook_arguments=hook_args,
            inflight_postings=[],
        )

    @patch.object(loan.interest_accrual_common, "update_schedule_events_skip")
    def test_flat_interest_does_not_accrue_interest_skip_schedule_while_no_penalty_postings(
        self,
        mock_update_schedule_events_skip: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_standard_interest_accrual_custom_instructions: MagicMock,
        mock_get_penalty_interest_accrual_custom_instruction: MagicMock,
        mock_handle_interest_capitalisation: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": sentinel.amortisation_method}
        )
        mock_is_flat_interest_loan.return_value = True
        mock_is_rule_of_78_loan.return_value = False
        mock_get_penalty_interest_accrual_custom_instruction.return_value = []

        update_event_type_directive = SentinelUpdateAccountEventTypeDirective(
            "update_interest_accrual"
        )
        mock_update_schedule_events_skip.return_value = [update_event_type_directive]

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=ACCRUAL_EVENT
        )

        result = loan.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args)

        # if scheduled code is running for flat interest and no penalty interest
        # is charged, an UpdateAccountEventTypeDirective is returned to skip
        # the daily accrual schedule
        expected_result = ScheduledEventHookResult(
            update_account_event_type_directives=[update_event_type_directive]
        )

        self.assertEqual(result, expected_result)
        mock_get_standard_interest_accrual_custom_instructions.assert_not_called()
        mock_handle_interest_capitalisation.assert_not_called()

    @patch.object(loan.interest_accrual_common, "update_schedule_events_skip")
    def test_flat_interest_with_penalties_no_skip_schedule(
        self,
        mock_update_schedule_events_skip: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_standard_interest_accrual_custom_instructions: MagicMock,
        mock_get_penalty_interest_accrual_custom_instruction: MagicMock,
        mock_handle_interest_capitalisation: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": sentinel.amortisation_method}
        )
        mock_is_flat_interest_loan.return_value = True
        mock_is_rule_of_78_loan.return_value = False
        penalty_accrual_custom_instructions = [SentinelCustomInstruction("penalty_accrual")]
        mock_get_penalty_interest_accrual_custom_instruction.return_value = (
            penalty_accrual_custom_instructions
        )
        mock_vault = self.create_mock()

        # construct expected result
        expected_postings = penalty_accrual_custom_instructions

        # no update to accrual schedule as penalty instructions exist
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_postings,  # type: ignore
                    client_batch_id=f"{loan.ACCOUNT_TYPE}_{ACCRUAL_EVENT}_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=ACCRUAL_EVENT
        )
        result = loan.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)
        mock_handle_interest_capitalisation.assert_not_called()
        mock_get_standard_interest_accrual_custom_instructions.assert_not_called()
        mock_update_schedule_events_skip.assert_not_called()

    @patch.object(loan.interest_accrual_common, "update_schedule_events_skip")
    def test_rule_of_78_with_penalties_no_skip_schedule(
        self,
        mock_update_schedule_events_skip: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_standard_interest_accrual_custom_instructions: MagicMock,
        mock_get_penalty_interest_accrual_custom_instruction: MagicMock,
        mock_handle_interest_capitalisation: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": sentinel.amortisation_method}
        )
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = True
        penalty_accrual_custom_instructions = [SentinelCustomInstruction("penalty_accrual")]
        mock_get_penalty_interest_accrual_custom_instruction.return_value = (
            penalty_accrual_custom_instructions
        )
        mock_vault = self.create_mock()

        # construct expected result
        expected_postings = penalty_accrual_custom_instructions

        # no update to accrual schedule as penalty instructions exist
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_postings,  # type: ignore
                    client_batch_id=f"{loan.ACCOUNT_TYPE}_{ACCRUAL_EVENT}_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=ACCRUAL_EVENT
        )
        result = loan.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)
        mock_handle_interest_capitalisation.assert_not_called()
        mock_get_standard_interest_accrual_custom_instructions.assert_not_called()
        mock_update_schedule_events_skip.assert_not_called()

    @patch.object(loan.interest_accrual_common, "update_schedule_events_skip")
    def test_rule_of_78_does_not_accrue_interest(
        self,
        mock_update_schedule_events_skip: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_standard_interest_accrual_custom_instructions: MagicMock,
        mock_get_penalty_interest_accrual_custom_instruction: MagicMock,
        mock_handle_interest_capitalisation: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": sentinel.amortisation_method}
        )
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = True
        mock_get_penalty_interest_accrual_custom_instruction.return_value = []
        update_interest_event_directive = SentinelUpdateAccountEventTypeDirective(
            "update_interest_accrual"
        )
        mock_update_schedule_events_skip.return_value = [update_interest_event_directive]

        expected_result = ScheduledEventHookResult(
            account_notification_directives=[],
            posting_instructions_directives=[],
            update_account_event_type_directives=[update_interest_event_directive],
        )

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=ACCRUAL_EVENT
        )

        scheduled_event_hook_result = loan.scheduled_event_hook(
            vault=sentinel.vault, hook_arguments=hook_args
        )
        self.assertEqual(expected_result, scheduled_event_hook_result)
        mock_get_standard_interest_accrual_custom_instructions.assert_not_called()
        mock_handle_interest_capitalisation.assert_not_called()


@patch.object(loan.interest_capitalisation, "handle_penalty_interest_capitalisation")
@patch.object(loan.utils, "get_parameter")
class LoanDueAmountScheduledEventTest(LoanTestBase):
    @patch.object(loan, "_update_check_overdue_schedule")
    @patch.object(loan, "_update_due_amount_calculation_day_schedule")
    @patch.object(loan, "_get_due_amount_custom_instructions")
    @patch.object(loan.repayment_holiday, "is_due_amount_calculation_blocked")
    @patch.object(loan, "_get_repayment_due_notification")
    @patch.object(loan, "_should_enable_balloon_payment_schedule")
    @patch.object(loan.balloon_payments, "update_balloon_payment_schedule")
    def test_due_amount_calculation_event_with_instructions_no_due_calc_schedule_changes(
        self,
        mock_update_balloon_payment_schedule: MagicMock,
        mock_should_enable_balloon_payment_schedule: MagicMock,
        mock_get_repayment_due_notification: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_get_due_amount_custom_instructions: MagicMock,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_get_parameter: MagicMock,
        mock_handle_penalty_interest_capitalisation: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_is_due_amount_calculation_blocked.return_value = False
        due_amount_custom_instructions = [SentinelCustomInstruction("due_amount")]
        penalty_interest_capitalisation_instructions = [
            SentinelCustomInstruction("penalty_capitalisation")
        ]
        due_notification = SentinelAccountNotificationDirective("due_notification")
        update_overdue_event_type_directive = SentinelUpdateAccountEventTypeDirective(
            "check_overdue"
        )
        update_balloon_event_type_directive = SentinelUpdateAccountEventTypeDirective(
            "balloon_payment"
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "repayment_period": Decimal("1"),
                "amortisation_method": "declining_principal",
                "due_amount_calculation_day": 1,
            }
        )
        mock_get_due_amount_custom_instructions.return_value = due_amount_custom_instructions
        mock_handle_penalty_interest_capitalisation.return_value = (
            penalty_interest_capitalisation_instructions
        )
        mock_get_repayment_due_notification.return_value = [due_notification]
        mock_update_check_overdue_schedule.return_value = [update_overdue_event_type_directive]
        mock_update_balloon_payment_schedule.return_value = [update_balloon_event_type_directive]
        mock_should_enable_balloon_payment_schedule.return_value = True

        # construct expected result
        expected_ci = due_amount_custom_instructions + penalty_interest_capitalisation_instructions
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_ci,  # type: ignore
                    client_batch_id=f"{loan.ACCOUNT_TYPE}_{DUE_AMOUNT_CALCULATION_EVENT}_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            update_account_event_type_directives=[
                update_overdue_event_type_directive,
                update_balloon_event_type_directive,
            ],
            account_notification_directives=[due_notification],
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=DUE_AMOUNT_CALCULATION_EVENT
        )
        result = loan.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="amortisation_method", is_union=True),
                call(vault=mock_vault, name="repayment_period"),
                call(vault=mock_vault, name="due_amount_calculation_day"),
            ]
        )
        mock_update_check_overdue_schedule.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            repayment_period=1,
        )
        mock_get_due_amount_custom_instructions.assert_called_once_with(
            vault=mock_vault, hook_arguments=hook_args
        )
        mock_get_repayment_due_notification.assert_called_once_with(
            vault=mock_vault,
            due_amount_custom_instructions=due_amount_custom_instructions,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_handle_penalty_interest_capitalisation.assert_called_once_with(
            vault=mock_vault, account_type="LOAN"
        )
        mock_update_due_amount_calculation_day_schedule.assert_not_called()
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )

    @patch.object(loan, "_update_due_amount_calculation_day_schedule")
    @patch.object(loan, "_get_due_amount_custom_instructions")
    @patch.object(loan.repayment_holiday, "is_due_amount_calculation_blocked")
    @patch.object(loan, "_should_enable_balloon_payment_schedule")
    def test_due_amount_calculation_event_no_instructions_no_due_calc_schedule_changes(
        self,
        mock_should_enable_balloon_payment_schedule: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_get_due_amount_custom_instructions: MagicMock,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
        mock_get_parameter: MagicMock,
        mock_handle_penalty_interest_capitalisation: MagicMock,
    ):
        # construct mocks
        mock_is_due_amount_calculation_blocked.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "repayment_period": Decimal("1"),
                "amortisation_method": "declining_principal",
                "due_amount_calculation_day": 1,
            }
        )
        mock_get_due_amount_custom_instructions.return_value = []
        mock_handle_penalty_interest_capitalisation.return_value = []
        mock_should_enable_balloon_payment_schedule.return_value = False

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=DUE_AMOUNT_CALCULATION_EVENT
        )
        result = loan.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)
        mock_get_due_amount_custom_instructions.assert_called_once_with(
            vault=sentinel.vault, hook_arguments=hook_args
        )
        mock_handle_penalty_interest_capitalisation.assert_called_once_with(
            vault=sentinel.vault, account_type="LOAN"
        )
        mock_update_due_amount_calculation_day_schedule.assert_not_called()
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )

    @patch.object(loan, "_update_due_amount_calculation_day_schedule")
    @patch.object(loan, "_get_due_amount_custom_instructions")
    @patch.object(loan.repayment_holiday, "is_due_amount_calculation_blocked")
    @patch.object(loan, "_should_enable_balloon_payment_schedule")
    def test_due_amount_calculation_event_reschedule_after_parameter_change(
        self,
        mock_should_enable_balloon_payment_schedule: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_get_due_amount_custom_instructions: MagicMock,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
        mock_get_parameter: MagicMock,
        mock_handle_penalty_interest_capitalisation: MagicMock,
    ):
        # construct mocks
        mock_is_due_amount_calculation_blocked.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "repayment_period": Decimal("1"),
                "amortisation_method": "declining_principal",
                "due_amount_calculation_day": 10,
            }
        )
        mock_should_enable_balloon_payment_schedule.return_value = False
        mock_get_due_amount_custom_instructions.return_value = []
        mock_handle_penalty_interest_capitalisation.return_value = []
        mock_update_due_amount_calculation_day_schedule.return_value = [
            SentinelUpdateAccountEventTypeDirective("due_amount_calc")
        ]

        # construct expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[],
            update_account_event_type_directives=[
                SentinelUpdateAccountEventTypeDirective("due_amount_calc")
            ],
            account_notification_directives=[],
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=DUE_AMOUNT_CALCULATION_EVENT
        )
        result = loan.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)
        mock_get_due_amount_custom_instructions.assert_called_once_with(
            vault=sentinel.vault, hook_arguments=hook_args
        )
        mock_handle_penalty_interest_capitalisation.assert_called_once_with(
            vault=sentinel.vault, account_type="LOAN"
        )
        mock_update_due_amount_calculation_day_schedule.assert_called_once_with(
            sentinel.vault, DEFAULT_DATETIME + relativedelta(months=1, day=10), 10
        )
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )

    @patch.object(loan, "_should_repayment_holiday_increase_tracker_balance")
    @patch.object(loan.repayment_holiday, "is_due_amount_calculation_blocked")
    def test_due_amount_calculation_repayment_blocked_impact_increase_emi(
        self,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_should_repayment_holiday_increase_tracker_balance: MagicMock,
        mock_get_parameter: MagicMock,
        mock_handle_penalty_interest_capitalisation: MagicMock,
    ):
        mock_is_due_amount_calculation_blocked.return_value = True
        mock_should_repayment_holiday_increase_tracker_balance.return_value = False
        mock_handle_penalty_interest_capitalisation.return_value = []
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": "declining_principal",
                "due_amount_calculation_day": 1,
            }
        )

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=DUE_AMOUNT_CALCULATION_EVENT
        )
        self.assertIsNone(loan.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args))
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
        mock_should_repayment_holiday_increase_tracker_balance.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_method="declining_principal",
        )

    @patch.object(loan.utils, "standard_instruction_details")
    @patch.object(loan.due_amount_calculation, "update_due_amount_calculation_counter")
    @patch.object(loan, "_should_repayment_holiday_increase_tracker_balance")
    @patch.object(loan.repayment_holiday, "is_due_amount_calculation_blocked")
    def test_due_amount_calculation_repayment_blocked_impact_increase_term(
        self,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_should_repayment_holiday_increase_tracker_balance: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_get_parameter: MagicMock,
        mock_handle_penalty_interest_capitalisation: MagicMock,
    ):
        mock_is_due_amount_calculation_blocked.return_value = True
        mock_should_repayment_holiday_increase_tracker_balance.return_value = True
        mock_handle_penalty_interest_capitalisation.return_value = []
        mock_update_due_amount_calculation_counter.return_value = DEFAULT_POSTINGS
        mock_standard_instruction_details.return_value = {"key": "value"}
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": "declining_principal",
                "due_amount_calculation_day": 1,
                "denomination": sentinel.denomination,
            }
        )
        mock_vault = self.create_mock()

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=DUE_AMOUNT_CALCULATION_EVENT
        )
        expected = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        CustomInstruction(
                            postings=DEFAULT_POSTINGS,
                            instruction_details={"key": "value"},
                            override_all_restrictions=True,
                        ),
                    ],
                    client_batch_id="LOAN_DUE_AMOUNT_CALCULATION_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        self.assertEqual(
            loan.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args), expected
        )
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )
        mock_should_repayment_holiday_increase_tracker_balance.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_method="declining_principal",
        )
        mock_update_due_amount_calculation_counter.assert_called_once_with(
            account_id=ACCOUNT_ID, denomination=sentinel.denomination
        )
        mock_standard_instruction_details.assert_called_once_with(
            description="Updating due amount calculation counter",
            event_type=DUE_AMOUNT_CALCULATION_EVENT,
            gl_impacted=False,
            account_type=loan.ACCOUNT_TYPE,
        )


@patch.object(loan.repayment_holiday, "is_overdue_amount_calculation_blocked")
@patch.object(loan.overdue, "schedule_logic")
class LoanCheckOverdueScheduleEvent(LoanTestBase):
    common_params = {
        "denomination": sentinel.denomination,
        "late_repayment_fee": Decimal("25"),
        "late_repayment_fee_income_account": sentinel.late_repayment_fee_income_account,
        "amortisation_method": sentinel.amortisation_method,
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.overdue_custom_instructions = [
            cls.custom_instruction(
                cls,
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("10"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="PRINCIPAL_DUE",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("10"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="PRINCIPAL_OVERDUE",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ],
            ),
            cls.custom_instruction(
                cls,
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("11"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="INTEREST_DUE",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("11"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="INTEREST_OVERDUE",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ],
            ),
        ]

        cls.expected_overdue_posting_balances = {
            BalanceCoordinate(
                account_address=lending_addresses.PRINCIPAL_DUE,
                asset=DEFAULT_ASSET,
                denomination="GBP",
                phase=Phase.COMMITTED,
            ): Balance(credit=Decimal("10"), debit=Decimal("0"), net=Decimal("-10")),
            BalanceCoordinate(
                account_address=lending_addresses.PRINCIPAL_OVERDUE,
                asset=DEFAULT_ASSET,
                denomination="GBP",
                phase=Phase.COMMITTED,
            ): Balance(credit=Decimal("0"), debit=Decimal("10"), net=Decimal("10")),
            BalanceCoordinate(
                account_address=lending_addresses.INTEREST_DUE,
                asset=DEFAULT_ASSET,
                denomination="GBP",
                phase=Phase.COMMITTED,
            ): Balance(credit=Decimal("11"), debit=Decimal("0"), net=Decimal("-11")),
            BalanceCoordinate(
                account_address=lending_addresses.INTEREST_OVERDUE,
                asset=DEFAULT_ASSET,
                denomination="GBP",
                phase=Phase.COMMITTED,
            ): Balance(credit=Decimal("0"), debit=Decimal("11"), net=Decimal("11")),
        }

    @patch.object(loan, "_update_check_overdue_schedule")
    @patch.object(loan.utils, "get_parameter")
    def test_check_overdue_with_no_overdue_custom_instructions(
        self,
        mock_get_parameter: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_schedule_logic: MagicMock,
        mock_is_overdue_amount_calculation_blocked: MagicMock,
    ):
        # construct mocks
        mock_is_overdue_amount_calculation_blocked.return_value = False
        mock_schedule_logic.return_value = [], []
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": "declining_principal"}
        )
        update_overdue_event_type_directive = SentinelUpdateAccountEventTypeDirective("overdue")
        mock_update_check_overdue_schedule.return_value = [update_overdue_event_type_directive]
        mock_vault = self.create_mock()
        expected_result = ScheduledEventHookResult(
            update_account_event_type_directives=[
                update_overdue_event_type_directive,
            ],
        )
        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.overdue.CHECK_OVERDUE_EVENT
        )

        result = loan.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

        mock_schedule_logic.assert_called_once_with(vault=mock_vault, hook_arguments=hook_args)

    @patch.object(loan.utils, "get_parameter")
    def test_check_overdue_with_blocking_flags(
        self,
        mock_get_parameter: MagicMock,
        mock_schedule_logic: MagicMock,
        mock_is_overdue_amount_calculation_blocked: MagicMock,
    ):
        mock_is_overdue_amount_calculation_blocked.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": "declining_principal"}
        )
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.overdue.CHECK_OVERDUE_EVENT
        )
        self.assertIsNone(loan.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args))

        mock_schedule_logic.assert_not_called()

    @patch.object(loan, "_update_check_overdue_schedule")
    @patch.object(loan, "_handle_delinquency")
    @patch.object(loan, "_get_overdue_repayment_notification")
    @patch.object(loan, "_charge_late_repayment_fee")
    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.interest_accrual_common, "update_schedule_events_skip")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    def test_check_overdue_with_overdue_custom_instructions(
        self,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_update_schedule_events_skip: MagicMock,
        mock_get_parameter: MagicMock,
        mock_charge_late_repayment_fee: MagicMock,
        mock_get_overdue_repayment_notification: MagicMock,
        mock_handle_delinquency: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_schedule_logic: MagicMock,
        mock_is_overdue_amount_calculation_blocked: MagicMock,
    ):
        # construct mocks
        mock_is_overdue_amount_calculation_blocked.return_value = False
        mock_vault = self.create_mock()
        fee_custom_instructions = [SentinelCustomInstruction("fee")]
        update_overdue_event_type_directive = SentinelUpdateAccountEventTypeDirective("overdue")
        mock_update_check_overdue_schedule.return_value = [update_overdue_event_type_directive]
        mock_schedule_logic.return_value = self.overdue_custom_instructions, []

        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters={**self.common_params})

        mock_charge_late_repayment_fee.return_value = fee_custom_instructions

        overdue_notification = SentinelAccountNotificationDirective("overdue_notification")
        mock_get_overdue_repayment_notification.return_value = [overdue_notification]

        delinquency_notification = SentinelAccountNotificationDirective("delinquency_notification")
        update_delinquency_event_type_directive = SentinelUpdateAccountEventTypeDirective(
            "delinquency_event"
        )

        mock_handle_delinquency.return_value = (
            [delinquency_notification],
            [update_delinquency_event_type_directive],
        )

        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False

        expected_posting_instructions = self.overdue_custom_instructions + fee_custom_instructions

        # construct expected result
        expected_notifications = [overdue_notification, delinquency_notification]
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_posting_instructions,
                    client_batch_id=f"{loan.ACCOUNT_TYPE}_{loan.overdue.CHECK_OVERDUE_EVENT}"
                    "_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            update_account_event_type_directives=[
                update_overdue_event_type_directive,
                update_delinquency_event_type_directive,
            ],
            account_notification_directives=expected_notifications,  # type: ignore
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.overdue.CHECK_OVERDUE_EVENT
        )
        result = loan.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)
        mock_schedule_logic.assert_called_once_with(vault=mock_vault, hook_arguments=hook_args)

        mock_charge_late_repayment_fee.assert_called_once_with(
            vault=mock_vault,
            event_type=loan.overdue.CHECK_OVERDUE_EVENT,
            denomination=sentinel.denomination,
            amount=Decimal("25"),
        )

        mock_get_overdue_repayment_notification.assert_called_once_with(
            account_id=ACCOUNT_ID,
            balances=self.expected_overdue_posting_balances,
            denomination=sentinel.denomination,
            late_repayment_fee=Decimal("25"),
            effective_datetime=DEFAULT_DATETIME,
        )

        mock_handle_delinquency.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            is_delinquency_schedule_event=False,
            balances=self.expected_overdue_posting_balances,
        )
        mock_update_schedule_events_skip.assert_not_called()

    @patch.object(loan, "_update_check_overdue_schedule")
    @patch.object(loan, "_handle_delinquency")
    @patch.object(loan, "_get_overdue_repayment_notification")
    @patch.object(loan, "_charge_late_repayment_fee")
    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.interest_accrual_common, "update_schedule_events_skip")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    def test_flat_interest_check_overdue_with_overdue_custom_instructions(
        self,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_update_schedule_events_skip: MagicMock,
        mock_get_parameter: MagicMock,
        mock_charge_late_repayment_fee: MagicMock,
        mock_get_overdue_repayment_notification: MagicMock,
        mock_handle_delinquency: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_schedule_logic: MagicMock,
        mock_is_overdue_amount_calculation_blocked: MagicMock,
    ):
        # construct mocks
        mock_is_overdue_amount_calculation_blocked.return_value = False
        mock_vault = self.create_mock()
        update_overdue_event_type_directive = SentinelUpdateAccountEventTypeDirective("overdue")
        mock_update_check_overdue_schedule.return_value = [update_overdue_event_type_directive]
        fee_custom_instructions = [SentinelCustomInstruction("fee")]
        mock_schedule_logic.return_value = self.overdue_custom_instructions, []

        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters={**self.common_params})

        mock_charge_late_repayment_fee.return_value = fee_custom_instructions

        overdue_notification = SentinelAccountNotificationDirective("overdue_notification")
        mock_get_overdue_repayment_notification.return_value = [overdue_notification]

        delinquency_notification = SentinelAccountNotificationDirective("delinquency_notification")
        update_delinquency_event_type_directive = SentinelUpdateAccountEventTypeDirective(
            "delinquency_event"
        )

        mock_handle_delinquency.return_value = (
            [delinquency_notification],
            [update_delinquency_event_type_directive],
        )
        update_interest_event_directive = SentinelUpdateAccountEventTypeDirective(
            "update_interest_accrual"
        )
        mock_update_schedule_events_skip.return_value = [update_interest_event_directive]
        mock_is_flat_interest_loan.return_value = True
        mock_is_rule_of_78_loan.return_value = False

        expected_posting_instructions = self.overdue_custom_instructions + fee_custom_instructions

        # construct expected result
        expected_notifications = [overdue_notification, delinquency_notification]
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_posting_instructions,
                    client_batch_id=f"{loan.ACCOUNT_TYPE}_{loan.overdue.CHECK_OVERDUE_EVENT}"
                    "_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            update_account_event_type_directives=[
                update_overdue_event_type_directive,
                update_delinquency_event_type_directive,
                update_interest_event_directive,
            ],
            account_notification_directives=expected_notifications,  # type: ignore
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.overdue.CHECK_OVERDUE_EVENT
        )
        result = loan.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)
        mock_schedule_logic.assert_called_once_with(vault=mock_vault, hook_arguments=hook_args)

        mock_charge_late_repayment_fee.assert_called_once_with(
            vault=mock_vault,
            event_type=loan.overdue.CHECK_OVERDUE_EVENT,
            denomination=sentinel.denomination,
            amount=Decimal("25"),
        )

        mock_get_overdue_repayment_notification.assert_called_once_with(
            account_id=ACCOUNT_ID,
            balances=self.expected_overdue_posting_balances,
            denomination=sentinel.denomination,
            late_repayment_fee=Decimal("25"),
            effective_datetime=DEFAULT_DATETIME,
        )

        mock_handle_delinquency.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            is_delinquency_schedule_event=False,
            balances=self.expected_overdue_posting_balances,
        )

    @patch.object(loan, "_update_check_overdue_schedule")
    @patch.object(loan, "_handle_delinquency")
    @patch.object(loan, "_get_overdue_repayment_notification")
    @patch.object(loan, "_charge_late_repayment_fee")
    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.interest_accrual_common, "update_schedule_events_skip")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    def test_rule_of_78_check_overdue_with_overdue_custom_instructions(
        self,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_update_schedule_events_skip: MagicMock,
        mock_get_parameter: MagicMock,
        mock_charge_late_repayment_fee: MagicMock,
        mock_get_overdue_repayment_notification: MagicMock,
        mock_handle_delinquency: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_schedule_logic: MagicMock,
        mock_is_overdue_amount_calculation_blocked: MagicMock,
    ):
        # construct mocks
        mock_is_overdue_amount_calculation_blocked.return_value = False
        mock_vault = self.create_mock()
        update_overdue_event_type_directive = SentinelUpdateAccountEventTypeDirective("overdue")
        mock_update_check_overdue_schedule.return_value = [update_overdue_event_type_directive]
        fee_custom_instructions = [SentinelCustomInstruction("fee")]
        mock_schedule_logic.return_value = self.overdue_custom_instructions, []

        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters={**self.common_params})

        mock_charge_late_repayment_fee.return_value = fee_custom_instructions

        overdue_notification = SentinelAccountNotificationDirective("overdue_notification")
        mock_get_overdue_repayment_notification.return_value = [overdue_notification]

        delinquency_notification = SentinelAccountNotificationDirective("delinquency_notification")
        update_delinquency_event_type_directive = SentinelUpdateAccountEventTypeDirective(
            "delinquency_event"
        )

        mock_handle_delinquency.return_value = (
            [delinquency_notification],
            [update_delinquency_event_type_directive],
        )
        update_interest_event_directive = SentinelUpdateAccountEventTypeDirective(
            "update_interest_accrual"
        )
        mock_update_schedule_events_skip.return_value = [update_interest_event_directive]
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = True

        expected_posting_instructions = self.overdue_custom_instructions + fee_custom_instructions

        # construct expected result
        expected_notifications = [overdue_notification, delinquency_notification]
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_posting_instructions,
                    client_batch_id=f"{loan.ACCOUNT_TYPE}_{loan.overdue.CHECK_OVERDUE_EVENT}"
                    "_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            update_account_event_type_directives=[
                update_overdue_event_type_directive,
                update_delinquency_event_type_directive,
                update_interest_event_directive,
            ],
            account_notification_directives=expected_notifications,  # type: ignore
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.overdue.CHECK_OVERDUE_EVENT
        )
        result = loan.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)
        mock_schedule_logic.assert_called_once_with(vault=mock_vault, hook_arguments=hook_args)

        mock_charge_late_repayment_fee.assert_called_once_with(
            vault=mock_vault,
            event_type=loan.overdue.CHECK_OVERDUE_EVENT,
            denomination=sentinel.denomination,
            amount=Decimal("25"),
        )

        mock_get_overdue_repayment_notification.assert_called_once_with(
            account_id=ACCOUNT_ID,
            balances=self.expected_overdue_posting_balances,
            denomination=sentinel.denomination,
            late_repayment_fee=Decimal("25"),
            effective_datetime=DEFAULT_DATETIME,
        )

        mock_handle_delinquency.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            is_delinquency_schedule_event=False,
            balances=self.expected_overdue_posting_balances,
        )


@patch.object(loan, "_handle_delinquency")
@patch.object(loan.utils, "get_parameter")
class LoanCheckDelinquencyTest(LoanTestBase):
    def test_check_delinquency_handle_delinquency_returns_empty_lists(
        self, mock_get_parameter: MagicMock, mock_handle_delinquency: MagicMock
    ):
        # construct mocks
        mock_handle_delinquency.return_value = ([], [])
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": "declining_principal"}
        )
        mock_vault = self.create_mock()

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.CHECK_DELINQUENCY
        )
        result = loan.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertIsNone(result)

        mock_handle_delinquency.assert_called_once_with(
            vault=mock_vault, hook_arguments=hook_args, is_delinquency_schedule_event=True
        )

    def test_check_delinquency_handle_delinquency_returns_notification_and_schedule_update(
        self, mock_get_parameter: MagicMock, mock_handle_delinquency: MagicMock
    ):
        # construct mocks
        delinquency_notification = SentinelAccountNotificationDirective("delinquency_notification")
        update_event_type_directive = SentinelUpdateAccountEventTypeDirective("delinquency_event")
        mock_handle_delinquency.return_value = (
            [delinquency_notification],
            [update_event_type_directive],
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": "declining_principal"}
        )
        mock_vault = self.create_mock()

        # construct expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[],
            update_account_event_type_directives=[update_event_type_directive],
            account_notification_directives=[delinquency_notification],
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.CHECK_DELINQUENCY
        )
        result = loan.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

        mock_handle_delinquency.assert_called_once_with(
            vault=mock_vault, hook_arguments=hook_args, is_delinquency_schedule_event=True
        )


@patch.object(loan.utils, "get_parameter")
class BalloonPaymentScheduledEventTest(LoanTestBase):
    @patch.object(loan, "_update_check_overdue_schedule")
    @patch.object(loan, "_get_repayment_due_notification")
    @patch.object(loan, "_get_balloon_payment_custom_instructions")
    def test_balloon_payment_scheduled_event_directives(
        self,
        mock_get_balloon_payment_custom_instructions: MagicMock,
        mock_get_repayment_due_notification: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # construct mocks
        due_amount_calc = loan.due_amount_calculation
        mock_vault = self.create_mock(
            last_execution_datetimes={
                due_amount_calc.DUE_AMOUNT_CALCULATION_EVENT: sentinel.last_execution_datetime
            }
        )
        balloon_event_custom_instructions = [SentinelCustomInstruction("balloon_amount")]
        update_overdue_directive = SentinelUpdateAccountEventTypeDirective("overdue")
        mock_update_check_overdue_schedule.return_value = [update_overdue_directive]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "repayment_period": Decimal("1"),
                "amortisation_method": "no_repayment",
            }
        )
        mock_get_balloon_payment_custom_instructions.return_value = (
            balloon_event_custom_instructions
        )
        due_notification = SentinelAccountNotificationDirective("due_notification")
        mock_get_repayment_due_notification.return_value = [due_notification]
        # construct expected result

        expected_ci = balloon_event_custom_instructions
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_ci,  # type: ignore
                    client_batch_id=f"{loan.ACCOUNT_TYPE}_{BALLOON_PAYMENT_EVENT}_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            update_account_event_type_directives=[update_overdue_directive],
            account_notification_directives=[due_notification],
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=BALLOON_PAYMENT_EVENT
        )
        result = loan.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="amortisation_method", is_union=True),
                call(vault=mock_vault, name="repayment_period"),
            ]
        )
        mock_get_balloon_payment_custom_instructions.assert_called_once_with(
            vault=mock_vault, hook_arguments=hook_args
        )
        mock_update_check_overdue_schedule.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            repayment_period=1,
        )

    @patch.object(loan, "_get_balloon_payment_custom_instructions")
    def test_balloon_payment_scheduled_event_no_directives_returns_None(
        self,
        mock_get_balloon_payment_custom_instructions: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # construct mocks

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "repayment_period": Decimal("1"),
                "amortisation_method": "no_repayment",
            }
        )
        mock_get_balloon_payment_custom_instructions.return_value = []
        # construct expected result

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=BALLOON_PAYMENT_EVENT
        )
        result = loan.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)

        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault, name="amortisation_method", is_union=True
        )
        mock_get_balloon_payment_custom_instructions.assert_called_once_with(
            vault=sentinel.vault, hook_arguments=hook_args
        )


@patch.object(loan.utils, "get_parameter")
@patch.object(loan, "_get_interest_application_feature")
@patch.object(loan.balloon_payments, "schedule_logic")
@patch.object(loan.overpayment, "reset_due_amount_calc_overpayment_trackers")
@patch.object(loan.overpayment, "track_emi_principal_excess")
class BalloonPaymentCustomInstructionsTest(LoanTestBase):
    def test_balloon_payment_event_calculate_custom_instructions(
        self,
        mock_overpayment_track_emi_principal_excess: MagicMock,
        mock_overpayment_reset_tracker: MagicMock,
        mock_schedule_logic: MagicMock,
        mock_get_interest_application: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        due_amount_calc = loan.due_amount_calculation
        # construct mocks
        mock_balances = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.COMMITTED): Balance(
                    debit=Decimal("1"), net=Decimal("1")
                )
            }
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "EFFECTIVE_FETCHER": MagicMock(balances=mock_balances)
            },
            last_execution_datetimes={
                due_amount_calc.DUE_AMOUNT_CALCULATION_EVENT: sentinel.last_execution_datetime
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": "no_repayment",
                "denomination": sentinel.denomination,
                "capitalise_no_repayment_accrued_interest": "NO_CAPITALISATION",
            }
        )

        mock_get_interest_application.return_value = sentinel.interest_feature
        mock_schedule_logic.return_value = [SentinelCustomInstruction("schedule_logic_ci")]
        mock_overpayment_reset_tracker.return_value = [
            SentinelCustomInstruction("overpayment_reset_ci")
        ]
        mock_overpayment_track_emi_principal_excess.return_value = [
            SentinelCustomInstruction("overpayment_emi_principal")
        ]

        # construct expected result
        expected_results = (
            mock_schedule_logic.return_value
            + mock_overpayment_reset_tracker.return_value
            + mock_overpayment_track_emi_principal_excess.return_value
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=BALLOON_PAYMENT_EVENT
        )
        result = loan._get_balloon_payment_custom_instructions(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertListEqual(result, expected_results)

        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="denomination"),
                call(
                    vault=mock_vault, name="capitalise_no_repayment_accrued_interest", is_union=True
                ),
            ]
        )
        mock_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            account_type=loan.ACCOUNT_TYPE,
            interest_application_feature=sentinel.interest_feature,
            balances=mock_balances,
            denomination=sentinel.denomination,
        )

    @patch.object(loan.interest_capitalisation, "handle_interest_capitalisation")
    def test_balloon_payment_event_daily_capitalisation_calculate_custom_instructions(
        self,
        mock_interest_cap: MagicMock,
        mock_overpayment_track_emi_principal_excess: MagicMock,
        mock_overpayment_reset_tracker: MagicMock,
        mock_schedule_logic: MagicMock,
        mock_get_interest_application: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        due_amount_calc = loan.due_amount_calculation
        # construct mocks
        mock_balances = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.COMMITTED): Balance(
                    debit=Decimal("1"), net=Decimal("1")
                )
            }
        )
        alt_mock_balances = BalanceDefaultDict(
            mapping={
                BalanceCoordinate("ALT", DEFAULT_ASSET, "GBP", Phase.COMMITTED): Balance(
                    debit=Decimal("1"), net=Decimal("1")
                )
            }
        )

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "EFFECTIVE_FETCHER": MagicMock(balances=mock_balances)
            },
            last_execution_datetimes={
                due_amount_calc.DUE_AMOUNT_CALCULATION_EVENT: sentinel.last_execution_datetime
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": "no_repayment",
                "denomination": sentinel.denomination,
                "capitalise_no_repayment_accrued_interest": "DAILY",
            }
        )

        def mock_balances_fn(**_):
            return alt_mock_balances

        mock_interest_cap.return_value = [MagicMock(balances=mock_balances_fn)]

        mock_get_interest_application.return_value = sentinel.interest_feature
        mock_schedule_logic.return_value = [SentinelCustomInstruction("schedule_logic_ci")]
        mock_overpayment_reset_tracker.return_value = [
            SentinelCustomInstruction("overpayment_reset_ci")
        ]
        mock_overpayment_track_emi_principal_excess.return_value = [
            SentinelCustomInstruction("overpayment_emi_principal")
        ]

        # construct expected result
        expected_results = (
            mock_schedule_logic.return_value
            + mock_interest_cap.return_value
            + mock_overpayment_reset_tracker.return_value
            + mock_overpayment_track_emi_principal_excess.return_value
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=BALLOON_PAYMENT_EVENT
        )
        result = loan._get_balloon_payment_custom_instructions(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertListEqual(result, expected_results)

        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="denomination"),
                call(
                    vault=mock_vault, name="capitalise_no_repayment_accrued_interest", is_union=True
                ),
            ]
        )
        mock_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            account_type=loan.ACCOUNT_TYPE,
            interest_application_feature=sentinel.interest_feature,
            balances=mock_balances,
            denomination=sentinel.denomination,
        )
