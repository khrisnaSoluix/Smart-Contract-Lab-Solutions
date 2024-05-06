# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal

# library
from library.mortgage.test import accounts, dimensions, parameters
from library.mortgage.test.simulation.common import MortgageTestBase

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ExpectedDerivedParameter,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
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

mortgage_1_template_params = {**parameters.mortgage_template_params}

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
    **parameters.mortgage_template_params,
    "variable_interest_rate": "0.189965",
}


class MortgageRepaymentHolidayTest(MortgageTestBase):
    def test_monthly_interest_accrual_fixed(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=9, day=21, tzinfo=timezone.utc)
        sub_tests = []

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=7, day=20, hour=0, minute=2, tzinfo=timezone.utc
        )
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

        events = [_set_up_repayment_holiday_flag(start)]
        events.append(
            create_flag_event(
                timestamp=start + relativedelta(seconds=2),
                flag_definition_id="REPAYMENT_HOLIDAY",
                account_id=accounts.MORTGAGE_ACCOUNT,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )
        events.extend(
            _set_up_deposit_events(1, str(Decimal("3140.01")), 20, payment_hour, start_year, 2)
        )
        events.extend(
            _set_up_deposit_events(2, str(Decimal("2910.69")), 20, payment_hour, start_year, 3)
        )

        sub_tests.append(SubTest(description="Flag and Repayment events", events=events))

        for i, values in enumerate(
            self.expected_output["repayment_holiday_test_monthly_interest_accrual_fixed"]
        ):
            sub_tests.append(
                SubTest(
                    description=f"check balance at repayment {i}",
                    expected_balances_at_ts={
                        repayment_date
                        + relativedelta(months=i): {
                            MORTGAGE_ACCOUNT: [
                                (dimensions.PRINCIPAL_DUE, values[0]),
                                (dimensions.INTEREST_DUE, values[1]),
                                (dimensions.PRINCIPAL, values[2]),
                                (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, values[3]),
                                (dimensions.ACCRUED_INTEREST_RECEIVABLE, values[4]),
                                (dimensions.CAPITALISED_INTEREST_TRACKER, values[5]),
                                (dimensions.EMI, values[6]),
                            ]
                        }
                    },
                )
            )

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=mortgage_2_template_params,
            instance_params=mortgage_2_instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_monthly_interest_accrual_variable(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=6, day=13, minute=1, tzinfo=timezone.utc)

        payment_holiday_start = datetime(
            year=2020, month=6, day=12, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=12, day=12, hour=0, minute=2, tzinfo=timezone.utc
        )
        sub_tests = []
        events = [_set_up_repayment_holiday_flag(start)]

        events.append(
            create_flag_event(
                timestamp=start + relativedelta(seconds=2),
                flag_definition_id="REPAYMENT_HOLIDAY",
                account_id=accounts.MORTGAGE_ACCOUNT,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )

        for event in self.input_data["repayment_holiday_test_monthly_interest_accrual_variable"]:
            if event[0] == "variable_rate_change":
                # Rate changes occuring just after repayment
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

        sub_tests.append(SubTest(description="Flag and Repayment events", events=events))

        for i, values in enumerate(
            self.expected_output["repayment_holiday_test_monthly_interest_accrual_variable"]
        ):
            sub_tests.append(
                SubTest(
                    description=f"check balance at repayment {i}",
                    expected_balances_at_ts={
                        repayment_date
                        + relativedelta(months=i): {
                            MORTGAGE_ACCOUNT: [
                                (dimensions.PRINCIPAL_DUE, values[0]),
                                (dimensions.INTEREST_DUE, values[1]),
                                (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, values[2]),
                                (dimensions.CAPITALISED_INTEREST_TRACKER, values[3]),
                                (dimensions.EMI, values[4]),
                            ]
                        }
                    },
                )
            )

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=mortgage_1_template_params,
            instance_params=mortgage_1_instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_1_year_fixed_with_full_repayment(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=21, minute=1, tzinfo=timezone.utc)

        instance_params = {
            **mortgage_2_instance_params,
            "total_repayment_count": "12",
            "principal": "18000",
        }

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=7, day=20, hour=0, minute=2, tzinfo=timezone.utc
        )
        sub_tests = []
        events = [_set_up_repayment_holiday_flag(start)]

        events.append(
            create_flag_event(
                timestamp=start + timedelta(seconds=2),
                flag_definition_id="REPAYMENT_HOLIDAY",
                account_id=MORTGAGE_ACCOUNT,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )

        events.extend(_set_up_deposit_events(1, "1539.07", 20, payment_hour, 2020, 2))
        events.extend(_set_up_deposit_events(2, "1525.31", 20, payment_hour, 2020, 3))

        # after repayment holiday
        events.extend(_set_up_deposit_events(5, "2296.70", 20, payment_hour, 2020, 8))

        # Final repayment
        events.extend(_set_up_deposit_events(1, "2297.94", 20, payment_hour, 2021, 1))

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

        sub_tests.append(SubTest(description="Flag and Repayment events", events=events))

        for i, values in enumerate(
            self.expected_output["repayment_holiday_1year_fixed_with_full_repayment"]
        ):
            sub_tests.append(
                SubTest(
                    description=f"check balance at repayment {i}",
                    expected_balances_at_ts={
                        repayment_date
                        + relativedelta(months=i): {
                            MORTGAGE_ACCOUNT: [
                                (dimensions.PRINCIPAL, values[0]),
                                (dimensions.PRINCIPAL_DUE, values[1]),
                                (dimensions.INTEREST_DUE, values[2]),
                                (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, values[3]),
                                (dimensions.CAPITALISED_INTEREST_TRACKER, values[4]),
                            ]
                        }
                    },
                )
            )

        sub_tests.append(
            SubTest(
                description="check all debt balances repaid after final repayment",
                expected_balances_at_ts={
                    end: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_DUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # only the tracker is left
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "104.74"),
                        ]
                    }
                },
            )
        )

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=mortgage_2_template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_daily_penalty_accrual_and_blocking(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=8, day=21, minute=1, tzinfo=timezone.utc)

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=6, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )

        first_repayment_date = datetime(year=2020, month=2, day=20, minute=2, tzinfo=timezone.utc)
        before_first_repayment_date = first_repayment_date - relativedelta(hours=1)
        after_first_repayment_due = first_repayment_date + relativedelta(hours=1)

        sub_tests = [
            SubTest(
                description="create flag definition and flag event",
                events=[
                    _set_up_repayment_holiday_flag(start),
                    create_flag_event(
                        timestamp=start + timedelta(seconds=2),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=MORTGAGE_ACCOUNT,
                        effective_timestamp=payment_holiday_start,
                        expiry_timestamp=payment_holiday_end,
                    ),
                ],
            ),
            SubTest(
                description="first EMI due",
                expected_balances_at_ts={
                    first_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2120.83"),
                            (dimensions.INTEREST_DUE, "1019.18"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_repayment_date,
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="120",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_first_repayment_due,
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="119",
                    ),
                ],
            ),
            SubTest(
                description="first EMI overdue, second EMI due, fee applied",
                expected_balances_at_ts={
                    datetime(year=2020, month=3, day=20, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2177.01"),
                            (dimensions.INTEREST_DUE, "733.68"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "2120.83"),
                            (dimensions.INTEREST_OVERDUE, "1019.18"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            (dimensions.PENALTIES, "15"),
                        ]
                    }
                },
            ),
            SubTest(
                description="second EMI overdue, third EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=4, day=20, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 15 + round((2120.83+1019.18)*round((0.24+0.031)/365, 10), 2) * 31
                            # + 15
                            (dimensions.PENALTIES, "102.23"),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment holiday starts, third EMI remains due, no overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=4, day=30, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            # round(293570.02 * round(0.031/365,10), 5) * 10
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "249.3334"),
                            (dimensions.PENALTIES, "102.23"),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment holiday ongoing, third EMI remains due",
                expected_balances_at_ts={
                    datetime(year=2020, month=5, day=20, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            # round(293570.02 * round(0.031/365,10), 5) * 30
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "748.0002"),
                            (dimensions.PENALTIES, "102.23"),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment holiday ongoing, no further overdue from check overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=5, day=30, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            # round(293570.02 * round(0.031/365,10), 5) * 40
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "997.3336"),
                            (dimensions.PENALTIES, "102.23"),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment holiday ongoing, no further due",
                expected_balances_at_ts={
                    datetime(year=2020, month=6, day=20, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2132.14"),
                            (dimensions.INTEREST_DUE, "778.55"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "0"),
                            (dimensions.PRINCIPAL_OVERDUE, "4297.84"),
                            (dimensions.INTEREST_OVERDUE, "1752.86"),
                            (dimensions.PRINCIPAL, "293570.02"),
                            # round(293570.02 * round(0.031/365,10), 5) * 61
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "1520.93374"),
                            (dimensions.PENALTIES, "102.23"),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment holiday ended, third EMI overdue, fourth EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=7, day=20, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            # EMI increased from 2910.69 to 2969.3
                            # due to capitalised interest added to principal
                            (dimensions.PRINCIPAL_DUE, "2217.42"),
                            (dimensions.INTEREST_DUE, "751.88"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "1520.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "6429.98"),
                            (dimensions.INTEREST_OVERDUE, "2531.41"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 102.23 + 15 + round(
                            #   (4297.84 + 1752.86) * round((0.24 + 0.031)/365, 10),
                            # 2) * 30
                            (dimensions.PENALTIES, "251.93"),
                        ]
                    }
                },
            ),
            SubTest(
                description="fourth EMI overdue, fifth EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=8, day=20, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (dimensions.PRINCIPAL_DUE, "2198.2"),
                            (dimensions.INTEREST_DUE, "771.1"),
                            (dimensions.CAPITALISED_INTEREST_TRACKER, "1520.93"),
                            (dimensions.PRINCIPAL_OVERDUE, "8647.4"),
                            (dimensions.INTEREST_OVERDUE, "3283.29"),
                            (dimensions.ACCRUED_INTEREST_PENDING_CAPITALISATION, "0"),
                            # 251.93 + 15 + round(
                            #  (8647.53 + 3283.29) * round((0.24 + 0.031)/365, 10),
                            # 2) * 30
                            (dimensions.PENALTIES, "473.08"),
                        ]
                    }
                },
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


def _set_up_repayment_holiday_flag(start):
    return create_flag_definition_event(timestamp=start, flag_definition_id="REPAYMENT_HOLIDAY")
