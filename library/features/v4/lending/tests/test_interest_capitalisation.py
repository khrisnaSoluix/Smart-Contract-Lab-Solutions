# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# features
import library.features.v4.lending.interest_capitalisation as interest_capitalisation
import library.features.v4.lending.lending_addresses as lending_addresses
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ASSET,
    BalanceCoordinate,
    CustomInstruction,
    Phase,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelPosting,
)

# from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PRINCIPAL_COORDINATE = BalanceCoordinate(
    "PRINCIPAL",
    DEFAULT_ASSET,
    sentinel.denomination,
    Phase.COMMITTED,
)


class InterestCapitalisationTest(FeatureTest):
    maxDiff = None


@patch.object(interest_capitalisation.accruals, "accrual_application_postings")
@patch.object(interest_capitalisation.utils, "create_postings")
@patch.object(interest_capitalisation.utils, "balance_at_coordinates")
@patch.object(interest_capitalisation.utils, "round_decimal")
class CapitaliseInterestTest(InterestCapitalisationTest):
    def test_capitalise_interest_applies_pending_capitalisation_accrued_interest(
        self,
        mock_round_decimal: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_create_postings: MagicMock,
        mock_accrual_application_postings: MagicMock,
    ):
        mock_round_decimal.return_value = Decimal("1")
        mock_balance_at_coordinates.return_value = sentinel.unrounded_interest
        application_posting = SentinelPosting("application")
        tracker_posting = SentinelPosting("tracker")
        mock_accrual_application_postings.return_value = [application_posting]
        mock_create_postings.return_value = [tracker_posting]

        result = interest_capitalisation.capitalise_interest(
            account_id=sentinel.account_id,
            application_precision=sentinel.application_precision,
            balances=sentinel.balances,
            capitalised_interest_receivable_account=sentinel.capitalised_receivable_account,
            capitalised_interest_received_account=sentinel.capitalised_received_account,
            denomination=sentinel.denomination,
            interest_address_pending_capitalisation=sentinel.address_pending_capitalisation,
            account_type=sentinel.account_type,
        )
        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=[application_posting, tracker_posting],
                    instruction_details={
                        "description": "Capitalise interest accrued to principal",
                        "event": "END_OF_REPAYMENT_HOLIDAY",
                        "gl_impacted": "True",
                        "account_type": sentinel.account_type,
                    },
                ),
            ],
        )

        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            address=sentinel.address_pending_capitalisation,
        )
        mock_round_decimal.assert_called_once_with(
            amount=sentinel.unrounded_interest, decimal_places=sentinel.application_precision
        )
        mock_accrual_application_postings.assert_called_once_with(
            customer_account=sentinel.account_id,
            denomination=sentinel.denomination,
            accrual_amount=sentinel.unrounded_interest,
            application_amount=Decimal("1"),
            accrual_customer_address=sentinel.address_pending_capitalisation,
            accrual_internal_account=sentinel.capitalised_receivable_account,
            application_customer_address=lending_addresses.PRINCIPAL,
            application_internal_account=sentinel.capitalised_received_account,
            payable=False,
        )

        mock_create_postings.assert_called_once_with(
            amount=Decimal("1"),
            debit_account=sentinel.account_id,
            credit_account=sentinel.account_id,
            debit_address=lending_addresses.CAPITALISED_INTEREST_TRACKER,
            credit_address=lending_addresses.INTERNAL_CONTRA,
        )

    def test_capitalise_interest_does_nothing_if_no_pending_capitalisation_accrued_interest(
        self,
        mock_round_decimal: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_create_postings: MagicMock,
        mock_accrual_application_postings: MagicMock,
    ):
        mock_round_decimal.return_value = Decimal("0")
        mock_balance_at_coordinates.return_value = sentinel.unrounded_interest
        result = interest_capitalisation.capitalise_interest(
            account_id=sentinel.account_id,
            application_precision=sentinel.application_precision,
            balances=sentinel.balances,
            capitalised_interest_receivable_account=sentinel.capitalised_receivable_account,
            capitalised_interest_received_account=sentinel.capitalised_received_account,
            denomination=sentinel.denomination,
            interest_address_pending_capitalisation=sentinel.address_pending_capitalisation,
            account_type=sentinel.account_type,
        )

        self.assertListEqual([], result)
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            address=sentinel.address_pending_capitalisation,
        )
        mock_round_decimal.assert_called_once_with(
            amount=sentinel.unrounded_interest, decimal_places=sentinel.application_precision
        )
        mock_create_postings.assert_not_called()
        mock_accrual_application_postings.assert_not_called()

    def test_capitalise_interest_does_nothing_if_negative_accrued_capitalised_interest(
        self,
        mock_round_decimal: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_create_postings: MagicMock,
        mock_accrual_application_postings: MagicMock,
    ):
        mock_round_decimal.return_value = Decimal("-10")
        mock_balance_at_coordinates.return_value = sentinel.unrounded_interest
        result = interest_capitalisation.capitalise_interest(
            account_id=sentinel.account_id,
            application_precision=sentinel.application_precision,
            balances=sentinel.balances,
            capitalised_interest_receivable_account=sentinel.capitalised_receivable_account,
            capitalised_interest_received_account=sentinel.capitalised_received_account,
            denomination=sentinel.denomination,
            interest_address_pending_capitalisation=sentinel.address_pending_capitalisation,
            account_type=sentinel.account_type,
        )

        self.assertListEqual([], result)
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            address=sentinel.address_pending_capitalisation,
        )
        mock_round_decimal.assert_called_once_with(
            amount=sentinel.unrounded_interest, decimal_places=sentinel.application_precision
        )
        mock_create_postings.assert_not_called()
        mock_accrual_application_postings.assert_not_called()


@patch.object(interest_capitalisation, "is_capitalise_penalty_interest")
@patch.object(interest_capitalisation, "handle_interest_capitalisation")
class HandlePenaltyInterestCapitalisationTest(InterestCapitalisationTest):
    def test_handle_penalty_interest_capitalisation_no_capitalisation(
        self,
        mock_handle_interest_capitalisation: MagicMock,
        mock_is_capitalise_penalty_interest: MagicMock,
    ):
        mock_is_capitalise_penalty_interest.return_value = False
        result = interest_capitalisation.handle_penalty_interest_capitalisation(
            vault=sentinel.vault,
            account_type=sentinel.account_type,
        )
        self.assertListEqual([], result)
        mock_is_capitalise_penalty_interest.assert_called_once_with(vault=sentinel.vault)
        mock_handle_interest_capitalisation.assert_not_called()

    def test_handle_penalty_interest_capitalisation_with_capitalisation(
        self,
        mock_handle_interest_capitalisation: MagicMock,
        mock_is_capitalise_penalty_interest: MagicMock,
    ):
        mock_is_capitalise_penalty_interest.return_value = True
        mock_handle_interest_capitalisation.return_value = [sentinel.custom_instructions]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                interest_capitalisation.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(  # noqa: E501
                    "effective"
                )
            }
        )
        result = interest_capitalisation.handle_penalty_interest_capitalisation(
            vault=mock_vault,
            account_type=sentinel.account_type,
        )
        self.assertListEqual(result, [sentinel.custom_instructions])
        mock_handle_interest_capitalisation.assert_called_once_with(
            vault=mock_vault,
            account_type=sentinel.account_type,
            balances=sentinel.balances_effective,
            interest_to_capitalise_address="ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION",
        )


@patch.object(interest_capitalisation, "_get_denomination")
@patch.object(interest_capitalisation.utils, "get_parameter")
@patch.object(interest_capitalisation.interest_application, "get_application_precision")
@patch.object(interest_capitalisation, "capitalise_interest")
class HandleInterestCapitalisationTest(InterestCapitalisationTest):
    def test_handle_capitalisation_uses_argument_values_when_specified(
        self,
        mock_capitalise_interest: MagicMock,
        mock_get_application_precision: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_denomination: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_capitalise_interest.return_value = [sentinel.capitalisation_postings]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: sentinel.received_acc,  # noqa: E501
                interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: sentinel.receivable_acc,  # noqa: E501
            }
        )
        mock_get_application_precision.return_value = sentinel.precision
        mock_get_denomination.return_value = sentinel.denomination

        result = interest_capitalisation.handle_interest_capitalisation(
            vault=mock_vault,
            account_type=sentinel.account_type,
            balances=sentinel.balances,
            interest_to_capitalise_address=sentinel.interest_to_capitalise_address,
        )

        self.assertListEqual([sentinel.capitalisation_postings], result)
        mock_capitalise_interest.assert_called_once_with(
            account_id=mock_vault.account_id,
            application_precision=sentinel.precision,
            balances=sentinel.balances,
            capitalised_interest_receivable_account=sentinel.receivable_acc,
            capitalised_interest_received_account=sentinel.received_acc,
            denomination=sentinel.denomination,
            interest_address_pending_capitalisation=sentinel.interest_to_capitalise_address,
            account_type=sentinel.account_type,
        )
        mock_get_application_precision.assert_called_once_with(vault=mock_vault)
        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="capitalised_interest_received_account"),
                call(vault=mock_vault, name="capitalised_interest_receivable_account"),
            ]
        )
        mock_get_denomination.assert_called_once_with(vault=mock_vault)

    def test_handle_capitalisation_no_optional_args(
        self,
        mock_capitalise_interest: MagicMock,
        mock_get_application_precision: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_denomination: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                interest_capitalisation.fetchers.EOD_FETCHER_ID: SentinelBalancesObservation(  # noqa: E501
                    "effective"
                )
            }
        )
        mock_capitalise_interest.return_value = [sentinel.capitalisation_postings]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: sentinel.received_acc,  # noqa: E501
                interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: sentinel.receivable_acc,  # noqa: E501
            }
        )
        mock_get_application_precision.return_value = sentinel.precision
        mock_get_denomination.return_value = sentinel.denomination

        result = interest_capitalisation.handle_interest_capitalisation(
            vault=mock_vault,
            account_type=sentinel.account_type,
        )

        self.assertListEqual([sentinel.capitalisation_postings], result)
        mock_capitalise_interest.assert_called_once_with(
            account_id=mock_vault.account_id,
            application_precision=sentinel.precision,
            balances=sentinel.balances_effective,
            capitalised_interest_receivable_account=sentinel.receivable_acc,
            capitalised_interest_received_account=sentinel.received_acc,
            denomination=sentinel.denomination,
            interest_address_pending_capitalisation="ACCRUED_INTEREST_PENDING_CAPITALISATION",
            account_type=sentinel.account_type,
        )
        mock_get_application_precision.assert_called_once_with(vault=mock_vault)
        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="capitalised_interest_received_account"),
                call(vault=mock_vault, name="capitalised_interest_receivable_account"),
            ]
        )
        mock_get_denomination.assert_called_once_with(vault=mock_vault)


@patch.object(interest_capitalisation.utils, "get_parameter")
class GetDenominationTest(InterestCapitalisationTest):
    def test_get_denomination_no_optional_args(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.return_value = sentinel.denomination
        result = interest_capitalisation._get_denomination(
            vault=sentinel.vault,
        )
        self.assertEqual(sentinel.denomination, result)
        mock_get_parameter.assert_called_once_with(vault=sentinel.vault, name="denomination")

    def test_get_denomination_with_optional_args(
        self,
        mock_get_parameter: MagicMock,
    ):
        result = interest_capitalisation._get_denomination(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
        )
        self.assertEqual(sentinel.denomination, result)
        mock_get_parameter.assert_not_called()


@patch.object(interest_capitalisation.utils, "get_parameter")
class IsCapitalisePenaltyInterestTest(InterestCapitalisationTest):
    def test_is_capitalise_penalty_interest(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.return_value = sentinel.capitalise_penalty_interest
        result = interest_capitalisation.is_capitalise_penalty_interest(
            vault=sentinel.vault,
        )
        self.assertEqual(sentinel.capitalise_penalty_interest, result)
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault,
            name="capitalise_penalty_interest",
            is_boolean=True,
        )


@patch.object(interest_capitalisation.utils, "get_parameter")
@patch.object(interest_capitalisation.interest_application, "get_application_precision")
@patch.object(interest_capitalisation, "capitalise_interest")
@patch.object(interest_capitalisation.utils, "balance_at_coordinates")
class HandleOverpaymentsToPenaltiesPendingCapitalisationTest(InterestCapitalisationTest):
    def test_handle_overpayments_to_penalties_pending_capitalisation(
        self,
        balance_at_coordinates: MagicMock,
        mock_capitalise_interest: MagicMock,
        mock_get_application_precision: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_capitalise_interest.return_value = [sentinel.capitalisation_postings]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: sentinel.received_acc,  # noqa: E501
                interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: sentinel.receivable_acc,  # noqa: E501
            }
        )
        mock_get_application_precision.return_value = sentinel.precision
        balance_at_coordinates.return_value = Decimal("5")

        result = interest_capitalisation.handle_overpayments_to_penalties_pending_capitalisation(
            vault=mock_vault,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

        self.assertListEqual([sentinel.capitalisation_postings], result)
        mock_capitalise_interest.assert_called_once_with(
            account_id=mock_vault.account_id,
            application_precision=sentinel.precision,
            balances=sentinel.balances,
            capitalised_interest_receivable_account=sentinel.receivable_acc,
            capitalised_interest_received_account=sentinel.received_acc,
            denomination=sentinel.denomination,
            interest_address_pending_capitalisation="ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION",  # noqa: E501
            application_customer_address="DEFAULT",
        )
        mock_get_application_precision.assert_called_once_with(vault=mock_vault)
        mock_get_parameter.assert_has_calls(
            calls=[
                call(vault=mock_vault, name="capitalised_interest_received_account"),
                call(vault=mock_vault, name="capitalised_interest_receivable_account"),
            ]
        )
        balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address="ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION",
            denomination=sentinel.denomination,
        )

    def test_handle_overpayments_to_penalties_pending_capitalisation_zero_balance(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_capitalise_interest: MagicMock,
        mock_get_application_precision: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_balance_at_coordinates.return_value = Decimal("0")

        result = interest_capitalisation.handle_overpayments_to_penalties_pending_capitalisation(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

        self.assertListEqual([], result)
        mock_capitalise_interest.assert_not_called()
        mock_get_application_precision.assert_not_called()
        mock_get_parameter.assert_not_called()
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address="ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION",
            denomination=sentinel.denomination,
        )

    def test_handle_overpayments_to_penalties_pending_capitalisation_negative_balance(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_capitalise_interest: MagicMock,
        mock_get_application_precision: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_balance_at_coordinates.return_value = Decimal("-100")

        result = interest_capitalisation.handle_overpayments_to_penalties_pending_capitalisation(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

        self.assertListEqual([], result)
        mock_capitalise_interest.assert_not_called()
        mock_get_application_precision.assert_not_called()
        mock_get_parameter.assert_not_called()
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address="ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION",
            denomination=sentinel.denomination,
        )
