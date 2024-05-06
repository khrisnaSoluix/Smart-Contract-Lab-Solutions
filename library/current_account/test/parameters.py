# standard libs
from json import dumps

# library
import library.current_account.contracts.template.current_account as current_account
from library.current_account.test import accounts

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
MONTHLY_MAINTENANCE_FEE_BY_TIER = {UPPER_TIER: "20", MIDDLE_TIER: "10", LOWER_TIER: "5"}
ZERO_MAINTENANCE_FEE_BY_TIER = {UPPER_TIER: "0", MIDDLE_TIER: "0", LOWER_TIER: "0"}
ANNUAL_MAINTENANCE_FEE_BY_TIER = {UPPER_TIER: "200", MIDDLE_TIER: "175", LOWER_TIER: "150"}
MINIMUM_BALANCE_THRESHOLD_BY_TIER = {UPPER_TIER: "25", MIDDLE_TIER: "75", LOWER_TIER: "100"}
WITHDRAWAL_LIMIT_BY_TIER = {
    UPPER_TIER: {"ATM": "5000"},
    MIDDLE_TIER: {"ATM": "2000"},
    LOWER_TIER: {"ATM": "1500"},
}


maximum_daily_withdrawal_by_transaction_type = (
    current_account.maximum_daily_withdrawal_by_transaction_type
)

# Default Parameters
default_template: dict[str, str] = {
    current_account.PARAM_ADDITIONAL_DENOMINATIONS: dumps(["USD"]),
    current_account.common_parameters.PARAM_DENOMINATION: TEST_DENOMINATION,
    current_account.dormancy.PARAM_DORMANCY_FLAGS: dumps(DORMANCY_FLAGS),
    current_account.account_tiers.PARAM_ACCOUNT_TIER_NAMES: dumps(TIER_FLAGS),
    current_account.excess_fee.PARAM_EXCESS_FEE: "2.50",
    current_account.excess_fee.PARAM_EXCESS_FEE_ACCOUNT: accounts.EXCESS_FEE_INCOME_ACCOUNT,
    current_account.excess_fee.PARAM_EXCESS_FEE_MONITORED_TRANSACTION_TYPE: "ATM",
    current_account.excess_fee.PARAM_PERMITTED_WITHDRAWALS: "6",
    current_account.inactivity_fee.PARAM_INACTIVITY_FEE: "10",
    current_account.inactivity_fee.PARAM_INACTIVITY_FLAGS: dumps(DORMANCY_FLAGS),
    current_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_HOUR: "0",
    current_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE: "0",
    current_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_SECOND: "0",
    current_account.inactivity_fee.PARAM_INACTIVITY_FEE_INCOME_ACCOUNT: (
        accounts.INACTIVITY_FEE_INCOME_ACCOUNT
    ),
    current_account.tiered_interest_accrual.PARAM_ACCRUAL_PRECISION: "5",
    current_account.tiered_interest_accrual.PARAM_DAYS_IN_YEAR: "365",
    current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "0",
    current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "0",
    current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "0",
    current_account.interest_application.PARAM_APPLICATION_PRECISION: "2",
    current_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: "monthly",
    current_account.interest_application.PARAM_INTEREST_APPLICATION_HOUR: "0",
    current_account.interest_application.PARAM_INTEREST_APPLICATION_MINUTE: "1",
    current_account.interest_application.PARAM_INTEREST_APPLICATION_SECOND: "0",
    current_account.interest_application.PARAM_INTEREST_PAID_ACCOUNT: (
        accounts.INTEREST_PAID_ACCOUNT
    ),
    current_account.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTEREST_RECEIVED_ACCOUNT
    ),
    current_account.maintenance_fees.PARAM_ANNUAL_MAINTENANCE_FEE_BY_TIER: dumps(
        ZERO_MAINTENANCE_FEE_BY_TIER
    ),
    current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: dumps(
        ZERO_MAINTENANCE_FEE_BY_TIER
    ),
    current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_HOUR: "0",
    current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_MINUTE: "1",
    current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_SECOND: "0",
    current_account.maintenance_fees.PARAM_ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: (
        accounts.ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT
    ),
    current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: (
        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT
    ),
    current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED: "False",
    current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
    current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER: dumps(
        MINIMUM_BALANCE_THRESHOLD_BY_TIER
    ),
    current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_HOUR: "0",
    current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_MINUTE: "1",
    current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_SECOND: "0",
    current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: (
        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT
    ),
    current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED: "False",
    current_account.minimum_single_deposit_limit.PARAM_MIN_DEPOSIT: "5",
    current_account.minimum_single_withdrawal_limit.PARAM_MIN_WITHDRAWAL: "5",
    current_account.maximum_balance_limit.PARAM_MAXIMUM_BALANCE: "50000",
    current_account.maximum_daily_deposit_limit.PARAM_MAX_DAILY_DEPOSIT: "40000",
    current_account.maximum_daily_withdrawal.PARAM_MAX_DAILY_WITHDRAWAL: "20000",
    maximum_daily_withdrawal_by_transaction_type.PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT: dumps(
        WITHDRAWAL_LIMIT_BY_TIER
    ),
    current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_DAYS: "2",
    current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_AMOUNT: "50",
    current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_RATE: "0.05",
    current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT
    ),
    current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: (
        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT
    ),
    current_account.roundup_autosave.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT: "1",
    current_account.roundup_autosave.PARAM_ROUNDUP_AUTOSAVE_TRANSACTION_TYPES: dumps(["PURCHASE"]),
    current_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: dumps(
        {
            "0.00": "0.01",
            "1000.00": "0.02",
            "3000.00": "0.035",
            "5000.00": "0.05",
            "10000.00": "0.06",
        }
    ),
    current_account.tiered_interest_accrual.PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT
    ),
    current_account.tiered_interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    ),
    current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_HOUR: "0",
    current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_MINUTE: "1",
    current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_SECOND: "0",
    current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE: "5",
    current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_CAP: "30",
    current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT: (
        accounts.UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT
    ),
    current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: (
        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT
    ),
    current_account.inactivity_fee.PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED: "False",
}

default_instance: dict[str, str] = {
    current_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_DAY: "1",
    current_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "1",
    current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_DAY: "1",
    current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_DAY: "1",
    current_account.overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "100",
    current_account.overdraft_limit.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "50",
    current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_DAY: "1",
    current_account.roundup_autosave.PARAM_ROUNDUP_AUTOSAVE_ACTIVE: "True",
    maximum_daily_withdrawal_by_transaction_type.PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION: dumps(
        {}
    ),
}

no_overdraft = {
    current_account.overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "0",
    current_account.overdraft_limit.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "0",
}
small_arranged_overdraft = {
    current_account.overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "5",
    current_account.overdraft_limit.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "0",
}
zero_minimum_deposit = {current_account.minimum_single_deposit_limit.PARAM_MIN_DEPOSIT: "0"}

annual_interest = {
    current_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: "annually",
}
maintenance_fees_enabled = {
    current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: dumps(
        MONTHLY_MAINTENANCE_FEE_BY_TIER
    ),
    current_account.maintenance_fees.PARAM_ANNUAL_MAINTENANCE_FEE_BY_TIER: dumps(
        ANNUAL_MAINTENANCE_FEE_BY_TIER
    ),
}
minimum_balance_fee_enabled = {
    current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
}

instance_parameters_no_overdraft = {**default_instance, **no_overdraft}
instance_parameters_small_overdraft = {**default_instance, **small_arranged_overdraft}

template_parameters_annual_interest = {**default_template, **annual_interest}

template_parameters_annual_interest_maintenance_fees_enabled = {
    **template_parameters_annual_interest,
    **maintenance_fees_enabled,
}

template_parameters_fees_enabled = {
    **default_template,
    **maintenance_fees_enabled,
    **minimum_balance_fee_enabled,
}
