# standard libs
from dateutil.relativedelta import relativedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.lending.amortisations.declining_principal as declining_principal
from library.features.v4.common.test.mocks import (
    mock_utils_get_parameter,
    mock_utils_get_parameter_for_multiple_vaults,
)

# contracts api
from contracts_api import Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.supervisor.common import (
    SupervisorFeatureTest,
)


class DecliningPrincipalCommon(FeatureTest):
    default_denomination = "GBP"
    tside = Tside.ASSET


class CalculateRemainingTermTest(DecliningPrincipalCommon):
    def test_no_emi_returns_zero(self):
        result = declining_principal.calculate_remaining_term(
            emi=Decimal("0"),
            remaining_principal=Decimal("100000"),
            monthly_interest_rate=Decimal("0.02"),
        )

        self.assertEqual(result, 0)

    @patch.object(declining_principal.utils, "round_decimal")
    def test_calculates_remaining_term_with_no_interest(self, mock_round_decimal: MagicMock):
        mock_round_decimal.return_value = Decimal("20")

        result = declining_principal.calculate_remaining_term(
            emi=Decimal("50"),
            remaining_principal=Decimal("1000"),
            monthly_interest_rate=Decimal("0"),
        )

        self.assertEqual(result, 20)
        mock_round_decimal.assert_called_once_with(
            amount=Decimal("20"), decimal_places=2, rounding=ROUND_HALF_UP
        )

    @patch.object(declining_principal.utils, "round_decimal")
    def test_calculates_remaining_term_with_eight_percent_interest(
        self, mock_round_decimal: MagicMock
    ):
        mock_round_decimal.return_value = Decimal("21.53")

        result = declining_principal.calculate_remaining_term(
            emi=Decimal("50"),
            remaining_principal=Decimal("1000"),
            monthly_interest_rate=Decimal("0.08") / Decimal("12"),
        )
        self.assertEqual(result, 22)
        mock_round_decimal.assert_called_once_with(
            amount=Decimal("21.536597731340794581456066225655376911163330078125"),
            decimal_places=2,
            rounding=ROUND_HALF_UP,
        )

    @patch.object(declining_principal.utils, "round_decimal")
    def test_calculates_remaining_term_with_different_rounding(self, mock_round_decimal: MagicMock):
        mock_round_decimal.return_value = Decimal("20.00")

        result = declining_principal.calculate_remaining_term(
            emi=Decimal("50"),
            remaining_principal=Decimal("1000"),
            monthly_interest_rate=Decimal("0"),
            decimal_places=2,
        )

        self.assertEqual(result, 20)
        mock_round_decimal.assert_called_once_with(
            amount=Decimal("20"), decimal_places=2, rounding=ROUND_HALF_UP
        )

    @patch.object(declining_principal.utils, "round_decimal")
    def test_calculates_remaining_term_with_different_rounding_strategy(
        self, mock_round_decimal: MagicMock
    ):
        mock_round_decimal.return_value = Decimal("20")

        result = declining_principal.calculate_remaining_term(
            emi=Decimal("50"),
            remaining_principal=Decimal("1000"),
            monthly_interest_rate=Decimal("0"),
            rounding=ROUND_CEILING,
        )

        self.assertEqual(result, Decimal("20"))
        mock_round_decimal.assert_called_once_with(
            amount=Decimal("20"), decimal_places=2, rounding=ROUND_CEILING
        )


@patch.object(declining_principal.utils, "get_parameter")
@patch.object(declining_principal.utils, "balance_at_coordinates")
@patch.object(declining_principal, "calculate_remaining_term")
@patch.object(declining_principal.term_helpers, "calculate_elapsed_term")
class TermDetailsTest(DecliningPrincipalCommon):

    common_params = {"total_repayment_count": "10", "denomination": sentinel.denomination}

    @staticmethod
    def mock_balances(balances, address, denomination):
        if address == declining_principal.lending_addresses.EMI:
            return Decimal(1)
        elif address == declining_principal.lending_addresses.PRINCIPAL:
            return Decimal(2)
        else:
            return Decimal(1000)

    def test_term_details_with_features(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)
        # can't use a sentinel for these return values they're used subtracted from original term
        #  and converted to int respectively
        mock_calculate_elapsed_term.return_value = 1
        mock_calculate_remaining_term.return_value = Decimal(8)
        mock_interest_rate = MagicMock(
            get_monthly_interest_rate=MagicMock(return_value=sentinel.monthly_interest_rate)
        )
        mock_principal_adjustments = [
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(1))),
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(10))),
        ]
        mock_balance_at_coordinates.side_effect = TermDetailsTest.mock_balances

        # create_mock uses DEFAULT_DATETIME as account_creation time
        mock_vault = self.create_mock()
        result = declining_principal.term_details(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            use_expected_term=False,
            interest_rate=mock_interest_rate,
            principal_adjustments=mock_principal_adjustments,  # type: ignore
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_called_once_with(
            emi=Decimal(1),
            # this is principal balance (2) + principal adjustments (1 + 10)
            remaining_principal=Decimal(13),
            monthly_interest_rate=sentinel.monthly_interest_rate,
        )
        self.assertEqual(result, (1, 8))

    def test_term_details_with_calculated_greater_than_original_minus_elapsed(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)
        # can't use a sentinel for these return values they're used subtracted from original term
        #  and converted to int respectively
        mock_calculate_elapsed_term.return_value = 1
        mock_calculate_remaining_term.return_value = Decimal("10")
        mock_interest_rate = MagicMock(
            get_monthly_interest_rate=MagicMock(return_value=sentinel.monthly_interest_rate)
        )
        mock_principal_adjustments = [
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(1))),
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(10))),
        ]
        mock_balance_at_coordinates.side_effect = TermDetailsTest.mock_balances

        # create_mock uses DEFAULT_DATETIME as account_creation time
        mock_vault = self.create_mock()
        result = declining_principal.term_details(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            use_expected_term=False,
            interest_rate=mock_interest_rate,
            principal_adjustments=mock_principal_adjustments,  # type: ignore
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_called_once_with(
            emi=Decimal(1),
            # this is principal balance (2) + principal adjustments (1 + 10)
            remaining_principal=Decimal(13),
            monthly_interest_rate=sentinel.monthly_interest_rate,
        )
        self.assertEqual(result, (1, 9))

    def test_term_details_without_features(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)
        # can't use a sentinel for these return values they're used subtracted from original term
        #  and converted to int respectively
        mock_calculate_elapsed_term.return_value = 1
        mock_calculate_remaining_term.return_value = Decimal(8)

        mock_balance_at_coordinates.side_effect = TermDetailsTest.mock_balances

        # create_mock uses DEFAULT_DATETIME as account_creation time
        mock_vault = self.create_mock()

        result = declining_principal.term_details(
            vault=mock_vault,
            use_expected_term=False,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_called_once_with(
            # emi and principal as per the mock_balances as there are no adjustment features
            emi=Decimal(1),
            remaining_principal=Decimal(2),
            monthly_interest_rate=Decimal(0),
        )
        self.assertEqual(result, (1, 8))

    def test_term_details_without_fetched_data(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)
        # can't use a sentinel for these return values they're used subtracted from original term
        #  and converted to int respectively
        mock_calculate_elapsed_term.return_value = 1
        mock_calculate_remaining_term.return_value = Decimal(8)
        mock_interest_rate = MagicMock(
            get_monthly_interest_rate=MagicMock(return_value=sentinel.monthly_interest_rate)
        )
        mock_principal_adjustments = [
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(1))),
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(10))),
        ]
        mock_balance_at_coordinates.side_effect = TermDetailsTest.mock_balances

        balances_observation_fetchers_mapping = {
            declining_principal.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                SentinelBalancesObservation("effective")
            )
        }

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping
        )

        result = declining_principal.term_details(
            vault=mock_vault,
            use_expected_term=False,
            effective_datetime=sentinel.effective_datetime,
            interest_rate=mock_interest_rate,
            principal_adjustments=mock_principal_adjustments,  # type: ignore
        )

        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances_effective, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_called_once_with(
            emi=Decimal(1),
            # this is principal balance (2) + principal adjustments (1 + 10)
            remaining_principal=Decimal(13),
            monthly_interest_rate=sentinel.monthly_interest_rate,
        )
        self.assertEqual(result, (1, 8))

    def test_term_details_effective_date_equals_account_creation(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_balance_at_coordinates.return_value = Decimal("0")
        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)

        mock_vault = self.create_mock()
        result = declining_principal.term_details(
            vault=mock_vault,
            use_expected_term=False,
            effective_datetime=mock_vault.get_account_creation_datetime(),
        )

        self.assertEqual(result, (0, 10))

    def test_term_details_without_emi_uses_elapsed_and_original_term(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_calculate_elapsed_term.return_value = 1
        # principal, overpayment
        mock_balance_at_coordinates.side_effect = [Decimal("10"), Decimal("0")]
        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)

        # create_mock uses DEFAULT_DATETIME as account_creation time
        mock_vault = self.create_mock()

        result = declining_principal.term_details(
            vault=mock_vault,
            use_expected_term=False,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, (1, 9))
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_not_called()

    def test_term_details_with_use_expected_term_uses_elapsed_and_original_term(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_calculate_elapsed_term.return_value = 1
        mock_balance_at_coordinates.return_value = Decimal("10")
        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)

        # create_mock uses DEFAULT_DATETIME as account_creation time
        mock_vault = self.create_mock()

        result = declining_principal.term_details(
            vault=mock_vault,
            use_expected_term=True,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, (1, 9))
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_not_called()

    def test_term_details_with_use_expected_term_with_zero_principal(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_calculate_elapsed_term.return_value = 1
        mock_balance_at_coordinates.return_value = Decimal("0")
        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)

        # create_mock uses DEFAULT_DATETIME as account_creation time
        mock_vault = self.create_mock()

        result = declining_principal.term_details(
            vault=mock_vault,
            use_expected_term=True,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, (1, 0))
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_not_called()

    def test_term_details_with_use_expected_term_with_negative_principal(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_calculate_elapsed_term.return_value = 1
        mock_balance_at_coordinates.return_value = Decimal("-10")
        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)

        # create_mock uses DEFAULT_DATETIME as account_creation time
        mock_vault = self.create_mock()

        result = declining_principal.term_details(
            vault=mock_vault,
            use_expected_term=True,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, (1, 0))
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_not_called()


@patch.object(declining_principal.utils, "get_parameter")
@patch.object(declining_principal.utils, "balance_at_coordinates")
@patch.object(declining_principal, "calculate_remaining_term")
@patch.object(declining_principal.term_helpers, "calculate_elapsed_term")
class SupervisorTermDetailsTest(DecliningPrincipalCommon):

    common_params = {"total_repayment_count": "10", "denomination": sentinel.denomination}

    @staticmethod
    def mock_balances(balances, address, denomination):
        if address == declining_principal.lending_addresses.EMI:
            return Decimal(1)
        elif address == declining_principal.lending_addresses.PRINCIPAL:
            return Decimal(2)
        else:
            return Decimal(1000)

    def test_term_details_with_features(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            SupervisorTermDetailsTest.common_params
        )
        # can't use a sentinel for these return values they're used subtracted from original term
        #  and converted to int respectively
        mock_calculate_elapsed_term.return_value = 1
        mock_calculate_remaining_term.return_value = Decimal(8)
        mock_interest_rate = MagicMock(
            get_monthly_interest_rate=MagicMock(return_value=sentinel.monthly_interest_rate)
        )
        mock_principal_adjustments = [
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(1))),
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(10))),
        ]
        mock_balance_at_coordinates.side_effect = SupervisorTermDetailsTest.mock_balances

        loan_vault = self.create_mock()

        result = declining_principal.supervisor_term_details(
            loan_vault=loan_vault,
            main_vault=sentinel.main_vault,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            use_expected_term=False,
            interest_rate=mock_interest_rate,
            principal_adjustments=mock_principal_adjustments,  # type: ignore
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_called_once_with(
            emi=Decimal(1),
            # this is principal balance (2) + principal adjustments (1 + 10)
            remaining_principal=Decimal(13),
            monthly_interest_rate=sentinel.monthly_interest_rate,
        )
        self.assertEqual(result, (1, 8))

    def test_term_details_with_calculated_greater_than_original_minus_elapsed(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            SupervisorTermDetailsTest.common_params
        )
        # can't use a sentinel for these return values they're used subtracted from original term
        #  and converted to int respectively
        mock_calculate_elapsed_term.return_value = 1
        mock_calculate_remaining_term.return_value = Decimal("10")
        mock_interest_rate = MagicMock(
            get_monthly_interest_rate=MagicMock(return_value=sentinel.monthly_interest_rate)
        )
        mock_principal_adjustments = [
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(1))),
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(10))),
        ]
        mock_balance_at_coordinates.side_effect = SupervisorTermDetailsTest.mock_balances

        loan_vault = self.create_mock()

        result = declining_principal.supervisor_term_details(
            loan_vault=loan_vault,
            main_vault=sentinel.main_vault,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            use_expected_term=False,
            interest_rate=mock_interest_rate,
            principal_adjustments=mock_principal_adjustments,  # type: ignore
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_called_once_with(
            emi=Decimal(1),
            # this is principal balance (2) + principal adjustments (1 + 10)
            remaining_principal=Decimal(13),
            monthly_interest_rate=sentinel.monthly_interest_rate,
        )
        self.assertEqual(result, (1, 9))

    def test_term_details_without_features(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            SupervisorTermDetailsTest.common_params
        )
        # can't use a sentinel for these return values they're used subtracted from original term
        #  and converted to int respectively
        mock_calculate_elapsed_term.return_value = 1
        mock_calculate_remaining_term.return_value = Decimal(8)

        mock_balance_at_coordinates.side_effect = SupervisorTermDetailsTest.mock_balances

        loan_vault = self.create_mock()

        result = declining_principal.supervisor_term_details(
            loan_vault=loan_vault,
            main_vault=sentinel.main_vault,
            use_expected_term=False,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_called_once_with(
            # emi and principal as per the mock_balances as there are no adjustment features
            emi=Decimal(1),
            remaining_principal=Decimal(2),
            monthly_interest_rate=Decimal(0),
        )
        self.assertEqual(result, (1, 8))

    def test_term_details_without_fetched_data(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            SupervisorTermDetailsTest.common_params
        )
        # can't use a sentinel for these return values they're used subtracted from original term
        #  and converted to int respectively
        mock_calculate_elapsed_term.return_value = 1
        mock_calculate_remaining_term.return_value = Decimal(8)
        mock_interest_rate = MagicMock(
            get_monthly_interest_rate=MagicMock(return_value=sentinel.monthly_interest_rate)
        )
        mock_principal_adjustments = [
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(1))),
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(10))),
        ]
        mock_balance_at_coordinates.side_effect = SupervisorTermDetailsTest.mock_balances

        balances_observation_fetchers_mapping = {
            declining_principal.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                SentinelBalancesObservation("effective")
            )
        }

        loan_vault = self.create_mock(
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping
        )

        result = declining_principal.supervisor_term_details(
            loan_vault=loan_vault,
            main_vault=sentinel.main_vault,
            use_expected_term=False,
            effective_datetime=sentinel.effective_datetime,
            interest_rate=mock_interest_rate,
            principal_adjustments=mock_principal_adjustments,  # type: ignore
        )

        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances_effective, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_called_once_with(
            emi=Decimal(1),
            # this is principal balance (2) + principal adjustments (1 + 10)
            remaining_principal=Decimal(13),
            monthly_interest_rate=sentinel.monthly_interest_rate,
        )
        self.assertEqual(result, (1, 8))

    def test_term_details_effective_date_equals_account_creation(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_balance_at_coordinates.return_value = Decimal("0")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            SupervisorTermDetailsTest.common_params
        )

        loan_vault = self.create_mock()

        result = declining_principal.supervisor_term_details(
            loan_vault=loan_vault,
            main_vault=sentinel.main_vault,
            use_expected_term=False,
            effective_datetime=loan_vault.get_account_creation_datetime(),
        )

        self.assertEqual(result, (0, 10))

    def test_term_details_without_emi_uses_elapsed_and_original_term(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_calculate_elapsed_term.return_value = 1
        # principal, overpayment
        mock_balance_at_coordinates.side_effect = [Decimal("10"), Decimal("0")]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            SupervisorTermDetailsTest.common_params
        )

        loan_vault = self.create_mock()

        result = declining_principal.supervisor_term_details(
            loan_vault=loan_vault,
            main_vault=sentinel.main_vault,
            use_expected_term=False,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, (1, 9))
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_not_called()

    def test_term_details_with_use_expected_term_uses_elapsed_and_original_term(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_calculate_elapsed_term.return_value = 1
        mock_balance_at_coordinates.return_value = Decimal("10")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            SupervisorTermDetailsTest.common_params
        )

        loan_vault = self.create_mock()

        result = declining_principal.supervisor_term_details(
            loan_vault=loan_vault,
            main_vault=sentinel.main_vault,
            use_expected_term=True,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, (1, 9))
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_not_called()

    def test_term_details_with_use_expected_term_with_zero_principal(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_calculate_elapsed_term.return_value = 1
        mock_balance_at_coordinates.return_value = Decimal("0")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            SupervisorTermDetailsTest.common_params
        )

        loan_vault = self.create_mock()

        result = declining_principal.supervisor_term_details(
            loan_vault=loan_vault,
            main_vault=sentinel.main_vault,
            use_expected_term=True,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, (1, 0))
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_not_called()

    def test_term_details_with_use_expected_term_with_negative_principal(
        self,
        mock_calculate_elapsed_term: MagicMock,
        mock_calculate_remaining_term: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_calculate_elapsed_term.return_value = 1
        mock_balance_at_coordinates.return_value = Decimal("-10")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            SupervisorTermDetailsTest.common_params
        )

        loan_vault = self.create_mock()

        result = declining_principal.supervisor_term_details(
            loan_vault=loan_vault,
            main_vault=sentinel.main_vault,
            use_expected_term=True,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, (1, 0))
        mock_calculate_elapsed_term.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_calculate_remaining_term.assert_not_called()


class DecliningPrincipalTest(FeatureTest):
    def test_calculate_declining_principal_0_lump_sum(self):
        # (100*0.02)*((1+0.02)^2)/(((1+0.02)^1)-1) = 51.50
        expected = Decimal("51.50")
        actual = declining_principal.apply_declining_principal_formula(
            remaining_principal=Decimal("100"),
            interest_rate=Decimal("0.02"),
            remaining_term=2,
            fulfillment_precision=2,
            lump_sum_amount=Decimal("0"),
        )
        self.assertEqual(expected, actual)

    def test_calculate_declining_principal_lump_sum_set_to_none(self):
        # (100*0.02)*((1+0.02)^2)/(((1+0.02)^1)-1) = 51.50
        expected = Decimal("51.50")
        actual = declining_principal.apply_declining_principal_formula(
            remaining_principal=Decimal("100"),
            interest_rate=Decimal("0.02"),
            remaining_term=2,
            fulfillment_precision=2,
            lump_sum_amount=None,
        )
        self.assertEqual(expected, actual)

    def test_calculate_declining_principal_lump_sum_greater_than_zero(self):
        # (100000-(50000/(1+0.02/12)^2))*0.02/12*(1+0.02/12)^2/(1+0.02/12)^2-1 =1515.46
        expected = Decimal("1515.46")
        actual = declining_principal.apply_declining_principal_formula(
            remaining_principal=Decimal("100000"),
            interest_rate=Decimal("0.02") / Decimal("12"),
            remaining_term=36,
            fulfillment_precision=2,
            lump_sum_amount=Decimal("50000"),
        )
        self.assertEqual(expected, actual)

    def test_calculate_declining_principal_zero_interest_rate(self):
        # (100/2)
        expected = Decimal("50")
        actual = declining_principal.apply_declining_principal_formula(
            remaining_principal=Decimal("100"),
            interest_rate=Decimal("0"),
            remaining_term=2,
            fulfillment_precision=2,
            lump_sum_amount=Decimal("0"),
        )
        self.assertEqual(expected, actual)

    def test_calculate_declining_principal_zero_remaining_term(self):
        expected = Decimal("100")
        actual = declining_principal.apply_declining_principal_formula(
            remaining_principal=Decimal("100"),
            interest_rate=Decimal("0.01"),
            remaining_term=0,
        )
        self.assertEqual(expected, actual)

    def test_calculate_declining_principal_zero_remaining_term_and_principal(self):
        expected = Decimal("0")
        actual = declining_principal.apply_declining_principal_formula(
            remaining_principal=Decimal("0"),
            interest_rate=Decimal("0.01"),
            remaining_term=0,
        )
        self.assertEqual(expected, actual)


@patch.object(declining_principal, "apply_declining_principal_formula")
@patch.object(declining_principal.utils, "get_parameter")
@patch.object(declining_principal, "_get_declining_principal_formula_terms")
@patch.object(declining_principal, "term_details")
class CalculateEmi(FeatureTest):
    def test_calculate_emi_no_optional_params_provided(
        self,
        mock_term_details: MagicMock,
        mock_get_declining_principal_formula_terms: MagicMock,
        mock_get_parameter: MagicMock,
        mock_apply_declining_principal_formula: MagicMock,
    ):

        mock_get_declining_principal_formula_terms.return_value = (
            sentinel.principal,
            sentinel.monthly_int_rate,
        )
        mock_term_details.return_value = (sentinel.elapsed_term, sentinel.remaining_term)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"principal": sentinel.principal}
        )
        mock_apply_declining_principal_formula.return_value = sentinel.emi

        result = declining_principal.calculate_emi(
            vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
        )
        self.assertEqual(result, sentinel.emi)

        mock_get_declining_principal_formula_terms.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            principal_amount=None,
            interest_calculation_feature=None,
        )

        mock_apply_declining_principal_formula.assert_called_once_with(
            remaining_principal=sentinel.principal,
            interest_rate=sentinel.monthly_int_rate,
            remaining_term=sentinel.remaining_term,
        )
        mock_term_details.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=True,
            interest_rate=None,
            principal_adjustments=None,
            balances=None,
        )

    def test_calculate_emi_all_optional_params_provided(
        self,
        mock_term_details: MagicMock,
        mock_get_declining_principal_formula_terms: MagicMock,
        mock_get_parameter: MagicMock,
        mock_apply_declining_principal_formula: MagicMock,
    ):
        mock_interest_feature = MagicMock()
        mock_interest_feature.get_monthly_interest_rate.return_value = sentinel.monthly_int_rate
        mock_apply_declining_principal_formula.return_value = sentinel.emi

        mock_principal_adjustments = [
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(1))),
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(49))),
        ]

        mock_get_declining_principal_formula_terms.return_value = (
            Decimal("100"),
            sentinel.monthly_int_rate,
        )
        mock_term_details.return_value = (sentinel.elapsed_term, sentinel.remaining_term)

        result = declining_principal.calculate_emi(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=False,
            principal_amount=Decimal("100"),
            interest_calculation_feature=mock_interest_feature,
            principal_adjustments=mock_principal_adjustments,  # type: ignore
            balances=sentinel.balances,
        )

        mock_get_declining_principal_formula_terms.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            principal_amount=Decimal("100"),
            interest_calculation_feature=mock_interest_feature,
        )

        mock_apply_declining_principal_formula.assert_called_once_with(
            remaining_principal=Decimal("150"),
            interest_rate=sentinel.monthly_int_rate,
            remaining_term=sentinel.remaining_term,
        )
        mock_term_details.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=False,
            interest_rate=mock_interest_feature,
            principal_adjustments=mock_principal_adjustments,
            balances=sentinel.balances,
        )
        self.assertEqual(result, sentinel.emi)

    def test_calculate_emi_with_principal_0(
        self,
        mock_term_details: MagicMock,
        mock_get_declining_principal_formula_terms: MagicMock,
        mock_get_parameter: MagicMock,
        mock_apply_declining_principal_formula: MagicMock,
    ):
        mock_interest_feature = MagicMock()
        mock_interest_feature.get_monthly_interest_rate.return_value = sentinel.monthly_int_rate
        mock_apply_declining_principal_formula.return_value = sentinel.emi
        mock_get_declining_principal_formula_terms.return_value = (
            Decimal("0"),
            sentinel.monthly_int_rate,
        )
        mock_term_details.return_value = (sentinel.elapsed_term, sentinel.remaining_term)

        result = declining_principal.calculate_emi(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            principal_amount=Decimal("0"),
            interest_calculation_feature=mock_interest_feature,
        )

        mock_get_declining_principal_formula_terms.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            principal_amount=Decimal("0"),
            interest_calculation_feature=mock_interest_feature,
        )

        mock_apply_declining_principal_formula.assert_called_once_with(
            remaining_principal=Decimal("0"),
            interest_rate=sentinel.monthly_int_rate,
            remaining_term=sentinel.remaining_term,
        )
        mock_term_details.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=True,
            interest_rate=mock_interest_feature,
            principal_adjustments=None,
            balances=None,
        )

        self.assertEqual(result, sentinel.emi)


@patch.object(declining_principal, "_get_declining_principal_formula_terms")
@patch.object(declining_principal, "supervisor_term_details")
@patch.object(declining_principal, "apply_declining_principal_formula")
class SupervisorCalculateEmi(SupervisorFeatureTest):
    def test_calculate_emi_no_optional_params_provided_supervisor(
        self,
        mock_apply_declining_principal_formula: MagicMock,
        mock_supervisor_term_details: MagicMock,
        mock_get_declining_principal_formula_terms: MagicMock,
    ):
        mock_get_declining_principal_formula_terms.return_value = (
            sentinel.principal,
            sentinel.monthly_int_rate,
        )
        mock_supervisor_term_details.return_value = (sentinel.elapsed_term, sentinel.remaining_term)
        mock_apply_declining_principal_formula.return_value = sentinel.emi
        mock_vault = self.create_supervisee_mock()
        mock_main_vault = self.create_supervisee_mock()

        result = declining_principal.supervisor_calculate_emi(
            loan_vault=mock_vault,
            main_vault=mock_main_vault,
            effective_datetime=sentinel.effective_datetime,
        )

        mock_get_declining_principal_formula_terms.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            principal_amount=None,
            interest_calculation_feature=None,
        )

        mock_supervisor_term_details.assert_called_once_with(
            loan_vault=mock_vault,
            main_vault=mock_main_vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=True,
            interest_rate=None,
            principal_adjustments=None,
            balances=None,
        )

        mock_apply_declining_principal_formula.assert_called_once_with(
            remaining_principal=sentinel.principal,
            interest_rate=sentinel.monthly_int_rate,
            remaining_term=sentinel.remaining_term,
        )
        self.assertEqual(result, sentinel.emi)

    @patch.object(declining_principal.utils, "get_parameter")
    def test_calculate_emi_all_optional_params_provided_supervisor(
        self,
        mock_get_parameter,
        mock_apply_declining_principal_formula: MagicMock,
        mock_supervisor_term_details: MagicMock,
        mock_get_declining_principal_formula_terms: MagicMock,
    ):
        mock_interest_feature = MagicMock()
        mock_interest_feature.get_monthly_interest_rate.return_value = sentinel.monthly_int_rate
        mock_apply_declining_principal_formula.return_value = sentinel.emi
        mock_supervisor_term_details.return_value = (sentinel.elapsed_term, sentinel.remaining_term)

        mock_principal_adjustments = [
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(1))),
            MagicMock(calculate_principal_adjustment=MagicMock(return_value=Decimal(49))),
        ]

        mock_get_declining_principal_formula_terms.return_value = (
            Decimal("100"),
            sentinel.monthly_int_rate,
        )

        mock_vault = self.create_supervisee_mock()
        mock_main_vault = self.create_supervisee_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter_for_multiple_vaults(
            parameters_per_vault={mock_main_vault: {"denomination": sentinel.denomination}}
        )

        result = declining_principal.supervisor_calculate_emi(
            loan_vault=mock_vault,
            main_vault=mock_main_vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=False,
            principal_amount=Decimal("100"),
            interest_calculation_feature=mock_interest_feature,
            principal_adjustments=mock_principal_adjustments,  # type: ignore
            balances=sentinel.balances,
        )

        mock_get_declining_principal_formula_terms.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            principal_amount=Decimal("100"),
            interest_calculation_feature=mock_interest_feature,
        )

        mock_supervisor_term_details.assert_called_once_with(
            loan_vault=mock_vault,
            main_vault=mock_main_vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=False,
            interest_rate=mock_interest_feature,
            principal_adjustments=mock_principal_adjustments,
            balances=sentinel.balances,
        )

        mock_apply_declining_principal_formula.assert_called_once_with(
            remaining_principal=Decimal("150"),
            interest_rate=sentinel.monthly_int_rate,
            remaining_term=sentinel.remaining_term,
        )
        self.assertEqual(result, sentinel.emi)

    @patch.object(declining_principal.utils, "get_parameter")
    def test_calculate_emi_with_principal_0_supervisor(
        self,
        mock_get_parameter,
        mock_apply_declining_principal_formula: MagicMock,
        mock_supervisor_term_details: MagicMock,
        mock_get_declining_principal_formula_terms: MagicMock,
    ):
        mock_interest_feature = MagicMock()
        mock_interest_feature.get_monthly_interest_rate.return_value = sentinel.monthly_int_rate
        mock_apply_declining_principal_formula.return_value = sentinel.emi
        mock_get_declining_principal_formula_terms.return_value = (
            Decimal("0"),
            sentinel.monthly_int_rate,
        )
        mock_supervisor_term_details.return_value = (sentinel.elapsed_term, sentinel.remaining_term)

        mock_vault = self.create_supervisee_mock()
        mock_main_vault = self.create_supervisee_mock()

        result = declining_principal.supervisor_calculate_emi(
            loan_vault=mock_vault,
            main_vault=mock_main_vault,
            effective_datetime=sentinel.effective_datetime,
            principal_amount=Decimal("0"),
            interest_calculation_feature=mock_interest_feature,
            principal_adjustments=None,
        )

        mock_get_declining_principal_formula_terms.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            principal_amount=Decimal("0"),
            interest_calculation_feature=mock_interest_feature,
        )

        mock_supervisor_term_details.assert_called_once_with(
            loan_vault=mock_vault,
            main_vault=mock_main_vault,
            effective_datetime=sentinel.effective_datetime,
            use_expected_term=True,
            interest_rate=mock_interest_feature,
            principal_adjustments=None,
            balances=None,
        )

        mock_apply_declining_principal_formula.assert_called_once_with(
            remaining_principal=Decimal("0"),
            interest_rate=sentinel.monthly_int_rate,
            remaining_term=sentinel.remaining_term,
        )

        self.assertEqual(result, sentinel.emi)


class IsDecliningPrincipalLoanTest(FeatureTest):
    def test_is_declining_principal_loan_true(self):
        self.assertEqual(
            declining_principal.is_declining_principal_loan("DECLINING_PRINCIPAL"), True
        )

    def test_is_declining_principal_lower_case_true(self):
        self.assertEqual(
            declining_principal.is_declining_principal_loan("declining_principal"), True
        )

    def test_is_declining_principal_loan_false(self):
        self.assertEqual(declining_principal.is_declining_principal_loan("other"), False)


@patch.object(declining_principal.utils, "get_parameter")
class GetDecliningPrincipalFormulaTerms(FeatureTest):
    def test_get_declining_principal_formula_terms_no_optional_params_provided(
        self, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"principal": sentinel.principal}
        )

        expected = (sentinel.principal, Decimal("0"))

        result = declining_principal._get_declining_principal_formula_terms(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
        )
        self.assertEqual(result, expected)

        mock_get_parameter.assert_called_once_with(vault=sentinel.vault, name="principal")

    def test_get_declining_principal_formula_terms_all_optional_params_provided(
        self, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"principal": sentinel.principal}
        )
        mock_interest_feature = MagicMock()
        mock_interest_feature.get_monthly_interest_rate.return_value = sentinel.monthly_int_rate

        expected = (Decimal("100"), sentinel.monthly_int_rate)

        result = declining_principal._get_declining_principal_formula_terms(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
            principal_amount=Decimal("100"),
            interest_calculation_feature=mock_interest_feature,
        )
        self.assertEqual(result, expected)

        mock_get_parameter.assert_not_called()
