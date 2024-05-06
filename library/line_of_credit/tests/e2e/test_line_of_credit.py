# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.

# standard libs
from time import time

# common
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT

# third_party
import requests

# constants
import library.line_of_credit.constants.dimensions as dimensions
import library.line_of_credit.constants.files as contract_files
import library.line_of_credit.constants.test_parameters as test_parameters


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
    "dummy_deposit_account": {"path": DUMMY_CONTRACT},
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

endtoend.testhandle.ACCOUNT_SCHEDULE_TAGS = test_parameters.DEFAULT_TAGS.copy()

endtoend.testhandle.WORKFLOWS = {
    "LINE_OF_CREDIT_CREATE_DRAWDOWN": "library/line_of_credit/workflows/"
    + "line_of_credit_create_drawdown.yaml",
}


class LineOfCreditSupervisorTest(endtoend.End2Endtest):
    def setUp(self):
        self._started_at = time()

    def tearDown(self):
        self._elapsed_time = time() - self._started_at

    # test case 1_A_B_3_A_B
    def test_1_3_drawdowns_exceeding_limits_are_rejected(self):
        cust_id = endtoend.core_api_helper.create_customer()
        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["credit_limit"] = "1000"
        loc_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="line_of_credit",
            instance_param_vals=loc_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        loc_account_id = loc_account["id"]

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "line_of_credit_supervisor",
            [
                loc_account_id,
            ],
        )

        # test max loan limit
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=loc_account_id, amount="1001", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # test min loan limit
        postingID_1 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=loc_account_id, amount="1", denomination="GBP"
        )

        pib_1 = endtoend.postings_helper.get_posting_batch(postingID_1)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib_1["status"])

        # Request a valid drawdown
        postingID_2 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=loc_account_id, amount="500", denomination="GBP"
        )
        pib_2 = endtoend.postings_helper.get_posting_batch(postingID_2)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_2["status"])

        # Open corresponding loan and associate to plan
        loan_instance_params = default_loan_instance_params | {
            "line_of_credit_account_id": loc_account_id,
            "principal": "500",
        }
        drawdown_loan = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="drawdown_loan",
            instance_param_vals=loan_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        drawdown_loan_id = drawdown_loan["id"]
        endtoend.supervisors_helper.add_account_to_plan(plan_id, drawdown_loan_id)
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                drawdown_loan_id: [(dimensions.PRINCIPAL, "500")],
                loc_account_id: [(dimensions.DEFAULT, "500")],
            }
        )

        # Request another valid drawdown - total credit limit usage is 600
        # but do not open the corresponding loan
        postingID_3 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=loc_account_id, amount="100", denomination="GBP"
        )
        pib_3 = endtoend.postings_helper.get_posting_batch(postingID_3)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_3["status"])
        endtoend.balances_helper.wait_for_all_account_balances(
            {loc_account_id: [(dimensions.DEFAULT, "600")]}
        )

        # extra drawdown rejected as remaining limit is 400
        postingID_4 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=loc_account_id, amount="401", denomination="GBP"
        )

        pib_4 = endtoend.postings_helper.get_posting_batch(postingID_4)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib_4["status"])

        # extra drawdown accepted as remaining limit is 400
        postingID_5 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=loc_account_id, amount="399", denomination="GBP"
        )

        pib_5 = endtoend.postings_helper.get_posting_batch(postingID_5)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_5["status"])
        endtoend.balances_helper.wait_for_all_account_balances(
            {loc_account_id: [(dimensions.DEFAULT, "999")]}
        )

    def test_2_A_D_drawdown_loan_behaviour(self):
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

        endtoend.supervisors_helper.link_accounts_to_supervisor(
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

        # check LOC still open after loans are paid back
        account_status = endtoend.contracts_helper.get_account(loc_account_id)["status"]
        self.assertEqual(account_status, "ACCOUNT_STATUS_OPEN")

    def test_1_D_credit_limit_amendable_no_less_than_total_across_loans(self):

        cust_id = endtoend.core_api_helper.create_customer()

        loc_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="line_of_credit",
            instance_param_vals=default_loc_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        loc_account_id = loc_account["id"]

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "line_of_credit_supervisor", [loc_account_id]
        )

        # associate two loans
        loan_instance_params = default_loan_instance_params | {
            "line_of_credit_account_id": loc_account_id,
            "principal": "500",
        }
        drawdown_loan_1 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="drawdown_loan",
            instance_param_vals=loan_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        drawdown_loan_id_1 = drawdown_loan_1["id"]
        drawdown_loan_2 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="drawdown_loan",
            instance_param_vals=loan_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        drawdown_loan_id_2 = drawdown_loan_2["id"]
        endtoend.supervisors_helper.add_account_to_plan(plan_id, drawdown_loan_id_1)
        endtoend.supervisors_helper.add_account_to_plan(plan_id, drawdown_loan_id_2)
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                drawdown_loan_id_1: [
                    (BalanceDimensions(address="PRINCIPAL", denomination="GBP"), "500")
                ],
                drawdown_loan_id_2: [
                    (BalanceDimensions(address="PRINCIPAL", denomination="GBP"), "500")
                ],
            }
        )

        # ensure credit limit can be increased
        resp = endtoend.core_api_helper.update_account_instance_parameters(
            loc_account_id,
            instance_param_vals={"credit_limit": "1200"},
        )
        endtoend.accounts_helper.wait_for_account_update(account_update_id=resp["id"])

        # Check credit_limit cannot be made lower than the sum of the loans (1000)
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            endtoend.core_api_helper.update_account_instance_parameters(
                loc_account_id,
                instance_param_vals={"credit_limit": "999"},
            )

        self.assertEqual(400, context.exception.response.status_code)
        # assertion to ensure it is the correct endpoint
        self.assertIn("v1/account-updates", str(context.exception))

        # check that the credit_limit is still at 1200
        loc_account_after_parameter_change = endtoend.contracts_helper.get_account(loc_account_id)
        self.assertEqual(
            "1200",
            loc_account_after_parameter_change["instance_param_vals"]["credit_limit"],
            "Update credit_limit should have been rejected and remained at 1200",
        )

        # Check credit_limit can be lowered to exact usage
        account_update = endtoend.core_api_helper.update_account_instance_parameters(
            loc_account_id,
            instance_param_vals={"credit_limit": "1000"},
        )
        endtoend.accounts_helper.wait_for_account_update(account_update_id=account_update["id"])
        loc_account_after_parameter_change = endtoend.contracts_helper.get_account(loc_account_id)
        self.assertEqual(
            "1000",
            loc_account_after_parameter_change["instance_param_vals"]["credit_limit"],
            "Update credit_limit should have been updated and lowered to 1000",
        )

        # make a repayment and check credit limit can be lowered further
        postingID_6 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=loc_account_id, amount="400", denomination="GBP"
        )
        pib_6 = endtoend.postings_helper.get_posting_batch(postingID_6)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_6["status"])
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                drawdown_loan_id_1: [
                    # there is an early repayment fee of 400 * 0.01 = 4
                    (BalanceDimensions(address="PRINCIPAL", denomination="GBP"), "104")
                ],
                loc_account_id: [
                    # there is an early repayment fee of 400 * 0.01 = 4
                    (BalanceDimensions(address="TOTAL_PRINCIPAL", denomination="GBP"), "604")
                ],
            }
        )
        account_update = endtoend.core_api_helper.update_account_instance_parameters(
            loc_account_id,
            instance_param_vals={"credit_limit": "605"},
        )
        endtoend.accounts_helper.wait_for_account_update(account_update_id=account_update["id"])
        loc_account_after_parameter_change = endtoend.contracts_helper.get_account(loc_account_id)
        self.assertEqual(
            "605",
            loc_account_after_parameter_change["instance_param_vals"]["credit_limit"],
            "Update credit_limit should have been updated and lowered to 1000",
        )

        # But not beyond the new limit
        # Check credit_limit cannot be made lower than the sum of the loans (604)
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            endtoend.core_api_helper.update_account_instance_parameters(
                loc_account_id,
                instance_param_vals={"credit_limit": "603"},
            )

        self.assertEqual(400, context.exception.response.status_code)
        # assertion to ensure it is the correct endpoint
        self.assertIn("v1/account-updates", str(context.exception))

    def test_15_create_drawdown_workflow(self):
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_deposit_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_deposit_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        loc_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="line_of_credit",
            instance_param_vals=default_loc_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        loc_account_id = loc_account["id"]

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "line_of_credit_supervisor",
            [loc_account_id],
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "LINE_OF_CREDIT_CREATE_DRAWDOWN",
            context={
                "user_id": cust_id,
                "plan_id": plan_id,
                "loc_account_id": loc_account_id,
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_loan_parameters",
            event_name="drawdown_loan_parameters_selected",
            context={
                "fixed_interest_rate": "0.149",
                "total_term": "12",
                "principal": "1000",
            },
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_deposit_account",
            event_name="deposit_account_selected",
            context={
                "deposit_account": dummy_deposit_account_id,
            },
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "drawdown_successful")

        loan_account_id = endtoend.workflows_helper.get_global_context(wf_id)["loan_account_id"]
        loan_account = endtoend.contracts_helper.get_account(loan_account_id)
        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

        result_dict = {
            "fixed_interest_rate": loan_account["instance_param_vals"]["fixed_interest_rate"],
            "total_term": loan_account["instance_param_vals"]["total_term"],
            "principal": loan_account["instance_param_vals"]["principal"],
            "deposit_account": loan_account["instance_param_vals"]["deposit_account"],
        }

        expected_dict = {
            "fixed_interest_rate": "0.149",
            "total_term": "12",
            "principal": "1000",
            "deposit_account": dummy_deposit_account_id,
        }

        self.assertDictEqual(result_dict, expected_dict)

        endtoend.balances_helper.wait_for_account_balances(
            loan_account_id,
            expected_balances=[(dimensions.PRINCIPAL, "1000")],
        )

        # clear balance
        endtoend.postings_helper.inbound_hard_settlement(
            account_id=loc_account_id, amount="1000", denomination="GBP", override=True
        )
