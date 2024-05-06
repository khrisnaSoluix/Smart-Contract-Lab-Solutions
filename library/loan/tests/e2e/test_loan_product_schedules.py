# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os
import time
from datetime import datetime, timezone

# third party
from dateutil.relativedelta import relativedelta

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
from library.common.flag_definitions.files import ACCOUNT_DELINQUENT, REPAYMENT_HOLIDAY

# Loan specific
import library.loan.constants.dimensions as dimensions
import library.loan.constants.files as contract_files

from library.loan.tests.e2e.loan_test_params import (
    internal_accounts_tside,
    loan_instance_params,
    loan_template_params,
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
    "loan": {
        "path": contract_files.CONTRACT_FILE,
        "template_params": loan_template_params,
    },
    "dummy_account": {
        "path": DUMMY_CONTRACT,
    },
}

endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": contract_files.files.UTILS_FILE},
    "amortisation": {"path": contract_files.files.AMORTISATION_FILE},
}

endtoend.testhandle.WORKFLOWS = {}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "ACCOUNT_DELINQUENT": ACCOUNT_DELINQUENT,
    "REPAYMENT_HOLIDAY": REPAYMENT_HOLIDAY,
}


class LoanProductSchedulesTest(endtoend.AcceleratedEnd2EndTest):

    default_tags = DEFAULT_TAGS

    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at
        # Uncomment this for timing info.
        # print('\n{} ({}s)'.format(self.id().rpartition('.')[2], round(self._elapsed_time, 2)))

    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags(
        {
            "LOAN_ACCRUE_INTEREST_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_loan_accrual_tag.resource.yaml",
            }
        }
    )
    def test_initial_accrual(self):
        endtoend.standard_setup()
        opening_date = datetime.now().astimezone(timezone.utc) - relativedelta(days=2)
        customer_id = endtoend.core_api_helper.create_customer()

        dummy_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        dummy_account_id = dummy_account["id"]

        instance_params = loan_instance_params.copy()
        instance_params["deposit_account"] = dummy_account_id
        instance_params["loan_start_date"] = datetime.strftime(opening_date, "%Y-%m-%d")
        loan_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        loan_account_id = loan_account["id"]

        endtoend.schedule_helper.trigger_next_schedule_execution(
            paused_tag_id="LOAN_ACCRUE_INTEREST_AST",
            schedule_frequency=self.paused_tags["LOAN_ACCRUE_INTEREST_AST"]["schedule_frequency"],
        )

        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="ACCRUE_INTEREST",
            account_id=loan_account_id,
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=loan_account_id,
            expected_balances=[
                (dimensions.ACCRUED_INTEREST, "0.09464"),
            ],
        )
