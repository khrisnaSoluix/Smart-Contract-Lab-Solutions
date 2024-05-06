# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.shariah import profit_application

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_ADDRESS,
    DEFAULT_DENOMINATION,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CalendarEvent,
    ScheduledEvent,
    ScheduleExpression,
    SmartContractEventType,
    UpdateAccountEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelScheduleExpression,
)

DEFAULT_DATE = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))

ACCRUED_PROFIT_PAYABLE_ACCOUNT = sentinel.accrued_profit_payable_account
PROFIT_PAID_ACCOUNT = sentinel.profit_paid_account
APPLICATION_EVENT = profit_application.APPLICATION_EVENT
APPLIED_PROFIT_ADDRESS = DEFAULT_ADDRESS
ACCRUED_PROFIT_ADDRESS = profit_application.ACCRUED_PROFIT_PAYABLE

PUBLIC_HOLIDAYS = "PUBLIC_HOLIDAYS"
DEFAULT_CALENDAR_EVENT = CalendarEvent(
    id="TEST",
    calendar_id=PUBLIC_HOLIDAYS,
    start_datetime=datetime(2020, 9, 5, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
    end_datetime=datetime(2020, 9, 6, 23, 23, 59, tzinfo=ZoneInfo("UTC")),
)


class TestProfitApplication(FeatureTest):
    def test_event_types_lower_case_event_name(self):
        expected_tag_id = ["CURRENT_ACCOUNT_APPLY_PROFIT_AST"]
        test_case = SmartContractEventType(
            name="current_account", scheduler_tag_ids=expected_tag_id
        )
        result = profit_application.event_types(test_case.name)[0].scheduler_tag_ids
        self.assertEqual(result, test_case.scheduler_tag_ids)

    @patch.object(profit_application.utils, "one_off_schedule_expression")
    @patch.object(profit_application.utils, "get_next_schedule_date_calendar_aware")
    @patch.object(profit_application.utils, "get_schedule_time_from_parameters")
    @patch.object(profit_application.utils, "get_parameter")
    def test_scheduled_events_monthly_frequency(
        self,
        mock_get_parameter: MagicMock,
        mock_get_schedule_time_from_parameters: MagicMock,
        mock_get_next_schedule_date_calendar_aware: MagicMock,
        mock_one_off_schedule_expression: MagicMock,
    ):
        mock_vault = self.create_mock(calendar_events=[DEFAULT_CALENDAR_EVENT])
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                profit_application.PARAM_PROFIT_APPLICATION_FREQUENCY: "monthly",
                profit_application.PARAM_PROFIT_APPLICATION_DAY: "1",
            }
        )
        mock_get_schedule_time_from_parameters.return_value = (0, 0, 0)
        mock_get_next_schedule_date_calendar_aware.return_value = DEFAULT_DATE + relativedelta(
            months=1
        )
        mock_one_off_schedule_expression.return_value = SentinelScheduleExpression("profit_expr")
        expected_result = {
            APPLICATION_EVENT: ScheduledEvent(
                start_datetime=DEFAULT_DATE, expression=SentinelScheduleExpression("profit_expr")
            )
        }
        actual_schedules = profit_application.scheduled_events(
            vault=mock_vault, start_datetime=DEFAULT_DATE
        )

        mock_get_schedule_time_from_parameters.assert_called_once_with(
            vault=mock_vault, parameter_prefix="profit_application"
        )
        mock_get_next_schedule_date_calendar_aware.assert_called_once_with(
            start_datetime=DEFAULT_DATE,
            schedule_frequency="monthly",
            intended_day=1,
            calendar_events=[DEFAULT_CALENDAR_EVENT],
        )
        mock_one_off_schedule_expression.assert_called_once_with(
            DEFAULT_DATE + relativedelta(months=1, hour=0, minute=0, second=0)
        )
        self.assertEqual(actual_schedules[APPLICATION_EVENT], expected_result[APPLICATION_EVENT])

    @patch.object(profit_application.utils, "one_off_schedule_expression")
    @patch.object(profit_application.utils, "get_next_schedule_date_calendar_aware")
    @patch.object(profit_application.utils, "get_schedule_time_from_parameters")
    @patch.object(profit_application.utils, "get_parameter")
    def test_scheduled_events_quarterly_frequency(
        self,
        mock_get_parameter: MagicMock,
        mock_get_schedule_time_from_parameters: MagicMock,
        mock_get_next_schedule_date_calendar_aware: MagicMock,
        mock_one_off_schedule_expression: MagicMock,
    ):
        mock_vault = self.create_mock(calendar_events=[DEFAULT_CALENDAR_EVENT])
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                profit_application.PARAM_PROFIT_APPLICATION_FREQUENCY: "quarterly",
                profit_application.PARAM_PROFIT_APPLICATION_DAY: "1",
            }
        )
        mock_get_schedule_time_from_parameters.return_value = (0, 0, 0)
        mock_get_next_schedule_date_calendar_aware.return_value = DEFAULT_DATE + relativedelta(
            months=3
        )
        mock_one_off_schedule_expression.return_value = SentinelScheduleExpression("profit_expr")
        expected_result = {
            APPLICATION_EVENT: ScheduledEvent(
                start_datetime=DEFAULT_DATE, expression=SentinelScheduleExpression("profit_expr")
            )
        }
        actual_schedules = profit_application.scheduled_events(
            vault=mock_vault, start_datetime=DEFAULT_DATE
        )

        mock_get_schedule_time_from_parameters.assert_called_once_with(
            vault=mock_vault, parameter_prefix="profit_application"
        )
        mock_get_next_schedule_date_calendar_aware.assert_called_once_with(
            start_datetime=DEFAULT_DATE,
            schedule_frequency="quarterly",
            intended_day=1,
            calendar_events=[DEFAULT_CALENDAR_EVENT],
        )
        mock_one_off_schedule_expression.assert_called_once_with(
            DEFAULT_DATE + relativedelta(months=3, hour=0, minute=0, second=0)
        )
        self.assertEqual(actual_schedules[APPLICATION_EVENT], expected_result[APPLICATION_EVENT])

    @patch.object(profit_application.utils, "one_off_schedule_expression")
    @patch.object(profit_application.utils, "get_next_schedule_date_calendar_aware")
    @patch.object(profit_application.utils, "get_schedule_time_from_parameters")
    @patch.object(profit_application.utils, "get_parameter")
    def test_scheduled_events_annually_frequency(
        self,
        mock_get_parameter: MagicMock,
        mock_get_schedule_time_from_parameters: MagicMock,
        mock_get_next_schedule_date_calendar_aware: MagicMock,
        mock_one_off_schedule_expression: MagicMock,
    ):
        mock_vault = self.create_mock(calendar_events=[DEFAULT_CALENDAR_EVENT])
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                profit_application.PARAM_PROFIT_APPLICATION_FREQUENCY: "annually",
                profit_application.PARAM_PROFIT_APPLICATION_DAY: "1",
            }
        )
        mock_get_schedule_time_from_parameters.return_value = (0, 0, 0)
        mock_get_next_schedule_date_calendar_aware.return_value = DEFAULT_DATE + relativedelta(
            years=1
        )
        mock_one_off_schedule_expression.return_value = SentinelScheduleExpression("profit_expr")
        expected_result = {
            APPLICATION_EVENT: ScheduledEvent(
                start_datetime=DEFAULT_DATE, expression=SentinelScheduleExpression("profit_expr")
            )
        }
        actual_schedules = profit_application.scheduled_events(
            vault=mock_vault, start_datetime=DEFAULT_DATE
        )

        mock_get_schedule_time_from_parameters.assert_called_once_with(
            vault=mock_vault, parameter_prefix="profit_application"
        )
        mock_get_next_schedule_date_calendar_aware.assert_called_once_with(
            start_datetime=DEFAULT_DATE,
            schedule_frequency="annually",
            intended_day=1,
            calendar_events=[DEFAULT_CALENDAR_EVENT],
        )
        mock_one_off_schedule_expression.assert_called_once_with(
            DEFAULT_DATE + relativedelta(years=1, hour=0, minute=0, second=0)
        )
        self.assertEqual(actual_schedules[APPLICATION_EVENT], expected_result[APPLICATION_EVENT])

    @patch.object(profit_application.utils, "standard_instruction_details")
    @patch.object(profit_application.accruals, "accrual_application_custom_instruction")
    @patch.object(profit_application.utils, "balance_at_coordinates")
    @patch.object(profit_application.utils, "get_parameter")
    def test_apply_positive_profit(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_accruals_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        accrued_amount = Decimal("1.23654")
        rounded_accrued_amount = Decimal("1.24")
        mock_balance_at_coordinates.side_effect = [accrued_amount]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                profit_application.PARAM_APPLICATION_PRECISION: 2,
                profit_application.PARAM_PROFIT_PAID_ACCOUNT: PROFIT_PAID_ACCOUNT,
                profit_application.tiered_profit_accrual.PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT: (
                    ACCRUED_PROFIT_PAYABLE_ACCOUNT
                ),
                "denomination": DEFAULT_DENOMINATION,
            },
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "EOD_FETCHER": SentinelBalancesObservation("balances_obs")
            }
        )
        mock_accruals_custom_instruction.return_value = [SentinelCustomInstruction("postings")]
        mock_standard_instruction_details.return_value = sentinel.value

        custom_instructions = profit_application.apply_profit(
            vault=mock_vault,
        )

        mock_accruals_custom_instruction.assert_called_once_with(
            customer_account="default_account",
            denomination=DEFAULT_DENOMINATION,
            application_amount=rounded_accrued_amount,
            accrual_amount=abs(accrued_amount),
            instruction_details=sentinel.value,
            accrual_customer_address=ACCRUED_PROFIT_ADDRESS,
            accrual_internal_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            application_customer_address=DEFAULT_ADDRESS,
            application_internal_account=PROFIT_PAID_ACCOUNT,
            payable=True,
        )
        self.assertListEqual(custom_instructions, [SentinelCustomInstruction("postings")])

    @patch.object(profit_application.utils, "standard_instruction_details")
    @patch.object(profit_application.accruals, "accrual_application_custom_instruction")
    @patch.object(profit_application.utils, "balance_at_coordinates")
    @patch.object(profit_application.utils, "get_parameter")
    def test_apply_zero_profit(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_accruals_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        accrued_amount = Decimal("0")
        mock_balance_at_coordinates.side_effect = [accrued_amount]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                profit_application.PARAM_APPLICATION_PRECISION: 2,
                profit_application.PARAM_PROFIT_PAID_ACCOUNT: PROFIT_PAID_ACCOUNT,
                profit_application.tiered_profit_accrual.PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT: (
                    ACCRUED_PROFIT_PAYABLE_ACCOUNT
                ),
                "denomination": DEFAULT_DENOMINATION,
            },
        )
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "EOD_FETCHER": SentinelBalancesObservation("balances_obs")
            }
        )

        custom_instructions = profit_application.apply_profit(vault=mock_vault)

        mock_accruals_custom_instruction.assert_not_called()
        self.assertListEqual(custom_instructions, [])

    @patch.object(profit_application, "scheduled_events")
    @patch.object(profit_application.utils, "get_parameter")
    def test_update_next_schedule_execution_annually(
        self,
        mock_get_parameter: MagicMock,
        mock_scheduled_events: MagicMock,
    ):
        test_start_date = datetime(year=2020, month=2, day=28, tzinfo=ZoneInfo("UTC"))
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                profit_application.PARAM_PROFIT_APPLICATION_FREQUENCY: "annually",
                profit_application.PARAM_PROFIT_APPLICATION_DAY: "1",
            }
        )
        mock_scheduled_events.return_value = {
            "APPLY_PROFIT": ScheduledEvent(
                start_datetime=test_start_date, expression=SentinelScheduleExpression("expression")
            )
        }
        update_result = profit_application.update_next_schedule_execution(
            vault=sentinel.vault, effective_datetime=test_start_date
        )
        expected_result = UpdateAccountEventTypeDirective(
            event_type=APPLICATION_EVENT, expression=SentinelScheduleExpression("expression")
        )

        self.assertEquals(update_result, expected_result)

    @patch.object(profit_application, "scheduled_events")
    @patch.object(profit_application.utils, "get_parameter")
    def test_update_next_schedule_execution_annually_february(
        self,
        mock_get_parameter: MagicMock,
        mock_scheduled_events: MagicMock,
    ):
        test_start_date = datetime(year=2020, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                profit_application.PARAM_PROFIT_APPLICATION_FREQUENCY: "annually",
                profit_application.PARAM_PROFIT_APPLICATION_DAY: "31",
            }
        )
        mock_scheduled_events.return_value = {
            "APPLY_PROFIT": ScheduledEvent(
                start_datetime=test_start_date, expression=SentinelScheduleExpression("expression")
            )
        }

        update_result = profit_application.update_next_schedule_execution(
            vault=sentinel.vault, effective_datetime=test_start_date
        )
        expected_result = UpdateAccountEventTypeDirective(
            event_type=APPLICATION_EVENT,
            expression=SentinelScheduleExpression("expression"),
        )

        self.assertEquals(update_result, expected_result)

    @patch.object(profit_application, "scheduled_events")
    @patch.object(profit_application.utils, "get_parameter")
    def test_update_next_schedule_execution_quarterly(
        self, mock_get_parameter: MagicMock, mock_scheduled_events: MagicMock
    ):
        mock_scheduled_events.return_value = {
            APPLICATION_EVENT: ScheduledEvent(
                start_datetime=DEFAULT_DATE,
                expression=ScheduleExpression(month=4, day=1, hour=1, minute=2, second=3),
            )
        }
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                profit_application.PARAM_PROFIT_APPLICATION_FREQUENCY: "quarterly",
                profit_application.PARAM_PROFIT_APPLICATION_DAY: "1",
            }
        )
        update_result = profit_application.update_next_schedule_execution(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATE
        )

        mock_scheduled_events.assert_called_once_with(
            vault=sentinel.vault, start_datetime=DEFAULT_DATE
        )
        self.assertEquals(
            update_result,
            UpdateAccountEventTypeDirective(
                event_type=APPLICATION_EVENT,
                expression=mock_scheduled_events.return_value[APPLICATION_EVENT].expression,
            ),
        )
