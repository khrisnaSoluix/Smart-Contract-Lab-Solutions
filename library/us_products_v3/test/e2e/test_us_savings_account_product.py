# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta

# library
import library.us_products_v3.constants.files as files
from library.us_products_v3.test.e2e.us_products_test_params import (
    APPLICATION_WORKFLOW_FLAG_DEFINITIONS,
    DEFAULT_SAVINGS_CONTRACT,
    US_SAVINGS_FLAG_DEFINITIONS,
    internal_accounts_tside,
    us_savings_account_template_params,
    us_savings_account_template_params_allow_excess_withdrawals,
)

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions
from inception_sdk.test_framework.endtoend.contracts_helper import ContractNotificationResourceType
from inception_sdk.vault.postings.posting_classes import (
    InboundHardSettlement,
    OutboundHardSettlement,
)

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    **DEFAULT_SAVINGS_CONTRACT,
    "us_savings_account_allow_excess_withdrawals": {
        "path": files.US_SAVINGS_TEMPLATE,
        "template_params": us_savings_account_template_params_allow_excess_withdrawals,
    },
}
endtoend.testhandle.CONTRACT_MODULES = {
    "interest": {"path": "library/common/contract_modules/interest.py"},
    "utils": {"path": "library/common/contract_modules/utils.py"},
}

endtoend.testhandle.WORKFLOWS = {
    "US_SAVINGS_ACCOUNT_APPLICATION": (
        "library/us_products_v3/workflows/us_savings_account_application.yaml"
    ),
    "US_PRODUCTS_CLOSURE": "library/us_products_v3/workflows/us_products_closure.yaml",
    "US_SAVINGS_ACCOUNT_INTEREST_APPLICATION_DAY_CHANGE": (
        "library/us_products_v3/workflows/us_savings_account_interest_application_day_change.yaml"
    ),
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    **APPLICATION_WORKFLOW_FLAG_DEFINITIONS,
    **US_SAVINGS_FLAG_DEFINITIONS,
}


class SavingsAccountTest(endtoend.End2Endtest):
    def test_workflow_apply_for_us_savings_account(self):

        cust_id = endtoend.core_api_helper.create_customer()

        wf_id = endtoend.workflows_helper.start_workflow(
            "US_SAVINGS_ACCOUNT_APPLICATION", context={"user_id": cust_id}
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_tier",
            event_name="account_tier_selected",
            context={"account_tier": endtoend.testhandle.flag_definition_id_mapping["UPPER_TIER"]},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_application_preferences",
            event_name="interest_application_day_provided",
            context={"interest_application_day": "9"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        us_savings_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]

        us_savings_account = endtoend.contracts_helper.get_account(us_savings_account_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", us_savings_account["status"])

        endtoend.accounts_helper.wait_for_account_update(
            account_id=us_savings_account_id, account_update_type="activation_update"
        )

        interest_application_day = us_savings_account["instance_param_vals"][
            "interest_application_day"
        ]

        self.assertEqual(interest_application_day, "9")

        flag_status = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping["UPPER_TIER"],
            account_ids=[us_savings_account["id"]],
        )
        self.assertEqual(flag_status[0]["account_id"], us_savings_account["id"])

        creation_date_savings = datetime.strptime(
            us_savings_account["opening_timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )

        account_schedules = endtoend.schedule_helper.get_account_schedules(us_savings_account["id"])

        accrue_interest_schedule_time = datetime.strptime(
            account_schedules["ACCRUE_INTEREST"]["next_run_timestamp"],
            "%Y-%m-%dT%H:%M:%SZ",
        )
        self.assertEqual(0, accrue_interest_schedule_time.hour)
        self.assertEqual(0, accrue_interest_schedule_time.minute)
        self.assertEqual(0, accrue_interest_schedule_time.second)

        apply_accrue_interest_schedule_time = datetime.strptime(
            account_schedules["APPLY_ACCRUED_INTEREST"]["next_run_timestamp"],
            "%Y-%m-%dT%H:%M:%SZ",
        )
        self.assertEqual(int(interest_application_day), apply_accrue_interest_schedule_time.day)
        self.assertEqual(0, apply_accrue_interest_schedule_time.hour)
        self.assertEqual(0, apply_accrue_interest_schedule_time.minute)
        self.assertEqual(0, apply_accrue_interest_schedule_time.second)

        fees_application_day = int(us_savings_account_template_params["fees_application_day"])
        fees_application_hour = int(us_savings_account_template_params["fees_application_hour"])
        fees_application_minute = int(us_savings_account_template_params["fees_application_minute"])
        fees_application_second = int(us_savings_account_template_params["fees_application_second"])
        apply_monthly_fees_expected_next_run_time = creation_date_savings.replace(
            day=fees_application_day,
            hour=fees_application_hour,
            minute=fees_application_minute,
            second=fees_application_second,
        )
        apply_monthly_fees_expected_next_run_time += relativedelta(months=1)

        if apply_monthly_fees_expected_next_run_time <= creation_date_savings + relativedelta(
            months=1
        ):
            apply_monthly_fees_expected_next_run_time += relativedelta(months=1)
        self.assertEqual(
            apply_monthly_fees_expected_next_run_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["APPLY_MONTHLY_FEES"]["next_run_timestamp"],
        )

    def test_account_rejects_large_deposit(self):

        cust_id = endtoend.core_api_helper.create_customer()

        instance_params = {"interest_application_day": "6"}

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account_v3",
            permitted_denominations=["USD"],
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id = account["id"]

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=us_savings_account_id, amount="6000", denomination="USD"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=us_savings_account_id, amount="200", denomination="USD"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

    def test_account_rejects_excess_withdrawals_but_accepts_deposit(self):

        cust_id = endtoend.core_api_helper.create_customer()

        instance_params = {"interest_application_day": "6"}

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account_v3",
            permitted_denominations=["USD"],
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id = account["id"]

        postingID_1 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=us_savings_account_id, amount="500", denomination="USD"
        )

        pib_1 = endtoend.postings_helper.get_posting_batch(postingID_1)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_1["status"])

        postingID_2 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=us_savings_account_id, amount="10", denomination="USD"
        )

        pib_2 = endtoend.postings_helper.get_posting_batch(postingID_2)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_2["status"])

        postingID_3 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=us_savings_account_id, amount="10", denomination="USD"
        )

        pib_3 = endtoend.postings_helper.get_posting_batch(postingID_3)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib_3["status"])

        postingID_4 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=us_savings_account_id, amount="100", denomination="USD"
        )

        pib_4 = endtoend.postings_helper.get_posting_batch(postingID_4)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_4["status"])

    def test_account_rejects_excess_withdrawals_in_multiple_transaction_pib(self):

        cust_id = endtoend.core_api_helper.create_customer()

        instance_params = {"interest_application_day": "6"}

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account_v3",
            permitted_denominations=["USD"],
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id = account["id"]

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=us_savings_account_id, amount="500", denomination="USD"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            us_savings_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="USD"), "500")],
        )

        withdrawal_instruction = OutboundHardSettlement(
            target_account_id=us_savings_account_id, amount="10", denomination="USD"
        )

        deposit_instruction = InboundHardSettlement(
            target_account_id=us_savings_account_id, amount="50", denomination="USD"
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

        endtoend.balances_helper.wait_for_account_balances(
            us_savings_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="USD"), "490")],
        )

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

    @endtoend.kafka_helper.kafka_only_test
    def test_account_apply_excess_withdrawal_fee(self):

        cust_id = endtoend.core_api_helper.create_customer()

        instance_params = {"interest_application_day": "6"}

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account_allow_excess_withdrawals",
            permitted_denominations=["USD"],
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id = account["id"]

        # Initial deposit
        postingID_1 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=us_savings_account_id, amount="500", denomination="USD"
        )

        pib_1 = endtoend.postings_helper.get_posting_batch(postingID_1)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_1["status"])

        # First withdrawal meets monthly withdrawal limit, triggering workflow
        postingID_2 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=us_savings_account_id, amount="10", denomination="USD"
        )

        pib_2 = endtoend.postings_helper.get_posting_batch(postingID_2)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_2["status"])

        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type="US_PRODUCTS_TRANSACTION_LIMIT_WARNING",
            notification_details={
                "account_id": us_savings_account_id,
                "limit": "1",
                "limit_type": "Monthly Withdrawal Limit",
                "message": "Warning: Reached monthly withdrawal transaction limit, charges will be "
                "applied for the next withdrawal.",
                "value": "1",
            },
            resource_id=us_savings_account_id,
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        # Second withdrawal exceeds monthly withdrawal limit, triggering fee
        postingID_3 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=us_savings_account_id, amount="10", denomination="USD"
        )

        pib_3 = endtoend.postings_helper.get_posting_batch(postingID_3)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_3["status"])

        # Second deposit
        postingID_4 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=us_savings_account_id, amount="50", denomination="USD"
        )

        pib_4 = endtoend.postings_helper.get_posting_batch(postingID_4)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_4["status"])

        # Initial 500 deposit + 50 second deposit - 2*10 withdrawals - 10 withdrawal fees
        endtoend.balances_helper.wait_for_account_balances(
            us_savings_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="USD"), "520")],
        )

    def test_account_apply_excess_withdrawal_fee_multiple_transaction_pib(self):

        cust_id = endtoend.core_api_helper.create_customer()

        instance_params = {"interest_application_day": "6"}

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account_allow_excess_withdrawals",
            permitted_denominations=["USD"],
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id = account["id"]

        postingID_1 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=us_savings_account_id, amount="500", denomination="USD"
        )

        pib_1 = endtoend.postings_helper.get_posting_batch(postingID_1)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_1["status"])

        withdrawal_instruction = OutboundHardSettlement(
            target_account_id=us_savings_account_id, amount="10", denomination="USD"
        )

        deposit_instruction = InboundHardSettlement(
            target_account_id=us_savings_account_id, amount="50", denomination="USD"
        )

        # only one withdrawal in pib exceeded limit
        posting_batch_id = endtoend.postings_helper.send_posting_instruction_batch(
            [withdrawal_instruction, withdrawal_instruction, deposit_instruction]
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_batch_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            us_savings_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="USD"), "520")],
        )

        # both withdrawals now in pib exceeded limit
        posting_batch_id = endtoend.postings_helper.send_posting_instruction_batch(
            [withdrawal_instruction, withdrawal_instruction, deposit_instruction]
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_batch_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            us_savings_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="USD"), "530")],
        )

    def test_workflow_close_us_account_no_plan_account(self):
        """
        Close a US savings account which is not associated to a plan
        """
        cust_id = endtoend.core_api_helper.create_customer()

        savings_instance_params = {"interest_application_day": "1"}

        us_savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account_v3",
            instance_param_vals=savings_instance_params,
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

        closed_savings_account = endtoend.contracts_helper.get_account(us_savings_account_id)

        self.assertTrue(closed_savings_account["status"] == "ACCOUNT_STATUS_CLOSED")

    def test_workflow_change_interest_application_day(self):
        """
        Test that changing the interest_application day using the workflow produces
        expected results
        """
        cust_id = endtoend.core_api_helper.create_customer()

        us_savings_instance_params = {"interest_application_day": "6"}

        us_savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="us_savings_account_v3",
            instance_param_vals=us_savings_instance_params,
            permitted_denominations=["USD"],
            status="ACCOUNT_STATUS_OPEN",
        )
        us_savings_account_id = us_savings_account["id"]

        self.assertEqual("6", us_savings_account["instance_param_vals"]["interest_application_day"])

        change_interest_application_date_wf_id = endtoend.workflows_helper.start_workflow(
            "US_SAVINGS_ACCOUNT_INTEREST_APPLICATION_DAY_CHANGE",
            context={"user_id": cust_id, "account_id": us_savings_account_id},
        )

        # Try to set the same interest application day as existing, which should be rejected
        endtoend.workflows_helper.send_event(
            change_interest_application_date_wf_id,
            event_state="change_interest_application_day",
            event_name="interest_application_day_given",
            context={"new_interest_application_day": "6"},
        )

        endtoend.workflows_helper.send_event(
            change_interest_application_date_wf_id,
            event_state="retry_change_interest_application_day",
            event_name="retry_change_interest_application_day",
            context={},
        )

        endtoend.workflows_helper.send_event(
            change_interest_application_date_wf_id,
            event_state="change_interest_application_day",
            event_name="interest_application_day_given",
            context={"new_interest_application_day": "31"},
        )

        endtoend.workflows_helper.wait_for_state(
            change_interest_application_date_wf_id,
            "account_instance_parameters_update_success",
        )

        endtoend.accounts_helper.wait_for_account_update(
            us_savings_account_id, "instance_param_vals_update"
        )

        us_savings_account = endtoend.contracts_helper.get_account(us_savings_account_id)

        self.assertEqual(
            "31", us_savings_account["instance_param_vals"]["interest_application_day"]
        )


if __name__ == "__main__":
    endtoend.runtests()
