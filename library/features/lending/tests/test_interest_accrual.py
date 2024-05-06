from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch

# inception imports
from inception_sdk.test_framework.contracts.unit.common import ContractFeatureTest
from inception_sdk.vault.contracts.types_extension import DEFAULT_ASSET
from library.features.lending.interest_accrual import (
    get_accrual_capital,
    get_accrual_posting_instructions,
    get_event_types,
    get_execution_schedules,
    get_accrued_interest,
)

DEFAULT_DATE = datetime(2019, 1, 1)
INTERNAL_CONTRA = "INTERNAL_CONTRA"

ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
ACCRUAL_EVENT = "ACCRUE_INTEREST"
ACCRUED_INTEREST_RECEIVABLE_ADDRESS = "ACCRUED_INTEREST_RECEIVABLE"
NON_EMI_ACCRUED_INTEREST_RECEIVABLE_ADDRESS = "NON_EMI_ACCRUED_INTEREST_RECEIVABLE"


class TestInterestAccrual(ContractFeatureTest):
    target_test_file = "library/features/lending/interest_accrual.py"

    @classmethod
    def setupClass(cls):
        cls.maxDiff = None
        super().setUpClass()

    def test_get_event_types(self):
        expected_tag_id = ["LOAN_ACCRUE_INTEREST_AST"]

        test_cases = [
            {"product_name": "LOAN", "expected_tag_id": expected_tag_id},
            {"product_name": "loan", "expected_tag_id": expected_tag_id},
        ]
        for test_case in test_cases:
            result = get_event_types(test_case["product_name"])[0].scheduler_tag_ids
            self.assertEqual(result, test_case["expected_tag_id"])

    def test_get_execution_schedules(self):
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 9, 1),
            interest_accrual_hour=1,
            interest_accrual_minute=2,
            interest_accrual_second=3,
        )
        actual_schedules = get_execution_schedules(mock_vault)
        expected_schedules = [
            (
                ACCRUAL_EVENT,
                {
                    "hour": "1",
                    "minute": "2",
                    "second": "3",
                },
            ),
        ]
        self.assertEqual(actual_schedules, expected_schedules)

    @patch("library.features.lending.interest_accrual.utils.get_balance_sum")
    def test_get_accrual_capital_default_address(self, mock_get_balance_sum):
        effective_date = datetime(2019, 9, 2, 1, 2, 3)
        mock_vault = self.create_mock()

        get_accrual_capital(mock_vault, effective_date, "GBP")

        mock_get_balance_sum.assert_called_once_with(
            mock_vault,
            ["DEFAULT"],
            denomination="GBP",
            # balance at midnight minus 1 micro second of the effective date
            timestamp=datetime(2019, 9, 1, 23, 59, 59, 999999),
        )

    @patch("library.features.lending.interest_accrual.utils.get_balance_sum")
    def test_get_accrual_capital_specific_address(self, mock_get_balance_sum):
        effective_date = datetime(2019, 9, 2, 5, 4, 2)
        mock_vault = self.create_mock()

        get_accrual_capital(
            mock_vault, effective_date, "GBP", capital_addresses=["some_other_address"]
        )

        mock_get_balance_sum.assert_called_once_with(
            mock_vault,
            ["some_other_address"],
            denomination="GBP",
            # balance at midnight minus 1 micro second of the effective date
            timestamp=datetime(2019, 9, 1, 23, 59, 59, 999999),
        )

    def test_get_accrual_posting_instructions(self):

        mock_formula = Mock(return_value=Decimal("100"))

        mock_vault = self.create_mock(
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )
        # effective date is exactly a month before first due amount calc date
        # so regular interest is accrued
        effective_date = datetime(2020, 1, 5)
        first_due_amount_calc_date = datetime(2020, 2, 5)

        results = get_accrual_posting_instructions(
            mock_vault,
            effective_date,
            "GBP",
            first_due_amount_calc_date,
            mock_formula,
            accrual_capital=Decimal(1000),
        )

        self.assertEqual(len(results), 1)
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("100"),
            denomination="GBP",
            client_transaction_id="ACCRUE_INTEREST_MOCK_HOOK_GBP",
            from_account_id=mock_vault.account_id,
            from_account_address=ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
            to_account_id=mock_vault.account_id,
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            instruction_details={
                "description": "Daily interest accrued on balance of 1000",
                "event": ACCRUAL_EVENT,
            },
            override_all_restrictions=True,
        )

    def test_get_accrual_posting_instructions_when_extra_interest(self):

        mock_formula = Mock(return_value=Decimal("100"))

        mock_vault = self.create_mock(
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )
        # effective date is before a month before first due amount calc date
        # so non-emi interest is accrued
        effective_date = datetime(2020, 1, 4)
        first_due_amount_calc_date = datetime(2020, 2, 5)

        results = get_accrual_posting_instructions(
            mock_vault,
            effective_date,
            "GBP",
            first_due_amount_calc_date,
            mock_formula,
            accrual_capital=Decimal(1000),
        )

        self.assertEqual(len(results), 1)
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("100"),
            denomination="GBP",
            client_transaction_id="ACCRUE_INTEREST_MOCK_HOOK_GBP",
            from_account_id=mock_vault.account_id,
            from_account_address=NON_EMI_ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
            to_account_id=mock_vault.account_id,
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            instruction_details={
                "description": "Daily interest accrued on balance of 1000",
                "event": ACCRUAL_EVENT,
            },
            override_all_restrictions=True,
        )

    def test_get_accrual_posting_instructions_0_accrual(self):

        mock_formula = Mock(return_value=Decimal("0"))
        mock_vault = self.create_mock()

        results = get_accrual_posting_instructions(
            mock_vault,
            DEFAULT_DATE,
            "GBP",
            DEFAULT_DATE,
            mock_formula,
            accrual_capital=Decimal("0"),
        )

        self.assertEqual(len(results), 0)
        mock_vault.make_internal_transfer_instructions.assert_not_called()

    @patch("library.features.lending.interest_accrual.utils.get_balance_sum")
    def test_get_accrued_interest(self, mock_get_balance_sum):
        mock_get_balance_sum.return_value = Decimal("100")
        mock_vault = self.create_mock()

        interest = get_accrued_interest(mock_vault)

        self.assertEqual(interest, Decimal("100"))

    @patch("library.features.lending.interest_accrual.utils.get_balance_sum")
    def test_get_accrued_interest_at(self, mock_get_balance_sum):
        mock_get_balance_sum.return_value = Decimal("100")
        mock_vault = self.create_mock()

        interest = get_accrued_interest(mock_vault, DEFAULT_DATE)

        self.assertEqual(interest, Decimal("100"))

        mock_get_balance_sum.assert_called_once_with(
            mock_vault, [ACCRUED_INTEREST_RECEIVABLE_ADDRESS], timestamp=DEFAULT_DATE
        )
