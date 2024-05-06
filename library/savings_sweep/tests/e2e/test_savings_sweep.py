# standard libs
import sys
import time
from datetime import datetime
from json import dumps, loads

from library.savings_sweep.tests.e2e.savings_sweep_test_params import (
    ca_template_params,
    ca_instance_params,
    savings_template_params,
    internal_accounts_tside,
)

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
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

endtoend.testhandle.ACCOUNT_SCHEDULE_TAGS = {
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

endtoend.testhandle.WORKFLOWS = {
    "SAVINGS_SWEEP_CHECKING_AND_SAVINGS_ACCOUNT_APPLICATION": (
        "library/savings_sweep/workflows/"
        "savings_sweep_checking_and_savings_account_application.yaml"
    ),
    "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION": (
        "library/savings_sweep/workflows/savings_sweep_account_association.yaml"
    ),
    "US_PRODUCTS_CLOSURE": "library/us_products/workflows/us_products_closure.yaml",
    "SAVINGS_SWEEP_SAVINGS_ACCOUNT_DISASSOCIATION": (
        "library/savings_sweep/workflows/" "savings_sweep_savings_account_disassociation.yaml"
    ),
    "SAVINGS_SWEEP_HIERARCHY_MANAGEMENT": (
        "library/savings_sweep/workflows/savings_sweep_hierarchy_management.yaml"
    ),
}

STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG = "STANDARD_OVERDRAFT_TRANSACTION_COVERAGE"
endtoend.testhandle.FLAG_DEFINITIONS = {
    "US_CHECKING_ACCOUNT_TIER_UPPER": (
        "library/us_products/flag_definitions/us_checking_account_tier_upper.resource.yaml"
    ),
    "US_CHECKING_ACCOUNT_TIER_MIDDLE": (
        "library/us_products/flag_definitions/us_checking_account_tier_middle.resource.yaml"
    ),
    "US_CHECKING_ACCOUNT_TIER_LOWER": (
        "library/us_products/flag_definitions/us_checking_account_tier_lower.resource.yaml"
    ),
    "US_SAVINGS_ACCOUNT_TIER_UPPER": (
        "library/us_products/flag_definitions/us_savings_account_tier_upper.resource.yaml"
    ),
    "US_SAVINGS_ACCOUNT_TIER_MIDDLE": (
        "library/us_products/flag_definitions/us_savings_account_tier_middle.resource.yaml"
    ),
    "US_SAVINGS_ACCOUNT_TIER_LOWER": (
        "library/us_products/flag_definitions/us_savings_account_tier_lower.resource.yaml"
    ),
    # Used by US Savings
    "PROMOTIONAL_INTEREST_RATES": (
        "library/us_products/flag_definitions/promotional_interest_rates.resource.yaml"
    ),
    # Used by US Checking
    "ACCOUNT_DORMANT": "library/common/flag_definitions/account_dormant.resource.yaml",
    STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG: (
        "library/us_products/flag_definitions/overdraft_transaction_coverage.resource.yaml"
    ),
    # Used by US Checking and Savings
    "PROMOTIONAL_MAINTENANCE_FEE": (
        "library/us_products/flag_definitions/promotional_maintenance_fee.resource.yaml"
    ),
}


class SavingsSweepSupervisorTest(endtoend.End2Endtest):
    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at

    def test_workflow_apply_for_savings_and_checking_account_succeeds(self):
        """
        Test apply for a linked checking and savings account and that instance parameter
        values are as expected. Apply again to check the application is rejected
        since the customer already has an existing plan
        """

        cust_id = endtoend.core_api_helper.create_customer()
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_CHECKING_AND_SAVINGS_ACCOUNT_APPLICATION",
            context={"user_id": cust_id},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_tier_savings",
            event_name="account_tier_savings_selected",
            context={
                "account_tier_savings": endtoend.testhandle.flag_definition_id_mapping[
                    "US_SAVINGS_ACCOUNT_TIER_UPPER"
                ]
            },
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_application_preferences_savings",
            event_name="savings_interest_application_day_provided",
            context={"interest_application_day_savings": "9"},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_overdraft_limit",
            event_name="chosen_overdraft_limit",
            context={"chosen_limit": "100"},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_application_preferences_checking",
            event_name="checking_interest_application_day_provided",
            context={"interest_application_day_checking": "2"},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_standard_overdraft_transaction_coverage_preference",
            event_name="standard_overdraft_transaction_coverage_selected",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "accounts_opened_successfully")

        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        us_savings_account_id = workflow_global_context["savings_account_id"]
        us_savings_account = endtoend.contracts_helper.get_account(us_savings_account_id)

        us_checking_account_id = workflow_global_context["checking_account_id"]
        us_checking_account = endtoend.contracts_helper.get_account(us_checking_account_id)

        plan_id = workflow_global_context["plan_id"]
        plan_update_savings = workflow_global_context["plan_update_id_savings"]
        plan_update_checking = workflow_global_context["plan_update_id_checking"]

        endtoend.supervisors_helper.wait_for_plan_updates(
            [plan_update_savings, plan_update_checking]
        )

        endtoend.supervisors_helper.check_plan_associations(
            self, plan_id, [us_savings_account_id, us_checking_account_id]
        )

        # check savings account
        self.assertEqual("ACCOUNT_STATUS_OPEN", us_savings_account["status"])
        flag_status = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping[
                "US_SAVINGS_ACCOUNT_TIER_UPPER"
            ],
            account_ids=[us_savings_account_id],
        )
        self.assertEqual(flag_status[0]["account_id"], us_savings_account_id)

        account_schedules_savings = endtoend.schedule_helper.get_account_schedules(
            us_savings_account_id
        )

        apply_accrue_interest_schedule_time_savings = datetime.strptime(
            account_schedules_savings["APPLY_ACCRUED_INTEREST"]["next_run_timestamp"],
            "%Y-%m-%dT%H:%M:%SZ",
        )
        self.assertEqual(9, apply_accrue_interest_schedule_time_savings.day)

        # check checking account
        self.assertEqual("ACCOUNT_STATUS_OPEN", us_checking_account["status"])

        self.assertEqual(
            "100", us_checking_account["instance_param_vals"]["standard_overdraft_limit"]
        )

        self.assertEqual(
            "2", us_checking_account["instance_param_vals"]["interest_application_day"]
        )

        flag_resources = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping[
                STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG
            ],
            account_ids=[us_checking_account_id],
        )
        self.assertTrue(
            flag_resources, "Check STANDARD_OVERDRAFT_TRANSACTION_COVERAGE flag created"
        )

        # now try to apply for another linked checking and savings account with the same user_id
        # this is should be rejected with the rejection message:
        #  'Cannot create a new plan, customer already has an account on an existing plan'

        wf2_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_CHECKING_AND_SAVINGS_ACCOUNT_APPLICATION",
            context={"user_id": cust_id},
        )
        endtoend.workflows_helper.wait_for_state(wf2_id, "open_linked_accounts_failed")

        workflow2_global_context = endtoend.workflows_helper.get_global_context(wf2_id)
        rejection_message = workflow2_global_context["reject_reason"]

        self.assertEqual(rejection_message, "Customer already has an account on an existing plan")

    def test_workflow_apply_for_savings_and_checking_account_existing_accounts_no_plan(
        self,
    ):
        """
        Test that if a customer has existing checking and savings accounts without a plan
        then the wf still creates 2 new accounts and adds them to a plan
        """
        cust_id = endtoend.core_api_helper.create_customer()
        us_checking_account_no_plan = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account",
            instance_param_vals=ca_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        us_checking_account_id_no_plan = us_checking_account_no_plan["id"]

        savings_instance_params = {"interest_application_day": "1"}
        us_savings_account_no_plan = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id_no_plan = us_savings_account_no_plan["id"]

        customer_accounts = endtoend.core_api_helper.get_customer_accounts(cust_id)
        self.assertEqual(len(customer_accounts), 2)
        customer_account_ids = [customer_accounts[0]["id"], customer_accounts[1]["id"]]
        self.assertNotEqual(customer_account_ids[0], customer_account_ids[1])
        self.assertIn(us_savings_account_id_no_plan, customer_account_ids)
        self.assertIn(us_checking_account_id_no_plan, customer_account_ids)

        # now run the workflow
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_CHECKING_AND_SAVINGS_ACCOUNT_APPLICATION",
            context={"user_id": cust_id},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_tier_savings",
            event_name="account_tier_savings_selected",
            context={
                "account_tier_savings": endtoend.testhandle.flag_definition_id_mapping[
                    "US_SAVINGS_ACCOUNT_TIER_UPPER"
                ]
            },
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_application_preferences_savings",
            event_name="savings_interest_application_day_provided",
            context={"interest_application_day_savings": "9"},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_overdraft_limit",
            event_name="chosen_overdraft_limit",
            context={"chosen_limit": "100"},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_application_preferences_checking",
            event_name="checking_interest_application_day_provided",
            context={"interest_application_day_checking": "1"},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_standard_overdraft_transaction_coverage_preference",
            event_name="standard_overdraft_transaction_coverage_selected",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "accounts_opened_successfully")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        us_savings_account_id = workflow_global_context["savings_account_id"]
        us_checking_account_id = workflow_global_context["checking_account_id"]

        plan_id = workflow_global_context["plan_id"]
        plan_update_savings = workflow_global_context["plan_update_id_savings"]
        plan_update_checking = workflow_global_context["plan_update_id_checking"]

        endtoend.supervisors_helper.wait_for_plan_updates(
            [plan_update_savings, plan_update_checking]
        )
        customer_accounts = endtoend.core_api_helper.get_customer_accounts(cust_id)
        self.assertEqual(len(customer_accounts), 4)
        customer_account_ids = [customer_account["id"] for customer_account in customer_accounts]

        self.assertIn(us_savings_account_id_no_plan, customer_account_ids)
        self.assertIn(us_checking_account_id_no_plan, customer_account_ids)
        self.assertIn(us_savings_account_id, customer_account_ids)
        self.assertIn(us_checking_account_id, customer_account_ids)

        endtoend.supervisors_helper.check_plan_associations(
            self, plan_id, [us_savings_account_id, us_checking_account_id]
        )

    def test_workflow_link_existing_accounts(self):
        """
        Test that the wf behaves as expected when subject to the different
        instantiation scenarios
        """
        cust_1_id = endtoend.core_api_helper.create_customer()
        cust_2_id = endtoend.core_api_helper.create_customer()

        # run the wf before creating any accounts
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_1_id}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_add_account_to_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = "Customer does not have any open accounts"
        self.assertEqual(reject_reason, expected_reject_reason)

        # create checking account for customer 1 and savings account for customer 2
        # run the wf for both customers and ensure it rejects the wf correctly
        us_checking_account_1_cust_1_id = endtoend.contracts_helper.create_account(
            customer=cust_1_id,
            contract="us_checking_account",
            instance_param_vals=ca_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        savings_instance_params = {"interest_application_day": "1"}
        us_savings_account_1_cust_2_id = endtoend.contracts_helper.create_account(
            customer=cust_2_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_1_id}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_add_account_to_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = (
            "Customer does not have the required " "US accounts to create a new plan"
        )
        self.assertEqual(reject_reason, expected_reject_reason)

        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_2_id}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_add_account_to_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = (
            "Customer does not have the required " "US accounts to create a new plan"
        )
        self.assertEqual(reject_reason, expected_reject_reason)

        # now create another us_checking_account for customer 1 and run the wf again
        # this should fail similarly to above since the user can only have
        # 1 checking account on a plan so a new plan cannot be created
        us_checking_account_2_cust_1_id = endtoend.contracts_helper.create_account(
            customer=cust_1_id,
            contract="us_checking_account",
            instance_param_vals=ca_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_1_id}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_add_account_to_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = (
            "Customer does not have the required " "US accounts to create a new plan"
        )
        self.assertEqual(reject_reason, expected_reject_reason)

        # customer_1 has 2 checking accounts and no savings accounts
        # create a savings account for customer 1 and run the wf again
        # a new plan should be created with 1 savings and 1 checking account
        us_savings_account_1_cust_1_id = endtoend.contracts_helper.create_account(
            customer=cust_1_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_1_id}
        )
        # attempt to select 2 checking accounts
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_accounts_to_add_to_new_plan",
            event_name="accounts_selected",
            context={
                "account_id_1": us_checking_account_1_cust_1_id,
                "account_id_2": us_checking_account_2_cust_1_id,
            },
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_message_to_select_again",
            event_name="reselection_accepted",
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_accounts_to_add_to_new_plan",
            event_name="accounts_selected",
            context={
                "account_id_1": us_checking_account_1_cust_1_id,
                "account_id_2": us_savings_account_1_cust_1_id,
            },
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "accounts_added_to_new_plan_successfully")

        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        plan_id = workflow_global_context["plan_id"]
        plan_update_id_2 = workflow_global_context["plan_update_id_2"]
        endtoend.supervisors_helper.wait_for_plan_updates([plan_update_id_2])

        # check the plan is opened correctly
        plan_details = endtoend.supervisors_helper.get_plan_details(plan_id)
        self.assertEqual(plan_details["status"], "PLAN_STATUS_OPEN")

        # now check the accounts are associated to the plan correctly
        endtoend.supervisors_helper.check_plan_associations(
            self,
            plan_id,
            [us_checking_account_1_cust_1_id, us_savings_account_1_cust_1_id],
        )

        # run the wf again for customer_1, this should be rejected because
        # they already have a checking account associated to the plan and
        # all of their open savings accounts are also associated to the plan
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_1_id}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_add_account_to_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = (
            "Customer already has a US checking account associated to"
            " an existing plan and no open US savings accounts available"
            " to be associated to the existing plan"
        )
        self.assertEqual(reject_reason, expected_reject_reason)

        # now create another us_savings account for customer 2 and run the wf again
        # this should create a new plan and associate the 2 savings accounts
        us_savings_account_2_cust_2_id = endtoend.contracts_helper.create_account(
            customer=cust_2_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_2_id}
        )
        # attempt to select the same account
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_accounts_to_add_to_new_plan",
            event_name="accounts_selected",
            context={
                "account_id_1": us_savings_account_1_cust_2_id,
                "account_id_2": us_savings_account_1_cust_2_id,
            },
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_message_to_select_again",
            event_name="reselection_accepted",
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_accounts_to_add_to_new_plan",
            event_name="accounts_selected",
            context={
                "account_id_1": us_savings_account_1_cust_2_id,
                "account_id_2": us_savings_account_2_cust_2_id,
            },
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "accounts_added_to_new_plan_successfully")

        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        plan_id = workflow_global_context["plan_id"]
        plan_update_id_2 = workflow_global_context["plan_update_id_2"]
        endtoend.supervisors_helper.wait_for_plan_updates([plan_update_id_2])

        # now check they are associated to the plan correctly
        endtoend.supervisors_helper.check_plan_associations(
            self,
            plan_id,
            [us_savings_account_1_cust_2_id, us_savings_account_2_cust_2_id],
        )

        # customer 2 has an active plan with 2 savings accounts associated to it
        # and no checking account, if we run the wf again it should be rejected
        # since the customer has no available savings accouts to add to the plan
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_2_id}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_add_account_to_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = (
            "Customer has no open US checking accounts"
            " and no open US savings accounts available"
            " to be associated to the existing plan"
        )
        self.assertEqual(reject_reason, expected_reject_reason)

        # create a checking account and run the wf
        us_checking_account_1_cust_2_id = endtoend.contracts_helper.create_account(
            customer=cust_2_id,
            contract="us_checking_account",
            instance_param_vals=ca_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_2_id}
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_account_to_add_to_existing_plan",
            event_name="account_id_selected",
            context={"account_id_to_add": us_checking_account_1_cust_2_id},
        )
        endtoend.workflows_helper.wait_for_state(
            wf_id, "account_added_to_existing_plan_successfully"
        )

        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        plan_id = workflow_global_context["plan_id"]
        plan_update_id = workflow_global_context["plan_update_id"]
        endtoend.supervisors_helper.wait_for_plan_updates([plan_update_id])

        endtoend.supervisors_helper.check_plan_associations(
            self,
            plan_id,
            [
                us_savings_account_1_cust_2_id,
                us_savings_account_2_cust_2_id,
                us_checking_account_1_cust_2_id,
            ],
        )

        # check the account exlusion list is generated correctly
        # the 2 savings accounts already on the plan should be excluded
        excluded_accounts = loads(workflow_global_context["accounts_to_exclude"])
        self.assertEqual(len(excluded_accounts), 2)
        self.assertIn(us_savings_account_1_cust_2_id, excluded_accounts)
        self.assertIn(us_savings_account_2_cust_2_id, excluded_accounts)

        us_savings_account_3_cust_2_id = endtoend.contracts_helper.create_account(
            customer=cust_2_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]
        us_checking_account_2_cust_2_id = endtoend.contracts_helper.create_account(
            customer=cust_2_id,
            contract="us_checking_account",
            instance_param_vals=ca_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_2_id}
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_account_to_add_to_existing_plan",
            event_name="account_id_selected",
            context={"account_id_to_add": us_savings_account_3_cust_2_id},
        )
        endtoend.workflows_helper.wait_for_state(
            wf_id, "account_added_to_existing_plan_successfully"
        )

        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        plan_id = workflow_global_context["plan_id"]
        plan_update_id = workflow_global_context["plan_update_id"]
        endtoend.supervisors_helper.wait_for_plan_updates([plan_update_id])

        endtoend.supervisors_helper.check_plan_associations(
            self,
            plan_id,
            [
                us_savings_account_1_cust_2_id,
                us_savings_account_2_cust_2_id,
                us_savings_account_3_cust_2_id,
                us_checking_account_1_cust_2_id,
            ],
        )

        # check the account exlusion list is generated correctly
        # both checking accounts should be exluded since the plan has 1 associated checking account
        # the 2 savings accounts already on the plan should also be excluded
        excluded_accounts = loads(workflow_global_context["accounts_to_exclude"])
        self.assertEqual(len(excluded_accounts), 4)
        self.assertIn(us_savings_account_1_cust_2_id, excluded_accounts)
        self.assertIn(us_savings_account_2_cust_2_id, excluded_accounts)
        self.assertIn(us_checking_account_1_cust_2_id, excluded_accounts)
        self.assertIn(us_checking_account_2_cust_2_id, excluded_accounts)

        # run the wf again, it should be rejected since the plan now has 1 checking account
        # and 3 savings accounts associated on it.
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_2_id}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_add_account_to_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = (
            "Customer already has a US checking account associated to an"
            " existing plan and 3 associated US savings accounts to"
            " the existing plan"
        )
        self.assertEqual(reject_reason, expected_reject_reason)

    def test_workflow_link_existing_accounts_invalid_plan_states(self):
        """
        Test that if the customer has an existing plan which is in an invalid state the wf fails
        invalid states: more than 1 checking account or more than 3 savings accounts or
        customer has multiple plans
        """

        cust_1_id = endtoend.core_api_helper.create_customer()

        us_checking_account_1_cust_1_id = endtoend.contracts_helper.create_account(
            customer=cust_1_id,
            contract="us_checking_account",
            instance_param_vals=ca_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]
        us_checking_account_2_cust_1_id = endtoend.contracts_helper.create_account(
            customer=cust_1_id,
            contract="us_checking_account",
            instance_param_vals=ca_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]
        # create a plan and add the 2 checking accounts to it
        endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep",
            [us_checking_account_1_cust_1_id, us_checking_account_2_cust_1_id],
        )
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_1_id}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_add_account_to_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = (
            "Customer appears to have more than 1 checking account associated"
            " to an existing plan"
        )
        self.assertEqual(reject_reason, expected_reject_reason)

        # create another customer with 4 savings accounts on a plan
        cust_2_id = endtoend.core_api_helper.create_customer()

        savings_instance_params = {"interest_application_day": "1"}
        us_savings_account_1_cust_2_id = endtoend.contracts_helper.create_account(
            customer=cust_2_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]
        us_savings_account_2_cust_2_id = endtoend.contracts_helper.create_account(
            customer=cust_2_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]
        us_savings_account_3_cust_2_id = endtoend.contracts_helper.create_account(
            customer=cust_2_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]
        us_savings_account_4_cust_2_id = endtoend.contracts_helper.create_account(
            customer=cust_2_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # create a plan and add the 4 savings accounts to it
        endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep",
            [
                us_savings_account_1_cust_2_id,
                us_savings_account_2_cust_2_id,
                us_savings_account_3_cust_2_id,
                us_savings_account_4_cust_2_id,
            ],
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_2_id}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_add_account_to_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = (
            "Customer appears to have more than 3 savings accounts "
            "associated to an existing plan"
        )
        self.assertEqual(reject_reason, expected_reject_reason)

        # now create a 3rd customer that only has an open checking account
        # which is associated to a plan - ensure the wf rejects the application
        # then create a second plan
        cust_3_id = endtoend.core_api_helper.create_customer()

        us_checking_account_1_cust_3_id = endtoend.contracts_helper.create_account(
            customer=cust_3_id,
            contract="us_checking_account",
            instance_param_vals=ca_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]
        endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep",
            [us_checking_account_1_cust_3_id],
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_3_id}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_add_account_to_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = (
            "Customer already has a US checking account associated to"
            " an existing plan and no open US savings accounts"
        )
        self.assertEqual(reject_reason, expected_reject_reason)

        # now create another us account and create a second plan
        us_savings_account_cust_3_id = endtoend.contracts_helper.create_account(
            customer=cust_3_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # create 2 plans
        endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep", [us_savings_account_cust_3_id]
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_ACCOUNT_ASSOCIATION", context={"user_id": cust_3_id}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_add_account_to_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = "Customer appears to have more than 1 active plan"
        self.assertEqual(reject_reason, expected_reject_reason)

    def test_workflow_close_us_account_two_accounts_on_plan(self):
        """
        Close a US checking account which is associated to a plan
        which has an active savings account associated with it
        """
        cust_id = endtoend.core_api_helper.create_customer()

        checking_instance_params = {
            "fee_free_overdraft_limit": "0",
            "standard_overdraft_limit": "0",
            "interest_application_day": "1",
            "daily_atm_withdrawal_limit": "-1",
        }

        us_checking_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account",
            instance_param_vals=checking_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_checking_account_id = us_checking_account["id"]

        savings_instance_params = {"interest_application_day": "1"}
        us_savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id = us_savings_account["id"]

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep",
            [us_checking_account_id, us_savings_account_id],
        )

        # Close the Checking account
        wf_id = endtoend.workflows_helper.start_workflow(
            "US_PRODUCTS_CLOSURE",
            context={"user_id": cust_id, "account_id": us_checking_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_final_balance",
            event_name="continue_process",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_terms_and_conditions",
            event_name="terms_conditions_accepted",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        plan_id = workflow_global_context["plan_id"]
        plan_update_disassociation = workflow_global_context["plan_disassociation_update_id"]

        endtoend.supervisors_helper.wait_for_plan_updates([plan_update_disassociation])

        closed_checking_account = endtoend.contracts_helper.get_account(us_checking_account_id)
        self.assertTrue(closed_checking_account["status"] == "ACCOUNT_STATUS_CLOSED")

        endtoend.supervisors_helper.check_plan_associations(
            self,
            plan_id,
            {
                us_checking_account_id: "ACCOUNT_PLAN_ASSOC_STATUS_INACTIVE",
                us_savings_account_id: "ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE",
            },
        )

        # check that the plan status remains open
        plan_details = endtoend.supervisors_helper.get_plan_details(plan_id)
        self.assertEqual(plan_details["status"], "PLAN_STATUS_OPEN")

    def test_workflow_disassociate_savings_from_plan(self):
        """
        Test that the workflow fails correctly the following conditions are met:
        customer has no open accounts
        customer has no open savings accounts
        customer has no plan
        Then check that the wf removes a savings account correctly when
        these conditions are not met
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # run the workflow without any customer accounts and check the reject_reason is as expected:
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_SAVINGS_ACCOUNT_DISASSOCIATION",
            context={"user_id": cust_id},
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_remove_account_from_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        actual_reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = "Customer does not have any open accounts"
        self.assertEqual(expected_reject_reason, actual_reject_reason)

        # now create a checking account
        checking_instance_params = {
            "fee_free_overdraft_limit": "0",
            "standard_overdraft_limit": "0",
            "interest_application_day": "1",
            "daily_atm_withdrawal_limit": "-1",
        }

        us_checking_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account",
            instance_param_vals=checking_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # run the workflow again after creating a checking account and
        # check the reject_reason is as expected:
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_SAVINGS_ACCOUNT_DISASSOCIATION",
            context={"user_id": cust_id},
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_remove_account_from_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        actual_reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = "Customer does not have any open savings accounts"
        self.assertEqual(expected_reject_reason, actual_reject_reason)

        # create a savings account
        savings_instance_params = {"interest_application_day": "1"}
        us_savings_account_1_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # run the workflow again and check the reject_reason is as expected:
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_SAVINGS_ACCOUNT_DISASSOCIATION",
            context={"user_id": cust_id},
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_remove_account_from_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        actual_reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = "Customer does not have an existing plan"
        self.assertEqual(expected_reject_reason, actual_reject_reason)

        # create a plan and add the checking account to it
        # the wf should fail since the customer does not have any savings accounts that are
        # associated to an existing plan
        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep", [us_checking_account_id]
        )
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_SAVINGS_ACCOUNT_DISASSOCIATION",
            context={"user_id": cust_id},
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "failure_to_remove_account_from_plan")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        actual_reject_reason = workflow_global_context["reject_reason"]
        expected_reject_reason = (
            "Customer does not have any savings accounts that " "are associated to a plan"
        )
        self.assertEqual(expected_reject_reason, actual_reject_reason)

        # the customer has 1 checking and 1 savings account
        # an active plan with only a checking account associated to it
        # create 2 new savings accounts and add them to the existing plan
        # check that the checking account and the first savings account are
        # present in the account exclusion list
        us_savings_account_2_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        us_savings_account_3_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        endtoend.supervisors_helper.add_account_to_plan(plan_id, us_savings_account_2_id)
        endtoend.supervisors_helper.add_account_to_plan(plan_id, us_savings_account_3_id)

        endtoend.supervisors_helper.check_plan_associations(
            self,
            plan_id,
            [us_checking_account_id, us_savings_account_2_id, us_savings_account_3_id],
        )

        # now run the wf to disassociate one of the savings accounts
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_SAVINGS_ACCOUNT_DISASSOCIATION",
            context={"user_id": cust_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_account_to_remove",
            event_name="account_selected",
            context={"savings_account_id_to_remove": us_savings_account_2_id},
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "account_removed_from_plan_successfully")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        plan_update_id = workflow_global_context["plan_update_id_savings"]
        endtoend.supervisors_helper.wait_for_plan_updates([plan_update_id])

        excluded_accounts = loads(workflow_global_context["accounts_to_exclude"])
        self.assertEqual(len(excluded_accounts), 2)
        self.assertIn(us_checking_account_id, excluded_accounts)
        self.assertIn(us_savings_account_1_id, excluded_accounts)

        endtoend.supervisors_helper.check_plan_associations(
            self,
            plan_id,
            {
                us_checking_account_id: "ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE",
                us_savings_account_2_id: "ACCOUNT_PLAN_ASSOC_STATUS_INACTIVE",
                us_savings_account_3_id: "ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE",
            },
        )

        # ensure plan remains open
        plan_status = endtoend.supervisors_helper.get_plan_details(plan_id)["status"]

        self.assertEqual(plan_status, "PLAN_STATUS_OPEN")

    def test_workflow_disassociate_savings_from_plan_only_account_on_plan(self):
        """
        Test that the workflow succeeds and removes the selected savings account from the plan
        and the plan is then closed if it was the only account on that plan.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        savings_instance_params = {"interest_application_day": "1"}
        us_savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id = us_savings_account["id"]

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep", [us_savings_account_id]
        )

        endtoend.supervisors_helper.check_plan_associations(self, plan_id, [us_savings_account_id])

        # now run the wf to disassociate the savings account
        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_SAVINGS_ACCOUNT_DISASSOCIATION",
            context={"user_id": cust_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_account_to_remove",
            event_name="account_selected",
            context={"savings_account_id_to_remove": us_savings_account_id},
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "account_removed_from_plan_successfully")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        plan_update_id = workflow_global_context["plan_closure_update_id"]
        endtoend.supervisors_helper.wait_for_plan_updates([plan_update_id])

        excluded_accounts = loads(workflow_global_context["accounts_to_exclude"])
        self.assertEqual(len(excluded_accounts), 0)

        endtoend.supervisors_helper.check_plan_associations(
            self, plan_id, {us_savings_account_id: "ACCOUNT_PLAN_ASSOC_STATUS_INACTIVE"}
        )

        plan_status = endtoend.supervisors_helper.get_plan_details(plan_id)["status"]
        self.assertEqual(plan_status, "PLAN_STATUS_CLOSED")

    def test_overdraft_is_incurred_on_checking_account_if_no_savings_account_in_plan(
        self,
    ):

        cust_id = endtoend.core_api_helper.get_existing_test_customer()

        checking_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account",
            instance_param_vals=ca_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        checking_account_id = checking_account["id"]

        endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep", [checking_account_id]
        )

        endtoend.postings_helper.outbound_hard_settlement(
            account_id=checking_account_id,
            amount="1200",
            denomination="USD",
            instruction_details={"description": "Withdrawal from checking account"},
        )

        endtoend.balances_helper.wait_for_account_balances(
            checking_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="USD"), "-1234")],
            description="1200 withdrawn from checking account plus 34 in fees",
            back_off=2,
        )

    def test_opf_fund_transfer_from_savings_account_to_checking_account(self):

        cust_id = endtoend.core_api_helper.get_existing_test_customer()

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

        endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep",
            [checking_account_id, savings_account_id],
        )

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=checking_account_id,
            amount="100",
            denomination="USD",
            instruction_details={"description": "Fund checking account"},
        )
        # Fund savings $1000
        endtoend.postings_helper.inbound_hard_settlement(
            account_id=savings_account_id,
            amount="1000",
            denomination="USD",
            instruction_details={"description": "Fund savings account"},
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                checking_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "100")
                ],
                savings_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "1000")
                ],
            },
            description="100 deposited into checking account and 1000"
            + " deposited into savings account",
        )

        # withdrawal amount within checking balance
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=checking_account_id,
            amount="50",
            denomination="USD",
            instruction_details={"description": "Withdrawal from checking account"},
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                checking_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "50")
                ],
            },
            description="withdrawal amount within checking balance and no transfer from savings",
        )

        # withdrawal amount exceeds checking balance but within savings balance
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=checking_account_id,
            amount="500",
            denomination="USD",
            instruction_details={"description": "Withdrawal savings_sweep"},
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                checking_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "38")
                ],
                savings_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "500")
                ],
            },
            description="450 + 12 fee + 38 transfer unit transferred from savings",
        )

        # withdrawal amount exceeds both checking and savings account balances
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=checking_account_id,
            amount="1700",
            denomination="USD",
            instruction_details={"description": "Withdrawal savings_sweep"},
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                savings_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "0")
                ],
                checking_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "-1208")
                ],
            },
            description="[Savings account] 526 transferred + 12 fee from savings as overdraft "
            + " sweep and [Checking account] -1700 + 526 = -1174 - 34 overdraft fee = -1208",
        )

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=savings_account_id,
            amount="1500",
            denomination="USD",
            instruction_details={"description": "Fund savings account"},
        )

        endtoend.balances_helper.wait_for_account_balances(
            savings_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="USD"), "1500")],
            description="1500 deposited into savings account",
        )

        # withdrawal triggers savings sweep but fee cap reached
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=checking_account_id,
            amount="20",
            denomination="USD",
            instruction_details={"description": "Withdrawal savings_sweep with fee capped"},
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                checking_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "22")
                ],
                savings_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "250")
                ],
            },
            description="[Checking Account]-1208 - 20 balance + 1228 + 22 transfer unit overdraft"
            + " sweep and [Savings account] 1250 transferred into checking account w/o fee",
        )

    def test_savings_sweep_transfer_unit_with_multiple_savings_accounts(self):

        cust_id = endtoend.core_api_helper.get_existing_test_customer()

        checking_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account",
            instance_param_vals=ca_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        checking_account_id = checking_account["id"]

        savings_instance_params = {"interest_application_day": "1"}
        us_savings_account_1 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        savings_account_id_1 = us_savings_account_1["id"]

        us_savings_account_2 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        savings_account_id_2 = us_savings_account_2["id"]

        us_savings_account_3 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        savings_account_id_3 = us_savings_account_3["id"]

        endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep",
            [
                checking_account_id,
                savings_account_id_1,
                savings_account_id_2,
                savings_account_id_3,
            ],
        )

        endtoend.core_api_helper.update_account_instance_parameters(
            checking_account_id,
            instance_param_vals={
                "savings_sweep_account_hierarchy": dumps(
                    [savings_account_id_2, savings_account_id_1, savings_account_id_3]
                ),
                "fee_free_overdraft_limit": "500",
            },
        )
        endtoend.accounts_helper.wait_for_account_update(
            account_id=checking_account_id,
            account_update_type="instance_param_vals_update",
        )

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=checking_account_id,
            amount="100",
            denomination="USD",
            instruction_details={"description": "Fund checking account"},
        )

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=savings_account_id_3,
            amount="1010.50",
            denomination="USD",
            instruction_details={"description": "Fund savings account 3"},
        )

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=savings_account_id_2,
            amount="500",
            denomination="USD",
            instruction_details={"description": "Fund savings account 2"},
        )

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=savings_account_id_1,
            amount="200",
            denomination="USD",
            instruction_details={"description": "Fund savings account 1"},
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                checking_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "100")
                ],
                savings_account_id_1: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "200")
                ],
                savings_account_id_2: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "500")
                ],
                savings_account_id_3: [
                    (
                        BalanceDimensions(address="DEFAULT", denomination="USD"),
                        "1010.50",
                    )
                ],
            },
            description="100 deposited into checking account, 200 deposited into savings account 1,"
            + "  500 deposited into savings account 2 and 1010.50 deposited into savings account 3",
        )

        # withdrawal above checking balance but within savings 2 balance
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=checking_account_id,
            amount="150",
            denomination="USD",
            instruction_details={"description": "Withdrawal from checking account"},
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                checking_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "38")
                ],
                # 500 - (50 + 12 fee + 38 transfer_unit) = 400
                savings_account_id_2: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "400")
                ],
            },
            description="[Checking account] withdrawal amount within checking balance and"
            + " [Savings account 2] 50 + 12 transfer from savings ",
        )

        # withdrawal amount exceeds savings 2 but within savings 1
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=checking_account_id,
            amount="500",
            denomination="USD",
            instruction_details={"description": "Withdrawal savings_sweep"},
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                checking_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "26")
                ],
                # 200 - 100 = 100
                savings_account_id_1: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "100")
                ],
                # total needed to sweep is 500 + 12 fee = 512
                # remaining amount needed to sweep is
                # 512 - 38 checking - 400 savings_account_id_2 = 74
                savings_account_id_2: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "0")
                ],
            },
            description="26 surplus after from savings 1, [Savings Account 1] 100 transferred"
            + " from savings 1 and [Savings Account 2] 400 transferred from savings 2",
        )

        # withdrawal amount exceeds all savings accounts balances
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=checking_account_id,
            amount="1700",
            denomination="USD",
            instruction_details={"description": "Withdrawal savings_sweep"},
        )

        # sweeping total of 1700, with no fee as cap reached
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                checking_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "-608")
                ],
                # remaining sweeping needed
                # 1700 - 26 checking - 100 savings_account_id_1 = 1574
                savings_account_id_1: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "0")
                ],
                # remaining sweeping needed 1574 - 1000 = 574
                savings_account_id_3: [
                    (BalanceDimensions(address="DEFAULT", denomination="USD"), "10.50")
                ],
            },
            description="[Checking account] -1700 + 1126 = -574 - 34 overdraft fee = -608,"
            + " 100 transferred from savings 1 and 1000 transferred from saving 3",
        )

    def test_workflow_manage_savings_sweep_hierarchy(self):
        """
        Test workflow Manage Savings Sweep Hierarchy
        """
        cust_id = endtoend.core_api_helper.create_customer()

        checking_instance_params = {
            "fee_free_overdraft_limit": "500",
            "standard_overdraft_limit": "1000",
            "interest_application_day": "1",
            "daily_atm_withdrawal_limit": "-1",
        }

        us_checking_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account",
            instance_param_vals=checking_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_checking_account_id = us_checking_account["id"]

        savings_instance_params = {"interest_application_day": "1"}
        us_savings_account1 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id1 = us_savings_account1["id"]
        us_savings_account2 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id2 = us_savings_account2["id"]
        us_savings_account3 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id3 = us_savings_account3["id"]
        us_savings_account4 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=savings_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id4 = us_savings_account4["id"]

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep",
            [
                us_checking_account_id,
                us_savings_account_id1,
                us_savings_account_id2,
                us_savings_account_id3,
            ],
        )

        endtoend.supervisors_helper.check_plan_associations(
            self,
            plan_id,
            [
                us_savings_account_id1,
                us_savings_account_id2,
                us_savings_account_id3,
                us_checking_account_id,
            ],
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_HIERARCHY_MANAGEMENT",
            context={"user_id": cust_id, "account_id": us_checking_account_id},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_update_hierarchy_option",
            event_name="enter_new_hierarchy",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "add_account_to_hierarchy")
        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        self.assertIn(
            us_savings_account_id4,
            workflow_global_context["accounts_to_exclude"],
            "Savings account not added to plan is in exclude list",
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_account_to_hierarchy",
            event_name="account_id_selected",
            context={"account_id_to_add": us_savings_account_id1},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_whether_to_add_another_to_hierarchy",
            event_name="add_another_to_hierarchy",
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_account_to_hierarchy",
            event_name="account_id_selected",
            context={"account_id_to_add": us_savings_account_id3},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_whether_to_add_another_to_hierarchy",
            event_name="finish_adding_to_hierarchy",
        )
        endtoend.workflows_helper.send_event(
            wf_id, event_state="confirm_new_hierarchy", event_name="confirm_and_apply"
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "manage_savings_sweep_hierarchy_complete")

        us_checking_account = endtoend.contracts_helper.get_account(us_checking_account_id)
        expected_hierarchy = f'["{us_savings_account_id1}","{us_savings_account_id3}"]'
        self.assertEqual(
            expected_hierarchy,
            us_checking_account["instance_param_vals"]["savings_sweep_account_hierarchy"],
        )

        # now reset the hierarchy and disable savings_sweep
        wf_id2 = endtoend.workflows_helper.start_workflow(
            "SAVINGS_SWEEP_HIERARCHY_MANAGEMENT",
            context={"user_id": cust_id, "account_id": us_checking_account_id},
        )
        endtoend.workflows_helper.send_event(
            wf_id2,
            event_state="select_update_hierarchy_option",
            event_name="reset_and_disable_savings_sweep",
        )
        endtoend.workflows_helper.send_event(
            wf_id2, event_state="confirm_new_hierarchy", event_name="confirm_and_apply"
        )

        endtoend.workflows_helper.wait_for_state(wf_id2, "manage_savings_sweep_hierarchy_complete")

        us_checking_account = endtoend.contracts_helper.get_account(us_checking_account_id)
        expected_hierarchy = "[]"
        self.assertEqual(
            expected_hierarchy,
            us_checking_account["instance_param_vals"]["savings_sweep_account_hierarchy"],
        )

    def test_workflow_close_us_account_only_account_on_plan(self):
        """
        Close a US checking account which is associated to a plan
        and is the only account on that plan
        """
        cust_id = endtoend.core_api_helper.create_customer()

        checking_instance_params = {
            "fee_free_overdraft_limit": "0",
            "standard_overdraft_limit": "0",
            "interest_application_day": "1",
            "daily_atm_withdrawal_limit": "-1",
        }

        us_checking_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account",
            instance_param_vals=checking_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_checking_account_id = us_checking_account["id"]
        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep", [us_checking_account_id]
        )

        # Close the Checking account
        wf_id = endtoend.workflows_helper.start_workflow(
            "US_PRODUCTS_CLOSURE",
            context={"user_id": cust_id, "account_id": us_checking_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_final_balance",
            event_name="continue_process",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_terms_and_conditions",
            event_name="terms_conditions_accepted",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")

        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        plan_id = workflow_global_context["plan_id"]
        plan_update_closure = workflow_global_context["plan_closure_update_id"]

        endtoend.supervisors_helper.wait_for_plan_updates([plan_update_closure])

        closed_checking_account = endtoend.contracts_helper.get_account(us_checking_account_id)
        self.assertTrue(closed_checking_account["status"] == "ACCOUNT_STATUS_CLOSED")

        endtoend.supervisors_helper.check_plan_associations(
            self,
            plan_id,
            {us_checking_account_id: "ACCOUNT_PLAN_ASSOC_STATUS_INACTIVE"},
        )

        # check that the plan status is closed
        plan_details = endtoend.supervisors_helper.get_plan_details(plan_id)
        self.assertEqual(plan_details["status"], "PLAN_STATUS_CLOSED")

    def test_workflow_close_us_account_only_account_on_plan_zero_balance(self):
        """
        Close a US savings account which is associated to a plan
        and is the only account on that plan
        """
        cust_id = endtoend.core_api_helper.create_customer()

        us_savings_instance_params = {"interest_application_day": "6"}

        us_savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=us_savings_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id = us_savings_account["id"]
        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep", [us_savings_account_id]
        )

        # Close the savings account
        wf_id = endtoend.workflows_helper.start_workflow(
            "US_PRODUCTS_CLOSURE",
            context={"user_id": cust_id, "account_id": us_savings_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_final_balance",
            event_name="continue_process",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_terms_and_conditions",
            event_name="terms_conditions_accepted",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")

        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        plan_id = workflow_global_context["plan_id"]
        plan_update_closure = workflow_global_context["plan_closure_update_id"]

        endtoend.supervisors_helper.wait_for_plan_updates([plan_update_closure])

        closed_savings_account = endtoend.contracts_helper.get_account(us_savings_account_id)
        self.assertTrue(closed_savings_account["status"] == "ACCOUNT_STATUS_CLOSED")

        endtoend.supervisors_helper.check_plan_associations(
            self, plan_id, {us_savings_account_id: "ACCOUNT_PLAN_ASSOC_STATUS_INACTIVE"}
        )

        # check that the plan status is closed
        plan_details = endtoend.supervisors_helper.get_plan_details(plan_id)
        self.assertEqual(plan_details["status"], "PLAN_STATUS_CLOSED")

    def test_workflow_close_on_plan_account_with_positive_balance(self):
        """
        Close a US savings account which is associated to a plan
        and is the only account on that plan
        """
        cust_id = endtoend.core_api_helper.create_customer()

        us_savings_instance_params = {"interest_application_day": "6"}

        us_savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account",
            instance_param_vals=us_savings_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id = us_savings_account["id"]

        deposit_posting = endtoend.postings_helper.inbound_hard_settlement(
            account_id=us_savings_account_id, amount="250", denomination="USD"
        )
        pib = endtoend.postings_helper.get_posting_batch(deposit_posting)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            us_savings_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="USD"), "250")],
            description="Savings account balance updated",
        )

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "savings_sweep", [us_savings_account_id]
        )

        # Close the Savings account
        wf_id = endtoend.workflows_helper.start_workflow(
            "US_PRODUCTS_CLOSURE",
            context={"user_id": cust_id, "account_id": us_savings_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_final_balance",
            event_name="continue_process",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_terms_and_conditions",
            event_name="terms_conditions_accepted",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="retrieve_disbursement_account",
            event_name="disbursement_account_given",
            context={"target_account_id": "1"},
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")

        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        plan_id = workflow_global_context["plan_id"]
        plan_update_closure = workflow_global_context["plan_closure_update_id"]

        endtoend.supervisors_helper.wait_for_plan_updates([plan_update_closure])

        closed_savings_account = endtoend.contracts_helper.get_account(us_savings_account_id)
        self.assertTrue(closed_savings_account["status"] == "ACCOUNT_STATUS_CLOSED")

        endtoend.supervisors_helper.check_plan_associations(
            self, plan_id, {us_savings_account_id: "ACCOUNT_PLAN_ASSOC_STATUS_INACTIVE"}
        )

        # check that the plan status is closed
        plan_details = endtoend.supervisors_helper.get_plan_details(plan_id)
        self.assertEqual(plan_details["status"], "PLAN_STATUS_CLOSED")


if __name__ == "__main__":
    endtoend.runtests()
