from datetime import datetime
from decimal import Decimal, getcontext
from unittest import skipIf
from unittest.mock import Mock, PropertyMock

# inception imports
from inception_sdk.test_framework.contracts.unit.common import ContractFeatureTest
from inception_sdk.vault.contracts.types_extension import UnionItemValue
from library.features.lending.interest.fixed_rate import (
    calculate_daily_accrual_amount,
    get_monthly_interest_rate,
    should_trigger_reamortisation,
)

DEFAULT_DATE = datetime(2019, 1, 1)


class TestFixedRateCalculationBase(ContractFeatureTest):
    target_test_file = "library/features/lending/interest/fixed_rate.py"

    def test_calculate_daily_accrual_amount(self):
        test_cases = [
            {
                "description": "365 days (2388.12 * 0.0125/365 ~ 0.08178)",
                "days_in_year": UnionItemValue("365"),
                "fixed_interest_rate": Decimal("0.0125"),
                "expected_result": Decimal("0.08178"),
            },
            {
                "description": "366 days (2388.12 * 0.0125/366 ~ 0.08156)",
                "days_in_year": UnionItemValue("366"),
                "fixed_interest_rate": Decimal("0.0125"),
                "expected_result": Decimal("0.08156"),
            },
            {
                "description": "360 days (2388.12 * 0.0125/360 ~ 0.08292)",
                "days_in_year": UnionItemValue("360"),
                "fixed_interest_rate": Decimal("0.0125"),
                "expected_result": Decimal("0.08292"),
            },
            {
                "description": "365 days (2388.12 * -0.0126/365 ~ 0.08244)",
                "days_in_year": UnionItemValue("365"),
                "fixed_interest_rate": Decimal("-0.0126"),
                "expected_result": Decimal("0.08244"),
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock(
                days_in_year=test_case["days_in_year"],
                fixed_interest_rate=test_case["fixed_interest_rate"],
            )
            result = calculate_daily_accrual_amount(mock_vault, Decimal("2388.12"), DEFAULT_DATE)
            self.assertEqual(result, test_case["expected_result"], msg=test_case["description"])

    def test_get_monthly_interest_rate(self):
        mock_vault = self.create_mock(fixed_interest_rate="0.012")
        self.assertEqual(get_monthly_interest_rate(mock_vault), Decimal("0.001"))

    def test_get_monthly_interest_rate_0(self):
        mock_vault = self.create_mock(fixed_interest_rate="0")
        self.assertEqual(get_monthly_interest_rate(mock_vault), Decimal("0"))

    # This skip can be verified by adding the following after the module imports
    # decimal.setcontext(decimal.Context(prec=5))
    @skipIf(
        condition=getcontext().prec != 28,
        reason="decimal precision is not the module default and assertion needs changing",
    )
    def test_get_monthly_interest_rate_indivisible(self):
        mock_vault = self.create_mock(fixed_interest_rate="0.011")
        self.assertEqual(
            get_monthly_interest_rate(mock_vault), Decimal("0.0009166666666666666666666666667")
        )

    def test_should_trigger_reamortisation(self):
        mock_vault = self.create_mock(fixed_interest_rate="0.012")
        mock_schedule_details = Mock()
        type(mock_schedule_details).last_execution_time = PropertyMock(return_value=None)
        self.assertEqual(
            should_trigger_reamortisation(
                mock_vault,
                elapsed_term_in_months=5,
                due_amount_schedule_details=mock_schedule_details,
            ),
            False,
        )
