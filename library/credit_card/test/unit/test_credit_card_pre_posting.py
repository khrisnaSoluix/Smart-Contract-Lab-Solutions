# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import patch, sentinel

# library
from library.credit_card.contracts.template import credit_card
from library.credit_card.test.unit.test_credit_card_common import CreditCardTestBase

# features
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
    SentinelCustomInstruction,
    SentinelRejection,
)


class CreditCardPrePostingTest(CreditCardTestBase):
    def setUp(self) -> None:
        # balances observation
        self.balances_observation = SentinelBalancesObservation("balances_observation")
        # mock vault
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                credit_card.LIVE_BALANCES_BOF_ID: self.balances_observation
            },
        )

        # default expected rejection
        self.expected_rejection = SentinelRejection("rejection")

        # default expected result
        self.expected_result = PrePostingHookResult(rejection=self.expected_rejection)

        # default postings
        ci = SentinelCustomInstruction("default")
        ci._set_output_attributes(  # type: ignore
            own_account_id=self.mock_vault.account_id,
            tside=credit_card.tside,
        )
        self.default_postings: list[credit_card.PostingInstruction] = [ci]

        # default hook arguments
        self.hook_arguments = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=self.default_postings,
            client_transactions=sentinel.client_transactions,
        )

        # get parameter
        patch_get_parameter = patch.object(credit_card.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "transaction_code_to_type_map": sentinel.transaction_code_to_type_map,
            }
        )

        # validate denomination
        patch_validate_denomination = patch.object(credit_card.utils, "validate_denomination")
        self.mock_validate_denomination = patch_validate_denomination.start()
        self.mock_validate_denomination.return_value = None

        # get supported transaction types
        patch_get_supported_txn_types = patch.object(credit_card, "_get_supported_txn_types")
        self.mock_get_supported_txn_types = patch_get_supported_txn_types.start()
        self.mock_get_supported_txn_types.return_value = sentinel.supported_txn_types

        # validate transaction type and refs
        patch_validate_txn_type_and_refs = patch.object(credit_card, "_validate_txn_type_and_refs")
        self.mock_validate_txn_type_and_refs = patch_validate_txn_type_and_refs.start()
        self.mock_validate_txn_type_and_refs.return_value = None

        # get non advice postings
        patch_get_non_advice_postings = patch.object(credit_card, "_get_non_advice_postings")
        self.mock_get_non_advice_postings = patch_get_non_advice_postings.start()
        self.mock_get_non_advice_postings.return_value = self.default_postings

        # check account has sufficient funds
        patch_check_account_has_sufficient_funds = patch.object(
            credit_card, "_check_account_has_sufficient_funds"
        )
        self.mock_check_account_has_sufficient_funds = (
            patch_check_account_has_sufficient_funds.start()
        )
        self.mock_check_account_has_sufficient_funds.return_value = None

        # check transaction type credit limits
        patch_check_txn_type_credit_limits = patch.object(
            credit_card, "_check_txn_type_credit_limits"
        )
        self.mock_check_txn_type_credit_limits = patch_check_txn_type_credit_limits.start()
        self.mock_check_txn_type_credit_limits.return_value = None

        # check transaction type time limits
        patch_check_txn_type_time_limits = patch.object(credit_card, "_check_txn_type_time_limits")
        self.mock_check_txn_type_time_limits = patch_check_txn_type_time_limits.start()
        self.mock_check_txn_type_time_limits.return_value = None

        # default expected result
        self.expected_result = PrePostingHookResult(rejection=self.expected_rejection)

        # clean up - runs after each test is complete
        self.addCleanup(patch.stopall)

        return super().setUp()

    def test_pre_posting_hook_no_rejections(self):
        result = credit_card.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertIsNone(result)

    def test_pre_posting_hook_wrong_denomination(self):
        # Mock return rejection
        self.mock_validate_denomination.return_value = self.expected_rejection

        result = credit_card.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_validate_denomination.assert_called_once_with(
            posting_instructions=self.default_postings,
            accepted_denominations=[sentinel.denomination],
        )

    def test_pre_posting_validate_transaction_type_rejection(self):
        # Mock return rejection
        self.mock_validate_txn_type_and_refs.return_value = self.expected_rejection

        result = credit_card.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_validate_txn_type_and_refs.assert_called_once_with(
            self.mock_vault,
            self.balances_observation.balances,
            self.default_postings,
            sentinel.supported_txn_types,
            sentinel.transaction_code_to_type_map,
            DEFAULT_DATETIME,
        )

    def test_pre_posting_insufficient_funds_rejection(self):
        # Mock return rejection
        self.mock_check_account_has_sufficient_funds.return_value = self.expected_rejection

        result = credit_card.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_check_account_has_sufficient_funds.assert_called_once_with(
            self.mock_vault,
            self.balances_observation.balances,
            sentinel.denomination,
            self.default_postings,
        )

    def test_pre_posting_transaction_type_credit_limit_rejection(self):
        # Mock return rejection
        self.mock_check_txn_type_credit_limits.return_value = self.expected_rejection

        result = credit_card.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_check_txn_type_credit_limits.assert_called_once_with(
            self.mock_vault,
            self.balances_observation.balances,
            self.default_postings,
            sentinel.denomination,
            DEFAULT_DATETIME,
            sentinel.transaction_code_to_type_map,
        )

    def test_pre_posting_transaction_type_time_limit_rejection(self):
        # Mock return rejection
        self.mock_check_txn_type_time_limits.return_value = self.expected_rejection

        result = credit_card.pre_posting_hook(
            vault=self.mock_vault,
            hook_arguments=self.hook_arguments,
        )
        self.assertEqual(self.expected_result, result)

        self.mock_check_txn_type_time_limits.assert_called_once_with(
            self.mock_vault,
            self.default_postings,
            DEFAULT_DATETIME,
        )
