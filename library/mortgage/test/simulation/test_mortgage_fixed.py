# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from collections import defaultdict
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from itertools import chain

# library
from library.mortgage.contracts.template import mortgage
from library.mortgage.test import accounts, dimensions, parameters
from library.mortgage.test.simulation.common import MortgageTestBase

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
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

MORTGAGE_ACCOUNT = "MORTGAGE_ACCOUNT"
DEPOSIT_ACCOUNT = "DEPOSIT_ACCOUNT"

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
repayment_day = 28
payment_hour = 12
start_year = 2020

mortgage_template_params = {
    **parameters.mortgage_template_params,
    mortgage.PARAM_GRACE_PERIOD: "5",
    mortgage.overpayment_allowance.PARAM_CHECK_OVERPAYMENT_ALLOWANCE_MINUTE: "0",
    mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE: ("0.1"),
    mortgage.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.189965",
}
reduce_emi_template_params = {
    **mortgage_template_params,
    mortgage.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_emi",
}
mortgage_1_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_term": "48",
    "total_repayment_count": "48",
    "interest_only_term": "0",
    "principal": "300000",
    "due_amount_calculation_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.00",
}
mortgage_2_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_term": "120",
    "total_repayment_count": "120",
    "interest_only_term": "0",
    "principal": "300000",
    "due_amount_calculation_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.00",
}
mortgage_2_EMI = "2910.69"
mortgage_2_first_month_payment = str(Decimal("2910.69") + Decimal("229.32"))

mortgage_3_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_term": "12",
    "total_repayment_count": "12",
    "interest_only_term": "0",
    "principal": "30000",
    "due_amount_calculation_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.00",
}
mortgage_3_EMI = "2542.18"
mortgage_3_first_month_payment = "2565.11"


class MortgageFixedTest(MortgageTestBase):
    def test_monthly_due_for_fixed_rate_with_full_repayment(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=29, minute=1, tzinfo=timezone.utc)

        events = []

        events.extend(
            _set_up_deposit_events(
                1,
                mortgage_3_first_month_payment,
                repayment_day,
                payment_hour,
                start_year,
                2,
            )
        )
        events.extend(
            _set_up_deposit_events(11, mortgage_3_EMI, repayment_day, payment_hour, start_year, 3)
        )

        subtests = [
            SubTest(
                description="monthly due for fixed rate with full repayment",
                events=events,
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=subtests,
            template_params=mortgage_template_params,
            instance_params=mortgage_3_instance_params,
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
            tzinfo=timezone.utc,
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(self.expected_output["1year_monthly_repayment"]):
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
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
        end = datetime(year=2021, month=1, day=21, minute=1, tzinfo=timezone.utc)

        repayment_day = int(mortgage_2_instance_params["due_amount_calculation_day"])
        # first repayment includes 9 additional days interest
        # mortgage start date = 20200111 and repayment day = 20
        # daily rate (25.48) * additional days (9) = 229.32
        repayment_1 = _set_up_deposit_events(
            1,
            mortgage_2_first_month_payment,
            repayment_day,
            payment_hour,
            start_year,
            2,
        )
        repayment_2 = _set_up_deposit_events(
            11, mortgage_2_EMI, repayment_day, payment_hour, start_year, 3
        )
        events = list(chain.from_iterable([repayment_1, repayment_2]))

        subtests = [
            SubTest(
                description="monthly due for fixed rate",
                events=events,
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=subtests,
            template_params=mortgage_template_params,
            instance_params=mortgage_2_instance_params,
        )
        res = self.run_test_scenario(test_scenario)

        repayment_date = datetime(
            year=start_year, month=2, day=repayment_day, hour=1, tzinfo=timezone.utc
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(self.expected_output["monthly_due_fixed"]):
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
            ]

        self.check_balances(expected_balances, get_balances(res))

    def test_monthly_due_for_fixed_rate_with_one_overpayment(self):
        """
        Test for Fixed Rate Interest with an overpayment in month 3.
        """
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=21, minute=1, tzinfo=timezone.utc)

        repayment_day = int(mortgage_2_instance_params["due_amount_calculation_day"])
        # first repayment includes 9 additional days interest
        # mortgage start date = 20200111 and repayment day = 20
        # daily rate (25.48) * additional days (9) = 229.32
        repayment_1 = _set_up_deposit_events(
            1,
            mortgage_2_first_month_payment,
            repayment_day,
            payment_hour,
            start_year,
            2,
        )
        # second repayment includes overpayment
        repayment_2 = _set_up_deposit_events(
            1,
            str(Decimal(mortgage_2_EMI) + Decimal("10000")),
            repayment_day,
            1,
            start_year,
            3,
        )
        repayment_3 = _set_up_deposit_events(
            10, mortgage_2_EMI, repayment_day, payment_hour, start_year, 4
        )
        events = list(chain.from_iterable([repayment_1, repayment_2, repayment_3]))

        subtests = [
            SubTest(
                description="monthly due for fixed rate with one overpayment",
                events=events,
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=subtests,
            template_params=mortgage_template_params,
            instance_params=mortgage_2_instance_params,
        )
        res = self.run_test_scenario(test_scenario)

        repayment_date = datetime(
            year=start_year, month=2, day=repayment_day, minute=1, tzinfo=timezone.utc
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(self.expected_output["monthly_due_fixed_with_one_overpayment"]):
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
            ]

        self.check_balances(expected_balances, get_balances(res))

    def test_monthly_due_for_fixed_rate_with_regular_overpayment(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=2, day=20, minute=1, tzinfo=timezone.utc)
        first_payment_event = _set_up_deposit_events(
            1,
            str(Decimal(mortgage_3_first_month_payment) + Decimal("1000")),
            20,
            payment_hour,
            start_year,
            2,
        )
        repayment_with_overpayment = str(Decimal(mortgage_3_EMI) + Decimal("1000"))
        events = first_payment_event + _set_up_deposit_events(
            7, repayment_with_overpayment, 20, payment_hour, start_year, 3
        )

        subtests = [
            SubTest(
                description="monthly due for fixed rate with regular overpayment",
                events=events,
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=subtests,
            template_params=mortgage_template_params,
            instance_params=mortgage_3_instance_params,
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
            tzinfo=timezone.utc,
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(
            self.expected_output["monthly_due_fixed_with_regular_overpayment"]
        ):
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (dimensions.PRINCIPAL_DUE, values[0]),
                (dimensions.INTEREST_DUE, values[1]),
            ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_regular_overpayment_impact_preference_reduce_emi(self):
        start = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
        end = start + relativedelta(months=12, days=10)

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
        sixth_repayment_date = fifth_repayment_date + relativedelta(months=1)
        seventh_repayment_date = sixth_repayment_date + relativedelta(months=1)
        eighth_repayment_date = seventh_repayment_date + relativedelta(months=1)
        ninth_repayment_date = eighth_repayment_date + relativedelta(months=1)
        tenth_repayment_date = ninth_repayment_date + relativedelta(months=1)
        eleventh_repayment_date = tenth_repayment_date + relativedelta(months=1)
        final_repayment_date = eleventh_repayment_date + relativedelta(months=1)

        template_params = reduce_emi_template_params
        instance_params = {
            **mortgage_1_instance_params,
            "total_repayment_count": "12",
            "principal": "3000",
        }

        sub_tests = [
            SubTest(
                description="first month emi",
                expected_balances_at_ts={
                    first_repayment_date: {
                        MORTGAGE_ACCOUNT: [
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
                events=[
                    create_inbound_hard_settlement_instruction(
                        # emi plus additional interest from account creation
                        "356.51",
                        first_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "345.00",
                        second_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "334.82",
                        third_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "323.58",
                        fourth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "310.93",
                        fifth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "296.51",
                        sixth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "279.68",
                        seventh_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "259.53",
                        eighth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "234.38",
                        ninth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "200.87",
                        tenth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        # only paying the EMI amount instead of ending the mortgage early
                        "50.69",
                        eleventh_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        # final payment of remaining mortgage + overpayment charge
                        "85.68",
                        final_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    second_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "238.46"),
                            (dimensions.INTEREST_DUE, "6.54"),
                            (dimensions.EMI, "245.00"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "100"),
                        ]
                    },
                    third_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "228.72"),
                            (dimensions.INTEREST_DUE, "6.10"),
                            (dimensions.EMI, "234.82"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "200"),
                        ]
                    },
                    fourth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "218.52"),
                            (dimensions.INTEREST_DUE, "5.06"),
                            (dimensions.EMI, "223.58"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "300"),
                        ]
                    },
                    fifth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "206.54"),
                            (dimensions.INTEREST_DUE, "4.39"),
                            (dimensions.EMI, "210.93"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "400"),
                        ]
                    },
                    sixth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "193.04"),
                            (dimensions.INTEREST_DUE, "3.47"),
                            (dimensions.EMI, "196.51"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "500"),
                        ]
                    },
                    seventh_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "176.87"),
                            (dimensions.INTEREST_DUE, "2.81"),
                            (dimensions.EMI, "179.68"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "600"),
                        ]
                    },
                    eighth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "157.45"),
                            (dimensions.INTEREST_DUE, "2.08"),
                            (dimensions.EMI, "159.53"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "700"),
                        ]
                    },
                    ninth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "133.02"),
                            (dimensions.INTEREST_DUE, "1.36"),
                            (dimensions.EMI, "134.38"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "800"),
                        ]
                    },
                    tenth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "100.08"),
                            (dimensions.INTEREST_DUE, "0.79"),
                            (dimensions.EMI, "100.87"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "900"),
                        ]
                    },
                    eleventh_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "50.43"),
                            (dimensions.INTEREST_DUE, "0.26"),
                            (dimensions.EMI, "50.69"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "1000"),
                        ]
                    },
                    final_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            # last payment rounds to remaining principal
                            # instead of using stored EMI
                            # hence total due is 50.68 instead of equal to EMI 50.69
                            (dimensions.PRINCIPAL_DUE, "50.55"),
                            (dimensions.INTEREST_DUE, "0.13"),
                            (dimensions.EMI, "50.69"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "1000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            # overpayment fee event ran on 2021/01/11
                            # total overpayment = 1000
                            # allowance 3000 * 0.1 = 300
                            # overpaid above allowance = 1000 - 300 = 700
                            # fee = 700 * 0.05 = 35
                            (dimensions.PENALTIES, "35"),
                        ]
                    },
                    final_repayment_date
                    + relativedelta(hours=6): {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.EMI, "50.69"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "1000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                            # v3-v4: principal balance now reflects actual principal, not expected
                            # (dimensions.PRINCIPAL, "1000"),
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PENALTIES, "0"),
                            # v3-v4: v3 doesn't add excess for last repayment, but this has no
                            # impact as it would only be used in the next due amount calculation
                            # which can't happen
                            # (
                            #     BalanceDimensions(address="EMI_PRINCIPAL_EXCESS"),
                            #     "-14.36",
                            # ),
                            (
                                BalanceDimensions(address="EMI_PRINCIPAL_EXCESS"),
                                "17.03",
                            ),
                            (
                                BalanceDimensions(address="PRINCIPAL_CAPITALISED_INTEREST"),
                                "0",
                            ),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=first_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="11",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=second_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="8",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fifth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="7",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=sixth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="6",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=seventh_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="5",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eighth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="4",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=ninth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="3",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=tenth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eleventh_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=final_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="0",
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=final_repayment_date + relativedelta(hours=5),
                        notification_type=mortgage.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.MORTGAGE_ACCOUNT,
                        },
                        resource_id=accounts.MORTGAGE_ACCOUNT,
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
        start = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
        end = start + relativedelta(months=12, days=10)

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
        sixth_repayment_date = fifth_repayment_date + relativedelta(months=1)
        seventh_repayment_date = sixth_repayment_date + relativedelta(months=1)
        eighth_repayment_date = seventh_repayment_date + relativedelta(months=1)
        ninth_repayment_date = eighth_repayment_date + relativedelta(months=1)
        tenth_repayment_date = ninth_repayment_date + relativedelta(months=1)
        eleventh_repayment_date = tenth_repayment_date + relativedelta(months=1)
        final_repayment_date = eleventh_repayment_date + relativedelta(months=1)

        template_params = reduce_emi_template_params
        instance_params = {
            **mortgage_1_instance_params,
            "total_repayment_count": "12",
            "principal": "3000",
        }

        sub_tests = [
            SubTest(
                description="first month emi",
                expected_balances_at_ts={
                    first_repayment_date: {
                        MORTGAGE_ACCOUNT: [
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
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
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
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "254.22",
                        second_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        "254.22",
                        third_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    second_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "247.44"),
                            (dimensions.INTEREST_DUE, "6.78"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    third_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "247.62"),
                            (dimensions.INTEREST_DUE, "6.60"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    fourth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "248.47"),
                            (dimensions.INTEREST_DUE, "5.75"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=second_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="10",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=third_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="9",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=fourth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="8",
                    ),
                ],
            ),
            SubTest(
                description="single overpayments of 250",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "504.22",
                        fourth_repayment_date + relativedelta(hours=5),
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    fifth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "217.95"),
                            (dimensions.INTEREST_DUE, "4.63"),
                            (dimensions.EMI, "222.58"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=fifth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="7",
                    ),
                ],
            ),
            SubTest(
                description="normal payments for the rest of lifetime",
                events=_set_up_deposit_events(
                    7,
                    "222.58",
                    repayment_day,
                    payment_hour,
                    2020,
                    6,
                ),
                expected_balances_at_ts={
                    sixth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "218.65"),
                            (dimensions.INTEREST_DUE, "3.93"),
                            (dimensions.EMI, "222.58"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                    seventh_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "219.10"),
                            (dimensions.INTEREST_DUE, "3.48"),
                            (dimensions.EMI, "222.58"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                    eighth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "219.67"),
                            (dimensions.INTEREST_DUE, "2.91"),
                            (dimensions.EMI, "222.58"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                    ninth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "220.33"),
                            (dimensions.INTEREST_DUE, "2.25"),
                            (dimensions.EMI, "222.58"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                    tenth_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "220.83"),
                            (dimensions.INTEREST_DUE, "1.75"),
                            (dimensions.EMI, "222.58"),
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                    eleventh_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "221.45"),
                            (dimensions.INTEREST_DUE, "1.13"),
                            (dimensions.EMI, "222.58"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "250"),
                        ]
                    },
                    final_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "222.17"),
                            (dimensions.INTEREST_DUE, "0.58"),
                            (dimensions.EMI, "222.58"),
                            # v3-v4: overpayment tracker is positive now
                            (dimensions.OVERPAYMENT, "250"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=sixth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="6",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=seventh_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="5",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eighth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="4",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=ninth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="3",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=tenth_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="2",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=eleventh_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="1",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=final_repayment_date + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
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
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    )
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=final_repayment_date + relativedelta(hours=5),
                        notification_type=mortgage.CLOSURE_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.MORTGAGE_ACCOUNT,
                        },
                        resource_id=accounts.MORTGAGE_ACCOUNT,
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
