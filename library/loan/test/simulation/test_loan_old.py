# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

# library
from library.loan.contracts.template import loan
from library.loan.test import accounts, dimensions, parameters
from library.loan.test.simulation.common import LoanTestBase

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedDerivedParameter,
    ExpectedRejection,
    ExpectedSchedule,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_template_parameter_change_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    get_balances,
    get_postings,
    get_processed_scheduled_events,
)

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
num_payments = 1
repayment_day = 28
payment_hour = 12
start_year = 2020
start_month = 1
loan_2_first_month_payment = str(Decimal("2910.69") + Decimal("229.32"))
loan_2_EMI = "2910.69"

loan_1_instance_params = {
    **parameters.loan_instance_params,
    loan.PARAM_FIXED_RATE_LOAN: "False",
    loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: "False",
    loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.129971",
    loan.disbursement.PARAM_PRINCIPAL: "300000",
    loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "12",
    loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "120",
    loan.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "-0.001",
}

loan_1_template_params = {
    **parameters.loan_template_params,
    loan.PARAM_AMORTISATION_METHOD: "declining_principal",
    loan.PARAM_LATE_REPAYMENT_FEE: "15",
    loan.PARAM_PENALTY_INCLUDES_BASE_RATE: "True",
    loan.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "True",
    loan.PARAM_ACCRUE_ON_DUE_PRINCIPAL: "False",
    loan.early_repayment.PARAM_EARLY_REPAYMENT_FLAT_FEE: "0",
    loan.early_repayment.PARAM_EARLY_REPAYMENT_FEE_RATE: "0",
    loan.overdue.PARAM_REPAYMENT_PERIOD: "10",
    loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0.05",
    loan.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_term",
    loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.032",
    loan.variable_rate.PARAM_ANNUAL_INTEREST_RATE_CAP: "1.00",
    loan.variable_rate.PARAM_ANNUAL_INTEREST_RATE_FLOOR: "0.00",
}

loan_2_instance_params = {
    **parameters.loan_instance_params,
    loan.PARAM_FIXED_RATE_LOAN: "True",
    loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: "False",
    loan.disbursement.PARAM_PRINCIPAL: "300000",
    loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20",
    loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
    loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "120",
    loan.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "0.00",
}

loan_2_template_params = {
    **parameters.loan_template_params,
    loan.PARAM_AMORTISATION_METHOD: "declining_principal",
    loan.PARAM_LATE_REPAYMENT_FEE: "15",
    loan.PARAM_PENALTY_INCLUDES_BASE_RATE: "True",
    loan.PARAM_GRACE_PERIOD: "5",
    loan.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "True",
    loan.PARAM_ACCRUE_ON_DUE_PRINCIPAL: "False",
    loan.early_repayment.PARAM_EARLY_REPAYMENT_FLAT_FEE: "0",
    loan.early_repayment.PARAM_EARLY_REPAYMENT_FEE_RATE: "0",
    loan.overdue.PARAM_REPAYMENT_PERIOD: "10",
    loan.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_term",
    loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.189965",
    loan.variable_rate.PARAM_ANNUAL_INTEREST_RATE_CAP: "1.00",
    loan.variable_rate.PARAM_ANNUAL_INTEREST_RATE_FLOOR: "0.00",
}


class LoanTest(LoanTestBase):
    def test_post_due_amount_calculation_schedules(self):
        """
        Check overdue and check delinquency both depend on repayment day schedule
        this test case ensures both events can be scheduled correctly
        """
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=1, day=10, minute=1, tzinfo=ZoneInfo("UTC"))

        # overpayment: 10,526.32, fee: 526.32, overpayment - fee: 10,000
        repayment_with_overpayment = str(Decimal(loan_2_EMI) + Decimal("10000") + Decimal("526.32"))

        sub_tests = [
            SubTest(
                description="check overdue, missing repayment triggers delinquency schedule",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=3,
                                day=1,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            )
                        ],
                        event_id=loan.overdue.CHECK_OVERDUE_EVENT,
                        account_id=self.loan_account_id,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=3,
                                day=6,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            )
                        ],
                        event_id=loan.CHECK_DELINQUENCY,
                        account_id=self.loan_account_id,
                    ),
                ],
            ),
            SubTest(
                description="check overdue scheduled, "
                "check delinquency not scheduled if due and overdue repaid",
                events=self.create_deposit_events(
                    num_payments=2,
                    repayment_amount=repayment_with_overpayment,
                    repayment_day=int(
                        loan_2_instance_params[
                            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
                        ]
                    ),
                    repayment_hour=payment_hour,
                    start_year=start_year,
                    start_month=3,
                ),
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=3,
                                day=30,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=4,
                                day=30,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=5,
                                day=30,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.overdue.CHECK_OVERDUE_EVENT,
                        account_id=self.loan_account_id,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=6,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            )
                        ],
                        event_id=loan.CHECK_DELINQUENCY,
                        account_id=self.loan_account_id,
                    ),
                ],
            ),
            SubTest(
                description="repayment day change updates check overdue and delinquency schedule",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=datetime(year=2020, month=6, day=15, tzinfo=ZoneInfo("UTC")),
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "25"},
                    )
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=7,
                                day=5,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=8,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=9,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=10,
                                day=5,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=11,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=12,
                                day=5,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2021,
                                month=1,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.overdue.CHECK_OVERDUE_EVENT,
                        account_id=self.loan_account_id,
                        count=11,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=7,
                                day=10,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=8,
                                day=9,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=9,
                                day=9,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=10,
                                day=10,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=11,
                                day=9,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=12,
                                day=10,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2021,
                                month=1,
                                day=9,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.CHECK_DELINQUENCY,
                        account_id=self.loan_account_id,
                        count=9,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=loan_2_template_params,
            instance_params=loan_2_instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_monthly_rest_interest_accrual_with_repayment_day_change(self):
        # Change repayment day after 1st repayment and ensure interest accrual continues until
        # the new repayment day. Ensure that overpayments aren't included in interest accrual
        # until the following repayment day.
        # Daily interest for 1st repayment period = 25.47945 (Remaining principal 300000)
        # Total interest for 1st repayment period = 32 days = 815.3424
        # Daily interest for 2nd repayment period = 21.26508 (Remaining principal 250379.17 )
        # Total interest for 2nd repayment period = 35 days = 744.2778

        start = default_simulation_start_date
        end = start + relativedelta(months=3, days=8, minutes=2)
        first_due_amount_calculation_datetime = start + relativedelta(months=1, days=1, minutes=1)
        second_due_amount_calculation_datetime = start + relativedelta(months=2, days=7, minutes=1)
        overdue_datetime = start + relativedelta(months=2, days=17, minutes=2)

        instance_params = {
            **loan_1_instance_params,
            loan.PARAM_INTEREST_ACCRUAL_REST_TYPE: "monthly",
        }

        sub_tests = [
            SubTest(
                description="5 days interest accrual on full starting principal with overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        # fee = 50000*0.05 = 2500
                        amount="50000",
                        event_datetime=start + relativedelta(days=2),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "300000"),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, "300000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.47945"),
                            (dimensions.EMI, "2910.69"),
                        ]
                    },
                    start
                    + relativedelta(days=5, seconds=1): {
                        # 25.47945 * 5 = 127.39725
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "252500"),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, "300000"),
                            (dimensions.OVERPAYMENT, "47500"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "127.39725"),
                        ]
                    },
                },
            ),
            SubTest(
                description="First due amount calculation event",
                expected_balances_at_ts={
                    first_due_amount_calculation_datetime: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "250379.17"),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, "250379.17"),
                            (dimensions.OVERPAYMENT, "47500"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            # total interest due = round(815.3424,2) but emi interest is
                            # 815.34 * 31/32 = 789.86
                            (dimensions.INTEREST_DUE, "815.34"),
                            (dimensions.EMI, "2910.69"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Second due amount calculation event",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        # fee = (50000 - 2936.17)*0.05 = 2353.19
                        amount="50000",
                        event_datetime=start + relativedelta(months=1, days=3),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(months=1, days=3),
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "18"},
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        # fee = 50000*0.05 = 2500
                        amount="50000",
                        event_datetime=start + relativedelta(months=1, days=4),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, days=4): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "158168.53"),
                            (dimensions.PENALTIES, "0"),
                            # 2*47500 + 50000 - (50000-2936.17)*0.05
                            (dimensions.OVERPAYMENT, "139710.64"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "2910.69"),
                        ]
                    },
                    second_due_amount_calculation_datetime: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "155874.53"),
                            (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, "155874.53"),
                            (dimensions.OVERPAYMENT, "139710.64"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.PRINCIPAL_DUE, "2294.00"),
                            # total interest due = round(744.2778,2) but emi interest is
                            # 744.28 * 29/35 = 616.69
                            (dimensions.INTEREST_DUE, "744.28"),
                            (dimensions.EMI, "2910.69"),
                        ]
                    },
                },
            ),
            SubTest(
                description="penalty fee and 4 days penalty accrual on current overdue balances",
                expected_balances_at_ts={
                    overdue_datetime: {
                        self.loan_account_id: [
                            (dimensions.INTEREST_OVERDUE, Decimal("744.28")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("2294.00")),
                            (dimensions.PENALTIES, "15"),
                        ]
                    },
                    overdue_datetime
                    + relativedelta(days=1): {
                        self.loan_account_id: [
                            (dimensions.PENALTIES, "17.26"),
                        ]
                    },
                    overdue_datetime
                    + relativedelta(days=2): {
                        self.loan_account_id: [(dimensions.PENALTIES, "19.52")]
                    },
                    overdue_datetime
                    + relativedelta(days=3): {
                        self.loan_account_id: [(dimensions.PENALTIES, "21.78")]
                    },
                    overdue_datetime
                    + relativedelta(days=4): {
                        self.loan_account_id: [(dimensions.PENALTIES, "24.04")]
                    },
                },
            ),
            SubTest(
                description="Subsequent Interest Accruals",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=3, days=7, minutes=2): {
                        self.loan_account_id: [(dimensions.INTEREST_DUE, "410.40")]
                    },
                    start
                    + relativedelta(months=3, days=8, minutes=2): {
                        self.loan_account_id: [(dimensions.ACCRUED_INTEREST_RECEIVABLE, "13.02630")]
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=loan_1_template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_regular_events(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=ZoneInfo("UTC"))

        first_repayment_time = datetime(
            year=2021, month=2, day=12, hour=0, minute=1, second=0, tzinfo=ZoneInfo("UTC")
        )
        before_first_repayment = first_repayment_time - relativedelta(seconds=1)
        after_first_repayment = first_repayment_time + relativedelta(minutes=1)
        after_first_deposit = first_repayment_time + relativedelta(hours=2)

        second_repayment_time = datetime(
            year=2021, month=3, day=12, hour=0, minute=1, second=0, tzinfo=ZoneInfo("UTC")
        )
        before_second_repayment = second_repayment_time - relativedelta(seconds=1)
        after_second_repayment = second_repayment_time + relativedelta(minutes=1)
        after_second_deposit = second_repayment_time + relativedelta(hours=2)

        third_overdue_check = datetime(
            year=2021, month=4, day=12, hour=0, minute=0, second=2, tzinfo=ZoneInfo("UTC")
        )
        after_third_overdue_check = third_overdue_check + relativedelta(seconds=10)
        third_repayment_time = datetime(
            year=2021, month=4, day=12, hour=0, minute=1, second=0, tzinfo=ZoneInfo("UTC")
        )
        after_third_repayment = third_repayment_time + relativedelta(minutes=1)
        after_third_deposit = third_repayment_time + relativedelta(hours=2)

        fourth_repayment_time = datetime(
            year=2021, month=5, day=12, hour=0, minute=1, second=0, tzinfo=ZoneInfo("UTC")
        )
        before_fourth_repayment = fourth_repayment_time - relativedelta(seconds=1)
        after_fourth_repayment = fourth_repayment_time + relativedelta(minutes=1)

        end = datetime(year=2021, month=5, day=31, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **loan_1_instance_params,
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "10",
            loan.disbursement.PARAM_PRINCIPAL: "1000",
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.01",
            loan.PARAM_FIXED_RATE_LOAN: "True",
        }
        template_params = {
            **loan_1_template_params,
            loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0",
            loan.interest_capitalisation.PARAM_CAPITALISE_PENALTY_INTEREST: "True",
        }

        sub_tests = [
            SubTest(
                description="activation",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "1000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="first scheduled repayment with overpayment",
                events=self.create_deposit_events(
                    num_payments=1,
                    repayment_amount="101",
                    repayment_day=12,
                    repayment_hour=1,
                    start_year=2021,
                    start_month=2,
                ),
                expected_balances_at_ts={
                    # accrued_interest = daily_interest_rate * days_since_start_of_loan * principal
                    #                  = 0.01 / 365 * 42 * 1000
                    before_first_repayment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "1.1508"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "1.1508"),
                        ]
                    },
                    # EMI and principal_due get calculated according to formula
                    # accrued_interest gets transferred to interest_due
                    after_first_repayment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "900.39"),
                            (dimensions.PRINCIPAL_DUE, "99.61"),
                            (dimensions.INTEREST_DUE, "1.15"),
                            (dimensions.EMI, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ]
                    },
                    # deposit of 101 repays the principal_due, interest_due and the remainder gets
                    # put in the overpayment address, after the overpayment fee of 5% is also paid
                    after_first_deposit: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "900.16"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "0.23"),
                        ]
                    },
                },
            ),
            SubTest(
                description="second scheduled repayment with underpayment sets overdue addresses",
                events=self.create_deposit_events(
                    num_payments=1,
                    repayment_amount="50",
                    repayment_day=12,
                    repayment_hour=1,
                    start_year=2021,
                    start_month=3,
                ),
                expected_balances_at_ts={
                    # accrued_interest = 0.01 / 365 * 28 * 900.39
                    before_second_repayment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "900.16"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.69076"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.69048"),
                            (dimensions.OVERPAYMENT, "0.23"),
                        ]
                    },
                    after_second_repayment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "800.39"),
                            (dimensions.PRINCIPAL_DUE, "99.77"),
                            (dimensions.INTEREST_DUE, "0.69"),
                            (dimensions.EMI, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "0.23"),
                        ]
                    },
                    # deposit of 50 only covers part of the principal_due
                    after_second_deposit: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "800.39"),
                            (dimensions.PRINCIPAL_DUE, "49.77"),
                            (dimensions.INTEREST_DUE, "0.69"),
                            (dimensions.EMI, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "0.23"),
                        ]
                    },
                    # the amounts left in the _due addresses get transferred to _overdue addresses
                    # a late repayment fee of 15 gets incurred in PENALTIES
                    after_third_overdue_check: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "800.39"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "49.77"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0.69"),
                            (dimensions.EMI, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.67983"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.67983"),
                            (dimensions.OVERPAYMENT, "0.23"),
                            (dimensions.PENALTIES, "15"),
                        ]
                    },
                },
            ),
            SubTest(
                description="capitalisation and large overpayment",
                events=self.create_deposit_events(
                    num_payments=1,
                    repayment_amount="500",
                    repayment_day=12,
                    repayment_hour=1,
                    start_year=2021,
                    start_month=4,
                ),
                expected_balances_at_ts={
                    # on the next scheduled repayment day, we can see interest from the penalties
                    # being accrued daily and transferred to CAPITALISED_INTEREST_TRACKER (0.73)
                    after_third_repayment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "701.34"),
                            (dimensions.PRINCIPAL_DUE, "99.78"),
                            (dimensions.PRINCIPAL_OVERDUE, "49.77"),
                            (dimensions.INTEREST_DUE, "0.68"),
                            (dimensions.INTEREST_OVERDUE, "0.69"),
                            (dimensions.EMI, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "0.23"),
                            (dimensions.PENALTIES, "15"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0.73"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ]
                    },
                    # third deposit of 500 pays off all overdue and due balances and also
                    # adds 317.38 to the overpayment balance
                    after_third_deposit: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "383.96"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "317.61"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0.73"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ]
                    },
                    # accrued expected interest is higher than the accrued interest, because the
                    # expected principal (700.84) is higher that the calculated one (700.84-317.61)
                    # due to the overpayment
                    before_fourth_repayment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "383.96"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.5766"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.3156"),
                            (dimensions.OVERPAYMENT, "317.61"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0.73"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ]
                    },
                    # the previous overpayment also resulted in 0.26 being stored in the
                    # EMI_PRINCIPAL_EXCESS balance since accrued expected interest was higher
                    # than the accrued interest
                    after_fourth_repayment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "283.82"),
                            (dimensions.PRINCIPAL_DUE, "100.14"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0.32"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI, "100.46"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.OVERPAYMENT, "317.61"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0.73"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0.26"),
                        ]
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_daily_interest_accrual(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=3, seconds=1)

        events = []
        events.append(
            create_inbound_hard_settlement_instruction(
                target_account_id=self.loan_account_id,
                # overpayment: 105,263.16, fee: 5,263.16, overpayment - fee: 100,000
                amount=str(Decimal("100000") + Decimal("5263.16")),
                event_datetime=start + relativedelta(days=2),
                internal_account_id=accounts.DEPOSIT,
            )
        )
        events.append(
            create_inbound_hard_settlement_instruction(
                target_account_id=self.loan_account_id,
                # overpayment: 105,263.16, fee: 5,263.16, overpayment - fee: 100,000
                amount=str(Decimal("100000") + Decimal("5263.16")),
                event_datetime=start + relativedelta(days=3),
                internal_account_id=accounts.DEPOSIT,
            )
        )
        sub_tests = [SubTest(description="Deposit events", events=events)]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=loan_1_template_params,
            instance_params=loan_1_instance_params,
        )
        res = self.run_test_scenario(test_scenario)

        expected_balances = {
            self.loan_account_id: {
                start
                + relativedelta(days=1, seconds=1): [
                    (dimensions.ACCRUED_INTEREST_RECEIVABLE, "25.47945"),
                    (dimensions.OVERPAYMENT, "0"),
                ],
                start
                + relativedelta(days=2, seconds=1): [
                    (dimensions.ACCRUED_INTEREST_RECEIVABLE, "42.46575"),
                    (dimensions.OVERPAYMENT, "100000"),
                ],
                start
                + relativedelta(days=3, seconds=1): [
                    (dimensions.ACCRUED_INTEREST_RECEIVABLE, "50.95890"),
                    (dimensions.OVERPAYMENT, "200000"),
                ],
            },
            accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: {
                start
                + relativedelta(days=1, seconds=1): [
                    (dimensions.DEFAULT, "0"),
                ],
                start
                + relativedelta(days=2, seconds=1): [
                    (dimensions.DEFAULT, "5263.16"),
                ],
                start
                + relativedelta(days=3, seconds=1): [
                    (dimensions.DEFAULT, "10526.32"),
                ],
            },
        }
        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

        schedules = get_processed_scheduled_events(
            res, event_id=loan.interest_accrual.ACCRUAL_EVENT, account_id=self.loan_account_id
        )
        self.assertEqual(len(schedules), 3)
        self.assertEqual("2020-01-12T00:00:01Z", schedules[0])
        self.assertEqual("2020-01-13T00:00:01Z", schedules[1])
        self.assertEqual("2020-01-14T00:00:01Z", schedules[2])

    def test_daily_penalty_accrual(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=19, minute=1, tzinfo=ZoneInfo("UTC"))

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=[],
            template_params=loan_2_template_params,
            instance_params=loan_2_instance_params,
        )
        res = self.run_test_scenario(test_scenario)

        principal_overdues = [
            posting
            for posting in get_postings(res, self.loan_account_id, dimensions.PRINCIPAL_OVERDUE)
            if posting["credit"]
        ]
        interest_overdues = [
            posting
            for posting in get_postings(res, self.loan_account_id, dimensions.INTEREST_OVERDUE)
            if posting["credit"]
        ]
        penalties = [
            posting
            for posting in get_postings(res, self.loan_account_id, dimensions.PENALTIES)
            if posting["credit"]
        ]

        for index, amount_due in enumerate(zip(principal_overdues, interest_overdues)):
            self.assertEquals(
                Decimal(self.expected_output["late_payment"]["overdue"][index][0]),
                Decimal(amount_due[0]["amount"]),
            )
            self.assertEquals(
                Decimal(self.expected_output["late_payment"]["overdue"][index][1]),
                Decimal(amount_due[1]["amount"]),
            )

        for index, amount_due in enumerate(penalties):
            self.assertEquals(
                Decimal(self.expected_output["late_payment"]["penalties"][index]),
                Decimal(amount_due["amount"]),
            )

    def test_daily_penalty_accrual_without_interest_capitalisation(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=3, hour=5, tzinfo=ZoneInfo("UTC"))

        repayment_date = datetime(year=2020, month=2, day=12, minute=1, tzinfo=ZoneInfo("UTC"))
        overdue_repayment_date = datetime(
            year=2020, month=2, day=22, second=2, tzinfo=ZoneInfo("UTC")
        )

        template_params = {
            **loan_1_template_params,
            loan.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "False",
        }

        sub_tests = [
            SubTest(
                description="first EMI due",
                expected_balances_at_ts={
                    repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            (dimensions.INTEREST_DUE, "815.34"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ]
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=repayment_date,
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": "2936.17",
                            "overdue_date": "2020-02-22",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="first EMI overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=2, day=22, hour=1, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            (dimensions.PENALTIES, "15"),
                        ]
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_repayment_date,
                        notification_type=loan.REPAYMENT_OVERDUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": "2936.17",
                            "overdue_date": str(overdue_repayment_date.date()),
                            loan.PARAM_LATE_REPAYMENT_FEE: "15",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="penalty accrual on overdue principal",
                expected_balances_at_ts={
                    datetime(year=2020, month=2, day=27, hour=1, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            # penalty rate (0.24 + 0.032 - 0.001)
                            # overdue principal 2120.83
                            # number of days 5
                            # 15 + (0.24 + 0.032 - 0.001)/365 * 2120.83 * 5 = 22.85
                            (dimensions.PENALTIES, "22.85"),
                        ]
                    }
                },
            ),
            SubTest(
                description="penalty accrual on overdue principal and interest",
                events=[
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2020, month=2, day=27, hour=10, tzinfo=ZoneInfo("UTC")
                        ),
                        **{loan.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "True"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(year=2020, month=3, day=3, hour=1, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            # penalty rate (0.24 + 0.032 - 0.001)
                            # total overdue 2120.83 + 815.34 = 2936.17
                            # overdue interest 815.34
                            # number of days 5
                            # 22.85 + (0.24 + 0.032 - 0.001)/365 * 2936.17 * 5 = 33.75
                            (dimensions.PENALTIES, "33.75"),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=loan_1_instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_daily_penalty_accrual_without_penalty_compounding_interest(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=3, hour=5, tzinfo=ZoneInfo("UTC"))

        repayment_date = datetime(year=2020, month=2, day=12, minute=1, tzinfo=ZoneInfo("UTC"))
        overdue_repayment_date = datetime(
            year=2020, month=2, day=22, second=2, tzinfo=ZoneInfo("UTC")
        )

        template_params = {
            **loan_1_template_params,
            loan.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "False",
        }

        sub_tests = [
            SubTest(
                description="first EMI due",
                expected_balances_at_ts={
                    repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            (dimensions.INTEREST_DUE, "815.34"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ]
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=repayment_date,
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": "2936.17",
                            "overdue_date": "2020-02-22",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="first EMI overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=2, day=22, hour=1, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "252.9932"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            (dimensions.PENALTIES, "15"),
                        ]
                    }
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_repayment_date,
                        notification_type=loan.REPAYMENT_OVERDUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": "2936.17",
                            "overdue_date": str(overdue_repayment_date.date()),
                            loan.PARAM_LATE_REPAYMENT_FEE: "15",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="penalty accrual on overdue principal",
                expected_balances_at_ts={
                    datetime(year=2020, month=2, day=27, hour=1, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "379.4898"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            # penalty rate (0.24 + 0.032 - 0.001)
                            # overdue principal 2120.83
                            # number of days 5
                            # 15 + (0.24 + 0.032 - 0.001)/365 * 2120.83 * 5 = 22.85
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PENALTIES, "22.85"),
                        ]
                    }
                },
            ),
            SubTest(
                description="penalty accrual on overdue principal and interest",
                events=[
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2020, month=2, day=27, hour=10, tzinfo=ZoneInfo("UTC")
                        ),
                        **{loan.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "True"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(year=2020, month=3, day=3, hour=1, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "505.9864"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            # penalty rate (0.24 + 0.032 - 0.001)
                            # total overdue 2120.83 + 815.34 = 2936.17
                            # overdue interest 815.34
                            # number of days 5
                            # 22.85 + (0.24 + 0.032 - 0.001)/365 * 2936.17 * 5 = 33.75
                            (dimensions.PENALTIES, "33.75"),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=loan_1_instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_zero_interest_rate(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2)

        template_params = {
            **loan_1_template_params,
            loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.001",
        }

        sub_tests = [
            SubTest(
                description="0 interest accrual",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="120",
                    ),
                ],
                expected_balances_at_ts={
                    datetime(year=2020, month=2, day=12, hour=1, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            # 300000/120 = 2500
                            (dimensions.PRINCIPAL_DUE, "2500"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ]
                    }
                },
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=loan_1_instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_change_repayment_day_scenarios(self):
        """
        There are 6 scenarios relating to a repayment day change
        after the first repayment date
        3 where the repayment day change request occurs after the months repayment day
        and 3 where the repayment day change request occurs before the current months repayment day

        scenarios:
            after repayment day has passed:
                1. old_repayment_day < change_day < new_repayment_day
                    (e.g. on 15th change from 12th to 20th)
                2. old repayment_day < new_repayment_day < change_day
                    e.g. on 23rd change from 20th to 21st)
                3. new_repayment_day < old_repayment_day < change_day
                    (e.g. on 23rd change from 21st to 12th)

            before repayment day:
                1. change_day < old_repayment_day < new_repayment_day
                    (e.g. on 9th change from 12th to 15th)
                2. change_day < new_repayment_day < old repayment_day
                    (e.g. on 9th change from 15th to 13th)
                3. new_repayment_day < change_day < old_repayment day
                    (e.g. on 9th change from 13th to 5th)

        """
        start = default_simulation_start_date
        end = start + relativedelta(months=9)
        instance_params = {
            **loan_2_instance_params,
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "12",
        }

        first_param_change = datetime(2020, 2, 15, 10, tzinfo=ZoneInfo("UTC"))
        second_param_change = datetime(2020, 3, 23, 10, tzinfo=ZoneInfo("UTC"))
        third_param_change = datetime(2020, 4, 23, 10, tzinfo=ZoneInfo("UTC"))
        fourth_param_change = datetime(2020, 6, 9, 10, tzinfo=ZoneInfo("UTC"))
        fifth_param_change = datetime(2020, 7, 9, 10, tzinfo=ZoneInfo("UTC"))
        sixth_param_change = datetime(2020, 8, 9, 10, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Change repayment day after current months repayment day event",
                events=[
                    # After payment day - scenario 1
                    # expect next schedule 20/03/20
                    create_instance_parameter_change_event(
                        timestamp=first_param_change,
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20"},
                    ),
                    # After payment day - scenario 2
                    # expect next schedule 21/04/20
                    create_instance_parameter_change_event(
                        timestamp=second_param_change,
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "21"},
                    ),
                    # After payment day - scenario 3
                    # expect next schedule 12/05/20
                    create_instance_parameter_change_event(
                        timestamp=third_param_change,
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "12"},
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=2,
                                day=12,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=3,
                                day=20,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=4,
                                day=21,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=5,
                                day=12,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=self.loan_account_id,
                        count=9,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-02-12",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="120",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_param_change + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-03-20",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=first_param_change + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="119",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_param_change + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-04-21",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_param_change + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="118",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_param_change + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-05-12",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_param_change + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="117",
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2020, 2, 12, 10, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "297879.17"),
                            (dimensions.INTEREST_DUE, "815.34"),
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            (dimensions.EMI, "2910.69"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                    },
                    datetime(2020, 3, 20, 10, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "295702.16"),
                            # the 8 extra days are counted as 'non-emi' interest
                            # so of the 936.07 interest due, only 733.68 is deducted from emi to
                            # determine the principal due
                            (dimensions.INTEREST_DUE, "936.07"),
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.EMI, "2910.69"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                    },
                    datetime(2020, 4, 21, 10, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "293570.02"),
                            (dimensions.INTEREST_DUE, "803.66"),
                            # the extra day is counted as 'non-emi' interest
                            # so of the 803.66 interest due, only 778.55 is deducted from emi to
                            # determine the principal due
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.EMI, "2910.69"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Change repayment day before current months repayment day event",
                events=[
                    # Before payment day - scenario 1
                    # on 09/06/20 change from 12th to 15th
                    # expect next schedule 15/06/20
                    create_instance_parameter_change_event(
                        timestamp=fourth_param_change,
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "15"},
                    ),
                    #  Before payment day - scenario 2
                    # on 09/07/20 change from 15th to 13th
                    # expect next schedule 13/07/20
                    create_instance_parameter_change_event(
                        timestamp=fifth_param_change,
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "13"},
                    ),
                    # Before payment day - scenario 3
                    # on 09/08/20 change from 13th to 5th
                    # expect next schedule 13/08/20
                    # and the subsequent on 05/09/20
                    create_instance_parameter_change_event(
                        timestamp=sixth_param_change,
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "5"},
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=6,
                                day=15,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=7,
                                day=13,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=8,
                                day=13,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=9,
                                day=5,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=10,
                                day=5,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=self.loan_account_id,
                        count=9,
                    )
                ],
                expected_balances_at_ts={
                    datetime(2020, 5, 12, 10, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "291182.93"),
                            (dimensions.INTEREST_DUE, "523.60"),
                            (dimensions.PRINCIPAL_DUE, "2387.09"),
                            (dimensions.EMI, "2910.69"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                    },
                    datetime(2020, 6, 15, 10, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "289038.89"),
                            (dimensions.INTEREST_DUE, "840.84"),
                            # total days between events is 34, therefore 31/34 days are emi interest
                            # the other 3 are non-emi interest
                            (dimensions.PRINCIPAL_DUE, "2144.04"),
                            (dimensions.EMI, "2910.69"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                    },
                    datetime(2020, 7, 13, 10, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "286815.56"),
                            (dimensions.INTEREST_DUE, "687.36"),
                            (dimensions.PRINCIPAL_DUE, "2223.33"),
                            (dimensions.EMI, "2910.69"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fourth_param_change + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-06-15",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_param_change + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="116",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fifth_param_change + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-07-13",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fifth_param_change + relativedelta(hours=1),  # 09/07/2020
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="115",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_param_change + relativedelta(hours=1),  # 09/08/2020
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-08-13",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_param_change + relativedelta(hours=1),  # 09/08/2020,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="114",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_param_change + relativedelta(months=1, day=3, hours=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-09-05",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=datetime(2020, 8, 14, 10, tzinfo=ZoneInfo("UTC")),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="113",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_param_change + relativedelta(months=2, day=3, hours=1),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-10-05",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_param_change + relativedelta(months=2, day=3, hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="112",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=loan_2_template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_post_repayment_day_schedules(self):
        """
        Check overdue and check delinquency both depend on repayment day schedule
        this test case ensures both events can be scheduled correctly
        """
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=1, day=10, minute=1, tzinfo=ZoneInfo("UTC"))

        # overpayment: 10,526.32, fee: 526.32, overpayment - fee: 10,000
        repayment_with_overpayment = str(Decimal(loan_2_EMI) + Decimal("10000") + Decimal("526.32"))

        sub_tests = [
            SubTest(
                description="check overdue, missing repayment triggers delinquency schedule",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=3,
                                day=1,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            )
                        ],
                        event_id=loan.overdue.CHECK_OVERDUE_EVENT,
                        account_id=self.loan_account_id,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=3,
                                day=6,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            )
                        ],
                        event_id=loan.CHECK_DELINQUENCY,
                        account_id=self.loan_account_id,
                    ),
                ],
            ),
            SubTest(
                description="check overdue scheduled, "
                "check delinquency not scheduled if due and overdue repaid",
                events=self.create_deposit_events(
                    num_payments=2,
                    repayment_amount=repayment_with_overpayment,
                    repayment_day=int(
                        loan_2_instance_params[
                            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
                        ]
                    ),
                    repayment_hour=payment_hour,
                    start_year=start_year,
                    start_month=3,
                ),
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=3,
                                day=30,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=4,
                                day=30,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=5,
                                day=30,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.overdue.CHECK_OVERDUE_EVENT,
                        account_id=self.loan_account_id,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=6,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            )
                        ],
                        event_id=loan.CHECK_DELINQUENCY,
                        account_id=self.loan_account_id,
                    ),
                ],
            ),
            SubTest(
                description="repayment day change updates check overdue and delinquency schedule",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=datetime(year=2020, month=6, day=15, tzinfo=ZoneInfo("UTC")),
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "25"},
                    )
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=7,
                                day=5,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=8,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=9,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=10,
                                day=5,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=11,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=12,
                                day=5,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2021,
                                month=1,
                                day=4,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.overdue.CHECK_OVERDUE_EVENT,
                        account_id=self.loan_account_id,
                        count=11,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=7,
                                day=10,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=8,
                                day=9,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=9,
                                day=9,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=10,
                                day=10,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=11,
                                day=9,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=12,
                                day=10,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2021,
                                month=1,
                                day=9,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.CHECK_DELINQUENCY,
                        account_id=self.loan_account_id,
                        count=9,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=loan_2_template_params,
            instance_params=loan_2_instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_capitalised_penalty_interest_and_fees(self):
        start = datetime(year=2021, month=1, day=19, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2021, month=7, day=21, hour=2, minute=1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **loan_2_instance_params,
            loan.disbursement.PARAM_PRINCIPAL: "800000",
            loan.PARAM_FIXED_RATE_LOAN: "False",
            loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: "True",
        }
        template_params = {
            **loan_2_template_params,
            loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.02",
            loan.PARAM_PENALTY_INTEREST_RATE: "0.02",
            loan.PARAM_ACCRUE_ON_DUE_PRINCIPAL: "True",
            loan.PARAM_PENALTY_INCLUDES_BASE_RATE: "False",
            loan.PARAM_LATE_REPAYMENT_FEE: "50",
            loan.overdue.PARAM_REPAYMENT_PERIOD: "1",
            loan.interest_capitalisation.PARAM_CAPITALISE_PENALTY_INTEREST: "True",
            loan.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "True",
        }

        first_repayment_date = datetime(
            year=2021, month=2, day=20, hour=0, minute=1, second=0, tzinfo=ZoneInfo("UTC")
        )
        sub_tests = [
            SubTest(
                description="repayment events before going into overdue",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_repayment_date],
                        event_id=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=self.loan_account_id,
                    ),
                ],
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount=str(Decimal("6002.18") + Decimal("1402.74")),
                        event_datetime=first_repayment_date + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount=str(Decimal("6142.89") + Decimal("1218.19")),
                        event_datetime=first_repayment_date + relativedelta(months=1, hours=1),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount=str(Decimal("6022.81") + Decimal("1338.27")),
                        event_datetime=first_repayment_date + relativedelta(months=2, hours=1),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2021,
                            month=4,
                            day=20,
                            hour=3,
                            tzinfo=ZoneInfo("UTC"),
                        ),
                        **{loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.021"},
                    ),
                ],
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=1, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "787854.93"),
                            (dimensions.PRINCIPAL_DUE, "6142.89"),
                            (dimensions.INTEREST_DUE, "1218.19"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI, "7361.08"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ]
                    },
                    first_repayment_date
                    + relativedelta(months=2, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "781832.12"),
                            (dimensions.PRINCIPAL_DUE, "6022.81"),
                            (dimensions.INTEREST_DUE, "1338.27"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI, "7361.08"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                        ]
                    },
                    first_repayment_date
                    + relativedelta(months=3, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "775786"),
                            (dimensions.PRINCIPAL_DUE, "6046.12"),
                            (dimensions.INTEREST_DUE, "1349.46"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI, "7395.58"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="overdue fees capitalisation day 1",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=3, days=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "775836"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "6046.12"),
                            (dimensions.INTEREST_OVERDUE, "1349.46"),
                            # amounts are transferred to overdue after accrual
                            # principal 781,832.12 * rate 0.021 / 365 = 44.98209
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "44.98209"),
                            (dimensions.EMI, "7395.58"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, "50"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0",
                            ),
                        ]
                    },
                },
            ),
            SubTest(
                description="overdue fees capitalisation day 2",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=3, days=2, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "775836"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "6046.12"),
                            (dimensions.INTEREST_OVERDUE, "1349.46"),
                            # accrual now excludes the overdue principal
                            # 44.98209 + (principal 775,836.00 * rate 0.021 / 365) = 89.61919
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "89.61919"),
                            (dimensions.EMI, "7395.58"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, "50"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0.40524",
                            ),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-0.40524")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                },
            ),
            SubTest(
                description="overdue fees capitalisation day 3",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=3, days=3, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "775836"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "6046.12"),
                            (dimensions.INTEREST_OVERDUE, "1349.46"),
                            # accrual now excludes the overdue principal
                            # 89.61919 + (principal 775,836.00 * rate 0.021 / 365) = 134.25629
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "134.25629"),
                            (dimensions.EMI, "7395.58"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, "50"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0.81048",
                            ),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-0.81048")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                },
            ),
            SubTest(
                description="overdue repayment received on day 3 overdue",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount=str(Decimal("6046.12") + Decimal("1349.46")),
                        event_datetime=first_repayment_date
                        + relativedelta(months=3, days=3, hours=11),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=3, days=3, hours=12): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "775836"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "134.25629"),
                            (dimensions.EMI, "7395.58"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, "50"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0.81048",
                            ),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-0.81048")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                },
            ),
            SubTest(
                description="repayment event after overdue fees and capitalisation",
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=4, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "769825.33"),
                            (dimensions.PRINCIPAL_DUE, "6011.48"),
                            (dimensions.INTEREST_DUE, "1384.1"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "7395.58"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0.81"),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, "50"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0",
                            ),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0.81")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(months=4, hours=2),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="769825.33",
                    ),
                ],
            ),
            SubTest(
                description="change rate after overdue fee capitalisations",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount=str(Decimal("6011.48") + Decimal("1384.1")),
                        event_datetime=first_repayment_date + relativedelta(months=4, hours=2),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2021,
                            month=6,
                            day=20,
                            hour=3,
                            tzinfo=ZoneInfo("UTC"),
                        ),
                        **{loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.02"},
                    ),
                ],
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(months=5, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "763729.11"),
                            (dimensions.PRINCIPAL_DUE, "6096.22"),
                            (dimensions.INTEREST_DUE, "1265.47"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "7361.69"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0.81"),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, "50"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0",
                            ),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0.81")
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_delinquency_with_backdated_repayments(self):
        """
        When a repayment is made before the grace period but vault received
        during the grace period, ensure repayment amount is applied to live overdue
        balances first, followed repayment hierarchy and
        CHECK_DELINQUENCY schedule has not instantiated the LOAN_MARK_DELINQUENT notification.
        Limitation: Penalties accrual not adjusted in retrospect by backdated payment
        """
        start = default_simulation_start_date
        end = datetime(year=2020, month=4, day=7, hour=2, minute=1, tzinfo=ZoneInfo("UTC"))

        first_repayment_date = datetime(
            year=2020, month=2, day=20, hour=0, minute=1, second=0, tzinfo=ZoneInfo("UTC")
        )
        first_grace_period_end = first_repayment_date + relativedelta(days=15, minute=0, second=2)

        second_repayment_date = datetime(
            year=2020, month=3, day=20, hour=0, minute=1, second=0, tzinfo=ZoneInfo("UTC")
        )
        second_grace_period_end = second_repayment_date + relativedelta(days=15, minute=0, second=2)

        before_first_repayment_date = first_repayment_date - relativedelta(hours=1)
        after_first_repayment_date = first_repayment_date + relativedelta(hours=1)

        sub_tests = [
            SubTest(
                description="late payment triggers check delinquency event",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_repayment_date],
                        event_id=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=self.loan_account_id,
                    ),
                    ExpectedSchedule(
                        run_times=[first_grace_period_end],
                        event_id=loan.CHECK_DELINQUENCY,
                        account_id=self.loan_account_id,
                    ),
                ],
                expected_balances_at_ts={
                    first_repayment_date
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            # EMI 2910.69 + Extra interest 229.32 = 3140.01 = 2120.83 + 1019.18
                            (dimensions.PRINCIPAL, "297879.17"),
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            (dimensions.INTEREST_DUE, "1019.18"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI, "2910.69"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="first transfer due reduces remaining term by 1 month on repayment day",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_repayment_date,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="120",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_first_repayment_date,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="119",
                    ),
                ],
            ),
            SubTest(
                description="backdated repayment after grace period triggers mark delinquency",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount=loan_2_first_month_payment,
                        event_datetime=first_grace_period_end + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT,
                        value_timestamp=first_grace_period_end - relativedelta(days=6),
                    )
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=first_grace_period_end,
                        notification_type=loan.MARK_DELINQUENT_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    first_grace_period_end: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            # penalty rate 0.24 + base rate 0.031 = 0.271
                            # 3140.01 * 0.271/365 * 5 + 15 fee = 26.65
                            # penalties not adjusted by backdating currently
                            (dimensions.PENALTIES, "26.65"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="backdated repayment during grace period avoids mark delinquency",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount=loan_2_first_month_payment,
                        event_datetime=second_grace_period_end - relativedelta(days=1),
                        internal_account_id=accounts.DEPOSIT,
                        value_timestamp=second_grace_period_end - relativedelta(days=2),
                    )
                ],
                expected_balances_at_ts={
                    second_repayment_date
                    + relativedelta(minutes=1): {
                        self.loan_account_id: [
                            # EMI 2910.69 = 2177.01 + 733.68
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.INTEREST_DUE, "733.68"),
                            (dimensions.PENALTIES, "26.65"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                    second_grace_period_end: {
                        self.loan_account_id: [
                            # customer second repayment pays off penalties
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=loan_2_template_params,
            instance_params=loan_2_instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_early_repayment(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=29, hour=3, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **loan_1_template_params,
            loan.overdue.PARAM_REPAYMENT_PERIOD: "29",
        }

        early_repayment_datetime = datetime(year=2020, month=3, day=28, tzinfo=ZoneInfo("UTC"))
        before_early_repayment = early_repayment_datetime - relativedelta(seconds=1)
        after_early_repayment = early_repayment_datetime + relativedelta(seconds=1)

        sub_tests = [
            SubTest(
                description="balances before early repayment",
                expected_balances_at_ts={
                    before_early_repayment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "295702.16"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "376.71645"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "376.71645"),
                            (dimensions.INTEREST_DUE, "733.68"),
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.EMI, "2910.69"),
                            (dimensions.PENALTIES, "47.7"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="118",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value=str(Decimal("301973.44") + Decimal("15563.27")),
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="301973.44",
                    ),
                ],
            ),
            SubTest(
                description="early repayment triggers close loan notification",
                events=[
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("301973.44") + Decimal("15563.27")),
                        early_repayment_datetime,
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    after_early_repayment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "401.83088"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.EMI, "2910.69"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OVERPAYMENT, "295702.16"),
                        ]
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=early_repayment_datetime,
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_early_repayment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                ],
            ),
            SubTest(
                description="back dated overpayment is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount=str(Decimal("301973.44") + Decimal("15563.27")),
                        event_datetime=early_repayment_datetime + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT,
                        value_timestamp=early_repayment_datetime - relativedelta(hours=1),
                    )
                ],
                expected_balances_at_ts={
                    early_repayment_datetime
                    + relativedelta(hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "401.83088"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.EMI, "2910.69"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OVERPAYMENT, "295702.16"),
                        ]
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=early_repayment_datetime + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot pay more than is owed",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=loan_1_instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_early_repayment_with_fees_capitalised(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=29, hour=3, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **loan_1_instance_params,
            loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: "True",
        }
        template_params = {
            **loan_1_template_params,
            loan.overdue.PARAM_REPAYMENT_PERIOD: "29",
            loan.interest_capitalisation.PARAM_CAPITALISE_PENALTY_INTEREST: "True",
        }

        early_repayment_datetime = datetime(year=2020, month=3, day=28, tzinfo=ZoneInfo("UTC"))
        before_early_repayment = early_repayment_datetime - relativedelta(seconds=1)
        after_early_repayment = early_repayment_datetime + relativedelta(seconds=1)

        sub_tests = [
            SubTest(
                description="before early repayment",
                expected_balances_at_ts={
                    before_early_repayment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "295717.16"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "376.7355"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "376.7355"),
                            (dimensions.INTEREST_DUE, "733.68"),
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.EMI, "2910.69"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "815.34"),
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, "15"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "32.70015",
                            ),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="118",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="317537.52",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="301973.46",
                    ),
                ],
            ),
            SubTest(
                description="early repayment triggers close loan notification",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "317537.52",
                        early_repayment_datetime,
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    after_early_repayment: {
                        self.loan_account_id: [
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "401.8512"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.EMI, "2910.69"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OVERPAYMENT, "295717.16"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "32.7"),
                            (dimensions.CAPITALISED_PENALTIES_TRACKER, "15"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0",
                            ),
                        ]
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=early_repayment_datetime,
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_early_repayment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)
