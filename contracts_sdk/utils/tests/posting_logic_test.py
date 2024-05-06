import unittest
from datetime import datetime
from decimal import Decimal

from .. import posting_logic
from ..exceptions import InvalidPostingInstructionException
from ..symbols import DEFAULT_ADDRESS, DEFAULT_ASSET, Phase, PostingInstructionType


_CLIENT_TRANSACTION_ID = "MSC0000132132XXXXXXX-MAIN"
_CLIENT_TRANSACTION_ID_2 = "MSC0000132132XXXXXXX-NEW"
_ACCOUNT_ID = "123"
_ACCOUNT_ID_2 = "1234"


class ClientTransactionBalancesTests(unittest.TestCase):
    def test_client_transaction_balances(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )

        # Auth Committed Postings
        auth = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )

        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [auth], PostingInstructionType.INBOUND_AUTHORISATION
        )

        # Correct balances returned
        balances = client_transaction.balances()
        self.assertEqual(len(balances), 1)

        self.assertEqual(
            balances[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(100), debit=Decimal(0)),
        )

    def test_client_transaction_balances_by_datetime(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )

        # Auth Committed Postings
        auth = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )

        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [auth], PostingInstructionType.INBOUND_AUTHORISATION
        )

        # Correct balances returned
        balances = client_transaction.balances(at_datetime=datetime(2018, 12, 11))
        self.assertEqual(len(balances), 1)

        self.assertEqual(
            balances[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(100), debit=Decimal(0)),
        )

        # No balances returned if before the first timestamp
        balances = client_transaction.balances(at_datetime=datetime(2018, 12, 10))
        self.assertEqual(len(balances), 0)

    def test_client_transaction_balances_multiple_committed_postings(self):
        # Auth Committed Postings
        auth = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )

        # AuthAdjust Committed Postings
        auth_adjust = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(50),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )

        # Settlement Committed Postings
        settle_1 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(50),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        settle2 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(50),
            credit=True,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )

        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [auth], PostingInstructionType.INBOUND_AUTHORISATION
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 12), [auth_adjust], PostingInstructionType.AUTHORISATION_ADJUSTMENT
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 13), [settle_1, settle2], PostingInstructionType.SETTLEMENT
        )

        # Correct balances returned - after auth
        balances = client_transaction.balances(at_datetime=datetime(2018, 12, 11))
        self.assertEqual(len(balances), 1)

        self.assertEqual(
            balances[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(100), debit=Decimal(0)),
        )

        # Correct balances returned - after auth adjust
        balances = client_transaction.balances(at_datetime=datetime(2018, 12, 12))
        self.assertEqual(len(balances), 1)

        self.assertEqual(
            balances[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(100), debit=Decimal(50)),
        )

        # Correct balances returned - after settlement
        balances = client_transaction.balances(at_datetime=datetime(2018, 12, 13))
        self.assertEqual(len(balances), 2)

        self.assertEqual(
            balances[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(100), debit=Decimal(100)),
        )
        self.assertEqual(
            balances[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(50), debit=Decimal(0)),
        )


class ClientTransactionValidationTests(unittest.TestCase):
    def test_client_transaction_no_committed_postings(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(
                datetime(2018, 12, 11), [], PostingInstructionType.TRANSFER
            )
        self.assertEqual(str(ex.exception), "Committed Postings required")

    def test_client_transaction_account_id_not_match(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        settle_1 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(50),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        settle2 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID_2,
            amount=Decimal(50),
            credit=True,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(
                datetime(2018, 12, 11), [settle_1, settle2], PostingInstructionType.SETTLEMENT
            )
        self.assertEqual(
            str(ex.exception),
            "Cannot add this Committed Posting with account "
            "ID 1234 to the Client Transaction for account ID 123",
        )

    def test_client_transaction_flag_final(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        release = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(50),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(
                datetime(2018, 12, 11), [release], PostingInstructionType.RELEASE, final=True
            )
        self.assertEqual(
            str(ex.exception), "Final flag can only be used with Settlement Posting Instructions"
        )

    def test_client_transaction_validate_primary(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        settle_1 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(50),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(
                datetime(2018, 12, 11), [settle_1], PostingInstructionType.SETTLEMENT
            )
        self.assertEqual(str(ex.exception), "A ClientTransaction cannot start with Settlement")

    def test_client_transaction_validate_custom_instruction_is_supported(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        custom_1 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(50),
            credit=False,
            denomination="LKR",
            phase=Phase.PENDING_IN,
        )

        custom_2 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(54321),
            credit=True,
            denomination="LKR",
            phase=Phase.PENDING_IN,
        )

        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [custom_1], PostingInstructionType.CUSTOM_INSTRUCTION
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 12), [custom_2], PostingInstructionType.CUSTOM_INSTRUCTION
        )
        balances = client_transaction.balances(at_datetime=datetime(2018, 12, 11))

        self.assertEqual(len(balances), 1)
        self.assertEqual(
            balances[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="LKR",
                    phase=Phase.PENDING_IN,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(0), debit=Decimal(50)),
        )

        balances = client_transaction.balances(at_datetime=datetime(2018, 12, 12))

        self.assertEqual(len(balances), 1)
        self.assertEqual(
            balances[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="LKR",
                    phase=Phase.PENDING_IN,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(54321), debit=Decimal(50)),
        )

    def test_client_transaction_validate_unknown(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        settle_1 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(50),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(datetime(2018, 12, 11), [settle_1], "xxx")
        self.assertEqual(str(ex.exception), "Unknown instruction type xxx")

    def test_client_transaction_validate_value_datetime(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        custom = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(50),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(
                None, [custom], PostingInstructionType.CUSTOM_INSTRUCTION
            )
        self.assertEqual(
            str(ex.exception),
            "All posting instructions within a ClientTransaction "
            "have to have a value_datetime set.",
        )

    def test_client_transaction_validate_secondary(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        auth = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        auth_2 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [auth], PostingInstructionType.INBOUND_AUTHORISATION
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(
                datetime(2018, 12, 11), [auth_2], PostingInstructionType.INBOUND_AUTHORISATION
            )
        self.assertEqual(
            str(ex.exception),
            "Cannot add InboundAuthorisation to existing "
            "ClientTransaction (id MSC0000132132XXXXXXX-MAIN)",
        )

    def test_client_transaction_validate_secondary_not_match(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        auth = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        settlement = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [auth], PostingInstructionType.INBOUND_HARD_SETTLEMENT
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(
                datetime(2018, 12, 11), [settlement], PostingInstructionType.SETTLEMENT
            )
        self.assertEqual(
            str(ex.exception),
            "Cannot add Settlement for an existing ClientTransaction "
            "(id MSC0000132132XXXXXXX-MAIN) that did not start with an "
            "InboundAuthorisation or an OutboundAuthorisation",
        )

    def test_client_transaction_validate_secondary_custom_not_match(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        auth = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        custom = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [auth], PostingInstructionType.INBOUND_AUTHORISATION
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(
                datetime(2018, 12, 11), [custom], PostingInstructionType.CUSTOM_INSTRUCTION
            )
        self.assertEqual(
            str(ex.exception),
            "Cannot add CustomInstruction for an existing ClientTransaction "
            "(id MSC0000132132XXXXXXX-MAIN) that did not start with a "
            "CustomInstruction",
        )

    def test_client_transaction_validate_secondary_exception_with_custom_primary_instruction(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        custom = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        settlement = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(123),
            credit=True,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [custom], PostingInstructionType.CUSTOM_INSTRUCTION
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(
                datetime(2018, 12, 11), [settlement], PostingInstructionType.SETTLEMENT
            )
        self.assertEqual(
            str(ex.exception),
            "Cannot add Settlement for an existing ClientTransaction "
            "(id MSC0000132132XXXXXXX-MAIN) that did not start with an "
            "InboundAuthorisation or an OutboundAuthorisation",
        )

    def test_client_transaction_validate_secondary_exception_with_non_chainable_instruction(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        custom = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        transfer = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(123),
            credit=True,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [custom], PostingInstructionType.CUSTOM_INSTRUCTION
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(
                datetime(2018, 12, 11), [transfer], PostingInstructionType.TRANSFER
            )
        self.assertEqual(
            str(ex.exception),
            "Cannot add Transfer to existing ClientTransaction (id MSC0000132132XXXXXXX-MAIN)",
        )

    def test_client_transaction_validate_secondary_backdating(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        auth = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        auth_2 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [auth], PostingInstructionType.INBOUND_AUTHORISATION
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(
                datetime(2018, 12, 10), [auth_2], PostingInstructionType.AUTHORISATION_ADJUSTMENT
            )
        self.assertEqual(str(ex.exception), "ClientTransaction does not support backdating")

    def test_client_transaction_validate_secondary_committed_postings_not_finalized(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        auth = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        settlement = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        settlement_2 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )
        auth_adjust = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [auth], PostingInstructionType.INBOUND_AUTHORISATION
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 11),
            [settlement, settlement_2],
            PostingInstructionType.SETTLEMENT,
            final=True,
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(
                datetime(2018, 12, 12),
                [auth_adjust],
                PostingInstructionType.AUTHORISATION_ADJUSTMENT,
            )
        self.assertEqual(
            str(ex.exception),
            "Client Transaction (id MSC0000132132XXXXXXX-MAIN) has already been finalised",
        )

    def test_client_transaction_validate_secondary_last_update_empty(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction._validate_secondary_instruction(
                datetime(2018, 12, 11), PostingInstructionType.SETTLEMENT
            )
        self.assertEqual(
            str(ex.exception),
            "Secondary instruction cannot be added to an empty ClientTransaction",
        )

    def test_client_transaction_validate_secondary_committed_posting_cancelled(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        auth = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        release = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        auth_adjust = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [auth], PostingInstructionType.INBOUND_AUTHORISATION
        )
        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [release], PostingInstructionType.RELEASE
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            client_transaction.add_committed_postings(
                datetime(2018, 12, 12),
                [auth_adjust],
                PostingInstructionType.AUTHORISATION_ADJUSTMENT,
            )
        self.assertEqual(
            str(ex.exception),
            "Client Transaction (id MSC0000132132XXXXXXX-MAIN) has already been finalised",
        )


class ClientTransactionStateChangesTests(unittest.TestCase):
    def test_client_transaction_state_lifecycle_complete(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )

        # Auth Committed Postings
        auth = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )

        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [auth], PostingInstructionType.INBOUND_AUTHORISATION
        )

        # Return Empty dict if datetime is too early
        self.assertEqual(client_transaction.balances(at_datetime=datetime(2018, 12, 10)), {})

        # Check that state is updated correctly
        self.assertEqual(client_transaction.last_update.completed, False)
        self.assertEqual(client_transaction.last_update.released, False)
        self.assertEqual(
            client_transaction.balances(at_datetime=datetime(2018, 12, 11))[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(100), debit=Decimal(0)),
        )

        # AuthAdjust Committed Postings
        auth_adjust = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(20),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )

        client_transaction.add_committed_postings(
            datetime(2018, 12, 12), [auth_adjust], PostingInstructionType.AUTHORISATION_ADJUSTMENT
        )

        # Check that state is updated correctly - adding auth adjust
        self.assertEqual(client_transaction.last_update.completed, False)
        self.assertEqual(client_transaction.last_update.released, False)
        self.assertEqual(
            client_transaction.balances(at_datetime=datetime(2018, 12, 12))[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(100), debit=Decimal(20)),
        )

        # Settlement Committed Postings
        settle1 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(30),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        settle2 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(30),
            credit=True,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )

        client_transaction.add_committed_postings(
            datetime(2018, 12, 13), [settle1, settle2], PostingInstructionType.SETTLEMENT
        )

        # Check that state is updated correctly - adding auth adjust
        self.assertEqual(client_transaction.last_update.completed, False)
        self.assertEqual(client_transaction.last_update.released, False)
        self.assertEqual(
            client_transaction.balances(at_datetime=datetime(2018, 12, 13))[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(100), debit=Decimal(50)),
        )
        self.assertEqual(
            client_transaction.balances(at_datetime=datetime(2018, 12, 13))[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(30), debit=Decimal(0)),
        )

        # Settlement Committed Postings - final
        settle3 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(50),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        settle4 = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=True,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )

        client_transaction.add_committed_postings(
            datetime(2018, 12, 14),
            [settle3, settle4],
            PostingInstructionType.SETTLEMENT,
            final=True,
        )

        # Check that state is updated correctly - adding auth adjust
        self.assertEqual(client_transaction.last_update.completed, True)
        self.assertEqual(client_transaction.last_update.released, False)
        self.assertEqual(
            client_transaction.balances(at_datetime=datetime(2018, 12, 14))[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(100), debit=Decimal(100)),
        )
        self.assertEqual(
            client_transaction.balances(at_datetime=datetime(2018, 12, 14))[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(130), debit=Decimal(0)),
        )

        # Can get historical CT balances value
        self.assertEqual(
            client_transaction.balances(at_datetime=datetime(2018, 12, 11))[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(100), debit=Decimal(0)),
        )

    def test_client_transaction_state_lifecycle_cancel(self):
        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )

        # Auth Committed Postings
        auth = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(100),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_OUT,
        )

        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [auth], PostingInstructionType.OUTBOUND_AUTHORISATION
        )

        # If timestamp is too early - return empty state
        self.assertEqual(
            client_transaction.balances(at_datetime=datetime(2018, 12, 10)),
            {},
        )

        # Check that state is updated correctly
        self.assertEqual(client_transaction.last_update.completed, False)
        self.assertEqual(client_transaction.last_update.released, False)
        self.assertEqual(
            client_transaction.balances(at_datetime=datetime(2018, 12, 11))[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(0), debit=Decimal(100)),
        )

        # AuthAdjust Committed Postings
        auth_adjust = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(20),
            credit=False,
            denomination="GBP",
            phase=Phase.PENDING_OUT,
        )

        client_transaction.add_committed_postings(
            datetime(2018, 12, 12), [auth_adjust], PostingInstructionType.AUTHORISATION_ADJUSTMENT
        )

        # Check that state is updated correctly - adding auth adjust
        self.assertEqual(client_transaction.last_update.completed, False)
        self.assertEqual(client_transaction.last_update.released, False)
        self.assertEqual(
            client_transaction.balances(at_datetime=datetime(2018, 12, 12))[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(0), debit=Decimal(120)),
        )

        # Release Committed Postings
        release = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(120),
            credit=True,
            denomination="GBP",
            phase=Phase.PENDING_OUT,
        )

        client_transaction.add_committed_postings(
            datetime(2018, 12, 13), [release], PostingInstructionType.RELEASE
        )

        # Check that state is updated correctly - adding auth adjust
        self.assertEqual(client_transaction.last_update.completed, False)
        self.assertEqual(client_transaction.last_update.released, True)
        self.assertEqual(
            client_transaction.balances(at_datetime=datetime(2018, 12, 13))[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(120), debit=Decimal(120)),
        )

    def test_custom_client_transaction_supported(self):

        client_transaction = posting_logic.SingleAccountClientTransaction(
            _CLIENT_TRANSACTION_ID, _ACCOUNT_ID
        )
        custom = posting_logic.CommittedPosting(
            account_id=_ACCOUNT_ID,
            amount=Decimal(180),
            credit=False,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )

        client_transaction.add_committed_postings(
            datetime(2018, 12, 11), [custom], PostingInstructionType.CUSTOM_INSTRUCTION
        )

        # Check that state is updated correctly (no change) - adding custom
        self.assertEqual(client_transaction.last_update.completed, False)
        self.assertEqual(client_transaction.last_update.released, False)
        self.assertEqual(
            client_transaction.balances()[
                posting_logic.BalanceKey(
                    account_address=DEFAULT_ADDRESS,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                    asset=DEFAULT_ASSET,
                )
            ],
            posting_logic.BalanceValue(credit=Decimal(0), debit=Decimal(180)),
        )
