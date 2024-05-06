# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.deposit.interest.fixed_interest_accrual as fixed_interest_accrual
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
)


class TestGetDailyInterestRate(FeatureTest):
    @patch.object(fixed_interest_accrual.utils, "yearly_to_daily_rate")
    @patch.object(fixed_interest_accrual.utils, "get_parameter")
    def test_get_daily_interest_rate(
        self, mock_get_parameter: MagicMock, mock_yearly_to_daily_rate: MagicMock
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                fixed_interest_accrual.PARAM_FIXED_INTEREST_RATE: Decimal("0.0365"),
                fixed_interest_accrual.interest_accrual_common.PARAM_DAYS_IN_YEAR: "actual",
            }
        )
        mock_yearly_to_daily_rate.return_value = Decimal("0.0001")

        result = fixed_interest_accrual.get_daily_interest_rate(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )
        self.assertEqual(result, Decimal("0.0001"))
        mock_yearly_to_daily_rate.assert_called_once_with(
            effective_date=DEFAULT_DATETIME, yearly_rate=Decimal("0.0365"), days_in_year="actual"
        )


class TestAccrueInterest(FeatureTest):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = self.create_mock()

        # get_parameter
        params = {
            fixed_interest_accrual.common_parameters.PARAM_DENOMINATION: sentinel.denomination,
            fixed_interest_accrual.PARAM_ACCRUAL_PRECISION: 2,
            fixed_interest_accrual.PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT: "payable_acc",
            fixed_interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: "receivable_acc",
        }
        patch_get_parameter = patch.object(fixed_interest_accrual.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=params)
        # get_daily_interest_rate
        patch_get_daily_interest_rate = patch.object(
            fixed_interest_accrual, "get_daily_interest_rate"
        )
        self.mock_get_daily_interest_rate = patch_get_daily_interest_rate.start()

        # get_accrual_capital
        patch_get_accrual_capital = patch.object(fixed_interest_accrual, "get_accrual_capital")
        self.mock_get_accrual_capital = patch_get_accrual_capital.start()
        self.mock_get_accrual_capital.return_value = Decimal("1000")

        # standard_instruction_details
        patch_standard_instruction_details = patch.object(
            fixed_interest_accrual.utils, "standard_instruction_details"
        )
        self.mock_standard_instruction_details = patch_standard_instruction_details.start()
        self.mock_standard_instruction_details.return_value = sentinel.instruction_details

        # accrual_custom_instruction
        patch_accrual_custom_instruction = patch.object(
            fixed_interest_accrual.accruals, "accrual_custom_instruction"
        )
        self.mock_accrual_custom_instruction = patch_accrual_custom_instruction.start()
        self.mock_accrual_custom_instruction.return_value = sentinel.accrual_instructions

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_payable_accrual_custom_instructions_returned(self):
        # positive interest rate => payable
        self.mock_get_daily_interest_rate.return_value = Decimal("0.01")

        expected_result = sentinel.accrual_instructions
        result = fixed_interest_accrual.accrue_interest(
            vault=self.mock_vault, effective_datetime=DEFAULT_DATETIME, account_type="PRODUCT"
        )
        self.assertEqual(result, expected_result)
        self.mock_accrual_custom_instruction.assert_called_once_with(
            customer_account=self.mock_vault.account_id,
            customer_address=fixed_interest_accrual.ACCRUED_INTEREST_PAYABLE,
            denomination=sentinel.denomination,
            amount=Decimal("10"),
            internal_account="payable_acc",
            payable=True,
            instruction_details=sentinel.instruction_details,
        )

    def test_receivable_accrual_custom_instructions_returned(self):
        # negative interest rate => receivable
        self.mock_get_daily_interest_rate.return_value = Decimal("-0.01")

        expected_result = sentinel.accrual_instructions
        result = fixed_interest_accrual.accrue_interest(
            vault=self.mock_vault, effective_datetime=DEFAULT_DATETIME, account_type="PRODUCT"
        )
        self.assertEqual(result, expected_result)
        self.mock_accrual_custom_instruction.assert_called_once_with(
            customer_account=self.mock_vault.account_id,
            customer_address=fixed_interest_accrual.ACCRUED_INTEREST_RECEIVABLE,
            denomination=sentinel.denomination,
            amount=Decimal("10"),
            internal_account="receivable_acc",
            payable=False,
            instruction_details=sentinel.instruction_details,
        )

    def test_optional_args_provided(self):
        self.mock_get_daily_interest_rate.return_value = Decimal("0.01")

        expected_result = sentinel.accrual_instructions
        result = fixed_interest_accrual.accrue_interest(
            vault=self.mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            account_type="PRODUCT",
            balances=sentinel.balances,
            accrued_interest_payable_account="PAYABLE",
            accrued_interest_receivable_account="RECEIVABLE",
        )

        self.assertEqual(result, expected_result)
        self.mock_get_accrual_capital.assert_called_once_with(
            vault=self.mock_vault, balances=sentinel.balances
        )
        self.mock_accrual_custom_instruction.assert_called_once_with(
            customer_account=self.mock_vault.account_id,
            customer_address=fixed_interest_accrual.ACCRUED_INTEREST_PAYABLE,
            denomination=sentinel.denomination,
            amount=Decimal("10"),
            internal_account="PAYABLE",
            payable=True,
            instruction_details=sentinel.instruction_details,
        )
