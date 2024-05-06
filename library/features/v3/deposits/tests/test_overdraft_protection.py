from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, Mock, MagicMock
from typing import Union, Optional

from inception_sdk.test_framework.contracts.unit.common import (
    balance_dimensions,
    Tside,
)

from inception_sdk.test_framework.contracts.unit.supervisor.common import (
    SupervisorContractTest,
)

from inception_sdk.vault.contracts.supervisor.types_extension import (
    Phase,
    Balance,
    Rejected,
    BalanceDefaultDict,
    BalancesObservation,
    PostingInstructionBatch,
)
from inception_sdk.vault.contracts.types import RejectedReason

import library.features.v3.deposits.overdraft_protection as odp
from library.features.v3.common.tests.mocks import mock_utils_get_parameter

DEFAULT_DATE = datetime(2019, 1, 1)
DEFAULT_DENOMINATION = "USD"

DEFAULT_DIMENSIONS = balance_dimensions(denomination=DEFAULT_DENOMINATION)
PENDING_OUTGOING_DIMENSIONS = balance_dimensions(
    denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_OUT
)
PENDING_INCOMING_DIMENSIONS = balance_dimensions(
    denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_IN
)


class ODPTestCommon(SupervisorContractTest):

    target_test_file = "library/features/v3/deposits/overdraft_protection.py"
    side = Tside.LIABILITY
    default_denom = DEFAULT_DENOMINATION

    def balances_for_account(
        self,
        dt=DEFAULT_DATE,
        default=Decimal("0"),
        pending_outgoing=Decimal("0"),
    ):

        balance_default_dict = BalanceDefaultDict(
            lambda: Balance(net=Decimal("0")),
            {
                DEFAULT_DIMENSIONS: Balance(net=Decimal(default)),
                PENDING_OUTGOING_DIMENSIONS: Balance(net=Decimal(pending_outgoing)),
            },
        )

        return [(dt, balance_default_dict)]

    def get_outbound_hard_settlement_mock(
        self,
        amount: str,
        account_id: str = "CHECKING_ACCOUNT",
    ) -> PostingInstructionBatch:
        return self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    denomination=DEFAULT_DENOMINATION, amount=amount, account_id=account_id
                ),
            ],
        )

    def get_outbound_auth_pib_mock(
        self,
        amount: str,
        account_id: str = "CHECKING_ACCOUNT",
    ) -> PostingInstructionBatch:
        return self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_auth(
                    denomination=DEFAULT_DENOMINATION, amount=amount, account_id=account_id
                ),
            ],
        )

    def get_inbound_hard_settlement_mock(self, amount):
        return self.mock_posting_instruction_batch(
            posting_instructions=[
                self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=amount),
            ],
        )

    def get_default_setup(
        self,
        checking_balance: Optional[list[tuple[datetime, BalanceDefaultDict]]] = None,
        savings_balance: Optional[list[tuple[datetime, BalanceDefaultDict]]] = None,
        checking_account_hook_return_data: Optional[Union[Rejected, None]] = None,
        posting_instructions_by_supervisee: Optional[
            Union[dict[str, PostingInstructionBatch], None]
        ] = None,
        existing_mock: Optional[Mock] = None,
    ) -> tuple[Mock, Mock, Mock]:
        balance_ts_checking = checking_balance or self.balances_for_account()
        balance_ts_savings = savings_balance or self.balances_for_account()
        balance_observation_fetchers = {
            "checking_account": {
                "live_balance": BalancesObservation(balances=balance_ts_checking[0][1])
            },
            "savings_account": {
                "live_balance": BalancesObservation(balances=balance_ts_savings[0][1])
            },
        }
        balances_observation_fetchers = balance_observation_fetchers or {}
        checking_observation_fetcher = balances_observation_fetchers.get("checking_account")
        savings_observation_fetcher = balances_observation_fetchers.get("savings_account")

        mock_vault_checking = self.create_supervisee_mock(
            alias="us_checking",
            account_id="CHECKING_ACCOUNT",
            balance_ts=balance_ts_checking,
            balances_observation_fetchers_mapping=checking_observation_fetcher,
            denomination=DEFAULT_DENOMINATION,
            additional_denominations="[]",
            hook_return_data=checking_account_hook_return_data,
        )

        mock_vault_savings = self.create_supervisee_mock(
            alias="us_savings",
            account_id="SAVINGS_ACCOUNT",
            balance_ts=balance_ts_savings,
            balances_observation_fetchers_mapping=savings_observation_fetcher,
        )

        supervisees = {
            "CHECKING_ACCOUNT": mock_vault_checking,
            "SAVINGS_ACCOUNT": mock_vault_savings,
        }

        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            existing_mock=existing_mock,
        )

        return (mock_vault, mock_vault_checking, mock_vault_savings)


class ODPValidateTest(ODPTestCommon):
    disable_rendering = True

    def test_validation_reraises_rejection_for_reason_other_than_insuf_funds(
        self,
    ):
        hook_return_data = Rejected("Other Rejection", reason_code=RejectedReason.AGAINST_TNC)

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_account_hook_return_data=hook_return_data
        )

        with self.assertRaises(Rejected) as r:
            odp.validate(mock_vault, mock_vault_checking, mock_vault_savings)
        self.assertEqual(r.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(
            r.exception.message,
            "Other Rejection",
        )

    def test_validation_raises_if_multiple_savings_accounts_attached(
        self,
    ):
        hook_return_data = Rejected(
            "INSUFFICIENT_FUNDS", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_account_hook_return_data=hook_return_data
        )

        with self.assertRaises(Rejected) as r:
            odp.validate(mock_vault, mock_vault_checking, ["SAVINGS1", "SAVINGS2"])
        self.assertEqual(r.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(
            r.exception.message,
            "Requested 1 us_savings accounts but found 2.",
        )

    def test_validation_reraises_rejection_if_no_savings_account_attached(
        self,
    ):
        hook_return_data = Rejected(
            "INSUFFICIENT_FUNDS", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_account_hook_return_data=hook_return_data
        )

        with self.assertRaises(Rejected) as r:
            odp.validate(mock_vault, mock_vault_checking, [])
        self.assertEqual(r.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)
        self.assertEqual(
            r.exception.message,
            "INSUFFICIENT_FUNDS",
        )

    @patch.object(odp.supervisor_utils, "sum_available_balances_across_supervisees")
    @patch.object(odp.utils, "get_available_balance")
    def test_validation_passes_if_posting_not_originally_rejected(
        self,
        mock_get_available_balance: MagicMock,
        mock_sum_available_balances_across_supervisees: MagicMock,
    ):

        pib = self.get_inbound_hard_settlement_mock("50")
        posting_instructions_by_supervisee = {"CHECKING_ACCOUNT": pib}

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
        )
        self.assertIsNone(odp.validate(mock_vault, mock_vault_checking, mock_vault_savings))
        mock_get_available_balance.assert_not_called()
        mock_sum_available_balances_across_supervisees.assert_not_called()

    @patch.object(odp.supervisor_utils, "sum_available_balances_across_supervisees")
    @patch.object(odp.utils, "get_available_balance")
    @patch.object(odp.utils, "get_parameter")
    def test_validation_reraises_if_combined_balance_insufficient(
        self,
        mock_get_parameter: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_sum_available_balances_across_supervisees: MagicMock,
    ):
        hook_return_data = Rejected(
            "INSUFFICIENT_FUNDS", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=dict(denomination=self.default_denom, standard_overdraft_limit=0)
        )
        mock_get_available_balance.return_value = Decimal("-50")
        mock_sum_available_balances_across_supervisees.return_value = Decimal("10")
        pib = self.get_outbound_hard_settlement_mock("50")
        posting_instructions_by_supervisee = {"CHECKING_ACCOUNT": pib}

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            checking_account_hook_return_data=hook_return_data,
        )

        with self.assertRaises(Rejected) as r:
            odp.validate(mock_vault, mock_vault_checking, [mock_vault_savings])
        self.assertEqual(r.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)
        self.assertEqual(
            r.exception.message,
            (
                "Combined checking and savings account balance 10 "
                "insufficient to cover net transaction amount -50"
            ),
        )
        mock_get_available_balance.assert_called_once_with(pib.balances(), self.default_denom)
        mock_sum_available_balances_across_supervisees.assert_called_once_with(
            [mock_vault_checking, mock_vault_savings],
            denomination=self.default_denom,
            observation_fetcher_id="live_balance",
            rounding_precision=2,
        )

    @patch.object(odp.supervisor_utils, "sum_available_balances_across_supervisees")
    @patch.object(odp.utils, "get_available_balance")
    @patch.object(odp.utils, "get_parameter")
    def test_validation_passes_if_combined_balance_sufficient(
        self,
        mock_get_parameter: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_sum_available_balances_across_supervisees: MagicMock,
    ):
        hook_return_data = Rejected(
            "INSUFFICIENT_FUNDS", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=dict(denomination=self.default_denom, standard_overdraft_limit=0)
        )
        mock_get_available_balance.return_value = Decimal("-50")
        mock_sum_available_balances_across_supervisees.return_value = Decimal("50")
        pib = self.get_outbound_hard_settlement_mock("50")
        posting_instructions_by_supervisee = {"CHECKING_ACCOUNT": pib}

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            checking_account_hook_return_data=hook_return_data,
        )

        self.assertIsNone(odp.validate(mock_vault, mock_vault_checking, [mock_vault_savings]))

        mock_get_available_balance.assert_called_once_with(pib.balances(), self.default_denom)
        mock_sum_available_balances_across_supervisees.assert_called_once_with(
            [mock_vault_checking, mock_vault_savings],
            denomination=self.default_denom,
            observation_fetcher_id="live_balance",
            rounding_precision=2,
        )

    @patch.object(odp.supervisor_utils, "sum_available_balances_across_supervisees")
    @patch.object(odp.utils, "get_available_balance")
    @patch.object(odp.utils, "get_parameter")
    def test_validation_passes_if_combined_balance_plus_standard_overdraft_sufficient(
        self,
        mock_get_parameter: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_sum_available_balances_across_supervisees: MagicMock,
    ):
        hook_return_data = Rejected(
            "INSUFFICIENT_FUNDS", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=dict(denomination=self.default_denom, standard_overdraft_limit=10)
        )
        mock_get_available_balance.return_value = Decimal("-60")
        mock_sum_available_balances_across_supervisees.return_value = Decimal("50")
        pib = self.get_outbound_hard_settlement_mock("50")
        posting_instructions_by_supervisee = {"CHECKING_ACCOUNT": pib}

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            checking_account_hook_return_data=hook_return_data,
        )

        self.assertIsNone(odp.validate(mock_vault, mock_vault_checking, [mock_vault_savings]))

        mock_get_available_balance.assert_called_once_with(pib.balances(), self.default_denom)
        mock_sum_available_balances_across_supervisees.assert_called_once_with(
            [mock_vault_checking, mock_vault_savings],
            denomination=self.default_denom,
            observation_fetcher_id="live_balance",
            rounding_precision=2,
        )

    @patch.object(odp.supervisor_utils, "sum_available_balances_across_supervisees")
    @patch.object(odp.utils, "get_available_balance")
    @patch.object(odp.utils, "get_parameter")
    def test_validation_reraises_if_combined_balance_plus_standard_overdraft_insufficient(
        self,
        mock_get_parameter: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_sum_available_balances_across_supervisees: MagicMock,
    ):
        hook_return_data = Rejected(
            "INSUFFICIENT_FUNDS", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=dict(denomination=self.default_denom, standard_overdraft_limit=5)
        )
        mock_get_available_balance.return_value = Decimal("-60")
        mock_sum_available_balances_across_supervisees.return_value = Decimal("50")
        pib = self.get_outbound_hard_settlement_mock("50")
        posting_instructions_by_supervisee = {"CHECKING_ACCOUNT": pib}

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            checking_account_hook_return_data=hook_return_data,
        )

        with self.assertRaises(Rejected) as r:
            odp.validate(mock_vault, mock_vault_checking, [mock_vault_savings])
        self.assertEqual(r.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)
        self.assertEqual(
            r.exception.message,
            (
                "Combined checking and savings account balance 50 "
                "insufficient to cover net transaction amount -60"
            ),
        )
        mock_get_available_balance.assert_called_once_with(pib.balances(), self.default_denom)
        mock_sum_available_balances_across_supervisees.assert_called_once_with(
            [mock_vault_checking, mock_vault_savings],
            denomination=self.default_denom,
            observation_fetcher_id="live_balance",
            rounding_precision=2,
        )


class ODPSweepTest(ODPTestCommon):
    def test_handle_odp_sweep_raises_if_no_us_savings_account_linked(self):

        mock_vault_checking = self.create_supervisee_mock(
            alias="us_checking",
            account_id="CHECKING_ACCOUNT",
        )

        supervisees = {
            "CHECKING_ACCOUNT": mock_vault_checking,
        }
        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
        )

        with self.assertRaises(Rejected) as r:
            odp.sweep_funds(mock_vault, DEFAULT_DATE)
        self.assertEqual(r.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(
            r.exception.message,
            "Requested 1 us_savings accounts but found 0.",
        )

    @patch("library.features.v3.common.utils.get_parameter")
    def test_handle_odp_sweep_transfers_funds_when_checking_account_is_negative(
        self,
        mock_get_parameter,
    ):

        balance_ts_checking = self.balances_for_account(
            default=Decimal("-100"),
        )
        balance_ts_savings = self.balances_for_account(
            default=Decimal("500"),
        )
        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_balance=balance_ts_checking,
            savings_balance=balance_ts_savings,
        )

        mock_get_parameter.return_value = "USD"

        odp.sweep_funds(mock_vault, DEFAULT_DATE)
        mock_vault_checking.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("100"),
            denomination="USD",
            client_transaction_id=(
                "INTERNAL_POSTING_SWEEP_WITHDRAWAL_FROM_SAVINGS_ACCOUNT_MOCK_HOOK"
            ),
            from_account_id="SAVINGS_ACCOUNT",
            from_account_address="DEFAULT",
            to_account_id="CHECKING_ACCOUNT",
            to_account_address="DEFAULT",
            asset="COMMERCIAL_BANK_MONEY",
            pics=[],
            override_all_restrictions=True,
            instruction_details={
                "description": "Sweep from savings account",
                "event": "SWEEP",
            },
        )

    @patch("library.features.v3.common.utils.get_parameter")
    def test_handle_odp_sweep_limited_by_savings(
        self,
        mock_get_parameter,
    ):

        balance_ts_checking = self.balances_for_account(
            default=Decimal("-100"),
        )
        balance_ts_savings = self.balances_for_account(
            default=Decimal("50"),
        )
        mock_vault, mock_vault_checking, _ = self.get_default_setup(
            checking_balance=balance_ts_checking,
            savings_balance=balance_ts_savings,
        )

        mock_get_parameter.return_value = "USD"

        odp.sweep_funds(mock_vault, DEFAULT_DATE)
        mock_vault_checking.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("50"),
            denomination="USD",
            client_transaction_id=(
                "INTERNAL_POSTING_SWEEP_WITHDRAWAL_FROM_SAVINGS_ACCOUNT_MOCK_HOOK"
            ),
            from_account_id="SAVINGS_ACCOUNT",
            from_account_address="DEFAULT",
            to_account_id="CHECKING_ACCOUNT",
            to_account_address="DEFAULT",
            asset="COMMERCIAL_BANK_MONEY",
            pics=[],
            override_all_restrictions=True,
            instruction_details={
                "description": "Sweep from savings account",
                "event": "SWEEP",
            },
        )

    @patch("library.features.v3.common.utils.get_parameter")
    def test_handle_odp_sweep_not_needed(
        self,
        mock_get_parameter,
    ):

        balance_ts_checking = self.balances_for_account(
            default=Decimal("100"),
        )
        balance_ts_savings = self.balances_for_account(
            default=Decimal("0"),
        )
        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_balance=balance_ts_checking,
            savings_balance=balance_ts_savings,
        )

        mock_get_parameter.return_value = "USD"

        odp.sweep_funds(mock_vault, DEFAULT_DATE)
        mock_vault_checking.make_internal_transfer_instructions.assert_not_called()


class ODPRemoveOverdraftFeesTest(ODPTestCommon):
    def test_per_transaction_overdraft_positive_balance_not_charged(self):
        balance_ts = self.balances_for_account(
            dt=DEFAULT_DATE - timedelta(seconds=1), default=Decimal(10)
        )
        pib = self.get_outbound_hard_settlement_mock("20")

        mock_vault = self.create_supervisee_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(10),
            pnl_account="1",
        )

        self.run_function(
            "remove_unnecessary_overdraft_fees",
            None,
            vault=mock_vault,
            postings=pib,
            offset_amount=0,
            denomination="USD",
            effective_date=DEFAULT_DATE,
            standard_overdraft_instructions=[],
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_per_transaction_overdraft_neg_bal_within_fee_free_limit_not_charged(self):
        balance_ts = self.balances_for_account(dt=DEFAULT_DATE, default=Decimal(-10))
        pib = self.get_outbound_hard_settlement_mock("20")

        mock_vault = self.create_supervisee_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(20),
            pnl_account="1",
        )

        self.run_function(
            "remove_unnecessary_overdraft_fees",
            None,
            vault=mock_vault,
            postings=pib,
            offset_amount=0,
            denomination="USD",
            effective_date=DEFAULT_DATE,
            standard_overdraft_instructions=[],
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_per_transaction_overdraft_neg_pending_auth_inside_fee_free_limit_not_charged(
        self,
    ):
        balance_ts = self.balances_for_account(
            dt=DEFAULT_DATE - timedelta(seconds=1),
            default=Decimal(-3),
            pending_outgoing=Decimal(-100),
        )
        pib = self.get_outbound_hard_settlement_mock("1")

        mock_vault = self.create_supervisee_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            pnl_account="1",
            standard_overdraft_fee_cap=Decimal(0),
        )

        self.run_function(
            "remove_unnecessary_overdraft_fees",
            None,
            vault=mock_vault,
            postings=pib,
            offset_amount=0,
            denomination="USD",
            effective_date=DEFAULT_DATE,
            standard_overdraft_instructions=[],
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_per_transaction_overdraft_savings_sweep_offset_within_fee_free_limit_not_charged(
        self,
    ):
        balance_ts = self.balances_for_account(
            dt=DEFAULT_DATE - timedelta(seconds=1), default=Decimal(-30)
        )
        pib = self.get_outbound_hard_settlement_mock("20")

        mock_vault = self.create_supervisee_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(20),
            pnl_account="1",
        )

        self.run_function(
            "remove_unnecessary_overdraft_fees",
            None,
            vault=mock_vault,
            postings=pib,
            offset_amount=30,
            denomination="USD",
            effective_date=DEFAULT_DATE,
            standard_overdraft_instructions=[],
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_per_transaction_overdraft_non_default_custom_instruction_no_fee_charged(
        self,
    ):
        balance_ts = self.balances_for_account(dt=DEFAULT_DATE, default=Decimal(-30))
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.custom_instruction(
                    amount="20",
                    credit=False,
                    denomination="USD",
                    account_address="OTHER_ADDRESS",
                )
            ],
        )

        mock_vault = self.create_supervisee_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            pnl_account="1",
        )

        self.run_function(
            "remove_unnecessary_overdraft_fees",
            None,
            vault=mock_vault,
            postings=pib,
            offset_amount=5,
            denomination="USD",
            effective_date=DEFAULT_DATE,
            standard_overdraft_instructions=[],
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_per_transaction_overdraft_credit_posting_no_fee_charged(self):
        balance_ts = self.balances_for_account(dt=DEFAULT_DATE, default=Decimal(-30))
        pib = self.get_inbound_hard_settlement_mock("20")

        mock_vault = self.create_supervisee_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            pnl_account="1",
        )

        self.run_function(
            "remove_unnecessary_overdraft_fees",
            None,
            vault=mock_vault,
            postings=pib,
            offset_amount=5,
            denomination="USD",
            effective_date=DEFAULT_DATE,
            standard_overdraft_instructions=[],
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()
