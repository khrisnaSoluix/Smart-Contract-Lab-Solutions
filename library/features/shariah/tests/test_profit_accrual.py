# standard library
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from unittest.mock import Mock, patch, call

# inception imports
from inception_sdk.test_framework.contracts.unit.common import (
    ContractFeatureTest,
)
from inception_sdk.vault.contracts.types_extension import (
    UnionItemValue,
    CalendarEvent,
    DEFAULT_ASSET,
    DEFAULT_ADDRESS,
)

from library.features.shariah.profit_accrual import (
    get_execution_schedules,
    _get_accrual_capital,
    get_accrual_posting_instructions,
    get_apply_accrual_posting_instructions,
    get_residual_cleanup_posting_instructions,
)

DEFAULT_DENOMINATION = "MYR"
DEFAULT_DATE = datetime(2019, 1, 1)
ACCRUED_PROFIT_PAYABLE_ACCOUNT = "ACCRUED_PROFIT_PAYABLE"
ACCRUAL_APPLICATION_EVENT = "APPLY_ACCRUED_PROFIT"
ACCRUAL_EVENT = "ACCRUE_PROFIT"
PROFIT_PAID_ACCOUNT = "PROFIT_PAID"
PUBLIC_HOLIDAYS = "&{PUBLIC_HOLIDAYS}"
INTERNAL_CONTRA = "INTERNAL_CONTRA"
ACCRUED_PROFIT_PAYABLE_ADDRESS = "ACCRUED_PROFIT_PAYABLE"


class TestProfitAccrualBase(ContractFeatureTest):
    target_test_file = "library/features/shariah/profit_accrual.py"

    def create_mock(
        self,
        balance_ts=None,
        creation_date=DEFAULT_DATE,
        days_in_year=UnionItemValue("365"),
        profit_accrual_hour=0,
        profit_accrual_minute=0,
        profit_accrual_second=0,
        profit_application_hour=0,
        profit_application_minute=0,
        profit_application_second=0,
        profit_application_frequency=UnionItemValue("monthly"),
        accrued_profit_payable_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
        profit_paid_account=PROFIT_PAID_ACCOUNT,
        **kwargs,
    ):
        params = {
            key: {"value": value}
            for key, value in locals().items()
            if key not in self.locals_to_ignore
        }
        parameter_ts = self.param_map_to_timeseries(params, creation_date)
        return super().create_mock(
            balance_ts=balance_ts or self.init_balances({"net": "98"}),
            parameter_ts=parameter_ts,
            creation_date=creation_date,
            **kwargs,
        )

    @classmethod
    def setupClass(cls):
        cls.maxDiff = None
        super().setUpClass()


class TestProfitAccrualSchedules(TestProfitAccrualBase):
    def test_profit_accrual_execution_schedules_for_monthly_apply(self):
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 9, 1),
            profit_application_day=5,
            profit_accrual_hour=1,
            profit_accrual_minute=2,
            profit_accrual_second=3,
            profit_application_hour=4,
            profit_application_minute=5,
            profit_application_second=6,
            profit_application_frequency=UnionItemValue("monthly"),
        )
        actual_schedules = get_execution_schedules(mock_vault)
        expected_schedules = [
            (
                ACCRUAL_EVENT,
                {
                    "hour": "1",
                    "minute": "2",
                    "second": "3",
                },
            ),
            (
                ACCRUAL_APPLICATION_EVENT,
                {
                    "year": "2019",
                    "month": "9",
                    "day": "5",
                    "hour": "4",
                    "minute": "5",
                    "second": "6",
                },
            ),
        ]
        self.assertEqual(actual_schedules, expected_schedules)

    def test_profit_accrual_execution_schedules_for_quarterly_apply(self):
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 9, 1),
            profit_application_day=5,
            profit_application_frequency=UnionItemValue("quarterly"),
        )
        actual_schedules = get_execution_schedules(mock_vault)
        expected_schedules = [
            (
                ACCRUAL_EVENT,
                {
                    "hour": "0",
                    "minute": "0",
                    "second": "0",
                },
            ),
            (
                ACCRUAL_APPLICATION_EVENT,
                {
                    "year": "2019",
                    "month": "12",
                    "day": "5",
                    "hour": "0",
                    "minute": "0",
                    "second": "0",
                },
            ),
        ]
        self.assertEqual(actual_schedules, expected_schedules)

    def test_profit_accrual_execution_schedules_for_annual_with_calendar(self):
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 9, 1),
            profit_application_day=5,
            profit_application_frequency=UnionItemValue("annually"),
            calendar_events=[
                CalendarEvent(
                    "TEST",
                    PUBLIC_HOLIDAYS,
                    datetime(2020, 9, 5, 0, 0, 0),
                    datetime(2020, 9, 6, 23, 23, 59),
                )
            ],
        )
        actual_schedules = get_execution_schedules(mock_vault)
        expected_schedules = [
            (
                ACCRUAL_EVENT,
                {
                    "hour": "0",
                    "minute": "0",
                    "second": "0",
                },
            ),
            (
                ACCRUAL_APPLICATION_EVENT,
                {
                    "year": "2020",
                    "month": "9",
                    "day": "7",
                    "hour": "0",
                    "minute": "0",
                    "second": "0",
                },
            ),
        ]
        self.assertEqual(actual_schedules, expected_schedules)


class TestProfitAccrual(TestProfitAccrualBase):
    @patch("library.features.common.utils.get_balance_sum")
    def test_get_accrual_capital_default_address(self, mock_get_balance_sum):
        effective_date = datetime(2019, 9, 2, 1, 2, 3)
        mock_vault = self.create_mock(
            profit_accrual_hour=effective_date.hour,
            profit_accrual_minute=effective_date.minute,
            profit_accrual_second=effective_date.second,
        )

        _get_accrual_capital(mock_vault, effective_date, "GBP")

        mock_get_balance_sum.assert_called_once_with(
            mock_vault,
            ["DEFAULT"],
            denomination="GBP",
            # balance at midnight minus 1 micro second of the effective date
            timestamp=datetime(2019, 9, 1, 23, 59, 59, 999999),
        )

    @patch("library.features.common.utils.get_balance_sum")
    def test_get_accrual_capital_specific_address(self, mock_get_balance_sum):
        effective_date = datetime(2019, 9, 2, 5, 4, 2)
        mock_vault = self.create_mock(
            profit_accrual_hour=effective_date.hour,
            profit_accrual_minute=effective_date.minute,
            profit_accrual_second=effective_date.second,
        )

        _get_accrual_capital(
            mock_vault, effective_date, "GBP", capital_address="some_other_address"
        )

        mock_get_balance_sum.assert_called_once_with(
            mock_vault,
            ["some_other_address"],
            denomination="GBP",
            # balance at midnight minus 1 micro second of the effective date
            timestamp=datetime(2019, 9, 1, 23, 59, 59, 999999),
        )

    @patch("library.features.shariah.profit_accrual._get_accrual_capital")
    def test_get_accrual_posting_instructions(self, mock_get_accrual_capital):
        mock_get_accrual_capital.return_value = Decimal("1000")

        mock_formula = Mock()
        mock_formula.calculate.return_value = Decimal("100")

        mock_vault = self.create_mock()

        results = get_accrual_posting_instructions(mock_vault, DEFAULT_DATE, "GBP", mock_formula)

        self.assertEqual(len(results), 2)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("100"),
                    denomination="GBP",
                    client_transaction_id="INTERNAL_POSTING_ACCRUE_PROFIT_MOCK_HOOK_INTERNAL",
                    from_account_id=PROFIT_PAID_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    instruction_details={
                        "description": "Daily profit accrued on balance of 1000",
                        "event": ACCRUAL_EVENT,
                        "account_type": "MURABAHAH",
                    },
                ),
                call(
                    amount=Decimal("100"),
                    denomination="GBP",
                    client_transaction_id="INTERNAL_POSTING_ACCRUE_PROFIT_MOCK_HOOK_CUSTOMER",
                    from_account_id=mock_vault.account_id,
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id=mock_vault.account_id,
                    to_account_address=ACCRUED_PROFIT_PAYABLE_ADDRESS,
                    asset=DEFAULT_ASSET,
                    instruction_details={
                        "description": "Daily profit accrued on balance of 1000",
                        "event": ACCRUAL_EVENT,
                        "account_type": "MURABAHAH",
                    },
                ),
            ]
        )

    @patch("library.features.shariah.profit_accrual._get_accrual_capital")
    def test_get_accrual_posting_instructions_0_accrual(self, mock_get_accrual_capital):
        mock_get_accrual_capital.return_value = Decimal("0")

        mock_formula = Mock()
        mock_formula.calculate.return_value = Decimal("0")
        mock_vault = self.create_mock()

        results = get_accrual_posting_instructions(mock_vault, DEFAULT_DATE, "GBP", mock_formula)

        self.assertEqual(len(results), 0)
        mock_vault.make_internal_transfer_instructions.assert_not_called()


class TestProfitAccrualApplication(TestProfitAccrualBase):
    @patch("library.features.shariah.profit_accrual.get_residual_cleanup_posting_instructions")
    @patch("library.features.shariah.profit_accrual.utils.round_decimal")
    @patch("library.features.shariah.profit_accrual.utils.get_balance_sum")
    def test_get_apply_accrual_posting_instructions(
        self,
        mock_get_balance_sum,
        mock_round_decimal,
        mock_get_residual_cleanup_posting_instructions,
    ):
        mock_get_balance_sum.return_value = Decimal("1.23456")
        mock_round_decimal.return_value = Decimal("1.23")
        mock_get_residual_cleanup_posting_instructions.return_value = [
            "reversal_pi1",
            "reversal_pi2",
        ]

        mock_vault = self.create_mock()

        results = get_apply_accrual_posting_instructions(mock_vault, DEFAULT_DATE, "GBP")

        mock_round_decimal.assert_called_once_with(
            Decimal("1.23456"), decimal_places=2, rounding=ROUND_DOWN
        )

        self.assertEqual(len(results), 4)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("1.23"),
                    denomination="GBP",
                    from_account_id=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=mock_vault.account_id,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="INTERNAL_POSTING_APPLY_ACCRUED_PROFIT_"
                    "MOCK_HOOK_GBP_INTERNAL",
                    instruction_details={
                        "description": "Profit Applied",
                        "event": ACCRUAL_APPLICATION_EVENT,
                        "account_type": "MURABAHAH",
                    },
                ),
                call(
                    amount=Decimal("1.23"),
                    denomination="GBP",
                    from_account_id=mock_vault.account_id,
                    from_account_address=ACCRUED_PROFIT_PAYABLE_ADDRESS,
                    to_account_id=mock_vault.account_id,
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="INTERNAL_POSTING_APPLY_ACCRUED_PROFIT_"
                    "MOCK_HOOK_GBP_CUSTOMER",
                    instruction_details={
                        "description": "Profit Applied",
                        "event": ACCRUAL_APPLICATION_EVENT,
                        "account_type": "MURABAHAH",
                    },
                ),
            ]
        )

        instruction_details = {
            "description": "Reversing accrued profit after application",
            "event": ACCRUAL_APPLICATION_EVENT,
            "account_type": "MURABAHAH",
        }

        mock_get_residual_cleanup_posting_instructions.assert_called_once_with(
            mock_vault, "GBP", instruction_details, remainder=Decimal("0.00456")
        )

    @patch("library.features.shariah.profit_accrual.get_residual_cleanup_posting_instructions")
    @patch("library.features.shariah.profit_accrual.utils.round_decimal")
    @patch("library.features.shariah.profit_accrual.utils.get_balance_sum")
    def test_get_apply_accrual_posting_instructions_nothing_to_apply(
        self,
        mock_get_balance_sum,
        mock_round_decimal,
        mock_get_residual_cleanup_posting_instructions,
    ):
        mock_get_balance_sum.return_value = Decimal("0.00001")
        mock_round_decimal.return_value = Decimal("0")
        mock_get_residual_cleanup_posting_instructions.return_value = [
            "reversal_pi1",
            "reversal_pi2",
        ]

        mock_vault = self.create_mock()

        results = get_apply_accrual_posting_instructions(mock_vault, DEFAULT_DATE, "GBP")

        mock_round_decimal.assert_called_once_with(
            Decimal("0.00001"), decimal_places=2, rounding=ROUND_DOWN
        )

        # current logic reverses everything after an application
        # even if application is rounded to 0, the remainder is still flattened out
        self.assertEqual(len(results), 2)
        mock_vault.make_internal_transfer_instructions.assert_not_called()

        instruction_details = {
            "description": "Reversing accrued profit after application",
            "event": ACCRUAL_APPLICATION_EVENT,
            "account_type": "MURABAHAH",
        }

        mock_get_residual_cleanup_posting_instructions.assert_called_once_with(
            mock_vault, "GBP", instruction_details, remainder=Decimal("0.00001")
        )


class TestProfitAccrualResidualCleanup(TestProfitAccrualBase):
    @patch("library.features.shariah.profit_accrual.utils.get_balance_sum")
    def test_get_residual_cleanup_posting_instructions_with_remainder_specified(
        self,
        mock_get_balance_sum,
    ):
        specified_remainder = Decimal("0.00456")
        mock_get_balance_sum.return_value = specified_remainder

        mock_vault = self.create_mock()

        instruction_details = {"some": "details"}

        results = get_residual_cleanup_posting_instructions(
            mock_vault, "GBP", instruction_details, specified_remainder
        )

        mock_get_balance_sum.assert_not_called()

        self.assertEqual(len(results), 2)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.00456"),
                    denomination="GBP",
                    from_account_id=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=PROFIT_PAID_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="INTERNAL_POSTING_REVERSE_RESIDUAL_PROFIT_"
                    "MOCK_HOOK_GBP_INTERNAL",
                    instruction_details=instruction_details,
                ),
                call(
                    amount=Decimal("0.00456"),
                    denomination="GBP",
                    from_account_id=mock_vault.account_id,
                    from_account_address=ACCRUED_PROFIT_PAYABLE_ADDRESS,
                    to_account_id=mock_vault.account_id,
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="INTERNAL_POSTING_REVERSE_RESIDUAL_PROFIT_"
                    "MOCK_HOOK_GBP_CUSTOMER",
                    instruction_details=instruction_details,
                ),
            ]
        )

    @patch("library.features.shariah.profit_accrual.utils.get_balance_sum")
    def test_get_residual_cleanup_posting_instructions_negative_remainder_specified(
        self,
        mock_get_balance_sum,
    ):
        specified_remainder = Decimal("-0.00456")
        mock_get_balance_sum.return_value = specified_remainder

        mock_vault = self.create_mock()

        instruction_details = {"some": "details"}

        results = get_residual_cleanup_posting_instructions(
            mock_vault, "GBP", instruction_details, specified_remainder
        )

        mock_get_balance_sum.assert_not_called()

        self.assertEqual(len(results), 2)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.00456"),
                    denomination="GBP",
                    from_account_id=PROFIT_PAID_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="INTERNAL_POSTING_REVERSE_RESIDUAL_PROFIT_"
                    "MOCK_HOOK_GBP_INTERNAL",
                    instruction_details=instruction_details,
                ),
                call(
                    amount=Decimal("0.00456"),
                    denomination="GBP",
                    from_account_id=mock_vault.account_id,
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id=mock_vault.account_id,
                    to_account_address=ACCRUED_PROFIT_PAYABLE_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="INTERNAL_POSTING_REVERSE_RESIDUAL_PROFIT_"
                    "MOCK_HOOK_GBP_CUSTOMER",
                    instruction_details=instruction_details,
                ),
            ]
        )

    @patch("library.features.shariah.profit_accrual.utils.get_balance_sum")
    def test_get_residual_cleanup_posting_instructions_remainder_unspecified(
        self,
        mock_get_balance_sum,
    ):
        remainder = Decimal("-0.00456")
        mock_get_balance_sum.return_value = remainder

        mock_vault = self.create_mock(
            balance_ts=self.init_balances(
                [{"address": ACCRUED_PROFIT_PAYABLE_ADDRESS, "net": remainder}]
            )
        )

        instruction_details = {"some": "details"}

        results = get_residual_cleanup_posting_instructions(mock_vault, "GBP", instruction_details)

        mock_get_balance_sum.assert_called_once_with(mock_vault, [ACCRUED_PROFIT_PAYABLE_ADDRESS])

        self.assertEqual(len(results), 2)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.00456"),
                    denomination="GBP",
                    from_account_id=PROFIT_PAID_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="INTERNAL_POSTING_REVERSE_RESIDUAL_PROFIT_"
                    "MOCK_HOOK_GBP_INTERNAL",
                    instruction_details=instruction_details,
                ),
                call(
                    amount=Decimal("0.00456"),
                    denomination="GBP",
                    from_account_id=mock_vault.account_id,
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id=mock_vault.account_id,
                    to_account_address=ACCRUED_PROFIT_PAYABLE_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="INTERNAL_POSTING_REVERSE_RESIDUAL_PROFIT_"
                    "MOCK_HOOK_GBP_CUSTOMER",
                    instruction_details=instruction_details,
                ),
            ]
        )

    @patch("library.features.shariah.profit_accrual.utils.get_balance_sum")
    def test_get_residual_cleanup_posting_instructions_0_remainder(
        self,
        mock_get_balance_sum,
    ):
        remainder = Decimal("0")
        mock_get_balance_sum.return_value = remainder

        mock_vault = self.create_mock(
            balance_ts=self.init_balances(
                [{"address": ACCRUED_PROFIT_PAYABLE_ADDRESS, "net": remainder}]
            )
        )

        instruction_details = {"some": "details"}

        results = get_residual_cleanup_posting_instructions(mock_vault, "GBP", instruction_details)

        mock_get_balance_sum.assert_called_once_with(mock_vault, [ACCRUED_PROFIT_PAYABLE_ADDRESS])

        self.assertEqual(len(results), 0)
        mock_vault.make_internal_transfer_instructions.assert_not_called()
