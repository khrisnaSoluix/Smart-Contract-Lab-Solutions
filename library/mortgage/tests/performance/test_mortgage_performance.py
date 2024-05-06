# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractConfig,
    ContractModuleConfig,
)
from datetime import datetime, timezone
from json import dumps

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.performance.performance_helper import PerformanceTest
from inception_sdk.test_framework.performance.test_types import PerformanceTestType
import library.mortgage.tests.e2e.mortgage_test_params as mortgage_test_params

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

DEFAULT_PENALTY_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DUE_AMOUNT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_FLAG = dumps(["ACCOUNT_DELINQUENT"])
DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_REPAYMENT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])

mortgage_template_params = {
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
    "accrued_interest_receivable_account": {
        "internal_account_key": mortgage_test_params.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    },
    "capitalised_interest_received_account": {
        "internal_account_key": mortgage_test_params.CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
    },
    "interest_received_account": {
        "internal_account_key": mortgage_test_params.INTEREST_RECEIVED_ACCOUNT,
    },
    "penalty_interest_received_account": {
        "internal_account_key": mortgage_test_params.PENALTY_INTEREST_RECEIVED_ACCOUNT,
    },
    "late_repayment_fee_income_account": {
        "internal_account_key": mortgage_test_params.LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
    },
    "overpayment_allowance_fee_income_account": {
        "internal_account_key": mortgage_test_params.OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT,
    },
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

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = mortgage_test_params.internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "mortgage": {
        "path": "library/mortgage/contracts/mortgage.py",
        "template_params": mortgage_template_params,
    },
}

endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"},
    "amortisation": {"path": "library/common/contract_modules/amortisation.py"},
}

endtoend.testhandle.WORKFLOWS = {
    "MORTGAGE_MARK_DELINQUENT": "library/mortgage/workflows/mortgage_mark_delinquent.yaml"
}

endtoend.testhandle.FLAG_DEFINITIONS = {}

SCHEDULE_TAGS_DIR = "library/mortgage/account_schedule_tags/performance_tests/"
TEST_PROFILES_DIR = "library/mortgage/tests/performance/"
PAUSED_SCHEDULE_TAG = SCHEDULE_TAGS_DIR + "paused_tag.resource.yaml"

# By default all schedules are skipped
DEFAULT_TAGS = {
    "MORTGAGE_REPAYMENT_DAY_SCHEDULE_AST": PAUSED_SCHEDULE_TAG,
    "MORTGAGE_ACCRUE_INTEREST_AST": PAUSED_SCHEDULE_TAG,
    "MORTGAGE_HANDLE_OVERPAYMENT_ALLOWANCE_AST": PAUSED_SCHEDULE_TAG,
    "MORTGAGE_CHECK_DELINQUENCY_AST": PAUSED_SCHEDULE_TAG,
}

CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "utils": "library/common/contract_modules/utils.py",
    "amortisation": "library/common/contract_modules/amortisation.py",
}


class MortgagePerformanceTest(PerformanceTest):

    product_name = "mortgage"
    product_id = "2"
    default_tags = DEFAULT_TAGS

    @classmethod
    def setUpClass(cls):
        # tags changing will not affect simulation so we can load once per test class

        cls.sim_contracts[cls.product_name] = ContractConfig(
            contract_file_path=endtoend.testhandle.CONTRACTS[cls.product_name]["path"],
            template_params=mortgage_template_params,
            account_configs=[],
            smart_contract_version_id="2",
            linked_contract_modules=[
                ContractModuleConfig(alias, file_path)
                for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
            ],
        )
        super().setUpClass(cls.product_name)

    @PerformanceTest.Decorators.set_paused_tags(
        {
            "MORTGAGE_ACCRUE_INTEREST_AST": {
                # To avoid backdating, skip this schedule to after first months postings
                "skip_to_date_before_execution": datetime(
                    2020, 7, 12, 0, 0, 1, tzinfo=timezone.utc
                ),
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_accrue_interest.resource.yaml",
            },
            "MORTGAGE_REPAYMENT_DAY_SCHEDULE_AST": {
                "schedule_frequency": "MONTHLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_repayment_day_schedule.resource.yaml",
            },
            "MORTGAGE_CHECK_DELINQUENCY_AST": {
                "schedule_frequency": "MONTHLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_check_delinquency.resource.yaml",
            },
            "MORTGAGE_HANDLE_OVERPAYMENT_ALLOWANCE_AST": {
                "schedule_frequency": "YEARLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_overpayment_allowance.resource.yaml",
            },
        }
    )
    def test_mortgage_schedules(self):
        self.run_performance_test(TEST_PROFILES_DIR + "test_mortgage_schedules_profile.yaml")

    @PerformanceTest.Decorators.set_paused_tags({})
    def test_posting_tps(self):
        self.run_performance_test(
            TEST_PROFILES_DIR + "test_postings_profile.yaml",
            PerformanceTestType.POSTINGS,
        )
