# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
from unittest import skip

from library.credit_card.tests.utils.common.common import (
    offset_datetime,
    LOCAL_UTC_OFFSET,
    convert_utc_to_local_schedule,
)
from library.credit_card.tests.utils.common.lending import (
    AVAILABLE,
    INTERNAL,
    OUTSTANDING,
    FULL_OUTSTANDING,
    DEPOSIT,
    CASH_ADVANCE_NEW,
    PURCHASE_AUTH,
    PURCHASE_NEW,
    TOTAL_REPAYMENTS_LAST_STATEMENT,
    EVENT_ACCRUE,
    EVENT_ANNUAL_FEE,
    EVENT_PDD,
    EVENT_SCOD,
)
from library.credit_card.contracts.tests.utils.unit.common import (
    update_event_type_call,
    compare_balances,
    init_balances,
    instruct_posting_batch_call,
    make_internal_transfer_instructions_call,
    ACCOUNT_ID,
    HOOK_EXECUTION_ID,
)
from library.credit_card.contracts.tests.utils.unit.lending import (
    LendingContractTest,
    accrue_interest_call,
    all_charged_fee_calls,
    bill_interest_air_call,
    bill_interest_off_bs_call,
    charge_dispute_fee_loan_to_customer_call,
    charge_dispute_fee_off_bs_call,
    charge_fee_off_bs_call,
    charge_interest_air_call,
    charge_interest_call,
    charge_txn_type_fee_off_bs_call,
    cleanup_address_call,
    decrease_credit_limit_revocable_commitment_call,
    dispute_fee_rebalancing_call,
    fee_rebalancing_call,
    fee_loan_to_income_call,
    generic_fee_other_liability_gl_call,
    internal_to_address_call,
    increase_credit_limit_revocable_commitment_call,
    interest_rebalancing_call,
    interest_write_off_call,
    override_info_balance_call,
    principal_write_off_call,
    publish_statement_workflow_call,
    rebalance_statement_bucket_call,
    repayment_rebalancing_call,
    repay_billed_interest_off_bs_call,
    repay_billed_interest_customer_to_loan_call,
    repay_charged_dispute_fee_customer_to_loan_gl_call,
    repay_charged_fee_customer_to_loan_call,
    repay_charged_fee_off_bs_call,
    repay_charged_interest_gl_call,
    repay_other_liability_gl_call,
    repay_principal_revocable_commitment_call,
    repay_principal_loan_gl_call,
    reverse_uncharged_interest_call,
    zero_out_mad_balance_call,
    spend_principal_revocable_commitment_call,
    set_revolver_call,
    spend_other_liability_gl_call,
    statement_to_unpaid_call,
    spend_principal_customer_to_loan_gl_call,
    txn_fee_loan_to_income_call,
    txn_specific_fee_other_liability_gl_call,
    unset_revolver_call,
    ACCRUAL_TIME,
    SCOD_TIME,
    PDD_TIME,
    ANNUAL_FEE_TIME,
)

from datetime import datetime, timedelta
from decimal import Decimal
from json import dumps
from inception_sdk.test_framework.contracts.unit import run
from inception_sdk.vault.contracts.types_extension import (
    Phase,
    Rejected,
    InvalidContractParameter,
    Balance,
    Tside,
    EventTypeSchedule,
    BalanceDefaultDict,
)
from unittest.mock import ANY, Mock

# Misc
CONTRACT_FILE = "library/credit_card/contracts/credit_card.py"
DEFAULT_DATE = datetime(2019, 1, 1)
DEFAULT_DENOM = "GBP"


class ExecutionScheduleTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_schedules_for_standard_parameters(self):
        mock_vault = self.create_mock(
            account_creation_date=offset_datetime(2019, 2, 10, 10),
            payment_due_period=22,
        )

        actual_schedules = run(self.smart_contract, "execution_schedules", mock_vault)
        event_scod_schedule = convert_utc_to_local_schedule(
            month="3",
            day="10",
            hour=str(SCOD_TIME.hour),
            minute=str(SCOD_TIME.minute),
            second=str(SCOD_TIME.second),
        )
        event_annual_fee_schedule = convert_utc_to_local_schedule(
            hour=str(ANNUAL_FEE_TIME.hour),
            minute=str(ANNUAL_FEE_TIME.minute),
            second=str(ANNUAL_FEE_TIME.second),
        )
        event_pdd_schedule = convert_utc_to_local_schedule(
            month="4",
            day="1",
            hour=str(PDD_TIME.hour),
            minute=str(PDD_TIME.minute),
            second=str(PDD_TIME.second),
        )
        event_accrue_schedule = convert_utc_to_local_schedule(
            hour=str(ACCRUAL_TIME.hour),
            minute=str(ACCRUAL_TIME.minute),
            second=str(ACCRUAL_TIME.second),
        )
        self.assertEqual(
            actual_schedules,
            [
                (EVENT_SCOD, event_scod_schedule),
                (EVENT_ANNUAL_FEE, event_annual_fee_schedule),
                (EVENT_PDD, event_pdd_schedule),
                (EVENT_ACCRUE, event_accrue_schedule),
            ],
        )

    @skip("sim test explicitly declare next year to prevent infinity loop")
    def test_schedules_for_account_creation_date_after_23_50(self):
        balances = init_balances()

        account_creation_date = offset_datetime(2018, 12, 11, 23, 55)

        expected_calls = [
            update_event_type_call(
                event_type=EVENT_ANNUAL_FEE,
                schedule=EventTypeSchedule(
                    month="12",
                    day="11",
                    hour=str(ANNUAL_FEE_TIME.hour),
                    minute=str(ANNUAL_FEE_TIME.minute),
                    second=str(ANNUAL_FEE_TIME.second),
                ),
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_pdd_execution_time=None,
            account_creation_date=account_creation_date,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ANNUAL_FEE,
            effective_date=account_creation_date,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_match=True
        )

    @skip("sim test explicitly declare next year to prevent infinity loop")
    def test_schedules_for_account_creation_date_after_23_50_eom(self):
        balances = init_balances()

        account_creation_date = offset_datetime(2018, 1, 31, 23, 55)

        expected_calls = [
            update_event_type_call(
                event_type=EVENT_ANNUAL_FEE,
                schedule=EventTypeSchedule(
                    month="1",
                    day="31",
                    hour=str(ANNUAL_FEE_TIME.hour),
                    minute=str(ANNUAL_FEE_TIME.minute),
                    second=str(ANNUAL_FEE_TIME.second),
                ),
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_pdd_execution_time=None,
            account_creation_date=account_creation_date,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ANNUAL_FEE,
            effective_date=account_creation_date,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_match=True
        )

    @skip("sim test explicitly declare next year to prevent infinity loop")
    def test_schedules_for_account_creation_date_on_29th_feb(self):
        account_creation_date = offset_datetime(2020, 2, 29, 10)

        mock_vault = self.create_mock(
            account_creation_date=account_creation_date, payment_due_period=22
        )

        actual_schedules = run(self.smart_contract, "execution_schedules", mock_vault)
        event_scod_schedule = convert_utc_to_local_schedule(
            month="3",
            day="29",
            hour=str(SCOD_TIME.hour),
            minute=str(SCOD_TIME.minute),
            second=str(SCOD_TIME.second),
        )
        event_annual_fee_schedule = convert_utc_to_local_schedule(
            hour=str(ANNUAL_FEE_TIME.hour),
            minute=str(ANNUAL_FEE_TIME.minute),
            second=str(ANNUAL_FEE_TIME.second),
        )
        event_pdd_schedule = convert_utc_to_local_schedule(
            month="4",
            day="20",
            hour=str(PDD_TIME.hour),
            minute=str(PDD_TIME.minute),
            second=str(PDD_TIME.second),
        )
        event_accrue_schedule = convert_utc_to_local_schedule(
            hour=str(ACCRUAL_TIME.hour),
            minute=str(ACCRUAL_TIME.minute),
            second=str(ACCRUAL_TIME.second),
        )
        self.assertEqual(
            actual_schedules,
            [
                (EVENT_SCOD, event_scod_schedule),
                (EVENT_ANNUAL_FEE, event_annual_fee_schedule),
                (EVENT_PDD, event_pdd_schedule),
                (EVENT_ACCRUE, event_accrue_schedule),
            ],
        )

        balances = init_balances()

        expected_calls = [
            update_event_type_call(
                event_type=EVENT_ANNUAL_FEE,
                schedule=EventTypeSchedule(
                    month="2",
                    day="last",
                    hour=str(ANNUAL_FEE_TIME.hour),
                    minute=str(ANNUAL_FEE_TIME.minute),
                    second=str(ANNUAL_FEE_TIME.second),
                ),
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_pdd_execution_time=None,
            account_creation_date=account_creation_date,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ANNUAL_FEE,
            effective_date=account_creation_date,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_match=True
        )

    def test_schedules_for_account_created_mid_month(self):
        mock_vault = self.create_mock(
            account_creation_date=offset_datetime(2019, 7, 2, 15), payment_due_period=21
        )

        actual_schedules = run(self.smart_contract, "execution_schedules", mock_vault)
        event_scod_schedule = convert_utc_to_local_schedule(
            month="8",
            day="2",
            hour=str(SCOD_TIME.hour),
            minute=str(SCOD_TIME.minute),
            second=str(SCOD_TIME.second),
        )
        event_annual_fee_schedule = convert_utc_to_local_schedule(
            hour=str(ANNUAL_FEE_TIME.hour),
            minute=str(ANNUAL_FEE_TIME.minute),
            second=str(ANNUAL_FEE_TIME.second),
        )
        event_pdd_schedule = convert_utc_to_local_schedule(
            month="8",
            day="23",
            hour=str(PDD_TIME.hour),
            minute=str(PDD_TIME.minute),
            second=str(PDD_TIME.second),
        )
        event_accrue_schedule = convert_utc_to_local_schedule(
            hour=str(ACCRUAL_TIME.hour),
            minute=str(ACCRUAL_TIME.minute),
            second=str(ACCRUAL_TIME.second),
        )
        self.assertEqual(
            actual_schedules,
            [
                (EVENT_SCOD, event_scod_schedule),
                (EVENT_ANNUAL_FEE, event_annual_fee_schedule),
                (EVENT_PDD, event_pdd_schedule),
                (EVENT_ACCRUE, event_accrue_schedule),
            ],
        )

    def test_schedule_day_set_to_last_when_landing_on_month_end(self):
        mock_vault = self.create_mock(
            account_creation_date=offset_datetime(2019, 1, 1), payment_due_period=21
        )

        actual_schedules = run(self.smart_contract, "execution_schedules", mock_vault)
        event_scod_schedule = convert_utc_to_local_schedule(
            month="2",
            day="1",
            hour=str(SCOD_TIME.hour),
            minute=str(SCOD_TIME.minute),
            second=str(SCOD_TIME.second),
        )
        event_annual_fee_schedule = convert_utc_to_local_schedule(
            hour=str(ANNUAL_FEE_TIME.hour),
            minute=str(ANNUAL_FEE_TIME.minute),
            second=str(ANNUAL_FEE_TIME.second),
        )
        event_pdd_schedule = convert_utc_to_local_schedule(
            month="2",
            day="22",
            hour=str(PDD_TIME.hour),
            minute=str(PDD_TIME.minute),
            second=str(PDD_TIME.second),
        )
        event_accrue_schedule = convert_utc_to_local_schedule(
            hour=str(ACCRUAL_TIME.hour),
            minute=str(ACCRUAL_TIME.minute),
            second=str(ACCRUAL_TIME.second),
        )
        self.assertEqual(
            actual_schedules,
            [
                (EVENT_SCOD, event_scod_schedule),
                (EVENT_ANNUAL_FEE, event_annual_fee_schedule),
                (EVENT_PDD, event_pdd_schedule),
                (EVENT_ACCRUE, event_accrue_schedule),
            ],
        )

    def test_schedules_when_offset_and_utc_account_creation_date_differ(self):
        """
        Account creation date is 2019-01-02T00:00:00+0800, which is 2019-01-01T16:00:00Z
        schedules are based on UTC date, so expect same results as if OFFSET timezone date
        were equal to UTC date.
        """
        mock_vault = self.create_mock(
            account_creation_date=offset_datetime(2019, 1, 2), payment_due_period=21
        )

        actual_schedules = run(self.smart_contract, "execution_schedules", mock_vault)
        event_scod_schedule = convert_utc_to_local_schedule(
            month="2",
            day="2",
            hour=str(SCOD_TIME.hour),
            minute=str(SCOD_TIME.minute),
            second=str(SCOD_TIME.second),
        )
        event_annual_fee_schedule = convert_utc_to_local_schedule(
            hour=str(ANNUAL_FEE_TIME.hour),
            minute=str(ANNUAL_FEE_TIME.minute),
            second=str(ANNUAL_FEE_TIME.second),
        )
        event_pdd_schedule = convert_utc_to_local_schedule(
            month="2",
            day="23",
            hour=str(PDD_TIME.hour),
            minute=str(PDD_TIME.minute),
            second=str(PDD_TIME.second),
        )
        event_accrue_schedule = convert_utc_to_local_schedule(
            hour=str(ACCRUAL_TIME.hour),
            minute=str(ACCRUAL_TIME.minute),
            second=str(ACCRUAL_TIME.second),
        )
        self.assertEqual(
            actual_schedules,
            [
                (EVENT_SCOD, event_scod_schedule),
                (EVENT_ANNUAL_FEE, event_annual_fee_schedule),
                (EVENT_PDD, event_pdd_schedule),
                (EVENT_ACCRUE, event_accrue_schedule),
            ],
        )

    def test_schedule_repayment_day_unchanged_when_pdd_falls_on_sunday(self):
        mock_vault = self.create_mock(
            account_creation_date=offset_datetime(2019, 1, 24, 11),
            payment_due_period=22,
        )

        actual_schedules = run(self.smart_contract, "execution_schedules", mock_vault)
        event_scod_schedule = convert_utc_to_local_schedule(
            month="2",
            day="24",
            hour=str(SCOD_TIME.hour),
            minute=str(SCOD_TIME.minute),
            second=str(SCOD_TIME.second),
        )
        event_annual_fee_schedule = convert_utc_to_local_schedule(
            hour=str(ANNUAL_FEE_TIME.hour),
            minute=str(ANNUAL_FEE_TIME.minute),
            second=str(ANNUAL_FEE_TIME.second),
        )
        event_pdd_schedule = convert_utc_to_local_schedule(
            month="3",
            day="18",
            hour=str(PDD_TIME.hour),
            minute=str(PDD_TIME.minute),
            second=str(PDD_TIME.second),
        )
        event_accrue_schedule = convert_utc_to_local_schedule(
            hour=str(ACCRUAL_TIME.hour),
            minute=str(ACCRUAL_TIME.minute),
            second=str(ACCRUAL_TIME.second),
        )
        self.assertEqual(
            actual_schedules,
            [
                (EVENT_SCOD, event_scod_schedule),
                (EVENT_ANNUAL_FEE, event_annual_fee_schedule),
                (EVENT_PDD, event_pdd_schedule),
                (EVENT_ACCRUE, event_accrue_schedule),
            ],
        )


class ActivationTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_available_balance_initialised_with_credit_limit_on_account_activation(
        self,
    ):
        balances = init_balances(balance_defs=[{"address": "cash_advance_charged", "net": "2000"}])
        credit_limit = Decimal("1000")
        expected_calls = [
            internal_to_address_call(credit=False, amount=credit_limit, address=AVAILABLE)
        ]

        mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

        run(self.smart_contract, "post_activate_code", mock_vault)

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_available_balance_initialised_with_invalid_credit_limit_on_account_activation(
        self,
    ):
        for credit_limit in [Decimal("0"), Decimal("-1000")]:
            balances = init_balances(
                balance_defs=[{"address": "cash_advance_charged", "net": "2000"}]
            )
            unexpected_calls = [
                internal_to_address_call(credit=False, amount=credit_limit, address=AVAILABLE)
            ]

            mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

            run(self.smart_contract, "post_activate_code", mock_vault)

            self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_opening_account_credits_revocable_commitment(self):
        new_credit_limit = Decimal("2000")

        expected_calls = [
            increase_credit_limit_revocable_commitment_call(amount=new_credit_limit),
        ]

        mock_vault = self.create_mock(credit_limit=new_credit_limit)

        run(self.smart_contract, "post_activate_code", mock_vault)

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_single_posting_batch_instructed_for_account_activation(self):
        balances = init_balances(balance_defs=[{"address": "cash_advance_charged", "net": "2000"}])
        credit_limit = Decimal("-1000")
        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 1, 1),
                client_batch_id=f"POST_ACTIVATION-{HOOK_EXECUTION_ID}",
            )
        ]

        mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

        run(self.smart_contract, "post_activate_code", mock_vault)

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_match=True
        )


class AnnualFeeTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_simple_fee_rebalance(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "PURCHASE_CHARGED", "net": "75"},
                {"address": AVAILABLE, "net": "925"},
                {"address": OUTSTANDING, "net": "75"},
                {"address": FULL_OUTSTANDING, "net": "75"},
            ],
        )
        annual_fee_amount = "25"

        expected_calls = all_charged_fee_calls(
            fees=[{"fee_type": "ANNUAL_FEE", "fee_amount": annual_fee_amount}],
            initial_info_balances={
                AVAILABLE: "925",
                OUTSTANDING: "75",
                FULL_OUTSTANDING: "75",
            },
        )

        mock_vault = self.create_mock(balance_ts=balances, annual_fee=Decimal(annual_fee_amount))

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ANNUAL_FEE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_match=False)

    def test_annual_fee_charged_and_rebalanced_if_fee_is_non_zero(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "cash_advance_charged", "net": "500"},
                {"address": AVAILABLE, "net": "500"},
                {"address": OUTSTANDING, "net": "500"},
                {"address": FULL_OUTSTANDING, "net": "500"},
            ],
        )
        annual_fee_amount = "100"

        expected_calls = all_charged_fee_calls(
            fees=[{"fee_type": "ANNUAL_FEE", "fee_amount": annual_fee_amount}],
            initial_info_balances={
                AVAILABLE: "500",
                OUTSTANDING: "500",
                FULL_OUTSTANDING: "500",
            },
        )

        mock_vault = self.create_mock(balance_ts=balances, annual_fee=Decimal(annual_fee_amount))

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ANNUAL_FEE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_match=False)

    def test_annual_fee_not_charged_if_fee_is_zero(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[{"address": "DEFAULT", "net": "0"}],
        )
        annual_fee_amount = "0"

        expected_calls = []

        mock_vault = self.create_mock(balance_ts=balances, annual_fee=Decimal(annual_fee_amount))

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ANNUAL_FEE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_match=True
        )

    def test_charging_annual_fee_does_not_cause_deposit_to_go_positive(self):
        annual_fee_amount = 100
        deposit_amount = 40

        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[{"address": DEPOSIT, "net": deposit_amount}],
        )

        expected_calls = [
            fee_rebalancing_call(amount=annual_fee_amount - deposit_amount, fee_type="ANNUAL_FEE"),
            fee_rebalancing_call(
                amount=annual_fee_amount, fee_type="ANNUAL_FEE", from_address="DEFAULT"
            ),
            fee_rebalancing_call(
                amount=-deposit_amount,
                fee_type="ANNUAL_FEE",
                from_address="DEPOSIT",
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances, annual_fee=Decimal(annual_fee_amount))

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ANNUAL_FEE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_charging_annual_fee_from_deposit_causes_internal_postings(self):
        annual_fee_amount = 100
        deposit_amount = 40

        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[{"address": DEPOSIT, "net": deposit_amount}],
        )

        expected_calls = [
            generic_fee_other_liability_gl_call(amount=deposit_amount, fee_type="ANNUAL_FEE"),
            charge_fee_off_bs_call(
                amount=annual_fee_amount - deposit_amount, fee_type="ANNUAL_FEE"
            ),
            # TODO: full income should be posted
            fee_loan_to_income_call(
                amount=annual_fee_amount - deposit_amount, fee_type="ANNUAL_FEE"
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances, annual_fee=Decimal(annual_fee_amount))

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ANNUAL_FEE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_single_posting_batch_instructed_for_annual_fee(self):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[{"address": "PURCHASE_CHARGED", "net": "1000"}],
        )

        annual_fee_amount = "100"

        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
                client_batch_id=f"ANNUAL_FEE-{HOOK_EXECUTION_ID}",
            )
        ]

        mock_vault = self.create_mock(balance_ts=balances, annual_fee=Decimal(annual_fee_amount))

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ANNUAL_FEE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls, exact_order=True, exact_match=True
        )


class ParameterChangeTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    # TODO: investigate use of pytest parameterize for repayment hierarchy scenarios
    def test_increasing_credit_limit_increases_available_balance(self):
        new_credit_limit = Decimal("2000")
        old_credit_limit = Decimal("1000")

        expected_calls = [
            internal_to_address_call(
                credit=False,
                amount=new_credit_limit - old_credit_limit,
                address=AVAILABLE,
            ),
        ]

        mock_vault = self.create_mock(credit_limit=old_credit_limit)

        run(
            self.smart_contract,
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"credit_limit": old_credit_limit},
            updated_parameter_values={"credit_limit": new_credit_limit},
            effective_date=offset_datetime(2019, 1, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_increasing_credit_limit_credits_revocable_commitment(self):
        new_credit_limit = Decimal("2000")
        old_credit_limit = Decimal("1000")

        expected_calls = [
            increase_credit_limit_revocable_commitment_call(
                amount=abs(new_credit_limit - old_credit_limit),
            ),
        ]

        mock_vault = self.create_mock(credit_limit=old_credit_limit)

        run(
            self.smart_contract,
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"credit_limit": old_credit_limit},
            updated_parameter_values={"credit_limit": new_credit_limit},
            effective_date=offset_datetime(2019, 1, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_decreasing_credit_limit_reduces_available_balance(self):
        new_credit_limit = Decimal("1000")
        old_credit_limit = Decimal("2000")

        expected_calls = [
            internal_to_address_call(
                credit=True,
                amount=old_credit_limit - new_credit_limit,
                address=AVAILABLE,
            ),
        ]

        mock_vault = self.create_mock(credit_limit=old_credit_limit)

        run(
            self.smart_contract,
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"credit_limit": old_credit_limit},
            updated_parameter_values={"credit_limit": new_credit_limit},
            effective_date=offset_datetime(2019, 1, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=True
        )

    def test_decreasing_credit_limit_debits_revocable_commitment(self):
        new_credit_limit = Decimal("1000")
        old_credit_limit = Decimal("2000")

        expected_calls = [
            decrease_credit_limit_revocable_commitment_call(
                amount=abs(new_credit_limit - old_credit_limit),
            ),
        ]

        mock_vault = self.create_mock(credit_limit=old_credit_limit)

        run(
            self.smart_contract,
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"credit_limit": old_credit_limit},
            updated_parameter_values={"credit_limit": new_credit_limit},
            effective_date=offset_datetime(2019, 1, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_changing_a_parameter_other_than_credit_limit_does_not_impact_available_balance(
        self,
    ):
        unexpected_calls = [
            internal_to_address_call(credit=ANY, amount=ANY, address=AVAILABLE),
        ]

        mock_vault = self.create_mock()

        run(
            self.smart_contract,
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"overlimit": "1"},
            updated_parameter_values={"overlimit": "2"},
            effective_date=offset_datetime(2019, 1, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_single_posting_batch_instructed_for_parameter_changes(self):
        new_credit_limit = Decimal("1000")
        old_credit_limit = Decimal("2000")

        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 1, 1),
                client_batch_id=f"POST_PARAMETER_CHANGE-{HOOK_EXECUTION_ID}",
            )
        ]

        mock_vault = self.create_mock(credit_limit=old_credit_limit)

        run(
            self.smart_contract,
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"credit_limit": old_credit_limit},
            updated_parameter_values={"credit_limit": new_credit_limit},
            effective_date=offset_datetime(2019, 1, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_match=True)


class PostPostingTxnRebalancingTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_outbound_hard_settlement_rebalancing(self):
        hard_settlement_amount = Decimal("100")
        balances = init_balances(
            # Equivalent to no spend/auth before this posting
            balance_defs=[{"address": "DEFAULT", "net": "100"}]
        )

        expected_calls = [
            internal_to_address_call(
                credit=False, address=PURCHASE_NEW, amount=hard_settlement_amount
            )
        ]
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.hard_settlement(amount=hard_settlement_amount)]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_outbound_hard_settlement_gl_postings(self):
        hard_settlement_amount = Decimal("100")
        balances = init_balances(
            # Equivalent to no spend/auth before this posting
            balance_defs=[{"address": "DEFAULT", "net": "100"}]
        )

        expected_calls = [
            spend_principal_customer_to_loan_gl_call(amount=hard_settlement_amount),
            spend_principal_revocable_commitment_call(amount=hard_settlement_amount),
        ]
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.hard_settlement(amount=hard_settlement_amount)]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_auth_rebalancing(self):
        auth_amount = Decimal("100")
        balances = init_balances(
            # Equivalent to no auth before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "0"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "10"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=False, address=PURCHASE_AUTH, amount=auth_amount)
        ]
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase_auth(amount=auth_amount)]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_auth_gl_postings(self):
        auth_amount = Decimal("100")
        balances = init_balances(
            # Equivalent to no auth before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "0"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "10"},
            ]
        )
        unexpected_calls = [
            spend_principal_revocable_commitment_call(),
            spend_principal_customer_to_loan_gl_call(),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase_auth(amount=auth_amount)]
        )
        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_auth_changes_affects_available_but_not_outstanding(self):
        auth_amount = Decimal("100")
        balances = init_balances(
            # Equivalent to no auth before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "0"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "100"},
                {"address": "AVAILABLE_BALANCE", "net": "1000"},
                {"address": "OUTSTANDING_BALANCE", "net": "0"},
                {"address": "FULL_OUTSTANDING_BALANCE", "net": "0"},
            ]
        )

        expected_calls = [
            internal_to_address_call(amount=auth_amount, credit=True, address=AVAILABLE),
        ]
        unexpected_calls = [
            internal_to_address_call(amount=auth_amount, credit=False, address=OUTSTANDING),
            internal_to_address_call(amount=auth_amount, credit=False, address=FULL_OUTSTANDING),
        ]
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase_auth(amount=auth_amount)]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, unexpected_calls)

    def test_auth_does_not_affect_deposit(self):
        balances = init_balances(
            balance_defs=[
                {"address": "available_balance", "net": "5500"},
                {"address": "DEPOSIT", "net": "500"},
                {"address": "outstanding_balance", "net": "500"},
                {"address": "full_outstanding_balance", "net": "500"},
            ]
        )
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase_auth(amount="1000")]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )
        mock_calls = mock_vault.mock_calls

        self.assertEqual(
            make_internal_transfer_instructions_call(
                from_account_address="DEPOSIT", to_account_address=INTERNAL, amount=ANY
            )
            in mock_calls,
            False,
        )

    def test_increasing_auth_rebalancing(self):
        auth_adjust_amount = Decimal("100")
        balances = init_balances(
            # Equivalent to $10 auth before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "0"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "110"},
                {"address": "PURCHASE_AUTH", "net": "10"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=False, address=PURCHASE_AUTH, amount=auth_adjust_amount)
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_auth_adjust(amount=auth_adjust_amount)]
        )
        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_increasing_auth_no_gl_postings(self):
        auth_adjust_amount = Decimal("100")
        balances = init_balances(
            # Equivalent to $10 auth before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "0"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "110"},
                {"address": "PURCHASE_AUTH", "net": "10"},
            ]
        )

        unexpected_calls = [
            spend_principal_revocable_commitment_call(),
            spend_principal_customer_to_loan_gl_call(),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_auth_adjust(amount=auth_adjust_amount)]
        )
        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_decreasing_auth_rebalancing(self):
        auth_adjust_amount = Decimal("-10")
        balances = init_balances(
            # Equivalent to £10 auth before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "0"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "10"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=False, address=AVAILABLE, amount=Decimal("1000")),
            internal_to_address_call(credit=True, address=PURCHASE_AUTH, amount=Decimal("10")),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_auth_adjust(amount=auth_adjust_amount)]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_decreasing_auth_no_gl_postings(self):
        auth_adjust_amount = Decimal("-10")
        balances = init_balances(
            # Equivalent to $10 auth before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "0"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "10"},
            ]
        )

        unexpected_calls = [
            spend_principal_revocable_commitment_call(),
            spend_principal_customer_to_loan_gl_call(),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_auth_adjust(amount=auth_adjust_amount)]
        )
        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_releasing_unsettled_auth_credits_txn_auth_bucket(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        balances = init_balances(
            # Equivalent to $100 auth before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "0"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "100"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=True, address=PURCHASE_AUTH, amount=auth_amount)
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.release(unsettled_amount=unsettled_amount)]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_releasing_of_partially_settled_auth_credits_txn_auth_bucket(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("50")
        unsettled_amount = auth_amount - settled_amount
        balances = init_balances(
            # Equivalent to $100 auth that was partially settled for $50 before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "-50"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "50"},
                {"address": "PURCHASE_CHARGED", "net": "-50"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=True, address=PURCHASE_AUTH, amount=unsettled_amount),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.release(unsettled_amount=unsettled_amount)]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_releases_affect_available_but_not_outstanding(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("50")
        unsettled_amount = auth_amount - settled_amount
        balances = init_balances(
            # Equivalent to $100 auth that was partially settled for $50 before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "-50"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "50"},
                {"address": "PURCHASE_CHARGED", "net": "50"},
                {"address": AVAILABLE, "net": "900"},
                {"address": OUTSTANDING, "net": "50"},
                {"address": FULL_OUTSTANDING, "net": "50"},
            ]
        )

        expected_calls = [
            internal_to_address_call(amount=unsettled_amount, credit=False, address=AVAILABLE),
        ]
        unexpected_calls = [
            internal_to_address_call(amount=ANY, credit=False, address=OUTSTANDING),
            internal_to_address_call(amount=ANY, credit=False, address=FULL_OUTSTANDING),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.release(unsettled_amount=unsettled_amount)]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, unexpected_calls)

    def test_releasing_fully_settled_auth_does_not_affect_txn_auth_bucket(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("100")
        unsettled_amount = auth_amount - settled_amount
        balances = init_balances(
            # Equivalent to $100 auth that was fully settled before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "-100"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "0"},
                {"address": "PURCHASE_CHARGED", "net": "-100"},
            ]
        )

        unexpected_calls = [
            internal_to_address_call(credit=True, address=PURCHASE_AUTH),
            internal_to_address_call(credit=False, address=PURCHASE_AUTH),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.release(unsettled_amount=unsettled_amount)]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_final_settle_of_unsettled_auth_credits_auth_and_debits_charged(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = None
        settle_is_final = True
        balances = init_balances(
            # Equivalent to $100 auth that was unsettled before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "100"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "100"},
                {"address": "PURCHASE_CHARGED", "net": "0"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=True, address=PURCHASE_AUTH, amount=auth_amount),
            internal_to_address_call(credit=False, address=PURCHASE_NEW, amount=auth_amount),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_final_settle_of_unsettled_auth_gl_postings(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = None
        settle_is_final = True
        balances = init_balances(
            # Equivalent to $100 auth that was unsettled before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "100"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "100"},
                {"address": "PURCHASE_CHARGED", "net": "0"},
            ]
        )

        expected_calls = [
            spend_principal_revocable_commitment_call(amount=unsettled_amount, txn_type="purchase"),
            spend_principal_customer_to_loan_gl_call(
                amount=unsettled_amount,
                txn_type_account_id="purchase_internal_account",
                txn_type="purchase",
            ),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_final_settle_of_partially_settled_auth_credits_auth_and_debits_new(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("50")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = None
        settle_is_final = True
        balances = init_balances(
            # Equivalent to $100 auth that was partially settled by 50 before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "100"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "50"},
                {"address": "PURCHASE_CHARGED", "net": "50"},
            ]
        )

        expected_calls = [
            internal_to_address_call(
                credit=True, address=PURCHASE_AUTH, amount=auth_amount - settled_amount
            ),
            internal_to_address_call(
                credit=False, address=PURCHASE_NEW, amount=auth_amount - settled_amount
            ),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_final_oversettle_partially_settled_auth_zeroes_auth_and_dr_new_by_oversettle_amt(
        self,
    ):
        auth_amount = Decimal("100")
        settled_amount = Decimal("50")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("125")
        settle_is_final = True
        balances = init_balances(
            # Equivalent to $100 auth that was partially settled by 50 before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "175"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "50"},
                {"address": "PURCHASE_CHARGED", "net": "50"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=True, address=PURCHASE_AUTH, amount=unsettled_amount),
            internal_to_address_call(credit=False, address=PURCHASE_NEW, amount=settle_amount),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_oversettle_partially_settled_auth_zeroes_auth_and_debits_new_by_oversettle_amt(
        self,
    ):
        auth_amount = Decimal("100")
        settled_amount = Decimal("50")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("125")
        settle_is_final = False
        balances = init_balances(
            # Equivalent to $100 auth that was partially settled by 50 before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "175"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "50"},
                {"address": "PURCHASE_CHARGED", "net": "50"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=True, address=PURCHASE_AUTH, amount=unsettled_amount),
            internal_to_address_call(credit=False, address=PURCHASE_NEW, amount=settle_amount),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_final_undersettle_auth_zeroes_auth_and_debits_new_by_undersettle_amount(
        self,
    ):
        auth_amount = Decimal("100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("75")
        settle_is_final = True
        balances = init_balances(
            # Equivalent to $100 auth that was unsettled before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "75"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "100"},
                {"address": "PURCHASE_CHARGED", "net": "0"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=True, address=PURCHASE_AUTH, amount=unsettled_amount),
            internal_to_address_call(credit=False, address=PURCHASE_NEW, amount=settle_amount),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_final_undersettle_affects_outstanding_and_available(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("75")
        settle_is_final = True
        balances = init_balances(
            # Equivalent to $100 auth that was unsettled before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "75"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "100"},
                {"address": "PURCHASE_CHARGED", "net": "0"},
                {"address": AVAILABLE, "net": "900"},
                {"address": OUTSTANDING, "net": "0"},
                {"address": FULL_OUTSTANDING, "net": "0"},
            ]
        )

        expected_calls = [
            internal_to_address_call(
                amount=unsettled_amount - settle_amount, credit=False, address=AVAILABLE
            ),
            internal_to_address_call(amount=settle_amount, credit=False, address=OUTSTANDING),
            internal_to_address_call(amount=settle_amount, credit=False, address=FULL_OUTSTANDING),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_undersettle_of_auth_credits_auth_and_debits_new_by_settle_amount(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("75")
        settle_is_final = False
        balances = init_balances(
            # Equivalent to $100 auth that was unsettled before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "75"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "25"},
                {"address": "PURCHASE_AUTH", "net": "100"},
                {"address": "PURCHASE_CHARGED", "net": "0"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=True, address=PURCHASE_AUTH, amount=settle_amount),
            internal_to_address_call(credit=False, address=PURCHASE_NEW, amount=settle_amount),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_full_settling_affects_outstanding_but_not_available(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = None
        settle_is_final = True
        balances = init_balances(
            # Equivalent to $100 auth that was unsettled before this posting
            balance_defs=[
                {"address": "DEFAULT", "net": "100"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "100"},
                {"address": "PURCHASE_CHARGED", "net": "0"},
                {"address": AVAILABLE, "net": "900"},
                {"address": OUTSTANDING, "net": "0"},
                {"address": FULL_OUTSTANDING, "net": "0"},
            ]
        )

        expected_calls = [
            internal_to_address_call(amount=unsettled_amount, credit=False, address=OUTSTANDING),
            internal_to_address_call(
                amount=unsettled_amount, credit=False, address=FULL_OUTSTANDING
            ),
        ]
        unexpected_calls = [
            internal_to_address_call(amount=ANY, credit=False, address=AVAILABLE),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, unexpected_calls)

    def test_settling_less_than_deposit_doesnt_debit_principal_address(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("100")
        settle_is_final = True
        balances = init_balances(
            # Equivalent to $100 auth and $200 deposit before settling fully
            balance_defs=[
                {"address": "DEFAULT", "net": "-100"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "100"},
                {"address": "PURCHASE_CHARGED", "net": "0"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=True, address=PURCHASE_AUTH, amount=auth_amount),
        ]

        expected_calls = [
            internal_to_address_call(amount=unsettled_amount, credit=False, address=OUTSTANDING),
            internal_to_address_call(
                amount=unsettled_amount, credit=False, address=FULL_OUTSTANDING
            ),
        ]
        unexpected_calls = [
            internal_to_address_call(credit=True, address=PURCHASE_NEW, amount=ANY),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, unexpected_calls)

    def test_settling_less_than_deposit_gl_postings(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("100")
        settle_is_final = True
        balances = init_balances(
            # Equivalent to $100 auth and $200 deposit before settling fully
            balance_defs=[
                {"address": "DEFAULT", "net": "-100"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "DEPOSIT", "net": "200"},
                {"address": "PURCHASE_AUTH", "net": "100"},
                {"address": "PURCHASE_CHARGED", "net": "0"},
            ]
        )

        expected_calls = [
            spend_other_liability_gl_call(
                amount=settle_amount, trigger="PRINCIPAL_SPENT", txn_type="PURCHASE"
            )
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )
        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_settling_more_than_deposit_partially_debits_principal_address(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("75")
        settle_is_final = True
        balances = init_balances(
            # Equivalent to $100 auth and $50 deposit before settling
            balance_defs=[
                {"address": "DEFAULT", "net": "25"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "DEPOSIT", "net": "50"},
                {"address": "PURCHASE_AUTH", "net": "100"},
                {"address": "PURCHASE_CHARGED", "net": "0"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=True, address=PURCHASE_AUTH, amount=auth_amount),
            internal_to_address_call(credit=False, address=PURCHASE_NEW, amount=settle_amount - 50),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_settling_more_than_deposit_gl_postings(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("75")
        settle_is_final = True
        deposit_amount = Decimal("50")
        balances = init_balances(
            # Equivalent to $100 auth and $50 deposit before settling
            balance_defs=[
                {"address": "DEFAULT", "net": "25"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "100"},
                {"address": "PURCHASE_CHARGED", "net": "0"},
                {"address": "DEPOSIT", "net": "50"},
            ]
        )

        expected_calls = [
            spend_other_liability_gl_call(
                amount=deposit_amount, trigger="PRINCIPAL_SPENT", txn_type="PURCHASE"
            ),
            spend_principal_customer_to_loan_gl_call(amount=settle_amount - deposit_amount),
            spend_principal_revocable_commitment_call(amount=settle_amount - deposit_amount),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )
        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_settling_more_than_deposit_updates_outstanding(self):
        auth_amount = Decimal("100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("75")
        settle_is_final = True
        balances = init_balances(
            # Equivalent to $100 auth and $50 deposit before settling
            balance_defs=[
                {"address": "DEFAULT", "net": "25"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "100"},
                {"address": "PURCHASE_CHARGED", "net": "0"},
                {"address": "DEPOSIT", "net": "50"},
                {"address": AVAILABLE, "net": "950"},
                {"address": OUTSTANDING, "net": "-50"},
                {"address": FULL_OUTSTANDING, "net": "-50"},
            ]
        )

        expected_calls = [
            internal_to_address_call(
                amount=unsettled_amount - settle_amount, credit=False, address=AVAILABLE
            ),
            internal_to_address_call(amount=settle_amount, credit=False, address=OUTSTANDING),
            internal_to_address_call(amount=settle_amount, credit=False, address=FULL_OUTSTANDING),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(balances, auth_amount, settled_amount, unsettled_amount)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_partial_settle_past_credit_limit_is_moved_from_auth_to_new_bucket(self):
        auth_amount = Decimal("1100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("1100")
        settle_is_final = False
        credit_limit = Decimal("1000")
        balances = init_balances(
            # Equivalent to $1100 auth before settling fully
            balance_defs=[
                {"address": "DEFAULT", "net": "1100"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "1100"},
                {"address": "PURCHASE_CHARGED", "net": "0"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=True, address=PURCHASE_AUTH, amount="1100"),
            internal_to_address_call(credit=False, address=PURCHASE_NEW, amount="1100"),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(
            balances,
            auth_amount,
            settled_amount,
            unsettled_amount,
            credit_limit=credit_limit,
        )

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_partial_settle_past_credit_limit_gl_postings(self):
        auth_amount = Decimal("1100")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("1100")
        settle_is_final = False
        credit_limit = Decimal("1000")
        balances = init_balances(
            # Equivalent to $1100 auth before settling fully
            balance_defs=[
                {"address": "DEFAULT", "net": "1100"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "1100"},
                {"address": "PURCHASE_CHARGED", "net": "0"},
            ]
        )

        expected_calls = [
            spend_principal_customer_to_loan_gl_call(
                amount=settle_amount,
                txn_type_account_id="purchase_internal_account",
                txn_type="purchase",
            ),
            spend_principal_revocable_commitment_call(amount=credit_limit, txn_type="purchase"),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(
            balances,
            auth_amount,
            settled_amount,
            unsettled_amount,
            credit_limit=credit_limit,
        )

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_principal_spend_entirely_past_limit_gl_postings(self):
        auth_amount = Decimal("1000")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("1000")
        settle_is_final = False
        credit_limit = Decimal("1000")
        balances = init_balances(
            # Equivalent to $1000 auth and $1000 purchase deposit before settling fully
            balance_defs=[
                {"address": "DEFAULT", "net": "2000"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "1000"},
                {"address": "PURCHASE_CHARGED", "net": "1000"},
            ]
        )

        expected_calls = [
            spend_principal_customer_to_loan_gl_call(
                amount=settle_amount,
                txn_type_account_id="purchase_internal_account",
                txn_type="purchase",
            ),
        ]
        unexpected_calls = [
            spend_principal_revocable_commitment_call(amount=ANY, txn_type="purchase"),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.settle(
                    amount=settle_amount,
                    final=settle_is_final,
                    unsettled_amount=unsettled_amount,
                )
            ]
        )

        mock_vault = self.mock_with_auth(
            balances,
            auth_amount,
            settled_amount,
            unsettled_amount,
            credit_limit=credit_limit,
        )

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_outbound_settlement_causes_gl_postings(self):
        balances = init_balances()
        credit_limit = Decimal("5000")
        auth_amount = Decimal("1500")
        settle_amount = Decimal("1000")

        posting_instructions = [self.settle(amount=settle_amount, final=True)]

        expected_calls = [
            spend_principal_revocable_commitment_call(amount=settle_amount, txn_type="purchase"),
            spend_principal_customer_to_loan_gl_call(
                amount=settle_amount,
                txn_type_account_id="purchase_internal_account",
                txn_type="purchase",
            ),
        ]

        # These are historic postings that the contract will retrieve (i.e. there is an
        # outstanding auth)
        ct_postings = [self.purchase_auth(auth_amount)]
        client_transaction = self.mock_client_transaction(
            postings=ct_postings,
            authorised=auth_amount,
            released=Decimal(0),
            settled=Decimal(0),
            unsettled=auth_amount,
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            credit_limit=credit_limit,
            client_transaction=client_transaction,
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )
        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_multiple_settlements_same_txn_types_partially_past_limit_rebalancing(self):
        hard_settle_amount_1 = Decimal("450")
        hard_settle_amount_2 = Decimal("600")
        balances = init_balances(
            # Equivalent to auth but no spend before batch
            balance_defs=[
                {"address": "DEFAULT", "net": "1050"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "500"},
            ]
        )

        posting_instructions = [
            self.cash_advance(amount=hard_settle_amount_1, posting_id="1"),
            self.cash_advance(amount=hard_settle_amount_2, posting_id="2"),
        ]

        expected_calls = [
            internal_to_address_call(
                credit=False, address=CASH_ADVANCE_NEW, amount=hard_settle_amount_1
            ),
            internal_to_address_call(
                credit=False, address=CASH_ADVANCE_NEW, amount=hard_settle_amount_2
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )
        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_multiple_settlements_same_txn_types_partially_past_limit_gl_postings(self):
        hard_settle_amount_1 = Decimal("450")
        hard_settle_amount_2 = Decimal("600")
        balances = init_balances(
            # Equivalent to auth but no spend before batch
            balance_defs=[
                {"address": "DEFAULT", "net": "1050"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "500"},
            ]
        )

        posting_instructions = [
            self.cash_advance(amount=hard_settle_amount_1, posting_id="1"),
            self.cash_advance(amount=hard_settle_amount_2, posting_id="2"),
        ]

        expected_calls = [
            spend_principal_revocable_commitment_call(
                amount=hard_settle_amount_1, posting_id="1", txn_type="cash_advance"
            ),
            spend_principal_customer_to_loan_gl_call(
                amount=hard_settle_amount_1,
                posting_id="1",
                txn_type="cash_advance",
                txn_type_account_id="cash_advance_internal_account",
            ),
            spend_principal_revocable_commitment_call(
                amount=550, posting_id="2", txn_type="cash_advance"
            ),
            spend_principal_customer_to_loan_gl_call(
                amount=hard_settle_amount_2,
                posting_id="2",
                txn_type="cash_advance",
                txn_type_account_id="cash_advance_internal_account",
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )
        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_multiple_settlements_different_txn_types_rebalancing(self):
        auth_amount = Decimal("500")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("500")
        settle_is_final = True
        hard_settle_amount = Decimal("450")
        balances = init_balances(
            # Equivalent to auth but no spend before batch
            balance_defs=[
                {"address": "DEFAULT", "net": "950"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "500"},
            ]
        )

        posting_instructions = [
            self.settle(
                amount=settle_amount,
                final=settle_is_final,
                id="1",
                unsettled_amount=unsettled_amount,
            ),
            self.cash_advance(amount=hard_settle_amount, posting_id="2"),
        ]

        expected_calls = [
            internal_to_address_call(
                credit=False, address=CASH_ADVANCE_NEW, amount=hard_settle_amount
            ),
            internal_to_address_call(credit=True, address=PURCHASE_AUTH, amount=auth_amount),
            internal_to_address_call(credit=False, address=PURCHASE_NEW, amount=settle_amount),
        ]

        mock_vault = self.mock_with_auth(balances, auth_amount, settle_amount, unsettled_amount)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )
        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_multiple_settlements_different_txn_types_gl_postings(self):
        auth_amount = Decimal("500")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("500")
        settle_is_final = True
        hard_settle_amount = Decimal("450")
        balances = init_balances(
            # Equivalent to no spend before batch
            balance_defs=[
                {"address": "DEFAULT", "net": "950"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "500"},
            ]
        )

        posting_instructions = [
            self.cash_advance(amount=hard_settle_amount, posting_id="1"),
            self.settle(
                amount=settle_amount,
                final=settle_is_final,
                id="2",
                unsettled_amount=unsettled_amount,
            ),
        ]

        expected_calls = [
            spend_principal_revocable_commitment_call(
                amount=hard_settle_amount, posting_id="1", txn_type="cash_advance"
            ),
            spend_principal_customer_to_loan_gl_call(
                amount=hard_settle_amount,
                posting_id="1",
                txn_type="cash_advance",
                txn_type_account_id="cash_advance_internal_account",
            ),
            spend_principal_revocable_commitment_call(
                amount=settle_amount, posting_id="2", txn_type="purchase"
            ),
            spend_principal_customer_to_loan_gl_call(
                amount=settle_amount,
                posting_id="2",
                txn_type="purchase",
                txn_type_account_id="purchase_internal_account",
            ),
        ]

        mock_vault = self.mock_with_auth(balances, auth_amount, settle_amount, unsettled_amount)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )
        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_multiple_settlements_different_txn_types_updates_available_and_outstanding(
        self,
    ):
        auth_amount = Decimal("500")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("500")
        settle_is_final = True
        hard_settle_amount = Decimal("450")
        balances = init_balances(
            # Equivalent to auth but no spend before batch
            balance_defs=[
                {"address": "DEFAULT", "net": "950"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "PURCHASE_AUTH", "net": "500"},
                {"address": AVAILABLE, "net": "500"},
                {"address": OUTSTANDING, "net": "0"},
                {"address": FULL_OUTSTANDING, "net": "0"},
            ]
        )

        posting_instructions = [
            self.settle(
                amount=settle_amount,
                final=settle_is_final,
                id="1",
                unsettled_amount=unsettled_amount,
            ),
            self.cash_advance(amount=hard_settle_amount, posting_id="2"),
        ]

        expected_calls = [
            internal_to_address_call(credit=True, address=AVAILABLE, amount=hard_settle_amount),
            internal_to_address_call(
                credit=False,
                address=OUTSTANDING,
                amount=settle_amount + hard_settle_amount,
            ),
            internal_to_address_call(
                credit=False,
                address=FULL_OUTSTANDING,
                amount=settle_amount + hard_settle_amount,
            ),
        ]

        mock_vault = self.mock_with_auth(balances, auth_amount, settle_amount, unsettled_amount)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )
        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_multiple_settlements_partially_covered_by_deposit_rebalancing(self):
        auth_amount = Decimal("500")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("500")
        settle_is_final = True
        hard_settle_amount = Decimal("450")
        balances = init_balances(
            # Equivalent to 600 deposit before batch
            balance_defs=[
                {"address": "DEFAULT", "net": "350"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "DEPOSIT", "net": "600"},
                {"address": "PURCHASE_AUTH", "net": "500"},
            ]
        )

        posting_instructions = [
            self.cash_advance(amount=hard_settle_amount, posting_id="1"),
            self.settle(
                amount=settle_amount,
                final=settle_is_final,
                id="2",
                unsettled_amount=unsettled_amount,
            ),
        ]

        expected_calls = [
            internal_to_address_call(credit=True, address=PURCHASE_AUTH, amount=auth_amount),
            internal_to_address_call(credit=False, address=PURCHASE_NEW, amount=350),
        ]
        unexpected_calls = [
            internal_to_address_call(credit=False, address=CASH_ADVANCE_NEW, amount=ANY),
        ]

        mock_vault = self.mock_with_auth(balances, auth_amount, settle_amount, unsettled_amount)
        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_multiple_settlements_partially_covered_by_deposit_gl_postings(self):
        auth_amount = Decimal("500")
        settled_amount = Decimal("0")
        unsettled_amount = auth_amount - settled_amount
        settle_amount = Decimal("500")
        settle_is_final = True
        hard_settle_amount = Decimal("450")
        balances = init_balances(
            # Equivalent to 600 deposit before batch
            balance_defs=[
                {"address": "DEFAULT", "net": "350"},
                {"address": "DEFAULT", "phase": Phase.PENDING_OUT, "net": "0"},
                {"address": "DEPOSIT", "net": "600"},
                {"address": "PURCHASE_AUTH", "net": "500"},
            ]
        )

        posting_instructions = [
            self.cash_advance(amount=hard_settle_amount, posting_id="1"),
            self.settle(
                amount=settle_amount,
                final=settle_is_final,
                id="2",
                unsettled_amount=unsettled_amount,
            ),
        ]

        expected_calls = [
            spend_other_liability_gl_call(
                amount="450",
                trigger="PRINCIPAL_SPENT",
                txn_type="CASH_ADVANCE",
                posting_id="1",
            ),
            spend_other_liability_gl_call(
                amount="150",
                trigger="PRINCIPAL_SPENT",
                txn_type="PURCHASE",
                posting_id="2",
            ),
            spend_principal_customer_to_loan_gl_call(amount="350", posting_id="2"),
            spend_principal_revocable_commitment_call(amount="350", posting_id="2"),
        ]

        mock_vault = self.mock_with_auth(balances, auth_amount, settle_amount, unsettled_amount)
        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )
        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)


class PostPostingExternalFeeRebalancingTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_external_fee_rebalancing(self):
        dispute_fee_amount = Decimal("100")
        balances = init_balances(
            # Equivalent to 0 spend/deposit before the fee is charged
            balance_defs=[{"address": "DEFAULT", "net": "-100"}]
        )

        expected_calls = [dispute_fee_rebalancing_call(amount=dispute_fee_amount)]
        unexpected_calls = [
            dispute_fee_rebalancing_call(amount=dispute_fee_amount, from_address="DEFAULT"),
        ]

        dispute_posting = self.dispute_fee(amount=Decimal(dispute_fee_amount))
        pib = self.mock_posting_instruction_batch(posting_instructions=[dispute_posting])

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_external_fee_gl_postings(self):
        dispute_fee_amount = Decimal("100")
        balances = init_balances(
            # Equivalent to 0 spend/deposit before the fee is charged
            balance_defs=[{"address": "DEFAULT", "net": "-100"}]
        )

        expected_calls = [
            charge_dispute_fee_loan_to_customer_call(amount=dispute_fee_amount),
            charge_dispute_fee_off_bs_call(amount=dispute_fee_amount),
        ]

        dispute_posting = self.dispute_fee(amount=Decimal(dispute_fee_amount))
        pib = self.mock_posting_instruction_batch(posting_instructions=[dispute_posting])

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_partially_extra_limit_external_fee_rebalancing(self):
        dispute_fee_amount = Decimal("100")
        credit_limit = Decimal("1000")
        balances = init_balances(
            # Equivalent to 975 spend before the fee is charged
            balance_defs=[
                {"address": "DEFAULT", "net": "-1075"},
                {"address": "PURCHASE_CHARGED", "net": "-975"},
            ]
        )

        expected_calls = [dispute_fee_rebalancing_call(amount=dispute_fee_amount)]
        unexpected_calls = [
            dispute_fee_rebalancing_call(amount=dispute_fee_amount, from_address="DEFAULT"),
        ]

        dispute_posting = self.dispute_fee(amount=Decimal(dispute_fee_amount))
        pib = self.mock_posting_instruction_batch(posting_instructions=[dispute_posting])

        mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_auth_bt_rebalances_txn_type_pot(self):
        balances = init_balances()
        amount1 = Decimal("100")
        amount2 = Decimal("200")
        expected_calls = [
            internal_to_address_call(
                credit=False, address="BALANCE_TRANSFER_REF1_CHARGED", amount=amount1
            ),
            internal_to_address_call(
                credit=False, address="BALANCE_TRANSFER_REF2_CHARGED", amount=amount2
            ),
            internal_to_address_call(credit=False, address=AVAILABLE, amount="700"),
        ]
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.balance_transfer(amount=amount1, ref="REF1"),
                self.balance_transfer(amount=amount2, ref="ref2"),
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {},
                    "transfer": {},
                    "balance_transfer": {},
                }
            ),
            transaction_code_to_type_map=dumps(
                {
                    "01": "purchase",
                    "00": "cash_advance",
                    "02": "transfer",
                    "03": "balance_transfer",
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {"REF1": "0.2", "ref2": "0.25"}}
            ),
        )

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_bt_succeeds_with_lower_case_reference(self):
        balances = init_balances()
        amount1 = Decimal("100")
        amount2 = Decimal("200")

        ref1 = "Mixed_Case_Reference_1"
        ref2 = "lower_case_reference"

        expected_calls = [
            internal_to_address_call(
                credit=False,
                address=f"BALANCE_TRANSFER_{ref1.upper()}_CHARGED",
                amount=amount1,
            ),
            internal_to_address_call(
                credit=False,
                address=f"BALANCE_TRANSFER_{ref2.upper()}_CHARGED",
                amount=amount2,
            ),
            internal_to_address_call(credit=False, address=AVAILABLE, amount="700"),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.balance_transfer(amount=amount1, ref=ref1),
                self.balance_transfer(amount=amount2, ref=ref2),
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types=dumps({"balance_transfer": {}}),
            annual_percentage_rate=dumps({}),
            base_interest_rates=dumps({}),
            transaction_code_to_type_map=dumps({"03": "balance_transfer"}),
            transaction_references=dumps({"balance_transfer": [ref1, ref2]}),
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {ref1: "0.2", ref2: "0.25"}}
            ),
            transaction_base_interest_rates=dumps(
                {"balance_transfer": {ref1: "0.2", ref2: "0.25"}}
            ),
        )

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_fully_extra_limit_external_fee_rebalancing(self):
        dispute_fee_amount = Decimal("100")
        credit_limit = Decimal("1000")
        balances = init_balances(
            # Equivalent to 1000 spend before the fee is charged
            balance_defs=[
                {"address": "DEFAULT", "net": "-1100"},
                {"address": "PURCHASE_CHARGED", "net": "-1000"},
            ]
        )

        expected_calls = [dispute_fee_rebalancing_call(amount=dispute_fee_amount)]
        unexpected_calls = [
            dispute_fee_rebalancing_call(amount=dispute_fee_amount, from_address="DEFAULT"),
        ]

        dispute_posting = self.dispute_fee(amount=Decimal(dispute_fee_amount))
        pib = self.mock_posting_instruction_batch(posting_instructions=[dispute_posting])

        mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, unexpected_calls)

    def test_fully_extra_limit_external_fee_gl_postings(self):
        dispute_fee_amount = Decimal("100")
        credit_limit = Decimal("1000")
        balances = init_balances(
            # Equivalent to 1000 spend before the fee is charged
            balance_defs=[
                {"address": "DEFAULT", "net": "1100"},
                {"address": "PURCHASE_CHARGED", "net": "1000"},
            ]
        )

        expected_calls = [
            charge_dispute_fee_loan_to_customer_call(amount=dispute_fee_amount),
        ]

        unexpected_calls = [charge_dispute_fee_off_bs_call(amount=ANY)]

        dispute_posting = self.dispute_fee(amount=Decimal(dispute_fee_amount))
        pib = self.mock_posting_instruction_batch(posting_instructions=[dispute_posting])

        mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, unexpected_calls)

    def test_external_fee_partially_covered_by_deposit_rebalancing(self):
        dispute_fee_amount = Decimal("100")
        credit_limit = Decimal("1000")
        balances = init_balances(
            # Equivalent to 60 deposit before the fee is charged
            balance_defs=[
                {"address": "DEFAULT", "net": "40"},
                {"address": "DEPOSIT", "net": "60"},
            ]
        )

        expected_calls = [dispute_fee_rebalancing_call(amount="40")]
        unexpected_calls = [
            dispute_fee_rebalancing_call(amount=ANY, from_address="DEFAULT"),
        ]

        dispute_posting = self.dispute_fee(
            amount=Decimal(dispute_fee_amount),
            client_transaction_id="a",
        )
        pib = self.mock_posting_instruction_batch(posting_instructions=[dispute_posting])

        mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_partially_extra_limit_external_fee_gl_postings(self):
        dispute_fee_amount = Decimal("100")
        credit_limit = Decimal("1000")
        balances = init_balances(
            # Equivalent to 975 spend before the fee is charged
            balance_defs=[
                {"address": "DEFAULT", "net": "1075"},
                {"address": "PURCHASE_CHARGED", "net": "975"},
            ]
        )

        expected_calls = [
            charge_dispute_fee_loan_to_customer_call(amount=dispute_fee_amount),
            charge_dispute_fee_off_bs_call(amount="25"),
        ]

        dispute_posting = self.dispute_fee(amount=Decimal(dispute_fee_amount))
        pib = self.mock_posting_instruction_batch(posting_instructions=[dispute_posting])

        mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_external_fee_fully_covered_by_deposit_rebalancing(self):
        dispute_fee_amount = Decimal("100")
        credit_limit = Decimal("1000")
        balances = init_balances(
            # Equivalent to 100 deposit before the fee is charged
            balance_defs=[
                {"address": "DEFAULT", "net": "0"},
                {"address": "DEPOSIT", "net": "100"},
            ]
        )

        unexpected_calls = [
            dispute_fee_rebalancing_call(amount=ANY),
            dispute_fee_rebalancing_call(amount=ANY, from_address="DEFAULT"),
        ]

        dispute_posting = self.dispute_fee(
            amount=Decimal(dispute_fee_amount),
            client_transaction_id="a",
        )
        pib = self.mock_posting_instruction_batch(posting_instructions=[dispute_posting])

        mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_external_fee_entirely_covered_by_deposit_gl_postings(self):
        dispute_fee_amount = "100"
        balances = init_balances(
            # Equivalent to 100 deposit before the fee is charged
            balance_defs=[
                {"address": "DEFAULT", "net": "0"},
                {"address": "DEPOSIT", "net": "100"},
            ]
        )

        dispute_fee_posting_id = "0"

        unexpected_calls = [
            charge_dispute_fee_loan_to_customer_call(posting_id=dispute_fee_posting_id),
            charge_dispute_fee_off_bs_call(posting_id=dispute_fee_posting_id),
        ]

        dispute_posting = self.dispute_fee(
            amount=Decimal(dispute_fee_amount),
            client_transaction_id="a",
            posting_id=dispute_fee_posting_id,
        )
        pib = self.mock_posting_instruction_batch(posting_instructions=[dispute_posting])

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_multiple_external_fees_rebalancing(self):
        dispute_fee_amount_1 = "100"
        dispute_fee_amount_2 = "33"

        balances = init_balances(
            # Equivalent to 0 spend/deposit before the fee is charged
            balance_defs=[{"address": "DEFAULT", "net": "133"}]
        )

        dispute_fee_posting_id_1 = "1"
        dispute_fee_posting_id_2 = "2"

        expected_calls = [
            dispute_fee_rebalancing_call(
                amount=dispute_fee_amount_1, posting_id=dispute_fee_posting_id_1
            ),
            dispute_fee_rebalancing_call(
                amount=dispute_fee_amount_2, posting_id=dispute_fee_posting_id_2
            ),
        ]
        unexpected_calls = [
            dispute_fee_rebalancing_call(
                amount=dispute_fee_amount_1,
                from_address="DEFAULT",
                posting_id=dispute_fee_posting_id_1,
            ),
            dispute_fee_rebalancing_call(
                amount=dispute_fee_amount_2,
                from_address="DEFAULT",
                posting_id=dispute_fee_posting_id_2,
            ),
        ]

        dispute_posting_1 = self.dispute_fee(
            amount=Decimal(dispute_fee_amount_1),
            client_transaction_id="a",
            posting_id=dispute_fee_posting_id_1,
        )
        dispute_posting_2 = self.dispute_fee(
            amount=Decimal(dispute_fee_amount_2),
            client_transaction_id="b",
            posting_id=dispute_fee_posting_id_2,
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[dispute_posting_1, dispute_posting_2]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_multiple_external_fees_internal_account_postings(self):
        dispute_fee_amount_1 = "100"
        dispute_fee_amount_2 = "33"

        balances = init_balances(
            # Equivalent to 0 spend/deposit before the fee is charged
            balance_defs=[{"address": "DEFAULT", "net": "133"}]
        )

        dispute_fee_posting_id_1 = "1"
        dispute_fee_posting_id_2 = "2"

        expected_calls = [
            charge_dispute_fee_loan_to_customer_call(
                amount=dispute_fee_amount_1, posting_id=dispute_fee_posting_id_1
            ),
            charge_dispute_fee_off_bs_call(
                amount=dispute_fee_amount_1, posting_id=dispute_fee_posting_id_1
            ),
            charge_dispute_fee_loan_to_customer_call(
                amount=dispute_fee_amount_2, posting_id=dispute_fee_posting_id_2
            ),
            charge_dispute_fee_off_bs_call(
                amount=dispute_fee_amount_2, posting_id=dispute_fee_posting_id_2
            ),
        ]

        dispute_posting_1 = self.dispute_fee(
            amount=Decimal(dispute_fee_amount_1),
            client_transaction_id="a",
            posting_id=dispute_fee_posting_id_1,
        )
        dispute_posting_2 = self.dispute_fee(
            amount=Decimal(dispute_fee_amount_2),
            client_transaction_id="b",
            posting_id=dispute_fee_posting_id_2,
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[dispute_posting_1, dispute_posting_2]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_multiple_external_fees_partially_covered_by_deposit_rebalancing(self):
        dispute_fee_amount_1 = "100"
        dispute_fee_amount_2 = "33"

        balances = init_balances(
            # Equivalent to 99 deposit before the fee is charged
            balance_defs=[
                {"address": "DEFAULT", "net": "34"},
                {"address": "DEPOSIT", "net": "99"},
            ]
        )

        dispute_fee_posting_id_1 = "1"
        dispute_fee_posting_id_2 = "2"

        expected_calls = [
            dispute_fee_rebalancing_call(amount="1", posting_id=dispute_fee_posting_id_1),
            dispute_fee_rebalancing_call(
                amount=dispute_fee_amount_2, posting_id=dispute_fee_posting_id_2
            ),
        ]
        unexpected_calls = [
            dispute_fee_rebalancing_call(
                amount=ANY, from_address="DEFAULT", posting_id=dispute_fee_posting_id_1
            ),
            dispute_fee_rebalancing_call(
                amount=ANY, from_address="DEFAULT", posting_id=dispute_fee_posting_id_2
            ),
        ]

        dispute_posting_1 = self.dispute_fee(
            amount=Decimal(dispute_fee_amount_1),
            client_transaction_id="a",
            posting_id=dispute_fee_posting_id_1,
        )
        dispute_posting_2 = self.dispute_fee(
            amount=Decimal(dispute_fee_amount_2),
            client_transaction_id="b",
            posting_id=dispute_fee_posting_id_2,
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[dispute_posting_1, dispute_posting_2]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_multiple_external_fees_partially_covered_by_deposit_gl_postings(self):
        dispute_fee_amount_1 = "100"
        dispute_fee_amount_2 = "33"

        balances = init_balances(
            # Equivalent to 99 deposit before the fee is charged
            balance_defs=[
                {"address": "DEFAULT", "net": "34"},
                {"address": "DEPOSIT", "net": "99"},
            ]
        )

        dispute_fee_posting_id_1 = "1"
        dispute_fee_posting_id_2 = "2"

        expected_calls = [
            charge_dispute_fee_loan_to_customer_call(
                amount="1", posting_id=dispute_fee_posting_id_1
            ),
            charge_dispute_fee_off_bs_call(amount="1", posting_id=dispute_fee_posting_id_1),
            charge_dispute_fee_loan_to_customer_call(
                amount=dispute_fee_amount_2, posting_id=dispute_fee_posting_id_2
            ),
            charge_dispute_fee_off_bs_call(
                amount=dispute_fee_amount_2, posting_id=dispute_fee_posting_id_2
            ),
        ]

        dispute_posting_1 = self.dispute_fee(
            amount=Decimal(dispute_fee_amount_1),
            client_transaction_id="a",
            posting_id=dispute_fee_posting_id_1,
        )
        dispute_posting_2 = self.dispute_fee(
            amount=Decimal(dispute_fee_amount_2),
            client_transaction_id="b",
            posting_id=dispute_fee_posting_id_2,
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[dispute_posting_1, dispute_posting_2]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_multiple_external_fees_fully_covered_by_deposit_rebalancing(self):
        dispute_fee_amount_1 = "100"
        dispute_fee_amount_2 = "33"

        balances = init_balances(
            # Equivalent to 133 deposit before the fee is charged
            balance_defs=[
                {"address": "DEFAULT", "net": "0"},
                {"address": "DEPOSIT", "net": "133"},
            ]
        )

        dispute_fee_posting_id_1 = "1"
        dispute_fee_posting_id_2 = "2"

        unexpected_calls = [
            dispute_fee_rebalancing_call(amount=ANY, posting_id=dispute_fee_posting_id_1),
            dispute_fee_rebalancing_call(amount=ANY, posting_id=dispute_fee_posting_id_2),
            dispute_fee_rebalancing_call(
                amount=ANY, from_address="DEFAULT", posting_id=dispute_fee_posting_id_1
            ),
            dispute_fee_rebalancing_call(
                amount=ANY, from_address="DEFAULT", posting_id=dispute_fee_posting_id_2
            ),
        ]

        dispute_posting_1 = self.dispute_fee(
            amount=Decimal(dispute_fee_amount_1),
            client_transaction_id="a",
            posting_id=dispute_fee_posting_id_1,
        )
        dispute_posting_2 = self.dispute_fee(
            amount=Decimal(dispute_fee_amount_2),
            client_transaction_id="b",
            posting_id=dispute_fee_posting_id_2,
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[dispute_posting_1, dispute_posting_2]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_multiple_external_fees_fully_covered_by_deposit_gl_postings(self):
        dispute_fee_amount_1 = "100"
        dispute_fee_amount_2 = "33"

        balances = init_balances(
            # Equivalent to 133 deposit before the fee is charged
            balance_defs=[
                {"address": "DEFAULT", "net": "0"},
                {"address": "DEPOSIT", "net": "133"},
            ]
        )

        posting_id_1 = "1"
        posting_id_2 = "2"

        expected_calls = [
            txn_specific_fee_other_liability_gl_call(
                amount="100", fee_type="DISPUTE_FEE", posting_id=posting_id_1
            ),
            txn_specific_fee_other_liability_gl_call(
                amount="33", fee_type="DISPUTE_FEE", posting_id=posting_id_2
            ),
        ]

        unexpected_calls = [
            charge_dispute_fee_loan_to_customer_call(amount=ANY, posting_id=posting_id_1),
            charge_dispute_fee_off_bs_call(amount=ANY, posting_id=posting_id_1),
            charge_dispute_fee_loan_to_customer_call(amount=ANY, posting_id=posting_id_2),
            charge_dispute_fee_off_bs_call(amount=ANY, posting_id=posting_id_2),
        ]

        dispute_posting_1 = self.dispute_fee(
            amount=Decimal(dispute_fee_amount_1),
            client_transaction_id="a",
            posting_id=posting_id_1,
        )
        dispute_posting_2 = self.dispute_fee(
            amount=Decimal(dispute_fee_amount_2),
            client_transaction_id="b",
            posting_id=posting_id_2,
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[dispute_posting_1, dispute_posting_2]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )


class PostPostingTxnTypeFeeTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_transaction_type_fees_flat_fee_applied_when_larger_than_percentage(self):
        balances = init_balances(balance_defs=[{"address": "DEFAULT", "net": "-10"}])
        posting_instructions = [self.cash_advance(amount="10")]

        expected_calls = [
            fee_rebalancing_call(amount="5", txn_type="cash_advance"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "5",
                    }
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=True
        )

    def test_transaction_type_fees_percentage_fee_applied_when_larger_than_flat(self):
        balances = init_balances(balance_defs=[{"address": "DEFAULT", "net": "150"}])
        posting_instructions = [self.cash_advance(amount="150")]

        expected_calls = [
            fee_rebalancing_call(amount="7.5", txn_type="cash_advance"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.05",
                        "flat_fee": "5",
                    }
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=True
        )

    def test_transaction_type_fees_fee_applied_when_flat_equals_percentage(self):
        balances = init_balances(balance_defs=[{"address": "DEFAULT", "net": "-150"}])
        posting_instructions = [self.cash_advance(amount="150")]

        expected_calls = [
            fee_rebalancing_call(amount="7.5", txn_type="cash_advance"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.05",
                        "flat_fee": "5",
                    }
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=True
        )

    def test_transaction_type_fees_triggers_internal_account_postings(self):
        balances = init_balances(balance_defs=[{"address": "DEFAULT", "net": "100"}])
        posting_instructions = [self.cash_advance(amount="100")]

        expected_calls = [
            txn_fee_loan_to_income_call(amount="5", txn_type="cash_advance"),
            charge_txn_type_fee_off_bs_call(amount="5", txn_type="cash_advance"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.05",
                        "flat_fee": "5",
                    }
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=True
        )

    def test_transaction_type_fees_partially_extra_limit_triggers_internal_account_postings(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "997.5"},
                {"address": "PURCHASE_BILLED", "net": "897.5"},
            ]
        )
        posting_instructions = [self.cash_advance(amount="100")]

        expected_calls = [
            txn_fee_loan_to_income_call(amount="5", txn_type="cash_advance"),
            charge_txn_type_fee_off_bs_call(amount="2.5", txn_type="cash_advance"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.05",
                        "flat_fee": "5",
                    }
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_transaction_type_fees_fully_extra_limit_triggers_internal_account_postings(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "1000"},
                {"address": "PURCHASE_BILLED", "net": "900"},
            ]
        )
        posting_instructions = [self.cash_advance(amount="100")]

        expected_calls = [
            txn_fee_loan_to_income_call(amount="5", txn_type="cash_advance"),
        ]

        unexpected_calls = [charge_txn_type_fee_off_bs_call(amount=ANY, txn_type="cash_advance")]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.05",
                        "flat_fee": "5",
                    }
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_transaction_type_fees_fee_applied_for_multiple_transactions_in_batch(self):
        balances = init_balances(balance_defs=[{"address": "DEFAULT", "net": "300"}])
        posting_instructions = [
            self.cash_advance(amount="100", posting_id="0"),
            self.cash_advance(amount="200", posting_id="1"),
        ]

        expected_calls = [
            fee_rebalancing_call(amount="5", txn_type="cash_advance", posting_id="0"),
            fee_rebalancing_call(amount="10", txn_type="cash_advance", posting_id="1"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.05",
                        "flat_fee": "5",
                    }
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=True
        )

    def test_transaction_type_fees_fee_not_applied_if_amount_is_zero(self):
        balances = init_balances(balance_defs=[{"address": "DEFAULT", "net": "300"}])
        posting_instructions = [
            self.cash_advance(amount="100"),
            self.cash_advance(amount="200"),
        ]

        unexpected_calls = [fee_rebalancing_call(amount=ANY, txn_type="cash_advance")]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0",
                        "flat_fee": "0",
                    }
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_transaction_type_fees_do_not_cause_deposit_balance_to_go_negative(self):
        balances = init_balances(balance_defs=[{"address": "DEPOSIT", "net": "101"}])

        posting_instructions = [self.cash_advance(amount="100")]
        # Can't use the all_charged_fee_calls helper due to the extra deposit balance check
        expected_calls = [
            fee_rebalancing_call("105", txn_type="cash_advance", from_address="DEFAULT"),
            fee_rebalancing_call("104", txn_type="cash_advance"),
            fee_rebalancing_call("-1", txn_type="cash_advance", from_address=DEPOSIT),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees='{"cash_advance": {"flat_fee": "105", "percentage_fee": "0.05"}}',
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_order=True)

    def test_transaction_type_fees_from_deposit_cause_internal_account_postings(self):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 101 deposit before postings
                {"address": "DEFAULT", "net": "-1"},
                {"address": "DEPOSIT", "net": "101"},
            ]
        )

        posting_instructions = [self.cash_advance(amount="100")]

        expected_calls = [
            txn_specific_fee_other_liability_gl_call(
                amount="1", txn_type="CASH_ADVANCE", fee_type="CASH_ADVANCE_FEE"
            ),
            txn_fee_loan_to_income_call(amount="104", txn_type="cash_advance"),
            charge_txn_type_fee_off_bs_call(amount="104", txn_type="cash_advance"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.05",
                        "flat_fee": "105",
                    }
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_txn_type_fee_charged_when_over_deposit_true_and_txn_gt_deposit(self):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 50 deposit before postings
                {"address": "DEFAULT", "net": "10"},
                {"address": "DEPOSIT", "net": "0"},
            ]
        )

        posting_instructions = [self.cash_advance(amount="10")]
        txn_type_fees = {
            "cash_advance": {
                "over_deposit_only": "True",
                "percentage_fee": "0.02",
                "flat_fee": "5",
            }
        }

        expected_calls = [
            fee_rebalancing_call(amount="5", txn_type="cash_advance"),
            fee_rebalancing_call(amount="5", txn_type="cash_advance", from_address="DEFAULT"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(txn_type_fees),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=False
        )

    def test_txn_type_fee_not_charged_when_over_deposit_true_and_sum_of_txns_lt_deposit(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 50 deposit before postings
                {"address": "DEFAULT", "net": "-10"},
                {"address": "DEPOSIT", "net": "50"},
            ]
        )

        posting_instructions = [
            self.cash_advance(amount="30"),
            self.cash_advance(amount="10"),
        ]
        txn_type_fees = {
            "cash_advance": {
                "over_deposit_only": "True",
                "percentage_fee": "0.5",
                "flat_fee": "10",
            }
        }

        unexpected_calls = [
            fee_rebalancing_call(ANY, txn_type="cash_advance", from_address="DEFAULT")
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(txn_type_fees),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_txn_type_fee_charged_when_over_deposit_false_and_sum_of_txns_lt_deposit(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 50 deposit before postings
                {"address": "DEFAULT", "net": "10"},
                {"address": "DEPOSIT", "net": "50"},
            ]
        )
        posting_instructions = [
            self.cash_advance(amount="30"),
            self.cash_advance(amount="10"),
        ]
        txn_type_fees = {
            "cash_advance": {
                "over_deposit_only": "False",
                "percentage_fee": "0.5",
                "flat_fee": "10",
            }
        }

        # $15 and $10 fee. First partially covered by deposit, second isn't
        expected_calls = [
            fee_rebalancing_call(amount="15", txn_type="cash_advance", from_address="DEFAULT"),
            fee_rebalancing_call(amount="5", txn_type="cash_advance"),
            fee_rebalancing_call(amount="-10", txn_type="cash_advance", from_address="DEPOSIT"),
            fee_rebalancing_call(amount="10", txn_type="cash_advance", from_address="DEFAULT"),
            fee_rebalancing_call(amount="10", txn_type="cash_advance"),
        ]

        unexpected_calls = [fee_rebalancing_call(amount="15", txn_type="cash_advance")]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(txn_type_fees),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_txn_type_fee_charged_if_over_deposit_true_and_sum_of_txns_gt_deposit(self):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 50 deposit before postings
                {"address": "DEFAULT", "net": "5"},
                {"address": "DEPOSIT", "net": "50"},
            ]
        )
        posting_instructions = [
            self.cash_advance(amount="30"),
            self.cash_advance(amount="25"),
        ]
        txn_type_fees = {
            "cash_advance": {
                "over_deposit_only": "True",
                "percentage_fee": "0.5",
                "flat_fee": "10",
            }
        }

        # First txn does not result in fees as 50 deposit covers 30 txn, but second does result in
        # fees as remaining 20 deposit does not cover 25 txn
        expected_calls = [
            fee_rebalancing_call("12.5", txn_type="cash_advance"),
            fee_rebalancing_call("12.5", txn_type="cash_advance", from_address="DEFAULT"),
        ]
        unexpected_calls = [
            fee_rebalancing_call("15", txn_type="cash_advance"),
            fee_rebalancing_call("15", txn_type="cash_advance", from_address="DEFAULT"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(txn_type_fees),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_txn_type_fee_charged_when_over_deposit_false_and_sum_of_txns_gt_deposit(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 50 deposit before postings
                {"address": "DEFAULT", "net": "5"},
                {"address": "DEPOSIT", "net": "50"},
            ]
        )
        posting_instructions = [
            self.cash_advance(amount="30"),
            self.cash_advance(amount="25"),
        ]
        txn_type_fees = {
            "cash_advance": {
                "over_deposit_only": "False",
                "percentage_fee": "0.5",
                "flat_fee": "10",
            }
        }

        expected_calls = [
            fee_rebalancing_call("15", txn_type="cash_advance"),
            fee_rebalancing_call("15", txn_type="cash_advance", from_address="DEFAULT"),
            fee_rebalancing_call("12.5", txn_type="cash_advance"),
            fee_rebalancing_call("12.5", txn_type="cash_advance", from_address="DEFAULT"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(txn_type_fees),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_no_txn_type_fee_charged_when_over_deposit_true_and_txn_eq_deposit(self):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 100 deposit before postings
                {"address": "DEFAULT", "net": "0"},
                {"address": "DEPOSIT", "net": "100"},
            ]
        )
        posting_instructions = [self.cash_advance(amount="100")]
        txn_type_fees = {
            "cash_advance": {
                "over_deposit_only": "True",
                "percentage_fee": "0.02",
                "flat_fee": "5",
            }
        }

        unexpected_calls = [
            fee_rebalancing_call(amount=ANY, txn_type="cash_advance", from_address=ANY)
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(txn_type_fees),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_no_txn_type_fee_charged_when_over_deposit_true_and_txn_lt_deposit(self):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 100 deposit before postings
                {"address": "DEFAULT", "net": "-10"},
                {"address": "DEPOSIT", "net": "100"},
            ]
        )
        posting_instructions = [self.cash_advance(amount="90")]
        txn_type_fees = {
            "cash_advance": {
                "over_deposit_only": "True",
                "percentage_fee": "0.02",
                "flat_fee": "5",
            }
        }
        unexpected_calls = [
            fee_rebalancing_call(amount=ANY, txn_type="cash_advance", from_address=ANY)
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees=dumps(txn_type_fees),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_txn_type_fee_charged_from_deposit_over_deposit_false_and_txn_plus_fee_lt_deposit(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 100 deposit before postings
                {"address": "DEFAULT", "net": "-10"},
                {"address": "DEPOSIT", "net": "100"},
            ]
        )
        posting_instructions = [self.cash_advance(amount="90")]
        txn_type_fees = {
            "cash_advance": {
                "over_deposit_only": "False",
                "percentage_fee": "0.02",
                "flat_fee": "5",
            }
        }
        expected_calls = [
            fee_rebalancing_call(amount=-5, txn_type="CASH_ADVANCE", from_address="DEPOSIT"),
            fee_rebalancing_call(amount=5, txn_type="CASH_ADVANCE", from_address="DEFAULT"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            credit_limit=30000,
            transaction_type_fees=dumps(txn_type_fees),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_transaction_level_creates_correct_address_for_all_valid_states(self):
        balances = init_balances()
        auth_amount = Decimal("10.00")

        ct_postings = [
            self.txn_with_ref_auth(
                amount=auth_amount, transaction_code="03", transaction_ref="ref2"
            )
        ]

        client_transaction = self.mock_client_transaction(
            postings=ct_postings,
            authorised=auth_amount,
            released=Decimal(0),
            settled=Decimal(0),
            unsettled=auth_amount,
        )

        posting_instructions = [
            self.balance_transfer(amount="150", ref="REF1"),
            self.txn_with_ref_auth(amount="15", transaction_code="03", transaction_ref="REF1"),
            self.txn_with_ref_settle(amount="10", transaction_code="03", transaction_ref="ref2"),
        ]

        expected_calls = [
            # 12.5 is the sum of flat and percentage fees
            fee_rebalancing_call(amount="12.5", txn_type="balance_transfer"),
            internal_to_address_call(
                credit=False, amount=150, address="BALANCE_TRANSFER_REF1_CHARGED"
            ),
            internal_to_address_call(credit=False, amount=15, address="BALANCE_TRANSFER_REF1_AUTH"),
            internal_to_address_call(
                credit=False, amount=10, address="BALANCE_TRANSFER_REF2_CHARGED"
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            client_transaction=client_transaction,
            transaction_type_fees='{"balance_transfer": {"over_deposit_only": "False", '
            '"combine": "True", "fee_cap": "0", '
            '"flat_fee": "5", "percentage_fee": "0.05"}}',
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "transfer": {},
                    "balance_transfer": {
                        "charge_interest_from_transaction_date": "True",
                        "transaction_references": "True",
                    },
                }
            ),
            transaction_code_to_type_map=dumps(
                {
                    "01": "purchase",
                    "00": "cash_advance",
                    "02": "transfer",
                    "03": "balance_transfer",
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            transaction_annual_percentage_rate=dumps({"REF1": "0.2", "ref2": "0.25"}),
            transaction_type_fees_internal_accounts_map=dumps(
                {
                    "balance_transfer": {
                        "loan": "balance_transfer_fee_loan_internal_account",
                        "income": "balance_transfer_fee_income_internal_account",
                    }
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_transaction_level_creates_correct_address(self):
        balances = init_balances()
        posting_instructions = [self.balance_transfer(amount="150", ref="REF1")]

        expected_calls = [
            # 17.5 is the sum of flat and percentage fees
            fee_rebalancing_call(amount="17.5", txn_type="balance_transfer"),
            internal_to_address_call(
                credit=False, amount=150, address="BALANCE_TRANSFER_REF1_CHARGED"
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_fees='{"balance_transfer": {"over_deposit_only": "False", '
            '"combine": "True", "flat_fee": "10", "percentage_fee": "0.05"}}',
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "transfer": {},
                    "balance_transfer": {
                        "charge_interest_from_transaction_date": "True",
                        "transaction_references": "True",
                    },
                }
            ),
            transaction_code_to_type_map=dumps(
                {
                    "01": "purchase",
                    "00": "cash_advance",
                    "02": "transfer",
                    "03": "balance_transfer",
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "REF2"]}),
            transaction_annual_percentage_rate=dumps({"REF1": "0.2", "REF2": "0.25"}),
            transaction_type_fees_internal_accounts_map=dumps(
                {
                    "balance_transfer": {
                        "loan": "balance_transfer_fee_loan_internal_account",
                        "income": "balance_transfer_fee_income_internal_account",
                    }
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_fee_charged_for_transaction_level_flat_greater(self):
        transaction_type_fees = dumps(
            {
                "balance_transfer": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.02",
                    "flat_fee": "5",
                }
            }
        )

        balances = init_balances(
            dt=offset_datetime(2019, 2, 25, 0, 0, 1),
            balance_defs=[{"address": "available_balance", "net": "2000"}],
        )

        amount = Decimal("100")

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.balance_transfer(amount=amount, ref="REF1")]
        )

        expected_calls = [fee_rebalancing_call(amount="5", txn_type="balance_transfer")]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {},
                    "transfer": {},
                    "balance_transfer": {},
                }
            ),
            transaction_code_to_type_map=dumps(
                {
                    "01": "purchase",
                    "00": "cash_advance",
                    "02": "transfer",
                    "03": "balance_transfer",
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "0.2"}}),
            transaction_type_fees=transaction_type_fees,
            transaction_type_fees_internal_accounts_map=dumps(
                {
                    "balance_transfer": {
                        "loan": "balance_transfer_fee_loan_internal_account",
                        "income": "balance_transfer_fee_income_internal_account",
                    }
                }
            ),
        )

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_fee_charged_for_transaction_level_perc_greater(self):
        transaction_type_fees = dumps(
            {
                "balance_transfer": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.025",
                    "flat_fee": "5",
                    "combine": "False",
                }
            }
        )

        balances = init_balances(
            dt=offset_datetime(2019, 2, 25, 0, 0, 1),
            balance_defs=[{"address": "available_balance", "net": "2000"}],
        )

        amount = Decimal("201")

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.balance_transfer(amount=amount, ref="REF1")]
        )

        expected_calls = [fee_rebalancing_call(amount="5.03", txn_type="balance_transfer")]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {},
                    "transfer": {},
                    "balance_transfer": {},
                }
            ),
            transaction_code_to_type_map=dumps(
                {
                    "01": "purchase",
                    "00": "cash_advance",
                    "02": "transfer",
                    "03": "balance_transfer",
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "0.2"}}),
            transaction_type_fees=transaction_type_fees,
            transaction_type_fees_internal_accounts_map=dumps(
                {
                    "balance_transfer": {
                        "loan": "balance_transfer_fee_loan_internal_account",
                        "income": "balance_transfer_fee_income_internal_account",
                    }
                }
            ),
        )

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_combined_fee_capped_for_balance_transfer(self):
        transaction_type_fees = dumps(
            {
                "balance_transfer": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.03",
                    "flat_fee": "20",
                    "combine": "True",
                    "fee_cap": "75",
                }
            }
        )

        balances = init_balances(
            dt=offset_datetime(2019, 2, 25, 0, 0, 1),
            balance_defs=[{"address": "available_balance", "net": "3000"}],
        )

        amount = Decimal("2000")

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.balance_transfer(amount=amount, ref="REF1")]
        )

        expected_calls = [fee_rebalancing_call(amount="75", txn_type="balance_transfer")]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {},
                    "transfer": {},
                    "balance_transfer": {},
                }
            ),
            transaction_code_to_type_map=dumps(
                {
                    "01": "purchase",
                    "00": "cash_advance",
                    "02": "transfer",
                    "03": "balance_transfer",
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "0.2"}}),
            transaction_type_fees=transaction_type_fees,
            transaction_type_fees_internal_accounts_map=dumps(
                {
                    "balance_transfer": {
                        "loan": "balance_transfer_fee_loan_internal_account",
                        "income": "balance_transfer_fee_income_internal_account",
                    }
                }
            ),
        )

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)


class PostPostingRepaymentRebalancingTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_repayment_distributed_to_only_overdue_bucket(self):
        repayment_amount = "90"
        balances = init_balances(
            balance_defs=[
                # Equivalent to 200 purchase + fees before repayment
                {"address": "DEFAULT", "net": "110"},
                {"address": "overdue_1", "net": "100"},
                {"address": "purchase_unpaid", "net": "100"},
                {"address": "cash_advance_fees_unpaid", "net": "100"},
            ]
        )
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.repay(amount=repayment_amount)]
        )

        expected_calls = [
            make_internal_transfer_instructions_call(
                amount="90",
                from_account_address=INTERNAL,
                to_account_address="OVERDUE_1",
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_order=True)

    def test_repayment_distributed_to_only_overdue_bucket_and_capped_to_bucket_amount(
        self,
    ):
        repayment_amount = "150"
        balances = init_balances(
            balance_defs=[
                # Equivalent to 200 purchase + fees before repayment
                {"address": "DEFAULT", "net": "50"},
                {"address": "overdue_1", "net": "100"},
                {"address": "purchase_unpaid", "net": "100"},
                {"address": "cash_advance_fees_unpaid", "net": "100"},
            ]
        )
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.repay(amount=repayment_amount)]
        )

        expected_calls = [
            make_internal_transfer_instructions_call(
                amount="100",
                from_account_address=INTERNAL,
                to_account_address="OVERDUE_1",
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_order=True)

    def test_repayment_with_empty_overdue_buckets_does_not_result_in_postings_to_overdue(
        self,
    ):
        repayment_amount = "90"
        balances = init_balances(
            balance_defs=[
                # Equivalent to 200 purchase + fees before repayment
                {"address": "DEFAULT", "net": "110"},
                {"address": "purchase_unpaid", "net": "100"},
                {"address": "cash_advance_fees_unpaid", "net": "100"},
            ]
        )
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.repay(amount=repayment_amount)]
        )
        unexpected_calls = [
            make_internal_transfer_instructions_call(
                amount=ANY,
                from_account_address=INTERNAL,
                to_account_address="OVERDUE_1",
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault,
            unexpected_calls=unexpected_calls,
        )

    def test_repayment_distributed_to_oldest_overdue_bucket_if_lte_oldest_overdue_amount(
        self,
    ):
        repayment_amount = "100"
        balances = init_balances(
            balance_defs=[
                # Equivalent to 200 purchase + fees before repayment
                {"address": "DEFAULT", "net": "100"},
                {"address": "overdue_1", "net": "100"},
                {"address": "overdue_2", "net": "100"},
                {"address": "purchase_unpaid", "net": "100"},
                {"address": "cash_advance_fees_unpaid", "net": "100"},
            ]
        )
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.repay(amount=repayment_amount)]
        )

        expected_calls = [
            make_internal_transfer_instructions_call(
                amount="100",
                from_account_address=INTERNAL,
                to_account_address="OVERDUE_2",
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_order=True)

    def test_repayment_distributed_to_oldest_overdue_buckets_if_gt_oldest_overdue_amount(
        self,
    ):
        repayment_amount = "175"
        balances = init_balances(
            balance_defs=[
                # Equivalent to 300 purchase + fees before repayment
                {"address": "DEFAULT", "net": "125"},
                {"address": "overdue_1", "net": "100"},
                {"address": "overdue_2", "net": "100"},
                {"address": "overdue_3", "net": "100"},
                {"address": "purchase_unpaid", "net": "100"},
                {"address": "cash_advance_fees_unpaid", "net": "200"},
            ]
        )
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.repay(amount=repayment_amount)]
        )

        expected_calls = [
            make_internal_transfer_instructions_call(
                amount="100",
                from_account_address=INTERNAL,
                to_account_address="OVERDUE_3",
            ),
            make_internal_transfer_instructions_call(
                amount="75",
                from_account_address=INTERNAL,
                to_account_address="OVERDUE_2",
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_order=True)

    def test_repayment_updates_total_repayments_balance(self):
        repayment_amount = "150"
        balances = init_balances(
            balance_defs=[
                # Equivalent to 200 purchase + fees before repayment
                {"address": "DEFAULT", "net": "50"},
                {"address": "overdue_1", "net": "100"},
                {"address": "purchase_unpaid", "net": "100"},
                {"address": "cash_advance_fees_unpaid", "net": "100"},
            ]
        )
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.repay(amount=repayment_amount)]
        )

        expected_calls = [
            make_internal_transfer_instructions_call(
                amount="150",
                from_account_address=TOTAL_REPAYMENTS_LAST_STATEMENT,
                to_account_address=INTERNAL,
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_order=True)

    def test_partial_repayment_to_deposit_counted_in_total_repayments_balance(self):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 200 purchase + fees before repayment
                {"address": "DEFAULT", "net": "-50"},
                {"address": "overdue_1", "net": "100"},
                {"address": "purchase_unpaid", "net": "100"},
                {"address": "cash_advance_fees_unpaid", "net": "100"},
            ]
        )

        repayment_amount = "250"

        expected_calls = [
            make_internal_transfer_instructions_call(
                amount=repayment_amount,
                from_account_address=TOTAL_REPAYMENTS_LAST_STATEMENT,
                to_account_address=INTERNAL,
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.repay(amount=repayment_amount)]
        )

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_order=True)

    def test_full_repayment_to_deposit_counted_in_total_repayments_balance(self):
        balances = init_balances()
        repayment_amount = "200"

        expected_calls = [
            make_internal_transfer_instructions_call(
                amount=repayment_amount,
                from_account_address=TOTAL_REPAYMENTS_LAST_STATEMENT,
                to_account_address=INTERNAL,
            ),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.repay(amount=repayment_amount)]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_over_repaying_credits_deposit_balance_with_excess_repayment(self):
        balances = init_balances(
            balance_defs=[
                {"address": "available_balance", "net": "5000"},
                {"address": "purchase_charged", "net": "100"},
                {"address": "outstanding_balance", "net": "100"},
                {"address": "full_outstanding_balance", "net": "100"},
            ]
        )
        posting_instructions = [self.repay(amount="200")]

        expected_calls = [
            internal_to_address_call(credit=False, amount=100, address=DEPOSIT),
            instruct_posting_batch_call(
                effective_date=DEFAULT_DATE,
                client_batch_id=f"POST_POSTING-{HOOK_EXECUTION_ID}",
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_order=False)

    def test_repayment_hierarchy_explicitly_followed(self):
        """
        Current Hierarchy:

        1. Unpaid interest (Following APR hierarchy, reverse-alphabetical order where APR equal)
        2. Billed interest (Following APR hierarchy, reverse-alphabetical order where APR equal)
        3. Unpaid fees (In alphabetical order)
        4. Billed fees (In alphabetical order)
        5. For each txn type following APR hierarchy, reverse-alphabetical order where APR equal:
        5a. Unpaid principal
        5b. Billed principal
        6. Charged principal (Following APR hierarchy, reverse-alphabetical order where APR equal)
        7. Charged interest (Following APR hierarchy, reverse-alphabetical order where APR equal)
        8. Charged but not billed fees (In alphabetical order)
        """

        balances = init_balances(
            balance_defs=[
                {"address": "purchase_charged", "net": "10"},
                {"address": "purchase_billed", "net": "11"},
                {"address": "purchase_unpaid", "net": "12"},
                {"address": "purchase_interest_charged", "net": "13"},
                {"address": "purchase_interest_billed", "net": "14"},
                {"address": "purchase_interest_unpaid", "net": "15"},
                {"address": "cash_advance_charged", "net": "16"},
                {"address": "cash_advance_billed", "net": "17"},
                {"address": "cash_advance_unpaid", "net": "18"},
                {"address": "cash_advance_interest_charged", "net": "19"},
                {"address": "cash_advance_interest_billed", "net": "20"},
                {"address": "cash_advance_interest_unpaid", "net": "21"},
                {"address": "cash_advance_fees_charged", "net": "22"},
                {"address": "overlimit_fees_charged", "net": "23"},
                {"address": "cash_advance_fees_billed", "net": "24"},
                {"address": "purchase_fees_billed", "net": "25"},
                {"address": "late_repayment_fees_billed", "net": "26"},
                {"address": "annual_fees_unpaid", "net": "27"},
                {"address": "overlimit_fees_unpaid", "net": "28"},
                {"address": "balance_transfer_ref1_billed", "net": "29"},
                {"address": "balance_transfer_ref2_billed", "net": "30"},
                {"address": "overdue_1", "net": "60"},
                {"address": "overdue_2", "net": "30"},
            ]
        )
        pib = self.mock_posting_instruction_batch(posting_instructions=[self.repay(amount="430")])

        expected_calls = [
            repayment_rebalancing_call(
                amount="21", to_address="CASH_ADVANCE_INTEREST_UNPAID", repay_count=0
            ),
            repayment_rebalancing_call(
                amount="15", to_address="PURCHASE_INTEREST_UNPAID", repay_count=1
            ),
            repayment_rebalancing_call(
                amount="20", to_address="CASH_ADVANCE_INTEREST_BILLED", repay_count=2
            ),
            repayment_rebalancing_call(
                amount="14", to_address="PURCHASE_INTEREST_BILLED", repay_count=3
            ),
            repayment_rebalancing_call(amount="27", to_address="ANNUAL_FEES_UNPAID", repay_count=4),
            repayment_rebalancing_call(
                amount="28", to_address="OVERLIMIT_FEES_UNPAID", repay_count=5
            ),
            repayment_rebalancing_call(
                amount="24", to_address="CASH_ADVANCE_FEES_BILLED", repay_count=6
            ),
            repayment_rebalancing_call(
                amount="26", to_address="LATE_REPAYMENT_FEES_BILLED", repay_count=7
            ),
            repayment_rebalancing_call(
                amount="25", to_address="PURCHASE_FEES_BILLED", repay_count=8
            ),
            repayment_rebalancing_call(
                amount="18", to_address="CASH_ADVANCE_UNPAID", repay_count=9
            ),
            repayment_rebalancing_call(
                amount="17", to_address="CASH_ADVANCE_BILLED", repay_count=10
            ),
            repayment_rebalancing_call(amount="12", to_address="PURCHASE_UNPAID", repay_count=11),
            repayment_rebalancing_call(amount="11", to_address="PURCHASE_BILLED", repay_count=12),
            repayment_rebalancing_call(
                amount="30", to_address="BALANCE_TRANSFER_REF2_BILLED", repay_count=13
            ),
            repayment_rebalancing_call(
                amount="29", to_address="BALANCE_TRANSFER_REF1_BILLED", repay_count=14
            ),
            repayment_rebalancing_call(
                amount="16", to_address="CASH_ADVANCE_CHARGED", repay_count=15
            ),
            repayment_rebalancing_call(amount="10", to_address="PURCHASE_CHARGED", repay_count=16),
            repayment_rebalancing_call(
                amount="19", to_address="CASH_ADVANCE_INTEREST_CHARGED", repay_count=17
            ),
            repayment_rebalancing_call(
                amount="13", to_address="PURCHASE_INTEREST_CHARGED", repay_count=18
            ),
            repayment_rebalancing_call(
                amount="22", to_address="CASH_ADVANCE_FEES_CHARGED", repay_count=19
            ),
            repayment_rebalancing_call(
                amount="23", to_address="OVERLIMIT_FEES_CHARGED", repay_count=20
            ),
            make_internal_transfer_instructions_call(
                amount="10",
                from_account_address="DEPOSIT",
                to_account_address="INTERNAL",
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types='{"cash_advance": {}, "purchase": {}, '
            '"balance_transfer": {"transaction_references": "True"}}',
            transaction_code_to_type_map=dumps(
                {
                    "01": "purchase",
                    "00": "cash_advance",
                    "02": "transfer",
                    "03": "balance_transfer",
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "REF2"]}),
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {"REF1": "0.02", "REF2": "0.03"}}
            ),
            transaction_type_fees_internal_accounts_map=dumps(
                {
                    "cash_advance": {
                        "loan": "cash_advance_fee_loan_internal_account",
                        "income": "cash_advance_fee_income_internal_account",
                    },
                    "purchase": {
                        "loan": "purchase_fee_loan_internal_account",
                        "income": "purchase_fee_income_internal_account",
                    },
                    "balance_transfer": {
                        "loan": "balance_transfer_fee_loan_internal_account",
                        "income": "balance_transfer_fee_income_internal_account",
                    },
                }
            ),
        )

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_order=True)

    def test_ordering_of_transaction_types_when_apr_equal_is_reverse_alphabetical(self):
        balances = init_balances(
            balance_defs=[
                {"address": "z_charged", "net": "10"},
                {"address": "a_charged", "net": "11"},
                {"address": "b_charged", "net": "12"},
                {"address": "c_charged", "net": "13"},
                {"address": "d_charged", "net": "14"},
                {"address": "e_charged", "net": "15"},
            ]
        )

        # Note transaction type 'c' is a higher rate
        repayment_hierarchy = '{"z": "1", "a": "1", "b": "1", "c": "2", "d": "1", "e": "1"}'
        rates = '{"z": "0.01", "a": "0.01", "b": "0.01", "c": "0.02", "d": "0.01", "e": "0.01"}'

        pib = self.mock_posting_instruction_batch(posting_instructions=[self.repay(amount="75")])

        expected_calls = [
            make_internal_transfer_instructions_call(
                amount="13",
                from_account_address=INTERNAL,
                to_account_address="C_CHARGED",
            ),
            make_internal_transfer_instructions_call(
                amount="10",
                from_account_address=INTERNAL,
                to_account_address="Z_CHARGED",
            ),
            make_internal_transfer_instructions_call(
                amount="15",
                from_account_address=INTERNAL,
                to_account_address="E_CHARGED",
            ),
            make_internal_transfer_instructions_call(
                amount="14",
                from_account_address=INTERNAL,
                to_account_address="D_CHARGED",
            ),
            make_internal_transfer_instructions_call(
                amount="12",
                from_account_address=INTERNAL,
                to_account_address="B_CHARGED",
            ),
            make_internal_transfer_instructions_call(
                amount="11",
                from_account_address=INTERNAL,
                to_account_address="A_CHARGED",
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types='{"z": {}, "a": {}, "b": {}, "c": {}, "d": {}, "e": {}}',
            transaction_type_internal_accounts_map=dumps(
                {
                    "z": "z_internal_account",
                    "a": "a_internal_account",
                    "b": "b_internal_account",
                    "c": "c_internal_account",
                    "d": "d_internal_account",
                    "e": "e_internal_account",
                }
            ),
            annual_percentage_rate=repayment_hierarchy,
            base_interest_rates=rates,
            minimum_percentage_due=rates,
            transaction_code_to_type_map='{"01": "z", "00":"a", '
            '"02": "b", "03": "c", '
            '"04": "d", "05": "e"}',
        )

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_order=True)

    def test_repaying_principal_causes_internal_account_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "balance_transfer_ref1_charged", "net": "50"},
                {"address": "balance_transfer_ref2_charged", "net": "100"},
                {"address": "purchase_charged", "net": "200"},
                {"address": "cash_advance_charged", "net": "300"},
            ]
        )
        repayment_amount = Decimal("650")

        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [
            repay_principal_revocable_commitment_call(
                amount="300", repay_count=1, txn_type="cash_advance"
            ),
            repay_principal_loan_gl_call(amount="300", repay_count=1, txn_type="cash_advance"),
            repay_principal_revocable_commitment_call(
                amount="200", repay_count=3, txn_type="purchase"
            ),
            repay_principal_loan_gl_call(amount="200", repay_count=3, txn_type="purchase"),
            repay_principal_revocable_commitment_call(
                amount="100", repay_count=0, txn_type="balance_transfer"
            ),
            repay_principal_loan_gl_call(amount="100", repay_count=0, txn_type="balance_transfer"),
            repay_principal_revocable_commitment_call(
                amount="50", repay_count=2, txn_type="balance_transfer"
            ),
            repay_principal_loan_gl_call(amount="50", repay_count=2, txn_type="balance_transfer"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types='{"cash_advance": {}, "purchase": {}, '
            '"balance_transfer": {"transaction_references": "True"}}',
            transaction_code_to_type_map=dumps(
                {
                    "01": "purchase",
                    "00": "cash_advance",
                    "02": "transfer",
                    "03": "balance_transfer",
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "REF2"]}),
            annual_percentage_rate=dumps({"cash_advance": "4", "purchase": "1", "transfer": "2"}),
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {"REF1": "3", "REF2": "5"}}
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_repaying_extra_limit_principal_causes_internal_account_postings(self):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 1200 charged before repayment
                {"address": "DEFAULT", "net": "700"},
                {"address": "dispute_fees_charged", "net": "300"},
                {"address": "cash_advance_fees_charged", "net": "400"},
                {"address": "purchase_charged", "net": "200"},
                {"address": "cash_advance_charged", "net": "300"},
            ]
        )
        repayment_amount = Decimal("500")

        expected_calls = [
            repay_principal_revocable_commitment_call(
                amount="100", repay_count=0, txn_type="cash_advance"
            ),
            repay_principal_loan_gl_call(amount="300", repay_count=0, txn_type="cash_advance"),
            repay_principal_revocable_commitment_call(
                amount="200", repay_count=1, txn_type="purchase"
            ),
            repay_principal_loan_gl_call(amount="200", repay_count=1, txn_type="purchase"),
        ]

        mock_vault = self.create_mock(balance_ts=balances, denomination=DEFAULT_DENOM)

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.repay(repayment_amount)]
        )
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_repaying_to_deposit_only_gl_postings(self):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 0 charged before repayment
                {"address": "DEFAULT", "net": "500"},
            ]
        )
        repayment_amount = Decimal("500")

        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [repay_other_liability_gl_call(repayment_amount)]

        mock_vault = self.create_mock(balance_ts=balances, denomination=DEFAULT_DENOM)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_repaying_to_deposit_and_other_address_causes_internal_account_postings(
        self,
    ):
        outstanding_amount = Decimal("200")
        repayment_amount = Decimal("500")
        balances = init_balances(
            balance_defs=[
                # Equivalent to 200 charged before repayment
                {"address": "DEFAULT", "net": "300"},
                {"address": "purchase_charged", "net": outstanding_amount},
            ]
        )

        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [
            repay_other_liability_gl_call(repayment_amount - outstanding_amount),
            repay_principal_revocable_commitment_call(
                amount=outstanding_amount, repay_count=0, txn_type="purchase"
            ),
            repay_principal_loan_gl_call(
                amount=outstanding_amount, repay_count=0, txn_type="purchase"
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances, denomination=DEFAULT_DENOM)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_multiple_repayment_to_deposit_and_other_address_causes_internal_account_postings(
        self,
    ):
        outstanding_amount = Decimal("200")
        repayment_amount_1 = Decimal("500")
        repayment_amount_2 = Decimal("200")
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "-500"},
                {"address": "purchase_charged", "net": outstanding_amount},
            ]
        )
        posting_instructions = [
            self.repay(repayment_amount_1, posting_id="0"),
            self.repay(repayment_amount_2, posting_id="1"),
        ]

        expected_calls = [
            repay_principal_revocable_commitment_call(
                amount=outstanding_amount,
                repay_count=0,
                txn_type="purchase",
                posting_id="0",
            ),
            repay_principal_loan_gl_call(
                amount=outstanding_amount,
                repay_count=0,
                txn_type="purchase",
                posting_id="0",
            ),
            repay_other_liability_gl_call(repayment_amount_1 - outstanding_amount, posting_id="0"),
            repay_other_liability_gl_call(repayment_amount_2, posting_id="1"),
        ]

        mock_vault = self.create_mock(balance_ts=balances, denomination=DEFAULT_DENOM)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_repaying_generic_fees_causes_internal_account_postings(self):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 600 in fees before repayment
                {"address": "DEFAULT", "net": "200"},
                {"address": "annual_fees_billed", "net": "300"},
                {"address": "overlimit_fees_unpaid", "net": "300"},
            ]
        )
        repayment_amount = Decimal("400")

        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [
            repay_charged_fee_customer_to_loan_call(
                amount="300", fee_type="OVERLIMIT_FEE", repay_count=0
            ),
            repay_charged_fee_off_bs_call(amount="300", fee_type="OVERLIMIT_FEE", repay_count=0),
            repay_charged_fee_customer_to_loan_call(
                amount="100", fee_type="ANNUAL_FEE", repay_count=1
            ),
            repay_charged_fee_off_bs_call(amount="100", fee_type="ANNUAL_FEE", repay_count=1),
        ]

        mock_vault = self.create_mock(balance_ts=balances, denomination=DEFAULT_DENOM)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_repaying_extra_limit_generic_fees_causes_internal_account_postings(self):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 1100 in fees/purchase before repayment
                {"address": "DEFAULT", "net": "700"},
                {"address": "annual_fees_billed", "net": "300"},
                {"address": "overlimit_fees_unpaid", "net": "300"},
                {"address": "purchase_charged", "net": "500"},
            ]
        )
        repayment_amount = Decimal("400")

        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [
            repay_charged_fee_customer_to_loan_call(
                amount="300", fee_type="OVERLIMIT_FEE", repay_count=0
            ),
            repay_charged_fee_off_bs_call(amount="200", fee_type="OVERLIMIT_FEE", repay_count=0),
            repay_charged_fee_customer_to_loan_call(
                amount="100", fee_type="ANNUAL_FEE", repay_count=1
            ),
            repay_charged_fee_off_bs_call(amount="100", fee_type="ANNUAL_FEE", repay_count=1),
        ]

        mock_vault = self.create_mock(balance_ts=balances, denomination=DEFAULT_DENOM)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_repaying_txn_type_fees_causes_internal_account_postings(self):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 300 in fees before repayment
                {"address": "DEFAULT", "net": "50"},
                {"address": "cash_advance_fees_charged", "net": "100"},
                {"address": "transfer_fees_charged", "net": "200"},
            ]
        )
        repayment_amount = Decimal("250")

        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [
            repay_charged_fee_customer_to_loan_call(
                amount="100", fee_type="CASH_ADVANCE_FEE", repay_count=0
            ),
            repay_charged_fee_off_bs_call(amount="100", fee_type="CASH_ADVANCE_FEE", repay_count=0),
            repay_charged_fee_customer_to_loan_call(
                amount="150", fee_type="TRANSFER_FEE", repay_count=1
            ),
            repay_charged_fee_off_bs_call(amount="150", fee_type="TRANSFER_FEE", repay_count=1),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            transaction_type_fees_internal_accounts_map=dumps(
                {
                    "transfer": {
                        "loan": "transfer_fee_loan_internal_account",
                        "income": "transfer_fee_income_internal_account",
                    },
                    "cash_advance": {
                        "loan": "cash_advance_fee_loan_internal_account",
                        "income": "cash_advance_fee_income_internal_account",
                    },
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_repaying_partially_extra_limit_txn_type_fees_causes_internal_account_postings(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 300 in fees before repayment
                {"address": "DEFAULT", "net": "800"},
                {"address": "cash_advance_fees_billed", "net": "100"},
                {"address": "transfer_fees_billed", "net": "200"},
                {"address": "purchase_charged", "net": "750"},
            ]
        )
        repayment_amount = Decimal("250")

        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [
            repay_charged_fee_customer_to_loan_call(
                amount="100", fee_type="CASH_ADVANCE_FEE", repay_count=0
            ),
            repay_charged_fee_off_bs_call(amount="50", fee_type="CASH_ADVANCE_FEE", repay_count=0),
            repay_charged_fee_customer_to_loan_call(
                amount="150", fee_type="TRANSFER_FEE", repay_count=1
            ),
            repay_charged_fee_off_bs_call(amount="150", fee_type="TRANSFER_FEE", repay_count=1),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            transaction_type_fees_internal_accounts_map=dumps(
                {
                    "cash_advance": {
                        "loan": "cash_advance_fee_loan_internal_account",
                        "income": "cash_advance_fee_income_internal_account",
                    },
                    "transfer": {
                        "loan": "transfer_fee_loan_internal_account",
                        "income": "transfer_fee_income_internal_account",
                    },
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_repaying_fully_extra_limit_txn_type_fees_causes_internal_account_postings(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                # Equivalent to 1100 in fees/purchase before repayment
                {"address": "DEFAULT", "net": "850"},
                {"address": "cash_advance_fees_billed", "net": "100"},
                {"address": "transfer_fees_billed", "net": "200"},
                {"address": "purchase_charged", "net": "800"},
            ]
        )
        repayment_amount = Decimal("250")

        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [
            repay_charged_fee_customer_to_loan_call(
                amount="100", fee_type="CASH_ADVANCE_FEE", repay_count=0
            ),
            repay_charged_fee_customer_to_loan_call(
                amount="150", fee_type="TRANSFER_FEE", repay_count=1
            ),
            repay_charged_fee_off_bs_call(amount="150", fee_type="TRANSFER_FEE", repay_count=1),
        ]

        unexpected_calls = [
            repay_charged_fee_off_bs_call(amount=ANY, fee_type="CASH_ADVANCE_FEE", repay_count=0),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            transaction_type_fees_internal_accounts_map=dumps(
                {
                    "cash_advance": {
                        "loan": "cash_advance_fee_loan_internal_account",
                        "income": "cash_advance_fee_income_internal_account",
                    },
                    "transfer": {
                        "loan": "transfer_fee_loan_internal_account",
                        "income": "transfer_fee_income_internal_account",
                    },
                }
            ),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_repaying_external_fees_causes_internal_account_postings(self):
        repayment_amount = Decimal("100")
        balances = init_balances(
            balance_defs=[
                # Equivalent to 100 in fees/purchase before repayment
                {"address": "DEFAULT", "net": "0"},
                {"address": "dispute_fees_billed", "net": "100"},
            ]
        )
        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [
            repay_charged_dispute_fee_customer_to_loan_gl_call(amount="100", repay_count=0),
            repay_charged_fee_off_bs_call(amount="100", fee_type="DISPUTE_FEE", repay_count=0),
        ]

        mock_vault = self.create_mock(balance_ts=balances, denomination=DEFAULT_DENOM)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_repaying_partially_extra_limit_external_fees_causes_internal_account_postings(
        self,
    ):
        repayment_amount = Decimal("100")
        balances = init_balances(
            balance_defs=[
                # Equivalent to 1050 in fees/purchase before repayment
                {"address": "DEFAULT", "net": "950"},
                {"address": "dispute_fees_billed", "net": "100"},
                {"address": "PURCHASE_CHARGED", "net": "950"},
            ]
        )

        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [
            repay_charged_dispute_fee_customer_to_loan_gl_call(amount="100", repay_count=0),
            repay_charged_fee_off_bs_call(amount="50", fee_type="DISPUTE_FEE", repay_count=0),
        ]

        mock_vault = self.create_mock(balance_ts=balances, denomination=DEFAULT_DENOM)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_repaying_fully_extra_limit_external_fees_causes_internal_account_postings(
        self,
    ):
        repayment_amount = Decimal("100")
        balances = init_balances(
            balance_defs=[
                # Equivalent to 1050 in fees/purchase before repayment
                {"address": "DEFAULT", "net": "1000"},
                {"address": "dispute_fees_billed", "net": "100"},
                {"address": "PURCHASE_CHARGED", "net": "1000"},
            ]
        )
        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [
            repay_charged_dispute_fee_customer_to_loan_gl_call(amount="100", repay_count=0),
        ]

        unexpected_calls = [
            repay_charged_fee_off_bs_call(amount=ANY, fee_type="DISPUTE_FEE", repay_count=0),
        ]

        mock_vault = self.create_mock(balance_ts=balances, denomination=DEFAULT_DENOM)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_repaying_charged_interest_causes_internal_account_postings(self):
        repayment_amount = Decimal("400")
        balances = init_balances(
            balance_defs=[
                # Equivalent to 1050 in interest before repayment
                {"address": "DEFAULT", "net": "100"},
                {"address": "purchase_interest_charged", "net": "200"},
                {"address": "cash_advance_interest_charged", "net": "300"},
                {"address": "transfer_interest_charged", "net": "0"},
            ]
        )

        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [
            repay_charged_interest_gl_call(amount="300", txn_type="cash_advance", repay_count=0),
            repay_charged_interest_gl_call(amount="100", txn_type="purchase", repay_count=1),
        ]
        unexpected_calls = [
            repay_charged_interest_gl_call(amount=ANY, txn_type="transfer", repay_count=ANY),
        ]

        mock_vault = self.create_mock(balance_ts=balances, denomination=DEFAULT_DENOM)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_repaying_billed_or_unpaid_interest_causes_internal_account_postings(self):
        repayment_amount = Decimal("525")
        balances = init_balances(
            balance_defs=[
                # Equivalent to 400 in interest before repayment
                {"address": "DEFAULT", "net": "0"},
                {"address": "purchase_interest_unpaid", "net": "0"},
                {"address": "cash_advance_interest_unpaid", "net": "300"},
                {"address": "transfer_interest_billed", "net": "100"},
                {"address": "cash_advance_fee_interest_billed", "net": "125"},
            ]
        )

        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [
            repay_billed_interest_customer_to_loan_call(
                amount="300", repay_count=0, txn_type="cash_advance"
            ),
            repay_billed_interest_customer_to_loan_call(
                amount="100", repay_count=1, txn_type="transfer"
            ),
            repay_billed_interest_customer_to_loan_call(
                amount="125", repay_count=2, txn_type="cash_advance_fee"
            ),
            repay_billed_interest_off_bs_call(amount="300", repay_count=0, txn_type="cash_advance"),
            repay_billed_interest_off_bs_call(amount="100", repay_count=1, txn_type="transfer"),
            repay_billed_interest_off_bs_call(
                amount="125", repay_count=2, txn_type="cash_advance_fee"
            ),
        ]
        unexpected_calls = [
            repay_billed_interest_customer_to_loan_call(amount=ANY, txn_type="purchase"),
            repay_billed_interest_off_bs_call(amount=ANY, txn_type="purchase"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            accrue_interest_on_unpaid_fees=True,
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_repaying_extra_limit_billed_or_unpaid_interest_causes_internal_account_postings(
        self,
    ):
        repayment_amount = Decimal("400")
        balances = init_balances(
            balance_defs=[
                # Equivalent to 1200 in purchase/interest before repayment
                {"address": "DEFAULT", "net": "800"},
                {"address": "PURCHASE_BILLED", "net": "800"},
                {"address": "purchase_interest_unpaid", "net": "0"},
                {"address": "cash_advance_interest_unpaid", "net": "300"},
                {"address": "transfer_interest_billed", "net": "100"},
            ]
        )

        posting_instructions = [self.repay(repayment_amount)]

        expected_calls = [
            repay_billed_interest_customer_to_loan_call(
                amount="300", repay_count=0, txn_type="cash_advance"
            ),
            repay_billed_interest_customer_to_loan_call(
                amount="100", repay_count=1, txn_type="transfer"
            ),
            repay_billed_interest_off_bs_call(amount="100", repay_count=0, txn_type="cash_advance"),
            repay_billed_interest_off_bs_call(amount="100", repay_count=1, txn_type="transfer"),
        ]
        unexpected_calls = [
            repay_billed_interest_customer_to_loan_call(amount=ANY, txn_type="purchase"),
            repay_billed_interest_off_bs_call(amount=ANY, txn_type="purchase"),
        ]

        mock_vault = self.create_mock(balance_ts=balances, denomination=DEFAULT_DENOM)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_outstanding_balances_adjusted_with_full_repayment_amount_even_when_overpaying(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                # Equivalent to spend of 100 before the batch was accepted
                {"address": "DEFAULT", "net": "100"},
                {"address": "purchase_charged", "net": "50"},
                {"address": "cash_advance_charged", "net": "50"},
                {"address": "outstanding_balance", "net": "100"},
                {"address": "full_outstanding_balance", "net": "100"},
            ]
        )

        posting_instructions = [self.repay(amount="200")]

        expected_calls = [
            internal_to_address_call(credit=True, amount=200, address=OUTSTANDING),
            internal_to_address_call(credit=True, amount=200, address=FULL_OUTSTANDING),
            instruct_posting_batch_call(
                effective_date=DEFAULT_DATE,
                client_batch_id=f"POST_POSTING-{HOOK_EXECUTION_ID}",
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_order=True)

    def test_repaying_charged_interest_updates_full_outstanding_and_not_outstanding(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                # DEFAULT was -400 before the batch was accepted due to purchase/interest
                {"address": "DEFAULT", "net": "0"},
                {"address": "purchase_interest_charged", "net": "100"},
                {"address": "purchase_charged", "net": "300"},
                {"address": "outstanding_balance", "net": "300"},
                {"address": "full_outstanding_balance", "net": "400"},
            ]
        )

        posting_instructions = [self.repay(amount="400")]

        expected_calls = [
            internal_to_address_call(credit=True, amount=300, address=OUTSTANDING),
            internal_to_address_call(credit=True, amount=400, address=FULL_OUTSTANDING),
            instruct_posting_batch_call(
                effective_date=DEFAULT_DATE,
                client_batch_id=f"POST_POSTING-{HOOK_EXECUTION_ID}",
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_outstanding_balances_adjusted_with_full_repayment_amount(self):
        balances = init_balances(
            balance_defs=[
                # DEFAULT was -300 before the batch was accepted due to purchase/interest
                {"address": "DEFAULT", "net": "100"},
                {"address": "purchase_charged", "net": "300"},
                {"address": "outstanding_balance", "net": "300"},
                {"address": "full_outstanding_balance", "net": "300"},
            ]
        )
        posting_instructions = [self.repay(amount="200")]

        expected_calls = [
            internal_to_address_call(credit=True, amount=200, address=OUTSTANDING),
            internal_to_address_call(credit=True, amount=200, address=FULL_OUTSTANDING),
            instruct_posting_batch_call(
                effective_date=DEFAULT_DATE,
                client_batch_id=f"POST_POSTING-{HOOK_EXECUTION_ID}",
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_order=True)

    def test_revolver_unset_if_repaying_full_outstanding_balance(self):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "0"},
                {"address": "overdue_1", "net": "300"},
                {"address": "purchase_unpaid", "net": "300"},
                {"address": "purchase_interest_charged", "net": "100"},
                {"address": "outstanding_balance", "net": "300"},
                {"address": "full_outstanding_balance", "net": "400"},
                {"address": "revolver", "net": "-1"},
            ]
        )
        posting_instructions = [self.repay(amount="400")]

        expected_calls = [unset_revolver_call()]

        mock_vault = self.create_mock(balance_ts=balances)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_revolver_unset_if_overpaying_full_outstanding_balance(self):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "-100"},
                {"address": "overdue_1", "net": "300"},
                {"address": "purchase_unpaid", "net": "300"},
                {"address": "purchase_interest_charged", "net": "100"},
                {"address": "outstanding_balance", "net": "300"},
                {"address": "full_outstanding_balance", "net": "400"},
                {"address": "revolver", "net": "-1"},
            ]
        )
        posting_instructions = [self.repay(amount="500")]
        expected_calls = [unset_revolver_call()]

        mock_vault = self.create_mock(balance_ts=balances)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_revolver_not_unset_if_only_repaying_outstanding_balance(self):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "100"},
                {"address": "overdue_1", "net": "300"},
                {"address": "purchase_unpaid", "net": "300"},
                {"address": "purchase_interest_charged", "net": "100"},
                {"address": "outstanding_balance", "net": "300"},
                {"address": "full_outstanding_balance", "net": "400"},
                {"address": "revolver", "net": "-1"},
            ]
        )
        pib = self.mock_posting_instruction_batch(posting_instructions=[self.repay(amount="300")])

        unexpected_calls = [unset_revolver_call()]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)


class AccrualTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_int_accrued_from_txn_day_on_spend_if_transactor_and_neg_outstanding_stmt_balance(
        self,
    ):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_unpaid", "net": "50"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "full_outstanding_balance", "net": "4000"},
                {"address": "outstanding_balance", "net": "4000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"

        expected_calls = [
            accrue_interest_call(
                amount="1.10",
                balance=2000,
                txn_type="CASH_ADVANCE",
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
            accrue_interest_call(
                amount="0.27",
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="PRE_SCOD",
            ),
            accrue_interest_call(
                amount="0.27",
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"purchase": {purchase_rate} , '
            f'"cash_advance": {cash_adv_rate}}}',
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "transfer": {}}),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_interest_accrued_on_spend_if_transactor_and_negative_outstanding_stmt_balance(
        self,
    ):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_unpaid", "net": "50"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "full_outstanding_balance", "net": "4000"},
                {"address": "outstanding_balance", "net": "4000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"

        expected_calls = [
            accrue_interest_call(
                amount="1.10",
                balance=2000,
                txn_type="CASH_ADVANCE",
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.55",
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"purchase": {purchase_rate} , '
            f'"cash_advance": {cash_adv_rate}}}',
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "transfer": {}}),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_interest_accrued_but_not_charged_does_not_update_aggregate_balances(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "full_outstanding_balance", "net": "4000"},
                {"address": "outstanding_balance", "net": "4000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"

        unexpected_calls = [
            make_internal_transfer_instructions_call(
                amount=ANY, from_account_address=AVAILABLE, to_account_address=INTERNAL
            ),
            make_internal_transfer_instructions_call(
                amount=ANY,
                from_account_address=OUTSTANDING,
                to_account_address=INTERNAL,
            ),
            make_internal_transfer_instructions_call(
                amount=ANY,
                from_account_address=FULL_OUTSTANDING,
                to_account_address=INTERNAL,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"purchase": {purchase_rate} , '
            f'"cash_advance": {cash_adv_rate}}}',
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "transfer": {}}),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_interest_charged_but_not_accrued_on_spend_if_revolver(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "revolver", "net": "-1"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"

        expected_calls = [
            charge_interest_call(amount="1.10", txn_type="CASH_ADVANCE"),
            charge_interest_call(amount="0.55", txn_type="PURCHASE"),
        ]
        unexpected_calls = [
            accrue_interest_call(
                amount="1.10",
                balance=2000,
                txn_type="CASH_ADVANCE",
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.55",
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]
        base_interest_rates = f'{{"purchase": {purchase_rate} , "cash_advance": {cash_adv_rate}}}'

        mock_vault = self.create_mock(balance_ts=balances, base_interest_rates=base_interest_rates)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_on_unpaid_fees_charged_but_not_accrued_on_spend_if_revolver(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "annual_fees_unpaid", "net": "300"},
                {"address": "revolver", "net": "-1"},
            ],
        )

        purchase_rate = "0.1"
        fees = "0.2"

        expected_calls = [
            charge_interest_call(amount="0.55", txn_type="PURCHASE"),
            charge_interest_call(amount="0.16", txn_type="ANNUAL_FEE"),
        ]
        unexpected_calls = [
            accrue_interest_call(
                amount="0.55",
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.16",
                balance=300,
                txn_type="ANNUAL_FEE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=dumps({"purchase": purchase_rate, "fees": fees}),
            accrue_interest_on_unpaid_fees=True,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_accrued_from_txn_day_does_not_consider_bank_charge_balances(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_unpaid", "net": "50"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "cash_advance_fees_charged", "net": "1000"},
                {"address": "cash_advance_interest_billed", "net": "1000"},
                {"address": "full_outstanding_balance", "net": "6000"},
                {"address": "outstanding_balance", "net": "6000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        expected_purchase_accrual = "0.55"
        expected_purchase_accrual_pre_scod = "0.27"
        expected_purchase_accrual_post_scod = "0.27"
        expected_cash_adv_accrual = "1.10"

        expected_calls = [
            accrue_interest_call(
                expected_cash_adv_accrual,
                balance=2000,
                txn_type="CASH_ADVANCE",
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
            accrue_interest_call(
                expected_purchase_accrual_pre_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="PRE_SCOD",
            ),
            accrue_interest_call(
                expected_purchase_accrual_post_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
        ]

        unexpected_calls = [
            accrue_interest_call(
                expected_purchase_accrual,
                balance=2050,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"purchase": {purchase_rate} , '
            f'"cash_advance": {cash_adv_rate}}}',
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "transfer": {}}),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_accrued_does_not_consider_bank_charge_balances(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_unpaid", "net": "50"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "cash_advance_fees_charged", "net": "1000"},
                {"address": "cash_advance_interest_billed", "net": "1000"},
                {"address": "full_outstanding_balance", "net": "6000"},
                {"address": "outstanding_balance", "net": "6000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        expected_purchase_accrual = "0.55"
        expected_cash_adv_accrual = "1.10"

        expected_calls = [
            accrue_interest_call(
                expected_cash_adv_accrual,
                balance=2000,
                txn_type="CASH_ADVANCE",
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                expected_purchase_accrual,
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        unexpected_calls = [
            accrue_interest_call(
                expected_purchase_accrual,
                balance=2050,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"purchase": {purchase_rate} , '
            f'"cash_advance": {cash_adv_rate}}}',
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "transfer": {}}),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_accrue_from_txn_day_and_charge_interest_on_unpaid_interest_when_enabled(
        self,
    ):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_unpaid", "net": "500"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "cash_advance_fees_charged", "net": "1000"},
                {"address": "cash_advance_interest_billed", "net": "1000"},
                {"address": "full_outstanding_balance", "net": "6000"},
                {"address": "outstanding_balance", "net": "6000"},
                {"address": "revolver", "net": "-1"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"

        # 0.55 without enabling interest on interest
        # 0.55 + 500 * 0.1 / 365 = 0.55 + ~ 0.13
        expected_purchase_charge = "0.68"
        expected_cash_adv_charge = "1.10"

        expected_calls = [
            charge_interest_call(expected_purchase_charge, txn_type="PURCHASE"),
            charge_interest_call(expected_cash_adv_charge, txn_type="CASH_ADVANCE"),
        ]

        unexpected_calls = [
            accrue_interest_call(
                "0.55",
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"purchase": {purchase_rate} , '
            f'"cash_advance": {cash_adv_rate}}}',
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "transfer": {}}),
            accrue_interest_on_unpaid_interest=True,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_accrue_interest_on_unpaid_interest_when_enabled(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_unpaid", "net": "500"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "cash_advance_fees_charged", "net": "1000"},
                {"address": "cash_advance_interest_billed", "net": "1000"},
                {"address": "full_outstanding_balance", "net": "6000"},
                {"address": "outstanding_balance", "net": "6000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"

        # 0.55 without enabling interest on interest
        # 0.55 + 500 * 0.1 / 365 = 0.55 + ~ 0.13
        expected_purchase_accrual = "0.68"
        expected_cash_adv_accrual = "1.10"

        expected_calls = [
            accrue_interest_call(
                expected_purchase_accrual,
                balance=2500,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                expected_cash_adv_accrual,
                balance=2000,
                txn_type="CASH_ADVANCE",
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
        ]

        unexpected_calls = [
            accrue_interest_call(
                "0.55",
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"purchase": {purchase_rate} , '
            f'"cash_advance": {cash_adv_rate}}}',
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "transfer": {}}),
            accrue_interest_on_unpaid_interest=True,
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_accrue_interest_from_txn_day_on_unpaid_fees_when_enabled(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_unpaid", "net": "500"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "purchase_fees_unpaid", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "cash_advance_fees_charged", "net": "1000"},
                {"address": "cash_advance_fees_unpaid", "net": "1000"},
                {"address": "cash_advance_interest_billed", "net": "1000"},
                {"address": "full_outstanding_balance", "net": "6000"},
                {"address": "outstanding_balance", "net": "6000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        fees_rate = "0.1"

        # 0.55 total across the 2 purchase accrual addresses without enabling interest on interest
        # 1000 * 0.1 / 365 = ~ 0.2739 * 2
        expected_purchase_accrual_pre_scod = "0.27"
        expected_purchase_accrual_post_scod = "0.27"
        expected_cash_adv_accrual = "1.10"
        expected_fees_accrual = "0.27"

        expected_calls = [
            accrue_interest_call(
                expected_purchase_accrual_pre_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="PRE_SCOD",
            ),
            accrue_interest_call(
                expected_purchase_accrual_post_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
            accrue_interest_call(
                expected_fees_accrual,
                balance=1000,
                txn_type="PURCHASE_FEE",
                daily_rate=Decimal(fees_rate) * 100 / 365,
            ),
            accrue_interest_call(
                expected_cash_adv_accrual,
                balance=2000,
                txn_type="CASH_ADVANCE",
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
            accrue_interest_call(
                expected_fees_accrual,
                balance=1000,
                txn_type="CASH_ADVANCE_FEE",
                daily_rate=Decimal(fees_rate) * 100 / 365,
            ),
        ]

        unexpected_calls = [
            accrue_interest_call(
                "0.68",
                balance=2500,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=dumps(
                {
                    "purchase": purchase_rate,
                    "cash_advance": cash_adv_rate,
                    "fees": fees_rate,
                }
            ),
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "transfer": {}}),
            accrue_interest_on_unpaid_fees=True,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_accrue_interest_on_unpaid_fees_when_enabled(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_unpaid", "net": "500"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "purchase_fees_unpaid", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "cash_advance_fees_charged", "net": "1000"},
                {"address": "cash_advance_fees_unpaid", "net": "1000"},
                {"address": "cash_advance_interest_billed", "net": "1000"},
                {"address": "full_outstanding_balance", "net": "6000"},
                {"address": "outstanding_balance", "net": "6000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        fees_rate = "0.1"

        # 0.55 without enabling interest on interest
        # 1000 * 0.1 / 365 = ~ 0.2739
        expected_purchase_accrual = "0.55"
        expected_cash_adv_accrual = "1.10"
        expected_fees_accrual = "0.27"

        expected_calls = [
            accrue_interest_call(
                expected_purchase_accrual,
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                expected_fees_accrual,
                balance=1000,
                txn_type="PURCHASE_FEE",
                daily_rate=Decimal(fees_rate) * 100 / 365,
            ),
            accrue_interest_call(
                expected_cash_adv_accrual,
                balance=2000,
                txn_type="CASH_ADVANCE",
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                expected_fees_accrual,
                balance=1000,
                txn_type="CASH_ADVANCE_FEE",
                daily_rate=Decimal(fees_rate) * 100 / 365,
            ),
        ]

        unexpected_calls = [
            accrue_interest_call(
                "0.68",
                balance=2500,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=dumps(
                {
                    "purchase": purchase_rate,
                    "cash_advance": cash_adv_rate,
                    "fees": fees_rate,
                }
            ),
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "transfer": {}}),
            accrue_interest_on_unpaid_fees=True,
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_accrue_interest_on_unpaid_fees_and_handle_address_within_address(
        self,
    ):
        """
        If we are accruing interest on fees for e.g. transfer txn_type in
        transfer_fee_interest_charged, make sure that interest isn't also accrued in
        the balance_transfer_fees_interest_charged address. This can happen when there's a name
        within another name scenario:
        "if transfer in balance_transfer:" will return true but it's 2 different addresses
        """
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[{"address": "transfer_fees_unpaid", "net": "1000"}],
        )

        expected_calls = [
            accrue_interest_call(ANY, balance=ANY, txn_type="TRANSFER_FEE", daily_rate=ANY)
        ]
        unexpected_calls = [
            accrue_interest_call(ANY, balance=ANY, txn_type="BALANCE_TRANSFER_FEE", daily_rate=ANY),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=dumps({"fees": "0.1"}),
            transaction_types=dumps({"transfer": {}, "balance_transfer": {}}),
            accrue_interest_on_unpaid_fees=True,
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_no_interest_accrue_interest_from_txn_day_on_unpaid_fees_when_disabled(
        self,
    ):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_unpaid", "net": "500"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "purchase_fees_unpaid", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "cash_advance_fees_charged", "net": "1000"},
                {"address": "cash_advance_fees_unpaid", "net": "1000"},
                {"address": "cash_advance_interest_billed", "net": "1000"},
                {"address": "full_outstanding_balance", "net": "6000"},
                {"address": "outstanding_balance", "net": "6000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        fees_rate = "0.1"

        # 0.55 total across the 2 purchase accrual addresses without enabling interest on interest
        # 1000 * 0.1 / 365 = ~ 0.2739 * 2
        expected_purchase_accrual_pre_scod = "0.27"
        expected_purchase_accrual_post_scod = "0.27"
        expected_cash_adv_accrual = "1.10"
        expected_fees_accrual = "0.27"

        expected_calls = [
            accrue_interest_call(
                expected_purchase_accrual_pre_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="PRE_SCOD",
            ),
            accrue_interest_call(
                expected_purchase_accrual_post_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
            accrue_interest_call(
                expected_cash_adv_accrual,
                balance=2000,
                txn_type="CASH_ADVANCE",
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
        ]

        unexpected_calls = [
            accrue_interest_call(
                "0.68",
                balance=2500,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                expected_fees_accrual,
                balance=1000,
                txn_type="PURCHASE_FEE",
                daily_rate=Decimal(fees_rate) * 100 / 365,
            ),
            accrue_interest_call(
                expected_fees_accrual,
                balance=1000,
                txn_type="CASH_ADVANCE_FEE",
                daily_rate=Decimal(fees_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=dumps(
                {
                    "purchase": purchase_rate,
                    "cash_advance": cash_adv_rate,
                    "fees": fees_rate,
                }
            ),
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "transfer": {}}),
            accrue_interest_on_unpaid_fees=False,
            accrue_interest_from_txn_day=True,
        )
        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_no_interest_accrue_interest_on_unpaid_fees_when_disabled(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_unpaid", "net": "500"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "purchase_fees_unpaid", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "cash_advance_fees_charged", "net": "1000"},
                {"address": "cash_advance_fees_unpaid", "net": "1000"},
                {"address": "cash_advance_interest_billed", "net": "1000"},
                {"address": "full_outstanding_balance", "net": "6000"},
                {"address": "outstanding_balance", "net": "6000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        fees_rate = "0.1"

        # 0.55 without enabling interest on interest
        # 1000 * 0.1 / 365 = ~ 0.2739
        expected_purchase_accrual = "0.55"
        expected_cash_adv_accrual = "1.10"
        expected_fees_accrual = "0.27"

        expected_calls = [
            accrue_interest_call(
                expected_purchase_accrual,
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                expected_cash_adv_accrual,
                balance=2000,
                txn_type="CASH_ADVANCE",
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
        ]

        unexpected_calls = [
            accrue_interest_call(
                "0.68",
                balance=2500,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                expected_fees_accrual,
                balance=1000,
                txn_type="PURCHASE_FEE",
                daily_rate=Decimal(fees_rate) * 100 / 365,
            ),
            accrue_interest_call(
                expected_fees_accrual,
                balance=1000,
                txn_type="CASH_ADVANCE_FEE",
                daily_rate=Decimal(fees_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=dumps(
                {
                    "purchase": purchase_rate,
                    "cash_advance": cash_adv_rate,
                    "fees": fees_rate,
                }
            ),
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "transfer": {}}),
            accrue_interest_on_unpaid_fees=False,
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_accruals_from_txn_day_rounded_to_2dp(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        expected_purchase_accrual_pre_scod = "0.27"  # 5dp rounding amount would be 0.27398
        expected_purchase_accrual_post_scod = "0.27"  # 5dp rounding amount would be 0.27398
        expected_cash_adv_accrual = "1.10"  # 5dp rounding amount would be 1.09589

        expected_calls = [
            charge_interest_call(expected_cash_adv_accrual, txn_type="CASH_ADVANCE"),
            accrue_interest_call(
                expected_purchase_accrual_pre_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="PRE_SCOD",
            ),
            accrue_interest_call(
                expected_purchase_accrual_post_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
        ]
        base_interest_rates = f'{{"purchase": {purchase_rate} , "cash_advance": {cash_adv_rate}}}'

        mock_vault = self.create_mock(
            balance_ts=balances,
            credit_limit=Decimal("5000"),
            base_interest_rates=base_interest_rates,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_accruals_rounded_to_2dp(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        expected_purchase_accrual = "0.55"  # 5dp rounding amount would be 0.54795
        expected_cash_adv_accrual = "1.10"  # 5dp rounding amount would be 1.09589

        expected_calls = [
            charge_interest_call(expected_cash_adv_accrual, txn_type="CASH_ADVANCE"),
            accrue_interest_call(
                expected_purchase_accrual,
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        base_interest_rates = f'{{"purchase": {purchase_rate} , "cash_advance": {cash_adv_rate}}}'

        mock_vault = self.create_mock(
            balance_ts=balances,
            credit_limit=Decimal("5000"),
            accrue_interest_from_txn_day=False,
            base_interest_rates=base_interest_rates,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_accruals_below_2_dp_do_not_resulting_in_postings(self):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1"},
                {"address": "purchase_charged", "net": "1"},
                {"address": "cash_advance_billed", "net": "2"},
            ],
        )

        purchase_rate = "0.01"
        cash_adv_rate = "0.02"

        expected_calls = []

        base_interest_rates = dumps({"purchase": purchase_rate, "cash_advance": cash_adv_rate})

        mock_vault = self.create_mock(balance_ts=balances, base_interest_rates=base_interest_rates)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls, exact_order=True, exact_match=True
        )

    def test_no_interest_accrued_if_not_revolver_and_no_outstanding_statement_balance(
        self,
    ):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_charged", "net": "1000"},
                {"address": "FULL_OUTSTANDING_BALANCE", "net": "1000"},
            ],
        )

        expected_calls = []

        mock_vault = self.create_mock(balance_ts=balances, accrue_interest_from_txn_day="False")

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_mock_vault_method_calls(
            mock_vault.make_internal_transfer_instructions,
            expected_calls=expected_calls,
            exact_match=True,
        )

    def test_no_interest_accrued_if_not_revolver_and_positive_outstanding_statement_balance(
        self,
    ):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "DEFAULT", "net": "-1000"},
                {"address": "DEPOSIT", "net": "1000"},
                {"address": "OUTSTANDING_BALANCE", "net": "-1000"},
                {"address": "FULL_OUTSTANDING_BALANCE", "net": "-1000"},
            ],
        )

        expected_calls = []

        mock_vault = self.create_mock(balance_ts=balances, accrue_interest_from_txn_day="False")

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_mock_vault_method_calls(
            mock_vault.make_internal_transfer_instructions,
            expected_calls=expected_calls,
            exact_match=True,
        )

    def test_interest_charged_but_not_accrued_if_charge_interest_from_transaction_date(
        self,
    ):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "cash_advance_charged", "net": "2000"},
                {"address": "cash_advance_interest_unpaid", "net": "500"},
            ],
        )
        cash_adv_rate = "0.2"

        expected_calls = [
            charge_interest_call(amount="1.10", txn_type="CASH_ADVANCE", rebalanced_address="")
        ]
        unexpected_calls = [
            accrue_interest_call(
                amount="1.10",
                balance=2000,
                txn_type="CASH_ADVANCE",
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"cash_advance": {cash_adv_rate}}}',
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_charged_but_not_accrued_only_if_charge_interest_from_transaction_date(
        self,
    ):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "cash_advance_charged", "net": "2000"},
                {"address": "purchase_charged", "net": "2000"},
            ],
        )
        cash_adv_rate = "0.2"
        purchase_rate = "0.1"

        expected_calls = [charge_interest_call(amount="1.10", txn_type="CASH_ADVANCE")]

        unexpected_calls = [
            accrue_interest_call(
                amount="1.10",
                balance=2000,
                txn_type="CASH_ADVANCE",
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"cash_advance": {cash_adv_rate},"purchase": {purchase_rate}}}',
        )
        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_charged_on_spend_if_revolver_and_outstanding_statement_balance_is_zero(
        self,
    ):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "0"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "0"},
                {"address": "revolver", "net": "-1"},
            ],
        )

        purchase_rate = "0.1"
        expected_purchase_accrual = "0.27"  # Round(0.1 * 1000/365, 2)

        expected_calls = [charge_interest_call(expected_purchase_accrual)]

        mock_vault = self.create_mock(
            balance_ts=balances, base_interest_rates=f'{{"purchase": {purchase_rate}}}'
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_no_interest_accrued_or_charged_for_accrual_amount_below_2dp_when_revolver(
        self,
    ):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_charged", "net": "1"},
                {"address": "cash_advance_charged", "net": "1000"},
                {"address": "revolver", "net": "-1"},
            ],
        )

        unexpected_calls = [
            accrue_interest_call(amount=ANY, daily_rate=ANY, balance=ANY, txn_type="PURCHASE"),
            interest_rebalancing_call(
                amount=ANY,
                txn_type="PURCHASE",
                rebalancing_pot="PURCHASE_INTEREST_CHARGED",
            ),
        ]
        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_interest_charged_debits_default_and_txn_type_interest_address(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[{"address": "cash_advance_charged", "net": "2000"}],
        )
        cash_adv_rate = "0.2"

        expected_calls = [
            interest_rebalancing_call(
                amount="1.10",
                txn_type="CASH_ADVANCE",
                rebalancing_pot="CASH_ADVANCE_INTEREST_CHARGED",
            ),
            interest_rebalancing_call(
                amount="1.10", txn_type="CASH_ADVANCE", rebalancing_pot="DEFAULT"
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"cash_advance": {cash_adv_rate}}}',
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_interest_charged_for_multiple_txn_types_drawn_from_credit_line(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "cash_advance_charged", "net": "2000"},
                {"address": "purchase_charged", "net": "2000"},
                {"address": "revolver", "net": "-1"},
            ],
        )
        cash_adv_rate = "0.2"
        purchase_rate = "0.1"

        expected_calls = [
            interest_rebalancing_call(
                amount="1.10",
                txn_type="CASH_ADVANCE",
                rebalancing_pot="CASH_ADVANCE_INTEREST_CHARGED",
            ),
            interest_rebalancing_call(
                amount="1.10", txn_type="CASH_ADVANCE", rebalancing_pot="DEFAULT"
            ),
            interest_rebalancing_call(
                amount="0.55",
                txn_type="PURCHASE",
                rebalancing_pot="PURCHASE_INTEREST_CHARGED",
            ),
            interest_rebalancing_call(
                amount="0.55", txn_type="PURCHASE", rebalancing_pot="DEFAULT"
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"cash_advance": {cash_adv_rate},"purchase": {purchase_rate}}}',
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_interest_charged_drawn_from_deposit_and_credit_line_if_required(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "cash_advance_charged", "net": "2000"},
                {"address": "DEPOSIT", "net": "1"},
            ],
        )
        cash_adv_rate = "0.2"

        expected_calls = [
            interest_rebalancing_call(
                amount="1.1", txn_type="CASH_ADVANCE", rebalancing_pot="DEFAULT"
            ),
            interest_rebalancing_call(
                amount="0.1",
                txn_type="CASH_ADVANCE",
                rebalancing_pot="CASH_ADVANCE_INTEREST_CHARGED",
            ),
            interest_rebalancing_call(
                amount="-1", txn_type="CASH_ADVANCE", rebalancing_pot="DEPOSIT"
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"cash_advance": {cash_adv_rate}}}',
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_interest_charged_for_multiple_txn_types_results_in_interest_gl_postings(
        self,
    ):
        accrual_cut_off_dt = offset_datetime(2019, 2, 24, 23, 59, 59, 999999)
        offset_value_date = (accrual_cut_off_dt + timedelta(hours=LOCAL_UTC_OFFSET)).date()
        balances = init_balances(  # SCOD balances
            dt=accrual_cut_off_dt,
            balance_defs=[
                {"address": "cash_advance_charged", "net": "2000"},
                {"address": "purchase_charged", "net": "2000"},
                {"address": "revolver", "net": "-1"},
            ],
        )
        cash_adv_rate = "0.2"
        purchase_rate = "0.1"

        expected_calls = [
            charge_interest_air_call(
                amount="1.10",
                txn_type="CASH_ADVANCE",
                interest_value_date=offset_value_date,
            ),
            charge_interest_air_call(
                amount="0.55",
                txn_type="PURCHASE",
                interest_value_date=offset_value_date,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"cash_advance": {cash_adv_rate}, "purchase": {purchase_rate}}}',
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_interest_charged_for_interest_on_unpaid_fees_results_in_interest_gl_postings(
        self,
    ):
        accrual_cut_off_dt = offset_datetime(2019, 2, 24, 23, 59, 59, 999999)
        offset_value_date = (accrual_cut_off_dt + timedelta(hours=LOCAL_UTC_OFFSET)).date()
        balances = init_balances(  # SCOD balances
            dt=accrual_cut_off_dt,
            balance_defs=[
                {"address": "cash_advance_charged", "net": "2000"},
                {"address": "annual_fees_unpaid", "net": "2000"},
                {"address": "revolver", "net": "-1"},
            ],
        )
        cash_adv_rate = "0.2"
        fees_rate = "0.1"

        expected_calls = [
            charge_interest_air_call(
                amount="1.10",
                txn_type="CASH_ADVANCE",
                interest_value_date=offset_value_date,
            ),
            charge_interest_air_call(
                amount="0.55",
                txn_type="ANNUAL_FEE",
                interest_value_date=offset_value_date,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=dumps({"cash_advance": cash_adv_rate, "fees": fees_rate}),
            accrue_interest_on_unpaid_fees=True,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_interest_accrued_and_charged_updates_full_outstanding_aggregate_only(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "CASH_ADVANCE_CHARGED", "net": "1000"},
                {"address": "revolver", "net": "-1"},
                {"address": "full_outstanding_balance", "net": "3000"},
                {"address": "outstanding_balance", "net": "3000"},
            ],
        )

        purchase_rate = Decimal("0.1")
        cash_advance_rate = Decimal("0.1")
        expected_purchase_accrual = Decimal("0.55")  # Round(0.1 * 2000/365, 2)
        expected_cash_advance_accrual = Decimal("0.27")  # Round(0.1 * 1000/365, 2)

        expected_calls = [
            charge_interest_call(expected_purchase_accrual, txn_type="PURCHASE"),
            charge_interest_call(expected_cash_advance_accrual, txn_type="CASH_ADVANCE"),
            make_internal_transfer_instructions_call(
                amount=expected_purchase_accrual + expected_cash_advance_accrual,
                from_account_address=FULL_OUTSTANDING,
                to_account_address=INTERNAL,
            ),
        ]
        unexpected_calls = [
            make_internal_transfer_instructions_call(
                amount=ANY,
                from_account_address=OUTSTANDING,
                to_account_address=INTERNAL,
            ),
            make_internal_transfer_instructions_call(
                amount=ANY, from_account_address=AVAILABLE, to_account_address=INTERNAL
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=dumps(
                {"purchase": str(purchase_rate), "cash_advance": str(cash_advance_rate)}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, unexpected_calls)

    def test_interest_not_accrued_if_transactor_and_no_statement_balance(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[{"address": "purchase_charged", "net": "1"}],
        )
        purchase_rate = "0.001"
        mock_vault = self.create_mock(
            balance_ts=balances, base_interest_rates=f'{{"purchase": {purchase_rate}}}'
        )

        unexpected_calls = [charge_interest_call(), accrue_interest_call()]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_interest_not_accrued_if_accrual_amount_below_2dp(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[{"address": "purchase_billed", "net": "1"}],
        )
        purchase_rate = "0.001"
        mock_vault = self.create_mock(
            balance_ts=balances, base_interest_rates=f'{{"purchase": {purchase_rate}}}'
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        mock_calls = mock_vault.mock_calls
        self.assertEqual(charge_interest_call() not in mock_calls, True)

    def test_no_interest_accrued_if_flag_set(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "cash_advance_charged", "net": "2000"},
                {"address": "cash_advance_interest_unpaid", "net": "500"},
            ],
        )
        cash_adv_rate = "0.2"

        # Empty as we should see no accrual on account due to flag
        expected_calls = []

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"cash_advance": {cash_adv_rate}}}',
            accrual_blocking_flags='["90_DAYS_DELINQUENT"]',
            flags_ts={"90_DAYS_DELINQUENT": [(DEFAULT_DATE, True)]},
            accrue_interest_on_unpaid_interest=True,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls, exact_order=True, exact_match=True
        )

    def test_no_interest_accrued_if_flag_set_after_accrual_cut_off(self):
        accrual_date = offset_datetime(2019, 2, 25, 0, 0, 1)
        accrual_cut_off = offset_datetime(2019, 2, 24, 23, 59, 59, 999999)
        flag_date = accrual_cut_off

        balances = init_balances(  # SCOD balances
            dt=accrual_cut_off,
            balance_defs=[
                {"address": "cash_advance_charged", "net": "2000"},
                {"address": "cash_advance_interest_unpaid", "net": "500"},
            ],
        )
        cash_adv_rate = "0.2"

        # Empty as we should see no accrual on account due to flag
        expected_calls = []

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"cash_advance": {cash_adv_rate}}}',
            accrual_blocking_flags='["90_DAYS_DELINQUENT"]',
            flags_ts={"90_DAYS_DELINQUENT": [(flag_date, True)]},
            accrue_interest_on_unpaid_interest=True,
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=accrual_date,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls, exact_order=True, exact_match=True
        )

    def test_interest_accrued_from_txn_day_if_unparameterised_flag_set(self):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_charged", "net": "2000"},
                {"address": "purchase_billed", "net": "2000"},
            ],
        )
        purchase_rate = "0.2"

        expected_calls = [
            accrue_interest_call(
                amount="1.10",
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="PRE_SCOD",
            ),
            accrue_interest_call(
                amount="1.10",
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"purchase": {purchase_rate}}}',
            accrual_blocking_flags='["90_DAYS_DELINQUENT"]',
            flags_ts={"RANDOM_FLAG_NOT_IN_PARAMS": [(DEFAULT_DATE, True)]},
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_interest_accrued_if_unparameterised_flag_set(self):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_charged", "net": "2000"},
                {"address": "purchase_billed", "net": "2000"},
            ],
        )
        purchase_rate = "0.2"

        expected_calls = [
            accrue_interest_call(
                amount="2.19",
                balance=4000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"purchase": {purchase_rate}}}',
            accrual_blocking_flags='["90_DAYS_DELINQUENT"]',
            flags_ts={"RANDOM_FLAG_NOT_IN_PARAMS": [(DEFAULT_DATE, True)]},
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_no_interest_accrued_if_flag_set_with_invalid_and_valid_states(self):
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[{"address": "cash_advance_charged", "net": "2000"}],
        )
        cash_adv_rate = "0.2"

        # Empty as we should see no accrual on account due to flag
        expected_calls = []

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates=f'{{"cash_advance": {cash_adv_rate}}}',
            accrual_blocking_flags='["90_DAYS_DELINQUENT"]',
            flags_ts={
                "RANDOM_FLAG_NOT_IN_PARAMS": [(DEFAULT_DATE, True)],
                "90_DAYS_DELINQUENT": [(DEFAULT_DATE, True)],
            },
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls, exact_order=True, exact_match=True
        )

    def test_single_posting_batch_instructed_for_interest_accrual(self):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_charged", "net": "1000"},
                {"address": "revolver", "net": "-1"},
            ],
        )

        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
                client_batch_id=f"ACCRUE_INTEREST-{HOOK_EXECUTION_ID}",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances, base_interest_rates='{"purchase": "0.01"}'
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls, exact_order=True, exact_match=True
        )

    def test_single_posting_batch_instructed_for_interest_on_interest_accrual(self):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_charged", "net": "1000"},
                {"address": "purchase_interest_unpaid", "net": "500"},
                {"address": "revolver", "net": "-1"},
            ],
        )

        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
                client_batch_id=f"ACCRUE_INTEREST-{HOOK_EXECUTION_ID}",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates='{"purchase": "0.01"}',
            accrue_interest_on_unpaid_interest=True,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls, exact_order=True, exact_match=True
        )

    def test_single_posting_batch_instructed_for_interest_on_unpaid_fees_accrual(self):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "cash_advance_charged", "net": "1000"},
                {"address": "cash_advance_fees_unpaid", "net": "500"},
                {"address": "revolver", "net": "-1"},
            ],
        )

        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
                client_batch_id=f"ACCRUE_INTEREST-{HOOK_EXECUTION_ID}",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            base_interest_rates='{"cash_advance": "0.01", "fees": "0.01"}',
            accrue_interest_on_unpaid_fees=True,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls, exact_order=True, exact_match=True
        )

    def test_billed_rounded_to_2dp_with_txn_level_accrue_from_txn_day(self):
        # Here we test that a txn_level with no interest free correctly bills
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "balance_transfer_ref1_billed", "net": "3000"},
                {"address": "balance_transfer_ref2_billed", "net": "4000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"
        bt_ref2_rate = "0.44"
        expected_purchase_accrual_pre_scod = "0.27"  # 5dp rounding amount would be 0.27398
        expected_purchase_accrual_post_scod = "0.27"  # 5dp rounding amount would be 0.27398
        expected_cash_adv_accrual = "1.10"  # 5dp rounding amount would be 1.09589
        expected_bt_ref1_accrual = Decimal("2.79")  # 5dp rounding amount would be 1.09589
        expected_bt_ref2_accrual = Decimal("4.82")  # 5dp rounding amount would be 1.09589

        expected_calls = [
            charge_interest_call(expected_cash_adv_accrual, txn_type="CASH_ADVANCE"),
            charge_interest_call(expected_bt_ref1_accrual, txn_type="BALANCE_TRANSFER", ref="REF1"),
            charge_interest_call(expected_bt_ref2_accrual, txn_type="BALANCE_TRANSFER", ref="REF2"),
            accrue_interest_call(
                expected_purchase_accrual_pre_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="PRE_SCOD",
            ),
            accrue_interest_call(
                expected_purchase_accrual_post_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            credit_limit=Decimal("15000"),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "transfer": {},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            base_interest_rates=f'{{"purchase":{purchase_rate}, "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"REF1":{bt_ref1_rate} , '
            f'"ref2": {bt_ref2_rate}}}}}',
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {"REF1": "0.4", "ref2": "0.5"}}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_billed_rounded_to_2dp_with_txn_level(self):
        # Here we test that a txn_level with no interest free correctly bills
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "balance_transfer_ref1_billed", "net": "3000"},
                {"address": "balance_transfer_ref2_billed", "net": "4000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"
        bt_ref2_rate = "0.44"
        expected_purchase_accrual = "0.55"  # 5dp rounding amount would be 0.54795
        expected_cash_adv_accrual = "1.10"  # 5dp rounding amount would be 1.09589
        expected_bt_ref1_accrual = Decimal("2.79")  # 5dp rounding amount would be 1.09589
        expected_bt_ref2_accrual = Decimal("4.82")  # 5dp rounding amount would be 1.09589

        expected_calls = [
            charge_interest_call(expected_cash_adv_accrual, txn_type="CASH_ADVANCE"),
            charge_interest_call(expected_bt_ref1_accrual, txn_type="BALANCE_TRANSFER", ref="REF1"),
            charge_interest_call(expected_bt_ref2_accrual, txn_type="BALANCE_TRANSFER", ref="REF2"),
            accrue_interest_call(
                expected_purchase_accrual,
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            credit_limit=Decimal("15000"),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "transfer": {},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            base_interest_rates=f'{{"purchase":{purchase_rate}, "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"REF1":{bt_ref1_rate} , '
            f'"ref2": {bt_ref2_rate}}}}}',
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {"REF1": "0.4", "ref2": "0.5"}}
            ),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_accruals_rounded_to_2dp_with_txn_level_accrue_from_txn_day(self):
        # Here we test that a txn_level with interest free period correctly accrues
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "balance_transfer_ref1_billed", "net": "3000"},
                {"address": "balance_transfer_ref2_billed", "net": "4000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"
        bt_ref2_rate = "0.44"
        expected_purchase_accrual_pre_scod = "0.27"  # 5dp rounding amount would be 0.27398
        expected_purchase_accrual_post_scod = "0.27"  # 5dp rounding amount would be 0.27398
        expected_cash_adv_accrual = "1.10"  # 5dp rounding amount would be 1.09589
        expected_bt_ref1_accrual = "2.79"  # 5dp rounding amount would be 1.09589
        expected_bt_ref2_accrual = "4.82"  # 5dp rounding amount would be 1.09589

        expected_calls = [
            charge_interest_call(expected_cash_adv_accrual, txn_type="CASH_ADVANCE"),
            accrue_interest_call(
                expected_bt_ref1_accrual,
                balance=3000,
                txn_type="BALANCE_TRANSFER",
                ref="REF1",
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
            accrue_interest_call(
                expected_bt_ref2_accrual,
                balance=4000,
                txn_type="BALANCE_TRANSFER",
                ref="REF2",
                daily_rate=Decimal(bt_ref2_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
            accrue_interest_call(
                expected_purchase_accrual_pre_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="PRE_SCOD",
            ),
            accrue_interest_call(
                expected_purchase_accrual_post_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            credit_limit=Decimal("15000"),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "transfer": {},
                    "balance_transfer": {},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            base_interest_rates=f'{{"purchase":{purchase_rate} , "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"ref1":{bt_ref1_rate} , '
            f'"ref2": {bt_ref2_rate}}}}}',
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {"REF1": "0.4", "ref2": "0.5"}}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_accruals_rounded_to_2dp_with_txn_level(self):
        # Here we test that a txn_level with interest free period correctly accrues
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "balance_transfer_ref1_billed", "net": "3000"},
                {"address": "balance_transfer_ref2_billed", "net": "4000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"
        bt_ref2_rate = "0.44"
        expected_purchase_accrual = "0.55"  # 5dp rounding amount would be 0.54795
        expected_cash_adv_accrual = "1.10"  # 5dp rounding amount would be 1.09589
        expected_bt_ref1_accrual = "2.79"  # 5dp rounding amount would be 1.09589
        expected_bt_ref2_accrual = "4.82"  # 5dp rounding amount would be 1.09589

        expected_calls = [
            charge_interest_call(expected_cash_adv_accrual, txn_type="CASH_ADVANCE"),
            accrue_interest_call(
                expected_bt_ref1_accrual,
                balance=3000,
                txn_type="BALANCE_TRANSFER",
                ref="REF1",
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
            accrue_interest_call(
                expected_bt_ref2_accrual,
                balance=4000,
                txn_type="BALANCE_TRANSFER",
                ref="REF2",
                daily_rate=Decimal(bt_ref2_rate) * 100 / 365,
            ),
            accrue_interest_call(
                expected_purchase_accrual,
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            credit_limit=Decimal("15000"),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "transfer": {},
                    "balance_transfer": {},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            base_interest_rates=f'{{"purchase":{purchase_rate} , "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"ref1":{bt_ref1_rate} , '
            f'"ref2": {bt_ref2_rate}}}}}',
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {"REF1": "0.4", "ref2": "0.5"}}
            ),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_billed_interest_rounded_to_2dp_with_txn_level_accrue_from_txn_day(self):
        # Here we test that a txn_level with no interest free correctly bills
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "balance_transfer_ref1_billed", "net": "3000"},
                {"address": "balance_transfer_ref2_billed", "net": "4000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"
        bt_ref2_rate = "0.44"
        expected_purchase_accrual_pre_scod = "0.27"  # 5dp rounding amount would be 0.27398
        expected_purchase_accrual_post_scod = "0.27"  # 5dp rounding amount would be 0.27398
        expected_cash_adv_accrual = "1.10"  # 5dp rounding amount would be 1.09589
        expected_bt_ref1_accrual = Decimal("2.79")  # 5dp rounding amount would be 2.79452
        expected_bt_ref2_accrual = Decimal("4.82")  # 5dp rounding amount would be 4.82192

        expected_calls = [
            charge_interest_call(expected_cash_adv_accrual, txn_type="CASH_ADVANCE"),
            charge_interest_call(expected_bt_ref1_accrual, txn_type="BALANCE_TRANSFER", ref="REF1"),
            charge_interest_call(expected_bt_ref2_accrual, txn_type="BALANCE_TRANSFER", ref="REF2"),
            accrue_interest_call(
                expected_purchase_accrual_pre_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="PRE_SCOD",
            ),
            accrue_interest_call(
                expected_purchase_accrual_post_scod,
                balance=1000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            credit_limit=Decimal("15000"),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "transfer": {},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            base_interest_rates=f'{{"purchase":{purchase_rate}, "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"REF1":{bt_ref1_rate} , '
            f'"ref2": {bt_ref2_rate}}}}}',
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {"REF1": "0.4", "ref2": "0.5"}}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_billed_interest_rounded_to_2dp_with_txn_level(self):
        # Here we test that a txn_level with no interest free correctly bills
        balances = init_balances(  # SCOD balances
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_billed", "net": "2000"},
                {"address": "balance_transfer_ref1_billed", "net": "3000"},
                {"address": "balance_transfer_ref2_billed", "net": "4000"},
            ],
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"
        bt_ref2_rate = "0.44"
        expected_purchase_accrual = "0.55"  # 5dp rounding amount would be 0.54795
        expected_cash_adv_accrual = "1.10"  # 5dp rounding amount would be 1.09589
        expected_bt_ref1_accrual = Decimal("2.79")  # 5dp rounding amount would be 2.79452
        expected_bt_ref2_accrual = Decimal("4.82")  # 5dp rounding amount would be 4.82192

        expected_calls = [
            charge_interest_call(expected_cash_adv_accrual, txn_type="CASH_ADVANCE"),
            charge_interest_call(expected_bt_ref1_accrual, txn_type="BALANCE_TRANSFER", ref="REF1"),
            charge_interest_call(expected_bt_ref2_accrual, txn_type="BALANCE_TRANSFER", ref="REF2"),
            accrue_interest_call(
                expected_purchase_accrual,
                balance=2000,
                txn_type="PURCHASE",
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            credit_limit=Decimal("15000"),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "transfer": {},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            base_interest_rates=f'{{"purchase":{purchase_rate}, "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"REF1":{bt_ref1_rate} , '
            f'"ref2": {bt_ref2_rate}}}}}',
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {"REF1": "0.4", "ref2": "0.5"}}
            ),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_accrual_from_txn_day_with_mixed_case_refs(self):
        credit_limit = Decimal("5000")
        balances = init_balances(
            balance_defs=[
                {
                    "address": "balance_transfer_charged_from_first_day_lower_billed",
                    "net": "200",
                },
                {
                    "address": "balance_transfer_charged_from_first_day_upper_billed",
                    "net": "400",
                },
                {
                    "address": "balance_transfer_charged_from_first_day_mixed_billed",
                    "net": "600",
                },
                {
                    "address": "balance_transfer_not_charged_from_first_day_lower_billed",
                    "net": "800",
                },
                {
                    "address": "balance_transfer_not_charged_from_first_day_upper_billed",
                    "net": "1000",
                },
                {
                    "address": "balance_transfer_not_charged_from_first_day_mixed_billed",
                    "net": "1200",
                },
                {"address": "total_repayments_last_billed", "net": "3200"},
                {"address": "revolver", "net": "0"},
            ]
        )

        bt_rate = 0.22
        expected_calls = [
            charge_interest_call(
                amount="0.12",
                txn_type="BALANCE_TRANSFER_CHARGED_FROM_FIRST_DAY",
                ref="LOWER",
            ),
            charge_interest_call(
                amount="0.24",
                txn_type="BALANCE_TRANSFER_CHARGED_FROM_FIRST_DAY",
                ref="UPPER",
            ),
            charge_interest_call(
                amount="0.36",
                txn_type="BALANCE_TRANSFER_CHARGED_FROM_FIRST_DAY",
                ref="MIXED",
            ),
            accrue_interest_call(
                amount="0.48",
                balance=800,
                txn_type="BALANCE_TRANSFER_NOT_CHARGED_FROM_FIRST_DAY",
                daily_rate=Decimal(bt_rate) * 100 / 365,
                ref="LOWER",
                accrual_type="POST_SCOD",
            ),
            accrue_interest_call(
                amount="0.60",
                balance=1000,
                txn_type="BALANCE_TRANSFER_NOT_CHARGED_FROM_FIRST_DAY",
                daily_rate=Decimal(bt_rate) * 100 / 365,
                ref="UPPER",
                accrual_type="POST_SCOD",
            ),
            accrue_interest_call(
                amount="0.72",
                balance=1200,
                txn_type="BALANCE_TRANSFER_NOT_CHARGED_FROM_FIRST_DAY",
                daily_rate=Decimal(bt_rate) * 100 / 365,
                ref="MIXED",
                accrual_type="POST_SCOD",
            ),
        ]

        transaction_type_internal_accounts_map = {
            "balance_transfer_charged_from_first_day": "balance_transfer_internal_account",
            "balance_transfer_not_charged_from_first_day": "balance_transfer_internal_account",
        }

        mock_vault = self.create_mock(
            balance_ts=balances,
            credit_limit=credit_limit,
            transaction_types=dumps(
                {
                    "balance_transfer_charged_from_first_day": {
                        "charge_interest_from_transaction_date": "True"
                    },
                    "balance_transfer_not_charged_from_first_day": {},
                }
            ),
            transaction_references=dumps(
                {
                    "balance_transfer_charged_from_first_day": [
                        "lower",
                        "UPPER",
                        "mIxEd",
                    ],
                    "balance_transfer_not_charged_from_first_day": [
                        "lower",
                        "UPPER",
                        "mIxEd",
                    ],
                }
            ),
            transaction_base_interest_rates=dumps(
                {
                    "balance_transfer_charged_from_first_day": {
                        "lower": str(bt_rate),
                        "UPPER": str(bt_rate),
                        "mIxEd": str(bt_rate),
                    },
                    "balance_transfer_not_charged_from_first_day": {
                        "lower": str(bt_rate),
                        "UPPER": str(bt_rate),
                        "mIxEd": str(bt_rate),
                    },
                }
            ),
            transaction_annual_percentage_rate=dumps(
                {
                    "balance_transfer_charged_from_first_day": {
                        "lower": "0.4",
                        "UPPER": "0.5",
                        "mIxEd": "0.6",
                    },
                    "balance_transfer_not_charged_from_first_day": {
                        "lower": "0.4",
                        "UPPER": "0.5",
                        "mIxEd": "0.6",
                    },
                }
            ),
            minimum_percentage_due=dumps(
                {
                    "balance_transfer_charged_from_first_day": "0.3",
                    "balance_transfer_not_charged_from_first_day": "0.3",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
            transaction_type_internal_accounts_map=dumps(transaction_type_internal_accounts_map),
            transaction_type_fees_internal_accounts_map=dumps(
                {
                    "balance_transfer_charged_from_first_day": {
                        "loan": "balance_transfer_fee_loan_internal_account",
                        "income": "balance_transfer_fee_income_internal_account",
                    },
                    "balance_transfer_not_charged_from_first_day": {
                        "loan": "balance_transfer_fee_loan_internal_account",
                        "income": "balance_transfer_fee_income_internal_account",
                    },
                }
            ),
            transaction_type_interest_internal_accounts_map=dumps(
                {
                    "balance_transfer_charged_from_first_day": {
                        "air": "balance_transfer_air_internal_account",
                        "income": "balance_transfer_interest_income_internal_account",
                    },
                    "balance_transfer_not_charged_from_first_day": {
                        "air": "balance_transfer_air_internal_account",
                        "income": "balance_transfer_interest_income_internal_account",
                    },
                }
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 2, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_accrual_with_mixed_case_refs(self):
        credit_limit = Decimal("5000")
        balances = init_balances(
            balance_defs=[
                {
                    "address": "balance_transfer_charged_from_first_day_lower_billed",
                    "net": "200",
                },
                {
                    "address": "balance_transfer_charged_from_first_day_upper_billed",
                    "net": "400",
                },
                {
                    "address": "balance_transfer_charged_from_first_day_mixed_billed",
                    "net": "600",
                },
                {
                    "address": "balance_transfer_not_charged_from_first_day_lower_billed",
                    "net": "800",
                },
                {
                    "address": "balance_transfer_not_charged_from_first_day_upper_billed",
                    "net": "1000",
                },
                {
                    "address": "balance_transfer_not_charged_from_first_day_mixed_billed",
                    "net": "1200",
                },
                {"address": "total_repayments_last_billed", "net": "3200"},
                {"address": "revolver", "net": "0"},
            ]
        )

        bt_rate = 0.22
        expected_calls = [
            charge_interest_call(
                amount="0.12",
                txn_type="BALANCE_TRANSFER_CHARGED_FROM_FIRST_DAY",
                ref="LOWER",
            ),
            charge_interest_call(
                amount="0.24",
                txn_type="BALANCE_TRANSFER_CHARGED_FROM_FIRST_DAY",
                ref="UPPER",
            ),
            charge_interest_call(
                amount="0.36",
                txn_type="BALANCE_TRANSFER_CHARGED_FROM_FIRST_DAY",
                ref="MIXED",
            ),
            accrue_interest_call(
                amount="0.48",
                balance=800,
                txn_type="BALANCE_TRANSFER_NOT_CHARGED_FROM_FIRST_DAY",
                daily_rate=Decimal(bt_rate) * 100 / 365,
                ref="LOWER",
            ),
            accrue_interest_call(
                amount="0.60",
                balance=1000,
                txn_type="BALANCE_TRANSFER_NOT_CHARGED_FROM_FIRST_DAY",
                daily_rate=Decimal(bt_rate) * 100 / 365,
                ref="UPPER",
            ),
            accrue_interest_call(
                amount="0.72",
                balance=1200,
                txn_type="BALANCE_TRANSFER_NOT_CHARGED_FROM_FIRST_DAY",
                daily_rate=Decimal(bt_rate) * 100 / 365,
                ref="MIXED",
            ),
        ]

        transaction_type_internal_accounts_map = {
            "balance_transfer_charged_from_first_day": "balance_transfer_internal_account",
            "balance_transfer_not_charged_from_first_day": "balance_transfer_internal_account",
        }

        mock_vault = self.create_mock(
            balance_ts=balances,
            credit_limit=credit_limit,
            transaction_types=dumps(
                {
                    "balance_transfer_charged_from_first_day": {
                        "charge_interest_from_transaction_date": "True"
                    },
                    "balance_transfer_not_charged_from_first_day": {},
                }
            ),
            transaction_references=dumps(
                {
                    "balance_transfer_charged_from_first_day": [
                        "lower",
                        "UPPER",
                        "mIxEd",
                    ],
                    "balance_transfer_not_charged_from_first_day": [
                        "lower",
                        "UPPER",
                        "mIxEd",
                    ],
                }
            ),
            transaction_base_interest_rates=dumps(
                {
                    "balance_transfer_charged_from_first_day": {
                        "lower": str(bt_rate),
                        "UPPER": str(bt_rate),
                        "mIxEd": str(bt_rate),
                    },
                    "balance_transfer_not_charged_from_first_day": {
                        "lower": str(bt_rate),
                        "UPPER": str(bt_rate),
                        "mIxEd": str(bt_rate),
                    },
                }
            ),
            transaction_annual_percentage_rate=dumps(
                {
                    "balance_transfer_charged_from_first_day": {
                        "lower": "0.4",
                        "UPPER": "0.5",
                        "mIxEd": "0.6",
                    },
                    "balance_transfer_not_charged_from_first_day": {
                        "lower": "0.4",
                        "UPPER": "0.5",
                        "mIxEd": "0.6",
                    },
                }
            ),
            minimum_percentage_due=dumps(
                {
                    "balance_transfer_charged_from_first_day": "0.3",
                    "balance_transfer_not_charged_from_first_day": "0.3",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
            transaction_type_internal_accounts_map=dumps(transaction_type_internal_accounts_map),
            transaction_type_fees_internal_accounts_map=dumps(
                {
                    "balance_transfer_charged_from_first_day": {
                        "loan": "balance_transfer_fee_loan_internal_account",
                        "income": "balance_transfer_fee_income_internal_account",
                    },
                    "balance_transfer_not_charged_from_first_day": {
                        "loan": "balance_transfer_fee_loan_internal_account",
                        "income": "balance_transfer_fee_income_internal_account",
                    },
                }
            ),
            transaction_type_interest_internal_accounts_map=dumps(
                {
                    "balance_transfer_charged_from_first_day": {
                        "air": "balance_transfer_air_internal_account",
                        "income": "balance_transfer_interest_income_internal_account",
                    },
                    "balance_transfer_not_charged_from_first_day": {
                        "air": "balance_transfer_air_internal_account",
                        "income": "balance_transfer_interest_income_internal_account",
                    },
                }
            ),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 2, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_interest_still_charged_normally_even_on_repayment_holiday(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_unpaid", "net": "400"},
                {"address": "purchase_interest_unpaid", "net": "100"},
                {"address": "late_repayment_fees_unpaid", "net": "200"},
                {"address": "revolver", "net": "-1"},
            ]
        )
        expected_calls = [
            # Purchase interest charged at 1500/365 = 4.11
            charge_interest_call(amount="4.11", txn_type="PURCHASE"),
            # Fees interest charged at 200/365 = 0.55
            charge_interest_call(amount="0.55", txn_type="LATE_REPAYMENT_FEE"),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            mad_equal_to_zero_flags='["REPAYMENT_HOLIDAY"]',
            overdue_amount_blocking_flags='["REPAYMENT_HOLIDAY"]',
            billed_to_unpaid_transfer_blocking_flags='["REPAYMENT_HOLIDAY"]',
            flags_ts={"REPAYMENT_HOLIDAY": [(DEFAULT_DATE - timedelta(days=1), True)]},
            accrue_interest_on_unpaid_fees=True,
            accrue_interest_on_unpaid_interest=True,
            base_interest_rates=dumps({"purchase": "1", "fees": "1"}),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)


class BalanceHelperTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def compare_balance_dicts(self, actual_balances, expected_balances):

        self.assertTrue(len(actual_balances) == len(expected_balances))

        # This could be improved to check no differences instead of failing the test on first one
        for dimensions in expected_balances:
            self.assertTrue(
                compare_balances(actual_balances[dimensions], expected_balances[dimensions])
            )

    def test_update_balances_with_existing_dimensions(self):
        BalanceHelperTests.tside = Tside.LIABILITY
        balances = init_balances(
            contract_tside=Tside.LIABILITY,
            balance_defs=[
                {
                    "address": "TEST_ADDRESS",
                    "denomination": "XAU",
                    "phase": Phase.COMMITTED,
                    "net": Decimal("100"),
                }
            ],
        ).latest()

        postings = [
            self.custom_instruction(
                amount="200",
                credit=False,
                account_address="TEST_ADDRESS",
                denomination="XAU",
                asset="COMMERCIAL_BANK_MONEY",
                phase=Phase.COMMITTED,
            )
        ]
        dimensions = ("TEST_ADDRESS", "COMMERCIAL_BANK_MONEY", "XAU", Phase.COMMITTED)

        run(
            self.smart_contract,
            "_update_balances",
            Mock(),
            account_id=ACCOUNT_ID,
            balances=balances,
            postings=postings,
        )

        self.assertEqual(
            True,
            compare_balances(
                Balance(Decimal(100), Decimal(200), Decimal(-100)), balances[dimensions]
            ),
            "in_flight_balances not initialised to posting balances",
        )

    def test_update_balances_with_new_dimensions(self):
        balances = init_balances(
            contract_tside=Tside.LIABILITY,
            balance_defs=[
                {
                    "address": "TEST_ADDRESS",
                    "denomination": "XAU",
                    "phase": Phase.COMMITTED,
                    "net": Decimal("100"),
                }
            ],
        ).latest()

        postings = [
            self.custom_instruction(
                amount="200",
                credit=False,
                account_address="ABCD",
                denomination="ZZZ",
                asset="1234",
                phase=Phase.COMMITTED,
            )
        ]
        existing_dimensions = (
            "TEST_ADDRESS",
            "COMMERCIAL_BANK_MONEY",
            "XAU",
            Phase.COMMITTED,
        )
        new_dimensions = ("ABCD", "1234", "ZZZ", Phase.COMMITTED)

        run(
            self.smart_contract,
            "_update_balances",
            Mock(),
            account_id=ACCOUNT_ID,
            balances=balances,
            postings=postings,
        )

        self.assertEqual(
            True,
            compare_balances(
                Balance(Decimal(100), Decimal(0), Decimal(100)),
                balances[existing_dimensions],
            ),
            "existing dimensions should not have changed",
        )
        self.assertEqual(
            True,
            compare_balances(
                Balance(Decimal(0), Decimal(200), Decimal(-200)),
                balances[new_dimensions],
            ),
            "new posting dimensions should have been updated",
        )

    def test_update_balances_accounts_for_tside(self):
        balances = BalanceDefaultDict(lambda *_: Balance())
        postings = [
            self.custom_instruction(
                amount="200",
                credit=False,
                account_address="ABCD",
                denomination="ZZZ",
                asset="1234",
                phase=Phase.COMMITTED,
            )
        ]
        dimensions = ("ABCD", "1234", "ZZZ", Phase.COMMITTED)

        run(
            self.smart_contract,
            "_update_balances",
            Mock(),
            account_id=ACCOUNT_ID,
            balances=balances,
            postings=postings,
        )

        self.assertEqual(
            True,
            compare_balances(Balance(Decimal(0), Decimal(200), Decimal(200)), balances[dimensions]),
            "TSide was not accounted for",
        )


class AggregateBalanceHelperTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def setUp(self):
        super().setUp()
        self.balances = init_balances(
            balance_defs=[
                # by setting the values at different powers of 10 we can easily see which were
                # included in the calc or not
                {"address": "DEPOSIT", "net": "10000000000"},
                {"address": "PURCHASE_BILLED", "net": "1"},
                {"address": "CASH_ADVANCE_CHARGED", "net": "10"},
                {"address": "TRANSFER_UNPAID", "net": "100"},
                {"address": "PURCHASE_INTEREST_UNCHARGED", "net": "1000"},
                {"address": "PURCHASE_INTEREST_BILLED", "net": "10000"},
                {"address": "CASH_ADVANCE_INTEREST_CHARGED", "net": "100000"},
                {"address": "TRANSFER_INTEREST_UNPAID", "net": "1000000"},
                {"address": "ANNUAL_FEES_CHARGED", "net": "10000000"},
                {"address": "CASH_ADVANCE_FEES_BILLED", "net": "100000000"},
                {"address": "DISPUTE_FEES_UNPAID", "net": "1000000000"},
            ]
        )

    def test_balance_def_with_principal_only(self):
        balance_def = {"PRINCIPAL": ["CHARGED", "BILLED", "UNPAID"]}

        expected_outcome = Decimal("-9999999889")
        output = run(
            self.smart_contract,
            "_calculate_aggregate_balance",
            Mock(),
            balances=self.balances.latest(),
            txn_type_map={"PURCHASE": None, "CASH_ADVANCE": None, "TRANSFER": None},
            fee_types=["ANNUAL_FEE", "DISPUTE_FEE"],
            denomination=DEFAULT_DENOM,
            balance_def=balance_def,
            include_deposit=True,
        )

        self.assertEqual(expected_outcome, output)

    def test_balance_def_with_interest_only(self):
        balance_def = {"INTEREST": ["UNCHARGED", "CHARGED", "BILLED", "UNPAID"]}
        expected_outcome = Decimal("-9998889000")
        output = run(
            self.smart_contract,
            "_calculate_aggregate_balance",
            Mock(),
            balances=self.balances.latest(),
            txn_type_map={"PURCHASE": None, "CASH_ADVANCE": None, "TRANSFER": None},
            fee_types=["ANNUAL_FEE", "DISPUTE_FEE"],
            denomination=DEFAULT_DENOM,
            balance_def=balance_def,
            include_deposit=True,
        )

        self.assertEqual(expected_outcome, output)

    def test_balance_def_with_fees_only(self):
        balance_def = {"FEES": ["CHARGED", "BILLED", "UNPAID"]}
        expected_outcome = Decimal("-8990000000")
        output = run(
            self.smart_contract,
            "_calculate_aggregate_balance",
            Mock(),
            balances=self.balances.latest(),
            txn_type_map={"PURCHASE": None, "CASH_ADVANCE": None, "TRANSFER": None},
            fee_types=["ANNUAL_FEE", "DISPUTE_FEE"],
            denomination=DEFAULT_DENOM,
            balance_def=balance_def,
            include_deposit=True,
        )

        self.assertEqual(expected_outcome, output)

    def test_balance_def_with_mixed_states_and_balance_types(self):
        balance_def = {
            "FEES": ["UNPAID"],
            "INTEREST": ["BILLED"],
            "PRINCIPAL": ["CHARGED"],
        }
        expected_outcome = Decimal("-8999989990")
        output = run(
            self.smart_contract,
            "_calculate_aggregate_balance",
            Mock(),
            balances=self.balances.latest(),
            txn_type_map={"PURCHASE": None, "CASH_ADVANCE": None, "TRANSFER": None},
            fee_types=["ANNUAL_FEE", "DISPUTE_FEE"],
            denomination=DEFAULT_DENOM,
            balance_def=balance_def,
            include_deposit=True,
        )

        self.assertEqual(expected_outcome, output)

    def test_deposit_can_be_excluded(self):
        balance_def = {
            "FEES": ["UNPAID"],
            "INTEREST": ["BILLED"],
            "PRINCIPAL": ["CHARGED"],
        }
        expected_outcome = Decimal("1000010010")
        output = run(
            self.smart_contract,
            "_calculate_aggregate_balance",
            Mock(),
            balances=self.balances.latest(),
            txn_type_map={"PURCHASE": None, "CASH_ADVANCE": None, "TRANSFER": None},
            fee_types=["ANNUAL_FEE", "DISPUTE_FEE"],
            denomination=DEFAULT_DENOM,
            balance_def=balance_def,
            include_deposit=False,
        )

        self.assertEqual(expected_outcome, output)


class CreditCardHelpersTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_that_year_2000_is_leap_year(self):
        # Year divisible by 400
        expected_outcome = True
        output = run(self.smart_contract, "_is_leap_year", Mock(), year=2000)
        self.assertEqual(expected_outcome, output)

    def test_that_year_1900_is_not_leap_year(self):
        # Year divisible by 100 but not 400
        expected_outcome = False
        output = run(self.smart_contract, "_is_leap_year", Mock(), year=1900)
        self.assertEqual(expected_outcome, output)

    def test_that_year_2020_is_leap_year(self):
        # Year divisible by 4 but not 400 or 100
        expected_outcome = True
        output = run(self.smart_contract, "_is_leap_year", Mock(), year=2020)
        self.assertEqual(expected_outcome, output)

    def test_that_year_2019_is_not_leap_year(self):
        # Year not divisible by 400, 100 or 4
        expected_outcome = False
        output = run(self.smart_contract, "_is_leap_year", Mock(), year=2019)
        self.assertEqual(expected_outcome, output)

    def test_non_leap_year_daily_rate_correct(self):
        expected_outcome = 0.0002739726
        output = run(
            self.smart_contract,
            "_yearly_to_daily_rate",
            Mock(),
            yearly_rate=0.1,
            leap_year=False,
        )
        output = round(output, 10)
        self.assertEqual(expected_outcome, output)

    def test_leap_year_daily_rate_correct(self):
        expected_outcome = 0.0002732240
        output = run(
            self.smart_contract,
            "_yearly_to_daily_rate",
            Mock(),
            yearly_rate=0.1,
            leap_year=True,
        )
        output = round(output, 10)
        self.assertEqual(expected_outcome, output)

    def test_false_string_parsed_as_false(self):
        expected_outcome = False
        output = run(
            self.smart_contract,
            "_str_to_bool",
            Mock(),
            string="false",
        )
        output = round(output, 10)
        self.assertEqual(expected_outcome, output)

    def test_true_string_parsed_as_true(self):
        expected_outcome = True
        output = run(
            self.smart_contract,
            "_str_to_bool",
            Mock(),
            string="true",
        )
        output = round(output, 10)
        self.assertEqual(expected_outcome, output)

    def test_random_string_parsed_as_false(self):
        expected_outcome = False
        output = run(
            self.smart_contract,
            "_str_to_bool",
            Mock(),
            string="abcd",
        )
        output = round(output, 10)
        self.assertEqual(expected_outcome, output)

    def test_string_case_does_not_affect_outcome(self):
        expected_outcome = True
        output = run(
            self.smart_contract,
            "_str_to_bool",
            Mock(),
            string="tRue",
        )
        output = round(output, 10)
        self.assertEqual(expected_outcome, output)

    def test_posting_instruction_without_advice_is_not_filtered_out(self):
        postings = [self.transfer(amount=Decimal(1))]
        expected_outcome = postings

        output = run(self.smart_contract, "_get_non_advice_postings", Mock(), postings=postings)
        self.assertEqual(expected_outcome, output)

    def test_advice_posting_is_filtered_out(self):
        posting = self.mock_posting_instruction(advice=True, amount=Decimal(1))
        postings = [posting]
        expected_outcome = []

        output = run(self.smart_contract, "_get_non_advice_postings", Mock(), postings=postings)
        self.assertEqual(expected_outcome, output)

    def test_non_advice_posting_is_not_filtered_out(self):
        posting = self.mock_posting_instruction(advice=False, amount=Decimal(1))
        postings = [posting]
        expected_outcome = [posting]
        output = run(self.smart_contract, "_get_non_advice_postings", Mock(), postings=postings)
        self.assertEqual(expected_outcome, output)

    def test_first_scod_is_1_month_minus_1_day_from_account_opening(self):
        scod_start, scod_end = run(
            self.smart_contract,
            "_get_first_scod",
            Mock(),
            account_creation_date=offset_datetime(2020, 10, 4, 13, 12, 54),
        )

        self.assertEqual(
            (offset_datetime(2020, 11, 3, 0), offset_datetime(2020, 11, 4, 0)),
            (scod_start, scod_end),
        )

    def test_first_scod_is_1_month_minus_1_day_from_account_opening_if_utc_and_local_date_differ(
        self,
    ):
        scod_start, scod_end = run(
            self.smart_contract,
            "_get_first_scod",
            Mock(),
            # This date is 1 day later in OFFSET timezone
            account_creation_date=offset_datetime(2020, 10, 4, 17, 12, 54),
        )

        self.assertEqual(
            (offset_datetime(2020, 11, 3, 0), offset_datetime(2020, 11, 4, 0)),
            (scod_start, scod_end),
        )

    def test_first_scod_localised_correctly_if_utc_and_local_date_are_identical(self):
        scod_start, scod_end = run(
            self.smart_contract,
            "_get_first_scod",
            Mock(),
            account_creation_date=datetime(2020, 10, 4, 13, 12, 54),
            localize_datetime=True,
        )

        self.assertEqual((datetime(2020, 11, 3), datetime(2020, 11, 4)), (scod_start, scod_end))

    def test_first_scod_localised_correctly_if_utc_and_local_date_are_different(self):
        scod_start, scod_end = run(
            self.smart_contract,
            "_get_first_scod",
            Mock(),
            # This date is 1 day later in OFFSET timezone
            account_creation_date=offset_datetime(2020, 10, 4, 18, 12, 54),
            localize_datetime=True,
        )

        self.assertEqual((datetime(2020, 11, 3), datetime(2020, 11, 4)), (scod_start, scod_end))

    def test_first_pdd_is_pdp_days_from_first_scod(self):
        pdd_start, pdd_end = run(
            self.smart_contract,
            "_get_first_pdd",
            Mock(),
            payment_due_period=22,
            first_scod_start=datetime(2020, 11, 3, 0),
        )

        self.assertEqual(
            (datetime(2020, 11, 25, 0), datetime(2020, 11, 26, 0)), (pdd_start, pdd_end)
        )

    def test_first_pdd_is_pdp_days_from_localized_first_scod(self):
        pdd_start, pdd_end = run(
            self.smart_contract,
            "_get_first_pdd",
            Mock(),
            payment_due_period=22,
            first_scod_start=datetime(2020, 11, 4),
        )

        self.assertEqual((datetime(2020, 11, 26), datetime(2020, 11, 27)), (pdd_start, pdd_end))

    def test_next_pdd_is_first_pdd_if_no_pdd_execution(self):
        pdd_start, pdd_end = run(
            self.smart_contract,
            "_get_next_pdd",
            Mock(),
            payment_due_period=22,
            account_creation_date=offset_datetime(2020, 10, 5, 10),
        )

        self.assertEqual(
            (offset_datetime(2020, 11, 26, 0), offset_datetime(2020, 11, 27, 0)),
            (pdd_start, pdd_end),
        )

    def test_localized_next_pdd_is_localized_first_pdd_if_no_pdd_execution(self):
        pdd_start, pdd_end = run(
            self.smart_contract,
            "_get_next_pdd",
            Mock(),
            payment_due_period=22,
            localize_datetime=True,
            account_creation_date=datetime(2020, 10, 5, 10),
        )

        self.assertEqual((datetime(2020, 11, 26), datetime(2020, 11, 27)), (pdd_start, pdd_end))

    def test_next_pdd_calculated_from_latest_pdd_start(self):
        pdd_start, pdd_end = run(
            self.smart_contract,
            "_get_next_pdd",
            Mock(),
            payment_due_period=22,
            last_pdd_execution_datetime=offset_datetime(2021, 8, 26, 0, 0, 1),
            account_creation_date=offset_datetime(2021, 10, 5, 10),
        )

        self.assertEqual(
            (offset_datetime(2021, 9, 26, 0), offset_datetime(2021, 9, 27, 0)),
            (pdd_start, pdd_end),
        )

    def test_next_pdd_when_current_pdd_local_and_utc_months_differ(self):
        pdd_start, pdd_end = run(
            self.smart_contract,
            "_get_next_pdd",
            Mock(),
            payment_due_period=22,
            last_pdd_execution_datetime=offset_datetime(2019, 3, 1, 0, 0, 1),
            account_creation_date=offset_datetime(2019, 1, 8, 13),
        )

        self.assertEqual(
            (offset_datetime(2019, 3, 1, 0), offset_datetime(2019, 3, 2, 0)),
            (pdd_start, pdd_end),
        )

    def test_localised_next_pdd_when_current_pdd_local_and_utc_months_differ(self):
        pdd_start, pdd_end = run(
            self.smart_contract,
            "_get_next_pdd",
            Mock(),
            payment_due_period=22,
            last_pdd_execution_datetime=datetime(2019, 3, 1, 0, 0, 1),
            account_creation_date=datetime(2019, 1, 8, 13),
            localize_datetime=True,
        )

        self.assertEqual((datetime(2019, 3, 1), datetime(2019, 3, 2)), (pdd_start, pdd_end))

    def test_next_pdd_accounts_for_different_month_lengths(self):
        pdd_start, pdd_end = run(
            self.smart_contract,
            "_get_next_pdd",
            Mock(),
            payment_due_period=26,
            last_pdd_execution_datetime=offset_datetime(2020, 5, 31, 0, 0, 1),
            account_creation_date=offset_datetime(2020, 4, 6, 10),
        )
        # 1st SCOD starts at on 2020, 5, 5 OFFSET timezone -> 2020, 5, 4, 16 UTC
        # 1st PDD starts on 2020, 5, 30, 16 UTC and ends on 2020, 5, 31, 16 UTC
        # Next PDD should be 2020, 6, 29, 16 / 2020, 5, 30 16 UTC as June has 30 days and May has 31
        self.assertEqual(
            (offset_datetime(2020, 6, 30, 0), offset_datetime(2020, 7, 1, 0)),
            (pdd_start, pdd_end),
        )

    def test_next_pdd_preserves_original_pdd_date_if_latest_pdd_on_different_date(self):
        pdd_start, pdd_end = run(
            self.smart_contract,
            "_get_next_pdd",
            Mock(),
            payment_due_period=26,
            last_pdd_execution_datetime=offset_datetime(2020, 6, 30, 0, 0, 1),
            account_creation_date=offset_datetime(2020, 4, 6, 10),
        )
        self.assertEqual(
            (
                offset_datetime(2020, 7, 31, 0),
                offset_datetime(
                    2020,
                    8,
                    1,
                ),
            ),
            (pdd_start, pdd_end),
        )

    def test_localized_next_pdd_accounts_for_different_month_lengths(self):
        pdd_start, pdd_end = run(
            self.smart_contract,
            "_get_next_pdd",
            Mock(),
            payment_due_period=26,
            last_pdd_execution_datetime=datetime(2020, 5, 31, 0, 0, 1),
            account_creation_date=datetime(2020, 4, 6, 10),
            localize_datetime=True,
        )
        # 1st SCOD starts at on 2020, 5, 5 OFFSET timezone
        # 1st PDD starts on 2020, 5, 31 OFFSET timezone and ends on 2020, 6, 1 UTC
        # Next PDD should be 2020, 6, 30 OFFSET timezone as June has 30 days and May has 31
        self.assertEqual((datetime(2020, 6, 30), datetime(2020, 7, 1)), (pdd_start, pdd_end))

    def test_localized_next_pdd_preserves_original_pdd_date_if_latest_pdd_on_different_date(
        self,
    ):
        pdd_start, pdd_end = run(
            self.smart_contract,
            "_get_next_pdd",
            Mock(),
            payment_due_period=26,
            last_pdd_execution_datetime=datetime(2020, 6, 30, 0, 0, 1),
            account_creation_date=datetime(2020, 4, 6, 10),
            localize_datetime=True,
        )
        self.assertEqual((datetime(2020, 7, 31), datetime(2020, 8, 1)), (pdd_start, pdd_end))

    def test_scod_is_payment_due_period_days_away_from_pdd(self):
        scod_start, scod_end = run(
            self.smart_contract,
            "_get_scod_for_pdd",
            Mock(),
            payment_due_period=26,
            pdd_start=datetime(2020, 6, 30, 0),
        )

        self.assertEqual((datetime(2020, 6, 4, 0), datetime(2020, 6, 5, 0)), (scod_start, scod_end))

    def test_combine_txn_and_type_rates(self):
        expected_outcome = {
            "type_a_with_refs_ref1": "1",
            "type_a_with_refs_ref2": "2",
            "type_a_without_refs": "5",
            "type_b_with_refs_ref8": "4",
            "type_b_with_refs_ref9": "3",
            "type_b_without_refs": "6",
        }

        txn_level_rate = {
            "type_a_with_refs": {"ref1": "1", "ref2": "2"},
            "type_b_with_refs": {"ref9": "3", "ref8": "4"},
        }
        txn_type_rate = {"type_a_without_refs": "5", "type_b_without_refs": "6"}

        output = run(
            self.smart_contract,
            "_combine_txn_and_type_rates",
            Mock(),
            txn_level_rate=txn_level_rate,
            txn_type_rate=txn_type_rate,
        )
        self.assertEqual(expected_outcome, output)

    def test_construct_full_list_of_stems(self):
        expected_outcome = ["abc", "def", "ghi_a", "ghi_b", "ghi_c"]
        output = run(
            self.smart_contract,
            "_construct_stems",
            Mock(),
            txn_types={"abc": None, "def": None, "ghi": ["a", "b", "c"]},
        )
        self.assertEqual(expected_outcome, output)

    def test_order_stems_by_repayment_hierarchy(self):
        expected_outcome = ["ghi_b", "abc", "ghi_a", "def", "ghi_c"]
        transaction_type_hierarchy = {"abc": "4", "def": "2"}
        transaction_hiererchy = {"ghi": {"a": "3", "b": "5", "c": "1"}}

        output = run(
            self.smart_contract,
            "_order_stems_by_repayment_hierarchy",
            Mock(),
            txn_stems=["abc", "def", "ghi_a", "ghi_b", "ghi_c"],
            txn_hierarchy=transaction_hiererchy,
            txn_type_hierarchy=transaction_type_hierarchy,
        )
        self.assertEqual(expected_outcome, output)

    def test_is_between_pdd_and_scod_if_before_account_creation_date_plus_payment_due_period(
        self,
    ):
        is_between_pdd_and_scod = run(
            self.smart_contract,
            "_is_between_pdd_and_scod",
            Mock(),
            vault=self.create_mock(last_scod_execution_time=None),
            payment_due_period=22,
            account_creation_date=offset_datetime(2021, 10, 5, 10),
            current_date=offset_datetime(2021, 10, 6, 0, 0, 0),
        )

        self.assertEqual((False), (is_between_pdd_and_scod))

    def test_is_between_pdd_and_scod_if_after_account_creation_date_plus_payment_due_period(
        self,
    ):
        is_between_pdd_and_scod = run(
            self.smart_contract,
            "_is_between_pdd_and_scod",
            Mock(),
            vault=self.create_mock(last_scod_execution_time=None),
            payment_due_period=22,
            account_creation_date=offset_datetime(2021, 10, 5, 10),
            current_date=offset_datetime(2021, 11, 1, 0, 0, 0),
        )

        self.assertEqual((False), (is_between_pdd_and_scod))

    def test_is_between_pdd_and_scod_if_just_before_pdd_event(self):
        is_between_pdd_and_scod = run(
            self.smart_contract,
            "_is_between_pdd_and_scod",
            Mock(),
            vault=self.create_mock(last_scod_execution_time=datetime(2021, 12, 5, 0, 0, 2)),
            payment_due_period=22,
            account_creation_date=offset_datetime(2021, 10, 5, 10),
            current_date=offset_datetime(2021, 12, 26, 23, 59, 59),
        )

        self.assertEqual((False), (is_between_pdd_and_scod))

    def test_is_between_pdd_and_scod_if_just_after_pdd_event(self):
        is_between_pdd_and_scod = run(
            self.smart_contract,
            "_is_between_pdd_and_scod",
            Mock(),
            vault=self.create_mock(last_scod_execution_time=datetime(2021, 12, 5, 0, 0, 2)),
            payment_due_period=22,
            account_creation_date=offset_datetime(2021, 10, 5, 10),
            current_date=offset_datetime(2021, 12, 27, 0, 0, 3),
        )

        self.assertEqual((True), (is_between_pdd_and_scod))

    def test_is_between_pdd_and_scod_if_just_before_scod_event(self):
        is_between_pdd_and_scod = run(
            self.smart_contract,
            "_is_between_pdd_and_scod",
            Mock(),
            vault=self.create_mock(last_scod_execution_time=datetime(2021, 12, 5, 0, 0, 2)),
            payment_due_period=22,
            account_creation_date=offset_datetime(2021, 10, 5, 10),
            current_date=offset_datetime(2022, 1, 4, 23, 59, 59),
        )

        self.assertEqual((True), (is_between_pdd_and_scod))

    def test_is_between_pdd_and_scod_if_just_after_scod_event(self):
        is_between_pdd_and_scod = run(
            self.smart_contract,
            "_is_between_pdd_and_scod",
            Mock(),
            vault=self.create_mock(last_scod_execution_time=datetime(2022, 1, 5, 0, 0, 2)),
            payment_due_period=22,
            account_creation_date=offset_datetime(2021, 10, 5, 10),
            current_date=offset_datetime(2022, 1, 5, 0, 0, 3),
        )

        self.assertEqual((False), (is_between_pdd_and_scod))

    def test_get_txn_type_and_ref_from_address_ref(self):
        address = "BALANCE_TRANSFER_REF1_INTEREST_CHARGED"
        expected_outcome = ("BALANCE_TRANSFER", "REF1")
        output = run(
            self.smart_contract,
            "_get_txn_type_and_ref_from_address",
            Mock(),
            address=address,
            base_txn_types=["PURCHASE", "CASH_ADVANCE", "TRANSFER", "BALANCE_TRANSFER"],
            address_type="INTEREST_CHARGED",
        )

        self.assertEqual(expected_outcome, output)

    def test_get_txn_type_and_ref_from_address_ref_and_ifp(self):
        address = "BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"
        expected_outcome = ("BALANCE_TRANSFER", "REF1")
        output = run(
            self.smart_contract,
            "_get_txn_type_and_ref_from_address",
            Mock(),
            address=address,
            base_txn_types=["PURCHASE", "CASH_ADVANCE", "TRANSFER", "BALANCE_TRANSFER"],
            address_type="INTEREST_FREE_PERIOD_INTEREST_UNCHARGED",
        )

        self.assertEqual(expected_outcome, output)

    def test_get_txn_type_and_ref_from_address_post_scod_uncharged(self):
        address = "PURCHASE_INTEREST_POST_SCOD_UNCHARGED"
        expected_outcome = ("PURCHASE", None)
        output = run(
            self.smart_contract,
            "_get_txn_type_and_ref_from_address",
            Mock(),
            address=address,
            base_txn_types=["PURCHASE", "CASH_ADVANCE", "TRANSFER", "BALANCE_TRANSFER"],
            address_type="INTEREST_POST_SCOD_UNCHARGED",
        )

        self.assertEqual(expected_outcome, output)

    def test_get_txn_type_and_ref_from_address_ref_and_pre_scod_uncharged(self):
        address = "BALANCE_TRANSFER_REF1_INTEREST_PRE_SCOD_UNCHARGED"
        expected_outcome = ("BALANCE_TRANSFER", "REF1")
        output = run(
            self.smart_contract,
            "_get_txn_type_and_ref_from_address",
            Mock(),
            address=address,
            base_txn_types=["PURCHASE", "CASH_ADVANCE", "TRANSFER", "BALANCE_TRANSFER"],
            address_type="INTEREST_PRE_SCOD_UNCHARGED",
        )

        self.assertEqual(expected_outcome, output)


class ParameterMismatchTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_no_exception_with_consistent_parameters(self):
        mock_vault = self.create_mock_for_param_test()
        run(
            self.smart_contract,
            "_check_txn_type_parameter_configuration",
            mock_vault,
            vault=mock_vault,
            effective_timestamp=offset_datetime(2019, 1, 1),
        )
        # Expect no exception

    def test_no_exception_with_consistent_parameters_and_interest_on_fees(self):
        update = [
            ["base_interest_rates", {"fees": {}}],
            ["annual_percentage_rate", {"fees": {}}],
        ]
        mock_vault = self.create_mock_for_param_test(
            param_val_update=update, accrue_interest_on_unpaid_fees=True
        )
        run(
            self.smart_contract,
            "_check_txn_type_parameter_configuration",
            mock_vault,
            vault=mock_vault,
            effective_timestamp=offset_datetime(2019, 1, 1),
        )
        # Expect no exception

    def test_parameter_mismatch_txn_code_missing(self):
        """
        Check error raised if there's a transaction type missing in transaction code
        """
        remove = [["transaction_code_to_type_map", ["2"]]]
        mock_vault = self.create_mock_for_param_test(param_val_remove=remove)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn(
            "Mismatch between txn types: 'transaction_code_to_type_map'",
            str(ex.exception),
        )

    def test_parameter_mismatch_txn_code_extra(self):
        """
        Check error raised if there's an extra transaction code not in
        transaction_types
        """
        update = [["transaction_code_to_type_map", {"99": "X"}]]
        mock_vault = self.create_mock_for_param_test(param_val_update=update)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn(
            "Mismatch between txn types: 'transaction_code_to_type_map'",
            str(ex.exception),
        )

    def test_parameter_mismatch_minimum_percentage_due_includes_ref(self):
        remove = [["minimum_percentage_due", ["C"]]]
        mock_vault = self.create_mock_for_param_test(param_val_remove=remove)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn("Mismatch between txn types: 'minimum_percentage_due'", str(ex.exception))

    def test_parameter_mismatch_minimum_percentage_due_includes_fees(self):
        remove = [["minimum_percentage_due", ["fees"]]]
        mock_vault = self.create_mock_for_param_test(param_val_remove=remove)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn("Mismatch between txn types: 'minimum_percentage_due'", str(ex.exception))

    def test_parameter_mismatch_minimum_percentage_due_includes_interest(self):
        remove = [["minimum_percentage_due", ["interest"]]]
        mock_vault = self.create_mock_for_param_test(param_val_remove=remove)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn("Mismatch between txn types: 'minimum_percentage_due'", str(ex.exception))

    def test_parameter_mismatch_extra_reference_type(self):
        """
        Make sure there's an error if an extra reference type is included that
        isn't in "transaction_types"
        """
        update = [["transaction_references", {"D": {}}]]
        mock_vault = self.create_mock_for_param_test(param_val_update=update)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn("Types in transaction_references ", str(ex.exception))

    def test_parameter_mismatch_ref_also_at_type_level(self):
        """
        The transaction-type-level "annual_percentage_rate" and
        "base_interest_rates" should not include transaction types that use
        refs
        """
        update = [["annual_percentage_rate", {"C": {}}]]
        mock_vault = self.create_mock_for_param_test(param_val_update=update)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn("Mismatch between txn types: 'annual_percentage_rate'", str(ex.exception))

        update = [["base_interest_rates", {"C": {}}]]
        mock_vault = self.create_mock_for_param_test(param_val_update=update)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn("Mismatch between txn types: 'base_interest_rates'", str(ex.exception))

    def test_parameter_mismatch_fees_not_present_in_interest_rates(self):
        """
        If interest is charged on fees make sure there are interest rates set for it
        """
        update = [["annual_percentage_rate", {"fees": {}}]]
        mock_vault = self.create_mock_for_param_test(
            param_val_update=update, accrue_interest_on_unpaid_fees="True"
        )

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn("Mismatch between txn types: 'base_interest_rates'", str(ex.exception))

        update = [["base_interest_rates", {"fees": {}}]]
        mock_vault = self.create_mock_for_param_test(
            param_val_update=update, accrue_interest_on_unpaid_fees="True"
        )

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn("Mismatch between txn types: 'annual_percentage_rate'", str(ex.exception))

    def test_parameter_mismatch_extra_ref_level_interest_type(self):
        """
        Extra transaction type present in ref level interest rate parameters
        """
        update = [["transaction_annual_percentage_rate", {"E": {}}]]
        mock_vault = self.create_mock_for_param_test(param_val_update=update)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn(
            "Mismatch between txn types: 'transaction_annual_percentage_rate'",
            str(ex.exception),
        )

        update = [["transaction_base_interest_rates", {"F": {}}]]
        mock_vault = self.create_mock_for_param_test(param_val_update=update)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn(
            "Mismatch between txn types: 'transaction_base_interest_rates'",
            str(ex.exception),
        )

    def test_parameter_mismatch_missing_internal_accounts(self):
        """
        Test behaviour if missing types from internal accounts map an interest
        internal accounts map
        """
        remove = [["transaction_type_internal_accounts_map", ["C"]]]
        mock_vault = self.create_mock_for_param_test(param_val_remove=remove)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn(
            "Mismatch between txn types: 'transaction_type_internal_accounts_map'",
            str(ex.exception),
        )

        remove = [["transaction_type_interest_internal_accounts_map", ["A"]]]
        mock_vault = self.create_mock_for_param_test(param_val_remove=remove)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn(
            "Mismatch between txn types: 'transaction_type_interest_internal_accounts_map'",
            str(ex.exception),
        )

    def test_parameter_mismatch_extra_internal_accounts(self):
        """
        Test behaviour if extra type in internal accounts map and interest
        internal accounts map
        """
        update = [["transaction_type_internal_accounts_map", {"D": "1"}]]
        mock_vault = self.create_mock_for_param_test(param_val_update=update)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn(
            "Mismatch between txn types: 'transaction_type_internal_accounts_map'",
            str(ex.exception),
        )

        update = [["transaction_type_interest_internal_accounts_map", {"E": "1"}]]
        mock_vault = self.create_mock_for_param_test(param_val_update=update)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn(
            "Mismatch between txn types: 'transaction_type_interest_internal_accounts_map'",
            str(ex.exception),
        )

    def test_parameter_mismatch_extra_type_in_limits(self):
        """
        Make sure all types listed in "limits" are valid
        """
        update = [["transaction_type_limits", {"D": "1"}]]
        mock_vault = self.create_mock_for_param_test(param_val_update=update)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn("Types in transaction_type_limits", str(ex.exception))

    def test_parameter_mismatch_extra_type_in_fees(self):
        """
        Make sure all types listed in "fees" are valid
        """
        update = [["transaction_type_fees", {"D": "1"}]]
        mock_vault = self.create_mock_for_param_test(param_val_update=update)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn("Types in transaction_type_fees", str(ex.exception))

    def test_parameter_mismatch_fees_without_internal_account(self):
        """
        Make sure all types with a fee are also have an internal account
        """
        update = [["transaction_type_fees", {"B": "0.05"}]]
        mock_vault = self.create_mock_for_param_test(param_val_update=update)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn(
            " are not present in transaction_type_fees_internal_accounts_map",
            str(ex.exception),
        )

    def test_parameter_mismatch_ref_expiry_in_txn_expiry(self):
        """
        Make sure types in the type-level interest free expiry are not ref types
        """
        update = [["interest_free_expiry", {"C": "2020-11-09 10:00:00"}]]
        mock_vault = self.create_mock_for_param_test(param_val_update=update)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn(" in interest_free_expiry", str(ex.exception))

    def test_parameter_mismatch_txn_expiry_in_ref_expiry(self):
        """
        Make sure types in the ref level expiry are ref types
        """
        update = [["transaction_interest_free_expiry", {"B": "2020-11-09 10:00:00"}]]
        mock_vault = self.create_mock_for_param_test(param_val_update=update)

        with self.assertRaises(InvalidContractParameter) as ex:
            run(
                self.smart_contract,
                "_check_txn_type_parameter_configuration",
                mock_vault,
                vault=mock_vault,
                effective_timestamp=offset_datetime(2019, 1, 1),
            )

        self.assertIn(" in transaction_interest_free_expiry", str(ex.exception))


class PrePostingDenomAndAvailableBalanceTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_can_spend_in_denomination(self):
        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])
        credit_limit = Decimal("5000")

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase(amount="1000", denomination=DEFAULT_DENOM)]
        )

        mock_vault = self.create_mock(
            balance_ts=balances, denomination=DEFAULT_DENOM, credit_limit=credit_limit
        )

        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

    def test_cant_spend_in_unsupported_denomination(self):
        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])
        credit_limit = Decimal("5000")

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase(amount="1000", denomination="HKD")]
        )

        mock_vault = self.create_mock(
            balance_ts=balances, denomination=DEFAULT_DENOM, credit_limit=credit_limit
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Cannot make transactions in given denomination;" " transactions must be in GBP",
        )

    def test_cant_exceed_credit_limit_if_no_overlimit(self):
        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])
        credit_limit = Decimal("5000")

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase(amount="5001", denomination=DEFAULT_DENOM)]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            overlimit=Decimal(0),
            credit_limit=credit_limit,
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds GBP 5000 for GBP 5001 transaction (excl advice instructions)",
        )

    def test_cant_transact_if_available_balance_consumed_by_principal_and_no_overlimit(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "default", "net": "5000"},
                {"address": "purchase_charged", "net": "2000"},
                {"address": "cash_advance_billed", "net": "3000"},
            ]
        )
        credit_limit = Decimal("5000")

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase(amount="1", denomination=DEFAULT_DENOM)]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            overlimit=Decimal(0),
            credit_limit=credit_limit,
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds GBP 0 for GBP 1 transaction (excl advice instructions)",
        )

    def test_cant_transact_if_available_balance_consumed_by_fees_and_no_overlimit(self):
        balances = init_balances(
            balance_defs=[
                {"address": "default", "net": "5001"},
                {"address": "dispute_fees_charged", "net": "1000"},
                {"address": "cash_advance_fees_billed", "net": "2000"},
                {"address": "annual_fees_unpaid", "net": "2001"},
            ]
        )
        credit_limit = Decimal("5000")

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase(amount="1", denomination=DEFAULT_DENOM)]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            overlimit_opt_in="False",
            credit_limit=credit_limit,
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds GBP -1 for GBP 1 transaction (excl advice instructions)",
        )

    def test_cant_transact_if_available_balance_consumed_by_interest_and_no_overlimit(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "5001"},
                {"address": "purchase_interest_billed", "net": "2000"},
                {"address": "cash_advance_interest_unpaid", "net": "3001"},
            ]
        )
        credit_limit = Decimal("5000")

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase(amount="1", denomination=DEFAULT_DENOM)]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            overlimit_opt_in="False",
            credit_limit=credit_limit,
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds GBP -1 for GBP 1 transaction (excl advice instructions)",
        )

    def test_available_balance_not_consumed_by_charged_interest(self):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "50000"},
                {"address": "purchase_interest_charged", "net": "20000"},
                {"address": "cash_advance_interest_charged", "net": "30000"},
            ]
        )
        credit_limit = Decimal("10000")

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase(amount="5000", denomination=DEFAULT_DENOM)]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            overlimit_opt_in="False",
            credit_limit=credit_limit,
        )

        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

    def test_cant_transact_if_available_balance_consumed_by_auths_and_no_overlimit(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "default", "phase": Phase.PENDING_OUT, "net": "5000"},
                {"address": "purchase_auth", "net": "5000"},
            ]
        )
        credit_limit = Decimal("5000")

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase(amount="1", denomination=DEFAULT_DENOM)]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            overlimit=Decimal(0),
            credit_limit=credit_limit,
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds GBP 0 for GBP 1 transaction (excl advice instructions)",
        )

    def test_can_exceed_credit_limit_if_enough_deposit_exists(self):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "-2000"},
                {"address": "DEPOSIT", "net": "2000"},
            ]
        )
        credit_limit = Decimal("5000")

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase(amount="6000", denomination=DEFAULT_DENOM)]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            overlimit=Decimal(0),
            credit_limit=credit_limit,
        )

        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

    def test_can_exceed_credit_limit_if_within_overlimit_and_opted_in(self):
        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])
        credit_limit = Decimal("5000")
        overlimit_opt_in = "True"
        posting_instructions = [self.purchase(amount="5001", denomination=DEFAULT_DENOM)]

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            credit_limit=credit_limit,
            overlimit=Decimal(10),
            overlimit_opt_in=overlimit_opt_in,
        )
        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)
        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

    def test_cant_exceed_overlimit_if_opted_in(self):
        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])
        credit_limit = Decimal("5000")
        overlimit_opt_in = "True"
        posting_instructions = [self.purchase(amount="5011", denomination=DEFAULT_DENOM)]

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            credit_limit=credit_limit,
            overlimit=Decimal(10),
            overlimit_opt_in=overlimit_opt_in,
        )
        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds GBP 5010 for GBP 5011 transaction (excl advice instructions)",
        )

    def test_can_transact_if_not_in_overlimit_and_opted_in(self):
        balances = init_balances(balance_defs=[{"address": "default", "net": "5000"}])
        credit_limit = Decimal("5000")
        overlimit_opt_in = "True"

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.purchase(amount="1", denomination=DEFAULT_DENOM)]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            overlimit=Decimal(10),
            credit_limit=credit_limit,
            overlimit_opt_in=overlimit_opt_in,
        )

        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.assert_no_side_effects(mock_vault)

    def test_cant_transact_if_already_overlimit(self):
        balances = init_balances(
            balance_defs=[
                {"address": "default", "net": "5001"},
                {"address": "purchase_charged", "net": "1001"},
                {"address": "cash_advance_billed", "net": "1950"},
                {"address": "transfer_unpaid", "net": "2050"},
            ]
        )
        credit_limit = Decimal("5000")
        overlimit_opt_in = "True"
        posting_instructions = [self.purchase(amount="1", denomination=DEFAULT_DENOM)]

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            credit_limit=credit_limit,
            overlimit=Decimal(10),
            overlimit_opt_in=overlimit_opt_in,
        )
        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds for GBP 1 transaction. Overlimit already in use",
        )

    def test_can_transact_if_available_balance_consumed_by_interest_and_opted_in(self):
        balances = init_balances(
            balance_defs=[
                {"address": "default", "net": "5005"},
                {"address": "purchase_interest_billed", "net": "1305"},
                {"address": "cash_advance_fees_charged", "net": "3700"},
            ]
        )
        credit_limit = Decimal("5000")
        overlimit_opt_in = "True"
        posting_instructions = [self.purchase(amount="1", denomination=DEFAULT_DENOM)]

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            credit_limit=credit_limit,
            overlimit=Decimal(10),
            overlimit_opt_in=overlimit_opt_in,
        )
        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)

        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

    def test_cant_transact_if_available_balance_consumed_by_principal_and_charges(self):
        balances = init_balances(
            balance_defs=[
                {"address": "default", "net": "5050"},
                {"address": "purchase_charged", "net": "4000"},
                {"address": "purchase_interest_billed", "net": "350"},
                {"address": "cash_advance_fees_charged", "net": "700"},
            ]
        )
        credit_limit = Decimal("5000")
        overlimit_opt_in = "True"
        posting_instructions = [self.purchase(amount="1000", denomination=DEFAULT_DENOM)]

        mock_vault = self.create_mock(
            balance_ts=balances,
            denomination=DEFAULT_DENOM,
            credit_limit=credit_limit,
            overlimit=Decimal(10),
            overlimit_opt_in=overlimit_opt_in,
        )
        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds GBP -40 for GBP 1000 transaction (excl advice instructions)",
        )

    def test_balance_checks_with_txn_refs(self):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 25, 0, 0, 1),
            balance_defs=[{"address": "available_balance", "net": "2000"}],
        )

        amount1 = Decimal("100")
        amount2 = Decimal("200")

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.balance_transfer(amount=amount1, ref="REF1"),
                self.balance_transfer(amount=amount2, ref="ref2"),
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {},
                    "transfer": {},
                    "balance_transfer": {},
                }
            ),
            transaction_code_to_type_map=dumps(
                {
                    "01": "purchase",
                    "00": "cash_advance",
                    "02": "transfer",
                    "03": "balance_transfer",
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {"REF1": "0.2", "ref2": "0.25"}}
            ),
        )

        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

    def test_existing_txn_refs_prevent_txn(self):
        amount1 = Decimal("100")
        amount2 = Decimal("200")
        existing_ref = "REF1"
        new_ref = "REF2"
        txn_type = "balance_transfer"
        existing_stem = f"{txn_type}_{existing_ref.lower()}"

        balances = init_balances(
            dt=offset_datetime(2019, 2, 25, 0, 0, 1),
            balance_defs=[
                {"address": "available_balance", "net": "2000"},
                {"address": existing_stem + "_charged", "net": "0"},
            ],
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.balance_transfer(amount=amount1, ref=existing_ref),
                self.balance_transfer(amount=amount2, ref=new_ref),
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types=dumps(
                {"purchase": {}, "balance_transfer": {"transaction_level": "True"}}
            ),
            transaction_code_to_type_map=dumps(
                {
                    "01": "purchase",
                    "00": "cash_advance",
                    "02": "transfer",
                    "03": txn_type,
                }
            ),
            transaction_references=dumps({txn_type: [existing_ref, new_ref]}),
            transaction_annual_percentage_rate=dumps(
                {txn_type: {existing_ref: "0.2", new_ref: "0.25"}}
            ),
        )

        with self.assertRaises(Rejected) as context:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
            )

        self.assertEqual(
            f"{existing_ref} already in use for {txn_type}. Please select a unique reference.",
            str(context.exception),
        )

    def test_txn_types_missing_ref_are_rejected(self):
        amount = Decimal("100")
        existing_ref = "REF1"
        new_ref = "REF2"
        txn_type = "balance_transfer"

        balances = init_balances(
            dt=offset_datetime(2019, 2, 25, 0, 0, 1),
            balance_defs=[{"address": "available_balance", "net": "2000"}],
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.balance_transfer(amount=amount, ref=None)]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types=dumps({"purchase": {}, txn_type: {"transaction_level": "True"}}),
            transaction_code_to_type_map=dumps(
                {
                    "01": "purchase",
                    "00": "cash_advance",
                    "02": "transfer",
                    "03": txn_type,
                }
            ),
            transaction_references=dumps({txn_type: [existing_ref, new_ref]}),
            transaction_annual_percentage_rate=dumps(
                {txn_type: {existing_ref: "0.2", new_ref: "0.25"}}
            ),
        )

        with self.assertRaises(Rejected) as context:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
            )

        self.assertEqual(
            f"Transaction type {txn_type} requires a transaction level reference and none has been "
            f"specified.",
            str(context.exception),
        )

    def test_txn_types_with_undefined_ref(self):
        amount = Decimal("100")
        txn_ref = "REF2"
        txn_type = "balance_transfer"

        balances = init_balances(
            dt=offset_datetime(2019, 2, 25, 0, 0, 1),
            balance_defs=[{"address": "available_balance", "net": "2000"}],
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.balance_transfer(amount=amount, ref=txn_ref)]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types=dumps({"purchase": {}, txn_type: {"transaction_level": "True"}}),
            transaction_code_to_type_map=dumps(
                {
                    "01": "purchase",
                    "00": "cash_advance",
                    "02": "transfer",
                    "03": txn_type,
                }
            ),
            transaction_references=dumps({txn_type: ["REF1"]}),
            transaction_annual_percentage_rate=dumps({txn_type: {"REF1": "0.2"}}),
        )

        with self.assertRaises(Rejected) as context:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
            )

        self.assertEqual(
            f"{txn_ref} undefined in parameters for {txn_type}. Please update parameters.",
            str(context.exception),
        )

    def test_txn_types_with_blank_txn_ref(self):
        amount = Decimal("100")
        txn_ref = "REF1"
        txn_type = "balance_transfer"

        balances = init_balances(
            dt=offset_datetime(2019, 2, 25, 0, 0, 1),
            balance_defs=[{"address": "available_balance", "net": "2000"}],
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.balance_transfer(amount=amount, ref=txn_ref)]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types=dumps({"purchase": {}, txn_type: {"transaction_level": "True"}}),
            transaction_code_to_type_map=dumps(
                {
                    "01": "purchase",
                    "00": "cash_advance",
                    "02": "transfer",
                    "03": txn_type,
                }
            ),
            transaction_references=dumps({txn_type: []}),
            transaction_annual_percentage_rate=dumps({txn_type: {"REF1": "0.2"}}),
        )

        with self.assertRaises(Rejected) as context:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
            )

        self.assertEqual(
            f"{txn_ref} undefined in parameters for {txn_type}. Please update parameters.",
            str(context.exception),
        )


class PrePostingOfflineTransactionTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_batch_with_multiple_instructions_rejected_if_non_advice_total_gt_available(
        self,
    ):
        available_balance = Decimal("3000")
        credit_limit = Decimal("5000")

        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "2000"},
                {"address": "PURCHASE_CHARGED", "net": "2000"},
            ]
        )

        posting_instructions = [
            self.mock_posting_instruction(amount=Decimal("2000"), advice=False),
            self.mock_posting_instruction(amount=Decimal("2000"), advice=False),
            self.mock_posting_instruction(amount=Decimal("1000"), advice=True),
        ]
        available_balance_delta = sum(
            [posting.amount for posting in posting_instructions if not posting.advice]
        )

        mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)

        with self.assertRaises(Rejected) as context:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        # If both postings were considered the total debit would be 2000
        self.assertEqual(
            f"Insufficient funds GBP {available_balance} for GBP"
            f" {available_balance_delta} transaction (excl advice instructions)",
            str(context.exception),
        )

    def test_instruction_with_true_advice_flag_bypasses_balance_checks(self):
        available_balance = Decimal("3000")
        credit_limit = Decimal("5000")

        balances = init_balances(
            balance_defs=[{"address": "default", "net": available_balance - credit_limit}]
        )

        posting_instruction = self.mock_posting_instruction(amount=Decimal(1000), advice=True)

        mock_vault = self.create_mock(balance_ts=balances)

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[posting_instruction],
        )

        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

    def test_batch_with_multiple_instructions_accepted_if_non_advice_total_lt_available(
        self,
    ):
        available_balance = Decimal("3000")
        credit_limit = Decimal("5000")

        balances = init_balances(
            balance_defs=[{"address": "default", "net": available_balance - credit_limit}]
        )

        posting_instructions = [
            self.mock_posting_instruction(amount=Decimal("1000"), advice=False),
            self.mock_posting_instruction(amount=Decimal("1000"), advice=False),
            self.mock_posting_instruction(amount=Decimal("1000"), advice=True),
        ]

        mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

        pib = self.mock_posting_instruction_batch(posting_instructions=posting_instructions)

        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )


class PrePostingTxnTypeCreditLimitTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_cant_exceed_txn_type_credit_limit_in_single_transaction(self):
        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.cash_advance(amount="1000")]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps(
                {"cash_advance": {"flat": "200"}, "purchase": {"flat": "200"}}
            ),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds for GBP 1000 transaction due to GBP 200.00 limit on "
            "transaction type cash_advance. Outstanding transactions amount to GBP"
            " 0",
        )

    def test_txn_type_credit_limits_do_not_impact_other_txn_types(self):

        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.cash_advance(amount="1000")]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps({"purchase": {"flat": "200"}}),
        )

        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

    def test_percentage_txn_type_limit_used_if_lower_than_flat_limit(self):

        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.cash_advance(amount="1000")]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps({"cash_advance": {"flat": "200", "percentage": "0.1"}}),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds for GBP 1000 transaction due to GBP 100.00 limit on "
            "transaction type cash_advance. Outstanding transactions amount to GBP"
            " 0",
        )

    def test_flat_txn_type_limit_used_if_lower_than_percentage_limit(self):

        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.cash_advance(amount="1000")]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps({"cash_advance": {"flat": "200", "percentage": "0.3"}}),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds for GBP 1000 transaction due to GBP 200.00 limit on "
            "transaction type cash_advance. Outstanding transactions amount to GBP"
            " 0",
        )

    def test_flat_txn_type_limit_used_if_percentage_limit_not_specified(self):

        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.cash_advance(amount="1000")]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps({"cash_advance": {"flat": "200"}}),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds for GBP 1000 transaction due to GBP 200.00 limit on "
            "transaction type cash_advance. Outstanding transactions amount to GBP"
            " 0",
        )

    def test_percentage_txn_type_limit_used_if_flat_limit_not_specified(self):

        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.cash_advance(amount="1000")]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps({"cash_advance": {"percentage": "0.4"}}),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds for GBP 1000 transaction due to GBP 400.00 limit on "
            "transaction type cash_advance. Outstanding transactions amount to GBP"
            " 0",
        )

    def test_cant_exceed_txn_type_credit_limit_with_multiple_transactions_in_batch(
        self,
    ):
        balances = init_balances(balance_defs=[{"address": AVAILABLE, "net": "5000"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.cash_advance(amount="150"),
                self.cash_advance(amount="100"),
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps({"cash_advance": {"flat": "200"}}),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds for GBP 250 transaction due to GBP 200.00 limit on "
            "transaction type cash_advance. Outstanding transactions amount to GBP"
            " 0",
        )

    def test_cant_exceed_txn_type_credit_limit_for_multiple_txn_in_a_statement(self):
        balances = init_balances(
            balance_defs=[
                {"address": "available_balance", "net": "5000"},
                {"address": "cash_advance_charged", "net": "100"},
            ]
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.cash_advance(amount="150")]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps({"cash_advance": {"flat": "200"}}),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds for GBP 150 transaction due to GBP 200.00 limit on "
            "transaction type cash_advance. Outstanding transactions amount to GBP"
            " 100",
        )

    def test_cant_exceed_txn_type_credit_limit_for_multiple_txn_across_statements(self):
        balances = init_balances(
            balance_defs=[
                {"address": "available_balance", "net": "5000"},
                {"address": "cash_advance_charged", "net": "10"},
                {"address": "cash_advance_billed", "net": "30"},
                {"address": "cash_advance_unpaid", "net": "20"},
            ]
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.cash_advance(amount="150")]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps({"cash_advance": {"flat": "200"}}),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds for GBP 150 transaction due to GBP 200.00 limit on "
            "transaction type cash_advance. Outstanding transactions amount to GBP"
            " 60",
        )

    def test_cant_exceed_txn_type_credit_limit_and_first_exceeding_txn_type_is_reported(
        self,
    ):
        """
        Test that transaction type limits are enforced when a batch contains multiple transactions
        of multiple types and the first transaction type in the posting batch is the one reported
        in the rejection reason
        """
        balances = init_balances(balance_defs=[{"address": AVAILABLE, "net": "5000"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.cash_advance(amount="150"),
                self.purchase(amount="150"),
                self.cash_advance(amount="150"),
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps(
                {"cash_advance": {"flat": "200"}, "purchase": {"flat": "200"}}
            ),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds for GBP 300 transaction due to GBP 200.00 limit on "
            "transaction type cash_advance. Outstanding transactions amount to GBP"
            " 0",
        )

    def test_can_exceed_txn_type_credit_limit_if_advice_flag_is_set_on_exceeding_txn(
        self,
    ):
        balances = init_balances(balance_defs=[{"address": AVAILABLE, "net": "5000"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.cash_advance(amount="250", advice=True)]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps(
                {"cash_advance": {"flat": "200"}, "purchase": {"flat": "200"}}
            ),
        )

        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

    def test_cant_exceed_txn_type_credit_limit_if_advice_flag_not_set_on_exceeding_txn(
        self,
    ):
        balances = init_balances(balance_defs=[{"address": AVAILABLE, "net": "5000"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.cash_advance(amount="250", advice=True),
                self.cash_advance(amount="250", advice=False),
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps(
                {"cash_advance": {"flat": "200"}, "purchase": {"flat": "200"}}
            ),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds for GBP 250 transaction due to GBP 200.00 limit on "
            "transaction type cash_advance. Outstanding transactions amount to GBP"
            " 0",
        )

    def test_cant_exceed_txn_type_credit_limit_when_overall_batch_is_a_credit(self):
        balances = init_balances(balance_defs=[{"address": AVAILABLE, "net": "5000"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.cash_advance(amount="150"),
                self.repay(amount="200"),
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps(
                {"cash_advance": {"flat": "100"}, "purchase": {"flat": "200"}}
            ),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds for GBP 150 transaction due to GBP 100.00 limit on "
            "transaction type cash_advance. Outstanding transactions amount to GBP"
            " 0",
        )

    def test_txn_type_credit_limit_has_no_effect_if_empty_dict_passed_in(self):
        balances = init_balances(balance_defs=[{"address": AVAILABLE, "net": "5000"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.cash_advance(amount="150"),
                self.repay(amount="200"),
            ]
        )

        mock_vault = self.create_mock(balance_ts=balances, transaction_type_limits="{}")

        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

    def test_cant_exceed_txn_type_credit_limits_with_txn_level(self):
        """
        Test that transaction type limits are enforced when a batch contains transactions including
        transaction level types and the first transaction type in the posting batch is the one
        reported in the rejection reason.
        """
        balances = init_balances(
            balance_defs=[
                {"address": "available_balance", "net": "5000"},
                {"address": "balance_transfer_ref1_charged", "net": "10"},
                {"address": "balance_transfer_ref2_billed", "net": "30"},
            ]
        )
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.balance_transfer(amount="80", ref="REF3")]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_type_limits=dumps({"balance_transfer": {"flat": "100"}}),
            transaction_types=dumps({"balance_transfer": {}}),
            transaction_code_to_type_map=dumps({"03": "balance_transfer"}),
            transaction_references=dumps({"balance_transfer": ["REF1", "REF2", "REF3"]}),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(ex.exception),
            "Insufficient funds for GBP 80 transaction due to GBP 100.00 limit on "
            "transaction type balance_transfer. Outstanding transactions amount to GBP"
            " 40",
        )

    def test_time_limited_txn_outside_window(self):
        """
        Test a balance transfer is rejected if outside the configured window
        """
        balances = init_balances(balance_defs=[{"address": "available_balance", "net": "5000"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.balance_transfer(amount="1000", ref="REF1")]
        )
        window = 14

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_code_to_type_map=dumps({"03": "balance_transfer"}),
            transaction_references=dumps({"balance_transfer": ["REF1", "REF2", "REF3"]}),
            transaction_type_limits=dumps(
                {
                    "cash_advance": {"flat": "200", "percentage": "0.1"},
                    "balance_transfer": {"allowed_days_after_opening": str(window)},
                }
            ),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE + timedelta(days=window),
            )

        self.assertEqual(
            str(ex.exception),
            "Transaction not permitted outside of configured window "
            f"{window} days from account opening",
        )

    def test_time_limited_txn_inside_window(self):
        """
        Test a balance transfer is allowed inside the configured window
        """
        balances = init_balances(balance_defs=[{"address": "available_balance", "net": "5000"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.balance_transfer(amount="1000", ref="REF1")]
        )
        window = 14

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_code_to_type_map=dumps({"03": "balance_transfer"}),
            transaction_references=dumps({"balance_transfer": ["REF1", "REF2", "REF3"]}),
            transaction_type_limits=dumps(
                {
                    "cash_advance": {"flat": "200", "percentage": "0.1"},
                    "balance_transfer": {"allowed_days_after_opening": str(window)},
                }
            ),
        )

        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE + timedelta(days=window, microseconds=-1),
        )

        # No exception raised

    def test_time_limited_txn_zero_window(self):
        """
        Test a balance transfer is rejected with zero window, checks for None/zero confusion
        """
        balances = init_balances(balance_defs=[{"address": "available_balance", "net": "5000"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.balance_transfer(amount="1000", ref="REF1")]
        )
        window = 0

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_code_to_type_map=dumps({"03": "balance_transfer"}),
            transaction_references=dumps({"balance_transfer": ["REF1", "REF2", "REF3"]}),
            transaction_type_limits=dumps(
                {
                    "cash_advance": {"flat": "200", "percentage": "0.1"},
                    "balance_transfer": {"allowed_days_after_opening": str(window)},
                }
            ),
        )

        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE + timedelta(days=window),
            )

        self.assertEqual(
            str(ex.exception),
            "Transaction not permitted outside of configured window "
            f"{window} days from account opening",
        )

    def test_multiple_txn_type_limits(self):
        """
        Ensure empty txn type limits doesn't cause a problem with time limit txn code
        """
        balances = init_balances(balance_defs=[{"address": "available_balance", "net": "5000"}])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.balance_transfer(amount="1000", ref="REF1")]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_code_to_type_map=dumps({"03": "balance_transfer"}),
            transaction_references=dumps({"balance_transfer": ["REF1", "REF2", "REF3"]}),
            transaction_type_limits=dumps({}),
        )

        run(
            self.smart_contract,
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        # No exception raised


class CloseCodeTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_close_code_fails_if_full_outstanding_balance_isnt_zero(self):
        balances = init_balances(
            balance_defs=[{"address": "full_outstanding_balance", "net": "1000"}]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts={"ACCOUNT_CLOSURE_REQUESTED": [(DEFAULT_DATE, True)]},
        )
        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "close_code",
                mock_vault,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(str(ex.exception), "Full Outstanding Balance is not zero")

    def test_close_code_fails_if_no_account_closure_flags_present(self):
        balances = init_balances(
            balance_defs=[{"full_outstanding_balance": "default", "net": "1000"}]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts=[],
        )
        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "close_code",
                mock_vault,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(str(ex.exception), "No account closure or write-off flags on the account")

    def test_close_code_fails_if_account_closure_flags_effective_after_closure(self):
        balances = init_balances(
            balance_defs=[{"address": "full_outstanding_balance", "net": "1000"}]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts={"ACCOUNT_CLOSURE_REQUESTED": [(DEFAULT_DATE + timedelta(hours=1), True)]},
        )
        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "close_code",
                mock_vault,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(str(ex.exception), "No account closure or write-off flags on the account")

    def test_close_code_fails_if_there_are_pending_authorisations(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_auth", "net": "10"},
                {"address": "cash_advance_auth", "net": "10"},
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts={"ACCOUNT_CLOSURE_REQUESTED": [(DEFAULT_DATE, True)]},
        )
        with self.assertRaises(Rejected) as ex:
            run(
                self.smart_contract,
                "close_code",
                mock_vault,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(str(ex.exception), "Outstanding authorisations on the account")

    def test_write_off_doesnt_fail_if_there_are_pending_authorisations(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_auth", "net": "10"},
                {"address": "cash_advance_auth", "net": "10"},
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)

    def test_write_off_doesnt_fail_if_there_is_full_outstanding_balance(self):
        balances = init_balances(
            balance_defs=[{"full_outstanding_balance": "default", "net": "10"}]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )
        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)

    def test_close_code_write_off_flag_takes_precedence(self):
        balances = init_balances(
            balance_defs=[{"full_outstanding_balance": "default", "net": "10"}]
        )

        # if account closure took precedence, this would throw an exception due to non-zero balance
        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts={
                "150_DPD": [(DEFAULT_DATE, True)],
                "ACCOUNT_CLOSURE_REQUESTED": [(DEFAULT_DATE, True)],
            },
        )
        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)

    def test_write_off_triggers_write_off_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "28"},
                {"address": "purchase_charged", "net": "1"},
                {"address": "purchase_unpaid", "net": "2"},
                {"address": "cash_advance_billed", "net": "3"},
                {"address": "cash_advance_fees_billed", "net": "4"},
                {"address": "overlimit_fees_charged", "net": "5"},
                {"address": "cash_advance_interest_unpaid", "net": "6"},
                {"address": "purchase_interest_billed", "net": "7"},
            ]
        )

        expected_calls = [principal_write_off_call("15"), interest_write_off_call("13")]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_write_off_with_no_interest_doesnt_trigger_interest_write_off_postings(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "1"},
                {"address": "purchase_charged", "net": "1"},
            ]
        )

        expected_calls = [principal_write_off_call("1")]
        unexpected_calls = [interest_write_off_call(ANY)]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_write_off_with_no_principal_doesnt_trigger_principal_write_off_postings(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "1"},
                {"address": "purchase_interest_billed", "net": "1"},
            ]
        )

        expected_calls = [interest_write_off_call("1")]
        unexpected_calls = [principal_write_off_call(ANY)]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_write_off_repayments_follow_hierarchy(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "361"},
                {"address": "outstanding_balance", "net": "329"},
                {"address": "purchase_charged", "net": "10"},
                {"address": "purchase_billed", "net": "11"},
                {"address": "purchase_unpaid", "net": "12"},
                {"address": "purchase_interest_charged", "net": "13"},
                {"address": "purchase_interest_billed", "net": "14"},
                {"address": "purchase_interest_unpaid", "net": "15"},
                {"address": "cash_advance_charged", "net": "16"},
                {"address": "cash_advance_billed", "net": "17"},
                {"address": "cash_advance_unpaid", "net": "18"},
                {"address": "cash_advance_interest_charged", "net": "19"},
                {"address": "cash_advance_interest_billed", "net": "20"},
                {"address": "cash_advance_interest_unpaid", "net": "21"},
                {"address": "cash_advance_fees_charged", "net": "22"},
                {"address": "overlimit_fees_charged", "net": "23"},
                {"address": "cash_advance_fees_billed", "net": "24"},
                {"address": "purchase_fees_billed", "net": "25"},
                {"address": "late_repayment_fees_billed", "net": "26"},
                {"address": "annual_fees_unpaid", "net": "27"},
                {"address": "overlimit_fees_unpaid", "net": "28"},
            ]
        )

        expected_calls = [
            repayment_rebalancing_call(
                amount="21",
                to_address="CASH_ADVANCE_INTEREST_UNPAID",
                posting_id="write_off_0",
                repay_count=0,
            ),
            repayment_rebalancing_call(
                amount="15",
                to_address="PURCHASE_INTEREST_UNPAID",
                posting_id="write_off_0",
                repay_count=1,
            ),
            repayment_rebalancing_call(
                amount="20",
                to_address="CASH_ADVANCE_INTEREST_BILLED",
                posting_id="write_off_0",
                repay_count=2,
            ),
            repayment_rebalancing_call(
                amount="14",
                to_address="PURCHASE_INTEREST_BILLED",
                posting_id="write_off_0",
                repay_count=3,
            ),
            repayment_rebalancing_call(
                amount="27",
                to_address="ANNUAL_FEES_UNPAID",
                posting_id="write_off_0",
                repay_count=4,
            ),
            repayment_rebalancing_call(
                amount="28",
                to_address="OVERLIMIT_FEES_UNPAID",
                posting_id="write_off_0",
                repay_count=5,
            ),
            repayment_rebalancing_call(
                amount="24",
                to_address="CASH_ADVANCE_FEES_BILLED",
                posting_id="write_off_0",
                repay_count=6,
            ),
            repayment_rebalancing_call(
                amount="26",
                to_address="LATE_REPAYMENT_FEES_BILLED",
                posting_id="write_off_0",
                repay_count=7,
            ),
            repayment_rebalancing_call(
                amount="25",
                to_address="PURCHASE_FEES_BILLED",
                posting_id="write_off_0",
                repay_count=8,
            ),
            repayment_rebalancing_call(
                amount="18",
                to_address="CASH_ADVANCE_UNPAID",
                posting_id="write_off_0",
                repay_count=9,
            ),
            repayment_rebalancing_call(
                amount="17",
                to_address="CASH_ADVANCE_BILLED",
                posting_id="write_off_0",
                repay_count=10,
            ),
            repayment_rebalancing_call(
                amount="12",
                to_address="PURCHASE_UNPAID",
                posting_id="write_off_0",
                repay_count=11,
            ),
            repayment_rebalancing_call(
                amount="11",
                to_address="PURCHASE_BILLED",
                posting_id="write_off_0",
                repay_count=12,
            ),
            # Cash advance charged is split in two because we're processing two repayments
            repayment_rebalancing_call(
                amount="1",
                to_address="CASH_ADVANCE_CHARGED",
                posting_id="write_off_0",
                repay_count=13,
            ),
            repayment_rebalancing_call(
                amount="15",
                to_address="CASH_ADVANCE_CHARGED",
                posting_id="write_off_1",
                repay_count=0,
            ),
            repayment_rebalancing_call(
                amount="10",
                to_address="PURCHASE_CHARGED",
                posting_id="write_off_1",
                repay_count=1,
            ),
            repayment_rebalancing_call(
                amount="19",
                to_address="CASH_ADVANCE_INTEREST_CHARGED",
                posting_id="write_off_1",
                repay_count=2,
            ),
            repayment_rebalancing_call(
                amount="13",
                to_address="PURCHASE_INTEREST_CHARGED",
                posting_id="write_off_1",
                repay_count=3,
            ),
            repayment_rebalancing_call(
                amount="22",
                to_address="CASH_ADVANCE_FEES_CHARGED",
                posting_id="write_off_1",
                repay_count=4,
            ),
            repayment_rebalancing_call(
                amount="23",
                to_address="OVERLIMIT_FEES_CHARGED",
                posting_id="write_off_1",
                repay_count=5,
            ),
        ]

        # if account closure took precedence, this would throw an exception due to non-zero balance
        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
            transaction_type_fees_internal_accounts_map=dumps(
                {
                    "cash_advance": {
                        "loan": "cash_advance_fee_loan_internal_account",
                        "income": "cash_advance_fee_income_internal_account",
                    },
                    "purchase": {
                        "loan": "purchase_fee_loan_internal_account",
                        "income": "purchase_fee_income_internal_account",
                    },
                }
            ),
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=False
        )

    def test_write_off_repayments_update_outstanding_balance(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "3"},
                {"address": "outstanding_balance", "net": "1"},
                {"address": "purchase_interest_charged", "net": "2"},
                {"address": "cash_advance_fees_billed", "net": "1"},
            ]
        )

        expected_calls = [
            internal_to_address_call(credit=True, amount=1, address=OUTSTANDING),
            internal_to_address_call(credit=True, amount=3, address=FULL_OUTSTANDING),
        ]

        # if account closure took precedence, this would throw an exception due to non-zero balance
        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=False
        )

    def test_write_off_repayments_updates_and_clears_total_repayments(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "3"},
                {"address": "outstanding_balance", "net": "1"},
                {"address": "purchase_interest_charged", "net": "2"},
                {"address": "cash_advance_fees_billed", "net": "1"},
            ]
        )

        expected_calls = [
            internal_to_address_call(
                credit=False, amount=2, address=TOTAL_REPAYMENTS_LAST_STATEMENT
            ),
            internal_to_address_call(
                credit=False, amount=1, address=TOTAL_REPAYMENTS_LAST_STATEMENT
            ),
            internal_to_address_call(
                credit=True, amount=3, address=TOTAL_REPAYMENTS_LAST_STATEMENT
            ),
        ]

        # if account closure took precedence, this would throw an exception due to non-zero balance
        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=False
        )

    def test_write_off_repayments_update_and_clear_available_balance(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "3"},
                {"address": "outstanding_balance", "net": "1"},
                {"address": "purchase_interest_charged", "net": "2"},
                {"address": "cash_advance_fees_billed", "net": "1"},
                {"address": "available_balance", "net": "999"},
            ]
        )

        expected_calls = [
            # Repayment/write-off of billed fees increases available by 1
            internal_to_address_call(credit=False, amount=1, address=AVAILABLE),
            # Account closure reduces available to 0
            internal_to_address_call(credit=True, amount=1000, address=AVAILABLE),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=False
        )

    def test_write_off_generic_fees_triggers_gl_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "3"},
                {"address": "overlimit_fees_charged", "net": "1"},
                {"address": "annual_fees_billed", "net": "2"},
            ]
        )

        expected_calls = [
            repay_charged_fee_customer_to_loan_call(
                amount="2",
                fee_type="ANNUAL_FEE",
                posting_id="write_off_0",
                repay_count=0,
            ),
            repay_charged_fee_customer_to_loan_call(
                amount="1",
                fee_type="OVERLIMIT_FEE",
                posting_id="write_off_0",
                repay_count=1,
            ),
            repay_charged_fee_off_bs_call(
                amount="2",
                fee_type="ANNUAL_FEE",
                posting_id="write_off_0",
                repay_count=0,
            ),
            repay_charged_fee_off_bs_call(
                amount="1",
                fee_type="OVERLIMIT_FEE",
                posting_id="write_off_0",
                repay_count=1,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_write_off_extra_limit_generic_fees_triggers_gl_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "2200"},
                {"address": "overlimit_fees_charged", "net": "1200"},
                {"address": "annual_fees_billed", "net": "1000"},
            ]
        )

        expected_calls = [
            repay_charged_fee_customer_to_loan_call(
                amount="1000",
                fee_type="ANNUAL_FEE",
                posting_id="write_off_0",
                repay_count=0,
            ),
            repay_charged_fee_customer_to_loan_call(
                amount="1200",
                fee_type="OVERLIMIT_FEE",
                posting_id="write_off_0",
                repay_count=1,
            ),
            repay_charged_fee_off_bs_call(
                amount="1000",
                fee_type="OVERLIMIT_FEE",
                posting_id="write_off_0",
                repay_count=1,
            ),
        ]

        unexpected_calls = [
            repay_charged_fee_off_bs_call(
                amount=ANY,
                fee_type="ANNUAL_FEE",
                posting_id="write_off_0",
                repay_count=0,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault,
            expected_calls=expected_calls,
            unexpected_calls=unexpected_calls,
            exact_order=True,
        )

    def test_write_off_txn_type_fees_triggers_gl_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "3"},
                {"address": "cash_advance_fees_charged", "net": "1"},
                {"address": "transfer_fees_billed", "net": "2"},
            ]
        )

        expected_calls = [
            repay_charged_fee_customer_to_loan_call(
                amount="2",
                fee_type="TRANSFER_FEE",
                posting_id="write_off_0",
                repay_count=0,
            ),
            repay_charged_fee_customer_to_loan_call(
                amount="1",
                fee_type="CASH_ADVANCE_FEE",
                posting_id="write_off_0",
                repay_count=1,
            ),
            repay_charged_fee_off_bs_call(
                amount="2",
                fee_type="TRANSFER_FEE",
                posting_id="write_off_0",
                repay_count=0,
            ),
            repay_charged_fee_off_bs_call(
                amount="1",
                fee_type="CASH_ADVANCE_FEE",
                posting_id="write_off_0",
                repay_count=1,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
            transaction_type_fees_internal_accounts_map=dumps(
                {
                    "transfer": {
                        "loan": "transfer_fee_loan_internal_account",
                        "income": "transfer_fee_income_internal_account",
                    },
                    "cash_advance": {
                        "loan": "cash_advance_fee_loan_internal_account",
                        "income": "cash_advance_fee_income_internal_account",
                    },
                }
            ),
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=False
        )

    def test_write_off_principal_triggers_gl_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "3"},
                {"address": "cash_advance_unpaid", "net": "1"},
                {"address": "purchase_billed", "net": "2"},
            ]
        )

        expected_calls = [
            repay_principal_revocable_commitment_call(
                amount="1",
                posting_id="write_off_0",
                repay_count=0,
                txn_type="cash_advance",
            ),
            repay_principal_revocable_commitment_call(
                amount="2", posting_id="write_off_0", repay_count=1, txn_type="purchase"
            ),
            repay_principal_loan_gl_call(
                amount="1",
                posting_id="write_off_0",
                repay_count=0,
                txn_type="cash_advance",
            ),
            repay_principal_loan_gl_call(
                amount="2", posting_id="write_off_0", repay_count=1, txn_type="purchase"
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=False
        )

    def test_write_off_extra_limit_principal_triggers_gl_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "2200"},
                {"address": "cash_advance_unpaid", "net": "1000"},
                {"address": "purchase_billed", "net": "1200"},
            ]
        )

        expected_calls = [
            repay_principal_loan_gl_call(
                amount="1000",
                posting_id="write_off_0",
                repay_count=0,
                txn_type="cash_advance",
            ),
            repay_principal_loan_gl_call(
                amount="1200",
                posting_id="write_off_0",
                repay_count=1,
                txn_type="purchase",
            ),
            repay_principal_revocable_commitment_call(
                amount="1000",
                posting_id="write_off_0",
                repay_count=1,
                txn_type="purchase",
            ),
        ]

        unexpected_calls = [
            repay_principal_revocable_commitment_call(
                amount=ANY,
                posting_id="write_off_0",
                repay_count=0,
                txn_type="cash_advance",
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_write_off_billed_or_unpaid_interest_triggers_gl_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "3"},
                {"address": "cash_advance_interest_unpaid", "net": "1"},
                {"address": "purchase_interest_billed", "net": "2"},
            ]
        )

        expected_calls = [
            repay_billed_interest_customer_to_loan_call(
                amount="1",
                posting_id="write_off_0",
                repay_count=0,
                txn_type="cash_advance",
            ),
            repay_billed_interest_customer_to_loan_call(
                amount="2", posting_id="write_off_0", repay_count=1, txn_type="purchase"
            ),
            repay_billed_interest_off_bs_call(
                amount="1",
                posting_id="write_off_0",
                repay_count=0,
                txn_type="cash_advance",
            ),
            repay_billed_interest_off_bs_call(
                amount="2", posting_id="write_off_0", repay_count=1, txn_type="purchase"
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=False
        )

    def test_write_off_extra_limit_billed_or_unpaid_interest_triggers_gl_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "2200"},
                {"address": "cash_advance_interest_unpaid", "net": "1000"},
                {"address": "purchase_interest_billed", "net": "1200"},
            ]
        )

        expected_calls = [
            repay_billed_interest_customer_to_loan_call(
                amount="1000",
                posting_id="write_off_0",
                repay_count=0,
                txn_type="cash_advance",
            ),
            repay_billed_interest_customer_to_loan_call(
                amount="1200",
                posting_id="write_off_0",
                repay_count=1,
                txn_type="purchase",
            ),
            repay_billed_interest_off_bs_call(
                amount="1000",
                posting_id="write_off_0",
                repay_count=1,
                txn_type="purchase",
            ),
        ]

        unexpected_calls = [
            repay_billed_interest_off_bs_call(
                amount=ANY,
                posting_id="write_off_0",
                repay_count=0,
                txn_type="cash_advance",
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_write_off_charged_interest_triggers_gl_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "3"},
                {"address": "cash_advance_interest_charged", "net": "1"},
                {"address": "purchase_interest_charged", "net": "2"},
            ]
        )

        expected_calls = [
            repay_charged_interest_gl_call(
                amount="1",
                txn_type="cash_advance",
                posting_id="write_off_0",
                repay_count=0,
            ),
            repay_charged_interest_gl_call(
                amount="2", txn_type="purchase", posting_id="write_off_0", repay_count=1
            ),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=False
        )

    def test_write_off_external_fees_triggers_gl_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "full_outstanding_balance", "net": "3"},
                {"address": "dispute_fees_unpaid", "net": "1"},
            ]
        )

        expected_calls = [
            repay_charged_dispute_fee_customer_to_loan_gl_call(
                amount="1", posting_id="write_off_0", repay_count=0
            ),
            repay_charged_fee_off_bs_call(
                amount="1",
                posting_id="write_off_0",
                fee_type="DISPUTE_FEE",
                repay_count=0,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_write_off_flags='["150_DPD"]',
            flags_ts={"150_DPD": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)
        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_order=False
        )

    def test_final_statement_generated_in_closed_code_if_account_can_be_closed(self):
        balances = init_balances()
        closure_date = DEFAULT_DATE - timedelta(hours=0)
        expected_calls = [
            publish_statement_workflow_call(
                mad="0.00",
                end_of_statement=str((closure_date + timedelta(hours=LOCAL_UTC_OFFSET)).date()),
                statement_amount="0.00",
                current_pdd="",
                next_pdd="",
                next_scod="",
                is_final="True",
            )
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts={"ACCOUNT_CLOSURE_REQUESTED": [(closure_date, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=closure_date)

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_previous_statement_snapshot_balances_zeroed_out_when_generating_final_statement(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "statement_balance", "net": "1000"},
                {"address": "mad_balance", "net": "100"},
            ]
        )
        expected_calls = [
            internal_to_address_call(credit=True, amount="100", address="MAD_BALANCE"),
            internal_to_address_call(credit=True, amount="1000", address="STATEMENT_BALANCE"),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts={"ACCOUNT_CLOSURE_REQUESTED": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_available_balance_zeroed_out_in_close_code_if_account_can_be_closed(self):
        balances = init_balances(
            balance_defs=[
                {"address": "default", "net": "0"},
                {"address": "available_balance", "net": "20000"},
            ]
        )

        expected_calls = [
            override_info_balance_call(
                delta_amount="20000",
                amount="0",
                info_balance=AVAILABLE,
                increase=False,
                trigger="ACCOUNT_CLOSED",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts={"ACCOUNT_CLOSURE_REQUESTED": [(DEFAULT_DATE, True)]},
            credit_limit=Decimal("20000"),
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_pre_post_scod_uncharged_int_bals_0ed_out_in_close_code_if_account_can_be_closed(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "default", "net": "0"},
                {"address": "purchase_interest_post_scod_uncharged", "net": "10"},
                {"address": "purchase_interest_pre_scod_uncharged", "net": "20"},
                {"address": "cash_advance_interest_post_scod_uncharged", "net": "15"},
                {"address": "cash_advance_interest_pre_scod_uncharged", "net": "25"},
                {
                    "address": "balance_transfer_ref1_interest_post_scod_uncharged",
                    "net": "20",
                },
                {
                    "address": "balance_transfer_ref2_interest_post_scod_uncharged",
                    "net": "25",
                },
                {
                    "address": "balance_transfer_ref1_interest_pre_scod_uncharged",
                    "net": "30",
                },
                {
                    "address": "balance_transfer_ref2_interest_pre_scod_uncharged",
                    "net": "35",
                },
            ]
        )

        expected_calls = [
            reverse_uncharged_interest_call(
                amount="10",
                txn_type="PURCHASE",
                trigger="ACCOUNT_CLOSED",
                accrual_type="POST_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="20",
                txn_type="PURCHASE",
                trigger="ACCOUNT_CLOSED",
                accrual_type="PRE_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="15",
                txn_type="CASH_ADVANCE",
                trigger="ACCOUNT_CLOSED",
                accrual_type="POST_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="25",
                txn_type="CASH_ADVANCE",
                trigger="ACCOUNT_CLOSED",
                accrual_type="PRE_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="20",
                txn_type="BALANCE_TRANSFER",
                trigger="ACCOUNT_CLOSED",
                txn_ref="REF1",
                accrual_type="POST_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="25",
                txn_type="BALANCE_TRANSFER",
                trigger="ACCOUNT_CLOSED",
                txn_ref="REF2",
                accrual_type="POST_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="30",
                txn_type="BALANCE_TRANSFER",
                trigger="ACCOUNT_CLOSED",
                txn_ref="REF1",
                accrual_type="PRE_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="35",
                txn_type="BALANCE_TRANSFER",
                trigger="ACCOUNT_CLOSED",
                txn_ref="REF2",
                accrual_type="PRE_SCOD",
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts={"ACCOUNT_CLOSURE_REQUESTED": [(DEFAULT_DATE, True)]},
            credit_limit=Decimal("20000"),
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "balance_transfer": {}}),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_uncharged_interest_balance_zeroed_out_in_close_code_if_account_can_be_closed(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "default", "net": "0"},
                {"address": "purchase_interest_uncharged", "net": "10"},
                {"address": "cash_advance_interest_uncharged", "net": "15"},
                {"address": "balance_transfer_ref1_interest_uncharged", "net": "20"},
                {"address": "balance_transfer_ref2_interest_uncharged", "net": "25"},
            ]
        )

        expected_calls = [
            reverse_uncharged_interest_call(
                amount="10", txn_type="PURCHASE", trigger="ACCOUNT_CLOSED"
            ),
            reverse_uncharged_interest_call(
                amount="15", txn_type="CASH_ADVANCE", trigger="ACCOUNT_CLOSED"
            ),
            reverse_uncharged_interest_call(
                amount="20",
                txn_type="BALANCE_TRANSFER",
                trigger="ACCOUNT_CLOSED",
                txn_ref="REF1",
            ),
            reverse_uncharged_interest_call(
                amount="25",
                txn_type="BALANCE_TRANSFER",
                trigger="ACCOUNT_CLOSED",
                txn_ref="REF2",
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts={"ACCOUNT_CLOSURE_REQUESTED": [(DEFAULT_DATE, True)]},
            credit_limit=Decimal("20000"),
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "balance_transfer": {}}),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            accrue_interest_from_txn_day=False,
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_available_balance_not_zeroed_out_in_close_code_if_already_0(self):
        balances = init_balances(
            balance_defs=[
                {"address": "default", "net": "1000"},
                {"address": "purchase_billed", "net": "1000"},
                {"address": "available_balance", "net": "0"},
            ]
        )

        unexpected_calls = [
            override_info_balance_call(
                delta_amount=ANY,
                amount=ANY,
                info_balance=AVAILABLE,
                increase=False,
                trigger="ACCOUNT_CLOSED",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts={"ACCOUNT_CLOSURE_REQUESTED": [(DEFAULT_DATE, True)]},
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=DEFAULT_DATE)

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_final_statement_workflow_uses_previous_statement_end_as_statement_start(
        self,
    ):
        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])

        account_creation_date = datetime(2019, 1, 1)
        payment_due_period = 21
        closure_date = offset_datetime(2019, 8, 10, 4)
        posting_instructions = []

        # First SCOD is 2019-1-31 and first PDD is 2019-2-21. Hence subsequent SCODs are on 1st of
        # the month
        expected_calls = [
            publish_statement_workflow_call(
                start_of_statement="2019-08-01",
                end_of_statement="2019-08-10",
                is_final="True",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts={"ACCOUNT_CLOSURE_REQUESTED": [(DEFAULT_DATE, True)]},
            account_creation_date=account_creation_date,
            payment_due_period=payment_due_period,
            posting_instructions=posting_instructions,
            last_scod_execution_time=datetime(2019, 8, 1, 0, 0, 2),
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=closure_date)

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_final_statement_workflow_before_first_scod_has_correct_statement_period(
        self,
    ):
        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])

        account_creation_date = datetime(2019, 1, 1)
        payment_due_period = 21
        closure_date = offset_datetime(2019, 1, 10, 4)
        posting_instructions = []

        # First SCOD is 2019-1-31 and first PDD is 2019-2-21. Hence subsequent SCODs are on 1st of
        # the month
        expected_calls = [
            publish_statement_workflow_call(
                start_of_statement="2019-01-01",
                end_of_statement="2019-01-10",
                is_final="True",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts={"ACCOUNT_CLOSURE_REQUESTED": [(DEFAULT_DATE, True)]},
            account_creation_date=account_creation_date,
            payment_due_period=payment_due_period,
            posting_instructions=posting_instructions,
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=closure_date)

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_final_statement_workflow_has_no_future_pdd_or_scod_dates(self):
        balances = init_balances(balance_defs=[{"address": "default", "net": "0"}])

        account_creation_date = datetime(2019, 1, 1)
        payment_due_period = 21
        closure_date = offset_datetime(2019, 8, 10, 4)
        posting_instructions = []

        expected_calls = [
            publish_statement_workflow_call(
                current_pdd="", next_pdd="", next_scod="", is_final="True"
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
            flags_ts={"ACCOUNT_CLOSURE_REQUESTED": [(DEFAULT_DATE, True)]},
            account_creation_date=account_creation_date,
            payment_due_period=payment_due_period,
            posting_instructions=posting_instructions,
        )

        run(self.smart_contract, "close_code", mock_vault, effective_date=closure_date)

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)


class PddTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_revolver_set_if_outstanding_statement_balance_at_effective_date(self):
        balances = init_balances(balance_defs=[{"address": "purchase_billed", "net": "5000"}])

        expected_calls = [set_revolver_call()]

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_revolver_set_if_outstanding_statement_balance_after_effective_date(self):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "200"},
                {"address": "purchase_billed", "net": "200"},
            ]
        )
        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 22, 0, 0, 1),
                balance_defs=[
                    {"address": "DEFAULT", "net": "100"},
                    {"address": "purchase_billed", "net": "100"},
                ],
            )
        )
        expected_calls = [set_revolver_call()]

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_revolver_not_set_if_no_outstanding_statement_balance_at_effective_date(
        self,
    ):
        balances = init_balances(balance_defs=[{"address": "DEFAULT", "net": "0"}])

        unexpected_calls = [set_revolver_call()]

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_revolver_not_set_if_no_outstanding_statement_balance_after_effective_date(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "200"},
                {"address": "purchase_billed", "net": "200"},
            ]
        )
        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 22, 0, 0, 1),
                balance_defs=[
                    {"address": "DEFAULT", "net": "0"},
                    {"address": "purchase_billed", "net": "0"},
                ],
            )
        )
        unexpected_calls = [set_revolver_call()]

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_revolver_not_set_if_positive_outstanding_statement_balance_at_effective_date(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "-1000"},
                {"address": "DEPOSIT", "net": "1000"},
            ]
        )

        unexpected_calls = [set_revolver_call()]

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_revolver_is_not_set_if_already_set(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "5000"},
                {"address": "revolver", "net": "-1"},
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )
        mock_calls = mock_vault.mock_calls
        self.assertEqual(set_revolver_call() not in mock_calls, True)

    def test_accrued_interest_from_txn_day_charged_if_outstanding_stmnt_bal_at_effective_date(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "5000"},
                {"address": "purchase_billed", "net": "5000"},
                {"address": "purchase_interest_post_scod_uncharged", "net": "100"},
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        expected_calls = [
            reverse_uncharged_interest_call(
                amount="100",
                txn_type="PURCHASE",
                trigger="INTEREST_CHARGED",
                accrual_type="POST_SCOD",
            ),
            charge_interest_call(
                amount="100", txn_type="PURCHASE", accrual_type_in_trigger="POST_SCOD"
            ),
        ]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_accrued_interest_charged_if_outstanding_statement_balance_at_effective_date(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "5000"},
                {"address": "purchase_billed", "net": "5000"},
                {"address": "purchase_interest_uncharged", "net": "100"},
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            accrue_interest_from_txn_day=False,
        )

        expected_calls = [
            reverse_uncharged_interest_call(
                amount="100", txn_type="PURCHASE", trigger="INTEREST_CHARGED"
            ),
            charge_interest_call(amount="100", txn_type="PURCHASE"),
        ]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_accrued_int_from_txn_day_charged_if_outstanding_stmnt_bal_after_effective_date(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "5000"},
                {"address": "purchase_billed", "net": "5000"},
                {"address": "purchase_interest_post_scod_uncharged", "net": "100"},
            ]
        )
        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 22, 0, 0, 1),
                balance_defs=[
                    {"address": "DEFAULT", "net": "5000"},
                    {"address": "purchase_billed", "net": "2500"},
                    {"address": "purchase_interest_post_scod_uncharged", "net": "100"},
                ],
            )
        )
        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        expected_calls = [
            reverse_uncharged_interest_call(
                amount="100",
                txn_type="PURCHASE",
                trigger="INTEREST_CHARGED",
                accrual_type="POST_SCOD",
            ),
            charge_interest_call(
                amount="100", txn_type="PURCHASE", accrual_type_in_trigger="POST_SCOD"
            ),
        ]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_accrued_interest_charged_if_outstanding_statement_balance_after_effective_date(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "5000"},
                {"address": "purchase_billed", "net": "5000"},
                {"address": "purchase_interest_uncharged", "net": "100"},
            ]
        )
        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 22, 0, 0, 1),
                balance_defs=[
                    {"address": "DEFAULT", "net": "5000"},
                    {"address": "purchase_billed", "net": "2500"},
                    {"address": "purchase_interest_uncharged", "net": "100"},
                ],
            )
        )
        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            accrue_interest_from_txn_day=False,
        )

        expected_calls = [
            reverse_uncharged_interest_call(
                amount="100", txn_type="PURCHASE", trigger="INTEREST_CHARGED"
            ),
            charge_interest_call(amount="100", txn_type="PURCHASE"),
        ]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_empty_accrued_interest_from_txn_day_not_charged_at_effective_date(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "5000"},
                {"address": "purchase_interest_post_scod_uncharged", "net": "0"},
                {"address": "cash_advance_interest_post_scod_uncharged", "net": "1"},
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        unexpected_calls = [charge_interest_call(amount=ANY, txn_type="PURCHASE")]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_empty_accrued_interest_not_charged_at_effective_date(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "5000"},
                {"address": "purchase_interest_uncharged", "net": "0"},
                {"address": "cash_advance_interest_uncharged", "net": "1"},
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            accrue_interest_from_txn_day=False,
        )

        unexpected_calls = [charge_interest_call(amount=ANY, txn_type="PURCHASE")]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_accrued_interest_from_txn_day_0ed_out_if_no_outstanding_stmnt_bal_at_effective_date(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "0"},
                {"address": "purchase_interest_post_scod_uncharged", "net": "100"},
                {"address": "cash_advance_interest_post_scod_uncharged", "net": "90"},
                {
                    "address": "balance_transfer_ref1_interest_post_scod_uncharged",
                    "net": "80",
                },
                {
                    "address": "balance_transfer_ref2_interest_post_scod_uncharged",
                    "net": "70",
                },
            ]
        )

        expected_calls = [
            reverse_uncharged_interest_call(
                amount="100",
                txn_type="PURCHASE",
                trigger="OUTSTANDING_REPAID",
                accrual_type="POST_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="90",
                txn_type="CASH_ADVANCE",
                trigger="OUTSTANDING_REPAID",
                accrual_type="POST_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="80",
                txn_type="BALANCE_TRANSFER",
                trigger="OUTSTANDING_REPAID",
                txn_ref="REF1",
                accrual_type="POST_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="70",
                txn_type="BALANCE_TRANSFER",
                trigger="OUTSTANDING_REPAID",
                txn_ref="REF2",
                accrual_type="POST_SCOD",
            ),
            instruct_posting_batch_call(
                client_batch_id="ZERO_OUT_ACCRUED_INTEREST-hook_execution_id",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "balance_transfer": {}}),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_accrued_interest_zeroed_out_if_no_outstanding_statement_balance_at_effective_date(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "0"},
                {"address": "purchase_interest_uncharged", "net": "100"},
                {"address": "cash_advance_interest_uncharged", "net": "90"},
                {"address": "balance_transfer_ref1_interest_uncharged", "net": "80"},
                {"address": "balance_transfer_ref2_interest_uncharged", "net": "70"},
            ]
        )

        expected_calls = [
            reverse_uncharged_interest_call(
                amount="100", txn_type="PURCHASE", trigger="OUTSTANDING_REPAID"
            ),
            reverse_uncharged_interest_call(
                amount="90", txn_type="CASH_ADVANCE", trigger="OUTSTANDING_REPAID"
            ),
            reverse_uncharged_interest_call(
                amount="80",
                txn_type="BALANCE_TRANSFER",
                trigger="OUTSTANDING_REPAID",
                txn_ref="REF1",
            ),
            reverse_uncharged_interest_call(
                amount="70",
                txn_type="BALANCE_TRANSFER",
                trigger="OUTSTANDING_REPAID",
                txn_ref="REF2",
            ),
            instruct_posting_batch_call(
                client_batch_id="ZERO_OUT_ACCRUED_INTEREST-hook_execution_id",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "balance_transfer": {}}),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_accrued_intrst_from_txn_day_0ed_out_if_no_outstanding_stmnt_bal_after_effective_date(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "100"},
                {"address": "purchase_interest_post_scod_uncharged", "net": "100"},
                {"address": "cash_advance_interest_post_scod_uncharged", "net": "90"},
            ]
        )
        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 22, 0, 0, 1),
                balance_defs=[
                    {"address": "purchase_billed", "net": "0"},
                    {"address": "purchase_interest_post_scod_uncharged", "net": "100"},
                    {
                        "address": "cash_advance_interest_post_scod_uncharged",
                        "net": "90",
                    },
                ],
            )
        )

        expected_calls = [
            reverse_uncharged_interest_call(
                amount="100",
                txn_type="PURCHASE",
                trigger="OUTSTANDING_REPAID",
                accrual_type="POST_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="100",
                txn_type="PURCHASE",
                trigger="OUTSTANDING_REPAID",
                accrual_type="POST_SCOD",
            ),
            instruct_posting_batch_call(
                client_batch_id="ZERO_OUT_ACCRUED_INTEREST-hook_execution_id",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            accrue_interest_from_txn_day=True,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_accrued_interest_zeroed_out_if_no_outstanding_statement_balance_after_effective_date(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "100"},
                {"address": "purchase_interest_uncharged", "net": "100"},
                {"address": "cash_advance_interest_uncharged", "net": "90"},
            ]
        )
        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 22, 0, 0, 1),
                balance_defs=[
                    {"address": "purchase_billed", "net": "0"},
                    {"address": "purchase_interest_uncharged", "net": "100"},
                    {"address": "cash_advance_interest_uncharged", "net": "90"},
                ],
            )
        )

        expected_calls = [
            reverse_uncharged_interest_call(
                amount="100", txn_type="PURCHASE", trigger="OUTSTANDING_REPAID"
            ),
            reverse_uncharged_interest_call(
                amount="100", txn_type="PURCHASE", trigger="OUTSTANDING_REPAID"
            ),
            instruct_posting_batch_call(
                client_batch_id="ZERO_OUT_ACCRUED_INTEREST-hook_execution_id",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_accrued_interest_from_txn_day_0ed_out_if_non_zero_deposit_at_effective_date(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "-100"},
                {"address": "DEPOSIT", "net": "100"},
                {"address": "purchase_billed", "net": "0"},
                {"address": "purchase_interest_post_scod_uncharged", "net": "100"},
                {"address": "cash_advance_interest_post_scod_uncharged", "net": "90"},
                {
                    "address": "balance_transfer_ref1_interest_post_scod_uncharged",
                    "net": "80",
                },
                {
                    "address": "balance_transfer_ref2_interest_post_scod_uncharged",
                    "net": "70",
                },
            ]
        )

        expected_calls = [
            reverse_uncharged_interest_call(
                amount="100",
                txn_type="PURCHASE",
                trigger="OUTSTANDING_REPAID",
                accrual_type="POST_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="90",
                txn_type="CASH_ADVANCE",
                trigger="OUTSTANDING_REPAID",
                accrual_type="POST_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="80",
                txn_type="BALANCE_TRANSFER",
                trigger="OUTSTANDING_REPAID",
                txn_ref="REF1",
                accrual_type="POST_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="70",
                txn_type="BALANCE_TRANSFER",
                trigger="OUTSTANDING_REPAID",
                txn_ref="REF2",
                accrual_type="POST_SCOD",
            ),
            instruct_posting_batch_call(
                client_batch_id="ZERO_OUT_ACCRUED_INTEREST-hook_execution_id",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "balance_transfer": {}}),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_accrued_interest_zeroed_out_if_non_zero_deposit_at_effective_date(self):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "-100"},
                {"address": "DEPOSIT", "net": "100"},
                {"address": "purchase_billed", "net": "0"},
                {"address": "purchase_interest_uncharged", "net": "100"},
                {"address": "cash_advance_interest_uncharged", "net": "90"},
                {"address": "balance_transfer_ref1_interest_uncharged", "net": "80"},
                {"address": "balance_transfer_ref2_interest_uncharged", "net": "70"},
            ]
        )

        expected_calls = [
            reverse_uncharged_interest_call(
                amount="100", txn_type="PURCHASE", trigger="OUTSTANDING_REPAID"
            ),
            reverse_uncharged_interest_call(
                amount="90", txn_type="CASH_ADVANCE", trigger="OUTSTANDING_REPAID"
            ),
            reverse_uncharged_interest_call(
                amount="80",
                txn_type="BALANCE_TRANSFER",
                trigger="OUTSTANDING_REPAID",
                txn_ref="REF1",
            ),
            reverse_uncharged_interest_call(
                amount="70",
                txn_type="BALANCE_TRANSFER",
                trigger="OUTSTANDING_REPAID",
                txn_ref="REF2",
            ),
            instruct_posting_batch_call(
                client_batch_id="ZERO_OUT_ACCRUED_INTEREST-hook_execution_id",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "balance_transfer": {}}),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_late_fee_charged_if_repayments_less_than_mad(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "2990"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "10"},
            ]
        )

        expected_calls = [
            fee_rebalancing_call("100", fee_type="LATE_REPAYMENT_FEE"),
            fee_rebalancing_call("100", fee_type="LATE_REPAYMENT_FEE", from_address="DEFAULT"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_late_fee_charged_if_repayments_less_than_mad_after_effective_date(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "2990"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "10"},
            ]
        )

        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 25, 0, 0, 2),
                balance_defs=[
                    {"address": "purchase_billed", "net": "2989"},
                    {"address": "purchase_charged", "net": "100"},
                    {"address": "mad_balance", "net": "100"},
                    {"address": "total_repayments_last_statement", "net": "10"},
                ],
            )
        )

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        expected_calls = [
            fee_rebalancing_call("100", fee_type="LATE_REPAYMENT_FEE"),
            fee_rebalancing_call("100", fee_type="LATE_REPAYMENT_FEE", from_address="DEFAULT"),
        ]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_late_fee_charged_triggers_gl_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "800"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "10"},
            ]
        )

        expected_calls = [
            fee_loan_to_income_call(amount="100", fee_type="LATE_REPAYMENT_FEE"),
            charge_fee_off_bs_call(amount="100", fee_type="LATE_REPAYMENT_FEE"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_late_fee_partially_extra_limit_triggers_gl_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "975"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "10"},
            ]
        )

        expected_calls = [
            fee_loan_to_income_call(amount="100", fee_type="LATE_REPAYMENT_FEE"),
            charge_fee_off_bs_call(amount="25", fee_type="LATE_REPAYMENT_FEE"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_late_fee_fully_extra_limit_triggers_gl_postings(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "10"},
            ]
        )

        expected_calls = [
            fee_loan_to_income_call(amount="100", fee_type="LATE_REPAYMENT_FEE"),
        ]

        unexpected_calls = [charge_fee_off_bs_call(amount=ANY, fee_type="LATE_REPAYMENT_FEE")]

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, unexpected_calls)

    def test_late_fee_not_charged_if_repayments_at_mad(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "2990"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_statement", "net": "100"},
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        unexpected_calls = [
            fee_rebalancing_call("100", fee_type="LATE_REPAYMENT_FEE", from_address=ANY)
        ]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_late_fee_not_charged_if_repayments_over_mad(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "2990"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_statement", "net": "101"},
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        unexpected_calls = [
            fee_rebalancing_call("100", fee_type="LATE_REPAYMENT_FEE", from_address=ANY)
        ]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_late_fee_not_charged_if_repayments_at_mad_after_effective_date(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "2990"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_statement", "net": "99"},
            ]
        )

        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 25, 0, 0, 2),
                balance_defs=[
                    {"address": "purchase_billed", "net": "2989"},
                    {"address": "mad_balance", "net": "100"},
                    {"address": "total_repayments_last_statement", "net": "100"},
                ],
            )
        )

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        unexpected_calls = [fee_rebalancing_call("100", fee_type="LATE_REPAYMENT_FEE")]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_late_fee_not_charged_if_repayments_over_mad_after_effective_date(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "2990"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_statement", "net": "99"},
            ]
        )

        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 25, 0, 0, 2),
                balance_defs=[
                    {"address": "purchase_billed", "net": "2988"},
                    {"address": "mad_balance", "net": "100"},
                    {"address": "total_repayments_last_statement", "net": "101"},
                ],
            )
        )

        mock_vault = self.create_mock(
            balance_ts=balances, last_scod_execution_time=offset_datetime(2019, 2, 1)
        )

        unexpected_calls = [fee_rebalancing_call("100", fee_type="LATE_REPAYMENT_FEE")]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_outstanding_statement_balances_moved_to_unpaid(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "cash_advance_billed", "net": "900"},
                {"address": "cash_advance_interest_billed", "net": "700"},
                {"address": "cash_advance_fees_billed", "net": "600"},
                {"address": "annual_fees_billed", "net": "500"},
                {"address": "purchase_fees_billed", "net": "400"},
                {"address": "dispute_fees_billed", "net": "300"},
            ]
        )

        expected_calls = [
            statement_to_unpaid_call(amount=1000, txn_type="PURCHASE"),
            statement_to_unpaid_call(amount=900, txn_type="CASH_ADVANCE"),
            statement_to_unpaid_call(amount=700, txn_type="CASH_ADVANCE_INTEREST"),
            statement_to_unpaid_call(amount=600, txn_type="CASH_ADVANCE_FEES"),
            statement_to_unpaid_call(amount=500, txn_type="ANNUAL_FEES"),
            statement_to_unpaid_call(amount=400, txn_type="PURCHASE_FEES"),
            statement_to_unpaid_call(amount=300, txn_type="DISPUTE_FEES"),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_outstanding_statement_balances_moved_to_unpaid_partial_repayment_after_effective_date(
        self,
    ):

        balances = init_balances(  # Balances updated before effective date
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "cash_advance_billed", "net": "900"},
                {"address": "cash_advance_interest_billed", "net": "700"},
                {"address": "cash_advance_fees_billed", "net": "600"},
                {"address": "annual_fees_billed", "net": "500"},
                {"address": "purchase_fees_billed", "net": "400"},
                {"address": "dispute_fees_billed", "net": "300"},
            ],
        )

        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 25, 0, 0, 2),
                balance_defs=[
                    {"address": "total_repayments_last_statement", "net": "2000"},
                    {"address": "purchase_billed", "net": "0"},
                    {"address": "cash_advance_billed", "net": "0"},
                    {"address": "cash_advance_interest_billed", "net": "600"},
                    {"address": "cash_advance_fees_billed", "net": "600"},
                    {"address": "annual_fees_billed", "net": "500"},
                    {"address": "purchase_fees_billed", "net": "400"},
                    {"address": "dispute_fees_billed", "net": "300"},
                ],
            )
        )

        expected_calls = [
            statement_to_unpaid_call(amount=600, txn_type="CASH_ADVANCE_INTEREST"),
            statement_to_unpaid_call(amount=600, txn_type="CASH_ADVANCE_FEES"),
            statement_to_unpaid_call(amount=500, txn_type="ANNUAL_FEES"),
            statement_to_unpaid_call(amount=400, txn_type="PURCHASE_FEES"),
            statement_to_unpaid_call(amount=300, txn_type="DISPUTE_FEES"),
        ]
        unexpected_calls = [
            statement_to_unpaid_call(amount=ANY, txn_type="PURCHASE"),
            statement_to_unpaid_call(amount=ANY, txn_type="CASH_ADVANCE"),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, unexpected_calls)

    def test_no_outstanding_statement_balances_moved_to_unpaid_full_repayment_after_effective_date(
        self,
    ):

        balances = init_balances(  # Balances updated before effective date
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "cash_advance_billed", "net": "900"},
                {"address": "cash_advance_interest_billed", "net": "700"},
                {"address": "cash_advance_fees_billed", "net": "600"},
                {"address": "annual_fees_billed", "net": "500"},
                {"address": "purchase_fees_billed", "net": "400"},
                {"address": "dispute_fees_billed", "net": "300"},
            ],
        )

        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 25, 0, 0, 2),
                balance_defs=[
                    {"address": "total_repayments_last_statement", "net": "4400"},
                    {"address": "purchase_billed", "net": "0"},
                    {"address": "cash_advance_billed", "net": "0"},
                    {"address": "cash_advance_interest_billed", "net": "0"},
                    {"address": "cash_advance_fees_billed", "net": "0"},
                    {"address": "annual_fees_billed", "net": "0"},
                    {"address": "purchase_fees_billed", "net": "0"},
                    {"address": "dispute_fees_billed", "net": "0"},
                ],
            )
        )

        unexpected_calls = [
            statement_to_unpaid_call(amount=ANY, txn_type="PURCHASE"),
            statement_to_unpaid_call(amount=ANY, txn_type="CASH_ADVANCE"),
            statement_to_unpaid_call(amount=ANY, txn_type="CASH_ADVANCE_INTEREST"),
            statement_to_unpaid_call(amount=ANY, txn_type="CASH_ADVANCE_FEES"),
            statement_to_unpaid_call(amount=ANY, txn_type="ANNUAL_FEES"),
            statement_to_unpaid_call(amount=ANY, txn_type="PURCHASE_FEES"),
            statement_to_unpaid_call(amount=ANY, txn_type="DISPUTE_FEES"),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_available_balance_adjusted_on_pdd_with_repayment_fee_but_not_charged_interest(
        self,
    ):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "statement_balance", "net": "1000"},
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_post_scod_uncharged", "net": "10"},
                {"address": "mad_balance", "net": "10"},
                {"address": "full_outstanding_balance", "net": "1000"},
                {"address": "outstanding_balance", "net": "1000"},
                {"address": "AVAILABLE_BALANCE", "net": "0"},
                {"address": "total_repayments_last_statement", "net": "0"},
            ],
        )

        expected_calls = [internal_to_address_call(credit=True, amount=100, address=AVAILABLE)]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1, 0, 0, 2),
            annual_percentage_rate='{"purchase": "1"}',
            transaction_types='{"purchase": {}}',
            transaction_code_to_type_map='{"00": "purchase"}',
            minimum_amount_due=Decimal(60),
            minimum_percentage_due='{"purchase": "0.01"}',
            base_interest_rates='{"purchase": "0.01"}',
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_outstanding_balance_adjusted_on_pdd_with_repayment_fee_but_not_charged_interest(
        self,
    ):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "statement_balance", "net": "1000"},
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_post_scod_uncharged", "net": "10"},
                {"address": "mad_balance", "net": "10"},
                {"address": "full_outstanding_balance", "net": "1000"},
                {"address": "outstanding_balance", "net": "1000"},
                {"address": "total_repayments_last_billed", "net": "0"},
            ],
        )

        expected_calls = [internal_to_address_call(amount=100, address=OUTSTANDING)]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1, 0, 0, 2),
            annual_percentage_rate='{"purchase": "1"}',
            transaction_types='{"purchase": {}}',
            transaction_code_to_type_map='{"00": "purchase"}',
            minimum_amount_due=Decimal(60),
            minimum_percentage_due='{"purchase": "0.01"}',
            base_interest_rates='{"purchase": "0.01"}',
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_full_outstanding_balance_adjusted_on_pdd_with_repayment_fee_and_charged_interest(
        self,
    ):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "statement_balance", "net": "1000"},
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_post_scod_uncharged", "net": "10"},
                {"address": "mad_balance", "net": "10"},
                {"address": "full_outstanding_balance", "net": "1000"},
                {"address": "outstanding_balance", "net": "1000"},
                {"address": "total_repayments_last_statement", "net": "0"},
            ],
        )

        expected_calls = [internal_to_address_call(amount=110, address=FULL_OUTSTANDING)]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1, 0, 0, 2),
            annual_percentage_rate='{"purchase": "1"}',
            transaction_types='{"purchase": {}}',
            transaction_code_to_type_map='{"00": "purchase"}',
            minimum_amount_due=Decimal(60),
            minimum_percentage_due='{"purchase": "0.01"}',
            base_interest_rates='{"purchase": "0.01"}',
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_aggregate_balances_adjustment_unaffected_by_balance_changes_after_effective_date(
        self,
    ):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "statement_balance", "net": "500"},
                {"address": "purchase_billed", "net": "500"},
                {"address": "purchase_interest_post_scod_uncharged", "net": "10"},
                {"address": "mad_balance", "net": "10"},
                {"address": "available_balance", "net": "500"},
                {"address": "full_outstanding_balance", "net": "500"},
                {"address": "outstanding_balance", "net": "500"},
            ],
        )

        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 25, 0, 0, 2),
                balance_defs=[
                    {"address": "statement_balance", "net": "500"},
                    {"address": "purchase_billed", "net": "500"},
                    {"address": "purchase_charged", "net": "500"},
                    {"address": "purchase_interest_post_scod_uncharged", "net": "10"},
                    {"address": "mad_balance", "net": "10"},
                    {"address": "available_balance", "net": "0"},
                    {"address": "full_outstanding_balance", "net": "1000"},
                    {"address": "outstanding_balance", "net": "1000"},
                ],
            )
        )

        expected_calls = [
            internal_to_address_call(credit=True, amount=100, address=AVAILABLE),
            internal_to_address_call(credit=False, amount=100, address=OUTSTANDING),
            internal_to_address_call(credit=False, amount=110, address=FULL_OUTSTANDING),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1, 0, 0, 2),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_intrst_charged_from_txn_day_on_pdd_updates_full_outstanding_and_not_outstanding(
        self,
    ):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "purchase_interest_post_scod_uncharged", "net": "100"},
                {"address": "cash_advance_interest_post_scod_uncharged", "net": "200"},
                {"address": "full_outstanding_balance", "net": "2000"},
                {"address": "outstanding_balance", "net": "2000"},
                {"address": "AVAILABLE_BALANCE", "net": "-1000"},
            ],
        )

        expected_calls = [
            charge_interest_call("100", txn_type="PURCHASE", accrual_type_in_trigger="POST_SCOD"),
            charge_interest_call(
                "200", txn_type="CASH_ADVANCE", accrual_type_in_trigger="POST_SCOD"
            ),
            internal_to_address_call(amount="100", credit=False, address="DEFAULT"),
            internal_to_address_call(amount="200", credit=False, address="DEFAULT"),
            internal_to_address_call(amount="300", credit=False, address=FULL_OUTSTANDING),
        ]
        unexpected_calls = [
            internal_to_address_call(amount=ANY, credit=False, address=OUTSTANDING),
            internal_to_address_call(amount=ANY, credit=True, address=AVAILABLE),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, unexpected_calls)

    def test_interest_charged_on_pdd_updates_full_outstanding_and_not_outstanding(self):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "purchase_interest_uncharged", "net": "100"},
                {"address": "cash_advance_interest_uncharged", "net": "200"},
                {"address": "full_outstanding_balance", "net": "2000"},
                {"address": "outstanding_balance", "net": "2000"},
                {"address": "AVAILABLE_BALANCE", "net": "-1000"},
            ],
        )

        expected_calls = [
            charge_interest_call("100", txn_type="PURCHASE"),
            charge_interest_call("200", txn_type="CASH_ADVANCE"),
            internal_to_address_call(amount="100", credit=False, address="DEFAULT"),
            internal_to_address_call(amount="200", credit=False, address="DEFAULT"),
            internal_to_address_call(amount="300", credit=False, address=FULL_OUTSTANDING),
        ]
        unexpected_calls = [
            internal_to_address_call(amount=ANY, credit=False, address=OUTSTANDING),
            internal_to_address_call(amount=ANY, credit=True, address=AVAILABLE),
        ]

        mock_vault = self.create_mock(balance_ts=balances, accrue_interest_from_txn_day=False)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, unexpected_calls)

    def test_pdd_and_scod_schedules_amended_after_first_pdd_processing(self):
        balances = init_balances()

        expected_calls = [
            update_event_type_call(
                event_type=EVENT_PDD,
                schedule=EventTypeSchedule(
                    month="3",
                    day="22",
                    hour=str(PDD_TIME.hour),
                    minute=str(PDD_TIME.minute),
                    second=str(PDD_TIME.second),
                ),
            ),
            update_event_type_call(
                event_type=EVENT_SCOD,
                schedule=EventTypeSchedule(
                    month="3",
                    day="1",
                    hour=str(SCOD_TIME.hour),
                    minute=str(SCOD_TIME.minute),
                    second=str(SCOD_TIME.second),
                ),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances, last_pdd_execution_time=None, payment_due_period=21
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 22, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_match=True
        )

    def test_pdd_and_scod_schedules_amended_if_local_and_utc_pdd_in_different_month(
        self,
    ):
        balances = init_balances()

        expected_calls = [
            update_event_type_call(
                event_type=EVENT_PDD,
                schedule=EventTypeSchedule(
                    month="4",
                    day="2",
                    hour=str(PDD_TIME.hour),
                    minute=str(PDD_TIME.minute),
                    second=str(PDD_TIME.second),
                ),
            ),
            update_event_type_call(
                event_type=EVENT_SCOD,
                schedule=EventTypeSchedule(
                    month="3",
                    day="11",
                    hour=str(SCOD_TIME.hour),
                    minute=str(SCOD_TIME.minute),
                    second=str(SCOD_TIME.second),
                ),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_pdd_execution_time=None,
            payment_due_period=22,
            account_creation_date=offset_datetime(2019, 1, 8, 23),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 3, 2, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault,
            expected_calls=expected_calls,
        )

    def test_pdd_and_scod_schedules_amended_after_second_pdd_processing(self):
        balances = init_balances()

        expected_calls = [
            update_event_type_call(
                event_type=EVENT_PDD,
                schedule=EventTypeSchedule(
                    month="4",
                    day="22",
                    hour=str(PDD_TIME.hour),
                    minute=str(PDD_TIME.minute),
                    second=str(PDD_TIME.second),
                ),
            ),
            update_event_type_call(
                event_type=EVENT_SCOD,
                schedule=EventTypeSchedule(
                    month="4",
                    day="1",
                    hour=str(SCOD_TIME.hour),
                    minute=str(SCOD_TIME.minute),
                    second=str(SCOD_TIME.second),
                ),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            payment_due_period=21,
            last_pdd_execution_time=offset_datetime(2019, 2, 22, 0, 0, 1),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 3, 22, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_match=True
        )

    def test_pdd_and_scod_amended_schedules_handle_month_ends(self):
        balances = init_balances()

        account_creation_date = offset_datetime(2018, 12, 11)
        # PDD is 2019/1/31, schedule is 2019/2/1
        pdd_run_date = offset_datetime(2019, 2, 1, 0, 0, 1)
        pdp = 21

        expected_calls = [
            update_event_type_call(
                event_type=EVENT_PDD,
                schedule=EventTypeSchedule(
                    month="3",
                    day="1",
                    hour=str(PDD_TIME.hour),
                    minute=str(PDD_TIME.minute),
                    second=str(PDD_TIME.second),
                ),
            ),
            update_event_type_call(
                event_type=EVENT_SCOD,
                schedule=EventTypeSchedule(
                    month="2",
                    day="8",
                    hour=str(SCOD_TIME.hour),
                    minute=str(SCOD_TIME.minute),
                    second=str(SCOD_TIME.second),
                ),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_pdd_execution_time=None,
            payment_due_period=pdp,
            account_creation_date=account_creation_date,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=pdd_run_date,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_match=True
        )

    def test_pdd_and_scod_amended_schedules_handle_leap_years(self):
        balances = init_balances()

        account_creation_date = offset_datetime(2019, 12, 11)
        last_scod_execution_time = offset_datetime(2020, 1, 10)
        pdd_run_date = offset_datetime(2020, 2, 1)  # PDD is 2020/1/31, so schedule is 2020/2/1
        pdd = 21

        # Next PDD will be on 2020/02/29 due to leap year
        expected_calls = [
            update_event_type_call(
                event_type=EVENT_PDD,
                schedule=EventTypeSchedule(
                    month="3",
                    day="1",
                    hour=str(PDD_TIME.hour),
                    minute=str(PDD_TIME.minute),
                    second=str(PDD_TIME.second),
                ),
            ),
            update_event_type_call(
                event_type=EVENT_SCOD,
                schedule=EventTypeSchedule(
                    month="2",
                    day="9",
                    hour=str(SCOD_TIME.hour),
                    minute=str(SCOD_TIME.minute),
                    second=str(SCOD_TIME.second),
                ),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=last_scod_execution_time,
            payment_due_period=pdd,
            account_creation_date=account_creation_date,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=pdd_run_date,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, exact_match=True
        )

    def test_posting_batch_for_pdd_no_interest_zeroing(self):
        balances = init_balances(balance_defs=[{"address": "purchase_billed", "net": "5000"}])

        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 2, 22),
                client_batch_id=f"PDD-{HOOK_EXECUTION_ID}",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            payment_due_period=21,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 22),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_match=True)

    def test_posting_batch_for_pdd_interest_from_txn_day_zeroing(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_interest_post_scod_uncharged", "net": "1000"},
                {
                    "address": "balance_transfer_ref1_interest_post_scod_uncharged",
                    "net": "200",
                },
                {
                    "address": "balance_transfer_ref2_interest_post_scod_uncharged",
                    "net": "300",
                },
            ]
        )

        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 2, 22),
                client_batch_id=f"ZERO_OUT_ACCRUED_INTEREST-{HOOK_EXECUTION_ID}",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            payment_due_period=21,
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "balance_transfer": {}}),
            transaction_references=dumps({"balance_transfer": ["REF1", "REF2"]}),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 22),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_match=True)

    def test_posting_batch_for_pdd_interest_zeroing(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_interest_uncharged", "net": "1000"},
                {"address": "balance_transfer_ref1_interest_uncharged", "net": "200"},
                {"address": "balance_transfer_ref2_interest_uncharged", "net": "300"},
            ]
        )

        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 2, 22),
                client_batch_id=f"ZERO_OUT_ACCRUED_INTEREST-{HOOK_EXECUTION_ID}",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            payment_due_period=21,
            transaction_types=dumps({"purchase": {}, "cash_advance": {}, "balance_transfer": {}}),
            transaction_references=dumps({"balance_transfer": ["REF1", "REF2"]}),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 22),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_match=True)

    def test_posting_batch_for_pdd_no_interest_zeroing_and_balances_updated_after_effective_date(
        self,
    ):
        balances = init_balances(  # Balances before effective date
            dt=offset_datetime(2019, 2, 21, 23, 59, 59, 999999),
            balance_defs=[{"address": "purchase_billed", "net": "1000"}],
        )

        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 22, 0, 0, 1, 1),
                balance_defs=[
                    {"address": "purchase_billed", "net": "800"},
                    {"address": "total_repayments_last_statement", "net": "200"},
                ],
            )
        )
        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 2, 22, 0, 0, 1, 1),
                client_batch_id=f"PDD-{HOOK_EXECUTION_ID}",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            payment_due_period=21,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 22, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_match=True)

    def test_posting_batch_for_pdd_interest_from_txn_day_0ing_and_bal_updated_after_eff_date(
        self,
    ):
        balances = init_balances(  # Balances before effective date
            dt=offset_datetime(2019, 2, 21, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_interest_post_scod_uncharged", "net": "1000"},
            ],
        )

        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 22, 0, 0, 1),
                balance_defs=[
                    {"address": "purchase_interest_post_scod_uncharged", "net": "1000"},
                    {"address": "purchase_charged", "net": "200"},
                ],
            )
        )
        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 2, 22, 0, 0, 1),
                client_batch_id=f"ZERO_OUT_ACCRUED_INTEREST-{HOOK_EXECUTION_ID}",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            payment_due_period=21,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 22),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_match=True)

    def test_posting_batch_for_pdd_interest_zeroing_and_balances_updated_after_effective_date(
        self,
    ):
        balances = init_balances(  # Balances before effective date
            dt=offset_datetime(2019, 2, 21, 23, 59, 59, 999999),
            balance_defs=[{"address": "purchase_interest_uncharged", "net": "1000"}],
        )

        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 22, 0, 0, 1),
                balance_defs=[
                    {"address": "purchase_interest_uncharged", "net": "1000"},
                    {"address": "purchase_charged", "net": "200"},
                ],
            )
        )
        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 2, 22, 0, 0, 1),
                client_batch_id=f"ZERO_OUT_ACCRUED_INTEREST-{HOOK_EXECUTION_ID}",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            payment_due_period=21,
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 22),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, exact_match=True)

    def test_existing_overdue_buckets_aged_on_pdd_if_there_is_no_overdue_for_current_cycle(
        self,
    ):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "overdue_1", "net": "1000"},
                {"address": "overdue_2", "net": "2000"},
                {"address": "overdue_3", "net": "3200"},
                {"address": "total_repayments_last_billed", "net": "0"},
                {"address": "mad_balance", "net": "6200"},
                {"address": "revolver", "net": "-1"},
            ],
        )

        # the expected calls are for the delta between new and old overdue buckets values
        expected_calls = [
            internal_to_address_call(credit=False, amount="3200", address="OVERDUE_4"),
            internal_to_address_call(credit=True, amount="1200", address="OVERDUE_3"),
            internal_to_address_call(credit=True, amount="1000", address="OVERDUE_2"),
            internal_to_address_call(credit=True, amount="1000", address="OVERDUE_1"),
        ]
        unexpected_calls = [
            internal_to_address_call(credit=False, amount=ANY, address="OVERDUE_1"),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, unexpected_calls)

    def test_existing_overdue_buckets_aged_on_pdd_if_there_is_overdue_for_current_cycle(
        self,
    ):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "overdue_1", "net": "1000"},
                {"address": "overdue_2", "net": "2000"},
                {"address": "overdue_3", "net": "3200"},
                {"address": "total_repayments_last_billed", "net": "0"},
                {"address": "mad_balance", "net": "6300"},
                {"address": "cash_advance_fees_billed", "net": "100"},
            ],
        )

        # the expected calls are for the delta between new and old overdue buckets (e.g. overdue_2
        # goes from -2000 to -1000, so it is credited with 1000
        expected_calls = [
            internal_to_address_call(credit=False, amount="3200", address="OVERDUE_4"),
            internal_to_address_call(credit=True, amount="1200", address="OVERDUE_3"),
            internal_to_address_call(credit=True, amount="1000", address="OVERDUE_2"),
            internal_to_address_call(credit=True, amount="900", address="OVERDUE_1"),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_new_overdue_amount_excludes_previous_overdue_included_in_mad_when_no_repayments(
        self,
    ):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "overdue_1", "net": "1100"},
                {"address": "total_repayments_last_billed", "net": "0"},
                {"address": "cash_advance_fees_billed", "net": "100"},
                {"address": "mad_balance", "net": "1200"},
            ],
        )

        # This equates to overdue being set to 100 (i.e. just the missing fees) as it was -1100
        expected_calls = [internal_to_address_call(credit=True, amount="1000", address="OVERDUE_1")]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_no_new_overdue_amount_if_repayments_plus_existing_overdue_exceed_mad(self):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "overdue_1", "net": "100"},
                {"address": "total_repayments_last_statement", "net": "100"},
                {"address": "cash_advance_fees_billed", "net": "0"},
                {"address": "purchase_billed", "net": "950"},
                {"address": "mad_balance", "net": "100"},
            ],
        )

        # This equates to overdue_1 being transferred to overdue 2, so overdue_1 is now 0
        expected_calls = [
            internal_to_address_call(credit=True, amount=100, address="OVERDUE_1"),
            internal_to_address_call(credit=False, amount=100, address="OVERDUE_2"),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_new_overdue_bucket_set_if_none_exist_today(self):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "total_repayments_last_statement", "net": "0"},
                {"address": "mad_balance", "net": "100"},
                {"address": "cash_advance_fees_billed", "net": "100"},
            ],
        )

        expected_calls = [
            make_internal_transfer_instructions_call(
                amount="100",
                from_account_address="OVERDUE_1",
                to_account_address=INTERNAL,
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_balances_moved_to_unpaid_on_pdd_with_txn_refs(self):
        balances = init_balances(
            balance_defs=[
                {"address": "balance_transfer_ref1_billed", "net": "1000"},
                {"address": "balance_transfer_ref2_billed", "net": "900"},
                {"address": "cash_advance_billed", "net": "800"},
                {"address": "balance_transfer_ref1_interest_billed", "net": "750"},
                {"address": "balance_transfer_ref2_interest_billed", "net": "700"},
                {"address": "balance_transfer_fees_billed", "net": "600"},
                {"address": "cash_advance_interest_billed", "net": "500"},
                {"address": "annual_fees_billed", "net": "400"},
            ]
        )

        expected_calls = [
            statement_to_unpaid_call(amount=1000, txn_type="BALANCE_TRANSFER", ref="REF1"),
            statement_to_unpaid_call(amount=900, txn_type="BALANCE_TRANSFER", ref="REF2"),
            statement_to_unpaid_call(amount=800, txn_type="CASH_ADVANCE"),
            statement_to_unpaid_call(amount=750, txn_type="BALANCE_TRANSFER_REF1_INTEREST"),
            statement_to_unpaid_call(amount=700, txn_type="BALANCE_TRANSFER_REF2_INTEREST"),
            statement_to_unpaid_call(amount=600, txn_type="BALANCE_TRANSFER_FEES"),
            statement_to_unpaid_call(amount=500, txn_type="CASH_ADVANCE_INTEREST"),
            statement_to_unpaid_call(amount=400, txn_type="ANNUAL_FEES"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "transfer": {},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            base_interest_rates=dumps({"purchase": "0.2", "cash_advance": "0.3"}),
            transaction_base_interest_rates=dumps(
                {"balance_transfer": {"REF1": "0.25", "ref2": "0.35"}}
            ),
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {"REF1": "0.4", "ref2": "0.5"}}
            ),
            minimum_percentage_due=dumps(
                {
                    "purchase": "0.2",
                    "cash_advance": "0.2",
                    "transfer": "0.2",
                    "balance_transfer": "0.2",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_overdue_postings_considers_partial_repayment_after_pdd_effective_date(
        self,
    ):
        balances = init_balances(  # Balances updated before effective date
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "total_repayments_last_statement", "net": "0"},
                {"address": "mad_balance", "net": "100"},
                {"address": "cash_advance_fees_billed", "net": "100"},
            ],
        )

        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 25, 0, 0, 2),
                balance_defs=[
                    {"address": "total_repayments_last_statement", "net": "50"},
                    {"address": "mad_balance", "net": "100"},
                    {"address": "cash_advance_fees_billed", "net": "50"},
                ],
            )
        )

        expected_calls = [
            make_internal_transfer_instructions_call(
                amount="50",
                from_account_address="OVERDUE_1",
                to_account_address=INTERNAL,
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_overdue_postings_considers_full_repayment_after_pdd_effective_date(self):
        balances = init_balances(  # Balances updated before effective date
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "total_repayments_last_statement", "net": "0"},
                {"address": "mad_balance", "net": "100"},
                {"address": "cash_advance_fees_billed", "net": "100"},
            ],
        )

        balances.extend(
            init_balances(  # Balances updated after effective date
                dt=offset_datetime(2019, 2, 25, 0, 0, 2),
                balance_defs=[
                    {"address": "total_repayments_last_statement", "net": "100"},
                    {"address": "mad_balance", "net": "100"},
                    {"address": "cash_advance_fees_billed", "net": "0"},
                ],
            )
        )

        expected_calls = []

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_mock_vault_method_calls(
            mock_vault.make_internal_transfer_instructions,
            expected_calls=expected_calls,
            exact_match=True,
        )

    def test_sub_type_construction_on_txn_ref_if_revolver_set_accrue_from_txn_day(self):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "balance_transfer_ref1_billed", "net": "3000"},
                {
                    "address": "balance_transfer_ref1_interest_post_scod_uncharged",
                    "net": "100",
                },
            ],
        )

        expected_calls = [
            set_revolver_call(),
            charge_interest_call(
                amount="100",
                txn_type="BALANCE_TRANSFER_REF1",
                accrual_type_in_trigger="POST_SCOD",
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types=dumps(
                {"balance_transfer": {"charge_interest_from_transaction_date": "False"}}
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            transaction_base_interest_rates=dumps({"balance_transfer": {"REF1": "0.25"}}),
            transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "0.4"}}),
            minimum_percentage_due=dumps(
                {"balance_transfer": "0.2", "interest": "1.0", "fees": "1.0"}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_sub_type_construction_on_txn_ref_if_revolver_set(self):
        balances = init_balances(
            dt=offset_datetime(2019, 2, 24, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "balance_transfer_ref1_billed", "net": "3000"},
                {"address": "balance_transfer_ref1_interest_uncharged", "net": "100"},
            ],
        )

        expected_calls = [
            set_revolver_call(),
            charge_interest_call(amount="100", txn_type="BALANCE_TRANSFER_REF1"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            transaction_types=dumps(
                {"balance_transfer": {"charge_interest_from_transaction_date": "False"}}
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            transaction_base_interest_rates=dumps({"balance_transfer": {"REF1": "0.25"}}),
            transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "0.4"}}),
            minimum_percentage_due=dumps(
                {"balance_transfer": "0.2", "interest": "1.0", "fees": "1.0"}
            ),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_mad_zeroed_on_pdd_if_mad_equal_to_zero_flag(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "mad_balance", "net": "500"},
            ]
        )
        expected_calls = [
            zero_out_mad_balance_call(amount="500", denomination=DEFAULT_DENOM),
        ]
        unexpected_calls = [
            internal_to_address_call(credit=False, amount=ANY, address="OVERDUE_1"),
            fee_rebalancing_call(ANY, fee_type="LATE_REPAYMENT_FEE"),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            mad_equal_to_zero_flags='["REPAYMENT_HOLIDAY"]',
            flags_ts={"REPAYMENT_HOLIDAY": [(DEFAULT_DATE - timedelta(days=1), True)]},
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_billed_not_moved_to_unpaid_on_pdd_if_blocked_by_flag(self):
        balances = init_balances(balance_defs=[{"address": "purchase_billed", "net": "1000"}])
        unexpected_calls = [statement_to_unpaid_call(amount=ANY, txn_type="PURCHASE")]
        mock_vault = self.create_mock(
            balance_ts=balances,
            billed_to_unpaid_transfer_blocking_flags='["REPAYMENT_HOLIDAY"]',
            flags_ts={"REPAYMENT_HOLIDAY": [(DEFAULT_DATE - timedelta(days=1), True)]},
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_overdue_buckets_not_aged_on_pdd_if_blocked_by_flag(self):
        balances = init_balances(
            balance_defs=[
                {"address": "overdue_1", "net": "1000"},
                {"address": "overdue_2", "net": "1000"},
            ]
        )
        unexpected_calls = [
            internal_to_address_call(credit=False, amount=ANY, address="OVERDUE_1"),
            internal_to_address_call(credit=False, amount=ANY, address="OVERDUE_2"),
            internal_to_address_call(credit=False, amount=ANY, address="OVERDUE_3"),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            overdue_amount_blocking_flags='["REPAYMENT_HOLIDAY"]',
            flags_ts={"REPAYMENT_HOLIDAY": [(DEFAULT_DATE - timedelta(days=1), True)]},
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_account_can_still_go_to_revolver_even_if_repayment_holiday(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "1000"},
                {"address": "purchase_interest_post_scod_uncharged", "net": "100"},
            ]
        )
        expected_calls = [
            set_revolver_call(),
            charge_interest_call(
                amount="100",
                txn_type="PURCHASE",
                accrual_type="POST_SCOD",
                accrual_type_in_trigger="POST_SCOD",
            ),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            mad_equal_to_zero_flags='["REPAYMENT_HOLIDAY"]',
            overdue_amount_blocking_flags='["REPAYMENT_HOLIDAY"]',
            flags_ts={"REPAYMENT_HOLIDAY": [(DEFAULT_DATE - timedelta(days=1), True)]},
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)


class ScodPercentageMadHelperTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_mad_contains_statement_charges_unpaid_charges_overdue_and_pct_of_txn_type(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "annual_fees_billed", "net": "70"},
                {"address": "overlimit_fees_billed", "net": "30"},
                {"address": "dispute_fees_unpaid", "net": "120"},
                {"address": "cash_advance_fees_unpaid", "net": "190"},
                {"address": "purchase_fees_unpaid", "net": "10"},
                {"address": "purchase_interest_billed", "net": "100"},
                {"address": "cash_advance_interest_billed", "net": "25"},
                {"address": "cash_advance_interest_unpaid", "net": "50"},
                {"address": "purchase_interest_unpaid", "net": "200"},
                {"address": "overdue_1", "net": "1000"},
                {"address": "purchase_billed", "net": "1000"},
                {"address": "cash_advance_billed", "net": "500"},
            ]
        )

        # all fees = 420, all interest = 375, all overdue/overlimit spend = -1000
        # txn_type = 0.1*1000 + 0.2 * 500 = 200
        expected_mad = Decimal(1995)
        actual_mad = run(
            self.smart_contract,
            "_calculate_percentage_mad",
            Mock(),
            in_flight_balances=balances.latest(),
            txn_types={"PURCHASE": None, "CASH_ADVANCE": None},
            fee_types=[
                "ANNUAL_FEE",
                "CASH_ADVANCE_FEE",
                "DISPUTE_FEE",
                "OVERLIMIT_FEE",
                "PURCHASE_FEE",
            ],
            denomination=DEFAULT_DENOM,
            mad_percentages={
                "purchase": "0.1",
                "cash_advance": "0.2",
                "interest": "1.0",
                "fees": "1.0",
            },
            credit_limit=Decimal("1000"),
        )
        self.assertEqual(expected_mad, actual_mad)

    def test_mad_contains_statement_charges_unpaid_charges_overdue_and_pct_of_interest(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "annual_fees_billed", "net": "70"},
                {"address": "overlimit_fees_billed", "net": "30"},
                {"address": "dispute_fees_unpaid", "net": "120"},
                {"address": "cash_advance_fees_unpaid", "net": "190"},
                {"address": "purchase_fees_unpaid", "net": "10"},
                {"address": "purchase_interest_billed", "net": "100"},
                {"address": "cash_advance_interest_billed", "net": "25"},
                {"address": "cash_advance_interest_unpaid", "net": "50"},
                {"address": "purchase_interest_unpaid", "net": "200"},
                {"address": "overdue_1", "net": "1000"},
                {"address": "purchase_billed", "net": "1000"},
                {"address": "cash_advance_billed", "net": "500"},
            ]
        )

        # all fees = 420, all interest = 375, all overdue/overlimit spend = 1000
        # mad_interest_fees = 0.75 * 420 + 0.0 * 375 = 315
        # expected_mad = 1000 + 315 + 1000 * 0.0 + 500 * 0.0 = 1315
        expected_mad = Decimal(1315)
        actual_mad = run(
            self.smart_contract,
            "_calculate_percentage_mad",
            Mock(),
            in_flight_balances=balances.latest(),
            txn_types={"PURCHASE": None, "CASH_ADVANCE": None},
            fee_types=[
                "ANNUAL_FEE",
                "CASH_ADVANCE_FEE",
                "DISPUTE_FEE",
                "OVERLIMIT_FEE",
                "PURCHASE_FEE",
            ],
            denomination=DEFAULT_DENOM,
            mad_percentages={
                "purchase": "0.0",
                "cash_advance": "0.0",
                "interest": "0.0",
                "fees": "0.75",
            },
            credit_limit=Decimal("1000"),
        )
        self.assertEqual(expected_mad, actual_mad)

    def test_mad_contains_statement_charges_unpaid_charges_overdue_and_pct_of_fees(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "annual_fees_billed", "net": "70"},
                {"address": "overlimit_fees_billed", "net": "30"},
                {"address": "dispute_fees_unpaid", "net": "120"},
                {"address": "cash_advance_fees_unpaid", "net": "190"},
                {"address": "purchase_fees_unpaid", "net": "10"},
                {"address": "purchase_interest_billed", "net": "100"},
                {"address": "cash_advance_interest_billed", "net": "25"},
                {"address": "cash_advance_interest_unpaid", "net": "50"},
                {"address": "purchase_interest_unpaid", "net": "200"},
                {"address": "overdue_1", "net": "600"},
                {"address": "purchase_billed", "net": "1000"},
                {"address": "cash_advance_billed", "net": "500"},
            ]
        )

        # all fees = 420, all interest = 375, all overdue/overlimit spend = 1000
        # mad_interest_fees = 0.0 * 420 + 0.65 * 375 = 243.75
        # expected_mad = 600 + 243.75 + 1000 * 0.1 + 500 * 0.2 = 1043.75
        expected_mad = Decimal(1043.75)
        actual_mad = run(
            self.smart_contract,
            "_calculate_percentage_mad",
            Mock(),
            in_flight_balances=balances.latest(),
            txn_types={"PURCHASE": None, "CASH_ADVANCE": None},
            fee_types=[
                "ANNUAL_FEE",
                "CASH_ADVANCE_FEE",
                "DISPUTE_FEE",
                "OVERLIMIT_FEE",
                "PURCHASE_FEE",
            ],
            denomination=DEFAULT_DENOM,
            mad_percentages={
                "purchase": "0.1",
                "cash_advance": "0.2",
                "interest": "0.65",
                "fees": "0.0",
            },
            credit_limit=Decimal("1000"),
        )
        self.assertEqual(expected_mad, actual_mad)

    def test_mad_contains_overlimit_if_greater_than_overdue(self):
        balances = init_balances(
            balance_defs=[
                {"address": "annual_fees_billed", "net": "70"},
                {"address": "overlimit_fees_billed", "net": "30"},
                {"address": "cash_advance_fees_unpaid", "net": "190"},
                {"address": "purchase_fees_unpaid", "net": "10"},
                {"address": "purchase_interest_billed", "net": "100"},
                {"address": "purchase_interest_unpaid", "net": "200"},
                {"address": "overdue_1", "net": "400"},
                {"address": "purchase_billed", "net": "1000"},
                {"address": "cash_advance_billed", "net": "500"},
            ]
        )
        # fees = 300, interest = 300, principal = 200, overlimit = 500 > overdue
        expected_mad = Decimal(1300)
        actual_mad = run(
            self.smart_contract,
            "_calculate_percentage_mad",
            Mock(),
            in_flight_balances=balances.latest(),
            txn_types={"PURCHASE": None, "CASH_ADVANCE": None},
            fee_types=[
                "ANNUAL_FEE",
                "CASH_ADVANCE_FEE",
                "DISPUTE_FEE",
                "OVERLIMIT_FEE",
                "PURCHASE_FEE",
            ],
            denomination=DEFAULT_DENOM,
            mad_percentages={
                "purchase": "0.1",
                "cash_advance": "0.2",
                "interest": "1.0",
                "fees": "1.0",
            },
            credit_limit=Decimal("1000"),
        )
        self.assertEqual(expected_mad, actual_mad)

    def test_mad_contains_overdue_if_greater_than_overlimit(self):
        balances = init_balances(
            balance_defs=[
                {"address": "annual_fees_billed", "net": "70"},
                {"address": "overlimit_fees_billed", "net": "30"},
                {"address": "cash_advance_fees_unpaid", "net": "190"},
                {"address": "purchase_fees_unpaid", "net": "10"},
                {"address": "purchase_interest_billed", "net": "100"},
                {"address": "purchase_interest_unpaid", "net": "200"},
                {"address": "overdue_1", "net": "600"},
                {"address": "purchase_billed", "net": "1000"},
                {"address": "cash_advance_billed", "net": "500"},
            ]
        )

        # fees = 300, interest = 300, principal = 200, overdue = 600 > overlimit (500)
        expected_mad = Decimal(1400)
        actual_mad = run(
            self.smart_contract,
            "_calculate_percentage_mad",
            Mock(),
            in_flight_balances=balances.latest(),
            txn_types={"PURCHASE": None, "CASH_ADVANCE": None},
            fee_types=[
                "ANNUAL_FEE",
                "CASH_ADVANCE_FEE",
                "DISPUTE_FEE",
                "OVERLIMIT_FEE",
                "PURCHASE_FEE",
            ],
            denomination=DEFAULT_DENOM,
            mad_percentages={
                "purchase": "0.1",
                "cash_advance": "0.2",
                "interest": "1.0",
                "fees": "1.0",
            },
            credit_limit=Decimal("1000"),
        )
        self.assertEqual(expected_mad, actual_mad)

    def test_individual_statement_percentage_amounts_are_rounded(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "4000.25"},
                {"address": "purchase_unpaid", "net": "4000.25"},
                {"address": "cash_advance_billed", "net": "8000.25"},
                {"address": "cash_advance_unpaid", "net": "8000.25"},
            ]
        )

        # If individual balances were rounded we would get 240
        # If the sum of all percentage amounts was rounded we would get 240.01
        expected_mad = Decimal("240.02")
        actual_mad = run(
            self.smart_contract,
            "_calculate_percentage_mad",
            Mock(),
            in_flight_balances=balances.latest(),
            txn_types={"PURCHASE": None, "CASH_ADVANCE": None},
            fee_types=[],
            denomination=DEFAULT_DENOM,
            mad_percentages={
                "purchase": "0.01",
                "cash_advance": "0.01",
                "interest": "1.0",
                "fees": "1.0",
            },
            credit_limit=Decimal("30000"),
        )
        self.assertEqual(expected_mad, actual_mad)

    def test_mad_contains_all_overdue_amounts_across_multiple_buckets(self):
        balances = init_balances(
            balance_defs=[
                {"address": "annual_fees_billed", "net": "70"},
                {"address": "overlimit_fees_billed", "net": "30"},
                {"address": "cash_advance_fees_unpaid", "net": "190"},
                {"address": "purchase_fees_unpaid", "net": "10"},
                {"address": "purchase_interest_billed", "net": "100"},
                {"address": "purchase_interest_unpaid", "net": "200"},
                {"address": "overdue_1", "net": "1000"},
                {"address": "overdue_2", "net": "1000"},
                {"address": "overdue_3", "net": "1000"},
                {"address": "purchase_billed", "net": "10000"},
                {"address": "cash_advance_billed", "net": "500"},
            ]
        )

        # all fees = 300, all interest = 300, all overdue/overlimit spend = -3000
        # txn_type = 0.1*10000 + 0.2 * 500 = 1100
        expected_mad = Decimal("4700")
        actual_mad = run(
            self.smart_contract,
            "_calculate_percentage_mad",
            Mock(),
            in_flight_balances=balances.latest(),
            txn_types={"PURCHASE": None, "CASH_ADVANCE": None},
            fee_types=[
                "ANNUAL_FEE",
                "CASH_ADVANCE_FEE",
                "DISPUTE_FEE",
                "OVERLIMIT_FEE",
                "PURCHASE_FEE",
            ],
            denomination=DEFAULT_DENOM,
            mad_percentages={
                "purchase": "0.1",
                "cash_advance": "0.2",
                "interest": "1.0",
                "fees": "1.0",
            },
            credit_limit=Decimal("30000"),
        )
        self.assertEqual(expected_mad, actual_mad)

    def test_mad_handles_txn_types_with_refs(self):
        balances = init_balances(
            balance_defs=[
                {"address": "balance_transfer_fees_billed", "net": "20"},
                {"address": "balance_transfer_fees_unpaid", "net": "10"},
                {"address": "balance_transfer_ref1_interest_billed", "net": "33"},
                {"address": "balance_transfer_ref2_interest_billed", "net": "44"},
                {"address": "balance_transfer_ref1_interest_unpaid", "net": "55"},
                {"address": "balance_transfer_ref2_interest_unpaid", "net": "66"},
                {"address": "overdue_1", "net": "10"},
                {"address": "balance_transfer_ref1_billed", "net": "500"},
                {"address": "balance_transfer_ref2_billed", "net": "600"},
            ]
        )

        # all fees = 30, all interest = 198, all overdue/overlimit spend = 10
        # txn_type = 0.1*1100 = 110
        expected_mad = Decimal("348")
        actual_mad = run(
            self.smart_contract,
            "_calculate_percentage_mad",
            Mock(),
            in_flight_balances=balances.latest(),
            txn_types={
                "CASH_ADVANCE": None,
                "PURCHASE": None,
                "BALANCE_TRANSFER": ["REF1", "REF2"],
            },
            fee_types=[
                "ANNUAL_FEE",
                "CASH_ADVANCE_FEE",
                "DISPUTE_FEE",
                "OVERLIMIT_FEE",
                "BALANCE_TRANSFER_FEE",
            ],
            denomination=DEFAULT_DENOM,
            mad_percentages={
                "balance_transfer": "0.1",
                "purchase": "0.1",
                "cash_advance": "0.2",
                "interest": "1.0",
                "fees": "1.0",
            },
            credit_limit=Decimal("30000"),
        )
        self.assertEqual(expected_mad, actual_mad)


class ScodMadTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_mad_is_0_for_positive_statement_balances(self):
        balances = init_balances(
            balance_defs=[
                {"address": "default", "net": "-100"},
                {"address": "mad_balance", "net": "10"},
            ]
        )

        mock_vault = self.create_mock(
            balance_ts=balances,
            minimum_amount_due=Decimal("100"),
            minimum_percentage_due='{"purchase": "0.111111"}',
        )

        expected_calls = [
            override_info_balance_call(
                delta_amount="10",
                amount="0",
                info_balance="MAD_BALANCE",
                increase=False,
            )
        ]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_mad_capped_at_statement_balance_when_fixed_amount(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_charged", "net": "500"},
            ]
        )

        expected_calls = [
            override_info_balance_call(
                delta_amount="1500",
                amount="1500.00",
                info_balance="MAD_BALANCE",
                increase=True,
            )
        ]

        mock_vault = self.create_mock(balance_ts=balances, minimum_amount_due=Decimal("100000"))

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_mad_capped_at_statement_balance_when_percentage_amount(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_charged", "net": "500"},
            ]
        )

        expected_calls = [
            override_info_balance_call(
                delta_amount="1500",
                amount="1500.00",
                info_balance="MAD_BALANCE",
                increase=True,
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            minimum_amount_due=Decimal("100"),
            minimum_percentage_due=dumps(
                {
                    "purchase": "1.1",
                    "cash_advance": "1.1",
                    "interest": "1.0",
                    "transfer": "1.0",
                    "fees": "1.0",
                    "balance_transfer": "1.1",
                }
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_mad_set_to_fixed_amount_when_larger_than_txn_type_percentages(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_charged", "net": "500"},
            ]
        )

        expected_calls = [
            override_info_balance_call(
                delta_amount="1000",
                amount="1000.00",
                info_balance="MAD_BALANCE",
                increase=True,
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            minimum_amount_due=Decimal("1000"),
            minimum_percentage_due=dumps(
                {
                    "balance_transfer": "0.1",
                    "purchase": "0.1",
                    "cash_advance": "0.2",
                    "transfer": "0.1",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_mad_set_to_pct_amount_when_larger_than_fixed_amount(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_charged", "net": "500"},
                {"address": "cash_advance_charged", "net": "500"},
            ]
        )

        expected_calls = [
            override_info_balance_call(
                delta_amount="150",
                amount="150",
                info_balance="MAD_BALANCE",
                increase=True,
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            minimum_amount_due=Decimal("100"),
            minimum_percentage_due=dumps(
                {
                    "balance_transfer": "0.1",
                    "purchase": "0.1",
                    "cash_advance": "0.2",
                    "transfer": "0.1",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_mad_set_to_statement_balance_when_flag_populated_on_account(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_charged", "net": "500"},
            ]
        )

        expected_calls = [
            override_info_balance_call(
                delta_amount="1500",
                amount="1500.00",
                info_balance="MAD_BALANCE",
                increase=True,
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            mad_as_full_statement_flags=dumps(["mad_eq_statement"]),
            # The flag must be present before cut-off
            flags_ts={"mad_eq_statement": [(DEFAULT_DATE - timedelta(hours=1), True)]},
            minimum_amount_due=Decimal("100"),
            minimum_percentage_due=dumps(
                {
                    "purchase": "0.1",
                    "cash_advance": "0.1",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_mad_set_to_zero_if_mad_equal_to_zero_flag(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_charged", "net": "500"},
            ]
        )
        unexpected_calls = [
            override_info_balance_call(
                delta_amount=ANY,
                amount=ANY,
                info_balance="MAD_BALANCE",
            )
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            mad_equal_to_zero_flags='["REPAYMENT_HOLIDAY"]',
            flags_ts={"REPAYMENT_HOLIDAY": [(DEFAULT_DATE - timedelta(days=1), True)]},
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

        expected_mad = Decimal("0")
        actual_mad = run(
            self.smart_contract,
            "_calculate_mad",
            mock_vault,
            vault=mock_vault,
            in_flight_balances=balances.latest(),
            denomination=DEFAULT_DENOM,
            txn_types={
                "CASH_ADVANCE": None,
                "PURCHASE": None,
                "BALANCE_TRANSFER": ["REF1", "REF2"],
            },
            effective_date=DEFAULT_DATE,
            statement_amount=1500,
        )
        self.assertEqual(expected_mad, actual_mad)


class ScodOverlimitTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_overlimit_fee_charged_on_scod_updates_outstanding_balances(self):
        overlimit_opt_in = "True"
        overlimit_fee = "100"
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "60"},
                {"address": "outstanding_balance", "net": "60"},
                {"address": "full_outstanding_balance", "net": "60"},
            ]
        )

        expected_calls = [
            override_info_balance_call(
                overlimit_fee, "160", info_balance=OUTSTANDING, increase=True
            ),
            override_info_balance_call(
                overlimit_fee, "160", info_balance=FULL_OUTSTANDING, increase=True
            ),
        ]

        # by setting the limit to 50 we ensure that all the principal buckets are included for the
        # account to be considered overdue
        mock_vault = self.create_mock(
            balance_ts=balances,
            overlimit_fee=Decimal(overlimit_fee),
            credit_limit=Decimal("50"),
            overlimit_opt_in=overlimit_opt_in,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_overlimit_fee_charged_on_scod_triggers_gl_postings(self):
        overlimit_opt_in = "True"
        overlimit_fee = "100"
        credit_limit = "50"
        # by setting the limit to 50 we ensure that all the principal buckets are included for the
        # account to be considered overdue
        balances = init_balances(balance_defs=[{"address": "purchase_billed", "net": "60"}])

        expected_calls = [
            fee_loan_to_income_call(amount=overlimit_fee, fee_type="OVERLIMIT_FEE"),
        ]
        # being overlimit means we are also extra limit, so there can never be off-bs postings
        unexpected_calls = [charge_fee_off_bs_call(amount=ANY, fee_type="OVERLIMIT_FEE")]

        mock_vault = self.create_mock(
            balance_ts=balances,
            overlimit_fee=Decimal(overlimit_fee),
            credit_limit=Decimal(credit_limit),
            overlimit_opt_in=overlimit_opt_in,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls, unexpected_calls)

    def test_overlimit_fee_not_charged_if_principal_amount_exceeds_credit_limit_and_opt_out(
        self,
    ):
        overlimit_opt_in = "False"
        overlimit_fee = "100"
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "10"},
                {"address": "purchase_charged", "net": "10"},
                {"address": "purchase_unpaid", "net": "10"},
                {"address": "cash_advance_billed", "net": "10"},
                {"address": "cash_advance_charged", "net": "10"},
                {"address": "cash_advance_unpaid", "net": "10"},
                {"address": "outstanding_balance", "net": "60"},
                {"address": "full_outstanding_balance", "net": "60"},
            ]
        )

        unexpected_calls = [
            fee_rebalancing_call(overlimit_fee, fee_type="OVERLIMIT_FEE", from_address=ANY)
        ]

        # by setting the limit to 50 we ensure that all the principal buckets are included for the
        # account to be considered overdue
        mock_vault = self.create_mock(
            balance_ts=balances,
            overlimit_fee=Decimal(overlimit_fee),
            credit_limit=Decimal("50"),
            overlimit_opt_in=overlimit_opt_in,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_overlimit_fee_not_charged_if_auth_amount_exceeds_credit_limit_and_opt_in(
        self,
    ):
        overlimit_opt_in = "False"
        overlimit_fee = "100"

        balances = init_balances(
            balance_defs=[
                {"address": "purchase_auth", "net": "60"},
                {"address": "purchase_charged", "net": "10"},
                {"address": "outstanding_balance", "net": "10"},
                {"address": "full_outstanding_balance", "net": "10"},
            ]
        )

        unexpected_calls = [
            fee_rebalancing_call(overlimit_fee, fee_type="OVERLIMIT_FEE", from_address=ANY)
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            overlimit_fee=Decimal(overlimit_fee),
            credit_limit=Decimal("50"),
            overlimit_opt_in=overlimit_opt_in,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_overlimit_fee_not_charged_on_scod_if_bank_charges_exceeds_credit_limit(
        self,
    ):
        overlimit_opt_in = "False"
        overlimit_fee = "100"

        balances = init_balances(
            balance_defs=[
                {"address": "cash_advance_fees_charged", "net": "10"},
                {"address": "annual_fees_billed", "net": "10"},
                {"address": "overlimit_fees_unpaid", "net": "10"},
                {"address": "purchase_interest_charged", "net": "10"},
                {"address": "purchase_interest_billed", "net": "10"},
                {"address": "purchase_interest_unpaid", "net": "10"},
                {"address": "outstanding_balance", "net": "60"},
                {"address": "full_outstanding_balance", "net": "60"},
            ]
        )
        unexpected_calls = [
            fee_rebalancing_call(overlimit_fee, fee_type="OVERLIMIT_FEE", from_address=ANY)
        ]
        # by setting the limit to 1 we ensure that none of the bank charge buckets are included in
        # the overlimit calculation
        mock_vault = self.create_mock(
            balance_ts=balances,
            overlimit_fee=Decimal(overlimit_fee),
            credit_limit=Decimal("50"),
            overlimit_opt_in=overlimit_opt_in,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_overlimit_fee_not_charged_if_principal_and_bank_charges_exceed_credit_limit(
        self,
    ):
        overlimit_opt_in = "False"
        overlimit_fee = "100"

        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "10"},
                {"address": "purchase_charged", "net": "10"},
                {"address": "purchase_unpaid", "net": "10"},
                {"address": "cash_advance_billed", "net": "10"},
                {"address": "cash_advance_charged", "net": "10"},
                {"address": "cash_advance_interest_billed", "net": "10"},
                {"address": "outstanding_balance", "net": "60"},
                {"address": "full_outstanding_balance", "net": "60"},
            ]
        )

        unexpected_calls = [
            fee_rebalancing_call(overlimit_fee, fee_type="OVERLIMIT_FEE", from_address=ANY)
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            overlimit_fee=Decimal(overlimit_fee),
            credit_limit=Decimal("50"),
            overlimit_opt_in=overlimit_opt_in,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_overlimit_fee_charged_on_scod_if_principal_amount_exceeds_credit_limit(
        self,
    ):
        overlimit_opt_in = "True"
        overlimit_fee = "100"
        balances = init_balances(
            balance_defs=[
                # This balance is not realistic, but proves that charged interest/fees are not used
                {"address": "purchase_interest_charged", "net": "-100"},
                {"address": "cash_advance_fees_billed", "net": "-100"},
                {"address": "purchase_billed", "net": "10"},
                {"address": "purchase_charged", "net": "10"},
                {"address": "purchase_unpaid", "net": "10"},
                {"address": "cash_advance_billed", "net": "10"},
                {"address": "cash_advance_charged", "net": "10"},
                {"address": "cash_advance_unpaid", "net": "10"},
                {"address": "outstanding_balance", "net": "60"},
                {"address": "full_outstanding_balance", "net": "60"},
            ]
        )

        expected_calls = [
            fee_rebalancing_call(overlimit_fee, fee_type="OVERLIMIT_FEE"),
            fee_rebalancing_call(overlimit_fee, fee_type="OVERLIMIT_FEE", from_address="DEFAULT"),
        ]

        # by setting the limit to 50 we ensure that all the principal buckets are included for the
        # account to be considered overdue
        mock_vault = self.create_mock(
            balance_ts=balances,
            overlimit_fee=Decimal(overlimit_fee),
            credit_limit=Decimal("50"),
            overlimit_opt_in=overlimit_opt_in,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)


class ScodTests(LendingContractTest):
    LendingContractTest.contract_file = CONTRACT_FILE

    def test_total_repayments_reset_on_scod_if_non_zero(self):
        balances = init_balances(
            balance_defs=[{"address": "total_repayments_last_statement", "net": "1000"}]
        )

        expected_calls = [
            override_info_balance_call(
                delta_amount="1000",
                amount="0",
                info_balance=TOTAL_REPAYMENTS_LAST_STATEMENT,
                increase=False,
            )
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_total_repayments_not_reset_on_scod_if_zero(self):
        balances = init_balances(
            balance_defs=[{"address": "total_repayments_last_statement", "net": "0"}]
        )
        unexpected_calls = [
            override_info_balance_call(
                delta_amount="1000",
                amount="0",
                info_balance=TOTAL_REPAYMENTS_LAST_STATEMENT,
                increase=False,
            ),
            override_info_balance_call(
                delta_amount="1000",
                amount="0",
                info_balance=TOTAL_REPAYMENTS_LAST_STATEMENT,
                increase=True,
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_transaction_type_statement_buckets_set_on_scod_if_non_zero(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_charged", "net": "2000"},
            ]
        )
        expected_calls = [
            rebalance_statement_bucket_call(Decimal("1000"), "PURCHASE"),
            rebalance_statement_bucket_call(Decimal("2000"), "CASH_ADVANCE"),
        ]
        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_transaction_type_statement_buckets_not_set_on_scod_if_zero(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_charged", "net": "0"},
                {"address": "cash_advance_charged", "net": "0"},
            ]
        )

        mock_vault = self.create_mock(balance_ts=balances)

        unexpected_calls = [
            rebalance_statement_bucket_call(ANY, "PURCHASE"),
            rebalance_statement_bucket_call(ANY, "CASH_ADVANCE"),
        ]

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_interest_statement_buckets_set_on_scod_if_non_zero(self):
        balances = init_balances(
            balance_defs=[
                {"address": "cash_advance_interest_charged", "net": "1000"},
                {"address": "purchase_interest_charged", "net": "2000"},
            ]
        )
        expected_calls = [
            rebalance_statement_bucket_call(Decimal("1000"), "CASH_ADVANCE_INTEREST"),
            rebalance_statement_bucket_call(Decimal("2000"), "PURCHASE_INTEREST"),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_interest_statement_buckets_not_set_on_scod_if_zero(self):
        balances = init_balances(
            balance_defs=[
                {"address": "cash_advance_interest_charged", "net": "0"},
                {"address": "purchase_interest_charged", "net": "0"},
            ]
        )
        unexpected_calls = [
            rebalance_statement_bucket_call(ANY, "PURCHASE_INTEREST"),
            rebalance_statement_bucket_call(ANY, "CASH_ADVANCE_INTEREST"),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_fee_statement_buckets_set_on_scod_if_non_zero(self):
        balances = init_balances(
            balance_defs=[{"address": "overlimit_fees_charged", "net": "1000"}]
        )
        expected_calls = [
            rebalance_statement_bucket_call(Decimal("1000"), "OVERLIMIT_FEES"),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_fee_statement_buckets_not_set_on_scod_if_zero(self):
        balances = init_balances(balance_defs=[{"address": "overlimit_fee_charged", "net": "0"}])
        unexpected_calls = [
            rebalance_statement_bucket_call(ANY, "OVERLIMIT_FEE"),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_external_fee_statement_buckets_set_on_scod_if_non_zero(self):
        balances = init_balances(
            balance_defs=[{"address": "atm_withdrawal_fees_charged", "net": "1000"}]
        )
        expected_calls = [
            rebalance_statement_bucket_call(Decimal("1000"), "ATM_WITHDRAWAL_FEES"),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_external_fee_statement_buckets_not_set_on_scod_if_zero(self):
        balances = init_balances(
            balance_defs=[{"address": "atm_withdrawal_fees_charged", "net": "0"}]
        )
        unexpected_calls = [
            rebalance_statement_bucket_call(ANY, "ATM_WITHDRAWAL_FEES"),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_txn_type_fee_statement_buckets_set_on_scod_if_non_zero(self):
        balances = init_balances(
            balance_defs=[{"address": "cash_advance_fees_charged", "net": "1000"}]
        )
        expected_calls = [rebalance_statement_bucket_call(Decimal("1000"), "CASH_ADVANCE_FEES")]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_txn_type_fee_statement_buckets_not_set_on_scod_if_zero(self):
        balances = init_balances(
            balance_defs=[{"address": "cash_advance_fees_charged", "net": "0"}]
        )
        unexpected_calls = [
            rebalance_statement_bucket_call(ANY, "CASH_ADVANCE_FEES"),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_billed_interest_only_posted_to_internal_account_on_scod_if_non_zero(self):
        credit_limit = Decimal("1500")
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_interest_charged", "net": "1000"},
                {"address": "cash_advance_interest_charged", "net": "500"},
                {"address": "transfer_interest_charged", "net": "0"},
            ]
        )

        expected_calls = [
            bill_interest_air_call(amount="1000", txn_type="purchase"),
            bill_interest_off_bs_call(amount="1000", txn_type="purchase"),
            bill_interest_air_call(amount="500", txn_type="cash_advance"),
            bill_interest_off_bs_call(amount="500", txn_type="cash_advance"),
        ]

        unexpected_calls = [
            bill_interest_air_call(amount=ANY, txn_type="transfer"),
            bill_interest_off_bs_call(amount=ANY, txn_type="transfer"),
        ]

        mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_billed_interest_on_unpaid_fees_posted_to_internal_account_on_scod_if_non_zero(
        self,
    ):
        credit_limit = Decimal("3000")
        balances = init_balances(
            balance_defs=[
                {"address": "annual_fee_interest_charged", "net": "1000"},
                {"address": "cash_advance_fee_interest_charged", "net": "500"},
                {"address": "cash_advance_interest_charged", "net": "600"},
                {"address": "transfer_interest_charged", "net": "0"},
            ]
        )

        expected_calls = [
            bill_interest_air_call(amount="1000", txn_type="annual_fee"),
            bill_interest_off_bs_call(amount="1000", txn_type="annual_fee"),
            bill_interest_air_call(amount="500", txn_type="cash_advance_fee"),
            bill_interest_off_bs_call(amount="500", txn_type="cash_advance_fee"),
            bill_interest_air_call(amount="600", txn_type="cash_advance"),
            bill_interest_off_bs_call(amount="600", txn_type="cash_advance"),
            override_info_balance_call("900", "900", AVAILABLE, True, trigger="billed_interest"),
            override_info_balance_call("2100", "2100", OUTSTANDING, True),
            override_info_balance_call("2100", "2100", FULL_OUTSTANDING, True),
        ]

        unexpected_calls = [
            bill_interest_air_call(amount=ANY, txn_type="transfer"),
            bill_interest_off_bs_call(amount=ANY, txn_type="transfer"),
        ]

        mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    @skip
    def test_billed_interest_extra_limit_causes_gl_postings(self):
        credit_limit = Decimal("400")
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_interest_charged", "net": "1000"},
                {"address": "cash_advance_interest_charged", "net": "500"},
                {"address": "transfer_interest_charged", "net": "0"},
            ]
        )

        expected_calls = [
            bill_interest_air_call(amount="500", txn_type="cash_advance"),
            bill_interest_off_bs_call(amount="400", txn_type="cash_advance"),
            bill_interest_air_call(amount="1000", txn_type="purchase"),
        ]

        unexpected_calls = [
            bill_interest_off_bs_call(amount=ANY, txn_type="purchase"),
            bill_interest_air_call(amount=ANY, txn_type="transfer"),
            bill_interest_off_bs_call(amount=ANY, txn_type="transfer"),
        ]

        mock_vault = self.create_mock(balance_ts=balances, credit_limit=credit_limit)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_statement_balance_reset_to_zero_on_scod_if_no_spend(self):
        balances = init_balances(balance_defs=[{"address": "statement_balance", "net": "1000"}])

        expected_calls = [
            override_info_balance_call(
                delta_amount="1000",
                amount="0",
                info_balance="STATEMENT_BALANCE",
                increase=False,
            )
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_info_balances_set_to_sum_of_new_statement_and_unpaid_spend_and_charges_at_scod(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_charged", "net": "100"},
                {"address": "cash_advance_charged", "net": "100"},
                {"address": "cash_advance_interest_charged", "net": "75"},
                {"address": "purchase_interest_charged", "net": "100"},
                {"address": "cash_advance_fees_charged", "net": "100"},
                {"address": "cash_advance_billed", "net": "100"},
                {"address": "overlimit_fees_billed", "net": "100"},
                {"address": "cash_advance_interest_billed", "net": "50"},
                {"address": "purchase_interest_billed", "net": "100"},
                {"address": "purchase_unpaid", "net": "100"},
                {"address": "purchase_fees_unpaid", "net": "100"},
                {"address": "purchase_interest_unpaid", "net": "100"},
                {"address": "statement_balance", "net": "650"},
                {"address": "outstanding_balance", "net": "650"},
                {"address": "full_outstanding_balance", "net": "1125"},
            ]
        )
        # current statement balance is 650 and we hav extra 475 of new balances that will be billed
        expected_calls = [
            override_info_balance_call("475", "1125", "STATEMENT_BALANCE", True),
            override_info_balance_call("475", "1125", OUTSTANDING, True),
        ]
        # full outstanding doesn't change as it already contained charged interest
        unexpected_calls = [
            override_info_balance_call(ANY, ANY, FULL_OUTSTANDING, True),
            override_info_balance_call(ANY, ANY, FULL_OUTSTANDING, False),
        ]
        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_info_balances_set_to_deposit_balance_at_scod_if_deposit_balance_negative(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "DEFAULT", "net": "500"},
                {"address": "DEPOSIT", "net": "-500"},
            ]
        )

        expected_calls = [
            override_info_balance_call("500", "500", "STATEMENT_BALANCE", increase=True),
            override_info_balance_call("500", "500", OUTSTANDING, increase=True),
            override_info_balance_call("500", "500", FULL_OUTSTANDING, increase=True),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(
            mock_vault,
            expected_calls=expected_calls,
        )

    def test_available_balance_decreased_on_scod_for_billed_interest_and_overlimit_fee(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_interest_charged", "net": "100"},
                {"address": "purchase_interest_billed", "net": "100"},
                {"address": "purchase_billed", "net": "150"},
                {"address": "available_balance", "net": "-150"},
            ]
        )

        expected_calls = [
            override_info_balance_call(
                "110", "-260", AVAILABLE, increase=False, trigger="OVERLIMIT_FEE"
            ),
            override_info_balance_call(
                "100", "-360", AVAILABLE, increase=False, trigger="billed_interest"
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            overlimit_fee=Decimal("110"),
            credit_limit=Decimal("100"),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_available_balance_unchanged_on_scod_if_zero_billed_interest_and_no_overlimit_fee(
        self,
    ):
        balances = init_balances(balance_defs=[{"address": "available_balance", "net": "1000"}])

        unexpected_calls = [
            override_info_balance_call(info_balance=AVAILABLE, increase=False, trigger=ANY),
            override_info_balance_call(info_balance=AVAILABLE, increase=True, trigger=ANY),
        ]

        mock_vault = self.create_mock(balance_ts=balances, overlimit_fee=Decimal("100"))

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_single_posting_batch_instructed_for_scod_processing_with_no_overlimit(
        self,
    ):
        balances = init_balances(balance_defs=[{"address": "purchase_charged", "net": "1000"}])

        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 2, 22),
                client_batch_id=f"SCOD_1-{HOOK_EXECUTION_ID}",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            payment_due_period=21,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=offset_datetime(2019, 2, 22, 0, 0, 2),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls, exact_order=True, exact_match=True
        )

    def test_two_posting_batch_instructed_for_scod_processing_with_overlimit(self):
        balances = init_balances(balance_defs=[{"address": "purchase_charged", "net": "1000"}])

        expected_calls = [
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 2, 28, 23, 59, 59, 999999),
                client_batch_id=f"SCOD_0-{HOOK_EXECUTION_ID}",
            ),
            instruct_posting_batch_call(
                effective_date=offset_datetime(2019, 3, 1),
                client_batch_id=f"SCOD_1-{HOOK_EXECUTION_ID}",
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            credit_limit=Decimal("500"),
            overlimit_fee=Decimal("50"),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=offset_datetime(2019, 3, 1, 0, 0, 2),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls, exact_order=True, exact_match=True
        )

    def test_full_repayment_during_scod_schedule_lag_is_cleaned_up_during_scod_processing(
        self,
    ):
        balances = init_balances(  # SCOD cut-off balances
            dt=offset_datetime(2019, 1, 31, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_fees_charged", "net": "200"},
                {"address": "overlimit_fees_charged", "net": "100"},
            ],
        )

        balances.extend(
            init_balances(  # Balances updated during schedule lag
                dt=offset_datetime(2019, 2, 1, 0, 0, 1),
                balance_defs=[{"address": "total_repayments_last_billed", "net": "1300"}],
            )
        )

        expected_calls = [
            cleanup_address_call(
                amount=1000,
                from_account_address=PURCHASE_NEW,
                to_account_address="PURCHASE_BILLED",
                event=EVENT_SCOD,
            ),
            cleanup_address_call(
                amount=200,
                from_account_address="CASH_ADVANCE_FEES_CHARGED",
                to_account_address="CASH_ADVANCE_FEES_BILLED",
                event=EVENT_SCOD,
            ),
            cleanup_address_call(
                amount=100,
                from_account_address="OVERLIMIT_FEES_CHARGED",
                to_account_address="OVERLIMIT_FEES_BILLED",
                event=EVENT_SCOD,
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=offset_datetime(2019, 2, 1, 0, 0, 2),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_partial_repayment_during_scod_schedule_lag_is_cleaned_up_during_scod_processing(
        self,
    ):
        balances = init_balances(  # SCOD cut-off balances
            dt=offset_datetime(2019, 1, 31, 23, 59, 59, 999999),
            balance_defs=[
                {"address": "purchase_interest_pre_scod_uncharged", "net": "1000"},
                {"address": "purchase_charged", "net": "1000"},
                {"address": "cash_advance_fees_charged", "net": "200"},
                {"address": "overlimit_fees_charged", "net": "100"},
            ],
        )

        balances.extend(
            init_balances(  # Balances updated during schedule lag
                dt=offset_datetime(2019, 2, 1, 0, 0, 1),
                balance_defs=[
                    {"address": "purchase_charged", "net": "700"},
                    {"address": "total_repayments_last_billed", "net": "600"},
                ],
            )
        )

        expected_calls = [
            cleanup_address_call(
                amount=300,
                from_account_address=PURCHASE_NEW,
                to_account_address="PURCHASE_BILLED",
                event=EVENT_SCOD,
            ),
            cleanup_address_call(
                amount=200,
                from_account_address="CASH_ADVANCE_FEES_CHARGED",
                to_account_address="CASH_ADVANCE_FEES_BILLED",
                event=EVENT_SCOD,
            ),
            cleanup_address_call(
                amount=100,
                from_account_address="OVERLIMIT_FEES_CHARGED",
                to_account_address="OVERLIMIT_FEES_BILLED",
                event=EVENT_SCOD,
            ),
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=offset_datetime(2019, 2, 1, 0, 0, 2),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls)

    def test_extra_spend_during_scod_schedule_lag_is_not_cleaned_up_during_scod_processing(
        self,
    ):
        balances = init_balances(  # SCOD cut-off balances
            dt=offset_datetime(2019, 1, 31, 23, 59, 59, 999999),
            balance_defs=[{"address": "purchase_charged", "net": "1000"}],
        )

        balances.extend(
            init_balances(  # Balances updated during schedule lag
                dt=offset_datetime(2019, 2, 1, 0, 0, 1),
                balance_defs=[{"address": "purchase_charged", "net": "1500"}],
            )
        )

        unexpected_calls = [
            cleanup_address_call(
                from_account_address=PURCHASE_NEW,
                to_account_address="PURCHASE_BILLED",
                amount=ANY,
                event=EVENT_SCOD,
            )
        ]

        mock_vault = self.create_mock(balance_ts=balances)

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=offset_datetime(2019, 2, 1, 0, 0, 2),
        )

        self.check_calls_for_vault_methods(mock_vault, unexpected_calls=unexpected_calls)

    def test_statement_period_in_workflow_correct_for_first_scod(self):
        balances = init_balances()

        account_creation_date = offset_datetime(2019, 1, 1)
        last_scod_execution_time = None
        payment_due_period = 21

        posting_instructions = []

        # First SCOD is on 2019-01-31
        expected_calls = [
            publish_statement_workflow_call(
                start_of_statement="2019-01-01",
                end_of_statement="2019-01-31",
                is_final="False",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_creation_date=account_creation_date,
            payment_due_period=payment_due_period,
            posting_instructions=posting_instructions,
            last_scod_execution_time=last_scod_execution_time,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=offset_datetime(2019, 2, 1, 0, 0, 2),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_statement_period_in_workflow_correct_for_second_scod(self):
        balances = init_balances()

        account_creation_date = offset_datetime(2019, 1, 1)
        last_scod_execution_time = offset_datetime(2019, 2, 1, 0, 0, 2)
        last_pdd_execution_time = offset_datetime(2019, 2, 22, 0, 0, 1)
        payment_due_period = 21

        posting_instructions = []

        # First SCOD is on 2019-01-31 so PDD is 21st feb
        # Next PDD is 21st march, so SCOD is 28th Feb
        expected_calls = [
            publish_statement_workflow_call(
                start_of_statement="2019-02-01",
                end_of_statement="2019-02-28",
                is_final="False",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_creation_date=account_creation_date,
            payment_due_period=payment_due_period,
            posting_instructions=posting_instructions,
            last_scod_execution_time=last_scod_execution_time,
            last_pdd_execution_time=last_pdd_execution_time,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=offset_datetime(2019, 3, 1, 0, 0, 2),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_statement_with_no_billed_amounts_has_empty_mad_and_statement_in_workflow(
        self,
    ):
        balances = init_balances()

        account_creation_date = offset_datetime(2019, 1, 1)
        last_scod_execution_time = offset_datetime(2019, 3, 1, 0, 0, 2)
        payment_due_period = 21

        posting_instructions = []

        # First SCOD is on 2019-01-31
        expected_calls = [
            publish_statement_workflow_call(
                mad="0.00",
                statement_amount="0.00",
                is_final="False",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_creation_date=account_creation_date,
            payment_due_period=payment_due_period,
            posting_instructions=posting_instructions,
            last_scod_execution_time=last_scod_execution_time,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=offset_datetime(2019, 4, 1, 0, 0, 2),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_statement_with_billed_amounts_has_non_zero_mad_and_statement_in_workflow(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "PURCHASE_CHARGED", "net": "1000"},
                {"address": "PURCHASE_FEES_CHARGED", "net": "1000"},
            ]
        )

        account_creation_date = offset_datetime(2019, 1, 1)
        last_scod_execution_time = offset_datetime(2019, 3, 1, 0, 0, 2)
        payment_due_period = 21

        posting_instructions = []

        # First SCOD is on 2019-01-31
        expected_calls = [
            publish_statement_workflow_call(
                mad="1010.00",
                statement_amount="2000.00",
                is_final="False",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_creation_date=account_creation_date,
            payment_due_period=payment_due_period,
            posting_instructions=posting_instructions,
            last_scod_execution_time=last_scod_execution_time,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=offset_datetime(2019, 4, 1, 0, 0, 2),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_next_scod_and_pdd_dates_correct_in_statement_workflow(self):
        balances = init_balances()

        account_creation_date = offset_datetime(2019, 1, 1)
        # SCOD is 2019, 1, 31 and schedule on 2019, 2, 1, so PDD falls on 21st with schedule on 22nd
        last_pdd_execution_time = offset_datetime(2019, 3, 22, 0, 0, 2)
        payment_due_period = 21

        posting_instructions = []

        # First SCOD is on 2019-01-31
        expected_calls = [
            publish_statement_workflow_call(
                current_pdd="2019-04-21",
                next_pdd="2019-05-21",
                next_scod="2019-04-30",
                is_final="False",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_creation_date=account_creation_date,
            payment_due_period=payment_due_period,
            posting_instructions=posting_instructions,
            last_pdd_execution_time=last_pdd_execution_time,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=offset_datetime(2019, 4, 1, 0, 0, 2),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_next_scod_and_pdd_dates_correct_in_first_statement_workflow(self):
        balances = init_balances()

        account_creation_date = offset_datetime(2019, 1, 1)
        # SCOD is 2019, 1, 31 and schedule on 2019, 2, 1, so PDD falls on 21st with schedule on 22nd
        last_pdd_execution_time = None
        last_scod_execution_time = None
        payment_due_period = 21

        posting_instructions = []

        # First SCOD is on 2019-01-31
        expected_calls = [
            publish_statement_workflow_call(
                current_pdd="2019-02-21",
                next_pdd="2019-03-21",
                next_scod="2019-02-28",
                is_final="False",
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            account_creation_date=account_creation_date,
            payment_due_period=payment_due_period,
            posting_instructions=posting_instructions,
            last_scod_execution_time=last_scod_execution_time,
            last_pdd_execution_time=last_pdd_execution_time,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=offset_datetime(2019, 2, 1, 0, 0, 2),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_scod_with_txn_level_refs(self):
        credit_limit = Decimal("5000")
        balances = init_balances(
            balance_defs=[
                {"address": "balance_transfer_ref1_interest_charged", "net": "10"},
                {"address": "balance_transfer_ref2_interest_charged", "net": "20"},
                {"address": "balance_transfer_ref1_charged", "net": "600"},
                {"address": "balance_transfer_ref2_charged", "net": "800"},
                {"address": "purchase_charged", "net": "200"},
                {"address": "purchase_interest_charged", "net": "2"},
            ]
        )

        # Mad should be 10 + 2 + 0.2 *(200) + 0.3 * (600 + 800)= 472

        expected_calls = [
            bill_interest_air_call(amount="10", txn_type="balance_transfer", txn_ref="ref1"),
            bill_interest_air_call(amount="20", txn_type="balance_transfer", txn_ref="REF2"),
            bill_interest_air_call(amount="2", txn_type="purchase"),
            override_info_balance_call(
                delta_amount="492",
                amount="492",
                info_balance="MAD_BALANCE",
                increase=True,
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            credit_limit=credit_limit,
            transaction_types=dumps(
                {
                    "purchase": {},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "REF2"]}),
            base_interest_rates=dumps({"purchase": "0.2"}),
            transaction_base_interest_rates=dumps(
                {"balance_transfer": {"REF1": "0.25", "REF2": "0.35"}}
            ),
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {"REF1": "0.4", "REF2": "0.5"}}
            ),
            minimum_percentage_due=dumps(
                {
                    "purchase": "0.2",
                    "balance_transfer": "0.3",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_mad_calculations_with_principal_interest(self):
        credit_limit = Decimal("5000")
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "200"},
                {"address": "purchase_interest_billed", "net": "2"},
            ]
        )

        # Mad should be  2 + 0.2 *(200)= 42

        expected_calls = [
            override_info_balance_call(
                delta_amount="42",
                amount="42",
                info_balance="MAD_BALANCE",
                increase=True,
            )
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            credit_limit=credit_limit,
            transaction_references=dumps({}),
            transaction_types=dumps({"purchase": {}}),
            base_interest_rates=dumps({"purchase": "0.2"}),
            minimum_percentage_due=dumps({"purchase": "0.2", "interest": "1.0", "fees": "1.0"}),
            minimum_amount_due=Decimal(15),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_SCOD,
            effective_date=DEFAULT_DATE,
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)


class InterestFreePeriodTests(LendingContractTest):
    def test_interest_free_period_interest_zeroed_if_outstanding_statement_balance_paid_by_pdd(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "0"},
                {
                    "address": "purchase_interest_free_period_interest_uncharged",
                    "net": "110",
                },
                {"address": "purchase_interest_post_scod_uncharged", "net": "100"},
                {
                    "address": "cash_advance_interest_free_period_interest_uncharged",
                    "net": "100",
                },
                {"address": "cash_advance_interest_charged", "net": "90"},
                {
                    "address": "balance_transfer_ref1_interest_free_period_interest_uncharged",
                    "net": "80",
                },
                {
                    "address": "balance_transfer_ref1_interest_post_scod_uncharged",
                    "net": "70",
                },
            ]
        )

        # alias trigger to shorter form for linter purposes
        REVERSE_IFPIU = "REVERSE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"

        # We expect to see INTEREST_FREE_PERIOD_INTEREST_UNCHARGED and INTEREST_UNCHARGED
        # to be zeroed out
        expected_calls = [
            reverse_uncharged_interest_call(
                amount="110",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            reverse_uncharged_interest_call(
                amount="100",
                txn_type="PURCHASE",
                trigger="OUTSTANDING_REPAID",
                accrual_type="POST_SCOD",
            ),
            reverse_uncharged_interest_call(
                amount="100",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            reverse_uncharged_interest_call(
                amount="80",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            reverse_uncharged_interest_call(
                amount="70",
                txn_type="BALANCE_TRANSFER",
                trigger="OUTSTANDING_REPAID",
                txn_ref="REF1",
                accrual_type="POST_SCOD",
            ),
            instruct_posting_batch_call(
                client_batch_id="ZERO_OUT_ACCRUED_INTEREST-hook_execution_id",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        unexpected_calls = [
            charge_interest_call(amount="110", txn_type="PURCHASE"),
            charge_interest_call(amount="100", txn_type="CASH_ADVANCE"),
            charge_interest_call(amount="80", txn_type="BALANCE_TRANSFER", ref="REF1"),
            instruct_posting_batch_call(
                client_batch_id=f"PDD-{HOOK_EXECUTION_ID}",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2020-12-31 12:00:00",
                    "purchase": "2020-12-31 12:00:00",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {"balance_transfer": {"REF1": "2020-12-31 12:00:00"}}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_free_period_interest_zeroed_if_mad_paid_by_pdd_accrue_from_txn_day(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "3000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "10"},
                {
                    "address": "purchase_interest_free_period_interest_uncharged",
                    "net": "110",
                },
                {"address": "purchase_interest_post_scod_uncharged", "net": "100"},
                {
                    "address": "cash_advance_interest_free_period_interest_uncharged",
                    "net": "100",
                },
                {"address": "cash_advance_interest_charged", "net": "90"},
                {
                    "address": "balance_transfer_ref1_interest_free_period_interest_uncharged",
                    "net": "80",
                },
                {
                    "address": "balance_transfer_ref1_interest_post_scod_uncharged",
                    "net": "70",
                },
            ]
        )

        # alias trigger to shorter form for linter purposes
        REVERSE_IFPIU = "REVERSE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"

        # We expect to see INTEREST_FREE_PERIOD_INTEREST_UNCHARGED zeroed out,
        # and INTEREST_UNCHARGED accrued outside interest free periods are moved to CHARGED.
        expected_calls = [
            charge_interest_call(
                amount="100", txn_type="PURCHASE", accrual_type_in_trigger="POST_SCOD"
            ),
            reverse_uncharged_interest_call(
                amount="110",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            reverse_uncharged_interest_call(
                amount="100",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            reverse_uncharged_interest_call(
                amount="80",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            charge_interest_call(
                amount="70",
                txn_type="BALANCE_TRANSFER",
                ref="REF1",
                accrual_type_in_trigger="POST_SCOD",
            ),
            instruct_posting_batch_call(
                client_batch_id=f"PDD-{HOOK_EXECUTION_ID}",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        unexpected_calls = [
            charge_interest_call(amount="110", txn_type="PURCHASE"),
            charge_interest_call(amount="100", txn_type="CASH_ADVANCE"),
            charge_interest_call(amount="80", txn_type="BALANCE_TRANSFER", ref="REF1"),
            instruct_posting_batch_call(
                client_batch_id="ZERO_OUT_ACCRUED_INTEREST-hook_execution_id",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2020-12-31 12:00:00",
                    "purchase": "2020-12-31 12:00:00",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {"balance_transfer": {"REF1": "2020-12-31 12:00:00"}}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_free_period_interest_zeroed_if_mad_paid_by_pdd(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "3000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "10"},
                {
                    "address": "purchase_interest_free_period_interest_uncharged",
                    "net": "110",
                },
                {"address": "purchase_interest_uncharged", "net": "100"},
                {
                    "address": "cash_advance_interest_free_period_interest_uncharged",
                    "net": "100",
                },
                {"address": "cash_advance_interest_charged", "net": "90"},
                {
                    "address": "balance_transfer_ref1_interest_free_period_interest_uncharged",
                    "net": "80",
                },
                {"address": "balance_transfer_ref1_interest_uncharged", "net": "70"},
            ]
        )

        # alias trigger to shorter form for linter purposes
        REVERSE_IFPIU = "REVERSE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"

        # We expect to see INTEREST_FREE_PERIOD_INTEREST_UNCHARGED zeroed out,
        # and INTEREST_UNCHARGED accrued outside interest free periods are moved to CHARGED.
        expected_calls = [
            charge_interest_call(amount="100", txn_type="PURCHASE"),
            reverse_uncharged_interest_call(
                amount="110",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            reverse_uncharged_interest_call(
                amount="100",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            reverse_uncharged_interest_call(
                amount="80",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            charge_interest_call(amount="70", txn_type="BALANCE_TRANSFER", ref="REF1"),
            instruct_posting_batch_call(
                client_batch_id=f"PDD-{HOOK_EXECUTION_ID}",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        unexpected_calls = [
            charge_interest_call(amount="110", txn_type="PURCHASE"),
            charge_interest_call(amount="100", txn_type="CASH_ADVANCE"),
            charge_interest_call(amount="80", txn_type="BALANCE_TRANSFER", ref="REF1"),
            instruct_posting_batch_call(
                client_batch_id="ZERO_OUT_ACCRUED_INTEREST-hook_execution_id",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2020-12-31 12:00:00",
                    "purchase": "2020-12-31 12:00:00",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {"balance_transfer": {"REF1": "2020-12-31 12:00:00"}}
            ),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_free_period_interest_charged_if_mad_unpaid_by_pdd_accrue_from_txn_day(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "3000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "0"},
                {
                    "address": "purchase_interest_free_period_interest_uncharged",
                    "net": "110",
                },
                {"address": "purchase_interest_post_scod_uncharged", "net": "100"},
                {
                    "address": "cash_advance_interest_free_period_interest_uncharged",
                    "net": "100",
                },
                {"address": "cash_advance_interest_charged", "net": "90"},
                {
                    "address": "balance_transfer_ref1_interest_free_period_interest_uncharged",
                    "net": "80",
                },
                {
                    "address": "balance_transfer_ref1_interest_post_scod_uncharged",
                    "net": "70",
                },
            ]
        )

        # alias trigger to shorter form for linter purposes
        REVERSE_IFPIU = "REVERSE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"

        # We expect to see INTEREST_FREE_PERIOD_INTEREST_UNCHARGED and INTEREST_UNCHARGED
        # moved to CHARGED.
        expected_calls = [
            charge_interest_call(
                amount="100", txn_type="PURCHASE", accrual_type_in_trigger="POST_SCOD"
            ),
            charge_interest_call(
                amount="110", txn_type="PURCHASE", charge_interest_free_period=True
            ),
            charge_interest_call(
                amount="100", txn_type="CASH_ADVANCE", charge_interest_free_period=True
            ),
            charge_interest_call(
                amount="70",
                txn_type="BALANCE_TRANSFER",
                ref="REF1",
                accrual_type_in_trigger="POST_SCOD",
            ),
            charge_interest_call(
                amount="80",
                txn_type="BALANCE_TRANSFER",
                ref="REF1",
                charge_interest_free_period=True,
            ),
            reverse_uncharged_interest_call(
                amount="110",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            reverse_uncharged_interest_call(
                amount="100",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            reverse_uncharged_interest_call(
                amount="80",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            instruct_posting_batch_call(
                client_batch_id=f"PDD-{HOOK_EXECUTION_ID}",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2020-12-31 12:00:00",
                    "purchase": "2020-12-31 12:00:00",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {"balance_transfer": {"REF1": "2020-12-31 12:00:00"}}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_interest_free_period_interest_charged_if_mad_unpaid_by_pdd(self):
        balances = init_balances(
            balance_defs=[
                {"address": "purchase_billed", "net": "3000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "0"},
                {
                    "address": "purchase_interest_free_period_interest_uncharged",
                    "net": "110",
                },
                {"address": "purchase_interest_uncharged", "net": "100"},
                {
                    "address": "cash_advance_interest_free_period_interest_uncharged",
                    "net": "100",
                },
                {"address": "cash_advance_interest_charged", "net": "90"},
                {
                    "address": "balance_transfer_ref1_interest_free_period_interest_uncharged",
                    "net": "80",
                },
                {"address": "balance_transfer_ref1_interest_uncharged", "net": "70"},
            ]
        )

        # alias trigger to shorter form for linter purposes
        REVERSE_IFPIU = "REVERSE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"

        # We expect to see INTEREST_FREE_PERIOD_INTEREST_UNCHARGED and INTEREST_UNCHARGED
        # moved to CHARGED.
        expected_calls = [
            charge_interest_call(amount="100", txn_type="PURCHASE"),
            charge_interest_call(
                amount="110", txn_type="PURCHASE", charge_interest_free_period=True
            ),
            charge_interest_call(
                amount="100", txn_type="CASH_ADVANCE", charge_interest_free_period=True
            ),
            charge_interest_call(amount="70", txn_type="BALANCE_TRANSFER", ref="REF1"),
            charge_interest_call(
                amount="80",
                txn_type="BALANCE_TRANSFER",
                ref="REF1",
                charge_interest_free_period=True,
            ),
            reverse_uncharged_interest_call(
                amount="110",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            reverse_uncharged_interest_call(
                amount="100",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            reverse_uncharged_interest_call(
                amount="80",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                trigger=REVERSE_IFPIU,
            ),
            instruct_posting_batch_call(
                client_batch_id=f"PDD-{HOOK_EXECUTION_ID}",
                effective_date=offset_datetime(2019, 2, 25),
            ),
        ]

        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2020-12-31 12:00:00",
                    "purchase": "2020-12-31 12:00:00",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {"balance_transfer": {"REF1": "2020-12-31 12:00:00"}}
            ),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_PDD,
            effective_date=offset_datetime(2019, 2, 25),
        )

        self.check_calls_for_vault_methods(mock_vault, expected_calls=expected_calls)

    def test_interest_free_period_no_interest_if_not_revolver_no_outstanding_statment_balance(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "cash_advance_billed", "net": "0"},
                {"address": "cash_advance_charged", "net": "200"},
                {"address": "purchase_billed", "net": "0"},
                {"address": "purchase_charged", "net": "3000"},
                {"address": "balance_transfer_ref1_billed", "net": "0"},
                {"address": "balance_transfer_ref1_charged", "net": "5000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "0"},
                {"address": "revolver", "net": "0"},
            ]
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"

        # Outstanding balance stays at 8200
        expected_calls = [
            override_info_balance_call(
                delta_amount="8200",
                info_balance=FULL_OUTSTANDING,
                trigger="ACCRUE_INTEREST",
            )
        ]
        # We expect to not see any charge interest/ accrue interest calls as all
        # transaction types have active interest free periods
        unexpected_calls = [
            charge_interest_call(txn_type="CASH_ADVANCE"),
            charge_interest_call(txn_type="PURCHASE"),
            charge_interest_call(txn_type="BALANCE_TRANSFER", ref="REF1"),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            annual_percentage_rate=dumps({"cash_advance": "4", "purchase": "1"}),
            transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "3"}}),
            base_interest_rates=f'{{"purchase":{purchase_rate}, "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"REF1":{bt_ref1_rate} }}}}',
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2020-12-31 12:00:00",
                    "purchase": "2020-12-31 12:00:00",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {"balance_transfer": {"REF1": "2020-12-31 12:00:00"}}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_free_period_accrue_uncharged_interest_if_revolver_before_pdd(
        self,
    ):
        # Have a mix of unpaid & new charges
        balances = init_balances(
            balance_defs=[
                {"address": "cash_advance_charged", "net": "200"},
                {"address": "purchase_unpaid", "net": "3000"},
                {"address": "balance_transfer_ref1_charged", "net": "5000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "0"},
                {"address": "revolver", "net": "-1"},
            ]
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"

        # Accrue interest free period uncharged interest for all transaction types
        # as they all have active interest free periods
        expected_calls = [
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
            override_info_balance_call(
                delta_amount="8200",
                info_balance=FULL_OUTSTANDING,
                trigger="ACCRUE_INTEREST",
            ),
        ]
        # We expect to not see any charge interest calls
        unexpected_calls = [
            charge_interest_call(txn_type="CASH_ADVANCE"),
            charge_interest_call(txn_type="PURCHASE"),
            charge_interest_call(txn_type="BALANCE_TRANSFER", ref="REF1"),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            annual_percentage_rate=dumps({"cash_advance": "4", "purchase": "1"}),
            transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "3"}}),
            base_interest_rates=f'{{"purchase":{purchase_rate}, "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"REF1":{bt_ref1_rate} }}}}',
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2020-12-31 12:00:00",
                    "purchase": "2020-12-31 12:00:00",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {"balance_transfer": {"REF1": "2020-12-31 12:00:00"}}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 2, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_free_period_no_interest_if_revolver_after_pdd(self):
        # Have a mix of unpaid & new charges
        balances = init_balances(
            balance_defs=[
                {"address": "cash_advance_charged", "net": "200"},
                {"address": "purchase_charged", "net": "3000"},
                {"address": "balance_transfer_ref1_unpaid", "net": "5000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "0"},
                {"address": "revolver", "net": "-1"},
            ]
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"

        # Outstanding balance stays at 8200
        expected_calls = [
            override_info_balance_call(
                delta_amount="8200",
                info_balance=FULL_OUTSTANDING,
                trigger="ACCRUE_INTEREST",
            )
        ]
        # We expect to not see any charge interest/ accrue interest calls as all
        # transaction types have active interest free periods
        unexpected_calls = [
            charge_interest_call(txn_type="CASH_ADVANCE"),
            charge_interest_call(txn_type="PURCHASE"),
            charge_interest_call(txn_type="BALANCE_TRANSFER", ref="REF1"),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            annual_percentage_rate=dumps({"cash_advance": "4", "purchase": "1"}),
            transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "3"}}),
            base_interest_rates=f'{{"purchase":{purchase_rate}, "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"REF1":{bt_ref1_rate} }}}}',
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2020-12-31 12:00:00",
                    "purchase": "2020-12-31 12:00:00",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {"balance_transfer": {"REF1": "2020-12-31 12:00:00"}}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_free_period_accrue_uncharged_if_outstanding_statement_balance_before_pdd(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "cash_advance_billed", "net": "200"},
                {"address": "purchase_billed", "net": "3000"},
                {"address": "balance_transfer_ref1_billed", "net": "5000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "8200"},
                {"address": "revolver", "net": "0"},
            ]
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"

        # Accrue interest free period uncharged interest for all transaction types
        # as they all have active interest free periods
        expected_calls = [
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
            override_info_balance_call(
                delta_amount="8200",
                info_balance=FULL_OUTSTANDING,
                trigger="ACCRUE_INTEREST",
            ),
        ]
        # We expect to not see any charge interest calls
        unexpected_calls = [
            charge_interest_call(txn_type="CASH_ADVANCE"),
            charge_interest_call(txn_type="PURCHASE"),
            charge_interest_call(txn_type="BALANCE_TRANSFER", ref="REF1"),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            annual_percentage_rate=dumps({"cash_advance": "4", "purchase": "1"}),
            transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "3"}}),
            base_interest_rates=f'{{"purchase":{purchase_rate}, "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"REF1":{bt_ref1_rate} }}}}',
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2020-12-31 12:00:00",
                    "purchase": "2020-12-31 12:00:00",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {"balance_transfer": {"REF1": "2020-12-31 12:00:00"}}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 2, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_free_period_no_interest_if_outstanding_statement_balance_after_pdd(
        self,
    ):
        # We generally expect is_revolver to be True in this case
        balances = init_balances(
            balance_defs=[
                {"address": "cash_advance_billed", "net": "200"},
                {"address": "purchase_billed", "net": "3000"},
                {"address": "balance_transfer_ref1_billed", "net": "5000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "8200"},
            ]
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"

        # Outstanding balance stays at 8200
        expected_calls = [
            override_info_balance_call(
                delta_amount="8200",
                info_balance=FULL_OUTSTANDING,
                trigger="ACCRUE_INTEREST",
            )
        ]
        # We expect to not see any charge interest/ accrue interest calls as all
        # transaction types have active interest free periods
        unexpected_calls = [
            charge_interest_call(txn_type="CASH_ADVANCE"),
            charge_interest_call(txn_type="PURCHASE"),
            charge_interest_call(txn_type="BALANCE_TRANSFER", ref="REF1"),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            annual_percentage_rate=dumps({"cash_advance": "4", "purchase": "1"}),
            transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "3"}}),
            base_interest_rates=f'{{"purchase":{purchase_rate}, "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"REF1":{bt_ref1_rate} }}}}',
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2020-12-31 12:00:00",
                    "purchase": "2020-12-31 12:00:00",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {"balance_transfer": {"REF1": "2020-12-31 12:00:00"}}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_int_free_period_if_expired_and_outstanding_stmnt_bal_before_pdd_accrue_from_txn_day(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "cash_advance_billed", "net": "200"},
                {"address": "purchase_billed", "net": "3000"},
                {"address": "balance_transfer_ref1_billed", "net": "5000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "8200"},
                {"address": "revolver", "net": "0"},
            ]
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"

        # As all interest free periods are expired, we just have normal behaviour here
        # I.e. charge interest on txn types with charge_interest_from_transaction_date=True
        # accrue uncharged interest on txn types with charge_interest_from_transaction_date=False
        expected_calls = [
            charge_interest_call(amount="0.11", txn_type="CASH_ADVANCE"),
            charge_interest_call(amount="4.66", txn_type="BALANCE_TRANSFER", ref="REF1"),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
                accrual_type="POST_SCOD",
            ),
            override_info_balance_call(
                delta_amount="8204.77",
                info_balance=FULL_OUTSTANDING,
                trigger="ACCRUE_INTEREST",
            ),
        ]
        unexpected_calls = [
            charge_interest_call(txn_type="PURCHASE"),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            annual_percentage_rate=dumps({"cash_advance": "4", "purchase": "1"}),
            transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "3"}}),
            base_interest_rates=f'{{"purchase":{purchase_rate}, "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"REF1":{bt_ref1_rate} }}}}',
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2018-12-31 12:00:00",
                    "purchase": "2018-12-31 12:00:00",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {"balance_transfer": {"REF1": "2018-12-31 12:00:00"}}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 2, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_free_period_interest_if_expired_and_outstanding_statement_balance_before_pdd(
        self,
    ):
        balances = init_balances(
            balance_defs=[
                {"address": "cash_advance_billed", "net": "200"},
                {"address": "purchase_billed", "net": "3000"},
                {"address": "balance_transfer_ref1_billed", "net": "5000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "8200"},
                {"address": "revolver", "net": "0"},
            ]
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"

        # As all interest free periods are expired, we just have normal behaviour here
        # I.e. charge interest on txn types with charge_interest_from_transaction_date=True
        # accrue uncharged interest on txn types with charge_interest_from_transaction_date=False
        expected_calls = [
            charge_interest_call(amount="0.11", txn_type="CASH_ADVANCE"),
            charge_interest_call(amount="4.66", txn_type="BALANCE_TRANSFER", ref="REF1"),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            override_info_balance_call(
                delta_amount="8204.77",
                info_balance=FULL_OUTSTANDING,
                trigger="ACCRUE_INTEREST",
            ),
        ]
        unexpected_calls = [
            charge_interest_call(txn_type="PURCHASE"),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            annual_percentage_rate=dumps({"cash_advance": "4", "purchase": "1"}),
            transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "3"}}),
            base_interest_rates=f'{{"purchase":{purchase_rate}, "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"REF1":{bt_ref1_rate} }}}}',
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2018-12-31 12:00:00",
                    "purchase": "2018-12-31 12:00:00",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {"balance_transfer": {"REF1": "2018-12-31 12:00:00"}}
            ),
            accrue_interest_from_txn_day=False,
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 2, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_free_period_interest_accrued_if_expired_and_revolver_after_pdd(
        self,
    ):
        # Have a mix of unpaid and new charges
        balances = init_balances(
            balance_defs=[
                {"address": "cash_advance_unpaid", "net": "200"},
                {"address": "purchase_charged", "net": "3000"},
                {"address": "balance_transfer_ref1_charged", "net": "5000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "0"},
                {"address": "revolver", "net": "-1"},
            ]
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"

        # As all interest free periods are expired, we just have normal behaviour here
        # I.e. charge interest on all txn types
        expected_calls = [
            charge_interest_call(amount="0.11", txn_type="CASH_ADVANCE"),
            charge_interest_call(amount="0.82", txn_type="PURCHASE"),
            charge_interest_call(amount="4.66", txn_type="BALANCE_TRANSFER", ref="REF1"),
            override_info_balance_call(
                delta_amount="8205.59",
                info_balance=FULL_OUTSTANDING,
                trigger="ACCRUE_INTEREST",
            ),
        ]
        # Interest is charged directly as we are in revolver
        unexpected_calls = [
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1"]}),
            annual_percentage_rate=dumps({"cash_advance": "4", "purchase": "1"}),
            transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "3"}}),
            base_interest_rates=f'{{"purchase":{purchase_rate}, "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"REF1":{bt_ref1_rate}}}}}',
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2018-12-31 12:00:00",
                    "purchase": "2018-12-31 12:00:00",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {"balance_transfer": {"REF1": "2018-12-31 12:00:00"}}
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 1),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_interest_free_period_expiry_second_precision(self):
        # Have a mix of unpaid and new charges
        balances = init_balances(
            balance_defs=[
                {"address": "cash_advance_unpaid", "net": "200"},
                {"address": "purchase_charged", "net": "3000"},
                {"address": "balance_transfer_ref1_charged", "net": "5000"},
                {"address": "balance_transfer_ref2_unpaid", "net": "1000"},
                {"address": "mad_balance", "net": "100"},
                {"address": "total_repayments_last_billed", "net": "0"},
                {"address": "revolver", "net": "-1"},
            ]
        )

        purchase_rate = "0.1"
        cash_adv_rate = "0.2"
        bt_ref1_rate = "0.34"
        bt_ref2_rate = "0.44"

        # For transaction types with expired interest free periods, expect to see interest charged
        # directly, since we are in revolver
        expected_calls = [
            charge_interest_call(amount="0.11", txn_type="CASH_ADVANCE"),
            charge_interest_call(amount="4.66", txn_type="BALANCE_TRANSFER", ref="REF1"),
            override_info_balance_call(
                delta_amount="9204.77",
                info_balance=FULL_OUTSTANDING,
                trigger="ACCRUE_INTEREST",
            ),
        ]
        # For transaction types that have active interest free periods, see that no interest
        # is charged/ accrued
        unexpected_calls = [
            charge_interest_call(amount="0.82", txn_type="PURCHASE"),
            charge_interest_call(amount="1.21", txn_type="BALANCE_TRANSFER", ref="REF2"),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.11",
                txn_type="CASH_ADVANCE_INTEREST_FREE_PERIOD",
                balance=200,
                daily_rate=Decimal(cash_adv_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="0.82",
                txn_type="PURCHASE_INTEREST_FREE_PERIOD",
                balance=3000,
                daily_rate=Decimal(purchase_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="4.66",
                txn_type="BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD",
                balance=5000,
                daily_rate=Decimal(bt_ref1_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="1.21",
                txn_type="BALANCE_TRANSFER_REF2",
                balance=1000,
                daily_rate=Decimal(bt_ref2_rate) * 100 / 365,
            ),
            accrue_interest_call(
                amount="1.21",
                txn_type="BALANCE_TRANSFER_REF2_INTEREST_FREE_PERIOD",
                balance=1000,
                daily_rate=Decimal(bt_ref2_rate) * 100 / 365,
            ),
        ]
        mock_vault = self.create_mock(
            balance_ts=balances,
            last_scod_execution_time=offset_datetime(2019, 2, 1),
            transaction_types=dumps(
                {
                    "purchase": {},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                }
            ),
            transaction_references=dumps({"balance_transfer": ["REF1", "ref2"]}),
            annual_percentage_rate=dumps({"cash_advance": "4", "purchase": "1"}),
            transaction_annual_percentage_rate=dumps(
                {"balance_transfer": {"REF1": "3", "ref2": "2"}}
            ),
            base_interest_rates=f'{{"purchase":{purchase_rate}, "cash_advance": {cash_adv_rate}}}',
            transaction_base_interest_rates=f'{{"balance_transfer": {{"REF1":{bt_ref1_rate} , '
            f'"ref2": {bt_ref2_rate}}}}}',
            interest_free_expiry=dumps(
                {
                    "cash_advance": "2019-02-24 23:59:59",
                    "purchase": "2019-02-25 00:00:01",
                }
            ),
            transaction_interest_free_expiry=dumps(
                {
                    "balance_transfer": {
                        "REF1": "2019-02-24 23:59:59",
                        "REF2": "2019-02-25 00:00:01",
                    }
                }
            ),
        )

        run(
            self.smart_contract,
            "scheduled_code",
            mock_vault,
            event_type=EVENT_ACCRUE,
            effective_date=offset_datetime(2019, 2, 25, 0, 0, 0),
        )

        self.check_calls_for_vault_methods(
            mock_vault, expected_calls=expected_calls, unexpected_calls=unexpected_calls
        )

    def test_schedules_for_non_default_execution_times(self):

        mock_vault = self.create_mock(
            account_creation_date=offset_datetime(2019, 1, 2),
            accrual_schedule_hour=10,
            accrual_schedule_minute=10,
            accrual_schedule_second=10,
            scod_schedule_hour=10,
            scod_schedule_minute=10,
            scod_schedule_second=12,
            pdd_schedule_hour=10,
            pdd_schedule_minute=10,
            pdd_schedule_second=11,
            annual_fee_schedule_hour=23,
            annual_fee_schedule_minute=50,
            annual_fee_schedule_second=10,
            payment_due_period=21,
        )

        actual_schedules = run(self.smart_contract, "execution_schedules", mock_vault)
        event_scod_schedule = convert_utc_to_local_schedule(
            month="2", day="2", hour="10", minute="10", second="12"
        )
        event_annual_fee_schedule = convert_utc_to_local_schedule(
            hour="23", minute="50", second="10"
        )
        event_pdd_schedule = convert_utc_to_local_schedule(
            month="2", day="23", hour="10", minute="10", second="11"
        )
        event_accrue_schedule = convert_utc_to_local_schedule(hour="10", minute="10", second="10")
        self.assertEqual(
            actual_schedules,
            [
                (EVENT_SCOD, event_scod_schedule),
                (EVENT_ANNUAL_FEE, event_annual_fee_schedule),
                (EVENT_PDD, event_pdd_schedule),
                (EVENT_ACCRUE, event_accrue_schedule),
            ],
        )
