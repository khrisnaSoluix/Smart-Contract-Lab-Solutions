# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.common.fetchers as fetchers
import library.features.v4.lending.delinquency as delinquency
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    ScheduledEvent,
    SmartContractEventType,
    SupervisorContractEventType,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelScheduleExpression,
)

DEFAULT_DATE = datetime(2020, 1, 2, 3, tzinfo=ZoneInfo("UTC"))


class DelinquencyTest(FeatureTest):
    maxDiff = None


class ScheduleLogicTest(DelinquencyTest):
    def setUp(self):
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "balances_obs"
                )
            }
        )
        self.product_name = "PRODUCT_A"

    def test_delinquency_notification_type(
        self,
    ):
        expected_notification_type = (
            f"{self.product_name}{delinquency.MARK_DELINQUENT_NOTIFICATION_SUFFIX}"
        )
        notification_type = delinquency.notification_type(product_name=self.product_name)
        self.assertEqual(notification_type, expected_notification_type)

    @patch.object(delinquency.utils, "sum_balances")
    def test_schedule_logic_has_remaining_debt_notification_sent(
        self, mock_sum_balances: MagicMock
    ):
        mock_sum_balances.return_value = Decimal("0.1")
        expected_notification_details = {"account_id": str(self.mock_vault.account_id)}
        expected_notification_directive = [
            AccountNotificationDirective(
                notification_type=delinquency.notification_type(self.product_name),
                notification_details=expected_notification_details,
            )
        ]
        result = delinquency.schedule_logic(
            vault=self.mock_vault,
            product_name=self.product_name,
            addresses=sentinel.addresses,
            denomination=sentinel.denomination,
        )
        self.assertEqual(expected_notification_directive, result)
        mock_sum_balances.assert_called_once_with(
            balances=SentinelBalancesObservation("balances_obs").balances,
            addresses=sentinel.addresses,
            denomination=sentinel.denomination,
            decimal_places=2,
        )

    @patch.object(delinquency.utils, "sum_balances")
    def test_schedule_logic_has_no_remaining_debt_no_notification_sent(
        self, mock_sum_balances: MagicMock
    ):
        mock_sum_balances.return_value = Decimal("0")
        result = delinquency.schedule_logic(
            vault=self.mock_vault,
            product_name=self.product_name,
            addresses=sentinel.addresses,
            denomination=sentinel.denomination,
        )
        self.assertListEqual(result, [])
        mock_sum_balances.assert_called_once_with(
            balances=SentinelBalancesObservation("balances_obs").balances,
            addresses=sentinel.addresses,
            denomination=sentinel.denomination,
            decimal_places=2,
        )

    @patch.object(delinquency.utils, "sum_balances")
    def test_schedule_logic_has_negative_remaining_debt_no_notification_sent(
        self, mock_sum_balances: MagicMock
    ):
        mock_sum_balances.return_value = Decimal("-0.1")
        result = delinquency.schedule_logic(
            vault=self.mock_vault,
            product_name=self.product_name,
            addresses=sentinel.addresses,
            denomination=sentinel.denomination,
        )
        self.assertListEqual(result, [])
        mock_sum_balances.assert_called_once_with(
            balances=SentinelBalancesObservation("balances_obs").balances,
            addresses=sentinel.addresses,
            denomination=sentinel.denomination,
            decimal_places=2,
        )


class ScheduleEventsTest(DelinquencyTest):
    def test_delinquency_event_types(
        self,
    ):
        product_name = "PRODUCT_A"
        event_types = delinquency.event_types(product_name=product_name)
        self.assertListEqual(
            event_types,
            [
                SmartContractEventType(
                    name=delinquency.CHECK_DELINQUENCY_EVENT,
                    scheduler_tag_ids=[f"{product_name}_{delinquency.CHECK_DELINQUENCY_EVENT}_AST"],
                )
            ],
        )

    def test_delinquency_supervisor_event_types(
        self,
    ):
        product_name = "PRODUCT_A"
        event_types = delinquency.supervisor_event_types(product_name=product_name)
        self.assertListEqual(
            event_types,
            [
                SupervisorContractEventType(
                    name=delinquency.CHECK_DELINQUENCY_EVENT,
                    scheduler_tag_ids=[f"{product_name}_{delinquency.CHECK_DELINQUENCY_EVENT}_AST"],
                )
            ],
        )

    @patch.object(delinquency.utils, "get_schedule_expression_from_parameters")
    def test_delinquency_check_scheduled_events_recurring(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
    ):
        start_dt = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        mock_vault = self.create_mock(creation_date=start_dt)
        sched_expr = SentinelScheduleExpression(delinquency.CHECK_DELINQUENCY_EVENT)
        mock_get_schedule_expression_from_parameters.return_value = sched_expr

        result = delinquency.scheduled_events(vault=mock_vault, start_datetime=start_dt)
        expected = {
            delinquency.CHECK_DELINQUENCY_EVENT: ScheduledEvent(
                start_datetime=start_dt.replace(hour=0, minute=0, second=0),
                expression=sched_expr,
                skip=False,
            )
        }

        self.assertDictEqual(result, expected)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix=delinquency.CHECK_DELINQUENCY_PREFIX,
            day=start_dt.day,
            month=None,
            year=None,
        )

    @patch.object(delinquency.utils, "get_schedule_expression_from_parameters")
    def test_delinquency_check_scheduled_events_one_off(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
    ):
        start_dt = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        mock_vault = self.create_mock(creation_date=start_dt)
        sched_expr = SentinelScheduleExpression(delinquency.CHECK_DELINQUENCY_EVENT)
        mock_get_schedule_expression_from_parameters.return_value = sched_expr

        result = delinquency.scheduled_events(
            vault=mock_vault, start_datetime=start_dt, is_one_off=True
        )
        expected = {
            delinquency.CHECK_DELINQUENCY_EVENT: ScheduledEvent(
                start_datetime=start_dt.replace(hour=0, minute=0, second=0),
                expression=sched_expr,
                skip=False,
            )
        }

        self.assertDictEqual(result, expected)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix=delinquency.CHECK_DELINQUENCY_PREFIX,
            day=start_dt.day,
            month=start_dt.month,
            year=start_dt.year,
        )

    @patch.object(delinquency.utils, "get_schedule_expression_from_parameters")
    def test_delinquency_check_scheduled_events_skipped(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
    ):
        start_dt = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        mock_vault = self.create_mock(creation_date=start_dt)
        sched_expr = SentinelScheduleExpression(delinquency.CHECK_DELINQUENCY_EVENT)
        mock_get_schedule_expression_from_parameters.return_value = sched_expr

        result = delinquency.scheduled_events(vault=mock_vault, start_datetime=start_dt, skip=True)
        expected = {
            delinquency.CHECK_DELINQUENCY_EVENT: ScheduledEvent(
                start_datetime=start_dt.replace(hour=0, minute=0, second=0),
                expression=sched_expr,
                skip=True,
            )
        }

        self.assertDictEqual(result, expected)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix=delinquency.CHECK_DELINQUENCY_PREFIX,
            day=start_dt.day,
            month=None,
            year=None,
        )


@patch.object(delinquency.utils, "get_parameter")
class GetParametersTest(DelinquencyTest):
    def test_get_grace_period_parameter(self, mock_get_parameter: MagicMock):
        grace_period_parameter = 5

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={delinquency.PARAM_GRACE_PERIOD: grace_period_parameter},
        )

        result = delinquency.get_grace_period_parameter(vault=sentinel.vault)

        self.assertEqual(
            grace_period_parameter,
            result,
        )
