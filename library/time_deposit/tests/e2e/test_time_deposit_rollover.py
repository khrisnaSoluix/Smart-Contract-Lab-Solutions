# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import time

# third party
from typing import Any, Dict
import inception_sdk.test_framework.endtoend as endtoend
from library.time_deposit.tests.e2e.time_deposit_test_params import (
    td_template_params,
    instance_params_with_grace_period,
    instance_params_without_grace_and_cool_off_period,
    instance_params_with_cool_off_period,
    internal_accounts_tside,
)
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
from inception_sdk.test_framework.endtoend.helper import COMMON_ACCOUNT_SCHEDULE_TAG_PATH

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "time_deposit": {
        "path": "library/time_deposit/contracts/time_deposit.py",
        "template_params": td_template_params,
    },
    "dummy_account": {
        "path": DUMMY_CONTRACT,
    },
}

endtoend.testhandle.CONTRACT_MODULES = {
    "interest": {"path": "library/common/contract_modules/interest.py"},
    "utils": {"path": "library/common/contract_modules/utils.py"},
}

endtoend.testhandle.WORKFLOWS = {
    # time deposit workflows
    "TIME_DEPOSIT_ACCOUNT_INFORMATION_UPDATE": (
        "library/time_deposit/workflows/time_deposit_account_information_update.yaml"
    ),
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

endtoend.testhandle.CALENDARS = {
    "PUBLIC_HOLIDAYS": ("library/common/calendars/public_holidays.resource.yaml")
}

endtoend.testhandle.ACCOUNT_SCHEDULE_TAGS = {
    "TIME_DEPOSIT_ACCRUE_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "TIME_DEPOSIT_APPLY_ACCRUED_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "TIME_DEPOSIT_ACCOUNT_MATURITY_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "TIME_DEPOSIT_ACCOUNT_CLOSE_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
}
POSTING_BATCH_ACCEPTED = "POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED"


class TimeDepositAccountTest(endtoend.End2Endtest):
    def setUp(self):
        self.cust_id = endtoend.core_api_helper.create_customer()
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at
        # Uncomment this for timing info.
        # print(
        #     "\n{} ({}s)".format(
        #         self.id().rpartition(".")[2], round(self._elapsed_time, 2)
        #     )
        # )

    def _create_td_param_account_details(
        self,
        cust_id: str,
    ) -> Dict[str, str]:
        """
        Creates a dummy account details that will be used for dummy TD creation for testing.
        :param cust_id: Customer id to link the account.
        :return: Account details that can be used for creation of dummy TD.
        """
        # create dummy account for disbursement
        savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        return {
            "maturity_vault_account_id": savings_account,
            "interest_payment_destination": "retain_on_account",
        }

    def _create_time_deposit_account(
        self, instance_params: Dict[str, str], cust_id: str, details=None
    ) -> Dict[str, Any]:
        """
        Creates a dummy time deposit account for testing.
        :param instance_params: TD instance params to be use in creating dummy account.
        :param cust_id: Customer id to link the account.
        :param details: Details to be use in creation of the account.
        :return: Created dummy TD account base on the params given.
        """
        details = details or self._create_td_param_account_details(cust_id)
        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            details=details,
        )
        return account

    def test_rollover_time_deposit_with_principal_and_interest_amount(self):
        """
        Testing on rollover time deposit with auto_rollover_type set as
        principal_and_interest and there is no interest in the account
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
                "grace_period": "0",
                "cool_off_period": "1",
                "period_end_hour": "21",
                "account_closure_period": "7",
                "auto_rollover_type": "principal_and_interest",
                "fee_free_percentage_limit": "0",
                "withdrawal_fee": "10",
                "withdrawal_percentage_fee": "0",
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

        # Close TD account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_MATURITY",
            context={
                "account_id": td_account_id,
                "applied_interest_amount": "0",
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        cwf_id = endtoend.workflows_helper.get_child_workflow_id(wf_id, "rollover_time_deposit")

        endtoend.workflows_helper.wait_for_state(cwf_id, "account_opened_successfully")

        context = endtoend.workflows_helper.get_state_local_context(
            cwf_id, "account_opened_successfully"
        )
        rollover_td_account = endtoend.contracts_helper.get_account(context["id"])
        self.assertEqual("ACCOUNT_STATUS_OPEN", rollover_td_account["status"])
        # Maturity TD account is open

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")
        # Original TD account is closed

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
                # Money has moved to new TD account
                rollover_td_account["id"]: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "200",
                    )
                ],
            }
        )

    def test_rollover_time_deposit_with_partial_principal_amount(self):
        """
        Testing on rollover time deposit with auto_rollover_type set as
        partial_principal
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # Create dummy account for disbursement
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
                "grace_period": "0",
                "cool_off_period": "1",
                "period_end_hour": "21",
                "account_closure_period": "7",
                "auto_rollover_type": "partial_principal",
                "fee_free_percentage_limit": "0",
                "withdrawal_fee": "10",
                "withdrawal_percentage_fee": "0",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_partial_principal_amount_settings",
            event_name="capture_partial_principal_amount",
            context={"partial_principal_amount": "100"},
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
                "applied_interest_amount": "0.5",
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        cwf_id = endtoend.workflows_helper.get_child_workflow_id(wf_id, "rollover_time_deposit")

        endtoend.workflows_helper.wait_for_state(cwf_id, "account_opened_successfully")
        context = endtoend.workflows_helper.get_state_local_context(
            cwf_id, "account_opened_successfully"
        )
        rollover_td_account = endtoend.contracts_helper.get_account(context["id"])
        self.assertEqual("ACCOUNT_STATUS_OPEN", rollover_td_account["status"])
        # Maturity TD account is open

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")
        # Original TD account is closed

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
                # Money has moved to new TD account
                rollover_td_account.get("id"): [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "100",
                    )
                ],
                # Money has moved to stated internal account
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

    def test_update_account_no_roll_over_no_grace_and_cool_off_period(self):
        """
        Update account information via WF if update is for no roll over not on
        cool off period and grace period also checks if vault path is working for
         interest and maturity destination
        """
        td_account_without_grace_and_cool_off_period = self._create_time_deposit_account(
            instance_params_without_grace_and_cool_off_period, self.cust_id
        )

        account_id = td_account_without_grace_and_cool_off_period["id"]
        time_deposit_account = endtoend.contracts_helper.get_account(account_id)

        expected_dict = {
            "interest_vault_account_id": time_deposit_account["id"],
            "maturity_vault_account_id": time_deposit_account["id"],
            "account_closure_period": "7",
            "auto_rollover_type": "no_rollover",
            "cool_off_period": "0",
            "deposit_period": "0",
            "fee_free_percentage_limit": "0",
            "grace_period": "0",
            "gross_interest_rate": "0.145",
            "interest_application_day": "6",
            "interest_application_frequency": "quarterly",
            "partial_principal_amount": "0",
            "period_end_hour": "21",
            "rollover_account_closure_period": "7",
            "rollover_grace_period": "0",
            "rollover_gross_interest_rate": "0.145",
            "rollover_interest_application_day": "6",
            "rollover_interest_application_frequency": "quarterly",
            "rollover_period_end_hour": "21",
            "rollover_term": "12",
            "rollover_term_unit": "months",
            "term": "12",
            "term_unit": "months",
            "withdrawal_fee": "10",
            "withdrawal_percentage_fee": "0",
            "interest_payment_destination": "vault",
        }

        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_ACCOUNT_INFORMATION_UPDATE",
            context={"user_id": self.cust_id, "account_id": account_id},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_customer_preferences",
            event_name="customer_rollover_preferences_given",
            context={"auto_rollover_type": "no_rollover"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_payment_destination_at_maturity",
            event_name="customer_no_rollover_preferences_given",
            context={
                "interest_payment_destination": "vault",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_vault_account_details",
            event_name="vault_account_captured_interest",
            context={"interest_vault_account_id": time_deposit_account["id"]},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={"maturity_vault_account_id": time_deposit_account["id"]},
        )

        # Account is updated if no errors were raised
        endtoend.workflows_helper.wait_for_state(wf_id, "account_rollover_update_succeded")
        account = endtoend.contracts_helper.get_account(account_id)
        current_dict = {**account["instance_param_vals"], **account["details"]}
        self.assertDictEqual(expected_dict, current_dict)

    def test_update_with_principal_with_app_day_no_grace_and_cool_off_period(
        self,
    ):
        """
        Update account information via WF if there is a roll over but with
        partial principal & interest application day not on cool off period and
        grace period also checks if interest destination retain on account
        is working.
        """
        td_account_without_grace_and_cool_off_period = self._create_time_deposit_account(
            instance_params_without_grace_and_cool_off_period,
            self.cust_id,
        )

        account_id = td_account_without_grace_and_cool_off_period["id"]
        expected_dict = {
            "account_closure_period": "7",
            "auto_rollover_type": "no_rollover",
            "cool_off_period": "0",
            "deposit_period": "0",
            "fee_free_percentage_limit": "0",
            "grace_period": "0",
            "gross_interest_rate": "0.145",
            "interest_application_day": "6",
            "interest_application_frequency": "quarterly",
            "partial_principal_amount": "456",
            "period_end_hour": "21",
            "rollover_account_closure_period": "19",
            "rollover_grace_period": "0",
            "rollover_gross_interest_rate": "0.89",
            "rollover_interest_application_day": "3",
            "rollover_interest_application_frequency": "monthly",
            "rollover_period_end_hour": "15",
            "rollover_term": "12",
            "rollover_term_unit": "months",
            "term": "12",
            "term_unit": "months",
            "withdrawal_fee": "10",
            "withdrawal_percentage_fee": "0",
            "interest_payment_destination": "retain_on_account",
            "maturity_vault_account_id": td_account_without_grace_and_cool_off_period["details"][
                "maturity_vault_account_id"
            ],
        }

        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_ACCOUNT_INFORMATION_UPDATE",
            context={"user_id": self.cust_id, "account_id": account_id},
        )

        expected_dict_temp = {"auto_rollover_type": "partial_principal"}
        expected_dict.update(expected_dict_temp)
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_customer_preferences",
            event_name="customer_rollover_preferences_given",
            context=expected_dict_temp,
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_details_with_partial_principal",
            event_name="capture_rollover_details_with_partial_principal_given",
            context={
                "partial_principal_amount": "456",
                "rollover_gross_interest_rate": "89",
                "rollover_grace_period": "0",
                "rollover_account_closure_period": "19",
                "rollover_period_end_hour": "15",
                "rollover_interest_application_frequency": "monthly",
                "interest_payment_destination": "retain_on_account",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={
                "maturity_vault_account_id": td_account_without_grace_and_cool_off_period[
                    "details"
                ]["maturity_vault_account_id"]
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_settings_with_interest_application_day",
            event_name="account_settings_captured_with_interest_application_day",
            context={"rollover_interest_application_day": "3"},
        )

        # Account is updated if no errors were raised
        endtoend.workflows_helper.wait_for_state(wf_id, "account_rollover_update_succeded")

        account = endtoend.contracts_helper.get_account(account_id)
        current_dict = {**account["instance_param_vals"], **account["details"]}
        self.assertDictEqual(expected_dict, current_dict)

    def test_update_account_with_principal_with_app_day_on_cool_off(
        self,
    ):
        """
        Update account information via WF if there is a roll over but with
        partial principal & interest application day on cool off period
        """
        td_account_with_cool_off = self._create_time_deposit_account(
            instance_params_with_cool_off_period, self.cust_id
        )
        account_id = td_account_with_cool_off["id"]
        expected_dict = {
            "account_closure_period": "7",
            "auto_rollover_type": "partial_principal",
            "cool_off_period": "12",
            "deposit_period": "7",
            "fee_free_percentage_limit": "0",
            "grace_period": "0",
            "gross_interest_rate": "0.28",
            "interest_application_day": "3",
            "interest_application_frequency": "monthly",
            "partial_principal_amount": "1456",
            "period_end_hour": "21",
            "rollover_account_closure_period": "16",
            "rollover_grace_period": "0",
            "rollover_gross_interest_rate": "0.28",
            "rollover_interest_application_day": "3",
            "rollover_interest_application_frequency": "monthly",
            "rollover_period_end_hour": "11",
            "rollover_term": "14",
            "rollover_term_unit": "days",
            "term": "14",
            "term_unit": "days",
            "withdrawal_fee": "10",
            "withdrawal_percentage_fee": "0",
            "interest_payment_destination": "retain_on_account",
            "maturity_vault_account_id": td_account_with_cool_off["details"][
                "maturity_vault_account_id"
            ],
        }
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_ACCOUNT_INFORMATION_UPDATE",
            context={"user_id": self.cust_id, "account_id": account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_customer_preferences",
            event_name="customer_rollover_preferences_given",
            context={"auto_rollover_type": "partial_principal"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_details_with_partial_principal_amend_period",
            event_name="capture_rollover_details_with_partial_principal_amend_period" + "_given",
            context={
                "partial_principal_amount": "1456",
                "rollover_gross_interest_rate": "28",
                "rollover_grace_period": "0",
                "rollover_interest_application_frequency": "monthly",
                "rollover_term_unit": "days",
                "rollover_term": "14",
                "rollover_account_closure_period": "16",
                "rollover_period_end_hour": "11",
                "interest_payment_destination": "retain_on_account",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={
                "maturity_vault_account_id": td_account_with_cool_off["details"][
                    "maturity_vault_account_id"
                ]
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_settings_with_interest_application_day",
            event_name="account_settings_captured_with_interest_application_day",
            context={"rollover_interest_application_day": "3"},
        )

        # Account is updated if no errors were raised
        endtoend.workflows_helper.wait_for_state(wf_id, "account_rollover_update_succeded")
        endtoend.accounts_helper.wait_for_account_update(
            account_id=account_id, account_update_type="instance_param_vals_update"
        )
        account = endtoend.contracts_helper.get_account(account_id)
        current_dict = {**account["instance_param_vals"], **account["details"]}
        self.assertDictEqual(expected_dict, current_dict)

    def test_update_account_with_principal_without_app_day_on_grace_period(
        self,
    ):
        """
        Update account information via WF if there is a roll over but with partial
        principal & without interest application day in grace period.
        Update vault maturity disbursement to new vault account.
        """

        # create dummy account to update disbursement of original TD.
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=self.cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        td_account_with_grace_period = self._create_time_deposit_account(
            instance_params_with_grace_period, self.cust_id
        )
        account_id = td_account_with_grace_period["id"]
        expected_dict = {
            "account_closure_period": "7",
            "auto_rollover_type": "partial_principal",
            "cool_off_period": "0",
            "deposit_period": "0",
            "fee_free_percentage_limit": "0",
            "grace_period": "10",
            "gross_interest_rate": "0.01",
            "interest_application_day": "6",
            "interest_application_frequency": "weekly",
            "partial_principal_amount": "7",
            "period_end_hour": "21",
            "rollover_account_closure_period": "14",
            "rollover_grace_period": "0",
            "rollover_gross_interest_rate": "0.01",
            "rollover_interest_application_day": "6",
            "rollover_interest_application_frequency": "weekly",
            "rollover_period_end_hour": "14",
            "rollover_term": "5",
            "rollover_term_unit": "days",
            "term": "5",
            "term_unit": "days",
            "withdrawal_fee": "10",
            "withdrawal_percentage_fee": "0",
            "interest_payment_destination": "retain_on_account",
            "maturity_vault_account_id": savings_account_id,
        }
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_ACCOUNT_INFORMATION_UPDATE",
            context={"user_id": self.cust_id, "account_id": account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_customer_preferences",
            event_name="customer_rollover_preferences_given",
            context={"auto_rollover_type": "partial_principal"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_details_with_partial_principal_amend_period",
            event_name="capture_rollover_details_with_partial_principal_amend_period" + "_given",
            context={
                "partial_principal_amount": "7",
                "rollover_gross_interest_rate": "1",
                "rollover_grace_period": "0",
                "rollover_term": "5",
                "rollover_term_unit": "days",
                "rollover_account_closure_period": "14",
                "rollover_period_end_hour": "14",
                "rollover_interest_application_frequency": "weekly",
                "interest_payment_destination": "retain_on_account",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={"maturity_vault_account_id": savings_account_id},
        )

        # Account is updated if no errors were raised
        endtoend.workflows_helper.wait_for_state(wf_id, "account_rollover_update_succeded")
        account = endtoend.contracts_helper.get_account(account_id)
        current_dict = {**account["instance_param_vals"], **account["details"]}
        self.assertDictEqual(expected_dict, current_dict)

    def test_update_account_with_principal_without_app_day_on_cool_off(self):
        """
        Update account information via WF if there is a roll over but with partial
        principal & without interest application day in cool off period
        """
        td_account_with_cool_off = self._create_time_deposit_account(
            instance_params_with_cool_off_period, self.cust_id
        )
        account_id = td_account_with_cool_off["id"]
        expected_dict = {
            "account_closure_period": "7",
            "account_closure_period": "7",
            "auto_rollover_type": "partial_principal",
            "cool_off_period": "12",
            "deposit_period": "7",
            "fee_free_percentage_limit": "0",
            "grace_period": "0",
            "gross_interest_rate": "0.01",
            "interest_application_day": "6",
            "interest_application_frequency": "weekly",
            "partial_principal_amount": "7",
            "period_end_hour": "21",
            "rollover_account_closure_period": "14",
            "rollover_grace_period": "0",
            "rollover_gross_interest_rate": "0.01",
            "rollover_interest_application_day": "6",
            "rollover_interest_application_frequency": "weekly",
            "rollover_period_end_hour": "14",
            "rollover_term": "5",
            "rollover_term_unit": "days",
            "term": "5",
            "term_unit": "days",
            "withdrawal_fee": "10",
            "withdrawal_percentage_fee": "0",
            "interest_payment_destination": "retain_on_account",
            "maturity_vault_account_id": td_account_with_cool_off["details"][
                "maturity_vault_account_id"
            ],
        }
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_ACCOUNT_INFORMATION_UPDATE",
            context={"user_id": self.cust_id, "account_id": account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_customer_preferences",
            event_name="customer_rollover_preferences_given",
            context={"auto_rollover_type": "partial_principal"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_details_with_partial_principal_amend_period",
            event_name="capture_rollover_details_with_partial_principal_amend_period" + "_given",
            context={
                "partial_principal_amount": "7",
                "rollover_gross_interest_rate": "1",
                "rollover_grace_period": "0",
                "rollover_term": "5",
                "rollover_term_unit": "days",
                "rollover_account_closure_period": "14",
                "rollover_period_end_hour": "14",
                "rollover_interest_application_frequency": "weekly",
                "interest_payment_destination": "retain_on_account",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={
                "maturity_vault_account_id": td_account_with_cool_off["details"][
                    "maturity_vault_account_id"
                ],
            },
        )

        # Account is updated if no errors were raised
        endtoend.workflows_helper.wait_for_state(wf_id, "account_rollover_update_succeded")
        account = endtoend.contracts_helper.get_account(account_id)
        current_dict = {**account["instance_param_vals"], **account["details"]}
        self.assertDictEqual(expected_dict, current_dict)

    def test_update_account_with_principal_without_app_day_no_grace_and_cool_off_period(
        self,
    ):
        """
        Update account information via WF if there is a roll over but with partial
        principal & without interest application day not in cool off period
        and grace period
        """
        td_account_without_grace_and_cool_off_period = self._create_time_deposit_account(
            instance_params_without_grace_and_cool_off_period,
            self.cust_id,
        )

        account_id = td_account_without_grace_and_cool_off_period["id"]
        expected_dict = {
            "account_closure_period": "7",
            "auto_rollover_type": "partial_principal",
            "cool_off_period": "0",
            "deposit_period": "0",
            "fee_free_percentage_limit": "0",
            "grace_period": "0",
            "gross_interest_rate": "0.145",
            "interest_application_day": "6",
            "interest_application_frequency": "quarterly",
            "partial_principal_amount": "7",
            "period_end_hour": "21",
            "rollover_account_closure_period": "18",
            "rollover_grace_period": "0",
            "rollover_gross_interest_rate": "0.01",
            "rollover_interest_application_day": "6",
            "rollover_interest_application_frequency": "weekly",
            "rollover_period_end_hour": "19",
            "rollover_term": "12",
            "rollover_term_unit": "months",
            "term": "12",
            "term_unit": "months",
            "withdrawal_fee": "10",
            "withdrawal_percentage_fee": "0",
            "interest_payment_destination": "retain_on_account",
            "maturity_vault_account_id": td_account_without_grace_and_cool_off_period["details"][
                "maturity_vault_account_id"
            ],
        }
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_ACCOUNT_INFORMATION_UPDATE",
            context={"user_id": self.cust_id, "account_id": account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_customer_preferences",
            event_name="customer_rollover_preferences_given",
            context={"auto_rollover_type": "partial_principal"},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_details_with_partial_principal",
            event_name="capture_rollover_details_with_partial_principal_given",
            context={
                "partial_principal_amount": "7",
                "rollover_gross_interest_rate": "1",
                "rollover_grace_period": "0",
                "rollover_account_closure_period": "18",
                "rollover_period_end_hour": "19",
                "rollover_interest_application_frequency": "weekly",
                "interest_payment_destination": "retain_on_account",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={
                "maturity_vault_account_id": td_account_without_grace_and_cool_off_period[
                    "details"
                ]["maturity_vault_account_id"]
            },
        )

        # Account is updated if no errors were raised
        endtoend.workflows_helper.wait_for_state(wf_id, "account_rollover_update_succeded")
        account = endtoend.contracts_helper.get_account(account_id)
        current_dict = {**account["instance_param_vals"], **account["details"]}
        self.assertDictEqual(expected_dict, current_dict)

    def test_update_account_without_principal_with_app_day_on_cool_off(self):
        """
        Update account information via WF if there is a roll over but without
        partial principal and with interest application day on cool off period
        """
        td_account_with_cool_off = self._create_time_deposit_account(
            instance_params_with_cool_off_period, self.cust_id
        )
        account_id = td_account_with_cool_off["id"]
        expected_dict = {
            "account_closure_period": "7",
            "auto_rollover_type": "principal",
            "cool_off_period": "12",
            "deposit_period": "7",
            "fee_free_percentage_limit": "0",
            "grace_period": "0",
            "gross_interest_rate": "0.37",
            "interest_application_day": "9",
            "interest_application_frequency": "monthly",
            "partial_principal_amount": "0",
            "period_end_hour": "21",
            "rollover_account_closure_period": "20",
            "rollover_grace_period": "0",
            "rollover_gross_interest_rate": "0.37",
            "rollover_interest_application_day": "9",
            "rollover_interest_application_frequency": "monthly",
            "rollover_period_end_hour": "20",
            "rollover_term": "16",
            "rollover_term_unit": "days",
            "term": "16",
            "term_unit": "days",
            "withdrawal_fee": "10",
            "withdrawal_percentage_fee": "0",
            "interest_payment_destination": "retain_on_account",
            "maturity_vault_account_id": td_account_with_cool_off["details"][
                "maturity_vault_account_id"
            ],
        }
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_ACCOUNT_INFORMATION_UPDATE",
            context={"user_id": self.cust_id, "account_id": account_id},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_customer_preferences",
            event_name="customer_rollover_preferences_given",
            context={"auto_rollover_type": "principal"},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_details_amend_period",
            event_name="capture_rollover_details_amend_period_given",
            context={
                "rollover_gross_interest_rate": "37",
                "rollover_grace_period": "0",
                "rollover_account_closure_period": "20",
                "rollover_period_end_hour": "20",
                "rollover_interest_application_frequency": "monthly",
                "rollover_term_unit": "days",
                "rollover_term": "16",
                "interest_payment_destination": "retain_on_account",
            },
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={
                "maturity_vault_account_id": td_account_with_cool_off["details"][
                    "maturity_vault_account_id"
                ]
            },
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_settings_with_interest_application_day",
            event_name="account_settings_captured_with_interest_application_day",
            context={"rollover_interest_application_day": "9"},
        )

        # Account is updated if no errors were raised
        endtoend.workflows_helper.wait_for_state(wf_id, "account_rollover_update_succeded")

        account = endtoend.contracts_helper.get_account(account_id)
        current_dict = {**account["instance_param_vals"], **account["details"]}
        self.assertDictEqual(expected_dict, current_dict)

    def test_update_account_without_principal_with_app_day_no_grace_and_cool_off_period(
        self,
    ):
        """
        Update account information via WF if there is a roll over but without
        partial principal and with interest application day not on cool off period
        and grace period
        """
        td_account_without_grace_and_cool_off_period = self._create_time_deposit_account(
            instance_params_without_grace_and_cool_off_period,
            self.cust_id,
        )

        account_id = td_account_without_grace_and_cool_off_period["id"]
        expected_dict = {
            "account_closure_period": "7",
            "auto_rollover_type": "principal",
            "cool_off_period": "0",
            "deposit_period": "0",
            "fee_free_percentage_limit": "0",
            "grace_period": "0",
            "gross_interest_rate": "0.145",
            "interest_application_day": "6",
            "interest_application_frequency": "quarterly",
            "partial_principal_amount": "0",
            "period_end_hour": "21",
            "rollover_account_closure_period": "22",
            "rollover_grace_period": "0",
            "rollover_gross_interest_rate": "0.08",
            "rollover_interest_application_day": "9",
            "rollover_interest_application_frequency": "monthly",
            "rollover_period_end_hour": "22",
            "rollover_term": "12",
            "rollover_term_unit": "months",
            "term": "12",
            "term_unit": "months",
            "withdrawal_fee": "10",
            "withdrawal_percentage_fee": "0",
            "interest_payment_destination": "retain_on_account",
            "maturity_vault_account_id": td_account_without_grace_and_cool_off_period["details"][
                "maturity_vault_account_id"
            ],
        }
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_ACCOUNT_INFORMATION_UPDATE",
            context={"user_id": self.cust_id, "account_id": account_id},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_customer_preferences",
            event_name="customer_rollover_preferences_given",
            context={"auto_rollover_type": "principal"},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_details",
            event_name="capture_rollover_details_given",
            context={
                "rollover_gross_interest_rate": "8",
                "rollover_account_closure_period": "22",
                "rollover_period_end_hour": "22",
                "rollover_grace_period": "0",
                "rollover_interest_application_frequency": "monthly",
                "interest_payment_destination": "retain_on_account",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={
                "maturity_vault_account_id": td_account_without_grace_and_cool_off_period[
                    "details"
                ]["maturity_vault_account_id"]
            },
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_settings_with_interest_application_day",
            event_name="account_settings_captured_with_interest_application_day",
            context={"rollover_interest_application_day": "9"},
        )

        # Account is updated if no errors were raised
        endtoend.workflows_helper.wait_for_state(wf_id, "account_rollover_update_succeded")

        account = endtoend.contracts_helper.get_account(account_id)
        current_dict = {**account["instance_param_vals"], **account["details"]}
        self.assertDictEqual(expected_dict, current_dict)

    def test_update_without_principal_and_app_day_no_grace_and_cool_off_period(
        self,
    ):
        """
        Update account information via WF if there is a roll over but without
        partial principal and interest application day not on cool off period
        and grace period
        """
        td_account_without_grace_and_cool_off_period = self._create_time_deposit_account(
            instance_params_without_grace_and_cool_off_period,
            self.cust_id,
        )

        account_id = td_account_without_grace_and_cool_off_period["id"]
        expected_dict = {
            "account_closure_period": "7",
            "auto_rollover_type": "principal",
            "cool_off_period": "0",
            "deposit_period": "0",
            "fee_free_percentage_limit": "0",
            "grace_period": "0",
            "gross_interest_rate": "0.145",
            "interest_application_day": "6",
            "interest_application_frequency": "quarterly",
            "partial_principal_amount": "0",
            "period_end_hour": "21",
            "rollover_account_closure_period": "23",
            "rollover_grace_period": "0",
            "rollover_gross_interest_rate": "0.03",
            "rollover_interest_application_day": "6",
            "rollover_interest_application_frequency": "weekly",
            "rollover_period_end_hour": "23",
            "rollover_term": "12",
            "rollover_term_unit": "months",
            "term": "12",
            "term_unit": "months",
            "withdrawal_fee": "10",
            "withdrawal_percentage_fee": "0",
            "interest_payment_destination": "vault",
            "maturity_vault_account_id": td_account_without_grace_and_cool_off_period["details"][
                "maturity_vault_account_id"
            ],
            "interest_vault_account_id": td_account_without_grace_and_cool_off_period["details"][
                "maturity_vault_account_id"
            ],
        }
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_ACCOUNT_INFORMATION_UPDATE",
            context={"user_id": self.cust_id, "account_id": account_id},
        )

        expected_dict_temp = {"auto_rollover_type": "principal"}
        expected_dict.update(expected_dict_temp)
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_customer_preferences",
            event_name="customer_rollover_preferences_given",
            context=expected_dict_temp,
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_details",
            event_name="capture_rollover_details_given",
            context={
                "rollover_account_closure_period": "23",
                "rollover_period_end_hour": "23",
                "rollover_gross_interest_rate": "3",
                "rollover_grace_period": "0",
                "rollover_interest_application_frequency": "weekly",
                "interest_payment_destination": "vault",
            },
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_vault_account_details",
            event_name="vault_account_captured_interest",
            context={
                "interest_vault_account_id": td_account_without_grace_and_cool_off_period[
                    "details"
                ]["maturity_vault_account_id"]
            },
        )
        expected_dict_temp = {
            "maturity_vault_account_id": td_account_without_grace_and_cool_off_period["details"][
                "maturity_vault_account_id"
            ],
        }
        expected_dict.update(expected_dict_temp)
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context=expected_dict_temp,
        )

        # Account is updated if no errors were raised
        endtoend.workflows_helper.wait_for_state(wf_id, "account_rollover_update_succeded")
        account = endtoend.contracts_helper.get_account(account_id)
        current_dict = {**account["instance_param_vals"], **account["details"]}
        self.assertDictEqual(expected_dict, current_dict)

    def test_update_without_principal_without_app_day_on_cool_off(
        self,
    ):
        """
        Update account information via WF if there is a roll over but without
        partial principal and interest application day not on cool off period
        and grace period.
        """
        td_account_with_cool_off = self._create_time_deposit_account(
            instance_params_with_cool_off_period, self.cust_id
        )
        account_id = td_account_with_cool_off["id"]
        expected_dict = {
            "account_closure_period": "7",
            "auto_rollover_type": "principal",
            "cool_off_period": "12",
            "deposit_period": "7",
            "fee_free_percentage_limit": "0",
            "grace_period": "0",
            "gross_interest_rate": "0.03",
            "interest_application_day": "6",
            "interest_application_frequency": "weekly",
            "partial_principal_amount": "0",
            "period_end_hour": "21",
            "rollover_account_closure_period": "24",
            "rollover_grace_period": "0",
            "rollover_gross_interest_rate": "0.03",
            "rollover_interest_application_day": "6",
            "rollover_interest_application_frequency": "weekly",
            "rollover_period_end_hour": "21",
            "rollover_term": "7",
            "rollover_term_unit": "days",
            "term": "7",
            "term_unit": "days",
            "withdrawal_fee": "10",
            "withdrawal_percentage_fee": "0",
            "interest_payment_destination": "vault",
            "maturity_vault_account_id": td_account_with_cool_off["details"][
                "maturity_vault_account_id"
            ],
            "interest_vault_account_id": td_account_with_cool_off["details"][
                "maturity_vault_account_id"
            ],
        }
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_ACCOUNT_INFORMATION_UPDATE",
            context={"user_id": self.cust_id, "account_id": account_id},
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_customer_preferences",
            event_name="customer_rollover_preferences_given",
            context={"auto_rollover_type": "principal"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_rollover_details_amend_period",
            event_name="capture_rollover_details_amend_period_given",
            context={
                "rollover_account_closure_period": "24",
                "rollover_period_end_hour": "21",
                "rollover_gross_interest_rate": "3",
                "rollover_grace_period": "0",
                "rollover_term": "7",
                "rollover_term_unit": "days",
                "rollover_interest_application_frequency": "weekly",
                "interest_payment_destination": "vault",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_vault_account_details",
            event_name="vault_account_captured_interest",
            context={
                "interest_vault_account_id": td_account_with_cool_off["details"][
                    "maturity_vault_account_id"
                ],
            },
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_maturity_vault_account_details",
            event_name="vault_account_captured_maturity",
            context={
                "maturity_vault_account_id": td_account_with_cool_off["details"][
                    "maturity_vault_account_id"
                ]
            },
        )

        # Account is updated if no errors were raised
        endtoend.workflows_helper.wait_for_state(wf_id, "account_rollover_update_succeded")

        account = endtoend.contracts_helper.get_account(account_id)
        current_dict = {**account["instance_param_vals"], **account["details"]}
        self.assertDictEqual(expected_dict, current_dict)

    def test_rollover_time_deposit_with_principal_amount(self):
        """
        Testing on rollover time deposit with auto_rollover_type set as
        principal
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
                "grace_period": "0",
                "cool_off_period": "1",
                "period_end_hour": "21",
                "account_closure_period": "7",
                "auto_rollover_type": "principal",
                "fee_free_percentage_limit": "0",
                "withdrawal_fee": "10",
                "withdrawal_percentage_fee": "0",
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

        # Close TD account
        wf_id = endtoend.workflows_helper.start_workflow(
            "TIME_DEPOSIT_MATURITY",
            context={
                "account_id": td_account_id,
                "applied_interest_amount": "0",
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["time_deposit"],
            },
        )

        cwf_id = endtoend.workflows_helper.get_child_workflow_id(wf_id, "rollover_time_deposit")

        endtoend.workflows_helper.wait_for_state(cwf_id, "account_opened_successfully")

        context = endtoend.workflows_helper.get_state_local_context(
            cwf_id, "account_opened_successfully"
        )
        rollover_td_account = endtoend.contracts_helper.get_account(context["id"])

        self.assertEqual("ACCOUNT_STATUS_OPEN", rollover_td_account["status"])
        # Maturity TD account is open

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")
        # Original TD account is closed

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
                # Money has moved to new TD account
                rollover_td_account["id"]: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "200",
                    )
                ],
            }
        )


if __name__ == "__main__":
    endtoend.runtests()
