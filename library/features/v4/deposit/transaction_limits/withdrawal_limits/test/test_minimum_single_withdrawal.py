# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.transaction_limits.test.test_common_transaction_limit import (
    CommonTransactionLimitTest,
)
from library.features.v4.deposit.transaction_limits.withdrawal_limits import (
    minimum_single_withdrawal,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    RejectionReason,
)


class TestMinimumSingleWithdrawal(CommonTransactionLimitTest):
    @patch.object(minimum_single_withdrawal.utils, "get_parameter")
    def test_minimum_single_withdrawal_ignore_deposit(self, mock_get_parameter: MagicMock):
        posting_instructions = [self.inbound_hard_settlement(amount=Decimal("0.001"))]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_withdrawal": Decimal("0.01")}
        )
        self.assertIsNone(
            minimum_single_withdrawal.validate(
                vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(minimum_single_withdrawal.utils, "get_parameter")
    def test_minimum_single_withdrawal_not_met(self, mock_get_parameter: MagicMock):
        posting_instructions = [self.outbound_hard_settlement(amount=Decimal("0.001"))]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_withdrawal": Decimal("0.01")}
        )
        expected_rejection = Rejection(
            message="Transaction amount 0.001 GBP is less than the minimum withdrawal "
            "amount 0.01 GBP.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = minimum_single_withdrawal.validate(
            vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
        )
        self.assertEqual(result, expected_rejection)

    @patch.object(minimum_single_withdrawal.utils, "get_parameter")
    def test_minimum_single_withdrawal_exceeded(self, mock_get_parameter: MagicMock):
        posting_instructions = [self.outbound_hard_settlement(amount=Decimal("0.02"))]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_withdrawal": Decimal("0.01")}
        )
        self.assertIsNone(
            minimum_single_withdrawal.validate(
                vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(minimum_single_withdrawal.utils, "get_parameter")
    def test_minimum_single_withdrawal_met(self, mock_get_parameter: MagicMock):
        posting_instructions = [self.outbound_hard_settlement(amount=Decimal("0.01"))]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_withdrawal": Decimal("0.01")}
        )
        self.assertIsNone(
            minimum_single_withdrawal.validate(
                vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(minimum_single_withdrawal.utils, "get_parameter")
    def test_minimum_single_withdrawal_several_postings_one_doesnt_meet_limit(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.inbound_hard_settlement(amount=Decimal("0.001")),
            self.outbound_hard_settlement(amount=Decimal("100.001")),
            self.outbound_hard_settlement(amount=Decimal("0.01")),
            self.outbound_hard_settlement(amount=Decimal("0.00999")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_withdrawal": Decimal("0.01")}
        )
        result = minimum_single_withdrawal.validate(
            vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
        )
        expected_rejection = Rejection(
            message="Transaction amount 0.00999 GBP is less than the minimum withdrawal "
            "amount 0.01 GBP.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)
