# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from json import loads

# third party
from requests import HTTPError

# library
from library.mortgage.contracts.template import mortgage
from library.mortgage.test import dimensions, files
from library.mortgage.test.e2e import accounts, parameters

# inception sdk
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT

endtoend.testhandle.CONTRACTS = {
    "mortgage": {
        "path": files.MORTGAGE_CONTRACT,
        "template_params": parameters.default_template,
    },
    "dummy_account": {
        "path": DUMMY_CONTRACT,
    },
}
endtoend.testhandle.WORKFLOWS = {
    "MORTGAGE_APPLICATION": "library/mortgage/workflows/mortgage_application.yaml",
    "MORTGAGE_MARK_DELINQUENT": "library/mortgage/workflows/mortgage_mark_delinquent.yaml",
    "MORTGAGE_REPAYMENT_HOLIDAY_APPLICATION": (
        "library/mortgage/workflows/mortgage_repayment_holiday_application.yaml"
    ),
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "ACCOUNT_DELINQUENT": "library/common/flag_definitions/account_delinquent.resource.yaml",
    "REPAYMENT_HOLIDAY": "library/common/flag_definitions/repayment_holiday.resource.yaml",
}


endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = accounts.internal_accounts_tside


class MortgageTest(endtoend.End2Endtest):
    def test_account_opening(self):
        cust_id = endtoend.core_api_helper.create_customer()
        deposit_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = {
            **parameters.default_instance,
            mortgage.disbursement.PARAM_DEPOSIT_ACCOUNT: deposit_account_id,
        }

        mortgage_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                deposit_account_id: [(dimensions.DEFAULT, "300000")],
                mortgage_account_id: [
                    (dimensions.PRINCIPAL, "300000"),
                    (dimensions.EMI, "25135.62"),
                ],
            }
        )


class MortgageWorkflowTest(endtoend.End2Endtest):
    @endtoend.kafka_helper.kafka_only_test
    def test_mark_delinquency_workflow(self):
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = {
            **parameters.default_instance,
            mortgage.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
        }

        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        mortgage_account_id = mortgage_account["id"]

        self.assertEqual("ACCOUNT_STATUS_OPEN", mortgage_account["status"])

        endtoend.contracts_helper.send_contract_notification(
            notification_type="MORTGAGE_MARK_DELINQUENT",
            notification_details={"account_id": mortgage_account_id},
            resource_id=mortgage_account_id,
            resource_type=(
                endtoend.contracts_helper.ContractNotificationResourceType.RESOURCE_ACCOUNT
            ),
        )

        workflows = endtoend.workflows_helper.wait_for_smart_contract_initiated_workflows(
            account_id=mortgage_account_id,
            workflow_definition_id=endtoend.testhandle.workflow_definition_id_mapping[
                "MORTGAGE_MARK_DELINQUENT"
            ],
        )
        endtoend.workflows_helper.wait_for_state(
            workflows[0]["wf_instance_id"], "account_delinquency_set"
        )

        flag_status = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping["ACCOUNT_DELINQUENT"],
            account_ids=[mortgage_account_id],
        )

        self.assertEqual(flag_status[0]["account_id"], mortgage_account_id)

    def test_application_workflow_does_not_open_account_for_invalid_product_id(self):
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
                "product_id": "invalid_id",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_creation_failed")

    def test_application_workflow_correctly_opens_an_account(self):
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

        # When setting the mortgage parameters, provide
        # an invalid variable rate adjustment
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_mortgage_parameters",
            event_name="mortgage_parameters_chosen",
            context={
                "deposit_account": "1",
                "due_amount_calculation_day": "28",
                "fixed_interest_rate": "0.01",
                "fixed_interest_term": "12",
                "interest_only_term": "0",
                "principal": "3000000",
                "total_repayment_count": "12",
                "variable_rate_adjustment": "-0.9",
            },
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "invalid_params")

        endtoend.workflows_helper.send_event(
            wf_id, event_state="invalid_params", event_name="retry_entry", context={}
        )

        # Provide all correct mortgage parameters
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_mortgage_parameters",
            event_name="mortgage_parameters_chosen",
            context={
                "deposit_account": "1",
                "due_amount_calculation_day": "28",
                "fixed_interest_rate": "0.01",
                "fixed_interest_term": "12",
                "interest_only_term": "0",
                "principal": "300000",
                "total_repayment_count": "12",
                "variable_rate_adjustment": "-0.001",
            },
        )

        # Check that the mortgage account was opened successfully
        endtoend.workflows_helper.wait_for_state(wf_id, "account_created_successfully")
        mortgage_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        mortgage_account = endtoend.contracts_helper.get_account(mortgage_account_id)
        self.assertEqual("ACCOUNT_STATUS_OPEN", mortgage_account["status"])

        endtoend.accounts_helper.wait_for_account_update(
            account_id=mortgage_account_id, account_update_type="activation_update"
        )

    def test_repayment_holiday_workflow(self):
        due_amount_calculation_day = 21

        cust_id = endtoend.core_api_helper.create_customer()
        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = {
            **parameters.default_instance,
            mortgage.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
            mortgage.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                due_amount_calculation_day
            ),
        }

        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        first_allowed_repayment_datetime = datetime.utcnow() + relativedelta(
            day=due_amount_calculation_day
        )
        if first_allowed_repayment_datetime < datetime.utcnow():
            first_allowed_repayment_datetime += relativedelta(months=1)

        wf_id = endtoend.workflows_helper.start_workflow(
            "MORTGAGE_REPAYMENT_HOLIDAY_APPLICATION",
            context={"account_id": mortgage_account["id"]},
        )

        latest_state = endtoend.workflows_helper.wait_for_state(
            wf_id=wf_id, state_name="capture_repayment_holiday_period"
        )

        # 1. try to create an invalid flag - in the past
        start_time = first_allowed_repayment_datetime - relativedelta(months=1)
        end_time = first_allowed_repayment_datetime + relativedelta(months=1)

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

        # 2. try to create an invalid flag - not on the repayment date
        start_time = first_allowed_repayment_datetime + relativedelta(months=1, days=1)
        end_time = first_allowed_repayment_datetime + relativedelta(months=2)

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

        # 3. try to create an invalid flag - start date > end date
        start_time = first_allowed_repayment_datetime + relativedelta(months=3)
        end_time = first_allowed_repayment_datetime + relativedelta(months=1)

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
        start_time = first_allowed_repayment_datetime + relativedelta(months=1)
        end_time = first_allowed_repayment_datetime + relativedelta(months=2)

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
        start_time = first_allowed_repayment_datetime + relativedelta(months=1)
        end_time = first_allowed_repayment_datetime + relativedelta(months=2)

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
        start_time = first_allowed_repayment_datetime + relativedelta(months=2)
        end_time = first_allowed_repayment_datetime + relativedelta(months=3)

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

    def test_update_repayment_day_raises_error_due_to_contract_rejection(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = {
            **parameters.default_instance,
            mortgage.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
        }

        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        mortgage_account_id = mortgage_account["id"]

        self.assertEqual("ACCOUNT_STATUS_OPEN", mortgage_account["status"])
        due_amount_calculation_day_before_request = endtoend.contracts_helper.get_account(
            mortgage_account_id
        )["instance_param_vals"]["due_amount_calculation_day"]

        # the request should error due to the pre_parameter_change_hook rejection
        try:
            endtoend.core_api_helper.update_account_instance_parameters(
                account_id=mortgage_account_id,
                instance_param_vals={"due_amount_calculation_day": "2"},
            )
        except HTTPError as err:
            message = loads(err.response.text).get("message")
            self.assertEqual(
                "It is not possible to change the monthly repayment day if the first repayment "
                "date has not passed.",
                message,
            )

        # validate parameter value has not changed in case the except condition was not invoked
        due_amount_calculation_day_after_request = endtoend.contracts_helper.get_account(
            mortgage_account_id
        )["instance_param_vals"]["due_amount_calculation_day"]
        self.assertEqual(
            due_amount_calculation_day_before_request, due_amount_calculation_day_after_request
        )

        due_amount_calculation_day_before_request = endtoend.contracts_helper.get_account(
            mortgage_account_id
        )["instance_param_vals"]["due_amount_calculation_day"]

        # apply the repayment_holiday flag to verify rejection
        endtoend.core_api_helper.create_flag(
            endtoend.testhandle.flag_definition_id_mapping["REPAYMENT_HOLIDAY"],
            mortgage_account_id,
        )

        # the request should error due to the pre_parameter_change_hook rejection
        try:
            endtoend.core_api_helper.update_account_instance_parameters(
                account_id=mortgage_account_id,
                instance_param_vals={"due_amount_calculation_day": "2"},
            )
        except HTTPError as err:
            message = loads(err.response.text).get("message")
            self.assertEqual(
                "The due_amount_calculation_day parameter cannot be updated during a "
                "repayment holiday.",
                message,
            )

        # validate parameter value has not changed in case the except condition was not invoked
        due_amount_calculation_day_after_request = endtoend.contracts_helper.get_account(
            mortgage_account_id
        )["instance_param_vals"]["due_amount_calculation_day"]
        self.assertEqual(
            due_amount_calculation_day_before_request, due_amount_calculation_day_after_request
        )
