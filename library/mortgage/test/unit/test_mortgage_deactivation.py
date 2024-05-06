# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.mortgage.contracts.template import mortgage
from library.mortgage.test.unit.test_mortgage_common import MortgageTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import DeactivationHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DeactivationHookResult,
    PostingInstructionsDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelRejection,
)


class DeactivationTest(MortgageTestBase):

    all_debt_addresses = [
        "PRINCIPAL_OVERDUE",
        "INTEREST_OVERDUE",
        "PENALTIES",
        "PRINCIPAL_DUE",
        "INTEREST_DUE",
        "PRINCIPAL",
        "ACCRUED_INTEREST_RECEIVABLE",
        "ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION",
    ]

    @patch.object(mortgage.close_loan, "reject_closure_when_outstanding_debt")
    @patch.object(mortgage.utils, "get_parameter")
    def test_deactivation_hook_with_outstanding_debt(
        self,
        mock_get_parameter: MagicMock,
        mock_reject_closure_when_outstanding_debt: MagicMock,
    ):
        # Set mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP"}
        )
        rejection = SentinelRejection("dummy_rejection")
        mock_reject_closure_when_outstanding_debt.return_value = rejection
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )

        # Expected result
        expected_result = DeactivationHookResult(rejection=rejection)

        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        hook_result = mortgage.deactivation_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertEqual(expected_result, hook_result)
        mock_reject_closure_when_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_live_balances,
            denomination="GBP",
            debt_addresses=self.all_debt_addresses,
        )

    @patch.object(mortgage.overpayment, "OverpaymentResidualCleanupFeature")
    @patch.object(mortgage.due_amount_calculation, "DueAmountCalculationResidualCleanupFeature")
    @patch.object(mortgage.close_loan, "net_balances")
    @patch.object(mortgage.close_loan, "reject_closure_when_outstanding_debt")
    @patch.object(mortgage.utils, "get_parameter")
    def test_deactivation_hook_no_outstanding_debt(
        self,
        mock_get_parameter: MagicMock,
        mock_reject_closure_when_outstanding_debt: MagicMock,
        mock_net_balances: MagicMock,
        mock_due_amount_calculation_cleanup_feature: MagicMock,
        mock_overpayment_cleanup_feature: MagicMock,
    ):

        # Expected values
        expected_cis = [SentinelCustomInstruction("end_of_mortgage")]
        # Set mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP"}
        )
        mock_reject_closure_when_outstanding_debt.return_value = False
        mock_net_balances.return_value = expected_cis
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )

        # Expected result
        expected_result = DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_cis,  # type: ignore
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        hook_result = mortgage.deactivation_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertEqual(expected_result, hook_result)
        mock_reject_closure_when_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_live_balances,
            denomination="GBP",
            debt_addresses=self.all_debt_addresses,
        )
        mock_net_balances.assert_called_once_with(
            balances=sentinel.balances_live_balances,
            denomination="GBP",
            account_id="default_account",
            residual_cleanup_features=[
                mock_overpayment_cleanup_feature,
                mortgage.overpayment_allowance.OverpaymentAllowanceResidualCleanupFeature,
                mock_due_amount_calculation_cleanup_feature,
                mortgage.lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=mortgage._get_residual_cleanup_postings
                ),
            ],
        )

    @patch.object(mortgage.overpayment, "OverpaymentResidualCleanupFeature")
    @patch.object(mortgage.due_amount_calculation, "DueAmountCalculationResidualCleanupFeature")
    @patch.object(mortgage.close_loan, "net_balances")
    @patch.object(mortgage.close_loan, "reject_closure_when_outstanding_debt")
    @patch.object(mortgage.utils, "get_parameter")
    def test_deactivation_hook_returns_none_if_no_cleanup_posting_instructions(
        self,
        mock_get_parameter: MagicMock,
        mock_reject_closure_when_outstanding_debt: MagicMock,
        mock_net_balances: MagicMock,
        mock_due_amount_calculation_cleanup_feature: MagicMock,
        mock_overpayment_cleanup_feature: MagicMock,
    ):
        # Set mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP"}
        )
        mock_reject_closure_when_outstanding_debt.return_value = False
        mock_net_balances.return_value = []
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )

        # Expected result
        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        hook_result = mortgage.deactivation_hook(vault=mock_vault, hook_arguments=hook_args)

        self.assertIsNone(hook_result)
        mock_reject_closure_when_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_live_balances,
            denomination="GBP",
            debt_addresses=self.all_debt_addresses,
        )
        mock_net_balances.assert_called_once_with(
            balances=sentinel.balances_live_balances,
            denomination="GBP",
            account_id="default_account",
            residual_cleanup_features=[
                mock_overpayment_cleanup_feature,
                mortgage.overpayment_allowance.OverpaymentAllowanceResidualCleanupFeature,
                mock_due_amount_calculation_cleanup_feature,
                mortgage.lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=mortgage._get_residual_cleanup_postings
                ),
            ],
        )
