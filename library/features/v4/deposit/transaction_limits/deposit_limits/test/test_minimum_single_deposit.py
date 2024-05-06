# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.transaction_limits.deposit_limits import minimum_single_deposit
from library.features.v4.deposit.transaction_limits.test.test_common_transaction_limit import (
    CommonTransactionLimitTest,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    RejectionReason,
)


class TestMinimumSingleDeposit(CommonTransactionLimitTest):
    @patch.object(minimum_single_deposit.utils, "get_parameter")
    def test_minimum_single_deposit_ignore_withdrawal(self, mock_get_parameter: MagicMock):
        postings = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("1000"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_deposit": Decimal("0.01")}
        )
        self.assertIsNone(
            minimum_single_deposit.validate(
                vault=MagicMock(), postings=postings, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(minimum_single_deposit.utils, "get_parameter")
    def test_minimum_single_deposit_not_met(self, mock_get_parameter: MagicMock):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("0.001"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_deposit": Decimal("0.01")}
        )
        result = minimum_single_deposit.validate(
            vault=MagicMock(), postings=postings, denomination=DEFAULT_DENOMINATION
        )
        expected_rejection = Rejection(
            message=f"Transaction amount 0.001 {DEFAULT_DENOMINATION} is less than the minimum "
            f"deposit amount 0.01 {DEFAULT_DENOMINATION}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)

    @patch.object(minimum_single_deposit.utils, "get_parameter")
    def test_minimum_single_deposit_met(self, mock_get_parameter: MagicMock):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("0.01"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_deposit": Decimal("0.01")}
        )
        self.assertIsNone(
            minimum_single_deposit.validate(
                vault=MagicMock(), postings=postings, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(minimum_single_deposit.utils, "get_parameter")
    def test_minimum_single_deposit_all_posting_instructions_pass_the_limit(
        self, mock_get_parameter: MagicMock
    ):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("0.01")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("0.02")),
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION, amount=Decimal("0.03")
            ),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_deposit": Decimal("0.01")}
        )
        self.assertIsNone(
            minimum_single_deposit.validate(
                vault=MagicMock(), postings=postings, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(minimum_single_deposit.utils, "get_parameter")
    def test_minimum_single_deposit_one_posting_does_not_pass_the_limit(
        self, mock_get_parameter: MagicMock
    ):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("0.01")),
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("0.02")),
            self.inbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION, amount=Decimal("0.001")
            ),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_deposit": Decimal("0.01")}
        )
        result = minimum_single_deposit.validate(
            vault=MagicMock(), postings=postings, denomination=DEFAULT_DENOMINATION
        )
        expected_rejection = Rejection(
            message=f"Transaction amount 0.001 {DEFAULT_DENOMINATION} is less than the minimum "
            f"deposit amount 0.01 {DEFAULT_DENOMINATION}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)

    @patch.object(minimum_single_deposit.utils, "get_parameter")
    def test_minimum_single_deposit_exceeded(self, mock_get_parameter: MagicMock):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("0.011"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_deposit": Decimal("0.01")}
        )
        self.assertIsNone(
            minimum_single_deposit.validate(
                vault=MagicMock(), postings=postings, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(minimum_single_deposit.utils, "get_parameter")
    def test_minimum_single_deposit_exponent_logging(self, mock_get_parameter: MagicMock):
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("0.01"))
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"minimum_deposit": Decimal("10")}
        )
        result = minimum_single_deposit.validate(
            vault=MagicMock(), postings=postings, denomination=DEFAULT_DENOMINATION
        )
        expected_rejection = Rejection(
            message=f"Transaction amount 0.01 {DEFAULT_DENOMINATION} is less than the minimum "
            f"deposit amount 10 {DEFAULT_DENOMINATION}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)
