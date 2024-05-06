# standard libs
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.lending.amortisations import flat_interest

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DATETIME,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)


class IsFlatInterestLoanTest(FeatureTest):
    def test_is_flat_interest_loan_true(self):
        self.assertEqual(flat_interest.is_flat_interest_loan("FLAT_INTEREST"), True)

    def test_is_flat_interest_loan_lower_case_true(self):
        self.assertEqual(flat_interest.is_flat_interest_loan("flat_interest"), True)

    def test_is_flat_interest_loan_false(self):
        self.assertEqual(flat_interest.is_flat_interest_loan("other"), False)


@patch.object(flat_interest.utils, "balance_at_coordinates")
@patch.object(flat_interest.utils, "get_parameter")
@patch.object(flat_interest.term_helpers, "calculate_elapsed_term")
class TermDetailsTest(FeatureTest):

    common_params = {"total_repayment_count": "10", "denomination": sentinel.denomination}

    def test_term_details_with_features(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)
        mock_vault = self.create_mock()
        mock_calculate_elapsed_term.return_value = 1
        mock_balance_at_coordinates.return_value = Decimal("10")

        result = flat_interest.term_details(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertEqual(result, (1, 9))
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=flat_interest.lending_addresses.PRINCIPAL,
            denomination=sentinel.denomination,
        )

    def test_term_details_without_fetched_data(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)
        mock_calculate_elapsed_term.return_value = 1
        mock_balance_at_coordinates.return_value = Decimal("10")

        balances_observation_fetchers_mapping = {
            flat_interest.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                SentinelBalancesObservation("effective")
            )
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping
        )
        result = flat_interest.term_details(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
        )
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances_effective, denomination=sentinel.denomination
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances_effective,
            address=flat_interest.lending_addresses.PRINCIPAL,
            denomination=sentinel.denomination,
        )
        self.assertEqual(result, (1, 9))

    def test_term_details_effective_date_equals_account_creation(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)

        mock_vault = self.create_mock()
        result = flat_interest.term_details(
            vault=mock_vault,
            effective_datetime=mock_vault.get_account_creation_datetime(),
        )

        self.assertEqual(result, (0, 10))
        mock_calculate_elapsed_term.assert_not_called()
        mock_balance_at_coordinates.assert_not_called()

    def test_term_details_zero_principal(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)
        mock_vault = self.create_mock()
        mock_calculate_elapsed_term.return_value = 1
        mock_balance_at_coordinates.return_value = Decimal("0")

        result = flat_interest.term_details(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertEqual(result, (1, 0))
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=flat_interest.lending_addresses.PRINCIPAL,
            denomination=sentinel.denomination,
        )

    def test_term_details_negative_principal(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)
        mock_vault = self.create_mock()
        mock_calculate_elapsed_term.return_value = 1
        mock_balance_at_coordinates.return_value = Decimal("-10")

        result = flat_interest.term_details(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertEqual(result, (1, 0))
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=flat_interest.lending_addresses.PRINCIPAL,
            denomination=sentinel.denomination,
        )


@patch.object(flat_interest, "calculate_non_accruing_loan_total_interest")
@patch.object(flat_interest.utils, "get_parameter")
class CalculateEmi(FeatureTest):
    def test_calculate_emi_no_optional_params_provided(
        self,
        mock_get_parameter: MagicMock,
        mock_calculate_non_accruing_loan_total_interest: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"principal": Decimal("5000"), "total_repayment_count": 12}
        )
        mock_calculate_non_accruing_loan_total_interest.return_value = Decimal("1000")

        result = flat_interest.calculate_emi(
            vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
        )
        self.assertEqual(result, Decimal("500"))

        mock_calculate_non_accruing_loan_total_interest.assert_called_once_with(
            original_principal=Decimal("5000"),
            annual_interest_rate=Decimal(0),
            total_term=12,
        )

    def test_calculate_emi_all_optional_params_provided(
        self,
        mock_get_parameter: MagicMock,
        mock_calculate_non_accruing_loan_total_interest: MagicMock,
    ):

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination, "total_repayment_count": 12}
        )
        mock_calculate_non_accruing_loan_total_interest.return_value = Decimal("1000")

        mock_interest_feature = MagicMock()
        mock_interest_feature.get_annual_interest_rate.return_value = sentinel.annual_int_rate

        mock_principal_adjustments = [
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(1))),
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(49))),
        ]

        result = flat_interest.calculate_emi(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            principal_amount=Decimal("5000"),
            interest_calculation_feature=mock_interest_feature,
            principal_adjustments=mock_principal_adjustments,  # type: ignore
            balances=sentinel.balances,
        )

        # (principal + adjustments + total interest) / term
        # (5000 + 50 + 1000)/10 = 605
        self.assertEqual(result, Decimal("504.17"))

        mock_calculate_non_accruing_loan_total_interest.assert_called_once_with(
            original_principal=Decimal("5050"),
            annual_interest_rate=sentinel.annual_int_rate,
            total_term=12,
        )


@patch.object(flat_interest.utils, "yearly_to_monthly_rate")
@patch.object(flat_interest.utils, "round_decimal")
class TotalInterestTest(FeatureTest):
    def test_calculate_non_accruing_loan_total_interest_default_precision(
        self, mock_round_decimal: MagicMock, mock_yearly_to_monthly_rate: MagicMock
    ):
        mock_round_decimal.return_value = sentinel.total_interest
        mock_yearly_to_monthly_rate.return_value = Decimal("0.1")
        result = flat_interest.calculate_non_accruing_loan_total_interest(
            original_principal=Decimal("10"),
            annual_interest_rate=sentinel.annual_rate,
            total_term=6,
        )
        self.assertEqual(result, sentinel.total_interest)
        mock_round_decimal.assert_called_once_with(amount=Decimal("6"), decimal_places=2)

    def test_calculate_non_accruing_loan_total_interest_custom_precision(
        self, mock_round_decimal: MagicMock, mock_yearly_to_monthly_rate: MagicMock
    ):
        mock_round_decimal.return_value = sentinel.total_interest
        mock_yearly_to_monthly_rate.return_value = Decimal("0.1")
        result = flat_interest.calculate_non_accruing_loan_total_interest(
            original_principal=Decimal("10"),
            annual_interest_rate=sentinel.annual_rate,
            total_term=6,
            precision=sentinel.precision,
        )
        self.assertEqual(result, sentinel.total_interest)
        mock_round_decimal.assert_called_once_with(
            amount=Decimal("6"), decimal_places=sentinel.precision
        )


@patch.object(flat_interest.utils, "get_parameter")
@patch.object(flat_interest.interest_application, "get_application_precision")
@patch.object(flat_interest, "get_interest_to_apply")
@patch.object(flat_interest.fees, "fee_postings")
class ApplyInterestTest(FeatureTest):
    def test_apply_interest(
        self,
        mock_fee_postings: MagicMock,
        mock_get_interest_to_apply: MagicMock,
        mock_get_application_precision: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "interest_received_account": sentinel.internal_account,
                "denomination": sentinel.denomination,
            }
        )
        mock_get_application_precision.return_value = sentinel.precision
        mock_get_interest_to_apply.return_value = flat_interest.lending_interfaces.InterestAmounts(
            emi_accrued=sentinel.emi_accrued,
            emi_rounded_accrued=sentinel.emi_rounded_accrued,
            non_emi_accrued=sentinel.non_emi_accrued,
            non_emi_rounded_accrued=sentinel.non_emi_rounded_accrued,
            total_rounded=sentinel.total_rounded,
        )
        mock_fee_postings.return_value = sentinel.postings

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                flat_interest.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(  # noqa: E501
                    "effective"
                )
            }
        )

        self.assertEqual(
            flat_interest.apply_interest(
                vault=mock_vault,
                effective_datetime=sentinel.effective_datetime,
                previous_application_datetime=sentinel.previous_application_datetime,
            ),
            sentinel.postings,
        )
        mock_fee_postings.assert_called_once_with(
            customer_account_id=ACCOUNT_ID,
            customer_account_address="INTEREST_DUE",
            denomination=sentinel.denomination,
            amount=sentinel.total_rounded,
            internal_account=sentinel.internal_account,
        )
        mock_get_interest_to_apply.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            previous_application_datetime=sentinel.previous_application_datetime,
            balances_at_application=sentinel.balances_effective,
            denomination=sentinel.denomination,
            application_precision=sentinel.precision,
        )


@patch.object(flat_interest, "_calculate_interest_due")
@patch.object(flat_interest.term_helpers, "calculate_elapsed_term")
@patch.object(flat_interest, "calculate_non_accruing_loan_total_interest")
@patch.object(flat_interest.interest_application, "get_application_precision")
@patch.object(flat_interest.utils, "get_parameter")
class GetInterestToApplyTest(FeatureTest):
    common_params = {
        "principal": sentinel.principal,
        "total_repayment_count": Decimal("12"),
        "fixed_interest_rate": sentinel.fixed_interest_rate,
    }
    elapsed_term = 1
    expected_result = flat_interest.lending_interfaces.InterestAmounts(
        emi_accrued=Decimal("0"),
        emi_rounded_accrued=sentinel.interest_due,
        non_emi_accrued=Decimal("0"),
        non_emi_rounded_accrued=Decimal("0"),
        total_rounded=sentinel.interest_due,
    )

    def test_get_interest_to_apply_default_args(
        self,
        mock_get_parameter: MagicMock,
        mock_get_application_precision: MagicMock,
        mock_calculate_non_accruing_loan_total_interest: MagicMock,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_interest_due: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_params, "denomination": sentinel.denomination}
        )
        mock_get_application_precision.return_value = sentinel.precision
        mock_calculate_non_accruing_loan_total_interest.return_value = sentinel.total_interest
        mock_calculate_elapsed_term.return_value = self.elapsed_term
        mock_calculate_interest_due.return_value = sentinel.interest_due

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                flat_interest.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(  # noqa: E501
                    "effective"
                )
            }
        )

        self.assertEqual(
            flat_interest.get_interest_to_apply(
                vault=mock_vault,
                effective_datetime=sentinel.effective_datetime,
                previous_application_datetime=sentinel.previous_application_datetime,
            ),
            self.expected_result,
        )
        mock_calculate_non_accruing_loan_total_interest.assert_called_once_with(
            original_principal=sentinel.principal,
            annual_interest_rate=sentinel.fixed_interest_rate,
            total_term=12,
            precision=sentinel.precision,
        )
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances_effective, denomination=sentinel.denomination
        )
        mock_calculate_interest_due.assert_called_once_with(
            total_interest=sentinel.total_interest,
            total_term=12,
            remaining_term=11,
            precision=sentinel.precision,
        )

    def test_get_interest_to_apply_all_args_provided(
        self,
        mock_get_parameter: MagicMock,
        mock_get_application_precision: MagicMock,
        mock_calculate_non_accruing_loan_total_interest: MagicMock,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_interest_due: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters={**self.common_params})
        mock_get_application_precision.return_value = sentinel.precision
        mock_calculate_non_accruing_loan_total_interest.return_value = sentinel.total_interest
        mock_calculate_elapsed_term.return_value = self.elapsed_term
        mock_calculate_interest_due.return_value = sentinel.interest_due

        self.assertEqual(
            flat_interest.get_interest_to_apply(
                effective_datetime=sentinel.effective_datetime,
                previous_application_datetime=sentinel.previous_application_datetime,
                vault=sentinel.vault,
                balances_at_application=sentinel.balances,
                denomination=sentinel.denomination,
                application_precision=sentinel.precision,
            ),
            self.expected_result,
        )
        mock_calculate_non_accruing_loan_total_interest.assert_called_once_with(
            original_principal=sentinel.principal,
            annual_interest_rate=sentinel.fixed_interest_rate,
            total_term=12,
            precision=sentinel.precision,
        )
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_interest_due.assert_called_once_with(
            total_interest=sentinel.total_interest,
            total_term=12,
            remaining_term=11,
            precision=sentinel.precision,
        )
        mock_get_application_precision.assert_not_called()


@patch.object(flat_interest.utils, "round_decimal")
class CalculateInterestDueTest(FeatureTest):
    def test_calculate_interest_due_not_final_term(self, mock_round_decimal: MagicMock):
        mock_round_decimal.return_value = Decimal("120.12")

        result = flat_interest._calculate_interest_due(
            total_interest=Decimal("1000"),
            total_term=10,
            remaining_term=2,
            precision=sentinel.precision,
        )
        self.assertEqual(result, Decimal("120.12"))
        mock_round_decimal.assert_called_once_with(
            amount=Decimal("100"), decimal_places=sentinel.precision
        )

    def test_calculate_interest_due_final_term(self, mock_round_decimal: MagicMock):
        # 1000 / 12
        mock_round_decimal.return_value = Decimal("83.33")

        result = flat_interest._calculate_interest_due(
            total_interest=Decimal("1000"),
            total_term=12,
            remaining_term=1,
            precision=sentinel.precision,
        )
        # since remaining term is 1, we're on the final event and so the total remaining interest
        # (total loan interest - interest paid) should be become due
        # elapsed = 11 so total interest paid so far is 83.33 * 11 = 916.63
        # so we expected 1000 - 916.63 = 83.37 to be due
        self.assertEqual(result, Decimal("83.37"))
        mock_round_decimal.assert_called_once_with(
            amount=(Decimal("1000") / 12), decimal_places=sentinel.precision
        )
