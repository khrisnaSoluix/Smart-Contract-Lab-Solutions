# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os
from json import dumps

# common
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractConfig,
    ContractModuleConfig,
)
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.performance.performance_helper import PerformanceTest
from inception_sdk.test_framework.performance.test_types import PerformanceTestType
import library.casa.tests.e2e.casa_test_params as casa_test_params

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

ca_template_params = {
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
    "accrued_interest_receivable_account": {
        "internal_account_key": casa_test_params.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    },
    "interest_received_account": {
        "internal_account_key": casa_test_params.INTEREST_RECEIVED_ACCOUNT,
    },
    "accrued_interest_payable_account": {
        "internal_account_key": casa_test_params.ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    },
    "interest_paid_account": {
        "internal_account_key": casa_test_params.INTEREST_PAID_ACCOUNT,
    },
    "overdraft_fee_income_account": {
        "internal_account_key": casa_test_params.OVERDRAFT_FEE_INCOME_ACCOUNT,
    },
    "overdraft_fee_receivable_account": {
        "internal_account_key": casa_test_params.OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
    },
    "maintenance_fee_income_account": {
        "internal_account_key": casa_test_params.MAINTENANCE_FEE_INCOME_ACCOUNT,
    },
    "minimum_balance_fee_income_account": {
        "internal_account_key": casa_test_params.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
    },
    "annual_maintenance_fee_income_account": {
        "internal_account_key": casa_test_params.ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
    },
    "inactivity_fee_income_account": {
        "internal_account_key": casa_test_params.INACTIVITY_FEE_INCOME_ACCOUNT,
    },
    "excess_withdrawal_fee_income_account": {
        "internal_account_key": casa_test_params.EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
    },
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
    "maximum_daily_withdrawal": "100000",
    "maximum_daily_deposit": "100000",
    "minimum_deposit": "0",
    "minimum_withdrawal": "0",
    "maximum_balance": "100000",
    "reject_excess_withdrawals": "false",
    "monthly_withdrawal_limit": "-1",
    "excess_withdrawal_fee": "0",
}

endtoend.testhandle.CONTRACTS = {
    "casa": {
        "path": "library/casa/contracts/casa.py",
        "template_params": ca_template_params,
    },
}

endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"},
    "interest": {"path": "library/common/contract_modules/interest.py"},
}

endtoend.testhandle.WORKFLOWS = {}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "CASA_TIER_UPPER": ("library/casa/flag_definitions/casa_tier_upper.resource.yaml"),
    "CASA_TIER_MIDDLE": ("library/casa/flag_definitions/casa_tier_middle.resource.yaml"),
    "CASA_TIER_LOWER": ("library/casa/flag_definitions/casa_tier_lower.resource.yaml"),
}


endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = casa_test_params.internal_accounts_tside

SCHEDULE_TAGS_DIR = "library/casa/account_schedule_tags/performance_tests/"
TEST_PROFILES_DIR = "library/casa/tests/performance/"
PAUSED_SCHEDULE_TAG = SCHEDULE_TAGS_DIR + "paused_tag.resource.yaml"


class CasaPerformanceTest(PerformanceTest):

    product_name = "casa"
    # By default all schedules are PAUSED
    default_tags = casa_test_params.DEFAULT_TAGS

    @classmethod
    def setUpClass(cls):
        # tags changing will not affect simulation so we can load once per test class

        cls.sim_contracts[cls.product_name] = ContractConfig(
            contract_file_path=endtoend.testhandle.CONTRACTS[cls.product_name]["path"],
            template_params=ca_template_params,
            account_configs=[],
            smart_contract_version_id="2",
            linked_contract_modules=[
                ContractModuleConfig(
                    alias="utils", file_path="library/common/contract_modules/utils.py"
                ),
                ContractModuleConfig(
                    alias="interest",
                    file_path="library/common/contract_modules/interest.py",
                ),
            ],
        )
        super().setUpClass(cls.product_name)

    @PerformanceTest.Decorators.set_paused_tags(
        {
            "CASA_APPLY_MONTHLY_FEES_AST": {
                "schedule_frequency": "MONTHLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_apply_monthly_fees.resource.yaml",
            },
            "CASA_APPLY_ACCRUED_INTEREST_AST": {
                "schedule_frequency": "MONTHLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_apply_interest.resource.yaml",
            },
            "CASA_APPLY_ANNUAL_FEES_AST": {
                "schedule_frequency": "YEARLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_apply_annual_fees.resource.yaml",
            },
        }
    )
    def test_casa_non_accrual_schedules(self):
        self.run_performance_test(
            TEST_PROFILES_DIR + "test_casa_non_accrual_schedules_profile.yaml"
        )

    @PerformanceTest.Decorators.set_paused_tags(
        {
            "CASA_ACCRUE_INTEREST_AND_DAILY_FEES_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_accruals_tag.resource.yaml",
            },
        }
    )
    def test_casa_accrual_schedule(self):
        self.run_performance_test(TEST_PROFILES_DIR + "test_casa_accrual_schedule_profile.yaml")

    @PerformanceTest.Decorators.set_paused_tags({})
    def test_posting_tps(self):
        self.run_performance_test(
            TEST_PROFILES_DIR + "test_posting_profile.yaml",
            PerformanceTestType.POSTINGS,
        )
