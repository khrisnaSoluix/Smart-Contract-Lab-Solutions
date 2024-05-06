# standard libs
from unittest.mock import MagicMock, patch, sentinel

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.lending import term_helpers
from library.features.v4.lending.interest_rate import fixed, fixed_to_variable, variable

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)


class FixedToVariableTest(FeatureTest):
    maxDiff = None


@patch.object(fixed_to_variable.utils, "get_parameter")
@patch.object(term_helpers, "calculate_elapsed_term")
class IsWithinFixedRateTermTest(FixedToVariableTest):

    mock_params = mock_utils_get_parameter(
        parameters={fixed_to_variable.PARAM_FIXED_INTEREST_TERM: 4}
    )

    def test_within_fixed_rate_term_if_elapsed_lt_fixed_term(
        self, mock_elapsed_term: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_elapsed_term.return_value = 3
        mock_get_parameter.side_effect = IsWithinFixedRateTermTest.mock_params

        self.assertTrue(
            fixed_to_variable.is_within_fixed_rate_term(
                vault=self.create_mock(),
                effective_datetime=sentinel.effective_datetime,
                balances=sentinel.balances,
                denomination=sentinel.denomination,
            )
        )

        mock_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )

    def test_is_not_within_fixed_rate_term_if_elapsed_gt_fixed_term(
        self, mock_elapsed_term: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_elapsed_term.return_value = 6
        mock_get_parameter.side_effect = IsWithinFixedRateTermTest.mock_params

        self.assertFalse(
            fixed_to_variable.is_within_fixed_rate_term(
                vault=self.create_mock(),
                effective_datetime=sentinel.effective_datetime,
                balances=sentinel.balances,
                denomination=sentinel.denomination,
            )
        )

        mock_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )

    def test_not_within_fixed_rate_term_if_elapsed_eq_fixed_term(
        self, mock_elapsed_term: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_elapsed_term.return_value = 4
        mock_get_parameter.side_effect = IsWithinFixedRateTermTest.mock_params

        self.assertFalse(
            fixed_to_variable.is_within_fixed_rate_term(
                vault=self.create_mock(),
                effective_datetime=sentinel.effective_datetime,
                balances=sentinel.balances,
                denomination=sentinel.denomination,
            )
        )

        mock_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )

    def test_not_within_fixed_rate_term_if_0_fixed_term(
        self, mock_elapsed_term: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={fixed_to_variable.PARAM_FIXED_INTEREST_TERM: 0}
        )

        self.assertFalse(
            fixed_to_variable.is_within_fixed_rate_term(
                vault=sentinel.vault,
                effective_datetime=sentinel.effective_datetime,
                balances=sentinel.balances,
                denomination=sentinel.denomination,
            )
        )
        mock_elapsed_term.assert_not_called()

    def test_within_fixed_rate_term_without_optional_args(
        self, mock_elapsed_term: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_elapsed_term.return_value = 6
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                fixed_to_variable.PARAM_FIXED_INTEREST_TERM: 4,
                "denomination": sentinel.denomination,
            }
        )
        balance_observation_mapping = {
            fixed_to_variable.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                SentinelBalancesObservation("fetched")
            )
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=balance_observation_mapping  # type: ignore
        )

        self.assertFalse(
            fixed_to_variable.is_within_fixed_rate_term(
                vault=mock_vault,
                effective_datetime=sentinel.effective_datetime,
            )
        )

        mock_elapsed_term.assert_called_once_with(
            balances=sentinel.balances_fetched, denomination=sentinel.denomination
        )

    def test_within_fixed_rate_at_activation_if_non_0_fixed_term(
        self, mock_elapsed_term: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = IsWithinFixedRateTermTest.mock_params
        mock_vault = self.create_mock()

        self.assertTrue(
            fixed_to_variable.is_within_fixed_rate_term(
                vault=mock_vault,
                effective_datetime=mock_vault.get_account_creation_datetime(),
            )
        )

        mock_elapsed_term.assert_not_called()


@patch.object(fixed_to_variable, "is_within_fixed_rate_term")
@patch.object(variable, "get_annual_interest_rate")
@patch.object(fixed, "get_annual_interest_rate")
class AnnualInterestRateTest(FixedToVariableTest):
    def test_get_annual_interest_rate_during_fixed_term(
        self,
        mock_fixed_rate: MagicMock,
        mock_variable_rate: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
    ):

        mock_is_within_fixed_rate_term.return_value = True
        mock_fixed_rate.return_value = sentinel.fixed_rate

        self.assertEqual(
            fixed_to_variable.get_annual_interest_rate(
                vault=sentinel.vault,
                effective_datetime=sentinel.effective_datetime,
                balances=sentinel.balances,
                denomination=sentinel.denomination,
            ),
            sentinel.fixed_rate,
        )

        mock_is_within_fixed_rate_term.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        mock_fixed_rate.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
        )
        mock_variable_rate.assert_not_called()

    def test_get_annual_interest_rate_during_variable_term(
        self,
        mock_fixed_rate: MagicMock,
        mock_variable_rate: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
    ):

        mock_is_within_fixed_rate_term.return_value = False
        mock_variable_rate.return_value = sentinel.variable_rate

        self.assertEqual(
            fixed_to_variable.get_annual_interest_rate(
                vault=sentinel.vault,
                effective_datetime=sentinel.effective_datetime,
                balances=sentinel.balances,
                denomination=sentinel.denomination,
            ),
            sentinel.variable_rate,
        )

        mock_is_within_fixed_rate_term.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        mock_variable_rate.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
        )
        mock_fixed_rate.assert_not_called()

    def test_get_annual_interest_rate_without_optional_args(
        self,
        mock_fixed_rate: MagicMock,
        mock_variable_rate: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
    ):
        fixed_to_variable.get_annual_interest_rate(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
        )

        mock_is_within_fixed_rate_term.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            balances=None,
            denomination=None,
        )


@patch.object(fixed_to_variable, "is_within_fixed_rate_term")
@patch.object(variable, "get_monthly_interest_rate")
@patch.object(fixed, "get_monthly_interest_rate")
class MonthlyInterestRateTest(FixedToVariableTest):
    def test_get_monthly_interest_rate_during_fixed_term(
        self,
        mock_fixed_rate: MagicMock,
        mock_variable_rate: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
    ):

        mock_is_within_fixed_rate_term.return_value = True
        mock_fixed_rate.return_value = sentinel.fixed_rate

        self.assertEqual(
            fixed_to_variable.get_monthly_interest_rate(
                vault=sentinel.vault,
                effective_datetime=sentinel.effective_datetime,
                balances=sentinel.balances,
                denomination=sentinel.denomination,
            ),
            sentinel.fixed_rate,
        )

        mock_fixed_rate.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
        )
        mock_variable_rate.assert_not_called()

    def test_get_monthly_interest_rate_during_variable_term(
        self,
        mock_fixed_rate: MagicMock,
        mock_variable_rate: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
    ):

        mock_is_within_fixed_rate_term.return_value = False
        mock_variable_rate.return_value = sentinel.variable_rate

        self.assertEqual(
            fixed_to_variable.get_monthly_interest_rate(
                vault=sentinel.vault,
                effective_datetime=sentinel.effective_datetime,
                balances=sentinel.balances,
                denomination=sentinel.denomination,
            ),
            sentinel.variable_rate,
        )

        mock_is_within_fixed_rate_term.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        mock_variable_rate.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
        )
        mock_fixed_rate.assert_not_called()

    def test_get_monthly_interest_rate_without_optional_args(
        self,
        mock_fixed_rate: MagicMock,
        mock_variable_rate: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
    ):

        fixed_to_variable.get_monthly_interest_rate(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
        )

        mock_is_within_fixed_rate_term.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            balances=None,
            denomination=None,
        )


@patch.object(fixed_to_variable, "is_within_fixed_rate_term")
@patch.object(variable, "get_daily_interest_rate")
@patch.object(fixed, "get_daily_interest_rate")
class DailyInterestRateTest(FixedToVariableTest):
    def test_get_daily_interest_rate_during_fixed_term(
        self,
        mock_fixed_rate: MagicMock,
        mock_variable_rate: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
    ):

        mock_is_within_fixed_rate_term.return_value = True
        mock_fixed_rate.return_value = sentinel.fixed_rate

        self.assertEqual(
            fixed_to_variable.get_daily_interest_rate(
                vault=sentinel.vault,
                effective_datetime=sentinel.effective_datetime,
                balances=sentinel.balances,
                denomination=sentinel.denomination,
            ),
            sentinel.fixed_rate,
        )

        mock_is_within_fixed_rate_term.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        mock_fixed_rate.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
        )
        mock_variable_rate.assert_not_called()

    def test_get_daily_interest_rate_during_variable_term(
        self,
        mock_fixed_rate: MagicMock,
        mock_variable_rate: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
    ):

        mock_is_within_fixed_rate_term.return_value = False
        mock_variable_rate.return_value = sentinel.variable_rate

        self.assertEqual(
            fixed_to_variable.get_daily_interest_rate(
                vault=sentinel.vault,
                effective_datetime=sentinel.effective_datetime,
                balances=sentinel.balances,
                denomination=sentinel.denomination,
            ),
            sentinel.variable_rate,
        )

        mock_is_within_fixed_rate_term.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        mock_variable_rate.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
        )
        mock_fixed_rate.assert_not_called()

    def test_get_daily_interest_rate_without_optional_args(
        self,
        mock_fixed_rate: MagicMock,
        mock_variable_rate: MagicMock,
        mock_is_within_fixed_rate_term: MagicMock,
    ):
        fixed_to_variable.get_daily_interest_rate(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
        )
        mock_is_within_fixed_rate_term.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            balances=None,
            denomination=None,
        )


@patch.object(
    fixed_to_variable.utils,
    "get_parameter",
    MagicMock(side_effect=mock_utils_get_parameter({"fixed_interest_term": 2})),
)
@patch.object(variable, "should_trigger_reamortisation")
@patch.object(variable, "get_annual_interest_rate")
@patch.object(fixed, "get_annual_interest_rate")
@patch.object(fixed_to_variable, "is_within_fixed_rate_term")
class ReamortisationConditionTest(FixedToVariableTest):
    def test_should_not_reamortise_during_fixed_interest_term(
        self,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_fixed_annual_interest_rate: MagicMock,
        mock_variable_interest_rate: MagicMock,
        mock_variable_reamortisation_condition: MagicMock,
    ):
        mock_is_within_fixed_rate_term.return_value = True

        self.assertFalse(
            fixed_to_variable.should_trigger_reamortisation(
                vault=sentinel.vault,
                period_start_datetime=sentinel.period_start,
                period_end_datetime=sentinel.period_end,
                elapsed_term=sentinel.elapsed_term,
            )
        )
        mock_fixed_annual_interest_rate.assert_not_called()
        mock_variable_interest_rate.assert_not_called()
        mock_variable_reamortisation_condition.assert_not_called()

    def test_should_not_reamortise_on_fixed_to_variable_transition_if_rates_equal(
        self,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_fixed_annual_interest_rate: MagicMock,
        mock_variable_interest_rate: MagicMock,
        mock_variable_reamortisation_condition: MagicMock,
    ):
        # elapsed == fixed interest, so this is fixed -> variable transition
        elapsed_term = 2
        mock_is_within_fixed_rate_term.return_value = False
        mock_variable_interest_rate.return_value = sentinel.rate
        mock_fixed_annual_interest_rate.return_value = sentinel.rate

        self.assertFalse(
            fixed_to_variable.should_trigger_reamortisation(
                vault=sentinel.vault,
                period_start_datetime=sentinel.period_start,
                period_end_datetime=sentinel.period_end,
                elapsed_term=elapsed_term,
            )
        )
        mock_variable_reamortisation_condition.assert_not_called()

    def test_should_reamortise_on_fixed_to_variable_transition_if_rates_not_equal(
        self,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_fixed_annual_interest_rate: MagicMock,
        mock_variable_interest_rate: MagicMock,
        mock_variable_reamortisation_condition: MagicMock,
    ):
        # elapsed == fixed interest, so this is fixed -> variable transition
        elapsed_term = 2
        mock_is_within_fixed_rate_term.return_value = False
        mock_variable_interest_rate.return_value = sentinel.rate_1
        mock_fixed_annual_interest_rate.return_value = sentinel.rate_2

        self.assertTrue(
            fixed_to_variable.should_trigger_reamortisation(
                vault=sentinel.vault,
                period_start_datetime=sentinel.period_start,
                period_end_datetime=sentinel.period_end,
                elapsed_term=elapsed_term,
            )
        )
        mock_variable_reamortisation_condition.assert_not_called()

    def test_should_reamortise_during_variable_term_if_required(
        self,
        mock_is_within_fixed_rate_term: MagicMock,
        mock_fixed_annual_interest_rate: MagicMock,
        mock_variable_interest_rate: MagicMock,
        mock_variable_reamortisation_condition: MagicMock,
    ):
        # elapsed > fixed interest, so we're in the variable rate part of the loan
        elapsed_term = 3
        mock_is_within_fixed_rate_term.return_value = False
        mock_variable_reamortisation_condition.return_value = True

        self.assertTrue(
            fixed_to_variable.should_trigger_reamortisation(
                vault=sentinel.vault,
                period_start_datetime=sentinel.period_start,
                period_end_datetime=sentinel.period_end,
                elapsed_term=elapsed_term,
            )
        )
