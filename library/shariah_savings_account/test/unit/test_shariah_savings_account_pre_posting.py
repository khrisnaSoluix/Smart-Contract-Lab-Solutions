# standard libs
from unittest.mock import patch, sentinel

# library
import library.shariah_savings_account.contracts.template.shariah_savings_account as shariah_savings_account  # noqa: E501
from library.shariah_savings_account.test.unit.test_shariah_savings_account_common import (  # noqa: E501
    ShariahSavingsAccountTestBase,
)

# features
import library.features.common.fetchers as fetchers
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import PrePostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PrePostingHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelRejection,
)

TEST_DENOMINATION = "MYR"


class PrePostingHookTest(ShariahSavingsAccountTestBase):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("balances_observation")
            },
        )

        # default expected rejection
        self.expected_rejection = SentinelRejection("rejection")

        # default hook arguments
        self.hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
            client_transactions=sentinel.client_transactions,
        )

        # default expected result
        self.expected_result = PrePostingHookResult(rejection=self.expected_rejection)

        # get parameter
        patch_get_parameter = patch.object(shariah_savings_account.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": TEST_DENOMINATION}
        )

        # is force override
        patch_is_force_override = patch.object(shariah_savings_account.utils, "is_force_override")
        self.mock_is_force_override = patch_is_force_override.start()
        self.mock_is_force_override.return_value = None

        # validate denomination
        patch_validate_denomination = patch.object(
            shariah_savings_account.utils, "validate_denomination"
        )
        self.mock_validate_denomination = patch_validate_denomination.start()
        self.mock_validate_denomination.return_value = None

        # maximum balance limit
        patch_maximum_balance_limit_validate = patch.object(
            shariah_savings_account.maximum_balance_limit, "validate"
        )
        self.mock_maximum_balance_limit_validate = patch_maximum_balance_limit_validate.start()
        self.mock_maximum_balance_limit_validate.return_value = None

        # minimum initial deposit
        patch_minimum_initial_deposit_validate = patch.object(
            shariah_savings_account.minimum_initial_deposit, "validate"
        )
        self.mock_minimum_initial_deposit_validate = patch_minimum_initial_deposit_validate.start()
        self.mock_minimum_initial_deposit_validate.return_value = None

        # minimum single deposit
        patch_minimum_single_deposit_validate = patch.object(
            shariah_savings_account.minimum_single_deposit, "validate"
        )
        self.mock_minimum_single_deposit_validate = patch_minimum_single_deposit_validate.start()
        self.mock_minimum_single_deposit_validate.return_value = None

        # maximum single deposit
        patch_maximum_single_deposit_validate = patch.object(
            shariah_savings_account.maximum_single_deposit, "validate"
        )
        self.mock_maximum_single_deposit_validate = patch_maximum_single_deposit_validate.start()
        self.mock_maximum_single_deposit_validate.return_value = None

        # maximum single withdrawal
        patch_maximum_single_withdrawal_validate = patch.object(
            shariah_savings_account.maximum_single_withdrawal, "validate"
        )
        self.mock_maximum_single_withdrawal_validate = (
            patch_maximum_single_withdrawal_validate.start()
        )
        self.mock_maximum_single_withdrawal_validate.return_value = None

        # minimum balance by tier
        patch_minimum_balance_by_tier_validate = patch.object(
            shariah_savings_account.minimum_balance_by_tier, "validate"
        )
        self.mock_minimum_balance_by_tier_validate = patch_minimum_balance_by_tier_validate.start()
        self.mock_minimum_balance_by_tier_validate.return_value = None

        # maximum withdrawal by payment type
        patch_maximum_withdrawal_by_payment_type_validate = patch.object(
            shariah_savings_account.maximum_withdrawal_by_payment_type, "validate"
        )
        self.mock_maximum_withdrawal_by_payment_type_validate = (
            patch_maximum_withdrawal_by_payment_type_validate.start()
        )
        self.mock_maximum_withdrawal_by_payment_type_validate.return_value = None

        # maximum daily deposit
        patch_maximum_daily_deposit_validate = patch.object(
            shariah_savings_account.maximum_daily_deposit, "validate"
        )
        self.mock_maximum_daily_deposit_validate = patch_maximum_daily_deposit_validate.start()
        self.mock_maximum_daily_deposit_validate.return_value = None

        # maximum daily withdrawal
        patch_maximum_daily_withdrawal_validate = patch.object(
            shariah_savings_account.maximum_daily_withdrawal, "validate"
        )
        self.mock_maximum_daily_withdrawal_validate = (
            patch_maximum_daily_withdrawal_validate.start()
        )
        self.mock_maximum_daily_withdrawal_validate.return_value = None

        # maximum daily withdrawal by payment type
        patch_maximum_daily_withdrawal_by_transaction_type_validate = patch.object(
            shariah_savings_account.maximum_daily_withdrawal_by_transaction_type, "validate"
        )
        self.mock_maximum_daily_withdrawal_by_transaction_type_validate = (
            patch_maximum_daily_withdrawal_by_transaction_type_validate.start()
        )
        self.mock_maximum_daily_withdrawal_by_transaction_type_validate.return_value = None

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_pre_posting_hook_no_rejections(self):
        result = shariah_savings_account.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertIsNone(result)

    def test_pre_posting_hook_force_override_no_rejections(self):
        # Mock return rejection to see force override ignores it
        self.mock_validate_denomination.return_value = self.expected_rejection

        # Mock return force override true
        self.mock_is_force_override.return_value = True

        result = shariah_savings_account.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertIsNone(result)

        self.mock_is_force_override.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions,
        )

    def test_pre_posting_validate_denomination_rejection(self):
        # Mock return rejection
        self.mock_validate_denomination.return_value = self.expected_rejection

        result = shariah_savings_account.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_validate_denomination.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions,
            accepted_denominations=[TEST_DENOMINATION],
        )

    def test_pre_posting_maximum_single_deposit_rejection(self):
        # Mock return rejection
        self.mock_maximum_single_deposit_validate.return_value = self.expected_rejection

        result = shariah_savings_account.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_maximum_single_deposit_validate.assert_called_once_with(
            vault=self.mock_vault,
            postings=sentinel.posting_instructions,
            denomination=TEST_DENOMINATION,
        )

    def test_pre_posting_minimum_single_deposit_rejection(self):
        # Mock return rejection
        self.mock_minimum_single_deposit_validate.return_value = self.expected_rejection

        result = shariah_savings_account.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_minimum_single_deposit_validate.assert_called_once_with(
            vault=self.mock_vault,
            postings=sentinel.posting_instructions,
            denomination=TEST_DENOMINATION,
        )

    def test_pre_posting_minimum_initial_deposit_rejection(self):
        # Mock return rejection
        self.mock_minimum_initial_deposit_validate.return_value = self.expected_rejection

        result = shariah_savings_account.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_minimum_initial_deposit_validate.assert_called_once_with(
            vault=self.mock_vault,
            postings=sentinel.posting_instructions,
            denomination=TEST_DENOMINATION,
            balances=sentinel.balances_balances_observation,
        )

    def test_pre_posting_maximum_balance_limit_rejection(self):
        # Mock return rejection
        self.mock_maximum_balance_limit_validate.return_value = self.expected_rejection

        result = shariah_savings_account.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_maximum_balance_limit_validate.assert_called_once_with(
            vault=self.mock_vault,
            postings=sentinel.posting_instructions,
            denomination=TEST_DENOMINATION,
            balances=sentinel.balances_balances_observation,
        )

    def test_pre_posting_maximum_withdrawal_by_payment_type_rejection(self):
        # Mock return rejection
        self.mock_maximum_withdrawal_by_payment_type_validate.return_value = self.expected_rejection

        result = shariah_savings_account.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_maximum_withdrawal_by_payment_type_validate.assert_called_once_with(
            vault=self.mock_vault,
            postings=sentinel.posting_instructions,
            denomination=TEST_DENOMINATION,
        )

    def test_pre_posting_minimum_balance_by_tier_rejection(self):
        # Mock return rejection
        self.mock_minimum_balance_by_tier_validate.return_value = self.expected_rejection

        result = shariah_savings_account.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_minimum_balance_by_tier_validate.assert_called_once_with(
            vault=self.mock_vault,
            postings=sentinel.posting_instructions,
            balances=sentinel.balances_balances_observation,
            denomination=TEST_DENOMINATION,
        )

    def test_pre_posting_maximum_single_withdrawal_rejection(self):
        # Mock return rejection
        self.mock_maximum_single_withdrawal_validate.return_value = self.expected_rejection

        result = shariah_savings_account.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_maximum_single_withdrawal_validate.assert_called_once_with(
            vault=self.mock_vault,
            postings=sentinel.posting_instructions,
            denomination=TEST_DENOMINATION,
        )

    def test_pre_posting_maximum_daily_deposit_rejection(self):
        # Mock return rejection
        self.mock_maximum_daily_deposit_validate.return_value = self.expected_rejection

        result = shariah_savings_account.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_maximum_daily_deposit_validate.assert_called_once_with(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
            denomination=TEST_DENOMINATION,
        )

    def test_pre_posting_maximum_daily_withdrawal_rejection(self):
        # Mock return rejection
        self.mock_maximum_daily_withdrawal_validate.return_value = self.expected_rejection

        result = shariah_savings_account.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_maximum_daily_withdrawal_validate.assert_called_once_with(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
            denomination=TEST_DENOMINATION,
        )

    def test_pre_posting_maximum_daily_withdrawal_by_payment_type_rejection(self):
        # Mock return rejection
        self.mock_maximum_daily_withdrawal_by_transaction_type_validate.return_value = (
            self.expected_rejection
        )

        result = shariah_savings_account.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_maximum_daily_withdrawal_by_transaction_type_validate.assert_called_once_with(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
            denomination=TEST_DENOMINATION,
        )
