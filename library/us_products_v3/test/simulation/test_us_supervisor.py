# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta as timedelta
from json import dumps
from uuid import uuid4

# library
from library.us_products_v3.constants.files import (
    US_CHECKING_TEMPLATE,
    US_SAVINGS_TEMPLATE,
    US_SUPERVISOR_TEMPLATE,
)

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractModuleConfig,
    ExpectedSchedule,
    SimulationTestScenario,
    SubTest,
    SupervisorConfig,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_instruction,
    create_account_plan_assoc_instruction,
    create_custom_instruction,
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
    create_outbound_authorisation_instruction,
    create_outbound_hard_settlement_instruction,
    create_plan_instruction,
    create_posting_instruction_batch,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    ExpectedRejection,
    SimulationTestCase,
    get_balances,
    get_processed_scheduled_events,
)
from inception_sdk.vault.postings.posting_classes import OutboundHardSettlement

# $ US constants
ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"
CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "interest": "library/common/contract_modules/interest.py",
    "utils": "library/common/contract_modules/utils.py",
}

CHECKING_ACCOUNT = "Checking Account"
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
INACTIVITY_FEE_INCOME_ACCOUNT = "INACTIVITY_FEE_INCOME"
PROMOTIONAL_MAINTENANCE_FEE = "PROMOTIONAL_MAINTENANCE_FEE"
INTERNAL_CONTRA = "INTERNAL_CONTRA"
PHASE_PENDING_OUT = "POSTING_PHASE_PENDING_OUTGOING"

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
    "inactivity_fee_income_account": INACTIVITY_FEE_INCOME_ACCOUNT,
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
    "overdraft_protection_sweep_hour": "0",
    "overdraft_protection_sweep_minute": "0",
    "overdraft_protection_sweep_second": "0",
}

BALANCE_TIER_RANGES = dumps(
    {
        "tier1": {"min": "0", "max": "15000.00"},
        "tier2": {"min": "15000.00"},
    }
)
TIERED_INTEREST_RATES = dumps(
    {
        "UPPER_TIER": {"tier1": "0.02", "tier2": "0.015"},
        "MIDDLE_TIER": {"tier1": "0.0125", "tier2": "0.01"},
        "LOWER_TIER": {"tier1": "0.149", "tier2": "-0.1485"},
    }
)
TIERED_MIN_BALANCE_THRESHOLD = dumps(
    {
        "UPPER_TIER": "25",
        "MIDDLE_TIER": "75",
        "LOWER_TIER": "100",
    }
)
ZERO_TIERED_MAINTENANCE_FEE_MONTHLY = dumps(
    {
        "UPPER_TIER": "0",
        "MIDDLE_TIER": "0",
        "LOWER_TIER": "0",
    }
)
ACCOUNT_TIER_NAMES = dumps(
    [
        "UPPER_TIER",
        "MIDDLE_TIER",
        "LOWER_TIER",
    ]
)
ZERO_TIERED_INTEREST_RATES = dumps(
    {
        "UPPER_TIER": {"tier1": "0", "tier2": "0"},
        "MIDDLE_TIER": {"tier1": "0", "tier2": "0"},
        "LOWER_TIER": {"tier1": "0", "tier2": "0"},
    }
)

default_savings_instance_params = {"interest_application_day": "5"}
default_savings_template_params = {
    "denomination": "USD",
    "balance_tier_ranges": BALANCE_TIER_RANGES,
    "tiered_interest_rates": TIERED_INTEREST_RATES,
    "minimum_combined_balance_threshold": dumps(
        {
            "UPPER_TIER": "3000",
            "MIDDLE_TIER": "4000",
            "LOWER_TIER": "5000",
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

CHECKING_ACCOUNT_ALIAS = "us_checking_account_v3"
SAVINGS_ACCOUNT_ALIAS = "us_savings_account_v3"
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
        INACTIVITY_FEE_INCOME_ACCOUNT: "LIABILITY",
        # This is a generic account used for external postings
        "1": "LIABILITY",
    }

    @classmethod
    def setUpClass(cls):
        cls.DEFAULT_SUPERVISEE_VERSION_IDS = {
            CHECKING_ACCOUNT_ALIAS: "1",
            SAVINGS_ACCOUNT_ALIAS: "2",
        }
        cls.contract_modules_savings = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
        ]
        cls.contract_modules_checking = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
            if alias != "utils"
        ]
        cls.contract_filepaths = [US_CHECKING_TEMPLATE, US_SAVINGS_TEMPLATE, US_SUPERVISOR_TEMPLATE]
        super().setUpClass()

    def _get_default_supervisor_config(
        self,
        checking_instance_params=default_checking_instance_params,
        checking_template_params=default_checking_template_params,
        checking_instances=1,
        savings_instance_params=default_savings_instance_params,
        savings_template_params=default_savings_template_params,
        savings_instances=1,
    ):
        checking_supervisee = ContractConfig(
            template_params=checking_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=checking_instance_params,
                    account_id_base=f"{CHECKING_ACCOUNT} ",
                    number_of_accounts=checking_instances,
                )
            ],
            contract_content=self.smart_contract_path_to_content[US_CHECKING_TEMPLATE],
            clu_resource_id="us_checking_account_v3",
            smart_contract_version_id=self.DEFAULT_SUPERVISEE_VERSION_IDS["us_checking_account_v3"],
            linked_contract_modules=self.contract_modules_checking,
        )
        savings_supervisee = ContractConfig(
            template_params=savings_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=savings_instance_params,
                    account_id_base=f"{SAVINGS_ACCOUNT} ",
                    number_of_accounts=savings_instances,
                )
            ],
            contract_content=self.smart_contract_path_to_content[US_SAVINGS_TEMPLATE],
            clu_resource_id="us_savings_account_v3",
            smart_contract_version_id=self.DEFAULT_SUPERVISEE_VERSION_IDS["us_savings_account_v3"],
            linked_contract_modules=self.contract_modules_savings,
        )

        supervisor_config = SupervisorConfig(
            supervisor_contract=self.smart_contract_path_to_content[US_SUPERVISOR_TEMPLATE],
            supervisee_contracts=[
                checking_supervisee,
                savings_supervisee,
            ],
            supervisor_contract_version_id="supervisor version 1",
            plan_id="1",
        )

        return supervisor_config

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
                        rejection_reason=("Multiple checking accounts not supported."),
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
            "Multiple checking accounts not supported.",
            str(ex.exception),
        )

    def test_multiple_supervisee_savings_accounts_in_post_posting(self):
        start = datetime(year=2021, month=1, day=10, tzinfo=timezone.utc)
        end = start + timedelta(hours=5)

        withdrawal_instruction_1 = OutboundHardSettlement(
            "100", target_account_id=f"{SAVINGS_ACCOUNT} 0", denomination="USD"
        )

        withdrawal_instruction_2 = OutboundHardSettlement(
            "100", target_account_id=f"{SAVINGS_ACCOUNT} 1", denomination="USD"
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
                        rejection_reason=("Multiple savings accounts not supported."),
                    )
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(savings_instances=2),
            internal_accounts=self.internal_accounts,
        )

        with self.assertRaises(Exception) as ex:
            self.run_test_scenario(test_scenario)

        self.assertIn(
            "Multiple savings accounts not supported.",
            str(ex.exception),
        )

    def test_overdraft_transaction_fee_logic_in_standard_overdraft(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=2, minute=10, tzinfo=timezone.utc)

        # set standard_overdraft_fee_cap to 0 to test it is unlimited
        checking_template_params = {
            **default_checking_template_params,
            "standard_overdraft_per_transaction_fee": "34",
            "standard_overdraft_fee_cap": "0",
        }

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

        checking_template_params = {
            **default_checking_template_params,
            "standard_overdraft_per_transaction_fee": "10",
            "standard_overdraft_fee_cap": "12",
        }

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

        checking_instance_params = {
            **default_checking_instance_params,
            "autosave_savings_account": f"{SAVINGS_ACCOUNT} 0",
        }
        checking_template_params = {
            **default_checking_template_params,
            "autosave_rounding_amount": "1.00",
            "denomination": "USD",
            "additional_denominations": dumps(["USD", "EUR"]),
        }

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

        checking_instance_params = {
            **default_checking_instance_params,
            "autosave_savings_account": f"{SAVINGS_ACCOUNT} 0",
        }
        checking_template_params = {
            **default_checking_template_params,
            "autosave_rounding_amount": "1.00",
            "denomination": "USD",
            "minimum_balance_fee": "50",
        }

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

        checking_template_params = {
            **default_checking_template_params,
            "minimum_balance_fee": "10",
            "tier_names": dumps(["X", "Y", "Z"]),
            "minimum_balance_threshold": dumps({"X": "1.5", "Y": "100", "Z": "200"}),
            "minimum_deposit_threshold": dumps({"Z": "500"}),
            "maintenance_fee_monthly": dumps({"Z": "10"}),
            "minimum_combined_balance_threshold": dumps({"Z": "5000"}),
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
        }

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

        checking_template_params = {
            **default_checking_template_params,
            "maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}),
            "fees_application_day": "2",
            "fees_application_hour": "17",
            "fees_application_minute": "30",
            "fees_application_second": "30",
        }

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

        checking_template_params = {
            **default_checking_template_params,
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
            "maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}),
        }

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

        checking_template_params = {
            **default_checking_template_params,
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
            "maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}),
            "minimum_deposit_threshold": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "10000"}),
            "minimum_combined_balance_threshold": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "5000"}),
        }
        savings_template_params = {
            **default_savings_template_params,
            "tiered_interest_rates": ZERO_TIERED_INTEREST_RATES,
            "maximum_daily_deposit": "4000",
        }

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

        checking_template_params = {
            **default_checking_template_params,
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
            "maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}),
            "minimum_combined_balance_threshold": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "5001"}),
        }
        savings_template_params = {
            **default_savings_template_params,
            "tiered_interest_rates": ZERO_TIERED_INTEREST_RATES,
            "maximum_daily_deposit": "4000",
        }

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

        checking_instance_params = {
            **default_checking_instance_params,
            "fee_free_overdraft_limit": "0",
        }
        checking_template_params = {
            **default_checking_template_params,
            "standard_overdraft_per_transaction_fee": "0",
            "standard_overdraft_daily_fee": "10",
            "standard_overdraft_fee_cap": "0",
            "maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "0"}),
        }

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

        checking_template_params = {
            **default_checking_template_params,
            "maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}),
            "minimum_balance_fee": "15",
            "minimum_balance_threshold": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "1001"}),
            "account_inactivity_fee": "99",
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
        }

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

        checking_template_params = {
            **default_checking_template_params,
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
            "minimum_deposit_threshold": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "10000"}),
        }
        savings_template_params = {
            **default_savings_template_params,
            "tiered_interest_rates": ZERO_TIERED_INTEREST_RATES,
            "maximum_daily_deposit": "4000",
            "maintenance_fee_monthly": dumps({"LOWER_TIER": "10"}),
            "minimum_combined_balance_threshold": dumps({"LOWER_TIER": "5000"}),
        }

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

        checking_template_params = {
            **default_checking_template_params,
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
            "minimum_deposit_threshold": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "10000"}),
        }
        savings_template_params = {
            **default_savings_template_params,
            "tiered_interest_rates": ZERO_TIERED_INTEREST_RATES,
            "maximum_daily_deposit": "4000",
            "maintenance_fee_monthly": dumps({"LOWER_TIER": "10"}),
            "minimum_combined_balance_threshold": dumps({"LOWER_TIER": "5000"}),
        }

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

        savings_template_params = {
            **default_savings_template_params,
            "minimum_balance_fee": "150",
            "tiered_interest_rates": ZERO_TIERED_INTEREST_RATES,
        }

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

        checking_template_params = {
            **default_checking_template_params,
            "maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}),
            "fees_application_day": "2",
            "fees_application_hour": "1",
            "fees_application_minute": "2",
            "fees_application_second": "3",
        }

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
            supervisor_contract_code=self.smart_contract_path_to_content[US_SUPERVISOR_TEMPLATE],
            supervisee_version_id_mapping=DEFAULT_SUPERVISEE_VERSION_IDS,
            contract_codes=[
                self.smart_contract_path_to_content[US_CHECKING_TEMPLATE],
                self.smart_contract_path_to_content[US_SAVINGS_TEMPLATE],
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
            "2021-12-01T18:00:30Z",
            "2021-12-01T19:00:30Z",
            "2021-12-01T20:00:30Z",
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

        savings_template_params = {
            **default_savings_template_params,
            "maintenance_fee_monthly": dumps({"LOWER_TIER": "10"}),
            "fees_application_day": "2",
            "fees_application_hour": "1",
            "fees_application_minute": "2",
            "fees_application_second": "3",
        }

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
            supervisor_contract_code=self.smart_contract_path_to_content[US_SUPERVISOR_TEMPLATE],
            supervisee_version_id_mapping=DEFAULT_SUPERVISEE_VERSION_IDS,
            contract_codes=[
                self.smart_contract_path_to_content[US_CHECKING_TEMPLATE],
                self.smart_contract_path_to_content[US_SAVINGS_TEMPLATE],
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
            "2020-12-01T16:00:30Z",
            "2020-12-01T17:00:30Z",
            "2020-12-01T18:00:30Z",
            "2020-12-01T19:00:30Z",
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
            "2020-12-01T16:00:30Z",
            "2020-12-01T17:00:30Z",
            "2020-12-01T18:00:30Z",
            "2020-12-01T19:00:30Z",
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

        checking_template_params = {
            **default_checking_template_params,
            "maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}),
            "fees_application_day": "3",
            "fees_application_hour": "1",
            "fees_application_minute": "2",
            "fees_application_second": "3",
        }
        savings_template_params = {
            **default_savings_template_params,
            "maintenance_fee_monthly": dumps({"LOWER_TIER": "10"}),
            "fees_application_day": "2",
            "fees_application_hour": "1",
            "fees_application_minute": "2",
            "fees_application_second": "3",
        }

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
            supervisor_contract_code=self.smart_contract_path_to_content[US_SUPERVISOR_TEMPLATE],
            supervisee_version_id_mapping=DEFAULT_SUPERVISEE_VERSION_IDS,
            contract_codes=[
                self.smart_contract_path_to_content[US_CHECKING_TEMPLATE],
                self.smart_contract_path_to_content[US_SAVINGS_TEMPLATE],
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
        expected_events = ["2020-12-02T16:00:32Z", "2021-01-03T01:02:03Z"]
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

        checking_template_params = {
            **default_checking_template_params,
            "maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}),
            "fees_application_day": "3",
            "fees_application_hour": "1",
            "fees_application_minute": "2",
            "fees_application_second": "3",
        }
        savings_template_params = {
            **default_savings_template_params,
            "maintenance_fee_monthly": dumps({"LOWER_TIER": "10"}),
            "fees_application_day": "3",
            "fees_application_hour": "1",
            "fees_application_minute": "2",
            "fees_application_second": "3",
        }

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

        supervisor_config = self._get_default_supervisor_config(
            checking_template_params=checking_template_params,
            savings_template_params=savings_template_params,
        )

        res = self.client.simulate_smart_contract(
            supervisor_contract_code=self.smart_contract_path_to_content[US_SUPERVISOR_TEMPLATE],
            supervisee_version_id_mapping=DEFAULT_SUPERVISEE_VERSION_IDS,
            contract_codes=[
                self.smart_contract_path_to_content[US_CHECKING_TEMPLATE],
                self.smart_contract_path_to_content[US_SAVINGS_TEMPLATE],
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
        expected_events = ["2020-12-01T16:00:34Z", "2021-01-03T01:02:03Z"]
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

    def test_INC_5886_AC2_performing_a_sweep_to_cover_a_transaction(self):
        start = datetime(year=2022, month=1, day=10, tzinfo=timezone.utc)
        end = start + timedelta(days=1, hours=2)

        sub_tests = [
            SubTest(
                description="Check schedules run when expected",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + timedelta(seconds=30)],
                        event_id="SETUP_ODP_LINK",
                        plan_id="1",
                    )
                ],
            ),
            SubTest(
                description="Fund the accounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "200",
                        start + timedelta(hours=1, seconds=1),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, seconds=1): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "100")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Make a withdrawal, accepted due to ODP",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "200",
                        start + timedelta(hours=1, minutes=4),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=4): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "-100")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Sweep from savings to checking at EOD to bring account current",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + timedelta(days=1)], event_id="ODP_SWEEP", plan_id="1"
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=1): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "0")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "100")],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_INC_5886_AC3_rejecting_a_sweep_to_cover_a_transaction(self):
        start = datetime(year=2022, month=1, day=10, tzinfo=timezone.utc)
        end = start + timedelta(days=1, hours=2)

        sub_tests = [
            SubTest(
                description="Check schedules run when expected",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + timedelta(seconds=30)],
                        event_id="SETUP_ODP_LINK",
                        plan_id="1",
                    )
                ],
            ),
            SubTest(
                description="Fund the accounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "200",
                        start + timedelta(hours=1, seconds=1),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, seconds=1): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "100")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Make a withdrawal, rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "5000",
                        start + timedelta(hours=1, minutes=4),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=1, minutes=4),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Combined checking and savings account balance 300.00 "
                        "insufficient to cover net transaction amount -5000",
                        account_id=f"{CHECKING_ACCOUNT} 0",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=4): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "100")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Run schedule, no need to sweep funds",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + timedelta(days=1)],
                        event_id="ODP_SWEEP",
                        plan_id="1",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=1): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "100")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_multiple_odp_eligible_transactions_hard_settlements_only(self):
        start = datetime(year=2022, month=1, day=10, tzinfo=timezone.utc)
        end = start + timedelta(days=1, hours=2)

        sub_tests = [
            SubTest(
                description="Check schedules run when expected",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + timedelta(seconds=30)],
                        event_id="SETUP_ODP_LINK",
                        plan_id="1",
                    )
                ],
            ),
            SubTest(
                description="Fund the accounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "200",
                        start + timedelta(hours=1, seconds=1),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, seconds=1): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "100")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Make a withdrawal, accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "50",
                        start + timedelta(hours=1, minutes=2),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=2): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "50")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Make a withdrawal, accepted due to ODP 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1, minutes=4),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=4): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "-50")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Make a withdrawal, accepted due to ODP 2",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1, minutes=6),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=6): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "-150")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Make a withdrawal, rejected due to insufficient combined balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "3000",
                        start + timedelta(hours=1, minutes=8),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=1, minutes=8),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Combined checking and savings account balance 50.00 "
                        "insufficient to cover net transaction amount -3000",
                        account_id=f"{CHECKING_ACCOUNT} 0",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=8): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "-150")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Sweep from savings to checking at EOD to bring account current",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + timedelta(days=1)],
                        event_id="ODP_SWEEP",
                        plan_id="1",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=1): {
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
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_multiple_odp_eligible_transactions_with_outbound_auths(self):
        start = datetime(year=2022, month=1, day=10, tzinfo=timezone.utc)
        end = start + timedelta(days=1, hours=2)

        sub_tests = [
            SubTest(
                description="Check schedules run when expected",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + timedelta(seconds=30)],
                        event_id="SETUP_ODP_LINK",
                        plan_id="1",
                    )
                ],
            ),
            SubTest(
                description="Fund the accounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "200",
                        start + timedelta(hours=1, seconds=1),
                        denomination="USD",
                        target_account_id=f"{SAVINGS_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, seconds=1): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "100")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Make a withdrawal, accepted",
                events=[
                    create_outbound_authorisation_instruction(
                        "50",
                        start + timedelta(hours=1, minutes=2),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=2): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (BalanceDimensions(denomination="USD"), "100"),
                            (BalanceDimensions(denomination="USD", phase=PHASE_PENDING_OUT), "-50"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Make a withdrawal, rejected due to insufficient combined balance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "3000",
                        start + timedelta(hours=1, minutes=4),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=1, minutes=4),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Combined checking and savings account balance 250.00 "
                        "insufficient to cover net transaction amount -3000",
                        account_id=f"{CHECKING_ACCOUNT} 0",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=4): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (BalanceDimensions(denomination="USD"), "100"),
                            (BalanceDimensions(denomination="USD", phase=PHASE_PENDING_OUT), "-50"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Make a withdrawal, accepted due to ODP",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1, minutes=6),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=6): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (BalanceDimensions(denomination="USD"), "0"),
                            (BalanceDimensions(denomination="USD", phase=PHASE_PENDING_OUT), "-50"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Make a withdrawal, rejected due to insufficient combined balance 2",
                events=[
                    create_outbound_authorisation_instruction(
                        "3000",
                        start + timedelta(hours=1, minutes=8),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=1, minutes=8),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Combined checking and savings account balance 150.00 "
                        "insufficient to cover net transaction amount -3000",
                        account_id=f"{CHECKING_ACCOUNT} 0",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=8): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (BalanceDimensions(denomination="USD"), "0"),
                            (BalanceDimensions(denomination="USD", phase=PHASE_PENDING_OUT), "-50"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
            SubTest(
                description="Sweep from savings to checking at EOD to bring account current",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + timedelta(days=1)],
                        event_id="ODP_SWEEP",
                        plan_id="1",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=1): {
                        f"{CHECKING_ACCOUNT} 0": [
                            (BalanceDimensions(denomination="USD"), "0"),
                            (BalanceDimensions(denomination="USD", phase=PHASE_PENDING_OUT), "-50"),
                        ],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "200")],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_unfunded_savings_account_on_plan(self):
        start = datetime(year=2022, month=1, day=10, tzinfo=timezone.utc)
        end = start + timedelta(hours=2)

        sub_tests = [
            SubTest(
                description="Fund the account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=1),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "100")],
                        f"{SAVINGS_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "0")],
                    }
                },
            ),
            SubTest(
                description="Make a withdrawal, accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "50",
                        start + timedelta(hours=1, minutes=2),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=2): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "50")],
                    }
                },
            ),
            SubTest(
                description="Make a withdrawal, rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "5000",
                        start + timedelta(hours=1, minutes=4),
                        denomination="USD",
                        target_account_id=f"{CHECKING_ACCOUNT} 0",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=1, minutes=4),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Combined checking and savings account balance 50.00 "
                        "insufficient to cover net transaction amount -5000",
                        account_id=f"{CHECKING_ACCOUNT} 0",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=4): {
                        f"{CHECKING_ACCOUNT} 0": [(BalanceDimensions(denomination="USD"), "50")],
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(),
            internal_accounts=self.internal_accounts,
        )

        self.run_test_scenario(test_scenario)
