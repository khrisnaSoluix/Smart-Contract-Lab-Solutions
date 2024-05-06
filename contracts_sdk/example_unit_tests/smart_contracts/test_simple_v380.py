from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock
import os

from ...utils.tools import SmartContracts380TestCase
from ...versions.version_380.smart_contracts import types


class SimpleTestCase(SmartContracts380TestCase):
    filepath = os.environ.get(
        "DATA_SIMPLE_V380", "contracts_sdk/example_unit_tests/smart_contracts/simple_v380.py"
    )
    contract_code = SmartContracts380TestCase.load_contract_code(filepath)
    account_id = "account_id"

    PercentageShape = types.NumberShape(
        kind=types.NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.00001
    )

    monthly_overdraft_rate = types.Parameter(
        name="monthly_overdraft_rate",
        description="Monthly Overdraft Rate",
        display_name="Monthly Overdraft Rate",
        level=types.Level.TEMPLATE,
        update_permission=types.UpdatePermission.USER_EDITABLE,
        derived=False,
        shape=PercentageShape,
        value=Decimal(0.05),
    )

    creation_date = datetime(year=2020, month=2, day=15)
    effective_date = datetime(year=2020, month=2, day=20)

    def get_parameter_timeseries(self, name):
        parameters_timeseries = mock.Mock()
        if name == "central_bank_yearly_interest_rate":
            parameters_timeseries.latest.return_value = "0.1"
        if name == "monthly_overdraft_rate":
            parameters_timeseries.latest.return_value = self.monthly_overdraft_rate.value

        return parameters_timeseries

    def test_execution_schedules_localizes_datetime(self):
        self.vault.get_account_creation_date.return_value = self.creation_date

        def localize_datetime(date: datetime):
            local_datetime = mock.Mock()
            if date == self.creation_date:
                local_datetime.isoformat.return_value = self.creation_date.isoformat()
            if date == (self.creation_date + timedelta(minutes=1)):
                local_datetime.isoformat.return_value = (
                    self.creation_date + timedelta(minutes=1)
                ).isoformat()

            return local_datetime

        self.vault.localize_datetime.side_effect = localize_datetime
        schedules = self.run_contract_function(self.contract_code, "execution_schedules")

        self.assertEqual("TEST_EVENT", schedules[0][0])
        self.assertEqual(
            (self.creation_date + timedelta(minutes=1)).isoformat(), schedules[0][1]["end_date"]
        )

    def test_derived_parameters_fails_when_invalid_permitted_denominations_provided(self):
        self.vault.get_permitted_denominations.return_value = ["GBP", "INR", "EUR"]

        with self.assertRaises(types.Rejected) as ex:
            self.run_contract_function(
                self.contract_code, "derived_parameters", effective_date=self.effective_date
            )

        self.assertIn("Invalid denominations used within this contract", str(ex.exception))

    def test_derived_parameters_return_permitted_denominations(self):
        self.vault.get_permitted_denominations.return_value = ["GBP", "USD", "EUR"]

        parameters = self.run_contract_function(
            self.contract_code, "derived_parameters", self.effective_date
        )

        self.assertEqual("USD", parameters["denomination"])

    def test_pre_posting_code_fails_when_too_many_calendars_provided(self):
        self.vault.get_permitted_denominations.return_value = ["GBP", "USD", "EUR"]

        native_calendar_events = types.CalendarEvents(
            calendar_events=[
                types.CalendarEvent(
                    id="test 1",
                    calendar_id="date_A",
                    start_timestamp=datetime(2015, 1, 1),
                    end_timestamp=datetime(2015, 1, 2),
                ),
                types.CalendarEvent(
                    id="test 2",
                    calendar_id="date_A",
                    start_timestamp=datetime(2016, 1, 1),
                    end_timestamp=datetime(2016, 1, 2),
                ),
                types.CalendarEvent(
                    id="test 3",
                    calendar_id="date_B",
                    start_timestamp=datetime(2016, 1, 1),
                    end_timestamp=datetime(2016, 1, 2),
                ),
            ]
        )

        def get_calendar_events(calendar_ids: list):
            if calendar_ids == ["date_A", "date_B"]:
                return native_calendar_events
            return types.CalendarEvents(calendar_events=[])

        self.vault.get_calendar_events.side_effect = get_calendar_events

        with self.assertRaises(types.Rejected) as ex:
            self.run_contract_function(
                self.contract_code, "pre_posting_code", {}, self.effective_date
            )

        self.assertIn("Wrong number of calendar events found", str(ex.exception))

    def test_pre_posting_code_fails_when_invalid_event_timestamp_provided(self):
        self.vault.get_permitted_denominations.return_value = ["GBP", "USD", "EUR"]

        native_calendar_events = types.CalendarEvents(
            calendar_events=[
                types.CalendarEvent(
                    id="test 1",
                    calendar_id="date_A",
                    start_timestamp=datetime(2015, 1, 1),
                    end_timestamp=datetime(2015, 1, 2),
                ),
                types.CalendarEvent(
                    id="test 3",
                    calendar_id="date_B",
                    start_timestamp=datetime(2020, 1, 1),
                    end_timestamp=datetime(2016, 1, 2),
                ),
            ]
        )

        def get_calendar_events(calendar_ids: list):
            if calendar_ids == ["date_A", "date_B"]:
                return native_calendar_events
            return types.CalendarEvents(calendar_events=[])

        self.vault.get_calendar_events.side_effect = get_calendar_events
        with self.assertRaises(types.Rejected) as ex:
            self.run_contract_function(
                self.contract_code, "pre_posting_code", {}, self.effective_date
            )

        self.assertIn("Calendar event start_timestamp incorrect", str(ex.exception))

    def test_post_posting_code_can_process_postings(self):
        # Collections of postings from which only one fits the condition in the contract.
        posting_instructions = [
            types.PostingInstruction(
                custom_instruction_grouping_key="some_key",
                client_transaction_id="id_12345",
                type=types.PostingInstructionType.CUSTOM_INSTRUCTION,
                pics=[],
                credit=True,
                amount=Decimal(10),
                denomination="GBP",
                account_id=self.account_id,
                account_address=types.defaultAddress.fixed_value,
                asset=types.defaultAsset.fixed_value,
                phase=types.Phase.COMMITTED,
            ),
            types.PostingInstruction(
                custom_instruction_grouping_key="some_key",
                client_transaction_id="id_12345",
                pics=[],
                type=types.PostingInstructionType.CUSTOM_INSTRUCTION,
                credit=True,
                amount=Decimal(10),
                denomination="GBP",
                account_id=self.account_id,
                account_address=types.defaultAddress.fixed_value,
                asset=types.defaultAsset.fixed_value,
                phase=types.Phase.COMMITTED,
            ),
            types.PostingInstruction(
                custom_instruction_grouping_key="some_key",
                client_transaction_id="id_12345",
                type=types.PostingInstructionType.CUSTOM_INSTRUCTION,
                pics=[],
                credit=False,
                amount=Decimal(10),
                denomination="GBP",
                account_id=self.account_id,
                account_address=types.defaultAddress.fixed_value,
                asset=types.defaultAsset.fixed_value,
                phase=types.Phase.COMMITTED,
            ),
            types.PostingInstruction(
                custom_instruction_grouping_key="some_key",
                client_transaction_id="id_12345",
                type=types.PostingInstructionType.CUSTOM_INSTRUCTION,
                pics=[],
                credit=True,
                amount=Decimal(10),
                denomination="GBP",
                account_id=self.account_id,
                account_address="different_address",
                asset=types.defaultAsset.fixed_value,
                phase=types.Phase.COMMITTED,
            ),
        ]

        self.vault.get_postings.return_value = posting_instructions
        self.run_contract_function(
            self.contract_code, "post_posting_code", None, self.effective_date
        )

        self.vault.add_account_note.assert_called_once_with(
            body="1",
            note_type=types.NoteType.RAW_TEXT,
            is_visible_to_customer=True,
            date=self.effective_date,
        )

    def test_scheduled_code_with_positive_accured_balance(self):
        def get_balance_timeseries():
            balance_key_1 = (
                types.defaultAddress.fixed_value,
                types.defaultAsset.fixed_value,
                "USD",
                types.Phase.COMMITTED,
            )

            balance_dict = types.BalanceDefaultDict()
            balance_dict[balance_key_1] = types.Balance(
                net=Decimal(20), credit=Decimal("2018.11"), debit=Decimal()
            )
            balance_timeseries = types.BalanceTimeseries(
                [
                    (self.effective_date, balance_dict),
                ]
            )
            return balance_timeseries

        self.vault.get_balance_timeseries.side_effect = get_balance_timeseries
        self.vault.account_id = self.account_id
        self.vault.get_parameter_timeseries.side_effect = self.get_parameter_timeseries
        self.run_contract_function(
            self.contract_code, "scheduled_code", "ACCRUE_INTEREST", self.effective_date
        )

        # 0.17 USD interest generated.
        self.vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("0.17"),
            denomination="USD",
            client_transaction_id="INTEREST_{}".format(self.account_id),
            from_account_id="1",
            from_account_address="ACCRUED_OUTGOING",
            to_account_id=self.account_id,
            to_account_address="ACCRUED_INCOMING",
            asset=types.defaultAsset.fixed_value,
        )
        self.vault.instruct_posting_batch.assert_called_once()

    def test_scheduled_code_with_negative_accured_balance(self):
        def get_balance_timeseries():
            balance_key_1 = (
                types.defaultAddress.fixed_value,
                types.defaultAsset.fixed_value,
                "USD",
                types.Phase.COMMITTED,
            )

            balance_dict = types.BalanceDefaultDict()
            balance_dict[balance_key_1] = types.Balance(
                net=Decimal(-20), credit=Decimal("2018.11"), debit=Decimal()
            )
            balance_timeseries = types.BalanceTimeseries(
                [
                    (self.effective_date, balance_dict),
                ]
            )
            return balance_timeseries

        self.vault.get_balance_timeseries.side_effect = get_balance_timeseries
        self.vault.account_id = self.account_id
        self.vault.get_parameter_timeseries.side_effect = self.get_parameter_timeseries
        self.run_contract_function(
            self.contract_code, "scheduled_code", "ACCRUE_INTEREST", self.effective_date
        )

        self.vault.make_internal_transfer_instructions.assert_not_called()
        self.vault.instruct_posting_batch.assert_not_called()

    def test_pre_posting_code_ensure_can_mock_pi_and_pib_attributes_and_balances(self):
        def get_balance_timeseries_historical():
            balance_key_1 = (
                types.defaultAddress.fixed_value,
                types.defaultAsset.fixed_value,
                "GBP",
                types.Phase.COMMITTED,
            )
            balance_dict = types.BalanceDefaultDict()
            balance_dict[balance_key_1] = types.Balance(
                net=Decimal(20), credit=Decimal(20), debit=Decimal(0)
            )
            balance_timeseries = types.BalanceTimeseries(
                [
                    (self.effective_date, balance_dict),
                ]
            )
            return balance_timeseries

        def get_balances_new():
            balance_key_1 = (
                types.defaultAddress.fixed_value,
                types.defaultAsset.fixed_value,
                "GBP",
                types.Phase.COMMITTED,
            )
            balance_dict = types.BalanceDefaultDict()
            balance_dict[balance_key_1] = types.Balance(
                net=Decimal(-30), credit=Decimal(0), debit=Decimal(-30)
            )
            return balance_dict

        pi = types.PostingInstruction(
            custom_instruction_grouping_key="some_key",
            client_transaction_id="id_12345",
            type=types.PostingInstructionType.CUSTOM_INSTRUCTION,
            pics=[],
            credit=True,
            amount=Decimal(10),
            denomination="GBP",
            account_id=self.account_id,
            account_address=types.defaultAddress.fixed_value,
            asset=types.defaultAsset.fixed_value,
            phase=types.Phase.COMMITTED,
        )
        pi.client_batch_id = "123"
        pi.value_timestamp = self.effective_date
        pi.insertion_timestamp = self.effective_date
        pi.batch_details = {}
        pi.client_id = "1"
        pi.batch_id = "2"

        pi.balances = get_balances_new

        posting_instructions = [pi]
        postings = types.PostingInstructionBatch(
            posting_instructions=posting_instructions,
            value_timestamp=self.effective_date,
            insertion_timestamp=self.effective_date,
            batch_details={},
            client_batch_id="123",
        )
        # Mock balances of the new postings - this will be calculated
        # automatically in the future versions of the SDK.
        postings.balances = get_balances_new

        # Mock historical balance timeseries
        self.vault.get_balance_timeseries.side_effect = get_balance_timeseries_historical

        with self.assertRaises(types.Rejected) as ex:
            self.run_contract_function(
                self.contract_code, "pre_posting_code", postings, self.effective_date
            )

        self.assertEqual("Account Default address cannot go into overdraft", str(ex.exception))

    def test_pre_posting_code_ensure_can_use_client_transaction(self):
        def get_balances():
            balance_key_1 = (
                types.defaultAddress.fixed_value,
                types.defaultAsset.fixed_value,
                "GBP",
                types.Phase.COMMITTED,
            )
            balance_dict = types.BalanceDefaultDict()
            balance_dict[balance_key_1] = types.Balance(
                net=Decimal(10), credit=Decimal(10), debit=Decimal(0)
            )
            return balance_dict

        def get_effects():
            key = (types.defaultAddress.fixed_value, types.defaultAsset.fixed_value, "GBP")
            effects_dict = types.ClientTransactionEffectsDefaultDict()
            effects_dict[key] = types.ClientTransactionEffects(
                authorised=Decimal(20),
                settled=Decimal(10),
                unsettled=Decimal(10),
                released=Decimal(0),
            )
            return effects_dict

        posting_instructions = [
            types.PostingInstruction(
                custom_instruction_grouping_key="some_key",
                client_transaction_id="client-transaction-id",
                type=types.PostingInstructionType.AUTHORISATION,
                pics=[],
                credit=True,
                amount=Decimal(20),
                denomination="GBP",
                account_id=self.account_id,
                account_address=types.defaultAddress.fixed_value,
                asset=types.defaultAsset.fixed_value,
                phase=types.Phase.PENDING_IN,
            ),
            types.PostingInstruction(
                custom_instruction_grouping_key="some_key",
                client_transaction_id="client-transaction-id",
                type=types.PostingInstructionType.SETTLEMENT,
                pics=[],
                credit=True,
                amount=Decimal(10),
                denomination="GBP",
                account_id=self.account_id,
                account_address=types.defaultAddress.fixed_value,
                asset=types.defaultAsset.fixed_value,
                phase=types.Phase.COMMITTED,
                final=False,
            ),
        ]
        posting_instructions[0].value_timestamp = self.effective_date
        ctx = types.ClientTransaction(posting_instructions)
        # Mock balances of the new postings - this will be calculated
        # automatically in the future versions of the SDK.
        ctx.effects = get_effects
        ctx.balances = get_balances

        ctxs = {("client-id", "client-transaction-id"): ctx}
        self.vault.get_client_transactions.return_value = ctxs

        # The hook argument
        postings = types.PostingInstructionBatch(
            posting_instructions=posting_instructions,
            value_timestamp=self.effective_date,
            insertion_timestamp=self.effective_date,
            batch_details={},
            client_batch_id="123",
        )

        self.run_contract_function(
            self.contract_code, "pre_posting_code", postings, self.effective_date
        )
