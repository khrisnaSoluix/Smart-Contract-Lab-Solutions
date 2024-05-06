# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.lending.due_amount_notification as due_amount_notification
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DENOMINATION,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    ScheduledEvent,
    SmartContractEventType,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelScheduleExpression,
)


class DueNotificationAmountTest(FeatureTest):
    maxDiff = None


class ScheduleLogicTest(DueNotificationAmountTest):
    param_return_vals_denom_only = {
        due_amount_notification.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
    }

    def test_due_amount_notification_type(
        self,
    ):
        # expected values
        product_name = "PRODUCT_A"
        # construct expected result
        expected_notification_type = (
            f"{product_name}{due_amount_notification.REPAYMENT_NOTIFICATION_SUFFIX}"
        )
        # run function
        notification_type = due_amount_notification.notification_type(product_name=product_name)
        # validate results
        self.assertEqual(notification_type, expected_notification_type)

    def test_send_repayment_notification(
        self,
    ):
        # expected values
        product_name = "PRODUCT_A"
        due_principal = Decimal("50")
        due_interest = Decimal("0")
        # overdue_datetime = due_amount_calculation_datetime + PARAM_REPAYMENT_PERIOD
        overdue_datetime = datetime(2020, 1, 4, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        mock_vault = self.create_mock()

        # construct expected result
        expected_notification_details = {
            "account_id": str(mock_vault.account_id),
            "due_principal": str(due_principal),
            "due_interest": str(due_interest),
            "overdue_date": str(overdue_datetime.date()),
        }
        expected_notification_directive = AccountNotificationDirective(
            notification_type=due_amount_notification.notification_type(product_name),
            notification_details=expected_notification_details,
        )

        # run function
        result = due_amount_notification.send_due_amount_notification(
            account_id=mock_vault.account_id,
            due_principal=due_principal,
            due_interest=due_interest,
            overdue_datetime=overdue_datetime,
            product_name=product_name,
        )

        # validate results
        self.assertEqual(expected_notification_directive, result)

    def test_schedule_logic_no_notification_no_values_provided(self):
        # expected values
        product_name = "PRODUCT_A"

        # overdue_datetime=due_amount_calculation_datetime + PARAM_REPAYMENT_PERIOD
        overdue_datetime = datetime(2019, 12, 31, 3, 4, 5, tzinfo=ZoneInfo("UTC"))

        # construct mocks
        mock_vault = self.create_mock()

        # run function
        result = due_amount_notification.schedule_logic(
            vault=mock_vault,
            product_name=product_name,
            overdue_datetime=overdue_datetime,
        )

        # validate results
        self.assertEqual([], result)

    def test_schedule_logic_no_notification(self):
        # expected values
        product_name = "PRODUCT_A"
        due_principal = Decimal("0")
        due_interest = Decimal("0")

        # overdue_datetime=due_amount_calculation_datetime + PARAM_REPAYMENT_PERIOD
        overdue_datetime = datetime(2019, 12, 31, 3, 4, 5, tzinfo=ZoneInfo("UTC"))

        # construct mocks
        mock_vault = self.create_mock()

        # run function
        result = due_amount_notification.schedule_logic(
            vault=mock_vault,
            product_name=product_name,
            overdue_datetime=overdue_datetime,
            due_interest=due_interest,
            due_principal=due_principal,
        )

        # validate results
        self.assertEqual([], result)

    @patch.object(due_amount_notification, "send_due_amount_notification")
    def test_schedule_logic_notification_sent_only_due_amount_provided(
        self,
        mock_send_due_amount_notification: MagicMock,
    ):
        # expected values
        product_name = "PRODUCT_A"
        due_principal = Decimal("70")
        due_interest = Decimal("0")

        # overdue_datetime = due_amount_calculation_date + PARAM_REPAYMENT_PERIOD
        overdue_datetime = datetime(2020, 1, 4, 3, 4, 5, tzinfo=ZoneInfo("UTC"))

        mock_vault = self.create_mock()

        # construct expected result
        expected_notification_details = {
            "account_id": str(mock_vault.account_id),
            "principal_due": str(due_principal),
            "interest_due": str(due_interest),
            "overdue_date": str(overdue_datetime.date()),
        }
        expected_notification_directive = AccountNotificationDirective(
            notification_type=due_amount_notification.notification_type(product_name),
            notification_details=expected_notification_details,
        )

        # construct mocks
        mock_send_due_amount_notification.return_value = expected_notification_directive

        # run function
        result = due_amount_notification.schedule_logic(
            vault=mock_vault,
            product_name=product_name,
            overdue_datetime=overdue_datetime,
            due_interest=due_interest,
            due_principal=due_principal,
        )

        # validate results
        self.assertEqual([expected_notification_directive], result)
        mock_send_due_amount_notification.assert_called_once_with(
            account_id=mock_vault.account_id,
            due_principal=due_principal,
            due_interest=due_interest,
            overdue_datetime=overdue_datetime,
            product_name=product_name,
        )

    @patch.object(due_amount_notification, "send_due_amount_notification")
    def test_schedule_logic_notification_sent_only_interest_provided(
        self,
        mock_send_due_amount_notification: MagicMock,
    ):
        # expected values
        product_name = "PRODUCT_A"
        due_principal = Decimal("0")
        due_interest = Decimal("0.1")

        # overdue_datetime=due_amount_calculation_datetime + PARAM_REPAYMENT_PERIOD
        overdue_datetime = datetime(2019, 12, 31, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        mock_vault = self.create_mock()

        # construct expected result
        expected_notification_details = {
            "account_id": str(mock_vault.account_id),
            "principal_due": str(due_principal),
            "interest_due": str(due_interest),
            "overdue_date": str(overdue_datetime.date()),
        }
        expected_notification_directive = AccountNotificationDirective(
            notification_type=due_amount_notification.notification_type(product_name),
            notification_details=expected_notification_details,
        )

        # construct mocks
        mock_send_due_amount_notification.return_value = expected_notification_directive

        # run function
        result = due_amount_notification.schedule_logic(
            vault=mock_vault,
            product_name=product_name,
            overdue_datetime=overdue_datetime,
            due_interest=due_interest,
            due_principal=due_principal,
        )

        # validate results
        self.assertEqual([expected_notification_directive], result)
        mock_send_due_amount_notification.assert_called_once_with(
            account_id=mock_vault.account_id,
            due_principal=due_principal,
            due_interest=due_interest,
            overdue_datetime=overdue_datetime,
            product_name=product_name,
        )

    def test_schedule_logic_no_notification_sent_negative_amount(
        self,
    ):
        # expected values
        product_name = "PRODUCT_A"
        due_principal = Decimal("-0.1")
        due_interest = Decimal("-0.1")

        # overdue_datetime=due_amount_calculation_datetime + PARAM_REPAYMENT_PERIOD
        overdue_datetime = datetime(2019, 12, 31, 3, 4, 5, tzinfo=ZoneInfo("UTC"))

        # construct mocks
        mock_vault = self.create_mock()

        # run function
        result = due_amount_notification.schedule_logic(
            vault=mock_vault,
            product_name=product_name,
            overdue_datetime=overdue_datetime,
            due_interest=due_interest,
            due_principal=due_principal,
        )

        # validate results
        self.assertEqual([], result)

    @patch.object(due_amount_notification, "send_due_amount_notification")
    def test_schedule_logic_notification_sent_both_principal_and_interest_provided(
        self,
        mock_send_due_amount_notification: MagicMock,
    ):
        # expected values
        product_name = "PRODUCT_A"
        due_principal = Decimal("100")
        due_interest = Decimal("0.1")

        # overdue_datetime=due_amount_calculation_datetime + PARAM_REPAYMENT_PERIOD
        overdue_datetime = datetime(2019, 12, 31, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        mock_vault = self.create_mock()

        # construct expected result
        expected_notification_details = {
            "account_id": str(mock_vault.account_id),
            "principal_due": str(due_principal),
            "interest_due": str(due_interest),
            "overdue_date": str(overdue_datetime.date()),
        }
        expected_notification_directive = AccountNotificationDirective(
            notification_type=due_amount_notification.notification_type(product_name),
            notification_details=expected_notification_details,
        )

        # construct mocks
        mock_send_due_amount_notification.return_value = expected_notification_directive

        # run function
        result = due_amount_notification.schedule_logic(
            vault=mock_vault,
            product_name=product_name,
            overdue_datetime=overdue_datetime,
            due_interest=due_interest,
            due_principal=due_principal,
        )

        # validate results
        self.assertEqual([expected_notification_directive], result)
        mock_send_due_amount_notification.assert_called_once_with(
            account_id=mock_vault.account_id,
            due_principal=due_principal,
            due_interest=due_interest,
            overdue_datetime=overdue_datetime,
            product_name=product_name,
        )

    @patch.object(due_amount_notification, "get_next_due_amount_notification_schedule")
    @patch.object(due_amount_notification.utils, "get_parameter")
    def test_get_next_due_amount_notification_datetime(
        self,
        mock_get_parameter: MagicMock,
        mock_get_next_due_amount_notification_schedule: MagicMock,
    ):
        # expected values
        notification_period = "2"
        due_amount_notification_datetime = datetime(2020, 2, 4, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        repayment_frequency_delta = relativedelta(months=1, days=1, years=1)
        param_return_vals = {
            due_amount_notification.PARAM_NOTIFICATION_PERIOD: notification_period,
        }
        # due_amount_notification_datetime + relative delta + notification period +
        # hour minute second doesn't come from the parameters so will remain
        # with the original value.
        next_due_amount_notification_datetime = datetime(
            2021, 3, 7, 3, 4, 5, tzinfo=ZoneInfo("UTC")
        )

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=param_return_vals)
        mock_get_next_due_amount_notification_schedule.return_value = (
            next_due_amount_notification_datetime
        )
        mock_vault = self.create_mock()

        # run function
        next_due_amount_notification_datetime = (
            due_amount_notification.get_next_due_amount_notification_datetime(
                vault=mock_vault,
                current_due_amount_notification_datetime=due_amount_notification_datetime,
                repayment_frequency_delta=repayment_frequency_delta,
            )
        )

        # validate results
        self.assertEqual(
            next_due_amount_notification_datetime, next_due_amount_notification_datetime
        )
        mock_get_next_due_amount_notification_schedule.assert_called_once_with(
            vault=mock_vault,
            next_due_amount_calc_datetime=due_amount_notification_datetime
            + repayment_frequency_delta
            + relativedelta(days=int(notification_period)),
        )


class ScheduleEventsTest(DueNotificationAmountTest):
    def test_due_notification_amount_event_types(
        self,
    ):
        # expected values
        product_name = "PRODUCT_A"
        # run function
        event_types = due_amount_notification.event_types(product_name=product_name)
        # validate results
        self.assertListEqual(
            event_types,
            [
                SmartContractEventType(
                    name=due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT,
                    scheduler_tag_ids=[
                        f"{product_name}_{due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT}_AST"
                    ],
                )
            ],
        )

    @patch.object(due_amount_notification.utils, "one_off_schedule_expression")
    @patch.object(due_amount_notification, "get_next_due_amount_notification_schedule")
    def test_due_notification_amount_scheduled_events(
        self,
        mock_get_next_due_amount_notification_schedule: MagicMock,
        mock_one_off_schedule_expression: MagicMock,
    ):
        # expected values
        # due_amount_datetime = start datetime + PARAM_REPAYMENT_FREQUENCY
        due_amount_datetime = datetime(2020, 2, 5, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        # due_amount_notification_date =  due_amount_datetime - PARAM_NOTIFICATION_PERIOD
        due_amount_notification_datetime = datetime(2020, 2, 3, 3, 4, 5, tzinfo=ZoneInfo("UTC"))

        # construct expected result
        expected_schedule_expression = SentinelScheduleExpression(
            due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT
        )
        expected = {
            due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT: ScheduledEvent(
                start_datetime=due_amount_notification_datetime - relativedelta(seconds=1),
                expression=expected_schedule_expression,
            )
        }

        # construct mocks
        mock_get_next_due_amount_notification_schedule.return_value = (
            due_amount_notification_datetime
        )
        mock_one_off_schedule_expression.return_value = expected_schedule_expression
        mock_vault = self.create_mock()

        # run function
        scheduled_events = due_amount_notification.scheduled_events(
            vault=mock_vault, next_due_amount_calc_datetime=due_amount_datetime
        )

        # validate results
        self.assertDictEqual(
            scheduled_events,
            expected,
        )
        mock_get_next_due_amount_notification_schedule.assert_called_once_with(
            vault=mock_vault, next_due_amount_calc_datetime=due_amount_datetime
        )

    @patch.object(due_amount_notification.utils, "get_schedule_time_from_parameters")
    @patch.object(due_amount_notification.utils, "get_parameter")
    def test_get_next_due_amount_notification_schedule(
        self, mock_get_parameter: MagicMock, mock_get_schedule_time_from_parameters: MagicMock
    ):
        # expected values
        notification_period = "2"
        # due_amount_datetime = start datetime + PARAM_REPAYMENT_FREQUENCY
        due_amount_datetime = datetime(2020, 2, 4, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        param_return_vals = {
            due_amount_notification.PARAM_NOTIFICATION_PERIOD: notification_period,
        }

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=param_return_vals)
        mock_get_schedule_time_from_parameters.return_value = (0, 0, 0)
        mock_vault = self.create_mock()

        # construct expected result
        # expected_due_amount_notification_datetime =
        # due_amount_datetime - PARAM_NOTIFICATION_PERIOD
        # hour minute second comes from parameters
        expected_due_amount_notification_datetime = datetime(
            2020, 2, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC")
        )

        # run function
        next_due_amount_notification_datetime = (
            due_amount_notification.get_next_due_amount_notification_schedule(
                vault=mock_vault, next_due_amount_calc_datetime=due_amount_datetime
            )
        )

        # validate results
        self.assertEqual(
            next_due_amount_notification_datetime, expected_due_amount_notification_datetime
        )


@patch.object(due_amount_notification.utils, "get_parameter")
class GetParametersTest(DueNotificationAmountTest):
    def test_get_repayment_period_parameter(self, mock_get_parameter: MagicMock):
        notification_period_parameter = 100

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                due_amount_notification.PARAM_NOTIFICATION_PERIOD: notification_period_parameter
            },
        )

        result = due_amount_notification.get_notification_period_parameter(vault=sentinel.vault)

        self.assertEqual(
            notification_period_parameter,
            result,
        )
