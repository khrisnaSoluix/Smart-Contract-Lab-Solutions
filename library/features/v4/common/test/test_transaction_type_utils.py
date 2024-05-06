# standard libs
from decimal import Decimal

# features
import library.features.v4.common.transaction_type_utils as transaction_type_utils

# contracts api
from contracts_api import (
    AuthorisationAdjustment,
    CustomInstruction,
    InboundAuthorisation,
    InboundHardSettlement,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Release,
    Settlement,
    Transfer,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AdjustmentAmount,
    Tside,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelPosting,
)


class TestTransactionUtils(FeatureTest):
    tside = Tside.LIABILITY


class TestMatchTransactionType(TestTransactionUtils):
    def test_match_single_transaction_type(self):
        types_to_match = ["atm"]
        transaction_type = "atm"
        expected_match = True

        instruction = CustomInstruction(
            postings=[SentinelPosting("posting")],
            override_all_restrictions=True,
            instruction_details={
                "description": "Move outstanding due debt into overdue debt.",
                "type": transaction_type,
            },
        )

        match_result = transaction_type_utils.match_transaction_type(
            posting_instruction=instruction, values=types_to_match
        )

        self.assertEqual(expected_match, match_result)

    def test_match_single_transaction_type_unmatched(self):
        types_to_match = ["atm"]
        transaction_type = "pos"
        expected_match = False

        instruction = CustomInstruction(
            postings=[SentinelPosting("posting")],
            override_all_restrictions=True,
            instruction_details={
                "description": "Some Description",
                "type": transaction_type,
            },
        )

        match_result = transaction_type_utils.match_transaction_type(
            posting_instruction=instruction, values=types_to_match
        )

        self.assertEqual(expected_match, match_result)

    def test_unmatched_transaction_type_in_selection(self):
        types_to_match = ["abv", "123", "xyz"]
        transaction_type = "atm"
        expected_match = False

        instruction = CustomInstruction(
            postings=[SentinelPosting("posting")],
            override_all_restrictions=True,
            instruction_details={
                "description": "Some Description",
                "type": transaction_type,
            },
        )

        match_result = transaction_type_utils.match_transaction_type(
            posting_instruction=instruction, values=types_to_match
        )

        self.assertEqual(expected_match, match_result)

    def test_matched_transaction_type_in_selection(self):
        types_to_match = ["atm", "pos", "direct_debit"]
        transaction_type = "atm"
        expected_match = True

        instruction = CustomInstruction(
            postings=[SentinelPosting("posting")],
            override_all_restrictions=True,
            instruction_details={
                "description": "Some Description",
                "type": transaction_type,
            },
        )

        match_result = transaction_type_utils.match_transaction_type(
            posting_instruction=instruction, values=types_to_match
        )

        self.assertEqual(expected_match, match_result)


class TestMatchTransactionTypeAliases(TestTransactionUtils):
    def test_posting_instruction_type_AuthorisationAdjustment(self):
        types_to_match = ["atm"]
        transaction_type = "atm"
        expected_match = True

        instruction = AuthorisationAdjustment(
            adjustment_amount=AdjustmentAmount(amount=Decimal("10")),
            client_transaction_id="id",
            override_all_restrictions=True,
            instruction_details={
                "description": "Move outstanding due debt into overdue debt.",
                "type": transaction_type,
            },
        )

        match_result = transaction_type_utils.match_transaction_type(
            posting_instruction=instruction, values=types_to_match
        )

        self.assertEqual(expected_match, match_result)

    def test_posting_instruction_type_CustomInstruction(self):
        types_to_match = ["atm"]
        transaction_type = "atm"
        expected_match = True

        instruction = CustomInstruction(
            postings=[SentinelPosting("")],
            instruction_details={
                "description": "Move outstanding due debt into overdue debt.",
                "type": transaction_type,
            },
        )

        match_result = transaction_type_utils.match_transaction_type(
            posting_instruction=instruction, values=types_to_match
        )

        self.assertEqual(expected_match, match_result)

    def test_posting_instruction_type_InboundAuthorisation(self):
        types_to_match = ["atm"]
        transaction_type = "atm"
        expected_match = True

        instruction = InboundAuthorisation(
            amount=Decimal("10"),
            client_transaction_id="id",
            denomination="GBP",
            target_account_id="id",
            internal_account_id="id",
            instruction_details={
                "description": "Move outstanding due debt into overdue debt.",
                "type": transaction_type,
            },
        )

        match_result = transaction_type_utils.match_transaction_type(
            posting_instruction=instruction, values=types_to_match
        )

        self.assertEqual(expected_match, match_result)

    def test_posting_instruction_type_InboundHardSettlement(self):
        types_to_match = ["atm"]
        transaction_type = "atm"
        expected_match = True

        instruction = InboundHardSettlement(
            amount=Decimal("10"),
            denomination="GBP",
            target_account_id="id",
            internal_account_id="id",
            instruction_details={
                "description": "Move outstanding due debt into overdue debt.",
                "type": transaction_type,
            },
        )

        match_result = transaction_type_utils.match_transaction_type(
            posting_instruction=instruction, values=types_to_match
        )

        self.assertEqual(expected_match, match_result)

    def test_posting_instruction_type_OutboundAuthorisation(self):
        types_to_match = ["atm"]
        transaction_type = "atm"
        expected_match = True

        instruction = OutboundAuthorisation(
            client_transaction_id="id",
            amount=Decimal("10"),
            denomination="GBP",
            target_account_id="id",
            internal_account_id="id",
            instruction_details={
                "description": "Move outstanding due debt into overdue debt.",
                "type": transaction_type,
            },
        )

        match_result = transaction_type_utils.match_transaction_type(
            posting_instruction=instruction, values=types_to_match
        )

        self.assertEqual(expected_match, match_result)

    def test_posting_instruction_type_OutboundHardSettlement(self):
        types_to_match = ["atm"]
        transaction_type = "atm"
        expected_match = True

        instruction = OutboundHardSettlement(
            amount=Decimal("10"),
            denomination="GBP",
            target_account_id="id",
            internal_account_id="id",
            instruction_details={
                "description": "Move outstanding due debt into overdue debt.",
                "type": transaction_type,
            },
        )

        match_result = transaction_type_utils.match_transaction_type(
            posting_instruction=instruction, values=types_to_match
        )

        self.assertEqual(expected_match, match_result)

    def test_posting_instruction_type_Release(self):
        types_to_match = ["atm"]
        transaction_type = "atm"
        expected_match = True

        instruction = Release(
            client_transaction_id="id",
            instruction_details={
                "description": "Move outstanding due debt into overdue debt.",
                "type": transaction_type,
            },
        )

        match_result = transaction_type_utils.match_transaction_type(
            posting_instruction=instruction, values=types_to_match
        )

        self.assertEqual(expected_match, match_result)

    def test_posting_instruction_type_Settlement(self):
        types_to_match = ["atm"]
        transaction_type = "atm"
        expected_match = True

        instruction = Settlement(
            client_transaction_id="id",
            instruction_details={
                "description": "Move outstanding due debt into overdue debt.",
                "type": transaction_type,
            },
        )

        match_result = transaction_type_utils.match_transaction_type(
            posting_instruction=instruction, values=types_to_match
        )

        self.assertEqual(expected_match, match_result)

    def test_posting_instruction_type_Transfer(self):
        types_to_match = ["atm"]
        transaction_type = "atm"
        expected_match = True

        instruction = Transfer(
            amount=Decimal("1"),
            creditor_target_account_id="id",
            denomination="GBP",
            debtor_target_account_id="id",
            instruction_details={
                "description": "Move outstanding due debt into overdue debt.",
                "type": transaction_type,
            },
        )

        match_result = transaction_type_utils.match_transaction_type(
            posting_instruction=instruction, values=types_to_match
        )

        self.assertEqual(expected_match, match_result)
