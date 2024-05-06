# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os
from datetime import datetime, timezone
import time

# third party
from dateutil.relativedelta import relativedelta

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions

from library.wallet.tests.e2e.wallet_test_params import (
    wallet_template_params,
    SCHEDULE_TAGS_DIR,
    DEFAULT_TAGS,
)

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = {}

endtoend.testhandle.CONTRACTS = {
    "wallet": {
        "path": "library/wallet/contracts/wallet.py",
        "template_params": wallet_template_params,
    },
}

endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"}
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "AUTO_TOP_UP_WALLET": ("library/wallet/flag_definitions/auto_top_up_wallet.resource.yaml"),
}


class WalletSchedulesTest(endtoend.AcceleratedEnd2EndTest):

    default_tags = DEFAULT_TAGS

    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at
        # Uncomment this for timing info.
        # print('\n{} ({}s)'.format(self.id().rpartition('.')[2],
        # round(self._elapsed_time, 2)))

    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags(
        {
            "WALLET_ZERO_OUT_DAILY_SPEND_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "pause_zero_out_daily_spend.resource.yaml",
            }
        }
    )
    def test_zero_out_daily_spend(self):
        endtoend.standard_setup()
        opening_date = datetime(2020, 5, 1, tzinfo=timezone.utc)

        customer_id = endtoend.core_api_helper.create_customer()

        instance_params = {
            "customer_wallet_limit": "1000",
            "daily_spending_limit": "500",
            "denomination": "GBP",
            "additional_denominations": '["SGD","USD"]',
            "nominated_account": "1",
        }

        wallet_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="wallet",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        account_id = wallet_account["id"]

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=account_id,
            amount="250",
            denomination="GBP",
            value_datetime=opening_date,
        )

        endtoend.postings_helper.outbound_hard_settlement(
            account_id=account_id,
            amount="150",
            denomination="GBP",
            value_datetime=opening_date + relativedelta(hours=1),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=account_id,
            expected_balances=[(BalanceDimensions("todays_spending"), "-150")],
        )

        endtoend.schedule_helper.trigger_next_schedule_execution(
            paused_tag_id="WALLET_ZERO_OUT_DAILY_SPEND_AST",
            schedule_frequency=self.paused_tags["WALLET_ZERO_OUT_DAILY_SPEND_AST"][
                "schedule_frequency"
            ],
        )

        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="ZERO_OUT_DAILY_SPEND",
            account_id=account_id,
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=account_id,
            expected_balances=[(BalanceDimensions("todays_spending"), "0")],
        )
