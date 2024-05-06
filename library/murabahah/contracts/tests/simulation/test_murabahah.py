# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
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
    create_auth_adjustment_instruction,
    create_flag_definition_event,
    create_flag_event,
    create_inbound_authorisation_instruction,
    create_inbound_hard_settlement_instruction,
    create_outbound_authorisation_instruction,
    create_outbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_release_event,
    create_settlement_event,
    update_account_status_pending_closure,
    create_calendar,
    create_calendar_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
)

CONTRACT_FILE = "library/murabahah/contracts/template/murabahah.py"
EXPECTED_OUTPUT = "library/murabahah/contracts/tests/simulation/expected_output.json"

ASSET = "ASSET"
LIABILITY = "LIABILITY"
PUBLIC_HOLIDAYS = "PUBLIC_HOLIDAYS"

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
    "profit_accrual_hour": "1",
    "profit_accrual_minute": "0",
    "profit_accrual_second": "0",
    "profit_application_hour": "1",
    "profit_application_minute": "5",
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

    def test_single_deposit(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        sub_tests = [
            SubTest(
                description="check balance after single deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "1000"),
                        ],
                    }
                },
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

    def test_profit_accrual_payable(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, hour=2, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        # the balance of the previous day (23:59:59) is used so on day 1 nothing is paid
        sub_tests = [
            SubTest(
                description="check profit accrual payable",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "1000"),
                            (INTERNAL_CONTRA_DIM, Decimal("-0.40821")),
                            (ACCRUED_PROFIT_PAYABLE_DIM, Decimal("0.40821")),
                        ],
                        PROFIT_PAID_ACCOUNT: [(DEFAULT_DIM, Decimal("0.40821"))],
                        ACCRUED_PROFIT_PAYABLE_ACCOUNT: [(DEFAULT_DIM, Decimal("0.40821"))],
                    }
                },
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

    def test_profit_application_payable_customer_account(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=1, hour=1, minute=10, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["profit_application_day"] = "1"

        sub_tests = [
            SubTest(
                description="check accrued profit payable to customer",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    # 31 days of profit accrued 1000 * 0.00040822 = 0.40822 * 31 = 12.65451
                    # checking just before profit application which runs at 01:05:00
                    end
                    - timedelta(minutes=6): {
                        MURABAHAH_ACCOUNT: [
                            (INTERNAL_CONTRA_DIM, Decimal("-12.65451")),
                            (ACCRUED_PROFIT_PAYABLE_DIM, Decimal("12.65451")),
                            (DEFAULT_DIM, Decimal("1000")),
                        ],
                    },
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (INTERNAL_CONTRA_DIM, Decimal("0")),
                            (ACCRUED_PROFIT_PAYABLE_DIM, Decimal("0")),
                            (DEFAULT_DIM, Decimal("1012.65")),
                        ],
                    },
                },
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

    def test_max_daily_deposit_in_single_posting(self):
        """
        Check if deposits over `maximum_daily_deposit` are rejected when deposited in 1 go.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        template_params["maximum_daily_deposit"] = "1000"
        instance_params = default_instance_params.copy()

        sub_tests = [
            SubTest(
                description="check max daily deposit in single posting",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1001",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "1000"),
                        ],
                    }
                },
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

    def test_max_daily_deposit_multiple_postings(self):
        """
        Check if deposits over `maximum_daily_deposit` are rejected when deposited over multiple
        postings.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_deposit"] = "1001"

        sub_tests = [
            SubTest(
                description="check max daily deposit in multiple posting",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="700",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "500"),
                        ],
                    }
                },
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

    def test_max_daily_deposit_multiple_postings_concurrent(self):
        """
        Are deposits over `maximum_daily_deposit` rejected when deposited over multiple postings at
        the same time.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_deposit"] = "1001"

        sub_tests = [
            SubTest(
                description="check max daily deposit in multiple concurrent posting",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="700",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "500"),
                        ],
                    }
                },
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

    def test_max_daily_deposit_under_24_hrs(self):
        """
        Check if `maximum_daily_deposit` is respected over the midnight boundary.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=3, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_deposit"] = "1001"

        sub_tests = [
            SubTest(
                description="check max daily deposit within the last 24 hours",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=22),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # should fail as it takes us over maximum_daily_deposit
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=23),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # should succeed as we're in a new day
                    create_inbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=start + timedelta(days=1, hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # should fail
                    create_inbound_hard_settlement_instruction(
                        amount="400",
                        event_datetime=start + timedelta(days=1, hours=23),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "1900"),
                        ],
                    }
                },
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

    def test_max_daily_deposit_with_withdrawal(self):
        """
        Check if withdrawing modifies the `maximum_daily_deposit` limit. It should not.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=3, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        # increase max withdrawal to withdraw enough within 1 day.
        template_params["maximum_daily_withdrawal"] = "1000"
        template_params["maximum_daily_deposit"] = "1001"

        sub_tests = [
            SubTest(
                description="check max daily deposit with witdrawal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # should pass because it is a new day
                    create_inbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=start + timedelta(days=1, hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # over the deposit limit
                    create_inbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=start + timedelta(days=1, hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # can we reset the 'counter' with a withdrawal?
                    create_outbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=start + timedelta(days=1, hours=4),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # next two are still over the deposit limit
                    create_inbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=start + timedelta(days=1, hours=5),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(days=1, hours=5),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # next two should work
                    create_inbound_hard_settlement_instruction(
                        amount="400",
                        event_datetime=start + timedelta(days=1, hours=6),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=start + timedelta(days=2, hours=7),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "2000"),
                        ],
                    }
                },
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

    def test_min_deposit(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["minimum_deposit"] = "100"

        sub_tests = [
            SubTest(
                description="check miniumum deposit respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # should all fail did not consider values less than 0 as the endpoint will
                    # raise an error
                    create_inbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="0.01",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="99",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "100"),
                        ],
                    }
                },
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

    def test_max_deposit(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_deposit"] = "100000"

        sub_tests = [
            SubTest(
                description="check maxiumum deposit respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="50000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10001",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10000.01",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "10000"),
                        ],
                    }
                },
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

    def test_max_balance(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=26, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_balance"] = "10000"
        instance_params["profit_application_day"] = "28"

        sub_tests = [
            SubTest(
                description="check max balance",
                events=[
                    # create 10 transactions over 10 days to build up to `maximum_balance`
                    *[
                        create_inbound_hard_settlement_instruction(
                            amount="1000",
                            event_datetime=start + timedelta(days=i, hours=1),
                            target_account_id=MURABAHAH_ACCOUNT,
                            internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                            denomination=default_template_params["denomination"],
                        )
                        for i in range(0, 10)
                    ],
                    # should fail over max allowable balance
                    create_inbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=start + timedelta(days=10, hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "10000"),
                        ],
                    }
                },
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

    def test_max_balance_with_profit(self):
        """
        Check that profit is applied correctly if account is over `maximum_balance`. As well as
        not being able to deposit.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=26, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_balance"] = "10000"
        instance_params["profit_application_day"] = "28"

        sub_tests = [
            SubTest(
                description="check max balance with profit",
                events=[
                    # create 10 transactions over 10 days to build up to `maximum_balance`
                    *[
                        create_inbound_hard_settlement_instruction(
                            amount="1000",
                            event_datetime=start + timedelta(days=i, minutes=1),
                            target_account_id=MURABAHAH_ACCOUNT,
                            internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                            denomination=default_template_params["denomination"],
                        )
                        for i in range(0, 10)
                    ],
                    # next 2 events should not get through to the account
                    create_inbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=start + timedelta(days=10, minutes=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(days=14, minutes=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "10091.84"),
                        ],
                    }
                },
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

    def test_single_withdrawal(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        sub_tests = [
            SubTest(
                description="check if single withdrawal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "450"),
                        ],
                    }
                },
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

    def test_max_daily_withdrawal_single_posting(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_withdrawal"] = "100"

        sub_tests = [
            SubTest(
                description="check maxiumum daily withdrawal respected in single posting",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="101",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "400"),
                        ],
                    }
                },
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

    def test_bad_withdrawals(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_withdrawal"] = "100"

        sub_tests = [
            SubTest(
                description="check if max daily withdrawal respected when including bad postings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="110",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "450"),
                        ],
                    }
                },
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

    def test_max_withdrawal(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_withdrawal"] = "10000"
        template_params["maximum_daily_deposit"] = "10000"
        template_params["maximum_withdrawal"] = "5000"

        sub_tests = [
            SubTest(
                description="check min withdrawal respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="5000.01",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="5001",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "5000"),
                        ],
                    }
                },
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

    def test_withdrawal_independence(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_withdrawal"] = "100"

        sub_tests = [
            SubTest(
                description="check withdrawal indpendence",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # below 3 should all fail
                    create_outbound_hard_settlement_instruction(
                        amount="101",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=4),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # valid withdrawal in the middle
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=6),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # below 3 should fail
                    create_outbound_hard_settlement_instruction(
                        amount="101",
                        event_datetime=start + timedelta(hours=7),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + timedelta(hours=8),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=9),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "950"),
                        ],
                    }
                },
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

    def test_max_daily_withdrawal(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=3, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_withdrawal"] = "100"

        sub_tests = [
            SubTest(
                description="check max daily withdrawal repected with deposits in between over"
                " multiple days",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # will bring the balance up to 200 again
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + timedelta(hours=4),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # should fail as we've already withdrawn the max daily amount
                    create_outbound_hard_settlement_instruction(
                        amount="60",
                        event_datetime=start + timedelta(hours=5),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + timedelta(hours=7),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # following 2 should succeed as the withdrawals are on a new day
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(days=1, hours=5),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(days=1, hours=6),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + timedelta(days=1, hours=7),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # should fail
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(days=1, hours=8),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "300"),
                        ],
                    }
                },
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

    def test_max_daily_withdrawal_under_24_hrs(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=3, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_withdrawal"] = "100"

        sub_tests = [
            SubTest(
                description="check max daily withdrawal respected over the midnight boundary",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + timedelta(hours=22),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # should fail as we've already withdrawn the max daily amount
                    create_outbound_hard_settlement_instruction(
                        amount="60",
                        event_datetime=start + timedelta(hours=23),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # following should succeed as the withdrawal is on a new day
                    create_outbound_hard_settlement_instruction(
                        amount="90",
                        event_datetime=start + timedelta(days=1, hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # should fail
                    create_outbound_hard_settlement_instruction(
                        amount="90",
                        event_datetime=start + timedelta(days=1, hours=23),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "810"),
                        ],
                    }
                },
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

    def test_wrong_denomination(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        time = start + timedelta(hours=2)

        sub_tests = [
            SubTest(
                description="check non default denominations rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination="MYR",
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=time,
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination="EUR",
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "500"),
                        ],
                    }
                },
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

    def test_change_date(self):
        start = datetime(year=2019, month=1, day=26, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=4, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["profit_application_day"] = "27"

        sub_tests = [
            SubTest(
                description="check profit application day change",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start,
                        account_id=MURABAHAH_ACCOUNT,
                        profit_application_day="3",
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "100.32"),
                        ],
                    }
                },
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

    def test_change_profit_application_day_on_holiday(self):
        start = datetime(2019, 1, 1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=30, hour=23, tzinfo=timezone.utc)
        change_param_start = datetime(2019, 2, 1, tzinfo=timezone.utc)
        holiday_start = datetime(2019, 2, 3, tzinfo=timezone.utc)
        holiday_end = datetime(2019, 2, 3, 23, tzinfo=timezone.utc)
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
            create_instance_parameter_change_event(
                timestamp=change_param_start,
                account_id=MURABAHAH_ACCOUNT,
                profit_application_day="3",
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
                                day=30,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2019,
                                month=2,
                                day=4,
                                hour=int(template_params["profit_application_hour"]),
                                minute=int(template_params["profit_application_minute"]),
                                second=int(template_params["profit_application_second"]),
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2019,
                                month=3,
                                day=3,
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

    def test_expired_flags_no_longer_have_tier_effect(self):
        """
        Check that an expired flag is no longer considered for tiering.
        """
        start = datetime(year=2019, month=1, day=1, hour=0, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=2, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        template_params["account_tier_names"] = dumps(["X", "Y", "Z"])
        template_params["days_in_year"] = "365"
        template_params["profit_accrual_hour"] = "0"
        template_params["profit_accrual_minute"] = "0"
        template_params["profit_accrual_second"] = "0"
        template_params["profit_application_hour"] = "0"
        template_params["profit_application_minute"] = "1"
        template_params["profit_application_second"] = "0"
        instance_params = default_instance_params.copy()
        template_params["minimum_deposit"] = "50"
        template_params["balance_tier_ranges"] = dumps(
            {
                "tier1": {"min": "0"},
                "tier2": {"min": "50.00"},
            }
        )
        template_params["tiered_minimum_balance_threshold"] = dumps(
            {"X": "10", "Y": "100", "Z": "200"}
        )
        template_params["tiered_profit_rates"] = dumps(
            {
                "X": {"tier1": "0.1", "tier2": "0.2"},
                "Y": {"tier1": "0.005", "tier2": "0.01"},
                "Z": {"tier1": "0", "tier2": "0"},
            }
        )

        expected_balances = {}
        for i in range(60):
            profit_date = start + relativedelta(days=i)
            expected_balances[profit_date] = {
                MURABAHAH_ACCOUNT: [
                    (
                        ACCRUED_PROFIT_PAYABLE_DIM,
                        self.expected_output["tiered_profit_accrual_payable"][i],
                    ),
                ],
            }

        expected_balances[end] = {
            MURABAHAH_ACCOUNT: [
                (DEFAULT_DIM, "1002.42"),
            ],
        }

        # check min account balance fee has only been charged in the first month, based on flag Y
        sub_tests = [
            SubTest(
                description="",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_flag_definition_event(timestamp=start, flag_definition_id="Y"),
                    create_flag_definition_event(timestamp=start, flag_definition_id="X"),
                    create_flag_event(
                        timestamp=start,
                        expiry_timestamp=start + timedelta(days=32),
                        flag_definition_id="Y",
                        account_id=MURABAHAH_ACCOUNT,
                    ),
                    create_flag_event(
                        timestamp=start + timedelta(days=32) + timedelta(seconds=1),
                        expiry_timestamp=end,
                        flag_definition_id="X",
                        account_id=MURABAHAH_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts=expected_balances,
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

    def test_in_auth_release(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["minimum_deposit"] = "100"

        sub_tests = [
            SubTest(
                description="check inbound auth and release",
                events=[
                    create_inbound_authorisation_instruction(
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        amount="100.00",
                        event_datetime=start + timedelta(hours=3),
                        denomination=default_template_params["denomination"],
                        client_transaction_id="RELEASE_TEST_TRANSACTION",
                    ),
                    create_release_event(
                        client_transaction_id="RELEASE_TEST_TRANSACTION",
                        event_datetime=start + timedelta(hours=6),
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (INCOMING_DIM, "0"),
                        ],
                    }
                },
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

    def test_out_auth_release(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=10, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        sub_tests = [
            SubTest(
                description="check outbound auth and release",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_authorisation_instruction(
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        amount="60.00",
                        event_datetime=start + timedelta(hours=3),
                        denomination=default_template_params["denomination"],
                        client_transaction_id="RELEASE_TEST_TRANSACTION",
                    ),
                    create_release_event(
                        client_transaction_id="RELEASE_TEST_TRANSACTION",
                        event_datetime=start + timedelta(hours=6),
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "100"),
                            (OUTGOING_DIM, Decimal("0")),
                        ],
                    }
                },
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

    def test_in_auth_settlement(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=10, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["minimum_deposit"] = "100"

        sub_tests = [
            SubTest(
                description="check inbound auth and settlement",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_authorisation_instruction(
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        amount="100.00",
                        event_datetime=start + timedelta(hours=3),
                        denomination=default_template_params["denomination"],
                        client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
                    ),
                    create_settlement_event(
                        "100.00",
                        event_datetime=start + timedelta(hours=4),
                        client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
                        final=True,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "300"),
                            (INCOMING_DIM, Decimal("0")),
                        ],
                    }
                },
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

    def test_out_auth_settlement(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=10, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        sub_tests = [
            SubTest(
                description="check outbound auth and settlement",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_authorisation_instruction(
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        amount="60.00",
                        event_datetime=start + timedelta(hours=3),
                        denomination=default_template_params["denomination"],
                        client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
                    ),
                    create_settlement_event(
                        "60.00",
                        event_datetime=start + timedelta(hours=4),
                        client_transaction_id="SETTLEMENT_TEST_TRANSACTION",
                        final=True,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "140"),
                            (OUTGOING_DIM, Decimal("0")),
                        ],
                    }
                },
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

    def test_out_auth_adjustment(self):
        """
        Check an Outbound Authorisation posting followed by authorisation Adjustment.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=10, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        sub_tests = [
            SubTest(
                description="check outbound auth followed by auth adjustment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_authorisation_instruction(
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        amount="50.00",
                        event_datetime=start + timedelta(hours=3),
                        denomination=default_template_params["denomination"],
                        client_transaction_id="ADJUSTMENT_TEST_TRANSACTION",
                    ),
                    create_auth_adjustment_instruction(
                        amount="30.00",
                        event_datetime=start + timedelta(hours=4),
                        client_transaction_id="ADJUSTMENT_TEST_TRANSACTION",
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "200"),
                            (OUTGOING_DIM, Decimal("-80")),
                        ],
                    }
                },
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

    def test_back_dated_posting_double_spend(self):
        """
        This test will check if backdated posting will be rejected if there are no funds anymore
        during the time it wants to backdate [value timestamp].
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=4, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_withdrawal"] = "5000"
        template_params["maximum_daily_deposit"] = "5000"

        sub_tests = [
            SubTest(
                description="",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=5),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # doing back dated deposit to check if its supported
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=6),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        value_timestamp=start + timedelta(hours=1),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=start + timedelta(hours=7),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # should be rejected since all funds was withdrawn on the previous event
                    create_outbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=start + timedelta(hours=8),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        value_timestamp=start + timedelta(hours=5),
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "100"),
                        ],
                    }
                },
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

    def test_back_dated_posting_max_account_balance(self):
        """
        Test if backdated deposit posting will go above the account balance limit.
        """
        start = datetime(year=2019, month=1, day=5, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=20, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_balance"] = "10000"
        template_params["maximum_daily_deposit"] = "10000"

        sub_tests = [
            SubTest(
                description="check backdated deposit will go above account balance limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + timedelta(hours=8),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + timedelta(days=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # Should get rejected since limit is now 10000.
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + timedelta(days=10),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        value_timestamp=start + timedelta(hours=5),
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "10000"),
                        ],
                    }
                },
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

    def test_min_initial_deposit(self):
        """Check if `minimum_initial_deposit` is respected"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end1 = datetime(year=2019, month=1, day=1, hour=5, tzinfo=timezone.utc)
        end2 = datetime(year=2019, month=1, day=1, hour=10, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["minimum_initial_deposit"] = "1000"
        sub_tests = [
            SubTest(
                description="check early closure fee applied when early closure",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="999.99",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end1: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check early closure fee applied when early closure",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=6),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end2: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "1000"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end2,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_early_account_closure_fee_applied(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=2, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["early_closure_fee"] = "50"
        template_params["early_closure_days"] = "2"

        sub_tests = [
            SubTest(
                description="check early closure fee applied when early closure",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    update_account_status_pending_closure(end, MURABAHAH_ACCOUNT),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (
                                BalanceDimensions(
                                    address="DEFAULT",
                                    asset="COMMERCIAL_BANK_MONEY",
                                    denomination="MYR",
                                    phase="POSTING_PHASE_COMMITTED",
                                ),
                                Decimal("950"),
                            ),
                            (
                                BalanceDimensions(
                                    address="EARLY_CLOSURE_FEE",
                                    asset="COMMERCIAL_BANK_MONEY",
                                    denomination="MYR",
                                    phase="POSTING_PHASE_COMMITTED",
                                ),
                                Decimal("0"),
                            ),
                        ],
                    }
                },
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

    def test_early_account_closure_fee_not_applied_when_closed_after_early_closure_days(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=4, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        template_params["early_closure_fee"] = "50"
        template_params["early_closure_days"] = "2"
        instance_params = default_instance_params.copy()

        sub_tests = [
            SubTest(
                description="check fee not applied when not early closure",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    update_account_status_pending_closure(end, MURABAHAH_ACCOUNT),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (
                                BalanceDimensions(
                                    address="EARLY_CLOSURE_FEE",
                                    asset="COMMERCIAL_BANK_MONEY",
                                    denomination="MYR",
                                    phase="POSTING_PHASE_COMMITTED",
                                ),
                                Decimal("0"),
                            )
                        ],
                    }
                },
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

    def test_max_withdrawal_of_a_payment_type(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        day1 = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)
        day2 = datetime(year=2019, month=1, day=2, hour=23, tzinfo=timezone.utc)
        day3 = datetime(year=2019, month=1, day=3, hour=23, tzinfo=timezone.utc)
        day4 = datetime(year=2019, month=1, day=4, hour=23, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=5, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_deposit"] = "20000"
        template_params["maximum_balance"] = "20000"
        template_params["maximum_daily_withdrawal"] = "20000"
        template_params["maximum_daily_deposit"] = "20000"
        template_params["maximum_withdrawal"] = "6000"
        instance_params["profit_application_day"] = "10"

        sub_tests = [
            SubTest(
                description="check max withdrawal for same payment type respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_VISA"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000.01",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_VISA"},
                    ),
                ],
                expected_balances_at_ts={
                    day1: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "16000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check max withdrawal for different payment type respected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(days=1, hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        event_datetime=start + timedelta(days=1, hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_VISA"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(days=1, hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_VISA"},
                    ),
                ],
                expected_balances_at_ts={
                    day2: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "10500"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check max withdrawal for same payment type on authorisation respected",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        event_datetime=start + timedelta(days=2, hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_VISA"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="60",
                        event_datetime=start + timedelta(days=2, hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_VISA"},
                    ),
                ],
                expected_balances_at_ts={
                    day3: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "10500"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check max withdrawal for same payment type with deposit accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(days=3, hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_VISA"},
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="4500",
                        event_datetime=start + timedelta(days=3, hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_VISA"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="4000",
                        event_datetime=start + timedelta(days=3, hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_VISA"},
                    ),
                ],
                expected_balances_at_ts={
                    day4: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check max withdrawal for same payment type with deposit rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(days=4, hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_VISA"},
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(days=4, hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_VISA"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="4000.01",
                        event_datetime=start + timedelta(days=4, hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_VISA"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "10000"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_handle_payment_type_threshold_fee(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_balance"] = "20000"
        template_params["maximum_daily_withdrawal"] = "20000"
        template_params["maximum_daily_deposit"] = "20000"
        template_params["maximum_deposit"] = "20000"
        template_params["maximum_withdrawal"] = "6000"
        instance_params["profit_application_day"] = "10"

        sub_tests = [
            SubTest(
                description="check payment fee is applied",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="5001",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_POS"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DUITNOW_PROXY"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="5001",
                        event_datetime=start + timedelta(hours=4),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DUITNOW_PROXY"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "4997.50"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_handle_payment_type_limit_fees(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_balance"] = "20000"
        template_params["maximum_daily_withdrawal"] = "20000"
        template_params["maximum_daily_deposit"] = "20000"
        template_params["maximum_deposit"] = "20000"
        template_params["maximum_withdrawal"] = "6000"
        instance_params["profit_application_day"] = "10"

        sub_tests = [
            SubTest(
                description="check payment type fee is applied",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=4),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "349.50"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_handle_payment_type_limit_fees_mix_category(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_balance"] = "20000"
        template_params["maximum_daily_withdrawal"] = "20000"
        template_params["maximum_daily_deposit"] = "20000"
        template_params["maximum_deposit"] = "20000"
        template_params["maximum_withdrawal"] = "6000"
        instance_params["profit_application_day"] = "10"

        sub_tests = [
            SubTest(
                description="check payment type fee is applied",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=4),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "350"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_handle_max_monthly_payment_type_withdrawal_limit_below(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["tiered_profit_rates"] = ZERO_TIERED_PROFIT_RATES
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_withdrawal"] = "20000"
        template_params["maximum_daily_deposit"] = "20000"
        instance_params["profit_application_day"] = "10"
        # MAX_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT is set to 2
        sub_tests = [
            SubTest(
                description="check payment type limit fee was not applied as it was below 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "450"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_handle_max_monthly_payment_type_withdrawal_limit_above(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["tiered_profit_rates"] = ZERO_TIERED_PROFIT_RATES
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_withdrawal"] = "20000"
        template_params["maximum_daily_deposit"] = "20000"
        instance_params["profit_application_day"] = "10"
        # MAX_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT is set to 2
        sub_tests = [
            SubTest(
                description="check 1 payment type limit fee is applied as there is 3 > 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "349.50"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_handle_max_monthly_payment_type_withdrawal_limit_same(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["tiered_profit_rates"] = ZERO_TIERED_PROFIT_RATES
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_withdrawal"] = "20000"
        template_params["maximum_daily_deposit"] = "20000"
        instance_params["profit_application_day"] = "10"
        # MAX_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT is set to 2
        sub_tests = [
            SubTest(
                description="check no payment type limit fee is applied as the count reset",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "400"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_maximum_payment_type_withdrawal(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_withdrawal"] = "2000"

        sub_tests = [
            SubTest(
                description="check min withdrawal respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="250",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="250.01",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="251",
                        event_datetime=start + timedelta(hours=4),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="600",
                        event_datetime=start + timedelta(hours=5),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="200",
                        event_datetime=start + timedelta(hours=6),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "550"),
                        ],
                    }
                },
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

    def test_maximum_payment_type_withdrawal_mix(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        template_params["maximum_daily_withdrawal"] = "2000"

        sub_tests = [
            SubTest(
                description="check min withdrawal respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="250",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "DEBIT_PAYWAVE"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                        instruction_details={"PAYMENT_TYPE": "ATM_ARBM"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "250"),
                        ],
                    }
                },
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

    def test_min_balance(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()

        sub_tests = [
            SubTest(
                description="check min balance repected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + timedelta(hours=1),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + timedelta(hours=2),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                    # Should be rejected as it will bring the balance below min balance
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + timedelta(hours=3),
                        target_account_id=MURABAHAH_ACCOUNT,
                        internal_account_id=DUMMY_DEPOSITING_ACCOUNT,
                        denomination=default_template_params["denomination"],
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        MURABAHAH_ACCOUNT: [
                            (DEFAULT_DIM, "100"),
                        ],
                    }
                },
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
