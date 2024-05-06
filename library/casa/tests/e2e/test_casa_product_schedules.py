# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os
from datetime import datetime, timezone

# third_party
from dateutil.relativedelta import relativedelta

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions

from library.casa.tests.e2e.casa_test_params import (
    ca_template_params,
    internal_accounts_tside,
    SCHEDULE_TAGS_DIR,
    DEFAULT_TAGS,
)

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "current_account": {
        "path": "library/casa/contracts/casa.py",
        "template_params": ca_template_params,
    }
}

endtoend.testhandle.WORKFLOWS = {}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "CASA_TIER_MIDDLE": ("library/casa/flag_definitions/casa_tier_middle.resource.yaml"),
    "ACCOUNT_DORMANT": ("library/common/flag_definitions/account_dormant.resource.yaml"),
}

endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"},
    "interest": {"path": "library/common/contract_modules/interest.py"},
}


class CasaProductTest(endtoend.AcceleratedEnd2EndTest):

    default_tags = DEFAULT_TAGS

    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags(
        {
            "CASA_ACCRUE_INTEREST_AND_DAILY_FEES_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_accruals_tag.resource.yaml",
            },
            "CASA_APPLY_ACCRUED_INTEREST_AST": {
                "schedule_frequency": "MONTHLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_apply_interest.resource.yaml",
            },
        }
    )
    def test_accrue_and_apply_interest(self):
        endtoend.standard_setup()
        opening_date = datetime(year=2020, month=1, day=10, hour=10, tzinfo=timezone.utc)

        customer_id = endtoend.core_api_helper.create_customer()
        current_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="current_account",
            instance_param_vals=dict(
                arranged_overdraft_limit="1000",
                unarranged_overdraft_limit="2000",
                interest_application_day="16",
                daily_atm_withdrawal_limit="1000",
            ),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        account_id = current_account["id"]

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=account_id,
            amount="1000",
            denomination="GBP",
            value_datetime=opening_date,
        )

        endtoend.schedule_helper.trigger_next_schedule_execution(
            paused_tag_id="CASA_ACCRUE_INTEREST_AND_DAILY_FEES_AST",
            schedule_frequency=self.paused_tags["CASA_ACCRUE_INTEREST_AND_DAILY_FEES_AST"][
                "schedule_frequency"
            ],
        )

        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="ACCRUE_INTEREST_AND_DAILY_FEES",
            account_id=account_id,
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=account_id,
            expected_balances=[
                (BalanceDimensions("DEFAULT"), "1000"),
                (BalanceDimensions("ACCRUED_DEPOSIT_PAYABLE"), "0.13699"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_execution(
            paused_tag_id="CASA_APPLY_ACCRUED_INTEREST_AST",
            schedule_frequency=self.paused_tags["CASA_APPLY_ACCRUED_INTEREST_AST"][
                "schedule_frequency"
            ],
        )

        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="APPLY_ACCRUED_INTEREST",
            account_id=account_id,
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=account_id,
            expected_balances=[
                # only applying one day's interest as only one accrual event has been run
                (BalanceDimensions("DEFAULT"), "1000.14"),
                (BalanceDimensions("ACCRUED_DEPOSIT_PAYABLE"), "0"),
            ],
        )
        account_schedules = endtoend.schedule_helper.get_account_schedules(account_id)
        # Expected accrue interest - 2020-01-12T01:02:03Z
        accrue_interest_expected_next_run_time_start = opening_date + relativedelta(
            day=12, hour=1, minute=2, second=3
        )
        self.assertEqual(
            accrue_interest_expected_next_run_time_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["ACCRUE_INTEREST_AND_DAILY_FEES"]["next_run_timestamp"],
        )
        # Expected apply Interest 2020-02-16T04:05:06Z
        apply_accrued_expected_next_run_time_start = opening_date + relativedelta(
            month=2, day=16, hour=4, minute=5, second=6
        )

        self.assertEqual(
            apply_accrued_expected_next_run_time_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["APPLY_ACCRUED_INTEREST"]["next_run_timestamp"],
        )

    # No tags set as we don't actually unpause any schedules
    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags({})
    def test_schedule_creation(self):
        endtoend.standard_setup()
        opening_date = datetime(year=2020, month=1, day=10, hour=10, tzinfo=timezone.utc)

        customer_id = endtoend.core_api_helper.create_customer()
        current_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="current_account",
            instance_param_vals=dict(
                arranged_overdraft_limit="1000",
                unarranged_overdraft_limit="2000",
                interest_application_day="16",
                daily_atm_withdrawal_limit="1000",
            ),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        account_id = current_account["id"]

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=account_id,
            amount="1000",
            denomination="GBP",
            value_datetime=opening_date,
        )

        account_schedules = endtoend.schedule_helper.get_account_schedules(account_id)
        # Expected accrue interest - 2020-01-11T01:02:03Z
        accrue_interest_expected_next_run_time_start = opening_date + relativedelta(
            day=11, hour=1, minute=2, second=3
        )
        self.assertEqual(
            accrue_interest_expected_next_run_time_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["ACCRUE_INTEREST_AND_DAILY_FEES"]["next_run_timestamp"],
        )

        # Expected apply Interest 2020-01-16T04:05:06Z
        apply_accrued_expected_next_run_time_start = opening_date + relativedelta(
            day=16, hour=4, minute=5, second=6
        )

        self.assertEqual(
            apply_accrued_expected_next_run_time_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["APPLY_ACCRUED_INTEREST"]["next_run_timestamp"],
        )

        # Expected monthly fees 2020-02-10T00:01:00Z
        apply_monthly_fees_expected_next_run_time_start = opening_date + relativedelta(
            month=2, day=10, hour=0, minute=1, second=0
        )

        self.assertEqual(
            apply_monthly_fees_expected_next_run_time_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["APPLY_MONTHLY_FEES"]["next_run_timestamp"],
        )

        # Expected annual fees 2021-01-10T00:01:00Z
        apply_annual_fees_expected_next_run_time_start = opening_date + relativedelta(
            year=2021, hour=0, minute=1, second=0
        )

        self.assertEqual(
            apply_annual_fees_expected_next_run_time_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["APPLY_ANNUAL_FEES"]["next_run_timestamp"],
        )
