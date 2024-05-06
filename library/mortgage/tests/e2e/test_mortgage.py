# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import sys

# common
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.helper import COMMON_ACCOUNT_SCHEDULE_TAG_PATH

# other
from library.mortgage.tests.e2e.mortgage_test_params import (
    mortgage_instance_params,
    mortgage_template_params,
    internal_accounts_tside,
    POSTING_BATCH_ACCEPTED,
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
    "interest": {"path": "library/common/contract_modules/interest.py"},
    "amortisation": {"path": "library/common/contract_modules/amortisation.py"},
}

endtoend.testhandle.WORKFLOWS = {
    "MORTGAGE_APPLICATION": "library/mortgage/workflows/mortgage_application.yaml",
    "MORTGAGE_CLOSURE": "library/mortgage/workflows/mortgage_closure.yaml",
    "MORTGAGE_EARLY_REPAYMENT": "library/mortgage/workflows/mortgage_early_repayment.yaml",
    "MORTGAGE_MARK_DELINQUENT": "library/mortgage/workflows/mortgage_mark_delinquent.yaml",
    "MORTGAGE_REPAYMENT_DAY_CHANGE": (
        "library/mortgage/workflows/mortgage_repayment_day_change.yaml"
    ),
    "MORTGAGE_REPAYMENT_HOLIDAY_APPLICATION": (
        "library/mortgage/workflows/mortgage_repayment_holiday_application.yaml"
    ),
    "MORTGAGE_SWITCH": "library/mortgage/workflows/mortgage_switch.yaml",
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "ACCOUNT_DELINQUENT": "library/common/flag_definitions/account_delinquent.resource.yaml",
    "REPAYMENT_HOLIDAY": "library/common/flag_definitions/repayment_holiday.resource.yaml",
}

endtoend.testhandle.ACCOUNT_SCHEDULE_TAGS = {
    "MORTGAGE_ACCRUE_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "MORTGAGE_REPAYMENT_DAY_SCHEDULE_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "MORTGAGE_HANDLE_OVERPAYMENT_ALLOWANCE_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "MORTGAGE_CHECK_DELINQUENCY_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
}


class MortgageAccountTests(endtoend.End2Endtest):
    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at
        # Uncomment this for timing info.
        # print('\n{} ({}s)'.format(self.id().rpartition('.')[2], round(self._elapsed_time, 2)))

    def test_account_creation(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_APPLICATION",
            context={
                "account_id": dummy_account_id,
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["mortgage"],
            },
        )

        # invalid term given
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_mortgage_parameters",
            event_name="mortgage_parameters_chosen",
            context={
                "deposit_account": "1",
                "fixed_interest_term": "13",
                "interest_only_term": "13",
                "total_term": "12",
                "fixed_interest_rate": "0.034544",
                "overpayment_percentage": "0.1",
                "overpayment_fee_percentage": "0.05",
                "principal": "100000",
                "repayment_day": "1",
                "variable_rate_adjustment": "0.00",
                "mortgage_start_date": datetime.strftime(datetime.utcnow(), "%Y-%m-%d"),
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "invalid_params")

        endtoend.workflows_helper.send_event(
            wf_id, event_state="invalid_params", event_name="retry_entry", context={}
        )

        # invalid variable rate adjustment given
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_mortgage_parameters",
            event_name="mortgage_parameters_chosen",
            context={
                "deposit_account": "1",
                "fixed_interest_term": "13",
                "interest_only_term": "13",
                "total_term": "12",
                "fixed_interest_rate": "0.034544",
                "overpayment_percentage": "0.1",
                "overpayment_fee_percentage": "0.05",
                "principal": "100000",
                "repayment_day": "1",
                "variable_rate_adjustment": "-0.13",
                "mortgage_start_date": datetime.strftime(datetime.utcnow(), "%Y-%m-%d"),
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "invalid_params")

        endtoend.workflows_helper.send_event(
            wf_id, event_state="invalid_params", event_name="retry_entry", context={}
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_mortgage_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_mortgage_parameters",
            event_name="mortgage_parameters_chosen",
            context={
                "deposit_account": "1",
                "fixed_interest_term": "9",
                "interest_only_term": "9",
                "total_term": "10",
                "fixed_interest_rate": "0.034544",
                "overpayment_percentage": "0.1",
                "overpayment_fee_percentage": "0.05",
                "principal": "100000",
                "repayment_day": "1",
                "variable_rate_adjustment": "0.00",
                "mortgage_start_date": datetime.strftime(datetime.utcnow(), "%Y-%m-%d"),
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        mortgage_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        mortgage_account = endtoend.contracts_helper.get_account(mortgage_account_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", mortgage_account["status"])

    def test_early_repayment_manual_fee(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = mortgage_instance_params.copy()
        instance_params["deposit_account"] = dummy_account_id
        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_EARLY_REPAYMENT", context={"account_id": mortgage_account["id"]}
        )

        endtoend.workflows_helper.send_event(
            wf_id, event_state="choose_fee_type", event_name="manual_fee", context={}
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_fee_details",
            event_name="fee_details_given",
            context={"fee_amount": "1234"},
        )

        endtoend.balances_helper.wait_for_account_balances(
            mortgage_account["id"],
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="PRINCIPAL", denomination="GBP"
                    ),
                    "100000",
                ),
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="PENALTIES", denomination="GBP"
                    ),
                    "1234",
                ),
            ],
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_repayment_account")

    def test_early_repayment_auto_erc_closes_account(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=dummy_account_id, amount="500000", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        instance_params = mortgage_instance_params.copy()
        instance_params["deposit_account"] = dummy_account_id
        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        # make an overpayment to incur the overpayment allowance fee
        posting_id2 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=mortgage_account["id"], amount="50000", denomination="GBP"
        )
        pib2 = endtoend.postings_helper.get_posting_batch(posting_id2)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib2["status"])
        endtoend.balances_helper.wait_for_account_balances(
            mortgage_account["id"],
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="PRINCIPAL", denomination="GBP"
                    ),
                    "100000",
                ),
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="PENALTIES", denomination="GBP"
                    ),
                    "0",
                ),
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="OVERPAYMENT", denomination="GBP"
                    ),
                    "-50000",
                ),
            ],
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_EARLY_REPAYMENT", context={"account_id": mortgage_account["id"]}
        )

        endtoend.workflows_helper.send_event(
            wf_id, event_state="choose_fee_type", event_name="auto_fee", context={}
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="input_erc_percentage",
            event_name="erc_fee_details_given",
            context={"erc_fee_percentage": "10"},
        )

        endtoend.balances_helper.wait_for_account_balances(
            mortgage_account["id"],
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="PRINCIPAL", denomination="GBP"
                    ),
                    "100000",
                ),
                (
                    # 5,000 (ERC fee) + 2,000 (overpayment fee) = 7,000
                    endtoend.balances_helper.BalanceDimensions(
                        address="PENALTIES", denomination="GBP"
                    ),
                    "7000",
                ),
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="OVERPAYMENT", denomination="GBP"
                    ),
                    "-50000",
                ),
            ],
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_repayment_account",
            event_name="account_selected",
            context={"repayment_account_id": dummy_account_id},
        )

        # Early repayment should trigger a contract initiated workflow to close the repaid mortgage
        mortgage_closure_wf = endtoend.workflows_helper.wait_for_smart_contract_initiated_workflows(
            account_id=mortgage_account["id"],
            workflow_definition_id=endtoend.testhandle.workflow_definition_id_mapping[
                "MORTGAGE_CLOSURE"
            ],
        )[0]

        # Once the contract-initiated workflow is finished, the account should be closed
        endtoend.workflows_helper.wait_for_state(
            mortgage_closure_wf["wf_instance_id"], "account_closed_successfully"
        )
        mortgage_account = endtoend.contracts_helper.get_account(mortgage_account["id"])
        self.assertEqual("ACCOUNT_STATUS_CLOSED", mortgage_account["status"])

        # Trying to close again should be handled by the workflow
        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_CLOSURE", context={"account_id": mortgage_account["id"]}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "account_already_closed")
        mortgage_account = endtoend.contracts_helper.get_account(mortgage_account["id"])
        self.assertEqual("ACCOUNT_STATUS_CLOSED", mortgage_account["status"])

    def test_early_repayment_skips_fee_posting_if_manual_or_erc_fee_zero(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = mortgage_instance_params.copy()
        instance_params["deposit_account"] = dummy_account_id
        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        # ERC Fee Route Test
        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_EARLY_REPAYMENT", context={"account_id": mortgage_account["id"]}
        )

        endtoend.workflows_helper.send_event(
            wf_id, event_state="choose_fee_type", event_name="auto_fee", context={}
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="input_erc_percentage",
            event_name="erc_fee_details_given",
            context={"erc_fee_percentage": "0"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_repayment_account")

        # Manual Fee Route Test
        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_EARLY_REPAYMENT", context={"account_id": mortgage_account["id"]}
        )

        endtoend.workflows_helper.send_event(
            wf_id, event_state="choose_fee_type", event_name="manual_fee", context={}
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_fee_details",
            event_name="fee_details_given",
            context={"fee_amount": "0"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_repayment_account")

    def test_mortgage_closure_workflow_with_balance(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = mortgage_instance_params.copy()
        instance_params["deposit_account"] = dummy_account_id
        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        self.assertEqual("ACCOUNT_STATUS_OPEN", mortgage_account["status"])

        endtoend.balances_helper.wait_for_account_balances(
            mortgage_account["id"],
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="PRINCIPAL", denomination="GBP"
                    ),
                    "100000",
                )
            ],
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_CLOSURE", context={"account_id": mortgage_account["id"]}
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closure_failure")

        mortgage_account = endtoend.contracts_helper.get_account(mortgage_account["id"])

        self.assertEqual("ACCOUNT_STATUS_OPEN", mortgage_account["status"])

    def test_mark_delinquency_workflow(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = mortgage_instance_params.copy()
        instance_params["deposit_account"] = dummy_account_id
        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        self.assertEqual("ACCOUNT_STATUS_OPEN", mortgage_account["status"])

        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_MARK_DELINQUENT", context={"account_id": mortgage_account["id"]}
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_delinquency_set")

        flag_status = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping["ACCOUNT_DELINQUENT"],
            account_ids=[mortgage_account["id"]],
        )

        self.assertEqual(flag_status[0]["account_id"], mortgage_account["id"])

    def test_switch_mortgage_positive_var_rate(self):
        # This test will convert from fixed to variable mortgage but with a positive
        # variable_rate_adjustment.
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=dummy_account_id, amount="10000", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        instance_params = mortgage_instance_params.copy()
        instance_params["deposit_account"] = dummy_account_id
        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        # Verify created account is currently a fixed mortgage
        self.assertEqual("12", mortgage_account["instance_param_vals"]["total_term"])
        self.assertEqual("12", mortgage_account["instance_param_vals"]["fixed_interest_term"])
        self.assertEqual(
            "0.00", mortgage_account["instance_param_vals"]["variable_rate_adjustment"]
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_SWITCH", context={"account_id": mortgage_account["id"]}
        )

        expected_dict = {
            "fixed_interest_rate": "0",
            "fixed_interest_term": "0",
            "variable_rate_adjustment": "0.17",
            "interest_only_term": "0",
            "total_term": "240",
        }

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_new_mortgage_terms",
            event_name="new_mortgage_terms_chosen",
            context=expected_dict,
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_product_switch",
            event_name="product_switch_confirmed",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "product_switched")

        mortgage_account = endtoend.contracts_helper.get_account(mortgage_account["id"])
        mortgage_start_date = mortgage_account["instance_param_vals"]["mortgage_start_date"]
        current_dict = {
            "fixed_interest_rate": mortgage_account["instance_param_vals"]["fixed_interest_rate"],
            "fixed_interest_term": mortgage_account["instance_param_vals"]["fixed_interest_term"],
            "variable_rate_adjustment": mortgage_account["instance_param_vals"][
                "variable_rate_adjustment"
            ],
            "interest_only_term": mortgage_account["instance_param_vals"]["interest_only_term"],
            "total_term": mortgage_account["instance_param_vals"]["total_term"],
        }

        self.assertEqual(datetime.utcnow().strftime("%Y-%m-%d"), mortgage_start_date)
        # If the below is true it is now a variable mortgage
        self.assertDictEqual(expected_dict, current_dict)

        endtoend.balances_helper.wait_for_account_balances(
            mortgage_account["id"],
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="PRINCIPAL", denomination="GBP"
                    ),
                    "100000",
                )
            ],
        )

    def test_switch_mortgage_negative_var_rate(self):
        # This test will convert from fixed to variable mortgage but with a negative
        # variable_rate_adjustment
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=dummy_account_id, amount="10000", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        instance_params = mortgage_instance_params.copy()
        instance_params["deposit_account"] = dummy_account_id
        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        # Verify created account is currently a fixed mortgage
        self.assertEqual("12", mortgage_account["instance_param_vals"]["total_term"])
        self.assertEqual("12", mortgage_account["instance_param_vals"]["fixed_interest_term"])
        self.assertEqual(
            "0.00", mortgage_account["instance_param_vals"]["variable_rate_adjustment"]
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_SWITCH", context={"account_id": mortgage_account["id"]}
        )

        expected_dict = {
            "fixed_interest_rate": "0",
            "fixed_interest_term": "0",
            "variable_rate_adjustment": "-0.129971",
            "interest_only_term": "0",
            "total_term": "240",
        }

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_new_mortgage_terms",
            event_name="new_mortgage_terms_chosen",
            context=expected_dict,
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_product_switch",
            event_name="product_switch_confirmed",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "product_switched")

        mortgage_account = endtoend.contracts_helper.get_account(mortgage_account["id"])
        mortgage_start_date = mortgage_account["instance_param_vals"]["mortgage_start_date"]
        current_dict = {
            "fixed_interest_rate": mortgage_account["instance_param_vals"]["fixed_interest_rate"],
            "fixed_interest_term": mortgage_account["instance_param_vals"]["fixed_interest_term"],
            "variable_rate_adjustment": mortgage_account["instance_param_vals"][
                "variable_rate_adjustment"
            ],
            "interest_only_term": mortgage_account["instance_param_vals"]["interest_only_term"],
            "total_term": mortgage_account["instance_param_vals"]["total_term"],
        }

        self.assertEqual(datetime.utcnow().strftime("%Y-%m-%d"), mortgage_start_date)
        # If the below is true it is now a variable mortgage
        self.assertDictEqual(expected_dict, current_dict)

        endtoend.balances_helper.wait_for_account_balances(
            mortgage_account["id"],
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="PRINCIPAL", denomination="GBP"
                    ),
                    "100000",
                )
            ],
        )

    def test_switch_mortgage_invalid_negative_interest_rate(self):
        # Variable rate / interest rate = variable_rate_adjustment (instance) +
        # variable_interest_rate (template)
        # Checks wether workflow will trigger rejection if final variable rate/ interest rate is
        # below 0
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=dummy_account_id, amount="10000", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        instance_params = mortgage_instance_params.copy()
        instance_params["deposit_account"] = dummy_account_id
        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        # Verify current adjustment rate is valid.
        self.assertEqual(
            "0.00", mortgage_account["instance_param_vals"]["variable_rate_adjustment"]
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_SWITCH", context={"account_id": mortgage_account["id"]}
        )
        # Current value for variable_interest_rate = 0.129971
        # After update it will become negative since we are summing -0.129972
        # [variable_rate_adjustment] and 0.129971 [variable_interest_rate]
        expected_dict = {
            "fixed_interest_rate": "0",
            "fixed_interest_term": "0",
            "variable_rate_adjustment": "-0.129972",
            "interest_only_term": "0",
            "total_term": "240",
        }

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_new_mortgage_terms",
            event_name="new_mortgage_terms_chosen",
            context=expected_dict,
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "invalid_mortgage_terms")
        workflow_local_context = endtoend.workflows_helper.get_state_local_context(
            wf_id, "invalid_mortgage_terms"
        )
        error_message = workflow_local_context["error_message"]
        self.assertEqual(
            error_message,
            "Invalid input:\n - Sum of variable rate and adjustment cannot be less than 0",
        )

    def test_change_mortgage_repayment_day(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = mortgage_instance_params.copy()
        instance_params["deposit_account"] = dummy_account_id
        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        self.assertEqual("ACCOUNT_STATUS_OPEN", mortgage_account["status"])

        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_REPAYMENT_DAY_CHANGE",
            context={"account_id": mortgage_account["id"], "user_id": cust_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="warn_too_soon_to_change_repayment_day",
            event_name="proceed_with_change",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="request_new_repayment_day",
            event_name="new_repayment_day_captured",
            context={"new_repayment_day": "15"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "repayment_day_update_success")
        endtoend.accounts_helper.wait_for_account_update(
            mortgage_account["id"], "instance_param_vals_update"
        )
        mortgage_account = endtoend.contracts_helper.get_account(mortgage_account["id"])
        new_repayment_day = mortgage_account["instance_param_vals"]["repayment_day"]

        self.assertEqual("15", new_repayment_day)

        account_schedules = endtoend.schedule_helper.get_account_schedules(mortgage_account["id"])

        repayment_day_schedule = account_schedules["REPAYMENT_DAY_SCHEDULE"]

        self.assertEqual(
            15,
            datetime.strptime(
                repayment_day_schedule["next_run_timestamp"], "%Y-%m-%dT%H:%M:%SZ"
            ).day,
        )

        # ensure new schedule will start after today to avoid past event catch-ups
        self.assertGreater(
            datetime.strptime(
                repayment_day_schedule["start_timestamp"], "%Y-%m-%dT%H:%M:%SZ"
            ).date(),
            datetime.utcnow().date(),
        )

        # Change repayment day rejected when REPAYMENT_HOLIDAY flag is active
        endtoend.core_api_helper.create_flag(
            endtoend.testhandle.flag_definition_id_mapping["REPAYMENT_HOLIDAY"],
            mortgage_account["id"],
        )

        wf_id_2 = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_REPAYMENT_DAY_CHANGE",
            context={"account_id": mortgage_account["id"], "user_id": cust_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id_2, "repayment_day_cannot_be_updated")

        mortgage_account = endtoend.contracts_helper.get_account(mortgage_account["id"])
        current_repayment_day = mortgage_account["instance_param_vals"]["repayment_day"]

        self.assertEqual("15", current_repayment_day)

        account_schedules = endtoend.schedule_helper.get_account_schedules(mortgage_account["id"])

        repayment_day_schedule = account_schedules["REPAYMENT_DAY_SCHEDULE"]

        self.assertEqual(
            15,
            datetime.strptime(
                repayment_day_schedule["next_run_timestamp"], "%Y-%m-%dT%H:%M:%SZ"
            ).day,
        )

        # ensure new schedule will start after today to avoid past event catch-ups
        self.assertGreater(
            datetime.strptime(
                repayment_day_schedule["start_timestamp"], "%Y-%m-%dT%H:%M:%SZ"
            ).date(),
            datetime.utcnow().date(),
        )

    def test_repayment_holiday_workflow(self):
        repayment_day = 21

        cust_id = endtoend.core_api_helper.create_customer()
        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = mortgage_instance_params.copy()
        instance_params["repayment_day"] = str(repayment_day)
        instance_params["deposit_account"] = dummy_account_id

        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        first_allowed_repayment_date = datetime.utcnow() + relativedelta(day=repayment_day)
        if first_allowed_repayment_date < datetime.utcnow():
            first_allowed_repayment_date += relativedelta(months=1)

        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_REPAYMENT_HOLIDAY_APPLICATION",
            context={"account_id": mortgage_account["id"]},
        )

        latest_state = endtoend.workflows_helper.wait_for_state(
            wf_id=wf_id, state_name="capture_repayment_holiday_period"
        )

        # 1. create a flag in the past
        start_time = first_allowed_repayment_date - relativedelta(months=1)
        end_time = first_allowed_repayment_date + relativedelta(months=1)

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_repayment_holiday_period",
            event_name="repayment_holiday_date_chosen",
            context={
                "repayment_holiday_start_date": start_time.strftime("%Y-%m-%d"),
                "repayment_holiday_end_date": end_time.strftime("%Y-%m-%d"),
            },
        )

        latest_state = endtoend.workflows_helper.wait_for_state(
            wf_id=wf_id,
            state_name="capture_repayment_holiday_period",
            starting_state_id=latest_state["id"],
        )

        # 2. create a flag not on the repayment date
        start_time = first_allowed_repayment_date + relativedelta(months=1, days=1)
        end_time = first_allowed_repayment_date + relativedelta(months=2)

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_repayment_holiday_period",
            event_name="repayment_holiday_date_chosen",
            context={
                "repayment_holiday_start_date": start_time.strftime("%Y-%m-%d"),
                "repayment_holiday_end_date": end_time.strftime("%Y-%m-%d"),
            },
        )

        latest_state = endtoend.workflows_helper.wait_for_state(
            wf_id=wf_id,
            state_name="capture_repayment_holiday_period",
            starting_state_id=latest_state["id"],
        )

        # 3. start date > end date
        start_time = first_allowed_repayment_date + relativedelta(months=3)
        end_time = first_allowed_repayment_date + relativedelta(months=1)

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_repayment_holiday_period",
            event_name="repayment_holiday_date_chosen",
            context={
                "repayment_holiday_start_date": start_time.strftime("%Y-%m-%d"),
                "repayment_holiday_end_date": end_time.strftime("%Y-%m-%d"),
            },
        )

        endtoend.workflows_helper.wait_for_state(
            wf_id=wf_id,
            state_name="capture_repayment_holiday_period",
            starting_state_id=latest_state["id"],
        )

        # 4. create valid flag
        start_time = first_allowed_repayment_date + relativedelta(months=1)
        end_time = first_allowed_repayment_date + relativedelta(months=2)

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_repayment_holiday_period",
            event_name="repayment_holiday_date_chosen",
            context={
                "repayment_holiday_start_date": start_time.strftime("%Y-%m-%d"),
                "repayment_holiday_end_date": end_time.strftime("%Y-%m-%d"),
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "repayment_holiday_set")

        # start new workflow on the same account
        wf_id_2 = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_REPAYMENT_HOLIDAY_APPLICATION",
            context={"account_id": mortgage_account["id"]},
        )

        endtoend.workflows_helper.wait_for_state(wf_id_2, "capture_repayment_holiday_period")

        # 5. create flag with same time as previous flag
        start_time = first_allowed_repayment_date + relativedelta(months=1)
        end_time = first_allowed_repayment_date + relativedelta(months=2)

        endtoend.workflows_helper.send_event(
            wf_id_2,
            event_state="capture_repayment_holiday_period",
            event_name="repayment_holiday_date_chosen",
            context={
                "repayment_holiday_start_date": start_time.strftime("%Y-%m-%d"),
                "repayment_holiday_end_date": end_time.strftime("%Y-%m-%d"),
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id_2, "account_already_on_holiday")

        # start new workflow on the same account
        wf_id_3 = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_REPAYMENT_HOLIDAY_APPLICATION",
            context={"account_id": mortgage_account["id"]},
        )

        endtoend.workflows_helper.wait_for_state(wf_id_3, "capture_repayment_holiday_period")

        # 6. create a flag in the future after the previous flag
        start_time = first_allowed_repayment_date + relativedelta(months=2)
        end_time = first_allowed_repayment_date + relativedelta(months=3)

        endtoend.workflows_helper.send_event(
            wf_id_3,
            event_state="capture_repayment_holiday_period",
            event_name="repayment_holiday_date_chosen",
            context={
                "repayment_holiday_start_date": start_time.strftime("%Y-%m-%d"),
                "repayment_holiday_end_date": end_time.strftime("%Y-%m-%d"),
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id_3, "repayment_holiday_set")


if __name__ == "__main__":
    endtoend.runtests()
