# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# library
from library.bnpl.contracts.template import bnpl
from library.bnpl.test.unit.test_bnpl_common import BNPLTest

# contracts api
from contracts_api import AccountNotificationDirective, ScheduledEventHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PostingInstructionsDirective,
    ScheduledEventHookResult,
    ScheduleExpression,
    UpdateAccountEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelScheduleExpression,
    SentinelUpdateAccountEventTypeDirective,
)


class InvalidEventTypeScheduleEventHookTest(BNPLTest):
    def test_none_result(self):
        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type="invalid_event_type",
        )
        result = bnpl.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args)
        # validate results
        self.assertIsNone(result)


class DueAmountCalculationScheduledEventHookTest(BNPLTest):
    @patch.object(bnpl.due_amount_calculation, "schedule_logic")
    @patch.object(bnpl, "_schedule_fortnightly_repayment_frequency")
    def test_schedule_due_amount_calculation_on_empty_ci(
        self,
        mock_schedule_fortnightly_repayment_frequency: MagicMock,
        mock_due_schedule_logic: MagicMock,
    ):
        # construct mocks
        mock_due_schedule_logic.return_value = []
        mock_schedule_fortnightly_repayment_frequency.return_value = []

        # construct expected result
        expected = None

        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
        )
        res = bnpl.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args)

        # validate results
        self.assertEqual(expected, res)
        mock_schedule_fortnightly_repayment_frequency.assert_called_once_with(
            vault=sentinel.vault, hook_arguments=hook_args
        )
        mock_due_schedule_logic.assert_called_once_with(
            vault=sentinel.vault,
            hook_arguments=hook_args,
            account_type=bnpl.PRODUCT_NAME,
            amortisation_feature=bnpl.declining_principal.AmortisationFeature,
        )

    @patch.object(bnpl.due_amount_calculation, "schedule_logic")
    @patch.object(bnpl, "_schedule_fortnightly_repayment_frequency")
    def test_schedule_due_amount_calc_with_ci_and_update_event_directive(
        self,
        mock_schedule_fortnightly_repayment_frequency: MagicMock,
        mock_due_schedule_logic: MagicMock,
    ):
        # expected values
        due_ci = SentinelCustomInstruction("due_amount_calculation")
        event_type = bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
        update_account_event_type_directive = SentinelUpdateAccountEventTypeDirective("directive")
        # construct mocks
        mock_due_schedule_logic.return_value = [due_ci]
        mock_schedule_fortnightly_repayment_frequency.return_value = [
            update_account_event_type_directive
        ]
        mock_vault = self.create_mock()

        # construct expected result
        expected = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[due_ci],
                    client_batch_id=f"{bnpl.PRODUCT_NAME}_{event_type}_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            update_account_event_type_directives=[update_account_event_type_directive],
        )
        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=event_type,
        )
        res = bnpl.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate results
        self.assertEqual(expected, res)
        mock_due_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            account_type=bnpl.PRODUCT_NAME,
            amortisation_feature=bnpl.declining_principal.AmortisationFeature,
        )
        mock_schedule_fortnightly_repayment_frequency.assert_called_once_with(
            vault=mock_vault, hook_arguments=hook_args
        )

    @patch.object(bnpl.config_repayment_frequency, "get_next_fortnightly_schedule_expression")
    @patch.object(bnpl.config_repayment_frequency, "get_repayment_frequency_parameter")
    def test_schedule_fortnightly_repayment_frequency(
        self,
        mock_get_repayment_frequency_parameter: MagicMock,
        mock_get_next_fortnightly_schedule_expression: MagicMock,
    ):
        # expected values
        sentinel_schedule = SentinelScheduleExpression("dummy_expression")
        event_type = bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
        fortnightly = bnpl.config_repayment_frequency.FORTNIGHTLY
        update_account_event_type_directive = [
            UpdateAccountEventTypeDirective(
                event_type=bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                expression=sentinel_schedule,
            ),
        ]

        # construct mocks
        mock_get_repayment_frequency_parameter.return_value = fortnightly
        mock_get_next_fortnightly_schedule_expression.return_value = sentinel_schedule
        mock_vault = self.create_mock()

        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=event_type,
        )
        res = bnpl._schedule_fortnightly_repayment_frequency(
            vault=mock_vault, hook_arguments=hook_args
        )

        # validate results
        self.assertEqual(update_account_event_type_directive, res)
        mock_get_next_fortnightly_schedule_expression.assert_called_once_with(
            effective_date=DEFAULT_DATETIME
        )
        mock_get_repayment_frequency_parameter.assert_called_once_with(vault=mock_vault)

    @patch.object(bnpl.config_repayment_frequency, "get_repayment_frequency_parameter")
    def test_not_schedule_fortnightly_repayment_frequency(
        self,
        mock_get_repayment_frequency_parameter: MagicMock,
    ):
        # expected values
        event_type = bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
        monthly = bnpl.config_repayment_frequency.MONTHLY
        update_account_event_type_directive: list[UpdateAccountEventTypeDirective] = []

        # construct mocks
        mock_get_repayment_frequency_parameter.return_value = monthly
        mock_vault = self.create_mock()

        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=event_type,
        )
        res = bnpl._schedule_fortnightly_repayment_frequency(
            vault=mock_vault, hook_arguments=hook_args
        )

        # validate results
        self.assertEqual(update_account_event_type_directive, res)
        mock_get_repayment_frequency_parameter.assert_called_once_with(vault=mock_vault)


class DueAmountNotificationScheduledEventHookTest(BNPLTest):
    @patch.object(bnpl, "_get_repayment_notification")
    @patch.object(
        bnpl.due_amount_notification,
        "get_next_due_amount_notification_datetime",
    )
    @patch.object(bnpl.utils, "get_schedule_expression_from_parameters")
    @patch.object(bnpl.config_repayment_frequency, "get_repayment_frequency_parameter")
    def test_only_update_event_type_result_on_empty_account_notification_directive(
        self,
        mock_get_repayment_frequency_parameter: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_next_due_amount_notification_datetime: MagicMock,
        mock_get_repayment_notification: MagicMock,
    ):
        # expected values
        expression = ScheduleExpression(
            hour=str("0"),
            minute=str("0"),
            second=str("0"),
            day=None,
            month=None,
            year=None,
            day_of_week=None,
        )
        repayment_frequency = bnpl.config_repayment_frequency.MONTHLY
        # construct mocks
        mock_vault = self.create_mock()
        mock_get_repayment_notification.return_value = []
        mock_get_repayment_frequency_parameter.return_value = repayment_frequency
        mock_get_schedule_expression_from_parameters.return_value = expression
        mock_get_next_due_amount_notification_datetime.return_value = datetime(
            2019, 1, 1, tzinfo=ZoneInfo("UTC")
        )

        # construct expected result
        expected = ScheduledEventHookResult(
            update_account_event_type_directives=[
                UpdateAccountEventTypeDirective(
                    event_type=bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT,
                    expression=expression,
                )
            ]
        )

        # validate results
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT,
        )
        self.assertEquals(
            bnpl.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args), expected
        )

    @patch.object(bnpl, "_get_repayment_notification")
    @patch.object(
        bnpl.due_amount_notification,
        "get_next_due_amount_notification_datetime",
    )
    @patch.object(bnpl.utils, "get_schedule_expression_from_parameters")
    @patch.object(bnpl.config_repayment_frequency, "get_repayment_frequency_parameter")
    def test_schedule_due_amount_notification(
        self,
        mock_get_repayment_frequency_parameter: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_next_due_amount_notification_datetime: MagicMock,
        mock_get_repayment_notification: MagicMock,
    ):
        # expected values
        due_amount_notification_datetime = DEFAULT_DATETIME
        next_due_amount_notification_datetime = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        mock_vault = self.create_mock()
        expression = ScheduleExpression(
            hour=str("0"),
            minute=str("0"),
            second=str("0"),
            day=None,
            month=None,
            year=None,
            day_of_week=None,
        )
        due_amount_notifications = [
            AccountNotificationDirective(
                notification_type=bnpl.due_amount_notification.notification_type(bnpl.PRODUCT_NAME),
                notification_details={"account_id": str(mock_vault.account_id)},
            )
        ]
        repayment_frequency = bnpl.config_repayment_frequency.MONTHLY

        # construct mocks
        mock_get_schedule_expression_from_parameters.return_value = expression
        mock_get_next_due_amount_notification_datetime.return_value = (
            next_due_amount_notification_datetime
        )

        mock_vault = self.create_mock()
        mock_get_repayment_notification.return_value = due_amount_notifications
        mock_get_repayment_frequency_parameter.return_value = repayment_frequency

        # construct expected result
        expected = ScheduledEventHookResult(
            account_notification_directives=due_amount_notifications,
            update_account_event_type_directives=[
                UpdateAccountEventTypeDirective(
                    event_type=bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT,
                    expression=expression,
                )
            ],
        )

        # validate results
        hook_args = ScheduledEventHookArguments(
            effective_datetime=due_amount_notification_datetime,
            event_type=bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT,
        )
        self.assertEquals(
            bnpl.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args), expected
        )
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix=bnpl.due_amount_notification.DUE_AMOUNT_NOTIFICATION_PREFIX,
            day=next_due_amount_notification_datetime.day,
            month=next_due_amount_notification_datetime.month,
            year=next_due_amount_notification_datetime.year,
        )
        mock_get_next_due_amount_notification_datetime.assert_called_once_with(
            vault=mock_vault,
            current_due_amount_notification_datetime=DEFAULT_DATETIME,
            repayment_frequency_delta=bnpl.config_repayment_frequency.FREQUENCY_MAP[
                bnpl.config_repayment_frequency.MONTHLY
            ],
        )
        mock_get_repayment_notification.assert_called_once_with(
            vault=mock_vault, due_amount_notification_datetime=due_amount_notification_datetime
        )

    @patch.object(bnpl.declining_principal, "term_details")
    @patch.object(bnpl.overdue, "get_overdue_datetime")
    @patch.object(bnpl.due_amount_calculation, "get_principal")
    @patch.object(bnpl.due_amount_calculation, "calculate_due_principal")
    @patch.object(bnpl.due_amount_calculation, "get_emi")
    @patch.object(bnpl.due_amount_notification, "get_notification_period_parameter")
    @patch.object(bnpl.overdue, "get_repayment_period_parameter")
    @patch.object(bnpl.common_parameters, "get_denomination_parameter")
    @patch.object(bnpl.due_amount_notification, "schedule_logic")
    def test_get_repayment_notification_is_final_due_event_false(
        self,
        mock_due_amount_notification_schedule_logic: MagicMock,
        mock_get_denomination_parameter: MagicMock,
        mock_get_repayment_period_parameter: MagicMock,
        mock_get_notification_period_parameter: MagicMock,
        mock_get_emi: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_get_principal: MagicMock,
        mock_get_overdue_datetime: MagicMock,
        mock_declining_principal_term_details: MagicMock,
    ):
        # expected values
        repayment_period = 2
        notification_period = 3
        mock_balances_observation = SentinelBalancesObservation("dummy_balances_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: mock_balances_observation
            }
        )
        denomination = sentinel.denomination
        principal = sentinel.principal
        due_principal = sentinel.due_principal
        emi = sentinel.emi
        due_amount_notification_datetime = DEFAULT_DATETIME
        overdue_datetime = sentinel.overdue_datetime
        balances = sentinel.balances_dummy_balances_observation
        due_amount_notifications = [sentinel.AccountNotificationDirective]

        # construct mocks
        mock_declining_principal_term_details.return_value = (0, 2)
        mock_due_amount_notification_schedule_logic.return_value = due_amount_notifications
        mock_get_denomination_parameter.return_value = denomination
        mock_get_notification_period_parameter.return_value = notification_period
        mock_get_repayment_period_parameter.return_value = repayment_period
        mock_get_emi.return_value = emi
        mock_calculate_due_principal.return_value = due_principal
        mock_get_principal.return_value = principal
        mock_get_overdue_datetime.return_value = overdue_datetime

        # validate results
        self.assertEquals(
            bnpl._get_repayment_notification(
                vault=mock_vault, due_amount_notification_datetime=due_amount_notification_datetime
            ),
            due_amount_notifications,
        )
        mock_get_emi.assert_called_once_with(balances=balances, denomination=denomination)
        mock_calculate_due_principal.assert_called_with(
            remaining_principal=principal,
            emi_interest_to_apply=Decimal("0"),
            emi=emi,
            is_final_due_event=False,
        )
        mock_get_principal.assert_called_once_with(balances=balances, denomination=denomination)
        mock_get_overdue_datetime.assert_called_once_with(
            due_amount_notification_datetime=due_amount_notification_datetime,
            repayment_period=int(repayment_period),
            notification_period=int(notification_period),
        )
        mock_due_amount_notification_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            product_name=bnpl.PRODUCT_NAME,
            overdue_datetime=overdue_datetime,
            due_interest=Decimal("0"),
            due_principal=due_principal,
        )

    @patch.object(bnpl.declining_principal, "term_details")
    @patch.object(bnpl.overdue, "get_overdue_datetime")
    @patch.object(bnpl.due_amount_calculation, "get_principal")
    @patch.object(bnpl.due_amount_calculation, "calculate_due_principal")
    @patch.object(bnpl.due_amount_calculation, "get_emi")
    @patch.object(bnpl.due_amount_notification, "get_notification_period_parameter")
    @patch.object(bnpl.overdue, "get_repayment_period_parameter")
    @patch.object(bnpl.common_parameters, "get_denomination_parameter")
    @patch.object(bnpl.due_amount_notification, "schedule_logic")
    def test_get_repayment_notification_is_final_due_event_true(
        self,
        mock_due_amount_notification_schedule_logic: MagicMock,
        mock_get_denomination_parameter: MagicMock,
        mock_get_repayment_period_parameter: MagicMock,
        mock_get_notification_period_parameter: MagicMock,
        mock_get_emi: MagicMock,
        mock_calculate_due_principal: MagicMock,
        mock_get_principal: MagicMock,
        mock_get_overdue_datetime: MagicMock,
        mock_declining_principal_term_details: MagicMock,
    ):
        # expected values
        repayment_period = 2
        notification_period = 3
        mock_balances_observation = SentinelBalancesObservation("dummy_balances_observation")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                bnpl.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: mock_balances_observation
            }
        )
        denomination = sentinel.denomination
        principal = sentinel.principal
        due_principal = sentinel.due_principal
        emi = sentinel.emi
        due_amount_notification_datetime = DEFAULT_DATETIME
        overdue_datetime = sentinel.overdue_datetime
        balances = sentinel.balances_dummy_balances_observation
        due_amount_notifications = [sentinel.AccountNotificationDirective]

        # construct mocks
        mock_declining_principal_term_details.return_value = (0, 1)
        mock_due_amount_notification_schedule_logic.return_value = due_amount_notifications
        mock_get_denomination_parameter.return_value = denomination
        mock_get_notification_period_parameter.return_value = notification_period
        mock_get_repayment_period_parameter.return_value = repayment_period
        mock_get_emi.return_value = emi
        mock_calculate_due_principal.return_value = due_principal
        mock_get_principal.return_value = principal
        mock_get_overdue_datetime.return_value = overdue_datetime

        # validate results
        self.assertEquals(
            bnpl._get_repayment_notification(
                vault=mock_vault, due_amount_notification_datetime=due_amount_notification_datetime
            ),
            due_amount_notifications,
        )
        mock_get_emi.assert_called_once_with(balances=balances, denomination=denomination)
        mock_calculate_due_principal.assert_called_with(
            remaining_principal=principal,
            emi_interest_to_apply=Decimal("0"),
            emi=emi,
            is_final_due_event=True,
        )
        mock_get_principal.assert_called_once_with(balances=balances, denomination=denomination)
        mock_get_overdue_datetime.assert_called_once_with(
            due_amount_notification_datetime=due_amount_notification_datetime,
            repayment_period=int(repayment_period),
            notification_period=int(notification_period),
        )
        mock_due_amount_notification_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            product_name=bnpl.PRODUCT_NAME,
            overdue_datetime=overdue_datetime,
            due_interest=Decimal("0"),
            due_principal=due_principal,
        )


class OverdueCheckScheduledEventHookTest(BNPLTest):
    @patch.object(bnpl.delinquency, "get_grace_period_parameter")
    @patch.object(bnpl.late_repayment, "get_late_repayment_fee_parameter")
    @patch.object(bnpl.overdue, "schedule_logic")
    @patch.object(bnpl, "_schedule_overdue_check_event")
    def test_schedule_overdue_check_on_empty_ci(
        self,
        mock_schedule_overdue_check_event: MagicMock,
        mock_overdue_schedule_logic: MagicMock,
        mock_get_late_repayment_fee_parameter: MagicMock,
        mock_get_grace_period_parameter: MagicMock,
    ):
        # expected values
        product_name = "product_a"
        effective_datetime = DEFAULT_DATETIME
        sentinel_schedule = SentinelScheduleExpression("dummy_expression")
        late_repayment_fee = Decimal("25")
        grace_period = 1

        # construct expected result
        expected_notification_details = {
            sentinel.notification_details_key: sentinel.notification_details_value
        }
        expected_notifications: list[AccountNotificationDirective] = [
            AccountNotificationDirective(
                notification_type=bnpl.overdue.notification_type(product_name),
                notification_details=expected_notification_details,
            )
        ]
        expected_update_account_event_type = [
            UpdateAccountEventTypeDirective(
                event_type=bnpl.overdue.CHECK_OVERDUE_EVENT,
                expression=sentinel_schedule,
            ),
        ]
        expected = ScheduledEventHookResult(
            update_account_event_type_directives=[*expected_update_account_event_type],
            account_notification_directives=expected_notifications,
        )

        # construct mocks
        mock_get_grace_period_parameter.return_value = grace_period
        mock_get_late_repayment_fee_parameter.return_value = late_repayment_fee
        mock_overdue_schedule_logic.return_value = [], expected_notifications
        mock_schedule_overdue_check_event.return_value = expected_update_account_event_type
        mock_vault = self.create_mock()

        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=effective_datetime,
            event_type=bnpl.overdue.CHECK_OVERDUE_EVENT,
        )
        res = bnpl.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate results
        self.assertEqual(expected, res)
        mock_overdue_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            account_type=bnpl.PRODUCT_NAME,
            late_repayment_fee=late_repayment_fee,
        )
        mock_schedule_overdue_check_event.assert_called_once_with(
            vault=mock_vault, effective_datetime=effective_datetime
        )
        mock_get_late_repayment_fee_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_grace_period_parameter.assert_called_once_with(vault=mock_vault)

    @patch.object(bnpl.delinquency, "get_grace_period_parameter")
    @patch.object(bnpl.late_repayment, "get_late_repayment_fee_parameter")
    @patch.object(bnpl.overdue, "schedule_logic")
    @patch.object(bnpl, "_schedule_overdue_check_event")
    def test_schedule_overdue_check(
        self,
        mock_schedule_overdue_check_event: MagicMock,
        mock_overdue_schedule_logic: MagicMock,
        mock_get_late_repayment_fee_parameter: MagicMock,
        mock_get_grace_period_parameter: MagicMock,
    ):
        # expected values
        product_name = "product_a"
        sentinel_schedule = SentinelScheduleExpression("dummy_expression")
        overdue_ci = SentinelCustomInstruction("dummy_overdue_ci")
        late_repayment_fee = Decimal("25")
        grace_period = 1
        effective_datetime = DEFAULT_DATETIME
        event_type = bnpl.overdue.CHECK_OVERDUE_EVENT

        # construct expected result
        expected_update_account_event_type = [
            UpdateAccountEventTypeDirective(
                event_type=event_type,
                expression=sentinel_schedule,
            )
        ]
        expected_notification_details = {
            sentinel.notification_details_key: sentinel.notification_details_value
        }
        expected_notifications: list[AccountNotificationDirective] = [
            AccountNotificationDirective(
                notification_type=bnpl.overdue.notification_type(product_name),
                notification_details=expected_notification_details,
            )
        ]
        expected = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[overdue_ci],
                    client_batch_id=f"{bnpl.PRODUCT_NAME}_{event_type}_MOCK_HOOK",
                    value_datetime=effective_datetime,
                ),
            ],
            update_account_event_type_directives=[*expected_update_account_event_type],
            account_notification_directives=expected_notifications,
        )

        # construct mocks
        mock_overdue_schedule_logic.return_value = [overdue_ci], expected_notifications
        mock_get_grace_period_parameter.return_value = grace_period
        mock_get_late_repayment_fee_parameter.return_value = late_repayment_fee
        mock_schedule_overdue_check_event.return_value = expected_update_account_event_type
        mock_vault = self.create_mock()

        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=effective_datetime,
            event_type=bnpl.overdue.CHECK_OVERDUE_EVENT,
        )
        res = bnpl.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate results
        self.assertEqual(expected, res)
        mock_overdue_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            account_type=bnpl.PRODUCT_NAME,
            late_repayment_fee=late_repayment_fee,
        )
        mock_schedule_overdue_check_event.assert_called_once_with(
            vault=mock_vault, effective_datetime=effective_datetime
        )
        mock_get_late_repayment_fee_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_grace_period_parameter.assert_called_once_with(vault=mock_vault)

    @patch.object(bnpl.delinquency, "get_grace_period_parameter")
    @patch.object(bnpl.late_repayment, "get_late_repayment_fee_parameter")
    @patch.object(bnpl.overdue, "schedule_logic")
    @patch.object(bnpl, "_schedule_overdue_check_event")
    @patch.object(bnpl.late_repayment, "schedule_logic")
    @patch.object(bnpl.common_parameters, "get_denomination_parameter")
    def test_schedule_overdue_check_with_no_grace_period(
        self,
        mock_get_denomination_parameter: MagicMock,
        mock_late_repayment_schedule_logic: MagicMock,
        mock_schedule_overdue_check_event: MagicMock,
        mock_overdue_schedule_logic: MagicMock,
        mock_get_late_repayment_fee_parameter: MagicMock,
        mock_get_grace_period_parameter: MagicMock,
    ):
        # expected values
        product_name = "product_a"
        sentinel_schedule = SentinelScheduleExpression("dummy_expression")
        overdue_ci = SentinelCustomInstruction("dummy_overdue_ci")
        late_repayment_fee = Decimal("25")
        grace_period = 0
        effective_datetime = DEFAULT_DATETIME
        event_type = bnpl.overdue.CHECK_OVERDUE_EVENT
        late_repayment_ci = SentinelCustomInstruction("dummy_late_repayment_ci")
        denomination = sentinel.denomination

        # construct expected result
        expected_update_account_event_type = [
            UpdateAccountEventTypeDirective(
                event_type=event_type,
                expression=sentinel_schedule,
            )
        ]
        expected_notification_details = {
            sentinel.notification_details_key: sentinel.notification_details_value
        }
        expected_notifications: list[AccountNotificationDirective] = [
            AccountNotificationDirective(
                notification_type=bnpl.overdue.notification_type(product_name),
                notification_details=expected_notification_details,
            )
        ]
        expected = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[overdue_ci, late_repayment_ci],
                    client_batch_id=f"{bnpl.PRODUCT_NAME}_{event_type}_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                ),
            ],
            update_account_event_type_directives=[*expected_update_account_event_type],
            account_notification_directives=expected_notifications,
        )

        # construct mocks
        mock_overdue_schedule_logic.return_value = [overdue_ci], expected_notifications
        mock_get_grace_period_parameter.return_value = grace_period
        mock_get_late_repayment_fee_parameter.return_value = late_repayment_fee
        mock_get_denomination_parameter.return_value = denomination
        mock_schedule_overdue_check_event.return_value = expected_update_account_event_type
        mock_late_repayment_schedule_logic.return_value = [late_repayment_ci]
        mock_vault = self.create_mock()

        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=effective_datetime,
            event_type=bnpl.overdue.CHECK_OVERDUE_EVENT,
        )
        res = bnpl.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate results
        self.assertEqual(expected, res)
        mock_overdue_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            account_type=bnpl.PRODUCT_NAME,
            late_repayment_fee=late_repayment_fee,
        )
        mock_schedule_overdue_check_event.assert_called_once_with(
            vault=mock_vault, effective_datetime=effective_datetime
        )
        mock_get_late_repayment_fee_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_grace_period_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_denomination_parameter.assert_called_once_with(vault=mock_vault)
        mock_late_repayment_schedule_logic.assert_called_once_with(
            vault=mock_vault, hook_arguments=hook_args, denomination=sentinel.denomination
        )

    @patch.object(bnpl.overdue, "get_repayment_period_parameter")
    @patch.object(bnpl, "_get_repayment_frequency_delta")
    @patch.object(bnpl.utils, "get_schedule_expression_from_parameters")
    def test_schedule_overdue_check_event_start_of_month(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_repayment_frequency_delta: MagicMock,
        mock_get_repayment_period_parameter: MagicMock,
    ):
        # expected values
        repayment_period = 2
        repayment_frequency_delta = bnpl.config_repayment_frequency.FREQUENCY_MAP[
            bnpl.config_repayment_frequency.MONTHLY
        ]
        sentinel_schedule = SentinelScheduleExpression("dummy_expression")
        effective_datetime = DEFAULT_DATETIME

        # construct expected result
        expected = [
            UpdateAccountEventTypeDirective(
                event_type=bnpl.overdue.CHECK_OVERDUE_EVENT,
                expression=sentinel_schedule,
            ),
        ]

        # construct mocks
        mock_get_repayment_period_parameter.return_value = repayment_period
        mock_get_repayment_frequency_delta.return_value = repayment_frequency_delta
        mock_get_schedule_expression_from_parameters.return_value = sentinel_schedule
        mock_vault = self.create_mock()

        # run function
        res = bnpl._schedule_overdue_check_event(
            vault=mock_vault, effective_datetime=effective_datetime
        )

        # validate results
        self.assertEqual(expected, res)
        mock_get_repayment_period_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_repayment_frequency_delta.assert_called_once_with(vault=mock_vault)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix=bnpl.overdue.CHECK_OVERDUE_PREFIX,
            # (effective datetime) Jan. 1, 2019 - (repayment period) 2 days = Dec. 30 2018
            # Dec. 30 2018 + (frequency) 1 month = Jan 30, 2019
            # Jan 30, 2019 + (repayment period) 2 = Feb 1, 2019
            day=1,
            month=2,
            year=2019,
        )

    @patch.object(bnpl.overdue, "get_repayment_period_parameter")
    @patch.object(bnpl, "_get_repayment_frequency_delta")
    @patch.object(bnpl.utils, "get_schedule_expression_from_parameters")
    def test_schedule_overdue_check_event_end_of_month(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_repayment_frequency_delta: MagicMock,
        mock_get_repayment_period_parameter: MagicMock,
    ):
        # expected values
        repayment_period = 2
        repayment_frequency_delta = bnpl.config_repayment_frequency.FREQUENCY_MAP[
            bnpl.config_repayment_frequency.MONTHLY
        ]
        sentinel_schedule = SentinelScheduleExpression("dummy_expression")
        effective_datetime = datetime(2019, 1, 31, tzinfo=ZoneInfo("UTC"))

        # construct expected result
        expected = [
            UpdateAccountEventTypeDirective(
                event_type=bnpl.overdue.CHECK_OVERDUE_EVENT,
                expression=sentinel_schedule,
            ),
        ]

        # construct mocks
        mock_get_repayment_period_parameter.return_value = repayment_period
        mock_get_repayment_frequency_delta.return_value = repayment_frequency_delta
        mock_get_schedule_expression_from_parameters.return_value = sentinel_schedule
        mock_vault = self.create_mock()

        # run function
        res = bnpl._schedule_overdue_check_event(
            vault=mock_vault, effective_datetime=effective_datetime
        )

        # validate results
        self.assertEqual(expected, res)
        mock_get_repayment_period_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_repayment_frequency_delta.assert_called_once_with(vault=mock_vault)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix=bnpl.overdue.CHECK_OVERDUE_PREFIX,
            # (effective datetime) Jan. 31, 2019 - (repayment period) 2 days = Jan. 29 2019
            # Jan. 29 2019 + (frequency) 1 month = Feb 28, 2019
            # Feb 28, 2019 + (repayment period) 2 = March 2, 2019
            day=2,
            month=3,
            year=2019,
        )

    @patch.object(bnpl.overdue, "get_repayment_period_parameter")
    @patch.object(bnpl, "_get_repayment_frequency_delta")
    @patch.object(bnpl.utils, "get_schedule_expression_from_parameters")
    def test_schedule_overdue_check_event_mid_month(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_repayment_frequency_delta: MagicMock,
        mock_get_repayment_period_parameter: MagicMock,
    ):
        # expected values
        repayment_period = 2
        repayment_frequency_delta = bnpl.config_repayment_frequency.FREQUENCY_MAP[
            bnpl.config_repayment_frequency.MONTHLY
        ]
        sentinel_schedule = SentinelScheduleExpression("dummy_expression")
        effective_datetime = datetime(2019, 1, 15, tzinfo=ZoneInfo("UTC"))

        # construct expected result
        expected = [
            UpdateAccountEventTypeDirective(
                event_type=bnpl.overdue.CHECK_OVERDUE_EVENT,
                expression=sentinel_schedule,
            ),
        ]

        # construct mocks
        mock_get_repayment_period_parameter.return_value = repayment_period
        mock_get_repayment_frequency_delta.return_value = repayment_frequency_delta
        mock_get_schedule_expression_from_parameters.return_value = sentinel_schedule
        mock_vault = self.create_mock()

        # run function
        res = bnpl._schedule_overdue_check_event(
            vault=mock_vault, effective_datetime=effective_datetime
        )

        # validate results
        self.assertEqual(expected, res)
        mock_get_repayment_period_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_repayment_frequency_delta.assert_called_once_with(vault=mock_vault)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix=bnpl.overdue.CHECK_OVERDUE_PREFIX,
            # (effective datetime) Jan. 15, 2019 - (repayment period) 2 days = Jan. 13 2019
            # Jan. 13 2019 + (frequency) 1 month = Feb 13, 2019
            # Feb 13, 2019 + (repayment period) 2 = Feb 15, 2019
            day=15,
            month=2,
            year=2019,
        )

    @patch.object(bnpl.config_repayment_frequency, "get_repayment_frequency_parameter")
    def test_get_repayment_frequency_delta(
        self,
        mock_get_repayment_frequency_parameter: MagicMock,
    ):
        # expected values
        monthly = bnpl.config_repayment_frequency.MONTHLY
        # construct expected result
        expected = bnpl.config_repayment_frequency.FREQUENCY_MAP[monthly]

        # construct mocks
        mock_get_repayment_frequency_parameter.return_value = monthly

        # run function
        res = bnpl._get_repayment_frequency_delta(vault=sentinel.vault)

        # validate results
        self.assertEqual(expected, res)
        mock_get_repayment_frequency_parameter.assert_called_once_with(vault=sentinel.vault)


class LateRepaymentCheckScheduledEventHookTest(BNPLTest):
    @patch.object(bnpl.late_repayment, "schedule_logic")
    @patch.object(bnpl, "_schedule_check_late_repayment_event")
    @patch.object(bnpl.common_parameters, "get_denomination_parameter")
    def test_schedule_late_repayment_on_empty_ci(
        self,
        mock_get_denomination_parameter: MagicMock,
        mock_schedule_check_late_repayment_event: MagicMock,
        mock_late_repayment_schedule_logic: MagicMock,
    ):
        # expected values
        sentinel_schedule = SentinelScheduleExpression("dummy_expression")

        # construct expected result
        expected_update_account_event_type = UpdateAccountEventTypeDirective(
            event_type=bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT,
            expression=sentinel_schedule,
        )
        expected = ScheduledEventHookResult(
            update_account_event_type_directives=[expected_update_account_event_type]
        )

        # construct mocks
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_late_repayment_schedule_logic.return_value = []
        mock_schedule_check_late_repayment_event.return_value = [expected_update_account_event_type]
        mock_vault = self.create_mock()

        # run hook
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT,
        )
        res = bnpl.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate results
        self.assertEqual(expected, res)
        mock_late_repayment_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            denomination=sentinel.denomination,
        )
        mock_get_denomination_parameter.assert_called_once_with(vault=mock_vault)
        mock_schedule_check_late_repayment_event.assert_called_once_with(
            vault=mock_vault, effective_datetime=hook_args.effective_datetime
        )

    @patch.object(bnpl.late_repayment, "schedule_logic")
    @patch.object(bnpl, "_schedule_check_late_repayment_event")
    @patch.object(bnpl.common_parameters, "get_denomination_parameter")
    def test_schedule_late_repayment_check_ci_included_if_not_empty(
        self,
        mock_get_denomination_parameter: MagicMock,
        mock_schedule_check_late_repayment_event: MagicMock,
        mock_late_repayment_schedule_logic: MagicMock,
    ):
        # expected values
        late_repayment_ci = [
            SentinelCustomInstruction(bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT)
        ]
        event_type = bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT
        sentinel_schedule = SentinelScheduleExpression("dummy_expression")

        # construct expected result
        expected_update_account_event_type = UpdateAccountEventTypeDirective(
            event_type=bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT,
            expression=sentinel_schedule,
        )
        expected = ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=late_repayment_ci,  # type: ignore
                    client_batch_id=f"{bnpl.PRODUCT_NAME}_{event_type}_MOCK_HOOK",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            update_account_event_type_directives=[expected_update_account_event_type],
        )

        # construct mocks
        mock_late_repayment_schedule_logic.return_value = late_repayment_ci
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_schedule_check_late_repayment_event.return_value = [expected_update_account_event_type]
        mock_vault = self.create_mock()

        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT,
        )
        res = bnpl.scheduled_event_hook(
            vault=mock_vault,
            hook_arguments=hook_args,
        )

        # validate results
        self.assertEqual(expected, res)
        mock_late_repayment_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            hook_arguments=hook_args,
            denomination=sentinel.denomination,
        )
        mock_get_denomination_parameter.assert_called_once_with(vault=mock_vault)
        mock_schedule_check_late_repayment_event.assert_called_once_with(
            vault=mock_vault, effective_datetime=hook_args.effective_datetime
        )

    @patch.object(bnpl.overdue, "get_repayment_period_parameter")
    @patch.object(bnpl.delinquency, "get_grace_period_parameter")
    @patch.object(bnpl, "_get_repayment_frequency_delta")
    @patch.object(bnpl.utils, "get_schedule_expression_from_parameters")
    def test_schedule_check_late_repayment_event_mid_month(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_repayment_frequency_delta: MagicMock,
        mock_get_grace_period_parameter: MagicMock,
        mock_get_repayment_period_parameter: MagicMock,
    ):
        # expected values
        sentinel_schedule = SentinelScheduleExpression("dummy_expression")
        monthly = bnpl.config_repayment_frequency.MONTHLY
        effective_datetime = datetime(2019, 1, 15, tzinfo=ZoneInfo("UTC"))

        # construct expected result
        expected_update_account_event_type = UpdateAccountEventTypeDirective(
            event_type=bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT,
            expression=sentinel_schedule,
        )
        expected = [expected_update_account_event_type]

        # construct mocks
        mock_get_schedule_expression_from_parameters.return_value = sentinel_schedule
        mock_get_repayment_frequency_delta.return_value = (
            bnpl.config_repayment_frequency.FREQUENCY_MAP[monthly]
        )
        mock_get_grace_period_parameter.return_value = 1
        mock_get_repayment_period_parameter.return_value = 1
        mock_vault = self.create_mock()

        # run function
        res = bnpl._schedule_check_late_repayment_event(
            vault=mock_vault,
            effective_datetime=effective_datetime,
        )

        # validate results
        self.assertEqual(expected, res)
        mock_get_grace_period_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_repayment_frequency_delta.assert_called_once_with(vault=mock_vault)
        mock_get_repayment_period_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix=bnpl.late_repayment.CHECK_LATE_REPAYMENT_PREFIX,
            # (effective datetime) Jan. 15, 2019 - (repayment period
            # + grace period) 2 days = Jan. 13 2019
            # Jan. 13 2019 + (frequency) 1 month = Feb 13, 2019
            # Feb 13, 2019 + (repayment period + grace period) 2 days = Feb 15, 2019
            day=15,
            month=2,
            year=2019,
        )

    @patch.object(bnpl.overdue, "get_repayment_period_parameter")
    @patch.object(bnpl.delinquency, "get_grace_period_parameter")
    @patch.object(bnpl, "_get_repayment_frequency_delta")
    @patch.object(bnpl.utils, "get_schedule_expression_from_parameters")
    def test_schedule_check_late_repayment_event_start_of_month(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_repayment_frequency_delta: MagicMock,
        mock_get_grace_period_parameter: MagicMock,
        mock_get_repayment_period_parameter: MagicMock,
    ):
        # expected values
        sentinel_schedule = SentinelScheduleExpression("dummy_expression")
        monthly = bnpl.config_repayment_frequency.MONTHLY
        effective_datetime = DEFAULT_DATETIME

        # construct expected result
        expected_update_account_event_type = UpdateAccountEventTypeDirective(
            event_type=bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT,
            expression=sentinel_schedule,
        )
        expected = [expected_update_account_event_type]

        # construct mocks
        mock_get_schedule_expression_from_parameters.return_value = sentinel_schedule
        mock_get_repayment_frequency_delta.return_value = (
            bnpl.config_repayment_frequency.FREQUENCY_MAP[monthly]
        )
        mock_get_grace_period_parameter.return_value = 1
        mock_get_repayment_period_parameter.return_value = 1
        mock_vault = self.create_mock()

        # run function
        res = bnpl._schedule_check_late_repayment_event(
            vault=mock_vault,
            effective_datetime=effective_datetime,
        )

        # validate results
        self.assertEqual(expected, res)
        mock_get_grace_period_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_repayment_frequency_delta.assert_called_once_with(vault=mock_vault)
        mock_get_repayment_period_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix=bnpl.late_repayment.CHECK_LATE_REPAYMENT_PREFIX,
            # (effective datetime) Jan. 1, 2019 - (repayment period +
            # grace period) 2 days = Dec. 30 2018
            # Dec. 30 2018 + (frequency) 1 month = Jan 30, 2019
            # Feb 1, 2019 + (repayment period + grace period) 2 days = Feb 1, 2019
            day=1,
            month=2,
            year=2019,
        )

    @patch.object(bnpl.overdue, "get_repayment_period_parameter")
    @patch.object(bnpl.delinquency, "get_grace_period_parameter")
    @patch.object(bnpl, "_get_repayment_frequency_delta")
    @patch.object(bnpl.utils, "get_schedule_expression_from_parameters")
    def test_schedule_check_late_repayment_event_end_of_month(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_repayment_frequency_delta: MagicMock,
        mock_get_grace_period_parameter: MagicMock,
        mock_get_repayment_period_parameter: MagicMock,
    ):
        # expected values
        sentinel_schedule = SentinelScheduleExpression("dummy_expression")
        monthly = bnpl.config_repayment_frequency.MONTHLY
        effective_datetime = datetime(2019, 1, 31, tzinfo=ZoneInfo("UTC"))

        # construct expected result
        expected_update_account_event_type = UpdateAccountEventTypeDirective(
            event_type=bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT,
            expression=sentinel_schedule,
        )
        expected = [expected_update_account_event_type]

        # construct mocks
        mock_get_schedule_expression_from_parameters.return_value = sentinel_schedule
        mock_get_repayment_frequency_delta.return_value = (
            bnpl.config_repayment_frequency.FREQUENCY_MAP[monthly]
        )
        mock_get_grace_period_parameter.return_value = 1
        mock_get_repayment_period_parameter.return_value = 1
        mock_vault = self.create_mock()

        # run function
        res = bnpl._schedule_check_late_repayment_event(
            vault=mock_vault,
            effective_datetime=effective_datetime,
        )

        # validate results
        self.assertEqual(expected, res)
        mock_get_grace_period_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_repayment_frequency_delta.assert_called_once_with(vault=mock_vault)
        mock_get_repayment_period_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix=bnpl.late_repayment.CHECK_LATE_REPAYMENT_PREFIX,
            # (effective datetime) Jan. 31, 2019 - (repayment period +
            # grace period) 2 days = Jan. 29 2019
            # Jan. 29 2019 + (frequency) 1 month = Feb 28, 2019
            # Feb 28, 2019 + (repayment period + grace period) 2 days = Mar. 2 2019
            day=2,
            month=3,
            year=2019,
        )


@patch.object(bnpl.delinquency, "schedule_logic")
@patch.object(bnpl.common_parameters, "get_denomination_parameter")
class DelinquencyNotificationScheduledEventHookTest(BNPLTest):
    def test_none_result_on_empty_account_notification_directive(
        self,
        mock_get_denomination_parameter: MagicMock,
        mock_delinquency_schedule_logic: MagicMock,
    ):
        # construct mocks
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_delinquency_schedule_logic.return_value = []

        # validate results
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=bnpl.delinquency.CHECK_DELINQUENCY_EVENT,
        )
        self.assertIsNone(bnpl.scheduled_event_hook(vault=sentinel.vault, hook_arguments=hook_args))

    def test_schedule_delinquency(
        self,
        mock_get_denomination_parameter: MagicMock,
        mock_delinquency_schedule_logic: MagicMock,
    ):
        # expected values
        mock_vault = self.create_mock()
        check_delinquency = [
            AccountNotificationDirective(
                notification_type=bnpl.delinquency.notification_type(bnpl.PRODUCT_NAME),
                notification_details={"account_id": str(mock_vault.account_id)},
            )
        ]

        # construct mocks
        mock_delinquency_schedule_logic.return_value = check_delinquency
        mock_get_denomination_parameter.return_value = sentinel.denomination
        # construct expected result
        expected = ScheduledEventHookResult(account_notification_directives=check_delinquency)

        # run function
        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=bnpl.delinquency.CHECK_DELINQUENCY_EVENT,
        )
        res = bnpl.scheduled_event_hook(vault=mock_vault, hook_arguments=hook_args)

        # validate results
        self.assertEqual(expected, res)
        mock_delinquency_schedule_logic.assert_called_once_with(
            vault=mock_vault,
            product_name=bnpl.PRODUCT_NAME,
            addresses=bnpl.lending_addresses.ALL_OUTSTANDING,
            denomination=sentinel.denomination,
        )
