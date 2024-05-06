# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from unittest.mock import MagicMock, patch, sentinel

# library
import library.mortgage.contracts.template.mortgage as mortgage
from library.mortgage.test.unit.test_mortgage_common import MortgageTestBase

# contracts api
from contracts_api import PostParameterChangeHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PostParameterChangeHookResult,
    ScheduleSkip,
    UpdateAccountEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelEndOfMonthSchedule,
    SentinelUpdateAccountEventTypeDirective,
)


@patch.object(mortgage, "_handle_due_amount_calculation_day_change")
class PostParameterChangeHookTest(MortgageTestBase):
    def test_no_event_directives_returns_none(
        self, mock_handle_due_amount_calculation_day_change: MagicMock
    ):
        # construct mocks
        mock_handle_due_amount_calculation_day_change.return_value = []

        # run function
        result = mortgage.post_parameter_change_hook(
            vault=sentinel.vault, hook_arguments=sentinel.hook_arguments
        )
        self.assertIsNone(result)
        mock_handle_due_amount_calculation_day_change.assert_called_once_with(
            sentinel.vault, sentinel.hook_arguments
        )

    def test_update_due_amount_calc_day_directives_returned(
        self, mock_handle_due_amount_calculation_day_change: MagicMock
    ):
        # construct mocks
        due_amount_calc_update_directives = [
            SentinelUpdateAccountEventTypeDirective("due_amount_calc")
        ]
        mock_handle_due_amount_calculation_day_change.return_value = (
            due_amount_calc_update_directives
        )
        # construct expected result
        expected_result = PostParameterChangeHookResult(
            update_account_event_type_directives=due_amount_calc_update_directives  # type:ignore
        )
        # run function
        result = mortgage.post_parameter_change_hook(
            vault=sentinel.vault, hook_arguments=sentinel.hook_arguments
        )
        self.assertEqual(result, expected_result)
        mock_handle_due_amount_calculation_day_change.assert_called_once_with(
            sentinel.vault, sentinel.hook_arguments
        )


@patch.object(mortgage, "_update_due_amount_calculation_day_schedule")
@patch.object(mortgage, "_calculate_next_due_amount_calculation_datetime")
class HandleDueAmountCalculationDayChangeTest(MortgageTestBase):
    updated_parameter_values = {
        mortgage.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: sentinel.parameter
    }

    def test_due_amount_calculation_day_unchanged_returns_empty_list(
        self,
        mock_calculate_next_due_amount_calculation_datetime: MagicMock,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
    ):
        # construct mocks
        mock_vault = sentinel.vault

        # run function
        hook_args = PostParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            old_parameter_values=sentinel.old_parameter_values,
            updated_parameter_values={"other_parameter": sentinel.value},
        )
        result = mortgage._handle_due_amount_calculation_day_change(mock_vault, hook_args)
        self.assertListEqual(result, [])
        mock_calculate_next_due_amount_calculation_datetime.assert_not_called()
        mock_update_due_amount_calculation_day_schedule.assert_not_called()

    def test_due_amount_calculation_day_updated_returns_update_event_directives(
        self,
        mock_calculate_next_due_amount_calculation_datetime: MagicMock,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
    ):
        # construct mocks
        last_execution_datetime = datetime(2018, 12, 15)
        update_due_amount_calc_directive = SentinelUpdateAccountEventTypeDirective(
            "due_amount_calc"
        )
        mock_vault = self.create_mock(
            last_execution_datetimes={"DUE_AMOUNT_CALCULATION": last_execution_datetime}
        )
        mock_calculate_next_due_amount_calculation_datetime.return_value = (
            sentinel.next_due_amount_calculation_datetime
        )
        mock_update_due_amount_calculation_day_schedule.return_value = [
            update_due_amount_calc_directive
        ]

        # construct expected result
        expected_result = [update_due_amount_calc_directive]

        # run function
        hook_args = PostParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            old_parameter_values=sentinel.old_parameter_values,
            updated_parameter_values={"due_amount_calculation_day": 5},
        )
        result = mortgage._handle_due_amount_calculation_day_change(mock_vault, hook_args)
        self.assertEqual(result, expected_result)
        mock_calculate_next_due_amount_calculation_datetime.assert_called_once_with(
            mock_vault,
            DEFAULT_DATETIME,
            last_execution_datetime,
            5,
        )
        mock_update_due_amount_calculation_day_schedule.assert_called_once_with(
            vault=mock_vault,
            schedule_start_datetime=sentinel.next_due_amount_calculation_datetime,
            due_amount_calculation_day=5,
        )


@patch.object(mortgage.utils, "get_end_of_month_schedule_from_parameters")
class UpdateDueAmountCalculationDayScheduleTest(MortgageTestBase):
    def test_directive_is_returned(self, mock_get_end_of_month_schedule: MagicMock):
        # construct mocks
        mock_get_end_of_month_schedule.return_value = SentinelEndOfMonthSchedule("due_amount_calc")

        # construct expected result
        expected_result = [
            UpdateAccountEventTypeDirective(
                event_type=mortgage.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                schedule_method=SentinelEndOfMonthSchedule("due_amount_calc"),
                skip=ScheduleSkip(end=DEFAULT_DATETIME - relativedelta(seconds=1)),
            )
        ]

        # run function
        result = mortgage._update_due_amount_calculation_day_schedule(
            sentinel.vault, schedule_start_datetime=DEFAULT_DATETIME, due_amount_calculation_day=5
        )
        self.assertEqual(result, expected_result)
        mock_get_end_of_month_schedule.assert_called_once_with(
            vault=sentinel.vault,
            parameter_prefix=mortgage.due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX,
            day=5,
        )
