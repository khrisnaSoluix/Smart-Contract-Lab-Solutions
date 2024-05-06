# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.deposit.cooling_off_period as cooling_off_period
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)


class DerivedParameterTest(FeatureTest):
    @patch.object(cooling_off_period.utils, "get_parameter")
    def test_derived_params_cooling_off_period_end_datetime(self, mock_get_parameter: MagicMock):
        mock_vault = self.create_mock(creation_date=DEFAULT_DATETIME)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "cooling_off_period": 5,
            }
        )
        expected_result = datetime(2019, 1, 6, 23, 59, 59, 999999, tzinfo=ZoneInfo("UTC"))
        result = cooling_off_period.get_cooling_off_period_end_datetime(vault=mock_vault)

        self.assertEqual(result, expected_result)


class ValidateCoolOffPeriodTest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(creation_date=DEFAULT_DATETIME)

        # get parameter
        patch_get_parameter = patch.object(cooling_off_period.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "cooling_off_period": 5,
            }
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_within_cooling_off_period_returns_true(self):
        effective_datetime = datetime(2019, 1, 6, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        result = cooling_off_period.is_within_cooling_off_period(
            vault=self.mock_vault, effective_datetime=effective_datetime
        )

        self.assertTrue(result)

    def test_at_cooling_off_period_end_time_returns_true(self):
        effective_datetime = datetime(2019, 1, 6, 23, 59, 59, 999999, tzinfo=ZoneInfo("UTC"))
        result = cooling_off_period.is_within_cooling_off_period(
            vault=self.mock_vault, effective_datetime=effective_datetime
        )

        self.assertTrue(result)

    def test_outside_cooling_off_period_returns_false(self):
        effective_datetime = datetime(2019, 1, 7, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        result = cooling_off_period.is_within_cooling_off_period(
            vault=self.mock_vault, effective_datetime=effective_datetime
        )

        self.assertFalse(result)


class WithdrawalSubjectToFeesTest(FeatureTest):
    def setUp(self) -> None:
        patch_is_within_cooling_off_period = patch.object(
            cooling_off_period, "is_within_cooling_off_period"
        )
        self.mock_is_within_cooling_off_period = patch_is_within_cooling_off_period.start()
        self.mock_is_within_cooling_off_period.return_value = True

        patch_posting_balances = patch.object(
            cooling_off_period.utils, "get_posting_instructions_balances"
        )
        self.mock_get_posting_instructions_balances = patch_posting_balances.start()
        self.mock_get_posting_instructions_balances.return_value = sentinel.posting_balances

        patch_posting_available_balance = patch.object(
            cooling_off_period.utils, "get_available_balance"
        )
        self.mock_get_available_balance = patch_posting_available_balance.start()

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_partial_withdrawal_within_cooling_off_period(self):
        self.mock_get_available_balance.side_effect = [
            Decimal("-1"),  # withdrawal amount
            Decimal("50"),  # current balance
        ]

        result = cooling_off_period.is_withdrawal_subject_to_fees(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            posting_instructions=sentinel.posting_instructions,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

        self.assertTrue(result)
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_available_balance.assert_has_calls(
            calls=[
                call(balances=sentinel.posting_balances, denomination=sentinel.denomination),
                call(balances=sentinel.balances, denomination=sentinel.denomination),
            ]
        )
        self.mock_is_within_cooling_off_period.assert_not_called()
        # self.mock_is_within_cooling_off_period.assert_called_once_with(
        #     vault=sentinel.vault, effective_datetime=sentinel.datetime
        # )

    def test_partial_withdrawal_outside_cooling_off_period(self):
        self.mock_get_available_balance.side_effect = [
            Decimal("-1"),  # withdrawal amount
            Decimal("50"),  # current balance
        ]
        self.mock_is_within_cooling_off_period.return_value = False

        result = cooling_off_period.is_withdrawal_subject_to_fees(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            posting_instructions=sentinel.posting_instructions,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

        self.assertTrue(result)
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_available_balance.assert_has_calls(
            calls=[
                call(balances=sentinel.posting_balances, denomination=sentinel.denomination),
                call(balances=sentinel.balances, denomination=sentinel.denomination),
            ]
        )
        self.mock_is_within_cooling_off_period.assert_not_called()

    def test_full_withdrawal_within_cooling_off_period(self):
        self.mock_get_available_balance.side_effect = [
            Decimal("-1"),  # withdrawal amount
            Decimal("0"),  # current balance
        ]

        result = cooling_off_period.is_withdrawal_subject_to_fees(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            posting_instructions=sentinel.posting_instructions,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

        self.assertFalse(result)
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_available_balance.assert_has_calls(
            calls=[
                call(balances=sentinel.posting_balances, denomination=sentinel.denomination),
                call(balances=sentinel.balances, denomination=sentinel.denomination),
            ]
        )
        self.mock_is_within_cooling_off_period.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )

    def test_full_withdrawal_outside_cooling_off_period(self):
        self.mock_get_available_balance.side_effect = [
            Decimal("-1"),  # withdrawal amount
            Decimal("0"),  # current balance
        ]
        self.mock_is_within_cooling_off_period.return_value = False

        result = cooling_off_period.is_withdrawal_subject_to_fees(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            posting_instructions=sentinel.posting_instructions,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

        self.assertTrue(result)
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_available_balance.assert_has_calls(
            calls=[
                call(balances=sentinel.posting_balances, denomination=sentinel.denomination),
                call(balances=sentinel.balances, denomination=sentinel.denomination),
            ]
        )
        self.mock_is_within_cooling_off_period.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )

    def test_deposits_are_not_subject_to_fees(self):
        self.mock_get_available_balance.return_value = Decimal("1")  # deposit amount

        result = cooling_off_period.is_withdrawal_subject_to_fees(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            posting_instructions=sentinel.posting_instructions,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

        self.assertFalse(result)
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_available_balance.assert_called_once_with(
            balances=sentinel.posting_balances, denomination=sentinel.denomination
        )
        self.mock_is_within_cooling_off_period.assert_not_called()

    @patch.object(cooling_off_period.common_parameters, "get_denomination_parameter")
    def test_full_withdrawal_within_cooling_off_period_no_optional_parameters(
        self, mock_get_denomination_parameter: MagicMock
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                cooling_off_period.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "live"
                )
            }
        )
        mock_get_denomination_parameter.return_value = sentinel.non_provided_denomination
        self.mock_get_available_balance.side_effect = [
            Decimal("-1"),  # withdrawal amount
            Decimal("0"),  # current balance
        ]

        result = cooling_off_period.is_withdrawal_subject_to_fees(
            vault=mock_vault,
            effective_datetime=sentinel.datetime,
            posting_instructions=sentinel.posting_instructions,
        )

        self.assertFalse(result)
        self.mock_get_posting_instructions_balances.assert_called_once_with(
            posting_instructions=sentinel.posting_instructions
        )
        self.mock_get_available_balance.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.posting_balances,
                    denomination=sentinel.non_provided_denomination,
                ),
                call(
                    balances=sentinel.balances_live, denomination=sentinel.non_provided_denomination
                ),
            ]
        )
        self.mock_is_within_cooling_off_period.assert_called_once_with(
            vault=mock_vault, effective_datetime=sentinel.datetime
        )
