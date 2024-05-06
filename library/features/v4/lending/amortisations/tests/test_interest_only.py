# standard libs
from decimal import Decimal
from typing import Callable
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.lending.amortisations.interest_only as interest_only

# contracts api
from contracts_api import Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest


class InterestOnlyCommon(FeatureTest):
    default_denomination = "GBP"
    tside = Tside.ASSET


@patch.object(interest_only.term_helpers, "calculate_term_details_from_counter")
class TermDetailsTest(FeatureTest):
    def test_term_details_with_optional_args(
        self,
        calculate_term_details_from_counter: MagicMock,
    ):
        calculate_term_details_from_counter.return_value = sentinel.term_details

        result = interest_only.term_details(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=sentinel.use_expected_term,
            interest_rate=sentinel.interest_rate_feature,
            principal_adjustments=sentinel.principal_adjustments,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        calculate_term_details_from_counter.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertEqual(result, sentinel.term_details)

    def test_term_details_without_optional_args(
        self,
        calculate_term_details_from_counter: MagicMock,
    ):
        calculate_term_details_from_counter.return_value = sentinel.term_details

        result = interest_only.term_details(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
        )

        calculate_term_details_from_counter.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            balances=None,
            denomination=None,
        )
        self.assertEqual(result, sentinel.term_details)


def mock_interest_get_annual_interest_rate(rate: Decimal) -> Callable:
    def get_annual_interest_rate(vault, effective_datetime, *args, **kwargs):
        return rate

    return get_annual_interest_rate


class CalculateEmi(FeatureTest):
    def test_calculate_emi(
        self,
    ):

        result = interest_only.calculate_emi(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
        )

        self.assertEqual(result, Decimal("0"))


class IsInterestOnlyLoanTest(FeatureTest):
    def test_is_interest_only_loan_true(self):
        self.assertEqual(
            interest_only.is_interest_only_loan("INTEREST_ONLY"),
            True,
        )

    def test_is_interest_only_lower_case_true(self):
        self.assertEqual(
            interest_only.is_interest_only_loan("interest_only"),
            True,
        )

    def test_is_interest_only_loan_false(self):
        self.assertEqual(interest_only.is_interest_only_loan("other"), False)
