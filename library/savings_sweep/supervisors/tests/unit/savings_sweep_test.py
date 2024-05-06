# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Tuple
from unittest.mock import call
import json

from inception_sdk.test_framework.contracts.unit.supervisor.common import (
    SupervisorContractTest,
    balance_dimensions,
    create_posting_instruction_batch_directive,
    create_hook_directive,
)
from inception_sdk.vault.contracts.supervisor.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Phase,
    Balance,
    Tside,
    OptionalValue,
    Rejected,
    EventTypeSchedule,
    InvalidContractParameter,
    BalanceDefaultDict,
)

# Ensure added to BUILD
CONTRACT_FILE = "library/savings_sweep/supervisors/savings_sweep.py"
CHECKING_CONTRACT_FILE = "library/us_products/contracts/us_checking_account.py"
SAVINGS_CONTRACT_FILE = "library/us_products/contracts/us_savings_account.py"

DEFAULT_SAVINGS_ACCOUNT = "000002"
DEFAULT_CHECKING_ACCOUNT = "000001"
DEFAULT_DENOMINATION = "USD"
DEFAULT_DATE = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
HOOK_EXECUTION_ID = "MOCK_HOOK"
OVERDRAFT_FEE_INCOME_ACCOUNT = "OVERDRAFT_FEE_INCOME"


CHECKING_TIER_NAMES = json.dumps(["US_CHECKING_ACCOUNT_TIER_DEFAULT"])
CHECKING_ACTIVE_FLAGS = ["US_CHECKING_ACCOUNT_TIER_DEFAULT"]
CHECKING_MIN_COMBINED_BALANCE = json.dumps({"US_CHECKING_ACCOUNT_TIER_DEFAULT": "5000"})
SAVINGS_TIER_NAMES = json.dumps(["US_SAVINGS_ACCOUNT_TIER_LOWER"])
SAVINGS_ACTIVE_FLAGS = ["US_SAVINGS_ACCOUNT_TIER_LOWER"]
SAVINGS_MIN_COMBINED_BALANCE = json.dumps({"US_SAVINGS_ACCOUNT_TIER_LOWER": "5000"})

DEFAULT_DIMENSIONS = balance_dimensions(denomination=DEFAULT_DENOMINATION)
PENDING_OUTGOING_DIMENSIONS = balance_dimensions(
    denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_OUT
)
ACCRUED_PAYABLE_DIMENSIONS = balance_dimensions(
    denomination=DEFAULT_DENOMINATION, address="ACCRUED_INTEREST_PAYABLE"
)
ACCRUED_RECEIVABLE_DIMENSIONS = balance_dimensions(
    denomination=DEFAULT_DENOMINATION, address="ACCRUED_INTEREST_RECEIVABLE"
)
ACCRUED_OVERDRAFT_FEE_DIMENSIONS = balance_dimensions(
    denomination=DEFAULT_DENOMINATION, address="ACCRUED_OVERDRAFT_FEE_RECEIVABLE"
)
TRANSACTION_FEE_DIMENSIONS = balance_dimensions(
    denomination=DEFAULT_DENOMINATION, address="TRANSACTION_FEE"
)


class SavingsSweepSupervisorTest(SupervisorContractTest):
    contract_files = {
        "supervisor": CONTRACT_FILE,
        "checking": CHECKING_CONTRACT_FILE,
        "savings": SAVINGS_CONTRACT_FILE,
    }
    # This is needed to enable posting mocks, but has no impact today as
    # supervisors do not support the `.balances()` methods
    side = Tside.LIABILITY

    def balances_for_checking_account(
        self,
        dt=DEFAULT_DATE,
        default=Decimal(0),
        pending_out=Decimal(0),
        accrued_overdraft_fee=Decimal(0),
        accrued_deposit_payable=Decimal(0),
        accrued_deposit_receivable=Decimal(0),
    ) -> List[Tuple[datetime, BalanceDefaultDict]]:

        balance_defaultdict = BalanceDefaultDict(
            lambda: Balance(net=Decimal("0")),
            {
                DEFAULT_DIMENSIONS: Balance(net=default),
                PENDING_OUTGOING_DIMENSIONS: Balance(net=pending_out),
                ACCRUED_PAYABLE_DIMENSIONS: Balance(net=accrued_deposit_payable),
                ACCRUED_RECEIVABLE_DIMENSIONS: Balance(net=accrued_deposit_receivable),
                ACCRUED_OVERDRAFT_FEE_DIMENSIONS: Balance(net=accrued_overdraft_fee),
            },
        )

        return [(dt, balance_defaultdict)]

    def balances_for_savings_account(
        self,
        dt=DEFAULT_DATE,
        default=Decimal(0),
        pending_outgoing=Decimal(0),
        accrued_receivable=Decimal(0),
        accrued_payable=Decimal(0),
        transaction_fee=Decimal(0),
    ):

        balance_default_dict = BalanceDefaultDict(
            lambda: Balance(net=Decimal("0")),
            {
                DEFAULT_DIMENSIONS: Balance(net=default),
                PENDING_OUTGOING_DIMENSIONS: Balance(net=pending_outgoing),
                ACCRUED_PAYABLE_DIMENSIONS: Balance(net=accrued_payable),
                ACCRUED_RECEIVABLE_DIMENSIONS: Balance(net=accrued_receivable),
                TRANSACTION_FEE_DIMENSIONS: Balance(net=transaction_fee),
            },
        )

        return [(dt, balance_default_dict)]

    def get_outbound_hard_settlement_mock(self, amount, account_id="000001"):
        return self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
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

    def get_default_setup(self, checking_balance=Decimal("0"), savings_balance=Decimal("0")):
        balance_ts = self.balances_for_checking_account(dt=DEFAULT_DATE, default=checking_balance)
        balance_ts_savings = self.balances_for_savings_account(
            dt=DEFAULT_DATE, default=savings_balance
        )

        mock_vault_checking = self.create_supervisee_mock(
            alias="us_checking",
            account_id="000001",
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(0),
            denomination=DEFAULT_DENOMINATION,
            additional_denominations="[]",
            standard_overdraft_limit=Decimal(0),
            transaction_code_to_type_map="{}",
            transaction_types="",
            autosave_rounding_amount=Decimal("1.00"),
            autosave_savings_account=OptionalValue(is_set=False),
            savings_sweep_account_hierarchy=OptionalValue(is_set=False),
            savings_sweep_fee=Decimal("0"),
            savings_sweep_fee_cap=Decimal("-1"),
            savings_sweep_transfer_unit=Decimal("0"),
        )

        mock_vault_savings = self.create_supervisee_mock(
            alias="us_savings", account_id="000002", balance_ts=balance_ts_savings
        )

        supervisees = {"000001": mock_vault_checking, "000002": mock_vault_savings}

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)

        return (mock_vault, mock_vault_checking, mock_vault_savings)

    def test_get_available_balance_returns_available_balance_on_checking(self):
        expected = 50

        balances = {
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=100),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.PENDING_OUT,
            ): Balance(net=-50),
        }

        result = self.run_function(
            "_get_available_balance",
            None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_get_available_balance_when_0_default_balance_on_checking(self):
        expected = -50

        balances = {
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=0),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.PENDING_OUT,
            ): Balance(net=-50),
        }

        result = self.run_function(
            "_get_available_balance",
            None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_get_available_balance_when_0_pending_balance_on_checking(self):
        expected = 100

        balances = {
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=100),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.PENDING_OUT,
            ): Balance(net=0),
        }

        result = self.run_function(
            "_get_available_balance",
            None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_get_available_balance_when_0_balance_on_checking(self):
        expected = 0

        balances = {
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=0),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.PENDING_OUT,
            ): Balance(net=0),
        }

        result = self.run_function(
            "_get_available_balance",
            None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_get_supervisees_for_alias_returns_correct_list_with_same_creation_date(
        self,
    ):
        mock_vault_checking_1 = self.create_supervisee_mock(
            alias="us_checking", account_id="000001"
        )
        mock_vault_checking_2 = self.create_supervisee_mock(
            alias="us_checking", account_id="000002"
        )
        mock_vault_savings = self.create_supervisee_mock(alias="us_savings", account_id="000003")

        supervisees = {
            "000001": mock_vault_checking_1,
            "000002": mock_vault_checking_2,
            "000003": mock_vault_savings,
        }

        expected = [mock_vault_checking_1, mock_vault_checking_2]

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        result = self.run_function(
            "_get_supervisees_for_alias",
            mock_vault,
            vault=mock_vault,
            alias="us_checking",
        )

        self.assertEqual(result, expected)

    def test_get_supervisees_for_alias_returns_correctly_ordered_list_with_different_dates(
        self,
    ):
        mock_vault_checking_1 = self.create_supervisee_mock(
            alias="us_checking", account_id="000001", creation_date=datetime(2020, 1, 1)
        )
        mock_vault_checking_2 = self.create_supervisee_mock(
            alias="us_checking", account_id="000002", creation_date=datetime(2019, 1, 1)
        )
        mock_vault_savings_1 = self.create_supervisee_mock(
            alias="us_savings", account_id="000004", creation_date=datetime(2020, 1, 1)
        )
        mock_vault_savings_2 = self.create_supervisee_mock(
            alias="us_savings", account_id="000005", creation_date=datetime(2019, 1, 1)
        )
        mock_vault_savings_3 = self.create_supervisee_mock(
            alias="us_savings", account_id="000006", creation_date=datetime(2020, 5, 10)
        )
        supervisees = {
            "000001": mock_vault_checking_1,
            "000002": mock_vault_checking_2,
            "000004": mock_vault_savings_1,
            "000005": mock_vault_savings_2,
            "000006": mock_vault_savings_3,
        }

        expected = [mock_vault_savings_2, mock_vault_savings_1, mock_vault_savings_3]

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        result = self.run_function(
            "_get_supervisees_for_alias",
            mock_vault,
            vault=mock_vault,
            alias="us_savings",
        )

        self.assertEqual(result, expected)

    def test_get_supervisees_for_alias_returns_empty_list_when_no_matching_alias(self):
        mock_vault_checking_1 = self.create_supervisee_mock(alias="checking", account_id="000001")
        mock_vault_checking_2 = self.create_supervisee_mock(alias="checking", account_id="000002")
        mock_vault_savings = self.create_supervisee_mock(alias="savings", account_id="000003")
        supervisees = {
            "000001": mock_vault_checking_1,
            "000002": mock_vault_checking_2,
            "000003": mock_vault_savings,
        }

        expected = []

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        result = self.run_function(
            "_get_supervisees_for_alias",
            mock_vault,
            vault=mock_vault,
            alias="NOT_PRESENT",
        )

        self.assertEqual(result, expected)

    def test_get_supervisees_for_alias_returns_empty_list_with_no_supervisees(self):
        expected = []

        mock_vault = self.create_supervisor_mock(supervisees={})
        result = self.run_function(
            "_get_supervisees_for_alias",
            mock_vault,
            vault=mock_vault,
            alias="us_checking",
        )

        self.assertEqual(result, expected)

    def test_savings_sweep_debit_posting_updates_on_plan_savings_account_eq_savings_balance(self):
        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_balance=Decimal("-10"), savings_balance=Decimal("10")
        )

        pib = self.get_outbound_hard_settlement_mock("20")

        self.run_function("post_posting_code", mock_vault, pib, DEFAULT_DATE)

        mock_vault_checking.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal(10),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="INTERNAL_POSTING_SAVINGS_SWEEP_WITHDRAWAL"
                    "_FROM_000002_MOCK_HOOK",
                    from_account_id="000002",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id="000001",
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    pics=[],
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Savings Sweep from savings account",
                        "event": "SAVINGS_SWEEP",
                    },
                )
            ]
        )

        mock_vault_checking.instruct_posting_batch.assert_called_with(
            client_batch_id="POST_POSTING_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_SAVINGS_SWEEP_WITHDRAWAL_FROM_000002_MOCK_HOOK"
            ],
            effective_date=DEFAULT_DATE,
        )

    def test_savings_sweep_debit_posting_updates_on_plan_savings_account_lt_savings_balance(self):

        mock_vault, mock_vault_checking, _ = self.get_default_setup(
            checking_balance=Decimal("10"), savings_balance=Decimal("10")
        )

        pib = self.get_outbound_hard_settlement_mock("15")

        self.run_function("post_posting_code", mock_vault, pib, DEFAULT_DATE)

        mock_vault_checking.make_internal_transfer_instructions.assert_called_with(
            amount=Decimal("10"),
            denomination=DEFAULT_DENOMINATION,
            client_transaction_id="INTERNAL_POSTING_SAVINGS_SWEEP_WITHDRAWAL"
            "_FROM_000002_MOCK_HOOK",
            from_account_id=DEFAULT_SAVINGS_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=DEFAULT_CHECKING_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            pics=[],
            override_all_restrictions=True,
            instruction_details={
                "description": "Savings Sweep from savings account",
                "event": "SAVINGS_SWEEP",
            },
        )

        mock_vault_checking.instruct_posting_batch.assert_called_with(
            client_batch_id="POST_POSTING_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_SAVINGS_SWEEP_WITHDRAWAL_FROM_000002_MOCK_HOOK"
            ],
            effective_date=DEFAULT_DATE,
        )

    def test_savings_sweep_debit_posting_updates_linked_savings_account_gt_savings_balance_with_od(
        self,
    ):
        mock_vault, mock_vault_checking, _ = self.get_default_setup(
            checking_balance=Decimal("-15"), savings_balance=Decimal("10")
        )
        pib = self.get_outbound_hard_settlement_mock("25")

        self.run_function("post_posting_code", mock_vault, pib, DEFAULT_DATE)

        mock_vault_checking.make_internal_transfer_instructions.assert_called_with(
            amount=Decimal(10),
            denomination=DEFAULT_DENOMINATION,
            client_transaction_id="INTERNAL_POSTING_SAVINGS_SWEEP_WITHDRAWAL"
            "_FROM_000002_MOCK_HOOK",
            from_account_id=DEFAULT_SAVINGS_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=DEFAULT_CHECKING_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            pics=[],
            override_all_restrictions=True,
            instruction_details={
                "description": "Savings Sweep from savings account",
                "event": "SAVINGS_SWEEP",
            },
        )

        mock_vault_checking.instruct_posting_batch.assert_called_with(
            client_batch_id="POST_POSTING_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_SAVINGS_SWEEP_WITHDRAWAL_FROM_000002_MOCK_HOOK"
            ],
            effective_date=DEFAULT_DATE,
        )

    def test_savings_sweep_transfer_unit(self):
        mock_vault_checking = self.create_supervisee_mock(
            alias="us_checking",
            account_id="000001",
            balance_ts=self.balances_for_checking_account(
                dt=DEFAULT_DATE - timedelta(seconds=1), default=Decimal("100")
            ),
            standard_overdraft_per_transaction_fee=Decimal(0),
            denomination=DEFAULT_DENOMINATION,
            additional_denominations="[]",
            standard_overdraft_limit=Decimal("1000"),
            transaction_code_to_type_map="{}",
            transaction_types="",
            autosave_rounding_amount=Decimal("1.00"),
            autosave_savings_account=OptionalValue(is_set=False),
            savings_sweep_account_hierarchy=OptionalValue(
                json.dumps(["000003", "000002", "000004"])
            ),
            savings_sweep_fee=Decimal("0"),
            savings_sweep_fee_cap=Decimal("-1"),
            savings_sweep_transfer_unit=Decimal("50"),
        )
        mock_vault_savings_0 = self.create_supervisee_mock(
            alias="us_savings",
            account_id="000002",
            balance_ts=self.balances_for_savings_account(
                dt=DEFAULT_DATE - timedelta(seconds=1), default=Decimal("110")
            ),
        )
        mock_vault_savings_1 = self.create_supervisee_mock(
            alias="us_savings",
            account_id="000003",
            balance_ts=self.balances_for_savings_account(
                dt=DEFAULT_DATE - timedelta(seconds=1), default=Decimal("205.90")
            ),
        )
        mock_vault_savings_2 = self.create_supervisee_mock(
            alias="us_savings",
            account_id="000004",
            balance_ts=self.balances_for_savings_account(
                dt=DEFAULT_DATE - timedelta(seconds=1), default=Decimal("500")
            ),
        )

        supervisees = {
            "000001": mock_vault_checking,
            "000002": mock_vault_savings_0,
            "000003": mock_vault_savings_1,
            "000004": mock_vault_savings_2,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)

        pib = self.get_outbound_hard_settlement_mock("550")

        self.run_function("post_posting_code", mock_vault, pib, DEFAULT_DATE)

        mock_vault_checking.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("200.00"),
                    asset="COMMERCIAL_BANK_MONEY",
                    client_transaction_id="INTERNAL_POSTING_SAVINGS_SWEEP_WITHDRAWAL"
                    "_FROM_000003_MOCK_HOOK",
                    denomination="USD",
                    from_account_address="DEFAULT",
                    from_account_id="000003",
                    instruction_details={
                        "description": "Savings Sweep from savings account",
                        "event": "SAVINGS_SWEEP",
                    },
                    override_all_restrictions=True,
                    pics=[],
                    to_account_address="DEFAULT",
                    to_account_id="000001",
                ),
                call(
                    amount=Decimal("100"),
                    asset="COMMERCIAL_BANK_MONEY",
                    client_transaction_id="INTERNAL_POSTING_SAVINGS_SWEEP_WITHDRAWAL"
                    "_FROM_000002_MOCK_HOOK",
                    denomination="USD",
                    from_account_address="DEFAULT",
                    from_account_id="000002",
                    instruction_details={
                        "description": "Savings Sweep from savings account",
                        "event": "SAVINGS_SWEEP",
                    },
                    override_all_restrictions=True,
                    pics=[],
                    to_account_address="DEFAULT",
                    to_account_id="000001",
                ),
                call(
                    amount=Decimal("150.00"),
                    asset="COMMERCIAL_BANK_MONEY",
                    client_transaction_id="INTERNAL_POSTING_SAVINGS_SWEEP_WITHDRAWAL"
                    "_FROM_000004_MOCK_HOOK",
                    denomination="USD",
                    from_account_address="DEFAULT",
                    from_account_id="000004",
                    instruction_details={
                        "description": "Savings Sweep from savings account",
                        "event": "SAVINGS_SWEEP",
                    },
                    override_all_restrictions=True,
                    pics=[],
                    to_account_address="DEFAULT",
                    to_account_id="000001",
                ),
            ]
        )

    def test_postings_with_multiple_account_ids_throws_exception(self):
        mock_vault_checking_1 = self.create_supervisee_mock(
            alias="us_checking", account_id="000001"
        )
        mock_vault_checking_2 = self.create_supervisee_mock(
            alias="us_checking", account_id="000002"
        )
        mock_vault_savings = self.create_supervisee_mock(alias="us_savings", account_id="000003")

        supervisees = {
            "000001": mock_vault_checking_1,
            "000002": mock_vault_checking_2,
            "000003": mock_vault_savings,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)

        debit_posting_1 = self.outbound_hard_settlement(
            account_id="000001",
            amount="20",
            denomination="USD",
            value_timestamp=DEFAULT_DATE,
        )
        debit_posting_2 = self.outbound_hard_settlement(
            account_id="000002",
            amount="30",
            denomination="USD",
            value_timestamp=DEFAULT_DATE,
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[debit_posting_1, debit_posting_2]
        )

        with self.assertRaises(Rejected) as ex:
            self.run_function("post_posting_code", mock_vault, pib, DEFAULT_DATE)

        self.assertIn(
            "Multiple checking accounts in post posting not supported.",
            str(ex.exception),
        )

    def test_per_transaction_overdraft_positive_balance_not_charged(self):
        balance_ts = self.balances_for_checking_account(
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
            "_charge_overdraft_per_transaction_fee",
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
        balance_ts = self.balances_for_checking_account(dt=DEFAULT_DATE, default=Decimal(-10))
        pib = self.get_outbound_hard_settlement_mock("20")

        mock_vault = self.create_supervisee_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(20),
            pnl_account="1",
        )

        self.run_function(
            "_charge_overdraft_per_transaction_fee",
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

    def test_per_transaction_overdraft_neg_bal_outside_fee_free_limit_charged(self):
        balance_ts = self.balances_for_checking_account(
            dt=DEFAULT_DATE - timedelta(seconds=1), default=Decimal(-10)
        )
        pib = self.get_outbound_hard_settlement_mock("20", account_id=DEFAULT_CHECKING_ACCOUNT)

        overdraft_pib = create_posting_instruction_batch_directive(
            Tside.LIABILITY,
            amount="5",
            denomination="USD",
            from_account_id=DEFAULT_CHECKING_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            client_transaction_id="INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_"
            "HOOK_USD_MOCK_POSTING_0",
            instruction_details={
                "description": "Applying stndard overdraft transaction fee for" " MOCK_POSTING",
                "event": "STANDARD_OVERDRAFT",
            },
        )

        hook_directive = create_hook_directive(posting_instruction_batch_directives=[overdraft_pib])

        mock_vault_checking = self.create_supervisee_mock(
            account_id=DEFAULT_CHECKING_ACCOUNT,
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            standard_overdraft_fee_cap=Decimal(0),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
            offset_amount=0,
            denomination="USD",
            hook_directives=hook_directive,
            autosave_savings_account=OptionalValue(is_set=False),
        )

        supervisees = {DEFAULT_CHECKING_ACCOUNT: mock_vault_checking}

        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            pib,
            DEFAULT_DATE,
        )

        expected_postings = []
        for posting in overdraft_pib.posting_instruction_batch:
            expected_postings.append(posting)

        mock_vault_checking.instruct_posting_batch.assert_called_with(
            client_batch_id="POST_POSTING_MOCK_HOOK",
            posting_instructions=expected_postings,
            effective_date=DEFAULT_DATE,
        )

    def test_per_transaction_overdraft_neg_pending_auth_inside_fee_free_limit_not_charged(
        self,
    ):
        balance_ts = self.balances_for_checking_account(
            dt=DEFAULT_DATE - timedelta(seconds=1),
            default=Decimal(-3),
            pending_out=Decimal(-100),
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
            "_charge_overdraft_per_transaction_fee",
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
        balance_ts = self.balances_for_checking_account(
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
            "_charge_overdraft_per_transaction_fee",
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

    def test_per_transaction_overdraft_savings_sweep_offset_outside_fee_free_limit_fee_charged(
        self,
    ):
        balance_ts = self.balances_for_checking_account(
            dt=DEFAULT_DATE - timedelta(seconds=1), default=Decimal(-30)
        )
        pib = self.get_outbound_hard_settlement_mock("20", account_id=DEFAULT_CHECKING_ACCOUNT)

        overdraft_pib = create_posting_instruction_batch_directive(
            Tside.LIABILITY,
            amount="5",
            denomination="USD",
            from_account_id=DEFAULT_CHECKING_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            client_transaction_id="INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_"
            "HOOK_USD_MOCK_POSTING_0",
            instruction_details={
                "description": "Applying standard overdraft transaction fee for" " MOCK_POSTING",
                "event": "STANDARD_OVERDRAFT",
            },
        )

        hook_directive = create_hook_directive(posting_instruction_batch_directives=[overdraft_pib])

        mock_vault_checking = self.create_supervisee_mock(
            account_id=DEFAULT_CHECKING_ACCOUNT,
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            standard_overdraft_fee_cap=Decimal(0),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
            offset_amount=5,
            denomination="USD",
            hook_directives=hook_directive,
            autosave_savings_account=OptionalValue(is_set=False),
        )

        supervisees = {DEFAULT_CHECKING_ACCOUNT: mock_vault_checking}

        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            pib,
            DEFAULT_DATE,
        )

        expected_postings = []
        for posting in overdraft_pib.posting_instruction_batch:
            expected_postings.append(posting)

        mock_vault_checking.instruct_posting_batch.assert_called_with(
            client_batch_id="POST_POSTING_MOCK_HOOK",
            posting_instructions=expected_postings,
            effective_date=DEFAULT_DATE,
        )

    def test_per_transaction_overdraft_non_default_custom_instruction_no_fee_charged(
        self,
    ):
        balance_ts = self.balances_for_checking_account(dt=DEFAULT_DATE, default=Decimal(-30))
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
            "_charge_overdraft_per_transaction_fee",
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

    def test_per_transaction_overdraft_default_custom_instruction_fee_charged(self):
        balance_ts = self.balances_for_checking_account(
            dt=DEFAULT_DATE - timedelta(seconds=1), default=Decimal(-30)
        )
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.custom_instruction(
                    amount="20",
                    credit=False,
                    denomination="USD",
                    account_address=DEFAULT_ADDRESS,
                    phase=Phase.COMMITTED,
                    asset=DEFAULT_ASSET,
                    account_id=DEFAULT_CHECKING_ACCOUNT,
                )
            ],
        )

        overdraft_pib = create_posting_instruction_batch_directive(
            Tside.LIABILITY,
            amount="5",
            denomination="USD",
            from_account_id=DEFAULT_CHECKING_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            client_transaction_id="INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_"
            "HOOK_USD_MOCK_POSTING_0",
            instruction_details={
                "description": "Applying standard overdraft transaction fee for" " MOCK_POSTING",
                "event": "STANDARD_OVERDRAFT",
            },
        )

        hook_directive = create_hook_directive(posting_instruction_batch_directives=[overdraft_pib])

        mock_vault_checking = self.create_supervisee_mock(
            account_id=DEFAULT_CHECKING_ACCOUNT,
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            standard_overdraft_fee_cap=Decimal(0),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
            offset_amount=5,
            denomination="USD",
            hook_directives=hook_directive,
            autosave_savings_account=OptionalValue(is_set=False),
        )

        supervisees = {DEFAULT_CHECKING_ACCOUNT: mock_vault_checking}

        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            pib,
            DEFAULT_DATE,
        )
        expected_postings = []
        for posting in overdraft_pib.posting_instruction_batch:
            expected_postings.append(posting)

        mock_vault_checking.instruct_posting_batch.assert_called_with(
            client_batch_id="POST_POSTING_MOCK_HOOK",
            posting_instructions=expected_postings,
            effective_date=DEFAULT_DATE,
        )

    def test_per_transaction_overdraft_credit_posting_no_fee_charged(self):
        balance_ts = self.balances_for_checking_account(dt=DEFAULT_DATE, default=Decimal(-30))
        pib = self.get_inbound_hard_settlement_mock("20")

        mock_vault = self.create_supervisee_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            pnl_account="1",
        )

        self.run_function(
            "_charge_overdraft_per_transaction_fee",
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

    def test_per_transaction_overdraft_two_postings_charges_twice(self):
        balance_ts = self.balances_for_checking_account(
            dt=DEFAULT_DATE - timedelta(seconds=1), default=Decimal(-40)
        )
        debit_posting_1 = self.outbound_hard_settlement(
            amount="20",
            denomination="USD",
            value_timestamp=DEFAULT_DATE,
            account_id=DEFAULT_CHECKING_ACCOUNT,
        )
        debit_posting_2 = self.outbound_hard_settlement(
            amount="30",
            denomination="USD",
            value_timestamp=DEFAULT_DATE,
            account_id=DEFAULT_CHECKING_ACCOUNT,
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[debit_posting_1, debit_posting_2]
        )

        overdraft_pib1 = create_posting_instruction_batch_directive(
            Tside.LIABILITY,
            amount="5",
            denomination="USD",
            from_account_id=DEFAULT_CHECKING_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            client_transaction_id="INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_"
            "HOOK_USD_MOCK_POSTING_0",
            instruction_details={
                "description": "Applying standard overdraft transaction fee for" " MOCK_POSTING",
                "event": "STANDARD_OVERDRAFT",
            },
        )

        overdraft_pib2 = create_posting_instruction_batch_directive(
            Tside.LIABILITY,
            amount="5",
            denomination="USD",
            from_account_id=DEFAULT_CHECKING_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            client_transaction_id="INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_"
            "HOOK_USD_MOCK_POSTING_1",
            instruction_details={
                "description": "Applying standard overdraft transaction fee for" " MOCK_POSTING",
                "event": "STANDARD_OVERDRAFT",
            },
        )

        hook_directive = create_hook_directive(
            posting_instruction_batch_directives=[overdraft_pib1, overdraft_pib2]
        )

        mock_vault_checking = self.create_supervisee_mock(
            account_id=DEFAULT_CHECKING_ACCOUNT,
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            standard_overdraft_fee_cap=Decimal(0),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
            offset_amount=0,
            denomination="USD",
            alias="us_checking",
            hook_directives=hook_directive,
            autosave_savings_account=OptionalValue(is_set=False),
        )

        supervisees = {DEFAULT_CHECKING_ACCOUNT: mock_vault_checking}

        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            pib,
            DEFAULT_DATE,
        )

        expected_postings = []
        for posting_directive in hook_directive.posting_instruction_batch_directives:
            pib = posting_directive.posting_instruction_batch
            for posting in pib:
                expected_postings.append(posting)

        mock_vault_checking.instruct_posting_batch.assert_called_with(
            client_batch_id="POST_POSTING_MOCK_HOOK",
            posting_instructions=expected_postings,
            effective_date=DEFAULT_DATE,
        )

    def test_per_transaction_fee_capped(self):
        balance_ts = self.balances_for_checking_account(
            dt=DEFAULT_DATE - timedelta(seconds=1), default=Decimal(-40)
        )
        debit_posting_1 = self.outbound_hard_settlement(
            amount="20",
            denomination="USD",
            value_timestamp=DEFAULT_DATE,
            account_id=DEFAULT_CHECKING_ACCOUNT,
        )
        debit_posting_2 = self.outbound_hard_settlement(
            amount="30",
            denomination="USD",
            value_timestamp=DEFAULT_DATE,
            account_id=DEFAULT_CHECKING_ACCOUNT,
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[debit_posting_1, debit_posting_2]
        )

        overdraft_pib = create_posting_instruction_batch_directive(
            Tside.LIABILITY,
            amount="5",
            denomination="USD",
            from_account_id=DEFAULT_CHECKING_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            client_transaction_id="INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_"
            "HOOK_USD_MOCK_POSTING_0",
            instruction_details={
                "description": "Applying standard overdraft transaction fee for" " MOCK_POSTING",
                "event": "STANDARD_OVERDRAFT",
            },
        )

        hook_directive = create_hook_directive(posting_instruction_batch_directives=[overdraft_pib])

        mock_vault_checking = self.create_supervisee_mock(
            account_id=DEFAULT_CHECKING_ACCOUNT,
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            standard_overdraft_fee_cap=Decimal(7),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
            denomination="USD",
            offset_amount=0,
            alias="us_checking",
            hook_directives=hook_directive,
            autosave_savings_account=OptionalValue(is_set=False),
        )

        supervisees = {DEFAULT_CHECKING_ACCOUNT: mock_vault_checking}

        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            pib,
            DEFAULT_DATE,
        )

        expected_postings = []
        for posting in overdraft_pib.posting_instruction_batch:
            expected_postings.append(posting)

        mock_vault_checking.instruct_posting_batch.assert_called_with(
            client_batch_id="POST_POSTING_MOCK_HOOK",
            posting_instructions=expected_postings,
            effective_date=DEFAULT_DATE,
        )

    def test_is_settled_against_default_address(self):
        pi_types = (
            (self.outbound_hard_settlement, True, {}),
            (self.settle_outbound_auth, True, {"unsettled_amount": "30"}),
            (self.inbound_transfer, True, {}),
            (self.outbound_auth, False, {}),
            (self.inbound_auth_adjust, False, {}),
            (self.release_outbound_auth, False, {"unsettled_amount": "30"}),
        )
        for pi_type in pi_types:
            pi = pi_type[0](amount="30", denomination="USD", **pi_type[2])

            mock_vault = self.create_supervisor_mock(supervisees={})

            result = self.run_function("_is_settled_against_default_address", mock_vault, pi)

            self.assertEqual(result, pi_type[1], pi_type[0])

    def test_is_settled_against_default_address_custom_instructions(self):
        pi = self.custom_instruction(
            amount="20",
            credit=False,
            denomination="USD",
            account_address=DEFAULT_ADDRESS,
            phase=Phase.COMMITTED,
            asset=DEFAULT_ASSET,
        )

        mock_vault = self.create_supervisor_mock(supervisees={})

        result = self.run_function("_is_settled_against_default_address", mock_vault, pi)
        self.assertTrue(result)

    def test_is_settled_against_non_default_address_custom_instructions(self):
        pi = self.custom_instruction(
            amount="20",
            credit=False,
            denomination="USD",
            account_address="NON_DEFAULT",
        )

        mock_vault = self.create_supervisor_mock(supervisees={})

        result = self.run_function("_is_settled_against_default_address", mock_vault, pi)
        self.assertFalse(result)

    def test_get_start_of_daily_window(self):
        test_cases = (
            {
                "effective_date": datetime(2021, 1, 20, 17, 12, 21),
                "creation_date": datetime(2021, 1, 19, 11, 11, 11),
                "expected_result": datetime(2021, 1, 20, 0, 0, 0),
                "description": "account created in before current day midnight",
            },
            {
                "effective_date": datetime(2021, 1, 20, 17, 12, 21),
                "creation_date": datetime(2021, 1, 20, 12, 11, 11),
                "expected_result": datetime(2021, 1, 20, 12, 11, 11),
                "description": "account created in after current day midnight",
            },
        )

        for test_case in test_cases:

            mock_vault_checking = self.create_supervisee_mock(
                alias="us_checking",
                account_id="000001",
                creation_date=test_case["creation_date"],
            )

            result = self.run_function(
                "_get_start_of_daily_window",
                None,
                mock_vault_checking,
                test_case["effective_date"],
            )

        self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_count_savings_sweep_used(self):
        debit_without_instruction_event = self.custom_instruction(
            account_id="000001",
            amount="10",
            credit=False,
            denomination="USD",
            value_timestamp=DEFAULT_DATE + timedelta(hours=1),
        )

        valid_debit_1 = self.custom_instruction(
            account_id="000001",
            amount="20",
            credit=False,
            denomination="USD",
            value_timestamp=DEFAULT_DATE + timedelta(hours=2),
            instruction_details={"event": "SAVINGS_SWEEP_FEE"},
        )

        debit_before_start_period = self.custom_instruction(
            account_id="000001",
            amount="30",
            credit=False,
            denomination="USD",
            value_timestamp=DEFAULT_DATE + timedelta(days=-1),
            instruction_details={"event": "SAVINGS_SWEEP_FEE"},
        )

        valid_debit_2 = self.custom_instruction(
            account_id="000001",
            amount="40",
            credit=False,
            denomination="USD",
            value_timestamp=DEFAULT_DATE + timedelta(hours=3),
            instruction_details={"event": "SAVINGS_SWEEP_FEE"},
        )

        credit_posting = self.inbound_hard_settlement(
            account_id="000001",
            amount="50",
            denomination="USD",
            value_timestamp=DEFAULT_DATE + timedelta(hours=4),
            instruction_details={"event": "SAVINGS_SWEEP_FEE"},
        )

        mock_vault_checking = self.create_supervisee_mock(
            alias="us_checking",
            account_id="000001",
            creation_date=DEFAULT_DATE + timedelta(days=-1),
            postings=[
                debit_without_instruction_event,
                valid_debit_1,
                debit_before_start_period,
                valid_debit_2,
                credit_posting,
            ],
        )

        result = self.run_function(
            "_count_savings_sweep_used",
            None,
            mock_vault_checking,
            DEFAULT_DATE + timedelta(hours=13),
        )

        self.assertEqual(result, 2)

    def test_get_applicable_savings_sweep_fee(self):
        test_cases = (
            {
                "savings_sweep_fee": "10",
                "savings_sweep_fee_cap": "2",
                "expected_result": Decimal("10"),
                "description": "should charge savings sweep fee",
            },
            {
                "savings_sweep_fee": "10",
                "savings_sweep_fee_cap": "1",
                "expected_result": Decimal("0"),
                "description": "No savings sweep fee if cap reached",
            },
            {
                "savings_sweep_fee": "0",
                "savings_sweep_fee_cap": "10",
                "expected_result": Decimal("0"),
                "description": "0 savings sweep fee",
            },
            {
                "savings_sweep_fee": "-100",
                "savings_sweep_fee_cap": "10",
                "expected_result": Decimal("0"),
                "description": "negative savings sweep fee",
            },
            {
                "savings_sweep_fee": "10",
                "savings_sweep_fee_cap": "0",
                "expected_result": Decimal("0"),
                "description": "savings sweep fee cap is 0",
            },
            {
                "savings_sweep_fee": "10",
                "savings_sweep_fee_cap": "-1",
                "expected_result": Decimal("10"),
                "description": "uncapped savings sweep fee",
            },
        )
        previous_charge = self.custom_instruction(
            account_id="000001",
            amount="50",
            credit=False,
            denomination="USD",
            value_timestamp=DEFAULT_DATE + timedelta(hours=1),
            instruction_details={"event": "SAVINGS_SWEEP_FEE"},
        )

        for test_case in test_cases:
            mock_vault_checking = self.create_supervisee_mock(
                alias="us_checking",
                account_id="000001",
                creation_date=DEFAULT_DATE + timedelta(days=-5),
                postings=[previous_charge],
                savings_sweep_fee=Decimal(test_case["savings_sweep_fee"]),
                savings_sweep_fee_cap=Decimal(test_case["savings_sweep_fee_cap"]),
            )

            result = self.run_function(
                "_get_applicable_savings_sweep_fee",
                None,
                mock_vault_checking,
                DEFAULT_DATE + timedelta(hours=10),
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_create_schedule_dict_from_datetime(self):
        schedule_datetime = datetime(year=2000, month=1, day=2, hour=3, minute=4, second=5)
        expected_schedule_dict = {
            "year": "2000",
            "month": "1",
            "day": "2",
            "hour": "3",
            "minute": "4",
            "second": "5",
        }

        mock_vault = self.create_supervisor_mock(supervisees={})
        result = self.run_function(
            "_create_schedule_dict_from_datetime", mock_vault, schedule_datetime
        )

        self.assertEqual(result, expected_schedule_dict)

    def test_create_event_type_schedule_from_datetime(self):
        schedule_datetime = datetime(year=2000, month=1, day=2, hour=3, minute=4, second=5)
        expected_event_type_schedule = EventTypeSchedule(
            day="2", hour="3", minute="4", second="5", month="1", year="2000"
        )

        mock_vault = self.create_supervisor_mock(supervisees={})
        result = self.run_function(
            "_create_event_type_schedule_from_datetime", mock_vault, schedule_datetime
        )

        self.assertEqual(result.__dict__, expected_event_type_schedule.__dict__)

    def test_is_maintenance_fee_posting_for_checking_post(self):
        post = self.custom_instruction(
            amount=10,
            credit=False,
            denomination=DEFAULT_DENOMINATION,
            account_address=DEFAULT_ADDRESS,
            account_id="000001",
            client_transaction_id="INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_XX_USD",
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )
        account_type = "us_checking"

        mock_vault = self.create_supervisor_mock(supervisees={})
        result = self.run_function("_is_maintenance_fee_posting", mock_vault, post, account_type)

        self.assertTrue(result)

    def test_is_maintenance_fee_posting_for_savings_post(self):
        post = self.custom_instruction(
            amount=10,
            credit=False,
            denomination=DEFAULT_DENOMINATION,
            account_address=DEFAULT_ADDRESS,
            account_id="000001",
            client_transaction_id="INTERNAL_POSTING_APPLY_MAINTENANCE_FEE_MONTHLY_XX_USD",
            instruction_details={
                "description": "Maintenance fee monthly",
                "event": "APPLY_MAINTENANCE_FEE_MONTHLY",
            },
        )
        account_type = "us_savings"

        mock_vault = self.create_supervisor_mock(supervisees={})
        result = self.run_function("_is_maintenance_fee_posting", mock_vault, post, account_type)

        self.assertTrue(result)

    def test_is_maintenance_fee_posting_fails(self):
        post = self.custom_instruction(
            amount=10,
            credit=False,
            denomination=DEFAULT_DENOMINATION,
            account_address=DEFAULT_ADDRESS,
            account_id="000001",
            client_transaction_id="SOMETHING_ELSE_MAINTENANCE_FEE_MONTHLY_XX_USD",
            instruction_details={
                "description": "Maintenance fee monthly",
                "event": "APPLY_MAINTENANCE_FEE_MONTHLY",
            },
        )
        account_type = "us_savings"

        mock_vault = self.create_supervisor_mock(supervisees={})
        result = self.run_function("_is_maintenance_fee_posting", mock_vault, post, account_type)

        self.assertEqual(False, result)

    def test_monthly_mean_balance_returns_correct_mean_balance_single(self):
        effective_time = datetime(2020, 5, 1)

        balance_ts = self.balances_for_checking_account(dt=datetime(2020, 4, 1), default=Decimal(0))

        balance_ts.extend(
            self.balances_for_checking_account(dt=datetime(2020, 4, 6), default=Decimal(500))
        )

        balance_ts.extend(
            self.balances_for_checking_account(dt=datetime(2020, 4, 26), default=Decimal(1000))
        )

        mock_vault = self.create_supervisee_mock(
            alias="us_checking",
            account_id="000001",
            creation_date=datetime(2020, 1, 1),
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
        )

        monthly_mean_balance = self.run_function(
            "_monthly_mean_balance",
            None,
            denomination=DEFAULT_DENOMINATION,
            effective_date=effective_time,
            all_accounts=(e for e in [mock_vault]),
        )

        expected_monthly_mean_balance = Decimal(500)

        self.assertEqual(monthly_mean_balance, expected_monthly_mean_balance)

    def test_monthly_mean_balance_returns_correct_mean_balance_single_fraction(self):
        effective_time = datetime(2020, 5, 1)

        balance_ts = self.balances_for_checking_account(dt=datetime(2020, 4, 1), default=Decimal(0))
        balance_ts.extend(
            self.balances_for_checking_account(dt=datetime(2020, 4, 2), default=Decimal(500))
        )
        balance_ts.extend(
            self.balances_for_checking_account(dt=datetime(2020, 4, 26), default=Decimal(1000))
        )

        mock_vault = self.create_supervisee_mock(
            alias="us_checking",
            account_id="000001",
            creation_date=datetime(2020, 1, 1),
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
        )

        monthly_mean_balance = self.run_function(
            "_monthly_mean_balance",
            None,
            denomination=DEFAULT_DENOMINATION,
            effective_date=effective_time,
            all_accounts=(e for e in [mock_vault]),
        )

        expected_monthly_mean_balance = Decimal("566.6666666666666666666666667")

        self.assertEqual(monthly_mean_balance, expected_monthly_mean_balance)

    def test_monthly_mean_balance_returns_correct_mean_balance_multiple(self):
        effective_time = datetime(2020, 5, 1)

        balance_ts = self.balances_for_checking_account(dt=datetime(2020, 4, 1), default=Decimal(0))
        balance_ts_savings = self.balances_for_savings_account(
            dt=datetime(2020, 4, 1), default=Decimal(2000)
        )

        balance_ts.extend(
            self.balances_for_checking_account(dt=datetime(2020, 4, 6), default=Decimal(500))
        )
        balance_ts_savings.extend(
            self.balances_for_savings_account(dt=datetime(2020, 4, 6), default=Decimal(1000))
        )

        balance_ts.extend(
            self.balances_for_checking_account(dt=datetime(2020, 4, 26), default=Decimal(1000))
        )
        balance_ts_savings.extend(
            self.balances_for_savings_account(dt=datetime(2020, 4, 26), default=Decimal(0))
        )

        mock_vault_checking = self.create_supervisee_mock(
            alias="us_checking",
            account_id="000001",
            creation_date=datetime(2020, 1, 1),
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
        )

        mock_vault_savings = self.create_supervisee_mock(
            alias="us_savings",
            account_id="000002",
            creation_date=datetime(2020, 1, 1),
            balance_ts=balance_ts_savings,
            denomination=DEFAULT_DENOMINATION,
        )

        monthly_mean_balance = self.run_function(
            "_monthly_mean_balance",
            None,
            denomination=DEFAULT_DENOMINATION,
            effective_date=effective_time,
            all_accounts=(e for e in [mock_vault_checking, mock_vault_savings]),
        )

        # checking 500 + savings 1000
        expected_monthly_mean_balance = Decimal(1500)

        self.assertEqual(monthly_mean_balance, expected_monthly_mean_balance)

    def test_monthly_mean_balance_multiple_checking_and_savings(self):
        effective_time = datetime(2020, 5, 1)

        # combined total for 5 days = 26,000
        balance_ts_checking1 = self.balances_for_checking_account(
            dt=datetime(2020, 4, 1), default=Decimal(0)
        )
        balance_ts_checking2 = self.balances_for_checking_account(
            dt=datetime(2020, 4, 1), default=Decimal(1000)
        )
        balance_ts_savings1 = self.balances_for_savings_account(
            dt=datetime(2020, 4, 1), default=Decimal(20000)
        )
        balance_ts_savings2 = self.balances_for_savings_account(
            dt=datetime(2020, 4, 1), default=Decimal(5000)
        )

        # combined total for 20 days = 12,000
        balance_ts_checking1.extend(
            self.balances_for_checking_account(dt=datetime(2020, 4, 6), default=Decimal(-1000))
        )
        balance_ts_checking2.extend(
            self.balances_for_checking_account(dt=datetime(2020, 4, 6), default=Decimal(0))
        )
        balance_ts_savings1.extend(
            self.balances_for_savings_account(dt=datetime(2020, 4, 6), default=Decimal(12000))
        )
        balance_ts_savings2.extend(
            self.balances_for_savings_account(dt=datetime(2020, 4, 6), default=Decimal(1000))
        )

        # combined total for 5 days = 11,500
        balance_ts_checking1.extend(
            self.balances_for_checking_account(dt=datetime(2020, 4, 26), default=Decimal(-500))
        )
        balance_ts_checking2.extend(
            self.balances_for_checking_account(dt=datetime(2020, 4, 26), default=Decimal(0))
        )
        balance_ts_savings1.extend(
            self.balances_for_savings_account(dt=datetime(2020, 4, 26), default=Decimal(11000))
        )
        balance_ts_savings2.extend(
            self.balances_for_savings_account(dt=datetime(2020, 4, 26), default=Decimal(1000))
        )

        mock_vault_checking1 = self.create_supervisee_mock(
            alias="us_checking",
            account_id="000001",
            creation_date=datetime(2020, 1, 1),
            balance_ts=balance_ts_checking1,
            denomination=DEFAULT_DENOMINATION,
        )

        mock_vault_checking2 = self.create_supervisee_mock(
            alias="us_checking",
            account_id="000002",
            creation_date=datetime(2020, 1, 1),
            balance_ts=balance_ts_checking2,
            denomination=DEFAULT_DENOMINATION,
        )

        mock_vault_savings1 = self.create_supervisee_mock(
            alias="us_savings",
            account_id="000003",
            creation_date=datetime(2020, 1, 1),
            balance_ts=balance_ts_savings1,
            denomination=DEFAULT_DENOMINATION,
        )

        mock_vault_savings2 = self.create_supervisee_mock(
            alias="us_savings",
            account_id="000004",
            creation_date=datetime(2020, 1, 1),
            balance_ts=balance_ts_savings2,
            denomination=DEFAULT_DENOMINATION,
        )

        monthly_mean_balance = self.run_function(
            "_monthly_mean_balance",
            None,
            denomination=DEFAULT_DENOMINATION,
            effective_date=effective_time,
            all_accounts=(
                e
                for e in [
                    mock_vault_checking1,
                    mock_vault_checking2,
                    mock_vault_savings1,
                    mock_vault_savings2,
                ]
            ),
        )

        # total = 427,500 / 30 days = 14,250
        expected_monthly_mean_balance = Decimal(14250)

        self.assertEqual(monthly_mean_balance, expected_monthly_mean_balance)

    def test_monthly_mean_balance_creation_date_considered(self):
        effective_time = datetime(2020, 5, 1)

        # This balance of 20,000 from 1st to 6th should be ignored by _monthly_mean_balance
        # as the creation_date is set to 6th April
        balance_ts = self.balances_for_checking_account(
            dt=datetime(2020, 4, 1), default=Decimal(20000)
        )

        balance_ts.extend(
            self.balances_for_checking_account(dt=datetime(2020, 4, 6), default=Decimal(500))
        )

        balance_ts.extend(
            self.balances_for_checking_account(dt=datetime(2020, 4, 26), default=Decimal(1000))
        )

        mock_vault = self.create_supervisee_mock(
            alias="us_checking",
            account_id="000001",
            creation_date=datetime(2020, 4, 6),
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
        )

        monthly_mean_balance = self.run_function(
            "_monthly_mean_balance",
            None,
            denomination=DEFAULT_DENOMINATION,
            effective_date=effective_time,
            all_accounts=(e for e in [mock_vault]),
        )

        expected_monthly_mean_balance = Decimal(500)

        self.assertEqual(monthly_mean_balance, expected_monthly_mean_balance)

    def test_extracting_tiered_param_no_flag_on_account(self):
        tier_names = ["good", "bad"]
        tiered_param = dict(good=1000, bad=5)
        account_tier_flags = []

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            None,
            account_tier_flags=account_tier_flags,
            tiered_param=tiered_param,
            tier_names=tier_names,
        )
        self.assertEqual(result, 5)

    def test_extracting_tiered_param_no_flag_on_account_different_order(self):
        tier_names = ["bad", "good"]
        tiered_param = dict(good=1000, bad=5)
        account_tier_flags = []

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            None,
            account_tier_flags=account_tier_flags,
            tiered_param=tiered_param,
            tier_names=tier_names,
        )
        self.assertEqual(result, 1000)

    def test_extracting_tiered_param_account_has_first_flag(self):
        tier_names = ["good", "bad"]
        tiered_param = dict(good=1000, bad=5)
        account_tier_flags = ["good"]

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            None,
            account_tier_flags=account_tier_flags,
            tiered_param=tiered_param,
            tier_names=tier_names,
        )
        self.assertEqual(result, 1000)

    def test_extracting_tiered_param_account_has_middle_flag(self):
        tier_names = ["good", "ugly", "bad"]
        tiered_param = dict(good=1000, ugly=500, bad=5)
        account_tier_flags = ["ugly"]

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            None,
            account_tier_flags=account_tier_flags,
            tiered_param=tiered_param,
            tier_names=tier_names,
        )
        self.assertEqual(result, 500)

    def test_extracting_tiered_param_account_has_last_flag(self):
        tier_names = ["good", "ugly", "bad"]
        tiered_param = dict(good=1000, ugly=500, bad=5)
        account_tier_flags = ["bad"]

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            None,
            account_tier_flags=account_tier_flags,
            tiered_param=tiered_param,
            tier_names=tier_names,
        )
        self.assertEqual(result, 5)

    def test_extracting_tiered_param_account_has_multiple_flags_uses_first(self):
        tier_names = ["good", "ugly", "bad"]
        tiered_param = dict(good=1000, ugly=500, bad=5)
        account_tier_flags = ["bad", "good", "ugly"]

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            None,
            account_tier_flags=account_tier_flags,
            tiered_param=tiered_param,
            tier_names=tier_names,
        )
        self.assertEqual(result, 1000)

    def test_extracting_tiered_param_account_has_different_flag(self):
        tier_names = ["good", "ugly", "bad"]
        tiered_param = dict(good=1000, ugly=500, bad=5)
        account_tier_flags = ["foo"]

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            None,
            account_tier_flags=account_tier_flags,
            tiered_param=tiered_param,
            tier_names=tier_names,
        )
        self.assertEqual(result, 5)

    def test_no_tier_parameter_configured(self):
        tier_names = []
        tiered_param = dict(good=1000, ugly=500, bad=5)
        account_tier_flags = ["foo"]

        with self.assertRaises(InvalidContractParameter) as e:
            self.run_function(
                "_get_dict_value_based_on_account_tier_flag",
                None,
                account_tier_flags=account_tier_flags,
                tiered_param=tiered_param,
                tier_names=tier_names,
            )
        self.assertEqual(
            str(e.exception),
            "No valid account tiers have been configured for this product.",
        )

    def test_handles_no_supervisees(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=28, hour=23, minute=59, tzinfo=timezone.utc)

        mock_vault = self.create_supervisor_mock(supervisees={}, creation_date=start)
        self.run_function(
            "scheduled_code",
            mock_vault,
            effective_date=end,
            event_type="SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES",
        )
        self.run_function(
            "scheduled_code",
            mock_vault,
            effective_date=end,
            event_type="SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES",
        )

        self.assert_no_side_effects(mock_vault)

    def test_get_applicable_postings(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        maintenance_fee = Decimal("10")
        minimum_balance_fee = Decimal("20")
        checking_available_bal = Decimal("1000")
        savings_available_bal = Decimal("1000")

        checking_balance_ts = self.balances_for_checking_account(
            start, default=checking_available_bal
        )
        mock_vault_checking = self.create_supervisee_mock(
            alias="us_checking",
            account_id="000001",
            balance_ts=checking_balance_ts,
            tside=Tside.LIABILITY,
            denomination=DEFAULT_DENOMINATION,
            maintenance_fee_monthly=maintenance_fee,
            tier_names=CHECKING_TIER_NAMES,
            flags=CHECKING_ACTIVE_FLAGS,
            minimum_combined_balance_threshold=CHECKING_MIN_COMBINED_BALANCE,
        )

        savings_balance_ts = self.balances_for_savings_account(start, default=savings_available_bal)
        mock_vault_savings = self.create_supervisee_mock(
            alias="us_savings",
            account_id="000002",
            balance_ts=savings_balance_ts,
            tside=Tside.LIABILITY,
            denomination=DEFAULT_DENOMINATION,
            account_tier_names=SAVINGS_TIER_NAMES,
            flags=SAVINGS_ACTIVE_FLAGS,
            minimum_combined_balance_threshold=SAVINGS_MIN_COMBINED_BALANCE,
        )

        def get_pis_for_account(account_id, account_type):
            client_txn_id = (
                "INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_XX_USD"
                if account_type == "us_checking"
                else "INTERNAL_POSTING_APPLY_MAINTENANCE_FEE_MONTHLY"
            )
            instruction_details = (
                {
                    "description": "Monthly maintenance fee",
                    "event": "APPLY_MONTHLY_FEES",
                    "supervisor": "Applied by supervisor",
                }
                if account_type == "us_checking"
                else {
                    "description": "Maintenance fee monthly",
                    "event": "APPLY_MAINTENANCE_FEE_MONTHLY",
                }
            )
            return [
                # maintenance fee posting
                self.custom_instruction(
                    account_id=account_id,
                    amount=maintenance_fee,
                    credit=False,
                    denomination=DEFAULT_DENOMINATION,
                    account_address=DEFAULT_ADDRESS,
                    client_transaction_id=client_txn_id,
                    instruction_details=instruction_details,
                ),
                # non-maintenance-fee postings
                self.custom_instruction(
                    account_id=account_id,
                    amount=minimum_balance_fee,
                    credit=False,
                    denomination=DEFAULT_DENOMINATION,
                    account_address=DEFAULT_ADDRESS,
                    client_transaction_id="INTERNAL_POSTING_APPLY_MONTHLY_FEES_MEAN_XX_USD",
                    instruction_details={
                        "description": "Minimum balance fee",
                        "event": "APPLY_MONTHLY_FEES",
                    },
                ),
                # some other internal posting
                self.custom_instruction(
                    account_id=account_id,
                    amount=minimum_balance_fee,
                    credit=False,
                    denomination=DEFAULT_DENOMINATION,
                    account_address=DEFAULT_ADDRESS,
                    client_transaction_id="INTERNAL_POSTING_SOMETHING_XX_USD",
                ),
            ]

        def get_expected_pis(input_pis):
            for pi in input_pis:
                pi.client_transaction_id += "_SUPERVISOR"
                pi.instruction_details["supervisor"] = "Applied by supervisor"
            return input_pis

        checking_pis = get_pis_for_account("000001", "us_checking")
        expected_checking_pis = get_expected_pis(checking_pis)
        expected_checking_pis_after_waiver = expected_checking_pis[1:]
        checking_pib = self.mock_posting_instruction_batch(posting_instructions=checking_pis)

        savings_pis = get_pis_for_account("000002", "us_savings")
        expected_savings_pis = get_expected_pis(savings_pis)
        expected_savings_pis_after_waiver = expected_savings_pis[1:]
        savings_pib = self.mock_posting_instruction_batch(posting_instructions=savings_pis)

        supervisees = {
            mock_vault_checking.account_id: mock_vault_checking,
            mock_vault_savings.account_id: mock_vault_savings,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees, creation_date=start)

        test_cases = [
            {
                "description": "checking: below minimum combined balance incurs maintenance fee",
                "input": (
                    mock_vault_checking,
                    checking_pib,
                    "us_checking",
                    Decimal("4999"),
                ),
                "expected_output": expected_checking_pis,
            },
            {
                "description": "checking: at minimum combined balance will waive maintenance fee",
                "input": (
                    mock_vault_checking,
                    checking_pib,
                    "us_checking",
                    Decimal("5000"),
                ),
                "expected_output": expected_checking_pis_after_waiver,
            },
            {
                "description": "checking: above minimum combined balance incurs maintenance fee",
                "input": (
                    mock_vault_checking,
                    checking_pib,
                    "us_checking",
                    Decimal("6000"),
                ),
                "expected_output": expected_checking_pis_after_waiver,
            },
            {
                "description": "checking: empty pib input results in empty postings output",
                "input": (mock_vault_checking, [], "us_checking", Decimal("1000")),
                "expected_output": [],
            },
            {
                "description": "checking: 0 combined balance will incur maintenance fee",
                "input": (
                    mock_vault_checking,
                    checking_pib,
                    "us_checking",
                    Decimal("0"),
                ),
                "expected_output": expected_checking_pis,
            },
            {
                "description": "checking: -ve combined balance will incur maintenance fee",
                "input": (
                    mock_vault_checking,
                    checking_pib,
                    "us_checking",
                    Decimal("-100"),
                ),
                "expected_output": expected_checking_pis,
            },
            {
                "description": "savings: below minimum combined balance will incur maintenance fee",
                "input": (
                    mock_vault_savings,
                    savings_pib,
                    "us_savings",
                    Decimal("4999"),
                ),
                "expected_output": expected_savings_pis,
            },
            {
                "description": "savings: at minimum combined balance will waive maintenance fee",
                "input": (
                    mock_vault_savings,
                    savings_pib,
                    "us_savings",
                    Decimal("5000"),
                ),
                "expected_output": expected_savings_pis_after_waiver,
            },
            {
                "description": "savings: above minimum combined balance incurs maintenance fee",
                "input": (
                    mock_vault_savings,
                    savings_pib,
                    "us_savings",
                    Decimal("6000"),
                ),
                "expected_output": expected_savings_pis_after_waiver,
            },
            {
                "description": "savings: empty pib input results in empty postings output",
                "input": (mock_vault_savings, [], "us_savings", Decimal("1000")),
                "expected_output": [],
            },
            {
                "description": "savings: 0 combined balance will incur maintenance fee",
                "input": (mock_vault_savings, savings_pib, "us_savings", Decimal("0")),
                "expected_output": expected_savings_pis,
            },
            {
                "description": "savings: -ve combined balance will incur maintenance fee",
                "input": (
                    mock_vault_savings,
                    savings_pib,
                    "us_savings",
                    Decimal("-100"),
                ),
                "expected_output": expected_savings_pis,
            },
        ]

        for test_case in test_cases:
            postings = self.run_function(
                "_get_applicable_postings", mock_vault, *test_case["input"]
            )
            self.assertEqual(postings, test_case["expected_output"], test_case["description"])

    def test_get_next_fee_datetime(self):
        creation_date = datetime(2020, 1, 16, 1, 21, 1)
        mock_vault = self.create_supervisee_mock(
            creation_date=creation_date,
            fees_application_day=15,
            fees_application_hour=1,
            fees_application_minute=2,
            fees_application_second=3,
        )

        effective_date = creation_date
        expected_date = datetime(2020, 3, 15, 1, 2, 3)
        result = self.run_function("_get_next_fee_datetime", None, mock_vault, effective_date)
        self.assertEqual(expected_date, result, "effective_date same as creation_date")

        effective_date = datetime(2020, 2, 15, 1, 2, 2)
        expected_date = datetime(2020, 3, 15, 1, 2, 3)
        result = self.run_function("_get_next_fee_datetime", None, mock_vault, effective_date)
        self.assertEqual(expected_date, result, "1 second and 1 month before first schedule time")

        effective_date = datetime(2020, 3, 15, 1, 2, 0)
        expected_date = datetime(2020, 3, 15, 1, 2, 3)
        result = self.run_function("_get_next_fee_datetime", None, mock_vault, effective_date)
        self.assertEqual(expected_date, result, "First expected schedule time")

        effective_date = datetime(2020, 3, 15, 1, 2, 3)
        expected_date = datetime(2020, 4, 15, 1, 2, 3)
        result = self.run_function("_get_next_fee_datetime", None, mock_vault, effective_date)
        self.assertEqual(expected_date, result, "Next expected schedule time")

        effective_date = datetime(2020, 4, 15, 1, 2, 4)
        expected_date = datetime(2020, 5, 15, 1, 2, 3)
        result = self.run_function("_get_next_fee_datetime", None, mock_vault, effective_date)
        self.assertEqual(expected_date, result, "One second after normal effective_date")

        effective_date = datetime(2020, 3, 15, 1, 2, 2)
        expected_date = datetime(2020, 3, 15, 1, 2, 3)
        result = self.run_function("_get_next_fee_datetime", None, mock_vault, effective_date)
        self.assertEqual(expected_date, result, "One second before normal effective_date")

        effective_date = datetime(2020, 3, 15, 1, 2, 2, 345)
        expected_date = datetime(2020, 3, 15, 1, 2, 3)
        result = self.run_function("_get_next_fee_datetime", None, mock_vault, effective_date)
        self.assertEqual(expected_date, result, "Some microseconds before")

        effective_date = datetime(2020, 3, 15, 1, 2, 3, 345)
        expected_date = datetime(2020, 4, 15, 1, 2, 3)
        result = self.run_function("_get_next_fee_datetime", None, mock_vault, effective_date)
        self.assertEqual(expected_date, result, "Some microseconds after")

        effective_date = datetime(2020, 3, 15, 1, 2, 3)
        expected_date = datetime(2020, 4, 15, 1, 2, 3)
        result = self.run_function("_get_next_fee_datetime", None, mock_vault, effective_date)
        self.assertEqual(expected_date, result, "effective_date same as a scheduled date")

    def test_get_committed_default_balance_from_postings(self):
        test_cases = (
            {
                "expected_result": Decimal("-50"),
                "description": "Outgoing Hard Settlement",
                "postings": [self.outbound_hard_settlement(amount=50, denomination="USD")],
            },
            {
                "expected_result": Decimal("50"),
                "description": "Incoming Hard Settlement",
                "postings": [self.inbound_hard_settlement(amount=50, denomination="USD")],
            },
            {
                "expected_result": Decimal("-30"),
                "description": "Debit Transfer",
                "postings": [
                    self.outbound_transfer(amount=30, denomination="USD"),
                ],
            },
            {
                "expected_result": Decimal("30"),
                "description": "Credit Transfer",
                "postings": [
                    self.inbound_transfer(amount=30, denomination="USD"),
                ],
            },
            {
                "expected_result": Decimal("0"),
                "description": "Incoming Authorisation ignored",
                "postings": [self.inbound_auth(amount=50, denomination="USD")],
            },
            {
                "expected_result": Decimal("-0"),
                "description": "Outgoing Authorisation ignored",
                "postings": [self.outbound_auth(amount=50, denomination="USD")],
            },
            {
                "expected_result": Decimal("30"),
                "description": "Custom Instruction credit default committed",
                "postings": [
                    self.custom_instruction(
                        amount="30",
                        credit=True,
                        denomination="USD",
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    )
                ],
            },
            {
                "expected_result": Decimal("-30"),
                "description": "Custom Instruction debit default committed",
                "postings": [
                    self.custom_instruction(
                        amount="30",
                        credit=False,
                        denomination="USD",
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    )
                ],
            },
            {
                "expected_result": Decimal("0"),
                "description": "Custom Instruction non-default address ignored",
                "postings": [
                    self.custom_instruction(
                        amount="30",
                        credit=False,
                        denomination="USD",
                        account_address="INTEREST_ACCRUAL",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    )
                ],
            },
            {
                "expected_result": Decimal("0"),
                "description": "Custom Instruction not committed ignored",
                "postings": [
                    self.custom_instruction(
                        amount="30",
                        credit=False,
                        denomination="USD",
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.PENDING_OUT,
                    )
                ],
            },
            {
                "expected_result": Decimal("30"),
                "description": "Settlement on inbound authorisation",
                "postings": [
                    self.settle_inbound_auth(unsettled_amount=30, final=True, denomination="USD")
                ],
            },
            {
                "expected_result": Decimal("-30"),
                "description": "Settlement on outbound authorisation",
                "postings": [
                    self.settle_outbound_auth(unsettled_amount=30, final=True, denomination="USD")
                ],
            },
            {
                "expected_result": Decimal("0"),
                "description": "Release ignored",
                "postings": [self.release_outbound_auth(unsettled_amount=30, denomination="USD")],
            },
            {
                "expected_result": Decimal("-60"),
                "description": "Multiple postings in batch",
                "include_out_auth": False,
                "postings": [
                    self.outbound_transfer(amount=30, denomination="USD"),
                    self.inbound_auth(amount=50, denomination="USD"),
                    self.settle_outbound_auth(unsettled_amount=30, final=True, denomination="USD"),
                ],
            },
        )

        for test_case in test_cases:
            pib = self.mock_posting_instruction_batch(posting_instructions=test_case["postings"])

            result = self.run_function(
                "_get_committed_default_balance_from_postings",
                None,
                postings=pib,
                denomination="USD",
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_ordered_savings_sweep_savings_accounts(self):

        test_cases = [
            {
                "description": "param list matches plan account list",
                "savings_sweep_account_hierarchy": OptionalValue(
                    json.dumps(["savings_2", "savings_3", "savings_1"])
                ),
                "expected_output": ["savings_2", "savings_3", "savings_1"],
            },
            {
                "description": "param list < plan account list",
                "savings_sweep_account_hierarchy": OptionalValue(
                    json.dumps(["savings_3", "savings_1"])
                ),
                "expected_output": ["savings_3", "savings_1"],
            },
            {
                "description": "param list > plan account list",
                "savings_sweep_account_hierarchy": OptionalValue(
                    json.dumps(
                        [
                            "savings_2",
                            "savings_5",
                            "savings_3",
                            "savings_1",
                            "savings_4",
                        ]
                    )
                ),
                "expected_output": ["savings_2", "savings_3", "savings_1"],
            },
            {
                "description": "param list empty",
                "savings_sweep_account_hierarchy": OptionalValue(json.dumps([])),
                "expected_output": [],
            },
            {
                "description": "param list not set",
                "savings_sweep_account_hierarchy": OptionalValue(is_set=False),
                "expected_output": ["savings_1", "savings_2", "savings_3"],
            },
            {
                "description": "param list mismatches plan account list",
                "savings_sweep_account_hierarchy": OptionalValue(
                    json.dumps(["savings_2", "savings_5", "savings_1"])
                ),
                "expected_output": ["savings_2", "savings_1"],
            },
            {
                "description": "param list all off plan",
                "savings_sweep_account_hierarchy": OptionalValue(
                    json.dumps(["savings_4", "savings_5", "savings_6"])
                ),
                "expected_output": [],
            },
        ]

        balance_ts = self.balances_for_checking_account(dt=DEFAULT_DATE, default=Decimal("100"))
        balance_ts_savings = self.balances_for_savings_account(
            dt=DEFAULT_DATE, default=Decimal("100")
        )

        mock_vault_savings_1 = self.create_supervisee_mock(
            creation_date=datetime(2020, 1, 16, tzinfo=timezone.utc),
            alias="us_savings",
            account_id="savings_1",
            balance_ts=balance_ts_savings,
        )

        mock_vault_savings_2 = self.create_supervisee_mock(
            creation_date=datetime(2020, 1, 17, tzinfo=timezone.utc),
            alias="us_savings",
            account_id="savings_2",
            balance_ts=balance_ts_savings,
        )

        mock_vault_savings_3 = self.create_supervisee_mock(
            creation_date=datetime(2020, 1, 18, tzinfo=timezone.utc),
            alias="us_savings",
            account_id="savings_3",
            balance_ts=balance_ts_savings,
        )

        mocked_savings_sweep_savings_accounts = [
            mock_vault_savings_1,
            mock_vault_savings_2,
            mock_vault_savings_3,
        ]

        for test_case in test_cases:
            mocked_checking = self.create_supervisee_mock(
                alias="us_checking",
                account_id="000001",
                balance_ts=balance_ts,
                savings_sweep_account_hierarchy=test_case["savings_sweep_account_hierarchy"],
            )

            result = self.run_function(
                "_get_ordered_savings_sweep_savings_accounts",
                None,
                mocked_checking,
                mocked_savings_sweep_savings_accounts,
            )

            output_account_ids = [account.account_id for account in result]

            self.assertEqual(
                output_account_ids,
                test_case["expected_output"],
                test_case["description"],
            )

    def test_get_available_savings_sweep_balances(self):

        test_cases = [
            {
                "description": "param list matches plan account list",
                "savings_sweep_account_hierarchy": OptionalValue(
                    json.dumps(["savings_2", "savings_3", "savings_1"])
                ),
                "expected_output": {
                    "savings_2": Decimal("123"),
                    "savings_3": Decimal("500"),
                    "savings_1": Decimal("3000"),
                },
            },
            {
                "description": "param list < plan account list",
                "savings_sweep_account_hierarchy": OptionalValue(
                    json.dumps(["savings_3", "savings_1"])
                ),
                "expected_output": {
                    "savings_3": Decimal("500"),
                    "savings_1": Decimal("3000"),
                },
            },
            {
                "description": "param list > plan account list",
                "savings_sweep_account_hierarchy": OptionalValue(
                    json.dumps(
                        [
                            "savings_2",
                            "savings_5",
                            "savings_3",
                            "savings_1",
                            "savings_4",
                        ]
                    )
                ),
                "expected_output": {
                    "savings_2": Decimal("123"),
                    "savings_3": Decimal("500"),
                    "savings_1": Decimal("3000"),
                },
            },
            {
                "description": "param list empty",
                "savings_sweep_account_hierarchy": OptionalValue(json.dumps([])),
                "expected_output": {},
            },
            {
                "description": "param list not set",
                "savings_sweep_account_hierarchy": OptionalValue(is_set=False),
                "expected_output": {
                    "savings_1": Decimal("3000"),
                    "savings_2": Decimal("123"),
                    "savings_3": Decimal("500"),
                },
            },
            {
                "description": "param list mismatches plan account list",
                "savings_sweep_account_hierarchy": OptionalValue(
                    json.dumps(["savings_2", "savings_5", "savings_1"])
                ),
                "expected_output": {
                    "savings_2": Decimal("123"),
                    "savings_1": Decimal("3000"),
                },
            },
            {
                "description": "param list all off plan",
                "savings_sweep_account_hierarchy": OptionalValue(
                    json.dumps(["savings_4", "savings_5", "savings_6"])
                ),
                "expected_output": {},
            },
        ]

        balance_ts_savings_1 = self.balances_for_savings_account(
            dt=DEFAULT_DATE, default=Decimal("3000")
        )

        balance_ts_savings_2 = self.balances_for_savings_account(
            dt=DEFAULT_DATE, default=Decimal("123")
        )

        balance_ts_savings_3 = self.balances_for_savings_account(
            dt=DEFAULT_DATE, default=Decimal("500")
        )

        mock_vault_savings_1 = self.create_supervisee_mock(
            creation_date=datetime(2020, 1, 16, tzinfo=timezone.utc),
            alias="us_savings",
            account_id="savings_1",
            balance_ts=balance_ts_savings_1,
        )

        mock_vault_savings_2 = self.create_supervisee_mock(
            creation_date=datetime(2020, 1, 17, tzinfo=timezone.utc),
            alias="us_savings",
            account_id="savings_2",
            balance_ts=balance_ts_savings_2,
        )

        mock_vault_savings_3 = self.create_supervisee_mock(
            creation_date=datetime(2020, 1, 18, tzinfo=timezone.utc),
            alias="us_savings",
            account_id="savings_3",
            balance_ts=balance_ts_savings_3,
        )

        mocked_savings_sweep_savings_accounts = [
            mock_vault_savings_1,
            mock_vault_savings_2,
            mock_vault_savings_3,
        ]

        for test_case in test_cases:
            mocked_checking = self.create_supervisee_mock(
                alias="us_checking",
                account_id="000001",
                savings_sweep_account_hierarchy=test_case["savings_sweep_account_hierarchy"],
            )

            result = self.run_function(
                "_get_available_savings_sweep_balances",
                None,
                mocked_checking,
                mocked_savings_sweep_savings_accounts,
                datetime(2021, 2, 19, tzinfo=timezone.utc),
                DEFAULT_DENOMINATION,
            )

            self.assertEqual(result, test_case["expected_output"], test_case["description"])
            result_order = [key for key in result.keys()]
            expected_order = [key for key in test_case["expected_output"].keys()]

            self.assertEqual(result_order, expected_order, test_case["description"])

    def test_get_savings_sweep_transfer_amount_with_transfer_unit(self):

        test_cases = [
            {
                "description": "savings more than required amount",
                "savings_sweep_transfer_unit": Decimal("50"),
                "savings_available_balance": Decimal("140"),
                "maximum_amount_required": Decimal("95"),
                "expected_output": Decimal("100"),
            },
            {
                "description": "savings less than required amount",
                "savings_sweep_transfer_unit": Decimal("50"),
                "savings_available_balance": Decimal("140"),
                "maximum_amount_required": Decimal("170"),
                "expected_output": Decimal("100"),
            },
            {
                "description": "savings more than required amount big difference",
                "savings_sweep_transfer_unit": Decimal("50"),
                "savings_available_balance": Decimal("159000000.3"),
                "maximum_amount_required": Decimal("5"),
                "expected_output": Decimal("50"),
            },
            {
                "description": "savings less than required amount big difference",
                "savings_sweep_transfer_unit": Decimal("50"),
                "savings_available_balance": Decimal("159.3"),
                "maximum_amount_required": Decimal("170000"),
                "expected_output": Decimal("150"),
            },
            {
                "description": "savings more than required amount with fractional "
                "savings_sweep_transfer_unit",
                "savings_sweep_transfer_unit": Decimal("0.5"),
                "savings_available_balance": Decimal("5123.81"),
                "maximum_amount_required": Decimal("189.3"),
                "expected_output": Decimal("189.5"),
            },
            {
                "description": "savings less than required amount with fractional "
                "savings_sweep_transfer_unit",
                "savings_sweep_transfer_unit": Decimal("0.02"),
                "savings_available_balance": Decimal("120.07"),
                "maximum_amount_required": Decimal("2001.3"),
                "expected_output": Decimal("120.06"),
            },
            {
                "description": "savings more than required amount with "
                "savings_sweep_transfer_unit odd number",
                "savings_sweep_transfer_unit": Decimal("7"),
                "savings_available_balance": Decimal("29.5"),
                "maximum_amount_required": Decimal("15.1"),
                "expected_output": Decimal("21"),
            },
            {
                "description": "savings less than required amount with "
                "savings_sweep_transfer_unit odd number",
                "savings_sweep_transfer_unit": Decimal("7"),
                "savings_available_balance": Decimal("29.5"),
                "maximum_amount_required": Decimal("35"),
                "expected_output": Decimal("28"),
            },
            {
                "description": "savings not enough for any transfer",
                "savings_sweep_transfer_unit": Decimal("100"),
                "savings_available_balance": Decimal("99.99"),
                "maximum_amount_required": Decimal("10"),
                "expected_output": Decimal("0"),
            },
            {
                "description": "savings more than required amount with "
                "savings_sweep_transfer_unit zero",
                "savings_sweep_transfer_unit": Decimal("0"),
                "savings_available_balance": Decimal("199.99"),
                "maximum_amount_required": Decimal("10"),
                "expected_output": Decimal("10"),
            },
            {
                "description": "savings less than required amount with "
                "savings_sweep_transfer_unit zero",
                "savings_sweep_transfer_unit": Decimal("0"),
                "savings_available_balance": Decimal("199.99"),
                "maximum_amount_required": Decimal("10000"),
                "expected_output": Decimal("199.99"),
            },
        ]

        for test_case in test_cases:
            mocked_checking = self.create_supervisee_mock(
                alias="us_checking",
                account_id="000001",
                savings_sweep_transfer_unit=test_case["savings_sweep_transfer_unit"],
            )

            result = self.run_function(
                "_get_savings_sweep_transfer_amount_with_transfer_unit",
                None,
                mocked_checking,
                test_case["savings_available_balance"],
                test_case["maximum_amount_required"],
            )

            self.assertEqual(result, test_case["expected_output"], test_case["description"])

    def test_filter_non_supervisee_postings(self):
        mock_vault, _, _ = self.get_default_setup(
            checking_balance=Decimal("-10"), savings_balance=Decimal("10")
        )

        relevant_pi = self.outbound_hard_settlement(
            denomination=DEFAULT_DENOMINATION,
            amount="50",
            account_id="000001",
        )

        irrelevant_pi = self.outbound_transfer(
            denomination=DEFAULT_DENOMINATION,
            amount="100",
            account_id="some_other_account",
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[relevant_pi, irrelevant_pi])

        result = self.run_function("_filter_non_supervisee_postings", mock_vault, mock_vault, pib)

        self.assertEqual(result, [relevant_pi])
