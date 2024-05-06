# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
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
)

min_repayment_instance_params = {
    **parameters.loan_instance_params,
    loan.PARAM_FIXED_RATE_LOAN: "True",
    loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: "False",
    loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: "0",
    loan.disbursement.PARAM_PRINCIPAL: "10000",
    loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20",
    loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
    loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "2",
}

min_repayment_template_params = {
    **parameters.loan_template_params,
    loan.PARAM_AMORTISATION_METHOD: "minimum_repayment_with_balloon_payment",
    loan.PARAM_GRACE_PERIOD: "5",
    loan.PARAM_LATE_REPAYMENT_FEE: "15",
    # loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "no_capitalisation",
    loan.PARAM_PENALTY_INCLUDES_BASE_RATE: "True",
    loan.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "True",
    loan.PARAM_ACCRUE_ON_DUE_PRINCIPAL: "False",
    loan.overdue.PARAM_REPAYMENT_PERIOD: "10",
}

default_simulation_start_date = datetime(year=2020, month=1, day=1, tzinfo=ZoneInfo("UTC"))


class LoanMinimumRepaymentTest(LoanTestBase):
    def test_min_repayment_balloon_loan_with_repayment_day_change(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=16)

        instance_params = {
            **min_repayment_instance_params,
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: "5",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
        }

        sub_tests = [
            SubTest(
                description="Change repayment day and check schedules",
                events=[
                    # this should change the balloon payment schedule from being
                    # run on 06/03/20 to 15/03/20
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(months=1, days=3),
                        account_id=self.loan_account_id,
                        **{loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "10"},
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=2,
                                day=1,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                            datetime(
                                year=2020,
                                month=3,
                                day=10,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=self.loan_account_id,
                        count=2,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=3,
                                day=15,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.balloon_payments.BALLOON_PAYMENT_EVENT,
                        account_id=self.loan_account_id,
                        count=1,
                    ),
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=min_repayment_template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_balloon_loan_overdue_balances_capitalise_penalty_interest(
        self,
    ):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        first_repayment_schedule = start + relativedelta(months=1, days=9, minutes=1)
        second_repayment_schedule = start + relativedelta(months=2, days=9, minutes=1)
        end = start + relativedelta(months=2, days=12)

        template_params = {
            **min_repayment_template_params,
            loan.overdue.PARAM_REPAYMENT_PERIOD: "1",
            loan.interest_capitalisation.PARAM_CAPITALISE_PENALTY_INTEREST: "True",
        }
        instance_params = {
            **min_repayment_instance_params,
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_AMOUNT: "5000",
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: "5",
        }

        sub_tests = [
            SubTest(
                description="due balances updated after first repayment date",
                expected_balances_at_ts={
                    first_repayment_schedule
                    - relativedelta(seconds=10): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "33.97280"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "33.97280"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-33.97280"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    first_repayment_schedule
                    + relativedelta(minutes=10): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "7503.72"),
                            (dimensions.PRINCIPAL_DUE, "2496.28"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.INTEREST_DUE, "33.97"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.EMI, "2522.61"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                },
            ),
            SubTest(
                description="due balances moved to overdue after missing payment "
                "and interest is accrued on overdue address",
                expected_balances_at_ts={
                    first_repayment_schedule
                    + relativedelta(days=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "7503.72"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2496.28"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "33.97"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0",
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.63730"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.63730"),
                            # late repayment fee of 15
                            (dimensions.PENALTIES, "15"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-0.63730"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "15")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                    first_repayment_schedule
                    + relativedelta(days=2): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "7503.72"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2496.28"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "33.97"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "1.87862",
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "1.27460"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "1.27460"),
                            (dimensions.PENALTIES, "15"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-1.27460"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "15")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-1.87862")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                },
            ),
            SubTest(
                description="overdue interest is capitalised after next repayment date",
                expected_balances_at_ts={
                    second_repayment_schedule
                    + relativedelta(minutes=10): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "5052.19"),
                            (dimensions.PRINCIPAL_DUE, "2504.13"),
                            (dimensions.PRINCIPAL_OVERDUE, "2496.28"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "52.60"),
                            (dimensions.INTEREST_DUE, "18.48"),
                            (dimensions.INTEREST_OVERDUE, "33.97"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "0",
                            ),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.PENALTIES, "15"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "52.45"),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "15")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "52.60")
                        ],
                    },
                    second_repayment_schedule
                    + relativedelta(days=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "5052.19"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "5000.41"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "52.60"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "52.45"),
                            (
                                dimensions.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                                "1.87862",
                            ),
                            # Interest calculation includes PRINCIPAL_CAPITALISED_INTEREST
                            # (4999.59+52.60)*ROUND(0.031/365,10)
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.42909"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.42909"),
                            (dimensions.PENALTIES, "30"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-0.42909"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "52.45"),
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "30")],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-1.87862")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "52.60")
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

    def test_min_repayment_predefined_emi_missed_repayment(self):
        start = default_simulation_start_date
        one_month_one_second_after_loan_start = start + relativedelta(months=1, seconds=1)
        one_month_one_minute_after_loan_start = start + relativedelta(months=1, minutes=1)
        two_month_one_second_after_loan_start = start + relativedelta(months=2, seconds=1)
        two_month_one_minute_after_loan_start = start + relativedelta(months=2, minutes=1)
        delinquency_notification = one_month_one_minute_after_loan_start + relativedelta(
            days=15, minute=0, second=2
        )
        end = start + relativedelta(months=2, days=6)

        instance_params = {
            **min_repayment_instance_params,
            loan.balloon_payments.PARAM_BALLOON_EMI_AMOUNT: "821",
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_AMOUNT: None,
            loan.disbursement.PARAM_PRINCIPAL: "100000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.02",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "36",
        }

        sub_tests = [
            SubTest(
                description="Standard Interest Accrual",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "821.00"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.02 / 365) * 100000 ,5) * 31
                    one_month_one_second_after_loan_start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "169.86295"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "169.86295 "),
                            (dimensions.EMI, "821.00"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-169.86295 "),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    one_month_one_minute_after_loan_start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "99348.86"),
                            (dimensions.PRINCIPAL_DUE, "651.14"),
                            (dimensions.INTEREST_DUE, "169.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "821.00"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "169.86"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due becomes Overdue",
                expected_balances_at_ts={
                    two_month_one_second_after_loan_start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "99348.86"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "651.14"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "169.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "157.86933"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "157.86933 "),
                            (dimensions.EMI, "821.00"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            # daily penalty rate = (0.02 + 0.24)/365 = 0.00071232876
                            # daily accrual = ROUND(0.00071232876 * 821,2) = 0.58
                            # total accrual = 0.58 * 19 = 11.02
                            # 15 late repayment fee
                            (dimensions.PENALTIES, "26.02"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-157.86933 "),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "169.86"),
                        ],
                        accounts.INTERNAL_PENALTY_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "11.02")
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "15")],
                        accounts.INTERNAL_CAPITALISED_PENALTIES_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                    two_month_one_minute_after_loan_start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "98685.73"),
                            (dimensions.PRINCIPAL_DUE, "663.13"),
                            (dimensions.PRINCIPAL_OVERDUE, "651.14"),
                            (dimensions.INTEREST_DUE, "157.87"),
                            (dimensions.INTEREST_OVERDUE, "169.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "821"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PENALTIES, "26.02"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "327.73"),
                        ],
                        accounts.INTERNAL_PENALTY_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "11.02")
                        ],
                        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "15")],
                        accounts.INTERNAL_CAPITALISED_PENALTIES_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=delinquency_notification,
                        notification_type=loan.MARK_DELINQUENT_NOTIFICATION,
                        notification_details={"account_id": self.loan_account_id},
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=min_repayment_template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_predefined_emi_balloon_payment_days_delta_22(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=12, days=23)

        instance_params = {
            **min_repayment_instance_params,
            loan.balloon_payments.PARAM_BALLOON_EMI_AMOUNT: "1850",
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_AMOUNT: None,
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: "22",
            loan.disbursement.PARAM_PRINCIPAL: "100000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.02",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
        }

        sub_tests = [
            SubTest(
                description="Standard Interest Accrual",
                events=self.create_deposit_events(
                    num_payments=11,
                    repayment_amount="1850",
                    repayment_day=1,
                    repayment_hour=16,
                    start_year=2020,
                    start_month=2,
                ),
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.02 / 365) * 100000 ,5) * 31
                    start
                    + relativedelta(months=1, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "98319.86"),
                            (dimensions.PRINCIPAL_DUE, "1680.14"),
                            (dimensions.INTEREST_DUE, "169.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "169.86"),
                        ],
                    },
                    start
                    + relativedelta(months=2, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "96626.09"),
                            (dimensions.PRINCIPAL_DUE, "1693.77"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "156.23"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "326.09"),
                        ],
                    },
                    start
                    + relativedelta(months=3, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "94940.22"),
                            (dimensions.PRINCIPAL_DUE, "1685.87"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "164.13"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "490.22"),
                        ],
                    },
                    start
                    + relativedelta(months=4, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "93246.29"),
                            (dimensions.PRINCIPAL_DUE, "1693.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "156.07"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "646.29"),
                        ],
                    },
                    start
                    + relativedelta(months=5, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "91554.68"),
                            (dimensions.PRINCIPAL_DUE, "1691.61"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "158.39"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "804.68"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="12",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="1850.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="100000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="100000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-02-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value="2020-02-11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="105263.16",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.balloon_payments.PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT,
                        value="79613.80",
                    ),
                ],
            ),
            SubTest(
                description="Final Instalment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="1850",
                        event_datetime=start + relativedelta(months=12, days=1),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=12, seconds=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "81330.15"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "138.14964"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "138.14964"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-138.14964"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1680.15"),
                        ],
                    },
                    start
                    + relativedelta(months=12, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "79618.30"),
                            (dimensions.PRINCIPAL_DUE, "1711.85"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "138.15"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1818.30"),
                        ],
                    },
                    start
                    + relativedelta(months=12, days=1, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "79618.30"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "4.36264"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "4.36264"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-4.36264"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1818.30"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Lump Sum Repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="79714.28",
                        event_datetime=start + relativedelta(months=12, days=22, hours=6),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=12, days=5, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "79618.30"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "21.8132"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "21.8132"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-21.8132"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1818.30"),
                        ],
                    },
                    start
                    + relativedelta(months=12, days=10, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "79618.30"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "43.6264"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "43.6264"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-43.6264"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1818.30"),
                        ],
                    },
                    start
                    + relativedelta(months=12, days=20, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "79618.30"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "87.2528"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "87.2528"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-87.2528"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1818.30"),
                        ],
                    },
                    start
                    + relativedelta(months=12, days=22, hours=5): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "79618.30"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "95.98"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1914.28"),
                        ],
                    },
                    start
                    + relativedelta(months=12, days=23): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "1850"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1914.28"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=1, minutes=1),
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "overdue_date": "2020-02-11",
                            "repayment_amount": "1850.00",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=6, minutes=1),
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "overdue_date": "2020-07-11",
                            "repayment_amount": "1850.00",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=12, minutes=1),
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "overdue_date": "2021-01-11",
                            "repayment_amount": "1850.00",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=12, days=22, hours=6),
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=min_repayment_template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_predefined_emi_under_repayment(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=5)

        instance_params = {
            **min_repayment_instance_params,
            loan.balloon_payments.PARAM_BALLOON_EMI_AMOUNT: "821",
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_AMOUNT: None,
            loan.disbursement.PARAM_PRINCIPAL: "100000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.02",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "36",
        }

        sub_tests = [
            SubTest(
                description="Standard Interest Accrual, single repayment less than EMI. Check "
                "balances after one month",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="820",
                        event_datetime=datetime(2020, 2, 1, 16, tzinfo=ZoneInfo("UTC")),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "821"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.02 / 365) * 100000 ,5) * 31
                    start
                    + relativedelta(months=1, seconds=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "169.86295"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "169.86295 "),
                            (dimensions.EMI, "821"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-169.86295 "),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    start
                    + relativedelta(months=1, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "99348.86"),
                            (dimensions.PRINCIPAL_DUE, "651.14"),
                            (dimensions.INTEREST_DUE, "169.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "821"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "169.86"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Outstanding Due becomes Overdue after two months",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, seconds=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "99348.86"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "1"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "157.86933"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "157.86933 "),
                            (dimensions.EMI, "821"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-157.86933 "),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "169.86"),
                        ],
                    },
                    start
                    + relativedelta(months=2, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "98685.73"),
                            (dimensions.PRINCIPAL_DUE, "663.13"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "157.87"),
                            (dimensions.INTEREST_OVERDUE, "1"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "821"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "327.73"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=min_repayment_template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_predefined_emi_amount_lt_interest(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=5)

        instance_params = {
            **min_repayment_instance_params,
            loan.balloon_payments.PARAM_BALLOON_EMI_AMOUNT: "2",
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_AMOUNT: None,
            loan.disbursement.PARAM_PRINCIPAL: "100000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.02",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "36",
        }

        sub_tests = [
            SubTest(
                description="Standard Interest Accrual, with single repayment for EMI amount after "
                "one month.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="169.86",
                        event_datetime=datetime(2020, 2, 1, 16, tzinfo=ZoneInfo("UTC")),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.02 / 365) * 100000 ,5) * 31
                    start
                    + relativedelta(months=1, seconds=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "169.86295"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "169.86295 "),
                            (dimensions.EMI, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-169.86295 "),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    start
                    + relativedelta(months=1, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "169.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "169.86"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check accrued and due amounts after two months.",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, seconds=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "158.90405"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "158.90405"),
                            (dimensions.EMI, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-158.90405"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "169.86"),
                        ],
                    },
                    start
                    + relativedelta(months=2, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "158.90"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "328.76"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=min_repayment_template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_with_predefined_emi_lt_interest_flattened_at_final_payment_delta_days_4(
        self,
    ):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=5)

        instance_params = {
            **min_repayment_instance_params,
            loan.balloon_payments.PARAM_BALLOON_EMI_AMOUNT: "2",
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_AMOUNT: None,
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: "4",
            loan.disbursement.PARAM_PRINCIPAL: "100000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.02",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "2",
        }

        sub_tests = [
            SubTest(
                description="Standard Interest Accrual, balances checked after one month.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="169.86",
                        event_datetime=datetime(2020, 2, 1, 16, tzinfo=ZoneInfo("UTC")),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.02 / 365) * 100000 ,5) * 31
                    start
                    + relativedelta(months=1, seconds=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "169.86295"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "169.86295 "),
                            (dimensions.EMI, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-169.86295 "),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    start
                    + relativedelta(months=1, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "169.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "169.86"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Standard Interest Accrual, balances checked after two months.",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, seconds=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "158.90405"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "158.90405"),
                            (dimensions.EMI, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-158.90405"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "169.86"),
                        ],
                    },
                    start
                    + relativedelta(months=2, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "158.90"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "328.76"),
                        ],
                    },
                    start
                    + relativedelta(months=2, days=4): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "158.90"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "16.43835"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "16.43835"),
                            (dimensions.EMI, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-16.43835"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "328.76"),
                        ],
                    },
                    start
                    + relativedelta(months=2, days=4, minutes=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "100000.00"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "180.82"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "350.68"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Lump Sum Repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="100180.82",
                        event_datetime=datetime(2020, 3, 5, 16, tzinfo=ZoneInfo("UTC")),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, days=4, hours=18): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "350.68"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=1, minutes=1),
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "overdue_date": "2020-02-11",
                            "repayment_amount": "169.86",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=2, minutes=1),
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "overdue_date": "2020-03-11",
                            "repayment_amount": "158.90",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(months=2, days=4, minutes=1),
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "overdue_date": "2020-03-15",
                            "repayment_amount": "100021.92",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=datetime(2020, 3, 5, 16, tzinfo=ZoneInfo("UTC")),
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=min_repayment_template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_balloon_amount_emi_calc_required_delta_days_0(self):

        start = default_simulation_start_date
        end = start + relativedelta(years=3, days=10)

        instance_params = {
            **min_repayment_instance_params,
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_AMOUNT: "50000",
            loan.disbursement.PARAM_PRINCIPAL: "100000",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "1",
            loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.02",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "36",
        }

        sub_tests = [
            SubTest(
                description="create monthly deposit events for payment of due balances and "
                "check daily interest accrual on day 1",
                events=self.create_deposit_events(
                    num_payments=35,
                    repayment_amount="1515.46",
                    repayment_day=1,
                    repayment_hour=11,
                    start_year=2020,
                    start_month=2,
                ),
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "100000.00"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "5.47945"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "5.47945"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "1515.46"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.47945")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="check balances after 1 month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "98654.40"),
                            (dimensions.PRINCIPAL_DUE, "1345.60"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTEREST_DUE, "169.86"),
                            (dimensions.EMI, "1515.46"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "169.86")],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="36",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="1515.46",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="100000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="100000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-02-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value="2020-02-11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="105263.16",
                    ),
                ],
            ),
            SubTest(
                description="check balances after repayment of due amounts",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, days=1, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "98654.40"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "5.40572"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "5.40572"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "1515.46"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-5.40572")
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "169.86")],
                    },
                },
            ),
            SubTest(
                description="check balances after 6 months",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=6, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "91870.79"),
                            (dimensions.PRINCIPAL_DUE, "1362.20"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTEREST_DUE, "153.26"),
                            (dimensions.EMI, "1515.46"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "963.55")],
                    },
                },
            ),
            SubTest(
                description="check balances on balloon payment date",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=3, hours=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "51431.43"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTEREST_DUE, "87.36"),
                            (dimensions.EMI, "1515.46"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "4559.89")],
                    },
                },
            ),
            SubTest(
                description="check payment clears due balances and emits notification",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="51518.79",
                        event_datetime=start + relativedelta(years=3, hours=2),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=3, hours=12): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "1515.46"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [(dimensions.DEFAULT, "0")],
                        accounts.INTERNAL_INTEREST_RECEIVED: [(dimensions.DEFAULT, "4559.89")],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + relativedelta(years=3, hours=2),
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=min_repayment_template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_min_repayment_balloon_amount_emi_calc_required_with_date_delta(
        self,
    ):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **min_repayment_instance_params,
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_DAYS_DELTA: "35",
            loan.balloon_payments.PARAM_BALLOON_PAYMENT_AMOUNT: "5000",
        }

        one_month_after_loan_start = start + relativedelta(months=1, minutes=1)

        before_first_payment = start + relativedelta(months=1, days=9, minutes=5)
        after_first_payment = start + relativedelta(months=1, days=9, hours=20)

        before_second_repayment_event = start + relativedelta(months=2, days=9, seconds=30)
        after_second_repayment_event = start + relativedelta(months=2, days=9, minutes=5)

        after_second_deposit = start + relativedelta(months=2, days=9, hours=20)

        day_after_theoretical_final_repayment_event = start + relativedelta(
            months=2, days=10, hours=20
        )
        before_balloon_payment_event = start + relativedelta(months=3, days=13, seconds=2)
        after_balloon_payment_event = start + relativedelta(months=3, days=13, hours=1)

        balloon_payment = after_balloon_payment_event + relativedelta(hours=5)
        after_balloon_payment = after_balloon_payment_event + relativedelta(hours=6)

        end = start + relativedelta(months=4)

        sub_tests = [
            SubTest(
                description="interest accrued correctly",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    # accrued_interest = round(daily_interest_rate * principal ,5) * days
                    #                  = round((0.031 / 365) * 10000 ,5) * 31
                    one_month_after_loan_start: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "10000"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "26.32892"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "26.32892"),
                            (dimensions.EMI, "2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-26.32892"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="2522.61",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="10000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="10000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-02-20",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value="2020-03-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
                        value="10526.32",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=self.loan_account_id,
                        name=loan.balloon_payments.PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT,
                        value="5000",
                    ),
                ],
            ),
            SubTest(
                description="interest moved to interest due after first repayment date",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="2530.25",
                        event_datetime=datetime(
                            year=2020, month=2, day=20, hour=12, tzinfo=ZoneInfo("UTC")
                        ),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    # First repayment date is 40 days after the loan start
                    # so more interest has been accrued
                    before_first_payment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "7503.72"),
                            (dimensions.PRINCIPAL_DUE, "2496.28"),
                            (dimensions.INTEREST_DUE, "33.97"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                    after_first_payment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "7503.72"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment + relativedelta(days=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="2522.61",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="10000.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="10033.97",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS,
                        value="2530.25",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_first_payment,
                        account_id=self.loan_account_id,
                        name=loan.balloon_payments.PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT,
                        value="5000",
                    ),
                ],
            ),
            SubTest(
                description="Check second repayment event and payment clears due",
                events=[
                    # Ensure overpayment is rejected
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="3522.61",
                        event_datetime=datetime(
                            year=2020, month=3, day=20, hour=10, tzinfo=ZoneInfo("UTC")
                        ),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="2522.61",
                        event_datetime=datetime(
                            year=2020, month=3, day=20, hour=12, tzinfo=ZoneInfo("UTC")
                        ),
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    before_second_repayment_event: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "7503.72"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "18.48170"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "18.48170"),
                            (dimensions.EMI, "2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-18.48170"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "33.97"),
                        ],
                    },
                    after_second_repayment_event: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "4999.59"),
                            (dimensions.PRINCIPAL_DUE, "2504.13"),
                            (dimensions.INTEREST_DUE, "18.48"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "52.45"),
                        ],
                    },
                    after_second_deposit: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "4999.59"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "52.45"),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=datetime(
                            year=2020, month=3, day=20, hour=10, tzinfo=ZoneInfo("UTC")
                        ),
                        account_id=self.loan_account_id,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Overpayments are not allowed for minimum repayment with "
                        "balloon payment loans.",
                    )
                ],
            ),
            SubTest(
                description="check interest accrued after theoretical final repayment",
                expected_balances_at_ts={
                    day_after_theoretical_final_repayment_event: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "4999.59"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0.42462"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0.42462"),
                            (dimensions.EMI, "2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-0.42462"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "52.45"),
                        ],
                    },
                    before_balloon_payment_event: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "4999.59"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "14.86170"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "14.86170"),
                            (dimensions.EMI, "2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-14.86170"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "52.45"),
                        ],
                    },
                    after_balloon_payment_event: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "4999.59"),
                            (dimensions.INTEREST_DUE, "14.86"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "67.31"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=self.loan_account_id,
                        name=loan.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="2522.61",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="4999.59",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="5000.01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-04-24",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value="2020-03-30",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_balloon_payment_event,
                        account_id=self.loan_account_id,
                        name=loan.overdue.PARAM_NEXT_OVERDUE_DATE,
                        value="2020-05-04",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=day_after_theoretical_final_repayment_event,
                        account_id=self.loan_account_id,
                        name=loan.balloon_payments.PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT,
                        value="5000",
                    ),
                ],
            ),
            SubTest(
                description="check payment clears due amounts and check schedules",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount="5014.45",
                        event_datetime=balloon_payment,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    after_balloon_payment: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.EMI, "2522.61"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "67.31"),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=2,
                                day=20,
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
                        ],
                        event_id=loan.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=self.loan_account_id,
                        count=2,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=4,
                                day=24,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=ZoneInfo("UTC"),
                            ),
                        ],
                        event_id=loan.balloon_payments.BALLOON_PAYMENT_EVENT,
                        account_id=self.loan_account_id,
                        count=1,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=balloon_payment,
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=min_repayment_template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)
