# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# library
from library.loan.contracts.template import loan
from library.loan.test.unit.test_loan_common import LoanTestBase

# features
import library.features.v4.common.events as events
import library.features.v4.lending.lending_addresses as lending_addresses
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import (
    CustomInstruction as _CustomInstruction,
    Posting as _Posting,
    PostPostingHookArguments,
    ScheduledEventHookArguments,
    Tside,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DATETIME,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AccountNotificationDirective,
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    CustomInstruction,
    Phase,
    Posting,
    ScheduleSkip,
    UpdateAccountEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelEndOfMonthSchedule,
    SentinelPosting,
    SentinelScheduleExpression,
)


class StandardInterestAccrualTest(LoanTestBase):
    @patch.object(loan.repayment_holiday, "is_due_amount_calculation_blocked")
    @patch.object(loan.overpayment, "track_interest_on_expected_principal")
    @patch.object(loan, "_get_interest_rate_feature")
    @patch.object(loan.interest_accrual, "daily_accrual_logic")
    @patch.object(loan, "_get_accrual_principal_addresses")
    @patch.object(loan, "_is_no_repayment_loan_interest_to_be_capitalised")
    @patch.object(loan, "_no_repayment_to_be_capitalised")
    def test_get_standard_interest_accrual_custom_instructions(
        self,
        mock_no_repayment_capitalisation: MagicMock,
        mock_no_repayment_interest_capitalisation: MagicMock,
        mock_get_accrual_principal_addresses: MagicMock,
        mock_daily_accrual_logic: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_track_interest_on_expected_principal: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
    ):
        accrual_instructions = [SentinelCustomInstruction("accrual")]
        mock_daily_accrual_logic.return_value = accrual_instructions
        expected_accrual_instructions = [SentinelCustomInstruction("expected_accrual")]
        mock_track_interest_on_expected_principal.return_value = expected_accrual_instructions
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_get_accrual_principal_addresses.return_value = sentinel.principal_addresses
        mock_is_due_amount_calculation_blocked.return_value = False
        mock_no_repayment_interest_capitalisation.return_value = False
        mock_no_repayment_capitalisation.return_value = False
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=sentinel.event_type
        )
        result = loan._get_standard_interest_accrual_custom_instructions(
            vault=sentinel.vault,
            hook_arguments=hook_args,
            inflight_postings=[sentinel.inflight_postings],
        )
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )

        self.assertEqual(result, accrual_instructions + expected_accrual_instructions)
        mock_daily_accrual_logic.assert_called_once_with(
            vault=sentinel.vault,
            hook_arguments=hook_args,
            account_type=loan.ACCOUNT_TYPE,
            interest_rate_feature=sentinel.interest_rate_feature,
            principal_addresses=sentinel.principal_addresses,
            inflight_postings=[sentinel.inflight_postings],
            customer_accrual_address=None,
            accrual_internal_account=None,
        )
        mock_track_interest_on_expected_principal.assert_called_once_with(
            vault=sentinel.vault,
            hook_arguments=hook_args,
            interest_rate_feature=sentinel.interest_rate_feature,
        )

    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.repayment_holiday, "is_due_amount_calculation_blocked")
    @patch.object(loan, "_get_interest_rate_feature")
    @patch.object(loan.interest_accrual, "daily_accrual_logic")
    @patch.object(loan, "_get_accrual_principal_addresses")
    @patch.object(loan, "_is_no_repayment_loan_interest_to_be_capitalised")
    @patch.object(loan, "_no_repayment_to_be_capitalised")
    def test_get_interest_accrual_custom_instructions_during_repayment_holiday(
        self,
        mock_no_repayment_capitalisation: MagicMock,
        mock_no_repayment_interest_capitalisation: MagicMock,
        mock_get_accrual_principal_addresses: MagicMock,
        mock_daily_accrual_logic: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        accrual_instructions = [SentinelCustomInstruction("accrual")]
        mock_daily_accrual_logic.return_value = accrual_instructions
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_get_accrual_principal_addresses.return_value = sentinel.principal_addresses
        mock_is_due_amount_calculation_blocked.return_value = True
        mock_no_repayment_capitalisation.return_value = False
        mock_no_repayment_interest_capitalisation.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                loan.interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: (
                    sentinel.capitalised_interest_receivable_account
                )
            }
        )
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=sentinel.event_type
        )
        result = loan._get_standard_interest_accrual_custom_instructions(
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
            account_type=loan.ACCOUNT_TYPE,
            interest_rate_feature=sentinel.interest_rate_feature,
            principal_addresses=sentinel.principal_addresses,
            inflight_postings=[sentinel.inflight_postings],
            customer_accrual_address=loan.ACCRUED_INTEREST_PENDING_CAPITALISATION,
            accrual_internal_account=sentinel.capitalised_interest_receivable_account,
        )

    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.repayment_holiday, "is_due_amount_calculation_blocked")
    @patch.object(loan, "_get_interest_rate_feature")
    @patch.object(loan.interest_accrual, "daily_accrual_logic")
    @patch.object(loan, "_get_accrual_principal_addresses")
    @patch.object(loan, "_is_no_repayment_loan_interest_to_be_capitalised")
    @patch.object(loan, "_no_repayment_to_be_capitalised")
    def test_get_interest_accrual_custom_instructions_for_no_repayment_capitalisation(
        self,
        mock_no_repayment_capitalisation: MagicMock,
        mock_no_repayment_interest_capitalisation: MagicMock,
        mock_get_accrual_principal_addresses: MagicMock,
        mock_daily_accrual_logic: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        accrual_instructions = [SentinelCustomInstruction("accrual")]
        mock_daily_accrual_logic.return_value = accrual_instructions
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_get_accrual_principal_addresses.return_value = sentinel.principal_addresses
        mock_is_due_amount_calculation_blocked.return_value = False
        mock_no_repayment_capitalisation.return_value = True
        mock_no_repayment_interest_capitalisation.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                loan.interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: (
                    sentinel.capitalised_interest_receivable_account
                )
            }
        )
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=sentinel.event_type
        )
        result = loan._get_standard_interest_accrual_custom_instructions(
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
            account_type=loan.ACCOUNT_TYPE,
            interest_rate_feature=sentinel.interest_rate_feature,
            principal_addresses=sentinel.principal_addresses,
            inflight_postings=[sentinel.inflight_postings],
            customer_accrual_address=loan.ACCRUED_INTEREST_PENDING_CAPITALISATION,
            accrual_internal_account=sentinel.capitalised_interest_receivable_account,
        )

    @patch.object(loan, "FIXED_RATE_FEATURE")
    @patch.object(loan.utils, "get_parameter")
    def test_get_interest_rate_feature_fixed_rate_loan(
        self, mock_get_parameter: MagicMock, mock_fixed_rate_feature: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"fixed_interest_loan": True, "amortisation_method": "declining_principal"}
        )

        self.assertEqual(
            loan._get_interest_rate_feature(vault=sentinel.vault), mock_fixed_rate_feature
        )

    @patch.object(loan, "VARIABLE_RATE_FEATURE")
    @patch.object(loan.utils, "get_parameter")
    def test_get_interest_rate_feature_variable_rate_loan(
        self, mock_get_parameter: MagicMock, mock_variable_rate_feature: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"fixed_interest_loan": False, "amortisation_method": "declining_principal"}
        )

        self.assertEqual(
            loan._get_interest_rate_feature(vault=sentinel.vault), mock_variable_rate_feature
        )

    @patch.object(loan, "FIXED_RATE_FEATURE")
    @patch.object(loan.utils, "get_parameter")
    def test_get_interest_rate_feature_always_fixed_for_rule_of_78(
        self, mock_get_parameter: MagicMock, mock_fixed_rate_feature: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            # fixed_interest_loan should be ignored for rule_of_78
            parameters={"fixed_interest_loan": False, "amortisation_method": "rule_of_78"}
        )

        self.assertEqual(
            loan._get_interest_rate_feature(vault=sentinel.vault), mock_fixed_rate_feature
        )

    @patch.object(loan, "FIXED_RATE_FEATURE")
    @patch.object(loan.utils, "get_parameter")
    def test_get_interest_rate_feature_always_fixed_for_flat_interest(
        self, mock_get_parameter: MagicMock, mock_fixed_rate_feature: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            # fixed_interest_loan should be ignored for flat_interest
            parameters={"fixed_interest_loan": False, "amortisation_method": "flat_interest"}
        )

        self.assertEqual(
            loan._get_interest_rate_feature(vault=sentinel.vault), mock_fixed_rate_feature
        )

    @patch.object(loan, "_is_monthly_rest_loan")
    @patch.object(loan.utils, "get_parameter")
    def test_get_accrual_principal_addresses_do_not_accrue_on_due_principal_daily_rest(
        self, mock_get_parameter: MagicMock, mock_is_monthly_rest_loan: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"accrue_interest_on_due_principal": False}
        )
        mock_is_monthly_rest_loan.return_value = False

        result = loan._get_accrual_principal_addresses(vault=sentinel.vault)
        self.assertListEqual(result, [lending_addresses.PRINCIPAL])

    @patch.object(loan, "_is_monthly_rest_loan")
    @patch.object(loan.utils, "get_parameter")
    def test_get_accrual_principal_addresses_accrue_on_due_principal_accrual_daily_rest(
        self, mock_get_parameter: MagicMock, mock_is_monthly_rest_loan: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"accrue_interest_on_due_principal": True}
        )
        mock_is_monthly_rest_loan.return_value = False

        result = loan._get_accrual_principal_addresses(vault=sentinel.vault)
        self.assertListEqual(result, [lending_addresses.PRINCIPAL, lending_addresses.PRINCIPAL_DUE])

    @patch.object(loan, "_is_monthly_rest_loan")
    @patch.object(loan.utils, "get_parameter")
    def test_get_accrual_principal_addresses_no_due_principal_monthly_rest(
        self, mock_get_parameter: MagicMock, mock_is_monthly_rest_loan: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"accrue_interest_on_due_principal": False}
        )
        mock_is_monthly_rest_loan.return_value = True
        result = loan._get_accrual_principal_addresses(vault=sentinel.vault)
        self.assertListEqual(result, [loan.MONTHLY_REST_EFFECTIVE_PRINCIPAL])

    @patch.object(loan, "_is_monthly_rest_loan")
    @patch.object(loan.utils, "get_parameter")
    def test_get_accrual_principal_addresses_due_principal_monthly_rest(
        self, mock_get_parameter: MagicMock, mock_is_monthly_rest_loan: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"accrue_interest_on_due_principal": True}
        )
        mock_is_monthly_rest_loan.return_value = True

        result = loan._get_accrual_principal_addresses(vault=sentinel.vault)
        self.assertListEqual(
            result, [loan.MONTHLY_REST_EFFECTIVE_PRINCIPAL, lending_addresses.PRINCIPAL_DUE]
        )

    @patch.object(loan.utils, "get_parameter")
    def test_is_monthly_rest_loan_daily_rest(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"interest_accrual_rest_type": "daily"}
        )

        self.assertFalse(loan._is_monthly_rest_loan(vault=sentinel.vault))

    @patch.object(loan.utils, "get_parameter")
    def test_is_monthly_rest_loan_monthly_rest(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"interest_accrual_rest_type": "monthly"}
        )

        self.assertTrue(loan._is_monthly_rest_loan(vault=sentinel.vault))

    @patch.object(loan.utils, "get_parameter")
    def test_get_loan_reamortisation_conditions_rule_of_78(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": "rule_of_78"}
        )
        result = loan._get_loan_reamortisation_conditions(vault=sentinel.vault)
        self.assertListEqual([], result)

    @patch.object(loan.utils, "get_parameter")
    def test_get_loan_reamortisation_conditions_flat_interest(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": "flat_interest"}
        )
        result = loan._get_loan_reamortisation_conditions(vault=sentinel.vault)
        self.assertListEqual([], result)

    @patch.object(loan.utils, "get_parameter")
    def test_get_loan_reamortisation_conditions_fixed(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": "declining_principal", "fixed_interest_loan": True}
        )
        result = loan._get_loan_reamortisation_conditions(vault=sentinel.vault)
        self.assertListEqual(
            [
                loan.overpayment.OverpaymentReamortisationCondition,
                loan.repayment_holiday.ReamortisationConditionWithPreference,
                loan.fixed_rate.FixedReamortisationCondition,
            ],
            result,
        )

    @patch.object(loan.utils, "get_parameter")
    def test_get_loan_reamortisation_conditions_variable(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"amortisation_method": "dummy", "fixed_interest_loan": False}
        )
        result = loan._get_loan_reamortisation_conditions(vault=sentinel.vault)
        self.assertListEqual(
            [
                loan.overpayment.OverpaymentReamortisationCondition,
                loan.repayment_holiday.ReamortisationConditionWithPreference,
                loan.variable_rate.VariableReamortisationCondition,
            ],
            result,
        )


class PenaltyInterestAccrualTest(LoanTestBase):
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

    @patch.object(loan.repayment_holiday, "is_penalty_accrual_blocked")
    def test_get_penalty_interest_accrual_custom_instruction_blocking_flag(
        self, mock_is_penalty_accrual_blocked: MagicMock
    ):
        mock_is_penalty_accrual_blocked.return_value = True

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.interest_accrual.ACCRUAL_EVENT
        )

        result = loan._get_penalty_interest_accrual_custom_instruction(
            vault=sentinel.vault, hook_arguments=hook_args
        )
        self.assertListEqual(result, [])
        mock_is_penalty_accrual_blocked.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
        )

    @patch.object(loan.interest_accrual_common, "daily_accrual")
    @patch.object(loan, "_get_overdue_capital")
    @patch.object(loan, "_get_interest_rate_feature")
    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.repayment_holiday, "is_penalty_accrual_blocked")
    def test_get_penalty_interest_accrual_custom_instruction_no_postings(
        self,
        mock_is_penalty_accrual_blocked: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_overdue_capital: MagicMock,
        mock_daily_accrual: MagicMock,
    ):
        mock_is_penalty_accrual_blocked.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_params)
        eod_balance_observation = SentinelBalancesObservation("eod_balance_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.EOD_FETCHER_ID: eod_balance_observation
            }
        )
        interest_rate_feature = MagicMock()
        interest_rate_feature.get_annual_interest_rate.return_value = Decimal("0.2")
        mock_get_interest_rate_feature.return_value = interest_rate_feature
        mock_get_overdue_capital.return_value = sentinel.overdue_capital
        mock_daily_accrual.return_value = []

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.interest_accrual.ACCRUAL_EVENT
        )

        result = loan._get_penalty_interest_accrual_custom_instruction(
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
            customer_address=lending_addresses.PENALTIES,
            denomination=sentinel.denomination,
            internal_account=sentinel.penalty_interest_received_account,
            payable=False,
            effective_balance=sentinel.overdue_capital,
            effective_datetime=DEFAULT_DATETIME,
            yearly_rate=Decimal("0.3"),
            days_in_year=sentinel.days_in_year,
            precision=sentinel.application_precision,
            rounding=ROUND_HALF_UP,
            account_type="LOAN",
            event_type=loan.interest_accrual.ACCRUAL_EVENT,
        )

    @patch.object(loan.interest_accrual_common, "daily_accrual")
    @patch.object(loan, "_get_overdue_capital")
    @patch.object(loan, "_get_interest_rate_feature")
    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.repayment_holiday, "is_penalty_accrual_blocked")
    def test_get_penalty_interest_accrual_custom_instruction_with_postings(
        self,
        mock_is_penalty_accrual_blocked: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_overdue_capital: MagicMock,
        mock_daily_accrual: MagicMock,
    ):
        mock_is_penalty_accrual_blocked.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_params)
        eod_balance_observation = SentinelBalancesObservation("eod_balance_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.EOD_FETCHER_ID: eod_balance_observation
            }
        )
        interest_rate_feature = MagicMock()
        interest_rate_feature.get_annual_interest_rate.return_value = Decimal("0.2")
        mock_get_interest_rate_feature.return_value = interest_rate_feature
        mock_get_overdue_capital.return_value = sentinel.overdue_capital
        custom_instructions = [SentinelCustomInstruction("penalty_accrual")]
        mock_daily_accrual.return_value = custom_instructions

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.interest_accrual.ACCRUAL_EVENT
        )

        result = loan._get_penalty_interest_accrual_custom_instruction(
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
            customer_address=lending_addresses.PENALTIES,
            denomination=sentinel.denomination,
            internal_account=sentinel.penalty_interest_received_account,
            payable=False,
            effective_balance=sentinel.overdue_capital,
            effective_datetime=DEFAULT_DATETIME,
            yearly_rate=Decimal("0.3"),
            days_in_year=sentinel.days_in_year,
            precision=sentinel.application_precision,
            rounding=ROUND_HALF_UP,
            account_type="LOAN",
            event_type=loan.interest_accrual.ACCRUAL_EVENT,
        )

    @patch.object(loan.interest_accrual_common, "daily_accrual")
    @patch.object(loan, "_get_overdue_capital")
    @patch.object(loan, "_get_interest_rate_feature")
    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.repayment_holiday, "is_penalty_accrual_blocked")
    def test_get_penalty_interest_accrual_custom_instruction_with_capitalisation_with_postings(
        self,
        mock_is_penalty_accrual_blocked: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_overdue_capital: MagicMock,
        mock_daily_accrual: MagicMock,
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
                loan.fetchers.EOD_FETCHER_ID: eod_balance_observation
            }
        )
        interest_rate_feature = MagicMock()
        interest_rate_feature.get_annual_interest_rate.return_value = Decimal("0.2")
        mock_get_interest_rate_feature.return_value = interest_rate_feature
        mock_get_overdue_capital.return_value = sentinel.overdue_capital
        custom_instructions = [SentinelCustomInstruction("penalty_accrual")]
        mock_daily_accrual.return_value = custom_instructions

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.interest_accrual.ACCRUAL_EVENT
        )

        result = loan._get_penalty_interest_accrual_custom_instruction(
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
            customer_address=loan.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
            denomination=sentinel.denomination,
            internal_account=sentinel.capitalised_interest_receivable_account,
            payable=False,
            effective_balance=sentinel.overdue_capital,
            effective_datetime=DEFAULT_DATETIME,
            yearly_rate=Decimal("0.3"),
            days_in_year=sentinel.days_in_year,
            precision=sentinel.accrual_precision,
            rounding=ROUND_HALF_UP,
            account_type="LOAN",
            event_type=loan.interest_accrual.ACCRUAL_EVENT,
        )


class DueAmountCalculationTest(LoanTestBase):
    @patch.object(loan.utils, "sum_balances")
    @patch.object(loan.utils, "get_parameter")
    def test_get_due_amount_notification(
        self, mock_get_parameter: MagicMock, mock_sum_balances: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination, "repayment_period": 5}
        )
        mock_sum_balances.return_value = Decimal("5")
        mock_vault = self.create_mock()

        mocked_custom_instructions = [
            _CustomInstruction(
                postings=[
                    _Posting(
                        credit=True,
                        amount=Decimal("3"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="PRINCIPAL",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    _Posting(
                        credit=False,
                        amount=Decimal("3"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="PRINCIPAL_DUE",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ]
            )
        ]

        expected_overdue_datetime = (DEFAULT_DATETIME + relativedelta(days=5)).date()
        expected_result = [
            AccountNotificationDirective(
                notification_type="LOAN_REPAYMENT_DUE",
                notification_details={
                    "account_id": ACCOUNT_ID,
                    "repayment_amount": "5",
                    "overdue_date": str(expected_overdue_datetime),
                },
            )
        ]

        result = loan._get_repayment_due_notification(
            vault=mock_vault,
            due_amount_custom_instructions=mocked_custom_instructions,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertListEqual(result, expected_result)

    @patch.object(loan.utils, "standard_instruction_details")
    @patch.object(loan.due_amount_calculation, "update_due_amount_calculation_counter")
    @patch.object(loan, "_get_balloon_payment_custom_instructions")
    @patch.object(loan, "_should_execute_balloon_payment_schedule_logic")
    @patch.object(loan, "_get_amortisation_method_parameter")
    @patch.object(loan.utils, "get_parameter")
    def test_get_due_amount_custom_instructions_balloon_payment(
        self,
        mock_get_parameter: MagicMock,
        mock_get_amortisation_method_parameter: MagicMock,
        mock_should_execute_balloon_payment_schedule_logic: MagicMock,
        mock_get_balloon_payment_custom_instructions: MagicMock,
        mock_update_due_amount_calculation_counter: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                loan.PARAM_DENOMINATION: sentinel.denomination,
            }
        )
        mock_get_balloon_payment_custom_instructions.return_value = [
            sentinel.balloon_payment_postings
        ]
        counter_postings = SentinelPosting("counter")
        mock_update_due_amount_calculation_counter.return_value = [counter_postings]
        mock_instruction_details = {"key": "value"}
        mock_standard_instruction_details.return_value = mock_instruction_details
        mock_should_execute_balloon_payment_schedule_logic.return_value = True
        mock_get_amortisation_method_parameter.return_value = sentinel.amortisation_method

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=sentinel.event_type
        )
        mock_vault = self.create_mock()
        result = loan._get_due_amount_custom_instructions(
            vault=mock_vault, hook_arguments=hook_args
        )
        expected_result = [sentinel.balloon_payment_postings] + [
            CustomInstruction(
                postings=[counter_postings],
                instruction_details=mock_instruction_details,
                override_all_restrictions=True,
            )
        ]
        self.assertListEqual(result, expected_result)

        mock_should_execute_balloon_payment_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_method=sentinel.amortisation_method,
        )
        mock_get_balloon_payment_custom_instructions.assert_called_once_with(
            vault=mock_vault, hook_arguments=hook_args
        )
        mock_standard_instruction_details.assert_called_once_with(
            description="Updating due amount calculation counter balance",
            event_type=sentinel.event_type,
            gl_impacted=False,
            account_type=loan.ACCOUNT_TYPE,
        )

    @patch.object(loan, "_should_execute_balloon_payment_schedule_logic")
    @patch.object(loan.overpayment, "track_emi_principal_excess")
    @patch.object(loan.overpayment, "reset_due_amount_calc_overpayment_trackers")
    @patch.object(loan, "_is_monthly_rest_loan")
    @patch.object(loan, "_get_interest_rate_feature")
    @patch.object(loan, "_get_amortisation_feature")
    @patch.object(loan, "_get_amortisation_method_parameter")
    @patch.object(loan, "_get_loan_reamortisation_conditions")
    @patch.object(loan, "_get_interest_application_feature")
    @patch.object(loan.due_amount_calculation, "schedule_logic")
    @patch.object(loan.utils, "get_parameter")
    def test_get_due_amount_custom_instructions_not_monthly_rest(
        self,
        mock_get_parameter: MagicMock,
        mock_schedule_logic: MagicMock,
        mock_get_interest_application_feature: MagicMock,
        mock_get_loan_reamortisation_conditions: MagicMock,
        mock_get_amortisation_method_parameter: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_is_monthly_rest_loan: MagicMock,
        mock_reset_overpayment_trackers: MagicMock,
        mock_track_emi_principal_excess: MagicMock,
        mock_should_execute_balloon_payment_schedule_logic: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
            }
        )
        mock_schedule_logic.return_value = [sentinel.due_amount_posting]
        mock_reset_overpayment_trackers.return_value = [sentinel.overpayment_tracker_postings]
        mock_track_emi_principal_excess.return_value = [sentinel.emi_principal_excess_postings]
        mock_is_monthly_rest_loan.return_value = False
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_get_interest_application_feature.return_value = sentinel.interest_application_feature
        mock_get_amortisation_feature.return_value = sentinel.amortisation_feature
        mock_get_amortisation_method_parameter.return_value = sentinel.amortisation_method
        mock_get_loan_reamortisation_conditions.return_value = [sentinel.reamortisation_conditions]
        mock_should_execute_balloon_payment_schedule_logic.return_value = False

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "effective"
                )
            },
            last_execution_datetimes={
                loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: sentinel.last_execution_datetime  # noqa: E501
            },
        )
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=sentinel.event_type
        )
        result = loan._get_due_amount_custom_instructions(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertListEqual(
            result,
            [
                sentinel.due_amount_posting,
                sentinel.overpayment_tracker_postings,
                sentinel.emi_principal_excess_postings,
            ],
        )

        mock_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            account_type=loan.ACCOUNT_TYPE,
            interest_application_feature=sentinel.interest_application_feature,
            reamortisation_condition_features=[sentinel.reamortisation_conditions],
            amortisation_feature=sentinel.amortisation_feature,
            interest_rate_feature=sentinel.interest_rate_feature,
            principal_adjustment_features=[loan.overpayment.OverpaymentPrincipalAdjustment],
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
        )
        mock_track_emi_principal_excess.assert_called_once_with(
            vault=mock_vault,
            interest_application_feature=sentinel.interest_application_feature,
            effective_datetime=DEFAULT_DATETIME,
            previous_application_datetime=sentinel.last_execution_datetime,
        )

    @patch.object(loan, "_should_execute_balloon_payment_schedule_logic")
    @patch.object(loan, "_add_principal_at_cycle_start_tracker_postings")
    @patch.object(loan.overpayment, "track_emi_principal_excess")
    @patch.object(loan.overpayment, "reset_due_amount_calc_overpayment_trackers")
    @patch.object(loan, "_is_monthly_rest_loan")
    @patch.object(loan, "_get_interest_rate_feature")
    @patch.object(loan, "_get_amortisation_feature")
    @patch.object(loan, "_get_amortisation_method_parameter")
    @patch.object(loan, "_get_loan_reamortisation_conditions")
    @patch.object(loan, "_get_interest_application_feature")
    @patch.object(loan.due_amount_calculation, "schedule_logic")
    @patch.object(loan.utils, "get_parameter")
    def test_get_due_amount_custom_instructions_monthly_rest_loan(
        self,
        mock_get_parameter: MagicMock,
        mock_schedule_logic: MagicMock,
        mock_get_interest_application_feature: MagicMock,
        mock_get_loan_reamortisation_conditions: MagicMock,
        mock_get_amortisation_method_parameter: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_is_monthly_rest_loan: MagicMock,
        mock_reset_overpayment_trackers: MagicMock,
        mock_track_emi_principal_excess: MagicMock,
        mock_add_principal_at_cycle_start_tracker_postings: MagicMock,
        mock_should_execute_balloon_payment_schedule_logic: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
            }
        )
        mock_schedule_logic.return_value = [sentinel.due_amount_posting]
        mock_add_principal_at_cycle_start_tracker_postings.return_value = [
            sentinel.adjusted_postings
        ]
        mock_reset_overpayment_trackers.return_value = [sentinel.overpayment_tracker_postings]
        mock_track_emi_principal_excess.return_value = [sentinel.emi_principal_excess_postings]
        mock_is_monthly_rest_loan.return_value = True
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_get_interest_application_feature.return_value = sentinel.interest_application_feature
        mock_get_amortisation_feature.return_value = sentinel.amortisation_feature
        mock_get_amortisation_method_parameter.return_value = sentinel.amortisation_method
        mock_get_loan_reamortisation_conditions.return_value = [sentinel.reamortisation_conditions]
        mock_should_execute_balloon_payment_schedule_logic.return_value = False

        mock_vault = self.create_mock(
            creation_date=sentinel.account_creation_datetime,
            balances_observation_fetchers_mapping={
                loan.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "effective"
                )
            },
            last_execution_datetimes={
                loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: None
            },
        )
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=sentinel.event_type
        )
        result = loan._get_due_amount_custom_instructions(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertListEqual(
            result,
            [
                sentinel.adjusted_postings,
                sentinel.overpayment_tracker_postings,
                sentinel.emi_principal_excess_postings,
            ],
        )

        mock_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            account_type=loan.ACCOUNT_TYPE,
            interest_application_feature=sentinel.interest_application_feature,
            reamortisation_condition_features=[sentinel.reamortisation_conditions],
            amortisation_feature=sentinel.amortisation_feature,
            interest_rate_feature=sentinel.interest_rate_feature,
            principal_adjustment_features=[loan.overpayment.OverpaymentPrincipalAdjustment],
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
        )
        mock_add_principal_at_cycle_start_tracker_postings.assert_called_once_with(
            vault=mock_vault, due_amount_postings=[sentinel.due_amount_posting]
        )
        mock_track_emi_principal_excess.assert_called_once_with(
            vault=mock_vault,
            interest_application_feature=sentinel.interest_application_feature,
            effective_datetime=DEFAULT_DATETIME,
            previous_application_datetime=sentinel.account_creation_datetime,
        )

    @patch.object(loan, "_get_net_balance_change_for_address")
    @patch.object(loan.utils, "create_postings")
    @patch.object(loan.utils, "balance_at_coordinates")
    @patch.object(loan.utils, "get_parameter")
    def test_add_principal_at_cycle_start_tracker_postings_final_repayment_event(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_create_postings: MagicMock,
        mock_get_net_balance_change_for_address: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "effective"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )

        # The final repayment event would mean all of the remaining balance in PRINCIPAL would be
        # moved to PRINCIPAL_DUE, leaving the principal balance empty
        # (i.e. principal balance + net_balance_change = 0) therefore we expect the principal
        # tracker balance to be reduced to 0 as well.
        # existing principal tracker balance, current principal balance
        mock_balance_at_coordinates.side_effect = [Decimal("100"), Decimal("100")]
        mock_get_net_balance_change_for_address.return_value = Decimal("-100")

        tracker_posting = SentinelPosting("tracker_posting")
        mock_create_postings.return_value = [tracker_posting]

        expected_tracker_ci = CustomInstruction(
            postings=[tracker_posting],
            override_all_restrictions=True,
            instruction_details={
                "description": "Update principal at repayment cycle start balance",
                "event": loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
            },
        )

        expected_result = [sentinel.due_amount_postings, expected_tracker_ci]

        result = loan._add_principal_at_cycle_start_tracker_postings(
            vault=mock_vault, due_amount_postings=[sentinel.due_amount_postings]
        )
        self.assertListEqual(result, expected_result)

        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances_effective,
                    address="MONTHLY_REST_EFFECTIVE_PRINCIPAL",
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances_effective,
                    address="PRINCIPAL",
                    denomination=sentinel.denomination,
                ),
            ]
        )
        self.assertEqual(mock_balance_at_coordinates.call_count, 2)
        mock_get_net_balance_change_for_address.assert_called_once_with(
            custom_instructions=[sentinel.due_amount_postings],
            account_id=ACCOUNT_ID,
            address="PRINCIPAL",
            denomination=sentinel.denomination,
        )
        # we expect the amount to be equal to the balance of the tracker address
        # thus zeroing it out
        mock_create_postings.assert_called_once_with(
            amount=Decimal("100"),
            debit_account=ACCOUNT_ID,
            credit_account=ACCOUNT_ID,
            debit_address="INTERNAL_CONTRA",
            credit_address="MONTHLY_REST_EFFECTIVE_PRINCIPAL",
            denomination=sentinel.denomination,
        )

    @patch.object(loan, "_get_net_balance_change_for_address")
    @patch.object(loan.utils, "create_postings")
    @patch.object(loan.utils, "balance_at_coordinates")
    @patch.object(loan.utils, "get_parameter")
    def test_add_principal_at_cycle_start_tracker_postings_no_due_postings(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_create_postings: MagicMock,
        mock_get_net_balance_change_for_address: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "effective"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        # existing principal tracker balance, current principal balance
        mock_balance_at_coordinates.side_effect = [Decimal("200"), Decimal("100")]
        mock_get_net_balance_change_for_address.return_value = Decimal("0")

        tracker_posting = SentinelPosting("tracker_posting")
        mock_create_postings.return_value = [tracker_posting]

        expected_tracker_ci = CustomInstruction(
            postings=[tracker_posting],
            override_all_restrictions=True,
            instruction_details={
                "description": "Update principal at repayment cycle start balance",
                "event": loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
            },
        )

        expected_result = [expected_tracker_ci]

        result = loan._add_principal_at_cycle_start_tracker_postings(
            vault=mock_vault, due_amount_postings=[]
        )
        self.assertListEqual(result, expected_result)

        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances_effective,
                    address="MONTHLY_REST_EFFECTIVE_PRINCIPAL",
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances_effective,
                    address="PRINCIPAL",
                    denomination=sentinel.denomination,
                ),
            ]
        )
        self.assertEqual(mock_balance_at_coordinates.call_count, 2)
        mock_get_net_balance_change_for_address.assert_called_once_with(
            custom_instructions=[],
            account_id=ACCOUNT_ID,
            address="PRINCIPAL",
            denomination=sentinel.denomination,
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("100"),
            debit_account=ACCOUNT_ID,
            credit_account=ACCOUNT_ID,
            debit_address="INTERNAL_CONTRA",
            credit_address="MONTHLY_REST_EFFECTIVE_PRINCIPAL",
            denomination=sentinel.denomination,
        )

    @patch.object(loan, "_get_net_balance_change_for_address")
    @patch.object(loan.utils, "create_postings")
    @patch.object(loan.utils, "balance_at_coordinates")
    @patch.object(loan.utils, "get_parameter")
    def test_add_principal_at_cycle_start_tracker_postings_with_due_postings(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_create_postings: MagicMock,
        mock_get_net_balance_change_for_address: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "effective"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        # existing principal tracker balance, current principal balance
        mock_balance_at_coordinates.side_effect = [Decimal("200"), Decimal("100")]
        mock_get_net_balance_change_for_address.return_value = Decimal("-10")

        tracker_posting = SentinelPosting("tracker_posting")
        mock_create_postings.return_value = [tracker_posting]

        expected_tracker_ci = CustomInstruction(
            postings=[tracker_posting],
            override_all_restrictions=True,
            instruction_details={
                "description": "Update principal at repayment cycle start balance",
                "event": loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
            },
        )

        expected_result = [sentinel.due_amount_postings, expected_tracker_ci]

        result = loan._add_principal_at_cycle_start_tracker_postings(
            vault=mock_vault, due_amount_postings=[sentinel.due_amount_postings]
        )
        self.assertListEqual(result, expected_result)

        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances_effective,
                    address="MONTHLY_REST_EFFECTIVE_PRINCIPAL",
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances_effective,
                    address="PRINCIPAL",
                    denomination=sentinel.denomination,
                ),
            ]
        )
        self.assertEqual(mock_balance_at_coordinates.call_count, 2)
        mock_get_net_balance_change_for_address.assert_called_once_with(
            custom_instructions=[sentinel.due_amount_postings],
            account_id=ACCOUNT_ID,
            address="PRINCIPAL",
            denomination=sentinel.denomination,
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("110"),
            debit_account=ACCOUNT_ID,
            credit_account=ACCOUNT_ID,
            debit_address="INTERNAL_CONTRA",
            credit_address="MONTHLY_REST_EFFECTIVE_PRINCIPAL",
            denomination=sentinel.denomination,
        )

    @patch.object(loan, "_get_net_balance_change_for_address")
    @patch.object(loan.utils, "create_postings")
    @patch.object(loan.utils, "balance_at_coordinates")
    @patch.object(loan.utils, "get_parameter")
    def test_add_principal_at_cycle_start_tracker_postings_zero_posting_amount(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_create_postings: MagicMock,
        mock_get_net_balance_change_for_address: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "effective"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        # existing principal tracker balance, current principal balance
        mock_balance_at_coordinates.side_effect = [Decimal("100"), Decimal("100")]
        mock_get_net_balance_change_for_address.return_value = Decimal("0")

        result = loan._add_principal_at_cycle_start_tracker_postings(
            vault=mock_vault, due_amount_postings=[sentinel.due_amount_postings]
        )
        self.assertListEqual(result, [sentinel.due_amount_postings])

        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances_effective,
                    address="MONTHLY_REST_EFFECTIVE_PRINCIPAL",
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances_effective,
                    address="PRINCIPAL",
                    denomination=sentinel.denomination,
                ),
            ]
        )
        self.assertEqual(mock_balance_at_coordinates.call_count, 2)
        mock_get_net_balance_change_for_address.assert_called_once_with(
            custom_instructions=[sentinel.due_amount_postings],
            account_id=ACCOUNT_ID,
            address="PRINCIPAL",
            denomination=sentinel.denomination,
        )
        mock_create_postings.assert_not_called()

    @patch.object(loan.utils, "balance_at_coordinates")
    def test_get_net_balance_change_for_address_empty_custom_instructions(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.return_value = Decimal("0")
        result = loan._get_net_balance_change_for_address(
            custom_instructions=[],
            account_id=sentinel.account_id,
            address=sentinel.address,
            denomination=sentinel.denomination,
        )
        self.assertEqual(result, Decimal("0"))
        mock_balance_at_coordinates.assert_called_once_with(
            balances=BalanceDefaultDict(),
            address=sentinel.address,
            denomination=sentinel.denomination,
        )

    @patch.object(loan.utils, "balance_at_coordinates")
    def test_get_net_balance_change_for_address(self, mock_balance_at_coordinates: MagicMock):
        mock_balance_at_coordinates.return_value = Decimal("3")

        custom_instructions = [
            _CustomInstruction(
                postings=[
                    _Posting(
                        credit=True,
                        amount=Decimal("3"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="PRINCIPAL",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    _Posting(
                        credit=False,
                        amount=Decimal("3"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="PRINCIPAL_DUE",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    _Posting(
                        credit=True,
                        amount=Decimal("1"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="INTEREST",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    _Posting(
                        credit=False,
                        amount=Decimal("1"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="INTEREST_DUE",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ],
            ),
            _CustomInstruction(
                postings=[
                    _Posting(
                        credit=True,
                        amount=Decimal("3"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="PRINCIPAL",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    _Posting(
                        credit=False,
                        amount=Decimal("3"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="ANOTHER_ADDRESS",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    _Posting(
                        credit=True,
                        amount=Decimal("1"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="INTEREST",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    _Posting(
                        credit=False,
                        amount=Decimal("1"),
                        denomination="GBP",
                        account_id=ACCOUNT_ID,
                        account_address="ANOTHER_ADDRESS",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ],
            ),
        ]

        expected_balance_dict = BalanceDefaultDict()
        for posting_instruction in custom_instructions:
            expected_balance_dict += posting_instruction.balances(
                account_id=ACCOUNT_ID, tside=Tside.ASSET
            )

        result = loan._get_net_balance_change_for_address(
            custom_instructions=custom_instructions,
            account_id=ACCOUNT_ID,
            address="PRINCIPAL",
            denomination="GBP",
        )
        self.assertEqual(result, Decimal("3"))
        mock_balance_at_coordinates.assert_called_once_with(
            balances=expected_balance_dict,
            address="PRINCIPAL",
            denomination="GBP",
        )

    @patch.object(loan.utils, "get_schedule_expression_from_parameters")
    def test_update_check_overdue_schedule_no_skip(
        self, mock_get_schedule_expression_from_parameters: MagicMock
    ):
        overdue_expression = SentinelScheduleExpression("overdue_expression")
        mock_get_schedule_expression_from_parameters.return_value = overdue_expression
        result = loan._update_check_overdue_schedule(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME, repayment_period=1
        )

        expected = [
            UpdateAccountEventTypeDirective(
                event_type=loan.overdue.CHECK_OVERDUE_EVENT,
                expression=overdue_expression,
                skip=False,
            )
        ]
        self.assertListEqual(result, expected)

        expected_datetime = DEFAULT_DATETIME + relativedelta(days=1)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=sentinel.vault,
            parameter_prefix=loan.overdue.CHECK_OVERDUE_PREFIX,
            day=expected_datetime.day,
        )

    @patch.object(loan.utils, "get_schedule_expression_from_parameters")
    @patch.object(loan.utils, "get_parameter")
    def test_update_check_overdue_schedule_no_skip_defaulted_repayment_period(
        self, mock_get_parameter: MagicMock, mock_get_schedule_expression_from_parameters: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"repayment_period": 2}
        )
        overdue_expression = SentinelScheduleExpression("overdue_expression")
        mock_get_schedule_expression_from_parameters.return_value = overdue_expression
        result = loan._update_check_overdue_schedule(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )

        expected = [
            UpdateAccountEventTypeDirective(
                event_type=loan.overdue.CHECK_OVERDUE_EVENT,
                expression=overdue_expression,
                skip=False,
            )
        ]
        self.assertListEqual(result, expected)

        expected_datetime = DEFAULT_DATETIME + relativedelta(days=2)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=sentinel.vault,
            parameter_prefix=loan.overdue.CHECK_OVERDUE_PREFIX,
            day=expected_datetime.day,
        )

    @patch.object(loan.utils, "get_schedule_expression_from_parameters")
    def test_update_check_overdue_schedule_with_skip(
        self, mock_get_schedule_expression_from_parameters: MagicMock
    ):
        result = loan._update_check_overdue_schedule(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME, skip=True
        )

        expected = [
            UpdateAccountEventTypeDirective(
                event_type=loan.overdue.CHECK_OVERDUE_EVENT,
                skip=True,
            )
        ]
        self.assertListEqual(result, expected)
        mock_get_schedule_expression_from_parameters.assert_not_called()


class LoanHelperFunctionTest(LoanTestBase):
    def test_get_activation_fee_custom_instruction_zero_amount(self):
        result = loan._get_activation_fee_custom_instruction(
            account_id=sentinel.account_id,
            amount=Decimal("0"),
            denomination=sentinel.denomination,
            fee_income_account=sentinel.fee_income_account,
        )

        expected = []

        self.assertListEqual(result, expected)

    def test_get_activation_fee_custom_instruction_negative_amount(self):
        result = loan._get_activation_fee_custom_instruction(
            account_id=sentinel.account_id,
            amount=Decimal("0"),
            denomination=sentinel.denomination,
            fee_income_account=sentinel.fee_income_account,
        )

        expected = []

        self.assertListEqual(result, expected)

    def test_get_activation_fee_custom_instruction_positive_amount(self):
        amount = Decimal("100")
        result = loan._get_activation_fee_custom_instruction(
            account_id=sentinel.account_id,
            amount=amount,
            denomination=sentinel.denomination,
            fee_income_account=sentinel.fee_income_account,
        )

        expected = [
            CustomInstruction(
                postings=[
                    Posting(
                        credit=False,
                        amount=amount,
                        denomination=sentinel.denomination,
                        account_id=sentinel.account_id,
                        account_address=lending_addresses.PRINCIPAL,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=True,
                        amount=amount,
                        denomination=sentinel.denomination,
                        account_id=sentinel.fee_income_account,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ],
                override_all_restrictions=True,
                instruction_details={
                    "description": f"Charge activation fee of {amount}",
                    "event": events.ACCOUNT_ACTIVATION,
                },
            )
        ]

        self.assertListEqual(result, expected)

    @patch.object(loan.utils, "get_parameter")
    def test_calculate_disbursement_principal_adjustment(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"upfront_fee": Decimal("10")}
        )

        result = loan._calculate_disbursement_principal_adjustment(vault=sentinel.vault)
        expected = Decimal("10")

        self.assertEqual(result, expected)

    @patch.object(loan.utils, "get_available_balance")
    def test_get_posting_amount_custom_address(self, mock_get_posting_amount: MagicMock):
        mock_get_posting_amount.return_value = sentinel.posting_amount

        result = loan._get_posting_amount(
            posting_instruction=self.inbound_hard_settlement(amount=Decimal("1")),
            denomination=sentinel.denomination,
            address=sentinel.address,
        )

        expected_balances = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.COMMITTED): Balance(
                    debit=Decimal("1"), net=Decimal("1")
                )
            }
        )

        self.assertEqual(result, sentinel.posting_amount)

        mock_get_posting_amount.assert_called_once_with(
            balances=expected_balances,
            denomination=sentinel.denomination,
            address=sentinel.address,
        )

    @patch.object(loan.utils, "get_available_balance")
    def test_get_posting_amount_defaulted_address(self, mock_get_posting_amount: MagicMock):
        mock_get_posting_amount.return_value = sentinel.posting_amount

        result = loan._get_posting_amount(
            posting_instruction=self.inbound_hard_settlement(amount=Decimal("1")),
            denomination=sentinel.denomination,
        )

        expected_balances = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.COMMITTED): Balance(
                    debit=Decimal("1"), net=Decimal("1")
                )
            }
        )

        self.assertEqual(result, sentinel.posting_amount)

        mock_get_posting_amount.assert_called_once_with(
            balances=expected_balances,
            denomination=sentinel.denomination,
            address=DEFAULT_ADDRESS,
        )

    @patch.object(loan.utils, "get_schedule_expression_from_parameters")
    def test_update_delinquency_schedule_skip(
        self, mock_get_schedule_expression_from_parameters: MagicMock
    ):
        schedule_expression = SentinelScheduleExpression("delinquency")

        mock_get_schedule_expression_from_parameters.return_value = schedule_expression

        expected = [
            UpdateAccountEventTypeDirective(
                event_type="CHECK_DELINQUENCY", expression=schedule_expression, skip=True
            )
        ]

        result = loan._update_delinquency_schedule(
            vault=sentinel.vault, next_schedule_datetime=DEFAULT_DATETIME, skip_schedule=True
        )

        self.assertListEqual(result, expected)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=sentinel.vault,
            parameter_prefix="check_delinquency",
            day=DEFAULT_DATETIME.day,
            month=DEFAULT_DATETIME.month,
            year=DEFAULT_DATETIME.year,
        )

    @patch.object(loan.utils, "get_schedule_expression_from_parameters")
    def test_update_delinquency_schedule_skip_is_false(
        self, mock_get_schedule_expression_from_parameters: MagicMock
    ):
        schedule_expression = SentinelScheduleExpression("delinquency")

        mock_get_schedule_expression_from_parameters.return_value = schedule_expression

        expected = [
            UpdateAccountEventTypeDirective(
                event_type="CHECK_DELINQUENCY", expression=schedule_expression, skip=False
            )
        ]

        result = loan._update_delinquency_schedule(
            vault=sentinel.vault, next_schedule_datetime=DEFAULT_DATETIME, skip_schedule=False
        )

        self.assertListEqual(result, expected)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=sentinel.vault,
            parameter_prefix="check_delinquency",
            day=DEFAULT_DATETIME.day,
            month=DEFAULT_DATETIME.month,
            year=DEFAULT_DATETIME.year,
        )

    @patch.object(loan.utils, "sum_balances")
    def test_get_late_payment_balance(self, mock_sum_balances: MagicMock):
        mock_sum_balances.return_value = sentinel.balance_sum

        result = loan._get_late_payment_balance(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        self.assertEqual(result, sentinel.balance_sum)
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=lending_addresses.LATE_REPAYMENT_ADDRESSES,
            denomination=sentinel.denomination,
            decimal_places=2,
        )

    @patch.object(loan.utils, "sum_balances")
    def test_get_overdue_capital_include_overdue_interest(self, mock_sum_balances: MagicMock):
        mock_sum_balances.return_value = sentinel.balance_sum

        result = loan._get_overdue_capital(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            include_overdue_interest=True,
        )

        self.assertEqual(result, sentinel.balance_sum)
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=lending_addresses.OVERDUE_ADDRESSES,
            denomination=sentinel.denomination,
            decimal_places=2,
        )

    @patch.object(loan, "_mark_account_delinquent")
    @patch.object(loan, "_update_delinquency_schedule")
    @patch.object(loan.utils, "get_parameter")
    def test_handle_delinquency_with_zero_grace_period_overdue_event(
        self,
        mock_get_parameter: MagicMock,
        mock_update_delinquency_schedule: MagicMock,
        mock_mark_account_delinquent: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "effective_balances"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"grace_period": 0, "denomination": sentinel.denomination}
        )
        mock_update_delinquency_schedule.return_value = [sentinel.update_delinquency_schedule]
        mock_mark_account_delinquent.return_value = [sentinel.delinquent_notification_directive]

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.overdue.CHECK_OVERDUE_EVENT
        )

        result = loan._handle_delinquency(
            vault=mock_vault, hook_arguments=hook_args, is_delinquency_schedule_event=False
        )

        expected = (
            [sentinel.delinquent_notification_directive],
            [sentinel.update_delinquency_schedule],
        )
        self.assertEqual(result, expected)

        mock_update_delinquency_schedule.assert_called_once_with(
            vault=mock_vault,
            next_schedule_datetime=DEFAULT_DATETIME + relativedelta(months=1),
            skip_schedule=True,
        )
        mock_mark_account_delinquent.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME, balances=None
        )

    @patch.object(loan, "_mark_account_delinquent")
    @patch.object(loan, "_update_delinquency_schedule")
    @patch.object(loan.utils, "get_parameter")
    def test_handle_delinquency_with_non_zero_grace_period_overdue_event(
        self,
        mock_get_parameter: MagicMock,
        mock_update_delinquency_schedule: MagicMock,
        mock_mark_account_delinquent: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "effective_balances"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"grace_period": 5, "denomination": sentinel.denomination}
        )
        mock_update_delinquency_schedule.return_value = [sentinel.update_event_directive]

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.overdue.CHECK_OVERDUE_EVENT
        )

        result = loan._handle_delinquency(
            vault=mock_vault, hook_arguments=hook_args, is_delinquency_schedule_event=False
        )

        expected = [], [sentinel.update_event_directive]  # type: ignore
        self.assertEqual(result, expected)

        mock_update_delinquency_schedule.assert_called_once_with(
            vault=mock_vault,
            next_schedule_datetime=DEFAULT_DATETIME + relativedelta(days=5),
            skip_schedule=False,
        )
        mock_mark_account_delinquent.assert_not_called()

    @patch.object(loan, "_mark_account_delinquent")
    @patch.object(loan, "_update_delinquency_schedule")
    @patch.object(loan.utils, "get_parameter")
    def test_handle_delinquency_on_delinquency_event(
        self,
        mock_get_parameter: MagicMock,
        mock_update_delinquency_schedule: MagicMock,
        mock_mark_account_delinquent: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "effective_balances"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"grace_period": 5, "denomination": sentinel.denomination}
        )
        mock_update_delinquency_schedule.return_value = [sentinel.update_event_directive]
        mock_mark_account_delinquent.return_value = [sentinel.delinquent_notification_directive]

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=loan.CHECK_DELINQUENCY
        )

        result = loan._handle_delinquency(
            vault=mock_vault, hook_arguments=hook_args, is_delinquency_schedule_event=True
        )

        expected = (
            [sentinel.delinquent_notification_directive],
            [sentinel.update_event_directive],
        )
        self.assertEqual(result, expected)

        mock_update_delinquency_schedule.assert_called_once_with(
            vault=mock_vault,
            next_schedule_datetime=DEFAULT_DATETIME + relativedelta(months=1),
            skip_schedule=True,
        )
        mock_mark_account_delinquent.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME, balances=None
        )

    @patch.object(loan.utils, "is_flag_in_list_applied")
    @patch.object(loan.repayment_holiday, "is_delinquency_blocked")
    def test_mark_account_delinquent_blocking_flag_applied(
        self,
        mock_is_delinquency_blocked: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
    ):
        mock_is_delinquency_blocked.return_value = True
        result = loan._mark_account_delinquent(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        self.assertListEqual(result, [])
        mock_is_delinquency_blocked.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )

    @patch.object(loan.utils, "is_flag_in_list_applied")
    @patch.object(loan.repayment_holiday, "is_delinquency_blocked")
    def test_mark_account_delinquent_already_delinquent(
        self,
        mock_is_delinquency_blocked: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
    ):
        mock_is_delinquency_blocked.return_value = False
        mock_is_flag_in_list_applied.return_value = True
        result = loan._mark_account_delinquent(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        self.assertListEqual(result, [])
        mock_is_delinquency_blocked.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )

    @patch.object(loan.utils, "is_flag_in_list_applied")
    @patch.object(loan, "_get_late_payment_balance")
    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.repayment_holiday, "is_delinquency_blocked")
    def test_mark_account_delinquent_with_positive_late_balance_returns_notification_directive(
        self,
        mock_is_delinquency_blocked: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_late_payment_balance: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_is_delinquency_blocked.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_get_late_payment_balance.return_value = Decimal("10")

        expected = [
            AccountNotificationDirective(
                notification_type="LOAN_MARK_DELINQUENT",
                notification_details={"account_id": ACCOUNT_ID},
            )
        ]
        result = loan._mark_account_delinquent(
            vault=mock_vault, effective_datetime=sentinel.datetime, balances=sentinel.balances
        )
        self.assertListEqual(result, expected)
        mock_is_delinquency_blocked.assert_called_once_with(
            vault=mock_vault, effective_datetime=sentinel.datetime
        )

    @patch.object(loan.utils, "is_flag_in_list_applied")
    @patch.object(loan, "_get_late_payment_balance")
    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.repayment_holiday, "is_delinquency_blocked")
    def test_mark_account_delinquent_with_zero_late_balance_returns_empty_list(
        self,
        mock_is_delinquency_blocked: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_late_payment_balance: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_is_delinquency_blocked.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_get_late_payment_balance.return_value = Decimal("0")

        result = loan._mark_account_delinquent(
            vault=sentinel.vault, effective_datetime=sentinel.datetime, balances=sentinel.balances
        )
        self.assertListEqual(result, [])
        mock_is_delinquency_blocked.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )

    @patch.object(loan.utils, "is_flag_in_list_applied")
    @patch.object(loan, "_get_late_payment_balance")
    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.repayment_holiday, "is_delinquency_blocked")
    def test_mark_account_delinquent_without_balances_gets_observation(
        self,
        mock_is_delinquency_blocked: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_late_payment_balance: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
    ):
        effective_balances_observation = SentinelBalancesObservation("effective")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: effective_balances_observation
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_is_delinquency_blocked.return_value = False
        mock_is_flag_in_list_applied.return_value = False
        mock_get_late_payment_balance.return_value = Decimal("0")

        result = loan._mark_account_delinquent(
            vault=mock_vault, effective_datetime=sentinel.datetime, balances=None
        )
        self.assertListEqual(result, [])
        mock_is_delinquency_blocked.assert_called_once_with(
            vault=mock_vault, effective_datetime=sentinel.datetime
        )
        mock_get_late_payment_balance.assert_called_once_with(
            balances=sentinel.balances_effective, denomination=sentinel.denomination
        )

    @patch.object(loan.utils, "sum_balances")
    def test_get_overdue_capital_include_overdue_interest_false(self, mock_sum_balances: MagicMock):
        mock_sum_balances.return_value = sentinel.balance_sum

        result = loan._get_overdue_capital(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            include_overdue_interest=False,
        )

        self.assertEqual(result, sentinel.balance_sum)
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=[lending_addresses.PRINCIPAL_OVERDUE],
            denomination=sentinel.denomination,
            decimal_places=2,
        )

    @patch.object(loan, "_get_late_payment_balance")
    def test_get_overdue_repayment_notification(self, mock_get_late_payment_balance: MagicMock):
        mock_get_late_payment_balance.return_value = sentinel.late_payment_balance

        result = loan._get_overdue_repayment_notification(
            account_id=sentinel.account_id,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            late_repayment_fee=sentinel.late_repayment_fee,
            effective_datetime=DEFAULT_DATETIME,
        )

        expected = [
            AccountNotificationDirective(
                notification_type="LOAN_REPAYMENT_OVERDUE",
                notification_details={
                    "account_id": sentinel.account_id,
                    "repayment_amount": str(sentinel.late_payment_balance),
                    "late_repayment_fee": str(sentinel.late_repayment_fee),
                    "overdue_date": str(DEFAULT_DATETIME.date()),
                },
            )
        ]

        self.assertListEqual(expected, result)
        mock_get_late_payment_balance.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )

    @patch.object(loan.utils, "balance_at_coordinates")
    def test_get_residual_cleanup_postings_no_postings(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [Decimal("0"), Decimal("0"), Decimal("0")]

        result = loan._get_residual_cleanup_postings(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            denomination=sentinel.denomination,
        )
        self.assertListEqual(result, [])

        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances,
                    address=loan.CAPITALISED_INTEREST_TRACKER,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances,
                    address=loan.CAPITALISED_PENALTIES_TRACKER,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances,
                    address=loan.MONTHLY_REST_EFFECTIVE_PRINCIPAL,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        self.assertEqual(mock_balance_at_coordinates.call_count, 3)

    @patch.object(loan.utils, "create_postings")
    @patch.object(loan.utils, "balance_at_coordinates")
    def test_get_residual_cleanup_postings_with_postings(
        self, mock_balance_at_coordinates: MagicMock, mock_create_postings: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [Decimal("1"), Decimal("2"), Decimal("3")]
        mock_create_postings.side_effect = [
            [sentinel.postings_1],
            [sentinel.postings_2],
            [sentinel.postings_3],
        ]
        result = loan._get_residual_cleanup_postings(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            denomination=sentinel.denomination,
        )
        self.assertListEqual(
            result, [sentinel.postings_1, sentinel.postings_2, sentinel.postings_3]
        )

        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances,
                    address=loan.CAPITALISED_INTEREST_TRACKER,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances,
                    address=loan.CAPITALISED_PENALTIES_TRACKER,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances,
                    address=loan.MONTHLY_REST_EFFECTIVE_PRINCIPAL,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        self.assertEqual(mock_balance_at_coordinates.call_count, 3)

        mock_create_postings.assert_has_calls(
            calls=[
                call(
                    amount=Decimal("1"),
                    debit_account=sentinel.account_id,
                    credit_account=sentinel.account_id,
                    debit_address=lending_addresses.INTERNAL_CONTRA,
                    credit_address=loan.CAPITALISED_INTEREST_TRACKER,
                    denomination=sentinel.denomination,
                ),
                call(
                    amount=Decimal("2"),
                    debit_account=sentinel.account_id,
                    credit_account=sentinel.account_id,
                    debit_address=lending_addresses.INTERNAL_CONTRA,
                    credit_address=loan.CAPITALISED_PENALTIES_TRACKER,
                    denomination=sentinel.denomination,
                ),
                call(
                    amount=Decimal("3"),
                    debit_account=sentinel.account_id,
                    credit_account=sentinel.account_id,
                    debit_address=lending_addresses.INTERNAL_CONTRA,
                    credit_address=loan.MONTHLY_REST_EFFECTIVE_PRINCIPAL,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        self.assertEqual(mock_create_postings.call_count, 3)

    @patch.object(loan.utils, "balance_at_coordinates")
    def test_get_interest_to_revert(self, mock_balance_at_coordinates: MagicMock):
        mock_balance_at_coordinates.return_value = sentinel.balance_net

        self.assertEqual(
            loan._get_interest_to_revert(
                balances=sentinel.balances, denomination=sentinel.denomination
            ),
            sentinel.balance_net,
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=lending_addresses.INTEREST_DUE,
            denomination=sentinel.denomination,
        )

    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan, "_get_repayment_schedule_declining_principal")
    def test_get_repayment_schedule_with_declining_principal(
        self,
        mock_get_repayment_schedule_declining_principal: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_repayment_schedule_declining_principal.return_value = sentinel.repayment_schedule
        mock_get_parameter.return_value = "DECLINING_PRINCIPAL"

        self.assertEquals(
            sentinel.repayment_schedule, loan._get_repayment_schedule(vault=sentinel.vault)
        )

    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan, "_get_repayment_schedule_declining_principal")
    def test_get_repayment_schedule_with_an_unsupported_amortisation_type(
        self,
        mock_get_repayment_schedule_declining_principal: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_repayment_schedule_declining_principal.return_value = sentinel.repayment_schedule
        mock_get_parameter.return_value = "FLAT_INTEREST"

        self.assertEquals({}, loan._get_repayment_schedule(vault=sentinel.vault))

    @patch.object(loan, "_get_repayment_schedule")
    def test_get_repayment_schedule_notification(
        self,
        mock_get_repayment_schedule: MagicMock,
    ):
        mock_get_repayment_schedule.return_value = {}
        mock_vault = self.create_mock()

        expected_notification = AccountNotificationDirective(
            notification_type=loan.REPAYMENT_SCHEDULE_NOTIFICATION,
            notification_details={"account_id": ACCOUNT_ID, "repayment_schedule": str({})},
        )
        self.assertEquals(
            expected_notification, loan._get_repayment_schedule_notification(vault=mock_vault)
        )

    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.minimum_repayment, "is_minimum_repayment_loan")
    @patch.object(loan.interest_only, "is_interest_only_loan")
    @patch.object(loan.no_repayment, "is_no_repayment_loan")
    def test_get_amortisation_feature_declining_principal(
        self,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_interest_only_loan: MagicMock,
        mock_is_minimum_repayment_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        mock_is_minimum_repayment_loan.return_value = False
        mock_is_interest_only_loan.return_value = False
        mock_is_no_repayment_loan.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {loan.PARAM_AMORTISATION_METHOD: sentinel.amortisation}
        )
        result = loan._get_amortisation_feature(vault=sentinel.vault)
        self.assertEqual(result, loan.declining_principal.AmortisationFeature)

    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.minimum_repayment, "is_minimum_repayment_loan")
    @patch.object(loan.interest_only, "is_interest_only_loan")
    @patch.object(loan.no_repayment, "is_no_repayment_loan")
    def test_get_amortisation_feature_no_repayment(
        self,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_interest_only_loan: MagicMock,
        mock_is_minimum_repayment_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        mock_is_minimum_repayment_loan.return_value = False
        mock_is_interest_only_loan.return_value = False
        mock_is_no_repayment_loan.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {loan.PARAM_AMORTISATION_METHOD: sentinel.amortisation}
        )
        result = loan._get_amortisation_feature(vault=sentinel.vault)
        self.assertEqual(result, loan.no_repayment.AmortisationFeature)

    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.minimum_repayment, "is_minimum_repayment_loan")
    @patch.object(loan.interest_only, "is_interest_only_loan")
    def test_get_amortisation_feature_interest_only(
        self,
        mock_is_interest_only_loan: MagicMock,
        mock_is_minimum_repayment_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        mock_is_minimum_repayment_loan.return_value = False
        mock_is_interest_only_loan.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {loan.PARAM_AMORTISATION_METHOD: sentinel.amortisation}
        )
        result = loan._get_amortisation_feature(vault=sentinel.vault)
        self.assertEqual(result, loan.interest_only.AmortisationFeature)

    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.minimum_repayment, "is_minimum_repayment_loan")
    def test_get_amortisation_feature_minimum_repayment(
        self,
        mock_is_minimum_repayment_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        mock_is_minimum_repayment_loan.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {loan.PARAM_AMORTISATION_METHOD: sentinel.amortisation}
        )
        result = loan._get_amortisation_feature(vault=sentinel.vault)
        self.assertEqual(result, loan.minimum_repayment.AmortisationFeature)

    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    def test_get_amortisation_feature_flat_interest(
        self,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_flat_interest_loan.return_value = True
        mock_is_rule_of_78_loan.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {loan.PARAM_AMORTISATION_METHOD: sentinel.amortisation}
        )

        result = loan._get_amortisation_feature(vault=sentinel.vault)
        self.assertEqual(result, loan.flat_interest.AmortisationFeature)
        mock_is_flat_interest_loan.assert_called_once_with(
            amortisation_method=sentinel.amortisation
        )
        mock_is_rule_of_78_loan.assert_called_once_with(amortisation_method=sentinel.amortisation)

    @patch.object(loan.utils, "get_parameter")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    def test_get_amortisation_feature_rule_of_78(
        self,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {loan.PARAM_AMORTISATION_METHOD: sentinel.amortisation}
        )

        result = loan._get_amortisation_feature(vault=sentinel.vault)
        self.assertEqual(result, loan.rule_of_78.AmortisationFeature)
        mock_is_rule_of_78_loan.assert_called_once_with(amortisation_method=sentinel.amortisation)
        mock_is_flat_interest_loan.assert_not_called()

    @patch.object(loan.utils, "get_parameter")
    def test_get_interest_rate_application_feature_rule_of_78(self, mock_get_parameter: MagicMock):
        mock_get_parameter.return_value = "rule_of_78"

        self.assertEqual(
            loan._get_interest_application_feature(vault=sentinel.vault),
            loan.rule_of_78.InterestApplication,
        )

    @patch.object(loan.utils, "get_parameter")
    def test_get_interest_rate_application_feature_flat_interest(
        self, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.return_value = "flat_interest"

        self.assertEqual(
            loan._get_interest_application_feature(vault=sentinel.vault),
            loan.flat_interest.InterestApplication,
        )

    @patch.object(loan.utils, "get_parameter")
    def test_get_interest_rate_application_feature_non_flat_interest(
        self, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.return_value = "other"

        self.assertEqual(
            loan._get_interest_application_feature(vault=sentinel.vault),
            loan.interest_application.InterestApplication,
        )

    @patch.object(loan.repayment_holiday, "is_repayment_holiday_impact_increase_emi")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    def test_should_repayment_holiday_increase_tracker_balance_increase_emi(
        self,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_repayment_holiday_impact_increase_emi: MagicMock,
    ):
        mock_is_repayment_holiday_impact_increase_emi.return_value = True
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False

        result = loan._should_repayment_holiday_increase_tracker_balance(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            amortisation_method=sentinel.amortisation,
        )

        self.assertTrue(result)
        mock_is_repayment_holiday_impact_increase_emi.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        mock_is_flat_interest_loan.assert_called_once_with(
            amortisation_method=sentinel.amortisation
        )
        mock_is_rule_of_78_loan.assert_called_once_with(amortisation_method=sentinel.amortisation)

    @patch.object(loan.repayment_holiday, "is_repayment_holiday_impact_increase_emi")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    def test_should_repayment_holiday_increase_tracker_balance_increase_term(
        self,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_repayment_holiday_impact_increase_emi: MagicMock,
    ):
        mock_is_repayment_holiday_impact_increase_emi.return_value = False
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False

        result = loan._should_repayment_holiday_increase_tracker_balance(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            amortisation_method=sentinel.amortisation,
        )

        self.assertFalse(result)
        mock_is_repayment_holiday_impact_increase_emi.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        mock_is_flat_interest_loan.assert_not_called()
        mock_is_rule_of_78_loan.assert_not_called()

    @patch.object(loan.repayment_holiday, "is_repayment_holiday_impact_increase_emi")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    def test_should_repayment_holiday_increase_tracker_balance_flat_interest(
        self,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_repayment_holiday_impact_increase_emi: MagicMock,
    ):
        mock_is_repayment_holiday_impact_increase_emi.return_value = True
        mock_is_flat_interest_loan.return_value = True
        mock_is_rule_of_78_loan.return_value = False

        result = loan._should_repayment_holiday_increase_tracker_balance(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            amortisation_method=sentinel.amortisation,
        )

        self.assertFalse(result)
        mock_is_repayment_holiday_impact_increase_emi.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        mock_is_flat_interest_loan.assert_called_once_with(
            amortisation_method=sentinel.amortisation
        )
        mock_is_rule_of_78_loan.assert_called_once_with(amortisation_method=sentinel.amortisation)

    @patch.object(loan.repayment_holiday, "is_repayment_holiday_impact_increase_emi")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    def test_should_repayment_holiday_increase_tracker_balance_rule_of_78(
        self,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_repayment_holiday_impact_increase_emi: MagicMock,
    ):
        mock_is_repayment_holiday_impact_increase_emi.return_value = True
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = True

        result = loan._should_repayment_holiday_increase_tracker_balance(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            amortisation_method=sentinel.amortisation,
        )

        self.assertFalse(result)
        mock_is_repayment_holiday_impact_increase_emi.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        mock_is_flat_interest_loan.assert_not_called()
        mock_is_rule_of_78_loan.assert_called_once_with(amortisation_method=sentinel.amortisation)


class LateRepaymentFeeTest(LoanTestBase):
    common_params = {
        loan.PARAM_DENOMINATION: sentinel.denomination,
        loan.PARAM_LATE_REPAYMENT_FEE: Decimal("25"),
        loan.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: sentinel.fee_income_account,
    }

    @patch.object(loan.fees, "fee_postings")
    @patch.object(loan.utils, "standard_instruction_details")
    @patch.object(loan.utils, "get_parameter")
    def test_late_repayment_fee_applied_to_penalties_address_when_not_capitalised(
        self,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_fee_postings: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_params
            | {
                loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: False,
            }
        )
        mock_standard_instruction_details.return_value = {"sentinel": "dict"}
        fee_postings = [SentinelPosting("FeePosting")]
        mock_fee_postings.return_value = fee_postings
        mock_vault = self.create_mock()

        result = loan._charge_late_repayment_fee(
            vault=mock_vault,
            event_type=sentinel.event_type,
        )

        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=fee_postings, instruction_details={"sentinel": "dict"}  # type: ignore
                )
            ],
        )

        mock_fee_postings.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            customer_account_address=lending_addresses.PENALTIES,
            denomination=f"{sentinel.denomination}",
            amount=Decimal("25"),
            internal_account=sentinel.fee_income_account,
        )

    @patch.object(loan.fees, "fee_postings")
    @patch.object(loan.utils, "standard_instruction_details")
    @patch.object(loan.utils, "get_parameter")
    def test_late_repayment_fee_not_applied_if_not_required(
        self,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_fee_postings: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_params
            | {
                loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: False,
            }
        )
        mock_standard_instruction_details.return_value = {"sentinel": "dict"}
        mock_fee_postings.return_value = []
        mock_vault = self.create_mock()

        result = loan._charge_late_repayment_fee(
            vault=mock_vault,
            event_type=sentinel.event_type,
        )

        self.assertListEqual(result, [])

    @patch.object(loan.fees, "fee_postings")
    @patch.object(loan.utils, "create_postings")
    @patch.object(loan.utils, "standard_instruction_details")
    @patch.object(loan.utils, "get_parameter")
    def test_late_repayment_fee_applied_to_principal_with_tracker_when_capitalised(
        self,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_create_postings: MagicMock,
        mock_fee_postings: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.common_params,
                loan.interest_capitalisation.PARAM_CAPITALISED_PENALTIES_RECEIVED_ACCOUNT: sentinel.capitalised_penalties_account,  # noqa: E501
            }
            | {
                loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: True,
            }
        )
        mock_standard_instruction_details.return_value = {"sentinel": "dict"}
        fee_postings = [SentinelPosting("FeePosting")]
        mock_fee_postings.return_value = fee_postings
        tracker_postings = [SentinelPosting("TrackerPosting")]
        mock_create_postings.return_value = tracker_postings
        mock_vault = self.create_mock()

        result = loan._charge_late_repayment_fee(
            vault=mock_vault,
            event_type=sentinel.event_type,
        )

        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=tracker_postings + fee_postings,  # type: ignore
                    instruction_details={"sentinel": "dict"},
                )
            ],
        )

        mock_create_postings.assert_called_once_with(
            amount=Decimal("25"),
            debit_account=mock_vault.account_id,
            credit_account=mock_vault.account_id,
            debit_address=loan.CAPITALISED_PENALTIES_TRACKER,
            credit_address=lending_addresses.INTERNAL_CONTRA,
        )

        mock_fee_postings.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            customer_account_address=lending_addresses.PRINCIPAL,
            denomination=f"{sentinel.denomination}",
            amount=Decimal("25"),
            internal_account=sentinel.capitalised_penalties_account,
        )

    @patch.object(loan.fees, "fee_postings")
    @patch.object(loan.utils, "standard_instruction_details")
    @patch.object(loan.utils, "get_parameter")
    def test_late_repayment_fee_args_override_defaults(
        self,
        mock_get_parameter: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_fee_postings: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: False,
                loan.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: sentinel.fee_income_account,
            }
        )
        mock_standard_instruction_details.return_value = {"sentinel": "dict"}
        fee_postings = [SentinelPosting("FeePosting")]
        mock_fee_postings.return_value = fee_postings
        mock_vault = self.create_mock()

        result = loan._charge_late_repayment_fee(
            vault=mock_vault,
            event_type=sentinel.event_type,
            amount=sentinel.arg_amount,
            denomination=sentinel.arg_denomination,
        )

        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=fee_postings, instruction_details={"sentinel": "dict"}  # type: ignore
                )
            ],
        )

        mock_fee_postings.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            customer_account_address=lending_addresses.PENALTIES,
            denomination=sentinel.arg_denomination,
            amount=sentinel.arg_amount,
            internal_account=sentinel.fee_income_account,
        )


@patch.object(loan, "_get_denomination_parameter")
@patch.object(loan, "_should_handle_interest_capitalisation")
@patch.object(loan.utils, "create_postings")
@patch.object(loan, "_is_monthly_rest_loan")
@patch.object(loan.interest_capitalisation, "handle_interest_capitalisation")
class HandleInterestCapitalisationTest(LoanTestBase):
    def test_capitalise_interest_applies_pending_capitalisation_accrued_interest_monthly_rest(
        self,
        mock_handle_interest_capitalisation: MagicMock,
        mock_is_monthly_rest_loan: MagicMock,
        mock_create_postings: MagicMock,
        mock_should_handle_interest_capitalisation: MagicMock,
        mock_get_denomination_parameter: MagicMock,
    ):
        mock_get_denomination_parameter.return_value = "GBP"
        mock_should_handle_interest_capitalisation.return_value = True
        mock_is_monthly_rest_loan.return_value = True
        mock_capitalisation_postings = [
            _Posting(
                credit=True,
                amount=Decimal("3"),
                denomination="GBP",
                account_id=ACCOUNT_ID,
                account_address="PRINCIPAL",
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
            _Posting(
                credit=False,
                amount=Decimal("3"),
                denomination="GBP",
                account_id=ACCOUNT_ID,
                account_address="DEFAULT",
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        mock_monthly_rest_postings = [
            _Posting(
                credit=True,
                amount=Decimal("3"),
                denomination="GBP",
                account_id=ACCOUNT_ID,
                account_address="INTERNAL_CONTRA",
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
            _Posting(
                credit=False,
                amount=Decimal("3"),
                denomination="GBP",
                account_id=ACCOUNT_ID,
                account_address="MONTHLY_REST_EFFECTIVE_PRINCIPAL",
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        mock_capitalisation_instructions = [
            _CustomInstruction(postings=mock_capitalisation_postings)
        ]
        mock_handle_interest_capitalisation.return_value = mock_capitalisation_instructions
        mock_create_postings.return_value = mock_monthly_rest_postings
        mock_vault = self.create_mock(account_id=ACCOUNT_ID)
        expected_instructions = [
            _CustomInstruction(postings=mock_capitalisation_postings + mock_monthly_rest_postings)
        ]

        result = loan._handle_interest_capitalisation(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            account_type=sentinel.account_type,
            balances=sentinel.balances,
            interest_to_capitalise_address=sentinel.interest_to_capitalise_address,
        )
        self.assertListEqual(expected_instructions, result)

        mock_create_postings.assert_called_once_with(
            amount=Decimal("3"),
            debit_account="default_account",
            credit_account="default_account",
            debit_address="MONTHLY_REST_EFFECTIVE_PRINCIPAL",
            credit_address="INTERNAL_CONTRA",
        )
        mock_should_handle_interest_capitalisation.assert_called_once_with(
            vault=mock_vault, effective_datetime=sentinel.effective_datetime
        )
        mock_handle_interest_capitalisation.assert_called_once_with(
            vault=mock_vault,
            account_type=sentinel.account_type,
            balances=sentinel.balances,
            interest_to_capitalise_address=sentinel.interest_to_capitalise_address,
        )
        mock_is_monthly_rest_loan.assert_called_once_with(vault=mock_vault)

    def test_capitalise_interest_do_not_handle_interest_capitalisation(
        self,
        mock_handle_interest_capitalisation: MagicMock,
        mock_is_monthly_rest_loan: MagicMock,
        mock_create_postings: MagicMock,
        mock_should_handle_interest_capitalisation: MagicMock,
        mock_get_denomination_parameter: MagicMock,
    ):
        mock_should_handle_interest_capitalisation.return_value = False
        result = loan._handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            account_type=sentinel.account_type,
            balances=sentinel.balances,
            interest_to_capitalise_address=sentinel.interest_to_capitalise_address,
        )
        self.assertListEqual([], result)
        mock_should_handle_interest_capitalisation.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
        )


class PostingHelpersTest(LoanTestBase):
    @patch.object(loan.utils, "str_to_bool")
    def test_is_interest_adjustment_true(self, mock_str_to_bool: MagicMock):
        mock_str_to_bool.return_value = True
        posting = CustomInstruction(
            postings=[SentinelPosting("dummy")],
            instruction_details={loan.INSTRUCTION_DETAILS_KEY_INTEREST_ADJUSTMENT: "true"},
        )
        self.assertTrue(loan._is_interest_adjustment(posting=posting))
        mock_str_to_bool.assert_called_once_with("true")

    @patch.object(loan.utils, "str_to_bool")
    def test_is_interest_adjustment_false(self, mock_str_to_bool: MagicMock):
        mock_str_to_bool.return_value = False
        posting = CustomInstruction(
            postings=[SentinelPosting("dummy")],
            instruction_details={loan.INSTRUCTION_DETAILS_KEY_FEE: "true"},
        )
        self.assertFalse(loan._is_interest_adjustment(posting=posting))
        mock_str_to_bool.assert_called_once_with("false")


class PostPostingHelpersTest(LoanTestBase):
    @patch.object(loan, "_handle_overpayment")
    @patch.object(loan.payments, "generate_repayment_postings")
    @patch.object(loan.close_loan, "does_repayment_fully_repay_loan")
    def test_process_payment_custom_instructions_loan_not_repaid(
        self,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_generate_repayment_postings: MagicMock,
        mock_handle_overpayment: MagicMock,
    ):
        mock_generate_repayment_postings.return_value = [sentinel.custom_instructions]
        mock_does_repayment_fully_repay_loan.return_value = False
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
            }
        )

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[sentinel.posting_instructions],
            client_transactions={"some_id": sentinel.client_transaction},
        )

        result = loan._process_payment(
            vault=mock_vault, hook_arguments=hook_args, denomination=sentinel.denomination
        )

        self.assertEqual(result, ([sentinel.custom_instructions], []))
        mock_generate_repayment_postings.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            overpayment_features=[
                loan.lending_interfaces.Overpayment(handle_overpayment=mock_handle_overpayment)
            ],
            early_repayment_fees=loan.EARLY_REPAYMENT_FEES,
        )
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=[sentinel.custom_instructions],
            balances=sentinel.balances_live,
            denomination=sentinel.denomination,
            account_id=ACCOUNT_ID,
            payment_addresses=loan.lending_addresses.ALL_OUTSTANDING,
        )

    @patch.object(loan, "_handle_overpayment")
    @patch.object(loan.payments, "generate_repayment_postings")
    @patch.object(loan.close_loan, "does_repayment_fully_repay_loan")
    def test_process_payment_custom_instructions_loan_fully_repaid(
        self,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_generate_repayment_postings: MagicMock,
        mock_handle_overpayment: MagicMock,
    ):
        mock_generate_repayment_postings.return_value = [sentinel.custom_instructions]
        mock_does_repayment_fully_repay_loan.return_value = True
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
            }
        )

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[sentinel.posting_instructions],
            client_transactions={"some_id": sentinel.client_transaction},
        )

        expected = (
            [sentinel.custom_instructions],
            [
                AccountNotificationDirective(
                    notification_type=loan.CLOSURE_NOTIFICATION,
                    notification_details={"account_id": ACCOUNT_ID},
                )
            ],
        )

        result = loan._process_payment(
            vault=mock_vault, hook_arguments=hook_args, denomination=sentinel.denomination
        )

        self.assertEqual(result, expected)
        mock_generate_repayment_postings.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            overpayment_features=[
                loan.lending_interfaces.Overpayment(handle_overpayment=mock_handle_overpayment)
            ],
            early_repayment_fees=loan.EARLY_REPAYMENT_FEES,
        )
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=[sentinel.custom_instructions],
            balances=sentinel.balances_live,
            denomination=sentinel.denomination,
            account_id=ACCOUNT_ID,
            payment_addresses=loan.lending_addresses.ALL_OUTSTANDING,
        )

    @patch.object(loan, "_handle_overpayment")
    @patch.object(loan.payments, "generate_repayment_postings")
    @patch.object(loan.close_loan, "does_repayment_fully_repay_loan")
    def test_process_payment_no_custom_instructions(
        self,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_generate_repayment_postings: MagicMock,
        mock_handle_overpayment: MagicMock,
    ):
        mock_generate_repayment_postings.return_value = []
        mock_does_repayment_fully_repay_loan.return_value = False
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
            }
        )

        hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[sentinel.posting_instructions],
            client_transactions={"some_id": sentinel.client_transaction},
        )

        result = loan._process_payment(
            vault=mock_vault, hook_arguments=hook_args, denomination=sentinel.denomination
        )

        self.assertEqual(result, ([], []))
        mock_generate_repayment_postings.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            overpayment_features=[
                loan.lending_interfaces.Overpayment(handle_overpayment=mock_handle_overpayment)
            ],
            early_repayment_fees=loan.EARLY_REPAYMENT_FEES,
        )
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=[],
            balances=sentinel.balances_live,
            denomination=sentinel.denomination,
            account_id=ACCOUNT_ID,
            payment_addresses=loan.lending_addresses.ALL_OUTSTANDING,
        )

    @patch.object(loan.overpayment, "handle_overpayment")
    @patch.object(loan.overpayment, "get_overpayment_fee_postings")
    @patch.object(loan.overpayment, "get_overpayment_fee")
    @patch.object(loan.overpayment, "get_max_overpayment_fee")
    @patch.object(loan.utils, "get_parameter")
    def test_handle_overpayment_no_postings(
        self,
        mock_get_parameter: MagicMock,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_overpayment_fee: MagicMock,
        mock_get_overpayment_fee_postings: MagicMock,
        mock_handle_overpayment: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "overpayment_fee_rate": sentinel.overpayment_fee_rate,
                "overpayment_fee_income_account": sentinel.overpayment_fee_income_account,
            }
        )
        mock_get_overpayment_fee.return_value = Decimal("0")
        mock_get_max_overpayment_fee.return_value = Decimal("0")
        mock_get_overpayment_fee_postings.return_value = []
        mock_handle_overpayment.return_value = []
        mock_vault = self.create_mock()

        result = loan._handle_overpayment(
            vault=mock_vault,
            overpayment_amount=Decimal("10"),
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )
        self.assertListEqual(result, [])

        mock_get_overpayment_fee.assert_called_once_with(
            principal_repaid=Decimal("10"),
            overpayment_fee_rate=sentinel.overpayment_fee_rate,
            precision=2,
        )
        mock_get_overpayment_fee_postings.assert_called_once_with(
            overpayment_fee=Decimal("0"),
            denomination=sentinel.denomination,
            customer_account_id=ACCOUNT_ID,
            customer_account_address=DEFAULT_ADDRESS,
            internal_account=sentinel.overpayment_fee_income_account,
        )
        mock_handle_overpayment.assert_called_once_with(
            vault=mock_vault,
            overpayment_amount=Decimal("10"),
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

    @patch.object(loan.overpayment, "handle_overpayment")
    @patch.object(loan.overpayment, "get_overpayment_fee_postings")
    @patch.object(loan.overpayment, "get_overpayment_fee")
    @patch.object(loan.overpayment, "get_max_overpayment_fee")
    @patch.object(loan.utils, "get_parameter")
    def test_handle_overpayment_with_postings_max_overpayment_fee_charged(
        self,
        mock_get_parameter: MagicMock,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_overpayment_fee: MagicMock,
        mock_get_overpayment_fee_postings: MagicMock,
        mock_handle_overpayment: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "overpayment_fee_rate": sentinel.overpayment_fee_rate,
                "overpayment_fee_income_account": sentinel.overpayment_fee_income_account,
            }
        )
        mock_get_overpayment_fee.return_value = Decimal("2")
        mock_get_max_overpayment_fee.return_value = Decimal("1")
        mock_get_overpayment_fee_postings.return_value = [sentinel.fee_postings]
        mock_handle_overpayment.return_value = [sentinel.overpayment_postings]
        mock_vault = self.create_mock()

        result = loan._handle_overpayment(
            vault=mock_vault,
            overpayment_amount=Decimal("10"),
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )
        self.assertListEqual(result, [sentinel.fee_postings, sentinel.overpayment_postings])

        mock_get_overpayment_fee.assert_called_once_with(
            principal_repaid=Decimal("10"),
            overpayment_fee_rate=sentinel.overpayment_fee_rate,
            precision=2,
        )
        mock_get_overpayment_fee_postings.assert_called_once_with(
            overpayment_fee=Decimal("1"),
            denomination=sentinel.denomination,
            customer_account_id=ACCOUNT_ID,
            customer_account_address=DEFAULT_ADDRESS,
            internal_account=sentinel.overpayment_fee_income_account,
        )
        mock_handle_overpayment.assert_called_once_with(
            vault=mock_vault,
            overpayment_amount=Decimal("9"),
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

    @patch.object(loan.overpayment, "handle_overpayment")
    @patch.object(loan.overpayment, "get_overpayment_fee_postings")
    @patch.object(loan.overpayment, "get_overpayment_fee")
    @patch.object(loan.overpayment, "get_max_overpayment_fee")
    @patch.object(loan.utils, "get_parameter")
    def test_handle_overpayment_with_postings_max_overpayment_fee_greater_than_overpayment_fee(
        self,
        mock_get_parameter: MagicMock,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_overpayment_fee: MagicMock,
        mock_get_overpayment_fee_postings: MagicMock,
        mock_handle_overpayment: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "overpayment_fee_rate": sentinel.overpayment_fee_rate,
                "overpayment_fee_income_account": sentinel.overpayment_fee_income_account,
            }
        )
        mock_get_overpayment_fee.return_value = Decimal("2")
        mock_get_max_overpayment_fee.return_value = Decimal("3")
        mock_get_overpayment_fee_postings.return_value = [sentinel.fee_postings]
        mock_handle_overpayment.return_value = [sentinel.overpayment_postings]
        mock_vault = self.create_mock()

        result = loan._handle_overpayment(
            vault=mock_vault,
            overpayment_amount=Decimal("10"),
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )
        self.assertListEqual(result, [sentinel.fee_postings, sentinel.overpayment_postings])

        mock_get_overpayment_fee.assert_called_once_with(
            principal_repaid=Decimal("10"),
            overpayment_fee_rate=sentinel.overpayment_fee_rate,
            precision=2,
        )
        mock_get_overpayment_fee_postings.assert_called_once_with(
            overpayment_fee=Decimal("2"),
            denomination=sentinel.denomination,
            customer_account_id=ACCOUNT_ID,
            customer_account_address=DEFAULT_ADDRESS,
            internal_account=sentinel.overpayment_fee_income_account,
        )
        mock_handle_overpayment.assert_called_once_with(
            vault=mock_vault,
            overpayment_amount=Decimal("8"),
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )


@patch.object(loan, "_get_interest_rate_feature")
@patch.object(loan.utils, "get_parameter")
class GetRepaymentScheduleTest(LoanTestBase):
    def test_get_repayment_schedule_declining_principal(
        self, mock_get_parameter: MagicMock, mock_get_interest_rate_feature: MagicMock
    ):
        start_dt = datetime(2020, 1, 10, tzinfo=ZoneInfo("UTC"))

        mock_vault = self.create_mock(creation_date=start_dt)

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                loan.disbursement.PARAM_PRINCIPAL: Decimal("100000"),
                loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
                loan.PARAM_UPFRONT_FEE: Decimal("0"),
                loan.PARAM_AMORTISE_UPFRONT_FEE: "False",
                loan.interest_accrual.PARAM_ACCRUAL_PRECISION: "5",
                loan.interest_application.PARAM_APPLICATION_PRECISION: "2",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "28",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_HOUR: "0",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_MINUTE: "0",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_SECOND: "1",
            }
        )

        annual_interest_rate = Decimal("0.129971")
        interest_rate_feature = MagicMock()
        interest_rate_feature.get_annual_interest_rate.return_value = annual_interest_rate
        interest_rate_feature.get_monthly_interest_rate.return_value = annual_interest_rate / 12
        # TODO INC-8480: Handle interest rate rounding
        # Currently this is manually quantized to assure sameness with existing v3 loan coverage
        interest_rate_feature.get_daily_interest_rate.return_value = (
            annual_interest_rate / 365
        ).quantize(Decimal(".0000000001"), rounding=ROUND_HALF_UP)

        mock_get_interest_rate_feature.return_value = interest_rate_feature

        expected_schedule = {
            "2020-02-28 00:00:01+00:00": ["1", "92172.28", "9572.54", "7827.72", "1744.82"],
            "2020-03-28 00:00:01+00:00": ["2", "84192.50", "8931.59", "7979.78", "951.81"],
            "2020-04-28 00:00:01+00:00": ["3", "76190.28", "8931.59", "8002.22", "929.37"],
            "2020-05-28 00:00:01+00:00": ["4", "68072.60", "8931.59", "8117.68", "813.91"],
            "2020-06-28 00:00:01+00:00": ["5", "59892.44", "8931.59", "8180.16", "751.43"],
            "2020-07-28 00:00:01+00:00": ["6", "51600.65", "8931.59", "8291.79", "639.80"],
            "2020-08-28 00:00:01+00:00": ["7", "43238.66", "8931.59", "8361.99", "569.60"],
            "2020-09-28 00:00:01+00:00": ["8", "34784.37", "8931.59", "8454.29", "477.30"],
            "2020-10-28 00:00:01+00:00": ["9", "26224.37", "8931.59", "8560.00", "371.59"],
            "2020-11-28 00:00:01+00:00": ["10", "17582.26", "8931.59", "8642.11", "289.48"],
            "2020-12-28 00:00:01+00:00": ["11", "8838.49", "8931.59", "8743.77", "187.82"],
            "2021-01-28 00:00:01+00:00": ["12", "0", "8936.05", "8838.49", "97.56"],
        }
        actual_schedule = loan._get_repayment_schedule_declining_principal(vault=mock_vault)
        self.assertDictEqual(expected_schedule, actual_schedule)

    def test_get_repayment_schedule_declining_principal_with_zero_interest_rate(
        self, mock_get_parameter: MagicMock, mock_get_interest_rate_feature: MagicMock
    ):
        start_dt = datetime(2020, 1, 10, tzinfo=ZoneInfo("UTC"))

        mock_vault = self.create_mock(creation_date=start_dt)

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                loan.disbursement.PARAM_PRINCIPAL: Decimal("120000"),
                loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
                loan.PARAM_UPFRONT_FEE: Decimal("0"),
                loan.PARAM_AMORTISE_UPFRONT_FEE: "True",
                loan.interest_accrual.PARAM_ACCRUAL_PRECISION: "5",
                loan.interest_application.PARAM_APPLICATION_PRECISION: "2",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "28",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_HOUR: "0",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_MINUTE: "0",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_SECOND: "1",
            }
        )

        interest_rate_feature = MagicMock()
        interest_rate_feature.get_annual_interest_rate.return_value = Decimal("0")
        interest_rate_feature.get_monthly_interest_rate.return_value = Decimal("0")
        interest_rate_feature.get_daily_interest_rate.return_value = Decimal("0")

        mock_get_interest_rate_feature.return_value = interest_rate_feature

        expected_schedule = {
            "2020-02-28 00:00:01+00:00": ["1", "110000.00", "10000.00", "10000.00", "0.00"],
            "2020-03-28 00:00:01+00:00": ["2", "100000.00", "10000.00", "10000.00", "0.00"],
            "2020-04-28 00:00:01+00:00": ["3", "90000.00", "10000.00", "10000.00", "0.00"],
            "2020-05-28 00:00:01+00:00": ["4", "80000.00", "10000.00", "10000.00", "0.00"],
            "2020-06-28 00:00:01+00:00": ["5", "70000.00", "10000.00", "10000.00", "0.00"],
            "2020-07-28 00:00:01+00:00": ["6", "60000.00", "10000.00", "10000.00", "0.00"],
            "2020-08-28 00:00:01+00:00": ["7", "50000.00", "10000.00", "10000.00", "0.00"],
            "2020-09-28 00:00:01+00:00": ["8", "40000.00", "10000.00", "10000.00", "0.00"],
            "2020-10-28 00:00:01+00:00": ["9", "30000.00", "10000.00", "10000.00", "0.00"],
            "2020-11-28 00:00:01+00:00": ["10", "20000.00", "10000.00", "10000.00", "0.00"],
            "2020-12-28 00:00:01+00:00": ["11", "10000.00", "10000.00", "10000.00", "0.00"],
            "2021-01-28 00:00:01+00:00": ["12", "0", "10000.00", "10000.00", "0.00"],
        }
        actual_schedule = loan._get_repayment_schedule_declining_principal(vault=mock_vault)
        self.assertDictEqual(expected_schedule, actual_schedule)

    def test_get_repayment_schedule_declining_principal_with_upfront_fee(
        self, mock_get_parameter: MagicMock, mock_get_interest_rate_feature: MagicMock
    ):
        start_dt = datetime(2020, 1, 10, tzinfo=ZoneInfo("UTC"))

        mock_vault = self.create_mock(creation_date=start_dt)

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                loan.disbursement.PARAM_PRINCIPAL: Decimal("120000"),
                loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
                loan.PARAM_UPFRONT_FEE: Decimal("120000"),
                loan.PARAM_AMORTISE_UPFRONT_FEE: "True",
                loan.interest_accrual.PARAM_ACCRUAL_PRECISION: "5",
                loan.interest_application.PARAM_APPLICATION_PRECISION: "2",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "28",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_HOUR: "0",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_MINUTE: "0",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_SECOND: "1",
            }
        )

        interest_rate_feature = MagicMock()
        interest_rate_feature.get_annual_interest_rate.return_value = Decimal("0")
        interest_rate_feature.get_monthly_interest_rate.return_value = Decimal("0")
        interest_rate_feature.get_daily_interest_rate.return_value = Decimal("0")

        mock_get_interest_rate_feature.return_value = interest_rate_feature

        expected_schedule = {
            "2020-02-28 00:00:01+00:00": ["1", "220000.00", "20000.00", "20000.00", "0.00"],
            "2020-03-28 00:00:01+00:00": ["2", "200000.00", "20000.00", "20000.00", "0.00"],
            "2020-04-28 00:00:01+00:00": ["3", "180000.00", "20000.00", "20000.00", "0.00"],
            "2020-05-28 00:00:01+00:00": ["4", "160000.00", "20000.00", "20000.00", "0.00"],
            "2020-06-28 00:00:01+00:00": ["5", "140000.00", "20000.00", "20000.00", "0.00"],
            "2020-07-28 00:00:01+00:00": ["6", "120000.00", "20000.00", "20000.00", "0.00"],
            "2020-08-28 00:00:01+00:00": ["7", "100000.00", "20000.00", "20000.00", "0.00"],
            "2020-09-28 00:00:01+00:00": ["8", "80000.00", "20000.00", "20000.00", "0.00"],
            "2020-10-28 00:00:01+00:00": ["9", "60000.00", "20000.00", "20000.00", "0.00"],
            "2020-11-28 00:00:01+00:00": ["10", "40000.00", "20000.00", "20000.00", "0.00"],
            "2020-12-28 00:00:01+00:00": ["11", "20000.00", "20000.00", "20000.00", "0.00"],
            "2021-01-28 00:00:01+00:00": ["12", "0", "20000.00", "20000.00", "0.00"],
        }
        actual_schedule = loan._get_repayment_schedule_declining_principal(vault=mock_vault)
        self.assertDictEqual(expected_schedule, actual_schedule)


@patch.object(loan.utils, "get_end_of_month_schedule_from_parameters")
class UpdateDueAmountCalculationDayScheduleTest(LoanTestBase):
    def test_directive_is_returned(self, mock_get_end_of_month_schedule: MagicMock):
        # construct mocks
        mock_get_end_of_month_schedule.return_value = SentinelEndOfMonthSchedule("due_amount_calc")

        # construct expected result
        expected_result = [
            UpdateAccountEventTypeDirective(
                event_type=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                schedule_method=SentinelEndOfMonthSchedule("due_amount_calc"),
                skip=ScheduleSkip(end=DEFAULT_DATETIME - relativedelta(seconds=1)),
            )
        ]

        # run function
        result = loan._update_due_amount_calculation_day_schedule(
            sentinel.vault, schedule_start_datetime=DEFAULT_DATETIME, due_amount_calculation_day=5
        )
        self.assertEqual(result, expected_result)
        mock_get_end_of_month_schedule.assert_called_once_with(
            vault=sentinel.vault,
            parameter_prefix=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX,
            day=5,
        )


@patch.object(loan.utils, "get_parameter")
class NoRepaymentInterestCapitalisationTest(LoanTestBase):
    def test_capitalise_monthly_capitalisation_eom_moved_forward(
        self, mock_get_parameter: MagicMock
    ):
        # Test Parameters
        creation_date = DEFAULT_DATETIME + relativedelta(month=1, day=31)
        test_date = DEFAULT_DATETIME + relativedelta(month=2, day=28)

        # Setup Mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": "no_repayment",
                loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "MONTHLY",
            }
        )
        mock_vault = self.create_mock(creation_date=creation_date)

        result = loan._is_no_repayment_loan_interest_to_be_capitalised(
            vault=mock_vault, effective_datetime=test_date
        )

        self.assertTrue(result)

    def test_capitalise_monthly_capitalisation_same_day(self, mock_get_parameter: MagicMock):
        # Test Parameters
        creation_date = DEFAULT_DATETIME + relativedelta(month=1, day=15)
        test_date = DEFAULT_DATETIME + relativedelta(month=2, day=15)

        # Setup Mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": "no_repayment",
                loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "MONTHLY",
            }
        )
        mock_vault = self.create_mock(creation_date=creation_date)

        result = loan._is_no_repayment_loan_interest_to_be_capitalised(
            vault=mock_vault, effective_datetime=test_date
        )

        self.assertTrue(result)

    def test_capitalise_monthly_capitalisation_different_day(self, mock_get_parameter: MagicMock):
        # Test Parameters
        creation_date = DEFAULT_DATETIME + relativedelta(month=1, day=15)
        test_date = DEFAULT_DATETIME + relativedelta(month=2, day=16)

        # Setup Mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": "no_repayment",
                loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "MONTHLY",
            }
        )
        mock_vault = self.create_mock(creation_date=creation_date)

        result = loan._is_no_repayment_loan_interest_to_be_capitalised(
            vault=mock_vault, effective_datetime=test_date
        )

        self.assertFalse(result)

    def test_capitalise_daily_capitalisation_different_day(self, mock_get_parameter: MagicMock):
        # Test Parameters
        creation_date = DEFAULT_DATETIME
        test_date = DEFAULT_DATETIME + relativedelta(month=2, day=16)

        # Setup Mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": "no_repayment",
                loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "DAILY",
            }
        )
        mock_vault = self.create_mock(creation_date=creation_date)

        result = loan._is_no_repayment_loan_interest_to_be_capitalised(
            vault=mock_vault, effective_datetime=test_date
        )

        self.assertTrue(result)

    def test_capitalise_no_capitalisation(self, mock_get_parameter: MagicMock):
        # Test Parameters
        creation_date = DEFAULT_DATETIME
        test_date = DEFAULT_DATETIME + relativedelta(months=1)

        # Setup Mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": "no_repayment",
                loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "NO_CAPITALISATION",
            }
        )
        mock_vault = self.create_mock(creation_date=creation_date)

        result = loan._is_no_repayment_loan_interest_to_be_capitalised(
            vault=mock_vault, effective_datetime=test_date
        )

        self.assertFalse(result)

    def test_capitalise_monthly(self, mock_get_parameter: MagicMock):
        # Test Parameters
        creation_date = DEFAULT_DATETIME
        test_date = DEFAULT_DATETIME + relativedelta(months=1)

        # Setup Mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": "no_repayment",
                loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "MONTHLY",
            }
        )
        mock_vault = self.create_mock(creation_date=creation_date)

        result = loan._is_no_repayment_loan_interest_to_be_capitalised(
            vault=mock_vault, effective_datetime=test_date
        )

        self.assertTrue(result)


@patch.object(loan.repayment_holiday, "is_penalty_accrual_blocked")
@patch.object(loan, "_is_no_repayment_loan_interest_to_be_capitalised")
@patch.object(loan.no_repayment, "is_no_repayment_loan")
class DoHandleInterestCapitalisationTest(LoanTestBase):
    @patch.object(loan, "_get_amortisation_method_parameter")
    def test_should_handle_interest_capitalisation_boolean_permutation_1(
        self,
        mock_get_amortisation: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_no_repayment_loan_interest_to_be_capitalised: MagicMock,
        mock_is_penalty_accrual_blocked: MagicMock,
    ):
        mock_get_amortisation.return_value = sentinel.amortisation
        mock_is_no_repayment_loan.return_value = True
        mock_is_no_repayment_loan_interest_to_be_capitalised.return_value = True
        mock_is_penalty_accrual_blocked.return_value = True
        result = loan._should_handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            is_penalty_interest_capitalisation=True,
        )
        description = (
            "is_no_repayment_loan_interest_to_be_capitalised: True, "
            "is_penalty_accrual_blocked: True, "
            "is_penalty_interest_capitalisation: True"
        )
        self.assertEqual(True, result, description)

    @patch.object(loan, "_get_amortisation_method_parameter")
    def test_should_handle_interest_capitalisation_boolean_permutation_2(
        self,
        mock_get_amortisation: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_no_repayment_loan_interest_to_be_capitalised: MagicMock,
        mock_is_penalty_accrual_blocked: MagicMock,
    ):
        mock_get_amortisation.return_value = sentinel.amortisation
        mock_is_no_repayment_loan.return_value = True
        mock_is_no_repayment_loan_interest_to_be_capitalised.return_value = True
        mock_is_penalty_accrual_blocked.return_value = False
        result = loan._should_handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            is_penalty_interest_capitalisation=True,
        )
        description = (
            "is_no_repayment_loan_interest_to_be_capitalised: True, "
            "is_penalty_accrual_blocked: False, "
            "is_penalty_interest_capitalisation: True"
        )
        self.assertEqual(True, result, description)

    @patch.object(loan, "_get_amortisation_method_parameter")
    def test_should_handle_interest_capitalisation_boolean_permutation_3(
        self,
        mock_get_amortisation: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_no_repayment_loan_interest_to_be_capitalised: MagicMock,
        mock_is_penalty_accrual_blocked: MagicMock,
    ):
        mock_get_amortisation.return_value = sentinel.amortisation
        mock_is_no_repayment_loan.return_value = True
        mock_is_no_repayment_loan_interest_to_be_capitalised.return_value = True
        mock_is_penalty_accrual_blocked.return_value = True
        result = loan._should_handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            is_penalty_interest_capitalisation=False,
        )
        description = (
            "is_no_repayment_loan_interest_to_be_capitalised: True, "
            "is_penalty_accrual_blocked: True, "
            "is_penalty_interest_capitalisation: False"
        )
        self.assertEqual(True, result, description)

    @patch.object(loan, "_get_amortisation_method_parameter")
    def test_should_handle_interest_capitalisation_boolean_permutation_4(
        self,
        mock_get_amortisation: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_no_repayment_loan_interest_to_be_capitalised: MagicMock,
        mock_is_penalty_accrual_blocked: MagicMock,
    ):
        mock_get_amortisation.return_value = sentinel.amortisation
        mock_is_no_repayment_loan.return_value = True
        mock_is_no_repayment_loan_interest_to_be_capitalised.return_value = True
        mock_is_penalty_accrual_blocked.return_value = False
        result = loan._should_handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            is_penalty_interest_capitalisation=False,
        )
        description = (
            "is_no_repayment_loan_interest_to_be_capitalised: True, "
            "is_penalty_accrual_blocked: False, "
            "is_penalty_interest_capitalisation: False"
        )
        self.assertEqual(True, result, description)

    @patch.object(loan, "_get_amortisation_method_parameter")
    def test_should_handle_interest_capitalisation_boolean_permutation_5(
        self,
        mock_get_amortisation: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_no_repayment_loan_interest_to_be_capitalised: MagicMock,
        mock_is_penalty_accrual_blocked: MagicMock,
    ):
        mock_get_amortisation.return_value = sentinel.amortisation
        mock_is_no_repayment_loan.return_value = False
        mock_is_no_repayment_loan_interest_to_be_capitalised.return_value = False
        mock_is_penalty_accrual_blocked.return_value = True
        result = loan._should_handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            is_penalty_interest_capitalisation=True,
        )
        description = (
            "is_no_repayment_loan_interest_to_be_capitalised: False, "
            "is_penalty_accrual_blocked: True, "
            "is_penalty_interest_capitalisation: True"
        )
        self.assertEqual(True, result, description)

    @patch.object(loan, "_get_amortisation_method_parameter")
    def test_should_handle_interest_capitalisation_boolean_permutation_6(
        self,
        mock_get_amortisation: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_no_repayment_loan_interest_to_be_capitalised: MagicMock,
        mock_is_penalty_accrual_blocked: MagicMock,
    ):
        mock_get_amortisation.return_value = sentinel.amortisation
        mock_is_no_repayment_loan.return_value = False
        mock_is_no_repayment_loan_interest_to_be_capitalised.return_value = False
        mock_is_penalty_accrual_blocked.return_value = False
        result = loan._should_handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            is_penalty_interest_capitalisation=True,
        )
        description = (
            "is_no_repayment_loan_interest_to_be_capitalised: False, "
            "is_penalty_accrual_blocked: False, "
            "is_penalty_interest_capitalisation: True"
        )
        self.assertEqual(True, result, description)

    @patch.object(loan, "_get_amortisation_method_parameter")
    def test_should_handle_interest_capitalisation_boolean_permutation_7(
        self,
        mock_get_amortisation: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_no_repayment_loan_interest_to_be_capitalised: MagicMock,
        mock_is_penalty_accrual_blocked: MagicMock,
    ):
        mock_get_amortisation.return_value = sentinel.amortisation
        mock_is_no_repayment_loan.return_value = False
        mock_is_no_repayment_loan_interest_to_be_capitalised.return_value = False
        mock_is_penalty_accrual_blocked.return_value = True
        result = loan._should_handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            is_penalty_interest_capitalisation=False,
        )
        description = (
            "is_no_repayment_loan_interest_to_be_capitalised: False, "
            "is_penalty_accrual_blocked: True, "
            "is_penalty_interest_capitalisation: False"
        )
        self.assertEqual(False, result, description)

    @patch.object(loan, "_get_amortisation_method_parameter")
    def test_should_handle_interest_capitalisation_boolean_permutation_8(
        self,
        mock_get_amortisation: MagicMock,
        mock_is_no_repayment_loan: MagicMock,
        mock_is_no_repayment_loan_interest_to_be_capitalised: MagicMock,
        mock_is_penalty_accrual_blocked: MagicMock,
    ):
        mock_get_amortisation.return_value = sentinel.amortisation
        mock_is_no_repayment_loan.return_value = False
        mock_is_no_repayment_loan_interest_to_be_capitalised.return_value = False
        mock_is_penalty_accrual_blocked.return_value = False
        result = loan._should_handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            is_penalty_interest_capitalisation=False,
        )
        description = (
            "is_no_repayment_loan_interest_to_be_capitalised: False, "
            "is_penalty_accrual_blocked: False, "
            "is_penalty_interest_capitalisation: False"
        )
        self.assertEqual(True, result, description)


@patch.object(loan.balloon_payments, "is_balloon_loan")
class ShouldExecuteBalloonPaymentScheduleLogicTest(LoanTestBase):
    def test_should_execute_balloon_payment_schedule_logic_non_balloon_loan(
        self, mock_is_balloon_loan: MagicMock
    ):
        mock_is_balloon_loan.return_value = False

        self.assertFalse(
            loan._should_execute_balloon_payment_schedule_logic(
                vault=sentinel.vault,
                effective_datetime=sentinel.datetime,
                amortisation_method=sentinel.amortisation_method,
            )
        )

    @patch.object(loan, "_get_amortisation_feature")
    @patch.object(loan.balloon_payments, "_get_balloon_payment_delta_days")
    def test_should_execute_balloon_payment_schedule_logic_with_delta_days(
        self,
        mock_get_balloon_payment_delta_days: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_is_balloon_loan: MagicMock,
    ):
        mock_get_amortisation_feature.return_value = MagicMock(
            term_details=MagicMock(return_value=(sentinel.elapsed, 1))
        )
        mock_get_balloon_payment_delta_days.return_value = 10
        mock_is_balloon_loan.return_value = True

        self.assertFalse(
            loan._should_execute_balloon_payment_schedule_logic(
                vault=sentinel.vault,
                effective_datetime=sentinel.datetime,
                amortisation_method=sentinel.amortisation_method,
            )
        )

    @patch.object(loan, "_get_amortisation_feature")
    @patch.object(loan.balloon_payments, "_get_balloon_payment_delta_days")
    def test_should_execute_balloon_payment_schedule_logic_zero_delta_days_final_term(
        self,
        mock_get_balloon_payment_delta_days: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_is_balloon_loan: MagicMock,
    ):
        mock_get_amortisation_feature.return_value = MagicMock(
            term_details=MagicMock(return_value=(sentinel.elapsed, 1))
        )
        mock_get_balloon_payment_delta_days.return_value = 0
        mock_is_balloon_loan.return_value = True

        self.assertTrue(
            loan._should_execute_balloon_payment_schedule_logic(
                vault=sentinel.vault,
                effective_datetime=sentinel.datetime,
                amortisation_method=sentinel.amortisation_method,
            )
        )

    @patch.object(loan, "_get_amortisation_feature")
    @patch.object(loan.balloon_payments, "_get_balloon_payment_delta_days")
    def test_should_execute_balloon_payment_schedule_logic_zero_delta_days_not_final_term(
        self,
        mock_get_balloon_payment_delta_days: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_is_balloon_loan: MagicMock,
    ):
        mock_get_amortisation_feature.return_value = MagicMock(
            term_details=MagicMock(return_value=(sentinel.elapsed, 2))
        )
        mock_get_balloon_payment_delta_days.return_value = 0
        mock_is_balloon_loan.return_value = True

        self.assertFalse(
            loan._should_execute_balloon_payment_schedule_logic(
                vault=sentinel.vault,
                effective_datetime=sentinel.datetime,
                amortisation_method=sentinel.amortisation_method,
            )
        )


@patch.object(loan.balloon_payments, "is_balloon_loan")
class ShouldEnableBalloonPaymentSchedule(LoanTestBase):
    def test_should_enable_balloon_payment_schedule_non_balloon_loan(
        self, mock_is_balloon_loan: MagicMock
    ):
        mock_is_balloon_loan.return_value = False
        self.assertFalse(
            loan._should_enable_balloon_payment_schedule(
                vault=sentinel.vault,
                effective_datetime=sentinel.datetime,
                amortisation_method=sentinel.amortisation_method,
            )
        )

    @patch.object(loan, "_get_amortisation_feature")
    def test_should_enable_balloon_payment_schedule_not_final_term(
        self, mock_get_amortisation_feature: MagicMock, mock_is_balloon_loan: MagicMock
    ):
        mock_is_balloon_loan.return_value = True
        mock_get_amortisation_feature.return_value = MagicMock(
            term_details=MagicMock(return_value=(sentinel.elapsed, 2))
        )

        self.assertFalse(
            loan._should_enable_balloon_payment_schedule(
                vault=sentinel.vault,
                effective_datetime=sentinel.datetime,
                amortisation_method=sentinel.amortisation_method,
            )
        )

    @patch.object(loan, "_get_amortisation_feature")
    @patch.object(loan.balloon_payments, "_get_balloon_payment_delta_days")
    def test_should_enable_balloon_payment_schedule_final_term_zero_delta_days(
        self,
        mock_get_balloon_payment_delta_days: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_is_balloon_loan: MagicMock,
    ):
        mock_is_balloon_loan.return_value = True
        mock_get_amortisation_feature.return_value = MagicMock(
            term_details=MagicMock(return_value=(sentinel.elapsed, 1))
        )
        mock_get_balloon_payment_delta_days.return_value = 0

        self.assertFalse(
            loan._should_enable_balloon_payment_schedule(
                vault=sentinel.vault,
                effective_datetime=sentinel.datetime,
                amortisation_method=sentinel.amortisation_method,
            )
        )

    @patch.object(loan, "_get_amortisation_feature")
    @patch.object(loan.balloon_payments, "_get_balloon_payment_delta_days")
    def test_should_enable_balloon_payment_schedule_final_term_delta_days(
        self,
        mock_get_balloon_payment_delta_days: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_is_balloon_loan: MagicMock,
    ):
        mock_is_balloon_loan.return_value = True
        mock_get_amortisation_feature.return_value = MagicMock(
            term_details=MagicMock(return_value=(sentinel.elapsed, 1))
        )
        mock_get_balloon_payment_delta_days.return_value = 10

        self.assertTrue(
            loan._should_enable_balloon_payment_schedule(
                vault=sentinel.vault,
                effective_datetime=sentinel.datetime,
                amortisation_method=sentinel.amortisation_method,
            )
        )


@patch.object(loan.utils, "get_parameter")
class ShouldCapitaliseNoRepayment(LoanTestBase):
    def test_should_capitalise_for_daily_no_repayment_cap(
        self,
        mock_get_parameter: MagicMock,
    ):
        bp = loan.balloon_payments
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "amortisation_method": bp.no_repayment.AMORTISATION_METHOD,
                loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "DAILY",
            }
        )
        self.assertTrue(
            loan._no_repayment_to_be_capitalised(
                vault=sentinel.vault,
            )
        )

    def test_should_capitalise_for_monthly_no_repayment_cap(
        self,
        mock_get_parameter: MagicMock,
    ):
        bp = loan.balloon_payments
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "amortisation_method": bp.no_repayment.AMORTISATION_METHOD,
                loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "Monthly",
            }
        )
        self.assertTrue(
            loan._no_repayment_to_be_capitalised(
                vault=sentinel.vault,
            )
        )

    def test_should_no_capitalise_for_no_cap_no_repayment(
        self,
        mock_get_parameter: MagicMock,
    ):
        bp = loan.balloon_payments
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "amortisation_method": bp.no_repayment.AMORTISATION_METHOD,
                loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "NO_CAPITALISATION",
            }
        )
        self.assertFalse(
            loan._no_repayment_to_be_capitalised(
                vault=sentinel.vault,
            )
        )

    def test_should_no_capitalise_for_minimum_repayment_loan(
        self,
        mock_get_parameter: MagicMock,
    ):
        bp = loan.balloon_payments
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "amortisation_method": bp.minimum_repayment.AMORTISATION_METHOD,
                loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "DAILY",
            }
        )
        self.assertFalse(
            loan._no_repayment_to_be_capitalised(
                vault=sentinel.vault,
            )
        )
