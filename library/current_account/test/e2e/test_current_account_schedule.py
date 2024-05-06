# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo

# library
from library.current_account.test import dimensions, files, parameters
from library.current_account.test.e2e import accounts as e2e_accounts, parameters as e2e_parameters

# inception sdk
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT

CURRENT_ACCOUNT = e2e_parameters.CURRENT_ACCOUNT
endtoend.testhandle.CONTRACTS = {
    CURRENT_ACCOUNT: {
        "path": files.CURRENT_ACCOUNT_CONTRACT,
        "template_params": e2e_parameters.default_template.copy(),
    },
    "dummy_account": {"path": DUMMY_CONTRACT},
}
endtoend.testhandle.FLAG_DEFINITIONS = {
    parameters.DORMANCY_FLAG: ("library/common/flag_definitions/account_dormant.resource.yaml")
}
endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = e2e_accounts.internal_accounts_tside


class CurrentAccountTest(endtoend.AcceleratedEnd2EndTest):
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {
            "current_account": [
                "ACCRUE_INTEREST",
                "APPLY_INTEREST",
                "APPLY_MONTHLY_FEE",
                "APPLY_UNARRANGED_OVERDRAFT_FEE",
            ]
        }
    )
    def test_scheduled_events(self):
        endtoend.standard_setup()
        # 2023/01/01
        opening_date = e2e_parameters.default_start_date

        customer_id = endtoend.core_api_helper.create_customer()
        current_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=CURRENT_ACCOUNT,
            instance_param_vals=e2e_parameters.default_instance,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        current_account_id = current_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", current_account["status"])

        # Make transaction to test interest accrual
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="5000",
            account_id=current_account_id,
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=opening_date,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=current_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "5000"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=current_account_id,
            schedule_name="ACCRUE_INTEREST",
        )

        # (1,000 * (0.01/365)) + (2,000 * (0.02/365)) + (2,000 * (0.035/365)) = 0.32877
        endtoend.balances_helper.wait_for_account_balances(
            account_id=current_account_id,
            expected_balances=[
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=current_account_id,
            schedule_name="APPLY_INTEREST",
            effective_date=datetime(
                year=2023, month=1, day=2, hour=0, minute=1, second=0, tzinfo=ZoneInfo("UTC")
            ),
        )
        # only applying one day's interest as only one accrual event has been run
        endtoend.balances_helper.wait_for_account_balances(
            account_id=current_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "5000.33"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
            ],
        )

        # Make transaction to lower account balances below minimum balance limit (LOWER_TIER = 100)
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="5125.33",
            account_id=current_account_id,
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=opening_date + relativedelta(days=1, hours=2),
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Check account balances
        endtoend.balances_helper.wait_for_account_balances(
            account_id=current_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "-125.00"),
            ],
        )

        # Accrued overdraft interest applying the buffer
        # -125 GBP + 50 GBP Buffer = -75 GBP * (0.05/365) = 0.01027
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=current_account_id,
            schedule_name="ACCRUE_INTEREST",
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=current_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "-125.00"),
                (dimensions.OVERDRAFT_ACCRUED_INTEREST, "-0.01027"),
                (dimensions.UNARRANGED_OVERDRAFT_FEE, "-5"),
            ],
        )
        # Accrued overdraft interest applying the buffer
        # -125 GBP + 50 GBP Buffer = -75 GBP * (0.05/365) = 0.01027
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=current_account_id,
            schedule_name="ACCRUE_INTEREST",
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=current_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "-125.00"),
                (dimensions.OVERDRAFT_ACCRUED_INTEREST, "-0.02054"),
                (dimensions.UNARRANGED_OVERDRAFT_FEE, "-10"),
            ],
        )
        # Accrued overdraft interest without the buffer
        # -125 GBP + 0 GBP Buffer = -125 GBP * (0.05/365) = 0.01712
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=current_account_id,
            schedule_name="ACCRUE_INTEREST",
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=current_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "-125.00"),
                (dimensions.OVERDRAFT_ACCRUED_INTEREST, "-0.03766"),
                (dimensions.UNARRANGED_OVERDRAFT_FEE, "-15"),
            ],
        )

        # Apply monthly fee to charge maintenance fee (5), unarranged overdraft fees (15)
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=current_account_id,
            schedule_name="APPLY_MONTHLY_FEE",
        )
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=current_account_id,
            schedule_name="APPLY_UNARRANGED_OVERDRAFT_FEE",
        )

        # Apply monthly fee to charge maintenance fee (5), unarranged overdraft fees (15)
        # and minimum balance fee (20)

        # Minimum mean balance fee
        # Average balance calculation
        # Day1: Balance is ignored since the fetcher will retrieve the balance at exactly T00:00:00
        # Day2: Balance (5000)
        # Day 3 to 31: (-125)
        # Average Balance = (5000*1 day) + (-125*29 days) = 1375 / 30 days= 45.83
        # The default minimum balance limit is 100 therefore the fee is applied
        endtoend.balances_helper.wait_for_account_balances(
            account_id=current_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "-145.00"),
                (dimensions.OVERDRAFT_ACCRUED_INTEREST, "-0.03766"),
                (dimensions.UNARRANGED_OVERDRAFT_FEE, "0"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=current_account_id,
            schedule_name="APPLY_INTEREST",
            effective_date=datetime(
                year=2023, month=2, day=2, hour=0, minute=1, second=0, tzinfo=ZoneInfo("UTC")
            ),
        )

        # Apply overdraft interest
        endtoend.balances_helper.wait_for_account_balances(
            account_id=current_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "-145.04"),
                (dimensions.OVERDRAFT_ACCRUED_INTEREST, "0"),
                (dimensions.UNARRANGED_OVERDRAFT_FEE, "0"),
            ],
        )

    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {
            "current_account": [
                "APPLY_MINIMUM_BALANCE_FEE",
            ]
        }
    )
    def test_scheduled_events_minimum_balance_fee(self):
        endtoend.standard_setup()
        # 2023/01/01
        opening_date = e2e_parameters.default_start_date

        customer_id = endtoend.core_api_helper.create_customer()
        current_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=CURRENT_ACCOUNT,
            instance_param_vals=e2e_parameters.default_instance.copy(),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        current_account_id = current_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", current_account["status"])

        # Make transaction to test interest accrual
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="50",
            account_id=current_account_id,
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=opening_date,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Current balance is lower than default tier (100) so minimum balance fee applies
        endtoend.balances_helper.wait_for_account_balances(
            account_id=current_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "50"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=current_account_id,
            schedule_name="APPLY_MINIMUM_BALANCE_FEE",
        )

        # Minimum balance fee applied
        endtoend.balances_helper.wait_for_account_balances(
            account_id=current_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "30"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
            ],
        )
