# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo

# library
from library.us_products.contracts.template import us_checking_account
from library.us_products.test import dimensions, files
from library.us_products.test.e2e import accounts, parameters

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.common.utils import ac_coverage

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = accounts.internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    us_checking_account.PRODUCT_NAME: {
        "path": files.CHECKING_ACCOUNT_CONTRACT,
        "template_params": parameters.default_template,
    }
}


class USCheckingAccountSchedulesTest(endtoend.AcceleratedEnd2EndTest):
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {
            us_checking_account.PRODUCT_NAME: [
                us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT,
                us_checking_account.interest_application.APPLICATION_EVENT,
            ]
        }
    )
    def test_initial_interest_accrual_and_application(self):
        endtoend.standard_setup()
        opening_datetime = datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC"))

        customer_id = endtoend.core_api_helper.create_customer()

        instance_params = {
            **parameters.default_instance,
            us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "2",
        }

        product_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=us_checking_account.PRODUCT_NAME,
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_datetime.isoformat(),
        )
        us_checking_account_id = product_account["id"]

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=us_checking_account_id,
            amount="1000",
            denomination="USD",
            value_datetime=opening_datetime + relativedelta(hours=9),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=us_checking_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "1000"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=us_checking_account_id,
            schedule_name=us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT,
            effective_date=datetime(2023, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=us_checking_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "1000.00"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0.02740"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=us_checking_account_id,
            schedule_name=us_checking_account.interest_application.APPLICATION_EVENT,
            effective_date=datetime(2023, 1, 2, 0, 1, 0, tzinfo=ZoneInfo("UTC")),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=us_checking_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "1000.03"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0.00000"),
            ],
        )

        # Trigger another interest accrual that balance will be forfeited on closure
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=us_checking_account_id,
            schedule_name=us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT,
            effective_date=datetime(2023, 1, 3, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=us_checking_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "1000.03"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0.02740"),
            ],
        )

        # Clear the default balance and let deactivation hook clear accrued interest
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=us_checking_account_id,
            amount="1000.03",
            denomination="USD",
            value_datetime=datetime(2023, 1, 3, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
            + relativedelta(hours=9),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=us_checking_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "0"),
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0.02740"),
            ],
        )

        # Update account status to pending closure so deactivation hook is run
        endtoend.core_api_helper.update_account(
            account_id=us_checking_account_id,
            status=endtoend.core_api_helper.AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE,
        )

        endtoend.accounts_helper.wait_for_account_update(
            account_id=us_checking_account_id,
            account_update_type="closure_update",
            target_status="ACCOUNT_UPDATE_STATUS_COMPLETED",
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=us_checking_account_id,
            expected_balances=[
                (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
            ],
        )

    @ac_coverage(["CPP-1921-AC06", "CPP-1922-AC08"])
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {
            us_checking_account.PRODUCT_NAME: [
                us_checking_account.minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT,
                us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                us_checking_account.paper_statement_fee.APPLICATION_EVENT,
            ]
        }
    )
    def test_monthly_schedules(self):
        endtoend.standard_setup()
        opening_datetime = datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC"))

        customer_id = endtoend.core_api_helper.create_customer()

        instance_params = {
            **parameters.default_instance,
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_DAY: "1",
            us_checking_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_DAY: "2",
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_DAY: "3",
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_ENABLED: "True",
        }

        product_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=us_checking_account.PRODUCT_NAME,
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_datetime.isoformat(),
        )
        us_checking_account_id = product_account["id"]

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=us_checking_account_id,
            amount="70",
            denomination="USD",
            value_datetime=opening_datetime + relativedelta(hours=9),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=us_checking_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "70"),
            ],
        )

        # Charge $20 for monthly minimum balance fee
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=us_checking_account_id,
            schedule_name=(
                us_checking_account.minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT
            ),
            effective_date=datetime(2023, 2, 1, 0, 1, 0, tzinfo=ZoneInfo("UTC")),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=us_checking_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "50"),
            ],
        )

        # Charge $5 for monthly monthly maintenance fee
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=us_checking_account_id,
            schedule_name=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
            effective_date=datetime(2023, 2, 2, 0, 1, 0, tzinfo=ZoneInfo("UTC")),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=us_checking_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "45"),
            ],
        )

        # Charge $20 for monthly paper statement fee
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=us_checking_account_id,
            schedule_name=(us_checking_account.paper_statement_fee.APPLICATION_EVENT),
            effective_date=datetime(2023, 2, 3, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=us_checking_account_id,
            expected_balances=[
                (dimensions.DEFAULT, "25"),
            ],
        )
