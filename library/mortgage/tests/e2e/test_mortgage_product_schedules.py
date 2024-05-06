# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import sys
import time
from datetime import datetime, timezone

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions

# other
from library.mortgage.tests.e2e.mortgage_test_params import (
    SCHEDULE_TAGS_DIR_SCHEDULE_TESTS,
    mortgage_instance_params,
    mortgage_template_params,
    DEFAULT_TAGS,
    internal_accounts_tside,
)

sys.path.insert(0, ".")

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "mortgage": {
        "path": "library/mortgage/contracts/mortgage.py",
        "template_params": mortgage_template_params,
    },
    "dummy_account": {
        "path": DUMMY_CONTRACT,
    },
}
endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"},
    "amortisation": {"path": "library/common/contract_modules/amortisation.py"},
}
endtoend.testhandle.FLAG_DEFINITIONS = {
    "ACCOUNT_DELINQUENT": "library/common/flag_definitions/account_delinquent.resource.yaml",
    "REPAYMENT_HOLIDAY": "library/common/flag_definitions/repayment_holiday.resource.yaml",
}


class MortgageProductTest(endtoend.AcceleratedEnd2EndTest):
    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at

    default_tags = DEFAULT_TAGS

    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags(
        {
            "MORTGAGE_ACCRUE_INTEREST_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR_SCHEDULE_TESTS
                + "paused_mortgage_accrual_tag.resource.yaml",
            }
        }
    )
    def test_accrual_interest(self):
        endtoend.standard_setup()
        opening_date = datetime(
            year=2022,
            month=5,
            day=13,
            hour=13,
            tzinfo=timezone.utc,
        )
        str_opening_date = datetime.strftime(opening_date, "%Y-%m-%d")
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = mortgage_instance_params.copy()
        instance_params["mortgage_start_date"] = str_opening_date
        instance_params["deposit_account"] = dummy_account_id

        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        mort_account_id = mortgage_account["id"]

        endtoend.schedule_helper.trigger_next_schedule_execution(
            paused_tag_id="MORTGAGE_ACCRUE_INTEREST_AST",
            schedule_frequency=self.paused_tags["MORTGAGE_ACCRUE_INTEREST_AST"][
                "schedule_frequency"
            ],
        )

        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="ACCRUE_INTEREST",
            account_id=mort_account_id,
        )

        # principal = 100000, fixed_interest_rate = 0.034544
        # Daily interest = 100000 x (0.034544/365) = 9.46411 (5dp)
        endtoend.balances_helper.wait_for_account_balances(
            account_id=mort_account_id,
            expected_balances=[
                (BalanceDimensions("ACCRUED_EXPECTED_INTEREST"), "9.46411"),
            ],
        )


if __name__ == "__main__":
    endtoend.runtests()
