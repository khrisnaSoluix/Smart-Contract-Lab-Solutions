# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.bnpl.contracts.template import bnpl
from library.bnpl.test.unit.test_bnpl_common import BNPLTest

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
    DeactivationHookArguments,
    DeactivationHookResult,
    PostingInstructionsDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelRejection,
)


class DeactivationTest(BNPLTest):
    @patch.object(bnpl.utils, "get_parameter")
    @patch.object(bnpl.close_loan, "reject_closure_when_outstanding_debt")
    def test_cannot_deactivate_an_account_with_outstanding_debt(
        self, mock_reject_closure_when_outstanding_debt: MagicMock, mock_get_parameter: MagicMock
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                bnpl.common_parameters.PARAM_DENOMINATION: self.default_denomination,
            }
        )
        mock_rejection = SentinelRejection("dummy_rejection")
        mock_reject_closure_when_outstanding_debt.return_value = mock_rejection

        # run function
        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        deactivate_account_result = bnpl.deactivation_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # validate results
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name=bnpl.common_parameters.PARAM_DENOMINATION, at_datetime=None
        )
        mock_reject_closure_when_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
        )
        self.assertEqual(
            deactivate_account_result, DeactivationHookResult(rejection=mock_rejection)
        )

    @patch.object(bnpl.due_amount_calculation, "DueAmountCalculationResidualCleanupFeature")
    @patch.object(bnpl.close_loan.utils, "get_parameter")
    @patch.object(bnpl.close_loan, "reject_closure_when_outstanding_debt")
    @patch.object(bnpl.close_loan, "net_balances")
    def test_deactivate_account_returns_none_if_no_net_postings(
        self,
        mock_net_balances: MagicMock,
        mock_reject_closure_when_outstanding_debt: MagicMock,
        mock_get_parameter: MagicMock,
        mock_due_amount_calculation_cleanup_feature: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                bnpl.common_parameters.PARAM_DENOMINATION: self.default_denomination,
            }
        )
        mock_reject_closure_when_outstanding_debt.return_value = None
        mock_net_balances.return_value = []

        # run function
        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        deactivate_account_result = bnpl.deactivation_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # validate results
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name=bnpl.common_parameters.PARAM_DENOMINATION, at_datetime=None
        )
        mock_net_balances.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
            account_id=mock_vault.account_id,
            residual_cleanup_features=[mock_due_amount_calculation_cleanup_feature],
        )
        self.assertIsNone(deactivate_account_result)

    @patch.object(bnpl.due_amount_calculation, "DueAmountCalculationResidualCleanupFeature")
    @patch.object(bnpl.close_loan.utils, "get_parameter")
    @patch.object(bnpl.close_loan, "reject_closure_when_outstanding_debt")
    @patch.object(bnpl.close_loan, "net_balances")
    def test_deactivate_account_instructs_postings_to_net_balances(
        self,
        mock_net_balances: MagicMock,
        mock_reject_closure_when_outstanding_debt: MagicMock,
        mock_get_parameter: MagicMock,
        mock_due_amount_calculation_cleanup_feature: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                bnpl.common_parameters.PARAM_DENOMINATION: self.default_denomination,
            }
        )
        mock_reject_closure_when_outstanding_debt.return_value = None
        mock_postings: list[CustomInstruction] = [
            SentinelCustomInstruction("dummy_posting_instruction")  # type: ignore
        ]
        mock_net_balances.return_value = mock_postings

        # run function
        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        deactivate_account_result = bnpl.deactivation_hook(
            vault=mock_vault, hook_arguments=hook_args
        )

        # assertions
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name=bnpl.common_parameters.PARAM_DENOMINATION, at_datetime=None
        )
        mock_reject_closure_when_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
        )
        mock_net_balances.assert_called_once_with(
            balances=sentinel.balances_dummy_balances_observation,
            denomination=self.default_denomination,
            account_id=mock_vault.account_id,
            residual_cleanup_features=[mock_due_amount_calculation_cleanup_feature],
        )
        self.assertEqual(
            deactivate_account_result,
            DeactivationHookResult(
                posting_instructions_directives=[
                    PostingInstructionsDirective(
                        posting_instructions=mock_postings,  # type: ignore
                        value_datetime=DEFAULT_DATETIME,
                    )
                ]
            ),
        )
