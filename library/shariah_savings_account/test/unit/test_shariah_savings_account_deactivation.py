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
from contracts_api import DeactivationHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
    DeactivationHookResult,
    PostingInstructionsDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)


@patch.object(shariah_savings_account.tiered_profit_accrual, "get_profit_reversal_postings")
@patch.object(shariah_savings_account.early_closure_fee, "apply_fees")
@patch.object(shariah_savings_account.utils, "get_parameter")
class DeactivationHookTest(ShariahSavingsAccountTestBase):
    def test_deactivation_instructs_fee_and_residual_profit_instructions(
        self,
        mock_get_parameter: MagicMock,
        mock_apply_fees: MagicMock,
        mock_get_profit_reversal_postings: MagicMock,
    ):
        # Construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                shariah_savings_account.fetchers.LIVE_BALANCES_BOF_ID: (
                    SentinelBalancesObservation("live")
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "MYR"}
        )
        fee_posting = SentinelCustomInstruction("fee_posting")
        reversal_posting = SentinelCustomInstruction("reversal_posting")
        mock_apply_fees.return_value = [fee_posting]
        mock_get_profit_reversal_postings.return_value = [reversal_posting]

        # Construct expected result
        expected_result = DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[fee_posting, reversal_posting],
                    client_batch_id="MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        # Run hook
        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = shariah_savings_account.deactivation_hook(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertEqual(result, expected_result)

        # Assert calls
        mock_get_parameter.assert_called_with(vault=mock_vault, name="denomination")
        mock_apply_fees.assert_called_with(
            vault=mock_vault,
            denomination="MYR",
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances_live,
            account_type=shariah_savings_account.ACCOUNT_TYPE,
        )
        mock_get_profit_reversal_postings.assert_called_with(
            vault=mock_vault,
            denomination="MYR",
            balances=sentinel.balances_live,
            event_name="CLOSE_ACCOUNT",
            account_type=shariah_savings_account.ACCOUNT_TYPE,
        )

    def test_deactivation_with_no_fee_or_residual_profit_instructions(
        self,
        mock_get_parameter: MagicMock,
        mock_apply_fees: MagicMock,
        mock_get_profit_reversal_postings: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                shariah_savings_account.fetchers.LIVE_BALANCES_BOF_ID: (
                    SentinelBalancesObservation("live")
                )
            },
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "MYR"}
        )
        fee_postings: list[CustomInstruction] = []
        reversal_postings: list[CustomInstruction] = []
        mock_apply_fees.return_value = fee_postings
        mock_get_profit_reversal_postings.return_value = reversal_postings

        hook_args = DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        result = shariah_savings_account.deactivation_hook(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertIsNone(result)

        # Assert calls
        mock_get_parameter.assert_called_with(vault=mock_vault, name="denomination")
        mock_apply_fees.assert_called_with(
            vault=mock_vault,
            denomination="MYR",
            effective_datetime=DEFAULT_DATETIME,
            balances=sentinel.balances_live,
            account_type=shariah_savings_account.ACCOUNT_TYPE,
        )
        mock_get_profit_reversal_postings.assert_called_with(
            vault=mock_vault,
            denomination="MYR",
            balances=sentinel.balances_live,
            event_name="CLOSE_ACCOUNT",
            account_type=shariah_savings_account.ACCOUNT_TYPE,
        )
