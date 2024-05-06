# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions

from library.us_products.tests.e2e.us_products_test_params import (
    checking_account_template_params,
    internal_accounts_tside,
    SCHEDULE_TAGS_DIR,
    DEFAULT_TAGS,
)

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "us_checking_account": {
        "path": "library/us_products/contracts/us_checking_account.py",
        "template_params": checking_account_template_params,
    },
}

endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"},
    "interest": {"path": "library/common/contract_modules/interest.py"},
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "ACCOUNT_DORMANT": "library/common/flag_definitions/account_dormant.resource.yaml",
    "STANDARD_OVERDRAFT_TRANSACTION_COVERAGE": (
        "library/us_products/flag_definitions/overdraft_transaction_coverage.resource.yaml"
    ),
    "PROMOTIONAL_MAINTENANCE_FEE": (
        "library/us_products/flag_definitions/promotional_maintenance_fee.resource.yaml"
    ),
}


class UsCheckingProductSchedulesTest(endtoend.AcceleratedEnd2EndTest):

    default_tags = DEFAULT_TAGS

    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags(
        {
            "US_CHECKING_ACCRUE_INTEREST_AND_DAILY_FEES_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR
                + "paused_checking_accrue_interest_and_daily_fees_tag.resource.yaml",
            }
        }
    )
    def test_initial_accrual(self):
        endtoend.standard_setup()
        opening_date = datetime(year=2020, month=1, day=1, hour=1, tzinfo=timezone.utc)

        customer_id = endtoend.core_api_helper.create_customer()
        instance_params = {
            "standard_overdraft_limit": "1000",
            "interest_application_day": "1",
            "daily_atm_withdrawal_limit": "-1",
            "fee_free_overdraft_limit": "0",
        }

        account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="us_checking_account",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        checking_account_id = account["id"]

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=checking_account_id,
            amount="1000",
            denomination="USD",
            value_datetime=opening_date,
            client_batch_id="BATCH_1",
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.schedule_helper.trigger_next_schedule_execution(
            paused_tag_id="US_CHECKING_ACCRUE_INTEREST_AND_DAILY_FEES_AST",
            schedule_frequency=self.paused_tags["US_CHECKING_ACCRUE_INTEREST_AND_DAILY_FEES_AST"][
                "schedule_frequency"
            ],
        )

        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="ACCRUE_INTEREST_AND_DAILY_FEES", account_id=checking_account_id
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=checking_account_id,
            expected_balances=[
                (
                    BalanceDimensions("ACCRUED_DEPOSIT_PAYABLE", "COMMERCIAL_BANK_MONEY", "USD"),
                    "0.13699",
                ),
            ],
        )


if __name__ == "__main__":
    endtoend.runtests()
