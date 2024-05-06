# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

# library
from library.mortgage.test import dimensions, parameters
from library.mortgage.test.simulation.common import MortgageTestBase

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import SubTest

MORTGAGE_ACCOUNT = "MORTGAGE_ACCOUNT"
DEPOSIT_ACCOUNT = "DEPOSIT_ACCOUNT"

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
start_year = 2020

mortgage_instance_params = {
    "fixed_interest_rate": "0.02",
    "fixed_interest_term": "2",
    "total_repayment_count": "120",
    "interest_only_term": "0",
    "principal": "800000",
    "due_amount_calculation_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.00",
}

mortgage_template_params = {
    **parameters.mortgage_template_params,
    "variable_interest_rate": "0.129971",
}


class MortgageVariableFixedTest(MortgageTestBase):
    def test_monthly_due_for_fixed_to_variable_rate_only(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=5, day=21, minute=1, tzinfo=timezone.utc)
        sub_tests = []

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

        for i, values in enumerate(self.expected_output["fixed_to_variable_rate"]):
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
            template_params=mortgage_template_params,
            instance_params=mortgage_instance_params,
        )

        self.run_test_scenario(test_scenario)
