# standard library
from datetime import timedelta
from decimal import Decimal
import json
from typing import Union
import unittest

# inception imports
from inception_sdk.test_framework.contracts.unit.common import (
    Deposit,
    Withdrawal,
)
from inception_sdk.vault.contracts.types_extension import (
    ClientTransaction,
    PostingInstructionBatch,
    Rejected,
    Vault,
)
from library.features.deposits.transaction_limits.common.test_utils import (
    TransactionLimitFeatureTest,
)
from library.features.deposits.transaction_limits.withdrawal_limits import (
    maximum_daily_withdrawal,
    maximum_daily_withdrawal_by_category,
    maximum_single_withdrawal,
    maximum_withdrawal_by_payment_type,
    minimum_balance_by_tier,
    minimum_single_withdrawal,
)


class WithdrawalFeatureTest(TransactionLimitFeatureTest):
    def default_withdrawal_pib(
        self, amount: Union[Decimal, str, int], **kwargs
    ) -> PostingInstructionBatch:
        return self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=amount, value_timestamp=self.EOD_DATETIME, **kwargs
                )
            ]
        )


class TestMaximumDailyWithdrawal(WithdrawalFeatureTest):
    target_test_file = (
        "library/features/deposits/transaction_limits/withdrawal_limits/maximum_daily_withdrawal.py"
    )

    def test_non_net_withdrawal_limit_not_exceeded(self):
        # the proposed transaction is -ve but is not hitting the daily limit of (-100)
        transactions = [
            Withdrawal(effective_date=self.EOD_DATETIME - timedelta(minutes=1), amount="40"),
            Withdrawal(effective_date=self.EOD_DATETIME, amount="50"),
        ]
        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=False,
            )
        )

    def test_non_net_withdrawal_limit_exceeded(self):
        # the proposed transaction is -ve and is causing the limit (-100) to be exceeded
        transactions = [
            Withdrawal(effective_date=self.EOD_DATETIME - timedelta(minutes=1), amount="60"),
            Withdrawal(effective_date=self.EOD_DATETIME, amount="50"),
        ]
        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        with self.assertRaises(Rejected) as ex:
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=False,
            )
        self.assertEqual(
            ex.exception.message,
            "PIB would cause the maximum daily withdrawal limit of 100 GBP to be " "exceeded.",
        )

    def test_non_net_withdrawal_limit_met(self):
        # the proposed transaction is -ve but is only meeting the daily limit (-100)
        transactions = [
            Withdrawal(effective_date=self.EOD_DATETIME - timedelta(minutes=1), amount="80"),
            Withdrawal(effective_date=self.EOD_DATETIME, amount="20"),
        ]
        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=False,
            )
        )

    def test_non_net_withdrawal_ignore_deposit_only_batches(self):
        # When net_batch=False, deposits should always be accepted even if the previous withdrawals
        # are over the limit.
        transactions = [
            Withdrawal(effective_date=self.EOD_DATETIME - timedelta(minutes=1), amount="110"),
            Deposit(effective_date=self.EOD_DATETIME, amount="50"),
        ]
        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=False,
            )
        )

    def test_posting_net_negative_withdrawal_limit_not_exceeded(self):
        # the proposed transaction's net is -ve but is not hitting the daily limit of (-100)
        transactions = [
            Deposit(effective_date=self.EOD_DATETIME - timedelta(minutes=1), amount="101"),
            Withdrawal(effective_date=self.EOD_DATETIME, amount="50"),
        ]
        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_posting_net_negative_withdrawal_limit_exceeded(self):
        # the proposed transaction's net is -ve and has exceeded the daily limit (-100)
        transactions = [
            Deposit(effective_date=self.EOD_DATETIME - timedelta(minutes=1), amount="101"),
            Withdrawal(effective_date=self.EOD_DATETIME, amount="150"),
        ]
        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        with self.assertRaises(Rejected) as ex:
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        self.assertEqual(
            ex.exception.message,
            "PIB would cause the maximum daily withdrawal limit of 100 GBP to be " "exceeded.",
        )

    def test_posting_net_negative_withdrawal_limit_met(self):
        # the proposed transaction's net is -ve but is only meeting the daily limit (-100)
        transactions = [
            Deposit(effective_date=self.EOD_DATETIME - timedelta(minutes=1), amount="101"),
            Withdrawal(effective_date=self.EOD_DATETIME, amount="100"),
        ]
        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_posting_net_positive_proposed_outbound_inbound_auths(self):
        # As the net of the two proposed transactions is positive, the batch should be
        # accepted even though the total withdrawal amount is higher than the limit
        transactions = [
            [
                self.outbound_auth(
                    amount=Decimal("100"),
                    value_timestamp=self.EOD_DATETIME - timedelta(minutes=4),
                    **{"client_transaction_id": "initial_outbound_auth"},
                ),
            ],
            [
                self.inbound_auth(
                    amount=Decimal("30"),
                    value_timestamp=self.EOD_DATETIME,
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
            ],
            [
                self.outbound_auth(
                    amount=Decimal("20"),
                    value_timestamp=self.EOD_DATETIME,
                    **{"client_transaction_id": "second_outbound_auth"},
                ),
            ],
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_posting_instructions(self.EOD_DATETIME, transactions)

        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_withdrawal_limit_already_exceeded_batch_inbound_accepted(self):
        # The daily withdrawal limit has been exceeded but the proposed inbound auth should
        # be accepted.
        transactions = [
            [
                self.outbound_auth(
                    amount=Decimal("130"),
                    value_timestamp=self.EOD_DATETIME - timedelta(minutes=4),
                    **{"client_transaction_id": "initial_outbound_auth"},
                ),
            ],
            [
                self.inbound_auth(
                    amount=Decimal("20"),
                    value_timestamp=self.EOD_DATETIME,
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
            ],
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_posting_instructions(self.EOD_DATETIME, transactions)

        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_withdrawal_limit_already_exceeded_batch_net_positive_accepted(self):
        # The daily withdrawal limit has been exceeded and the proposed posting batch
        # includes another outbound auth. As the net of the batch is positive, the batch
        # should be accepted.
        transactions = [
            [
                self.outbound_auth(
                    amount=Decimal("130"),
                    value_timestamp=self.EOD_DATETIME - timedelta(minutes=4),
                    **{"client_transaction_id": "initial_outbound_auth"},
                ),
            ],
            [
                self.inbound_auth(
                    amount=Decimal("20"),
                    value_timestamp=self.EOD_DATETIME,
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
            ],
            [
                self.outbound_auth(
                    amount=Decimal("5"),
                    value_timestamp=self.EOD_DATETIME,
                    **{"client_transaction_id": "second_outbound_auth"},
                ),
            ],
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_posting_instructions(self.EOD_DATETIME, transactions)

        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_maximum_daily_withdrawal_net_batch_ignore_single_deposit_transactions(self):
        # Deposit transactions should be ignored when they are the only proposed posting
        # as they do not count towards the daily limit
        transactions = [
            Deposit(effective_date=self.EOD_DATETIME, amount="101"),
        ]
        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_maximum_daily_withdrawal_chainable_auth_settlement(self):
        # check that a settlement is accepted up to the amount of the original auth
        # even if that auth was over the limit (the net of the batch is 0 as the 110
        # was accounted for in the original auth)
        transactions = [
            [
                self.outbound_auth(
                    amount=Decimal("110"),
                    value_timestamp=self.EOD_DATETIME - timedelta(minutes=4),
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
                self.settle_outbound_auth(
                    unsettled_amount=Decimal("110"),
                    amount=Decimal("110"),
                    value_timestamp=self.EOD_DATETIME,
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
            ],
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_posting_instructions(self.EOD_DATETIME, transactions)

        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_maximum_daily_withdrawal_chainable_auth_oversettlement(self):
        # check that an oversettlement (settlement > auth) is rejected if the oversettlement
        # amount exceeds the deposit limit (this oversettlement is impacting the total withdrawn
        # amount by -20)

        transactions = [
            [
                self.outbound_auth(
                    amount=Decimal("90"),
                    value_timestamp=self.EOD_DATETIME - timedelta(minutes=4),
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
                self.settle_outbound_auth(
                    unsettled_amount=Decimal("90"),
                    amount=Decimal("110"),
                    value_timestamp=self.EOD_DATETIME,
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
            ],
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_posting_instructions(self.EOD_DATETIME, transactions)

        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        with self.assertRaises(Rejected) as ex:
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        self.assertEqual(
            ex.exception.message,
            "PIB would cause the maximum daily withdrawal limit of 100 GBP to be exceeded.",
        )

    def test_maximum_daily_withdrawal_chainable_auth_release(self):
        # want to check that a release is always accepted even if the original
        # auth was over the limit
        transactions = [
            [
                self.outbound_auth(
                    amount=Decimal("110"),
                    value_timestamp=self.EOD_DATETIME - timedelta(minutes=4),
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
                self.release_outbound_auth(
                    unsettled_amount=Decimal("110"),
                    amount=Decimal("110"),
                    value_timestamp=self.EOD_DATETIME,
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
            ],
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_posting_instructions(self.EOD_DATETIME, transactions)

        vault = self.create_mock(
            maximum_daily_withdrawal=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_withdrawal.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )


class TestMaximumDailyWithdrawalByCategory(WithdrawalFeatureTest):
    target_test_file = (
        "library/features/deposits/transaction_limits/withdrawal_limits/"
        "maximum_daily_withdrawal_by_category.py"
    )

    def setUp(self) -> None:
        self.instruction_detail_key = "WITHDRAWAL_TYPE"
        return super().setUp()

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
    ) -> PostingInstructionBatch:
        for ct in client_transactions.values():
            for posting in ct:
                posting.instruction_details.update(instruction_details)
        return client_transactions

    def test_maximum_daily_withdrawal_by_category_ignore_deposits(self):
        # Ensure that deposit transactions are ignored
        transactions = [
            Deposit(effective_date=self.EOD_DATETIME - timedelta(minutes=1), amount="101"),
            Withdrawal(effective_date=self.EOD_DATETIME, amount="50"),
        ]
        pib, client_transactions, _ = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        instruction_details = {self.instruction_detail_key: "ATM"}
        pib = self._add_detail_keys_to_all_instructions_in_pib(pib, instruction_details)
        client_transactions = self._add_detail_keys_to_all_instructions_in_cts(
            client_transactions, instruction_details
        )
        limit_mapping = {"ATM": "100"}
        self.assertIsNone(
            maximum_daily_withdrawal_by_category.validate(
                limit_mapping=limit_mapping,
                instruction_detail_key=self.instruction_detail_key,
                postings=pib,
                client_transactions=client_transactions,
                effective_date=self.EOD_DATETIME,
                denomination=self.default_denom,
            )
        )

    def test_maximum_daily_withdrawal_by_category_exceeded(self):
        # Existing previous ATM withdrawal of 50 so a further withdrawal of 51 will breach the
        # 100 limit
        transactions = [
            Withdrawal(effective_date=self.EOD_DATETIME - timedelta(minutes=1), amount="50"),
            Withdrawal(effective_date=self.EOD_DATETIME, amount="51"),
        ]
        pib, client_transactions, _ = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        instruction_details = {self.instruction_detail_key: "ATM"}
        pib = self._add_detail_keys_to_all_instructions_in_pib(pib, instruction_details)
        client_transactions = self._add_detail_keys_to_all_instructions_in_cts(
            client_transactions, instruction_details
        )
        limit_mapping = {"ATM": "100"}
        with self.assertRaises(Rejected) as ex:
            maximum_daily_withdrawal_by_category.validate(
                limit_mapping=limit_mapping,
                instruction_detail_key=self.instruction_detail_key,
                postings=pib,
                client_transactions=client_transactions,
                effective_date=self.EOD_DATETIME,
                denomination=self.default_denom,
            )
        self.assertEqual(
            ex.exception.message,
            "Transaction would cause the maximum ATM payment limit of 100 GBP to be exceeded.",
        )


class TestMaximumSingleWithdrawal(WithdrawalFeatureTest):
    target_test_file = (
        "library/features/deposits/transaction_limits/withdrawal_limits/"
        "maximum_single_withdrawal.py"
    )

    def setUp(self) -> None:
        self.vault = self.create_mock(maximum_withdrawal=Decimal(100))
        return super().setUp()

    def test_maximum_single_withdrawal_ignore_deposit(self):
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.inbound_hard_settlement(amount=1000)]
        )
        self.assertIsNone(
            maximum_single_withdrawal.validate(vault=self.vault, postings=pib, denomination="GBP")
        )

    def test_maximum_single_withdrawal_exceeded(self):
        pib = self.default_withdrawal_pib(101)
        with self.assertRaises(Rejected) as ex:
            maximum_single_withdrawal.validate(vault=self.vault, postings=pib, denomination="GBP")
        self.assertEqual(
            ex.exception.message,
            "Transaction amount 101 GBP is greater than the maximum withdrawal amount 100 GBP.",
        )

    def test_maximum_single_withdrawal_not_exceeded(self):
        pib = self.default_withdrawal_pib(99)
        self.assertIsNone(
            maximum_single_withdrawal.validate(vault=self.vault, postings=pib, denomination="GBP")
        )

    def test_maximum_single_withdrawal_met(self):
        pib = self.default_withdrawal_pib(100)
        self.assertIsNone(
            maximum_single_withdrawal.validate(vault=self.vault, postings=pib, denomination="GBP")
        )


class TestMaximumWithdrawalByPaymentType(WithdrawalFeatureTest):
    target_test_file = (
        "library/features/deposits/transaction_limits/withdrawal_limits/"
        "maximum_withdrawal_by_payment_type.py"
    )

    def setUp(self) -> None:
        self.vault = self.create_mock(
            maximum_payment_type_withdrawal=json.dumps(
                {
                    "PAYMENT_TYPE_1": "100",
                    "PAYMENT_TYPE_2": "200",
                }
            )
        )
        return super().setUp()

    def test_maximum_withdrawal_by_payment_type_ignore_deposit(self):
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=1000, instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_1"}
                )
            ]
        )
        self.assertIsNone(
            maximum_withdrawal_by_payment_type.validate(
                vault=self.vault, postings=pib, denomination="GBP"
            )
        )

    def test_maximum_withdrawal_by_payment_type_1_exceeded(self):
        pib = self.default_withdrawal_pib(
            101, instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_1"}
        )
        with self.assertRaises(Rejected) as ex:
            maximum_withdrawal_by_payment_type.validate(
                vault=self.vault, postings=pib, denomination="GBP"
            )
        self.assertEqual(
            ex.exception.message,
            "Transaction amount 101.00 GBP is more than the maximum withdrawal amount 100 GBP "
            "allowed for the the payment type PAYMENT_TYPE_1.",
        )

    def test_maximum_withdrawal_by_payment_type_1_not_exceeded(self):
        pib = self.default_withdrawal_pib(
            99, instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_1"}
        )
        self.assertIsNone(
            maximum_withdrawal_by_payment_type.validate(
                vault=self.vault, postings=pib, denomination="GBP"
            )
        )

    def test_maximum_withdrawal_by_payment_type_1_met(self):
        pib = self.default_withdrawal_pib(
            100, instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_1"}
        )
        self.assertIsNone(
            maximum_withdrawal_by_payment_type.validate(
                vault=self.vault, postings=pib, denomination="GBP"
            )
        )

    def test_maximum_withdrawal_by_payment_type_2_exceeded(self):
        pib = self.default_withdrawal_pib(
            201, instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_2"}
        )
        with self.assertRaises(Rejected) as ex:
            maximum_withdrawal_by_payment_type.validate(
                vault=self.vault, postings=pib, denomination="GBP"
            )
        self.assertEqual(
            ex.exception.message,
            "Transaction amount 201.00 GBP is more than the maximum withdrawal amount 200 GBP "
            "allowed for the the payment type PAYMENT_TYPE_2.",
        )

    def test_maximum_withdrawal_by_payment_type_2_not_exceeded(self):
        pib = self.default_withdrawal_pib(
            199, instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_2"}
        )
        self.assertIsNone(
            maximum_withdrawal_by_payment_type.validate(
                vault=self.vault, postings=pib, denomination="GBP"
            )
        )

    def test_maximum_withdrawal_by_payment_type_2_met(self):
        pib = self.default_withdrawal_pib(
            200, instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_2"}
        )
        self.assertIsNone(
            maximum_withdrawal_by_payment_type.validate(
                vault=self.vault, postings=pib, denomination="GBP"
            )
        )


class TestMinimumBalanceByTier(WithdrawalFeatureTest):
    target_test_file = (
        "library/features/deposits/transaction_limits/withdrawal_limits/minimum_balance_by_tier.py"
    )

    def _mock_vault_with_account_tier(self, account_tier: str) -> Vault:
        account_tiers = ["STANDARD", "SAVINGS"]
        tiered_minimum_balance_threshold = {
            "STANDARD": "0",
            "SAVINGS": "100",
        }
        return self.create_mock(
            account_tier_names=json.dumps(account_tiers),
            tiered_minimum_balance_threshold=json.dumps(tiered_minimum_balance_threshold),
            flags=[account_tier],
        )

    def test_account_tier_minimum_balance_exceeded(self):
        # Current balance is 100 so any withdrawal should be rejected for SAVINGS account
        postings = self.default_withdrawal_pib(1)
        balances = self.default_balances(100)
        vault = self._mock_vault_with_account_tier("SAVINGS")
        with self.assertRaises(Rejected) as ex:
            minimum_balance_by_tier.validate(
                vault=vault,
                postings=postings,
                balances=balances,
                denomination=self.default_denom,
            )
        self.assertEqual(
            ex.exception.message,
            "Transaction amount -1 GBP will result in the account balance falling below the minimum"
            " permitted of 100 GBP.",
        )

    def test_account_tier_minimum_balance_not_exceeded(self):
        # Current balance is 100 so a withdrawal up to 100 should be permitted on a STANDARD account
        postings = self.default_withdrawal_pib(99)
        balances = self.default_balances(100)
        vault = self._mock_vault_with_account_tier("STANDARD")
        self.assertIsNone(
            minimum_balance_by_tier.validate(
                vault=vault,
                postings=postings,
                balances=balances,
                denomination=self.default_denom,
            )
        )

    def test_account_tier_minimum_balance_exceeded_below_zero(self):
        # Current balance is 100 so a withdrawal over 100 should be rejected on a STANDARD account
        postings = self.default_withdrawal_pib(101)
        balances = self.default_balances(100)
        vault = self._mock_vault_with_account_tier("STANDARD")
        with self.assertRaises(Rejected) as ex:
            minimum_balance_by_tier.validate(
                vault=vault,
                postings=postings,
                balances=balances,
                denomination=self.default_denom,
            )
        self.assertEqual(
            ex.exception.message,
            "Transaction amount -101 GBP will result in the account balance falling below the "
            "minimum permitted of 0 GBP.",
        )


class TestMinimumSingleWithdrawal(WithdrawalFeatureTest):
    target_test_file = (
        "library/features/deposits/transaction_limits/withdrawal_limits/"
        "minimum_single_withdrawal.py"
    )

    def setUp(self) -> None:
        self.vault = self.create_mock(minimum_withdrawal=Decimal("0.01"))
        return super().setUp()

    def test_minimum_single_withdrawal_ignore_deposit(self):
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("0.001"))]
        )
        self.assertIsNone(
            minimum_single_withdrawal.validate(vault=self.vault, postings=pib, denomination="GBP")
        )

    def test_minimum_single_withdrawal_not_met(self):
        pib = self.default_withdrawal_pib(Decimal("0.001"))
        with self.assertRaises(Rejected) as ex:
            minimum_single_withdrawal.validate(vault=self.vault, postings=pib, denomination="GBP")
        self.assertEqual(
            ex.exception.message,
            "Transaction amount 0.001 GBP is less than the minimum withdrawal amount 0.01 GBP.",
        )

    def test_minimum_single_withdrawal_exceeded(self):
        pib = self.default_withdrawal_pib(Decimal("0.02"))
        self.assertIsNone(
            minimum_single_withdrawal.validate(vault=self.vault, postings=pib, denomination="GBP")
        )

    def test_minimum_single_withdrawal_met(self):
        pib = self.default_withdrawal_pib(Decimal("0.01"))
        self.assertIsNone(
            minimum_single_withdrawal.validate(vault=self.vault, postings=pib, denomination="GBP")
        )


if __name__ == "__main__":
    unittest.main()
