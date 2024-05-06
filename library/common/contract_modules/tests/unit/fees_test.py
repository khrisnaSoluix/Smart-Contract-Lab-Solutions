# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard
from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import call

# common
from inception_sdk.test_framework.contracts.unit.common import (
    ContractModuleTest,
    TimeSeries,
    balance_dimensions,
)
from inception_sdk.vault.contracts.types_extension import Balance, Phase, Tside

# misc
CONTRACT_MODULE_FILE = "library/common/contract_modules/fees.py"
DEFAULT_DATE = datetime(2021, 1, 1)
DEFAULT_DENOMINATION = "GBP"
DEFAULT_ADDRESS = "DEFAULT"
OVERPAYMENT_ADDRESS = "OVERPAYMENT"
DEFAULT_ASSET = "COMMERCIAL_BANK_MONEY"

MINIMUM_BALANCE_FEE_INCOME_ACCOUNT = "MINIMUM_BALANCE_FEE_INCOME"
INACTIVITY_FEE_INCOME_ACCOUNT = "INACTIVITY_FEE_INCOME_ACCOUNT"
MAINTENANCE_FEE_INCOME_ACCOUNT = "MAINTENANCE_FEE_INCOME_ACCOUNT"
ACCRUED_OVERDRAFT = "ACCRUED_OVERDRAFT"
HOOK_EXECUTION_ID = "MOCK_HOOK"


def balances_for_account(
    dt=DEFAULT_DATE, default_balance=Decimal("0"), overpayment_balance=Decimal("0")
):

    balance_dict = defaultdict(lambda: Balance(net=Decimal("0")))
    balance_dict[
        balance_dimensions(
            address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            denomination=DEFAULT_DENOMINATION,
            phase=Phase.COMMITTED,
        )
    ] = Balance(net=default_balance)
    balance_dict[
        balance_dimensions(
            address=OVERPAYMENT_ADDRESS,
            asset=DEFAULT_ASSET,
            denomination=DEFAULT_DENOMINATION,
            phase=Phase.COMMITTED,
        )
    ] = Balance(net=overpayment_balance)

    return [(dt, balance_dict)]


class FeesModuleTest(ContractModuleTest):
    contract_module_file = CONTRACT_MODULE_FILE
    side = Tside.LIABILITY

    def create_mock(
        self,
        balance_ts=None,
        postings=None,
        creation_date=DEFAULT_DATE,
        client_transaction=None,
        flags=None,
        **kwargs,
    ):
        balance_ts = balance_ts or []
        postings = postings or []
        client_transaction = client_transaction or {}
        flags = flags or []

        params = {
            key: {"value": value}
            for key, value in locals().items()
            if key not in self.locals_to_ignore
        }
        parameter_ts = self.param_map_to_timeseries(params, creation_date)
        return super().create_mock(
            balance_ts=balance_ts,
            parameter_ts=parameter_ts,
            postings=postings,
            creation_date=creation_date,
            client_transaction=client_transaction,
            flags=flags,
            **kwargs,
        )

    def test_construct_account_inactivity_fee_details(self):
        mock_vault = self.create_mock()
        result = self.run_function(
            "construct_account_inactivity_fee_details",
            mock_vault,
            amount=Decimal("10"),
            denomination="USD",
            internal_account=INACTIVITY_FEE_INCOME_ACCOUNT,
        )

        self.assertEqual(result.fee_type, "account_inactivity_fee")
        self.assertEqual(result.amount, Decimal("10"))
        self.assertEqual(result.denomination, "USD")
        self.assertEqual(result.internal_account, INACTIVITY_FEE_INCOME_ACCOUNT)
        self.assertEqual(result.is_account_dormant, False)
        self.assertEqual(len(result.__annotations__.keys()), 5)

    def test_construct_minimum_balance_fee_details(self):
        mock_vault = self.create_mock()
        result = self.run_function(
            "construct_minimum_balance_fee_details",
            mock_vault,
            amount=Decimal("10"),
            denomination="USD",
            internal_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            is_account_dormant=True,
        )

        self.assertEqual(result.fee_type, "minimum_balance_fee")
        self.assertEqual(result.amount, Decimal("10"))
        self.assertEqual(result.denomination, "USD")
        self.assertEqual(result.internal_account, MINIMUM_BALANCE_FEE_INCOME_ACCOUNT)
        self.assertEqual(result.is_account_dormant, True)
        self.assertEqual(result.account_creation_date, None)
        self.assertEqual(result.addresses, [DEFAULT_ADDRESS])
        self.assertEqual(result.minimum_balance_threshold, Decimal("0"))
        self.assertEqual(len(result.__annotations__.keys()), 8)

    def test_construct_maintenance_fee_details_monthly(self):
        mock_vault = self.create_mock()
        result = self.run_function(
            "construct_maintenance_fee_details",
            mock_vault,
            fee_frequency="monthly",
            amount=Decimal("10"),
            denomination="USD",
            internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
        )

        self.assertEqual(result.fee_type, "monthly_maintenance_fee")
        self.assertEqual(result.amount, Decimal("10"))
        self.assertEqual(result.denomination, "USD")
        self.assertEqual(result.internal_account, MAINTENANCE_FEE_INCOME_ACCOUNT)
        self.assertEqual(result.is_account_dormant, False)
        self.assertEqual(result.account_creation_date, None)
        self.assertEqual(result.addresses, [DEFAULT_ADDRESS])
        self.assertEqual(result.minimum_balance_threshold, Decimal("0"))
        self.assertEqual(result.minimum_deposit, Decimal("0"))
        self.assertEqual(result.waive_fee_if_mean_balance_above_threshold, False)
        self.assertEqual(result.waive_fee_based_on_monthly_deposits, False)
        self.assertEqual(result.included_transaction_types, [])
        self.assertEqual(result.excluded_transaction_types, [])
        self.assertEqual(result.client_transactions, {})
        self.assertEqual(len(result.__annotations__.keys()), 14)

    def test_construct_maintenance_fee_details_annual(self):
        mock_vault = self.create_mock()
        result = self.run_function(
            "construct_maintenance_fee_details",
            mock_vault,
            fee_frequency="annual",
            amount=Decimal("10"),
            denomination="USD",
            internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
            addresses=["PRINCIPAL", "INTEREST"],
        )

        self.assertEqual(result.fee_type, "annual_maintenance_fee")
        self.assertEqual(result.amount, Decimal("10"))
        self.assertEqual(result.denomination, "USD")
        self.assertEqual(result.internal_account, MAINTENANCE_FEE_INCOME_ACCOUNT)
        self.assertEqual(result.is_account_dormant, False)
        self.assertEqual(result.account_creation_date, None)
        self.assertEqual(result.addresses, ["PRINCIPAL", "INTEREST"])
        self.assertEqual(result.minimum_balance_threshold, Decimal("0"))
        self.assertEqual(result.minimum_deposit, Decimal("0"))
        self.assertEqual(result.waive_fee_if_mean_balance_above_threshold, False)
        self.assertEqual(result.waive_fee_based_on_monthly_deposits, False)
        self.assertEqual(result.included_transaction_types, [])
        self.assertEqual(result.excluded_transaction_types, [])
        self.assertEqual(result.client_transactions, {})
        self.assertEqual(len(result.__annotations__.keys()), 14)

    def test_min_balance_fee_not_applied_if_mean_balance_above_threshold(self):
        effective_time = datetime(2020, 2, 1)
        period_start = effective_time - relativedelta(months=1)
        fee_amount = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_minimum_balance_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=period_start,
            minimum_balance_threshold=Decimal("90"),
        )

        balance_ts = TimeSeries(
            balances_for_account(dt=period_start, default_balance=Decimal("100"))
        )

        self.run_function(
            function_name="apply_minimum_balance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
            minimum_balance_fee_details=fee_details,
            balances=balance_ts,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_min_balance_fee_not_applied_if_mean_balance_equals_threshold(self):
        effective_time = datetime(2020, 2, 1)
        period_start = effective_time - relativedelta(months=1)
        fee_amount = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_minimum_balance_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=period_start,
            minimum_balance_threshold=Decimal("90"),
        )

        balance_ts = TimeSeries(
            balances_for_account(dt=period_start, default_balance=Decimal("100"))
        )

        self.run_function(
            function_name="apply_minimum_balance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
            minimum_balance_fee_details=fee_details,
            balances=balance_ts,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_min_balance_fee_not_applied_if_mean_balance_multiple_addresses_above_threshold(
        self,
    ):
        effective_time = datetime(2020, 2, 1)
        period_start = effective_time - relativedelta(months=1)
        fee_amount = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_minimum_balance_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=period_start,
            addresses=[DEFAULT_ADDRESS, OVERPAYMENT_ADDRESS],
            minimum_balance_threshold=Decimal("90"),
        )

        balance_ts = TimeSeries(
            balances_for_account(
                dt=period_start,
                default_balance=Decimal("50"),
                overpayment_balance=Decimal("51"),
            )
        )

        self.run_function(
            function_name="apply_minimum_balance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
            minimum_balance_fee_details=fee_details,
            balances=balance_ts,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_min_balance_fee_applied_if_mean_balance_under_threshold(self):
        effective_time = datetime(2020, 2, 1)
        period_start = effective_time - relativedelta(months=1)
        fee_amount = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_minimum_balance_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=period_start,
            minimum_balance_threshold=Decimal("90"),
        )

        balance_ts = TimeSeries(
            balances_for_account(dt=period_start, default_balance=Decimal("80"))
        )

        self.run_function(
            function_name="apply_minimum_balance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
            minimum_balance_fee_details=fee_details,
            balances=balance_ts,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MINIMUM_BALANCE_FEE_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MINIMUM_BALANCE_FEE",
            },
        )

    def test_min_balance_fee_applied_if_mean_balance_is_zero(self):
        effective_time = datetime(2020, 2, 1)
        period_start = effective_time - relativedelta(months=1)
        fee_amount = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_minimum_balance_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=period_start,
            minimum_balance_threshold=Decimal("90"),
        )

        balance_ts = TimeSeries(balances_for_account(dt=period_start, default_balance=Decimal("0")))

        self.run_function(
            function_name="apply_minimum_balance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
            minimum_balance_fee_details=fee_details,
            balances=balance_ts,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MINIMUM_BALANCE_FEE_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MINIMUM_BALANCE_FEE",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MINIMUM_BALANCE_FEE_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MINIMUM_BALANCE_FEE",
            },
        )

    def test_min_balance_fee_not_applied_if_dormant(self):
        effective_time = datetime(2020, 2, 1)
        period_start = effective_time - relativedelta(months=1)
        fee_amount = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_minimum_balance_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            is_account_dormant=True,
            account_creation_date=period_start,
            addresses=[DEFAULT_ADDRESS, OVERPAYMENT_ADDRESS],
            minimum_balance_threshold=Decimal("90"),
        )

        balance_ts = TimeSeries(
            balances_for_account(dt=period_start, default_balance=Decimal("100"))
        )

        self.run_function(
            function_name="apply_minimum_balance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
            minimum_balance_fee_details=fee_details,
            balances=balance_ts,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_account_mean_balance_fee_period_with_fee_charged(self):
        fee_hour = 23
        fee_minute = 0
        fee_second = 0
        anniversary = datetime(2020, 2, 1)
        effective_time = anniversary.replace(hour=fee_hour, minute=fee_minute, second=fee_second)
        expected_period_start = datetime(2020, 1, 1)
        expected_period_end = datetime(2020, 1, 31, fee_hour, fee_minute, fee_second)

        fee_amount = Decimal("100")
        minimum_balance_threshold = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_minimum_balance_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=expected_period_start,
            minimum_balance_threshold=minimum_balance_threshold,
        )

        balance_time = expected_period_start - relativedelta(days=2)
        balance_ts = []
        # The mean balance is sampled daily for a month at the fee application time. Set up balances
        # which are:
        # - just below the balance threshold during the current sampling month
        # - well above the balance threshold for two days before and after the sampling month
        # such that if the sampling month included the outlying balances the test would fail by
        # the mean being above the threshold and not charging the fee.
        while balance_time < expected_period_end + relativedelta(days=2):
            if expected_period_start <= balance_time <= expected_period_end:
                balance = balances_for_account(
                    dt=balance_time,
                    default_balance=minimum_balance_threshold - 1,
                )
            else:
                balance = balances_for_account(
                    dt=balance_time,
                    default_balance=60 * minimum_balance_threshold,
                )
            balance_ts.extend(balance)
            balance_time += relativedelta(minutes=15)

        self.run_function(
            function_name="apply_minimum_balance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            minimum_balance_fee_details=fee_details,
            balances=TimeSeries(balance_ts),
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MINIMUM_BALANCE_FEE_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MINIMUM_BALANCE_FEE",
            },
        )

    def test_account_mean_balance_fee_period_with_fee_not_charged(self):
        fee_hour = 23
        fee_minute = 0
        fee_second = 0
        anniversary = datetime(2020, 2, 1)
        effective_time = anniversary.replace(hour=fee_hour, minute=fee_minute, second=fee_second)
        expected_period_start = datetime(2020, 1, 1)
        expected_period_end = datetime(2020, 1, 31, fee_hour, fee_minute, fee_second)

        fee_amount = Decimal("100")
        minimum_balance_threshold = Decimal("100")
        fee_amount = Decimal("100")
        minimum_balance_threshold = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_minimum_balance_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=expected_period_start,
            minimum_balance_threshold=minimum_balance_threshold,
        )

        balance_time = expected_period_start - relativedelta(days=2)
        balance_ts = []
        # The mean balance is sampled daily for a month at the fee application time. Set up balances
        # which are:
        # - equal to the balance threshold during the current sampling month
        # - well above the balance threshold for two days before and after the sampling month
        # such that if the sampling month included the outlying balances the test would fail by
        # the mean being above the threshold and not charging the fee.
        while balance_time < expected_period_end + relativedelta(days=2):
            if expected_period_start <= balance_time <= expected_period_end:
                balance = balances_for_account(
                    dt=balance_time, default_balance=minimum_balance_threshold
                )
            else:
                balance = balances_for_account(dt=balance_time, default_balance=Decimal("-100000"))
            balance_ts.extend(balance)
            balance_time += relativedelta(hours=6)

        self.run_function(
            function_name="apply_minimum_balance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            minimum_balance_fee_details=fee_details,
            balances=TimeSeries(balance_ts),
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_min_balance_fee_charged_with_mid_month_period_and_sampling_midnight(
        self,
    ):
        fee_hour = 0
        fee_minute = 0
        fee_second = 0
        anniversary = datetime(2019, 3, 15)
        effective_time = anniversary.replace(hour=fee_hour, minute=fee_minute, second=fee_second)
        expected_period_start = datetime(2019, 2, 15)
        expected_period_end = datetime(2019, 3, 14, fee_hour, fee_minute, fee_second)

        fee_amount = Decimal("100")
        minimum_balance_threshold = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_minimum_balance_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=expected_period_start,
            minimum_balance_threshold=Decimal("100"),
        )

        balance_time = expected_period_start - relativedelta(days=2)
        balance_ts = []
        # The mean balance is sampled daily for a month at the fee application time. Set up balances
        # which are:
        # - just below the balance threshold during the current sampling month
        # - well above the balance threshold for two days before and after the sampling month
        # such that if the sampling month included the outlying balances the test would fail by
        # the mean being above the threshold and not charging the fee.
        while balance_time < expected_period_end + relativedelta(days=2):
            if expected_period_start <= balance_time <= expected_period_end:
                balance = balances_for_account(
                    dt=balance_time,
                    default_balance=minimum_balance_threshold - 1,
                )
            else:
                balance = balances_for_account(
                    dt=balance_time,
                    default_balance=60 * minimum_balance_threshold,
                )
            balance_ts.extend(balance)
            balance_time += relativedelta(minutes=15)

        self.run_function(
            function_name="apply_minimum_balance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            minimum_balance_fee_details=fee_details,
            balances=TimeSeries(balance_ts),
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MINIMUM_BALANCE_FEE_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MINIMUM_BALANCE_FEE",
            },
        )

    def test_min_balance_fee_sampling_in_leap_year_february(self):
        fee_hour = 0
        fee_minute = 0
        fee_second = 0
        anniversary = datetime(2020, 3, 15)
        effective_time = anniversary.replace(hour=fee_hour, minute=fee_minute, second=fee_second)
        expected_period_start = datetime(2020, 2, 15)
        expected_period_end = datetime(2020, 3, 14, fee_hour, fee_minute, fee_second)

        fee_amount = Decimal("100")
        minimum_balance_threshold = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_minimum_balance_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=expected_period_start,
            minimum_balance_threshold=Decimal("100"),
        )

        balance_time = expected_period_start - relativedelta(days=2)
        balance_ts = []
        # The mean balance is sampled daily for a month at the fee application time. Set up balances
        # which are:
        # - just below the balance threshold during the current sampling month
        # - well above the balance threshold for two days before and after the sampling month
        # such that if the sampling month included the outlying balances the test would fail by
        # the mean being above the threshold and not charging the fee.
        while balance_time < expected_period_end + relativedelta(days=2):
            if expected_period_start <= balance_time <= expected_period_end:
                balance = balances_for_account(
                    dt=balance_time,
                    default_balance=minimum_balance_threshold - 1,
                )
            else:
                balance = balances_for_account(
                    dt=balance_time,
                    default_balance=60 * minimum_balance_threshold,
                )
            balance_ts.extend(balance)
            balance_time += relativedelta(hours=12)

        self.run_function(
            function_name="apply_minimum_balance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            minimum_balance_fee_details=fee_details,
            balances=TimeSeries(balance_ts),
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MINIMUM_BALANCE_FEE_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MINIMUM_BALANCE_FEE",
            },
        )

    def test_active_account_does_not_charge_inactivity_fee(self):
        fee_amount = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_account_inactivity_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=INACTIVITY_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            function_name="apply_inactivity_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            fee_details=fee_details,
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_dormant_account_charges_inactivity_fee(self):
        fee_amount = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_account_inactivity_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=INACTIVITY_FEE_INCOME_ACCOUNT,
            is_account_dormant=True,
        )

        self.run_function(
            function_name="apply_inactivity_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            fee_details=fee_details,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=INACTIVITY_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_ACCOUNT_INACTIVITY_FEE_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Account inactivity fee",
                "event": "APPLY_ACCOUNT_INACTIVITY_FEE",
            },
        )

    def test_monthly_maintenance_fee_applied(self):
        fee_amount = Decimal("100")
        effective_time = datetime(2020, 2, 1)

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_maintenance_fee_details",
            mock_vault,
            fee_frequency="monthly",
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            function_name="apply_maintenance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            maintenance_fee_details=fee_details,
            balances=balances_for_account(),
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MAINTENANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_MAINTENANCE_FEE_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_MAINTENANCE_FEE",
            },
        )

    def test_dormant_account_does_not_charge_monthly_maintenance_fee(self):
        effective_time = datetime(2020, 2, 1)
        fee_amount = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_maintenance_fee_details",
            mock_vault,
            fee_frequency="monthly",
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
            is_account_dormant=True,
        )

        self.run_function(
            function_name="apply_maintenance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            maintenance_fee_details=fee_details,
            balances=balances_for_account(),
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_annual_maintenance_fee_applied(self):
        fee_amount = Decimal("100")

        effective_time = datetime(2020, 2, 1)
        fee_amount = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_maintenance_fee_details",
            mock_vault,
            fee_frequency="annual",
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            function_name="apply_maintenance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            maintenance_fee_details=fee_details,
            balances=balances_for_account(),
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MAINTENANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_ANNUAL_MAINTENANCE_FEE_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Annual maintenance fee",
                "event": "APPLY_ANNUAL_MAINTENANCE_FEE",
            },
        )

    def test_dormant_account_does_not_charge_annual_maintenance_fee(self):
        effective_time = datetime(2020, 2, 1)
        fee_amount = Decimal("100")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_maintenance_fee_details",
            mock_vault,
            fee_frequency="annual",
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
            is_account_dormant=True,
        )

        self.run_function(
            function_name="apply_maintenance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            maintenance_fee_details=fee_details,
            balances=balances_for_account(),
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_maintenance_fee_applied_if_nr_of_transactions_waive_criteria_not_met(self):
        effective_time = datetime(2020, 2, 1)
        fee_amount = Decimal("100")

        period_start = effective_time - relativedelta(months=1)
        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "DEPOSIT_TRANSACTION_ID_1"
        client_transactions = {
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=[
                    self.inbound_hard_settlement(
                        amount=100,
                        client_id=client_id_1,
                        client_transaction_id=client_transaction_id_1,
                        value_timestamp=effective_time - relativedelta(days=10),
                    )
                ],
            )
        }

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_maintenance_fee_details",
            mock_vault,
            fee_frequency="monthly",
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=period_start,
            waive_fee_based_on_monthly_deposits=True,
            # The deposit does not have a matching client_transaction_id
            included_transaction_types=["ATM_TRANSACTION"],
            client_transactions=client_transactions,
        )

        self.run_function(
            function_name="apply_maintenance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            maintenance_fee_details=fee_details,
            balances=balances_for_account(),
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MAINTENANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_MAINTENANCE_FEE_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_MAINTENANCE_FEE",
            },
        )

    def test_maintenance_fee_not_applied_if_nr_of_transactions_waive_criteria_met(self):
        effective_time = datetime(2020, 2, 1)
        fee_amount = Decimal("100")

        period_start = effective_time - relativedelta(months=1)
        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "DEPOSIT_TRANSACTION_ID_1"
        client_transactions = {
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=[
                    self.inbound_hard_settlement(
                        amount=100,
                        client_id=client_id_1,
                        client_transaction_id=client_transaction_id_1,
                        value_timestamp=effective_time - relativedelta(days=10),
                    )
                ],
            )
        }

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_maintenance_fee_details",
            mock_vault,
            fee_frequency="monthly",
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=period_start,
            waive_fee_based_on_monthly_deposits=True,
            # The deposit has a matching client_transaction_id
            included_transaction_types=["DEPOSIT_TRANSACTION"],
            client_transactions=client_transactions,
        )

        self.run_function(
            function_name="apply_maintenance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            maintenance_fee_details=fee_details,
            balances=balances_for_account(),
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_maintenance_fee_applied_if_min_deposit_threshold_waive_criteria_not_met(
        self,
    ):
        effective_time = datetime(2020, 2, 1)
        fee_amount = Decimal("100")

        period_start = effective_time - relativedelta(months=1)
        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "DEPOSIT_TRANSACTION_ID_1"
        client_transactions = {
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=[
                    self.inbound_hard_settlement(
                        amount=100,
                        client_id=client_id_1,
                        client_transaction_id=client_transaction_id_1,
                        value_timestamp=effective_time - relativedelta(days=10),
                    )
                ],
            )
        }

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_maintenance_fee_details",
            mock_vault,
            fee_frequency="monthly",
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=period_start,
            minimum_deposit=Decimal("500"),
            waive_fee_based_on_monthly_deposits=True,
            excluded_transaction_types=["ATM_TRANSACTION"],
            client_transactions=client_transactions,
        )

        self.run_function(
            function_name="apply_maintenance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            maintenance_fee_details=fee_details,
            balances=balances_for_account(),
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MAINTENANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_MAINTENANCE_FEE_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_MAINTENANCE_FEE",
            },
        )

    def test_maintenance_fee_not_applied_if_min_deposit_threshold_waive_criteria_met(
        self,
    ):
        effective_time = datetime(2020, 2, 1)
        fee_amount = Decimal("100")

        period_start = effective_time - relativedelta(months=1)
        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "DEPOSIT_TRANSACTION_ID_1"
        client_transactions = {
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=[
                    self.inbound_hard_settlement(
                        amount=100,
                        client_id=client_id_1,
                        client_transaction_id=client_transaction_id_1,
                        value_timestamp=effective_time - relativedelta(days=10),
                    )
                ],
            )
        }

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_maintenance_fee_details",
            mock_vault,
            fee_frequency="monthly",
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=period_start,
            minimum_deposit=Decimal("50"),
            waive_fee_based_on_monthly_deposits=True,
            excluded_transaction_types=["ATM_TRANSACTION"],
            client_transactions=client_transactions,
        )

        self.run_function(
            function_name="apply_maintenance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            maintenance_fee_details=fee_details,
            balances=balances_for_account(),
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_maintenance_fee_is_skipped_if_mean_balance_above_threshold_set_true(self):
        effective_time = datetime(2020, 2, 1)
        fee_amount = Decimal("100")

        period_start = effective_time - relativedelta(months=1)
        balance_ts = TimeSeries(
            balances_for_account(dt=period_start, default_balance=Decimal("100"))
        )

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_maintenance_fee_details",
            mock_vault,
            fee_frequency="monthly",
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=period_start,
            minimum_balance_threshold=Decimal("90"),
            waive_fee_if_mean_balance_above_threshold=True,
        )

        self.run_function(
            function_name="apply_maintenance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            maintenance_fee_details=fee_details,
            balances=balance_ts,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_multiple_fees_applied(self):
        fee_amount = Decimal("100")
        effective_time = datetime(2020, 2, 1)
        period_start = effective_time - relativedelta(months=1)
        balance_ts = TimeSeries(balances_for_account(dt=period_start, default_balance=Decimal("0")))

        mock_vault = self.create_mock()

        fee_setup = [
            self.run_function(
                "construct_maintenance_fee_details",
                mock_vault,
                fee_frequency="monthly",
                amount=fee_amount,
                denomination=DEFAULT_DENOMINATION,
                internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
                minimum_balance_threshold=Decimal("90"),
                waive_fee_if_mean_balance_above_threshold=True,
            ),
            self.run_function(
                "construct_maintenance_fee_details",
                mock_vault,
                fee_frequency="annual",
                amount=fee_amount,
                denomination=DEFAULT_DENOMINATION,
                internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
                minimum_balance_threshold=Decimal("90"),
                waive_fee_if_mean_balance_above_threshold=True,
            ),
            self.run_function(
                "construct_minimum_balance_fee_details",
                mock_vault,
                amount=fee_amount,
                denomination=DEFAULT_DENOMINATION,
                internal_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
                minimum_balance_threshold=Decimal("90"),
            ),
        ]

        self.run_function(
            function_name="apply_multiple_fees",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            fees=fee_setup,
            balances=balance_ts,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=fee_amount,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=MAINTENANCE_FEE_INCOME_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_MAINTENANCE_FEE_"
                    f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Monthly maintenance fee",
                        "event": "APPLY_MONTHLY_MAINTENANCE_FEE",
                    },
                ),
                call(
                    amount=fee_amount,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=MAINTENANCE_FEE_INCOME_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"INTERNAL_POSTING_APPLY_ANNUAL_MAINTENANCE_FEE_"
                    f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Annual maintenance fee",
                        "event": "APPLY_ANNUAL_MAINTENANCE_FEE",
                    },
                ),
                call(
                    amount=fee_amount,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"INTERNAL_POSTING_APPLY_MINIMUM_BALANCE_FEE_"
                    f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Minimum balance fee",
                        "event": "APPLY_MINIMUM_BALANCE_FEE",
                    },
                ),
            ]
        )

    def test_minimum_balance_fee_not_applied_if_zero(self):
        fee_amount = Decimal("0")

        effective_time = datetime(2020, 2, 1)
        period_start = effective_time - relativedelta(months=1)

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_minimum_balance_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            account_creation_date=period_start,
            minimum_balance_threshold=Decimal("90"),
        )

        balance_ts = TimeSeries(
            balances_for_account(dt=period_start, default_balance=Decimal("10"))
        )

        self.run_function(
            function_name="apply_minimum_balance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
            minimum_balance_fee_details=fee_details,
            balances=balance_ts,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_maintenance_fee_not_applied_if_zero(self):

        effective_time = datetime(2020, 2, 1)
        fee_amount = Decimal("0")

        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_maintenance_fee_details",
            mock_vault,
            fee_frequency="monthly",
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            function_name="apply_maintenance_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
            maintenance_fee_details=fee_details,
            balances=balances_for_account(),
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_inactivity_fee_not_applied_if_zero(self):
        fee_amount = Decimal("0")
        mock_vault = self.create_mock()

        fee_details = self.run_function(
            "construct_account_inactivity_fee_details",
            mock_vault,
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            internal_account=INACTIVITY_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            function_name="apply_inactivity_fee",
            vault_object=mock_vault,
            vault=mock_vault,
            fee_details=fee_details,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
