# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import time
import uuid
from datetime import datetime, timezone
from library.time_deposit.tests.e2e.time_deposit_test_params import (
    td_instance_params,
    td_template_params,
    td_template_params_2,
    internal_accounts_tside,
    DUMMY_CONTRA,
)

# third party
from dateutil.relativedelta import relativedelta

# common
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.helper import COMMON_ACCOUNT_SCHEDULE_TAG_PATH

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "time_deposit": {
        "path": "library/time_deposit/contracts/time_deposit.py",
        "template_params": td_template_params,
    },
    "time_deposit_2": {
        "path": "library/time_deposit/contracts/time_deposit.py",
        "template_params": td_template_params_2,
    },
    "dummy_account": {"path": DUMMY_CONTRACT},
}

endtoend.testhandle.CONTRACT_MODULES = {
    "interest": {"path": "library/common/contract_modules/interest.py"},
    "utils": {"path": "library/common/contract_modules/utils.py"},
}

endtoend.testhandle.WORKFLOWS = {
    # time deposit workflows
    "TIME_DEPOSIT_APPLICATION": ("library/time_deposit/workflows/time_deposit_application.yaml"),
    "TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER": (
        "library/time_deposit/workflows/time_deposit_applied_interest_transfer.yaml"
    ),
    "TIME_DEPOSIT_CLOSURE": ("library/time_deposit/workflows/time_deposit_closure.yaml"),
    "TIME_DEPOSIT_INTEREST_PREFERENCE_CHANGE": (
        "library/time_deposit/workflows/time_deposit_interest_preference_change.yaml"
    ),
    "TIME_DEPOSIT_MATURITY": ("library/time_deposit/workflows/time_deposit_maturity.yaml"),
    "TIME_DEPOSIT_ROLLOVER": ("library/time_deposit/workflows/time_deposit_rollover.yaml"),
    "TIME_DEPOSIT_WITHDRAWAL": ("library/time_deposit/workflows/time_deposit_withdrawal.yaml"),
}

endtoend.testhandle.ACCOUNT_SCHEDULE_TAGS = {
    "TIME_DEPOSIT_ACCRUE_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "TIME_DEPOSIT_APPLY_ACCRUED_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "TIME_DEPOSIT_ACCOUNT_MATURITY_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "TIME_DEPOSIT_ACCOUNT_CLOSE_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
}

endtoend.testhandle.CALENDARS = {
    "PUBLIC_HOLIDAYS": ("library/common/calendars/public_holidays.resource.yaml")
}

POSTING_BATCH_ACCEPTED = "POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED"
POSTING_BATCH_REJECTED = "POSTING_INSTRUCTION_BATCH_STATUS_REJECTED"


class TimeDepositAccountTest(endtoend.End2Endtest):
    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at
        # Uncomment this for timing info.
        # print(
        #     "\n{} ({}s)".format(
        #         self.id().rpartition(".")[2], round(self._elapsed_time, 2)
        #     )
        # )

    def test_account_opening_and_maturity_to_time_deposit(self):
        """
        Open account through workflow with maturity to new time deposit, check it
        can receive deposits, run maturity workflow and ensure new account is set
        up with funds.
        """

        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # Apply for time deposit account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_customer_preferences",
            event_name="customer_preferences_given",
            context={
                "interest_application_frequency": "quarterly",
                "term_unit": "months",
                "term": "6",
                "interest_payment_destination": "retain_on_account",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={"maturity_vault_account_id": savings_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_settings_with_interest_application_day",
            event_name="account_settings_captured",
            context={
                "interest_application_day": "1",
                "gross_interest_rate": "0.145",
                "deposit_period": "7",
                "cool_off_period": "0",
                "fee_free_percentage_limit": "0",
                "withdrawal_fee": "0",
                "withdrawal_percentage_fee": "0",
                "account_closure_period": "7",
                "period_end_hour": "0",
                "auto_rollover_type": "no_rollover",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        td_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]

        td_account = endtoend.contracts_helper.get_account(td_account_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", td_account["status"])
        # TD account is open

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="200", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "200",
                )
            ],
        )

        # Close TD account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_MATURITY",
            context={
                "account_id": td_account_id,
                "applied_interest_amount": "0",
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")
        # Original TD account is closed

        # Money has moved to a different account
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                td_account_id: [
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
                        "200",
                    )
                ],
            }
        )

    def test_invalid_deposits(self):
        """
        Tests that postings under minimum_deposit are rejected
        Tests that postings over maximum_balance are rejected
        """
        cust_id = endtoend.core_api_helper.create_customer()

        instance_params = {
            "interest_application_frequency": "quarterly",
            "interest_application_day": "6",
            "gross_interest_rate": "0.145",
            "term_unit": "months",
            "term": "12",
            "deposit_period": "7",
            "account_closure_period": "7",
            "grace_period": "0",
            "cool_off_period": "0",
            "fee_free_percentage_limit": "0",
            "withdrawal_fee": "0",
            "withdrawal_percentage_fee": "0",
            "period_end_hour": "21",
            "auto_rollover_type": "no_rollover",
            "partial_principal_amount": "0",
            "rollover_interest_application_frequency": "quarterly",
            "rollover_interest_application_day": "6",
            "rollover_gross_interest_rate": "0.145",
            "rollover_term_unit": "months",
            "rollover_term": "12",
            "rollover_grace_period": "7",
            "rollover_period_end_hour": "0",
            "rollover_account_closure_period": "7",
        }

        td_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        td_account_id = td_account["id"]

        # Check posting below minimum_first_deposit
        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="49", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_REJECTED, pib["status"])

        # Check posting above maximum_balance
        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="1001", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_REJECTED, pib["status"])
        self.assertEqual(
            endtoend.balances_helper.compare_balances(
                td_account_id,
                [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "0",
                    )
                ],
            ),
            {},
        )

    def test_deposit_period_respected_for_inbound_auth_and_hard_settlement(self):
        """
        Tests that with a deposit period of 0, deposits and inbound auths are rejected
        """
        cust_id = endtoend.core_api_helper.create_customer()

        instance_params = {
            "interest_application_frequency": "quarterly",
            "interest_application_day": "6",
            "gross_interest_rate": "0.145",
            "term_unit": "months",
            "term": "12",
            "deposit_period": "0",
            "cool_off_period": "0",
            "fee_free_percentage_limit": "0",
            "grace_period": "0",
            "withdrawal_fee": "0",
            "withdrawal_percentage_fee": "0",
            "period_end_hour": "0",
            "account_closure_period": "1",
            "auto_rollover_type": "no_rollover",
            "partial_principal_amount": "0",
            "rollover_interest_application_frequency": "quarterly",
            "rollover_interest_application_day": "6",
            "rollover_gross_interest_rate": "0.145",
            "rollover_term_unit": "months",
            "rollover_term": "12",
            "rollover_grace_period": "0",
            "rollover_period_end_hour": "0",
            "rollover_account_closure_period": "1",
        }

        td_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            wait_for_activation=True,
        )

        td_account_id = td_account["id"]

        posting_id_hard_settlement = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="100", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id_hard_settlement)
        self.assertEqual(POSTING_BATCH_REJECTED, pib["status"])

        posting_id_auth = endtoend.postings_helper.inbound_auth(
            account_id=td_account_id, amount="100", denomination="GBP"
        )

        pib_auth = endtoend.postings_helper.get_posting_batch(posting_id_auth)
        self.assertEqual(POSTING_BATCH_REJECTED, pib_auth["status"])

        self.assertEqual(
            endtoend.balances_helper.compare_balances(
                td_account_id,
                [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "0",
                    )
                ],
            ),
            {},
        )

    def test_multiple_deposits_rejected_when_single(self):
        """
        Tests that any deposit after first deposit is rejected
        for accounts with single_deposit set to single
        """
        cust_id = endtoend.core_api_helper.create_customer()

        instance_params = {
            "interest_application_frequency": "quarterly",
            "interest_application_day": "6",
            "gross_interest_rate": "0.145",
            "term_unit": "months",
            "term": "12",
            "deposit_period": "7",
            "grace_period": "0",
            "cool_off_period": "0",
            "fee_free_percentage_limit": "0",
            "withdrawal_fee": "0",
            "withdrawal_percentage_fee": "0",
            "period_end_hour": "0",
            "account_closure_period": "0",
            "auto_rollover_type": "no_rollover",
            "partial_principal_amount": "0",
            "rollover_interest_application_frequency": "quarterly",
            "rollover_interest_application_day": "6",
            "rollover_gross_interest_rate": "0.145",
            "rollover_term_unit": "months",
            "rollover_term": "12",
            "rollover_grace_period": "0",
            "rollover_period_end_hour": "0",
            "rollover_account_closure_period": "0",
        }

        td_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit_2",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        td_account_id = td_account["id"]

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="200", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="200", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_REJECTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "200",
                )
            ],
        )

    def test_change_interest_payment_preference(self):
        """
        With an opened account, tests that interest payment destination can
        be changed from retain_on_account to another Vault account
        """

        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # Create TD account now
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_customer_preferences",
            event_name="customer_preferences_given",
            context={
                "interest_application_frequency": "quarterly",
                "term_unit": "months",
                "term": "6",
                "interest_payment_destination": "retain_on_account",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={"maturity_vault_account_id": savings_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_settings_with_interest_application_day",
            event_name="account_settings_captured",
            context={
                "interest_application_day": "1",
                "gross_interest_rate": "0.145",
                "deposit_period": "7",
                "cool_off_period": "0",
                "fee_free_percentage_limit": "0",
                "withdrawal_fee": "0",
                "withdrawal_percentage_fee": "0",
                "account_closure_period": "7",
                "period_end_hour": "0",
                "auto_rollover_type": "no_rollover",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        td_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]

        td_account = endtoend.contracts_helper.get_account(td_account_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", td_account["status"])
        # End TD account set up

        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_INTEREST_PREFERENCE_CHANGE",
            context={"user_id": cust_id, "account_id": td_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="request_new_interest_destination",
            event_name="new_interest_destination_entered",
            context={"interest_payment_destination": "vault"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account_details",
            event_name="vault_account_captured",
            context={"vault_account_id": savings_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "interest_destination_updated")

        td_account = endtoend.contracts_helper.get_account(td_account_id)

        self.assertEqual("vault", td_account["details"]["interest_payment_destination"])
        self.assertEqual(
            savings_account_id,
            td_account["details"]["interest_vault_account_id"],
        )

    def test_close_workflow_with_unfunded_account(self):
        """
        Tests the close workflow closes an unfunded account
        """

        cust_id = endtoend.core_api_helper.create_customer()

        instance_params = {
            "interest_application_frequency": "quarterly",
            "interest_application_day": "6",
            "gross_interest_rate": "0.145",
            "term_unit": "months",
            "term": "12",
            "deposit_period": "1",
            "grace_period": "0",
            "cool_off_period": "0",
            "fee_free_percentage_limit": "0",
            "withdrawal_fee": "0",
            "withdrawal_percentage_fee": "0",
            "period_end_hour": "0",
            "account_closure_period": "2",
            "auto_rollover_type": "no_rollover",
            "partial_principal_amount": "0",
            "rollover_interest_application_frequency": "quarterly",
            "rollover_interest_application_day": "6",
            "rollover_gross_interest_rate": "0.145",
            "rollover_term_unit": "months",
            "rollover_term": "12",
            "rollover_grace_period": "2",
            "rollover_period_end_hour": "0",
            "rollover_account_closure_period": "2",
        }

        td_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            wait_for_activation=True,
        )

        td_account_id = td_account["id"]

        # Close TD account now
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_CLOSURE", context={"account_id": td_account_id}
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")

    def test_close_workflow_with_funded_account(self):
        """
        Tests the close workflow fails to close a funded account
        """
        cust_id = endtoend.core_api_helper.create_customer()

        instance_params = {
            "interest_application_frequency": "quarterly",
            "interest_application_day": "6",
            "gross_interest_rate": "0.145",
            "term_unit": "months",
            "term": "12",
            "deposit_period": "7",
            "grace_period": "0",
            "cool_off_period": "0",
            "fee_free_percentage_limit": "0",
            "withdrawal_fee": "0",
            "withdrawal_percentage_fee": "0",
            "period_end_hour": "0",
            "account_closure_period": "7",
            "auto_rollover_type": "no_rollover",
            "partial_principal_amount": "0",
            "rollover_interest_application_frequency": "quarterly",
            "rollover_interest_application_day": "6",
            "rollover_gross_interest_rate": "0.145",
            "rollover_term_unit": "months",
            "rollover_term": "12",
            "rollover_grace_period": "7",
            "rollover_period_end_hour": "0",
            "rollover_account_closure_period": "7",
        }

        td_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        td_account_id = td_account["id"]

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="200", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        # Close TD account now
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_CLOSURE", context={"account_id": td_account_id}
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closure_failure")

    def test_interest_transfer_workflow_does_nothing_with_own_account(self):
        """
        Open account through workflow with interest payment retain on account,
        run apply interest workflow and ensure funds dont change.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # Apply for TD account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_customer_preferences",
            event_name="customer_preferences_given",
            context={
                "interest_application_frequency": "quarterly",
                "term_unit": "months",
                "term": "6",
                "interest_payment_destination": "retain_on_account",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={"maturity_vault_account_id": savings_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_settings_with_interest_application_day",
            event_name="account_settings_captured",
            context={
                "interest_application_day": "1",
                "gross_interest_rate": "0.145",
                "deposit_period": "7",
                "cool_off_period": "0",
                "fee_free_percentage_limit": "0",
                "withdrawal_fee": "0",
                "withdrawal_percentage_fee": "0",
                "account_closure_period": "7",
                "period_end_hour": "0",
                "auto_rollover_type": "no_rollover",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        td_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]

        td_account = endtoend.contracts_helper.get_account(td_account_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", td_account["status"])

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="200", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "200",
                )
            ],
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
            context={"account_id": td_account_id, "applied_interest_amount": "100"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "no_transfer_needed")

        self.assertEqual(
            endtoend.balances_helper.compare_balances(
                td_account_id,
                [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "200",
                    )
                ],
            ),
            {},
        )

    def test_interest_transfer_workflow_applies_to_internal_account(self):
        """
        Open account through workflow with interest to internal dummy
        account, run transfer applied interest workflow, ensure interest is moved
        to dummy account
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # Create TD account now
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_customer_preferences",
            event_name="customer_preferences_given",
            context={
                "interest_application_frequency": "quarterly",
                "term_unit": "months",
                "term": "6",
                "interest_payment_destination": "vault",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_vault_account_details",
            event_name="vault_account_captured_interest",
            context={"interest_vault_account_id": savings_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={"maturity_vault_account_id": savings_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_settings_with_interest_application_day",
            event_name="account_settings_captured",
            context={
                "interest_application_day": "1",
                "gross_interest_rate": "0.145",
                "deposit_period": "7",
                "cool_off_period": "0",
                "fee_free_percentage_limit": "0",
                "withdrawal_fee": "0",
                "withdrawal_percentage_fee": "0",
                "account_closure_period": "7",
                "period_end_hour": "0",
                "auto_rollover_type": "no_rollover",
            },
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        td_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]

        td_account = endtoend.contracts_helper.get_account(td_account_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", td_account["status"])
        # End TD account set up

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="200", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "200",
                )
            ],
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
            context={"account_id": td_account_id, "applied_interest_amount": "200"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "interest_applied")

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                td_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "0",
                    ),
                ],
                savings_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "200",
                    )
                ],
            }
        )

    def test_interest_transfer_workflow_doesnt_move_to_bad_account(self):
        """
        Open account through workflow with interest to internal dummy
        account, set this dummy account id to a bad value run transfer
        applied interest workflow, ensure interest is not moved to bad account,
        but stays on TD account.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        bad_account_id = str(uuid.uuid4())
        # Create TD account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_customer_preferences",
            event_name="customer_preferences_given",
            context={
                "interest_application_frequency": "quarterly",
                "term_unit": "months",
                "term": "6",
                "interest_payment_destination": "vault",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_vault_account_details",
            event_name="vault_account_captured_interest",
            context={"interest_vault_account_id": bad_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={"maturity_vault_account_id": bad_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_settings_with_interest_application_day",
            event_name="account_settings_captured",
            context={
                "interest_application_day": "1",
                "gross_interest_rate": "0.145",
                "deposit_period": "7",
                "cool_off_period": "0",
                "fee_free_percentage_limit": "0",
                "withdrawal_fee": "0",
                "withdrawal_percentage_fee": "0",
                "account_closure_period": "7",
                "period_end_hour": "20",
                "auto_rollover_type": "no_rollover",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        td_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]

        td_account = endtoend.contracts_helper.get_account(td_account_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", td_account["status"])
        # End TD account set up

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="200", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "200",
                )
            ],
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
            context={"account_id": td_account_id, "applied_interest_amount": "200"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "transfer_failed")

        self.assertEqual(
            endtoend.balances_helper.compare_balances(
                td_account_id,
                [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "200",
                    )
                ],
            ),
            {},
        )

    def test_withdrawal_to_negative_is_rejected(self):
        """
        Tests that postings that would take the balance below zero are rejected
        even if withdrawal_override is set to true
        """
        cust_id = endtoend.core_api_helper.create_customer()

        instance_params = {
            "interest_application_frequency": "quarterly",
            "interest_application_day": "6",
            "gross_interest_rate": "0.145",
            "term_unit": "months",
            "term": "12",
            "deposit_period": "7",
            "grace_period": "0",
            "cool_off_period": "0",
            "fee_free_percentage_limit": "0",
            "withdrawal_fee": "0",
            "withdrawal_percentage_fee": "0",
            "period_end_hour": "21",
            "account_closure_period": "7",
            "auto_rollover_type": "no_rollover",
            "partial_principal_amount": "0",
            "rollover_interest_application_frequency": "quarterly",
            "rollover_interest_application_day": "6",
            "rollover_gross_interest_rate": "0.145",
            "rollover_term_unit": "months",
            "rollover_term": "12",
            "rollover_grace_period": "7",
            "rollover_period_end_hour": "21",
            "rollover_account_closure_period": "7",
        }

        td_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        td_account_id = td_account["id"]

        # Check posting below doesn't allow negative balance
        postings = []
        postings.append(
            endtoend.postings_helper.create_posting(
                account_id=td_account_id,
                amount="100",
                denomination="GBP",
                asset="COMMERCIAL_BANK_MONEY",
                account_address="DEFAULT",
                phase="POSTING_PHASE_COMMITTED",
                credit=False,
            )
        )
        postings.append(
            endtoend.postings_helper.create_posting(
                account_id=endtoend.testhandle.internal_account_id_to_uploaded_id[DUMMY_CONTRA],
                amount="100",
                denomination="GBP",
                asset="COMMERCIAL_BANK_MONEY",
                account_address="DEFAULT",
                phase="POSTING_PHASE_COMMITTED",
                credit=True,
            )
        )
        # withdrawal_override needed to force the funds out of TD
        # TODO make this use output from KERN-I-26
        postingID = endtoend.postings_helper.create_custom_instruction(
            postings, batch_details={"withdrawal_override": "true"}
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_REJECTED, pib["status"])

    def test_change_interest_preference_to_retain(self):
        """
        Open account through workflow with interest to dummy account,
        run change interest preference workflow to change interest to be retained on
        account, run transfer applied interest workflow, ensure no interest is moved
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # Create TD account now
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_customer_preferences",
            event_name="customer_preferences_given",
            context={
                "interest_application_frequency": "quarterly",
                "term_unit": "months",
                "term": "6",
                "interest_payment_destination": "vault",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_vault_account_details",
            event_name="vault_account_captured_interest",
            context={"interest_vault_account_id": savings_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={"maturity_vault_account_id": savings_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_settings_with_interest_application_day",
            event_name="account_settings_captured",
            context={
                "interest_application_day": "1",
                "gross_interest_rate": "0.145",
                "deposit_period": "7",
                "cool_off_period": "0",
                "fee_free_percentage_limit": "0",
                "withdrawal_fee": "0",
                "withdrawal_percentage_fee": "0",
                "account_closure_period": "7",
                "period_end_hour": "0",
                "auto_rollover_type": "no_rollover",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        td_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]

        td_account = endtoend.contracts_helper.get_account(td_account_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", td_account["status"])
        # End TD account set up

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="200", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "200",
                )
            ],
        )

        # Change interest preference
        change_interest_wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_INTEREST_PREFERENCE_CHANGE",
            context={"account_id": td_account_id, "user_id": cust_id},
        )

        endtoend.workflows_helper.send_event(
            change_interest_wf_id,
            event_state="request_new_interest_destination",
            event_name="new_interest_destination_entered",
            context={"interest_payment_destination": "retain_on_account"},
        )

        endtoend.workflows_helper.wait_for_state(
            change_interest_wf_id, "interest_destination_updated"
        )
        # Interest preference changed

        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
            context={"account_id": td_account_id, "applied_interest_amount": "200"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "no_transfer_needed")

        self.assertEqual(
            endtoend.balances_helper.compare_balances(
                td_account_id,
                [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "200",
                    )
                ],
            ),
            {},
        )

    def test_change_interest_preference_to_vault(self):
        """
        Open account through workflow with interest payment retain on account,
        run change interest preference workflow to change interest preference
        to pay to a vault account, run apply interest workflow and ensure funds
        are transferred to that vault account
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # Apply for TD account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_customer_preferences",
            event_name="customer_preferences_given",
            context={
                "interest_application_frequency": "quarterly",
                "term_unit": "months",
                "term": "6",
                "interest_payment_destination": "retain_on_account",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={"maturity_vault_account_id": savings_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_settings_with_interest_application_day",
            event_name="account_settings_captured",
            context={
                "interest_application_day": "1",
                "gross_interest_rate": "0.145",
                "deposit_period": "7",
                "cool_off_period": "0",
                "fee_free_percentage_limit": "0",
                "withdrawal_fee": "0",
                "withdrawal_percentage_fee": "0",
                "account_closure_period": "7",
                "period_end_hour": "0",
                "auto_rollover_type": "no_rollover",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        td_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]

        td_account = endtoend.contracts_helper.get_account(td_account_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", td_account["status"])

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="200", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        # Posting was successful
        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "200",
                )
            ],
        )

        # Change interest payment preference
        change_interest_wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_INTEREST_PREFERENCE_CHANGE",
            context={"account_id": td_account_id, "user_id": cust_id},
        )

        endtoend.workflows_helper.send_event(
            change_interest_wf_id,
            event_state="request_new_interest_destination",
            event_name="new_interest_destination_entered",
            context={"interest_payment_destination": "vault"},
        )

        endtoend.workflows_helper.send_event(
            change_interest_wf_id,
            event_state="capture_vault_account_details",
            event_name="vault_account_captured",
            context={"vault_account_id": savings_account_id},
        )

        endtoend.workflows_helper.wait_for_state(
            change_interest_wf_id, "interest_destination_updated"
        )
        # Interest preference changed

        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
            context={"account_id": td_account_id, "applied_interest_amount": "200"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "interest_applied")

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                td_account_id: [
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
                        "200",
                    )
                ],
            }
        )

    def test_account_opening_no_interest_application_day(self):
        """
        Open account through workflow without interest application day
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # Apply for time deposit account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_customer_preferences",
            event_name="customer_preferences_given",
            context={
                "interest_application_frequency": "maturity",
                "term_unit": "months",
                "term": "6",
                "interest_payment_destination": "retain_on_account",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={"maturity_vault_account_id": savings_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_settings_without_interest_application_day",
            event_name="account_settings_captured_no_interest_application_day",
            context={
                "gross_interest_rate": "0.145",
                "deposit_period": "7",
                "cool_off_period": "0",
                "fee_free_percentage_limit": "0",
                "withdrawal_fee": "0",
                "withdrawal_percentage_fee": "0",
                "account_closure_period": "7",
                "period_end_hour": "0",
                "auto_rollover_type": "no_rollover",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        td_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]

        td_account = endtoend.contracts_helper.get_account(td_account_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", td_account["status"])

    def test_workflow_withdrawal_does_not_cover_fees(self):
        """
        Test withdrawal workflow does not cover the fees for the amount withdrawn.
        An example being, the user requests a withdrawal of 9 but the fees (flat = 10
        and percentage = 0.90, total = 10.90) exceed the amount which should not be
        allowed.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # create time deposit account
        instance_params = td_instance_params.copy()
        instance_params["grace_period"] = "0"
        instance_params["deposit_period"] = "7"
        instance_params["cool_off_period"] = "0"
        instance_params["fee_free_percentage_limit"] = "0"
        instance_params["withdrawal_fee"] = "10"
        instance_params["withdrawal_percentage_fee"] = "0.9"

        td_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="100", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "100",
                )
            ],
        )

        # perform early withdrawal on the account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_WITHDRAWAL",
            context={
                "account_id": td_account_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_withdrawal_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_withdrawal_parameters",
            event_name="withdrawal_parameters_selected",
            context={"withdrawal_type": "partial", "disbursement_destination": "vault"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_partial_withdrawal_amount",
            event_name="partial_withdrawal_amount_selected",
            context={"requested_withdrawal_amount": "9"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "withdrawal_failed")

    def test_workflow_withdrawal_partial_to_internal_account_without_fees(self):
        """
        Test withdrawal workflow transfers partial amount to a different account
        and does not incur a fee for the amount withdrawn.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # create time deposit account
        instance_params = td_instance_params.copy()
        instance_params["fee_free_percentage_limit"] = "0.5"
        instance_params["withdrawal_fee"] = "10"
        instance_params["withdrawal_percentage_fee"] = "0.3"

        td_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="1000", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "1000",
                )
            ],
        )

        # perform early withdrawal on the account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_WITHDRAWAL",
            context={
                "account_id": td_account_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_withdrawal_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_withdrawal_parameters",
            event_name="withdrawal_parameters_selected",
            context={"withdrawal_type": "partial", "disbursement_destination": "vault"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_partial_withdrawal_amount",
            event_name="partial_withdrawal_amount_selected",
            context={"requested_withdrawal_amount": "100"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account",
            event_name="vault_account_captured",
            context={"disbursement_account_id": savings_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "withdrawal_successful")

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                td_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "900",
                    )
                ],
                savings_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "100",
                    )
                ],
            }
        )

    def test_workflow_withdrawal_partial_to_diff_vault_account_with_flat_fee(self):
        """
        Test withdrawal workflow only incurs a flat fee for the partial amount
        withdrawn.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # create time deposit account
        instance_params = td_instance_params.copy()
        instance_params["grace_period"] = "0"
        instance_params["deposit_period"] = "7"
        instance_params["cool_off_period"] = "0"
        instance_params["fee_free_percentage_limit"] = "0.1"
        instance_params["withdrawal_fee"] = "15"
        instance_params["withdrawal_percentage_fee"] = "0"

        td_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="1000", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "1000",
                )
            ],
        )

        # perform early withdrawal on the account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_WITHDRAWAL",
            context={
                "account_id": td_account_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_withdrawal_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_withdrawal_parameters",
            event_name="withdrawal_parameters_selected",
            context={"withdrawal_type": "partial", "disbursement_destination": "vault"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_partial_withdrawal_amount",
            event_name="partial_withdrawal_amount_selected",
            context={"requested_withdrawal_amount": "200"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account",
            event_name="vault_account_captured",
            context={"disbursement_account_id": savings_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "withdrawal_successful")

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                td_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "800",
                    )
                ],
                savings_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "185",
                    )
                ],
            }
        )

    def test_workflow_withdrawal_partial_to_internal_account_with_flat_fee_in_period(
        self,
    ):
        """
        Test withdrawal workflow doesn't incurs a flat fee for the partial amount
        withdrawn if its in grace period.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # create time deposit account
        instance_params = td_instance_params.copy()
        instance_params["grace_period"] = "15"
        instance_params["deposit_period"] = "0"
        instance_params["cool_off_period"] = "0"
        instance_params["fee_free_percentage_limit"] = "0.1"
        instance_params["withdrawal_fee"] = "15"
        instance_params["withdrawal_percentage_fee"] = "0"

        td_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="1000", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "1000",
                )
            ],
        )

        # perform early withdrawal on the account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_WITHDRAWAL",
            context={
                "account_id": td_account_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_withdrawal_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_withdrawal_parameters",
            event_name="withdrawal_parameters_selected",
            context={"withdrawal_type": "partial", "disbursement_destination": "vault"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_partial_withdrawal_amount",
            event_name="partial_withdrawal_amount_selected",
            context={"requested_withdrawal_amount": "200"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account",
            event_name="vault_account_captured",
            context={"disbursement_account_id": savings_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "withdrawal_successful")

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                td_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "800",
                    )
                ],
                savings_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "200",
                    )
                ],
            }
        )

    def test_workflow_withdrawal_partial_to_int_account_with_percentage_fee_in_period(
        self,
    ):
        """
        Test withdrawal workflow doesn't incurs a percentage fee for the
        partial amount withdrawn if its in cool off period.
        """

        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # create time deposit account
        instance_params = td_instance_params.copy()
        instance_params["grace_period"] = "0"
        instance_params["deposit_period"] = "7"
        instance_params["cool_off_period"] = "15"
        instance_params["fee_free_percentage_limit"] = "0"
        instance_params["withdrawal_fee"] = "0"
        instance_params["withdrawal_percentage_fee"] = "0.2"

        td_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="1000", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "1000",
                )
            ],
        )

        # perform early withdrawal on the account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_WITHDRAWAL",
            context={
                "account_id": td_account_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_withdrawal_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_withdrawal_parameters",
            event_name="withdrawal_parameters_selected",
            context={"withdrawal_type": "partial", "disbursement_destination": "vault"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_partial_withdrawal_amount",
            event_name="partial_withdrawal_amount_selected",
            context={"requested_withdrawal_amount": "200"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account",
            event_name="vault_account_captured",
            context={"disbursement_account_id": savings_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "withdrawal_successful")

        # No fees
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                savings_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "200",
                    )
                ],
                td_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "800",
                    )
                ],
            }
        )

    def test_workflow_withdrawal_partial_to_internal_account_with_percentage_fee(self):
        """
        Test withdrawal workflow only incurs a percentage fee for the partial amount
        withdrawn.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # create time deposit account
        instance_params = td_instance_params.copy()
        instance_params["grace_period"] = "0"
        instance_params["deposit_period"] = "7"
        instance_params["cool_off_period"] = "0"
        instance_params["fee_free_percentage_limit"] = "0"
        instance_params["withdrawal_fee"] = "0"
        instance_params["withdrawal_percentage_fee"] = "0.2"

        td_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="1000", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "1000",
                )
            ],
        )

        # perform early withdrawal on the account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_WITHDRAWAL",
            context={
                "account_id": td_account_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_withdrawal_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_withdrawal_parameters",
            event_name="withdrawal_parameters_selected",
            context={"withdrawal_type": "partial", "disbursement_destination": "vault"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_partial_withdrawal_amount",
            event_name="partial_withdrawal_amount_selected",
            context={"requested_withdrawal_amount": "200"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account",
            event_name="vault_account_captured",
            context={"disbursement_account_id": savings_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "withdrawal_successful")

        # 20% of 200 = 40
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                savings_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "160",
                    )
                ],
                td_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "800",
                    )
                ],
            }
        )

    def test_workflow_withdrawal_partial_to_int_account_with_flat_and_percentage_fee(
        self,
    ):
        """
        Test withdrawal workflow incurs both a flat and percentage fee for the amount
        withdrawn.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # create time deposit account
        instance_params = td_instance_params.copy()
        instance_params["grace_period"] = "0"
        instance_params["deposit_period"] = "7"
        instance_params["cool_off_period"] = "0"
        instance_params["fee_free_percentage_limit"] = "0"
        instance_params["withdrawal_fee"] = "10"
        instance_params["withdrawal_percentage_fee"] = "0.2"

        td_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="1000", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "1000",
                )
            ],
        )

        # perform early withdrawal on the account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_WITHDRAWAL",
            context={
                "account_id": td_account_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_withdrawal_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_withdrawal_parameters",
            event_name="withdrawal_parameters_selected",
            context={"withdrawal_type": "partial", "disbursement_destination": "vault"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_partial_withdrawal_amount",
            event_name="partial_withdrawal_amount_selected",
            context={"requested_withdrawal_amount": "200"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account",
            event_name="vault_account_captured",
            context={"disbursement_account_id": savings_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "withdrawal_successful")

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                td_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "800",
                    )
                ],
                # 200 * 0.2 + 10 = 40 + 10 = 50
                savings_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "150",
                    )
                ],
            }
        )

    def test_workflow_withdrawal_full_with_flat_and_percentage_fee_applied(self):
        """
        Test withdrawal workflow for the full amount, and incurs both a flat and
        percentage fee for the amount withdrawn. The account should be closed as
        there are no more funds.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        # create time deposit account
        instance_params = td_instance_params.copy()
        instance_params["grace_period"] = "0"
        instance_params["deposit_period"] = "7"
        instance_params["cool_off_period"] = "0"
        instance_params["fee_free_percentage_limit"] = "0"
        instance_params["withdrawal_fee"] = "10"
        instance_params["withdrawal_percentage_fee"] = "0.2"

        td_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id, amount="1000", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "1000",
                )
            ],
        )

        # perform early withdrawal on the account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_WITHDRAWAL",
            context={
                "account_id": td_account_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_withdrawal_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_withdrawal_parameters",
            event_name="withdrawal_parameters_selected",
            context={"withdrawal_type": "full", "disbursement_destination": "vault"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account",
            event_name="vault_account_captured",
            context={"disbursement_account_id": savings_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "withdrawal_successful")

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                td_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "0",
                    )
                ],
                # 1000 * 20% + 10 = 210
                savings_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "790",
                    )
                ],
            }
        )

        endtoend.accounts_helper.wait_for_account_update(
            account_id=td_account_id, account_update_type="closure_update"
        )

    def test_withdrawal_on_holiday(self):
        """
        test withdrawal during holiday
        """
        create_calendar_event_date = datetime.now().astimezone(timezone.utc) - relativedelta(
            months=1
        )
        check_calendar_from_date = create_calendar_event_date
        check_calendar_to_date = create_calendar_event_date + relativedelta(minutes=1)
        calendar_event_from = datetime(
            create_calendar_event_date.year,
            create_calendar_event_date.month,
            create_calendar_event_date.day,
            0,
            0,
            1,
        ).astimezone(timezone.utc)
        calendar_event_to = datetime(
            create_calendar_event_date.year,
            create_calendar_event_date.month,
            create_calendar_event_date.day,
            23,
            59,
            59,
        ).astimezone(timezone.utc)
        calender_event = endtoend.core_api_helper.get_calendar_events(
            calendar_ids=endtoend.testhandle.calendar_ids_to_e2e_ids["PUBLIC_HOLIDAYS"],
            calendar_timestamp_from=check_calendar_from_date,
            calendar_timestamp_to=check_calendar_to_date,
        )
        if not calender_event:
            calendar_event_id = "E2E_TEST_EVENT_" + uuid.uuid4().hex
            endtoend.core_api_helper.create_calendar_event(
                event_id=calendar_event_id,
                calendar_id=endtoend.testhandle.calendar_ids_to_e2e_ids["PUBLIC_HOLIDAYS"],
                name="E2E TEST EVENT",
                is_active=True,
                start_timestamp=calendar_event_from,
                end_timestamp=calendar_event_to,
            )

        cust_id = endtoend.core_api_helper.create_customer()
        instance_params = td_instance_params.copy()

        td_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        td_account_id = td_account["id"]

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id,
            amount="200",
            denomination="GBP",
            value_datetime=create_calendar_event_date,
        )

        endtoend.postings_helper.outbound_hard_settlement(
            account_id=td_account_id,
            amount="200",
            denomination="GBP",
            value_datetime=create_calendar_event_date,
            batch_details={"withdrawal_override": "true"},
        )

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "200",
                )
            ],
        )

        endtoend.postings_helper.outbound_hard_settlement(
            account_id=td_account_id,
            amount="200",
            denomination="GBP",
            value_datetime=create_calendar_event_date,
            batch_details={"withdrawal_override": "true", "calendar_override": "true"},
        )

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "0",
                )
            ],
        )


if __name__ == "__main__":
    endtoend.runtests()
