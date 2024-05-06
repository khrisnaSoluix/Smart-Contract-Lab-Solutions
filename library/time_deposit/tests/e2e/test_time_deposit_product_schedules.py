# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os
import uuid
from datetime import datetime, timezone

# third party
from dateutil.relativedelta import relativedelta

from library.time_deposit.tests.e2e.time_deposit_test_params import (
    td_template_params,
    internal_accounts_tside,
)

# common
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "time_deposit": {
        "path": "library/time_deposit/contracts/time_deposit.py",
        "template_params": td_template_params,
    },
    "dummy_account": {
        "path": DUMMY_CONTRACT,
    },
}

endtoend.testhandle.CONTRACT_MODULES = {
    "interest": {"path": "library/common/contract_modules/interest.py"},
    "utils": {"path": "library/common/contract_modules/utils.py"},
}

endtoend.testhandle.WORKFLOWS = {
    # time deposit workflows
    "TIME_DEPOSIT_APPLICATON": ("library/time_deposit/workflows/time_deposit_application.yaml"),
    "TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER": (
        "library/time_deposit/workflows/time_deposit_applied_interest_transfer.yaml"
    ),
    "TIME_DEPOSIT_CLOSURE": ("library/time_deposit/workflows/time_deposit_closure.yaml"),
    "TIME_DEPOSIT_INTEREST_PREFERENCE_CHANGE": (
        "library/time_deposit/workflows/time_deposit_interest_preference_change.yaml"
    ),
    "TIME_DEPOSIT_MATURITY": ("library/time_deposit/workflows/time_deposit_maturity.yaml"),
    "TIME_DEPOSIT_ROLLOVER": ("library/time_deposit/workflows/time_deposit_rollover.yaml"),
    "TIME_DEPOSIT_WITHDRAWAL": ("library/time_deposit/workflows/time_deposit_withdrawal.yaml"),
}

endtoend.testhandle.FLAG_DEFINITIONS = {}

endtoend.testhandle.CALENDARS = {
    "PUBLIC_HOLIDAYS": ("library/common/calendars/public_holidays.resource.yaml")
}

SCHEDULE_TAGS_DIR = "library/time_deposit/account_schedule_tags/schedules_tests/"
PAUSED_SCHEDULE_TAG = SCHEDULE_TAGS_DIR + "paused_tag.resource.yaml"

# By default all schedules are paused
DEFAULT_TAGS = {
    "TIME_DEPOSIT_ACCRUE_INTEREST_AST": PAUSED_SCHEDULE_TAG,
    "TIME_DEPOSIT_APPLY_ACCRUED_INTEREST_AST": PAUSED_SCHEDULE_TAG,
    "TIME_DEPOSIT_ACCOUNT_MATURITY_AST": PAUSED_SCHEDULE_TAG,
    "TIME_DEPOSIT_ACCOUNT_CLOSE_AST": PAUSED_SCHEDULE_TAG,
}


class TimeDepositProductTest(endtoend.AcceleratedEnd2EndTest):

    default_tags = DEFAULT_TAGS

    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags(
        {
            "TIME_DEPOSIT_ACCRUE_INTEREST_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_accruals_tag.resource.yaml",
            }
        }
    )
    def test_interest_accrual_with_cool_off_period(self):
        """
        Test no interest accrued during cool off period and retrospectively accrued after cool off
        period
        """
        endtoend.standard_setup()
        customer_id = endtoend.core_api_helper.create_customer()
        opening_date = datetime(2020, 5, 1, tzinfo=timezone.utc)

        time_deposit_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="time_deposit",
            instance_param_vals=dict(
                interest_application_frequency="quarterly",
                interest_application_day="25",
                gross_interest_rate="0.145",
                term_unit="months",
                term="12",
                deposit_period="1",
                grace_period="0",
                cool_off_period="1",
                fee_free_percentage_limit="0",
                withdrawal_fee="0",
                withdrawal_percentage_fee="0",
                period_end_hour="0",
                account_closure_period="2",
                auto_rollover_type="no_rollover",
                partial_principal_amount="0",
                rollover_interest_application_frequency="quarterly",
                rollover_interest_application_day="25",
                rollover_gross_interest_rate="0.145",
                rollover_term_unit="months",
                rollover_term="12",
                rollover_grace_period="0",
                rollover_period_end_hour="0",
                rollover_account_closure_period="2",
            ),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        td_account_id = time_deposit_account["id"]

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id,
            amount="200",
            denomination="GBP",
            value_datetime=opening_date,
        )

        # The first execution will not result in accruals as it is during cool-off
        endtoend.schedule_helper.trigger_next_schedule_execution(
            paused_tag_id="TIME_DEPOSIT_ACCRUE_INTEREST_AST",
            schedule_frequency=self.paused_tags["TIME_DEPOSIT_ACCRUE_INTEREST_AST"][
                "schedule_frequency"
            ],
        )

        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="ACCRUE_INTEREST", account_id=td_account_id
        )

        endtoend.balances_helper.wait_for_account_balances(
            account_id=td_account_id,
            expected_balances=[
                (BalanceDimensions("DEFAULT"), "200"),
                (BalanceDimensions("ACCRUED_INTEREST_PAYABLE"), "0"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_execution(
            paused_tag_id="TIME_DEPOSIT_ACCRUE_INTEREST_AST",
            schedule_frequency=self.paused_tags["TIME_DEPOSIT_ACCRUE_INTEREST_AST"][
                "schedule_frequency"
            ],
        )

        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="ACCRUE_INTEREST",
            account_id=td_account_id,
            effective_date=datetime(2020, 5, 2, 23, 58, 59, tzinfo=timezone.utc),
        )

        # the second execution results in two accruals due to cool-off ending
        # daily interest (0.079452) * days since account creation (2) = 0.1589
        endtoend.balances_helper.wait_for_account_balances(
            account_id=td_account_id,
            expected_balances=[
                (BalanceDimensions("DEFAULT"), "200"),
                (BalanceDimensions("ACCRUED_INTEREST_PAYABLE"), "0.1589"),
            ],
        )

    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags(
        {
            "TIME_DEPOSIT_ACCRUE_INTEREST_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_accruals_tag.resource.yaml",
            }
        }
    )
    def test_interest_accrual_no_cool_off_period(self):
        """
        Test during that interest is accrued with no cool off.
        Test also checks that schedules are set up correctly to the expected time.
        """
        endtoend.standard_setup()
        customer_id = endtoend.core_api_helper.create_customer()
        opening_date = datetime(2020, 5, 1, tzinfo=timezone.utc)

        time_deposit_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="time_deposit",
            instance_param_vals=dict(
                interest_application_frequency="quarterly",
                interest_application_day="25",
                gross_interest_rate="0.145",
                term_unit="months",
                term="12",
                deposit_period="1",
                grace_period="0",
                cool_off_period="0",
                fee_free_percentage_limit="0",
                withdrawal_fee="0",
                withdrawal_percentage_fee="0",
                period_end_hour="0",
                account_closure_period="2",
                auto_rollover_type="no_rollover",
                partial_principal_amount="0",
                rollover_interest_application_frequency="quarterly",
                rollover_interest_application_day="25",
                rollover_gross_interest_rate="0.145",
                rollover_term_unit="months",
                rollover_term="12",
                rollover_grace_period="0",
                rollover_period_end_hour="0",
                rollover_account_closure_period="2",
            ),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        td_account_id = time_deposit_account["id"]

        account_schedules = endtoend.schedule_helper.get_account_schedules(td_account_id)
        # Expected accrue interest - 2020-05-01T23:58:59
        accrue_interest_expected_next_run_time_start = opening_date + relativedelta(
            hours=23, minutes=58, seconds=59
        )
        self.assertEqual(
            accrue_interest_expected_next_run_time_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["ACCRUE_INTEREST"]["next_run_timestamp"],
        )

        # Expected apply interest happens quarterly on 25th of month: 2020-08-25T23:59:59Z
        apply_accrued_expected_next_run_time_start = opening_date + relativedelta(
            months=3, days=24, hours=23, minutes=59, seconds=59
        )

        self.assertEqual(
            apply_accrued_expected_next_run_time_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["APPLY_ACCRUED_INTEREST"]["next_run_timestamp"],
        )

        # Expected account maturity - 12 months after start date: 2021-05-01T00:00:00Z
        account_maturity_expected_next_run_time_start = opening_date + relativedelta(months=12)
        self.assertEqual(
            account_maturity_expected_next_run_time_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["ACCOUNT_MATURITY"]["next_run_timestamp"],
        )

        # Expected account close schedule: start_date + account_closure_period + deposit_period
        account_close_date = opening_date + relativedelta(days=3)

        self.assertEqual(
            account_close_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["ACCOUNT_CLOSE"]["next_run_timestamp"],
        )

        endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id,
            amount="200",
            denomination="GBP",
            value_datetime=opening_date,
        )

        endtoend.schedule_helper.trigger_next_schedule_execution(
            paused_tag_id="TIME_DEPOSIT_ACCRUE_INTEREST_AST",
            schedule_frequency=self.paused_tags["TIME_DEPOSIT_ACCRUE_INTEREST_AST"][
                "schedule_frequency"
            ],
        )

        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="ACCRUE_INTEREST", account_id=td_account_id
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=td_account_id,
            expected_balances=[
                (BalanceDimensions("DEFAULT"), "200"),
                (BalanceDimensions("ACCRUED_INTEREST_PAYABLE"), "0.07945"),
            ],
        )

    # No tags set as we don't actually unpause any schedules
    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags({})
    def test_maturity_date(self):
        """
        Ensure that maturity date is updated if the original maturity date falls on a holiday
        """
        endtoend.standard_setup()
        customer_id = endtoend.core_api_helper.create_customer()
        opening_date = datetime(2020, 5, 1, 1, tzinfo=timezone.utc)
        # A calendar event will be set up to cover the maturity date
        calendar_event_from = datetime(2020, 5, 31, tzinfo=timezone.utc)
        calendar_event_to = datetime(2020, 6, 2, tzinfo=timezone.utc)
        # original maturity date would be 1 month after opening date, + 1 day due to calendar event
        expected_maturity_date = datetime(2020, 6, 2, 1, tzinfo=timezone.utc)

        endtoend.core_api_helper.create_calendar_event(
            event_id="E2E_TEST_EVENT_" + uuid.uuid4().hex,
            calendar_id=endtoend.testhandle.calendar_ids_to_e2e_ids["PUBLIC_HOLIDAYS"],
            name="E2E TEST EVENT",
            is_active=True,
            start_timestamp=calendar_event_from,
            end_timestamp=calendar_event_to,
        )

        time_deposit_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="time_deposit",
            instance_param_vals=dict(
                interest_application_frequency="quarterly",
                interest_application_day="25",
                gross_interest_rate="0.145",
                term_unit="months",
                term="1",
                deposit_period="1",
                grace_period="2",
                cool_off_period="1",
                fee_free_percentage_limit="0",
                withdrawal_fee="0",
                withdrawal_percentage_fee="0",
                period_end_hour="0",
                account_closure_period="0",
                auto_rollover_type="no_rollover",
                partial_principal_amount="0",
                rollover_interest_application_frequency="quarterly",
                rollover_interest_application_day="25",
                rollover_gross_interest_rate="0.145",
                rollover_term_unit="months",
                rollover_term="1",
                rollover_grace_period="2",
                rollover_period_end_hour="0",
                rollover_account_closure_period="2",
            ),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        td_account_id = time_deposit_account["id"]

        # We must pass in the right instance param effective timestamp as contracts engine only
        # retrieves a certain amount of calendar events
        derived_parameters = endtoend.core_api_helper.get_account_derived_parameters(
            td_account_id, opening_date.isoformat()
        )
        maturity_date = derived_parameters["maturity_date"]
        expected_maturity_date_str = expected_maturity_date.strftime("%Y-%m-%d %X")
        self.assertEqual(maturity_date, expected_maturity_date_str)

    @endtoend.AcceleratedEnd2EndTest.Decorators.set_paused_tags(
        {
            "TIME_DEPOSIT_ACCRUE_INTEREST_AST": {
                "schedule_frequency": "DAILY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_accruals_tag.resource.yaml",
            },
            "TIME_DEPOSIT_APPLY_ACCRUED_INTEREST_AST": {
                "schedule_frequency": "WEEKLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_apply_interest.resource.yaml",
            },
            "TIME_DEPOSIT_ACCOUNT_MATURITY_AST": {
                "schedule_frequency": "WEEKLY",
                "tag_resource": SCHEDULE_TAGS_DIR + "paused_account_maturity.resource.yaml",
            },
        }
    )
    def test_rollover_time_deposit_with_principal_and_interest_amount(self):
        """
        Open account through workflow with principal and interest amount
        """
        endtoend.standard_setup()
        customer_id = endtoend.core_api_helper.create_customer()
        # create dummy account for disbursement
        savings_account_id = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        opening_date = datetime(2020, 5, 1, tzinfo=timezone.utc)
        time_deposit_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="time_deposit",
            instance_param_vals=dict(
                interest_application_frequency="weekly",
                interest_application_day="25",
                gross_interest_rate="0.145",
                term_unit="days",
                term="8",
                deposit_period="1",
                grace_period="0",
                cool_off_period="0",
                fee_free_percentage_limit="0",
                withdrawal_fee="0",
                withdrawal_percentage_fee="0",
                period_end_hour="0",
                account_closure_period="2",
                auto_rollover_type="principal_and_interest",
                partial_principal_amount="0",
                rollover_interest_application_frequency="quarterly",
                rollover_interest_application_day="25",
                rollover_gross_interest_rate="0.145",
                rollover_term_unit="months",
                rollover_term="12",
                rollover_grace_period="1",
                rollover_period_end_hour="0",
                rollover_account_closure_period="2",
            ),
            details=dict(
                interest_payment_destination="retain_on_account",
                maturity_vault_account_id=savings_account_id,
                maturity_disbursement_destination="vault",
            ),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        td_account_id = time_deposit_account["id"]
        endtoend.postings_helper.inbound_hard_settlement(
            account_id=td_account_id,
            amount="200",
            denomination="GBP",
            value_datetime=opening_date,
        )

        endtoend.balances_helper.wait_for_account_balances(
            td_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "200",
                )
            ],
        )
        # accrue interest
        endtoend.schedule_helper.trigger_next_schedule_execution(
            paused_tag_id="TIME_DEPOSIT_ACCRUE_INTEREST_AST",
            schedule_frequency=self.paused_tags["TIME_DEPOSIT_ACCRUE_INTEREST_AST"][
                "schedule_frequency"
            ],
        )
        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="ACCRUE_INTEREST",
            account_id=td_account_id,
        )

        # apply interest so that we have the capitalised_interest address created
        endtoend.schedule_helper.trigger_next_schedule_execution(
            paused_tag_id="TIME_DEPOSIT_APPLY_ACCRUED_INTEREST_AST",
            schedule_frequency=self.paused_tags["TIME_DEPOSIT_APPLY_ACCRUED_INTEREST_AST"][
                "schedule_frequency"
            ],
        )
        endtoend.schedule_helper.wait_for_scheduled_jobs_to_finish(
            schedule_name="APPLY_ACCRUED_INTEREST",
            account_id=td_account_id,
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=td_account_id,
            expected_balances=[
                (BalanceDimensions("DEFAULT"), "200.08"),
                (BalanceDimensions("CAPITALISED_INTEREST"), "0.08"),
            ],
        )
        # run maturity schedule
        endtoend.schedule_helper.set_test_pause_at_timestamp_for_tag(
            schedule_tag_id="TIME_DEPOSIT_ACCOUNT_MATURITY_AST",
            test_pause_at_timestamp=opening_date + relativedelta(days=9),
        )

        # The maturity schedule should trigger a maturity workflow, which then rolls the TD over
        maturity_wf = endtoend.workflows_helper.wait_for_smart_contract_initiated_workflows(
            account_id=td_account_id,
            workflow_definition_id=endtoend.testhandle.workflow_definition_id_mapping[
                "TIME_DEPOSIT_MATURITY"
            ],
        )[0]

        cwf_id = endtoend.workflows_helper.get_child_workflow_id(
            maturity_wf["wf_instance_id"], "rollover_time_deposit", wait_for_parent_state=False
        )
        endtoend.workflows_helper.wait_for_state(cwf_id, "account_opened_successfully")
        context = endtoend.workflows_helper.get_state_local_context(
            cwf_id, "account_opened_successfully"
        )
        rollover_td_account = endtoend.contracts_helper.get_account(context["id"])
        self.assertEqual("ACCOUNT_STATUS_OPEN", rollover_td_account["status"])
        # Maturity TD account is open

        endtoend.workflows_helper.wait_for_state(
            maturity_wf["wf_instance_id"], "account_closed_successfully"
        )

        wf_context = endtoend.workflows_helper.get_global_context(maturity_wf["wf_instance_id"])

        # Original TD account is closed

        self.assertGreaterEqual(wf_context["balance_check_counter"], "1")
        rollover_td_account_id = rollover_td_account["id"]
        endtoend.balances_helper.wait_for_account_balances_by_ids(
            {
                td_account_id: [
                    (BalanceDimensions("DEFAULT"), "0"),
                    (BalanceDimensions("CAPITALISED_INTEREST"), "0"),
                ],
                rollover_td_account_id: [
                    (BalanceDimensions("DEFAULT"), "200.08"),
                ],
            }
        )
