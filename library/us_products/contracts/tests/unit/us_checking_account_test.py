# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps as json_dumps, loads
from typing import Dict, List, Optional, Tuple
from unittest.mock import call, Mock

# common
from inception_sdk.test_framework.contracts.unit.common import (
    ContractTest,
    balance_dimensions,
    CLIENT_ID_0,
    CLIENT_TRANSACTION_ID_0,
    CLIENT_ID_1,
    CLIENT_TRANSACTION_ID_1,
)
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Phase,
    Balance,
    Rejected,
    Tside,
    RejectedReason,
    UnionItemValue,
    NumberShape,
    Parameter,
    InvalidContractParameter,
    OptionalValue,
    BalanceDefaultDict,
)

CONTRACT_FILE = "library/us_products/contracts/us_checking_account.py"
UTILS_MODULE_FILE = "library/common/contract_modules/utils.py"
INTEREST_MODULE_FILE = "library/common/contract_modules/interest.py"

DEFAULT_DENOMINATION = "GBP"
ADDITIONAL_DENOMINATIONS = json_dumps(["USD", "EUR"])
DEFAULT_DATE = datetime(2019, 1, 1)
ACCRUED_OVERDRAFT_RECEIVABLE = "ACCRUED_OVERDRAFT_RECEIVABLE"
ACCRUED_DEPOSIT_PAYABLE = "ACCRUED_DEPOSIT_PAYABLE"
ACCRUED_DEPOSIT_RECEIVABLE = "ACCRUED_DEPOSIT_RECEIVABLE"
ACCRUED_INCOMING = "ACCRUED_INCOMING"
ACCRUED_OUTGOING = "ACCRUED_OUTGOING"
ACCRUED_OVERDRAFT_FEE_RECEIVABLE = "ACCRUED_OVERDRAFT_FEE_RECEIVABLE"
HOOK_EXECUTION_ID = "MOCK_HOOK"
DORMANCY_FLAG = "ACCOUNT_DORMANT"
STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG = "STANDARD_OVERDRAFT_TRANSACTION_COVERAGE"
INTERNAL_CONTRA = "INTERNAL_CONTRA"
ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
OVERDRAFT_FEE_INCOME_ACCOUNT = "OVERDRAFT_FEE_INCOME"
OVERDRAFT_FEE_RECEIVABLE_ACCOUNT = "OVERDRAFT_FEE_RECEIVABLE"
MAINTENANCE_FEE_INCOME_ACCOUNT = "MAINTENANCE_FEE_INCOME"
MINIMUM_BALANCE_FEE_INCOME_ACCOUNT = "MINIMUM_BALANCE_FEE_INCOME"
ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT = "ANNUAL_MAINTENANCE_FEE_INCOME"
INACTIVITY_FEE_INCOME_ACCOUNT = "INACTIVITY_FEE_INCOME"

DEPOSIT_TIER_RANGES = json_dumps(
    {
        "tier1": {"min": 0, "max": 3000.00},
        "tier2": {"min": 3000.00, "max": 5000.00},
        "tier3": {"min": 5000.00, "max": 7500.00},
        "tier4": {"min": 7500.00, "max": 15000.00},
        "tier5": {"min": 15000.00},
    }
)
DEPOSIT_INTEREST_RATE_TIERS_POSITIVE = json_dumps(
    {
        "tier1": "0.03",
        "tier2": "0.04",
        "tier3": "0.02",
        "tier4": "0.00",
        "tier5": "0.01",
    }
)
DEPOSIT_INTEREST_RATE_TIERS_NEGATIVE = json_dumps(
    {
        "tier1": "-0.03",
        "tier2": "-0.04",
        "tier3": "-0.02",
        "tier4": "0",
        "tier5": "-0.035",
    }
)

DEPOSIT_INTEREST_RATE_TIERS_MIXED = json_dumps(
    {
        "tier1": "0.03",
        "tier2": "0.04",
        "tier3": "-0.02",
        "tier4": "0",
        "tier5": "-0.035",
    }
)

PROMOTIONAL_MAINTENANCE_FEE = "PROMOTIONAL_MAINTENANCE_FEE"
MAINTENANCE_FEE_MONTHLY = json_dumps(
    {
        "US_SAVINGS_ACCOUNT_TIER_UPPER": "10",
        "US_SAVINGS_ACCOUNT_TIER_MIDDLE": "20",
        "US_SAVINGS_ACCOUNT_TIER_LOWER": "30",
    }
)
PROMOTIONAL_MAINTENANCE_FEE_MONTHLY = json_dumps(
    {
        "US_SAVINGS_ACCOUNT_TIER_UPPER": "5",
        "US_SAVINGS_ACCOUNT_TIER_MIDDLE": "10",
        "US_SAVINGS_ACCOUNT_TIER_LOWER": "15",
    }
)


class CheckingAccountTest(ContractTest):
    contract_file = CONTRACT_FILE
    side = Tside.LIABILITY
    linked_contract_modules = {
        "interest": {
            "path": INTEREST_MODULE_FILE,
        },
        "utils": {
            "path": UTILS_MODULE_FILE,
        },
    }
    default_denom = DEFAULT_DENOMINATION

    def account_balances(
        self,
        dt=DEFAULT_DATE,
        balance_defs: Optional[List[Dict[str, str]]] = None,
        denomination=DEFAULT_DENOMINATION,
        accrued_overdraft=Decimal(0),
        default_committed=Decimal(0),
        accrued_deposit_payable=Decimal(0),
        accrued_deposit_receivable=Decimal(0),
        overdraft_fee=Decimal(0),
        accrued_incoming=Decimal(0),
        accrued_outgoing=Decimal(0),
        default_pending_incoming=Decimal(0),
        default_pending_outgoing=Decimal(0),
    ) -> List[Tuple[datetime, BalanceDefaultDict]]:
        balance_dict = {
            balance_dimensions(denomination=denomination): Balance(net=default_committed),
            balance_dimensions(
                denomination=denomination, address=ACCRUED_OVERDRAFT_RECEIVABLE
            ): Balance(net=accrued_overdraft),
            balance_dimensions(denomination=denomination, address=ACCRUED_DEPOSIT_PAYABLE): Balance(
                net=accrued_deposit_payable
            ),
            balance_dimensions(denomination=denomination, address=ACCRUED_OUTGOING): Balance(
                net=accrued_outgoing
            ),
            balance_dimensions(denomination=denomination, address=ACCRUED_INCOMING): Balance(
                net=accrued_incoming
            ),
            balance_dimensions(denomination=denomination, phase=Phase.PENDING_IN): Balance(
                net=default_pending_incoming
            ),
            balance_dimensions(denomination=denomination, phase=Phase.PENDING_OUT): Balance(
                net=default_pending_outgoing
            ),
            balance_dimensions(denomination=denomination, phase=Phase.COMMITTED): Balance(
                net=default_committed
            ),
            balance_dimensions(
                denomination=denomination, address=ACCRUED_DEPOSIT_RECEIVABLE
            ): Balance(net=accrued_deposit_receivable),
            balance_dimensions(
                denomination=denomination, address=ACCRUED_OVERDRAFT_FEE_RECEIVABLE
            ): Balance(net=overdraft_fee),
        }

        balance_default_dict = BalanceDefaultDict(lambda: Balance(net=Decimal(0)), balance_dict)
        balance_defs_dict = self.init_balances(dt, balance_defs)[0][1]
        return [(dt, balance_default_dict + balance_defs_dict)]

    def _maintenance_fee_setup_and_run(
        self,
        event_type,
        default_committed=Decimal(0),
        effective_time=DEFAULT_DATE,
        monthly_fee=Decimal(0),
        annual_fee=Decimal(0),
        flags=None,
        client_transaction=None,
        contract_modules=None,
    ):
        flags = flags or []
        balance_ts = self.account_balances(
            dt=effective_time - relativedelta(months=1), default_committed=default_committed
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            account_inactivity_fee=Decimal(0),
            maintenance_fee_annual=annual_fee,
            minimum_balance_fee=Decimal(0),
            tier_names=json_dumps(["Z"]),
            maintenance_fee_monthly=json_dumps({"Z": str(monthly_fee)}),
            minimum_balance_threshold=json_dumps({"Z": "1500"}),
            minimum_combined_balance_threshold=json_dumps({"Z": "5000"}),
            minimum_deposit_threshold=json_dumps({"Z": "500"}),
            fees_application_day=1,
            fees_application_hour=0,
            fees_application_minute=0,
            fees_application_second=0,
            flags=flags,
            contract_modules=contract_modules,
            client_transaction=client_transaction,
            maintenance_fee_income_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
            annual_maintenance_fee_income_account=ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type=event_type,
            effective_date=effective_time,
        )
        return mock_vault

    def test_pre_posting_code_rejects_postings_in_wrong_denomination(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(2000)
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_auth(denomination="HKD", amount="1")],
        )
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="GBP",
            additional_denominations=ADDITIONAL_DENOMINATIONS,
        )

        with self.assertRaises(Rejected) as e:
            self.run_function("pre_posting_code", mock_vault, test_postings, effective_time)

        self.assertEqual(e.exception.reason_code, RejectedReason.WRONG_DENOMINATION)

    def test_pre_posting_code_rejects_postings_over_standard_overdraft_limit(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(0)
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_auth(denomination=DEFAULT_DENOMINATION, amount="1000")
            ],
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="GBP",
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            standard_overdraft_limit=900,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal", '
            '"3123": "eCommerce"}',
            optional_standard_overdraft_coverage='["ATM withdrawal", "eCommerce"]',
        )

        with self.assertRaises(Rejected) as e:
            self.run_function("pre_posting_code", mock_vault, test_postings, effective_time)

        self.assertEqual(str(e.exception), "Posting exceeds standard_overdraft_limit.")
        self.assertEqual(e.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)

    def test_pre_posting_code_allows_credit_postings_even_if_total_is_over_standard_overdraft_limit(
        self,
    ):
        effective_time = datetime(2019, 1, 1)
        accrued_overdraft = Decimal(0)
        default_committed = Decimal(-200)
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
        )

        posting_instructions = [
            self.inbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION, amount="50", value_timestamp=effective_time
            )
        ]

        pib, client_transaction, _ = self.pib_and_cts_for_posting_instructions(
            effective_time, posting_instructions_groups=[posting_instructions]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            standard_overdraft_limit=100,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
            optional_standard_overdraft_coverage='["ATM withdrawal", "eCommerce"]',
            client_transaction=client_transaction,
        )

        try:
            self.run_function("pre_posting_code", mock_vault, pib, effective_time)
        except Exception as e:
            self.fail(f"Exception was raised: {e}")

    def test_pre_posting_code_accepts_correct_postings(self):
        effective_time = datetime(2019, 1, 1)
        accrued_overdraft = Decimal(0)
        default_committed = Decimal(0)
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
        )

        posting_instructions = [
            self.outbound_auth(
                denomination=DEFAULT_DENOMINATION, amount="100", value_timestamp=effective_time
            )
        ]

        pib, client_transaction, _ = self.pib_and_cts_for_posting_instructions(
            effective_time, posting_instructions_groups=[posting_instructions]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            standard_overdraft_limit=900,
            daily_atm_withdrawal_limit=100,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
            optional_standard_overdraft_coverage='["ATM withdrawal", "eCommerce"]',
            client_transaction=client_transaction,
        )

        try:
            self.run_function("pre_posting_code", mock_vault, pib, effective_time)
        except Exception as e:
            self.fail(f"Exception was raised: {e}")

    def test_pre_posting_code_overdraft_coverage(self):
        effective_time = datetime(2021, 1, 1)
        # auth amount will exceed available balance of 90
        default_committed = Decimal(200)
        auth_amount = Decimal("110")
        balance_ts = self.account_balances(
            effective_time,
            default_committed=default_committed,
            default_pending_outgoing=Decimal(-100),
            denomination="USD",
        )

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=effective_time,
            posting_instructions_groups=[
                [
                    self.outbound_auth(
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        amount=auth_amount,
                        denomination="USD",
                        value_timestamp=effective_time,
                        instruction_details={"transaction_code": "6011"},
                    )
                ]
            ],
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transactions,
            denomination="USD",
            additional_denominations=json_dumps(["GBP", "EUR"]),
            standard_overdraft_limit=1000,
            daily_atm_withdrawal_limit=500,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal", '
            '"3123": "eCommerce"}',
            optional_standard_overdraft_coverage='["ATM withdrawal", "eCommerce"]',
            flags=[],
        )

        with self.assertRaises(Rejected, msg="ATM posting rejected when no coverage flag set") as e:
            self.run_function("pre_posting_code", mock_vault, pib, effective_time)

        self.assertEqual(
            str(e.exception),
            "Posting requires standard overdraft yet transaction type is not covered.",
        )
        self.assertEqual(e.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)

        # Now run pre_posting_code again, this time with the coverage flag set
        mock_vault_with_flag = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transactions,
            denomination="USD",
            additional_denominations=json_dumps(["GBP", "EUR"]),
            standard_overdraft_limit=1000,
            daily_atm_withdrawal_limit=500,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal", '
            '"3123": "eCommerce"}',
            optional_standard_overdraft_coverage='["ATM withdrawal", "eCommerce"]',
            flags=[STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG],
        )
        # This will error with an exception if pre_posting_code does not accept the posting
        self.run_function("pre_posting_code", mock_vault_with_flag, pib, effective_time)

    def test_posting_over_transaction_type_daily_limit_rejected(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(2000)
        denomination = DEFAULT_DENOMINATION
        auth_amount = Decimal("1000")

        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=effective_time,
            posting_instructions_groups=[
                [
                    self.outbound_auth(
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        amount=auth_amount,
                        denomination=denomination,
                        value_timestamp=effective_time,
                        instruction_details={"transaction_code": "6011"},
                    )
                ]
            ],
        )

        daily_atm_withdrawal_limit = Decimal(100)
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transactions,
            denomination=DEFAULT_DENOMINATION,
            daily_atm_withdrawal_limit=daily_atm_withdrawal_limit,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "_check_transaction_type_limits",
                vault=mock_vault,
                vault_object=mock_vault,
                postings=pib,
                client_transactions=client_transactions,
                denomination=denomination,
                effective_date=effective_time,
            )

            expected_rejection_error = (
                "Transaction would cause the ATM"
                " daily withdrawal limit of %s %s to be exceeded."
                % (daily_atm_withdrawal_limit, denomination),
            )

            self.assertEqual(str(e.exception), expected_rejection_error)

    def test_additional_denom_transaction_type_has_no_affect_on_limits(self):
        """
        Transactions performed in a different currency will have no impact on transaction
        Limits set by the contract
        """
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(2000)
        denomination = DEFAULT_DENOMINATION
        auth_amount = Decimal("1000")

        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=effective_time,
            posting_instructions_groups=[
                [
                    self.outbound_auth(
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        amount=auth_amount,
                        denomination="USD",
                        value_timestamp=effective_time - timedelta(hours=1),
                        instruction_details={"transaction_code": "6011"},
                    ),
                    self.settle_outbound_auth(
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        unsettled_amount=auth_amount,
                        denomination="USD",
                        final=True,
                        value_timestamp=effective_time,
                        instruction_details={"transaction_code": "6011"},
                    ),
                ]
            ],
        )

        daily_atm_withdrawal_limit = Decimal(100)
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transactions,
            denomination=DEFAULT_DENOMINATION,
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            daily_atm_withdrawal_limit=daily_atm_withdrawal_limit,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
        )

        self.run_function(
            "_check_transaction_type_limits",
            vault=mock_vault,
            vault_object=mock_vault,
            postings=pib,
            client_transactions=client_transactions,
            denomination=denomination,
            effective_date=effective_time,
        )

    def test_credit_transaction_over_transaction_type_daily_limit_accepted(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(2000)
        denomination = DEFAULT_DENOMINATION

        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=effective_time,
            posting_instructions_groups=[
                [
                    self.inbound_hard_settlement(
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        amount="1000",
                        denomination="USD",
                        value_timestamp=effective_time,
                        instruction_details={"transaction_code": "6011"},
                    )
                ]
            ],
        )

        daily_atm_withdrawal_limit = Decimal(100)
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transactions,
            denomination=DEFAULT_DENOMINATION,
            daily_atm_withdrawal_limit=daily_atm_withdrawal_limit,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
        )

        self.run_function(
            "_check_transaction_type_limits",
            vault=mock_vault,
            vault_object=mock_vault,
            postings=pib,
            client_transactions=client_transactions,
            denomination=denomination,
            effective_date=effective_time,
        )

    def test_postings_for_unknown_transaction_type_not_limited(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("20000")
        hard_settle_amount = Decimal("10000")

        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=effective_time,
            posting_instructions_groups=[
                [
                    self.outbound_hard_settlement(
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        amount=hard_settle_amount,
                        denomination=DEFAULT_DENOMINATION,
                        value_timestamp=effective_time,
                        instruction_details={"transaction_code": "1234"},
                    )
                ]
            ],
        )

        daily_atm_withdrawal_limit = Decimal(100)
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transactions,
            denomination=DEFAULT_DENOMINATION,
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            fee_free_overdraft_limit=Decimal(0),
            standard_overdraft_limit=Decimal(100),
            daily_atm_withdrawal_limit=daily_atm_withdrawal_limit,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
        )

        self.run_function("pre_posting_code", mock_vault, pib, effective_time)

    def test_postings_of_mixed_transaction_types_accepted(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("20000")
        daily_atm_withdrawal_limit = Decimal(100)
        not_atm_amount = Decimal("10000")
        atm_amount = daily_atm_withdrawal_limit

        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        client_id_2 = "client_ID_2"
        client_transaction_id_2 = "CT_ID_2"

        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=effective_time,
            posting_instructions_groups=[
                [
                    self.outbound_hard_settlement(
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        amount=not_atm_amount,
                        denomination=DEFAULT_DENOMINATION,
                        value_timestamp=effective_time,
                        instruction_details={"transaction_code": "1234"},
                    ),
                ],
                [
                    self.outbound_hard_settlement(
                        client_transaction_id=client_transaction_id_2,
                        client_id=client_id_2,
                        denomination=DEFAULT_DENOMINATION,
                        amount=atm_amount,
                        value_timestamp=effective_time,
                        instruction_details={"transaction_code": "6011"},
                    ),
                ],
            ],
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transactions,
            denomination=DEFAULT_DENOMINATION,
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            fee_free_overdraft_limit=Decimal(0),
            standard_overdraft_limit=Decimal(100),
            daily_atm_withdrawal_limit=daily_atm_withdrawal_limit,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
        )

        self.run_function("pre_posting_code", mock_vault, pib, effective_time)

    def test_scheduled_code_does_not_accrue_when_balance_lt_buffer(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(-40)
        accrued_overdraft = Decimal(0)
        tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "200", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "-1", "B": "1", "C": "-1"})

        balance_ts = self.account_balances(
            effective_time - timedelta(days=1),
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=tier_names,
            flags=["B"],
            interest_free_buffer=tiered_param_od_buffer_amount,
            overdraft_interest_rate=Decimal(0.1555),
            standard_overdraft_daily_fee=Decimal(50),
            standard_overdraft_fee_cap=Decimal(80),
            fee_free_overdraft_limit=Decimal(50),
            standard_overdraft_limit=Decimal(900),
            deposit_tier_ranges=DEPOSIT_TIER_RANGES,
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            overdraft_interest_free_buffer_days=tiered_param_od_buffer_period,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

        mock_vault.instruct_posting_batch.assert_not_called()

    def test_scheduled_code_accrues_interest_at_eod(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("-200")
        accrued_overdraft = Decimal("200")
        expected_standard_overdraft_daily_fee = Decimal("50")
        overdraft_interest_rate = Decimal("0.15695")
        daily_rate = overdraft_interest_rate / 365
        daily_rate_percent = daily_rate * 100
        tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "50", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "-1", "B": "1", "C": "-1"})
        expected_interest_accrual = Decimal("0.06450").copy_abs().quantize(Decimal(".00001"))
        balance_ts = self.account_balances(
            effective_time - timedelta(days=1),
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
            overdraft_fee=expected_standard_overdraft_daily_fee,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=tier_names,
            flags=["A"],
            interest_free_buffer=tiered_param_od_buffer_amount,
            overdraft_interest_rate=overdraft_interest_rate,
            standard_overdraft_daily_fee=Decimal("50"),
            standard_overdraft_fee_cap=Decimal("80"),
            fee_free_overdraft_limit=Decimal("1000"),
            standard_overdraft_limit=Decimal("900"),
            overdraft_interest_free_buffer_days=tiered_param_od_buffer_period,
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_OVERDRAFT_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                        f" on balance of {default_committed + 50:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
                call(
                    amount=expected_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_GL_OVERDRAFT_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                        f" on balance of {default_committed + 50:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                f"ACCRUE_INTEREST_CUSTOMER_OVERDRAFT_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"ACCRUE_INTEREST_GL_OVERDRAFT_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_scheduled_code_accrues_interest_on_decimal_balance(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("-50.01")
        accrued_overdraft = Decimal("0")
        expected_standard_overdraft_daily_fee = Decimal("50")
        overdraft_interest_rate = Decimal("0.15695")
        tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "50", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "-1", "B": "1", "C": "-1"})

        balance_ts = self.account_balances(
            effective_time - timedelta(days=1),
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
            overdraft_fee=expected_standard_overdraft_daily_fee,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=tier_names,
            flags=["A"],
            interest_free_buffer=tiered_param_od_buffer_amount,
            overdraft_interest_rate=overdraft_interest_rate,
            standard_overdraft_daily_fee=Decimal("50"),
            standard_overdraft_fee_cap=Decimal("80"),
            fee_free_overdraft_limit=Decimal("40"),
            standard_overdraft_limit=Decimal("900"),
            overdraft_interest_free_buffer_days=tiered_param_od_buffer_period,
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
            overdraft_fee_receivable_account=OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("50"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_OVERDRAFT_FEE_RECEIVABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_FEES_CUSTOMER_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued fee Standard Overdraft.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
                call(
                    amount=Decimal("50"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_FEES_GL_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued fee Standard Overdraft.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                f"ACCRUE_FEES_CUSTOMER_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"ACCRUE_FEES_GL_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_scheduled_code_charges_fee_at_eod(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(-200)
        accrued_overdraft = Decimal(200)
        tier_names = json_dumps(["FLAG_A", "FLAG_B", "FLAG_C"])
        tiered_param_od_buffer_amount = json_dumps(
            {"FLAG_A": "50", "FLAG_B": "300", "FLAG_C": "500"}
        )
        tiered_param_od_buffer_period = json_dumps({"FLAG_A": "-1", "FLAG_B": "1", "FLAG_C": "-1"})
        expected_standard_overdraft_daily_fee = Decimal(50)
        overdraft_interest_rate = Decimal("0.00")
        balance_ts = self.account_balances(
            effective_time - timedelta(days=1),
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
            overdraft_fee=expected_standard_overdraft_daily_fee,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=tier_names,
            flags=["FLAG_B"],
            interest_free_buffer=tiered_param_od_buffer_amount,
            overdraft_interest_rate=overdraft_interest_rate,
            standard_overdraft_daily_fee=Decimal(50),
            standard_overdraft_fee_cap=Decimal(80),
            fee_free_overdraft_limit=Decimal(100),
            standard_overdraft_limit=Decimal(100),
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            overdraft_interest_free_buffer_days=tiered_param_od_buffer_period,
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
            overdraft_fee_receivable_account=OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_standard_overdraft_daily_fee,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_OVERDRAFT_FEE_RECEIVABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_FEES_CUSTOMER_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued fee Standard Overdraft.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
                call(
                    amount=expected_standard_overdraft_daily_fee,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_FEES_GL_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued fee Standard Overdraft.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                f"ACCRUE_FEES_CUSTOMER_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"ACCRUE_FEES_GL_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_monthly_maintenance_fee_not_applied_if_zero(self):
        expected_maintenance_fee = Decimal(0)
        effective_time = datetime(2020, 2, 1)
        mock_vault = self._maintenance_fee_setup_and_run(
            event_type="APPLY_MONTHLY_FEES",
            effective_time=effective_time,
            monthly_fee=expected_maintenance_fee,
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()

        mock_vault.instruct_posting_batch.assert_not_called()

    def test_monthly_maintenance_fee_applied_if_non_zero(self):
        expected_maintenance_fee = Decimal(25)
        effective_time = datetime(2020, 2, 1)
        mock_vault = self._maintenance_fee_setup_and_run(
            event_type="APPLY_MONTHLY_FEES",
            effective_time=effective_time,
            monthly_fee=expected_maintenance_fee,
            client_transaction={},
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_maintenance_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MAINTENANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_MOCK_HOOK_GBP",
            ],
            effective_date=effective_time,
        )

    def test_monthly_maintenance_fee_not_applied_if_min_daily_balance_waive_criteria_met(
        self,
    ):
        expected_maintenance_fee = Decimal(25)
        effective_time = datetime(2020, 2, 1)
        mock_vault = self._maintenance_fee_setup_and_run(
            event_type="APPLY_MONTHLY_FEES",
            effective_time=effective_time,
            monthly_fee=expected_maintenance_fee,
            default_committed=Decimal(1500),
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_monthly_maintenance_fee_applied_if_min_daily_balance_waive_criteria_not_met(
        self,
    ):
        expected_maintenance_fee = Decimal(25)
        effective_time = datetime(2020, 2, 1)
        mock_vault = self._maintenance_fee_setup_and_run(
            event_type="APPLY_MONTHLY_FEES",
            effective_time=effective_time,
            monthly_fee=expected_maintenance_fee,
            default_committed=Decimal(1499),
            client_transaction={},
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_maintenance_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MAINTENANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_MOCK_HOOK_GBP",
            ],
            effective_date=effective_time,
        )

    def test_monthly_maintenance_fee_ignores_combined_balance_waive_criteria(self):
        expected_maintenance_fee = Decimal(25)
        effective_time = datetime(2020, 2, 1)

        balance_ts = self.account_balances(
            dt=effective_time - relativedelta(months=1), default_committed=Decimal(1100)
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            account_inactivity_fee=Decimal(0),
            maintenance_fee_annual=Decimal(0),
            minimum_balance_fee=Decimal(0),
            tier_names=json_dumps(["Z"]),
            maintenance_fee_monthly=json_dumps({"Z": str(expected_maintenance_fee)}),
            minimum_balance_threshold=json_dumps({"Z": "1500"}),
            minimum_combined_balance_threshold=json_dumps({"Z": "1000"}),
            minimum_deposit_threshold=json_dumps({"Z": "500"}),
            fees_application_day=1,
            fees_application_hour=0,
            fees_application_minute=0,
            fees_application_second=0,
            flags=[],
            client_transaction={},
            maintenance_fee_income_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_maintenance_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MAINTENANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_MOCK_HOOK_GBP",
            ],
            effective_date=effective_time,
        )

    def test_monthly_maintenance_fee_not_applied_if_min_deposit_threshold_waive_criteria_met(
        self,
    ):
        expected_maintenance_fee = Decimal(25)
        effective_time = datetime(2020, 2, 1)

        # Build client transactions
        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        _, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=effective_time,
            posting_instructions_groups=[
                [
                    self.inbound_hard_settlement(
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        amount="500",
                        value_timestamp=effective_time - timedelta(days=10),
                    ),
                ],
            ],
        )

        mock_vault = self._maintenance_fee_setup_and_run(
            event_type="APPLY_MONTHLY_FEES",
            effective_time=effective_time,
            monthly_fee=expected_maintenance_fee,
            client_transaction=client_transactions,
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_monthly_maintenance_fee_applied_if_min_deposit_threshold_waive_criteria_not_met(
        self,
    ):
        expected_maintenance_fee = Decimal(25)
        effective_time = datetime(2020, 2, 1)

        # Build client transactions
        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"
        _, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=effective_time,
            posting_instructions_groups=[
                [
                    self.inbound_hard_settlement(
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        amount="499",
                        value_timestamp=effective_time - timedelta(days=10),
                    ),
                ],
            ],
        )

        mock_vault = self._maintenance_fee_setup_and_run(
            event_type="APPLY_MONTHLY_FEES",
            effective_time=effective_time,
            monthly_fee=expected_maintenance_fee,
            client_transaction=client_transactions,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_maintenance_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MAINTENANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_MOCK_HOOK_GBP",
            ],
            effective_date=effective_time,
        )

    def test_monthly_mean_balance_returns_correct_mean_balance_single(self):
        effective_time = datetime(2020, 5, 1)

        # 5 days at 0, in 30 day month
        balance_ts = self.account_balances(dt=datetime(2020, 4, 1), default_committed=Decimal(0))
        # 20 days at 500, in 30 day month
        balance_ts.extend(
            self.account_balances(dt=datetime(2020, 4, 6), default_committed=Decimal(500))
        )
        # 5 days at 1000, in 30 day month
        balance_ts.extend(
            self.account_balances(dt=datetime(2020, 4, 26), default_committed=Decimal(1000))
        )

        mock_vault = self.create_mock(creation_date=datetime(2020, 1, 1), balance_ts=balance_ts)

        monthly_mean_balance = self.run_function(
            "_monthly_mean_balance",
            mock_vault,
            vault=mock_vault,
            denomination=DEFAULT_DENOMINATION,
            effective_date=effective_time,
        )

        expected_monthly_mean_balance = Decimal(500)

        self.assertEqual(monthly_mean_balance, expected_monthly_mean_balance)

    def test_monthly_mean_balance_returns_correct_mean_balance_single_fraction(self):
        effective_time = datetime(2020, 5, 1)

        # 1 days at 0, in 30 day month
        balance_ts = self.account_balances(dt=datetime(2020, 4, 1), default_committed=Decimal(0))
        # 20 days at 500, in 30 day month
        balance_ts.extend(
            self.account_balances(dt=datetime(2020, 4, 2), default_committed=Decimal(500))
        )
        # 5 days at 1000, in 30 day month
        balance_ts.extend(
            self.account_balances(dt=datetime(2020, 4, 26), default_committed=Decimal(1000))
        )

        mock_vault = self.create_mock(creation_date=datetime(2020, 1, 1), balance_ts=balance_ts)

        monthly_mean_balance = self.run_function(
            "_monthly_mean_balance",
            mock_vault,
            vault=mock_vault,
            denomination=DEFAULT_DENOMINATION,
            effective_date=effective_time,
        )

        expected_monthly_mean_balance = Decimal("566.6666666666666666666666667")

        self.assertEqual(monthly_mean_balance, expected_monthly_mean_balance)

    def test_sum_deposit_transactions_returns_correct_sum_with_mixed_transactions(self):
        effective_time = datetime(2020, 3, 1)

        # Build client transactions
        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"
        client_id_2 = "client_ID_2"
        client_transaction_id_2 = "CT_ID_2"
        client_id_3 = "client_ID_3"
        client_transaction_id_3 = "CT_ID_3"
        client_id_4 = "client_ID_4"
        client_transaction_id_4 = "CT_ID_4"
        client_id_5 = "client_ID_5"
        client_transaction_id_5 = "CT_ID_5"

        _, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=effective_time,
            posting_instructions_groups=[
                [
                    # Should be ignored - before window start
                    self.inbound_hard_settlement(
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        amount="100",
                        value_timestamp=effective_time - timedelta(days=32),
                    ),
                ],
                [
                    # Should be counted
                    self.inbound_hard_settlement(
                        client_transaction_id=client_transaction_id_2,
                        client_id=client_id_2,
                        amount="200",
                        value_timestamp=effective_time - timedelta(days=20),
                    ),
                ],
                [
                    # Should be ignored - withdrawal
                    self.outbound_hard_settlement(
                        client_transaction_id=client_transaction_id_3,
                        client_id=client_id_3,
                        amount="300",
                        value_timestamp=effective_time - timedelta(days=10),
                    ),
                ],
                [
                    # Should be counted
                    self.inbound_hard_settlement(
                        client_transaction_id=client_transaction_id_4,
                        client_id=client_id_4,
                        amount="400",
                        value_timestamp=effective_time - timedelta(days=5),
                    ),
                ],
                [
                    # Should be ignored - unsettled
                    self.inbound_auth(
                        client_transaction_id=client_transaction_id_5,
                        client_id=client_id_5,
                        amount="500",
                        value_timestamp=effective_time,
                    ),
                ],
            ],
        )

        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            client_transaction=client_transactions,
        )

        deposit_sum = self.run_function(
            "_sum_deposit_transactions",
            mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
        )

        # txn_2 (200) + txn_4 (400)
        expected_deposit_sum = Decimal(600)

        self.assertEqual(deposit_sum, expected_deposit_sum)

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

    def test_account_under_balance_fee_not_applied_if_mean_balance_above_threshold(
        self,
    ):
        effective_time = datetime(2020, 2, 1)
        expected_minimum_balance_fee = Decimal(100)

        period_start = effective_time - relativedelta(months=1)
        balance_ts = self.account_balances(dt=period_start, default_committed=Decimal("1500"))

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=json_dumps(["Z"]),
            maintenance_fee_monthly=json_dumps({"Z": "0"}),
            minimum_balance_threshold=json_dumps({"Z": "1500"}),
            minimum_combined_balance_threshold=json_dumps({"Z": "5000"}),
            minimum_deposit_threshold=json_dumps({"Z": "500"}),
            minimum_balance_fee=Decimal(expected_minimum_balance_fee),
            fees_application_day=1,
            fees_application_hour=23,
            fees_application_minute=0,
            fees_application_second=0,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

        mock_vault.instruct_posting_batch.assert_not_called()

    def test_account_under_balance_fee_applied_if_mean_balance_is_zero(self):
        effective_time = datetime(2020, 3, 15)
        expected_minimum_balance_fee = Decimal(100)

        period_start = effective_time - relativedelta(months=1)

        balance_ts = self.account_balances(dt=period_start, default_committed=Decimal("0"))

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=json_dumps(["X", "Y", "Z"]),
            maintenance_fee_monthly=json_dumps({"Z": "0"}),
            minimum_balance_threshold=json_dumps({"Z": "100"}),
            minimum_combined_balance_threshold=json_dumps({"Z": "5000"}),
            minimum_deposit_threshold=json_dumps({"Z": "500"}),
            minimum_balance_fee=Decimal(expected_minimum_balance_fee),
            fees_application_day=1,
            fees_application_hour=23,
            fees_application_minute=0,
            fees_application_second=0,
            minimum_balance_fee_income_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_minimum_balance_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_FEES_MEAN_BALANCE_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_APPLY_MONTHLY_FEES_MEAN_BALANCE_MOCK_HOOK_GBP",
            ],
            effective_date=effective_time,
        )

    def test_account_mean_balance_fee_period_with_fee_charged(self):
        fee_day = 28
        fee_hour = 23
        fee_minute = 0
        fee_second = 0
        anniversary = datetime(2020, 2, 1)
        effective_time = anniversary.replace(hour=fee_hour, minute=fee_minute, second=fee_second)
        expected_period_start = datetime(2020, 1, 1)
        expected_period_end = datetime(2020, 1, 31, fee_hour, fee_minute, fee_second)
        expected_minimum_balance_fee = Decimal(100)
        expected_minimum_balance_threshold = Decimal(100)

        balance_time = expected_period_start - relativedelta(days=2)
        balance_ts = []
        # The mean balance is sampled daily for a month at the fee application time. Set up balances
        # which are:
        # - just below the balance threshold during the current sampling month
        # - well above the balance threshold for two days before and after the sampling month
        # such that if the sampling month included the outlying balances the test would fail by
        # the mean being above the threshold and not charging the fee.
        while balance_time < expected_period_end + relativedelta(days=2):
            if expected_period_start <= balance_time <= expected_period_end:
                balance = self.account_balances(
                    dt=balance_time,
                    default_committed=expected_minimum_balance_threshold - 1,
                )
            else:
                balance = self.account_balances(
                    dt=balance_time,
                    default_committed=60 * expected_minimum_balance_threshold,
                )
            balance_ts.extend(balance)
            balance_time += relativedelta(minutes=15)

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=json_dumps(["Z"]),
            maintenance_fee_monthly=json_dumps({"Z": "0"}),
            minimum_balance_threshold=json_dumps({"Z": "100"}),
            minimum_combined_balance_threshold=json_dumps({"Z": "5000"}),
            minimum_deposit_threshold=json_dumps({"Z": "500"}),
            minimum_balance_fee=expected_minimum_balance_fee,
            fees_application_day=fee_day,
            fees_application_hour=fee_hour,
            fees_application_minute=fee_minute,
            fees_application_second=fee_second,
            minimum_balance_fee_income_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_minimum_balance_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_FEES_MEAN_BALANCE_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_APPLY_MONTHLY_FEES_MEAN_BALANCE_MOCK_HOOK_GBP",
            ],
            effective_date=effective_time,
        )

    def test_account_mean_balance_fee_period_with_fee_not_charged(self):
        fee_day = 28
        fee_hour = 23
        fee_minute = 0
        fee_second = 0
        anniversary = datetime(2020, 2, 1)
        effective_time = anniversary.replace(hour=fee_hour, minute=fee_minute, second=fee_second)
        expected_period_start = datetime(2020, 1, 1)
        expected_period_end = datetime(2020, 1, 31, fee_hour, fee_minute, fee_second)
        expected_minimum_balance_fee = Decimal(100)
        expected_minimum_balance_threshold = Decimal(100)

        balance_time = expected_period_start - relativedelta(days=2)
        balance_ts = []
        # The mean balance is sampled daily for a month at the fee application time. Set up balances
        # which are:
        # - at the balance threshold during the current sampling month
        # - well below the balance threshold for two days before and after the sampling month
        # such that if the sampling month included the outlying balances the test would fail by
        # the mean being below the threshold and charging the fee.
        while balance_time < expected_period_end + relativedelta(days=2):
            if expected_period_start <= balance_time <= expected_period_end:
                balance = self.account_balances(
                    dt=balance_time, default_committed=expected_minimum_balance_threshold
                )
            else:
                balance = self.account_balances(
                    dt=balance_time, default_committed=Decimal("-100000")
                )
            balance_ts.extend(balance)
            balance_time += relativedelta(hours=6)

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=json_dumps(["Z"]),
            maintenance_fee_monthly=json_dumps({"Z": "0"}),
            minimum_balance_threshold=json_dumps({"Z": "100"}),
            minimum_combined_balance_threshold=json_dumps({"Z": "5000"}),
            minimum_deposit_threshold=json_dumps({"Z": "500"}),
            minimum_balance_fee=expected_minimum_balance_fee,
            fees_application_day=fee_day,
            fees_application_hour=fee_hour,
            fees_application_minute=fee_minute,
            fees_application_second=fee_second,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

        mock_vault.instruct_posting_batch.assert_not_called()

    def test_account_under_balance_fee_charged_with_mid_month_period_and_sampling_midnight(
        self,
    ):
        fee_day = 28
        fee_hour = 0
        fee_minute = 0
        fee_second = 0
        anniversary = datetime(2019, 3, 15)
        effective_time = anniversary.replace(hour=fee_hour, minute=fee_minute, second=fee_second)
        expected_period_start = datetime(2019, 2, 15)
        expected_period_end = datetime(2019, 3, 14, fee_hour, fee_minute, fee_second)
        expected_minimum_balance_fee = Decimal(100)
        expected_minimum_balance_threshold = Decimal(100)

        balance_time = expected_period_start - relativedelta(days=2)
        balance_ts = []
        # The mean balance is sampled daily for a month at the fee application time. Set up balances
        # which are:
        # - just below the balance threshold during the current sampling month
        # - well above the balance threshold for two days before and after the sampling month
        # such that if the sampling month included the outlying balances the test would fail by
        # the mean being above the threshold and not charging the fee.
        while balance_time < expected_period_end + relativedelta(days=2):
            if expected_period_start <= balance_time <= expected_period_end:
                balance = self.account_balances(
                    dt=balance_time,
                    default_committed=expected_minimum_balance_threshold - 1,
                )
            else:
                balance = self.account_balances(
                    dt=balance_time,
                    default_committed=60 * expected_minimum_balance_threshold,
                )
            balance_ts.extend(balance)
            balance_time += relativedelta(minutes=15)

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            account_inactivity_fee=Decimal(10),
            tier_names=json_dumps(["Z"]),
            maintenance_fee_monthly=json_dumps({"Z": "0"}),
            minimum_balance_threshold=json_dumps({"Z": "1500"}),
            minimum_combined_balance_threshold=json_dumps({"Z": "5000"}),
            minimum_deposit_threshold=json_dumps({"Z": "500"}),
            minimum_balance_fee=expected_minimum_balance_fee,
            fees_application_day=fee_day,
            fees_application_hour=fee_hour,
            fees_application_minute=fee_minute,
            fees_application_second=fee_second,
            minimum_balance_fee_income_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_minimum_balance_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_FEES_MEAN_BALANCE_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_APPLY_MONTHLY_FEES_MEAN_BALANCE_MOCK_HOOK_GBP",
            ],
            effective_date=effective_time,
        )

    def test_account_under_balance_fee_sampling_in_leap_year_february(self):
        fee_day = 28
        fee_hour = 0
        fee_minute = 0
        fee_second = 0
        anniversary = datetime(2020, 3, 15)
        effective_time = anniversary.replace(hour=fee_hour, minute=fee_minute, second=fee_second)
        expected_period_start = datetime(2020, 2, 15)
        expected_period_end = datetime(2020, 3, 14, fee_hour, fee_minute, fee_second)
        expected_minimum_balance_fee = Decimal(100)
        expected_minimum_balance_threshold = Decimal(100)

        balance_time = expected_period_start - relativedelta(days=2)
        balance_ts = []
        # The mean balance is sampled daily for a month at the fee application time. Set up balances
        # which are:
        # - just below the balance threshold during the current sampling month
        # - well above the balance threshold for two days before and after the sampling month
        # such that if the sampling month included the outlying balances the test would fail by
        # the mean being above the threshold and not charging the fee.
        while balance_time < expected_period_end + relativedelta(days=2):
            if expected_period_start <= balance_time <= expected_period_end:
                balance = self.account_balances(
                    dt=balance_time,
                    default_committed=expected_minimum_balance_threshold - 1,
                )
            else:
                balance = self.account_balances(
                    dt=balance_time,
                    default_committed=60 * expected_minimum_balance_threshold,
                )
            balance_ts.extend(balance)
            balance_time += relativedelta(hours=12)

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=json_dumps(["Z"]),
            maintenance_fee_monthly=json_dumps({"Z": "0"}),
            minimum_balance_threshold=json_dumps({"Z": "1500"}),
            minimum_combined_balance_threshold=json_dumps({"Z": "5000"}),
            minimum_deposit_threshold=json_dumps({"Z": "500"}),
            minimum_balance_fee=expected_minimum_balance_fee,
            fees_application_day=fee_day,
            fees_application_hour=fee_hour,
            fees_application_minute=fee_minute,
            fees_application_second=fee_second,
            minimum_balance_fee_income_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_minimum_balance_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_FEES_MEAN_BALANCE_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_APPLY_MONTHLY_FEES_MEAN_BALANCE_MOCK_HOOK_GBP",
            ],
            effective_date=effective_time,
        )

    def test_account_monthly_maintenance_and_minimum_balance_and_overdraft_fee_all_applied(
        self,
    ):
        effective_time = DEFAULT_DATE
        default_committed = Decimal(-10000)
        expected_maintenance_fee = Decimal(10)
        expected_minimum_balance_fee = Decimal(100)
        expected_standard_overdraft_daily_fee = Decimal(50)
        balance_ts = self.account_balances(
            effective_time,
            default_committed=default_committed,
            overdraft_fee=-expected_standard_overdraft_daily_fee,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=json_dumps(["Z"]),
            maintenance_fee_monthly=json_dumps({"Z": str(expected_maintenance_fee)}),
            minimum_balance_threshold=json_dumps({"Z": "1500"}),
            minimum_combined_balance_threshold=json_dumps({"Z": "5000"}),
            minimum_deposit_threshold=json_dumps({"Z": "500"}),
            minimum_balance_fee=Decimal(expected_minimum_balance_fee),
            fees_application_day=1,
            fees_application_hour=23,
            fees_application_minute=0,
            fees_application_second=0,
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            minimum_balance_fee_income_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            overdraft_fee_receivable_account=OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
            maintenance_fee_income_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
            client_transaction={},
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_standard_overdraft_daily_fee,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id="Main account",
                    to_account_address=ACCRUED_OVERDRAFT_FEE_RECEIVABLE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_FEES_CUSTOMER_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Overdraft fees applied.",
                        "event": "APPLY_MONTHLY_FEES",
                    },
                ),
                call(
                    amount=expected_standard_overdraft_daily_fee,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_FEES_GL_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Overdraft fees applied.",
                        "event": "APPLY_MONTHLY_FEES",
                    },
                ),
                call(
                    amount=expected_maintenance_fee,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=MAINTENANCE_FEE_INCOME_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_"
                    f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Monthly maintenance fee",
                        "event": "APPLY_MONTHLY_FEES",
                    },
                ),
                call(
                    amount=expected_minimum_balance_fee,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_FEES_MEAN_BALANCE_"
                    f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Minimum balance fee",
                        "event": "APPLY_MONTHLY_FEES",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_has_calls(
            [
                call(
                    client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
                    effective_date=effective_time,
                    posting_instructions=[
                        f"APPLY_FEES_CUSTOMER_{HOOK_EXECUTION_ID}"
                        f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                        f"APPLY_FEES_GL_{HOOK_EXECUTION_ID}"
                        f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                        "INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_MOCK_HOOK_GBP",
                        "INTERNAL_POSTING_APPLY_MONTHLY_FEES_MEAN_BALANCE_MOCK_HOOK_GBP",
                    ],
                ),
            ]
        )

    def test_account_annual_maintenance_fee_applied(self):
        expected_maintenance_fee = Decimal(10)
        effective_time = DEFAULT_DATE
        mock_vault = self._maintenance_fee_setup_and_run(
            event_type="APPLY_ANNUAL_FEES",
            effective_time=effective_time,
            annual_fee=expected_maintenance_fee,
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_maintenance_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_ANNUAL_FEES_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Annual maintenance fee",
                "event": "APPLY_ANNUAL_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ANNUAL_FEES_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_APPLY_ANNUAL_FEES_MOCK_HOOK_GBP",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_accrues_interest_and_charges_fee_at_eod(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(-200)
        accrued_overdraft = Decimal(200)
        expected_standard_overdraft_daily_fee = Decimal(50)
        overdraft_interest_rate = Decimal("0.15695")
        interest_free_buffer = Decimal("100")
        tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "100", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "-1", "B": "1", "C": "-1"})
        daily_interest_rate = overdraft_interest_rate / 365
        daily_interest_rate_percent = daily_interest_rate * 100

        expected_interest_accrual = Decimal("0.04300").copy_abs().quantize(Decimal(".00001"))

        balance_ts = self.account_balances(
            effective_time - timedelta(days=1),
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
            overdraft_fee=expected_standard_overdraft_daily_fee,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=tier_names,
            flags=["A"],
            interest_free_buffer=tiered_param_od_buffer_amount,
            overdraft_interest_free_buffer_days=tiered_param_od_buffer_period,
            overdraft_interest_rate=overdraft_interest_rate,
            standard_overdraft_daily_fee=Decimal(50),
            standard_overdraft_fee_cap=Decimal(80),
            fee_free_overdraft_limit=Decimal(10),
            standard_overdraft_limit=Decimal(10),
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
            overdraft_fee_receivable_account=OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_OVERDRAFT_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at "
                        f"{daily_interest_rate_percent:0.5f}%"
                        f" on balance of {default_committed + interest_free_buffer:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
                call(
                    amount=expected_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_GL_OVERDRAFT_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at "
                        f"{daily_interest_rate_percent:0.5f}%"
                        f" on balance of {default_committed + interest_free_buffer:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
                call(
                    amount=expected_standard_overdraft_daily_fee,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_OVERDRAFT_FEE_RECEIVABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_FEES_CUSTOMER_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued fee Standard Overdraft.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
                call(
                    amount=expected_standard_overdraft_daily_fee,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_FEES_GL_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued fee Standard Overdraft.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                f"ACCRUE_INTEREST_CUSTOMER_OVERDRAFT_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"ACCRUE_INTEREST_GL_OVERDRAFT_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"ACCRUE_FEES_CUSTOMER_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"ACCRUE_FEES_GL_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_scheduled_code_applies_accrued_overdraft_interest(self):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal(0)
        accrued_overdraft_balance = Decimal("-10")
        default_committed = Decimal(-200)
        accrued_deposit_payable = Decimal("0.00")
        accrued_deposit_receivable = Decimal("0.00")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft=accrued_overdraft_balance,
            default_committed=default_committed,
            overdraft_fee=overdraft_fee_balance,
            accrued_deposit_payable=accrued_deposit_payable,
            accrued_deposit_receivable=accrued_deposit_receivable,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            interest_application_day=1,
            interest_application_hour=effective_time.hour,
            interest_application_minute=effective_time.minute,
            interest_application_second=effective_time.second,
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            effective_date=effective_time,
            event_type="APPLY_ACCRUED_OVERDRAFT_INTEREST",
        )

        expected_fulfilment = Decimal("10.00")

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id="Main account",
                    to_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued overdraft interest applied.",
                        "event": "APPLY_ACCRUED_OVERDRAFT_INTEREST",
                    },
                ),
                call(
                    amount=expected_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_GL_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued overdraft interest applied.",
                        "event": "APPLY_ACCRUED_OVERDRAFT_INTEREST",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_OVERDRAFT_INTEREST_MOCK_HOOK",
            posting_instructions=[
                f"APPLY_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"APPLY_INTEREST_GL_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_accrues_payable_deposit_interest_at_eod(self):
        effective_time = datetime(2019, 1, 1)
        deposit_interest_yearly_rate = Decimal("0.0300")
        deposit_daily_rate = deposit_interest_yearly_rate / 365
        deposit_daily_rate_percentage = deposit_daily_rate * 100
        default_committed = Decimal("1000")
        tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "100", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "-1", "B": "1", "C": "-1"})
        expected_deposit_interest_accrual = Decimal("0.08219")

        balance_ts = self.account_balances(
            effective_time - timedelta(days=1), default_committed=default_committed
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            pnl_account="1",
            tier_names=tier_names,
            flags=["A"],
            deposit_interest_rate_tiers=DEPOSIT_INTEREST_RATE_TIERS_POSITIVE,
            deposit_tier_ranges=DEPOSIT_TIER_RANGES,
            overdraft_interest_rate=Decimal("0.1555"),
            interest_free_buffer=tiered_param_od_buffer_amount,
            standard_overdraft_daily_fee=Decimal("50"),
            standard_overdraft_fee_cap=Decimal("80"),
            fee_free_overdraft_limit=Decimal("10"),
            standard_overdraft_limit=Decimal("10"),
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            overdraft_interest_free_buffer_days=tiered_param_od_buffer_period,
            accrued_interest_payable_account=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            interest_paid_account=INTEREST_PAID_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_deposit_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id="Main account",
                    to_account_address=ACCRUED_DEPOSIT_PAYABLE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_TIER1"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE"
                    f"_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at "
                        f"{deposit_daily_rate_percentage:0.5f}%"
                        f" on balance of {default_committed:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
                call(
                    amount=expected_deposit_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=INTEREST_PAID_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_GL_TIER1"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE"
                    f"_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at "
                        f"{deposit_daily_rate_percentage:0.5f}%"
                        f" on balance of {default_committed:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                f"ACCRUE_INTEREST_CUSTOMER_TIER1"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE"
                f"_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"ACCRUE_INTEREST_GL_TIER1"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE"
                f"_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_scheduled_code_accrues_receivable_deposit_interest_at_eod(self):
        effective_time = datetime(2019, 1, 1)
        deposit_interest_yearly_rate = Decimal("-0.0300")
        deposit_daily_rate = deposit_interest_yearly_rate / 365
        deposit_daily_rate_percentage = deposit_daily_rate * 100
        default_committed = Decimal("1000")
        tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "100", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "-1", "B": "1", "C": "-1"})
        expected_deposit_interest_accrual = Decimal("0.08219")

        balance_ts = self.account_balances(
            effective_time - timedelta(days=1), default_committed=default_committed
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            pnl_account="1",
            tier_names=tier_names,
            flags=["A"],
            deposit_interest_rate_tiers=DEPOSIT_INTEREST_RATE_TIERS_NEGATIVE,
            deposit_tier_ranges=DEPOSIT_TIER_RANGES,
            overdraft_interest_rate=Decimal("0.1555"),
            interest_free_buffer=tiered_param_od_buffer_amount,
            standard_overdraft_daily_fee=Decimal("50"),
            standard_overdraft_fee_cap=Decimal("80"),
            fee_free_overdraft_limit=Decimal("10"),
            standard_overdraft_limit=Decimal("10"),
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            overdraft_interest_free_buffer_days=tiered_param_od_buffer_period,
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_deposit_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_TIER1"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE"
                    f"_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at "
                        f"{deposit_daily_rate_percentage:0.5f}%"
                        f" on balance of {default_committed:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
                call(
                    amount=expected_deposit_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_GL_TIER1"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE"
                    f"_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at "
                        f"{deposit_daily_rate_percentage:0.5f}%"
                        f" on balance of {default_committed:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                f"ACCRUE_INTEREST_CUSTOMER_TIER1"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE"
                f"_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"ACCRUE_INTEREST_GL_TIER1"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE"
                f"_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_scheduled_code_zero_deposit_interest_rate_accrues_nothing(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("1000")
        tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "200", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "-1", "B": "1", "C": "-1"})
        balance_ts = self.account_balances(
            effective_time,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            pnl_account="1",
            flags=["B"],
            tier_names=tier_names,
            deposit_interest_rate_tiers=json_dumps({"tier1": "0.00"}),
            deposit_tier_ranges=json_dumps({"tier1": {"min": 0}}),
            overdraft_interest_rate=Decimal("0.1555"),
            interest_free_buffer=tiered_param_od_buffer_amount,
            standard_overdraft_daily_fee=Decimal(50),
            standard_overdraft_fee_cap=Decimal(80),
            fee_free_overdraft_limit=Decimal(10),
            standard_overdraft_limit=Decimal(10),
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            overdraft_interest_free_buffer_days=tiered_param_od_buffer_period,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

    def test_scheduled_code_applies_accrued_receivable_deposit_interest(self):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0.00")
        accrued_overdraft = Decimal("0.00")
        default_committed = Decimal("1000.00")
        accrued_deposit_payable = Decimal("0.00")
        accrued_deposit_receivable = Decimal("-10.00")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
            overdraft_fee=overdraft_fee_balance,
            accrued_deposit_payable=accrued_deposit_payable,
            accrued_deposit_receivable=accrued_deposit_receivable,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            interest_application_day=1,
            interest_application_hour=effective_time.hour,
            interest_application_minute=effective_time.minute,
            interest_application_second=effective_time.second,
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            deposit_interest_application_frequency=UnionItemValue(key="monthly"),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            effective_date=effective_time,
            event_type="APPLY_ACCRUED_DEPOSIT_INTEREST",
        )

        expected_fulfilment = Decimal("10.00")

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id="Main account",
                    to_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_CUSTOMER"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE"
                    f"_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued deposit interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_GL"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE"
                    f"_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued deposit interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_DEPOSIT_INTEREST_MOCK_HOOK",
            posting_instructions=[
                f"APPLY_INTEREST_CUSTOMER"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE"
                f"_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"APPLY_INTEREST_GL"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE"
                f"_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_applies_accrued_payable_deposit_interest(self):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0.00")
        accrued_overdraft = Decimal("0.00")
        default_committed = Decimal("1000.00")
        accrued_deposit_payable = Decimal("10.00")
        accrued_deposit_receivable = Decimal("0.00")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
            overdraft_fee=overdraft_fee_balance,
            accrued_deposit_payable=accrued_deposit_payable,
            accrued_deposit_receivable=accrued_deposit_receivable,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            interest_application_day=1,
            interest_application_hour=effective_time.hour,
            interest_application_minute=effective_time.minute,
            interest_application_second=effective_time.second,
            deposit_interest_application_frequency=UnionItemValue(key="monthly"),
            accrued_interest_payable_account=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            effective_date=effective_time,
            event_type="APPLY_ACCRUED_DEPOSIT_INTEREST",
        )

        expected_fulfilment = Decimal("10.00")

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_DEPOSIT_PAYABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_CUSTOMER"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued deposit interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id="Main account",
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_GL"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued deposit interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_DEPOSIT_INTEREST_MOCK_HOOK",
            posting_instructions=[
                f"APPLY_INTEREST_CUSTOMER"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"APPLY_INTEREST_GL"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_reverses_accrued_payable_deposit_interest_with_neg_remainder(
        self,
    ):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0.00")
        accrued_overdraft = Decimal("0.00")
        default_committed = Decimal("1000.00")
        accrued_deposit = Decimal("10.03565")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
            overdraft_fee=overdraft_fee_balance,
            accrued_deposit_payable=accrued_deposit,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            interest_application_day=1,
            interest_application_hour=effective_time.hour,
            interest_application_minute=effective_time.minute,
            interest_application_second=effective_time.second,
            deposit_interest_application_frequency=UnionItemValue(key="monthly"),
            accrued_interest_payable_account=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            interest_paid_account=INTEREST_PAID_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            effective_date=effective_time,
            event_type="APPLY_ACCRUED_DEPOSIT_INTEREST",
        )

        expected_interest_fulfilment = Decimal("10.04")
        expected_rounding_fulfilment = Decimal("0.00435")

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_interest_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_DEPOSIT_PAYABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_CUSTOMER"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued deposit interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_interest_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id="Main account",
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_GL"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued deposit interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_rounding_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id="Main account",
                    to_account_address=ACCRUED_DEPOSIT_PAYABLE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_rounding_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=INTEREST_PAID_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_GL"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_DEPOSIT_INTEREST_MOCK_HOOK",
            posting_instructions=[
                f"APPLY_INTEREST_CUSTOMER"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"APPLY_INTEREST_GL"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"ACCRUE_INTEREST_CUSTOMER"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"ACCRUE_INTEREST_GL"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_reverses_accrued_payable_deposit_interest_with_pos_remainder(
        self,
    ):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0.00")
        accrued_overdraft = Decimal("0.00")
        default_committed = Decimal("1000.00")
        accrued_deposit = Decimal("10.03465")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
            overdraft_fee=overdraft_fee_balance,
            accrued_deposit_payable=accrued_deposit,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            interest_application_day=1,
            interest_application_hour=effective_time.hour,
            interest_application_minute=effective_time.minute,
            interest_application_second=effective_time.second,
            deposit_interest_application_frequency=UnionItemValue(key="monthly"),
            accrued_interest_payable_account=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            interest_paid_account=INTEREST_PAID_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            effective_date=effective_time,
            event_type="APPLY_ACCRUED_DEPOSIT_INTEREST",
        )

        expected_interest_fulfilment = Decimal("10.03")
        expected_rounding_fulfilment = Decimal("0.00465")

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_interest_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_DEPOSIT_PAYABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_CUSTOMER"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued deposit interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_interest_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id="Main account",
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_GL"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued deposit interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_rounding_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_DEPOSIT_PAYABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"REVERSE_ACCRUED_INTEREST_CUSTOMER"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_rounding_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_PAID_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"REVERSE_ACCRUED_INTEREST_GL"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_DEPOSIT_INTEREST_MOCK_HOOK",
            posting_instructions=[
                f"APPLY_INTEREST_CUSTOMER"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"APPLY_INTEREST_GL"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"REVERSE_ACCRUED_INTEREST_CUSTOMER"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"REVERSE_ACCRUED_INTEREST_GL"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_reverses_accrued_receivable_deposit_interest_with_neg_remainder(
        self,
    ):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0.00")
        accrued_overdraft = Decimal("0.00")
        default_committed = Decimal("1000.00")
        accrued_deposit = Decimal("-10.03565")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
            overdraft_fee=overdraft_fee_balance,
            accrued_deposit_receivable=accrued_deposit,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            interest_application_day=1,
            interest_application_hour=effective_time.hour,
            interest_application_minute=effective_time.minute,
            interest_application_second=effective_time.second,
            deposit_interest_application_frequency=UnionItemValue(key="monthly"),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            effective_date=effective_time,
            event_type="APPLY_ACCRUED_DEPOSIT_INTEREST",
        )

        expected_interest_fulfilment = Decimal("10.04")
        expected_rounding_fulfilment = Decimal("0.00435")

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_interest_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id="Main account",
                    to_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_CUSTOMER"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued deposit interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_interest_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_GL"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued deposit interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_rounding_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_rounding_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_GL"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_DEPOSIT_INTEREST_MOCK_HOOK",
            posting_instructions=[
                f"APPLY_INTEREST_CUSTOMER"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"APPLY_INTEREST_GL"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"ACCRUE_INTEREST_CUSTOMER"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"ACCRUE_INTEREST_GL"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_reverses_accrued_receivable_deposit_interest_with_pos_remainder(
        self,
    ):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0.00")
        accrued_overdraft = Decimal("0.00")
        default_committed = Decimal("1000.00")
        accrued_deposit = Decimal("-10.03465")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
            overdraft_fee=overdraft_fee_balance,
            accrued_deposit_receivable=accrued_deposit,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            interest_application_day=1,
            interest_application_hour=effective_time.hour,
            interest_application_minute=effective_time.minute,
            interest_application_second=effective_time.second,
            deposit_interest_application_frequency=UnionItemValue(key="monthly"),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            effective_date=effective_time,
            event_type="APPLY_ACCRUED_DEPOSIT_INTEREST",
        )

        expected_interest_fulfilment = Decimal("10.03")
        expected_rounding_fulfilment = Decimal("0.00465")

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_interest_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id="Main account",
                    to_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_CUSTOMER"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued deposit interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_interest_fulfilment,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_GL"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued deposit interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_rounding_fulfilment,
                    from_account_id="Main account",
                    from_account_address=INTERNAL_CONTRA,
                    denomination=DEFAULT_DENOMINATION,
                    to_account_id="Main account",
                    to_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"REVERSE_ACCRUED_INTEREST_CUSTOMER"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
                call(
                    amount=expected_rounding_fulfilment,
                    from_account_id=INTEREST_RECEIVED_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    denomination=DEFAULT_DENOMINATION,
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"REVERSE_ACCRUED_INTEREST_GL"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_DEPOSIT_INTEREST",
                    },
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_DEPOSIT_INTEREST_MOCK_HOOK",
            posting_instructions=[
                f"APPLY_INTEREST_CUSTOMER"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"APPLY_INTEREST_GL"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"REVERSE_ACCRUED_INTEREST_CUSTOMER"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"REVERSE_ACCRUED_INTEREST_GL"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time,
        )

    def test_close_code_applies_accrued_overdraft_interest_and_applies_overdraft_fees(
        self,
    ):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(-200)
        accrued_overdraft = Decimal("-10.78980")
        standard_overdraft_daily_fee = Decimal(50)
        overdraft_fee_balance = Decimal(50)
        accrued_deposit_payable = Decimal(0.00)
        accrued_deposit_receivable = Decimal(0.00)
        accrued_overdraft_fulfilment = accrued_overdraft.copy_abs().quantize(Decimal(".01"))
        overdraft_fee_balance_fulfilment = overdraft_fee_balance.copy_abs().quantize(Decimal(".01"))
        remainder = accrued_overdraft + accrued_overdraft_fulfilment

        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft=accrued_overdraft,
            default_committed=default_committed,
            overdraft_fee=-standard_overdraft_daily_fee,
            accrued_deposit_payable=accrued_deposit_payable,
            accrued_deposit_receivable=accrued_deposit_receivable,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            interest_free_buffer=50,
            overdraft_interest_rate=Decimal("0.1555"),
            standard_overdraft_daily_fee=Decimal(50),
            standard_overdraft_fee_cap=80,
            fee_free_overdraft_limit=10,
            standard_overdraft_limit=900,
            deposit_interest_rate=Decimal(0.0000),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
            overdraft_fee_receivable_account=OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
        )

        self.run_function("close_code", mock_vault, effective_date=effective_time)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=accrued_overdraft_fulfilment,
                    client_transaction_id=f"APPLY_INTEREST_CUSTOMER"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id="Main account",
                    to_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Accrued overdraft interest applied.",
                        "event": "APPLY_ACCRUED_OVERDRAFT_INTEREST",
                    },
                ),
                call(
                    amount=accrued_overdraft_fulfilment,
                    client_transaction_id=f"APPLY_INTEREST_GL"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Accrued overdraft interest applied.",
                        "event": "APPLY_ACCRUED_OVERDRAFT_INTEREST",
                    },
                ),
                call(
                    amount=abs(remainder),
                    client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_OVERDRAFT_INTEREST",
                    },
                ),
                call(
                    amount=abs(remainder),
                    client_transaction_id=f"ACCRUE_INTEREST_GL"
                    f"_{HOOK_EXECUTION_ID}_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}"
                    f"_{DEFAULT_DENOMINATION}",
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_OVERDRAFT_INTEREST",
                    },
                ),
                call(
                    amount=overdraft_fee_balance_fulfilment,
                    client_transaction_id=f"APPLY_FEES_CUSTOMER_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id="Main account",
                    to_account_address=ACCRUED_OVERDRAFT_FEE_RECEIVABLE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Overdraft fees applied.",
                        "event": "APPLY_MONTHLY_FEES",
                    },
                ),
                call(
                    amount=overdraft_fee_balance_fulfilment,
                    client_transaction_id=f"APPLY_FEES_GL_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Overdraft fees applied.",
                        "event": "APPLY_MONTHLY_FEES",
                    },
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_any_call(
            client_batch_id="CLOSE_MOCK_HOOK",
            posting_instructions=[
                f"APPLY_INTEREST_CUSTOMER"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                "APPLY_INTEREST_GL"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                "ACCRUE_INTEREST_CUSTOMER"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                "ACCRUE_INTEREST_GL"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}"
                f"_{DEFAULT_DENOMINATION}",
                f"APPLY_FEES_CUSTOMER_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"APPLY_FEES_GL_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time,
        )

    def test_get_outgoing_available_balance_returns_available_balance(self):
        expected = 150

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
            ): Balance(net=50),
        }

        result = self.run_function(
            "_get_outgoing_available_balance",
            None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_get_outgoing_available_balance_when_0_default_committed(self):
        expected = 50

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
            ): Balance(net=50),
        }

        result = self.run_function(
            "_get_outgoing_available_balance",
            None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_get_outgoing_available_balance_when_0_pending_balance(self):
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
            "_get_outgoing_available_balance",
            None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_get_outgoing_available_balance_when_0_balance(self):
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
            "_get_outgoing_available_balance",
            None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_get_accrue_interest_schedule(self):
        mock_vault = self.create_mock(
            interest_accrual_hour=23,
            interest_accrual_minute=58,
            interest_accrual_second=59,
            deposit_interest_application_frequency=UnionItemValue(key="monthly"),
        )

        accrue_interest_schedule = self.run_function(
            "_get_accrue_interest_schedule", mock_vault, vault=mock_vault
        )

        expected_accrue_interest_schedule = {
            "hour": "23",
            "minute": "58",
            "second": "59",
        }
        self.assertEqual(accrue_interest_schedule, expected_accrue_interest_schedule)

    def test_get_apply_accrued_interest_schedule_creates_schedule_same_month(self):
        mock_vault = self.create_mock(
            interest_application_day=3,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_next_apply_accrued_interest_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2020, 1, 1, 3, 4, 5),
        )

        expected_apply_accrued_interest_schedule = {
            "year": "2020",
            "month": "1",
            "day": "3",
            "hour": "23",
            "minute": "59",
            "second": "59",
        }
        self.assertEqual(apply_accrued_interest_date, expected_apply_accrued_interest_schedule)

    def test_get_apply_accrued_interest_schedule_creates_schedule_next_month(self):
        mock_vault = self.create_mock(
            interest_application_day=3,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_next_apply_accrued_interest_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2020, 1, 5, 3, 4, 5),
        )

        expected_apply_accrued_interest_schedule = {
            "year": "2020",
            "month": "2",
            "day": "3",
            "hour": "23",
            "minute": "59",
            "second": "59",
        }
        self.assertEqual(apply_accrued_interest_date, expected_apply_accrued_interest_schedule)

    def test_get_apply_accrued_interest_schedule_creates_schedule_day_not_in_month(
        self,
    ):
        mock_vault = self.create_mock(
            interest_application_day=31,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_next_apply_accrued_interest_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2019, 2, 1, 3, 4, 5),
        )

        expected_apply_accrued_interest_schedule = {
            "year": "2019",
            "month": "2",
            "day": "28",
            "hour": "23",
            "minute": "59",
            "second": "59",
        }
        self.assertEqual(apply_accrued_interest_date, expected_apply_accrued_interest_schedule)

    def test_get_apply_accrued_interest_schedule_creates_schedule_day_in_month_quarterly(
        self,
    ):
        mock_vault = self.create_mock(
            interest_application_day=31,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_next_apply_accrued_interest_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2019, 2, 1, 3, 4, 5),
            interest_application_frequency="quarterly",
        )

        expected_apply_accrued_interest_schedule = {
            "year": "2019",
            "month": "5",
            "day": "31",
            "hour": "23",
            "minute": "59",
            "second": "59",
        }
        self.assertEqual(apply_accrued_interest_date, expected_apply_accrued_interest_schedule)

    def test_get_apply_accrued_interest_schedule_creates_schedule_day_in_month_annually(
        self,
    ):
        mock_vault = self.create_mock(
            interest_application_day=31,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_next_apply_accrued_interest_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2019, 2, 1, 3, 4, 5),
            interest_application_frequency="annually",
        )

        expected_apply_accrued_interest_schedule = {
            "year": "2020",
            "month": "2",
            "day": "29",
            "hour": "23",
            "minute": "59",
            "second": "59",
        }
        self.assertEqual(apply_accrued_interest_date, expected_apply_accrued_interest_schedule)

    def test_get_apply_accrued_interest_schedule_creates_schedule_day_not_in_month_leap_year(
        self,
    ):
        mock_vault = self.create_mock(
            interest_application_day=31,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_next_apply_accrued_interest_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2020, 2, 1, 3, 4, 5),
        )

        expected_apply_accrued_interest_schedule = {
            "year": "2020",
            "month": "2",
            "day": "29",
            "hour": "23",
            "minute": "59",
            "second": "59",
        }
        self.assertEqual(apply_accrued_interest_date, expected_apply_accrued_interest_schedule)

    def test_next_schedule_date_returns_correct_date_monthly(self):
        mock_vault = self.create_mock()
        get_next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2020, 2, 1, 3, 4, 5),
            intended_day=31,
            schedule_frequency="monthly",
        )

        expected_apply_accrued_interest_schedule = datetime(
            year=2020, month=2, day=29, hour=3, minute=4, second=5
        )

        self.assertEqual(get_next_schedule_date, expected_apply_accrued_interest_schedule)

    def test_next_schedule_date_returns_correct_date_quarterly(self):
        mock_vault = self.create_mock()
        get_next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2019, 11, 1, 3, 4, 5),
            intended_day=31,
            schedule_frequency="quarterly",
        )

        expected_apply_accrued_interest_schedule = datetime(
            year=2020, month=2, day=29, hour=3, minute=4, second=5
        )

        self.assertEqual(get_next_schedule_date, expected_apply_accrued_interest_schedule)

    def test_next_schedule_date_returns_correct_date_annually(self):
        mock_vault = self.create_mock()
        get_next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2020, 2, 29, 23, 59, 59),
            intended_day=31,
            schedule_frequency="annually",
        )

        expected_apply_accrued_interest_schedule = datetime(
            year=2021, month=2, day=28, hour=23, minute=59, second=59
        )

        self.assertEqual(get_next_schedule_date, expected_apply_accrued_interest_schedule)

    def test_get_next_fee_schedule_correct_monthly_schedule(self):
        mock_vault = self.create_mock(
            fees_application_day=2,
            fees_application_hour=23,
            fees_application_minute=59,
            fees_application_second=0,
        )

        next_fee_schedule = self.run_function(
            "_get_next_fee_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2020, 1, 2, 3, 4, 5),
            period=relativedelta(months=1),
        )

        expected_next_fee_schedule = {
            "year": "2020",
            "month": "2",
            "day": "2",
            "hour": "23",
            "minute": "59",
            "second": "0",
        }
        self.assertEqual(next_fee_schedule, expected_next_fee_schedule)

    def test_get_next_fee_schedule_correct_monthly_schedule_day_greater_than_next_month_1(
        self,
    ):
        mock_vault = self.create_mock(
            fees_application_day=31,
            fees_application_hour=23,
            fees_application_minute=59,
            fees_application_second=0,
        )

        next_fee_schedule = self.run_function(
            "_get_next_fee_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2019, 1, 2, 3, 4, 5),
            period=relativedelta(months=1),
        )

        expected_next_fee_schedule = {
            "year": "2019",
            "month": "2",
            "day": "28",
            "hour": "23",
            "minute": "59",
            "second": "0",
        }
        self.assertEqual(next_fee_schedule, expected_next_fee_schedule)

    def test_get_next_fee_schedule_correct_monthly_schedule_day_greater_than_next_month_2(
        self,
    ):
        creation_date = datetime(2020, 1, 1)
        mock_vault = self.create_mock(
            fees_application_day=31,
            fees_application_hour=0,
            fees_application_minute=1,
            fees_application_second=0,
            creation_date=creation_date,
        )

        next_fee_schedule = self.run_function(
            "_get_next_fee_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=creation_date,
            period=relativedelta(months=1),
        )

        expected_next_fee_schedule = {
            "year": "2020",
            "month": "2",
            "day": "29",
            "hour": "0",
            "minute": "1",
            "second": "0",
        }
        self.assertEqual(next_fee_schedule, expected_next_fee_schedule)

    def test_get_next_fee_schedule_correct_monthly_schedule_when_lt_period_from_creation(
        self,
    ):
        creation_date = datetime(2020, 1, 2)

        mock_vault = self.create_mock(
            fees_application_day=1,
            fees_application_hour=0,
            fees_application_minute=1,
            fees_application_second=0,
            creation_date=creation_date,
        )

        next_fee_schedule = self.run_function(
            "_get_next_fee_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=creation_date,
            period=relativedelta(months=1),
        )

        expected_next_fee_schedule = {
            "year": "2020",
            "month": "3",
            "day": "1",
            "hour": "0",
            "minute": "1",
            "second": "0",
        }
        self.assertEqual(next_fee_schedule, expected_next_fee_schedule)

    def test_get_next_fee_schedule_correct_yearly_schedule(self):
        mock_vault = self.create_mock(
            fees_application_day=2,
            fees_application_hour=23,
            fees_application_minute=59,
            fees_application_second=0,
        )

        next_fee_schedule = self.run_function(
            "_get_next_fee_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2020, 1, 1, 3, 4, 5),
            period=relativedelta(years=1),
        )

        expected_next_fee_schedule = {
            "year": "2021",
            "month": "1",
            "day": "2",
            "hour": "23",
            "minute": "59",
            "second": "0",
        }
        self.assertEqual(next_fee_schedule, expected_next_fee_schedule)

    def test_get_next_fee_schedule_correct_yearly_schedule_when_less_than_period_fr_creation(
        self,
    ):
        creation_date = datetime(2020, 1, 2)

        mock_vault = self.create_mock(
            fees_application_day=1,
            fees_application_hour=0,
            fees_application_minute=1,
            fees_application_second=0,
            creation_date=creation_date,
        )

        next_fee_schedule = self.run_function(
            "_get_next_fee_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=creation_date,
            period=relativedelta(years=1),
        )

        expected_next_fee_schedule = {
            "year": "2021",
            "month": "2",
            "day": "1",
            "hour": "0",
            "minute": "1",
            "second": "0",
        }
        self.assertEqual(next_fee_schedule, expected_next_fee_schedule)

    def test_close_code_reverses_accrued_payable_interest(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(300)
        accrued_deposit = Decimal("10.78980")

        balance_ts = self.account_balances(
            effective_time,
            default_committed=default_committed,
            accrued_deposit_payable=accrued_deposit,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            accrued_interest_payable_account=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            interest_paid_account=INTEREST_PAID_ACCOUNT,
        )

        self.run_function("close_code", mock_vault, effective_date=effective_time)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=accrued_deposit,
                    client_transaction_id=f"REVERSE_ACCRUED_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_DEPOSIT_PAYABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Reverse accrued interest due to account closure",
                        "event": "CLOSE_ACCOUNT",
                    },
                ),
                call(
                    amount=accrued_deposit,
                    client_transaction_id=f"REVERSE_ACCRUED_INTEREST_GL_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_PAID_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Reverse accrued interest due to account closure",
                        "event": "CLOSE_ACCOUNT",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="CLOSE_MOCK_HOOK",
            posting_instructions=[
                f"REVERSE_ACCRUED_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"REVERSE_ACCRUED_INTEREST_GL_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time,
        )

    def test_overdraft_day_buffer_less_than_7_days_balances(self):
        # Within buffer period and amount - no postings expected
        effective_time = datetime(2020, 2, 1)

        period_start = effective_time - relativedelta(days=6)
        balance_ts = self.account_balances(dt=period_start, default_committed=Decimal("-50"))
        tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "70", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "7", "B": "-1", "C": "-1"})

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=tier_names,
            flags=["A"],
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            interest_free_buffer=tiered_param_od_buffer_amount,
            overdraft_interest_rate=Decimal(0.1555),
            standard_overdraft_daily_fee=Decimal(10),
            standard_overdraft_fee_cap=Decimal(80),
            fee_free_overdraft_limit=Decimal(200),
            standard_overdraft_limit=Decimal(10),
            overdraft_interest_free_buffer_days=tiered_param_od_buffer_period,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

        mock_vault.instruct_posting_batch.assert_not_called()

    def test_overdraft_day_buffer(self):
        # Outside buffer period, within amount - posting expected as if no buffer
        effective_time = datetime(2020, 2, 1)
        default_committed = Decimal("-50")
        tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "70", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "7", "B": "-1", "C": "-1"})
        period_start = effective_time - relativedelta(days=7, seconds=1)
        balance_ts = self.account_balances(dt=period_start, default_committed=default_committed)
        overdraft_interest_rate = Decimal("0.1555")
        daily_rate = overdraft_interest_rate / 365
        daily_rate_percent = daily_rate * 100
        expected_interest_accrual = Decimal("0.02130")

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=tier_names,
            flags=["A"],
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            interest_free_buffer=tiered_param_od_buffer_amount,
            overdraft_interest_rate=Decimal("0.1555"),
            standard_overdraft_daily_fee=Decimal(10),
            standard_overdraft_fee_cap=Decimal(80),
            fee_free_overdraft_limit=Decimal(200),
            standard_overdraft_limit=Decimal(10),
            overdraft_interest_free_buffer_days=tiered_param_od_buffer_period,
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_OVERDRAFT_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                        f" on balance of {default_committed:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
                call(
                    amount=expected_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_GL_OVERDRAFT_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                        f" on balance of {default_committed:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                f"ACCRUE_INTEREST_CUSTOMER_OVERDRAFT_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"ACCRUE_INTEREST_GL_OVERDRAFT_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_overdraft_day_buffer_breach_overdraft_buffer_amount(self):
        # Within buffer period, outside of overdraft amount - charge interest on balance - buffer
        effective_time = datetime(2020, 2, 1)
        default_committed = Decimal("-400")
        balance_ts = self.account_balances(
            effective_time - timedelta(seconds=1), default_committed=default_committed
        )
        overdraft_interest_rate = Decimal("0.1555")
        daily_rate = overdraft_interest_rate / 365
        daily_rate_percent = daily_rate * 100
        expected_interest_accrual = Decimal("0.14059")
        tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "70", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "7", "B": "-1", "C": "-1"})

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=tier_names,
            flags=["A"],
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            interest_free_buffer=tiered_param_od_buffer_amount,
            overdraft_interest_rate=Decimal("0.1555"),
            standard_overdraft_daily_fee=Decimal(10),
            standard_overdraft_fee_cap=Decimal(80),
            fee_free_overdraft_limit=Decimal(500),
            standard_overdraft_limit=Decimal(1000),
            overdraft_interest_free_buffer_days=tiered_param_od_buffer_period,
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_OVERDRAFT_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                        f" on balance of {default_committed + 70:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
                call(
                    amount=expected_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_GL_OVERDRAFT_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                        f" on balance of {default_committed + 70:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                f"ACCRUE_INTEREST_CUSTOMER_OVERDRAFT_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"ACCRUE_INTEREST_GL_OVERDRAFT_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_overdraft_0_day_buffer_breach_overdraft_buffer_amount(self):
        # 0 Buffer days, so always charge against the full balance
        effective_time = datetime(2020, 2, 1)
        default_committed = Decimal("-400")
        tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "70", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "0", "B": "-1", "C": "-1"})
        balance_ts = self.account_balances(
            effective_time - timedelta(seconds=1), default_committed=default_committed
        )
        overdraft_interest_rate = Decimal("0.1555")
        daily_rate = overdraft_interest_rate / 365
        daily_rate_percent = daily_rate * 100
        expected_interest_accrual = Decimal("0.17041")

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=tier_names,
            flags=["A"],
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            interest_free_buffer=tiered_param_od_buffer_amount,
            overdraft_interest_rate=Decimal("0.1555"),
            standard_overdraft_daily_fee=Decimal(10),
            standard_overdraft_fee_cap=Decimal(80),
            fee_free_overdraft_limit=Decimal(500),
            standard_overdraft_limit=Decimal(1000),
            overdraft_interest_free_buffer_days=tiered_param_od_buffer_period,
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_OVERDRAFT_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                        f" on balance of {default_committed:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
                call(
                    amount=expected_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_GL_OVERDRAFT_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                        f" on balance of {default_committed:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                f"ACCRUE_INTEREST_CUSTOMER_OVERDRAFT_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"ACCRUE_INTEREST_GL_OVERDRAFT_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_multiple_flags_earliest_in_list_selected(self):
        # Flag A will mean 0 Buffer days, so always charge against the full balance
        effective_time = datetime(2020, 2, 1)
        default_committed = Decimal("-400")
        tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "70", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "0", "B": "-1", "C": "-1"})
        balance_ts = self.account_balances(
            effective_time - timedelta(seconds=1), default_committed=default_committed
        )
        overdraft_interest_rate = Decimal("0.1555")
        daily_rate = overdraft_interest_rate / 365
        daily_rate_percent = daily_rate * 100
        expected_interest_accrual = Decimal("0.17041")

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=tier_names,
            # A should be selected
            flags=["A", "B", "C"],
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            interest_free_buffer=tiered_param_od_buffer_amount,
            overdraft_interest_rate=Decimal("0.1555"),
            standard_overdraft_daily_fee=Decimal(10),
            standard_overdraft_fee_cap=Decimal(80),
            fee_free_overdraft_limit=Decimal(500),
            standard_overdraft_limit=Decimal(1000),
            overdraft_interest_free_buffer_days=tiered_param_od_buffer_period,
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=expected_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_OVERDRAFT_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                        f" on balance of {default_committed:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
                call(
                    amount=expected_interest_accrual,
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"ACCRUE_INTEREST_GL_OVERDRAFT_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                        f" on balance of {default_committed:0.2f}.",
                        "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                f"ACCRUE_INTEREST_CUSTOMER_OVERDRAFT_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"ACCRUE_INTEREST_GL_OVERDRAFT_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_close_code_reverses_accrued_negative_interest(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(300)
        accrued_deposit = Decimal("-10.78980")

        balance_ts = self.account_balances(
            effective_time,
            default_committed=default_committed,
            accrued_deposit_receivable=accrued_deposit,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function("close_code", mock_vault, effective_date=effective_time)

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=abs(accrued_deposit),
                    client_transaction_id=f"REVERSE_ACCRUED_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id="Main account",
                    to_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Reverse accrued interest due to account closure",
                        "event": "CLOSE_ACCOUNT",
                    },
                ),
                call(
                    amount=abs(accrued_deposit),
                    client_transaction_id=f"REVERSE_ACCRUED_INTEREST_GL_{HOOK_EXECUTION_ID}"
                    f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=INTEREST_RECEIVED_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Reverse accrued interest due to account closure",
                        "event": "CLOSE_ACCOUNT",
                    },
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="CLOSE_MOCK_HOOK",
            posting_instructions=[
                f"REVERSE_ACCRUED_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                f"REVERSE_ACCRUED_INTEREST_GL_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            ],
            effective_date=effective_time,
        )

    def test_daily_ATM_limit_change_limited_by_template_parameter(self):
        mock_vault = self.create_mock(
            tier_names=json_dumps(["Z"]),
            maximum_daily_atm_withdrawal_limit=json_dumps({"Z": 25}),
        )
        shape = NumberShape(max_value=100)
        parameters = {"daily_atm_withdrawal_limit": Parameter(shape=shape)}
        effective_date = datetime(2020, 2, 1, 3, 4, 5)
        parameters = self.run_function(
            "pre_parameter_change_code",
            mock_vault,
            parameters,
            effective_date,
        )
        self.assertEqual(parameters["daily_atm_withdrawal_limit"].shape.max_value, 25)

    def test_posting_batch_with_supported_denom_and_sufficient_balance_is_accepted(
        self,
    ):

        main_denomination = "GBP"
        additional_denominations = json_dumps(["USD", "EUR", "CHF"])
        usd_posting = self.outbound_hard_settlement(
            amount="30", denomination="USD", value_timestamp=DEFAULT_DATE
        )

        pib, client_transaction, _ = self.pib_and_cts_for_posting_instructions(
            DEFAULT_DATE, posting_instructions_groups=[[usd_posting]]
        )

        mock_vault = self.create_mock(
            balance_ts=self.account_balances(
                balance_defs=[
                    {"address": "default", "denomination": "GBP", "net": "100"},
                    {"address": "default", "denomination": "USD", "net": "100"},
                ]
            ),
            denomination=main_denomination,
            additional_denominations=additional_denominations,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
            client_transaction=client_transaction,
        )

        self.run_function("pre_posting_code", mock_vault, pib, DEFAULT_DATE)

    def test_posting_batch_with_supported_and_unsupported_denom_is_rejected(self):

        main_denomination = "GBP"
        additional_denominations = json_dumps(["USD"])
        hkd_posting = self.outbound_hard_settlement(denomination="HKD", amount="1")
        usd_posting = self.outbound_hard_settlement(denomination="USD", amount="1")
        zar_posting = self.outbound_hard_settlement(denomination="ZAR", amount="1")
        gbp_posting = self.outbound_hard_settlement(denomination="GBP", amount="1")

        mock_vault = self.create_mock(
            balance_ts=self.account_balances(),
            denomination=main_denomination,
            additional_denominations=additional_denominations,
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[hkd_posting, usd_posting, zar_posting, gbp_posting]
        )

        with self.assertRaises(Rejected) as e:
            self.run_function("pre_posting_code", mock_vault, pib, DEFAULT_DATE)

        self.assertEqual(e.exception.reason_code, RejectedReason.WRONG_DENOMINATION)

    def test_posting_batch_with_single_denom_rejected_if_insufficient_balances(self):

        main_denomination = "GBP"
        additional_denominations = json_dumps(["USD"])
        usd_posting = self.outbound_hard_settlement(amount="20", denomination="USD")

        mock_vault = self.create_mock(
            balance_ts=self.account_balances(
                balance_defs=[
                    {"address": "default", "denomination": "USD", "net": "10"},
                ]
            ),
            denomination=main_denomination,
            additional_denominations=additional_denominations,
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[usd_posting])

        with self.assertRaises(Rejected) as e:
            self.run_function("pre_posting_code", mock_vault, pib, DEFAULT_DATE)

        self.assertEqual(e.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)

    def test_posting_batch_with_multiple_denom_rejected_if_one_insufficient_balance(
        self,
    ):

        main_denomination = "GBP"
        additional_denominations = json_dumps(["USD"])
        usd_posting = self.outbound_hard_settlement(amount="20", denomination="USD")
        gbp_posting = self.outbound_hard_settlement(amount="20", denomination="GBP")
        mock_vault = self.create_mock(
            balance_ts=self.account_balances(
                balance_defs=[
                    {"address": "default", "denomination": "USD", "net": "10"},
                    {"address": "default", "denomination": "GBP", "net": "30"},
                ]
            ),
            denomination=main_denomination,
            additional_denominations=additional_denominations,
            standard_overdraft_limit=Decimal("0.00"),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[usd_posting, gbp_posting])

        with self.assertRaises(Rejected) as e:
            self.run_function("pre_posting_code", mock_vault, pib, DEFAULT_DATE)

        expected_rejection_error = (
            "Postings total USD -20, which exceeds the available balance of USD 10"
        )

        self.assertEqual(str(e.exception), expected_rejection_error)
        self.assertEqual(e.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)

    def test_posting_batch_with_single_denom_debit_exceeding_available_accepted_due_to_credit(
        self,
    ):

        main_denomination = "GBP"
        additional_denominations = json_dumps(["USD"])
        usd_posting = self.outbound_hard_settlement(
            amount="30",
            denomination="USD",
            value_timestamp=DEFAULT_DATE,
            client_transaction_id=CLIENT_TRANSACTION_ID_0,
            client_id=CLIENT_ID_0,
        )
        usd_posting_2 = self.inbound_hard_settlement(
            amount="20",
            denomination="USD",
            value_timestamp=DEFAULT_DATE,
            client_transaction_id=CLIENT_TRANSACTION_ID_1,
            client_id=CLIENT_ID_1,
        )

        pib, client_transaction, _ = self.pib_and_cts_for_posting_instructions(
            DEFAULT_DATE, posting_instructions_groups=[[usd_posting], [usd_posting_2]]
        )
        mock_vault = self.create_mock(
            balance_ts=self.account_balances(
                balance_defs=[
                    {"address": "default", "denomination": "USD", "net": "10"},
                ]
            ),
            denomination=main_denomination,
            additional_denominations=additional_denominations,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
            client_transaction=client_transaction,
        )

        self.run_function("pre_posting_code", mock_vault, pib, DEFAULT_DATE)

    def test_posting_batch_rejected_if_multiple_debits_below_zero(self):
        main_denomination = "GBP"
        additional_denominations = json_dumps(["USD"])
        usd_posting1 = self.outbound_hard_settlement(amount="100", denomination="USD")
        usd_posting2 = self.outbound_hard_settlement(amount="100", denomination="USD")
        mock_vault = self.create_mock(
            balance_ts=self.account_balances(
                balance_defs=[
                    {"address": "default", "denomination": "USD", "net": "150"},
                ]
            ),
            denomination=main_denomination,
            additional_denominations=additional_denominations,
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[usd_posting1, usd_posting2])

        with self.assertRaises(Rejected) as e:
            self.run_function("pre_posting_code", mock_vault, pib, DEFAULT_DATE)

        self.assertEqual(e.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)

    def test_posting_batch_accepted_if_crediting_single_denom(self):
        main_denomination = "GBP"
        additional_denominations = json_dumps(["USD", "EUR"])
        usd_posting = self.inbound_hard_settlement(
            amount="20", denomination="USD", value_timestamp=DEFAULT_DATE - timedelta(hours=1)
        )
        gbp_posting = self.outbound_hard_settlement(
            amount="20", denomination="GBP", value_timestamp=DEFAULT_DATE
        )

        pib, client_transaction, _ = self.pib_and_cts_for_posting_instructions(
            DEFAULT_DATE, posting_instructions_groups=[[usd_posting, gbp_posting]]
        )

        mock_vault = self.create_mock(
            balance_ts=self.account_balances(
                balance_defs=[
                    {"address": "default", "denomination": "USD", "net": "10"},
                    {"address": "default", "denomination": "GBP", "net": "30"},
                ]
            ),
            denomination=main_denomination,
            additional_denominations=additional_denominations,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
            standard_overdraft_limit=Decimal("0.00"),
            client_transaction=client_transaction,
        )
        self.run_function(
            "pre_posting_code",
            mock_vault,
            pib,
            DEFAULT_DATE,
        )

    def test_posting_batch_accepted_if_crediting_multiple_balances(self):
        main_denomination = "GBP"
        additional_denominations = json_dumps(["USD", "EUR"])
        usd_posting = self.inbound_hard_settlement(
            amount="20", denomination="USD", value_timestamp=DEFAULT_DATE - timedelta(hours=1)
        )
        eur_posting = self.inbound_hard_settlement(
            amount="20", denomination="EUR", value_timestamp=DEFAULT_DATE
        )

        pib, client_transaction, _ = self.pib_and_cts_for_posting_instructions(
            DEFAULT_DATE, posting_instructions_groups=[[usd_posting, eur_posting]]
        )

        mock_vault = self.create_mock(
            balance_ts=self.account_balances(
                balance_defs=[
                    {"address": "default", "denomination": "USD", "net": "10"},
                    {"address": "default", "denomination": "EUR", "net": "30"},
                ]
            ),
            denomination=main_denomination,
            additional_denominations=additional_denominations,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
            client_transaction=client_transaction,
        )

        self.run_function(
            "pre_posting_code",
            mock_vault,
            pib,
            DEFAULT_DATE,
        )

    def test_available_balance_reduced_by_pending_out_balances(self):
        balance_ts = self.account_balances(
            balance_defs=[
                {"address": "default", "denomination": "USD", "net": "10"},
                {
                    "address": "default",
                    "denomination": "USD",
                    "phase": Phase.PENDING_OUT,
                    "net": "-10",
                },
            ]
        )
        expected_available_balance = Decimal("0")
        available_balance = self.run_function(
            "_get_outgoing_available_balance",
            Mock(),
            balances=balance_ts[0][1],
            denomination="USD",
        )

        self.assertEqual(expected_available_balance, available_balance)

    def test_available_balance_not_affected_by_pending_in_balances(self):
        balance_ts = self.account_balances(
            balance_defs=[
                {"address": "default", "denomination": "USD", "net": "10"},
                {
                    "address": "default",
                    "denomination": "USD",
                    "phase": Phase.PENDING_IN,
                    "net": "10",
                },
            ]
        )
        expected_available_balance = Decimal("10")
        available_balance = self.run_function(
            "_get_outgoing_available_balance",
            Mock(),
            balances=balance_ts[0][1],
            denomination="USD",
        )

        self.assertEqual(expected_available_balance, available_balance)

    def test_dormant_account_prevents_external_debits(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(2000)
        auth_amount = Decimal("1000")

        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=effective_time,
            posting_instructions_groups=[
                [
                    self.outbound_hard_settlement(
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        amount=auth_amount,
                        denomination="USD",
                        value_timestamp=effective_time,
                        instruction_details={"transaction_code": "6011"},
                    ),
                ]
            ],
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transactions,
            denomination=DEFAULT_DENOMINATION,
            standard_overdraft_limit=Decimal(1000),
            daily_atm_withdrawal_limit=Decimal(1000),
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            flags=[DORMANCY_FLAG],
        )

        with self.assertRaises(Rejected) as e:
            self.run_function("pre_posting_code", mock_vault, pib, effective_time)

        self.assertEqual(
            str(e.exception),
            'Account flagged "Dormant" does not accept external transactions.',
        )
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)

    def test_dormant_account_does_not_charge_monthly_maintenance_fee(self):
        mock_vault = self._maintenance_fee_setup_and_run(
            event_type="APPLY_MONTHLY_FEES",
            monthly_fee=Decimal(10),
            flags=[DORMANCY_FLAG],
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_dormant_account_does_not_charge_annual_maintenance_fee(self):
        mock_vault = self._maintenance_fee_setup_and_run(
            event_type="APPLY_ANNUAL_FEES",
            annual_fee=Decimal(10),
            flags=[DORMANCY_FLAG],
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_dormant_account_does_not_charge_minimum_balance_fee(self):
        effective_time = datetime(2020, 3, 15)
        expected_minimum_balance_fee = Decimal(100)

        period_start = effective_time - relativedelta(months=1)

        balance_ts = self.account_balances(dt=period_start, default_committed=Decimal("0"))

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            account_inactivity_fee=Decimal(0),
            tier_names=json_dumps(["X", "Y", "Z"]),
            maintenance_fee_monthly=json_dumps({"Z": "0"}),
            minimum_balance_threshold=json_dumps({"Z": "1500"}),
            minimum_combined_balance_threshold=json_dumps({"Z": "5000"}),
            minimum_deposit_threshold=json_dumps({"Z": "500"}),
            minimum_balance_fee=Decimal(expected_minimum_balance_fee),
            fees_application_day=1,
            fees_application_hour=23,
            fees_application_minute=0,
            fees_application_second=0,
            flags=[DORMANCY_FLAG],
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_dormant_account_charges_inactivity_fee(self):
        effective_time = datetime(2020, 3, 15)
        expected_inactivity_fee = Decimal(100)

        period_start = effective_time - relativedelta(months=1)

        balance_ts = self.account_balances(dt=period_start, default_committed=Decimal("0"))

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            tier_names=json_dumps(["Z"]),
            maintenance_fee_monthly=json_dumps({"Z": "10"}),
            minimum_balance_threshold=json_dumps({"Z": "1500"}),
            minimum_combined_balance_threshold=json_dumps({"Z": "5000"}),
            minimum_deposit_threshold=json_dumps({"Z": "500"}),
            account_inactivity_fee=expected_inactivity_fee,
            fees_application_day=1,
            fees_application_hour=23,
            fees_application_minute=0,
            fees_application_second=0,
            flags=[DORMANCY_FLAG],
            inactivity_fee_income_account=INACTIVITY_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_inactivity_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=INACTIVITY_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MONTHLY_FEES_INACTIVITY_"
            f"{HOOK_EXECUTION_ID}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Account inactivity fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_APPLY_MONTHLY_FEES_INACTIVITY_MOCK_HOOK_GBP",
            ],
            effective_date=effective_time,
        )

    def test_autosave_simple(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(1000)
        balance_ts = self.account_balances(
            effective_time - timedelta(seconds=1), default_committed=default_committed
        )
        autosave_savings_account = "12345678"
        autosave_rounding_amount = Decimal("1.00")
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    denomination=DEFAULT_DENOMINATION,
                    amount=Decimal("5.6"),
                )
            ],
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            minimum_balance_fee=Decimal(0),
            denomination=DEFAULT_DENOMINATION,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
        )
        result, _ = self.run_function(
            "_autosave_from_purchase",
            mock_vault,
            mock_vault,
            test_postings,
            effective_time,
            DEFAULT_DENOMINATION,
            autosave_savings_account,
            autosave_rounding_amount,
        )
        self.assertEqual(Decimal("0.4"), result, "Failed to round up to nearest 1.00")

        autosave_rounding_amount = Decimal("10.00")
        result, _ = self.run_function(
            "_autosave_from_purchase",
            mock_vault,
            mock_vault,
            test_postings,
            effective_time,
            DEFAULT_DENOMINATION,
            autosave_savings_account,
            autosave_rounding_amount,
        )
        self.assertEqual(Decimal("4.40"), result, "Failed to round up to nearest 10.00")

        autosave_rounding_amount = Decimal("0.50")
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_hard_settlement(amount=Decimal("232.14"))]
        )

        result, _ = self.run_function(
            "_autosave_from_purchase",
            mock_vault,
            mock_vault,
            test_postings,
            effective_time,
            DEFAULT_DENOMINATION,
            autosave_savings_account,
            autosave_rounding_amount,
        )
        self.assertEqual(Decimal("0.36"), result, "Failed to round up to nearest 0.50")

        autosave_rounding_amount = Decimal("0.50")
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    denomination=DEFAULT_DENOMINATION,
                    amount=Decimal("1.50"),
                )
            ],
        )
        result, _ = self.run_function(
            "_autosave_from_purchase",
            mock_vault,
            mock_vault,
            test_postings,
            effective_time,
            DEFAULT_DENOMINATION,
            autosave_savings_account,
            autosave_rounding_amount,
        )
        self.assertEqual(Decimal("0"), result, "Failed to return no saving")

        autosave_rounding_amount = Decimal("1.00")
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    denomination=DEFAULT_DENOMINATION,
                    amount=Decimal("3.00"),
                )
            ],
        )
        result, _ = self.run_function(
            "_autosave_from_purchase",
            mock_vault,
            mock_vault,
            test_postings,
            effective_time,
            DEFAULT_DENOMINATION,
            autosave_savings_account,
            autosave_rounding_amount,
        )
        self.assertEqual(Decimal("0"), result, "Failed to return no saving, rounding_amount is 1")

        autosave_rounding_amount = Decimal("0.80")
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    denomination=DEFAULT_DENOMINATION,
                    amount=Decimal("1.14"),
                )
            ],
        )
        result, _ = self.run_function(
            "_autosave_from_purchase",
            mock_vault,
            mock_vault,
            test_postings,
            effective_time,
            DEFAULT_DENOMINATION,
            autosave_savings_account,
            autosave_rounding_amount,
        )
        self.assertEqual(Decimal("0.46"), result, "Failed to round up to nearest 0.80")

        autosave_rounding_amount = Decimal("1.00")
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    denomination=DEFAULT_DENOMINATION,
                    amount=Decimal("500.301"),
                )
            ],
        )
        result, _ = self.run_function(
            "_autosave_from_purchase",
            mock_vault,
            mock_vault,
            test_postings,
            effective_time,
            DEFAULT_DENOMINATION,
            autosave_savings_account,
            autosave_rounding_amount,
        )
        self.assertEqual(Decimal("0.699"), result, "Failed to round to 3 decimals")

    def test_autosave_not_enough_balance(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(0.5)
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)
        autosave_savings_account = "12345678"
        autosave_rounding_amount = Decimal("1.00")
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    denomination=DEFAULT_DENOMINATION,
                    amount=Decimal("10.30"),
                )
            ],
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            minimum_balance_fee=Decimal(0),
            denomination=DEFAULT_DENOMINATION,
            transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal"}',
            transaction_types='["purchase", "ATM withdrawal", "transfer"]',
        )
        result, _ = self.run_function(
            "_autosave_from_purchase",
            mock_vault,
            mock_vault,
            test_postings,
            effective_time,
            DEFAULT_DENOMINATION,
            autosave_savings_account,
            autosave_rounding_amount,
        )
        self.assertEqual(0, result)

    def test_per_transaction_overdraft_positive_balance_not_charged(self):
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE - timedelta(seconds=1), default_committed=Decimal(10)
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_hard_settlement(amount=Decimal("20"))]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(10),
            pnl_account="1",
        )

        self.run_function(
            "_charge_overdraft_per_transaction_fee",
            mock_vault,
            vault=mock_vault,
            postings=pib,
            offset_amount=0,
            denomination="USD",
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_per_transaction_overdraft_neg_bal_within_fee_free_limit_not_charged(self):
        balance_ts = self.account_balances(dt=DEFAULT_DATE, default_committed=Decimal(-10))
        debit_posting = self.outbound_hard_settlement(
            amount="20",
            denomination="USD",
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[debit_posting])

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(20),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            "_charge_overdraft_per_transaction_fee",
            mock_vault,
            vault=mock_vault,
            postings=pib,
            offset_amount=0,
            denomination="USD",
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_per_transaction_overdraft_neg_bal_outside_fee_free_limit_charged(self):
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE, denomination="USD", default_committed=Decimal(-10)
        )
        debit_posting = self.outbound_hard_settlement(
            amount="20",
            denomination="USD",
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[debit_posting])

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            standard_overdraft_fee_cap=Decimal(0),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
            autosave_savings_account=OptionalValue(value="12345678", is_set=False),
            denomination="USD",
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_with(
            amount=Decimal(5),
            denomination="USD",
            client_transaction_id="INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_HOOK_"
            "USD_MOCK_POSTING_0",
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            instruction_details={
                "description": "Applying standard overdraft transaction fee" " for MOCK_POSTING",
                "event": "STANDARD_OVERDRAFT",
            },
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="POST_POSTING_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_HOOK_"
                "USD_MOCK_POSTING_0"
            ],
            effective_date=DEFAULT_DATE,
        )

    def test_per_transaction_overdraft_neg_pending_auth_outside_fee_free_limit_not_charged(
        self,
    ):
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE - timedelta(seconds=1),
            denomination="USD",
            default_committed=Decimal(-3),
            default_pending_outgoing=Decimal(-100),
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_hard_settlement(amount=Decimal("20"))]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            "_charge_overdraft_per_transaction_fee",
            mock_vault,
            vault=mock_vault,
            postings=pib,
            offset_amount=0,
            denomination="USD",
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_per_transaction_overdraft_savings_sweep_offset_within_fee_free_limit_not_charged(
        self,
    ):
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE, denomination="USD", default_committed=Decimal(-30)
        )
        debit_posting = self.outbound_hard_settlement(
            amount="20",
            denomination="USD",
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[debit_posting])

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            "_charge_overdraft_per_transaction_fee",
            mock_vault,
            vault=mock_vault,
            postings=pib,
            offset_amount=30,
            denomination="USD",
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_per_transaction_overdraft_savings_sweep_offset_outside_fee_free_limit_fee_charged(
        self,
    ):
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE, denomination="USD", default_committed=Decimal(-30)
        )
        debit_posting = self.outbound_hard_settlement(
            amount="20",
            denomination="USD",
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[debit_posting])

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            standard_overdraft_fee_cap=Decimal(0),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
            autosave_savings_account=OptionalValue(value="12345678", is_set=False),
            denomination="USD",
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_with(
            amount=Decimal(5),
            denomination="USD",
            client_transaction_id="INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_HOOK_"
            "USD_MOCK_POSTING_0",
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            instruction_details={
                "description": "Applying standard overdraft transaction fee for" " MOCK_POSTING",
                "event": "STANDARD_OVERDRAFT",
            },
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="POST_POSTING_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_HOOK_"
                "USD_MOCK_POSTING_0"
            ],
            effective_date=DEFAULT_DATE,
        )

    def test_per_transaction_overdraft_non_default_custom_instruction_no_fee_charged(
        self,
    ):
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE, denomination="USD", default_committed=Decimal(-30)
        )
        debit_posting = self.custom_instruction(
            amount="20",
            credit=False,
            denomination="USD",
            account_address="OTHER_ADDRESS",
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[debit_posting])

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            "_charge_overdraft_per_transaction_fee",
            mock_vault,
            vault=mock_vault,
            postings=pib,
            offset_amount=5,
            denomination="USD",
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_per_transaction_overdraft_default_custom_instruction_fee_charged(self):
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE, denomination="USD", default_committed=Decimal(-30)
        )
        debit_posting = self.custom_instruction(
            amount="20",
            credit=False,
            denomination="USD",
            account_address=DEFAULT_ADDRESS,
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[debit_posting])

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            standard_overdraft_fee_cap=Decimal(0),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
            autosave_savings_account=OptionalValue(value="12345678", is_set=False),
            denomination="USD",
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_with(
            amount=Decimal(5),
            denomination="USD",
            client_transaction_id="INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_HOOK_"
            "USD_MOCK_POSTING_0",
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            instruction_details={
                "description": "Applying standard overdraft transaction fee for" " MOCK_POSTING",
                "event": "STANDARD_OVERDRAFT",
            },
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="POST_POSTING_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_HOOK_"
                "USD_MOCK_POSTING_0"
            ],
            effective_date=DEFAULT_DATE,
        )

    def test_per_transaction_overdraft_credit_posting_no_fee_charged(self):
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE, denomination="USD", default_committed=Decimal(-30)
        )
        debit_posting = self.inbound_hard_settlement(
            amount="20",
            denomination="USD",
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[debit_posting])

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
        )

        self.run_function(
            "_charge_overdraft_per_transaction_fee",
            mock_vault,
            vault=mock_vault,
            postings=pib,
            offset_amount=5,
            denomination="USD",
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_per_transaction_overdraft_two_postings_charges_twice(self):
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE, denomination="USD", default_committed=Decimal(-40)
        )
        debit_posting_1 = self.outbound_hard_settlement(
            amount="20",
            denomination="USD",
            value_timestamp=DEFAULT_DATE,
        )
        debit_posting_2 = self.outbound_hard_settlement(
            amount="30",
            denomination="USD",
            value_timestamp=DEFAULT_DATE + timedelta(seconds=1),
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[debit_posting_1, debit_posting_2]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            standard_overdraft_fee_cap=Decimal(0),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
            autosave_savings_account=OptionalValue(value="12345678", is_set=False),
            denomination="USD",
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal(5),
                    denomination="USD",
                    client_transaction_id="INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_"
                    "MOCK_HOOK_USD_MOCK_POSTING_0",
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    instruction_details={
                        "description": "Applying standard overdraft transaction fee for"
                        " MOCK_POSTING",
                        "event": "STANDARD_OVERDRAFT",
                    },
                ),
                call(
                    amount=Decimal(5),
                    denomination="USD",
                    client_transaction_id="INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_"
                    "MOCK_HOOK_USD_MOCK_POSTING_1",
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    instruction_details={
                        "description": "Applying standard overdraft transaction fee for"
                        " MOCK_POSTING",
                        "event": "STANDARD_OVERDRAFT",
                    },
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="POST_POSTING_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_HOOK_USD_MOCK_"
                "POSTING_0",
                "INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_HOOK_USD_MOCK_"
                "POSTING_1",
            ],
            effective_date=DEFAULT_DATE,
        )

    def test_per_transaction_fee_capped(self):
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE, denomination="USD", default_committed=Decimal(-40)
        )
        debit_posting_1 = self.outbound_hard_settlement(
            amount="20",
            denomination="USD",
            value_timestamp=DEFAULT_DATE,
        )
        debit_posting_2 = self.outbound_hard_settlement(
            amount="30",
            denomination="USD",
            value_timestamp=DEFAULT_DATE + timedelta(seconds=1),
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[debit_posting_1, debit_posting_2]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            standard_overdraft_per_transaction_fee=Decimal(5),
            fee_free_overdraft_limit=Decimal(5),
            standard_overdraft_fee_cap=Decimal(7),
            overdraft_fee_income_account=OVERDRAFT_FEE_INCOME_ACCOUNT,
            denomination="USD",
            autosave_savings_account=OptionalValue(value="12345678", is_set=False),
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal(5),
                    denomination="USD",
                    client_transaction_id="INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_"
                    "MOCK_HOOK_USD_MOCK_POSTING_0",
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    instruction_details={
                        "description": "Applying standard overdraft transaction fee for"
                        " MOCK_POSTING",
                        "event": "STANDARD_OVERDRAFT",
                    },
                )
            ]
        )
        mock_vault.make_internal_transfer_instructions.assert_called_once()
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="POST_POSTING_MOCK_HOOK",
            posting_instructions=[
                "INTERNAL_POSTING_STANDARD_OVERDRAFT_TRANSACTION_FEE_MOCK_HOOK_USD_MOCK_POSTING_0"
            ],
            effective_date=DEFAULT_DATE,
        )

    def test_get_monthly_maintenance_fee_tiers(self):
        test_cases = (
            {
                "flags": [PROMOTIONAL_MAINTENANCE_FEE],
                "expected_result": PROMOTIONAL_MAINTENANCE_FEE_MONTHLY,
                "description": "has promotional fee flag",
            },
            {
                "flags": [],
                "expected_result": MAINTENANCE_FEE_MONTHLY,
                "description": "no promotional fee flag",
            },
        )

        for test_case in test_cases:
            mock_vault = self.create_mock(
                denomination="USD",
                flags=test_case["flags"],
                maintenance_fee_monthly=MAINTENANCE_FEE_MONTHLY,
                promotional_maintenance_fee_monthly=PROMOTIONAL_MAINTENANCE_FEE_MONTHLY,
            )
            result = self.run_function("_get_monthly_maintenance_fee_tiers", mock_vault, mock_vault)

            self.assertDictEqual(
                result, loads(test_case["expected_result"]), test_case["description"]
            )

    def test_has_transaction_type_not_covered_by_standard_overdraft(self):
        test_cases = (
            {
                "expected_result": False,
                "description": "ATM transaction with standard overdraft coverage flag",
                "flags": [STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG],
                "postings": [
                    self.outbound_hard_settlement(
                        amount="30",
                        denomination="USD",
                        value_timestamp=DEFAULT_DATE,
                        instruction_details={"transaction_code": "6011"},
                    )
                ],
            },
            {
                "expected_result": True,
                "description": "ATM transaction without standard overdraft coverage flag",
                "flags": [],
                "postings": [
                    self.outbound_hard_settlement(
                        amount="30",
                        denomination="USD",
                        value_timestamp=DEFAULT_DATE,
                        instruction_details={"transaction_code": "6011"},
                    )
                ],
            },
            {
                "expected_result": False,
                "description": "eCommerce transaction with standard overdraft coverage flag",
                "flags": [STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG],
                "postings": [
                    self.outbound_hard_settlement(
                        amount="30",
                        denomination="USD",
                        value_timestamp=DEFAULT_DATE,
                        instruction_details={"transaction_code": "3123"},
                    )
                ],
            },
            {
                "expected_result": True,
                "description": "eCommerce transaction without standard overdraft coverage flag",
                "flags": [],
                "postings": [
                    self.outbound_hard_settlement(
                        amount="30",
                        denomination="USD",
                        value_timestamp=DEFAULT_DATE,
                        instruction_details={"transaction_code": "3123"},
                    )
                ],
            },
            {
                "expected_result": False,
                "description": "other transaction type is covered by overdraft",
                "flags": [STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG],
                "postings": [
                    self.outbound_hard_settlement(
                        amount="30",
                        denomination="USD",
                        value_timestamp=DEFAULT_DATE,
                        instruction_details={"transaction_code": "SOME DIFFERENT TRANSACTION TYPE"},
                    )
                ],
            },
            {
                "expected_result": False,
                "description": "other transaction type covered by overdraft with no coverage flag",
                "flags": [],
                "postings": [
                    self.outbound_hard_settlement(
                        amount="30",
                        denomination="USD",
                        value_timestamp=DEFAULT_DATE,
                        instruction_details={"transaction_code": "SOME DIFFERENT TRANSACTION TYPE"},
                    )
                ],
            },
            {
                "expected_result": True,
                "description": "Transaction posting not covered mixed with others in batch",
                "flags": [],
                "postings": [
                    self.outbound_hard_settlement(
                        amount="300",
                        denomination="USD",
                        value_timestamp=DEFAULT_DATE,
                        instruction_details={"transaction_code": "SOME DIFFERENT TRANSACTION TYPE"},
                    ),
                    self.outbound_hard_settlement(
                        amount="20",
                        denomination="USD",
                        value_timestamp=DEFAULT_DATE,
                        instruction_details={"transaction_code": "6011"},
                    ),
                    self.inbound_hard_settlement(
                        amount="200",
                        denomination="USD",
                        value_timestamp=DEFAULT_DATE,
                    ),
                ],
            },
        )

        for test_case in test_cases:
            mock_vault = self.create_mock(
                transaction_code_to_type_map='{"": "purchase", "6011": "ATM withdrawal", '
                '"3123": "eCommerce"}',
                optional_standard_overdraft_coverage='["ATM withdrawal", "eCommerce"]',
                flags=test_case["flags"],
            )

            pib = self.mock_posting_instruction_batch(posting_instructions=test_case["postings"])

            result = self.run_function(
                "_has_transaction_type_not_covered_by_standard_overdraft",
                None,
                vault=mock_vault,
                postings=pib,
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

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

            mock_vault = self.create_mock(supervisees={})

            result = self.run_function("_is_settled_against_default_address", mock_vault, pi)

            self.assertEqual(result, pi_type[1], pi_type[0])

    def test_get_committed_default_committed_from_postings(self):
        test_cases = (
            {
                "expected_result": Decimal("-50"),
                "description": "Outgoing Hard Settlement",
                "postings": [
                    self.outbound_hard_settlement(
                        amount="50",
                        denomination="USD",
                    )
                ],
            },
            {
                "expected_result": Decimal("50"),
                "description": "Incoming Hard Settlement",
                "postings": [
                    self.inbound_hard_settlement(
                        amount="50",
                        denomination="USD",
                    )
                ],
            },
            {
                "expected_result": Decimal("-30"),
                "description": "Debit Transfer",
                "postings": [
                    self.outbound_transfer(
                        amount="30",
                        denomination="USD",
                    )
                ],
            },
            {
                "expected_result": Decimal("30"),
                "description": "Credit Transfer",
                "postings": [
                    self.inbound_transfer(
                        amount="30",
                        denomination="USD",
                    )
                ],
            },
            {
                "expected_result": Decimal("0"),
                "description": "Incoming Authorisation ignored",
                "postings": [
                    self.inbound_auth(
                        amount="50",
                        denomination="USD",
                    )
                ],
            },
            {
                "expected_result": Decimal("-0"),
                "description": "Outgoing Authorisation ignored",
                "postings": [
                    self.outbound_auth(
                        amount="50",
                        denomination="USD",
                    )
                ],
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
                        credit=True,
                        denomination="USD",
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.PENDING_IN,
                    )
                ],
            },
            {
                "expected_result": Decimal("30"),
                "description": "Settlement on inbound authorisation",
                "postings": [
                    self.settle_inbound_auth(
                        amount="30",
                        unsettled_amount="30",
                        denomination="USD",
                    )
                ],
            },
            {
                "expected_result": Decimal("-30"),
                "description": "Settlement on outbound authorisation",
                "postings": [
                    self.settle_outbound_auth(
                        amount="30",
                        unsettled_amount="30",
                        denomination="USD",
                    )
                ],
            },
            {
                "expected_result": Decimal("0"),
                "description": "Release ignored",
                "postings": [
                    self.release_outbound_auth(
                        amount="30",
                        unsettled_amount="30",
                        denomination="USD",
                    )
                ],
            },
            {
                "expected_result": Decimal("-60"),
                "description": "Multiple postings in batch",
                "include_out_auth": False,
                "postings": [
                    self.outbound_transfer(
                        amount="30",
                        denomination="USD",
                    ),
                    self.inbound_auth(
                        amount="50",
                        denomination="USD",
                    ),
                    self.outbound_hard_settlement(
                        amount="30",
                        denomination="USD",
                    ),
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
