# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timedelta
from decimal import Decimal
from json import dumps
from unittest.mock import call

# common
from inception_sdk.test_framework.contracts.unit.common import (
    ContractTest,
    balance_dimensions,
)
from inception_sdk.vault.contracts.types_extension import (
    Balance,
    BalanceDefaultDict,
    DEFAULT_ASSET,
    INTERNAL_CONTRA,
    Tside,
    UnionItemValue,
    OptionalValue,
)


DEFAULT_DENOMINATION = "MYR"
DEFAULT_DATE = datetime(2019, 1, 1)
ACCRUED_PROFIT_PAYABLE_ACCOUNT = "ACCRUED_PROFIT_PAYABLE"
PROFIT_PAID_ACCOUNT = "PROFIT_PAID"
EARLY_CLOSURE_FEE_INCOME_ACCOUNT = "EARLY_CLOSURE_FEE_INCOME"
PAYMENT_TYPE_FEE_INCOME_ACCOUNT = "PAYMENT_TYPE_FEE_INCOME"

INTERNAL_POSTING = "INTERNAL_POSTING"
EARLY_CLOSURE_FEE_ADDRESS = "EARLY_CLOSURE_FEE"

BALANCE_TIER_RANGES = dumps(
    {
        "tier1": {"min": "0"},
        "tier2": {"min": "5000.00"},
        "tier3": {"min": "15000.00"},
    }
)
TIERED_PROFIT_RATES = dumps(
    {
        "MURABAHAH_TIER_UPPER": {
            "tier1": "0.02",
            "tier2": "0.015",
            "tier3": "0.01",
        },
        "MURABAHAH_TIER_MIDDLE": {
            "tier1": "0.0125",
            "tier2": "0.01",
            "tier3": "0.0075",
        },
        "MURABAHAH_TIER_LOWER": {
            "tier1": "0",
            "tier2": "0.0075",
            "tier3": "0.005",
        },
    }
)
TIERED_MIN_BALANCE_THRESHOLD = dumps(
    {
        "MURABAHAH_TIER_UPPER": "25",
        "MURABAHAH_TIER_MIDDLE": "75",
        "MURABAHAH_TIER_LOWER": "100",
    }
)
ACCOUNT_TIER_NAMES = dumps(
    [
        "MURABAHAH_TIER_UPPER",
        "MURABAHAH_TIER_MIDDLE",
        "MURABAHAH_TIER_LOWER",
    ]
)
MAXIMUM_DAILY_PAYMENT_TYPE_WITHDRAWAL = dumps(
    {
        "DUITNOW_PROXY": "50000",
        "DUITNOWQR": "50000",
        "JOMPAY": "50000",
        "ONUS": "50000",
        "ATM_ARBM": "5000",
        "ATM_MEPS": "5000",
        "ATM_VISA": "5000",
        "ATM_IBFT": "30000",
        "DEBIT_POS": "100000",
    }
)
MAXIMUM_PAYMENT_TYPE_WITHDRAWAL = dumps(
    {
        "DEBIT_PAYWAVE": "250",
    }
)
MAXIMUM_DAILY_PAYMENT_CATEGORY_WITHDRAWAL = dumps(
    {
        "DUITNOW": "50000",
    }
)
PAYMENT_TYPE_FLAT_FEES = dumps(
    {
        "ATM_MEPS": "1",
        "ATM_IBFT": "5",
    }
)
PAYMENT_TYPE_THRESHOLD_FEES = dumps(
    {
        "DUITNOW_PROXY": {"fee": "0.50", "threshold": "5000"},
        "ATM_IBFT": {"fee": "0.15", "threshold": "5000"},
    }
)
MAX_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT = dumps(
    {
        "ATM_ARBM": {"fee": "0.50", "limit": "8"},
    }
)


class MurabahahTest(ContractTest):
    contract_file = "library/murabahah/contracts/template/murabahah.py"
    side = Tside.LIABILITY

    def create_mock(
        self,
        balance_ts=None,
        postings=None,
        creation_date=DEFAULT_DATE,
        client_transaction=None,
        flags=None,
        balance_tier_ranges=BALANCE_TIER_RANGES,
        tiered_profit_rates=TIERED_PROFIT_RATES,
        days_in_year=UnionItemValue("actual"),
        profit_accrual_hour=0,
        profit_accrual_minute=0,
        profit_accrual_second=0,
        profit_application_hour=0,
        profit_application_minute=0,
        profit_application_second=0,
        profit_application_frequency=UnionItemValue("monthly"),
        schedule_start_date=OptionalValue(value=None, is_set=False),
        tiered_minimum_balance_threshold=TIERED_MIN_BALANCE_THRESHOLD,
        account_tier_names=ACCOUNT_TIER_NAMES,
        accrued_profit_payable_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
        profit_paid_account=PROFIT_PAID_ACCOUNT,
        early_closure_fee_income_account=EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
        maximum_daily_payment_category_withdrawal=MAXIMUM_DAILY_PAYMENT_CATEGORY_WITHDRAWAL,
        maximum_daily_payment_type_withdrawal=MAXIMUM_DAILY_PAYMENT_TYPE_WITHDRAWAL,
        **kwargs,
    ):
        if not balance_ts:
            balance_ts = []

        if not postings:
            postings = []

        if not client_transaction:
            client_transaction = {}

        if not flags:
            flags = []

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

    def account_balances(
        self,
        dt=DEFAULT_DATE,
        accrued_payable=Decimal(0),
        default_committed=Decimal(0),
        early_closure_fee=Decimal(0),
        internal_contra=Decimal(0),
    ):

        balance_dict = {
            balance_dimensions(denomination=DEFAULT_DENOMINATION): Balance(net=default_committed),
            balance_dimensions(
                denomination=DEFAULT_DENOMINATION, address=ACCRUED_PROFIT_PAYABLE_ACCOUNT
            ): Balance(net=accrued_payable),
            balance_dimensions(
                denomination=DEFAULT_DENOMINATION, address=EARLY_CLOSURE_FEE_ADDRESS
            ): Balance(net=early_closure_fee),
            balance_dimensions(denomination=DEFAULT_DENOMINATION, address=INTERNAL_CONTRA): Balance(
                net=internal_contra
            ),
        }

        balance_default_dict = BalanceDefaultDict(lambda: Balance(net=Decimal("0")), balance_dict)

        return [(dt, balance_default_dict)]

    def test_execution_schedules_creation(self):
        mock_vault = self.create_mock(
            profit_application_day=28,
            creation_date=datetime(2019, 1, 2, 5, 6, 7),
            profit_accrual_hour=1,
            profit_accrual_minute=2,
            profit_accrual_second=3,
            profit_application_hour=23,
            profit_application_minute=22,
            profit_application_second=21,
        )

        expected_accrue_schedule = (
            "ACCRUE_PROFIT",
            {"hour": "1", "minute": "2", "second": "3"},
        )
        expected_apply_accrued_schedule = (
            "APPLY_ACCRUED_PROFIT",
            {
                "year": "2019",
                "month": "1",
                "day": "28",
                "hour": "23",
                "minute": "22",
                "second": "21",
            },
        )

        execution_schedules = self.run_function("execution_schedules", mock_vault)

        self.assertIn(expected_accrue_schedule, execution_schedules)
        self.assertIn(expected_apply_accrued_schedule, execution_schedules)

    def test_execution_schedules_creation_with_invalid_day_defaults_to_last_day_of_month(
        self,
    ):
        mock_vault = self.create_mock(
            profit_application_day=31, creation_date=datetime(2019, 2, 2, 5, 6, 7)
        )

        expected_accrue_schedule = (
            "ACCRUE_PROFIT",
            {"hour": "0", "minute": "0", "second": "0"},
        )
        expected_apply_accrued_schedule = (
            "APPLY_ACCRUED_PROFIT",
            {
                "year": "2019",
                "month": "2",
                "day": "28",
                "hour": "0",
                "minute": "0",
                "second": "0",
            },
        )

        execution_schedules = self.run_function("execution_schedules", mock_vault)

        self.assertIn(expected_accrue_schedule, execution_schedules)
        self.assertIn(expected_apply_accrued_schedule, execution_schedules)

    def test_execution_schedules_update_to_last_valid_day_of_month(self):
        accrued_payable = Decimal(0)
        default_committed = Decimal(2000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            accrued_payable=accrued_payable,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            profit_application_day=28,
            denomination="MYR",
            creation_date=DEFAULT_DATE,
            APPLY_ACCRUED_PROFIT=datetime(2020, 2, 1),
        )

        effective_date = datetime(2020, 2, 1, 1)
        mock_vault.localize_datetime.return_value = effective_date

        expected_schedule = {
            "year": "2020",
            "month": "2",
            "day": "28",
            "hour": "0",
            "minute": "0",
            "second": "0",
        }

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters={"profit_application_day": "31"},
            new_parameters={"profit_application_day": "28"},
            effective_date=effective_date,
        )

        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_PROFIT", new_schedule=expected_schedule
        )

    def test_scheduled_code_accrue_profit_with_payable_tiered_profit(self):
        tiered_profit_rates = dumps(
            {
                "MURABAHAH_TIER_LOWER": {
                    "tier1": "0",
                    "tier2": "0.1485",
                    "tier3": "0.15",
                }
            }
        )

        input_data = [
            "0.04068",
            "4.06849",
            INTERNAL_CONTRA,
            "ACCRUED_PROFIT_PAYABLE",
            PROFIT_PAID_ACCOUNT,
            ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            "LOWER",
        ]
        profit_rate = input_data[0]
        accrued_profit = input_data[1]
        cust_from_address = input_data[2]
        cust_to_address = input_data[3]
        from_account_id = input_data[4]
        to_account_id = input_data[5]
        account_tier = input_data[6]

        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("15000")
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="MYR",
            accrued_profit_payable_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            profit_paid_account=PROFIT_PAID_ACCOUNT,
            account_tier=account_tier,
            tiered_profit_rates=tiered_profit_rates,
            balance_tier_ranges=BALANCE_TIER_RANGES,
            daily_rate=(Decimal(profit_rate) / 365),
            amount_to_accrue=accrued_profit,
        )
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_PROFIT",
            effective_date=DEFAULT_DATE,
        )
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("4.06849"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="INTERNAL_POSTING_ACCRUE_PROFIT_MOCK_HOOK_INTERNAL",
                    from_account_id=from_account_id,
                    from_account_address="DEFAULT",
                    to_account_id=to_account_id,
                    to_account_address="DEFAULT",
                    instruction_details={
                        "description": "Daily profit accrued on balance of 15000",
                        "event": "ACCRUE_PROFIT",
                        "account_type": "MURABAHAH",
                    },
                    asset=DEFAULT_ASSET,
                ),
                call(
                    amount=Decimal("4.06849"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="INTERNAL_POSTING_ACCRUE_PROFIT_MOCK_HOOK_CUSTOMER",
                    from_account_id="Main account",
                    from_account_address=cust_from_address,
                    to_account_id="Main account",
                    to_account_address=cust_to_address,
                    instruction_details={
                        "description": "Daily profit accrued on balance of 15000",
                        "event": "ACCRUE_PROFIT",
                        "account_type": "MURABAHAH",
                    },
                    asset=DEFAULT_ASSET,
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=[
                "INTERNAL_POSTING_ACCRUE_PROFIT_MOCK_HOOK_INTERNAL",
                "INTERNAL_POSTING_ACCRUE_PROFIT_MOCK_HOOK_CUSTOMER",
            ],
            client_batch_id="ACCRUE_PROFIT_MOCK_HOOK",
            effective_date=DEFAULT_DATE,
            batch_details={"event": "ACCRUE_PROFIT"},
        )

    def test_scheduled_code_accrue_profit_with_payable_small_profit(self):
        """
        Test for a real use case within the bank.
        """
        tiered_profit_rates = dumps(
            {
                "MURABAHAH_TIER_LOWER": {
                    "tier1": "0.0075",
                    "tier2": "0.01",
                    "tier3": "0.015",
                }
            }
        )

        input_data = [
            "0.00205",
            INTERNAL_CONTRA,
            "ACCRUED_PROFIT_PAYABLE",
            PROFIT_PAID_ACCOUNT,
            ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            "LOWER",
        ]
        profit_rate = input_data[0]
        cust_from_address = input_data[1]
        cust_to_address = input_data[2]
        from_account_id = input_data[3]
        to_account_id = input_data[4]
        account_tier = input_data[5]

        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("70")
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="MYR",
            accrued_profit_payable_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            profit_paid_account=PROFIT_PAID_ACCOUNT,
            account_tier=account_tier,
            tiered_profit_rates=tiered_profit_rates,
            balance_tier_ranges=BALANCE_TIER_RANGES,
            daily_rate=(Decimal(profit_rate) / 365),
        )
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_PROFIT",
            effective_date=DEFAULT_DATE,
        )
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.00143"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="INTERNAL_POSTING_ACCRUE_PROFIT_MOCK_HOOK_INTERNAL",
                    from_account_id=from_account_id,
                    from_account_address="DEFAULT",
                    to_account_id=to_account_id,
                    to_account_address="DEFAULT",
                    instruction_details={
                        "description": "Daily profit accrued on balance of 70",
                        "event": "ACCRUE_PROFIT",
                        "account_type": "MURABAHAH",
                    },
                    asset=DEFAULT_ASSET,
                ),
                call(
                    amount=Decimal("0.00143"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="INTERNAL_POSTING_ACCRUE_PROFIT_MOCK_HOOK_CUSTOMER",
                    from_account_id="Main account",
                    from_account_address=cust_from_address,
                    to_account_id="Main account",
                    to_account_address=cust_to_address,
                    instruction_details={
                        "description": "Daily profit accrued on balance of 70",
                        "event": "ACCRUE_PROFIT",
                        "account_type": "MURABAHAH",
                    },
                    asset=DEFAULT_ASSET,
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=[
                "INTERNAL_POSTING_ACCRUE_PROFIT_MOCK_HOOK_INTERNAL",
                "INTERNAL_POSTING_ACCRUE_PROFIT_MOCK_HOOK_CUSTOMER",
            ],
            client_batch_id="ACCRUE_PROFIT_MOCK_HOOK",
            effective_date=DEFAULT_DATE,
            batch_details={"event": "ACCRUE_PROFIT"},
        )

    def test_scheduled_code_does_not_accrue_outside_tier_ranges(self):
        accrue_profit_date = DEFAULT_DATE
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1),
            default_committed=Decimal(-100),
        )
        mock_vault = self.create_mock(balance_ts=balance_ts, denomination="MYR")
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_PROFIT",
            effective_date=accrue_profit_date,
        )
        self.assert_no_side_effects(mock_vault)

    def test_scheduled_code_accrue_profit_when_tiered_profit_is_zero(self):
        accrue_profit_date = DEFAULT_DATE + timedelta(hours=5)
        accrued_payable = Decimal(0)
        default_committed = Decimal(5000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            accrued_payable=accrued_payable,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(balance_ts=balance_ts, denomination="MYR")

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_PROFIT",
            effective_date=accrue_profit_date,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_scheduled_code_apply_accrued_profit_with_remainder_creates_reverse(
        self,
    ):
        input_data = [
            (
                "payable accrued, positive remainder",
                "4.06849",
                "4.06",
                "0.00849",
                "ACCRUED_PROFIT_PAYABLE",
                INTERNAL_CONTRA,
                ACCRUED_PROFIT_PAYABLE_ACCOUNT,
                "Main account",
                "ACCRUED_PROFIT_PAYABLE",
                INTERNAL_CONTRA,
                ACCRUED_PROFIT_PAYABLE_ACCOUNT,
                PROFIT_PAID_ACCOUNT,
                "PAYABLE",
            ),
        ]

        accrue_profit_date = DEFAULT_DATE
        start_of_day = accrue_profit_date
        default_committed = Decimal("10000")

        for input_row in input_data:
            incoming_amount = input_row[1]
            rounded_amount = input_row[2]
            remainder = input_row[3]
            cust_outgoing_account_address = input_row[4]
            cust_incoming_account_address = input_row[5]
            from_account_id = input_row[6]
            to_account_id = input_row[7]
            cust_from_account_address_reverse = input_row[8]
            cust_to_account_address_reverse = input_row[9]
            from_account_id_reverse = input_row[10]
            to_account_id_reverse = input_row[11]

            accrued_payable = Decimal(incoming_amount)

            balance_ts = self.account_balances(
                DEFAULT_DATE,
                accrued_payable=accrued_payable,
                default_committed=default_committed,
            )

            mock_vault = self.create_mock(
                balance_ts=balance_ts,
                denomination="MYR",
                profit_application_day=28,
                accrued_profit_payable_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
                profit_paid_account=PROFIT_PAID_ACCOUNT,
            )

            self.run_function(
                "scheduled_code",
                mock_vault,
                event_type="APPLY_ACCRUED_PROFIT",
                effective_date=accrue_profit_date,
            )

            mock_vault.make_internal_transfer_instructions.assert_has_calls(
                [
                    call(
                        amount=Decimal(rounded_amount),
                        denomination=DEFAULT_DENOMINATION,
                        from_account_id=from_account_id,
                        from_account_address="DEFAULT",
                        to_account_id=to_account_id,
                        to_account_address="DEFAULT",
                        client_transaction_id=f"{INTERNAL_POSTING}_APPLY_ACCRUED_"
                        f"PROFIT_MOCK_HOOK_MYR_INTERNAL",
                        instruction_details={
                            "description": "Profit Applied",
                            "event": "APPLY_ACCRUED_PROFIT",
                            "account_type": "MURABAHAH",
                        },
                        asset=DEFAULT_ASSET,
                        override_all_restrictions=True,
                    ),
                    call(
                        amount=Decimal(rounded_amount),
                        denomination=DEFAULT_DENOMINATION,
                        from_account_id="Main account",
                        from_account_address=cust_outgoing_account_address,
                        to_account_id="Main account",
                        to_account_address=cust_incoming_account_address,
                        client_transaction_id=f"{INTERNAL_POSTING}_APPLY_ACCRUED_"
                        f"PROFIT_MOCK_HOOK_MYR_CUSTOMER",
                        instruction_details={
                            "description": "Profit Applied",
                            "event": "APPLY_ACCRUED_PROFIT",
                            "account_type": "MURABAHAH",
                        },
                        asset=DEFAULT_ASSET,
                        override_all_restrictions=True,
                    ),
                    call(
                        amount=Decimal(remainder),
                        denomination=DEFAULT_DENOMINATION,
                        from_account_id=from_account_id_reverse,
                        from_account_address="DEFAULT",
                        to_account_id=to_account_id_reverse,
                        to_account_address="DEFAULT",
                        client_transaction_id=f"{INTERNAL_POSTING}_REVERSE_"
                        f"RESIDUAL_PROFIT_MOCK_HOOK_MYR_INTERNAL",
                        instruction_details={
                            "description": "Reversing accrued profit after application",
                            "event": "APPLY_ACCRUED_PROFIT",
                            "account_type": "MURABAHAH",
                        },
                        asset=DEFAULT_ASSET,
                        override_all_restrictions=True,
                    ),
                    call(
                        amount=Decimal(remainder),
                        denomination=DEFAULT_DENOMINATION,
                        from_account_id="Main account",
                        from_account_address=cust_from_account_address_reverse,
                        to_account_id="Main account",
                        to_account_address=cust_to_account_address_reverse,
                        client_transaction_id=f"{INTERNAL_POSTING}_REVERSE_"
                        f"RESIDUAL_PROFIT_MOCK_HOOK_MYR_CUSTOMER",
                        instruction_details={
                            "description": "Reversing accrued profit after application",
                            "event": "APPLY_ACCRUED_PROFIT",
                            "account_type": "MURABAHAH",
                        },
                        asset=DEFAULT_ASSET,
                        override_all_restrictions=True,
                    ),
                ]
            )

            mock_vault.instruct_posting_batch.assert_called_with(
                client_batch_id="APPLY_ACCRUED_PROFIT_MOCK_HOOK",
                posting_instructions=[
                    f"{INTERNAL_POSTING}_APPLY_ACCRUED_PROFIT_MOCK_HOOK_MYR_INTERNAL",
                    f"{INTERNAL_POSTING}_APPLY_ACCRUED_PROFIT_MOCK_HOOK_MYR_CUSTOMER",
                    f"{INTERNAL_POSTING}_REVERSE_RESIDUAL_PROFIT_MOCK_HOOK_MYR_INTERNAL",
                    f"{INTERNAL_POSTING}_REVERSE_RESIDUAL_PROFIT_MOCK_HOOK_MYR_CUSTOMER",
                ],
                effective_date=start_of_day,
                batch_details={"event": "APPLY_ACCRUED_PROFIT"},
            )

    def test_scheduled_code_applied_profit_with_no_remainder_has_no_reverse_postings(
        self,
    ):
        input_data = [
            (
                "payable accrued, no remainder",
                "4.07",
                "4.07",
                "ACCRUED_PROFIT_PAYABLE",
                INTERNAL_CONTRA,
                ACCRUED_PROFIT_PAYABLE_ACCOUNT,
                "Main account",
            ),
        ]

        accrue_profit_date = DEFAULT_DATE
        start_of_day = accrue_profit_date
        default_committed = Decimal("10000")

        for input_row in input_data:
            incoming_amount = input_row[1]
            rounded_amount = input_row[2]
            cust_outgoing_account_address = input_row[3]
            cust_incoming_account_address = input_row[4]
            from_account_id = input_row[5]
            to_account_id = input_row[6]

            accrued_payable = Decimal(incoming_amount)

            balance_ts = self.account_balances(
                DEFAULT_DATE,
                accrued_payable=accrued_payable,
                default_committed=default_committed,
            )

            mock_vault = self.create_mock(
                balance_ts=balance_ts,
                denomination="MYR",
                profit_application_day=28,
                accrued_profit_payable_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
                profit_paid_account=PROFIT_PAID_ACCOUNT,
            )

            self.run_function(
                "scheduled_code",
                mock_vault,
                event_type="APPLY_ACCRUED_PROFIT",
                effective_date=accrue_profit_date,
            )

            mock_vault.make_internal_transfer_instructions.assert_has_calls(
                [
                    call(
                        amount=Decimal(rounded_amount),
                        denomination=DEFAULT_DENOMINATION,
                        from_account_id=from_account_id,
                        from_account_address="DEFAULT",
                        to_account_id=to_account_id,
                        to_account_address="DEFAULT",
                        client_transaction_id=f"{INTERNAL_POSTING}_APPLY_ACCRUED_"
                        f"PROFIT_MOCK_HOOK_MYR_INTERNAL",
                        instruction_details={
                            "description": "Profit Applied",
                            "event": "APPLY_ACCRUED_PROFIT",
                            "account_type": "MURABAHAH",
                        },
                        asset=DEFAULT_ASSET,
                        override_all_restrictions=True,
                    ),
                    call(
                        amount=Decimal(rounded_amount),
                        denomination=DEFAULT_DENOMINATION,
                        from_account_id="Main account",
                        from_account_address=cust_outgoing_account_address,
                        to_account_id="Main account",
                        to_account_address=cust_incoming_account_address,
                        client_transaction_id=f"{INTERNAL_POSTING}_APPLY_ACCRUED_"
                        f"PROFIT_MOCK_HOOK_MYR_CUSTOMER",
                        instruction_details={
                            "description": "Profit Applied",
                            "event": "APPLY_ACCRUED_PROFIT",
                            "account_type": "MURABAHAH",
                        },
                        asset=DEFAULT_ASSET,
                        override_all_restrictions=True,
                    ),
                ]
            )

            mock_vault.instruct_posting_batch.assert_called_with(
                client_batch_id="APPLY_ACCRUED_PROFIT_MOCK_HOOK",
                posting_instructions=[
                    f"{INTERNAL_POSTING}_APPLY_ACCRUED_PROFIT_MOCK_HOOK_MYR_INTERNAL",
                    f"{INTERNAL_POSTING}_APPLY_ACCRUED_PROFIT_MOCK_HOOK_MYR_CUSTOMER",
                ],
                effective_date=start_of_day,
                batch_details={"event": "APPLY_ACCRUED_PROFIT"},
            )

    def test_scheduled_code_apply_accrue_profit_with_small_accrue_profit_payable(
        self,
    ):
        """
        This test should only create reverse posting since accrued_profit is 0.00 (2dp) we should
        reverse the residue accrued_profit.
        """
        accrue_profit_date = DEFAULT_DATE
        start_of_day = accrue_profit_date
        accrued_payable = Decimal(0.001)
        default_committed = Decimal(10000)

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            accrued_payable=accrued_payable,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="MYR",
            profit_application_day=28,
            accrued_profit_payable_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            profit_paid_account=PROFIT_PAID_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_ACCRUED_PROFIT",
            effective_date=accrue_profit_date,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=Decimal("0.001000000000000000020816681712"),
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
            from_account_address="DEFAULT",
            to_account_id=PROFIT_PAID_ACCOUNT,
            to_account_address="DEFAULT",
            client_transaction_id=INTERNAL_POSTING + "_REVERSE_RESIDUAL_PROFIT_"
            "MOCK_HOOK_MYR_INTERNAL",
            instruction_details={
                "description": "Reversing accrued profit after application",
                "event": "APPLY_ACCRUED_PROFIT",
                "account_type": "MURABAHAH",
            },
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=Decimal("0.001000000000000000020816681712"),
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address="ACCRUED_PROFIT_PAYABLE",
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            client_transaction_id=INTERNAL_POSTING + "_REVERSE_RESIDUAL_PROFIT_"
            "MOCK_HOOK_MYR_CUSTOMER",
            instruction_details={
                "description": "Reversing accrued profit after application",
                "event": "APPLY_ACCRUED_PROFIT",
                "account_type": "MURABAHAH",
            },
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_PROFIT_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_REVERSE_RESIDUAL_PROFIT_MOCK_HOOK_MYR_INTERNAL",
                "INTERNAL_POSTING_REVERSE_RESIDUAL_PROFIT_MOCK_HOOK_MYR_CUSTOMER",
            ],
            effective_date=start_of_day,
            batch_details={"event": "APPLY_ACCRUED_PROFIT"},
        )

    def test_post_parameter_change_code_amends_schedule_to_new_profit_application_day(
        self,
    ):
        accrued_payable = Decimal(0)
        default_committed = Decimal(2000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            accrued_payable=accrued_payable,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            profit_application_day=12,
            denomination="MYR",
            creation_date=DEFAULT_DATE,
            APPLY_ACCRUED_PROFIT=datetime(2020, 1, 1),
        )

        expected_schedule = {
            "year": "2019",
            "month": "1",
            "day": "12",
            "hour": "0",
            "minute": "0",
            "second": "0",
        }

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters={"profit_application_day": "28"},
            new_parameters={"profit_application_day": "12"},
            effective_date=DEFAULT_DATE,
        )

        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_PROFIT", new_schedule=expected_schedule
        )

    def test_post_parameter_change_code_with_undefined_new_profit_application_day(
        self,
    ):
        """
        This test should not call amend schedule.
        """
        accrued_payable = Decimal(0)
        default_committed = Decimal(2000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            accrued_payable=accrued_payable,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="MYR",
        )

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters={"profit_application_day": "28"},
            new_parameters={"not_profit_application_day_parameter": "12"},
            effective_date=DEFAULT_DATE,
        )
        mock_vault.amend_schedule.assert_not_called()

    def test_post_parameter_change_code_with_unchanged_profit_application_day(self):
        """
        This test should not call amend_schedule.
        """
        accrued_payable = Decimal(0)
        default_committed = Decimal(2000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            accrued_payable=accrued_payable,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="MYR",
            profit_application_day=28,
        )

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters={"profit_application_day": "28"},
            new_parameters={"profit_application_day": "28"},
            effective_date=DEFAULT_DATE,
        )
        mock_vault.amend_schedule.assert_not_called()

    def test_pre_posting_code_allows_unsupported_denom_with_override(self):
        accrued_payable = Decimal(0)
        default_committed = Decimal(1)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            accrued_payable=accrued_payable,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="MYR",
            minimum_deposit=Decimal(50),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=Decimal(100),
            maximum_deposit=Decimal(10000),
            maximum_withdrawal=Decimal(10000),
            maximum_payment_type_withdrawal=MAXIMUM_PAYMENT_TYPE_WITHDRAWAL,
        )
        test_posting = self.mock_posting_instruction(denomination="HKD", amount=Decimal(1))

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[test_posting],
            batch_details={"force_override": "true"},
        )

        self.run_function(
            "pre_posting_code",
            mock_vault,
            pib,
            DEFAULT_DATE,
        )

        self.assert_no_side_effects(mock_vault)

    def test_pre_posting_code_allows_negative_balance_with_override(self):
        accrued_payable = Decimal(0)
        default_committed = Decimal(1)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            accrued_payable=accrued_payable,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="MYR",
            gross_profit_rate=Decimal(0.1485),
            minimum_deposit=Decimal(50),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=Decimal(100),
            maximum_deposit=Decimal(10000),
            maximum_withdrawal=Decimal(10000),
            maximum_payment_type_withdrawal=MAXIMUM_PAYMENT_TYPE_WITHDRAWAL,
        )
        test_posting = self.mock_posting_instruction(denomination="MYR", amount=Decimal(50))

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[test_posting],
            batch_details={"force_override": "true"},
        )

        self.run_function(
            "pre_posting_code",
            mock_vault,
            pib,
            DEFAULT_DATE,
        )

        self.assert_no_side_effects(mock_vault)

    def test_close_code_reverses_accrued_profit(self):
        input_data = [
            (
                "10.78980",
                ACCRUED_PROFIT_PAYABLE_ACCOUNT,
                PROFIT_PAID_ACCOUNT,
                "ACCRUED_PROFIT_PAYABLE",
                INTERNAL_CONTRA,
            ),
            (
                "-10.78980",
                PROFIT_PAID_ACCOUNT,
                ACCRUED_PROFIT_PAYABLE_ACCOUNT,
                INTERNAL_CONTRA,
                "ACCRUED_PROFIT_PAYABLE",
            ),
        ]

        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(300)

        for (
            accrued_profit,
            from_account_id,
            to_account_id,
            from_cust_address,
            to_cust_address,
        ) in input_data:

            accrued_payable = Decimal(accrued_profit)

            balance_ts = self.account_balances(
                effective_time,
                default_committed=default_committed,
                accrued_payable=accrued_payable,
            )

            mock_vault = self.create_mock(
                balance_ts=balance_ts,
                denomination=DEFAULT_DENOMINATION,
                profit_paid_account=PROFIT_PAID_ACCOUNT,
                accrued_profit_payable_account=ACCRUED_PROFIT_PAYABLE_ACCOUNT,
                early_closure_fee="0",
                early_closure_days="0",
            )

            self.run_function("close_code", mock_vault, effective_date=effective_time)

            mock_vault.make_internal_transfer_instructions.assert_any_call(
                amount=abs(accrued_payable),
                client_transaction_id=f"{INTERNAL_POSTING}_REVERSE_RESIDUAL_PROFIT"
                f"_MOCK_HOOK_{DEFAULT_DENOMINATION}_CUSTOMER",
                denomination=DEFAULT_DENOMINATION,
                from_account_id="Main account",
                from_account_address=from_cust_address,
                to_account_id="Main account",
                to_account_address=to_cust_address,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                instruction_details={
                    "description": "Reverse profit due to account closure",
                    "event": "CLOSE_ACCOUNT",
                    "account_type": "MURABAHAH",
                },
            )
            mock_vault.make_internal_transfer_instructions.assert_any_call(
                amount=abs(accrued_payable),
                client_transaction_id=f"{INTERNAL_POSTING}_REVERSE_RESIDUAL_PROFIT"
                f"_MOCK_HOOK_{DEFAULT_DENOMINATION}_INTERNAL",
                denomination=DEFAULT_DENOMINATION,
                from_account_id=from_account_id,
                from_account_address="DEFAULT",
                to_account_id=to_account_id,
                to_account_address="DEFAULT",
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                instruction_details={
                    "description": "Reverse profit due to account closure",
                    "event": "CLOSE_ACCOUNT",
                    "account_type": "MURABAHAH",
                },
            )
            mock_vault.instruct_posting_batch.assert_called_with(
                client_batch_id="MOCK_HOOK",
                batch_details={"event": "CLOSE_CODE"},
                posting_instructions=[
                    INTERNAL_POSTING + "_REVERSE_RESIDUAL_PROFIT_MOCK_HOOK_MYR" "_INTERNAL",
                    INTERNAL_POSTING + "_REVERSE_RESIDUAL_PROFIT_MOCK_HOOK_MYR" "_CUSTOMER",
                ],
                effective_date=effective_time,
            )
