# standard libs
from unittest.mock import MagicMock, call, patch, sentinel

# library
from library.current_account.test.unit.current_account_common import (
    DEFAULT_DATE,
    CurrentAccountTest,
    current_account,
)

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import PostPostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PostingInstructionsDirective,
    PostPostingHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)


@patch.object(current_account.utils, "get_parameter")
@patch.object(current_account.partial_fee, "charge_outstanding_fees")
@patch.object(current_account.excess_fee, "apply")
@patch.object(current_account.roundup_autosave, "apply")
class PostPostingHookTest(CurrentAccountTest):
    balances_observation_fetchers_mapping = {
        current_account.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
    }

    def test_return_none_when_autosave_and_txn_fees_are_not_applied_and_no_outstanding_fees(
        self,
        mock_autosave_apply: MagicMock,
        mock_excess_fee_apply: MagicMock,
        mock_charge_outstanding_partial_fee: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": "GBP",
            }
        )
        postings = [SentinelCustomInstruction("dummy_posting")]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.balances_observation_fetchers_mapping,
            client_transactions_mapping={
                current_account.fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID: sentinel.months_tx
            },
        )
        mock_autosave_apply.return_value = []
        mock_excess_fee_apply.return_value = []
        mock_charge_outstanding_partial_fee.return_value = []
        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )

        result = current_account.post_posting_hook(vault=mock_vault, hook_arguments=hook_arguments)
        self.assertIsNone(result)
        mock_autosave_apply.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination="GBP",
            balances=sentinel.balances_live,
        )
        mock_charge_outstanding_partial_fee.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATE,
            fee_collection=current_account.FEE_HIERARCHY,
            balances=sentinel.balances_live,
            denomination="GBP",
            available_balance_feature=current_account.overdraft_limit.OverdraftLimitAvailableBalance,  # noqa: E501
        )
        mock_excess_fee_apply.assert_called_once_with(
            vault=mock_vault,
            proposed_client_transactions=hook_arguments.client_transactions,
            effective_datetime=DEFAULT_DATE,
            denomination="GBP",
            account_type="CURRENT_ACCOUNT",
        )

    @patch.object(current_account.utils, "update_inflight_balances")
    def test_return_autosave_instructions_when_autosave_applied_no_outstanding_or_applied_fees(
        self,
        mock_update_inflight_balances: MagicMock,
        mock_autosave_apply: MagicMock,
        mock_excess_fee_apply: MagicMock,
        mock_charge_outstanding_partial_fee: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": "GBP",
            }
        )
        postings = [SentinelCustomInstruction("dummy_posting")]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.balances_observation_fetchers_mapping,
            client_transactions_mapping={
                current_account.fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID: sentinel.months_tx
            },
        )
        autosave_custom_instruction = SentinelCustomInstruction("autosave_custom_instruction")
        mock_autosave_apply.return_value = [autosave_custom_instruction]
        mock_excess_fee_apply.return_value = []
        mock_charge_outstanding_partial_fee.return_value = []
        mock_update_inflight_balances.return_value = sentinel.autosave_inflight_balances

        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )

        result = current_account.post_posting_hook(vault=mock_vault, hook_arguments=hook_arguments)

        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("autosave_custom_instruction")],
                    value_datetime=DEFAULT_DATE,
                ),
            ]
        )
        self.assertEqual(result, expected_result)
        mock_autosave_apply.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination="GBP",
            balances=sentinel.balances_live,
        )
        mock_update_inflight_balances.assert_called_once_with(
            account_id=mock_vault.account_id,
            tside=current_account.tside,
            current_balances=sentinel.balances_live,
            posting_instructions=[autosave_custom_instruction],
        )
        mock_charge_outstanding_partial_fee.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATE,
            fee_collection=current_account.FEE_HIERARCHY,
            balances=sentinel.autosave_inflight_balances,
            denomination="GBP",
            available_balance_feature=current_account.overdraft_limit.OverdraftLimitAvailableBalance,  # noqa: E501
        )
        mock_excess_fee_apply.assert_called_once_with(
            vault=mock_vault,
            proposed_client_transactions=hook_arguments.client_transactions,
            effective_datetime=DEFAULT_DATE,
            denomination="GBP",
            account_type="CURRENT_ACCOUNT",
        )

    @patch.object(current_account.utils, "update_inflight_balances")
    def test_return_excess_fee_instructions_autosave_not_applied_fees_applied_no_outstanding_fees(
        self,
        mock_update_inflight_balances: MagicMock,
        mock_autosave_apply: MagicMock,
        mock_excess_fee_apply: MagicMock,
        mock_charge_outstanding_partial_fee: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": "GBP",
            }
        )
        postings = [SentinelCustomInstruction("dummy_posting")]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.balances_observation_fetchers_mapping,
            client_transactions_mapping={
                current_account.fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID: sentinel.months_tx
            },
        )
        mock_autosave_apply.return_value = []
        mock_charge_outstanding_partial_fee.return_value = []
        mock_excess_fee_apply.return_value = [
            SentinelCustomInstruction("excess_fee_custom_instructions")
        ]
        mock_update_inflight_balances.return_value = sentinel.excess_fee_inflight_balances
        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )

        result = current_account.post_posting_hook(vault=mock_vault, hook_arguments=hook_arguments)

        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("excess_fee_custom_instructions")
                    ],
                    value_datetime=DEFAULT_DATE,
                ),
            ]
        )
        self.assertEqual(result, expected_result)
        mock_autosave_apply.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination="GBP",
            balances=sentinel.balances_live,
        )
        mock_charge_outstanding_partial_fee.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATE,
            fee_collection=current_account.FEE_HIERARCHY,
            balances=sentinel.excess_fee_inflight_balances,
            denomination="GBP",
            available_balance_feature=current_account.overdraft_limit.OverdraftLimitAvailableBalance,  # noqa: E501
        )
        mock_excess_fee_apply.assert_called_once_with(
            vault=mock_vault,
            proposed_client_transactions=hook_arguments.client_transactions,
            effective_datetime=DEFAULT_DATE,
            denomination="GBP",
            account_type="CURRENT_ACCOUNT",
        )

    @patch.object(current_account.utils, "update_inflight_balances")
    def test_return_posting_directives_autosave_and_fee_applied_and_partial_fees_collected(
        self,
        mock_update_inflight_balances: MagicMock,
        mock_autosave_apply: MagicMock,
        mock_excess_fee_apply: MagicMock,
        mock_charge_outstanding_partial_fee: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": "GBP",
            }
        )
        postings = [SentinelCustomInstruction("dummy_posting")]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.balances_observation_fetchers_mapping,
            client_transactions_mapping={
                current_account.fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID: sentinel.months_tx
            },
        )
        autosave_custom_instruction = SentinelCustomInstruction("autosave_custom_instruction")
        mock_autosave_apply.return_value = [autosave_custom_instruction]
        mock_charge_outstanding_partial_fee.return_value = [
            SentinelCustomInstruction("outstanding_fee_custom_instruction")
        ]
        excess_fee_custom_instruction = SentinelCustomInstruction("excess_fee_custom_instruction")
        mock_excess_fee_apply.return_value = [excess_fee_custom_instruction]
        mock_update_inflight_balances.side_effect = [
            sentinel.autosave_inflight_balances,
            sentinel.excess_fee_inflight_balances,
        ]

        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )

        result = current_account.post_posting_hook(vault=mock_vault, hook_arguments=hook_arguments)
        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[autosave_custom_instruction],
                    value_datetime=DEFAULT_DATE,
                ),
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("excess_fee_custom_instruction"),
                        SentinelCustomInstruction("outstanding_fee_custom_instruction"),
                    ],
                    value_datetime=DEFAULT_DATE,
                ),
            ]
        )
        self.assertEqual(result, expected_result)
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name="denomination", at_datetime=DEFAULT_DATE
        )
        mock_autosave_apply.assert_called_once_with(
            vault=mock_vault,
            postings=postings,
            denomination="GBP",
            balances=sentinel.balances_live,
        )
        mock_update_inflight_balances.assert_has_calls(
            calls=[
                call(
                    account_id=mock_vault.account_id,
                    tside=current_account.tside,
                    current_balances=sentinel.balances_live,
                    posting_instructions=[autosave_custom_instruction],
                ),
                call(
                    account_id=mock_vault.account_id,
                    tside=current_account.tside,
                    current_balances=sentinel.autosave_inflight_balances,
                    posting_instructions=[excess_fee_custom_instruction],
                ),
            ]
        )
        mock_charge_outstanding_partial_fee.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATE,
            fee_collection=current_account.FEE_HIERARCHY,
            balances=sentinel.excess_fee_inflight_balances,
            denomination="GBP",
            available_balance_feature=current_account.overdraft_limit.OverdraftLimitAvailableBalance,  # noqa: E501
        )
        mock_excess_fee_apply.assert_called_once_with(
            vault=mock_vault,
            proposed_client_transactions=hook_arguments.client_transactions,
            effective_datetime=DEFAULT_DATE,
            denomination="GBP",
            account_type="CURRENT_ACCOUNT",
        )
