# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from unittest.mock import patch, sentinel

# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test.unit.test_time_deposit_common import TimeDepositTest

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ActivationHookArguments,
    ActivationHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelScheduledEvent,
)


class ActivationHookCommon(TimeDepositTest):
    def setUp(self) -> None:
        self.mock_vault = sentinel.vault

        self.hook_arguments = ActivationHookArguments(
            effective_datetime=DEFAULT_DATETIME,
        )

        patch_fixed_interest_accrual_scheduled_events = patch.object(
            time_deposit.fixed_interest_accrual, "scheduled_events"
        )
        self.mock_fixed_interest_accrual_scheduled_events = (
            patch_fixed_interest_accrual_scheduled_events.start()
        )
        self.mock_fixed_interest_accrual_scheduled_events.return_value = {
            time_deposit.fixed_interest_accrual.ACCRUAL_EVENT: SentinelScheduledEvent(
                "interest_accrual"
            ),
        }

        patch_interest_application_scheduled_events = patch.object(
            time_deposit.interest_application, "scheduled_events"
        )
        self.mock_interest_application_scheduled_events = (
            patch_interest_application_scheduled_events.start()
        )
        self.mock_interest_application_scheduled_events.return_value = {
            time_deposit.interest_application.APPLICATION_EVENT: SentinelScheduledEvent(
                "interest_application"
            ),
        }

        patch_create_end_of_time_schedule = patch.object(
            time_deposit.utils, "create_end_of_time_schedule"
        )
        self.mock_create_end_of_time_schedule = patch_create_end_of_time_schedule.start()
        self.mock_create_end_of_time_schedule.return_value = SentinelScheduledEvent(
            "end_of_time_schedule"
        )

        patch_get_grace_period_parameter = patch.object(
            time_deposit.grace_period, "get_grace_period_parameter"
        )
        self.mock_get_grace_period_parameter = patch_get_grace_period_parameter.start()
        self.mock_get_grace_period_parameter.return_value = 0

        patch_deposit_maturity_scheduled_events = patch.object(
            time_deposit.deposit_maturity, "scheduled_events"
        )
        self.mock_deposit_maturity_scheduled_events = (
            patch_deposit_maturity_scheduled_events.start()
        )
        self.mock_deposit_maturity_scheduled_events.side_effect = [
            {
                time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT: SentinelScheduledEvent(
                    "account_maturity"
                ),
                time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT: (
                    SentinelScheduledEvent("notify_upcoming_maturity")
                ),
            }
        ]

        self.addCleanup(patch.stopall)
        return super().setUp()


class NewTimeDepositActivationHookTest(ActivationHookCommon):
    def setUp(self) -> None:
        patch_get_deposit_period_end_datetime = patch.object(
            time_deposit.deposit_period, "get_deposit_period_end_datetime"
        )
        self.mock_get_deposit_period_end_datetime = patch_get_deposit_period_end_datetime.start()
        self.mock_get_deposit_period_end_datetime.return_value = datetime.min

        patch_get_cooling_off_period_end_datetime = patch.object(
            time_deposit.cooling_off_period, "get_cooling_off_period_end_datetime"
        )
        self.mock_get_cooling_off_period_end_datetime = (
            patch_get_cooling_off_period_end_datetime.start()
        )
        self.mock_get_cooling_off_period_end_datetime.return_value = datetime.max

        patch_deposit_period_end_scheduled_events = patch.object(
            time_deposit.deposit_period, "scheduled_events"
        )
        self.mock_deposit_period_end_scheduled_events = (
            patch_deposit_period_end_scheduled_events.start()
        )
        self.mock_deposit_period_end_scheduled_events.return_value = {
            time_deposit.deposit_period.DEPOSIT_PERIOD_END_EVENT: SentinelScheduledEvent(
                "deposit_period_end"
            ),
        }

        patch_grace_period_end_scheduled_events = patch.object(
            time_deposit.grace_period, "scheduled_events"
        )
        self.mock_grace_period_end_scheduled_events = (
            patch_grace_period_end_scheduled_events.start()
        )
        self.mock_grace_period_end_scheduled_events.return_value = {
            time_deposit.grace_period.GRACE_PERIOD_END_EVENT: SentinelScheduledEvent(
                "grace_period_end"
            ),
        }

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_schedule_events_created(self):
        hook_result = time_deposit.activation_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(
            hook_result,
            ActivationHookResult(
                scheduled_events_return_value={
                    time_deposit.fixed_interest_accrual.ACCRUAL_EVENT: SentinelScheduledEvent(
                        "interest_accrual"
                    ),
                    time_deposit.interest_application.APPLICATION_EVENT: SentinelScheduledEvent(
                        "interest_application"
                    ),
                    time_deposit.deposit_period.DEPOSIT_PERIOD_END_EVENT: SentinelScheduledEvent(
                        "deposit_period_end"
                    ),
                    time_deposit.grace_period.GRACE_PERIOD_END_EVENT: SentinelScheduledEvent(
                        "end_of_time_schedule"
                    ),
                    time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT: SentinelScheduledEvent(
                        "account_maturity"
                    ),
                    time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT: SentinelScheduledEvent(  # noqa: E501
                        "notify_upcoming_maturity"
                    ),
                }
            ),
        )
        self.mock_interest_application_scheduled_events.assert_called_once_with(
            vault=sentinel.vault, reference_datetime=datetime.max
        )
        self.mock_create_end_of_time_schedule.assert_called_once_with(
            start_datetime=DEFAULT_DATETIME + relativedelta(days=1)
        )
        self.mock_deposit_period_end_scheduled_events.assert_called_once_with(vault=sentinel.vault)


class RenewedActivationHookTest(ActivationHookCommon):
    def setUp(self) -> None:
        super().setUp()
        patch_get_grace_period_end_datetime = patch.object(
            time_deposit.grace_period, "get_grace_period_end_datetime"
        )
        self.mock_get_grace_period_end_datetime = patch_get_grace_period_end_datetime.start()
        self.mock_get_grace_period_end_datetime.return_value = sentinel.grace_period_end_datetime
        self.mock_get_grace_period_parameter.return_value = 1

        patch_grace_period_end_scheduled_events = patch.object(
            time_deposit.grace_period, "scheduled_events"
        )
        self.mock_grace_period_end_scheduled_events = (
            patch_grace_period_end_scheduled_events.start()
        )
        self.mock_grace_period_end_scheduled_events.return_value = {
            time_deposit.grace_period.GRACE_PERIOD_END_EVENT: SentinelScheduledEvent(
                "grace_period_end"
            ),
        }

        self.addCleanup(patch.stopall)
        return

    def test_schedule_events_created(self):
        hook_result = time_deposit.activation_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(
            hook_result,
            ActivationHookResult(
                scheduled_events_return_value={
                    time_deposit.fixed_interest_accrual.ACCRUAL_EVENT: SentinelScheduledEvent(
                        "interest_accrual"
                    ),
                    time_deposit.interest_application.APPLICATION_EVENT: SentinelScheduledEvent(
                        "interest_application"
                    ),
                    time_deposit.deposit_period.DEPOSIT_PERIOD_END_EVENT: SentinelScheduledEvent(
                        "end_of_time_schedule"
                    ),
                    time_deposit.grace_period.GRACE_PERIOD_END_EVENT: SentinelScheduledEvent(
                        "grace_period_end"
                    ),
                    time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT: SentinelScheduledEvent(
                        "account_maturity"
                    ),
                    time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT: SentinelScheduledEvent(  # noqa: E501
                        "notify_upcoming_maturity"
                    ),
                }
            ),
        )
        self.mock_interest_application_scheduled_events.assert_called_once_with(
            vault=sentinel.vault, reference_datetime=sentinel.grace_period_end_datetime
        )
        self.mock_grace_period_end_scheduled_events.assert_called_once_with(vault=sentinel.vault)
        self.mock_create_end_of_time_schedule.assert_called_once_with(
            start_datetime=DEFAULT_DATETIME + relativedelta(days=1)
        )
