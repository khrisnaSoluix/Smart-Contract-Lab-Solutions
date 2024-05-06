# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.lending.term_helpers as term_helpers
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)


class TermHelpersCommon(FeatureTest):
    default_denomination = "GBP"
    tside = Tside.ASSET


class CalculateElapsedTermTest(TermHelpersCommon):
    @patch.object(term_helpers.utils, "balance_at_coordinates")
    def test_elapsed_term_extracted_from_tracker_balance(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.return_value = Decimal(10)

        self.assertEqual(
            term_helpers.calculate_elapsed_term(
                balances=sentinel.balances,
                denomination=sentinel.denomination,
            ),
            10,
        )

        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            address=term_helpers.lending_addresses.DUE_CALCULATION_EVENT_COUNTER,
        )


class CalculateTermDetailsFromCounter(TermHelpersCommon):
    @patch.object(term_helpers.utils, "balance_at_coordinates")
    @patch.object(term_helpers.utils, "get_parameter")
    def test_elapsed_term_extracted_from_tracker_balance(
        self, mock_get_parameter, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_observation_fetcher_mapping = {
            term_helpers.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                "dummy_observation"
            )
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=mock_balance_observation_fetcher_mapping,
        )
        mock_balance_at_coordinates.return_value = Decimal(10)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                term_helpers.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: (Decimal("10")),
            }
        )
        self.assertEqual(
            term_helpers.calculate_term_details_from_counter(
                vault=mock_vault,
                effective_datetime=sentinel.datetime,
            ),
            (10, 0),
        )

        mock_balance_at_coordinates.assert_called_once_with(
            balances=SentinelBalancesObservation("dummy_observation").balances,
            denomination=sentinel.denomination,
            address=term_helpers.lending_addresses.DUE_CALCULATION_EVENT_COUNTER,
        )

    @patch.object(term_helpers.utils, "balance_at_coordinates")
    @patch.object(term_helpers.utils, "get_parameter")
    def test_elapsed_term_extracted_from_tracker_balance_all_args_provided(
        self, mock_get_parameter, mock_balance_at_coordinates: MagicMock
    ):
        mock_vault = self.create_mock()
        mock_balance_at_coordinates.return_value = Decimal(10)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                term_helpers.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: (Decimal("12")),
            }
        )
        self.assertEqual(
            term_helpers.calculate_term_details_from_counter(
                vault=mock_vault,
                effective_datetime=sentinel.datetime,
                denomination=sentinel.denomination,
                balances=sentinel.balances,
            ),
            (10, 2),
        )

        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            address=term_helpers.lending_addresses.DUE_CALCULATION_EVENT_COUNTER,
        )

    @patch.object(term_helpers.utils, "balance_at_coordinates")
    @patch.object(term_helpers.utils, "get_parameter")
    def test_elapsed_term_extracted_from_tracker_balance_same_datetime_as_account_creation(
        self, mock_get_parameter, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_observation_fetcher_mapping = {
            term_helpers.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                "dummy_observation"
            )
        }
        mock_vault = self.create_mock(
            creation_date=sentinel.creation_date,
            balances_observation_fetchers_mapping=mock_balance_observation_fetcher_mapping,
        )
        mock_balance_at_coordinates.return_value = Decimal(10)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                term_helpers.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: (Decimal("10")),
            }
        )
        self.assertEqual(
            term_helpers.calculate_term_details_from_counter(
                vault=mock_vault,
                effective_datetime=sentinel.creation_date,
                denomination=sentinel.denomination,
            ),
            (0, 10),
        )

        mock_balance_at_coordinates.assert_not_called()
