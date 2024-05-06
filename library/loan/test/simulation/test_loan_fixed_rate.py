# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from itertools import chain
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
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import get_balances

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
repayment_day = 28
payment_hour = 12
start_year = 2020
start_month = 1
four_year_300000_principal_EMI = "6653.57"
four_year_300000_principal_first_month_payment = "6882.89"
ten_year_300000_principal_first_month_payment = str(Decimal("2910.69") + Decimal("229.32"))
ten_year_300000_principal_EMI = "2910.69"
one_year_30000_principal_EMI = "2542.18"
one_year_30000_principal_first_month_payment = "2565.11"

# All loans in these tests are fixed rate
fixed_rate_instance_params = {
    **parameters.loan_instance_params,
    loan.PARAM_FIXED_RATE_LOAN: "True",
    loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "20",
    loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
    loan.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "0.00",
}
fixed_rate_template_params = {
    **parameters.loan_template_params,
    loan.PARAM_ACCRUE_ON_DUE_PRINCIPAL: "False",
    loan.PARAM_AMORTISATION_METHOD: "declining_principal",
    loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "no_capitalisation",
    loan.PARAM_GRACE_PERIOD: "5",
    loan.PARAM_LATE_REPAYMENT_FEE: "15",
    loan.PARAM_PENALTY_INCLUDES_BASE_RATE: "True",
    loan.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "True",
    loan.overdue.PARAM_REPAYMENT_PERIOD: "10",
    loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0.05",
    loan.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: loan.overpayment.REDUCE_TERM,
    loan.early_repayment.PARAM_EARLY_REPAYMENT_FLAT_FEE: "0",
    loan.early_repayment.PARAM_EARLY_REPAYMENT_FEE_RATE: "0",
}

four_year_300000_principal_instance_params = {
    **fixed_rate_instance_params,
    loan.disbursement.PARAM_PRINCIPAL: "300000",
    loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "48",
}

ten_year_300000_principal_instance_params = {
    **fixed_rate_instance_params,
    loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "120",
    loan.disbursement.PARAM_PRINCIPAL: "300000",
}

one_year_30000_principal_instance_params = {
    **fixed_rate_instance_params,
    loan.disbursement.PARAM_PRINCIPAL: "30000",
    loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
}

one_year_3000_principal_instance_params = {
    **fixed_rate_instance_params,
    loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
    loan.disbursement.PARAM_PRINCIPAL: "3000",
}


class LoanFixedRateTest(LoanTestBase):
    def test_monthly_due_for_fixed_rate_with_full_repayment(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=29, minute=1, tzinfo=ZoneInfo("UTC"))

        events = []

        events.extend(
            self.create_deposit_events(
                num_payments=1,
                repayment_amount=one_year_30000_principal_first_month_payment,
                repayment_day=repayment_day,
                repayment_hour=payment_hour,
                start_year=start_year,
                start_month=2,
            )
        )
        events.extend(
            self.create_deposit_events(
                11, one_year_30000_principal_EMI, repayment_day, payment_hour, start_year, 3
            )
        )

        sub_tests = [SubTest(description="Deposit events", events=events)]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=fixed_rate_template_params,
            instance_params=one_year_30000_principal_instance_params,
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
        for i, values in enumerate(self.expected_output["1year_monthly_repayment"]):
            expected_balances[self.loan_account_id][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL, values[0]),
                (dimensions.PRINCIPAL_DUE, values[1]),
                (dimensions.INTEREST_DUE, values[2]),
            ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_monthly_due_for_fixed_rate(self):
        """
        Test for Fixed Rate Interest.
        """
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=21, minute=1, tzinfo=ZoneInfo("UTC"))

        repayment_day = int(
            ten_year_300000_principal_instance_params[
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
            ]
        )
        # first repayment includes 9 additional days interest
        # loan start date = 20200111 and repayment day = 20
        # daily rate (25.48) * additional days (9) = 229.32
        repayment_1 = self.create_deposit_events(
            num_payments=1,
            repayment_amount=ten_year_300000_principal_first_month_payment,
            repayment_day=repayment_day,
            repayment_hour=payment_hour,
            start_year=start_year,
            start_month=2,
        )
        repayment_2 = self.create_deposit_events(
            num_payments=11,
            repayment_amount=ten_year_300000_principal_EMI,
            repayment_day=repayment_day,
            repayment_hour=payment_hour,
            start_year=start_year,
            start_month=3,
        )
        events = list(chain.from_iterable([repayment_1, repayment_2]))

        sub_tests = [SubTest(description="Deposit events", events=events)]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=fixed_rate_template_params,
            instance_params=ten_year_300000_principal_instance_params,
        )

        res = self.run_test_scenario(test_scenario)

        repayment_date = datetime(
            year=start_year, month=2, day=repayment_day, hour=1, tzinfo=ZoneInfo("UTC")
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(self.expected_output["monthly_due_fixed"]):
            expected_balances[self.loan_account_id][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
            ]

        self.check_balances(expected_balances, get_balances(res))

    def test_monthly_due_for_fixed_rate_with_one_overpayment(self):
        """
        Test for Fixed Rate Interest with an overpayment in month 3.
        """
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=21, minute=1, tzinfo=ZoneInfo("UTC"))

        repayment_day = int(
            ten_year_300000_principal_instance_params[
                loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
            ]
        )
        # first repayment includes 9 additional days interest
        # loan start date = 20200111 and repayment day = 20
        # daily rate (25.48) * additional days (9) = 229.32
        repayment_1 = self.create_deposit_events(
            num_payments=1,
            repayment_amount=ten_year_300000_principal_first_month_payment,
            repayment_day=repayment_day,
            repayment_hour=payment_hour,
            start_year=start_year,
            start_month=2,
        )
        # second repayment includes overpayment
        # overpayment: 10,526.32, fee: 526.32, overpayment - fee: 10,000
        repayment_2 = self.create_deposit_events(
            num_payments=1,
            repayment_amount=str(
                Decimal(ten_year_300000_principal_EMI) + Decimal("10000") + Decimal("526.32")
            ),
            repayment_day=repayment_day,
            repayment_hour=1,
            start_year=start_year,
            start_month=3,
        )
        repayment_3 = self.create_deposit_events(
            num_payments=10,
            repayment_amount=ten_year_300000_principal_EMI,
            repayment_day=repayment_day,
            repayment_hour=payment_hour,
            start_year=start_year,
            start_month=4,
        )
        events = list(chain.from_iterable([repayment_1, repayment_2, repayment_3]))

        sub_tests = [SubTest(description="Deposit events", events=events)]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=fixed_rate_template_params,
            instance_params=ten_year_300000_principal_instance_params,
        )

        res = self.run_test_scenario(test_scenario)

        repayment_date = datetime(
            year=start_year, month=2, day=repayment_day, minute=1, tzinfo=ZoneInfo("UTC")
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(self.expected_output["monthly_due_fixed_with_one_overpayment"]):
            expected_balances[self.loan_account_id][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
            ]

        expected_balances[self.loan_account_id][end] = [(dimensions.OVERPAYMENT, "10000")]
        expected_balances[accounts.INTERNAL_OVERPAYMENT_FEE_INCOME][end] = [
            (dimensions.DEFAULT, "526.32")
        ]

        self.check_balances(expected_balances, get_balances(res))

    def test_monthly_due_for_fixed_rate_with_regular_overpayment(self):
        """
        Test for Fixed Rate Interest with a regular overpayment every month.
        """
        start = default_simulation_start_date
        end = datetime(year=2021, month=11, day=21, minute=1, tzinfo=ZoneInfo("UTC"))

        # overpayment: 1,052.63, fee: 52.63, overpayment - fee: 1,000
        first_payment_event = self.create_deposit_events(
            num_payments=1,
            repayment_amount=str(
                Decimal(one_year_30000_principal_first_month_payment)
                + Decimal("1000")
                + Decimal("52.63")
            ),
            repayment_day=20,
            repayment_hour=payment_hour,
            start_year=start_year,
            start_month=2,
        )
        repayment_with_overpayment = str(
            Decimal(one_year_30000_principal_EMI) + Decimal("1000") + Decimal("52.63")
        )
        events = first_payment_event + self.create_deposit_events(
            num_payments=7,
            repayment_amount=repayment_with_overpayment,
            repayment_day=20,
            repayment_hour=payment_hour,
            start_year=start_year,
            start_month=3,
        )

        sub_tests = [SubTest(description="Deposit events", events=events)]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=fixed_rate_template_params,
            instance_params=one_year_30000_principal_instance_params,
        )

        res = self.run_test_scenario(test_scenario)

        repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=ZoneInfo("UTC"),
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(
            self.expected_output["monthly_due_fixed_with_regular_overpayment"]
        ):
            expected_balances[self.loan_account_id][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
            ]

        # 8 overpayments of 1,000 each (not including fee) = total overpayment 41,000
        # total overpayment fees = 8 * 52.63 = 421.04
        expected_balances[self.loan_account_id][end] = [(dimensions.OVERPAYMENT, "8000")]
        expected_balances[accounts.INTERNAL_OVERPAYMENT_FEE_INCOME][end] = [
            (dimensions.DEFAULT, "421.04")
        ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_monthly_due_for_fixed_rate_with_accrue_on_due_principal(self):
        start = default_simulation_start_date
        end = datetime(year=2024, month=2, day=28, minute=1, tzinfo=ZoneInfo("UTC"))
        template_params = {
            **fixed_rate_template_params,
            loan.PARAM_ACCRUE_ON_DUE_PRINCIPAL: "True",
        }

        repayment_date = datetime(
            year=start_year,
            month=1,
            day=20,
            hour=0,
            minute=1,
            second=0,
            tzinfo=ZoneInfo("UTC"),
        )

        before_first_repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=0,
            second=30,
            tzinfo=ZoneInfo("UTC"),
        )
        after_first_repayment_date = before_first_repayment_date + relativedelta(minute=1)

        first_payment_date = datetime(
            year=start_year,
            month=2,
            day=repayment_day,
            hour=payment_hour,
            tzinfo=ZoneInfo("UTC"),
        )
        before_first_payment_date = first_payment_date - relativedelta(minutes=1)
        after_first_payment_date = first_payment_date + relativedelta(minutes=1)

        before_final_repayment_date = datetime(
            year=2024,
            month=1,
            day=20,
            hour=0,
            minute=0,
            second=30,
            tzinfo=ZoneInfo("UTC"),
        )
        after_final_repayment_date = before_final_repayment_date + relativedelta(minutes=1)
        final_payment_amount = "6869.86"
        final_payment_date = datetime(
            year=2024,
            month=1,
            day=repayment_day,
            hour=payment_hour,
            tzinfo=ZoneInfo("UTC"),
        )
        before_final_payment_date = final_payment_date - relativedelta(minutes=1)
        after_final_payment_date = final_payment_date + relativedelta(minutes=1)

        before_additional_repayment_date = datetime(
            year=2024,
            month=2,
            day=20,
            hour=0,
            minute=0,
            second=30,
            tzinfo=ZoneInfo("UTC"),
        )
        after_additional_repayment_date = before_additional_repayment_date + relativedelta(
            minutes=1
        )

        sub_tests = [
            SubTest(
                description="check balances first repayment date",
                expected_balances_at_ts={
                    start: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "300000"),
                        ]
                    },
                    # 0.031/365 * 300000 = 25.47945
                    # 25.47945 * 40 = 1019.17800
                    before_first_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "300000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "1019.17800"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-1019.17800"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                    after_first_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "294136.29"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.PRINCIPAL_DUE, "5863.71"),
                            (dimensions.INTEREST_DUE, "1019.18"),
                            (dimensions.EMI, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1019.18"),
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances after first payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount=four_year_300000_principal_first_month_payment,
                        event_datetime=first_payment_date,
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    # 0.031/365 * (294136.29+5863.71) = 25.47945
                    # 25.47945 * 8 = 203.8356
                    before_first_payment_date: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "294136.29"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "203.8356"),
                            (dimensions.PRINCIPAL_DUE, "5863.71"),
                            (dimensions.INTEREST_DUE, "1019.18"),
                            (dimensions.EMI, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-203.8356"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1019.18"),
                        ],
                    },
                    after_first_payment_date: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "294136.29"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "203.8356"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-203.8356"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1019.18"),
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances second repayment date",
                expected_balances_at_ts={
                    before_first_repayment_date
                    + relativedelta(months=1): {
                        # 0.031/365 * 294136.29 = 24.98144
                        # 203.8356 + 24.98144 * 21 = 203.8356 + 524.61024 = 728.44584
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "294136.29"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "728.44584"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-728.44584"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1019.18"),
                        ],
                    },
                    after_first_repayment_date
                    + relativedelta(months=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "288211.17"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.PRINCIPAL_DUE, "5925.12"),
                            (dimensions.INTEREST_DUE, "728.45"),
                            (dimensions.EMI, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1747.63"),
                        ],
                    },
                },
            ),
            SubTest(
                description="check balances after second payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount=four_year_300000_principal_EMI,
                        event_datetime=first_payment_date + relativedelta(months=1),
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    # 0.031/365 * (288211.17+5925.12) = 24.98144
                    # 24.98144 * 8 = 199.85152
                    before_first_payment_date
                    + relativedelta(months=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "288211.17"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "199.85152"),
                            (dimensions.PRINCIPAL_DUE, "5925.12"),
                            (dimensions.INTEREST_DUE, "728.45"),
                            (dimensions.EMI, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-199.85152"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1747.63"),
                        ],
                    },
                    after_first_payment_date
                    + relativedelta(months=1): {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "288211.17"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "199.85152"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "-199.85152"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "1747.63"),
                        ],
                    },
                },
            ),
            SubTest(
                description="payments",
                events=self.create_deposit_events(
                    num_payments=45,
                    repayment_amount=four_year_300000_principal_EMI,
                    repayment_day=repayment_day,
                    repayment_hour=payment_hour,
                    start_year=2020,
                    start_month=4,
                ),
            ),
            SubTest(
                description="check balances final repayment date",
                expected_balances_at_ts={
                    before_final_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "6847.34"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "22.52253"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                    after_final_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.PRINCIPAL_DUE, "6847.34"),
                            (dimensions.INTEREST_DUE, "22.52"),
                            (dimensions.EMI, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="check balances final payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=self.loan_account_id,
                        amount=final_payment_amount,
                        event_datetime=final_payment_date,
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    # 0.031/365 * (6847.34) = 0.58155
                    # 0.58155 * 8 = 4.65240
                    before_final_payment_date: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "4.65240"),
                            (dimensions.PRINCIPAL_DUE, "6847.34"),
                            (dimensions.INTEREST_DUE, "22.52"),
                            (dimensions.EMI, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                    after_final_payment_date: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "4.65240"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=final_payment_date,
                        account_id=self.loan_account_id,
                        name=loan.due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE,
                        value="2024-01-20",
                    ),
                ],
            ),
            SubTest(
                description="check balances additional repayment date",
                expected_balances_at_ts={
                    before_additional_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "4.65240"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ]
                    },
                    after_additional_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "4.65"),
                            (dimensions.EMI, "6653.57"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: [
                            (dimensions.DEFAULT, "0"),
                        ],
                        accounts.INTERNAL_INTEREST_RECEIVED: [
                            (dimensions.DEFAULT, "19821.62"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=repayment_date + relativedelta(months=1),
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": "6882.89",
                            "overdue_date": "2020-03-01",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=repayment_date + relativedelta(months=3),
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": "6653.57",
                            "overdue_date": "2020-04-30",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=repayment_date + relativedelta(months=6),
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": "6653.57",
                            "overdue_date": "2020-07-30",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=before_additional_repayment_date
                        + relativedelta(minute=1, second=0),
                        notification_type=loan.REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                            "repayment_amount": "4.65",
                            "overdue_date": "2024-03-01",
                        },
                        resource_id=f"{self.loan_account_id}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=four_year_300000_principal_instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_regular_overpayment_impact_preference_reduce_emi(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(months=12, days=10)

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
        sixth_repayment_date = fifth_repayment_date + relativedelta(months=1)
        seventh_repayment_date = sixth_repayment_date + relativedelta(months=1)
        eighth_repayment_date = seventh_repayment_date + relativedelta(months=1)
        ninth_repayment_date = eighth_repayment_date + relativedelta(months=1)
        tenth_repayment_date = ninth_repayment_date + relativedelta(months=1)
        eleventh_repayment_date = tenth_repayment_date + relativedelta(months=1)
        final_repayment_date = eleventh_repayment_date + relativedelta(months=1)

        template_params = {
            **fixed_rate_template_params,
            loan.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_emi",
        }
        instance_params = one_year_3000_principal_instance_params

        sub_tests = [
            SubTest(
                description="first month emi",
                expected_balances_at_ts={
                    first_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "246.32"),
                            (dimensions.INTEREST_DUE, "10.19"),
                            (dimensions.EMI, "254.22"),
                            (dimensions.OVERPAYMENT, "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="regular overpayments of 100",
                # overpayment: 105.26, fee: 5.26, overpayment - fee: 100
                events=[
                    create_inbound_hard_settlement_instruction(
                        # emi plus additional interest from account creation
                        str(Decimal("356.51") + Decimal("5.26")),
                        first_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("345.00") + Decimal("5.26")),
                        second_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("334.82") + Decimal("5.26")),
                        third_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("323.58") + Decimal("5.26")),
                        fourth_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("310.93") + Decimal("5.26")),
                        fifth_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("296.51") + Decimal("5.26")),
                        sixth_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("279.68") + Decimal("5.26")),
                        seventh_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("259.53") + Decimal("5.26")),
                        eighth_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("234.38") + Decimal("5.26")),
                        ninth_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("200.87") + Decimal("5.26")),
                        tenth_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        # only paying the EMI amount instead of ending the loan early
                        "50.69",
                        eleventh_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        # final payment of remaining loan + overpayment charge
                        "50.68",
                        final_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    second_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "238.46"),
                            (dimensions.INTEREST_DUE, "6.54"),
                            (dimensions.EMI, "245.00"),
                            (dimensions.OVERPAYMENT, "100"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "5.26")],
                    },
                    third_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "228.72"),
                            (dimensions.INTEREST_DUE, "6.10"),
                            (dimensions.EMI, "234.82"),
                            (dimensions.OVERPAYMENT, "200"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "10.52")],
                    },
                    fourth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "218.52"),
                            (dimensions.INTEREST_DUE, "5.06"),
                            (dimensions.EMI, "223.58"),
                            (dimensions.OVERPAYMENT, "300"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "15.78")],
                    },
                    fifth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "206.54"),
                            (dimensions.INTEREST_DUE, "4.39"),
                            (dimensions.EMI, "210.93"),
                            (dimensions.OVERPAYMENT, "400"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "21.04")],
                    },
                    sixth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "193.04"),
                            (dimensions.INTEREST_DUE, "3.47"),
                            (dimensions.EMI, "196.51"),
                            (dimensions.OVERPAYMENT, "500"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "26.30")],
                    },
                    seventh_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "176.87"),
                            (dimensions.INTEREST_DUE, "2.81"),
                            (dimensions.EMI, "179.68"),
                            (dimensions.OVERPAYMENT, "600"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "31.56")],
                    },
                    eighth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "157.45"),
                            (dimensions.INTEREST_DUE, "2.08"),
                            (dimensions.EMI, "159.53"),
                            (dimensions.OVERPAYMENT, "700"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "36.82")],
                    },
                    ninth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "133.02"),
                            (dimensions.INTEREST_DUE, "1.36"),
                            (dimensions.EMI, "134.38"),
                            (dimensions.OVERPAYMENT, "800"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "42.08")],
                    },
                    tenth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "100.08"),
                            (dimensions.INTEREST_DUE, "0.79"),
                            (dimensions.EMI, "100.87"),
                            (dimensions.OVERPAYMENT, "900"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "47.34")],
                    },
                    eleventh_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "50.43"),
                            (dimensions.INTEREST_DUE, "0.26"),
                            (dimensions.EMI, "50.69"),
                            (dimensions.OVERPAYMENT, "1000"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "52.60")],
                    },
                    final_repayment_date: {
                        self.loan_account_id: [
                            # last payment rounds to remaining principal
                            # instead of using stored EMI
                            # hence total due is 50.68 instead of equal to EMI 50.69
                            (dimensions.PRINCIPAL_DUE, "50.55"),
                            (dimensions.INTEREST_DUE, "0.13"),
                            (dimensions.EMI, "50.69"),
                            (dimensions.OVERPAYMENT, "1000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            # total overpayment = 1000
                            (dimensions.PENALTIES, "0"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "52.60")],
                    },
                    final_repayment_date
                    + relativedelta(hours=6): {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "50.69"),
                            (dimensions.OVERPAYMENT, "1000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.EMI_PRINCIPAL_EXCESS, "17.03"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                        ],
                        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: [(dimensions.DEFAULT, "52.60")],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="8",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fifth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="7",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="6",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=seventh_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="5",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eighth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="4",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=ninth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="3",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=tenth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eleventh_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=final_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=final_repayment_date + relativedelta(hours=5),
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
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

    def test_one_off_overpayment_impact_preference_reduce_emi(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(months=12, days=10)

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
        sixth_repayment_date = fifth_repayment_date + relativedelta(months=1)
        seventh_repayment_date = sixth_repayment_date + relativedelta(months=1)
        eighth_repayment_date = seventh_repayment_date + relativedelta(months=1)
        ninth_repayment_date = eighth_repayment_date + relativedelta(months=1)
        tenth_repayment_date = ninth_repayment_date + relativedelta(months=1)
        eleventh_repayment_date = tenth_repayment_date + relativedelta(months=1)
        final_repayment_date = eleventh_repayment_date + relativedelta(months=1)

        template_params = {
            **fixed_rate_template_params,
            loan.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: loan.overpayment.REDUCE_EMI,
        }
        instance_params = one_year_3000_principal_instance_params

        sub_tests = [
            SubTest(
                description="first month emi",
                expected_balances_at_ts={
                    first_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "246.32"),
                            (dimensions.INTEREST_DUE, "10.19"),
                            (dimensions.EMI, "254.22"),
                            (dimensions.OVERPAYMENT, "0"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="11",
                    ),
                ],
            ),
            SubTest(
                description="repayments without overpayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "256.51",
                        first_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "254.22",
                        second_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "254.22",
                        third_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    ),
                ],
                expected_balances_at_ts={
                    second_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "247.44"),
                            (dimensions.INTEREST_DUE, "6.78"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    third_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "247.62"),
                            (dimensions.INTEREST_DUE, "6.60"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    fourth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "248.47"),
                            (dimensions.INTEREST_DUE, "5.75"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="8",
                    ),
                ],
            ),
            SubTest(
                description="single overpayments of 250",
                # overpayment: 263.16, fee: 13.16, overpayment - fee: 250
                events=[
                    create_inbound_hard_settlement_instruction(
                        str(Decimal("504.22") + Decimal("13.16")),
                        fourth_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_balances_at_ts={
                    fifth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "217.95"),
                            (dimensions.INTEREST_DUE, "4.63"),
                            (dimensions.EMI, "222.58"),
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fifth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="7",
                    ),
                ],
            ),
            SubTest(
                description="normal payments for the rest of lifetime",
                events=self.create_deposit_events(
                    7,
                    "222.58",
                    repayment_day,
                    payment_hour,
                    2020,
                    6,
                ),
                expected_balances_at_ts={
                    sixth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "218.65"),
                            (dimensions.INTEREST_DUE, "3.93"),
                            (dimensions.EMI, "222.58"),
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                    seventh_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "219.10"),
                            (dimensions.INTEREST_DUE, "3.48"),
                            (dimensions.EMI, "222.58"),
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                    eighth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "219.67"),
                            (dimensions.INTEREST_DUE, "2.91"),
                            (dimensions.EMI, "222.58"),
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                    ninth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "220.33"),
                            (dimensions.INTEREST_DUE, "2.25"),
                            (dimensions.EMI, "222.58"),
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                    tenth_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "220.83"),
                            (dimensions.INTEREST_DUE, "1.75"),
                            (dimensions.EMI, "222.58"),
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                    eleventh_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "221.45"),
                            (dimensions.INTEREST_DUE, "1.13"),
                            (dimensions.EMI, "222.58"),
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                    final_repayment_date: {
                        self.loan_account_id: [
                            (dimensions.PRINCIPAL_DUE, "222.17"),
                            (dimensions.INTEREST_DUE, "0.58"),
                            (dimensions.EMI, "222.58"),
                            (dimensions.OVERPAYMENT, "250"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=sixth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="6",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=seventh_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="5",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eighth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="4",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=ninth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="3",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=tenth_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eleventh_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=final_repayment_date + relativedelta(hours=1),
                        account_id=self.loan_account_id,
                        name=loan.derived_params.PARAM_REMAINING_TERM,
                        value="0",
                    ),
                ],
            ),
            SubTest(
                description="final repayment closes account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # final EMI + residual
                        "222.75",
                        final_repayment_date + relativedelta(hours=5),
                        target_account_id=self.loan_account_id,
                        internal_account_id=accounts.DEPOSIT,
                    )
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=final_repayment_date + relativedelta(hours=5),
                        notification_type=loan.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": self.loan_account_id,
                        },
                        resource_id=self.loan_account_id,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
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
