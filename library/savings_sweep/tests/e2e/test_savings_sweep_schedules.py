# standard libs
import sys
from datetime import datetime, timedelta

# third party
from dateutil.relativedelta import relativedelta

from library.savings_sweep.tests.e2e.savings_sweep_test_params import (
    ca_template_params,
    ca_instance_params,
    savings_template_params,
    internal_accounts_tside,
)

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.helper import COMMON_ACCOUNT_SCHEDULE_TAG_PATH

sys.path.append(".")

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "us_savings_account": {
        "path": "library/us_products/contracts/us_savings_account.py",
        "template_params": savings_template_params,
        "supervisee_alias": "us_savings",
    },
    "us_checking_account": {
        "path": "library/us_products/contracts/us_checking_account.py",
        "template_params": ca_template_params,
        "supervisee_alias": "us_checking",
    },
}
endtoend.testhandle.CONTRACT_MODULES = {
    "interest": {"path": "library/common/contract_modules/interest.py"},
    "utils": {"path": "library/common/contract_modules/utils.py"},
}
endtoend.testhandle.SUPERVISORCONTRACTS = {
    "savings_sweep": {"path": "library/savings_sweep/supervisors/savings_sweep.py"}
}

endtoend.testhandle.WORKFLOWS = {}

endtoend.testhandle.FLAG_DEFINITIONS = {
    # Used by US Savings
    "PROMOTIONAL_INTEREST_RATES": (
        "library/us_products/flag_definitions/promotional_interest_rates.resource.yaml"
    ),
    # Used by US Checking
    "ACCOUNT_DORMANT": "library/common/flag_definitions/account_dormant.resource.yaml",
    "STANDARD_OVERDRAFT_TRANSACTION_COVERAGE": (
        "library/us_products/flag_definitions/overdraft_transaction_coverage.resource.yaml"
    ),
    # Used by US Checking and Savings
    "PROMOTIONAL_MAINTENANCE_FEE": (
        "library/us_products/flag_definitions/promotional_maintenance_fee.resource.yaml"
    ),
}

OVERDRAFT_LOC_TRANSACTION_COVERAGE_FLAG = "OVERDRAFT_LOC_TRANSACTION_COVERAGE"

SCHEDULE_TAGS_DIR = "library/savings_sweep/account_schedule_tags/schedules_tests/"

DEFAULT_TAGS = {
    "US_CHECKING_ACCRUE_INTEREST_AND_DAILY_FEES_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "US_CHECKING_APPLY_ACCRUED_OVERDRAFT_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "US_CHECKING_APPLY_ACCRUED_DEPOSIT_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "US_CHECKING_APPLY_MONTHLY_FEES_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "US_CHECKING_APPLY_ANNUAL_FEES_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "US_SAVINGS_ACCRUE_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "US_SAVINGS_APPLY_ACCRUED_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "US_SAVINGS_APPLY_MONTHLY_FEES_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "US_SAVINGS_APPLY_ANNUAL_FEES_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
}


class OverdraftProtectionSupervisorTest(endtoend.AcceleratedEnd2EndTest):

    default_tags = DEFAULT_TAGS

    """
    Unlike normal accelerated end-to-ends, we cannot rely on backdated schedules that we then
    let catch up, as this is not supported for Supervisors/Plans yet. Instead we must fast-
    forward schedules. This is not ideal, as future-dated postings can cause confusion, but
    it is better than nothing.
    """

    def next_fee_schedule_timestamp(self, base_date, params):
        fees_application_day = int(params["fees_application_day"])
        fees_application_hour = int(params["fees_application_hour"])
        fees_application_minute = int(params["fees_application_minute"])
        fees_application_second = int(params["fees_application_second"])

        next_run_time = base_date.replace(
            day=fees_application_day,
            hour=fees_application_hour,
            minute=fees_application_minute,
            second=fees_application_second,
        )
        next_run_time += relativedelta(months=1)

        if next_run_time < base_date + relativedelta(months=1):
            next_run_time += relativedelta(months=1, day=fees_application_day)

        return next_run_time

    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags(
        {
            "SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES_AST": {
                "tag_resource": SCHEDULE_TAGS_DIR
                + "paused_supervisor_checking_fees_tag.resource.yaml",
            },
            "SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES_AST": {
                "tag_resource": SCHEDULE_TAGS_DIR
                + "paused_supervisor_savings_fees_tag.resource.yaml",
            },
        }
    )
    def test_supervisor_schedules_synchronise_with_supervisees_after_first_job(self):
        endtoend.standard_setup()
        cust_id = endtoend.core_api_helper.create_customer()

        checking_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account",
            instance_param_vals=ca_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        checking_account_id = checking_account["id"]

        savings_instance_params = {"interest_application_day": "1"}
        us_savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        savings_account_id = us_savings_account["id"]

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep",
            [checking_account_id, savings_account_id],
        )

        creation_date = datetime.strptime(
            checking_account["opening_timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        expected_next_run_time_checking = self.next_fee_schedule_timestamp(
            creation_date, ca_template_params
        )
        creation_date = datetime.strptime(
            us_savings_account["opening_timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        expected_next_run_time_savings = self.next_fee_schedule_timestamp(
            creation_date, savings_template_params
        )

        # The schedule starts are set to 6s from plan creation date, so we can fast-fwd by a minute
        # and expect the jobs to be published
        endtoend.schedule_helper.fast_forward_tag(
            paused_tag_id="SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES_AST",
            fast_forward_to_date=datetime.now() + timedelta(minutes=1),
        )
        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES", plan_id=plan_id
        )
        endtoend.schedule_helper.fast_forward_tag(
            paused_tag_id="SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES_AST",
            fast_forward_to_date=datetime.now() + timedelta(minutes=1),
        )
        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES", plan_id=plan_id
        )

        # Once the schedules have run, they should have picked up the supervisee params and
        # rescheduled themselves to match
        plan_schedules = endtoend.schedule_helper.get_plan_schedules(plan_id)
        checking_schedules = endtoend.schedule_helper.get_account_schedules(checking_account_id)
        savings_schedules = endtoend.schedule_helper.get_account_schedules(savings_account_id)

        self.assertEqual(
            expected_next_run_time_checking.strftime("%Y-%m-%dT%H:%M:%SZ"),
            plan_schedules["SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES"]["next_run_timestamp"],
        )
        self.assertEqual(
            expected_next_run_time_savings.strftime("%Y-%m-%dT%H:%M:%SZ"),
            plan_schedules["SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES"]["next_run_timestamp"],
        )

        self.assertEqual(
            expected_next_run_time_checking.strftime("%Y-%m-%dT%H:%M:%SZ"),
            checking_schedules["APPLY_MONTHLY_FEES"]["next_run_timestamp"],
        )

        self.assertEqual(
            expected_next_run_time_savings.strftime("%Y-%m-%dT%H:%M:%SZ"),
            savings_schedules["APPLY_MONTHLY_FEES"]["next_run_timestamp"],
        )


if __name__ == "__main__":
    endtoend.runtests()
