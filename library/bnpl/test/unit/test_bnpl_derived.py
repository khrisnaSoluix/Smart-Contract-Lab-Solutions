# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# library
import library.bnpl.contracts.template.bnpl as bnpl
from library.bnpl.test.unit.test_bnpl_common import BNPLTest

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import DerivedParameterHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DerivedParameterHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)

DEFAULT_DATETIME = datetime(2023, 1, 1, tzinfo=bnpl.UTC_ZONE)


@patch.object(bnpl.derived_params, "get_principal_paid_to_date")
@patch.object(bnpl.derived_params, "get_total_remaining_principal")
@patch.object(bnpl.derived_params, "get_total_outstanding_debt")
@patch.object(bnpl.config_repayment_frequency, "get_elapsed_and_remaining_terms")
@patch.object(bnpl.config_repayment_frequency, "get_next_due_amount_calculation_date")
@patch.object(bnpl.due_amount_calculation, "get_emi")
@patch.object(bnpl.utils, "get_parameter")
class DerivedParameterHookTest(BNPLTest):
    default_repayment_frequency = BNPLTest.default_repayment_frequency
    default_repayment_count = BNPLTest.default_repayment_count
    default_principal = Decimal("100000")
    default_parameters = {
        bnpl.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
        bnpl.config_repayment_frequency.PARAM_REPAYMENT_FREQUENCY: default_repayment_frequency,
        bnpl.lending_params.PARAM_TOTAL_REPAYMENT_COUNT: default_repayment_count,
        bnpl.disbursement.PARAM_PRINCIPAL: default_principal,
    }

    def test_derived_parameter_hook_for_equated_instalment_amount(
        self,
        mock_get_parameter: MagicMock,
        mock_get_emi: MagicMock,
        mock_get_next_due_amount_calculation_date: MagicMock,
        mock_get_elapsed_and_remaining_terms: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_get_principal_paid_to_date: MagicMock,
    ):
        dummy_balances_observation = SentinelBalancesObservation("dummy_balances_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: dummy_balances_observation
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_get_emi.return_value = Decimal("1000")
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)

        result: DerivedParameterHookResult = bnpl.derived_parameter_hook(mock_vault, hook_args)
        actual = result.parameters_return_value["equated_instalment_amount"]
        expected = Decimal("1000")

        self.assertEqual(actual, expected)

        mock_get_emi.assert_called_once_with(
            balances=dummy_balances_observation.balances,
            denomination=DEFAULT_DENOMINATION,
        )

    def test_derived_parameter_hook_for_loan_end_date(
        self,
        mock_get_parameter: MagicMock,
        mock_get_emi: MagicMock,
        mock_get_next_due_amount_calculation_date: MagicMock,
        mock_get_elapsed_and_remaining_terms: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_get_principal_paid_to_date: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_get_next_due_amount_calculation_date.return_value = sentinel.loan_end_date

        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result: DerivedParameterHookResult = bnpl.derived_parameter_hook(mock_vault, hook_args)
        actual = result.parameters_return_value["loan_end_date"]
        expected = sentinel.loan_end_date

        self.assertEqual(actual, expected)
        self.assertEqual(
            mock_get_next_due_amount_calculation_date.call_args_list[0],
            call(
                vault=mock_vault,
                effective_date=datetime.max.replace(tzinfo=bnpl.UTC_ZONE),
                total_repayment_count=self.default_repayment_count
                - bnpl.emi_in_advance.EMI_IN_ADVANCE_OFFSET,
                repayment_frequency=self.default_repayment_frequency,
            ),
        )

    def test_derived_parameter_hook_for_next_repayment_date(
        self,
        mock_get_parameter: MagicMock,
        mock_get_emi: MagicMock,
        mock_get_next_due_amount_calculation_date: MagicMock,
        mock_get_elapsed_and_remaining_terms: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_get_principal_paid_to_date: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_get_next_due_amount_calculation_date.return_value = sentinel.next_repayment_date

        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result: DerivedParameterHookResult = bnpl.derived_parameter_hook(mock_vault, hook_args)
        actual = result.parameters_return_value["next_repayment_date"]
        expected = sentinel.next_repayment_date

        self.assertEqual(actual, expected)
        self.assertEqual(
            mock_get_next_due_amount_calculation_date.call_args_list[1],
            call(
                vault=mock_vault,
                effective_date=DEFAULT_DATETIME,
                total_repayment_count=self.default_repayment_count
                - bnpl.emi_in_advance.EMI_IN_ADVANCE_OFFSET,
                repayment_frequency=self.default_repayment_frequency,
            ),
        )

    def test_derived_parameter_hook_for_remaining_term(
        self,
        mock_get_parameter: MagicMock,
        mock_get_emi: MagicMock,
        mock_get_next_due_amount_calculation_date: MagicMock,
        mock_get_elapsed_and_remaining_terms: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_get_principal_paid_to_date: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
            creation_date=sentinel.creation_date,
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_get_elapsed_and_remaining_terms.return_value = (
            bnpl.config_repayment_frequency.LoanTerms(
                remaining=sentinel.remaining_term, elapsed=sentinel.elapsed_term
            )
        )

        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result: DerivedParameterHookResult = bnpl.derived_parameter_hook(mock_vault, hook_args)
        actual = result.parameters_return_value["remaining_term"]
        expected = f"{sentinel.remaining_term} month(s)"

        self.assertEqual(actual, expected)
        mock_get_elapsed_and_remaining_terms.assert_called_once_with(
            account_creation_date=sentinel.creation_date,
            effective_date=DEFAULT_DATETIME,
            total_repayment_count=self.default_repayment_count
            - bnpl.emi_in_advance.EMI_IN_ADVANCE_OFFSET,
            repayment_frequency=self.default_repayment_frequency,
        )

    def test_derived_parameter_hook_for_total_outstanding_debt(
        self,
        mock_get_parameter: MagicMock,
        mock_get_emi: MagicMock,
        mock_get_next_due_amount_calculation_date: MagicMock,
        mock_get_elapsed_and_remaining_terms: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_get_principal_paid_to_date: MagicMock,
    ):
        dummy_balances_observation = SentinelBalancesObservation("dummy_balances_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: dummy_balances_observation
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_get_total_outstanding_debt.return_value = Decimal("1000")

        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result: DerivedParameterHookResult = bnpl.derived_parameter_hook(mock_vault, hook_args)
        actual = result.parameters_return_value["total_outstanding_debt"]
        expected = Decimal("1000")

        self.assertEqual(actual, expected)
        mock_get_total_outstanding_debt.assert_called_once_with(
            balances=dummy_balances_observation.balances,
            denomination=DEFAULT_DENOMINATION,
        )

    def test_derived_parameter_hook_for_total_remaining_principal(
        self,
        mock_get_parameter: MagicMock,
        mock_get_emi: MagicMock,
        mock_get_next_due_amount_calculation_date: MagicMock,
        mock_get_elapsed_and_remaining_terms: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_get_principal_paid_to_date: MagicMock,
    ):
        dummy_balances_observation = SentinelBalancesObservation("dummy_balances_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: dummy_balances_observation
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_get_total_remaining_principal.return_value = Decimal("144000")

        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result: DerivedParameterHookResult = bnpl.derived_parameter_hook(mock_vault, hook_args)
        actual: Decimal = result.parameters_return_value["total_remaining_principal"]
        expected = Decimal("144000")

        self.assertEqual(actual, expected)
        mock_get_total_remaining_principal.assert_called_once_with(
            balances=dummy_balances_observation.balances,
            denomination=DEFAULT_DENOMINATION,
        )

    def test_derived_parameter_hook_for_principal_paid_to_date(
        self,
        mock_get_parameter: MagicMock,
        mock_get_emi: MagicMock,
        mock_get_next_due_amount_calculation_date: MagicMock,
        mock_get_elapsed_and_remaining_terms: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_total_remaining_principal: MagicMock,
        mock_get_principal_paid_to_date: MagicMock,
    ):
        dummy_balances_observation = SentinelBalancesObservation("dummy_balances_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: dummy_balances_observation
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.default_parameters
        )
        mock_get_principal_paid_to_date.return_value = Decimal("70000")

        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result: DerivedParameterHookResult = bnpl.derived_parameter_hook(mock_vault, hook_args)
        actual: Decimal = result.parameters_return_value["principal_paid_to_date"]
        expected = Decimal("70000")
        self.assertEqual(actual, expected)
        mock_get_principal_paid_to_date.assert_called_once_with(
            original_principal=self.default_principal,
            balances=dummy_balances_observation.balances,
            denomination=DEFAULT_DENOMINATION,
        )
