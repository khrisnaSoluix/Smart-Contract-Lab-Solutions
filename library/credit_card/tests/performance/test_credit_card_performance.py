# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractConfig,
)
from inception_sdk.test_framework.performance.performance_helper import (
    PerformanceTest,
    PerformanceTestType,
)
from library.credit_card.tests.utils.common.lending import (
    DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS,
)

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

endtoend.testhandle.CONTRACTS = {
    "credit_card": {
        "path": "library/credit_card/contracts/credit_card.py",
        "template_params": DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS,
    },
}

endtoend.testhandle.WORKFLOWS = {}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "ACCOUNT_CLOSURE_REQUESTED": (
        "library/credit_card/flag_definitions/account_closure_requested.resource.yaml"
    ),
    "MANUAL_WRITE_OFF": ("library/credit_card/flag_definitions/manual_write_off.resource.yaml"),
    "OVER_90_DPD": ("library/credit_card/flag_definitions/over_90_dpd.resource.yaml"),
    "OVER_150_DPD": ("library/credit_card/flag_definitions/over_150_dpd.resource.yaml"),
}

SCHEDULE_TAGS_DIR = "library/credit_card/account_schedule_tags/performance_tests/"
TEST_PROFILES_DIR = "library/credit_card/tests/performance/"
PAUSED_SCHEDULE_TAG = SCHEDULE_TAGS_DIR + "paused_tag.resource.yaml"

# By default all schedules are skipped
DEFAULT_TAGS = {
    "CREDIT_CARD_ACCRUE_INTEREST_AST": PAUSED_SCHEDULE_TAG,
    "CREDIT_CARD_ANNUAL_FEE_AST": PAUSED_SCHEDULE_TAG,
    "CREDIT_CARD_PAYMENT_DUE_AST": PAUSED_SCHEDULE_TAG,
    "CREDIT_CARD_STATEMENT_CUT_OFF_AST": PAUSED_SCHEDULE_TAG,
}


class CreditCardPerformanceTest(PerformanceTest):
    product_name = "credit_card"
    product_id = "2"
    default_tags = DEFAULT_TAGS

    @classmethod
    def setUpClass(cls):
        # tags changing will not affect simulation so we can load once per test class

        cls.sim_contracts[cls.product_name] = ContractConfig(
            contract_file_path=endtoend.testhandle.CONTRACTS[cls.product_name]["path"],
            template_params=DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS,
            account_configs=[],
            smart_contract_version_id="2",
        )
        super().setUpClass(cls.product_name)

    @PerformanceTest.Decorators.set_paused_tags(
        {
            "CREDIT_CARD_ACCRUE_INTEREST_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_accrue_interest.resource.yaml",
            },
            "CREDIT_CARD_STATEMENT_CUT_OFF_AST": {
                "schedule_frequency": "MONTHLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_statement_cut_off_date.resource.yaml",
            },
            "CREDIT_CARD_PAYMENT_DUE_AST": {
                "schedule_frequency": "MONTHLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_payment_due.resource.yaml",
            },
        }
    )
    def test_credit_card_schedules(self):
        self.run_performance_test(TEST_PROFILES_DIR + "test_schedules_profile.yaml")

    @PerformanceTest.Decorators.set_paused_tags(
        {
            "CREDIT_CARD_ANNUAL_FEE_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_annual_fee.resource.yaml",
            }
        }
    )
    def test_credit_card_annual_fee_schedule(self):
        """
        To avoid backdating this schedule is run separately, as the annual fee is charged to the
        Credit Card account immediately upon account creation.
        """
        self.run_performance_test(TEST_PROFILES_DIR + "test_annual_fee_schedule_profile.yaml")

    @PerformanceTest.Decorators.set_paused_tags({})
    def test_postings_tps(self):
        self.run_performance_test(
            TEST_PROFILES_DIR + "test_postings_tps_profile.yaml",
            PerformanceTestType.POSTINGS,
        )
