# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

# library
import library.us_products_v3.supervisors.template.us_supervisor_v3 as odp_supervisor

# features
import library.features.v3.common.utils as utils

# inception sdk
from inception_sdk.test_framework.contracts.unit.supervisor.common import (
    SupervisorContractTest,
    balance_dimensions,
    create_hook_directive,
    create_posting_instruction_batch_directive,
)
from inception_sdk.vault.contracts.supervisor.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Balance,
    BalanceDefaultDict,
    BalancesObservation,
    EventTypeSchedule,
    InvalidContractParameter,
    OptionalValue,
    Phase,
    Rejected,
    Tside,
)
from inception_sdk.vault.contracts.types import RejectedReason

CONTRACT_FILE = "library/us_products_v3/supervisors/template/us_supervisor_v3.py"
DEFAULT_SAVINGS_ACCOUNT = "000002"
DEFAULT_CHECKING_ACCOUNT = "000001"
DEFAULT_DENOMINATION = "USD"
DEFAULT_DATE = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
HOOK_EXECUTION_ID = "MOCK_HOOK"
OVERDRAFT_FEE_INCOME_ACCOUNT = "OVERDRAFT_FEE_INCOME"


CHECKING_TIER_NAMES = json.dumps(["DEFAULT_TIER"])
CHECKING_ACTIVE_FLAGS = ["DEFAULT_TIER"]
CHECKING_MIN_COMBINED_BALANCE = json.dumps({"DEFAULT_TIER": "5000"})
SAVINGS_TIER_NAMES = json.dumps(["LOWER_TIER"])
SAVINGS_ACTIVE_FLAGS = ["LOWER_TIER"]
SAVINGS_MIN_COMBINED_BALANCE = json.dumps({"LOWER_TIER": "5000"})

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
        # "checking": CHECKING_CONTRACT_FILE,
        # "savings": SAVINGS_CONTRACT_FILE,
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
    ) -> list[tuple[datetime, BalanceDefaultDict]]:

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

    def get_outbound_auth_mock(self, amount, account_id="000001"):
        return self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_auth(
                    denomination=DEFAULT_DENOMINATION, amount=amount, account_id=account_id
                ),
            ],
        )

    def get_default_setup(
        self,
        checking_balance=Decimal("0"),
        savings_balance=Decimal("0"),
        posting_instructions_by_supervisee=None,
        checking_account_hook_return_data=None,
        existing_mock=None,
    ):
        balance_ts = self.balances_for_checking_account(dt=DEFAULT_DATE, default=checking_balance)
        balance_ts_savings = self.balances_for_savings_account(
            dt=DEFAULT_DATE, default=savings_balance
        )
        balance_observation_fetchers = {
            "checking_account": {"live_balance": BalancesObservation(balances=balance_ts[0][1])},
            "savings_account": {
                "live_balance": BalancesObservation(balances=balance_ts_savings[0][1])
            },
        }
        balances_observation_fetchers = balance_observation_fetchers or {}
        checking_observation_fetcher = balances_observation_fetchers.get("checking_account")
        savings_observation_fetcher = balances_observation_fetchers.get("savings_account")

        mock_vault_checking = self.create_supervisee_mock(
            alias="us_checking",
            account_id="000001",
            balance_ts=balance_ts,
            balances_observation_fetchers_mapping=checking_observation_fetcher,
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
            hook_return_data=checking_account_hook_return_data,
        )

        mock_vault_savings = self.create_supervisee_mock(
            alias="us_savings",
            account_id="000002",
            balance_ts=balance_ts_savings,
            balances_observation_fetchers_mapping=savings_observation_fetcher,
        )

        supervisees = {"000001": mock_vault_checking, "000002": mock_vault_savings}

        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            existing_mock=existing_mock,
        )

        return (mock_vault, mock_vault_checking, mock_vault_savings)

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

    def test_postings_with_multiple_checking_account_ids_throws_exception(self):
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

        debit_posting_1 = self.mock_posting_instruction(
            amount=20.00,
            credit=False,
            advice=DEFAULT_DATE,
            denomination="USD",
            instruction_type="HardSettlement",
            account_id="000001",
        )
        debit_posting_2 = self.mock_posting_instruction(
            amount=30.00,
            credit=False,
            advice=DEFAULT_DATE,
            denomination="USD",
            instruction_type="HardSettlement",
            account_id="000002",
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[debit_posting_1, debit_posting_2]
        )
        posting_instructions_by_supervisee = {"000001": debit_posting_1, "000002": debit_posting_2}
        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
        )

        with self.assertRaises(Rejected) as ex:
            self.run_function("post_posting_code", mock_vault, pib, DEFAULT_DATE)

        self.assertIn(
            "Multiple checking accounts not supported.",
            str(ex.exception),
        )

    def test_postings_with_multiple_savings_account_ids_throws_exception(self):
        mock_vault_checking_1 = self.create_supervisee_mock(
            alias="us_checking", account_id="000001"
        )
        mock_vault_savings_1 = self.create_supervisee_mock(alias="us_savings", account_id="000003")
        mock_vault_savings_2 = self.create_supervisee_mock(alias="us_savings", account_id="000003")

        supervisees = {
            "000001": mock_vault_checking_1,
            "000002": mock_vault_savings_1,
            "000003": mock_vault_savings_2,
        }

        debit_posting_1 = self.mock_posting_instruction(
            amount=20.00,
            credit=False,
            advice=DEFAULT_DATE,
            denomination="USD",
            instruction_type="HardSettlement",
            account_id="000001",
        )
        debit_posting_2 = self.mock_posting_instruction(
            amount=30.00,
            credit=False,
            advice=DEFAULT_DATE,
            denomination="USD",
            instruction_type="HardSettlement",
            account_id="000002",
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[debit_posting_1, debit_posting_2]
        )
        posting_instructions_by_supervisee = {"000001": debit_posting_1, "000002": debit_posting_2}
        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
        )

        with self.assertRaises(Rejected) as ex:
            self.run_function("post_posting_code", mock_vault, pib, DEFAULT_DATE)

        self.assertIn(
            "Multiple savings accounts not supported.",
            str(ex.exception),
        )

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
            alias="us_checking",
            hook_directives=hook_directive,
            autosave_savings_account=OptionalValue(is_set=False),
        )

        supervisees = {DEFAULT_CHECKING_ACCOUNT: mock_vault_checking}
        posting_instructions_by_supervisee = {"000001": pib}

        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
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
            alias="us_checking",
            hook_directives=hook_directive,
            autosave_savings_account=OptionalValue(is_set=False),
        )

        supervisees = {DEFAULT_CHECKING_ACCOUNT: mock_vault_checking}
        posting_instructions_by_supervisee = {"000001": pib}

        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
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
            alias="us_checking",
            hook_directives=hook_directive,
            autosave_savings_account=OptionalValue(is_set=False),
        )

        supervisees = {DEFAULT_CHECKING_ACCOUNT: mock_vault_checking}
        posting_instructions_by_supervisee = {"000001": pib}

        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
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
        posting_instructions_by_supervisee = {"000001": pib}
        mock_vault = self.create_supervisor_mock(
            supervisees=supervisees,
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
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


class PrePostingCodeTest(SavingsSweepSupervisorTest):
    @patch.object(odp_supervisor, "vault")
    def test_override_posting_always_accepted(self, mock_vault: Mock):
        postings_with_override = self.mock_posting_instruction_batch(
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("5"))],
            batch_details={"force_override": "true"},
        )
        self.assertIsNone(
            odp_supervisor.pre_posting_code(
                postings=postings_with_override,
                effective_date=DEFAULT_DATE,
            )
        )

    @patch.object(odp_supervisor, "vault")
    def test_without_override_posting_rejected(self, mock_vault: Mock):
        # should get rejected if not for the batch_details
        postings = self.mock_posting_instruction_batch(
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("5"))],
        )
        with self.assertRaises(Rejected):
            odp_supervisor.pre_posting_code(
                postings=postings,
                effective_date=DEFAULT_DATE,
            )

    @patch.object(odp_supervisor, "_setup_supervisor_schedules")
    @patch.object(odp_supervisor, "vault")
    def test_scheduled_code_setup_odp_link(
        self,
        mock_vault: Mock,
        mock__setup_supervisor_schedules: Mock,
    ):

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_balance=Decimal("-10"),
            savings_balance=Decimal("10"),
            existing_mock=mock_vault,
        )

        odp_supervisor.scheduled_code("SETUP_ODP_LINK", DEFAULT_DATE)
        mock__setup_supervisor_schedules.assert_called_once_with(
            mock_vault, "SETUP_ODP_LINK", DEFAULT_DATE
        )

    @patch.object(utils, "instruct_posting_batch")
    @patch.object(odp_supervisor, "vault")
    def test_scheduled_code_odp_sweep_no_sweep_needed(
        self, mock_vault: Mock, mock_instruct_posting_batch: Mock
    ):
        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_balance=Decimal("100"),
            savings_balance=Decimal("500"),
            existing_mock=mock_vault,
        )

        odp_supervisor.scheduled_code("ODP_SWEEP", DEFAULT_DATE)
        mock_instruct_posting_batch.assert_called_once_with(
            mock_vault_checking, [], DEFAULT_DATE, "ODP_SWEEP"
        )

    @patch.object(utils, "instruct_posting_batch")
    @patch.object(odp_supervisor, "vault")
    def test_scheduled_code_odp_sweep_transfers_funds_when_checking_account_is_negative(
        self, mock_vault: Mock, mock_instruct_posting_batch: Mock
    ):

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_balance=Decimal("-100"),
            savings_balance=Decimal("500"),
            existing_mock=mock_vault,
        )

        odp_supervisor.scheduled_code("ODP_SWEEP", DEFAULT_DATE)
        mock_instruct_posting_batch.assert_called_once_with(
            mock_vault_checking,
            ["INTERNAL_POSTING_SWEEP_WITHDRAWAL_FROM_000002_MOCK_HOOK"],
            DEFAULT_DATE,
            "ODP_SWEEP",
        )

    @patch.object(odp_supervisor, "vault")
    def test_pre_posting_code_no_checking_account(self, mock_vault: Mock):
        mock_vault_savings = self.create_supervisee_mock(alias="us_savings", account_id="000001")
        supervisees = {
            "000001": mock_vault_savings,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees, existing_mock=mock_vault)

        debit_posting = self.mock_posting_instruction(
            amount=20.00,
            credit=False,
            advice=DEFAULT_DATE,
            denomination="USD",
            instruction_type="HardSettlement",
            account_id="000002",
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[debit_posting])
        with self.assertRaises(Rejected) as r:
            odp_supervisor.pre_posting_code(pib, DEFAULT_DATE)
        self.assertEqual(r.exception.message, "Requested 1 us_checking accounts but found 0.")

    @patch.object(odp_supervisor, "vault")
    def test_pre_posting_code_multiple_checking_accounts(self, mock_vault: Mock):

        mock_vault_checking_1 = self.create_supervisee_mock(
            alias="us_checking", account_id="CHECKING_ACCOUNT"
        )
        mock_vault_checking_2 = self.create_supervisee_mock(
            alias="us_checking", account_id="EXTRA_CHECKING_ACCOUNT"
        )
        supervisees = {
            "CHECKING_ACCOUNT": mock_vault_checking_1,
            "EXTRA_CHECKING_ACCOUNT": mock_vault_checking_2,
        }
        mock_vault = self.create_supervisor_mock(supervisees=supervisees, existing_mock=mock_vault)

        pib = self.get_outbound_hard_settlement_mock("20")

        with self.assertRaises(Rejected) as r:
            odp_supervisor.pre_posting_code(pib, DEFAULT_DATE)
        self.assertEqual(r.exception.message, "Requested 1 us_checking accounts but found 2.")

    @patch.object(odp_supervisor, "vault")
    def test_pre_posting_code_checking_account_has_enough_funds(self, mock_vault: Mock):
        hook_return_data = None
        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_balance=Decimal("100"),
            savings_balance=Decimal("0"),
            checking_account_hook_return_data=hook_return_data,
            existing_mock=mock_vault,
        )

        pib = self.get_outbound_hard_settlement_mock("20")

        # Returns None if no rejections are raised
        self.assertIsNone(odp_supervisor.pre_posting_code(pib, DEFAULT_DATE))

    @patch.object(odp_supervisor, "vault")
    def test_pre_posting_code_checking_account_rejection_tnc(self, mock_vault: Mock):
        hook_return_data = Rejected(
            "Against Terms and Conditions", reason_code=RejectedReason.AGAINST_TNC
        )

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_balance=Decimal("100"),
            savings_balance=Decimal("500"),
            checking_account_hook_return_data=hook_return_data,
            existing_mock=mock_vault,
        )

        pib = self.get_outbound_hard_settlement_mock("200")

        with self.assertRaises(Rejected) as r:
            odp_supervisor.pre_posting_code(pib, DEFAULT_DATE)
        self.assertEqual(r.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(r.exception.message, "Against Terms and Conditions")

    @patch.object(odp_supervisor, "vault")
    def test_pre_posting_code_checking_balance_insufficient_no_savings_account(
        self, mock_vault: Mock
    ):
        hook_return_data = Rejected(
            "Insufficient Funds", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )
        pib = self.get_outbound_hard_settlement_mock("200")

        mock_vault_checking = self.create_supervisee_mock(
            alias="us_checking",
            checking_balance=Decimal("100"),
            account_id="CHECKING_ACCOUNT",
            hook_return_data=hook_return_data,
        )
        supervisees = {
            "CHECKING_ACCOUNT": mock_vault_checking,
        }
        mock_vault = self.create_supervisor_mock(supervisees=supervisees, existing_mock=mock_vault)

        with self.assertRaises(Rejected) as r:
            odp_supervisor.pre_posting_code(pib, DEFAULT_DATE)
        self.assertEqual(r.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)
        self.assertEqual(
            r.exception.message,
            "Insufficient Funds",
        )

    @patch.object(odp_supervisor, "vault")
    def test_pre_posting_code_checking_balance_insufficient_multiple_savings_accounts(
        self, mock_vault: Mock
    ):
        balance_ts_checking = self.balances_for_checking_account(default=Decimal("100"))
        balance_ts = self.balances_for_savings_account(default=Decimal("100"))
        hook_return_data = Rejected(
            "Insufficient Funds", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )
        pib = self.get_outbound_hard_settlement_mock("200")

        mock_vault_checking = self.create_supervisee_mock(
            alias="us_checking",
            balance_ts=balance_ts_checking,
            account_id="CHECKING_ACCOUNT",
            hook_return_data=hook_return_data,
        )
        mock_vault_savings_1 = self.create_supervisee_mock(
            alias="us_savings", balance_ts=balance_ts, account_id="SAVINGS_ACCOUNT"
        )
        mock_vault_savings_2 = self.create_supervisee_mock(
            alias="us_savings", balance_ts=balance_ts, account_id="EXTRA_SAVINGS_ACCOUNT"
        )
        supervisees = {
            "CHECKING_ACCOUNT": mock_vault_checking,
            "SAVINGS_ACCOUNT": mock_vault_savings_1,
            "EXTRA_SAVINGS_ACCOUNT": mock_vault_savings_2,
        }
        mock_vault = self.create_supervisor_mock(supervisees=supervisees, existing_mock=mock_vault)

        with self.assertRaises(Rejected) as r:
            odp_supervisor.pre_posting_code(pib, DEFAULT_DATE)
        self.assertEqual(r.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(
            r.exception.message,
            "Requested 1 us_savings accounts but found 2.",
        )

    @patch.object(odp_supervisor.utils, "get_parameter")
    @patch.object(odp_supervisor, "vault")
    def test_pre_posting_code_checking_balance_insufficient_combined_balance_sufficient(
        self, mock_vault: Mock, mock_get_parameter: Mock
    ):
        hook_return_data = Rejected(
            "Insufficient Funds", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )
        pib = self.get_outbound_hard_settlement_mock("200")
        posting_instructions_by_supervisee = {"000001": pib}

        mock_get_parameter.side_effect = [Decimal(1000), "USD"]

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_balance=Decimal("100"),
            savings_balance=Decimal("500"),
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            checking_account_hook_return_data=hook_return_data,
            existing_mock=mock_vault,
        )

        # Returns None if no rejections are raised
        self.assertIsNone(odp_supervisor.pre_posting_code(pib, DEFAULT_DATE))

    @patch.object(odp_supervisor.utils, "get_parameter")
    @patch.object(odp_supervisor, "vault")
    def test_pre_posting_code_checking_balance_insufficient_combined_balance_plus_od_sufficient(
        self, mock_vault: Mock, mock_get_parameter: Mock
    ):
        hook_return_data = Rejected(
            "Insufficient Funds", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )
        pib = self.get_outbound_hard_settlement_mock("1200")
        posting_instructions_by_supervisee = {"000001": pib}

        mock_get_parameter.side_effect = [Decimal(1000), "USD"]

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_balance=Decimal("100"),
            savings_balance=Decimal("500"),
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            checking_account_hook_return_data=hook_return_data,
            existing_mock=mock_vault,
        )

        # Returns None if no rejections are raised
        self.assertIsNone(odp_supervisor.pre_posting_code(pib, DEFAULT_DATE))

    @patch.object(utils, "get_parameter")
    @patch.object(odp_supervisor, "vault")
    def test_pre_posting_code_checking_balance_insufficient_combined_balance_plus_od_insufficient(
        self, mock_vault: Mock, mock_get_parameter: Mock
    ):
        hook_return_data = Rejected(
            "Insufficient Funds", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )
        pib = self.get_outbound_hard_settlement_mock("215")
        posting_instructions_by_supervisee = {"000001": pib}

        mock_get_parameter.side_effect = [Decimal(10), "USD"]

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_balance=Decimal("100"),
            savings_balance=Decimal("100"),
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            checking_account_hook_return_data=hook_return_data,
            existing_mock=mock_vault,
        )

        with self.assertRaises(Rejected) as r:
            odp_supervisor.pre_posting_code(pib, DEFAULT_DATE)
        self.assertEqual(r.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)
        self.assertEqual(
            r.exception.message,
            (
                "Combined checking and savings account balance 200.00 "
                "insufficient to cover net transaction amount -215"
            ),
        )

    @patch.object(odp_supervisor.utils, "get_parameter")
    @patch.object(odp_supervisor, "vault")
    def test_pre_posting_code_combined_balance_sufficient_with_outbound_auth(
        self, mock_vault: Mock, mock_get_parameter: Mock
    ):
        hook_return_data = Rejected(
            "Insufficient Funds", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )
        pib = self.get_outbound_auth_mock("200")
        posting_instructions_by_supervisee = {"000001": pib}

        mock_get_parameter.side_effect = [Decimal(0), "USD"]

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_balance=Decimal("100"),
            savings_balance=Decimal("500"),
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            checking_account_hook_return_data=hook_return_data,
            existing_mock=mock_vault,
        )

        # Returns None if no rejections are raised
        self.assertIsNone(odp_supervisor.pre_posting_code(pib, DEFAULT_DATE))

    @patch.object(odp_supervisor.utils, "get_parameter")
    @patch.object(odp_supervisor, "vault")
    def test_pre_posting_code_combined_balance_insufficient_with_outbound_auth(
        self, mock_vault: Mock, mock_get_parameter: Mock
    ):
        hook_return_data = Rejected(
            "Insufficient Funds", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )
        pib = self.get_outbound_auth_mock("200")
        posting_instructions_by_supervisee = {"000001": pib}

        mock_get_parameter.side_effect = [Decimal(0), "USD"]

        mock_vault, mock_vault_checking, mock_vault_savings = self.get_default_setup(
            checking_balance=Decimal("100"),
            savings_balance=Decimal("50"),
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            checking_account_hook_return_data=hook_return_data,
            existing_mock=mock_vault,
        )

        with self.assertRaises(Rejected) as r:
            odp_supervisor.pre_posting_code(pib, DEFAULT_DATE)
        self.assertEqual(r.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)
        self.assertEqual(
            r.exception.message,
            "Combined checking and savings account balance 150.00 \
insufficient to cover net transaction amount -200",
        )
