# standard libs
from json import dumps

# library
from library.us_products.contracts.template import us_checking_account
from library.us_products.test import accounts

TEST_DENOMINATION = "USD"

UPPER_TIER = "UPPER_TIER"
MIDDLE_TIER = "MIDDLE_TIER"
LOWER_TIER = "LOWER_TIER"
ACCOUNT_TIER_NAMES = [UPPER_TIER, MIDDLE_TIER, LOWER_TIER]

MONTHLY_MAINTENANCE_FEE_BY_TIER = {UPPER_TIER: "20", MIDDLE_TIER: "10", LOWER_TIER: "5"}
MONTHLY_MAINTENANCE_FEE_BY_TIER_ZERO = {UPPER_TIER: "0", MIDDLE_TIER: "0", LOWER_TIER: "0"}

TIERED_INTEREST_RATES = {
    "0.00": "0.01",
    "1000.00": "0.02",
    "3000.00": "0.035",
    "5000.00": "0.05",
    "10000.00": "0.06",
}

TIERED_INTEREST_RATES_ZERO = {
    "0.00": "0.00",
}

TIERED_DAILY_WITHDRAWAL_LIMIT = {
    UPPER_TIER: {"ATM": "5000"},
    MIDDLE_TIER: {"ATM": "2000"},
    LOWER_TIER: {"ATM": "1500"},
}

DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION = {"ATM": "1000", "CASH": "500"}
ELIGIBLE_FEE_TYPES = ["out_of_network_ATM"]
FEE_REBATE_INTERNAL_ACCOUNTS = {
    "out_of_network_ATM": accounts.OUT_OF_NETWORK_ATM_FEE_REBATE_ACCOUNT
}

MINIMUM_BALANCE_THRESHOLD_BY_TIER = {
    UPPER_TIER: "25",
    MIDDLE_TIER: "75",
    LOWER_TIER: "100",
}

DEPOSIT_THRESHOLD_BY_TIER = {
    UPPER_TIER: "300",
    MIDDLE_TIER: "150",
    LOWER_TIER: "100",
}

# Flag names
TEST_INACTIVITY_FLAG = "ACCOUNT_INACTIVE"
DEFAULT_INACTIVITY_FLAGS = [TEST_INACTIVITY_FLAG]
DORMANCY_FLAG = "ACCOUNT_DORMANT"
DORMANCY_FLAGS = [DORMANCY_FLAG]

EXCLUDED_TRANSACTION = "excluded_transaction_type"
EXCLUDED_TRANSACTIONS = [EXCLUDED_TRANSACTION]


checking_account_instance_params: dict[str, str] = {
    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "1",
    us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_DAY: "1",
    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_DAY: "1",
    us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_DAY: "1",
    us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_ENABLED: "False",
    us_checking_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_DAY: "1",
    us_checking_account.overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "100",
    us_checking_account.overdraft_coverage.PARAM_OVERDRAFT_OPT_IN: "True",
    us_checking_account.overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "50",
    us_checking_account.maximum_daily_withdrawal_by_transaction_type.PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION: (  # noqa: E501
        dumps(DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION)
    ),
}

checking_account_template_params: dict[str, str] = {
    us_checking_account.overdraft_coverage.PARAM_EXCLUDED_OVERDRAFT_COVERAGE_LIST: dumps(
        EXCLUDED_TRANSACTIONS
    ),
    us_checking_account.tiered_interest_accrual.PARAM_ACCRUAL_PRECISION: "5",
    us_checking_account.tiered_interest_accrual.PARAM_DAYS_IN_YEAR: "365",
    us_checking_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "0",
    us_checking_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "0",
    us_checking_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "0",
    us_checking_account.tiered_interest_accrual.PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT
    ),
    us_checking_account.tiered_interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    ),
    us_checking_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: dumps(
        TIERED_INTEREST_RATES
    ),
    us_checking_account.PARAM_DENOMINATION: TEST_DENOMINATION,
    us_checking_account.account_tiers.PARAM_ACCOUNT_TIER_NAMES: dumps(ACCOUNT_TIER_NAMES),
    us_checking_account.maximum_daily_withdrawal_by_transaction_type.PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT: (  # noqa: E501
        dumps(TIERED_DAILY_WITHDRAWAL_LIMIT)
    ),
    us_checking_account.interest_application.PARAM_APPLICATION_PRECISION: "2",
    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: "monthly",
    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_HOUR: "0",
    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_MINUTE: "1",
    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_SECOND: "0",
    us_checking_account.interest_application.PARAM_INTEREST_PAID_ACCOUNT: (
        accounts.INTEREST_PAID_ACCOUNT
    ),
    us_checking_account.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTEREST_RECEIVED_ACCOUNT
    ),
    us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
    us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER: dumps(
        MINIMUM_BALANCE_THRESHOLD_BY_TIER
    ),
    us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_HOUR: "0",
    us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_MINUTE: "1",
    us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_SECOND: "0",
    us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: (
        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT
    ),
    us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED: "False",
    us_checking_account.dormancy.PARAM_DORMANCY_FLAGS: dumps(DORMANCY_FLAGS),
    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FLAGS: dumps(DEFAULT_INACTIVITY_FLAGS),
    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE: "10",
    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_INCOME_ACCOUNT: (
        accounts.INACTIVITY_FEE_INCOME_ACCOUNT
    ),
    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_HOUR: "0",
    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE: "0",
    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_SECOND: "0",
    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED: "False",
    us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_PARTIAL_FEE_ENABLED: "False",
    us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_RATE: "20",
    us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_INCOME_ACCOUNT: (
        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT
    ),
    us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_HOUR: "0",
    us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_MINUTE: "0",
    us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_SECOND: "0",
    us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: dumps(
        MONTHLY_MAINTENANCE_FEE_BY_TIER_ZERO
    ),
    us_checking_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_HOUR: "0",
    us_checking_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_MINUTE: "1",
    us_checking_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_SECOND: "0",
    us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: (
        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT
    ),
    us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED: "False",
    us_checking_account.deposit_parameters.PARAM_CAPITALISE_ACCRUED_INTEREST_ON_ACCOUNT_CLOSURE: (  # noqa: E501
        "False"
    ),
    us_checking_account.direct_deposit_tracker.PARAM_DEPOSIT_THRESHOLD_BY_TIER: dumps(
        DEPOSIT_THRESHOLD_BY_TIER
    ),
    us_checking_account.unlimited_fee_rebate.PARAM_ELIGIBLE_FEE_TYPES: dumps(ELIGIBLE_FEE_TYPES),
    us_checking_account.unlimited_fee_rebate.PARAM_FEE_REBATE_INTERNAL_ACCOUNTS: dumps(
        FEE_REBATE_INTERNAL_ACCOUNTS
    ),
}
