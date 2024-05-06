# standard libs
from unittest.mock import patch, sentinel

# library
from library.us_products.contracts.template import us_checking_account
from library.us_products.test.unit.test_us_checking_account_common import CheckingAccountTest

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import PrePostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PrePostingHookResult,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelRejection,
)


class PrePostingHookTest(CheckingAccountTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = sentinel.vault

        # default hook arguments
        self.hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[sentinel.posting_instruction],
            client_transactions={},
        )

        # default expected rejection
        self.expected_rejection = SentinelRejection("rejection")

        # default expected result
        self.expected_result = PrePostingHookResult(rejection=self.expected_rejection)

        # get parameter
        patch_get_parameter = patch.object(us_checking_account.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )

        # is force override
        patch_is_force_override = patch.object(us_checking_account.utils, "is_force_override")
        self.mock_is_force_override = patch_is_force_override.start()
        self.mock_is_force_override.return_value = False

        # validate denomination
        patch_validate_denomination = patch.object(
            us_checking_account.utils, "validate_denomination"
        )
        self.mock_validate_denomination = patch_validate_denomination.start()
        self.mock_validate_denomination.return_value = None

        # is flag in list applied
        patch_validate_account_transaction = patch.object(
            us_checking_account.dormancy, "validate_account_transaction"
        )
        self.mock_validate_account_transaction = patch_validate_account_transaction.start()
        self.mock_validate_account_transaction.return_value = None

        # validate maximum_daily_withdrawal_by_transaction_type
        patch_maximum_daily_withdrawal_by_transaction_type_validate = patch.object(
            us_checking_account.maximum_daily_withdrawal_by_transaction_type, "validate"
        )
        self.mock_maximum_daily_withdrawal_by_transaction_type_validate = (
            patch_maximum_daily_withdrawal_by_transaction_type_validate.start()
        )
        self.mock_maximum_daily_withdrawal_by_transaction_type_validate.return_value = None

        # validate overdraft limit
        patch_overdraft_coverage_validate = patch.object(
            us_checking_account.overdraft_coverage, "validate"
        )
        self.mock_overdraft_coverage_validate = patch_overdraft_coverage_validate.start()
        self.mock_overdraft_coverage_validate.return_value = None

        patch_group_postings_by_fee_eligibility = patch.object(
            us_checking_account.unlimited_fee_rebate,
            "group_posting_instructions_by_fee_eligibility",
        )
        self.mock_group_postings = patch_group_postings_by_fee_eligibility.start()
        self.mock_group_postings.return_value = {
            us_checking_account.unlimited_fee_rebate.NON_FEE_POSTINGS: [
                sentinel.posting_instruction
            ],
            us_checking_account.unlimited_fee_rebate.FEES_ELIGIBLE_FOR_REBATE: [],
            us_checking_account.unlimited_fee_rebate.FEES_INELIGIBLE_FOR_REBATE: [],
        }

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_when_force_override_is_active_posting_instructions_are_accepted(self):
        # setup mocks
        self.mock_is_force_override.return_value = True

        # hook call
        hook_result = us_checking_account.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        # assertions
        self.assertIsNone(hook_result)
        self.mock_is_force_override.assert_called_once_with(
            posting_instructions=[sentinel.posting_instruction]
        )

    def test_posting_with_unsupported_denomination_is_rejected(self):
        # setup mocks
        self.mock_validate_denomination.return_value = self.expected_rejection

        # hook call
        hook_result = us_checking_account.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, self.expected_result)
        self.mock_get_parameter.assert_called_once_with(
            vault=self.mock_vault, name="denomination", at_datetime=None
        )
        self.mock_validate_denomination.assert_called_with(
            posting_instructions=[sentinel.posting_instruction],
            accepted_denominations=[sentinel.denomination],
        )

    def test_posting_when_account_dormant_is_rejected(self):
        # construct values
        dormancy_rejection = Rejection(
            message="Account flagged 'Dormant' does not accept external transactions.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        dormancy_result = PrePostingHookResult(rejection=dormancy_rejection)

        # setup mocks
        self.mock_validate_account_transaction.return_value = dormancy_rejection

        # hook call
        hook_result = us_checking_account.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, dormancy_result)
        self.mock_validate_account_transaction.assert_called_once_with(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

    def test_posting_that_exceeds_maximum_daily_withdrawal_by_txn_type_is_rejected(self):
        # setup mocks
        self.mock_maximum_daily_withdrawal_by_transaction_type_validate.return_value = (
            self.expected_rejection
        )

        # hook call
        hook_result = us_checking_account.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, self.expected_result)
        self.mock_get_parameter.assert_called_once_with(
            vault=self.mock_vault, name="denomination", at_datetime=None
        )
        self.mock_validate_denomination.assert_called_with(
            posting_instructions=[sentinel.posting_instruction],
            accepted_denominations=[sentinel.denomination],
        )

    def test_posting_is_rejected_when_amount_exceeds_overdraft_coverage(self):
        # setup mocks
        self.mock_overdraft_coverage_validate.return_value = self.expected_rejection
        self.mock_group_postings.return_value = {
            us_checking_account.unlimited_fee_rebate.NON_FEE_POSTINGS: [
                sentinel.posting_instruction
            ],
            us_checking_account.unlimited_fee_rebate.FEES_ELIGIBLE_FOR_REBATE: [
                sentinel.eligible_for_rebate_posting
            ],
            us_checking_account.unlimited_fee_rebate.FEES_INELIGIBLE_FOR_REBATE: [
                sentinel.ineligible_fee_posting
            ],
        }
        # hook call
        hook_result = us_checking_account.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        # assertions
        self.assertEqual(hook_result, self.expected_result)
        self.mock_get_parameter.assert_called_once_with(
            vault=self.mock_vault, name="denomination", at_datetime=None
        )
        self.mock_overdraft_coverage_validate.assert_called_with(
            vault=sentinel.vault,
            postings=[sentinel.posting_instruction, sentinel.ineligible_fee_posting],
            denomination=sentinel.denomination,
            effective_datetime=DEFAULT_DATETIME,
        )

    def test_none_returned_when_no_rejections(self):
        # hook call
        hook_result = us_checking_account.pre_posting_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        # assertions
        self.assertIsNone(hook_result)
        self.mock_get_parameter.assert_called_once_with(
            vault=self.mock_vault, name="denomination", at_datetime=None
        )
