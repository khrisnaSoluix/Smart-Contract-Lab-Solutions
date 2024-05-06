from datetime import datetime
from decimal import Decimal
from unittest import mock
import os

from ...utils.tools import SmartContracts3100TestCase
from ...versions.version_3100.smart_contracts import types


class SimpleTestCase(SmartContracts3100TestCase):
    filepath = os.environ.get(
        "DATA_SIMPLE_V3100", "contracts_sdk/example_unit_tests/smart_contracts/simple_v3100.py"
    )
    contract_code = SmartContracts3100TestCase.load_contract_code(filepath)

    effective_date = datetime(year=2020, month=2, day=20)
    pause_datetime = datetime(year=2020, month=2, day=15)

    def _get_balances_observation(self, fetcher_id=None):
        get_balances_observation = mock.Mock()
        if fetcher_id == "lbof_1":
            balances_observation_balances = types.BalanceDefaultDict()
            balances_observation_balances[
                (
                    types.defaultAddress.fixed_value,
                    types.defaultAsset.fixed_value,
                    "GBP",
                    types.Phase.COMMITTED,
                )
            ] = types.Balance(credit=Decimal(10), debit=Decimal(0), net=Decimal(10))

            get_balances_observation = types.BalancesObservation(
                value_datetime=None, balances=balances_observation_balances
            )

        return get_balances_observation

    def _get_empty_balances_observation(self, fetcher_id=None):
        get_balances_observation = mock.Mock()
        if fetcher_id == "lbof_1":
            balances_observation_balances = types.BalanceDefaultDict()
            get_balances_observation = types.BalancesObservation(
                value_datetime=None, balances=balances_observation_balances
            )
        return get_balances_observation

    def test_scheduled_code_get_scheduled_job_details(self):
        self.vault.get_scheduled_job_details.return_value = types.ScheduledJob(
            pause_datetime=self.pause_datetime
        )
        self.run_contract_function(
            self.contract_code, "scheduled_code", "SCHEDULE_JOB_DETAILS", self.effective_date
        )

        self.vault.add_account_note.assert_called_once_with(
            body="pause_datetime: 2020-02-15 00:00:00",
            note_type=types.NoteType.RAW_TEXT,
            is_visible_to_customer=True,
            date=self.effective_date,
        )

    def test_scheduled_code_get_balances_observation(self):
        self.vault.get_balances_observation.side_effect = self._get_balances_observation
        self.run_contract_function(
            self.contract_code, "scheduled_code", "FETCH_BALANCES_OBSERVATION", self.effective_date
        )

        self.vault.add_account_note.assert_called_once_with(
            body="live_balances_observation: None, 10",
            note_type=types.NoteType.RAW_TEXT,
            is_visible_to_customer=True,
            date=self.effective_date,
        )

    def test_scheduled_code_get_balances_observation_no_initial_balances(self):
        self.vault.get_balances_observation.side_effect = self._get_empty_balances_observation
        self.run_contract_function(
            self.contract_code, "scheduled_code", "FETCH_BALANCES_OBSERVATION", self.effective_date
        )
        self.vault.add_account_note.assert_called_once_with(
            body="live_balances_observation: None, 0",
            note_type=types.NoteType.RAW_TEXT,
            is_visible_to_customer=True,
            date=self.effective_date,
        )
