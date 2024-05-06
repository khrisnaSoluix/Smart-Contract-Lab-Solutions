# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.lending.emi as emi
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelPosting,
)


class EMITest(FeatureTest):
    maxDiff = None


@patch.object(
    emi.utils,
    "get_parameter",
    MagicMock(side_effect=mock_utils_get_parameter({"denomination": sentinel.denomination})),
)
@patch.object(emi.utils, "balance_at_coordinates")
@patch.object(emi, "update_emi")
class UpdateEMIInstructionsTest(EMITest):
    def test_amortise_when_emi_changed_with_optional_attributes(
        self,
        mock_update_emi: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        mock_vault = self.create_mock(account_id=sentinel.account_id)
        mock_amortisation_feature = MagicMock(calculate_emi=MagicMock(return_value=Decimal("2")))
        mock_calculate_emi = mock_amortisation_feature.calculate_emi
        mock_update_emi.return_value = [SentinelPosting("update_emi")]
        mock_balance_at_coordinates.return_value = Decimal("1")
        mock_interest_calculation = MagicMock(
            get_monthly_interest_rate=MagicMock(return_value=sentinel.monthly_interest_rate),
        )
        mock_principal_adjustment = MagicMock(
            calculate_principal_adjustment=MagicMock(return_value=sentinel.principal_adjustment),
        )

        expected = [
            CustomInstruction(
                postings=[SentinelPosting("update_emi")],
                instruction_details={
                    "description": "Updating EMI to " f"{mock_calculate_emi.return_value}",
                    "event": "ACCOUNT_ACTIVATION",
                },
            )
        ]

        actual = emi.amortise(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=mock_amortisation_feature,
            principal_amount=sentinel.principal_amount,
            interest_calculation_feature=mock_interest_calculation,
            principal_adjustments=[mock_principal_adjustment],
            balances=sentinel.balances,
        )

        self.assertListEqual(actual, expected)
        mock_calculate_emi.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            principal_amount=sentinel.principal_amount,
            interest_calculation_feature=mock_interest_calculation,
            principal_adjustments=[mock_principal_adjustment],
            balances=sentinel.balances,
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=emi.lending_addresses.EMI,
            denomination=sentinel.denomination,
        )
        mock_update_emi.assert_called_once_with(
            account_id=mock_vault.account_id,
            denomination=sentinel.denomination,
            current_emi=Decimal("1"),
            updated_emi=Decimal("2"),
        )

    def test_amortise_when_emi_changed_without_optional_attributes(
        self,
        mock_update_emi: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        mock_vault = self.create_mock(account_id=sentinel.account_id)
        mock_amortisation_feature = MagicMock(calculate_emi=MagicMock(return_value=Decimal("2")))
        mock_calculate_emi = mock_amortisation_feature.calculate_emi
        mock_update_emi.return_value = [SentinelPosting("update_emi")]
        mock_balance_at_coordinates.return_value = Decimal("1")

        expected = [
            CustomInstruction(
                postings=[SentinelPosting("update_emi")],
                instruction_details={
                    "description": "Updating EMI to " f"{mock_calculate_emi.return_value}",
                    "event": "ACCOUNT_ACTIVATION",
                },
            )
        ]

        actual = emi.amortise(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=mock_amortisation_feature,
        )

        self.assertListEqual(actual, expected)
        mock_calculate_emi.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            principal_amount=None,
            interest_calculation_feature=None,
            principal_adjustments=None,
            balances=None,
        )
        mock_balance_at_coordinates.assert_not_called()
        mock_update_emi.assert_called_once_with(
            account_id=mock_vault.account_id,
            denomination=sentinel.denomination,
            current_emi=Decimal("0"),
            updated_emi=Decimal("2"),
        )

    def test_amortise_when_emi_unchanged(
        self,
        mock_update_emi: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        mock_vault = self.create_mock(account_id=sentinel.account_id)
        mock_amortisation_feature = MagicMock(calculate_emi=MagicMock(return_value=Decimal("1")))
        mock_balance_at_coordinates.return_value = Decimal("1")
        mock_calculate_emi = mock_amortisation_feature.calculate_emi
        mock_update_emi.return_value = []

        expected: list[CustomInstruction] = []

        actual = emi.amortise(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=mock_amortisation_feature,
            balances=sentinel.balances,
        )

        self.assertListEqual(actual, expected)
        mock_calculate_emi.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            principal_amount=None,
            interest_calculation_feature=None,
            principal_adjustments=None,
            balances=sentinel.balances,
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=emi.lending_addresses.EMI,
            denomination=sentinel.denomination,
        )
        mock_update_emi.assert_called_once_with(
            account_id=mock_vault.account_id,
            denomination=sentinel.denomination,
            current_emi=Decimal("1"),
            updated_emi=Decimal("1"),
        )


@patch.object(emi.utils, "create_postings")
class UpdateEMITest(EMITest):
    def test_update_emi_zero_delta(self, mock_create_postings: MagicMock):

        self.assertListEqual(
            emi.update_emi(
                account_id=sentinel.account_id,
                denomination=sentinel.denomination,
                current_emi=Decimal("1"),
                updated_emi=Decimal("1"),
            ),
            [],
        )
        mock_create_postings.assert_not_called()

    def test_update_emi_negative_delta(self, mock_create_postings: MagicMock):
        mock_create_postings.return_value = [sentinel.postings]
        self.assertListEqual(
            emi.update_emi(
                account_id=sentinel.account_id,
                denomination=sentinel.denomination,
                current_emi=Decimal("1"),
                updated_emi=Decimal("2"),
            ),
            [sentinel.postings],
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("1"),
            debit_account=sentinel.account_id,
            debit_address=emi.lending_addresses.EMI,
            credit_account=sentinel.account_id,
            credit_address=emi.lending_addresses.INTERNAL_CONTRA,
            denomination=sentinel.denomination,
        )

    def test_update_emi_positive_delta(self, mock_create_postings: MagicMock):
        mock_create_postings.return_value = [sentinel.postings]
        self.assertListEqual(
            emi.update_emi(
                account_id=sentinel.account_id,
                denomination=sentinel.denomination,
                current_emi=Decimal("2"),
                updated_emi=Decimal("1"),
            ),
            [sentinel.postings],
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("1"),
            debit_account=sentinel.account_id,
            debit_address=emi.lending_addresses.INTERNAL_CONTRA,
            credit_account=sentinel.account_id,
            credit_address=emi.lending_addresses.EMI,
            denomination=sentinel.denomination,
        )


@patch.object(emi.utils, "balance_at_coordinates")
class GetExpectedEMITest(EMITest):
    def test_get_expected_emi_default_decimal_places(self, mock_balance_at_coordinates: MagicMock):
        mock_balance_at_coordinates.return_value = sentinel.emi
        result = emi.get_expected_emi(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        self.assertEqual(result, sentinel.emi)
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address="EMI",
            denomination=sentinel.denomination,
            decimal_places=2,
        )

    def test_get_expected_emi_decimal_places_provded(self, mock_balance_at_coordinates: MagicMock):
        mock_balance_at_coordinates.return_value = sentinel.emi
        result = emi.get_expected_emi(
            balances=sentinel.balances, denomination=sentinel.denomination, decimal_places=5
        )
        self.assertEqual(result, sentinel.emi)
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address="EMI",
            denomination=sentinel.denomination,
            decimal_places=5,
        )
