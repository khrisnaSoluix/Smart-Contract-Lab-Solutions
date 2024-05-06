# standard libs
from unittest.mock import MagicMock, patch

# library
from library.savings_account.test.unit.savings_account_common import (
    DEFAULT_DATE,
    SavingsAccountTest,
    savings_account,
)

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import ScheduledEventHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PostingInstructionsDirective,
    ScheduledEventHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelCustomInstruction,
    SentinelUpdateAccountEventTypeDirective,
)

parameters = {
    "accrued_interest_payable_account": "ACCRUED_INTEREST_PAYABLE",
    "denomination": "GBP",
}


@patch.object(savings_account.inactivity_fee, "apply")
@patch.object(savings_account.utils, "is_flag_in_list_applied")
class ScheduledEventInactivityFeeTest(SavingsAccountTest):
    def test_inactivity_fee_account_not_dormant(
        self, mock_is_flag_in_list_applied: MagicMock, mock_inactivity_fee_apply: MagicMock
    ):
        # mocks
        mock_is_flag_in_list_applied.return_value = False

        # hook call
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATE,
            event_type=savings_account.inactivity_fee.APPLICATION_EVENT,
        )
        hook_result = savings_account.scheduled_event_hook(self.create_mock(), hook_arguments)

        # assertions
        self.assertIsNone(hook_result)
        mock_inactivity_fee_apply.assert_not_called()

    def test_inactivity_fee_account_dormant(
        self, mock_is_flag_in_list_applied: MagicMock, mock_inactivity_fee_apply: MagicMock
    ):
        # mocks
        mock_is_flag_in_list_applied.return_value = True
        mock_inactivity_fee_apply.return_value = [SentinelCustomInstruction("inactivity_fee")]
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("inactivity_fee")],
                    value_datetime=DEFAULT_DATE,
                    client_batch_id=f"MOCK_HOOK_{savings_account.inactivity_fee.APPLICATION_EVENT}",
                )
            ]
        )
        mock_vault = self.create_mock()

        # hook call
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATE,
            event_type=savings_account.inactivity_fee.APPLICATION_EVENT,
        )
        hook_result = savings_account.scheduled_event_hook(mock_vault, hook_arguments)

        # assertions
        self.assertEquals(hook_result, expected_result)
        mock_inactivity_fee_apply.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATE
        )


class ScheduledEventHookTest(SavingsAccountTest):
    @patch.object(savings_account.tiered_interest_accrual, "accrue_interest")
    def test_scheduled_event_accrue_interest(
        self,
        mock_accrue_interest: MagicMock,
    ):
        mock_accrue_interest.return_value = [SentinelCustomInstruction("accrued_interest")]

        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATE, event_type="ACCRUE_INTEREST"
        )
        mock_vault = self.create_mock()

        hook_result = savings_account.scheduled_event_hook(mock_vault, hook_arguments)
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("accrued_interest"),
                    ],
                    value_datetime=DEFAULT_DATE,
                    client_batch_id="MOCK_HOOK_ACCRUE_INTEREST",
                )
            ]
        )

        self.assertEqual(hook_result, expected_result)
        mock_accrue_interest.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATE
        )

    @patch.object(savings_account.interest_application, "update_next_schedule_execution")
    @patch.object(savings_account.interest_application, "apply_interest")
    def test_scheduled_event_apply_interest(
        self,
        mock_apply_interest: MagicMock,
        mock_update_next_schedule_execution: MagicMock,
    ):
        mock_apply_interest.return_value = [SentinelCustomInstruction("apply_interest")]
        mock_update_next_schedule_execution.return_value = SentinelUpdateAccountEventTypeDirective(
            "directive"
        )
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATE, event_type="APPLY_INTEREST"
        )
        mock_vault = self.create_mock()

        hook_result = savings_account.scheduled_event_hook(mock_vault, hook_arguments)
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("apply_interest"),
                    ],
                    value_datetime=DEFAULT_DATE,
                    client_batch_id="MOCK_HOOK_APPLY_INTEREST",
                )
            ],
            update_account_event_type_directives=[
                SentinelUpdateAccountEventTypeDirective("directive")
            ],
        )

        self.assertEquals(hook_result, expected_result)
        mock_apply_interest.assert_called_once_with(
            vault=mock_vault, account_type="SAVINGS_ACCOUNT"
        )
        mock_update_next_schedule_execution.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATE
        )

    @patch.object(savings_account.minimum_monthly_balance, "apply_minimum_balance_fee")
    @patch.object(savings_account.utils, "is_flag_in_list_applied")
    @patch.object(savings_account.utils, "get_parameter")
    def test_scheduled_event_apply_minimum_balance_fee(
        self,
        mock_get_parameter: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_apply_minimum_balance_fee: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": "GBP",
            }
        )
        mock_is_flag_in_list_applied.return_value = False
        mock_apply_minimum_balance_fee.return_value = [
            SentinelCustomInstruction("apply_minimum_balance_fee")
        ]

        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATE,
            event_type=savings_account.minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT,
        )

        mock_vault = self.create_mock()
        hook_result = savings_account.scheduled_event_hook(mock_vault, hook_arguments)
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("apply_minimum_balance_fee"),
                    ],
                    value_datetime=DEFAULT_DATE,
                    client_batch_id="MOCK_HOOK_APPLY_MINIMUM_BALANCE_FEE",
                )
            ]
        )

        self.assertEquals(hook_result, expected_result)

        mock_apply_minimum_balance_fee.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATE,
            denomination="GBP",
        )
