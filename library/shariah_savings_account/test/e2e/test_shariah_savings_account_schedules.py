# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
import uuid
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from logging import basicConfig, getLogger
from os import environ

# library
from library.shariah_savings_account.test import dimensions, files
from library.shariah_savings_account.test.e2e import accounts, parameters

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend

log = getLogger(__name__)
basicConfig(
    level=environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

SHARIAH_SAVINGS_ACCOUNT = parameters.SAVINGS_ACCOUNT

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = accounts.internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    SHARIAH_SAVINGS_ACCOUNT: {
        "path": files.CONTRACT_FILE,
        "template_params": parameters.default_template.copy(),
    }
}

endtoend.testhandle.CALENDARS = {
    "PUBLIC_HOLIDAYS": ("library/common/calendars/public_holidays.resource.yaml")
}


class ShariahSavingsAccountSchedulesTest(endtoend.AcceleratedEnd2EndTest):
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules({})
    def test_shariah_savings_account_schedules_with_calendars_events_during_profit_application(
        self,
    ):
        """
        Simple test to make sure that profit application will not occur during a calendar event
        """
        endtoend.standard_setup()

        opening_datetime = datetime(2019, 1, 1, tzinfo=timezone.utc)

        # calendar is event
        holiday_start = datetime(2019, 1, 5, tzinfo=timezone.utc)
        holiday_end = datetime(2019, 1, 6, 23, tzinfo=timezone.utc)

        # with this calendar the apply schedule will be delayed by an extra two days
        endtoend.core_api_helper.create_calendar_event(
            event_id="E2E_TEST_EVENT_" + uuid.uuid4().hex,
            calendar_id=endtoend.testhandle.calendar_ids_to_e2e_ids["PUBLIC_HOLIDAYS"],
            name="E2E TEST EVENT",
            is_active=True,
            start_timestamp=holiday_start,
            end_timestamp=holiday_end,
        )

        # expected application timestamp
        expected_apply_next_runtime = datetime(2019, 1, 7, 0, 1, 0, tzinfo=timezone.utc)

        # create account
        customer_id = endtoend.core_api_helper.create_customer()
        shariah_savings_account_id = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=SHARIAH_SAVINGS_ACCOUNT,
            instance_param_vals=parameters.default_instance,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_datetime.isoformat(),
        )["id"]

        schedules = endtoend.schedule_helper.get_account_schedules(
            account_id=shariah_savings_account_id
        )

        self.assertEqual(
            expected_apply_next_runtime.strftime("%Y-%m-%dT%H:%M:%SZ"),
            schedules["APPLY_PROFIT"]["next_run_timestamp"],
        )

    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {SHARIAH_SAVINGS_ACCOUNT: ["ACCRUE_PROFIT", "APPLY_PROFIT"]}
    )
    def test_shariah_savings_account_accrue_and_apply_profit(self):
        endtoend.standard_setup()

        opening_date = datetime(2022, 4, 5, 1, tzinfo=timezone.utc)
        deposit_1_date = opening_date + relativedelta(hour=15)

        customer_id = endtoend.core_api_helper.create_customer()

        shariah_savings_account_id = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=SHARIAH_SAVINGS_ACCOUNT,
            instance_param_vals=parameters.default_instance,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )["id"]

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=shariah_savings_account_id,
            amount="1000",
            denomination="MYR",
            value_datetime=deposit_1_date,
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=shariah_savings_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "1000"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=shariah_savings_account_id,
            schedule_name="ACCRUE_PROFIT",
            effective_date=datetime(2022, 4, 6, 0, 0, 0, tzinfo=timezone.utc),
        )

        # annual profit rate: 0.149
        # daily profit rate: (0.149 / 365) = 0.00040821917
        # daily profit on balance of 1000: 1000 * 0.00040821917 = 0.40822
        endtoend.balances_helper.wait_for_account_balances(
            account_id=shariah_savings_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "1000"),
                (dimensions.ACCRUED_PROFIT_PAYABLE, "0.40822"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=shariah_savings_account_id,
            schedule_name="APPLY_PROFIT",
            effective_date=datetime(2022, 5, 5, 0, 1, 0, tzinfo=timezone.utc),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=shariah_savings_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "1000.41"),
                (dimensions.ACCRUED_PROFIT_PAYABLE, "0"),
            ],
        )
