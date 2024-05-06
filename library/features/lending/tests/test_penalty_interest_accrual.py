# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

# common
from inception_sdk.test_framework.contracts.unit.common import ContractFeatureTest
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    UnionItemValue,
)

# other
import library.features.lending.interest.fixed_rate as fixed_rate
import library.features.lending.penalty_interest_accrual as penalty_interest_accrual

DEFAULT_DATE = datetime(2019, 1, 1)


class TestPenaltyInterestCalculationBase(ContractFeatureTest):
    target_test_file = "library/features/lending/penalty_interest_accrual.py"

    def test_calculate_daily_accrual_amount(self):
        test_cases = [
            # Penalty rate only
            {
                "description": "365 days (2388.12 * 0.0125/365 ~ 0.08178)",
                "days_in_year": UnionItemValue("365"),
                "penalty_interest_rate": Decimal("0.0125"),
                "penalty_includes_base_rate": UnionItemValue("False"),
                "expected_result": Decimal("0.08"),
            },
            {
                "description": "366 days (2388.12 * 0.0122/366 ~ 0.07960)",
                "days_in_year": UnionItemValue("366"),
                "penalty_interest_rate": Decimal("0.0122"),
                "penalty_includes_base_rate": UnionItemValue("False"),
                "expected_result": Decimal("0.08"),
            },
            {
                "description": "360 days (2388.12 * 0.0125/360 ~ 0.08292)",
                "days_in_year": UnionItemValue("360"),
                "penalty_interest_rate": Decimal("0.0125"),
                "penalty_includes_base_rate": UnionItemValue("False"),
                "expected_result": Decimal("0.08"),
            },
            # Base rate + penalty rate
            {
                "description": "365 days (2388.12 * 0.0355/365 ~ 0.23226",
                "days_in_year": UnionItemValue("365"),
                "penalty_interest_rate": Decimal("0.0125"),
                "penalty_includes_base_rate": UnionItemValue("True"),
                "expected_result": Decimal("0.23"),
            },
            {
                "description": "366 days (2388.12 * 0.0355/366 ~ 0.23163)",
                "days_in_year": UnionItemValue("366"),
                "penalty_interest_rate": Decimal("0.0125"),
                "penalty_includes_base_rate": UnionItemValue("True"),
                "expected_result": Decimal("0.23"),
            },
            {
                "description": "360 days (2388.12 * 0.0355/360 ~ 0.23549)",
                "days_in_year": UnionItemValue("360"),
                "penalty_interest_rate": Decimal("0.0125"),
                "penalty_includes_base_rate": UnionItemValue("True"),
                "expected_result": Decimal("0.24"),
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock(
                days_in_year=test_case["days_in_year"],
                penalty_interest_rate=test_case["penalty_interest_rate"],
                penalty_includes_base_rate=test_case["penalty_includes_base_rate"],
                fixed_interest_rate=Decimal("0.023"),
            )
            result = penalty_interest_accrual.calculate_daily_accrual_amount(
                mock_vault, Decimal("2388.12"), DEFAULT_DATE, fixed_rate.feature
            )
            self.assertEqual(result, test_case["expected_result"], msg=test_case["description"])

    def test_get_accrual_posting_instructions(self):

        mock_formula = Mock(return_value=Decimal("100"))

        mock_vault = self.create_mock(
            penalty_interest_income_account="PENALTY_INTEREST_INCOME",
        )

        results = penalty_interest_accrual.get_accrual_posting_instructions(
            mock_vault,
            DEFAULT_DATE,
            "GBP",
            mock_formula,
            accrual_capital=Decimal(1000),
            accrual_address="PENALTIES",
        )

        self.assertEqual(len(results), 1)
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("100"),
            denomination="GBP",
            client_transaction_id="ACCRUE_PENALTY_INTEREST_MOCK_HOOK_GBP",
            from_account_id=mock_vault.account_id,
            from_account_address="PENALTIES",
            to_account_id="PENALTY_INTEREST_INCOME",
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            instruction_details={
                "description": "Daily penalty interest accrued on balance of 1000",
                "event": penalty_interest_accrual.ACCRUAL_EVENT,
            },
            override_all_restrictions=True,
        )

    def test_get_accrual_posting_instructions_zero_accrual(self):

        mock_formula = Mock(return_value=Decimal("0"))

        mock_vault = self.create_mock(
            penalty_interest_income_account="PENALTY_INTEREST_INCOME",
        )

        results = penalty_interest_accrual.get_accrual_posting_instructions(
            mock_vault,
            DEFAULT_DATE,
            "GBP",
            mock_formula,
            accrual_capital=Decimal(1000),
            accrual_address="PENALTIES",
        )

        self.assertListEqual([], results)
