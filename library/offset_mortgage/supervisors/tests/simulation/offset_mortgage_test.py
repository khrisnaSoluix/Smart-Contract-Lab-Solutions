# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from json import dumps
from time import time

# common
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    SuperviseeConfig,
    SimulationTestScenario,
    SubTest,
    ContractModuleConfig,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.events.plan_events import (
    AccountPlanAssocStatus,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    account_to_simulate,
    create_account_plan_assoc_instruction,
    create_inbound_hard_settlement_instruction,
    create_outbound_hard_settlement_instruction,
    create_outbound_authorisation_instruction,
    create_template_parameter_change_event,
    create_plan_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    create_supervisor_config,
    get_balances,
    SimulationTestCase,
)

SUPERVISOR_CONTRACT_FILE = "library/offset_mortgage/supervisors/offset_mortgage.py"
MORTGAGE_CONTRACT_FILE = "library/mortgage/contracts/mortgage.py"
CASA_CONTRACT_FILE = "library/casa/contracts/casa.py"

CASA_CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "utils": "library/common/contract_modules/utils.py",
    "interest": "library/common/contract_modules/interest.py",
}

MORTGAGE_CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "utils": "library/common/contract_modules/utils.py",
    "amortisation": "library/common/contract_modules/amortisation.py",
}

DEFAULT_DENOMINATION = "GBP"

MORTGAGE_ACCOUNT = "MORTGAGE_ACCOUNT"
DEPOSIT_ACCOUNT = "DEPOSIT_ACCOUNT"

DEFAULT_PENALTY_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DUE_AMOUNT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_FLAG = dumps(["ACCOUNT_DELINQUENT"])
DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_REPAYMENT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])

INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTERNAL_INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT = "PENALTY_INTEREST_RECEIVED"
INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT = "CAPITALISED_INTEREST_RECEIVED"
INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "LATE_REPAYMENT_FEE_INCOME"
INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT = "OVERPAYMENT_ALLOWANCE_FEE_INCOME"

EAS_ACCOUNT = "Easy Access Saver Account"
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
MAINTENANCE_FEE_INCOME_ACCOUNT = "MAINTENANCE_FEE_INCOME"
EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT = "EXCESS_WITHDRAWAL_FEE_INCOME"
MINIMUM_BALANCE_FEE_INCOME_ACCOUNT = "MINIMUM_BALANCE_FEE_INCOME"
DUMMY_DEPOSITING_ACCOUNT = "DUMMY_DEPOSITING_ACCOUNT"

CA_ACCOUNT = "Current Account"
OVERDRAFT_FEE_INCOME_ACCOUNT = "OVERDRAFT_FEE_INCOME"
OVERDRAFT_FEE_RECEIVABLE_ACCOUNT = "OVERDRAFT_FEE_RECEIVABLE"
ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT = "ANNUAL_MAINTENANCE_FEE_INCOME"
INACTIVITY_FEE_INCOME_ACCOUNT = "INACTIVITY_FEE_INCOME"

ASSET = "ASSET"
LIABILITY = "LIABILITY"

DEFAULT_SUPERVISEE_VERSION_IDS = {
    "mortgage": "1000",
    "easy_access_saver": "1001",
    "current_account": "1002",
}

default_internal_accounts = {
    DEPOSIT_ACCOUNT: LIABILITY,
    "1": LIABILITY,
    # Mortgage internal accounts
    INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: ASSET,
    INTERNAL_INTEREST_RECEIVED_ACCOUNT: LIABILITY,
    INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT: LIABILITY,
    INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: LIABILITY,
    INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: LIABILITY,
    INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT: LIABILITY,
    # EAS internal accounts
    EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT: LIABILITY,
    # CA internal accounts
    OVERDRAFT_FEE_INCOME_ACCOUNT: LIABILITY,
    OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: ASSET,
    ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: LIABILITY,
    INACTIVITY_FEE_INCOME_ACCOUNT: LIABILITY,
    # CA and EAS internal accounts
    INTEREST_PAID_ACCOUNT: ASSET,
    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: ASSET,
    INTEREST_RECEIVED_ACCOUNT: LIABILITY,
    ACCRUED_INTEREST_PAYABLE_ACCOUNT: LIABILITY,
    MAINTENANCE_FEE_INCOME_ACCOUNT: LIABILITY,
    MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: LIABILITY,
}

PRINCIPAL = "PRINCIPAL"
PRINCIPAL_CAPITALISED_INTEREST = "PRINCIPAL_CAPITALISED_INTEREST"
ACCRUED_EXPECTED_INTEREST = "ACCRUED_EXPECTED_INTEREST"
CAPITALISED_INTEREST = "CAPITALISED_INTEREST"
INTEREST_DUE = "INTEREST_DUE"
PRINCIPAL_DUE = "PRINCIPAL_DUE"
OVERPAYMENT = "OVERPAYMENT"
EMI_PRINCIPAL_EXCESS = "EMI_PRINCIPAL_EXCESS"
INTEREST_OVERDUE = "INTEREST_OVERDUE"
PRINCIPAL_OVERDUE = "PRINCIPAL_OVERDUE"
PENALTIES = "PENALTIES"
EMI_ADDRESS = "EMI"
ACCRUED_INTEREST = "ACCRUED_INTEREST"
INTERNAL_CONTRA = "INTERNAL_CONTRA"

PRINCIPAL_DIMENSION = BalanceDimensions(address=PRINCIPAL)
ACCRUED_EXPECTED_INTEREST_DIMENSION = BalanceDimensions(address=ACCRUED_EXPECTED_INTEREST)
ACCRUED_INTEREST_DIMENSION = BalanceDimensions(address=ACCRUED_INTEREST)
INTEREST_DUE_DIMENSION = BalanceDimensions(address=INTEREST_DUE)
PRINCIPAL_DUE_DIMENSION = BalanceDimensions(address=PRINCIPAL_DUE)
OVERPAYMENT_DIMENSION = BalanceDimensions(address=OVERPAYMENT)
EMI_PRINCIPAL_EXCESS_DIMENSION = BalanceDimensions(address=EMI_PRINCIPAL_EXCESS)
INTEREST_OVERDUE_DIMENSION = BalanceDimensions(address=INTEREST_OVERDUE)
PRINCIPAL_OVERDUE_DIMENSION = BalanceDimensions(address=PRINCIPAL_OVERDUE)
PENALTIES_DIMENSION = BalanceDimensions(address=PENALTIES)
EMI_ADDRESS_DIMENSION = BalanceDimensions(address=EMI_ADDRESS)
INTERNAL_CONTRA_DIMENSION = BalanceDimensions(address=INTERNAL_CONTRA)
DEFAULT_DIMENSION = BalanceDimensions()

# Current Account
ACCRUED_DEPOSIT_RECEIVABLE_DIMENSION = BalanceDimensions(address="ACCRUED_DEPOSIT_RECEIVABLE")
ACCRUED_DEPOSIT_PAYABLE_DIMENSION = BalanceDimensions(address="ACCRUED_DEPOSIT_PAYABLE")
ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSION = BalanceDimensions(address="ACCRUED_OVERDRAFT_RECEIVABLE")

INTERNAL_CONTRA_DIM = BalanceDimensions(address="INTERNAL_CONTRA")

default_simulation_start_date = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)

default_mortgage_instance_params = {
    "fixed_interest_rate": "0.129971",
    "fixed_interest_term": "0",
    "total_term": "120",
    "overpayment_fee_percentage": "0.05",
    "interest_only_term": "0",
    "principal": "300000",
    "repayment_day": "12",
    "deposit_account": DEPOSIT_ACCOUNT,
    "overpayment_percentage": "0.1",
    "variable_rate_adjustment": "0",
    "mortgage_start_date": str(default_simulation_start_date.date()),
}

default_mortgage_template_params = {
    "variable_interest_rate": "0.032",
    "denomination": "GBP",
    "late_repayment_fee": "15",
    "penalty_interest_rate": "0.24",
    "penalty_includes_base_rate": "True",
    "grace_period": "5",
    "penalty_blocking_flags": DEFAULT_PENALTY_BLOCKING_FLAG,
    "due_amount_blocking_flags": DEFAULT_DUE_AMOUNT_BLOCKING_FLAG,
    "delinquency_blocking_flags": DEFAULT_DELINQUENCY_BLOCKING_FLAG,
    "delinquency_flags": DEFAULT_DELINQUENCY_FLAG,
    "overdue_amount_blocking_flags": DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG,
    "repayment_blocking_flags": DEFAULT_REPAYMENT_BLOCKING_FLAG,
    "accrued_interest_receivable_account": INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    "capitalised_interest_received_account": INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
    "interest_received_account": INTERNAL_INTEREST_RECEIVED_ACCOUNT,
    "penalty_interest_received_account": INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT,
    "late_repayment_fee_income_account": INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
    "overpayment_allowance_fee_income_account": INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT,
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "overpayment_impact_preference": "reduce_term",
    "accrue_interest_hour": "0",
    "accrue_interest_minute": "0",
    "accrue_interest_second": "1",
    "check_delinquency_hour": "0",
    "check_delinquency_minute": "0",
    "check_delinquency_second": "2",
    "repayment_hour": "0",
    "repayment_minute": "1",
    "repayment_second": "0",
    "overpayment_hour": "0",
    "overpayment_minute": "0",
    "overpayment_second": "0",
}

BALANCE_TIER_RANGES = dumps(
    {
        "tier1": {"min": "0"},
        "tier2": {"min": "15000.00"},
    }
)
TIERED_INTEREST_RATES = dumps({"tier1": "0.149", "tier2": "-0.1485"})
TIERED_MIN_BALANCE_THRESHOLD = dumps(
    {
        "CASA_TIER_UPPER": "25",
        "CASA_TIER_MIDDLE": "75",
        "CASA_TIER_LOWER": "100",
    }
)
ACCOUNT_TIER_NAMES = dumps(
    [
        "CASA_TIER_UPPER",
        "CASA_TIER_MIDDLE",
        "CASA_TIER_LOWER",
    ]
)
ZERO_TIERED_INTEREST_RATES = dumps({"tier1": "0", "tier2": "0"})
NEGATIVE_TIERED_INTEREST_RATES = dumps({"tier1": "-0.149", "tier2": "-0.1485"})

default_eas_instance_params = {
    "arranged_overdraft_limit": "0",
    "unarranged_overdraft_limit": "0",
    "interest_application_day": "5",
    "daily_atm_withdrawal_limit": "0",
    "autosave_savings_account": "",
}

default_eas_template_params = {
    "denomination": "GBP",
    "additional_denominations": dumps([]),
    "deposit_tier_ranges": BALANCE_TIER_RANGES,
    "deposit_interest_rate_tiers": TIERED_INTEREST_RATES,
    "minimum_deposit": "100",
    "maximum_daily_deposit": "1000000",
    "minimum_withdrawal": "0.01",
    "maximum_daily_withdrawal": "10000",
    "maximum_balance": "10000000",
    "accrued_interest_payable_account": ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    "interest_paid_account": INTEREST_PAID_ACCOUNT,
    "accrued_interest_receivable_account": ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    "interest_received_account": INTEREST_RECEIVED_ACCOUNT,
    "maintenance_fee_income_account": MAINTENANCE_FEE_INCOME_ACCOUNT,
    "annual_maintenance_fee_income_account": ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
    "inactivity_fee_income_account": INACTIVITY_FEE_INCOME_ACCOUNT,
    "excess_withdrawal_fee_income_account": EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
    "minimum_balance_fee_income_account": MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
    "interest_accrual_days_in_year": "365",
    "interest_accrual_hour": "0",
    "interest_accrual_minute": "0",
    "interest_accrual_second": "0",
    "interest_application_hour": "0",
    "interest_application_minute": "1",
    "interest_application_second": "0",
    "deposit_interest_application_frequency": "monthly",
    "monthly_withdrawal_limit": "5",
    "reject_excess_withdrawals": "true",
    "excess_withdrawal_fee": "10",
    "account_inactivity_fee": "0",
    "maintenance_fee_annual": "0",
    "maintenance_fee_monthly": "0",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "minimum_balance_threshold": TIERED_MIN_BALANCE_THRESHOLD,
    "minimum_balance_fee": "0",
    "account_tier_names": ACCOUNT_TIER_NAMES,
    "interest_free_buffer": dumps(
        {
            "CASA_TIER_UPPER": "0",
            "CASA_TIER_MIDDLE": "0",
            "CASA_TIER_LOWER": "0",
        }
    ),
    "overdraft_interest_free_buffer_days": dumps(
        {
            "CASA_TIER_UPPER": "0",
            "CASA_TIER_MIDDLE": "0",
            "CASA_TIER_LOWER": "0",
        }
    ),
    "overdraft_interest_rate": "0",
    "unarranged_overdraft_fee": "0",
    "unarranged_overdraft_fee_cap": "0",
    "maximum_daily_atm_withdrawal_limit": dumps(
        {
            "CASA_TIER_UPPER": "0",
            "CASA_TIER_MIDDLE": "0",
            "CASA_TIER_LOWER": "0",
        }
    ),
    "transaction_code_to_type_map": dumps({"": "purchase", "6011": "ATM withdrawal"}),
    "autosave_rounding_amount": "0.00",
    "overdraft_fee_income_account": OVERDRAFT_FEE_INCOME_ACCOUNT,
    "overdraft_fee_receivable_account": OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
}

default_ca_template_params = {
    "denomination": "GBP",
    "additional_denominations": dumps(["USD", "EUR"]),
    "account_tier_names": dumps(
        [
            "CASA_TIER_UPPER",
            "CASA_TIER_MIDDLE",
            "CASA_TIER_LOWER",
        ]
    ),
    "deposit_interest_application_frequency": "monthly",
    "interest_accrual_days_in_year": "365",
    "interest_free_buffer": dumps(
        {
            "CASA_TIER_UPPER": "500",
            "CASA_TIER_MIDDLE": "300",
            "CASA_TIER_LOWER": "50",
        }
    ),
    "overdraft_interest_free_buffer_days": dumps(
        {
            "CASA_TIER_UPPER": "-1",
            "CASA_TIER_MIDDLE": "21",
            "CASA_TIER_LOWER": "-1",
        }
    ),
    "overdraft_interest_rate": "0.1485",
    "unarranged_overdraft_fee": "5",
    "unarranged_overdraft_fee_cap": "80",
    "interest_application_hour": "0",
    "interest_application_minute": "1",
    "interest_application_second": "0",
    "interest_accrual_hour": "0",
    "interest_accrual_minute": "0",
    "interest_accrual_second": "0",
    "accrued_interest_receivable_account": ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    "interest_received_account": INTEREST_RECEIVED_ACCOUNT,
    "accrued_interest_payable_account": ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    "interest_paid_account": INTEREST_PAID_ACCOUNT,
    "overdraft_fee_income_account": OVERDRAFT_FEE_INCOME_ACCOUNT,
    "overdraft_fee_receivable_account": OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
    "maintenance_fee_income_account": MAINTENANCE_FEE_INCOME_ACCOUNT,
    "minimum_balance_fee_income_account": MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
    "annual_maintenance_fee_income_account": ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
    "inactivity_fee_income_account": INACTIVITY_FEE_INCOME_ACCOUNT,
    "maintenance_fee_annual": "0",
    "maintenance_fee_monthly": "0",
    "minimum_balance_threshold": dumps(
        {
            "CASA_TIER_UPPER": "25",
            "CASA_TIER_MIDDLE": "75",
            "CASA_TIER_LOWER": "100",
        }
    ),
    "minimum_balance_fee": "0",
    "account_inactivity_fee": "0",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "maximum_daily_atm_withdrawal_limit": dumps(
        {
            "CASA_TIER_UPPER": "5000",
            "CASA_TIER_MIDDLE": "2000",
            "CASA_TIER_LOWER": "1000",
        }
    ),
    "transaction_code_to_type_map": dumps({"": "purchase", "6011": "ATM withdrawal"}),
    "deposit_tier_ranges": dumps(
        {
            "tier1": {"min": "0"},
            "tier2": {"min": "3000.00"},
            "tier3": {"min": "5000.00"},
            "tier4": {"min": "7500.00"},
            "tier5": {"min": "15000.00"},
        }
    ),
    "deposit_interest_rate_tiers": dumps(
        {
            "tier1": "0.05",
            "tier2": "0.04",
            "tier3": "0.02",
            "tier4": "0",
            "tier5": "-0.035",
        }
    ),
    "autosave_rounding_amount": "1.00",
    "minimum_deposit": "100",
    "maximum_daily_deposit": "1000000",
    "minimum_withdrawal": "0.01",
    "maximum_daily_withdrawal": "10000",
    "maximum_balance": "10000000",
    "monthly_withdrawal_limit": "-1",
    "reject_excess_withdrawals": "false",
    "excess_withdrawal_fee": "0",
    "excess_withdrawal_fee_income_account": EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
}
default_ca_instance_params = {
    "arranged_overdraft_limit": "10000",
    "unarranged_overdraft_limit": "20000",
    "interest_application_day": "1",
    "daily_atm_withdrawal_limit": "1000",
    "autosave_savings_account": "",
}


class OffsetMortgageSupervisorTest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.mortgage_contract = MORTGAGE_CONTRACT_FILE
        cls.eas_contract = CASA_CONTRACT_FILE
        cls.ca_contract = CASA_CONTRACT_FILE
        cls.casa_contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CASA_CONTRACT_MODULES_ALIAS_FILE_MAP.items()
        ]
        cls.mortgage_contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in MORTGAGE_CONTRACT_MODULES_ALIAS_FILE_MAP.items()
        ]
        supervisor_contract = SUPERVISOR_CONTRACT_FILE

        with open(supervisor_contract, encoding="utf-8") as smart_contract_file:
            cls.supervisor_contract_contents = smart_contract_file.read()

        cls.load_test_config()

    def setUp(self):
        self._started_at = time()

    def tearDown(self):
        self._elapsed_time = time() - self._started_at
        print("{} ({}s)".format(self.id().rpartition(".")[2], round(self._elapsed_time, 2)))

    def _get_default_supervisor_config(
        self,
        mortgage_instance_params=default_mortgage_instance_params,
        mortgage_template_params=default_mortgage_template_params,
        mortgage_instances=1,
        eas_instance_params=default_eas_instance_params,
        eas_template_params=default_eas_template_params,
        eas_instances=1,
        ca_instance_params=default_ca_instance_params,
        ca_template_params=default_ca_template_params,
        ca_instances=1,
    ):

        mortgage_supervisee = SuperviseeConfig(
            contract_id="mortgage",
            contract_file=MORTGAGE_CONTRACT_FILE,
            account_name=MORTGAGE_ACCOUNT,
            version=DEFAULT_SUPERVISEE_VERSION_IDS["mortgage"],
            instance_parameters=mortgage_instance_params,
            template_parameters=mortgage_template_params,
            instances=mortgage_instances,
            linked_contract_modules=self.mortgage_contract_modules,
        )
        eas_supervisee = SuperviseeConfig(
            contract_id="easy_access_saver",
            contract_file=CASA_CONTRACT_FILE,
            account_name=EAS_ACCOUNT,
            version=DEFAULT_SUPERVISEE_VERSION_IDS["easy_access_saver"],
            instance_parameters=eas_instance_params,
            template_parameters=eas_template_params,
            instances=eas_instances,
            linked_contract_modules=self.casa_contract_modules,
        )
        ca_supervisee = SuperviseeConfig(
            contract_id="current_account",
            contract_file=CASA_CONTRACT_FILE,
            account_name=CA_ACCOUNT,
            version=DEFAULT_SUPERVISEE_VERSION_IDS["current_account"],
            instance_parameters=ca_instance_params,
            template_parameters=ca_template_params,
            instances=ca_instances,
            linked_contract_modules=self.casa_contract_modules,
        )

        supervisor_config = create_supervisor_config(
            SUPERVISOR_CONTRACT_FILE,
            "supervisor version 1",
            [
                mortgage_supervisee,
                eas_supervisee,
                ca_supervisee,
            ],
        )

        return supervisor_config

    def test_daily_offset_accrual_multiple_eas(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = datetime(year=2021, month=5, day=12, hour=23, minute=59, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="deposit into savings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{EAS_ACCOUNT} 0",
                        internal_account_id="1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{EAS_ACCOUNT} 1",
                        internal_account_id="1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{EAS_ACCOUNT} 2",
                        internal_account_id="1",
                    ),
                ],
            ),
            SubTest(
                description="1st interest accrual day",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "23.67122"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{EAS_ACCOUNT} 2": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2219.72"),
                            (INTEREST_DUE_DIMENSION, "994.19"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{EAS_ACCOUNT} 2": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3213.91",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{MORTGAGE_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "23.47662"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.11644"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{EAS_ACCOUNT} 2": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with 1 savings withdrawn)",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{EAS_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "47.82995"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.23288"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{EAS_ACCOUNT} 2": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2243.58"),
                            (INTEREST_DUE_DIMENSION, "681.02"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{EAS_ACCOUNT} 2": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd interest accrual day after repayment (with all savings withdrawn)",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3213.91",
                        event_datetime=datetime(2021, 3, 12, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{MORTGAGE_ACCOUNT} 0",
                        internal_account_id="1",
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 3, 13, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{EAS_ACCOUNT} 1",
                        internal_account_id="1",
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 3, 13, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{EAS_ACCOUNT} 2",
                        internal_account_id="1",
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2021, 3, 14, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "50.01596"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "51.8483"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 2": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 4, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2123.93"),
                            (INTEREST_DUE_DIMENSION, "800.67"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 2": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(eas_instances=3),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_accrual_multiple_offset_accounts(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = datetime(year=2021, month=5, day=12, hour=23, minute=59, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="deposit into savings and current account, withdraw from one ca",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{EAS_ACCOUNT} 0",
                        internal_account_id="1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{EAS_ACCOUNT} 1",
                        internal_account_id="1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{CA_ACCOUNT} 0",
                        internal_account_id="1",
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="8000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{CA_ACCOUNT} 1",
                        internal_account_id="1",
                    ),
                ],
            ),
            SubTest(
                description="1st interest accrual day",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "23.67122"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{CA_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSION, "-3.23445"),
                            (DEFAULT_DIMENSION, "-8000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2219.72"),
                            (INTEREST_DUE_DIMENSION, "994.19"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{CA_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSION, "-36.02775"),
                            (DEFAULT_DIMENSION, "-8100.27"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3213.91",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{MORTGAGE_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "23.47662"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.11644"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{CA_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSION, "-39.303"),
                            (DEFAULT_DIMENSION, "-8100.27"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with 1 savings withdrawn)",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{EAS_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "47.82995"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.23288"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{CA_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSION, "-42.57825"),
                            (DEFAULT_DIMENSION, "-8100.27"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2243.58"),
                            (INTEREST_DUE_DIMENSION, "681.02"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                        f"{CA_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSION, "-36.43816"),
                            (DEFAULT_DIMENSION, "-8191.98"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd interest accrual day after repayment (with all savings withdrawn)",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3213.91",
                        event_datetime=datetime(2021, 3, 12, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{MORTGAGE_ACCOUNT} 0",
                        internal_account_id="1",
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 3, 13, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{EAS_ACCOUNT} 1",
                        internal_account_id="1",
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 3, 13, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{CA_ACCOUNT} 0",
                        internal_account_id="1",
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2021, 3, 14, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "50.01596"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "51.8483"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSION, "-43.06328"),
                            (DEFAULT_DIMENSION, "-8191.98"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 4, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2123.93"),
                            (INTEREST_DUE_DIMENSION, "800.67"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 1": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSION, "-36.89774"),
                            (DEFAULT_DIMENSION, "-8294.67"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(eas_instances=2, ca_instances=2),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=timezone.utc)
        sub_tests = [
            SubTest(
                description="deposit into savings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{EAS_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.42465"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    },
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2146.07"),
                            (INTEREST_DUE_DIMENSION, "1067.84"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3213.91",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{MORTGAGE_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.2365"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.11644"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="withdraw from savings",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{EAS_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with savings withdrawn)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "51.34971"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.23288"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2194.31"),
                            (INTEREST_DUE_DIMENSION, "730.29"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(eas_instances=3),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual_with_overpayment(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="deposit into savings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{EAS_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                # interest = 3.2% (25.42 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.42465"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2146.07"),
                            (INTEREST_DUE_DIMENSION, "1067.84"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount with overpayment",
                # (overpayment 10000 + 3213.91 due)
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="13213.91",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{MORTGAGE_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "24.35979"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.11644"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="withdraw from savings",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{EAS_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with savings withdrawn)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "49.59629"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.23288"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2218.85"),
                            (INTEREST_DUE_DIMENSION, "705.75"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual_with_rate_change(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="deposit into savings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{EAS_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                # interest = 3.2% (25.42 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.42465"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="rate change ready for next interest accrual period",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=2),
                        smart_contract_version_id=DEFAULT_SUPERVISEE_VERSION_IDS["mortgage"],
                        variable_interest_rate="0.02",
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day includes discounted interest",
                # interest = 3.2% (25.42 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 3, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "50.8493"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.60272"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd interest accrual day includes discounted interest + "
                + "variable rate change",
                # interest = 2% (15.89 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 4, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "66.73971"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "69.04107"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2274.48"),
                            (INTEREST_DUE_DIMENSION, "686.47"),
                            (EMI_ADDRESS_DIMENSION, "2760.4"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2960.95",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{MORTGAGE_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "15.76578"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "16.31502"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="withdraw from savings",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{EAS_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with savings withdrawn)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "32.0795"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "32.63004"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2304.16"),
                            (INTEREST_DUE_DIMENSION, "456.24"),
                            (EMI_ADDRESS_DIMENSION, "2760.4"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual_with_eas_pending_out(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = datetime(year=2021, month=2, day=12, hour=23, minute=59, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="deposit into savings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{EAS_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="dcreate pending withdrawal",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(days=2),
                        target_account_id=f"{EAS_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.42465"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 3, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "50.8493"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.60272"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd interest accrual day includes discounted interest + "
                + "pending EAS withdrawal",
                expected_balances_at_ts={
                    datetime(2021, 1, 4, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "77.15066"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "78.90408"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2111.01"),
                            (INTEREST_DUE_DIMENSION, "1102.9"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st interest accrual day after includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.42465"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 3, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "50.8493"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.60272"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual_with_eas_monthly_fee_application(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=timezone.utc)

        eas_template_params = deepcopy(default_eas_template_params)
        eas_template_params["maintenance_fee_monthly"] = "200"

        sub_tests = [
            SubTest(
                description="deposit into savings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{EAS_ACCOUNT} 0",
                        internal_account_id="1",
                    ),
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.42465"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2145.88"),
                            (INTEREST_DUE_DIMENSION, "1068.03"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "9800"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3213.91",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{MORTGAGE_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment "
                + "(and EAS monthly fee applied)",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.25405"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.11644"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "9800"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd interest accrual day after repayment "
                + "(and EAS monthly fee applied)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "50.5081"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.23288"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "9800"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2217.29"),
                            (INTEREST_DUE_DIMENSION, "707.31"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{EAS_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "9600"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                eas_template_params=eas_template_params
            ),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_eas_supervisee_only_commits_interest_accruals_no_offset(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = start + timedelta(minutes=5)

        expected_balances = {
            MORTGAGE_ACCOUNT: {
                end: [
                    (ACCRUED_INTEREST_DIMENSION, "26.30136"),
                    (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                ]
            },
            EAS_ACCOUNT: {
                end: [
                    (DEFAULT_DIMENSION, "1000"),
                    (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0.40822"),
                ]
            },
        }

        mortgage_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            contract_version_id=DEFAULT_SUPERVISEE_VERSION_IDS["mortgage"],
            instance_params=default_mortgage_instance_params,
            template_params=default_mortgage_template_params,
            contract_file_path=self.mortgage_contract,
        )

        eas_account = account_to_simulate(
            timestamp=start,
            account_id=EAS_ACCOUNT,
            contract_version_id=DEFAULT_SUPERVISEE_VERSION_IDS["easy_access_saver"],
            instance_params=default_eas_instance_params,
            template_params=default_eas_template_params,
            contract_file_path=self.eas_contract,
        )

        ca_account = account_to_simulate(
            timestamp=start,
            account_id=CA_ACCOUNT,
            contract_version_id=DEFAULT_SUPERVISEE_VERSION_IDS["current_account"],
            instance_params=default_ca_instance_params,
            template_params=default_ca_template_params,
            contract_file_path=self.ca_contract,
        )

        events = []
        events.append(
            create_plan_instruction(
                timestamp=start,
                plan_id="1",
                supervisor_contract_version_id="Supervisor version 1",
            )
        )
        events.append(
            create_account_plan_assoc_instruction(
                timestamp=start + timedelta(seconds=6),
                assoc_id="Supervised " + EAS_ACCOUNT,
                account_id=EAS_ACCOUNT,
                plan_id="1",
                status=AccountPlanAssocStatus.ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE,
            )
        )
        events.append(
            create_inbound_hard_settlement_instruction(
                event_datetime=start + timedelta(seconds=10),
                amount="1000",
                denomination=DEFAULT_DENOMINATION,
                target_account_id=EAS_ACCOUNT,
                internal_account_id="1",
            )
        )

        res = self.client.simulate_smart_contract(
            supervisor_contract_config=self._get_default_supervisor_config(
                ca_instances=0,
            ),
            supervisor_contract_code=self.supervisor_contract_contents,
            supervisor_contract_version_id="Supervisor version 1",
            supervisee_version_id_mapping=DEFAULT_SUPERVISEE_VERSION_IDS,
            account_creation_events=[mortgage_account, eas_account, ca_account],
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        balances = get_balances(res)
        print(balances[EAS_ACCOUNT])

        self.check_balances(expected_balances=expected_balances, actual_balances=balances)

    def test_daily_ca_offset_accrual(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="deposit into current account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{CA_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.42465"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2146.07"),
                            (INTEREST_DUE_DIMENSION, "1067.84"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3213.91",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{MORTGAGE_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.2365"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.11644"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="withdraw from current account",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{CA_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with savings withdrawn)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "51.34971"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.23288"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2194.31"),
                            (INTEREST_DUE_DIMENSION, "730.29"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_ca_offset_accrual_with_overpayment(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="deposit into current account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{CA_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                # interest = 3.2% (25.42 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.42465"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2146.07"),
                            (INTEREST_DUE_DIMENSION, "1067.84"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount with overpayment",
                # (overpayment 10000 + 3213.91 due)
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="13213.91",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{MORTGAGE_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "24.35979"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.11644"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="withdraw from current account",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{CA_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with amount withdrawn)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "49.59629"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.23288"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2218.85"),
                            (INTEREST_DUE_DIMENSION, "705.75"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_ca_offset_accrual_with_rate_change(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="deposit into current account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{CA_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                # interest = 3.2% (25.42 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.42465"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="rate change ready for next interest accrual period",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=2),
                        smart_contract_version_id=DEFAULT_SUPERVISEE_VERSION_IDS["mortgage"],
                        variable_interest_rate="0.02",
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day includes discounted interest",
                # interest = 3.2% (25.42 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 3, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "50.8493"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.60272"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd interest accrual day includes discounted interest + "
                + "variable rate change",
                # interest = 2% (15.89 per day)
                expected_balances_at_ts={
                    datetime(2021, 1, 4, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "66.73971"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "69.04107"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2274.48"),
                            (INTEREST_DUE_DIMENSION, "686.47"),
                            (EMI_ADDRESS_DIMENSION, "2760.4"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2960.95",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{MORTGAGE_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "15.76578"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "16.31502"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="withdraw from current account",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2021, 2, 13, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{CA_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day after repayment (with savings withdrawn)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "32.0795"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "32.63004"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2304.16"),
                            (INTEREST_DUE_DIMENSION, "456.24"),
                            (EMI_ADDRESS_DIMENSION, "2760.4"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual_with_ca_pending_out(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = datetime(year=2021, month=2, day=12, hour=23, minute=59, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="deposit into current account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{CA_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.42465"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="create pending withdrawal",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(days=2),
                        target_account_id=f"{CA_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="2nd interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 3, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "50.8493"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.60272"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="3rd interest accrual day includes discounted interest + pending "
                + "CA withdrawal",
                expected_balances_at_ts={
                    datetime(2021, 1, 4, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "77.15066"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "78.90408"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2111.01"),
                            (INTEREST_DUE_DIMENSION, "1102.9"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st interest accrual day after includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.42465"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd interest accrual day includes discounted interest",
                expected_balances_at_ts={
                    datetime(2021, 1, 3, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "50.8493"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.60272"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_offset_accrual_with_ca_monthly_fee_application(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = datetime(year=2021, month=3, day=12, hour=23, minute=59, tzinfo=timezone.utc)

        eas_template_params = deepcopy(default_eas_template_params)
        ca_template_params = deepcopy(default_ca_template_params)
        ca_template_params["maintenance_fee_monthly"] = "200"

        sub_tests = [
            SubTest(
                description="deposit into current account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=start + timedelta(seconds=10),
                        target_account_id=f"{CA_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day",
                expected_balances_at_ts={
                    datetime(2021, 1, 2, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.42465"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "10000"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 2, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2145.88"),
                            (INTEREST_DUE_DIMENSION, "1068.03"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "9800"),
                        ],
                    }
                },
            ),
            SubTest(
                description="pay 1st mortgage due amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3213.91",
                        event_datetime=datetime(2021, 2, 12, 12, 30, 0, tzinfo=timezone.utc),
                        target_account_id=f"{MORTGAGE_ACCOUNT} 0",
                        internal_account_id="1",
                    )
                ],
            ),
            SubTest(
                description="1st interest accrual day after repayment (and CA monthly fee applied)",
                expected_balances_at_ts={
                    datetime(2021, 2, 13, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "25.25405"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.11644"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "9800"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd interest accrual day after repayment (and CA monthly fee applied)",
                expected_balances_at_ts={
                    datetime(2021, 2, 14, 0, 0, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "50.5081"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "52.23288"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (INTEREST_DUE_DIMENSION, "0"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "9800"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd mortgage transfer due day",
                expected_balances_at_ts={
                    datetime(2021, 3, 12, 0, 1, 1, tzinfo=timezone.utc): {
                        f"{MORTGAGE_ACCOUNT} 0": [
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "2217.29"),
                            (INTEREST_DUE_DIMENSION, "707.31"),
                            (EMI_ADDRESS_DIMENSION, "2924.6"),
                        ],
                        f"{CA_ACCOUNT} 0": [
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "9600"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                eas_template_params=eas_template_params,
                ca_template_params=ca_template_params,
            ),
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_ca_supervisee_only_commits_interest_accruals_no_offset(self):
        start = datetime(year=2021, month=1, day=1, hour=23, minute=59, tzinfo=timezone.utc)
        end = start + timedelta(minutes=5)

        expected_balances = {
            MORTGAGE_ACCOUNT: {
                end: [
                    (ACCRUED_INTEREST_DIMENSION, "26.30136"),
                    (ACCRUED_EXPECTED_INTEREST_DIMENSION, "26.30136"),
                ]
            },
            CA_ACCOUNT: {
                start
                + timedelta(seconds=10): [
                    (DEFAULT_DIMENSION, "1000"),
                    (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0"),
                ],
                end: [
                    (DEFAULT_DIMENSION, "1000"),
                    (ACCRUED_DEPOSIT_PAYABLE_DIMENSION, "0.13699"),
                ],
            },
        }

        mortgage_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            contract_version_id=DEFAULT_SUPERVISEE_VERSION_IDS["mortgage"],
            instance_params=default_mortgage_instance_params,
            template_params=default_mortgage_template_params,
            contract_file_path=self.mortgage_contract,
        )

        eas_account = account_to_simulate(
            timestamp=start,
            account_id=EAS_ACCOUNT,
            contract_version_id=DEFAULT_SUPERVISEE_VERSION_IDS["easy_access_saver"],
            instance_params=default_eas_instance_params,
            template_params=default_eas_template_params,
            contract_file_path=self.eas_contract,
        )

        ca_account = account_to_simulate(
            timestamp=start,
            account_id=CA_ACCOUNT,
            contract_version_id=DEFAULT_SUPERVISEE_VERSION_IDS["current_account"],
            instance_params=default_ca_instance_params,
            template_params=default_ca_template_params,
            contract_file_path=self.ca_contract,
        )

        events = []
        events.append(
            create_plan_instruction(
                timestamp=start,
                plan_id="1",
                supervisor_contract_version_id="Supervisor version 1",
            )
        )
        events.append(
            create_account_plan_assoc_instruction(
                timestamp=start + timedelta(seconds=6),
                assoc_id="Supervised " + CA_ACCOUNT,
                account_id=CA_ACCOUNT,
                plan_id="1",
                status=AccountPlanAssocStatus.ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE,
            )
        )
        events.append(
            create_inbound_hard_settlement_instruction(
                event_datetime=start + timedelta(seconds=10),
                amount="1000",
                denomination=DEFAULT_DENOMINATION,
                target_account_id=CA_ACCOUNT,
                internal_account_id="1",
            )
        )

        res = self.client.simulate_smart_contract(
            supervisor_contract_config=self._get_default_supervisor_config(
                eas_instances=0,
            ),
            supervisor_contract_code=self.supervisor_contract_contents,
            supervisor_contract_version_id="Supervisor version 1",
            supervisee_version_id_mapping=DEFAULT_SUPERVISEE_VERSION_IDS,
            account_creation_events=[mortgage_account, eas_account, ca_account],
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        balances = get_balances(res)
        self.check_balances(expected_balances=expected_balances, actual_balances=balances)
