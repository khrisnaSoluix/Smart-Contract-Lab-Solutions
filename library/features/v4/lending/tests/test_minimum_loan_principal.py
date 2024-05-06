# standard libs
from decimal import Decimal
from unittest.mock import patch, sentinel

# features
import library.features.v4.lending.minimum_loan_principal as minimum_loan_principal
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    RejectionReason,
    Tside,
)


@patch.object(minimum_loan_principal.utils, "get_parameter")
class MinimumLoanAmountTest(FeatureTest):
    tside = Tside.ASSET
    common_param_return_values = {
        minimum_loan_principal.PARAM_MINIMUM_LOAN_PRINCIPAL: Decimal("50"),
        "denomination": "GBP",
    }

    def test_posting_greater_than_min_amount_returns_none(self, mock_get_parameter):
        mock_vault = sentinel.vault
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_param_return_values
        )

        posting_instruction = self.outbound_hard_settlement(amount=Decimal("100"))

        actual = minimum_loan_principal.validate(
            mock_vault, posting_instruction=posting_instruction
        )
        self.assertIsNone(actual)

    def test_posting_equal_to_min_amount_returns_none(self, mock_get_parameter):
        mock_vault = sentinel.vault
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_param_return_values
        )

        posting_instruction = self.outbound_hard_settlement(amount=Decimal("50"))

        actual = minimum_loan_principal.validate(
            mock_vault, posting_instruction=posting_instruction
        )
        self.assertIsNone(actual)

    def test_posting_less_than_min_amount_returns_rejection(self, mock_get_parameter):
        mock_vault = sentinel.vault
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.common_param_return_values
        )

        posting_instruction = self.outbound_hard_settlement(amount=Decimal("10"))

        expected = Rejection(
            message="Cannot create loan smaller than minimum loan amount limit of: 50.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        actual = minimum_loan_principal.validate(
            mock_vault, posting_instruction=posting_instruction
        )
        self.assertEqual(actual, expected)

    def test_not_setting_min_amount_returns_none(self, mock_get_parameter):
        mock_vault = sentinel.vault
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": "GBP",
                minimum_loan_principal.PARAM_MINIMUM_LOAN_PRINCIPAL: None,
            }
        )

        posting_instruction = self.outbound_hard_settlement(amount=Decimal("10"))

        actual = minimum_loan_principal.validate(
            mock_vault, posting_instruction=posting_instruction
        )
        self.assertIsNone(actual)
