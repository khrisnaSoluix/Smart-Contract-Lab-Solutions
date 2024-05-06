# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# library
import library.line_of_credit.supervisors.template.line_of_credit_supervisor as line_of_credit_supervisor  # noqa: E501
from library.line_of_credit.test.unit.test_line_of_credit_supervisor_common import (
    LineOfCreditSupervisorTestBase,
)

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import SupervisorScheduledEventHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    DEFAULT_HOOK_EXECUTION_ID,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    ParameterTimeseries,
    PostingInstructionsDirective,
    ScheduleSkip,
    SupervisorScheduledEventHookResult,
    Tside,
    UpdateAccountEventTypeDirective,
    UpdatePlanEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelAccountNotificationDirective,
    SentinelCustomInstruction,
    SentinelEndOfMonthSchedule,
    SentinelPostingInstructionsDirective,
    SentinelScheduleExpression,
    SentinelUpdatePlanEventTypeDirective,
)


@patch.object(line_of_credit_supervisor, "_get_loc_and_loan_supervisee_vault_objects")
class DummyEventTest(LineOfCreditSupervisorTestBase):
    def test_blank_hook_returns_none(
        self,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = None, []
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type="dummy_event",
            supervisee_pause_at_datetime={},
        )
        result = line_of_credit_supervisor.scheduled_event_hook(
            vault=sentinel.vault, hook_arguments=hook_arguments
        )
        self.assertIsNone(result)
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)


@patch.object(line_of_credit_supervisor, "_get_loc_and_loan_supervisee_vault_objects")
@patch.object(line_of_credit_supervisor.supervisor_utils, "get_supervisee_schedule_sync_updates")
class LocSupervisorScheduledEventHookTest(LineOfCreditSupervisorTestBase):
    def test_none_returned_when_no_plan_event_directives(
        self,
        mock_get_supervisee_schedule_sync_updates: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, []
        mock_get_supervisee_schedule_sync_updates.return_value = {}
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=line_of_credit_supervisor.supervisor_utils.SUPERVISEE_SCHEDULE_SYNC_EVENT,
            supervisee_pause_at_datetime={},
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertIsNone(result)
        mock_get_supervisee_schedule_sync_updates.assert_called_once_with(
            vault=sentinel.vault,
            supervisee_alias=line_of_credit_supervisor.LOC_ALIAS,
            hook_arguments=hook_arguments,
            schedule_updates_when_supervisees=line_of_credit_supervisor._schedule_updates_when_supervisees,  # noqa: E501
        )
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)

    def test_hook_result_returned_when_plan_event_directives(
        self,
        mock_get_supervisee_schedule_sync_updates: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, []
        mock_get_supervisee_schedule_sync_updates.return_value = [
            SentinelUpdatePlanEventTypeDirective("event_update")
        ]

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=line_of_credit_supervisor.supervisor_utils.SUPERVISEE_SCHEDULE_SYNC_EVENT,
            supervisee_pause_at_datetime={},
        )

        expected_result = SupervisorScheduledEventHookResult(
            update_plan_event_type_directives=[SentinelUpdatePlanEventTypeDirective("event_update")]
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_get_supervisee_schedule_sync_updates.assert_called_once_with(
            vault=sentinel.vault,
            supervisee_alias=line_of_credit_supervisor.LOC_ALIAS,
            hook_arguments=hook_arguments,
            schedule_updates_when_supervisees=line_of_credit_supervisor._schedule_updates_when_supervisees,  # noqa: E501
        )
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)


@patch.object(line_of_credit_supervisor.utils, "get_schedule_expression_from_parameters")
@patch.object(line_of_credit_supervisor.utils, "get_end_of_month_schedule_from_parameters")
class ScheduleUpdatesWhenSuperviseesTest(LineOfCreditSupervisorTestBase):
    event_type = line_of_credit_supervisor.supervisor_utils.SUPERVISEE_SCHEDULE_SYNC_EVENT

    def test_schedule_updates_when_supervisees(
        self,
        get_end_of_month_schedule_from_parameters: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
    ):
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )
        mock_get_schedule_expression_from_parameters.return_value = SentinelScheduleExpression(
            "expression"
        )
        get_end_of_month_schedule_from_parameters.return_value = SentinelEndOfMonthSchedule(
            "schedule"
        )
        expected = [
            UpdatePlanEventTypeDirective(
                event_type=line_of_credit_supervisor.interest_accrual_supervisor.ACCRUAL_EVENT,
                expression=SentinelScheduleExpression("expression"),
                skip=False,
            ),
            UpdatePlanEventTypeDirective(
                event_type=line_of_credit_supervisor.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,  # noqa: E501
                schedule_method=SentinelEndOfMonthSchedule("schedule"),
                skip=False,
            ),
        ]
        result = line_of_credit_supervisor._schedule_updates_when_supervisees(
            loc_vault=sentinel.vault, hook_arguments=hook_arguments
        )
        self.assertListEqual(expected, result)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=sentinel.vault,
            parameter_prefix=line_of_credit_supervisor.interest_accrual_supervisor.INTEREST_ACCRUAL_PREFIX,  # noqa: E501
        )
        get_end_of_month_schedule_from_parameters.assert_called_once_with(
            vault=sentinel.vault,
            parameter_prefix=line_of_credit_supervisor.due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX,  # noqa: E501
        )
        self.assertListEqual(result, expected)


@patch.object(line_of_credit_supervisor, "_get_loc_and_loan_supervisee_vault_objects")
@patch.object(line_of_credit_supervisor.repayment_holiday, "is_interest_accrual_blocked")
@patch.object(line_of_credit_supervisor, "_handle_accrue_interest")
@patch.object(line_of_credit_supervisor, "_handle_due_amount_calculation_day_change")
class AccrualEventTest(LineOfCreditSupervisorTestBase):
    event_type = line_of_credit_supervisor.interest_accrual_supervisor.ACCRUAL_EVENT

    def test_none_returned_when_interest_accrual_blocked(
        self,
        mock_handle_due_amount_calculation_day_change: MagicMock,
        mock_handle_accrue_interest: MagicMock,
        mock_is_interest_accrual_blocked: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, []
        mock_is_interest_accrual_blocked.return_value = True
        mock_handle_due_amount_calculation_day_change.return_value = [], {}
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertIsNone(result)
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_is_interest_accrual_blocked.assert_called_once_with(
            vault=sentinel.loc_vault, effective_datetime=DEFAULT_DATETIME
        )
        mock_handle_accrue_interest.assert_not_called()
        mock_handle_due_amount_calculation_day_change.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments
        )

    def test_none_returned_when_no_supervisee_pi_directives(
        self,
        mock_handle_due_amount_calculation_day_change: MagicMock,
        mock_handle_accrue_interest: MagicMock,
        mock_is_interest_accrual_blocked: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, []
        mock_is_interest_accrual_blocked.return_value = False
        mock_handle_accrue_interest.return_value = {}
        mock_handle_due_amount_calculation_day_change.return_value = [], {}
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertIsNone(result)
        mock_handle_accrue_interest.assert_called_once_with(
            vault=sentinel.vault,
            hook_arguments=hook_arguments,
            loc_vault=sentinel.loc_vault,
            loan_vaults=[],
        )
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_is_interest_accrual_blocked.assert_called_once_with(
            vault=sentinel.loc_vault, effective_datetime=DEFAULT_DATETIME
        )
        mock_handle_due_amount_calculation_day_change.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments
        )

    def test_hook_result_returned_when_supervisee_pi_directives(
        self,
        mock_handle_due_amount_calculation_day_change: MagicMock,
        mock_handle_accrue_interest: MagicMock,
        mock_is_interest_accrual_blocked: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, [
            sentinel.loan
        ]
        mock_is_interest_accrual_blocked.return_value = False
        supervisee_posting_instructions_directives = {
            sentinel.dummy1: [SentinelPostingInstructionsDirective("pi_directive_1")],
            sentinel.dummy2: [SentinelPostingInstructionsDirective("pi_directive_2")],
        }
        mock_handle_accrue_interest.return_value = supervisee_posting_instructions_directives
        mock_handle_due_amount_calculation_day_change.return_value = [], {}
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        expected_result = SupervisorScheduledEventHookResult(
            supervisee_posting_instructions_directives=supervisee_posting_instructions_directives
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_handle_accrue_interest.assert_called_once_with(
            vault=sentinel.vault,
            hook_arguments=hook_arguments,
            loc_vault=sentinel.loc_vault,
            loan_vaults=[sentinel.loan],
        )
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_is_interest_accrual_blocked.assert_called_once_with(
            vault=sentinel.loc_vault, effective_datetime=DEFAULT_DATETIME
        )
        mock_handle_due_amount_calculation_day_change.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments
        )

    def test_hook_result_returned_when_event_type_directives(
        self,
        mock_handle_due_amount_calculation_day_change: MagicMock,
        mock_handle_accrue_interest: MagicMock,
        mock_is_interest_accrual_blocked: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, [
            sentinel.loan
        ]
        mock_is_interest_accrual_blocked.return_value = False
        mock_handle_accrue_interest.return_value = {}
        plan_update_due_amount_calc_directive = [
            UpdatePlanEventTypeDirective(
                event_type=self.event_type,
                schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
                skip=ScheduleSkip(end=DEFAULT_DATETIME - relativedelta(seconds=1)),
            )
        ]
        acc_update_due_amount_calc_directive = {
            sentinel.account_id: [
                UpdateAccountEventTypeDirective(
                    event_type=self.event_type,
                    schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
                    skip=ScheduleSkip(end=DEFAULT_DATETIME - relativedelta(seconds=1)),
                )
            ]
        }
        mock_handle_due_amount_calculation_day_change.return_value = (
            plan_update_due_amount_calc_directive,
            acc_update_due_amount_calc_directive,
        )
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        expected_result = SupervisorScheduledEventHookResult(
            update_plan_event_type_directives=plan_update_due_amount_calc_directive,
            supervisee_update_account_event_type_directives=acc_update_due_amount_calc_directive,
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_handle_accrue_interest.assert_called_once_with(
            vault=sentinel.vault,
            hook_arguments=hook_arguments,
            loc_vault=sentinel.loc_vault,
            loan_vaults=[sentinel.loan],
        )
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_is_interest_accrual_blocked.assert_called_once_with(
            vault=sentinel.loc_vault, effective_datetime=DEFAULT_DATETIME
        )
        mock_handle_due_amount_calculation_day_change.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments
        )


@patch.object(line_of_credit_supervisor, "_get_loc_and_loan_supervisee_vault_objects")
@patch.object(line_of_credit_supervisor.repayment_holiday, "is_due_amount_calculation_blocked")
@patch.object(line_of_credit_supervisor, "_get_due_amount_custom_instructions")
@patch.object(line_of_credit_supervisor, "_get_repayment_due_notification")
@patch.object(line_of_credit_supervisor, "_update_check_overdue_schedule")
@patch.object(line_of_credit_supervisor, "_get_due_amount_calculation_day_parameter")
@patch.object(line_of_credit_supervisor, "_update_due_amount_calculation_day_schedule")
class DueAmountCalculationEventTest(LineOfCreditSupervisorTestBase):
    event_type = line_of_credit_supervisor.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT

    def test_due_calc_hook_returns_none_when_no_custom_instructions_or_notification(
        self,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
        mock_get_due_amount_calculation_day_parameter: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_get_repayment_due_notification: MagicMock,
        mock_get_due_amount_custom_instructions: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, [
            sentinel.loan
        ]
        mock_is_due_amount_calculation_blocked.return_value = False
        mock_get_due_amount_custom_instructions.return_value = [], Decimal("0")
        mock_get_repayment_due_notification.return_value = {}
        mock_update_check_overdue_schedule.return_value = []
        mock_get_due_amount_calculation_day_parameter.return_value = DEFAULT_DATETIME.day
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertIsNone(result)
        mock_get_due_amount_custom_instructions.assert_called_once_with(
            hook_arguments=hook_arguments, loc_vault=sentinel.loc_vault, loan_vaults=[sentinel.loan]
        )
        mock_get_repayment_due_notification.assert_called_once_with(
            loc_vault=sentinel.loc_vault,
            repayment_amount=Decimal("0"),
            hook_arguments=hook_arguments,
        )
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_update_check_overdue_schedule.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments
        )
        mock_update_check_overdue_schedule.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments
        )
        mock_update_due_amount_calculation_day_schedule.assert_not_called()
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.loc_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

    def test_due_calc_returns_notifications_when_no_instructions_but_zero_amount_notification(
        self,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
        mock_get_due_amount_calculation_day_parameter: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_get_repayment_due_notification: MagicMock,
        mock_get_due_amount_custom_instructions: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, [
            sentinel.loan
        ]
        mock_is_due_amount_calculation_blocked.return_value = False
        mock_get_due_amount_custom_instructions.return_value = [], Decimal("0")
        repayment_due_notification_directives = {
            "loc_account_id": [SentinelAccountNotificationDirective("repayment notification")]
        }
        mock_get_repayment_due_notification.return_value = repayment_due_notification_directives
        mock_update_check_overdue_schedule.return_value = []
        mock_get_due_amount_calculation_day_parameter.return_value = DEFAULT_DATETIME.day
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        expected_result = SupervisorScheduledEventHookResult(
            supervisee_posting_instructions_directives=None,
            supervisee_account_notification_directives=repayment_due_notification_directives,
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_get_due_amount_custom_instructions.assert_called_once_with(
            hook_arguments=hook_arguments, loc_vault=sentinel.loc_vault, loan_vaults=[sentinel.loan]
        )
        mock_get_repayment_due_notification.assert_called_once_with(
            loc_vault=sentinel.loc_vault,
            repayment_amount=Decimal("0"),
            hook_arguments=hook_arguments,
        )
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_update_check_overdue_schedule.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments
        )
        mock_update_check_overdue_schedule.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments
        )
        mock_update_due_amount_calculation_day_schedule.assert_not_called()
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.loc_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

    def test_due_calc_returns_directives_when_custom_instructions_and_no_due_calc_day_change(
        self,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
        mock_get_due_amount_calculation_day_parameter: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_get_repayment_due_notification: MagicMock,
        mock_get_due_amount_custom_instructions: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, [
            sentinel.loan
        ]
        mock_is_due_amount_calculation_blocked.return_value = False
        supervisee_posting_instructions_directives = {
            sentinel.dummy1: [SentinelPostingInstructionsDirective("pi_directive_1")],
            sentinel.dummy2: [SentinelPostingInstructionsDirective("pi_directive_2")],
        }
        mock_get_due_amount_custom_instructions.return_value = (
            supervisee_posting_instructions_directives,
            sentinel.repayment_amount,
        )
        repayment_due_notification_directives = {
            "loc_account_id": [SentinelAccountNotificationDirective("repayment notification")]
        }
        mock_get_repayment_due_notification.return_value = repayment_due_notification_directives
        update_plan_event_type_directives = [SentinelUpdatePlanEventTypeDirective("event_update")]
        mock_update_check_overdue_schedule.return_value = update_plan_event_type_directives
        mock_get_due_amount_calculation_day_parameter.return_value = DEFAULT_DATETIME.day
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        expected_result = SupervisorScheduledEventHookResult(
            update_plan_event_type_directives=update_plan_event_type_directives,
            supervisee_posting_instructions_directives=supervisee_posting_instructions_directives,
            supervisee_account_notification_directives=repayment_due_notification_directives,
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_get_due_amount_custom_instructions.assert_called_once_with(
            hook_arguments=hook_arguments, loc_vault=sentinel.loc_vault, loan_vaults=[sentinel.loan]
        )
        mock_get_repayment_due_notification.assert_called_once_with(
            loc_vault=sentinel.loc_vault,
            repayment_amount=sentinel.repayment_amount,
            hook_arguments=hook_arguments,
        )
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_update_check_overdue_schedule.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments
        )
        mock_update_check_overdue_schedule.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments
        )
        mock_update_due_amount_calculation_day_schedule.assert_not_called()
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.loc_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

    def test_due_calc_returns_directives_when_due_calc_day_ne_effective_datetime_day(
        self,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
        mock_get_due_amount_calculation_day_parameter: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_get_repayment_due_notification: MagicMock,
        mock_get_due_amount_custom_instructions: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, [
            sentinel.loan
        ]
        mock_is_due_amount_calculation_blocked.return_value = False
        supervisee_posting_instructions_directives = {
            sentinel.dummy1: [SentinelPostingInstructionsDirective("pi_directive_1")],
            sentinel.dummy2: [SentinelPostingInstructionsDirective("pi_directive_2")],
        }
        mock_get_due_amount_custom_instructions.return_value = (
            supervisee_posting_instructions_directives,
            sentinel.repayment_amount,
        )
        repayment_due_notification_directives = {
            "loc_account_id": [SentinelAccountNotificationDirective("repayment notification")]
        }
        mock_get_repayment_due_notification.return_value = repayment_due_notification_directives
        update_plan_event_type_directives = [SentinelUpdatePlanEventTypeDirective("event_update")]
        mock_update_check_overdue_schedule.return_value = update_plan_event_type_directives
        new_due_amount_calculation_day = 28
        mock_get_due_amount_calculation_day_parameter.return_value = new_due_amount_calculation_day
        plan_update_due_amount_calc_directive = [
            UpdatePlanEventTypeDirective(
                event_type=self.event_type,
                schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
                skip=ScheduleSkip(end=DEFAULT_DATETIME - relativedelta(seconds=1)),
            )
        ]
        acc_update_due_amount_calc_directive = {
            sentinel.account_id: [
                UpdateAccountEventTypeDirective(
                    event_type=self.event_type,
                    schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
                    skip=ScheduleSkip(end=DEFAULT_DATETIME - relativedelta(seconds=1)),
                )
            ]
        }
        mock_update_due_amount_calculation_day_schedule.return_value = (
            plan_update_due_amount_calc_directive,
            acc_update_due_amount_calc_directive,
        )
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        expected_result = SupervisorScheduledEventHookResult(
            update_plan_event_type_directives=update_plan_event_type_directives
            + plan_update_due_amount_calc_directive,
            supervisee_posting_instructions_directives=supervisee_posting_instructions_directives,
            supervisee_account_notification_directives=repayment_due_notification_directives,
            supervisee_update_account_event_type_directives=acc_update_due_amount_calc_directive,
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_get_due_amount_custom_instructions.assert_called_once_with(
            hook_arguments=hook_arguments, loc_vault=sentinel.loc_vault, loan_vaults=[sentinel.loan]
        )
        mock_get_repayment_due_notification.assert_called_once_with(
            loc_vault=sentinel.loc_vault,
            repayment_amount=sentinel.repayment_amount,
            hook_arguments=hook_arguments,
        )
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_update_check_overdue_schedule.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments
        )
        mock_update_check_overdue_schedule.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments
        )
        mock_update_due_amount_calculation_day_schedule.assert_called_once_with(
            loc_vault=sentinel.loc_vault,
            schedule_start_datetime=DEFAULT_DATETIME
            + relativedelta(months=1, day=new_due_amount_calculation_day),
            due_amount_calculation_day=new_due_amount_calculation_day,
        )
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.loc_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

    @patch.object(line_of_credit_supervisor, "_update_due_amount_calculation_counters")
    @patch.object(line_of_credit_supervisor.common_parameters, "get_denomination_parameter")
    def test_due_calc_repayment_holiday(
        self,
        mock_get_denomination_parameter: MagicMock,
        mock_update_due_amount_calculation_counters: MagicMock,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
        mock_get_due_amount_calculation_day_parameter: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_get_repayment_due_notification: MagicMock,
        mock_get_due_amount_custom_instructions: MagicMock,
        mock_is_due_amount_calculation_blocked: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, [
            sentinel.loan1,
            sentinel.loan2,
        ]
        mock_is_due_amount_calculation_blocked.return_value = True
        supervisee_posting_instructions_directives = {
            sentinel.loan1: [SentinelPostingInstructionsDirective("pi_directive_1")],
            sentinel.loan2: [SentinelPostingInstructionsDirective("pi_directive_2")],
        }
        mock_update_due_amount_calculation_counters.return_value = (
            supervisee_posting_instructions_directives
        )
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_get_due_amount_calculation_day_parameter.return_value = DEFAULT_DATETIME.day

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        expected_result = SupervisorScheduledEventHookResult(
            update_plan_event_type_directives={},
            supervisee_posting_instructions_directives=supervisee_posting_instructions_directives,
            supervisee_account_notification_directives={},
        )
        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_get_due_amount_custom_instructions.assert_not_called()
        mock_get_repayment_due_notification.assert_not_called()
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_update_check_overdue_schedule.assert_not_called()
        mock_update_due_amount_calculation_day_schedule.assert_not_called()
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.loc_vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_update_due_amount_calculation_counters.assert_called_once_with(
            loan_vaults=[sentinel.loan1, sentinel.loan2],
            hook_arguments=hook_arguments,
            denomination=sentinel.denomination,
        )


@patch.object(line_of_credit_supervisor, "_get_loc_and_loan_supervisee_vault_objects")
@patch.object(line_of_credit_supervisor, "_handle_delinquency")
@patch.object(line_of_credit_supervisor, "_update_check_delinquency_schedule")
@patch.object(line_of_credit_supervisor.delinquency, "get_grace_period_parameter")
@patch.object(line_of_credit_supervisor.repayment_holiday, "is_delinquency_blocked")
class CheckDelinquencyEventTest(LineOfCreditSupervisorTestBase):
    event_type = line_of_credit_supervisor.delinquency.CHECK_DELINQUENCY_EVENT

    def test_check_delinquency_when_nothing_overdue(
        self,
        mock_is_delinquency_blocked: MagicMock,
        mock_get_grace_period_parameter: MagicMock,
        mock_update_check_delinquency_schedule: MagicMock,
        mock_handle_delinquency: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, []
        mock_handle_delinquency.return_value = {}
        update_plan_event_type_directives = [SentinelUpdatePlanEventTypeDirective("event_update")]
        mock_update_check_delinquency_schedule.return_value = update_plan_event_type_directives
        mock_get_grace_period_parameter.return_value = 7
        mock_is_delinquency_blocked.return_value = False
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )
        expected_result = SupervisorScheduledEventHookResult(
            update_plan_event_type_directives=update_plan_event_type_directives,
            supervisee_account_notification_directives={},
        )
        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_handle_delinquency.assert_called_once_with(
            hook_arguments=hook_arguments, loc_vault=sentinel.loc_vault, loan_vaults=[]
        )
        mock_update_check_delinquency_schedule.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments, grace_period=7, skip=True
        )
        mock_get_grace_period_parameter.assert_called_once_with(vault=sentinel.loc_vault)

    def test_check_delinquency_when_still_overdue(
        self,
        mock_is_delinquency_blocked: MagicMock,
        mock_get_grace_period_parameter: MagicMock,
        mock_update_check_delinquency_schedule: MagicMock,
        mock_handle_delinquency: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, []
        update_plan_event_type_directives = [SentinelUpdatePlanEventTypeDirective("event_update")]
        mock_update_check_delinquency_schedule.return_value = update_plan_event_type_directives
        delinquent_notification_directives = {
            "loc_account_id": [SentinelAccountNotificationDirective("delinquent notification")]
        }
        mock_handle_delinquency.return_value = delinquent_notification_directives
        mock_get_grace_period_parameter.return_value = 7
        mock_is_delinquency_blocked.return_value = False
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )
        expected_result = SupervisorScheduledEventHookResult(
            update_plan_event_type_directives=update_plan_event_type_directives,
            supervisee_account_notification_directives=delinquent_notification_directives,
        )
        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_handle_delinquency.assert_called_once_with(
            hook_arguments=hook_arguments, loc_vault=sentinel.loc_vault, loan_vaults=[]
        )
        mock_update_check_delinquency_schedule.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments, grace_period=7, skip=True
        )
        mock_get_grace_period_parameter.assert_called_once_with(vault=sentinel.loc_vault)

    def test_check_delinquency_when_event_is_blocked(
        self,
        mock_is_delinquency_blocked: MagicMock,
        mock_get_grace_period_parameter: MagicMock,
        mock_update_check_delinquency_schedule: MagicMock,
        mock_handle_delinquency: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = sentinel.loc_vault, []
        update_plan_event_type_directives = [SentinelUpdatePlanEventTypeDirective("event_update")]
        mock_update_check_delinquency_schedule.return_value = update_plan_event_type_directives
        mock_get_grace_period_parameter.return_value = 7
        mock_is_delinquency_blocked.return_value = True
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )
        expected_result = SupervisorScheduledEventHookResult(
            update_plan_event_type_directives=update_plan_event_type_directives,
            supervisee_account_notification_directives={},
        )
        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_handle_delinquency.assert_not_called()
        mock_update_check_delinquency_schedule.assert_called_once_with(
            loc_vault=sentinel.loc_vault, hook_arguments=hook_arguments, grace_period=7, skip=True
        )
        mock_get_grace_period_parameter.assert_called_once_with(vault=sentinel.loc_vault)


@patch.object(line_of_credit_supervisor, "_get_loc_and_loan_supervisee_vault_objects")
@patch.object(line_of_credit_supervisor.repayment_holiday, "is_overdue_amount_calculation_blocked")
@patch.object(line_of_credit_supervisor, "_get_overdue_custom_instructions")
@patch.object(line_of_credit_supervisor, "_get_overdue_amounts_from_instructions")
@patch.object(line_of_credit_supervisor.common_parameters, "get_denomination_parameter")
@patch.object(line_of_credit_supervisor.overdue, "get_overdue_repayment_notification")
@patch.object(line_of_credit_supervisor, "_update_check_overdue_schedule")
@patch.object(line_of_credit_supervisor, "_update_check_delinquency_schedule")
@patch.object(line_of_credit_supervisor.delinquency, "get_grace_period_parameter")
@patch.object(line_of_credit_supervisor, "_get_delinquency_notification")
@patch.object(line_of_credit_supervisor.late_repayment, "get_late_repayment_fee_parameter")
class CheckOverdueEventTest(LineOfCreditSupervisorTestBase):
    event_type = line_of_credit_supervisor.overdue.CHECK_OVERDUE_EVENT

    def test_check_overdue_when_no_custom_instructions_grace_period_is_7(
        self,
        mock_get_late_repayment_fee_parameter: MagicMock,
        mock_get_delinquency_notification: MagicMock,
        mock_get_grace_period_parameter: MagicMock,
        mock_update_check_delinquency_schedule: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_get_overdue_repayment_notification: MagicMock,
        mock_get_denomination_parameter: MagicMock,
        mock_get_overdue_amounts_from_instructions: MagicMock,
        mock_get_overdue_custom_instructions: MagicMock,
        mock_is_overdue_amount_calculation_blocked: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_loc_vault = self.create_mock("loc account")
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = mock_loc_vault, []
        mock_is_overdue_amount_calculation_blocked.return_value = False
        mock_get_overdue_custom_instructions.return_value = {}
        mock_get_overdue_amounts_from_instructions.return_value = Decimal("0"), Decimal("0")
        mock_get_denomination_parameter.return_value = sentinel.denomination

        overdue_event_type_directives = [SentinelUpdatePlanEventTypeDirective("skip_overdue")]
        delinquency_event_type_directives = [
            SentinelUpdatePlanEventTypeDirective("skip_check_delinquency")
        ]
        mock_update_check_overdue_schedule.return_value = overdue_event_type_directives
        mock_get_grace_period_parameter.return_value = 7
        mock_update_check_delinquency_schedule.return_value = delinquency_event_type_directives

        mock_get_overdue_repayment_notification.return_value = {}
        overdue_event_type_directives = [SentinelUpdatePlanEventTypeDirective("skip_overdue")]
        mock_update_check_overdue_schedule.return_value = overdue_event_type_directives
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        expected_result = SupervisorScheduledEventHookResult(
            update_plan_event_type_directives=delinquency_event_type_directives
            + overdue_event_type_directives,
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_get_overdue_custom_instructions.assert_called_once_with(
            hook_arguments=hook_arguments,
            loc_vault=mock_loc_vault,
            loan_vaults=[],
        )
        mock_get_overdue_amounts_from_instructions.assert_called_once_with(
            loc_account_id=mock_loc_vault.account_id,
            instructions_directives={},
            denomination=sentinel.denomination,
        )
        mock_get_denomination_parameter.assert_called_once_with(vault=mock_loc_vault)
        mock_get_overdue_repayment_notification.assert_not_called()
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_update_check_overdue_schedule.assert_called_once_with(
            loc_vault=mock_loc_vault, hook_arguments=hook_arguments, skip=True
        )
        mock_update_check_delinquency_schedule.assert_called_once_with(
            loc_vault=mock_loc_vault, hook_arguments=hook_arguments, grace_period=7, skip=True
        )
        mock_get_grace_period_parameter.assert_called_once_with(vault=mock_loc_vault)
        mock_get_delinquency_notification.assert_not_called()
        mock_get_late_repayment_fee_parameter.assert_not_called()
        mock_is_overdue_amount_calculation_blocked.assert_called_once_with(
            vault=mock_loc_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

    def test_check_overdue_when_custom_instructions_and_grace_period_is_7(
        self,
        mock_get_late_repayment_fee_parameter: MagicMock,
        mock_get_delinquency_notification: MagicMock,
        mock_get_grace_period_parameter: MagicMock,
        mock_update_check_delinquency_schedule: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_get_overdue_repayment_notification: MagicMock,
        mock_get_denomination_parameter: MagicMock,
        mock_get_overdue_amounts_from_instructions: MagicMock,
        mock_get_overdue_custom_instructions: MagicMock,
        mock_is_overdue_amount_calculation_blocked: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_loc_vault = self.create_mock("loc account")
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = mock_loc_vault, [
            sentinel.loan_vault
        ]
        mock_is_overdue_amount_calculation_blocked.return_value = False
        supervisee_posting_instructions_directives = {
            sentinel.dummy1: [SentinelPostingInstructionsDirective("pi_directive_1")],
            sentinel.dummy2: [SentinelPostingInstructionsDirective("pi_directive_2")],
        }
        mock_get_overdue_custom_instructions.return_value = (
            supervisee_posting_instructions_directives
        )
        overdue_repayment_amount = Decimal("10")
        mock_get_overdue_amounts_from_instructions.return_value = (
            overdue_repayment_amount,
            overdue_repayment_amount,
        )
        mock_get_denomination_parameter.return_value = sentinel.denomination
        overdue_notification_directives = {
            "loc account": [SentinelAccountNotificationDirective("overdue notification")]
        }
        mock_get_overdue_repayment_notification.return_value = [
            SentinelAccountNotificationDirective("overdue notification")
        ]
        update_plan_event_type_directives = [SentinelUpdatePlanEventTypeDirective("event_update")]
        delinquency_event_type_directives = [
            SentinelUpdatePlanEventTypeDirective("delinquency_event_update")
        ]
        mock_update_check_overdue_schedule.return_value = update_plan_event_type_directives
        mock_update_check_delinquency_schedule.return_value = delinquency_event_type_directives
        mock_get_grace_period_parameter.return_value = 7
        mock_get_late_repayment_fee_parameter.return_value = sentinel.late_repayment_fee
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        expected_result = SupervisorScheduledEventHookResult(
            update_plan_event_type_directives=delinquency_event_type_directives
            + update_plan_event_type_directives,
            supervisee_posting_instructions_directives=supervisee_posting_instructions_directives,
            supervisee_account_notification_directives=overdue_notification_directives,
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_get_overdue_custom_instructions.assert_called_once_with(
            hook_arguments=hook_arguments,
            loc_vault=mock_loc_vault,
            loan_vaults=[sentinel.loan_vault],
        )
        mock_get_overdue_amounts_from_instructions.assert_called_once_with(
            loc_account_id=mock_loc_vault.account_id,
            instructions_directives=supervisee_posting_instructions_directives,
            denomination=sentinel.denomination,
        )
        mock_get_denomination_parameter.assert_called_once_with(vault=mock_loc_vault)
        mock_get_overdue_repayment_notification.assert_called_once_with(
            account_id=mock_loc_vault.account_id,
            product_name=line_of_credit_supervisor.LOC_ACCOUNT_TYPE,
            effective_datetime=hook_arguments.effective_datetime,
            overdue_principal_amount=overdue_repayment_amount,
            overdue_interest_amount=overdue_repayment_amount,
            late_repayment_fee=sentinel.late_repayment_fee,
        )
        mock_get_loc_and_loan_supervisee_vault_objects.assert_called_once_with(vault=sentinel.vault)
        mock_update_check_overdue_schedule.assert_called_once_with(
            loc_vault=mock_loc_vault, hook_arguments=hook_arguments, skip=True
        )
        mock_update_check_delinquency_schedule.assert_called_once_with(
            loc_vault=mock_loc_vault, hook_arguments=hook_arguments, grace_period=7, skip=False
        )
        mock_get_grace_period_parameter.assert_called_once_with(vault=mock_loc_vault)
        mock_get_delinquency_notification.assert_not_called()
        mock_get_late_repayment_fee_parameter.assert_called_once_with(vault=mock_loc_vault)
        mock_is_overdue_amount_calculation_blocked.assert_called_once_with(
            vault=mock_loc_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

    def test_check_overdue_when_custom_instructions_and_zero_grace_period(
        self,
        mock_get_late_repayment_fee_parameter: MagicMock,
        mock_get_delinquency_notification: MagicMock,
        mock_get_grace_period_parameter: MagicMock,
        mock_update_check_delinquency_schedule: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_get_overdue_repayment_notification: MagicMock,
        mock_get_denomination_parameter: MagicMock,
        mock_get_overdue_amounts_from_instructions: MagicMock,
        mock_get_overdue_custom_instructions: MagicMock,
        mock_is_overdue_amount_calculation_blocked: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_loc_vault = self.create_mock(account_id="loc_account_id")
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = mock_loc_vault, [
            sentinel.loan_vault
        ]
        mock_is_overdue_amount_calculation_blocked.return_value = False
        supervisee_posting_instructions_directives = {
            sentinel.dummy1: [SentinelPostingInstructionsDirective("pi_directive_1")],
            sentinel.dummy2: [SentinelPostingInstructionsDirective("pi_directive_2")],
        }
        overdue_repayment_amount = Decimal("10")
        mock_get_overdue_amounts_from_instructions.return_value = (
            overdue_repayment_amount,
            overdue_repayment_amount,
        )
        mock_get_overdue_custom_instructions.return_value = (
            supervisee_posting_instructions_directives
        )
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_get_overdue_repayment_notification.return_value = [
            SentinelAccountNotificationDirective("overdue notification")
        ]
        update_plan_event_type_directives = [SentinelUpdatePlanEventTypeDirective("event_update")]
        delinquency_event_type_directives = [
            SentinelUpdatePlanEventTypeDirective("delinquency_event_update")
        ]
        mock_update_check_overdue_schedule.return_value = update_plan_event_type_directives
        mock_update_check_delinquency_schedule.return_value = delinquency_event_type_directives
        mock_get_grace_period_parameter.return_value = 0
        mock_get_delinquency_notification.return_value = [
            SentinelAccountNotificationDirective("delinquent notification")
        ]
        mock_get_late_repayment_fee_parameter.return_value = sentinel.late_repayment_fee
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        expected_result = SupervisorScheduledEventHookResult(
            update_plan_event_type_directives=delinquency_event_type_directives
            + update_plan_event_type_directives,
            supervisee_posting_instructions_directives=supervisee_posting_instructions_directives,
            supervisee_account_notification_directives={
                "loc_account_id": [
                    SentinelAccountNotificationDirective("overdue notification"),
                    SentinelAccountNotificationDirective("delinquent notification"),
                ]
            },
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_get_overdue_custom_instructions.assert_called_once_with(
            hook_arguments=hook_arguments,
            loc_vault=mock_loc_vault,
            loan_vaults=[sentinel.loan_vault],
        )
        mock_get_overdue_amounts_from_instructions.assert_called_once_with(
            loc_account_id=mock_loc_vault.account_id,
            instructions_directives=supervisee_posting_instructions_directives,
            denomination=sentinel.denomination,
        )
        mock_get_overdue_repayment_notification.assert_called_once_with(
            account_id=mock_loc_vault.account_id,
            product_name=line_of_credit_supervisor.LOC_ACCOUNT_TYPE,
            effective_datetime=hook_arguments.effective_datetime,
            overdue_principal_amount=overdue_repayment_amount,
            overdue_interest_amount=overdue_repayment_amount,
            late_repayment_fee=sentinel.late_repayment_fee,
        )
        mock_update_check_overdue_schedule.assert_called_once_with(
            loc_vault=mock_loc_vault, hook_arguments=hook_arguments, skip=True
        )
        mock_update_check_delinquency_schedule.assert_called_once_with(
            loc_vault=mock_loc_vault, hook_arguments=hook_arguments, grace_period=0, skip=True
        )
        mock_get_grace_period_parameter.assert_called_once_with(vault=mock_loc_vault)
        mock_get_delinquency_notification.assert_called_once_with(account_id="loc_account_id")
        mock_get_late_repayment_fee_parameter.assert_called_once_with(vault=mock_loc_vault)
        mock_is_overdue_amount_calculation_blocked.assert_called_once_with(
            vault=mock_loc_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

    def test_check_overdue_repayment_holiday(
        self,
        mock_get_late_repayment_fee_parameter: MagicMock,
        mock_get_delinquency_notification: MagicMock,
        mock_get_grace_period_parameter: MagicMock,
        mock_update_check_delinquency_schedule: MagicMock,
        mock_update_check_overdue_schedule: MagicMock,
        mock_get_overdue_repayment_notification: MagicMock,
        mock_get_denomination_parameter: MagicMock,
        mock_get_overdue_amounts_from_instructions: MagicMock,
        mock_get_overdue_custom_instructions: MagicMock,
        mock_is_overdue_amount_calculation_blocked: MagicMock,
        mock_get_loc_and_loan_supervisee_vault_objects: MagicMock,
    ):
        mock_loc_vault = self.create_mock(account_id="loc_account_id")
        mock_get_loc_and_loan_supervisee_vault_objects.return_value = mock_loc_vault, [
            sentinel.loan_vault
        ]
        mock_is_overdue_amount_calculation_blocked.return_value = True
        update_plan_event_type_directives = [SentinelUpdatePlanEventTypeDirective("event_update")]
        mock_update_check_overdue_schedule.return_value = update_plan_event_type_directives

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        expected_result = SupervisorScheduledEventHookResult(
            update_plan_event_type_directives=update_plan_event_type_directives,
        )

        result = line_of_credit_supervisor.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_get_overdue_custom_instructions.assert_not_called()
        mock_get_overdue_amounts_from_instructions.assert_not_called()
        mock_get_overdue_repayment_notification.assert_not_called()
        mock_update_check_overdue_schedule.assert_called_once_with(
            loc_vault=mock_loc_vault, hook_arguments=hook_arguments, skip=True
        )
        mock_update_check_delinquency_schedule.assert_not_called()
        mock_get_grace_period_parameter.assert_not_called()
        mock_get_delinquency_notification.assert_not_called()
        mock_get_late_repayment_fee_parameter.assert_not_called()
        mock_is_overdue_amount_calculation_blocked.assert_called_once_with(
            vault=mock_loc_vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_get_denomination_parameter.assert_not_called()


@patch.object(line_of_credit_supervisor.common_parameters, "get_denomination_parameter")
@patch.object(
    line_of_credit_supervisor.supervisor_utils, "get_balances_default_dicts_from_timeseries"
)
@patch.object(line_of_credit_supervisor.due_amount_calculation, "supervisor_schedule_logic")
@patch.object(line_of_credit_supervisor.declining_principal, "supervisor_term_details")
@patch.object(
    line_of_credit_supervisor.due_amount_calculation,
    "get_supervisee_last_execution_effective_datetime",
)
@patch.object(line_of_credit_supervisor.overpayment, "track_emi_principal_excess")
@patch.object(line_of_credit_supervisor.overpayment, "reset_due_amount_calc_overpayment_trackers")
@patch.object(line_of_credit_supervisor, "_get_total_repayment_amount_for_loan")
@patch.object(line_of_credit_supervisor.supervisor_utils, "create_aggregate_posting_instructions")
@patch.object(line_of_credit_supervisor, "_get_application_precision_parameter")
class GetDueAmountCustomInstructionsTest(LineOfCreditSupervisorTestBase):
    event_type = line_of_credit_supervisor.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT

    def test_get_due_amount_cis(
        self,
        mock_get_application_precision_parameter: MagicMock,
        mock_create_aggregate_posting_instructions: MagicMock,
        mock_get_total_repayment_amount_for_loan: MagicMock,
        mock_reset_due_amount_calc_overpayment_trackers: MagicMock,
        mock_track_emi_principal_excess: MagicMock,
        mock_get_supervisee_last_execution_effective_datetime: MagicMock,
        mock_term_details: MagicMock,
        mock_supervisor_schedule_logic: MagicMock,
        mock_get_balances_default_dicts_from_timeseries: MagicMock,
        mock_get_denomination_parameter: MagicMock,
    ):
        creation_date = DEFAULT_DATETIME - relativedelta(months=1)
        loc_vault = self.create_supervisee_mock(
            account_id="loc account",
            creation_date=creation_date,
            requires_fetched_balances=sentinel.fetched_balances,
        )
        loan_vault_1 = self.create_supervisee_mock(
            account_id="loan account 1",
            creation_date=creation_date,
            requires_fetched_balances=sentinel.fetched_balances,
        )
        loan_vault_2 = self.create_supervisee_mock(
            account_id="loan account 2",
            creation_date=creation_date,
            requires_fetched_balances=sentinel.fetched_balances,
        )
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_supervisor_schedule_logic.side_effect = [
            [SentinelCustomInstruction("loan_1_ci_1"), SentinelCustomInstruction("loan_1_ci_2")],
            [SentinelCustomInstruction("loan_2_ci_1"), SentinelCustomInstruction("loan_2_ci_2")],
        ]
        mock_term_details.return_value = (sentinel.elapsed_term, sentinel.remaining_term)
        mock_get_supervisee_last_execution_effective_datetime.return_value = (
            sentinel.previous_application_datetime
        )
        mock_track_emi_principal_excess.side_effect = [
            [SentinelCustomInstruction("loan_1_track_emi_principal_excess")],
            [SentinelCustomInstruction("loan_2_track_emi_principal_excess")],
        ]
        mock_reset_due_amount_calc_overpayment_trackers.side_effect = [
            [SentinelCustomInstruction("loan_1_reset_overpayment_trackers")],
            [SentinelCustomInstruction("loan_2_reset_overpayment_trackers")],
        ]
        mock_get_total_repayment_amount_for_loan.return_value = Decimal("1")
        mock_get_balances_default_dicts_from_timeseries.return_value = {
            loan_vault_1.account_id: sentinel.loan_1_vault_balances,
            loan_vault_2.account_id: sentinel.loan_2_vault_balances,
            loc_vault.account_id: sentinel.loc_vault_balances,
        }
        aggregated_instructions = [
            SentinelCustomInstruction("aggregated_ci_1"),
            SentinelCustomInstruction("aggregated_ci_1"),
        ]
        mock_create_aggregate_posting_instructions.return_value = aggregated_instructions
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )
        mock_get_application_precision_parameter.return_value = 2

        # should have supervisee instructions plus the aggregated instructions
        expected_pi_directives = {
            "loc account": [
                PostingInstructionsDirective(
                    posting_instructions=aggregated_instructions,
                    value_datetime=DEFAULT_DATETIME,
                    client_batch_id=f"{self.event_type}_" f"{loc_vault.get_hook_execution_id()}",
                    batch_details={"event": f"{self.event_type}"},
                )
            ],
            "loan account 1": [
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("loan_1_ci_1"),
                        SentinelCustomInstruction("loan_1_ci_2"),
                        SentinelCustomInstruction("loan_1_track_emi_principal_excess"),
                        SentinelCustomInstruction("loan_1_reset_overpayment_trackers"),
                    ],
                    value_datetime=hook_arguments.effective_datetime,
                    client_batch_id=f"{self.event_type}_" f"{loan_vault_1.get_hook_execution_id()}",
                    batch_details={"event": f"{self.event_type}"},
                )
            ],
            "loan account 2": [
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("loan_2_ci_1"),
                        SentinelCustomInstruction("loan_2_ci_2"),
                        SentinelCustomInstruction("loan_2_track_emi_principal_excess"),
                        SentinelCustomInstruction("loan_2_reset_overpayment_trackers"),
                    ],
                    value_datetime=hook_arguments.effective_datetime,
                    client_batch_id=f"{self.event_type}_" f"{loan_vault_2.get_hook_execution_id()}",
                    batch_details={"event": f"{self.event_type}"},
                )
            ],
        }
        expected_repayment_amount = Decimal("2")
        (
            result_pi_directives,
            result_repayment_amount,
        ) = line_of_credit_supervisor._get_due_amount_custom_instructions(
            hook_arguments=hook_arguments,
            loc_vault=loc_vault,
            loan_vaults=[loan_vault_1, loan_vault_2],
        )
        self.assertDictEqual(result_pi_directives, expected_pi_directives)
        self.assertEqual(result_repayment_amount, expected_repayment_amount)
        mock_get_denomination_parameter.assert_called_once_with(vault=loc_vault)
        mock_get_balances_default_dicts_from_timeseries.assert_called_with(
            supervisees=[loc_vault, loan_vault_1, loan_vault_2], effective_datetime=DEFAULT_DATETIME
        )
        mock_term_details.assert_has_calls(
            [
                call(
                    main_vault=loc_vault,
                    loan_vault=loan_vault_1,
                    effective_datetime=hook_arguments.effective_datetime,
                    interest_rate=line_of_credit_supervisor.FIXED_RATE_FEATURE,
                    balances=sentinel.loan_1_vault_balances,
                ),
                call(
                    main_vault=loc_vault,
                    loan_vault=loan_vault_2,
                    effective_datetime=hook_arguments.effective_datetime,
                    interest_rate=line_of_credit_supervisor.FIXED_RATE_FEATURE,
                    balances=sentinel.loan_2_vault_balances,
                ),
            ]
        )
        mock_get_supervisee_last_execution_effective_datetime.assert_has_calls(
            [
                call(
                    main_vault=loc_vault,
                    loan_vault=loan_vault_1,
                    event_type=line_of_credit_supervisor.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,  # noqa: E501
                    effective_datetime=hook_arguments.effective_datetime,
                    elapsed_term=sentinel.elapsed_term,
                ),
                call(
                    main_vault=loc_vault,
                    loan_vault=loan_vault_2,
                    event_type=line_of_credit_supervisor.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,  # noqa: E501
                    effective_datetime=hook_arguments.effective_datetime,
                    elapsed_term=sentinel.elapsed_term,
                ),
            ]
        )
        mock_track_emi_principal_excess.assert_has_calls(
            [
                call(
                    vault=loan_vault_1,
                    interest_application_feature=line_of_credit_supervisor.interest_application_supervisor.interest_application_interface,  # noqa: E501
                    effective_datetime=hook_arguments.effective_datetime,
                    previous_application_datetime=sentinel.previous_application_datetime,
                    balances=sentinel.loan_1_vault_balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    vault=loan_vault_2,
                    interest_application_feature=line_of_credit_supervisor.interest_application_supervisor.interest_application_interface,  # noqa: E501
                    effective_datetime=hook_arguments.effective_datetime,
                    previous_application_datetime=sentinel.previous_application_datetime,
                    balances=sentinel.loan_2_vault_balances,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_supervisor_schedule_logic.assert_has_calls(
            [
                call(
                    loan_vault=loan_vault_1,
                    main_vault=loc_vault,
                    hook_arguments=hook_arguments,
                    account_type=line_of_credit_supervisor.LOC_ACCOUNT_TYPE,
                    interest_application_feature=line_of_credit_supervisor.interest_application_supervisor.interest_application_interface,  # noqa: E501
                    reamortisation_condition_features=[
                        line_of_credit_supervisor.repayment_holiday.SupervisorReamortisationConditionWithoutPreference,  # noqa: E501
                        line_of_credit_supervisor.overpayment.SupervisorOverpaymentReamortisationCondition,  # noqa: E501
                    ],
                    amortisation_feature=line_of_credit_supervisor.declining_principal.SupervisorAmortisationFeature,  # noqa: E501
                    interest_rate_feature=line_of_credit_supervisor.FIXED_RATE_FEATURE,
                    principal_adjustment_features=[
                        line_of_credit_supervisor.overpayment.SupervisorOverpaymentPrincipalAdjustment  # noqa: E501
                    ],
                    balances=sentinel.loan_1_vault_balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    loan_vault=loan_vault_2,
                    main_vault=loc_vault,
                    hook_arguments=hook_arguments,
                    account_type=line_of_credit_supervisor.LOC_ACCOUNT_TYPE,
                    interest_application_feature=line_of_credit_supervisor.interest_application_supervisor.interest_application_interface,  # noqa: E501
                    reamortisation_condition_features=[
                        line_of_credit_supervisor.repayment_holiday.SupervisorReamortisationConditionWithoutPreference,  # noqa: E501
                        line_of_credit_supervisor.overpayment.SupervisorOverpaymentReamortisationCondition,  # noqa: E501
                    ],
                    amortisation_feature=line_of_credit_supervisor.declining_principal.SupervisorAmortisationFeature,  # noqa: E501
                    interest_rate_feature=line_of_credit_supervisor.FIXED_RATE_FEATURE,
                    principal_adjustment_features=[
                        line_of_credit_supervisor.overpayment.SupervisorOverpaymentPrincipalAdjustment  # noqa: E501
                    ],
                    balances=sentinel.loan_2_vault_balances,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_get_total_repayment_amount_for_loan.assert_has_calls(
            [
                call(
                    loan_account_id=loan_vault_1.account_id,
                    custom_instructions=[
                        SentinelCustomInstruction("loan_1_ci_1"),
                        SentinelCustomInstruction("loan_1_ci_2"),
                        SentinelCustomInstruction("loan_1_track_emi_principal_excess"),
                        SentinelCustomInstruction("loan_1_reset_overpayment_trackers"),
                    ],
                    denomination=sentinel.denomination,
                ),
                call(
                    loan_account_id=loan_vault_2.account_id,
                    custom_instructions=[
                        SentinelCustomInstruction("loan_2_ci_1"),
                        SentinelCustomInstruction("loan_2_ci_2"),
                        SentinelCustomInstruction("loan_2_track_emi_principal_excess"),
                        SentinelCustomInstruction("loan_2_reset_overpayment_trackers"),
                    ],
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_create_aggregate_posting_instructions.assert_called_once_with(
            aggregate_account_id=loc_vault.account_id,
            posting_instructions_by_supervisee={
                "loan account 1": [
                    SentinelCustomInstruction("loan_1_ci_1"),
                    SentinelCustomInstruction("loan_1_ci_2"),
                    SentinelCustomInstruction("loan_1_track_emi_principal_excess"),
                    SentinelCustomInstruction("loan_1_reset_overpayment_trackers"),
                ],
                "loan account 2": [
                    SentinelCustomInstruction("loan_2_ci_1"),
                    SentinelCustomInstruction("loan_2_ci_2"),
                    SentinelCustomInstruction("loan_2_track_emi_principal_excess"),
                    SentinelCustomInstruction("loan_2_reset_overpayment_trackers"),
                ],
            },
            prefix="TOTAL",
            balances=sentinel.loc_vault_balances,
            addresses_to_aggregate=[
                line_of_credit_supervisor.lending_addresses.PRINCIPAL,
                line_of_credit_supervisor.lending_addresses.PRINCIPAL_DUE,
                line_of_credit_supervisor.lending_addresses.INTEREST_DUE,
                line_of_credit_supervisor.lending_addresses.EMI,
                line_of_credit_supervisor.lending_addresses.ACCRUED_INTEREST_RECEIVABLE,
                line_of_credit_supervisor.lending_addresses.NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
            ],
            rounding_precision=2,
        )
        mock_get_application_precision_parameter.assert_called_once_with(
            loan_vaults=[loan_vault_1, loan_vault_2]
        )

    def test_get_due_amount_cis_new_loan_ignored(
        self,
        mock_get_application_precision_parameter: MagicMock,
        mock_create_aggregate_posting_instructions: MagicMock,
        mock_get_total_repayment_amount_for_loan: MagicMock,
        mock_track_emi_principal_excess: MagicMock,
        mock_get_supervisee_last_execution_effective_datetime: MagicMock,
        mock_term_details: MagicMock,
        mock_reset_due_amount_calc_overpayment_trackers: MagicMock,
        mock_supervisor_schedule_logic: MagicMock,
        mock_get_balances_default_dicts_from_timeseries: MagicMock,
        mock_get_denomination_parameter: MagicMock,
    ):
        creation_date = DEFAULT_DATETIME - relativedelta(months=1)
        loc_vault = self.create_supervisee_mock(
            account_id="loc account",
            creation_date=creation_date,
            requires_fetched_balances=sentinel.fetched_balances,
        )
        # create a loan with the same creation date as the hook args effective date
        loan_vault = self.create_supervisee_mock(
            account_id="loan account 3",
            creation_date=DEFAULT_DATETIME,
            requires_fetched_balances=sentinel.fetched_balances,
        )
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_get_balances_default_dicts_from_timeseries.return_value = {
            loc_vault.account_id: sentinel.loc_vault_balances,
        }
        mock_create_aggregate_posting_instructions.return_value = []
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )
        mock_get_application_precision_parameter.return_value = 2

        expected_pi_directives = {}
        expected_repayment_amount = Decimal("0")
        (
            result_pi_directives,
            result_repayment_amount,
        ) = line_of_credit_supervisor._get_due_amount_custom_instructions(
            hook_arguments=hook_arguments,
            loc_vault=loc_vault,
            loan_vaults=[loan_vault],
        )
        self.assertDictEqual(result_pi_directives, expected_pi_directives)
        self.assertEqual(result_repayment_amount, expected_repayment_amount)
        mock_get_denomination_parameter.assert_called_once_with(vault=loc_vault)
        mock_get_balances_default_dicts_from_timeseries.assert_called_with(
            supervisees=[loc_vault, loan_vault],
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_supervisor_schedule_logic.assert_not_called()
        mock_term_details.assert_not_called()
        mock_get_supervisee_last_execution_effective_datetime.assert_not_called()
        mock_track_emi_principal_excess.assert_not_called()
        mock_reset_due_amount_calc_overpayment_trackers.assert_not_called()
        mock_get_total_repayment_amount_for_loan.assert_not_called()
        mock_create_aggregate_posting_instructions.assert_called_once_with(
            aggregate_account_id=loc_vault.account_id,
            posting_instructions_by_supervisee={},
            prefix="TOTAL",
            balances=sentinel.loc_vault_balances,
            addresses_to_aggregate=[
                line_of_credit_supervisor.lending_addresses.PRINCIPAL,
                line_of_credit_supervisor.lending_addresses.PRINCIPAL_DUE,
                line_of_credit_supervisor.lending_addresses.INTEREST_DUE,
                line_of_credit_supervisor.lending_addresses.EMI,
                line_of_credit_supervisor.lending_addresses.ACCRUED_INTEREST_RECEIVABLE,
                line_of_credit_supervisor.lending_addresses.NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
            ],
            rounding_precision=2,
        )
        mock_get_application_precision_parameter.assert_called_once_with(loan_vaults=[loan_vault])


@patch.object(line_of_credit_supervisor.utils, "sum_balances")
class GetTotalRepaymentAmountTest(LineOfCreditSupervisorTestBase):
    def test_get_total_repayment_amount_for_loan(
        self,
        mock_sum_balances: MagicMock,
    ):
        mock_sum_balances.return_value = Decimal("10")
        result = line_of_credit_supervisor._get_total_repayment_amount_for_loan(
            loan_account_id=sentinel.account_id,
            custom_instructions=[
                SentinelCustomInstruction("loan_1_ci"),
                SentinelCustomInstruction("loan_2_ci"),
            ],
            denomination=sentinel.denomination,
        )
        self.assertEqual(result, Decimal("20"))
        expected_balances = SentinelCustomInstruction("dummy").balances(
            account_id=sentinel.account_id, tside=Tside.ASSET
        )
        mock_sum_balances.assert_has_calls(
            [
                call(
                    balances=expected_balances,
                    addresses=[
                        line_of_credit_supervisor.lending_addresses.PRINCIPAL_DUE,
                        line_of_credit_supervisor.lending_addresses.INTEREST_DUE,
                    ],
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=expected_balances,
                    addresses=[
                        line_of_credit_supervisor.lending_addresses.PRINCIPAL_DUE,
                        line_of_credit_supervisor.lending_addresses.INTEREST_DUE,
                    ],
                    denomination=sentinel.denomination,
                ),
            ]
        )


@patch.object(line_of_credit_supervisor.common_parameters, "get_denomination_parameter")
@patch.object(
    line_of_credit_supervisor.supervisor_utils, "get_balances_default_dicts_from_timeseries"
)
@patch.object(line_of_credit_supervisor.supervisor_utils, "create_aggregate_posting_instructions")
@patch.object(line_of_credit_supervisor, "_get_application_precision_parameter")
@patch.object(line_of_credit_supervisor.overdue, "schedule_logic")
@patch.object(line_of_credit_supervisor.late_repayment, "schedule_logic")
class GetOverdueCustomInstructionsTest(LineOfCreditSupervisorTestBase):
    event_type = line_of_credit_supervisor.overdue.CHECK_OVERDUE_EVENT

    def test_overdue_cis_returns_instructions(
        self,
        mock_late_repayment_schedule_logic: MagicMock,
        mock_overdue_schedule_logic: MagicMock,
        mock_get_application_precision_parameter: MagicMock,
        mock_create_aggregate_posting_instructions: MagicMock,
        mock_get_balances_default_dicts_from_timeseries: MagicMock,
        mock_get_denomination_parameter: MagicMock,
    ):
        creation_date = DEFAULT_DATETIME - relativedelta(months=1)
        loc_vault = self.create_supervisee_mock(
            account_id="loc account",
            creation_date=creation_date,
            requires_fetched_balances=sentinel.fetched_balances,
        )
        loan_vault_1 = self.create_supervisee_mock(
            account_id="loan account 1",
            creation_date=creation_date,
            requires_fetched_balances=sentinel.fetched_balances,
        )
        loan_vault_2 = self.create_supervisee_mock(
            account_id="loan account 2",
            creation_date=creation_date,
            requires_fetched_balances=sentinel.fetched_balances,
        )
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_get_balances_default_dicts_from_timeseries.return_value = {
            loan_vault_1.account_id: sentinel.loan_1_vault_balances,
            loan_vault_2.account_id: sentinel.loan_2_vault_balances,
            loc_vault.account_id: sentinel.loc_vault_balances,
        }
        aggregated_instructions = [
            SentinelCustomInstruction("aggregated_ci_1"),
            SentinelCustomInstruction("aggregated_ci_2"),
        ]
        mock_create_aggregate_posting_instructions.return_value = aggregated_instructions
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )
        mock_get_application_precision_parameter.return_value = 2
        supervisee_instructions = [
            SentinelCustomInstruction("supervisee_instruction_1"),
            SentinelCustomInstruction("supervisee_instruction_2"),
        ]
        mock_overdue_schedule_logic.return_value = supervisee_instructions, sentinel.dummy
        late_repayment_instructions = [
            SentinelCustomInstruction("late_repayment_instruction"),
        ]
        mock_late_repayment_schedule_logic.return_value = late_repayment_instructions

        expected_pi_directives = {
            "loc account": [
                PostingInstructionsDirective(
                    posting_instructions=aggregated_instructions + late_repayment_instructions,
                    value_datetime=DEFAULT_DATETIME,
                    client_batch_id=f"{self.event_type}_{loc_vault.get_hook_execution_id()}",
                    batch_details={"event": f"{self.event_type}"},
                )
            ],
            "loan account 1": [
                PostingInstructionsDirective(
                    posting_instructions=supervisee_instructions,
                    value_datetime=hook_arguments.effective_datetime,
                    client_batch_id=f"{self.event_type}_{loan_vault_1.get_hook_execution_id()}",
                    batch_details={"event": f"{self.event_type}"},
                )
            ],
            "loan account 2": [
                PostingInstructionsDirective(
                    posting_instructions=supervisee_instructions,
                    value_datetime=hook_arguments.effective_datetime,
                    client_batch_id=f"{self.event_type}_{loan_vault_2.get_hook_execution_id()}",
                    batch_details={"event": f"{self.event_type}"},
                )
            ],
        }
        result = line_of_credit_supervisor._get_overdue_custom_instructions(
            hook_arguments,
            loc_vault=loc_vault,
            loan_vaults=[loan_vault_1, loan_vault_2],
        )
        self.assertDictEqual(result, expected_pi_directives)
        mock_get_denomination_parameter.assert_called_once_with(vault=loc_vault)
        mock_get_balances_default_dicts_from_timeseries.assert_has_calls(
            [
                call(
                    supervisees=[loc_vault, loan_vault_1, loan_vault_2],
                    effective_datetime=DEFAULT_DATETIME,
                ),
            ]
        )
        mock_get_balances_default_dicts_from_timeseries.assert_called_once_with(
            supervisees=[loc_vault, loan_vault_1, loan_vault_2],
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_create_aggregate_posting_instructions.assert_called_once_with(
            aggregate_account_id=loc_vault.account_id,
            posting_instructions_by_supervisee={
                "loan account 1": supervisee_instructions,
                "loan account 2": supervisee_instructions,
            },
            prefix="TOTAL",
            balances=sentinel.loc_vault_balances,
            addresses_to_aggregate=[
                line_of_credit_supervisor.lending_addresses.PRINCIPAL_DUE,
                line_of_credit_supervisor.lending_addresses.PRINCIPAL_OVERDUE,
                line_of_credit_supervisor.lending_addresses.INTEREST_DUE,
                line_of_credit_supervisor.lending_addresses.INTEREST_OVERDUE,
            ],
            rounding_precision=2,
        )
        mock_get_application_precision_parameter.assert_called_once_with(
            loan_vaults=[loan_vault_1, loan_vault_2]
        )
        mock_overdue_schedule_logic.assert_has_calls(
            [
                call(
                    vault=loan_vault_1,
                    hook_arguments=hook_arguments,
                    balances=sentinel.loan_1_vault_balances,
                    account_type=line_of_credit_supervisor.LOC_ACCOUNT_TYPE,
                ),
                call(
                    vault=loan_vault_2,
                    hook_arguments=hook_arguments,
                    balances=sentinel.loan_2_vault_balances,
                    account_type=line_of_credit_supervisor.LOC_ACCOUNT_TYPE,
                ),
            ]
        )
        mock_late_repayment_schedule_logic.assert_called_once_with(
            vault=loc_vault,
            hook_arguments=hook_arguments,
            denomination=sentinel.denomination,
            account_type=line_of_credit_supervisor.LOC_ACCOUNT_TYPE,
            check_total_overdue_amount=False,
        )

    def test_overdue_cis_zero_overdue_amount(
        self,
        mock_late_repayment_schedule_logic: MagicMock,
        mock_overdue_schedule_logic: MagicMock,
        mock_get_application_precision_parameter: MagicMock,
        mock_create_aggregate_posting_instructions: MagicMock,
        mock_get_balances_default_dicts_from_timeseries: MagicMock,
        mock_get_denomination_parameter: MagicMock,
    ):
        creation_date = DEFAULT_DATETIME - relativedelta(months=1)
        loc_vault = self.create_supervisee_mock(
            account_id="loc account",
            creation_date=creation_date,
            requires_fetched_balances=sentinel.fetched_balances,
        )
        loan_vault_1 = self.create_supervisee_mock(
            account_id="loan account 1",
            creation_date=creation_date,
            requires_fetched_balances=sentinel.fetched_balances,
        )
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_get_balances_default_dicts_from_timeseries.return_value = {
            loan_vault_1.account_id: sentinel.loan_1_vault_balances,
            loc_vault.account_id: sentinel.loc_vault_balances,
        }
        aggregated_instructions = [
            SentinelCustomInstruction("aggregated_ci_1"),
            SentinelCustomInstruction("aggregated_ci_2"),
        ]
        mock_create_aggregate_posting_instructions.return_value = aggregated_instructions
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )
        mock_get_application_precision_parameter.return_value = 2
        mock_overdue_schedule_logic.return_value = [], sentinel.dummy
        result = line_of_credit_supervisor._get_overdue_custom_instructions(
            hook_arguments,
            loc_vault=loc_vault,
            loan_vaults=[loan_vault_1],
        )
        self.assertDictEqual(result, {})
        mock_get_denomination_parameter.assert_called_once_with(vault=loc_vault)
        mock_get_balances_default_dicts_from_timeseries.assert_called_once_with(
            supervisees=[loc_vault, loan_vault_1],
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_create_aggregate_posting_instructions.assert_not_called()
        mock_get_application_precision_parameter.assert_called_once_with(loan_vaults=[loan_vault_1])
        mock_overdue_schedule_logic.assert_has_calls(
            [
                call(
                    vault=loan_vault_1,
                    hook_arguments=hook_arguments,
                    balances=sentinel.loan_1_vault_balances,
                    account_type=line_of_credit_supervisor.LOC_ACCOUNT_TYPE,
                ),
            ]
        )
        mock_late_repayment_schedule_logic.assert_not_called()


@patch.object(line_of_credit_supervisor.utils, "balance_at_coordinates")
class GetTotalOverdueAmountTest(LineOfCreditSupervisorTestBase):
    def test_get_overdue_amounts_from_instructions(
        self,
        mock_balance_at_coordinates: MagicMock,
    ):
        mock_balance_at_coordinates.return_value = Decimal("10")
        supervisee_posting_instructions_directives = {
            sentinel.loc_account_id: [SentinelPostingInstructionsDirective("pi_directive_1")],
            sentinel.dummy2: [SentinelPostingInstructionsDirective("pi_directive_2")],
        }
        aggregated_instructions = [
            SentinelCustomInstruction("aggregated_ci_1"),
            SentinelCustomInstruction("aggregated_ci_2"),
        ]
        supervisee_posting_instructions_directives = {
            sentinel.loc_account_id: [
                PostingInstructionsDirective(
                    posting_instructions=aggregated_instructions,
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            sentinel.dummy_account_id: [
                PostingInstructionsDirective(
                    posting_instructions=aggregated_instructions,
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        }
        (
            result_overdue_principal_amount,
            result_overdue_interest_amount,
        ) = line_of_credit_supervisor._get_overdue_amounts_from_instructions(
            loc_account_id=sentinel.loc_account_id,
            instructions_directives=supervisee_posting_instructions_directives,
            denomination=sentinel.denomination,
        )
        self.assertEqual(result_overdue_principal_amount, Decimal("20"))
        self.assertEqual(result_overdue_interest_amount, Decimal("20"))
        expected_balances = SentinelCustomInstruction("dummy").balances(
            account_id=sentinel.loc_account_id, tside=Tside.ASSET
        )
        expected_mock_calls = [
            call(
                balances=expected_balances,
                address=f"TOTAL_{line_of_credit_supervisor.lending_addresses.PRINCIPAL_OVERDUE}",
                denomination=sentinel.denomination,
            ),
            call(
                balances=expected_balances,
                address=f"TOTAL_{line_of_credit_supervisor.lending_addresses.PRINCIPAL_OVERDUE}",
                denomination=sentinel.denomination,
            ),
            call(
                balances=expected_balances,
                address=f"TOTAL_{line_of_credit_supervisor.lending_addresses.INTEREST_OVERDUE}",
                denomination=sentinel.denomination,
            ),
            call(
                balances=expected_balances,
                address=f"TOTAL_{line_of_credit_supervisor.lending_addresses.INTEREST_OVERDUE}",
                denomination=sentinel.denomination,
            ),
        ]
        mock_balance_at_coordinates.assert_has_calls(expected_mock_calls)

    def test_get_overdue_amounts_from_instructions_when_no_loc_instructions(
        self,
        mock_balance_at_coordinates: MagicMock,
    ):
        mock_balance_at_coordinates.return_value = Decimal("10")
        supervisee_posting_instructions_directives = {
            sentinel.loc_account_id: [SentinelPostingInstructionsDirective("pi_directive_1")],
            sentinel.dummy2: [SentinelPostingInstructionsDirective("pi_directive_2")],
        }
        aggregated_instructions = [
            SentinelCustomInstruction("aggregated_ci_1"),
            SentinelCustomInstruction("aggregated_ci_2"),
        ]
        supervisee_posting_instructions_directives = {
            sentinel.dummy_account_id: [
                PostingInstructionsDirective(
                    posting_instructions=aggregated_instructions,
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        }
        (
            result_overdue_principal_amount,
            result_overdue_interest_amount,
        ) = line_of_credit_supervisor._get_overdue_amounts_from_instructions(
            loc_account_id=sentinel.loc_account_id,
            instructions_directives=supervisee_posting_instructions_directives,
            denomination=sentinel.denomination,
        )
        self.assertEqual(result_overdue_principal_amount, Decimal("0"))
        self.assertEqual(result_overdue_interest_amount, Decimal("0"))
        mock_balance_at_coordinates.assert_not_called()


@patch.object(line_of_credit_supervisor.utils, "get_parameter")
class GetRepaymentDueNotificationTest(LineOfCreditSupervisorTestBase):
    def test_get_repayment_due_notification(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {line_of_credit_supervisor.overdue.PARAM_REPAYMENT_PERIOD: 7}
        )
        mock_loc_vault = self.create_mock("loc account")
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )
        overdue_date = hook_arguments.effective_datetime + relativedelta(days=7)
        expected = {
            "loc account": [
                AccountNotificationDirective(
                    notification_type=line_of_credit_supervisor.REPAYMENT_DUE_NOTIFICATION,
                    notification_details={
                        "account_id": "loc account",
                        "repayment_amount": str(sentinel.repayment_amount),
                        "overdue_date": str(overdue_date.date()),
                    },
                )
            ],
        }
        result = line_of_credit_supervisor._get_repayment_due_notification(
            loc_vault=mock_loc_vault,
            repayment_amount=sentinel.repayment_amount,
            hook_arguments=hook_arguments,
        )
        self.assertDictEqual(result, expected)
        mock_get_parameter.assert_called_once_with(
            vault=mock_loc_vault,
            name=line_of_credit_supervisor.overdue.PARAM_REPAYMENT_PERIOD,
            at_datetime=None,
        )


@patch.object(line_of_credit_supervisor.common_parameters, "get_denomination_parameter")
@patch.object(
    line_of_credit_supervisor.due_amount_calculation,
    "get_actual_next_repayment_date",
)
@patch.object(line_of_credit_supervisor, "_get_standard_interest_accrual_custom_instructions")
@patch.object(line_of_credit_supervisor, "_get_penalty_interest_accrual_custom_instructions")
@patch.object(line_of_credit_supervisor.utils, "get_balance_default_dict_from_mapping")
@patch.object(line_of_credit_supervisor.supervisor_utils, "create_aggregate_posting_instructions")
@patch.object(line_of_credit_supervisor, "_get_application_precision_parameter")
@patch.object(
    line_of_credit_supervisor.due_amount_calculation,
    "DUE_AMOUNT_CALCULATION_EVENT",
    sentinel.event_type,
)
class HandleAccrueInterestTest(LineOfCreditSupervisorTestBase):
    def test_dictionary_of_pis_is_returned(
        self,
        mock_get_application_precision_parameter: MagicMock,
        mock_create_aggregate_posting_instructions: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_get_penalty_interest_accrual_custom_instructions: MagicMock,
        mock_get_standard_interest_accrual_custom_instructions: MagicMock,
        mock_get_actual_next_repayment_date: MagicMock,
        mock_get_denomination_parameter: MagicMock,
    ):
        mock_vault = self.create_supervisor_mock()
        loc_vault = self.create_supervisee_mock(
            account_id="loc",
            requires_fetched_balances=sentinel.fetched_balances,
            last_execution_datetimes={sentinel.event_type: DEFAULT_DATETIME},
        )
        loan1 = self.create_mock(account_id="1")
        loan2 = self.create_mock(account_id="2")
        mock_get_denomination_parameter.return_value = sentinel.denomination
        month_after_opening = DEFAULT_DATETIME + relativedelta(months=1)
        mock_get_actual_next_repayment_date.return_value = month_after_opening
        mock_get_standard_interest_accrual_custom_instructions.side_effect = [
            [SentinelCustomInstruction("accrual_ci_1")],
            [SentinelCustomInstruction("accrual_ci_2")],
        ]
        mock_get_penalty_interest_accrual_custom_instructions.return_value = []
        mock_get_balance_default_dict_from_mapping.return_value = sentinel.default_dict
        mock_create_aggregate_posting_instructions.return_value = [
            SentinelCustomInstruction("aggregate_accrual_instruction")
        ]
        mock_get_application_precision_parameter.return_value = sentinel.precision

        posting_instructions_by_supervisee = {
            "1": [SentinelCustomInstruction("accrual_ci_1")],
            "2": [SentinelCustomInstruction("accrual_ci_2")],
        }

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )

        expected = {
            "1": [
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("accrual_ci_1")],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            "2": [
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("accrual_ci_2")],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            "loc": [
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("aggregate_accrual_instruction")
                    ],
                    client_batch_id=f"AGGREGATE_LOC_{line_of_credit_supervisor.LOC_ACCOUNT_TYPE}"
                    f"_INTEREST_ACCRUAL_{DEFAULT_HOOK_EXECUTION_ID}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        }

        result = line_of_credit_supervisor._handle_accrue_interest(
            vault=mock_vault,
            hook_arguments=hook_arguments,
            loc_vault=loc_vault,
            loan_vaults=[loan1, loan2],
        )
        self.assertDictEqual(result, expected)
        mock_get_denomination_parameter.assert_called_once_with(vault=loc_vault)
        mock_get_standard_interest_accrual_custom_instructions.assert_has_calls(
            calls=[
                call(
                    vault=loan1,
                    hook_arguments=hook_arguments,
                    next_due_amount_calculation_datetime=month_after_opening,
                    denomination=sentinel.denomination,
                ),
                call(
                    vault=loan2,
                    hook_arguments=hook_arguments,
                    next_due_amount_calculation_datetime=month_after_opening,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_get_penalty_interest_accrual_custom_instructions.assert_has_calls(
            calls=[
                call(
                    loan_vault=loan1,
                    hook_arguments=hook_arguments,
                    denomination=sentinel.denomination,
                ),
                call(
                    loan_vault=loan2,
                    hook_arguments=hook_arguments,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_get_balance_default_dict_from_mapping.assert_called_once_with(
            mapping=sentinel.fetched_balances,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_create_aggregate_posting_instructions.assert_called_once_with(
            aggregate_account_id="loc",
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            prefix="TOTAL",
            balances=sentinel.default_dict,
            addresses_to_aggregate=[
                line_of_credit_supervisor.lending_addresses.ACCRUED_INTEREST_RECEIVABLE,
                line_of_credit_supervisor.lending_addresses.NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                line_of_credit_supervisor.lending_addresses.PENALTIES,
            ],
            rounding_precision=sentinel.precision,
        )
        mock_get_application_precision_parameter.assert_called_once_with(
            loan_vaults=[loan1, loan2],
        )

    def test_no_loc_pids_returned_if_no_aggregate_instructions(
        self,
        mock_get_application_precision_parameter: MagicMock,
        mock_create_aggregate_posting_instructions: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_get_penalty_interest_accrual_custom_instructions: MagicMock,
        mock_get_standard_interest_accrual_custom_instructions: MagicMock,
        mock_get_actual_next_repayment_date: MagicMock,
        mock_get_denomination_parameter: MagicMock,
    ):
        loc_vault = self.create_supervisee_mock(
            account_id="loc",
            requires_fetched_balances=sentinel.fetched_balances,
            last_execution_datetimes={sentinel.event_type: DEFAULT_DATETIME},
        )
        loan1 = self.create_mock(account_id="1")
        loan2 = self.create_mock(account_id="2")
        mock_vault = self.create_supervisor_mock()
        mock_get_denomination_parameter.return_value = sentinel.denomination
        month_after_opening = DEFAULT_DATETIME + relativedelta(months=1)
        mock_get_actual_next_repayment_date.return_value = month_after_opening
        mock_get_standard_interest_accrual_custom_instructions.side_effect = [
            [SentinelCustomInstruction("accrual_ci_1")],
            [SentinelCustomInstruction("accrual_ci_2")],
        ]
        mock_get_penalty_interest_accrual_custom_instructions.side_effect = [
            [SentinelCustomInstruction("penalty_accrual_ci_1")],
            [SentinelCustomInstruction("penalty_accrual_ci_2")],
        ]
        mock_get_balance_default_dict_from_mapping.return_value = sentinel.default_dict
        mock_create_aggregate_posting_instructions.return_value = []
        mock_get_application_precision_parameter.return_value = sentinel.precision

        posting_instructions_by_supervisee = {
            "1": [
                SentinelCustomInstruction("accrual_ci_1"),
                SentinelCustomInstruction("penalty_accrual_ci_1"),
            ],
            "2": [
                SentinelCustomInstruction("accrual_ci_2"),
                SentinelCustomInstruction("penalty_accrual_ci_2"),
            ],
        }

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )

        expected = {
            "1": [
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("accrual_ci_1"),
                        SentinelCustomInstruction("penalty_accrual_ci_1"),
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            "2": [
                PostingInstructionsDirective(
                    posting_instructions=[
                        SentinelCustomInstruction("accrual_ci_2"),
                        SentinelCustomInstruction("penalty_accrual_ci_2"),
                    ],
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
        }
        result = line_of_credit_supervisor._handle_accrue_interest(
            vault=mock_vault,
            hook_arguments=hook_arguments,
            loc_vault=loc_vault,
            loan_vaults=[loan1, loan2],
        )
        self.assertDictEqual(result, expected)
        mock_get_denomination_parameter.assert_called_once_with(vault=loc_vault)
        mock_get_standard_interest_accrual_custom_instructions.assert_has_calls(
            calls=[
                call(
                    vault=loan1,
                    hook_arguments=hook_arguments,
                    next_due_amount_calculation_datetime=month_after_opening,
                    denomination=sentinel.denomination,
                ),
                call(
                    vault=loan2,
                    hook_arguments=hook_arguments,
                    next_due_amount_calculation_datetime=month_after_opening,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_get_penalty_interest_accrual_custom_instructions.assert_has_calls(
            calls=[
                call(
                    loan_vault=loan1,
                    hook_arguments=hook_arguments,
                    denomination=sentinel.denomination,
                ),
                call(
                    loan_vault=loan2,
                    hook_arguments=hook_arguments,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_get_balance_default_dict_from_mapping.assert_called_once_with(
            mapping=sentinel.fetched_balances,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_create_aggregate_posting_instructions.assert_called_once_with(
            aggregate_account_id="loc",
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            prefix="TOTAL",
            balances=sentinel.default_dict,
            addresses_to_aggregate=[
                line_of_credit_supervisor.lending_addresses.ACCRUED_INTEREST_RECEIVABLE,
                line_of_credit_supervisor.lending_addresses.NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                line_of_credit_supervisor.lending_addresses.PENALTIES,
            ],
            rounding_precision=sentinel.precision,
        )
        mock_get_application_precision_parameter.assert_called_once_with(
            loan_vaults=[loan1, loan2],
        )

    def test_empty_dictionary_is_returned_if_no_accrual_instructions(
        self,
        mock_get_application_precision_parameter: MagicMock,
        mock_create_aggregate_posting_instructions: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_get_penalty_interest_accrual_custom_instructions: MagicMock,
        mock_get_standard_interest_accrual_custom_instructions: MagicMock,
        mock_get_actual_next_repayment_date: MagicMock,
        mock_get_denomination_parameter: MagicMock,
    ):
        loc_vault = self.create_supervisee_mock(
            account_id="loc",
            requires_fetched_balances=sentinel.fetched_balances,
            last_execution_datetimes={sentinel.event_type: DEFAULT_DATETIME},
        )
        loan1 = self.create_mock(account_id="1")
        loan2 = self.create_mock(account_id="2")
        mock_vault = self.create_supervisor_mock()
        mock_get_denomination_parameter.return_value = sentinel.denomination
        month_after_opening = DEFAULT_DATETIME + relativedelta(months=1)
        mock_get_actual_next_repayment_date.return_value = month_after_opening
        mock_get_standard_interest_accrual_custom_instructions.side_effect = [[], []]
        mock_get_penalty_interest_accrual_custom_instructions.return_value = []

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )

        result = line_of_credit_supervisor._handle_accrue_interest(
            vault=mock_vault,
            hook_arguments=hook_arguments,
            loc_vault=loc_vault,
            loan_vaults=[loan1, loan2],
        )
        self.assertDictEqual(result, {})
        mock_get_denomination_parameter.assert_called_once_with(vault=loc_vault)
        mock_get_standard_interest_accrual_custom_instructions.assert_has_calls(
            calls=[
                call(
                    vault=loan1,
                    hook_arguments=hook_arguments,
                    next_due_amount_calculation_datetime=month_after_opening,
                    denomination=sentinel.denomination,
                ),
                call(
                    vault=loan2,
                    hook_arguments=hook_arguments,
                    next_due_amount_calculation_datetime=month_after_opening,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_get_penalty_interest_accrual_custom_instructions.assert_has_calls(
            calls=[
                call(
                    loan_vault=loan1,
                    hook_arguments=hook_arguments,
                    denomination=sentinel.denomination,
                ),
                call(
                    loan_vault=loan2,
                    hook_arguments=hook_arguments,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        mock_get_balance_default_dict_from_mapping.assert_not_called()
        mock_create_aggregate_posting_instructions.assert_not_called()
        mock_get_application_precision_parameter.assert_not_called()


class GetStandardInterestAccrualCustomInstructionsTest(LineOfCreditSupervisorTestBase):
    @patch.object(line_of_credit_supervisor.utils, "get_balance_default_dict_from_mapping")
    @patch.object(line_of_credit_supervisor.common_parameters, "get_denomination_parameter")
    @patch.object(line_of_credit_supervisor.interest_accrual_supervisor, "daily_accrual_logic")
    @patch.object(line_of_credit_supervisor.overpayment, "track_interest_on_expected_principal")
    def test_custom_instruction_is_returned(
        self,
        mock_track_interest_on_expected_principal: MagicMock,
        mock_daily_accrual_logic: MagicMock,
        mock_get_denomination_parameter: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
    ):
        loan = self.create_supervisee_mock(requires_fetched_balances=sentinel.fetched_balances)
        mock_get_balance_default_dict_from_mapping.return_value = sentinel.default_dict
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_daily_accrual_logic.return_value = [SentinelCustomInstruction("accrual_ci")]
        mock_track_interest_on_expected_principal.return_value = [
            SentinelCustomInstruction("track_expected_interest_ci")
        ]

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )

        expected = [
            SentinelCustomInstruction("accrual_ci"),
            SentinelCustomInstruction("track_expected_interest_ci"),
        ]

        result = line_of_credit_supervisor._get_standard_interest_accrual_custom_instructions(
            vault=loan,
            hook_arguments=hook_arguments,
            next_due_amount_calculation_datetime=sentinel.datetime,
        )
        self.assertEqual(result, expected)

        mock_get_balance_default_dict_from_mapping.assert_called_once_with(
            mapping=sentinel.fetched_balances,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_get_denomination_parameter.assert_called_once_with(vault=loan)
        mock_daily_accrual_logic.assert_called_once_with(
            vault=loan,
            hook_arguments=hook_arguments,
            next_due_amount_calculation_datetime=sentinel.datetime,
            account_type=line_of_credit_supervisor.DRAWDOWN_LOAN_ACCOUNT_TYPE,
            interest_rate_feature=line_of_credit_supervisor.FIXED_RATE_FEATURE,
            denomination=sentinel.denomination,
            balances=sentinel.default_dict,
        )
        mock_track_interest_on_expected_principal.assert_called_once_with(
            vault=loan,
            hook_arguments=hook_arguments,
            interest_rate_feature=line_of_credit_supervisor.FIXED_RATE_FEATURE,
            balances=sentinel.default_dict,
            denomination=sentinel.denomination,
        )

    @patch.object(line_of_credit_supervisor.utils, "get_balance_default_dict_from_mapping")
    @patch.object(line_of_credit_supervisor.common_parameters, "get_denomination_parameter")
    @patch.object(line_of_credit_supervisor.interest_accrual_supervisor, "daily_accrual_logic")
    @patch.object(line_of_credit_supervisor.overpayment, "track_interest_on_expected_principal")
    def test_denomination_param_is_not_called_when_denomination_is_passed_in(
        self,
        mock_track_interest_on_expected_principal: MagicMock,
        mock_daily_accrual_logic: MagicMock,
        mock_get_denomination_parameter: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
    ):
        loan = self.create_supervisee_mock(requires_fetched_balances=sentinel.fetched_balances)
        mock_get_balance_default_dict_from_mapping.return_value = sentinel.default_dict
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_daily_accrual_logic.return_value = [SentinelCustomInstruction("accrual_ci")]
        mock_track_interest_on_expected_principal.return_value = []

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )

        expected = [SentinelCustomInstruction("accrual_ci")]

        result = line_of_credit_supervisor._get_standard_interest_accrual_custom_instructions(
            vault=loan,
            hook_arguments=hook_arguments,
            next_due_amount_calculation_datetime=sentinel.datetime,
            denomination=sentinel.denomination_argument,
        )
        self.assertEqual(result, expected)

        mock_get_balance_default_dict_from_mapping.assert_called_once_with(
            mapping=sentinel.fetched_balances,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_daily_accrual_logic.assert_called_once_with(
            vault=loan,
            hook_arguments=hook_arguments,
            next_due_amount_calculation_datetime=sentinel.datetime,
            account_type=line_of_credit_supervisor.DRAWDOWN_LOAN_ACCOUNT_TYPE,
            interest_rate_feature=line_of_credit_supervisor.FIXED_RATE_FEATURE,
            denomination=sentinel.denomination_argument,
            balances=sentinel.default_dict,
        )
        mock_track_interest_on_expected_principal.assert_called_once_with(
            vault=loan,
            hook_arguments=hook_arguments,
            interest_rate_feature=line_of_credit_supervisor.FIXED_RATE_FEATURE,
            balances=sentinel.default_dict,
            denomination=sentinel.denomination_argument,
        )
        mock_get_denomination_parameter.assert_not_called()


@patch.object(line_of_credit_supervisor.utils, "get_parameter")
class GetPenaltyInterestAccrualCustomInstructions(LineOfCreditSupervisorTestBase):
    def setUp(self) -> None:
        self.mock_loan_vault = self.create_supervisee_mock(
            requires_fetched_balances=sentinel.fetched_balances
        )

        self.mock_daily_accrual = patch.object(
            line_of_credit_supervisor.interest_accrual_common, "daily_accrual"
        ).start()
        self.mock_daily_accrual.return_value = [sentinel.accrual_ci]

        self.mock_sum_balances = patch.object(
            line_of_credit_supervisor.utils, "sum_balances"
        ).start()
        self.mock_sum_balances.return_value = sentinel.balance_to_accrue_on

        self.mock_get_balance_default_dict_from_mapping = patch.object(
            line_of_credit_supervisor.utils, "get_balance_default_dict_from_mapping"
        ).start()
        self.mock_get_balance_default_dict_from_mapping.return_value = sentinel.balances

        self.addCleanup(patch.stopall)
        return super().setUp()

    @patch.object(line_of_credit_supervisor.common_parameters, "get_denomination_parameter")
    def test_gets_denomination_if_not_provided(
        self,
        mock_get_denomination_parameter: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                line_of_credit_supervisor.drawdown_loan.PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE: True,  # noqa: E501
                line_of_credit_supervisor.drawdown_loan.PARAM_PENALTY_INTEREST_INCOME_ACCOUNT: sentinel.penalty_interest_income_account,  # noqa: E501
                line_of_credit_supervisor.drawdown_loan.PARAM_PENALTY_INTEREST_RATE: Decimal(
                    "0.10"
                ),
                line_of_credit_supervisor.interest_accrual_common.PARAM_DAYS_IN_YEAR: sentinel.days_in_year,  # noqa: E501
                line_of_credit_supervisor.interest_application.PARAM_APPLICATION_PRECISION: "2",
                line_of_credit_supervisor.fixed_rate.PARAM_FIXED_INTEREST_RATE: Decimal(".15"),
            },
        )

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )

        result = line_of_credit_supervisor._get_penalty_interest_accrual_custom_instructions(
            loan_vault=self.mock_loan_vault,
            hook_arguments=hook_arguments,
        )

        self.assertListEqual(result, [sentinel.accrual_ci])

        mock_get_parameter.assert_has_calls(
            [
                call(
                    vault=self.mock_loan_vault,
                    name=line_of_credit_supervisor.drawdown_loan.PARAM_PENALTY_INTEREST_RATE,
                    at_datetime=None,
                ),
                call(
                    vault=self.mock_loan_vault,
                    name=line_of_credit_supervisor.drawdown_loan.PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE,  # noqa: E501
                    is_boolean=True,
                    at_datetime=None,
                ),
                call(
                    self.mock_loan_vault,
                    line_of_credit_supervisor.fixed_rate.PARAM_FIXED_INTEREST_RATE,
                    at_datetime=DEFAULT_DATETIME,
                ),
                call(
                    vault=self.mock_loan_vault,
                    name=line_of_credit_supervisor.drawdown_loan.PARAM_PENALTY_INTEREST_INCOME_ACCOUNT,  # noqa: E501
                    at_datetime=None,
                ),
                call(
                    vault=self.mock_loan_vault,
                    name=line_of_credit_supervisor.interest_accrual_common.PARAM_DAYS_IN_YEAR,
                    at_datetime=None,
                ),
                call(
                    vault=self.mock_loan_vault,
                    name=line_of_credit_supervisor.interest_application.PARAM_APPLICATION_PRECISION,
                    at_datetime=None,
                ),
            ]
        )
        self.mock_get_balance_default_dict_from_mapping.assert_called_once_with(
            mapping=sentinel.fetched_balances, effective_datetime=DEFAULT_DATETIME
        )
        mock_get_denomination_parameter.assert_called_once_with(vault=self.mock_loan_vault)
        self.mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=[
                line_of_credit_supervisor.lending_addresses.INTEREST_OVERDUE,
                line_of_credit_supervisor.lending_addresses.PRINCIPAL_OVERDUE,
            ],
            denomination=sentinel.denomination,
        )
        self.mock_daily_accrual.assert_called_once_with(
            customer_account=self.mock_loan_vault.account_id,
            customer_address=line_of_credit_supervisor.lending_addresses.PENALTIES,
            denomination=sentinel.denomination,
            internal_account=sentinel.penalty_interest_income_account,
            days_in_year=sentinel.days_in_year,
            yearly_rate=Decimal("0.25"),
            effective_balance=sentinel.balance_to_accrue_on,
            account_type=line_of_credit_supervisor.DRAWDOWN_LOAN_ACCOUNT_TYPE,
            event_type=hook_arguments.event_type,
            effective_datetime=DEFAULT_DATETIME,
            payable=False,
            precision=2,
            rounding=line_of_credit_supervisor.ROUND_HALF_UP,
        )

    def test_penalty_does_not_include_base_rate(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                line_of_credit_supervisor.drawdown_loan.PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE: False,  # noqa: E501
                line_of_credit_supervisor.drawdown_loan.PARAM_PENALTY_INTEREST_INCOME_ACCOUNT: sentinel.penalty_interest_income_account,  # noqa: E501
                line_of_credit_supervisor.drawdown_loan.PARAM_PENALTY_INTEREST_RATE: Decimal(
                    "0.10"
                ),
                line_of_credit_supervisor.interest_accrual_common.PARAM_DAYS_IN_YEAR: sentinel.days_in_year,  # noqa: E501
                line_of_credit_supervisor.interest_application.PARAM_APPLICATION_PRECISION: "2",
            },
        )
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )

        result = line_of_credit_supervisor._get_penalty_interest_accrual_custom_instructions(
            loan_vault=self.mock_loan_vault,
            hook_arguments=hook_arguments,
            denomination=sentinel.denomination,
        )

        self.assertListEqual(result, [sentinel.accrual_ci])

        mock_get_parameter.assert_has_calls(
            [
                call(
                    vault=self.mock_loan_vault,
                    name=line_of_credit_supervisor.drawdown_loan.PARAM_PENALTY_INTEREST_RATE,
                    at_datetime=None,
                ),
                call(
                    vault=self.mock_loan_vault,
                    name=line_of_credit_supervisor.drawdown_loan.PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE,  # noqa: E501
                    is_boolean=True,
                    at_datetime=None,
                ),
                call(
                    vault=self.mock_loan_vault,
                    name=line_of_credit_supervisor.drawdown_loan.PARAM_PENALTY_INTEREST_INCOME_ACCOUNT,  # noqa: E501
                    at_datetime=None,
                ),
                call(
                    vault=self.mock_loan_vault,
                    name=line_of_credit_supervisor.interest_accrual_common.PARAM_DAYS_IN_YEAR,
                    at_datetime=None,
                ),
                call(
                    vault=self.mock_loan_vault,
                    name=line_of_credit_supervisor.interest_application.PARAM_APPLICATION_PRECISION,
                    at_datetime=None,
                ),
            ]
        )
        self.mock_get_balance_default_dict_from_mapping.assert_called_once_with(
            mapping=sentinel.fetched_balances, effective_datetime=DEFAULT_DATETIME
        )
        self.mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=[
                line_of_credit_supervisor.lending_addresses.INTEREST_OVERDUE,
                line_of_credit_supervisor.lending_addresses.PRINCIPAL_OVERDUE,
            ],
            denomination=sentinel.denomination,
        )
        self.mock_daily_accrual.assert_called_once_with(
            customer_account=self.mock_loan_vault.account_id,
            customer_address=line_of_credit_supervisor.lending_addresses.PENALTIES,
            denomination=sentinel.denomination,
            internal_account=sentinel.penalty_interest_income_account,
            days_in_year=sentinel.days_in_year,
            yearly_rate=Decimal("0.10"),
            effective_balance=sentinel.balance_to_accrue_on,
            account_type=line_of_credit_supervisor.DRAWDOWN_LOAN_ACCOUNT_TYPE,
            event_type=hook_arguments.event_type,
            effective_datetime=DEFAULT_DATETIME,
            payable=False,
            precision=2,
            rounding=line_of_credit_supervisor.ROUND_HALF_UP,
        )


class GetUpdateCheckOverdueScheduleTest(LineOfCreditSupervisorTestBase):
    @patch.object(line_of_credit_supervisor, "_get_repayment_period_parameter")
    @patch.object(line_of_credit_supervisor.utils, "get_schedule_expression_from_parameters")
    def test_update_check_overdue_schedule_no_skip(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_repayment_period_parameter: MagicMock,
    ):
        mock_get_schedule_expression_from_parameters.return_value = SentinelScheduleExpression(
            "expression"
        )
        mock_get_repayment_period_parameter.return_value = 1
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )
        expected = [
            UpdatePlanEventTypeDirective(
                event_type=line_of_credit_supervisor.overdue.CHECK_OVERDUE_EVENT,
                expression=SentinelScheduleExpression("expression"),
                skip=False,
            )
        ]
        result = line_of_credit_supervisor._update_check_overdue_schedule(
            loc_vault=sentinel.vault, hook_arguments=hook_arguments
        )
        self.assertListEqual(result, expected)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=sentinel.vault,
            parameter_prefix=line_of_credit_supervisor.overdue.CHECK_OVERDUE_PREFIX,
            day=(DEFAULT_DATETIME + relativedelta(days=1)).day,
        )
        mock_get_repayment_period_parameter.assert_called_once_with(loc_vault=sentinel.vault)

    @patch.object(line_of_credit_supervisor, "_get_repayment_period_parameter")
    @patch.object(line_of_credit_supervisor.utils, "get_schedule_expression_from_parameters")
    def test_update_check_overdue_schedule_with_skip(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_repayment_period_parameter: MagicMock,
    ):
        mock_get_schedule_expression_from_parameters.return_value = SentinelScheduleExpression(
            "expression"
        )
        mock_get_repayment_period_parameter.return_value = 1
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )
        expected = [
            UpdatePlanEventTypeDirective(
                event_type=line_of_credit_supervisor.overdue.CHECK_OVERDUE_EVENT,
                skip=True,
            )
        ]
        result = line_of_credit_supervisor._update_check_overdue_schedule(
            loc_vault=sentinel.vault, hook_arguments=hook_arguments, skip=True
        )
        self.assertListEqual(result, expected)
        mock_get_schedule_expression_from_parameters.assert_not_called()
        mock_get_repayment_period_parameter.assert_not_called()


@patch.object(line_of_credit_supervisor.common_parameters, "get_denomination_parameter")
@patch.object(line_of_credit_supervisor.utils, "get_balance_default_dict_from_mapping")
@patch.object(line_of_credit_supervisor.utils, "sum_balances")
class HandleDelinquencyTest(LineOfCreditSupervisorTestBase):
    def test_handle_delinquency_when_overdue(
        self,
        mock_sum_balances: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_get_denomination_parameter: MagicMock,
    ):
        loc_vault = self.create_supervisee_mock(
            account_id="loc account",
            requires_fetched_balances=sentinel.fetched_balances,
        )
        loan_vault_1 = self.create_supervisee_mock(
            account_id="loan account 1",
            requires_fetched_balances=sentinel.fetched_balances,
        )
        loan_vault_2 = self.create_supervisee_mock(
            account_id="loan account 2",
            requires_fetched_balances=sentinel.fetched_balances,
        )
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_get_balance_default_dict_from_mapping.side_effect = [
            sentinel.loan_1_vault_balances,
            sentinel.loan_2_vault_balances,
        ]
        mock_sum_balances.return_value = Decimal("10")
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )
        expected = {
            "loc account": [
                AccountNotificationDirective(
                    notification_type=line_of_credit_supervisor.DELINQUENT_NOTIFICATION,  # noqa: E501
                    notification_details={
                        "account_id": loc_vault.account_id,
                    },
                )
            ],
        }
        result = line_of_credit_supervisor._handle_delinquency(
            hook_arguments=hook_arguments,
            loc_vault=loc_vault,
            loan_vaults=[loan_vault_1, loan_vault_2],
        )
        self.assertDictEqual(result, expected)
        mock_get_denomination_parameter.assert_called_once_with(vault=loc_vault)
        mock_get_balance_default_dict_from_mapping.assert_has_calls(
            calls=[
                call(
                    mapping=loan_vault_1.get_balances_timeseries(),
                    effective_datetime=hook_arguments.effective_datetime,
                ),
            ]
        )
        mock_sum_balances.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.loan_1_vault_balances,
                    addresses=line_of_credit_supervisor.lending_addresses.OVERDUE_ADDRESSES,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    def test_handle_delinquency_nothing_overdue(
        self,
        mock_sum_balances: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_get_denomination_parameter: MagicMock,
    ):
        loc_vault = self.create_supervisee_mock(
            account_id="loc account",
            requires_fetched_balances=sentinel.fetched_balances,
        )
        loan_vault_1 = self.create_supervisee_mock(
            account_id="loan account 1",
            requires_fetched_balances=sentinel.fetched_balances,
        )
        loan_vault_2 = self.create_supervisee_mock(
            account_id="loan account 2",
            requires_fetched_balances=sentinel.fetched_balances,
        )
        mock_get_denomination_parameter.return_value = sentinel.denomination
        mock_get_balance_default_dict_from_mapping.side_effect = [
            sentinel.loan_1_vault_balances,
            sentinel.loan_2_vault_balances,
        ]
        mock_sum_balances.return_value = Decimal("0")
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )
        result = line_of_credit_supervisor._handle_delinquency(
            hook_arguments=hook_arguments,
            loc_vault=loc_vault,
            loan_vaults=[loan_vault_1, loan_vault_2],
        )
        self.assertDictEqual(result, {})
        mock_get_denomination_parameter.assert_called_once_with(vault=loc_vault)
        mock_get_balance_default_dict_from_mapping.assert_has_calls(
            calls=[
                call(
                    mapping=loan_vault_1.get_balances_timeseries(),
                    effective_datetime=hook_arguments.effective_datetime,
                ),
                call(
                    mapping=loan_vault_2.get_balances_timeseries(),
                    effective_datetime=hook_arguments.effective_datetime,
                ),
            ]
        )
        mock_sum_balances.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.loan_1_vault_balances,
                    addresses=line_of_credit_supervisor.lending_addresses.OVERDUE_ADDRESSES,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.loan_2_vault_balances,
                    addresses=line_of_credit_supervisor.lending_addresses.OVERDUE_ADDRESSES,
                    denomination=sentinel.denomination,
                ),
            ]
        )


@patch.object(line_of_credit_supervisor.utils, "get_schedule_expression_from_parameters")
class UpdateCheckDelinquencyScheduleTest(LineOfCreditSupervisorTestBase):
    def test_update_check_delinquency_schedule_no_skip(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
    ):
        mock_get_schedule_expression_from_parameters.return_value = SentinelScheduleExpression(
            "expression"
        )
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )
        expected = [
            UpdatePlanEventTypeDirective(
                event_type=line_of_credit_supervisor.delinquency.CHECK_DELINQUENCY_EVENT,
                expression=SentinelScheduleExpression("expression"),
                skip=False,
            )
        ]
        result = line_of_credit_supervisor._update_check_delinquency_schedule(
            loc_vault=sentinel.vault, hook_arguments=hook_arguments, grace_period=1
        )
        self.assertListEqual(result, expected)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=sentinel.vault,
            parameter_prefix=line_of_credit_supervisor.delinquency.CHECK_DELINQUENCY_PREFIX,
            day=(DEFAULT_DATETIME + relativedelta(days=1)).day,
        )

    def test_update_check_overdue_schedule_with_skip(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
    ):
        mock_get_schedule_expression_from_parameters.return_value = SentinelScheduleExpression(
            "expression"
        )
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )
        expected = [
            UpdatePlanEventTypeDirective(
                event_type=line_of_credit_supervisor.delinquency.CHECK_DELINQUENCY_EVENT,
                skip=True,
            )
        ]
        result = line_of_credit_supervisor._update_check_delinquency_schedule(
            loc_vault=sentinel.vault, hook_arguments=hook_arguments, grace_period=1, skip=True
        )
        self.assertListEqual(result, expected)
        mock_get_schedule_expression_from_parameters.assert_not_called()


@patch.object(line_of_credit_supervisor.utils, "get_end_of_month_schedule_from_parameters")
class UpdateDueAmountCalculationDayScheduleTest(LineOfCreditSupervisorTestBase):
    event_type = line_of_credit_supervisor.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT

    def test_event_directives_returned_from_update_due_amount_calculation_day_schedule(
        self,
        mock_get_end_of_month_schedule_from_parameters: MagicMock,
    ):
        mock_get_end_of_month_schedule_from_parameters.return_value = SentinelEndOfMonthSchedule(
            "end_of_month"
        )
        mock_loc_vault = self.create_mock("loc account")
        expected = [
            UpdatePlanEventTypeDirective(
                event_type=self.event_type,
                schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
                skip=ScheduleSkip(end=DEFAULT_DATETIME - relativedelta(seconds=1)),
            )
        ], {
            mock_loc_vault.account_id: [
                UpdateAccountEventTypeDirective(
                    event_type=self.event_type,
                    schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
                    skip=ScheduleSkip(end=DEFAULT_DATETIME - relativedelta(seconds=1)),
                )
            ]
        }
        result = line_of_credit_supervisor._update_due_amount_calculation_day_schedule(
            loc_vault=mock_loc_vault,
            schedule_start_datetime=DEFAULT_DATETIME,
            due_amount_calculation_day=1,
        )
        self.assertEqual(result, expected)
        mock_get_end_of_month_schedule_from_parameters.assert_has_calls(
            [
                call(vault=mock_loc_vault, parameter_prefix="due_amount_calculation", day=1),
            ]
        )


@patch.object(
    line_of_credit_supervisor.due_amount_calculation, "get_next_due_amount_calculation_datetime"
)
@patch.object(line_of_credit_supervisor, "_update_due_amount_calculation_day_schedule")
@patch.object(
    line_of_credit_supervisor.due_amount_calculation,
    "DUE_AMOUNT_CALCULATION_EVENT",
    sentinel.event_type,
)
@patch.object(
    line_of_credit_supervisor.due_amount_calculation,
    "PARAM_DUE_AMOUNT_CALCULATION_DAY",
    sentinel.param_name,
)
class HandleDueAmountCalculationDayChange(LineOfCreditSupervisorTestBase):
    def setUp(self) -> None:
        self.last_execution_datetime = DEFAULT_DATETIME - relativedelta(days=2)
        self.last_execution_datetimes = {sentinel.event_type: self.last_execution_datetime}
        self.new_param_updated_datetime = self.last_execution_datetime + relativedelta(days=1)
        self.parameter_timeseries = ParameterTimeseries(
            iterable=[
                (DEFAULT_DATETIME - relativedelta(days=10), sentinel.due_calc_day),
                (self.new_param_updated_datetime, sentinel.due_calc_day),
            ]
        )
        self.mock_loc_vault = self.create_mock(
            account_id="loc account",
            last_execution_datetimes=self.last_execution_datetimes,
            parameter_ts={sentinel.param_name: self.parameter_timeseries},
        )
        self.mock_update_due_amount_calculation_day_schedule_return_value = [
            UpdatePlanEventTypeDirective(
                event_type=sentinel.event_type,
                schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
                skip=ScheduleSkip(end=DEFAULT_DATETIME - relativedelta(seconds=1)),
            )
        ], {
            self.mock_loc_vault.account_id: [
                UpdateAccountEventTypeDirective(
                    event_type=sentinel.event_type,
                    schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
                    skip=ScheduleSkip(end=DEFAULT_DATETIME - relativedelta(seconds=1)),
                )
            ]
        }
        return super().setUp()

    def test_handle_due_amount_calculation_day_change_param_updated_after_last_execution_datetime(
        self,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
        mock_get_next_due_amount_calculation_datetime: MagicMock,
    ):
        next_due_calc_datetime = DEFAULT_DATETIME + relativedelta(months=1)
        mock_get_next_due_amount_calculation_datetime.return_value = next_due_calc_datetime
        mock_update_due_amount_calculation_day_schedule.return_value = (
            self.mock_update_due_amount_calculation_day_schedule_return_value
        )
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )
        expected = [
            UpdatePlanEventTypeDirective(
                event_type=sentinel.event_type,
                schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
                skip=ScheduleSkip(end=DEFAULT_DATETIME - relativedelta(seconds=1)),
            )
        ], {
            self.mock_loc_vault.account_id: [
                UpdateAccountEventTypeDirective(
                    event_type=sentinel.event_type,
                    schedule_method=SentinelEndOfMonthSchedule("end_of_month"),
                    skip=ScheduleSkip(end=DEFAULT_DATETIME - relativedelta(seconds=1)),
                )
            ]
        }
        result = line_of_credit_supervisor._handle_due_amount_calculation_day_change(
            loc_vault=self.mock_loc_vault,
            hook_arguments=hook_arguments,
        )
        self.assertEqual(result, expected)
        mock_get_next_due_amount_calculation_datetime.assert_called_once_with(
            vault=self.mock_loc_vault,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=1,
            remaining_term=1,
        )
        mock_update_due_amount_calculation_day_schedule.assert_called_once_with(
            loc_vault=self.mock_loc_vault,
            schedule_start_datetime=next_due_calc_datetime,
            due_amount_calculation_day=sentinel.due_calc_day,
        )

    def test_handle_due_amount_calculation_day_change_no_param_changes(
        self,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
        mock_get_next_due_amount_calculation_datetime: MagicMock,
    ):
        parameter_timeseries = ParameterTimeseries(
            iterable=[
                (DEFAULT_DATETIME - relativedelta(days=10), sentinel.due_calc_day),
            ]
        )
        mock_loc_vault = self.create_mock(
            account_id="loc account",
            last_execution_datetimes=self.last_execution_datetimes,
            parameter_ts={sentinel.param_name: parameter_timeseries},
        )
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )
        expected = [], {}
        result = line_of_credit_supervisor._handle_due_amount_calculation_day_change(
            loc_vault=mock_loc_vault,
            hook_arguments=hook_arguments,
        )
        self.assertEqual(result, expected)
        mock_get_next_due_amount_calculation_datetime.assert_not_called()
        mock_update_due_amount_calculation_day_schedule.assert_not_called()

    def test_handle_due_amount_calculation_day_change_param_updated_before_last_execution(
        self,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
        mock_get_next_due_amount_calculation_datetime: MagicMock,
    ):
        new_param_updated_datetime = self.last_execution_datetime - relativedelta(days=1)
        parameter_timeseries = ParameterTimeseries(
            iterable=[
                (DEFAULT_DATETIME - relativedelta(days=10), sentinel.due_calc_day),
                (new_param_updated_datetime, sentinel.due_calc_day),
            ]
        )
        mock_loc_vault = self.create_mock(
            account_id="loc account",
            last_execution_datetimes=self.last_execution_datetimes,
            parameter_ts={sentinel.param_name: parameter_timeseries},
        )
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )
        expected = [], {}
        result = line_of_credit_supervisor._handle_due_amount_calculation_day_change(
            loc_vault=mock_loc_vault,
            hook_arguments=hook_arguments,
        )
        self.assertEqual(result, expected)
        mock_get_next_due_amount_calculation_datetime.assert_not_called()
        mock_update_due_amount_calculation_day_schedule.assert_not_called()

    def test_handle_due_amount_calculation_day_change_next_due_dt_eq_last_execution_plus_1_month(
        self,
        mock_update_due_amount_calculation_day_schedule: MagicMock,
        mock_get_next_due_amount_calculation_datetime: MagicMock,
    ):
        next_due_calc_datetime = self.last_execution_datetime + relativedelta(months=1)
        mock_loc_vault = self.create_mock(
            account_id="loc account",
            last_execution_datetimes=self.last_execution_datetimes,
            parameter_ts={sentinel.param_name: self.parameter_timeseries},
        )
        mock_get_next_due_amount_calculation_datetime.return_value = next_due_calc_datetime
        mock_update_due_amount_calculation_day_schedule.return_value = (
            self.mock_update_due_amount_calculation_day_schedule_return_value
        )
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=sentinel.event_type,
            supervisee_pause_at_datetime={},
        )
        expected = [], {}
        result = line_of_credit_supervisor._handle_due_amount_calculation_day_change(
            loc_vault=mock_loc_vault,
            hook_arguments=hook_arguments,
        )
        self.assertEqual(result, expected)
        mock_get_next_due_amount_calculation_datetime.assert_called_once_with(
            vault=mock_loc_vault,
            effective_datetime=DEFAULT_DATETIME,
            elapsed_term=1,
            remaining_term=1,
        )
        mock_update_due_amount_calculation_day_schedule.assert_not_called()
