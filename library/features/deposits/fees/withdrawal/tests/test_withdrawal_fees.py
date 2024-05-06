# standard library
import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import call
from dateutil.relativedelta import relativedelta

# inception imports
from inception_sdk.test_framework.contracts.unit.common import (
    DEFAULT_DENOMINATION,
    ContractFeatureTest,
    Deposit,
    Withdrawal,
)
from inception_sdk.vault.contracts.types_extension import (
    ClientTransaction,
    PostingInstructionBatch,
    Tside,
)
from library.features.deposits.fees.withdrawal import (
    payment_type_flat_fee,
    payment_type_threshold_fee,
    monthly_limit_by_payment_type,
)


def fee_call(amount: Decimal, client_transaction_id: str, instruction_details: dict[str, str]):
    return call(
        amount=amount,
        denomination="GBP",
        client_transaction_id=client_transaction_id,
        from_account_id="Main account",
        from_account_address="DEFAULT",
        to_account_id="PAYMENT_TYPE_FEE_INCOME_ACCOUNT",
        to_account_address="DEFAULT",
        asset="COMMERCIAL_BANK_MONEY",
        override_all_restrictions=True,
        instruction_details=instruction_details,
    )


class TestPaymentTypeFlatFee(ContractFeatureTest):
    target_test_file = "library/features/deposits/fees/withdrawal/payment_type_flat_fee.py"
    side = Tside.LIABILITY

    def setUp(self) -> None:
        payment_type_flat_fee_param = {
            "ATM_MEPS": "1",
            "ATM_VISAPLUS": "12",
        }
        self.vault = self.create_mock(
            payment_type_flat_fee=json.dumps(payment_type_flat_fee_param),
            payment_type_fee_income_account="PAYMENT_TYPE_FEE_INCOME_ACCOUNT",
        )
        return super().setUp()

    def test_payment_type_flat_fee_type_1(self):
        postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=1000, instruction_details={"PAYMENT_TYPE": "ATM_MEPS"}
                )
            ]
        )
        payment_type_flat_fee.get_fees(
            vault=self.vault,
            postings=postings,
            denomination=DEFAULT_DENOMINATION,
        )
        self.vault.make_internal_transfer_instructions.assert_has_calls(
            [
                fee_call(
                    amount=Decimal("1"),
                    client_transaction_id="INTERNAL_POSTING_APPLY_PAYMENT_TYPE_FLAT_FEE_FOR_"
                    "ATM_MEPS_MOCK_HOOK",
                    instruction_details={
                        "description": "payment fee applied for withdrawal using ATM_MEPS",
                        "payment_type": "ATM_MEPS",
                        "event": "APPLY_PAYMENT_TYPE_FLAT_FEE",
                    },
                )
            ]
        )

    def test_payment_type_flat_fee_type_2(self):
        postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=1000, instruction_details={"PAYMENT_TYPE": "ATM_VISAPLUS"}
                )
            ]
        )
        payment_type_flat_fee.get_fees(
            vault=self.vault,
            postings=postings,
            denomination=DEFAULT_DENOMINATION,
        )
        self.vault.make_internal_transfer_instructions.assert_has_calls(
            [
                fee_call(
                    amount=Decimal("12"),
                    client_transaction_id="INTERNAL_POSTING_APPLY_PAYMENT_TYPE_FLAT_FEE_FOR_"
                    "ATM_VISAPLUS_MOCK_HOOK",
                    instruction_details={
                        "description": "payment fee applied for withdrawal using ATM_VISAPLUS",
                        "payment_type": "ATM_VISAPLUS",
                        "event": "APPLY_PAYMENT_TYPE_FLAT_FEE",
                    },
                )
            ]
        )

    def test_payment_type_flat_fee_type_not_known(self):
        postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=1000, instruction_details={"PAYMENT_TYPE": "UNKNOWN"}
                )
            ]
        )
        payment_type_flat_fee.get_fees(
            vault=self.vault,
            postings=postings,
            denomination=DEFAULT_DENOMINATION,
        )
        self.vault.make_internal_transfer_instructions.assert_not_called()

    def test_payment_type_flat_fee_not_applied_to_deposit(self):
        postings = self.mock_posting_instruction_batch(
            posting_instructions=[self.inbound_hard_settlement(amount=1000)]
        )
        payment_type_flat_fee.get_fees(
            vault=self.vault,
            postings=postings,
            denomination=DEFAULT_DENOMINATION,
        )
        self.vault.make_internal_transfer_instructions.assert_not_called()

    def test_payment_type_flat_fee_not_applied_to_deposit_with_payment_type(self):
        postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=1000, instruction_details={"PAYMENT_TYPE": "ATM_VISAPLUS"}
                )
            ]
        )
        payment_type_flat_fee.get_fees(
            vault=self.vault,
            postings=postings,
            denomination=DEFAULT_DENOMINATION,
        )
        self.vault.make_internal_transfer_instructions.assert_not_called()


class TestPaymentTypeThresholdFee(ContractFeatureTest):
    target_test_file = "library/features/deposits/fees/withdrawal/payment_type_threshold_fee.py"
    side = Tside.LIABILITY

    def setUp(self) -> None:
        payment_type_threshold_fee = {
            "DUITNOW_ACC": {"fee": "0.50", "threshold": "4000"},
            "ATM_IBFT_SANS": {"fee": "0.15", "threshold": "5000"},
        }
        self.vault = self.create_mock(
            payment_type_threshold_fee=json.dumps(payment_type_threshold_fee),
            payment_type_fee_income_account="PAYMENT_TYPE_FEE_INCOME_ACCOUNT",
        )
        return super().setUp()

    def test_payment_type_threshold_fee_type_1_exceeded(self):
        postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=4001, instruction_details={"PAYMENT_TYPE": "DUITNOW_ACC"}
                )
            ]
        )
        payment_type_threshold_fee.get_fees(
            vault=self.vault,
            postings=postings,
            denomination=DEFAULT_DENOMINATION,
        )
        self.vault.make_internal_transfer_instructions.assert_has_calls(
            [
                fee_call(
                    amount=Decimal("0.50"),
                    client_transaction_id="INTERNAL_POSTING_APPLY_PAYMENT_TYPE_THRESHOLD_FEE_FOR"
                    "_DUITNOW_ACC_MOCK_HOOK",
                    instruction_details={
                        "description": "payment fee on withdrawal more than 4000 for payment "
                        "using DUITNOW_ACC",
                        "payment_type": "DUITNOW_ACC",
                        "event": "APPLY_PAYMENT_TYPE_THRESHOLD_FEE",
                    },
                )
            ]
        )

    def test_payment_type_threshold_fee_type_1_not_exceeded(self):
        postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=3999, instruction_details={"PAYMENT_TYPE": "DUITNOW_ACC"}
                )
            ]
        )
        payment_type_threshold_fee.get_fees(
            vault=self.vault,
            postings=postings,
            denomination=DEFAULT_DENOMINATION,
        )
        self.vault.make_internal_transfer_instructions.assert_not_called()

    def test_payment_type_threshold_fee_type_1_met(self):
        postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=4000, instruction_details={"PAYMENT_TYPE": "DUITNOW_ACC"}
                )
            ]
        )
        payment_type_threshold_fee.get_fees(
            vault=self.vault,
            postings=postings,
            denomination=DEFAULT_DENOMINATION,
        )
        self.vault.make_internal_transfer_instructions.assert_not_called()

    def test_payment_type_threshold_fee_type_2_exceeded(self):
        postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=5001, instruction_details={"PAYMENT_TYPE": "ATM_IBFT_SANS"}
                )
            ]
        )
        payment_type_threshold_fee.get_fees(
            vault=self.vault,
            postings=postings,
            denomination=DEFAULT_DENOMINATION,
        )
        self.vault.make_internal_transfer_instructions.assert_has_calls(
            [
                fee_call(
                    amount=Decimal("0.15"),
                    client_transaction_id="INTERNAL_POSTING_APPLY_PAYMENT_TYPE_THRESHOLD_FEE_FOR"
                    "_ATM_IBFT_SANS_MOCK_HOOK",
                    instruction_details={
                        "description": "payment fee on withdrawal more than 5000 for payment "
                        "using ATM_IBFT_SANS",
                        "payment_type": "ATM_IBFT_SANS",
                        "event": "APPLY_PAYMENT_TYPE_THRESHOLD_FEE",
                    },
                )
            ]
        )

    def test_payment_type_threshold_fee_type_unknown(self):
        postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=5001, instruction_details={"PAYMENT_TYPE": "UNKNOWN"}
                )
            ]
        )
        payment_type_threshold_fee.get_fees(
            vault=self.vault,
            postings=postings,
            denomination=DEFAULT_DENOMINATION,
        )
        self.vault.make_internal_transfer_instructions.assert_not_called()

    def test_payment_type_threshold_fee_type_ignore_deposit(self):
        postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=5001, instruction_details={"PAYMENT_TYPE": "ATM_IBFT_SANS"}
                )
            ]
        )
        payment_type_threshold_fee.get_fees(
            vault=self.vault,
            postings=postings,
            denomination=DEFAULT_DENOMINATION,
        )
        self.vault.make_internal_transfer_instructions.assert_not_called()


class TestMonthlyLimitByPaymentType(ContractFeatureTest):
    target_test_file = "library/features/deposits/fees/withdrawal/monthly_limit_by_payment_type.py"
    side = Tside.LIABILITY

    def _add_detail_keys_to_all_instructions_in_pib(
        self, pib: PostingInstructionBatch, instruction_details: dict[str, str]
    ) -> PostingInstructionBatch:
        for posting in pib.posting_instructions:
            posting.instruction_details.update(instruction_details)
        return pib

    def _add_detail_keys_to_all_instructions_in_cts(
        self,
        client_transactions: dict[tuple[str, str], ClientTransaction],
        instruction_details: dict[str, str],
    ) -> dict[tuple[str, str], ClientTransaction]:
        for ct in client_transactions.values():
            for posting in ct:
                posting.instruction_details.update(instruction_details)
        return client_transactions

    def setUp(self) -> None:
        self.default_datetime = datetime(2022, 1, 31)
        self.denomination = "GBP"
        maximum_monthly_payment_type_withdrawal_limit = {
            "ATM_ARBM": {"fee": "0.50", "limit": "3"},
        }
        self.vault = self.create_mock(
            maximum_monthly_payment_type_withdrawal_limit=json.dumps(
                maximum_monthly_payment_type_withdrawal_limit
            ),
            payment_type_fee_income_account="PAYMENT_TYPE_FEE_INCOME_ACCOUNT",
        )
        return super().setUp()

    def test_monthly_limit_by_payment_type_exceeded_by_1(self):
        # The monthly limit for payment type ATM_ARBM is 3, expect a charge of 0.50
        transactions = [
            Withdrawal(effective_date=self.default_datetime - timedelta(days=3), amount="1"),
            Withdrawal(effective_date=self.default_datetime - timedelta(days=2), amount="1"),
            Withdrawal(effective_date=self.default_datetime - timedelta(days=1), amount="1"),
            Withdrawal(effective_date=self.default_datetime, amount="1"),
        ]
        pib, client_transactions, _ = self.pib_and_cts_for_transactions(
            hook_effective_date=self.default_datetime, transactions=transactions
        )
        instruction_details = {"PAYMENT_TYPE": "ATM_ARBM"}
        pib = self._add_detail_keys_to_all_instructions_in_pib(pib, instruction_details)
        client_transactions = self._add_detail_keys_to_all_instructions_in_cts(
            client_transactions, instruction_details
        )
        monthly_limit_by_payment_type.get_fees(
            vault=self.vault,
            postings=pib,
            client_transactions=client_transactions,
            effective_date=self.default_datetime,
            denomination=self.denomination,
        )
        self.vault.make_internal_transfer_instructions.assert_has_calls(
            [
                fee_call(
                    amount=Decimal("0.50"),
                    client_transaction_id="INTERNAL_POSTING_APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_"
                    "FEES_MOCK_HOOK",
                    instruction_details={
                        "description": "Total fees charged for limits on payment types: ATM_ARBM "
                        "0.50 GBP",
                        "event": "APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
                    },
                ),
            ]
        )

    def test_monthly_limit_by_payment_type_exceeded_by_2(self):
        # The monthly limit for payment type ATM_ARBM is 3, expect a charge of 1.00
        transactions = [
            Withdrawal(effective_date=self.default_datetime - timedelta(days=3), amount="1"),
            Withdrawal(effective_date=self.default_datetime - timedelta(days=2), amount="1"),
            Withdrawal(effective_date=self.default_datetime - timedelta(days=1), amount="1"),
            Withdrawal(effective_date=self.default_datetime, amount="1"),
            Withdrawal(effective_date=self.default_datetime, amount="1"),
        ]
        pib, client_transactions, _ = self.pib_and_cts_for_transactions(
            hook_effective_date=self.default_datetime, transactions=transactions
        )
        instruction_details = {"PAYMENT_TYPE": "ATM_ARBM"}
        pib = self._add_detail_keys_to_all_instructions_in_pib(pib, instruction_details)
        client_transactions = self._add_detail_keys_to_all_instructions_in_cts(
            client_transactions, instruction_details
        )
        monthly_limit_by_payment_type.get_fees(
            vault=self.vault,
            postings=pib,
            client_transactions=client_transactions,
            effective_date=self.default_datetime,
            denomination=self.denomination,
        )
        self.vault.make_internal_transfer_instructions.assert_has_calls(
            [
                fee_call(
                    amount=Decimal("1.00"),
                    client_transaction_id="INTERNAL_POSTING_APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_"
                    "FEES_MOCK_HOOK",
                    instruction_details={
                        "description": "Total fees charged for limits on payment types: ATM_ARBM "
                        "1.00 GBP",
                        "event": "APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
                    },
                ),
            ]
        )

    def test_monthly_limit_by_payment_type_not_exceeded(self):
        transactions = [
            Withdrawal(effective_date=self.default_datetime - timedelta(days=2), amount="1"),
            Withdrawal(effective_date=self.default_datetime - timedelta(days=1), amount="1"),
            Withdrawal(effective_date=self.default_datetime, amount="1"),
        ]
        pib, client_transactions, _ = self.pib_and_cts_for_transactions(
            hook_effective_date=self.default_datetime, transactions=transactions
        )
        instruction_details = {"PAYMENT_TYPE": "ATM_ARBM"}
        pib = self._add_detail_keys_to_all_instructions_in_pib(pib, instruction_details)
        client_transactions = self._add_detail_keys_to_all_instructions_in_cts(
            client_transactions, instruction_details
        )
        monthly_limit_by_payment_type.get_fees(
            vault=self.vault,
            postings=pib,
            client_transactions=client_transactions,
            effective_date=self.default_datetime,
            denomination=self.denomination,
        )
        self.vault.make_internal_transfer_instructions.assert_not_called()

    def test_monthly_limit_by_payment_type_unknown(self):
        transactions = [
            Withdrawal(effective_date=self.default_datetime - timedelta(days=4), amount="1"),
            Withdrawal(effective_date=self.default_datetime - timedelta(days=3), amount="1"),
            Withdrawal(effective_date=self.default_datetime - timedelta(days=2), amount="1"),
            Withdrawal(effective_date=self.default_datetime - timedelta(days=1), amount="1"),
            Withdrawal(effective_date=self.default_datetime, amount="1"),
        ]
        pib, client_transactions, _ = self.pib_and_cts_for_transactions(
            hook_effective_date=self.default_datetime, transactions=transactions
        )
        instruction_details = {"PAYMENT_TYPE": "UNKNOWN"}
        pib = self._add_detail_keys_to_all_instructions_in_pib(pib, instruction_details)
        client_transactions = self._add_detail_keys_to_all_instructions_in_cts(
            client_transactions, instruction_details
        )
        monthly_limit_by_payment_type.get_fees(
            vault=self.vault,
            postings=pib,
            client_transactions=client_transactions,
            effective_date=self.default_datetime,
            denomination=self.denomination,
        )
        self.vault.make_internal_transfer_instructions.assert_not_called()

    def test_monthly_limit_by_payment_type_only_transactions_this_month(self):
        transactions = [
            Withdrawal(effective_date=self.default_datetime - relativedelta(months=1), amount="1"),
            Withdrawal(effective_date=self.default_datetime - timedelta(days=2), amount="1"),
            Withdrawal(effective_date=self.default_datetime - timedelta(days=1), amount="1"),
            Withdrawal(effective_date=self.default_datetime, amount="1"),
        ]
        pib, client_transactions, _ = self.pib_and_cts_for_transactions(
            hook_effective_date=self.default_datetime, transactions=transactions
        )
        instruction_details = {"PAYMENT_TYPE": "ATM_ARBM"}
        pib = self._add_detail_keys_to_all_instructions_in_pib(pib, instruction_details)
        client_transactions = self._add_detail_keys_to_all_instructions_in_cts(
            client_transactions, instruction_details
        )
        monthly_limit_by_payment_type.get_fees(
            vault=self.vault,
            postings=pib,
            client_transactions=client_transactions,
            effective_date=self.default_datetime,
            denomination=self.denomination,
        )
        self.vault.make_internal_transfer_instructions.assert_not_called()

    def test_monthly_limit_by_payment_type_deposits_ignored(self):
        transactions = [
            Withdrawal(effective_date=self.default_datetime - timedelta(days=3), amount="1"),
            Withdrawal(effective_date=self.default_datetime - timedelta(days=2), amount="1"),
            Deposit(effective_date=self.default_datetime - timedelta(days=1), amount="1"),
            Withdrawal(effective_date=self.default_datetime, amount="1"),
        ]
        pib, client_transactions, _ = self.pib_and_cts_for_transactions(
            hook_effective_date=self.default_datetime, transactions=transactions
        )
        instruction_details = {"PAYMENT_TYPE": "ATM_ARBM"}
        pib = self._add_detail_keys_to_all_instructions_in_pib(pib, instruction_details)
        client_transactions = self._add_detail_keys_to_all_instructions_in_cts(
            client_transactions, instruction_details
        )
        monthly_limit_by_payment_type.get_fees(
            vault=self.vault,
            postings=pib,
            client_transactions=client_transactions,
            effective_date=self.default_datetime,
            denomination=self.denomination,
        )
        self.vault.make_internal_transfer_instructions.assert_not_called()

    def test_monthly_limit_by_payment_type_deposit_ignored_as_current_transaction(self):
        transactions = [
            Withdrawal(effective_date=self.default_datetime - timedelta(days=3), amount="1"),
            Withdrawal(effective_date=self.default_datetime - timedelta(days=2), amount="1"),
            Withdrawal(effective_date=self.default_datetime - timedelta(days=1), amount="1"),
            Deposit(effective_date=self.default_datetime, amount="1"),
        ]
        pib, client_transactions, _ = self.pib_and_cts_for_transactions(
            hook_effective_date=self.default_datetime, transactions=transactions
        )
        instruction_details = {"PAYMENT_TYPE": "ATM_ARBM"}
        pib = self._add_detail_keys_to_all_instructions_in_pib(pib, instruction_details)
        client_transactions = self._add_detail_keys_to_all_instructions_in_cts(
            client_transactions, instruction_details
        )
        monthly_limit_by_payment_type.get_fees(
            vault=self.vault,
            postings=pib,
            client_transactions=client_transactions,
            effective_date=self.default_datetime,
            denomination=self.denomination,
        )
        self.vault.make_internal_transfer_instructions.assert_not_called()
