from datetime import datetime
from zoneinfo import ZoneInfo
from unittest import TestCase, mock

from contracts_api import smart_contracts_lib  # type: ignore
from contracts_api import (
    ParameterTimeseries,
    OptionalValue,
    ActivationHookArguments,
)

from . import savings_v400


class SavingsTestCaseV400(TestCase):
    def test_activation_hook(self):
        # Define the vault data values for the vault mocks
        def mock_get_parameter_timeseries(name):
            if name == "key_date":
                return ParameterTimeseries(
                    [
                        (creation_datetime, OptionalValue(payday)),
                    ]
                )
            self.assertTrue(False, f"Unexpected parameter name '{name}'")

        payday = 27
        timezone = ZoneInfo("UTC")
        creation_datetime = datetime(2022, 10, 1, 1, 1, tzinfo=timezone)
        effective_datetime = datetime(2022, 10, 10, 1, 1, tzinfo=timezone)
        hook_args = ActivationHookArguments(effective_datetime=effective_datetime)
        # Create and mock the vault
        mock_vault = mock.create_autospec(smart_contracts_lib.VaultFunctionsABC)
        mock_vault.get_account_creation_datetime.return_value = creation_datetime
        mock_vault.get_parameter_timeseries.side_effect = mock_get_parameter_timeseries
        # Call the savings account activation hook
        hook_result = savings_v400.activation_hook(mock_vault, hook_args)
        # Assert on the hook results and vault method calls
        mock_vault.get_account_creation_datetime.assert_called()
        scheduled_events = hook_result.scheduled_events_return_value
        self.assertEqual(2, len(scheduled_events))
        self.assertTrue("APPLY_ACCRUED_INTEREST" in scheduled_events)
        expression = scheduled_events["APPLY_ACCRUED_INTEREST"].expression
        self.assertEqual(str(payday), expression.day)
        self.assertEqual(0, expression.hour)
        self.assertEqual(1, expression.minute)
        self.assertTrue(
            all(
                attr is None
                for attr in (
                    expression.second,
                    expression.day_of_week,
                    expression.month,
                    expression.year,
                )
            )
        )
        self.assertTrue("ACCRUE_INTEREST" in scheduled_events)
        expression = scheduled_events["ACCRUE_INTEREST"].expression
        self.assertEqual(0, expression.hour)
        self.assertTrue(
            all(
                attr is None
                for attr in (
                    expression.second,
                    expression.minute,
                    expression.day,
                    expression.day_of_week,
                    expression.month,
                    expression.year,
                )
            )
        )
