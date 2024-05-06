# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import call
from json import dumps
from typing import List, Tuple

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

CONTRACT_FILE = "library/mortgage/contracts/mortgage.py"
UTILS_MODULE_FILE = "library/common/contract_modules/utils.py"
AMORTISATION_FILE = "library/common/contract_modules/amortisation.py"
DEFAULT_DENOMINATION = "GBP"
VAULT_ACCOUNT_ID = "Main account"
DEFAULT_DATE = datetime(2020, 1, 10, tzinfo=timezone.utc)
DEPOSIT_ACCOUNT = "12345"
INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT = "CAPITALISED_INTEREST_RECEIVED"
INTERNAL_INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT = "PENALTY_INTEREST_RECEIVED"
INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "LATE_REPAYMENT_FEE_INCOME"
INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT = "OVERPAYMENT_ALLOWANCE_FEE_INCOME"

PRINCIPAL = "PRINCIPAL"
PRINCIPAL_DUE = "PRINCIPAL_DUE"
INTEREST_DUE = "INTEREST_DUE"
PRINCIPAL = "PRINCIPAL"
OVER_PAYMENT = "OVER_PAYMENT"
ACCRUED_INTEREST = "ACCRUED_INTEREST"
CAPITALISED_INTEREST = "CAPITALISED_INTEREST"
ACCRUED_EXPECTED_INTEREST = "ACCRUED_EXPECTED_INTEREST"
INTERNAL_CONTRA = "INTERNAL_CONTRA"

DEFAULT_ARREARS_FEE = Decimal("15")
DEFAULT_DUE_AMOUNT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_FLAG = dumps(["ACCOUNT_DELINQUENT"])
DEFAULT_FIXED_INTEREST_RATE = Decimal("0.129971")
DEFAULT_FIXED_INTEREST_TERM = Decimal(0)
DEFAULT_GRACE_PERIOD = Decimal(15)
DEFAULT_INTEREST_ONLY_TERM = Decimal(0)
DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_OVERPAYMENT_FEE_PERCENTAGE = Decimal("0.05")
DEFAULT_OVERPAYMENT_PERCENTAGE = Decimal("0.1")
DEFAULT_PENALTY_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_PENALTY_INCLUDES_BASE_RATE = UnionItemValue(key="True")
DEFAULT_PENALTY_INTEREST_RATE = Decimal("0.129971")
DEFAULT_PRINCIPAL = Decimal(100000)
DEFAULT_REPAYMENT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_REPAYMENT_DAY = Decimal(28)
DEFAULT_REPAYMENT_DAY_ADJUSTMENT = OptionalValue(Decimal(0))
DEFAULT_SCHEDULE_HOUR = Decimal(0)
DEFAULT_SCHEDULE_MINUTE = Decimal(0)
DEFAULT_SCHEDULE_SECOND = Decimal(1)
DEFAULT_TOTAL_TERM = Decimal(1)
DEFAULT_VARIABLE_INTEREST_RATE = Decimal("0.129971")
DEFAULT_VARIABLE_RATE_ADJUSTMENT = Decimal("0.00")


class MortgageTest(ContractTest):

    contract_file = CONTRACT_FILE
    side = Tside.ASSET
    linked_contract_modules = {
        "utils": {
            "path": UTILS_MODULE_FILE,
        },
        "amortisation": {"path": AMORTISATION_FILE},
    }

    def create_mock(
        self,
        balance_ts=None,
        postings=None,
        creation_date=DEFAULT_DATE,
        client_transaction=None,
        flags=None,
        penalty_blocking_flags=DEFAULT_PENALTY_BLOCKING_FLAG,
        delinquency_blocking_flags=DEFAULT_DELINQUENCY_BLOCKING_FLAG,
        late_repayment_fee=DEFAULT_ARREARS_FEE,
        delinquency_flags=DEFAULT_DELINQUENCY_FLAG,
        denomination=DEFAULT_DENOMINATION,
        deposit_account=DEPOSIT_ACCOUNT,
        due_amount_blocking_flags=DEFAULT_DUE_AMOUNT_BLOCKING_FLAG,
        fixed_interest_rate=DEFAULT_FIXED_INTEREST_RATE,
        fixed_interest_term=DEFAULT_FIXED_INTEREST_TERM,
        grace_period=DEFAULT_GRACE_PERIOD,
        interest_only_term=DEFAULT_INTEREST_ONLY_TERM,
        mortgage_start_date=DEFAULT_DATE,
        overdue_amount_blocking_flags=DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG,
        overpayment_fee_percentage=DEFAULT_OVERPAYMENT_FEE_PERCENTAGE,
        overpayment_percentage=DEFAULT_OVERPAYMENT_PERCENTAGE,
        penalty_includes_base_rate=DEFAULT_PENALTY_INCLUDES_BASE_RATE,
        penalty_interest_rate=DEFAULT_PENALTY_INTEREST_RATE,
        principal=DEFAULT_PRINCIPAL,
        repayment_blocking_flags=DEFAULT_REPAYMENT_BLOCKING_FLAG,
        repayment_day=DEFAULT_REPAYMENT_DAY,
        repayment_day_adjustment=DEFAULT_REPAYMENT_DAY_ADJUSTMENT,
        total_term=DEFAULT_TOTAL_TERM,
        variable_interest_rate=DEFAULT_VARIABLE_INTEREST_RATE,
        variable_rate_adjustment=DEFAULT_VARIABLE_RATE_ADJUSTMENT,
        late_repayment_fee_income_account=INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
        interest_received_account=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
        overpayment_allowance_fee_income_account=INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT,
        penalty_interest_received_account=INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT,
        capitalised_interest_received_account=INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
        overpayment_impact_preference=UnionItemValue(key="reduce_term"),
        accrue_interest_hour=DEFAULT_SCHEDULE_HOUR,
        accrue_interest_minute=DEFAULT_SCHEDULE_MINUTE,
        accrue_interest_second=DEFAULT_SCHEDULE_SECOND,
        check_delinquency_hour=DEFAULT_SCHEDULE_HOUR,
        check_delinquency_minute=DEFAULT_SCHEDULE_MINUTE,
        check_delinquency_second=DEFAULT_SCHEDULE_SECOND,
        repayment_hour=DEFAULT_SCHEDULE_HOUR,
        repayment_minute=DEFAULT_SCHEDULE_MINUTE,
        repayment_second=DEFAULT_SCHEDULE_SECOND,
        overpayment_hour=DEFAULT_SCHEDULE_HOUR,
        overpayment_minute=DEFAULT_SCHEDULE_MINUTE,
        overpayment_second=DEFAULT_SCHEDULE_SECOND,
        **kwargs,
    ):
        client_transaction = client_transaction or {}
        balance_ts = balance_ts or []
        postings = postings or []
        flags = flags or []
        params = {
            key: {"value": value}
            for key, value in locals().items()
            if key not in self.locals_to_ignore
        }
        parameter_ts = self.param_map_to_timeseries(params, creation_date)
        return super().create_mock(
            balance_ts=balance_ts,
            parameter_ts=parameter_ts,
            postings=postings,
            creation_date=creation_date,
            client_transaction=client_transaction,
            flags=flags,
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
        in_arrears_accrued=Decimal(0),
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
            balance_dimensions(): Balance(net=default_committed),
            balance_dimensions(address="PRINCIPAL"): Balance(net=principal),
            balance_dimensions(address="ACCRUED_INTEREST"): Balance(net=accrued_interest),
            balance_dimensions(address="PRINCIPAL_DUE"): Balance(net=principal_due),
            balance_dimensions(address="INTEREST_DUE"): Balance(net=interest_due),
            balance_dimensions(address="PENALTIES"): Balance(net=fees),
            balance_dimensions(address="IN_ARREARS_ACCRUED"): Balance(net=in_arrears_accrued),
            balance_dimensions(address="PRINCIPAL_OVERDUE"): Balance(net=principal_overdue),
            balance_dimensions(address="OVERPAYMENT"): Balance(net=overpayment),
            balance_dimensions(address="ACCRUED_EXPECTED_INTEREST"): Balance(
                net=expected_accrued_interest
            ),
            balance_dimensions(address="EMI_PRINCIPAL_EXCESS"): Balance(net=emi_principal_excess),
            balance_dimensions(address="INTEREST_OVERDUE"): Balance(net=interest_overdue),
            balance_dimensions(address="EMI"): Balance(net=emi),
            balance_dimensions(address="CAPITALISED_INTEREST"): Balance(net=capitalised_interest),
            balance_dimensions(address="PRINCIPAL_CAPITALISED_INTEREST"): Balance(
                net=principal_capitalised_interest
            ),
            balance_dimensions(address="nonexistant_address"): Balance(net=nonexistant_address),
        }

        balance_default_dict = BalanceDefaultDict(lambda: Balance(net=0), balance_dict)
        return [(dt, balance_default_dict)]

    def test_post_activation_code(self):

        #  Check post activation code makes principal posting

        mock_vault = self.create_mock(
            principal=Decimal(100000),
            deposit_account="12345",
            denomination=DEFAULT_DENOMINATION,
        )

        postings = [
            {
                "amount": Decimal("100000"),
                "denomination": DEFAULT_DENOMINATION,
                "client_transaction_id": "MOCK_HOOK_PRINCIPAL",
                "from_account_id": "Main account",
                "from_account_address": PRINCIPAL,
                "to_account_id": DEPOSIT_ACCOUNT,
                "to_account_address": DEFAULT_ADDRESS,
                "instruction_details": {
                    "description": "Payment of 100000 of mortgage principal",
                    "event": "PRINCIPAL_PAYMENT",
                },
                "asset": DEFAULT_ASSET,
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in postings]

        self.run_function("post_activate_code", mock_vault)

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=["MOCK_HOOK_PRINCIPAL"], effective_date=DEFAULT_DATE
        )
        self.assertEqual(mock_vault.instruct_posting_batch.call_count, 1)

    def test_execution_schedules(self):

        #  Check execution schedules are correctly defined
        mock_vault = self.create_mock(
            repayment_day=int(28),
            grace_period=int(15),
            check_delinquency_second=int(2),
            repayment_minute=int(1),
            repayment_second=int(0),
            overpayment_second=int(0),
        )
        accrue_interest_schedule = {
            "hour": "0",
            "minute": "0",
            "second": "1",
            "start_date": "2020-01-11",
        }
        repayment_day_schedule = {
            "day": "28",
            "hour": "0",
            "minute": "1",
            "second": "0",
            "start_date": "2020-02-10",
        }
        handle_overpayment_allowance_schedule = {
            "day": "10",
            "hour": "0",
            "minute": "0",
            "month": "1",
            "second": "0",
            "start_date": "2020-01-11",
        }
        check_delinquency_schedule = {
            "hour": "0",
            "minute": "0",
            "second": "2",
            "end_date": "2020-01-11",
            "start_date": "2020-01-11",
        }
        expected_schedule = [
            ("ACCRUE_INTEREST", accrue_interest_schedule),
            ("REPAYMENT_DAY_SCHEDULE", repayment_day_schedule),
            ("HANDLE_OVERPAYMENT_ALLOWANCE", handle_overpayment_allowance_schedule),
            ("CHECK_DELINQUENCY", check_delinquency_schedule),
        ]

        execution_schedule = self.run_function("execution_schedules", mock_vault)

        self.assertEqual(execution_schedule, expected_schedule)

    def test_is_within_term(self):
        mock_vault = self.create_mock(interest_only_term=12, repayment_day=20)
        effective_date = datetime(2020, 12, 20, 23, 59, 59, tzinfo=timezone.utc)
        result = self.run_function(
            "_is_within_term",
            mock_vault,
            mock_vault,
            effective_date,
            "interest_only_term",
        )
        self.assertTrue(result)

    def test_is_outside_of_term(self):
        mock_vault = self.create_mock(repayment_day=20, total_term=12)
        effective_date = datetime(2021, 2, 20, 0, 0, 3, tzinfo=timezone.utc)
        result = self.run_function(
            "_is_within_term", mock_vault, mock_vault, effective_date, "total_term"
        )
        self.assertFalse(result)

    def test_is_within_interest_only_term(self):
        mock_vault = self.create_mock(interest_only_term=12, repayment_day=20)
        effective_date = datetime(2020, 12, 20, 23, 59, 59, tzinfo=timezone.utc)
        result = self.run_function(
            "_is_within_term",
            mock_vault,
            mock_vault,
            effective_date,
            "interest_only_term",
        )
        self.assertTrue(result)

    def test_is_outside_of_interest_only_term(self):
        mock_vault = self.create_mock(repayment_day=20, total_term=12)
        effective_date = datetime(2021, 2, 20, 0, 0, 3, tzinfo=timezone.utc)
        result = self.run_function(
            "_is_within_term",
            mock_vault,
            mock_vault,
            effective_date,
            "interest_only_term",
        )
        self.assertFalse(result)

    def test_is_last_payment_date(self):
        mock_vault = self.create_mock(
            total_term=12,
            repayment_day=5,
            mortgage_start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        effective_date = datetime(2021, 1, 5, 0, 0, 0, tzinfo=timezone.utc)
        result = self.run_function("_is_last_payment_date", mock_vault, mock_vault, effective_date)
        self.assertTrue(result)

    def test_effective_date_is_not_last_payment_date(self):
        mock_vault = self.create_mock(total_term=12, repayment_day=5)
        effective_date = datetime(2020, 12, 5, 0, 0, 0, tzinfo=timezone.utc)
        result = self.run_function("_is_last_payment_date", mock_vault, mock_vault, effective_date)
        self.assertFalse(result)

    def test_get_expected_term_repayment_day_before_start_date(self):
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
                mortgage_start_date=datetime(2020, 1, 10, tzinfo=timezone.utc),
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
                mortgage_start_date=datetime(2020, 1, 20, tzinfo=timezone.utc),
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
                "last_execution_time": datetime(2021, 12, 1, 0, 1, 0, tzinfo=timezone.utc),
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
                mortgage_start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
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

    def test_get_expected_interest_only_term_repayment_day_before_start_date(self):
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
                interest_only_term=12,
                repayment_day=5,
                mortgage_start_date=datetime(2020, 1, 10, tzinfo=timezone.utc),
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
            )
            result = self.run_function(
                "_get_expected_remaining_term",
                mock_vault,
                mock_vault,
                test_case["effective_date"],
                "interest_only_term",
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_expected_remaining_interest_only_term_repayment_day_after_start_date(
        self,
    ):
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
                interest_only_term=12,
                repayment_day=28,
                mortgage_start_date=datetime(2020, 1, 20, tzinfo=timezone.utc),
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
            )
            result = self.run_function(
                "_get_expected_remaining_term",
                mock_vault,
                mock_vault,
                test_case["effective_date"],
                "interest_only_term",
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_expected_remaining_interest_only_term_repayment_day_on_start_date(
        self,
    ):
        test_cases = [
            {
                "description": "day before first repayment day",
                "effective_date": datetime(2020, 1, 29, 0, 0, 0, tzinfo=timezone.utc),
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
                interest_only_term=12,
                repayment_day=1,
                mortgage_start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
            )
            result = self.run_function(
                "_get_expected_remaining_term",
                mock_vault,
                mock_vault,
                test_case["effective_date"],
                "interest_only_term",
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_fixed_interest_rate(self):
        mock_vault = self.create_mock(
            fixed_interest_term=12,
            fixed_interest_rate=Decimal("0.0122"),
            variable_interest_rate=Decimal("0.4333"),
            variable_rate_adjustment=Decimal("1.23"),
            repayment_day=5,
        )
        effective_date = datetime(2021, 1, 5, 0, 0, 0, tzinfo=timezone.utc)
        result = self.run_function("_get_interest_rate", mock_vault, mock_vault, effective_date)
        self.assertEqual(result["interest_rate"], Decimal("0.0122"))
        self.assertEqual(result["interest_rate_type"], "fixed_interest_rate")

    def test_get_variable_interest_rate(self):
        mock_vault = self.create_mock(
            fixed_interest_term=12,
            fixed_interest_rate=Decimal("0.0122"),
            variable_interest_rate=Decimal("0.4333"),
            variable_rate_adjustment=Decimal("0.00"),
            repayment_day=5,
        )
        effective_date = datetime(2021, 3, 5, 0, 0, 0, tzinfo=timezone.utc)
        result = self.run_function("_get_interest_rate", mock_vault, mock_vault, effective_date)
        self.assertEqual(result["interest_rate"], Decimal("0.4333"))
        self.assertEqual(result["interest_rate_type"], "variable_interest_rate")

    def test_get_variable_interest_rate_with_adjustment(self):
        mock_vault = self.create_mock(
            fixed_interest_term=12,
            fixed_interest_rate=Decimal("0.0122"),
            variable_interest_rate=Decimal("0.4333"),
            variable_rate_adjustment=Decimal("-0.23"),
            repayment_day=5,
        )
        effective_date = datetime(2021, 3, 5, 0, 0, 0, tzinfo=timezone.utc)
        result = self.run_function("_get_interest_rate", mock_vault, mock_vault, effective_date)
        self.assertEqual(result["interest_rate"], Decimal("0.2033"))
        self.assertEqual(result["interest_rate_type"], "variable_interest_rate")

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
            denomination=DEFAULT_DENOMINATION,
            total_term=120,
            interest_only_term=0,
            fulfillment_precision=2,
            accrual_precision=5,
            variable_rate_adjustment=parameter_ts[variable_rate_adjustment],
            variable_interest_rate=parameter_ts[variable_interest_rate],
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            mock_vault,
            effective_date,
            annual_interest_rate,
        )
        self.assertEqual(result["emi"], Decimal("2910.69"))
        self.assertEqual(result["interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_expected_interest"], Decimal("123.45"))
        self.assertEqual(result["principal"], Decimal("2787.24"))
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
            denomination=DEFAULT_DENOMINATION,
            total_term=120,
            fixed_interest_term=0,
            interest_only_term=0,
            fulfillment_precision=2,
            accrual_precision=5,
            REPAYMENT_DAY_SCHEDULE=effective_date + relativedelta(hours=-1),
            variable_rate_adjustment=parameter_ts[variable_rate_adjustment],
            variable_interest_rate=parameter_ts[variable_interest_rate],
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            mock_vault,
            effective_date,
            annual_interest_rate,
        )
        self.assertEqual(result["emi"], Decimal("2910.69"))
        self.assertEqual(result["interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_expected_interest"], Decimal("123.45"))
        self.assertEqual(result["principal"], Decimal("2787.24"))
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
            denomination=DEFAULT_DENOMINATION,
            total_term=120,
            interest_only_term=0,
            fulfillment_precision=2,
            accrual_precision=5,
            variable_rate_adjustment=parameter_ts[variable_rate_adjustment],
            variable_interest_rate=parameter_ts[variable_interest_rate],
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            mock_vault,
            effective_date,
            annual_interest_rate,
        )
        self.assertEqual(result["emi"], Decimal("2910.69"))
        self.assertEqual(result["interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_expected_interest"], Decimal("123.45"))
        self.assertEqual(result["principal"], Decimal("2787.24"))
        self.assertEqual(result["principal_excess"], Decimal("0"))

    def test_calculate_monthly_payment_interest_and_principal_with_emi_no_recalc(self):
        annual_interest_rate = {
            "interest_rate": Decimal("0.031"),
            "interest_rate_type": "fixed_interest_rate",
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
            variable_rate_adjustment: [(effective_date + relativedelta(days=-2), Decimal("0.01"))],
            variable_interest_rate: [(effective_date + relativedelta(days=-3), Decimal("0.12"))],
        }
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            repayment_day=28,
            principal=300000,
            denomination=DEFAULT_DENOMINATION,
            total_term=120,
            fixed_interest_term=0,
            interest_only_term=0,
            fulfillment_precision=2,
            accrual_precision=5,
            REPAYMENT_DAY_SCHEDULE=effective_date + relativedelta(days=-1),
            variable_rate_adjustment=parameter_ts[variable_rate_adjustment],
            variable_interest_rate=parameter_ts[variable_interest_rate],
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            mock_vault,
            effective_date,
            annual_interest_rate,
        )
        self.assertEqual(result["emi"], Decimal("1000.00"))
        self.assertEqual(result["interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_expected_interest"], Decimal("123.45"))
        self.assertEqual(result["principal"], Decimal("876.55"))
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
            mortgage_start_date=DEFAULT_DATE,
            repayment_day=28,
            principal=300000,
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            total_term=120,
            interest_only_term=0,
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
        self.assertEqual(result["interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_expected_interest"], Decimal("153.45"))
        self.assertEqual(result["principal"], Decimal("2715.74"))
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
            mortgage_start_date=DEFAULT_DATE,
            repayment_day=28,
            principal=300000,
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            total_term=120,
            interest_only_term=0,
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
        self.assertEqual(result["interest"], Decimal("253.45"))
        self.assertEqual(result["accrued_expected_interest"], Decimal("253.45"))
        self.assertEqual(result["principal"], Decimal("2810.69"))

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
            mortgage_start_date=DEFAULT_DATE,
            repayment_day=28,
            principal=300000,
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            total_term=120,
            interest_only_term=0,
            fulfillment_precision=2,
            accrual_precision=5,
        )
        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            mock_vault,
            effective_date,
            annual_interest_rate,
        )
        self.assertEqual(result["interest"], Decimal("1.23"))
        self.assertEqual(result["principal"], Decimal("2903.86"))

    def test_calculate_monthly_payment_interest_and_principal_no_emi_end_of_fixed_interest(
        self,
    ):
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
        )
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 12, 0, 0, 0, tzinfo=timezone.utc),
            balance_ts=balance_ts,
            repayment_day=28,
            principal=300000,
            denomination=DEFAULT_DENOMINATION,
            total_term=120,
            fixed_interest_term=1,
            interest_only_term=0,
            fulfillment_precision=2,
            accrual_precision=5,
            mortgage_start_date=datetime(2020, 1, 12, 0, 0, 0, tzinfo=timezone.utc),
            REPAYMENT_DAY_SCHEDULE=effective_date + relativedelta(months=-1),
        )

        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            mock_vault,
            effective_date,
            annual_interest_rate,
        )

        self.assertEqual(result["emi"], Decimal("2931.56"))
        self.assertEqual(result["interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_expected_interest"], Decimal("123.45"))
        self.assertEqual(result["principal"], Decimal("2808.11"))
        self.assertEqual(result["principal_excess"], Decimal("0"))

    def test_calculate_monthly_payment_interest_and_principal_with_emi_end_of_fixed_interest(
        self,
    ):
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
            denomination=DEFAULT_DENOMINATION,
            total_term=120,
            fixed_interest_term=1,
            interest_only_term=0,
            fulfillment_precision=2,
            accrual_precision=5,
            mortgage_start_date=datetime(2020, 1, 12, 0, 0, 0, tzinfo=timezone.utc),
            REPAYMENT_DAY_SCHEDULE=effective_date + relativedelta(months=-1),
        )

        result = self.run_function(
            "_calculate_monthly_payment_interest_and_principal",
            mock_vault,
            mock_vault,
            effective_date,
            annual_interest_rate,
        )

        self.assertEqual(result["emi"], Decimal("2931.56"))
        self.assertEqual(result["interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_interest"], Decimal("123.45"))
        self.assertEqual(result["accrued_expected_interest"], Decimal("123.45"))
        self.assertEqual(result["principal"], Decimal("2808.11"))
        self.assertEqual(result["principal_excess"], Decimal("0"))

    def test_has_new_overpayment(self):
        repayment_date = datetime(2020, 2, 28, 0, 0, 3, tzinfo=timezone.utc)
        mortgage_start_date = datetime(2020, 1, 15, 0, 0, 3, tzinfo=timezone.utc)

        test_cases = [
            {
                "description": "has overpayment since last execution",
                "last_event_execution_date": datetime(2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc),
                "overpayment": Decimal("-100"),
                "expected_result": True,
            },
            {
                "description": "has overpayment before last execution",
                "last_event_execution_date": datetime(2020, 3, 20, 0, 0, 3, tzinfo=timezone.utc),
                "overpayment": Decimal("-100"),
                "expected_result": False,
            },
            {
                "description": "has overpayment since account creation",
                "last_event_execution_date": None,
                "overpayment": Decimal("-100"),
                "expected_result": True,
            },
            {
                "description": "no overpayment since account creation",
                "last_event_execution_date": None,
                "overpayment": Decimal("0"),
                "expected_result": False,
            },
            {
                "description": "no overpayment since last execution",
                "last_event_execution_date": datetime(2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc),
                "overpayment": Decimal("0"),
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            balance_ts = self.account_balances(
                mortgage_start_date,
                principal=Decimal("10000"),
                overpayment=Decimal("0"),
            )

            if test_case["last_event_execution_date"]:
                balance_ts.extend(
                    self.account_balances(
                        test_case["last_event_execution_date"],
                        principal=Decimal("9000"),
                        overpayment=Decimal("0"),
                    )
                )

            balance_ts.extend(
                self.account_balances(
                    repayment_date,
                    principal=Decimal("9000"),
                    overpayment=test_case["overpayment"],
                )
            )

            mock_vault = self.create_mock(
                balance_ts=balance_ts,
                mortgage_start_date=mortgage_start_date,
                REPAYMENT_DAY_SCHEDULE=test_case["last_event_execution_date"],
            )
            result = self.run_function("_has_new_overpayment", mock_vault, vault=mock_vault)

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

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
            denomination=DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(12),
            fulfillment_precision=2,
        )

        incoming_posting = self.outbound_hard_settlement(
            amount="1000",
            denomination=DEFAULT_DENOMINATION,
        )
        incoming_postings = self.mock_posting_instruction_batch(
            posting_instructions=[incoming_posting]
        )

        postings = [
            {
                "amount": Decimal("150.00"),
                "asset": "COMMERCIAL_BANK_MONEY",
                "client_transaction_id": "REPAY_PRINCIPAL_OVERDUE_testctid",
                "denomination": "GBP",
                "from_account_address": "DEFAULT",
                "from_account_id": "Main account",
                "instruction_details": {
                    "description": (
                        "Paying off 150.00 from PRINCIPAL_OVERDUE, "
                        "which was at 150.00 - 2020-02-10 00:00:00+00:00"
                    ),
                    "event": "REPAYMENT",
                },
                "override_all_restrictions": True,
                "to_account_address": "PRINCIPAL_OVERDUE",
                "to_account_id": "Main account",
            },
            {
                "amount": Decimal("50.00"),
                "asset": "COMMERCIAL_BANK_MONEY",
                "client_transaction_id": "REPAY_INTEREST_OVERDUE_testctid",
                "denomination": "GBP",
                "from_account_address": "DEFAULT",
                "from_account_id": "Main account",
                "instruction_details": {
                    "description": (
                        "Paying off 50.00 from INTEREST_OVERDUE, "
                        "which was at 50.00 - 2020-02-10 00:00:00+00:00"
                    ),
                    "event": "REPAYMENT",
                },
                "override_all_restrictions": True,
                "to_account_address": "INTEREST_OVERDUE",
                "to_account_id": "Main account",
            },
            {
                "amount": Decimal("100.00"),
                "asset": "COMMERCIAL_BANK_MONEY",
                "client_transaction_id": "REPAY_PRINCIPAL_DUE_testctid",
                "denomination": "GBP",
                "from_account_address": "DEFAULT",
                "from_account_id": "Main account",
                "instruction_details": {
                    "description": (
                        "Paying off 100.00 from PRINCIPAL_DUE, "
                        "which was at 100.00 - 2020-02-10 00:00:00+00:00"
                    ),
                    "event": "REPAYMENT",
                },
                "override_all_restrictions": True,
                "to_account_address": "PRINCIPAL_DUE",
                "to_account_id": "Main account",
            },
            {
                "amount": Decimal("35.00"),
                "asset": "COMMERCIAL_BANK_MONEY",
                "client_transaction_id": "REPAY_INTEREST_DUE_testctid",
                "denomination": "GBP",
                "from_account_address": "DEFAULT",
                "from_account_id": "Main account",
                "instruction_details": {
                    "description": (
                        "Paying off 35.00 from INTEREST_DUE, "
                        "which was at 35.00 - 2020-02-10 00:00:00+00:00"
                    ),
                    "event": "REPAYMENT",
                },
                "override_all_restrictions": True,
                "to_account_address": "INTEREST_DUE",
                "to_account_id": "Main account",
            },
            {
                "amount": Decimal("665.00"),
                "asset": "COMMERCIAL_BANK_MONEY",
                "client_transaction_id": "OVERPAYMENT_BALANCE_testctid",
                "denomination": "GBP",
                "from_account_address": "DEFAULT",
                "from_account_id": "Main account",
                "instruction_details": {
                    "description": (
                        "Upon repayment, 665.00 of the repayment "
                        "has been transfered to the OVERPAYMENT balance."
                    ),
                    "event": "OVERPAYMENT_BALANCE_INCREASE",
                },
                "override_all_restrictions": True,
                "to_account_address": "OVERPAYMENT",
                "to_account_id": "Main account",
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in postings]

        self.run_function(
            "_process_payment",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
            repayment_amount_remaining=1000,
            client_transaction_id="testctid",
            postings=incoming_postings,
            denomination="GBP",
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=[
                "REPAY_PRINCIPAL_OVERDUE_testctid",
                "REPAY_INTEREST_OVERDUE_testctid",
                "REPAY_PRINCIPAL_DUE_testctid",
                "REPAY_INTEREST_DUE_testctid",
                "OVERPAYMENT_BALANCE_testctid",
            ],
            effective_date=effective_date,
        )
        self.assertEqual(mock_vault.instruct_posting_batch.call_count, 1)

    def test_handle_repayment_due(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("1000"),
            interest_due=Decimal("350.00"),
            principal=Decimal("100000"),
        )

        effective_date = DEFAULT_DATE + relativedelta(months=1)

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            mortgage_start_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            repayment_day=int(10),
            denomination=DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(12),
            late_repayment_fee=Decimal(12),
            late_repayment_fee_income_account=INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
            grace_period=5,
            fulfillment_precision=2,
        )

        self.run_function(
            "_handle_repayment_due",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
        )

        postings = [
            {
                "amount": Decimal("1000"),
                "asset": "COMMERCIAL_BANK_MONEY",
                "client_transaction_id": "MOCK_HOOK_PRINCIPAL_OVERDUE",
                "denomination": "GBP",
                "from_account_address": "PRINCIPAL_OVERDUE",
                "from_account_id": "Main account",
                "instruction_details": {
                    "description": ("Mark oustanding due amount of 1000 as PRINCIPAL_OVERDUE."),
                    "event": "MOVE_BALANCE_INTO_PRINCIPAL_OVERDUE",
                },
                "to_account_address": "PRINCIPAL_DUE",
                "to_account_id": "Main account",
            },
            {
                "amount": Decimal("350.00"),
                "asset": "COMMERCIAL_BANK_MONEY",
                "client_transaction_id": "MOCK_HOOK_INTEREST_OVERDUE",
                "denomination": "GBP",
                "from_account_address": "INTEREST_OVERDUE",
                "from_account_id": "Main account",
                "instruction_details": {
                    "description": ("Mark oustanding due amount of 350.00 as INTEREST_OVERDUE."),
                    "event": "MOVE_BALANCE_INTO_INTEREST_OVERDUE",
                },
                "to_account_address": "INTEREST_DUE",
                "to_account_id": "Main account",
            },
            {
                "amount": Decimal("12"),
                "asset": "COMMERCIAL_BANK_MONEY",
                "client_transaction_id": "MOCK_HOOK_CHARGE_FEE",
                "denomination": "GBP",
                "from_account_address": "PENALTIES",
                "from_account_id": "Main account",
                "instruction_details": {
                    "description": ("Incur late repayment fees of 12"),
                    "event": "INCUR_PENALTY_FEES",
                },
                "to_account_address": "DEFAULT",
                "to_account_id": INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in postings]

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

    def test_handle_end_blocking_flags(self):
        balance_ts = self.account_balances(DEFAULT_DATE, capitalised_interest=Decimal("1000"))

        effective_date = DEFAULT_DATE + relativedelta(months=1)

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            mortgage_start_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            repayment_day=int(10),
            denomination=DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(12),
            late_repayment_fee=Decimal(12),
            late_repayment_fee_income_account=INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
            grace_period=5,
            fulfillment_precision=2,
            flags=["NOT_REPAYMENT_HOLIDAY"],
        )

        self.run_function(
            "_handle_end_blocking_flags",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
        )

        postings = [
            {
                "amount": Decimal("1000"),
                "asset": "COMMERCIAL_BANK_MONEY",
                "client_transaction_id": "MOCK_HOOK_TRANSFER_ACCRUED_CAPITALISED_INTEREST_CUSTOMER",
                "denomination": "GBP",
                "from_account_address": "PRINCIPAL_CAPITALISED_INTEREST",
                "from_account_id": "Main account",
                "instruction_details": {
                    "description": ("Capitalise interest accrued after due amount blocking"),
                    "event": "TRANSFER_CAPITALISED_INTEREST_TO_PRINCIPAL_CAPITALISED_INTEREST",
                },
                "to_account_address": "CAPITALISED_INTEREST",
                "to_account_id": "Main account",
            }
        ]

        expected_postings = [call(**kwargs) for kwargs in postings]

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

    def test_handle_end_blocking_flags_no_capitalised_interest(self):
        balance_ts = self.account_balances(DEFAULT_DATE, capitalised_interest=Decimal("0"))

        effective_date = DEFAULT_DATE + relativedelta(months=1)

        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            mortgage_start_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            repayment_day=int(10),
            denomination=DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            principal=Decimal("100000"),
            total_term=int(12),
            late_repayment_fee=Decimal(12),
            late_repayment_fee_income_account=INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
            grace_period=5,
            fulfillment_precision=2,
            flags=["NOT_REPAYMENT_HOLIDAY"],
        )

        self.run_function(
            "_handle_end_blocking_flags",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls([])

    def test_get_penalty_daily_rate_with_base(self):
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            mortgage_start_date=DEFAULT_DATE,
            fixed_interest_term=12,
            fixed_interest_rate=Decimal("0.012234"),
            variable_interest_rate=Decimal("0.2333"),
            penalty_interest_rate=Decimal("0.48"),
            penalty_includes_base_rate=UnionItemValue("True"),
            variable_rate_adjustment=Decimal("0.00"),
            repayment_day=5,
        )
        effective_date = datetime(2020, 8, 5, 0, 0, 0, tzinfo=timezone.utc)
        result = self.run_function(
            "_get_penalty_daily_rate", mock_vault, mock_vault, effective_date
        )
        expected = (Decimal("0.492234") / 365).quantize(Decimal(".0000000001"))
        self.assertEqual(result, expected)

    def test_get_penalty_daily_rate_without_base(self):
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            mortgage_start_date=DEFAULT_DATE,
            fixed_interest_term=12,
            fixed_interest_rate=Decimal("0.0122"),
            variable_interest_rate=Decimal("0.2333"),
            penalty_interest_rate=Decimal("0.483212"),
            penalty_includes_base_rate=UnionItemValue("False"),
            variable_rate_adjustment=Decimal("0.00"),
            repayment_day=5,
        )
        effective_date = datetime(2021, 3, 5, 0, 0, 0, tzinfo=timezone.utc)
        result = self.run_function(
            "_get_penalty_daily_rate", mock_vault, mock_vault, effective_date
        )
        expected = (Decimal("0.483212") / 365).quantize(Decimal(".0000000001"))
        self.assertEqual(result, expected)

    def test_calculate_daily_penalty(self):
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
            mortgage_start_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            denomination="GBP",
            fixed_interest_term=12,
            fixed_interest_rate=Decimal("0.0122"),
            variable_interest_rate=Decimal("0.2333"),
            penalty_interest_rate=Decimal("0.483212"),
            penalty_includes_base_rate=UnionItemValue("False"),
            repayment_day=5,
            fulfillment_precision=2,
            accrual_precision=5,
        )
        effective_date = datetime(2020, 3, 5, 0, 0, 0, tzinfo=timezone.utc)
        result = self.run_function(
            "_calculate_daily_penalty", mock_vault, mock_vault, effective_date
        )
        expected = Decimal("145.33") * (Decimal("0.483212") / 365).quantize(Decimal(".000001"))
        self.assertEqual(result["amount_accrued"], expected.quantize(Decimal(".01")))

    def test_calculate_daily_penalty_round_to_zero(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            overpayment=Decimal("-150"),
            fees=Decimal("325"),
            principal_overdue=Decimal("2"),
            interest_overdue=Decimal("0"),
            nonexistant_address=Decimal("2"),
        )
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            mortgage_start_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            denomination="GBP",
            fixed_interest_term=12,
            fixed_interest_rate=Decimal("0.0122"),
            variable_interest_rate=Decimal("0.2333"),
            penalty_interest_rate=Decimal("0.483212"),
            penalty_includes_base_rate=UnionItemValue("False"),
            repayment_day=5,
            fulfillment_precision=2,
            accrual_precision=5,
        )
        effective_date = datetime(2020, 3, 5, 0, 0, 0, tzinfo=timezone.utc)
        result = self.run_function(
            "_calculate_daily_penalty", mock_vault, mock_vault, effective_date
        )
        self.assertEqual(result["amount_accrued"], 0)

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
            denomination=DEFAULT_DENOMINATION,
            fulfillment_precision=2,
            accrual_precision=5,
        )

        outstanding_debt = self.run_function("_sum_outstanding_dues", mock_vault, mock_vault)

        self.assertEqual(outstanding_debt, Decimal("660.00"))

    def test_get_expected_principal(self):

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            principal_capitalised_interest=Decimal("6950"),
            overpayment=Decimal("-150"),
            emi_principal_excess=Decimal("222.12"),
            fees=Decimal("325"),
            nonexistant_address=Decimal("2"),
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            fulfillment_precision=2,
        )

        outstanding_debt = self.run_function("_get_expected_principal", mock_vault, mock_vault)

        self.assertEqual(outstanding_debt, Decimal("106950"))

    def test_get_expected_principal_no_capitalised_interest(self):

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
            denomination=DEFAULT_DENOMINATION,
            fulfillment_precision=2,
        )

        outstanding_debt = self.run_function("_get_expected_principal", mock_vault, mock_vault)

        self.assertEqual(outstanding_debt, Decimal("100000"))

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
            denomination=DEFAULT_DENOMINATION,
            fulfillment_precision=2,
        )

        outstanding_debt = self.run_function(
            "_get_outstanding_actual_principal", mock_vault, mock_vault
        )

        self.assertEqual(outstanding_debt, Decimal("100072.12"))

    def test_get_overdue_balance(self):

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
            denomination=DEFAULT_DENOMINATION,
            fulfillment_precision=2,
        )

        result = self.run_function("_get_overdue_balance", mock_vault, mock_vault)

        self.assertEqual(result, Decimal("145.33"))

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
            denomination=DEFAULT_DENOMINATION,
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
            denomination=DEFAULT_DENOMINATION,
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
            "Cannot make transactions in given denomination; " "transactions must be in GBP",
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
            self.outbound_hard_settlement(amount=50, denomination="GBP"),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock(balance_ts=balance_ts, denomination=DEFAULT_DENOMINATION)

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
            self.inbound_hard_settlement(amount="100510.01", denomination="GBP"),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            repayment_day=20,
            interest_only_term=0,
            total_term=120,
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
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(str(e.exception), "Cannot pay more than is owed")
        self.assert_no_side_effects(mock_vault)

    def test_pre_posting_code_accepts_overpayment_for_interest_only(self):
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
            self.inbound_hard_settlement(amount="1000.01", denomination="GBP"),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            interest_only_term=12,
            total_term=20,
            repayment_day=20,
            fulfillment_precision=2,
            accrual_precision=5,
        )

        self.run_function(
            "pre_posting_code",
            mock_vault,
            postings=postings_batch,
            effective_date=DEFAULT_DATE,
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
            self.inbound_hard_settlement(amount="1000.01", denomination="GBP"),
            self.inbound_hard_settlement(amount="200.01", denomination="GBP"),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            interest_only_term=12,
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
            self.inbound_hard_settlement(amount="500", denomination="GBP"),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            interest_only_term=0,
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

    def test_overpayment_allowance_calculated_correctly(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal=Decimal("100000"),
            overpayment=Decimal("-12000"),
        )
        effective_date = DEFAULT_DATE + relativedelta(years=1)
        balance_ts += self.account_balances(
            effective_date,
            principal=Decimal("90000"),
            overpayment=Decimal("-22001"),
        )

        overpayment_allowance_fee_income_account = INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            mortgage_start_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            fixed_interest_rate=Decimal("0.129971"),
            overpayment_percentage=Decimal("0.1"),
            overpayment_fee_percentage=Decimal("0.05"),
            principal=Decimal("100000"),
            total_term=int(24),
            late_repayment_fee=Decimal(12),
            overpayment_allowance_fee_income_account=overpayment_allowance_fee_income_account,
            fulfillment_precision=2,
        )

        self.run_function(
            "_check_if_over_overpayment_allowance_and_charge_fee",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
        )

        mock_vault.make_internal_transfer_instructions.assert_called()

    def test_overpayment_fee_applied_correctly(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal=Decimal("100000"),
            overpayment=Decimal("-12000"),
        )
        effective_date = DEFAULT_DATE + relativedelta(years=1)
        balance_ts += self.account_balances(
            effective_date,
            principal=Decimal("90000"),
            overpayment=Decimal("-22100"),
        )
        overpayment_allowance_fee_income_account = INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT
        mock_vault = self.create_mock(
            creation_date=DEFAULT_DATE,
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            overpayment_percentage=Decimal("0.1"),
            overpayment_fee_percentage=Decimal("0.05"),
            principal=Decimal("100000"),
            total_term=int(24),
            late_repayment_fee=Decimal("12"),
            overpayment_allowance_fee_income_account=overpayment_allowance_fee_income_account,
            fulfillment_precision=2,
        )

        self.run_function(
            "_check_if_over_overpayment_allowance_and_charge_fee",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("5.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address="PENALTIES",
                    to_account_id=overpayment_allowance_fee_income_account,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    client_transaction_id="MOCK_HOOK_OVERPAYMENT_fee",
                    instruction_details={
                        "description": "Overpayment fee of 5.00 resulted from excess of 100.0 "
                        "above allowance of 10000.00.",
                        "event": "CHECK_IF_OVER_OVERPAYMENT_ALLOWANCE",
                    },
                )
            ]
        )

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
            denomination=DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            overpayment_percentage=Decimal("0.1"),
            overpayment_fee_percentage=Decimal("0.05"),
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
            denomination=DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            overpayment_percentage=Decimal("0.1"),
            overpayment_fee_percentage=Decimal("0.05"),
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
                    workflow="MORTGAGE_MARK_DELINQUENT",
                    context={"account_id": "Main account"},
                )
            ]
        )

    def test_handle_end_of_mortgage(self):
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
            denomination=DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            overpayment_percentage=Decimal("0.1"),
            overpayment_fee_percentage=Decimal("0.05"),
            principal=Decimal("100000"),
            total_term=int(24),
            late_repayment_fee=Decimal(12),
            fulfillment_precision=2,
        )

        self.run_function(
            "_handle_end_of_mortgage",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("88000.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address="OVERPAYMENT",
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address="PRINCIPAL",
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_OVERPAYMENT_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring overpayments to PRINCIPAL address",
                        "event": "END_OF_MORTGAGE",
                    },
                ),
                call(
                    amount=Decimal("12000.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address="EMI_PRINCIPAL_EXCESS",
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address="PRINCIPAL",
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_EMI_PRINCIPAL_EXCESS_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring principal excess to PRINCIPAL address",
                        "event": "END_OF_MORTGAGE",
                    },
                ),
            ]
        )

    def test_handle_end_of_mortgage_without_overpayment(self):
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
            denomination=DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            overpayment_percentage=Decimal("0.1"),
            overpayment_fee_percentage=Decimal("0.05"),
            principal=Decimal("100000"),
            total_term=int(24),
            late_repayment_fee=Decimal(12),
            fulfillment_precision=2,
        )

        self.run_function(
            "_handle_end_of_mortgage",
            mock_vault,
            mock_vault,
            effective_date=effective_date,
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
            denomination=DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            overpayment_percentage=Decimal("0.1"),
            overpayment_fee_percentage=Decimal("0.05"),
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
            denomination=DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            overpayment_percentage=Decimal("0.1"),
            overpayment_fee_percentage=Decimal("0.05"),
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
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address="OVERPAYMENT",
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address="PRINCIPAL",
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_OVERPAYMENT_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring overpayments to PRINCIPAL address",
                        "event": "END_OF_MORTGAGE",
                    },
                ),
                call(
                    amount=Decimal("12000.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address="EMI_PRINCIPAL_EXCESS",
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address="PRINCIPAL",
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_EMI_PRINCIPAL_EXCESS_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring principal excess to PRINCIPAL address",
                        "event": "END_OF_MORTGAGE",
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
            denomination=DEFAULT_DENOMINATION,
            interest_rate=Decimal("0.129971"),
            overpayment_percentage=Decimal("0.1"),
            overpayment_fee_percentage=Decimal("0.05"),
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
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address="PRINCIPAL_CAPITALISED_INTEREST",
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address="PRINCIPAL",
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_PRINCIPAL_CAPITALISED_INTEREST_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring PRINCIPAL_CAPITALISED_INTEREST"
                        " to PRINCIPAL address",
                        "event": "END_OF_MORTGAGE",
                    },
                )
            ]
        )

    def test_post_parameter_change_code(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            principal=Decimal("100000"),
            overpayment=Decimal("-8000"),
            emi_principal_excess=Decimal("-4000"),
        )
        effective_date = DEFAULT_DATE

        old_parameter_values = {"mortgage_start_date": "2020-01-10"}

        updated_parameter_values = {"mortgage_start_date": "2020-09-02"}

        mock_vault = self.create_mock(
            mortgage_start_date=datetime.strptime("2020-09-02", "%Y-%m-%d"),
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            fixed_interest_rate=Decimal("0.129971"),
            overpayment_percentage=Decimal("0.1"),
            overpayment_fee_percentage=Decimal("0.05"),
            principal=Decimal("100000"),
            total_term=int(24),
            late_repayment_fee=Decimal(12),
            overpayment_second=int(0),
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
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address="OVERPAYMENT",
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address="PRINCIPAL",
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_OVERPAYMENT_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring overpayments to PRINCIPAL address",
                        "event": "END_OF_MORTGAGE",
                    },
                ),
                call(
                    amount=Decimal("4000.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address="EMI_PRINCIPAL_EXCESS",
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address="PRINCIPAL",
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="TRANSFER_EMI_PRINCIPAL_EXCESS_MOCK_HOOK",
                    instruction_details={
                        "description": "Transferring principal excess to PRINCIPAL address",
                        "event": "END_OF_MORTGAGE",
                    },
                ),
            ]
        )

        mock_vault.amend_schedule.assert_has_calls(
            [
                call(
                    event_type="HANDLE_OVERPAYMENT_ALLOWANCE",
                    new_schedule={
                        "month": "9",
                        "day": "2",
                        "hour": "0",
                        "minute": "0",
                        "second": "0",
                        "start_date": "2020-09-03",
                    },
                )
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

    def test_handle_repayment_day_change_lower_repayment_day(self):
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
                            (repayment_day_schedule + relativedelta(months=2, day=12)).date()
                        ),
                    },
                )
            ]
        )

    def test_handle_handle_repayment_day_change_repayment_day_no_schedule_same_month(
        self,
    ):
        # change takes effect on 12/01 and the payment date is changed from 28 to 20
        # no previous payment
        # initial payment is expected to be on 2020-02-28
        # updated first payment is expected to be on 2020-02-20
        effective_date = datetime(2020, 1, 12, 0, 0, 0, tzinfo=timezone.utc)
        account_creation_date = datetime(2020, 1, 10, 0, 0, 0, tzinfo=timezone.utc)
        expected_new_schedule_date = datetime(2020, 2, 20, 0, 0, 0, tzinfo=timezone.utc)

        mock_vault = self.create_mock(
            mortgage_start_date=account_creation_date,
            repayment_day=20,
            REPAYMENT_DAY_SCHEDULE=None,
            repayment_minute=int(1),
            repayment_second=int(0),
        )
        previous_values = {"repayment_day": 28}
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
                        "start_date": str(expected_new_schedule_date.date()),
                    },
                )
            ]
        )

    def test_handle_handle_repayment_day_change_repayment_day_no_schedule_extra_month(
        self,
    ):
        # change takes effect on 28/01 and the payment date is changed from 20 to 12
        # no previous payment
        # initial payment is expected to be on 2020-02-20
        # updated first payment is expected to be on 2020-03-12
        effective_date = datetime(2020, 1, 28, 0, 0, 0, tzinfo=timezone.utc)
        account_creation_date = datetime(2020, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        expected_new_schedule_date = datetime(2020, 3, 12, 0, 0, 0, tzinfo=timezone.utc)

        mock_vault = self.create_mock(
            mortgage_start_date=account_creation_date,
            repayment_day=12,
            REPAYMENT_DAY_SCHEDULE=None,
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
                        "start_date": str(expected_new_schedule_date.date()),
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

    def test_accrue_interest_no_principal_no_accrual(self):
        balance_ts = self.account_balances(principal=Decimal(0))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            fixed_interest_term=12,
            repayment_day=1,
            mortgage_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrual_precision=5,
            fulfillment_precision=2,
        )

        self.run_function(
            "_accrue_interest",
            mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_accrue_interest_only_principal_accrues_interest(self):
        balance_ts = self.account_balances(principal=Decimal(100))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            fixed_interest_term=12,
            repayment_day=1,
            mortgage_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrued_interest_receivable_account=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrual_precision=5,
            fulfillment_precision=2,
        )

        self.run_function(
            "_accrue_interest",
            mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.00274"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=ACCRUED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=INTERNAL_CONTRA,
                    instruction_details={
                        "description": "Daily interest accrued at 0.002740% on outstanding "
                        "principal of 100.00",
                        "event_type": "ACCRUE_INTEREST",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                ),
                call(
                    amount=Decimal("0.00274"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_INTERNAL",
                    from_account_id=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": "Daily interest accrued at 0.002740% on outstanding "
                        "principal of 100.00",
                        "event_type": "ACCRUE_INTEREST",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                ),
                call(
                    amount=Decimal("0.00274"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_EXPECTED",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=ACCRUED_EXPECTED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=INTERNAL_CONTRA,
                    instruction_details={
                        "description": "Expected daily interest accrued at 0.002740%"
                        " on expected principal of 100.00 and outstanding"
                        " principal of 100.00",
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

    def test_accrue_interest_repayment_holiday_accrues_interest(self):
        balance_ts = self.account_balances(principal=Decimal(1000))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            fixed_interest_term=12,
            repayment_day=1,
            mortgage_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrued_interest_receivable_account=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrual_precision=5,
            fulfillment_precision=2,
            flags=["REPAYMENT_HOLIDAY"],
        )

        self.run_function(
            "_accrue_interest",
            mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.03"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=CAPITALISED_INTEREST,
                    to_account_id=INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": "Daily capitalised interest accrued at 0.002740% on "
                        "outstanding principal of 1000",
                        "event_type": "ACCRUE_CAPITALISED_INTEREST",
                        "daily_interest_rate": "0.0000273973",
                    },
                    asset=DEFAULT_ASSET,
                )
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_MOCK_HOOK",
            posting_instructions=["MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER"],
            effective_date=DEFAULT_DATE,
        )
        self.assertEqual(mock_vault.instruct_posting_batch.call_count, 1)

    def test_accrue_interest_repayment_holiday_accrues_no_interest_principal_0(self):
        balance_ts = self.account_balances(principal=Decimal(0))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            fixed_interest_term=12,
            repayment_day=1,
            mortgage_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrued_interest_receivable_account=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrual_precision=5,
            fulfillment_precision=2,
            flags=["REPAYMENT_HOLIDAY"],
        )

        self.run_function(
            "_accrue_interest",
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
            denomination=DEFAULT_DENOMINATION,
            fixed_interest_term=12,
            repayment_day=1,
            mortgage_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrued_interest_receivable_account=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrual_precision=5,
            fulfillment_precision=2,
        )

        self.run_function(
            "_accrue_interest",
            mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.00247"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=ACCRUED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=INTERNAL_CONTRA,
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
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_INTERNAL",
                    from_account_id=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
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
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_EXPECTED",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=ACCRUED_EXPECTED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=INTERNAL_CONTRA,
                    instruction_details={
                        "description": "Expected daily interest accrued at 0.002740% on expected"
                        " principal of 100.00 and outstanding principal of 90.00",
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
            denomination=DEFAULT_DENOMINATION,
            fixed_interest_term=12,
            repayment_day=1,
            mortgage_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrued_interest_receivable_account=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrual_precision=5,
            fulfillment_precision=2,
        )

        self.run_function(
            "_accrue_interest",
            mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.00247"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=ACCRUED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=INTERNAL_CONTRA,
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
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_INTERNAL",
                    from_account_id=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
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
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_EXPECTED",
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=ACCRUED_EXPECTED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=INTERNAL_CONTRA,
                    instruction_details={
                        "description": "Expected daily interest accrued at 0.002740% on "
                        "expected principal of 100.00 and outstanding principal of 90.00",
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
            in_arrears_accrued=Decimal(40),
            default_committed=Decimal(50),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            fixed_interest_term=12,
            repayment_day=1,
            mortgage_start_date=DEFAULT_DATE,
            fixed_interest_rate=Decimal("0.01"),
            accrued_interest_receivable_account=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            fulfillment_precision=2,
            accrual_precision=5,
        )

        self.run_function(
            "_accrue_interest",
            mock_vault,
            vault=mock_vault,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_schedules_call_instruct_posting_batch_only_once(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            overpayment=Decimal(0),
            principal_due=Decimal(20),
            interest_due=Decimal(30),
            fees=Decimal(40),
            in_arrears_accrued=Decimal(50),
            default_committed=Decimal(60),
            principal_overdue=Decimal(70),
            interest_overdue=Decimal(80),
            principal=Decimal(100),
        )

        effective_date = DEFAULT_DATE + relativedelta(years=1)

        balance_ts += self.account_balances(
            effective_date,
            overpayment=Decimal(-50),
            principal_due=Decimal(20),
            interest_due=Decimal(30),
            fees=Decimal(40),
            in_arrears_accrued=Decimal(50),
            default_committed=Decimal(60),
            principal_overdue=Decimal(70),
            interest_overdue=Decimal(80),
            principal=Decimal(90),
        )
        event_types = [
            "ACCRUE_INTEREST",
            "REPAYMENT_DAY_SCHEDULE",
            "HANDLE_OVERPAYMENT_ALLOWANCE",
            "CHECK_DELINQUENCY",
        ]
        for event_type in event_types:
            mock_vault = self.create_mock(
                balance_ts=balance_ts,
                denomination=DEFAULT_DENOMINATION,
                fixed_interest_term=12,
                repayment_day=1,
                mortgage_start_date=DEFAULT_DATE,
                fixed_interest_rate=Decimal("0.01"),
                accrued_interest_receivable_account=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                interest_received_account=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
                fulfillment_precision=2,
                accrual_precision=5,
            )
            self.run_function(
                "scheduled_code",
                mock_vault,
                event_type=event_type,
                effective_date=effective_date,
            )
            self.assertIn(
                mock_vault.instruct_posting_batch.call_count,
                [0, 1],
                f"{event_type} has called instruct_posting_batch more than once",
            )


class CommonHelperTest(MortgageTest):
    contract_file = CONTRACT_FILE
    side = Tside.ASSET
    linked_contract_modules = {
        "utils": {
            "path": UTILS_MODULE_FILE,
        }
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
            interest_address=ACCRUED_INTEREST,
            actual_balance=Decimal("123.45"),
            rounded_balance=Decimal("123.45"),
            event_type="MOCK_EVENT",
            interest_received_account=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrued_interest_receivable_account=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            denomination=DEFAULT_DENOMINATION,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        self.assertEqual(len(interest_remainder_postings), 0)

    def test_create_interest_remainder_posting_negative_remainder(self):
        mock_vault = self.create_mock()

        interest_remainder_postings = self.run_function(
            "_create_interest_remainder_posting",
            mock_vault,
            vault=mock_vault,
            interest_address=ACCRUED_INTEREST,
            actual_balance=Decimal("123.4433"),
            rounded_balance=Decimal("123.45"),
            event_type="MOCK_EVENT",
            interest_received_account=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrued_interest_receivable_account=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            denomination=DEFAULT_DENOMINATION,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.0067"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=ACCRUED_INTEREST,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="MOCK_EVENT_REMAINDER_MOCK_HOOK_GBP_" "CUSTOMER",
                    instruction_details={
                        "description": "Extra interest charged to customer from negative remainder"
                        " due to repayable amount for ACCRUED_INTEREST rounded up",
                        "event_type": "MOCK_EVENT",
                    },
                ),
                call(
                    amount=Decimal("0.0067"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="MOCK_EVENT_REMAINDER_MOCK_HOOK_GBP_" "INTERNAL",
                    instruction_details={
                        "description": f"Extra interest charged to account {VAULT_ACCOUNT_ID} from "
                        "negative remainder due to repayable amount for "
                        f"{ACCRUED_INTEREST} rounded up",
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
            interest_address=ACCRUED_INTEREST,
            actual_balance=Decimal("123.4567"),
            rounded_balance=Decimal("123.45"),
            event_type="MOCK_EVENT",
            interest_received_account=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrued_interest_receivable_account=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            denomination=DEFAULT_DENOMINATION,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.0067"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=ACCRUED_INTEREST,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="MOCK_EVENT_REMAINDER_MOCK_HOOK_GBP_CUSTOMER",
                    instruction_details={
                        "description": "Extra interest returned to customer from positive "
                        f"remainder due to repayable amount for {ACCRUED_INTEREST} "
                        "rounded down",
                        "event_type": "MOCK_EVENT",
                    },
                ),
                call(
                    amount=Decimal("0.0067"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="MOCK_EVENT_REMAINDER_MOCK_HOOK_GBP_INTERNAL",
                    instruction_details={
                        "description": f"Extra interest returned to account {VAULT_ACCOUNT_ID} "
                        "from positive remainder due to repayable amount for "
                        f"{ACCRUED_INTEREST} rounded down",
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
                "description": "remortgage before first repayment day setting start date in future",
                "effective_date": datetime(2020, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "remortgage_date": datetime(2020, 2, 4, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "remortgage after first repayment day",
                "effective_date": datetime(2020, 2, 6, 10, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 2, 5, 0, 1, 0, tzinfo=timezone.utc),
                "remortgage_date": datetime(2020, 2, 6, 0, 0, 0, tzinfo=timezone.utc),
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
                "expected_result": datetime(2020, 8, 5, 0, 1, 0, tzinfo=timezone.utc),
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
                test_case["remortgage_date"]
                if "remortgage_date" in test_case
                else (datetime(2020, 1, 1, tzinfo=timezone.utc))
            )
            mock_vault = self.create_mock(
                total_term=12,
                repayment_day=5,
                mortgage_start_date=start_date,
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
                repayment_hour=0,
                repayment_minute=1,
                repayment_second=0,
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
                "description": "remortgage before first repayment day setting start date in future",
                "effective_date": datetime(2020, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "remortgage_date": datetime(2020, 2, 4, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "remortgage after first repayment day",
                "effective_date": datetime(2020, 3, 6, 10, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
                "remortgage_date": datetime(2020, 3, 6, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 5, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "1 microsecond before first repayment day",
                "effective_date": datetime(2020, 3, 4, 23, 59, 59, 999999, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "same day as first repayment day at 00:00",
                "effective_date": datetime(2020, 3, 5, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "same datetime as first repayment day",
                "effective_date": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "expected_result": datetime(2020, 4, 5, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "1 microsecond after first repayment day event",
                "effective_date": datetime(2020, 3, 5, 0, 1, 0, 1, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 3, 5, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 4, 5, 0, 1, 0, tzinfo=timezone.utc),
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
                "expected_result": datetime(2020, 8, 5, 0, 1, 0, tzinfo=timezone.utc),
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
                test_case["remortgage_date"]
                if "remortgage_date" in test_case
                else (datetime(2020, 1, 5, 0, 1, tzinfo=timezone.utc))
            )
            mock_vault = self.create_mock(
                total_term=12,
                repayment_day=5,
                mortgage_start_date=start_date,
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
                repayment_hour=0,
                repayment_minute=1,
                repayment_second=0,
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
                "description": "remortgage before first repayment day setting start date in future",
                "effective_date": datetime(2020, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
                "remortgage_date": datetime(2020, 2, 9, 0, 0, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 3, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "remortgage after first repayment day",
                "effective_date": datetime(2020, 3, 11, 10, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 3, 10, 0, 1, 0, tzinfo=timezone.utc),
                "remortgage_date": datetime(2020, 3, 11, 0, 0, 0, tzinfo=timezone.utc),
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
                "last_execution_time": datetime(2020, 5, 10, 0, 1, 0, tzinfo=timezone.utc),
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
                "expected_result": datetime(2020, 8, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
            {
                "description": "repayment day changed from 1 to 10",
                "effective_date": datetime(2020, 6, 2, 12, 1, 1, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 6, 1, 0, 1, 0, tzinfo=timezone.utc),
                "expected_result": datetime(2020, 7, 10, 0, 1, 0, tzinfo=timezone.utc),
            },
        ]
        for test_case in test_cases:
            start_date = (
                test_case["remortgage_date"]
                if "remortgage_date" in test_case
                else (datetime(2020, 1, 19, tzinfo=timezone.utc))
            )
            mock_vault = self.create_mock(
                total_term=12,
                repayment_day=10,
                mortgage_start_date=start_date,
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
                repayment_hour=0,
                repayment_minute=1,
                repayment_second=0,
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
                    "description": "before mortgage has disbursed at start of mortgage",
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
                    "description": "before first repayment of 1 year mortgage",
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
                    "description": "after first repayment of 1 year mortgage",
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
                    "description": "after 6th repayment of 1 year mortgage",
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
                    "description": "after penultimate repayment of 1 year mortgage",
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
                    "description": "10 year mortgage after first payment due",
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
                mock_vault = self.create_mock(
                    balance_ts=test_case["balances"],
                    denomination=DEFAULT_DENOMINATION,
                    total_term=test_case["total_term"],
                    variable_interest_rate=test_case["variable_interest_rate"],
                    fixed_interest_term=Decimal(0),
                    repayment_day=5,
                    fulfillment_precision=2,
                    mortgage_start_date=DEFAULT_DATE,
                    variable_rate_adjustment=Decimal(0),
                )
                effective_date = (
                    test_case["effective_date"] if "effective_date" in test_case else (DEFAULT_DATE)
                )
                result = self.run_function(
                    "_get_calculated_remaining_term",
                    mock_vault,
                    mock_vault,
                    effective_date,
                )
                self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_remaining_term_in_months(self):
        mortgage_start_date = datetime(2020, 1, 11, 0, 0, 0, tzinfo=timezone.utc)
        test_cases = [
            {
                "description": "before mortgage has disbursed at start of mortgage",
                "effective_date": mortgage_start_date,
                "last_execution_time": None,
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
                "description": "before first repayment of 1 year mortgage",
                "effective_date": datetime(2020, 2, 19, 0, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": None,
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
                "description": "after first transfer due of 1 year mortgage, "
                "calculated remaining term rather than expected",
                "effective_date": datetime(2020, 2, 20, 10, 0, 0, tzinfo=timezone.utc),
                "last_execution_time": datetime(2020, 2, 20, 0, 1, 0, tzinfo=timezone.utc),
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
                balance_ts=test_case["balances"],
                denomination=DEFAULT_DENOMINATION,
                total_term=test_case["total_term"],
                variable_interest_rate=test_case["variable_interest_rate"],
                fixed_interest_term=Decimal(0),
                repayment_day=5,
                fulfillment_precision=2,
                mortgage_start_date=mortgage_start_date,
                variable_rate_adjustment=Decimal(0),
                REPAYMENT_DAY_SCHEDULE=test_case["last_execution_time"],
                repayment_hour=0,
                repayment_minute=1,
                repayment_second=0,
            )
            result = self.run_function(
                "_get_remaining_term_in_months",
                mock_vault,
                mock_vault,
                test_case["effective_date"],
                "total_term",
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

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
