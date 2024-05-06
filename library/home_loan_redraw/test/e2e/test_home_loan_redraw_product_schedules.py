# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone

# library
from library.home_loan_redraw.test import dimensions, files, parameters
from library.home_loan_redraw.test.e2e import accounts, parameters as e2e_parameters

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
from inception_sdk.test_framework.endtoend.contracts_helper import ContractNotificationResourceType
from inception_sdk.test_framework.endtoend.core_api_helper import AccountStatus

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = accounts.internal_accounts_tside

HOME_LOAN_REDRAW = e2e_parameters.HOME_LOAN_REDRAW

endtoend.testhandle.CONTRACTS = {
    HOME_LOAN_REDRAW: {
        "path": files.HOME_LOAN_REDRAW_CONTRACT,
        "template_params": e2e_parameters.default_template,
    },
    "dummy_account": {"path": DUMMY_CONTRACT},
}


class HomeLoanRedrawTest(endtoend.AcceleratedEnd2EndTest):
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {HOME_LOAN_REDRAW: ["DUE_AMOUNT_CALCULATION", "ACCRUE_INTEREST"]}
    )
    def test_home_loan_redraw_lifecycle(self):
        endtoend.standard_setup()
        opening_date = datetime(year=2020, month=1, day=5, hour=0, minute=1, tzinfo=timezone.utc)
        customer_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )["id"]

        instance_params = e2e_parameters.default_instance.copy()
        instance_params["deposit_account"] = dummy_account_id
        instance_params["due_amount_calculation_day"] = "5"
        instance_params["total_repayment_count"] = "120"

        home_loan_redraw_account_id = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=HOME_LOAN_REDRAW,
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )["id"]
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[(dimensions.PRINCIPAL, "800000"), (dimensions.EMI, "7361.08")],
        )
        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=home_loan_redraw_account_id,
            schedule_name="ACCRUE_INTEREST",
            effective_date=datetime(2020, 1, 6, 0, 0, tzinfo=timezone.utc),
        )
        # (0.0199 + 0.0001)/365 * (800000) = 43.83562
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[
                (dimensions.PRINCIPAL, "800000"),
                (dimensions.EMI, "7361.08"),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "43.83560"),
            ],
        )

        # make lump sum deposit
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=home_loan_redraw_account_id,
            amount="100000",
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=datetime(2020, 1, 6, 1, 0, tzinfo=timezone.utc),
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[
                (dimensions.PRINCIPAL, "800000"),
                (dimensions.EMI, "7361.08"),
                (dimensions.REDRAW, "-100000"),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "43.83560"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=home_loan_redraw_account_id,
            schedule_name="ACCRUE_INTEREST",
            effective_date=datetime(2020, 1, 7, 0, 0, tzinfo=timezone.utc),
        )
        # round(round((0.0199 + 0.0001)/365, 10) * (800000-100000),5) = 38.35615
        # 38.35615 + 43.83560 = 82.19175
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[
                (dimensions.PRINCIPAL, "800000"),
                (dimensions.EMI, "7361.08"),
                (dimensions.REDRAW, "-100000"),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "82.19175"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=home_loan_redraw_account_id,
            schedule_name="DUE_AMOUNT_CALCULATION",
            effective_date=datetime(2020, 2, 5, 0, 1, tzinfo=timezone.utc),
        )
        # due balances should be repaid using available redraw funds
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[
                (dimensions.PRINCIPAL, "792721.11"),
                (dimensions.REDRAW, "-92638.92"),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                (dimensions.EMI, "7361.08"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.INTEREST_DUE, "0"),
            ],
        )

        # Withdraw more than available redraw funds
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=home_loan_redraw_account_id,
            amount="100000",
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=datetime(2020, 2, 6, 0, 0, tzinfo=timezone.utc),
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Withdraw most of available redraw funds
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=home_loan_redraw_account_id,
            amount="90000",
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=datetime(2020, 2, 6, 0, 1, tzinfo=timezone.utc),
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[
                (dimensions.PRINCIPAL, "792721.11"),
                (dimensions.REDRAW, "-2638.92"),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                (dimensions.EMI, "7361.08"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.INTEREST_DUE, "0"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=home_loan_redraw_account_id,
            schedule_name="ACCRUE_INTEREST",
            effective_date=datetime(2020, 1, 8, 0, 0, tzinfo=timezone.utc),
        )
        # we still accrue with a redraw balance of 100000 here
        # round(round((0.0199 + 0.0001)/365, 10) * (800000-100000),5) = 38.35615
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[
                (dimensions.PRINCIPAL, "792721.11"),
                (dimensions.REDRAW, "-2638.92"),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "38.35615"),
                (dimensions.EMI, "7361.08"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.INTEREST_DUE, "0"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=home_loan_redraw_account_id,
            schedule_name="DUE_AMOUNT_CALCULATION",
            effective_date=datetime(2020, 3, 5, 0, 1, tzinfo=timezone.utc),
        )
        # some due principal should be repaid using remaining redraw funds
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[
                (dimensions.PRINCIPAL, "785360.03"),
                (dimensions.REDRAW, "0"),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                (dimensions.EMI, "7361.08"),
                # we would expect to see 7361.08 - 38.36 - 2638.92 = 4683.80 but the interest is
                # treated as non-emi because we accrued on 2020-01-08 and this is due amount calc
                # for 2020-03-05 so instead we see 7361.08 - 2638.92 = 4722.16
                (dimensions.PRINCIPAL_DUE, "4722.16"),
                (dimensions.INTEREST_DUE, "38.36"),
            ],
        )

    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {HOME_LOAN_REDRAW: ["DUE_AMOUNT_CALCULATION", "ACCRUE_INTEREST"]}
    )
    def test_home_loan_redraw_closure(self):
        endtoend.standard_setup()
        opening_date = datetime(year=2020, month=1, day=5, hour=0, minute=1, tzinfo=timezone.utc)
        customer_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )["id"]

        instance_params = e2e_parameters.default_instance.copy()
        instance_params["deposit_account"] = dummy_account_id
        instance_params["due_amount_calculation_day"] = "5"
        instance_params["total_repayment_count"] = "1"

        home_loan_redraw_account_id = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=HOME_LOAN_REDRAW,
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )["id"]
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[(dimensions.PRINCIPAL, "800000"), (dimensions.EMI, "801333.33")],
        )

        endtoend.core_api_helper.update_account(
            home_loan_redraw_account_id,
            AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE,
        )
        endtoend.accounts_helper.wait_for_account_update(
            account_id=home_loan_redraw_account_id,
            account_update_type="closure_update",
            target_status="ACCOUNT_UPDATE_STATUS_REJECTED",
        )
        # verify closure update rejected with correct rejection
        account_closure_update = endtoend.core_api_helper.get_account_updates_by_type(
            account_id=home_loan_redraw_account_id, update_types=["closure_update"]
        )
        for update in account_closure_update:
            self.assertEqual(
                update["failure_reason"],
                "contract engine error from deactivation hook: The loan cannot be closed until"
                " all outstanding debt is repaid",
            )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=home_loan_redraw_account_id,
            schedule_name="ACCRUE_INTEREST",
            effective_date=datetime(2020, 1, 6, 0, 0, tzinfo=timezone.utc),
        )
        # (0.0199 + 0.0001)/365 * (800000) = 43.83562
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[
                (dimensions.PRINCIPAL, "800000"),
                (dimensions.EMI, "801333.33"),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "43.83560"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=home_loan_redraw_account_id,
            schedule_name="ACCRUE_INTEREST",
            effective_date=datetime(2020, 1, 7, 0, 0, tzinfo=timezone.utc),
        )
        # round(round((0.0199 + 0.0001)/365,10) * (800000), 5) = 43.83560
        # 43.83562*2 = 87.67120
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[
                (dimensions.PRINCIPAL, "800000"),
                (dimensions.EMI, "801333.33"),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "87.67120"),
            ],
        )

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            account_id=home_loan_redraw_account_id,
            schedule_name="DUE_AMOUNT_CALCULATION",
            effective_date=datetime(2020, 2, 5, 0, 1, tzinfo=timezone.utc),
        )
        # due balances should be repaid using available redraw funds
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[
                (dimensions.PRINCIPAL, "0"),
                (dimensions.REDRAW, "0"),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                (dimensions.EMI, "801333.33"),
                (dimensions.PRINCIPAL_DUE, "800000"),
                (dimensions.INTEREST_DUE, "87.67"),
            ],
        )

        # Repay due amount
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=home_loan_redraw_account_id,
            amount="800087.67",
            denomination=parameters.TEST_DENOMINATION,
            value_datetime=datetime(2020, 2, 5, 0, 2, tzinfo=timezone.utc),
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[
                (dimensions.PRINCIPAL, "0"),
                (dimensions.REDRAW, "0"),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                (dimensions.EMI, "801333.33"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.INTEREST_DUE, "0"),
            ],
        )
        endtoend.contracts_helper.wait_for_contract_notification(
            notification_type="HOME_LOAN_REDRAW_PAID_OFF",
            notification_details={"account_id": home_loan_redraw_account_id},
            resource_id=home_loan_redraw_account_id,
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        account_update_id = endtoend.core_api_helper.create_closure_update(
            account_id=home_loan_redraw_account_id
        )["id"]

        # verify closure update completes successfully
        endtoend.accounts_helper.wait_for_account_update(
            account_update_id=account_update_id, target_status="ACCOUNT_UPDATE_STATUS_COMPLETED"
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=home_loan_redraw_account_id,
            expected_balances=[
                (dimensions.PRINCIPAL, "0"),
                (dimensions.REDRAW, "0"),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                (dimensions.EMI, "0"),
                (dimensions.PRINCIPAL_DUE, "0"),
                (dimensions.INTEREST_DUE, "0"),
            ],
        )
