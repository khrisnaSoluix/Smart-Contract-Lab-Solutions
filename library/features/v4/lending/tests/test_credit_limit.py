# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.lending.credit_limit as credit_limit
from library.features.v4.common.test.mocks import (
    mock_utils_get_parameter,
    mock_utils_get_parameter_for_multiple_vaults,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    RejectionReason,
    Tside,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)


@patch.object(credit_limit.utils, "get_parameter")
class CalculateAssociatedOriginalPrincipalTest(FeatureTest):
    tside = Tside.ASSET

    def test_correct_associated_original_principal_is_returned(self, mock_get_parameter: MagicMock):
        mock_vaults = [sentinel.vault1, sentinel.vault2, sentinel.vault3]

        mock_get_parameter.side_effect = mock_utils_get_parameter_for_multiple_vaults(
            parameters_per_vault={
                sentinel.vault1: {"principal": Decimal("107.32")},
                sentinel.vault2: {"principal": Decimal("45.15")},
                sentinel.vault3: {"principal": Decimal("80.70")},
            }
        )

        expected = Decimal("233.17")

        actual = credit_limit.calculate_associated_original_principal(loans=mock_vaults)
        self.assertEqual(actual, expected)


@patch.object(credit_limit.utils, "balance_at_coordinates")
@patch.object(credit_limit.supervisor_utils, "sum_balances_across_supervisees")
class CalculateUnassociatedPrincipalTest(FeatureTest):
    tside = Tside.ASSET

    def test_correct_unassociated_principal_is_returned(
        self,
        mock_sum_balances_across_supervisees,
        mock_balance_at_coordinates,
    ):
        main_vault_balances = sentinel.main_vault_balances
        loan_balances = sentinel.loan_balances
        denomination = sentinel.denomination
        associated_original_principal = Decimal("80")  # associated principal
        mock_sum_balances_across_supervisees.return_value = Decimal("75")  # associated repayments
        mock_balance_at_coordinates.return_value = Decimal("100")  # main_vault default

        expected = Decimal("95")

        actual = credit_limit.calculate_unassociated_principal(
            main_vault_balances=main_vault_balances,
            loan_balances=loan_balances,
            denomination=denomination,
            associated_original_principal=associated_original_principal,
        )
        self.assertEqual(actual, expected)


@patch.object(credit_limit.supervisor_utils, "sum_balances_across_supervisees")
class CalculateAvailableCreditLimitTest(FeatureTest):
    tside = Tside.ASSET

    def test_original_applicable_principal(
        self,
        mock_sum_balances_across_supervisees,
    ):
        loan_balances = sentinel.loan_balances
        main_vault_credit_limit = Decimal("300")
        applicable_principal = "original"
        denomination = sentinel.denomination
        associated_original_principal = Decimal("80")
        unassociated_principal = Decimal("25")

        expected = Decimal("195")

        actual = credit_limit.calculate_available_credit_limit(
            loan_balances=loan_balances,
            credit_limit=main_vault_credit_limit,
            applicable_principal=applicable_principal,
            denomination=denomination,
            associated_original_principal=associated_original_principal,
            unassociated_principal=unassociated_principal,
        )
        self.assertEqual(actual, expected)
        mock_sum_balances_across_supervisees.assert_not_called()

    def test_outstanding_applicable_principal(
        self,
        mock_sum_balances_across_supervisees,
    ):
        loan_balances = sentinel.loan_balances
        main_vault_credit_limit = Decimal("300")
        applicable_principal = "outstanding"
        denomination = sentinel.denomination
        associated_original_principal = Decimal("80")
        unassociated_principal = Decimal("25")
        mock_sum_balances_across_supervisees.return_value = Decimal("75")  # outstanding principal

        expected = Decimal("200")

        actual = credit_limit.calculate_available_credit_limit(
            loan_balances=loan_balances,
            credit_limit=main_vault_credit_limit,
            applicable_principal=applicable_principal,
            denomination=denomination,
            associated_original_principal=associated_original_principal,
            unassociated_principal=unassociated_principal,
        )
        self.assertEqual(actual, expected)
        mock_sum_balances_across_supervisees.assert_called_once()


@patch.object(credit_limit.utils, "get_available_balance")
@patch.object(credit_limit, "calculate_available_credit_limit")
@patch.object(credit_limit, "calculate_unassociated_principal")
@patch.object(credit_limit, "calculate_associated_original_principal")
@patch.object(credit_limit.utils, "get_parameter")
@patch.object(credit_limit.supervisor_utils, "get_balance_default_dicts_for_supervisees")
class ValidateCreditLimitTest(FeatureTest):
    tside = Tside.ASSET
    main_vault_parameters = {
        credit_limit.PARAM_DENOMINATION: sentinel.denomination,
        credit_limit.PARAM_CREDIT_LIMIT: sentinel.credit_limit,
        credit_limit.PARAM_CREDIT_LIMIT_APPLICABLE_PRINCIPAL: sentinel.applicable_principal,
    }

    def test_posting_greater_than_credit_limit_returns_rejection(
        self,
        mock_get_balance_default_dicts_for_supervisees: MagicMock,
        mock_get_parameter: MagicMock,
        mock_calculate_associated_original_principal: MagicMock,
        mock_calculate_unassociated_principal: MagicMock,
        mock_calculate_available_credit_limit: MagicMock,
        mock_get_available_balance: MagicMock,
    ):
        main_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                credit_limit.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "balances_observation"
                )
            },
        )
        loans = sentinel.loans
        posting_instruction = self.outbound_hard_settlement(amount=Decimal("101"))

        mock_get_balance_default_dicts_for_supervisees.return_value = sentinel.balance_default_dicts
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.main_vault_parameters
        )
        mock_calculate_associated_original_principal.return_value = (
            sentinel.associated_original_principal
        )
        mock_calculate_unassociated_principal.return_value = sentinel.unassociated_principal
        mock_calculate_available_credit_limit.return_value = Decimal("100")
        mock_get_available_balance.return_value = Decimal("101")

        expected = Rejection(
            message="Incoming posting of 101 exceeds available credit limit of 100",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        actual = credit_limit.validate(
            main_vault=main_vault,
            loans=loans,
            posting_instruction=posting_instruction,
        )

        self.assertEqual(actual, expected)
        mock_calculate_associated_original_principal.assert_called_once_with(loans=loans)
        mock_calculate_unassociated_principal.assert_called_once_with(
            main_vault_balances=SentinelBalancesObservation("balances_observation").balances,
            loan_balances=sentinel.balance_default_dicts,
            denomination=sentinel.denomination,
            associated_original_principal=sentinel.associated_original_principal,
            non_repayable_addresses=None,
        )

        mock_calculate_available_credit_limit.assert_called_once_with(
            loan_balances=sentinel.balance_default_dicts,
            credit_limit=sentinel.credit_limit,
            applicable_principal=sentinel.applicable_principal,
            denomination=sentinel.denomination,
            associated_original_principal=sentinel.associated_original_principal,
            unassociated_principal=sentinel.unassociated_principal,
        )

    def test_posting_less_than_credit_limit_returns_none(
        self,
        mock_get_balance_default_dicts_for_supervisees: MagicMock,
        mock_get_parameter: MagicMock,
        mock_calculate_associated_original_principal: MagicMock,
        mock_calculate_unassociated_principal: MagicMock,
        mock_calculate_available_credit_limit: MagicMock,
        mock_get_available_balance: MagicMock,
    ):
        main_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                credit_limit.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "balances_observation"
                )
            },
        )
        loans = sentinel.loans
        posting_instruction = self.outbound_hard_settlement(amount=Decimal("99"))

        mock_get_balance_default_dicts_for_supervisees.return_value = sentinel.balance_default_dicts
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.main_vault_parameters
        )
        mock_calculate_associated_original_principal.return_value = (
            sentinel.associated_original_principal
        )
        mock_calculate_unassociated_principal.return_value = sentinel.unassociated_principal
        mock_calculate_available_credit_limit.return_value = Decimal("100")
        mock_get_available_balance.return_value = Decimal("99")

        actual = credit_limit.validate(
            main_vault=main_vault,
            loans=loans,
            posting_instruction=posting_instruction,
        )

        self.assertIsNone(actual)
        mock_calculate_associated_original_principal.assert_called_once_with(loans=loans)
        mock_calculate_unassociated_principal.assert_called_once_with(
            main_vault_balances=SentinelBalancesObservation("balances_observation").balances,
            loan_balances=sentinel.balance_default_dicts,
            denomination=sentinel.denomination,
            associated_original_principal=sentinel.associated_original_principal,
            non_repayable_addresses=None,
        )

        mock_calculate_available_credit_limit.assert_called_once_with(
            loan_balances=sentinel.balance_default_dicts,
            credit_limit=sentinel.credit_limit,
            applicable_principal=sentinel.applicable_principal,
            denomination=sentinel.denomination,
            associated_original_principal=sentinel.associated_original_principal,
            unassociated_principal=sentinel.unassociated_principal,
        )

    def test_posting_equal_to_credit_limit_returns_none(
        self,
        mock_get_balance_default_dicts_for_supervisees: MagicMock,
        mock_get_parameter: MagicMock,
        mock_calculate_associated_original_principal: MagicMock,
        mock_calculate_unassociated_principal: MagicMock,
        mock_calculate_available_credit_limit: MagicMock,
        mock_get_available_balance: MagicMock,
    ):
        main_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                credit_limit.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "balances_observation"
                )
            },
        )
        loans = sentinel.loans
        posting_instruction = self.outbound_hard_settlement(amount=Decimal("100"))

        mock_get_balance_default_dicts_for_supervisees.return_value = sentinel.balance_default_dicts
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.main_vault_parameters
        )
        mock_calculate_associated_original_principal.return_value = (
            sentinel.associated_original_principal
        )
        mock_calculate_unassociated_principal.return_value = sentinel.unassociated_principal
        mock_calculate_available_credit_limit.return_value = Decimal("100")
        mock_get_available_balance.return_value = Decimal("100")

        actual = credit_limit.validate(
            main_vault=main_vault,
            loans=loans,
            posting_instruction=posting_instruction,
        )

        self.assertIsNone(actual)
        mock_calculate_associated_original_principal.assert_called_once_with(loans=loans)
        mock_calculate_unassociated_principal.assert_called_once_with(
            main_vault_balances=SentinelBalancesObservation("balances_observation").balances,
            loan_balances=sentinel.balance_default_dicts,
            denomination=sentinel.denomination,
            associated_original_principal=sentinel.associated_original_principal,
            non_repayable_addresses=None,
        )

        mock_calculate_available_credit_limit.assert_called_once_with(
            loan_balances=sentinel.balance_default_dicts,
            credit_limit=sentinel.credit_limit,
            applicable_principal=sentinel.applicable_principal,
            denomination=sentinel.denomination,
            associated_original_principal=sentinel.associated_original_principal,
            unassociated_principal=sentinel.unassociated_principal,
        )


@patch.object(credit_limit.utils, "sum_balances")
@patch.object(credit_limit.utils, "get_parameter")
class ValidateCreditLimitParameterChangeTest(FeatureTest):
    def test_rejects_credit_limit_below_total_outstanding_principal(
        self, mock_get_parameter: MagicMock, mock_sum_balances: MagicMock
    ):

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                credit_limit.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "balances_observation"
                )
            }
        )
        mock_sum_balances.return_value = Decimal("100")  # this is the total outstanding principal
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )

        result = credit_limit.validate_credit_limit_parameter_change(
            vault=mock_vault, proposed_credit_limit=Decimal("99.99")
        )

        expected = Rejection(
            message="Cannot set proposed credit limit 99.99 "
            "to a value below the total outstanding debt of 100",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        self.assertEqual(result, expected)
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name=credit_limit.PARAM_DENOMINATION
        )
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances_balances_observation,
            denomination=sentinel.denomination,
            addresses=credit_limit.addresses.ALL_PRINCIPAL,
        )

    def test_accepts_credit_limit_equal_to_total_outstanding_principal(
        self, mock_get_parameter: MagicMock, mock_sum_balances: MagicMock
    ):

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                credit_limit.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation(
                    "balances_observation"
                )
            }
        )
        mock_sum_balances.return_value = Decimal("100")  # this is the total outstanding principal
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_limit.PARAM_DENOMINATION: sentinel.denomination}
        )

        result = credit_limit.validate_credit_limit_parameter_change(
            vault=mock_vault,
            proposed_credit_limit=Decimal("100"),
        )

        self.assertIsNone(result)
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault, name=credit_limit.PARAM_DENOMINATION
        )
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances_balances_observation,
            denomination=sentinel.denomination,
            addresses=credit_limit.addresses.ALL_PRINCIPAL,
        )

    def test_accept_credit_limit_larger_than_total_outstanding_principal_with_non_default_arguments(
        self, mock_get_parameter: MagicMock, mock_sum_balances: MagicMock
    ):

        mock_sum_balances.return_value = Decimal("100")  # this is the total outstanding principal

        result = credit_limit.validate_credit_limit_parameter_change(
            vault=sentinel.vault,
            proposed_credit_limit=Decimal("101"),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            principal_addresses=sentinel.addresses,
        )

        self.assertIsNone(result)
        mock_get_parameter.assert_not_called()
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            addresses=sentinel.addresses,
        )
