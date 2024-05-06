from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import patch, Mock

# inception imports
from inception_sdk.test_framework.contracts.unit.common import ContractFeatureTest
from inception_sdk.vault.contracts.types_extension import UnionItemValue
import library.features.lending.interest.fixed_to_variable_rate as fixed_to_variable_rate

DEFAULT_START_DATE = datetime(2019, 1, 1)
DEFAULT_EFFECTIVE_DATE = DEFAULT_START_DATE + relativedelta(months=6)
DEFAULT_ELAPSED_TERM = 6


class TestFixedToVariableRateCalculationBase(ContractFeatureTest):
    target_test_file = "library/features/lending/interest/fixed_to_variable_rate.py"

    def test_calculate_daily_accrual_amount(self):
        test_cases = [
            # 365
            # within fixed term
            {
                "description": "365 days, within fixed term. (2388.12 * 0.0125/365 ~ 0.08178)",
                "days_in_year": UnionItemValue("365"),
                "mortgage_start_date": DEFAULT_START_DATE,
                "fixed_interest_term": Decimal("12"),
                "fixed_interest_rate": Decimal("0.0125"),
                "expected_result": Decimal("0.08178"),
            },
            # within variable term
            {
                "description": "365 days, within variable term. "
                "(2388.12 * (0.0125+0)/365 ~ 0.08178)",
                "days_in_year": UnionItemValue("365"),
                "mortgage_start_date": DEFAULT_START_DATE,
                "fixed_interest_term": Decimal("4"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("0.00"),
                "expected_result": Decimal("0.08178"),
            },
            {
                "description": "365 days, within variable term. "
                "(2388.12 * (0.0125+0.25)/365 ~ 1.71748)",
                "days_in_year": UnionItemValue("365"),
                "mortgage_start_date": DEFAULT_START_DATE,
                "fixed_interest_term": Decimal("4"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("0.25"),
                "expected_result": Decimal("1.71748"),
            },
            {
                "description": "365 days, within variable term. "
                "(2388.12 * (0.0125-0.002)/365 ~ 0.06869)",
                "days_in_year": UnionItemValue("365"),
                "mortgage_start_date": DEFAULT_START_DATE,
                "fixed_interest_term": Decimal("4"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("-0.002"),
                "expected_result": Decimal("0.06870"),
            },
            # 366
            # within fixed term
            {
                "description": "366 days, within fixed term. (2388.12 * 0.0125/366 ~ 0.08156)",
                "days_in_year": UnionItemValue("366"),
                "mortgage_start_date": DEFAULT_START_DATE,
                "fixed_interest_term": Decimal("12"),
                "fixed_interest_rate": Decimal("0.0125"),
                "expected_result": Decimal("0.08156"),
            },
            # within variable term
            {
                "description": "366 days, within variable term. "
                "(2388.12 * (0.0125+0)/366 ~ 0.08156)",
                "days_in_year": UnionItemValue("366"),
                "mortgage_start_date": DEFAULT_START_DATE,
                "fixed_interest_term": Decimal("4"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("0.00"),
                "expected_result": Decimal("0.08156"),
            },
            {
                "description": "366 days, within variable term. "
                "(2388.12 * (0.0125+0.25)/366 ~ 1.71279)",
                "days_in_year": UnionItemValue("366"),
                "mortgage_start_date": DEFAULT_START_DATE,
                "fixed_interest_term": Decimal("4"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("0.25"),
                "expected_result": Decimal("1.71279"),
            },
            {
                "description": "366 days, within variable term. "
                "(2388.12 * (0.0125-0.002)/366 ~ 0.06851)",
                "days_in_year": UnionItemValue("366"),
                "mortgage_start_date": DEFAULT_START_DATE,
                "fixed_interest_term": Decimal("4"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("-0.002"),
                "expected_result": Decimal("0.06851"),
            },
            # 360
            # within fixed term
            {
                "description": "360 days, within fixed term. " "(2388.12 * 0.0125/360 ~ 0.08292)",
                "days_in_year": UnionItemValue("360"),
                "mortgage_start_date": DEFAULT_START_DATE,
                "fixed_interest_term": Decimal("12"),
                "fixed_interest_rate": Decimal("0.0125"),
                "expected_result": Decimal("0.08292"),
            },
            # within variable term
            {
                "description": "360 days, within variable term. "
                "(2388.12 * (0.0125+0)/360 ~ 0.08292)",
                "days_in_year": UnionItemValue("360"),
                "mortgage_start_date": DEFAULT_START_DATE,
                "fixed_interest_term": Decimal("4"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("0.00"),
                "expected_result": Decimal("0.08292"),
            },
            {
                "description": "360 days, within variable term. "
                "(2388.12 * (0.0125+0.25)/360 ~ 1.74134)",
                "days_in_year": UnionItemValue("360"),
                "mortgage_start_date": DEFAULT_START_DATE,
                "fixed_interest_term": Decimal("4"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("0.25"),
                "expected_result": Decimal("1.74134"),
            },
            {
                "description": "360 days, within variable term. "
                "(2388.12 * (0.0125-0.002)/360 ~ 0.06965)",
                "days_in_year": UnionItemValue("360"),
                "mortgage_start_date": DEFAULT_START_DATE,
                "fixed_interest_term": Decimal("4"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("-0.002"),
                "expected_result": Decimal("0.06965"),
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock(
                days_in_year=test_case["days_in_year"],
                mortgage_start_date=test_case["mortgage_start_date"],
                fixed_interest_term=test_case["fixed_interest_term"],
                fixed_interest_rate=test_case.get("fixed_interest_rate"),
                variable_interest_rate=test_case.get("variable_interest_rate"),
                variable_rate_adjustment=test_case.get("variable_rate_adjustment"),
            )

            result = fixed_to_variable_rate.calculate_daily_accrual_amount(
                mock_vault,
                Decimal("2388.12"),
                effective_date=DEFAULT_EFFECTIVE_DATE,
                elapsed_term_in_month=DEFAULT_ELAPSED_TERM,
            )
            self.assertEqual(result, test_case["expected_result"])

    @patch("library.features.lending.interest.fixed_to_variable_rate.variable_rate")
    def test_should_trigger_reamortisation(self, mock_variable_rate):
        test_cases = [
            # Never reamortise within fixed term
            {
                "description": "effective date and prev effective date within fixed term, "
                "variable rate is unchanged",
                "fixed_interest_term": Decimal("12"),
                "elapsed_term": 2,
                "rate_adjusted": False,
                "expected_result": False,
            },
            {
                "description": "effective date and prev effective date within fixed term, "
                "variable rate is changed but impactless",
                "fixed_interest_term": Decimal("12"),
                "elapsed_term": 2,
                "rate_adjusted": True,
                "expected_result": False,
            },
            # Reamortise when leaving fixed term
            {
                "description": "effective date outside but prev effective date within fixed term, "
                "variable rate is unchanged",
                "fixed_interest_term": Decimal("12"),
                "elapsed_term": 13,
                "rate_adjusted": False,
                "expected_result": True,
            },
            {
                "description": "effective date outside but prev effective date within fixed term, "
                "variable rate is changed",
                "fixed_interest_term": Decimal("12"),
                "elapsed_term": 13,
                "rate_adjusted": True,
                "expected_result": True,
            },
            # Only reamortise in variable term if variable rate has changed
            {
                "description": "effective date outside but prev effective date within fixed term, "
                "variable rate is unchanged",
                "fixed_interest_term": Decimal("12"),
                "elapsed_term": 14,
                "rate_adjusted": False,
                "expected_result": False,
            },
            {
                "description": "effective date outside but prev effective date within fixed term, "
                "variable rate is changed",
                "fixed_interest_term": Decimal("12"),
                "elapsed_term": 14,
                "rate_adjusted": True,
                "expected_result": True,
            },
        ]
        for test_case in test_cases:
            mock_variable_rate.should_trigger_reamortisation.return_value = test_case[
                "rate_adjusted"
            ]
            mock_vault = self.create_mock(
                loan_start_date=DEFAULT_START_DATE,
                fixed_interest_term=test_case["fixed_interest_term"],
            )
            result = fixed_to_variable_rate.should_trigger_reamortisation(
                mock_vault,
                elapsed_term_in_months=test_case["elapsed_term"],
                # only used by the variable rate feature, which is mocked here
                due_amount_schedule_details=Mock(),
            )
            self.assertEqual(result, test_case["expected_result"], msg=test_case["description"])

    @patch.object(fixed_to_variable_rate.variable_rate, "get_daily_interest_rate")
    @patch.object(fixed_to_variable_rate.fixed_rate, "get_daily_interest_rate")
    @patch.object(fixed_to_variable_rate, "is_within_fixed_rate_term")
    def test_get_daily_interest_rate_within_fixed_term(
        self, mocked_is_within_fixed_rate_term, mocked_fixed_rate, mocked_variable_rate
    ):
        elapsed_term = 6
        mock_vault = self.create_mock()
        mocked_is_within_fixed_rate_term.return_value = True
        fixed_to_variable_rate.get_daily_interest_rate(
            mock_vault, DEFAULT_EFFECTIVE_DATE, elapsed_term
        )
        mocked_is_within_fixed_rate_term.assert_called_once_with(mock_vault, elapsed_term)
        mocked_fixed_rate.assert_called_once_with(mock_vault, DEFAULT_EFFECTIVE_DATE)
        mocked_variable_rate.assert_not_called()

    @patch.object(fixed_to_variable_rate.variable_rate, "get_daily_interest_rate")
    @patch.object(fixed_to_variable_rate.fixed_rate, "get_daily_interest_rate")
    @patch.object(fixed_to_variable_rate, "is_within_fixed_rate_term")
    def test_get_daily_interest_rate_outside_fixed_term(
        self, mocked_is_within_fixed_rate_term, mocked_fixed_rate, mocked_variable_rate
    ):
        elapsed_term = 7
        mock_vault = self.create_mock()
        mocked_is_within_fixed_rate_term.return_value = False
        fixed_to_variable_rate.get_daily_interest_rate(
            mock_vault, DEFAULT_EFFECTIVE_DATE, elapsed_term
        )
        mocked_is_within_fixed_rate_term.assert_called_once_with(mock_vault, elapsed_term)
        mocked_variable_rate.assert_called_once_with(mock_vault, DEFAULT_EFFECTIVE_DATE)
        mocked_fixed_rate.assert_not_called()

    def test_is_within_fixed_rate_term(self):
        test_cases = [
            {
                "description": "elapsed term less than fixed rate term",
                "elapsed_term": 5,
                "fixed_rate_term": "6",
                "expected_output": True,
            },
            {
                "description": "elapsed term greater than fixed rate term",
                "elapsed_term": 7,
                "fixed_rate_term": "6",
                "expected_output": False,
            },
            {
                "description": "elapsed term equal to fixed rate term",
                "elapsed_term": 6,
                "fixed_rate_term": "6",
                "expected_output": True,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(fixed_interest_term=test_case["fixed_rate_term"])
            result = fixed_to_variable_rate.is_within_fixed_rate_term(
                mock_vault, test_case["elapsed_term"]
            )
            self.assertEqual(result, test_case["expected_output"], test_case["description"])
