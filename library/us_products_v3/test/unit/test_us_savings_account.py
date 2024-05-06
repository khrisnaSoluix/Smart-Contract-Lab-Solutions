# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import json
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps as json_dumps
from typing import Any, Optional
from unittest import skip
from unittest.mock import call

# library
from library.us_products_v3.constants.files import US_SAVINGS_TEMPLATE

# inception sdk
from inception_sdk.test_framework.contracts.unit.common import (
    CLIENT_ID_0,
    CLIENT_ID_1,
    CLIENT_ID_2,
    CLIENT_ID_3,
    CLIENT_TRANSACTION_ID_0,
    CLIENT_TRANSACTION_ID_1,
    CLIENT_TRANSACTION_ID_2,
    CLIENT_TRANSACTION_ID_3,
    INTERNAL_CLIENT_TRANSACTION_ID_0,
    ContractTest,
    Deposit,
    Transaction,
    Withdrawal,
    balance_dimensions,
)
from inception_sdk.vault.contracts.types import DEFAULT_ADDRESS
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ASSET,
    Balance,
    BalanceDefaultDict,
    EventTypeSchedule,
    OptionalValue,
    PostingInstruction,
    Rejected,
    Tside,
    UnionItemValue,
)

UTILS_MODULE_FILE = "library/common/contract_modules/utils.py"
INTEREST_MODULE_FILE = "library/common/contract_modules/interest.py"

DEFAULT_DENOMINATION = "USD"
DEFAULT_DATE = datetime(2019, 1, 1)
HOOK_EXECUTION_ID = "hook_execution_id"
PNL_ACCOUNT = "1"
VAULT_ACCOUNT_ID = "Main account"
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
ACCRUED_INTEREST_PAYABLE_ADDRESS = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
MAINTENANCE_FEE_INCOME_ACCOUNT = "MAINTENANCE_FEE_INCOME"
EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT = "EXCESS_WITHDRAWALS_INCOME"
MINIMUM_BALANCE_FEE_INCOME_ACCOUNT = "MINIMUM_BALANCE_INCOME"
INTERNAL_CONTRA = "INTERNAL_CONTRA"
INTERNAL_POSTING = "INTERNAL_POSTING"
UNSET_OPTIONAL_VALUE = OptionalValue(is_set=False)
PROMOTIONAL_INTEREST_RATES = "PROMOTIONAL_INTEREST_RATES"
PROMOTIONAL_MAINTENANCE_FEE = "PROMOTIONAL_MAINTENANCE_FEE"

BALANCE_TIER_RANGES = json.dumps(
    {
        "tier1": {"min": "0", "max": "5000.00"},
        "tier2": {"min": "5000.00", "max": "15000.00"},
        "tier3": {"min": "15000.00"},
    }
)
TIERED_INTEREST_RATES = json.dumps(
    {
        "UPPER_TIER": {
            "tier1": "0.02",
            "tier2": "0.015",
            "tier3": "-0.01",
        },
        "MIDDLE_TIER": {
            "tier1": "0.0125",
            "tier2": "0.01",
            "tier3": "-0.015",
        },
        "LOWER_TIER": {
            "tier1": "0",
            "tier2": "0.1485",
            "tier3": "-0.1485",
        },
    }
)
PROMOTION_RATES = json.dumps(
    {
        "UPPER_TIER": {
            "tier1": "0.04",
            "tier2": "0.03",
            "tier3": "0",
        },
        "MIDDLE_TIER": {
            "tier1": "0.025",
            "tier2": "0.02",
            "tier3": "0",
        },
        "LOWER_TIER": {
            "tier1": "-0.1",
            "tier2": "0",
            "tier3": "0.3",
        },
    }
)
TIERED_MIN_BALANCE_THRESHOLD = json.dumps(
    {
        "UPPER_TIER": "25",
        "MIDDLE_TIER": "75",
        "LOWER_TIER": "100",
    }
)
ACCOUNT_TIER_NAMES = json.dumps(
    [
        "UPPER_TIER",
        "MIDDLE_TIER",
        "LOWER_TIER",
    ]
)

MAINTENANCE_FEE_MONTHLY = json.dumps(
    {
        "UPPER_TIER": "10",
        "MIDDLE_TIER": "20",
        "LOWER_TIER": "30",
    }
)
PROMOTIONAL_MAINTENANCE_FEE_MONTHLY = json.dumps(
    {
        "UPPER_TIER": "5",
        "MIDDLE_TIER": "10",
        "LOWER_TIER": "15",
    }
)


class SavingsAccountBaseTest(ContractTest):
    default_denom = "USD"
    contract_file = US_SAVINGS_TEMPLATE
    side = Tside.LIABILITY
    linked_contract_modules = {
        "interest": {
            "path": INTEREST_MODULE_FILE,
        },
        "utils": {
            "path": UTILS_MODULE_FILE,
        },
    }

    def create_mock(self, **kwargs):
        return super().create_mock(
            balance_tier_ranges=(
                kwargs.pop("balance_tier_ranges")
                if "balance_tier_ranges" in kwargs
                else BALANCE_TIER_RANGES
            ),
            tiered_interest_rates=(
                kwargs.pop("tiered_interest_rates")
                if "tiered_interest_rates" in kwargs
                else TIERED_INTEREST_RATES
            ),
            promotional_rates=(
                kwargs.pop("promotional_rates")
                if "promotional_rates" in kwargs
                else PROMOTION_RATES
            ),
            accrued_interest_payable_account=(
                kwargs.pop("accrued_interest_payable_account")
                if "accrued_interest_payable_account" in kwargs
                else ACCRUED_INTEREST_PAYABLE_ACCOUNT
            ),
            interest_paid_account=(
                kwargs.pop("interest_paid_account")
                if "interest_paid_account" in kwargs
                else INTEREST_PAID_ACCOUNT
            ),
            accrued_interest_receivable_account=(
                kwargs.pop("accrued_interest_receivable_account")
                if "accrued_interest_receivable_account" in kwargs
                else ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
            ),
            interest_received_account=(
                kwargs.pop("interest_received_account")
                if "interest_received_account" in kwargs
                else INTEREST_RECEIVED_ACCOUNT
            ),
            excess_withdrawal_fee_income_account=(
                kwargs.pop("excess_withdrawal_fee_income_account")
                if "excess_withdrawal_fee_income_account" in kwargs
                else EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT
            ),
            maintenance_fee_income_account=(
                kwargs.pop("maintenance_fee_income_account")
                if "maintenance_fee_income_account" in kwargs
                else MAINTENANCE_FEE_INCOME_ACCOUNT
            ),
            minimum_balance_fee_income_account=(
                kwargs.pop("minimum_balance_fee_income_account")
                if "minimum_balance_fee_income_account" in kwargs
                else MINIMUM_BALANCE_FEE_INCOME_ACCOUNT
            ),
            days_in_year=(
                kwargs.pop("days_in_year") if "days_in_year" in kwargs else UnionItemValue("actual")
            ),
            interest_accrual_hour=(
                kwargs.pop("interest_accrual_hour") if "interest_accrual_hour" in kwargs else 0
            ),
            interest_accrual_minute=(
                kwargs.pop("interest_accrual_minute") if "interest_accrual_minute" in kwargs else 0
            ),
            interest_accrual_second=(
                kwargs.pop("interest_accrual_second") if "interest_accrual_second" in kwargs else 0
            ),
            interest_application_hour=(
                kwargs.pop("interest_application_hour")
                if "interest_application_hour" in kwargs
                else 0
            ),
            interest_application_minute=(
                kwargs.pop("interest_application_minute")
                if "interest_application_minute" in kwargs
                else 0
            ),
            interest_application_second=(
                kwargs.pop("interest_application_second")
                if "interest_application_second" in kwargs
                else 0
            ),
            interest_application_frequency=(
                kwargs.pop("interest_application_frequency")
                if "interest_application_frequency" in kwargs
                else UnionItemValue("monthly")
            ),
            maintenance_fee_monthly=(
                kwargs.pop("maintenance_fee_monthly") if "maintenance_fee_monthly" in kwargs else 0
            ),
            promotional_maintenance_fee_monthly=(
                kwargs.pop("promotional_maintenance_fee_monthly")
                if "promotional_maintenance_fee_monthly" in kwargs
                else PROMOTIONAL_MAINTENANCE_FEE_MONTHLY
            ),
            maintenance_fee_annual=(
                kwargs.pop("maintenance_fee_annual") if "maintenance_fee_annual" in kwargs else 0
            ),
            monthly_withdrawal_limit=(
                kwargs.pop("monthly_withdrawal_limit")
                if "monthly_withdrawal_limit" in kwargs
                else -1
            ),
            reject_excess_withdrawals=(
                kwargs.pop("reject_excess_withdrawals")
                if "reject_excess_withdrawals" in kwargs
                else UnionItemValue("true")
            ),
            excess_withdrawal_fee=(
                kwargs.pop("excess_withdrawal_fee")
                if "excess_withdrawal_fee" in kwargs
                else Decimal("10.00")
            ),
            fees_application_hour=(
                kwargs.pop("fees_application_hour") if "fees_application_hour" in kwargs else 0
            ),
            fees_application_minute=(
                kwargs.pop("fees_application_minute") if "fees_application_minute" in kwargs else 0
            ),
            fees_application_second=(
                kwargs.pop("fees_application_second") if "fees_application_second" in kwargs else 0
            ),
            tiered_minimum_balance_threshold=(
                kwargs.pop("tiered_minimum_balance_threshold")
                if "tiered_minimum_balance_threshold" in kwargs
                else TIERED_MIN_BALANCE_THRESHOLD
            ),
            minimum_balance_fee=(
                kwargs.pop("minimum_balance_fee") if "minimum_balance_fee" in kwargs else 0
            ),
            account_tier_names=(
                kwargs.pop("account_tier_names")
                if "account_tier_names" in kwargs
                else ACCOUNT_TIER_NAMES
            ),
            **kwargs,
        )

    def account_balances(
        self,
        dt=DEFAULT_DATE,
        denomination=DEFAULT_DENOMINATION,
        accrued_payable=Decimal(0),
        internal_contra=Decimal(0),
        default_committed=Decimal(0),
        accrued_receivable=Decimal(0),
        overdraft_fee=Decimal(0),
    ) -> list[tuple[datetime, BalanceDefaultDict]]:
        return [
            (
                dt,
                BalanceDefaultDict(
                    lambda: Balance(),
                    {
                        balance_dimensions(denomination=denomination): Balance(
                            net=default_committed
                        ),
                        balance_dimensions(
                            denomination=denomination, address="ACCRUED_INTEREST_PAYABLE"
                        ): Balance(net=accrued_payable),
                        balance_dimensions(
                            denomination=denomination, address="ACCRUED_INTEREST_RECEIVABLE"
                        ): Balance(net=accrued_receivable),
                        balance_dimensions(
                            denomination=denomination, address="INTERNAL_CONTRA"
                        ): Balance(net=internal_contra),
                        balance_dimensions(
                            denomination=denomination, address="OVERDRAFT_FEE"
                        ): Balance(net=overdraft_fee),
                        balance_dimensions(denomination=denomination, address="DEFAULT"): Balance(
                            net=default_committed
                        ),
                    },
                ),
            )
        ]


class SavingsAccountTest(SavingsAccountBaseTest):
    def test_execution_schedules_update_to_last_valid_day_of_month(self):
        default_committed = Decimal(2000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            interest_application_day=28,
            denomination="USD",
            creation_date=DEFAULT_DATE,
            APPLY_ACCRUED_INTEREST=datetime(2020, 2, 1),
        )

        expected_schedule = EventTypeSchedule(
            year="2020",
            month="2",
            day="28",
            hour="0",
            minute="0",
            second="0",
        )

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"interest_application_day": "31"},
            updated_parameter_values={"interest_application_day": "28"},
            effective_date=datetime(2020, 2, 1, 1),
        )

        mock_vault.update_event_type.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST", schedule=expected_schedule
        )

    def test_scheduled_code_accrue_interest_with_payable_and_receivable_tiered_interest(
        self,
    ):
        accrue_interest_date = DEFAULT_DATE
        end_of_day = accrue_interest_date - timedelta(microseconds=1)
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1),
            default_committed=Decimal("25000"),
        )
        mock_vault = self.create_mock(balance_ts=balance_ts, denomination="USD")
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST",
            effective_date=accrue_interest_date,
        )
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("4.06849"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="ACCRUE_INTEREST_TIER2_MOCK_HOOK_"
                    "ACCRUED_INTEREST_PAYABLE_COMMERCIAL_BANK_MONEY_USD",
                    from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id="Main account",
                    to_account_address=ACCRUED_INTEREST_PAYABLE_ADDRESS,
                    instruction_details={
                        "description": "Daily interest accrued at 0.04068% on balance of 10000.00.",
                        "event": "ACCRUE_INTEREST",
                        "gl_impacted": "True",
                        "account_type": "US_SAVINGS",
                    },
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("4.06849"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="ACCRUE_INTEREST_TIER3_MOCK_HOOK_ACCRUED_"
                    "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
                    from_account_id="Main account",
                    from_account_address="ACCRUED_INTEREST_RECEIVABLE",
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": "Daily interest accrued at -0.04068% "
                        "on balance of 10000.00.",
                        "event": "ACCRUE_INTEREST",
                        "gl_impacted": "True",
                        "account_type": "US_SAVINGS",
                    },
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=[
                "ACCRUE_INTEREST_TIER2_MOCK_HOOK_ACCRUED_"
                "INTEREST_PAYABLE_COMMERCIAL_BANK_MONEY_USD",
                "ACCRUE_INTEREST_TIER3_MOCK_HOOK_ACCRUED_"
                "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
            ],
            effective_date=end_of_day,
        )

    def test_interest_applies_when_exceeding_available_balance(self):
        default_committed = Decimal("0.5")
        accrued_receivable = Decimal("-1.50")
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            accrued_receivable=accrued_receivable,
            default_committed=default_committed,
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts, denomination="USD", interest_application_day=28
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("1.5"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    client_transaction_id="APPLY_INTEREST_PRIMARY_MOCK_HOOK_ACCRUED_"
                    "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                        "gl_impacted": "True",
                        "account_type": "US_SAVINGS",
                    },
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("1.5"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address="ACCRUED_INTEREST_RECEIVABLE",
                    client_transaction_id="APPLY_INTEREST_OFFSET_MOCK_HOOK_ACCRUED_"
                    "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                        "gl_impacted": "True",
                        "account_type": "US_SAVINGS",
                    },
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK_USD",
            posting_instructions=[
                "APPLY_INTEREST_PRIMARY_MOCK_HOOK_ACCRUED_"
                "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
                "APPLY_INTEREST_OFFSET_MOCK_HOOK_ACCRUED_"
                "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
            ],
            effective_date=DEFAULT_DATE,
        )

    def test_scheduled_code_does_not_accrue_outside_tier_ranges(self):
        accrue_interest_date = DEFAULT_DATE
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1),
            default_committed=Decimal(-100),
        )
        mock_vault = self.create_mock(balance_ts=balance_ts, denomination="USD")
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST",
            effective_date=accrue_interest_date,
        )
        self.assert_no_side_effects(mock_vault)

    def test_scheduled_code_accrue_interest_when_tiered_interest_is_zero(self):

        accrue_interest_date = DEFAULT_DATE + timedelta(hours=5)
        default_committed = Decimal(5000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(balance_ts=balance_ts, denomination="USD")

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST",
            effective_date=accrue_interest_date,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_scheduled_code_apply_accrued_interest_with_remainder_creates_reverse(
        self,
    ):
        input_data = [
            (
                "payable accrued, negative remainder",
                "4.06849",
                "4.07",
                "0.00151",
                INTEREST_PAID_ACCOUNT,
                DEFAULT_ADDRESS,
                VAULT_ACCOUNT_ID,
                DEFAULT_ADDRESS,
                False,
                ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                DEFAULT_ADDRESS,
                VAULT_ACCOUNT_ID,
                ACCRUED_INTEREST_PAYABLE_ADDRESS,
                "PAYABLE",
            ),
            (
                "payable accrued, positive remainder",
                "1.004",
                "1.00",
                "0.004",
                INTEREST_PAID_ACCOUNT,
                DEFAULT_ADDRESS,
                VAULT_ACCOUNT_ID,
                DEFAULT_ADDRESS,
                True,
                ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                DEFAULT_ADDRESS,
                VAULT_ACCOUNT_ID,
                ACCRUED_INTEREST_PAYABLE_ADDRESS,
                "PAYABLE",
            ),
            (
                "receivable accrued, positive remainder",
                "4.06849",
                "4.07",
                "0.00151",
                VAULT_ACCOUNT_ID,
                DEFAULT_ADDRESS,
                INTEREST_RECEIVED_ACCOUNT,
                DEFAULT_ADDRESS,
                False,
                VAULT_ACCOUNT_ID,
                "ACCRUED_INTEREST_RECEIVABLE",
                ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                DEFAULT_ADDRESS,
                "RECEIVABLE",
            ),
            (
                "receivable accrued, negative remainder",
                "1.004",
                "1.00",
                "0.004",
                VAULT_ACCOUNT_ID,
                DEFAULT_ADDRESS,
                INTEREST_RECEIVED_ACCOUNT,
                DEFAULT_ADDRESS,
                True,
                VAULT_ACCOUNT_ID,
                "ACCRUED_INTEREST_RECEIVABLE",
                ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                DEFAULT_ADDRESS,
                "RECEIVABLE",
            ),
        ]

        accrue_interest_date = DEFAULT_DATE
        start_of_day = accrue_interest_date
        default_committed = Decimal("10000")

        for input_row in input_data:
            test_name = input_row[0]
            incoming_amount = input_row[1]
            rounded_amount = input_row[2]
            remainder = input_row[3]
            from_account_id = input_row[4]
            from_account_address = input_row[5]
            to_account_id = input_row[6]
            to_account_address = input_row[7]
            switch_reverse = input_row[8]
            from_account_id_reverse = input_row[9]
            from_account_address_reverse = input_row[10]
            to_account_id_reverse = input_row[11]
            to_account_address_reverse = input_row[12]
            interest_type = input_row[13]

            positive_remainder = Decimal(incoming_amount) > Decimal(rounded_amount)

            if test_name[0] == "r":
                accrued_receivable = -Decimal(incoming_amount)
                accrued_payable = Decimal(0)
            else:
                accrued_receivable = Decimal(0)
                accrued_payable = Decimal(incoming_amount)

            balance_ts = self.account_balances(
                DEFAULT_DATE,
                accrued_receivable=accrued_receivable,
                accrued_payable=accrued_payable,
                default_committed=default_committed,
            )

            mock_vault = self.create_mock(
                balance_ts=balance_ts, denomination="USD", interest_application_day=28
            )

            self.run_function(
                "scheduled_code",
                mock_vault,
                event_type="APPLY_ACCRUED_INTEREST",
                effective_date=accrue_interest_date,
            )

            remainder_prefix = "REVERSE_ACCRUED" if positive_remainder else "ACCRUE"
            remainder_transaction_id = (
                f"{remainder_prefix}_INTEREST_MOCK_HOOK"
                + f"_ACCRUED_INTEREST_{interest_type}_COMMERCIAL_BANK_MONEY_USD"
            )

            calls = [
                call(
                    amount=Decimal(rounded_amount),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id=f"APPLY_INTEREST_PRIMARY_MOCK_HOOK_ACCRUED_"
                    f"INTEREST_{interest_type}_COMMERCIAL_BANK_MONEY_USD",
                    from_account_id=from_account_id,
                    from_account_address=from_account_address,
                    to_account_id=to_account_id,
                    to_account_address=to_account_address,
                    instruction_details={
                        "event": "APPLY_ACCRUED_INTEREST",
                        "description": "Interest Applied.",
                        "gl_impacted": "True",
                        "account_type": "US_SAVINGS",
                    },
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal(rounded_amount),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id=f"APPLY_INTEREST_OFFSET_MOCK_HOOK_ACCRUED_"
                    f"INTEREST_{interest_type}_COMMERCIAL_BANK_MONEY_USD",
                    from_account_id=to_account_id_reverse,
                    from_account_address=to_account_address_reverse,
                    to_account_id=from_account_id_reverse,
                    to_account_address=from_account_address_reverse,
                    instruction_details={
                        "event": "APPLY_ACCRUED_INTEREST",
                        "description": "Interest Applied.",
                        "gl_impacted": "True",
                        "account_type": "US_SAVINGS",
                    },
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                ),
            ]

            if switch_reverse:
                tmp = from_account_id_reverse
                from_account_id_reverse = to_account_id_reverse
                to_account_id_reverse = tmp

                tmp = from_account_address_reverse
                from_account_address_reverse = to_account_address_reverse
                to_account_address_reverse = tmp

            calls.extend(
                [
                    call(
                        amount=Decimal(remainder),
                        denomination=DEFAULT_DENOMINATION,
                        client_transaction_id=remainder_transaction_id.format(""),
                        from_account_id=from_account_id_reverse,
                        from_account_address=from_account_address_reverse,
                        to_account_id=to_account_id_reverse,
                        to_account_address=to_account_address_reverse,
                        asset=DEFAULT_ASSET,
                        instruction_details={
                            "event": "APPLY_ACCRUED_INTEREST",
                            "description": "Zero out remainder after accrued interest applied.",
                            "gl_impacted": "True",
                            "account_type": "US_SAVINGS",
                        },
                        override_all_restrictions=True,
                    )
                ]
            )
            mock_vault.make_internal_transfer_instructions.assert_has_calls(calls)

            mock_vault.instruct_posting_batch.assert_called_with(
                client_batch_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK_USD",
                posting_instructions=[
                    f"APPLY_INTEREST_PRIMARY_MOCK_HOOK_ACCRUED_"
                    f"INTEREST_{interest_type}_COMMERCIAL_BANK_MONEY_USD",
                    f"APPLY_INTEREST_OFFSET_MOCK_HOOK_ACCRUED_"
                    f"INTEREST_{interest_type}_COMMERCIAL_BANK_MONEY_USD",
                    remainder_transaction_id.format("GL_CUSTOMER"),
                ],
                effective_date=start_of_day,
            )

    def test_scheduled_code_applied_receivable_interest_with_no_remainder_has_no_reverse_postings(
        self,
    ):

        accrue_interest_date = DEFAULT_DATE
        start_of_day = accrue_interest_date
        accrued_receivable = Decimal("-4.0")
        default_committed = Decimal("10000")

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            accrued_receivable=accrued_receivable,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts, denomination="USD", interest_application_day=28
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            effective_date=accrue_interest_date,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("4.0"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    client_transaction_id="APPLY_INTEREST_PRIMARY_MOCK_HOOK_ACCRUED_"
                    "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
                    instruction_details={
                        "event": "APPLY_ACCRUED_INTEREST",
                        "description": "Interest Applied.",
                        "gl_impacted": "True",
                        "account_type": "US_SAVINGS",
                    },
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("4.0"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id="Main account",
                    to_account_address="ACCRUED_INTEREST_RECEIVABLE",
                    client_transaction_id="APPLY_INTEREST_OFFSET_MOCK_HOOK_ACCRUED_"
                    "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
                    instruction_details={
                        "event": "APPLY_ACCRUED_INTEREST",
                        "description": "Interest Applied.",
                        "gl_impacted": "True",
                        "account_type": "US_SAVINGS",
                    },
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK_USD",
            posting_instructions=[
                "APPLY_INTEREST_PRIMARY_MOCK_HOOK_ACCRUED_"
                "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
                "APPLY_INTEREST_OFFSET_MOCK_HOOK_ACCRUED_"
                "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
            ],
            effective_date=start_of_day,
        )

    def test_scheduled_code_apply_accrue_interest_when_accrued_payable_is_zero(self):

        accrue_interest_date = DEFAULT_DATE
        accrued_payable = Decimal(0)
        default_committed = Decimal(10000)

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            accrued_payable=accrued_payable,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts, denomination="USD", interest_application_day=28
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            effective_date=accrue_interest_date,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_scheduled_code_apply_accrue_interest_with_small_accrue_interest(self):

        # this test should only create reverse posting

        accrue_interest_date = DEFAULT_DATE
        start_of_day = accrue_interest_date
        accrued_receivable = Decimal("-0.001")
        default_committed = Decimal(10000)

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            accrued_receivable=accrued_receivable,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts, denomination="USD", interest_application_day=28
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            effective_date=accrue_interest_date,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.001"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id="Main account",
                    to_account_address="ACCRUED_INTEREST_RECEIVABLE",
                    client_transaction_id="REVERSE_ACCRUED_INTEREST_MOCK_HOOK_ACCRUED_"
                    "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
                    instruction_details={
                        "event": "APPLY_ACCRUED_INTEREST",
                        "description": "Zero out remainder after accrued interest applied.",
                        "gl_impacted": "True",
                        "account_type": "US_SAVINGS",
                    },
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK_USD",
            posting_instructions=[
                "REVERSE_ACCRUED_INTEREST_MOCK_HOOK_ACCRUED_"
                "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
            ],
            effective_date=start_of_day,
        )

    def test_post_parameter_change_code_amends_schedule_to_new_interest_application_day(
        self,
    ):

        default_committed = Decimal(2000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            interest_application_day=12,
            denomination="USD",
            creation_date=DEFAULT_DATE,
            APPLY_ACCRUED_INTEREST=datetime(2020, 1, 1),
        )
        expected_schedule = EventTypeSchedule(
            year="2019",
            month="1",
            day="12",
            hour="0",
            minute="0",
            second="0",
        )

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"interest_application_day": "28"},
            updated_parameter_values={"interest_application_day": "12"},
            effective_date=DEFAULT_DATE,
        )

        mock_vault.update_event_type.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST", schedule=expected_schedule
        )

    def test_post_parameter_change_code_with_undefined_new_interest_application_day(
        self,
    ):

        #  This test should not call amend schedule
        default_committed = Decimal(2000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
        )

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"interest_application_day": "28"},
            updated_parameter_values={"not_interest_application_day_parameter": "12"},
            effective_date=DEFAULT_DATE,
        )
        mock_vault.update_event_type.assert_not_called()

    def test_post_parameter_change_code_with_unchanged_interest_application_day(self):

        # this test should not call amend_schedule

        default_committed = Decimal(2000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            interest_application_day=28,
        )

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"interest_application_day": "28"},
            updated_parameter_values={"interest_application_day": "28"},
            effective_date=DEFAULT_DATE,
        )
        mock_vault.update_event_type.assert_not_called()

    def test_pre_posting_code_rejects_wrong_denomination(self):
        default_committed = Decimal(2000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            minimum_deposit=Decimal(50),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=Decimal(100),
            minimum_withdrawal=Decimal(0.01),
        )
        test_posting = self.outbound_auth(amount="1", denomination="HKD")

        pib = self.mock_posting_instruction_batch(posting_instructions=[test_posting])

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                DEFAULT_DATE,
            )

        expected_rejection_error = (
            f"Cannot make transactions in given"
            f" denomination; transactions must be in "
            f"{DEFAULT_DENOMINATION}"
        )

        self.assertEqual(str(e.exception), expected_rejection_error)

    def test_pre_posting_code_allows_unsupported_denom_with_override(self):
        default_committed = Decimal(1)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            minimum_deposit=Decimal(50),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=Decimal(100),
            minimum_withdrawal=Decimal(0.01),
        )
        test_posting = self.outbound_auth(denomination="HKD", amount=Decimal(1))

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[test_posting],
            batch_details={"force_override": "true"},
        )

        self.run_function(
            "pre_posting_code",
            mock_vault,
            pib,
            DEFAULT_DATE,
        )

        self.assert_no_side_effects(mock_vault)

    def test_pre_posting_code_allows_negative_balance_with_override(self):
        default_committed = Decimal(1)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            gross_interest_rate=Decimal(0.1485),
            minimum_deposit=Decimal(50),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=Decimal(100),
            minimum_withdrawal=Decimal(0.01),
        )
        test_posting = self.outbound_hard_settlement(denomination="USD", amount=Decimal(50))

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[test_posting],
            batch_details={"force_override": "true"},
        )

        self.run_function(
            "pre_posting_code",
            mock_vault,
            pib,
            DEFAULT_DATE,
        )

        self.assert_no_side_effects(mock_vault)

    def test_pre_posting_code_rejects_insufficient_funds(self):
        default_committed = Decimal(0)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            minimum_deposit=Decimal(50),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=Decimal(100),
            minimum_withdrawal=Decimal(0.01),
        )
        test_posting = self.outbound_auth(denomination="USD", amount=Decimal(100))

        pib = self.mock_posting_instruction_batch(posting_instructions=[test_posting])

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                DEFAULT_DATE,
            )

        expected_rejection_error = "Insufficient funds for transaction."

        self.assertEqual(str(e.exception), expected_rejection_error)

    def test_pre_posting_code_rejects_exceeding_max_balance(self):
        default_committed = Decimal(99990)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            minimum_deposit=Decimal(50),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=Decimal(100),
            minimum_withdrawal=Decimal(0.01),
        )
        test_posting = self.inbound_auth(denomination="USD", amount=Decimal(100))

        pib = self.mock_posting_instruction_batch(posting_instructions=[test_posting])

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                DEFAULT_DATE,
            )

        expected_rejection_error = "Posting would cause the maximum " "balance to be exceeded."

        self.assertEqual(str(e.exception), expected_rejection_error)

    def test_pre_posting_code_rejects_single_deposit_below_min_amount(self):

        default_committed = Decimal(2000)

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )
        pib, client_transactions, _ = self.pib_and_cts_for_transactions(
            hook_effective_date=DEFAULT_DATE,
            transactions=[Deposit(amount="9", effective_date=DEFAULT_DATE)],
        )

        minimum_deposit = Decimal(10)
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            client_transaction=client_transactions,
            minimum_deposit=minimum_deposit,
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=Decimal(100),
            minimum_withdrawal=Decimal(10),
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                datetime(2020, 9, 27),
            )

            expected_rejection_error = (
                f"Transaction amount is less than the minimum deposit"
                f"amount {minimum_deposit} {DEFAULT_DENOMINATION}."
            )

            self.assertEqual(str(e.exception), expected_rejection_error)

    def test_pre_posting_code_rejects_deposits_below_min_amount_whith_mixed_multiple_postings(
        self,
    ):

        #   posting_life_cycle_1 for the first client transaction: Send £50 to an external account:
        #   initial posting of £50 goes into pending.out as a debit during authorisation
        #   then committed will have £50 debitted during sttlement

        #   posting_life_cycle_2 for the second client transaction:
        #   Send £10 to an external account which is below min withdrawal amount of £10
        #   Pending_out will have debit of £10 during authorisation

        #   posting_life_cycle_3 for the 3rd client transaction:
        #   amount of £9 is depositted into this account
        #   this means, pending_in pot will have £9 creditted during authorisation
        #   however, this is when pre-posting hook should reject this transaction

        effective_date = datetime(2020, 9, 7)
        default_committed = Decimal(2000)

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )
        ct_0_postings = [
            self.outbound_auth(
                amount="50",
                value_timestamp=effective_date - timedelta(days=3),
                client_transaction_id=CLIENT_TRANSACTION_ID_0,
                client_id=CLIENT_ID_0,
            ),
            self.settle_outbound_auth(
                final=True,
                unsettled_amount="50",
                value_timestamp=effective_date - timedelta(days=2),
                client_transaction_id=CLIENT_TRANSACTION_ID_0,
                client_id=CLIENT_ID_0,
            ),
        ]
        ct_1_postings = [
            self.outbound_auth(
                amount="10",
                value_timestamp=effective_date - timedelta(days=1),
                client_transaction_id=CLIENT_TRANSACTION_ID_1,
                client_id=CLIENT_ID_1,
            ),
        ]
        ct_2_postings = [
            self.inbound_auth(
                amount="9",
                value_timestamp=effective_date,
                client_transaction_id=CLIENT_TRANSACTION_ID_2,
                client_id=CLIENT_ID_2,
            )
        ]
        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=effective_date,
            posting_instructions_groups=[ct_0_postings, ct_1_postings, ct_2_postings],
        )
        minimum_deposit = Decimal(10)
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            client_transaction=client_transactions,
            minimum_deposit=minimum_deposit,
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=Decimal(100),
            minimum_withdrawal=Decimal(10),
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,  # `postings` in `pre_posting_code`
                DEFAULT_DATE,  # `effective_date` in `pre_posting_code`
            )

            expected_rejection_error = (
                f"Transaction amount is less than the minimum deposit amount"
                f" {minimum_deposit} {DEFAULT_DENOMINATION}."
            )

            self.assertEqual(str(e.exception), expected_rejection_error)

    def test_pre_posting_code_rejects_deposits_exceeds_max_daily_deposit_for_single_posting(
        self,
    ):

        #   posting_life_cycle_1 for the first client transaction:
        #   Receive £1001 from an external account:
        #   initial posting of £1001 goes into pending.in as a credit during authorisation
        #   then committed will have £1001 creditted during sttlement

        effective_date = datetime(2020, 9, 27)
        default_committed = Decimal(2000)

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )
        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=effective_date,
            posting_instructions_groups=[
                [
                    self.inbound_auth(
                        amount="1001",
                        denomination=self.default_denom,
                        value_timestamp=effective_date - timedelta(days=1),
                    ),
                    self.settle_inbound_auth(
                        final=True,
                        unsettled_amount="1001",
                        denomination=self.default_denom,
                        value_timestamp=effective_date,
                    ),
                ]
            ],
        )

        maximum_daily_deposit = Decimal(1000)
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            client_transaction=client_transactions,
            minimum_deposit=Decimal(10),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=maximum_daily_deposit,
            maximum_daily_withdrawal=Decimal(100),
            minimum_withdrawal=Decimal(10),
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,  # `postings` in `pre_posting_code`
                DEFAULT_DATE,  # `effective_date` in `pre_posting_code`
            )
            expected_rejection_error = (
                f"Transaction would cause the maximum daily deposit limit of"
                f" {maximum_daily_deposit} {DEFAULT_DENOMINATION}"
                f" to be exceeded."
            )

            self.assertEqual(str(e.exception), expected_rejection_error)

    def test_pre_posting_code_rejects_deposits_exceeding_max_daily_deposit(self):

        # this is for sum of multiple postings

        #   posting_life_cycle_1: for the first client transaction,
        #   receive £501 from an external account as hard settlement.
        #   This means posting of £501 goes into committed as a credit during hard settlement
        #   posting_life_cycle_2: this has £500 in committed pot during settlement

        effective_date = datetime(2020, 9, 7)
        default_committed = Decimal(2000)

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )
        pib, client_transactions, _ = self.pib_and_cts_for_transactions(
            hook_effective_date=effective_date,
            transactions=[
                Deposit(amount="501", effective_date=effective_date - timedelta(days=1)),
                Deposit(amount="500", effective_date=effective_date),
            ],
        )

        maximum_daily_deposit = Decimal(1000)
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            client_transaction=client_transactions,
            minimum_deposit=Decimal(10),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=maximum_daily_deposit,
            maximum_daily_withdrawal=Decimal(100),
            minimum_withdrawal=Decimal(10),
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,  # `postings` in `pre_posting_code`
                DEFAULT_DATE,  # `effective_date` in `pre_posting_code`
            )

            expected_rejection_error = (
                f"Transaction would cause the maximum daily deposit limit of"
                f" {maximum_daily_deposit} {DEFAULT_DENOMINATION}"
                f" to be exceeded."
            )

            self.assertEqual(str(e.exception), expected_rejection_error)

    def test_sum_without_current_client_trans_when_trans_cancelled(self):

        # this is when client transactions are cancelled.
        effective_date = datetime(2020, 9, 7)

        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=effective_date,
            posting_instructions_groups=[
                [
                    self.outbound_auth(
                        amount="100",
                        denomination=self.default_denom,
                        value_timestamp=effective_date - timedelta(days=1),
                    ),
                    self.release_outbound_auth(
                        unsettled_amount="100",
                        denomination=self.default_denom,
                        value_timestamp=effective_date,
                    ),
                ]
            ],
        )

        result = self.run_function(
            "_sum_without_current_client_trans",
            None,
            client_transactions=client_transactions,
            client_transaction_id="dummy",
            cutoff_timestamp=DEFAULT_DATE,
            denomination="USD",
        )

        self.assertEqual(result, (0, 0))

    def test_sum_without_current_client_trans_when_client_id_same_as_trans_id(self):

        #  check than when client transaction is same as client_transaction_id
        #  then amount that we are summing up to check against limit, will be zero.

        #   posting_life_cycle_1:
        #   receive £501 from an external account as hard settlement with same trans IDs

        effective_date = datetime(2020, 9, 7)

        _, client_transactions, _ = self.pib_and_cts_for_transactions(
            hook_effective_date=effective_date,
            transactions=[Deposit(amount="501", effective_date=effective_date)],
        )

        result = self.run_function(
            "_sum_without_current_client_trans",
            None,
            client_transactions=client_transactions,
            client_transaction_id="CT_ID_0",
            cutoff_timestamp=DEFAULT_DATE,
            denomination="USD",
        )

        self.assertEqual(result, (0, 0))

    def test_invalid_day_defaults_to_last_day_of_month(self):

        effective_date = datetime(2019, 9, 1)
        intended_day = 31
        mock_vault = self.create_mock(interest_application_day=intended_day)
        result = self.run_function(
            "_get_next_interest_application_day",
            None,
            mock_vault,
            effective_date,
        )

        self.assertEqual(result, datetime(2019, 9, 30, 0, 0, 0))

        # Leap year edge case
        effective_date = datetime(2020, 2, 1)
        result = self.run_function(
            "_get_next_interest_application_day",
            None,
            mock_vault,
            effective_date,
        )

        self.assertEqual(result, datetime(2020, 2, 29, 0, 0, 0))

    def test_close_code_reverses_accrued_interest(self):
        input_data = [
            (
                "PAYABLE",
                "10.78980",
                VAULT_ACCOUNT_ID,
                ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                "ACCRUED_INTEREST_PAYABLE",
                DEFAULT_ADDRESS,
            ),
            (
                "RECEIVABLE",
                "-10.78980",
                ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                VAULT_ACCOUNT_ID,
                DEFAULT_ADDRESS,
                "ACCRUED_INTEREST_RECEIVABLE",
            ),
        ]

        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal(300)

        for (
            interest_type,
            accrued_interest,
            from_account_id,
            to_account_id,
            from_cust_address,
            to_cust_address,
        ) in input_data:

            if interest_type == "PAYABLE":
                accrued_payable = Decimal(accrued_interest)
                accrued_receivable = Decimal(0)
            else:
                accrued_receivable = Decimal(accrued_interest)
                accrued_payable = Decimal(0)

            balance_ts = self.account_balances(
                effective_time,
                default_committed=default_committed,
                accrued_payable=accrued_payable,
                accrued_receivable=accrued_receivable,
            )

            mock_vault = self.create_mock(
                balance_ts=balance_ts,
                denomination=DEFAULT_DENOMINATION,
            )

            self.run_function("close_code", mock_vault, effective_date=effective_time)
            mock_vault.make_internal_transfer_instructions.assert_has_calls(
                [
                    call(
                        amount=abs(Decimal(accrued_interest)),
                        denomination=DEFAULT_DENOMINATION,
                        client_transaction_id=f"REVERSE_ACCRUED_INTEREST_MOCK_HOOK_ACCRUED_"
                        f"INTEREST_{interest_type}_COMMERCIAL_BANK_MONEY_USD",
                        from_account_id=from_account_id,
                        from_account_address=from_cust_address,
                        to_account_id=to_account_id,
                        to_account_address=to_cust_address,
                        asset=DEFAULT_ASSET,
                        instruction_details={
                            "description": "Reverse accrued interest due to account" " closure",
                            "event": "CLOSE_ACCOUNT",
                            "gl_impacted": "True",
                            "account_type": "US_SAVINGS",
                        },
                        override_all_restrictions=True,
                    ),
                ]
            )
            mock_vault.instruct_posting_batch.assert_called_with(
                client_batch_id="REVERSE_ACCRUED_INTEREST_MOCK_HOOK_USD",
                posting_instructions=[
                    f"REVERSE_ACCRUED_INTEREST_MOCK_HOOK_ACCRUED_"
                    f"INTEREST_{interest_type}_COMMERCIAL_BANK_MONEY_USD",
                ],
                effective_date=effective_time,
            )

    def test_apply_interest_frequency_annually(self):
        mock_vault = self.create_mock(
            interest_application_day=28,
            interest_application_frequency=UnionItemValue("annually"),
        )

        effective_date = datetime(2020, 1, 10, tzinfo=timezone.utc)
        expected_date = datetime(2021, 1, 28, 0, 0, 0, tzinfo=timezone.utc)

        result = self.run_function(
            "_get_next_apply_interest_datetime", mock_vault, mock_vault, effective_date
        )

        self.assertEqual(result, expected_date)

    def test_apply_interest_frequency_quarterly(self):
        mock_vault = self.create_mock(
            interest_application_day=28,
            interest_application_frequency=UnionItemValue("quarterly"),
        )

        effective_date = datetime(2020, 1, 10, tzinfo=timezone.utc)
        expected_date = datetime(2020, 4, 28, 0, 0, 0, tzinfo=timezone.utc)

        result = self.run_function(
            "_get_next_apply_interest_datetime", mock_vault, mock_vault, effective_date
        )

        self.assertEqual(result, expected_date)

    def test_get_start_of_monthly_withdrawal_window(self):
        test_cases = (
            {
                "test_case": "within a month since account creation",
                "creation_date": datetime(2020, 1, 10, 1, 2, 3, tzinfo=timezone.utc),
                "effective_date": datetime(2020, 1, 15, 2, 3, 4, tzinfo=timezone.utc),
                "expected_date": datetime(2020, 1, 10, 0, 0, 0, tzinfo=timezone.utc),
            },
            {
                "test_case": "within a year since account creation",
                "creation_date": datetime(2020, 1, 10, 1, 2, 3, tzinfo=timezone.utc),
                "effective_date": datetime(2020, 8, 20, 5, 6, 7, tzinfo=timezone.utc),
                "expected_date": datetime(2020, 8, 10, 0, 0, 0, tzinfo=timezone.utc),
            },
            {
                "test_case": "beyond a year since account creation",
                "creation_date": datetime(2020, 1, 10, 1, 2, 3, tzinfo=timezone.utc),
                "effective_date": datetime(2021, 3, 7, 8, 9, 10, tzinfo=timezone.utc),
                "expected_date": datetime(2021, 2, 10, 0, 0, 0, tzinfo=timezone.utc),
            },
        )

        for test_case in test_cases:
            with self.subTest(test_case=test_case["test_case"]):
                mock_vault = self.create_mock(
                    creation_date=test_case["creation_date"],
                    interest_application_day=28,
                    interest_application_frequency=UnionItemValue("quarterly"),
                )
                result = self.run_function(
                    "_get_start_of_monthly_withdrawal_window",
                    mock_vault,
                    mock_vault,
                    test_case["effective_date"],
                )
                self.assertEqual(result, test_case["expected_date"])

    def test_account_monthly_maintenance_fee_not_applied_if_zero(self):
        default_committed = Decimal("10000")
        input_maintenance_fee = Decimal("0")
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            account_tier_names=json_dumps(["LOWER_TIER"]),
            maintenance_fee_monthly=json_dumps({"LOWER_TIER": str(input_maintenance_fee)}),
            fees_application_day=1,
            fees_application_hour=0,
            fees_application_minute=0,
            fees_application_second=0,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

        mock_vault.instruct_posting_batch.assert_not_called()

    def test_account_monthly_maintenance_fee_applied(self):
        default_committed = Decimal("10000")
        input_maintenance_fee = Decimal("5")
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            account_tier_names=json_dumps(["LOWER_TIER"]),
            maintenance_fee_monthly=json_dumps({"LOWER_TIER": str(input_maintenance_fee)}),
            fees_application_day=1,
            fees_application_hour=0,
            fees_application_minute=0,
            fees_application_second=0,
            client_transaction={},
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_with(
            amount=input_maintenance_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address="DEFAULT",
            to_account_id=MAINTENANCE_FEE_INCOME_ACCOUNT,
            to_account_address="DEFAULT",
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MAINTENANCE_FEE_MONTHLY_MOCK_HOOK"
            f"_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Maintenance fee monthly",
                "event": "APPLY_MAINTENANCE_FEE_MONTHLY",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=["INTERNAL_POSTING_APPLY_MAINTENANCE_FEE_MONTHLY_MOCK_HOOK_USD"],
            effective_date=DEFAULT_DATE,
        )

    def test_monthly_maintenance_fee_not_applied_if_automated_deposit_transfer(self):
        effective_time = datetime(2020, 2, 1)
        balance_ts = self.account_balances(
            dt=effective_time - relativedelta(months=1), default_committed=Decimal(100)
        )
        expected_maintenance_fee = Decimal(10)

        # Build client transactions
        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "DEPOSIT_ACH_CT_ID_1"
        ct_postings = [
            self.inbound_hard_settlement(
                denomination="USD",
                amount=Decimal(100),
                client_transaction_id=client_transaction_id_1,
                client_id=client_id_1,
                value_timestamp=effective_time - timedelta(hours=1),
            )
        ]
        client_transaction = {
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=ct_postings,
            )
        }

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            account_tier_names=json_dumps(["LOWER_TIER"]),
            maintenance_fee_monthly=json_dumps({"LOWER_TIER": str(expected_maintenance_fee)}),
            fees_application_day=1,
            fees_application_hour=0,
            fees_application_minute=0,
            fees_application_second=0,
            automated_transfer_tag="DEPOSIT_ACH_",
            client_transaction=client_transaction,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_monthly_maintenance_fee_applied_if_manual_deposit_transfer(self):
        effective_time = datetime(2020, 2, 1)
        balance_ts = self.account_balances(
            dt=effective_time - relativedelta(months=1), default_committed=Decimal(100)
        )
        expected_maintenance_fee = Decimal(10)

        # Build client transactions
        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "MANUAL_DEPOSIT_CT_ID_1"
        ct_postings = [
            self.inbound_hard_settlement(
                denomination="USD",
                amount=Decimal(100),
                client_transaction_id=client_transaction_id_1,
                client_id=client_id_1,
                value_timestamp=effective_time - timedelta(hours=1),
            )
        ]
        client_transaction = {
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=ct_postings,
            )
        }

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            account_tier_names=json_dumps(["LOWER_TIER"]),
            maintenance_fee_monthly=json_dumps({"LOWER_TIER": str(expected_maintenance_fee)}),
            fees_application_day=1,
            fees_application_hour=0,
            fees_application_minute=0,
            fees_application_second=0,
            automated_transfer_tag="DEPOSIT_ACH_",
            client_transaction=client_transaction,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_with(
            amount=expected_maintenance_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address="DEFAULT",
            to_account_id=MAINTENANCE_FEE_INCOME_ACCOUNT,
            to_account_address="DEFAULT",
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MAINTENANCE_FEE_MONTHLY_MOCK_HOOK"
            f"_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Maintenance fee monthly",
                "event": "APPLY_MAINTENANCE_FEE_MONTHLY",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=["INTERNAL_POSTING_APPLY_MAINTENANCE_FEE_MONTHLY_MOCK_HOOK_USD"],
            effective_date=effective_time,
        )

    def test_balance_fee_not_applied_if_mean_balance_above_threshold(self):
        default_committed = Decimal("100")
        effective_time = datetime(2020, 9, 1)
        expected_minimum_balance_fee = Decimal("10")
        account_tier_flags = ["LOWER_TIER"]
        period_start = datetime(2020, 8, 1)
        balance_ts = self.account_balances(dt=period_start, default_committed=default_committed)

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            minimum_balance_fee=expected_minimum_balance_fee,
            flags=account_tier_flags,
            account_tier_names=json_dumps(["LOWER_TIER"]),
            maintenance_fee_monthly=json_dumps({"LOWER_TIER": str(Decimal(0))}),
            fees_application_day=1,
            fees_application_hour=0,
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

    def test_balance_fee_applied_if_mean_balance_is_zero_and_below_threshold(self):
        default_committed = Decimal("0")
        effective_time = datetime(2020, 9, 1)
        expected_minimum_balance_fee = Decimal("10")
        account_tier_flags = ["LOWER_TIER"]
        period_start = datetime(2020, 8, 1)
        balance_ts = self.account_balances(dt=period_start, default_committed=default_committed)

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            minimum_balance_fee=expected_minimum_balance_fee,
            flags=account_tier_flags,
            account_tier_names=json_dumps(["LOWER_TIER"]),
            maintenance_fee_monthly=json_dumps({"LOWER_TIER": str(Decimal(0))}),
            fees_application_day=1,
            fees_application_hour=0,
            fees_application_minute=0,
            fees_application_second=0,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_with(
            amount=expected_minimum_balance_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address="DEFAULT",
            to_account_id=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            to_account_address="DEFAULT",
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_MINIMUM_BALANCE_FEE_MOCK_HOOK"
            f"_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MINIMUM_BALANCE_FEE",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=[
                "INTERNAL_POSTING_APPLY_MINIMUM_BALANCE_FEE_MOCK_HOOK_USD",
            ],
            effective_date=effective_time,
        )

    def test_extracting_tiered_param_no_flag_on_account_returns_last_tier(self):
        default_committed = Decimal("0")
        account_tier_flags = []
        period_start = datetime(2020, 8, 1)
        balance_ts = self.account_balances(dt=period_start, default_committed=default_committed)

        mock_vault = self.create_mock(
            balance_ts=balance_ts, denomination="USD", flags=account_tier_flags
        )

        result = self.run_function("_get_account_tier", mock_vault, mock_vault)
        self.assertEqual(result, "LOWER_TIER")

    def test_extracting_tiered_param_one_flag_on_account(self):
        default_committed = Decimal("0")
        account_tier_flags = ["MIDDLE_TIER"]
        period_start = datetime(2020, 8, 1)
        balance_ts = self.account_balances(dt=period_start, default_committed=default_committed)

        mock_vault = self.create_mock(
            balance_ts=balance_ts, denomination="USD", flags=account_tier_flags
        )

        result = self.run_function("_get_account_tier", mock_vault, mock_vault)
        self.assertEqual(result, "MIDDLE_TIER")

    def test_extracting_tiered_param_multiple_flags_on_account_returns_first(self):
        default_committed = Decimal("0")
        account_tier_flags = [
            "MIDDLE_TIER",
            "UPPER_TIER",
        ]
        period_start = datetime(2020, 8, 1)
        balance_ts = self.account_balances(dt=period_start, default_committed=default_committed)

        mock_vault = self.create_mock(
            balance_ts=balance_ts, denomination="USD", flags=account_tier_flags
        )

        result = self.run_function("_get_account_tier", mock_vault, mock_vault)
        self.assertEqual(result, "UPPER_TIER")

    def test_extracting_tiered_param_non_existent_flag_return_last_tier(self):
        default_committed = Decimal("0")
        account_tier_flags = ["NO_FLAG"]
        period_start = datetime(2020, 8, 1)
        balance_ts = self.account_balances(dt=period_start, default_committed=default_committed)

        mock_vault = self.create_mock(
            balance_ts=balance_ts, denomination="USD", flags=account_tier_flags
        )

        result = self.run_function("_get_account_tier", mock_vault, mock_vault)

        self.assertEqual(result, "LOWER_TIER")

    def test_get_next_apply_fees_schedule_correct_monthly_schedule(self):
        mock_vault = self.create_mock(
            fees_application_day=2,
            fees_application_hour=23,
            fees_application_minute=59,
            fees_application_second=0,
        )

        next_fee_schedule = self.run_function(
            "_get_next_apply_fees_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2020, 1, 1, 3, 4, 5),
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

    def test_get_next_apply_fees_schedule_correct_monthly_schedule_day_gt_next_month_1(
        self,
    ):
        mock_vault = self.create_mock(
            fees_application_day=31,
            fees_application_hour=23,
            fees_application_minute=59,
            fees_application_second=0,
        )

        next_fee_schedule = self.run_function(
            "_get_next_apply_fees_schedule",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2019, 1, 1, 3, 4, 5),
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

    def test_get_next_apply_fees_schedule_correct_monthly_schedule_day_gt_next_month_2(
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
            "_get_next_apply_fees_schedule",
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

    def test_get_next_apply_fees_schedule_correct_monthly_schedule_when_lt_period_fr_creation(self):
        creation_date = datetime(2020, 1, 2)
        mock_vault = self.create_mock(
            fees_application_day=1,
            fees_application_hour=0,
            fees_application_minute=1,
            fees_application_second=0,
            creation_date=creation_date,
        )

        next_fee_schedule = self.run_function(
            "_get_next_apply_fees_schedule",
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

    def test_get_next_apply_fees_schedule_correct_yearly_schedule(self):
        mock_vault = self.create_mock(
            fees_application_day=2,
            fees_application_hour=23,
            fees_application_minute=59,
            fees_application_second=0,
        )

        next_fee_schedule = self.run_function(
            "_get_next_apply_fees_schedule",
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

    def test_get_next_apply_fees_schedule_correct_yearly_schedule_when_lt_period_fr_creation(
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
            "_get_next_apply_fees_schedule",
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

    def test_count_automated_deposit_transactions_returns_correct_count_w_mixed_transactions(self):
        effective_time = datetime(2020, 3, 1)

        # Build client transactions
        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "DEPOSIT_ACH_CT_ID_1"
        client_id_2 = "client_ID_2"
        client_transaction_id_2 = "DEPOSIT_ACH_CT_ID_2"
        client_id_3 = "client_ID_3"
        client_transaction_id_3 = "DEPOSIT_ACH_CT_ID_3"
        client_id_4 = "client_ID_4"
        client_transaction_id_4 = "DEPOSIT_ACH_CT_ID_4"
        client_id_5 = "client_ID_5"
        client_transaction_id_5 = "MANUAL_ACH_CT_ID_5"
        client_id_6 = "client_ID_6"
        client_transaction_id_6 = "DEPOSIT_ACH_CT_ID_6"

        client_transaction = {
            # Should be ignored - too far in past
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=[
                    self.inbound_hard_settlement(
                        denomination="USD",
                        amount="100",
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        value_timestamp=effective_time - relativedelta(days=32),
                    )
                ]
            ),
            # Should be counted
            (client_id_2, client_transaction_id_2): self.mock_client_transaction(
                posting_instructions=[
                    self.inbound_hard_settlement(
                        denomination="USD",
                        amount="200",
                        client_transaction_id=client_transaction_id_2,
                        client_id=client_id_2,
                        value_timestamp=effective_time - relativedelta(days=20),
                    )
                ]
            ),
            # Should be ignored - withdrawal
            (client_id_3, client_transaction_id_3): self.mock_client_transaction(
                posting_instructions=[
                    self.outbound_hard_settlement(
                        denomination="USD",
                        amount="300",
                        client_transaction_id=client_transaction_id_3,
                        client_id=client_id_3,
                        value_timestamp=effective_time - relativedelta(days=10),
                    )
                ]
            ),
            # Should be counted
            (client_id_4, client_transaction_id_4): self.mock_client_transaction(
                posting_instructions=[
                    self.inbound_hard_settlement(
                        denomination="USD",
                        amount="400",
                        client_transaction_id=client_transaction_id_4,
                        client_id=client_id_4,
                        value_timestamp=effective_time - relativedelta(days=5),
                    )
                ]
            ),
            # Should be ignored - incorrect transaction id
            (client_id_5, client_transaction_id_5): self.mock_client_transaction(
                posting_instructions=[
                    self.inbound_hard_settlement(
                        denomination="USD",
                        amount="500",
                        client_transaction_id=client_transaction_id_5,
                        client_id=client_id_5,
                        value_timestamp=effective_time - relativedelta(days=1),
                    ),
                ]
            ),
            # Should be ignored - not settled
            (client_id_6, client_transaction_id_6): self.mock_client_transaction(
                posting_instructions=[
                    self.inbound_auth(
                        denomination="USD",
                        amount="600",
                        client_transaction_id=client_transaction_id_6,
                        client_id=client_id_6,
                        value_timestamp=effective_time,
                    ),
                ]
            ),
        }

        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            automated_transfer_tag="DEPOSIT_ACH_",
            client_transaction=client_transaction,
        )

        deposit_count = self.run_function(
            "_count_automated_deposit_transactions",
            mock_vault,
            vault=mock_vault,
            effective_date=effective_time,
        )

        # txn_2 + txn_4
        expected_deposit_count = 2

        self.assertEqual(deposit_count, expected_deposit_count)

    def test_get_tiered_interest_rates(self):
        test_cases = (
            {
                "flags": [PROMOTIONAL_INTEREST_RATES],
                "expected_result": PROMOTION_RATES,
                "description": "has promotional rates flag",
            },
            {
                "flags": [],
                "expected_result": TIERED_INTEREST_RATES,
                "description": "no promotional rates flag",
            },
        )

        for test_case in test_cases:
            mock_vault = self.create_mock(denomination="USD", flags=test_case["flags"])
            result = self.run_function("_get_tiered_interest_rates", mock_vault, mock_vault)
            self.assertDictEqual(
                result,
                json.loads(test_case["expected_result"]),
                test_case["description"],
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
            )
            result = self.run_function("_get_monthly_maintenance_fee_tiers", mock_vault, mock_vault)
            self.assertDictEqual(
                result,
                json.loads(test_case["expected_result"]),
                test_case["description"],
            )

    def test_scheduled_code_accrue_interest_with_promotional_tiered_interest(self):
        accrue_interest_date = DEFAULT_DATE
        end_of_day = accrue_interest_date - timedelta(microseconds=1)
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1),
            default_committed=Decimal("25000"),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            days_in_year=UnionItemValue(key="365"),
            flags=[PROMOTIONAL_INTEREST_RATES],
        )
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST",
            effective_date=accrue_interest_date,
        )
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("1.36986"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="ACCRUE_INTEREST_TIER1_MOCK_HOOK_ACCRUED_"
                    "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
                    from_account_id="Main account",
                    from_account_address="ACCRUED_INTEREST_RECEIVABLE",
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": "Daily interest accrued at -0.02740% on balance of 5000.00.",
                        "event": "ACCRUE_INTEREST",
                        "gl_impacted": "True",
                        "account_type": "US_SAVINGS",
                    },
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("8.21918"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="ACCRUE_INTEREST_TIER3_MOCK_HOOK_ACCRUED_"
                    "INTEREST_PAYABLE_COMMERCIAL_BANK_MONEY_USD",
                    from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id="Main account",
                    to_account_address="ACCRUED_INTEREST_PAYABLE",
                    instruction_details={
                        "description": "Daily interest accrued at 0.08219% on balance of 10000.00.",
                        "event": "ACCRUE_INTEREST",
                        "gl_impacted": "True",
                        "account_type": "US_SAVINGS",
                    },
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                ),
            ]
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=[
                "ACCRUE_INTEREST_TIER1_MOCK_HOOK_ACCRUED_"
                "INTEREST_RECEIVABLE_COMMERCIAL_BANK_MONEY_USD",
                "ACCRUE_INTEREST_TIER3_MOCK_HOOK_ACCRUED_"
                "INTEREST_PAYABLE_COMMERCIAL_BANK_MONEY_USD",
            ],
            effective_date=end_of_day,
        )


class SavingsAccountMinimumWithdrawalTest(SavingsAccountBaseTest):
    def test_pre_posting_code_rejects_withdrawals_below_min_amount(self):

        default_committed = Decimal(2000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=DEFAULT_DATE,
            posting_instructions_groups=[
                [
                    self.outbound_auth(
                        denomination="USD",
                        amount=Decimal(9),
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                        client_id=CLIENT_ID_1,
                        value_timestamp=DEFAULT_DATE,
                    )
                ]
            ],
        )

        minimum_withdrawal = Decimal(10)
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            client_transaction=client_transactions,
            minimum_deposit=Decimal(50),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=Decimal(100),
            minimum_withdrawal=minimum_withdrawal,
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                DEFAULT_DATE,
            )
        expected_rejection_error = (
            f"Transaction amount is less than the minimum withdrawal amount"
            f" {minimum_withdrawal} {DEFAULT_DENOMINATION}."
        )

        self.assertEqual(str(e.exception), expected_rejection_error)

    def test_pre_posting_code_accepts_withdrawals_below_min_amount_if_overridden(self):

        force_override = {"force_override": "true"}
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=Decimal(2000),
        )

        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=DEFAULT_DATE,
            posting_instructions_groups=[
                [
                    self.outbound_auth(
                        denomination="USD",
                        amount=Decimal(9),
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                        client_id=CLIENT_ID_1,
                        value_timestamp=DEFAULT_DATE,
                    )
                ]
            ],
            batch_details=force_override,
        )

        minimum_withdrawal = Decimal(10)
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            client_transaction=client_transactions,
            minimum_deposit=Decimal(50),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=Decimal(100),
            minimum_withdrawal=minimum_withdrawal,
        )

        self.run_function(
            "pre_posting_code",
            mock_vault,
            pib,
            DEFAULT_DATE,
        )

        self.assert_no_side_effects(mock_vault)

    def test_pre_posting_code_rejects_withdrawals_below_min_amounts(self):

        # this test is whith mixed multiple postings

        #   posting_life_cycle_1: Send 50 to an external account:
        #   initial posting of £50 goes into pending.out as a debit
        #   during authorisation.
        #   then committed will have £50 debitted during sttlement.

        #   posting_life_cycle_2 for the second client transaction:
        #   Send £9 to an external account which is below
        #   min withdrawal amount of £10.
        #   Pending_out will have debit of £9 during authorisation
        #   and that's when we expect pre-posting hook to
        #   reject this transaction.

        #   posting_life_cycle_3 for the 3rd client transaction:
        #   amount of £60 is depositted into this account
        #   this means, pending_in pot will have £60
        #   creditted during authorisation,
        #   and later committed will have £60 creditted during settlement

        default_committed = Decimal(2000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        ct_1_postings = [
            self.outbound_auth(
                denomination="USD",
                amount=Decimal(50),
                client_transaction_id=CLIENT_TRANSACTION_ID_1,
                client_id=CLIENT_ID_1,
                value_timestamp=DEFAULT_DATE - timedelta(hours=1),
            ),
            self.settle_outbound_auth(
                denomination="USD",
                amount=Decimal(50),
                unsettled_amount=Decimal(50),
                client_transaction_id=CLIENT_TRANSACTION_ID_1,
                client_id=CLIENT_ID_1,
                value_timestamp=DEFAULT_DATE,
            ),
        ]

        ct_2_postings = [
            self.outbound_auth(
                denomination="USD",
                amount=Decimal(9),
                client_transaction_id=CLIENT_TRANSACTION_ID_2,
                client_id=CLIENT_ID_2,
                value_timestamp=DEFAULT_DATE,
            ),
        ]

        ct_3_postings = [
            self.inbound_auth(
                denomination="USD",
                amount=Decimal(60),
                client_transaction_id=CLIENT_TRANSACTION_ID_3,
                client_id=CLIENT_ID_3,
                value_timestamp=DEFAULT_DATE - timedelta(minutes=1),
            ),
            self.settle_inbound_auth(
                denomination="USD",
                amount=Decimal(60),
                unsettled_amount=Decimal(60),
                client_transaction_id=CLIENT_TRANSACTION_ID_3,
                client_id=CLIENT_ID_3,
                value_timestamp=DEFAULT_DATE,
            ),
        ]

        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=DEFAULT_DATE,
            posting_instructions_groups=[ct_1_postings, ct_2_postings, ct_3_postings],
        )

        minimum_withdrawal = Decimal(10)
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            client_transaction=client_transactions,
            minimum_deposit=Decimal(50),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=Decimal(100),
            minimum_withdrawal=Decimal(10),
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                DEFAULT_DATE,
            )
            expected_rejection_error = (
                f"Transaction amount is less than the minimum withdrawal amount"
                f" {minimum_withdrawal} {DEFAULT_DENOMINATION}."
            )

            self.assertEqual(str(e.exception), expected_rejection_error)


class SavingsAccountWithdrawalLimitTest(SavingsAccountBaseTest):
    def test_pre_posting_code_rejects_withdrawals_exceeding_daily_limits_for_single_trans(
        self,
    ):

        default_committed = Decimal(2000)
        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=DEFAULT_DATE,
            posting_instructions_groups=[
                [
                    self.outbound_auth(
                        denomination="USD",
                        amount=Decimal(101),
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                        client_id=CLIENT_ID_1,
                        value_timestamp=DEFAULT_DATE,
                    )
                ]
            ],
        )

        maximum_daily_withdrawal = Decimal(100)
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            client_transaction=client_transactions,
            minimum_deposit=Decimal(50),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=maximum_daily_withdrawal,
            minimum_withdrawal=Decimal(10),
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                DEFAULT_DATE,
            )

            expected_rejection_error = (
                f"Transaction would cause the maximum daily withdrawal limit of"
                f" {maximum_daily_withdrawal} USD to be exceeded."
            )

            self.assertEqual(str(e.exception), expected_rejection_error)

    @skip(
        "INC-5242 - Tests were written against an incorrect implementation"
        " + incorrect mocking. Contract behaviour and tests need revisiting"
    )
    def test_reject_withdrawals_exceeding_daily_limits(self):

        #   this test is with multiple transactions

        #   posting_life_cycle_1: Send 91 to an external account:
        #   initial posting of £91 goes into pending.out as a debit during authorisation
        #   then committed will have £91 debitted during sttlement. This does not affect
        #   limit

        #   posting_life_cycle_2 for the second client transaction:
        #   Send £10 to an external account
        #   Pending_out will have debit of £10 during authorisation
        #   and that's when we expect pre-posting hook to reject this transaction.

        #   posting_life_cycle_3 for the 3rd client transaction:
        #   amount of £60 is depositted into this account
        #   this means, pending_in pot will have £60 credited during authorisation
        #   and later, committed will have £60 credited during settlement

        default_committed = Decimal(2000)

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        ct_1_postings = [
            self.outbound_auth(
                denomination="USD",
                amount=Decimal(91),  # $91.0 withdrawal in auth
                client_transaction_id=CLIENT_TRANSACTION_ID_1,
                client_id=CLIENT_ID_1,
                value_timestamp=DEFAULT_DATE - timedelta(hours=1),
            ),
            self.settle_outbound_auth(
                denomination="USD",
                amount=Decimal(91),  # $91.0 withdrawal in settled
                unsettled_amount=Decimal(91),
                client_transaction_id=CLIENT_TRANSACTION_ID_1,
                client_id=CLIENT_ID_1,
                value_timestamp=DEFAULT_DATE,
            ),
        ]
        ct_2_postings = [
            self.outbound_auth(
                denomination="USD",
                amount=Decimal(10),  # $10 withdrawal in auth
                client_transaction_id=CLIENT_TRANSACTION_ID_2,
                client_id=CLIENT_ID_2,
                value_timestamp=DEFAULT_DATE,
            ),
        ]
        ct_3_postings = [
            self.inbound_auth(
                denomination="USD",
                amount=Decimal(60),
                client_transaction_id=CLIENT_TRANSACTION_ID_3,
                client_id=CLIENT_ID_3,
                value_timestamp=DEFAULT_DATE - timedelta(minutes=1),
            ),
            self.settle_inbound_auth(
                denomination="USD",
                amount=Decimal(60),
                unsettled_amount=Decimal(60),
                client_transaction_id=CLIENT_TRANSACTION_ID_3,
                client_id=CLIENT_ID_3,
                value_timestamp=DEFAULT_DATE,
            ),
        ]

        pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=DEFAULT_DATE,
            posting_instructions_groups=[ct_1_postings, ct_2_postings, ct_3_postings],
        )

        maximum_daily_withdrawal = Decimal(100)
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="USD",
            client_transaction=client_transactions,
            minimum_deposit=Decimal(50),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=maximum_daily_withdrawal,
            minimum_withdrawal=Decimal(10),
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                DEFAULT_DATE,
            )

            expected_rejection_error = (
                f"Transaction would cause the maximum daily withdrawal limit of"
                f" {maximum_daily_withdrawal} USD to be exceeded."
            )

            self.assertEqual(str(e.exception), expected_rejection_error)

        test_cases = (
            {
                "monthly_withdrawal_limit": 3,
                "number_of_withdrawals": {"current": 2, "previous": 2, "total": 4},
                "expected_result": 1,
                "description": "current pib brings over withdrawal limit",
            },
            {
                "monthly_withdrawal_limit": 3,
                "number_of_withdrawals": {"current": 1, "previous": 2, "total": 3},
                "expected_result": 0,
                "description": "current pib brings to withdrawal limit",
            },
            {
                "monthly_withdrawal_limit": 3,
                "number_of_withdrawals": {"current": 2, "previous": 3, "total": 5},
                "expected_result": 2,
                "description": "previous pibs already reached withdrawal limit",
            },
            {
                "monthly_withdrawal_limit": 3,
                "number_of_withdrawals": {"current": 3, "previous": 4, "total": 7},
                "expected_result": 3,
                "description": "previous pibs already above withdrawal limit",
            },
            {
                "monthly_withdrawal_limit": -1,
                "number_of_withdrawals": {"current": 2, "previous": 3, "total": 5},
                "expected_result": 0,
                "description": "unlimited withdrawals",
            },
            {
                "monthly_withdrawal_limit": 10,
                "number_of_withdrawals": {"current": 2, "previous": 3, "total": 5},
                "expected_result": 0,
                "description": "below withdrawal limit",
            },
        )

        for test_case in test_cases:
            mock_vault = self.create_mock(
                denomination="USD",
                monthly_withdrawal_limit=test_case["monthly_withdrawal_limit"],
            )
            result = self.run_function(
                "_count_excess_withdrawals",
                mock_vault,
                mock_vault,
                test_case["number_of_withdrawals"],
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])


# The Excess Withdrawal tests differ slightly to CASA, due to unrelated parameters being optional on
# US Savings and not in CASA. This can be aligned once the relevant features are also aligned and
# templated
class ExcessWithdrawalRejectionTest(SavingsAccountTest):
    effective_date = datetime(2020, 9, 27)

    def _excess_withdrawal_test(
        self,
        transactions: Optional[list[Transaction]] = None,
        posting_instruction_groups: Optional[list[list[PostingInstruction]]] = None,
        withdrawal_limit: int = 1,
        expect_rejected: bool = True,
        effective_date: datetime = datetime(2020, 9, 27),
        reject_excess_withdrawals: bool = True,
    ):
        """
        Standardised test structure for excess withdrawal fees.
        :param transactions: list of transactions for the scenario. Use posting instructions if
        more complicated posting instruction types than hard settlements are needed
        :param posting_instructions: list of posting_instructions for the scenario. Only use if
        transaction types other than hard settlements are needed. Otherwise see `transactions`.
        :param withdrawal_limit: the monthly limit for withdrawals for the scenario
        :param expect_rejected: whether we expect the PIB to be rejected or not. Defaults to True as
        almost all tests check for rejection
        :param effective_date: the post_posting_code effective date to use
        :param reject_excess_withdrawals: the parameter value for reject_excess_withdrawals.
        Defaults to True as almost all tests need this value to check that the excess withdrawals
        are rejected
        """

        if transactions:
            pib, client_transactions, _ = self.pib_and_cts_for_transactions(
                hook_effective_date=effective_date, transactions=transactions
            )
        elif posting_instruction_groups:
            pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
                hook_effective_date=effective_date,
                posting_instructions_groups=posting_instruction_groups,
            )
        else:
            raise ValueError("One of transactions or posting_instruction_groups must be provided")

        default_committed = Decimal(2000)
        effective_date = datetime(2020, 9, 27)

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            creation_date=datetime(2020, 9, 23, 5, 6, 7),
            balance_ts=balance_ts,
            denomination=self.default_denom,
            client_transaction=client_transactions,
            minimum_deposit=Decimal(50),
            maximum_balance=Decimal(100000),
            maximum_daily_deposit=Decimal(1000),
            maximum_daily_withdrawal=Decimal(100),
            minimum_withdrawal=Decimal(10),
            monthly_withdrawal_limit=Decimal(withdrawal_limit),
            reject_excess_withdrawals=UnionItemValue(str(reject_excess_withdrawals)),
        )

        if expect_rejected:
            with self.assertRaises(Rejected) as e:
                self.run_function("pre_posting_code", mock_vault, pib, effective_date)

            expected_rejection_error = (
                f"Exceeding monthly allowed withdrawal number: {withdrawal_limit}"
            )
            self.assertEqual(str(e.exception), expected_rejection_error)
        else:
            self.run_function("pre_posting_code", mock_vault, pib, effective_date)

    def test_reject_withdrawal_exceeding_monthly_limits(self):

        self._excess_withdrawal_test(
            effective_date=self.effective_date,
            transactions=[
                Withdrawal(effective_date=self.effective_date - timedelta(days=2), amount="14"),
                Withdrawal(effective_date=self.effective_date, amount="11"),
            ],
            withdrawal_limit=1,
            expect_rejected=True,
        )

    def test_reject_withdrawals_exceeding_monthly_limits(self):

        # The PIB is rejected as the total withdrawals now exceeds 1 (1 historic + 2 new)
        self._excess_withdrawal_test(
            effective_date=self.effective_date,
            transactions=[
                Withdrawal(effective_date=self.effective_date - timedelta(days=2), amount="14"),
                Withdrawal(effective_date=self.effective_date, amount="11"),
                Withdrawal(effective_date=self.effective_date, amount="12"),
            ],
            withdrawal_limit=1,
            expect_rejected=True,
        )

    def test_allow_withdrawal_within_monthly_limits(self):

        # The PIB is accepted as the total withdrawals doesn't exceed 2 (1 historic + 1 new)
        self._excess_withdrawal_test(
            effective_date=self.effective_date,
            transactions=[
                Withdrawal(effective_date=self.effective_date - timedelta(days=2), amount="14"),
                Withdrawal(effective_date=self.effective_date, amount="11"),
            ],
            withdrawal_limit=2,
            expect_rejected=False,
        )

    def test_allow_withdrawal_if_monthly_limit_is_disabled(self):

        # The PIB is accepted as the limit is disabled
        self._excess_withdrawal_test(
            effective_date=self.effective_date,
            transactions=[
                Withdrawal(effective_date=self.effective_date - timedelta(days=2), amount="14"),
                Withdrawal(effective_date=self.effective_date, amount="11"),
            ],
            withdrawal_limit=-1,
            expect_rejected=False,
        )

    def test_accept_deposit_after_withdrawal_hard_limit_is_exceeded(self):

        # The PIB is accepted as it does not count towards withdrawals
        self._excess_withdrawal_test(
            effective_date=self.effective_date,
            transactions=[
                Withdrawal(effective_date=self.effective_date - timedelta(days=2), amount="14"),
                Deposit(effective_date=self.effective_date, amount="50"),
            ],
            withdrawal_limit=0,
            expect_rejected=False,
        )

    def test_withdrawal_limit_considers_historic_auth_settle_txn_started_in_window(self):

        self._excess_withdrawal_test(
            effective_date=self.effective_date,
            posting_instruction_groups=[
                [
                    self.outbound_auth(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date - timedelta(days=1),
                    ),
                    self.settle_outbound_auth(
                        denomination=self.default_denom,
                        final=True,
                        unsettled_amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date - timedelta(hours=4),
                    ),
                ],
                [
                    self.outbound_hard_settlement(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                        client_id=CLIENT_ID_1,
                        value_timestamp=self.effective_date,
                    ),
                ],
            ],
            withdrawal_limit=1,
            expect_rejected=True,
        )

    def test_withdrawal_limit_considers_historic_hard_settlement_txn_in_window(
        self,
    ):
        # The PIB is rejected as previous
        self._excess_withdrawal_test(
            effective_date=self.effective_date,
            transactions=[
                Withdrawal(effective_date=self.effective_date - timedelta(days=2), amount="14"),
                Withdrawal(effective_date=self.effective_date, amount="14"),
            ],
            withdrawal_limit=1,
            expect_rejected=True,
        )

    def test_withdrawal_limit_ignores_txn_started_in_prev_window(
        self,
    ):
        # TODO(INC-5178): review this behaviour

        self._excess_withdrawal_test(
            effective_date=self.effective_date,
            posting_instruction_groups=[
                [
                    self.outbound_auth(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date - timedelta(days=40),
                    ),
                    self.settle_outbound_auth(
                        denomination=self.default_denom,
                        # This is not on the corresponding CASA test because the US Products
                        # still use posting amounts and therefore don't support `None` amounts
                        amount=Decimal(14),
                        unsettled_amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date,
                    ),
                ],
                [
                    self.outbound_hard_settlement(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                        client_id=CLIENT_ID_1,
                        value_timestamp=self.effective_date,
                    ),
                ],
            ],
            withdrawal_limit=1,
            expect_rejected=False,
        )

    def test_withdrawal_limit_ignores_cancelled_txn(
        self,
    ):

        # TODO(INC-5178): review this behaviour
        self._excess_withdrawal_test(
            effective_date=self.effective_date,
            posting_instruction_groups=[
                [
                    self.outbound_auth(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date - timedelta(days=40),
                    ),
                    # releasing == 'cancelled' txn
                    self.release_outbound_auth(
                        denomination=self.default_denom,
                        unsettled_amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date,
                    ),
                ],
            ],
            withdrawal_limit=0,
            expect_rejected=False,
        )

    def test_withdrawal_limit_ignores_unsettled_auth(
        self,
    ):

        self._excess_withdrawal_test(
            effective_date=self.effective_date,
            posting_instruction_groups=[
                [
                    self.outbound_auth(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date,
                    ),
                ],
            ],
            withdrawal_limit=0,
            expect_rejected=False,
        )

    def test_withdrawal_limit_considers_partially_settled_auth(
        self,
    ):
        self._excess_withdrawal_test(
            effective_date=self.effective_date,
            posting_instruction_groups=[
                [
                    self.outbound_auth(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date - timedelta(days=1),
                    ),
                    self.settle_outbound_auth(
                        denomination=self.default_denom,
                        amount=Decimal(10),
                        unsettled_amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date,
                    ),
                ],
            ],
            withdrawal_limit=0,
            expect_rejected=True,
        )

    def test_withdrawal_limit_ignores_internal_postings(
        self,
    ):

        self._excess_withdrawal_test(
            effective_date=self.effective_date,
            posting_instruction_groups=[
                [
                    self.outbound_hard_settlement(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=INTERNAL_CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date,
                    )
                ],
            ],
            withdrawal_limit=0,
            expect_rejected=False,
        )


class ExcessWithdrawalFeesTest(SavingsAccountBaseTest):

    effective_date = datetime(2020, 9, 27)

    def excess_withdrawal_fee_call(self, amount: str, limit: int):
        return call(
            amount=Decimal(amount),
            client_transaction_id=f"{INTERNAL_POSTING}_" "APPLY_EXCESS_WITHDRAWAL_FEE_MOCK_HOOK",
            denomination=self.default_denom,
            from_account_id="Main account",
            from_account_address="DEFAULT",
            to_account_id=EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
            to_account_address="DEFAULT",
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": f"Excess withdrawal fee on exceeding monthly"
                f" withdrawal limit of {limit}",
                "event": "APPLY_EXCESS_WITHDRAWAL_FEE",
            },
        )

    def _excess_withdrawal_test(
        self,
        transactions: Optional[list[Transaction]] = None,
        posting_instruction_groups: Optional[list[list[PostingInstruction]]] = None,
        withdrawal_limit: int = 1,
        effective_date: datetime = datetime(2020, 9, 27),
        reject_excess_withdrawals: bool = False,
    ):
        """
        Standardised test setup and execution for excess withdrawal scenarios.
        :param transactions: list of transactions for the scenario. Use posting instructions if
        more complicated posting instruction types than hard settlements are needed
        :param posting_instructions: list of posting_instructions for the scenario. Only use if
        transaction types other than hard settlements are needed. Otherwise see `transactions`.
        :param withdrawal_limit: the monthly limit for withdrawals for the scenario
        :param effective_date: the post_posting_code effective date to use
        :param reject_excess_withdrawals: the parameter value for reject_excess_withdrawals.
        Defaults to false as almost all tests need this value to check that the fees are charged
        """

        if transactions:
            pib, client_transactions, _ = self.pib_and_cts_for_transactions(
                hook_effective_date=effective_date, transactions=transactions
            )
        elif posting_instruction_groups:
            pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
                hook_effective_date=effective_date,
                posting_instructions_groups=posting_instruction_groups,
            )
        else:
            raise ValueError("One of transactions or posting_instruction_groups must be provided")

        default_committed = Decimal(2000)

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            creation_date=datetime(2020, 9, 23, 5, 6, 7),
            balance_ts=balance_ts,
            denomination=self.default_denom,
            autosave_savings_account=OptionalValue(is_set=False),
            transaction_code_to_type_map=OptionalValue(is_set=False),
            client_transaction=client_transactions,
            excess_withdrawal_fee=Decimal("10.00"),
            reject_excess_withdrawals=UnionItemValue(str(reject_excess_withdrawals)),
            monthly_withdrawal_limit=Decimal(withdrawal_limit),
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            pib,
            effective_date,
        )

        return mock_vault

    def _excess_withdrawal_fees_test(
        self,
        transactions: Optional[list[Transaction]] = None,
        posting_instruction_groups: Optional[list[list[PostingInstruction]]] = None,
        withdrawal_limit: int = 1,
        expected_fees: Optional[Any] = None,
        effective_date: datetime = datetime(2020, 9, 27),
        reject_excess_withdrawals: bool = False,
    ):
        """
        Standardised test setup execution and assertion for excess withdrawal fees.
        :param transactions: list of transactions for the scenario. Use posting instructions if
        more complicated posting instruction types than hard settlements are needed
        :param posting_instructions: list of posting_instructions for the scenario. Only use if
        transaction types other than hard settlements are needed. Otherwise see `transactions`.
        :param withdrawal_limit: the monthly limit for withdrawals for the scenario
        :param expected_fees: the expected fee call for the test. Can be None if no fees expected
        :param effective_date: the post_posting_code effective date to use
        :param reject_excess_withdrawals: the parameter value for reject_excess_withdrawals.
        Defaults to false as almost all tests need this value to check that the fees are charged
        """

        mock_vault = self._excess_withdrawal_test(
            transactions=transactions,
            posting_instruction_groups=posting_instruction_groups,
            withdrawal_limit=withdrawal_limit,
            effective_date=effective_date,
            reject_excess_withdrawals=reject_excess_withdrawals,
        )

        if expected_fees:
            mock_vault.make_internal_transfer_instructions.assert_has_calls([expected_fees])
        else:
            mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_excess_withdrawal_fees_not_charged_if_excess_withdrawals_rejected(self):

        self._excess_withdrawal_fees_test(
            transactions=[Withdrawal(amount="14", effective_date=self.effective_date)],
            withdrawal_limit=0,
            reject_excess_withdrawals=True,
            effective_date=self.effective_date,
            expected_fees=None,
        )

    def test_excess_withdrawal_fees_consider_hard_settle_txn_in_pib(self):

        self._excess_withdrawal_fees_test(
            transactions=[Withdrawal(amount="14", effective_date=self.effective_date)],
            withdrawal_limit=0,
            effective_date=self.effective_date,
            expected_fees=self.excess_withdrawal_fee_call(amount="10.00", limit=0),
        )

    def test_excess_withdrawal_fees_consider_multiple_hard_settle_txn_in_pib(
        self,
    ):

        self._excess_withdrawal_fees_test(
            transactions=[
                Withdrawal(amount="14", effective_date=self.effective_date),
                Withdrawal(amount="15", effective_date=self.effective_date),
            ],
            withdrawal_limit=0,
            effective_date=self.effective_date,
            expected_fees=self.excess_withdrawal_fee_call(amount="20.00", limit=0),
        )

    def test_excess_withdrawal_fees_consider_auth_settle_txn_started_in_window(
        self,
    ):

        self._excess_withdrawal_fees_test(
            posting_instruction_groups=[
                [
                    self.outbound_auth(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date - timedelta(days=1),
                    ),
                    self.settle_outbound_auth(
                        denomination=self.default_denom,
                        final=True,
                        unsettled_amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date,
                    ),
                ]
            ],
            withdrawal_limit=0,
            effective_date=self.effective_date,
            expected_fees=self.excess_withdrawal_fee_call(amount="10.00", limit=0),
        )

    def test_excess_withdrawal_fees_consider_previous_txns_outside_of_pib(
        self,
    ):

        # withdrawal limit set to 1, fees are charged due to one previous and one current txn
        self._excess_withdrawal_fees_test(
            transactions=[
                Withdrawal(amount="14", effective_date=self.effective_date - timedelta(days=1)),
                Withdrawal(amount="15", effective_date=self.effective_date),
            ],
            withdrawal_limit=1,
            effective_date=self.effective_date,
            expected_fees=self.excess_withdrawal_fee_call(amount="10.00", limit=1),
        )

    def test_excess_withdrawal_fees_consider_partially_settled_auth(
        self,
    ):

        # Fees are charged as the historic auth that is now partially settled and OHS both count
        self._excess_withdrawal_fees_test(
            posting_instruction_groups=[
                [
                    self.outbound_auth(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date - timedelta(days=1),
                    ),
                    self.settle_outbound_auth(
                        denomination=self.default_denom,
                        amount=Decimal(8),
                        unsettled_amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date,
                    ),
                ],
                [
                    self.outbound_hard_settlement(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_1,
                        client_id=CLIENT_ID_1,
                        value_timestamp=self.effective_date,
                    ),
                ],
            ],
            withdrawal_limit=1,
            effective_date=self.effective_date,
            expected_fees=self.excess_withdrawal_fee_call(amount="10.00", limit=1),
        )

    def test_excess_withdrawal_fees_ignore_txn_started_in_prev_window(
        self,
    ):
        # TODO: is this by design?
        self._excess_withdrawal_fees_test(
            posting_instruction_groups=[
                [
                    self.outbound_auth(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date - timedelta(days=40),
                    ),
                    self.settle_outbound_auth(
                        denomination=self.default_denom,
                        final=True,
                        unsettled_amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date,
                    ),
                ]
            ],
            withdrawal_limit=0,
            effective_date=self.effective_date,
            expected_fees=None,
        )

    def test_excess_withdrawal_fees_ignore_cancelled_txn(
        self,
    ):
        # TODO: is this by design?
        self._excess_withdrawal_fees_test(
            posting_instruction_groups=[
                [
                    self.outbound_auth(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date - timedelta(days=40),
                    ),
                    # releasing == 'cancelled' txn
                    self.release_outbound_auth(
                        denomination=self.default_denom,
                        unsettled_amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date,
                    ),
                ]
            ],
            withdrawal_limit=0,
            effective_date=self.effective_date,
            expected_fees=None,
        )

    def test_excess_withdrawal_fees_ignores_unsettled_auth(
        self,
    ):

        self._excess_withdrawal_fees_test(
            posting_instruction_groups=[
                [
                    self.outbound_auth(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date - timedelta(days=40),
                    )
                ]
            ],
            withdrawal_limit=0,
            effective_date=self.effective_date,
            expected_fees=None,
        )

    def test_excess_withdrawal_fees_ignores_internal_posting(
        self,
    ):

        self._excess_withdrawal_fees_test(
            posting_instruction_groups=[
                [
                    self.outbound_hard_settlement(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=INTERNAL_CLIENT_TRANSACTION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date,
                    )
                ]
            ],
            withdrawal_limit=0,
            effective_date=self.effective_date,
            expected_fees=None,
        )

    def test_excess_withdrawal_fees_ignore_deposits(self):

        # No fee charged despite withdrawal_limit already exceeded as the current pib just has
        # a deposit inside
        self._excess_withdrawal_fees_test(
            transactions=[
                Withdrawal(effective_date=self.effective_date - timedelta(days=1), amount="14"),
                Deposit(effective_date=self.effective_date, amount="50"),
            ],
            withdrawal_limit=0,
            effective_date=self.effective_date,
            expected_fees=None,
        )


class ExcessWithdrawalNotificationTest(SavingsAccountBaseTest):

    effective_date = datetime(2020, 9, 27)

    def excess_withdrawal_notification_call(
        self, amount: int, limit: int, reject_excess_withdrawals: bool = True
    ):

        limit_message = (
            (
                "Warning: Reached monthly withdrawal transaction limit, "
                "no further withdrawals will be allowed for the current period."
            )
            if reject_excess_withdrawals
            else (
                "Warning: Reached monthly withdrawal transaction limit, "
                "charges will be applied for the next withdrawal."
            )
        )

        return call(
            notification_type="US_PRODUCTS_TRANSACTION_LIMIT_WARNING",
            notification_details={
                "account_id": "Main account",
                "limit_type": "Monthly Withdrawal Limit",
                "limit": str(limit),
                "value": str(amount),
                "message": limit_message,
            },
        )

    def _excess_withdrawal_test(
        self,
        transactions: Optional[list[Transaction]] = None,
        posting_instruction_groups: Optional[list[list[PostingInstruction]]] = None,
        withdrawal_limit: int = 1,
        effective_date: datetime = datetime(2020, 9, 27),
        reject_excess_withdrawals: bool = False,
    ):
        """
        Standardised test setup and execution for excess withdrawal scenarios.
        :param transactions: list of transactions for the scenario. Use posting instructions if
        more complicated posting instruction types than hard settlements are needed
        :param posting_instructions: list of posting_instructions for the scenario. Only use if
        transaction types other than hard settlements are needed. Otherwise see `transactions`.
        :param withdrawal_limit: the monthly limit for withdrawals for the scenario
        :param effective_date: the post_posting_code effective date to use
        :param reject_excess_withdrawals: the parameter value for reject_excess_withdrawals.
        Defaults to false as almost all tests need this value to check that the fees are charged
        """

        if transactions:
            pib, client_transactions, _ = self.pib_and_cts_for_transactions(
                hook_effective_date=effective_date, transactions=transactions
            )
        elif posting_instruction_groups:
            pib, client_transactions, _ = self.pib_and_cts_for_posting_instructions(
                hook_effective_date=effective_date,
                posting_instructions_groups=posting_instruction_groups,
            )
        else:
            raise ValueError("One of transactions or posting_instruction_groups must be provided")

        default_committed = Decimal(2000)

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            creation_date=datetime(2020, 9, 23, 5, 6, 7),
            balance_ts=balance_ts,
            denomination=self.default_denom,
            autosave_savings_account=OptionalValue(is_set=False),
            transaction_code_to_type_map=OptionalValue(is_set=False),
            client_transaction=client_transactions,
            excess_withdrawal_fee=Decimal("10.00"),
            reject_excess_withdrawals=UnionItemValue(str(reject_excess_withdrawals)),
            monthly_withdrawal_limit=Decimal(withdrawal_limit),
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            pib,
            effective_date,
        )

        return mock_vault

    def _excess_withdrawal_notification_test(
        self,
        transactions: Optional[list[Transaction]] = None,
        posting_instruction_groups: Optional[list[list[PostingInstruction]]] = None,
        withdrawal_limit: int = 1,
        expected_notification: Optional[Any] = None,
        effective_date: datetime = datetime(2020, 9, 27),
        reject_excess_withdrawals: bool = False,
    ):
        """
        Standardised test setup execution and assertion for excess withdrawal notifications.
        :param transactions: list of transactions for the scenario. Use posting instructions if
        more complicated posting instruction types than hard settlements are needed
        :param posting_instructions: list of posting_instructions for the scenario. Only use if
        transaction types other than hard settlements are needed. Otherwise see `transactions`.
        :param withdrawal_limit: the monthly limit for withdrawals for the scenario
        :param expected_fees: the expected fee call for the test. Can be None if no fees expected
        :param effective_date: the post_posting_code effective date to use
        :param reject_excess_withdrawals: the parameter value for reject_excess_withdrawals.
        Defaults to false as almost all tests need this value to check that the fees are charged
        """

        mock_vault = self._excess_withdrawal_test(
            transactions=transactions,
            posting_instruction_groups=posting_instruction_groups,
            withdrawal_limit=withdrawal_limit,
            effective_date=effective_date,
            reject_excess_withdrawals=reject_excess_withdrawals,
        )

        if expected_notification:
            mock_vault.instruct_notification.assert_has_calls([expected_notification])
        else:
            mock_vault.instruct_notification.assert_not_called()

    def test_notification_sent_when_withdrawal_limit_reached_with_excess_withdrawals_rejected(
        self,
    ):

        effective_date = datetime(2020, 9, 27)

        self._excess_withdrawal_notification_test(
            transactions=[Withdrawal(effective_date=effective_date, amount="14")],
            reject_excess_withdrawals=True,
            withdrawal_limit=1,
            effective_date=effective_date,
            expected_notification=self.excess_withdrawal_notification_call(
                amount=1, limit=1, reject_excess_withdrawals=True
            ),
        )

    def test_notification_sent_when_withdrawal_limit_reached_with_excess_withdrawals_accepted(
        self,
    ):

        effective_date = datetime(2020, 9, 27)

        self._excess_withdrawal_notification_test(
            transactions=[Withdrawal(effective_date=effective_date, amount="14")],
            reject_excess_withdrawals=False,
            withdrawal_limit=1,
            effective_date=effective_date,
            expected_notification=self.excess_withdrawal_notification_call(
                amount=1, limit=1, reject_excess_withdrawals=False
            ),
        )

    def test_notification_not_sent_when_withdrawal_limit_previously_reached_in_same_period(
        self,
    ):

        effective_date = datetime(2020, 9, 27)

        # two historic transactions already take us to the limit of 2, so the extra transaction
        # should not trigger an extra notification
        self._excess_withdrawal_notification_test(
            transactions=[
                Withdrawal(effective_date=effective_date - timedelta(days=2), amount="14"),
                Withdrawal(effective_date=effective_date - timedelta(days=1), amount="14"),
                Withdrawal(effective_date=effective_date, amount="14"),
            ],
            reject_excess_withdrawals=False,
            withdrawal_limit=2,
            effective_date=effective_date,
            expected_notification=None,
        )
