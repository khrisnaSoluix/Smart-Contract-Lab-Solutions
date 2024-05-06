# standard libs
from json import dumps

# library
import library.savings_account.contracts.template.savings_account as savings_account
from library.savings_account.test import accounts

# inception sdk
from inception_sdk.test_framework.common import constants

TEST_DENOMINATION = constants.DEFAULT_DENOMINATION

# Flag parameter values
DORMANCY_FLAG = "ACCOUNT_DORMANT"
DORMANCY_FLAGS = [DORMANCY_FLAG]
UPPER_TIER = "UPPER_TIER"
MIDDLE_TIER = "MIDDLE_TIER"
LOWER_TIER = "LOWER_TIER"
TIER_FLAGS = [UPPER_TIER, MIDDLE_TIER, LOWER_TIER]
MINIMUM_BALANCE_THRESHOLD_BY_TIER = {UPPER_TIER: "25", MIDDLE_TIER: "75", LOWER_TIER: "100"}
WITHDRAWAL_LIMIT_BY_TIER = {
    UPPER_TIER: {"ATM": "5000"},
    MIDDLE_TIER: {"ATM": "2000"},
    LOWER_TIER: {"ATM": "1500"},
}

maximum_daily_withdrawal_by_transaction_type = (
    savings_account.maximum_daily_withdrawal_by_transaction_type
)

# Default Parameters
default_template: dict[str, str] = {
    savings_account.common_parameters.PARAM_DENOMINATION: TEST_DENOMINATION,
    savings_account.dormancy.PARAM_DORMANCY_FLAGS: dumps(DORMANCY_FLAGS),
    savings_account.account_tiers.PARAM_ACCOUNT_TIER_NAMES: dumps(TIER_FLAGS),
    savings_account.excess_fee.PARAM_EXCESS_FEE: "2.50",
    savings_account.excess_fee.PARAM_EXCESS_FEE_ACCOUNT: accounts.EXCESS_FEE_INCOME_ACCOUNT,
    savings_account.excess_fee.PARAM_EXCESS_FEE_MONITORED_TRANSACTION_TYPE: "ATM",
    savings_account.excess_fee.PARAM_PERMITTED_WITHDRAWALS: "6",
    savings_account.inactivity_fee.PARAM_INACTIVITY_FLAGS: dumps(DORMANCY_FLAGS),
    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE: "10",
    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_HOUR: "0",
    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE: "1",
    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_SECOND: "0",
    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_INCOME_ACCOUNT: (
        accounts.INACTIVITY_FEE_INCOME_ACCOUNT
    ),
    savings_account.tiered_interest_accrual.PARAM_ACCRUAL_PRECISION: "5",
    savings_account.tiered_interest_accrual.PARAM_DAYS_IN_YEAR: "365",
    savings_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "0",
    savings_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "0",
    savings_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "0",
    savings_account.interest_application.PARAM_APPLICATION_PRECISION: "2",
    savings_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: "monthly",
    savings_account.interest_application.PARAM_INTEREST_APPLICATION_HOUR: "0",
    savings_account.interest_application.PARAM_INTEREST_APPLICATION_MINUTE: "1",
    savings_account.interest_application.PARAM_INTEREST_APPLICATION_SECOND: "0",
    savings_account.interest_application.PARAM_INTEREST_PAID_ACCOUNT: (
        accounts.INTEREST_PAID_ACCOUNT
    ),
    savings_account.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTEREST_RECEIVED_ACCOUNT
    ),
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER: dumps(
        MINIMUM_BALANCE_THRESHOLD_BY_TIER
    ),
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_HOUR: "0",
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_MINUTE: "1",
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_SECOND: "0",
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: (
        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT
    ),
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED: "False",
    savings_account.minimum_single_deposit_limit.PARAM_MIN_DEPOSIT: "5",
    savings_account.minimum_single_withdrawal_limit.PARAM_MIN_WITHDRAWAL: "5",
    savings_account.maximum_balance_limit.PARAM_MAXIMUM_BALANCE: "50000",
    savings_account.maximum_daily_deposit_limit.PARAM_MAX_DAILY_DEPOSIT: "40000",
    savings_account.maximum_daily_withdrawal.PARAM_MAX_DAILY_WITHDRAWAL: "20000",
    maximum_daily_withdrawal_by_transaction_type.PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT: dumps(
        WITHDRAWAL_LIMIT_BY_TIER
    ),
    savings_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: dumps(
        {
            "0.00": "0.01",
            "1000.00": "0.02",
            "3000.00": "0.035",
            "5000.00": "0.05",
            "10000.00": "0.06",
        }
    ),
    savings_account.tiered_interest_accrual.PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT
    ),
    savings_account.tiered_interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    ),
    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED: "False",
}

default_instance: dict[str, str] = {
    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_DAY: "1",
    savings_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "2",
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_DAY: "1",
    maximum_daily_withdrawal_by_transaction_type.PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION: dumps(
        {}
    ),
}
