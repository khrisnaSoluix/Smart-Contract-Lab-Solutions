# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import sys
from datetime import datetime, timezone

# library
from library.mortgage.contracts.template import mortgage
from library.mortgage.test import dimensions, files
from library.mortgage.test.e2e import accounts, parameters

# inception sdk
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT

sys.path.insert(0, ".")

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = accounts.internal_accounts_tside
endtoend.testhandle.CONTRACTS = {
    "mortgage": {
        "path": files.MORTGAGE_CONTRACT,
        "template_params": parameters.default_template,
    },
    "dummy_account": {
        "path": DUMMY_CONTRACT,
    },
}
endtoend.testhandle.FLAG_DEFINITIONS = {
    "ACCOUNT_DELINQUENT": "library/common/flag_definitions/account_delinquent.resource.yaml",
    # "REPAYMENT_HOLIDAY": "library/common/flag_definitions/repayment_holiday.resource.yaml",
}


class MortgageProductTest(endtoend.AcceleratedEnd2EndTest):
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules({"mortgage": ["ACCRUE_INTEREST"]})
    def test_accrual_interest(self):
        endtoend.standard_setup()
        opening_date = datetime(
            year=2022,
            month=5,
            day=13,
            hour=13,
            tzinfo=timezone.utc,
        )
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = {
            **parameters.default_instance,
            mortgage.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
            mortgage.disbursement.PARAM_PRINCIPAL: "100000",
        }

        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        mort_account_id = mortgage_account["id"]

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=mort_account_id,
            schedule_name="ACCRUE_INTEREST",
            effective_date=datetime(2022, 5, 14, 0, 0, 1, tzinfo=timezone.utc),
        )

        # principal = 100000, fixed_interest_rate = 0.01
        # Daily interest = 100000 x (0.01/365) = 2.73973" (5dp)
        endtoend.balances_helper.wait_for_account_balances(
            account_id=mort_account_id,
            expected_balances=[
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "2.73973"),
            ],
        )


if __name__ == "__main__":
    endtoend.runtests()
