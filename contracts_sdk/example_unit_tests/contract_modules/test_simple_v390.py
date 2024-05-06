from datetime import datetime
from decimal import Decimal
import os

from ...utils.tools import ContractModules390TestCase
from ...versions.version_390.contract_modules import types


class SimpleTestCase(ContractModules390TestCase):
    filepath = os.environ.get(
        "DATA_SIMPLE_V390", "contracts_sdk/example_unit_tests/contract_modules/simple_v390.py"
    )
    contract_code = ContractModules390TestCase.load_contract_code(filepath)
    effective_date = datetime(2021, 1, 1)

    def test_round_accrual(self):
        amount = Decimal("0.123456789")
        amount_rounded = self.run_contract_function(self.contract_code, "round_accrual", amount)
        self.assertEqual(Decimal("0.12346"), amount_rounded)

    def test_round_fullfilment(self):
        amount = Decimal("0.123456789")
        amount_rounded = self.run_contract_function(self.contract_code, "round_fulfilment", amount)
        self.assertEqual(Decimal("0.12"), amount_rounded)

    def test_build_posting_instruction_batch_fails_with_negative_amount(self):
        amount = Decimal("-0.1")
        with self.assertRaises(types.Rejected) as ex:
            self.run_contract_function(
                self.contract_code, "build_posting_instruction_batch", amount, self.effective_date
            )
        self.assertIn("Cannot build PostingInstructions with negative amount", str(ex.exception))

    def test_build_posting_instruction_batch_with_positive_amount(self):
        amount = Decimal("5")
        posting_instruction_batch = self.run_contract_function(
            self.contract_code, "build_posting_instruction_batch", amount, self.effective_date
        )
        self.assertEqual(1, len(posting_instruction_batch))
        self.assertEqual(amount, posting_instruction_batch[0].amount)
        self.assertEqual(self.effective_date, posting_instruction_batch.value_timestamp)
