# standard libs
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.common.fetchers as fetchers
import library.features.v4.lending.early_repayment as early_repayment
import library.features.v4.lending.lending_interfaces as lending_interfaces

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ASSET,
    BalanceCoordinate,
    BalanceDefaultDict,
    CustomInstruction,
    Phase,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PRINCIPAL_COORDINATE = BalanceCoordinate(
    "PRINCIPAL",
    DEFAULT_ASSET,
    sentinel.denomination,
    Phase.COMMITTED,
)


class EarlyRepaymentTest(FeatureTest):
    maxDiff = None


@patch.object(early_repayment, "_get_balances")
@patch.object(early_repayment, "_get_denomination")
@patch.object(early_repayment, "_is_zero_principal")
@patch.object(early_repayment, "get_total_early_repayment_amount")
class IsPostingAnEarlyRepaymentTest(EarlyRepaymentTest):
    def test_is_posting_an_early_repayment_false_no_optional_args_supplied(
        self,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_is_zero_principal: MagicMock,
        mock_get_denomination: MagicMock,
        mock_get_balances: MagicMock,
    ):
        mock_get_total_early_repayment_amount.return_value = Decimal("300")
        mock_is_zero_principal.return_value = False
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_balances.return_value = sentinel.balances

        result = early_repayment.is_posting_an_early_repayment(
            vault=sentinel.vault,
            repayment_amount=Decimal("-500"),
            early_repayment_fees=[],
        )
        self.assertFalse(result)
        mock_get_denomination.assert_called_once_with(vault=sentinel.vault, denomination=None)
        mock_get_balances.assert_called_once_with(vault=sentinel.vault, balances=None)
        mock_get_total_early_repayment_amount.assert_called_once_with(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            early_repayment_fees=[],
            balances=sentinel.balances,
            precision=2,
        )
        mock_is_zero_principal.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )

    def test_is_posting_an_early_repayment_true_no_optional_args_supplied(
        self,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_is_zero_principal: MagicMock,
        mock_get_denomination: MagicMock,
        mock_get_balances: MagicMock,
    ):
        mock_get_total_early_repayment_amount.return_value = Decimal("300")
        mock_is_zero_principal.return_value = False
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_balances.return_value = sentinel.balances

        result = early_repayment.is_posting_an_early_repayment(
            vault=sentinel.vault,
            repayment_amount=Decimal("-300"),
            early_repayment_fees=[],
        )
        self.assertTrue(result)
        mock_get_denomination.assert_called_once_with(vault=sentinel.vault, denomination=None)
        mock_get_balances.assert_called_once_with(vault=sentinel.vault, balances=None)
        mock_get_total_early_repayment_amount.assert_called_once_with(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            early_repayment_fees=[],
            balances=sentinel.balances,
            precision=2,
        )
        mock_is_zero_principal.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )

    def test_is_posting_an_early_repayment_false_with_optional_args_supplied(
        self,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_is_zero_principal: MagicMock,
        mock_get_denomination: MagicMock,
        mock_get_balances: MagicMock,
    ):
        mock_get_total_early_repayment_amount.return_value = Decimal("300")
        mock_is_zero_principal.return_value = False
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_balances.return_value = sentinel.balances

        result = early_repayment.is_posting_an_early_repayment(
            vault=sentinel.vault,
            repayment_amount=Decimal("-500"),
            early_repayment_fees=[sentinel.early_repayment_fee],
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=1,
        )
        self.assertFalse(result)
        mock_get_denomination.assert_called_once_with(
            vault=sentinel.vault, denomination=sentinel.denomination
        )
        mock_get_balances.assert_called_once_with(vault=sentinel.vault, balances=sentinel.balances)
        mock_get_total_early_repayment_amount.assert_called_once_with(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            early_repayment_fees=[sentinel.early_repayment_fee],
            balances=sentinel.balances,
            precision=1,
        )
        mock_is_zero_principal.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )

    def test_is_posting_an_early_repayment_true_with_optional_args_supplied(
        self,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_is_zero_principal: MagicMock,
        mock_get_denomination: MagicMock,
        mock_get_balances: MagicMock,
    ):
        mock_get_total_early_repayment_amount.return_value = Decimal("300")
        mock_is_zero_principal.return_value = False
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_balances.return_value = sentinel.balances

        result = early_repayment.is_posting_an_early_repayment(
            vault=sentinel.vault,
            repayment_amount=Decimal("-300"),
            early_repayment_fees=[sentinel.early_repayment_fee],
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=1,
        )
        self.assertTrue(result)
        mock_get_denomination.assert_called_once_with(
            vault=sentinel.vault, denomination=sentinel.denomination
        )
        mock_get_balances.assert_called_once_with(vault=sentinel.vault, balances=sentinel.balances)
        mock_get_total_early_repayment_amount.assert_called_once_with(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            early_repayment_fees=[sentinel.early_repayment_fee],
            balances=sentinel.balances,
            precision=1,
        )
        mock_is_zero_principal.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )

    def test_is_posting_an_early_repayment_zero_repayment_amount(
        self,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_is_zero_principal: MagicMock,
        mock_get_denomination: MagicMock,
        mock_get_balances: MagicMock,
    ):
        mock_get_total_early_repayment_amount.return_value = Decimal("300")
        mock_is_zero_principal.return_value = False
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_balances.return_value = sentinel.balances

        result = early_repayment.is_posting_an_early_repayment(
            vault=sentinel.vault,
            repayment_amount=Decimal("0"),
            early_repayment_fees=[sentinel.early_repayment_fee],
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=1,
        )
        self.assertFalse(result)
        mock_get_denomination.assert_not_called()
        mock_get_balances.assert_not_called()
        mock_get_total_early_repayment_amount.assert_not_called()
        mock_is_zero_principal.assert_not_called()

    def test_is_posting_an_early_repayment_zero_principal(
        self,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_is_zero_principal: MagicMock,
        mock_get_denomination: MagicMock,
        mock_get_balances: MagicMock,
    ):
        mock_get_total_early_repayment_amount.return_value = Decimal("300")
        mock_is_zero_principal.return_value = True
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_balances.return_value = sentinel.balances

        result = early_repayment.is_posting_an_early_repayment(
            vault=sentinel.vault,
            repayment_amount=Decimal("-1000"),
            early_repayment_fees=[sentinel.early_repayment_fee],
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=1,
        )
        self.assertFalse(result)
        mock_get_denomination.assert_called_once_with(
            vault=sentinel.vault, denomination=sentinel.denomination
        )
        mock_get_balances.assert_called_once_with(vault=sentinel.vault, balances=sentinel.balances)
        mock_get_total_early_repayment_amount.assert_not_called()
        mock_is_zero_principal.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )


@patch.object(early_repayment, "_get_balances")
@patch.object(early_repayment, "_get_denomination")
@patch.object(early_repayment, "_is_zero_principal")
@patch.object(early_repayment, "_get_sum_of_early_repayment_fees_and_outstanding_debt")
class GetTotalEarlyRepaymentAmountTest(EarlyRepaymentTest):
    def test_get_total_early_repayment_amount_no_optional_args_supplied(
        self,
        mock_get_sum_of_early_repayment_fees_and_outstanding_debt: MagicMock,
        mock_is_zero_principal: MagicMock,
        mock_get_denomination: MagicMock,
        mock_get_balances: MagicMock,
    ):
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_balances.return_value = sentinel.balances
        mock_is_zero_principal.return_value = False
        mock_get_sum_of_early_repayment_fees_and_outstanding_debt.return_value = sentinel.amount

        result = early_repayment.get_total_early_repayment_amount(
            vault=sentinel.vault,
            early_repayment_fees=[],
        )
        self.assertEqual(sentinel.amount, result)
        mock_get_denomination.assert_called_once_with(vault=sentinel.vault, denomination=None)
        mock_get_balances.assert_called_once_with(vault=sentinel.vault, balances=None)
        mock_is_zero_principal.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_get_sum_of_early_repayment_fees_and_outstanding_debt.assert_called_once_with(
            vault=sentinel.vault,
            early_repayment_fees=[],
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=2,
            debt_addresses=[
                "PRINCIPAL_OVERDUE",
                "INTEREST_OVERDUE",
                "PENALTIES",
                "PRINCIPAL_DUE",
                "INTEREST_DUE",
                "PRINCIPAL",
                "ACCRUED_INTEREST_RECEIVABLE",
                "ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION",
            ],
        )

    def test_get_total_early_repayment_amount_with_optional_args_supplied(
        self,
        mock_get_sum_of_early_repayment_fees_and_outstanding_debt: MagicMock,
        mock_is_zero_principal: MagicMock,
        mock_get_denomination: MagicMock,
        mock_get_balances: MagicMock,
    ):
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_balances.return_value = sentinel.balances
        mock_is_zero_principal.return_value = False
        mock_get_sum_of_early_repayment_fees_and_outstanding_debt.return_value = sentinel.amount

        def _get_early_repayment_fee_amount(
            vault: SmartContractVault,
            balances: BalanceDefaultDict,
            denomination: str,
            precision: int = 2,
        ):
            return sentinel.early_repayment_fee_amount

        def _charge_early_repayment_fee(
            vault: SmartContractVault,
            account_id: str,
            amount_to_charge: Decimal,
            fee_name: str,
            denomination: Optional[str] = None,
        ) -> list[CustomInstruction]:
            return [sentinel.custom_instruction]

        early_repayment_fees = [
            lending_interfaces.EarlyRepaymentFee(
                get_early_repayment_fee_amount=_get_early_repayment_fee_amount,
                charge_early_repayment_fee=_charge_early_repayment_fee,
                fee_name="Dummy early repayment fee 1",
            ),
            lending_interfaces.EarlyRepaymentFee(
                get_early_repayment_fee_amount=_get_early_repayment_fee_amount,
                charge_early_repayment_fee=_charge_early_repayment_fee,
                fee_name="Dummy early repayment fee 2",
            ),
        ]

        result = early_repayment.get_total_early_repayment_amount(
            vault=sentinel.vault,
            early_repayment_fees=early_repayment_fees,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=1,
        )
        # 110 = early_repayment_fee_amount 5 * number of fees 2 + total_outstanding_debt 100
        self.assertEqual(sentinel.amount, result)
        mock_get_denomination.assert_called_once_with(
            vault=sentinel.vault, denomination=sentinel.denomination
        )
        mock_get_balances.assert_called_once_with(vault=sentinel.vault, balances=sentinel.balances)
        mock_is_zero_principal.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_get_sum_of_early_repayment_fees_and_outstanding_debt.assert_called_once_with(
            vault=sentinel.vault,
            early_repayment_fees=early_repayment_fees,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=1,
            debt_addresses=[
                "PRINCIPAL_OVERDUE",
                "INTEREST_OVERDUE",
                "PENALTIES",
                "PRINCIPAL_DUE",
                "INTEREST_DUE",
                "PRINCIPAL",
                "ACCRUED_INTEREST_RECEIVABLE",
                "ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION",
            ],
        )

    def test_get_total_early_repayment_amount_with_zero_principal_no_check_for_accrued_interest(
        self,
        mock_get_sum_of_early_repayment_fees_and_outstanding_debt: MagicMock,
        mock_is_zero_principal: MagicMock,
        mock_get_denomination: MagicMock,
        mock_get_balances: MagicMock,
    ):
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_balances.return_value = sentinel.balances
        mock_is_zero_principal.return_value = True

        result = early_repayment.get_total_early_repayment_amount(
            vault=sentinel.vault,
            early_repayment_fees=[],
            check_for_outstanding_accrued_interest_on_zero_principal=False,
        )
        self.assertEqual(Decimal("0.00"), result)
        mock_is_zero_principal.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_get_sum_of_early_repayment_fees_and_outstanding_debt.assert_not_called()

    def test_get_total_early_repayment_amount_with_zero_principal_and_check_for_accrued_interest(
        self,
        mock_get_sum_of_early_repayment_fees_and_outstanding_debt: MagicMock,
        mock_is_zero_principal: MagicMock,
        mock_get_denomination: MagicMock,
        mock_get_balances: MagicMock,
    ):
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_balances.return_value = sentinel.balances
        mock_is_zero_principal.return_value = True
        mock_get_sum_of_early_repayment_fees_and_outstanding_debt.return_value = sentinel.amount

        result = early_repayment.get_total_early_repayment_amount(
            vault=sentinel.vault,
            early_repayment_fees=[],
            check_for_outstanding_accrued_interest_on_zero_principal=True,
        )
        self.assertEqual(sentinel.amount, result)
        mock_get_denomination.assert_called_once_with(vault=sentinel.vault, denomination=None)
        mock_get_balances.assert_called_once_with(vault=sentinel.vault, balances=None)
        mock_is_zero_principal.assert_not_called()
        mock_get_sum_of_early_repayment_fees_and_outstanding_debt.assert_called_once_with(
            vault=sentinel.vault,
            early_repayment_fees=[],
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=2,
            debt_addresses=[
                "PRINCIPAL_OVERDUE",
                "INTEREST_OVERDUE",
                "PENALTIES",
                "PRINCIPAL_DUE",
                "INTEREST_DUE",
                "PRINCIPAL",
                "ACCRUED_INTEREST_RECEIVABLE",
                "ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION",
            ],
        )


@patch.object(early_repayment.utils, "get_parameter")
@patch.object(early_repayment.utils, "round_decimal")
class FlatFeeTest(EarlyRepaymentTest):
    def test_get_early_repayment_flat_fee_no_optional_args_supplied(
        self,
        mock_round_decimal: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.return_value = sentinel.parameter_value
        mock_round_decimal.return_value = sentinel.flat_fee
        result = early_repayment.get_early_repayment_flat_fee(
            vault=sentinel.vault,
        )
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault, name="early_repayment_flat_fee"
        )
        mock_round_decimal.assert_called_once_with(sentinel.parameter_value, 2)
        self.assertEqual(sentinel.flat_fee, result)

    def test_get_early_repayment_flat_fee_with_optional_args_supplied(
        self,
        mock_round_decimal: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.return_value = sentinel.parameter_value
        mock_round_decimal.return_value = sentinel.flat_fee
        result = early_repayment.get_early_repayment_flat_fee(
            vault=sentinel.vault,
            balances=sentinel.balance,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault, name="early_repayment_flat_fee"
        )
        mock_round_decimal.assert_called_once_with(sentinel.parameter_value, sentinel.precision)
        self.assertEqual(sentinel.flat_fee, result)


@patch.object(early_repayment, "_get_balances")
@patch.object(early_repayment, "_get_denomination")
@patch.object(early_repayment.utils, "get_parameter")
@patch.object(early_repayment.utils, "round_decimal")
@patch.object(early_repayment.derived_params, "get_total_remaining_principal")
class PercentageFeeTest(EarlyRepaymentTest):
    def test_calculate_early_repayment_percentage_fee_no_optional_args_supplied(
        self,
        mock_get_total_remaining_principal: MagicMock,
        mock_round_decimal: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_denomination: MagicMock,
        mock_get_balances: MagicMock,
    ):
        mock_get_balances.return_value = sentinel.balances
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_total_remaining_principal.return_value = Decimal("100")
        mock_get_parameter.return_value = Decimal("0.1")
        mock_round_decimal.return_value = sentinel.repayment_fee
        result = early_repayment.calculate_early_repayment_percentage_fee(
            vault=sentinel.vault,
        )
        mock_get_balances.assert_called_once_with(vault=sentinel.vault, balances=None)
        mock_get_denomination.assert_called_once_with(vault=sentinel.vault, denomination=None)
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault, name="early_repayment_fee_rate"
        )
        # 10 = remaining_principal 100 * fee rate 0.1
        mock_round_decimal.assert_called_once_with(Decimal("10"), 2)
        mock_get_total_remaining_principal.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        self.assertEqual(sentinel.repayment_fee, result)

    def test_calculate_early_repayment_percentage_fee_with_optional_args_supplied(
        self,
        mock_get_total_remaining_principal: MagicMock,
        mock_round_decimal: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_denomination: MagicMock,
        mock_get_balances: MagicMock,
    ):
        mock_get_balances.return_value = sentinel.balances
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_total_remaining_principal.return_value = Decimal("100")
        mock_get_parameter.return_value = Decimal("0.1")
        mock_round_decimal.return_value = sentinel.repayment_fee
        result = early_repayment.calculate_early_repayment_percentage_fee(
            vault=sentinel.vault,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        mock_get_balances.assert_called_once_with(vault=sentinel.vault, balances=sentinel.balances)
        mock_get_denomination.assert_called_once_with(
            vault=sentinel.vault, denomination=sentinel.denomination
        )
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault, name="early_repayment_fee_rate"
        )
        # 10 = remaining_principal 100 * fee rate 0.1
        mock_round_decimal.assert_called_once_with(Decimal("10"), sentinel.precision)
        mock_get_total_remaining_principal.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        self.assertEqual(sentinel.repayment_fee, result)


@patch.object(early_repayment, "_get_denomination")
@patch.object(early_repayment.utils, "get_parameter")
@patch.object(early_repayment.fees, "fee_custom_instruction")
class ChargeFeeTest(EarlyRepaymentTest):
    def test_charge_early_repayment_fee_no_optional_args_supplied(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_denomination: MagicMock,
    ):
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_parameter.return_value = sentinel.parameter_value
        mock_fee_custom_instruction.return_value = sentinel.custom_instructions
        result = early_repayment.charge_early_repayment_fee(
            vault=sentinel.vault,
            account_id=sentinel.account_id,
            amount_to_charge=sentinel.amount_to_charge,
            fee_name=sentinel.fee_name,
        )
        mock_get_denomination.assert_called_once_with(vault=sentinel.vault, denomination=None)
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault, name="early_repayment_fee_income_account"
        )
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=sentinel.account_id,
            denomination=sentinel.denomination,
            amount=sentinel.amount_to_charge,
            internal_account=sentinel.parameter_value,
            instruction_details={"description": "Early Repayment Fee: sentinel.fee_name"},
        )
        self.assertEqual(sentinel.custom_instructions, result)

    def test_charge_early_repayment_fee_with_optional_args_supplied(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_denomination: MagicMock,
    ):
        mock_get_denomination.return_value = sentinel.denomination
        mock_get_parameter.return_value = sentinel.parameter_value
        mock_fee_custom_instruction.return_value = sentinel.custom_instructions
        result = early_repayment.charge_early_repayment_fee(
            vault=sentinel.vault,
            account_id=sentinel.account_id,
            amount_to_charge=sentinel.amount_to_charge,
            fee_name=sentinel.fee_name,
            denomination=sentinel.denomination,
        )
        mock_get_denomination.assert_called_once_with(
            vault=sentinel.vault, denomination=sentinel.denomination
        )
        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault, name="early_repayment_fee_income_account"
        )
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=sentinel.account_id,
            denomination=sentinel.denomination,
            amount=sentinel.amount_to_charge,
            internal_account=sentinel.parameter_value,
            instruction_details={"description": "Early Repayment Fee: sentinel.fee_name"},
        )
        self.assertEqual(sentinel.custom_instructions, result)


@patch.object(early_repayment.utils, "sum_balances")
class IsZeroPrincipalTest(EarlyRepaymentTest):
    def test_is_zero_principal_false(
        self,
        mock_sum_balances: MagicMock,
    ):
        mock_sum_balances.return_value = Decimal("100")
        result = early_repayment._is_zero_principal(
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )
        self.assertFalse(result)
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances, addresses=["PRINCIPAL"], denomination=sentinel.denomination
        )

    def test_is_zero_principal_true(
        self,
        mock_sum_balances: MagicMock,
    ):
        mock_sum_balances.return_value = Decimal("0")
        result = early_repayment._is_zero_principal(
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )
        self.assertTrue(result)
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances, addresses=["PRINCIPAL"], denomination=sentinel.denomination
        )

    def test_is_zero_principal_true_with_balances_lt_zero(
        self,
        mock_sum_balances: MagicMock,
    ):
        mock_sum_balances.return_value = Decimal("-100")
        result = early_repayment._is_zero_principal(
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )
        self.assertTrue(result)
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances, addresses=["PRINCIPAL"], denomination=sentinel.denomination
        )


@patch.object(early_repayment.utils, "get_parameter")
class GetDenominationTest(EarlyRepaymentTest):
    def test_get_denomination_no_optional_args(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.return_value = sentinel.denomination
        result = early_repayment._get_denomination(
            vault=sentinel.vault,
        )
        self.assertEqual(sentinel.denomination, result)
        mock_get_parameter.assert_called_once_with(vault=sentinel.vault, name="denomination")

    def test_get_denomination_with_optional_args(
        self,
        mock_get_parameter: MagicMock,
    ):
        result = early_repayment._get_denomination(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
        )
        self.assertEqual(sentinel.denomination, result)
        mock_get_parameter.assert_not_called()


class GetBalancesTest(EarlyRepaymentTest):
    def test_get_balances_no_optional_args(
        self,
    ):
        live_balance_obs = SentinelBalancesObservation("live")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={fetchers.LIVE_BALANCES_BOF_ID: live_balance_obs}
        )
        result = early_repayment._get_balances(
            vault=mock_vault,
        )
        self.assertEqual(sentinel.balances_live, result)

    def test_get_balances_with_optional_args(
        self,
    ):
        result = early_repayment._get_balances(
            vault=sentinel.vault,
            balances=sentinel.balances,
        )
        self.assertEqual(sentinel.balances, result)


@patch.object(early_repayment.derived_params, "get_total_outstanding_debt")
class GetSumOfEarlyRepaymentFeesAndOutstandingDebtTest(EarlyRepaymentTest):
    def test_get_sum_of_early_repayment_fees_and_outstanding_debt(
        self,
        mock_get_total_outstanding_debt: MagicMock,
    ):
        total_outstanding_debt = Decimal("100")
        early_repayment_fee_amount = Decimal("5")
        mock_get_total_outstanding_debt.return_value = total_outstanding_debt

        def _get_early_repayment_fee_amount(
            vault: SmartContractVault,
            balances: BalanceDefaultDict,
            denomination: str,
            precision: int = 2,
        ):
            return early_repayment_fee_amount

        def _charge_early_repayment_fee(
            vault: SmartContractVault,
            account_id: str,
            amount_to_charge: Decimal,
            fee_name: str,
            denomination: Optional[str] = None,
        ) -> list[CustomInstruction]:
            return [sentinel.custom_instruction]

        early_repayment_fees = [
            lending_interfaces.EarlyRepaymentFee(
                get_early_repayment_fee_amount=_get_early_repayment_fee_amount,
                charge_early_repayment_fee=_charge_early_repayment_fee,
                fee_name="Dummy early repayment fee 1",
            ),
            lending_interfaces.EarlyRepaymentFee(
                get_early_repayment_fee_amount=_get_early_repayment_fee_amount,
                charge_early_repayment_fee=_charge_early_repayment_fee,
                fee_name="Dummy early repayment fee 2",
            ),
        ]

        result = early_repayment._get_sum_of_early_repayment_fees_and_outstanding_debt(
            vault=sentinel.vault,
            early_repayment_fees=early_repayment_fees,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=2,
            debt_addresses=sentinel.addresses,
        )
        # 110 = early_repayment_fee_amount 5 * number of fees 2 + total_outstanding_debt 100
        self.assertEqual(Decimal("110"), result)
        mock_get_total_outstanding_debt.assert_called_once_with(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            debt_addresses=sentinel.addresses,
        )
