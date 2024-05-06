# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# library
from library.mortgage.contracts.template import mortgage
from library.mortgage.test.unit.test_mortgage_common import MortgageTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import DerivedParameterHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)


@patch.object(mortgage, "_use_expected_term")
@patch.object(mortgage, "_get_early_repayment_fee")
@patch.object(mortgage.overpayment_allowance, "get_allowance_usage_fee")
@patch.object(mortgage.overpayment_allowance, "get_overpayment_allowance_fee_for_early_repayment")
@patch.object(mortgage, "_get_actual_next_repayment_dateeter")
@patch.object(mortgage, "_get_outstanding_payments_amount")
@patch.object(mortgage, "_get_outstanding_principal")
@patch.object(mortgage, "_is_within_interest_only_term")
@patch.object(mortgage.fixed_to_variable, "is_within_fixed_rate_term")
@patch.object(mortgage.derived_params, "get_total_outstanding_debt")
@patch.object(mortgage.utils, "get_parameter")
class DerivedParametersTest(MortgageTestBase):
    # define common return types to avoid duplicated definitions across tests
    common_get_param_return_values = {
        "denomination": sentinel.denomination,
        "application_precision": 2,
        "overpayment_allowance_fee_percentage": Decimal("0.01"),
    }

    bof_mapping = {
        mortgage.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation("effective")
    }

    def setUp(self):
        # re-use mock across tests and retain ability to inspect calls if required
        overpayment_allowance_patcher = patch.object(
            mortgage.overpayment_allowance,
            "get_overpayment_allowance_status",
            # original allowance, used allowance
            MagicMock(return_value=(Decimal("10"), Decimal("2"))),
        )
        term_details_patcher = patch.object(
            mortgage.declining_principal,
            "term_details",
            MagicMock(return_value=(sentinel.elapsed_term, sentinel.remaining_term)),
        )
        self.addCleanup(overpayment_allowance_patcher.stop)
        self.addCleanup(term_details_patcher.stop)
        self.mock_overpayment_allowance_status = overpayment_allowance_patcher.start()
        self.mock_term_details_patcher = term_details_patcher.start()

    def test_total_outstanding_debt(
        self,
        mock_get_parameter: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_is_within_term: MagicMock,
        mock_get_outstanding_principal: MagicMock,
        mock_get_outstanding_payments_amount: MagicMock,
        mock_get_actual_next_repayment_dateeter: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_get_allowance_usage_fee: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_use_expected_term: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.bof_mapping,
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_get_param_return_values
        )
        mock_get_total_outstanding_debt.return_value = Decimal("100")

        # construct expected result
        expected_total_outstanding_debt = Decimal("100")

        # run function
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = mortgage.derived_parameter_hook(mock_vault, hook_args)
        actual = result.parameters_return_value["total_outstanding_debt"]
        self.assertEqual(actual, expected_total_outstanding_debt)

    def test_is_fixed_interest(
        self,
        mock_get_parameter: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_is_within_term: MagicMock,
        mock_get_outstanding_principal: MagicMock,
        mock_get_outstanding_payments_amount: MagicMock,
        mock_get_actual_next_repayment_dateeter: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_get_allowance_usage_fee: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_use_expected_term: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.bof_mapping,
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_get_param_return_values
        )
        mock_is_within_fixed_rate_term.return_value = True

        # construct expected result
        expected_is_fixed_interest = "True"

        # run function
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = mortgage.derived_parameter_hook(mock_vault, hook_args)
        actual = result.parameters_return_value["is_fixed_interest"]
        self.assertEqual(actual, expected_is_fixed_interest)

    def test_is_interest_only_term(
        self,
        mock_get_parameter: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_is_within_term: MagicMock,
        mock_get_outstanding_principal: MagicMock,
        mock_get_outstanding_payments_amount: MagicMock,
        mock_get_actual_next_repayment_dateeter: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_get_allowance_usage_fee: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_use_expected_term: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.bof_mapping,
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_get_param_return_values
        )
        mock_is_within_term.return_value = True

        # construct expected result
        expected_is_interest_only_term = "True"

        # run function
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = mortgage.derived_parameter_hook(mock_vault, hook_args)
        actual = result.parameters_return_value["is_interest_only_term"]
        self.assertEqual(actual, expected_is_interest_only_term)

    def test_total_remaining_principal(
        self,
        mock_get_parameter: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_is_within_term: MagicMock,
        mock_get_outstanding_principal: MagicMock,
        mock_get_outstanding_payments_amount: MagicMock,
        mock_get_actual_next_repayment_dateeter: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_get_allowance_usage_fee: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_use_expected_term: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.bof_mapping,
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_get_param_return_values
        )
        mock_get_outstanding_principal.return_value = Decimal("100")

        # construct expected result
        expected_total_remaining_principal = Decimal("100")

        # run function
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = mortgage.derived_parameter_hook(mock_vault, hook_args)
        actual = result.parameters_return_value["total_remaining_principal"]
        self.assertEqual(actual, expected_total_remaining_principal)

    def test_outstanding_payments(
        self,
        mock_get_parameter: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_is_within_term: MagicMock,
        mock_get_outstanding_principal: MagicMock,
        mock_get_outstanding_payments_amount: MagicMock,
        mock_get_actual_next_repayment_dateeter: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_get_allowance_usage_fee: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_use_expected_term: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.bof_mapping,
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_get_param_return_values
        )
        mock_get_outstanding_payments_amount.return_value = Decimal("100")

        # construct expected result
        expected_outstanding_payments = Decimal("100")

        # run function
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = mortgage.derived_parameter_hook(mock_vault, hook_args)
        actual = result.parameters_return_value["outstanding_payments"]
        self.assertEqual(actual, expected_outstanding_payments)

    def test_next_repayment_date(
        self,
        mock_get_parameter: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_is_within_term: MagicMock,
        mock_get_outstanding_principal: MagicMock,
        mock_get_outstanding_payments_amount: MagicMock,
        mock_get_actual_next_repayment_dateeter: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_get_allowance_usage_fee: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_use_expected_term: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.bof_mapping,
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_get_param_return_values
        )
        mock_get_actual_next_repayment_dateeter.return_value = DEFAULT_DATETIME

        # construct expected result
        expected_next_repayment_date = DEFAULT_DATETIME

        # run function
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = mortgage.derived_parameter_hook(mock_vault, hook_args)
        actual = result.parameters_return_value["next_repayment_date"]
        self.assertEqual(actual, expected_next_repayment_date)

    def test_remaining_term_without_expected_term(
        self,
        mock_get_parameter: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_is_within_term: MagicMock,
        mock_get_outstanding_principal: MagicMock,
        mock_get_outstanding_payments_amount: MagicMock,
        mock_get_actual_next_repayment_dateeter: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_get_allowance_usage_fee: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_use_expected_term: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.bof_mapping,
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_get_param_return_values,
        )
        mock_use_expected_term.return_value = False

        # construct expected result
        expected_remaining_term = sentinel.remaining_term

        # run function
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = mortgage.derived_parameter_hook(mock_vault, hook_args)
        actual = result.parameters_return_value["remaining_term"]
        self.assertEqual(actual, expected_remaining_term)
        mock_use_expected_term.assert_called_once_with(
            vault=mock_vault,
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
        )
        self.mock_term_details_patcher.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=False,
            interest_rate=mortgage.fixed_to_variable.InterestRate,
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
        )

    def test_remaining_term_with_expected_term(
        self,
        mock_get_parameter: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_is_within_term: MagicMock,
        mock_get_outstanding_principal: MagicMock,
        mock_get_outstanding_payments_amount: MagicMock,
        mock_get_actual_next_repayment_dateeter: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_get_allowance_usage_fee: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_use_expected_term: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.bof_mapping,
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_get_param_return_values,
        )
        mock_use_expected_term.return_value = True

        # construct expected result
        expected_remaining_term = sentinel.remaining_term

        # run function
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = mortgage.derived_parameter_hook(mock_vault, hook_args)
        actual = result.parameters_return_value["remaining_term"]
        self.assertEqual(actual, expected_remaining_term)
        mock_use_expected_term.assert_called_once_with(
            vault=mock_vault,
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
        )
        self.mock_term_details_patcher.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
            interest_rate=mortgage.fixed_to_variable.InterestRate,
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
        )

    def test_overpayment_allowance(
        self,
        mock_get_parameter: MagicMock,
        mock_get_all_outstanding_debt: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_is_within_term: MagicMock,
        mock_get_outstanding_principal: MagicMock,
        mock_get_outstanding_payments_amount: MagicMock,
        mock_get_actual_next_repayment_dateeter: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_get_allowance_usage_fee: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_use_expected_term: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.bof_mapping,
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_get_param_return_values
        )
        mock_overpayment_fee = Decimal("5")
        mock_get_allowance_usage_fee.return_value = mock_overpayment_fee

        # construct expected result
        expected_remaining_allowance = Decimal("8")
        expected_used_allowance = Decimal("2")

        # run function
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = mortgage.derived_parameter_hook(mock_vault, hook_args)
        self.assertEqual(
            result.parameters_return_value[
                mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_REMAINING
            ],
            expected_remaining_allowance,
        )
        self.assertEqual(
            result.parameters_return_value[
                mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_USED
            ],
            expected_used_allowance,
        )
        self.assertEqual(
            result.parameters_return_value[
                mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE
            ],
            mock_overpayment_fee,
        )
        self.mock_overpayment_allowance_status.assert_called_once_with(
            vault=mock_vault, effective_datetime=hook_args.effective_datetime
        )
        mock_get_allowance_usage_fee.assert_called_once_with(
            allowance=expected_remaining_allowance + expected_used_allowance,
            used_allowance=expected_used_allowance,
            overpayment_allowance_fee_percentage=Decimal("0.01"),
        )

    def test_early_repayment_fee(
        self,
        mock_get_parameter: MagicMock,
        mock_get_all_outstanding_debt: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_is_within_term: MagicMock,
        mock_get_outstanding_principal: MagicMock,
        mock_get_outstanding_payments_amount: MagicMock,
        mock_get_actual_next_repayment_dateeter: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_get_allowance_usage_fee: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_use_expected_term: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.bof_mapping,
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_get_param_return_values
        )
        mock_get_outstanding_principal.return_value = Decimal("150")
        mock_early_repayment_fee = Decimal("1.50")
        mock_get_early_repayment_fee.return_value = mock_early_repayment_fee

        # run function
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = mortgage.derived_parameter_hook(mock_vault, hook_args)
        self.assertEqual(
            result.parameters_return_value[mortgage.PARAM_DERIVED_EARLY_REPAYMENT_FEE],
            mock_early_repayment_fee,
        )
        mock_get_early_repayment_fee.assert_called_once_with(
            vault=mock_vault,
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
        )

    def test_total_early_repayment_fee(
        self,
        mock_get_parameter: MagicMock,
        mock_get_all_outstanding_debt: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_is_within_term: MagicMock,
        mock_get_outstanding_principal: MagicMock,
        mock_get_outstanding_payments_amount: MagicMock,
        mock_get_actual_next_repayment_dateeter: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_get_allowance_usage_fee: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_use_expected_term: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.bof_mapping,
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_get_param_return_values
        )
        mock_get_overpayment_allowance_fee_for_early_repayment.return_value = Decimal("20.50")
        mock_get_early_repayment_fee.return_value = Decimal("1.50")

        # run function
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = mortgage.derived_parameter_hook(mock_vault, hook_args)
        self.assertEqual(
            result.parameters_return_value[mortgage.PARAM_TOTAL_EARLY_REPAYMENT_FEE],
            Decimal("22.00"),
        )


class DerivedParametersHelpersTest(MortgageTestBase):
    @patch.object(mortgage, "_calculate_next_due_amount_calculation_datetime")
    @patch.object(mortgage.utils, "get_parameter")
    def test_get_actual_next_repayment_dateeter(
        self,
        mock_get_parameter: MagicMock,
        mock_calculate_next_due_amount_calculation_datetime: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            last_execution_datetimes={
                mortgage.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: sentinel.last_event
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={mortgage.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: 5}
        )
        mock_calculate_next_due_amount_calculation_datetime.return_value = sentinel.next_datetime

        # construct expected result
        expected_result = sentinel.next_datetime

        # run function
        result = mortgage._get_actual_next_repayment_dateeter(
            mock_vault, sentinel.effective_datetime
        )
        self.assertEqual(result, expected_result)
        mock_get_parameter.assert_called_once_with(
            mock_vault,
            name=mortgage.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY,
            at_datetime=sentinel.effective_datetime,
        )
        mock_calculate_next_due_amount_calculation_datetime.assert_called_once_with(
            mock_vault,
            sentinel.effective_datetime,
            sentinel.last_event,
            due_amount_calculation_day=5,
        )

    @patch.object(mortgage, "_get_outstanding_principal")
    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.utils, "round_decimal")
    def test_get_early_repayment_fee_percentage_fee_is_applied(
        self,
        mock_round_decimal: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_outstanding_principal: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE: Decimal(
                    "0.05"
                ),
                mortgage.PARAM_EARLY_REPAYMENT_FEE: Decimal("-1"),
            }
        )
        mock_get_outstanding_principal.return_value = Decimal("100")
        # 0.05 * 100
        mock_round_decimal.return_value = Decimal("5.00")

        # run function
        result = mortgage._get_early_repayment_fee(
            vault=sentinel.vault,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, Decimal("5.00"))
        mock_get_parameter.assert_has_calls(
            [
                call(vault=sentinel.vault, name=mortgage.PARAM_EARLY_REPAYMENT_FEE),
                call(
                    vault=sentinel.vault,
                    name=mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE,
                ),
            ],
        )
        mock_get_outstanding_principal.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_round_decimal.assert_called_once_with(
            amount=Decimal("5.00"),
            decimal_places=2,
        )

    @patch.object(mortgage, "_get_outstanding_principal")
    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.utils, "round_decimal")
    def test_get_early_repayment_fee_flat_fee_is_applied(
        self,
        mock_round_decimal: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_outstanding_principal: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                mortgage.PARAM_EARLY_REPAYMENT_FEE: Decimal("20.25"),
            }
        )

        # run function
        result = mortgage._get_early_repayment_fee(
            vault=sentinel.vault,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, Decimal("20.25"))
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault, name=mortgage.PARAM_EARLY_REPAYMENT_FEE
        )
        mock_get_outstanding_principal.assert_not_called()
        mock_round_decimal.assert_not_called()

    @patch.object(mortgage, "_get_outstanding_principal")
    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.utils, "round_decimal")
    def test_get_early_repayment_fee_no_fee_is_applied(
        self,
        mock_round_decimal: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_outstanding_principal: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                mortgage.PARAM_EARLY_REPAYMENT_FEE: Decimal("0"),
            }
        )

        # run function
        result = mortgage._get_early_repayment_fee(
            vault=sentinel.vault,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, Decimal("0"))
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault, name=mortgage.PARAM_EARLY_REPAYMENT_FEE
        )
        mock_get_outstanding_principal.assert_not_called()
        mock_round_decimal.assert_not_called()
