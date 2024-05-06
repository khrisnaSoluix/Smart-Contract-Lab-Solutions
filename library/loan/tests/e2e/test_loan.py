# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

# common
from inception_sdk.test_framework.common.constants import DEFAULT_DENOMINATION
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.helper import COMMON_ACCOUNT_SCHEDULE_TAG_PATH
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
from library.common.flag_definitions.files import ACCOUNT_DELINQUENT, REPAYMENT_HOLIDAY

# Loan specific
import library.loan.constants.dimensions as dimensions
import library.loan.constants.files as contract_files

from library.loan.tests.e2e.loan_test_params import (
    internal_accounts_tside,
    loan_template_params,
    loan_balloon_min_repayment_template_params,
    loan_balloon_no_repayment_template_params,
    loan_balloon_interest_only_template_params,
    POSTING_BATCH_ACCEPTED,
    loan_instance_params,
    loan_balloon_min_repayment_instance_params,
)

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "loan": {
        "path": contract_files.CONTRACT_FILE,
        "template_params": loan_template_params,
    },
    "dummy_current_account": {"path": DUMMY_CONTRACT},
    "balloon_loan_min_repayment": {
        "path": contract_files.CONTRACT_FILE,
        "template_params": loan_balloon_min_repayment_template_params,
    },
    "balloon_loan_no_repayment": {
        "path": contract_files.CONTRACT_FILE,
        "template_params": loan_balloon_no_repayment_template_params,
    },
    "balloon_loan_interest_only_repayment": {
        "path": contract_files.CONTRACT_FILE,
        "template_params": loan_balloon_interest_only_template_params,
    },
}

endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": contract_files.files.UTILS_FILE},
    "amortisation": {"path": contract_files.files.AMORTISATION_FILE},
}

endtoend.testhandle.WORKFLOWS = {
    "LOAN_APPLICATION": "library/loan/workflows/loan_application.yaml",
    "LOAN_EARLY_REPAYMENT": "library/loan/workflows/loan_early_repayment.yaml",
    "LOAN_CLOSURE": "library/loan/workflows/loan_closure.yaml",
    "LOAN_MARK_DELINQUENT": "library/loan/workflows/loan_mark_delinquent.yaml",
    "LOAN_TOP_UP": "library/loan/workflows/loan_top_up.yaml",
    "LOAN_REPAYMENT_DAY_CHANGE": "library/loan/workflows/loan_repayment_day_change.yaml",
    "LOAN_REPAYMENT_HOLIDAY_APPLICATION": (
        "library/loan/workflows/loan_repayment_holiday_application.yaml"
    ),
    "LOAN_REPAYMENT_NOTIFICATION": "library/common/workflows/simple_notification.yaml",
    "LOAN_OVERDUE_REPAYMENT_NOTIFICATION": "library/common/workflows/simple_notification.yaml",
}


endtoend.testhandle.FLAG_DEFINITIONS = {
    "ACCOUNT_DELINQUENT": ACCOUNT_DELINQUENT,
    "REPAYMENT_HOLIDAY": REPAYMENT_HOLIDAY,
}

endtoend.testhandle.ACCOUNT_SCHEDULE_TAGS = {
    "LOAN_ACCRUE_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "LOAN_REPAYMENT_DAY_SCHEDULE_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "LOAN_BALLOON_PAYMENT_SCHEDULE_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "LOAN_CHECK_DELINQUENCY_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "LOAN_CHECK_OVERDUE_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
}


class LoanAccountTests(endtoend.End2Endtest):
    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at
        # Uncomment this for timing info.
        # print('\n{} ({}s)'.format(self.id().rpartition('.')[2], round(self._elapsed_time, 2)))

    def test_workflow_apply_for_fixed_rate_loan_with_balloon(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid[
                    "balloon_loan_min_repayment"
                ],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_loan_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_loan_parameters",
            event_name="loan_parameters_selected",
            context={
                "fixed_interest_loan": "True",
                "total_term": "13",
                "principal": "20000",
                "repayment_day": "1",
                "interest_accrual_rest_type": "monthly",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_balloon_min_repayment_type")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_balloon_min_repayment_type",
            event_name="balloon_min_repayment_type_selected",
            context={
                "balloon_payment_type": "chosen_balloon_amount",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_balloon_payment_amount")

        # as balloon payment amount is > principal, user should be prompted
        # to re-input the balloon payment amount
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_balloon_payment_amount",
            event_name="balloon_payment_amount_selected",
            context={
                "balloon_payment_amount": "30000",
            },
        )
        endtoend.workflows_helper.wait_for_state(
            wf_id,
            "balloon_amount_details_invalid",
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="balloon_amount_details_invalid",
            event_name="balloon_amount_error_confirmed",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_balloon_payment_amount")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_balloon_payment_amount",
            event_name="balloon_payment_amount_selected",
            context={
                "balloon_payment_amount": "10000",
            },
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "choose_balloon_payment_date")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_balloon_payment_date",
            event_name="balloon_date_selected",
            context={
                "balloon_payment_days": "1",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "confirm_balloon_payment_date")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_balloon_payment_date",
            event_name="balloon_date_confirmed",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_fixed_interest_rate")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_fixed_interest_rate",
            event_name="fixed_interest_rate_captured",
            context={"fixed_interest_rate": "0.0345"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_vault_account_details")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account_details",
            event_name="vault_account_captured",
            context={"deposit_account": dummy_current_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "determine_upfront_fee")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="determine_upfront_fee",
            event_name="no_upfront_fee_selected",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        loan_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        loan_account = endtoend.contracts_helper.get_account(loan_account_id)

        fixed_interest_rate = loan_account["instance_param_vals"]["fixed_interest_rate"]
        fixed_interest_loan = loan_account["instance_param_vals"]["fixed_interest_loan"]
        variable_rate_adjustment = loan_account["instance_param_vals"]["variable_rate_adjustment"]
        repayment_holiday_impact = loan_account["instance_param_vals"][
            "repayment_holiday_impact_preference"
        ]
        interest_accrual_rest_type = loan_account["instance_param_vals"][
            "interest_accrual_rest_type"
        ]
        balloon_payment_amount = loan_account["instance_param_vals"]["balloon_payment_amount"]
        balloon_emi_amount = loan_account["instance_param_vals"]["balloon_emi_amount"]
        balloon_payment_days_delta = loan_account["instance_param_vals"][
            "balloon_payment_days_delta"
        ]
        loan_start_date = loan_account["instance_param_vals"]["loan_start_date"]
        repayment_period = loan_template_params["repayment_period"]
        loan_start_day = datetime.strptime(loan_start_date, "%Y-%m-%d").day

        # If loan taken out on 1st, next_payment_date is in 1 month
        # otherwise it'll be the month after that
        month_delta = 1 if loan_start_day == 1 else 2

        next_repayment_date = (datetime.today() + relativedelta(months=month_delta)).replace(day=1)
        next_overdue_date = next_repayment_date + relativedelta(days=int(repayment_period))

        self.assertEqual(fixed_interest_rate, "0.0345")
        self.assertEqual(fixed_interest_loan, "True")
        self.assertEqual(variable_rate_adjustment, "0")
        self.assertEqual(repayment_holiday_impact, "increase_emi")
        self.assertEqual(interest_accrual_rest_type, "monthly")
        self.assertEqual(balloon_payment_amount, "10000")
        self.assertEqual(balloon_emi_amount, "")
        self.assertEqual(balloon_payment_days_delta, "1")

        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

        endtoend.balances_helper.wait_for_account_balances(
            loan_account_id,
            expected_balances=[(dimensions.PRINCIPAL, "20000")],
        )

        derived_params = endtoend.core_api_helper.get_account_derived_parameters(loan_account_id)
        self.assertEqual("13", derived_params["remaining_term"], "remaining term at start of loan")
        self.assertEqual(
            "20000",
            derived_params["remaining_principal"],
            "remaining principal at start of loan",
        )
        self.assertEqual(
            "20000.00",
            derived_params["total_outstanding_debt"],
            "total outstanding debt at start of loan",
        )
        self.assertEqual(
            "0",
            derived_params["outstanding_payments"],
            "outstanding_payments at start of loan",
        )
        self.assertEqual(
            "813.55",
            derived_params["expected_emi"],
            "expected emi at start of loan",
        )
        self.assertEqual(
            next_repayment_date.strftime("%Y-%m-%d"),
            derived_params["next_repayment_date"],
            "next repayment date at start of loan",
        )
        self.assertEqual(
            next_overdue_date.strftime("%Y-%m-%d"),
            derived_params["next_overdue_date"],
            "next overdue date at start of loan",
        )
        self.assertEqual(
            "21052.63",
            derived_params["total_early_repayment_amount"],
            "total early repayment amount",
        )

    def test_workflow_apply_for_fixed_rate_loan_with_balloon_interest_only(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid[
                    "balloon_loan_interest_only_repayment"
                ],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_loan_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_loan_parameters",
            event_name="loan_parameters_selected",
            context={
                "fixed_interest_loan": "True",
                "total_term": "13",
                "principal": "20000",
                "repayment_day": "1",
                "interest_accrual_rest_type": "monthly",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_balloon_payment_date")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_balloon_payment_date",
            event_name="balloon_date_selected",
            context={
                "balloon_payment_days": "1",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "confirm_balloon_payment_date")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_balloon_payment_date",
            event_name="balloon_date_confirmed",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_fixed_interest_rate")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_fixed_interest_rate",
            event_name="fixed_interest_rate_captured",
            context={"fixed_interest_rate": "0.0345"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_vault_account_details")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account_details",
            event_name="vault_account_captured",
            context={"deposit_account": dummy_current_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "determine_upfront_fee")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="determine_upfront_fee",
            event_name="no_upfront_fee_selected",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        loan_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        loan_account = endtoend.contracts_helper.get_account(loan_account_id)

        fixed_interest_rate = loan_account["instance_param_vals"]["fixed_interest_rate"]
        fixed_interest_loan = loan_account["instance_param_vals"]["fixed_interest_loan"]
        variable_rate_adjustment = loan_account["instance_param_vals"]["variable_rate_adjustment"]
        repayment_holiday_impact = loan_account["instance_param_vals"][
            "repayment_holiday_impact_preference"
        ]
        interest_accrual_rest_type = loan_account["instance_param_vals"][
            "interest_accrual_rest_type"
        ]
        balloon_payment_amount = loan_account["instance_param_vals"]["balloon_payment_amount"]
        balloon_emi_amount = loan_account["instance_param_vals"]["balloon_emi_amount"]
        balloon_payment_days_delta = loan_account["instance_param_vals"][
            "balloon_payment_days_delta"
        ]
        loan_start_date = loan_account["instance_param_vals"]["loan_start_date"]
        repayment_period = loan_template_params["repayment_period"]
        loan_start_day = datetime.strptime(loan_start_date, "%Y-%m-%d").day

        # If loan taken out on 1st, next_payment_date is in 1 month
        # otherwise it'll be the month after that
        month_delta = 1 if loan_start_day == 1 else 2

        next_repayment_date = (datetime.today() + relativedelta(months=month_delta)).replace(day=1)
        next_overdue_date = next_repayment_date + relativedelta(days=int(repayment_period))

        self.assertEqual(fixed_interest_rate, "0.0345")
        self.assertEqual(fixed_interest_loan, "True")
        self.assertEqual(variable_rate_adjustment, "0")
        self.assertEqual(repayment_holiday_impact, "increase_emi")
        self.assertEqual(interest_accrual_rest_type, "monthly")
        self.assertEqual(balloon_payment_amount, "")
        self.assertEqual(balloon_emi_amount, "")
        self.assertEqual(balloon_payment_days_delta, "1")

        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

        endtoend.balances_helper.wait_for_account_balances(
            loan_account_id,
            expected_balances=[
                (
                    dimensions.PRINCIPAL,
                    "20000",
                )
            ],
        )

        derived_params = endtoend.core_api_helper.get_account_derived_parameters(loan_account_id)
        self.assertEqual("13", derived_params["remaining_term"], "remaining term at start of loan")
        self.assertEqual(
            "20000",
            derived_params["remaining_principal"],
            "remaining principal at start of loan",
        )
        self.assertEqual(
            "20000.00",
            derived_params["total_outstanding_debt"],
            "total outstanding debt at start of loan",
        )
        self.assertEqual(
            "0",
            derived_params["outstanding_payments"],
            "outstanding_payments at start of loan",
        )
        self.assertEqual(
            "0",
            derived_params["expected_emi"],
            "expected emi at start of loan",
        )
        self.assertEqual(
            next_repayment_date.strftime("%Y-%m-%d"),
            derived_params["next_repayment_date"],
            "next repayment date at start of loan",
        )
        self.assertEqual(
            next_overdue_date.strftime("%Y-%m-%d"),
            derived_params["next_overdue_date"],
            "next overdue date at start of loan",
        )
        self.assertEqual(
            "21052.63",
            derived_params["total_early_repayment_amount"],
            "total early repayment amount",
        )

    def test_workflow_apply_for_fixed_rate_loan_with_balloon_no_repayment(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid[
                    "balloon_loan_no_repayment"
                ],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_loan_parameters_no_repayment")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_loan_parameters_no_repayment",
            event_name="loan_parameters_chosen",
            context={
                "fixed_interest_loan": "True",
                "total_term": "13",
                "principal": "20000",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_fixed_interest_rate")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_fixed_interest_rate",
            event_name="fixed_interest_rate_captured",
            context={"fixed_interest_rate": "0.0345"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_vault_account_details")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account_details",
            event_name="vault_account_captured",
            context={"deposit_account": dummy_current_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "determine_upfront_fee")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="determine_upfront_fee",
            event_name="no_upfront_fee_selected",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        loan_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        loan_account = endtoend.contracts_helper.get_account(loan_account_id)

        fixed_interest_rate = loan_account["instance_param_vals"]["fixed_interest_rate"]
        fixed_interest_loan = loan_account["instance_param_vals"]["fixed_interest_loan"]
        variable_rate_adjustment = loan_account["instance_param_vals"]["variable_rate_adjustment"]
        repayment_holiday_impact = loan_account["instance_param_vals"][
            "repayment_holiday_impact_preference"
        ]
        interest_accrual_rest_type = loan_account["instance_param_vals"][
            "interest_accrual_rest_type"
        ]

        loan_start_date = datetime.strptime(
            loan_account["instance_param_vals"]["loan_start_date"], "%Y-%m-%d"
        )
        repayment_period = loan_template_params["repayment_period"]

        # no repayment loan does not have periodic scheduling, only an one-off event
        # therefore
        # 1. it does not require repayment_day param; however, it was decided the param should not
        # be optional, as all other loan types need it
        # 2. however, in this case, the value of the param does not matter as long as the contract
        # can be uploaded (comsopision pattern should alleviate this trade off in the future)
        # 3. the one-off repayment event does not need repayment_day value to be worked out, and
        # does not have the restriction of having to be run on or before 28th of a month
        next_repayment_date = loan_start_date + relativedelta(months=13)
        next_overdue_date = next_repayment_date + relativedelta(days=int(repayment_period))

        self.assertEqual(fixed_interest_rate, "0.0345")
        self.assertEqual(fixed_interest_loan, "True")
        self.assertEqual(variable_rate_adjustment, "0")
        self.assertEqual(repayment_holiday_impact, "increase_emi")
        self.assertEqual(interest_accrual_rest_type, "daily")

        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

        endtoend.balances_helper.wait_for_account_balances(
            loan_account_id,
            expected_balances=[
                (
                    dimensions.PRINCIPAL,
                    "20000",
                )
            ],
        )

        derived_params = endtoend.core_api_helper.get_account_derived_parameters(loan_account_id)
        self.assertEqual("13", derived_params["remaining_term"], "remaining term at start of loan")
        self.assertEqual(
            "20000",
            derived_params["remaining_principal"],
            "remaining principal at start of loan",
        )
        self.assertEqual(
            "20000.00",
            derived_params["total_outstanding_debt"],
            "total outstanding debt at start of loan",
        )
        self.assertEqual(
            "0",
            derived_params["outstanding_payments"],
            "outstanding_payments at start of loan",
        )
        self.assertEqual(
            "0",
            derived_params["expected_emi"],
            "expected emi at start of loan",
        )
        self.assertEqual(
            next_repayment_date.strftime("%Y-%m-%d"),
            derived_params["next_repayment_date"],
            "next repayment date at start of loan",
        )
        self.assertEqual(
            next_overdue_date.strftime("%Y-%m-%d"),
            derived_params["next_overdue_date"],
            "next overdue date at start of loan",
        )
        self.assertEqual(
            "21052.63",
            derived_params["total_early_repayment_amount"],
            "total early repayment amount",
        )

    def test_account_creation_with_fixed_upfront_fee_subtracted(self):
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_APPLICATION",
            context={
                "account_id": dummy_current_account_id,
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["loan"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_loan_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_loan_parameters",
            event_name="loan_parameters_selected",
            context={
                "fixed_interest_loan": "False",
                "total_term": "13",
                "principal": "15000",
                "repayment_day": "1",
                "interest_accrual_rest_type": "daily",
            },
        )

        # variable rate 0.129971 + adjustment -0.13 < 0
        endtoend.workflows_helper.wait_for_state(wf_id, "capture_variable_rate_adjustment")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_variable_rate_adjustment",
            event_name="variable_rate_adjustment_captured",
            context={"variable_rate_adjustment": "-0.13"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "invalid_variable_rate_adjustment")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="invalid_variable_rate_adjustment",
            event_name="retry_variable_rate_adjustment_input",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_variable_rate_adjustment")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_variable_rate_adjustment",
            event_name="variable_rate_adjustment_captured",
            context={"variable_rate_adjustment": "0.01"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_vault_account_details")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account_details",
            event_name="vault_account_captured",
            context={"deposit_account": dummy_current_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "determine_upfront_fee")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="determine_upfront_fee",
            event_name="upfront_fee_selected",
            context={"upfront_fee": "2000"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_fee_transfer_method")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_fee_transfer_method",
            event_name="fee_transfer_method_selected",
            context={"amortise_upfront_fee": "False"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        loan_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        loan_account = endtoend.contracts_helper.get_account(loan_account_id)

        fixed_interest_rate = loan_account["instance_param_vals"]["fixed_interest_rate"]
        fixed_interest_loan = loan_account["instance_param_vals"]["fixed_interest_loan"]
        variable_rate_adjustment = loan_account["instance_param_vals"]["variable_rate_adjustment"]
        interest_accrual_rest_type = loan_account["instance_param_vals"][
            "interest_accrual_rest_type"
        ]

        self.assertEqual(fixed_interest_rate, "0")
        self.assertEqual(fixed_interest_loan, "False")
        self.assertEqual(variable_rate_adjustment, "0.01")
        self.assertEqual(interest_accrual_rest_type, "daily")

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                loan_account["id"]: [
                    (
                        dimensions.PRINCIPAL,
                        "15000",
                    )
                ],
                dummy_current_account_id: [
                    (
                        dimensions.DEFAULT,
                        "13000",
                    )
                ],
            }
        )
        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

    def test_account_creation_with_percentage_upfront_fee_subtracted(self):
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_APPLICATION",
            context={
                "account_id": dummy_current_account_id,
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["loan"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_loan_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_loan_parameters",
            event_name="loan_parameters_selected",
            context={
                "fixed_interest_loan": "False",
                "total_term": "13",
                "principal": "15000",
                "repayment_day": "1",
                "interest_accrual_rest_type": "daily",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_variable_rate_adjustment")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_variable_rate_adjustment",
            event_name="variable_rate_adjustment_captured",
            context={"variable_rate_adjustment": "0.01"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_vault_account_details")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account_details",
            event_name="vault_account_captured",
            context={"deposit_account": dummy_current_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "determine_upfront_fee")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="determine_upfront_fee",
            event_name="upfront_fee_percentage_selected",
            context={"upfront_fee_percentage": "10"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_fee_transfer_method")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_fee_transfer_method",
            event_name="fee_transfer_method_selected",
            context={"amortise_upfront_fee": "False"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        loan_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        loan_account = endtoend.contracts_helper.get_account(loan_account_id)

        fixed_interest_rate = loan_account["instance_param_vals"]["fixed_interest_rate"]
        fixed_interest_loan = loan_account["instance_param_vals"]["fixed_interest_loan"]
        variable_rate_adjustment = loan_account["instance_param_vals"]["variable_rate_adjustment"]

        self.assertEqual(fixed_interest_rate, "0")
        self.assertEqual(fixed_interest_loan, "False")
        self.assertEqual(variable_rate_adjustment, "0.01")

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                loan_account["id"]: [
                    (
                        dimensions.PRINCIPAL,
                        "15000",
                    )
                ],
                dummy_current_account_id: [
                    (
                        dimensions.DEFAULT,
                        "13500",
                    )
                ],
            }
        )

        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

    def test_account_creation_with_fixed_upfront_fee_added(self):
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_APPLICATION",
            context={
                "account_id": dummy_current_account_id,
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["loan"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_loan_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_loan_parameters",
            event_name="loan_parameters_selected",
            context={
                "fixed_interest_loan": "False",
                "total_term": "13",
                "principal": "15000",
                "repayment_day": "1",
                "interest_accrual_rest_type": "daily",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_variable_rate_adjustment")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_variable_rate_adjustment",
            event_name="variable_rate_adjustment_captured",
            context={"variable_rate_adjustment": "0.00"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_vault_account_details")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account_details",
            event_name="vault_account_captured",
            context={"deposit_account": dummy_current_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "determine_upfront_fee")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="determine_upfront_fee",
            event_name="upfront_fee_selected",
            context={"upfront_fee": "2000"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_fee_transfer_method")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_fee_transfer_method",
            event_name="fee_transfer_method_selected",
            context={"amortise_upfront_fee": "True"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        loan_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        loan_account = endtoend.contracts_helper.get_account(loan_account_id)

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                loan_account["id"]: [
                    (
                        dimensions.PRINCIPAL,
                        "17000",
                    )
                ],
                dummy_current_account_id: [
                    (
                        dimensions.DEFAULT,
                        "15000",
                    )
                ],
            }
        )

        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

    def test_account_creation_with_percentage_upfront_fee_added(self):
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_APPLICATION",
            context={
                "account_id": dummy_current_account_id,
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["loan"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_loan_parameters")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_loan_parameters",
            event_name="loan_parameters_selected",
            context={
                "fixed_interest_loan": "False",
                "total_term": "13",
                "principal": "15000",
                "repayment_day": "1",
                "interest_accrual_rest_type": "daily",
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_variable_rate_adjustment")
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_variable_rate_adjustment",
            event_name="variable_rate_adjustment_captured",
            context={"variable_rate_adjustment": "0.00"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_vault_account_details")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account_details",
            event_name="vault_account_captured",
            context={"deposit_account": dummy_current_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "determine_upfront_fee")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="determine_upfront_fee",
            event_name="upfront_fee_percentage_selected",
            context={"upfront_fee_percentage": "10"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_fee_transfer_method")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_fee_transfer_method",
            event_name="fee_transfer_method_selected",
            context={"amortise_upfront_fee": "True"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        loan_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        loan_account = endtoend.contracts_helper.get_account(loan_account_id)

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                loan_account["id"]: [
                    (
                        dimensions.PRINCIPAL,
                        "16500",
                    )
                ],
                dummy_current_account_id: [
                    (
                        dimensions.DEFAULT,
                        "15000",
                    )
                ],
            }
        )

        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

    def test_early_repayment_manual_fee(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = loan_instance_params.copy()
        instance_params["deposit_account"] = dummy_current_account_id
        loan_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_EARLY_REPAYMENT", context={"account_id": loan_account["id"]}
        )

        endtoend.workflows_helper.send_event(
            wf_id, event_state="choose_fee_type", event_name="manual_fee", context={}
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_fee_details",
            event_name="fee_details_given",
            context={"fee_amount": "123"},
        )

        endtoend.balances_helper.wait_for_account_balances(
            loan_account["id"],
            expected_balances=[
                (
                    dimensions.PRINCIPAL,
                    "1000",
                ),
                (
                    dimensions.PENALTIES,
                    "123",
                ),
            ],
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="continue_and_refresh_balances",
            event_name="continue_with_early_repayment",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_repayment_account")

    def test_early_repayment_auto_erc_closes_account(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=dummy_current_account_id, amount="500000", denomination=DEFAULT_DENOMINATION
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        instance_params = loan_instance_params.copy()
        instance_params["deposit_account"] = dummy_current_account_id
        loan_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_EARLY_REPAYMENT", context={"account_id": loan_account["id"]}
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
            loan_account["id"],
            expected_balances=[
                (
                    dimensions.PRINCIPAL,
                    "1000",
                ),
                (
                    dimensions.PENALTIES,
                    "100",
                ),
            ],
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="continue_and_refresh_balances",
            event_name="continue_with_early_repayment",
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_repayment_account",
            event_name="account_selected",
            context={"repayment_account_id": dummy_current_account_id},
        )
        endtoend.workflows_helper.wait_for_state(
            wf_id=wf_id, state_name="account_charged_successfully"
        )

        # Early repayment should trigger a contract initiated workflow to close the repaid loan
        loan_closure_wf = endtoend.workflows_helper.wait_for_smart_contract_initiated_workflows(
            account_id=loan_account["id"],
            workflow_definition_id=endtoend.testhandle.workflow_definition_id_mapping[
                "LOAN_CLOSURE"
            ],
        )[0]

        # Once the contract-initiated workflow is finished, the account should be closed
        endtoend.workflows_helper.wait_for_state(
            loan_closure_wf["wf_instance_id"], "account_closed_successfully"
        )
        loan_account = endtoend.contracts_helper.get_account(loan_account["id"])
        self.assertEqual("ACCOUNT_STATUS_CLOSED", loan_account["status"])

        # Trying to close again should be handled by the workflow
        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_CLOSURE", context={"account_id": loan_account["id"]}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "account_already_closed")
        loan_account = endtoend.contracts_helper.get_account(loan_account["id"])
        self.assertEqual("ACCOUNT_STATUS_CLOSED", loan_account["status"])

    def test_early_repayment_skips_fee_posting_if_manual_or_erc_fee_zero(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = loan_instance_params.copy()
        instance_params["deposit_account"] = dummy_current_account_id
        loan_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        # ERC Fee Route Test
        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_EARLY_REPAYMENT", context={"account_id": loan_account["id"]}
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

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="continue_and_refresh_balances",
            event_name="continue_with_early_repayment",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_repayment_account")

        # Manual Fee Route Test
        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_EARLY_REPAYMENT", context={"account_id": loan_account["id"]}
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

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="continue_and_refresh_balances",
            event_name="continue_with_early_repayment",
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_repayment_account")

    def test_minimum_repayment_loan_early_repayment(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=dummy_current_account_id, amount="500000", denomination=DEFAULT_DENOMINATION
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        instance_params = loan_balloon_min_repayment_instance_params.copy()
        instance_params["deposit_account"] = dummy_current_account_id
        loan_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="balloon_loan_min_repayment",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_EARLY_REPAYMENT", context={"account_id": loan_account["id"]}
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
            loan_account["id"],
            expected_balances=[
                (
                    dimensions.PRINCIPAL,
                    "1000",
                ),
                (
                    dimensions.PENALTIES,
                    "100",
                ),
            ],
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="continue_and_refresh_balances",
            event_name="continue_with_early_repayment",
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_repayment_account",
            event_name="account_selected",
            context={"repayment_account_id": dummy_current_account_id},
        )

        endtoend.workflows_helper.wait_for_state(
            wf_id=wf_id, state_name="account_charged_successfully"
        )

        # Early repayment should trigger a contract initiated workflow to close the repaid loan
        loan_closure_wf = endtoend.workflows_helper.wait_for_smart_contract_initiated_workflows(
            account_id=loan_account["id"],
            workflow_definition_id=endtoend.testhandle.workflow_definition_id_mapping[
                "LOAN_CLOSURE"
            ],
        )[0]

        # Once the contract-initiated workflow is finished, the account should be closed
        endtoend.workflows_helper.wait_for_state(
            loan_closure_wf["wf_instance_id"], "account_closed_successfully"
        )
        loan_account = endtoend.contracts_helper.get_account(loan_account["id"])
        self.assertEqual("ACCOUNT_STATUS_CLOSED", loan_account["status"])

        # Trying to close again should be handled by the workflow
        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_CLOSURE", context={"account_id": loan_account["id"]}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "account_already_closed")
        loan_account = endtoend.contracts_helper.get_account(loan_account["id"])
        self.assertEqual("ACCOUNT_STATUS_CLOSED", loan_account["status"])

    def test_close_loan_workflow_with_balance(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = loan_instance_params.copy()
        instance_params["deposit_account"] = dummy_current_account_id
        loan_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

        endtoend.balances_helper.wait_for_account_balances(
            loan_account["id"],
            expected_balances=[
                (
                    dimensions.PRINCIPAL,
                    "1000",
                )
            ],
        )

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_CLOSURE", context={"account_id": loan_account["id"]}
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closure_failure")

        loan_account = endtoend.contracts_helper.get_account(loan_account["id"])

        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

    def test_mark_delinquency_workflow(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = loan_instance_params.copy()
        instance_params["deposit_account"] = dummy_current_account_id
        loan_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_MARK_DELINQUENT", context={"account_id": loan_account["id"]}
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_delinquency_set")

        flag_status = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping["ACCOUNT_DELINQUENT"],
            account_ids=[loan_account["id"]],
        )

        self.assertEqual(flag_status[0]["account_id"], loan_account["id"])

    def test_change_loan_repayment_day(self):

        cust_id = endtoend.core_api_helper.create_customer()

        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = loan_instance_params.copy()
        instance_params["deposit_account"] = dummy_current_account_id
        loan_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        self.assertEqual("ACCOUNT_STATUS_OPEN", loan_account["status"])

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_REPAYMENT_DAY_CHANGE",
            context={"account_id": loan_account["id"], "user_id": cust_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "too_soon_to_change_repayment_day")

        loan_account = endtoend.contracts_helper.get_account(loan_account["id"])
        repayment_day = loan_account["instance_param_vals"]["repayment_day"]

        self.assertEqual("1", repayment_day)

        account_schedules = endtoend.schedule_helper.get_account_schedules(loan_account["id"])

        repayment_day_schedule = account_schedules["REPAYMENT_DAY_SCHEDULE"]

        self.assertEqual(
            1,
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
            loan_account["id"],
        )

        wf_id_2 = endtoend.workflows_helper.start_workflow(
            "LOAN_REPAYMENT_DAY_CHANGE",
            context={"account_id": loan_account["id"], "user_id": cust_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id_2, "repayment_day_cannot_be_updated")

        loan_account = endtoend.contracts_helper.get_account(loan_account["id"])
        current_repayment_day = loan_account["instance_param_vals"]["repayment_day"]

        self.assertEqual("1", current_repayment_day)

        account_schedules = endtoend.schedule_helper.get_account_schedules(loan_account["id"])

        self.assertEqual(
            1,
            datetime.strptime(
                account_schedules["REPAYMENT_DAY_SCHEDULE"]["next_run_timestamp"],
                "%Y-%m-%dT%H:%M:%SZ",
            ).day,
        )

        # ensure new schedule will start after today to avoid past event catch-ups
        self.assertGreater(
            datetime.strptime(
                repayment_day_schedule["start_timestamp"], "%Y-%m-%dT%H:%M:%SZ"
            ).date(),
            datetime.utcnow().date(),
        )

        no_repayment_balloon_loan = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="balloon_loan_no_repayment",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        wf_id_3 = endtoend.workflows_helper.start_workflow(
            "LOAN_REPAYMENT_DAY_CHANGE",
            context={"account_id": no_repayment_balloon_loan["id"], "user_id": cust_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id_3, "repayment_day_cannot_be_updated")

    def test_repayment_holiday_workflow(self):
        repayment_day = 21

        cust_id = endtoend.core_api_helper.create_customer()

        instance_params = loan_instance_params.copy()
        instance_params["repayment_day"] = str(repayment_day)
        loan_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        instance_params = endtoend.contracts_helper.get_account(loan_account["id"])[
            "instance_param_vals"
        ]
        balloon_payment_days_delta = instance_params["balloon_payment_days_delta"]
        self.assertEqual("", balloon_payment_days_delta)

        derived_params = endtoend.core_api_helper.get_account_derived_parameters(loan_account["id"])
        next_repayment_date = derived_params["next_repayment_date"]
        first_allowed_repayment_date = datetime.strptime(next_repayment_date, "%Y-%m-%d")

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_REPAYMENT_HOLIDAY_APPLICATION",
            context={"account_id": loan_account["id"]},
        )

        latest_state = endtoend.workflows_helper.wait_for_state(
            wf_id=wf_id, state_name="capture_repayment_holiday_period"
        )

        # 1. create a flag in the past
        start_time = first_allowed_repayment_date - relativedelta(months=3)
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
            "repayment_holiday_impact_preference"
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
            "LOAN_REPAYMENT_HOLIDAY_APPLICATION",
            context={"account_id": loan_account["id"]},
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

        balloon_loan_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="balloon_loan_min_repayment",
            instance_param_vals=loan_balloon_min_repayment_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )

        wf_id_4 = endtoend.workflows_helper.start_workflow(
            "LOAN_REPAYMENT_HOLIDAY_APPLICATION",
            context={"account_id": balloon_loan_account["id"]},
        )

        endtoend.workflows_helper.wait_for_state(wf_id_4, "repayment_holiday_application_failed")

    def test_workflow_top_up_loan_apply_variable_interest(self):
        """
        Apply for variable interest loan
        """
        cust_id = endtoend.core_api_helper.create_customer()
        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]
        instance_params = loan_instance_params.copy()
        instance_params["principal"] = "1000"
        instance_params["fixed_interest_loan"] = "False"
        instance_params["fixed_interest_rate"] = "0"
        instance_params["variable_rate_adjustment"] = "0.011"
        instance_params["deposit_account"] = dummy_current_account_id
        loan_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        loan_account_id = loan_account["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_TOP_UP",
            context={
                "account_id": loan_account_id,
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["loan"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="request_top_up",
            event_name="loan_details_given",
            context={
                "reason_for_loan": "TEST_TOP_UP",
                "desired_principal": "3000",
                "loan_term_extension": "12",
                "new_interest_rate": "0.012",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account_details",
            event_name="vault_account_captured",
            context={"disbursement_account_id": dummy_current_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "top_up_application_success")

        endtoend.accounts_helper.wait_for_account_update(
            loan_account_id, "instance_param_vals_update"
        )
        # Parameters should be changed at this point

        loan = endtoend.contracts_helper.get_account(loan_account_id)
        new_variable_rate_adjustment = loan["instance_param_vals"]["variable_rate_adjustment"]
        new_total_term = loan["instance_param_vals"]["total_term"]
        new_principal = loan["instance_param_vals"]["principal"]
        loan_start_date = loan["instance_param_vals"]["loan_start_date"]

        self.assertEqual(
            "0.012",
            new_variable_rate_adjustment,
            "variable_rate_adjustment parameter updated",
        )
        self.assertEqual("24", new_total_term, "total_term parameter updated")
        self.assertEqual("4000", new_principal, "principal parameter updated")
        self.assertEqual(
            datetime.utcnow().strftime("%Y-%m-%d"),
            loan_start_date,
            "loan_start_date parameter updated",
        )

        endtoend.balances_helper.wait_for_account_balances(
            loan_account_id,
            expected_balances=[
                (
                    dimensions.PRINCIPAL,
                    "4000",
                )
            ],
            description="Loan principal topped up",
        )

        derived_params = endtoend.core_api_helper.get_account_derived_parameters(loan_account_id)
        self.assertEqual(
            int(derived_params.get("remaining_term")), 24, "remaining term after topup"
        )

    def test_workflow_top_up_success_and_recheck_balance_error(self):
        """
        Open Vault current account and apply for fixed interest loan.
        Top up loan with workflow.
        Before completion of first top-up, start another top-up which completes successfully.
        Ensure the first top-up workflow is cancelled.
        """
        cust_id = endtoend.core_api_helper.create_customer()
        dummy_current_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_current_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]
        instance_params = loan_instance_params.copy()
        instance_params["principal"] = "2500"
        instance_params["deposit_account"] = dummy_current_account_id
        loan_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        loan_account_id = loan_account["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "LOAN_TOP_UP",
            context={
                "account_id": loan_account_id,
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["loan"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="request_top_up",
            event_name="loan_details_given",
            context={
                "reason_for_loan": "TEST_TOP_UP",
                "desired_principal": "3000",
                "loan_term_extension": "24",
                "new_interest_rate": "0.1212",
            },
        )

        # Now do another successful top up before we have completed the first one
        wf_id2 = endtoend.workflows_helper.start_workflow(
            "LOAN_TOP_UP",
            context={
                "account_id": loan_account_id,
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["loan"],
            },
        )
        endtoend.workflows_helper.send_event(
            wf_id2,
            event_state="request_top_up",
            event_name="loan_details_given",
            context={
                "reason_for_loan": "TEST_TOP_UP2",
                "desired_principal": "2000",
                "loan_term_extension": "24",
                "new_interest_rate": "0.1213",
            },
        )
        endtoend.workflows_helper.send_event(
            wf_id2,
            event_state="capture_vault_account_details",
            event_name="vault_account_captured",
            context={"disbursement_account_id": dummy_current_account_id},
        )
        endtoend.workflows_helper.wait_for_state(wf_id2, "top_up_application_success")
        endtoend.accounts_helper.wait_for_account_update(
            loan_account_id, "instance_param_vals_update"
        )
        # Parameters should be changed at this point
        loan = endtoend.contracts_helper.get_account(loan_account_id)
        new_fixed_interest_rate = loan["instance_param_vals"]["fixed_interest_rate"]
        new_total_term = loan["instance_param_vals"]["total_term"]
        new_principal = loan["instance_param_vals"]["principal"]
        loan_start_date = loan["instance_param_vals"]["loan_start_date"]
        self.assertEqual("0.1213", new_fixed_interest_rate, "fixed_interest_rate parameter updated")
        self.assertEqual("36", new_total_term, "total_term parameter updated")
        self.assertEqual("4500", new_principal, "principal parameter updated")
        self.assertEqual(
            datetime.utcnow().strftime("%Y-%m-%d"),
            loan_start_date,
            "loan_start_date parameter updated",
        )
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                loan_account_id: [
                    (
                        dimensions.PRINCIPAL,
                        "4500",
                    )
                ],
                dummy_current_account_id: [
                    (
                        dimensions.DEFAULT,
                        "4500",
                    )
                ],
            },
            description="Loan principal topped up and Current account balance after top up",
        )
        derived_params = endtoend.core_api_helper.get_account_derived_parameters(loan_account_id)
        self.assertEqual(int(derived_params.get("remaining_term")), 36, "remaining term 36")

        # Now continue the first workflow to the next steps, it should error out
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_vault_account_details",
            event_name="vault_account_captured",
            context={"disbursement_account_id": dummy_current_account_id},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_details_changed_error")

    def test_balloon_payment_schedule_created(self):
        """
        Test that when we create an balloon loan
        that the BALLOON_PAYMENT_SCHEDULE is created
        """
        cust_id = endtoend.core_api_helper.create_customer()
        non_balloon_loan_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="loan",
            instance_param_vals=loan_instance_params,
            permitted_denominations=[DEFAULT_DENOMINATION],
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        non_balloon_loan_account_schedules = endtoend.schedule_helper.get_account_schedules(
            non_balloon_loan_id, []
        )
        self.assertTrue("BALLOON_PAYMENT_SCHEDULE" not in non_balloon_loan_account_schedules)

        balloon_loan_id_balloon_days_delta_set = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="balloon_loan_min_repayment",
            instance_param_vals=loan_balloon_min_repayment_instance_params,
            permitted_denominations=[DEFAULT_DENOMINATION],
            status="ACCOUNT_STATUS_OPEN",
        )

        balloon_loan_id = balloon_loan_id_balloon_days_delta_set["id"]
        balloon_loan_start_date = datetime.strptime(
            balloon_loan_id_balloon_days_delta_set["instance_param_vals"]["loan_start_date"],
            "%Y-%m-%d",
        )

        balloon_loan_account_schedules = endtoend.schedule_helper.get_account_schedules(
            balloon_loan_id, []
        )
        self.assertTrue("BALLOON_PAYMENT_SCHEDULE" in balloon_loan_account_schedules)

        balloon_payment_schedule = balloon_loan_account_schedules["BALLOON_PAYMENT_SCHEDULE"]
        expected_schedule_start_date = datetime.strftime(
            balloon_loan_start_date + relativedelta(days=1),
            "%Y-%m-%dT%H:%M:%SZ",
        )

        expected_schedule_end_date = expected_schedule_start_date

        expected_schedule_next_run_time = None
        self.assertEqual(
            expected_schedule_start_date,
            balloon_payment_schedule["start_timestamp"],
            "schedule start date",
        )
        self.assertEqual(
            expected_schedule_end_date,
            balloon_payment_schedule["end_timestamp"],
            "schedule end date",
        )
        self.assertEqual(
            expected_schedule_next_run_time,
            balloon_payment_schedule["next_run_timestamp"],
            "schedule next run time",
        )


if __name__ == "__main__":
    endtoend.runtests()
