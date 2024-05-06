# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from json import dumps

# common
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ExpectedSchedule,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_instance_parameter_change_event,
    create_calendar,
    create_calendar_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
)

ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"
EXPECTED_OUTPUT = "library/murabahah/contracts/tests/simulation/expected_output.json"

ASSET = "ASSET"
LIABILITY = "LIABILITY"
PUBLIC_HOLIDAYS = "PUBLIC_HOLIDAYS"

CONTRACT_FILE = "library/murabahah/contracts/template/murabahah.py"
MURABAHAH_ACCOUNT = "Murabahah Account"
ACCRUED_PROFIT_PAYABLE_ACCOUNT = "ACCRUED_PROFIT_PAYABLE"
PROFIT_PAID_ACCOUNT = "PROFIT_PAID"
EARLY_CLOSURE_FEE_INCOME_ACCOUNT = "EARLY_CLOSURE_FEE_INCOME"
DUMMY_DEPOSITING_ACCOUNT = "DUMMY_DEPOSITING_ACCOUNT"
PAYMENT_TYPE_FEE_INCOME_ACCOUNT = "PAYMENT_TYPE_FEE_INCOME"

INTERNAL_CONTRA = "INTERNAL_CONTRA"

ACCRUED_PROFIT_PAYABLE_DIM = BalanceDimensions(
    address="ACCRUED_PROFIT_PAYABLE",
    denomination="MYR",
)
ACCRUED_PROFIT_RECEIVABLE_DIM = BalanceDimensions(
    address="ACCRUED_PROFIT_RECEIVABLE",
    denomination="MYR",
)
INTERNAL_CONTRA_DIM = BalanceDimensions(
    address="INTERNAL_CONTRA",
    denomination="MYR",
)

DEFAULT_DIM = BalanceDimensions(
    address="DEFAULT",
    asset="COMMERCIAL_BANK_MONEY",
    denomination="MYR",
    phase="POSTING_PHASE_COMMITTED",
)

OUTGOING_DIM = BalanceDimensions(
    address="DEFAULT",
    asset="COMMERCIAL_BANK_MONEY",
    denomination="MYR",
    phase="POSTING_PHASE_PENDING_OUTGOING",
)

INCOMING_DIM = BalanceDimensions(
    address="DEFAULT",
    asset="COMMERCIAL_BANK_MONEY",
    denomination="MYR",
    phase="POSTING_PHASE_PENDING_INCOMING",
)

default_internal_accounts = {
    DUMMY_DEPOSITING_ACCOUNT: LIABILITY,
    ACCRUED_PROFIT_PAYABLE_ACCOUNT: LIABILITY,
    PROFIT_PAID_ACCOUNT: ASSET,
    EARLY_CLOSURE_FEE_INCOME_ACCOUNT: LIABILITY,
    PAYMENT_TYPE_FEE_INCOME_ACCOUNT: LIABILITY,
}

BALANCE_TIER_RANGES = dumps(
    {
        "tier1": {"min": "0"},
        "tier2": {"min": "15000.00"},
    }
)
TIERED_PROFIT_RATES = dumps(
    {
        "MURABAHAH_TIER_UPPER": {"tier1": "0.02", "tier2": "0.015"},
        "MURABAHAH_TIER_MIDDLE": {"tier1": "0.0125", "tier2": "0.01"},
        "MURABAHAH_TIER_LOWER": {"tier1": "0.149", "tier2": "0.1"},
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
ZERO_TIERED_PROFIT_RATES = dumps(
    {
        "MURABAHAH_TIER_UPPER": {"tier1": "0", "tier2": "0"},
        "MURABAHAH_TIER_MIDDLE": {"tier1": "0", "tier2": "0"},
        "MURABAHAH_TIER_LOWER": {"tier1": "0", "tier2": "0"},
    }
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
        "ATM_ARBM": {"fee": "0.50", "limit": "2"},
    }
)

default_instance_params = {
    "profit_application_day": "5",
}
default_template_params = {
    "account_tier_names": ACCOUNT_TIER_NAMES,
    "denomination": "MYR",
    "days_in_year": "365",
    "profit_accrual_hour": "0",
    "profit_accrual_minute": "0",
    "profit_accrual_second": "0",
    "profit_application_hour": "0",
    "profit_application_minute": "1",
    "profit_application_second": "0",
    "profit_application_frequency": "monthly",
    "minimum_deposit": "100",
    "minimum_initial_deposit": "0",
    "maximum_balance": "10000",
    "maximum_deposit": "10000",
    "maximum_withdrawal": "10000",
    "maximum_payment_type_withdrawal": MAXIMUM_PAYMENT_TYPE_WITHDRAWAL,
    "maximum_daily_deposit": "1001",
    "maximum_daily_withdrawal": "100",
    "maximum_daily_payment_category_withdrawal": MAXIMUM_DAILY_PAYMENT_CATEGORY_WITHDRAWAL,
    "maximum_daily_payment_type_withdrawal": MAXIMUM_DAILY_PAYMENT_TYPE_WITHDRAWAL,
    "maximum_monthly_payment_type_withdrawal_limit": MAX_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT,
    "balance_tier_ranges": BALANCE_TIER_RANGES,
    "tiered_minimum_balance_threshold": TIERED_MIN_BALANCE_THRESHOLD,
    "tiered_profit_rates": TIERED_PROFIT_RATES,
    "payment_type_flat_fee": PAYMENT_TYPE_FLAT_FEES,
    "payment_type_threshold_fee": PAYMENT_TYPE_THRESHOLD_FEES,
    "early_closure_fee": "0",
    "early_closure_days": "0",
    "accrued_profit_payable_account": ACCRUED_PROFIT_PAYABLE_ACCOUNT,
    "early_closure_fee_income_account": EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
    "payment_type_fee_income_account": PAYMENT_TYPE_FEE_INCOME_ACCOUNT,
    "profit_paid_account": PROFIT_PAID_ACCOUNT,
}


class MurabahahTest(SimulationTestCase):

    account_id_base = MURABAHAH_ACCOUNT
    contract_filepaths = [CONTRACT_FILE]
    expected_output_filename = EXPECTED_OUTPUT
    internal_accounts = default_internal_accounts

    def get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
    ):
        contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[CONTRACT_FILE],
            template_params=template_params or self.default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or self.default_instance_params,
                    account_id_base=self.account_id_base,
                )
            ],
        )
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=self.internal_accounts or internal_accounts,
            debug=False,
        )

    def test_schedules(self):
        """
        Test that the correct profit accrual, application and maintenance fee schedules are
        created when the account is instantiated.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        # needs to be 2nd day for the profit to apply since the year just started on the 1st day
        end = datetime(year=2020, month=1, day=2, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        template_params["profit_application_hour"] = "0"
        template_params["profit_application_minute"] = "1"
        template_params["profit_application_second"] = "0"
        template_params["profit_application_frequency"] = "monthly"
        template_params["profit_accrual_hour"] = "0"
        template_params["profit_accrual_minute"] = "0"
        template_params["profit_accrual_second"] = "0"
        instance_params = default_instance_params.copy()
        instance_params["profit_application_day"] = "1"

        # get accrue profit schedules
        # 367 because we added 2 days
        run_times_accrue_profit = []
        accrue_profit_date = start
        accrue_profit_date = accrue_profit_date.replace(
            hour=int(template_params["profit_accrual_hour"]),
            minute=int(template_params["profit_accrual_minute"]),
            second=int(template_params["profit_accrual_second"]),
        )
        run_times_accrue_profit.append(accrue_profit_date)
        for _ in range(0, 366):
            accrue_profit_date = accrue_profit_date + relativedelta(days=1)
            run_times_accrue_profit.append(accrue_profit_date)

        # get apply profit and monthly fee schedules
        # this is monthly profit and fee so should be 12
        run_times_apply_profit = []
        profit_application_date = start
        profit_application_date = profit_application_date.replace(
            day=int(instance_params["profit_application_day"]),
            hour=int(template_params["profit_application_hour"]),
            minute=int(template_params["profit_application_minute"]),
            second=int(template_params["profit_application_second"]),
        )

        for _ in range(0, 12):
            profit_application_date = profit_application_date + relativedelta(months=1)
            run_times_apply_profit.append(profit_application_date)

        sub_tests = [
            SubTest(
                description="check schedules",
                events=[],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=run_times_accrue_profit,
                        event_id="ACCRUE_PROFIT",
                        account_id=MURABAHAH_ACCOUNT,
                        count=367,
                    ),
                    ExpectedSchedule(
                        run_times=run_times_apply_profit,
                        event_id="APPLY_ACCRUED_PROFIT",
                        account_id=MURABAHAH_ACCOUNT,
                        count=12,
                    ),
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_schedules_profit_payment_day_change(self):
        """
        Test that the profit application schedule is updated when the profit application day
        parameter is changed.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=2, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        template_params["profit_application_hour"] = "0"
        template_params["profit_application_minute"] = "1"
        template_params["profit_application_second"] = "0"
        template_params["profit_application_frequency"] = "monthly"
        template_params["profit_accrual_hour"] = "0"
        template_params["profit_accrual_minute"] = "0"
        template_params["profit_accrual_second"] = "0"
        instance_params = default_instance_params.copy()
        instance_params["profit_application_day"] = "1"

        new_profit_application_day = "3"

        # get accrue profit schedules
        # 367 because we added 2 days
        run_times_accrue_profit = []
        accrue_profit_date = start
        accrue_profit_date = accrue_profit_date.replace(
            hour=int(template_params["profit_accrual_hour"]),
            minute=int(template_params["profit_accrual_minute"]),
            second=int(template_params["profit_accrual_second"]),
        )
        run_times_accrue_profit.append(accrue_profit_date)
        for _ in range(0, 366):
            accrue_profit_date = accrue_profit_date + relativedelta(days=1)
            run_times_accrue_profit.append(accrue_profit_date)

        # get apply profit schedules
        # this is monthly profit and fee so should be 12
        run_times_apply_profit = []
        profit_application_date = start
        profit_application_date = profit_application_date.replace(
            day=int(new_profit_application_day),
            hour=int(template_params["profit_application_hour"]),
            minute=int(template_params["profit_application_minute"]),
            second=int(template_params["profit_application_second"]),
        )
        for _ in range(0, 12):
            run_times_apply_profit.append(profit_application_date)
            profit_application_date = profit_application_date + relativedelta(months=1)

        sub_tests = [
            SubTest(
                description="check schedules with new profit application day change",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start,
                        account_id=MURABAHAH_ACCOUNT,
                        profit_application_day=new_profit_application_day,
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=run_times_accrue_profit,
                        event_id="ACCRUE_PROFIT",
                        account_id=MURABAHAH_ACCOUNT,
                        count=367,
                    ),
                    ExpectedSchedule(
                        run_times=run_times_apply_profit,
                        event_id="APPLY_ACCRUED_PROFIT",
                        account_id=MURABAHAH_ACCOUNT,
                        count=12,
                    ),
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_account_schedules_apply_accrue_profit_monthly(self):
        """
        Test if the schedules runtime of the apply accrue profit are correct when the frequency is
        set to monthly and when the application creation date falls on the end of the month dates
        29, 30, 31.
        """
        start = datetime(year=2019, month=1, day=29, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=30, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["profit_application_day"] = "30"

        sub_tests = [
            SubTest(
                description="ensure montly apply accrue profit schedule runtime is correct",
                events=[],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2019,
                                month=1,
                                day=30,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2019,
                                month=2,
                                day=28,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2019,
                                month=3,
                                day=30,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="APPLY_ACCRUED_PROFIT",
                        account_id=MURABAHAH_ACCOUNT,
                        count=3,
                    )
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_account_schedules_apply_accrue_profit_quarterly(self):
        """
        Test if the schedules runtime of the apply accrue profit are correct when the frequency is
        set to quarterly and when the application creation date falls on the end of the month dates
        29, 30, 31.
        """
        start = datetime(year=2019, month=1, day=29, tzinfo=timezone.utc)
        end = datetime(year=2019, month=12, day=30, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        template_params["profit_application_frequency"] = "quarterly"
        instance_params = default_instance_params.copy()
        instance_params["profit_application_day"] = "30"

        sub_tests = [
            SubTest(
                description="ensure apply accrue profit schedule runtime quarterly is correct",
                events=[],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2019,
                                month=4,
                                day=30,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2019,
                                month=7,
                                day=30,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2019,
                                month=10,
                                day=30,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="APPLY_ACCRUED_PROFIT",
                        account_id=MURABAHAH_ACCOUNT,
                        count=3,
                    )
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_account_schedules_apply_accrue_profit_annually(self):
        """
        Test if the schedules runtime of the apply accrue profit are correct when the frequency is
        set to annually and when the application creation date falls on the end of the month dates
        29, 30, 31.
        """
        start = datetime(year=2019, month=1, day=29, tzinfo=timezone.utc)
        end = datetime(year=2022, month=12, day=30, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        template_params["profit_application_frequency"] = "annually"
        instance_params = default_instance_params.copy()
        instance_params["profit_application_day"] = "30"

        sub_tests = [
            SubTest(
                description="ensure apply accrue profit schedule runtime annually is correct",
                events=[],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=1,
                                day=30,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2021,
                                month=1,
                                day=30,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2022,
                                month=1,
                                day=30,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="APPLY_ACCRUED_PROFIT",
                        account_id=MURABAHAH_ACCOUNT,
                        count=3,
                    )
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_account_schedules_apply_accrue_profit_on_holiday(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=30, hour=23, tzinfo=timezone.utc)
        holiday_start = datetime(2019, 1, 30, tzinfo=timezone.utc)
        holiday_end = datetime(2019, 1, 30, 23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["profit_application_day"] = "30"

        events = [
            create_calendar(
                timestamp=start,
                calendar_id=PUBLIC_HOLIDAYS,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="TEST1",
                calendar_id=PUBLIC_HOLIDAYS,
                start_timestamp=holiday_start,
                end_timestamp=holiday_end,
            ),
        ]

        sub_tests = [
            SubTest(
                description="check apply accrue profit date when it falls on a holiday",
                events=events,
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2019,
                                month=1,
                                day=31,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2019,
                                month=2,
                                day=28,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2019,
                                month=3,
                                day=30,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="APPLY_ACCRUED_PROFIT",
                        account_id=MURABAHAH_ACCOUNT,
                        count=3,
                    )
                ],
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_account_schedules_apply_accrue_profit_on_holiday_consecutive(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=30, hour=23, tzinfo=timezone.utc)
        holiday_start = datetime(2019, 1, 30, tzinfo=timezone.utc)
        holiday_end = datetime(2019, 1, 30, 23, tzinfo=timezone.utc)
        holiday_start2 = datetime(2019, 1, 31, tzinfo=timezone.utc)
        holiday_end2 = datetime(2019, 1, 31, 23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["profit_application_day"] = "30"

        events = [
            create_calendar(
                timestamp=start,
                calendar_id=PUBLIC_HOLIDAYS,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="TEST1",
                calendar_id=PUBLIC_HOLIDAYS,
                start_timestamp=holiday_start,
                end_timestamp=holiday_end,
            ),
            create_calendar_event(
                timestamp=start,
                calendar_event_id="TEST2",
                calendar_id=PUBLIC_HOLIDAYS,
                start_timestamp=holiday_start2,
                end_timestamp=holiday_end2,
            ),
        ]

        sub_tests = [
            SubTest(
                description="check withdrawal date when it falls on a holiday",
                events=events,
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2019,
                                month=2,
                                day=1,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2019,
                                month=2,
                                day=28,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2019,
                                month=3,
                                day=30,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="APPLY_ACCRUED_PROFIT",
                        account_id=MURABAHAH_ACCOUNT,
                        count=3,
                    )
                ],
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)
