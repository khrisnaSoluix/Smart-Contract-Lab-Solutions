# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import json
import os
from datetime import datetime, timezone

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractConfig,
    ContractModuleConfig,
)
from inception_sdk.test_framework.performance.performance_helper import PerformanceTest
from inception_sdk.test_framework.performance.test_types import PerformanceTestType
import library.loan.tests.e2e.loan_test_params as loan_test_params

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

DEFAULT_PENALTY_BLOCKING_FLAG = json.dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DUE_AMOUNT_BLOCKING_FLAG = json.dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_BLOCKING_FLAG = json.dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_FLAG = json.dumps(["ACCOUNT_DELINQUENT"])
DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG = json.dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_REPAYMENT_BLOCKING_FLAG = json.dumps(["REPAYMENT_HOLIDAY"])

loan_template_params = {
    "denomination": "GBP",
    "variable_interest_rate": "0.129971",
    "annual_interest_rate_cap": "1.0",
    "annual_interest_rate_floor": "0.0",
    "late_repayment_fee": "15",
    "penalty_interest_rate": "0.24",
    "capitalise_penalty_interest": "False",
    "penalty_includes_base_rate": "True",
    "repayment_period": "10",
    "grace_period": "5",
    "penalty_compounds_overdue_interest": "True",
    "accrue_interest_on_due_principal": "False",
    "penalty_blocking_flags": DEFAULT_PENALTY_BLOCKING_FLAG,
    "due_amount_blocking_flags": DEFAULT_DUE_AMOUNT_BLOCKING_FLAG,
    "delinquency_blocking_flags": DEFAULT_DELINQUENCY_BLOCKING_FLAG,
    "delinquency_flags": DEFAULT_DELINQUENCY_FLAG,
    "overdue_amount_blocking_flags": DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG,
    "repayment_blocking_flags": DEFAULT_REPAYMENT_BLOCKING_FLAG,
    "accrued_interest_receivable_account": {
        "internal_account_key": loan_test_params.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    },
    "capitalised_interest_received_account": {
        "internal_account_key": loan_test_params.CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
    },
    "capitalised_interest_receivable_account": {
        "internal_account_key": loan_test_params.CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT
    },
    "capitalised_penalties_received_account": {
        "internal_account_key": loan_test_params.CAPITALISED_PENALTIES_RECEIVED_ACCOUNT,
    },
    "interest_received_account": {
        "internal_account_key": loan_test_params.INTEREST_RECEIVED_ACCOUNT,
    },
    "penalty_interest_received_account": {
        "internal_account_key": loan_test_params.PENALTY_INTEREST_RECEIVED_ACCOUNT,
    },
    "late_repayment_fee_income_account": {
        "internal_account_key": loan_test_params.LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
    },
    "overpayment_fee_income_account": {
        "internal_account_key": loan_test_params.OVERPAYMENT_FEE_INCOME_ACCOUNT,
    },
    "overpayment_fee_rate": "0.05",
    "upfront_fee_income_account": {
        "internal_account_key": loan_test_params.UPFRONT_FEE_INCOME_ACCOUNT,
    },
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "amortisation_method": "declining_principal",
    "capitalise_no_repayment_accrued_interest": "no_capitalisation",
    "overpayment_impact_preference": "reduce_term",
    "accrue_interest_hour": "0",
    "accrue_interest_minute": "0",
    "accrue_interest_second": "1",
    "check_overdue_hour": "0",
    "check_overdue_minute": "0",
    "check_overdue_second": "2",
    "check_delinquency_hour": "0",
    "check_delinquency_minute": "0",
    "check_delinquency_second": "2",
    "repayment_hour": "0",
    "repayment_minute": "1",
    "repayment_second": "0",
}

endtoend.testhandle.CONTRACTS = {
    "loan": {
        "path": "library/loan/contracts/loan.py",
        "template_params": loan_template_params,
    },
}
endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"},
    "amortisation": {"path": "library/common/contract_modules/amortisation.py"},
}

endtoend.testhandle.WORKFLOWS = {
    "LOAN_MARK_DELINQUENT": "library/loan/workflows/loan_mark_delinquent.yaml",
    "LOAN_REPAYMENT_NOTIFICATION": "library/common/workflows/simple_notification.yaml",
    "LOAN_OVERDUE_REPAYMENT_NOTIFICATION": "library/common/workflows/simple_notification.yaml",
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "ACCOUNT_DELINQUENT": "library/common/flag_definitions/account_delinquent.resource.yaml",
    "REPAYMENT_HOLIDAY": "library/common/flag_definitions/repayment_holiday.resource.yaml",
}

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = loan_test_params.internal_accounts_tside

SCHEDULE_TAGS_DIR = "library/loan/account_schedule_tags/performance_tests/"
TEST_PROFILES_DIR = "library/loan/tests/performance/"
PAUSED_SCHEDULE_TAG = SCHEDULE_TAGS_DIR + "paused_tag.resource.yaml"

# By default all schedules are skipped
DEFAULT_TAGS = {
    "LOAN_ACCRUE_INTEREST_AST": PAUSED_SCHEDULE_TAG,
    "LOAN_REPAYMENT_DAY_SCHEDULE_AST": PAUSED_SCHEDULE_TAG,
    "LOAN_CHECK_OVERDUE_AST": PAUSED_SCHEDULE_TAG,
    "LOAN_CHECK_DELINQUENCY_AST": PAUSED_SCHEDULE_TAG,
}

CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "utils": "library/common/contract_modules/utils.py",
    "amortisation": "library/common/contract_modules/amortisation.py",
}


class LoanPerformanceTest(PerformanceTest):

    product_name = "loan"
    default_tags = DEFAULT_TAGS

    @classmethod
    def setUpClass(cls):
        # tags changing will not affect simulation so we can load once per test class

        cls.sim_contracts[cls.product_name] = ContractConfig(
            contract_file_path=endtoend.testhandle.CONTRACTS[cls.product_name]["path"],
            template_params=loan_template_params,
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
            "LOAN_ACCRUE_INTEREST_AST": {
                # To avoid backdating, skip this schedule to after first months postings
                "skip_to_date_before_execution": datetime(2020, 7, 1, 0, 0, 1, tzinfo=timezone.utc),
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_accrue_interest.resource.yaml",
            },
            "LOAN_REPAYMENT_DAY_SCHEDULE_AST": {
                "schedule_frequency": "MONTHLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_repayment_day_schedule.resource.yaml",
            },
            "LOAN_CHECK_OVERDUE_AST": {
                "schedule_frequency": "MONTHLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_check_overdue.resource.yaml",
            },
            "LOAN_CHECK_DELINQUENCY_AST": {
                "schedule_frequency": "MONTHLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_check_delinquency.resource.yaml",
            },
        }
    )
    def test_loan_schedules(self):
        self.run_performance_test(TEST_PROFILES_DIR + "test_loan_schedules_profile.yaml")

    @PerformanceTest.Decorators.set_paused_tags({})
    def test_posting_tps(self):
        self.run_performance_test(
            TEST_PROFILES_DIR + "test_posting_profile.yaml",
            PerformanceTestType.POSTINGS,
        )
