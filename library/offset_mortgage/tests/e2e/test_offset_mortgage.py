# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from json import loads
from sys import path
from time import time
from typing import List

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.endtoend.helper import COMMON_ACCOUNT_SCHEDULE_TAG_PATH

from library.offset_mortgage.tests.e2e.offset_mortgage_test_params import (
    internal_accounts_tside,
    default_mortgage_instance_params,
    default_mortgage_template_params,
    default_new_mortgage_params_for_offset_mortgage,
    default_eas_template_params,
    default_eas_instance_params,
    default_ca_template_params,
    default_ca_instance_params,
)

path.append(".")

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "mortgage": {
        "path": "library/mortgage/contracts/mortgage.py",
        "template_params": default_mortgage_template_params,
    },
    "easy_access_saver": {
        "path": "library/casa/contracts/casa.py",
        "template_params": default_eas_template_params,
    },
    "current_account": {
        "path": "library/casa/contracts/casa.py",
        "template_params": default_ca_template_params,
    },
}

endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"},
    "interest": {"path": "library/common/contract_modules/interest.py"},
    "amortisation": {"path": "library/common/contract_modules/amortisation.py"},
}

endtoend.testhandle.SUPERVISORCONTRACTS = {
    "offset_mortgage": {"path": "library/offset_mortgage/supervisors/offset_mortgage.py"}
}

endtoend.testhandle.ACCOUNT_SCHEDULE_TAGS = {
    "CASA_ACCRUE_INTEREST_AND_DAILY_FEES_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "CASA_APPLY_ACCRUED_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "CASA_APPLY_ANNUAL_FEES_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "CASA_APPLY_MONTHLY_FEES_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "MORTGAGE_ACCRUE_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "MORTGAGE_REPAYMENT_DAY_SCHEDULE_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "MORTGAGE_HANDLE_OVERPAYMENT_ALLOWANCE_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "MORTGAGE_CHECK_DELINQUENCY_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "OFFSET_MORTGAGE_ACCRUE_OFFSET_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    # Used by CASA
    "ACCOUNT_DORMANT": "library/common/flag_definitions/account_dormant.resource.yaml",
    # Used by CASA_APPLICATION WF
    "CASA_TIER_UPPER": ("library/casa/flag_definitions/casa_tier_upper.resource.yaml"),
    "CASA_TIER_MIDDLE": ("library/casa/flag_definitions/casa_tier_middle.resource.yaml"),
    "CASA_TIER_LOWER": ("library/casa/flag_definitions/casa_tier_lower.resource.yaml"),
}

endtoend.testhandle.WORKFLOWS = {
    # Child workflow used in offset mortgage application/update workflows
    "CASA_APPLICATION": ("library/casa/workflows/casa_application.yaml"),
    "OFFSET_MORTGAGE_APPLICATION": (
        "library/offset_mortgage/workflows/offset_mortgage_application.yaml"
    ),
    "OFFSET_MORTGAGE_CLOSURE": ("library/offset_mortgage/workflows/offset_mortgage_closure.yaml"),
    "OFFSET_MORTGAGE_UPDATE": ("library/offset_mortgage/workflows/offset_mortgage_update.yaml"),
    "MORTGAGE_SWITCH": "library/mortgage/workflows/mortgage_switch.yaml",
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    # Used by CASA
    "ACCOUNT_DORMANT": "library/common/flag_definitions/account_dormant.resource.yaml",
    # Used by CASA_APPLICATION WF
    "CASA_TIER_UPPER": ("library/casa/flag_definitions/casa_tier_upper.resource.yaml"),
    "CASA_TIER_MIDDLE": ("library/casa/flag_definitions/casa_tier_middle.resource.yaml"),
    "CASA_TIER_LOWER": ("library/casa/flag_definitions/casa_tier_lower.resource.yaml"),
}


class OffsetMortgageTest(endtoend.End2Endtest):
    def setUp(self):
        self._started_at = time()

    def tearDown(self):
        self._elapsed_time = time() - self._started_at

    def check_accounts_linked_via_workflow(self, wf_id: str, account_ids: List[str]):
        """
        Helper method to validate that expected accounts are linked based on an offset
        mortgage workflow
        :param wf_id: the workflow id. If not specified,
        :param account_ids: the list of account ids to validate on top of what was
        created via the workflow. For example, an account id may have been created outside
        but linked via the workflow, or created outside and linked outside of the workflow
        """

        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        plan_id = workflow_global_context["plan_id"]

        plan_update_ids = loads(workflow_global_context["plan_update_id_eas_ca_list"])
        # mortgage is only present if created via the application workflow
        if "plan_update_id_mortgage" in workflow_global_context:
            plan_update_ids.append(workflow_global_context["plan_update_id_mortgage"])

        endtoend.supervisors_helper.wait_for_plan_updates(plan_update_ids)

        account_ids.append(workflow_global_context["mortgage_account_id"])
        endtoend.supervisors_helper.check_plan_associations(self, plan_id, account_ids)

    def test_offset_mortgage_creation(self):
        cust_id = endtoend.core_api_helper.get_existing_test_customer()
        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=default_mortgage_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        mortgage_account_id = mortgage_account["id"]

        eas_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=default_eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        eas_account_id = eas_account["id"]

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "offset_mortgage", [mortgage_account_id, eas_account_id]
        )

        endtoend.supervisors_helper.check_plan_associations(
            self, plan_id, [mortgage_account_id, eas_account_id]
        )

    def test_workflow_offset_mortage_application_opening_new_mortgage(self):
        """
        Test applying for an offset mortgage by opening a new mortgage.
        """
        cust_id = endtoend.core_api_helper.create_customer()
        mortgage_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["mortgage"]
        eas_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["easy_access_saver"]
        # Easy access saver creation
        eas_1_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=default_eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        eas_1_account_id = eas_1_account["id"]

        # Fund savings accounts
        endtoend.postings_helper.inbound_hard_settlement(
            account_id=eas_1_account_id,
            amount="30000",
            denomination="GBP",
            instruction_details={"description": "Fund savings account 1"},
        )

        # Wait for account balances
        endtoend.balances_helper.wait_for_account_balances(
            eas_1_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="GBP"), "30000")],
            description="EAS account funded with 30 000",
        )

        # Start workflow to apply for offset mortgage with existing accounts
        wf_id = endtoend.workflows_helper.start_workflow(
            "OFFSET_MORTGAGE_APPLICATION",
            context={
                "user_id": cust_id,
                "mortgage_product_id": mortgage_product_id,
                "eas_product_id": eas_product_id,
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_create_new_or_existing_mortgage")

        # Choose new mortgage
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_create_new_or_existing_mortgage",
            event_name="create_new_mortgage_selected",
            context={},
        )

        creation_date = datetime.strptime(
            eas_1_account["opening_timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        new_mortgage_params_for_offset_mortgage = (
            default_new_mortgage_params_for_offset_mortgage.copy()
        )
        new_mortgage_params_for_offset_mortgage["new_mortgage_start_date"] = str(creation_date)
        # Populate account param and submit with default values
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="new_mortgage_select_parameters",
            event_name="new_mortgage_parameters_selected",
            context=new_mortgage_params_for_offset_mortgage,
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_or_create_accounts_for_offset")

        # Choose new eas or current account
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_or_create_accounts_for_offset",
            event_name="select_existing_eas_or_ca",
            context={},
        )

        # Select EAS 1
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_eas_or_ca_account",
            event_name="eas_or_ca_selected",
            context={"eas_or_ca_id": str(eas_1_account_id)},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_more_accounts_to_offset_list",
            event_name="proceed_to_next",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "open_offset_mortgage_successful")

        self.check_accounts_linked_via_workflow(wf_id, [eas_1_account_id])

    def test_workflow_offset_mortage_application_selecting_existing_mortgage_outside_int_only_term(
        self,
    ):
        """
        Test applying for an offset mortgage outside interest only term.
        """
        cust_id = endtoend.core_api_helper.create_customer()
        mortgage_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["mortgage"]
        eas_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["easy_access_saver"]

        # Mortgage account creation
        mortgage_1_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=default_mortgage_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        mortgage_1_account_id = mortgage_1_account["id"]

        mortgage_2_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=default_mortgage_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        mortgage_2_account_id = mortgage_2_account["id"]

        # Easy access saver creation
        eas_1_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=default_eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        eas_1_account_id = eas_1_account["id"]

        eas_2_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=default_eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        eas_2_account_id = eas_2_account["id"]

        # Wait for mortgage balances
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                mortgage_1_account_id: [
                    (
                        BalanceDimensions(address="PRINCIPAL", denomination="GBP"),
                        "300000",
                    )
                ],
                mortgage_2_account_id: [
                    (
                        BalanceDimensions(address="PRINCIPAL", denomination="GBP"),
                        "300000",
                    )
                ],
            },
            description="300 000 GBP moved to PRINCIPAL balance of the mortgage",
        )

        # Fund savings accounts
        endtoend.postings_helper.inbound_hard_settlement(
            account_id=eas_1_account_id,
            amount="30000",
            denomination="GBP",
            instruction_details={"description": "Fund savings account 1"},
        )

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=eas_2_account_id,
            amount="50000",
            denomination="GBP",
            instruction_details={"description": "Fund savings account 2"},
        )

        # Wait for account balances
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                eas_1_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="GBP"), "30000")
                ],
                eas_2_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="GBP"), "50000")
                ],
            },
            description="EAS account 1 funded with 30 000 and EAS account 2 funded with 50 000",
        )

        # Start workflow to apply for offset mortgage with existing accounts
        wf_id = endtoend.workflows_helper.start_workflow(
            "OFFSET_MORTGAGE_APPLICATION",
            context={
                "user_id": cust_id,
                "mortgage_product_id": mortgage_product_id,
                "eas_product_id": eas_product_id,
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_create_new_or_existing_mortgage")

        # Choose existing mortgage
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_create_new_or_existing_mortgage",
            event_name="existing_mortgage_selected",
            context={},
        )

        # Select Mortgage 2
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_existing_mortgage",
            event_name="mortgage_account_selected",
            context={"mortgage_account_id": str(mortgage_2_account_id)},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_or_create_accounts_for_offset")

        # Choose new eas or current account
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_or_create_accounts_for_offset",
            event_name="select_existing_eas_or_ca",
            context={},
        )

        # Select EAS 1
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_eas_or_ca_account",
            event_name="eas_or_ca_selected",
            context={"eas_or_ca_id": str(eas_1_account_id)},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_more_accounts_to_offset_list",
            event_name="proceed_to_next",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "open_offset_mortgage_successful")

        self.check_accounts_linked_via_workflow(wf_id, [mortgage_2_account_id, eas_1_account_id])

    def test_workflow_offset_mortage_application_selecting_existing_mortgage_within_int_only_term(
        self,
    ):
        """
        Test applying for an offset mortgage within interest only term.
        """
        cust_id = endtoend.core_api_helper.create_customer()
        mortgage_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["mortgage"]
        eas_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["easy_access_saver"]
        mortgage_instance_params = default_mortgage_instance_params.copy()
        mortgage_instance_params["interest_only_term"] = "1"
        # Mortgage account creation
        mortgage_1_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=mortgage_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        mortgage_1_account_id = mortgage_1_account["id"]

        mortgage_2_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=mortgage_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        mortgage_2_account_id = mortgage_2_account["id"]

        # Easy access saver creation
        eas_1_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=default_eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        eas_1_account_id = eas_1_account["id"]

        eas_2_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=default_eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        eas_2_account_id = eas_2_account["id"]

        # Wait for mortgage balances
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                mortgage_1_account_id: [
                    (
                        BalanceDimensions(address="PRINCIPAL", denomination="GBP"),
                        "300000",
                    )
                ],
                mortgage_2_account_id: [
                    (
                        BalanceDimensions(address="PRINCIPAL", denomination="GBP"),
                        "300000",
                    )
                ],
            },
            description="300 000 GBP moved to PRINCIPAL balance of the mortgage",
        )

        # Fund savings accounts
        endtoend.postings_helper.inbound_hard_settlement(
            account_id=eas_1_account_id,
            amount="30000",
            denomination="GBP",
            instruction_details={"description": "Fund savings account 1"},
        )

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=eas_2_account_id,
            amount="50000",
            denomination="GBP",
            instruction_details={"description": "Fund savings account 2"},
        )

        # Wait for account balances
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                eas_1_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="GBP"), "30000")
                ],
                eas_2_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="GBP"), "50000")
                ],
            },
            description="EAS account 1 funded with 30 000 and EAS account 2 funded with 50 000",
        )

        # Start workflow to apply for offset mortgage with existing accounts
        wf_id = endtoend.workflows_helper.start_workflow(
            "OFFSET_MORTGAGE_APPLICATION",
            context={
                "user_id": cust_id,
                "mortgage_product_id": mortgage_product_id,
                "eas_product_id": eas_product_id,
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_create_new_or_existing_mortgage")

        # Choose existing mortgage
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_create_new_or_existing_mortgage",
            event_name="existing_mortgage_selected",
            context={},
        )

        # Select Mortgage 2
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_existing_mortgage",
            event_name="mortgage_account_selected",
            context={"mortgage_account_id": str(mortgage_2_account_id)},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "open_offset_mortgage_failed")

        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        error_message = workflow_global_context["error_message"]
        self.assertEqual(
            error_message,
            "Existing mortgage account which is currently in interest only term cannot be used.",
        )

    def test_workflow_offset_mortage_closure(self):
        """
        Test closing an offset mortgage.
        """
        cust_id = endtoend.core_api_helper.create_customer()
        mortgage_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["mortgage"]

        # create mortgage accounts
        mortgage_1_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=default_mortgage_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        mortgage_1_account_id = mortgage_1_account["id"]

        mortgage_2_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=default_mortgage_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        mortgage_2_account_id = mortgage_2_account["id"]

        # create easy access saver accounts
        eas_1_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=default_eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        eas_1_account_id = eas_1_account["id"]

        eas_2_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=default_eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        eas_2_account_id = eas_2_account["id"]

        # wait for mortgage balances
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                mortgage_1_account_id: [
                    (
                        BalanceDimensions(address="PRINCIPAL", denomination="GBP"),
                        "300000",
                    )
                ],
                mortgage_2_account_id: [
                    (
                        BalanceDimensions(address="PRINCIPAL", denomination="GBP"),
                        "300000",
                    )
                ],
            },
            description="300 000 GBP moved to PRINCIPAL balance of the mortgage",
        )

        # fund savings accounts
        endtoend.postings_helper.inbound_hard_settlement(
            account_id=eas_1_account_id,
            amount="30000",
            denomination="GBP",
            instruction_details={"description": "Fund savings account 1"},
        )

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=eas_2_account_id,
            amount="50000",
            denomination="GBP",
            instruction_details={"description": "Fund savings account 2"},
        )

        # wait for account balances
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                eas_1_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="GBP"), "30000")
                ],
                eas_2_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="GBP"), "50000")
                ],
            },
            description="EAS account 1 funded with 30,000 and EAS account 2 funded with 50,000",
        )

        # create supervisor contract
        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "offset_mortgage", [mortgage_1_account_id, eas_1_account_id]
        )

        # start workflow to close an offset mortgage
        wf_id = endtoend.workflows_helper.start_workflow(
            "OFFSET_MORTGAGE_CLOSURE",
            context={"user_id": cust_id, "mortgage_product_id": mortgage_product_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_mortgage")

        # select mortgage 1
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_mortgage",
            event_name="mortgage_account_selected",
            context={"mortgage_account_id": str(mortgage_1_account_id)},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "close_offset_mortgage_successful")

        workflow_global_context = endtoend.workflows_helper.get_global_context(wf_id)
        plan_closure_update_id = workflow_global_context["plan_closure_update_id"]
        endtoend.supervisors_helper.wait_for_plan_updates([plan_closure_update_id])

        endtoend.supervisors_helper.check_plan_associations(
            self,
            plan_id,
            {
                mortgage_1_account_id: "ACCOUNT_PLAN_ASSOC_STATUS_INACTIVE",
                eas_1_account_id: "ACCOUNT_PLAN_ASSOC_STATUS_INACTIVE",
            },
        )

    def test_workflow_offset_mortage_update_link_existing_accounts(self):
        """
        Test update_offset_mortgage workflow to link more existing
        easy access saver  and current account to an existing offset mortgage
        """
        cust_id = endtoend.core_api_helper.create_customer()
        mortgage_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["mortgage"]
        eas_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["easy_access_saver"]
        ca_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["current_account"]

        # Open a current account
        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=default_ca_instance_params,
            permitted_denominations=["GBP", "EUR", "USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        current_account_id = account["id"]

        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=default_mortgage_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        mortgage_account_id = mortgage_account["id"]

        eas_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=default_eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        eas_account_id = eas_account["id"]

        eas_account2 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=default_eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        eas_2_account_id = eas_account2["id"]

        endtoend.supervisors_helper.link_accounts_to_supervisor(
            "offset_mortgage", [mortgage_account_id, eas_account_id]
        )

        # Start workflow to update offset mortgage to add accounts
        wf_id = endtoend.workflows_helper.start_workflow(
            "OFFSET_MORTGAGE_UPDATE",
            context={
                "user_id": cust_id,
                "mortgage_product_id": mortgage_product_id,
                "eas_product_id": eas_product_id,
                "ca_product_id": ca_product_id,
            },
        )

        # select a mortgage
        endtoend.workflows_helper.wait_for_state(wf_id, "select_existing_mortgage")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_existing_mortgage",
            event_name="mortgage_account_selected",
            context={"mortgage_account_id": str(mortgage_account_id)},
        )

        # select to add an existing eas or ca
        endtoend.workflows_helper.wait_for_state(wf_id, "select_or_create_accounts_for_offset")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_or_create_accounts_for_offset",
            event_name="select_existing_eas_or_ca",
            context={},
        )

        # select an eas
        endtoend.workflows_helper.wait_for_state(wf_id, "select_valid_account_to_link")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_valid_account_to_link",
            event_name="eas_or_ca_selected",
            context={"eas_or_ca_id": str(eas_2_account_id)},
        )
        # proceed to add more account
        endtoend.workflows_helper.wait_for_state(wf_id, "add_more_accounts_to_offset_list")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_more_accounts_to_offset_list",
            event_name="selected_additional_eas_or_ca",
            context={},
        )

        # select to add an existing eas or ca
        endtoend.workflows_helper.wait_for_state(wf_id, "select_or_create_accounts_for_offset")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_or_create_accounts_for_offset",
            event_name="select_existing_eas_or_ca",
            context={},
        )

        # select a ca
        endtoend.workflows_helper.wait_for_state(wf_id, "select_valid_account_to_link")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_valid_account_to_link",
            event_name="eas_or_ca_selected",
            context={"eas_or_ca_id": str(current_account_id)},
        )

        # proceed to add acct to plan
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_more_accounts_to_offset_list",
            event_name="proceed_to_next",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "update_offset_mortgage_successful")

        self.check_accounts_linked_via_workflow(
            wf_id, [eas_account_id, eas_2_account_id, current_account_id]
        )

    def test_workflow_offset_mortage_update_link_new_accounts(self):
        """
        Test updating for an offset mortgage with new EAS and new Current accounts
        """
        cust_id = endtoend.core_api_helper.create_customer()
        mortgage_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["mortgage"]
        eas_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["easy_access_saver"]
        ca_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["current_account"]

        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=default_mortgage_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        mortgage_account_id = mortgage_account["id"]

        eas_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=default_eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        eas_account_id = eas_account["id"]

        endtoend.supervisors_helper.link_accounts_to_supervisor(
            "offset_mortgage", [mortgage_account_id, eas_account_id]
        )

        # Start workflow to update offset mortgage to add accounts
        wf_id = endtoend.workflows_helper.start_workflow(
            "OFFSET_MORTGAGE_UPDATE",
            context={
                "user_id": cust_id,
                "mortgage_product_id": mortgage_product_id,
                "eas_product_id": eas_product_id,
                "ca_product_id": ca_product_id,
            },
        )

        # select a mortgage
        endtoend.workflows_helper.wait_for_state(wf_id, "select_existing_mortgage")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_existing_mortgage",
            event_name="mortgage_account_selected",
            context={"mortgage_account_id": str(mortgage_account_id)},
        )

        # select to add an existing eas or ca
        endtoend.workflows_helper.wait_for_state(wf_id, "select_or_create_accounts_for_offset")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_or_create_accounts_for_offset",
            event_name="create_new_eas_selected",
            context={},
        )

        cwf_id = endtoend.workflows_helper.get_child_workflow_id(wf_id, "new_eas_account")

        endtoend.workflows_helper.send_event(
            cwf_id,
            event_state="select_product_id",
            event_name="product_id_selected",
            context={"product_id": eas_product_id},
        )

        endtoend.workflows_helper.send_event(
            cwf_id,
            event_state="capture_account_tier",
            event_name="account_tier_selected",
            context={
                "account_tier": endtoend.testhandle.flag_definition_id_mapping["CASA_TIER_UPPER"]
            },
        )

        endtoend.workflows_helper.send_event(
            cwf_id,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "1"},
        )

        endtoend.workflows_helper.wait_for_state(cwf_id, "account_opened_successfully")
        eas_2_account_id = endtoend.workflows_helper.get_global_context(cwf_id)["account_id"]

        # proceed to add more accounts
        endtoend.workflows_helper.wait_for_state(wf_id, "add_more_accounts_to_offset_list")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_more_accounts_to_offset_list",
            event_name="selected_additional_eas_or_ca",
            context={},
        )

        # select to add an existing eas or ca
        endtoend.workflows_helper.wait_for_state(wf_id, "select_or_create_accounts_for_offset")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_or_create_accounts_for_offset",
            event_name="create_new_current_selected",
            context={},
        )

        # create current account
        cwf_id2 = endtoend.workflows_helper.get_child_workflow_id(
            wf_id, "new_current_account", existing_instantiated_child_workflows=[cwf_id]
        )

        endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="select_product_id",
            event_name="product_id_selected",
            context={"product_id": ca_product_id},
        )
        endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="capture_account_tier",
            event_name="account_tier_selected",
            context={
                "account_tier": endtoend.testhandle.flag_definition_id_mapping["CASA_TIER_UPPER"]
            },
        )

        endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="choose_daily_atm_limit",
            event_name="chosen_daily_atm_limit",
            context={"chosen_daily_atm_limit": "200"},
        )

        state_id = endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="choose_unarranged_overdraft_limit",
            event_name="chosen_overdraft_limit",
            context={"chosen_unarranged_overdraft_limit": "9000"},
        )

        endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="choose_arranged_overdraft_limit",
            event_name="chosen_arranged_overdraft_limit",
            context={"chosen_arranged_overdraft_limit": "100"},
            current_state_id=state_id,
        )

        endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="capture_autosave_preferences",
            event_name="proceed",
            context={"autosave_account_id": str(eas_2_account_id)},
        )

        endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "1"},
        )

        endtoend.workflows_helper.wait_for_state(cwf_id2, "account_opened_successfully")
        current_account_id = endtoend.workflows_helper.get_global_context(cwf_id2)["account_id"]

        # proceed to add acct to plan
        endtoend.workflows_helper.wait_for_state(wf_id, "add_more_accounts_to_offset_list")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_more_accounts_to_offset_list",
            event_name="proceed_to_next",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "update_offset_mortgage_successful")

        self.check_accounts_linked_via_workflow(
            wf_id,
            [current_account_id, eas_account_id, eas_2_account_id, mortgage_account_id],
        )

    def test_switch_var_offset_to_fix_offset_mortgage(self):
        cust_id = endtoend.core_api_helper.get_existing_test_customer()

        # Create variable mortgage
        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=default_mortgage_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        mortgage_account_id = mortgage_account["id"]

        # check mortgage account
        self.assertEqual("ACCOUNT_STATUS_OPEN", mortgage_account["status"])
        self.assertEqual(
            mortgage_account["instance_param_vals"]["principal"],
            default_mortgage_instance_params["principal"],
        )

        # Create EAS
        eas_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=default_eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        eas_account_id = eas_account["id"]

        # check eas account
        self.assertEqual("ACCOUNT_STATUS_OPEN", eas_account["status"])
        self.assertEqual(
            eas_account["instance_param_vals"]["interest_application_day"],
            default_eas_instance_params["interest_application_day"],
        )

        # Linking accounts
        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "offset_mortgage", [mortgage_account_id, eas_account_id]
        )

        # Switch mortgage to fixed rate
        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_SWITCH", context={"account_id": mortgage_account["id"]}
        )

        expected_dict = {
            "fixed_interest_rate": ".10",
            "fixed_interest_term": "15",
            "variable_rate_adjustment": "0",
            "interest_only_term": "0",
            "total_term": "15",
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
        # Check that fixed rate change was successful
        self.assertDictEqual(expected_dict, current_dict)
        self.assertEqual(datetime.utcnow().strftime("%Y-%m-%d"), mortgage_start_date)
        endtoend.balances_helper.wait_for_account_balances(
            mortgage_account["id"],
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="PRINCIPAL", denomination="GBP"
                    ),
                    "300000",
                )
            ],
        )
        # Check if link is still there after switching to fixed rate.
        endtoend.supervisors_helper.check_plan_associations(
            self, plan_id, [mortgage_account_id, eas_account_id]
        )

    def test_workflow_offset_mortage_application_opening_new_mortgage_new_accounts_for_offset(
        self,
    ):
        """
        Test applying for an offset mortgage by opening a new mortgage
        and new EAS and Current account.
        """
        cust_id = endtoend.core_api_helper.create_customer()
        mortgage_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["mortgage"]
        eas_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["easy_access_saver"]
        ca_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["current_account"]

        # Start workflow to apply for offset mortgage with existing accounts
        wf_id = endtoend.workflows_helper.start_workflow(
            "OFFSET_MORTGAGE_APPLICATION",
            context={
                "user_id": cust_id,
                "mortgage_product_id": mortgage_product_id,
                "eas_product_id": eas_product_id,
                "ca_product_id": ca_product_id,
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_create_new_or_existing_mortgage")

        # Choose new mortgage
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_create_new_or_existing_mortgage",
            event_name="create_new_mortgage_selected",
            context={},
        )

        # Populate account param and submit with default values
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="new_mortgage_select_parameters",
            event_name="new_mortgage_parameters_selected",
            context=default_new_mortgage_params_for_offset_mortgage,
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_or_create_accounts_for_offset")

        # Choose new eas or current account
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_or_create_accounts_for_offset",
            event_name="create_new_eas_selected",
            context={},
        )

        cwf_id = endtoend.workflows_helper.get_child_workflow_id(wf_id, "new_eas_account")

        endtoend.workflows_helper.send_event(
            cwf_id,
            event_state="select_product_id",
            event_name="product_id_selected",
            context={"product_id": eas_product_id},
        )

        endtoend.workflows_helper.send_event(
            cwf_id,
            event_state="capture_account_tier",
            event_name="account_tier_selected",
            context={
                "account_tier": endtoend.testhandle.flag_definition_id_mapping["CASA_TIER_UPPER"]
            },
        )

        endtoend.workflows_helper.send_event(
            cwf_id,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "1"},
        )

        endtoend.workflows_helper.wait_for_state(cwf_id, "account_opened_successfully")
        eas_1_account_id = endtoend.workflows_helper.get_global_context(cwf_id)["account_id"]

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_more_accounts_to_offset_list",
            event_name="selected_additional_eas_or_ca",
            context={},
        )

        # select to add an existing eas or ca
        endtoend.workflows_helper.wait_for_state(wf_id, "select_or_create_accounts_for_offset")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_or_create_accounts_for_offset",
            event_name="create_new_ca_selected",
            context={},
        )

        # create current account
        cwf_id2 = endtoend.workflows_helper.get_child_workflow_id(
            wf_id, "new_current_account", existing_instantiated_child_workflows=[cwf_id]
        )

        endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="select_product_id",
            event_name="product_id_selected",
            context={"product_id": ca_product_id},
        )

        endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="capture_account_tier",
            event_name="account_tier_selected",
            context={
                "account_tier": endtoend.testhandle.flag_definition_id_mapping["CASA_TIER_UPPER"]
            },
        )

        endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="choose_daily_atm_limit",
            event_name="chosen_daily_atm_limit",
            context={"chosen_daily_atm_limit": "200"},
        )

        state_id = endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="choose_unarranged_overdraft_limit",
            event_name="chosen_overdraft_limit",
            context={"chosen_unarranged_overdraft_limit": "9000"},
        )

        endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="choose_arranged_overdraft_limit",
            event_name="chosen_arranged_overdraft_limit",
            context={"chosen_arranged_overdraft_limit": "100"},
            current_state_id=state_id,
        )

        endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="capture_autosave_preferences",
            event_name="proceed",
            context={"autosave_account_id": str(eas_1_account_id)},
        )

        endtoend.workflows_helper.send_event(
            cwf_id2,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "1"},
        )

        endtoend.workflows_helper.wait_for_state(cwf_id2, "account_opened_successfully")
        current_account_id = endtoend.workflows_helper.get_global_context(cwf_id2)["account_id"]

        # proceed to add acct to plan
        endtoend.workflows_helper.wait_for_state(wf_id, "add_more_accounts_to_offset_list")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_more_accounts_to_offset_list",
            event_name="proceed_to_next",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "open_offset_mortgage_successful")

        self.check_accounts_linked_via_workflow(wf_id, [current_account_id, eas_1_account_id])

    def test_workflow_offset_mortage_application_opening_new_mortgage_multiple_accounts_for_offset(
        self,
    ):
        """
        Test applying for an offset mortgage by opening a new mortgage with multiple accounts.
        """
        cust_id = endtoend.core_api_helper.create_customer()
        mortgage_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["mortgage"]
        eas_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["easy_access_saver"]
        ca_product_id = endtoend.testhandle.contract_pid_to_uploaded_pid["current_account"]

        # Easy access saver creation
        eas_1_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=default_eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        eas_1_account_id = eas_1_account["id"]

        # Fund savings accounts
        endtoend.postings_helper.inbound_hard_settlement(
            account_id=eas_1_account_id,
            amount="30000",
            denomination="GBP",
            instruction_details={"description": "Fund savings account 1"},
        )

        # Wait for account balances
        endtoend.balances_helper.wait_for_account_balances(
            eas_1_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="GBP"), "30000")],
            description="EAS account funded with 30 000",
        )

        # Current account creation
        ca_1_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=default_ca_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        ca_1_account_id = ca_1_account["id"]

        # Fund current account
        endtoend.postings_helper.inbound_hard_settlement(
            account_id=ca_1_account_id,
            amount="40000",
            denomination="GBP",
            instruction_details={"description": "Fund current account 1"},
        )

        # Wait for account balances
        endtoend.balances_helper.wait_for_account_balances(
            ca_1_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="GBP"), "40000")],
            description="CA account funded with 40 000",
        )

        # Start workflow to apply for offset mortgage with existing accounts
        wf_id = endtoend.workflows_helper.start_workflow(
            "OFFSET_MORTGAGE_APPLICATION",
            context={
                "user_id": cust_id,
                "mortgage_product_id": mortgage_product_id,
                "eas_product_id": eas_product_id,
                "ca_product_id": ca_product_id,
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_create_new_or_existing_mortgage")

        # Choose new mortgage
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_create_new_or_existing_mortgage",
            event_name="create_new_mortgage_selected",
            context={},
        )

        creation_date = datetime.strptime(
            eas_1_account["opening_timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        new_mortgage_params_for_offset_mortgage = (
            default_new_mortgage_params_for_offset_mortgage.copy()
        )
        new_mortgage_params_for_offset_mortgage["new_mortgage_start_date"] = str(creation_date)
        # Populate account param and submit with default values
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="new_mortgage_select_parameters",
            event_name="new_mortgage_parameters_selected",
            context=new_mortgage_params_for_offset_mortgage,
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_or_create_accounts_for_offset")

        # Select EAS 1

        # Choose new eas or current account
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_or_create_accounts_for_offset",
            event_name="select_existing_eas_or_ca",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_eas_or_ca_account",
            event_name="eas_or_ca_selected",
            context={"eas_or_ca_id": str(eas_1_account_id)},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_more_accounts_to_offset_list",
            event_name="selected_additional_eas_or_ca",
            context={},
        )

        # Select CA 1

        # Choose new eas or current account
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_or_create_accounts_for_offset",
            event_name="select_existing_eas_or_ca",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_eas_or_ca_account",
            event_name="eas_or_ca_selected",
            context={"eas_or_ca_id": str(ca_1_account_id)},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_more_accounts_to_offset_list",
            event_name="selected_additional_eas_or_ca",
            context={},
        )

        # Choose new eas or current account
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_or_create_accounts_for_offset",
            event_name="create_new_eas_selected",
            context={},
        )

        cwf_id = endtoend.workflows_helper.get_child_workflow_id(wf_id, "new_eas_account")

        endtoend.workflows_helper.send_event(
            cwf_id,
            event_state="select_product_id",
            event_name="product_id_selected",
            context={"product_id": eas_product_id},
        )

        endtoend.workflows_helper.send_event(
            cwf_id,
            event_state="capture_account_tier",
            event_name="account_tier_selected",
            context={
                "account_tier": endtoend.testhandle.flag_definition_id_mapping["CASA_TIER_UPPER"]
            },
        )

        endtoend.workflows_helper.send_event(
            cwf_id,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "1"},
        )

        endtoend.workflows_helper.wait_for_state(cwf_id, "account_opened_successfully")

        eas_2_account_id = endtoend.workflows_helper.get_global_context(cwf_id)["account_id"]

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_more_accounts_to_offset_list",
            event_name="proceed_to_next",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "open_offset_mortgage_successful")

        self.check_accounts_linked_via_workflow(
            wf_id, [eas_1_account_id, eas_2_account_id, ca_1_account_id]
        )


if __name__ == "__main__":
    endtoend.runtests()
