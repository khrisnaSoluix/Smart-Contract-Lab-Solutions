# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.transaction_limits.test.test_common_transaction_limit import (
    CommonTransactionLimitTest,
)
from library.features.v4.deposit.transaction_limits.withdrawal_limits import (
    maximum_single_withdrawal,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    RejectionReason,
)


class TestMaximumSingleWithdrawal(CommonTransactionLimitTest):
    @patch.object(maximum_single_withdrawal.utils, "get_parameter")
    def test_maximum_single_withdrawal_ignore_deposit(self, mock_get_parameter: MagicMock):
        posting_instructions = [self.inbound_hard_settlement(amount=Decimal("1000"))]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_withdrawal": Decimal("100")}
        )
        self.assertIsNone(
            maximum_single_withdrawal.validate(
                vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(maximum_single_withdrawal.utils, "get_parameter")
    def test_maximum_single_withdrawal_exceeded(self, mock_get_parameter: MagicMock):
        posting_instructions = [self.outbound_hard_settlement(amount=Decimal("101"))]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_withdrawal": Decimal("100")}
        )
        result = maximum_single_withdrawal.validate(
            vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
        )
        expected_rejection = Rejection(
            message="Transaction amount 101 GBP is greater than the maximum withdrawal "
            "amount 100 GBP.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)

    @patch.object(maximum_single_withdrawal.utils, "get_parameter")
    def test_maximum_single_withdrawal_not_exceeded(self, mock_get_parameter: MagicMock):
        posting_instructions = [self.outbound_hard_settlement(amount=Decimal("99"))]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_withdrawal": Decimal("100")}
        )
        self.assertIsNone(
            maximum_single_withdrawal.validate(
                vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(maximum_single_withdrawal.utils, "get_parameter")
    def test_maximum_single_withdrawal_met(self, mock_get_parameter: MagicMock):
        posting_instructions = [self.outbound_hard_settlement(amount=Decimal("100"))]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_withdrawal": Decimal("100")}
        )
        self.assertIsNone(
            maximum_single_withdrawal.validate(
                vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(maximum_single_withdrawal.utils, "get_parameter")
    def test_maximum_single_withdrawal_several_postings_do_not_exceed_limit(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.inbound_hard_settlement(amount=Decimal("200")),
            self.outbound_hard_settlement(amount=Decimal("100")),
            self.outbound_hard_settlement(amount=Decimal("55")),
            self.outbound_hard_settlement(amount=Decimal("45.01")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_withdrawal": Decimal("100")}
        )
        self.assertIsNone(
            maximum_single_withdrawal.validate(
                vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(maximum_single_withdrawal.utils, "get_parameter")
    def test_maximum_single_withdrawal_several_postings_and_one_exceeds_limit(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.inbound_hard_settlement(amount=Decimal("200")),
            self.outbound_hard_settlement(amount=Decimal("100")),
            self.outbound_hard_settlement(amount=Decimal("45.01")),
            self.outbound_hard_settlement(amount=Decimal("100.01")),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_withdrawal": Decimal("100")}
        )
        result = maximum_single_withdrawal.validate(
            vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
        )
        expected_rejection = Rejection(
            message="Transaction amount 100.01 GBP is greater than the maximum withdrawal "
            "amount 100 GBP.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)
