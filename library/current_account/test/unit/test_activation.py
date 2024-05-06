# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.current_account.test.unit.current_account_common import (
    DEFAULT_DATE,
    CurrentAccountTest,
    current_account,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ActivationHookArguments,
    ActivationHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelScheduledEvent,
)


class ActivationHookTest(CurrentAccountTest):
    @patch.object(current_account.unarranged_overdraft_fee, "application_scheduled_events")
    @patch.object(current_account.minimum_monthly_balance, "scheduled_events")
    @patch.object(current_account.interest_application, "scheduled_events")
    @patch.object(current_account.inactivity_fee, "scheduled_events")
    @patch.object(current_account.tiered_interest_accrual, "scheduled_events")
    @patch.object(current_account.maintenance_fees, "scheduled_events")
    def test_activation_returns_event_schedule(
        self,
        mock_maintenance_fees_scheduled_events: MagicMock,
        mock_tiered_accrual_sched_event: MagicMock,
        mock_inactivity_fee_scheduled_events: MagicMock,
        mock_interest_application_schedule: MagicMock,
        mock_minimum_monthly_balance_schedule_event: MagicMock,
        mock_unarranged_overdraft_scheduled_events: MagicMock,
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

        mock_maintenance_fees_scheduled_events.side_effect = [
            {"APPLY_MONTHLY_FEE": SentinelScheduledEvent("monthly_maintenance_fee")},
            {"APPLY_ANNUAL_FEE": SentinelScheduledEvent("annual_maintenance_fee")},
        ]
        mock_minimum_monthly_balance_schedule_event.side_effect = [
            {"APPLY_MINIMUM_BALANCE_FEE": SentinelScheduledEvent("minimum_balance_fee")},
        ]
        mock_unarranged_overdraft_scheduled_events.return_value = {
            "APPLY_UNARRANGED_OVERDRAFT_FEE": (
                SentinelScheduledEvent("unarranged_overdraft_application")
            ),
        }

        hook_result = current_account.activation_hook(
            sentinel.vault, ActivationHookArguments(effective_datetime=DEFAULT_DATE)
        )

        self.assertEqual(
            hook_result,
            ActivationHookResult(
                scheduled_events_return_value={
                    "APPLY_INACTIVITY_FEE": SentinelScheduledEvent("inactivity_fee_schedule"),
                    "APPLY_INTEREST": SentinelScheduledEvent("interest_application_schedule"),
                    "ACCRUE_INTEREST": SentinelScheduledEvent("deposit_accrual_schedule"),
                    "APPLY_MONTHLY_FEE": SentinelScheduledEvent("monthly_maintenance_fee"),
                    "APPLY_ANNUAL_FEE": SentinelScheduledEvent("annual_maintenance_fee"),
                    "APPLY_MINIMUM_BALANCE_FEE": SentinelScheduledEvent("minimum_balance_fee"),
                    "APPLY_UNARRANGED_OVERDRAFT_FEE": (
                        SentinelScheduledEvent("unarranged_overdraft_application")
                    ),
                }
            ),
        )
