# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import sentinel

# library
import library.bnpl.contracts.template.bnpl as bnpl
from library.bnpl.test.unit.test_bnpl_common import BNPLTest

# contracts api
from contracts_api import ConversionHookArguments, ScheduledEvent

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ConversionHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelScheduledEvent,
)


class ConversionTest(BNPLTest):
    def test_conversion_passes_schedules_through(self):
        effective_datetime = DEFAULT_DATETIME
        existing_schedules: dict[str, ScheduledEvent] = {
            sentinel.due_event_type: SentinelScheduledEvent("due_event"),
            sentinel.overdue_event_type: SentinelScheduledEvent("overdue_event"),
            sentinel.late_repayment_event_type: SentinelScheduledEvent("late_repayment_event"),
            sentinel.delinquency_event_type: SentinelScheduledEvent("delinquency_event"),
            sentinel.notification_event_type: SentinelScheduledEvent("notification_event"),
        }

        hook_args = ConversionHookArguments(
            effective_datetime=effective_datetime, existing_schedules=existing_schedules
        )

        expected_result = ConversionHookResult(
            scheduled_events_return_value=existing_schedules,
            posting_instructions_directives=[],
        )

        hook_result = bnpl.conversion_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertEqual(hook_result, expected_result)
