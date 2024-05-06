# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os

# library
import library.line_of_credit.constants.files as contract_files
import library.line_of_credit.constants.test_parameters as test_parameters

# inception sdk
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


default_loan_instance_params = test_parameters.e2e_drawdown_loan_instance_params
default_loan_template_params = test_parameters.e2e_drawdown_loan_template_params
default_loc_instance_params = test_parameters.e2e_loc_instance_params
default_loc_template_params = test_parameters.e2e_loc_template_params

default_loan_instance_params.update({"deposit_account": "1"})

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = test_parameters.internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "drawdown_loan": {
        "path": contract_files.DRAWDOWN_LOAN_CONTRACT,
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
    def setUp(self):
        self.loan_accounts = []
        return super().setUp()

    def tearDown(self) -> None:
        for loan in self.loan_accounts:
            endtoend.contracts_helper.terminate_account(loan)
        return super().tearDown()

    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {"line_of_credit_supervisor": ["SUPERVISEE_SCHEDULE_SYNC", "ACCRUE_INTEREST"]}
    )
    def test_initial_accrual(self):
        endtoend.standard_setup()
        cust_id = endtoend.core_api_helper.create_customer()

        loc_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="line_of_credit",
            instance_param_vals=default_loc_instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=test_parameters.default_simulation_start_date.isoformat(),
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
            opening_timestamp=test_parameters.default_simulation_start_date.isoformat(),
        )
        drawdown_loan_0_id = drawdown_loan_0["id"]

        drawdown_1_instance_params = loan_instance_params.copy()
        drawdown_1_instance_params["principal"] = "500"

        drawdown_loan_1 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="drawdown_loan",
            instance_param_vals=drawdown_1_instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=test_parameters.default_simulation_start_date.isoformat(),
        )
        drawdown_loan_1_id = drawdown_loan_1["id"]

        self.loan_accounts = [drawdown_loan_0, drawdown_loan_1]

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

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            schedule_name="SUPERVISEE_SCHEDULE_SYNC",
            plan_id=plan_id,
        )
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            schedule_name="ACCRUE_INTEREST",
            plan_id=plan_id,
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
                        "0.61233",
                    ),
                ],
            }
        )


if __name__ == "__main__":
    endtoend.runtests()
