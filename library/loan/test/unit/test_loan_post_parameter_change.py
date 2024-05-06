# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from unittest.mock import MagicMock, patch, sentinel

# library
from library.loan.contracts.template import loan
from library.loan.test.unit.test_loan_common import LoanTestBase

# contracts api
from contracts_api import PostParameterChangeHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PostParameterChangeHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelUpdateAccountEventTypeDirective,
)


@patch.object(loan, "_handle_due_amount_calculation_day_change")
class PostParameterChangeHookTest(LoanTestBase):
    def test_no_event_directives_returns_none(
        self,
        mock_handle_due_amount_calculation_day_change: MagicMock,
    ):
        # construct mocks
        mock_handle_due_amount_calculation_day_change.return_value = []

        # run function
        hook_args = PostParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            old_parameter_values=sentinel.old_parameter_values,
            updated_parameter_values={"other_parameter": sentinel.value},
        )
        result = loan.post_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)
        mock_handle_due_amount_calculation_day_change.assert_not_called()

    @patch.object(loan, "_get_amortisation_feature")
    def test_update_due_amount_calc_day_directives_returned(
        self,
        mock_get_amortisation_feature: MagicMock,
        mock_handle_due_amount_calculation_day_change: MagicMock,
    ):
        # construct mocks
        due_amount_calc_update_directives = [
            SentinelUpdateAccountEventTypeDirective("due_amount_calc")
        ]
        mock_term_details = MagicMock(return_value=(sentinel.elapsed_term, sentinel.remaining_term))
        mock_handle_due_amount_calculation_day_change.return_value = (
            due_amount_calc_update_directives
        )
        mock_get_amortisation_feature.return_value = MagicMock(term_details=mock_term_details)

        # construct expected result
        expected_result = PostParameterChangeHookResult(
            update_account_event_type_directives=due_amount_calc_update_directives  # type: ignore
        )

        # run function
        hook_args = PostParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            old_parameter_values=sentinel.old_parameter_values,
            updated_parameter_values={"due_amount_calculation_day": sentinel.value},
        )
        result = loan.post_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)
        mock_handle_due_amount_calculation_day_change.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )
        mock_term_details.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            use_expected_term=True,
        )


@patch.object(loan, "_update_due_amount_calculation_day_schedule")
@patch.object(loan.due_amount_calculation, "get_next_due_amount_calculation_datetime")
class HandleDueAmountCalculationDayChangeTest(LoanTestBase):
    def test_directive_not_returned_when_last_execution_datetime_is_none(
        self,
        mock_get_next_due_amount_calculation_datetime: MagicMock,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
    ):
        # construct mocks
        last_execution_datetime = None
        mock_vault = self.create_mock(
            last_execution_datetimes={"DUE_AMOUNT_CALCULATION": last_execution_datetime}
        )
        mock_get_next_due_amount_calculation_datetime.return_value = datetime(2019, 1, 15)

        # run function
        result = loan._handle_due_amount_calculation_day_change(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )
        self.assertListEqual(result, [])
        mock_get_next_due_amount_calculation_datetime.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )
        mock_update_due_amount_calculation_day_schedule.assert_not_called()

    def test_directive_not_returned_when_new_schedule_date_is_last_execution_plus_1_month(
        self,
        mock_get_next_due_amount_calculation_datetime: MagicMock,
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
        mock_get_next_due_amount_calculation_datetime.return_value = datetime(2019, 1, 15)
        mock_update_due_amount_calculation_day_schedule.return_value = [
            update_due_amount_calc_directive
        ]

        # run function
        result = loan._handle_due_amount_calculation_day_change(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )
        self.assertListEqual(result, [])
        mock_get_next_due_amount_calculation_datetime.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )
        mock_update_due_amount_calculation_day_schedule.assert_not_called()

    def test_directive_returned_when_new_schedule_date_is_not_last_execution_plus_1_month(
        self,
        mock_get_next_due_amount_calculation_datetime: MagicMock,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
    ):
        # construct mocks
        last_execution_datetime = datetime(2018, 12, 5)
        update_due_amount_calc_directive = SentinelUpdateAccountEventTypeDirective(
            "due_amount_calc"
        )
        mock_vault = self.create_mock(
            last_execution_datetimes={"DUE_AMOUNT_CALCULATION": last_execution_datetime}
        )
        mock_get_next_due_amount_calculation_datetime.return_value = datetime(2019, 1, 15)
        mock_update_due_amount_calculation_day_schedule.return_value = [
            update_due_amount_calc_directive
        ]

        # construct expected result
        expected_result = [update_due_amount_calc_directive]

        # run function
        result = loan._handle_due_amount_calculation_day_change(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )
        self.assertEqual(result, expected_result)
        mock_get_next_due_amount_calculation_datetime.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=sentinel.elapsed_term,
            remaining_term=sentinel.remaining_term,
        )
        mock_update_due_amount_calculation_day_schedule.assert_called_once_with(
            vault=mock_vault,
            schedule_start_datetime=datetime(2019, 1, 15),
            due_amount_calculation_day=15,
        )
