import calendar
from datetime import datetime
import json
import os
from unittest import mock

from ...utils.tools import SupervisorContracts360TestCase
from ...versions.version_360.supervisor_contracts import types


class NativesTestCase(SupervisorContracts360TestCase):
    effective_date = datetime(year=2020, month=2, day=15)

    filepath = os.environ.get(
        "DATA_NATIVES_V360", "contracts_sdk/example_unit_tests/supervisor_contracts/natives_v360.py"
    )
    contract_code = SupervisorContracts360TestCase.load_contract_code(filepath)

    def test_type_hints_are_supported(self):
        output_type = self.run_contract_function(self.contract_code, "execution_schedules")
        self.assertEqual((), output_type)

    def test_native_objects_are_supported(self):
        example_json_data = {"time 1": 10}

        def get_parameter_timeseries(name):
            timeseries = mock.Mock()
            if name == "balance_pot":
                timeseries.latest.return_value = json.dumps(example_json_data)
            return timeseries

        supervisee = self.create_supervisee_vault()
        supervisee.get_parameter_timeseries.side_effect = get_parameter_timeseries
        supervisee.account_id = "account_id"

        self.vault.supervisees = {
            "account_id": supervisee,
        }
        self.run_contract_function(self.contract_code, "post_posting_code", {}, self.effective_date)
        expected_body = {
            "interest_due_round_half_down": "12912.48",
            "interest_due_round_half_up": "12912.5",
            "interest_due_round_floor": "12912.4",
            "interest_due_round_down": "12912.47",
            "interest_due_round_half_even": "12912.48",
            "interest_due_round_05up": "12912.4",
            "interest_due_round_ceil": "12912.5",
            "repayment_date": datetime(2020, 1, 16).isoformat(),
            "date_from_parser": datetime(2015, 5, 1).isoformat(),
            "repayment_day": calendar.day_name[0],
            "balance_dict": 10,
            "checking_math_sqrt": 10.0,
            "checking_math_ceil": 101,
        }
        expected_body_converted_via_json = json.dumps(expected_body)

        self.vault.supervisees["account_id"].add_account_note.assert_called_once_with(
            body=expected_body_converted_via_json,
            note_type=types.NoteType.RAW_TEXT,
            is_visible_to_customer=True,
            date=self.effective_date,
        )
