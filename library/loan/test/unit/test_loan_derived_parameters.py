# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# library
from library.loan.contracts.template import loan
from library.loan.test.unit.test_loan_common import DEFAULT_DATETIME, LoanTestBase

# features
from library.features.common.fetchers import EFFECTIVE_OBSERVATION_FETCHER_ID
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)


@patch.object(loan.due_amount_calculation, "get_actual_next_repayment_date")
@patch.object(loan, "_use_expected_term")
@patch.object(loan, "_get_amortisation_feature")
@patch.object(loan, "_get_interest_rate_feature")
@patch.object(loan.emi, "get_expected_emi")
@patch.object(loan.derived_params, "get_total_remaining_principal")
@patch.object(loan.derived_params, "get_total_outstanding_debt")
@patch.object(loan.derived_params, "get_total_due_amount")
@patch.object(loan.early_repayment, "get_total_early_repayment_amount")
@patch.object(loan.overdue, "get_next_overdue_derived_parameter")
@patch.object(loan.utils, "get_parameter")
class DerivedParameterTest(LoanTestBase):
    @patch.object(loan.balloon_payments, "get_expected_balloon_payment_amount")
    @patch.object(loan.due_amount_calculation, "get_first_due_amount_calculation_datetime")
    def test_derived_params_are_returned_correctly_zero_elapsed_term(
        self,
        mock_get_first_due_amount_calculation_datetime: MagicMock,
        mock_get_expected_balloon_payment_amount: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_next_overdue_derived_parameter: MagicMock,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_get_total_due_amount: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_get_expected_emi: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_use_expected_term: MagicMock,
        mock_get_actual_next_repayment_date: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
            last_execution_datetimes={
                loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: None
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": "declining_principal",
                "denomination": sentinel.denomination,
                "principal": sentinel.principal,
            }
        )
        mock_get_total_outstanding_debt.return_value = sentinel.total_outstanding_debt
        mock_get_total_due_amount.return_value = sentinel.total_due_amount
        mock_get_total_early_repayment_amount.return_value = sentinel.total_early_repayment_amount
        mock_get_total_remaining_principal.return_value = sentinel.remaining_principal
        mock_get_expected_emi.return_value = sentinel.emi
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, sentinel.remaining_term))
        mock_get_amortisation_feature.return_value = MagicMock(term_details=mock_term_details)
        mock_use_expected_term.return_value = sentinel.use_expected_term
        mock_get_actual_next_repayment_date.return_value = sentinel.next_repayment_datetime
        mock_get_expected_balloon_payment_amount.return_value = sentinel.expected_balloon_payment
        mock_get_next_overdue_derived_parameter.return_value = sentinel.next_overdue_datetime
        mock_get_first_due_amount_calculation_datetime.return_value = sentinel.first_due_datetime

        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        derived_param_hook_result: DerivedParameterHookResult = loan.derived_parameter_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="denomination"),
                call(vault=mock_vault, name="amortisation_method", is_union=True),
            ]
        )
        mock_get_total_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_due_amount.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_early_repayment_amount.assert_called_once_with(
            vault=mock_vault,
            early_repayment_fees=loan.EARLY_REPAYMENT_FEES,
            balances=sentinel.balances_dummy_balances_observation,
        )
        mock_get_total_remaining_principal.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_expected_emi.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=sentinel.use_expected_term,
            interest_rate=sentinel.interest_rate_feature,
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_actual_next_repayment_date.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )
        mock_get_expected_balloon_payment_amount.assert_not_called()
        mock_get_next_overdue_derived_parameter.assert_called_once_with(
            vault=mock_vault,
            previous_due_amount_calculation_datetime=sentinel.first_due_datetime,
        )

        expected_derived_params = {
            "next_repayment_date": sentinel.next_repayment_datetime,
            "remaining_term": sentinel.remaining_term,
            "total_outstanding_debt": sentinel.total_outstanding_debt,
            "total_outstanding_payments": sentinel.total_due_amount,
            "expected_balloon_payment_amount": Decimal("0"),
            "total_remaining_principal": sentinel.remaining_principal,
            "total_early_repayment_amount": sentinel.total_early_repayment_amount,
            "equated_instalment_amount": sentinel.emi,
            "next_overdue_date": sentinel.next_overdue_datetime,
        }

        self.assertEqual(
            derived_param_hook_result,
            DerivedParameterHookResult(parameters_return_value=expected_derived_params),
        )

    @patch.object(loan.balloon_payments, "get_expected_balloon_payment_amount")
    @patch.object(loan.no_repayment, "get_balloon_payment_datetime")
    def test_derived_params_are_returned_correctly_zero_elapsed_term_and_no_repayment(
        self,
        mock_get_balloon_payment_datetime: MagicMock,
        mock_get_expected_balloon_payment_amount: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_next_overdue_derived_parameter: MagicMock,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_get_total_due_amount: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_get_expected_emi: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_use_expected_term: MagicMock,
        mock_get_actual_next_repayment_date: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
            last_execution_datetimes={
                loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: None
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": "no_repayment",
                "denomination": sentinel.denomination,
                "principal": sentinel.principal,
            }
        )
        mock_get_total_outstanding_debt.return_value = sentinel.total_outstanding_debt
        mock_get_total_due_amount.return_value = sentinel.total_due_amount
        mock_get_total_early_repayment_amount.return_value = sentinel.total_early_repayment_amount
        mock_get_total_remaining_principal.return_value = sentinel.remaining_principal
        mock_get_expected_emi.return_value = sentinel.emi
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, sentinel.remaining_term))
        mock_get_amortisation_feature.return_value = MagicMock(term_details=mock_term_details)
        mock_use_expected_term.return_value = sentinel.use_expected_term
        mock_get_balloon_payment_datetime.return_value = sentinel.no_repayment_datetime
        mock_get_actual_next_repayment_date.return_value = sentinel.next_repayment_datetime
        mock_get_expected_balloon_payment_amount.return_value = sentinel.expected_balloon_payment
        mock_get_next_overdue_derived_parameter.return_value = sentinel.next_overdue_datetime
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        derived_param_hook_result: DerivedParameterHookResult = loan.derived_parameter_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="denomination"),
                call(vault=mock_vault, name="amortisation_method", is_union=True),
            ]
        )
        mock_get_total_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_due_amount.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_early_repayment_amount.assert_called_once_with(
            vault=mock_vault,
            early_repayment_fees=loan.EARLY_REPAYMENT_FEES,
            balances=sentinel.balances_dummy_balances_observation,
        )
        mock_get_total_remaining_principal.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_expected_emi.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=sentinel.use_expected_term,
            interest_rate=sentinel.interest_rate_feature,
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_expected_balloon_payment_amount.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances_dummy_balances_observation,
            interest_rate_feature=sentinel.interest_rate_feature,
        )
        mock_get_next_overdue_derived_parameter.assert_called_once_with(
            vault=mock_vault,
            previous_due_amount_calculation_datetime=sentinel.no_repayment_datetime,
        )

        expected_derived_params = {
            "next_repayment_date": sentinel.no_repayment_datetime,
            "remaining_term": sentinel.remaining_term,
            "total_outstanding_debt": sentinel.total_outstanding_debt,
            "total_outstanding_payments": sentinel.total_due_amount,
            "total_remaining_principal": sentinel.remaining_principal,
            "total_early_repayment_amount": sentinel.total_early_repayment_amount,
            "equated_instalment_amount": sentinel.emi,
            "next_overdue_date": sentinel.next_overdue_datetime,
            "expected_balloon_payment_amount": sentinel.expected_balloon_payment,
        }

        self.assertEqual(
            derived_param_hook_result,
            DerivedParameterHookResult(parameters_return_value=expected_derived_params),
        )

    def test_derived_params_are_returned_correctly_greater_than_zero_elapsed_term(
        self,
        mock_get_parameter: MagicMock,
        mock_get_next_overdue_derived_parameter: MagicMock,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_get_total_due_amount: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_get_expected_emi: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_use_expected_term: MagicMock,
        mock_get_actual_next_repayment_date: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
            last_execution_datetimes={
                loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: sentinel.previous_due_datetime  # noqa: E501
            },
        )
        sentinel.amortisation_method = MagicMock(upper=lambda: sentinel.amortisation_method)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "amortisation_method": sentinel.amortisation_method,
            }
        )
        mock_get_total_outstanding_debt.return_value = sentinel.total_outstanding_debt
        mock_get_total_due_amount.return_value = sentinel.total_due_amount
        mock_get_total_early_repayment_amount.return_value = sentinel.total_early_repayment_amount
        mock_get_total_remaining_principal.return_value = sentinel.remaining_principal
        mock_get_expected_emi.return_value = sentinel.emi
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, sentinel.remaining_term))
        mock_get_amortisation_feature.return_value = MagicMock(term_details=mock_term_details)
        mock_use_expected_term.return_value = sentinel.use_expected_term
        mock_get_actual_next_repayment_date.side_effect = [
            sentinel.next_repayment_datetime,
            sentinel.previous_repayment_datetime,
        ]
        mock_get_next_overdue_derived_parameter.return_value = sentinel.next_overdue_datetime

        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        derived_param_hook_result: DerivedParameterHookResult = loan.derived_parameter_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        expected_calls = [
            call(vault=mock_vault, name="denomination"),
            call(vault=mock_vault, name="amortisation_method", is_union=True),
        ]
        mock_get_parameter.assert_has_calls(calls=expected_calls)
        mock_get_total_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_due_amount.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_early_repayment_amount.assert_called_once_with(
            vault=mock_vault,
            early_repayment_fees=loan.EARLY_REPAYMENT_FEES,
            balances=sentinel.balances_dummy_balances_observation,
        )
        mock_get_total_remaining_principal.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_expected_emi.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=sentinel.use_expected_term,
            interest_rate=sentinel.interest_rate_feature,
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_actual_next_repayment_date.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )
        mock_get_next_overdue_derived_parameter.assert_called_once_with(
            vault=mock_vault,
            previous_due_amount_calculation_datetime=sentinel.previous_due_datetime,
        )

        expected_derived_params = {
            "next_repayment_date": sentinel.next_repayment_datetime,
            "remaining_term": sentinel.remaining_term,
            "total_outstanding_debt": sentinel.total_outstanding_debt,
            "total_outstanding_payments": sentinel.total_due_amount,
            "total_remaining_principal": sentinel.remaining_principal,
            "total_early_repayment_amount": sentinel.total_early_repayment_amount,
            "equated_instalment_amount": sentinel.emi,
            "expected_balloon_payment_amount": Decimal("0"),
            "next_overdue_date": sentinel.next_overdue_datetime,
        }

        self.assertEqual(
            derived_param_hook_result,
            DerivedParameterHookResult(parameters_return_value=expected_derived_params),
        )

    @patch.object(loan.no_repayment, "get_balloon_payment_datetime")
    @patch.object(loan.balloon_payments, "get_expected_balloon_payment_amount")
    def test_derived_params_get_repayment_date_no_repayment(
        self,
        mock_get_expected_balloon_payment_amount: MagicMock,
        mock_no_repayment_get_balloon_payment_datetime: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_next_overdue_derived_parameter: MagicMock,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_get_total_due_amount: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_get_expected_emi: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_use_expected_term: MagicMock,
        mock_get_actual_next_repayment_date: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
            last_execution_datetimes={
                loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: None
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": loan.no_repayment.AMORTISATION_METHOD,
                "denomination": sentinel.denomination,
                "principal": sentinel.principal,
            }
        )
        mock_get_total_outstanding_debt.return_value = sentinel.total_outstanding_debt
        mock_get_total_early_repayment_amount.return_value = sentinel.total_early_repayment_amount
        mock_get_total_due_amount.return_value = sentinel.total_due_amount
        mock_get_total_remaining_principal.return_value = sentinel.remaining_principal
        mock_get_expected_emi.return_value = sentinel.emi
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, sentinel.remaining_term))
        mock_get_amortisation_feature.return_value = MagicMock(term_details=mock_term_details)
        mock_use_expected_term.return_value = sentinel.use_expected_term
        mock_no_repayment_get_balloon_payment_datetime.return_value = (
            sentinel.next_repayment_datetime
        )
        mock_get_expected_balloon_payment_amount.return_value = sentinel.expected_balloon_payment
        mock_get_next_overdue_derived_parameter.return_value = sentinel.next_overdue_datetime

        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        derived_param_hook_result: DerivedParameterHookResult = loan.derived_parameter_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="denomination"),
                call(vault=mock_vault, name="amortisation_method", is_union=True),
            ]
        )
        mock_get_total_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_due_amount.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_remaining_principal.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_expected_emi.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=sentinel.use_expected_term,
            interest_rate=sentinel.interest_rate_feature,
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_actual_next_repayment_date.assert_not_called()
        mock_no_repayment_get_balloon_payment_datetime.assert_called_once_with(vault=mock_vault)
        mock_get_expected_balloon_payment_amount.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances_dummy_balances_observation,
            interest_rate_feature=sentinel.interest_rate_feature,
        )
        mock_get_next_overdue_derived_parameter.assert_called_once_with(
            vault=mock_vault,
            previous_due_amount_calculation_datetime=sentinel.next_repayment_datetime,
        )

        expected_derived_params = {
            "next_repayment_date": sentinel.next_repayment_datetime,
            "remaining_term": sentinel.remaining_term,
            "total_early_repayment_amount": sentinel.total_early_repayment_amount,
            "total_outstanding_debt": sentinel.total_outstanding_debt,
            "total_outstanding_payments": sentinel.total_due_amount,
            "expected_balloon_payment_amount": sentinel.expected_balloon_payment,
            "total_remaining_principal": sentinel.remaining_principal,
            "equated_instalment_amount": sentinel.emi,
            "next_overdue_date": sentinel.next_overdue_datetime,
        }

        self.assertEqual(
            derived_param_hook_result,
            DerivedParameterHookResult(parameters_return_value=expected_derived_params),
        )

    @patch.object(loan.no_repayment, "get_balloon_payment_datetime")
    @patch.object(loan.balloon_payments, "get_expected_balloon_payment_amount")
    def test_derived_params_get_repayment_date_balloon_payment_after_final_due_calc(
        self,
        mock_get_expected_balloon_payment_amount: MagicMock,
        mock_no_repayment_get_balloon_payment_datetime: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_next_overdue_derived_parameter: MagicMock,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_get_total_due_amount: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_get_expected_emi: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_use_expected_term: MagicMock,
        mock_get_actual_next_repayment_date: MagicMock,
    ):
        # test vars
        final_due_calc = DEFAULT_DATETIME + relativedelta(months=12)
        test_time = DEFAULT_DATETIME + relativedelta(months=12, days=5)
        balloon_payment_offset_days = 10
        expected_datetime = datetime(2024, 1, 11, 0, 0, tzinfo=ZoneInfo(key="UTC"))
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
            last_execution_datetimes={
                loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: final_due_calc
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": loan.minimum_repayment.AMORTISATION_METHOD,
                "denomination": sentinel.denomination,
                "principal": sentinel.principal,
                loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: balloon_payment_offset_days,
            }
        )
        mock_get_total_outstanding_debt.return_value = sentinel.total_outstanding_debt
        mock_get_total_due_amount.return_value = sentinel.total_due_amount
        mock_get_total_remaining_principal.return_value = sentinel.remaining_principal
        mock_get_expected_emi.return_value = sentinel.emi
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_get_total_early_repayment_amount.return_value = sentinel.total_early_repayment_amount
        # Set 0 remaining term
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, 0))
        mock_get_amortisation_feature.return_value = MagicMock(term_details=mock_term_details)
        mock_use_expected_term.return_value = sentinel.use_expected_term
        mock_get_actual_next_repayment_date.return_value = final_due_calc
        mock_get_expected_balloon_payment_amount.return_value = sentinel.expected_balloon_payment
        mock_get_next_overdue_derived_parameter.return_value = final_due_calc + relativedelta(
            days=2
        )
        expected_next_overdue_datetime = final_due_calc + relativedelta(days=12)

        hook_args = DerivedParameterHookArguments(effective_datetime=test_time)
        derived_param_hook_result: DerivedParameterHookResult = loan.derived_parameter_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="denomination"),
                call(vault=mock_vault, name="amortisation_method", is_union=True),
            ]
        )
        mock_get_total_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_due_amount.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_remaining_principal.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_expected_emi.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=test_time,
            use_expected_term=sentinel.use_expected_term,
            interest_rate=sentinel.interest_rate_feature,
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_actual_next_repayment_date.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=test_time,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=0,
        )
        mock_no_repayment_get_balloon_payment_datetime.assert_not_called()
        mock_get_expected_balloon_payment_amount.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=test_time,
            balances=sentinel.balances_dummy_balances_observation,
            interest_rate_feature=sentinel.interest_rate_feature,
        )
        mock_get_next_overdue_derived_parameter.assert_called_once_with(
            vault=mock_vault,
            previous_due_amount_calculation_datetime=final_due_calc,
        )

        expected_derived_params = {
            "next_repayment_date": expected_datetime,
            "remaining_term": 0,
            "total_outstanding_debt": sentinel.total_outstanding_debt,
            "total_outstanding_payments": sentinel.total_due_amount,
            "expected_balloon_payment_amount": sentinel.expected_balloon_payment,
            "total_early_repayment_amount": sentinel.total_early_repayment_amount,
            "total_remaining_principal": sentinel.remaining_principal,
            "equated_instalment_amount": sentinel.emi,
            "next_overdue_date": expected_next_overdue_datetime,
        }

        self.assertEqual(
            derived_param_hook_result,
            DerivedParameterHookResult(parameters_return_value=expected_derived_params),
        )

    @patch.object(loan.no_repayment, "get_balloon_payment_datetime")
    @patch.object(loan.balloon_payments, "get_expected_balloon_payment_amount")
    def test_derived_params_get_repayment_date_balloon_payment_before_final_due_calc(
        self,
        mock_get_expected_balloon_payment_amount: MagicMock,
        mock_no_repayment_get_balloon_payment_datetime: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_next_overdue_derived_parameter: MagicMock,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_get_total_due_amount: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_get_expected_emi: MagicMock,
        mock_get_interest_rate_feature: MagicMock,
        mock_get_amortisation_feature: MagicMock,
        mock_use_expected_term: MagicMock,
        mock_get_actual_next_repayment_date: MagicMock,
    ):
        # test vars
        final_due_calc = DEFAULT_DATETIME + relativedelta(months=12)
        test_time = DEFAULT_DATETIME + relativedelta(months=12, days=-2)
        balloon_payment_offset_days = 10
        expected_datetime = final_due_calc
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
            last_execution_datetimes={
                loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: final_due_calc
                - relativedelta(months=1)
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "amortisation_method": loan.minimum_repayment.AMORTISATION_METHOD,
                "denomination": sentinel.denomination,
                "principal": sentinel.principal,
                loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: balloon_payment_offset_days,
            }
        )
        mock_get_total_outstanding_debt.return_value = sentinel.total_outstanding_debt
        mock_get_total_due_amount.return_value = sentinel.total_due_amount
        mock_get_total_remaining_principal.return_value = sentinel.remaining_principal
        mock_get_expected_emi.return_value = sentinel.emi
        mock_get_interest_rate_feature.return_value = sentinel.interest_rate_feature
        mock_get_total_early_repayment_amount.return_value = sentinel.total_early_repayment_amount
        # Set 0 remaining term
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, 0))
        mock_get_amortisation_feature.return_value = MagicMock(term_details=mock_term_details)
        mock_use_expected_term.return_value = sentinel.use_expected_term
        mock_get_actual_next_repayment_date.return_value = final_due_calc
        mock_get_expected_balloon_payment_amount.return_value = sentinel.expected_balloon_payment
        mock_get_next_overdue_derived_parameter.return_value = final_due_calc + relativedelta(
            days=2
        )

        expected_next_overdue_datetime = final_due_calc + relativedelta(days=2)

        hook_args = DerivedParameterHookArguments(effective_datetime=test_time)
        derived_param_hook_result: DerivedParameterHookResult = loan.derived_parameter_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="denomination"),
                call(vault=mock_vault, name="amortisation_method", is_union=True),
            ]
        )
        mock_get_total_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_due_amount.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_total_remaining_principal.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_expected_emi.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=test_time,
            use_expected_term=sentinel.use_expected_term,
            interest_rate=sentinel.interest_rate_feature,
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
        )
        mock_get_actual_next_repayment_date.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=test_time,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=0,
        )
        mock_no_repayment_get_balloon_payment_datetime.assert_not_called()
        mock_get_expected_balloon_payment_amount.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=test_time,
            balances=sentinel.balances_dummy_balances_observation,
            interest_rate_feature=sentinel.interest_rate_feature,
        )
        mock_get_next_overdue_derived_parameter.assert_called_once_with(
            vault=mock_vault,
            previous_due_amount_calculation_datetime=final_due_calc - relativedelta(months=1),
        )

        expected_derived_params = {
            "next_repayment_date": expected_datetime,
            "remaining_term": 0,
            "total_outstanding_debt": sentinel.total_outstanding_debt,
            "total_outstanding_payments": sentinel.total_due_amount,
            "expected_balloon_payment_amount": sentinel.expected_balloon_payment,
            "total_early_repayment_amount": sentinel.total_early_repayment_amount,
            "total_remaining_principal": sentinel.remaining_principal,
            "equated_instalment_amount": sentinel.emi,
            "next_overdue_date": expected_next_overdue_datetime,
        }

        self.assertEqual(
            derived_param_hook_result,
            DerivedParameterHookResult(parameters_return_value=expected_derived_params),
        )


class DerivedParameterHelperFunctionTest(LoanTestBase):
    @patch.object(loan.utils, "balance_at_coordinates")
    @patch.object(loan.overpayment, "get_overpayment_preference_parameter")
    def test_use_expected_term_increase_reduce_emi_preference(
        self, mock_get_overpayment_preference: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_get_overpayment_preference.return_value = "reduce_emi"
        mock_balance_at_coordinates.return_value = Decimal("10")
        self.assertTrue(
            loan._use_expected_term(
                vault=sentinel.vault, balances=sentinel.balances, denomination=sentinel.denomination
            )
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=loan.overpayment.OVERPAYMENT,
            denomination=sentinel.denomination,
        )
        mock_get_overpayment_preference.assert_called_once_with(vault=sentinel.vault)

    @patch.object(loan.utils, "balance_at_coordinates")
    @patch.object(loan.overpayment, "get_overpayment_preference_parameter")
    def test_use_expected_term_increase_term_preference_no_overpayment(
        self, mock_get_overpayment_preference: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_get_overpayment_preference.return_value = "reduce_term"
        # principal, overpayment
        mock_balance_at_coordinates.return_value = Decimal("0")
        self.assertTrue(
            loan._use_expected_term(
                vault=sentinel.vault, balances=sentinel.balances, denomination=sentinel.denomination
            )
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=loan.overpayment.OVERPAYMENT,
            denomination=sentinel.denomination,
        )
        mock_get_overpayment_preference.assert_called_once_with(vault=sentinel.vault)

    @patch.object(loan.utils, "balance_at_coordinates")
    @patch.object(loan.overpayment, "get_overpayment_preference_parameter")
    def test_use_expected_term_increase_term_preference_with_overpayment(
        self, mock_get_overpayment_preference: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_get_overpayment_preference.return_value = "reduce_term"
        # principal, overpayment
        mock_balance_at_coordinates.return_value = Decimal("10")
        self.assertFalse(
            loan._use_expected_term(
                vault=sentinel.vault, balances=sentinel.balances, denomination=sentinel.denomination
            )
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=loan.overpayment.OVERPAYMENT,
            denomination=sentinel.denomination,
        )
        mock_get_overpayment_preference.assert_called_once_with(vault=sentinel.vault)
