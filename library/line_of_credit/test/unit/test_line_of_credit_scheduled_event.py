# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import sentinel

# library
from library.line_of_credit.contracts.template import line_of_credit
from library.line_of_credit.test.unit.test_line_of_credit_common import (
    DEFAULT_DATETIME,
    LineOfCreditTestBase,
)

# contracts api
from contracts_api import ScheduledEventHookArguments


class DueAmountCalculationEventTest(LineOfCreditTestBase):
    event_type = line_of_credit.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT

    def test_due_amount_calc_event_returns_none(
        self,
    ):
        hook_arguments = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
        )
        result = line_of_credit.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertIsNone(result)
