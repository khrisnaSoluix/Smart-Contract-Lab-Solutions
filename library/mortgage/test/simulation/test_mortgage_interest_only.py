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

interest_only_start_date = datetime(year=2019, month=6, day=11, tzinfo=timezone.utc)
payment_hour = 12

mortgage_2_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_term": "18",
    "total_repayment_count": "18",
    "interest_only_term": "6",
    "principal": "30000",
    "due_amount_calculation_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.00",
}

mortgage_3_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_term": "120",
    "total_repayment_count": "120",
    "interest_only_term": "12",
    "principal": "300000",
    "due_amount_calculation_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.00",
}

mortgage_3_template_params = {
    **parameters.mortgage_template_params,
    "variable_interest_rate": "0.189965",
}

mortgage_4_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_term": "3",
    "total_repayment_count": "18",
    "interest_only_term": "6",
    "principal": "30000",
    "due_amount_calculation_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.001",
}

mortgage_4_template_params = {
    **parameters.mortgage_template_params,
    "variable_interest_rate": "0.0279",
}


class MortgageInterestOnly(MortgageTestBase):
    def test_monthly_due_for_fixed_rate_interest_only_to_plus_principal_repayment(self):
        start = interest_only_start_date
        end = interest_only_start_date + relativedelta(months=18, days=10)
        sub_tests = []
        events = []

        for event in self.input_data["fixed_rate_interest_only_to_plus_principal"]:
            # Repayments occur on repayment day
            events.extend(
                _set_up_deposit_events(
                    int(event[1]),
                    event[2],
                    20,
                    payment_hour,
                    int(event[3]),
                    int(event[4]),
                )
            )

        repayment_date = datetime(
            year=2019,
            month=7,
            day=20,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
        )

        sub_tests.append(SubTest(description="Repayment events", events=events))

        for i, values in enumerate(self.expected_output["interest_only_to_plus_principal"]):
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

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=mortgage_3_template_params,
            instance_params=mortgage_2_instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_monthly_due_for_fixed_to_variable_rate_interest_only_to_plus_principal_repayment(
        self,
    ):
        start = interest_only_start_date
        end = interest_only_start_date + relativedelta(months=18, days=10)
        sub_tests = []
        events = []

        for event in self.input_data["fixed_to_variable_rate_interest_only_to_plus_principal"]:
            if event[0] == "variable_rate_change":
                events.append(
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=int(event[1]),
                            month=int(event[2]),
                            day=int(event[3]),
                            hour=12,
                            tzinfo=timezone.utc,
                        ),
                        variable_interest_rate=str(event[4]),
                    )
                )
            else:
                events.extend(
                    _set_up_deposit_events(
                        int(event[1]), event[2], 20, 10, int(event[3]), int(event[4])
                    )
                )

        repayment_date = datetime(
            year=2019,
            month=7,
            day=20,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
        )

        sub_tests.append(SubTest(description="rate change and repayment events", events=events))

        for i, values in enumerate(
            self.expected_output["fixed_to_variable_rate_interest_only_to_plus_principal"]
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
                            ]
                        }
                    },
                )
            )

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=mortgage_4_template_params,
            instance_params=mortgage_4_instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_derived_param_is_interest_only_term_true(self):
        start = datetime(2020, 1, 9, minute=5, second=10, tzinfo=timezone.utc)
        end = datetime(2020, 3, 12, tzinfo=timezone.utc)

        template_params = {
            **mortgage_3_template_params,
        }
        instance_params = {
            **mortgage_3_instance_params,
            "interest_only_term": "1",
        }

        events = []
        # repayment day is 20 hence interest only term will change only after 20.
        before_interest_only_term_end_date = datetime(2020, 2, 20, tzinfo=timezone.utc)
        after_interest_only_term_end_date = datetime(2020, 2, 21, tzinfo=timezone.utc)
        sub_tests = [
            SubTest(
                description="check derived parameters",
                events=events,
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_interest_only_term_end_date,
                        account_id=MORTGAGE_ACCOUNT,
                        name="is_interest_only_term",
                        value="True",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_interest_only_term_end_date,
                        account_id=MORTGAGE_ACCOUNT,
                        name="is_interest_only_term",
                        value="False",
                    ),
                ],
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_derived_param_is_interest_only_term_false(self):
        start = datetime(2020, 1, 9, minute=5, second=10, tzinfo=timezone.utc)
        end = datetime(2020, 2, 23, tzinfo=timezone.utc)

        template_params = {
            **mortgage_3_template_params,
        }
        instance_params = {
            **mortgage_3_instance_params,
            "interest_only_term": "0",
        }

        events = [
            create_instance_parameter_change_event(
                account_id=MORTGAGE_ACCOUNT,
                timestamp=datetime(2020, 1, 17, tzinfo=timezone.utc),
                interest_only_term="1",
            ),
        ]
        before_param_change_date = datetime(2020, 1, 16, tzinfo=timezone.utc)
        after_param_change_date = datetime(2020, 1, 18, tzinfo=timezone.utc)
        after_interest_only_term_end_date = datetime(2020, 2, 21, tzinfo=timezone.utc)
        sub_tests = [
            SubTest(
                description="check derived parameters",
                events=events,
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_param_change_date,
                        account_id=MORTGAGE_ACCOUNT,
                        name="is_interest_only_term",
                        value="False",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_param_change_date,
                        account_id=MORTGAGE_ACCOUNT,
                        name="is_interest_only_term",
                        value="True",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_interest_only_term_end_date,
                        account_id=MORTGAGE_ACCOUNT,
                        name="is_interest_only_term",
                        value="False",
                    ),
                ],
            )
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
