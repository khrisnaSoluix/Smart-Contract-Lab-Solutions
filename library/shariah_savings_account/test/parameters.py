# standard libs
from json import dumps

# library
from library.shariah_savings_account.contracts.template import shariah_savings_account
from library.shariah_savings_account.test import accounts

TEST_DENOMINATION = "MYR"

UPPER_TIER = "SHARIAH_SAVINGS_ACCOUNT_TIER_UPPER"
MIDDLE_TIER = "SHARIAH_SAVINGS_ACCOUNT_TIER_MIDDLE"
LOWER_TIER = "SHARIAH_SAVINGS_ACCOUNT_TIER_LOWER"

# Parameters
TIERED_PROFIT_RATES = {
    UPPER_TIER: {
        "0.00": "0.50",
        "5000.00": "0.50",
        "15000.00": "0.50",
    },
    MIDDLE_TIER: {
        "0.00": "0.50",
        "5000.00": "0.50",
        "15000.00": "0.50",
    },
    LOWER_TIER: {
        "0.00": "0.149",
        "5000.00": "0.149",
        "15000.00": "0.100",
    },
}

PAYMENT_TYPE_FLAT_FEES = {
    "ATM_MEPS": "1",
    "ATM_IBFT": "5",
}

PAYMENT_TYPE_THRESHOLD_FEES = {
    "DUITNOW_PROXY": {"fee": "0.50", "threshold": "5000"},
    "ATM_IBFT": {"fee": "0.15", "threshold": "5000"},
}


MAXIMUM_PAYMENT_TYPE_WITHDRAWAL = {
    "DEBIT_PAYWAVE": "250",
}

TIERED_MIN_BALANCE_THRESHOLD = {
    UPPER_TIER: "25",
    MIDDLE_TIER: "75",
    LOWER_TIER: "100",
}

ACCOUNT_TIER_NAMES = [
    UPPER_TIER,
    MIDDLE_TIER,
    LOWER_TIER,
]

MAX_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT = {
    "ATM_ARBM": {"fee": "0.50", "limit": "2"},
}

DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION_TYPE = {
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

TIERED_DAILY_WITHDRAWAL_LIMITS = {
    UPPER_TIER: {"ATM": "5000"},
    MIDDLE_TIER: {"ATM": "2000"},
    LOWER_TIER: {"ATM": "1500"},
}


max_daily_withdrawal_by_txn_type = (
    shariah_savings_account.maximum_daily_withdrawal_by_transaction_type
)
monthly_limit_by_txn_type = shariah_savings_account.payment_type_monthly_limit_fee
default_instance: dict[str, str] = {
    shariah_savings_account.profit_application.PARAM_PROFIT_APPLICATION_DAY: "5",
    max_daily_withdrawal_by_txn_type.PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION: dumps(
        DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION_TYPE,
    ),
}

default_template: dict[str, str] = {
    shariah_savings_account.PARAM_DENOMINATION: TEST_DENOMINATION,
    shariah_savings_account.PARAM_PAYMENT_TYPE_FEE_INCOME_ACCOUNT: (
        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT
    ),
    shariah_savings_account.account_tiers.PARAM_ACCOUNT_TIER_NAMES: dumps(ACCOUNT_TIER_NAMES),
    shariah_savings_account.early_closure_fee.PARAM_EARLY_CLOSURE_DAYS: "1",
    shariah_savings_account.early_closure_fee.PARAM_EARLY_CLOSURE_FEE: "0",
    shariah_savings_account.early_closure_fee.PARAM_EARLY_CLOSURE_FEE_INCOME_ACCOUNT: (
        accounts.EARLY_CLOSURE_FEE_INCOME_ACCOUNT
    ),
    shariah_savings_account.maximum_balance_limit.PARAM_MAXIMUM_BALANCE: "20000",
    shariah_savings_account.maximum_daily_deposit.PARAM_MAX_DAILY_DEPOSIT: "20000",
    shariah_savings_account.maximum_daily_withdrawal.PARAM_MAX_DAILY_WITHDRAWAL: "20000",
    shariah_savings_account.minimum_initial_deposit.PARAM_MIN_INITIAL_DEPOSIT: "0",
    shariah_savings_account.minimum_single_deposit.PARAM_MIN_DEPOSIT: "100",
    shariah_savings_account.maximum_single_deposit.PARAM_MAX_DEPOSIT: "20000",
    shariah_savings_account.maximum_single_withdrawal.PARAM_MAX_WITHDRAWAL: "10000",
    shariah_savings_account.maximum_withdrawal_by_payment_type.PARAM_MAX_WITHDRAWAL_BY_TYPE: dumps(
        MAXIMUM_PAYMENT_TYPE_WITHDRAWAL
    ),
    monthly_limit_by_txn_type.PARAM_MAXIMUM_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT: dumps(
        MAX_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT
    ),
    shariah_savings_account.payment_type_flat_fee.PARAM_PAYMENT_TYPE_FLAT_FEE: dumps(
        PAYMENT_TYPE_FLAT_FEES
    ),
    shariah_savings_account.payment_type_threshold_fee.PARAM_PAYMENT_TYPE_THRESHOLD_FEE: dumps(
        PAYMENT_TYPE_THRESHOLD_FEES
    ),
    shariah_savings_account.profit_application.PARAM_APPLICATION_PRECISION: "2",
    shariah_savings_account.profit_application.PARAM_PROFIT_APPLICATION_FREQUENCY: "monthly",
    shariah_savings_account.profit_application.PARAM_PROFIT_APPLICATION_HOUR: "0",
    shariah_savings_account.profit_application.PARAM_PROFIT_APPLICATION_MINUTE: "1",
    shariah_savings_account.profit_application.PARAM_PROFIT_APPLICATION_SECOND: "0",
    shariah_savings_account.profit_application.PARAM_PROFIT_PAID_ACCOUNT: (
        accounts.PROFIT_PAID_ACCOUNT
    ),
    max_daily_withdrawal_by_txn_type.PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT: dumps(
        TIERED_DAILY_WITHDRAWAL_LIMITS
    ),
    shariah_savings_account.minimum_balance_by_tier.PARAM_MIN_BALANCE_THRESHOLD: dumps(
        TIERED_MIN_BALANCE_THRESHOLD
    ),
    shariah_savings_account.tiered_profit_accrual.PARAM_TIERED_PROFIT_RATES: dumps(
        TIERED_PROFIT_RATES
    ),
    shariah_savings_account.tiered_profit_accrual.PARAM_ACCRUAL_PRECISION: "5",
    shariah_savings_account.tiered_profit_accrual.PARAM_DAYS_IN_YEAR: "365",
    shariah_savings_account.tiered_profit_accrual.PARAM_PROFIT_ACCRUAL_HOUR: "0",
    shariah_savings_account.tiered_profit_accrual.PARAM_PROFIT_ACCRUAL_MINUTE: "0",
    shariah_savings_account.tiered_profit_accrual.PARAM_PROFIT_ACCRUAL_SECOND: "0",
    shariah_savings_account.tiered_profit_accrual.PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT: (
        accounts.ACCRUED_PROFIT_PAYABLE_ACCOUNT
    ),
}
