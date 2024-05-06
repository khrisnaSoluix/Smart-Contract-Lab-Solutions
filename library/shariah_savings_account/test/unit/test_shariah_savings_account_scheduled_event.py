# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
import library.shariah_savings_account.contracts.template.shariah_savings_account as shariah_savings_account  # noqa: E501
from library.shariah_savings_account.test.unit.test_shariah_savings_account_common import (  # noqa: E501
    ShariahSavingsAccountTestBase,
)

# contracts api
from contracts_api import ScheduledEventHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PostingInstructionsDirective,
    ScheduledEventHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelCustomInstruction,
    SentinelUpdateAccountEventTypeDirective,
)


class ScheduledEventHookTest(ShariahSavingsAccountTestBase):
    def test_schedule_with_dummy_event_type(self):
        mock_vault = self.create_mock()
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type="DUMMY"
        )
        result = shariah_savings_account.scheduled_event_hook(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertIsNone(result)

    @patch.object(shariah_savings_account.tiered_profit_accrual, "accrue_profit")
    @patch.object(shariah_savings_account.account_tiers, "get_account_tier")
    def test_accrual_schedule_instructs_profit_accrual_postings(
        self,
        mock_get_account_tier: MagicMock,
        mock_accrue_profit: MagicMock,
    ):
        # Construct mocks
        mock_vault = self.create_mock()
        accrual_custom_instructions = [SentinelCustomInstruction("standard_accrual")]
        mock_get_account_tier.return_value = sentinel.account_tier
        mock_accrue_profit.return_value = accrual_custom_instructions

        # Construct expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=accrual_custom_instructions,  # type: ignore
                    client_batch_id="ACCRUE_PROFIT_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ]
        )

        # Run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=shariah_savings_account.tiered_profit_accrual.ACCRUAL_EVENT,
        )
        result = shariah_savings_account.scheduled_event_hook(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertEqual(result, expected_result)

        # Assert calls
        mock_accrue_profit.assert_called_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            account_tier=sentinel.account_tier,
            account_type="SHARIAH_SAVINGS_ACCOUNT",
        )

    @patch.object(shariah_savings_account.profit_application, "update_next_schedule_execution")
    @patch.object(shariah_savings_account.profit_application, "apply_profit")
    def test_application_schedule_instructs_profit_application_postings(
        self,
        mock_apply_profit: MagicMock,
        mock_update_next_schedule_execution: MagicMock,
    ):
        # Construct mocks
        mock_vault = self.create_mock()
        apply_custom_instructions = [SentinelCustomInstruction("standard_application")]
        mock_apply_profit.return_value = apply_custom_instructions
        updated_schedule = SentinelUpdateAccountEventTypeDirective("next_schedule")
        mock_update_next_schedule_execution.return_value = updated_schedule

        # Construct expected result
        expected_result = ScheduledEventHookResult(
            update_account_event_type_directives=[updated_schedule],
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=apply_custom_instructions,  # type: ignore
                    client_batch_id="APPLY_PROFIT_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        )

        # Run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=(shariah_savings_account.profit_application.APPLICATION_EVENT),
        )
        result = shariah_savings_account.scheduled_event_hook(
            vault=mock_vault, hook_arguments=hook_args
        )
        self.assertEqual(result, expected_result)

        # Assert calls
        mock_apply_profit.assert_called_with(
            vault=mock_vault,
            account_type="SHARIAH_SAVINGS_ACCOUNT",
        )
