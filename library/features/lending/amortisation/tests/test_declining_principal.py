from decimal import Decimal

# inception library
from inception_sdk.test_framework.contracts.unit.common import ContractFeatureTest
import library.features.lending.amortisation.declining_principal as declining_principal


class DecliningPrincipalRepaymentTest(ContractFeatureTest):
    target_test_file = "library/features/lending/amortisation/declining_principal.py"

    def test_calculate_emi(self):
        test_cases = [
            {
                "description": "declining principal without lump sum",
                "input": {
                    "fulfillment_precision": 2,
                    "remaining_principal": Decimal("100"),
                    "interest_rate": Decimal("0.02"),
                    "remaining_term": 2,
                    "lump_sum_amount": Decimal("0"),
                },
                # (100*0.02)*((1+0.02)^2)/(((1+0.02)^1)-1) = 51.50
                "expected_result": Decimal("51.50"),
            },
            {
                "description": "declining principal lump sum amount is None",
                "input": {
                    "fulfillment_precision": 2,
                    "remaining_principal": Decimal("100"),
                    "interest_rate": Decimal("0.02"),
                    "remaining_term": 2,
                    "lump_sum_amount": None,
                },
                "expected_result": Decimal("51.50"),
            },
            {
                "description": "lump sum amount is non-0",
                "input": {
                    "fulfillment_precision": 2,
                    "remaining_principal": Decimal("100000"),
                    "interest_rate": Decimal("0.02") / Decimal("12"),
                    "remaining_term": 36,
                    "lump_sum_amount": Decimal("50000"),
                },
                # (100000-(50000/(1+0.02/12)^2))*0.02/12*(1+0.02/12)^2/(1+0.02/12)^2-1 =1515.46
                "expected_result": Decimal("1515.46"),
            },
        ]
        for test_case in test_cases:
            result = declining_principal.calculate_emi(**test_case["input"])
            self.assertEqual(result, test_case["expected_result"], test_case["description"])
