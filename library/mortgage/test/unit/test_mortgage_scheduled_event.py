# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from unittest.mock import MagicMock, patch, sentinel

# library
import library.mortgage.contracts.template.mortgage as mortgage
from library.mortgage.test.unit.test_mortgage_common import MortgageTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import ScheduledEventHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DATETIME,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
    PostingInstructionsDirective,
    ScheduledEventHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelAccountNotificationDirective,
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelPosting,
    SentinelUpdateAccountEventTypeDirective,
)


@patch.object(mortgage, "_get_standard_interest_accrual_custom_instructions")
@patch.object(mortgage, "_handle_interest_capitalisation")
@patch.object(mortgage, "_get_penalty_interest_accrual_custom_instruction")
class AccrualScheduledEventTest(MortgageTestBase):
    event_type = mortgage.interest_accrual.ACCRUAL_EVENT

    def test_interest_accrual_with_instructions(
        self,
        mock_get_penalty_interest_accrual_custom_instruction: MagicMock,
        mock_handle_interest_capitalisation: MagicMock,
        mock_get_standard_interest_accrual_custom_instructions: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
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
                    client_batch_id=f"{mortgage.ACCOUNT_TYPE}_{self.event_type}_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=self.event_type
        )
        result = mortgage.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

    def test_interest_accrual_no_accrual_instructions(
        self,
        mock_get_penalty_interest_accrual_custom_instruction: MagicMock,
        mock_handle_interest_capitalisation: MagicMock,
        mock_get_standard_interest_accrual_custom_instructions: MagicMock,
    ):
        mock_get_penalty_interest_accrual_custom_instruction.return_value = []
        mock_handle_interest_capitalisation.return_value = []
        mock_get_standard_interest_accrual_custom_instructions.return_value = []

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=self.event_type
        )
        result = mortgage.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)


class StandardInterestAccrualTest(MortgageTestBase):
    @patch.object(mortgage.repayment_holiday, "is_due_amount_calculation_blocked")
    @patch.object(mortgage.fixed_to_variable, "InterestRate")
    @patch.object(mortgage.overpayment, "track_interest_on_expected_principal")
    @patch.object(mortgage.interest_accrual, "daily_accrual_logic")
    def test_get_standard_interest_accrual_custom_instructions(
        self,
        mock_daily_accrual_logic: MagicMock,
        mock_track_interest_on_expected_principal: MagicMock,
        mock_interest_rate_feature: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
    ):
        accrual_instructions = [SentinelCustomInstruction("accrual")]
        mock_daily_accrual_logic.return_value = accrual_instructions
        expected_accrual_instructions = [SentinelCustomInstruction("expected_accrual")]
        mock_track_interest_on_expected_principal.return_value = expected_accrual_instructions
        mock_is_due_amount_calculation_blocked.return_value = False

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=sentinel.event_type
        )
        result = mortgage._get_standard_interest_accrual_custom_instructions(
            vault=sentinel.vault,
            hook_arguments=hook_args,
            inflight_postings=[sentinel.inflight_postings],
        )

        self.assertEqual(result, accrual_instructions + expected_accrual_instructions)
        mock_daily_accrual_logic.assert_called_once_with(
            vault=sentinel.vault,
            hook_arguments=hook_args,
            account_type=mortgage.ACCOUNT_TYPE,
            interest_rate_feature=mock_interest_rate_feature,
            principal_addresses=[mortgage.lending_addresses.PRINCIPAL],
            inflight_postings=[sentinel.inflight_postings],
            customer_accrual_address=None,
            accrual_internal_account=None,
        )
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )

    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.repayment_holiday, "is_due_amount_calculation_blocked")
    @patch.object(mortgage.fixed_to_variable, "InterestRate")
    @patch.object(mortgage.overpayment, "track_interest_on_expected_principal")
    @patch.object(mortgage.interest_accrual, "daily_accrual_logic")
    def test_get_interest_accrual_custom_instructions_during_repayment_holiday(
        self,
        mock_daily_accrual_logic: MagicMock,
        mock_track_interest_on_expected_principal: MagicMock,
        mock_interest_rate_feature: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        accrual_instructions = [SentinelCustomInstruction("accrual")]
        mock_daily_accrual_logic.return_value = accrual_instructions
        mock_is_due_amount_calculation_blocked.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                mortgage.interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: (
                    sentinel.capitalised_interest_receivable_account
                )
            }
        )
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=sentinel.event_type
        )
        result = mortgage._get_standard_interest_accrual_custom_instructions(
            vault=sentinel.vault,
            hook_arguments=hook_args,
            inflight_postings=[sentinel.inflight_postings],
        )

        self.assertEqual(result, accrual_instructions)
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
        mock_daily_accrual_logic.assert_called_once_with(
            vault=sentinel.vault,
            hook_arguments=hook_args,
            account_type=mortgage.ACCOUNT_TYPE,
            interest_rate_feature=mock_interest_rate_feature,
            principal_addresses=[mortgage.lending_addresses.PRINCIPAL],
            inflight_postings=[sentinel.inflight_postings],
            customer_accrual_address=(mortgage.ACCRUED_INTEREST_PENDING_CAPITALISATION),
            accrual_internal_account=sentinel.capitalised_interest_receivable_account,
        )
        mock_track_interest_on_expected_principal.assert_not_called()


@patch.object(mortgage.repayment_holiday, "is_penalty_accrual_blocked")
class PenaltyInterestAccrualTest(MortgageTestBase):
    common_params: dict[str, Any] = {
        "denomination": sentinel.denomination,
        "penalty_compounds_overdue_interest": sentinel.penalty_compounds_overdue_interest,
        "days_in_year": sentinel.days_in_year,
        "penalty_interest_rate": Decimal("0.1"),
        "penalty_includes_base_rate": sentinel.penalty_includes_base_rate,
        "application_precision": sentinel.application_precision,
        "penalty_interest_received_account": sentinel.penalty_interest_received_account,
        "capitalise_penalty_interest": False,
    }

    def test_get_penalty_interest_accrual_custom_instruction_blocking_flag(
        self, mock_is_penalty_accrual_blocked: MagicMock
    ):
        mock_is_penalty_accrual_blocked.return_value = True

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=mortgage.interest_accrual.ACCRUAL_EVENT
        )

        result = mortgage._get_penalty_interest_accrual_custom_instruction(
            vault=sentinel.vault, hook_arguments=hook_args
        )
        self.assertListEqual(result, [])
        mock_is_penalty_accrual_blocked.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
        )

    @patch.object(mortgage.interest_accrual_common, "daily_accrual")
    @patch.object(mortgage, "_get_overdue_capital")
    @patch.object(mortgage.fixed_to_variable, "get_annual_interest_rate")
    @patch.object(mortgage.utils, "get_parameter")
    def test_get_penalty_interest_accrual_custom_instruction_no_postings(
        self,
        mock_get_parameter: MagicMock,
        mock_get_annual_interest_rate: MagicMock,
        mock_get_overdue_capital: MagicMock,
        mock_daily_accrual: MagicMock,
        mock_is_penalty_accrual_blocked: MagicMock,
    ):
        mock_is_penalty_accrual_blocked.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_params)
        eod_balance_observation = SentinelBalancesObservation("eod_balance_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.EOD_FETCHER_ID: eod_balance_observation
            }
        )
        mock_get_annual_interest_rate.return_value = Decimal("0.2")
        mock_get_overdue_capital.return_value = sentinel.overdue_capital
        mock_daily_accrual.return_value = []

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=mortgage.interest_accrual.ACCRUAL_EVENT
        )

        result = mortgage._get_penalty_interest_accrual_custom_instruction(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertListEqual(result, [])
        mock_is_penalty_accrual_blocked.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

        mock_get_overdue_capital.assert_called_once_with(
            balances=eod_balance_observation.balances,
            denomination=sentinel.denomination,
            include_overdue_interest=sentinel.penalty_compounds_overdue_interest,
        )
        mock_daily_accrual.assert_called_once_with(
            customer_account=ACCOUNT_ID,
            customer_address=mortgage.lending_addresses.PENALTIES,
            denomination=sentinel.denomination,
            internal_account=sentinel.penalty_interest_received_account,
            payable=False,
            effective_balance=sentinel.overdue_capital,
            effective_datetime=DEFAULT_DATETIME,
            yearly_rate=Decimal("0.3"),
            days_in_year=sentinel.days_in_year,
            precision=sentinel.application_precision,
            rounding=ROUND_HALF_UP,
            account_type="MORTGAGE",
            event_type=mortgage.interest_accrual.ACCRUAL_EVENT,
        )

    @patch.object(mortgage.interest_accrual_common, "daily_accrual")
    @patch.object(mortgage, "_get_overdue_capital")
    @patch.object(mortgage.fixed_to_variable, "get_annual_interest_rate")
    @patch.object(mortgage.utils, "get_parameter")
    def test_get_penalty_interest_accrual_custom_instruction_with_postings(
        self,
        mock_get_parameter: MagicMock,
        mock_get_annual_interest_rate: MagicMock,
        mock_get_overdue_capital: MagicMock,
        mock_daily_accrual: MagicMock,
        mock_is_penalty_accrual_blocked: MagicMock,
    ):
        mock_is_penalty_accrual_blocked.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_params)
        eod_balance_observation = SentinelBalancesObservation("eod_balance_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.EOD_FETCHER_ID: eod_balance_observation
            }
        )
        mock_get_annual_interest_rate.return_value = Decimal("0.2")
        mock_get_overdue_capital.return_value = sentinel.overdue_capital
        custom_instructions = [SentinelCustomInstruction("penalty_accrual")]
        mock_daily_accrual.return_value = custom_instructions

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=mortgage.interest_accrual.ACCRUAL_EVENT
        )

        result = mortgage._get_penalty_interest_accrual_custom_instruction(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertListEqual(result, custom_instructions)

        mock_is_penalty_accrual_blocked.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

        mock_get_overdue_capital.assert_called_once_with(
            balances=eod_balance_observation.balances,
            denomination=sentinel.denomination,
            include_overdue_interest=sentinel.penalty_compounds_overdue_interest,
        )
        mock_daily_accrual.assert_called_once_with(
            customer_account=ACCOUNT_ID,
            customer_address=mortgage.lending_addresses.PENALTIES,
            denomination=sentinel.denomination,
            internal_account=sentinel.penalty_interest_received_account,
            payable=False,
            effective_balance=sentinel.overdue_capital,
            effective_datetime=DEFAULT_DATETIME,
            yearly_rate=Decimal("0.3"),
            days_in_year=sentinel.days_in_year,
            precision=sentinel.application_precision,
            rounding=ROUND_HALF_UP,
            account_type="MORTGAGE",
            event_type=mortgage.interest_accrual.ACCRUAL_EVENT,
        )

    @patch.object(mortgage.interest_accrual_common, "daily_accrual")
    @patch.object(mortgage, "_get_overdue_capital")
    @patch.object(mortgage.fixed_to_variable, "get_annual_interest_rate")
    @patch.object(mortgage.utils, "get_parameter")
    def test_get_penalty_interest_accrual_custom_instruction_with_capitalisation_with_postings(
        self,
        mock_get_parameter: MagicMock,
        mock_get_annual_interest_rate: MagicMock,
        mock_get_overdue_capital: MagicMock,
        mock_daily_accrual: MagicMock,
        mock_is_penalty_accrual_blocked: MagicMock,
    ):
        mock_is_penalty_accrual_blocked.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_params
            | {
                "accrual_precision": sentinel.accrual_precision,
                "capitalise_penalty_interest": True,
                "capitalised_interest_receivable_account": (
                    sentinel.capitalised_interest_receivable_account
                ),
            }
        )
        eod_balance_observation = SentinelBalancesObservation("eod_balance_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.EOD_FETCHER_ID: eod_balance_observation
            }
        )
        mock_get_annual_interest_rate.return_value = Decimal("0.2")
        mock_get_overdue_capital.return_value = sentinel.overdue_capital
        custom_instructions = [SentinelCustomInstruction("penalty_accrual")]
        mock_daily_accrual.return_value = custom_instructions

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=mortgage.interest_accrual.ACCRUAL_EVENT
        )

        result = mortgage._get_penalty_interest_accrual_custom_instruction(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertListEqual(result, custom_instructions)

        mock_is_penalty_accrual_blocked.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

        mock_get_overdue_capital.assert_called_once_with(
            balances=eod_balance_observation.balances,
            denomination=sentinel.denomination,
            include_overdue_interest=sentinel.penalty_compounds_overdue_interest,
        )
        mock_daily_accrual.assert_called_once_with(
            customer_account=ACCOUNT_ID,
            customer_address=(mortgage.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION),
            denomination=sentinel.denomination,
            internal_account=sentinel.capitalised_interest_receivable_account,
            payable=False,
            effective_balance=sentinel.overdue_capital,
            effective_datetime=DEFAULT_DATETIME,
            yearly_rate=Decimal("0.3"),
            days_in_year=sentinel.days_in_year,
            precision=sentinel.accrual_precision,
            rounding=ROUND_HALF_UP,
            account_type="MORTGAGE",
            event_type=mortgage.interest_accrual.ACCRUAL_EVENT,
        )


@patch.object(mortgage, "_should_handle_interest_capitalisation")
@patch.object(mortgage.interest_capitalisation, "handle_interest_capitalisation")
class HandleInterestCapitalisationTest(MortgageTestBase):
    def test_handle_interest_capitalisation_no_optional_args(
        self,
        mock_handle_interest_capitalisation: MagicMock,
        mock_should_handle_interest_capitalisation: MagicMock,
    ):
        mock_should_handle_interest_capitalisation.return_value = True
        mock_handle_interest_capitalisation.return_value = [sentinel.custom_instruction]
        result = mortgage._handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            account_type=sentinel.account_type,
        )

        self.assertListEqual([sentinel.custom_instruction], result)

        mock_should_handle_interest_capitalisation.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        mock_handle_interest_capitalisation.assert_called_once_with(
            vault=sentinel.vault,
            account_type=sentinel.account_type,
            balances=None,
            interest_to_capitalise_address="ACCRUED_INTEREST_PENDING_CAPITALISATION",
        )

    def test_handle_interest_capitalisation_with_optional_args(
        self,
        mock_handle_interest_capitalisation: MagicMock,
        mock_should_handle_interest_capitalisation: MagicMock,
    ):
        mock_should_handle_interest_capitalisation.return_value = True
        mock_handle_interest_capitalisation.return_value = [sentinel.custom_instruction]
        result = mortgage._handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            account_type=sentinel.account_type,
            balances=sentinel.balances,
            interest_to_capitalise_address=sentinel.address,
        )

        self.assertListEqual([sentinel.custom_instruction], result)

        mock_should_handle_interest_capitalisation.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        mock_handle_interest_capitalisation.assert_called_once_with(
            vault=sentinel.vault,
            account_type=sentinel.account_type,
            balances=sentinel.balances,
            interest_to_capitalise_address=sentinel.address,
        )

    def test_handle_interest_capitalisation_no_capitalisation(
        self,
        mock_handle_interest_capitalisation: MagicMock,
        mock_should_handle_interest_capitalisation: MagicMock,
    ):
        mock_should_handle_interest_capitalisation.return_value = False
        result = mortgage._handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            account_type=sentinel.account_type,
        )

        self.assertListEqual([], result)

        mock_should_handle_interest_capitalisation.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        mock_handle_interest_capitalisation.assert_not_called


@patch.object(mortgage.interest_capitalisation, "handle_penalty_interest_capitalisation")
@patch.object(mortgage, "_get_due_amount_custom_instructions")
@patch.object(mortgage, "_handle_delinquency")
@patch.object(mortgage, "_charge_late_repayment_fee")
@patch.object(mortgage.overdue, "schedule_logic")
@patch.object(mortgage.utils, "is_flag_in_list_applied")
class DueAmountCalculationEventTest(MortgageTestBase):
    event_type = mortgage.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT

    def test_due_amount_event_with_no_instructions(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_overdue_schedule_logic: MagicMock,
        mock_charge_late_repayment_fee: MagicMock,
        mock_handle_delinquency: MagicMock,
        mock_get_due_amount_custom_instructions: MagicMock,
        mock_handle_penalty_interest_capitalisation: MagicMock,
    ):
        # construct mocks
        mock_is_flag_in_list_applied.return_value = False
        mock_overdue_schedule_logic.return_value = [], []
        mock_charge_late_repayment_fee.return_value = []
        mock_handle_delinquency.return_value = [], []
        mock_get_due_amount_custom_instructions.return_value = []
        mock_handle_penalty_interest_capitalisation.return_value = []

        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
        )
        result = mortgage.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)
        mock_get_due_amount_custom_instructions.assert_called_once_with(
            vault=sentinel.vault, hook_arguments=hook_args
        )

    def test_due_amount_event_with_instructions(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_overdue_schedule_logic: MagicMock,
        mock_charge_late_repayment_fee: MagicMock,
        mock_handle_delinquency: MagicMock,
        mock_get_due_amount_custom_instructions: MagicMock,
        mock_handle_penalty_interest_capitalisation: MagicMock,
    ):
        # expected values
        overdue_instructions = [SentinelCustomInstruction("overdue")]
        late_repayment_fee_instructions = [SentinelCustomInstruction("late_repayment_fee")]
        due_amount_instructions = [SentinelCustomInstruction("due_amount")]
        penalty_interest_instructions = [SentinelCustomInstruction("penalty_interest")]
        delinquency_event_updates = [SentinelUpdateAccountEventTypeDirective("delinquency")]
        delinquency_notifications = [SentinelAccountNotificationDirective("delinquency")]

        # construct mocks
        mock_vault = self.create_mock()
        mock_is_flag_in_list_applied.return_value = False
        mock_overdue_schedule_logic.return_value = overdue_instructions, []
        mock_charge_late_repayment_fee.return_value = late_repayment_fee_instructions
        mock_handle_delinquency.return_value = delinquency_notifications, delinquency_event_updates
        mock_get_due_amount_custom_instructions.return_value = due_amount_instructions
        mock_handle_penalty_interest_capitalisation.return_value = penalty_interest_instructions

        # construct expected result
        expected_instructions = [
            *overdue_instructions,
            *late_repayment_fee_instructions,
            *due_amount_instructions,
            *penalty_interest_instructions,
        ]
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_instructions,  # type: ignore
                    client_batch_id=f"{mortgage.ACCOUNT_TYPE}_{self.event_type}_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            account_notification_directives=delinquency_notifications,  # type: ignore
            update_account_event_type_directives=delinquency_event_updates,  # type: ignore
        )
        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
        )
        result = mortgage.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)
        mock_get_due_amount_custom_instructions.assert_called_once_with(
            vault=mock_vault, hook_arguments=hook_args
        )
        mock_handle_penalty_interest_capitalisation.assert_called_once_with(
            vault=mock_vault, account_type="MORTGAGE"
        )

    def test_due_amount_event_with_overdue_amount_blocking_flags(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_overdue_schedule_logic: MagicMock,
        mock_charge_late_repayment_fee: MagicMock,
        mock_handle_delinquency: MagicMock,
        mock_get_due_amount_custom_instructions: MagicMock,
        mock_handle_penalty_interest_capitalisation: MagicMock,
    ):
        # expected values
        due_amount_instructions = [SentinelCustomInstruction("due_amount")]
        penalty_interest_instructions = [SentinelCustomInstruction("penalty_interest")]

        # construct mocks
        mock_vault = self.create_mock()
        mock_is_flag_in_list_applied.return_value = True
        mock_get_due_amount_custom_instructions.return_value = due_amount_instructions
        mock_handle_penalty_interest_capitalisation.return_value = penalty_interest_instructions

        # construct expected result
        expected_instructions = [
            *due_amount_instructions,
            *penalty_interest_instructions,
        ]
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_instructions,  # type: ignore
                    client_batch_id=f"{mortgage.ACCOUNT_TYPE}_{self.event_type}_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )
        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
        )
        result = mortgage.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)
        mock_get_due_amount_custom_instructions.assert_called_once_with(
            vault=mock_vault, hook_arguments=hook_args
        )
        mock_handle_penalty_interest_capitalisation.assert_called_once_with(
            vault=mock_vault, account_type="MORTGAGE"
        )
        mock_overdue_schedule_logic.assert_not_called()
        mock_charge_late_repayment_fee.assert_not_called()
        mock_handle_delinquency.assert_not_called()


class DueAmountCalculationInstructionsTest(MortgageTestBase):
    event_type = mortgage.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT

    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.overpayment, "reset_due_amount_calc_overpayment_trackers")
    @patch.object(mortgage.overpayment, "track_emi_principal_excess")
    @patch.object(mortgage.due_amount_calculation, "schedule_logic")
    @patch.object(mortgage, "_is_within_interest_only_term")
    @patch.object(mortgage.repayment_holiday, "is_due_amount_calculation_blocked")
    def test_get_due_amount_custom_instructions_outside_interest_only_term(
        self,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_is_within_interest_only_term: MagicMock,
        mock_schedule_logic: MagicMock,
        mock_track_emi_principal_excess: MagicMock,
        mock_reset_due_amount_calc_overpayment_trackers: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # construct mocks
        effective_observation = SentinelBalancesObservation("effective")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: effective_observation
            },
            last_execution_datetimes={
                mortgage.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: sentinel.last_execution_datetime  # noqa: E501
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                mortgage.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_emi",
                mortgage.PARAM_DENOMINATION: sentinel.denomination,
            }
        )
        mock_is_due_amount_calculation_blocked.return_value = False
        mock_is_within_interest_only_term.return_value = False
        mock_schedule_logic.return_value = [sentinel.due_amount_custom_instructions]
        mock_reset_due_amount_calc_overpayment_trackers.return_value = [
            sentinel.overpayment_reset_tracker_cis
        ]
        mock_track_emi_principal_excess.return_value = [sentinel.emi_principal_excess_tracker_cis]

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=self.event_type
        )
        result = mortgage._get_due_amount_custom_instructions(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertEqual(
            result,
            [
                sentinel.due_amount_custom_instructions,
                sentinel.overpayment_reset_tracker_cis,
                sentinel.emi_principal_excess_tracker_cis,
            ],
        )

        mock_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            account_type=mortgage.ACCOUNT_TYPE,
            interest_application_feature=(mortgage.interest_application.InterestApplication),
            reamortisation_condition_features=[
                mortgage.overpayment.OverpaymentReamortisationCondition,
                mortgage.repayment_holiday.ReamortisationConditionWithoutPreference,
                mortgage.fixed_to_variable.ReamortisationCondition,
                mortgage.lending_interfaces.ReamortisationCondition(
                    should_trigger_reamortisation=mortgage._is_end_of_interest_only_term
                ),
            ],
            amortisation_feature=mortgage.declining_principal.AmortisationFeature,
            interest_rate_feature=mortgage.fixed_to_variable.InterestRate,
            principal_adjustment_features=[
                mortgage.lending_interfaces.PrincipalAdjustment(
                    calculate_principal_adjustment=mortgage.overpayment.calculate_principal_adjustment  # noqa: E501
                )
            ],
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
        )
        mock_reset_due_amount_calc_overpayment_trackers.assert_called_once_with(vault=mock_vault)
        mock_is_within_interest_only_term.assert_called_once_with(vault=mock_vault)
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )
        mock_track_emi_principal_excess.assert_called_once_with(
            vault=mock_vault,
            interest_application_feature=(mortgage.interest_application.InterestApplication),
            effective_datetime=DEFAULT_DATETIME,
            previous_application_datetime=sentinel.last_execution_datetime,
        )

    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.overpayment, "reset_due_amount_calc_overpayment_trackers")
    @patch.object(mortgage.overpayment, "track_emi_principal_excess")
    @patch.object(mortgage.due_amount_calculation, "schedule_logic")
    @patch.object(mortgage, "_is_within_interest_only_term")
    @patch.object(mortgage.repayment_holiday, "is_due_amount_calculation_blocked")
    def test_get_due_amount_custom_instructions_within_interest_only_term(
        self,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_is_within_interest_only_term: MagicMock,
        mock_schedule_logic: MagicMock,
        mock_track_emi_principal_excess: MagicMock,
        mock_reset_due_amount_calc_overpayment_trackers: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # construct mocks
        effective_observation = SentinelBalancesObservation("effective")
        mock_vault = self.create_mock(
            creation_date=sentinel.account_creation_datetime,
            balances_observation_fetchers_mapping={
                mortgage.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: effective_observation
            },
            last_execution_datetimes={
                mortgage.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: None
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                mortgage.PARAM_DENOMINATION: sentinel.denomination,
            }
        )
        mock_is_due_amount_calculation_blocked.return_value = False
        mock_is_within_interest_only_term.return_value = True
        mock_schedule_logic.return_value = [sentinel.due_amount_custom_instructions]
        mock_reset_due_amount_calc_overpayment_trackers.return_value = [
            sentinel.overpayment_reset_tracker_cis
        ]
        mock_track_emi_principal_excess.return_value = [sentinel.emi_principal_excess_tracker_cis]

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=self.event_type
        )
        result = mortgage._get_due_amount_custom_instructions(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertEqual(
            result,
            [
                sentinel.due_amount_custom_instructions,
                sentinel.overpayment_reset_tracker_cis,
                sentinel.emi_principal_excess_tracker_cis,
            ],
        )

        mock_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            account_type=mortgage.ACCOUNT_TYPE,
            interest_application_feature=(mortgage.interest_application.InterestApplication),
            reamortisation_condition_features=[],
            amortisation_feature=mortgage.declining_principal.AmortisationFeature,
            interest_rate_feature=mortgage.fixed_to_variable.InterestRate,
            principal_adjustment_features=[
                mortgage.lending_interfaces.PrincipalAdjustment(
                    calculate_principal_adjustment=mortgage.overpayment.calculate_principal_adjustment  # noqa: E501
                )
            ],
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
        )

        mock_reset_due_amount_calc_overpayment_trackers.assert_called_once_with(vault=mock_vault)
        mock_is_within_interest_only_term.assert_called_once_with(vault=mock_vault)
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )
        mock_track_emi_principal_excess.assert_called_once_with(
            vault=mock_vault,
            interest_application_feature=(mortgage.interest_application.InterestApplication),
            effective_datetime=DEFAULT_DATETIME,
            previous_application_datetime=sentinel.account_creation_datetime,
        )

    @patch.object(mortgage.utils, "standard_instruction_details")
    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.overpayment, "track_emi_principal_excess")
    @patch.object(mortgage.overpayment, "reset_due_amount_calc_overpayment_trackers")
    @patch.object(mortgage.due_amount_calculation, "update_due_amount_calculation_counter")
    @patch.object(mortgage.due_amount_calculation, "schedule_logic")
    @patch.object(mortgage, "_is_within_interest_only_term")
    @patch.object(mortgage.repayment_holiday, "is_due_amount_calculation_blocked")
    def test_get_due_amount_custom_instructions_with_blocking_flags(
        self,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_is_within_interest_only_term: MagicMock,
        mock_schedule_logic: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_reset_due_amount_calc_overpayment_trackers: MagicMock,
        mock_track_emi_principal_excess: MagicMock,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        # construct mocks
        mock_is_due_amount_calculation_blocked.return_value = True
        mock_update_due_amount_calculation_counter.return_value = [SentinelPosting("counter")]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {mortgage.PARAM_DENOMINATION: sentinel.denomination}
        )
        mock_standard_instruction_details.return_value = {"sentinel": "dict"}
        mock_vault = self.create_mock()

        expected = [
            CustomInstruction(
                postings=[SentinelPosting("counter")],
                instruction_details={"sentinel": "dict"},
                override_all_restrictions=True,
            )
        ]

        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=self.event_type
        )
        result = mortgage._get_due_amount_custom_instructions(
            vault=mock_vault, hook_arguments=hook_args
        )

        self.assertListEqual(result, expected)

        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )
        mock_update_due_amount_calculation_counter.assert_called_once_with(
            account_id=ACCOUNT_ID, denomination=sentinel.denomination
        )
        mock_schedule_logic.assert_not_called()
        mock_is_within_interest_only_term.assert_not_called()
        mock_reset_due_amount_calc_overpayment_trackers.assert_not_called()
        mock_track_emi_principal_excess.assert_not_called()


class CheckDelinquencyEventTest(MortgageTestBase):
    event_type = mortgage.CHECK_DELINQUENCY

    @patch.object(mortgage, "_handle_delinquency")
    def test_scheduled_event_hook_returns_notification_when_delinquent(
        self, mock_handle_delinquency: MagicMock
    ):
        # expected values
        delinquency_event_updates = SentinelUpdateAccountEventTypeDirective("delinquency")
        delinquency_notifications = SentinelAccountNotificationDirective("delinquency")

        # construct mocks
        mock_handle_delinquency.return_value = [delinquency_notifications], [
            delinquency_event_updates
        ]

        # construct expected result
        expected_result = ScheduledEventHookResult(
            account_notification_directives=[delinquency_notifications],
            update_account_event_type_directives=[delinquency_event_updates],
        )

        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=self.event_type
        )
        result = mortgage.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)
        mock_handle_delinquency.assert_called_once_with(
            vault=sentinel.vault,
            hook_arguments=hook_args,
            is_delinquency_schedule_event=True,
        )

    @patch.object(mortgage, "_handle_delinquency")
    def test_scheduled_event_hook_notification_not_in_result_when_not_delinquent(
        self, mock_handle_delinquency: MagicMock
    ):
        # construct mocks
        mock_handle_delinquency.return_value = [], []

        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=self.event_type
        )
        result = mortgage.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)
        mock_handle_delinquency.assert_called_once_with(
            vault=sentinel.vault,
            hook_arguments=hook_args,
            is_delinquency_schedule_event=True,
        )


@patch.object(mortgage.overpayment_allowance, "handle_allowance_usage")
class CheckOverpaymentAllowanceEventTest(MortgageTestBase):
    event_type = mortgage.overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_EVENT

    def test_overpayment_allowance_feature_returns_instructions(
        self, mock_handle_allowance_usage: MagicMock
    ):
        allowance_instructions = [SentinelCustomInstruction("allowance")]
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=allowance_instructions,  # type: ignore
                    client_batch_id=f"{mortgage.ACCOUNT_TYPE}_{self.event_type}_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )

        mock_vault = self.create_mock()
        mock_handle_allowance_usage.return_value = allowance_instructions
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=self.event_type
        )
        self.assertEqual(
            mortgage.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args),
            expected_result,
        )
        mock_handle_allowance_usage.assert_called_once_with(
            vault=mock_vault, account_type=mortgage.ACCOUNT_TYPE
        )

    def test_overpayment_allowance_feature_returns_no_instructions(
        self, mock_handle_allowance_usage: MagicMock
    ):
        allowance_instructions: list[CustomInstruction] = []

        mock_vault = self.create_mock()
        mock_handle_allowance_usage.return_value = allowance_instructions
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=self.event_type
        )
        self.assertIsNone(
            mortgage.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args),
        )
        mock_handle_allowance_usage.assert_called_once_with(
            vault=mock_vault, account_type=mortgage.ACCOUNT_TYPE
        )
