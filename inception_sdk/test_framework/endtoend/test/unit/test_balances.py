# standard libs
from datetime import datetime
from unittest import TestCase

# inception sdk
import inception_sdk.test_framework.endtoend.balances as balances
from inception_sdk.test_framework.common.balance_helpers import Balance, BalanceDimensions

BALANCES = [
    {
        "id": "1",
        "account_id": "1",
        "account_address": "DEFAULT",
        "phase": "POSTING_PHASE_COMMITTED",
        "asset": "COMMERCIAL_BANK_MONEY",
        "denomination": "GBP",
        "value_time": "2021-01-01T00:00:00Z",
        "amount": "60",
        "total_debit": "0",
        "total_credit": "60",
    },
    {
        "id": "2",
        "account_id": "1",
        "account_address": "OTHER",
        "phase": "POSTING_PHASE_COMMITTED",
        "asset": "COMMERCIAL_BANK_MONEY",
        "denomination": "GBP",
        "value_time": "",
        "amount": "20",
        "total_debit": "0",
        "total_credit": "20",
    },
]


class BalancesTest(TestCase):
    def setUp(self) -> None:
        self.sample_balances = BALANCES
        self.maxDiff = None
        return super().setUp()

    def test_standardise_balance_value_time_format(self):
        test_cases = [
            {
                "description": "timestamp without milliseconds",
                "timestamp": "2021-10-11T00:00:00Z",
                "expected_result": datetime(2021, 10, 11, 0, 0, 0),
            },
            {
                "description": "timestamp with milliseconds",
                "timestamp": "2021-10-11T00:00:00.12345Z",
                "expected_result": datetime(2021, 10, 11, 0, 0, 0),
            },
            {
                "description": "No timestamp",
                "timestamp": None,
                "expected_result": datetime(1970, 1, 1, 0, 0, 0),
            },
        ]

        for test_case in test_cases:
            result = balances.standardise_balance_value_time_format(test_case["timestamp"])

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_create_balance_dict(self):
        expected_balance_dict = {}
        expected_balance_dict[
            BalanceDimensions("DEFAULT", "COMMERCIAL_BANK_MONEY", "GBP", "POSTING_PHASE_COMMITTED")
        ] = Balance(
            net="60",
            credit="60",
            debit="0",
            value_timestamp=datetime(2021, 1, 1, 0, 0, 0),
        )
        expected_balance_dict[
            BalanceDimensions("OTHER", "COMMERCIAL_BANK_MONEY", "GBP", "POSTING_PHASE_COMMITTED")
        ] = Balance(
            net="20",
            credit="20",
            debit="0",
            value_timestamp=datetime(1970, 1, 1, 0, 0, 0),
        )

        result = balances.create_balance_dict(self.sample_balances)
        self.assertDictEqual(expected_balance_dict, result)

        # loop needed because value_time is not considered in the balance __eq__ method
        for dimension, balance_object in expected_balance_dict.items():
            self.assertEqual(balance_object.value_timestamp, result[dimension].value_timestamp)
