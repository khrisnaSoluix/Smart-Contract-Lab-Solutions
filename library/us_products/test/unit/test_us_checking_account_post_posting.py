# standard libs
from unittest.mock import patch, sentinel

# library
from library.us_products.contracts.template import us_checking_account
from library.us_products.test.unit.test_us_checking_account_common import CheckingAccountTest

# features
import library.features.common.fetchers as fetchers

# contracts api
from contracts_api import PostPostingHookArguments, Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DATETIME,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PostingInstructionsDirective,
    PostPostingHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)


class PostPostingHookTest(CheckingAccountTest):
    def setUp(self) -> None:

        self.mock_vault = self.create_mock(
            account_id=ACCOUNT_ID,
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            },
        )
        self.hook_args = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[sentinel.posting_instruction],
            client_transactions={sentinel.cti: sentinel.client_transactions},
        )

        patch_denomination_parameter = patch.object(
            us_checking_account.common_parameters, "get_denomination_parameter"
        )
        self.mock_denomination_parameter = patch_denomination_parameter.start()
        self.mock_denomination_parameter.return_value = sentinel.denomination

        patch_rebate_fees = patch.object(us_checking_account.unlimited_fee_rebate, "rebate_fees")
        self.mock_rebate_fees = patch_rebate_fees.start()
        self.mock_rebate_fees.return_value = [SentinelCustomInstruction("rebate_fees")]

        patch_update_inflight_balances = patch.object(
            us_checking_account.utils, "update_inflight_balances"
        )
        self.mock_update_inflight_balances = patch_update_inflight_balances.start()
        self.mock_update_inflight_balances.return_value = sentinel.inflight_balances

        patch_charge_outstanding_fees = patch.object(
            us_checking_account.partial_fee, "charge_outstanding_fees"
        )
        self.mock_charge_outstanding_fees = patch_charge_outstanding_fees.start()
        self.mock_charge_outstanding_fees.return_value = [
            SentinelCustomInstruction("charge_outstanding_fees")
        ]

        patch_generate_tracking_instructions = patch.object(
            us_checking_account.direct_deposit_tracker, "generate_tracking_instructions"
        )
        self.mock_generate_tracking_instructions = patch_generate_tracking_instructions.start()
        self.mock_generate_tracking_instructions.return_value = []

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_fees_rebated_and_partial_fees_collected_returns_posting_directive(self):
        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("rebate_fees"),
                        SentinelCustomInstruction("charge_outstanding_fees"),
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )
        result = us_checking_account.post_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_args
        )
        self.assertEqual(result, expected_result)
        self.mock_rebate_fees.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[sentinel.posting_instruction],
            denomination=sentinel.denomination,
        )
        self.mock_update_inflight_balances.assert_called_once_with(
            account_id=ACCOUNT_ID,
            tside=Tside.LIABILITY,
            current_balances=sentinel.balances_live_balances,
            posting_instructions=[SentinelCustomInstruction("rebate_fees")],
        )
        self.mock_charge_outstanding_fees.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            fee_collection=us_checking_account.FEE_HIERARCHY,
            balances=sentinel.inflight_balances,
            denomination=sentinel.denomination,
            available_balance_feature=us_checking_account.overdraft_coverage.OverdraftCoverageAvailableBalance,  # noqa: E501
        )

    def test_partial_fees_collected_no_rebated_fees_returns_posting_directive(self):
        self.mock_rebate_fees.return_value = []
        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("charge_outstanding_fees"),
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )
        result = us_checking_account.post_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_args
        )
        self.assertEqual(result, expected_result)
        self.mock_rebate_fees.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[sentinel.posting_instruction],
            denomination=sentinel.denomination,
        )
        self.mock_update_inflight_balances.assert_not_called()
        self.mock_charge_outstanding_fees.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            fee_collection=us_checking_account.FEE_HIERARCHY,
            balances=sentinel.balances_live_balances,
            denomination=sentinel.denomination,
            available_balance_feature=us_checking_account.overdraft_coverage.OverdraftCoverageAvailableBalance,  # noqa: E501
        )

    def test_no_partial_fees_collected_no_rebated_fees_returns_none(self):
        self.mock_rebate_fees.return_value = []
        self.mock_charge_outstanding_fees.return_value = []

        result = us_checking_account.post_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_args
        )
        self.assertIsNone(result)
        self.mock_rebate_fees.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[sentinel.posting_instruction],
            denomination=sentinel.denomination,
        )
        self.mock_update_inflight_balances.assert_not_called()
        self.mock_charge_outstanding_fees.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            fee_collection=us_checking_account.FEE_HIERARCHY,
            balances=sentinel.balances_live_balances,
            denomination=sentinel.denomination,
            available_balance_feature=us_checking_account.overdraft_coverage.OverdraftCoverageAvailableBalance,  # noqa: E501
        )
        self.mock_generate_tracking_instructions.assert_called_once_with(
            vault=self.mock_vault,
            posting_instructions=self.hook_args.posting_instructions,
        )

    def test_direct_deposit_tracking_address_updated(self):
        # construct mocks
        self.mock_charge_outstanding_fees.return_value = []
        self.mock_rebate_fees.return_value = []
        self.mock_generate_tracking_instructions.return_value = [
            SentinelCustomInstruction("update_tracking_instructions")
        ]

        # expected result
        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("update_tracking_instructions")
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        # run function
        result = us_checking_account.post_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_args
        )

        # assertions
        self.assertEqual(expected_result, result)
        self.mock_charge_outstanding_fees.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            fee_collection=us_checking_account.FEE_HIERARCHY,
            balances=sentinel.balances_live_balances,
            denomination=sentinel.denomination,
            available_balance_feature=us_checking_account.overdraft_coverage.OverdraftCoverageAvailableBalance,  # noqa: E501
        )
        self.mock_generate_tracking_instructions.assert_called_once_with(
            vault=self.mock_vault,
            posting_instructions=self.hook_args.posting_instructions,
        )
