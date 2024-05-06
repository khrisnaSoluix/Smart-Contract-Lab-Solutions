# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.loan.contracts.template import loan
from library.loan.test.unit.test_loan_common import LoanTestBase

# features
import library.features.v4.lending.lending_addresses as lending_addresses
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import DeactivationHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DATETIME,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DeactivationHookResult,
    PostingInstructionsDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelRejection,
)


@patch.object(loan.close_loan, "reject_closure_when_outstanding_debt")
@patch.object(loan.utils, "get_parameter")
class DeactivationTest(LoanTestBase):
    def test_deactivation_hook_with_remaining_debt(
        self, mock_get_parameter: MagicMock, mock_reject_closure: MagicMock
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        rejection = SentinelRejection("rejection")
        mock_reject_closure.return_value = rejection

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
            }
        )

        # expected result
        expected_result = DeactivationHookResult(rejection=rejection)

        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = loan.deactivation_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

        mock_reject_closure.assert_called_once_with(
            balances=sentinel.balances_live,
            denomination=sentinel.denomination,
            debt_addresses=lending_addresses.ALL_OUTSTANDING,
        )

    @patch.object(loan, "_get_residual_cleanup_postings")
    @patch.object(loan.overpayment, "OverpaymentResidualCleanupFeature")
    @patch.object(loan.due_amount_calculation, "DueAmountCalculationResidualCleanupFeature")
    @patch.object(loan.close_loan, "net_balances")
    def test_deactivation_hook_zero_remaining_debt_with_custom_instructions(
        self,
        mock_net_balances: MagicMock,
        mock_due_amount_calculation_cleanup_feature: MagicMock,
        mock_overpayment_cleanup_feature: MagicMock,
        mock_get_residual_cleanup_postings: MagicMock,
        mock_get_parameter: MagicMock,
        mock_reject_closure: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_reject_closure.return_value = None

        expected_cis = SentinelCustomInstruction("end_of_loan")
        mock_net_balances.return_value = [expected_cis]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
            }
        )

        # expected result
        expected_result = DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[expected_cis], value_datetime=DEFAULT_DATETIME
                )
            ]
        )

        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = loan.deactivation_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

        mock_reject_closure.assert_called_once_with(
            balances=sentinel.balances_live,
            denomination=sentinel.denomination,
            debt_addresses=lending_addresses.ALL_OUTSTANDING,
        )
        mock_net_balances.assert_called_once_with(
            balances=sentinel.balances_live,
            denomination=sentinel.denomination,
            account_id=ACCOUNT_ID,
            residual_cleanup_features=[
                mock_overpayment_cleanup_feature,
                mock_due_amount_calculation_cleanup_feature,
                loan.lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=mock_get_residual_cleanup_postings
                ),
            ],
        )

    @patch.object(loan, "_get_residual_cleanup_postings")
    @patch.object(loan.overpayment, "OverpaymentResidualCleanupFeature")
    @patch.object(loan.due_amount_calculation, "DueAmountCalculationResidualCleanupFeature")
    @patch.object(loan.close_loan, "net_balances")
    def test_deactivation_hook_zero_remaining_debt_no_custom_instructions(
        self,
        mock_net_balances: MagicMock,
        mock_due_amount_calculation_cleanup_feature: MagicMock,
        mock_overpayment_cleanup_feature: MagicMock,
        mock_get_residual_cleanup_postings: MagicMock,
        mock_get_parameter: MagicMock,
        mock_reject_closure: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_reject_closure.return_value = None

        mock_net_balances.return_value = []

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
            }
        )

        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = loan.deactivation_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertIsNone(result)

        mock_reject_closure.assert_called_once_with(
            balances=sentinel.balances_live,
            denomination=sentinel.denomination,
            debt_addresses=lending_addresses.ALL_OUTSTANDING,
        )
        mock_net_balances.assert_called_once_with(
            balances=sentinel.balances_live,
            denomination=sentinel.denomination,
            account_id=ACCOUNT_ID,
            residual_cleanup_features=[
                mock_overpayment_cleanup_feature,
                mock_due_amount_calculation_cleanup_feature,
                loan.lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=mock_get_residual_cleanup_postings
                ),
            ],
        )
