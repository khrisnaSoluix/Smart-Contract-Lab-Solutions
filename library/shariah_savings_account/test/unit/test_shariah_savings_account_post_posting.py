# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
import library.shariah_savings_account.contracts.template.shariah_savings_account as shariah_savings_account  # noqa: E501
from library.shariah_savings_account.test.unit.test_shariah_savings_account_common import (  # noqa: E501
    ShariahSavingsAccountTestBase,
)

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import CustomInstruction, PostPostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PostingInstructionsDirective,
    PostPostingHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelCustomInstruction,
)


@patch.object(shariah_savings_account.payment_type_monthly_limit_fee, "apply_fees")
@patch.object(shariah_savings_account.payment_type_threshold_fee, "apply_fees")
@patch.object(shariah_savings_account.payment_type_flat_fee, "apply_fees")
@patch.object(shariah_savings_account.utils, "get_parameter")
class PostPostingHookTest(ShariahSavingsAccountTestBase):
    def test_post_posting_code_with_all_fees_applied(
        self,
        mock_get_parameter: MagicMock,
        mock_payment_type_flat_fee_apply_fees: MagicMock,
        mock_payment_type_threshold_fee_apply_fees: MagicMock,
        mock_payment_type_monthly_limit_fee_apply_fees: MagicMock,
    ):
        # expected values
        expected_cis_flat_fee = [SentinelCustomInstruction("payment_type_flat_fee_CI")]
        expected_cis_threshold_fee = [SentinelCustomInstruction("payment_type_threshold_fee_CI")]
        expected_cis_monthly_limit_fee = [
            SentinelCustomInstruction("payment_type_monthly_limit_fee_CI")
        ]

        # construct mocks
        mock_vault = self.create_mock(
            client_transactions_mapping={
                shariah_savings_account.fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID: (
                    sentinel.fetched_client_transactions
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "maximum_monthly_payment_type_withdrawal_limit": {"sentinel": "dictionary"},
                "payment_type_fee_income_account": sentinel.payment_type_fee_income_account,
            }
        )

        mock_payment_type_flat_fee_apply_fees.return_value = expected_cis_flat_fee
        mock_payment_type_threshold_fee_apply_fees.return_value = expected_cis_threshold_fee
        mock_payment_type_monthly_limit_fee_apply_fees.return_value = expected_cis_monthly_limit_fee

        # construct expected results
        expected_cis = [
            *expected_cis_flat_fee,
            *expected_cis_threshold_fee,
            *expected_cis_monthly_limit_fee,
        ]
        expected_result = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=expected_cis,  # type: ignore
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        # run function
        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
            client_transactions=sentinel.hook_client_transactions,
        )

        result = shariah_savings_account.post_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # Assert
        self.assertEqual(expected_result, result)
        mock_payment_type_flat_fee_apply_fees.assert_called_once_with(
            vault=mock_vault,
            postings=sentinel.posting_instructions,
            denomination=sentinel.denomination,
        )
        mock_payment_type_threshold_fee_apply_fees.assert_called_once_with(
            vault=mock_vault,
            postings=sentinel.posting_instructions,
            denomination=sentinel.denomination,
        )
        mock_payment_type_monthly_limit_fee_apply_fees.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=sentinel.denomination,
            updated_client_transactions=sentinel.hook_client_transactions,
            historic_client_transactions=sentinel.fetched_client_transactions,
        )

    def test_post_posting_code_with_no_fees_applied(
        self,
        mock_get_parameter: MagicMock,
        mock_payment_type_flat_fee_apply_fees: MagicMock,
        mock_payment_type_threshold_fee_apply_fees: MagicMock,
        mock_payment_type_monthly_limit_fee_apply_fees: MagicMock,
    ):
        # expected values
        expected_cis_flat_fee: list[CustomInstruction] = []
        expected_cis_threshold_fee: list[CustomInstruction] = []
        expected_cis_monthly_limit_fee: list[CustomInstruction] = []

        # construct mocks
        mock_vault = self.create_mock(
            client_transactions_mapping={
                shariah_savings_account.fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID: (
                    sentinel.fetched_client_transactions
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "maximum_monthly_payment_type_withdrawal_limit": {"sentinel": "dictionary"},
                "payment_type_fee_income_account": sentinel.payment_type_fee_income_account,
            }
        )

        mock_payment_type_flat_fee_apply_fees.return_value = expected_cis_flat_fee
        mock_payment_type_threshold_fee_apply_fees.return_value = expected_cis_threshold_fee
        mock_payment_type_monthly_limit_fee_apply_fees.return_value = expected_cis_monthly_limit_fee

        # run function
        hook_arguments = PostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=sentinel.posting_instructions,
            client_transactions=sentinel.hook_client_transactions,
        )

        result = shariah_savings_account.post_posting_hook(
            vault=mock_vault, hook_arguments=hook_arguments
        )

        # Assert
        self.assertIsNone(result)
        mock_payment_type_flat_fee_apply_fees.assert_called_once_with(
            vault=mock_vault,
            postings=sentinel.posting_instructions,
            denomination=sentinel.denomination,
        )
        mock_payment_type_threshold_fee_apply_fees.assert_called_once_with(
            vault=mock_vault,
            postings=sentinel.posting_instructions,
            denomination=sentinel.denomination,
        )
        mock_payment_type_monthly_limit_fee_apply_fees.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=sentinel.denomination,
            updated_client_transactions=sentinel.hook_client_transactions,
            historic_client_transactions=sentinel.fetched_client_transactions,
        )
