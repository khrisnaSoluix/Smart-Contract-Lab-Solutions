# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
import library.shariah_savings_account.contracts.template.shariah_savings_account as shariah_savings_account  # noqa: E501
from library.shariah_savings_account.test.unit.test_shariah_savings_account_common import (  # noqa: E501
    ShariahSavingsAccountTestBase,
)

# contracts api
from contracts_api import ActivationHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ActivationHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelScheduledEvent,
)


@patch.object(shariah_savings_account.profit_application, "scheduled_events")
@patch.object(shariah_savings_account.tiered_profit_accrual, "scheduled_events")
class ActivationHookTest(ShariahSavingsAccountTestBase):
    def test_execution_schedules_returns_correct_schedule(
        self,
        mock_scheduled_events_accrual: MagicMock,
        mock_scheduled_events_application: MagicMock,
    ):
        # Set up mocks
        mock_vault = self.create_mock()

        accrual_scheduled_event = {sentinel.accrual: SentinelScheduledEvent("accrual")}
        application_scheduled_event = {sentinel.application: SentinelScheduledEvent("application")}
        mock_scheduled_events_application.return_value = application_scheduled_event
        mock_scheduled_events_accrual.return_value = accrual_scheduled_event

        # Run hook
        hook_arguments = ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        hook_result = shariah_savings_account.activation_hook(mock_vault, hook_arguments)

        # Validate result
        expected_events = {}
        expected_events.update(accrual_scheduled_event)
        expected_events.update(application_scheduled_event)
        expected_result = ActivationHookResult(scheduled_events_return_value=expected_events)

        self.assertEqual(hook_result, expected_result)

        # Assert calls
        mock_scheduled_events_accrual.assert_called_once_with(
            vault=mock_vault,
            start_datetime=DEFAULT_DATETIME,
        )
        mock_scheduled_events_application.assert_called_once_with(
            vault=mock_vault,
            start_datetime=DEFAULT_DATETIME,
        )
