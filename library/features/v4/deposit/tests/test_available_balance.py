# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# features
import library.features.v4.deposit.available_balance as feature

# contracts api
from contracts_api import BalanceDefaultDict, Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalance,
    SentinelCustomInstruction,
)


class IsWithdrawalExceedingAvailableBalance(FeatureTest):
    tside = Tside.LIABILITY

    @patch.object(feature.utils, "get_available_balance")
    def test_postings_exceeding_available_balance(self, mock_get_available_balance: MagicMock):
        balances = BalanceDefaultDict(
            mapping={self.balance_coordinate(denomination="USD"): SentinelBalance("dummy_balance")}
        )
        posting_instructions = [
            self.outbound_hard_settlement(denomination="USD", amount=Decimal("175"))
        ]
        mock_get_available_balance.side_effect = [Decimal("100"), Decimal("-175")]

        result = feature.validate(
            balances=balances,
            denominations=["USD"],
            posting_instructions=posting_instructions,
        )

        self.assertEqual(
            result,
            Rejection(
                message="Posting amount of 175 USD is exceeding available balance of 100 USD.",
                reason_code=RejectionReason.INSUFFICIENT_FUNDS,
            ),
        )

    @patch.object(feature.utils, "get_available_balance")
    def test_postings_exceeding_available_balance_multiple_supported_denomination(
        self, mock_get_available_balance: MagicMock
    ):
        posting_instructions = [
            self.inbound_hard_settlement(denomination=sentinel.denom_one, amount=Decimal("75")),
            self.outbound_hard_settlement(denomination=sentinel.denom_two, amount=Decimal("175")),
        ]
        mock_get_available_balance.side_effect = [
            # Checking balance and postings amount for denom_one
            Decimal("100"),
            Decimal("75"),
            Decimal("0"),
            # Checking balance and postings amount for denom_two
            Decimal("100"),
            Decimal("0"),
            Decimal("-175"),
        ]

        result = feature.validate(
            balances=sentinel.balances,
            denominations=[sentinel.denom_one, sentinel.denom_two],
            posting_instructions=posting_instructions,
        )

        self.assertEqual(
            result,
            Rejection(
                message=f"Posting amount of 175 {sentinel.denom_two} is exceeding "
                f"available balance of 100 {sentinel.denom_two}.",
                reason_code=RejectionReason.INSUFFICIENT_FUNDS,
            ),
        )
        self.assertEqual(mock_get_available_balance.call_count, 6)

        mock_get_available_balance.assert_has_calls(
            [
                call(balances=sentinel.balances, denomination=sentinel.denom_one),
                call(balances=posting_instructions[0].balances(), denomination=sentinel.denom_one),
                call(balances=posting_instructions[1].balances(), denomination=sentinel.denom_one),
                call(balances=sentinel.balances, denomination=sentinel.denom_two),
                call(balances=posting_instructions[0].balances(), denomination=sentinel.denom_two),
                call(balances=posting_instructions[1].balances(), denomination=sentinel.denom_two),
            ]
        )

    @patch.object(feature.utils, "get_available_balance")
    def test_postings_not_exceeding_available_balance(self, mock_get_available_balance: MagicMock):
        balances = BalanceDefaultDict(
            mapping={self.balance_coordinate(denomination="USD"): self.balance(net=Decimal("200"))}
        )
        posting_instructions = [
            self.outbound_hard_settlement(denomination="USD", amount=Decimal("175"))
        ]
        mock_get_available_balance.side_effect = [Decimal("200"), Decimal("-175")]

        result = feature.validate(
            balances=balances, denominations=["USD"], posting_instructions=posting_instructions
        )

        self.assertIsNone(result)

    def test_no_denominations_does_not_reject(self):
        result = feature.validate(
            balances=SentinelBalance("dummy_balance"),
            denominations=[],
            posting_instructions=[SentinelCustomInstruction("dummy_CI")],
        )

        self.assertIsNone(result)
