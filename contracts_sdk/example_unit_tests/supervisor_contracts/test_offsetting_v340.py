from datetime import datetime
from decimal import Decimal
import os
from unittest import mock

from ...utils.tools import SupervisorContracts340TestCase
from ...versions.version_340.supervisor_contracts import types


class OffsettingTestCase(SupervisorContracts340TestCase):

    filepath = os.environ.get(
        "DATA_OFFSETTING_V340",
        "contracts_sdk/example_unit_tests/supervisor_contracts/offsetting_v340.py",
    )
    contract_code = SupervisorContracts340TestCase.load_contract_code(filepath)

    def test_execution_schedules_fails_if_no_key_date_provided(self):
        mortgage_supervisee = self.create_supervisee_vault()
        mortgage_supervisee.tside = types.Tside.ASSET

        self.vault.supervisees = {"mortgage": mortgage_supervisee}

        with self.assertRaises(types.InvalidContractParameter) as ex:
            self.run_contract_function(self.contract_code, "execution_schedules")

        self.assertIn("Cannot get key_date parameter value from supervisees", str(ex.exception))

    def test_execution_schedules_with_key_date_provided(self):
        def get_parameter_timeseries(name):
            timeseries = mock.Mock()
            if name == "key_date":
                timeseries.latest.return_value = Decimal(28)
            return timeseries

        mortgage_supervisee = self.create_supervisee_vault()
        mortgage_supervisee.tside = types.Tside.ASSET

        savings_supervisee = self.create_supervisee_vault()
        savings_supervisee.get_parameter_timeseries.side_effect = get_parameter_timeseries
        savings_supervisee.tside = types.Tside.LIABILITY

        self.vault.supervisees = {"mortgage": mortgage_supervisee, "savings": savings_supervisee}

        execution_schedules = self.run_contract_function(self.contract_code, "execution_schedules")
        self.assertEqual(
            [
                (
                    "APPLY_MONTHLY_INTEREST_OFFSETTING",
                    {
                        "day": f"{Decimal(28)}",
                        "hour": "23",
                        "minute": "59",
                        "second": "59",
                    },
                )
            ],
            execution_schedules,
        )

    def test_scheduled_code_fails_if_unknown_tside_provided(self):
        effective_date = datetime(year=2020, month=2, day=15)

        def get_hook_directives():
            return types.HookDirectives(
                add_account_note_directives=[],
                amend_schedule_directives=[],
                remove_schedules_directives=[],
                workflow_start_directives=[],
                posting_instruction_batch_directives=[
                    types.PostingInstructionBatchDirective(
                        request_id="request_id",
                        posting_instruction_batch=types.PostingInstructionBatch(
                            batch_id="test",
                            batch_details={},
                            client_id="Visa",
                            client_batch_id="international_payment",
                            value_timestamp=effective_date,
                            posting_instructions=[],
                        ),
                    )
                ],
            )

        unknown_tside_supervisee = self.create_supervisee_vault()
        unknown_tside_supervisee.get_hook_directives.side_effect = get_hook_directives
        unknown_tside_supervisee.tside = "unknown"
        unknown_tside_supervisee.account_id = "supervisee"

        self.vault.supervisees = {"supervisee": unknown_tside_supervisee}

        with self.assertRaises(types.Rejected) as ex:
            self.run_contract_function(
                self.contract_code,
                "scheduled_code",
                event_type="APPLY_MONTHLY_INTEREST_OFFSETTING",
                effective_date=effective_date,
            )

        self.assertIn(
            "Got unexpected account T-side. It should be either an Asset or Liability type",
            str(ex.exception),
        )

    def test_scheduled_code_with_higher_mortgage_balance(self):
        effective_date = datetime(year=2020, month=2, day=15)
        balance_key_1 = (
            types.defaultAddress.fixed_value,
            types.defaultAsset.fixed_value,
            "GBP",
            types.Phase.COMMITTED,
        )
        balance_key_2 = (
            types.defaultAddress.fixed_value,
            types.defaultAsset.fixed_value,
            "GBP",
            types.Phase.PENDING_OUT,
        )
        mortgage_posting_instruction_directive = types.PostingInstruction(
            custom_instruction_grouping_key="some_key",
            client_transaction_id="mortgage_payment_id",
            pics=["MORTGAGE_PAYMENT"],
            instruction_details={"TYPE": "REPAYMENT"},
            type=types.PostingInstructionType.CUSTOM_INSTRUCTION,
            credit=True,
            amount=Decimal(10),
            denomination="GBP",
            account_id="mortgage",
            account_address=types.defaultAddress.fixed_value,
            asset=types.defaultAsset.fixed_value,
            phase=types.Phase.COMMITTED,
        )

        def get_mortgage_hook_directives():
            return types.HookDirectives(
                add_account_note_directives=[],
                amend_schedule_directives=[],
                remove_schedules_directives=[],
                workflow_start_directives=[],
                posting_instruction_batch_directives=[
                    types.PostingInstructionBatchDirective(
                        request_id="mortgage_request_id",
                        posting_instruction_batch=types.PostingInstructionBatch(
                            batch_id="mortgage_batch",
                            batch_details={},
                            client_batch_id="mortgage_payment",
                            value_timestamp=effective_date,
                            posting_instructions=[mortgage_posting_instruction_directive],
                        ),
                    )
                ],
            )

        def get_mortgage_balance_timeseries():
            balance_dict = types.BalanceDefaultDict(lambda *_: types.Balance())
            balance_dict[balance_key_1] = types.Balance(net=Decimal(2))
            balance_dict[balance_key_2] = types.Balance(net=Decimal(10))
            balance_timeseries = types.BalanceTimeseries(
                [
                    (effective_date, balance_dict),
                ]
            )
            return balance_timeseries

        savings_posting_instruction_directive = types.PostingInstruction(
            custom_instruction_grouping_key="some_key",
            client_transaction_id="savings_payment_id",
            pics=["SAVINGS_PAYMENT"],
            instruction_details={"TYPE": "SAVINGS"},
            type=types.PostingInstructionType.CUSTOM_INSTRUCTION,
            credit=False,
            amount=Decimal(10),
            denomination="GBP",
            account_id="savings",
            account_address=types.defaultAddress.fixed_value,
            asset=types.defaultAsset.fixed_value,
            phase=types.Phase.COMMITTED,
        )

        def get_savings_hook_directives():
            return types.HookDirectives(
                add_account_note_directives=[],
                amend_schedule_directives=[],
                remove_schedules_directives=[],
                workflow_start_directives=[],
                posting_instruction_batch_directives=[
                    types.PostingInstructionBatchDirective(
                        request_id="savings_request_id",
                        posting_instruction_batch=types.PostingInstructionBatch(
                            batch_id="savings_batch",
                            batch_details={},
                            client_batch_id="savings_payment",
                            value_timestamp=effective_date,
                            posting_instructions=[savings_posting_instruction_directive],
                        ),
                    )
                ],
            )

        def get_savings_balance_timeseries():
            balance_dict = types.BalanceDefaultDict(lambda *_: types.Balance())
            balance_dict[balance_key_1] = types.Balance(net=Decimal(1))
            balance_dict[balance_key_2] = types.Balance(net=Decimal(10))
            balance_timeseries = types.BalanceTimeseries(
                [
                    (effective_date, balance_dict),
                ]
            )
            return balance_timeseries

        def get_parameter_timeseries(name):
            timeseries = mock.Mock()
            if name == "effective_interest":
                timeseries.latest.return_value = Decimal(0.1)
            return timeseries

        mortgage_supervisee = self.create_supervisee_vault()
        mortgage_supervisee.get_hook_directives.side_effect = get_mortgage_hook_directives
        mortgage_supervisee.get_balance_timeseries.side_effect = get_mortgage_balance_timeseries
        mortgage_supervisee.get_parameter_timeseries.side_effect = get_parameter_timeseries
        mortgage_supervisee.tside = types.Tside.ASSET
        mortgage_supervisee.account_id = "mortgage"

        savings_supervisee = self.create_supervisee_vault()
        savings_supervisee.get_hook_directives.side_effect = get_savings_hook_directives
        savings_supervisee.get_balance_timeseries.side_effect = get_savings_balance_timeseries
        savings_supervisee.tside = types.Tside.LIABILITY
        savings_supervisee.account_id = "savings"

        self.vault.supervisees = {"mortgage": mortgage_supervisee, "savings": savings_supervisee}

        self.run_contract_function(
            self.contract_code,
            "scheduled_code",
            event_type="APPLY_MONTHLY_INTEREST_OFFSETTING",
            effective_date=effective_date,
        )
        self.vault.supervisees[
            "mortgage"
        ].make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal(0.1) * Decimal(12),
            denomination="GBP",
            client_transaction_id="some_client_transaction_id",
            from_account_id="mortgage",
            to_account_id="mortgage",
            asset=types.defaultAsset.fixed_value,
        )
        self.vault.supervisees["mortgage"].instruct_posting_batch.assert_called_once_with(
            posting_instructions=[savings_posting_instruction_directive]
        )

    def test_scheduled_code_with_higher_savings_balance(self):
        effective_date = datetime(year=2020, month=2, day=15)
        balance_key_1 = (
            types.defaultAddress.fixed_value,
            types.defaultAsset.fixed_value,
            "GBP",
            types.Phase.COMMITTED,
        )
        balance_key_2 = (
            types.defaultAddress.fixed_value,
            types.defaultAsset.fixed_value,
            "GBP",
            types.Phase.PENDING_OUT,
        )
        mortgage_posting_instruction_directive = types.PostingInstruction(
            custom_instruction_grouping_key="some_key",
            client_transaction_id="mortgage_payment_id",
            pics=["MORTGAGE_PAYMENT"],
            instruction_details={"TYPE": "REPAYMENT"},
            type=types.PostingInstructionType.CUSTOM_INSTRUCTION,
            credit=True,
            amount=Decimal(10),
            denomination="GBP",
            account_id="mortgage",
            account_address=types.defaultAddress.fixed_value,
            asset=types.defaultAsset.fixed_value,
            phase=types.Phase.COMMITTED,
        )

        def get_mortgage_hook_directives():
            return types.HookDirectives(
                add_account_note_directives=[],
                amend_schedule_directives=[],
                remove_schedules_directives=[],
                workflow_start_directives=[],
                posting_instruction_batch_directives=[
                    types.PostingInstructionBatchDirective(
                        request_id="mortgage_request_id",
                        posting_instruction_batch=types.PostingInstructionBatch(
                            batch_id="mortgage_batch",
                            batch_details={},
                            client_batch_id="mortgage_payment",
                            value_timestamp=effective_date,
                            posting_instructions=[mortgage_posting_instruction_directive],
                        ),
                    )
                ],
            )

        def get_mortgage_balance_timeseries():
            balance_dict = types.BalanceDefaultDict(lambda *_: types.Balance())
            balance_dict[balance_key_1] = types.Balance(net=Decimal(1))
            balance_dict[balance_key_2] = types.Balance(net=Decimal(10))
            balance_timeseries = types.BalanceTimeseries(
                [
                    (effective_date, balance_dict),
                ]
            )
            return balance_timeseries

        savings_posting_instruction_directive = types.PostingInstruction(
            custom_instruction_grouping_key="some_key",
            client_transaction_id="savings_payment_id",
            pics=["SAVINGS_PAYMENT"],
            instruction_details={"TYPE": "SAVINGS"},
            type=types.PostingInstructionType.CUSTOM_INSTRUCTION,
            credit=False,
            amount=Decimal(10),
            denomination="GBP",
            account_id="savings",
            account_address=types.defaultAddress.fixed_value,
            asset=types.defaultAsset.fixed_value,
            phase=types.Phase.COMMITTED,
        )

        def get_savings_hook_directives():
            return types.HookDirectives(
                add_account_note_directives=[],
                amend_schedule_directives=[],
                remove_schedules_directives=[],
                workflow_start_directives=[],
                posting_instruction_batch_directives=[
                    types.PostingInstructionBatchDirective(
                        request_id="savings_request_id",
                        posting_instruction_batch=types.PostingInstructionBatch(
                            batch_id="savings_batch",
                            batch_details={},
                            client_batch_id="savings_payment",
                            value_timestamp=effective_date,
                            posting_instructions=[savings_posting_instruction_directive],
                        ),
                    )
                ],
            )

        def get_savings_balance_timeseries():
            balance_dict = types.BalanceDefaultDict(lambda *_: types.Balance())
            balance_dict[balance_key_1] = types.Balance(net=Decimal(2))
            balance_dict[balance_key_2] = types.Balance(net=Decimal(10))
            balance_timeseries = types.BalanceTimeseries(
                [
                    (effective_date, balance_dict),
                ]
            )
            return balance_timeseries

        def get_parameter_timeseries(name):
            timeseries = mock.Mock()
            if name == "effective_interest":
                timeseries.latest.return_value = Decimal(0.1)
            return timeseries

        mortgage_supervisee = self.create_supervisee_vault()
        mortgage_supervisee.get_hook_directives.side_effect = get_mortgage_hook_directives
        mortgage_supervisee.get_balance_timeseries.side_effect = get_mortgage_balance_timeseries
        mortgage_supervisee.tside = types.Tside.ASSET
        mortgage_supervisee.account_id = "mortgage"

        savings_supervisee = self.create_supervisee_vault()
        savings_supervisee.get_hook_directives.side_effect = get_savings_hook_directives
        savings_supervisee.get_balance_timeseries.side_effect = get_savings_balance_timeseries
        savings_supervisee.get_parameter_timeseries.side_effect = get_parameter_timeseries
        savings_supervisee.tside = types.Tside.LIABILITY
        savings_supervisee.account_id = "savings"

        self.vault.supervisees = {"mortgage": mortgage_supervisee, "savings": savings_supervisee}

        self.run_contract_function(
            self.contract_code,
            "scheduled_code",
            event_type="APPLY_MONTHLY_INTEREST_OFFSETTING",
            effective_date=effective_date,
        )
        self.vault.supervisees[
            "savings"
        ].make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal(0.1) * Decimal(12),
            denomination="GBP",
            client_transaction_id="some_client_transaction_id",
            from_account_id="savings",
            to_account_id="savings",
            asset=types.defaultAsset.fixed_value,
        )
        self.vault.supervisees["savings"].instruct_posting_batch.assert_called_once_with(
            posting_instructions=[savings_posting_instruction_directive]
        )
