# standard libs
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

# library
from library.savings_account.test import dimensions, files, parameters
from library.savings_account.test.e2e import accounts as e2e_accounts, parameters as e2e_parameters

# inception sdk
from inception_sdk.test_framework import endtoend

SAVINGS_ACCOUNT = e2e_parameters.SAVINGS_ACCOUNT
endtoend.testhandle.CONTRACTS = {
    SAVINGS_ACCOUNT: {
        "path": files.SAVINGS_ACCOUNT_CONTRACT,
        "template_params": e2e_parameters.default_template.copy(),
    },
}
endtoend.testhandle.FLAG_DEFINITIONS = {
    parameters.DORMANCY_FLAG: ("library/common/flag_definitions/account_dormant.resource.yaml")
}
endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = e2e_accounts.internal_accounts_tside


class SavingsAccountTest(endtoend.AcceleratedEnd2EndTest):
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {
            SAVINGS_ACCOUNT: [
                "ACCRUE_INTEREST",
                "APPLY_INTEREST",
                "APPLY_MINIMUM_BALANCE_FEE",
            ]
        }
    )
    def test_scheduled_events(self):
        endtoend.standard_setup()
        # 2023/01/01
        opening_date = e2e_parameters.default_start_date

        customer_id = endtoend.core_api_helper.create_customer()
        savings_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=SAVINGS_ACCOUNT,
            instance_param_vals=e2e_parameters.default_instance.copy(),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        savings_account_id = savings_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", savings_account["status"])

        # Make transaction to test interest accrual
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="5000",
            account_id=savings_account_id,
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=opening_date,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "5000"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=savings_account_id,
            schedule_name="ACCRUE_INTEREST",
        )

        # (1,000 * (0.01/365)) + (2,000 * (0.02/365)) + (2,000 * (0.035/365)) = 0.32877
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id,
            expected_balances=[
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=savings_account_id,
            schedule_name="APPLY_INTEREST",
            effective_date=datetime(
                year=2023, month=1, day=2, hour=0, minute=1, second=0, tzinfo=timezone.utc
            ),
        )
        # Only applying one day's interest as only one accrual event has been run
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "5000.33"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
            ],
        )

        # Clear out account balance
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="5000.33",
            account_id=savings_account_id,
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=opening_date + relativedelta(days=1, hours=2),
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Check account balances
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
            ],
        )

    def test_scheduled_events_minimum_balance_fee(self):
        endtoend.standard_setup()
        # 2023/01/01
        opening_date = e2e_parameters.default_start_date

        customer_id = endtoend.core_api_helper.create_customer()
        savings_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=SAVINGS_ACCOUNT,
            instance_param_vals=e2e_parameters.default_instance.copy(),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        savings_account_id = savings_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", savings_account["status"])

        # Make transaction to fund the account
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="50",
            account_id=savings_account_id,
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=opening_date,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Current balance is lower than default tier (100) so minimum balance fee applies
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "50"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=savings_account_id,
            schedule_name="APPLY_MINIMUM_BALANCE_FEE",
        )

        # Minimum balance fee applied
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "30"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
            ],
        )

        # Clear out account balance
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="30",
            account_id=savings_account_id,
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=opening_date + relativedelta(days=1, hours=2),
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Check account balances
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
            ],
        )
