# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from dateutil.relativedelta import relativedelta
from unittest.mock import MagicMock, call, patch

# library
import library.line_of_credit.supervisors.template.line_of_credit_supervisor as line_of_credit_supervisor  # noqa: E501
from library.line_of_credit.test.unit.test_line_of_credit_supervisor_common import (
    DEFAULT_DATETIME,
    LineOfCreditSupervisorTestBase,
)

# contracts api
from contracts_api import SupervisorActivationHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    SupervisorActivationHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelScheduledEvent,
)


@patch.object(line_of_credit_supervisor.utils, "create_end_of_time_schedule")
@patch.object(
    line_of_credit_supervisor.supervisor_utils, "supervisee_schedule_sync_scheduled_event"
)
class ActivationTest(LineOfCreditSupervisorTestBase):
    def test_activation_schedules_returned(
        self,
        mock_supervisee_schedule_sync_scheduled_event: MagicMock,
        mock_create_end_of_time_schedule: MagicMock,
    ):
        mock_vault = self.create_supervisor_mock(creation_date=DEFAULT_DATETIME)
        mock_create_end_of_time_schedule.return_value = SentinelScheduledEvent("End of time event")
        mock_supervisee_schedule_sync_scheduled_event.return_value = {
            "SUPERVISEE_SCHEDULE_SYNC": SentinelScheduledEvent("Schedule sync event")
        }

        expected_result = SupervisorActivationHookResult(
            scheduled_events_return_value={
                "SUPERVISEE_SCHEDULE_SYNC": SentinelScheduledEvent("Schedule sync event"),
                line_of_credit_supervisor.interest_accrual_supervisor.ACCRUAL_EVENT: (
                    SentinelScheduledEvent("End of time event")
                ),
                line_of_credit_supervisor.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: (
                    SentinelScheduledEvent("End of time event")
                ),
                line_of_credit_supervisor.overdue.CHECK_OVERDUE_EVENT: SentinelScheduledEvent(
                    "End of time event"
                ),
                line_of_credit_supervisor.delinquency.CHECK_DELINQUENCY_EVENT: (
                    SentinelScheduledEvent("End of time event")
                ),
            }
        )
        month_after_opening = (
            DEFAULT_DATETIME + relativedelta(hour=0, minute=0, second=0) + relativedelta(months=1)
        )

        hook_arguments = SupervisorActivationHookArguments(effective_datetime=DEFAULT_DATETIME)

        result = line_of_credit_supervisor.activation_hook(mock_vault, hook_arguments)
        self.assertEqual(result, expected_result)
        mock_create_end_of_time_schedule.assert_has_calls(
            [call(start_datetime=DEFAULT_DATETIME), call(start_datetime=month_after_opening)]
        )
        mock_supervisee_schedule_sync_scheduled_event.assert_called_once_with(vault=mock_vault)
