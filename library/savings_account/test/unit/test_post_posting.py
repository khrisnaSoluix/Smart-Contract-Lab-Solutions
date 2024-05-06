# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.savings_account.test.unit.savings_account_common import (
    DEFAULT_DATE,
    SavingsAccountTest,
    savings_account,
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


@patch.object(savings_account.utils, "get_parameter")
@patch.object(savings_account.excess_fee, "apply")
@patch.object(savings_account.partial_fee, "charge_outstanding_fees")
class PostPostingHookTest(SavingsAccountTest):
    balances_observation_fetchers_mapping = {
        savings_account.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
    }

    def test_return_none_when_fees_are_not_applied_no_outstanding_partially_charged_fees(
        self,
        mock_charge_outstanding_fees: MagicMock,
        mock_excess_fee_apply: MagicMock,
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
                savings_account.fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID: sentinel.months_tx
            },
        )
        mock_excess_fee_apply.return_value = []
        mock_charge_outstanding_fees.return_value = []
        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )

        result = savings_account.post_posting_hook(vault=mock_vault, hook_arguments=hook_arguments)
        self.assertIsNone(result)
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name="denomination", at_datetime=DEFAULT_DATE
        )
        mock_excess_fee_apply.assert_called_once_with(
            vault=mock_vault,
            proposed_client_transactions=hook_arguments.client_transactions,
            effective_datetime=DEFAULT_DATE,
            denomination="GBP",
            account_type="SAVINGS_ACCOUNT",
        )

    @patch.object(savings_account.utils, "update_inflight_balances")
    def test_post_posting_returns_posting_directives_when_fees_are_applied_and_outstanding_fees(
        self,
        mock_update_inflight_balances: MagicMock,
        mock_charge_outstanding_fees: MagicMock,
        mock_excess_fee_apply: MagicMock,
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
                savings_account.fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID: sentinel.months_tx
            },
        )
        mock_excess_fee_apply.return_value = [
            SentinelCustomInstruction("excess_fee_custom_instruction")
        ]
        mock_charge_outstanding_fees.return_value = [
            SentinelCustomInstruction("charge_outstanding_fees")
        ]
        mock_update_inflight_balances.return_value = sentinel.inflight_balances

        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATE, posting_instructions=postings, client_transactions={}
        )

        result = savings_account.post_posting_hook(vault=mock_vault, hook_arguments=hook_arguments)
        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("excess_fee_custom_instruction"),
                        SentinelCustomInstruction("charge_outstanding_fees"),
                    ],
                    value_datetime=DEFAULT_DATE,
                ),
            ]
        )
        self.assertEqual(result, expected_result)
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name="denomination", at_datetime=DEFAULT_DATE
        )
        mock_excess_fee_apply.assert_called_once_with(
            vault=mock_vault,
            proposed_client_transactions=hook_arguments.client_transactions,
            effective_datetime=DEFAULT_DATE,
            denomination="GBP",
            account_type="SAVINGS_ACCOUNT",
        )
        mock_update_inflight_balances.assert_called_once_with(
            account_id=mock_vault.account_id,
            tside=savings_account.tside,
            current_balances=sentinel.balances_live,
            posting_instructions=mock_excess_fee_apply.return_value,
        )
        mock_charge_outstanding_fees.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATE,
            fee_collection=savings_account.FEE_HIERARCHY,
            balances=sentinel.inflight_balances,
            denomination="GBP",
        )
