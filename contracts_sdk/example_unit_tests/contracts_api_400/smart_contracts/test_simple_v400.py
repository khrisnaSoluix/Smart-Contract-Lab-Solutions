from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest import TestCase, mock

from contracts_api import smart_contracts_lib  # type: ignore
from contracts_api import ActivationHookArguments, ScheduledEventHookArguments

from . import simple_v400


class SimpleTestCaseV400(TestCase):
    def test_activation_hook(self):
        # Define the vault data values for the vault mocks
        creation_datetime = datetime(2000, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC"))
        effective_datetime = datetime(2022, 10, 10, 1, 1, tzinfo=ZoneInfo("UTC"))
        hook_args = ActivationHookArguments(effective_datetime=effective_datetime)
        # Create and mock the vault
        mock_vault = mock.create_autospec(smart_contracts_lib.VaultFunctionsABC)
        mock_vault.get_account_creation_datetime.return_value = creation_datetime
        # Call the simple account activation hook
        hook_result = simple_v400.activation_hook(mock_vault, hook_args)
        # Assert on the hook results and vault method calls
        mock_vault.get_account_creation_datetime.assert_called()
        self.assertTrue(
            "EXAMPLE_EVENT" in hook_result.scheduled_events_return_value,
            "Missing expected 'EXAMPLE_EVENT' ScheduledEvent",
        )
        scheduled_event = hook_result.scheduled_events_return_value["EXAMPLE_EVENT"]
        self.assertEqual(creation_datetime, scheduled_event.start_datetime)
        self.assertEqual(creation_datetime + timedelta(minutes=1), scheduled_event.end_datetime)
        expression = scheduled_event.expression
        self.assertEqual("*", expression.minute)
        self.assertTrue(
            all(
                attr is None
                for attr in (
                    expression.second,
                    expression.hour,
                    expression.day,
                    expression.day_of_week,
                    expression.month,
                    expression.year,
                )
            )
        )

    def test_scheduled_event_hook(self):
        # Define the vault data values for the vault mocks
        test_event = "EXAMPLE_EVENT"
        effective_datetime = datetime(2022, 10, 10, 1, 1, tzinfo=ZoneInfo("UTC"))
        hook_args = ScheduledEventHookArguments(
            effective_datetime=effective_datetime, event_type=test_event
        )
        # Create and mock the vault
        mock_vault = mock.create_autospec(smart_contracts_lib.VaultFunctionsABC)
        # Call the simple account scheduled event hook
        response = simple_v400.scheduled_event_hook(mock_vault, hook_args)
        # Assert on the hook results and vault method calls
        self.assertEqual(1, len(response.update_account_event_type_directives))
        directive = response.update_account_event_type_directives[0]
        self.assertEqual(test_event, directive.event_type)
        self.assertTrue(directive.skip)
        # Check that the directive not instructed any schedule expression or end_datetime changes
        self.assertIsNone(directive.end_datetime)
        self.assertIsNone(directive.expression)
        self.assertIsNone(directive.schedule_method)
