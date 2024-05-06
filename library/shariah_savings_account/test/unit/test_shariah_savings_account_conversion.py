# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import sentinel

# library
import library.shariah_savings_account.contracts.template.shariah_savings_account as shariah_savings_account  # noqa: E501
from library.shariah_savings_account.test.unit.test_shariah_savings_account_common import (  # noqa: E501
    ShariahSavingsAccountTestBase,
)

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


class ConversionTest(ShariahSavingsAccountTestBase):
    def test_conversion_passes_schedules_through(self):

        effective_datetime = DEFAULT_DATETIME
        existing_schedules: dict[str, ScheduledEvent] = {
            sentinel.tiered_profit_accrual_event_type: SentinelScheduledEvent(
                "tiered_profit_accrual_event"
            ),
            sentinel.profit_application_event_type: SentinelScheduledEvent(
                "profit_application_event"
            ),
        }

        hook_args = ConversionHookArguments(
            effective_datetime=effective_datetime, existing_schedules=existing_schedules
        )

        expected_result = ConversionHookResult(
            scheduled_events_return_value=existing_schedules,
            posting_instructions_directives=[],
        )

        hook_result = shariah_savings_account.conversion_hook(
            vault=sentinel.vault, hook_arguments=hook_args
        )

        self.assertEqual(hook_result, expected_result)
