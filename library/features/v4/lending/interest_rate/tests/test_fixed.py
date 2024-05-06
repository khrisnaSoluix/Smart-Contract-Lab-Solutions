# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.lending.interest_rate import fixed

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest


class FixedTest(FeatureTest):
    target_test_file_path = "library/features/v4/lending/interest_rate/fixed.py"


@patch.object(fixed.utils, "get_parameter")
class AnnualInterestRateTest(FixedTest):
    def test_get_annual_interest_rate(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "fixed_interest_rate": Decimal(("0.0120")),
            }
        )
        self.assertEqual(fixed.get_annual_interest_rate(vault=sentinel.vault), Decimal("0.0120"))
        mock_get_parameter.assert_called_once_with(
            sentinel.vault, "fixed_interest_rate", at_datetime=None
        )

    def test_get_annual_interest_rate_with_effective_datetime(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "fixed_interest_rate": Decimal(("0.0120")),
            }
        )
        self.assertEqual(
            fixed.get_annual_interest_rate(
                vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
            ),
            Decimal("0.0120"),
        )
        mock_get_parameter.assert_called_once_with(
            sentinel.vault, "fixed_interest_rate", at_datetime=sentinel.effective_datetime
        )


@patch.object(fixed.utils, "yearly_to_monthly_rate")
@patch.object(fixed, "get_annual_interest_rate")
class MonthlyInterestRateTest(FixedTest):
    def test_get_monthly_interest_rate(
        self, mock_get_annual_interest_rate: MagicMock, mock_yearly_to_monthly_rate: MagicMock
    ):
        mock_get_annual_interest_rate.return_value = sentinel.annual_rate
        fixed.get_monthly_interest_rate(vault=sentinel.vault)

        mock_get_annual_interest_rate.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=None
        )
        mock_yearly_to_monthly_rate.assert_called_once_with(
            mock_get_annual_interest_rate.return_value
        )

    def test_get_monthly_interest_rate_with_effective_datetime(
        self, mock_get_annual_interest_rate: MagicMock, mock_yearly_to_monthly_rate: MagicMock
    ):
        mock_get_annual_interest_rate.return_value = sentinel.annual_rate
        fixed.get_monthly_interest_rate(
            vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
        )

        mock_get_annual_interest_rate.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
        )
        mock_yearly_to_monthly_rate.assert_called_once_with(
            mock_get_annual_interest_rate.return_value
        )


@patch.object(fixed.utils, "yearly_to_daily_rate")
@patch.object(fixed.utils, "get_parameter")
@patch.object(fixed, "get_annual_interest_rate")
class DailyInterestRateTest(FixedTest):
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
        fixed.get_daily_interest_rate(vault=sentinel.vault, effective_datetime=sentinel.datetime)

        mock_get_annual_interest_rate.assert_called_once_with(vault=sentinel.vault)
        mock_yearly_to_daily_rate.assert_called_once_with(
            sentinel.datetime, sentinel.annual_rate, sentinel.days_in_year
        )


class ReamortisationInterfaceTest(FixedTest):
    def test_interface_returns_false(self):
        self.assertFalse(
            fixed.FixedReamortisationCondition.should_trigger_reamortisation("a", "b", "c", "d")
        )
