# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
from library.features.v4.lending import derived_params

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest


@patch.object(derived_params.utils, "sum_balances")
class CalculateTotalDueAmountTest(FeatureTest):
    def test_get_total_due_amount(self, mock_sum_balances: MagicMock):
        mock_sum = Decimal("100.00")
        mock_sum_balances.return_value = mock_sum
        total_due_amount = derived_params.get_total_due_amount(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        self.assertEqual(total_due_amount, mock_sum)
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=derived_params.lending_addresses.REPAYMENT_HIERARCHY,
            denomination=sentinel.denomination,
            decimal_places=sentinel.precision,
        )


@patch.object(derived_params.utils, "sum_balances")
class CalculateTotalOutstandingDebtTest(FeatureTest):
    def test_get_total_outstanding_debt(self, mock_sum_balances: MagicMock):
        mock_sum = Decimal("100.00")
        mock_sum_balances.return_value = mock_sum
        total_outstanding_debt = derived_params.get_total_outstanding_debt(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        self.assertEqual(total_outstanding_debt, mock_sum)
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=derived_params.lending_addresses.ALL_OUTSTANDING,
            denomination=sentinel.denomination,
            decimal_places=sentinel.precision,
        )


@patch.object(derived_params.utils, "sum_balances")
class CalculateTotalRemainingPrincipalTest(FeatureTest):
    def test_get_total_remaining_principal(self, mock_sum_balances: MagicMock):
        mock_sum = Decimal("100.00")
        mock_sum_balances.return_value = mock_sum
        total_remaining_principal = derived_params.get_total_remaining_principal(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        self.assertEqual(total_remaining_principal, mock_sum)
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=derived_params.lending_addresses.ALL_PRINCIPAL,
            denomination=sentinel.denomination,
            decimal_places=sentinel.precision,
        )


@patch.object(derived_params, "get_total_remaining_principal")
class CalculatePrincipalPaidToDateTest(FeatureTest):
    def test_get_principal_paid_to_date(self, mock_get_total_remaining_principal: MagicMock):
        mock_get_total_remaining_principal.return_value = Decimal("88")
        principal_paid_to_date = derived_params.get_principal_paid_to_date(
            original_principal=Decimal("100"),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        expected = Decimal("12")
        self.assertEqual(principal_paid_to_date, expected)
        mock_get_total_remaining_principal.assert_called_with(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )


class RemainingTermTest(FeatureTest):
    def setUp(self) -> None:
        self.mock_term_details = MagicMock(
            return_value=(sentinel.elapsed_term, sentinel.remaining_term)
        )
        self.mock_amortisation = MagicMock(term_details=self.mock_term_details)

    def test_get_remaining_term(self):
        result = derived_params.get_remaining_term(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            amortisation_feature=self.mock_amortisation,
            interest_rate=sentinel.interest_rate,
            principal_adjustments=[sentinel.principal_adjustments],
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertEqual(result, sentinel.remaining_term)
        self.mock_term_details.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            interest_rate=sentinel.interest_rate,
            principal_adjustments=[sentinel.principal_adjustments],
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

    def test_get_remaining_term_without_optional_args(self):
        result = derived_params.get_remaining_term(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            amortisation_feature=self.mock_amortisation,
        )
        self.assertEqual(result, sentinel.remaining_term)
        self.mock_term_details.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.datetime,
            interest_rate=None,
            principal_adjustments=None,
            balances=None,
            denomination=None,
        )
