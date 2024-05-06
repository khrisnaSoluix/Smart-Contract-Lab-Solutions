# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from unittest.mock import MagicMock, patch, sentinel

# library
import library.bnpl.contracts.template.bnpl as bnpl
from library.bnpl.test.unit.test_bnpl_common import BNPLTest

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import PostPostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DENOMINATION,
    DEFAULT_HOOK_EXECUTION_ID,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    PostingInstructionsDirective,
    PostPostingHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)

DEFAULT_DATETIME = datetime(2023, 1, 1, tzinfo=bnpl.UTC_ZONE)


@patch.object(bnpl.utils, "is_force_override")
class PostPostingHookTest(BNPLTest):
    @patch.object(bnpl.payments, "generate_repayment_postings")
    @patch.object(bnpl.utils, "get_parameter")
    @patch.object(bnpl.close_loan, "does_repayment_fully_repay_loan")
    def test_post_posting_hook_returns_none_on_empty_posting_instructions(
        self,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_generate_repayment_postings: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # construct expected result
        expected = None

        # construct mocks
        mock_generate_repayment_postings.return_value = []
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                bnpl.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
            }
        )
        mock_does_repayment_fully_repay_loan.return_value = False

        # run function
        hook_args = PostPostingHookArguments(
            posting_instructions=[],
            effective_datetime=DEFAULT_DATETIME,
            client_transactions={},
        )
        result = bnpl.post_posting_hook(mock_vault, hook_args)

        # validate results
        self.assertEqual(result, expected)
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=[],
            balances=sentinel.balances_dummy_balances_observation,
            denomination=DEFAULT_DENOMINATION,
            account_id=mock_vault.account_id,
            payment_addresses=bnpl.lending_addresses.ALL_OUTSTANDING,
        )

    @patch.object(bnpl.payments, "generate_repayment_postings")
    @patch.object(bnpl.utils, "get_parameter")
    @patch.object(bnpl.close_loan, "does_repayment_fully_repay_loan")
    def test_post_posting_hook_returns_repayment_posting_instructions(
        self,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_generate_repayment_postings: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # expected values
        mock_repayment_posting = SentinelCustomInstruction("dummy_posting")

        # construct expected result
        expected = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[mock_repayment_posting],
                    client_batch_id=f"REPAYMENT_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            account_notification_directives=[],
        )

        # construct mocks
        mock_generate_repayment_postings.return_value = [mock_repayment_posting]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                bnpl.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
            }
        )
        mock_does_repayment_fully_repay_loan.return_value = False

        # run function
        hook_args = PostPostingHookArguments(
            posting_instructions=[sentinel.posting_instructions],
            effective_datetime=DEFAULT_DATETIME,
            client_transactions={},
        )
        result = bnpl.post_posting_hook(mock_vault, hook_args)

        # validate results
        self.assertEqual(result, expected)
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=[mock_repayment_posting],
            balances=sentinel.balances_dummy_balances_observation,
            denomination=DEFAULT_DENOMINATION,
            account_id=mock_vault.account_id,
            payment_addresses=bnpl.lending_addresses.ALL_OUTSTANDING,
        )

    @patch.object(bnpl.payments, "generate_repayment_postings")
    @patch.object(bnpl.utils, "get_parameter")
    @patch.object(bnpl.close_loan, "does_repayment_fully_repay_loan")
    @patch.object(bnpl.close_loan, "send_loan_paid_off_notification")
    def test_post_posting_hook_returns_both_postings_and_notifications(
        self,
        mock_send_loan_paid_off_notification: MagicMock,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_generate_repayment_postings: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # expected values
        product_name = "PRODUCT_A"
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )
        mock_repayment_posting = SentinelCustomInstruction("dummy_posting")

        # construct expected result
        expected_notification_type = (
            f"{product_name}{bnpl.close_loan.notification_type(product_name=bnpl.PRODUCT_NAME)}"
        )
        expected_notification_details = {
            "account_id": mock_vault.account_id,
        }
        expected_notification: AccountNotificationDirective = AccountNotificationDirective(
            notification_type=expected_notification_type,
            notification_details=expected_notification_details,
        )
        expected = PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[mock_repayment_posting],
                    client_batch_id=f"REPAYMENT_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            account_notification_directives=[expected_notification],
        )

        # construct mocks
        mock_generate_repayment_postings.return_value = [mock_repayment_posting]
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                bnpl.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
            }
        )
        mock_does_repayment_fully_repay_loan.return_value = True
        mock_send_loan_paid_off_notification.return_value = expected_notification

        # run function
        hook_args = PostPostingHookArguments(
            posting_instructions=[sentinel.posting_instructions],
            effective_datetime=DEFAULT_DATETIME,
            client_transactions={},
        )
        result = bnpl.post_posting_hook(mock_vault, hook_args)

        # validate results
        self.assertEqual(result, expected)
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=[mock_repayment_posting],
            balances=sentinel.balances_dummy_balances_observation,
            denomination=DEFAULT_DENOMINATION,
            account_id=mock_vault.account_id,
            payment_addresses=bnpl.lending_addresses.ALL_OUTSTANDING,
        )
        mock_send_loan_paid_off_notification.assert_called_once_with(
            account_id=mock_vault.account_id, product_name=bnpl.PRODUCT_NAME
        )

    @patch.object(bnpl.payments, "generate_repayment_postings")
    @patch.object(bnpl.utils, "get_parameter")
    @patch.object(bnpl.close_loan, "does_repayment_fully_repay_loan")
    @patch.object(bnpl.close_loan, "send_loan_paid_off_notification")
    def test_post_posting_hook_returns_only_notifications(
        self,
        mock_send_loan_paid_off_notification: MagicMock,
        mock_does_repayment_fully_repay_loan: MagicMock,
        mock_get_parameter: MagicMock,
        mock_generate_repayment_postings: MagicMock,
        mock_is_force_override: MagicMock,
    ):
        # expected values
        product_name = "PRODUCT_A"
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "dummy_balances_observation"
                )
            },
        )

        # construct expected result
        expected_notification_details = {
            "account_id": mock_vault.account_id,
        }
        expected_notification_type = (
            f"{product_name}{bnpl.close_loan.notification_type(product_name=bnpl.PRODUCT_NAME)}"
        )
        expected_notification: AccountNotificationDirective = AccountNotificationDirective(
            notification_type=expected_notification_type,
            notification_details=expected_notification_details,
        )
        expected = PostPostingHookResult(
            posting_instructions_directives=[],
            account_notification_directives=[expected_notification],
        )

        # construct mocks
        mock_generate_repayment_postings.return_value = []
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                bnpl.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
            }
        )
        mock_does_repayment_fully_repay_loan.return_value = True
        mock_send_loan_paid_off_notification.return_value = expected_notification

        # run function
        hook_args = PostPostingHookArguments(
            posting_instructions=[],
            effective_datetime=DEFAULT_DATETIME,
            client_transactions={},
        )
        result = bnpl.post_posting_hook(mock_vault, hook_args)

        # validate results
        self.assertEqual(result, expected)
        mock_does_repayment_fully_repay_loan.assert_called_once_with(
            repayment_posting_instructions=[],
            balances=sentinel.balances_dummy_balances_observation,
            denomination=DEFAULT_DENOMINATION,
            account_id=mock_vault.account_id,
            payment_addresses=bnpl.lending_addresses.ALL_OUTSTANDING,
        )
        mock_send_loan_paid_off_notification.assert_called_once_with(
            account_id=mock_vault.account_id, product_name=bnpl.PRODUCT_NAME
        )

    def test_post_posting_hook_returns_none_for_force_override(
        self,
        mock_is_force_override: MagicMock,
    ):
        # construct expected result
        expected = None

        # construct mocks
        mock_vault = self.create_mock()
        mock_is_force_override.return_value = True

        # run function
        hook_args = PostPostingHookArguments(
            posting_instructions=sentinel.posting_instructions,
            effective_datetime=DEFAULT_DATETIME,
            client_transactions={},
        )
        result = bnpl.post_posting_hook(mock_vault, hook_args)

        # validate results
        self.assertEqual(result, expected)
