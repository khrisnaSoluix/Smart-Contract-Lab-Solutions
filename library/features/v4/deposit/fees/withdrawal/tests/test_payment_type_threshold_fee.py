# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.fees.withdrawal import payment_type_threshold_fee

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DENOMINATION,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
    Tside,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelPosting,
)


@patch.object(payment_type_threshold_fee.utils, "standard_instruction_details")
@patch.object(payment_type_threshold_fee.fees, "fee_postings")
@patch.object(payment_type_threshold_fee.utils, "get_parameter")
class TestPaymentTypeThresholdFee(FeatureTest):
    tside = Tside.LIABILITY
    payment_type_threshold_fees_map = {
        "DUITNOW_ACC": {"fee": "0.50", "threshold": "4000"},
        "ATM_IBFT_SANS": {"fee": "0.15", "threshold": "5000"},
    }
    payment_type_threshold_fees_parameters = {
        "payment_type_threshold_fee": payment_type_threshold_fees_map,
        "payment_type_fee_income_account": "PAYMENT_TYPE_FEE_INCOME_ACCOUNT",
    }

    def test_payment_type_threshold_fee_type_duitnow_acc_exceeded(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_threshold_fees_parameters
        )
        postings = [
            self.outbound_hard_settlement(
                amount=Decimal("4001"),
                instruction_details={"PAYMENT_TYPE": "DUITNOW_ACC"},
            )
        ]

        mock_fee_postings.return_value = [
            SentinelPosting("fee_posting_1"),
            SentinelPosting("fee_posting_2"),
        ]
        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = payment_type_threshold_fee.apply_fees(
            vault=mock_vault, postings=postings, denomination=DEFAULT_DENOMINATION
        )

        expected = [
            CustomInstruction(
                postings=[
                    SentinelPosting("fee_posting_1"),
                    SentinelPosting("fee_posting_2"),
                ],
                instruction_details=mock_standard_instruction_details.return_value,
                override_all_restrictions=True,
            )
        ]

        self.assertListEqual(results, expected)
        mock_fee_postings.assert_called_once()
        mock_standard_instruction_details.assert_called_once_with(
            description="payment fee on withdrawal more than 4000 for payment with type "
            "DUITNOW_ACC",
            event_type="APPLY_PAYMENT_TYPE_THRESHOLD_FEE",
            gl_impacted=True,
        )

    def test_payment_type_threshold_fee_type_duitnow_acc_not_exceeded(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_threshold_fees_parameters
        )
        postings = [
            self.outbound_hard_settlement(
                amount=Decimal("3999"),
                instruction_details={"PAYMENT_TYPE": "DUITNOW_ACC"},
            )
        ]

        results = payment_type_threshold_fee.apply_fees(
            vault=mock_vault, postings=postings, denomination=DEFAULT_DENOMINATION
        )

        self.assertListEqual(results, [])
        mock_fee_postings.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    def test_payment_type_threshold_fee_type_duitnow_acc_met(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_threshold_fees_parameters
        )
        postings = [
            self.outbound_hard_settlement(
                amount=Decimal("4000"),
                instruction_details={"PAYMENT_TYPE": "DUITNOW_ACC"},
            )
        ]

        results = payment_type_threshold_fee.apply_fees(
            vault=mock_vault, postings=postings, denomination=DEFAULT_DENOMINATION
        )

        self.assertListEqual(results, [])
        mock_fee_postings.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    def test_payment_type_threshold_fee_type_atm_ibft_sans_exceeded(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_threshold_fees_parameters
        )
        postings = [
            self.outbound_hard_settlement(
                amount=Decimal("5001"),
                instruction_details={"PAYMENT_TYPE": "ATM_IBFT_SANS"},
            )
        ]

        mock_fee_postings.return_value = [
            SentinelPosting("fee_posting_1"),
            SentinelPosting("fee_posting_2"),
        ]
        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = payment_type_threshold_fee.apply_fees(
            vault=mock_vault, postings=postings, denomination=DEFAULT_DENOMINATION
        )

        expected = [
            CustomInstruction(
                postings=[
                    SentinelPosting("fee_posting_1"),
                    SentinelPosting("fee_posting_2"),
                ],
                instruction_details=mock_standard_instruction_details.return_value,
                override_all_restrictions=True,
            )
        ]

        self.assertListEqual(results, expected)
        mock_fee_postings.assert_called_once()
        mock_standard_instruction_details.assert_called_once_with(
            description="payment fee on withdrawal more than 5000 for payment with type "
            "ATM_IBFT_SANS",
            event_type="APPLY_PAYMENT_TYPE_THRESHOLD_FEE",
            gl_impacted=True,
        )

    def test_payment_type_threshold_fee_type_unknown(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_threshold_fees_parameters
        )
        postings = [
            self.outbound_hard_settlement(
                amount=Decimal("5001"),
                instruction_details={"PAYMENT_TYPE": "UNKNOWN"},
            )
        ]

        results = payment_type_threshold_fee.apply_fees(
            vault=mock_vault, postings=postings, denomination=DEFAULT_DENOMINATION
        )

        self.assertListEqual(results, [])
        mock_fee_postings.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    def test_payment_type_threshold_fee_type_ignore_deposit(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_threshold_fees_parameters
        )
        postings = [
            self.inbound_hard_settlement(
                amount=Decimal("5001"),
                instruction_details={"PAYMENT_TYPE": "ATM_IBFT_SANS"},
            )
        ]

        results = payment_type_threshold_fee.apply_fees(
            vault=mock_vault, postings=postings, denomination=DEFAULT_DENOMINATION
        )

        self.assertListEqual(results, [])
        mock_fee_postings.assert_not_called()
        mock_standard_instruction_details.assert_not_called()
