# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
import logging
import os

# standard libs
from time import time
from datetime import datetime, timedelta

# common
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions

# constants
import library.line_of_credit.constants.files as contract_files
import library.line_of_credit.constants.test_parameters as test_parameters

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


default_loan_instance_params = test_parameters.e2e_loan_instance_params
default_loan_template_params = test_parameters.e2e_loan_template_params
default_loc_instance_params = test_parameters.e2e_loc_instance_params
default_loc_template_params = test_parameters.e2e_loc_template_params

default_loc_template_params.update(
    {
        "minimum_loan_amount": "50",
        "maximum_loan_amount": "1000",
    }
)

default_loan_instance_params.update({"deposit_account": "1"})

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = test_parameters.internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "drawdown_loan": {
        "path": contract_files.LOAN_CONTRACT,
        "template_params": default_loan_template_params,
        "supervisee_alias": "drawdown_loan",
    },
    "line_of_credit": {
        "path": contract_files.LOC_CONTRACT,
        "template_params": default_loc_template_params,
        "supervisee_alias": "line_of_credit",
    },
}

endtoend.testhandle.SUPERVISORCONTRACTS = {
    "line_of_credit_supervisor": {
        "path": contract_files.LOC_SUPERVISOR,
    }
}


class LineOfCreditSupervisorSchedulesTest(endtoend.AcceleratedEnd2EndTest):

    default_tags = test_parameters.DEFAULT_TAGS

    def setUp(self):
        self._started_at = time()

    def tearDown(self):
        self._elapsed_time = time() - self._started_at
        # Uncomment this for timing info.
        # print('\n{} ({}s)'.format(self.id().rpartition('.')[2], round(self._elapsed_time, 2)))

    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags(
        {
            "SETUP_LOC_LINK_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": test_parameters.SCHEDULE_TAGS_DIR + "paused_tag.resource.yaml",
            },
            "LINE_OF_CREDIT_SUPERVISOR_ACCRUE_INTEREST_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": test_parameters.SCHEDULE_TAGS_DIR
                + "paused_accrue_interest.resource.yaml",
            },
        },
    )
    def test_initial_accrual(self):
        endtoend.standard_setup()
        cust_id = endtoend.core_api_helper.create_customer()

        loc_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="line_of_credit",
            instance_param_vals=default_loc_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        loc_account_id = loc_account["id"]
        loan_instance_params = default_loan_instance_params | {
            "line_of_credit_account_id": loc_account_id
        }

        drawdown_loan_0 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="drawdown_loan",
            instance_param_vals=loan_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        drawdown_loan_0_id = drawdown_loan_0["id"]

        drawdown_1_instance_params = loan_instance_params.copy()
        drawdown_1_instance_params["principal"] = "500"

        drawdown_loan_1 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="drawdown_loan",
            instance_param_vals=drawdown_1_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        drawdown_loan_1_id = drawdown_loan_1["id"]

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "line_of_credit_supervisor",
            [loc_account_id, drawdown_loan_0_id, drawdown_loan_1_id],
        )

        # check each drawdown has it's own principal
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                drawdown_loan_0_id: [
                    (BalanceDimensions(address="PRINCIPAL", denomination="GBP"), "1000")
                ],
                drawdown_loan_1_id: [
                    (BalanceDimensions(address="PRINCIPAL", denomination="GBP"), "500")
                ],
            }
        )

        # The schedule starts are set to 6s from plan creation date, so we can fast-fwd by a minute
        # and expect the jobs to be published
        endtoend.schedule_helper.fast_forward_tag(
            paused_tag_id="SETUP_LOC_LINK_AST",
            fast_forward_to_date=datetime.now() + timedelta(hours=2),
        )
        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="SETUP_LOC_LINK", plan_id=plan_id
        )
        endtoend.schedule_helper.fast_forward_tag(
            paused_tag_id="LINE_OF_CREDIT_SUPERVISOR_ACCRUE_INTEREST_AST",
            fast_forward_to_date=datetime.now() + timedelta(days=1),
        )
        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="ACCRUE_INTEREST", plan_id=plan_id
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                drawdown_loan_0_id: [
                    (
                        BalanceDimensions(
                            address="ACCRUED_INTEREST_RECEIVABLE",
                            asset="COMMERCIAL_BANK_MONEY",
                            denomination="GBP",
                            phase="POSTING_PHASE_COMMITTED",
                        ),
                        "0.40822",
                    ),
                ],
                drawdown_loan_1_id: [
                    (
                        BalanceDimensions(
                            address="ACCRUED_INTEREST_RECEIVABLE",
                            asset="COMMERCIAL_BANK_MONEY",
                            denomination="GBP",
                            phase="POSTING_PHASE_COMMITTED",
                        ),
                        "0.20411",
                    ),
                ],
                loc_account_id: [
                    (
                        BalanceDimensions(
                            address="TOTAL_ACCRUED_INTEREST_RECEIVABLE",
                            asset="COMMERCIAL_BANK_MONEY",
                            denomination="GBP",
                            phase="POSTING_PHASE_COMMITTED",
                        ),
                        "0.61",
                    ),
                ],
            }
        )


if __name__ == "__main__":
    endtoend.runtests()
