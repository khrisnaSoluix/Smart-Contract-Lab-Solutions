# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from collections import defaultdict
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

# library
from library.loan.contracts.template import loan
from library.loan.test import accounts, dimensions, parameters
from library.loan.test.simulation.common import LoanTestBase

# inception sdk
import inception_sdk.test_framework.common.constants as constants
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ExpectedDerivedParameter,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_flag_definition_event,
    create_flag_event,
    create_template_parameter_change_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import get_balances

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
num_payments = 1
repayment_day = 28
payment_hour = 12
start_year = 2020
start_month = 1

variable_rate_instance_params = {
    **parameters.loan_instance_params,
    loan.PARAM_FIXED_RATE_LOAN: "False",
    loan.disbursement.PARAM_PRINCIPAL: "300000",
    loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "12",
    loan.repayment_holiday.PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE: "increase_emi",
    loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "120",
    loan.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "-0.001",
    loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: "False",
}

variable_rate_template_params = {
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

fixed_rate_instance_params = {
    **parameters.loan_instance_params,
    loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
    loan.PARAM_FIXED_RATE_LOAN: "True",
    loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "120",
    loan.disbursement.PARAM_PRINCIPAL: "300000",
    loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20",
    loan.repayment_holiday.PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE: "increase_emi",
    loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: "False",
}

fixed_rate_template_params = {
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
}

REPAYMENT_HOLIDAY_FLAG = parameters.DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE[0]


class LoanRepaymentHolidayTest(LoanTestBase):
    def test_monthly_interest_accrual_fixed_increase_emi(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=9, day=21, tzinfo=ZoneInfo("UTC"))

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=ZoneInfo("UTC")
        )
        payment_holiday_end = datetime(
            year=2020, month=7, day=20, hour=0, minute=2, tzinfo=ZoneInfo("UTC")
        )

        events = [_set_up_repayment_holiday_flag(start)]

        events.append(
            create_flag_event(
                timestamp=start + timedelta(seconds=2),
                flag_definition_id=REPAYMENT_HOLIDAY_FLAG,
                account_id=self.loan_account_id,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )

        events.extend(
            self.create_deposit_events(
                num_payments=1,
                repayment_amount=str(Decimal("3140.01")),
                repayment_day=20,
                repayment_hour=payment_hour,
                start_year=start_year,
                start_month=2,
            )
        )
        events.extend(
            self.create_deposit_events(
                num_payments=2,
                repayment_amount=str(Decimal("2910.69")),
                repayment_day=20,
                repayment_hour=payment_hour,
                start_year=start_year,
                start_month=3,
            )
        )

        sub_tests = [SubTest(description="Deposit events", events=events)]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=fixed_rate_template_params,
            instance_params=fixed_rate_instance_params,
        )

        res = self.run_test_scenario(test_scenario)

        repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=2,
            second=0,
            microsecond=2,
            tzinfo=ZoneInfo("UTC"),
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(
            self.expected_output[
                "repayment_holiday_test_monthly_interest_accrual_fixed_increase_emi"
            ]
        ):
            expected_balances[self.loan_account_id][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
                (dimensions.PRINCIPAL, values[2]),
                (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, values[3]),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, values[4]),
                (dimensions.CAPITALISED_INTEREST_TRACKER, values[5]),
                (dimensions.EMI, values[6]),
            ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_monthly_interest_accrual_fixed_increase_term(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=9, day=21, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **fixed_rate_instance_params,
            loan.repayment_holiday.PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE: "increase_term",
        }

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=ZoneInfo("UTC")
        )
        payment_holiday_end = datetime(
            year=2020, month=7, day=20, hour=0, minute=2, tzinfo=ZoneInfo("UTC")
        )

        first_repayment_date = datetime(
            year=2020, month=2, day=20, minute=2, tzinfo=ZoneInfo("UTC")
        )
        at_event_b4_holiday_start = payment_holiday_start.replace(hour=0)
        after_event_b4_holiday_start = payment_holiday_start.replace(hour=1)
        before_first_repayment_date = first_repayment_date - relativedelta(hours=1)
        after_first_repayment_due = first_repayment_date + relativedelta(hours=1)
        before_holiday_end = payment_holiday_end - relativedelta(days=1)
        after_holiday_end = payment_holiday_end + relativedelta(hours=1)
        before_repayment_after_holiday = datetime(
            year=2020, month=8, day=19, hour=12, tzinfo=ZoneInfo("UTC")
        )
        before_2nd_repayment_after_holiday = datetime(
            year=2020, month=9, day=19, hour=12, tzinfo=ZoneInfo("UTC")
        )

        sub_tests = [
            SubTest(
                description="create flag definition and flag event with overlapping flag",
                events=[
                    _set_up_repayment_holiday_flag(start),
                    create_flag_event(
                        timestamp=start + timedelta(seconds=2),
                        flag_definition_id=REPAYMENT_HOLIDAY_FLAG,
                        account_id=self.loan_account_id,
                        effective_timestamp=payment_holiday_start,
                        expiry_timestamp=payment_holiday_start + relativedelta(months=1, days=1),
                    ),
                    create_flag_event(
                        timestamp=start + timedelta(seconds=4),
                        flag_definition_id=REPAYMENT_HOLIDAY_FLAG,
                        account_id=self.loan_account_id,
                        effective_timestamp=payment_holiday_start + relativedelta(months=1),
                        expiry_timestamp=payment_holiday_end,
                    ),
                ],
            ),
            SubTest(
                description="repayments up to end of repayment holiday",
                events=self.create_deposit_events(
                    num_payments=1,
                    repayment_amount=str(Decimal("3140.01")),
                    repayment_day=20,
                    repayment_hour=12,
                    start_year=2020,
                    start_month=2,
                )
                + self.create_deposit_events(
                    num_payments=2,
                    repayment_amount=str(Decimal("2910.69")),
                    repayment_day=20,
                    repayment_hour=12,
                    start_year=2020,
                    start_month=3,
                ),
                expected_balances_at_ts={
                    first_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            (dimensions.INTEREST_DUE, "1019.18"),
                            (dimensions.PRINCIPAL, "297879.17"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI, "2910.69"),
                        ]
                    },
                    first_repayment_date.replace(month=3): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.INTEREST_DUE, "733.68"),
                            (dimensions.PRINCIPAL, "295702.16"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI, "2910.69"),
                        ]
                    },
                    first_repayment_date.replace(month=4): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI, "2910.69"),
                        ]
                    },
                    # holiday started on April repayment date, April repayment made
                    first_repayment_date.replace(month=5): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            # 293570.02 * 0.031/365 = 24.93334
                            # 24.93334 * 30 = 748.0002
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "748.0002",
                            ),
                            (dimensions.EMI, "2910.69"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-748.0002")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                    first_repayment_date.replace(month=6): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            # 293570.02 * 0.031/365 = 24.93334
                            # 24.93334 * 61 = 1520.93374
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "1520.93374",
                            ),
                            (dimensions.EMI, "2910.69"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-1520.93374")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                    first_repayment_date.replace(month=7): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            # 293570.02 * 0.031/365 = 24.93334
                            # 24.93334 * 91 = 2268.93394
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "2268.93394",
                            ),
                            (dimensions.EMI, "2910.69"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-2268.93394")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_repayment_date,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="120",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_first_repayment_due,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="119",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=at_event_b4_holiday_start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="117",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_event_b4_holiday_start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="117",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_holiday_end,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="117",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_holiday_end,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="117",
                    ),
                ],
            ),
            SubTest(
                description="repayment after repayment holiday",
                events=self.create_deposit_events(
                    num_payments=1,
                    repayment_amount=str(Decimal("2910.69")),
                    repayment_day=20,
                    repayment_hour=12,
                    start_year=2020,
                    start_month=8,
                ),
                expected_balances_at_ts={
                    first_repayment_date.replace(month=8, hour=2): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2131.78"),
                            (dimensions.INTEREST_DUE, "778.91"),
                            (dimensions.PRINCIPAL, "293707.17"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "2268.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI, "2910.69"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "2268.93")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_repayment_after_holiday,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="117",
                    ),
                ],
            ),
            SubTest(
                description="2nd repayment after repayment holiday",
                expected_balances_at_ts={
                    first_repayment_date.replace(month=9, hour=2): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2137.40"),
                            (dimensions.INTEREST_DUE, "773.29"),
                            (dimensions.PRINCIPAL, "291569.77"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "2268.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI, "2910.69"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "2268.93")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_2nd_repayment_after_holiday,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="116",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=fixed_rate_template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_monthly_interest_accrual_variable_increase_emi(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=6, day=13, minute=1, tzinfo=ZoneInfo("UTC"))

        payment_holiday_start = datetime(
            year=2020, month=6, day=12, hour=20, minute=2, tzinfo=ZoneInfo("UTC")
        )
        payment_holiday_end = datetime(
            year=2020, month=12, day=12, hour=0, minute=2, tzinfo=ZoneInfo("UTC")
        )

        events = [_set_up_repayment_holiday_flag(start)]

        events.append(
            create_flag_event(
                timestamp=start + timedelta(seconds=2),
                flag_definition_id=REPAYMENT_HOLIDAY_FLAG,
                account_id=self.loan_account_id,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )

        for event in self.input_data[
            "repayment_holiday_test_monthly_interest_accrual_variable_increase_emi"
        ]:
            if event[0] == "variable_rate_change":
                # Rate changes occurring just after repayment
                events.append(
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=int(event[1]),
                            month=int(event[2]),
                            day=int(event[3]),
                            tzinfo=ZoneInfo("UTC"),
                        ),
                        **{loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: str(event[4])}
                    )
                )
            else:
                # Repayments occur on repayment day
                events.extend(
                    self.create_deposit_events(
                        int(event[1]),
                        event[2],
                        12,
                        payment_hour,
                        int(event[3]),
                        int(event[4]),
                    )
                )

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

        sub_tests = [SubTest(description="Deposit events", events=events)]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=variable_rate_template_params,
            instance_params=variable_rate_instance_params,
        )

        res = self.run_test_scenario(test_scenario)

        balances = get_balances(res)

        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(
            self.expected_output[
                "repayment_holiday_test_monthly_interest_accrual_variable_increase_emi"
            ]
        ):
            expected_balances[self.loan_account_id][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
                (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, values[2]),
                (dimensions.CAPITALISED_INTEREST_TRACKER, values[3]),
                (dimensions.EMI, values[4]),
                (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal(str(i + 1))),
            ]

        self.check_balances(expected_balances=expected_balances, actual_balances=balances)

    def test_monthly_interest_accrual_variable_increase_term(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=2, day=13, minute=1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **variable_rate_instance_params,
            loan.repayment_holiday.PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE: "increase_term",
        }

        payment_holiday_start = datetime(
            year=2020, month=6, day=12, hour=20, minute=2, tzinfo=ZoneInfo("UTC")
        )
        payment_holiday_end = datetime(
            year=2020, month=12, day=12, hour=0, minute=2, tzinfo=ZoneInfo("UTC")
        )

        first_repayment_date = datetime(
            year=2020, month=2, day=12, minute=2, tzinfo=ZoneInfo("UTC")
        )
        at_event_b4_holiday_start = payment_holiday_start.replace(hour=0)
        after_event_b4_holiday_start = payment_holiday_start.replace(hour=1)
        before_first_repayment_date = first_repayment_date - relativedelta(hours=1)
        after_first_repayment_due = first_repayment_date + relativedelta(hours=1)
        before_holiday_end = payment_holiday_end - relativedelta(days=1)
        after_holiday_end = payment_holiday_end + relativedelta(hours=1)
        before_repayment_after_holiday = datetime(
            year=2021, month=1, day=11, hour=11, tzinfo=ZoneInfo("UTC")
        )
        before_2nd_repayment_after_holiday = datetime(
            year=2021, month=2, day=11, hour=11, tzinfo=ZoneInfo("UTC")
        )

        sub_tests = [
            SubTest(
                description="create flag definition and flag event",
                events=[
                    _set_up_repayment_holiday_flag(start),
                    create_flag_event(
                        timestamp=start + timedelta(seconds=2),
                        flag_definition_id=REPAYMENT_HOLIDAY_FLAG,
                        account_id=self.loan_account_id,
                        effective_timestamp=payment_holiday_start,
                        expiry_timestamp=payment_holiday_end,
                    ),
                ],
            ),
            SubTest(
                description="repayments up to end of repayment holiday",
                events=[
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2020,
                            month=2,
                            day=5,
                            tzinfo=ZoneInfo("UTC"),
                        ),
                        **{loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.039"}
                    )
                ]
                + self.create_deposit_events(
                    num_payments=1,
                    repayment_amount=str(Decimal("3034.40")),
                    repayment_day=12,
                    repayment_hour=12,
                    start_year=2020,
                    start_month=2,
                )
                + self.create_deposit_events(
                    num_payments=1,
                    # overpayment: 10,526.32, fee: 526.32, overpayment - fee: 10,000
                    repayment_amount=str(Decimal("3008.92") + Decimal("10000") + Decimal("526.32")),
                    repayment_day=12,
                    repayment_hour=12,
                    start_year=2020,
                    start_month=3,
                )
                + [
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2020,
                            month=3,
                            day=15,
                            tzinfo=ZoneInfo("UTC"),
                        ),
                        **{loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.041"}
                    ),
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=2020,
                            month=4,
                            day=10,
                            tzinfo=ZoneInfo("UTC"),
                        ),
                        **{loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.0322"}
                    ),
                ]
                + self.create_deposit_events(
                    num_payments=3,
                    repayment_amount=str(Decimal("2913.37")),
                    repayment_day=12,
                    repayment_hour=12,
                    start_year=2020,
                    start_month=4,
                ),
                expected_balances_at_ts={
                    first_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2173.03"),
                            (dimensions.INTEREST_DUE, "861.37"),
                            (dimensions.PRINCIPAL, "297826.97"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI, "3008.92"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ]
                    },
                    first_repayment_date.replace(month=3): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2109.73"),
                            (dimensions.INTEREST_DUE, "899.19"),
                            (dimensions.PRINCIPAL, "295717.24"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI, "3008.92"),
                            (dimensions.OVERPAYMENT, "0"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ]
                    },
                    first_repayment_date.replace(month=4): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "1966.51"),
                            (dimensions.INTEREST_DUE, "946.86"),
                            (dimensions.PRINCIPAL, "283750.73"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI, "2913.37"),
                            (dimensions.OVERPAYMENT, "10000"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "526.32")],
                    },
                    first_repayment_date.replace(month=5): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2185.72"),
                            (dimensions.INTEREST_DUE, "727.65"),
                            (dimensions.PRINCIPAL, "281565.01"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI, "2913.37"),
                            (dimensions.OVERPAYMENT, "10000"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("4")),
                        ]
                    },
                    first_repayment_date.replace(month=6): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2167.26"),
                            (dimensions.INTEREST_DUE, "746.11"),
                            (dimensions.PRINCIPAL, "279397.75"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI, "2913.37"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("5")),
                        ]
                    },
                    # holiday started on June repayment date, June repayment made
                    first_repayment_date.replace(month=7): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "279397.75"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("5")),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "716.48340",
                            ),
                            (dimensions.EMI, "2913.37"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-716.48340")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                    first_repayment_date.replace(month=8): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "279397.75"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("5")),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "1456.84958",
                            ),
                            (dimensions.EMI, "2913.37"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-1456.84958")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                    first_repayment_date.replace(month=9): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "279397.75"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "2197.21576",
                            ),
                            (dimensions.EMI, "2913.37"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("5")),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-2197.21576")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                    first_repayment_date.replace(month=10): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "279397.75"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "2913.69916",
                            ),
                            (dimensions.EMI, "2913.37"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("5")),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-2913.69916")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                    first_repayment_date.replace(month=11): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "279397.75"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "3654.06534",
                            ),
                            (dimensions.EMI, "2913.37"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("5")),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-3654.06534")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                    first_repayment_date.replace(month=12): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL, "279397.75"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "4370.54874",
                            ),
                            (dimensions.EMI, "2913.37"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("5")),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-4370.54874")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_repayment_date,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="120",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_first_repayment_due,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="119",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=at_event_b4_holiday_start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="111",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_event_b4_holiday_start,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="111",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=before_holiday_end,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="111",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_holiday_end,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="111",
                    ),
                ],
            ),
            SubTest(
                description="repayment after repayment holiday",
                events=self.create_deposit_events(
                    num_payments=1,
                    repayment_amount=str(Decimal("2913.37")),
                    repayment_day=12,
                    repayment_hour=12,
                    start_year=2021,
                    start_month=1,
                ),
                expected_balances_at_ts={
                    first_repayment_date.replace(year=2021, month=1): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2161.42"),
                            (dimensions.INTEREST_DUE, "751.95"),
                            (dimensions.PRINCIPAL, "281606.88"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "4370.55"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI, "2913.37"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("6")),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "4370.55")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_repayment_after_holiday,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="113",
                    ),
                ],
            ),
            SubTest(
                description="2nd repayment after repayment holiday",
                expected_balances_at_ts={
                    first_repayment_date.replace(year=2021, month=2): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2167.15"),
                            (dimensions.INTEREST_DUE, "746.22"),
                            (dimensions.PRINCIPAL, "279439.73"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "4370.55"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.EMI, "2913.37"),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("7")),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "4370.55")
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_2nd_repayment_after_holiday,
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
            template_params=variable_rate_template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_1_year_fixed_with_full_repayment(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=21, minute=1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **fixed_rate_instance_params,
            loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
            loan.disbursement.PARAM_PRINCIPAL: "18000",
        }

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=ZoneInfo("UTC")
        )
        payment_holiday_end = datetime(
            year=2020, month=7, day=20, hour=0, minute=2, tzinfo=ZoneInfo("UTC")
        )

        events = [_set_up_repayment_holiday_flag(start)]

        events.append(
            create_flag_event(
                timestamp=start + timedelta(seconds=2),
                flag_definition_id=REPAYMENT_HOLIDAY_FLAG,
                account_id=self.loan_account_id,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )

        events.extend(self.create_deposit_events(1, "1539.07", 20, payment_hour, 2020, 2))
        events.extend(self.create_deposit_events(2, "1525.31", 20, payment_hour, 2020, 3))

        # after repayment holiday
        events.extend(self.create_deposit_events(5, "2296.70", 20, payment_hour, 2020, 8))

        # Final repayment
        events.extend(self.create_deposit_events(1, "2297.94", 20, payment_hour, 2021, 1))

        sub_tests = [SubTest(description="Deposit events", events=events)]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=fixed_rate_template_params,
            instance_params=instance_params,
        )

        res = self.run_test_scenario(test_scenario)

        repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=2,
            second=0,
            microsecond=2,
            tzinfo=ZoneInfo("UTC"),
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(
            self.expected_output["repayment_holiday_1year_fixed_with_full_repayment"]
        ):
            expected_balances[self.loan_account_id][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL, values[0]),
                (dimensions.PRINCIPAL_DUE, values[1]),
                (dimensions.INTEREST_DUE, values[2]),
                (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, values[3]),
                (dimensions.CAPITALISED_INTEREST_TRACKER, values[4]),
            ]
        expected_balances[self.loan_account_id][end] = [
            (dimensions.PRINCIPAL, "0"),
            (dimensions.PRINCIPAL_DUE, "0"),
            (dimensions.INTEREST_DUE, "0"),
            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
            (dimensions.CAPITALISED_INTEREST_TRACKER, "104.74"),
        ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_daily_penalty_accrual_and_blocking(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=8, day=21, minute=1, tzinfo=ZoneInfo("UTC"))

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=ZoneInfo("UTC")
        )
        payment_holiday_end = datetime(
            year=2020, month=6, day=20, hour=20, minute=2, tzinfo=ZoneInfo("UTC")
        )

        first_repayment_date = datetime(
            year=2020, month=2, day=20, minute=2, tzinfo=ZoneInfo("UTC")
        )
        before_first_repayment_date = first_repayment_date - relativedelta(hours=1)
        after_first_repayment_due = first_repayment_date + relativedelta(hours=1)

        sub_tests = [
            SubTest(
                description="create flag definition and flag event",
                events=[
                    _set_up_repayment_holiday_flag(start),
                    create_flag_event(
                        timestamp=start + timedelta(seconds=2),
                        flag_definition_id=REPAYMENT_HOLIDAY_FLAG,
                        account_id=self.loan_account_id,
                        effective_timestamp=payment_holiday_start,
                        expiry_timestamp=payment_holiday_end,
                    ),
                ],
            ),
            SubTest(
                description="first EMI due",
                expected_balances_at_ts={
                    first_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            (dimensions.INTEREST_DUE, "1019.18"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_repayment_date,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="120",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_first_repayment_due,
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="119",
                    ),
                ],
            ),
            SubTest(
                description="first EMI overdue, incurring 15 late payment fee",
                expected_balances_at_ts={
                    datetime(year=2020, month=3, day=1, minute=2, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL, Decimal("297879.17")),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "1019.18"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("252.99320")),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.PENALTIES, "15"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
            ),
            SubTest(
                description="second EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=3, day=20, minute=2, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.INTEREST_DUE, "733.68"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "1019.18"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 3140.01*(0.24+0.031)/365 * 19 + 15 = 59.27
                            (dimensions.PENALTIES, "59.27"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
            ),
            SubTest(
                description="second EMI overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=3, day=30, minute=2, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 59.27 + 15 + 3140.01*(0.24+0.031)/365 * 10 = 97.57
                            (dimensions.PENALTIES, "97.57"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
            ),
            SubTest(
                description="third EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=4, day=20, minute=2, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 97.57 + (4297.84+1752.86)*(0.24+0.031)/365 * 21 = 191.86
                            (dimensions.PENALTIES, "191.86"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
            ),
            SubTest(
                description="repayment holiday starts, third EMI remains due, no overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=4, day=30, minute=2, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            # 293570.02 * 0.031/365 = 24.93334
                            # 24.93334 * 10 = 249.3334
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "249.33340",
                            ),
                            (dimensions.PENALTIES, "191.86"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-249.33340")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
            ),
            SubTest(
                description="repayment holiday ongoing, third EMI remains due",
                expected_balances_at_ts={
                    datetime(year=2020, month=5, day=20, minute=2, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            # 249.3 + 293570.02 * 0.031/365 = 24.93334
                            # 24.93334 * 30 = 748.0002
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "748.00020",
                            ),
                            (dimensions.PENALTIES, "191.86"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-748.00020")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
            ),
            SubTest(
                description="repayment holiday ongoing, no further overdue from check overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=5, day=30, minute=2, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            # 747.9 + 293570.02 * 0.031/365 * 10 = 997.33360
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "997.33360",
                            ),
                            (dimensions.PENALTIES, "191.86"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-997.33360")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
            ),
            SubTest(
                description="repayment holiday ongoing, no further due",
                expected_balances_at_ts={
                    datetime(year=2020, month=6, day=20, minute=2, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            # 997.2+ 293570.02 * 0.031/365 * 21 = 1520.93374
                            (
                                dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION,
                                "1520.93374",
                            ),
                            (dimensions.PENALTIES, "191.86"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-1520.93374")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0")
                        ],
                    }
                },
            ),
            SubTest(
                description="repayment holiday ended, third EMI overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=6, day=30, minute=2, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "1520.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "6429.98"),
                            (dimensions.INTEREST_OVERDUE, "2531.41"),
                            (dimensions.PRINCIPAL, "295090.95"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 191.86 + 15 + (4297.84+1752.86)*(0.24+0.031)/365 * 10 = 251.76
                            (dimensions.PENALTIES, "251.76"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1520.93")
                        ],
                    }
                },
            ),
            SubTest(
                description="fourth EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=7, day=20, minute=2, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            # EMI increased from 2910.69 to 2969.3
                            # due to capitalised interest added to principal
                            (dimensions.PRINCIPAL_DUE, "2217.42"),
                            (dimensions.INTEREST_DUE, "751.88"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "1520.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "6429.98"),
                            (dimensions.INTEREST_OVERDUE, "2531.41"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 251.76+ (6429.98+2531.41)*(0.24+0.031)/365 * 20 = 384.76
                            (dimensions.PENALTIES, "384.76"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1520.93")
                        ],
                    }
                },
            ),
            SubTest(
                description="fourth EMI overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=7, day=30, minute=2, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "1520.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "8647.4"),
                            (dimensions.INTEREST_OVERDUE, "3283.29"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 384.76+15+(6429.98+2531.41)*(0.24+0.031)/365*10 = 466.26
                            (dimensions.PENALTIES, "466.26"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1520.93")
                        ],
                    }
                },
            ),
            SubTest(
                description="fifth EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=8, day=20, minute=2, tzinfo=ZoneInfo("UTC")): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "2198.2"),
                            (dimensions.INTEREST_DUE, "771.1"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "1520.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "8647.4"),
                            (dimensions.INTEREST_OVERDUE, "3283.29"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 466.26+(8647.4+3283.29)*(0.24+0.031)/365*21 = 652.32
                            (dimensions.PENALTIES, "652.32"),
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1520.93")
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=fixed_rate_template_params,
            instance_params=fixed_rate_instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_monthly_rest_accrual_fixed_increase_emi(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=9, day=21, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **fixed_rate_instance_params,
            loan.PARAM_INTEREST_ACCRUAL_REST_TYPE: constants.MONTHLY,
        }

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=ZoneInfo("UTC")
        )
        payment_holiday_end = datetime(
            year=2020, month=7, day=20, hour=0, minute=2, tzinfo=ZoneInfo("UTC")
        )

        events = [_set_up_repayment_holiday_flag(start)]

        events.append(
            create_flag_event(
                timestamp=start + timedelta(seconds=2),
                flag_definition_id=REPAYMENT_HOLIDAY_FLAG,
                account_id=self.loan_account_id,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )

        events.extend(
            self.create_deposit_events(1, str(Decimal("3140.01")), 20, payment_hour, start_year, 2)
        )
        events.extend(
            self.create_deposit_events(2, str(Decimal("2910.69")), 20, payment_hour, start_year, 3)
        )

        sub_tests = [SubTest(description="Deposit events", events=events)]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=fixed_rate_template_params,
            instance_params=instance_params,
        )

        res = self.run_test_scenario(test_scenario)

        repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=2,
            second=0,
            microsecond=2,
            tzinfo=ZoneInfo("UTC"),
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(
            self.expected_output["repayment_holiday_test_monthly_rest_fixed_increase_emi"]
        ):
            expected_balances[self.loan_account_id][repayment_date + relativedelta(months=i)] = [
                (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                (dimensions.OVERPAYMENT, Decimal("0")),
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
                (dimensions.PRINCIPAL, values[2]),
                (dimensions.MONTHLY_REST_EFFECTIVE_PRINCIPAL, values[2]),
                (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, values[3]),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, values[4]),
                (dimensions.CAPITALISED_INTEREST_TRACKER, values[5]),
                (dimensions.EMI, values[6]),
            ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))


def _set_up_repayment_holiday_flag(start):
    return create_flag_definition_event(timestamp=start, flag_definition_id=REPAYMENT_HOLIDAY_FLAG)
