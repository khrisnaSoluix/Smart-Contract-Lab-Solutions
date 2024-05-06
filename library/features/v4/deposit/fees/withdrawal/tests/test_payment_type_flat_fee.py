# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.fees.withdrawal import payment_type_flat_fee

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


@patch.object(payment_type_flat_fee.utils, "standard_instruction_details")
@patch.object(payment_type_flat_fee.fees, "fee_postings")
@patch.object(payment_type_flat_fee.utils, "get_parameter")
class TestPaymentTypeFlatFee(FeatureTest):
    tside = Tside.LIABILITY
    payment_type_flat_fee_map = {
        "ATM_MEPS": "1",
        "ATM_VISAPLUS": "12",
    }
    payment_type_flat_fee_parameters = {
        "payment_type_flat_fee": payment_type_flat_fee_map,
        "payment_type_fee_income_account": "PAYMENT_TYPE_FEE_INCOME_ACCOUNT",
    }

    def test_payment_type_flat_fee_type_atm_meps(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_flat_fee_parameters
        )
        postings = [
            self.outbound_hard_settlement(
                amount=Decimal("1000"),
                instruction_details={"PAYMENT_TYPE": "ATM_MEPS"},
            )
        ]

        mock_fee_postings.return_value = [
            SentinelPosting("fee_posting_1"),
            SentinelPosting("fee_posting_2"),
        ]
        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = payment_type_flat_fee.apply_fees(
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
            description="payment fee applied for withdrawal using ATM_MEPS",
            event_type="APPLY_PAYMENT_TYPE_FLAT_FEE",
            gl_impacted=True,
        )

    def test_payment_type_flat_fee_type_atm_visaplus(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_flat_fee_parameters
        )
        postings = [
            self.outbound_hard_settlement(
                amount=Decimal("1000"),
                instruction_details={"PAYMENT_TYPE": "ATM_VISAPLUS"},
            )
        ]

        mock_fee_postings.return_value = [
            SentinelPosting("fee_posting_1"),
            SentinelPosting("fee_posting_2"),
        ]
        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = payment_type_flat_fee.apply_fees(
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
            description="payment fee applied for withdrawal using ATM_VISAPLUS",
            event_type="APPLY_PAYMENT_TYPE_FLAT_FEE",
            gl_impacted=True,
        )

    def test_payment_type_flat_fee_type_not_known(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_flat_fee_parameters
        )
        postings = [
            self.outbound_hard_settlement(
                amount=Decimal("1000"),
                instruction_details={"PAYMENT_TYPE": "UNKNOWN"},
            )
        ]

        results = payment_type_flat_fee.apply_fees(
            vault=mock_vault, postings=postings, denomination=DEFAULT_DENOMINATION
        )

        self.assertListEqual(results, [])
        mock_fee_postings.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    def test_payment_type_flat_fee_not_applied_to_deposit(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_flat_fee_parameters
        )
        postings = [self.inbound_hard_settlement(amount=Decimal("1000"))]

        results = payment_type_flat_fee.apply_fees(
            vault=mock_vault, postings=postings, denomination=DEFAULT_DENOMINATION
        )

        self.assertListEqual(results, [])
        mock_fee_postings.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    def test_payment_type_flat_fee_not_applied_to_deposit_with_payment_type(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_flat_fee_parameters
        )
        postings = [
            self.inbound_hard_settlement(
                amount=Decimal("1000"),
                instruction_details={"PAYMENT_TYPE": "ATM_VISAPLUS"},
            )
        ]

        results = payment_type_flat_fee.apply_fees(
            vault=mock_vault, postings=postings, denomination=DEFAULT_DENOMINATION
        )

        self.assertListEqual(results, [])
        mock_fee_postings.assert_not_called()
        mock_standard_instruction_details.assert_not_called()
