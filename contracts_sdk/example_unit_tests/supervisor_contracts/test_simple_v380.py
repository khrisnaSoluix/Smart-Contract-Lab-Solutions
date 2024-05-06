from datetime import datetime
from decimal import Decimal
import os

from ...utils.tools import SupervisorContracts380TestCase
from ...versions.version_380.supervisor_contracts import types


class SimpleTestCase(SupervisorContracts380TestCase):

    filepath = os.environ.get(
        "DATA_SIMPLE_V380", "contracts_sdk/example_unit_tests/supervisor_contracts/simple_v380.py"
    )
    contract_code = SupervisorContracts380TestCase.load_contract_code(filepath)
    effective_date = datetime(year=2020, month=2, day=15)

    def test_execution_schedules(self):
        execution_schedules = self.run_contract_function(self.contract_code, "execution_schedules")
        self.assertEqual([("EVENT_TYPE", {"hour": "11", "minute": "30"})], execution_schedules)

    def test_scheduled_code_with_calendar_event_type(self):
        calendar_events_a = [
            types.CalendarEvent(
                id="calendar_event_1",
                calendar_id="A",
                start_timestamp=datetime(2020, 11, 1),
                end_timestamp=datetime(2020, 12, 5),
            ),
            types.CalendarEvent(
                id="calendar_event_1",
                calendar_id="A",
                start_timestamp=datetime(2020, 12, 1),
                end_timestamp=datetime(2020, 12, 3),
            ),
        ]

        def get_calendar_events(calendar_ids):
            calendar_events = types.CalendarEvents(calendar_events=[])
            if calendar_ids == ["A"]:
                calendar_events = types.CalendarEvents(calendar_events=calendar_events_a)
            return calendar_events

        supervisee = self.create_supervisee_vault()
        self.vault.supervisees = {"supervisee": supervisee}
        self.vault.get_calendar_events.side_effect = get_calendar_events

        self.run_contract_function(
            self.contract_code,
            "scheduled_code",
            event_type="CALENDAR_EVENT_TYPE",
            effective_date=self.effective_date,
        )
        supervisee.add_account_note.assert_called_once_with(
            body=f"{len(calendar_events_a)}",
            note_type=types.NoteType.RAW_TEXT,
            is_visible_to_customer=True,
            date=self.effective_date,
        )

    def test_scheduled_code_with_update_event_type(self):
        update_account_event_type_directive = types.UpdateAccountEventTypeDirective(
            account_id="supervisee",
            event_type="EVENT_TYPE",
            schedule=types.EventTypeSchedule(
                day="1",
            ),
            end_datetime=datetime(year=2020, month=1, day=1),
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
            event_type="SUPERVISED_UPDATE_EVENT_TYPE",
            effective_date=self.effective_date,
        )
        supervisee.update_event_type.assert_called_once_with(
            event_type=update_account_event_type_directive.event_type,
            schedule=update_account_event_type_directive.schedule,
            end_datetime=update_account_event_type_directive.end_datetime,
        )

    def test_post_posting_code(self):
        self.vault.supervisees = {"supervisee": self.create_supervisee_vault()}

        hook_postings = types.PostingInstructionBatch(
            batch_id="batch_id",
            batch_details={},
            client_batch_id="international-payment",
            insertion_timestamp=self.effective_date,
            value_timestamp=self.effective_date,
            posting_instructions=[
                types.PostingInstruction(
                    custom_instruction_grouping_key="some_key",
                    client_transaction_id="client_transaction_id",
                    pics=[],
                    type=types.PostingInstructionType.TRANSFER,
                    credit=True,
                    amount=Decimal(10),
                    denomination="GBP",
                    account_id="supervisee",
                    account_address=types.defaultAddress.fixed_value,
                    asset=types.defaultAsset.fixed_value,
                    phase=types.Phase.COMMITTED,
                ),
            ],
        )

        self.run_contract_function(
            self.contract_code,
            "post_posting_code",
            postings=hook_postings,
            effective_date=self.effective_date,
        )

        self.vault.supervisees["supervisee"].add_account_note.assert_called_once_with(
            body=(f"Successfully created an account note for {hook_postings[0].account_id}"),
            note_type=types.NoteType.RAW_TEXT,
            is_visible_to_customer=True,
            date=self.effective_date,
        )
