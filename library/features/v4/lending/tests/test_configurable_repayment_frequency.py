# standard libs
from datetime import datetime
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.lending import configurable_repayment_frequency, due_amount_calculation

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest

# sentinels
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    EndOfMonthSchedule,
    ScheduledEvent,
    ScheduleExpression,
    ScheduleFailover,
)

UTC_ZONE = ZoneInfo("UTC")
PARAM_REPAYMENT_FREQUENCY = configurable_repayment_frequency.PARAM_REPAYMENT_FREQUENCY


class ConfigurableRepaymentFrequencyTestCommon(FeatureTest):
    total_repayment_count = 4
    account_creation_date = datetime(2022, 1, 5, 1, 0, 0, tzinfo=UTC_ZONE)


@patch.object(configurable_repayment_frequency.utils, "get_schedule_time_from_parameters")
class GetDueAmountCalculationSchedule(ConfigurableRepaymentFrequencyTestCommon):
    first_due_amount_calculation_date = datetime(2023, 1, 1, 1, 2, 3, tzinfo=UTC_ZONE)
    expected_schedule_start_date = datetime(2022, 12, 31, 23, 59, 59, tzinfo=UTC_ZONE)
    hour = 23
    minute = 59
    second = 59
    time_tuple = (hour, minute, second)

    def test_weekly_schedule(self, mock_get_schedule_time_from_parameters: MagicMock):
        mock_get_schedule_time_from_parameters.return_value = self.time_tuple
        result = configurable_repayment_frequency.get_due_amount_calculation_schedule(
            vault=sentinel.vault,
            first_due_amount_calculation_datetime=self.first_due_amount_calculation_date,
            repayment_frequency=configurable_repayment_frequency.WEEKLY,
        )
        expected = {
            due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: ScheduledEvent(
                start_datetime=self.expected_schedule_start_date,
                expression=ScheduleExpression(
                    hour=self.hour,
                    minute=self.minute,
                    second=self.second,
                    day_of_week=self.first_due_amount_calculation_date.weekday(),
                ),
            ),
        }
        self.assertEqual(result, expected)

    def test_monthly_schedule(self, mock_get_schedule_time_from_parameters):
        mock_get_schedule_time_from_parameters.return_value = self.time_tuple
        result = configurable_repayment_frequency.get_due_amount_calculation_schedule(
            vault=sentinel.vault,
            first_due_amount_calculation_datetime=self.first_due_amount_calculation_date,
            repayment_frequency=configurable_repayment_frequency.MONTHLY,
        )
        expected = {
            due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: ScheduledEvent(
                start_datetime=self.expected_schedule_start_date,
                schedule_method=EndOfMonthSchedule(
                    day=self.first_due_amount_calculation_date.day,
                    hour=self.hour,
                    minute=self.minute,
                    second=self.second,
                    failover=ScheduleFailover.FIRST_VALID_DAY_BEFORE,
                ),
            ),
        }
        self.assertEqual(result, expected)

    def test_fortnightly_schedule(self, mock_get_schedule_time_from_parameters):
        mock_get_schedule_time_from_parameters.return_value = self.time_tuple
        result = configurable_repayment_frequency.get_due_amount_calculation_schedule(
            vault=sentinel.vault,
            first_due_amount_calculation_datetime=self.first_due_amount_calculation_date,
            repayment_frequency=configurable_repayment_frequency.FORTNIGHTLY,
        )
        expected = {
            due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: ScheduledEvent(
                start_datetime=self.expected_schedule_start_date,
                expression=ScheduleExpression(
                    hour=self.hour,
                    minute=self.minute,
                    second=self.second,
                    day=self.first_due_amount_calculation_date.day,
                ),
            ),
        }
        self.assertEqual(result, expected)


@patch.object(configurable_repayment_frequency.utils, "one_off_schedule_expression")
class GetNextFortnightlyScheduleExpressionTest(ConfigurableRepaymentFrequencyTestCommon):
    def test_next_fortnightly_schedule_expression(self, mock_one_off_schedule_expression):
        mock_one_off_schedule_expression.return_value = sentinel.schedule_expression
        result = configurable_repayment_frequency.get_next_fortnightly_schedule_expression(
            effective_date=self.account_creation_date,
        )
        self.assertEqual(result, sentinel.schedule_expression)
        next_due_date = datetime(2022, 1, 19, 1, 0, 0, tzinfo=UTC_ZONE)
        mock_one_off_schedule_expression.assert_called_once_with(next_due_date)


class GetNextDueAmountCalculationDateTest(ConfigurableRepaymentFrequencyTestCommon):
    def setUp(self):
        self.mock_vault = self.create_mock(
            creation_date=self.account_creation_date,
        )

    def test_next_repayment_date_when_queried_on_repayment_date(self):
        next_repayment_date = configurable_repayment_frequency.get_next_due_amount_calculation_date(
            vault=self.mock_vault,
            effective_date=datetime(2022, 1, 12, tzinfo=UTC_ZONE),
            total_repayment_count=self.total_repayment_count,
            repayment_frequency="weekly",
        )
        self.assertEqual(next_repayment_date, datetime(2022, 1, 12, tzinfo=UTC_ZONE))

    def test_weekly_next_repayment_date(self):
        next_repayment_date = configurable_repayment_frequency.get_next_due_amount_calculation_date(
            vault=self.mock_vault,
            effective_date=datetime(2022, 1, 6, tzinfo=UTC_ZONE),
            total_repayment_count=self.total_repayment_count,
            repayment_frequency="weekly",
        )
        self.assertEqual(
            next_repayment_date,
            datetime(2022, 1, 12, tzinfo=UTC_ZONE),
        )

    def test_weekly_next_repayment_date_for_last_repayment_date(self):
        next_repayment_date = configurable_repayment_frequency.get_next_due_amount_calculation_date(
            vault=self.mock_vault,
            effective_date=datetime(2022, 1, 27, tzinfo=UTC_ZONE),
            total_repayment_count=self.total_repayment_count,
            repayment_frequency="weekly",
        )
        self.assertEqual(
            next_repayment_date,
            datetime(2022, 2, 2, tzinfo=UTC_ZONE),
        )

    def test_weekly_next_repayment_date_after_last_repayment_date(self):
        next_repayment_date = configurable_repayment_frequency.get_next_due_amount_calculation_date(
            vault=self.mock_vault,
            effective_date=datetime(2022, 2, 20, tzinfo=UTC_ZONE),
            total_repayment_count=self.total_repayment_count,
            repayment_frequency="weekly",
        )
        self.assertEqual(
            next_repayment_date,
            datetime(2022, 2, 2, tzinfo=UTC_ZONE),
        )

    def test_fortnightly_next_repayment_date(self):
        next_repayment_date = configurable_repayment_frequency.get_next_due_amount_calculation_date(
            vault=self.mock_vault,
            effective_date=datetime(2022, 1, 6, tzinfo=UTC_ZONE),
            total_repayment_count=self.total_repayment_count,
            repayment_frequency="fortnightly",
        )
        self.assertEqual(
            next_repayment_date,
            datetime(2022, 1, 19, tzinfo=UTC_ZONE),
        )

    def test_fortnightly_next_repayment_date_for_last_repayment_date(self):
        next_repayment_date = configurable_repayment_frequency.get_next_due_amount_calculation_date(
            vault=self.mock_vault,
            effective_date=datetime(2022, 2, 17, tzinfo=UTC_ZONE),
            total_repayment_count=self.total_repayment_count,
            repayment_frequency="fortnightly",
        )
        self.assertEqual(
            next_repayment_date,
            datetime(2022, 3, 2, tzinfo=UTC_ZONE),
        )

    def test_fortnightly_next_repayment_date_after_last_repayment_date(self):
        next_repayment_date = configurable_repayment_frequency.get_next_due_amount_calculation_date(
            vault=self.mock_vault,
            effective_date=datetime(2022, 3, 10, tzinfo=UTC_ZONE),
            total_repayment_count=self.total_repayment_count,
            repayment_frequency="fortnightly",
        )
        self.assertEqual(
            next_repayment_date,
            datetime(2022, 3, 2, tzinfo=UTC_ZONE),
        )

    def test_monthly_next_repayment_date(self):
        next_repayment_date = configurable_repayment_frequency.get_next_due_amount_calculation_date(
            vault=self.mock_vault,
            effective_date=datetime(2022, 1, 6, tzinfo=UTC_ZONE),
            total_repayment_count=self.total_repayment_count,
            repayment_frequency="monthly",
        )
        self.assertEqual(
            next_repayment_date,
            datetime(2022, 2, 5, tzinfo=UTC_ZONE),
        )

    def test_monthly_next_repayment_date_for_last_repayment_date(self):
        next_repayment_date = configurable_repayment_frequency.get_next_due_amount_calculation_date(
            vault=self.mock_vault,
            effective_date=datetime(2022, 4, 17, tzinfo=UTC_ZONE),
            total_repayment_count=self.total_repayment_count,
            repayment_frequency="monthly",
        )
        self.assertEqual(
            next_repayment_date,
            datetime(2022, 5, 5, tzinfo=UTC_ZONE),
        )

    def test_monthly_next_repayment_date_after_last_repayment_date(self):
        next_repayment_date = configurable_repayment_frequency.get_next_due_amount_calculation_date(
            vault=self.mock_vault,
            effective_date=datetime(2022, 5, 10, tzinfo=UTC_ZONE),
            total_repayment_count=self.total_repayment_count,
            repayment_frequency="monthly",
        )
        self.assertEqual(
            next_repayment_date,
            datetime(2022, 5, 5, tzinfo=UTC_ZONE),
        )

    def test_loan_end_date(self):
        loan_end_date = configurable_repayment_frequency.get_next_due_amount_calculation_date(
            vault=self.mock_vault,
            effective_date=datetime.max.replace(tzinfo=UTC_ZONE),
            total_repayment_count=self.total_repayment_count,
            repayment_frequency="monthly",
        )
        self.assertEqual(
            loan_end_date,
            datetime(2022, 5, 5, tzinfo=UTC_ZONE),
        )


class GetElapsedAndRemainingTermsTest(ConfigurableRepaymentFrequencyTestCommon):
    effective_date = datetime(2022, 2, 20, tzinfo=UTC_ZONE)

    def test_weekly_elapsed_and_remaining_terms(self):
        total_repayment_count = 16
        elapsed_and_remaining_terms = (
            configurable_repayment_frequency.get_elapsed_and_remaining_terms(
                account_creation_date=self.account_creation_date,
                effective_date=self.effective_date,
                total_repayment_count=total_repayment_count,
                repayment_frequency="weekly",
            )
        )
        self.assertTupleEqual(
            elapsed_and_remaining_terms,
            configurable_repayment_frequency.LoanTerms(elapsed=6, remaining=10),
        )

    def test_fortnightly_elapsed_and_remaining_terms(self):
        total_repayment_count = 8
        elapsed_and_remaining_terms = (
            configurable_repayment_frequency.get_elapsed_and_remaining_terms(
                account_creation_date=self.account_creation_date,
                effective_date=self.effective_date,
                total_repayment_count=total_repayment_count,
                repayment_frequency="fortnightly",
            )
        )
        self.assertTupleEqual(
            elapsed_and_remaining_terms,
            configurable_repayment_frequency.LoanTerms(elapsed=3, remaining=5),
        )

    def test_monthly_elapsed_and_remaining_terms(self):
        elapsed_and_remaining_terms = (
            configurable_repayment_frequency.get_elapsed_and_remaining_terms(
                account_creation_date=self.account_creation_date,
                effective_date=self.effective_date,
                total_repayment_count=self.total_repayment_count,
                repayment_frequency="monthly",
            )
        )
        self.assertTupleEqual(
            elapsed_and_remaining_terms,
            configurable_repayment_frequency.LoanTerms(elapsed=1, remaining=3),
        )


@patch.object(configurable_repayment_frequency.utils, "get_parameter")
class GetParametersTest(ConfigurableRepaymentFrequencyTestCommon):
    def test_get_repayment_frequency_parameter(self, mock_get_parameter: MagicMock):
        repayment_frequency_parameter = "dummy_frequency"

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={PARAM_REPAYMENT_FREQUENCY: repayment_frequency_parameter},
        )

        result = configurable_repayment_frequency.get_repayment_frequency_parameter(
            vault=sentinel.vault
        )

        self.assertEqual(
            repayment_frequency_parameter,
            result,
        )
