# standard library
from datetime import timedelta
from decimal import Decimal
from typing import Union

# inception imports
from inception_sdk.vault.contracts.types_extension import (
    PostingInstructionBatch,
    Rejected,
)
from inception_sdk.test_framework.contracts.unit.common import (
    DEFAULT_DENOMINATION,
    Deposit,
    Withdrawal,
)
from library.features.deposits.transaction_limits.deposit_limits import (
    maximum_balance_limit,
    maximum_daily_deposit,
    maximum_single_deposit,
    minimum_initial_deposit,
    minimum_single_deposit,
)
from library.features.deposits.transaction_limits.common.test_utils import (
    TransactionLimitFeatureTest,
)


class DepositFeatureTest(TransactionLimitFeatureTest):
    def default_deposit_pib(self, amount: Union[Decimal, str, int]) -> PostingInstructionBatch:
        return self.mock_posting_instruction_batch(
            posting_instructions=[
                self.inbound_hard_settlement(amount=amount, value_timestamp=self.EOD_DATETIME)
            ]
        )


class TestMaximumBalanceLimit(DepositFeatureTest):
    target_test_file = (
        "library/features/deposits/transaction_limits/deposit_limits/maximum_balance_limit.py"
    )

    def setUp(self) -> None:
        self.vault = self.create_mock(maximum_balance=Decimal(100))
        return super().setUp()

    def test_maximum_balance_limit_ignore_withdrawal(self):
        postings = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_hard_settlement(amount=1000)]
        )
        balances = self.init_balances(balance_defs=[{"net": "0"}])[0][1]
        self.assertIsNone(
            maximum_balance_limit.validate(
                vault=self.vault,
                postings=postings,
                balances=balances,
                denomination=DEFAULT_DENOMINATION,
            )
        )

    def test_maximum_balance_limit_exceeded(self):
        postings = self.default_deposit_pib(amount=101)
        balances = self.default_balances(0)
        with self.assertRaises(Rejected) as ex:
            maximum_balance_limit.validate(
                vault=self.vault,
                postings=postings,
                balances=balances,
                denomination=DEFAULT_DENOMINATION,
            )
        self.assertEqual(
            ex.exception.message, "Posting would exceed maximum permitted balance 100 GBP."
        )

    def test_maximum_balance_limit_not_exceeded(self):
        postings = self.default_deposit_pib(amount=99)
        balances = self.default_balances(0)
        self.assertIsNone(
            maximum_balance_limit.validate(
                vault=self.vault,
                postings=postings,
                balances=balances,
                denomination=DEFAULT_DENOMINATION,
            )
        )

    def test_maximum_balance_limit_exceeded_already_over(self):
        postings = self.default_deposit_pib(amount=1)
        balances = self.default_balances(amount=101)
        with self.assertRaises(Rejected) as ex:
            maximum_balance_limit.validate(
                vault=self.vault,
                postings=postings,
                balances=balances,
                denomination=DEFAULT_DENOMINATION,
            )
        self.assertEqual(
            ex.exception.message, "Posting would exceed maximum permitted balance 100 GBP."
        )


class TestMaximumSingleDepositLimit(DepositFeatureTest):
    target_test_file = (
        "library/features/deposits/transaction_limits/deposit_limits/maximum_single_deposit.py"
    )

    def setUp(self) -> None:
        self.vault = self.create_mock(maximum_deposit=Decimal(10))
        return super().setUp()

    def test_maximum_single_deposit_ignore_withdrawal(self):
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_hard_settlement(1000)]
        )
        self.assertIsNone(
            maximum_single_deposit.validate(vault=self.vault, postings=pib, denomination="GBP")
        )

    def test_maximum_single_deposit_exceeded(self):
        pib = self.default_deposit_pib(amount=11)
        with self.assertRaises(Rejected) as ex:
            maximum_single_deposit.validate(vault=self.vault, postings=pib, denomination="GBP")
        self.assertEqual(
            ex.exception.message,
            "Transaction amount 11 GBP is more than the maximum permitted deposit amount 10 GBP.",
        )

    def test_maximum_single_deposit_met(self):
        pib = self.default_deposit_pib(amount=10)
        self.assertIsNone(
            maximum_single_deposit.validate(vault=self.vault, postings=pib, denomination="GBP")
        )

    def test_maximum_single_deposit_not_exceeded(self):
        pib = self.default_deposit_pib(amount=9)
        self.assertIsNone(
            maximum_single_deposit.validate(vault=self.vault, postings=pib, denomination="GBP")
        )


class TestMinimumInitialDeposit(DepositFeatureTest):
    target_test_file = (
        "library/features/deposits/transaction_limits/deposit_limits/minimum_initial_deposit.py"
    )

    def setUp(self) -> None:
        self.vault = self.create_mock(minimum_initial_deposit=Decimal(20))
        self.zero_balance = self.default_balances(0)
        return super().setUp()

    def test_minimum_initial_deposit_ignore_withdrawal(self):
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_hard_settlement(amount=1000)]
        )
        positive_balance = self.default_balances(1)
        self.assertIsNone(
            minimum_initial_deposit.validate(
                vault=self.vault,
                postings=pib,
                balances=positive_balance,
                denomination="GBP",
            )
        )

    def test_minimum_initial_deposit_not_met(self):
        pib = self.default_deposit_pib(amount=19)
        with self.assertRaises(Rejected) as ex:
            minimum_initial_deposit.validate(
                vault=self.vault,
                postings=pib,
                balances=self.zero_balance,
                denomination="GBP",
            )
        self.assertEqual(
            ex.exception.message,
            "Transaction amount 19.00 GBP is less than the minimum initial deposit amount "
            "20.00 GBP.",
        )

    def test_minimum_initial_deposit_met(self):
        pib = self.default_deposit_pib(amount=20)
        self.assertIsNone(
            minimum_initial_deposit.validate(
                vault=self.vault,
                postings=pib,
                balances=self.zero_balance,
                denomination="GBP",
            )
        )

    def test_minimum_initial_deposit_not_met_but_balance_exists(self):
        latest_balances = self.default_balances(amount=19)
        pib = self.default_deposit_pib(amount=1)
        vault = self.create_mock(minimum_initial_deposit=Decimal(20))
        self.assertIsNone(
            minimum_initial_deposit.validate(
                vault=vault, postings=pib, balances=latest_balances, denomination="GBP"
            )
        )


class TestMinimumSingleDeposit(DepositFeatureTest):
    target_test_file = (
        "library/features/deposits/transaction_limits/deposit_limits/minimum_single_deposit.py"
    )

    def setUp(self) -> None:
        self.vault = self.create_mock(minimum_deposit=Decimal("0.01"))
        return super().setUp()

    def test_minimum_single_deposit_ignore_withdrawal(self):
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_hard_settlement(amount=1000)]
        )
        self.assertIsNone(
            minimum_single_deposit.validate(vault=self.vault, postings=pib, denomination="GBP")
        )

    def test_minimum_single_deposit_not_met(self):
        pib = self.default_deposit_pib(amount=Decimal("0.001"))
        with self.assertRaises(Rejected) as ex:
            minimum_single_deposit.validate(vault=self.vault, postings=pib, denomination="GBP")
        self.assertEqual(
            ex.exception.message,
            "Transaction amount 0.001 GBP is less than the minimum deposit amount 0.01 GBP.",
        )

    def test_minimum_single_deposit_met(self):
        pib = self.default_deposit_pib(amount=Decimal("0.01"))
        self.assertIsNone(
            minimum_single_deposit.validate(vault=self.vault, postings=pib, denomination="GBP")
        )

    def test_minimum_single_deposit_exceeded(self):
        pib = self.default_deposit_pib(amount=Decimal("0.011"))
        self.assertIsNone(
            minimum_single_deposit.validate(vault=self.vault, postings=pib, denomination="GBP")
        )

    def test_minimum_single_deposit_exponent_logging(self):
        self.vault = self.create_mock(minimum_deposit=Decimal(10))
        pib = self.default_deposit_pib(amount=Decimal("0.01"))
        with self.assertRaises(Rejected) as ex:
            minimum_single_deposit.validate(vault=self.vault, postings=pib, denomination="GBP")
        self.assertEqual(
            ex.exception.message,
            "Transaction amount 0.01 GBP is less than the minimum deposit amount 10 GBP.",
        )


class TestMaximumDailyDeposit(DepositFeatureTest):
    target_test_file = (
        "library/features/deposits/transaction_limits/deposit_limits/maximum_daily_deposit.py"
    )

    def test_posting_non_net_maximum_daily_deposit_not_exceeded(self):
        # the proposed transaction is +ve but is not hitting the daily limit of (+100)
        transactions = [
            Deposit(effective_date=self.EOD_DATETIME - timedelta(minutes=2), amount="50"),
            Deposit(effective_date=self.EOD_DATETIME, amount="40"),
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_deposit=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=False,
            )
        )

    def test_posting_non_net_maximum_daily_deposit_met(self):
        # the proposed transaction is +ve but is only meeting the daily limit of (+100)
        transactions = [
            Deposit(effective_date=self.EOD_DATETIME - timedelta(minutes=2), amount="30"),
            Deposit(effective_date=self.EOD_DATETIME, amount="70"),
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_deposit=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=False,
            )
        )

    def test_posting_non_net_maximum_daily_deposit_exceeded(self):
        # the proposed transaction is +ve and is exceeding the daily limit of (+100)
        transactions = [
            Deposit(effective_date=self.EOD_DATETIME - timedelta(minutes=2), amount="50"),
            Deposit(effective_date=self.EOD_DATETIME, amount="60"),
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_deposit=Decimal(100),
        )
        with self.assertRaises(Rejected) as ex:
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=False,
            )
        self.assertEqual(
            ex.exception.message,
            "PIB would cause the maximum daily deposit limit of 100 GBP to be exceeded.",
        )

    def test_non_net_deposit_ignore_withdrawal_only_batches(self):
        # When net_batch=False, withdrawals should always be accepted even if the previous deposits
        # are over the limit.
        transactions = [
            Deposit(effective_date=self.EOD_DATETIME - timedelta(minutes=1), amount="110"),
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
            maximum_daily_deposit=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=False,
            )
        )

    def test_posting_net_positive_maximum_daily_deposit_not_exceeded(self):
        # the proposed transaction's net is +ve but is not hitting the daily limit of (+100)
        transactions = [
            Deposit(effective_date=self.EOD_DATETIME, amount="99"),
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_deposit=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_posting_net_positive_maximum_daily_deposit_met(self):
        # the proposed transaction's net is +ve but is only meeting the daily limit of (+100)
        transactions = [
            Deposit(effective_date=self.EOD_DATETIME, amount="100"),
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_deposit=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_posting_net_positive_maximum_daily_deposit_exceeded(self):
        # the proposed transaction's net is +ve and is exceeding the daily limit of (+100)
        transactions = [
            Deposit(effective_date=self.EOD_DATETIME, amount="102"),
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_deposit=Decimal(100),
        )
        with self.assertRaises(Rejected) as ex:
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        self.assertEqual(
            ex.exception.message,
            "PIB would cause the maximum daily deposit limit of 100 GBP to be exceeded.",
        )

    def test_posting_net_negative_proposed_outbound_inbound_auths(self):
        # As the net of the two proposed transactions are negative, the batch should be
        # accepted even though the deposited amounts are exceeding the limit
        #  e.g. deposits 90 + 30 would breach the limit but the outbound of 40 makes
        # the net of the batch a -ve (-40 + 30 = -10)
        transactions = [
            [
                self.inbound_auth(
                    amount=Decimal("90"),
                    value_timestamp=self.EOD_DATETIME - timedelta(minutes=4),
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
            ],
            [
                self.inbound_auth(
                    amount=Decimal("30"),
                    value_timestamp=self.EOD_DATETIME,
                    **{"client_transaction_id": "second_inbound_auth"},
                ),
            ],
            [
                self.outbound_auth(
                    amount=Decimal("40"),
                    value_timestamp=self.EOD_DATETIME,
                    **{"client_transaction_id": "initial_outbound_auth"},
                ),
            ],
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_posting_instructions(self.EOD_DATETIME, transactions)

        vault = self.create_mock(
            maximum_daily_deposit=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_deposit_limit_already_exceeded_batch_outbound_accepted(self):
        # The daily deposit limit has been exceeded but the proposed outbound auth should
        # be accepted.
        transactions = [
            [
                self.inbound_auth(
                    amount=Decimal("130"),
                    value_timestamp=self.EOD_DATETIME - timedelta(minutes=4),
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
            ],
            [
                self.outbound_auth(
                    amount=Decimal("20"),
                    value_timestamp=self.EOD_DATETIME,
                    **{"client_transaction_id": "initial_outbound_auth"},
                ),
            ],
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_posting_instructions(self.EOD_DATETIME, transactions)

        vault = self.create_mock(
            maximum_daily_deposit=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_deposit_limit_already_exceeded_batch_net_negative_accepted(self):
        # The daily deposit limit has been exceeded and the proposed posting batch includes
        # another inbound auth. As the net of the batch is negative, the batch should be
        # accepted.
        transactions = [
            [
                self.inbound_auth(
                    amount=Decimal("130"),
                    value_timestamp=self.EOD_DATETIME - timedelta(minutes=4),
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
            ],
            [
                self.outbound_auth(
                    amount=Decimal("20"),
                    value_timestamp=self.EOD_DATETIME,
                    **{"client_transaction_id": "initial_outbound_auth"},
                ),
            ],
            [
                self.inbound_auth(
                    amount=Decimal("5"),
                    value_timestamp=self.EOD_DATETIME - timedelta(minutes=4),
                    **{"client_transaction_id": "second_inbound_auth"},
                ),
            ],
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_posting_instructions(self.EOD_DATETIME, transactions)

        vault = self.create_mock(
            maximum_daily_deposit=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_maximum_daily_deposit_net_batch_ignore_withdrawals(self):
        # Withdrawal transactions should be ignored when they are the only proposed posting
        # as they do not count towards the daily deposit limit
        transactions = [
            Withdrawal(effective_date=self.EOD_DATETIME, amount="101"),
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_deposit=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_maximum_daily_deposit_mixture_of_deposits_and_withdrawals_exceeds_limit(self):
        # Ensure that historic withdrawal transactions are ignored and the previous deposit
        # transaction is taken into account
        transactions = [
            Withdrawal(effective_date=self.EOD_DATETIME - timedelta(minutes=3), amount="101"),
            Deposit(effective_date=self.EOD_DATETIME - timedelta(minutes=2), amount="50"),
            Withdrawal(effective_date=self.EOD_DATETIME - timedelta(minutes=1), amount="101"),
            Deposit(effective_date=self.EOD_DATETIME, amount="51"),
        ]

        (
            _,
            client_transactions,
            client_transactions_excluding_proposed,
        ) = self.pib_and_cts_for_transactions(
            hook_effective_date=self.EOD_DATETIME, transactions=transactions
        )
        vault = self.create_mock(
            maximum_daily_deposit=Decimal(100),
        )
        with self.assertRaises(Rejected) as ex:
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        self.assertEqual(
            ex.exception.message,
            "PIB would cause the maximum daily deposit limit of 100 GBP to be exceeded.",
        )

    def test_maximum_daily_deposit_chainable_auth_settlement(self):
        # check that a settlement is accepted up to the amount of the original auth
        # even if that auth was over the limit (the net of the batch is 0 as the 110
        # was accounted for in the original auth)
        transactions = [
            [
                self.inbound_auth(
                    amount=Decimal("110"),
                    value_timestamp=self.EOD_DATETIME - timedelta(minutes=4),
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
                self.settle_inbound_auth(
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
            maximum_daily_deposit=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )

    def test_maximum_daily_deposit_chainable_auth_oversettlement(self):
        # check that an oversettlement (settlement > auth) is rejected if the oversettlement
        # amount exceeds the deposit limit (this oversettlement is impacting the total deposited
        # amount by +20)

        transactions = [
            [
                self.inbound_auth(
                    amount=Decimal("90"),
                    value_timestamp=self.EOD_DATETIME - timedelta(minutes=4),
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
                self.settle_inbound_auth(
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
            maximum_daily_deposit=Decimal(100),
        )
        with self.assertRaises(Rejected) as ex:
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        self.assertEqual(
            ex.exception.message,
            "PIB would cause the maximum daily deposit limit of 100 GBP to be exceeded.",
        )

    def test_maximum_daily_deposit_chainable_auth_release(self):
        # want to check that a release is always accepted even if the original
        # auth was over the limit
        transactions = [
            [
                self.inbound_auth(
                    amount=Decimal("110"),
                    value_timestamp=self.EOD_DATETIME - timedelta(minutes=4),
                    **{"client_transaction_id": "initial_inbound_auth"},
                ),
                self.release_inbound_auth(
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
            maximum_daily_deposit=Decimal(100),
        )
        self.assertIsNone(
            maximum_daily_deposit.validate(
                vault=vault,
                client_transactions=client_transactions,
                client_transactions_excluding_proposed=client_transactions_excluding_proposed,
                effective_date=self.EOD_DATETIME,
                denomination="GBP",
                net_batch=True,
            )
        )
