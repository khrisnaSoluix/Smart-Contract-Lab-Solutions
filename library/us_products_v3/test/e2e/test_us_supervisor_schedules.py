# standard libs
import sys
from datetime import datetime
from dateutil.relativedelta import relativedelta

# library
from library.us_products_v3.test.e2e.us_products_test_params import (
    DEFAULT_CONTRACTS,
    DEFAULT_SUPERVISORCONTRACTS,
    US_CHECKING_FLAG_DEFINITIONS,
    US_SAVINGS_FLAG_DEFINITIONS,
    checking_account_instance_params,
    checking_account_template_params,
    internal_accounts_tside,
    us_savings_account_template_params,
)

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

sys.path.append(".")

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = DEFAULT_CONTRACTS

endtoend.testhandle.CONTRACT_MODULES = {
    "interest": {"path": "library/common/contract_modules/interest.py"},
    "utils": {"path": "library/common/contract_modules/utils.py"},
}
endtoend.testhandle.SUPERVISORCONTRACTS = DEFAULT_SUPERVISORCONTRACTS

endtoend.testhandle.WORKFLOWS = {}

endtoend.testhandle.FLAG_DEFINITIONS = {
    **US_CHECKING_FLAG_DEFINITIONS,
    **US_SAVINGS_FLAG_DEFINITIONS,
}


class OverdraftProtectionSupervisorTest(endtoend.AcceleratedEnd2EndTest):

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

    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {
            "us_v3": [
                "SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES",
                "SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES",
            ]
        }
    )
    def test_supervisor_schedules_synchronise_with_supervisees_after_first_job(self):
        endtoend.standard_setup()
        cust_id = endtoend.core_api_helper.create_customer()

        checking_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account_v3",
            instance_param_vals=checking_account_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        checking_account_id = checking_account["id"]

        savings_instance_params = {"interest_application_day": "1"}
        us_savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account_v3",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        savings_account_id = us_savings_account["id"]

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "us_v3",
            [checking_account_id, savings_account_id],
        )

        creation_date = datetime.strptime(
            checking_account["opening_timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        expected_next_run_time_checking = self.next_fee_schedule_timestamp(
            creation_date, checking_account_template_params
        )
        creation_date = datetime.strptime(
            us_savings_account["opening_timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        expected_next_run_time_savings = self.next_fee_schedule_timestamp(
            creation_date, us_savings_account_template_params
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            schedule_name="SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES",
            plan_id=plan_id,
        )
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            schedule_name="SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES",
            plan_id=plan_id,
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

    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {"us_v3": ["SETUP_ODP_LINK", "ODP_SWEEP"]}
    )
    def test_odp_sweep_occurs_when_linked_checking_is_overdrafted(
        self,
    ):
        endtoend.standard_setup()
        cust_id = endtoend.core_api_helper.create_customer()

        checking_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account_v3",
            instance_param_vals=checking_account_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        checking_account_id = checking_account["id"]
        savings_instance_params = {"interest_application_day": "1"}
        savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account_v3",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        savings_account_id = savings_account["id"]

        endtoend.supervisors_helper.link_accounts_to_supervisor(
            "us_v3", [checking_account_id, savings_account_id]
        )
        plan_id = endtoend.testhandle.plans[-1]

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            schedule_name="SETUP_ODP_LINK",
            plan_id=plan_id,
        )

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=checking_account_id,
            amount="100",
            denomination="USD",
            instruction_details={"description": "Deposit to checking account"},
        )

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=savings_account_id,
            amount="1000",
            denomination="USD",
            instruction_details={"description": "Deposit to savings account"},
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            accounts_expected_balances={
                checking_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "100")
                ],
                savings_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "1000")
                ],
            }
        )

        endtoend.postings_helper.outbound_hard_settlement(
            account_id=checking_account_id,
            amount="1000",
            denomination="USD",
            instruction_details={"description": "Withdrawal from checking account"},
        )

        endtoend.balances_helper.wait_for_account_balances(
            checking_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="USD"), "-900")],
            description="Overdraft permitted, 1000 deducted from checking",
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            schedule_name="ODP_SWEEP",
            plan_id=plan_id,
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            accounts_expected_balances={
                checking_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "0")
                ],
                savings_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "100")
                ],
            }
        )


if __name__ == "__main__":
    endtoend.runtests()
