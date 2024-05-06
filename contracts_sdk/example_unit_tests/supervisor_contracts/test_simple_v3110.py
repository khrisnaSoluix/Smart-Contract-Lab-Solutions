from datetime import datetime
import os

from ...utils.tools import SupervisorContracts3110TestCase
from ...versions.version_3110.supervisor_contracts import types


class SimpleTestCase(SupervisorContracts3110TestCase):

    filepath = os.environ.get(
        "DATA_SIMPLE_V3110", "contracts_sdk/example_unit_tests/supervisor_contracts/simple_v3110.py"
    )
    contract_code = SupervisorContracts3110TestCase.load_contract_code(filepath)
    effective_date = datetime(year=2020, month=2, day=15)

    def test_scheduled_code_skip_event_type(self):
        update_account_event_type_directive = types.UpdateAccountEventTypeDirective(
            account_id="supervisee",
            event_type="EVENT_TYPE",
            schedule=types.EventTypeSchedule(
                day="1",
            ),
            end_datetime=datetime(year=2022, month=1, day=1),
            skip=types.ScheduleSkip(end=datetime(year=2021, month=2, day=15)),
        )

        def get_hook_directives():
            return types.HookDirectives(
                add_account_note_directives=[],
                amend_schedule_directives=[],
                remove_schedules_directives=[],
                workflow_start_directives=[],
                posting_instruction_batch_directives=[],
                update_account_event_type_directives=[update_account_event_type_directive],
            )

        supervisee = self.create_supervisee_vault()
        supervisee.get_hook_directives.side_effect = get_hook_directives
        self.vault.supervisees = {"supervisee": supervisee}

        self.run_contract_function(
            self.contract_code,
            "scheduled_code",
            event_type="SKIP_EVENT_TYPE",
            effective_date=self.effective_date,
        )
        supervisee.update_event_type.assert_called_once_with(
            event_type=update_account_event_type_directive.event_type,
            schedule=update_account_event_type_directive.schedule,
            skip=update_account_event_type_directive.skip,
        )
