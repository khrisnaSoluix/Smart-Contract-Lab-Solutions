# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# library
from library.credit_card.test.e2e.common import standard_teardown as credit_card_teardown
from library.credit_card.test.e2e.parameters import (
    DEFAULT_CREDIT_CARD_INSTANCE_PARAMS,
    DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS,
)

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
import inception_sdk.test_framework.endtoend.schedule_helper as schedule_helper
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions

DEFAULT_DENOM = "GBP"

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

endtoend.testhandle.CONTRACTS = {
    "credit_card": {
        "path": "library/credit_card/contracts/template/credit_card.py",
        "template_params": DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS,
    }
}

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = {
    "TSIDE_ASSET": [],
    "TSIDE_LIABILITY": ["1", "PRINCIPAL_WRITE_OFF", "INTEREST_WRITE_OFF"],
}

endtoend.testhandle.WORKFLOWS = {}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "ACCOUNT_CLOSURE_REQUESTED": (
        "library/credit_card/flag_definitions/account_closure_requested.resource.yaml"
    ),
}


class CreditCardAccountTest(endtoend.AcceleratedEnd2EndTest):
    account = None
    account_id = None

    def tearDown(self):
        credit_card_teardown(self, "ACCOUNT_CLOSURE_REQUESTED")
        super().tearDown()

    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {"credit_card": ["ACCRUE_INTEREST", "STATEMENT_CUT_OFF"]}
    )
    def test_interest_accrual_and_statement_cutoff(self):
        """
        Tests that STATEMENT_CUTOFF_DATE runs after ACCRUE_INTEREST even if
        we unpause the SCOD tag first. This test has a lot of issues not faced
        elsewhere due to the Scheduler's in-built 20 second delay in between
        publishing jobs when using Schedule Tags. Thus, a lot of calls which
        asynchronously await results have extended timeouts and backoffs.
        Uses the following sequence:
        - All tags start on Paused
        - Make one Purchase transaction for interest to accrue
        - Skip all ACCRUE_INTEREST schedules up to SCOD-2
        - Allow one ACCRUE_INTEREST to run at SCOD-1 and check balances
        - Unpause SCOD tag, then ACCRUE_INTEREST tag
        - Final ACCRUE_INTEREST should still run before SCOD
        - Check balance updated by ACCRUE_INTEREST, then moved by SCOD
        """
        endtoend.standard_setup()

        opening_date = datetime(2021, 2, 4, 1, tzinfo=ZoneInfo("UTC"))
        # SCOD is + 1 month - 1 day, (2021, 3, 3) but the schedule runs at the end of the day
        # We skip all ACCRUE_INTEREST jobs between opening date and SCOD-2 and then trigger
        # the two accruals and SCOD
        end_skip_date = datetime(2021, 3, 2, tzinfo=ZoneInfo("UTC"))
        first_accrual_date = datetime(2021, 3, 3, tzinfo=ZoneInfo("UTC"))
        second_accrual_date = datetime(2021, 3, 4, tzinfo=ZoneInfo("UTC"))
        scod_date = datetime(2021, 3, 4, 0, 0, 2, tzinfo=ZoneInfo("UTC"))

        customer_id = endtoend.core_api_helper.create_customer()
        self.account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="credit_card",
            instance_param_vals=DEFAULT_CREDIT_CARD_INSTANCE_PARAMS,
            permitted_denominations=[DEFAULT_DENOM],
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        self.account_id = self.account["id"]

        # Checks that schedule creation is as expected
        schedules = schedule_helper.get_account_schedules(self.account_id)
        self.assertEqual(schedules["ACCRUE_INTEREST"]["status"], "SCHEDULE_STATUS_ENABLED")
        # Scheduler only goes down to second precision
        self.assertEqual(
            schedules["ACCRUE_INTEREST"]["next_run_timestamp"],
            datetime(2021, 2, 5).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        self.assertEqual(schedules["STATEMENT_CUT_OFF"]["status"], "SCHEDULE_STATUS_ENABLED")
        # Scheduler only goes down to second precision
        self.assertEqual(
            schedules["STATEMENT_CUT_OFF"]["next_run_timestamp"],
            datetime(
                2021,
                3,
                4,
                int(DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS["scod_schedule_hour"]),
                int(DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS["scod_schedule_minute"]),
                int(DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS["scod_schedule_second"]),
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        self.assertEqual(schedules["PAYMENT_DUE"]["status"], "SCHEDULE_STATUS_ENABLED")
        # Scheduler only goes down to second precision
        self.assertEqual(
            schedules["PAYMENT_DUE"]["next_run_timestamp"],
            datetime(
                2021,
                3,
                28,
                int(DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS["pdd_schedule_hour"]),
                int(DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS["pdd_schedule_minute"]),
                int(DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS["pdd_schedule_second"]),
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        self.assertEqual(schedules["ANNUAL_FEE"]["status"], "SCHEDULE_STATUS_ENABLED")
        # Scheduler only goes down to second precision
        self.assertEqual(
            schedules["ANNUAL_FEE"]["next_run_timestamp"],
            datetime(
                2021,
                2,
                4,
                int(DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS["annual_fee_schedule_hour"]),
                int(DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS["annual_fee_schedule_minute"]),
                int(DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS["annual_fee_schedule_second"]),
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

        # Make a purchase posting so there is something to accrue interest on
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="200",
            denomination="GBP",
            value_datetime=opening_date,
            instruction_details={"transaction_code": "xxx"},
        )

        endtoend.schedule_helper.skip_scheduled_jobs_and_wait(
            schedule_name="ACCRUE_INTEREST",
            skip_start_date=opening_date,
            skip_end_date=end_skip_date,
            resource_id=self.account_id,
            resource_type=endtoend.schedule_helper.ResourceType.ACCOUNT,
            initial_wait=600,
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            schedule_name="ACCRUE_INTEREST",
            account_id=self.account_id,
            effective_date=first_accrual_date,
        )

        # Ensure ACCRUE_INTEREST has run at SCOD-1
        endtoend.balances_helper.wait_for_account_balances(
            account_id=self.account_id,
            expected_balances=[
                (BalanceDimensions("PURCHASE_INTEREST_PRE_SCOD_UNCHARGED"), "0.13"),
            ],
        )

        # Unpause both tags to SCOD date. SCOD tag first, then ACCRUE_INTEREST tag.
        # ACCRUE_INTEREST should still run first due to group ordering.
        # Can't use normal helper as we're splitting triggering and waiting
        scod_tag_id, _, _ = endtoend.schedule_helper.trigger_next_schedule_job(
            resource_id=self.account_id,
            resource_type=endtoend.schedule_helper.ResourceType.ACCOUNT,
            schedule_name="STATEMENT_CUT_OFF",
        )
        accrue_tag_id, _, _ = endtoend.schedule_helper.trigger_next_schedule_job(
            resource_id=self.account_id,
            resource_type=endtoend.schedule_helper.ResourceType.ACCOUNT,
            schedule_name="ACCRUE_INTEREST",
        )

        # Wait for all ACCRUE_INTEREST jobs to catch up
        endtoend.schedule_helper.wait_for_schedule_job(
            schedule_tag_id=accrue_tag_id, expected_run_time=second_accrual_date
        )

        # Wait for all STATEMENT_CUT_OFF jobs to catch up
        endtoend.schedule_helper.wait_for_schedule_job(
            schedule_tag_id=scod_tag_id, expected_run_time=scod_date
        )

        # Ensure that SCOD balance movements happen after second ACCRUE_INTEREST
        endtoend.balances_helper.wait_for_account_balances(
            account_id=self.account_id,
            expected_balances=[
                (BalanceDimensions("PURCHASE_INTEREST_POST_SCOD_UNCHARGED"), "0.26"),
            ],
        )


if __name__ == "__main__":
    endtoend.runtests()
