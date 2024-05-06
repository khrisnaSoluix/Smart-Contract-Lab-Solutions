# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

# library
from library.wallet.contracts.template import wallet
from library.wallet.test import dimensions, files, parameters
from library.wallet.test.e2e.parameters import POSTING_BATCH_REJECTED, WALLET_PRODUCT

# inception sdk
# common
import inception_sdk.test_framework.endtoend as endtoend

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = {}

endtoend.testhandle.CONTRACTS = {
    WALLET_PRODUCT: {
        "path": files.WALLET_CONTRACT,
        "template_params": parameters.default_template,
    },
}

endtoend.testhandle.FLAG_DEFINITIONS = {"AUTO_TOP_UP_WALLET": files.AUTO_TOP_UP_WALLET}


class WalletSchedulesTest(endtoend.AcceleratedEnd2EndTest):
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {WALLET_PRODUCT: [wallet.ZERO_OUT_DAILY_SPEND_EVENT]}
    )
    def test_zero_out_daily_spend(self):
        endtoend.standard_setup()
        opening_date = datetime(2020, 5, 1, tzinfo=timezone.utc)

        customer_id = endtoend.core_api_helper.create_customer()

        instance_params = {
            **parameters.default_instance,
            wallet.PARAM_NOMINATED_ACCOUNT: "1",
            wallet.PARAM_SPENDING_LIMIT: "500",
        }

        wallet_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=WALLET_PRODUCT,
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        account_id = wallet_account["id"]

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=account_id,
            amount="700",
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=opening_date,
        )
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=account_id,
            amount="500",
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=opening_date + relativedelta(hours=1),
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=account_id,
            expected_balances=[
                (dimensions.TODAYS_SPENDING_DIMENSIONS, "-500"),
                (dimensions.DEFAULT_DIMENSIONS, "200"),
            ],
        )

        # Attempt to bring total amount spent to an amount that would exceed daily spend limit
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=account_id,
            amount="100",
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=datetime(2020, 5, 1, 22, 29, 0, tzinfo=timezone.utc),
        )
        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_REJECTED, pib["status"])
        self.assertEqual(
            "Transaction would exceed daily spending limit",
            pib["posting_instructions"][0]["contract_violations"][0]["reason"],
        )

        # Zero out daily spend
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=account_id,
            schedule_name=wallet.ZERO_OUT_DAILY_SPEND_EVENT,
            effective_date=datetime(2020, 5, 1, 23, 59, 59, tzinfo=timezone.utc),
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=account_id,
            expected_balances=[(dimensions.TODAYS_SPENDING_DIMENSIONS, "0")],
        )

        # Make sure posting is accepted after the spending is zeroed out
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=account_id,
            amount="100",
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=datetime(2020, 5, 2, tzinfo=timezone.utc),
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=account_id,
            expected_balances=[
                (dimensions.TODAYS_SPENDING_DIMENSIONS, "-100"),
            ],
        )
