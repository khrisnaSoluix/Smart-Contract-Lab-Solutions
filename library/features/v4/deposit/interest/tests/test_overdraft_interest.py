# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.interest import overdraft_interest

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
    Phase,
    Posting,
    Tside,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)

DECIMAL_ZERO = Decimal("0")


class TestOverdraftInterest(FeatureTest):
    tside = Tside.LIABILITY
    maxDiff = None


class TestRetrieveEODObservations(TestOverdraftInterest):
    def test_retrieve_eod_balances(self):
        current_eod_observation = SentinelBalancesObservation("current_eod_observation")
        previous_day1_observation = SentinelBalancesObservation("previous_day1_observation")
        previous_day2_observation = SentinelBalancesObservation("previous_day2_observation")
        previous_day3_observation = SentinelBalancesObservation("previous_day3_observation")
        previous_day4_observation = SentinelBalancesObservation("previous_day4_observation")
        previous_day5_observation = SentinelBalancesObservation("previous_day5_observation")

        test_balance_observation_fetcher_mapping = {
            overdraft_interest.fetchers.EOD_FETCHER_ID: current_eod_observation,
            overdraft_interest.fetchers.PREVIOUS_EOD_1_FETCHER_ID: previous_day1_observation,
            overdraft_interest.fetchers.PREVIOUS_EOD_2_FETCHER_ID: previous_day2_observation,
            overdraft_interest.fetchers.PREVIOUS_EOD_3_FETCHER_ID: previous_day3_observation,
            overdraft_interest.fetchers.PREVIOUS_EOD_4_FETCHER_ID: previous_day4_observation,
            overdraft_interest.fetchers.PREVIOUS_EOD_5_FETCHER_ID: previous_day5_observation,
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )
        result = overdraft_interest._retrieve_eod_observations(
            vault=mock_vault,
        )
        self.assertEqual(
            result,
            [
                current_eod_observation,
                previous_day1_observation,
                previous_day2_observation,
                previous_day3_observation,
                previous_day4_observation,
                previous_day5_observation,
            ],
        )


@patch.object(overdraft_interest.utils, "balance_at_coordinates")
class TestCalculateAccrualBalance(TestOverdraftInterest):
    # Buffer amount = 10 Buffer period = 3 EOD Balance > 0 Previous days all have negative balance
    def test_calculate_accrual_balance_positive_balance_at_eod_returns_0(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.return_value = 50
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("10"),
            interest_free_days=int("3"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("dummy"),
            ],
        )
        self.assertEqual(result, Decimal("0"))
        mock_balance_at_coordinates.assert_called_once_with(
            balances=SentinelBalancesObservation("current_eod_observation").balances,
            denomination=sentinel.denomination,
        )

    # Buffer amount = 10 Buffer period = 3 EOD Balance = 0 Previous days all have negative balance
    def test_calculate_accrual_balance_balance_at_eod_is_0_returns_0(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.return_value = 0
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("10"),
            interest_free_days=int("3"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("dummy"),
            ],
        )
        self.assertEqual(result, Decimal("0"))

    # Buffer amount = 10 Buffer period = 3 EOD Balance = -9.99 Previous Day 1 balance is positive
    def test_calculate_accrual_balance_eod_negative_previous_day1_positive_returns_0_buffer_applies(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-9.99"),
            Decimal("0"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("10"),
            interest_free_days=int("3"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("0"))
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=SentinelBalancesObservation("current_eod_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day1_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day2_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day3_observation").balances,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    # Buffer amount = 10 Buffer period = 3 EOD Balance = -10.01 Previous Day 1 balance is positive
    def test_calculate_accrual_balance_eod_negative_buffer_are_applied_reducing_overdraft(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-10.01"),
            Decimal("0"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("10"),
            interest_free_days=int("3"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("-0.01"))
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=SentinelBalancesObservation("current_eod_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day1_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day2_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day3_observation").balances,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    # Buffer amount = 10 Buffer period = 3 EOD Balance = -9.99 Previous Day 2 is positive
    def test_calculate_accrual_balance_eod_negative_previous_day2_positive_returns_0_buffer_applies(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("0"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("10"),
            interest_free_days=int("3"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("0"))
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=SentinelBalancesObservation("current_eod_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day1_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day2_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day3_observation").balances,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    # Buffer amount = 10 Buffer period = 3 EOD Balance = -9.99 Previous Day 3 is positive
    def test_calculate_accrual_balance_eod_negative_previous_day3_positive_returns_0_buffer_applies(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("0"),
            Decimal("-9.99"),
            Decimal("-9.99"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("10"),
            interest_free_days=int("3"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("0"))
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=SentinelBalancesObservation("current_eod_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day1_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day2_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day3_observation").balances,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    # Buffer amount = 10 Buffer period = 3 EOD Balance = -9.99 Previous Day 4 is positive
    def test_calculate_accrual_balance_eod_negative_previous_day4_positive_buffer_doesnt_apply(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("0"),
            Decimal("-9.99"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("10"),
            interest_free_days=int("3"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("-9.99"))
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=SentinelBalancesObservation("current_eod_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day1_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day2_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day3_observation").balances,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    # Buffer Period Edge cases - Minimum Period - 1 day buffer
    # Buffer amount = 10 Buffer period = 1 EOD Balance = -9.99 Previous Day 1 is positive
    def test_calculate_accrual_balance_edge_case_minimum_period_previous_day_pos_buffer_applies(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-9.99"),
            Decimal("0"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.91"),
            Decimal("-9.99"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("10"),
            interest_free_days=int("1"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("0"))
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=SentinelBalancesObservation("current_eod_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day1_observation").balances,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    # Buffer amount = 10 Buffer period = 1 EOD Balance = -9.99 Previous Day 1 is negative
    def test_calculate_accrual_balance_edge_case_minimum_period_previous_day1_negative_doesnt_apply(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-9.99"),
            Decimal("-0.50"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("10"),
            interest_free_days=int("1"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("-9.99"))
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=SentinelBalancesObservation("current_eod_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day1_observation").balances,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    # Buffer Period Edge cases - Maximum Period - 5 day buffer
    # Buffer amount = 10 Buffer period = 1 EOD Balance = -9.99 Previous Days are positive
    def test_calculate_accrual_balance_edge_case_maximum_period_prev_days_positive_buffer_applies(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("0"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("10"),
            interest_free_days=int("5"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("0"))
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=SentinelBalancesObservation("current_eod_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day1_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day2_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day3_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day4_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day5_observation").balances,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    # Buffer amount = 10 Buffer period = 5 EOD Balance = -9.99 Previous Days are negative
    def test_calculate_accrual_balance_edge_case_maximum_period_prev_days_neg_buffer_not_applied(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
            Decimal("-9.99"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("10"),
            interest_free_days=int("5"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("-9.99"))
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=SentinelBalancesObservation("current_eod_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day1_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day2_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day3_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day4_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day5_observation").balances,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    # Buffer amount = 0 Buffer period = 3 EOD Balance = -999.99 Previous Day 2 is positive
    def test_calculate_accrual_balance_eod_negative_only_period_is_set_buffer_applies(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-999.99"),
            Decimal("-999.99"),
            Decimal("0"),
            Decimal("-999.99"),
            Decimal("-999.99"),
            Decimal("-999.99"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("0"),
            interest_free_days=int("3"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("0"))
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=SentinelBalancesObservation("current_eod_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day1_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day2_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day3_observation").balances,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    # Buffer amount = 0 Buffer period = 3 EOD Balance = -999.99 Previous Day 4 is positive
    def test_calculate_accrual_balance_eod_negative_only_period_is_set_buffer_doesnt_apply(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-999.99"),
            Decimal("-999.99"),
            Decimal("-999.99"),
            Decimal("-999.99"),
            Decimal("0"),
            Decimal("-999.99"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("0"),
            interest_free_days=int("3"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("-999.99"))
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=SentinelBalancesObservation("current_eod_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day1_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day2_observation").balances,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=SentinelBalancesObservation("previous_day3_observation").balances,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    # Buffer amount = 50 Buffer period = 0 EOD Balance = -100 Previous Days positive
    def test_calculate_accrual_balance_eod_negative_only_amount_is_set_prev_days_positive(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-100"),
            Decimal("100"),
            Decimal("100"),
            Decimal("100"),
            Decimal("100"),
            Decimal("100"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("50"),
            interest_free_days=int("0"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("-50"))
        mock_balance_at_coordinates.assert_called_once_with(
            balances=SentinelBalancesObservation("current_eod_observation").balances,
            denomination=sentinel.denomination,
        )

    # Buffer amount = 50 Buffer period = 0 EOD Balance = -100 Previous Days negative
    def test_calculate_accrual_balance_eod_negative_only_amount_is_set_prev_days_negative(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-100"),
            Decimal("-100"),
            Decimal("-100"),
            Decimal("-100"),
            Decimal("-100"),
            Decimal("-100"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("50"),
            interest_free_days=int("0"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("-50"))
        mock_balance_at_coordinates.assert_called_once_with(
            balances=SentinelBalancesObservation("current_eod_observation").balances,
            denomination=sentinel.denomination,
        )

    # Buffer amount = 50 Buffer period = 0 EOD Balance = -25 Previous Days negative
    def test_calculate_accrual_balance_eod_negative_only_amount_is_set_buffer_covers_overdraft(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-25"),
            Decimal("-100"),
            Decimal("-100"),
            Decimal("-100"),
            Decimal("-100"),
            Decimal("-100"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("50"),
            interest_free_days=int("0"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("0"))
        mock_balance_at_coordinates.assert_called_once_with(
            balances=SentinelBalancesObservation("current_eod_observation").balances,
            denomination=sentinel.denomination,
        )

    # Buffer amount = 0 Buffer period = 0 EOD Balance = -0.01 Previous Days positive
    def test_calculate_accrual_balance_eod_negative_both_parameters_are_zero(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.side_effect = [
            Decimal("-0.01"),
            Decimal("1"),
            Decimal("1"),
            Decimal("1"),
            Decimal("1"),
            Decimal("1"),
        ]
        result = overdraft_interest._calculate_accrual_balance(
            interest_free_amount=Decimal("0"),
            interest_free_days=int("0"),
            denomination=sentinel.denomination,
            observations=[
                SentinelBalancesObservation("current_eod_observation"),
                SentinelBalancesObservation("previous_day1_observation"),
                SentinelBalancesObservation("previous_day2_observation"),
                SentinelBalancesObservation("previous_day3_observation"),
                SentinelBalancesObservation("previous_day4_observation"),
                SentinelBalancesObservation("previous_day5_observation"),
            ],
        )
        self.assertEqual(result, Decimal("-0.01"))
        mock_balance_at_coordinates.assert_called_once_with(
            balances=SentinelBalancesObservation("current_eod_observation").balances,
            denomination=sentinel.denomination,
        )


@patch.object(overdraft_interest, "_calculate_accrual_balance")
@patch.object(overdraft_interest, "_retrieve_eod_observations")
@patch.object(overdraft_interest.utils, "get_parameter")
class TestAccrueInterest(TestOverdraftInterest):
    def test_accrue_interest_overdraft_interest_rate_and_internal_acc_not_set(
        self,
        mock_get_parameter: MagicMock,
        mock_retrieve_eod_observations: MagicMock,
        mock_calculate_accrual_balance: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "overdraft_interest_rate": DECIMAL_ZERO,
                "overdraft_interest_receivable_account": "",
            }
        )
        result = overdraft_interest.accrue_interest(
            vault=sentinel,
            effective_datetime=sentinel.effective_datetime,
        )
        self.assertListEqual(result, [])
        mock_retrieve_eod_observations.assert_not_called()
        mock_calculate_accrual_balance.assert_not_called()

    def test_accrue_interest_overdraft_interest_rate_not_set_internal_acc_set(
        self,
        mock_get_parameter: MagicMock,
        mock_retrieve_eod_observations: MagicMock,
        mock_calculate_accrual_balance: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "overdraft_interest_rate": DECIMAL_ZERO,
                "overdraft_interest_receivable_account": "INTERNAL_ACCOUNT",
            }
        )
        result = overdraft_interest.accrue_interest(
            vault=sentinel,
            effective_datetime=sentinel.effective_datetime,
        )
        self.assertListEqual(result, [])
        mock_retrieve_eod_observations.assert_not_called()
        mock_calculate_accrual_balance.assert_not_called()

    def test_accrue_interest_overdraft_interest_rate_set_internal_acc_not_set(
        self,
        mock_get_parameter: MagicMock,
        mock_retrieve_eod_observations: MagicMock,
        mock_calculate_accrual_balance: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "overdraft_interest_rate": Decimal("0.05"),
                "overdraft_interest_receivable_account": "",
            }
        )
        result = overdraft_interest.accrue_interest(
            vault=sentinel,
            effective_datetime=sentinel.effective_datetime,
        )
        self.assertListEqual(result, [])
        mock_retrieve_eod_observations.assert_not_called()
        mock_calculate_accrual_balance.assert_not_called()

    def test_accrue_interest_overdraft_parameters_set_and_balance_is_zero(
        self,
        mock_get_parameter: MagicMock,
        mock_retrieve_eod_observations: MagicMock,
        mock_calculate_accrual_balance: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
                "overdraft_interest_rate": Decimal("0.05"),
                "overdraft_interest_receivable_account": "INTERNAL_ACCOUNT",
                "interest_free_buffer_amount": Decimal("10"),
                "interest_free_buffer_days": int("3"),
                "days_in_year": "365",
                "accrual_precision": Decimal("5"),
            }
        )
        mock_retrieve_eod_observations.return_value = sentinel.observations
        mock_calculate_accrual_balance.return_value = DECIMAL_ZERO
        result = overdraft_interest.accrue_interest(
            vault=sentinel,
            effective_datetime=sentinel.effective_datetime,
        )
        self.assertListEqual(result, [])

    def test_accrue_interest_overdraft_parameters_set_and_balance_not_zero(
        self,
        mock_get_parameter: MagicMock,
        mock_retrieve_eod_observations: MagicMock,
        mock_calculate_accrual_balance: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
                "overdraft_interest_rate": Decimal("0.05"),
                "overdraft_interest_receivable_account": "INTERNAL_ACCOUNT",
                "interest_free_buffer_amount": Decimal("10"),
                "interest_free_buffer_days": int("3"),
                "days_in_year": "365",
                "accrual_precision": Decimal("5"),
            }
        )
        mock_calculate_accrual_balance.return_value = Decimal("-500")
        mock_retrieve_eod_observations.return_value = sentinel.eod_observations
        mock_vault = self.create_mock(account_id=sentinel.account_id)
        expected_postings = [
            Posting(
                credit=True,
                amount=Decimal("0.06849"),
                denomination=sentinel.denomination,
                account_id="INTERNAL_ACCOUNT",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
            Posting(
                credit=False,
                amount=Decimal("0.06849"),
                denomination=sentinel.denomination,
                account_id=sentinel.account_id,
                account_address="OVERDRAFT_ACCRUED_INTEREST",
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        result = overdraft_interest.accrue_interest(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
        )
        mock_calculate_accrual_balance.assert_called_once_with(
            interest_free_amount=Decimal("10"),
            interest_free_days=int("3"),
            denomination=sentinel.denomination,
            observations=sentinel.eod_observations,
        )
        mock_retrieve_eod_observations.assert_called_once_with(vault=mock_vault)
        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=expected_postings,
                    instruction_details={
                        "description": "Accrual on overdraft balance of -500.00 "
                        f"{sentinel.denomination} at 5.00%",
                        "event": "ACCRUE_OVERDRAFT_DAILY_FEE",
                        "gl_impacted": "True",
                        "account_type": "",
                    },
                    override_all_restrictions=True,
                )
            ],
        )


@patch.object(overdraft_interest.accruals, "accrual_application_custom_instruction")
@patch.object(overdraft_interest.utils, "standard_instruction_details")
@patch.object(overdraft_interest.utils, "round_decimal")
@patch.object(overdraft_interest.utils, "balance_at_coordinates")
@patch.object(overdraft_interest.utils, "get_parameter")
class TestApplyInterest(TestOverdraftInterest):
    def test_apply_interest_accrued_balance_is_zero(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_round_decimal: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_accrual_application_custom_instruction: MagicMock,
    ):
        effective_balance_observation = SentinelBalancesObservation("effective_balance_observation")

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("0")
        test_balance_observation_fetcher_mapping = {
            overdraft_interest.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: effective_balance_observation,  # noqa: E501
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )
        result = overdraft_interest.apply_interest(
            vault=mock_vault,
        )
        self.assertEqual(result, [])
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name="denomination", at_datetime=None
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=effective_balance_observation.balances,
            address="OVERDRAFT_ACCRUED_INTEREST",
            denomination=sentinel.denomination,
        )
        mock_accrual_application_custom_instruction.assert_not_called()
        mock_round_decimal.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    def test_apply_interest_accrued_balance_is_not_zero_but_optional_param_receivable_acc_not_set(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_round_decimal: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_accrual_application_custom_instruction: MagicMock,
    ):
        effective_balance_observation = SentinelBalancesObservation("effective_balance_observation")

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
                "overdraft_interest_receivable_account": "",
                "overdraft_interest_received_account": sentinel.received_account,
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("10")
        test_balance_observation_fetcher_mapping = {
            overdraft_interest.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: effective_balance_observation,  # noqa: E501
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )
        result = overdraft_interest.apply_interest(
            vault=mock_vault,
        )
        self.assertEqual(result, [])
        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="denomination", at_datetime=None),
                call(
                    vault=mock_vault,
                    name="overdraft_interest_receivable_account",
                    is_optional=True,
                    default_value="",
                ),
                call(
                    vault=mock_vault,
                    name="overdraft_interest_received_account",
                    is_optional=True,
                    default_value="",
                ),
            ],
        )
        mock_accrual_application_custom_instruction.assert_not_called()
        mock_round_decimal.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    def test_apply_interest_accrued_balance_is_not_zero_but_optional_param_received_acc_not_set(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_round_decimal: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_accrual_application_custom_instruction: MagicMock,
    ):
        effective_balance_observation = SentinelBalancesObservation("effective_balance_observation")

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
                "overdraft_interest_receivable_account": sentinel.receivable_account,
                "overdraft_interest_received_account": "",
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("10")
        test_balance_observation_fetcher_mapping = {
            overdraft_interest.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: effective_balance_observation,  # noqa: E501
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )
        result = overdraft_interest.apply_interest(
            vault=mock_vault,
        )
        self.assertEqual(result, [])
        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="denomination", at_datetime=None),
                call(
                    vault=mock_vault,
                    name="overdraft_interest_receivable_account",
                    is_optional=True,
                    default_value="",
                ),
                call(
                    vault=mock_vault,
                    name="overdraft_interest_received_account",
                    is_optional=True,
                    default_value="",
                ),
            ],
        )
        mock_accrual_application_custom_instruction.assert_not_called()
        mock_round_decimal.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    def test_apply_interest_accrued_balance_is_not_zero_but_optional_params_not_set(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_round_decimal: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_accrual_application_custom_instruction: MagicMock,
    ):
        effective_balance_observation = SentinelBalancesObservation("effective_balance_observation")

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
                "overdraft_interest_receivable_account": "",
                "overdraft_interest_received_account": "",
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("10")
        test_balance_observation_fetcher_mapping = {
            overdraft_interest.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: effective_balance_observation,  # noqa: E501
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )
        result = overdraft_interest.apply_interest(
            vault=mock_vault,
        )
        self.assertEqual(result, [])
        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="denomination", at_datetime=None),
                call(
                    vault=mock_vault,
                    name="overdraft_interest_receivable_account",
                    is_optional=True,
                    default_value="",
                ),
                call(
                    vault=mock_vault,
                    name="overdraft_interest_received_account",
                    is_optional=True,
                    default_value="",
                ),
            ],
        )
        mock_accrual_application_custom_instruction.assert_not_called()
        mock_round_decimal.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    def test_apply_interest_accrued_balance_is_not_zero_optional_params_set(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_round_decimal: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_accrual_application_custom_instruction: MagicMock,
    ):
        effective_balance_observation = SentinelBalancesObservation("effective_balance_observation")
        custom_posting_instructions = [SentinelCustomInstruction("overdraft_interest_charge")]

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
                "overdraft_interest_receivable_account": sentinel.receivable_account,
                "overdraft_interest_received_account": sentinel.received_account,
                "application_precision": int("2"),
            }
        )
        mock_round_decimal.return_value = Decimal("45.15")
        mock_balance_at_coordinates.return_value = Decimal("45.14591")
        mock_standard_instruction_details.return_value = sentinel.instruction_details
        mock_accrual_application_custom_instruction.return_value = custom_posting_instructions
        test_balance_observation_fetcher_mapping = {
            overdraft_interest.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: effective_balance_observation,  # noqa: E501
        }
        mock_vault = self.create_mock(
            account_id=sentinel.account_id,
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )
        result = overdraft_interest.apply_interest(
            vault=mock_vault,
            account_type=sentinel.account_type,
        )
        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="denomination", at_datetime=None),
                call(
                    vault=mock_vault,
                    name="overdraft_interest_receivable_account",
                    is_optional=True,
                    default_value="",
                ),
                call(
                    vault=mock_vault,
                    name="overdraft_interest_received_account",
                    is_optional=True,
                    default_value="",
                ),
                call(mock_vault, "application_precision"),
            ],
        )
        mock_round_decimal.assert_called_once_with(
            amount=Decimal("45.14591"),
            decimal_places=int("2"),
        )
        mock_standard_instruction_details.assert_called_once_with(
            description=f"Apply 45.15 {sentinel.denomination} overdraft interest"
            f" of 45.14591 rounded to 2 DP to "
            f"{sentinel.account_id}.",
            event_type="APPLY_OVERDRAFT_DAILY_FEE",
            gl_impacted=True,
            account_type=sentinel.account_type,
        )
        mock_accrual_application_custom_instruction.assert_called_once_with(
            customer_account=sentinel.account_id,
            denomination=sentinel.denomination,
            accrual_amount=Decimal("45.14591"),
            accrual_customer_address="OVERDRAFT_ACCRUED_INTEREST",
            accrual_internal_account=sentinel.receivable_account,
            application_amount=Decimal("45.15"),
            application_customer_address=DEFAULT_ADDRESS,
            application_internal_account=sentinel.received_account,
            payable=False,
            instruction_details=sentinel.instruction_details,
        )

        self.assertListEqual(
            result,
            custom_posting_instructions,
        )


@patch.object(overdraft_interest.accruals, "accrual_custom_instruction")
@patch.object(overdraft_interest.utils, "standard_instruction_details")
@patch.object(overdraft_interest.utils, "balance_at_coordinates")
@patch.object(overdraft_interest.utils, "get_parameter")
class TestGetInterestReversalPostings(TestOverdraftInterest):
    def test_get_interest_reversal_when_internal_account_not_set(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_accrual_custom_instruction: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "overdraft_interest_receivable_account": "",
            }
        )
        result = overdraft_interest.get_interest_reversal_postings(
            vault=sentinel.vault,
            event_name=sentinel.event_name,
            account_type=sentinel.account_type,
        )
        self.assertListEqual(result, [])
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault,
            name="overdraft_interest_receivable_account",
            is_optional=True,
            default_value="",
        )
        mock_balance_at_coordinates.assert_not_called()
        mock_standard_instruction_details.assert_not_called()
        mock_accrual_custom_instruction.assert_not_called()

    def test_get_interest_reversal_when_internal_account_set_but_balance_is_zero(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_accrual_custom_instruction: MagicMock,
    ):
        effective_balance_observation = SentinelBalancesObservation("effective_balance_observation")

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "overdraft_interest_receivable_account": sentinel.receivable_account,
                "denomination": sentinel.denomination,
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("0")
        test_balance_observation_fetcher_mapping = {
            overdraft_interest.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                effective_balance_observation
            )
        }
        mock_vault = self.create_mock(
            account_id=sentinel.account_id,
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )
        result = overdraft_interest.get_interest_reversal_postings(
            vault=mock_vault,
            event_name=sentinel.event_name,
            account_type=sentinel.account_type,
        )
        self.assertListEqual(result, [])
        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name="overdraft_interest_receivable_account",
                    is_optional=True,
                    default_value="",
                ),
                call(vault=mock_vault, name="denomination", at_datetime=None),
            ]
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=effective_balance_observation.balances,
            address="OVERDRAFT_ACCRUED_INTEREST",
            denomination=sentinel.denomination,
        )
        mock_standard_instruction_details.assert_not_called()
        mock_accrual_custom_instruction.assert_not_called()

    def test_get_interest_reversal_when_internal_account_set_and_balance_is_not_zero(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_accrual_custom_instruction: MagicMock,
    ):
        effective_balance_observation = SentinelBalancesObservation("effective")
        custom_posting_instructions = [SentinelCustomInstruction("overdraft_interest_reversal")]

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "overdraft_interest_receivable_account": sentinel.receivable_account,
                "denomination": sentinel.denomination,
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("50")
        mock_standard_instruction_details.return_value = sentinel.instruction_details
        mock_accrual_custom_instruction.return_value = custom_posting_instructions
        test_balance_observation_fetcher_mapping = {
            overdraft_interest.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                effective_balance_observation
            )
        }
        mock_vault = self.create_mock(
            account_id=sentinel.account_id,
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )

        result = overdraft_interest.get_interest_reversal_postings(
            vault=mock_vault,
            event_name=sentinel.event_name,
            account_type=sentinel.account_type,
        )

        self.assertListEqual(
            result,
            custom_posting_instructions,
        )
        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name="overdraft_interest_receivable_account",
                    is_optional=True,
                    default_value="",
                ),
                call(vault=mock_vault, name="denomination", at_datetime=None),
            ]
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=effective_balance_observation.balances,
            address="OVERDRAFT_ACCRUED_INTEREST",
            denomination=sentinel.denomination,
        )
        mock_standard_instruction_details.assert_called_once_with(
            description=f"Reversing 50 {sentinel.denomination} " "of accrued overdraft interest.",
            event_type=sentinel.event_name,
            gl_impacted=True,
            account_type=sentinel.account_type,
        )
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account=sentinel.account_id,
            customer_address="OVERDRAFT_ACCRUED_INTEREST",
            denomination=sentinel.denomination,
            amount=Decimal("50"),
            internal_account=sentinel.receivable_account,
            payable=False,
            instruction_details=sentinel.instruction_details,
            reversal=True,
        )

    def test_get_interest_reversal_when_internal_account_set_and_balance_is_not_zero_optional_args(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_accrual_custom_instruction: MagicMock,
    ):
        custom_posting_instructions = [SentinelCustomInstruction("overdraft_interest_reversal")]

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "overdraft_interest_receivable_account": sentinel.receivable_account,
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("50")
        mock_standard_instruction_details.return_value = sentinel.instruction_details
        mock_accrual_custom_instruction.return_value = custom_posting_instructions

        mock_vault = self.create_mock()

        result = overdraft_interest.get_interest_reversal_postings(
            vault=mock_vault,
            event_name=sentinel.event_name,
            account_type=sentinel.account_type,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertListEqual(
            result,
            custom_posting_instructions,
        )
        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name="overdraft_interest_receivable_account",
                    is_optional=True,
                    default_value="",
                ),
            ]
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address="OVERDRAFT_ACCRUED_INTEREST",
            denomination=sentinel.denomination,
        )
        mock_standard_instruction_details.assert_called_once_with(
            description=f"Reversing 50 {sentinel.denomination} " "of accrued overdraft interest.",
            event_type=sentinel.event_name,
            gl_impacted=True,
            account_type=sentinel.account_type,
        )
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account=mock_vault.account_id,
            customer_address="OVERDRAFT_ACCRUED_INTEREST",
            denomination=sentinel.denomination,
            amount=Decimal("50"),
            internal_account=sentinel.receivable_account,
            payable=False,
            instruction_details=sentinel.instruction_details,
            reversal=True,
        )

    def test_get_interest_reversal_parameters_set_and_balance_not_zero_account_type_not_informed(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_standard_instruction_details: MagicMock,
        mock_accrual_custom_instruction: MagicMock,
    ):
        effective_balance_observation = SentinelBalancesObservation("effective")
        custom_posting_instructions = [SentinelCustomInstruction("overdraft_interest_reversal")]

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "overdraft_interest_receivable_account": sentinel.receivable_account,
                "denomination": sentinel.denomination,
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("50")
        mock_standard_instruction_details.return_value = sentinel.instruction_details
        mock_accrual_custom_instruction.return_value = custom_posting_instructions
        test_balance_observation_fetcher_mapping = {
            overdraft_interest.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                effective_balance_observation
            )
        }
        mock_vault = self.create_mock(
            account_id=sentinel.account_id,
            balances_observation_fetchers_mapping=test_balance_observation_fetcher_mapping,
        )

        result = overdraft_interest.get_interest_reversal_postings(
            vault=mock_vault,
            event_name=sentinel.event_name,
        )

        self.assertListEqual(
            result,
            custom_posting_instructions,
        )
        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name="overdraft_interest_receivable_account",
                    is_optional=True,
                    default_value="",
                ),
                call(vault=mock_vault, name="denomination", at_datetime=None),
            ]
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=effective_balance_observation.balances,
            address="OVERDRAFT_ACCRUED_INTEREST",
            denomination=sentinel.denomination,
        )
        mock_standard_instruction_details.assert_called_once_with(
            description=f"Reversing 50 {sentinel.denomination} " "of accrued overdraft interest.",
            event_type=sentinel.event_name,
            gl_impacted=True,
            account_type="",
        )
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account=sentinel.account_id,
            customer_address="OVERDRAFT_ACCRUED_INTEREST",
            denomination=sentinel.denomination,
            amount=Decimal("50"),
            internal_account=sentinel.receivable_account,
            payable=False,
            instruction_details=sentinel.instruction_details,
            reversal=True,
        )
