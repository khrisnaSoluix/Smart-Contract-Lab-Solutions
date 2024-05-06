# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.interest import interest_application

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DENOMINATION,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ADDRESS,
    EndOfMonthSchedule,
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

DEFAULT_DATETIME = datetime(year=2019, month=1, day=1, tzinfo=ZoneInfo("UTC"))
ACCRUED_INTEREST_PAYABLE_ADDRESS = "ACCRUED_INTEREST_PAYABLE"
ACCRUED_INTEREST_RECEIVABLE_ADDRESS = "ACCRUED_INTEREST_RECEIVABLE"
APPLICATION_EVENT = "APPLY_INTEREST"
APPLIED_INTEREST_ADDRESS = DEFAULT_ADDRESS
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"


class TestEventTypes(FeatureTest):
    def test_get_event_types_lower_case_event_name(self):
        expected_tag_id = ["CURRENT_ACCOUNT_APPLY_INTEREST_AST"]
        test_case = SmartContractEventType(
            name="current_account", scheduler_tag_ids=expected_tag_id
        )
        result = interest_application.event_types(test_case.name)[0].scheduler_tag_ids
        self.assertEqual(result, test_case.scheduler_tag_ids)


@patch.object(interest_application.utils, "get_schedule_expression_from_parameters")
@patch.object(interest_application.utils, "get_next_schedule_date")
@patch.object(interest_application.utils, "monthly_scheduled_event")
@patch.object(interest_application.utils, "get_parameter")
class TestScheduledEvents(FeatureTest):
    def test_scheduled_events_monthly_frequency(
        self,
        mock_get_parameter: MagicMock,
        mock_monthly_scheduled_event: MagicMock,
        mock_get_next_schedule_date: MagicMock,
        mock_get_schedule_expr_from_parameters: MagicMock,
    ):
        # mocks
        scheduled_event = ScheduledEvent(
            start_datetime=DEFAULT_DATETIME.replace(hour=0, minute=0, second=0, microsecond=0)
            + relativedelta(days=1),
            schedule_method=EndOfMonthSchedule(hour=1, minute=2, second=3, day=1),
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"interest_application_frequency": "monthly"}
        )
        mock_monthly_scheduled_event.return_value = scheduled_event
        # feature call
        actual_schedules = interest_application.scheduled_events(
            vault=sentinel.vault, reference_datetime=DEFAULT_DATETIME
        )
        # assertions
        mock_monthly_scheduled_event.assert_called_once_with(
            vault=sentinel.vault,
            start_datetime=DEFAULT_DATETIME.replace(hour=0, minute=0, second=0, microsecond=0)
            + relativedelta(days=1),
            parameter_prefix="interest_application",
        )

        self.assertDictEqual(actual_schedules, {APPLICATION_EVENT: scheduled_event})
        mock_get_next_schedule_date.assert_not_called()
        mock_get_schedule_expr_from_parameters.assert_not_called()

    def test_scheduled_events_quarterly_frequency(
        self,
        mock_get_parameter: MagicMock,
        mock_monthly_scheduled_event: MagicMock,
        mock_get_next_schedule_date: MagicMock,
        mock_get_schedule_expr_from_parameters: MagicMock,
    ):
        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"interest_application_frequency": "quarterly", "interest_application_day": "1"}
        )
        mock_get_next_schedule_date.return_value = DEFAULT_DATETIME + relativedelta(months=3)
        mock_get_schedule_expr_from_parameters.return_value = SentinelScheduleExpression(
            "interest_expr"
        )
        # feature call
        actual_schedules = interest_application.scheduled_events(
            vault=sentinel.vault, reference_datetime=DEFAULT_DATETIME
        )
        # assertions
        mock_get_parameter.assert_has_calls(
            [
                call(sentinel.vault, name="interest_application_frequency", is_union=True),
                call(sentinel.vault, name="interest_application_day"),
            ]
        )
        mock_get_next_schedule_date.assert_called_once_with(
            start_date=DEFAULT_DATETIME, schedule_frequency="quarterly", intended_day=1
        )
        mock_get_schedule_expr_from_parameters.assert_called_once_with(
            vault=sentinel.vault, parameter_prefix="interest_application", day=1, month=4, year=2019
        )
        self.assertDictEqual(
            actual_schedules,
            {
                APPLICATION_EVENT: ScheduledEvent(
                    start_datetime=DEFAULT_DATETIME + relativedelta(days=1),
                    expression=SentinelScheduleExpression("interest_expr"),
                )
            },
        )
        mock_monthly_scheduled_event.assert_not_called()

    def test_scheduled_events_annually_frequency_not_february(
        self,
        mock_get_parameter: MagicMock,
        mock_monthly_scheduled_event: MagicMock,
        mock_get_next_schedule_date: MagicMock,
        mock_get_schedule_expr_from_parameters: MagicMock,
    ):
        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"interest_application_frequency": "annually", "interest_application_day": "1"}
        )
        mock_get_next_schedule_date.return_value = DEFAULT_DATETIME + relativedelta(years=1)
        mock_get_schedule_expr_from_parameters.return_value = SentinelScheduleExpression(
            "interest_expr"
        )
        # feature call
        actual_schedules = interest_application.scheduled_events(
            vault=sentinel.vault, reference_datetime=DEFAULT_DATETIME
        )
        # assertions
        self.assertDictEqual(
            actual_schedules,
            {
                APPLICATION_EVENT: ScheduledEvent(
                    start_datetime=DEFAULT_DATETIME + relativedelta(months=1),
                    expression=SentinelScheduleExpression("interest_expr"),
                )
            },
        )
        mock_get_next_schedule_date.assert_called_once_with(
            start_date=DEFAULT_DATETIME, schedule_frequency="annually", intended_day=1
        )
        mock_get_schedule_expr_from_parameters.assert_called_once_with(
            vault=sentinel.vault, parameter_prefix="interest_application", day=1, month=1, year=None
        )
        mock_monthly_scheduled_event.assert_not_called()

    def test_scheduled_events_annually_frequency_in_february(
        self,
        mock_get_parameter: MagicMock,
        mock_monthly_scheduled_event: MagicMock,
        mock_get_next_schedule_date: MagicMock,
        mock_get_schedule_expr_from_parameters: MagicMock,
    ):
        # mocks
        test_datetime = datetime(year=2019, month=2, day=1, tzinfo=ZoneInfo("UTC"))
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"interest_application_frequency": "annually", "interest_application_day": "5"}
        )
        mock_get_next_schedule_date.return_value = test_datetime + relativedelta(years=1, day=5)
        mock_get_schedule_expr_from_parameters.return_value = SentinelScheduleExpression(
            "interest_expr"
        )
        # feature call
        actual_schedules = interest_application.scheduled_events(
            vault=sentinel.vault, reference_datetime=test_datetime
        )
        # assertions
        self.assertDictEqual(
            actual_schedules,
            {
                APPLICATION_EVENT: ScheduledEvent(
                    start_datetime=test_datetime + relativedelta(months=1),
                    expression=SentinelScheduleExpression("interest_expr"),
                )
            },
        )
        mock_get_next_schedule_date.assert_called_once_with(
            start_date=test_datetime, schedule_frequency="annually", intended_day=5
        )
        mock_get_schedule_expr_from_parameters.assert_called_once_with(
            vault=sentinel.vault, parameter_prefix="interest_application", day=5, month=2, year=None
        )
        mock_monthly_scheduled_event.assert_not_called()


@patch.object(interest_application.utils, "standard_instruction_details")
@patch.object(interest_application.accruals, "accrual_application_custom_instruction")
@patch.object(interest_application.utils, "sum_balances")
@patch.object(interest_application.utils, "get_parameter")
class TestApplyInterestApplication(FeatureTest):
    def test_generate_default_address_application_postings(
        self,
        mock_get_parameter: MagicMock,
        mock_sum_balances: MagicMock,
        mock_accruals_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "application_precision": 2,
                "interest_paid_account": INTEREST_PAID_ACCOUNT,
                "interest_received_account": INTEREST_RECEIVED_ACCOUNT,
                "denomination": DEFAULT_DENOMINATION,
                "accrued_interest_payable_account": "interest_payable_internal_acc",
                "accrued_interest_receivable_account": "interest_receivable_internal_acc",
            },
        )
        mock_sum_balances.side_effect = [Decimal("1.23654"), Decimal("2.23654")]
        mock_accruals_custom_instruction.side_effect = [
            [SentinelCustomInstruction("dummy")],
            [SentinelCustomInstruction("dummy2")],
        ]
        mock_standard_instruction_details.side_effect = [sentinel.value, sentinel.value]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                interest_application.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(  # noqa: E501
                    "balances_obs"
                )
            }
        )
        # feature call
        custom_instructions = interest_application.apply_interest(
            vault=mock_vault, account_type="dummy_account"
        )
        # assertions
        mock_accruals_custom_instruction.assert_has_calls(
            [
                call(
                    customer_account="default_account",
                    denomination=DEFAULT_DENOMINATION,
                    application_amount=Decimal("1.24"),
                    accrual_amount=Decimal("1.23654"),
                    instruction_details=sentinel.value,
                    accrual_customer_address=ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    accrual_internal_account="interest_receivable_internal_acc",
                    application_customer_address=DEFAULT_ADDRESS,
                    application_internal_account=INTEREST_RECEIVED_ACCOUNT,
                    payable=False,
                ),
                call(
                    customer_account="default_account",
                    denomination=DEFAULT_DENOMINATION,
                    application_amount=Decimal("2.24"),
                    accrual_amount=Decimal("2.23654"),
                    instruction_details=sentinel.value,
                    accrual_customer_address=ACCRUED_INTEREST_PAYABLE_ADDRESS,
                    accrual_internal_account="interest_payable_internal_acc",
                    application_customer_address=DEFAULT_ADDRESS,
                    application_internal_account=INTEREST_PAID_ACCOUNT,
                    payable=True,
                ),
            ]
        )
        self.assertEqual(len(custom_instructions), 2)
        self.assertEqual(
            custom_instructions,
            [SentinelCustomInstruction("dummy"), SentinelCustomInstruction("dummy2")],
        )

    def test_generate_default_address_application_postings_balances_provided(
        self,
        mock_get_parameter: MagicMock,
        mock_sum_balances: MagicMock,
        mock_accruals_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "application_precision": 2,
                "interest_paid_account": INTEREST_PAID_ACCOUNT,
                "interest_received_account": INTEREST_RECEIVED_ACCOUNT,
                "denomination": DEFAULT_DENOMINATION,
                "accrued_interest_payable_account": "interest_payable_internal_acc",
                "accrued_interest_receivable_account": "interest_receivable_internal_acc",
            },
        )
        mock_sum_balances.side_effect = [Decimal("1.23654"), Decimal("2.23654")]
        mock_accruals_custom_instruction.side_effect = [
            [SentinelCustomInstruction("dummy")],
            [SentinelCustomInstruction("dummy2")],
        ]
        mock_standard_instruction_details.side_effect = [sentinel.value, sentinel.value]
        mock_vault = self.create_mock()

        # feature call with balances provided
        result = interest_application.apply_interest(
            vault=mock_vault,
            account_type="dummy_account",
            balances=sentinel.balances,
        )
        self.assertEqual(
            result,
            [SentinelCustomInstruction("dummy"), SentinelCustomInstruction("dummy2")],
        )

        # call assertions
        mock_sum_balances.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances,
                    addresses=[ACCRUED_INTEREST_RECEIVABLE_ADDRESS],
                    denomination=DEFAULT_DENOMINATION,
                ),
                call(
                    balances=sentinel.balances,
                    addresses=[ACCRUED_INTEREST_PAYABLE_ADDRESS],
                    denomination=DEFAULT_DENOMINATION,
                ),
            ]
        )
        mock_accruals_custom_instruction.assert_has_calls(
            [
                call(
                    customer_account="default_account",
                    denomination=DEFAULT_DENOMINATION,
                    application_amount=Decimal("1.24"),
                    accrual_amount=Decimal("1.23654"),
                    instruction_details=sentinel.value,
                    accrual_customer_address=ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    accrual_internal_account="interest_receivable_internal_acc",
                    application_customer_address=DEFAULT_ADDRESS,
                    application_internal_account=INTEREST_RECEIVED_ACCOUNT,
                    payable=False,
                ),
                call(
                    customer_account="default_account",
                    denomination=DEFAULT_DENOMINATION,
                    application_amount=Decimal("2.24"),
                    accrual_amount=Decimal("2.23654"),
                    instruction_details=sentinel.value,
                    accrual_customer_address=ACCRUED_INTEREST_PAYABLE_ADDRESS,
                    accrual_internal_account="interest_payable_internal_acc",
                    application_customer_address=DEFAULT_ADDRESS,
                    application_internal_account=INTEREST_PAID_ACCOUNT,
                    payable=True,
                ),
            ]
        )


@patch.object(interest_application, "scheduled_events")
@patch.object(interest_application.utils, "get_parameter")
class TestUpdateNextSchedule(FeatureTest):
    def test_update_next_schedule_execution_monthly(
        self, mock_get_parameter: MagicMock, mock_scheduled_events: MagicMock
    ):
        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"interest_application_frequency": "monthly"}
        )
        # feature call
        feature_result = interest_application.update_next_schedule_execution(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
        # assertions
        self.assertEquals(feature_result, None)
        mock_scheduled_events.assert_not_called()

    def test_update_next_schedule_execution_quarterly(
        self, mock_get_parameter: MagicMock, mock_scheduled_events: MagicMock
    ):
        # mocks
        mock_scheduled_events.return_value = {
            APPLICATION_EVENT: ScheduledEvent(
                start_datetime=DEFAULT_DATETIME,
                expression=ScheduleExpression(
                    year=2019, month=4, day=1, hour=1, minute=2, second=3
                ),
            )
        }
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"interest_application_frequency": "quarterly", "interest_application_day": "1"}
        )
        # feature call
        feature_result = interest_application.update_next_schedule_execution(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
        # assertions
        self.assertEquals(
            feature_result,
            UpdateAccountEventTypeDirective(
                event_type=APPLICATION_EVENT,
                expression=mock_scheduled_events.return_value[APPLICATION_EVENT].expression,
            ),
        )
        mock_scheduled_events.assert_called_once_with(
            vault=sentinel.vault, reference_datetime=DEFAULT_DATETIME
        )

    def test_update_next_schedule_execution_annually_is_february_not_leap(
        self, mock_get_parameter: MagicMock, mock_scheduled_events: MagicMock
    ):
        test_start_date = datetime(year=2020, month=2, day=1, tzinfo=ZoneInfo("UTC"))
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"interest_application_frequency": "annually", "interest_application_day": "1"}
        )
        mock_scheduled_events.return_value = {
            "APPLY_INTEREST": ScheduledEvent(
                start_datetime=test_start_date, expression=SentinelScheduleExpression("expression")
            )
        }

        update_result = interest_application.update_next_schedule_execution(
            vault=sentinel.vault, effective_datetime=test_start_date
        )

        self.assertIsNone(update_result)
        mock_scheduled_events.assert_not_called()

    def test_update_next_schedule_execution_annually_is_february_leap(
        self, mock_get_parameter: MagicMock, mock_scheduled_events: MagicMock
    ):
        test_start_date = datetime(year=2020, month=2, day=1, tzinfo=ZoneInfo("UTC"))
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"interest_application_frequency": "annually", "interest_application_day": "29"}
        )
        mock_scheduled_events.return_value = {
            "APPLY_INTEREST": ScheduledEvent(
                start_datetime=test_start_date, expression=SentinelScheduleExpression("expression")
            )
        }

        update_result = interest_application.update_next_schedule_execution(
            vault=sentinel.vault, effective_datetime=test_start_date
        )
        expected_result = UpdateAccountEventTypeDirective(
            event_type=APPLICATION_EVENT,
            expression=SentinelScheduleExpression("expression"),
        )

        self.assertEqual(update_result, expected_result)
        mock_scheduled_events.assert_called_once_with(
            vault=sentinel.vault, reference_datetime=test_start_date
        )

    def test_update_next_schedule_execution_annually_is_not_february(
        self, mock_get_parameter: MagicMock, mock_scheduled_events: MagicMock
    ):
        # mocks
        test_start_date = datetime(year=2020, month=1, day=28, tzinfo=ZoneInfo("UTC"))
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"interest_application_frequency": "annually", "interest_application_day": "1"}
        )
        # feature call
        feature_result = interest_application.update_next_schedule_execution(
            vault=sentinel.vault, effective_datetime=test_start_date
        )
        # assertions
        self.assertIsNone(feature_result)
        mock_scheduled_events.assert_not_called()
