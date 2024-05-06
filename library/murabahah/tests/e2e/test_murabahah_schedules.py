# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from logging import basicConfig, getLogger
from os import environ
import uuid

# third party
from dateutil.relativedelta import relativedelta

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions

from library.murabahah.tests.e2e.murabahah_test_params import (
    murabahah_template_params,
    murabahah_instance_params,
    internal_accounts_tside,
    DEFAULT_TAGS,
    SCHEDULE_TAGS_DIR,
)

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

log = getLogger(__name__)
basicConfig(
    level=environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

endtoend.testhandle.CONTRACTS = {
    "murabahah": {
        "path": "library/murabahah/contracts/template/murabahah.py",
        "template_params": murabahah_template_params,
    }
}

endtoend.testhandle.CALENDARS = {
    "PUBLIC_HOLIDAYS": ("library/common/calendars/public_holidays.resource.yaml")
}


class MurabahahSchedulesTest(endtoend.AcceleratedEnd2EndTest):

    default_tags = DEFAULT_TAGS

    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags({})
    def test_murabahah_schedules_with_calendars_when_utc_and_local_dates_differ(self):
        """
        In this scenario, the utc opening date and local date will not match,
        for example: 2022-04-05T18:00:00Z == 2022-04-06T02:00:00+0800
        We cannot test this scenario in unit tests in a consistent manner because we have
        to pass in a tz naive datetime to replicate platform behaviour, but this then
        gets localized and assumes system timezone, which will vary based on the
        test runner's setup.
        We also can't test it in simulator, because the simulator doesn't support the
        event_timezone metadata
        """
        endtoend.standard_setup()

        # Calendar events will be fetched within the time window
        # [effective_date - 3 months, effective_date + 3 months]
        # hence we need to use a dynamic month to ensure the test doesn't fail outside
        # of this 3 month window
        current_date = datetime.now(tz=timezone.utc)

        # opening date is in the past, so next runs will be 1 month/day afterward
        # opening date is YYYY-[M-2]-05T18:00:00Z
        opening_date = current_date - relativedelta(
            months=2, day=5, hour=18, minute=0, second=0, microsecond=0
        )

        # calendar is active YYYY-[M-1]-05T00:00:00Z - YYYY-[M-1]-07T00:00:00Z
        public_holidays_start_timestamp = current_date - relativedelta(
            months=1, day=5, hour=0, minute=0, second=0, microsecond=0
        )
        public_holidays_end_timestamp = current_date - relativedelta(
            months=1, day=7, hour=0, minute=0, second=0, microsecond=0
        )

        # With this calendar the apply schedule will be delayed by an extra two days
        endtoend.core_api_helper.create_calendar_event(
            event_id="E2E_TEST_EVENT_" + uuid.uuid4().hex,
            calendar_id=endtoend.testhandle.calendar_ids_to_e2e_ids["PUBLIC_HOLIDAYS"],
            name="E2E TEST EVENT",
            is_active=True,
            start_timestamp=public_holidays_start_timestamp,
            end_timestamp=public_holidays_end_timestamp,
        )

        # expect next accrual: YYYY-[M-2]-06T16:00:00Z
        expected_accrue_next_runtime = current_date - relativedelta(
            months=2, day=6, hour=16, minute=0, second=0, microsecond=0
        )
        # expect next application: YYYY-[M-1]-07T16:00:00Z
        expected_apply_next_runtime = current_date - relativedelta(
            months=1, day=7, hour=16, minute=0, second=0, microsecond=0
        )

        customer_id = endtoend.core_api_helper.create_customer()

        murabahah_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="murabahah",
            instance_param_vals=murabahah_instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        murabahah_account_id = murabahah_account["id"]

        schedules = endtoend.schedule_helper.get_account_schedules(account_id=murabahah_account_id)

        self.assertEqual(
            expected_accrue_next_runtime.strftime("%Y-%m-%dT%H:%M:%SZ"),
            schedules["ACCRUE_PROFIT"]["next_run_timestamp"],
        )
        self.assertEqual(
            expected_apply_next_runtime.strftime("%Y-%m-%dT%H:%M:%SZ"),
            schedules["APPLY_ACCRUED_PROFIT"]["next_run_timestamp"],
        )

    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags(
        {
            "MURABAHAH_ACCRUE_PROFIT_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_accruals_tag.resource.yaml",
            }
        }
    )
    def test_murabahah_initial_accrual_deposit(self):
        endtoend.standard_setup()

        opening_date = datetime(2022, 4, 5, 1, tzinfo=timezone.utc)
        deposit_1_date = opening_date + relativedelta(hour=15)

        customer_id = endtoend.core_api_helper.create_customer()

        murabahah_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="murabahah",
            instance_param_vals=murabahah_instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        murabahah_account_id = murabahah_account["id"]

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=murabahah_account_id,
            amount="1000",
            denomination="MYR",
            value_datetime=deposit_1_date,
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=murabahah_account_id,
            expected_balances=[
                (BalanceDimensions("DEFAULT", denomination="MYR"), "1000"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_execution(
            paused_tag_id="MURABAHAH_ACCRUE_PROFIT_AST",
            schedule_frequency=self.paused_tags["MURABAHAH_ACCRUE_PROFIT_AST"][
                "schedule_frequency"
            ],
        )

        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="ACCRUE_PROFIT",
            account_id=murabahah_account_id,
        )

        # annual profit rate: 0.50
        # daily profit rate: (0.50 / 365) = 0.001369863
        # daily profit on balance of £1000: 1000 * 0.001369863 =  1.369863
        endtoend.balances_helper.wait_for_account_balances(
            account_id=murabahah_account_id,
            expected_balances=[
                (BalanceDimensions("DEFAULT", denomination="MYR"), "1000"),
                (
                    BalanceDimensions("ACCRUED_PROFIT_PAYABLE", denomination="MYR"),
                    "1.36986",
                ),
            ],
        )
