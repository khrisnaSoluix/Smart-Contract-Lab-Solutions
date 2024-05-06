# standard libs
from decimal import Decimal
from unittest.mock import patch, sentinel

# features
import library.features.v4.lending.maximum_loan_principal as maximum_loan_principal
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    RejectionReason,
    Tside,
)


@patch.object(maximum_loan_principal.utils, "get_parameter")
class MaximumLoanAmountTest(FeatureTest):
    tside = Tside.ASSET
    common_param_return_values = {
        maximum_loan_principal.PARAM_MAXIMUM_LOAN_PRINCIPAL: Decimal("1000"),
        "denomination": "GBP",
    }

    def test_posting_less_than_max_amount_returns_none(self, mock_get_parameter):
        mock_vault = sentinel.vault
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_param_return_values
        )

        posting_instruction = self.outbound_hard_settlement(amount=Decimal("100"))

        actual = maximum_loan_principal.validate(
            mock_vault, posting_instruction=posting_instruction
        )
        self.assertIsNone(actual)

    def test_posting_equal_to_max_amount_returns_none(self, mock_get_parameter):
        mock_vault = sentinel.vault
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_param_return_values
        )

        posting_instruction = self.outbound_hard_settlement(amount=Decimal("1000"))

        actual = maximum_loan_principal.validate(
            mock_vault, posting_instruction=posting_instruction
        )
        self.assertIsNone(actual)

    def test_posting_greater_than_max_amount_returns_rejection(self, mock_get_parameter):
        mock_vault = sentinel.vault
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_param_return_values
        )

        posting_instruction = self.outbound_hard_settlement(amount=Decimal("1001"))

        expected = Rejection(
            message="Cannot create loan larger than maximum loan amount limit of: 1000.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        actual = maximum_loan_principal.validate(
            mock_vault, posting_instruction=posting_instruction
        )
        self.assertEqual(actual, expected)

    def test_not_setting_max_amount_returns_none(self, mock_get_parameter):
        mock_vault = sentinel.vault
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": "GBP",
                maximum_loan_principal.PARAM_MAXIMUM_LOAN_PRINCIPAL: None,
            }
        )

        posting_instruction = self.outbound_hard_settlement(amount=Decimal("1001"))

        actual = maximum_loan_principal.validate(
            mock_vault, posting_instruction=posting_instruction
        )
        self.assertIsNone(actual)
