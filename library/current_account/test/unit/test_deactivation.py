# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.current_account.test.unit.current_account_common import (
    DEFAULT_DATE,
    CurrentAccountTest,
    current_account,
)

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DeactivationHookArguments,
    DeactivationHookResult,
    PostingInstructionsDirective,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)


class DeactivationHookTest(CurrentAccountTest):
    balances_observation_mapping = {
        current_account.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
    }

    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    def test_deactivation_returns_rejection_flag_active(
        self, mock_is_flag_in_list_applied: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_is_flag_in_list_applied.return_value = True
        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATE)
        mock_get_parameter.side_effect = mock_utils_get_parameter({"denomination": "GBP"})

        hook_result = current_account.deactivation_hook(MagicMock, hook_arguments)

        expected_result = DeactivationHookResult(
            rejection=Rejection(
                message="Cannot close a dormant account.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        self.assertEqual(hook_result, expected_result)

    @patch.object(current_account.partial_fee, "has_outstanding_fees")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    def test_deactivation_returns_rejection_if_outstanding_fees(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_has_outstanding_fees: MagicMock,
    ):
        mock_is_flag_in_list_applied.return_value = False
        mock_has_outstanding_fees.return_value = True
        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATE)
        mock_get_parameter.side_effect = mock_utils_get_parameter({"denomination": "GBP"})

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.balances_observation_mapping
        )
        hook_result = current_account.deactivation_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        expected_result = DeactivationHookResult(
            rejection=Rejection(
                message="Cannot close account with outstanding fees.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        self.assertEqual(hook_result, expected_result)
        mock_has_outstanding_fees.assert_called_once_with(
            vault=mock_vault,
            fee_collection=current_account.FEE_HIERARCHY,
            balances=sentinel.balances_live,
            denomination="GBP",
        )

    @patch.object(current_account.partial_fee, "has_outstanding_fees")
    @patch.object(current_account.unarranged_overdraft_fee, "apply_fee")
    @patch.object(current_account, "_clean_up_accrued_and_overdraft_interest")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    def test_deactivation_returns_deactivation_result_flag_not_active(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_apply_remaining_interest: MagicMock,
        mock_apply_unarranged_overdraft_fee: MagicMock,
        mock_has_outstanding_fees: MagicMock,
    ):
        mock_is_flag_in_list_applied.return_value = False
        mock_has_outstanding_fees.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter({"denomination": "GBP"})
        mock_apply_remaining_interest.return_value = [SentinelCustomInstruction("postings")]
        mock_apply_unarranged_overdraft_fee.return_value = []
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.balances_observation_mapping
        )

        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATE)
        hook_result = current_account.deactivation_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        self.assertEqual(
            hook_result,
            DeactivationHookResult(
                posting_instructions_directives=[
                    PostingInstructionsDirective(
                        posting_instructions=[SentinelCustomInstruction("postings")],
                        value_datetime=DEFAULT_DATE,
                        client_batch_id="MOCK_HOOK_CLOSE_ACCOUNT",
                    )
                ]
            ),
        )
        mock_apply_remaining_interest.assert_called_once_with(
            vault=mock_vault, balances=sentinel.balances_live, denomination="GBP"
        )

    @patch.object(current_account.partial_fee, "has_outstanding_fees")
    @patch.object(current_account.unarranged_overdraft_fee, "apply_fee")
    @patch.object(current_account, "_clean_up_accrued_and_overdraft_interest")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    def test_deactivation_returns_none(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_apply_remaining_interest: MagicMock,
        mock_apply_unarranged_overdraft_fee: MagicMock,
        mock_has_outstanding_fees: MagicMock,
    ):
        mock_is_flag_in_list_applied.return_value = False
        mock_has_outstanding_fees.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter({"denomination": "GBP"})
        mock_apply_unarranged_overdraft_fee.return_value = []
        mock_apply_remaining_interest.return_value = []

        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATE)
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.balances_observation_mapping
        )
        hook_result = current_account.deactivation_hook(mock_vault, hook_arguments)

        self.assertIsNone(hook_result, None)
        mock_apply_remaining_interest.assert_called_once_with(
            vault=mock_vault, balances=sentinel.balances_live, denomination="GBP"
        )

    @patch.object(current_account.overdraft_interest, "get_interest_reversal_postings")
    @patch.object(current_account.tiered_interest_accrual, "get_interest_reversal_postings")
    def test_deactivation_reverse_interest_method(
        self,
        mock_get_interest_reversal_postings: MagicMock,
        mock_get_overdraft_interest_reversal_postings: MagicMock,
    ):
        mock_get_interest_reversal_postings.return_value = [
            SentinelCustomInstruction("interest_reversal_postings")
        ]
        mock_get_overdraft_interest_reversal_postings.return_value = [
            SentinelCustomInstruction("overdraft_interest_reversal_postings")
        ]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.balances_observation_mapping
        )
        method_result = current_account._clean_up_accrued_and_overdraft_interest(
            vault=mock_vault, balances=sentinel.balances, denomination=sentinel.denomination
        )

        self.assertListEqual(
            method_result,
            [
                SentinelCustomInstruction("interest_reversal_postings"),
                SentinelCustomInstruction("overdraft_interest_reversal_postings"),
            ],
        )
        mock_get_interest_reversal_postings.assert_called_once_with(
            vault=mock_vault,
            event_name="CLOSE_ACCOUNT",
            account_type="CURRENT_ACCOUNT",
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        mock_get_overdraft_interest_reversal_postings.assert_called_once_with(
            vault=mock_vault,
            event_name="CLOSE_ACCOUNT",
            account_type="CURRENT_ACCOUNT",
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

    @patch.object(current_account.partial_fee, "has_outstanding_fees")
    @patch.object(current_account.unarranged_overdraft_fee, "apply_fee")
    @patch.object(current_account, "_clean_up_accrued_and_overdraft_interest")
    @patch.object(current_account.utils, "get_parameter")
    @patch.object(current_account.utils, "is_flag_in_list_applied")
    def test_deactivation_returns_unarranged_overdraft_fee_instructions(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_apply_remaining_interest: MagicMock,
        mock_apply_unarranged_overdraft_fee: MagicMock,
        mock_has_outstanding_fees: MagicMock,
    ):
        mock_is_flag_in_list_applied.return_value = False
        mock_has_outstanding_fees.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter({"denomination": "GBP"})
        mock_apply_remaining_interest.return_value = []
        mock_apply_unarranged_overdraft_fee.return_value = [SentinelCustomInstruction("postings")]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.balances_observation_mapping
        )

        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATE)
        hook_result = current_account.deactivation_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        self.assertEqual(
            hook_result,
            DeactivationHookResult(
                posting_instructions_directives=[
                    PostingInstructionsDirective(
                        posting_instructions=[SentinelCustomInstruction("postings")],
                        value_datetime=DEFAULT_DATE,
                        client_batch_id="MOCK_HOOK_CLOSE_ACCOUNT",
                    )
                ]
            ),
        )
        mock_apply_remaining_interest.assert_called_once_with(
            vault=mock_vault, balances=sentinel.balances_live, denomination="GBP"
        )
