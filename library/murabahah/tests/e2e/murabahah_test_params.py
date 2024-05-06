# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
from json import dumps

# constants for account names
ACCRUED_PROFIT_PAYABLE_ACCOUNT = "ACCRUED_PROFIT_PAYABLE"
PROFIT_PAID_ACCOUNT = "PROFIT_PAID"
EARLY_CLOSURE_FEE_INCOME_ACCOUNT = "EARLY_CLOSURE_FEE_INCOME"
PAYMENT_TYPE_FEE_INCOME_ACCOUNT = "PAYMENT_TYPE_FEE_INCOME"

# required internal accounts dictionary
internal_accounts_tside = {
    "TSIDE_ASSET": [
        PROFIT_PAID_ACCOUNT,
    ],
    "TSIDE_LIABILITY": [
        ACCRUED_PROFIT_PAYABLE_ACCOUNT,
        EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
        PAYMENT_TYPE_FEE_INCOME_ACCOUNT,
    ],
}

# constants used for account addresses
INTERNAL_CONTRA = "INTERNAL_CONTRA"

# required constants for product schedules tests
SCHEDULE_TAGS_DIR = "library/murabahah/account_schedule_tags/tests/"
PAUSED_SCHEDULE_TAG = (
    "library/common/tests/e2e/account_schedule_tags/"
    "common_paused_account_schedule_tag.resource.yaml"
)

# By default all schedules are paused
DEFAULT_TAGS = {
    "MURABAHAH_ACCRUE_PROFIT_AST": PAUSED_SCHEDULE_TAG,
    "MURABAHAH_APPLY_ACCRUED_PROFIT_AST": PAUSED_SCHEDULE_TAG,
}


# MURABAHAH CONSTANTS
BALANCE_TIER_RANGES = dumps(
    {
        "tier1": {"min": "0"},
        "tier2": {"min": "5000.00"},
        "tier3": {"min": "15000.00"},
    }
)

# tiered profit rates
TIERED_PROFIT_RATES = dumps(
    {
        "MURABAHAH_TIER_UPPER": {
            "tier1": "0.50",
            "tier2": "0.50",
            "tier3": "0.50",
        },
        "MURABAHAH_TIER_MIDDLE": {
            "tier1": "0.50",
            "tier2": "0.50",
            "tier3": "0.50",
        },
        "MURABAHAH_TIER_LOWER": {
            "tier1": "0.50",
            "tier2": "0.50",
            "tier3": "0.50",
        },
    }
)

# tiered min balance threshold used for both murabahah accounts
TIERED_MIN_BALANCE_THRESHOLD = dumps(
    {
        "MURABAHAH_TIER_UPPER": "25",
        "MURABAHAH_TIER_MIDDLE": "75",
        "MURABAHAH_TIER_LOWER": "100",
    }
)

# account tier names used for both murabahah accounts
ACCOUNT_TIER_NAMES = dumps(
    [
        "MURABAHAH_TIER_UPPER",
        "MURABAHAH_TIER_MIDDLE",
        "MURABAHAH_TIER_LOWER",
    ]
)

# payment type limit used for both murabahah accounts
MAXIMUM_DAILY_PAYMENT_TYPE_WITHDRAWAL = dumps(
    {
        "DUITNOW_PROXY": "50000",
        "DUITNOWQR": "50000",
        "JOMPAY": "50000",
        "ONUS": "50000",
        "ATM_ARBM": "5000",
        "ATM_MEPS": "5000",
        "ATM_VISA": "5000",
        "ATM_IBFT": "30000",
        "DEBIT_POS": "100000",
    }
)

# payment type limit per transaction used for both murabahah accounts
MAXIMUM_PAYMENT_TYPE_WITHDRAWAL = dumps(
    {
        "DEBIT_PAYWAVE": "250",
    }
)

# payment type limit used for both murabahah accounts
MAXIMUM_DAILY_PAYMENT_CATEGORY_WITHDRAWAL = dumps(
    {
        "DUITNOW": "50000",
    }
)

# payment type flat fees used for both murabahah accounts
PAYMENT_TYPE_FLAT_FEES = dumps(
    {
        "ATM_MEPS": "1",
        "ATM_IBFT": "5",
    }
)

# payment type fees used for both murabahah accounts
PAYMENT_TYPE_THRESHOLD_FEES = dumps(
    {
        "DUITNOW_PROXY": {"fee": "0.50", "threshold": "5000"},
        "ATM_IBFT": {"fee": "0.15", "threshold": "5000"},
    }
)

# payment type limit fees used for both murabahah accounts
MAX_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT = dumps(
    {
        "ATM_ARBM": {"fee": "0.50", "limit": "8"},
    }
)

# murabahah template parameters
murabahah_template_params = {
    "account_tier_names": ACCOUNT_TIER_NAMES,
    "denomination": "MYR",
    "days_in_year": "365",
    "profit_accrual_hour": "0",
    "profit_accrual_minute": "0",
    "profit_accrual_second": "0",
    "profit_application_hour": "0",
    "profit_application_minute": "0",
    "profit_application_second": "0",
    "profit_application_frequency": "monthly",
    "minimum_deposit": "1",
    "minimum_initial_deposit": "0",
    "maximum_balance": "10000",
    "maximum_deposit": "10000",
    "maximum_withdrawal": "10000",
    "maximum_payment_type_withdrawal": MAXIMUM_PAYMENT_TYPE_WITHDRAWAL,
    "maximum_daily_deposit": "1000",
    "maximum_daily_withdrawal": "100",
    "maximum_daily_payment_category_withdrawal": MAXIMUM_DAILY_PAYMENT_CATEGORY_WITHDRAWAL,
    "maximum_daily_payment_type_withdrawal": MAXIMUM_DAILY_PAYMENT_TYPE_WITHDRAWAL,
    "maximum_monthly_payment_type_withdrawal_limit": MAX_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT,
    "balance_tier_ranges": BALANCE_TIER_RANGES,
    "tiered_minimum_balance_threshold": TIERED_MIN_BALANCE_THRESHOLD,
    "tiered_profit_rates": TIERED_PROFIT_RATES,
    "payment_type_flat_fee": PAYMENT_TYPE_FLAT_FEES,
    "payment_type_threshold_fee": PAYMENT_TYPE_THRESHOLD_FEES,
    "early_closure_fee": "0",
    "early_closure_days": "1",
    "accrued_profit_payable_account": {
        "internal_account_key": ACCRUED_PROFIT_PAYABLE_ACCOUNT,
    },
    "early_closure_fee_income_account": {
        "internal_account_key": EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
    },
    "payment_type_fee_income_account": {
        "internal_account_key": PAYMENT_TYPE_FEE_INCOME_ACCOUNT,
    },
    "profit_paid_account": {
        "internal_account_key": PROFIT_PAID_ACCOUNT,
    },
}

# murabahah template parameters
murabahah_template_params_with_early_closure_fees = {
    "account_tier_names": ACCOUNT_TIER_NAMES,
    "denomination": "MYR",
    "days_in_year": "365",
    "profit_accrual_hour": "0",
    "profit_accrual_minute": "0",
    "profit_accrual_second": "0",
    "profit_application_hour": "0",
    "profit_application_minute": "0",
    "profit_application_second": "0",
    "profit_application_frequency": "monthly",
    "minimum_deposit": "1",
    "minimum_initial_deposit": "0",
    "maximum_balance": "10000",
    "maximum_deposit": "10000",
    "maximum_withdrawal": "10000",
    "maximum_payment_type_withdrawal": MAXIMUM_PAYMENT_TYPE_WITHDRAWAL,
    "maximum_daily_deposit": "1000",
    "maximum_daily_withdrawal": "100",
    "maximum_daily_payment_category_withdrawal": MAXIMUM_DAILY_PAYMENT_CATEGORY_WITHDRAWAL,
    "maximum_daily_payment_type_withdrawal": MAXIMUM_DAILY_PAYMENT_TYPE_WITHDRAWAL,
    "maximum_monthly_payment_type_withdrawal_limit": MAX_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT,
    "balance_tier_ranges": BALANCE_TIER_RANGES,
    "tiered_minimum_balance_threshold": TIERED_MIN_BALANCE_THRESHOLD,
    "tiered_profit_rates": TIERED_PROFIT_RATES,
    "payment_type_flat_fee": PAYMENT_TYPE_FLAT_FEES,
    "payment_type_threshold_fee": PAYMENT_TYPE_THRESHOLD_FEES,
    "early_closure_fee": "100",
    "early_closure_days": "1",
    "accrued_profit_payable_account": {
        "internal_account_key": ACCRUED_PROFIT_PAYABLE_ACCOUNT,
    },
    "early_closure_fee_income_account": {
        "internal_account_key": EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
    },
    "payment_type_fee_income_account": {
        "internal_account_key": PAYMENT_TYPE_FEE_INCOME_ACCOUNT,
    },
    "profit_paid_account": {
        "internal_account_key": PROFIT_PAID_ACCOUNT,
    },
}

# murabahah account instance parameters
murabahah_instance_params = {
    "profit_application_day": "6",
}
