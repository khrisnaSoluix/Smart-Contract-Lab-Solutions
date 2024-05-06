from datetime import datetime
from decimal import Decimal
import os
from unittest import mock

from ...utils.tools import SmartContracts340TestCase
from ...versions.version_340.smart_contracts import types


class SavingsAccountTestCase(SmartContracts340TestCase):

    filepath = os.environ.get(
        "DATA_SAVINGS_V340", "contracts_sdk/example_unit_tests/smart_contracts/savings_v340.py"
    )
    contract_code = SmartContracts340TestCase.load_contract_code(filepath)
    old_parameter_values = {}

    creation_date = datetime(year=2020, month=2, day=15)
    key_date = types.Parameter(
        name="key_date",
        description="Do you want to choose the day you are paid interest?",
        display_name="Elected day of month to pay interest on",
        level=types.Level.INSTANCE,
        update_permission=types.UpdatePermission.USER_EDITABLE,
        value=types.OptionalValue(Decimal(25)),
        default_value=types.OptionalValue(Decimal(28)),
        shape=types.OptionalShape(
            types.NumberShape(
                min_value=1,
                max_value=31,
                step=1,
            )
        ),
    )
    effective_date = datetime(year=2020, month=2, day=15)

    def test_execution_schedules_selects_pay_day_via_helper_functions(self):
        self.vault.get_account_creation_date.return_value = self.creation_date

        def get_parameter_timeseries(name):
            timeseries = mock.Mock()
            if name == "key_date":
                timeseries.at.return_value = self.key_date.value
            return timeseries

        self.vault.get_parameter_timeseries.side_effect = get_parameter_timeseries

        schedules = self.run_contract_function(
            self.contract_code,
            "execution_schedules",
        )
        self.assertEqual(
            (
                (
                    "APPLY_ACCRUED_INTEREST",
                    {"day": str(self.key_date.value.value), "hour": "0", "minute": "1"},
                ),
                ("ACCRUE_INTEREST", {"hour": "0"}),
            ),
            schedules,
        )

    def test_pre_parameter_change_code_updates_parameters(self):
        self.vault.get_account_creation_date.return_value = self.creation_date
        parameters = {"key_date": self.key_date}

        parameters = self.run_contract_function(
            self.contract_code, "pre_parameter_change_code", parameters, self.effective_date
        )

        self.assertEqual(
            types.OptionalValue(Decimal(self.creation_date.day)).value,
            parameters["key_date"].default_value.value,
        )

    def test_pre_parameter_change_code_does_not_change_parameters(self):
        parameters = self.run_contract_function(
            self.contract_code, "pre_parameter_change_code", {}, self.effective_date
        )
        self.assertEqual({}, parameters)

    def test_post_parameter_change_code_does_not_amend_schedule_if_key_date_not_updated(self):
        self.run_contract_function(
            self.contract_code,
            "post_parameter_change_code",
            self.old_parameter_values,
            {},
            self.effective_date,
        )

        self.vault.amend_schedule.assert_not_called()

    def test_post_parameter_change_code_amends_schedule(self):
        updated_parameter_values = {"key_date": self.key_date}
        self.run_contract_function(
            self.contract_code,
            "post_parameter_change_code",
            self.old_parameter_values,
            updated_parameter_values,
            self.effective_date,
        )

        self.vault.amend_schedule.assert_called_once_with(
            event_type="APPLY_ACCRUED_INTEREST", new_schedule=None
        )

    def test_get_selected_interest_payday_with_effective_date(self):
        def get_parameter_timeseries(name):
            timeseries = mock.Mock()
            if name == "key_date":
                timeseries.at.return_value = self.key_date.value
            return timeseries

        self.vault.get_parameter_timeseries.side_effect = get_parameter_timeseries

        output_payday = self.run_contract_function(
            self.contract_code, "_get_selected_interest_payday", self.vault, self.effective_date
        )

        self.vault.get_parameter_timeseries.assert_called_once_with(name="key_date")
        self.assertEqual(Decimal(25), output_payday)

    def test_get_selected_interest_payday_with_no_effective_date(self):
        self.vault.get_account_creation_date.return_value = self.creation_date

        def get_parameter_timeseries(name):
            timeseries = mock.Mock()
            if name == "key_date":
                # An empty value -> account creation date being used.
                timeseries.latest.return_value = types.OptionalValue()
            return timeseries

        self.vault.get_parameter_timeseries.side_effect = get_parameter_timeseries
        output_payday = self.run_contract_function(
            self.contract_code, "_get_selected_interest_payday", self.vault, None
        )

        self.vault.get_parameter_timeseries.assert_called_once_with(name="key_date")
        self.assertEqual(Decimal(15), output_payday)

    def test_get_interest_payday_for_same_month_payment(self):
        selected_day = 1
        output_day = self.run_contract_function(
            self.contract_code, "_get_interest_payday", selected_day, self.effective_date
        )

        self.assertEqual("1", output_day)

    def test_get_interest_payday_for_next_month_payment(self):
        selected_day = 22
        output_day = self.run_contract_function(
            self.contract_code,
            "_get_interest_payday",
            selected_day,
            self.effective_date,
            has_paid_interest_this_month=True,
        )

        self.assertEqual("22", output_day)
