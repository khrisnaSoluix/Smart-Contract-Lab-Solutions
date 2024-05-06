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
    ExpectedDerivedParameter,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_template_parameter_change_event,
)

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
num_payments = 1
repayment_day = 28
payment_hour = 12
start_year = 2020
start_month = 1

variable_rate_instance_params = {
    **parameters.loan_instance_params,
    loan.PARAM_FIXED_RATE_LOAN: "False",
    loan.PARAM_AMORTISE_UPFRONT_FEE: "False",
    loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: "False",
    loan.disbursement.PARAM_PRINCIPAL: "300000",
    loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "12",
    loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.01",
    loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "120",
    loan.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "-0.001",
}

variable_rate_template_params = {
    **parameters.loan_template_params,
    loan.PARAM_ACCRUE_ON_DUE_PRINCIPAL: "False",
    loan.PARAM_AMORTISATION_METHOD: "declining_principal",
    loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "no_capitalisation",
    loan.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "True",
    loan.PARAM_PENALTY_INCLUDES_BASE_RATE: "True",
    loan.PARAM_GRACE_PERIOD: "1",
    loan.PARAM_LATE_REPAYMENT_FEE: "15",
    loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0.05",
    loan.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_term",
    loan.overdue.PARAM_REPAYMENT_PERIOD: "10",
    loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.032",
    loan.variable_rate.PARAM_ANNUAL_INTEREST_RATE_CAP: "1.00",
    loan.variable_rate.PARAM_ANNUAL_INTEREST_RATE_FLOOR: "0.00",
}


class LoanVariableTest(LoanTestBase):

    loan_instance_params = variable_rate_instance_params
    loan_template_params = variable_rate_template_params

    def test_monthly_due_for_variable_rate_with_overpayment(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=12, day=13, minute=1, tzinfo=ZoneInfo("UTC"))

        events = []
        sub_tests = []

        for event in self.input_data["monthly_due_for_variable_rate_with_overpayment"]:
            if event[0] == "variable_rate_change":
                events.append(
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=int(event[1]),
                            month=int(event[2]),
                            day=int(event[3]),
                            tzinfo=ZoneInfo("UTC"),
                        ),
                        **{loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: str(event[4])},
                    )
                )
            else:
                # Repayments occur on repayment day
                events.extend(
                    self.create_deposit_events(
                        num_payments=int(event[1]),
                        repayment_amount=event[2],
                        repayment_day=12,
                        repayment_hour=payment_hour,
                        start_year=int(event[3]),
                        start_month=int(event[4]),
                    )
                )

        sub_tests.append(SubTest(description="rate change and repayment events", events=events))

        repayment_date = datetime(
            year=start_year,
            month=2,
            day=12,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=ZoneInfo("UTC"),
        )
        for i, values in enumerate(self.expected_output["variable_rate_with_overpayments"]):
            sub_tests.append(
                SubTest(
                    description=f"check balance at repayment {i+1}",
                    expected_balances_at_ts={
                        repayment_date
                        + relativedelta(months=i): {
                            self.loan_account_id: [
                                (dimensions.PRINCIPAL_DUE, values[0]),
                                (dimensions.INTEREST_DUE, values[1]),
                            ]
                        }
                    },
                )
            )

        before_first_rate_change = datetime(2020, 2, 4, 1, tzinfo=ZoneInfo("UTC"))
        after_first_rate_change = datetime(2020, 2, 5, 1, tzinfo=ZoneInfo("UTC"))
        # overpayment of £10,000 made on repayment day 12/3/2020
        before_overpayment = datetime(2020, 3, 12, 1, tzinfo=ZoneInfo("UTC"))
        after_overpayment = datetime(2020, 3, 12, 21, tzinfo=ZoneInfo("UTC"))

        sub_tests.extend(
            [
                SubTest(
                    description="remaining term before_first_rate_change",
                    expected_derived_parameters=[
                        ExpectedDerivedParameter(
                            timestamp=before_first_rate_change,
                            account_id=self.loan_account_id,
                            name=loan.derived_params.PARAM_REMAINING_TERM,
                            value="120",
                        )
                    ],
                ),
                SubTest(
                    description="remaining term after_first_rate_change",
                    expected_derived_parameters=[
                        ExpectedDerivedParameter(
                            timestamp=after_first_rate_change,
                            account_id=self.loan_account_id,
                            name=loan.derived_params.PARAM_REMAINING_TERM,
                            value="120",
                        )
                    ],
                ),
                SubTest(
                    description="remaining term before_overpayment",
                    expected_derived_parameters=[
                        ExpectedDerivedParameter(
                            timestamp=before_overpayment,
                            account_id=self.loan_account_id,
                            name=loan.derived_params.PARAM_REMAINING_TERM,
                            value="118",
                        )
                    ],
                ),
                SubTest(
                    description="remaining term after_overpayment",
                    expected_derived_parameters=[
                        ExpectedDerivedParameter(
                            timestamp=after_overpayment,
                            account_id=self.loan_account_id,
                            name=loan.derived_params.PARAM_REMAINING_TERM,
                            value="114",
                        )
                    ],
                ),
            ]
        )

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_variable_rate_with_overpayment_emi_adjustment(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=6, days=16)

        instance_params = {
            **self.loan_instance_params,
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20",
            loan.disbursement.PARAM_PRINCIPAL: "3000",
        }
        template_params = {
            **self.loan_template_params,
            loan.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_emi",
        }

        first_repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=ZoneInfo("UTC"),
        )

        second_repayment_date = first_repayment_date + relativedelta(months=1)
        third_repayment_date = second_repayment_date + relativedelta(months=1)
        fourth_repayment_date = third_repayment_date + relativedelta(months=1)
        fifth_repayment_date = fourth_repayment_date + relativedelta(months=1)

        new_repayment_day = "25"
        sixth_repayment_date = datetime(
            year=start_year,
            month=7,
            day=25,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=ZoneInfo("UTC"),
        )

        sub_tests = [
            SubTest(
                description="first month emi",
                expected_balances_at_ts={
                    first_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "2753.68"),
                            (dimensions.PRINCIPAL_DUE, "246.32"),
                            (dimensions.INTEREST_DUE, "10.19"),
                            (dimensions.EMI, "254.22"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="11",
                    )
                ],
            ),
            SubTest(
                description="rate change without overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # emi plus additional interest from account creation
                        "256.51",
                        first_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_template_parameter_change_event(
                        timestamp=first_repayment_date + relativedelta(hours=10),
                        # 0.029 - 0.01 adjustment = 0.028
                        **{loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.029"},
                    ),
                ],
                expected_balances_at_ts={
                    second_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "247.72"),
                            (dimensions.INTEREST_DUE, "6.13"),
                            (dimensions.EMI, "253.85"),
                            (dimensions.OVERPAYMENT, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="10",
                    )
                ],
            ),
            SubTest(
                description="rate change with overpayment",
                events=[
                    # overpayment: 210.53, fee: 10.53, overpayment - fee: 200
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("253.85") + Decimal("200") + Decimal("10.53")),
                        second_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_template_parameter_change_event(
                        timestamp=second_repayment_date + relativedelta(hours=10),
                        # 0.016 - 0.01 adjustment = 0.015
                        **{loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.016"},
                    ),
                ],
                expected_balances_at_ts={
                    third_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "229.24"),
                            (dimensions.INTEREST_DUE, "2.94"),
                            (dimensions.EMI, "232.18"),
                            (dimensions.OVERPAYMENT, "200"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="9",
                    )
                ],
            ),
            SubTest(
                description="overpayment without rate change",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # overpayment: 105.26, fee: 5.26, overpayment - fee: 100
                        str(Decimal("232.18") + Decimal("100") + Decimal("5.26")),
                        third_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    fourth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "218.57"),
                            (dimensions.INTEREST_DUE, "2.44"),
                            (dimensions.EMI, "221.01"),
                            (dimensions.OVERPAYMENT, "300"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="8",
                    )
                ],
            ),
            SubTest(
                description="constant rate value with no overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "221.01",
                        fourth_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    fifth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "218.77"),
                            (dimensions.INTEREST_DUE, "2.24"),
                            (dimensions.EMI, "221.01"),
                            (dimensions.OVERPAYMENT, "300"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fifth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="7",
                    )
                ],
            ),
            SubTest(
                description="overpayment made after repayment day change triggers emi recalc",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=fifth_repayment_date + relativedelta(hours=2),
                        account_id=self.loan_account_id,
                        **{
                            loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: (
                                new_repayment_day
                            )
                        },
                    ),
                    create_inbound_hard_settlement_instruction(
                        # overpayment: 105.26, fee: 5.26, overpayment - fee: 100
                        str(Decimal("221.01") + Decimal("100") + Decimal("5.26")),
                        fifth_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    sixth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.EMI, "206.66"),
                            (dimensions.OVERPAYMENT, "400"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=sixth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="6",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_interest_rate_change_after_final_repayment_day(self):
        """
        test added logic in _calculate_monthly_payment_interest_and_principal
        to ensure that if emi is recalculated after the final repayment day
        we do not encounter [<class 'decimal.DivisionUndefined'>] errors.
        """
        start = default_simulation_start_date
        end = datetime(year=2021, month=5, day=21, minute=1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **self.loan_instance_params,
            loan.disbursement.PARAM_PRINCIPAL: "80000",
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
            loan.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "0",
        }

        monthly_emi = "6782.79"
        first_payment = "6789.80"

        before_final_repayment_day = datetime(
            year=2021,
            month=1,
            day=12,
            hour=0,
            minute=0,
            second=30,
            tzinfo=ZoneInfo("UTC"),
        )
        after_final_repayment_day = before_final_repayment_day + relativedelta(hours=5)

        first_payment_date = datetime(
            year=2020,
            month=2,
            day=12,
            hour=10,
            minute=0,
            second=30,
            tzinfo=ZoneInfo("UTC"),
        )
        payments = [
            create_inbound_hard_settlement_instruction(
                first_payment,
                first_payment_date,
                target_account_id=self.loan_account_id,
                internal_account_id=accounts.DEPOSIT,
            )
        ]
        payments.extend(
            self.create_deposit_events(
                num_payments=10,
                repayment_amount=monthly_emi,
                repayment_day=12,
                repayment_hour=10,
                start_year=2020,
                start_month=3,
            )
        )

        sub_tests = [
            SubTest(
                description="payments excluding final payment",
                events=payments,
                expected_balances_at_ts={
                    before_final_repayment_day: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "6765.23"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "18.38672"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "6782.79"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                    after_final_repayment_day: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.PRINCIPAL_DUE, "6765.23"),
                            (dimensions.INTEREST_DUE, "18.39"),
                            (dimensions.EMI, "6782.79"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_final_repayment_day + relativedelta(hours=5),
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2021-01-12",
                    )
                ],
            ),
            SubTest(
                description="change interest rate once N = 0 to trigger emi recalculation",
                events=[
                    create_template_parameter_change_event(
                        timestamp=before_final_repayment_day + relativedelta(months=1),
                        **{loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.01"},
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_final_repayment_day + relativedelta(months=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    )
                ],
                expected_balances_at_ts={
                    before_final_repayment_day
                    + relativedelta(months=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "6782.79"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "6765.23"),
                            (dimensions.INTEREST_OVERDUE, "18.39"),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)
