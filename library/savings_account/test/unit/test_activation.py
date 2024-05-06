# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.savings_account.test.unit.savings_account_common import (
    DEFAULT_DATE,
    SavingsAccountTest,
    savings_account,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ActivationHookArguments,
    ActivationHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelScheduledEvent,
)


class ActivationHookTest(SavingsAccountTest):
    @patch.object(savings_account.minimum_monthly_balance, "scheduled_events")
    @patch.object(savings_account.interest_application, "scheduled_events")
    @patch.object(savings_account.inactivity_fee, "scheduled_events")
    @patch.object(savings_account.tiered_interest_accrual, "scheduled_events")
    def test_activation_returns_event_schedule(
        self,
        mock_tiered_accrual_sched_event: MagicMock,
        mock_inactivity_fee_scheduled_events: MagicMock,
        mock_interest_application_schedule: MagicMock,
        mock_minimum_monthly_balance_schedule_event: MagicMock,
    ):

        mock_inactivity_fee_scheduled_events.return_value = {
            "APPLY_INACTIVITY_FEE": SentinelScheduledEvent("inactivity_fee_schedule")
        }
        mock_interest_application_schedule.return_value = {
            "APPLY_INTEREST": SentinelScheduledEvent("interest_application_schedule")
        }

        mock_tiered_accrual_sched_event.return_value = {
            "ACCRUE_INTEREST": SentinelScheduledEvent("deposit_accrual_schedule")
        }

        mock_minimum_monthly_balance_schedule_event.side_effect = [
            {"APPLY_MINIMUM_BALANCE_FEE": SentinelScheduledEvent("minimum_balance_fee")},
        ]

        hook_result = savings_account.activation_hook(
            sentinel.vault, ActivationHookArguments(effective_datetime=DEFAULT_DATE)
        )

        self.assertEqual(
            hook_result,
            ActivationHookResult(
                scheduled_events_return_value={
                    "APPLY_INACTIVITY_FEE": SentinelScheduledEvent("inactivity_fee_schedule"),
                    "APPLY_INTEREST": SentinelScheduledEvent("interest_application_schedule"),
                    "ACCRUE_INTEREST": SentinelScheduledEvent("deposit_accrual_schedule"),
                    "APPLY_MINIMUM_BALANCE_FEE": SentinelScheduledEvent("minimum_balance_fee"),
                }
            ),
        )
