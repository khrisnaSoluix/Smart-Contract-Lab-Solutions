# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.lending.amortisations.minimum_repayment as minimum_repayment
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)


class MinimumRepaymentCommon(FeatureTest):
    default_denomination = "GBP"
    tside = Tside.ASSET


@patch.object(minimum_repayment.utils, "get_parameter")
@patch.object(minimum_repayment.term_helpers, "calculate_elapsed_term")
class TermDetailsTest(FeatureTest):
    common_params = {"total_repayment_count": "10", "denomination": sentinel.denomination}

    def test_term_details_with_features(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "application_precision": 2,
                "denomination": sentinel.denomination,
                "total_repayment_count": 12,
            }
        )
        mock_calculate_elapsed_term.return_value = 4
        mock_principal_adjustments = [
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(1))),
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(10))),
        ]

        mock_vault = self.create_mock()
        result = minimum_repayment.term_details(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=False,
            interest_rate=None,
            principal_adjustments=mock_principal_adjustments,  # type: ignore
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        self.assertEqual(result, (4, 8))

    def test_term_details_without_features(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "application_precision": 2,
                "denomination": sentinel.denomination,
                "total_repayment_count": 12,
            }
        )
        mock_calculate_elapsed_term.return_value = 4

        balances_observation_fetchers_mapping = {
            minimum_repayment.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                SentinelBalancesObservation("effective")
            )
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping
        )
        result = minimum_repayment.term_details(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=False,
        )

        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances_effective, denomination=sentinel.denomination
        )
        self.assertEqual(result, (4, 8))

    def test_term_details_effective_date_equals_account_creation(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "total_repayment_count": 10,
            }
        )

        mock_vault = self.create_mock()
        result = minimum_repayment.term_details(
            vault=mock_vault,
            use_expected_term=False,
            effective_datetime=mock_vault.get_account_creation_datetime(),
        )

        self.assertEqual(result, (0, 10))


@patch.object(minimum_repayment.declining_principal, "apply_declining_principal_formula")
@patch.object(minimum_repayment.utils, "get_parameter")
@patch.object(minimum_repayment, "term_details")
class CalculateEmi(FeatureTest):
    def test_calculate_emi_no_optional_params_provided(
        self,
        mock_term_details: MagicMock,
        mock_get_parameter: MagicMock,
        mock_apply_declining_principal_formula: MagicMock,
    ):
        mock_term_details.return_value = sentinel.elapsed, sentinel.remaining
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "principal": sentinel.principal,
                "balloon_emi_amount": None,  # Return None to simulate unset param
                "balloon_payment_amount": sentinel.balloon_payment_amount,
            }
        )
        mock_apply_declining_principal_formula.return_value = sentinel.emi
        mock_vault = self.create_mock()

        result = minimum_repayment.calculate_emi(
            vault=mock_vault, effective_datetime=sentinel.effective_datetime
        )

        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=True,
            interest_rate=None,
            principal_adjustments=None,
            balances=None,
        )
        mock_apply_declining_principal_formula.assert_called_once_with(
            remaining_principal=sentinel.principal,
            interest_rate=Decimal(0),
            remaining_term=sentinel.remaining,
            lump_sum_amount=sentinel.balloon_payment_amount,
        )
        self.assertEqual(result, sentinel.emi)

    def test_calculate_emi_all_optional_params_provided(
        self,
        mock_term_details: MagicMock,
        mock_get_parameter: MagicMock,
        mock_apply_declining_principal_formula: MagicMock,
    ):
        mock_interest_feature = MagicMock()
        mock_interest_feature.get_monthly_interest_rate.return_value = sentinel.monthly_int_rate
        mock_term_details.return_value = sentinel.elapsed, sentinel.remaining
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "principal": sentinel.principal,
                "balloon_emi_amount": None,  # Return None to simulate unset param
                "balloon_payment_amount": sentinel.balloon_payment_amount,
                "denomination": sentinel.denomination,
            }
        )
        mock_principal_adjustments = [
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(1))),
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(49))),
        ]
        mock_apply_declining_principal_formula.return_value = sentinel.emi
        mock_vault = self.create_mock()

        result = minimum_repayment.calculate_emi(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=False,
            principal_amount=Decimal("100"),
            interest_calculation_feature=mock_interest_feature,
            principal_adjustments=mock_principal_adjustments,  # type: ignore
            balances=sentinel.balances,
        )

        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=False,
            interest_rate=mock_interest_feature,
            principal_adjustments=mock_principal_adjustments,
            balances=sentinel.balances,
        )

        mock_apply_declining_principal_formula.assert_called_once_with(
            remaining_principal=Decimal("150"),
            interest_rate=sentinel.monthly_int_rate,
            remaining_term=sentinel.remaining,
            lump_sum_amount=sentinel.balloon_payment_amount,
        )
        self.assertEqual(result, sentinel.emi)

    def test_calculate_emi_with_principal_0(
        self,
        mock_term_details: MagicMock,
        mock_get_parameter: MagicMock,
        mock_apply_minimum_repayment_formula: MagicMock,
    ):
        mock_interest_feature = MagicMock()
        mock_interest_feature.get_monthly_interest_rate.return_value = sentinel.monthly_int_rate
        mock_apply_minimum_repayment_formula.return_value = sentinel.emi
        mock_term_details.return_value = sentinel.elapsed, sentinel.remaining
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "principal": sentinel.principal,
                "balloon_emi_amount": None,  # Return None to simulate unset param
                "balloon_payment_amount": sentinel.balloon_payment_amount,
            }
        )
        mock_vault = self.create_mock()

        result = minimum_repayment.calculate_emi(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            principal_amount=Decimal("0"),
            interest_calculation_feature=mock_interest_feature,
            principal_adjustments=None,
        )

        mock_term_details.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=True,
            interest_rate=mock_interest_feature,
            principal_adjustments=None,
            balances=None,
        )

        mock_apply_minimum_repayment_formula.assert_called_once_with(
            remaining_principal=Decimal("0"),
            interest_rate=sentinel.monthly_int_rate,
            remaining_term=sentinel.remaining,
            lump_sum_amount=sentinel.balloon_payment_amount,
        )

        self.assertEqual(result, sentinel.emi)

    def test_calculate_emi_with_pre_defined_emi(
        self,
        mock_term_details: MagicMock,
        mock_get_parameter: MagicMock,
        mock_apply_minimum_repayment_formula: MagicMock,
    ):
        # Setup Mock Values to capture a wrong return in the test.
        mock_interest_feature = MagicMock()
        mock_interest_feature.get_monthly_interest_rate.return_value = sentinel.monthly_int_rate
        mock_apply_minimum_repayment_formula.return_value = sentinel.emi
        mock_term_details.return_value = sentinel.elapsed, sentinel.remaining
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "principal": sentinel.principal,
                "balloon_emi_amount": sentinel.balloon_emi_amount,
                "balloon_payment_amount": sentinel.balloon_payment_amount,
            }
        )
        mock_vault = self.create_mock()

        result = minimum_repayment.calculate_emi(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            principal_amount=Decimal("0"),
            interest_calculation_feature=mock_interest_feature,
            principal_adjustments=None,
        )

        mock_term_details.assert_not_called()

        mock_apply_minimum_repayment_formula.assert_not_called()

        self.assertEqual(result, sentinel.balloon_emi_amount)


class IsMinimumRepaymentLoanTest(FeatureTest):
    def test_is_minimum_repayment_loan_true(self):
        self.assertEqual(
            minimum_repayment.is_minimum_repayment_loan("MINIMUM_REPAYMENT_WITH_BALLOON_PAYMENT"),
            True,
        )

    def test_is_minimum_repayment_lower_case_true(self):
        self.assertEqual(
            minimum_repayment.is_minimum_repayment_loan("minimum_repayment_with_balloon_payment"),
            True,
        )

    def test_is_minimum_repayment_loan_false(self):
        self.assertEqual(minimum_repayment.is_minimum_repayment_loan("other"), False)
