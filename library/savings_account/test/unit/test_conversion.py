# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import sentinel

# library
import library.savings_account.contracts.template.savings_account as savings_account
from library.savings_account.test.unit.savings_account_common import SavingsAccountTest

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


class ConversionTest(SavingsAccountTest):
    def test_conversion_passes_schedules_through(self):

        effective_datetime = DEFAULT_DATETIME
        existing_schedules: dict[str, ScheduledEvent] = {
            sentinel.accrual_event_type: SentinelScheduledEvent("accrual_event"),
            sentinel.application_event_type: SentinelScheduledEvent("application_event"),
            sentinel.fee_event_type: SentinelScheduledEvent("fee_event"),
        }

        hook_args = ConversionHookArguments(
            effective_datetime=effective_datetime, existing_schedules=existing_schedules
        )

        expected_result = ConversionHookResult(
            scheduled_events_return_value=existing_schedules,
            posting_instructions_directives=[],
        )

        hook_result = savings_account.conversion_hook(
            vault=sentinel.vault, hook_arguments=hook_args
        )

        self.assertEqual(hook_result, expected_result)
