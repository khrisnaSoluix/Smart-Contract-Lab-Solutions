# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test.unit.test_time_deposit_common import TimeDepositTest

# features
import library.features.common.fetchers as fetchers
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PostingInstructionsDirective,
    ScheduledEventHookArguments,
    ScheduledEventHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelAccountNotificationDirective,
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelUpdateAccountEventTypeDirective,
)


class DummyEventTest(TimeDepositTest):
    def test_undefined_scheduled_event(self):
        # hook call
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type="UNDEFINED",
        )
        hook_result = time_deposit.scheduled_event_hook(sentinel.vault, hook_arguments)

        # assertions
        self.assertIsNone(hook_result)


@patch.object(time_deposit.fixed_interest_accrual, "accrue_interest")
class AccrualScheduledEventTest(TimeDepositTest):
    event_type = time_deposit.fixed_interest_accrual.ACCRUAL_EVENT

    def test_interest_accrual_with_instructions(
        self,
        mock_accrue_interest: MagicMock,
    ):
        mock_accrue_interest.return_value = [SentinelCustomInstruction("accrued_interest")]

        mock_vault = self.create_mock()
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=self.event_type
        )

        hook_result = time_deposit.scheduled_event_hook(mock_vault, hook_arguments)
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("accrued_interest"),
                    ],
                    value_datetime=DEFAULT_DATETIME,
                    client_batch_id="MOCK_HOOK_ACCRUE_INTEREST",
                )
            ]
        )

        self.assertEqual(hook_result, expected_result)
        mock_accrue_interest.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            account_type=time_deposit.PRODUCT_NAME,
        )

    def test_none_returned_when_no_pi_directives(
        self,
        mock_accrue_interest: MagicMock,
    ):
        mock_accrue_interest.return_value = []

        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=self.event_type
        )
        result = time_deposit.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertIsNone(result)


class DepositPeriodEndTest(TimeDepositTest):
    event_type = time_deposit.deposit_period.DEPOSIT_PERIOD_END_EVENT

    def setUp(self) -> None:
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "effective_observation"
                )
            },
        )

        self.hook_arguments = ScheduledEventHookArguments(
            event_type=self.event_type,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.expected_test_notification = [SentinelAccountNotificationDirective("closure")]
        patch_handle_account_closure_notification = patch.object(
            time_deposit.deposit_period, "handle_account_closure_notification"
        )
        self.mock_handle_account_closure_notification = (
            patch_handle_account_closure_notification.start()
        )
        self.mock_handle_account_closure_notification.return_value = self.expected_test_notification

        patch_get_parameter = patch.object(time_deposit.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": self.default_denom}
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_deposit_period_notification_is_returned(self):
        expected_result = ScheduledEventHookResult(
            account_notification_directives=self.expected_test_notification
        )
        result = time_deposit.scheduled_event_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(result, expected_result)
        self.mock_handle_account_closure_notification.assert_called_once_with(
            product_name="TIME_DEPOSIT",
            balances=sentinel.balances_effective_observation,
            denomination=self.default_denom,
            account_id=self.mock_vault.account_id,
            effective_datetime=DEFAULT_DATETIME,
        )

    def test_no_notification_is_returned_when_no_closure(self):
        self.mock_handle_account_closure_notification.return_value = []

        hook_result = time_deposit.scheduled_event_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertIsNone(hook_result)
        self.mock_handle_account_closure_notification.assert_called_once_with(
            product_name="TIME_DEPOSIT",
            balances=sentinel.balances_effective_observation,
            denomination=self.default_denom,
            account_id=self.mock_vault.account_id,
            effective_datetime=DEFAULT_DATETIME,
        )


class InterestApplicationEventTest(TimeDepositTest):
    event_type = time_deposit.interest_application.APPLICATION_EVENT

    def setUp(self) -> None:
        self.mock_vault = self.create_mock()

        self.hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=self.event_type
        )

        patch_apply_interest = patch.object(time_deposit.interest_application, "apply_interest")
        self.mock_apply_interest = patch_apply_interest.start()
        self.interest_application_instructions = [SentinelCustomInstruction("interest_application")]
        self.mock_apply_interest.return_value = self.interest_application_instructions

        patch_update_next_schedule_execution = patch.object(
            time_deposit.interest_application, "update_next_schedule_execution"
        )
        self.mock_update_next_schedule_execution = patch_update_next_schedule_execution.start()
        self.interest_application_update_event = SentinelUpdateAccountEventTypeDirective(
            "interest_application"
        )
        self.mock_update_next_schedule_execution.return_value = (
            self.interest_application_update_event
        )

        patch_get_parameter = patch.object(time_deposit.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denom,
                time_deposit.interest_application.PARAM_APPLICATION_PRECISION: "2",
            }
        )

        patch_sum_balances = patch.object(time_deposit.utils, "sum_balances")
        self.mock_sum_balances = patch_sum_balances.start()
        self.mock_sum_balances.side_effect = [Decimal("0"), Decimal("0")]

        return super().setUp()

    def test_instructions_and_update_event_directives_returned(self):
        # construct expected result
        expected_result = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=self.interest_application_instructions,  # type: ignore
                    value_datetime=DEFAULT_DATETIME,
                    client_batch_id="MOCK_HOOK_APPLY_INTEREST",
                )
            ],
            update_account_event_type_directives=[self.interest_application_update_event],
        )

        # run function
        result = time_deposit.scheduled_event_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )
        self.assertEqual(result, expected_result)

    def test_none_returned_if_no_instructions_or_update_event_directives(self):
        # construct mocks
        self.mock_apply_interest.return_value = []
        self.mock_update_next_schedule_execution.return_value = None

        # run function
        result = time_deposit.scheduled_event_hook(self.mock_vault, self.hook_arguments)
        self.assertIsNone(result)


class AccountMaturityNotificationTest(TimeDepositTest):
    event_type_maturity = time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT

    def setUp(self) -> None:
        self.mock_vault = self.create_mock()

        self.hook_arguments = ScheduledEventHookArguments(
            event_type=self.event_type_maturity,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.expected_test_notification = [SentinelAccountNotificationDirective("account_maturity")]
        self.expected_account_update = [
            SentinelUpdateAccountEventTypeDirective("interest_accrual"),
            SentinelUpdateAccountEventTypeDirective("interest_application"),
        ]

        # handle account maturity notification
        patch_handle_account_maturity_event = patch.object(
            time_deposit.deposit_maturity, "handle_account_maturity_event"
        )
        self.mock_handle_account_maturity_event = patch_handle_account_maturity_event.start()
        self.mock_handle_account_maturity_event.return_value = (
            self.expected_test_notification,
            self.expected_account_update,
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_handle_notification_and_account_update_at_account_maturity(self):
        expected_result = ScheduledEventHookResult(
            account_notification_directives=self.expected_test_notification,
            update_account_event_type_directives=self.expected_account_update,
        )

        result = time_deposit.scheduled_event_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(result, expected_result)
        self.mock_handle_account_maturity_event.assert_called_once_with(
            product_name="TIME_DEPOSIT",
            account_id=self.mock_vault.account_id,
            effective_datetime=DEFAULT_DATETIME,
            schedules_to_skip_indefinitely=[
                time_deposit.fixed_interest_accrual.ACCRUAL_EVENT,
                time_deposit.interest_application.APPLICATION_EVENT,
            ],
        )

    def test_handle_no_notification_and_no_event_update_at_account_maturity(self):
        self.mock_handle_account_maturity_event.return_value = ([], [])

        result = time_deposit.scheduled_event_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertIsNone(result)
        self.mock_handle_account_maturity_event.assert_called_once_with(
            product_name="TIME_DEPOSIT",
            account_id=self.mock_vault.account_id,
            effective_datetime=DEFAULT_DATETIME,
            schedules_to_skip_indefinitely=[
                time_deposit.fixed_interest_accrual.ACCRUAL_EVENT,
                time_deposit.interest_application.APPLICATION_EVENT,
            ],
        )


class AccountMaturityNotifyTest(TimeDepositTest):
    event_type_maturity_notice = time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT

    def setUp(self) -> None:
        self.mock_vault = self.create_mock()

        self.hook_arguments = ScheduledEventHookArguments(
            event_type=self.event_type_maturity_notice,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.expected_test_notification = [SentinelAccountNotificationDirective("account_maturity")]
        self.expected_account_update = [SentinelUpdateAccountEventTypeDirective("account_maturity")]

        # handle account maturity notification
        patch_handle_notify_upcoming_maturity_event = patch.object(
            time_deposit.deposit_maturity, "handle_notify_upcoming_maturity_event"
        )
        self.mock_handle_notify_upcoming_maturity_event = (
            patch_handle_notify_upcoming_maturity_event.start()
        )
        self.mock_handle_notify_upcoming_maturity_event.return_value = (
            self.expected_test_notification,
            self.expected_account_update,
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_notify_upcoming_maturity_and_maturity_account_update_is_present(self):
        expected_result = ScheduledEventHookResult(
            account_notification_directives=self.expected_test_notification,
            update_account_event_type_directives=self.expected_account_update,
        )

        result = time_deposit.scheduled_event_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(result, expected_result)
        self.mock_handle_notify_upcoming_maturity_event.assert_called_once_with(
            vault=self.mock_vault,
            product_name="TIME_DEPOSIT",
        )

    def test_handle_no_notification_and_no_event_update_before_account_maturity(self):
        self.mock_handle_notify_upcoming_maturity_event.return_value = ([], [])

        result = time_deposit.scheduled_event_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertIsNone(result)
        self.mock_handle_notify_upcoming_maturity_event.assert_called_once_with(
            vault=self.mock_vault,
            product_name="TIME_DEPOSIT",
        )


class GracePeriodEndTest(TimeDepositTest):
    event_type = time_deposit.grace_period.GRACE_PERIOD_END_EVENT

    def setUp(self) -> None:
        self.hook_arguments = ScheduledEventHookArguments(
            event_type=self.event_type,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.expected_test_notification = [SentinelAccountNotificationDirective("closure")]
        patch_handle_account_closure_notification = patch.object(
            time_deposit.grace_period, "handle_account_closure_notification"
        )
        self.mock_handle_account_closure_notification = (
            patch_handle_account_closure_notification.start()
        )
        self.mock_handle_account_closure_notification.return_value = self.expected_test_notification

        patch_get_parameter = patch.object(time_deposit.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": self.default_denom}
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_grace_period_notification_is_returned(self):
        expected_result = ScheduledEventHookResult(
            account_notification_directives=self.expected_test_notification
        )
        result = time_deposit.scheduled_event_hook(
            vault=sentinel.vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(result, expected_result)
        self.mock_handle_account_closure_notification.assert_called_once_with(
            vault=sentinel.vault,
            product_name="TIME_DEPOSIT",
            denomination=self.default_denom,
            effective_datetime=DEFAULT_DATETIME,
        )

    def test_no_notification_is_returned_when_no_closure(self):
        self.mock_handle_account_closure_notification.return_value = []

        hook_result = time_deposit.scheduled_event_hook(
            vault=sentinel.vault, hook_arguments=self.hook_arguments
        )

        self.assertIsNone(hook_result)
        self.mock_handle_account_closure_notification.assert_called_once_with(
            vault=sentinel.vault,
            product_name="TIME_DEPOSIT",
            denomination=self.default_denom,
            effective_datetime=DEFAULT_DATETIME,
        )
