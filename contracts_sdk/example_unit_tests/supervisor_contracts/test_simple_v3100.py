from datetime import datetime
import os

from ...utils.tools import SupervisorContracts3100TestCase
from ...versions.version_3100.supervisor_contracts import types


class SimpleTestCase(SupervisorContracts3100TestCase):

    filepath = os.environ.get(
        "DATA_SIMPLE_V3100", "contracts_sdk/example_unit_tests/supervisor_contracts/simple_v3100.py"
    )
    contract_code = SupervisorContracts3100TestCase.load_contract_code(filepath)

    effective_date = datetime(year=2020, month=2, day=20)
    pause_datetime = datetime(year=2020, month=2, day=15)

    def test_scheduled_code_get_scheduled_job_details(self):
        self.vault.supervisees = {"SUPERVISEE": self.create_supervisee_vault()}

        self.vault.get_scheduled_job_details.return_value = types.ScheduledJob(
            pause_datetime=self.pause_datetime
        )
        self.vault.supervisees[
            "SUPERVISEE"
        ].get_scheduled_job_details.return_value = types.ScheduledJob(
            pause_datetime=self.pause_datetime
        )

        self.run_contract_function(
            self.contract_code,
            "scheduled_code",
            "SUPERVISED_SCHEDULE_JOB_DETAILS",
            self.effective_date,
        )

        self.vault.supervisees["SUPERVISEE"].add_account_note.assert_called_once_with(
            body="pause_datetime: 2020-02-15 00:00:00 2020-02-15 00:00:00",
            note_type=types.NoteType.RAW_TEXT,
            is_visible_to_customer=True,
            date=self.effective_date,
        )
