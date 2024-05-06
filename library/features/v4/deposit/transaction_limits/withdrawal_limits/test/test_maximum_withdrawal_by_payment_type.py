# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.transaction_limits.test.test_common_transaction_limit import (
    CommonTransactionLimitTest,
)
from library.features.v4.deposit.transaction_limits.withdrawal_limits import (
    maximum_withdrawal_by_payment_type,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    RejectionReason,
)


class TestMaximumWithdrawalByPaymentType(CommonTransactionLimitTest):
    @patch.object(maximum_withdrawal_by_payment_type.utils, "get_parameter")
    def test_maximum_withdrawal_by_payment_type_ignore_deposit(self, mock_get_parameter: MagicMock):
        posting_instructions = [
            self.inbound_hard_settlement(
                amount=Decimal("1000"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_1"}
            )
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_payment_type_withdrawal": {"PAYMENT_TYPE_1": "100", "PAYMENT_TYPE_2": "200"}}
        )
        mock_get_parameter.return_value = {"PAYMENT_TYPE_1": "100", "PAYMENT_TYPE_2": "200"}
        self.assertIsNone(
            maximum_withdrawal_by_payment_type.validate(
                vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(maximum_withdrawal_by_payment_type.utils, "get_parameter")
    def test_maximum_withdrawal_by_payment_type_1_exceeded(self, mock_get_parameter: MagicMock):
        posting_instructions = [
            self.outbound_hard_settlement(
                amount=Decimal("101"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_1"}
            )
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_payment_type_withdrawal": {"PAYMENT_TYPE_1": "100", "PAYMENT_TYPE_2": "200"}}
        )
        result = maximum_withdrawal_by_payment_type.validate(
            vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
        )
        expected_rejection = Rejection(
            message="Transaction amount 101.00 GBP is more than the maximum withdrawal "
            "amount 100 GBP allowed for the the payment type PAYMENT_TYPE_1.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)

    @patch.object(maximum_withdrawal_by_payment_type.utils, "get_parameter")
    def test_maximum_withdrawal_by_payment_type_1_not_exceeded(self, mock_get_parameter: MagicMock):
        posting_instructions = [
            self.outbound_hard_settlement(
                amount=Decimal("99"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_1"}
            )
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_payment_type_withdrawal": {"PAYMENT_TYPE_1": "100", "PAYMENT_TYPE_2": "200"}}
        )
        self.assertIsNone(
            maximum_withdrawal_by_payment_type.validate(
                vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(maximum_withdrawal_by_payment_type.utils, "get_parameter")
    def test_maximum_withdrawal_by_payment_type_1_multi_postings_do_not_exceed_limit(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.outbound_hard_settlement(
                amount=Decimal("99"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_1"}
            ),
            self.outbound_hard_settlement(
                amount=Decimal("200"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_3"}
            ),
            self.outbound_hard_settlement(
                amount=Decimal("100"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_1"}
            ),
            self.inbound_hard_settlement(
                amount=Decimal("100.01"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_1"}
            ),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_payment_type_withdrawal": {"PAYMENT_TYPE_1": "100", "PAYMENT_TYPE_2": "200"}}
        )
        self.assertIsNone(
            maximum_withdrawal_by_payment_type.validate(
                vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(maximum_withdrawal_by_payment_type.utils, "get_parameter")
    def test_maximum_withdrawal_by_payment_type_1_met(self, mock_get_parameter: MagicMock):
        posting_instructions = [
            self.outbound_hard_settlement(
                amount=Decimal("100"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_1"}
            )
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_payment_type_withdrawal": {"PAYMENT_TYPE_1": "100", "PAYMENT_TYPE_2": "200"}}
        )
        self.assertIsNone(
            maximum_withdrawal_by_payment_type.validate(
                vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(maximum_withdrawal_by_payment_type.utils, "get_parameter")
    def test_maximum_withdrawal_by_payment_type_2_exceeded(self, mock_get_parameter: MagicMock):
        posting_instructions = [
            self.outbound_hard_settlement(
                amount=Decimal("201"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_2"}
            )
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_payment_type_withdrawal": {"PAYMENT_TYPE_1": "100", "PAYMENT_TYPE_2": "200"}}
        )
        result = maximum_withdrawal_by_payment_type.validate(
            vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
        )
        expected_rejection = Rejection(
            message="Transaction amount 201.00 GBP is more than the maximum withdrawal "
            "amount 200 GBP allowed for the the payment type PAYMENT_TYPE_2.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)

    @patch.object(maximum_withdrawal_by_payment_type.utils, "get_parameter")
    def test_maximum_withdrawal_by_payment_type_2_not_exceeded(self, mock_get_parameter: MagicMock):
        posting_instructions = [
            self.outbound_hard_settlement(
                amount=Decimal("199"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_2"}
            )
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_payment_type_withdrawal": {"PAYMENT_TYPE_1": "100", "PAYMENT_TYPE_2": "200"}}
        )
        self.assertIsNone(
            maximum_withdrawal_by_payment_type.validate(
                vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(maximum_withdrawal_by_payment_type.utils, "get_parameter")
    def test_maximum_withdrawal_by_payment_type_2_met(self, mock_get_parameter: MagicMock):
        posting_instructions = [
            self.outbound_hard_settlement(
                amount=Decimal("200"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_2"}
            )
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_payment_type_withdrawal": {"PAYMENT_TYPE_1": "100", "PAYMENT_TYPE_2": "200"}}
        )
        self.assertIsNone(
            maximum_withdrawal_by_payment_type.validate(
                vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
            )
        )

    @patch.object(maximum_withdrawal_by_payment_type.utils, "get_parameter")
    def test_maximum_withdrawal_by_payment_type_2_multi_postings_exceeds_limit(
        self, mock_get_parameter: MagicMock
    ):
        posting_instructions = [
            self.inbound_hard_settlement(
                amount=Decimal("100"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_2"}
            ),
            self.outbound_hard_settlement(
                amount=Decimal("1000"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_3"}
            ),
            self.outbound_hard_settlement(
                amount=Decimal("35.12"), instruction_details={"REGION": "ASIA"}
            ),
            self.outbound_hard_settlement(
                amount=Decimal("100"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_2"}
            ),
            self.outbound_hard_settlement(
                amount=Decimal("200"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_2"}
            ),
            self.outbound_hard_settlement(
                amount=Decimal("200.01"), instruction_details={"PAYMENT_TYPE": "PAYMENT_TYPE_2"}
            ),
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"maximum_payment_type_withdrawal": {"PAYMENT_TYPE_1": "100", "PAYMENT_TYPE_2": "200"}}
        )
        result = maximum_withdrawal_by_payment_type.validate(
            vault=MagicMock(), postings=posting_instructions, denomination=DEFAULT_DENOMINATION
        )
        expected_rejection = Rejection(
            message="Transaction amount 200.01 GBP is more than the maximum withdrawal "
            "amount 200 GBP allowed for the the payment type PAYMENT_TYPE_2.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        self.assertEqual(result, expected_rejection)
