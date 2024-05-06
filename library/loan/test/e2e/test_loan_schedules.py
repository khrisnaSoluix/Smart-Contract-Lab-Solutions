# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from zoneinfo import ZoneInfo

# library
from library.loan.contracts.template import loan
from library.loan.test import dimensions, files
from library.loan.test.e2e import accounts, parameters

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
from inception_sdk.test_framework.endtoend.contracts_helper import ContractNotificationResourceType

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = accounts.internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "loan": {
        "path": files.LOAN_CONTRACT,
        "template_params": parameters.default_template,
    },
    "dummy_account": {
        "path": DUMMY_CONTRACT,
    },
}

ACCRUAL_EVENT = loan.interest_accrual.ACCRUAL_EVENT
DUE_AMOUNT_CALCULATION_EVENT = loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
CHECK_OVERDUE_EVENT = loan.overdue.CHECK_OVERDUE_EVENT


class LoanProductSchedulesTest(endtoend.AcceleratedEnd2EndTest):
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {"loan": [ACCRUAL_EVENT, DUE_AMOUNT_CALCULATION_EVENT]}
    )
    def test_initial_accrual(self):
        endtoend.standard_setup()
        opening_date = datetime(2022, 4, 27, tzinfo=ZoneInfo("UTC"))
        customer_id = endtoend.core_api_helper.create_customer()

        dummy_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        dummy_account_id = dummy_account["id"]

        instance_params = {
            **parameters.default_instance,
            loan.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
        }
        loan_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        loan_account_id = loan_account["id"]
        endtoend.balances_helper.wait_for_account_balances(
            account_id=loan_account_id,
            expected_balances=[(dimensions.PRINCIPAL, "3000"), (dimensions.EMI, "254.22")],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=loan_account_id,
            schedule_name="ACCRUE_INTEREST",
            effective_date=datetime(2022, 4, 28, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=loan_account_id,
            expected_balances=[
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.25479"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=loan_account_id,
            schedule_name=ACCRUAL_EVENT,
            effective_date=datetime(2022, 4, 29, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=loan_account_id,
            expected_balances=[
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.50958"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=loan_account_id,
            schedule_name=DUE_AMOUNT_CALCULATION_EVENT,
            effective_date=datetime(2022, 5, 28, 0, 1, 0, tzinfo=ZoneInfo("UTC")),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=loan_account_id,
            expected_balances=[
                (dimensions.PRINCIPAL, "2746.04"),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                (dimensions.PRINCIPAL_DUE, "253.96"),
                (dimensions.INTEREST_DUE, "0.51"),
            ],
        )

    @endtoend.kafka_helper.kafka_only_test
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {"loan": [DUE_AMOUNT_CALCULATION_EVENT, "CHECK_OVERDUE"]}
    )
    def test_loan_notifications(self):
        endtoend.standard_setup()
        opening_date = datetime(year=2020, month=10, day=1, hour=10, tzinfo=ZoneInfo("UTC"))
        customer_id = endtoend.core_api_helper.create_customer()

        dummy_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        dummy_account_id = dummy_account["id"]
        instance_params = {
            **parameters.default_instance,
            loan.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
            # Fixed Rate
            loan.PARAM_FIXED_RATE_LOAN: "True",
            loan.disbursement.PARAM_PRINCIPAL: "1000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "11",
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.034544",
        }

        loan_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="loan",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        loan_account_id = loan_account["id"]

        # Loan Repayment Schedule Notification
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type="LOAN_REPAYMENT_SCHEDULE",
            notification_details={
                "account_id": loan_account_id,
                "repayment_schedule": (
                    '{"2020-11-11 00:01:00+00:00": ["1", "918.03", "85.85", "81.97", "3.88"], '
                    '"2020-12-11 00:01:00+00:00": ["2", "835.74", "84.90", "82.29", "2.61"], '
                    '"2021-01-11 00:01:00+00:00": ["3", "753.29", "84.90", "82.45", "2.45"], '
                    '"2021-02-11 00:01:00+00:00": ["4", "670.60", "84.90", "82.69", "2.21"], '
                    '"2021-03-11 00:01:00+00:00": ["5", "587.48", "84.90", "83.12", "1.78"], '
                    '"2021-04-11 00:01:00+00:00": ["6", "504.30", "84.90", "83.18", "1.72"], '
                    '"2021-05-11 00:01:00+00:00": ["7", "420.83", "84.90", "83.47", "1.43"], '
                    '"2021-06-11 00:01:00+00:00": ["8", "337.16", "84.90", "83.67", "1.23"], '
                    '"2021-07-11 00:01:00+00:00": ["9", "253.22", "84.90", "83.94", "0.96"], '
                    '"2021-08-11 00:01:00+00:00": ["10", "169.06", "84.90", "84.16", "0.74"], '
                    '"2021-09-11 00:01:00+00:00": ["11", "84.66", "84.90", "84.40", "0.50"], '
                    '"2021-10-11 00:01:00+00:00": ["12", "0", "84.90", "84.66", "0.24"]}'
                ),
            },
            resource_id=str(loan_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=loan_account_id,
            schedule_name=DUE_AMOUNT_CALCULATION_EVENT,
            effective_date=datetime(2020, 11, 11, 0, 1, 0, tzinfo=ZoneInfo("UTC")),
        )

        # Loan Repayment Notification
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
            notification_details={
                "account_id": loan_account_id,
                "repayment_amount": "84.90",
                "overdue_date": "2020-11-18",
            },
            resource_id=str(loan_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=loan_account_id,
            schedule_name=CHECK_OVERDUE_EVENT,
            effective_date=datetime(2020, 11, 18, 0, 0, 2, tzinfo=ZoneInfo("UTC")),
        )

        # Loan Overdue Repayment Notification
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type=loan.REPAYMENT_OVERDUE_NOTIFICATION,
            notification_details={
                "account_id": loan_account_id,
                "late_repayment_fee": "10",
                "overdue_date": "2020-11-18",
                "repayment_amount": "84.90",
            },
            resource_id=str(loan_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )
