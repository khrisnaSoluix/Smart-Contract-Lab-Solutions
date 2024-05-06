# standard libs
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.common.client_transaction_utils as client_transaction_utils

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ClientTransaction,
    Tside,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    DEFAULT_POSTINGS,
)

CUT_OFF_DATE = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
CTX_ID_1 = "client_transaction_id_1"
CTX_ID_2 = "client_transaction_id_2"
CTX_ID_3 = "client_transaction_id_3"
DEFAULT_ACCOUNT = "default_account"
CTX_ID_DUMMY = "client_transaction_id_dummy"


class TestTransactionLimitUtils(FeatureTest):
    tside = Tside.LIABILITY


class TestSumClientTransactions(TestTransactionLimitUtils):
    def test_sum_client_transactions_handles_hard_settlement_deposits(self):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("501"),
                    value_datetime=value_datetime,
                )
            ],
            tside=self.tside,
        )

        result = client_transaction_utils.sum_client_transactions(
            cutoff_datetime=CUT_OFF_DATE, client_transactions={CTX_ID_1: ctx}, denomination="GBP"
        )
        self.assertEqual(result, (501, 0))

    def test_sum_client_transactions_handles_hard_settlement_withdrawals(self):
        value_datetime = CUT_OFF_DATE + timedelta(hours=+1)

        ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("502"),
                    value_datetime=value_datetime,
                )
            ],
            tside=self.tside,
        )

        result = client_transaction_utils.sum_client_transactions(
            cutoff_datetime=CUT_OFF_DATE, client_transactions={CTX_ID_1: ctx}, denomination="GBP"
        )
        self.assertEqual(result, (0, 502))

    def test_sum_client_transactions_handles_mix_of_txns(self):
        """
        Sum should include PIBs of mixed transaction types (e.g. Deposits and Withdrawals)
        """
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)
        postings_inbound = [
            self.inbound_hard_settlement(
                amount=Decimal("501"),
                value_datetime=value_datetime,
            )
        ]
        postings_outbound = [
            self.outbound_hard_settlement(
                amount=Decimal("501"),
                value_datetime=value_datetime,
            )
        ]

        ctx_inbound = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=postings_inbound,
        )

        ctx_outbound = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=postings_outbound,
        )

        result = client_transaction_utils.sum_client_transactions(
            cutoff_datetime=CUT_OFF_DATE,
            client_transactions={CTX_ID_1: ctx_inbound, CTX_ID_2: ctx_outbound},
            denomination="GBP",
        )
        self.assertEqual(result, (501, 501))

    def test_sum_client_transactions_settlement_value_not_counted_twice(self):
        """
        When summing client transactions including proposed, the
        function should consider chainable transactions
        and not double count an auth and a settlement
        """
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_auth(
                    amount=Decimal("105"),
                    value_datetime=value_datetime - timedelta(minutes=1),
                ),
                self.settle_outbound_auth(
                    unsettled_amount=Decimal("105"),
                    amount=Decimal("105"),
                    value_datetime=value_datetime,
                ),
            ],
            tside=self.tside,
        )

        result = client_transaction_utils.sum_client_transactions(
            client_transactions={CTX_ID_1: ctx}, cutoff_datetime=CUT_OFF_DATE, denomination="GBP"
        )
        self.assertEqual(result, (0, 105))

    def test_sum_client_transactions_handles_partial_settlements(self):
        """
        A partial settlement should not affect the sum of the client
        transactions as the settlement wasn't final so any value up to the
        original auth of 105 could still be settled
        """
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_auth(
                    amount=Decimal("105"),
                    value_datetime=value_datetime - timedelta(minutes=1),
                ),
                self.settle_outbound_auth(
                    unsettled_amount=Decimal("105"),
                    amount=Decimal("40"),
                    value_datetime=value_datetime,
                ),
            ],
            tside=self.tside,
        )

        result = client_transaction_utils.sum_client_transactions(
            client_transactions={CTX_ID_1: ctx}, cutoff_datetime=CUT_OFF_DATE, denomination="GBP"
        )

        self.assertEqual(result, (0, 105))

    def test_sum_client_transaction_handles_cancelled_transactions(self):
        """
        Sum should not include cancelled client transactions ids as the original
        funds that were authed have now be zero'd out
        """
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_auth(
                    amount=Decimal("10"),
                    value_datetime=value_datetime - timedelta(minutes=1),
                ),
                self.release_outbound_auth(
                    unsettled_amount=Decimal("10"),
                    value_datetime=value_datetime,
                ),
            ],
            tside=self.tside,
        )

        result = client_transaction_utils.sum_client_transactions(
            client_transactions={CTX_ID_1: ctx}, cutoff_datetime=CUT_OFF_DATE, denomination="GBP"
        )

        self.assertEqual(result, (0, 0))

    def test_sum_client_transactions_includes_transaction_on_cut_off(self):
        """
        Sum should include pib that takes place on the cut-off time
        """
        value_datetime = CUT_OFF_DATE

        ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("501"),
                    denomination="USD",
                    value_datetime=value_datetime,
                )
            ],
            tside=self.tside,
        )

        result = client_transaction_utils.sum_client_transactions(
            client_transactions={CTX_ID_1: ctx}, cutoff_datetime=CUT_OFF_DATE, denomination="USD"
        )

        self.assertEqual(result, (0, 501))

    def test_sum_client_transactions_includes_transaction_after_cut_off(self):
        """
        Sum should include pib that takes place after the cut-off time
        """
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("501"),
                    denomination="USD",
                    value_datetime=value_datetime,
                )
            ],
            tside=self.tside,
        )

        result = client_transaction_utils.sum_client_transactions(
            client_transactions={CTX_ID_1: ctx}, cutoff_datetime=CUT_OFF_DATE, denomination="USD"
        )

        self.assertEqual(result, (0, 501))

    def test_sum_client_transactions_excludes_transaction_before_cut_off(self):
        """
        Sum should not include a posting with value_datetime before the cut-off time as it is not
        considered as part of that day's total
        """
        value_datetime = CUT_OFF_DATE - timedelta(hours=1)

        ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("501"),
                    denomination="USD",
                    value_datetime=value_datetime,
                )
            ],
            tside=self.tside,
        )

        result = client_transaction_utils.sum_client_transactions(
            client_transactions={CTX_ID_1: ctx}, cutoff_datetime=CUT_OFF_DATE, denomination="USD"
        )

        self.assertEqual(result, (0, 0))

    def test_sum_client_transactions_excludes_transactions_of_different_denomination(self):
        """
        Sum should not include a posting with denomination different than the one indicated
        """
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("501"),
                    denomination="USD",
                    value_datetime=value_datetime,
                )
            ],
            tside=self.tside,
        )

        ctx2 = ClientTransaction(
            client_transaction_id=CTX_ID_2,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("100"),
                    denomination="EUR",
                    value_datetime=value_datetime,
                )
            ],
            tside=self.tside,
        )

        result = client_transaction_utils.sum_client_transactions(
            client_transactions={CTX_ID_1: ctx, CTX_ID_2: ctx2},
            cutoff_datetime=CUT_OFF_DATE,
            denomination="EUR",
        )

        self.assertEqual(result, (0, 100))

    def test_chainable_transactions_auth_adjust_cut_off_respected(self):
        """
        If an auth takes place before the cutoff time, only the
        proposed auth adjustment should contribute to the
        withdrawals.
        """
        previous_day_value_datetime = CUT_OFF_DATE - timedelta(hours=23)
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_auth(
                    amount=Decimal("90"),
                    value_datetime=previous_day_value_datetime,
                ),
                self.outbound_auth_adjust(
                    amount=Decimal("40"),
                    value_datetime=value_datetime,
                ),
            ],
        )

        result = client_transaction_utils.sum_client_transactions(
            client_transactions={CTX_ID_1: ctx}, cutoff_datetime=CUT_OFF_DATE, denomination="GBP"
        )

        self.assertEqual(result, (0, 40))

    def test_chainable_transactions_auth_adjust_decrease(self):
        """
        A negative auth adjustment to an outbound auth is considered as deposit
        """
        previous_day_value_datetime = CUT_OFF_DATE - timedelta(hours=23)
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_auth(
                    amount=Decimal("90"),
                    value_datetime=previous_day_value_datetime,
                ),
                self.outbound_auth_adjust(
                    amount=Decimal("-40"),
                    value_datetime=value_datetime,
                ),
            ],
        )

        result = client_transaction_utils.sum_client_transactions(
            client_transactions={CTX_ID_1: ctx}, cutoff_datetime=CUT_OFF_DATE, denomination="GBP"
        )

        self.assertEqual(result, (40, 0))

    def test_chainable_settlements_cut_off_respected(self):
        """
        If an auth takes place before the cutoff time, the proposed
        settlement should still not impact the the sum as it
        was already accounted for at the time of the auth.
        """
        previous_day_value_datetime = CUT_OFF_DATE - timedelta(hours=23)
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)

        ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_auth(
                    amount=Decimal("90"),
                    value_datetime=previous_day_value_datetime,
                ),
                self.settle_outbound_auth(
                    unsettled_amount=Decimal("90"),
                    amount=Decimal("90"),
                    value_datetime=value_datetime,
                ),
            ],
            tside=self.tside,
        )
        result = client_transaction_utils.sum_client_transactions(
            client_transactions={CTX_ID_1: ctx}, cutoff_datetime=CUT_OFF_DATE, denomination="GBP"
        )
        self.assertEqual(result, (0, 0))

    def test_custom_instruction_client_transaction_has_zero_sum(self):
        ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=sentinel.account_id,
            posting_instructions=[
                self.custom_instruction(
                    postings=DEFAULT_POSTINGS,
                    value_datetime=CUT_OFF_DATE,
                ),
            ],
            tside=self.tside,
        )
        result = client_transaction_utils.sum_client_transactions(
            client_transactions={CTX_ID_1: ctx}, cutoff_datetime=CUT_OFF_DATE, denomination="GBP"
        )
        self.assertEqual(result, (0, 0))


class TestFilterClientTransactions(TestTransactionLimitUtils):
    def setUp(self) -> None:
        self.eligible_client_transaction = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("1"),
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    )
                ],
                tside=self.tside,
            )
        }
        return super().setUp()

    def test_filter_with_matching_key_value(
        self,
    ):
        self.assertDictEqual(
            client_transaction_utils.filter_client_transactions(
                denomination=self.default_denomination,
                client_transactions=self.eligible_client_transaction,
                key="type",
                value="atm",
            ),
            self.eligible_client_transaction,
        )

    def test_filter_with_matching_key_value_and_multiple_txns(self):
        client_transactions = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("1"),
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    )
                ],
                tside=self.tside,
            ),
            CTX_ID_2: ClientTransaction(
                client_transaction_id=CTX_ID_2,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("1"),
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    )
                ],
                tside=self.tside,
            ),
        }

        self.assertEqual(
            client_transaction_utils.filter_client_transactions(
                denomination=self.default_denomination,
                client_transactions=client_transactions,
                key="type",
                value="atm",
            ),
            client_transactions,
        )

    def test_filter_excludes_transaction_without_key(self):
        self.assertDictEqual(
            client_transaction_utils.filter_client_transactions(
                denomination=self.default_denomination,
                client_transactions=self.eligible_client_transaction,
                client_transaction_ids_to_ignore=[],
                key="other_type",
                value="atm",
            ),
            {},
        )

    def test_filter_excludes_transaction_with_wrong_value(
        self,
    ):
        self.assertDictEqual(
            client_transaction_utils.filter_client_transactions(
                denomination=self.default_denomination,
                client_transactions=self.eligible_client_transaction,
                client_transaction_ids_to_ignore=[""],
                key="type",
                value="not_atm",
            ),
            {},
        )

    def test_filter_excludes_transaction_with_id_to_ignore(
        self,
    ):
        self.assertDictEqual(
            client_transaction_utils.filter_client_transactions(
                denomination=self.default_denomination,
                client_transactions=self.eligible_client_transaction,
                client_transaction_ids_to_ignore=[CTX_ID_1],
                key="type",
                value="atm",
            ),
            {},
        )

    def test_filter_excludes_released_transaction(self):
        client_transactions = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_auth(
                        amount=Decimal("1"),
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    ),
                    self.release_outbound_auth(
                        unsettled_amount=Decimal("1"),
                    ),
                ],
                tside=self.tside,
            )
        }
        self.assertTrue(client_transactions[CTX_ID_1].released())

        self.assertDictEqual(
            client_transaction_utils.filter_client_transactions(
                denomination=self.default_denomination,
                client_transactions=client_transactions,
                client_transaction_ids_to_ignore=[],
                key="type",
                value="atm",
            ),
            {},
        )

    def test_filter_excludes_custom_instructions(self):
        client_transactions = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=sentinel.account_id,
                posting_instructions=[
                    self.custom_instruction(
                        amount=Decimal("1"),
                        postings=DEFAULT_POSTINGS,
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    ),
                ],
                tside=self.tside,
            )
        }

        self.assertEqual(
            client_transaction_utils.filter_client_transactions(
                denomination=self.default_denomination,
                client_transactions=client_transactions,
                client_transaction_ids_to_ignore=[""],
                key="type",
                value="atm",
            ),
            {},
        )

    def test_filter_excludes_different_denomination(
        self,
    ):
        self.assertEqual(
            client_transaction_utils.filter_client_transactions(
                denomination="BLA",
                client_transactions=self.eligible_client_transaction,
                client_transaction_ids_to_ignore=[""],
                key="type",
                value="atm",
            ),
            {},
        )


class TestSumDebitsByInstructionDetails(TestTransactionLimitUtils):
    @patch.object(client_transaction_utils, "sum_client_transactions")
    @patch.object(client_transaction_utils, "filter_client_transactions")
    def test_sum_debits_by_instruction_details(
        self, mock_filter_transactions: MagicMock, mock_sum_client_transaction: MagicMock
    ):
        mock_filter_transactions.return_value = sentinel.filtered_transactions
        mock_sum_client_transaction.return_value = sentinel.net_credit, sentinel.net_debit

        self.assertEqual(
            client_transaction_utils.sum_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=sentinel.client_transaction_ids_to_ignore,
                cutoff_datetime=sentinel.cutoff_datetime,
                key=sentinel.key,
                value=sentinel.value,
            ),
            sentinel.net_debit,
        )
        mock_filter_transactions.assert_called_once_with(
            denomination=sentinel.denomination,
            client_transactions=sentinel.client_transactions,
            client_transaction_ids_to_ignore=sentinel.client_transaction_ids_to_ignore,
            key=sentinel.key,
            value=sentinel.value,
        )
        mock_sum_client_transaction.assert_called_once_with(
            cutoff_datetime=sentinel.cutoff_datetime,
            client_transactions=sentinel.filtered_transactions,
            denomination=sentinel.denomination,
        )


# We should ideally test get_total_transaction_impact separately and mock here. At the moment
# it's tested within sum_client_transactions, so we're repeating some tests
@patch.object(client_transaction_utils, "filter_client_transactions")
class TestExtractDebitsByInstructionDetails(TestTransactionLimitUtils):
    def setUp(self) -> None:
        self.eligible_client_transaction = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("1"),
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    )
                ],
                tside=self.tside,
            )
        }
        return super().setUp()

    def test_extract_debits_filters_client_transactions(
        self, mock_filter_client_transactions: MagicMock
    ):
        mock_filter_client_transactions.return_value = {}
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=sentinel.cutoff_datetime,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [],
        )
        mock_filter_client_transactions.assert_called_once_with(
            denomination=sentinel.denomination,
            client_transactions=sentinel.client_transactions,
            client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
            key=sentinel.key,
            value=sentinel.value,
        )

    def test_extract_debits_outbound_auth_settle_across_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # settle has no net debit impact to a previous auth
        auth_posting = self.outbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE - timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        settle_posting = self.settle_outbound_auth(
            amount=Decimal("1"),
            unsettled_amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    auth_posting,
                    settle_posting,
                ],
                tside=self.tside,
            )
        }
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [],
        )

    def test_extract_debits_outbound_auth_oversettle_across_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # oversettle has net debit impact == over settlement amount
        auth_posting = self.outbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE - timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        settle_posting = self.settle_outbound_auth(
            amount=Decimal("2"),
            unsettled_amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    auth_posting,
                    settle_posting,
                ],
                tside=self.tside,
            )
        }
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [settle_posting],
        )

    def test_extract_debits_outbound_auth_settle_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # auth/settle after cut-off has net debit impact == auth amount
        auth_posting = self.outbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE,
            instruction_details={"type": "atm"},
        )
        settle_posting = self.settle_outbound_auth(
            amount=Decimal("1"),
            unsettled_amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    auth_posting,
                    settle_posting,
                ],
                tside=self.tside,
            )
        }
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [auth_posting],
        )

    def test_extract_debits_outbound_auth_over_settle_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # auth over settle after cut-off has net debit impact == auth + over settlement amount
        auth_posting = self.outbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE,
            instruction_details={"type": "atm"},
        )
        settle_posting = self.settle_outbound_auth(
            amount=Decimal("2"),
            unsettled_amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    auth_posting,
                    settle_posting,
                ],
                tside=self.tside,
            )
        }
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [auth_posting, settle_posting],
        )

    def test_extract_debits_outbound_auth_and_decrease_auth_adjustment_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # decreasing auth is a net credit, so only the original auth is a net debit
        auth_posting = self.outbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE,
            instruction_details={"type": "atm"},
        )
        adjust_posting = self.outbound_auth_adjust(
            amount=Decimal("-2"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    auth_posting,
                    adjust_posting,
                ],
                tside=self.tside,
            )
        }
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [auth_posting],
        )

    def test_extract_debits_outbound_auth_and_increase_auth_adjustment_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # increasing auth is a net debit, so both auth and adjustment are returned
        auth_posting = self.outbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE,
            instruction_details={"type": "atm"},
        )
        adjust_posting = self.outbound_auth_adjust(
            amount=Decimal("2"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    auth_posting,
                    adjust_posting,
                ],
                tside=self.tside,
            )
        }
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [auth_posting, adjust_posting],
        )

    def test_extract_debits_outbound_hard_settle_before_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # outbound hard settlement before cut-off is net 0 after the cut-off
        outbound_hard_settle_posting = self.outbound_hard_settlement(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE - timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )

        mock_filter_client_transactions.return_value = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    outbound_hard_settle_posting,
                ],
                tside=self.tside,
            )
        }
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [],
        )

    def test_extract_debits_outbound_hard_settle_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # outbound hard settlement after cut-off is net debit after the cut-off for hard settlement
        # amount
        outbound_hard_settle_posting = self.outbound_hard_settlement(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )

        mock_filter_client_transactions.return_value = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    outbound_hard_settle_posting,
                ],
                tside=self.tside,
            )
        }
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [outbound_hard_settle_posting],
        )

    def test_extract_debits_inbound_auth_settle_across_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # inbound postings are credits and are never included
        auth_posting = self.inbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE - timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        settle_posting = self.settle_inbound_auth(
            amount=Decimal("1"),
            unsettled_amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    auth_posting,
                    settle_posting,
                ],
                tside=self.tside,
            )
        }
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [],
        )

    def test_extract_debits_inbound_auth_settle_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # inbound postings are credits and are never included

        auth_posting = self.inbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE,
            instruction_details={"type": "atm"},
        )
        settle_posting = self.settle_inbound_auth(
            amount=Decimal("1"),
            unsettled_amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    auth_posting,
                    settle_posting,
                ],
                tside=self.tside,
            )
        }
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [],
        )

    def test_extract_debits_inbound_hard_settle_before_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # inbound postings are credits and are never included
        inbound_hard_settle_posting = self.inbound_hard_settlement(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE - timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )

        mock_filter_client_transactions.return_value = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    inbound_hard_settle_posting,
                ],
                tside=self.tside,
            )
        }
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [],
        )

    def test_extract_debits_inbound_hard_settle_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # inbound postings are credits and are never included
        inbound_hard_settle_posting = self.inbound_hard_settlement(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )

        mock_filter_client_transactions.return_value = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    inbound_hard_settle_posting,
                ],
                tside=self.tside,
            )
        }
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [],
        )

    def test_extract_debits_custom_instruction(self, mock_filter_client_transactions: MagicMock):
        # custom instructions have none effects so we do not try to derive intent and classify them
        # as a debit
        mock_filter_client_transactions.return_value = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=sentinel.account_id,
                posting_instructions=[
                    self.custom_instruction(
                        amount=Decimal("1"),
                        postings=DEFAULT_POSTINGS,
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    ),
                ],
                tside=self.tside,
            )
        }
        self.assertListEqual(
            client_transaction_utils.extract_debits_by_instruction_details_key(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                value=sentinel.value,
            ),
            [],
        )


class TestFilterClientTransactionsByType(TestTransactionLimitUtils):
    def setUp(self) -> None:
        self.eligible_client_transaction = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("1"),
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    )
                ],
                tside=self.tside,
            )
        }
        return super().setUp()

    def test_filter_with_matching_key_value(
        self,
    ):
        self.assertDictEqual(
            client_transaction_utils.filter_client_transactions_by_type(
                denomination=self.default_denomination,
                client_transactions=self.eligible_client_transaction,
                key="type",
                values=["atm"],
            ),
            {"atm": self.eligible_client_transaction},
        )

    def test_filter_with_matching_key_value_and_multiple_txns(self):
        client_transactions = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("1"),
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    )
                ],
                tside=self.tside,
            ),
            CTX_ID_2: ClientTransaction(
                client_transaction_id=CTX_ID_2,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("1"),
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    )
                ],
                tside=self.tside,
            ),
        }

        self.assertEqual(
            client_transaction_utils.filter_client_transactions_by_type(
                denomination=self.default_denomination,
                client_transactions=client_transactions,
                key="type",
                values=["atm"],
            ),
            {"atm": client_transactions},
        )

    def test_filter_excludes_transaction_without_key(self):
        self.assertDictEqual(
            client_transaction_utils.filter_client_transactions_by_type(
                denomination=self.default_denomination,
                client_transactions=self.eligible_client_transaction,
                client_transaction_ids_to_ignore=[],
                key="other_type",
                values=["atm"],
            ),
            {"atm": {}},
        )

    def test_filter_excludes_transaction_with_wrong_value(
        self,
    ):
        self.assertDictEqual(
            client_transaction_utils.filter_client_transactions_by_type(
                denomination=self.default_denomination,
                client_transactions=self.eligible_client_transaction,
                client_transaction_ids_to_ignore=[""],
                key="type",
                values=["not_atm"],
            ),
            {"not_atm": {}},
        )

    def test_filter_excludes_transaction_with_id_to_ignore(
        self,
    ):
        self.assertDictEqual(
            client_transaction_utils.filter_client_transactions_by_type(
                denomination=self.default_denomination,
                client_transactions=self.eligible_client_transaction,
                client_transaction_ids_to_ignore=[CTX_ID_1],
                key="type",
                values=["atm"],
            ),
            {"atm": {}},
        )

    def test_filter_excludes_released_transaction(self):
        client_transactions = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_auth(
                        amount=Decimal("1"),
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    ),
                    self.release_outbound_auth(
                        unsettled_amount=Decimal("1"),
                    ),
                ],
                tside=self.tside,
            )
        }
        self.assertTrue(client_transactions[CTX_ID_1].released())

        self.assertDictEqual(
            client_transaction_utils.filter_client_transactions_by_type(
                denomination=self.default_denomination,
                client_transactions=client_transactions,
                client_transaction_ids_to_ignore=[],
                key="type",
                values=["atm"],
            ),
            {"atm": {}},
        )

    def test_filter_excludes_custom_instructions(self):
        client_transactions = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=sentinel.account_id,
                posting_instructions=[
                    self.custom_instruction(
                        amount=Decimal("1"),
                        postings=DEFAULT_POSTINGS,
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    ),
                ],
                tside=self.tside,
            )
        }

        self.assertEqual(
            client_transaction_utils.filter_client_transactions_by_type(
                denomination=self.default_denomination,
                client_transactions=client_transactions,
                client_transaction_ids_to_ignore=[""],
                key="type",
                values=["atm"],
            ),
            {"atm": {}},
        )

    def test_filter_excludes_different_denomination(
        self,
    ):
        self.assertEqual(
            client_transaction_utils.filter_client_transactions_by_type(
                denomination="BLA",
                client_transactions=self.eligible_client_transaction,
                client_transaction_ids_to_ignore=[""],
                key="type",
                values=["atm"],
            ),
            {"atm": {}},
        )

    def test_filter_with_multiple_eligible_types(self):
        atm_client_transactions = {
            CTX_ID_1: ClientTransaction(
                client_transaction_id=CTX_ID_1,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("1"),
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    )
                ],
                tside=self.tside,
            ),
            CTX_ID_2: ClientTransaction(
                client_transaction_id=CTX_ID_2,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("1"),
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "atm"},
                    )
                ],
                tside=self.tside,
            ),
        }
        pos_client_transactions = {
            CTX_ID_3: ClientTransaction(
                client_transaction_id=CTX_ID_3,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("1"),
                        value_datetime=CUT_OFF_DATE,
                        instruction_details={"type": "pos"},
                    )
                ],
                tside=self.tside,
            ),
        }
        client_transactions = atm_client_transactions | pos_client_transactions
        self.assertEqual(
            client_transaction_utils.filter_client_transactions_by_type(
                denomination=self.default_denomination,
                client_transactions=client_transactions,
                key="type",
                values=["atm", "pos", "other"],
            ),
            {"atm": atm_client_transactions, "pos": pos_client_transactions, "other": {}},
        )


class TestSumDebitsByType(TestTransactionLimitUtils):
    @patch.object(client_transaction_utils, "sum_client_transactions")
    @patch.object(client_transaction_utils, "filter_client_transactions_by_type")
    def test_sum_debits_by_instruction_details(
        self, mock_filter_transactions: MagicMock, mock_sum_client_transaction: MagicMock
    ):
        mock_filter_transactions.return_value = {
            sentinel.value_1: sentinel.filtered_transactions_1,
            sentinel.value_2: sentinel.filtered_transactions_2,
        }
        mock_sum_client_transaction.side_effect = [
            (sentinel.net_credit_1, sentinel.net_debit_1),
            (sentinel.net_credit_2, sentinel.net_debit_2),
        ]

        self.assertDictEqual(
            client_transaction_utils.sum_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=sentinel.client_transaction_ids_to_ignore,
                cutoff_datetime=sentinel.cutoff_datetime,
                key=sentinel.key,
                values=[sentinel.value_1, sentinel.value_2],
            ),
            {sentinel.value_1: sentinel.net_debit_1, sentinel.value_2: sentinel.net_debit_2},
        )
        mock_filter_transactions.assert_called_once_with(
            denomination=sentinel.denomination,
            client_transactions=sentinel.client_transactions,
            client_transaction_ids_to_ignore=sentinel.client_transaction_ids_to_ignore,
            key=sentinel.key,
            values=[sentinel.value_1, sentinel.value_2],
        )
        mock_sum_client_transaction.assert_has_calls(
            calls=[
                call(
                    cutoff_datetime=sentinel.cutoff_datetime,
                    client_transactions=sentinel.filtered_transactions_1,
                    denomination=sentinel.denomination,
                ),
                call(
                    cutoff_datetime=sentinel.cutoff_datetime,
                    client_transactions=sentinel.filtered_transactions_2,
                    denomination=sentinel.denomination,
                ),
            ]
        )


# We should ideally test get_total_transaction_impact separately and mock here. At the moment
# it's tested within sum_client_transactions, so we're repeating some tests
@patch.object(client_transaction_utils, "filter_client_transactions_by_type")
class TestExtractDebitsByType(TestTransactionLimitUtils):
    def test_extract_debits_filters_client_transactions(
        self, mock_filter_client_transactions: MagicMock
    ):
        mock_filter_client_transactions.return_value = {}
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=sentinel.cutoff_datetime,
                key=sentinel.key,
                values=[sentinel.value],
            ),
            {},
        )
        mock_filter_client_transactions.assert_called_once_with(
            denomination=sentinel.denomination,
            client_transactions=sentinel.client_transactions,
            client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
            key=sentinel.key,
            values=[sentinel.value],
        )

    def test_extract_debits_outbound_auth_settle_across_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # settle has no net debit impact to a previous auth
        auth_posting = self.outbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE - timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        settle_posting = self.settle_outbound_auth(
            amount=Decimal("1"),
            unsettled_amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            "atm": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=DEFAULT_ACCOUNT,
                    posting_instructions=[
                        auth_posting,
                        settle_posting,
                    ],
                    tside=self.tside,
                )
            }
        }
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm"],
            ),
            {"atm": []},
        )

    def test_extract_debits_outbound_auth_oversettle_across_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # oversettle has net debit impact == over settlement amount
        auth_posting = self.outbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE - timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        settle_posting = self.settle_outbound_auth(
            amount=Decimal("2"),
            unsettled_amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            "atm": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=DEFAULT_ACCOUNT,
                    posting_instructions=[
                        auth_posting,
                        settle_posting,
                    ],
                    tside=self.tside,
                )
            }
        }
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm"],
            ),
            {"atm": [settle_posting]},
        )

    def test_extract_debits_outbound_auth_settle_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # auth/settle after cut-off has net debit impact == auth amount
        auth_posting = self.outbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE,
            instruction_details={"type": "atm"},
        )
        settle_posting = self.settle_outbound_auth(
            amount=Decimal("1"),
            unsettled_amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            "atm": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=DEFAULT_ACCOUNT,
                    posting_instructions=[
                        auth_posting,
                        settle_posting,
                    ],
                    tside=self.tside,
                )
            }
        }
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm"],
            ),
            {"atm": [auth_posting]},
        )

    def test_extract_debits_outbound_auth_over_settle_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # auth over settle after cut-off has net debit impact == auth + over settlement amount
        auth_posting = self.outbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE,
            instruction_details={"type": "atm"},
        )
        settle_posting = self.settle_outbound_auth(
            amount=Decimal("2"),
            unsettled_amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            "atm": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=DEFAULT_ACCOUNT,
                    posting_instructions=[
                        auth_posting,
                        settle_posting,
                    ],
                    tside=self.tside,
                )
            }
        }
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm"],
            ),
            {"atm": [auth_posting, settle_posting]},
        )

    def test_extract_debits_outbound_auth_and_decrease_auth_adjustment_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # decreasing auth is a net credit, so only the original auth is a net debit
        auth_posting = self.outbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE,
            instruction_details={"type": "atm"},
        )
        adjust_posting = self.outbound_auth_adjust(
            amount=Decimal("-2"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            "atm": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=DEFAULT_ACCOUNT,
                    posting_instructions=[
                        auth_posting,
                        adjust_posting,
                    ],
                    tside=self.tside,
                )
            }
        }
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm"],
            ),
            {"atm": [auth_posting]},
        )

    def test_extract_debits_outbound_auth_and_increase_auth_adjustment_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # increasing auth is a net debit, so both auth and adjustment are returned
        auth_posting = self.outbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE,
            instruction_details={"type": "atm"},
        )
        adjust_posting = self.outbound_auth_adjust(
            amount=Decimal("2"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            "atm": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=DEFAULT_ACCOUNT,
                    posting_instructions=[
                        auth_posting,
                        adjust_posting,
                    ],
                    tside=self.tside,
                )
            }
        }
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm"],
            ),
            {"atm": [auth_posting, adjust_posting]},
        )

    def test_extract_debits_outbound_hard_settle_before_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # outbound hard settlement before cut-off is net 0 after the cut-off
        outbound_hard_settle_posting = self.outbound_hard_settlement(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE - timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )

        mock_filter_client_transactions.return_value = {
            "atm": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=DEFAULT_ACCOUNT,
                    posting_instructions=[
                        outbound_hard_settle_posting,
                    ],
                    tside=self.tside,
                )
            }
        }
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm"],
            ),
            {"atm": []},
        )

    def test_extract_debits_outbound_hard_settle_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # outbound hard settlement after cut-off is net debit after the cut-off for hard settlement
        # amount
        outbound_hard_settle_posting = self.outbound_hard_settlement(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )

        mock_filter_client_transactions.return_value = {
            "atm": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=DEFAULT_ACCOUNT,
                    posting_instructions=[
                        outbound_hard_settle_posting,
                    ],
                    tside=self.tside,
                )
            }
        }
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm"],
            ),
            {"atm": [outbound_hard_settle_posting]},
        )

    def test_extract_debits_inbound_auth_settle_across_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # inbound postings are credits and are never included
        auth_posting = self.inbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE - timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        settle_posting = self.settle_inbound_auth(
            amount=Decimal("1"),
            unsettled_amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            "atm": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=DEFAULT_ACCOUNT,
                    posting_instructions=[
                        auth_posting,
                        settle_posting,
                    ],
                    tside=self.tside,
                )
            }
        }
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm"],
            ),
            {"atm": []},
        )

    def test_extract_debits_inbound_auth_settle_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # inbound postings are credits and are never included

        auth_posting = self.inbound_auth(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE,
            instruction_details={"type": "atm"},
        )
        settle_posting = self.settle_inbound_auth(
            amount=Decimal("1"),
            unsettled_amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        mock_filter_client_transactions.return_value = {
            "atm": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=DEFAULT_ACCOUNT,
                    posting_instructions=[
                        auth_posting,
                        settle_posting,
                    ],
                    tside=self.tside,
                )
            }
        }
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm"],
            ),
            {"atm": []},
        )

    def test_extract_debits_inbound_hard_settle_before_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # inbound postings are credits and are never included
        inbound_hard_settle_posting = self.inbound_hard_settlement(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE - timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )

        mock_filter_client_transactions.return_value = {
            "atm": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=DEFAULT_ACCOUNT,
                    posting_instructions=[
                        inbound_hard_settle_posting,
                    ],
                    tside=self.tside,
                )
            }
        }
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm"],
            ),
            {"atm": []},
        )

    def test_extract_debits_inbound_hard_settle_after_cut_off(
        self, mock_filter_client_transactions: MagicMock
    ):
        # inbound postings are credits and are never included
        inbound_hard_settle_posting = self.inbound_hard_settlement(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )

        mock_filter_client_transactions.return_value = {
            "atm": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=DEFAULT_ACCOUNT,
                    posting_instructions=[
                        inbound_hard_settle_posting,
                    ],
                    tside=self.tside,
                )
            }
        }
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm"],
            ),
            {"atm": []},
        )

    def test_extract_debits_custom_instruction(self, mock_filter_client_transactions: MagicMock):
        # custom instructions have none effects so we do not try to derive intent and classify them
        # as a debit
        mock_filter_client_transactions.return_value = {
            "atm": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=sentinel.account_id,
                    posting_instructions=[
                        self.custom_instruction(
                            amount=Decimal("1"),
                            postings=DEFAULT_POSTINGS,
                            value_datetime=CUT_OFF_DATE,
                            instruction_details={"type": "atm"},
                        ),
                    ],
                    tside=self.tside,
                )
            }
        }
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm"],
            ),
            {"atm": []},
        )

    def test_extract_debits_multiple_types(self, mock_filter_client_transactions: MagicMock):
        # custom instructions have none effects so we do not try to derive intent and classify them
        # as a debit
        # outbound hard settlement after cut-off is net debit after the cut-off for hard settlement
        # amount
        outbound_hard_settle_posting = self.outbound_hard_settlement(
            amount=Decimal("1"),
            value_datetime=CUT_OFF_DATE + timedelta(minutes=1),
            instruction_details={"type": "atm"},
        )
        pos_client_transactions = {
            "pos": {
                CTX_ID_1: ClientTransaction(
                    client_transaction_id=CTX_ID_1,
                    account_id=DEFAULT_ACCOUNT,
                    posting_instructions=[
                        outbound_hard_settle_posting,
                    ],
                    tside=self.tside,
                )
            }
        }
        atm_client_transactions = {
            "atm": {
                CTX_ID_2: ClientTransaction(
                    client_transaction_id=CTX_ID_2,
                    account_id=sentinel.account_id,
                    posting_instructions=[
                        self.custom_instruction(
                            amount=Decimal("1"),
                            postings=DEFAULT_POSTINGS,
                            value_datetime=CUT_OFF_DATE,
                            instruction_details={"type": "atm"},
                        ),
                    ],
                    tside=self.tside,
                )
            }
        }
        other_client_transactions: dict[str, dict[str, ClientTransaction]] = {"other": {}}

        mock_filter_client_transactions.return_value = (
            pos_client_transactions | atm_client_transactions | other_client_transactions
        )
        self.assertDictEqual(
            client_transaction_utils.extract_debits_by_type(
                denomination=sentinel.denomination,
                client_transactions=sentinel.client_transactions,
                client_transaction_ids_to_ignore=[CTX_ID_DUMMY],
                cutoff_datetime=CUT_OFF_DATE,
                key=sentinel.key,
                values=["atm", "pos", "other"],
            ),
            {"pos": [outbound_hard_settle_posting], "atm": [], "other": []},
        )
