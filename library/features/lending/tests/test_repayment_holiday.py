import json
from datetime import datetime

# common
from inception_sdk.vault.contracts.types_extension import (
    Tside,
)
from inception_sdk.test_framework.contracts.unit.common import (
    ContractFeatureTest,
    TimeSeries,
)

# other
import library.features.common.utils as utils
import library.features.lending.repayment_holiday as repayment_holiday


class TestRepaymentHoliday(ContractFeatureTest):

    target_test_file = "library/features/lending/repayment_holiday.py"
    side = Tside.ASSET

    def test_should_trigger_reamortisation(self):
        test_cases = [
            {
                "description": "No reamortisation when still on repayment holiday",
                "repayment_holiday_at_previous_schedule": True,
                "repayment_holiday_now": True,
                "reamortisation_triggered": False,
            },
            {
                "description": "No reamortisation when newly on repayment holiday",
                "repayment_holiday_at_previous_schedule": False,
                "repayment_holiday_now": True,
                "reamortisation_triggered": False,
            },
            {
                "description": "No reamortisation when never on repayment holiday",
                "repayment_holiday_at_previous_schedule": False,
                "repayment_holiday_now": False,
                "reamortisation_triggered": False,
            },
            {
                "description": "Reamortisation when no longer on repayment holiday",
                "repayment_holiday_at_previous_schedule": True,
                "repayment_holiday_now": False,
                "reamortisation_triggered": True,
            },
        ]
        for test_case in test_cases:
            # this is just before the last execution time
            flag_ts = [(datetime(2020, 3, 5), test_case["repayment_holiday_at_previous_schedule"])]
            if (
                test_case["repayment_holiday_now"]
                != test_case["repayment_holiday_at_previous_schedule"]
            ):
                # this is just before the 'current' time
                flag_ts.append((datetime(2020, 4, 5), test_case["repayment_holiday_now"]))
            mock_vault = self.create_mock(
                due_amount_calculation_blocking_flags=json.dumps(["REPAYMENT_HOLIDAY"]),
                flags={"REPAYMENT_HOLIDAY": flag_ts},
            )

            result = repayment_holiday.should_trigger_reamortisation(
                mock_vault,
                elapsed_term_in_months=None,
                due_amount_schedule_details=utils.ScheduleDetails(
                    year=None,
                    month=None,
                    day=5,
                    hour=1,
                    minute=2,
                    second=3,
                    last_execution_time=datetime(2020, 3, 5, 1, 2, 3),
                ),
            )
            self.assertEqual(
                result, test_case["reamortisation_triggered"], test_case["description"]
            )

    def test_should_trigger_reamortisation_using_kwargs(self):
        flag_ts = [TimeSeries([(datetime(2020, 3, 5), True), (datetime(2020, 4, 5), False)])]
        mock_vault = self.create_mock()

        result = repayment_holiday.should_trigger_reamortisation(
            mock_vault,
            elapsed_term_in_months=None,
            due_amount_schedule_details=utils.ScheduleDetails(
                year=None,
                month=None,
                day=5,
                hour=1,
                minute=2,
                second=3,
                last_execution_time=datetime(2020, 3, 5, 1, 2, 3),
            ),
            due_amount_calculation_blocking_flags=flag_ts,
        )
        self.assertEqual(result, True, "Should trigger reamortisation when repayment holiday ends")
