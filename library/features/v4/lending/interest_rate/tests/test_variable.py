# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.lending.interest_rate import variable

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest


class VariableTest(FeatureTest):
    maxDiff = None


@patch.object(variable.utils, "get_parameter")
class AnnualInterestRateTest(VariableTest):
    expected_parameter_calls = [
        call(vault=sentinel.vault, name="variable_interest_rate", at_datetime=None),
        call(vault=sentinel.vault, name="variable_rate_adjustment", at_datetime=None),
        call(
            vault=sentinel.vault,
            name="annual_interest_rate_cap",
            is_optional=True,
            default_value=Decimal("inf"),
            at_datetime=None,
        ),
        call(
            vault=sentinel.vault,
            name="annual_interest_rate_floor",
            is_optional=True,
            default_value=Decimal("-inf"),
            at_datetime=None,
        ),
    ]

    def test_get_annual_interest_rate_no_adjustment_no_floor_or_cap(
        self, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "variable_interest_rate": Decimal("0.0120"),
                "variable_rate_adjustment": Decimal("0"),
                "annual_interest_rate_cap": Decimal("inf"),
                "annual_interest_rate_floor": Decimal("-inf"),
            }
        )
        self.assertEqual(variable.get_annual_interest_rate(vault=sentinel.vault), Decimal("0.0120"))
        mock_get_parameter.assert_has_calls(calls=self.expected_parameter_calls)
        self.assertEqual(mock_get_parameter.call_count, 4)

    def test_get_annual_interest_rate_with_adjustment_no_floor_or_cap(
        self, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "variable_interest_rate": Decimal("0.0120"),
                "variable_rate_adjustment": Decimal("0.0120"),
                "annual_interest_rate_cap": Decimal("inf"),
                "annual_interest_rate_floor": Decimal("-inf"),
            }
        )
        self.assertEqual(variable.get_annual_interest_rate(vault=sentinel.vault), Decimal("0.0240"))
        mock_get_parameter.assert_has_calls(calls=self.expected_parameter_calls)
        self.assertEqual(mock_get_parameter.call_count, 4)

    def test_get_annual_interest_rate_with_adjustment_cap_less_than_interest_rate(
        self, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "variable_interest_rate": Decimal("0.0120"),
                "variable_rate_adjustment": Decimal("0.0120"),
                "annual_interest_rate_cap": Decimal("0.0150"),
                "annual_interest_rate_floor": Decimal("-inf"),
            }
        )
        self.assertEqual(variable.get_annual_interest_rate(vault=sentinel.vault), Decimal("0.0150"))
        mock_get_parameter.assert_has_calls(calls=self.expected_parameter_calls)
        self.assertEqual(mock_get_parameter.call_count, 4)

    def test_get_annual_interest_rate_with_adjustment_cap_greater_than_interest_rate(
        self, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "variable_interest_rate": Decimal("0.0120"),
                "variable_rate_adjustment": Decimal("0.0120"),
                "annual_interest_rate_cap": Decimal("0.5"),
                "annual_interest_rate_floor": Decimal("-inf"),
            }
        )
        self.assertEqual(variable.get_annual_interest_rate(vault=sentinel.vault), Decimal("0.0240"))
        mock_get_parameter.assert_has_calls(calls=self.expected_parameter_calls)
        self.assertEqual(mock_get_parameter.call_count, 4)

    def test_get_annual_interest_rate_with_adjustment_floor_greater_than_interest_rate(
        self, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "variable_interest_rate": Decimal("0.0120"),
                "variable_rate_adjustment": Decimal("0.0120"),
                "annual_interest_rate_cap": Decimal("inf"),
                "annual_interest_rate_floor": Decimal("0.5"),
            }
        )
        self.assertEqual(variable.get_annual_interest_rate(vault=sentinel.vault), Decimal("0.5"))
        mock_get_parameter.assert_has_calls(calls=self.expected_parameter_calls)
        self.assertEqual(mock_get_parameter.call_count, 4)

    def test_get_annual_interest_rate_with_adjustment_floor_less_than_interest_rate(
        self, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "variable_interest_rate": Decimal("0.0120"),
                "variable_rate_adjustment": Decimal("0.0120"),
                "annual_interest_rate_cap": Decimal("inf"),
                "annual_interest_rate_floor": Decimal("0.005"),
            }
        )
        self.assertEqual(variable.get_annual_interest_rate(vault=sentinel.vault), Decimal("0.0240"))
        mock_get_parameter.assert_has_calls(calls=self.expected_parameter_calls)
        self.assertEqual(mock_get_parameter.call_count, 4)

    def test_get_annual_interest_rate_with_adjustment_interest_rate_inside_floor_and_cap(
        self, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "variable_interest_rate": Decimal("0.0120"),
                "variable_rate_adjustment": Decimal("0.0120"),
                "annual_interest_rate_cap": Decimal("0.5"),
                "annual_interest_rate_floor": Decimal("0.005"),
            }
        )
        self.assertEqual(variable.get_annual_interest_rate(vault=sentinel.vault), Decimal("0.0240"))
        mock_get_parameter.assert_has_calls(calls=self.expected_parameter_calls)
        self.assertEqual(mock_get_parameter.call_count, 4)

    def test_get_annual_interest_rate_custom_datetime(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "variable_interest_rate": Decimal("0.0120"),
                "variable_rate_adjustment": Decimal("0.0120"),
                "annual_interest_rate_cap": Decimal("0.5"),
                "annual_interest_rate_floor": Decimal("0.005"),
            }
        )
        self.assertEqual(
            variable.get_annual_interest_rate(
                vault=sentinel.vault, effective_datetime=sentinel.datetime
            ),
            Decimal("0.0240"),
        )
        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.vault,
                    name="variable_interest_rate",
                    at_datetime=sentinel.datetime,
                ),
                call(
                    vault=sentinel.vault,
                    name="variable_rate_adjustment",
                    at_datetime=sentinel.datetime,
                ),
                call(
                    vault=sentinel.vault,
                    name="annual_interest_rate_cap",
                    is_optional=True,
                    default_value=Decimal("inf"),
                    at_datetime=sentinel.datetime,
                ),
                call(
                    vault=sentinel.vault,
                    name="annual_interest_rate_floor",
                    is_optional=True,
                    default_value=Decimal("-inf"),
                    at_datetime=sentinel.datetime,
                ),
            ]
        )
        self.assertEqual(mock_get_parameter.call_count, 4)


@patch.object(variable.utils, "yearly_to_monthly_rate")
@patch.object(variable, "get_annual_interest_rate")
class MonthlyInterestRateTest(VariableTest):
    def test_get_monthly_interest_rate_no_datetime(
        self, mock_get_annual_interest_rate: MagicMock, mock_yearly_to_monthly_rate: MagicMock
    ):
        mock_get_annual_interest_rate.return_value = sentinel.annual_rate
        variable.get_monthly_interest_rate(vault=sentinel.vault)

        mock_get_annual_interest_rate.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=None
        )
        mock_yearly_to_monthly_rate.assert_called_once_with(
            mock_get_annual_interest_rate.return_value
        )

    def test_get_monthly_interest_rate_with_datetime(
        self, mock_get_annual_interest_rate: MagicMock, mock_yearly_to_monthly_rate: MagicMock
    ):
        mock_get_annual_interest_rate.return_value = sentinel.annual_rate
        variable.get_monthly_interest_rate(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )

        mock_get_annual_interest_rate.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        mock_yearly_to_monthly_rate.assert_called_once_with(
            mock_get_annual_interest_rate.return_value
        )


@patch.object(variable.utils, "yearly_to_daily_rate")
@patch.object(variable.utils, "get_parameter")
@patch.object(variable, "get_annual_interest_rate")
class DailyInterestRateTest(VariableTest):
    def test_get_daily_interest_rate(
        self,
        mock_get_annual_interest_rate: MagicMock,
        mock_get_parameter: MagicMock,
        mock_yearly_to_daily_rate: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "days_in_year": sentinel.days_in_year,
            }
        )
        mock_get_annual_interest_rate.return_value = sentinel.annual_rate
        variable.get_daily_interest_rate(vault=sentinel.vault, effective_datetime=sentinel.datetime)

        mock_get_annual_interest_rate.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        mock_yearly_to_daily_rate.assert_called_once_with(
            sentinel.datetime, sentinel.annual_rate, sentinel.days_in_year
        )


@patch.object(variable, "get_monthly_interest_rate")
class ShouldTriggerReamortisationTest(VariableTest):
    expected_mock_calls = [
        call(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
        ),
        call(
            vault=sentinel.vault,
            effective_datetime=sentinel.last_execution_datetime,
        ),
    ]

    def test_should_trigger_reamortisation_true(self, mock_get_monthly_interest_rate: MagicMock):
        mock_get_monthly_interest_rate.side_effect = [
            sentinel.current_interest_rate,
            sentinel.previous_interest_rate,
        ]

        self.assertTrue(
            variable.should_trigger_reamortisation(
                vault=sentinel.vault,
                period_start_datetime=sentinel.effective_datetime,
                period_end_datetime=sentinel.last_execution_datetime,
            )
        )
        mock_get_monthly_interest_rate.assert_has_calls(calls=self.expected_mock_calls)
        self.assertEqual(mock_get_monthly_interest_rate.call_count, 2)

    def test_should_trigger_reamortisation_false(self, mock_get_monthly_interest_rate: MagicMock):
        mock_get_monthly_interest_rate.side_effect = [
            sentinel.current_interest_rate,
            sentinel.current_interest_rate,
        ]

        self.assertFalse(
            variable.should_trigger_reamortisation(
                vault=sentinel.vault,
                period_start_datetime=sentinel.effective_datetime,
                period_end_datetime=sentinel.last_execution_datetime,
            )
        )
        mock_get_monthly_interest_rate.assert_has_calls(calls=self.expected_mock_calls)
        self.assertEqual(mock_get_monthly_interest_rate.call_count, 2)
