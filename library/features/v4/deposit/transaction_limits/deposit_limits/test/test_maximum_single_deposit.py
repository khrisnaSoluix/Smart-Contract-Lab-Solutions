# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.transaction_limits.deposit_limits import maximum_single_deposit
from library.features.v4.deposit.transaction_limits.test.test_common_transaction_limit import (
    CommonTransactionLimitTest,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    RejectionReason,
)


class TestMaximumSingleDepositLimit(CommonTransactionLimitTest):
    @patch.object(maximum_single_deposit.utils, "get_parameter")
    def test_maximum_single_deposit_ignore_withdrawal(self, mock_get_parameter: MagicMock):
        postings = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("1000"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_deposit": Decimal("10")}
        )
        self.assertIsNone(
            maximum_single_deposit.validate(
                vault=MagicMock(), postings=postings, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(maximum_single_deposit.utils, "get_parameter")
    def test_maximum_single_deposit_exceeded(self, mock_get_parameter: MagicMock):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("11"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_deposit": Decimal("10")}
        )
        result = maximum_single_deposit.validate(
            vault=MagicMock(), postings=postings, denomination=DEFAULT_DENOMINATION
        )
        expected_rejection = Rejection(
            message=f"Transaction amount 11 {DEFAULT_DENOMINATION} is more than the maximum "
            f"permitted deposit amount 10 {DEFAULT_DENOMINATION}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)

    @patch.object(maximum_single_deposit.utils, "get_parameter")
    def test_maximum_single_deposit_met(self, mock_get_parameter: MagicMock):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("10"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_deposit": Decimal("10")}
        )
        self.assertIsNone(
            maximum_single_deposit.validate(
                vault=MagicMock(), postings=postings, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(maximum_single_deposit.utils, "get_parameter")
    def test_maximum_single_deposit_not_exceeded(self, mock_get_parameter: MagicMock):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("9"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_deposit": Decimal("10")}
        )
        self.assertIsNone(
            maximum_single_deposit.validate(
                vault=MagicMock(), postings=postings, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(maximum_single_deposit.utils, "get_parameter")
    def test_maximum_single_deposit_exceeded_reject_when_one_transaction_over_limit(
        self, mock_get_parameter: MagicMock
    ):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("8.75")),
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("100")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("9.99")),
            self.inbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION, amount=Decimal("10.01")
            ),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_deposit": Decimal("10")}
        )
        result = maximum_single_deposit.validate(
            vault=MagicMock(), postings=postings, denomination=DEFAULT_DENOMINATION
        )
        expected_rejection = Rejection(
            message=f"Transaction amount 10.01 {DEFAULT_DENOMINATION} is more than the maximum "
            f"permitted deposit amount 10 {DEFAULT_DENOMINATION}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)
