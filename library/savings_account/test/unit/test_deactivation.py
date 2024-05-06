# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
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


@patch.object(savings_account.utils, "get_parameter")
@patch.object(savings_account.utils, "is_flag_in_list_applied")
class DeactivationHookTest(SavingsAccountTest):
    balances_observation_mapping = {
        savings_account.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
    }

    def test_deactivation_returns_rejection_flag_active(
        self, mock_is_flag_in_list_applied: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_is_flag_in_list_applied.return_value = True
        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATE)
        mock_get_parameter.side_effect = mock_utils_get_parameter({"denomination": "GBP"})

        hook_result = savings_account.deactivation_hook(MagicMock, hook_arguments)

        expected_result = DeactivationHookResult(
            rejection=Rejection(
                message="Cannot close a dormant account.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        self.assertEqual(hook_result, expected_result)

    @patch.object(savings_account.partial_fee, "has_outstanding_fees")
    def test_deactivation_returns_rejection_if_outstanding_fees(
        self,
        mock_has_outstanding_fees: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_flag_in_list_applied.return_value = False
        mock_has_outstanding_fees.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter({"denomination": "GBP"})
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.balances_observation_mapping
        )

        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATE)
        hook_result = savings_account.deactivation_hook(mock_vault, hook_arguments)

        expected_result = DeactivationHookResult(
            rejection=Rejection(
                message="Cannot close account with outstanding fees.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        self.assertEqual(hook_result, expected_result)
        mock_has_outstanding_fees.assert_called_once_with(
            vault=mock_vault,
            fee_collection=savings_account.FEE_HIERARCHY,
            balances=sentinel.balances_live,
            denomination="GBP",
        )

    @patch.object(savings_account.partial_fee, "has_outstanding_fees")
    @patch.object(savings_account.tiered_interest_accrual, "get_interest_reversal_postings")
    def test_deactivation_returns_interest_reversal_postings_no_outstanding_fees(
        self,
        mock_get_interest_reversal_postings: MagicMock,
        mock_has_outstanding_fees: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_flag_in_list_applied.return_value = False
        mock_has_outstanding_fees.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter({"denomination": "GBP"})
        mock_get_interest_reversal_postings.return_value = [
            SentinelCustomInstruction("interest_reversal_postings")
        ]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.balances_observation_mapping
        )

        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATE)
        hook_result = savings_account.deactivation_hook(mock_vault, hook_arguments)

        mock_get_interest_reversal_postings.assert_called_once_with(
            vault=mock_vault,
            event_name="CLOSE_ACCOUNT",
            account_type=savings_account.PRODUCT_NAME,
            balances=sentinel.balances_live,
            denomination="GBP",
        )
        mock_has_outstanding_fees.assert_called_once_with(
            vault=mock_vault,
            fee_collection=savings_account.FEE_HIERARCHY,
            balances=sentinel.balances_live,
            denomination="GBP",
        )

        self.assertEqual(
            hook_result,
            DeactivationHookResult(
                posting_instructions_directives=[
                    PostingInstructionsDirective(
                        posting_instructions=[
                            SentinelCustomInstruction("interest_reversal_postings")
                        ],
                        value_datetime=DEFAULT_DATE,
                        client_batch_id="MOCK_HOOK_CLOSE_ACCOUNT",
                    )
                ]
            ),
        )

    @patch.object(savings_account.partial_fee, "has_outstanding_fees")
    @patch.object(savings_account.tiered_interest_accrual, "get_interest_reversal_postings")
    def test_deactivation_returns_none_no_outstanding_fees_no_accrued_interest(
        self,
        mock_get_interest_reversal_postings: MagicMock,
        mock_has_outstanding_fees: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_flag_in_list_applied.return_value = False
        mock_has_outstanding_fees.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter({"denomination": "GBP"})
        mock_get_interest_reversal_postings.return_value = []
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.balances_observation_mapping
        )

        hook_arguments = DeactivationHookArguments(effective_datetime=DEFAULT_DATE)
        self.assertIsNone(savings_account.deactivation_hook(mock_vault, hook_arguments))

        mock_get_interest_reversal_postings.assert_called_once_with(
            vault=mock_vault,
            event_name="CLOSE_ACCOUNT",
            account_type=savings_account.PRODUCT_NAME,
            balances=sentinel.balances_live,
            denomination="GBP",
        )
        mock_has_outstanding_fees.assert_called_once_with(
            vault=mock_vault,
            fee_collection=savings_account.FEE_HIERARCHY,
            balances=sentinel.balances_live,
            denomination="GBP",
        )
