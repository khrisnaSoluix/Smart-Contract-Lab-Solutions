# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

# library
from library.mortgage.test import dimensions, parameters
from library.mortgage.test.simulation.common import MortgageTestBase

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

MORTGAGE_ACCOUNT = "MORTGAGE_ACCOUNT"
DEPOSIT_ACCOUNT = "DEPOSIT_ACCOUNT"

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
payment_hour = 12
start_year = 2020


mortgage_1_instance_params = {
    "fixed_interest_rate": "0.129971",
    "fixed_interest_term": "0",
    "total_repayment_count": "120",
    "interest_only_term": "0",
    "principal": "300000",
    "due_amount_calculation_day": "12",
    "deposit_account": DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "-0.001",
}


class MortgageVariableTest(MortgageTestBase):
    def test_monthly_due_for_variable_rate_with_overpayment(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=12, day=13, minute=1, tzinfo=timezone.utc)

        events = []
        sub_tests = []

        for event in self.input_data["monthly_due_for_variable_rate_with_overpayment"]:
            if event[0] == "variable_rate_change":
                # Rate changes occurring just after repayment
                events.append(
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=int(event[1]),
                            month=int(event[2]),
                            day=int(event[3]),
                            tzinfo=timezone.utc,
                        ),
                        variable_interest_rate=str(event[4]),
                    )
                )
            else:
                # Repayments occur on repayment day
                events.extend(
                    _set_up_deposit_events(
                        int(event[1]),
                        event[2],
                        12,
                        payment_hour,
                        int(event[3]),
                        int(event[4]),
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
            tzinfo=timezone.utc,
        )
        for i, values in enumerate(self.expected_output["variable_rate_with_overpayments"]):
            sub_tests.append(
                SubTest(
                    description=f"check balance at repayment {i}",
                    expected_balances_at_ts={
                        repayment_date
                        + relativedelta(months=i): {
                            MORTGAGE_ACCOUNT: [
                                (dimensions.PRINCIPAL_DUE, values[0]),
                                (dimensions.INTEREST_DUE, values[1]),
                            ]
                        }
                    },
                )
            )

        before_first_rate_change = datetime(2020, 2, 4, 1, tzinfo=timezone.utc)
        after_first_rate_change = datetime(2020, 2, 5, 1, tzinfo=timezone.utc)
        # overpayment of £11,000 made on repayment day 12/3/2020
        before_overpayment = datetime(2020, 3, 12, 1, tzinfo=timezone.utc)
        after_overpayment = datetime(2020, 3, 12, 21, tzinfo=timezone.utc)

        sub_tests.extend(
            [
                SubTest(
                    description="remaining term before_first_rate_change",
                    expected_derived_parameters=[
                        ExpectedDerivedParameter(
                            timestamp=before_first_rate_change,
                            account_id=MORTGAGE_ACCOUNT,
                            name="remaining_term",
                            value="120",
                        )
                    ],
                ),
                SubTest(
                    description="remaining term after_first_rate_change",
                    expected_derived_parameters=[
                        ExpectedDerivedParameter(
                            timestamp=after_first_rate_change,
                            account_id=MORTGAGE_ACCOUNT,
                            name="remaining_term",
                            value="120",
                        )
                    ],
                ),
                SubTest(
                    description="remaining term before_overpayment",
                    expected_derived_parameters=[
                        ExpectedDerivedParameter(
                            timestamp=before_overpayment,
                            account_id=MORTGAGE_ACCOUNT,
                            name="remaining_term",
                            value="118",
                        )
                    ],
                ),
                SubTest(
                    description="remaining term after_overpayment",
                    expected_derived_parameters=[
                        ExpectedDerivedParameter(
                            timestamp=after_overpayment,
                            account_id=MORTGAGE_ACCOUNT,
                            name="remaining_term",
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
            instance_params=mortgage_1_instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_interest_rate_change_after_final_repayment_day(self):
        """
        ensure that if emi is recalculated after the final repayment day
        we do not encounter [<class 'decimal.DivisionUndefined'>] errors.
        """
        start = default_simulation_start_date
        end = datetime(year=2021, month=5, day=21, minute=1, tzinfo=timezone.utc)

        instance_params = {
            **mortgage_1_instance_params,
            "total_repayment_count": "12",
            "principal": "80000",
            "variable_rate_adjustment": "0",
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
            tzinfo=timezone.utc,
        )
        after_final_repayment_day = before_final_repayment_day + relativedelta(hours=5)

        first_payment_date = datetime(
            year=2020,
            month=2,
            day=12,
            hour=10,
            minute=0,
            second=30,
            tzinfo=timezone.utc,
        )
        payments = [
            create_inbound_hard_settlement_instruction(
                first_payment,
                first_payment_date,
                target_account_id=MORTGAGE_ACCOUNT,
                internal_account_id=DEPOSIT_ACCOUNT,
            )
        ]
        payments.extend(_set_up_deposit_events(10, monthly_emi, 12, 10, 2020, 3))

        sub_tests = [
            SubTest(
                description="payments excluding final payment",
                events=payments,
                expected_balances_at_ts={
                    before_final_repayment_day: {
                        MORTGAGE_ACCOUNT: [
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
                        MORTGAGE_ACCOUNT: [
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
                        account_id=MORTGAGE_ACCOUNT,
                        name="next_repayment_date",
                        value="2021-02-12",
                    )
                ],
            ),
            SubTest(
                description="change interest rate once N = 0 to trigger emi recalculation",
                events=[
                    create_template_parameter_change_event(
                        timestamp=before_final_repayment_day + relativedelta(months=1),
                        variable_interest_rate="0.01",
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_final_repayment_day + relativedelta(months=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="0",
                    )
                ],
                expected_balances_at_ts={
                    before_final_repayment_day
                    + relativedelta(months=1): {
                        MORTGAGE_ACCOUNT: [
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
                    after_final_repayment_day
                    + relativedelta(months=1): {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            # v3-v4: when term is 0 we now return 0 emi
                            (dimensions.EMI, "0"),
                            # (dimensions.EMI, "6782.79"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "6765.23"),
                            (dimensions.INTEREST_OVERDUE, "18.39"),
                        ]
                    },
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

    def test_variable_rate_with_overpayment_emi_adjustment(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=6, days=16)

        template_params = {
            **parameters.mortgage_template_params,
            "overpayment_impact_preference": "reduce_emi",
        }

        instance_params = {
            **mortgage_1_instance_params,
            "total_repayment_count": "12",
            "due_amount_calculation_day": "20",
            "principal": "3000",
        }

        first_repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
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
            tzinfo=timezone.utc,
        )

        sub_tests = [
            SubTest(
                description="first month emi",
                expected_balances_at_ts={
                    first_repayment_date: {
                        MORTGAGE_ACCOUNT: [
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
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
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
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_template_parameter_change_event(
                        timestamp=first_repayment_date + relativedelta(hours=10),
                        # 0.029 - 0.01 adjustment = 0.028
                        variable_interest_rate="0.029",
                    ),
                ],
                expected_balances_at_ts={
                    second_repayment_date: {
                        MORTGAGE_ACCOUNT: [
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
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="10",
                    )
                ],
            ),
            SubTest(
                description="rate change with overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "453.85",
                        second_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_template_parameter_change_event(
                        timestamp=second_repayment_date + relativedelta(hours=10),
                        # 0.016 - 0.01 adjustment = 0.015
                        variable_interest_rate="0.016",
                    ),
                ],
                expected_balances_at_ts={
                    third_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "229.24"),
                            (dimensions.INTEREST_DUE, "2.94"),
                            (dimensions.EMI, "232.18"),
                            # v3-v4: overpayment is a positive tracker
                            # (dimensions.OVERPAYMENT, "-200"),
                            (dimensions.OVERPAYMENT, "200"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="9",
                    )
                ],
            ),
            SubTest(
                description="overpayment without rate change",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "332.18",
                        third_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    fourth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "218.57"),
                            (dimensions.INTEREST_DUE, "2.44"),
                            (dimensions.EMI, "221.01"),
                            # v3-v4: overpayment is a positive tracker
                            # (dimensions.OVERPAYMENT, "-300"),
                            (dimensions.OVERPAYMENT, "300"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
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
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    fifth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "218.77"),
                            (dimensions.INTEREST_DUE, "2.24"),
                            (dimensions.EMI, "221.01"),
                            # v3-v4: overpayment is a positive tracker
                            # (dimensions.OVERPAYMENT, "-300"),
                            (dimensions.OVERPAYMENT, "300"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fifth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="7",
                    )
                ],
            ),
            SubTest(
                description="overpayment after repayment day change triggers emi recalculation",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=fifth_repayment_date + relativedelta(hours=2),
                        account_id=MORTGAGE_ACCOUNT,
                        due_amount_calculation_day=new_repayment_day,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "321.01",
                        fifth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    sixth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.EMI, "206.66"),
                            # v3-v4: overpayment is a positive tracker
                            # (dimensions.OVERPAYMENT, "-400"),
                            (dimensions.OVERPAYMENT, "400"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=sixth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="6",
                    )
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


def _set_up_deposit_events(
    num_payments,
    repayment_amount,
    repayment_day,
    repayment_hour,
    start_year,
    start_month,
):
    events = []
    for i in range(num_payments):
        month = (i + start_month - 1) % 12 + 1
        year = start_year + int((i + start_month + 1 - month) / 12)

        event_date = datetime(
            year=year,
            month=month,
            day=repayment_day,
            hour=repayment_hour,
            tzinfo=timezone.utc,
        )
        events.append(
            create_inbound_hard_settlement_instruction(
                target_account_id=MORTGAGE_ACCOUNT,
                amount=repayment_amount,
                event_datetime=event_date,
                internal_account_id=DEPOSIT_ACCOUNT,
            )
        )

    return events
