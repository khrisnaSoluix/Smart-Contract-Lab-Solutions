# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test.unit.test_time_deposit_common import TimeDepositTest

# contracts api
from contracts_api import ConversionHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ConversionHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelScheduledEvent,
)


@patch.object(time_deposit.utils, "update_completed_schedules")
class ConversionHookTest(TimeDepositTest):
    def test_conversion_passes_schedules_through(self, mock_update_completed_schedules: MagicMock):
        existing_schedules = {
            sentinel.accrual_event_type: SentinelScheduledEvent("accrual_event"),
            sentinel.application_event_type: SentinelScheduledEvent("application_event"),
            sentinel.fee_event_type: SentinelScheduledEvent("fee_event"),
        }
        updated_schedules = {
            sentinel.accrual_event_type: SentinelScheduledEvent("accrual_event_new"),
            sentinel.application_event_type: SentinelScheduledEvent("application_event_new"),
            sentinel.fee_event_type: SentinelScheduledEvent("fee_event_new"),
        }
        mock_update_completed_schedules.return_value = updated_schedules

        hook_args = ConversionHookArguments(
            effective_datetime=DEFAULT_DATETIME, existing_schedules=existing_schedules
        )

        expected_result = ConversionHookResult(
            scheduled_events_return_value=updated_schedules,
        )

        hook_result = time_deposit.conversion_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertEqual(hook_result, expected_result)
        mock_update_completed_schedules.assert_called_once_with(
            scheduled_events=existing_schedules,
            effective_datetime=DEFAULT_DATETIME,
            potentially_completed_schedules=[
                time_deposit.deposit_period.DEPOSIT_PERIOD_END_EVENT,
                time_deposit.grace_period.GRACE_PERIOD_END_EVENT,
                time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT,
                time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
            ],
        )
