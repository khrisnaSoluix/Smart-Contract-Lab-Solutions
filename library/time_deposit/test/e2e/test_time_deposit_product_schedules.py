# standard libs
import uuid
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test import dimensions, files
from library.time_deposit.test.e2e import accounts, parameters

# inception sdk
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.endtoend.contracts_helper import ContractNotificationResourceType

new_time_deposit_template_params = {**parameters.default_template}
renewed_time_deposit_template_params = {**parameters.default_renewed_template}
instance_params = {
    **parameters.default_instance,
    time_deposit.fixed_interest_accrual.PARAM_FIXED_INTEREST_RATE: "0.35",
}
endtoend.testhandle.CONTRACTS = {
    "new_time_deposit": {
        "path": files.TIME_DEPOSIT_CONTRACT,
        "template_params": new_time_deposit_template_params,
    },
    "renewed_time_deposit": {
        "path": files.TIME_DEPOSIT_CONTRACT,
        "template_params": renewed_time_deposit_template_params,
    },
    "converted_time_deposit": {
        "path": files.TIME_DEPOSIT_CONTRACT,
        "template_params": parameters.default_template.copy(),
    },
}

endtoend.testhandle.CALENDARS = {
    "PUBLIC_HOLIDAYS": ("library/common/calendars/public_holidays.resource.yaml")
}

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = accounts.internal_accounts_tside


class TimeDepositTest(endtoend.AcceleratedEnd2EndTest):
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {
            "new_time_deposit": [
                time_deposit.fixed_interest_accrual.ACCRUAL_EVENT,
                time_deposit.interest_application.APPLICATION_EVENT,
                time_deposit.deposit_period.DEPOSIT_PERIOD_END_EVENT,
                time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT,
                time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
            ],
        }
    )
    def test_time_deposit_lifecycle_with_rollover(self):
        """
        This test illustrates the lifecycle of a time deposit including rollover of principal
        into a renewed time deposit account. How the rollover preference is stored on the account
        resource and determined at account maturity is purely for example purposes only and is not
        mandated by the product.
        """
        endtoend.standard_setup()
        new_time_deposit_opening_datetime = datetime(
            year=2022, month=1, day=1, hour=5, minute=35, second=0, tzinfo=ZoneInfo("UTC")
        )
        accrual_event_datetime = datetime(
            year=2022, month=1, day=2, tzinfo=ZoneInfo("UTC")
        ).replace(
            hour=int(
                new_time_deposit_template_params[
                    time_deposit.fixed_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR
                ]
            ),
            minute=int(
                new_time_deposit_template_params[
                    time_deposit.fixed_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE
                ]
            ),
            second=int(
                new_time_deposit_template_params[
                    time_deposit.fixed_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND
                ]
            ),
        )

        deposit_period_end_datetime = datetime(
            year=2022, month=1, day=6, hour=23, minute=59, second=59, tzinfo=ZoneInfo("UTC")
        )

        interest_application_datetime = new_time_deposit_opening_datetime.replace(
            day=12,
            hour=int(
                new_time_deposit_template_params[
                    time_deposit.interest_application.PARAM_INTEREST_APPLICATION_HOUR
                ]
            ),
            minute=int(
                new_time_deposit_template_params[
                    time_deposit.interest_application.PARAM_INTEREST_APPLICATION_MINUTE
                ]
            ),
            second=int(
                new_time_deposit_template_params[
                    time_deposit.interest_application.PARAM_INTEREST_APPLICATION_SECOND
                ]
            ),
        )

        account_maturity_datetime = (
            new_time_deposit_opening_datetime + relativedelta(months=4, days=1)
        ).replace(hour=0, minute=0, second=0)
        pre_account_maturity_notification_datetime = account_maturity_datetime - relativedelta(
            days=1
        )
        renewed_time_deposit_opening_datetime = account_maturity_datetime + relativedelta(minutes=1)

        customer_id = endtoend.core_api_helper.create_customer()
        time_deposit_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="new_time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            details={"maturity_type": "rollover", "rollover_type": "principal_only"},
            opening_timestamp=new_time_deposit_opening_datetime.isoformat(),
            wait_for_activation=True,
        )
        time_deposit_account_id = time_deposit_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", time_deposit_account["status"])

        # Custom deposits into the account
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="5000",
            account_id=time_deposit_account_id,
            denomination="GBP",
            value_datetime=new_time_deposit_opening_datetime + relativedelta(hours=1),
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=time_deposit_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "5000"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=time_deposit_account_id,
            schedule_name=time_deposit.fixed_interest_accrual.ACCRUAL_EVENT,
            effective_date=accrual_event_datetime,
        )

        # round(5000 * round((0.35/365),10),5) = 4.79452
        endtoend.balances_helper.wait_for_account_balances(
            account_id=time_deposit_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "5000"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "4.79452"),
            ],
        )

        # deposit period ends
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=time_deposit_account_id,
            schedule_name=time_deposit.deposit_period.DEPOSIT_PERIOD_END_EVENT,
            effective_date=deposit_period_end_datetime,
        )

        # try deposit after the deposit period
        # Custom deposits into the account
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="5000",
            account_id=time_deposit_account_id,
            denomination="GBP",
            value_datetime=deposit_period_end_datetime + relativedelta(hours=1),
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # interest gets applied
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=time_deposit_account_id,
            schedule_name=time_deposit.interest_application.APPLICATION_EVENT,
            effective_date=interest_application_datetime,
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=time_deposit_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "5004.79"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                (dimensions.APPLIED_INTEREST_TRACKER, "4.79"),
            ],
        )

        # Customer partially withdraws some funds
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="100",
            account_id=time_deposit_account_id,
            denomination="GBP",
            value_datetime=interest_application_datetime + relativedelta(hours=1),
            client_batch_id="partial_early_withdrawal",
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=time_deposit_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "4904.79"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                (dimensions.APPLIED_INTEREST_TRACKER, "4.79"),
                (dimensions.EARLY_WITHDRAWALS_TRACKER, "100"),
            ],
        )
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type=time_deposit.WITHDRAWAL_FEES_NOTIFICATION,
            notification_details={
                "account_id": str(time_deposit_account_id),
                "denomination": "GBP",
                "withdrawal_amount": "100",
                "flat_fee_amount": "10",
                "percentage_fee_amount": "1.00",
                "number_of_interest_days_fee": "0",
                "total_fee_amount": "11.00",
                "client_batch_id": "partial_early_withdrawal",
            },
            resource_id=str(time_deposit_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        # account matures
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=time_deposit_account_id,
            schedule_name=time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
            effective_date=pre_account_maturity_notification_datetime,
        )
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type=time_deposit.NOTIFY_UPCOMING_MATURITY_NOTIFICATION,
            notification_details={
                "account_id": str(time_deposit_account_id),
                "account_maturity_datetime": str(account_maturity_datetime),
            },
            resource_id=str(time_deposit_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=time_deposit_account_id,
            schedule_name=time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT,
            effective_date=account_maturity_datetime,
        )
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type=time_deposit.ACCOUNT_MATURITY_NOTIFICATION,
            notification_details={
                "account_id": str(time_deposit_account_id),
                "account_maturity_datetime": str(account_maturity_datetime),
                "reason": "Account has now reached maturity",
            },
            resource_id=str(time_deposit_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        # Example of how to determine the customer rollover preference
        # Get rollover type from account notes
        rollover_details = endtoend.contracts_helper.get_account(
            account_id=time_deposit_account_id
        )["details"]
        rollover_amount = Decimal("0")
        if rollover_details["maturity_type"] == "rollover":
            rollover_type = rollover_details["rollover_type"]
            if rollover_type == "principal_only":
                applied_interest = endtoend.contracts_helper.get_specific_balance(
                    account_id=time_deposit_account_id,
                    address=time_deposit.APPLIED_INTEREST_TRACKER,
                )
                default_balance = endtoend.contracts_helper.get_specific_balance(
                    account_id=time_deposit_account_id,
                    address=time_deposit.DEFAULT_ADDRESS,
                )
                rollover_amount = Decimal(default_balance) - Decimal(applied_interest)

        # rollover amount = 4900
        # Since the customer has chosen to rollover into another time deposit a
        # 'renewed_time_deposit' account is created
        renewed_time_deposit_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="renewed_time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            details={},
            opening_timestamp=renewed_time_deposit_opening_datetime.isoformat(),
            wait_for_activation=True,
        )
        renewed_time_deposit_account_id = renewed_time_deposit_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", renewed_time_deposit_account["status"])

        # transfer rollover amount to the new account
        posting_id = endtoend.postings_helper.create_transfer(
            amount=str(rollover_amount),
            debtor_target_account_id=time_deposit_account_id,
            creditor_target_account_id=renewed_time_deposit_account_id,
            value_datetime=renewed_time_deposit_opening_datetime,
            denomination="GBP",
            instruction_details={"force_override": "True"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_all_account_balances(
            accounts_expected_balances={
                time_deposit_account_id: [
                    (dimensions.DEFAULT, "4.79"),
                    (dimensions.APPLIED_INTEREST_TRACKER, "4.79"),
                    (dimensions.EARLY_WITHDRAWALS_TRACKER, "100"),
                ],
                renewed_time_deposit_account_id: [(dimensions.DEFAULT, "4900")],
            }
        )

        # transfer applied interest back to the customer
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="4.79",
            account_id=time_deposit_account_id,
            denomination="GBP",
            value_datetime=renewed_time_deposit_opening_datetime + relativedelta(seconds=1),
            client_batch_id="return_interest_to_customer",
            instruction_details={"force_override": "True"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=time_deposit_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.APPLIED_INTEREST_TRACKER, "4.79"),
                (dimensions.EARLY_WITHDRAWALS_TRACKER, "100"),
            ],
        )

        # # matured time deposit can now be closed
        endtoend.core_api_helper.update_account(
            account_id=time_deposit_account_id,
            status=endtoend.core_api_helper.AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE,
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=time_deposit_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.APPLIED_INTEREST_TRACKER, "0"),
                (dimensions.EARLY_WITHDRAWALS_TRACKER, "0"),
            ],
        )
        endtoend.core_api_helper.update_account(
            account_id=time_deposit_account_id,
            status=endtoend.core_api_helper.AccountStatus.ACCOUNT_STATUS_CLOSED,
        )

        matured_time_deposit_account = endtoend.contracts_helper.get_account(
            account_id=time_deposit_account_id
        )
        self.assertEqual("ACCOUNT_STATUS_CLOSED", matured_time_deposit_account["status"])

    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {"new_time_deposit": [time_deposit.deposit_period.DEPOSIT_PERIOD_END_EVENT]}
    )
    def test_completed_deposit_period_end_schedule_passed_through_conversion(self):
        endtoend.standard_setup()

        opening_datetime = parameters.default_e2e_start_date
        deposit_period_end_datetime = opening_datetime.replace(
            hour=23, minute=59, second=59
        ) + relativedelta(days=5)

        customer_id = endtoend.core_api_helper.create_customer()
        time_deposit_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="new_time_deposit",
            instance_param_vals=parameters.default_instance.copy(),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_datetime.isoformat(),
        )
        time_deposit_account_id = time_deposit_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", time_deposit_account["status"])

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=time_deposit_account_id,
            schedule_name=time_deposit.deposit_period.DEPOSIT_PERIOD_END_EVENT,
        )
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type=time_deposit.DEPOSIT_PERIOD_NOTIFICATION,
            notification_details={
                "account_id": time_deposit_account_id,
                "deposit_balance": "0",
                "deposit_period_end_datetime": str(deposit_period_end_datetime),
                "reason": "Close account due to lack of deposits at the end of deposit period",
            },
            resource_id=str(time_deposit_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )
        schedules = endtoend.schedule_helper.get_account_schedules(
            account_id=time_deposit_account_id, statuses_to_exclude=[]
        )

        self.assertEqual(
            schedules[time_deposit.deposit_period.DEPOSIT_PERIOD_END_EVENT]["status"],
            "SCHEDULE_STATUS_COMPLETED",
        )

        endtoend.contracts_helper.convert_account(
            account_id=time_deposit_account_id,
            product_version_id=endtoend.testhandle.contract_pid_to_uploaded_product_version_id[
                "converted_time_deposit"
            ],
        )
        endtoend.accounts_helper.wait_for_account_update(
            account_id=time_deposit_account_id,
            account_update_type="product_version_update",
            target_status="ACCOUNT_UPDATE_STATUS_COMPLETED",
        )
        schedules = endtoend.schedule_helper.get_account_schedules(
            account_id=time_deposit_account_id, statuses_to_exclude=[]
        )

        self.assertEqual(
            schedules[time_deposit.deposit_period.DEPOSIT_PERIOD_END_EVENT]["status"],
            "SCHEDULE_STATUS_DISABLED",
        )

    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {
            "new_time_deposit": [
                time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
                time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT,
            ]
        }
    )
    def test_account_maturity_is_updated_to_next_non_holiday_date_when_falls_on_holiday(self):
        """
        Checks if the maturity date falls on a holiday (based on calendars),
        then the account maturity schedule is updated to fall on the next non holiday date.
        The notification sent prior to account maturity uses the original maturity datetime ;
        desired_maturity(holiday) = 05/06/23 + 1 day as per design doc = 06/06/23
        notification_before_maturity = 05/06/23
        new_maturity_date due to holidays = 07/06/23
        """
        endtoend.standard_setup()

        opening_datetime = parameters.default_e2e_start_date
        desired_maturity_datetime = datetime(
            year=2023, month=6, day=5, hour=1, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )

        # create holiday event
        holiday_start = datetime(
            year=2023, month=6, day=5, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )
        holiday_end = datetime(
            year=2023, month=6, day=6, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )

        endtoend.core_api_helper.create_calendar_event(
            event_id="E2E_TEST_EVENT_" + uuid.uuid4().hex,
            calendar_id=endtoend.testhandle.calendar_ids_to_e2e_ids["PUBLIC_HOLIDAYS"],
            name="E2E TEST EVENT",
            is_active=True,
            start_timestamp=holiday_start,
            end_timestamp=holiday_end,
        )

        instance_params = parameters.default_instance.copy()
        instance_params["desired_maturity_date"] = str(desired_maturity_datetime.date())

        customer_id = endtoend.core_api_helper.create_customer()
        time_deposit_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="new_time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_datetime.isoformat(),
        )
        time_deposit_account_id = time_deposit_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", time_deposit_account["status"])

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=time_deposit_account_id,
            schedule_name=time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
            effective_date=datetime(2023, 6, 5, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )

        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type=time_deposit.NOTIFY_UPCOMING_MATURITY_NOTIFICATION,
            notification_details={
                "account_id": time_deposit_account_id,
                "account_maturity_datetime": "2023-06-07 00:00:00+00:00",
            },
            resource_id=str(time_deposit_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=time_deposit_account_id,
            schedule_name=time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT,
            effective_date=datetime(2023, 6, 7, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )

        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type=time_deposit.ACCOUNT_MATURITY_NOTIFICATION,
            notification_details={
                "account_id": time_deposit_account_id,
                "account_maturity_datetime": "2023-06-07 00:00:00+00:00",
                "reason": "Account has now reached maturity",
            },
            resource_id=str(time_deposit_account_id),
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )
        schedules = endtoend.schedule_helper.get_account_schedules(
            account_id=time_deposit_account_id, statuses_to_exclude=[]
        )

        self.assertEqual(
            schedules[time_deposit.deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT]["status"],
            "SCHEDULE_STATUS_COMPLETED",
        )
        self.assertEqual(
            schedules[time_deposit.deposit_maturity.ACCOUNT_MATURITY_EVENT]["status"],
            "SCHEDULE_STATUS_COMPLETED",
        )
