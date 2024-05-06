# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# features
import library.features.v4.deposit.interest.deposit_interest_accrual_common as deposit_interest_accrual_common  # noqa: E501
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ADDRESS,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)

EOD_SENTINEL_FETCHER = {
    deposit_interest_accrual_common.fetchers.EOD_FETCHER_ID: SentinelBalancesObservation("eod")
}
EFFECTIVE_SENTINEL_FETCHER = {
    deposit_interest_accrual_common.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
        SentinelBalancesObservation("effective")
    )
}

interest_accrual_common = deposit_interest_accrual_common.interest_accrual_common


class TestInterestAccrualCapital(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=EOD_SENTINEL_FETCHER
        )

        # get_parameter
        patch_get_parameter = patch.object(deposit_interest_accrual_common.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )

        # sum_balances
        patch_sum_balances = patch.object(deposit_interest_accrual_common.utils, "sum_balances")
        self.mock_sum_balances = patch_sum_balances.start()
        self.mock_sum_balances.side_effect = [Decimal(100)]
        return super().setUp()

    def test_get_accrual_capital(self):
        self.assertEqual(
            deposit_interest_accrual_common.get_accrual_capital(
                vault=self.mock_vault, capital_addresses=sentinel.capital_addresses
            ),
            Decimal(100),
        )

        self.mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances_eod,
            addresses=sentinel.capital_addresses,
            denomination=sentinel.denomination,
        )

    def test_get_accrual_capital_default_address(self):
        self.assertEqual(
            deposit_interest_accrual_common.get_accrual_capital(vault=self.mock_vault),
            Decimal(100),
        )

        self.mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances_eod,
            addresses=[DEFAULT_ADDRESS],
            denomination=sentinel.denomination,
        )

    def test_get_accrual_capital_negative_balance(self):
        self.mock_sum_balances.side_effect = [Decimal(-100)]
        self.assertEqual(
            deposit_interest_accrual_common.get_accrual_capital(
                vault=self.mock_vault, capital_addresses=sentinel.capital_addresses
            ),
            Decimal(0),
        )

        self.mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances_eod,
            addresses=sentinel.capital_addresses,
            denomination=sentinel.denomination,
        )

    def test_get_accrual_capital_uses_provided_balances(self):
        self.mock_sum_balances.side_effect = [Decimal(-100)]
        self.assertEqual(
            deposit_interest_accrual_common.get_accrual_capital(
                vault=self.mock_vault,
                balances=sentinel.provided_balances,
                capital_addresses=sentinel.capital_addresses,
            ),
            Decimal(0),
        )

        self.mock_sum_balances.assert_called_once_with(
            balances=sentinel.provided_balances,
            addresses=sentinel.capital_addresses,
            denomination=sentinel.denomination,
        )


class TestReverseInterestAccrual(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=EFFECTIVE_SENTINEL_FETCHER
        )

        # get_parameter
        patch_get_parameter = patch.object(deposit_interest_accrual_common.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": "GBP",
                "accrued_interest_payable_account": "payable_acc",
                "accrued_interest_receivable_account": "receivable_acc",
            }
        )

        # sum_balances
        patch_sum_balances = patch.object(deposit_interest_accrual_common.utils, "sum_balances")
        self.mock_sum_balances = patch_sum_balances.start()

        # accrual_custom_instruction
        patch_accrual_custom_instruction = patch.object(
            deposit_interest_accrual_common.accruals, "accrual_custom_instruction"
        )
        self.mock_accrual_custom_instruction = patch_accrual_custom_instruction.start()

        return super().setUp()

    def test_reverse_payable_interest(self):
        self.mock_sum_balances.side_effect = [
            Decimal("0"),  # receivable
            Decimal("1.5"),  # payable
        ]
        self.mock_accrual_custom_instruction.return_value = [
            SentinelCustomInstruction("internal_payable")
        ]

        reversal_postings = deposit_interest_accrual_common.get_interest_reversal_postings(
            vault=self.mock_vault, event_name="CLOSE_ACCOUNT"
        )

        self.mock_accrual_custom_instruction.assert_called_with(
            customer_account=self.mock_vault.account_id,
            customer_address=interest_accrual_common.ACCRUED_INTEREST_PAYABLE,
            denomination="GBP",
            amount=Decimal("1.5"),
            internal_account="payable_acc",
            payable=True,
            instruction_details={
                "description": "Reversing 1.5 GBP of accrued interest",
                "event": "CLOSE_ACCOUNT",
                "gl_impacted": "True",
                "account_type": "",
            },
            reversal=True,
        )

        self.assertEqual(len(reversal_postings), 1)
        self.assertListEqual(reversal_postings, [SentinelCustomInstruction("internal_payable")])

    def test_reverse_receivable_interest(
        self,
    ):
        self.mock_sum_balances.side_effect = [
            Decimal("1.5"),  # receivable
            Decimal("0"),  # payable
        ]
        self.mock_accrual_custom_instruction.return_value = [
            SentinelCustomInstruction("internal receivable")
        ]

        reversal_postings = deposit_interest_accrual_common.get_interest_reversal_postings(
            vault=self.mock_vault, event_name="CLOSE_ACCOUNT"
        )

        self.mock_accrual_custom_instruction.assert_called_with(
            customer_account=self.mock_vault.account_id,
            customer_address=interest_accrual_common.ACCRUED_INTEREST_RECEIVABLE,
            denomination="GBP",
            amount=Decimal("1.5"),
            internal_account="receivable_acc",
            payable=False,
            instruction_details={
                "description": "Reversing 1.5 GBP of accrued interest",
                "event": "CLOSE_ACCOUNT",
                "gl_impacted": "True",
                "account_type": "",
            },
            reversal=True,
        )

        self.assertEqual(len(reversal_postings), 1)
        self.assertListEqual(reversal_postings, [SentinelCustomInstruction("internal receivable")])

    def test_no_reverse_interest_balance_0(self):
        self.mock_sum_balances.side_effect = [
            Decimal("0"),  # receivable
            Decimal("0"),  # payable
        ]

        reversal_postings = deposit_interest_accrual_common.get_interest_reversal_postings(
            vault=self.mock_vault, event_name="CLOSE_ACCOUNT"
        )

        self.assertListEqual(reversal_postings, [])
        self.mock_accrual_custom_instruction.assert_not_called()

    def test_reverse_interest_balances_and_denomination_provided(self):
        # construct mocks
        self.mock_sum_balances.side_effect = [
            Decimal("1.5"),  # receivable
            Decimal("0"),  # payable
        ]
        self.mock_accrual_custom_instruction.return_value = [
            SentinelCustomInstruction("internal_receivable")
        ]

        # run function with balances provided
        reversal_postings = deposit_interest_accrual_common.get_interest_reversal_postings(
            vault=self.mock_vault,
            event_name="CLOSE_ACCOUNT",
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertEqual(reversal_postings, [SentinelCustomInstruction("internal_receivable")])

        # call assertions
        self.mock_sum_balances.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances,
                    addresses=[interest_accrual_common.ACCRUED_INTEREST_RECEIVABLE],
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.balances,
                    addresses=[interest_accrual_common.ACCRUED_INTEREST_PAYABLE],
                    denomination=sentinel.denomination,
                ),
            ]
        )
        self.mock_accrual_custom_instruction.assert_called_with(
            customer_account=self.mock_vault.account_id,
            customer_address=interest_accrual_common.ACCRUED_INTEREST_RECEIVABLE,
            denomination=sentinel.denomination,
            amount=Decimal("1.5"),
            internal_account="receivable_acc",
            payable=False,
            instruction_details={
                "description": "Reversing 1.5 sentinel.denomination of accrued interest",
                "event": "CLOSE_ACCOUNT",
                "gl_impacted": "True",
                "account_type": "",
            },
            reversal=True,
        )


@patch.object(deposit_interest_accrual_common.utils, "get_parameter")
class TestGetTargetCustomerAddressAndInternalAccount(FeatureTest):
    def test_positive_accrual_amount_returns_payable_address_and_account(
        self, mock_get_parameter: MagicMock
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "accrued_interest_payable_account": "payable",
                "accrued_interest_receivable_account": "receivable",
            }
        )

        result = deposit_interest_accrual_common.get_target_customer_address_and_internal_account(
            vault=mock_vault, accrual_amount=Decimal("10")
        )
        self.assertTupleEqual(
            result,
            (
                deposit_interest_accrual_common.interest_accrual_common.ACCRUED_INTEREST_PAYABLE,
                "payable",
            ),
        )

    def test_negative_accrual_amount_returns_receivable_address_and_account(
        self, mock_get_parameter: MagicMock
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "accrued_interest_payable_account": "payable",
                "accrued_interest_receivable_account": "receivable",
            }
        )

        result = deposit_interest_accrual_common.get_target_customer_address_and_internal_account(
            vault=mock_vault, accrual_amount=Decimal("-10")
        )
        self.assertTupleEqual(
            result,
            (
                deposit_interest_accrual_common.interest_accrual_common.ACCRUED_INTEREST_RECEIVABLE,
                "receivable",
            ),
        )

    def test_positive_accrual_amount_returns_payable_address_and_provided_account(
        self, mock_get_parameter: MagicMock
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "accrued_interest_payable_account": "payable",
                "accrued_interest_receivable_account": "receivable",
            }
        )

        result = deposit_interest_accrual_common.get_target_customer_address_and_internal_account(
            vault=mock_vault,
            accrual_amount=Decimal("10"),
            accrued_interest_payable_account="PAYABLE",
            accrued_interest_receivable_account="RECEIVABLE",
        )
        self.assertTupleEqual(
            result,
            (
                deposit_interest_accrual_common.interest_accrual_common.ACCRUED_INTEREST_PAYABLE,
                "PAYABLE",
            ),
        )

    def test_negative_accrual_amount_returns_receivable_address_and_provided_account(
        self, mock_get_parameter: MagicMock
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "accrued_interest_payable_account": "payable",
                "accrued_interest_receivable_account": "receivable",
            }
        )

        result = deposit_interest_accrual_common.get_target_customer_address_and_internal_account(
            vault=mock_vault,
            accrual_amount=Decimal("-10"),
            accrued_interest_payable_account="PAYABLE",
            accrued_interest_receivable_account="RECEIVABLE",
        )
        self.assertTupleEqual(
            result,
            (
                deposit_interest_accrual_common.interest_accrual_common.ACCRUED_INTEREST_RECEIVABLE,
                "RECEIVABLE",
            ),
        )
