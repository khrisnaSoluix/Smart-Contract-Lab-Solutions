# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
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

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

wallet_template_params = {
    "zero_out_daily_spend_hour": "23",
    "zero_out_daily_spend_minute": "59",
    "zero_out_daily_spend_second": "59",
}

endtoend.testhandle.CONTRACTS = {
    "wallet": {
        "path": "library/wallet/contracts/wallet.py",
        "template_params": wallet_template_params,
    },
}
endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"},
}

endtoend.testhandle.WORKFLOWS = {}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "AUTO_TOP_UP_WALLET": "library/wallet/flag_definitions/auto_top_up_wallet.resource.yaml"
}

SCHEDULE_TAGS_DIR = "library/wallet/account_schedule_tags/performance_tests/"
TEST_PROFILES_DIR = "library/wallet/tests/performance/"
PAUSED_SCHEDULE_TAG = SCHEDULE_TAGS_DIR + "paused_tag.resource.yaml"

# By default all schedules are skipped
DEFAULT_TAGS = {"WALLET_ZERO_OUT_DAILY_SPEND_AST": PAUSED_SCHEDULE_TAG}

CONTRACT_MODULES_ALIAS_FILE_MAP = {"utils": "library/common/contract_modules/utils.py"}


class WalletPerformanceTest(PerformanceTest):

    product_name = "wallet"
    default_tags = DEFAULT_TAGS

    @classmethod
    def setUpClass(cls):
        # tags changing will not affect simulation so we can load once per test class

        cls.sim_contracts[cls.product_name] = ContractConfig(
            contract_file_path=endtoend.testhandle.CONTRACTS[cls.product_name]["path"],
            template_params=wallet_template_params,
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
            "WALLET_ZERO_OUT_DAILY_SPEND_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "pause_zero_out_daily_spend.resource.yaml",
            }
        }
    )
    def test_zero_out_daily_spend(self):
        self.run_performance_test(TEST_PROFILES_DIR + "test_zero_out_daily_spend_profile.yaml")

    @PerformanceTest.Decorators.set_paused_tags({})
    def test_posting_tps(self):
        self.run_performance_test(
            TEST_PROFILES_DIR + "test_posting_profile.yaml",
            PerformanceTestType.POSTINGS,
        )

    @PerformanceTest.Decorators.set_paused_tags({})
    def test_auto_top_up(self):
        self.run_performance_test(
            TEST_PROFILES_DIR + "test_auto_top_up_profile.yaml",
            PerformanceTestType.POSTINGS,
        )

    @PerformanceTest.Decorators.set_paused_tags({})
    def test_auto_transfer_deposit(self):
        self.run_performance_test(
            TEST_PROFILES_DIR + "test_auto_transfer_deposit_profile.yaml",
            PerformanceTestType.POSTINGS,
        )
