# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
from decimal import ROUND_05UP, Decimal, ROUND_HALF_UP, ROUND_FLOOR, ROUND_HALF_DOWN

from inception_sdk.test_framework.contracts.unit.common import (
    ContractFeatureTest,
)

from library.features.common import utils_common as utils

# it's clumsy to assert on an unbounded number of decimal places so this is used to enforce
# decimal precision on assertions when converting from yearly rate
DEFAULT_DECIMAL_PRECISION = 10


class UtilsTest(ContractFeatureTest):
    target_test_file = "library/features/common/utils_common.py"
    disable_rendering = True

    def test_str_to_bool(self):
        test_cases = [
            {
                "description": "returns true when string is true",
                "string": "true",
                "expected_result": True,
            },
            {
                "description": "returns true when string is mixed case",
                "string": "tRue",
                "expected_result": True,
            },
            {
                "description": "returns false when string is false",
                "string": "false",
                "expected_result": False,
            },
            {
                "description": "returns false when string is empty",
                "string": "",
                "expected_result": False,
            },
            {
                "description": "returns false when string is random text",
                "string": "abcd",
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            result = utils.str_to_bool(test_case["string"])
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_round_with_different_rounding_methods(self):
        positive_input = Decimal("15.456")
        negative_input = Decimal("-15.456")
        input_data = [
            ("round floor", ROUND_FLOOR, positive_input, Decimal("15.45")),
            ("round half down", ROUND_HALF_DOWN, positive_input, Decimal("15.46")),
            ("round half up", ROUND_HALF_UP, positive_input, Decimal("15.46")),
            ("round floor negative", ROUND_FLOOR, negative_input, Decimal("-15.46")),
            ("round half up negative", ROUND_HALF_UP, negative_input, Decimal("-15.46")),
            ("round half down negative", ROUND_HALF_DOWN, negative_input, Decimal("-15.46")),
            ("round 05 up negative", ROUND_05UP, negative_input, Decimal("-15.46")),
        ]

        for test_name, rounding, input_amount, expected_amount in input_data:
            result = utils.round_decimal(
                amount=input_amount,
                decimal_places=2,
                rounding=rounding,
            )
            self.assertEqual(result, expected_amount, test_name)

    def test_yearly_to_monthly_rate(self):
        result = round(utils.yearly_to_monthly_rate(Decimal("0.011")), DEFAULT_DECIMAL_PRECISION)

        self.assertEqual(result, Decimal("0.0009166667"))

    def test_round_with_different_precision(self):
        input_data = [
            ("0 dp", 0, Decimal("15")),
            ("2 dp", 2, Decimal("15.46")),
            ("5 dp", 5, Decimal("15.45556")),
        ]

        for test_name, decimal_places, expected_amount in input_data:
            result = utils.round_decimal(
                amount=Decimal("15.455555"),
                decimal_places=decimal_places,
                rounding=ROUND_HALF_UP,
            )
            self.assertEqual(result, expected_amount, test_name)

    def test_get_transaction_type(self):
        test_cases = [
            {
                "description": "returns correct type from code",
                "instruction_details": {
                    "transaction_code": "00",
                },
                "txn_code_to_type_map": {
                    "00": "cash_advance",
                    "01": "purchase",
                },
                "default_txn_type": "purchase",
                "expected_result": "cash_advance",
            },
            {
                "description": "returns correct type for empty string code",
                "instruction_details": {"transaction_code": ""},
                "txn_code_to_type_map": {
                    "": "cash_advance",
                    "01": "purchase",
                },
                "default_txn_type": "default_purchase",
                "expected_result": "cash_advance",
            },
            {
                "description": "returns default type if code not in map",
                "instruction_details": {
                    "transaction_code": "04",
                },
                "txn_code_to_type_map": {
                    "00": "cash_advance",
                    "01": "purchase",
                },
                "default_txn_type": "default_purchase",
                "expected_result": "default_purchase",
            },
            {
                "description": "returns default type if no transaction_code",
                "instruction_details": {},
                "txn_code_to_type_map": {
                    "00": "cash_advance",
                    "01": "purchase",
                },
                "default_txn_type": "default_purchase",
                "expected_result": "default_purchase",
            },
        ]

        for test_case in test_cases:
            result = utils.get_transaction_type(
                instruction_details=test_case["instruction_details"],
                txn_code_to_type_map=test_case["txn_code_to_type_map"],
                default_txn_type=test_case["default_txn_type"],
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])
