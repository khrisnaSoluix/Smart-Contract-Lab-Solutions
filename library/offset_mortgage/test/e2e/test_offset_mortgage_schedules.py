# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo

# library
import library.current_account.test.dimensions as ca_dimensions
import library.mortgage.test.dimensions as mortgage_dimensions
import library.mortgage.test.e2e.accounts as mortgage_test_accounts
import library.mortgage.test.e2e.parameters as mortgage_test_parameters
import library.offset_mortgage.test.files as files
import library.savings_account.test.dimensions as sa_dimensions
from library.current_account.test.e2e import (
    accounts as ca_accounts,
    parameters as ca_test_parameters,
)
from library.mortgage.contracts.template import mortgage
from library.savings_account.test.e2e import (
    accounts as sa_accounts,
    parameters as sa_test_parameters,
)

# inception sdk
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = {
    "TSIDE_ASSET": [
        *mortgage_test_accounts.internal_accounts_tside["TSIDE_ASSET"],
        *ca_accounts.internal_accounts_tside["TSIDE_ASSET"],
        *sa_accounts.internal_accounts_tside["TSIDE_ASSET"],
    ],
    "TSIDE_LIABILITY": [
        *mortgage_test_accounts.internal_accounts_tside["TSIDE_LIABILITY"],
        *ca_accounts.internal_accounts_tside["TSIDE_LIABILITY"],
        *sa_accounts.internal_accounts_tside["TSIDE_LIABILITY"],
    ],
}

endtoend.testhandle.CONTRACTS = {
    "mortgage": {
        "path": files.MORTGAGE_CONTRACT,
        "template_params": mortgage_test_parameters.default_template.copy(),
    },
    "current_account": {
        "path": files.CURRENT_ACCOUNT_CONTRACT,
        "template_params": ca_test_parameters.default_template.copy(),
    },
    "savings_account": {
        "path": files.SAVINGS_ACCOUNT_CONTRACT,
        "template_params": sa_test_parameters.default_template.copy(),
    },
    "dummy_account": {
        "path": DUMMY_CONTRACT,
    },
}

endtoend.testhandle.SUPERVISORCONTRACTS = {
    "offset_mortgage": {"path": files.OFFSET_MORTGAGE_SUPERVISOR_CONTRACT}
}

default_start_datetime = datetime(
    year=2023, month=1, day=1, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
)


class OffsetMortgageSchedulesTest(endtoend.AcceleratedEnd2EndTest):
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {"offset_mortgage": ["ACCRUE_OFFSET_INTEREST"]}
    )
    def test_initial_accrual(self):
        endtoend.standard_setup()
        cust_id = endtoend.core_api_helper.create_customer()
        deposit_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=default_start_datetime.isoformat(),
        )["id"]

        mortgage_instance_params = {
            **mortgage_test_parameters.default_instance,
            mortgage.disbursement.PARAM_DEPOSIT_ACCOUNT: deposit_account_id,
        }

        mortgage_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=mortgage_instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=default_start_datetime.isoformat(),
        )["id"]

        current_account_1_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=ca_test_parameters.default_instance,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=default_start_datetime.isoformat(),
        )["id"]

        current_account_2_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=ca_test_parameters.default_instance,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=default_start_datetime.isoformat(),
        )["id"]

        savings_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="savings_account",
            instance_param_vals=sa_test_parameters.default_instance,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=default_start_datetime.isoformat(),
        )["id"]

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "offset_mortgage",
            [mortgage_account_id, current_account_1_id, current_account_2_id, savings_account_id],
        )

        endtoend.supervisors_helper.check_plan_associations(
            self,
            plan_id,
            [mortgage_account_id, current_account_1_id, current_account_2_id, savings_account_id],
        )

        # Deposit into CA/SA accounts
        ca_posting_1_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="10000",
            account_id=current_account_1_id,
            denomination="GBP",
            value_datetime=(default_start_datetime + relativedelta(seconds=10)).isoformat(),
        )
        pib = endtoend.postings_helper.get_posting_batch(ca_posting_1_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=current_account_1_id,
            expected_balances=[
                (ca_dimensions.DEFAULT, "10000"),
                (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
            ],
        )

        ca_posting_2_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="10000",
            account_id=current_account_2_id,
            denomination="GBP",
            value_datetime=(default_start_datetime + relativedelta(seconds=10)).isoformat(),
        )
        pib = endtoend.postings_helper.get_posting_batch(ca_posting_2_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=current_account_2_id,
            expected_balances=[
                (ca_dimensions.DEFAULT, "10000"),
                (ca_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
            ],
        )

        sa_posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="10000",
            account_id=savings_account_id,
            denomination="GBP",
            value_datetime=(default_start_datetime + relativedelta(seconds=10)).isoformat(),
        )
        pib = endtoend.postings_helper.get_posting_batch(sa_posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id,
            expected_balances=[
                (sa_dimensions.DEFAULT, "10000"),
                (sa_dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
            ],
        )

        # Trigger offset schedule
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            schedule_name="ACCRUE_OFFSET_INTEREST",
            plan_id=plan_id,
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=mortgage_account_id,
            expected_balances=[
                # (300000 - 30000) *  0.00274%
                (mortgage_dimensions.ACCRUED_INTEREST_RECEIVABLE, "7.39727"),
                (mortgage_dimensions.ACCRUED_EXPECTED_INTEREST, "7.39727"),
            ],
        )
