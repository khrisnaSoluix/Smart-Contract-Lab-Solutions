import calendar
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import json
import os
from unittest import mock

from ...utils.tools import SmartContracts360TestCase


class NativesTestCase(SmartContracts360TestCase):
    effective_date = datetime(year=2020, month=2, day=15)

    filepath = os.environ.get(
        "DATA_NATIVES_V360", "contracts_sdk/example_unit_tests/smart_contracts/natives_v360.py"
    )
    contract_code = SmartContracts360TestCase.load_contract_code(filepath)

    def test_type_hints_are_supported(self):
        output_type = self.run_contract_function(self.contract_code, "post_activate_code")

        self.assertEqual("all native types successfully processed", output_type)
        self.assertIsInstance(output_type, str)

    def test_native_objects_are_supported(self):
        example_json_data = {"time 1": 10}

        def get_parameter_timeseries(name):
            timeseries = mock.Mock()
            if name == "balance_pot":
                timeseries.latest.return_value = json.dumps(example_json_data)
            return timeseries

        self.vault.get_parameter_timeseries.side_effect = get_parameter_timeseries
        output_parameters = self.run_contract_function(
            self.contract_code, "derived_parameters", self.effective_date
        )

        self.assertEqual(Decimal("12912.5"), output_parameters["interest_due_round_half_up"])
        self.assertEqual(Decimal("12912.48"), output_parameters["interest_due_round_half_down"])
        self.assertEqual(Decimal("12912.4"), output_parameters["interest_due_round_floor"])
        self.assertEqual(Decimal("12912.47"), output_parameters["interest_due_round_down"])
        self.assertEqual(Decimal("12912.48"), output_parameters["interest_due_round_half_even"])
        self.assertEqual(Decimal("12912.4"), output_parameters["interest_due_round_05up"])
        self.assertEqual(Decimal("12912.5"), output_parameters["interest_due_round_ceil"])
        self.assertEqual(datetime(2020, 1, 16), output_parameters["repayment_date"])
        self.assertEqual(calendar.day_name[0], output_parameters["repayment_day"])
        self.assertIsInstance(output_parameters["internal_account_balance"], defaultdict)
        self.assertEqual(20, output_parameters["internal_account_balance"]["account 1"])
        self.assertEqual(datetime(2015, 5, 1), output_parameters["date_from_parser"])
        self.assertEqual(10, output_parameters["balance_dict"])
        self.assertEqual(10.0, output_parameters["checking_math_sqrt"])
        self.assertEqual(101, output_parameters["checking_math_ceil"])
