# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import patch, sentinel

# library
from library.credit_card.contracts.template import credit_card
from library.credit_card.test.unit.test_credit_card_common import CreditCardTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import PostPostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    BalanceDefaultDict,
    PostingInstructionsDirective,
    PostPostingHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalance,
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)


class CreditCardPostPostingTest(CreditCardTestBase):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                credit_card.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "balances_observation"
                )
            },
        )

        # get parameter
        patch_get_parameter = patch.object(credit_card.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "credit_limit": sentinel.credit_limit,
                "denomination": sentinel.denomination,
            }
        )

        # deep copy balances
        patch_deep_copy_balances = patch.object(credit_card, "_deep_copy_balances")
        self.mock_deep_copy_balances = patch_deep_copy_balances.start()
        # TODO: What this return_value should be?
        self.deep_copy_balances_balance_dict = BalanceDefaultDict(
            mapping={
                credit_card.LIVE_BALANCES_BOF_ID: SentinelBalance(""),  # type: ignore
            }
        )
        self.mock_deep_copy_balances.return_value = self.deep_copy_balances_balance_dict

        # rebalance postings
        patch_rebalance_postings = patch.object(credit_card, "_rebalance_postings")
        self.mock_rebalance_postings = patch_rebalance_postings.start()
        self.mock_rebalance_postings.return_value = []

        # charge txn type fees
        patch_charge_txn_type_fees = patch.object(credit_card, "_charge_txn_type_fees")
        self.mock_charge_txn_type_fees = patch_charge_txn_type_fees.start()
        self.mock_charge_txn_type_fees.return_value = []

        # adjust aggregate balances
        patch_adjust_aggregate_balances = patch.object(credit_card, "_adjust_aggregate_balances")
        self.mock_adjust_aggregate_balances = patch_adjust_aggregate_balances.start()
        self.mock_adjust_aggregate_balances.return_value = []

        # Default Hook Arguments
        self.hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
            client_transactions=sentinel.client_transactions,
        )

        # Tear Down of Patches
        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_post_posting_no_new_posting_instructions(self):
        result = credit_card.post_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertIsNone(result)

    def test_post_posting_only_rebalance_posting_instructions(self):
        expected_cis = [SentinelCustomInstruction("rebalance_instruction")]
        self.mock_rebalance_postings.return_value = expected_cis

        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_cis,  # type: ignore
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )
        result = credit_card.post_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )

        # Assert:
        self.assertEquals(result, expected_result)
        self.mock_rebalance_postings.assert_called_once_with(
            self.mock_vault,
            sentinel.denomination,
            sentinel.posting_instructions,
            sentinel.client_transactions,
            self.deep_copy_balances_balance_dict,
            DEFAULT_DATETIME,
        )

        self.mock_charge_txn_type_fees.assert_called_once_with(
            self.mock_vault,
            sentinel.posting_instructions,
            SentinelBalancesObservation("balances_observation").balances,
            self.deep_copy_balances_balance_dict,
            sentinel.denomination,
            DEFAULT_DATETIME,
        )

        self.mock_adjust_aggregate_balances.assert_called_once_with(
            self.mock_vault,
            sentinel.denomination,
            self.deep_copy_balances_balance_dict,
            effective_datetime=DEFAULT_DATETIME,
            credit_limit=sentinel.credit_limit,
        )

    def test_post_posting_only_charge_txn_type_fees_posting_instructions(self):
        expected_cis = [SentinelCustomInstruction("charge_txn_type_fees_instruction")]
        self.mock_charge_txn_type_fees.return_value = expected_cis

        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_cis,  # type: ignore
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )
        result = credit_card.post_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )

        # Assert:
        self.assertEquals(result, expected_result)
        self.mock_rebalance_postings.assert_called_once_with(
            self.mock_vault,
            sentinel.denomination,
            sentinel.posting_instructions,
            sentinel.client_transactions,
            self.deep_copy_balances_balance_dict,
            DEFAULT_DATETIME,
        )
        self.mock_charge_txn_type_fees.assert_called_once_with(
            self.mock_vault,
            sentinel.posting_instructions,
            SentinelBalancesObservation("balances_observation").balances,
            self.deep_copy_balances_balance_dict,
            sentinel.denomination,
            DEFAULT_DATETIME,
        )

        self.mock_adjust_aggregate_balances.assert_called_once_with(
            self.mock_vault,
            sentinel.denomination,
            self.deep_copy_balances_balance_dict,
            effective_datetime=DEFAULT_DATETIME,
            credit_limit=sentinel.credit_limit,
        )

    def test_post_posting_only_adjust_aggregate_balances_posting_instructions(self):
        expected_cis = [SentinelCustomInstruction("adjust_aggregate_balances_instruction")]
        self.mock_adjust_aggregate_balances.return_value = expected_cis

        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_cis,  # type: ignore
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )
        result = credit_card.post_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )

        # Assert:
        self.assertEquals(result, expected_result)
        self.mock_rebalance_postings.assert_called_once_with(
            self.mock_vault,
            sentinel.denomination,
            sentinel.posting_instructions,
            sentinel.client_transactions,
            self.deep_copy_balances_balance_dict,
            DEFAULT_DATETIME,
        )
        self.mock_charge_txn_type_fees.assert_called_once_with(
            self.mock_vault,
            sentinel.posting_instructions,
            SentinelBalancesObservation("balances_observation").balances,
            self.deep_copy_balances_balance_dict,
            sentinel.denomination,
            DEFAULT_DATETIME,
        )

        self.mock_adjust_aggregate_balances.assert_called_once_with(
            self.mock_vault,
            sentinel.denomination,
            self.deep_copy_balances_balance_dict,
            effective_datetime=DEFAULT_DATETIME,
            credit_limit=sentinel.credit_limit,
        )

    def test_post_posting_all_new_posting_instructions(self):
        self.mock_rebalance_postings.return_value = [
            SentinelCustomInstruction("rebalance_instruction")
        ]
        self.mock_charge_txn_type_fees.return_value = [
            SentinelCustomInstruction("charge_txn_type_fees")
        ]
        self.mock_adjust_aggregate_balances.return_value = [
            SentinelCustomInstruction("adjust_aggregate_balances")
        ]
        expected_cis = (
            self.mock_rebalance_postings.return_value
            + self.mock_charge_txn_type_fees.return_value
            + self.mock_adjust_aggregate_balances.return_value
        )

        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_cis,  # type: ignore
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )
        result = credit_card.post_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )

        # Assert:
        self.assertEquals(result, expected_result)
        self.mock_rebalance_postings.assert_called_once_with(
            self.mock_vault,
            sentinel.denomination,
            sentinel.posting_instructions,
            sentinel.client_transactions,
            self.deep_copy_balances_balance_dict,
            DEFAULT_DATETIME,
        )
        self.mock_charge_txn_type_fees.assert_called_once_with(
            self.mock_vault,
            sentinel.posting_instructions,
            SentinelBalancesObservation("balances_observation").balances,
            self.deep_copy_balances_balance_dict,
            sentinel.denomination,
            DEFAULT_DATETIME,
        )

        self.mock_adjust_aggregate_balances.assert_called_once_with(
            self.mock_vault,
            sentinel.denomination,
            self.deep_copy_balances_balance_dict,
            effective_datetime=DEFAULT_DATETIME,
            credit_limit=sentinel.credit_limit,
        )
