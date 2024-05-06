# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta

# library
import library.us_products_v3.constants.files as files
from library.us_products_v3.test.e2e.us_products_test_params import (
    APPLICATION_WORKFLOW_FLAG_DEFINITIONS,
    DEFAULT_CHECKING_CONTRACT,
    STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG,
    US_CHECKING_FLAG_DEFINITIONS,
    checking_account_instance_params,
    checking_account_template_params,
    checking_account_template_params_for_close,
    internal_accounts_tside,
)

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions
from inception_sdk.vault.postings.posting_classes import (
    InboundHardSettlement,
    OutboundHardSettlement,
    PostingInstruction,
)
from inception_sdk.vault.postings.postings_helper import create_pib_from_posting_instructions

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    **DEFAULT_CHECKING_CONTRACT,
    "us_checking_account_for_close": {
        "path": files.US_CHECKING_TEMPLATE,
        "template_params": checking_account_template_params_for_close,
    },
    "dummy_account": {"path": DUMMY_CONTRACT},
}
endtoend.testhandle.CONTRACT_MODULES = {
    "interest": {"path": "library/common/contract_modules/interest.py"},
    "utils": {"path": "library/common/contract_modules/utils.py"},
}

endtoend.testhandle.WORKFLOWS = {
    "US_CHECKING_ACCOUNT_APPLICATION": (
        "library/us_products_v3/workflows/us_checking_account_application.yaml"
    ),
    "US_PRODUCTS_CLOSURE": "library/us_products_v3/workflows/us_products_closure.yaml",
    "US_PRODUCTS_MANAGE_OVERDRAFT_COVERAGE": (
        "library/us_products_v3/workflows/us_products_manage_overdraft_coverage.yaml"
    ),
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    **APPLICATION_WORKFLOW_FLAG_DEFINITIONS,
    **US_CHECKING_FLAG_DEFINITIONS,
}


class CheckingAccountProductTest(endtoend.End2Endtest):
    def test_workflow_apply_for_us_checking_account_with_overdraft(self):
        """
        Apply for a Checking Account for an existing customer
        and be prompted to enter overdraft limit and
        interest application day.
        """

        cust_id = endtoend.core_api_helper.create_customer()

        wf_id = endtoend.workflows_helper.start_workflow(
            "US_CHECKING_ACCOUNT_APPLICATION", context={"user_id": cust_id}
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_overdraft_limit",
            event_name="chosen_overdraft_limit",
            context={"chosen_limit": "100"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "1"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_standard_overdraft_transaction_coverage_preference",
            event_name="standard_overdraft_transaction_coverage_selected",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        us_checking_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        endtoend.accounts_helper.wait_for_account_update(
            us_checking_account_id, "activation_update"
        )

        us_checking_account = endtoend.contracts_helper.get_account(us_checking_account_id)

        creation_date = datetime.strptime(
            us_checking_account["opening_timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )

        account_schedules = endtoend.schedule_helper.get_account_schedules(us_checking_account_id)

        interest_accrual_hour = int(checking_account_template_params["interest_accrual_hour"])
        interest_accrual_minute = int(checking_account_template_params["interest_accrual_minute"])
        interest_accrual_second = int(checking_account_template_params["interest_accrual_second"])
        accrue_interest_expected_next_run_time = datetime(
            year=creation_date.year,
            month=creation_date.month,
            day=creation_date.day,
            hour=interest_accrual_hour,
            minute=interest_accrual_minute,
            second=interest_accrual_second,
        )
        if accrue_interest_expected_next_run_time <= creation_date:
            accrue_interest_expected_next_run_time += relativedelta(days=1)

        interest_application_day = int(checking_account_instance_params["interest_application_day"])
        interest_application_hour = int(
            checking_account_template_params["interest_application_hour"]
        )
        interest_application_minute = int(
            checking_account_template_params["interest_application_minute"]
        )
        interest_application_second = int(
            checking_account_template_params["interest_application_second"]
        )
        apply_interest_expected_next_run_time = datetime(
            year=creation_date.year,
            month=creation_date.month,
            day=interest_application_day,
            hour=interest_application_hour,
            minute=interest_application_minute,
            second=interest_application_second,
        )
        if apply_interest_expected_next_run_time <= creation_date:
            apply_interest_expected_next_run_time += relativedelta(months=1)

        self.assertEqual(
            accrue_interest_expected_next_run_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["ACCRUE_INTEREST_AND_DAILY_FEES"]["next_run_timestamp"],
        )
        self.assertEqual(
            apply_interest_expected_next_run_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["APPLY_ACCRUED_DEPOSIT_INTEREST"]["next_run_timestamp"],
        )

        self.assertEqual("ACCOUNT_STATUS_OPEN", us_checking_account["status"])

        self.assertEqual(
            "0", us_checking_account["instance_param_vals"]["fee_free_overdraft_limit"]
        )

        self.assertEqual(
            "100", us_checking_account["instance_param_vals"]["standard_overdraft_limit"]
        )

        self.assertEqual(
            "-1",
            us_checking_account["instance_param_vals"]["daily_atm_withdrawal_limit"],
        )

        flag_resources = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping[
                STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG
            ],
            account_ids=[us_checking_account_id],
        )
        self.assertTrue(
            flag_resources,
            "Check STANDARD_OVERDRAFT_TRANSACTION_COVERAGE flag \
            created",
        )

    def test_workflow_apply_for_us_checking_account_no_overdraft(self):
        """
        Apply for a Checking Account without an overdraft (overdraft amount of zero)
        """

        cust_id = endtoend.core_api_helper.create_customer()

        wf_id = endtoend.workflows_helper.start_workflow(
            "US_CHECKING_ACCOUNT_APPLICATION", context={"user_id": cust_id}
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_overdraft_limit",
            event_name="chosen_overdraft_limit",
            context={"chosen_limit": "0"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "1"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_standard_overdraft_transaction_coverage_preference",
            event_name="standard_overdraft_transaction_coverage_not_selected",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        us_checking_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        endtoend.accounts_helper.wait_for_account_update(
            us_checking_account_id, "activation_update"
        )

        us_checking_account = endtoend.contracts_helper.get_account(us_checking_account_id)
        creation_date = datetime.strptime(
            us_checking_account["opening_timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        account_schedules = endtoend.schedule_helper.get_account_schedules(us_checking_account_id)

        interest_accrual_hour = int(checking_account_template_params["interest_accrual_hour"])
        interest_accrual_minute = int(checking_account_template_params["interest_accrual_minute"])
        interest_accrual_second = int(checking_account_template_params["interest_accrual_second"])
        accrue_interest_expected_next_run_time = datetime(
            year=creation_date.year,
            month=creation_date.month,
            day=creation_date.day,
            hour=interest_accrual_hour,
            minute=interest_accrual_minute,
            second=interest_accrual_second,
        )
        if accrue_interest_expected_next_run_time <= creation_date:
            accrue_interest_expected_next_run_time += relativedelta(days=1)

        interest_application_day = int(checking_account_instance_params["interest_application_day"])
        interest_application_hour = int(
            checking_account_template_params["interest_application_hour"]
        )
        interest_application_minute = int(
            checking_account_template_params["interest_application_minute"]
        )
        interest_application_second = int(
            checking_account_template_params["interest_application_second"]
        )
        apply_interest_expected_next_run_time = datetime(
            year=creation_date.year,
            month=creation_date.month,
            day=interest_application_day,
            hour=interest_application_hour,
            minute=interest_application_minute,
            second=interest_application_second,
        )
        if apply_interest_expected_next_run_time <= creation_date:
            apply_interest_expected_next_run_time += relativedelta(months=1)

        self.assertEqual(
            accrue_interest_expected_next_run_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["ACCRUE_INTEREST_AND_DAILY_FEES"]["next_run_timestamp"],
        )
        self.assertEqual(
            apply_interest_expected_next_run_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["APPLY_ACCRUED_DEPOSIT_INTEREST"]["next_run_timestamp"],
        )

        self.assertEqual("ACCOUNT_STATUS_OPEN", us_checking_account["status"])

        self.assertEqual(
            "0", us_checking_account["instance_param_vals"]["fee_free_overdraft_limit"]
        )

        self.assertEqual(
            "0", us_checking_account["instance_param_vals"]["standard_overdraft_limit"]
        )

        self.assertEqual(
            "-1",
            us_checking_account["instance_param_vals"]["daily_atm_withdrawal_limit"],
        )

        flag_resources = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping[
                STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG
            ],
            account_ids=[us_checking_account_id],
        )
        self.assertFalse(
            flag_resources, "Check not STANDARD_OVERDRAFT_TRANSACTION_COVERAGE flag created"
        )

    def test_workflow_close_account_failure_and_ticket_no_plan(self):
        """
        Check close account fails with negative balance
        We also expect a notification ticket to be created
        """
        cust_id = endtoend.core_api_helper.create_customer()

        checking_instance_params = {
            "fee_free_overdraft_limit": "0",
            "standard_overdraft_limit": "1000",
            "interest_application_day": "1",
            "daily_atm_withdrawal_limit": "-1",
        }

        us_checking_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account_for_close",
            instance_param_vals=checking_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_checking_account_id = us_checking_account["id"]

        deposit_posting = endtoend.postings_helper.outbound_hard_settlement(
            account_id=us_checking_account_id, amount="99.99", denomination="USD"
        )
        pib = endtoend.postings_helper.get_posting_batch(deposit_posting)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            us_checking_account_id,
            expected_balances=[
                (BalanceDimensions(address="DEFAULT", denomination="USD"), "-99.99")
            ],
            description="Checking account balance updated",
        )

        # Close the Checking account
        wf_id = endtoend.workflows_helper.start_workflow(
            "US_PRODUCTS_CLOSURE",
            context={"user_id": cust_id, "account_id": us_checking_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closure_failure")

        tickets = endtoend.workflows_helper.wait_for_ticket_creation(
            workflow_instance_id=wf_id,
            tags="us-account-closure-failure-notification",
        )

        ticket = tickets[0]
        self.assertEqual(us_checking_account_id, ticket["metadata"]["account_id"])
        self.assertEqual(
            "Account is ineligible for closure while the final balance is negative",
            ticket["metadata"]["rejection_reason"],
            f"Unexpected rejection_reason (ticket ID: {ticket['id']})",
        )
        self.assertEqual(
            "-99.99",
            ticket["metadata"]["final_balance"],
            f"Unexpected final_balance (ticket ID: {ticket['id']})",
        )

        account = endtoend.contracts_helper.get_account(us_checking_account_id)

        # account should remain in OPEN status
        self.assertEqual("ACCOUNT_STATUS_OPEN", account["status"])

    def test_workflow_manage_overdraft_coverage(self):
        """
        Test managing the overdraft coverage flag for an existing customer, enabling and disabling
        on a valid checking account type.
        """

        cust_id = endtoend.core_api_helper.create_customer()

        # Attempt to manage flag on invalid account type
        dummy_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "US_PRODUCTS_MANAGE_OVERDRAFT_COVERAGE",
            context={"user_id": cust_id, "account_id": dummy_account["id"]},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "manage_flag_failure")
        rejection_reason = endtoend.workflows_helper.get_global_context(wf_id)["rejection_reason"]
        self.assertEqual(rejection_reason, "Account is not a US checking account")

        # Enable overdraft coverage flag for checking account
        checking_instance_params = {
            "fee_free_overdraft_limit": "0",
            "standard_overdraft_limit": "1000",
            "interest_application_day": "1",
            "daily_atm_withdrawal_limit": "-1",
        }
        us_checking_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account_v3",
            instance_param_vals=checking_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_checking_account_id = us_checking_account["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "US_PRODUCTS_MANAGE_OVERDRAFT_COVERAGE",
            context={"user_id": cust_id, "account_id": us_checking_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_enable_flag",
            event_name="overdraft_coverage_enabled",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "manage_flag_success")

        flag_resources = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping[
                STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG
            ],
            account_ids=[us_checking_account_id],
        )
        self.assertEqual(len(flag_resources), 1)
        res_flag_definition_id = flag_resources[0].get("flag_definition_id")
        res_flag_is_active = flag_resources[0].get("is_active")
        self.assertEqual(
            res_flag_definition_id,
            endtoend.testhandle.flag_definition_id_mapping[
                STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG
            ],
        )
        self.assertTrue(res_flag_is_active)

        # Disable overdraft coverage flag for checking account
        wf_id = endtoend.workflows_helper.start_workflow(
            "US_PRODUCTS_MANAGE_OVERDRAFT_COVERAGE",
            context={"user_id": cust_id, "account_id": us_checking_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_disable_flag",
            event_name="overdraft_coverage_disabled",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "manage_flag_success")

        flag_resources = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping[
                STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG
            ],
            account_ids=[us_checking_account_id],
        )
        # only active flags are retrieved
        self.assertEqual(len(flag_resources), 0)

    def test_per_transaction_fee_capped(self):
        """
        Check that per transaction fees are capped
        """
        cust_id = endtoend.core_api_helper.create_customer()

        checking_instance_params = {
            "fee_free_overdraft_limit": "0",
            "standard_overdraft_limit": "1000",
            "interest_application_day": "1",
            "daily_atm_withdrawal_limit": "-1",
        }

        us_checking_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account_v3",
            instance_param_vals=checking_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_checking_account_id = us_checking_account["id"]

        # standard_overdraft_per_transaction_fee = 34
        # standard_overdraft_fee_cap = 80

        withdrawal_posting_1 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=us_checking_account_id, amount="100", denomination="USD"
        )
        pib_1 = endtoend.postings_helper.get_posting_batch(withdrawal_posting_1)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_1["status"])

        withdrawal_posting_2 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=us_checking_account_id, amount="100", denomination="USD"
        )
        pib_2 = endtoend.postings_helper.get_posting_batch(withdrawal_posting_2)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_2["status"])

        withdrawal_posting_3 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=us_checking_account_id, amount="100", denomination="USD"
        )
        pib_3 = endtoend.postings_helper.get_posting_batch(withdrawal_posting_3)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_3["status"])

        # Fee should be charged only twice from the three postings
        endtoend.balances_helper.wait_for_account_balances(
            us_checking_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="USD"), "-368")],
            description="Checking account balance updated",
        )

    def test_workflow_close_us_account_positive_balance_no_plan(self):
        """
        Close a US checking account which is not associated to any plans
        and has a positive remaining balance
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
            contract="us_checking_account_v3",
            instance_param_vals=checking_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_checking_account_id = us_checking_account["id"]

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=us_checking_account_id, amount="5500", denomination="USD"
        )

        endtoend.balances_helper.wait_for_account_balances(
            us_checking_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="USD"), "5500")],
            description="Checking account balance updated",
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

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="retrieve_disbursement_account",
            event_name="disbursement_account_given",
            context={"target_account_id": "1"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")

        closed_checking_account = endtoend.contracts_helper.get_account(us_checking_account_id)

        self.assertTrue(closed_checking_account["status"] == "ACCOUNT_STATUS_CLOSED")

    def test_workflow_close_us_account_zero_balance_no_plan(self):
        """
        Close a US checking account which is not associated to any plans
        and has a zero remaining balance
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
            contract="us_checking_account_v3",
            instance_param_vals=checking_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_checking_account_id = us_checking_account["id"]

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

        closed_checking_account = endtoend.contracts_helper.get_account(us_checking_account_id)

        self.assertTrue(closed_checking_account["status"] == "ACCOUNT_STATUS_CLOSED")

    def test_standard_overdraft_transaction_type_coverage(self):
        cust_id = endtoend.core_api_helper.create_customer()

        us_checking_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_checking_account_v3",
            instance_param_vals=checking_account_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        account_id = us_checking_account["id"]

        credit_posting = endtoend.postings_helper.inbound_hard_settlement(
            account_id=account_id, amount="100", denomination="USD"
        )
        pib_1 = endtoend.postings_helper.get_posting_batch(credit_posting)
        self.assertEqual(
            "POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED",
            pib_1["status"],
            "Fund the acount",
        )

        # Try an eCommerge transaction that would require overdraft
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=account_id,
            amount="200",
            denomination="USD",
            instruction_details={"transaction_code": "3123"},
        )
        pib_2 = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(
            "POSTING_INSTRUCTION_BATCH_STATUS_REJECTED",
            pib_2["status"],
            "eCommerge transaction not covered",
        )

        # Multiple postings in batch should be rejected if one posting is not covered
        posting_instructions = [
            PostingInstruction(
                instruction=OutboundHardSettlement(
                    amount="5.5", denomination="USD", target_account_id=account_id
                ),
                instruction_details={"transaction_code": "3123"},
            ),
            PostingInstruction(
                instruction=OutboundHardSettlement(
                    amount="150.5", denomination="USD", target_account_id=account_id
                ),
                instruction_details={"transaction_code": "other"},
            ),
            PostingInstruction(
                instruction=InboundHardSettlement(
                    amount="2", denomination="USD", target_account_id=account_id
                ),
                instruction_details={"transaction_code": "other"},
            ),
        ]
        postingID = endtoend.postings_helper.send_and_wait_for_posting_instruction_batch(
            create_pib_from_posting_instructions(posting_instructions=posting_instructions)[
                "posting_instruction_batch"
            ]
        )
        pib_3 = endtoend.postings_helper.get_posting_batch(postingID)

        self.assertEqual(
            "POSTING_INSTRUCTION_BATCH_STATUS_REJECTED",
            pib_3["status"],
            "eCommerge transaction not covered in multiple posting batch",
        )

        # Flag account for overdraft transaction type coverage
        endtoend.core_api_helper.create_flag(
            endtoend.testhandle.flag_definition_id_mapping[
                STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG
            ],
            account_id=account_id,
        )["id"]

        # Now retry the eCommerce transaction
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=account_id,
            amount="200",
            denomination="USD",
            instruction_details={"transaction_code": "3123"},
        )
        pib_3 = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(
            "POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED",
            pib_3["status"],
            "eCommerce transaction with overdraft coverage enabled",
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="USD"), "-100")],
            description="Balance after 1 successful eCommerce withdrawal into overdraft",
        )


if __name__ == "__main__":
    endtoend.runtests()
