# standard library
from decimal import Decimal

# inception imports
from inception_sdk.test_framework.contracts.unit.common import ContractFeatureTest

from inception_sdk.vault.contracts.types_extension import (
    Rejected,
    OptionalValue,
)
from library.features.lending import maximum_loan_amount, minimum_loan_amount

from inception_sdk.vault.contracts.types_extension import Tside


class TestMaximumLoanAmount(ContractFeatureTest):
    target_test_file = "library/features/lending/maximum_loan_amount.py"
    side = Tside.ASSET

    def setUp(self) -> None:
        self.vault = self.create_mock(
            maximum_loan_amount=OptionalValue(Decimal(100)), denomination="GBP"
        )

    def test_maximum_loan_amount_accepted(self):

        postings = [self.outbound_hard_settlement(amount=50, denomination="GBP")]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        self.assertIsNone(
            maximum_loan_amount.validate(self.vault, postings=pib, denomination="GBP")
        )

    def test_maximum_loan_amount_met(self):

        postings = [self.outbound_hard_settlement(amount=100, denomination="GBP")]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        self.assertIsNone(
            maximum_loan_amount.validate(self.vault, postings=pib, denomination="GBP")
        )

    def test_maximum_loan_amount_rejected(self):

        postings = [self.outbound_hard_settlement(amount=101, denomination="GBP")]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        with self.assertRaises(Rejected) as ex:
            maximum_loan_amount.validate(self.vault, postings=pib, denomination="GBP")
        self.assertEqual(
            ex.exception.message,
            "Cannot create loan larger than maximum loan amount limit of: 100.",
        )

    def test_maximum_loan_amount_ignores_inbound_hard_settlements(self):

        postings = [self.inbound_hard_settlement(amount=101, denomination="GBP")]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        self.assertIsNone(
            maximum_loan_amount.validate(self.vault, postings=pib, denomination="GBP")
        )


class TestMinimumLoanAmount(ContractFeatureTest):
    target_test_file = "library/features/lending/minimum_loan_amount.py"
    side = Tside.ASSET

    def setUp(self) -> None:
        self.vault = self.create_mock(
            minimum_loan_amount=OptionalValue(Decimal(100)), denomination="GBP"
        )

    def test_minimum_loan_amount_accepted(self):

        postings = [self.outbound_hard_settlement(amount=101, denomination="GBP")]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)

        self.assertIsNone(
            minimum_loan_amount.validate(self.vault, postings=pib, denomination="GBP")
        )

    def test_minimum_loan_amount_met(self):

        postings = [self.outbound_hard_settlement(amount=100, denomination="GBP")]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        self.assertIsNone(
            minimum_loan_amount.validate(self.vault, postings=pib, denomination="GBP")
        )

    def test_minimum_loan_amount_rejected(self):

        postings = [self.outbound_hard_settlement(amount=99, denomination="GBP")]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        with self.assertRaises(Rejected) as ex:
            minimum_loan_amount.validate(self.vault, postings=pib, denomination="GBP")
        self.assertEqual(
            ex.exception.message,
            "Cannot create loan smaller than minimum loan amount limit of: 100.",
        )

    def test_minimum_loan_amount_ignores_inbound_hard_settlements(self):

        postings = [self.inbound_hard_settlement(amount=99, denomination="GBP")]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        self.assertIsNone(
            minimum_loan_amount.validate(self.vault, postings=pib, denomination="GBP")
        )
