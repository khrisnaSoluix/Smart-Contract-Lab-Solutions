# standard library
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

# inception imports
from inception_sdk.test_framework.contracts.unit.common import (
    ContractFeatureTest,
)
from inception_sdk.vault.contracts.types_extension import Tside
from library.features.deposits.transaction_limits.common.utils import (
    sum_client_transactions,
)

CUT_OFF_DATE = datetime(2019, 1, 1)
CLIENT_ID_1 = "client_id_1"
CLIENT_TRANSACTION_ID_1 = "client_transaction_id_1"


class TestTransactionLimitUtils(ContractFeatureTest):
    target_test_file = "library/features/deposits/transaction_limits/common/utils.py"
    side = Tside.LIABILITY

    def test_sum_client_transactions_handles_hard_settlement_deposits(self):
        """
        Sum should include pibs that are deposits
        """

        value_timestamp = CUT_OFF_DATE + timedelta(hours=1)

        (_, client_transactions, _,) = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=value_timestamp,
            posting_instructions_groups=[
                [
                    self.inbound_hard_settlement(
                        amount=Decimal("501"),
                        denomination="USD",
                        value_timestamp=value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    )
                ],
            ],
        )

        result = sum_client_transactions(
            denomination="USD",
            client_transactions=client_transactions,
            cutoff_timestamp=CUT_OFF_DATE,
        )

        self.assertEqual(result, (501, 0))

    def test_sum_client_transactions_handles_hard_settlement_withdrawals(self):
        """
        Sum should include pibs that are withdrawals
        """

        value_timestamp = CUT_OFF_DATE + timedelta(hours=1)

        (_, client_transactions, _,) = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=value_timestamp,
            posting_instructions_groups=[
                [
                    self.outbound_hard_settlement(
                        amount=Decimal("502"),
                        denomination="USD",
                        value_timestamp=value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    )
                ],
            ],
        )

        result = sum_client_transactions(
            denomination="USD",
            client_transactions=client_transactions,
            cutoff_timestamp=CUT_OFF_DATE,
        )

        self.assertEqual(result, (0, 502))

    def test_sum_client_transactions_handles_mix_of_txns(self):
        """
        Sum should include pibs of mixed transaction types (e.g. Deposits
        and Withdrawals)
        """

        value_timestamp = CUT_OFF_DATE + timedelta(hours=1)

        client_transaction_id_2 = "client_transaction_id_2"
        (_, client_transactions, _,) = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=value_timestamp,
            posting_instructions_groups=[
                [
                    self.inbound_hard_settlement(
                        amount=Decimal("501"),
                        denomination="USD",
                        value_timestamp=value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    ),
                ],
                [
                    self.outbound_hard_settlement(
                        amount=Decimal("501"),
                        denomination="USD",
                        value_timestamp=value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=client_transaction_id_2,
                    )
                ],
            ],
        )

        result = sum_client_transactions(
            denomination="USD",
            client_transactions=client_transactions,
            cutoff_timestamp=CUT_OFF_DATE,
        )

        self.assertEqual(result, (501, 501))

    def test_sum_client_transactions_settlement_value_not_counted_twice(self):
        """
        When summing client transactions including proposed, the
        function should consider chainable transactions
        and not double count an auth and a settlement
        """

        value_timestamp = CUT_OFF_DATE + timedelta(hours=1)

        (_, client_transactions, _,) = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=value_timestamp,
            posting_instructions_groups=[
                [
                    self.outbound_auth(
                        amount=Decimal("105"),
                        denomination="USD",
                        value_timestamp=value_timestamp - timedelta(minutes=1),
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    ),
                    self.settle_outbound_auth(
                        unsettled_amount=Decimal("105"),
                        amount=Decimal("105"),
                        denomination="USD",
                        value_timestamp=value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    ),
                ],
            ],
        )

        result = sum_client_transactions(
            denomination="USD",
            client_transactions=client_transactions,
            cutoff_timestamp=CUT_OFF_DATE,
        )

        self.assertEqual(result, (0, 105))

    def test_sum_client_transactions_handles_partial_settlements(self):
        """
        A partial settlement should not affect the sum of the client
        transactions as the settlement wasn't final so any value up to the
        original auth of 105 could still be settled
        """

        value_timestamp = CUT_OFF_DATE + timedelta(hours=1)

        (_, client_transactions, _,) = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=value_timestamp,
            posting_instructions_groups=[
                [
                    self.outbound_auth(
                        amount=Decimal("105"),
                        denomination="USD",
                        value_timestamp=value_timestamp - timedelta(minutes=1),
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    ),
                    self.settle_outbound_auth(
                        unsettled_amount=Decimal("105"),
                        amount=Decimal("40"),
                        denomination="USD",
                        value_timestamp=value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    ),
                ],
            ],
        )

        result = sum_client_transactions(
            denomination="USD",
            client_transactions=client_transactions,
            cutoff_timestamp=CUT_OFF_DATE,
        )

        self.assertEqual(result, (0, 105))

    def test_sum_client_transaction_handles_cancelled_transactions(self):
        """
        Sum should not include cancelled client transactions ids as the original
        funds that were authed have now be zero'd out
        """

        value_timestamp = CUT_OFF_DATE + timedelta(hours=1)

        (_, client_transactions, _,) = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=value_timestamp,
            posting_instructions_groups=[
                [
                    self.outbound_auth(
                        amount=Decimal("10"),
                        denomination="USD",
                        value_timestamp=value_timestamp - timedelta(minutes=1),
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    ),
                    self.release_outbound_auth(
                        unsettled_amount=Decimal("10"),
                        denomination="USD",
                        value_timestamp=value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    ),
                ]
            ],
        )

        result = sum_client_transactions(
            denomination="USD",
            client_transactions=client_transactions,
            cutoff_timestamp=CUT_OFF_DATE,
        )

        self.assertEqual(result, (0, 0))

    def test_sum_client_transactions_includes_transaction_on_cut_off(self):
        """
        Sum should include pib that takes place on the cut-off time
        """

        value_timestamp = CUT_OFF_DATE

        (_, client_transactions, _,) = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=value_timestamp,
            posting_instructions_groups=[
                [
                    self.outbound_hard_settlement(
                        amount=Decimal("501"),
                        denomination="USD",
                        value_timestamp=value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    )
                ],
            ],
        )

        result = sum_client_transactions(
            denomination="USD",
            client_transactions=client_transactions,
            cutoff_timestamp=CUT_OFF_DATE,
        )

        self.assertEqual(result, (0, 501))

    def test_sum_client_transactions_includes_transaction_after_cut_off(self):
        """
        Sum should include pib that takes place after the cut-off time
        """

        value_timestamp = CUT_OFF_DATE + timedelta(hours=1)

        (_, client_transactions, _,) = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=value_timestamp,
            posting_instructions_groups=[
                [
                    self.outbound_hard_settlement(
                        amount=Decimal("501"),
                        denomination="USD",
                        value_timestamp=value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    )
                ],
            ],
        )

        result = sum_client_transactions(
            denomination="USD",
            client_transactions=client_transactions,
            cutoff_timestamp=CUT_OFF_DATE,
        )

        self.assertEqual(result, (0, 501))

    def test_sum_client_transactions_excludes_transaction_before_cut_off(self):
        """
        Sum should not include a PIB with value_timestamp before the cut-off timeas it is not
        considered as part of that day's total
        """

        value_timestamp = CUT_OFF_DATE - timedelta(hours=1)

        (_, client_transactions, _,) = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=value_timestamp,
            posting_instructions_groups=[
                [
                    self.outbound_hard_settlement(
                        amount=Decimal("501"),
                        denomination="USD",
                        value_timestamp=value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    )
                ],
            ],
        )

        result = sum_client_transactions(
            denomination="USD",
            client_transactions=client_transactions,
            cutoff_timestamp=CUT_OFF_DATE,
        )

        self.assertEqual(result, (0, 0))

    def test_chainable_transactions_auth_adjust_cut_off_respected(self):
        """
        If an auth takes place before the cutoff time, only the
        proposed auth adjustment should contribute to the
        withdrawals.
        """

        previous_day_value_timestamp = CUT_OFF_DATE - timedelta(hours=23)
        value_timestamp = CUT_OFF_DATE + timedelta(hours=1)

        (_, client_transactions, _,) = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=value_timestamp,
            posting_instructions_groups=[
                [
                    self.outbound_auth(
                        amount=Decimal("90"),
                        denomination="USD",
                        value_timestamp=previous_day_value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    ),
                    self.outbound_auth_adjust(
                        amount=Decimal("40"),
                        denomination="USD",
                        value_timestamp=value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    ),
                ],
            ],
        )

        result = sum_client_transactions(
            denomination="USD",
            client_transactions=client_transactions,
            cutoff_timestamp=CUT_OFF_DATE,
        )

        self.assertEqual(result, (0, 40))

    def test_chainable_settlements_cut_off_respected(self):
        """
        If an auth takes place before the cutoff time, the proposed
        settlement should still not impact the the sum as it
        was already accounted for at the time of the auth.
        """

        previous_day_value_timestamp = CUT_OFF_DATE - timedelta(hours=23)
        value_timestamp = CUT_OFF_DATE + timedelta(hours=1)

        (_, client_transactions, _,) = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=value_timestamp,
            posting_instructions_groups=[
                [
                    self.outbound_auth(
                        amount=Decimal("90"),
                        denomination="USD",
                        value_timestamp=previous_day_value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    ),
                    self.settle_outbound_auth(
                        unsettled_amount=Decimal("90"),
                        amount=Decimal("90"),
                        denomination="USD",
                        value_timestamp=value_timestamp,
                        client_id=CLIENT_ID_1,
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                    ),
                ],
            ],
        )

        result = sum_client_transactions(
            denomination="USD",
            client_transactions=client_transactions,
            cutoff_timestamp=CUT_OFF_DATE,
        )

        self.assertEqual(result, (0, 0))


if __name__ == "__main__":
    unittest.main()
