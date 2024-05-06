# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal

# library
from library.mortgage.contracts.template import mortgage
from library.mortgage.test import accounts, dimensions, parameters
from library.mortgage.test.simulation.common import MortgageTestBase

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedRejection,
    ExpectedSchedule,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import get_contract_notifications

MORTGAGE_ACCOUNT = "MORTGAGE_ACCOUNT"
DEPOSIT_ACCOUNT = "DEPOSIT_ACCOUNT"

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
payment_hour = 12
start_year = 2020
mortgage_2_first_month_payment = str(Decimal("2910.69") + Decimal("229.32"))
mortgage_2_EMI = "2910.69"

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

mortgage_1_template_params = {
    **parameters.mortgage_template_params,
    mortgage.PARAM_GRACE_PERIOD: "5",
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

mortgage_2_template_params = {
    **mortgage_1_template_params,
    mortgage.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.189965",
}


class MortgageTest(MortgageTestBase):
    def test_change_repayment_day_after(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=1, minute=1, tzinfo=timezone.utc)
        sub_tests = []
        events = []
        for event in self.input_data["change_repayment_day_after"]:
            if event[0] == "repayment_day_change":
                events.append(
                    create_instance_parameter_change_event(
                        timestamp=datetime(
                            year=int(event[1]),
                            month=int(event[2]),
                            day=int(event[3]),
                            tzinfo=timezone.utc,
                        ),
                        account_id=MORTGAGE_ACCOUNT,
                        due_amount_calculation_day=str(event[4]),
                    )
                )
            elif event[0] == "repayment_postings":
                events.extend(
                    _set_up_deposit_events(
                        num_payments=int(event[1]),
                        repayment_amount=event[2],
                        repayment_day=int(event[5]),
                        repayment_hour=payment_hour,
                        start_year=int(event[3]),
                        start_month=int(event[4]),
                    )
                )

        sub_tests.append(SubTest(description="Repayments and param changes", events=events))

        expected_output = self.expected_output["change_repayment_day_after"]
        for i, values in enumerate(expected_output):
            repayment_date = datetime(
                year=start_year,
                month=2,
                day=int(values[2]),
                hour=1,
                tzinfo=timezone.utc,
            )
            sub_tests.append(
                SubTest(
                    description=f"balances after due amount calc {i+1}",
                    expected_balances_at_ts={
                        repayment_date
                        + relativedelta(months=i): {
                            accounts.MORTGAGE_ACCOUNT: [
                                (dimensions.PRINCIPAL_DUE, values[0]),
                                (dimensions.INTEREST_DUE, values[1]),
                            ]
                        }
                    },
                )
            )

        sub_tests += [
            SubTest(
                description="Due amount calculation runs as expected, accounting for due amount "
                "calc day change",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(year=2020, month=2, day=20, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=3, day=20, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=4, day=22, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=5, day=22, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=6, day=26, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=7, day=26, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=8, day=26, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=9, day=26, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=10, day=26, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=11, day=26, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=12, day=26, minute=1, tzinfo=timezone.utc),
                        ],
                        event_id="DUE_AMOUNT_CALCULATION",
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        count=11,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=mortgage_2_template_params,
            instance_params=mortgage_2_instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_change_repayment_day_before(self):

        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=1, minute=1, tzinfo=timezone.utc)
        sub_tests = []
        events = []
        for event in self.input_data["change_repayment_day_before"]:
            if event[0] == "repayment_day_change":
                events.append(
                    create_instance_parameter_change_event(
                        timestamp=datetime(
                            year=int(event[1]),
                            month=int(event[2]),
                            day=int(event[3]),
                            tzinfo=timezone.utc,
                        ),
                        account_id=MORTGAGE_ACCOUNT,
                        due_amount_calculation_day=str(event[4]),
                    )
                )
            elif event[0] == "repayment_postings":
                events.extend(
                    _set_up_deposit_events(
                        num_payments=int(event[1]),
                        repayment_amount=event[2],
                        repayment_day=int(event[5]),
                        repayment_hour=payment_hour,
                        start_year=int(event[3]),
                        start_month=int(event[4]),
                    )
                )

        sub_tests.append(SubTest(description="Repayments and param changes", events=events))

        expected_output = self.expected_output["change_repayment_day_before"]
        previous_repayment_date = None
        months_delta = 0
        for i, values in enumerate(expected_output):
            repayment_date = datetime(
                year=start_year,
                month=2,
                day=int(values[2]),
                hour=1,
                tzinfo=timezone.utc,
            )
            if previous_repayment_date and previous_repayment_date > values[2]:
                months_delta = months_delta + 1
            sub_tests.append(
                SubTest(
                    description=f"balances after due amount calc {i+1}",
                    expected_balances_at_ts={
                        repayment_date
                        + relativedelta(months=months_delta): {
                            accounts.MORTGAGE_ACCOUNT: [
                                (dimensions.PRINCIPAL_DUE, values[0]),
                                (dimensions.INTEREST_DUE, values[1]),
                            ]
                        }
                    },
                )
            )
            previous_repayment_date = values[2]
            months_delta += 1

        sub_tests += [
            SubTest(
                description="Due amount calculation runs as expected, accounting for due amount "
                "calc day change",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(year=2020, month=2, day=20, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=3, day=20, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=5, day=18, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=6, day=18, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=7, day=18, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=8, day=18, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=9, day=18, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=11, day=10, minute=1, tzinfo=timezone.utc),
                            datetime(year=2020, month=12, day=10, minute=1, tzinfo=timezone.utc),
                        ],
                        event_id="DUE_AMOUNT_CALCULATION",
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        count=9,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=mortgage_2_template_params,
            instance_params=mortgage_2_instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_check_delinquency_schedule(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=10, minute=1, tzinfo=timezone.utc)

        day_of_repayment_day_change = datetime(year=2020, month=6, day=15, tzinfo=timezone.utc)
        sub_tests = []

        repayment_with_overpayment = str(Decimal(mortgage_2_EMI) + Decimal("10000"))

        sub_tests = [
            SubTest(
                description="Setup payments and day change",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        amount=repayment_with_overpayment,
                        event_datetime=datetime(
                            year=2020, month=3, day=25, hour=12, tzinfo=timezone.utc
                        ),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.MORTGAGE_ACCOUNT,
                        amount=repayment_with_overpayment,
                        event_datetime=datetime(
                            year=2020, month=4, day=25, hour=12, tzinfo=timezone.utc
                        ),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_instance_parameter_change_event(
                        timestamp=day_of_repayment_day_change,
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        due_amount_calculation_day="25",
                    ),
                ],
            ),
            SubTest(
                description="Delinquency runs as expected, accounting for due amount calc day"
                " change",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            # Initial delinquency as no repayments are made for due amounts 1 and 2
                            datetime(year=2020, month=3, day=25, second=2, tzinfo=timezone.utc),
                            # Late overpayments for due amount 1 and 2 mean no new overdue until
                            # amounts until overdue checks for due amount 4, which takes place in
                            # due amount calculation 5 (June). Delinquency check day has shifted
                            # due to due amount # calc day change
                            datetime(year=2020, month=6, day=30, second=2, tzinfo=timezone.utc),
                            datetime(year=2020, month=7, day=30, second=2, tzinfo=timezone.utc),
                            datetime(year=2020, month=8, day=30, second=2, tzinfo=timezone.utc),
                            datetime(year=2020, month=9, day=30, second=2, tzinfo=timezone.utc),
                            datetime(year=2020, month=10, day=30, second=2, tzinfo=timezone.utc),
                            datetime(year=2020, month=11, day=30, second=2, tzinfo=timezone.utc),
                            datetime(year=2020, month=12, day=30, second=2, tzinfo=timezone.utc),
                        ],
                        event_id="CHECK_DELINQUENCY",
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        count=8,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=mortgage_2_template_params,
            instance_params=mortgage_2_instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_overpayment_backdated_posting_is_rejected(self):
        """
        Ensure smart contract refers the live balances and rejects
        when backdated repayment postings are received with an amount exceeding
        the current outstanding debt balances
        """
        template_parameters = parameters.mortgage_template_params.copy()
        template_parameters[mortgage.PARAM_EARLY_REPAYMENT_FEE] = "0"

        start = default_simulation_start_date
        first_posting_event_datetime = datetime(
            year=2020, month=3, day=27, hour=10, tzinfo=timezone.utc
        )
        second_posting_event_datetime = first_posting_event_datetime + relativedelta(hours=1)
        end = datetime(year=2020, month=3, day=28, minute=1, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="First overpayment is accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=MORTGAGE_ACCOUNT,
                        amount="200000",
                        event_datetime=first_posting_event_datetime,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    first_posting_event_datetime: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL, "101596.72"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "376.71645"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "376.71645"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.EMI, "2910.69"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OVERPAYMENT, "194105.44"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Backdated overpayment is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=MORTGAGE_ACCOUNT,
                        amount="200000",
                        event_datetime=second_posting_event_datetime,
                        internal_account_id=DEPOSIT_ACCOUNT,
                        value_timestamp=first_posting_event_datetime - relativedelta(hours=1),
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=second_posting_event_datetime,
                        rejection_reason="Cannot pay more than is owed",
                        rejection_type="AgainstTermsAndConditions",
                        account_id=accounts.MORTGAGE_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    second_posting_event_datetime: {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL, "101596.72"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "376.71645"),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, "376.71645"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.EMI, "2910.69"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OVERPAYMENT, "194105.44"),
                        ],
                    }
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=mortgage_1_instance_params,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_account_marked_delinquent_when_backdated_payment_received_after_grace_period(
        self,
    ):
        """
        When a repayment is made after the grace period but backdated to during the grace period,
        ensure repayment amount is applied to live overdue balances first,
        followed repayment hierarchy and
        MORTGAGE_MARK_DELINQUENT workflow is instantiated at the end of the grace period.
        """

        start = default_simulation_start_date
        first_delinquency_check = datetime(
            year=2020, month=3, day=25, second=2, tzinfo=timezone.utc
        )
        end = datetime(year=2020, month=3, day=26, hour=2, minute=1, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Mortgage marked as delinquent at end of grace period",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=first_delinquency_check,
                        notification_type="MORTGAGE_MARK_DELINQUENT",
                        notification_details={
                            "account_id": accounts.MORTGAGE_ACCOUNT,
                        },
                        resource_id=f"{accounts.MORTGAGE_ACCOUNT}",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Backdated overpayment is accepted after grace period",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=MORTGAGE_ACCOUNT,
                        amount=mortgage_2_first_month_payment,
                        event_datetime=datetime(
                            year=2020, month=3, day=25, hour=1, tzinfo=timezone.utc
                        ),
                        internal_account_id=DEPOSIT_ACCOUNT,
                        value_timestamp=first_delinquency_check - relativedelta(days=1),
                    )
                ],
                expected_balances_at_ts={
                    # the test framework behaves a little strangely here, as it inserts an entry in
                    # the balance ts out of chronological order. As we process it in reverse order
                    # when querying for balances at time X, it is found before the original entry,
                    # but this also means we can't query the original balances at time X before the
                    # backdated repayment
                    first_delinquency_check
                    - relativedelta(days=1): {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.INTEREST_DUE, "733.68"),
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.PENALTIES, "26.65"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        event_id="CHECK_DELINQUENCY",
                        run_times=[first_delinquency_check],
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        count=1,
                    )
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=mortgage_2_instance_params,
            template_params=mortgage_2_template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_account_not_marked_delinquent_when_backdated_payment_received_during_grace_period(
        self,
    ):
        """
        When a repayment is made before the grace period but vault received
        during the grace period, ensure repayment amount is applied to live overdue
        balances first, followed repayment hierarchy and
        CHECK_DELINQUENCY schedule has not instantiated the MORTGAGE_MARK_DELINQUENT workflow.
        """
        start = default_simulation_start_date
        second_due_amount_calculation = datetime(
            year=2020, month=3, day=20, minute=1, tzinfo=timezone.utc
        )
        first_delinquency_check = datetime(
            year=2020, month=3, day=25, second=2, tzinfo=timezone.utc
        )
        end = datetime(year=2020, month=3, day=26, hour=2, minute=1, tzinfo=timezone.utc)

        sub_tests = [
            # See further down for assertion on no delinquency notifications
            SubTest(
                description="Backdated overpayment is accepted during grace period for before the "
                "grace period",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=MORTGAGE_ACCOUNT,
                        # repay EMI + non-emi interest + penalties (breakdown below)
                        # 15 late repayment fees + 4 * round(
                        #   (2910.69+229.32) * round((0.24 + 0.031)/365, 10),
                        # 2)
                        amount=str(Decimal("2910.69") + Decimal("229.32") + Decimal("24.32")),
                        event_datetime=first_delinquency_check - relativedelta(days=1),
                        value_timestamp=second_due_amount_calculation + relativedelta(days=1),
                        internal_account_id=DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    # the test framework behaves a little strangely here, as it inserts an entry in
                    # the balance ts out of chronological order. As we process it in reverse order
                    # when querying for balances at time X, it is found before the original entry,
                    # but this also means we can't query the original balances at time X before the
                    # backdated repayment
                    first_delinquency_check
                    - relativedelta(days=1): {
                        accounts.MORTGAGE_ACCOUNT: [
                            (dimensions.INTEREST_DUE, "733.68"),
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.PENALTIES, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        event_id="CHECK_DELINQUENCY",
                        run_times=[first_delinquency_check],
                        account_id=accounts.MORTGAGE_ACCOUNT,
                        count=1,
                    )
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=mortgage_2_instance_params,
            template_params=mortgage_2_template_params,
        )
        # TODO(INC-8620): improve negative assertions in simulator framework
        res = self.run_test_scenario(test_scenario)
        self.assertListEqual(
            [], get_contract_notifications(res).get("MORTGAGE_MARK_DELINQUENT", [])
        )


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
