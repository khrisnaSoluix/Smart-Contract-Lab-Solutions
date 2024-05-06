# standard libs
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.lending.maximum_outstanding_loans as maximum_outstanding_loans
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    RejectionReason,
    Tside,
)


@patch.object(maximum_outstanding_loans.utils, "get_parameter")
class MaximumOutstandingLoansTest(FeatureTest):
    tside = Tside.ASSET
    param_name = maximum_outstanding_loans.PARAM_MAXIMUM_NUMBER_OF_OUTSTANDING_LOANS

    def test_less_than_max_loans_returns_none(self, mock_get_parameter: MagicMock):
        mock_loc_vault = sentinel.loc
        mock_loan_vaults = [
            sentinel.loan_1,
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter({self.param_name: 2})

        result = maximum_outstanding_loans.validate(
            main_vault=mock_loc_vault, loans=mock_loan_vaults
        )
        self.assertIsNone(result)
        mock_get_parameter.assert_called_once_with(vault=mock_loc_vault, name=self.param_name)

    def test_equal_to_max_loans_returns_rejection(self, mock_get_parameter: MagicMock):
        mock_loc_vault = sentinel.loc
        mock_loan_vaults = [
            sentinel.loan_1,
            sentinel.loan_2,
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter({self.param_name: 2})

        expected = Rejection(
            message="Cannot create new loan due to outstanding loan limit being exceeded. "
            + "Current number of loans: 2, maximum loan limit: 2.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = maximum_outstanding_loans.validate(
            main_vault=mock_loc_vault, loans=mock_loan_vaults
        )
        self.assertEqual(result, expected)
        mock_get_parameter.assert_called_once_with(vault=mock_loc_vault, name=self.param_name)

    def test_more_than_max_loans_returns_rejection(self, mock_get_parameter: MagicMock):
        mock_loc_vault = sentinel.loc
        mock_loan_vaults = [
            sentinel.loan_1,
            sentinel.loan_2,
            sentinel.loan_3,
        ]
        mock_get_parameter.side_effect = mock_utils_get_parameter({self.param_name: 2})

        expected = Rejection(
            message="Cannot create new loan due to outstanding loan limit being exceeded. "
            + "Current number of loans: 3, maximum loan limit: 2.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = maximum_outstanding_loans.validate(
            main_vault=mock_loc_vault, loans=mock_loan_vaults
        )
        self.assertEqual(result, expected)
        mock_get_parameter.assert_called_once_with(vault=mock_loc_vault, name=self.param_name)
