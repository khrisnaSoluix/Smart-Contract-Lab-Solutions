# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import time
from json import loads

# third_party
import requests

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions
from inception_sdk.vault.postings.posting_classes import (
    InboundHardSettlement,
    OutboundHardSettlement,
)
from inception_sdk.test_framework.endtoend.helper import COMMON_ACCOUNT_SCHEDULE_TAG_PATH

from library.casa.tests.e2e.casa_test_params import (
    eas_template_params,
    easy_access_saver_template_params_allow_excess_withdrawals,
    eas_instance_params,
    ca_template_params,
    ca_instance_params,
    internal_accounts_tside,
    DORMANCY_FLAG,
)

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "easy_access_saver": {
        "path": "library/casa/contracts/casa.py",
        "template_params": eas_template_params,
    },
    "easy_access_saver_allow_excess_withdrawals": {
        "path": "library/casa/contracts/casa.py",
        "template_params": easy_access_saver_template_params_allow_excess_withdrawals,
    },
    "current_account": {
        "path": "library/casa/contracts/casa.py",
        "template_params": ca_template_params,
    },
}

endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"},
    "interest": {"path": "library/common/contract_modules/interest.py"},
}

endtoend.testhandle.WORKFLOWS = {
    "CASA_APPLICATION": ("library/casa/workflows/casa_application.yaml"),
    "CASA_OVERDRAFT_CREATION": ("library/casa/workflows/casa_overdraft_creation.yaml"),
    "CASA_OVERDRAFT_CANCELLATION": ("library/casa/workflows/casa_overdraft_cancellation.yaml"),
    "CASA_OVERDRAFT_ADJUSTMENT": ("library/casa/workflows/casa_overdraft_adjustment.yaml"),
    "CASA_CLOSURE": "library/casa/workflows/casa_closure.yaml",
    "CASA_INTEREST_PAYMENT_DATE_CHANGE": (
        "library/casa/workflows/casa_interest_payment_date_change.yaml"
    ),
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    DORMANCY_FLAG: "library/common/flag_definitions/account_dormant.resource.yaml",
    "CASA_TIER_UPPER": ("library/casa/flag_definitions/casa_tier_upper.resource.yaml"),
    "CASA_TIER_MIDDLE": ("library/casa/flag_definitions/casa_tier_middle.resource.yaml"),
    "CASA_TIER_LOWER": ("library/casa/flag_definitions/casa_tier_lower.resource.yaml"),
}

endtoend.testhandle.ACCOUNT_SCHEDULE_TAGS = {
    "CASA_ACCRUE_INTEREST_AND_DAILY_FEES_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "CASA_APPLY_ACCRUED_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "CASA_APPLY_ANNUAL_FEES_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "CASA_APPLY_MONTHLY_FEES_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
}


class CasaProductTest(endtoend.End2Endtest):
    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at
        # Uncomment this for timing info.
        # print("\n{} ({}s)".format(self.id().rpartition(".")[2], round(self._elapsed_time, 2)))

    def test_workflow_fails_to_close_account_in_pending_closure_state(self):
        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=ca_instance_params,
            permitted_denominations=["GBP", "USD", "EUR"],
            status="ACCOUNT_STATUS_OPEN",
        )
        casa_id = account["id"]

        endtoend.core_api_helper.update_account(
            casa_id,
            endtoend.core_api_helper.AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE,
        )

        wf_context = {"account_id": casa_id, "user_id": cust_id}

        wf_id = endtoend.workflows_helper.start_workflow("CASA_CLOSURE", context=wf_context)

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closure_failure")

        account = endtoend.contracts_helper.get_account(casa_id)

        self.assertEqual("ACCOUNT_STATUS_PENDING_CLOSURE", account["status"])

    def test_close_account_with_multiple_currencies(self):
        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=ca_instance_params,
            permitted_denominations=["GBP", "USD", "EUR"],
            status="ACCOUNT_STATUS_OPEN",
        )
        casa_id = account["id"]

        account2 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=ca_instance_params,
            permitted_denominations=["GBP", "USD", "EUR"],
            status="ACCOUNT_STATUS_OPEN",
        )
        casa_id2 = account2["id"]

        # the account have balance left in three currencies
        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=casa_id, amount="500", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=casa_id, amount="100", denomination="EUR"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=casa_id, amount="10", denomination="USD"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        wf_context = {"account_id": casa_id, "user_id": cust_id}
        wf_id = endtoend.workflows_helper.start_workflow("CASA_CLOSURE", context=wf_context)

        state_id = endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_disbursement_destination",
            event_name="local_transfer_selected",
            context={"target_account_id": casa_id2},
        )

        state_id = endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_disbursement_destination",
            event_name="local_transfer_selected",
            context={"target_account_id": casa_id2},
            current_state_id=state_id,
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_disbursement_destination",
            event_name="local_transfer_selected",
            context={"target_account_id": casa_id2},
            current_state_id=state_id,
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")

        endtoend.balances_helper.wait_for_account_balances(
            casa_id2,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "500",
                ),
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="EUR"
                    ),
                    "100",
                ),
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="USD"
                    ),
                    "10",
                ),
            ],
        )

    def test_close_account_with_transaction_during_closure(self):
        """
        Test closure of current account with transaction during closure,
        """
        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=ca_instance_params,
            permitted_denominations=["GBP"],
            status="ACCOUNT_STATUS_OPEN",
        )
        casa_id = account["id"]

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=casa_id, amount="500", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        wf_context = {"account_id": casa_id, "user_id": cust_id}

        savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=eas_instance_params,
            permitted_denominations=["GBP", "USD", "EUR"],
            status="ACCOUNT_STATUS_OPEN",
        )

        savings_account_id = savings_account["id"]

        wf_id = endtoend.workflows_helper.start_workflow("CASA_CLOSURE", context=wf_context)

        # Wait for the balances and account list to have been processed, then
        # make another inbound posting.
        endtoend.workflows_helper.wait_for_state(wf_id, "capture_disbursement_destination")

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=casa_id, amount="500", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Transfer out the first outstanding amount,
        # then another to cover the most recent posting
        state_id = endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_disbursement_destination",
            event_name="local_transfer_selected",
            context={"target_account_id": savings_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_disbursement_destination",
            event_name="local_transfer_selected",
            context={"target_account_id": savings_account_id},
            current_state_id=state_id,
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                casa_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "0",
                    )
                ],
                savings_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "1000",
                    )
                ],
            }
        )

    def test_close_account_with_no_valid_account_for_disbursement_and_zero_balance(
        self,
    ):
        """
        this test case check on closing account wiht no valid account for disbursement
        as well as closing account with zero balance
        """
        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=ca_instance_params,
            permitted_denominations=["GBP"],
            status="ACCOUNT_STATUS_OPEN",
        )
        casa_id = account["id"]

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=casa_id, amount="500", denomination="GBP"
        )

        endtoend.balances_helper.wait_for_account_balances(
            casa_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "500",
                )
            ],
        )

        wf_context = {"account_id": casa_id, "user_id": cust_id}
        wf_id = endtoend.workflows_helper.start_workflow("CASA_CLOSURE", context=wf_context)

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closure_failure")
        rejection_reason = endtoend.workflows_helper.get_global_context(wf_id)["rejection_reason"]
        self.assertEqual(rejection_reason, "no suitable account for disbursement")

        casa = endtoend.contracts_helper.get_account(
            account_id=casa_id,
        )
        self.assertEqual("ACCOUNT_STATUS_OPEN", casa["status"])

        # Clear the account balance
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=casa_id,
            amount="500",
            denomination="GBP",
            instruction_details={"transaction_code": "6000"},
        )

        endtoend.balances_helper.wait_for_account_balances(
            casa_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "0",
                )
            ],
        )

        # Close the current account
        wf_id = endtoend.workflows_helper.start_workflow("CASA_CLOSURE", context=wf_context)

        endtoend.workflows_helper.send_event(
            wf_id, event_state="request_confirmation", event_name="closure_confirmed"
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")

        # Ensure that the current account is closed
        casa = endtoend.contracts_helper.get_account(casa_id)
        self.assertEqual("ACCOUNT_STATUS_CLOSED", casa["status"])

    def test_apply_for_casa_with_overdraft(self):
        """
        Apply for a Current Account for an existing customer
        and be prompted to enter overdraft limit and
        interest application day.
        """

        cust_id = endtoend.core_api_helper.create_customer()

        wf_id = endtoend.workflows_helper.start_workflow(
            "CASA_APPLICATION",
            context={
                "user_id": cust_id,
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_product_id",
            event_name="product_id_selected",
            context={
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["current_account"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_tier",
            event_name="account_tier_selected",
            context={
                "account_tier": endtoend.testhandle.flag_definition_id_mapping["CASA_TIER_UPPER"]
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_daily_atm_limit",
            event_name="chosen_daily_atm_limit",
            context={"chosen_daily_atm_limit": "200"},
        )

        state_id = endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_unarranged_overdraft_limit",
            event_name="chosen_overdraft_limit",
            context={"chosen_unarranged_overdraft_limit": "9000"},
        )

        # test overdraft max limit is enforced
        state_id = endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_arranged_overdraft_limit",
            event_name="chosen_arranged_overdraft_limit",
            context={"chosen_arranged_overdraft_limit": "10001"},
            current_state_id=state_id,
        )

        # test with acceptable limit
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_arranged_overdraft_limit",
            event_name="chosen_arranged_overdraft_limit",
            context={"chosen_arranged_overdraft_limit": "100"},
            current_state_id=state_id,
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="autosave_not_available",
            event_name="proceed_without_autosave",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "1"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        casa_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        endtoend.accounts_helper.wait_for_account_update(casa_id, "activation_update")

        casa = endtoend.contracts_helper.get_account(casa_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", casa["status"])

        self.assertEqual("100", casa["instance_param_vals"]["arranged_overdraft_limit"])

        self.assertEqual("200", casa["instance_param_vals"]["daily_atm_withdrawal_limit"])

    def test_apply_for_casa_no_overdraft(self):
        """
        Apply for a Current Account without an overdraft (overdraft amount of zero)
        """

        cust_id = endtoend.core_api_helper.create_customer()

        wf_id = endtoend.workflows_helper.start_workflow(
            "CASA_APPLICATION",
            context={
                "user_id": cust_id,
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_product_id",
            event_name="product_id_selected",
            context={
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["current_account"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_tier",
            event_name="account_tier_selected",
            context={
                "account_tier": endtoend.testhandle.flag_definition_id_mapping["CASA_TIER_UPPER"]
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_daily_atm_limit",
            event_name="chosen_daily_atm_limit",
            context={"chosen_daily_atm_limit": "400"},
        )

        # Unarranged overdraft is 0 so arranged overdraft should also default to 0
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_unarranged_overdraft_limit",
            event_name="chosen_overdraft_limit",
            context={"chosen_unarranged_overdraft_limit": "0"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="autosave_not_available",
            event_name="proceed_without_autosave",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "1"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        casa_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        endtoend.accounts_helper.wait_for_account_update(casa_id, "activation_update")

        casa = endtoend.contracts_helper.get_account(casa_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", casa["status"])

        self.assertEqual("0", casa["instance_param_vals"]["arranged_overdraft_limit"])

        self.assertEqual("400", casa["instance_param_vals"]["daily_atm_withdrawal_limit"])

    def test_add_overdraft_to_existing_account(self):
        """
        Add an overdraft to an existing customer's account
        """
        test_param_values = {
            "arranged_overdraft_limit": "100",
            "daily_atm_withdrawal_limit": "200",
        }

        cust_id = endtoend.core_api_helper.create_customer()
        casa_params_with_no_overdraft = ca_instance_params.copy()
        casa_params_with_no_overdraft["arranged_overdraft_limit"] = "0"

        casa = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=casa_params_with_no_overdraft,
            permitted_denominations=["GBP", "EUR", "USD"],
            status="ACCOUNT_STATUS_OPEN",
        )

        casa_id = casa["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "CASA_OVERDRAFT_CREATION",
            context={"user_id": cust_id, "account_id": casa_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_arranged_overdraft_limit",
            event_name="chosen_overdraft_limit",
            context={"chosen_limit": test_param_values["arranged_overdraft_limit"]},
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "display_overdraft")

        casa_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        endtoend.accounts_helper.wait_for_account_update(casa_id, "instance_param_vals_update")

        casa = endtoend.contracts_helper.get_account(casa_id)

        self.assertEqual(
            "100",
            casa["instance_param_vals"]["arranged_overdraft_limit"],
            "arranged_overdraft_limit parameter value not updated as expected",
        )

        self.assertEqual(
            "1000",
            casa["instance_param_vals"]["daily_atm_withdrawal_limit"],
            "daily_atm_withdrawal_limit parameter value not updated as expected",
        )

    def test_cancel_overdraft(self):
        """
        Test an overdraft can be removed from a current account
        """

        cust_id = endtoend.core_api_helper.create_customer()

        casa = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=ca_instance_params,
            permitted_denominations=["GBP", "EUR", "USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        casa_id = casa["id"]

        self.assertEqual("ACCOUNT_STATUS_OPEN", casa["status"])

        self.assertEqual("1000", casa["instance_param_vals"]["arranged_overdraft_limit"])

        wf_id = endtoend.workflows_helper.start_workflow(
            "CASA_OVERDRAFT_CANCELLATION",
            context={"user_id": cust_id, "account_id": casa_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_cancellation",
            event_name="overdraft_displayed",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "overdraft_cancelled")
        endtoend.accounts_helper.wait_for_account_update(casa_id, "instance_param_vals_update")
        casa = endtoend.contracts_helper.get_account(casa_id)
        self.assertEqual("0", casa["instance_param_vals"]["arranged_overdraft_limit"])

    def test_daily_atm_withdrawal_limit(self):
        """
        Test the configuration of the daily ATM limit when opening the account
        and then that the limit is enforced for ATM withdrawal
        """
        cust_id = endtoend.core_api_helper.create_customer()

        wf_id = endtoend.workflows_helper.start_workflow(
            "CASA_APPLICATION",
            context={
                "user_id": cust_id,
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_product_id",
            event_name="product_id_selected",
            context={
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["current_account"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_tier",
            event_name="account_tier_selected",
            context={
                "account_tier": endtoend.testhandle.flag_definition_id_mapping["CASA_TIER_UPPER"]
            },
        )

        # Try with limit too large
        state_id = endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_daily_atm_limit",
            event_name="chosen_daily_atm_limit",
            context={"chosen_daily_atm_limit": "20000"},
        )

        # Acceptable limit
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_daily_atm_limit",
            event_name="chosen_daily_atm_limit",
            context={"chosen_daily_atm_limit": "300"},
            current_state_id=state_id,
        )

        state_id = endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_unarranged_overdraft_limit",
            event_name="chosen_overdraft_limit",
            context={"chosen_unarranged_overdraft_limit": "9000"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_arranged_overdraft_limit",
            event_name="chosen_arranged_overdraft_limit",
            context={"chosen_arranged_overdraft_limit": "1000"},
            current_state_id=state_id,
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="autosave_not_available",
            event_name="proceed_without_autosave",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "1"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        casa_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]

        casa = endtoend.contracts_helper.get_account(casa_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", casa["status"])

        self.assertEqual("300", casa["instance_param_vals"]["daily_atm_withdrawal_limit"])

        # Spend non-ATM transaction more than daily limit -> OK
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=casa_id,
            amount="400",
            denomination="GBP",
            instruction_details={"transaction_code": "6000"},
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Now a posting of ATM type below the limit -> OK
        # split into a hard settlement and an auth
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=casa_id,
            amount="200",
            denomination="GBP",
            instruction_details={"transaction_code": "6011"},
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        postingID = endtoend.postings_helper.outbound_auth(
            account_id=casa_id,
            amount="79",
            denomination="GBP",
            instruction_details={"transaction_code": "6011"},
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Now a posting of ATM type that goes over the limit (auth)
        postingID = endtoend.postings_helper.outbound_auth(
            account_id=casa_id,
            amount="21.50",
            denomination="GBP",
            instruction_details={"transaction_code": "6011"},
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Now a posting of ATM type that goes over the limit (hard settlement)
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=casa_id,
            amount="21.50",
            denomination="GBP",
            instruction_details={"transaction_code": "6011"},
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Another non-ATM transaction -> OK
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=casa_id,
            amount="400",
            denomination="GBP",
            instruction_details={"transaction_code": "6000"},
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Check the daily_atm_withdrawal_limit parameter can be updated
        param_value = "280"
        resp = endtoend.core_api_helper.update_account_instance_parameters(
            casa_id,
            instance_param_vals={"daily_atm_withdrawal_limit": param_value},
        )
        endtoend.accounts_helper.wait_for_account_update(account_update_id=resp["id"])
        casa = endtoend.contracts_helper.get_account(casa_id)
        self.assertEqual(
            param_value,
            casa["instance_param_vals"]["daily_atm_withdrawal_limit"],
            "Failed to update the daily_atm_withdrawal_limit instance parameter account "
            "id '{}' resp: '{}'".format(casa_id, resp),
        )

        # Check the updated parameter has taken effect
        # Withdraw amount between old limit 300 and new limit 280
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=casa_id,
            amount="1.50",
            denomination="GBP",
            instruction_details={"transaction_code": "6011"},
        )
        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            casa_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "-1000",
                )
            ],
            description="Default balance is as expected",
        )

        # Check daily_atm_withdrawal_limit cant be made higher than max
        param_value = "5001"
        with self.assertRaises(requests.exceptions.HTTPError):
            endtoend.core_api_helper.update_account_instance_parameters(
                casa_id,
                instance_param_vals={"daily_atm_withdrawal_limit": param_value},
            )
        casa = endtoend.contracts_helper.get_account(casa_id)
        self.assertEqual(
            "280",
            casa["instance_param_vals"]["daily_atm_withdrawal_limit"],
            "Update daily_atm_withdrawal_limit should have been rejected and remained at 280",
        )

    def test_overdraft_limit_balance_checks(self):
        # Ensure when changing the overdraft, we aren't making the overdraft less than the current
        # balance
        cust_id = endtoend.core_api_helper.create_customer()
        ca_instance_params = {
            "arranged_overdraft_limit": "1000",
            "unarranged_overdraft_limit": "2000",
            "interest_application_day": "1",
            "daily_atm_withdrawal_limit": "1000",
        }
        # Create current account
        account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=ca_instance_params,
            permitted_denominations=["GBP", "EUR", "USD"],
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # Populate balance for customer
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=account_id,
            amount="1500",
            denomination="GBP",
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "-1500",
                )
            ],
        )

        # Start workflow
        wf_id = endtoend.workflows_helper.start_workflow(
            "CASA_OVERDRAFT_ADJUSTMENT", context={"account_id": account_id}
        )

        # Try adjusting unarranged overdraft with amount below current balance
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_unarranged_overdraft_limit",
            event_name="unarranged_overdraft_limit_chosen",
            context={"chosen_unarranged_limit": "1300"},
        )

        # Select ok at the failure event
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_unarranged_overdraft_check_failure",
            event_name="unarranged_rejection_displayed",
            context=None,
        )

        # Acceptable unarranged limit
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_unarranged_overdraft_limit",
            event_name="unarranged_overdraft_limit_chosen",
            context={"chosen_unarranged_limit": "1700"},
        )

        # Arranged limit greater than new unarranged overdraft limit
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_arranged_overdraft_limit",
            event_name="arranged_overdraft_limit_chosen",
            context={"chosen_arranged_limit": "1800"},
        )

        # Select ok at the failure event
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_arranged_overdraft_check_failure",
            event_name="arranged_rejection_displayed",
            context=None,
        )

        # Arranged limit less than current balance
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_arranged_overdraft_limit",
            event_name="arranged_overdraft_limit_chosen",
            context={"chosen_arranged_limit": "1200"},
        )

        # Select ok at the failure event
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_arranged_overdraft_check_failure",
            event_name="arranged_rejection_displayed",
            context=None,
        )

        # Acceptable arranged limit
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_arranged_overdraft_limit",
            event_name="arranged_overdraft_limit_chosen",
            context={"chosen_arranged_limit": "1500"},
        )

        # Select Proceed at the acceptance event
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_overdraft_limits",
            event_name="overdraft_limits_confirmed",
            context=None,
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "overdraft_adjusted")

        endtoend.accounts_helper.wait_for_account_update(account_id, "instance_param_vals_update")

        # Check the parameters have changed
        casa = endtoend.contracts_helper.get_account(account_id)

        self.assertEqual("1500", casa["instance_param_vals"]["arranged_overdraft_limit"])

        self.assertEqual("1700", casa["instance_param_vals"]["unarranged_overdraft_limit"])

    def test_overdraft_limit_parameter_constraints(self):
        # Ensure when changing the overdraft, we aren't breaching the parameter limits
        cust_id_1 = endtoend.core_api_helper.create_customer()
        ca_instance_params = {
            "arranged_overdraft_limit": "1000",
            "unarranged_overdraft_limit": "2000",
            "interest_application_day": "1",
            "daily_atm_withdrawal_limit": "1000",
        }
        # Create current account
        account_id = endtoend.contracts_helper.create_account(
            customer=cust_id_1,
            contract="current_account",
            instance_param_vals=ca_instance_params,
            permitted_denominations=["GBP"],
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # Populate balance for customer 1
        endtoend.postings_helper.inbound_hard_settlement(
            account_id=account_id,
            amount="1500",
            denomination="GBP",
        )

        # Start workflow
        wf_id = endtoend.workflows_helper.start_workflow(
            "CASA_OVERDRAFT_ADJUSTMENT", context={"account_id": account_id}
        )

        # Try adjusting unarranged overdraft to be above the parameter shape limit
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_unarranged_overdraft_limit",
            event_name="unarranged_overdraft_limit_chosen",
            context={"chosen_unarranged_limit": "20000"},
        )

        # Select ok at the failure event
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_unarranged_overdraft_check_failure",
            event_name="unarranged_rejection_displayed",
            context=None,
        )

        # Try adjusting unarranged overdraft to be below 0
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_unarranged_overdraft_limit",
            event_name="unarranged_overdraft_limit_chosen",
            context={"chosen_unarranged_limit": "-2500"},
        )

        # Select ok at the failure event
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_unarranged_overdraft_check_failure",
            event_name="unarranged_rejection_displayed",
            context=None,
        )

        # Acceptable unarranged limit
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_unarranged_overdraft_limit",
            event_name="unarranged_overdraft_limit_chosen",
            context={"chosen_unarranged_limit": "2500"},
        )

        # Arranged limit less than the current buffer
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_arranged_overdraft_limit",
            event_name="arranged_overdraft_limit_chosen",
            context={"chosen_arranged_limit": "20"},
        )

        # Select ok at the failure event
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_arranged_overdraft_check_failure",
            event_name="arranged_rejection_displayed",
            context=None,
        )

        # Arranged limit less than 0
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_arranged_overdraft_limit",
            event_name="arranged_overdraft_limit_chosen",
            context={"chosen_arranged_limit": "-300"},
        )

        # Select ok at the failure event
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="display_arranged_overdraft_check_failure",
            event_name="arranged_rejection_displayed",
            context=None,
        )

        # Acceptable arranged limit
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_arranged_overdraft_limit",
            event_name="arranged_overdraft_limit_chosen",
            context={"chosen_arranged_limit": "1500"},
        )

        # Select Proceed at the acceptance event
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_overdraft_limits",
            event_name="overdraft_limits_confirmed",
            context=None,
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "overdraft_adjusted")

        endtoend.accounts_helper.wait_for_account_update(account_id, "instance_param_vals_update")

        # Check the parameters have changed
        casa = endtoend.contracts_helper.get_account(account_id)

        self.assertEqual("1500", casa["instance_param_vals"]["arranged_overdraft_limit"])

        self.assertEqual("2500", casa["instance_param_vals"]["unarranged_overdraft_limit"])

    def test_multi_currency_account_spending_between_accounts(self):
        cust_id_1 = endtoend.core_api_helper.create_customer()
        cust_id_2 = endtoend.core_api_helper.create_customer()

        casa_id_1 = endtoend.contracts_helper.create_account(
            customer=cust_id_1,
            contract="current_account",
            instance_param_vals=ca_instance_params,
            permitted_denominations=["GBP", "USD", "EUR"],
            status="ACCOUNT_STATUS_OPEN",
        )["id"]
        casa_id_2 = endtoend.contracts_helper.create_account(
            customer=cust_id_2,
            contract="current_account",
            instance_param_vals=ca_instance_params,
            permitted_denominations=["GBP", "USD", "EUR"],
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # Populate balance for customer 1
        endtoend.postings_helper.inbound_hard_settlement(
            account_id=casa_id_1,
            amount="200",
            denomination="EUR",
        )

        endtoend.balances_helper.wait_for_account_balances(
            casa_id_1,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="EUR"
                    ),
                    "200",
                )
            ],
        )

        # Transfer to customer 2
        endtoend.postings_helper.create_transfer(
            amount="100.00",
            debtor_target_account_id=casa_id_1,
            creditor_target_account_id=casa_id_2,
            denomination="EUR",
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                casa_id_1: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="EUR"
                        ),
                        "100",
                    )
                ],
                casa_id_2: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="EUR"
                        ),
                        "100",
                    )
                ],
            }
        )

    def test_dormant_account_rejects_external_postings(self):
        """
        Test that a dormant account rejects normal postings
        """
        cust_id = endtoend.core_api_helper.create_customer()

        casa = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=ca_instance_params,
            permitted_denominations=["GBP", "EUR", "USD"],
            status="ACCOUNT_STATUS_OPEN",
        )

        casa_id = casa["id"]

        self.assertEqual("ACCOUNT_STATUS_OPEN", casa["status"])

        # Make transaction before dormancy effected
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=casa_id,
            amount="400",
            denomination="GBP",
            instruction_details={"transaction_code": "6000"},
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Flag account as dormant
        flag_id = endtoend.core_api_helper.create_flag(
            endtoend.testhandle.flag_definition_id_mapping[DORMANCY_FLAG], account_id=casa_id
        )["id"]

        # Expect further transactions to be rejected, credit and debit
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=casa_id,
            amount="200",
            denomination="GBP",
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=casa_id,
            amount="200",
            denomination="GBP",
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            casa_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "-400",
                )
            ],
        )

        # Remove the dormancy flag otherwise the e2e helper can't close the account
        endtoend.core_api_helper.remove_flag(flag_id)

    def test_update_autosave_savings_account(self):
        """
        Open a current account, then a savings account,
        then update the autosave_savings_account parameter,
        test Autosave works properly,
        then close the savings account
        """
        cust_id = endtoend.core_api_helper.create_customer()

        casa_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=ca_instance_params,
            permitted_denominations=["GBP", "EUR", "USD"],
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # Fund the account - it needs a positive balance for testing
        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=casa_id,
            amount="2000",
            denomination="GBP",
        )

        endtoend.balances_helper.wait_for_account_balances(
            casa_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "2000",
                )
            ],
            description="Default balance is as expected after funding",
        )

        # Purchase posting
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=casa_id,
            amount="400",
            denomination="GBP",
            instruction_details={"transaction_code": "6000"},
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Now a posting of ATM type
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=casa_id,
            amount="200",
            denomination="GBP",
            instruction_details={"transaction_code": "6011"},
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # check balance, should be nothing transferred to savings
        endtoend.balances_helper.wait_for_account_balances(
            casa_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "1400",
                )
            ],
            description="Expected balance, no savings account yet setup",
        )

        savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=eas_instance_params,
            permitted_denominations=["GBP", "USD", "EUR"],
            status="ACCOUNT_STATUS_OPEN",
        )

        savings_account_id = savings_account["id"]

        self.assertEqual("ACCOUNT_STATUS_OPEN", savings_account["status"])

        # Check the autosave_savings_account parameter can be updated
        resp = endtoend.core_api_helper.update_account_instance_parameters(
            casa_id,
            instance_param_vals={"autosave_savings_account": savings_account_id},
        )
        endtoend.accounts_helper.wait_for_account_update(account_update_id=resp["id"])
        casa = endtoend.contracts_helper.get_account(casa_id)
        self.assertEqual(
            savings_account_id,
            casa["instance_param_vals"]["autosave_savings_account"],
            "Failed to update the autosave_savings_account instance parameter account "
            "id '{}' resp: '{}'".format(casa_id, resp),
        )

        # Check the updated parameter has taken effect
        # Spend something and check money is transferred to savings
        # Purchase posting
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=casa_id,
            amount="399.20",
            denomination="GBP",
            instruction_details={"transaction_code": "6000"},
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_all_account_balances(
            accounts_expected_balances={
                casa_id: [(BalanceDimensions(address="DEFAULT", denomination="GBP"), "1000")],
                savings_account_id: [
                    (BalanceDimensions(address="DEFAULT", denomination="GBP"), "0.8")
                ],
            }
        )

        # Check the parameter can be removed to disable autosave
        resp = endtoend.core_api_helper.update_account_instance_parameters(
            casa_id, instance_param_vals={"autosave_savings_account": ""}
        )
        endtoend.accounts_helper.wait_for_account_update(account_update_id=resp["id"])
        casa = endtoend.contracts_helper.get_account(casa_id)
        self.assertEqual(
            "",
            casa["instance_param_vals"]["autosave_savings_account"],
            "Failed to remove the autosave_savings_account instance parameter account "
            "id '{}' resp: '{}'".format(casa_id, resp),
        )

        # check no autosave now parameter is removed
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=casa_id,
            amount="99.73",
            denomination="GBP",
            instruction_details={"transaction_code": "6000"},
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            casa_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "900.27",
                )
            ],
            description="Expected balance after purchase after removing autosave parameter"
            "casa {}, "
            "savings_account {}, ".format(casa_id, savings_account_id),
        )

        # Now need to close the savings account
        wf_context = {"account_id": savings_account_id, "user_id": cust_id}

        wf_id = endtoend.workflows_helper.start_workflow("CASA_CLOSURE", context=wf_context)

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_disbursement_destination",
            event_name="local_transfer_selected",
            context={"target_account_id": casa_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")

        account = endtoend.contracts_helper.get_account(savings_account_id)

        self.assertEqual("ACCOUNT_STATUS_CLOSED", account["status"])

        # Check no autosave happens after savings account is closed
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=casa_id,
            amount="5.50",
            denomination="GBP",
            instruction_details={"transaction_code": "6000"},
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            casa_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "895.57",
                )
            ],
            description="Expected balance after autosave on closed savings account"
            "casa {}, "
            "savings_account {}, ".format(casa_id, savings_account_id),
        )

    def test_casa_opening_autosave_account_choice(self):
        """
        Test that a customer with multiple easy access saver accounts and multiple other
        accounts can link an account and only choose from easy access saver accounts
        """
        cust_id = endtoend.core_api_helper.create_customer()

        savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=eas_instance_params,
            permitted_denominations=["GBP", "USD", "EUR"],
            status="ACCOUNT_STATUS_OPEN",
        )

        savings_account_id = savings_account["id"]

        NUM_OTHER_ACCOUNTS = 3
        for _ in range(NUM_OTHER_ACCOUNTS):
            endtoend.contracts_helper.create_account(
                customer=cust_id,
                contract="current_account",
                instance_param_vals=ca_instance_params,
                permitted_denominations=["GBP", "USD", "EUR"],
                status="ACCOUNT_STATUS_OPEN",
            )

        wf_id = endtoend.workflows_helper.start_workflow(
            "CASA_APPLICATION",
            context={
                "user_id": cust_id,
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_product_id",
            event_name="product_id_selected",
            context={
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["current_account"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_tier",
            event_name="account_tier_selected",
            context={
                "account_tier": endtoend.testhandle.flag_definition_id_mapping["CASA_TIER_UPPER"]
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_daily_atm_limit",
            event_name="chosen_daily_atm_limit",
            context={"chosen_daily_atm_limit": "200"},
        )

        state_id = endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_unarranged_overdraft_limit",
            event_name="chosen_overdraft_limit",
            context={"chosen_unarranged_overdraft_limit": "9000"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_arranged_overdraft_limit",
            event_name="chosen_arranged_overdraft_limit",
            context={"chosen_arranged_overdraft_limit": "100"},
            current_state_id=state_id,
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_autosave_preferences",
            event_name="proceed",
            context={"autosave_account_id": str(savings_account_id)},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "1"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")
        casa_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        casa = endtoend.contracts_helper.get_account(casa_id)
        self.assertEqual(
            str(savings_account_id),
            casa["instance_param_vals"]["autosave_savings_account"],
        )

        # Check the right number of non-easy access saver accounts were excluded
        data = endtoend.workflows_helper.reload_workflow(wf_id)
        self.assertEqual(NUM_OTHER_ACCOUNTS, len(loads(data["global_state"]["exclude_accounts"])))

    def test_casa_opening_autosave_declined(self):
        """
        Test that a customer with an easy access saver account can choose not to enable
        autosave feature
        """
        cust_id = endtoend.core_api_helper.create_customer()

        endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=eas_instance_params,
            permitted_denominations=["GBP", "USD", "EUR"],
            status="ACCOUNT_STATUS_OPEN",
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "CASA_APPLICATION",
            context={
                "user_id": cust_id,
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_product_id",
            event_name="product_id_selected",
            context={
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["current_account"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_tier",
            event_name="account_tier_selected",
            context={
                "account_tier": endtoend.testhandle.flag_definition_id_mapping["CASA_TIER_UPPER"]
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_daily_atm_limit",
            event_name="chosen_daily_atm_limit",
            context={"chosen_daily_atm_limit": "200"},
        )

        state_id = endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_unarranged_overdraft_limit",
            event_name="chosen_overdraft_limit",
            context={"chosen_unarranged_overdraft_limit": "9000"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_arranged_overdraft_limit",
            event_name="chosen_arranged_overdraft_limit",
            context={"chosen_arranged_overdraft_limit": "100"},
            current_state_id=state_id,
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_autosave_preferences",
            event_name="proceed",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "1"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")
        casa_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        casa = endtoend.contracts_helper.get_account(casa_id)
        self.assertEqual("", casa["instance_param_vals"]["autosave_savings_account"])

    def test_casa_application_can_create_eas(self):

        cust_id = endtoend.core_api_helper.create_customer()

        wf_id = endtoend.workflows_helper.start_workflow(
            "CASA_APPLICATION",
            context={
                "user_id": cust_id,
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_product_id",
            event_name="product_id_selected",
            context={
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["easy_access_saver"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_tier",
            event_name="account_tier_selected",
            context={
                "account_tier": endtoend.testhandle.flag_definition_id_mapping["CASA_TIER_MIDDLE"]
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "1"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        eas_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        endtoend.accounts_helper.wait_for_account_update(eas_id, "activation_update")

        eas = endtoend.contracts_helper.get_account(eas_id)

        flag_status = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping["CASA_TIER_MIDDLE"],
            account_ids=[eas_id],
        )
        self.assertEqual(flag_status[0]["account_id"], eas_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", eas["status"])

        self.assertEqual("", eas["instance_param_vals"]["arranged_overdraft_limit"])

        self.assertEqual("", eas["instance_param_vals"]["daily_atm_withdrawal_limit"])

    def test_casa_application_rejects_unsupported_product_id(self):

        cust_id = endtoend.core_api_helper.create_customer()

        wf_id = endtoend.workflows_helper.start_workflow(
            "CASA_APPLICATION",
            context={
                "user_id": cust_id,
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_product_id",
            event_name="product_id_selected",
            context={
                "product_id": "unsupported_contract",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_tier",
            event_name="account_tier_selected",
            context={
                "account_tier": endtoend.testhandle.flag_definition_id_mapping["CASA_TIER_MIDDLE"]
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opening_failed")

    def test_overdraft_facility_pre_posting(self):
        """
        Test that if overdraft parameters are set then a current account accepts a posting
        which results in a negative balance and a savings account will reject the posting.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        eas_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=eas_instance_params,
            permitted_denominations=["GBP"],
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        ca_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=ca_instance_params,
            permitted_denominations=["GBP"],
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        postingID_eas = endtoend.postings_helper.outbound_hard_settlement(
            account_id=eas_id, amount="100", denomination="GBP", instruction_details={}
        )
        postingID_ca = endtoend.postings_helper.outbound_hard_settlement(
            account_id=ca_id, amount="100", denomination="GBP", instruction_details={}
        )

        pib_eas = endtoend.postings_helper.get_posting_batch(postingID_eas)
        pib_ca = endtoend.postings_helper.get_posting_batch(postingID_ca)

        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib_eas["status"])
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_ca["status"])

        endtoend.balances_helper.wait_for_all_account_balances(
            accounts_expected_balances={
                ca_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "-100",
                    )
                ]
            }
        )

    def test_account_rejects_excess_withdrawals_but_accepts_deposit(self):

        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        savings_account_id = account["id"]

        postingID_1 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=savings_account_id, amount="500", denomination="GBP"
        )

        pib_1 = endtoend.postings_helper.get_posting_batch(postingID_1)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_1["status"])

        postingID_2 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=savings_account_id, amount="10", denomination="GBP"
        )

        pib_2 = endtoend.postings_helper.get_posting_batch(postingID_2)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_2["status"])

        postingID_3 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=savings_account_id, amount="10", denomination="GBP"
        )

        pib_3 = endtoend.postings_helper.get_posting_batch(postingID_3)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib_3["status"])

        postingID_4 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=savings_account_id, amount="100", denomination="GBP"
        )

        pib_4 = endtoend.postings_helper.get_posting_batch(postingID_4)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_4["status"])

    def test_account_rejects_excess_withdrawals_in_multiple_transaction_pib(self):

        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver",
            instance_param_vals=eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        savings_account_id = account["id"]

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=savings_account_id, amount="500", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        withdrawal_instruction = OutboundHardSettlement(
            target_account_id=savings_account_id, amount="10", denomination="GBP"
        )

        deposit_instruction = InboundHardSettlement(
            target_account_id=savings_account_id, amount="50", denomination="GBP"
        )

        posting_batch_id_0 = endtoend.postings_helper.send_posting_instruction_batch(
            [withdrawal_instruction, withdrawal_instruction, deposit_instruction]
        )
        pib_0 = endtoend.postings_helper.get_posting_batch(posting_batch_id_0)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib_0["status"])

        posting_batch_id_1 = endtoend.postings_helper.send_posting_instruction_batch(
            [withdrawal_instruction]
        )
        pib_1 = endtoend.postings_helper.get_posting_batch(posting_batch_id_1)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_1["status"])

        posting_batch_id_2 = endtoend.postings_helper.send_posting_instruction_batch(
            [withdrawal_instruction, deposit_instruction]
        )
        pib_2 = endtoend.postings_helper.get_posting_batch(posting_batch_id_2)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib_2["status"])

        posting_batch_id_3 = endtoend.postings_helper.send_posting_instruction_batch(
            [deposit_instruction, deposit_instruction]
        )
        pib_3 = endtoend.postings_helper.get_posting_batch(posting_batch_id_3)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_3["status"])

    def test_account_apply_excess_withdrawal_fee(self):

        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver_allow_excess_withdrawals",
            instance_param_vals=eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        savings_account_id = account["id"]

        postingID_1 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=savings_account_id, amount="500", denomination="GBP"
        )

        pib_1 = endtoend.postings_helper.get_posting_batch(postingID_1)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_1["status"])

        postingID_2 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=savings_account_id, amount="10", denomination="GBP"
        )

        pib_2 = endtoend.postings_helper.get_posting_batch(postingID_2)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_2["status"])

        postingID_3 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=savings_account_id, amount="10", denomination="GBP"
        )

        pib_3 = endtoend.postings_helper.get_posting_batch(postingID_3)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_3["status"])

        postingID_4 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=savings_account_id, amount="50", denomination="GBP"
        )

        pib_4 = endtoend.postings_helper.get_posting_batch(postingID_4)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_4["status"])

        endtoend.balances_helper.wait_for_account_balances(
            savings_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="GBP"), "520")],
        )

    def test_account_apply_excess_withdrawal_fee_multiple_transaction_pib(self):

        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="easy_access_saver_allow_excess_withdrawals",
            instance_param_vals=eas_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        savings_account_id = account["id"]

        postingID_1 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=savings_account_id, amount="500", denomination="GBP"
        )

        pib_1 = endtoend.postings_helper.get_posting_batch(postingID_1)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_1["status"])

        withdrawal_instruction = OutboundHardSettlement(
            target_account_id=savings_account_id, amount="10", denomination="GBP"
        )

        deposit_instruction = InboundHardSettlement(
            target_account_id=savings_account_id, amount="50", denomination="GBP"
        )

        # only one withdrawal in pib exceeded limit
        posting_batch_id = endtoend.postings_helper.send_posting_instruction_batch(
            [withdrawal_instruction, withdrawal_instruction, deposit_instruction]
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_batch_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            savings_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="GBP"), "520")],
        )

        # both withdrawals now in pib exceeded limit
        posting_batch_id = endtoend.postings_helper.send_posting_instruction_batch(
            [withdrawal_instruction, withdrawal_instruction, deposit_instruction]
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_batch_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            savings_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="GBP"), "530")],
        )
