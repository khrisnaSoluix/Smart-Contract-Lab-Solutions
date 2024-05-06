# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import sentinel

# library
import library.offset_mortgage.supervisors.template.offset_mortgage as offset_mortgage
from library.offset_mortgage.test.unit.test_offset_mortgage_common import OffsetMortgageTestBase

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ScheduledEvent,
    ScheduleExpression,
    SupervisorActivationHookResult,
)


class ActivationTest(OffsetMortgageTestBase):
    def test_activation_schedules_returned(self):
        # construct mocks
        mock_vault = self.create_supervisor_mock(creation_date=DEFAULT_DATETIME)

        # construct expected result
        expected_result = SupervisorActivationHookResult(
            scheduled_events_return_value={
                offset_mortgage.ACCRUE_OFFSET_INTEREST_EVENT: ScheduledEvent(
                    start_datetime=DEFAULT_DATETIME,
                    expression=ScheduleExpression(hour=0, minute=0, second=1),
                )
            }
        )

        # run function
        result = offset_mortgage.activation_hook(mock_vault, sentinel.hook_args)
        self.assertEqual(result, expected_result)
