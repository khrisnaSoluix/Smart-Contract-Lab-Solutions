# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps as json_dumps
from unittest.mock import call, Mock
from typing import Any, Dict, List, Optional, Tuple
from inception_sdk.test_framework.contracts.unit.common import (
    ContractTest,
    Transaction,
    Withdrawal,
    Deposit,
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
    OptionalShape,
    PostingInstruction,
    BalanceDefaultDict,
    ClientTransaction,
    EventTypeSchedule,
)


CONTRACT_FILE = "library/casa/contracts/casa.py"
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
INTERNAL_CONTRA = "INTERNAL_CONTRA"
INTERNAL_POSTING = "INTERNAL_POSTING"
PNL_ACCOUNT = "1"
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
INACTIVITY_FEE_INCOME_ACCOUNT = "INACTIVITY_FEE_INCOME"
EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT = OptionalValue("EXCESS_WITHDRAWALS_INCOME")
DEPOSIT_TIER_RANGES = json_dumps(
    {
        "tier1": {"min": 0},
        "tier2": {"min": 3000.00},
        "tier3": {"min": 5000.00},
        "tier4": {"min": 7500.00},
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
DEFAULT_ACCOUNT_INACTIVITY_FEE = Decimal("0")
DEFAULT_ARRANGED_OVERDRAFT_LIMIT = Decimal("0")
DEFAULT_AUTOSAVE_ROUNDING_AMOUNT = Decimal("0")
DEFAULT_AUTOSAVE_SAVINGS_ACCOUNT = OptionalValue("12345678")
DEFAULT_DAILY_ATM_WITHDRAWAL_LIMIT = OptionalValue(Decimal("100"))
DEFAULT_DEPOSIT_INTEREST_APPLICATION_FREQUENCY = UnionItemValue(key="monthly")
DEFAULT_DEPOSIT_INTEREST_RATE_TIERS = DEPOSIT_INTEREST_RATE_TIERS_MIXED
DEFAULT_DEPOSIT_TIER_RANGES = DEPOSIT_TIER_RANGES
DEFAULT_FEES_APPLICATION_HOUR = 0
DEFAULT_FEES_APPLICATION_MINUTE = 0
DEFAULT_FEES_APPLICATION_SECOND = 0
DEFAULT_INTEREST_ACCRUAL_DAYS_IN_YEAR = UnionItemValue(key="365")
DEFAULT_INTEREST_ACCRUAL_HOUR = 0
DEFAULT_INTEREST_ACCRUAL_MINUTE = 0
DEFAULT_INTEREST_ACCRUAL_SECOND = 0
DEFAULT_INTEREST_APPLICATION_DAY = 1
DEFAULT_INTEREST_APPLICATION_HOUR = 0
DEFAULT_INTEREST_APPLICATION_MINUTE = 0
DEFAULT_INTEREST_APPLICATION_SECOND = 0
DEFAULT_INTEREST_FREE_BUFFER = json_dumps({"A": "100", "B": "300", "C": "500"})
DEFAULT_MAINTENANCE_FEE_ANNUAL = Decimal("0")
DEFAULT_MAINTENANCE_FEE_MONTHLY = Decimal("0")
DEFAULT_MINIMUM_BALANCE_FEE = Decimal("0")
DEFAULT_MINIMUM_BALANCE_THRESHOLD = json_dumps({"Z": "100"})
DEFAULT_MAXIMUM_DAILY_ATM_WITHDRAWAL_LIMIT = OptionalValue(json_dumps({"Z": 25}))
DEFAULT_OVERDRAFT_INTEREST_FREE_BUFFER_DAYS = json_dumps({"A": "-1", "B": "1", "C": "-1"})
DEFAULT_OVERDRAFT_INTEREST_RATE = Decimal("0")
DEFAULT_ACCOUNT_TIER_NAMES = json_dumps(["A", "B", "C"])
DEFAULT_TRANSACTION_CODE_TO_TYPE_MAP = OptionalValue(
    json_dumps({"": "purchase", "6011": "ATM withdrawal"}), is_set=True
)
DEFAULT_TRANSACTION_TYPES = json_dumps(["purchase", "ATM withdrawal", "transfer"])
DEFAULT_UNARRANGED_OVERDRAFT_FEE = Decimal("0")
DEFAULT_UNARRANGED_OVERDRAFT_FEE_CAP = Decimal("0")
DEFAULT_UNARRANGED_OVERDRAFT_LIMIT = Decimal("0")
MAXIMUM_DAILY_DEPOSIT = OptionalValue()
MAXIMUM_DAILY_WITHDRAWAL = OptionalValue()
MINIMUM_DEPOSIT = OptionalValue()
MINIMUM_WITHDRAWAL = OptionalValue()
MAXIMUM_BALANCE = OptionalValue()
DEFAULT_REJECT_EXCESS_WITHDRAWALS = OptionalValue(is_set=False)
REJECT_EXCESS_WITHDRAWALS_FALSE = OptionalValue(UnionItemValue("false"))
MONTHLY_WITHDRAWAL_LIMIT = OptionalValue(is_set=False)
EXCESS_WITHDRAWAL_FEE = OptionalValue(is_set=False)

INTERNAL_CLIENT_TRANSATION_ID_0 = INTERNAL_POSTING + "_CT_ID_0"


class CASATest(ContractTest):
    default_denom = DEFAULT_DENOMINATION
    contract_file = CONTRACT_FILE
    side = Tside.LIABILITY
    linked_contract_modules = {
        "utils": {
            "path": UTILS_MODULE_FILE,
        },
        "interest": {"path": INTEREST_MODULE_FILE},
    }

    def create_mock(
        self,
        balance_ts=None,
        postings=None,
        creation_date=DEFAULT_DATE,
        client_transaction: Optional[Dict[Tuple, ClientTransaction]] = None,
        client_transaction_excluding_proposed: Optional[Dict[Tuple, ClientTransaction]] = None,
        flags=None,
        account_inactivity_fee=DEFAULT_ACCOUNT_INACTIVITY_FEE,
        additional_denominations=ADDITIONAL_DENOMINATIONS,
        arranged_overdraft_limit=OptionalValue(DEFAULT_ARRANGED_OVERDRAFT_LIMIT),
        autosave_rounding_amount=DEFAULT_AUTOSAVE_ROUNDING_AMOUNT,
        autosave_savings_account=DEFAULT_AUTOSAVE_SAVINGS_ACCOUNT,
        daily_atm_withdrawal_limit=DEFAULT_DAILY_ATM_WITHDRAWAL_LIMIT,
        denomination=DEFAULT_DENOMINATION,
        deposit_interest_application_frequency=DEFAULT_DEPOSIT_INTEREST_APPLICATION_FREQUENCY,
        deposit_interest_rate_tiers=DEFAULT_DEPOSIT_INTEREST_RATE_TIERS,
        deposit_tier_ranges=DEFAULT_DEPOSIT_TIER_RANGES,
        fees_application_hour=DEFAULT_FEES_APPLICATION_HOUR,
        fees_application_minute=DEFAULT_FEES_APPLICATION_MINUTE,
        fees_application_second=DEFAULT_FEES_APPLICATION_SECOND,
        interest_accrual_days_in_year=DEFAULT_INTEREST_ACCRUAL_DAYS_IN_YEAR,
        interest_accrual_hour=DEFAULT_INTEREST_ACCRUAL_HOUR,
        interest_accrual_minute=DEFAULT_INTEREST_ACCRUAL_MINUTE,
        interest_accrual_second=DEFAULT_INTEREST_ACCRUAL_SECOND,
        interest_application_day=DEFAULT_INTEREST_APPLICATION_DAY,
        interest_application_hour=DEFAULT_INTEREST_APPLICATION_HOUR,
        interest_application_minute=DEFAULT_INTEREST_APPLICATION_MINUTE,
        interest_application_second=DEFAULT_INTEREST_APPLICATION_SECOND,
        interest_free_buffer=OptionalValue(DEFAULT_INTEREST_FREE_BUFFER),
        maintenance_fee_annual=DEFAULT_MAINTENANCE_FEE_ANNUAL,
        maintenance_fee_monthly=DEFAULT_MAINTENANCE_FEE_MONTHLY,
        minimum_balance_fee=DEFAULT_MINIMUM_BALANCE_FEE,
        minimum_balance_threshold=DEFAULT_MINIMUM_BALANCE_THRESHOLD,
        maximum_daily_atm_withdrawal_limit=DEFAULT_MAXIMUM_DAILY_ATM_WITHDRAWAL_LIMIT,
        overdraft_interest_free_buffer_days=OptionalValue(
            DEFAULT_OVERDRAFT_INTEREST_FREE_BUFFER_DAYS
        ),
        overdraft_interest_rate=OptionalValue(DEFAULT_OVERDRAFT_INTEREST_RATE),
        account_tier_names=DEFAULT_ACCOUNT_TIER_NAMES,
        transaction_code_to_type_map=DEFAULT_TRANSACTION_CODE_TO_TYPE_MAP,
        unarranged_overdraft_fee=OptionalValue(DEFAULT_UNARRANGED_OVERDRAFT_FEE),
        unarranged_overdraft_fee_cap=OptionalValue(DEFAULT_UNARRANGED_OVERDRAFT_FEE_CAP),
        unarranged_overdraft_limit=OptionalValue(DEFAULT_UNARRANGED_OVERDRAFT_LIMIT),
        annual_maintenance_fee_income_account=ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
        accrued_interest_payable_account=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
        accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
        inactivity_fee_income_account=INACTIVITY_FEE_INCOME_ACCOUNT,
        interest_paid_account=INTEREST_PAID_ACCOUNT,
        interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        maintenance_fee_income_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
        minimum_balance_fee_income_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
        excess_withdrawal_fee_income_account=EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
        overdraft_fee_income_account=OptionalValue(OVERDRAFT_FEE_INCOME_ACCOUNT),
        overdraft_fee_receivable_account=OptionalValue(OVERDRAFT_FEE_RECEIVABLE_ACCOUNT),
        maximum_daily_deposit=MAXIMUM_DAILY_DEPOSIT,
        maximum_daily_withdrawal=MAXIMUM_DAILY_WITHDRAWAL,
        minimum_deposit=MINIMUM_DEPOSIT,
        minimum_withdrawal=MINIMUM_WITHDRAWAL,
        maximum_balance=MAXIMUM_BALANCE,
        reject_excess_withdrawals=DEFAULT_REJECT_EXCESS_WITHDRAWALS,
        monthly_withdrawal_limit=MONTHLY_WITHDRAWAL_LIMIT,
        excess_withdrawal_fee=EXCESS_WITHDRAWAL_FEE,
    ):
        params = {
            key: {"value": value}
            for key, value in locals().items()
            if key not in self.locals_to_ignore
        }
        parameter_ts = self.param_map_to_timeseries(params, creation_date)

        balance_ts = balance_ts or []
        postings = postings or []
        creation_date = DEFAULT_DATE
        flags = flags or []

        return super().create_mock(
            balance_ts=balance_ts,
            parameter_ts=parameter_ts,
            postings=postings,
            creation_date=creation_date,
            client_transaction=client_transaction,
            client_transaction_excluding_proposed=client_transaction_excluding_proposed,
            flags=flags,
        )

    def account_balances(
        self,
        dt=DEFAULT_DATE,
        balance_defs: Optional[List[dict[str, str]]] = None,
        default_committed=Decimal("0"),
        default_pending_in=Decimal("0"),
        default_pending_out=Decimal("0"),
        accrued_deposit_payable=Decimal("0"),
        accrued_deposit_receivable=Decimal("0"),
        accrued_overdraft_receivable=Decimal("0"),
        accrued_overdraft_fee_receivable=Decimal("0"),
    ) -> List[Tuple[datetime, BalanceDefaultDict]]:

        balance_dict = {
            balance_dimensions(denomination=DEFAULT_DENOMINATION): Balance(net=default_committed),
            balance_dimensions(denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_IN): Balance(
                net=default_pending_in
            ),
            balance_dimensions(denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_OUT): Balance(
                net=default_pending_out
            ),
            balance_dimensions(
                denomination=DEFAULT_DENOMINATION, address=ACCRUED_OVERDRAFT_RECEIVABLE
            ): Balance(net=accrued_overdraft_receivable),
            balance_dimensions(
                denomination=DEFAULT_DENOMINATION, address=ACCRUED_DEPOSIT_PAYABLE
            ): Balance(net=accrued_deposit_payable),
            balance_dimensions(
                denomination=DEFAULT_DENOMINATION, address=ACCRUED_DEPOSIT_RECEIVABLE
            ): Balance(net=accrued_deposit_receivable),
            balance_dimensions(
                denomination=DEFAULT_DENOMINATION, address=ACCRUED_OVERDRAFT_RECEIVABLE
            ): Balance(net=accrued_overdraft_receivable),
            balance_dimensions(
                denomination=DEFAULT_DENOMINATION, address=ACCRUED_OVERDRAFT_FEE_RECEIVABLE
            ): Balance(net=accrued_overdraft_fee_receivable),
        }

        balance_default_dict = BalanceDefaultDict(lambda: Balance(net=Decimal("0")), balance_dict)
        balance_defs_default_dict = self.init_balances(dt, balance_defs)[0][1]

        return [(dt, balance_default_dict + balance_defs_default_dict)]

    def _maintenance_fee_setup_and_run(
        self,
        event_type,
        effective_time=DEFAULT_DATE,
        monthly_fee=Decimal("0"),
        annual_fee=Decimal("0"),
        flags=None,
    ):
        default_committed = Decimal("0")
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        flags = flags or []

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            maintenance_fee_monthly=monthly_fee,
            account_inactivity_fee=Decimal("0"),
            maintenance_fee_annual=annual_fee,
            minimum_balance_fee=Decimal("0"),
            account_tier_names=json_dumps(["Z"]),
            minimum_balance_threshold=json_dumps({"Z": "100"}),
            fees_application_hour=0,
            fees_application_minute=0,
            fees_application_second=0,
            flags=flags,
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


class CASAGeneralTest(CASATest):
    def test_pre_posting_code_rejects_postings_in_wrong_denomination(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("2000")
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_auth(amount=10, denomination="HKD")],
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

    def test_pre_posting_code_rejects_postings_over_unarranged_overdraft_limit(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("0")
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_auth(
                    denomination=DEFAULT_DENOMINATION,
                    amount=1000,
                )
            ],
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination="GBP",
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            unarranged_overdraft_limit=OptionalValue(900),
        )

        with self.assertRaises(Rejected) as e:
            self.run_function("pre_posting_code", mock_vault, test_postings, effective_time)

        self.assertEqual(str(e.exception), "Posting exceeds unarranged_overdraft_limit.")
        self.assertEqual(e.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)

    def test_pre_posting_code_accepts_posting_within_unarranged_overdraft(self):
        effective_time = datetime(2019, 1, 1)
        accrued_overdraft_receivable = Decimal("0")
        default_committed = Decimal("0")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft_receivable=accrued_overdraft_receivable,
            default_committed=default_committed,
        )

        posting_instructions = [
            self.outbound_auth(
                denomination=DEFAULT_DENOMINATION,
                amount=100,
                value_timestamp=effective_time,
            )
        ]

        pib, client_transaction, _ = self.pib_and_cts_for_posting_instructions(
            effective_time, posting_instructions_groups=[posting_instructions]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            unarranged_overdraft_limit=OptionalValue(Decimal("900")),
            daily_atm_withdrawal_limit=OptionalValue(Decimal("100")),
            client_transaction=client_transaction,
        )

        try:
            self.run_function("pre_posting_code", mock_vault, pib, effective_time)
        except Exception as e:
            self.fail(f"Exception was raised: {e}")

    def test_scheduled_code_does_not_accrue_when_balance_lt_buffer(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("-40")
        accrued_overdraft_receivable = Decimal("0")
        account_tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "200", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "-1", "B": "1", "C": "-1"})

        balance_ts = self.account_balances(
            effective_time - timedelta(days=1),
            accrued_overdraft_receivable=accrued_overdraft_receivable,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            account_tier_names=account_tier_names,
            flags=["B"],
            interest_free_buffer=OptionalValue(tiered_param_od_buffer_amount),
            overdraft_interest_rate=OptionalValue(Decimal("0.1555")),
            unarranged_overdraft_fee=OptionalValue(Decimal("50")),
            unarranged_overdraft_fee_cap=OptionalValue(Decimal("80")),
            arranged_overdraft_limit=OptionalValue(Decimal("50")),
            unarranged_overdraft_limit=OptionalValue(Decimal("900")),
            deposit_tier_ranges=DEPOSIT_TIER_RANGES,
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            overdraft_interest_free_buffer_days=OptionalValue(tiered_param_od_buffer_period),
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

        mock_vault.instruct_posting_batch.assert_not_called()

    def test_account_monthly_maintenance_fee_not_applied_if_zero(self):
        expected_maintenance_fee = Decimal("0")
        mock_vault = self._maintenance_fee_setup_and_run(
            event_type="APPLY_MONTHLY_FEES", monthly_fee=expected_maintenance_fee
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()

        mock_vault.instruct_posting_batch.assert_not_called()

    def test_account_monthly_maintenance_fee_applied(self):
        expected_maintenance_fee = Decimal("10")
        effective_time = DEFAULT_DATE
        mock_vault = self._maintenance_fee_setup_and_run(
            event_type="APPLY_MONTHLY_FEES",
            effective_time=effective_time,
            monthly_fee=expected_maintenance_fee,
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
            client_transaction_id=f"APPLY_MONTHLY_FEES_MAINTENANCE_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}_INTERNAL",
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "APPLY_MONTHLY_FEES_MAINTENANCE_MOCK_HOOK_GBP_INTERNAL",
            ],
            effective_date=effective_time,
        )

    def test_extracting_tiered_param_no_flag_on_account(self):
        tiered_param = dict(good=1000, bad=5)

        mock_vault = self.create_mock(
            account_tier_names=json_dumps(["good", "ugly", "bad"]), flags=[]
        )

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            mock_vault,
            mock_vault,
            tiered_param=tiered_param,
        )
        self.assertEqual(result, 5)

    def test_extracting_tiered_param_no_flag_on_account_different_order(self):
        tiered_param = dict(good=1000, bad=5)

        mock_vault = self.create_mock(account_tier_names=json_dumps(["bad", "good"]), flags=[])

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            mock_vault,
            mock_vault,
            tiered_param=tiered_param,
        )
        self.assertEqual(result, 1000)

    def test_extracting_tiered_param_account_has_first_flag(self):
        tiered_param = dict(good=1000, bad=5)

        mock_vault = self.create_mock(
            account_tier_names=json_dumps(["good", "bad"]), flags=["good"]
        )

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            mock_vault,
            mock_vault,
            tiered_param=tiered_param,
        )
        self.assertEqual(result, 1000)

    def test_extracting_tiered_param_account_has_middle_flag(self):
        tiered_param = dict(good=1000, ugly=500, bad=5)
        mock_vault = self.create_mock(
            account_tier_names=json_dumps(["good", "ugly", "bad"]), flags=["ugly"]
        )

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            mock_vault,
            mock_vault,
            tiered_param=tiered_param,
        )
        self.assertEqual(result, 500)

    def test_extracting_tiered_param_account_has_last_flag(self):
        tiered_param = dict(good=1000, ugly=500, bad=5)
        mock_vault = self.create_mock(
            account_tier_names=json_dumps(["good", "ugly", "bad"]), flags=["bad"]
        )

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            mock_vault,
            mock_vault,
            tiered_param=tiered_param,
        )
        self.assertEqual(result, 5)

    def test_extracting_tiered_param_account_has_multiple_flags_uses_first(self):
        tiered_param = dict(good=1000, ugly=500, bad=5)
        mock_vault = self.create_mock(
            account_tier_names=json_dumps(["good", "ugly", "bad"]), flags=["bad", "good", "ugly"]
        )

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            mock_vault,
            mock_vault,
            tiered_param=tiered_param,
        )
        self.assertEqual(result, 1000)

    def test_extracting_tiered_param_account_has_different_flag(self):
        tiered_param = dict(good=1000, ugly=500, bad=5)
        mock_vault = self.create_mock(
            account_tier_names=json_dumps(["good", "ugly", "bad"]), flags=["foo"]
        )

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            mock_vault,
            mock_vault,
            tiered_param=tiered_param,
        )
        self.assertEqual(result, 5)

    def test_extracting_tiered_param_with_tier_provided(self):
        tiered_param = dict(good=1000, ugly=500, bad=5)
        mock_vault = self.create_mock()

        result = self.run_function(
            "_get_dict_value_based_on_account_tier_flag",
            mock_vault,
            mock_vault,
            tiered_param=tiered_param,
            tier_name="ugly",
        )
        self.assertEqual(result, 500)

    def test_no_tier_parameter_configured(self):
        tiered_param = dict(good=1000, ugly=500, bad=5)
        mock_vault = self.create_mock(flags=["foo"])

        with self.assertRaises(InvalidContractParameter) as e:
            self.run_function(
                "_get_dict_value_based_on_account_tier_flag",
                mock_vault,
                mock_vault,
                tiered_param=tiered_param,
            )
        self.assertEqual(
            str(e.exception),
            "No valid account tiers have been configured for this product.",
        )

    def test_account_under_balance_fee_not_applied_if_mean_balance_above_threshold(
        self,
    ):
        effective_time = datetime(2020, 2, 1)
        expected_minimum_balance_fee = Decimal("100")

        period_start = effective_time - relativedelta(months=1)
        balance_ts = self.account_balances(dt=period_start, default_committed=Decimal("100"))

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            maintenance_fee_monthly=Decimal("0"),
            account_tier_names=json_dumps(["Z"]),
            minimum_balance_threshold=json_dumps({"Z": "100"}),
            minimum_balance_fee=expected_minimum_balance_fee,
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
        expected_minimum_balance_fee = Decimal("100")

        period_start = effective_time - relativedelta(months=1)

        balance_ts = self.account_balances(dt=period_start, default_committed=Decimal("0"))

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            maintenance_fee_monthly=Decimal("0"),
            account_tier_names=json_dumps(["X", "Y", "Z"]),
            minimum_balance_threshold=json_dumps({"X": "25", "Y": "50", "Z": "100"}),
            minimum_balance_fee=expected_minimum_balance_fee,
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
            client_transaction_id=f"APPLY_MONTHLY_FEES_MEAN_BALANCE_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}_INTERNAL",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "APPLY_MONTHLY_FEES_MEAN_BALANCE_MOCK_HOOK_GBP_INTERNAL",
            ],
            effective_date=effective_time,
        )

    def test_account_mean_balance_fee_period_with_fee_charged(self):
        fee_hour = 23
        fee_minute = 0
        fee_second = 0
        anniversary = datetime(2020, 2, 1)
        effective_time = anniversary.replace(hour=fee_hour, minute=fee_minute, second=fee_second)
        expected_period_start = datetime(2020, 1, 1)
        expected_period_end = datetime(2020, 1, 31, fee_hour, fee_minute, fee_second)
        expected_minimum_balance_fee = Decimal("100")
        expected_minimum_balance_threshold = Decimal("100")

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
            maintenance_fee_monthly=Decimal("0"),
            account_tier_names=json_dumps(["Z"]),
            minimum_balance_threshold=json_dumps({"Z": "100"}),
            minimum_balance_fee=expected_minimum_balance_fee,
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
            client_transaction_id=f"APPLY_MONTHLY_FEES_MEAN_BALANCE_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}_INTERNAL",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "APPLY_MONTHLY_FEES_MEAN_BALANCE_MOCK_HOOK_GBP_INTERNAL",
            ],
            effective_date=effective_time,
        )

    def test_account_mean_balance_fee_period_with_fee_not_charged(self):
        fee_hour = 23
        fee_minute = 0
        fee_second = 0
        anniversary = datetime(2020, 2, 1)
        effective_time = anniversary.replace(hour=fee_hour, minute=fee_minute, second=fee_second)
        expected_period_start = datetime(2020, 1, 1)
        expected_period_end = datetime(2020, 1, 31, fee_hour, fee_minute, fee_second)
        expected_minimum_balance_fee = Decimal("100")
        expected_minimum_balance_threshold = Decimal("100")

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
            maintenance_fee_monthly=Decimal("0"),
            account_tier_names=json_dumps(["Z"]),
            minimum_balance_threshold=json_dumps({"Z": "100"}),
            minimum_balance_fee=expected_minimum_balance_fee,
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
        fee_hour = 0
        fee_minute = 0
        fee_second = 0
        anniversary = datetime(2019, 3, 15)
        effective_time = anniversary.replace(hour=fee_hour, minute=fee_minute, second=fee_second)
        expected_period_start = datetime(2019, 2, 15)
        expected_period_end = datetime(2019, 3, 14, fee_hour, fee_minute, fee_second)
        expected_minimum_balance_fee = Decimal("100")
        expected_minimum_balance_threshold = Decimal("100")

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
            maintenance_fee_monthly=Decimal("0"),
            account_inactivity_fee=Decimal("10"),
            account_tier_names=json_dumps(["Z"]),
            minimum_balance_threshold=json_dumps({"Z": "100"}),
            minimum_balance_fee=expected_minimum_balance_fee,
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
            client_transaction_id=f"APPLY_MONTHLY_FEES_MEAN_BALANCE_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}_INTERNAL",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "APPLY_MONTHLY_FEES_MEAN_BALANCE_MOCK_HOOK_GBP_INTERNAL",
            ],
            effective_date=effective_time,
        )

    def test_account_under_balance_fee_sampling_in_leap_year_february(self):
        fee_hour = 0
        fee_minute = 0
        fee_second = 0
        anniversary = datetime(2020, 3, 15)
        effective_time = anniversary.replace(hour=fee_hour, minute=fee_minute, second=fee_second)
        expected_period_start = datetime(2020, 2, 15)
        expected_period_end = datetime(2020, 3, 14, fee_hour, fee_minute, fee_second)
        expected_minimum_balance_fee = Decimal("100")
        expected_minimum_balance_threshold = Decimal("100")

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
            maintenance_fee_monthly=Decimal("0"),
            account_tier_names=json_dumps(["Z"]),
            minimum_balance_threshold=json_dumps({"Z": "100"}),
            minimum_balance_fee=expected_minimum_balance_fee,
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
            client_transaction_id=f"APPLY_MONTHLY_FEES_MEAN_BALANCE_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}_INTERNAL",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "APPLY_MONTHLY_FEES_MEAN_BALANCE_MOCK_HOOK_GBP_INTERNAL",
            ],
            effective_date=effective_time,
        )

    def test_account_monthly_maintenance_and_minimum_balance_and_overdraft_fee_all_applied(
        self,
    ):
        effective_time = DEFAULT_DATE
        default_committed = Decimal("-10000")
        expected_maintenance_fee = Decimal("10")
        expected_minimum_balance_fee = Decimal("100")
        expected_unarranged_overdraft_fee = Decimal("50")
        balance_ts = self.account_balances(
            effective_time,
            default_committed=default_committed,
            accrued_overdraft_fee_receivable=-expected_unarranged_overdraft_fee,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            maintenance_fee_monthly=expected_maintenance_fee,
            account_tier_names=json_dumps(["Z"]),
            minimum_balance_threshold=json_dumps({"Z": "100"}),
            minimum_balance_fee=expected_minimum_balance_fee,
            fees_application_hour=23,
            fees_application_minute=0,
            fees_application_second=0,
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            overdraft_fee_income_account=OptionalValue(OVERDRAFT_FEE_INCOME_ACCOUNT),
            overdraft_fee_receivable_account=OptionalValue(OVERDRAFT_FEE_RECEIVABLE_ACCOUNT),
            maintenance_fee_income_account=MAINTENANCE_FEE_INCOME_ACCOUNT,
            minimum_balance_fee_income_account=MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            unarranged_overdraft_fee=OptionalValue(expected_unarranged_overdraft_fee),
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_MONTHLY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_unarranged_overdraft_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            to_account_id="Main account",
            to_account_address="ACCRUED_OVERDRAFT_FEE_RECEIVABLE",
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_FEES_CUSTOMER_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Overdraft fees applied.",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_unarranged_overdraft_fee,
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
            client_transaction_id=f"APPLY_MONTHLY_FEES_MAINTENANCE_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}_INTERNAL",
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
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
            client_transaction_id=f"APPLY_MONTHLY_FEES_MEAN_BALANCE_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}_INTERNAL",
            instruction_details={
                "description": "Minimum balance fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_has_calls(
            [
                call(
                    client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
                    effective_date=effective_time,
                    posting_instructions=[
                        "APPLY_FEES_CUSTOMER_MOCK_HOOK_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_"
                        "COMMERCIAL_BANK_MONEY_GBP",
                        "APPLY_FEES_GL_MOCK_HOOK_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_"
                        "COMMERCIAL_BANK_MONEY_GBP",
                        "APPLY_MONTHLY_FEES_MAINTENANCE_MOCK_HOOK_GBP_INTERNAL",
                        "APPLY_MONTHLY_FEES_MEAN_BALANCE_MOCK_HOOK_GBP_INTERNAL",
                    ],
                ),
            ]
        )

    def test_account_annual_maintenance_fee_applied(self):
        expected_maintenance_fee = Decimal("10")
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
            client_transaction_id=f"APPLY_ANNUAL_FEES_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}_INTERNAL",
            instruction_details={
                "description": "Annual maintenance fee",
                "event": "APPLY_ANNUAL_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ANNUAL_FEES_MOCK_HOOK",
            posting_instructions=[
                "APPLY_ANNUAL_FEES_MOCK_HOOK_GBP_INTERNAL",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_accrues_interest_and_charges_fee_at_eod(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("-200")
        accrued_overdraft_receivable = Decimal("200")
        expected_unarranged_overdraft_fee = Decimal("50")
        overdraft_interest_rate = Decimal("0.15695")
        interest_free_buffer = Decimal("100")
        account_tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "100", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "-1", "B": "1", "C": "-1"})
        daily_interest_rate = overdraft_interest_rate / 365
        daily_interest_rate_percent = daily_interest_rate * 100

        expected_interest_accrual = Decimal("0.04300").copy_abs().quantize(Decimal(".00001"))

        balance_ts = self.account_balances(
            effective_time - timedelta(days=1),
            accrued_overdraft_receivable=accrued_overdraft_receivable,
            default_committed=default_committed,
            accrued_overdraft_fee_receivable=expected_unarranged_overdraft_fee,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            account_tier_names=account_tier_names,
            flags=["A"],
            interest_free_buffer=OptionalValue(tiered_param_od_buffer_amount),
            overdraft_interest_free_buffer_days=OptionalValue(tiered_param_od_buffer_period),
            overdraft_interest_rate=OptionalValue(overdraft_interest_rate),
            unarranged_overdraft_fee=OptionalValue(Decimal("50")),
            unarranged_overdraft_fee_cap=OptionalValue(Decimal("80")),
            arranged_overdraft_limit=OptionalValue(Decimal("10")),
            unarranged_overdraft_limit=OptionalValue(Decimal("10")),
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
            overdraft_fee_income_account=OptionalValue(OVERDRAFT_FEE_INCOME_ACCOUNT),
            overdraft_fee_receivable_account=OptionalValue(OVERDRAFT_FEE_RECEIVABLE_ACCOUNT),
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at "
                f"{daily_interest_rate_percent:0.5f}%"
                f" on balance of {default_committed + interest_free_buffer:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=INTEREST_RECEIVED_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at "
                f"{daily_interest_rate_percent:0.5f}%"
                f" on balance of {default_committed + interest_free_buffer:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_unarranged_overdraft_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_OVERDRAFT_FEE_RECEIVABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_FEES_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Unarranged overdraft fee accrued.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_unarranged_overdraft_fee,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=OVERDRAFT_FEE_INCOME_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_FEES_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Unarranged overdraft fee accrued.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                "ACCRUE_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_GL_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_FEES_CUSTOMER_MOCK_HOOK_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_FEES_GL_MOCK_HOOK_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_scheduled_code_applies_accrued_overdraft_receivable_interest(self):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0")
        accrued_overdraft_receivable_balance = Decimal("-10")
        default_committed = Decimal("-200")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft_receivable=accrued_overdraft_receivable_balance,
            default_committed=default_committed,
            accrued_overdraft_fee_receivable=overdraft_fee_balance,
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
            event_type="APPLY_ACCRUED_INTEREST",
        )

        expected_fulfilment = Decimal("10.00")

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            to_account_id="Main account",
            to_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK",
            posting_instructions=[
                "APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_applies_accrued_deposit_and_overdraft_receivable_interest(self):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0")
        accrued_overdraft_receivable_balance = Decimal("-10")
        default_committed = Decimal("-200")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft_receivable=accrued_overdraft_receivable_balance,
            default_committed=default_committed,
            accrued_overdraft_fee_receivable=overdraft_fee_balance,
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
            event_type="APPLY_ACCRUED_INTEREST",
        )

        expected_fulfilment = Decimal("10.00")

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            to_account_id="Main account",
            to_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK",
            posting_instructions=[
                "APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_accrues_positive_deposit_interest_at_eod(self):
        effective_time = datetime(2019, 1, 1)
        deposit_interest_yearly_rate = Decimal("0.0300")
        deposit_daily_rate = deposit_interest_yearly_rate / 365
        deposit_daily_rate_percentage = deposit_daily_rate * 100
        default_committed = Decimal("1000")
        account_tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "100", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "-1", "B": "1", "C": "-1"})
        expected_deposit_interest_accrual = Decimal("0.08219")

        balance_ts = self.account_balances(
            effective_time - timedelta(days=1), default_committed=default_committed
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            account_tier_names=account_tier_names,
            flags=["A"],
            deposit_interest_rate_tiers=DEPOSIT_INTEREST_RATE_TIERS_POSITIVE,
            deposit_tier_ranges=DEPOSIT_TIER_RANGES,
            overdraft_interest_rate=OptionalValue(Decimal("0.1555")),
            interest_free_buffer=OptionalValue(tiered_param_od_buffer_amount),
            unarranged_overdraft_fee=OptionalValue(Decimal("50")),
            unarranged_overdraft_fee_cap=OptionalValue(Decimal("80")),
            arranged_overdraft_limit=OptionalValue(Decimal("10")),
            unarranged_overdraft_limit=OptionalValue(Decimal("10")),
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            overdraft_interest_free_buffer_days=OptionalValue(tiered_param_od_buffer_period),
            accrued_interest_payable_account=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            interest_paid_account=INTEREST_PAID_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_deposit_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=INTEREST_PAID_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_GL_TIER1_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at "
                f"{deposit_daily_rate_percentage:0.5f}%"
                f" on balance of {default_committed:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_deposit_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            to_account_id="Main account",
            to_account_address=ACCRUED_DEPOSIT_PAYABLE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_TIER1_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at "
                f"{deposit_daily_rate_percentage:0.5f}%"
                f" on balance of {default_committed:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                "ACCRUE_INTEREST_CUSTOMER_TIER1_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_GL_TIER1_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_scheduled_code_accrues_negative_deposit_interest_at_eod(self):
        effective_time = datetime(2019, 1, 1)
        deposit_interest_yearly_rate = Decimal("-0.0300")
        deposit_daily_rate = deposit_interest_yearly_rate / 365
        deposit_daily_rate_percentage = deposit_daily_rate * 100
        default_committed = Decimal("1000")
        account_tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "100", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "-1", "B": "1", "C": "-1"})
        expected_deposit_interest_accrual = Decimal("0.08219")

        balance_ts = self.account_balances(
            effective_time - timedelta(days=1), default_committed=default_committed
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            account_tier_names=account_tier_names,
            flags=["A"],
            deposit_interest_rate_tiers=DEPOSIT_INTEREST_RATE_TIERS_NEGATIVE,
            deposit_tier_ranges=DEPOSIT_TIER_RANGES,
            overdraft_interest_rate=OptionalValue(Decimal("0.1555")),
            interest_free_buffer=OptionalValue(tiered_param_od_buffer_amount),
            unarranged_overdraft_fee=OptionalValue(Decimal("50")),
            unarranged_overdraft_fee_cap=OptionalValue(Decimal("80")),
            arranged_overdraft_limit=OptionalValue(Decimal("10")),
            unarranged_overdraft_limit=OptionalValue(Decimal("10")),
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            overdraft_interest_free_buffer_days=OptionalValue(tiered_param_od_buffer_period),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_deposit_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=INTEREST_RECEIVED_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_GL_TIER1_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at "
                f"{deposit_daily_rate_percentage:0.5f}%"
                f" on balance of {default_committed:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_deposit_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_TIER1_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at "
                f"{deposit_daily_rate_percentage:0.5f}%"
                f" on balance of {default_committed:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                "ACCRUE_INTEREST_CUSTOMER_TIER1_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_GL_TIER1_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_scheduled_code_zero_deposit_interest_rate_accrues_nothing(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("1000")
        account_tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "200", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "-1", "B": "1", "C": "-1"})
        balance_ts = self.account_balances(
            effective_time,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            flags=["B"],
            account_tier_names=account_tier_names,
            deposit_interest_rate_tiers=json_dumps({"tier1": "0.00"}),
            deposit_tier_ranges=json_dumps({"tier1": {"min": 0}}),
            overdraft_interest_rate=OptionalValue(Decimal("0.1555")),
            interest_free_buffer=OptionalValue(tiered_param_od_buffer_amount),
            unarranged_overdraft_fee=OptionalValue(Decimal("50")),
            unarranged_overdraft_fee_cap=OptionalValue(Decimal("80")),
            arranged_overdraft_limit=OptionalValue(Decimal("10")),
            unarranged_overdraft_limit=OptionalValue(Decimal("10")),
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            overdraft_interest_free_buffer_days=OptionalValue(tiered_param_od_buffer_period),
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

    def test_scheduled_code_applies_accrued_negative_deposit_interest(self):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0.00")
        accrued_overdraft_receivable = Decimal("0.00")
        default_committed = Decimal("1000.00")
        accrued_deposit = Decimal("-10.00")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft_receivable=accrued_overdraft_receivable,
            default_committed=default_committed,
            accrued_overdraft_fee_receivable=overdraft_fee_balance,
            accrued_deposit_receivable=accrued_deposit,
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
            event_type="APPLY_ACCRUED_INTEREST",
        )

        expected_fulfilment = Decimal("10.00")

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            to_account_id="Main account",
            to_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK",
            posting_instructions=[
                "APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_applies_accrued_positive_deposit_interest(self):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0.00")
        accrued_overdraft_receivable = Decimal("0.00")
        default_committed = Decimal("1000.00")
        accrued_deposit = Decimal("10.00")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft_receivable=accrued_overdraft_receivable,
            default_committed=default_committed,
            accrued_overdraft_fee_receivable=overdraft_fee_balance,
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
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            effective_date=effective_time,
            event_type="APPLY_ACCRUED_INTEREST",
        )

        expected_fulfilment = Decimal("10.00")

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_DEPOSIT_PAYABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id="Main account",
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK",
            posting_instructions=[
                "APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_" "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_reverses_accrued_positive_deposit_interest_with_neg_remainder(
        self,
    ):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0.00")
        accrued_overdraft_receivable = Decimal("0.00")
        default_committed = Decimal("1000.00")
        accrued_deposit = Decimal("10.03565")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft_receivable=accrued_overdraft_receivable,
            default_committed=default_committed,
            accrued_overdraft_fee_receivable=overdraft_fee_balance,
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
            event_type="APPLY_ACCRUED_INTEREST",
        )

        expected_interest_fulfilment = Decimal("10.04")
        expected_rounding_fulfilment = Decimal("0.00435")

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_DEPOSIT_PAYABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id="Main account",
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_rounding_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            to_account_id="Main account",
            to_account_address=ACCRUED_DEPOSIT_PAYABLE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Zero out remainder after accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_rounding_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=INTEREST_PAID_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Zero out remainder after accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK",
            posting_instructions=[
                "APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_" "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_GL_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_" "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_reverses_accrued_positive_deposit_interest_with_pos_remainder(
        self,
    ):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0.00")
        accrued_overdraft_receivable = Decimal("0.00")
        default_committed = Decimal("1000.00")
        accrued_deposit = Decimal("10.03465")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft_receivable=accrued_overdraft_receivable,
            default_committed=default_committed,
            accrued_overdraft_fee_receivable=overdraft_fee_balance,
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
            event_type="APPLY_ACCRUED_INTEREST",
        )

        expected_interest_fulfilment = Decimal("10.03")
        expected_rounding_fulfilment = Decimal("0.00465")

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_DEPOSIT_PAYABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id="Main account",
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_rounding_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_DEPOSIT_PAYABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"REVERSE_ACCRUED_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Zero out remainder after accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_rounding_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=INTEREST_PAID_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"REVERSE_ACCRUED_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Zero out remainder after accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK",
            posting_instructions=[
                "APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_" "COMMERCIAL_BANK_MONEY_GBP",
                "REVERSE_ACCRUED_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "REVERSE_ACCRUED_INTEREST_GL_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_reverses_accrued_negative_deposit_interest_with_neg_remainder(
        self,
    ):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0.00")
        accrued_overdraft_receivable = Decimal("0.00")
        default_committed = Decimal("1000.00")
        accrued_deposit = Decimal("-10.03565")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft_receivable=accrued_overdraft_receivable,
            default_committed=default_committed,
            accrued_overdraft_fee_receivable=overdraft_fee_balance,
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
            event_type="APPLY_ACCRUED_INTEREST",
        )

        expected_interest_fulfilment = Decimal("10.04")
        expected_rounding_fulfilment = Decimal("0.00435")

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            to_account_id="Main account",
            to_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_rounding_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Zero out remainder after accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_rounding_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=INTEREST_RECEIVED_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Zero out remainder after accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK",
            posting_instructions=[
                "APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_GL_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time,
        )

    def test_scheduled_code_reverses_accrued_negative_deposit_interest_with_pos_remainder(
        self,
    ):
        effective_time = datetime(2019, 1, 1)
        overdraft_fee_balance = Decimal("0.00")
        accrued_overdraft_receivable = Decimal("0.00")
        default_committed = Decimal("1000.00")
        accrued_deposit = Decimal("-10.03465")
        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft_receivable=accrued_overdraft_receivable,
            default_committed=default_committed,
            accrued_overdraft_fee_receivable=overdraft_fee_balance,
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
            event_type="APPLY_ACCRUED_INTEREST",
        )

        expected_interest_fulfilment = Decimal("10.03")
        expected_rounding_fulfilment = Decimal("0.00465")

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            to_account_id="Main account",
            to_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_fulfilment,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"APPLY_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_rounding_fulfilment,
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            denomination=DEFAULT_DENOMINATION,
            to_account_id="Main account",
            to_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"REVERSE_ACCRUED_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Zero out remainder after accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_rounding_fulfilment,
            from_account_id=INTEREST_RECEIVED_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            denomination=DEFAULT_DENOMINATION,
            to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"REVERSE_ACCRUED_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": "Zero out remainder after accrued interest applied.",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK",
            posting_instructions=[
                "APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "REVERSE_ACCRUED_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "REVERSE_ACCRUED_INTEREST_GL_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time,
        )

    def test_close_code_applies_accrued_overdraft_interest_and_applies_overdraft_fees(
        self,
    ):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("-200")
        accrued_overdraft_receivable = Decimal("-10.78980")
        unarranged_overdraft_fee = Decimal("50")
        overdraft_fee_balance = Decimal("50")
        accrued_deposit_payable = Decimal("0.00")
        accrued_overdraft_receivable_fulfilment = accrued_overdraft_receivable.copy_abs().quantize(
            Decimal(".01")
        )
        overdraft_fee_balance_fulfilment = overdraft_fee_balance.copy_abs().quantize(Decimal(".01"))
        remainder = accrued_overdraft_receivable + accrued_overdraft_receivable_fulfilment

        balance_ts = self.account_balances(
            effective_time,
            accrued_overdraft_receivable=accrued_overdraft_receivable,
            default_committed=default_committed,
            accrued_overdraft_fee_receivable=-unarranged_overdraft_fee,
            accrued_deposit_payable=accrued_deposit_payable,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            interest_free_buffer=OptionalValue(50),
            overdraft_interest_rate=OptionalValue(Decimal("0.1555")),
            unarranged_overdraft_fee=OptionalValue(Decimal("50")),
            unarranged_overdraft_fee_cap=OptionalValue(80),
            arranged_overdraft_limit=OptionalValue(10),
            unarranged_overdraft_limit=OptionalValue(900),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
            overdraft_fee_receivable_account=OptionalValue(OVERDRAFT_FEE_RECEIVABLE_ACCOUNT),
        )

        self.run_function("close_code", mock_vault, effective_date=effective_time)

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=accrued_overdraft_receivable_fulfilment,
            client_transaction_id=f"APPLY_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            to_account_id="Main account",
            to_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "CLOSE_ACCOUNT",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=accrued_overdraft_receivable_fulfilment,
            client_transaction_id=f"APPLY_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Accrued interest applied.",
                "event": "CLOSE_ACCOUNT",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=overdraft_fee_balance_fulfilment,
            client_transaction_id=f"APPLY_FEES_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            to_account_id="Main account",
            to_account_address=ACCRUED_OVERDRAFT_FEE_RECEIVABLE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Overdraft fees applied.",
                "event": "CLOSE_ACCOUNT",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=overdraft_fee_balance_fulfilment,
            client_transaction_id=f"APPLY_FEES_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_FEE_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Overdraft fees applied.",
                "event": "CLOSE_ACCOUNT",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=abs(remainder),
            client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Zero out remainder after accrued interest applied.",
                "event": "CLOSE_ACCOUNT",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=abs(remainder),
            client_transaction_id=f"ACCRUE_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=INTEREST_RECEIVED_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Zero out remainder after accrued interest applied.",
                "event": "CLOSE_ACCOUNT",
            },
        )
        mock_vault.instruct_posting_batch.assert_any_call(
            client_batch_id="CLOSE_MOCK_HOOK",
            posting_instructions=[
                "APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_GL_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "APPLY_FEES_CUSTOMER_MOCK_HOOK_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "APPLY_FEES_GL_MOCK_HOOK_ACCRUED_OVERDRAFT_FEE_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
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
            "_get_next_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2020, 1, 1, 3, 4, 5),
            interest_application_frequency="monthly",
            interest_application_day=3,
        )

        expected_apply_accrued_interest_schedule = datetime(2020, 1, 3, 23, 59, 59)
        self.assertEqual(apply_accrued_interest_date, expected_apply_accrued_interest_schedule)

    def test_get_apply_accrued_interest_schedule_creates_schedule_next_month(self):
        mock_vault = self.create_mock(
            interest_application_day=3,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_next_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2020, 1, 5, 3, 4, 5),
            interest_application_frequency="monthly",
            interest_application_day=3,
        )

        expected_apply_accrued_interest_schedule = datetime(2020, 2, 3, 23, 59, 59)
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
            "_get_next_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2019, 2, 1, 3, 4, 5),
            interest_application_frequency="monthly",
            interest_application_day=31,
        )

        expected_apply_accrued_interest_schedule = datetime(2019, 2, 28, 23, 59, 59)
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
            "_get_next_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2019, 2, 1, 3, 4, 5),
            interest_application_frequency="quarterly",
            interest_application_day=31,
        )

        expected_apply_accrued_interest_schedule = datetime(2019, 5, 31, 23, 59, 59)
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
            "_get_next_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2019, 2, 1, 3, 4, 5),
            interest_application_frequency="annually",
            interest_application_day=31,
        )

        expected_apply_accrued_interest_schedule = datetime(2020, 2, 29, 23, 59, 59)
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
            "_get_next_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            effective_date=datetime(2020, 2, 1, 3, 4, 5),
            interest_application_frequency="monthly",
            interest_application_day=31,
        )

        expected_apply_accrued_interest_schedule = datetime(2020, 2, 29, 23, 59, 59)
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

    def test_close_code_reverses_accrued_interest(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("300")
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

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=accrued_deposit,
            client_transaction_id=f"REVERSE_ACCRUED_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=INTEREST_PAID_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Reverse ACCRUED_DEPOSIT interest due to account closure",
                "event": "CLOSE_ACCOUNT",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=accrued_deposit,
            client_transaction_id=f"REVERSE_ACCRUED_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_DEPOSIT_PAYABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Reverse ACCRUED_DEPOSIT interest due to account closure",
                "event": "CLOSE_ACCOUNT",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="CLOSE_MOCK_HOOK",
            posting_instructions=[
                "REVERSE_ACCRUED_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "REVERSE_ACCRUED_INTEREST_GL_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time,
        )

    def test_overdraft_day_buffer_less_than_7_days_balances(self):
        # Within buffer period and amount - no postings expected
        effective_time = datetime(2020, 2, 1)

        period_start = effective_time - relativedelta(days=6)
        balance_ts = self.account_balances(dt=period_start, default_committed=Decimal("-50"))
        account_tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "70", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "7", "B": "-1", "C": "-1"})

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            account_tier_names=account_tier_names,
            flags=["A"],
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            interest_free_buffer=OptionalValue(tiered_param_od_buffer_amount),
            overdraft_interest_rate=OptionalValue(Decimal("0.1555")),
            unarranged_overdraft_fee=OptionalValue(Decimal("10")),
            unarranged_overdraft_fee_cap=OptionalValue(Decimal("80")),
            arranged_overdraft_limit=OptionalValue(Decimal("200")),
            unarranged_overdraft_limit=OptionalValue(Decimal("10")),
            overdraft_interest_free_buffer_days=OptionalValue(tiered_param_od_buffer_period),
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
        account_tier_names = json_dumps(["A", "B", "C"])
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
            account_tier_names=account_tier_names,
            flags=["A"],
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            interest_free_buffer=OptionalValue(tiered_param_od_buffer_amount),
            overdraft_interest_rate=OptionalValue(Decimal("0.1555")),
            unarranged_overdraft_fee=OptionalValue(Decimal("10")),
            unarranged_overdraft_fee_cap=OptionalValue(Decimal("80")),
            arranged_overdraft_limit=OptionalValue(Decimal("200")),
            unarranged_overdraft_limit=OptionalValue(Decimal("10")),
            overdraft_interest_free_buffer_days=OptionalValue(tiered_param_od_buffer_period),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=INTEREST_RECEIVED_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_GL_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                f" on balance of {default_committed:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                f" on balance of {default_committed:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                "ACCRUE_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_GL_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
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
        account_tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "70", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "7", "B": "-1", "C": "-1"})

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            account_tier_names=account_tier_names,
            flags=["A"],
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            interest_free_buffer=OptionalValue(tiered_param_od_buffer_amount),
            overdraft_interest_rate=OptionalValue(Decimal("0.1555")),
            unarranged_overdraft_fee=OptionalValue(Decimal("10")),
            unarranged_overdraft_fee_cap=OptionalValue(Decimal("80")),
            arranged_overdraft_limit=OptionalValue(Decimal("500")),
            unarranged_overdraft_limit=OptionalValue(Decimal("1000")),
            overdraft_interest_free_buffer_days=OptionalValue(tiered_param_od_buffer_period),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=INTEREST_RECEIVED_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_GL_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                f" on balance of {default_committed + 70:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                f" on balance of {default_committed + 70:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                "ACCRUE_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_GL_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_overdraft_interest_accrual_with_deposit_single_tier(self):
        """
        Test the deposit interest doesn't accrue for overdraft balance
        for single tier deposit interest rates
        """
        effective_time = datetime(2020, 2, 1)
        default_committed = Decimal("-400")
        balance_ts = self.account_balances(
            effective_time - timedelta(seconds=1), default_committed=default_committed
        )
        overdraft_interest_rate = Decimal("0.1555")
        daily_rate = overdraft_interest_rate / 365
        daily_rate_percent = daily_rate * 100
        expected_interest_accrual = Decimal("0.14059")
        account_tier_names = json_dumps(["A", "B", "C"])
        tiered_param_od_buffer_amount = json_dumps({"A": "70", "B": "300", "C": "500"})
        tiered_param_od_buffer_period = json_dumps({"A": "7", "B": "-1", "C": "-1"})

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            account_tier_names=account_tier_names,
            flags=["A"],
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            interest_free_buffer=OptionalValue(tiered_param_od_buffer_amount),
            overdraft_interest_rate=OptionalValue(Decimal("0.1555")),
            unarranged_overdraft_fee=OptionalValue(Decimal("10")),
            unarranged_overdraft_fee_cap=OptionalValue(Decimal("80")),
            arranged_overdraft_limit=OptionalValue(Decimal("500")),
            unarranged_overdraft_limit=OptionalValue(Decimal("1000")),
            overdraft_interest_free_buffer_days=OptionalValue(tiered_param_od_buffer_period),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
            deposit_interest_rate_tiers=json_dumps({"tier1": "0.025"}),
            deposit_tier_ranges=json_dumps({"tier1": {"min": 0}}),
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=INTEREST_RECEIVED_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_GL_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                f" on balance of {default_committed + 70:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                f" on balance of {default_committed + 70:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                "ACCRUE_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_GL_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_overdraft_0_day_buffer_breach_overdraft_buffer_amount(self):
        # 0 Buffer days, so always charge against the full balance
        effective_time = datetime(2020, 2, 1)
        default_committed = Decimal("-400")
        account_tier_names = json_dumps(["A", "B", "C"])
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
            account_tier_names=account_tier_names,
            flags=["A"],
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            interest_free_buffer=OptionalValue(tiered_param_od_buffer_amount),
            overdraft_interest_rate=OptionalValue(Decimal("0.1555")),
            unarranged_overdraft_fee=OptionalValue(Decimal("10")),
            unarranged_overdraft_fee_cap=OptionalValue(Decimal("80")),
            arranged_overdraft_limit=OptionalValue(Decimal("500")),
            unarranged_overdraft_limit=OptionalValue(Decimal("1000")),
            overdraft_interest_free_buffer_days=OptionalValue(tiered_param_od_buffer_period),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=INTEREST_RECEIVED_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_GL_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                f" on balance of {default_committed:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                f" on balance of {default_committed:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                "ACCRUE_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_GL_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_multiple_flags_earliest_in_list_selected(self):
        # Flag A will mean 0 Buffer days, so always charge against the full balance
        effective_time = datetime(2020, 2, 1)
        default_committed = Decimal("-400")
        account_tier_names = json_dumps(["A", "B", "C"])
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
            account_tier_names=account_tier_names,
            # A should be selected
            flags=["A", "B", "C"],
            interest_accrual_days_in_year=UnionItemValue(key="365"),
            interest_free_buffer=OptionalValue(tiered_param_od_buffer_amount),
            overdraft_interest_rate=OptionalValue(Decimal("0.1555")),
            unarranged_overdraft_fee=OptionalValue(Decimal("10")),
            unarranged_overdraft_fee_cap=OptionalValue(Decimal("80")),
            arranged_overdraft_limit=OptionalValue(Decimal("500")),
            unarranged_overdraft_limit=OptionalValue(Decimal("1000")),
            overdraft_interest_free_buffer_days=OptionalValue(tiered_param_od_buffer_period),
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                f" on balance of {default_committed:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=expected_interest_accrual,
            denomination=DEFAULT_DENOMINATION,
            from_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=INTEREST_RECEIVED_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"ACCRUE_INTEREST_GL_{HOOK_EXECUTION_ID}"
            f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            instruction_details={
                "description": f"Daily interest accrued at {daily_rate_percent:0.5f}%"
                f" on balance of {default_committed:0.2f}.",
                "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
            },
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                "ACCRUE_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_GL_MOCK_HOOK_ACCRUED_OVERDRAFT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_close_code_reverses_accrued_negative_interest(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("300")
        accrued_deposit = Decimal("-10.78980")

        balance_ts = self.account_balances(
            effective_time,
            default_committed=default_committed,
            accrued_deposit_receivable=accrued_deposit,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            accrued_interest_payable_account=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            interest_paid_account=INTEREST_PAID_ACCOUNT,
            interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        )

        self.run_function("close_code", mock_vault, effective_date=effective_time)

        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=abs(accrued_deposit),
            client_transaction_id=f"REVERSE_ACCRUED_INTEREST_GL_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            denomination=DEFAULT_DENOMINATION,
            from_account_id=INTEREST_RECEIVED_ACCOUNT,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Reverse ACCRUED_DEPOSIT interest due to account closure",
                "event": "CLOSE_ACCOUNT",
            },
        )
        mock_vault.make_internal_transfer_instructions.assert_any_call(
            amount=abs(accrued_deposit),
            client_transaction_id=f"REVERSE_ACCRUED_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
            f"ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            to_account_id="Main account",
            to_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Reverse ACCRUED_DEPOSIT interest due to account closure",
                "event": "CLOSE_ACCOUNT",
            },
        )
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="CLOSE_MOCK_HOOK",
            posting_instructions=[
                "REVERSE_ACCRUED_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "REVERSE_ACCRUED_INTEREST_GL_MOCK_HOOK_ACCRUED_DEPOSIT_RECEIVABLE_COMMERCIAL"
                "_BANK_MONEY_GBP",
            ],
            effective_date=effective_time,
        )

    def test_posting_batch_with_supported_denom_and_sufficient_balance_is_accepted(
        self,
    ):

        main_denomination = "GBP"
        additional_denominations = json_dumps(["USD", "EUR", "CHF"])
        usd_posting = self.outbound_hard_settlement(
            amount="30",
            denomination="USD",
            value_timestamp=DEFAULT_DATE,
        )
        balance_ts = self.account_balances(
            balance_defs=[
                {"address": "default", "denomination": "USD", "net": "100"},
                {"address": "default", "denomination": "GBP", "net": "100"},
            ]
        )

        pib, client_transaction, _ = self.pib_and_cts_for_posting_instructions(
            DEFAULT_DATE, posting_instructions_groups=[[usd_posting]]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=main_denomination,
            additional_denominations=additional_denominations,
            client_transaction=client_transaction,
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[usd_posting])

        self.run_function("pre_posting_code", mock_vault, pib, DEFAULT_DATE)

    def test_check_posting_denominations_rejects_unsupported_denom(self):

        accepted_denominations = set(["GBP", "USD"])
        hkd_posting = self.outbound_hard_settlement(denomination="HKD", amount=1)
        usd_posting = self.outbound_hard_settlement(denomination="USD", amount=1)
        zar_posting = self.outbound_hard_settlement(denomination="ZAR", amount=1)
        gbp_posting = self.outbound_hard_settlement(denomination="GBP", amount=1)

        mock_vault = self.create_mock(balance_ts=self.account_balances())

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[hkd_posting, usd_posting, zar_posting, gbp_posting]
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "_check_posting_denominations", mock_vault, pib, accepted_denominations
            )

        self.assertEqual(e.exception.reason_code, RejectedReason.WRONG_DENOMINATION)

    def test_check_posting_denominations_returns_posting_denom(self):

        accepted_denominations = set(["GBP", "USD", "HKD", "ZAR"])
        expected_posting_denoms = set(["USD", "HKD"])

        mock_vault = self.create_mock(balance_ts=self.account_balances())

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(amount="1", denomination=denom)
                for denom in expected_posting_denoms
            ]
        )

        posting_denoms = self.run_function(
            "_check_posting_denominations", mock_vault, pib, accepted_denominations
        )

        self.assertEqual(posting_denoms, expected_posting_denoms)

    def test_posting_batch_with_single_denom_rejected_if_insufficient_balances(self):

        main_denomination = "GBP"
        additional_denominations = json_dumps(["USD"])
        usd_posting = self.outbound_hard_settlement(amount="20", denomination="USD")
        balance_ts = self.account_balances(
            balance_defs=[
                {"address": "default", "denomination": "USD", "net": "10"},
            ]
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
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
        balance_ts = self.account_balances(
            balance_defs=[
                {"address": "default", "denomination": "USD", "net": "10"},
                {"address": "default", "denomination": "GBP", "net": "30"},
            ]
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=main_denomination,
            additional_denominations=additional_denominations,
            unarranged_overdraft_limit=OptionalValue(Decimal("0.00")),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[usd_posting, gbp_posting])

        with self.assertRaises(Rejected) as e:
            self.run_function("pre_posting_code", mock_vault, pib, DEFAULT_DATE)

        expected_rejection_error = (
            "Postings total USD -20, which exceeds the available balance of USD 10."
        )

        self.assertEqual(str(e.exception), expected_rejection_error)
        self.assertEqual(e.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)

    def test_posting_batch_with_single_denom_debit_exceeding_available_accepted_due_to_credit(
        self,
    ):

        main_denomination = "GBP"
        additional_denominations = json_dumps(["USD"])
        usd_posting = self.outbound_auth(
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
        balance_ts = self.account_balances(
            balance_defs=[
                {"address": "default", "denomination": "USD", "net": "10"},
            ]
        )

        pib, client_transaction, _ = self.pib_and_cts_for_posting_instructions(
            DEFAULT_DATE, posting_instructions_groups=[[usd_posting], [usd_posting_2]]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=main_denomination,
            additional_denominations=additional_denominations,
            client_transaction=client_transaction,
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[usd_posting, usd_posting_2])

        self.run_function("pre_posting_code", mock_vault, pib, DEFAULT_DATE)

    def test_posting_batch_rejected_if_multiple_debits_below_zero(self):
        main_denomination = "GBP"
        additional_denominations = json_dumps(["USD"])
        usd_posting1 = self.outbound_auth(amount="100", denomination="USD")
        usd_posting2 = self.outbound_auth(amount="100", denomination="USD")
        balance_ts = self.account_balances(
            balance_defs=[
                {"address": "default", "denomination": "USD", "net": "150"},
            ]
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
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
        usd_posting = self.inbound_auth(
            amount="20",
            denomination="USD",
            value_timestamp=DEFAULT_DATE,
            client_transaction_id=CLIENT_TRANSACTION_ID_0,
            client_id=CLIENT_ID_0,
        )
        gbp_posting = self.outbound_auth(
            amount="20",
            denomination="GBP",
            value_timestamp=DEFAULT_DATE,
            client_transaction_id=CLIENT_TRANSACTION_ID_1,
            client_id=CLIENT_ID_1,
        )
        balance_ts = self.account_balances(
            balance_defs=[
                {"address": "default", "denomination": "USD", "net": "10"},
                {"address": "default", "denomination": "GBP", "net": "30"},
            ]
        )

        pib, client_transaction, _ = self.pib_and_cts_for_posting_instructions(
            DEFAULT_DATE, posting_instructions_groups=[[usd_posting], [gbp_posting]]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=main_denomination,
            additional_denominations=additional_denominations,
            unarranged_overdraft_limit=OptionalValue(Decimal("0.00")),
            client_transaction=client_transaction,
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[usd_posting, gbp_posting])

        self.run_function(
            "pre_posting_code",
            mock_vault,
            pib,
            DEFAULT_DATE,
        )

    def test_posting_batch_accepted_if_crediting_multiple_balances(self):
        main_denomination = "GBP"
        additional_denominations = json_dumps(["USD", "EUR"])
        usd_posting = self.inbound_auth(
            amount="20",
            denomination="USD",
            value_timestamp=DEFAULT_DATE,
            client_transaction_id=CLIENT_TRANSACTION_ID_0,
            client_id=CLIENT_ID_0,
        )
        eur_posting = self.inbound_hard_settlement(
            amount="20",
            denomination="EUR",
            value_timestamp=DEFAULT_DATE,
            client_transaction_id=CLIENT_TRANSACTION_ID_1,
            client_id=CLIENT_ID_1,
        )
        balance_ts = self.account_balances(
            balance_defs=[
                {"address": "default", "denomination": "USD", "net": "10"},
                {"address": "default", "denomination": "EUR", "net": "30"},
            ]
        )

        pib, client_transaction, _ = self.pib_and_cts_for_posting_instructions(
            DEFAULT_DATE, posting_instructions_groups=[[usd_posting], [eur_posting]]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=main_denomination,
            additional_denominations=additional_denominations,
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
            default_committed=Decimal(10), default_pending_out=Decimal(-10)
        )
        expected_available_balance = Decimal("0")
        available_balance = self.run_function(
            "_get_outgoing_available_balance",
            Mock(),
            balances=balance_ts[0][1],
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(expected_available_balance, available_balance)

    def test_available_balance_not_affected_by_pending_in_balances(self):
        balance_ts = self.account_balances(
            default_committed=Decimal(10), default_pending_in=Decimal(10)
        )
        expected_available_balance = Decimal("10")
        available_balance = self.run_function(
            "_get_outgoing_available_balance",
            Mock(),
            balances=balance_ts[0][1],
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(expected_available_balance, available_balance)

    def test_dormant_account_prevents_external_debits(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("2000")

        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.outbound_hard_settlement(
                    client_transaction_id=client_transaction_id_1,
                    client_id=client_id_1,
                    denomination=DEFAULT_DENOMINATION,
                    amount=1000,
                    instruction_details={"transaction_code": "6011"},
                    value_timestamp=effective_time,
                )
            ],
        )
        client_transaction = {
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=test_postings
            )
        }

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transaction,
            denomination=DEFAULT_DENOMINATION,
            unarranged_overdraft_limit=OptionalValue(Decimal("1000")),
            daily_atm_withdrawal_limit=OptionalValue(Decimal("1000")),
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            flags=[DORMANCY_FLAG],
        )

        with self.assertRaises(Rejected) as e:
            self.run_function("pre_posting_code", mock_vault, test_postings, effective_time)

        self.assertEqual(
            str(e.exception),
            'Account flagged "Dormant" does not accept external transactions.',
        )
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)

    def test_dormant_account_does_not_charge_monthly_maintenance_fee(self):
        mock_vault = self._maintenance_fee_setup_and_run(
            event_type="APPLY_MONTHLY_FEES",
            monthly_fee=Decimal("10"),
            flags=[DORMANCY_FLAG],
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_dormant_account_does_not_charge_annual_maintenance_fee(self):
        mock_vault = self._maintenance_fee_setup_and_run(
            event_type="APPLY_ANNUAL_FEES",
            annual_fee=Decimal("10"),
            flags=[DORMANCY_FLAG],
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_dormant_account_does_not_charge_minimum_balance_fee(self):
        effective_time = datetime(2020, 3, 15)
        expected_minimum_balance_fee = Decimal("100")

        period_start = effective_time - relativedelta(months=1)

        balance_ts = self.account_balances(dt=period_start, default_committed=Decimal("0"))

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            maintenance_fee_monthly=Decimal("0"),
            account_inactivity_fee=Decimal("0"),
            account_tier_names=json_dumps(["X", "Y", "Z"]),
            minimum_balance_threshold=json_dumps({"X": "25", "Y": "50", "Z": "100"}),
            minimum_balance_fee=expected_minimum_balance_fee,
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

    def test_check_transaction_limits(self):

        test_cases = [
            {
                "description": "toggle minimum withdrawal rejects insufficient amount",
                "test_input": {
                    "withdrawal_balance_delta": -Decimal("100"),
                    "deposit_balance_delta": Decimal("0.1"),
                    "minimum_withdrawal": Decimal("500"),
                    "minimum_deposit": None,
                },
                "expected_rejection": "less than the minimum withdrawal amount",
            },
            {
                "description": "toggle minimum withdrawal accepts sufficient amount",
                "test_input": {
                    "withdrawal_balance_delta": -Decimal("500"),
                    "deposit_balance_delta": Decimal("0.1"),
                    "minimum_withdrawal": Decimal("500"),
                    "minimum_deposit": None,
                },
            },
            {
                "description": "toggle minimum deposit rejects insufficient amount",
                "test_input": {
                    "withdrawal_balance_delta": -Decimal("0.1"),
                    "deposit_balance_delta": Decimal("100"),
                    "minimum_withdrawal": None,
                    "minimum_deposit": Decimal("500"),
                },
                "expected_rejection": "less than the minimum deposit amount",
            },
            {
                "description": "toggle minimum deposit accepts sufficient amount",
                "test_input": {
                    "withdrawal_balance_delta": -Decimal("0.1"),
                    "deposit_balance_delta": Decimal("500"),
                    "minimum_withdrawal": None,
                    "minimum_deposit": Decimal("500"),
                },
            },
            {
                "description": "toggle both deposit and withdrawal off throws no exception",
                "test_input": {
                    "withdrawal_balance_delta": -Decimal("0.1"),
                    "deposit_balance_delta": Decimal("0.1"),
                    "minimum_withdrawal": None,
                    "minimum_deposit": None,
                },
            },
            {
                "description": "toggle both deposit and withdrawal on with insufficient deposit",
                "test_input": {
                    "withdrawal_balance_delta": -Decimal("110"),
                    "deposit_balance_delta": Decimal("0.1"),
                    "minimum_withdrawal": Decimal("100"),
                    "minimum_deposit": Decimal("100"),
                },
                "expected_rejection": "less than the minimum deposit amount",
            },
            {
                "description": "toggle both deposit and withdrawal on with insufficient withdrawal",
                "test_input": {
                    "withdrawal_balance_delta": -Decimal("0.1"),
                    "deposit_balance_delta": Decimal("110"),
                    "minimum_withdrawal": Decimal("100"),
                    "minimum_deposit": Decimal("100"),
                },
                "expected_rejection": "less than the minimum deposit withdrawal",
            },
            {
                "description": "toggle both on with insufficient withdrawal and deposit",
                "test_input": {
                    "withdrawal_balance_delta": -Decimal("0.1"),
                    "deposit_balance_delta": Decimal("0.1"),
                    "minimum_withdrawal": Decimal("100"),
                    "minimum_deposit": Decimal("100"),
                },
                "expected_rejection": "less than the minimum withdrawal amount",
            },
        ]
        mock_vault = self.create_mock()

        for test_case in test_cases:

            if "expected_rejection" in test_case:
                with self.assertRaises(Rejected) as e:
                    self.run_function(
                        "_check_transaction_limits",
                        mock_vault,
                        "GBP",
                        **test_case["test_input"],
                    )

                    self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)
                    self.assertIn(test_case["expected_rejection"], str(e.exception))
            else:
                try:
                    self.run_function(
                        "_check_transaction_limits",
                        mock_vault,
                        "GBP",
                        **test_case["test_input"],
                    )
                except Rejected:
                    self.fail("Unexpected Rejected exception")

    def test_dormant_account_charges_inactivity_fee(self):
        effective_time = datetime(2020, 3, 15)
        expected_inactivity_fee = Decimal("100")

        period_start = effective_time - relativedelta(months=1)

        balance_ts = self.account_balances(dt=period_start, default_committed=Decimal("0"))

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            maintenance_fee_monthly=Decimal("10"),
            account_inactivity_fee=expected_inactivity_fee,
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
            client_transaction_id=f"APPLY_MONTHLY_FEES_INACTIVITY_{HOOK_EXECUTION_ID}"
            f"_{DEFAULT_DENOMINATION}_INTERNAL",
            instruction_details={
                "description": "Account inactivity fee",
                "event": "APPLY_MONTHLY_FEES",
            },
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_MONTHLY_FEES_MOCK_HOOK",
            posting_instructions=[
                "APPLY_MONTHLY_FEES_INACTIVITY_MOCK_HOOK_GBP_INTERNAL",
            ],
            effective_date=effective_time,
        )

    def test_are_overdraft_facility_parameters_set(self):
        test_cases = [
            {
                "description": "All overdraft parameters are omitted",
                "input": {
                    "unarranged_overdraft_limit": OptionalValue(is_set=False),
                    "overdraft_fee_income_account": OptionalValue(is_set=False),
                    "overdraft_fee_receivable_account": OptionalValue(is_set=False),
                    "arranged_overdraft_limit": OptionalValue(is_set=False),
                    "unarranged_overdraft_fee": OptionalValue(is_set=False),
                    "unarranged_overdraft_fee_cap": OptionalValue(is_set=False),
                    "interest_free_buffer": OptionalValue(is_set=False),
                    "overdraft_interest_free_buffer_days": OptionalValue(is_set=False),
                    "overdraft_interest_rate": OptionalValue(is_set=False),
                },
                "expected_result": False,
            },
            {
                "description": "Some of the overdraft parameters are omitted",
                "input": {
                    "unarranged_overdraft_limit": OptionalValue("100", is_set=True),
                    "overdraft_fee_income_account": OptionalValue(is_set=False),
                    "overdraft_fee_receivable_account": OptionalValue(is_set=False),
                    "arranged_overdraft_limit": OptionalValue(is_set=False),
                    "unarranged_overdraft_fee": OptionalValue(is_set=False),
                    "unarranged_overdraft_fee_cap": OptionalValue(is_set=False),
                    "interest_free_buffer": OptionalValue(is_set=False),
                    "overdraft_interest_free_buffer_days": OptionalValue(is_set=False),
                    "overdraft_interest_rate": OptionalValue(is_set=False),
                },
                "expected_result": False,
            },
            {
                "description": "None of the overdraft parameters are omitted",
                "input": {
                    "unarranged_overdraft_limit": OptionalValue("100", is_set=True),
                    "overdraft_fee_income_account": OptionalValue("100", is_set=True),
                    "overdraft_fee_receivable_account": OptionalValue("100", is_set=True),
                    "arranged_overdraft_limit": OptionalValue("100", is_set=True),
                    "unarranged_overdraft_fee": OptionalValue("100", is_set=True),
                    "unarranged_overdraft_fee_cap": OptionalValue("100", is_set=True),
                    "interest_free_buffer": OptionalValue("100", is_set=True),
                    "overdraft_interest_free_buffer_days": OptionalValue("100", is_set=True),
                    "overdraft_interest_rate": OptionalValue("100", is_set=True),
                },
                "expected_result": True,
            },
        ]

        for test_case in test_cases:

            mock_vault = self.create_mock(**test_case["input"])

            result = self.run_function(
                "_are_overdraft_facility_parameters_set",
                mock_vault,
                mock_vault,
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_scheduled_code_does_not_accrue_overdraft_interest_or_fees_if_overdraft_facility_false(
        self,
    ):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("-100")
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            unarranged_overdraft_limit=OptionalValue(is_set=False),
            overdraft_fee_income_account=OptionalValue(is_set=False),
            overdraft_fee_receivable_account=OptionalValue(is_set=False),
            arranged_overdraft_limit=OptionalValue(is_set=False),
            unarranged_overdraft_fee=OptionalValue(is_set=False),
            unarranged_overdraft_fee_cap=OptionalValue(is_set=False),
            interest_free_buffer=OptionalValue(is_set=False),
            overdraft_interest_free_buffer_days=OptionalValue(is_set=False),
            overdraft_interest_rate=OptionalValue(is_set=False),
            deposit_tier_ranges=DEPOSIT_TIER_RANGES,
            denomination=DEFAULT_DENOMINATION,
            interest_accrual_days_in_year=UnionItemValue(key="365"),
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_scheduled_code_accrues_deposit_interest_only_if_overdraft_facility_false(
        self,
    ):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("100")
        expected_accrual_amount = Decimal("0.00822")  # 100*0.3/365
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            unarranged_overdraft_limit=OptionalValue(is_set=False),
            overdraft_fee_income_account=OptionalValue(is_set=False),
            overdraft_fee_receivable_account=OptionalValue(is_set=False),
            arranged_overdraft_limit=OptionalValue(is_set=False),
            unarranged_overdraft_fee=OptionalValue(is_set=False),
            unarranged_overdraft_fee_cap=OptionalValue(is_set=False),
            interest_free_buffer=OptionalValue(is_set=False),
            overdraft_interest_free_buffer_days=OptionalValue(is_set=False),
            overdraft_interest_rate=OptionalValue(is_set=False),
            deposit_tier_ranges=DEPOSIT_TIER_RANGES,
            denomination=DEFAULT_DENOMINATION,
            interest_accrual_days_in_year=UnionItemValue(key="365"),
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            effective_date=effective_time,
        )

        expected_calls = [
            call(
                amount=expected_accrual_amount,
                denomination=DEFAULT_DENOMINATION,
                from_account_id="Main account",
                from_account_address=INTERNAL_CONTRA,
                to_account_id="Main account",
                to_account_address=ACCRUED_DEPOSIT_PAYABLE,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_TIER1_{HOOK_EXECUTION_ID}_"
                f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                instruction_details={
                    "description": "Daily interest accrued at 0.00822% on balance of 100.00.",
                    "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                },
            ),
            call(
                amount=expected_accrual_amount,
                denomination=DEFAULT_DENOMINATION,
                from_account_id=INTEREST_PAID_ACCOUNT,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"ACCRUE_INTEREST_GL_TIER1_{HOOK_EXECUTION_ID}_"
                f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                instruction_details={
                    "description": "Daily interest accrued at 0.00822% on balance of 100.00.",
                    "event": "ACCRUE_INTEREST_AND_DAILY_FEES",
                },
            ),
        ]
        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_calls)
        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="ACCRUE_INTEREST_AND_DAILY_FEES_MOCK_HOOK",
            posting_instructions=[
                "ACCRUE_INTEREST_CUSTOMER_TIER1_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_COMMERCIAL"
                "_BANK_MONEY_GBP",
                "ACCRUE_INTEREST_GL_TIER1_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_COMMERCIAL"
                "_BANK_MONEY_GBP",
            ],
            effective_date=effective_time - timedelta(microseconds=1),
        )

    def test_interest_applies_when_exceeding_available_balance(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("0.5")
        accrued_deposit_payable = Decimal("1.5")

        balance_ts = self.account_balances(
            effective_time,
            default_committed=default_committed,
            accrued_deposit_payable=accrued_deposit_payable,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            unarranged_overdraft_limit=OptionalValue(is_set=False),
            overdraft_fee_income_account=OptionalValue(is_set=False),
            overdraft_fee_receivable_account=OptionalValue(is_set=False),
            arranged_overdraft_limit=OptionalValue(is_set=False),
            unarranged_overdraft_fee=OptionalValue(is_set=False),
            unarranged_overdraft_fee_cap=OptionalValue(is_set=False),
            interest_free_buffer=OptionalValue(is_set=False),
            overdraft_interest_free_buffer_days=OptionalValue(is_set=False),
            overdraft_interest_rate=OptionalValue(is_set=False),
            deposit_tier_ranges=DEPOSIT_TIER_RANGES,
            denomination=DEFAULT_DENOMINATION,
            interest_accrual_days_in_year=UnionItemValue(key="365"),
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            effective_date=effective_time,
        )
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("1.50"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=ACCRUED_DEPOSIT_PAYABLE,
                    to_account_id="Main account",
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_CUSTOMER_{HOOK_EXECUTION_ID}_"
                    f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued interest applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                ),
                call(
                    amount=Decimal("1.50"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id="Main account",
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_INTEREST_GL_{HOOK_EXECUTION_ID}_"
                    f"ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Accrued interest applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                ),
            ]
        )

        mock_vault.instruct_posting_batch.assert_called_with(
            client_batch_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK",
            posting_instructions=[
                "APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_"
                "COMMERCIAL_BANK_MONEY_GBP",
                "APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_DEPOSIT_PAYABLE_" "COMMERCIAL_BANK_MONEY_GBP",
            ],
            effective_date=effective_time,
        )

    def test_check_balance_limits_rejects_postings_correctly(
        self,
    ):
        mock_vault = self.create_mock(
            unarranged_overdraft_limit=OptionalValue(Decimal("100"), is_set=True),
        )
        test_cases = [
            {
                "description": "Main denom and use_overdraft_facility",
                "denomination": "GBP",
                "use_overdraft_facility": True,
                "expected_str_rejection": "Posting exceeds unarranged_overdraft_limit.",
            },
            {
                "description": "Main denom not use_overdraft_facility",
                "denomination": "GBP",
                "use_overdraft_facility": False,
                "expected_str_rejection": "Postings total GBP -500, which exceeds the available "
                "balance of GBP 100.",
            },
            {
                "description": "Not denom use overdraft_facility",
                "denomination": "USD",
                "use_overdraft_facility": True,
                "expected_str_rejection": "Postings total GBP -500, which exceeds the available "
                "balance of GBP 100.",
            },
            {
                "description": "Not denom no overdraft_facility",
                "denomination": "USD",
                "use_overdraft_facility": False,
                "expected_str_rejection": "Postings total GBP -500, which exceeds the available "
                "balance of GBP 100.",
            },
        ]

        for test_case in test_cases:
            with self.assertRaises(Rejected) as e:
                self.run_function(
                    "_check_balance_limits",
                    mock_vault,
                    mock_vault,
                    posting_denomination="GBP",
                    main_denomination=test_case["denomination"],
                    withdrawal_balance_delta=-Decimal("500"),
                    available_balance=Decimal("100"),
                    use_overdraft_facility=test_case["use_overdraft_facility"],
                )

            self.assertEqual(
                str(e.exception),
                test_case["expected_str_rejection"],
                test_case["description"],
            )
            self.assertEqual(
                e.exception.reason_code,
                RejectedReason.INSUFFICIENT_FUNDS,
                test_case["description"],
            )

    def test_post_parameter_change_code_amends_schedule_to_last_day_of_month(self):
        mock_vault = self.create_mock(
            interest_application_day=28,
            denomination="GBP",
            creation_date=DEFAULT_DATE,
            deposit_interest_application_frequency=UnionItemValue(key="monthly"),
            unarranged_overdraft_limit=OptionalValue(is_set=False),
            overdraft_fee_income_account=OptionalValue(is_set=False),
            overdraft_fee_receivable_account=OptionalValue(is_set=False),
            arranged_overdraft_limit=OptionalValue(is_set=False),
            unarranged_overdraft_fee=OptionalValue(is_set=False),
            unarranged_overdraft_fee_cap=OptionalValue(is_set=False),
            interest_free_buffer=OptionalValue(is_set=False),
            overdraft_interest_free_buffer_days=OptionalValue(is_set=False),
            overdraft_interest_rate=OptionalValue(is_set=False),
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
            old_parameters={"interest_application_day": "31"},
            new_parameters={"interest_application_day": "28"},
            effective_date=datetime(2020, 2, 1, 1),
        )

        mock_vault.update_event_type.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST", schedule=expected_schedule
        )

    def test_post_parameter_change_code_amends_schedule_to_new_interest_application_day(
        self,
    ):
        mock_vault = self.create_mock(
            interest_application_day=12,
            denomination="GBP",
            creation_date=DEFAULT_DATE,
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
            old_parameters={"interest_application_day": "28"},
            new_parameters={"interest_application_day": "12"},
            effective_date=DEFAULT_DATE,
        )

        mock_vault.update_event_type.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            schedule=expected_schedule,
        )

    def test_post_parameter_change_code_with_undefined_new_interest_application_day(
        self,
    ):
        mock_vault = self.create_mock(
            interest_application_day=12,
            denomination="GBP",
            creation_date=DEFAULT_DATE,
        )

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters={"interest_application_day": "28"},
            new_parameters={"not_interest_application_day_parameter": "12"},
            effective_date=DEFAULT_DATE,
        )
        mock_vault.update_event_type.assert_not_called()

    def test_post_parameter_change_code_with_unchanged_interest_application_day(self):
        mock_vault = self.create_mock(
            denomination="GBP", interest_application_day=28, creation_date=DEFAULT_DATE
        )

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters={"interest_application_day": "28"},
            new_parameters={"interest_application_day": "28"},
            effective_date=DEFAULT_DATE,
        )
        mock_vault.update_event_type.assert_not_called()


class CASADailyTxnLimitTest(CASATest):
    def test_posting_over_transaction_type_daily_limit_rejected(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("2000")
        denomination = DEFAULT_DENOMINATION

        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"
        client_id_2 = "client_ID_2"
        client_transaction_id_2 = "CT_ID_2"

        client_transaction = {
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=[
                    self.outbound_hard_settlement(
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        denomination=DEFAULT_DENOMINATION,
                        amount=1000,
                        instruction_details={"transaction_code": "6011"},
                        value_timestamp=effective_time,
                    ),
                ],
            ),
            (client_id_2, client_transaction_id_2): self.mock_client_transaction(
                posting_instructions=[
                    self.outbound_hard_settlement(
                        client_transaction_id=client_transaction_id_2,
                        client_id=client_id_2,
                        denomination=DEFAULT_DENOMINATION,
                        amount=1000,
                        instruction_details={"transaction_code": "123"},
                        value_timestamp=effective_time,
                    ),
                ],
            ),
        }

        daily_atm_withdrawal_limit = OptionalValue(Decimal("100"))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transaction,
            denomination=DEFAULT_DENOMINATION,
            daily_atm_withdrawal_limit=daily_atm_withdrawal_limit,
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "_check_daily_limits",
                vault=mock_vault,
                vault_object=mock_vault,
                client_transactions=client_transaction,
                denomination=denomination,
                effective_date=effective_time,
            )
            expected_rejection_error = (
                "Transaction would cause the ATM"
                " daily withdrawal limit of %s %s to be exceeded."
                % (daily_atm_withdrawal_limit, denomination),
            )
            self.assertEqual(str(e.exception), expected_rejection_error)

    def test_credit_transaction_over_transaction_type_daily_limit_accepted(self):
        effective_time = datetime(2019, 1, 1, 1)
        default_committed = Decimal("2000")
        denomination = DEFAULT_DENOMINATION

        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        client_transaction = {
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=[
                    self.inbound_hard_settlement(
                        client_transaction_id=client_transaction_id_1,
                        client_id=client_id_1,
                        denomination=DEFAULT_DENOMINATION,
                        amount=1000,
                        instruction_details={"transaction_code": "6011"},
                        value_timestamp=effective_time,
                    )
                ],
            )
        }

        daily_atm_withdrawal_limit = OptionalValue(Decimal("100"))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transaction,
            denomination=DEFAULT_DENOMINATION,
            daily_atm_withdrawal_limit=daily_atm_withdrawal_limit,
        )

        self.run_function(
            "_check_daily_limits",
            vault=mock_vault,
            vault_object=mock_vault,
            client_transactions=client_transaction,
            denomination=denomination,
            effective_date=effective_time,
        )

    def test_postings_for_unknown_transaction_type_not_limited(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("20000")
        spend_amount = Decimal("10000")

        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        posting_instructions = [
            self.outbound_hard_settlement(
                client_transaction_id=client_transaction_id_1,
                client_id=client_id_1,
                denomination=DEFAULT_DENOMINATION,
                amount=spend_amount,
                instruction_details={"transaction_code": "1234"},
                value_timestamp=effective_time,
            )
        ]
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=posting_instructions
        )

        client_transaction = {
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=posting_instructions
            )
        }

        daily_atm_withdrawal_limit = OptionalValue(Decimal("100"))
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transaction,
            denomination=DEFAULT_DENOMINATION,
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            arranged_overdraft_limit=OptionalValue(Decimal("0")),
            unarranged_overdraft_limit=OptionalValue(Decimal("100")),
            daily_atm_withdrawal_limit=daily_atm_withdrawal_limit,
        )

        self.run_function("pre_posting_code", mock_vault, test_postings, effective_time)

    def test_postings_of_mixed_types_accepted(self):
        # PIB with posting at ATM limit and non-ATM posting under default balance is accepted
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("20000")
        daily_atm_withdrawal_limit = OptionalValue(Decimal("100"))
        not_atm_amount = Decimal("10000")
        atm_amount = daily_atm_withdrawal_limit.value

        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        client_id_2 = "client_ID_2"
        client_transaction_id_2 = "CT_ID_2"

        non_atm_posting = self.outbound_hard_settlement(
            client_transaction_id=client_transaction_id_1,
            client_id=client_id_1,
            denomination=DEFAULT_DENOMINATION,
            amount=not_atm_amount,
            instruction_details={"transaction_code": "1234"},
            value_timestamp=effective_time,
        )
        atm_posting = self.outbound_hard_settlement(
            client_transaction_id=client_transaction_id_2,
            client_id=client_id_2,
            denomination=DEFAULT_DENOMINATION,
            amount=atm_amount,
            instruction_details={"transaction_code": "6011"},
            value_timestamp=effective_time,
        )

        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[non_atm_posting, atm_posting]
        )

        client_transaction = {
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=[non_atm_posting]
            ),
            (client_id_2, client_transaction_id_2): self.mock_client_transaction(
                posting_instructions=[atm_posting]
            ),
        }

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transaction,
            denomination=DEFAULT_DENOMINATION,
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            arranged_overdraft_limit=OptionalValue(Decimal("0")),
            unarranged_overdraft_limit=OptionalValue(Decimal("100")),
            daily_atm_withdrawal_limit=daily_atm_withdrawal_limit,
        )

        self.run_function("pre_posting_code", mock_vault, test_postings, effective_time)

    def test_daily_limit_applied_to_pib_at_midnight(self):
        # a PIB with value_timestamp at midnight is considered as part of that day's total
        # and should be rejected if the amount exceeds the limit
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("20000")
        daily_atm_withdrawal_limit = OptionalValue(Decimal("100"))
        atm_amount = daily_atm_withdrawal_limit.value + 1

        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        atm_posting = self.outbound_hard_settlement(
            client_transaction_id=client_transaction_id_1,
            client_id=client_id_1,
            denomination=DEFAULT_DENOMINATION,
            amount=atm_amount,
            instruction_details={"transaction_code": "6011"},
            value_timestamp=effective_time,
        )

        test_postings = self.mock_posting_instruction_batch(posting_instructions=[atm_posting])

        client_transaction = {
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=[atm_posting]
            )
        }

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transaction,
            denomination=DEFAULT_DENOMINATION,
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            arranged_overdraft_limit=OptionalValue(Decimal("0")),
            unarranged_overdraft_limit=OptionalValue(Decimal("100")),
            daily_atm_withdrawal_limit=daily_atm_withdrawal_limit,
        )

        with self.assertRaises(Rejected) as e:
            self.run_function("pre_posting_code", mock_vault, test_postings, effective_time)
            expected_rejection_error = (
                "Transaction would cause the ATM"
                " daily withdrawal limit of 100 GBP to be exceeded."
            )
            self.assertEqual(str(e.exception), expected_rejection_error)

    def test_daily_limit_resets_at_midnight(self):
        # a PIB with value_timestamp before midnight is not considered as part of next day's total
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("20000")
        daily_atm_withdrawal_limit = OptionalValue(Decimal("100"))

        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        client_id_1 = "client_ID_1"
        client_transaction_id_1 = "CT_ID_1"

        client_id_2 = "client_ID_2"
        client_transaction_id_2 = "CT_ID_2"

        prev_day_posting = self.outbound_hard_settlement(
            client_transaction_id=client_transaction_id_1,
            client_id=client_id_1,
            denomination=DEFAULT_DENOMINATION,
            amount=51,
            instruction_details={"transaction_code": "6011"},
            value_timestamp=effective_time - timedelta(microseconds=1),
        )
        current_day_posting = self.outbound_hard_settlement(
            client_transaction_id=client_transaction_id_2,
            client_id=client_id_2,
            denomination=DEFAULT_DENOMINATION,
            amount=50,
            instruction_details={"transaction_code": "6011"},
            value_timestamp=effective_time,
        )

        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[prev_day_posting, current_day_posting]
        )

        client_transaction = {
            (client_id_1, client_transaction_id_1): self.mock_client_transaction(
                posting_instructions=[prev_day_posting]
            ),
            (client_id_2, client_transaction_id_2): self.mock_client_transaction(
                posting_instructions=[current_day_posting]
            ),
        }
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            client_transaction=client_transaction,
            denomination=DEFAULT_DENOMINATION,
            additional_denominations=ADDITIONAL_DENOMINATIONS,
            arranged_overdraft_limit=OptionalValue(Decimal("0")),
            unarranged_overdraft_limit=OptionalValue(Decimal("100")),
            daily_atm_withdrawal_limit=daily_atm_withdrawal_limit,
        )

        self.run_function("pre_posting_code", mock_vault, test_postings, effective_time)

    def test_daily_ATM_limit_change_limited_by_template_parameter(self):
        mock_vault = self.create_mock(
            account_tier_names=json_dumps(["Z"]),
            maximum_daily_atm_withdrawal_limit=OptionalValue(json_dumps({"Z": 25})),
        )
        shape = NumberShape(max_value=100)
        parameters = {"daily_atm_withdrawal_limit": OptionalShape(Parameter(shape=shape))}
        effective_date = datetime(2020, 2, 1, 3, 4, 5)
        parameters = self.run_function(
            "pre_parameter_change_code",
            mock_vault,
            parameters,
            effective_date,
        )
        self.assertEqual(parameters["daily_atm_withdrawal_limit"].shape.shape.max_value, 25)


class ExcessWithdrawalRejectionTest(CASATest):
    effective_date = datetime(2020, 9, 27)

    def _excess_withdrawal_test(
        self,
        transactions: Optional[List[Transaction]] = None,
        posting_instruction_groups: Optional[List[List[PostingInstruction]]] = None,
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

        balance_ts = self.account_balances(
            DEFAULT_DATE,
            default_committed=default_committed,
        )

        mock_vault = self.create_mock(
            creation_date=datetime(2020, 9, 23, 5, 6, 7),
            balance_ts=balance_ts,
            denomination="GBP",
            client_transaction=client_transactions,
            minimum_deposit=OptionalValue(Decimal(50)),
            maximum_balance=OptionalValue(Decimal(100000)),
            maximum_daily_deposit=OptionalValue(Decimal(1000)),
            maximum_daily_withdrawal=OptionalValue(Decimal(100)),
            minimum_withdrawal=OptionalValue(Decimal(10)),
            monthly_withdrawal_limit=OptionalValue(Decimal(withdrawal_limit)),
            reject_excess_withdrawals=OptionalValue(UnionItemValue(str(reject_excess_withdrawals))),
        )

        if expect_rejected:
            with self.assertRaises(Rejected) as e:
                self.run_function("pre_posting_code", mock_vault, pib, effective_date)

            expected_rejection_error = (
                f"Exceeding monthly allowed withdrawal number: {withdrawal_limit}"
            )
            self.assertEqual(str(e.exception), expected_rejection_error)
        else:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                effective_date,
            )

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
        transactions: Optional[List[Transaction]] = None,
        posting_instruction_groups: Optional[List[List[PostingInstruction]]] = None,
        withdrawal_limit: int = 1,
        effective_date: datetime = datetime(2020, 9, 27),
        reject_excess_withdrawals: bool = False,
    ):
        self._excess_withdrawal_test(
            effective_date=self.effective_date,
            posting_instruction_groups=[
                [
                    self.outbound_hard_settlement(
                        denomination=self.default_denom,
                        amount=Decimal(14),
                        client_transaction_id=INTERNAL_CLIENT_TRANSATION_ID_0,
                        client_id=CLIENT_ID_0,
                        value_timestamp=self.effective_date,
                    )
                ],
            ],
            withdrawal_limit=0,
            expect_rejected=False,
        )


class ExcessWithdrawalFeesTest(CASATest):

    effective_date = datetime(2020, 9, 27)

    def excess_withdrawal_fee_call(self, amount: str, limit: int):
        return call(
            amount=Decimal(amount),
            client_transaction_id=f"{INTERNAL_POSTING}_" "APPLY_EXCESS_WITHDRAWAL_FEE_MOCK_HOOK",
            denomination=DEFAULT_DENOMINATION,
            from_account_id="Main account",
            from_account_address="DEFAULT",
            to_account_id=EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT.value,
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
        transactions: Optional[List[Transaction]] = None,
        posting_instruction_groups: Optional[List[List[PostingInstruction]]] = None,
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
            denomination="GBP",
            autosave_savings_account=OptionalValue(is_set=False),
            transaction_code_to_type_map=OptionalValue(is_set=False),
            client_transaction=client_transactions,
            excess_withdrawal_fee=OptionalValue(Decimal("10.00")),
            reject_excess_withdrawals=OptionalValue(UnionItemValue(str(reject_excess_withdrawals))),
            monthly_withdrawal_limit=OptionalValue(Decimal(withdrawal_limit)),
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
        transactions: Optional[List[Transaction]] = None,
        posting_instruction_groups: Optional[List[List[PostingInstruction]]] = None,
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
                        client_transaction_id=INTERNAL_CLIENT_TRANSATION_ID_0,
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


class ExcessWithdrawalNotificationTest(CASATest):

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
            workflow="CASA_TRANSACTION_LIMIT_WARNING",
            context={
                "account_id": "Main account",
                "limit_type": "Monthly Withdrawal Limit",
                "limit": str(limit),
                "value": str(amount),
                "message": limit_message,
            },
        )

    def _excess_withdrawal_test(
        self,
        transactions: Optional[List[Transaction]] = None,
        posting_instruction_groups: Optional[List[List[PostingInstruction]]] = None,
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
            denomination="GBP",
            autosave_savings_account=OptionalValue(is_set=False),
            transaction_code_to_type_map=OptionalValue(is_set=False),
            client_transaction=client_transactions,
            excess_withdrawal_fee=OptionalValue(Decimal("10.00")),
            reject_excess_withdrawals=OptionalValue(UnionItemValue(str(reject_excess_withdrawals))),
            monthly_withdrawal_limit=OptionalValue(Decimal(withdrawal_limit)),
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
        transactions: Optional[List[Transaction]] = None,
        posting_instruction_groups: Optional[List[List[PostingInstruction]]] = None,
        withdrawal_limit: int = 1,
        expected_workflows: Optional[Any] = None,
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

        if expected_workflows:
            mock_vault.start_workflow.assert_has_calls([expected_workflows])
        else:
            mock_vault.start_workflow.assert_not_called()

    def test_notification_sent_when_withdrawal_limit_reached_with_excess_withdrawals_rejected(
        self,
    ):

        effective_date = datetime(2020, 9, 27)

        self._excess_withdrawal_notification_test(
            transactions=[Withdrawal(effective_date=effective_date, amount="14")],
            reject_excess_withdrawals=True,
            withdrawal_limit=1,
            effective_date=effective_date,
            expected_workflows=self.excess_withdrawal_notification_call(
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
            expected_workflows=self.excess_withdrawal_notification_call(
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
            expected_workflows=None,
        )


class AutosaveTest(CASATest):
    def test_autosave_simple(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("1000")
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        scenarios = [
            {
                "name": "Round up to nearest 1.00",
                "posting_amount": "5.6",
                "rounding_amount": "1",
                "expected_savings_amount": "0.4",
            },
            {
                "name": "Round up to nearest 10.00",
                "posting_amount": "5.6",
                "rounding_amount": "10",
                "expected_savings_amount": "4.4",
            },
            {
                "name": "Round up to nearest 0.50",
                "posting_amount": "23232.14",
                "rounding_amount": "0.5",
                "expected_savings_amount": ".36",
            },
            {
                "name": "Round up to nearest 0.80",
                "posting_amount": "1.14",
                "rounding_amount": "0.8",
                "expected_savings_amount": ".46",
            },
            {
                "name": "Round up - 3 decimals",
                "posting_amount": "500.301",
                "rounding_amount": "1",
                "expected_savings_amount": ".699",
            },
            {
                "name": "No rounding - 0.5",
                "posting_amount": "1.5",
                "rounding_amount": "0.5",
                "expected_savings_amount": "0",
            },
            {
                "name": "No rounding - 1.0",
                "posting_amount": "3",
                "rounding_amount": "1",
                "expected_savings_amount": "0",
            },
        ]
        for scenario in scenarios:
            posting_instructions = [
                self.outbound_hard_settlement(
                    denomination=DEFAULT_DENOMINATION,
                    amount=Decimal(scenario["posting_amount"]),
                    value_timestamp=effective_time,
                )
            ]

            (
                pib,
                client_transaction,
                client_transaction_ex,
            ) = self.pib_and_cts_for_posting_instructions(
                effective_time, posting_instructions_groups=[posting_instructions]
            )

            mock_vault = self.create_mock(
                balance_ts=balance_ts,
                minimum_balance_fee=Decimal("0"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction=client_transaction,
                client_transaction_excluding_proposed=client_transaction_ex,
            )

            result = self.run_function(
                "_get_total_savings_amount",
                mock_vault,
                mock_vault,
                pib,
                DEFAULT_DENOMINATION,
                Decimal(scenario["rounding_amount"]),
            )
            self.assertEqual(Decimal(scenario["expected_savings_amount"]), result, scenario["name"])

    def test_autosave_not_enough_balance(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("0.5")
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)
        autosave_savings_account = "12345678"
        autosave_rounding_amount = Decimal("1.00")

        posting_instructions = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("10.30"),
                value_timestamp=effective_time,
            )
        ]

        pib, client_transaction, client_transaction_ex = self.pib_and_cts_for_posting_instructions(
            effective_time, posting_instructions_groups=[posting_instructions]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            minimum_balance_fee=Decimal("0"),
            denomination=DEFAULT_DENOMINATION,
            client_transaction=client_transaction,
            client_transaction_excluding_proposed=client_transaction_ex,
        )

        result = self.run_function(
            "_autosave_from_purchase",
            mock_vault,
            mock_vault,
            pib,
            DEFAULT_DENOMINATION,
            autosave_savings_account,
            autosave_rounding_amount,
        )
        self.assertEqual([], result)

    def test_no_autosave_applied_on_auth_postings(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("1000")
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        posting_instructions = [
            self.outbound_auth(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("5.6"),
                value_timestamp=effective_time - timedelta(hours=1),
            ),
        ]

        pib, client_transaction, client_transaction_ex = self.pib_and_cts_for_posting_instructions(
            effective_time, posting_instructions_groups=[posting_instructions]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            minimum_balance_fee=Decimal("0"),
            denomination=DEFAULT_DENOMINATION,
            client_transaction=client_transaction,
            client_transaction_excluding_proposed=client_transaction_ex,
        )

        result = self.run_function(
            "_get_total_savings_amount",
            mock_vault,
            mock_vault,
            pib,
            DEFAULT_DENOMINATION,
            Decimal("1"),
        )
        self.assertEqual(Decimal("0"), result)

    def test_no_autosave_applied_on_auth_and_autosaves_on_settlement(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("1000")
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        posting_instructions = [
            self.outbound_auth(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("5.6"),
                value_timestamp=effective_time - timedelta(hours=1),
            ),
            self.settle_outbound_auth(
                denomination=DEFAULT_DENOMINATION,
                unsettled_amount=Decimal("5.6"),
                value_timestamp=effective_time,
                final=True,
            ),
        ]

        pib, client_transaction, client_transaction_ex = self.pib_and_cts_for_posting_instructions(
            effective_time, posting_instructions_groups=[posting_instructions]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            minimum_balance_fee=Decimal("0"),
            denomination=DEFAULT_DENOMINATION,
            client_transaction=client_transaction,
            client_transaction_excluding_proposed=client_transaction_ex,
        )

        result = self.run_function(
            "_get_total_savings_amount",
            mock_vault,
            mock_vault,
            pib,
            DEFAULT_DENOMINATION,
            Decimal("1"),
        )
        self.assertEqual(Decimal("0.4"), result)

    def test_no_autosave_applied_on_auth_adjustment_postings(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("1000")
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        posting_instructions = [
            self.outbound_auth(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("5.6"),
                value_timestamp=effective_time - timedelta(hours=2),
            ),
            self.outbound_auth_adjust(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("5"),
                value_timestamp=effective_time - timedelta(hours=1),
            ),
        ]

        pib, client_transaction, client_transaction_ex = self.pib_and_cts_for_posting_instructions(
            effective_time, posting_instructions_groups=[posting_instructions]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            minimum_balance_fee=Decimal("0"),
            denomination=DEFAULT_DENOMINATION,
            client_transaction=client_transaction,
            client_transaction_excluding_proposed=client_transaction_ex,
        )

        result = self.run_function(
            "_get_total_savings_amount",
            mock_vault,
            mock_vault,
            pib,
            DEFAULT_DENOMINATION,
            Decimal("1"),
        )
        self.assertEqual(Decimal("0"), result)

    def test_no_autosave_applied_on_release_postings(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("1000")
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        posting_instructions = [
            self.outbound_auth(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("5.6"),
                value_timestamp=effective_time - timedelta(hours=1),
            ),
            self.release_outbound_auth(
                denomination=DEFAULT_DENOMINATION,
                unsettled_amount=Decimal("5.6"),
                value_timestamp=effective_time,
                final=True,
            ),
        ]

        pib, client_transaction, client_transaction_ex = self.pib_and_cts_for_posting_instructions(
            effective_time, posting_instructions_groups=[posting_instructions]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            minimum_balance_fee=Decimal("0"),
            denomination=DEFAULT_DENOMINATION,
            client_transaction=client_transaction,
            client_transaction_excluding_proposed=client_transaction_ex,
        )

        result = self.run_function(
            "_get_total_savings_amount",
            mock_vault,
            mock_vault,
            pib,
            DEFAULT_DENOMINATION,
            Decimal("1"),
        )
        self.assertEqual(Decimal("0"), result)

    def test_no_autosave_applied_on_non_purchase_postings(self):
        effective_time = datetime(2019, 1, 1)
        default_committed = Decimal("1000")
        balance_ts = self.account_balances(effective_time, default_committed=default_committed)

        posting_instructions = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("100.6"),
                value_timestamp=effective_time,
                instruction_details={"transaction_code": "6011"},  # ATM withdrawal
            ),
        ]

        pib, client_transaction, client_transaction_ex = self.pib_and_cts_for_posting_instructions(
            effective_time, posting_instructions_groups=[posting_instructions]
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            minimum_balance_fee=Decimal("0"),
            denomination=DEFAULT_DENOMINATION,
            client_transaction=client_transaction,
            client_transaction_excluding_proposed=client_transaction_ex,
        )

        result = self.run_function(
            "_get_total_savings_amount",
            mock_vault,
            mock_vault,
            pib,
            DEFAULT_DENOMINATION,
            Decimal("1"),
        )
        self.assertEqual(Decimal("0"), result)

    def test_account_tier_derived_parameter_with_middle_flag(self):
        effective_date = DEFAULT_DATE

        mock_vault = self.create_mock(account_tier_names=json_dumps(["X", "Y", "Z"]), flags=["Y"])

        result = self.run_function(
            "derived_parameters",
            mock_vault,
            effective_date,
        )

        self.assertEqual(result, {"account_tier": "Y"})

    def test_account_tier_derived_parameter_with_first_flag(self):
        effective_date = DEFAULT_DATE

        mock_vault = self.create_mock(account_tier_names=json_dumps(["X", "Y", "Z"]), flags=["X"])

        result = self.run_function(
            "derived_parameters",
            mock_vault,
            effective_date,
        )

        self.assertEqual(result, {"account_tier": "X"})

    def test_account_tier_derived_parameter_with_random_flag(self):
        effective_date = DEFAULT_DATE

        mock_vault = self.create_mock(account_tier_names=json_dumps(["X", "Y", "Z"]), flags=["foo"])

        result = self.run_function(
            "derived_parameters",
            mock_vault,
            effective_date,
        )

        self.assertEqual(result, {"account_tier": "Z"})

    def test_account_tier_derived_parameter_with_no_flag(self):
        effective_date = DEFAULT_DATE

        mock_vault = self.create_mock(
            account_tier_names=json_dumps(["X", "Y", "Z"]),
        )

        result = self.run_function(
            "derived_parameters",
            mock_vault,
            effective_date,
        )

        self.assertEqual(result, {"account_tier": "Z"})

    def test_are_autosave_parameters_set(self):
        test_cases = [
            {
                "description": "All autosave parameters are omitted",
                "autosave_rounding_amount": OptionalValue(is_set=False),
                "autosave_savings_account": OptionalValue(is_set=False),
                "expected_result": False,
            },
            {
                "description": "Some autosave parameters are omitted",
                "autosave_rounding_amount": OptionalValue(is_set=False),
                "autosave_savings_account": OptionalValue(is_set=True),
                "expected_result": False,
            },
            {
                "description": "All autosave parameters are set",
                "autosave_rounding_amount": OptionalValue(is_set=True),
                "autosave_savings_account": OptionalValue(is_set=True),
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock(
                autosave_rounding_amount=test_case["autosave_rounding_amount"],
                autosave_savings_account=test_case["autosave_savings_account"],
            )

            result = self.run_function("_are_autosave_parameters_set", mock_vault, mock_vault)

            self.assertEqual(result, test_case["expected_result"], test_case["description"])
