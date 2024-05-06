# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta as timedelta
from json import dumps
from time import time
from uuid import uuid4

# common
from inception_sdk.common.python.file_utils import load_file_contents
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractModuleConfig,
    SimulationTestScenario,
    SubTest,
    SuperviseeConfig,
    SupervisorConfig,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_instruction,
    create_account_plan_assoc_instruction,
    create_auth_adjustment_instruction,
    create_custom_instruction,
    create_flag_definition_event,
    create_flag_event,
    create_inbound_authorisation_instruction,
    create_inbound_hard_settlement_instruction,
    create_outbound_authorisation_instruction,
    create_outbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_template_parameter_change_event,
    create_plan_instruction,
    create_posting_instruction_batch,
    create_release_event,
    create_settlement_event,
    create_transfer_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    create_supervisor_config,
    ExpectedRejection,
    get_balances,
    get_processed_scheduled_events,
    SimulationTestCase,
)
from inception_sdk.vault.postings.posting_classes import OutboundHardSettlement

CHECKING_CONTRACT_FILE = "library/us_products/contracts/us_checking_account.py"
SAVINGS_CONTRACT_FILE = "library/us_products/contracts/us_savings_account.py"
SUPERVISOR_CONTRACT_FILE = "library/savings_sweep/supervisors/savings_sweep.py"
ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"
CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "interest": "library/common/contract_modules/interest.py",
    "utils": "library/common/contract_modules/utils.py",
}

CHECKING_ACCOUNT = "Checking Acoount"
SAVINGS_ACCOUNT = "Savings Account"
CHECKING_ACCOUNT_PRODUCT_VERSION_ID = "1"
SAVINGS_ACCOUNT_PRODUCT_VERSION_ID = "2"

DEFAULT_DENOMINATION = "USD"
DEFAULT_CLIENT_BATCH_ID = str(uuid4())
DORMANCY_FLAG = "ACCOUNT_DORMANT"

DEFAULT_USD_DIMENSION = BalanceDimensions(denomination=DEFAULT_DENOMINATION)
NON_DEFAULT_USD_DIMENSION = BalanceDimensions(address="NON_DEFAULT_ADDRESS", denomination="USD")

DEFAULT_EUR_DIMENSION = BalanceDimensions(denomination="EUR")

ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
MAINTENANCE_FEE_INCOME_ACCOUNT = "MAINTENANCE_FEE_INCOME"
EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT = "EXCESS_WITHDRAWAL_FEE_INCOME"
MINIMUM_BALANCE_FEE_INCOME_ACCOUNT = "MINIMUM_BALANCE_FEE_INCOME"
OVERDRAFT_FEE_INCOME_ACCOUNT = "OVERDRAFT_FEE_INCOME"
OVERDRAFT_FEE_RECEIVABLE_ACCOUNT = "OVERDRAFT_FEE_RECEIVABLE"
ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT = "ANNUAL_MAINTENANCE_FEE_INCOME"
INACTIVITY_FEE_INCOME_ACCOUNT = "INACTIVITY_FEE_INCOME"
PROMOTIONAL_MAINTENANCE_FEE = "PROMOTIONAL_MAINTENANCE_FEE"
INTERNAL_CONTRA = "INTERNAL_CONTRA"

default_checking_instance_params = {
    "fee_free_overdraft_limit": "1000",
    "standard_overdraft_limit": "2000",
    "interest_application_day": "1",
    "daily_atm_withdrawal_limit": "1000",
}
default_checking_template_params = {
    "denomination": "USD",
    "additional_denominations": dumps(["USD," "EUR"]),
    "tier_names": dumps(
        [
            "US_CHECKING_ACCOUNT_TIER_UPPER",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE",
            "US_CHECKING_ACCOUNT_TIER_LOWER",
        ]
    ),
    "deposit_interest_application_frequency": "monthly",
    "interest_accrual_days_in_year": "365",
    "interest_free_buffer": dumps(
        {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "500",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "300",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "50",
        }
    ),
    "overdraft_interest_free_buffer_days": dumps(
        {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "-1",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "21",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "-1",
        }
    ),
    "overdraft_interest_rate": "0.1485",
    "standard_overdraft_per_transaction_fee": "0",
    "standard_overdraft_daily_fee": "5",
    "standard_overdraft_fee_cap": "80",
    "savings_sweep_fee": "12",
    "savings_sweep_fee_cap": "1",
    "savings_sweep_transfer_unit": "0",
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
    "maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "0"}),
    "promotional_maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "0"}),
    "minimum_balance_threshold": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "1500"}),
    "minimum_combined_balance_threshold": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "5000"}),
    "minimum_deposit_threshold": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "500"}),
    "minimum_balance_fee": "0",
    "account_inactivity_fee": "0",
    "fees_application_day": "1",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "maximum_daily_atm_withdrawal_limit": dumps(
        {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "5000",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "2000",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "1000",
        }
    ),
    "transaction_code_to_type_map": dumps({"6011": "ATM withdrawal", "3123": "eCommerce"}),
    "transaction_types": dumps(["purchase", "ATM withdrawal", "transfer"]),
    "deposit_tier_ranges": dumps(
        {
            "tier1": {"min": "0", "max": "3000.00"},
            "tier2": {"min": "3000.00", "max": "5000.00"},
            "tier3": {"min": "5000.00", "max": "7500.00"},
            "tier4": {"min": "7500.00", "max": "15000.00"},
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
    "optional_standard_overdraft_coverage": dumps(["ATM withdrawal", "eCommerce"]),
}

BALANCE_TIER_RANGES = dumps(
    {
        "tier1": {"min": "0", "max": "15000.00"},
        "tier2": {"min": "15000.00"},
    }
)
TIERED_INTEREST_RATES = dumps(
    {
        "US_SAVINGS_ACCOUNT_TIER_UPPER": {"tier1": "0.02", "tier2": "0.015"},
        "US_SAVINGS_ACCOUNT_TIER_MIDDLE": {"tier1": "0.0125", "tier2": "0.01"},
        "US_SAVINGS_ACCOUNT_TIER_LOWER": {"tier1": "0.149", "tier2": "-0.1485"},
    }
)
TIERED_MIN_BALANCE_THRESHOLD = dumps(
    {
        "US_SAVINGS_ACCOUNT_TIER_UPPER": "25",
        "US_SAVINGS_ACCOUNT_TIER_MIDDLE": "75",
        "US_SAVINGS_ACCOUNT_TIER_LOWER": "100",
    }
)
ZERO_TIERED_MAINTENANCE_FEE_MONTHLY = dumps(
    {
        "US_SAVINGS_ACCOUNT_TIER_UPPER": "0",
        "US_SAVINGS_ACCOUNT_TIER_MIDDLE": "0",
        "US_SAVINGS_ACCOUNT_TIER_LOWER": "0",
    }
)
ACCOUNT_TIER_NAMES = dumps(
    [
        "US_SAVINGS_ACCOUNT_TIER_UPPER",
        "US_SAVINGS_ACCOUNT_TIER_MIDDLE",
        "US_SAVINGS_ACCOUNT_TIER_LOWER",
    ]
)
ZERO_TIERED_INTEREST_RATES = dumps(
    {
        "US_SAVINGS_ACCOUNT_TIER_UPPER": {"tier1": "0", "tier2": "0"},
        "US_SAVINGS_ACCOUNT_TIER_MIDDLE": {"tier1": "0", "tier2": "0"},
        "US_SAVINGS_ACCOUNT_TIER_LOWER": {"tier1": "0", "tier2": "0"},
    }
)

default_savings_instance_params = {"interest_application_day": "5"}
default_savings_template_params = {
    "denomination": "USD",
    "balance_tier_ranges": BALANCE_TIER_RANGES,
    "tiered_interest_rates": TIERED_INTEREST_RATES,
    "minimum_combined_balance_threshold": dumps(
        {
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "3000",
            "US_SAVINGS_ACCOUNT_TIER_MIDDLE": "4000",
            "US_SAVINGS_ACCOUNT_TIER_LOWER": "5000",
        }
    ),
    "minimum_deposit": "0",
    "maximum_daily_deposit": "1001",
    "minimum_withdrawal": "0.01",
    "maximum_daily_withdrawal": "1000",
    "maximum_balance": "10000",
    "accrued_interest_payable_account": ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    "interest_paid_account": INTEREST_PAID_ACCOUNT,
    "accrued_interest_receivable_account": ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    "interest_received_account": INTEREST_RECEIVED_ACCOUNT,
    "maintenance_fee_income_account": MAINTENANCE_FEE_INCOME_ACCOUNT,
    "excess_withdrawal_fee_income_account": EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
    "minimum_balance_fee_income_account": MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
    "days_in_year": "365",
    "interest_accrual_hour": "0",
    "interest_accrual_minute": "0",
    "interest_accrual_second": "0",
    "interest_application_hour": "0",
    "interest_application_minute": "1",
    "interest_application_second": "0",
    "interest_application_frequency": "monthly",
    "monthly_withdrawal_limit": "5",
    "reject_excess_withdrawals": "true",
    "excess_withdrawal_fee": "10",
    "maintenance_fee_annual": "0",
    "maintenance_fee_monthly": ZERO_TIERED_MAINTENANCE_FEE_MONTHLY,
    "promotional_maintenance_fee_monthly": ZERO_TIERED_MAINTENANCE_FEE_MONTHLY,
    "fees_application_day": "1",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "tiered_minimum_balance_threshold": TIERED_MIN_BALANCE_THRESHOLD,
    "minimum_balance_fee": "0",
    "account_tier_names": ACCOUNT_TIER_NAMES,
    "automated_transfer_tag": "DEPOSIT_ACH_",
    "promotional_rates": TIERED_INTEREST_RATES,
}

CHECKING_ACCOUNT_ALIAS = "us_checking_account"
SAVINGS_ACCOUNT_ALIAS = "us_savings_account"
DEFAULT_SUPERVISEE_VERSION_IDS = {CHECKING_ACCOUNT_ALIAS: "1", SAVINGS_ACCOUNT_ALIAS: "2"}


class SavingsSweepSupervisorTest(SimulationTestCase):

    internal_accounts = {
        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: "ASSET",
        INTEREST_RECEIVED_ACCOUNT: "LIABILITY",
        ACCRUED_INTEREST_PAYABLE_ACCOUNT: "LIABILITY",
        INTEREST_PAID_ACCOUNT: "ASSET",
        OVERDRAFT_FEE_INCOME_ACCOUNT: "LIABILITY",
        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: "ASSET",
        MAINTENANCE_FEE_INCOME_ACCOUNT: "LIABILITY",
        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: "LIABILITY",
        ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: "LIABILITY",
        INACTIVITY_FEE_INCOME_ACCOUNT: "LIABILITY",
        # This is a generic account used for external postings
        "1": "LIABILITY",
    }

    @classmethod
    def setUpClass(cls):
        cls.checking_contract = CHECKING_CONTRACT_FILE
        cls.savings_contract = SAVINGS_CONTRACT_FILE
        cls.contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
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
        checking_instance_params=default_checking_instance_params,
        checking_template_params=default_checking_template_params,
        checking_instances=1,
        savings_instance_params=default_savings_instance_params,
        savings_template_params=default_savings_template_params,
        savings_instances=1,
    ):

        checking_supervisee = SuperviseeConfig(
            contract_id=CHECKING_ACCOUNT_ALIAS,
            contract_file=CHECKING_CONTRACT_FILE,
            account_name=CHECKING_ACCOUNT,
            version=CHECKING_ACCOUNT_PRODUCT_VERSION_ID,
            instance_parameters=checking_instance_params,
            template_parameters=checking_template_params,
            instances=checking_instances,
            linked_contract_modules=self.contract_modules,
        )
        savings_supervisee = SuperviseeConfig(
            contract_id=SAVINGS_ACCOUNT_ALIAS,
            contract_file=SAVINGS_CONTRACT_FILE,
            account_name=SAVINGS_ACCOUNT,
            version=SAVINGS_ACCOUNT_PRODUCT_VERSION_ID,
            instance_parameters=savings_instance_params,
            template_parameters=savings_template_params,
            instances=savings_instances,
            linked_contract_modules=self.contract_modules,
        )

        supervisor_config = create_supervisor_config(
            SUPERVISOR_CONTRACT_FILE,
            "supervisor version 1",
            [
                checking_supervisee,
                savings_supervisee,
            ],
        )

        return supervisor_config

    def test_savings_sweep_amount_lt_100_bug(self):
        """
        INC-3400 workaround in supervisor contract to add 1 microsecond to the Savings Sweep posting
        This ensures the value_timestamp of the Savings Sweep posting is not the same as the
        withdrawal posting.
        If the initial withdrawal amount is greater than or equal to 100, this problem is not seen.
        """
        start = datetime(year=2021, month=1, day=10, tzinfo=timezone.utc)
        end = start + timedelta(hours=5)

        checking_instance_params = default_checking_instance_params.copy()
        checking_instance_params["savings_sweep_account_hierarchy"] = dumps(
            [f"{SAVINGS_ACCOUNT} 0", f"{SAVINGS_ACCOUNT} 1", f"{SAVINGS_ACCOUNT} 2"]
        )

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["savings_sweep_fee"] = "0"
        checking_template_params["savings_sweep_fee_cap"] = "-1"

        sub_tests = [
            SubTest(
                description="phase 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "150",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "50",  # bug only appears if this amount is less than 100
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1, minutes=10),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=30): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "0")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "100")],
                    }
                },
            ),
            SubTest(
                description="phase 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "50",
                        start + timedelta(hours=2, minutes=10),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=2, minutes=30): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "0")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "50")],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                checking_instance_params=checking_instance_params,
                checking_template_params=checking_template_params,
            ),
        )

        self.run_test_scenario(test_scenario)

    def test_savings_sweep_hierarchy(self):
        start = datetime(year=2021, month=1, day=10, tzinfo=timezone.utc)
        end = start + timedelta(hours=6)

        checking_instance_parameters = default_checking_instance_params.copy()
        checking_instance_parameters["savings_sweep_account_hierarchy"] = dumps(
            [f"{SAVINGS_ACCOUNT} 1", f"{SAVINGS_ACCOUNT} 0", f"{SAVINGS_ACCOUNT} 2"]
        )

        checking_template_parameters = default_checking_template_params.copy()
        checking_template_parameters["savings_sweep_fee_cap"] = "-1"

        checking_account_configs = [
            AccountConfig(
                instance_params=checking_instance_parameters,
                account_id_base=f"{CHECKING_ACCOUNT} ",
            )
        ]

        savings_account_configs = [
            AccountConfig(
                instance_params=default_savings_instance_params,
                account_id_base=f"{SAVINGS_ACCOUNT} ",
                number_of_accounts=3,
            )
        ]

        checking_account_contract = ContractConfig(
            clu_resource_id=CHECKING_ACCOUNT_ALIAS,
            contract_file_path=self.checking_contract,
            template_params=checking_template_parameters,
            smart_contract_version_id=CHECKING_ACCOUNT_PRODUCT_VERSION_ID,
            account_configs=checking_account_configs,
            linked_contract_modules=self.contract_modules,
        )

        savings_account_contract = ContractConfig(
            clu_resource_id=SAVINGS_ACCOUNT_ALIAS,
            contract_file_path=self.savings_contract,
            template_params=default_savings_template_params,
            smart_contract_version_id=SAVINGS_ACCOUNT_PRODUCT_VERSION_ID,
            account_configs=savings_account_configs,
            linked_contract_modules=self.contract_modules,
        )

        supervisor_config = SupervisorConfig(
            supervisor_file_path=SUPERVISOR_CONTRACT_FILE,
            supervisee_contracts=[checking_account_contract, savings_account_contract],
        )

        sub_tests = [
            SubTest(
                description="sweeping according to hierarchy",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "200",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 2",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "50",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1, minutes=10),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=30): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "0")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "100")],
                        f"{SAVINGS_ACCOUNT} 1": [(BalanceDimensions(denomination="USD"), "138")],
                        f"{SAVINGS_ACCOUNT} 2": [(BalanceDimensions(denomination="USD"), "500")],
                    }
                },
            ),
            SubTest(
                description="savings_sweep not triggered if savings account balances below \
                    savings_sweep fee",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "133",
                        start + timedelta(hours=2),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 1",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "98",
                        start + timedelta(hours=2),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "498",
                        start + timedelta(hours=2),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 2",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "5",
                        start + timedelta(hours=2, minutes=10),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=2, minutes=5): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "0")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "2")],
                        f"{SAVINGS_ACCOUNT} 1": [(BalanceDimensions(denomination="USD"), "5")],
                        f"{SAVINGS_ACCOUNT} 2": [(BalanceDimensions(denomination="USD"), "2")],
                    },
                    start
                    + timedelta(hours=2, minutes=15): {
                        # withdrawal of 5 within fee free loc
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "-5")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "2")],
                        f"{SAVINGS_ACCOUNT} 1": [(BalanceDimensions(denomination="USD"), "5")],
                        f"{SAVINGS_ACCOUNT} 2": [(BalanceDimensions(denomination="USD"), "2")],
                    },
                },
            ),
            SubTest(
                description="savings_sweep triggered if savings account balances above \
                    savings_sweep fee",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "10",
                        start + timedelta(hours=3),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 2",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "10",
                        start + timedelta(hours=3, minutes=10),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=3, minutes=15): {
                        # total needed is -5 + -10 withdrawal + -12 savings_sweep fee = -27
                        # total savings account balance 2 + 5 + 12 = 19
                        # final checking balance is -27 + 19 = -8
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "-8")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "0")],
                        f"{SAVINGS_ACCOUNT} 1": [(BalanceDimensions(denomination="USD"), "0")],
                        f"{SAVINGS_ACCOUNT} 2": [(BalanceDimensions(denomination="USD"), "0")],
                    }
                },
            ),
            SubTest(
                description="Unset the hierarchy optional parameter",
                events=[
                    # Savings accounts all updated to have balance = 100
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=4),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=4),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=4),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 2",
                    ),
                    create_instance_parameter_change_event(
                        timestamp=start + timedelta(hours=4),
                        account_id=f"{CHECKING_ACCOUNT} 0",
                        savings_sweep_account_hierarchy="",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "10",
                        start + timedelta(hours=4, minutes=10),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=4, minutes=15): {
                        # Total needed is -8 checking balance + -10 withdrawal +
                        # -12 savings_sweep fee = 30
                        # As per default Savings Sweep behaviour,
                        # Savings Account 0 is used first as oldest account
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "0")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "70")],
                        f"{SAVINGS_ACCOUNT} 1": [(BalanceDimensions(denomination="USD"), "100")],
                        f"{SAVINGS_ACCOUNT} 2": [(BalanceDimensions(denomination="USD"), "100")],
                    }
                },
            ),
            SubTest(
                description="Set the hierarchy optional parameter to disable Savings Sweep",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + timedelta(hours=5),
                        account_id=f"{CHECKING_ACCOUNT} 0",
                        savings_sweep_account_hierarchy="[]",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "10",
                        start + timedelta(hours=5, minutes=10),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=5, minutes=15): {
                        # No Savings Sweep so balances remain the same,
                        # except with -10 withdrawal from checking
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "-10")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "70")],
                        f"{SAVINGS_ACCOUNT} 1": [(BalanceDimensions(denomination="USD"), "100")],
                        f"{SAVINGS_ACCOUNT} 2": [(BalanceDimensions(denomination="USD"), "100")],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=supervisor_config,
        )

        self.run_test_scenario(test_scenario)

    def test_savings_sweep(self):
        start = datetime(year=2021, month=1, day=10, tzinfo=timezone.utc)
        end = start + timedelta(hours=5)

        sub_tests = [
            SubTest(
                description="0 balance in checking triggers savings sweep transfer",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(minutes=1),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                        client_transaction_id="123456",
                        instruction_details={"description": "test2"},
                        batch_details={"description": "test2"},
                        client_batch_id="123",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "50",
                        start + timedelta(minutes=2),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                        client_transaction_id="654321",
                        instruction_details={"description": "test1"},
                        batch_details={"description": "test1"},
                        client_batch_id="456",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(minutes=5): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "0")],
                        # transferred 50 + 12 savings sweep fee
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "438")],
                        # against savings inbound = -500
                        # against checking outbound = 50
                        # against checking savings_sweep fee = 12
                        # final balance = -438
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "12")
                        ],
                    }
                },
            ),
            SubTest(
                description="savings_sweep with inbound and outbound auth and adjustment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "62",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "150",
                        start + timedelta(hours=1, minutes=1),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_authorisation_instruction(
                        "60",
                        start + timedelta(hours=1, minutes=2),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_outbound_authorisation_instruction(
                        "10",
                        start + timedelta(hours=1, minutes=3),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                        client_transaction_id="ADJUSTMENT_TEST_TRANSACTION",
                    ),
                    # out auth increased to 40 with auth of 10 + adjustment 30
                    create_auth_adjustment_instruction(
                        amount="30.00",
                        event_datetime=start + timedelta(hours=1, minutes=4),
                        client_transaction_id="ADJUSTMENT_TEST_TRANSACTION",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "200",
                        start + timedelta(hours=1, minutes=5),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=30): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (BalanceDimensions(denomination="USD"), "0"),
                            (
                                BalanceDimensions(
                                    denomination="USD",
                                    phase="POSTING_PHASE_PENDING_OUTGOING",
                                ),
                                "-40",
                            ),
                            (
                                BalanceDimensions(
                                    denomination="USD",
                                    phase="POSTING_PHASE_PENDING_INCOMING",
                                ),
                                "60",
                            ),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [
                            # fee cap reached
                            # total balance = 500 - 50 =  450
                            (BalanceDimensions(denomination="USD"), "450")
                        ],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "12")
                        ],
                    }
                },
            ),
            SubTest(
                description="savings_sweep only triggered when outbound auth is settled",
                events=[
                    create_release_event(
                        client_transaction_id="ADJUSTMENT_TEST_TRANSACTION",
                        event_datetime=start + timedelta(hours=2),
                    ),
                    create_outbound_authorisation_instruction(
                        "40",
                        start + timedelta(hours=2),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                        client_transaction_id="super123",
                    ),
                    create_settlement_event(
                        "40",
                        "super123",
                        start + timedelta(hours=2, minutes=20),
                        final=True,
                    ),
                ],
                expected_balances_at_ts={
                    # before settlement, no fund movement from savings
                    start
                    + timedelta(hours=2, minutes=19): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (BalanceDimensions(denomination="USD"), "0"),
                            (
                                BalanceDimensions(
                                    denomination="USD",
                                    phase="POSTING_PHASE_PENDING_OUTGOING",
                                ),
                                "-40",
                            ),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "450")],
                    },
                    # after settlement, 40 was transferred from savings
                    start
                    + timedelta(hours=2, minutes=21): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (BalanceDimensions(denomination="USD"), "0"),
                            (
                                BalanceDimensions(
                                    denomination="USD",
                                    phase="POSTING_PHASE_PENDING_OUTGOING",
                                ),
                                "0",
                            ),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "410")],
                    },
                },
            ),
            SubTest(
                description="transfer between checking and internal account",
                events=[
                    create_transfer_instruction(
                        "50",
                        start + timedelta(hours=3),
                        denomination="USD",
                        debtor_target_account_id=f"{CHECKING_ACCOUNT} 0",
                        creditor_target_account_id="1",
                    )
                ],
                expected_balances_at_ts={
                    # 50 transferred from savings account
                    start
                    + timedelta(hours=3, minutes=30): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (BalanceDimensions(denomination="USD"), "0"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "360")],
                    },
                },
            ),
            SubTest(
                description="transfer between checking and savings account",
                events=[
                    create_account_instruction(
                        timestamp=start + timedelta(hours=4),
                        account_id=f"{SAVINGS_ACCOUNT} 1",
                        product_id="2",
                        instance_param_vals=default_savings_instance_params,
                    ),
                    create_transfer_instruction(
                        "50",
                        start + timedelta(hours=4, minutes=5),
                        denomination="USD",
                        debtor_target_account_id=f"{CHECKING_ACCOUNT} 0",
                        creditor_target_account_id=f"{SAVINGS_ACCOUNT} 1",
                    ),
                ],
                expected_balances_at_ts={
                    # 50 transferred checking account 0 -> savings account 1
                    # 50 savings_sweep savings account 0 -> checking account 0
                    start
                    + timedelta(hours=4, minutes=30): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (BalanceDimensions(denomination="USD"), "0"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "310")],
                        f"{SAVINGS_ACCOUNT} 1": [(BalanceDimensions(denomination="USD"), "50")],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
        )

        self.run_test_scenario(test_scenario)

    def test_savings_sweep_transfer_unit(self):
        start = datetime(year=2021, month=1, day=10, tzinfo=timezone.utc)
        end = start + timedelta(hours=5)

        checking_instance_params = default_checking_instance_params.copy()
        checking_instance_params["savings_sweep_account_hierarchy"] = dumps(
            [f"{SAVINGS_ACCOUNT} 1", f"{SAVINGS_ACCOUNT} 0", f"{SAVINGS_ACCOUNT} 2"]
        )

        checking_instance_params["fee_free_overdraft_limit"] = "0"
        checking_template_params = default_checking_template_params.copy()
        checking_template_params["savings_sweep_fee"] = "34"
        checking_template_params["standard_overdraft_per_transaction_fee"] = "34"
        checking_template_params["savings_sweep_fee_cap"] = "-1"
        checking_template_params["savings_sweep_transfer_unit"] = "50"

        checking_account_configs = [
            AccountConfig(
                instance_params=checking_instance_params,
                account_id_base=f"{CHECKING_ACCOUNT} ",
            )
        ]

        savings_account_configs = [
            AccountConfig(
                instance_params=default_savings_instance_params,
                account_id_base=f"{SAVINGS_ACCOUNT} ",
                number_of_accounts=3,
            )
        ]

        checking_account_contract = ContractConfig(
            clu_resource_id=CHECKING_ACCOUNT_ALIAS,
            contract_file_path=self.checking_contract,
            template_params=checking_template_params,
            smart_contract_version_id=CHECKING_ACCOUNT_PRODUCT_VERSION_ID,
            account_configs=checking_account_configs,
            linked_contract_modules=self.contract_modules,
        )

        savings_account_contract = ContractConfig(
            clu_resource_id=SAVINGS_ACCOUNT_ALIAS,
            contract_file_path=self.savings_contract,
            template_params=default_savings_template_params,
            smart_contract_version_id=SAVINGS_ACCOUNT_PRODUCT_VERSION_ID,
            account_configs=savings_account_configs,
            linked_contract_modules=self.contract_modules,
        )

        supervisor_config = SupervisorConfig(
            supervisor_file_path=SUPERVISOR_CONTRACT_FILE,
            supervisee_contracts=[checking_account_contract, savings_account_contract],
        )

        sub_tests = [
            SubTest(
                description="sweeping according to hierarchy with transfer unit set to 50",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "120",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 2",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "160",
                        start + timedelta(hours=1, minutes=10),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                # Checking Account 0 funds used: $100
                # Savings Account 1 funds used: $100
                #   $60 used for transaction
                #   $34 will be used for Savings Sweep fee
                #   $6 surplus added to checking account balance
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=30): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "6")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "100")],
                        f"{SAVINGS_ACCOUNT} 1": [(BalanceDimensions(denomination="USD"), "20")],
                        f"{SAVINGS_ACCOUNT} 2": [(BalanceDimensions(denomination="USD"), "500")],
                    }
                },
            ),
            SubTest(
                description="sweeping from multiple savings accounts with transfer unit set to 50",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "812.13",
                        start + timedelta(hours=2, minutes=10),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    )
                ],
                #  812.13       Total outbound transation from checking
                #    - 6        Checking Account 0 (positive balance)
                #    - 0        Savings Account 1
                #    - 100      Savings Account 0
                #    - 500      Savings Account 2
                #    = 206.13   remaining to be paid from standard overdraft
                #    - 34       savings_sweep_fee
                #    - 34       standard_overdraft_per_transaction_fee
                #    = -274.13  Checking Account 0 (standard overdraft)
                expected_balances_at_ts={
                    start
                    + timedelta(hours=2, minutes=30): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (BalanceDimensions(denomination="USD"), "-274.13")
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "0")],
                        f"{SAVINGS_ACCOUNT} 1": [(BalanceDimensions(denomination="USD"), "20")],
                        f"{SAVINGS_ACCOUNT} 2": [(BalanceDimensions(denomination="USD"), "0")],
                    }
                },
            ),
            SubTest(
                description="sweeping according to hierarchy with transfer unit set to 1",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(hours=2, minutes=31),
                        smart_contract_version_id=CHECKING_ACCOUNT_PRODUCT_VERSION_ID,
                        savings_sweep_transfer_unit="1",
                    ),
                    # Reset the account balances to 0
                    create_inbound_hard_settlement_instruction(
                        "274.13",
                        start + timedelta(hours=2, minutes=31),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "20",
                        start + timedelta(hours=2, minutes=31),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "120",
                        start + timedelta(hours=3),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=3),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "500.5",
                        start + timedelta(hours=3),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 2",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=3),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "159.01",
                        start + timedelta(hours=3, minutes=10),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                # Checking Account 0 funds used: $100
                # Savings Account 1 funds used: $94
                #   $60 used for transaction
                #   $34 will be used for Savings Sweep fee
                #   $0.99 surplus added to checking account balance
                expected_balances_at_ts={
                    start
                    + timedelta(hours=3, minutes=30): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "0.99")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "100")],
                        f"{SAVINGS_ACCOUNT} 1": [(BalanceDimensions(denomination="USD"), "26")],
                        f"{SAVINGS_ACCOUNT} 2": [(BalanceDimensions(denomination="USD"), "500.5")],
                    }
                },
            ),
            SubTest(
                description="sweeping from multiple savings accounts with transfer unit set to 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "909.73",
                        start + timedelta(hours=4, minutes=10),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    )
                ],
                #  909.73       Total outbound transation from checking
                #    - 0.99     Checking Account 0 (positive balance)
                #    - 26       Savings Account 1
                #    - 100      Savings Account 0
                #    - 500      Savings Account 2
                #    = 282.74   remaining to be paid from standard overdraft
                #    - 34       savings_sweep_fee
                #    - 34       standard_overdraft_per_transaction_fee
                #    = -350.74  Checking Account 0 (standard overdraft)
                expected_balances_at_ts={
                    start
                    + timedelta(hours=4, minutes=30): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (BalanceDimensions(denomination="USD"), "-350.74")
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "0")],
                        f"{SAVINGS_ACCOUNT} 1": [(BalanceDimensions(denomination="USD"), "0")],
                        f"{SAVINGS_ACCOUNT} 2": [(BalanceDimensions(denomination="USD"), "0.5")],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=supervisor_config,
        )

        self.run_test_scenario(test_scenario)

    def test_multiple_supervisee_accounts_on_plan(self):
        start = datetime(year=2021, month=1, day=10, tzinfo=timezone.utc)
        end = start + timedelta(hours=5)

        sub_tests = [
            SubTest(
                description="funding supervisor accounts on plan",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(seconds=10),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(seconds=11),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(seconds=12),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 2",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "150",
                        start + timedelta(seconds=13),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "150",
                        start + timedelta(seconds=14),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "150",
                        start + timedelta(seconds=15),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 2",
                    ),
                ],
            ),
            SubTest(
                description="triggers $10 savings sweep transfer and $12 savings_sweep fee",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "160",
                        start + timedelta(seconds=16),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 1",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(seconds=16): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "150"),
                        ],
                        f"{CHECKING_ACCOUNT} 1": [
                            (DEFAULT_USD_DIMENSION, "0"),
                        ],
                        f"{CHECKING_ACCOUNT} 2": [
                            (DEFAULT_USD_DIMENSION, "150"),
                        ],
                        # # only the oldest (by account creation date) savings account
                        # # is used for savings sweep, as hierarchy option not enabled
                        # # 500 - 10 - 12 = 478
                        f"{SAVINGS_ACCOUNT} 0": {
                            (DEFAULT_USD_DIMENSION, "478"),
                        },
                        f"{SAVINGS_ACCOUNT} 1": {
                            (DEFAULT_USD_DIMENSION, "500"),
                        },
                        f"{SAVINGS_ACCOUNT} 2": {
                            (DEFAULT_USD_DIMENSION, "500"),
                        },
                        OVERDRAFT_FEE_INCOME_ACCOUNT: {
                            (DEFAULT_USD_DIMENSION, "12"),
                        },
                    }
                },
            ),
            SubTest(
                description=(
                    "triggers 150 savings_sweep transfer & $12 savings_sweep fee, cap is for \
                    each acc, not cust level"
                ),
                events=[
                    create_outbound_hard_settlement_instruction(
                        "300",
                        start + timedelta(seconds=17),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 2",
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "150"),
                        ],
                        f"{CHECKING_ACCOUNT} 1": [
                            (DEFAULT_USD_DIMENSION, "0"),
                        ],
                        f"{CHECKING_ACCOUNT} 2": [
                            (DEFAULT_USD_DIMENSION, "0"),
                        ],
                        # only the oldest (by account creation date) savings account
                        # is used for savings sweep, as hierarchy option not enabled
                        # 500 - 10 - 12 - 150 - 12 = 316
                        f"{SAVINGS_ACCOUNT} 0": {
                            (DEFAULT_USD_DIMENSION, "316"),
                        },
                        f"{SAVINGS_ACCOUNT} 1": {
                            (DEFAULT_USD_DIMENSION, "500"),
                        },
                        f"{SAVINGS_ACCOUNT} 2": {
                            (DEFAULT_USD_DIMENSION, "500"),
                        },
                        # fees income from savings_sweep = 12 + 12
                        OVERDRAFT_FEE_INCOME_ACCOUNT: {
                            (DEFAULT_USD_DIMENSION, "24"),
                        },
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                checking_instances=3, savings_instances=3
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_multiple_supervisee_accounts_in_post_posting(self):
        start = datetime(year=2021, month=1, day=10, tzinfo=timezone.utc)
        end = start + timedelta(hours=5)

        withdrawal_instruction_1 = OutboundHardSettlement(
            "100", target_account_id=f"{CHECKING_ACCOUNT} 0", denomination="USD"
        )

        withdrawal_instruction_2 = OutboundHardSettlement(
            "100", target_account_id=f"{CHECKING_ACCOUNT} 1", denomination="USD"
        )

        sub_tests = [
            SubTest(
                description="create posting and catch rejection",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            withdrawal_instruction_1,
                            withdrawal_instruction_2,
                        ],
                        event_datetime=start + timedelta(hours=1),
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=1),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Multiple checking accounts in post posting not supported."
                        ),
                    )
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(checking_instances=3),
            internal_accounts=self.internal_accounts,
        )

        with self.assertRaises(Exception) as ex:
            self.run_test_scenario(test_scenario)

        self.assertIn(
            "Multiple checking accounts in post posting not supported.",
            str(ex.exception),
        )

    def test_overdraft_transaction_fee_logic_in_standard_overdraft(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=2, minute=10, tzinfo=timezone.utc)

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["standard_overdraft_per_transaction_fee"] = "34"
        # set standard_overdraft_fee_cap to 0 to test it is unlimited
        checking_template_params["standard_overdraft_fee_cap"] = "0"

        withdrawal_instruction = OutboundHardSettlement(
            "100", target_account_id=f"{CHECKING_ACCOUNT} 0", denomination="USD"
        )

        sub_tests = [
            SubTest(
                description="within fee free overdraft should not incur a charge",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "999",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    )
                ],
            ),
            SubTest(
                description="exceeding fee free overdraft should incur a fee",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "501",
                        start + timedelta(hours=3),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    )
                ],
            ),
            SubTest(
                description="exceeding od limit should not incur fee as posting is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(hours=5),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    )
                ],
            ),
            SubTest(
                description="credit postings should not incur overdraft fees",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "300",
                        start + timedelta(hours=7),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    )
                ],
            ),
            SubTest(
                description="non-default address postings should not incur overdraft fees",
                events=[
                    create_custom_instruction(
                        amount="300",
                        debtor_target_account_id=f"{CHECKING_ACCOUNT} 0",
                        creditor_target_account_id="1",
                        debtor_target_account_address="NON_DEFAULT_ADDRESS",
                        creditor_target_account_address="DEFAULT",
                        event_datetime=start + timedelta(hours=7),
                        denomination="USD",
                    )
                ],
            ),
            SubTest(
                description="default address custom postings should incur overdraft fees",
                events=[
                    create_custom_instruction(
                        amount="200",
                        debtor_target_account_id=f"{CHECKING_ACCOUNT} 0",
                        creditor_target_account_id="1",
                        debtor_target_account_address="DEFAULT",
                        creditor_target_account_address="DEFAULT",
                        event_datetime=start + timedelta(hours=9),
                        denomination="USD",
                    )
                ],
            ),
            SubTest(
                description="two withdrawals within a pib will incur overdraft fees twice",
                events=[
                    create_posting_instruction_batch(
                        instructions=[withdrawal_instruction, withdrawal_instruction],
                        event_datetime=start + timedelta(hours=11),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=2): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "-999"),
                        ],
                    },
                    start
                    + timedelta(hours=4): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "-1534"),
                        ],
                    },
                    start
                    + timedelta(hours=6): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "-1534"),
                        ],
                    },
                    start
                    + timedelta(hours=7): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "-1234"),
                            (NON_DEFAULT_USD_DIMENSION, "-300"),
                        ],
                    },
                    start
                    + timedelta(hours=10): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "-1468"),
                            (NON_DEFAULT_USD_DIMENSION, "-300"),
                        ]
                    },
                    end: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "-1736"),
                            (NON_DEFAULT_USD_DIMENSION, "-300"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [(DEFAULT_USD_DIMENSION, "0")],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                checking_template_params=checking_template_params,
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_standard_overdraft_fee_cap_applied(self):
        start = datetime(year=2021, month=1, day=1, hour=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=1, hour=12, tzinfo=timezone.utc)

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["standard_overdraft_per_transaction_fee"] = "10"
        checking_template_params["standard_overdraft_fee_cap"] = "12"

        sub_tests = [
            SubTest(
                description="standard overdraft fee cap applied",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "10",
                        start + timedelta(hours=2),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "1500",
                        start + timedelta(hours=2),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    # fee for this should not be charged as it is capped from the first withdrawal
                    create_outbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=3),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "50",
                        start + timedelta(hours=5),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "20",
                        start + timedelta(hours=7),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "-1570"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": {
                            (DEFAULT_USD_DIMENSION, "0"),
                        },
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                checking_template_params=checking_template_params
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_autosave(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=1, hour=5, tzinfo=timezone.utc)

        checking_instance_params = default_checking_instance_params.copy()
        checking_instance_params["autosave_savings_account"] = f"{SAVINGS_ACCOUNT} 0"

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["autosave_rounding_amount"] = "1.00"
        checking_template_params["denomination"] = "USD"
        checking_template_params["additional_denominations"] = dumps(["USD", "EUR"])

        sub_tests = [
            SubTest(
                description="check autosave",
                events=[
                    # no auto saving for deposits
                    create_inbound_hard_settlement_instruction(
                        "1000.01",
                        start + timedelta(minutes=1),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "1000.00",
                        start + timedelta(minutes=1),
                        denomination="EUR",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    # after this balance should be USD 716.01 because of autosave 0.55
                    create_outbound_hard_settlement_instruction(
                        "283.45",
                        start + timedelta(minutes=3),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    # non default denomination does not trigger autosave
                    create_outbound_hard_settlement_instruction(
                        "283.45",
                        start + timedelta(minutes=3),
                        denomination="EUR",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    # after this USD balance should be
                    # current 716.01 -515.01 - autosave 0.99 = 200.01
                    create_outbound_hard_settlement_instruction(
                        "515.01",
                        start + timedelta(minutes=5),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    # expect no saving for this one 200.01 - 88 = 112.01
                    create_outbound_hard_settlement_instruction(
                        "88.00",
                        start + timedelta(minutes=7),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    # at this point remaining balance is 112.01 so autosave will not be allowed
                    create_outbound_hard_settlement_instruction(
                        "112.01",
                        start + timedelta(minutes=9),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "1000.00",
                        start + timedelta(minutes=11),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    # multiple withdrawals within a pib also triggers auto save
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                "99.05",
                                target_account_id=f"{CHECKING_ACCOUNT} 0",
                                denomination="USD",
                            ),
                            OutboundHardSettlement(
                                "49.75",
                                target_account_id=f"{CHECKING_ACCOUNT} 0",
                                denomination="USD",
                            ),
                        ],
                        event_datetime=start + timedelta(minutes=13),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(minutes=10): {
                        f"{CHECKING_ACCOUNT} 0": {
                            (DEFAULT_USD_DIMENSION, "0"),
                            (DEFAULT_EUR_DIMENSION, "716.55"),
                        },
                        f"{SAVINGS_ACCOUNT} 0": {
                            (DEFAULT_USD_DIMENSION, "1.54"),
                            (DEFAULT_EUR_DIMENSION, "0.00"),
                        },
                    },
                    end: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "850"),
                            (DEFAULT_EUR_DIMENSION, "716.55"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": {
                            (DEFAULT_USD_DIMENSION, "2.74"),
                            (DEFAULT_EUR_DIMENSION, "0.00"),
                        },
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                checking_instance_params=checking_instance_params,
                checking_template_params=checking_template_params,
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_account_with_min_balance_does_not_trigger_autosave(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=1, hour=5, tzinfo=timezone.utc)

        checking_instance_params = default_checking_instance_params.copy()
        checking_instance_params["autosave_savings_account"] = f"{SAVINGS_ACCOUNT} 0"

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["autosave_rounding_amount"] = "1.00"
        checking_template_params["denomination"] = "USD"
        checking_template_params["minimum_balance_fee"] = "50"

        sub_tests = [
            SubTest(
                description="account with minimum balance does not trigger autosave",
                events=[
                    # no auto saving for deposits
                    create_inbound_hard_settlement_instruction(
                        "1000.00",
                        start + timedelta(minutes=1),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "283.45",
                        start + timedelta(minutes=3),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "716.55"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": {
                            (DEFAULT_USD_DIMENSION, "0.00"),
                        },
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                checking_instance_params=checking_instance_params,
                checking_template_params=checking_template_params,
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_checking_minimum_balance_fee_and_monthly_maintenance_fee_applied(self):
        start = datetime(year=2020, month=12, day=31, tzinfo=timezone.utc)
        end = datetime(year=2021, month=3, day=2, tzinfo=timezone.utc)

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["minimum_balance_fee"] = "10"
        checking_template_params["tier_names"] = dumps(["X", "Y", "Z"])
        checking_template_params["minimum_balance_threshold"] = dumps(
            {"X": "1.5", "Y": "100", "Z": "200"}
        )
        checking_template_params["minimum_deposit_threshold"] = dumps({"Z": "500"})
        checking_template_params["maintenance_fee_monthly"] = dumps({"Z": "10"})
        checking_template_params["minimum_combined_balance_threshold"] = dumps({"Z": "5000"})
        checking_template_params["interest_free_buffer"] = dumps(
            {"X": "500", "Y": "300", "Z": "50"}
        )
        checking_template_params["overdraft_interest_free_buffer_days"] = dumps(
            {"X": "-1", "Y": "-1", "Z": "-1"}
        )
        checking_template_params["deposit_tier_ranges"] = dumps({"tier1": {"min": "0"}})
        checking_template_params["deposit_interest_rate_tiers"] = dumps({"tier1": "0.00"})

        sub_tests = [
            SubTest(
                description="checking minimum balance fee and monthly maintainence fee applied",
                expected_balances_at_ts={
                    # Both fee types will have applied 2 times
                    end: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "-40.0"),
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
                checking_template_params=checking_template_params
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_maintenance_fee_application_at_configured_time(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(
            year=2021,
            month=3,
            day=2,
            hour=17,
            minute=30,
            second=31,
            tzinfo=timezone.utc,
        )

        before_2nd_fee_application = datetime(
            year=2021,
            month=3,
            day=2,
            hour=17,
            minute=30,
            second=29,
            tzinfo=timezone.utc,
        )

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["maintenance_fee_monthly"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}
        )
        checking_template_params["fees_application_day"] = "2"
        checking_template_params["fees_application_hour"] = "17"
        checking_template_params["fees_application_minute"] = "30"
        checking_template_params["fees_application_second"] = "30"

        sub_tests = [
            SubTest(
                description="maintainance fee application at configured time",
                expected_balances_at_ts={
                    before_2nd_fee_application: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "-10.0"),
                        ],
                    },
                    end: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "-20.0"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                checking_template_params=checking_template_params
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_monthly_maintenance_fee_not_applied_if_min_deposit_waive_criteria_met(
        self,
    ):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=2, day=1, minute=2, tzinfo=timezone.utc)

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["deposit_tier_ranges"] = dumps({"tier1": {"min": "0"}})
        checking_template_params["deposit_interest_rate_tiers"] = dumps({"tier1": "0.00"})
        checking_template_params["maintenance_fee_monthly"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}
        )

        sub_tests = [
            SubTest(
                description=(
                    "monthly maintainance fee not applied if minimum deposit waive criteria met"
                ),
                events=[
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(minutes=2),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    )
                ],
                expected_balances_at_ts={
                    # Maintenance fee will not have been applied
                    end: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "500.0"),
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
                checking_template_params=checking_template_params
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_monthly_maintenance_fee_not_applied_if_min_combined_balance_waive_criteria_met(
        self,
    ):
        start = datetime(year=2020, month=12, day=31, tzinfo=timezone.utc)
        end = datetime(year=2021, month=2, day=1, minute=2, tzinfo=timezone.utc)

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["deposit_tier_ranges"] = dumps({"tier1": {"min": "0"}})
        checking_template_params["deposit_interest_rate_tiers"] = dumps({"tier1": "0.00"})
        checking_template_params["maintenance_fee_monthly"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}
        )
        checking_template_params["minimum_deposit_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10000"}
        )
        checking_template_params["minimum_combined_balance_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "5000"}
        )

        savings_template_params = default_savings_template_params.copy()
        savings_template_params["tiered_interest_rates"] = ZERO_TIERED_INTEREST_RATES
        savings_template_params["maximum_daily_deposit"] = "4000"

        sub_tests = [
            SubTest(
                description=(
                    "monthly maintainance fee not applied if min combined bal waive criteria met"
                ),
                events=[
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(minutes=1),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "4000",
                        start + timedelta(minutes=10),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        # maintenance fee will not have been applied
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "1000"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "4000"),
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
                checking_template_params=checking_template_params,
                savings_template_params=savings_template_params,
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_monthly_maintenance_fee_applied_if_min_combined_balance_waive_criteria_not_met(
        self,
    ):
        start = datetime(year=2020, month=12, day=31, tzinfo=timezone.utc)
        end = datetime(year=2021, month=2, day=1, minute=2, tzinfo=timezone.utc)

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["deposit_tier_ranges"] = dumps({"tier1": {"min": "0"}})
        checking_template_params["deposit_interest_rate_tiers"] = dumps({"tier1": "0.00"})
        checking_template_params["maintenance_fee_monthly"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}
        )
        checking_template_params["minimum_deposit_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10000"}
        )
        checking_template_params["minimum_combined_balance_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "5001"}
        )

        savings_template_params = default_savings_template_params.copy()
        savings_template_params["tiered_interest_rates"] = ZERO_TIERED_INTEREST_RATES
        savings_template_params["maximum_daily_deposit"] = "4000"

        sub_tests = [
            SubTest(
                description=(
                    "monthly maintainance fee applied if min combined waive criteria not met"
                ),
                events=[
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(minutes=1),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "4000",
                        start + timedelta(minutes=10),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        # maintenance fee will have been applied
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "990"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "4000"),
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
                checking_template_params=checking_template_params,
                savings_template_params=savings_template_params,
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_standard_overdraft_daily_fee_gets_applied(self):
        start = datetime(year=2020, month=12, day=31, tzinfo=timezone.utc)
        end = datetime(year=2021, month=2, day=1, minute=5, tzinfo=timezone.utc)
        before_fee_application = datetime(year=2021, month=2, day=1, tzinfo=timezone.utc)

        checking_instance_params = default_checking_instance_params.copy()
        checking_instance_params["fee_free_overdraft_limit"] = "0"

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["standard_overdraft_per_transaction_fee"] = "0"
        checking_template_params["standard_overdraft_daily_fee"] = "10"
        checking_template_params["standard_overdraft_fee_cap"] = "0"
        checking_template_params["maintenance_fee_monthly"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "0"}
        )
        checking_template_params["overdraft_interest_rate"] = "0"

        sub_tests = [
            SubTest(
                description="standard overdraft daily fee gets applied",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "200",
                        start + timedelta(days=10),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    # standard_overdraft_daily_fee fees will have accrued 32 times and been applied
                    # standard_overdraft_daily_fee fees will have accrued but not yet applied
                    before_fee_application: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "-300"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_OVERDRAFT_FEE_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "-320",
                            ),
                        ],
                    },
                    # standard_overdraft_daily_fee fees will have accrued 32 times and been applied
                    end: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "-620"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_OVERDRAFT_FEE_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "0",
                            ),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                checking_instance_params=checking_instance_params,
                checking_template_params=checking_template_params,
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_dormant_account_monthly_fees(self):
        """
        Test that the monthly maintenance fee and the minimum account balance
        are not applied if account is dormant and that the dormancy fee is
        applied
        """
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        dormant = datetime(year=2021, month=1, day=3, tzinfo=timezone.utc)
        end = datetime(year=2021, month=3, day=1, tzinfo=timezone.utc)

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["maintenance_fee_monthly"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}
        )
        checking_template_params["minimum_balance_fee"] = "15"
        checking_template_params["minimum_balance_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "1001"}
        )
        checking_template_params["account_inactivity_fee"] = "99"
        checking_template_params["deposit_tier_ranges"] = dumps({"tier1": {"min": "0"}})
        checking_template_params["deposit_interest_rate_tiers"] = dumps({"tier1": "0.00"})

        sub_tests = [
            SubTest(
                description="dormant account monthly fees",
                events=[
                    create_flag_definition_event(
                        timestamp=start + timedelta(hours=1),
                        flag_definition_id=DORMANCY_FLAG,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(hours=2),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_flag_event(
                        timestamp=dormant,
                        expiry_timestamp=end,
                        flag_definition_id=DORMANCY_FLAG,
                        account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        # maintenance fee and minimum account balance fee not applied and dormancy
                        # fee applied
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "901"),
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
                checking_template_params=checking_template_params
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_savings_monthly_maint_fee_not_applied_if_min_combined_balance_waive_criteria_met(
        self,
    ):
        start = datetime(year=2020, month=12, day=31, tzinfo=timezone.utc)
        end = datetime(year=2021, month=2, day=1, minute=2, tzinfo=timezone.utc)

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["deposit_tier_ranges"] = dumps({"tier1": {"min": "0"}})
        checking_template_params["deposit_interest_rate_tiers"] = dumps({"tier1": "0.00"})
        checking_template_params["minimum_deposit_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10000"}
        )

        savings_template_params = default_savings_template_params.copy()
        savings_template_params["tiered_interest_rates"] = ZERO_TIERED_INTEREST_RATES
        savings_template_params["maximum_daily_deposit"] = "4000"
        savings_template_params["maintenance_fee_monthly"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "10"}
        )
        savings_template_params["minimum_combined_balance_threshold"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "5000"}
        )

        sub_tests = [
            SubTest(
                description=(
                    "savings monthly maint fee not applied if combined balance waive criteria met"
                ),
                events=[
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(minutes=1),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "4000",
                        start + timedelta(minutes=10),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        # maintenance fee will not have been applied
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "1000"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "4000"),
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
                checking_template_params=checking_template_params,
                savings_template_params=savings_template_params,
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_savings_monthly_maint_fee_applied_if_min_combined_balance_waive_criteria_not_met(
        self,
    ):
        start = datetime(year=2020, month=12, day=31, tzinfo=timezone.utc)
        end = datetime(year=2021, month=2, day=1, minute=2, tzinfo=timezone.utc)

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["deposit_tier_ranges"] = dumps({"tier1": {"min": "0"}})
        checking_template_params["deposit_interest_rate_tiers"] = dumps({"tier1": "0.00"})
        checking_template_params["minimum_deposit_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10000"}
        )

        savings_template_params = default_savings_template_params.copy()
        savings_template_params["tiered_interest_rates"] = ZERO_TIERED_INTEREST_RATES
        savings_template_params["maximum_daily_deposit"] = "4000"
        savings_template_params["maintenance_fee_monthly"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "10"}
        )
        savings_template_params["minimum_combined_balance_threshold"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "5000"}
        )

        sub_tests = [
            SubTest(
                description=(
                    "savings monthly maint fee applied if min combined bal waive criteria not met"
                ),
                events=[
                    create_inbound_hard_settlement_instruction(
                        "999",
                        start + timedelta(minutes=1),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "4000",
                        start + timedelta(minutes=10),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "999"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "3990"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_USD_DIMENSION, "10")],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                checking_template_params=checking_template_params,
                savings_template_params=savings_template_params,
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_savings_minimum_balance_fee_applied(self):
        start = datetime(year=2020, month=12, day=31, tzinfo=timezone.utc)
        end = datetime(year=2021, month=2, day=1, minute=2, tzinfo=timezone.utc)

        savings_template_params = default_savings_template_params.copy()
        savings_template_params["minimum_balance_fee"] = "150"
        savings_template_params["tiered_interest_rates"] = ZERO_TIERED_INTEREST_RATES

        sub_tests = [
            SubTest(
                description="check minimum maintainence fee applied on savings account",
                expected_balances_at_ts={
                    end: {
                        f"{SAVINGS_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "-150"),
                        ],
                        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (DEFAULT_USD_DIMENSION, "150"),
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
                savings_template_params=savings_template_params
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_old_account_added_to_existing_plan_with_no_supervisees(self):
        start = datetime(year=2021, month=10, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=12, day=3, tzinfo=timezone.utc)

        checking_account_id = f"{CHECKING_ACCOUNT} 0"
        checking_product_id = "1"
        savings_product_id = "2"
        plan_id = "1"
        supervisor_contract_version_id = "supervisor version 1"

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["maintenance_fee_monthly"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}
        )
        checking_template_params["fees_application_day"] = "2"
        checking_template_params["fees_application_hour"] = "1"
        checking_template_params["fees_application_minute"] = "2"
        checking_template_params["fees_application_second"] = "3"

        events = []

        # Account 1 created so it runs monthly schedule before being supervised
        events.append(
            create_account_instruction(
                timestamp=start,
                account_id=checking_account_id,
                product_id=checking_product_id,
                instance_param_vals=default_checking_instance_params,
            )
        )

        # Create the plan 2 months later
        events.append(
            create_plan_instruction(
                timestamp=start + timedelta(months=2, hour=18),
                plan_id=plan_id,
                supervisor_contract_version_id=supervisor_contract_version_id,
            )
        )

        # Link the account to the plan a few hours after plan creation
        events.append(
            create_account_plan_assoc_instruction(
                timestamp=start + timedelta(months=2, hour=20),
                assoc_id="Supervised " + checking_account_id,
                account_id=checking_account_id,
                plan_id=plan_id,
            )
        )

        supervisor_config = self._get_default_supervisor_config(
            checking_instances=1,
            savings_instances=1,
            checking_template_params=checking_template_params,
            savings_template_params=default_savings_template_params,
        )

        res = self.client.simulate_smart_contract(
            supervisor_contract_code=self.supervisor_contract_contents,
            supervisee_version_id_mapping=DEFAULT_SUPERVISEE_VERSION_IDS,
            contract_codes=[
                load_file_contents(self.checking_contract),
                load_file_contents(self.savings_contract),
            ],
            templates_parameters=[
                checking_template_params,
                default_savings_template_params,
            ],
            smart_contract_version_ids=[checking_product_id, savings_product_id],
            supervisor_contract_version_id=supervisor_contract_version_id,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            internal_account_ids=self.internal_accounts,
            supervisor_contract_config=supervisor_config,
        )

        expected_balances = {
            checking_account_id: {
                end: [
                    (BalanceDimensions(denomination="USD"), "-20"),
                ]
            }
        }
        self.check_balances(expected_balances, get_balances(res))

        supervisor_events = get_processed_scheduled_events(
            res, event_id="SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES", plan_id=plan_id
        )
        expected_events = [
            "2021-12-01T18:00:06Z",
            "2021-12-01T19:00:06Z",
            "2021-12-01T20:00:06Z",
            "2021-12-02T01:02:03Z",
        ]
        self.assertEqual(expected_events, supervisor_events)

        checking_events = get_processed_scheduled_events(
            res, event_id="APPLY_MONTHLY_FEES", account_id=checking_account_id
        )
        expected_events = ["2021-11-02T01:02:03Z", "2021-12-02T01:02:03Z"]
        self.assertEqual(expected_events, checking_events)

    def test_new_account_added_to_existing_plan_with_no_supervisees(self):
        start = datetime(year=2020, month=12, day=1, hour=16, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=3, tzinfo=timezone.utc)

        checking_account_id = f"{CHECKING_ACCOUNT} 0"
        savings_account_id = f"{SAVINGS_ACCOUNT} 0"
        checking_product_id = "1"
        savings_product_id = "2"
        plan_id = "1"
        supervisor_contract_version_id = "supervisor version 1"

        savings_template_params = default_savings_template_params.copy()
        savings_template_params["maintenance_fee_monthly"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "10"}
        )
        savings_template_params["fees_application_day"] = "2"
        savings_template_params["fees_application_hour"] = "1"
        savings_template_params["fees_application_minute"] = "2"
        savings_template_params["fees_application_second"] = "3"

        events = []

        # Create the plan
        events.append(
            create_plan_instruction(
                timestamp=start,
                plan_id=plan_id,
                supervisor_contract_version_id=supervisor_contract_version_id,
            )
        )

        # Account 1 created
        events.append(
            create_account_instruction(
                timestamp=start + timedelta(hours=2),
                account_id=savings_account_id,
                product_id=savings_product_id,
                instance_param_vals=default_savings_instance_params,
            )
        )

        # Create Checking account to stop hourly supervisor schedules
        events.append(
            create_account_instruction(
                timestamp=start + timedelta(hours=2, seconds=2),
                account_id=checking_account_id,
                product_id=checking_product_id,
                instance_param_vals=default_checking_instance_params,
            )
        )

        # Link the account to the plan a few minutes later
        events.append(
            create_account_plan_assoc_instruction(
                timestamp=start + timedelta(hours=2, minutes=5, second=0),
                assoc_id="Supervised " + savings_account_id,
                account_id=savings_account_id,
                plan_id=plan_id,
            )
        )

        # Link Checking account to stop hourly supervisor schedules for performance of test
        events.append(
            create_account_plan_assoc_instruction(
                timestamp=start + timedelta(hours=2, minutes=5, second=2),
                assoc_id="Supervised " + checking_account_id,
                account_id=checking_account_id,
                plan_id=plan_id,
            )
        )

        supervisor_config = self._get_default_supervisor_config(
            checking_instances=1,
            savings_instances=1,
            checking_template_params=default_checking_template_params,
            savings_template_params=savings_template_params,
        )

        res = self.client.simulate_smart_contract(
            supervisor_contract_code=self.supervisor_contract_contents,
            supervisee_version_id_mapping=DEFAULT_SUPERVISEE_VERSION_IDS,
            contract_codes=[
                load_file_contents(self.checking_contract),
                load_file_contents(self.savings_contract),
            ],
            templates_parameters=[
                default_checking_template_params,
                savings_template_params,
            ],
            smart_contract_version_ids=[checking_product_id, savings_product_id],
            supervisor_contract_version_id=supervisor_contract_version_id,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            internal_account_ids=self.internal_accounts,
            supervisor_contract_config=supervisor_config,
        )

        expected_balances = {
            savings_account_id: {
                end: [
                    (BalanceDimensions(denomination="USD"), "-10"),
                ]
            }
        }
        self.check_balances(expected_balances, get_balances(res))

        supervisor_events = get_processed_scheduled_events(
            res, event_id="SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES", plan_id=plan_id
        )
        expected_events = [
            "2020-12-01T16:00:06Z",
            "2020-12-01T17:00:06Z",
            "2020-12-01T18:00:06Z",
            "2020-12-01T19:00:06Z",
            "2021-01-02T01:02:03Z",
        ]
        self.assertEqual(expected_events, supervisor_events)

        savings_events = get_processed_scheduled_events(
            res, event_id="APPLY_MONTHLY_FEES", account_id=savings_account_id
        )
        expected_events = ["2021-01-02T01:02:03Z"]
        self.assertEqual(expected_events, savings_events)

        supervisor_checking_events = get_processed_scheduled_events(
            res, event_id="SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES", plan_id=plan_id
        )
        expected_events = [
            "2020-12-01T16:00:06Z",
            "2020-12-01T17:00:06Z",
            "2020-12-01T18:00:06Z",
            "2020-12-01T19:00:06Z",
        ]
        self.assertEqual(expected_events, supervisor_checking_events)

    def test_old_account_added_to_plan_that_already_has_supervisee(self):
        start = datetime(year=2020, month=11, day=1, hour=16, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=3, hour=2, tzinfo=timezone.utc)

        checking_account_id = f"{CHECKING_ACCOUNT} 0"
        savings_account_id = f"{SAVINGS_ACCOUNT} 0"
        checking_product_id = "1"
        savings_product_id = "2"
        plan_id = "1"
        supervisor_contract_version_id = "supervisor version 1"

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["maintenance_fee_monthly"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}
        )
        checking_template_params["fees_application_day"] = "3"
        checking_template_params["fees_application_hour"] = "1"
        checking_template_params["fees_application_minute"] = "2"
        checking_template_params["fees_application_second"] = "3"

        savings_template_params = default_savings_template_params.copy()
        savings_template_params["maintenance_fee_monthly"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "10"}
        )
        savings_template_params["fees_application_day"] = "2"
        savings_template_params["fees_application_hour"] = "1"
        savings_template_params["fees_application_minute"] = "2"
        savings_template_params["fees_application_second"] = "3"

        events = []

        # Account 2 created
        events.append(
            create_account_instruction(
                timestamp=start,
                account_id=savings_account_id,
                product_id=savings_product_id,
                instance_param_vals=default_savings_instance_params,
            )
        )

        # Account 1 created
        events.append(
            create_account_instruction(
                timestamp=start + timedelta(months=1, days=1),
                account_id=checking_account_id,
                product_id=checking_product_id,
                instance_param_vals=default_checking_instance_params,
            )
        )

        # Create the plan
        events.append(
            create_plan_instruction(
                timestamp=start + timedelta(months=1, days=1, seconds=2),
                plan_id=plan_id,
                supervisor_contract_version_id=supervisor_contract_version_id,
            )
        )

        # Link the account to the plan
        events.append(
            create_account_plan_assoc_instruction(
                timestamp=start + timedelta(months=1, days=1, seconds=4),
                assoc_id="Supervised " + checking_account_id,
                account_id=checking_account_id,
                plan_id=plan_id,
            )
        )

        # Link Account 2 to the plan after it has done first fee date
        events.append(
            create_account_plan_assoc_instruction(
                timestamp=start + timedelta(months=1, days=2, seconds=4),
                assoc_id="Supervised " + savings_account_id,
                account_id=savings_account_id,
                plan_id=plan_id,
            )
        )

        supervisor_config = self._get_default_supervisor_config(
            checking_instances=1,
            savings_instances=1,
            checking_template_params=checking_template_params,
            savings_template_params=savings_template_params,
        )

        res = self.client.simulate_smart_contract(
            supervisor_contract_code=self.supervisor_contract_contents,
            supervisee_version_id_mapping=DEFAULT_SUPERVISEE_VERSION_IDS,
            contract_codes=[
                load_file_contents(self.checking_contract),
                load_file_contents(self.savings_contract),
            ],
            templates_parameters=[checking_template_params, savings_template_params],
            smart_contract_version_ids=[checking_product_id, savings_product_id],
            supervisor_contract_version_id=supervisor_contract_version_id,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            internal_account_ids=self.internal_accounts,
            supervisor_contract_config=supervisor_config,
        )

        expected_balances = {
            checking_account_id: {
                end: [
                    (BalanceDimensions(denomination="USD"), "-10"),
                ]
            },
            savings_account_id: {
                end: [
                    (BalanceDimensions(denomination="USD"), "-20"),
                ]
            },
        }
        self.check_balances(expected_balances, get_balances(res))

        supervisor_events = get_processed_scheduled_events(
            res, event_id="SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES", plan_id=plan_id
        )
        expected_events = ["2020-12-02T16:00:08Z", "2021-01-03T01:02:03Z"]
        self.assertEqual(expected_events, supervisor_events)

        checking_events = get_processed_scheduled_events(
            res, event_id="APPLY_MONTHLY_FEES", account_id=checking_account_id
        )
        expected_events = ["2021-01-03T01:02:03Z"]
        self.assertEqual(expected_events, checking_events)

        savings_events = get_processed_scheduled_events(
            res, event_id="APPLY_MONTHLY_FEES", account_id=savings_account_id
        )
        expected_events = ["2020-12-02T01:02:03Z", "2021-01-02T01:02:03Z"]
        self.assertEqual(expected_events, savings_events)

    def test_new_account_added_to_plan_that_already_has_supervisee(self):
        start = datetime(year=2020, month=12, day=1, hour=16, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=3, hour=2, tzinfo=timezone.utc)

        checking_account_id = f"{CHECKING_ACCOUNT} 0"
        savings_account_id = f"{SAVINGS_ACCOUNT} 0"
        savings2_account_id = f"{SAVINGS_ACCOUNT} 1"
        checking_product_id = "1"
        savings_product_id = "2"
        plan_id = "1"
        supervisor_contract_version_id = "supervisor version 1"

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["maintenance_fee_monthly"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}
        )
        checking_template_params["fees_application_day"] = "3"
        checking_template_params["fees_application_hour"] = "1"
        checking_template_params["fees_application_minute"] = "2"
        checking_template_params["fees_application_second"] = "3"

        savings_template_params = default_savings_template_params.copy()
        savings_template_params["maintenance_fee_monthly"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "10"}
        )
        savings_template_params["fees_application_day"] = "3"
        savings_template_params["fees_application_hour"] = "1"
        savings_template_params["fees_application_minute"] = "2"
        savings_template_params["fees_application_second"] = "3"

        events = []

        # Account 1 created
        events.append(
            create_account_instruction(
                timestamp=start,
                account_id=checking_account_id,
                product_id=checking_product_id,
                instance_param_vals=default_checking_instance_params,
            )
        )

        # Create savings account just to stop hourly schedules for test performance
        events.append(
            create_account_instruction(
                timestamp=start + timedelta(seconds=2),
                account_id=savings2_account_id,
                product_id=savings_product_id,
                instance_param_vals=default_savings_instance_params,
            )
        )

        # Create the plan
        events.append(
            create_plan_instruction(
                timestamp=start + timedelta(seconds=4),
                plan_id=plan_id,
                supervisor_contract_version_id=supervisor_contract_version_id,
            )
        )

        # Link the accounts to the plan
        events.append(
            create_account_plan_assoc_instruction(
                timestamp=start + timedelta(seconds=6),
                assoc_id="Supervised " + checking_account_id,
                account_id=checking_account_id,
                plan_id=plan_id,
            )
        )
        events.append(
            create_account_plan_assoc_instruction(
                timestamp=start + timedelta(seconds=8),
                assoc_id="Supervised " + savings2_account_id,
                account_id=savings2_account_id,
                plan_id=plan_id,
            )
        )

        # Account 2 created
        events.append(
            create_account_instruction(
                timestamp=start + timedelta(days=10, seconds=4),
                account_id=savings_account_id,
                product_id=savings_product_id,
                instance_param_vals=default_savings_instance_params,
            )
        )

        # Link Account 2 to the plan
        events.append(
            create_account_plan_assoc_instruction(
                timestamp=start + timedelta(days=10, seconds=4),
                assoc_id="Supervised " + savings_account_id,
                account_id=savings_account_id,
                plan_id=plan_id,
            )
        )

        supervisor_config = self._get_default_supervisor_config(
            checking_instances=1,
            savings_instances=1,
            checking_template_params=checking_template_params,
            savings_template_params=savings_template_params,
        )

        res = self.client.simulate_smart_contract(
            supervisor_contract_code=self.supervisor_contract_contents,
            supervisee_version_id_mapping=DEFAULT_SUPERVISEE_VERSION_IDS,
            contract_codes=[
                load_file_contents(self.checking_contract),
                load_file_contents(self.savings_contract),
            ],
            templates_parameters=[checking_template_params, savings_template_params],
            smart_contract_version_ids=[checking_product_id, savings_product_id],
            supervisor_contract_version_id=supervisor_contract_version_id,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            internal_account_ids=self.internal_accounts,
            supervisor_contract_config=supervisor_config,
        )

        expected_balances = {
            checking_account_id: {
                end: [
                    (BalanceDimensions(denomination="USD"), "-10"),
                ]
            },
            savings_account_id: {
                end: [
                    (BalanceDimensions(denomination="USD"), "0"),
                ]
            },
        }
        self.check_balances(expected_balances, get_balances(res))

        supervisor_events = get_processed_scheduled_events(
            res, event_id="SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES", plan_id=plan_id
        )
        expected_events = ["2020-12-01T16:00:10Z", "2021-01-03T01:02:03Z"]
        self.assertEqual(expected_events, supervisor_events)

        checking_events = get_processed_scheduled_events(
            res, event_id="APPLY_MONTHLY_FEES", account_id=checking_account_id
        )
        expected_events = ["2021-01-03T01:02:03Z"]
        self.assertEqual(expected_events, checking_events)

        savings_events = get_processed_scheduled_events(
            res, event_id="APPLY_MONTHLY_FEES", account_id=savings_account_id
        )
        expected_events = []
        self.assertEqual(expected_events, savings_events)

    def test_3_checking_multiple_savings_monthly_fees(self):
        start = datetime(year=2020, month=12, day=31, tzinfo=timezone.utc)
        end = datetime(year=2021, month=4, day=2, minute=2, tzinfo=timezone.utc)

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["deposit_tier_ranges"] = dumps({"tier1": {"min": "0"}})
        checking_template_params["deposit_interest_rate_tiers"] = dumps({"tier1": "0.00"})
        checking_template_params["minimum_deposit_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10000"}
        )
        checking_template_params["maintenance_fee_monthly"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}
        )
        checking_template_params["minimum_combined_balance_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "5000"}
        )
        checking_template_params["minimum_balance_fee"] = "0"
        checking_template_params["minimum_balance_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "20000"}
        )
        checking_template_params["fees_application_day"] = "1"

        savings_template_params = default_savings_template_params.copy()
        savings_template_params["tiered_interest_rates"] = ZERO_TIERED_INTEREST_RATES
        savings_template_params["maximum_daily_deposit"] = "0"
        savings_template_params["maximum_balance"] = "0"
        savings_template_params["maintenance_fee_monthly"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "10"}
        )
        savings_template_params["minimum_combined_balance_threshold"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "6000"}
        )
        savings_template_params["minimum_balance_fee"] = "0"
        savings_template_params["tiered_minimum_balance_threshold"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "2000"}
        )
        savings_template_params["fees_application_day"] = "2"

        sub_tests = [
            SubTest(
                description="checking multiple savings monthly fee",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(minutes=1),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(minutes=2),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(minutes=3),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(minutes=4),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{SAVINGS_ACCOUNT} 1",
                    ),
                    # After 1st fees date
                    # Checking Account 0 : balance 1000 - maintenance_fee_monthly 10
                    # Checking Account 1 : balance 500 - maintenance_fee_monthly 10
                    # Checking Account 2 : balance 0 - maintenance_fee_monthly 10
                    # Savings Account 0 : balance 1000 - maintenance_fee_monthly 10
                    # Savings Account 1 : balance 500 - maintenance_fee_monthly 10
                    # Savings Account 2 : balance 0 - maintenance_fee_monthly 10
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(months=1, days=2, minutes=1),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(months=1, days=2, minutes=2),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 2",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(months=1, days=2, minutes=3),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{SAVINGS_ACCOUNT} 1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(months=1, days=2, minutes=4),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{SAVINGS_ACCOUNT} 2",
                    ),
                    # After 2nd fees date
                    # Checking Account 0 : balance 990 - maintenance_fee_monthly waivered
                    # Checking Account 1 : balance 1490 - maintenance_fee_monthly waivered
                    # Checking Account 2 : balance 490 - maintenance_fee_monthly waivered
                    # Savings Account 0 : balance 990 - maintenance_fee_monthly 10
                    # Savings Account 1 : balance 1490 - maintenance_fee_monthly 10
                    # Savings Account 2 : balance 490 - maintenance_fee_monthly 10
                    # Total : 5,910
                    create_inbound_hard_settlement_instruction(
                        "300",
                        start + timedelta(months=2, days=2, minutes=6),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{SAVINGS_ACCOUNT} 2",
                    ),
                    # After 3rd fees date, as above except
                    # Savings Account 2 : balance 780 - maintenance_fee_monthly waivered
                ],
                expected_balances_at_ts={
                    end: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "990"),
                        ],
                        f"{CHECKING_ACCOUNT} 1": [
                            (DEFAULT_USD_DIMENSION, "1490"),
                        ],
                        f"{CHECKING_ACCOUNT} 2": [
                            (DEFAULT_USD_DIMENSION, "490"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "980"),
                        ],
                        f"{SAVINGS_ACCOUNT} 1": [
                            (DEFAULT_USD_DIMENSION, "1480"),
                        ],
                        f"{SAVINGS_ACCOUNT} 2": [
                            (DEFAULT_USD_DIMENSION, "780"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (DEFAULT_USD_DIMENSION, "90"),
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
                checking_template_params=checking_template_params,
                checking_instances=3,
                savings_template_params=savings_template_params,
                savings_instances=3,
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_1_checking_multiple_savings_monthly_fees(self):
        start = datetime(year=2020, month=12, day=31, tzinfo=timezone.utc)
        end = datetime(year=2021, month=4, day=2, minute=2, tzinfo=timezone.utc)

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["deposit_tier_ranges"] = dumps({"tier1": {"min": "0"}})
        checking_template_params["deposit_interest_rate_tiers"] = dumps({"tier1": "0.00"})
        checking_template_params["minimum_deposit_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10000"}
        )
        checking_template_params["maintenance_fee_monthly"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}
        )
        checking_template_params["minimum_combined_balance_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "5000"}
        )
        checking_template_params["minimum_balance_fee"] = "0"
        checking_template_params["minimum_balance_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "20000"}
        )
        checking_template_params["fees_application_day"] = "1"

        savings_template_params = default_savings_template_params.copy()
        savings_template_params["tiered_interest_rates"] = ZERO_TIERED_INTEREST_RATES
        savings_template_params["maximum_daily_deposit"] = "0"
        savings_template_params["maximum_balance"] = "0"
        savings_template_params["maintenance_fee_monthly"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "10"}
        )
        savings_template_params["minimum_combined_balance_threshold"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "6000"}
        )
        savings_template_params["minimum_balance_fee"] = "0"
        savings_template_params["tiered_minimum_balance_threshold"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "2000"}
        )
        savings_template_params["fees_application_day"] = "2"

        sub_tests = [
            SubTest(
                description="checking multiple savings monthly fees",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(minutes=3),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(minutes=4),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{SAVINGS_ACCOUNT} 1",
                    ),
                    # After 1st fees date
                    # Checking Account 0 : balance 0 - maintenance_fee_monthly 10
                    # Savings Account 0 : balance 1000 - maintenance_fee_monthly 10
                    # Savings Account 1 : balance 500 - maintenance_fee_monthly 10
                    # Total : 1,470
                    create_inbound_hard_settlement_instruction(
                        "1010",
                        start + timedelta(months=1, minutes=1),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "2130",
                        start + timedelta(months=1, minutes=3),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(months=1, minutes=4),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{SAVINGS_ACCOUNT} 1",
                    ),
                    # After 2nd fees date
                    # Checking Account 0 : balance 1000 - maintenance_fee_monthly waivered
                    # Savings Account 0 : balance 3120 - maintenance_fee_monthly 10
                    # Savings Account 1 : balance 990 - maintenance_fee_monthly 10
                    # Total : 5,090
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(months=2, minutes=6),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    )
                    # After 3rd fees date, as above except
                    # Savings Account 0 : balance 4120 - maintenance_fee_monthly waivered
                ],
                expected_balances_at_ts={
                    end: {
                        f"{CHECKING_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "1000"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [
                            (DEFAULT_USD_DIMENSION, "4110"),
                        ],
                        f"{SAVINGS_ACCOUNT} 1": [
                            (DEFAULT_USD_DIMENSION, "980"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (DEFAULT_USD_DIMENSION, "50"),
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
                checking_template_params=checking_template_params,
                savings_template_params=savings_template_params,
                savings_instances=2,
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_multiple_checking_1_savings_monthly_fees(self):
        start = datetime(year=2020, month=12, day=31, tzinfo=timezone.utc)
        end = datetime(year=2021, month=4, day=2, minute=2, tzinfo=timezone.utc)

        checking_template_params = default_checking_template_params.copy()
        checking_template_params["deposit_tier_ranges"] = dumps({"tier1": {"min": "0"}})
        checking_template_params["deposit_interest_rate_tiers"] = dumps({"tier1": "0.00"})
        checking_template_params["minimum_deposit_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10000"}
        )
        checking_template_params["maintenance_fee_monthly"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}
        )
        checking_template_params["minimum_combined_balance_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "5000"}
        )
        checking_template_params["minimum_balance_fee"] = "0"
        checking_template_params["minimum_balance_threshold"] = dumps(
            {"US_CHECKING_ACCOUNT_TIER_LOWER": "20000"}
        )
        checking_template_params["fees_application_day"] = "1"

        savings_template_params = default_savings_template_params.copy()
        savings_template_params["tiered_interest_rates"] = ZERO_TIERED_INTEREST_RATES
        savings_template_params["maximum_daily_deposit"] = "0"
        savings_template_params["maximum_balance"] = "0"
        savings_template_params["maintenance_fee_monthly"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "10"}
        )
        savings_template_params["minimum_combined_balance_threshold"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "6000"}
        )
        savings_template_params["minimum_balance_fee"] = "0"
        savings_template_params["tiered_minimum_balance_threshold"] = dumps(
            {"US_SAVINGS_ACCOUNT_TIER_LOWER": "2000"}
        )
        savings_template_params["fees_application_day"] = "2"

        sub_tests = [
            SubTest(
                description="multiple checking and one savings account monthly fees",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(minutes=3),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(minutes=4),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                    # After 1st fees date
                    # Checking Account 0 : balance 1000 - maintenance_fee_monthly 10
                    # Checking Account 1 : balance 0 - maintenance_fee_monthly 10
                    # Savings Account 0 : balance 500 - maintenance_fee_monthly 10
                    # Total : 1,470
                    create_inbound_hard_settlement_instruction(
                        "2000",
                        start + timedelta(months=1, minutes=1),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(months=1, minutes=3),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{CHECKING_ACCOUNT} 1",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "530",
                        start + timedelta(months=1, minutes=4),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                    # After 2nd fees date
                    # Checking Account 0 : balance 2990 - maintenance_fee_monthly waivered
                    # Checking Account 1 : balance 990 - maintenance_fee_monthly waivered
                    # Savings Account 0 : balance 1020 - maintenance_fee_monthly 10
                    # Total : 4,990
                    create_inbound_hard_settlement_instruction(
                        "1010",
                        start + timedelta(months=2, minutes=6),
                        denomination=DEFAULT_DENOMINATION,
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    )
                    # After 3rd fees date, as above except
                    # Savings Account 0 : balance 2020 - maintenance_fee_monthly waivered
                ],
                expected_balances_at_ts={
                    end: {
                        f"{CHECKING_ACCOUNT} 0": {
                            (DEFAULT_USD_DIMENSION, "2990"),
                        },
                        f"{CHECKING_ACCOUNT} 1": {
                            (DEFAULT_USD_DIMENSION, "990"),
                        },
                        f"{SAVINGS_ACCOUNT} 0": {
                            (DEFAULT_USD_DIMENSION, "2020"),
                        },
                        MAINTENANCE_FEE_INCOME_ACCOUNT: {
                            (DEFAULT_USD_DIMENSION, "40"),
                        },
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                checking_template_params=checking_template_params,
                checking_instances=2,
                savings_template_params=savings_template_params,
            ),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)
