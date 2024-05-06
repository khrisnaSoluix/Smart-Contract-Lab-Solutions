# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# library
from library.line_of_credit.contracts.template import line_of_credit
from library.line_of_credit.test.unit.test_line_of_credit_common import (
    DEFAULT_DATETIME,
    LineOfCreditTestBase,
)

# features
from library.features.common.fetchers import EFFECTIVE_OBSERVATION_FETCHER_ID
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import DerivedParameterHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DerivedParameterHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)


@patch.object(line_of_credit.utils, "get_parameter")
@patch.object(line_of_credit, "_get_total_arrears_amount")
@patch.object(line_of_credit, "_get_total_early_repayment_amount")
@patch.object(line_of_credit, "_get_total_monthly_repayment_amount")
@patch.object(line_of_credit, "_get_total_original_principal")
@patch.object(line_of_credit, "_get_total_outstanding_due_amount")
@patch.object(line_of_credit, "_get_total_outstanding_principal")
@patch.object(line_of_credit, "_get_total_available_credit")
@patch.object(line_of_credit.due_amount_calculation, "get_actual_next_repayment_date")
class LineOfCreditDerivedParametersTest(LineOfCreditTestBase):
    def test_derived_params_are_returned_correctly(
        self,
        mock_get_actual_next_repayment_date: MagicMock,
        mock_get_total_available_credit: MagicMock,
        mock_get_total_outstanding_principal: MagicMock,
        mock_get_total_outstanding_due_amount: MagicMock,
        mock_get_total_original_principal: MagicMock,
        mock_get_total_monthly_repayment_amount: MagicMock,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_get_total_arrears_amount: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        last_execution_datetimes = {
            line_of_credit.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: (
                sentinel.last_execution_datetime
            )
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
            last_execution_datetimes=last_execution_datetimes,
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
            }
        )
        mock_get_total_arrears_amount.return_value = sentinel.total_arrears_amount
        mock_get_total_early_repayment_amount.return_value = sentinel.early_repayment_amount
        mock_get_total_monthly_repayment_amount.return_value = (
            sentinel.total_monthly_repayment_amount
        )
        mock_get_total_original_principal.return_value = sentinel.total_original_principal
        mock_get_total_outstanding_due_amount.return_value = sentinel.total_outstanding_due_amount
        mock_get_total_outstanding_principal.return_value = sentinel.total_outstanding_principal
        mock_get_total_available_credit.return_value = sentinel.total_available_credit
        mock_get_actual_next_repayment_date.return_value = sentinel.next_due_calc_datetime
        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)

        expected_derived_params = {
            line_of_credit.PARAM_TOTAL_ARREARS_AMOUNT: sentinel.total_arrears_amount,
            line_of_credit.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT: (
                sentinel.early_repayment_amount
            ),
            line_of_credit.PARAM_TOTAL_MONTHLY_REPAYMENT_AMOUNT: (
                sentinel.total_monthly_repayment_amount
            ),
            line_of_credit.PARAM_TOTAL_ORIGINAL_PRINCIPAL: sentinel.total_original_principal,
            line_of_credit.PARAM_TOTAL_OUTSTANDING_DUE_AMOUNT: (
                sentinel.total_outstanding_due_amount
            ),
            line_of_credit.PARAM_TOTAL_OUTSTANDING_PRINCIPAL: sentinel.total_outstanding_principal,
            line_of_credit.PARAM_TOTAL_AVAILABLE_CREDIT: sentinel.total_available_credit,
            line_of_credit.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE: (
                sentinel.next_due_calc_datetime
            ),
        }
        result: DerivedParameterHookResult = line_of_credit.derived_parameter_hook(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertEqual(
            result,
            DerivedParameterHookResult(parameters_return_value=expected_derived_params),
        )
        mock_get_total_arrears_amount.assert_called_once_with(
            denomination=sentinel.denomination,
            balances=sentinel.balances_dummy_balances_observation,
        )
        mock_get_total_early_repayment_amount.assert_called_once_with(
            vault=mock_vault,
            denomination=sentinel.denomination,
            balances=sentinel.balances_dummy_balances_observation,
        )
        mock_get_total_monthly_repayment_amount.assert_called_once_with(
            denomination=sentinel.denomination,
            balances=sentinel.balances_dummy_balances_observation,
        )
        mock_get_total_original_principal.assert_called_once_with(
            denomination=sentinel.denomination,
            balances=sentinel.balances_dummy_balances_observation,
        )
        mock_get_total_outstanding_due_amount.assert_called_once_with(
            denomination=sentinel.denomination,
            balances=sentinel.balances_dummy_balances_observation,
        )
        mock_get_total_outstanding_principal.assert_called_once_with(
            denomination=sentinel.denomination,
            balances=sentinel.balances_dummy_balances_observation,
        )
        mock_get_total_available_credit.assert_called_once_with(
            vault=mock_vault, total_outstanding_principal=sentinel.total_outstanding_principal
        )
        mock_get_actual_next_repayment_date.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=hook_args.effective_datetime,
            elapsed_term=1,
            remaining_term=1,
        )


@patch.object(line_of_credit.utils, "get_parameter")
@patch.object(line_of_credit.overpayment, "get_max_overpayment_fee")
@patch.object(line_of_credit.utils, "sum_balances")
class LineOfCreditGetTotalEarlyRepaymentAmountTest(LineOfCreditTestBase):
    def test_get_total_early_repayment_amount_returned_correctly(
        self,
        mock_sum_balances: MagicMock,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "overpayment_fee_rate": sentinel.overpayment_fee_rate,
            }
        )
        mock_get_max_overpayment_fee.return_value = Decimal("1")
        mock_sum_balances.return_value = Decimal("10")
        result = line_of_credit._get_total_early_repayment_amount(
            vault=mock_vault, denomination=sentinel.denomination, balances=sentinel.balances
        )
        self.assertEqual(
            result,
            Decimal("11"),
        )
        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="overpayment_fee_rate"),
            ]
        )
        mock_get_max_overpayment_fee.assert_called_once_with(
            fee_rate=sentinel.overpayment_fee_rate,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=2,
            principal_address="TOTAL_PRINCIPAL",
        )
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=line_of_credit.line_of_credit_addresses.OUTSTANDING_DEBT_ADDRESSES,
            denomination=sentinel.denomination,
            decimal_places=2,
        )


@patch.object(line_of_credit.utils, "sum_balances")
class GetTotalArrearsTest(LineOfCreditTestBase):
    def test_total_arrears_amount_returned_correctly(self, mock_sum_balances: MagicMock):
        mock_sum_balances.return_value = sentinel.total_arrears

        result = line_of_credit._get_total_arrears_amount(
            denomination=sentinel.denomination, balances=sentinel.balances
        )

        self.assertEqual(result, sentinel.total_arrears)

        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=[
                line_of_credit.line_of_credit_addresses.TOTAL_PRINCIPAL_OVERDUE,
                line_of_credit.line_of_credit_addresses.TOTAL_INTEREST_OVERDUE,
            ],
            denomination=sentinel.denomination,
        )


@patch.object(line_of_credit.utils, "sum_balances")
class GetTotalMonthlyRepaymentAmountTest(LineOfCreditTestBase):
    def test_total_monthly_repayment_amount_returned_correctly(self, mock_sum_balances: MagicMock):
        mock_sum_balances.return_value = sentinel.total_monthly_repayment_amount

        result = line_of_credit._get_total_monthly_repayment_amount(
            denomination=sentinel.denomination, balances=sentinel.balances
        )

        self.assertEqual(result, sentinel.total_monthly_repayment_amount)

        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=[line_of_credit.line_of_credit_addresses.TOTAL_EMI],
            denomination=sentinel.denomination,
            decimal_places=2,
        )


@patch.object(line_of_credit.utils, "sum_balances")
class GetTotalOutstandingDueAmountTest(LineOfCreditTestBase):
    def test_total_outstanding_due_amount_returned_correctly(self, mock_sum_balances: MagicMock):
        mock_sum_balances.return_value = sentinel.total_outstanding_due_amount

        result = line_of_credit._get_total_outstanding_due_amount(
            denomination=sentinel.denomination, balances=sentinel.balances
        )

        self.assertEqual(result, sentinel.total_outstanding_due_amount)

        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=[
                line_of_credit.line_of_credit_addresses.TOTAL_PRINCIPAL_DUE,
                line_of_credit.line_of_credit_addresses.TOTAL_INTEREST_DUE,
            ],
            denomination=sentinel.denomination,
        )


@patch.object(line_of_credit.utils, "sum_balances")
class GetTotalOriginalPrincipal(LineOfCreditTestBase):
    def test_total_original_principal_returned_correctly(self, mock_sum_balances: MagicMock):
        mock_sum_balances.return_value = sentinel.total_original_principal

        result = line_of_credit._get_total_original_principal(
            denomination=sentinel.denomination, balances=sentinel.balances
        )

        self.assertEqual(result, sentinel.total_original_principal)

        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=[line_of_credit.line_of_credit_addresses.TOTAL_ORIGINAL_PRINCIPAL],
            denomination=sentinel.denomination,
            decimal_places=2,
        )


@patch.object(line_of_credit.utils, "sum_balances")
class GetTotalOutstandingPrincipal(LineOfCreditTestBase):
    def test_total_outstanding_principal_returned_correctly(self, mock_sum_balances: MagicMock):
        mock_sum_balances.return_value = sentinel.total_outstanding_principal

        result = line_of_credit._get_total_outstanding_principal(
            denomination=sentinel.denomination, balances=sentinel.balances
        )

        self.assertEqual(result, sentinel.total_outstanding_principal)

        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=[
                line_of_credit.line_of_credit_addresses.TOTAL_PRINCIPAL,
                line_of_credit.line_of_credit_addresses.TOTAL_PRINCIPAL_DUE,
                line_of_credit.line_of_credit_addresses.TOTAL_PRINCIPAL_OVERDUE,
            ],
            denomination=sentinel.denomination,
        )


@patch.object(line_of_credit.utils, "get_parameter")
class GetTotaLAvailableCredit(LineOfCreditTestBase):
    def test_total_available_credit_returned_correctly(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "credit_limit": Decimal("150"),
            }
        )

        result = line_of_credit._get_total_available_credit(
            vault=sentinel.vault, total_outstanding_principal=Decimal("30")
        )

        self.assertEqual(result, Decimal("120"))

        mock_get_parameter.assert_called_once_with(vault=sentinel.vault, name="credit_limit")
