# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.line_of_credit.contracts.template import drawdown_loan
from library.line_of_credit.test.unit.test_drawdown_loan_common import (
    DEFAULT_DATETIME,
    DrawdownLoanTestBase,
)

# features
from library.features.common.fetchers import EFFECTIVE_OBSERVATION_FETCHER_ID

# contracts api
from contracts_api import DerivedParameterHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DerivedParameterHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)


@patch.object(drawdown_loan.common_parameters, "get_denomination_parameter")
@patch.object(drawdown_loan.early_repayment, "get_total_early_repayment_amount")
class DrawdownLoanDerivedParametersTest(DrawdownLoanTestBase):
    def test_derived_params_are_returned_correctly(
        self,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_get_denomination: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_get_total_early_repayment_amount.return_value = sentinel.early_repayment_amount
        mock_get_denomination.return_value = sentinel.denomination

        hook_args = DerivedParameterHookArguments(effective_datetime=DEFAULT_DATETIME)

        expected_derived_params = {
            drawdown_loan.PARAM_PER_LOAN_EARLY_REPAYMENT_AMOUNT: sentinel.early_repayment_amount
        }
        result: DerivedParameterHookResult = drawdown_loan.derived_parameter_hook(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertEqual(
            result,
            DerivedParameterHookResult(parameters_return_value=expected_derived_params),
        )

        mock_get_total_early_repayment_amount.assert_called_once_with(
            vault=mock_vault,
            early_repayment_fees=[drawdown_loan.overpayment.EarlyRepaymentOverpaymentFee],
            balances=sentinel.balances_dummy_balances_observation,
            denomination=sentinel.denomination,
            debt_addresses=drawdown_loan.lending_addresses.ALL_OUTSTANDING_SUPERVISOR,
            check_for_outstanding_accrued_interest_on_zero_principal=True,
        )
