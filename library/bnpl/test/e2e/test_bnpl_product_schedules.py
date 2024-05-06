# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone

# library
from library.bnpl.constants import dimensions, files, test_parameters
from library.bnpl.contracts.template import bnpl

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
from inception_sdk.test_framework.endtoend.contracts_helper import ContractNotificationResourceType
from inception_sdk.test_framework.endtoend.core_api_helper import AccountStatus

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = test_parameters.internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "bnpl": {
        "path": files.BNPL_CONTRACT,
        "template_params": test_parameters.bnpl_template_params_for_e2e,
    },
    "dummy_account": {"path": DUMMY_CONTRACT},
}


class BNPLSchedulesTest(endtoend.AcceleratedEnd2EndTest):
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {
            "bnpl": [
                bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                bnpl.overdue.CHECK_OVERDUE_EVENT,
                bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT,
                bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT,
            ]
        }
    )
    def test_bnpl_lifecycle(self):
        endtoend.standard_setup()
        opening_date = datetime(year=2020, month=1, day=5, hour=0, minute=0, tzinfo=timezone.utc)
        customer_id = endtoend.core_api_helper.create_customer()
        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )["id"]

        instance_params = {
            **test_parameters.bnpl_instance_params,
            bnpl.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
        }

        # principal is disbursed and due amount is calculated on account creation
        bnpl_account_id = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="bnpl",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )["id"]
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "90"),
                (dimensions.PRINCIPAL_DUE, "30"),
                (dimensions.PRINCIPAL_OVERDUE, "0"),
                (dimensions.PENALTIES, "0"),
            ],
        )

        # account closure rejected due to unpaid debt
        endtoend.core_api_helper.update_account(
            bnpl_account_id,
            AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE,
        )
        endtoend.accounts_helper.wait_for_account_update(
            account_id=bnpl_account_id,
            account_update_type="closure_update",
            target_status="ACCOUNT_UPDATE_STATUS_REJECTED",
        )

        # overdue check is triggered after the repayment period has passed,
        # overdue amount is moved to overdue address, and an overdue notification is sent
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.overdue.CHECK_OVERDUE_EVENT,
            effective_date=datetime(2020, 1, 8, 0, 1, tzinfo=timezone.utc),
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "90"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.PRINCIPAL_OVERDUE, "30"),
                (dimensions.PENALTIES, "0"),
            ],
        )
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type="BUY_NOW_PAY_LATER_OVERDUE_REPAYMENT",
            notification_details={
                "account_id": bnpl_account_id,
                "late_repayment_fee": "25",
                "overdue_date": "2020-01-08",
                "overdue_interest": "0",
                "overdue_principal": "30",
            },
            resource_id=str(bnpl_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        # late repayment check is triggered after the grace period has passed
        # and late repayment fee is charged to the penalties address
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT,
            effective_date=datetime(2020, 1, 10, 0, 1, tzinfo=timezone.utc),
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "90"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.PRINCIPAL_OVERDUE, "30"),
                (dimensions.PENALTIES, "25"),
            ],
        )

        # due amount notification is triggered N days before the next due date where N is the
        # number of days in the notification period, and a due amount notification is sent
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT,
            effective_date=datetime(2020, 2, 3, 1, 2, 3, tzinfo=timezone.utc),
        )
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type="BUY_NOW_PAY_LATER_REPAYMENT",
            notification_details={
                "account_id": bnpl_account_id,
                "due_interest": "0",
                "due_principal": "30",
                "overdue_date": "2020-02-08",
            },
            resource_id=str(bnpl_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        # due amount calculation is triggered and due amount is moved to due address
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
            effective_date=datetime(2020, 2, 5, 0, 1, tzinfo=timezone.utc),
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "60"),
                (dimensions.PRINCIPAL_DUE, "30"),
                (dimensions.PRINCIPAL_OVERDUE, "30"),
                (dimensions.PENALTIES, "25"),
            ],
        )

        # overdue check is triggered after the repayment period has passed,
        # overdue amount is moved to overdue address, and an overdue notification is sent
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.overdue.CHECK_OVERDUE_EVENT,
            effective_date=datetime(2020, 2, 8, 0, 1, tzinfo=timezone.utc),
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "60"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.PRINCIPAL_OVERDUE, "60"),
                (dimensions.PENALTIES, "25"),
            ],
        )
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type="BUY_NOW_PAY_LATER_OVERDUE_REPAYMENT",
            notification_details={
                "account_id": bnpl_account_id,
                "late_repayment_fee": "25",
                "overdue_date": "2020-02-08",
                "overdue_interest": "0",
                "overdue_principal": "30",
            },
            resource_id=str(bnpl_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        # late repayment check is triggered after the grace period has passed
        # and late repayment fee is charged to the penalties address
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT,
            effective_date=datetime(2020, 2, 10, 0, 1, tzinfo=timezone.utc),
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "60"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.PRINCIPAL_OVERDUE, "60"),
                (dimensions.PENALTIES, "50"),
            ],
        )

        # due amount notification is triggered N days before the next due date where N is the
        # number of days in the notification period, and a due amount notification is sent
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT,
            effective_date=datetime(2020, 3, 3, 1, 2, 3, tzinfo=timezone.utc),
        )
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type="BUY_NOW_PAY_LATER_REPAYMENT",
            notification_details={
                "account_id": bnpl_account_id,
                "due_interest": "0",
                "due_principal": "30",
                "overdue_date": "2020-03-08",
            },
            resource_id=str(bnpl_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        # due amount calculation is triggered and due amount is moved to due address
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
            effective_date=datetime(2020, 3, 5, 0, 1, tzinfo=timezone.utc),
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "30"),
                (dimensions.PRINCIPAL_DUE, "30"),
                (dimensions.PRINCIPAL_OVERDUE, "60"),
                (dimensions.PENALTIES, "50"),
            ],
        )

        # repayment to pay off principal overdue
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=bnpl_account_id,
            amount="60",
            denomination=test_parameters.default_denomination,
            value_datetime=datetime(2020, 3, 5, 4, 1, tzinfo=timezone.utc),
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "30"),
                (dimensions.PRINCIPAL_DUE, "30"),
                (dimensions.PRINCIPAL_OVERDUE, "0"),
                (dimensions.PENALTIES, "50"),
            ],
        )

        # repayment to pay off penalties
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=bnpl_account_id,
            amount="50",
            denomination=test_parameters.default_denomination,
            value_datetime=datetime(2020, 3, 5, 5, 1, tzinfo=timezone.utc),
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "30"),
                (dimensions.PRINCIPAL_DUE, "30"),
                (dimensions.PRINCIPAL_OVERDUE, "0"),
                (dimensions.PENALTIES, "0"),
            ],
        )

        # repayment to pay off principal due
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=bnpl_account_id,
            amount="30",
            denomination=test_parameters.default_denomination,
            value_datetime=datetime(2020, 3, 5, 6, 1, tzinfo=timezone.utc),
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "30"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.PRINCIPAL_OVERDUE, "0"),
                (dimensions.PENALTIES, "0"),
            ],
        )

        # account closure is rejected due to unpaid debt
        endtoend.core_api_helper.create_account_update(
            bnpl_account_id, account_update={"closure_update": {}}
        )
        endtoend.accounts_helper.wait_for_account_update(
            account_id=bnpl_account_id,
            account_update_type="closure_update",
            target_status="ACCOUNT_UPDATE_STATUS_REJECTED",
        )

        # overdue check is triggered after the repayment period has passed,
        # no balance updates expected since due principal has been repaid
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.overdue.CHECK_OVERDUE_EVENT,
            effective_date=datetime(2020, 3, 8, 0, 1, tzinfo=timezone.utc),
        )

        # late repayment check is triggered after the grace period has passed,
        # no balance updates expected since due principal has been repaid
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT,
            effective_date=datetime(2020, 3, 10, 0, 1, tzinfo=timezone.utc),
        )

        # due amount notification is triggered N days before the next due date where N is the
        # number of days in the notification period, and a due amount notification is sent
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT,
            effective_date=datetime(2020, 4, 3, 1, 2, 3, tzinfo=timezone.utc),
        )
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type="BUY_NOW_PAY_LATER_REPAYMENT",
            notification_details={
                "account_id": bnpl_account_id,
                "due_interest": "0",
                "due_principal": "30",
                "overdue_date": "2020-04-08",
            },
            resource_id=str(bnpl_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        # due amount calculation is triggered and due amount is moved to due address
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
            effective_date=datetime(2020, 4, 5, 0, 1, tzinfo=timezone.utc),
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "0"),
                (dimensions.PRINCIPAL_DUE, "30"),
                (dimensions.PRINCIPAL_OVERDUE, "0"),
                (dimensions.PENALTIES, "0"),
            ],
        )

        # overdue check is triggered after the repayment period has passed,
        # overdue amount is moved to overdue address, and an overdue notification is sent
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.overdue.CHECK_OVERDUE_EVENT,
            effective_date=datetime(2020, 4, 8, 0, 1, tzinfo=timezone.utc),
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "0"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.PRINCIPAL_OVERDUE, "30"),
                (dimensions.PENALTIES, "0"),
            ],
        )
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type="BUY_NOW_PAY_LATER_OVERDUE_REPAYMENT",
            notification_details={
                "account_id": bnpl_account_id,
                "late_repayment_fee": "25",
                "overdue_date": "2020-04-08",
                "overdue_interest": "0",
                "overdue_principal": "30",
            },
            resource_id=str(bnpl_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        # late repayment check is triggered after the grace period has passed
        # and late repayment fee is charged to the penalties address
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name=bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT,
            effective_date=datetime(2020, 4, 10, 0, 1, tzinfo=timezone.utc),
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "0"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.PRINCIPAL_OVERDUE, "30"),
                (dimensions.PENALTIES, "25"),
            ],
        )

        # delinquency check is triggered after the delinquency period has passed,
        # and a delinquency notification is sent
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=bnpl_account_id,
            schedule_name="CHECK_DELINQUENCY",
            effective_date=datetime(2020, 4, 10, 0, 1, tzinfo=timezone.utc),
        )
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type="BUY_NOW_PAY_LATER_DELINQUENT_NOTIFICATION",
            notification_details={
                "account_id": bnpl_account_id,
            },
            resource_id=str(bnpl_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        # account closure is rejected due to unpaid debt
        endtoend.core_api_helper.create_account_update(
            bnpl_account_id, account_update={"closure_update": {}}
        )
        endtoend.accounts_helper.wait_for_account_update(
            account_id=bnpl_account_id,
            account_update_type="closure_update",
            target_status="ACCOUNT_UPDATE_STATUS_REJECTED",
        )

        # repayment to pay off principal overdue and penalties
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=bnpl_account_id,
            amount="55",
            denomination=test_parameters.default_denomination,
            value_datetime=datetime(2020, 4, 8, 4, 1, tzinfo=timezone.utc),
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "30"),
                (dimensions.PRINCIPAL, "0"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.PRINCIPAL_OVERDUE, "0"),
            ],
        )

        # check for end of loan notification
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type="BUY_NOW_PAY_LATER_LOAN_PAID_OFF",
            notification_details={
                "account_id": bnpl_account_id,
            },
            resource_id=str(bnpl_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        # account closure is accepted
        endtoend.core_api_helper.create_account_update(
            bnpl_account_id, account_update={"closure_update": {}}
        )
        endtoend.accounts_helper.wait_for_account_update(
            account_id=bnpl_account_id,
            account_update_type="closure_update",
            target_status="ACCOUNT_UPDATE_STATUS_COMPLETED",
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=bnpl_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.EMI, "0"),
                (dimensions.PRINCIPAL, "0"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.PRINCIPAL_OVERDUE, "0"),
            ],
        )
