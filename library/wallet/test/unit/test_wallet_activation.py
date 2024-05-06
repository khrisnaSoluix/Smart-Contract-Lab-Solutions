# library
import library.wallet.contracts.template.wallet as contract
from library.wallet.test.unit.test_wallet_common import DEFAULT_DATETIME, WalletTestBase

# contracts api
from contracts_api import ActivationHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ScheduledEvent,
    ScheduleExpression,
)


class ActivationHookTest(WalletTestBase):
    def test_execution_schedules_returns_correct_schedule(self):
        mock_vault = self.create_mock()

        hook_arguments = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        hook_result = contract.activation_hook(mock_vault, hook_arguments)
        events = hook_result.scheduled_events_return_value

        zero_out_daily_spend_schedule = {"hour": "23", "minute": "59", "second": "59"}
        self.assertEqual(
            events["ZERO_OUT_DAILY_SPEND"],
            ScheduledEvent(
                expression=ScheduleExpression(**zero_out_daily_spend_schedule),
                start_datetime=DEFAULT_DATETIME,
            ),
        )
