# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os

# common
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractConfig,
    ContractModuleConfig,
)
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.performance.performance_helper import PerformanceTest
from inception_sdk.test_framework.performance.test_types import PerformanceTestType
import library.time_deposit.tests.e2e.time_deposit_test_params as time_deposit_test_params

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

td_template_params = {
    "denomination": "GBP",
    "interest_accrual_hour": "23",
    "interest_accrual_minute": "58",
    "interest_accrual_second": "59",
    "interest_application_hour": "23",
    "interest_application_minute": "59",
    "interest_application_second": "59",
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "minimum_first_deposit": "50",
    "maximum_balance": "1000",
    "single_deposit": "unlimited",
    "accrued_interest_payable_account": {
        "internal_account_key": time_deposit_test_params.ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    },
    "interest_paid_account": {
        "internal_account_key": time_deposit_test_params.INTEREST_PAID_ACCOUNT
    },
}

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = time_deposit_test_params.internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "time_deposit": {
        "path": "library/time_deposit/contracts/time_deposit.py",
        "template_params": td_template_params,
    },
}

endtoend.testhandle.CONTRACT_MODULES = {
    "interest": {"path": "library/common/contract_modules/interest.py"},
    "utils": {"path": "library/common/contract_modules/utils.py"},
}

endtoend.testhandle.WORKFLOWS = {
    # Override the TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER workflow to avoid issues in waiting for
    # balance updates as a result of postings made during the workflow.
    # https://pennyworth.atlassian.net/browse/INC-4724
    "TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER": "library/common/workflows/simple_notification.yaml",
    "TIME_DEPOSIT_APPLICATION": "library/time_deposit/workflows/time_deposit_application.yaml",
    "TIME_DEPOSIT_CLOSURE": "library/time_deposit/workflows/time_deposit_closure.yaml",
    # Override the TIME_DEPOSIT_MATURITY workflow to avoid issues in waiting for balance updates
    # as a result of the maturity workflow (simple_notification does nothing)
    # https://pennyworth.atlassian.net/browse/INC-4724
    "TIME_DEPOSIT_MATURITY": "library/common/workflows/simple_notification.yaml",
    "TIME_DEPOSIT_ROLLOVER": "library/time_deposit/workflows/time_deposit_rollover.yaml",
}

endtoend.testhandle.FLAG_DEFINITIONS = {}

SCHEDULE_TAGS_DIR = "library/time_deposit/account_schedule_tags/performance_tests/"
TEST_PROFILES_DIR = "library/time_deposit/tests/performance/"
PAUSED_SCHEDULE_TAG = SCHEDULE_TAGS_DIR + "paused_tag.resource.yaml"

# By default all schedules are skipped
DEFAULT_TAGS = {
    "TIME_DEPOSIT_ACCRUE_INTEREST_AST": PAUSED_SCHEDULE_TAG,
    "TIME_DEPOSIT_APPLY_ACCRUED_INTEREST_AST": PAUSED_SCHEDULE_TAG,
    "TIME_DEPOSIT_ACCOUNT_MATURITY_AST": PAUSED_SCHEDULE_TAG,
    "TIME_DEPOSIT_ACCOUNT_CLOSE_AST": PAUSED_SCHEDULE_TAG,
}

endtoend.testhandle.CALENDARS = {
    "PUBLIC_HOLIDAYS": ("library/common/calendars/public_holidays.resource.yaml")
}

CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "utils": "library/common/contract_modules/utils.py",
    "interest": "library/common/contract_modules/interest.py",
}


class TimeDepositPerformanceTest(PerformanceTest):

    product_name = "time_deposit"
    default_tags = DEFAULT_TAGS

    @classmethod
    def setUpClass(cls):
        # tags changing will not affect simulation so we can load once per test class

        cls.sim_contracts[cls.product_name] = ContractConfig(
            contract_file_path=endtoend.testhandle.CONTRACTS[cls.product_name]["path"],
            template_params=td_template_params,
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
            "TIME_DEPOSIT_APPLY_ACCRUED_INTEREST_AST": {
                "schedule_frequency": "MONTHLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_apply_interest.resource.yaml",
            },
            "TIME_DEPOSIT_ACCOUNT_MATURITY_AST": {
                "schedule_frequency": "MONTHLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_account_maturity.resource.yaml",
            },
        }
    )
    def test_time_deposit_non_accrual_schedules(self):
        self.run_performance_test(
            TEST_PROFILES_DIR + "test_time_deposit_non_accrual_schedules_profile.yaml"
        )

    @PerformanceTest.Decorators.set_paused_tags(
        {
            "TIME_DEPOSIT_ACCRUE_INTEREST_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_accruals_tag.resource.yaml",
            },
        }
    )
    def test_time_deposit_accrual_schedule(self):
        self.run_performance_test(
            TEST_PROFILES_DIR + "test_time_deposit_accrual_schedule_profile.yaml"
        )

    @PerformanceTest.Decorators.set_paused_tags({})
    def test_repayments(self):
        self.run_performance_test(
            TEST_PROFILES_DIR + "test_pre_posting_profile.yaml",
            PerformanceTestType.POSTINGS,
        )
