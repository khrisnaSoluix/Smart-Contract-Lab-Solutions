# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import Mock, call
from json import dumps
from typing import List, Tuple

import inception_sdk.test_framework.common.constants as constants

from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Balance,
    OptionalValue,
    Rejected,
    RejectedReason,
    Tside,
    UnionItemValue,
    BalanceDefaultDict,
)
from inception_sdk.test_framework.contracts.unit.common import ContractTest, balance_dimensions

import library.common.contract_modules.constants.files as files

# Loan specific
import library.loan.constants.accounts as accounts
import library.loan.constants.addresses as address
import library.loan.constants.files as contract_files
import library.loan.constants.flags as flags

VAULT_ACCOUNT_ID = accounts.LOAN_ACCOUNT
DEFAULT_DATE = datetime(2020, 1, 10, tzinfo=timezone.utc)

DEFAULT_ARREARS_FEE = Decimal("15")
DEFAULT_FIXED_INTEREST_RATE = Decimal("0.129971")
DEFAULT_FIXED_INTEREST_LOAN = UnionItemValue(key="False")
DEFAULT_GRACE_PERIOD = Decimal(15)
DEFAULT_OVERPAYMENT_FEE_RATE = Decimal("0.1")
DEFAULT_PENALTY_INCLUDES_BASE_RATE = UnionItemValue(key="True")
DEFAULT_PENALTY_INTEREST_RATE = Decimal("0.129971")
DEFAULT_PRINCIPAL = Decimal(100000)
DEFAULT_REPAYMENT_DAY = Decimal(28)
DEFAULT_REPAYMENT_DAY_ADJUSTMENT = OptionalValue(Decimal(0))
DEFAULT_SCHEDULE_HOUR = Decimal(0)
DEFAULT_SCHEDULE_MINUTE = Decimal(0)
DEFAULT_SCHEDULE_SECOND = Decimal(1)
DEFAULT_TOTAL_TERM = Decimal(1)
DEFAULT_VARIABLE_INTEREST_RATE = Decimal("0.129971")
DEFAULT_ANNUAL_INTEREST_RATE_CAP = Decimal("1.00")
DEFAULT_ANNUAL_INTEREST_RATE_FLOOR = Decimal("0.00")
DEFAULT_VARIABLE_RATE_ADJUSTMENT = Decimal("0.00")
DEFAULT_UPFRONT_FEE = Decimal("0.00")


class LoanTest(ContractTest):
    contract_file = contract_files.CONTRACT_FILE
    side = Tside.ASSET
    linked_contract_modules = {
        "utils": {"path": files.UTILS_FILE},
        "amortisation": {"path": files.AMORTISATION_FILE},
    }

    def create_mock(
        self,
        creation_date=DEFAULT_DATE,
        penalty_blocking_flags=flags.DEFAULT_PENALTY_BLOCKING_FLAG,
        delinquency_blocking_flags=flags.DEFAULT_DELINQUENCY_BLOCKING_FLAG,
        late_repayment_fee=DEFAULT_ARREARS_FEE,
        upfront_fee=DEFAULT_UPFRONT_FEE,
        amortise_upfront_fee=UnionItemValue(key="True"),
        delinquency_flags=flags.DEFAULT_DELINQUENCY_FLAG,
        denomination=constants.DEFAULT_DENOMINATION,
        deposit_account=accounts.DEPOSIT_ACCOUNT,
        due_amount_blocking_flags=flags.DEFAULT_DUE_AMOUNT_BLOCKING_FLAG,
        fixed_interest_rate=DEFAULT_FIXED_INTEREST_RATE,
        fixed_interest_loan=DEFAULT_FIXED_INTEREST_LOAN,
        grace_period=DEFAULT_GRACE_PERIOD,
        loan_start_date=DEFAULT_DATE,
        overdue_amount_blocking_flags=flags.DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG,
        penalty_includes_base_rate=DEFAULT_PENALTY_INCLUDES_BASE_RATE,
        penalty_interest_rate=DEFAULT_PENALTY_INTEREST_RATE,
        principal=DEFAULT_PRINCIPAL,
        repayment_blocking_flags=flags.DEFAULT_REPAYMENT_BLOCKING_FLAG,
        repayment_day=DEFAULT_REPAYMENT_DAY,
        repayment_day_adjustment=DEFAULT_REPAYMENT_DAY_ADJUSTMENT,
        total_term=DEFAULT_TOTAL_TERM,
        variable_interest_rate=DEFAULT_VARIABLE_INTEREST_RATE,
        variable_rate_adjustment=DEFAULT_VARIABLE_RATE_ADJUSTMENT,
        annual_interest_rate_cap=DEFAULT_ANNUAL_INTEREST_RATE_CAP,
        annual_interest_rate_floor=DEFAULT_ANNUAL_INTEREST_RATE_FLOOR,
        late_repayment_fee_income_account=accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
        interest_received_account=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
        overpayment_fee_income_account=accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT,
        overpayment_fee_rate=DEFAULT_OVERPAYMENT_FEE_RATE,
        penalty_interest_received_account=accounts.INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT,
        capitalised_interest_received_account=(
            accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT
        ),
        capitalised_interest_receivable_account=(
            accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT
        ),
        penalty_compounds_overdue_interest=UnionItemValue(key="True"),
        repayment_holiday_impact_preference=UnionItemValue(key="increase_emi"),
        accrue_interest_on_due_principal=UnionItemValue(key="False"),
        upfront_fee_income_account=accounts.INTERNAL_UPFRONT_FEE_INCOME_ACCOUNT,
        amortisation_method=UnionItemValue(key="declining_principal"),
        capitalise_no_repayment_accrued_interest=UnionItemValue(key="no_capitalisation"),
        overpayment_impact_preference=UnionItemValue(key="reduce_term"),
        interest_accrual_rest_type=UnionItemValue(key="daily"),
        accrue_interest_hour=DEFAULT_SCHEDULE_HOUR,
        accrue_interest_minute=DEFAULT_SCHEDULE_MINUTE,
        accrue_interest_second=DEFAULT_SCHEDULE_SECOND,
        check_overdue_hour=DEFAULT_SCHEDULE_HOUR,
        check_overdue_minute=DEFAULT_SCHEDULE_MINUTE,
        check_overdue_second=DEFAULT_SCHEDULE_SECOND,
        check_delinquency_hour=DEFAULT_SCHEDULE_HOUR,
        check_delinquency_minute=DEFAULT_SCHEDULE_MINUTE,
        check_delinquency_second=DEFAULT_SCHEDULE_SECOND,
        repayment_hour=DEFAULT_SCHEDULE_HOUR,
        repayment_minute=DEFAULT_SCHEDULE_MINUTE,
        repayment_second=DEFAULT_SCHEDULE_SECOND,
        fulfillment_precision=2,
        capitalise_penalty_interest=UnionItemValue(key="False"),
        capitalise_late_repayment_fee=UnionItemValue(key="False"),
        balloon_payment_days_delta=OptionalValue(None),
        balloon_payment_amount=OptionalValue(None),
        balloon_emi_amount=OptionalValue(None),
        **kwargs,
    ):
        params = {
            key: {"value": value}
            for key, value in locals().items()
            if key not in self.locals_to_ignore
        }
        parameter_ts = self.param_map_to_timeseries(params, creation_date)
        return super().create_mock(
            account_id=accounts.LOAN_ACCOUNT,
            parameter_ts=parameter_ts,
            creation_date=creation_date,
            **kwargs,
        )

    def account_balances(
        self,
        dt=DEFAULT_DATE,
        principal=Decimal(0),
        accrued_interest=Decimal(0),
        principal_due=Decimal(0),
        interest_due=Decimal(0),
        fees=Decimal(0),
        overpayment=Decimal(0),
        emi_principal_excess=Decimal(0),
        principal_overdue=Decimal(0),
        interest_overdue=Decimal(0),
        default_committed=Decimal(0),
        expected_accrued_interest=Decimal(0),
        emi=Decimal(0),
        capitalised_interest=Decimal(0),
        principal_capitalised_interest=Decimal(0),
        nonexistant_address=Decimal(0),
    ) -> List[Tuple[datetime, BalanceDefaultDict]]:

        balance_dict = {
            balance_dimensions(denomination=constants.DEFAULT_DENOMINATION): Balance(
                net=default_committed
            ),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION, address=address.PRINCIPAL
            ): Balance(net=principal),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION, address=address.ACCRUED_INTEREST
            ): Balance(net=accrued_interest),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION, address=address.PRINCIPAL_DUE
            ): Balance(net=principal_due),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION, address=address.INTEREST_DUE
            ): Balance(net=interest_due),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION, address=address.PENALTIES
            ): Balance(net=fees),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION, address=address.PRINCIPAL_OVERDUE
            ): Balance(net=principal_overdue),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION, address=address.OVERPAYMENT
            ): Balance(net=overpayment),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION,
                address=address.ACCRUED_EXPECTED_INTEREST,
            ): Balance(net=expected_accrued_interest),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION, address=address.EMI_PRINCIPAL_EXCESS
            ): Balance(net=emi_principal_excess),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION, address=address.INTEREST_OVERDUE
            ): Balance(net=interest_overdue),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION, address=address.EMI_ADDRESS
            ): Balance(net=emi),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION,
                address=address.ACCRUED_INTEREST_PENDING_CAPITALISATION,
            ): Balance(net=capitalised_interest),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION,
                address=address.PRINCIPAL_CAPITALISED_INTEREST,
            ): Balance(net=principal_capitalised_interest),
            balance_dimensions(
                denomination=constants.DEFAULT_DENOMINATION, address="nonexistant_address"
            ): Balance(net=nonexistant_address),
        }

        balance_default_dict = BalanceDefaultDict(lambda: Balance(net=Decimal("0")), balance_dict)

        return [(dt, balance_default_dict)]

    def test_post_activation_code(self):

        #  Check post activation code makes principal posting

        mock_vault = self.create_mock(
            principal=Decimal(100000),
            deposit_account=accounts.DEPOSIT_ACCOUNT,
            upfront_fee=Decimal(0),
            denomination=constants.DEFAULT_DENOMINATION,
        )

        postings = [
            {
                "amount": Decimal("100000"),
                "denomination": constants.DEFAULT_DENOMINATION,
                "client_transaction_id": "MOCK_HOOK_PRINCIPAL_DISBURSMENT",
                "from_account_id": VAULT_ACCOUNT_ID,
                "from_account_address": address.PRINCIPAL,
                "to_account_id": accounts.DEPOSIT_ACCOUNT,
                "to_account_address": DEFAULT_ADDRESS,
                "instruction_details": {
                    "description": "Payment of 100000 of loan principal",
                    "event": "PRINCIPAL_PAYMENT",
                },
                "asset": DEFAULT_ASSET,
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in postings]

        self.run_function("post_activate_code", mock_vault)

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=["MOCK_HOOK_PRINCIPAL_DISBURSMENT"],
            effective_date=DEFAULT_DATE,
            client_batch_id="BATCH_MOCK_HOOK_INITIAL_LOAN_DISBURSMENT",
        )
        self.assertEqual(mock_vault.instruct_posting_batch.call_count, 1)

    def test_post_activation_code_with_upfront_fee(self):

        #  Check post activation code makes principal posting

        mock_vault = self.create_mock(
            principal=Decimal(5000),
            deposit_account=accounts.DEPOSIT_ACCOUNT,
            upfront_fee=Decimal(75),
            denomination=constants.DEFAULT_DENOMINATION,
        )

        postings = [
            {
                "amount": Decimal("5000"),
                "denomination": constants.DEFAULT_DENOMINATION,
                "client_transaction_id": "MOCK_HOOK_PRINCIPAL_DISBURSMENT",
                "from_account_id": VAULT_ACCOUNT_ID,
                "from_account_address": address.PRINCIPAL,
                "to_account_id": accounts.DEPOSIT_ACCOUNT,
                "to_account_address": DEFAULT_ADDRESS,
                "instruction_details": {
                    "description": "Payment of 5000 of loan principal",
                    "event": "PRINCIPAL_PAYMENT",
                },
                "asset": DEFAULT_ASSET,
            },
            {
                "amount": Decimal("75"),
                "denomination": constants.DEFAULT_DENOMINATION,
                "client_transaction_id": "MOCK_HOOK_UPFRONT_FEE_DISBURSMENT",
                "from_account_id": VAULT_ACCOUNT_ID,
                "from_account_address": address.PRINCIPAL,
                "to_account_id": accounts.INTERNAL_UPFRONT_FEE_INCOME_ACCOUNT,
                "to_account_address": DEFAULT_ADDRESS,
                "instruction_details": {
                    "description": "Applying upfront fee of 75",
                    "event": "TRANSFER_UPFRONT_FEE",
                },
                "asset": DEFAULT_ASSET,
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in postings]

        self.run_function("post_activate_code", mock_vault)

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=[
                "MOCK_HOOK_PRINCIPAL_DISBURSMENT",
                "MOCK_HOOK_UPFRONT_FEE_DISBURSMENT",
            ],
            effective_date=DEFAULT_DATE,
            client_batch_id="BATCH_MOCK_HOOK_INITIAL_LOAN_DISBURSMENT",
        )
        self.assertEqual(mock_vault.instruct_posting_batch.call_count, 1)

    def test_get_initial_repayment_day_schedule(self):
        test_cases = [
            {
                "description": "Not a no_repayment loan",
                "amortisation_method": UnionItemValue(key="declining_principal"),
                "expected_schedule": {
                    "day": "1",
                    "hour": "0",
                    "minute": "1",
                    "second": "0",
                    "start_date": "2020-02-01",
                },
            },
            {
                "description": "Is a no_repayment loan",
                "amortisation_method": UnionItemValue(key="no_repayment"),
                "expected_schedule": {
                    "day": "1",
                    "hour": "0",
                    "minute": "1",
                    "second": "0",
                    "start_date": "2020-02-01",
                    "end_date": "2020-02-01",
                },
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                amortisation_method=test_case["amortisation_method"],
                repayment_hour=0,
                repayment_minute=1,
                repayment_second=0,
                loan_start_date=datetime(2020, 1, 1),
            )

            result = self.run_function(
                "_get_initial_repayment_day_schedule", mock_vault, mock_vault, 1
            )
            self.assertEqual(test_case["expected_schedule"], result, test_case["description"])

    def test_execution_schedules(self):
        #  Check execution schedules are correctly defined
        mock_vault = self.create_mock(
            repayment_day=int(28),
            repayment_period=int(10),
            grace_period=int(15),
            check_overdue_second=int(2),
            check_delinquency_second=int(2),
            repayment_minute=int(1),
            repayment_second=int(0),
        )

        expected_schedule = [
            (
                "ACCRUE_INTEREST",
                {"hour": "0", "minute": "0", "second": "1", "start_date": "2020-01-11"},
            ),
            (
                "REPAYMENT_DAY_SCHEDULE",
                {
                    "day": "28",
                    "hour": "0",
                    "minute": "1",
                    "second": "0",
                    "start_date": "2020-02-10",
                },
            ),
            (
                "CHECK_OVERDUE",
                {
                    "hour": "0",
                    "minute": "0",
                    "second": "2",
                    "end_date": "2020-01-11",
                    "start_date": "2020-01-11",
                },
            ),
            (
                "CHECK_DELINQUENCY",
                {
                    "hour": "0",
                    "minute": "0",
                    "second": "2",
                    "end_date": "2020-01-11",
                    "start_date": "2020-01-11",
                },
            ),
        ]

        execution_schedule = self.run_function("execution_schedules", mock_vault)

        self.assertEqual(execution_schedule, expected_schedule)

    def test_execution_schedules_balloon_loan(self):
        #  Check execution schedules are correctly defined
        mock_vault = self.create_mock(
            repayment_day=28,
            repayment_period=10,
            check_overdue_second=2,
            check_delinquency_second=2,
            repayment_minute=1,
            repayment_second=0,
            amortisation_method=UnionItemValue(key="minimum_repayment_with_balloon_payment"),
            balloon_payment_date=OptionalValue("0"),
        )

        expected_schedule = [
            (
                "ACCRUE_INTEREST",
                {"hour": "0", "minute": "0", "second": "1", "start_date": "2020-01-11"},
            ),
            (
                "REPAYMENT_DAY_SCHEDULE",
                {
                    "day": "28",
                    "hour": "0",
                    "minute": "1",
                    "second": "0",
                    "start_date": "2020-02-10",
                },
            ),
            (
                "CHECK_OVERDUE",
                {
                    "hour": "0",
                    "minute": "0",
                    "second": "2",
                    "end_date": "2020-01-11",
                    "start_date": "2020-01-11",
                },
            ),
            (
                "CHECK_DELINQUENCY",
                {
                    "hour": "0",
                    "minute": "0",
                    "second": "2",
                    "end_date": "2020-01-11",
                    "start_date": "2020-01-11",
                },
            ),
            (
                "BALLOON_PAYMENT_SCHEDULE",
                {
                    "year": "2020",
                    "month": "1",
                    "day": "11",
                    "hour": "0",
                    "minute": "1",
                    "second": "0",
                    "start_date": datetime.strftime(
                        DEFAULT_DATE + relativedelta(days=1), "%Y-%m-%d"
                    ),
                    "end_date": datetime.strftime(
                        DEFAULT_DATE + relativedelta(days=1),
                        "%Y-%m-%d",
                    ),
                },
            ),
        ]

        execution_schedule = self.run_function("execution_schedules", mock_vault)
        self.assertEqual(execution_schedule, expected_schedule)

    def test_execution_schedules_no_repayment_loan(self):
        #  Check execution schedules are correctly defined
        mock_vault = self.create_mock(
            repayment_day=28,
            repayment_period=10,
            check_overdue_second=2,
            check_delinquency_second=2,
            repayment_minute=1,
            repayment_second=0,
            amortisation_method=UnionItemValue(key="no_repayment"),
        )

        expected_schedule = [
            (
                "ACCRUE_INTEREST",
                {"hour": "0", "minute": "0", "second": "1", "start_date": "2020-01-11"},
            ),
            (
                "REPAYMENT_DAY_SCHEDULE",
                {
                    "day": "28",
                    "hour": "0",
                    "minute": "1",
                    "second": "0",
                    "start_date": "2020-02-10",
                    "end_date": "2020-02-10",
                },
            ),
            (
                "CHECK_OVERDUE",
                {
                    "hour": "0",
                    "minute": "0",
                    "second": "2",
                    "end_date": "2020-01-11",
                    "start_date": "2020-01-11",
                },
            ),
            (
                "CHECK_DELINQUENCY",
                {
                    "hour": "0",
                    "minute": "0",
                    "second": "2",
                    "end_date": "2020-01-11",
                    "start_date": "2020-01-11",
                },
            ),
            (
                "BALLOON_PAYMENT_SCHEDULE",
                {
                    "year": "2020",
                    "month": "2",
                    "day": "10",
                    "hour": "0",
                    "minute": "1",
                    "second": "0",
                },
            ),
        ]

        execution_schedule = self.run_function("execution_schedules", mock_vault)
        self.assertEqual(execution_schedule, expected_schedule)

    def test_is_outside_of_term(self):
        mock_vault = self.create_mock(repayment_day=20, total_term=12)
        effective_date = datetime(2021, 2, 20, 0, 0, 3, tzinfo=timezone.utc)
        result = self.run_function(
            "_is_within_term", mock_vault, mock_vault, effective_date, "total_term"
        )
        self.assertFalse(result)

    def test_is_last_payment_date(self):
        mock_vault = self.create_mock(
            total_term=12,
            repayment_day=5,
            loan_start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        effective_date = datetime(2021, 1, 5, 0, 0, 0, tzinfo=timezone.utc)
        result = self.run_function("_is_last_payment_date", mock_vault, mock_vault, effective_date)
        self.assertTrue(result)

    def test_effective_date_is_not_last_payment_date(self):
        mock_vault = self.create_mock(total_term=12, repayment_day=5)
        effective_date = datetime(2020, 12, 5, 0, 0, 0, tzinfo=timezone.utc)
        result = self.run_function("_is_last_payment_date", mock_vault, mock_vault, effective_date)
        self.assertFalse(result)

    def test_get_expected_remaining_term_repayment_day_before_start_date(self):
        test_cases = [
            {
                "description": "day before first repayment day",
                "effective_date": datetime(2020, 3, 4, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": 12,
            },
            {
                "description": "day of first repayment day",
                "effective_date": datetime(2020, 3, 5, 1, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 12,
            },
            {
                "description": "1 microsecond before end of first repayment day",
                "effective_date": datetime(2020, 3, 5, 23, 59, 59, 99999, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 12,
            },
            {
                "description": "day after first repayment day",
                "effective_date": datetime(2020, 3, 6, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 11,
            },
            {
                "description": "day before mid repayment day",
                "effective_date": datetime(2020, 9, 4, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 8, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 6,
            },
            {
                "description": "day of mid repayment day",
                "effective_date": datetime(2020, 9, 5, 1, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 9, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 6,
            },
            {
                "description": "day after mid repayment day",
                "effective_date": datetime(2020, 9, 6, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 9, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 5,
            },
            {
                "description": "day before last repayment day",
                "effective_date": datetime(2021, 2, 4, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2021, 1, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 1,
            },
            {
                "description": "day of last repayment day",
                "effective_date": datetime(2021, 2, 5, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2021, 1, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 1,
            },
            {
                "description": "day after last repayment day",
                "effective_date": datetime(2021, 2, 6, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2021, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 0,
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock(
                total_term=12,
                repayment_day=5,
                loan_start_date=datetime(2020, 1, 10, tzinfo=timezone.utc),
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
            )
            result = self.run_function(
                "_get_expected_remaining_term",
                mock_vault,
                mock_vault,
                test_case["effective_date"],
                "total_term",
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_expected_remaining_term_repayment_day_after_start_date(self):
        test_cases = [
            {
                "description": "day before first repayment day",
                "effective_date": datetime(2020, 2, 27, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": 12,
            },
            {
                "description": "day of first repayment day",
                "effective_date": datetime(2020, 2, 28, 1, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 2, 28, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 12,
            },
            {
                "description": "day after first repayment day",
                "effective_date": datetime(2020, 2, 29, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 2, 28, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 11,
            },
            {
                "description": "day before mid repayment day",
                "effective_date": datetime(2020, 8, 27, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 7, 28, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 6,
            },
            {
                "description": "day of mid repayment day",
                "effective_date": datetime(2020, 8, 28, 1, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 8, 28, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 6,
            },
            {
                "description": "day after mid repayment day",
                "effective_date": datetime(2020, 8, 29, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 8, 28, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 5,
            },
            {
                "description": "day before last repayment day",
                "effective_date": datetime(2021, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 12, 28, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 1,
            },
            {
                "description": "day of last repayment day",
                "effective_date": datetime(2021, 1, 28, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 12, 28, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 1,
            },
            {
                "description": "day after last repayment day",
                "effective_date": datetime(2021, 1, 29, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 12, 28, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 0,
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock(
                total_term=12,
                repayment_day=28,
                loan_start_date=datetime(2020, 1, 20, tzinfo=timezone.utc),
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
            )
            result = self.run_function(
                "_get_expected_remaining_term",
                mock_vault,
                mock_vault,
                test_case["effective_date"],
                "total_term",
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_expected_remaining_term_repayment_day_on_start_date(self):
        test_cases = [
            {
                "description": "day before first repayment day",
                "effective_date": datetime(2020, 1, 31, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": 12,
            },
            {
                "description": "day of first repayment day",
                "effective_date": datetime(2020, 2, 1, 1, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 2, 1, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 12,
            },
            {
                "description": "day after first repayment day",
                "effective_date": datetime(2020, 2, 2, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 2, 1, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 11,
            },
            {
                "description": "day before mid repayment day",
                "effective_date": datetime(2020, 7, 31, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 7, 1, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 6,
            },
            {
                "description": "day of mid repayment day",
                "effective_date": datetime(2020, 8, 1, 1, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 8, 1, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 6,
            },
            {
                "description": "day after mid repayment day",
                "effective_date": datetime(2020, 8, 2, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 8, 1, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 5,
            },
            {
                "description": "day before last repayment day",
                "effective_date": datetime(2020, 12, 31, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 12, 1, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 1,
            },
            {
                "description": "day of last repayment day",
                "effective_date": datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 12, 1, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 1,
            },
            {
                "description": "day after last repayment day",
                "effective_date": datetime(2021, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2021, 1, 1, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": 0,
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock(
                total_term=12,
                repayment_day=1,
                loan_start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
            )
            result = self.run_function(
                "_get_expected_remaining_term",
                mock_vault,
                mock_vault,
                test_case["effective_date"],
                "total_term",
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_total_interest_plus_principal_term(self):
        mock_vault = self.create_mock(total_term=120, repayment_day=5)
        result = self.run_function(
            "_get_total_interest_plus_principal_term", mock_vault, mock_vault
        )
        self.assertEqual(result, 120)

    def test_get_interest_rate(self):
        effective_date = DEFAULT_DATE + timedelta(seconds=1)
        test_cases = [
            {
                "description": "Fixed rate",
                "fixed_interest_loan": UnionItemValue(key="True"),
                "fixed_interest_rate": Decimal("0.0122"),
                "variable_interest_rate": "0.4333",
                "variable_rate_adjustment": Decimal("0.00"),
                "annual_interest_rate_cap": Decimal("1.00"),
                "annual_interest_rate_floor": Decimal("0.00"),
                "expected_result": ["fixed_interest_rate", Decimal("0.0122")],
            },
            {
                "description": "Variable rate - no adjustment",
                "fixed_interest_loan": UnionItemValue(key="False"),
                "fixed_interest_rate": Decimal("0.0122"),
                "variable_interest_rate": Decimal("0.4333"),
                "variable_rate_adjustment": Decimal("0.00"),
                "annual_interest_rate_cap": Decimal("1.00"),
                "annual_interest_rate_floor": Decimal("0.00"),
                "expected_result": ["variable_interest_rate", Decimal("0.4333")],
            },
            {
                "description": "Variable rate - with adjustment, between limits",
                "fixed_interest_loan": UnionItemValue(key="False"),
                "fixed_interest_rate": Decimal("0.0122"),
                "variable_interest_rate": Decimal("0.4333"),
                "variable_rate_adjustment": Decimal("-0.23"),
                "annual_interest_rate_cap": Decimal("1.00"),
                "annual_interest_rate_floor": Decimal("0.00"),
                "expected_result": ["variable_interest_rate", Decimal("0.2033")],
            },
            {
                "description": "Variable rate - with adjustment, greater than cap",
                "fixed_interest_loan": UnionItemValue(key="False"),
                "fixed_interest_rate": Decimal("0.0122"),
                "variable_interest_rate": Decimal("0.4333"),
                "variable_rate_adjustment": Decimal("-0.23"),
                "annual_interest_rate_cap": Decimal("0.20"),
                "annual_interest_rate_floor": Decimal("0.00"),
                "expected_result": ["variable_interest_rate", Decimal("0.20")],
            },
            {
                "description": "Variable rate - with adjustment, equal to cap",
                "fixed_interest_loan": UnionItemValue(key="False"),
                "fixed_interest_rate": Decimal("0.0122"),
                "variable_interest_rate": Decimal("0.4333"),
                "variable_rate_adjustment": Decimal("-0.23"),
                "annual_interest_rate_cap": Decimal("0.2033"),
                "annual_interest_rate_floor": Decimal("0.00"),
                "expected_result": ["variable_interest_rate", Decimal("0.2033")],
            },
            {
                "description": "Variable rate - with adjustment, equal to floor",
                "fixed_interest_loan": UnionItemValue(key="False"),
                "fixed_interest_rate": Decimal("0.0122"),
                "variable_interest_rate": Decimal("0.4333"),
                "variable_rate_adjustment": Decimal("-0.23"),
                "annual_interest_rate_cap": Decimal("1"),
                "annual_interest_rate_floor": Decimal("0.2033"),
                "expected_result": ["variable_interest_rate", Decimal("0.2033")],
            },
            {
                "description": "Variable rate - with adjustment, less than floor",
                "fixed_interest_loan": UnionItemValue(key="False"),
                "fixed_interest_rate": Decimal("0.0122"),
                "variable_interest_rate": Decimal("0.4333"),
                "variable_rate_adjustment": Decimal("-0.23"),
                "annual_interest_rate_cap": Decimal("1"),
                "annual_interest_rate_floor": Decimal("0.25"),
                "expected_result": ["variable_interest_rate", Decimal("0.25")],
            },
            {
                "description": "Variable rate - with adjustment, negative",
                "fixed_interest_loan": UnionItemValue(key="False"),
                "fixed_interest_rate": Decimal("0.0122"),
                "variable_interest_rate": Decimal("0.4333"),
                "variable_rate_adjustment": Decimal("-0.73"),
                "annual_interest_rate_cap": Decimal("1"),
                "annual_interest_rate_floor": Decimal("0.1"),
                "expected_result": ["variable_interest_rate", Decimal("0.1")],
            },
        ]

        for test_case in test_cases:

            mock_vault = self.create_mock(
                fixed_interest_loan=test_case["fixed_interest_loan"],
                fixed_interest_rate=test_case["fixed_interest_rate"],
                variable_interest_rate=test_case["variable_interest_rate"],
                variable_rate_adjustment=test_case["variable_rate_adjustment"],
                annual_interest_rate_cap=test_case["annual_interest_rate_cap"],
                annual_interest_rate_floor=test_case["annual_interest_rate_floor"],
                repayment_day=5,
            )
            result = self.run_function("_get_interest_rate", mock_vault, mock_vault, effective_date)
            self.assertEqual(
                result["interest_rate_type"],
                test_case["expected_result"][0],
                test_case["description"],
            )
            self.assertEqual(
                result["interest_rate"],
                test_case["expected_result"][1],
                test_case["description"],
            )

    def test_get_additional_interest(self):
        test_cases = [
            {
                "description": "No previous execution",
                "effective_date": datetime(2020, 2, 28, 0, 1, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "balance_ts": self.account_balances(
                    datetime(2020, 2, 28, 0, 1, 0, tzinfo=timezone.utc),
                    principal=Decimal("300000"),
                    accrued_interest=Decimal("123.45"),
                    expected_accrued_interest=Decimal("123.45"),
                    overpayment=Decimal("0"),
                    emi=Decimal("1000.00"),
                ),
                "previous_balance": self.account_balances(
                    datetime(2020, 1, 20, 0, 1, 0, tzinfo=timezone.utc),
                    principal=Decimal("300000"),
                    accrued_interest=Decimal("12"),
                    expected_accrued_interest=Decimal("12"),
                    overpayment=Decimal("0"),
                    emi=Decimal("1000.00"),
                ),
                "expected_result": Decimal("12"),
            },
            {
                "description": "Previous execution, no additional interest",
                "effective_date": datetime(2020, 2, 28, 0, 1, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 1, 28, 0, 1, 0, tzinfo=timezone.utc),
                "balance_ts": self.account_balances(
                    datetime(2020, 2, 28, 0, 0, 0, tzinfo=timezone.utc),
                    principal=Decimal("300000"),
                    accrued_interest=Decimal("123.45"),
                    expected_accrued_interest=Decimal("123.45"),
                    overpayment=Decimal("0"),
                    emi=Decimal("1000.00"),
                ),
                "previous_balance": self.account_balances(
                    datetime(2020, 1, 28, 0, 1, 0, tzinfo=timezone.utc),
                    principal=Decimal("300000"),
                    accrued_interest=Decimal("123.45"),
                    expected_accrued_interest=Decimal("0"),
                    overpayment=Decimal("0"),
                    emi=Decimal("1000.00"),
                ),
                "expected_result": Decimal("0"),
            },
            {
                "description": "Previous execution, with additional interest",
                "effective_date": datetime(2020, 2, 28, 0, 1, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 1, 28, 0, 1, 0, tzinfo=timezone.utc),
                "balance_ts": self.account_balances(
                    datetime(2020, 2, 28, 0, 0, 0, tzinfo=timezone.utc),
                    principal=Decimal("300000"),
                    accrued_interest=Decimal("123.45"),
                    expected_accrued_interest=Decimal("123.45"),
                    overpayment=Decimal("0"),
                    emi=Decimal("1000.00"),
                ),
                "previous_balance": self.account_balances(
                    datetime(2020, 1, 28, 0, 1, 0, tzinfo=timezone.utc),
                    principal=Decimal("300000"),
                    accrued_interest=Decimal("123.45"),
                    expected_accrued_interest=Decimal("123.45"),
                    overpayment=Decimal("0"),
                    emi=Decimal("1000.00"),
                ),
                "expected_result": Decimal("123.45"),
            },
        ]

        for test_case in test_cases:
            if "previous_balance" in test_case:
                test_case["balance_ts"].extend(test_case["previous_balance"])
            mock_vault = self.create_mock(
                balance_ts=test_case["balance_ts"],
                repayment_day=28,
                principal=300000,
                denomination=constants.DEFAULT_DENOMINATION,
                total_term=120,
                fixed_interest_loan=UnionItemValue(key="True"),
                fixed_interest_rate="0.01",
                fulfillment_precision=2,
                accrual_precision=5,
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
            )
            result = self.run_function(
                "_get_additional_interest",
                mock_vault,
                mock_vault,
                test_case["effective_date"],
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_calculate_monthly_payment_interest_and_principal_no_emi(self):
        annual_interest_rate = {
            "interest_rate": Decimal("0.031"),
            "interest_rate_type": "variable_interest_rate",
        }

        effective_date = datetime(2020, 1, 28, 0, 0, 0, tzinfo=timezone.utc)
        transfer_amount_date = datetime(2020, 1, 12, 0, 0, 3, tzinfo=timezone.utc)
        balance_ts = self.account_balances(
            transfer_amount_date,
            principal=Decimal("300000"),
            accrued_interest=Decimal("123.45"),
            expected_accrued_interest=Decimal("123.45"),
            overpayment=Decimal("0"),
        )
        variable_rate_adjustment = "variable_rate_adjustment"
        variable_interest_rate = "variable_interest_rate"
        parameter_ts = {
            variable_rate_adjustment: [(effective_date + relativedelta(days=-1), Decimal("-0.01"))],
            variable_interest_rate: [(effective_date + relativedelta(days=-2), Decimal("0.32"))],
        }
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            repayment_day=28,
            principal=300000,
            denomination=constants.DEFAULT_DENOMINATION,
            total_term=120,
            fulfillment_precision=2,
            accrual_precision=5,
            variable_rate_adjustment=parameter_ts[variable_rate_adjustment],
            variable_interest_rate=parameter_ts[variable_interest_rate],
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            vault=mock_vault,
            effective_date=effective_date,
            annual_interest_rate=annual_interest_rate,
        )
        self.assertEqual(result["emi"], Decimal("2910.69"))
        self.assertEqual(result["interest_due"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest_excluding_overpayment"], Decimal("123.45"))
        self.assertEqual(result["principal_due_excluding_overpayment"], Decimal("2787.24"))
        self.assertEqual(result["principal_excess"], Decimal("0"))

    def test_calculate_monthly_payment_interest_and_principal_no_emi_with_last_exec(
        self,
    ):
        annual_interest_rate = {
            "interest_rate": Decimal("0.031"),
            "interest_rate_type": "variable_interest_rate",
        }

        effective_date = datetime(2020, 1, 28, 0, 0, 0, tzinfo=timezone.utc)
        transfer_amount_date = datetime(2020, 1, 12, 0, 0, 3, tzinfo=timezone.utc)
        balance_ts = self.account_balances(
            transfer_amount_date,
            principal=Decimal("300000"),
            accrued_interest=Decimal("123.45"),
            expected_accrued_interest=Decimal("123.45"),
            overpayment=Decimal("0"),
        )
        variable_rate_adjustment = "variable_rate_adjustment"
        variable_interest_rate = "variable_interest_rate"
        parameter_ts = {
            variable_rate_adjustment: [(effective_date + relativedelta(days=-1), Decimal("0.01"))],
            variable_interest_rate: [(effective_date + relativedelta(days=-2), Decimal("0.32"))],
        }
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            repayment_day=28,
            principal=300000,
            denomination=constants.DEFAULT_DENOMINATION,
            total_term=120,
            fixed_interest_loan=UnionItemValue(key="False"),
            fulfillment_precision=2,
            accrual_precision=5,
            REPAYMENT_DAY_SCHEDULE=None,
            variable_rate_adjustment=parameter_ts[variable_rate_adjustment],
            variable_interest_rate=parameter_ts[variable_interest_rate],
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            vault=mock_vault,
            effective_date=effective_date,
            annual_interest_rate=annual_interest_rate,
        )
        self.assertEqual(result["emi"], Decimal("2910.69"))
        self.assertEqual(result["interest_due"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest_excluding_overpayment"], Decimal("123.45"))
        self.assertEqual(result["principal_due_excluding_overpayment"], Decimal("2787.24"))
        self.assertEqual(result["principal_excess"], Decimal("0"))

    def test_calculate_monthly_payment_interest_and_principal_with_emi_recalc(self):
        annual_interest_rate = {
            "interest_rate": Decimal("0.031"),
            "interest_rate_type": "variable_interest_rate",
        }

        effective_date = datetime(2020, 1, 28, 0, 0, 0, tzinfo=timezone.utc)
        transfer_amount_date = datetime(2020, 1, 12, 0, 0, 3, tzinfo=timezone.utc)
        balance_ts = self.account_balances(
            transfer_amount_date,
            principal=Decimal("300000"),
            accrued_interest=Decimal("123.45"),
            expected_accrued_interest=Decimal("123.45"),
            overpayment=Decimal("0"),
            emi=Decimal("1000.00"),
        )
        variable_rate_adjustment = "variable_rate_adjustment"
        variable_interest_rate = "variable_interest_rate"
        parameter_ts = {
            variable_rate_adjustment: [(effective_date + relativedelta(days=-1), Decimal("-0.01"))],
            variable_interest_rate: [(effective_date + relativedelta(days=-2), Decimal("0.32"))],
        }
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            repayment_day=28,
            principal=300000,
            denomination=constants.DEFAULT_DENOMINATION,
            total_term=120,
            fulfillment_precision=2,
            accrual_precision=5,
            variable_rate_adjustment=parameter_ts[variable_rate_adjustment],
            variable_interest_rate=parameter_ts[variable_interest_rate],
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            vault=mock_vault,
            effective_date=effective_date,
            annual_interest_rate=annual_interest_rate,
        )
        self.assertEqual(result["emi"], Decimal("2910.69"))
        self.assertEqual(result["interest_due"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest_excluding_overpayment"], Decimal("123.45"))
        self.assertEqual(result["principal_due_excluding_overpayment"], Decimal("2787.24"))
        self.assertEqual(result["principal_excess"], Decimal("0"))

    def test_calculate_monthly_payment_interest_and_principal_fixed_rate_no_emi_recalc(
        self,
    ):
        annual_interest_rate = {
            "interest_rate": Decimal("0.031"),
            "interest_rate_type": "fixed_interest_rate",
        }

        effective_date = datetime(2020, 1, 28, 0, 0, 0, tzinfo=timezone.utc)
        transfer_amount_date = datetime(2020, 1, 12, 0, 0, 3, tzinfo=timezone.utc)
        last_execution_time = effective_date - relativedelta(months=1)
        balance_ts = self.account_balances(
            last_execution_time,
            principal=Decimal("300000"),
            accrued_interest=Decimal("0"),
            expected_accrued_interest=Decimal("0"),
            overpayment=Decimal("0"),
            emi=Decimal("1000.00"),
        )

        balance_ts.extend(
            self.account_balances(
                transfer_amount_date,
                principal=Decimal("300000"),
                accrued_interest=Decimal("123.45"),
                expected_accrued_interest=Decimal("123.45"),
                overpayment=Decimal("0"),
                emi=Decimal("1000.00"),
            )
        )

        fixed_interest_loan = "fixed_interest_loan"
        parameter_ts = {
            fixed_interest_loan: [
                (effective_date - relativedelta(months=1), UnionItemValue(key="True"))
            ],
        }
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            repayment_day=28,
            principal=300000,
            denomination=constants.DEFAULT_DENOMINATION,
            total_term=120,
            fixed_interest_loan=parameter_ts[fixed_interest_loan],
            fulfillment_precision=2,
            accrual_precision=5,
            REPAYMENT_DAY_SCHEDULE=last_execution_time,
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            vault=mock_vault,
            effective_date=effective_date,
            annual_interest_rate=annual_interest_rate,
        )
        self.assertEqual(result["emi"], Decimal("1000.00"))
        self.assertEqual(result["interest_due"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest_excluding_overpayment"], Decimal("123.45"))
        self.assertEqual(result["principal_due_excluding_overpayment"], Decimal("876.55"))
        self.assertEqual(result["principal_excess"], Decimal("0"))

    def test_calculate_monthly_payment_interest_and_principal_with_excess_no_emi(self):
        annual_interest_rate = {
            "interest_rate": Decimal("0.031"),
            "interest_rate_type": "variable_interest_rate",
        }

        effective_date = datetime(2020, 1, 12, 0, 0, 3, tzinfo=timezone.utc)
        balance_ts = self.account_balances(
            effective_date,
            principal=Decimal("295723"),
            accrued_interest=Decimal("123.45"),
            expected_accrued_interest=Decimal("153.45"),
        )
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            loan_start_date=DEFAULT_DATE,
            repayment_day=28,
            principal=300000,
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            total_term=120,
            fulfillment_precision=2,
            accrual_precision=5,
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            vault=mock_vault,
            effective_date=effective_date,
            annual_interest_rate=annual_interest_rate,
        )
        self.assertEqual(result["emi"], Decimal("2869.19"))
        self.assertEqual(result["interest_due"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest_excluding_overpayment"], Decimal("153.45"))
        self.assertEqual(result["principal_due_excluding_overpayment"], Decimal("2715.74"))
        self.assertEqual(result["principal_excess"], Decimal("30.00"))

    def test_calculate_monthly_payment_interest_and_principal_first_emi_additional_days(
        self,
    ):
        annual_interest_rate = {
            "interest_rate": Decimal("0.031"),
            "interest_rate_type": "fixed_interest_rate",
        }

        effective_date = datetime(2020, 2, 28, 0, 0, 3, tzinfo=timezone.utc)
        repayment_start_date = datetime(2020, 1, 28, 0, 0, 3, tzinfo=timezone.utc)
        balance_ts = self.account_balances(
            repayment_start_date,
            principal=Decimal("300000"),
            accrued_interest=Decimal("153.45"),
            expected_accrued_interest=Decimal("153.45"),
        )
        balance_ts.extend(
            self.account_balances(
                effective_date,
                principal=Decimal("300000"),
                accrued_interest=Decimal("253.45"),
                expected_accrued_interest=Decimal("253.45"),
            )
        )

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            loan_start_date=DEFAULT_DATE,
            repayment_day=28,
            principal=300000,
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            total_term=120,
            fulfillment_precision=2,
            accrual_precision=5,
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            vault=mock_vault,
            effective_date=effective_date,
            annual_interest_rate=annual_interest_rate,
        )
        self.assertEqual(result["emi"], Decimal("2910.69"))
        self.assertEqual(result["interest_due"], Decimal("253.45"))
        self.assertEqual(result["accrued_interest_excluding_overpayment"], Decimal("253.45"))
        self.assertEqual(result["principal_due_excluding_overpayment"], Decimal("2810.69"))

    def test_calculate_monthly_payment_interest_and_principal_final_payment(self):
        annual_interest_rate = {
            "interest_rate": Decimal("0.031"),
            "interest_rate_type": "fixed_interest_rate",
        }

        effective_date = datetime(2029, 12, 28, 0, 0, 0, tzinfo=timezone.utc)
        transfer_amount_date = datetime(2020, 1, 12, 0, 0, 3, tzinfo=timezone.utc)
        balance_ts = self.account_balances(
            transfer_amount_date,
            principal=Decimal("2903.86"),
            accrued_interest=Decimal("1.23"),
            emi=Decimal("2910.69"),
        )
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            loan_start_date=DEFAULT_DATE,
            repayment_day=28,
            principal=300000,
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            total_term=120,
            fulfillment_precision=2,
            accrual_precision=5,
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            vault=mock_vault,
            effective_date=effective_date,
            annual_interest_rate=annual_interest_rate,
        )
        self.assertEqual(result["interest_due"], Decimal("1.23"))
        self.assertEqual(result["principal_due_excluding_overpayment"], Decimal("2903.86"))

    def test_calculate_monthly_payment_interest_and_principal_with_emi(self):
        annual_interest_rate = {
            "interest_rate": Decimal("0.031"),
            "interest_rate_type": "variable_interest_rate",
        }

        effective_date = datetime(2020, 3, 28, 0, 1, 0, tzinfo=timezone.utc)
        balance_ts = self.account_balances(
            effective_date,
            principal=Decimal("300000"),
            accrued_interest=Decimal("123.45"),
            expected_accrued_interest=Decimal("123.45"),
            overpayment=Decimal("0"),
            emi=Decimal("1000"),
        )
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 12, 0, 0, 0, tzinfo=timezone.utc),
            balance_ts=balance_ts,
            repayment_day=28,
            principal=300000,
            denomination=constants.DEFAULT_DENOMINATION,
            total_term=120,
            fixed_interest_loan=UnionItemValue(key="False"),
            fulfillment_precision=2,
            accrual_precision=5,
            loan_start_date=datetime(2020, 1, 12, 0, 0, 0, tzinfo=timezone.utc),
            REPAYMENT_DAY_SCHEDULE=effective_date + relativedelta(months=-1),
        )

        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            vault=mock_vault,
            effective_date=effective_date,
            annual_interest_rate=annual_interest_rate,
        )

        self.assertEqual(result["emi"], Decimal("1000"))
        self.assertEqual(result["interest_due"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest_excluding_overpayment"], Decimal("123.45"))
        self.assertEqual(result["principal_due_excluding_overpayment"], Decimal("876.55"))
        self.assertEqual(result["principal_excess"], Decimal("0"))

    def test_calculate_monthly_payment_interest_and_principal_emi_upfront_fee_subtracted(
        self,
    ):
        annual_interest_rate = {
            "interest_rate": Decimal("0.031"),
            "interest_rate_type": "fixed_interest_rate",
        }

        effective_date = datetime(2020, 2, 28, 0, 0, 3, tzinfo=timezone.utc)
        repayment_start_date = datetime(2020, 2, 28, 0, 0, 3, tzinfo=timezone.utc)
        balance_ts = self.account_balances(
            repayment_start_date,
            principal=Decimal("10000"),
            accrued_interest=Decimal("10"),
            expected_accrued_interest=Decimal("10"),
        )
        balance_ts.extend(
            self.account_balances(
                effective_date,
                principal=Decimal("10000"),
                accrued_interest=Decimal("10"),
                expected_accrued_interest=Decimal("10"),
            )
        )

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            loan_start_date=DEFAULT_DATE,
            repayment_day=28,
            principal=10000,
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            total_term=36,
            fulfillment_precision=2,
            accrual_precision=5,
            upfront_fee=2500,
            amortise_upfront_fee=UnionItemValue("False"),
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            vault=mock_vault,
            effective_date=effective_date,
            annual_interest_rate=annual_interest_rate,
        )

        # (10000 * 0.031 / 12 * (1+0.031 / 12)^36)/((1+0.031/12)^36-1)
        self.assertEqual(result["emi"], Decimal("291.25"))
        self.assertEqual(result["interest_due"], Decimal("10"))
        self.assertEqual(result["accrued_interest_excluding_overpayment"], Decimal("10"))
        self.assertEqual(result["principal_due_excluding_overpayment"], Decimal("281.25"))

    def test_calculate_monthly_payment_interest_and_principal_emi_upfront_fee_added(
        self,
    ):
        annual_interest_rate = {
            "interest_rate": Decimal("0.031"),
            "interest_rate_type": "fixed_interest_rate",
        }

        effective_date = datetime(2020, 2, 28, 0, 0, 3, tzinfo=timezone.utc)
        repayment_start_date = datetime(2020, 2, 28, 0, 0, 3, tzinfo=timezone.utc)
        balance_ts = self.account_balances(
            repayment_start_date,
            principal=Decimal("12500"),
            accrued_interest=Decimal("10"),
            expected_accrued_interest=Decimal("10"),
        )

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            loan_start_date=DEFAULT_DATE,
            repayment_day=28,
            principal=10000,
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            total_term=36,
            fulfillment_precision=2,
            accrual_precision=5,
            upfront_fee=2500,
            amortise_upfront_fee=UnionItemValue("True"),
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            vault=mock_vault,
            effective_date=effective_date,
            annual_interest_rate=annual_interest_rate,
        )

        # (12500 * 0.031 / 12 * (1+0.031 / 12)^36)/((1+0.031/12)^36-1)
        self.assertEqual(result["emi"], Decimal("364.07"))
        self.assertEqual(result["interest_due"], Decimal("10"))
        self.assertEqual(result["accrued_interest_excluding_overpayment"], Decimal("10"))
        self.assertEqual(result["principal_due_excluding_overpayment"], Decimal("354.07"))

    def test_process_payment_repays_in_order(self):

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            principal_overdue=Decimal("150"),
            interest_overdue=Decimal("50"),
        )

        effective_date = DEFAULT_DATE + relativedelta(months=1)

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            repayment_day=int(10),
            denomination=constants.DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(12),
            fulfillment_precision=2,
        )

        incoming_posting = self.inbound_hard_settlement(
            amount="1000",
            denomination=constants.DEFAULT_DENOMINATION,
        )
        incoming_postings = self.mock_posting_instruction_batch(
            posting_instructions=[incoming_posting]
        )

        postings = [
            {
                "amount": Decimal("150.00"),
                "asset": DEFAULT_ASSET,
                "client_transaction_id": "REPAY_PRINCIPAL_OVERDUE_testctid",
                "denomination": constants.DEFAULT_DENOMINATION,
                "from_account_address": DEFAULT_ADDRESS,
                "from_account_id": VAULT_ACCOUNT_ID,
                "instruction_details": {
                    "description": (
                        "Paying off 150.00 from PRINCIPAL_OVERDUE, "
                        "which was at 150.00 - 2020-02-10 00:00:00+00:00"
                    ),
                    "event": "REPAYMENT",
                },
                "override_all_restrictions": True,
                "to_account_address": address.PRINCIPAL_OVERDUE,
                "to_account_id": VAULT_ACCOUNT_ID,
            },
            {
                "amount": Decimal("50.00"),
                "asset": DEFAULT_ASSET,
                "client_transaction_id": "REPAY_INTEREST_OVERDUE_testctid",
                "denomination": constants.DEFAULT_DENOMINATION,
                "from_account_address": DEFAULT_ADDRESS,
                "from_account_id": VAULT_ACCOUNT_ID,
                "instruction_details": {
                    "description": (
                        "Paying off 50.00 from INTEREST_OVERDUE, "
                        "which was at 50.00 - 2020-02-10 00:00:00+00:00"
                    ),
                    "event": "REPAYMENT",
                },
                "override_all_restrictions": True,
                "to_account_address": address.INTEREST_OVERDUE,
                "to_account_id": VAULT_ACCOUNT_ID,
            },
            {
                "amount": Decimal("100.00"),
                "asset": DEFAULT_ASSET,
                "client_transaction_id": "REPAY_PRINCIPAL_DUE_testctid",
                "denomination": constants.DEFAULT_DENOMINATION,
                "from_account_address": DEFAULT_ADDRESS,
                "from_account_id": VAULT_ACCOUNT_ID,
                "instruction_details": {
                    "description": (
                        "Paying off 100.00 from PRINCIPAL_DUE, "
                        "which was at 100.00 - 2020-02-10 00:00:00+00:00"
                    ),
                    "event": "REPAYMENT",
                },
                "override_all_restrictions": True,
                "to_account_address": address.PRINCIPAL_DUE,
                "to_account_id": VAULT_ACCOUNT_ID,
            },
            {
                "amount": Decimal("35.00"),
                "asset": DEFAULT_ASSET,
                "client_transaction_id": "REPAY_INTEREST_DUE_testctid",
                "denomination": constants.DEFAULT_DENOMINATION,
                "from_account_address": DEFAULT_ADDRESS,
                "from_account_id": VAULT_ACCOUNT_ID,
                "instruction_details": {
                    "description": (
                        "Paying off 35.00 from INTEREST_DUE, "
                        "which was at 35.00 - 2020-02-10 00:00:00+00:00"
                    ),
                    "event": "REPAYMENT",
                },
                "override_all_restrictions": True,
                "to_account_address": address.INTEREST_DUE,
                "to_account_id": VAULT_ACCOUNT_ID,
            },
            {
                "amount": Decimal("598.50"),
                "asset": DEFAULT_ASSET,
                "client_transaction_id": "OVERPAYMENT_BALANCE_testctid",
                "denomination": constants.DEFAULT_DENOMINATION,
                "from_account_address": DEFAULT_ADDRESS,
                "from_account_id": VAULT_ACCOUNT_ID,
                "instruction_details": {
                    "description": (
                        "Upon repayment, 598.50 of the repayment "
                        "has been transfered to the OVERPAYMENT balance."
                    ),
                    "event": "OVERPAYMENT_BALANCE_INCREASE",
                },
                "override_all_restrictions": True,
                "to_account_address": address.OVERPAYMENT,
                "to_account_id": VAULT_ACCOUNT_ID,
            },
            {
                "amount": Decimal("66.50"),
                "asset": DEFAULT_ASSET,
                "client_transaction_id": "OVERPAYMENT_FEE_testctid",
                "denomination": constants.DEFAULT_DENOMINATION,
                "from_account_address": DEFAULT_ADDRESS,
                "from_account_id": VAULT_ACCOUNT_ID,
                "instruction_details": {
                    "description": (
                        "Upon repayment, 66.50 of the repayment "
                        "has been transfered to the overpayment_fee_income_account."
                    ),
                    "event": "OVERPAYMENT_FEE",
                },
                "override_all_restrictions": True,
                "to_account_address": DEFAULT_ADDRESS,
                "to_account_id": accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT,
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in postings]

        self.run_function(
            "_process_payment",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
            posting=incoming_posting,
            client_transaction_id="testctid",
            postings=incoming_postings,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=[
                "REPAY_PRINCIPAL_OVERDUE_testctid",
                "REPAY_INTEREST_OVERDUE_testctid",
                "REPAY_PRINCIPAL_DUE_testctid",
                "REPAY_INTEREST_DUE_testctid",
                "OVERPAYMENT_BALANCE_testctid",
                "OVERPAYMENT_FEE_testctid",
            ],
            effective_date=effective_date,
        )
        self.assertEqual(mock_vault.instruct_posting_batch.call_count, 1)

    def test_handle_overdue(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("1000"),
            interest_due=Decimal("350.00"),
            principal=Decimal("100000"),
        )

        effective_date = DEFAULT_DATE + relativedelta(months=1)

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            loan_start_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            repayment_day=int(10),
            denomination=constants.DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(12),
            late_repayment_fee=Decimal(12),
            late_repayment_fee_income_account=accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
            grace_period=5,
            fulfillment_precision=2,
        )

        self.run_function("_handle_overdue", mock_vault, mock_vault, effective_date=effective_date)

        postings = [
            {
                "amount": Decimal("1000"),
                "asset": DEFAULT_ASSET,
                "client_transaction_id": "MOCK_HOOK_PRINCIPAL_OVERDUE",
                "denomination": constants.DEFAULT_DENOMINATION,
                "from_account_address": address.PRINCIPAL_OVERDUE,
                "from_account_id": VAULT_ACCOUNT_ID,
                "instruction_details": {
                    "description": ("Mark oustanding due amount of 1000 as PRINCIPAL_OVERDUE."),
                    "event": "MOVE_BALANCE_INTO_PRINCIPAL_OVERDUE",
                },
                "to_account_address": address.PRINCIPAL_DUE,
                "to_account_id": VAULT_ACCOUNT_ID,
            },
            {
                "amount": Decimal("350.00"),
                "asset": DEFAULT_ASSET,
                "client_transaction_id": "MOCK_HOOK_INTEREST_OVERDUE",
                "denomination": constants.DEFAULT_DENOMINATION,
                "from_account_address": address.INTEREST_OVERDUE,
                "from_account_id": VAULT_ACCOUNT_ID,
                "instruction_details": {
                    "description": ("Mark oustanding due amount of 350.00 as INTEREST_OVERDUE."),
                    "event": "MOVE_BALANCE_INTO_INTEREST_OVERDUE",
                },
                "to_account_address": address.INTEREST_DUE,
                "to_account_id": VAULT_ACCOUNT_ID,
            },
            {
                "amount": Decimal("12"),
                "asset": DEFAULT_ASSET,
                "client_transaction_id": "MOCK_HOOK_CHARGE_FEE",
                "denomination": constants.DEFAULT_DENOMINATION,
                "from_account_address": address.PENALTIES,
                "from_account_id": VAULT_ACCOUNT_ID,
                "instruction_details": {
                    "description": ("Incur late repayment fees of 12"),
                    "event": "INCUR_PENALTY_FEES",
                },
                "to_account_address": DEFAULT_ADDRESS,
                "to_account_id": accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in postings]

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

        mock_vault.start_workflow.assert_has_calls(
            [
                call(
                    workflow="LOAN_OVERDUE_REPAYMENT_NOTIFICATION",
                    context={
                        "account_id": VAULT_ACCOUNT_ID,
                        "repayment_amount": "1350.00",
                        "late_repayment_fee": "12",
                        "overdue_date": "2020-02-10",
                    },
                )
            ]
        )

    def test_handle_interest_capitalisation(self):
        balance_ts = self.account_balances(DEFAULT_DATE, capitalised_interest=Decimal("1000"))

        effective_date = DEFAULT_DATE + relativedelta(months=1)

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            loan_start_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            repayment_day=int(10),
            denomination=constants.DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(12),
            late_repayment_fee=Decimal(12),
            grace_period=5,
            fulfillment_precision=2,
            flags=["NOT_REPAYMENT_HOLIDAY"],
        )

        self.run_function(
            "_handle_interest_capitalisation",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
        )

        postings = [
            {
                "amount": Decimal("1000"),
                "asset": DEFAULT_ASSET,
                "client_transaction_id": "MOCK_HOOK_TRANSFER_ACCRUED_INTEREST_PENDING"
                "_CAPITALISATION_INTERNAL",
                "denomination": constants.DEFAULT_DENOMINATION,
                "from_account_address": address.PRINCIPAL_CAPITALISED_INTEREST,
                "from_account_id": VAULT_ACCOUNT_ID,
                "instruction_details": {
                    "description": ("Capitalise interest accrued to principal"),
                    "event": "TRANSFER_ACCRUED_INTEREST_PENDING_CAPITALISATION_TO_PRINCIPAL"
                    "_CAPITALISED_INTEREST",
                },
                "to_account_address": DEFAULT_ADDRESS,
                "to_account_id": accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT,
            },
            {
                "amount": Decimal("1000"),
                "asset": DEFAULT_ASSET,
                "client_transaction_id": "MOCK_HOOK_TRANSFER_ACCRUED_INTEREST_PENDING"
                "_CAPITALISATION_CUSTOMER",
                "denomination": constants.DEFAULT_DENOMINATION,
                "from_account_address": address.INTERNAL_CONTRA,
                "from_account_id": VAULT_ACCOUNT_ID,
                "instruction_details": {
                    "description": ("Capitalise interest accrued to principal"),
                    "event": "TRANSFER_ACCRUED_INTEREST_PENDING_CAPITALISATION_TO_PRINCIPAL"
                    "_CAPITALISED_INTEREST",
                },
                "to_account_address": address.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                "to_account_id": VAULT_ACCOUNT_ID,
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in postings]

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

    def test_handle_interest_capitalisation_no_repayment_capitalisation(self):
        balance_ts = self.account_balances(DEFAULT_DATE, capitalised_interest=Decimal("1000"))

        effective_date = DEFAULT_DATE + relativedelta(months=1)

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            loan_start_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            repayment_day=int(10),
            denomination=constants.DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(12),
            late_repayment_fee=Decimal(12),
            late_repayment_fee_income_account=accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
            grace_period=5,
            fulfillment_precision=2,
            amortisation_method=UnionItemValue(key="no_repayment"),
            capitalise_no_repayment_accrued_interest=UnionItemValue(key="daily"),
            interest_accrual_rest_type=UnionItemValue(key="daily"),
        )

        self.run_function(
            "_handle_interest_capitalisation",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
        )

        postings = [
            {
                "amount": Decimal("1000"),
                "asset": DEFAULT_ASSET,
                "client_transaction_id": "MOCK_HOOK_TRANSFER_ACCRUED_INTEREST_PENDING"
                "_CAPITALISATION_INTERNAL",
                "denomination": constants.DEFAULT_DENOMINATION,
                "from_account_address": address.PRINCIPAL_CAPITALISED_INTEREST,
                "from_account_id": VAULT_ACCOUNT_ID,
                "instruction_details": {
                    "description": ("Capitalise interest accrued to principal"),
                    "event": "TRANSFER_ACCRUED_INTEREST_PENDING_CAPITALISATION"
                    "_TO_PRINCIPAL_CAPITALISED_INTEREST",
                },
                "to_account_address": DEFAULT_ADDRESS,
                "to_account_id": accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT,
            },
            {
                "amount": Decimal("1000"),
                "asset": DEFAULT_ASSET,
                "client_transaction_id": "MOCK_HOOK_TRANSFER_ACCRUED_INTEREST_PENDING"
                "_CAPITALISATION_CUSTOMER",
                "denomination": constants.DEFAULT_DENOMINATION,
                "from_account_address": address.INTERNAL_CONTRA,
                "from_account_id": VAULT_ACCOUNT_ID,
                "instruction_details": {
                    "description": ("Capitalise interest accrued to principal"),
                    "event": "TRANSFER_ACCRUED_INTEREST_PENDING_CAPITALISATION"
                    "_TO_PRINCIPAL_CAPITALISED_INTEREST",
                },
                "to_account_address": address.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                "to_account_id": VAULT_ACCOUNT_ID,
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in postings]

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

    def test_handle_interest_capitalisation_no_capitalised_interest(self):
        balance_ts = self.account_balances(DEFAULT_DATE, capitalised_interest=Decimal("0"))

        effective_date = DEFAULT_DATE + relativedelta(months=1)

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            loan_start_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            repayment_day=int(10),
            denomination=constants.DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(12),
            late_repayment_fee=Decimal(12),
            late_repayment_fee_income_account=accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
            grace_period=5,
            fulfillment_precision=2,
            flags=["NOT_REPAYMENT_HOLIDAY"],
        )

        self.run_function(
            "_handle_interest_capitalisation",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls([])

    def test_get_penalty_daily_rate_with_base(self):
        effective_date = DEFAULT_DATE + timedelta(seconds=1)
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            loan_start_date=DEFAULT_DATE,
            fixed_interest_loan=UnionItemValue(key="True"),
            fixed_interest_rate=Decimal("0.012234"),
            variable_interest_rate=Decimal("0.2333"),
            penalty_interest_rate=Decimal("0.48"),
            penalty_includes_base_rate=UnionItemValue("True"),
            variable_rate_adjustment=Decimal("0.00"),
            repayment_day=5,
        )
        result = self.run_function(
            "_get_penalty_daily_rate", mock_vault, mock_vault, effective_date
        )
        expected = (Decimal("0.492234") / 365).quantize(Decimal(".0000000001"))
        self.assertEqual(result, expected)

    def test_get_penalty_daily_rate_without_base(self):
        effective_date = DEFAULT_DATE + timedelta(seconds=1)
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            loan_start_date=DEFAULT_DATE,
            fixed_interest_loan=UnionItemValue(key="True"),
            fixed_interest_rate=Decimal("0.0122"),
            variable_interest_rate=Decimal("0.2333"),
            penalty_interest_rate=Decimal("0.483212"),
            penalty_includes_base_rate=UnionItemValue("False"),
            variable_rate_adjustment=Decimal("0.00"),
            repayment_day=5,
        )
        result = self.run_function(
            "_get_penalty_daily_rate", mock_vault, mock_vault, effective_date
        )
        expected = (Decimal("0.483212") / 365).quantize(Decimal(".0000000001"))
        self.assertEqual(result, expected)

    def test_calculate_daily_penalty(self):
        effective_date = DEFAULT_DATE + timedelta(seconds=1)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            overpayment=Decimal("-150"),
            fees=Decimal("325"),
            principal_overdue=Decimal("123"),
            interest_overdue=Decimal("22.33"),
            nonexistant_address=Decimal("2"),
        )
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            loan_start_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fixed_interest_loan=UnionItemValue(key="True"),
            fixed_interest_rate=Decimal("0.0122"),
            variable_interest_rate=Decimal("0.2333"),
            penalty_interest_rate=Decimal("0.483212"),
            penalty_includes_base_rate=UnionItemValue("False"),
            repayment_day=5,
            fulfillment_precision=2,
            accrual_precision=5,
        )
        result = self.run_function(
            "_calculate_daily_penalty", mock_vault, mock_vault, effective_date
        )
        expected = Decimal("145.33") * (Decimal("0.483212") / 365).quantize(Decimal(".000001"))
        self.assertEqual(result["amount_accrued"], expected.quantize(Decimal(".0001")))

    def test_sum_outstanding_dues(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            principal_overdue=Decimal("150"),
            interest_overdue=Decimal("50"),
            overpayment=Decimal("-150"),
            fees=Decimal("325"),
            nonexistant_address=Decimal("2"),
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fulfillment_precision=2,
            accrual_precision=5,
        )

        outstanding_debt = self.run_function("_sum_outstanding_dues", mock_vault, mock_vault)

        self.assertEqual(outstanding_debt, Decimal("660.00"))

    def test_send_repayment_notification(self):
        effective_date = datetime(2020, 1, 10, tzinfo=timezone.utc)

        mock_vault = self.create_mock(
            creation_date=effective_date,
            repayment_period=int(10),
        )

        mock_monthly_due = Mock()
        mock_monthly_due.principal_due_excluding_overpayment = Decimal("150")
        mock_monthly_due.principal_excess = Decimal("0")
        mock_monthly_due.interest_due = Decimal("100")

        self.run_function(
            "_send_repayment_notification",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
            monthly_due={
                "principal_due_excluding_overpayment": 150,
                "interest_due": 100,
                "principal_excess": 123,
            },
        )

        mock_vault.start_workflow.assert_has_calls(
            [
                call(
                    workflow="LOAN_REPAYMENT_NOTIFICATION",
                    context={
                        "account_id": VAULT_ACCOUNT_ID,
                        "repayment_amount": "373",
                        "overdue_date": "2020-01-20",
                    },
                )
            ]
        )

    def test_get_outstanding_actual_principal(self):

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            overpayment=Decimal("-150"),
            emi_principal_excess=Decimal("222.12"),
            fees=Decimal("325"),
            nonexistant_address=Decimal("2"),
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fulfillment_precision=2,
        )

        outstanding_debt = self.run_function(
            "_get_outstanding_actual_principal", mock_vault, mock_vault
        )

        self.assertEqual(outstanding_debt, Decimal("100072.12"))

    def test_get_due_principal(self):

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            overpayment=Decimal("-150"),
            emi_principal_excess=Decimal("222.12"),
            fees=Decimal("325"),
            nonexistant_address=Decimal("2"),
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fulfillment_precision=2,
        )

        outstanding_debt = self.run_function("_get_due_principal", mock_vault, mock_vault)

        self.assertEqual(outstanding_debt, Decimal("100"))

    def test_get_due_principal_from_previous_date(self):

        previous_repayment_date = DEFAULT_DATE - relativedelta(days=10)
        balance_ts = self.account_balances(
            previous_repayment_date,
            principal_due=Decimal("105"),
            interest_due=Decimal("30.00"),
            principal=Decimal("100000"),
            overpayment=Decimal("0"),
            emi_principal_excess=Decimal("222.12"),
            fees=Decimal("325"),
            nonexistant_address=Decimal("2"),
        )

        balance_ts.extend(
            self.account_balances(
                DEFAULT_DATE,
                principal_due=Decimal("100"),
                interest_due=Decimal("35.00"),
                principal=Decimal("100000"),
                overpayment=Decimal("-150"),
                emi_principal_excess=Decimal("222.12"),
                fees=Decimal("325"),
                nonexistant_address=Decimal("2"),
            )
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fulfillment_precision=2,
        )

        outstanding_debt = self.run_function(
            "_get_due_principal", mock_vault, mock_vault, previous_repayment_date
        )

        self.assertEqual(outstanding_debt, Decimal("105"))

    def test_is_accrue_interest_on_due_principal_true(self):

        mock_vault = self.create_mock(
            accrue_interest_on_due_principal=UnionItemValue(key="True"),
        )

        accrue_on_due = self.run_function(
            "_is_accrue_interest_on_due_principal", mock_vault, mock_vault
        )

        self.assertEqual(accrue_on_due, True)

    def test_is_accrue_interest_on_due_principal_false(self):

        mock_vault = self.create_mock(
            accrue_interest_on_due_principal=UnionItemValue(key="False"),
        )

        accrue_on_due = self.run_function(
            "_is_accrue_interest_on_due_principal", mock_vault, mock_vault
        )

        self.assertEqual(accrue_on_due, False)

    def test_is_capitalise_penalty_interest_true(self):

        mock_vault = self.create_mock(
            capitalise_penalty_interest=UnionItemValue(key="True"),
        )

        result = self.run_function("_is_capitalise_penalty_interest", mock_vault, mock_vault)

        self.assertEqual(result, True)

    def test_is_capitalise_penalty_interest_false(self):

        mock_vault = self.create_mock(
            capitalise_penalty_interest=UnionItemValue(key="False"),
        )

        result = self.run_function("_is_capitalise_penalty_interest", mock_vault, mock_vault)

        self.assertEqual(result, False)

    def test_accrue_penalty_interest_capitalised(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_overdue=Decimal("100"),
            interest_overdue=Decimal("50"),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            capitalise_penalty_interest=UnionItemValue(key="True"),
            penalty_interest_rate=Decimal("0.5"),
            penalty_includes_base_rate=UnionItemValue("False"),
            fulfillment_precision=2,
            accrual_precision=5,
        )
        self.run_function("_handle_accrue_interest", mock_vault, mock_vault, DEFAULT_DATE)

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.20548"),
                    asset=DEFAULT_ASSET,
                    client_transaction_id="MOCK_HOOK_ACCRUE_AND_CAPITALISE_PENALTY"
                    "_INTEREST_CUSTOMER",
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_address=address.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    instruction_details={
                        "description": "Penalty interest accrual on overdue amount "
                        "capitalised to principal",
                        "event": "ACCRUE_AND_CAPITALISE_PENALTY_INTEREST",
                    },
                    override_all_restrictions=True,
                    to_account_address=address.INTERNAL_CONTRA,
                    to_account_id=VAULT_ACCOUNT_ID,
                ),
                call(
                    amount=Decimal("0.20548"),
                    asset=DEFAULT_ASSET,
                    client_transaction_id="MOCK_HOOK_ACCRUE_AND_CAPITALISE_PENALTY"
                    "_INTEREST_INTERNAL",
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_address=DEFAULT_ADDRESS,
                    from_account_id=accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT,
                    instruction_details={
                        "description": "Penalty interest accrual on overdue amount "
                        "capitalised to principal",
                        "event": "ACCRUE_AND_CAPITALISE_PENALTY_INTEREST",
                    },
                    override_all_restrictions=True,
                    to_account_address=DEFAULT_ADDRESS,
                    to_account_id=accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_MOCK_HOOK",
            effective_date=datetime(2020, 1, 10, 0, 0, tzinfo=timezone.utc),
            posting_instructions=[
                "MOCK_HOOK_ACCRUE_AND_CAPITALISE_PENALTY_INTEREST_CUSTOMER",
                "MOCK_HOOK_ACCRUE_AND_CAPITALISE_PENALTY_INTEREST_INTERNAL",
            ],
        )
        self.assertEqual(mock_vault.instruct_posting_batch.call_count, 1)

    def test_accrue_penalty_interest_not_capitalised(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_overdue=Decimal("100"),
            interest_overdue=Decimal("50"),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            capitalise_penalty_interest=UnionItemValue(key="False"),
            penalty_interest_rate=Decimal("0.5"),
            penalty_includes_base_rate=UnionItemValue("False"),
            fulfillment_precision=2,
            accrual_precision=5,
        )
        self.run_function("_handle_accrue_interest", mock_vault, mock_vault, DEFAULT_DATE)

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.21"),
                    asset=DEFAULT_ASSET,
                    client_transaction_id="MOCK_HOOK_ACCRUE_PENALTY_INTEREST",
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_address=address.PENALTIES,
                    from_account_id=VAULT_ACCOUNT_ID,
                    instruction_details={
                        "description": "Penalty interest accrual on overdue amount",
                        "event": "ACCRUE_PENALTY_INTEREST",
                    },
                    override_all_restrictions=True,
                    to_account_address=DEFAULT_ADDRESS,
                    to_account_id=accounts.INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT,
                )
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_MOCK_HOOK",
            effective_date=datetime(2020, 1, 10, 0, 0, tzinfo=timezone.utc),
            posting_instructions=["MOCK_HOOK_ACCRUE_PENALTY_INTEREST"],
        )
        self.assertEqual(mock_vault.instruct_posting_batch.call_count, 1)

    def test_get_capitalised_interest_amount(self):
        balance_ts = self.account_balances(DEFAULT_DATE, capitalised_interest=Decimal("1.01234"))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            fulfillment_precision=2,
            accrual_precision=5,
        )
        result = self.run_function("_get_capitalised_interest_amount", mock_vault, mock_vault)

        self.assertEqual(result, Decimal("1.01"))

    def test_get_transfer_capitalised_interest_instructions_no_interest(self):
        balance_ts = self.account_balances(DEFAULT_DATE, capitalised_interest=Decimal("0"))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            fulfillment_precision=2,
            accrual_precision=5,
        )
        self.run_function(
            "_get_transfer_capitalised_interest_instructions",
            mock_vault,
            mock_vault,
            address.ACCRUED_INTEREST_PENDING_CAPITALISATION,
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_get_transfer_capitalised_interest_instructions(self):
        balance_ts = self.account_balances(DEFAULT_DATE, capitalised_interest=Decimal("1.01"))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            fulfillment_precision=2,
            accrual_precision=5,
        )
        self.run_function(
            "_get_transfer_capitalised_interest_instructions",
            mock_vault,
            mock_vault,
            address.ACCRUED_INTEREST_PENDING_CAPITALISATION,
        )
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("1.01"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.PRINCIPAL_CAPITALISED_INTEREST,
                    to_account_id=accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    client_transaction_id="MOCK_HOOK_TRANSFER_ACCRUED_"
                    "INTEREST_PENDING_CAPITALISATION_INTERNAL",
                    instruction_details={
                        "description": "Capitalise interest accrued to principal",
                        "event": "TRANSFER_ACCRUED_INTEREST_PENDING_CAPITALISATION_TO_PRINCIPAL"
                        "_CAPITALISED_INTEREST",
                    },
                ),
                call(
                    amount=Decimal("1.01"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.INTERNAL_CONTRA,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                    asset=DEFAULT_ASSET,
                    client_transaction_id="MOCK_HOOK_TRANSFER_ACCRUED_"
                    "INTEREST_PENDING_CAPITALISATION_CUSTOMER",
                    instruction_details={
                        "description": "Capitalise interest accrued to principal",
                        "event": "TRANSFER_ACCRUED_INTEREST_PENDING_CAPITALISATION_TO_PRINCIPAL"
                        "_CAPITALISED_INTEREST",
                    },
                ),
            ]
        )

    def test_get_capital_for_penalty_accrual(self):

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            overpayment=Decimal("-150"),
            fees=Decimal("325"),
            principal_overdue=Decimal("123"),
            interest_overdue=Decimal("22.33"),
            nonexistant_address=Decimal("2"),
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fulfillment_precision=2,
        )

        result = self.run_function("_get_capital_for_penalty_accrual", mock_vault, mock_vault)

        self.assertEqual(result, Decimal("145.33"))

    def test_get_capital_for_penalty_accrual_no_compound_interest(self):

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            overpayment=Decimal("-150"),
            fees=Decimal("325"),
            principal_overdue=Decimal("123"),
            interest_overdue=Decimal("22.33"),
            nonexistant_address=Decimal("2"),
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fulfillment_precision=2,
            penalty_compounds_overdue_interest=UnionItemValue(key="False"),
        )

        result = self.run_function("_get_capital_for_penalty_accrual", mock_vault, mock_vault)

        self.assertEqual(result, Decimal("123"))

    def test_get_late_payment_balance(self):

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            overpayment=Decimal("-150"),
            fees=Decimal("325"),
            principal_overdue=Decimal("123"),
            interest_overdue=Decimal("22.33"),
            nonexistant_address=Decimal("2"),
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fulfillment_precision=2,
        )

        result = self.run_function("_get_late_payment_balance", mock_vault, vault=mock_vault)

        self.assertEqual(result, Decimal("470.33"))

    def test_pre_posting_code_rejects_non_gbp_denomination(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            overpayment=Decimal("-150"),
            fees=Decimal("325"),
            nonexistant_address=Decimal("2"),
        )

        postings = [
            self.outbound_hard_settlement(amount=50, denomination="EUR"),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fulfillment_precision=2,
            accrual_precision=5,
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=postings_batch,
                effective_date=DEFAULT_DATE,
            )
        self.assertEqual(e.exception.reason_code, RejectedReason.WRONG_DENOMINATION)
        self.assertEqual(
            str(e.exception),
            "Cannot make transactions in given denomination; "
            f"transactions must be in {constants.DEFAULT_DENOMINATION}",
        )
        self.assert_no_side_effects(mock_vault)

    def test_pre_posting_code_rejects_debits(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            overpayment=Decimal("-150"),
            fees=Decimal("325"),
            nonexistant_address=Decimal("2"),
        )

        postings = [
            self.outbound_hard_settlement(amount=50, denomination=constants.DEFAULT_DENOMINATION),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts, denomination=constants.DEFAULT_DENOMINATION
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=postings_batch,
                effective_date=DEFAULT_DATE,
            )
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(str(e.exception), "Debiting not allowed from this account")
        self.assert_no_side_effects(mock_vault)

    def test_pre_posting_code_rejects_paying_more_than_owed(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("2177.01"),
            accrued_interest=Decimal("376.71645"),
            interest_due=Decimal("733.68"),
            principal=Decimal("295702.16"),
            principal_overdue=Decimal("2120.83"),
            interest_overdue=Decimal("815.34"),
            overpayment=Decimal("0"),
            fees=Decimal("47.7"),
            nonexistant_address=Decimal("2"),
        )

        # max_repayment 317536.71 = outstanding_debt + overpayment_fee
        postings = [
            self.inbound_hard_settlement(
                amount="317536.72", denomination=constants.DEFAULT_DENOMINATION
            ),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            repayment_day=20,
            total_term=120,
            fulfillment_precision=2,
            accrual_precision=5,
            overpayment_fee_rate=Decimal("0.05"),
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=postings_batch,
                effective_date=DEFAULT_DATE,
            )
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(str(e.exception), "Cannot pay more than is owed")
        self.assert_no_side_effects(mock_vault)

    def test_pre_posting_code_rejects_overpayment_for_flat_interest(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("250"),
            interest_due=Decimal("7.75"),
            overpayment=Decimal("0"),
            accrued_interest=Decimal("1.25"),
            principal=Decimal("1000"),
            principal_overdue=Decimal("0"),
            interest_overdue=Decimal("0"),
            fees=Decimal("20"),
            nonexistant_address=Decimal("2"),
        )

        postings = [
            self.inbound_hard_settlement(amount="300", denomination=constants.DEFAULT_DENOMINATION),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            repayment_day=20,
            total_term=120,
            fulfillment_precision=2,
            accrual_precision=5,
            amortisation_method=UnionItemValue(key="flat_interest"),
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=postings_batch,
                effective_date=DEFAULT_DATE,
            )
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(
            str(e.exception),
            "Overpayments are not allowed for flat interest loans",
        )
        self.assert_no_side_effects(mock_vault)

    def test_pre_posting_code_rejects_overpayment_for_minimum_repayment(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("150"),
            interest_due=Decimal("7.75"),
            overpayment=Decimal("0"),
            accrued_interest=Decimal("1.25"),
            principal=Decimal("1000"),
            principal_overdue=Decimal("0"),
            interest_overdue=Decimal("0"),
            fees=Decimal("20"),
            nonexistant_address=Decimal("2"),
        )

        postings = [
            self.inbound_hard_settlement(amount="300", denomination=constants.DEFAULT_DENOMINATION),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            repayment_day=20,
            total_term=120,
            fulfillment_precision=2,
            accrual_precision=5,
            amortisation_method=UnionItemValue(key="minimum_repayment_with_balloon_payment"),
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=postings_batch,
                effective_date=DEFAULT_DATE,
            )
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(
            str(e.exception),
            "Overpayments are not allowed for minimum repayment with balloon payment loans",
        )
        self.assert_no_side_effects(mock_vault)

    def test_pre_posting_code_rejects_multiple_postings_in_batch(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            principal_overdue=Decimal("150"),
            interest_overdue=Decimal("50"),
            overpayment=Decimal("-150"),
            fees=Decimal("325"),
            nonexistant_address=Decimal("2"),
        )

        postings = [
            self.inbound_hard_settlement(
                amount="1000.01", denomination=constants.DEFAULT_DENOMINATION
            ),
            self.inbound_hard_settlement(
                amount="200.01", denomination=constants.DEFAULT_DENOMINATION
            ),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            total_term=20,
            repayment_day=20,
            fulfillment_precision=2,
            accrual_precision=5,
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=postings_batch,
                effective_date=DEFAULT_DATE,
            )
        self.assertEqual(e.exception.reason_code, RejectedReason.CLIENT_CUSTOM_REASON)
        self.assertEqual(str(e.exception), "Multiple postings in batch not supported")
        self.assert_no_side_effects(mock_vault)

    def test_pre_posting_code_accepts_credits(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal_overdue=Decimal("150"),
            interest_overdue=Decimal("50"),
            principal=Decimal("100000"),
            overpayment=Decimal("-150"),
            fees=Decimal("325"),
            nonexistant_address=Decimal("2"),
        )

        postings = [
            self.inbound_hard_settlement(amount="500", denomination=constants.DEFAULT_DENOMINATION),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            total_term=120,
            repayment_day=20,
            fulfillment_precision=2,
            accrual_precision=5,
        )

        try:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=postings_batch,
                effective_date=DEFAULT_DATE,
            )
        except Rejected:
            self.fail("pre_posting_code raised Rejected for reasonable credit")

    def test_overpayment_fee(self):
        test_cases = [
            {
                "description": "no overpayment, expected repayment made",
                "principal": Decimal("294136.29"),
                "principal_due": Decimal("5863.71"),
                "interest_due": Decimal("1019.18"),
                "repayment_amount": Decimal("6882.89"),
                "overpayment_fee_rate": Decimal("0.2"),
                "expected_result": Decimal("0"),
            },
            {
                "description": "small overpayment 0.11 over due amount",
                "principal": Decimal("294136.29"),
                "principal_due": Decimal("5863.71"),
                "interest_due": Decimal("1019.18"),
                "repayment_amount": Decimal("6883.00"),
                "overpayment_fee_rate": Decimal("0.2"),
                "expected_result": Decimal("0.02"),
            },
            {
                "description": "large overpayment 10000.11 over due amount",
                "principal": Decimal("294136.29"),
                "principal_due": Decimal("5863.71"),
                "interest_due": Decimal("1019.18"),
                "repayment_amount": Decimal("16883.00"),
                "overpayment_fee_rate": Decimal("0.2"),
                "expected_result": Decimal("2000.02"),
            },
            {
                "description": "overpayment of 500 with 0 in DUE",
                "principal": Decimal("294136.29"),
                "repayment_amount": Decimal("500.00"),
                "overpayment_fee_rate": Decimal("0.3"),
                "expected_result": Decimal("150"),
            },
            {
                "description": "total early repayment",
                "principal": Decimal("10000"),
                "principal_due": Decimal("1000"),
                "interest_due": Decimal("356"),
                "principal_overdue": Decimal("10"),
                "interest_overdue": Decimal("20"),
                "accrued_interest": Decimal("1500.01"),
                "fees": Decimal("87.78"),
                "repayment_amount": Decimal("13510.11"),
                "overpayment_fee_rate": Decimal("0.05"),
                "expected_result": Decimal("526.32"),
            },
            {
                "description": "repayment arbitrarily higher than total outstanding",
                "principal": Decimal("10000"),
                "principal_due": Decimal("1000"),
                "interest_due": Decimal("356"),
                "principal_overdue": Decimal("10"),
                "interest_overdue": Decimal("20"),
                "accrued_interest": Decimal("1500"),
                "repayment_amount": Decimal("999999999999"),
                "overpayment_fee_rate": Decimal("0.05"),
                "expected_result": Decimal("526.32"),
            },
        ]
        for test_case in test_cases:
            balance_ts = self.account_balances(
                DEFAULT_DATE,
                principal=test_case["principal"],
                principal_due=test_case.get("principal_due", 0),
                interest_due=test_case.get("interest_due", 0),
                principal_overdue=test_case.get("principal_overdue", 0),
                interest_overdue=test_case.get("interest_overdue", 0),
                accrued_interest=test_case.get("accrued_interest", 0),
                fees=test_case.get("fees", 0),
            )
            mock_vault = self.create_mock(
                overpayment_fee_rate=test_case["overpayment_fee_rate"],
                balance_ts=balance_ts,
            )
            result = self.run_function(
                "_get_overpayment_fee",
                mock_vault,
                mock_vault,
                repayment_amount=test_case["repayment_amount"],
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_schedule_delinquency_check(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal=Decimal("100000"),
            overpayment=Decimal("-12000"),
        )
        effective_date = DEFAULT_DATE

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(24),
            late_repayment_fee=Decimal(12),
            grace_period=5,
            check_delinquency_second=int(2),
        )

        self.run_function(
            "_schedule_delinquency_check",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
        )

        mock_vault.amend_schedule.assert_has_calls(
            [
                call(
                    event_type="CHECK_DELINQUENCY",
                    new_schedule={
                        "month": "1",
                        "day": "15",
                        "hour": "0",
                        "minute": "0",
                        "second": "2",
                        "year": "2020",
                    },
                )
            ]
        )

    def test_schedule_delinquency_check_0_grace_period(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_overdue=Decimal("1000"),
            interest_overdue=Decimal("2000"),
        )
        effective_date = DEFAULT_DATE

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(24),
            late_repayment_fee=Decimal(12),
            grace_period=0,
            delinquency_flags=dumps(["ACCOUNT_DELINQUENT"]),
            flags={"ACCOUNT_DELINQUENT": [(DEFAULT_DATE, False)]},
        )

        self.run_function(
            "_schedule_delinquency_check",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
        )

        mock_vault.start_workflow.assert_has_calls(
            [
                call(
                    workflow="LOAN_MARK_DELINQUENT",
                    context={"account_id": VAULT_ACCOUNT_ID},
                )
            ]
        )

    def test_handle_end_of_loan(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal=Decimal("100000"),
            overpayment=Decimal("-88000"),
            emi_principal_excess=Decimal("-12000"),
        )
        effective_date = DEFAULT_DATE

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(24),
            late_repayment_fee=Decimal(12),
            fulfillment_precision=2,
        )

        self.run_function(
            "_handle_end_of_loan", mock_vault, mock_vault, effective_date=effective_date
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("88000.00"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.OVERPAYMENT,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.PRINCIPAL,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_OVERPAYMENT_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring overpayments to PRINCIPAL address",
                        "event": "END_OF_LOAN",
                    },
                ),
                call(
                    amount=Decimal("12000.00"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.EMI_PRINCIPAL_EXCESS,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.PRINCIPAL,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_EMI_PRINCIPAL_EXCESS_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring principal excess to PRINCIPAL address",
                        "event": "END_OF_LOAN",
                    },
                ),
            ]
        )

    def test_handle_end_of_loan_without_overpayment(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal=Decimal("100000"),
            overpayment=Decimal("0.00"),
            emi_principal_excess=Decimal("0.00"),
        )
        effective_date = DEFAULT_DATE

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(24),
            late_repayment_fee=Decimal(12),
            fulfillment_precision=2,
        )

        self.run_function(
            "_handle_end_of_loan", mock_vault, mock_vault, effective_date=effective_date
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_close_code_with_outstanding_debt(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal=Decimal("0.00"),
            overpayment=Decimal("12.00"),
            emi_principal_excess=Decimal("0.00"),
        )
        effective_date = DEFAULT_DATE

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(24),
            late_repayment_fee=Decimal(12),
            fulfillment_precision=2,
            accrual_precision=5,
        )

        with self.assertRaises(Rejected) as e:
            self.run_function("close_code", mock_vault, effective_date=effective_date)
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(str(e.exception), "Cannot close account until account balance nets to 0")
        self.assert_no_side_effects(mock_vault)

    def test_close_code(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal=Decimal("100000"),
            overpayment=Decimal("-88000"),
            emi_principal_excess=Decimal("-12000"),
        )
        effective_date = DEFAULT_DATE

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(24),
            late_repayment_fee=Decimal(12),
            fulfillment_precision=2,
            accrual_precision=5,
        )
        self.run_function("close_code", mock_vault, effective_date=effective_date)

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("88000.00"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.OVERPAYMENT,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.PRINCIPAL,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_OVERPAYMENT_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring overpayments to PRINCIPAL address",
                        "event": "END_OF_LOAN",
                    },
                ),
                call(
                    amount=Decimal("12000.00"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.EMI_PRINCIPAL_EXCESS,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.PRINCIPAL,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_EMI_PRINCIPAL_EXCESS_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring principal excess to PRINCIPAL address",
                        "event": "END_OF_LOAN",
                    },
                ),
            ]
        )

    def test_close_code_repayment_holiday(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal=Decimal("-5000"),
            principal_capitalised_interest=Decimal("5000"),
            overpayment=Decimal("0"),
            emi_principal_excess=Decimal("0"),
        )
        effective_date = DEFAULT_DATE

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(24),
            late_repayment_fee=Decimal(12),
            fulfillment_precision=2,
            accrual_precision=5,
        )
        self.run_function("close_code", mock_vault, effective_date=effective_date)

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("5000.00"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.PRINCIPAL_CAPITALISED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.PRINCIPAL,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_PRINCIPAL_CAPITALISED_INTEREST_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring PRINCIPAL_CAPITALISED_INTEREST"
                        " to PRINCIPAL address",
                        "event": "END_OF_LOAN",
                    },
                )
            ]
        )

    def test_post_parameter_change_code_loan_start_date(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal=Decimal("100000"),
            overpayment=Decimal("-8000"),
            emi_principal_excess=Decimal("-4000"),
        )
        effective_date = DEFAULT_DATE

        old_parameter_values = {"loan_start_date": "2020-01-10"}

        updated_parameter_values = {"loan_start_date": "2020-09-02"}

        mock_vault = self.create_mock(
            loan_start_date=datetime.strptime("2020-09-02", "%Y-%m-%d"),
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fixed_interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(24),
            late_repayment_fee=Decimal(12),
        )

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values,
            updated_parameter_values,
            effective_date=effective_date,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("8000.00"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.OVERPAYMENT,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.PRINCIPAL,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_OVERPAYMENT_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring overpayments to PRINCIPAL address",
                        "event": "END_OF_LOAN",
                    },
                ),
                call(
                    amount=Decimal("4000.00"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.EMI_PRINCIPAL_EXCESS,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.PRINCIPAL,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_EMI_PRINCIPAL_EXCESS_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring principal excess to PRINCIPAL address",
                        "event": "END_OF_LOAN",
                    },
                ),
            ]
        )

    def test_handle_repayment_day_change_higher_repayment_day(self):
        effective_date = datetime(2020, 1, 12, 0, 0, 0, tzinfo=timezone.utc)
        repayment_day_schedule = datetime(2020, 1, 12, 0, 0, 0, tzinfo=timezone.utc)

        mock_vault = self.create_mock(
            repayment_day=20,
            REPAYMENT_DAY_SCHEDULE=repayment_day_schedule,
            repayment_minute=int(1),
            repayment_second=int(0),
        )
        previous_values = {"repayment_day": 12}
        updated_values = {"repayment_day": 20}
        self.run_function(
            "_handle_repayment_day_change",
            mock_vault,
            mock_vault,
            previous_values,
            updated_values,
            effective_date,
        )

        mock_vault.amend_schedule.assert_has_calls(
            [
                call(
                    event_type="REPAYMENT_DAY_SCHEDULE",
                    new_schedule={
                        "day": "20",
                        "hour": "0",
                        "minute": "1",
                        "second": "0",
                        # schedule run occured on 12th Jan, next run starts on 20th Feb
                        "start_date": "2020-02-20",
                    },
                )
            ]
        )

    def test_handle_handle_repayment_day_change_lower_repayment_day(self):
        # change takes effect on 28/01 and the payment date is changed from 20 to 12
        # previous payment was on 2020-01-20
        # next payment is expected to be on 2020-03-12
        effective_date = datetime(2020, 1, 28, 0, 0, 0, tzinfo=timezone.utc)
        repayment_day_schedule = datetime(2020, 1, 20, 0, 0, 0, tzinfo=timezone.utc)

        mock_vault = self.create_mock(
            repayment_day=12,
            REPAYMENT_DAY_SCHEDULE=repayment_day_schedule,
            repayment_minute=int(1),
            repayment_second=int(0),
        )
        previous_values = {"repayment_day": 20}
        updated_values = {"repayment_day": 12}
        self.run_function(
            "_handle_repayment_day_change",
            mock_vault,
            mock_vault,
            previous_values,
            updated_values,
            effective_date,
        )

        mock_vault.amend_schedule.assert_has_calls(
            [
                call(
                    event_type="REPAYMENT_DAY_SCHEDULE",
                    new_schedule={
                        "day": "12",
                        "hour": "0",
                        "minute": "1",
                        "second": "0",
                        "start_date": str(
                            (repayment_day_schedule + relativedelta(months=1, day=12)).date()
                        ),
                    },
                )
            ]
        )

    def test_handle_handle_repayment_day_change_same_repayment_day(self):
        # change takes effect on 28/01 and the payment date is changed from 20 to 20
        # previous payment was on 2020-01-20
        # next payment is expected to be on 2020-02-20, i.e. no change in schedule
        effective_date = datetime(2020, 1, 28, 0, 0, 0, tzinfo=timezone.utc)
        repayment_day_schedule = datetime(2020, 1, 20, 0, 0, 0, tzinfo=timezone.utc)

        mock_vault = self.create_mock(
            repayment_day=20, REPAYMENT_DAY_SCHEDULE=repayment_day_schedule
        )
        previous_values = {"repayment_day": 20}
        updated_values = {"repayment_day": 20}
        self.run_function(
            "_handle_repayment_day_change",
            mock_vault,
            mock_vault,
            previous_values,
            updated_values,
            effective_date,
        )

        mock_vault.amend_schedule.assert_has_calls([])

    def test_get_days_elapsed_since_last_repayment_date(self):
        mock_vault = self.create_mock(
            fixed_interest_loan=UnionItemValue(key="True"),
            fixed_interest_rate=Decimal("0.012234"),
            variable_interest_rate=Decimal("0.2333"),
            penalty_interest_rate=Decimal("0.48"),
            penalty_includes_base_rate=UnionItemValue("True"),
            variable_rate_adjustment=Decimal("0.00"),
            repayment_day=12,
            REPAYMENT_DAY_SCHEDULE=datetime(2020, 1, 12, 0, 0, 0, tzinfo=timezone.utc),
        )
        effective_date = datetime(2020, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        result = self.run_function(
            "_get_days_elapsed_since_last_repayment_date",
            mock_vault,
            mock_vault,
            effective_date,
        )
        self.assertEqual(result, 8)

    def test_get_days_elapsed_without_last_repayment_date(self):
        mock_vault = self.create_mock(
            fixed_interest_loan=UnionItemValue(key="True"),
            fixed_interest_rate=Decimal("0.012234"),
            variable_interest_rate=Decimal("0.2333"),
            penalty_interest_rate=Decimal("0.48"),
            penalty_includes_base_rate=UnionItemValue("True"),
            variable_rate_adjustment=Decimal("0.00"),
            repayment_day=12,
        )
        effective_date = datetime(2020, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        result = self.run_function(
            "_get_days_elapsed_since_last_repayment_date",
            mock_vault,
            mock_vault,
            effective_date,
        )
        self.assertEqual(result, 10)

    def test_accrue_interest_no_principal_no_accrual(self):
        balance_ts = self.account_balances(principal=Decimal(0))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fixed_interest_loan=UnionItemValue(key="True"),
            repayment_day=1,
            loan_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrual_precision=5,
            fulfillment_precision=2,
        )

        self.run_function(
            "_handle_accrue_interest",
            mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_accrue_interest_repayment_holiday_accrues_interest(self):
        balance_ts = self.account_balances(principal=Decimal(1000))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fixed_interest_loan=UnionItemValue(key="True"),
            repayment_day=1,
            loan_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrual_precision=5,
            fulfillment_precision=2,
            flags=["REPAYMENT_HOLIDAY"],
        )

        self.run_function(
            "_handle_accrue_interest",
            mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.02740"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.INTERNAL_CONTRA,
                    instruction_details={
                        "description": "Daily capitalised interest accrued at 0.002740% on "
                        "outstanding principal of 1000",
                        "event_type": "ACCRUE_INTEREST_PENDING_CAPITALISATION",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                ),
                call(
                    amount=Decimal("0.02740"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_INTERNAL",
                    from_account_id=accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": "Daily capitalised interest accrued at 0.002740% on "
                        "outstanding principal of 1000",
                        "event_type": "ACCRUE_INTEREST_PENDING_CAPITALISATION",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_MOCK_HOOK",
            posting_instructions=[
                "MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                "MOCK_HOOK_INTEREST_ACCRUAL_INTERNAL",
            ],
            effective_date=DEFAULT_DATE,
        )
        self.assertEqual(mock_vault.instruct_posting_batch.call_count, 1)

    def test_accrue_interest_repayment_holiday_accrues_no_interest_principal_0(self):
        balance_ts = self.account_balances(principal=Decimal(0))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fixed_interest_loan=UnionItemValue(key="True"),
            repayment_day=1,
            loan_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrued_interest_receivable_account=(
                accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
            ),
            interest_received_account=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrual_precision=5,
            fulfillment_precision=2,
            flags=["REPAYMENT_HOLIDAY"],
        )

        self.run_function(
            "_handle_accrue_interest",
            mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls([])
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_accrue_interest_principal_with_overpayment_accrues_interest_on_outstanding(
        self,
    ):
        balance_ts = self.account_balances(principal=Decimal(100), overpayment=Decimal(-10))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fixed_interest_loan=UnionItemValue(key="True"),
            repayment_day=1,
            loan_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrued_interest_receivable_account=(
                accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
            ),
            interest_received_account=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrual_precision=5,
            fulfillment_precision=2,
        )

        self.run_function(
            "_handle_accrue_interest",
            mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.00247"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.ACCRUED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.INTERNAL_CONTRA,
                    instruction_details={
                        "description": "Daily interest accrued at 0.002740% on outstanding "
                        "principal of 90.00",
                        "event_type": "ACCRUE_INTEREST",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                ),
                call(
                    amount=Decimal("0.00247"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_INTERNAL",
                    from_account_id=accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": "Daily interest accrued at 0.002740% on outstanding "
                        "principal of 90.00",
                        "event_type": "ACCRUE_INTEREST",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                ),
                call(
                    amount=Decimal("0.00274"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_EXPECTED",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.ACCRUED_EXPECTED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.INTERNAL_CONTRA,
                    instruction_details={
                        "description": "Expected daily interest accrued at 0.002740% on principal"
                        "_with_capitalised_interest of 100.00 and outstanding_principal of 90.00",
                        "event_type": "ACCRUE_INTEREST",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_MOCK_HOOK",
            posting_instructions=[
                "MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                "MOCK_HOOK_INTEREST_ACCRUAL_INTERNAL",
                "MOCK_HOOK_INTEREST_ACCRUAL_EXPECTED",
            ],
            effective_date=DEFAULT_DATE,
        )
        self.assertEqual(mock_vault.instruct_posting_batch.call_count, 1)

    def test_accrue_interest_principal_with_emi_excess_accrues_interest_on_outstanding(
        self,
    ):
        balance_ts = self.account_balances(
            principal=Decimal(100), emi_principal_excess=Decimal(-10)
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fixed_interest_loan=UnionItemValue(key="True"),
            repayment_day=1,
            loan_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrued_interest_receivable_account=(
                accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
            ),
            interest_received_account=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrual_precision=5,
            fulfillment_precision=2,
        )

        self.run_function(
            "_handle_accrue_interest",
            mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.00247"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.ACCRUED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.INTERNAL_CONTRA,
                    instruction_details={
                        "description": "Daily interest accrued at 0.002740% on outstanding "
                        "principal of 90.00",
                        "event_type": "ACCRUE_INTEREST",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                ),
                call(
                    amount=Decimal("0.00247"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_INTERNAL",
                    from_account_id=accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": "Daily interest accrued at 0.002740% on outstanding "
                        "principal of 90.00",
                        "event_type": "ACCRUE_INTEREST",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                ),
                call(
                    amount=Decimal("0.00274"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_EXPECTED",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.ACCRUED_EXPECTED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.INTERNAL_CONTRA,
                    instruction_details={
                        "description": "Expected daily interest accrued at 0.002740% on principal"
                        "_with_capitalised_interest of 100.00 and outstanding_principal of 90.00",
                        "event_type": "ACCRUE_INTEREST",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_MOCK_HOOK",
            posting_instructions=[
                "MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                "MOCK_HOOK_INTEREST_ACCRUAL_INTERNAL",
                "MOCK_HOOK_INTEREST_ACCRUAL_EXPECTED",
            ],
            effective_date=DEFAULT_DATE,
        )
        self.assertEqual(mock_vault.instruct_posting_batch.call_count, 1)

    def test_accrue_interest_principal_with_accrue_interest_on_due_accrues_interest(
        self,
    ):
        balance_ts = self.account_balances(principal=Decimal(100), principal_due=Decimal(100))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fixed_interest_loan=UnionItemValue(key="True"),
            repayment_day=1,
            loan_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrued_interest_receivable_account=(
                accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
            ),
            interest_received_account=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrue_interest_on_due_principal=UnionItemValue(key="True"),
            accrual_precision=5,
            fulfillment_precision=2,
        )

        self.run_function(
            "_handle_accrue_interest",
            mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.00548"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.ACCRUED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.INTERNAL_CONTRA,
                    instruction_details={
                        "description": "Daily interest accrued at 0.002740% on outstanding "
                        "principal of 200.00",
                        "event_type": "ACCRUE_INTEREST",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                ),
                call(
                    amount=Decimal("0.00548"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_INTERNAL",
                    from_account_id=accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": "Daily interest accrued at 0.002740% on outstanding "
                        "principal of 200.00",
                        "event_type": "ACCRUE_INTEREST",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                ),
                call(
                    amount=Decimal("0.00548"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_EXPECTED",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.ACCRUED_EXPECTED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.INTERNAL_CONTRA,
                    instruction_details={
                        "description": "Expected daily interest accrued at 0.002740% on principal"
                        "_with_capitalised_interest of 200.00 and outstanding_principal of 200.00",
                        "event_type": "ACCRUE_INTEREST",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_MOCK_HOOK",
            posting_instructions=[
                "MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                "MOCK_HOOK_INTEREST_ACCRUAL_INTERNAL",
                "MOCK_HOOK_INTEREST_ACCRUAL_EXPECTED",
            ],
            effective_date=DEFAULT_DATE,
        )
        self.assertEqual(mock_vault.instruct_posting_batch.call_count, 1)

    def test_accrue_interest_non_principal_address_no_accrued_interest(self):
        balance_ts = self.account_balances(
            principal_due=Decimal(10),
            interest_due=Decimal(20),
            fees=Decimal(30),
            principal_overdue=Decimal(50),
            interest_overdue=Decimal(60),
            default_committed=Decimal(70),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=constants.DEFAULT_DENOMINATION,
            fixed_interest_loan=UnionItemValue(key="True"),
            repayment_day=1,
            loan_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrued_interest_receivable_account=(
                accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
            ),
            interest_received_account=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            fulfillment_precision=2,
            accrual_precision=5,
        )
        accrue_interest_instructions = self.run_function(
            "_get_accrue_interest_instructions",
            mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
        )
        self.assertEqual(accrue_interest_instructions, [])

    def test_get_accrue_interest_schedule(self):
        loan_start_date = datetime(2020, 1, 11, 0, 0, 0, tzinfo=timezone.utc)
        loan_start_date_plus_day = loan_start_date + relativedelta(days=1)
        test_cases = [
            {
                "description": "declining principal",
                "amortisation_method": UnionItemValue(key="declining_principal"),
                "expected_result": {
                    "hour": "0",
                    "minute": "0",
                    "second": "1",
                    "start_date": str(loan_start_date_plus_day.date()),
                },
            },
            {
                "description": "no repayment",
                "amortisation_method": UnionItemValue(key="no_repayment"),
                "expected_result": {
                    "hour": "0",
                    "minute": "0",
                    "second": "1",
                    "start_date": str(loan_start_date_plus_day.date()),
                },
            },
            {
                "description": "flat interest",
                "amortisation_method": UnionItemValue(key="flat_interest"),
                "expected_result": {
                    "hour": "0",
                    "minute": "0",
                    "second": "1",
                    "start_date": str(loan_start_date_plus_day.date()),
                    "end_date": str(loan_start_date_plus_day.date()),
                },
            },
            {
                "description": "rule of 78",
                "amortisation_method": UnionItemValue(key="rule_of_78"),
                "expected_result": {
                    "hour": "0",
                    "minute": "0",
                    "second": "1",
                    "start_date": str(loan_start_date_plus_day.date()),
                    "end_date": str(loan_start_date_plus_day.date()),
                },
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                amortisation_method=test_case["amortisation_method"],
                loan_start_date=loan_start_date,
            )
            result = self.run_function(
                "_get_accrue_interest_schedule",
                mock_vault,
                vault=mock_vault,
            )
            self.assertEqual(
                result,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_schedules_call_instruct_posting_batch_only_once(self):
        balance_ts = self.account_balances(
            principal_due=Decimal(10),
            interest_due=Decimal(20),
            fees=Decimal(30),
            principal_overdue=Decimal(50),
            interest_overdue=Decimal(60),
            default_committed=Decimal(70),
        )
        event_types = [
            "ACCRUE_INTEREST",
            "REPAYMENT_DAY_SCHEDULE",
            "CHECK_OVERDUE",
            "CHECK_DELINQUENCY",
        ]
        for event_type in event_types:
            mock_vault = self.create_mock(
                balance_ts=balance_ts,
                denomination=constants.DEFAULT_DENOMINATION,
                fixed_interest_loan=UnionItemValue(key="True"),
                repayment_day=1,
                loan_start_date=DEFAULT_DATE,
                fixed_interest_rate=Decimal("0.01"),
                accrued_interest_receivable_account=(
                    accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
                ),
                interest_received_account=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
                fulfillment_precision=2,
                accrual_precision=5,
                repayment_period=10,
            )
            self.run_function(
                "scheduled_code",
                mock_vault,
                event_type=event_type,
                effective_date=DEFAULT_DATE,
            )
            self.assertIn(
                mock_vault.instruct_posting_batch.call_count,
                [0, 1],
                f"{event_type} has called instruct_posting_batch more than once",
            )

    def test_is_balloon_payment_loan(self):
        test_cases = [
            {
                "description": "declining_principal",
                "amortisation_method": UnionItemValue(key="declining_principal"),
                "expected_result": False,
            },
            {
                "description": "flat_interest",
                "amortisation_method": UnionItemValue(key="flat_interest"),
                "expected_result": False,
            },
            {
                "description": "rule_of_78",
                "amortisation_method": UnionItemValue(key="rule_of_78"),
                "expected_result": False,
            },
            {
                "description": "interest_only",
                "amortisation_method": UnionItemValue(key="interest_only"),
                "expected_result": True,
            },
            {
                "description": "no_repayment",
                "amortisation_method": UnionItemValue(key="no_repayment"),
                "expected_result": True,
            },
            {
                "description": "minimum_repayment",
                "amortisation_method": UnionItemValue(key="minimum_repayment_with_balloon_payment"),
                "expected_result": True,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(amortisation_method=test_case["amortisation_method"])

            result = self.run_function("_is_balloon_payment_loan", mock_vault, mock_vault)
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_is_no_repayment_loan(self):
        test_cases = [
            {
                "description": "declining_principal",
                "amortisation_method": UnionItemValue(key="declining_principal"),
                "expected_result": False,
            },
            {
                "description": "flat_interest",
                "amortisation_method": UnionItemValue(key="flat_interest"),
                "expected_result": False,
            },
            {
                "description": "rule_of_78",
                "amortisation_method": UnionItemValue(key="rule_of_78"),
                "expected_result": False,
            },
            {
                "description": "interest_only",
                "amortisation_method": UnionItemValue(key="interest_only"),
                "expected_result": False,
            },
            {
                "description": "no_repayment",
                "amortisation_method": UnionItemValue(key="no_repayment"),
                "expected_result": True,
            },
            {
                "description": "minimum_repayment",
                "amortisation_method": UnionItemValue(key="minimum_repayment_with_balloon_payment"),
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(amortisation_method=test_case["amortisation_method"])

            result = self.run_function("_is_no_repayment_loan", mock_vault, mock_vault)
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_is_no_repayment_loan_interest_to_be_capitalised(self):
        test_cases = [
            {
                "description": "not a no_repayment loan",
                "amortisation_method": UnionItemValue(key="declining_principal"),
                "capitalise_no_repayment_accrued_interest": UnionItemValue(key="no_capitalisation"),
                "expected_result": False,
            },
            {
                "description": "no_repayment loan without capitalisation",
                "amortisation_method": UnionItemValue(key="no_repayment"),
                "capitalise_no_repayment_accrued_interest": UnionItemValue(key="no_capitalisation"),
                "expected_result": False,
            },
            {
                "description": "no_repayment loan with capitalisation, daily capitalisation",
                "amortisation_method": UnionItemValue(key="no_repayment"),
                "capitalise_no_repayment_accrued_interest": UnionItemValue(key=constants.DAILY),
                "expected_result": True,
            },
            {
                "description": "no_repayment loan with capitalisation, monthly capitalisation,"
                " invalid day",
                "amortisation_method": UnionItemValue(key="no_repayment"),
                "capitalise_no_repayment_accrued_interest": UnionItemValue(key=constants.MONTHLY),
                "expected_result": False,
            },
            {
                "description": "no_repayment loan with capitalisation, monthly capitalisation,"
                " valid day",
                "amortisation_method": UnionItemValue(key="no_repayment"),
                "capitalise_no_repayment_accrued_interest": UnionItemValue(key=constants.MONTHLY),
                "effective_date": DEFAULT_DATE + relativedelta(months=1),
                "expected_result": True,
            },
            {
                "description": "no_repayment loan with capitalisation, monthly capitalisation,"
                " loan start day > 28, effective_date in Feb valid day",
                "amortisation_method": UnionItemValue(key="no_repayment"),
                "capitalise_no_repayment_accrued_interest": UnionItemValue(key=constants.MONTHLY),
                "loan_start_date": datetime(2021, 1, 31, tzinfo=timezone.utc),
                "effective_date": datetime(2021, 2, 28, tzinfo=timezone.utc),
                "expected_result": True,
            },
            {
                "description": "no_repayment loan with capitalisation, monthly capitalisation,"
                " loan start day > 28 effective_date in May, invalid day",
                "amortisation_method": UnionItemValue(key="no_repayment"),
                "capitalise_no_repayment_accrued_interest": UnionItemValue(key=constants.MONTHLY),
                "loan_start_date": datetime(2021, 1, 30, tzinfo=timezone.utc),
                "effective_date": datetime(2021, 5, 31, tzinfo=timezone.utc),
                "expected_result": False,
            },
            {
                "description": "no_repayment loan with capitalisation, monthly capitalisation,"
                " loan start day > 28 effective_date in May, valid day",
                "amortisation_method": UnionItemValue(key="no_repayment"),
                "capitalise_no_repayment_accrued_interest": UnionItemValue(key=constants.MONTHLY),
                "loan_start_date": datetime(2021, 1, 30, tzinfo=timezone.utc),
                "effective_date": datetime(2021, 5, 30, tzinfo=timezone.utc),
                "expected_result": True,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                amortisation_method=test_case["amortisation_method"],
                capitalise_no_repayment_accrued_interest=test_case[
                    "capitalise_no_repayment_accrued_interest"
                ],
                loan_start_date=test_case.get("loan_start_date", DEFAULT_DATE),
            )

            effective_date = test_case.get("effective_date", DEFAULT_DATE + timedelta(days=1))

            result = self.run_function(
                "_is_no_repayment_loan_interest_to_be_capitalised",
                mock_vault,
                mock_vault,
                effective_date,
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_balloon_payment_schedule(self):
        test_cases = [
            {
                "description": "balloon date delta empty, no_repayment",
                "balloon_payment_days_delta": None,
                "amortisation_method": "no_repayment",
                "expected_result": (
                    "BALLOON_PAYMENT_SCHEDULE",
                    {
                        "year": str(2020),
                        "month": str(2),
                        "day": str(1),
                        "hour": str(0),
                        "minute": str(1),
                        "second": str(0),
                    },
                ),
            },
            {
                "description": "balloon date delta empty, min_repayment",
                "balloon_payment_days_delta": None,
                "amortisation_method": "minimum_repayment_with_balloon_payment",
                "expected_result": (
                    "BALLOON_PAYMENT_SCHEDULE",
                    {
                        "year": str(2020),
                        "month": str(1),
                        "day": str(2),
                        "hour": str(0),
                        "minute": str(1),
                        "second": str(0),
                        "start_date": datetime.strftime(datetime(2020, 1, 2), "%Y-%m-%d"),
                        "end_date": datetime.strftime(
                            datetime(2020, 1, 2),
                            "%Y-%m-%d",
                        ),
                    },
                ),
            },
            {
                "description": "balloon date delta not empty, min_repayment",
                "balloon_payment_days_delta": 5,
                "amortisation_method": "minimum_repayment_with_balloon_payment",
                "expected_result": (
                    "BALLOON_PAYMENT_SCHEDULE",
                    {
                        "year": str(2020),
                        "month": str(1),
                        "day": str(2),
                        "hour": str(0),
                        "minute": str(1),
                        "second": str(0),
                        "start_date": datetime.strftime(datetime(2020, 1, 2), "%Y-%m-%d"),
                        "end_date": datetime.strftime(
                            datetime(2020, 1, 2),
                            "%Y-%m-%d",
                        ),
                    },
                ),
            },
            {
                "description": "balloon date delta not empty, interest_only",
                "balloon_payment_days_delta": 5,
                "amortisation_method": "interest_only",
                "expected_result": (
                    "BALLOON_PAYMENT_SCHEDULE",
                    {
                        "year": str(2020),
                        "month": str(1),
                        "day": str(2),
                        "hour": str(0),
                        "minute": str(1),
                        "second": str(0),
                        "start_date": datetime.strftime(datetime(2020, 1, 2), "%Y-%m-%d"),
                        "end_date": datetime.strftime(
                            datetime(2020, 1, 2),
                            "%Y-%m-%d",
                        ),
                    },
                ),
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                amortisation_method=UnionItemValue(key=test_case["amortisation_method"]),
                balloon_payment_days_delta=OptionalValue(test_case["balloon_payment_days_delta"]),
                repayment_day=10,
                repayment_hour=0,
                repayment_minute=1,
                repayment_second=0,
                loan_start_date=datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                total_term=1,
                REPAYMENT_DAY_SCHEDULE=None,
            )

            result = self.run_function("_get_balloon_payment_schedule", mock_vault, mock_vault)
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_should_handle_balloon_payment(self):
        test_cases = [
            {
                "description": "Not final repayment event",
                "balloon_payment_days_delta": None,
                "effective_date": DEFAULT_DATE,
                "expected_result": False,
            },
            {
                "description": "Final repayment event, delta is zero",
                "balloon_payment_days_delta": 0,
                "expected_result": True,
            },
            {
                "description": "Final repayment event, delta is not zero",
                "balloon_payment_days_delta": 5,
                "expected_result": False,
            },
            {
                "description": "Final repayment event, delta is None",
                "balloon_payment_days_delta": None,
                "expected_result": True,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                balloon_payment_days_delta=OptionalValue(test_case["balloon_payment_days_delta"]),
                repayment_day=10,
                loan_start_date=datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                total_term=2,
                REPAYMENT_DAY_SCHEDULE=None,
            )
            effective_date = test_case.get(
                "effective_date", datetime(2020, 3, 10, tzinfo=timezone.utc)
            )
            result = self.run_function(
                "_should_handle_balloon_payment", mock_vault, mock_vault, effective_date
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_should_enable_balloon_payment_schedule(self):
        test_cases = [
            {
                "description": "no_repayment loan",
                "amortisation_method": "no_repayment",
                "balloon_payment_days_delta": 5,
                "expected_result": False,
            },
            {
                "description": "delta is zero",
                "amortisation_method": "interest_only",
                "balloon_payment_days_delta": 0,
                "expected_result": False,
            },
            {
                "description": "delta is None",
                "amortisation_method": "interest_only",
                "balloon_payment_days_delta": None,
                "expected_result": False,
            },
            {
                "description": "Not last payment date",
                "amortisation_method": "interest_only",
                "balloon_payment_days_delta": 5,
                "effective_date": DEFAULT_DATE,
                "expected_result": False,
            },
            {
                "description": "last payment date should enable schedule",
                "amortisation_method": "interest_only",
                "balloon_payment_days_delta": 5,
                "effective_date": datetime(2020, 3, 10, tzinfo=timezone.utc),
                "expected_result": True,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                amortisation_method=UnionItemValue(key=test_case["amortisation_method"]),
                balloon_payment_days_delta=OptionalValue(test_case["balloon_payment_days_delta"]),
                loan_start_date=datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                total_term=2,
                repayment_day=10,
                REPAYMENT_DAY_SCHEDULE=None,
            )
            effective_date = test_case.get(
                "effective_date", datetime(2020, 3, 10, tzinfo=timezone.utc)
            )

            result = self.run_function(
                "_should_enable_balloon_payment_schedule",
                mock_vault,
                mock_vault,
                effective_date,
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_replace_repayment_day_schedule_with_balloon_payment(self):

        mock_vault = self.create_mock(
            amortisation_method=UnionItemValue(key="interest_only"),
            balloon_payment_days_delta=OptionalValue(5),
            repayment_hour=0,
            repayment_minute=1,
            repayment_second=0,
            repayment_day=10,
            loan_start_date=datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            total_term=2,
            REPAYMENT_DAY_SCHEDULE=None,
        )
        effective_date = datetime(2020, 3, 10, tzinfo=timezone.utc)

        self.run_function(
            "_replace_repayment_day_schedule_with_balloon_payment",
            mock_vault,
            mock_vault,
            effective_date,
        )
        mock_vault.amend_schedule.assert_has_calls(
            [
                call(
                    event_type="BALLOON_PAYMENT_SCHEDULE",
                    new_schedule={
                        "year": "2020",
                        "month": "3",
                        "day": "15",
                        "hour": "0",
                        "minute": "1",
                        "second": "0",
                    },
                ),
                call(
                    event_type="REPAYMENT_DAY_SCHEDULE",
                    new_schedule={
                        "hour": "0",
                        "minute": "1",
                        "second": "0",
                        "start_date": str(effective_date.date()),
                        "end_date": str(effective_date.date()),
                    },
                ),
            ]
        )

    def test_get_remaining_term_no_repayment_loan(self):
        test_cases = [
            {
                "description": "effective_date = loan start date",
                "loan_start_date": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "effective_date": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "expected_result": 36,
            },
            {
                "description": "effective_date in same month as loan start date",
                "loan_start_date": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "effective_date": datetime(2020, 1, 24, tzinfo=timezone.utc),
                "expected_result": 36,
            },
            {
                "description": "effective_date > loan start date start of month",
                "loan_start_date": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "effective_date": datetime(2020, 3, 1, tzinfo=timezone.utc),
                "expected_result": 34,
            },
            {
                "description": "effective_date > loan start date end of month",
                "loan_start_date": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "effective_date": datetime(2020, 3, 26, tzinfo=timezone.utc),
                "expected_result": 34,
            },
            {
                "description": "effective_date different year to loan start date",
                "loan_start_date": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "effective_date": datetime(2022, 3, 26, tzinfo=timezone.utc),
                "expected_result": 10,
            },
            {
                "description": "Remaining term is 1",
                "loan_start_date": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "effective_date": datetime(2022, 12, 26, tzinfo=timezone.utc),
                "expected_result": 1,
            },
            {
                "description": "Remaining term is 0",
                "loan_start_date": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "effective_date": datetime(2023, 1, 1, tzinfo=timezone.utc),
                "expected_result": 0,
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock(
                loan_start_date=test_case["loan_start_date"],
                total_term=36,
            )

            result = self.run_function(
                "_get_remaining_term_no_repayment_loan",
                mock_vault,
                mock_vault,
                test_case["effective_date"],
                test_case["loan_start_date"],
            )
            self.assertEqual(result, test_case["expected_result"])

    def test_get_expected_balloon_payment_amount(self):
        test_cases = [
            {
                "description": "Declining principal loan",
                "amortisation_method": "declining_principal",
                "balloon_payment_amount": None,
                "balloon_emi_amount": None,
                "expected_result": Decimal("0"),
            },
            {
                "description": "No repayment loan",
                "amortisation_method": "no_repayment",
                "balloon_payment_amount": None,
                "balloon_emi_amount": None,
                "expected_result": Decimal("8000"),
            },
            {
                "description": "Interest only loan",
                "amortisation_method": "interest_only",
                "balloon_payment_amount": None,
                "balloon_emi_amount": None,
                "expected_result": Decimal("8000"),
            },
            {
                "description": "Minimum repayment loan, balloon amount",
                "amortisation_method": "minimum_repayment_with_balloon_payment",
                "balloon_payment_amount": Decimal("1000"),
                "balloon_emi_amount": None,
                "expected_result": Decimal("1000"),
            },
            {
                "description": "Minimum repayment loan, emi amount 3 year loan",
                "amortisation_method": "minimum_repayment_with_balloon_payment",
                "balloon_payment_amount": None,
                "balloon_emi_amount": Decimal("821"),
                "principal": Decimal("100000"),
                "total_term": 36,
                "expected_result": Decimal("75743.79"),
            },
            {
                "description": "Minimum repayment loan, emi amount 1 year loan",
                "amortisation_method": "minimum_repayment_with_balloon_payment",
                "balloon_payment_amount": None,
                "balloon_emi_amount": Decimal("1850"),
                "principal": Decimal("100000"),
                "total_term": 12,
                "expected_result": Decimal("79613.80"),
            },
        ]
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal=Decimal("10000"),
            overpayment=Decimal("-2000"),
        )
        for test_case in test_cases:
            mock_vault = self.create_mock(
                balance_ts=balance_ts,
                amortisation_method=UnionItemValue(key=test_case["amortisation_method"]),
                balloon_payment_amount=OptionalValue(test_case["balloon_payment_amount"]),
                balloon_emi_amount=OptionalValue(test_case["balloon_emi_amount"]),
                total_term=test_case.get("total_term", "1"),
                fulfillment_precision=2,
                fixed_interest_loan=UnionItemValue(key=True),
                fixed_interest_rate=Decimal("0.02"),
                principal=test_case.get("principal", "10000"),
            )

            result = self.run_function(
                "_get_expected_balloon_payment_amount",
                mock_vault,
                vault=mock_vault,
                effective_date=DEFAULT_DATE + timedelta(seconds=1),
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])


class CommonHelperTest(LoanTest):
    contract_file = contract_files.CONTRACT_FILE
    side = Tside.ASSET
    linked_contract_modules = {
        "utils": {"path": files.UTILS_FILE},
        "amortisation": {"path": files.AMORTISATION_FILE},
    }

    def test_precision_doesnt_round_less_dp(self):
        mock_vault = self.create_mock()

        rounded_amount = self.run_function(
            "_round_to_precision", mock_vault, precision=5, amount=Decimal("1.11")
        )

        self.assertEqual(rounded_amount, Decimal("1.11000"))

    def test_round_to_precision_0dp(self):
        mock_vault = self.create_mock()

        rounded_amount = self.run_function(
            "_round_to_precision", mock_vault, precision=0, amount=Decimal("1.1111111")
        )

        self.assertEqual(rounded_amount, Decimal("1.0"))

    def test_round_to_precision_5dp(self):
        mock_vault = self.create_mock()

        rounded_amount = self.run_function(
            "_round_to_precision", mock_vault, precision=5, amount=Decimal("1.1111111")
        )

        self.assertEqual(rounded_amount, Decimal("1.11111"))

    def test_round_to_precision_15dp(self):
        mock_vault = self.create_mock()

        rounded_amount = self.run_function(
            "_round_to_precision",
            mock_vault,
            precision=15,
            amount=Decimal("1.1111111111111111111"),
        )

        self.assertEqual(rounded_amount, Decimal("1.111111111111111"))

    def test_create_interest_remainder_posting_no_remainder_no_posting(self):
        mock_vault = self.create_mock()

        interest_remainder_postings = self.run_function(
            "_create_interest_remainder_posting",
            mock_vault,
            vault=mock_vault,
            interest_address=address.ACCRUED_INTEREST,
            actual_balance=Decimal("123.45"),
            rounded_balance=Decimal("123.45"),
            event_type="MOCK_EVENT",
            interest_received_account=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrued_interest_receivable_account=(
                accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
            ),
            denomination=constants.DEFAULT_DENOMINATION,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        self.assertEqual(len(interest_remainder_postings), 0)

    def test_create_interest_remainder_posting_negative_remainder(self):
        mock_vault = self.create_mock()

        interest_remainder_postings = self.run_function(
            "_create_interest_remainder_posting",
            mock_vault,
            vault=mock_vault,
            interest_address=address.ACCRUED_INTEREST,
            actual_balance=Decimal("123.4433"),
            rounded_balance=Decimal("123.45"),
            event_type="MOCK_EVENT",
            interest_received_account=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrued_interest_receivable_account=(
                accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
            ),
            denomination=constants.DEFAULT_DENOMINATION,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.0067"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.ACCRUED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="MOCK_EVENT_REMAINDER_MOCK_HOOK_"
                    f"{constants.DEFAULT_DENOMINATION}_CUSTOMER",
                    instruction_details={
                        "description": "Extra interest charged to customer from negative remainder"
                        " due to repayable amount for ACCRUED_INTEREST rounded up",
                        "event_type": "MOCK_EVENT",
                    },
                ),
                call(
                    amount=Decimal("0.0067"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_id=accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="MOCK_EVENT_REMAINDER_MOCK_HOOK_"
                    f"{constants.DEFAULT_DENOMINATION}_INTERNAL",
                    instruction_details={
                        "description": f"Extra interest charged to account {VAULT_ACCOUNT_ID} from "
                        "negative remainder due to repayable amount for "
                        f"{address.ACCRUED_INTEREST} rounded up",
                        "event_type": "MOCK_EVENT",
                    },
                ),
            ]
        )
        self.assertEqual(len(interest_remainder_postings), 2)

    def test_create_interest_remainder_posting_positive_remainder(self):
        mock_vault = self.create_mock()

        interest_remainder_postings = self.run_function(
            "_create_interest_remainder_posting",
            mock_vault,
            vault=mock_vault,
            interest_address=address.ACCRUED_INTEREST,
            actual_balance=Decimal("123.4567"),
            rounded_balance=Decimal("123.45"),
            event_type="MOCK_EVENT",
            interest_received_account=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrued_interest_receivable_account=(
                accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
            ),
            denomination=constants.DEFAULT_DENOMINATION,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.0067"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=address.INTERNAL_CONTRA,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=address.ACCRUED_INTEREST,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="MOCK_EVENT_REMAINDER_MOCK_HOOK_"
                    f"{constants.DEFAULT_DENOMINATION}_CUSTOMER",
                    instruction_details={
                        "description": "Extra interest returned to customer from positive "
                        f"remainder due to repayable amount for {address.ACCRUED_INTEREST} "
                        "rounded down",
                        "event_type": "MOCK_EVENT",
                    },
                ),
                call(
                    amount=Decimal("0.0067"),
                    denomination=constants.DEFAULT_DENOMINATION,
                    from_account_id=accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="MOCK_EVENT_REMAINDER_MOCK_HOOK_"
                    f"{constants.DEFAULT_DENOMINATION}_INTERNAL",
                    instruction_details={
                        "description": f"Extra interest returned to account {VAULT_ACCOUNT_ID} "
                        "from positive remainder due to repayable amount for "
                        f"{address.ACCRUED_INTEREST} rounded down",
                        "event_type": "MOCK_EVENT",
                    },
                ),
            ]
        )
        self.assertEqual(len(interest_remainder_postings), 2)

    def test_calculate_next_repayment_date_start_date_before_repayment_day(self):
        test_cases = [
            {
                "description": "day before first repayment day",
                "effective_date": datetime(2020, 2, 4, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "over a month before first repayment day",
                "effective_date": datetime(2020, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "get first repayment date when run later in account lifecycle",
                "effective_date": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 9, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "topup before first repayment day setting start date in future",
                "effective_date": datetime(2020, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "topup_date": datetime(2020, 2, 4, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "topup after first repayment day",
                "effective_date": datetime(2020, 2, 6, 10, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
                "topup_date": datetime(2020, 2, 6, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 4, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "1 microsecond before first repayment day",
                "effective_date": datetime(2020, 2, 4, 23, 59, 59, 999999, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "same day as first repayment day at 00:00",
                "effective_date": datetime(2020, 2, 5, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "same datetime as first repayment day",
                "effective_date": datetime(2020, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "1 microsecond after first repayment day event",
                "effective_date": datetime(2020, 2, 5, 0, 1, 0, 1, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "1 microsecond before mid repayment day event",
                "effective_date": datetime(2020, 8, 5, 0, 0, 0, 999999, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 7, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 8, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "some days before last repayment day",
                "effective_date": datetime(2020, 12, 1, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 11, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 12, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "repayment day changed from 10 to 5",
                "effective_date": datetime(2020, 6, 11, 12, 1, 1, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 6, 10, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 7, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "repayment day changed from 1 to 5",
                "effective_date": datetime(2020, 6, 1, 12, 1, 1, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 6, 1, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 7, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
        ]
        for test_case in test_cases:
            start_date = (
                test_case["topup_date"]
                if "topup_date" in test_case
                else (datetime(2020, 1, 1, tzinfo=timezone.utc))
            )
            amortisation_method = UnionItemValue(key="declining_principal")
            mock_vault = self.create_mock(
                total_term=12,
                repayment_day=5,
                repayment_hour=0,
                repayment_minute=1,
                repayment_second=0,
                loan_start_date=start_date,
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
                amortisation_method=amortisation_method,
            )
            next_payment_date = self.run_function(
                "_calculate_next_repayment_date",
                mock_vault,
                vault=mock_vault,
                effective_date=test_case["effective_date"],
            )
            self.assertEqual(
                next_payment_date,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_calculate_next_repayment_date_start_date_same_as_repayment_day(self):
        test_cases = [
            {
                "description": "day before first repayment day",
                "effective_date": datetime(2020, 3, 4, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "over a month before first repayment day",
                "effective_date": datetime(2020, 1, 5, 0, 1, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "topup before first repayment day setting start date in future",
                "effective_date": datetime(2020, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "topup_date": datetime(2020, 2, 4, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "topup after first repayment day",
                "effective_date": datetime(2020, 3, 6, 10, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
                "topup_date": datetime(2020, 3, 6, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 5, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "1 microsecond before first repayment day",
                "effective_date": datetime(2020, 2, 4, 23, 59, 59, 999999, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "same day as first repayment day at 00:00",
                "effective_date": datetime(2020, 2, 5, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "same datetime as first repayment day",
                "effective_date": datetime(2020, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "1 microsecond after first repayment day event",
                "effective_date": datetime(2020, 2, 5, 0, 1, 0, 1, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "1 microsecond before mid repayment day event",
                "effective_date": datetime(2020, 8, 5, 0, 0, 0, 999999, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 7, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 8, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "some days before last repayment day",
                "effective_date": datetime(2021, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2021, 1, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2021, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "repayment day changed from 10 to 5",
                "effective_date": datetime(2020, 6, 11, 12, 1, 1, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 6, 10, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 7, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "repayment day changed from 1 to 5",
                "effective_date": datetime(2020, 6, 1, 12, 1, 1, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 6, 1, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 7, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
        ]
        for test_case in test_cases:
            start_date = (
                test_case["topup_date"]
                if "topup_date" in test_case
                else (datetime(2020, 1, 5, 0, 1, tzinfo=timezone.utc))
            )
            amortisation_method = UnionItemValue(key="declining_principal")
            mock_vault = self.create_mock(
                total_term=12,
                repayment_day=5,
                repayment_hour=0,
                repayment_minute=1,
                repayment_second=0,
                loan_start_date=start_date,
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
                amortisation_method=amortisation_method,
            )
            next_payment_date = self.run_function(
                "_calculate_next_repayment_date",
                mock_vault,
                vault=mock_vault,
                effective_date=test_case["effective_date"],
            )
            self.assertEqual(
                next_payment_date,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_calculate_next_repayment_date_start_date_after_repayment_day(self):
        test_cases = [
            {
                "description": "day before first repayment day",
                "effective_date": datetime(2020, 3, 9, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "over a month before first repayment day",
                "effective_date": datetime(2020, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "topup before first repayment day setting start date in future",
                "effective_date": datetime(2020, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "topup_date": datetime(2020, 2, 9, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 3, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "topup after first repayment day",
                "effective_date": datetime(2020, 3, 11, 10, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 3, 10, 0, 1, 0, tzinfo=timezone.utc),
                "topup_date": datetime(2020, 3, 11, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 5, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "1 microsecond before first repayment day",
                "effective_date": datetime(2020, 3, 9, 23, 59, 59, 999999, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "same day as first repayment day at 00:00",
                "effective_date": datetime(2020, 3, 10, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "same datetime as first repayment day",
                "effective_date": datetime(2020, 3, 10, 0, 1, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 4, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "1 microsecond after first repayment day event",
                "effective_date": datetime(2020, 3, 10, 0, 1, 0, 1, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 3, 10, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 4, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "1 microsecond before mid repayment day event",
                "effective_date": datetime(2020, 8, 10, 0, 0, 0, 999999, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 7, 10, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 8, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "some days before last repayment day",
                "effective_date": datetime(2021, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2021, 1, 10, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2021, 2, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "repayment day changed from 15 to 10",
                "effective_date": datetime(2020, 6, 16, 12, 1, 1, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 6, 15, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 7, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "repayment day changed from 1 to 10",
                "effective_date": datetime(2020, 6, 2, 12, 1, 1, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 6, 1, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 7, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "repayment day changed from 9 to 10,"
                "repayment day occured this month",
                "effective_date": datetime(2020, 3, 12, 12, 1, 1, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 3, 9, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 4, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "repayment day changed from 12 to 15,"
                "before current months repayment day",
                "effective_date": datetime(2020, 3, 9, 12, 1, 1, tzinfo=timezone.utc),
                "repayment_day": Decimal("15"),
                "last_execution_time": datetime(2020, 2, 12, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 3, 15, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "repayment day changed from 12 to 11, before repayment date",
                "effective_date": datetime(2020, 3, 9, 12, 1, 1, tzinfo=timezone.utc),
                "repayment_day": Decimal("11"),
                "last_execution_time": datetime(2020, 2, 12, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 3, 11, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "repayment day changed from 12 to 2, before repayment date"
                "after 2nd has passed",
                "effective_date": datetime(2020, 3, 9, 12, 1, 1, tzinfo=timezone.utc),
                "repayment_day": Decimal("2"),
                "last_execution_time": datetime(2020, 2, 12, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 3, 12, 0, 1, 0, tzinfo=timezone.utc),
            },
        ]
        for test_case in test_cases:
            start_date = (
                test_case["topup_date"]
                if "topup_date" in test_case
                else (datetime(2020, 1, 19, tzinfo=timezone.utc))
            )
            repayment_day = test_case["repayment_day"] if "repayment_day" in test_case else 10
            amortisation_method = UnionItemValue(key="declining_principal")

            mock_vault = self.create_mock(
                total_term=12,
                repayment_day=repayment_day,
                loan_start_date=start_date,
                repayment_hour=0,
                repayment_minute=1,
                repayment_second=0,
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
                amortisation_method=amortisation_method,
            )
            next_payment_date = self.run_function(
                "_calculate_next_repayment_date",
                mock_vault,
                vault=mock_vault,
                effective_date=test_case["effective_date"],
            )
            self.assertEqual(
                next_payment_date,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_calculate_next_repayment_date_balloon_loan(self):
        test_cases = [
            {
                "description": "no repayment loan, loan start",
                "amortisation_method": "no_repayment",
                "loan_start_date": datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "total_term": 24,
                "effective_date": datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            },
            {
                "description": "no repayment loan, mid loan",
                "amortisation_method": "no_repayment",
                "loan_start_date": datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "total_term": 24,
                "effective_date": datetime(2021, 10, 11, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            },
            {
                "description": "interest only loan, loan start",
                "amortisation_method": "interest_only",
                "balloon_payment_days_delta": "10",
                "loan_start_date": datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "total_term": 24,
                "effective_date": datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 2, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "interest only loan, mid loan",
                "amortisation_method": "interest_only",
                "balloon_payment_days_delta": "10",
                "loan_start_date": datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "total_term": 24,
                "effective_date": datetime(2021, 10, 11, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2021, 10, 10, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2021, 11, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "interest only loan, balloon payment",
                "amortisation_method": "interest_only",
                "balloon_payment_days_delta": "10",
                "loan_start_date": datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "total_term": 24,
                "effective_date": datetime(2022, 1, 11, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2022, 1, 10, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2022, 1, 20, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "min repayment loan, loan start",
                "amortisation_method": "minimum_repayment_with_balloon_payment",
                "balloon_payment_days_delta": "10",
                "loan_start_date": datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "total_term": 24,
                "effective_date": datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 2, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "minimum repayment loan, mid loan",
                "amortisation_method": "minimum_repayment_with_balloon_payment",
                "balloon_payment_days_delta": "10",
                "loan_start_date": datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "total_term": 24,
                "effective_date": datetime(2021, 10, 11, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2021, 10, 10, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2021, 11, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "minimum repayment loan, balloon payment",
                "amortisation_method": "minimum_repayment_with_balloon_payment",
                "balloon_payment_days_delta": "10",
                "loan_start_date": datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "total_term": 24,
                "effective_date": datetime(2022, 1, 11, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2022, 1, 10, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2022, 1, 20, 0, 1, 0, tzinfo=timezone.utc),
            },
        ]
        for test_case in test_cases:

            mock_vault = self.create_mock(
                total_term=test_case["total_term"],
                repayment_day=10,
                loan_start_date=test_case["loan_start_date"],
                repayment_hour=0,
                repayment_minute=1,
                repayment_second=0,
                REPAYMENT_DAY_SCHEDULE=test_case.get("last_execution_time"),
                balloon_payment_days_delta=OptionalValue(
                    test_case.get("balloon_payment_days_delta")
                ),
                amortisation_method=UnionItemValue(key=test_case["amortisation_method"]),
                repayment_holiday_impact_preference=UnionItemValue(key="increase_emi"),
            )
            next_payment_date = self.run_function(
                "_calculate_next_repayment_date",
                mock_vault,
                vault=mock_vault,
                effective_date=test_case["effective_date"],
            )
            self.assertEqual(
                next_payment_date,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_get_calculated_remaining_term(self):
        test_cases = [
            {
                "description": "before loan has disbursed at start of loan",
                "total_term": 12,
                "variable_interest_rate": Decimal("0.045"),
                "balances": self.account_balances(
                    DEFAULT_DATE,
                    principal=Decimal("0"),
                    overpayment=Decimal("0"),
                    emi_principal_excess=Decimal("0"),
                    principal_capitalised_interest=Decimal("0"),
                    emi=Decimal("554.96"),
                ),
                "expected_result": 12,
            },
            {
                "description": "before first repayment of 1 year loan",
                "total_term": 12,
                "variable_interest_rate": Decimal("0.045"),
                "balances": self.account_balances(
                    DEFAULT_DATE,
                    principal=Decimal("6500"),
                    overpayment=Decimal("0"),
                    emi_principal_excess=Decimal("0"),
                    principal_capitalised_interest=Decimal("0"),
                    emi=Decimal("554.96"),
                ),
                "expected_result": 12,
            },
            {
                "description": "after first repayment of 1 year loan",
                "total_term": 12,
                "variable_interest_rate": Decimal("0.045"),
                "balances": self.account_balances(
                    DEFAULT_DATE,
                    principal=Decimal("5969.88"),
                    overpayment=Decimal("0"),
                    emi_principal_excess=Decimal("0"),
                    principal_capitalised_interest=Decimal("0"),
                    emi=Decimal("554.96"),
                ),
                "expected_result": 11,
            },
            {
                "description": "overpayment of more than emi reduces remaining term",
                "total_term": 12,
                "variable_interest_rate": Decimal("0.045"),
                "balances": self.account_balances(
                    DEFAULT_DATE,
                    principal=Decimal("5969.88"),
                    overpayment=Decimal("-554.97"),
                    emi_principal_excess=Decimal("0"),
                    principal_capitalised_interest=Decimal("0"),
                    emi=Decimal("554.96"),
                ),
                "expected_result": 10,
            },
            {
                "description": "small overpayment of half emi does not reduce remaining term",
                "total_term": 12,
                "variable_interest_rate": Decimal("0.045"),
                "balances": self.account_balances(
                    DEFAULT_DATE,
                    principal=Decimal("5969.88"),
                    overpayment=Decimal("-277.48"),
                    emi_principal_excess=Decimal("0"),
                    principal_capitalised_interest=Decimal("0"),
                    emi=Decimal("554.96"),
                ),
                "expected_result": 11,
            },
            {
                "description": "after 6th repayment of 1 year loan",
                "total_term": 12,
                "variable_interest_rate": Decimal("0.045"),
                "balances": self.account_balances(
                    DEFAULT_DATE,
                    principal=Decimal("3286.16"),
                    overpayment=Decimal("0"),
                    emi_principal_excess=Decimal("0"),
                    principal_capitalised_interest=Decimal("0"),
                    emi=Decimal("554.96"),
                ),
                "expected_result": 6,
            },
            {
                "description": "overpayment after 6th of more than emi reduces remaining term",
                "total_term": 12,
                "variable_interest_rate": Decimal("0.045"),
                "balances": self.account_balances(
                    DEFAULT_DATE,
                    principal=Decimal("3286.16"),
                    overpayment=Decimal("-554.97"),
                    emi_principal_excess=Decimal("0"),
                    principal_capitalised_interest=Decimal("0"),
                    emi=Decimal("554.96"),
                ),
                "expected_result": 5,
            },
            {
                "description": "small overpayment after 6th does not reduce remaining term",
                "total_term": 12,
                "variable_interest_rate": Decimal("0.045"),
                "balances": self.account_balances(
                    DEFAULT_DATE,
                    principal=Decimal("3286.16"),
                    overpayment=Decimal("-277.48"),
                    emi_principal_excess=Decimal("0"),
                    principal_capitalised_interest=Decimal("0"),
                    emi=Decimal("554.96"),
                ),
                "expected_result": 6,
            },
            {
                "description": "after penultimate repayment of 1 year loan",
                "total_term": 12,
                "variable_interest_rate": Decimal("0.045"),
                "balances": self.account_balances(
                    DEFAULT_DATE,
                    principal=Decimal("552.94"),
                    overpayment=Decimal("0"),
                    emi_principal_excess=Decimal("0"),
                    principal_capitalised_interest=Decimal("0"),
                    emi=Decimal("554.96"),
                ),
                "expected_result": 1,
            },
            {
                "description": "10 year loan after first payment due",
                "total_term": 120,
                "variable_interest_rate": Decimal("0.031"),
                "balances": self.account_balances(
                    DEFAULT_DATE,
                    principal=Decimal("297879.17"),
                    overpayment=Decimal("0"),
                    emi_principal_excess=Decimal("0"),
                    principal_capitalised_interest=Decimal("0"),
                    emi=Decimal("2910.69"),
                ),
                "expected_result": 119,
            },
        ]
        for test_case in test_cases:
            effective_date = test_case.get("effective_date", DEFAULT_DATE)
            mock_vault = self.create_mock(
                creation_date=DEFAULT_DATE,
                balance_ts=test_case["balances"],
                denomination=constants.DEFAULT_DENOMINATION,
                total_term=test_case["total_term"],
                variable_interest_rate=test_case["variable_interest_rate"],
                annual_interest_rate_cap=Decimal("0.2033"),
                annual_interest_rate_floor=Decimal("0.01"),
                fixed_interest_loan=UnionItemValue(key="False"),
                accrue_interest_on_due_principal=UnionItemValue(key="False"),
                repayment_day=5,
                fulfillment_precision=2,
                loan_start_date=DEFAULT_DATE,
                variable_rate_adjustment=Decimal(0),
            )
            result = self.run_function(
                "_get_calculated_remaining_term", mock_vault, mock_vault, effective_date
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_remaining_term_in_months(self):
        loan_start_date = datetime(2020, 1, 11, 0, 0, 0, tzinfo=timezone.utc)
        test_cases = [
            {
                "description": "before loan has disbursed at start of loan - declining principal",
                "effective_date": loan_start_date,
                "last_execution_time": None,
                "amortisation_method": UnionItemValue(key="declining_principal"),
                "total_term": 12,
                "variable_interest_rate": Decimal("0.045"),
                "balances": self.account_balances(
                    DEFAULT_DATE,
                    principal=Decimal("0"),
                    overpayment=Decimal("0"),
                    emi_principal_excess=Decimal("0"),
                    principal_capitalised_interest=Decimal("0"),
                    emi=Decimal("554.96"),
                ),
                "expected_result": 12,
            },
            {
                "description": "before first repayment of 1 year loan - declining principal",
                "effective_date": datetime(2020, 2, 19, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "amortisation_method": UnionItemValue(key="declining_principal"),
                "total_term": 12,
                "variable_interest_rate": Decimal("0.045"),
                "balances": self.account_balances(
                    DEFAULT_DATE,
                    principal=Decimal("6500"),
                    overpayment=Decimal("0"),
                    emi_principal_excess=Decimal("0"),
                    principal_capitalised_interest=Decimal("0"),
                    emi=Decimal("554.96"),
                ),
                "expected_result": 12,
            },
            {
                "description": "after first transfer due of 1 year loan,"
                "calculated remaining term rather than expected - declining principal",
                "effective_date": datetime(2020, 2, 20, 10, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 2, 20, 0, 1, 0, tzinfo=timezone.utc),
                "amortisation_method": UnionItemValue(key="declining_principal"),
                "total_term": 12,
                "variable_interest_rate": Decimal("0.045"),
                "balances": self.account_balances(
                    DEFAULT_DATE,
                    principal=Decimal("5969.88"),
                    overpayment=Decimal("0"),
                    emi_principal_excess=Decimal("0"),
                    principal_capitalised_interest=Decimal("0"),
                    emi=Decimal("554.96"),
                ),
                "expected_result": 11,
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock(
                creation_date=DEFAULT_DATE,
                balance_ts=test_case["balances"],
                denomination=constants.DEFAULT_DENOMINATION,
                total_term=test_case["total_term"],
                variable_interest_rate=test_case["variable_interest_rate"],
                annual_interest_rate_cap=Decimal("0.2033"),
                annual_interest_rate_floor=Decimal("0.01"),
                fixed_interest_loan=UnionItemValue(key="False"),
                accrue_interest_on_due_principal=UnionItemValue(key="False"),
                amortisation_method=test_case["amortisation_method"],
                repayment_day=5,
                repayment_hour=0,
                repayment_minute=1,
                repayment_second=0,
                fulfillment_precision=2,
                loan_start_date=loan_start_date,
                variable_rate_adjustment=Decimal(0),
                repayment_holiday_impact_preference=UnionItemValue(key="increase_emi"),
            )
            result = self.run_function(
                "_get_remaining_term_in_months",
                mock_vault,
                mock_vault,
                test_case["effective_date"],
                "total_term",
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_is_declining_principal_amortisation_method(self):
        test_cases = [
            {
                "description": "declining principal",
                "amortisation_method": "dECLining_Principal",
                "expected_result": True,
            },
            {
                "description": "flat interest",
                "amortisation_method": "flat_interest",
                "expected_result": False,
            },
            {
                "description": "rule of 78",
                "amortisation_method": "rule_of_78",
                "expected_result": False,
            },
            {
                "description": "interest only",
                "amortisation_method": "interest_only",
                "expected_result": False,
            },
            {
                "description": "no repayment",
                "amortisation_method": "no_repayment",
                "expected_result": False,
            },
            {
                "description": "minimum repayment with balloon payment",
                "amortisation_method": "minimum_repayment_with_balloon_payment",
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                amortisation_method=UnionItemValue(key=test_case["amortisation_method"]),
            )
            result = self.run_function(
                "_is_declining_principal_amortisation_method",
                mock_vault,
                vault=mock_vault,
            )
            self.assertEqual(
                result,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_is_interest_only_amortisation_method(self):
        test_cases = [
            {
                "description": "interest only",
                "amortisation_method": "interest_only",
                "expected_result": True,
            },
            {
                "description": "flat interest",
                "amortisation_method": "flat_interest",
                "expected_result": False,
            },
            {
                "description": "rule of 78",
                "amortisation_method": "rule_of_78",
                "expected_result": False,
            },
            {
                "description": "declining principle",
                "amortisation_method": "declining_principal",
                "expected_result": False,
            },
            {
                "description": "no repayment",
                "amortisation_method": "no_repayment",
                "expected_result": False,
            },
            {
                "description": "minimum repayment with balloon payment",
                "amortisation_method": "minimum_repayment_with_balloon_payment",
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                amortisation_method=UnionItemValue(key=test_case["amortisation_method"]),
            )
            result = self.run_function(
                "_is_interest_only_amortisation_method",
                mock_vault,
                vault=mock_vault,
            )
            self.assertEqual(
                result,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_is_minimum_repayment_amortisation_method(self):
        test_cases = [
            {
                "description": "minimum repayment with balloon payment",
                "amortisation_method": "minimum_repayment_with_balloon_payment",
                "expected_result": True,
            },
            {
                "description": "interest only",
                "amortisation_method": "interest_only",
                "expected_result": False,
            },
            {
                "description": "flat interest",
                "amortisation_method": "flat_interest",
                "expected_result": False,
            },
            {
                "description": "rule of 78",
                "amortisation_method": "rule_of_78",
                "expected_result": False,
            },
            {
                "description": "declining principle",
                "amortisation_method": "declining_principal",
                "expected_result": False,
            },
            {
                "description": "no repayment",
                "amortisation_method": "no_repayment",
                "expected_result": False,
            },
            {
                "description": "interest only",
                "amortisation_method": "interest_only",
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                amortisation_method=UnionItemValue(key=test_case["amortisation_method"]),
            )
            result = self.run_function(
                "_is_minimum_repayment_amortisation_method",
                mock_vault,
                vault=mock_vault,
            )
            self.assertEqual(
                result,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_flat_interest_amortisation_method(self):
        test_cases = [
            {
                "description": "interest only",
                "amortisation_method": "interest_only",
                "expected_result": False,
            },
            {
                "description": "flat interest",
                "amortisation_method": "flat_interest",
                "expected_result": True,
            },
            {
                "description": "rule of 78",
                "amortisation_method": "rule_of_78",
                "expected_result": True,
            },
            {
                "description": "declining principal",
                "amortisation_method": "declining_principal",
                "expected_result": False,
            },
            {
                "description": "no repayment",
                "amortisation_method": "no_repayment",
                "expected_result": False,
            },
            {
                "description": "minimum repayment with balloon payment",
                "amortisation_method": "minimum_repayment_with_balloon_payment",
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                amortisation_method=UnionItemValue(key=test_case["amortisation_method"]),
            )
            result = self.run_function(
                "_is_flat_interest_amortisation_method",
                mock_vault,
                vault=mock_vault,
            )
            self.assertEqual(
                result,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_is_monthly_rest_interest(self):
        test_cases = [
            {
                "description": "daily rest",
                "interest_accrual_rest_type": "daily",
                "expected_result": False,
            },
            {
                "description": "monthly rest",
                "interest_accrual_rest_type": "monthly",
                "expected_result": True,
            },
            {
                "description": "unknown",
                "interest_accrual_rest_type": "unknown",
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                interest_accrual_rest_type=UnionItemValue(
                    key=test_case["interest_accrual_rest_type"]
                ),
            )
            result = self.run_function(
                "_is_monthly_rest_interest",
                mock_vault,
                vault=mock_vault,
            )
            self.assertEqual(
                result,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_has_schedule_run_today(self):
        test_cases = [
            {
                "description": "schedule run today",
                "schedule_last_run_date": DEFAULT_DATE,
                "expected_result": True,
            },
            {
                "description": "schedule not run today",
                "schedule_last_run_date": DEFAULT_DATE - relativedelta(days=1),
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(TEST_SCHEDULE=test_case["schedule_last_run_date"])

            result = self.run_function(
                "_has_schedule_run_today",
                mock_vault,
                mock_vault,
                DEFAULT_DATE,
                "TEST_SCHEDULE",
            )
            self.assertEqual(
                result,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_get_balance_date_for_interest_accrual(self):
        loan_start_date = datetime(2020, 1, 11, 0, 0, 0, tzinfo=timezone.utc)
        test_cases = [
            {
                "description": "daily rest interest accrual",
                "REPAYMENT_DAY_SCHEDULE": None,
                "rest_type": UnionItemValue(key="daily"),
                "expected_result": None,
            },
            {
                "description": "daily rest interest accrual with previous repayment due schedule",
                "REPAYMENT_DAY_SCHEDULE": datetime(2020, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
                "rest_type": UnionItemValue(key="daily"),
                "expected_result": None,
            },
            {
                "description": "monthly rest interest accrual no previous repayment due schedule",
                "REPAYMENT_DAY_SCHEDULE": None,
                "rest_type": UnionItemValue(key="monthly"),
                "expected_result": datetime(2020, 1, 11, 0, 0, 0, 2, tzinfo=timezone.utc),
            },
            {
                "description": "monthly rest with previous repayment due schedule",
                "REPAYMENT_DAY_SCHEDULE": datetime(2020, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
                "rest_type": UnionItemValue(key="monthly"),
                "expected_result": datetime(2020, 2, 1, 0, 0, 0, 2, tzinfo=timezone.utc),
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                loan_start_date=loan_start_date,
                interest_accrual_rest_type=test_case["rest_type"],
                REPAYMENT_DAY_SCHEDULE=test_case["REPAYMENT_DAY_SCHEDULE"],
            )
            result = self.run_function(
                "_get_balance_date_for_interest_accrual",
                mock_vault,
                vault=mock_vault,
            )
            self.assertEqual(
                result,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_is_rule_of_78_amortisation_method(self):
        loan_start_date = datetime(2020, 1, 11, 0, 0, 0, tzinfo=timezone.utc)
        test_cases = [
            {
                "description": "interest only",
                "amortisation_method": "interest_only",
                "expected_result": False,
            },
            {
                "description": "flat interest",
                "amortisation_method": "flat_interest",
                "expected_result": False,
            },
            {
                "description": "rule of 78",
                "amortisation_method": "rule_of_78",
                "expected_result": True,
            },
            {
                "description": "declining principal",
                "amortisation_method": "declining_principal",
                "expected_result": False,
            },
            {
                "description": "no repayment",
                "amortisation_method": "no_repayment",
                "expected_result": False,
            },
            {
                "description": "minimum repayment with balloon payment",
                "amortisation_method": "minimum_repayment_with_balloon_payment",
                "expected_result": False,
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock(
                amortisation_method=UnionItemValue(key=test_case["amortisation_method"]),
                loan_start_date=loan_start_date,
            )
            result = self.run_function("_is_rule_of_78_amortisation_method", mock_vault, mock_vault)
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_P_with_upfront_fee(self):
        loan_start_date = datetime(2020, 1, 11, 0, 0, 0, tzinfo=timezone.utc)
        test_cases = [
            {
                "description": "£1000 loan, no fee",
                "principal": Decimal("1000"),
                "amortise_upfront_fee": UnionItemValue(key="False"),
                "upfront_fee": Decimal("0"),
                "expected_result": Decimal("1000"),
            },
            {
                "description": "£1000 loan, amortised fee",
                "principal": Decimal("1000"),
                "amortise_upfront_fee": UnionItemValue(key="True"),
                "upfront_fee": Decimal("50"),
                "expected_result": Decimal("1050"),
            },
            {
                "description": "£1000 loan, non amortised fee",
                "principal": Decimal("1000"),
                "amortise_upfront_fee": UnionItemValue(key="False"),
                "upfront_fee": Decimal("50"),
                "fixed_interest_rate": Decimal("0.12789"),
                "expected_result": Decimal("1000"),
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock(
                principal=test_case["principal"],
                upfront_fee=test_case["upfront_fee"],
                amortise_upfront_fee=test_case["amortise_upfront_fee"],
                loan_start_date=loan_start_date,
            )
            result = self.run_function("_get_P_with_upfront_fee", mock_vault, mock_vault)
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_posting_amount(self):
        mock_vault = self.create_mock()
        pending_out_posting = self.outbound_auth(
            denomination=constants.DEFAULT_DENOMINATION,
            amount=Decimal(100),
        )
        committed_posting = self.settle_outbound_auth(
            denomination=constants.DEFAULT_DENOMINATION,
            amount=Decimal(100),
            final=True,
            unsettled_amount=Decimal(100),
        )
        test_cases = [
            {
                "test_posting": pending_out_posting,
                "include_pending_out": True,
                "expected_result": Decimal(100),
            },
            {
                "test_posting": pending_out_posting,
                "include_pending_out": False,
                "expected_result": Decimal(0),
            },
            {
                "test_posting": committed_posting,
                "include_pending_out": True,
                "expected_result": Decimal(0),
            },
            {
                "test_posting": committed_posting,
                "include_pending_out": False,
                "expected_result": Decimal(100),
            },
        ]
        for test_case in test_cases:
            result = self.run_function(
                "_get_posting_amount",
                mock_vault,
                test_case["test_posting"],
                test_case["include_pending_out"],
            )
            self.assertEqual(result, test_case["expected_result"])
