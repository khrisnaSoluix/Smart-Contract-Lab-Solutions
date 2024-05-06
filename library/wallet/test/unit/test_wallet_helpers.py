# standard libs
from decimal import Decimal

# library
import library.wallet.contracts.template.wallet as contract
from library.wallet.test.unit.test_wallet_common import (
    DEFAULT_ACCOUNT_ID,
    DEFAULT_DENOMINATION,
    DEFAULT_NOMINATED_ACCOUNT,
    DUPLICATION,
    TODAYS_SPENDING,
    WalletTestBase,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    CustomInstruction,
    Phase,
    Posting,
)


class HelpersTest(WalletTestBase):
    def test_release_and_decreased_auth_includes_releases_and_decreased_outbound_auths(
        self,
    ):

        postings = [
            self.release_outbound_auth(unsettled_amount=Decimal(10), account_id=DEFAULT_ACCOUNT_ID),
            self.outbound_auth_adjust(amount=Decimal(-5), account_id=DEFAULT_ACCOUNT_ID),
            # None of the below should have any impact
            self.settle_outbound_auth(
                amount=Decimal(100),
                unsettled_amount=Decimal(100),
                final=True,
                account_id=DEFAULT_ACCOUNT_ID,
            ),
            self.inbound_hard_settlement(amount=Decimal(1000), account_id=DEFAULT_ACCOUNT_ID),
            self.outbound_auth_adjust(amount=Decimal(10000), account_id=DEFAULT_ACCOUNT_ID),
            self.inbound_auth_adjust(amount=Decimal(100000), account_id=DEFAULT_ACCOUNT_ID),
        ]

        amount = contract._get_release_and_decreased_auth_amount(
            postings=postings, denomination=DEFAULT_DENOMINATION
        )

        self.assertEqual(amount, Decimal(15))

    def test_sweep_excess_funds_negative_amount(
        self,
    ):
        posting_instruction = contract._sweep_excess_funds(
            account_id=DEFAULT_ACCOUNT_ID,
            amount=Decimal(-5),
            denomination=DEFAULT_DENOMINATION,
            nominated_account="2",
        )
        self.assertListEqual([], posting_instruction)

    def test_sweep_excess_funds_positive_amount(
        self,
    ):

        excess_amount = Decimal("500")
        posting_instruction = contract._sweep_excess_funds(
            account_id=DEFAULT_ACCOUNT_ID,
            amount=excess_amount,
            denomination=DEFAULT_DENOMINATION,
            nominated_account=DEFAULT_NOMINATED_ACCOUNT,
        )
        expected_postings = [
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=DEFAULT_NOMINATED_ACCOUNT,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                amount=excess_amount,
                phase=Phase.COMMITTED,
            ),
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=DEFAULT_ACCOUNT_ID,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                amount=excess_amount,
                phase=Phase.COMMITTED,
            ),
        ]

        expected_pi = [
            CustomInstruction(
                postings=expected_postings,
                instruction_details={"description": "RETURNING_EXCESS_BALANCE"},
                override_all_restrictions=True,
            )
        ]

        self.assertEqual(expected_pi, posting_instruction)

    def test_update_tracked_spend_amount_zero(
        self,
    ):
        posting_instruction = contract._update_tracked_spend(
            account_id=DEFAULT_ACCOUNT_ID,
            amount=Decimal(0),
            denomination=DEFAULT_DENOMINATION,
        )
        self.assertListEqual([], posting_instruction)

    def test_update_tracked_spend_amount_negative(
        self,
    ):
        # amount < 0 means spend.

        spend_amount = -Decimal("30")
        posting_instruction = contract._update_tracked_spend(
            account_id=DEFAULT_ACCOUNT_ID,
            amount=spend_amount,
            denomination=DEFAULT_DENOMINATION,
        )

        expected_postings = [
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=DEFAULT_ACCOUNT_ID,
                account_address=DUPLICATION,
                asset=DEFAULT_ASSET,
                credit=True,
                amount=abs(spend_amount),
                phase=Phase.COMMITTED,
            ),
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=DEFAULT_ACCOUNT_ID,
                account_address=TODAYS_SPENDING,
                asset=DEFAULT_ASSET,
                credit=False,
                amount=abs(spend_amount),
                phase=Phase.COMMITTED,
            ),
        ]

        expected_pi = [
            CustomInstruction(
                postings=expected_postings,
                instruction_details={"description": "UPDATING_TRACKED_SPEND"},
                override_all_restrictions=None,
            )
        ]

        self.assertEqual(expected_pi, posting_instruction)

    def test_update_tracked_spend_amount_positive(
        self,
    ):
        # amount > 0 means refund / release auth.

        spend_amount = Decimal("70")
        posting_instruction = contract._update_tracked_spend(
            account_id=DEFAULT_ACCOUNT_ID,
            amount=spend_amount,
            denomination=DEFAULT_DENOMINATION,
        )

        expected_postings = [
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=DEFAULT_ACCOUNT_ID,
                account_address=TODAYS_SPENDING,
                asset=DEFAULT_ASSET,
                credit=True,
                amount=abs(spend_amount),
                phase=Phase.COMMITTED,
            ),
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=DEFAULT_ACCOUNT_ID,
                account_address=DUPLICATION,
                asset=DEFAULT_ASSET,
                credit=False,
                amount=abs(spend_amount),
                phase=Phase.COMMITTED,
            ),
        ]

        expected_pi = [
            CustomInstruction(
                postings=expected_postings,
                instruction_details={"description": "UPDATING_TRACKED_SPEND"},
                override_all_restrictions=None,
            )
        ]

        self.assertEqual(expected_pi, posting_instruction)

    def test_update_tracked_spend_zero_out_daily_spend(
        self,
    ):
        # _update_tracked_spend will be called with a positive value
        # when called from _get_zero_out_daily_spend_instructions
        spend_amount = Decimal("70")

        # Zero out daily spend.
        posting_instruction = contract._update_tracked_spend(
            account_id=DEFAULT_ACCOUNT_ID,
            amount=spend_amount,
            denomination=DEFAULT_DENOMINATION,
            zero_out_daily_spend=True,
        )

        expected_postings = [
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=DEFAULT_ACCOUNT_ID,
                account_address=TODAYS_SPENDING,
                asset=DEFAULT_ASSET,
                credit=True,
                amount=spend_amount,
                phase=Phase.COMMITTED,
            ),
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=DEFAULT_ACCOUNT_ID,
                account_address=DUPLICATION,
                asset=DEFAULT_ASSET,
                credit=False,
                amount=spend_amount,
                phase=Phase.COMMITTED,
            ),
        ]

        expected_pi = [
            CustomInstruction(
                postings=expected_postings,
                instruction_details={"event_type": "ZERO_OUT_DAILY_SPENDING"},
                override_all_restrictions=True,
            )
        ]

        self.assertEqual(expected_pi, posting_instruction)

    def test_top_up_balance_zero(
        self,
    ):
        posting_instruction = contract._top_up_balance(
            account_id=DEFAULT_ACCOUNT_ID,
            amount=Decimal(0),
            denomination=DEFAULT_DENOMINATION,
            nominated_account="2",
        )
        self.assertListEqual([], posting_instruction)

    def test_top_up_balance_positive(
        self,
    ):

        transfer_amount = Decimal("80")
        posting_instruction = contract._top_up_balance(
            account_id=DEFAULT_ACCOUNT_ID,
            amount=transfer_amount,
            denomination=DEFAULT_DENOMINATION,
            nominated_account=DEFAULT_NOMINATED_ACCOUNT,
        )

        expected_postings = [
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=DEFAULT_ACCOUNT_ID,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                amount=transfer_amount,
                phase=Phase.COMMITTED,
            ),
            Posting(
                denomination=DEFAULT_DENOMINATION,
                account_id=DEFAULT_NOMINATED_ACCOUNT,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                amount=transfer_amount,
                phase=Phase.COMMITTED,
            ),
        ]

        expected_pi = [
            CustomInstruction(
                postings=expected_postings,
                instruction_details={
                    "description": "Auto top up transferred from nominated account:"
                    + str(transfer_amount)
                },
                override_all_restrictions=None,
            )
        ]

        self.assertEqual(expected_pi, posting_instruction)
