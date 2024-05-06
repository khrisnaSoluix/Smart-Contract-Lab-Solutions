# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from json import dumps
from zoneinfo import ZoneInfo

# library
from library.loan.contracts.template import loan
from library.loan.test import dimensions, files
from library.loan.test.e2e import accounts, parameters

# inception sdk
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
from inception_sdk.test_framework.endtoend.contracts_helper import ContractNotificationResourceType

endtoend.testhandle.CONTRACTS = {
    "loan": {
        "path": files.LOAN_CONTRACT,
        "template_params": parameters.default_template.copy(),
    },
    "dummy_account": {
        "path": DUMMY_CONTRACT,
    },
}

endtoend.testhandle.WORKFLOWS = {
    "LOAN_APPLICATION": "library/loan/workflows/loan_application.yaml",
    "LOAN_MARK_DELINQUENT": "library/loan/workflows/loan_mark_delinquent.yaml",
    "LOAN_REPAYMENT_HOLIDAY_APPLICATION": (
        "library/loan/workflows/loan_repayment_holiday_application.yaml"
    ),
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "ACCOUNT_DELINQUENT": "library/common/flag_definitions/account_delinquent.resource.yaml",
    "REPAYMENT_HOLIDAY": "library/common/flag_definitions/repayment_holiday.resource.yaml",
}

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = accounts.internal_accounts_tside


class LoanTest(endtoend.End2Endtest):
    def test_account_opening(self):
        cust_id = endtoend.core_api_helper.create_customer()
        deposit_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = {
            **parameters.default_instance,
            loan.disbursement.PARAM_DEPOSIT_ACCOUNT: deposit_account_id,
        }

        loan_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                deposit_account_id: [(dimensions.DEFAULT, "3000")],
                loan_account_id: [(dimensions.PRINCIPAL, "3000"), (dimensions.EMI, "254.22")],
            }
        )

    @endtoend.kafka_helper.kafka_only_test
    def test_repayment_schedule_notification(self):
        opening_dt = datetime(year=2020, month=10, day=1, hour=10, tzinfo=ZoneInfo("UTC"))
        cust_id = endtoend.core_api_helper.create_customer()

        deposit_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = {
            **parameters.default_instance,
            loan.PARAM_FIXED_RATE_LOAN: "True",
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.034544",
            loan.disbursement.PARAM_DEPOSIT_ACCOUNT: deposit_account_id,
            loan.disbursement.PARAM_PRINCIPAL: "1000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "11",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
        }

        loan_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_dt.isoformat(),
        )["id"]

        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type="LOAN_REPAYMENT_SCHEDULE",
            notification_details={
                "account_id": loan_account_id,
                "repayment_schedule": dumps(
                    {
                        "2020-11-11 00:01:00+00:00": ["1", "918.03", "85.85", "81.97", "3.88"],
                        "2020-12-11 00:01:00+00:00": ["2", "835.74", "84.90", "82.29", "2.61"],
                        "2021-01-11 00:01:00+00:00": ["3", "753.29", "84.90", "82.45", "2.45"],
                        "2021-02-11 00:01:00+00:00": ["4", "670.60", "84.90", "82.69", "2.21"],
                        "2021-03-11 00:01:00+00:00": ["5", "587.48", "84.90", "83.12", "1.78"],
                        "2021-04-11 00:01:00+00:00": ["6", "504.30", "84.90", "83.18", "1.72"],
                        "2021-05-11 00:01:00+00:00": ["7", "420.83", "84.90", "83.47", "1.43"],
                        "2021-06-11 00:01:00+00:00": ["8", "337.16", "84.90", "83.67", "1.23"],
                        "2021-07-11 00:01:00+00:00": ["9", "253.22", "84.90", "83.94", "0.96"],
                        "2021-08-11 00:01:00+00:00": ["10", "169.06", "84.90", "84.16", "0.74"],
                        "2021-09-11 00:01:00+00:00": ["11", "84.66", "84.90", "84.40", "0.50"],
                        "2021-10-11 00:01:00+00:00": ["12", "0", "84.90", "84.66", "0.24"],
                    }
                ),
            },
            resource_id=str(loan_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )


class LoanWorkflowTest(endtoend.End2Endtest):
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
            loan.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
        }
        loan_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        loan_account_id = loan_account["id"]

        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

        endtoend.contracts_helper.send_contract_notification(
            notification_type="LOAN_MARK_DELINQUENT",
            notification_details={"account_id": loan_account_id},
            resource_id=loan_account_id,
            resource_type=(
                endtoend.contracts_helper.ContractNotificationResourceType.RESOURCE_ACCOUNT
            ),
        )

        workflows = endtoend.workflows_helper.wait_for_smart_contract_initiated_workflows(
            account_id=loan_account_id,
            workflow_definition_id=endtoend.testhandle.workflow_definition_id_mapping[
                "LOAN_MARK_DELINQUENT"
            ],
        )
        endtoend.workflows_helper.wait_for_state(
            workflows[0]["wf_instance_id"], "account_delinquency_set"
        )

        flag_status = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping["ACCOUNT_DELINQUENT"],
            account_ids=[loan_account_id],
        )

        self.assertEqual(flag_status[0]["account_id"], loan_account_id)

    def test_application_workflow_does_not_open_account_for_invalid_product_id(self):
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_APPLICATION",
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
            "LOAN_APPLICATION",
            context={
                "account_id": dummy_account_id,
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["loan"],
            },
        )

        # variable rate adjustment is invalid as fixed rate + adjustment < 0
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_loan_parameters",
            event_name="loan_parameters_chosen",
            context={
                # Accrual Rest
                loan.PARAM_INTEREST_ACCRUAL_REST_TYPE: "daily",
                # Upfront Fee
                loan.PARAM_UPFRONT_FEE: "0",
                loan.PARAM_AMORTISE_UPFRONT_FEE: "False",
                # Late repayment Fee
                loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: "False",
                # Fixed Rate
                loan.PARAM_FIXED_RATE_LOAN: "False",
                loan.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
                loan.disbursement.PARAM_PRINCIPAL: "300000",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "28",
                loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.01",
                loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
                loan.repayment_holiday.PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE: "increase_emi",
                loan.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "-0.9",
            },
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "invalid_params")

        endtoend.workflows_helper.send_event(
            wf_id, event_state="invalid_params", event_name="retry_entry", context={}
        )

        # Provide all correct loan parameters
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_loan_parameters",
            event_name="loan_parameters_chosen",
            context={
                # Accrual Rest
                loan.PARAM_INTEREST_ACCRUAL_REST_TYPE: "daily",
                # Upfront Fee
                loan.PARAM_UPFRONT_FEE: "0",
                loan.PARAM_AMORTISE_UPFRONT_FEE: "False",
                # Late repayment Fee
                loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: "False",
                # Fixed Rate
                loan.PARAM_FIXED_RATE_LOAN: "False",
                loan.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
                loan.disbursement.PARAM_PRINCIPAL: "300000",
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "28",
                loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.01",
                loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
                loan.repayment_holiday.PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE: "increase_emi",
                loan.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "-0.001",
            },
        )

        # Check that the loan account was opened successfully
        endtoend.workflows_helper.wait_for_state(wf_id, "account_created_successfully")
        loan_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        loan_account = endtoend.contracts_helper.get_account(loan_account_id)
        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

        endtoend.accounts_helper.wait_for_account_update(
            account_id=loan_account_id, account_update_type="activation_update"
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
            loan.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                due_amount_calculation_day
            ),
        }

        loan_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        first_allowed_repayment_datetime = datetime.utcnow() + relativedelta(
            day=due_amount_calculation_day
        )
        if first_allowed_repayment_datetime < datetime.utcnow():
            first_allowed_repayment_datetime += relativedelta(months=1)

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_REPAYMENT_HOLIDAY_APPLICATION",
            context={"account_id": loan_account["id"]},
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

        endtoend.workflows_helper.wait_for_state(
            wf_id=wf_id, state_name="capture_impact_preference"
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_impact_preference",
            event_name="impact_preference_selected",
            context={"chosen_impact_preference": "increase_term"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "repayment_holiday_set")

        loan_account = endtoend.contracts_helper.get_account(loan_account["id"])
        impact_preference = loan_account["instance_param_vals"][
            loan.repayment_holiday.PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE
        ]
        self.assertEqual(
            "increase_term", impact_preference, "impact preference parameter is updated"
        )

        # start new workflow on the same account
        wf_id_2 = endtoend.workflows_helper.start_workflow(
            "LOAN_REPAYMENT_HOLIDAY_APPLICATION",
            context={"account_id": loan_account["id"]},
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
            "LOAN_REPAYMENT_HOLIDAY_APPLICATION",
            context={"account_id": loan_account["id"]},
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

        endtoend.workflows_helper.wait_for_state(
            wf_id=wf_id_3, state_name="capture_impact_preference"
        )

        endtoend.workflows_helper.send_event(
            wf_id_3,
            event_state="capture_impact_preference",
            event_name="impact_preference_selected",
            context={"chosen_impact_preference": "increase_emi"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id_3, "repayment_holiday_set")
