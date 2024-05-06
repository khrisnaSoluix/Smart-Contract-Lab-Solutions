import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import Mock, patch, call, sentinel

# inception imports
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ASSET,
    DEFAULT_ADDRESS,
    INTERNAL_CONTRA,
    Rejected,
    RejectedReason,
    Tside,
    EventTypeSchedule,
)
from inception_sdk.test_framework.contracts.unit.common import (
    ContractFeatureTest,
    TimeSeries,
)
import library.features.common.utils as utils
import library.features.lending.debt_management as debt_management

DEFAULT_DATE = datetime(2020, 1, 10)
DEFAULT_DENOMINATION = "GBP"

EMI_ADDRESS = "EMI"
PENALTIES_ADDRESS = "PENALTIES"
PRINCIPAL_ADDRESS = "PRINCIPAL"
PRINCIPAL_DUE_ADDRESS = "PRINCIPAL_DUE"
INTEREST_DUE_ADDRESS = "INTEREST_DUE"
PRINCIPAL_OVERDUE_ADDRESS = "PRINCIPAL_OVERDUE"
INTEREST_OVERDUE_ADDRESS = "INTEREST_OVERDUE"
ACCRUED_INTEREST_RECEIVABLE_ADDRESS = "ACCRUED_INTEREST_RECEIVABLE_ADDRESS"


class TestDebtManagement(ContractFeatureTest):

    target_test_file = "library/features/lending/debt_management.py"
    side = Tside.ASSET

    def create_mock(self, **kwargs):
        return super().create_mock(
            overdue_amount_calculation_blocking_flags=json.dumps(["REPAYMENT_HOLIDAY"]),
            delinquency_blocking_flags=json.dumps(["REPAYMENT_HOLIDAY"]),
            notification_blocking_flags=json.dumps(["REPAYMENT_HOLIDAY"]),
            **kwargs,
        )

    def test_get_event_types(self):
        test_cases = [
            {
                "product_name": "LOAN",
                "expected_event_names": [
                    "DUE_AMOUNT_CALCULATION",
                    "CHECK_OVERDUE",
                    "CHECK_DELINQUENCY",
                ],
                "expected_tag_ids": [
                    ["LOAN_DUE_AMOUNT_CALCULATION_AST"],
                    ["LOAN_CHECK_OVERDUE_AST"],
                    ["LOAN_CHECK_DELINQUENCY_AST"],
                ],
            },
            {
                "product_name": "loan",
                "expected_event_names": [
                    "DUE_AMOUNT_CALCULATION",
                    "CHECK_OVERDUE",
                    "CHECK_DELINQUENCY",
                ],
                "expected_tag_ids": [
                    ["LOAN_DUE_AMOUNT_CALCULATION_AST"],
                    ["LOAN_CHECK_OVERDUE_AST"],
                    ["LOAN_CHECK_DELINQUENCY_AST"],
                ],
            },
        ]
        for test_case in test_cases:
            event_types = debt_management.get_event_types(test_case["product_name"])
            self.assertEqual(3, len(event_types))
            self.assertEqual(event_types[0].name, test_case["expected_event_names"][0])
            self.assertEqual(event_types[1].name, test_case["expected_event_names"][1])
            self.assertEqual(event_types[0].scheduler_tag_ids, test_case["expected_tag_ids"][0])
            self.assertEqual(event_types[1].scheduler_tag_ids, test_case["expected_tag_ids"][1])

    def test_get_execution_schedules(self):
        test_cases = [
            {
                "description": "Check schedules are correctly defined for repayment period 5",
                "start_date": DEFAULT_DATE,
                "due_amount_calculation_day": int(28),
                "repayment_period": int(5),
                "grace_period": int(1),
                "due_amount_start_date": "2020-02-10 00:00:00",
                "check_overdue_start_date": "2020-02-15 00:00:00",
                "check_delinquency_start_date": "2020-02-16 00:00:00",
            },
            {
                "description": "Check schedules are correctly defined for repayment period 10",
                "start_date": DEFAULT_DATE,
                "due_amount_calculation_day": int(28),
                "repayment_period": int(10),
                "grace_period": int(1),
                "due_amount_start_date": "2020-02-10 00:00:00",
                "check_overdue_start_date": "2020-02-20 00:00:00",
                "check_delinquency_start_date": "2020-02-21 00:00:00",
            },
            {
                "description": "Check execution schedules are correctly defined in the edge case:"
                "start_date.day == due_amount_calculation_day but "
                "start_date.time > due_amount_calculation_time",
                "start_date": DEFAULT_DATE.replace(hour=10, minute=0, second=0),
                "due_amount_calculation_day": int(10),
                "repayment_period": int(5),
                "grace_period": int(1),
                "due_amount_start_date": "2020-02-10 00:00:00",
                "check_overdue_start_date": "2020-02-15 00:00:00",
                "check_delinquency_start_date": "2020-02-16 00:00:00",
            },
            {
                "description": "Check schedules are correctly defined for repayment period 5"
                "grace period 0 => delinquency check is overdue check +1 day",
                "start_date": DEFAULT_DATE,
                "due_amount_calculation_day": int(28),
                "repayment_period": int(5),
                "grace_period": int(0),
                "due_amount_start_date": "2020-02-10 00:00:00",
                "check_overdue_start_date": "2020-02-15 00:00:00",
                "check_delinquency_start_date": "2020-02-16 00:00:00",
            },
            {
                "description": "Check schedules are correctly defined for repayment period 5"
                "grace period 5 => delinquency check is overdue check +5 days",
                "start_date": DEFAULT_DATE,
                "due_amount_calculation_day": int(28),
                "repayment_period": int(5),
                "grace_period": int(5),
                "due_amount_start_date": "2020-02-10 00:00:00",
                "check_overdue_start_date": "2020-02-15 00:00:00",
                "check_delinquency_start_date": "2020-02-20 00:00:00",
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                due_amount_calculation_day=test_case["due_amount_calculation_day"],
                due_amount_calculation_hour=int(0),
                due_amount_calculation_minute=int(1),
                due_amount_calculation_second=int(0),
                check_overdue_hour=int(0),
                check_overdue_minute=int(1),
                check_overdue_second=int(0),
                check_delinquency_hour=int(0),
                check_delinquency_minute=int(1),
                check_delinquency_second=int(0),
                repayment_period=test_case["repayment_period"],
                grace_period=test_case["grace_period"],
            )

            check_overdue_datetime = datetime.strptime(
                test_case["check_overdue_start_date"], "%Y-%m-%d %H:%M:%S"
            )
            check_delinquency_datetime = datetime.strptime(
                test_case["check_delinquency_start_date"], "%Y-%m-%d %H:%M:%S"
            )

            expected_schedules = [
                (
                    "DUE_AMOUNT_CALCULATION",
                    {
                        "day": str(test_case["due_amount_calculation_day"]),
                        "hour": "0",
                        "minute": "1",
                        "second": "0",
                    },
                ),
                (
                    "CHECK_OVERDUE",
                    {
                        "year": str(check_overdue_datetime.year),
                        "month": str(check_overdue_datetime.month),
                        "day": str(check_overdue_datetime.day),
                        "hour": "0",
                        "minute": "1",
                        "second": "0",
                    },
                ),
                (
                    "CHECK_DELINQUENCY",
                    {
                        "year": str(check_delinquency_datetime.year),
                        "month": str(check_delinquency_datetime.month),
                        "day": str(check_delinquency_datetime.day),
                        "hour": "0",
                        "minute": "1",
                        "second": "0",
                    },
                ),
            ]

            execution_schedules = debt_management.get_execution_schedules(
                mock_vault, test_case["start_date"]
            )

            self.assertEqual(execution_schedules, expected_schedules)

    def test_schedule_overdue_check(self):
        mock_vault = self.create_mock()
        check_overdue_schedule_details = utils.ScheduleDetails(
            year=2020,
            month=1,
            day=22,
            hour=1,
            minute=2,
            second=3,
            last_execution_time=None,
        )
        debt_management.schedule_overdue_check(
            mock_vault, DEFAULT_DATE, check_overdue_schedule_details
        )
        mock_vault.update_event_type.assert_called_once_with(
            event_type="CHECK_OVERDUE",
            schedule=EventTypeSchedule(
                year="2020",
                month="1",
                day="22",
                hour="1",
                minute="2",
                second="3",
            ),
        )

    def test_get_check_overdue_schedule_details(self):
        mock_vault = self.create_mock(
            check_overdue_hour="4",
            check_overdue_minute="5",
            check_overdue_second="6",
            repayment_period="1",
        )
        effective_date = DEFAULT_DATE
        schedule_details = debt_management.get_check_overdue_schedule_details(
            mock_vault, effective_date
        )
        expected_details = utils.ScheduleDetails(
            year=2020,
            month=1,
            day=11,
            hour=4,
            minute=5,
            second=6,
            last_execution_time=None,
        )
        self.assertEqual(schedule_details, expected_details)

    def test_schedule_delinquency_check(self):
        mock_vault = self.create_mock()
        check_delinquency_schedule_details = utils.ScheduleDetails(
            year=2020,
            month=1,
            day=22,
            hour=1,
            minute=2,
            second=3,
            last_execution_time=None,
        )
        debt_management.schedule_delinquency_check(
            mock_vault, DEFAULT_DATE, check_delinquency_schedule_details
        )
        mock_vault.update_event_type.assert_called_once_with(
            event_type="CHECK_DELINQUENCY",
            schedule=EventTypeSchedule(
                year="2020",
                month="1",
                day="22",
                hour="1",
                minute="2",
                second="3",
            ),
        )

    def test_get_check_delinquency_schedule_details(self):
        mock_vault = self.create_mock(
            check_delinquency_hour="4",
            check_delinquency_minute="5",
            check_delinquency_second="6",
            grace_period="1",
        )
        effective_date = DEFAULT_DATE
        schedule_details = debt_management.get_check_delinquency_schedule_details(
            mock_vault, effective_date
        )
        expected_details = utils.ScheduleDetails(
            year=2020,
            month=1,
            day=11,
            hour=4,
            minute=5,
            second=6,
            last_execution_time=None,
        )
        self.assertEqual(schedule_details, expected_details)

    def test_get_due_amount_calculation_schedule_details(self):
        mock_vault = self.create_mock(
            due_amount_calculation_day=1,
            due_amount_calculation_hour=2,
            due_amount_calculation_minute=3,
            due_amount_calculation_second=4,
            DUE_AMOUNT_CALCULATION=datetime(2020, 3, 1, 2, 3, 4),
        )
        schedule_details = debt_management.get_due_amount_calculation_schedule_details(
            mock_vault, datetime(2020, 4, 1, 2, 3, 4)
        )
        self.assertEqual(
            schedule_details,
            utils.ScheduleDetails(
                year=None,
                month=None,
                day=1,
                hour=2,
                minute=3,
                second=4,
                last_execution_time=datetime(2020, 3, 1, 2, 3, 4),
            ),
        )

    def test_get_due_amount_calculation_schedule_details_with_same_effective_date(self):
        mock_vault = self.create_mock(
            due_amount_calculation_day=1,
            due_amount_calculation_hour=2,
            due_amount_calculation_minute=3,
            due_amount_calculation_second=4,
            DUE_AMOUNT_CALCULATION=datetime(2020, 3, 1, 2, 3, 4),
        )
        schedule_details = debt_management.get_due_amount_calculation_schedule_details(
            mock_vault, datetime(2020, 3, 1, 2, 3, 4)
        )
        self.assertEqual(
            schedule_details,
            utils.ScheduleDetails(
                year=None,
                month=None,
                day=1,
                hour=2,
                minute=3,
                second=4,
                # offset by one month
                last_execution_time=datetime(2020, 2, 1, 2, 3, 4),
            ),
        )

    def test_calculate_next_due_amount_calc_date_start_date_before_due_amount_calcn_day(
        self,
    ):
        test_cases = [
            {
                "description": "day before first due amount calculation day",
                "effective_date": datetime(2020, 2, 4, 0, 0, 0),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0),
            },
            {
                "description": "over a month before first due amount calculation day",
                "effective_date": datetime(2020, 1, 2, 0, 0, 0),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0),
            },
            {
                "description": "get first repayment date when run later in account lifecycle",
                "effective_date": datetime(2020, 1, 1),
                "last_execution_time": datetime(2020, 9, 5, 0, 1, 0),
                "expected_result": datetime(2020, 2, 5, 0, 1, 0),
            },
            {
                "description": (
                    "topup before first due amount calculation day setting start date in future"
                ),
                "effective_date": datetime(2020, 1, 2, 0, 0, 0),
                "last_execution_time": None,
                "topup_date": datetime(2020, 2, 4, 0, 0, 0),
                "expected_result": datetime(2020, 3, 5, 0, 1, 0),
            },
            {
                "description": "topup after first due amount calculation day",
                "effective_date": datetime(2020, 2, 6, 10, 0, 0),
                "last_execution_time": datetime(2020, 2, 5, 0, 1, 0),
                "topup_date": datetime(2020, 2, 6, 0, 0, 0),
                "expected_result": datetime(2020, 4, 5, 0, 1, 0),
            },
            {
                "description": "1 microsecond before first due amount calculation day",
                "effective_date": datetime(2020, 2, 4, 23, 59, 59, 999999),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0),
            },
            {
                "description": "same day as first due amount calculation day at 00:00",
                "effective_date": datetime(2020, 2, 5, 0, 0, 0),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0),
            },
            {
                "description": "same datetime as first due amount calculation day",
                "effective_date": datetime(2020, 2, 5, 0, 1, 0),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 5, 0, 1, 0),
            },
            {
                "description": "1 microsecond after first due amount calculation day event",
                "effective_date": datetime(2020, 2, 5, 0, 1, 0, 1),
                "last_execution_time": datetime(2020, 2, 5, 0, 1, 0),
                "expected_result": datetime(2020, 3, 5, 0, 1, 0),
            },
            {
                "description": "1 microsecond before mid due amount calculation day event",
                "effective_date": datetime(2020, 8, 5, 0, 0, 0, 999999),
                "last_execution_time": datetime(2020, 7, 5, 0, 1, 0),
                "expected_result": datetime(2020, 8, 5, 0, 1, 0),
            },
            {
                "description": "some days before last due amount calculation day",
                "effective_date": datetime(2020, 12, 1, 0, 0, 0),
                "last_execution_time": datetime(2020, 11, 5, 0, 1, 0),
                "expected_result": datetime(2020, 12, 5, 0, 1, 0),
            },
            {
                "description": "due amount calculation day changed from 10 to 5",
                "effective_date": datetime(2020, 6, 11, 12, 1, 1),
                "last_execution_time": datetime(2020, 6, 10, 0, 1, 0),
                "expected_result": datetime(2020, 7, 5, 0, 1, 0),
            },
            {
                "description": "due amount calculation day changed from 1 to 5",
                "effective_date": datetime(2020, 6, 1, 12, 1, 1),
                "last_execution_time": datetime(2020, 6, 1, 0, 1, 0),
                "expected_result": datetime(2020, 7, 5, 0, 1, 0),
            },
        ]
        for test_case in test_cases:
            start_date = (
                test_case["topup_date"] if "topup_date" in test_case else (datetime(2020, 1, 1))
            )
            due_amount_schedule_details = utils.ScheduleDetails(
                day=5,
                hour=0,
                minute=1,
                second=0,
                last_execution_time=test_case["last_execution_time"],
                year=None,
                month=None,
            )
            next_payment_date = debt_management._calculate_next_due_amount_calculation_date(
                loan_start_date=start_date,
                effective_date=test_case["effective_date"],
                due_amount_schedule_details=due_amount_schedule_details,
            )
            self.assertEqual(
                next_payment_date,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_calculate_next_due_amount_calc_date_start_date_same_as_due_amount_calc_day(
        self,
    ):
        test_cases = [
            {
                "description": "day before first due amount calculation day",
                "effective_date": datetime(2020, 3, 4, 0, 0, 0),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 5, 0, 1, 0),
            },
            {
                "description": "over a month before first due amount calculation day",
                "effective_date": datetime(2020, 1, 5, 0, 1, 0),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0),
            },
            {
                "description": (
                    "topup before first due amount calculation day setting start date in future"
                ),
                "effective_date": datetime(2020, 1, 2, 0, 0, 0),
                "last_execution_time": None,
                "topup_date": datetime(2020, 2, 4, 0, 0, 0),
                "expected_result": datetime(2020, 3, 5, 0, 1, 0),
            },
            {
                "description": "topup after first due amount calculation day",
                "effective_date": datetime(2020, 3, 6, 10, 0, 0),
                "last_execution_time": datetime(2020, 3, 5, 0, 1, 0),
                "topup_date": datetime(2020, 3, 6, 0, 0, 0),
                "expected_result": datetime(2020, 5, 5, 0, 1, 0),
            },
            {
                "description": "1 microsecond before first due amount calculation day",
                "effective_date": datetime(2020, 2, 4, 23, 59, 59, 999999),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0),
            },
            {
                "description": "same day as first due amount calculation day at 00:00",
                "effective_date": datetime(2020, 2, 5, 0, 0, 0),
                "last_execution_time": None,
                "expected_result": datetime(2020, 2, 5, 0, 1, 0),
            },
            {
                "description": "same datetime as first due amount calculation day",
                "effective_date": datetime(2020, 2, 5, 0, 1, 0),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 5, 0, 1, 0),
            },
            {
                "description": "1 microsecond after first due amount calculation day event",
                "effective_date": datetime(2020, 2, 5, 0, 1, 0, 1),
                "last_execution_time": datetime(2020, 3, 5, 0, 1, 0),
                "expected_result": datetime(2020, 3, 5, 0, 1, 0),
            },
            {
                "description": "1 microsecond before mid due amount calculation day event",
                "effective_date": datetime(2020, 8, 5, 0, 0, 0, 999999),
                "last_execution_time": datetime(2020, 7, 5, 0, 1, 0),
                "expected_result": datetime(2020, 8, 5, 0, 1, 0),
            },
            {
                "description": "some days before last due amount calculation day",
                "effective_date": datetime(2021, 2, 1, 0, 0, 0),
                "last_execution_time": datetime(2021, 1, 5, 0, 1, 0),
                "expected_result": datetime(2021, 2, 5, 0, 1, 0),
            },
            {
                "description": "due amount calculation day changed from 10 to 5",
                "effective_date": datetime(2020, 6, 11, 12, 1, 1),
                "last_execution_time": datetime(2020, 6, 10, 0, 1, 0),
                "expected_result": datetime(2020, 7, 5, 0, 1, 0),
            },
            {
                "description": "due amount calculation day changed from 1 to 5",
                "effective_date": datetime(2020, 6, 1, 12, 1, 1),
                "last_execution_time": datetime(2020, 6, 1, 0, 1, 0),
                "expected_result": datetime(2020, 7, 5, 0, 1, 0),
            },
        ]
        for test_case in test_cases:
            start_date = (
                test_case["topup_date"]
                if "topup_date" in test_case
                else (datetime(2020, 1, 5, 0, 1))
            )
            due_amount_schedule_details = utils.ScheduleDetails(
                day=5,
                hour=0,
                minute=1,
                second=0,
                last_execution_time=test_case["last_execution_time"],
                year=None,
                month=None,
            )
            next_payment_date = debt_management._calculate_next_due_amount_calculation_date(
                loan_start_date=start_date,
                effective_date=test_case["effective_date"],
                due_amount_schedule_details=due_amount_schedule_details,
            )
            self.assertEqual(
                next_payment_date,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_calculate_next_due_amount_calc_date_start_date_after_due_amount_calc_day(
        self,
    ):
        test_cases = [
            {
                "description": "day before first due amount calculation day",
                "effective_date": datetime(2020, 3, 9, 0, 0, 0),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 10, 0, 1, 0),
            },
            {
                "description": "over a month before first due amount calculation day",
                "effective_date": datetime(2020, 1, 20, 0, 0, 0),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 10, 0, 1, 0),
            },
            {
                "description": (
                    "topup before first due amount calculation day setting start date in future"
                ),
                "effective_date": datetime(2020, 1, 2, 0, 0, 0),
                "last_execution_time": None,
                "topup_date": datetime(2020, 2, 9, 0, 0, 0),
                "expected_result": datetime(2020, 3, 10, 0, 1, 0),
            },
            {
                "description": "topup after first due amount calculation day",
                "effective_date": datetime(2020, 3, 11, 10, 0, 0),
                "last_execution_time": datetime(2020, 3, 10, 0, 1, 0),
                "topup_date": datetime(2020, 3, 11, 0, 0, 0),
                "expected_result": datetime(2020, 5, 10, 0, 1, 0),
            },
            {
                "description": "1 microsecond before first due amount calculation day",
                "effective_date": datetime(2020, 3, 9, 23, 59, 59, 999999),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 10, 0, 1, 0),
            },
            {
                "description": "same day as first due amount calculation day at 00:00",
                "effective_date": datetime(2020, 3, 10, 0, 0, 0),
                "last_execution_time": None,
                "expected_result": datetime(2020, 3, 10, 0, 1, 0),
            },
            {
                "description": "same datetime as first due amount calculation day",
                "effective_date": datetime(2020, 3, 10, 0, 1, 0),
                "last_execution_time": None,
                "expected_result": datetime(2020, 4, 10, 0, 1, 0),
            },
            {
                "description": "1 microsecond after first due amount calculation day event",
                "effective_date": datetime(2020, 3, 10, 0, 1, 0, 1),
                "last_execution_time": datetime(2020, 3, 10, 0, 1, 0),
                "expected_result": datetime(2020, 4, 10, 0, 1, 0),
            },
            {
                "description": "1 microsecond before mid due amount calculation day event",
                "effective_date": datetime(2020, 8, 10, 0, 0, 0, 999999),
                "last_execution_time": datetime(2020, 7, 10, 0, 1, 0),
                "expected_result": datetime(2020, 8, 10, 0, 1, 0),
            },
            {
                "description": "some days before last due amount calculation day",
                "effective_date": datetime(2021, 2, 1, 0, 0, 0),
                "last_execution_time": datetime(2021, 1, 10, 0, 1, 0),
                "expected_result": datetime(2021, 2, 10, 0, 1, 0),
            },
            {
                "description": "due amount calculation day changed from 15 to 10",
                "effective_date": datetime(2020, 6, 16, 12, 1, 1),
                "last_execution_time": datetime(2020, 6, 15, 0, 1, 0),
                "expected_result": datetime(2020, 7, 10, 0, 1, 0),
            },
            {
                "description": "due amount calculation day changed from 1 to 10",
                "effective_date": datetime(2020, 6, 2, 12, 1, 1),
                "last_execution_time": datetime(2020, 6, 1, 0, 1, 0),
                "expected_result": datetime(2020, 7, 10, 0, 1, 0),
            },
            {
                "description": "due amount calculation day changed from 9 to 10,"
                "due amount calculation day occured this month",
                "effective_date": datetime(2020, 3, 12, 12, 1, 1),
                "last_execution_time": datetime(2020, 3, 9, 0, 1, 0),
                "expected_result": datetime(2020, 4, 10, 0, 1, 0),
            },
            {
                "description": "due amount calculation day changed from 12 to 15,"
                "before current months due amount calculation day",
                "effective_date": datetime(2020, 3, 9, 12, 1, 1),
                "due_amount_calculation_day": Decimal("15"),
                "last_execution_time": datetime(2020, 2, 12, 0, 1, 0),
                "expected_result": datetime(2020, 3, 15, 0, 1, 0),
            },
            {
                "description": (
                    "due amount calculation day changed from 12 to 11, before repayment date"
                ),
                "effective_date": datetime(2020, 3, 9, 12, 1, 1),
                "due_amount_calculation_day": Decimal("11"),
                "last_execution_time": datetime(2020, 2, 12, 0, 1, 0),
                "expected_result": datetime(2020, 3, 11, 0, 1, 0),
            },
            {
                "description": (
                    "due amount calculation day changed from 12 to 2, before repayment date"
                    "after 2nd has passed"
                ),
                "effective_date": datetime(2020, 3, 9, 12, 1, 1),
                "due_amount_calculation_day": Decimal("2"),
                "last_execution_time": datetime(2020, 2, 12, 0, 1, 0),
                "expected_result": datetime(2020, 3, 12, 0, 1, 0),
            },
        ]
        for test_case in test_cases:
            start_date = (
                test_case["topup_date"] if "topup_date" in test_case else (datetime(2020, 1, 19))
            )
            due_amount_calculation_day = (
                test_case["due_amount_calculation_day"]
                if "due_amount_calculation_day" in test_case
                else 10
            )

            due_amount_schedule_details = utils.ScheduleDetails(
                day=due_amount_calculation_day,
                hour=0,
                minute=1,
                second=0,
                last_execution_time=test_case["last_execution_time"],
                year=None,
                month=None,
            )
            next_payment_date = debt_management._calculate_next_due_amount_calculation_date(
                loan_start_date=start_date,
                effective_date=test_case["effective_date"],
                due_amount_schedule_details=due_amount_schedule_details,
            )

            self.assertEqual(
                next_payment_date,
                test_case["expected_result"],
                test_case["description"],
            )

    def test_get_expected_remaining_term_due_amount_calculation_day_before_start_date(self):
        test_cases = [
            {
                "description": "day before first due amount calculation day",
                "effective_date": datetime(2020, 3, 4, 0, 0, 0),
                "last_execution_time": None,
                "expected_result": (12, 0),
            },
            {
                "description": "day of first due amount calculation day",
                "effective_date": datetime(2020, 3, 5, 1, 0, 0),
                "last_execution_time": datetime(2020, 3, 5, 0, 1, 0),
                "expected_result": (12, 0),
            },
            {
                "description": "1 microsecond before end of first due amount calculation day",
                "effective_date": datetime(2020, 3, 5, 23, 59, 59, 99999),
                "last_execution_time": datetime(2020, 3, 5, 0, 1, 0),
                "expected_result": (12, 0),
            },
            {
                "description": "day after first due amount calculation day",
                "effective_date": datetime(2020, 3, 6, 0, 0, 0),
                "last_execution_time": datetime(2020, 3, 5, 0, 1, 0),
                "expected_result": (11, 1),
            },
            {
                "description": "day before mid due amount calculation day",
                "effective_date": datetime(2020, 9, 4, 0, 0, 0),
                "last_execution_time": datetime(2020, 8, 5, 0, 1, 0),
                "expected_result": (6, 6),
            },
            {
                "description": "day of mid due amount calculation day",
                "effective_date": datetime(2020, 9, 5, 1, 0, 0),
                "last_execution_time": datetime(2020, 9, 5, 0, 1, 0),
                "expected_result": (6, 6),
            },
            {
                "description": "day after mid due amount calculation day",
                "effective_date": datetime(2020, 9, 6, 0, 0, 0),
                "last_execution_time": datetime(2020, 9, 5, 0, 1, 0),
                "expected_result": (5, 7),
            },
            {
                "description": "day before last due amount calculation day",
                "effective_date": datetime(2021, 2, 4, 0, 0, 0),
                "last_execution_time": datetime(2021, 1, 5, 0, 1, 0),
                "expected_result": (1, 11),
            },
            {
                "description": "day of last due amount calculation day",
                "effective_date": datetime(2021, 2, 5, 0, 0, 0),
                "last_execution_time": datetime(2021, 1, 5, 0, 1, 0),
                "expected_result": (1, 11),
            },
            {
                "description": "day after last due amount calculation day",
                "effective_date": datetime(2021, 2, 6, 0, 0, 0),
                "last_execution_time": datetime(2021, 2, 5, 0, 1, 0),
                "expected_result": (0, 12),
            },
        ]
        for test_case in test_cases:
            due_amount_schedule_details = utils.ScheduleDetails(
                day=5,
                hour=0,
                minute=1,
                second=0,
                last_execution_time=test_case["last_execution_time"],
                year=None,
                month=None,
            )
            mock_vault = self.create_mock(total_term=12, loan_start_date=datetime(2020, 1, 10))
            result = debt_management.get_expected_remaining_term(
                mock_vault,
                test_case["effective_date"],
                schedule_details=due_amount_schedule_details,
            )
            self.assertEqual(
                result["remaining"], test_case["expected_result"][0], test_case["description"]
            )
            self.assertEqual(
                result["elapsed"], test_case["expected_result"][1], test_case["description"]
            )

    def test_get_expected_remaining_term_due_amount_calculation_day_after_start_date(self):
        test_cases = [
            {
                "description": "day before first due amount calculation day",
                "effective_date": datetime(2020, 2, 27, 0, 0, 0),
                "last_execution_time": None,
                "expected_result": (12, 0),
            },
            {
                "description": "day of first due amount calculation day",
                "effective_date": datetime(2020, 2, 28, 1, 0, 0),
                "last_execution_time": datetime(2020, 2, 28, 0, 1, 0),
                "expected_result": (12, 0),
            },
            {
                "description": "day after first due amount calculation day",
                "effective_date": datetime(2020, 2, 29, 0, 0, 0),
                "last_execution_time": datetime(2020, 2, 28, 0, 1, 0),
                "expected_result": (11, 1),
            },
            {
                "description": "day before mid due amount calculation day",
                "effective_date": datetime(2020, 8, 27, 0, 0, 0),
                "last_execution_time": datetime(2020, 7, 28, 0, 1, 0),
                "expected_result": (6, 6),
            },
            {
                "description": "day of mid due amount calculation day",
                "effective_date": datetime(2020, 8, 28, 1, 0, 0),
                "last_execution_time": datetime(2020, 8, 28, 0, 1, 0),
                "expected_result": (6, 6),
            },
            {
                "description": "day after mid due amount calculation day",
                "effective_date": datetime(2020, 8, 29, 0, 0, 0),
                "last_execution_time": datetime(2020, 8, 28, 0, 1, 0),
                "expected_result": (5, 7),
            },
            {
                "description": "day before last due amount calculation day",
                "effective_date": datetime(2021, 1, 27, 0, 0, 0),
                "last_execution_time": datetime(2020, 12, 28, 0, 1, 0),
                "expected_result": (1, 11),
            },
            {
                "description": "day of last due amount calculation day",
                "effective_date": datetime(2021, 1, 28, 0, 0, 0),
                "last_execution_time": datetime(2020, 12, 28, 0, 1, 0),
                "expected_result": (1, 11),
            },
            {
                "description": "day after last due amount calculation day",
                "effective_date": datetime(2021, 1, 29, 0, 0, 0),
                "last_execution_time": datetime(2020, 12, 28, 0, 1, 0),
                "expected_result": (0, 12),
            },
        ]
        for test_case in test_cases:
            due_amount_schedule_details = utils.ScheduleDetails(
                day=28,
                hour=0,
                minute=1,
                second=0,
                last_execution_time=test_case["last_execution_time"],
                year=None,
                month=None,
            )
            mock_vault = self.create_mock(total_term=12, loan_start_date=datetime(2020, 1, 20))
            result = debt_management.get_expected_remaining_term(
                mock_vault,
                test_case["effective_date"],
                schedule_details=due_amount_schedule_details,
            )
            self.assertEqual(
                result["remaining"], test_case["expected_result"][0], test_case["description"]
            )
            self.assertEqual(
                result["elapsed"], test_case["expected_result"][1], test_case["description"]
            )

    def test_get_expected_remaining_term_due_amount_calculation_day_on_start_date(self):
        test_cases = [
            {
                "description": "day before first due amount calculation day",
                "effective_date": datetime(2020, 1, 31, 0, 0, 0),
                "last_execution_time": None,
                "expected_result": (12, 0),
            },
            {
                "description": "day of first due amount calculation day",
                "effective_date": datetime(2020, 2, 1, 1, 0, 0),
                "last_execution_time": datetime(2020, 2, 1, 0, 1, 0),
                "expected_result": (12, 0),
            },
            {
                "description": "day after first due amount calculation day",
                "effective_date": datetime(2020, 2, 2, 0, 0, 0),
                "last_execution_time": datetime(2020, 2, 1, 0, 1, 0),
                "expected_result": (11, 1),
            },
            {
                "description": "day before mid due amount calculation day",
                "effective_date": datetime(2020, 7, 31, 0, 0, 0),
                "last_execution_time": datetime(2020, 7, 1, 0, 1, 0),
                "expected_result": (6, 6),
            },
            {
                "description": "day of mid due amount calculation day",
                "effective_date": datetime(2020, 8, 1, 1, 0, 0),
                "last_execution_time": datetime(2020, 8, 1, 0, 1, 0),
                "expected_result": (6, 6),
            },
            {
                "description": "day after mid due amount calculation day",
                "effective_date": datetime(2020, 8, 2, 0, 0, 0),
                "last_execution_time": datetime(2020, 8, 1, 0, 1, 0),
                "expected_result": (5, 7),
            },
            {
                "description": "day before last due amount calculation day",
                "effective_date": datetime(2020, 12, 31, 0, 0, 0),
                "last_execution_time": datetime(2020, 12, 1, 0, 1, 0),
                "expected_result": (1, 11),
            },
            {
                "description": "day of last due amount calculation day",
                "effective_date": datetime(2021, 1, 1, 0, 0, 0),
                "last_execution_time": datetime(2020, 12, 1, 0, 1, 0),
                "expected_result": (1, 11),
            },
            {
                "description": "day after last due amount calculation day",
                "effective_date": datetime(2021, 1, 2, 0, 0, 0),
                "last_execution_time": datetime(2021, 1, 1, 0, 1, 0),
                "expected_result": (0, 12),
            },
        ]
        for test_case in test_cases:
            due_amount_schedule_details = utils.ScheduleDetails(
                day=1,
                hour=0,
                minute=1,
                second=0,
                last_execution_time=test_case["last_execution_time"],
                year=None,
                month=None,
            )
            mock_vault = self.create_mock(total_term=12, loan_start_date=datetime(2020, 1, 1))
            result = debt_management.get_expected_remaining_term(
                mock_vault,
                test_case["effective_date"],
                schedule_details=due_amount_schedule_details,
            )
            self.assertEqual(
                result["remaining"], test_case["expected_result"][0], test_case["description"]
            )
            self.assertEqual(
                result["elapsed"], test_case["expected_result"][1], test_case["description"]
            )

    @patch("library.features.lending.debt_management.get_remaining_dues")
    @patch("library.features.lending.debt_management.get_all_remaining_debt")
    @patch("library.features.lending.debt_management.utils.get_posting_amount")
    def test_validate_repayment_rejects_debits(
        self, mocked_get_posting_amount, mocked_get_all_remaining_debt, mocked_get_remaining_dues
    ):
        # debit to an ASSET is positive
        mocked_get_posting_amount.return_value = Decimal("50")
        mocked_get_all_remaining_debt.return_value = Decimal("1000")
        mocked_get_remaining_dues.return_value = Decimal("100")

        postings = [
            self.outbound_hard_settlement(amount=Decimal("50"), denomination="GBP"),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock()

        with self.assertRaises(Rejected) as e:
            debt_management.validate_repayment(
                mock_vault,
                postings=postings_batch,
            )
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(str(e.exception), "Debiting not allowed from this account")
        self.assert_no_side_effects(mock_vault)

    @patch("library.features.lending.debt_management.get_remaining_dues")
    @patch("library.features.lending.debt_management.get_all_remaining_debt")
    @patch("library.features.lending.debt_management.utils.get_posting_amount")
    def test_validate_repayment_rejects_paying_more_than_owed(
        self, mocked_get_posting_amount, mocked_get_all_remaining_debt, mocked_get_remaining_dues
    ):
        # incoming credit to an ASSET account is negative
        mocked_get_posting_amount.return_value = Decimal("-317536.72")
        mocked_get_all_remaining_debt.return_value = Decimal("317535.78")
        mocked_get_remaining_dues.return_value = Decimal("2000")

        postings = [
            self.inbound_hard_settlement(amount="317536.72", denomination="GBP"),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock()

        with self.assertRaises(Rejected) as e:
            debt_management.validate_repayment(
                mock_vault,
                postings=postings_batch,
            )
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(str(e.exception), "Cannot pay more than is owed")
        self.assert_no_side_effects(mock_vault)

    def test_validate_repayment_rejects_multiple_postings_in_batch(self):

        postings = [
            self.inbound_hard_settlement(amount="1000.01", denomination="GBP"),
            self.inbound_hard_settlement(amount="200.01", denomination="GBP"),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock()

        with self.assertRaises(Rejected) as e:
            debt_management.validate_repayment(
                mock_vault,
                postings=postings_batch,
            )
        self.assertEqual(e.exception.reason_code, RejectedReason.CLIENT_CUSTOM_REASON)
        self.assertEqual(str(e.exception), "Multiple postings in batch not supported")
        self.assert_no_side_effects(mock_vault)

    @patch("library.features.lending.debt_management.get_remaining_dues")
    @patch("library.features.lending.debt_management.get_all_remaining_debt")
    @patch("library.features.lending.debt_management.utils.get_posting_amount")
    def test_validate_repayment_allows_credit(
        self, mocked_get_posting_amount, mocked_get_all_remaining_debt, mocked_get_remaining_dues
    ):
        mocked_get_posting_amount.return_value = Decimal("-500.00")
        mocked_get_all_remaining_debt.return_value = Decimal("317535.78")
        mocked_get_remaining_dues.return_value = Decimal("2000")

        postings = [
            self.inbound_hard_settlement(amount=Decimal("500"), denomination="GBP"),
        ]
        postings_batch = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            value_timestamp=DEFAULT_DATE + relativedelta(hours=1),
        )
        mock_vault = self.create_mock()

        try:
            debt_management.validate_repayment(
                mock_vault,
                postings=postings_batch,
            )
        except Rejected:
            self.fail("pre_posting_code raised Rejected for reasonable credit")

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_get_overdue_posting_instructions_with_overdue(
        self,
        mocked_get_balance_sum,
    ):
        def side_effect(_, addresses):
            balances = {
                PRINCIPAL_DUE_ADDRESS: Decimal("1000"),
                INTEREST_DUE_ADDRESS: Decimal("350.00"),
            }
            return balances.get(addresses[0])

        mocked_get_balance_sum.side_effect = side_effect

        mock_vault = self.create_mock(denomination=DEFAULT_DENOMINATION)

        results = debt_management.get_overdue_posting_instructions(mock_vault, DEFAULT_DATE)
        postings = [
            {
                "amount": Decimal("1000"),
                "asset": "COMMERCIAL_BANK_MONEY",
                "client_transaction_id": "MOCK_HOOK_PRINCIPAL_OVERDUE",
                "denomination": "GBP",
                "from_account_address": "PRINCIPAL_OVERDUE",
                "from_account_id": "Main account",
                "instruction_details": {
                    "description": ("Mark outstanding due amount of 1000 as PRINCIPAL_OVERDUE."),
                    "event": "MOVE_BALANCE_INTO_PRINCIPAL_OVERDUE",
                },
                "to_account_address": "PRINCIPAL_DUE",
                "to_account_id": "Main account",
                "override_all_restrictions": True,
            },
            {
                "amount": Decimal("350.00"),
                "asset": "COMMERCIAL_BANK_MONEY",
                "client_transaction_id": "MOCK_HOOK_INTEREST_OVERDUE",
                "denomination": "GBP",
                "from_account_address": "INTEREST_OVERDUE",
                "from_account_id": "Main account",
                "instruction_details": {
                    "description": ("Mark outstanding due amount of 350.00 as INTEREST_OVERDUE."),
                    "event": "MOVE_BALANCE_INTO_INTEREST_OVERDUE",
                },
                "to_account_address": "INTEREST_DUE",
                "to_account_id": "Main account",
                "override_all_restrictions": True,
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in postings]

        # principal due and interest due
        self.assertEqual(len(results), 2)

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    @patch("library.features.lending.debt_management.get_late_repayment_fee_posting_instructions")
    def test_get_overdue_posting_instructions_without_overdue(
        self,
        mocked_get_late_repayment_fee_posting_instructions,
        mocked_get_balance_sum,
    ):
        mocked_get_late_repayment_fee_posting_instructions.return_value = ["some late fee postings"]

        mocked_get_balance_sum.return_value = Decimal("0")

        mock_vault = self.create_mock(denomination=DEFAULT_DENOMINATION)

        results = debt_management.get_overdue_posting_instructions(mock_vault, DEFAULT_DATE)

        self.assertEqual(len(results), 0)

    def test_get_late_repayment_fee_posting_instructions(self):
        fee_amount = Decimal("15")
        late_repayment_fee_income_account = "late_repayment_fee_income_account"
        mock_vault = self.create_mock(
            denomination=DEFAULT_DENOMINATION,
            late_repayment_fee=fee_amount,
            late_repayment_fee_income_account=late_repayment_fee_income_account,
        )

        results = debt_management.get_late_repayment_fee_posting_instructions(mock_vault)

        self.assertEqual(len(results), 1)
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=fee_amount,
            denomination=DEFAULT_DENOMINATION,
            client_transaction_id="MOCK_HOOK_CHARGE_FEE",
            from_account_id="Main account",
            from_account_address="PENALTIES",
            to_account_id=late_repayment_fee_income_account,
            to_account_address=DEFAULT_ADDRESS,
            instruction_details={
                "description": f"Incur late repayment fees of {fee_amount}",
                "event": "INCUR_PENALTY_FEES",
            },
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
        )

    def test_get_late_repayment_fee_posting_instructions_zero_fee(self):
        fee_amount = Decimal("0")
        late_repayment_fee_income_account = "late_repayment_fee_income_account"
        mock_vault = self.create_mock(
            denomination=DEFAULT_DENOMINATION,
            late_repayment_fee=fee_amount,
            late_repayment_fee_income_account=late_repayment_fee_income_account,
        )

        results = debt_management.get_late_repayment_fee_posting_instructions(mock_vault)

        self.assertEqual(len(results), 0)
        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_get_principal_due_posting_instructions(self):
        mock_vault = self.create_mock()
        principal_due_amount = Decimal("100")
        results = debt_management.get_principal_due_posting_instructions(
            mock_vault, principal_due_amount, "GBP"
        )

        self.assertEqual(len(results), 1)
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=principal_due_amount,
            asset="COMMERCIAL_BANK_MONEY",
            client_transaction_id="UPDATE_PRINCIPAL_DUE_MOCK_HOOK",
            denomination="GBP",
            from_account_address="PRINCIPAL_DUE",
            from_account_id="Main account",
            instruction_details={
                "description": (f"Monthly principal added to due address: {principal_due_amount}"),
                "event": "DUE_AMOUNT_CALCULATION",
            },
            to_account_address="PRINCIPAL",
            to_account_id="Main account",
            override_all_restrictions=True,
        )

    def test_get_store_emi_posting_instructions_decreases_existing_stored_emi(self):
        mock_vault = self.create_mock(make_instructions_return_full_objects=True)
        emi_amount = Decimal("90")
        stored_emi = Decimal("100")
        debt_management.get_store_emi_posting_instructions(
            mock_vault, emi_amount, stored_emi, "GBP"
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=stored_emi - emi_amount,
            denomination=DEFAULT_DENOMINATION,
            client_transaction_id="UPDATE_EMI_MOCK_HOOK",
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            to_account_id="Main account",
            to_account_address=EMI_ADDRESS,
            instruction_details={
                "description": "Updating EMI amount from 100 to 90",
                "event": debt_management.DUE_AMOUNT_CALCULATION,
            },
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
        )

    def test_get_store_emi_posting_instructions_increases_existing_stored_emi(self):
        mock_vault = self.create_mock()
        emi_amount = Decimal("100")
        stored_emi = Decimal("90")
        debt_management.get_store_emi_posting_instructions(
            mock_vault, emi_amount, stored_emi, "GBP"
        )
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=emi_amount - stored_emi,
            denomination=DEFAULT_DENOMINATION,
            client_transaction_id="UPDATE_EMI_MOCK_HOOK",
            from_account_id="Main account",
            from_account_address=EMI_ADDRESS,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            instruction_details={
                "description": "Updating EMI amount from 90 to 100",
                "event": debt_management.DUE_AMOUNT_CALCULATION,
            },
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
        )

    def test_get_store_emi_posting_instructions_creates_initial_stored_emi(self):
        mock_vault = self.create_mock()
        emi_amount = Decimal("100")
        stored_emi = Decimal("0")
        debt_management.get_store_emi_posting_instructions(
            mock_vault, emi_amount, stored_emi, "GBP"
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=emi_amount,
            denomination=DEFAULT_DENOMINATION,
            client_transaction_id="UPDATE_EMI_MOCK_HOOK",
            from_account_id="Main account",
            from_account_address=EMI_ADDRESS,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            instruction_details={
                "description": "Updating EMI amount from 0 to 100",
                "event": debt_management.DUE_AMOUNT_CALCULATION,
            },
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
        )

    def test_get_store_emi_posting_instructions_negative_emi(self):
        mock_vault = self.create_mock()
        emi_amount = Decimal("-10")
        stored_emi = Decimal("10")
        debt_management.get_store_emi_posting_instructions(
            mock_vault, emi_amount, stored_emi, "GBP"
        )

        mock_vault.make_internal_transfer_instructions.not_called()

    def test_get_store_emi_posting_instructions_unchanged_emi(self):
        mock_vault = self.create_mock()
        emi_amount = Decimal("10")
        stored_emi = Decimal("10")
        debt_management.get_store_emi_posting_instructions(
            mock_vault, emi_amount, stored_emi, "GBP"
        )

        mock_vault.make_internal_transfer_instructions.not_called()

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_get_remaining_principal(self, mocked_get_balance_sum):
        overpayment = Mock()
        repayment_holiday = Mock()

        mocked_balance = {"PRINCIPAL": Decimal("1000")}

        def get_balance_sum_side_effect(_, addresses):
            return mocked_balance.get(addresses[0])

        mocked_get_balance_sum.side_effect = get_balance_sum_side_effect

        overpayment.get_principal_adjustment_amount.return_value = Decimal("100")
        repayment_holiday.get_principal_adjustment_amount.return_value = Decimal("30")
        principal_adjustment_effects = [overpayment, repayment_holiday]

        results = debt_management.get_remaining_principal(
            self.create_mock(), principal_adjustment_effects
        )
        self.assertEqual(results, Decimal("1130"))

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_get_remaining_principal_without_adjustment(self, mocked_get_balance_sum):

        mocked_balance = {"PRINCIPAL": Decimal("1000")}

        def get_balance_sum_side_effect(_, addresses):
            return mocked_balance.get(addresses[0])

        mocked_get_balance_sum.side_effect = get_balance_sum_side_effect

        results = debt_management.get_remaining_principal(self.create_mock())
        self.assertEqual(results, Decimal("1000"))

    @patch("library.features.lending.debt_management.interest_accrual", autospec=True)
    @patch("library.features.lending.debt_management.utils.get_balance_sum", autospec=True)
    @patch("library.features.lending.debt_management.get_remaining_principal", autospec=True)
    def test_get_all_remaining_debt(
        self, mocked_get_remaining_principal, mocked_get_balance_sum, mocked_interest_accrual
    ):
        mocked_balance = {
            PENALTIES_ADDRESS: Decimal("12.34"),
            PRINCIPAL_DUE_ADDRESS: Decimal("100.45"),
            INTEREST_DUE_ADDRESS: Decimal("22.11"),
            PRINCIPAL_OVERDUE_ADDRESS: Decimal("40.88"),
            INTEREST_OVERDUE_ADDRESS: Decimal("31.78"),
            ACCRUED_INTEREST_RECEIVABLE_ADDRESS: Decimal("0.34567"),
            "BALANCE_TO_IGNORE": Decimal("1000000"),
        }
        remaining_principal = Decimal("100")

        def get_balance_sum_side_effect(_, addresses) -> Decimal:
            return Decimal(sum(mocked_balance.get(address, Decimal("0")) for address in addresses))

        mocked_get_remaining_principal.return_value = remaining_principal
        mocked_interest_accrual.ACCRUED_INTEREST_RECEIVABLE_ADDRESS = (
            ACCRUED_INTEREST_RECEIVABLE_ADDRESS
        )
        mocked_get_balance_sum.side_effect = get_balance_sum_side_effect

        results = debt_management.get_all_remaining_debt(self.create_mock())

        # all balance addresses, other than the balance to ignore, and principal
        self.assertEqual(results, Decimal("307.90567"))

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_get_remaining_dues(self, mocked_get_balance_sum):
        mock_vault = self.create_mock()
        debt_management.get_remaining_dues(mock_vault)
        mocked_get_balance_sum.assert_called_once()

    def test_send_repayment_notification(self):
        test_cases = [
            {
                "description": "notification blocking flags passed to function",
                "effective_date": datetime(2020, 2, 5),
                "notification_blocking_flags": [TimeSeries([(datetime(2020, 1, 5), True)])],
                "notification_blocked": True,
            },
            {
                "description": "None notification blocking flags passed to function, but set on "
                "mock_vault - no notification",
                "effective_date": datetime(2020, 2, 5),
                "notification_blocking_flags": None,
                "vault_flags": ["REPAYMENT_HOLIDAY"],
                "notification_blocked": True,
            },
            {
                "description": "None notification blocking flags passed to function, and not set "
                "on mock_vault - notification sent",
                "effective_date": datetime(2020, 2, 5),
                "notification_blocking_flags": None,
                "vault_flags": [],
                "notification_blocked": False,
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock(flags=test_case.get("vault_flags"))
            repayment_amount = Decimal("123")
            debt_management.send_repayment_notification(
                mock_vault,
                repayment_amount,
                due_amount_calculation_date=test_case["effective_date"],
                repayment_period=12,
                product_name="LOAN",
                notification_blocking_flags=test_case["notification_blocking_flags"],
            )

            if test_case["notification_blocked"]:
                mock_vault.instruct_notification.assert_not_called()
            else:
                mock_vault.instruct_notification.assert_called_once_with(
                    notification_type="LOAN_REPAYMENT",
                    notification_details={
                        "account_id": mock_vault.account_id,
                        "repayment_amount": str(repayment_amount),
                        "overdue_date": str(
                            (test_case["effective_date"] + relativedelta(days=12)).date()
                        ),
                    },
                )

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_send_overdue_repayment_notification(self, mocked_get_balance_sum):
        mock_vault = self.create_mock(late_repayment_fee="10")
        due_amount = Decimal("123")
        mocked_get_balance_sum.return_value = due_amount
        debt_management.send_overdue_repayment_notification(
            mock_vault, DEFAULT_DATE, due_amount, "LOAN"
        )
        mock_vault.instruct_notification.assert_called_once_with(
            notification_type="LOAN_OVERDUE_REPAYMENT",
            notification_details={
                "account_id": mock_vault.account_id,
                "repayment_amount": str(due_amount),
                "late_repayment_fee": "10",
                "overdue_date": str(DEFAULT_DATE.date()),
            },
        )

    @patch("library.features.lending.debt_management.utils.is_flag_in_list_applied")
    def test_apply_delinquency_flag(self, mocked_is_flag_in_list_applied):
        mocked_is_flag_in_list_applied.return_value = False
        mock_vault = self.create_mock()
        debt_management.apply_delinquency_flag(mock_vault, DEFAULT_DATE, "LOAN")
        mock_vault.start_workflow.assert_called_once_with(
            workflow="LOAN_MARK_DELINQUENT",
            context={"account_id": mock_vault.account_id},
        )

    @patch("library.features.lending.debt_management.utils.is_flag_in_list_applied")
    def test_apply_delinquency_flag_already_flagged(self, mocked_is_flag_in_list_applied):
        mocked_is_flag_in_list_applied.return_value = True
        mock_vault = self.create_mock()
        debt_management.apply_delinquency_flag(mock_vault, DEFAULT_DATE, "LOAN")
        mock_vault.start_workflow.assert_not_called()

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_get_end_of_loan_cleanup_posting_instructions(self, mocked_get_balance_sum):
        emi_balance = Decimal("100")
        mock_vault = self.create_mock(denomination=DEFAULT_DENOMINATION)
        mocked_overpayment = Mock()
        mocked_overpayment.get_cleanup_residual_posting_instructions.return_value = [
            "some clean up postings"
        ]
        mocked_get_balance_sum.return_value = emi_balance
        results = debt_management.get_end_of_loan_cleanup_posting_instructions(
            mock_vault, [mocked_overpayment]
        )
        self.assertEqual(len(results), 2)
        mocked_overpayment.get_cleanup_residual_posting_instructions.assert_called_once()
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=emi_balance,
            denomination=DEFAULT_DENOMINATION,
            client_transaction_id="CLEAR_EMI_MOCK_HOOK",
            from_account_id=mock_vault.account_id,
            from_account_address=INTERNAL_CONTRA,
            to_account_id=mock_vault.account_id,
            to_account_address=EMI_ADDRESS,
            instruction_details={
                "description": "Clearing EMI address balance",
                "event": "END_OF_LOAN",
            },
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
        )


@patch("library.features.lending.debt_management.declining_principal.calculate_emi")
@patch("library.features.lending.debt_management.utils.get_balance_sum")
@patch("library.features.lending.debt_management.get_remaining_principal")
@patch("library.features.lending.debt_management.get_expected_remaining_term")
@patch("library.features.lending.debt_management.interest_accrual.get_accrued_interest")
@patch("library.features.lending.debt_management.get_store_emi_posting_instructions")
@patch("library.features.lending.debt_management.get_principal_due_posting_instructions")
class TestDebtManagementTransferDue(ContractFeatureTest):

    target_test_file = "library/features/lending/debt_management.py"
    side = Tside.ASSET

    def create_mock(self, **kwargs):
        return super().create_mock(
            due_amount_calculation_blocking_flags=json.dumps(["REPAYMENT_HOLIDAY"]),
            # These params do not affect test outcomes, but are needed to avoid exceptions due to
            # casting param values to int
            due_amount_calculation_day="5",
            due_amount_calculation_hour="0",
            due_amount_calculation_minute="0",
            due_amount_calculation_second="2",
            **kwargs,
        )

    def test_get_transfer_due_instructions(
        self,
        mocked_get_principal_due_posting_instructions,
        mocked_get_store_emi_posting_instructions,
        mocked_get_accrued_interest,
        mocked_get_expected_remaining_term,
        mocked_get_remaining_principal,
        mocked_get_balance_sum,
        mocked_calculate_emi,
    ):
        mock_vault = self.create_mock(repayment_period="5")

        mocked_overpayment = Mock(
            get_principal_adjustment_posting_instructions=Mock(
                return_value=[sentinel.overpayment_postings]
            ),
            should_trigger_reamortisation=Mock(return_value=False),
        )
        mocked_repayment_holiday = Mock(
            get_principal_adjustment_posting_instructions=Mock(
                return_value=[sentinel.repayment_holiday_postings]
            )
        )

        mocked_interest_calculation = Mock(
            get_interest_rate=Mock(return_value="some_rate"),
            should_trigger_reamortisation=Mock(return_value=False),
        )

        mocked_emi_adjustment_effects = [mocked_overpayment, mocked_interest_calculation]
        mocked_principal_adjustment_effects = [mocked_overpayment, mocked_repayment_holiday]

        mocked_get_remaining_principal.return_value = Decimal("200")
        mocked_get_store_emi_posting_instructions.return_value = [sentinel.emi_postings]
        mocked_get_principal_due_posting_instructions.return_value = [
            sentinel.principal_due_postings
        ]
        mock_application_posting_instructions = Mock(
            get_application_posting_instructions=Mock(return_value=[sentinel.application_postings])
        )

        mock_overpayment_application_posting_instructions = Mock(
            get_application_posting_instructions=Mock(
                return_value=[sentinel.overpayment_application_postings]
            )
        )

        mocked_application_effects = [
            mock_application_posting_instructions,
            mock_overpayment_application_posting_instructions,
        ]

        mocked_get_balance_sum.return_value = Decimal("100")
        mocked_get_accrued_interest.return_value = Decimal("12.6")

        results = debt_management.get_transfer_due_instructions(
            mock_vault,
            DEFAULT_DENOMINATION,
            DEFAULT_DATE,
            mocked_interest_calculation,
            emi_adjustment_effects=mocked_emi_adjustment_effects,
            principal_adjustment_effects=mocked_principal_adjustment_effects,
            interest_application_effects=mocked_application_effects,
        )

        self.assertListEqual(
            results,
            [
                # module does emi adjustment effects
                sentinel.emi_postings,
                # then principal due
                sentinel.principal_due_postings,
                # then application effects
                sentinel.application_postings,
                sentinel.overpayment_application_postings,
                # then principal adjustment effects
                sentinel.overpayment_postings,
                sentinel.repayment_holiday_postings,
            ],
        )

        # no re amortisation triggered
        mocked_calculate_emi.assert_not_called()

        mocked_get_remaining_principal.assert_called_once()
        mocked_get_expected_remaining_term.assert_called_once()
        mocked_get_accrued_interest.assert_called_once()

        mocked_get_principal_due_posting_instructions.assert_called_once_with(
            mock_vault, Decimal("100") - (Decimal("12.6")), DEFAULT_DENOMINATION
        )

    def test_get_transfer_due_instructions_principal_due_gt_remaining_principal(
        self,
        mocked_get_principal_due_posting_instructions,
        mocked_get_store_emi_posting_instructions,
        mocked_get_accrued_interest,
        mocked_get_expected_remaining_term,
        mocked_get_remaining_principal,
        mocked_get_balance_sum,
        mocked_calculate_emi,
    ):
        mock_vault = self.create_mock(repayment_period="5")

        # The principal due would be 100-12.6, but it is capped to 50
        mocked_get_remaining_principal.return_value = Decimal("50")
        mocked_get_balance_sum.return_value = Decimal("100")
        mocked_get_accrued_interest.return_value = Decimal("12.6")

        mocked_overpayment = Mock(
            get_principal_adjustment_posting_instructions=Mock(
                return_value=[sentinel.overpayment_postings]
            ),
            should_trigger_reamortisation=Mock(return_value=False),
        )
        mocked_repayment_holiday = Mock(
            get_principal_adjustment_posting_instructions=Mock(
                return_value=[sentinel.repayment_holiday_postings]
            )
        )

        mocked_interest_calculation = Mock(
            get_interest_rate=Mock(return_value="some_rate"),
            should_trigger_reamortisation=Mock(return_value=False),
        )

        mocked_emi_adjustment_effects = [mocked_overpayment, mocked_interest_calculation]
        mocked_principal_adjustment_effects = [mocked_overpayment, mocked_repayment_holiday]

        mocked_get_store_emi_posting_instructions.return_value = [sentinel.emi_postings]
        mocked_get_principal_due_posting_instructions.return_value = [
            sentinel.principal_due_postings
        ]
        mock_application_posting_instructions = Mock(
            get_application_posting_instructions=Mock(return_value=[sentinel.application_postings])
        )

        mock_overpayment_application_posting_instructions = Mock(
            get_application_posting_instructions=Mock(
                return_value=[sentinel.overpayment_application_postings]
            )
        )

        mocked_application_effects = [
            mock_application_posting_instructions,
            mock_overpayment_application_posting_instructions,
        ]

        results = debt_management.get_transfer_due_instructions(
            mock_vault,
            DEFAULT_DENOMINATION,
            DEFAULT_DATE,
            mocked_interest_calculation,
            emi_adjustment_effects=mocked_emi_adjustment_effects,
            principal_adjustment_effects=mocked_principal_adjustment_effects,
            interest_application_effects=mocked_application_effects,
        )

        self.assertListEqual(
            results,
            [
                # module does emi adjustment effects
                sentinel.emi_postings,
                # then principal due
                sentinel.principal_due_postings,
                # then application effects
                sentinel.application_postings,
                sentinel.overpayment_application_postings,
                # then principal adjustment effects
                sentinel.overpayment_postings,
                sentinel.repayment_holiday_postings,
            ],
        )

        # no re amortisation triggered
        mocked_calculate_emi.assert_not_called()

        mocked_get_remaining_principal.assert_called_once()
        mocked_get_expected_remaining_term.assert_called_once()
        mocked_get_accrued_interest.assert_called_once()

        mocked_get_principal_due_posting_instructions.assert_called_once_with(
            mock_vault, Decimal("50"), DEFAULT_DENOMINATION
        )

    def test_get_transfer_due_instructions_triggers_reamortisation(
        self,
        mocked_get_principal_due_posting_instructions,
        mocked_get_store_emi_posting_instructions,
        mocked_get_accrued_interest,
        mocked_get_expected_remaining_term,
        mocked_get_remaining_principal,
        mocked_get_balance_sum,
        mocked_calculate_emi,
    ):
        # The only difference if we require reamortisation is that the we see
        # posting instructions to adjust the EMI

        mock_vault = self.create_mock(repayment_period="5")

        mocked_overpayment = Mock(
            should_trigger_reamortisation=Mock(return_value=True),
        )

        mocked_interest_calculation = Mock(
            get_interest_rate=Mock(return_value="some_rate"),
            should_trigger_reamortisation=Mock(return_value=False),
        )

        mocked_emi_adjustment_effects = [mocked_overpayment, mocked_interest_calculation]
        mocked_get_remaining_principal.return_value = Decimal("200")
        mocked_get_store_emi_posting_instructions.return_value = [sentinel.emi_postings]
        mocked_get_principal_due_posting_instructions.return_value = [
            sentinel.principal_due_postings
        ]
        mock_application_posting_instructions = Mock(
            get_application_posting_instructions=Mock(return_value=[sentinel.application_postings])
        )

        mocked_application_effects = [
            mock_application_posting_instructions,
        ]

        mocked_calculate_emi.return_value = Decimal("100")
        mocked_get_balance_sum.return_value = Decimal("100")
        mocked_get_accrued_interest.return_value = Decimal("12.6")

        results = debt_management.get_transfer_due_instructions(
            mock_vault,
            DEFAULT_DENOMINATION,
            DEFAULT_DATE,
            mocked_interest_calculation,
            emi_adjustment_effects=mocked_emi_adjustment_effects,
            principal_adjustment_effects=[],
            interest_application_effects=mocked_application_effects,
        )

        self.assertListEqual(
            results,
            [
                # module does emi adjustment effects
                sentinel.emi_postings,
                # then principal due
                sentinel.principal_due_postings,
                # then application effects
                sentinel.application_postings,
                # no principal adjustment effects
            ],
        )

        # reamortisation is triggered
        mocked_calculate_emi.assert_called_once()

        mocked_get_remaining_principal.assert_called_once()
        mocked_get_expected_remaining_term.assert_called_once()
        mocked_get_accrued_interest.assert_called_once()

        mocked_get_principal_due_posting_instructions.assert_called_once_with(
            mock_vault, Decimal("100") - (Decimal("12.6")), DEFAULT_DENOMINATION
        )

    def test_get_transfer_due_instructions_with_schedule_details(
        self,
        mocked_get_principal_due_posting_instructions,
        mocked_get_store_emi_posting_instructions,
        mocked_get_accrued_interest,
        mocked_get_expected_remaining_term,
        mocked_get_remaining_principal,
        mocked_get_balance_sum,
        mocked_calculate_emi,
    ):
        # no repayment_period available via `vault`
        mock_vault = self.create_mock()
        due_amount_schedule_details = utils.ScheduleDetails(
            day=1,
            hour=2,
            minute=3,
            second=4,
            last_execution_time=datetime(2020, 1, 1, 2, 3, 4),
            month=None,
            year=None,
        )
        repayment_period = 5

        mocked_overpayment = Mock(
            get_principal_adjustment_posting_instructions=Mock(
                return_value=[sentinel.overpayment_postings]
            ),
            should_trigger_reamortisation=Mock(return_value=False),
        )
        mocked_repayment_holiday = Mock(
            get_principal_adjustment_posting_instructions=Mock(
                return_value=[sentinel.repayment_holiday_postings]
            )
        )

        mocked_interest_calculation = Mock(
            get_interest_rate=Mock(return_value="some_rate"),
            should_trigger_reamortisation=Mock(return_value=False),
        )

        mocked_emi_adjustment_effects = [mocked_overpayment, mocked_interest_calculation]
        mocked_principal_adjustment_effects = [mocked_overpayment, mocked_repayment_holiday]
        mocked_get_remaining_principal.return_value = Decimal("200")
        mocked_get_store_emi_posting_instructions.return_value = [sentinel.emi_postings]
        mocked_get_principal_due_posting_instructions.return_value = [
            sentinel.principal_due_postings
        ]
        mock_application_posting_instructions = Mock(
            get_application_posting_instructions=Mock(return_value=[sentinel.application_postings])
        )

        mock_overpayment_application_posting_instructions = Mock(
            get_application_posting_instructions=Mock(
                return_value=[sentinel.overpayment_application_postings]
            )
        )

        mocked_application_effects = [
            mock_application_posting_instructions,
            mock_overpayment_application_posting_instructions,
        ]

        mocked_get_balance_sum.return_value = Decimal("100")
        mocked_get_accrued_interest.return_value = Decimal("12.6")

        results = debt_management.get_transfer_due_instructions(
            mock_vault,
            DEFAULT_DENOMINATION,
            DEFAULT_DATE,
            mocked_interest_calculation,
            repayment_period=repayment_period,
            emi_adjustment_effects=mocked_emi_adjustment_effects,
            principal_adjustment_effects=mocked_principal_adjustment_effects,
            interest_application_effects=mocked_application_effects,
            due_amount_schedule_details=due_amount_schedule_details,
        )

        self.assertListEqual(
            results,
            [
                # module does emi adjustment effects
                sentinel.emi_postings,
                # then principal due
                sentinel.principal_due_postings,
                # then application effects
                sentinel.application_postings,
                sentinel.overpayment_application_postings,
                # then principal adjustment effects
                sentinel.overpayment_postings,
                sentinel.repayment_holiday_postings,
            ],
        )

        # no re amortisation triggered
        mocked_calculate_emi.assert_not_called()

        mocked_get_remaining_principal.assert_called_once()
        mocked_get_expected_remaining_term.assert_called_once_with(
            mock_vault, DEFAULT_DATE, schedule_details=due_amount_schedule_details
        )
        mocked_get_accrued_interest.assert_called_once_with(mock_vault)

        mocked_get_principal_due_posting_instructions.assert_called_once_with(
            mock_vault, Decimal("100") - (Decimal("12.6")), DEFAULT_DENOMINATION
        )

    def test_get_transfer_due_ignores_loan_under_a_month_old(
        self,
        mocked_get_principal_due_posting_instructions,
        mocked_get_store_emi_posting_instructions,
        mocked_get_accrued_interest,
        mocked_get_expected_remaining_term,
        mocked_get_remaining_principal,
        mocked_get_balance_sum,
        mocked_calculate_emi,
    ):
        test_cases = [
            {
                "description": "loan more than a month old not ignored",
                "effective_date": datetime(2020, 2, 5, 0, 0, 0),
                "loan_creation_date": datetime(2020, 1, 1, 0, 0, 0),
                "loan_ignored": False,
            },
            {
                "description": "loan less than a month old ignored",
                "effective_date": datetime(2020, 2, 5, 0, 0, 0),
                "loan_creation_date": datetime(2020, 2, 1, 0, 0, 0),
                "loan_ignored": True,
            },
            {
                "description": "loan exactly a month old not ignored",
                "effective_date": datetime(2020, 2, 5, 0, 0, 0),
                "loan_creation_date": datetime(2020, 1, 5, 0, 0, 0),
                "loan_ignored": False,
            },
            {
                "description": "loan opening time is not used",
                "effective_date": datetime(2020, 2, 5, 0, 0, 0),
                "loan_creation_date": datetime(2020, 1, 5, 6, 0, 0),
                "loan_ignored": False,
            },
        ]
        mocked_get_balance_sum.return_value = Decimal("100")
        mocked_get_remaining_principal.return_value = Decimal("200")
        mocked_get_accrued_interest.return_value = Decimal("12.6")
        for test_case in test_cases:
            mock_vault = self.create_mock(creation_date=test_case["loan_creation_date"])

            results = debt_management.get_transfer_due_instructions(
                mock_vault,
                DEFAULT_DENOMINATION,
                test_case["effective_date"],
                Mock(),
                repayment_period=5,
                emi_adjustment_effects=[],
                principal_adjustment_effects=[],
                interest_application_effects=[],
            )
            if test_case["loan_ignored"]:
                self.assertEqual(results, [], test_case["description"])
            else:
                self.assertNotEqual(results, [], test_case["description"])

    def test_get_transfer_due_blocking_flags(
        self,
        mocked_get_principal_due_posting_instructions,
        mocked_get_store_emi_posting_instructions,
        mocked_get_accrued_interest,
        mocked_get_expected_remaining_term,
        mocked_get_remaining_principal,
        mocked_get_balance_sum,
        mocked_calculate_emi,
    ):
        test_cases = [
            {
                "description": "due amount blocking flags passed to function",
                "effective_date": datetime(2020, 2, 5),
                "due_amount_calculation_blocking_flags": [
                    TimeSeries([(datetime(2020, 1, 5), True)])
                ],
                "due_amount_blocked": True,
            },
            {
                "description": "None due amount blocking flags passed to function, but set on "
                "mock_vault - no due amount postings",
                "effective_date": datetime(2020, 2, 5),
                "due_amount_calculation_blocking_flags": None,
                "vault_flags": ["REPAYMENT_HOLIDAY"],
                "due_amount_blocked": True,
            },
            {
                "description": "None due amount blocking flags passed to function, and not set "
                "on mock_vault - due amount postings generated",
                "effective_date": datetime(2020, 2, 5),
                "due_amount_calculation_blocking_flags": None,
                "vault_flags": [],
                "due_amount_blocked": False,
            },
        ]
        mocked_get_balance_sum.return_value = Decimal("100")
        mocked_get_remaining_principal.return_value = Decimal("200")
        mocked_get_accrued_interest.return_value = Decimal("12.6")
        for test_case in test_cases:
            mock_vault = self.create_mock(flags=test_case.get("vault_flags"))

            results = debt_management.get_transfer_due_instructions(
                mock_vault,
                DEFAULT_DENOMINATION,
                test_case["effective_date"],
                Mock(),
                repayment_period=5,
                emi_adjustment_effects=[],
                principal_adjustment_effects=[],
                interest_application_effects=[],
                due_amount_calculation_blocking_flags=test_case[
                    "due_amount_calculation_blocking_flags"
                ],
            )
            if test_case["due_amount_blocked"]:
                self.assertEqual(results, [], test_case["description"])
            else:
                self.assertNotEqual(results, [], test_case["description"])


class TestRepaymentProcessing(ContractFeatureTest):

    target_test_file = "library/features/lending/debt_management.py"
    side = Tside.ASSET

    REPAYMENT_HIERARCHY = [["ADDRESS_1"], ["ADDRESS_2", "ADDRESS_3"], ["ADDRESS_4"]]

    def setUp(self) -> None:
        self.maxDiff = None
        return super().setUp()

    def mock_balances_multi_account(
        self,
        mock_get_balance_sum: Mock,
        loan_1_address_1: Decimal = Decimal(0),
        loan_1_address_2: Decimal = Decimal(0),
        loan_1_address_3: Decimal = Decimal(0),
        loan_1_address_4: Decimal = Decimal(0),
        loan_2_address_1: Decimal = Decimal(0),
        loan_2_address_2: Decimal = Decimal(0),
        loan_2_address_3: Decimal = Decimal(0),
        loan_2_address_4: Decimal = Decimal(0),
    ) -> None:
        mock_get_balance_sum.side_effect = [
            # This is ordered as per the test hierarchy
            loan_1_address_1,
            loan_2_address_1,
            loan_1_address_2,
            loan_1_address_3,
            loan_2_address_2,
            loan_2_address_3,
            loan_1_address_4,
            loan_2_address_4,
        ]

    def mock_balances_single_account(
        self,
        mock_get_balance_sum: Mock,
        loan_1_address_1: Decimal = Decimal(0),
        loan_1_address_2: Decimal = Decimal(0),
        loan_1_address_3: Decimal = Decimal(0),
        loan_1_address_4: Decimal = Decimal(0),
    ) -> None:
        mock_get_balance_sum.side_effect = [
            # This is ordered as per the test hierarchy
            loan_1_address_1,
            loan_1_address_2,
            loan_1_address_3,
            loan_1_address_4,
        ]

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_distribute_full_repayment_single_target(self, mock_get_balance_sum: Mock):
        self.mock_balances_single_account(
            mock_get_balance_sum,
            loan_1_address_1=Decimal("10.00"),
            loan_1_address_2=Decimal("1.00"),
            loan_1_address_3=Decimal("0.015"),
            loan_1_address_4=Decimal("0.10"),
        )

        mock_vault = self.create_mock(account_id="loan_1")
        amount = Decimal("11.12")
        results = debt_management.distribute_repayment(
            repayment_targets=[mock_vault],
            repayment_amount=amount,
            denomination=DEFAULT_DENOMINATION,
            repayment_hierarchy=self.REPAYMENT_HIERARCHY,
        )[mock_vault]

        self.assertDictEqual(
            results,
            {
                "ADDRESS_1": (Decimal("10.00"), Decimal("10.00")),
                "ADDRESS_2": (Decimal("1.00"), Decimal("1.00")),
                "ADDRESS_3": (Decimal("0.015"), Decimal("0.02")),
                "ADDRESS_4": (Decimal("0.1"), Decimal("0.1")),
            },
        )

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_distribute_partial_repayment_single_target(self, mock_get_balance_sum: Mock):
        self.mock_balances_single_account(
            mock_get_balance_sum,
            loan_1_address_1=Decimal("10.00"),
            loan_1_address_2=Decimal("1.00"),
            loan_1_address_3=Decimal("0.015"),
            loan_1_address_4=Decimal("0.10"),
        )
        mock_vault = self.create_mock(account_id="loan_1")
        amount = Decimal("11.02")
        results = debt_management.distribute_repayment(
            repayment_targets=[mock_vault],
            repayment_amount=amount,
            denomination=DEFAULT_DENOMINATION,
            repayment_hierarchy=self.REPAYMENT_HIERARCHY,
        )[mock_vault]

        self.assertDictEqual(
            results,
            {
                "ADDRESS_1": (Decimal("10.00"), Decimal("10.00")),
                "ADDRESS_2": (Decimal("1.00"), Decimal("1.00")),
                "ADDRESS_3": (Decimal("0.015"), Decimal("0.02")),
            },
        )

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_distribute_partial_repayment_multiple_targets(self, mock_get_balance_sum: Mock):
        self.mock_balances_multi_account(
            mock_get_balance_sum,
            loan_1_address_1=Decimal("10.00"),
            loan_2_address_1=Decimal("10.00"),
            loan_1_address_2=Decimal("1.00"),
            loan_1_address_3=Decimal("0.049"),
        )

        mock_vault_1 = self.create_mock(account_id="loan_1")
        mock_vault_2 = self.create_mock(account_id="loan_2")
        amount = Decimal("21.05")
        results = debt_management.distribute_repayment(
            repayment_targets=[mock_vault_1, mock_vault_2],
            repayment_amount=amount,
            denomination=DEFAULT_DENOMINATION,
            repayment_hierarchy=self.REPAYMENT_HIERARCHY,
        )

        self.assertDictEqual(
            results,
            {
                mock_vault_1: {
                    "ADDRESS_1": (Decimal("10.00"), Decimal("10.00")),
                    "ADDRESS_2": (Decimal("1.00"), Decimal("1.00")),
                    "ADDRESS_3": (Decimal("0.049"), Decimal("0.05")),
                },
                mock_vault_2: {
                    "ADDRESS_1": (Decimal("10.00"), Decimal("10.00")),
                },
            },
        )

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_distribute_full_repayment_multiple_targets(self, mock_get_balance_sum: Mock):
        self.mock_balances_multi_account(
            mock_get_balance_sum,
            loan_1_address_1=Decimal("10.00"),
            loan_2_address_1=Decimal("10.00"),
            loan_1_address_2=Decimal("1.00"),
            loan_1_address_3=Decimal("0.049"),
            loan_2_address_2=Decimal("0.50"),
            loan_2_address_3=Decimal("0.012"),
        )
        amount = Decimal("21.56")

        mock_vault_1 = self.create_mock(account_id="loan_1")
        mock_vault_2 = self.create_mock(account_id="loan_2")
        results = debt_management.distribute_repayment(
            repayment_targets=[mock_vault_1, mock_vault_2],
            repayment_amount=amount,
            denomination=DEFAULT_DENOMINATION,
            repayment_hierarchy=self.REPAYMENT_HIERARCHY,
        )

        self.assertDictEqual(
            results,
            {
                mock_vault_1: {
                    "ADDRESS_1": (Decimal("10.00"), Decimal("10.00")),
                    "ADDRESS_2": (Decimal("1.00"), Decimal("1.00")),
                    "ADDRESS_3": (Decimal("0.049"), Decimal("0.05")),
                },
                mock_vault_2: {
                    "ADDRESS_1": (Decimal("10.00"), Decimal("10.00")),
                    "ADDRESS_2": (Decimal("0.50"), Decimal("0.50")),
                    "ADDRESS_3": (Decimal("0.012"), Decimal("0.01")),
                },
            },
        )

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_single_target_round_down_behaviour(self, mock_get_balance_sum: Mock):
        self.mock_balances_single_account(
            mock_get_balance_sum,
            loan_1_address_1=Decimal("0.012"),
        )
        amount = Decimal("0.01")

        mock_vault_1 = self.create_mock(account_id="loan_1")
        results = debt_management.distribute_repayment(
            repayment_targets=[mock_vault_1],
            repayment_amount=amount,
            denomination=DEFAULT_DENOMINATION,
            repayment_hierarchy=self.REPAYMENT_HIERARCHY,
        )

        self.assertDictEqual(
            results,
            {
                mock_vault_1: {"ADDRESS_1": (Decimal("0.012"), Decimal("0.01"))},
            },
        )

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_single_target_round_down_behaviour_underpay(self, mock_get_balance_sum: Mock):
        self.mock_balances_single_account(
            mock_get_balance_sum,
            loan_1_address_1=Decimal("0.022"),
        )
        amount = Decimal("0.01")

        mock_vault_1 = self.create_mock(account_id="loan_1")
        results = debt_management.distribute_repayment(
            repayment_targets=[mock_vault_1],
            repayment_amount=amount,
            denomination=DEFAULT_DENOMINATION,
            repayment_hierarchy=self.REPAYMENT_HIERARCHY,
        )

        self.assertDictEqual(
            results,
            {
                mock_vault_1: {"ADDRESS_1": (Decimal("0.01"), Decimal("0.01"))},
            },
        )

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_single_target_round_up_behaviour_underpay(self, mock_get_balance_sum: Mock):
        self.mock_balances_single_account(
            mock_get_balance_sum,
            loan_1_address_1=Decimal("0.018"),
        )
        amount = Decimal("0.01")

        mock_vault_1 = self.create_mock(account_id="loan_1")
        results = debt_management.distribute_repayment(
            repayment_targets=[mock_vault_1],
            repayment_amount=amount,
            denomination=DEFAULT_DENOMINATION,
            repayment_hierarchy=self.REPAYMENT_HIERARCHY,
        )

        self.assertDictEqual(
            results,
            {
                mock_vault_1: {"ADDRESS_1": (Decimal("0.01"), Decimal("0.01"))},
            },
        )

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_single_target_round_up_behaviour(self, mock_get_balance_sum: Mock):
        self.mock_balances_single_account(
            mock_get_balance_sum,
            loan_1_address_1=Decimal("0.0092"),
        )
        amount = Decimal("0.01")

        mock_vault_1 = self.create_mock(account_id="loan_1")
        results = debt_management.distribute_repayment(
            repayment_targets=[mock_vault_1],
            repayment_amount=amount,
            denomination=DEFAULT_DENOMINATION,
            repayment_hierarchy=self.REPAYMENT_HIERARCHY,
        )

        self.assertDictEqual(
            results,
            {
                mock_vault_1: {"ADDRESS_1": (Decimal("0.0092"), Decimal("0.01"))},
            },
        )

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_single_target_round_to_0_balance_behaviour(self, mock_get_balance_sum: Mock):
        self.mock_balances_single_account(
            mock_get_balance_sum,
            loan_1_address_1=Decimal("0.0042"),
        )
        amount = Decimal("0.01")

        mock_vault_1 = self.create_mock(account_id="loan_1")
        results = debt_management.distribute_repayment(
            repayment_targets=[mock_vault_1],
            repayment_amount=amount,
            denomination=DEFAULT_DENOMINATION,
            repayment_hierarchy=self.REPAYMENT_HIERARCHY,
        )

        self.assertDictEqual(
            results,
            {mock_vault_1: {}},
        )

    @patch("library.features.lending.debt_management.utils.get_balance_sum")
    def test_single_target_multiple_round_up_within_list(self, mock_get_balance_sum: Mock):
        self.mock_balances_single_account(
            mock_get_balance_sum,
            loan_1_address_1=Decimal("10.00"),
            # each of these individual rounds up to 0.01, only the first is repaid
            loan_1_address_2=Decimal("0.0052"),
            loan_1_address_3=Decimal("0.0052"),
        )
        amount = Decimal("10.01")

        mock_vault_1 = self.create_mock(account_id="loan_1")
        results = debt_management.distribute_repayment(
            repayment_targets=[mock_vault_1],
            repayment_amount=amount,
            denomination=DEFAULT_DENOMINATION,
            repayment_hierarchy=self.REPAYMENT_HIERARCHY,
        )

        self.assertDictEqual(
            results,
            {
                mock_vault_1: {
                    "ADDRESS_1": (Decimal("10.00"), Decimal("10.00")),
                    "ADDRESS_2": (Decimal("0.0052"), Decimal("0.01")),
                }
            },
        )
