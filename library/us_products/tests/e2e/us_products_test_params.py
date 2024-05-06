from json import dumps

# constants for account names
ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INT_RECEIVABLE"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
OVERDRAFT_FEE_INCOME_ACCOUNT = "OVERDRAFT_FEE_INCOME"
MAINTENANCE_FEE_INCOME_ACCOUNT = "MAINTENANCE_FEE_INCOME"
OVERDRAFT_FEE_RECEIVABLE_ACCOUNT = "OVERDRAFT_FEE_RECEIVABLE"
MINIMUM_BALANCE_FEE_INCOME_ACCOUNT = "MINIMUM_BALANCE_FEE_INCOME"
ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT = "ANNUAL_MAINTENANCE_FEE_INC"
INACTIVITY_FEE_INCOME_ACCOUNT = "INACTIVITY_FEE_INCOME"
EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT = "EXCESS_WITHDRAWAL_FEE_INC"

# required internal accounts dictionary
internal_accounts_tside = {
    "TSIDE_ASSET": [
        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
        INTEREST_PAID_ACCOUNT,
        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
    ],
    "TSIDE_LIABILITY": [
        ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
        INTEREST_RECEIVED_ACCOUNT,
        ACCRUED_INTEREST_PAYABLE_ACCOUNT,
        EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
        INACTIVITY_FEE_INCOME_ACCOUNT,
        MAINTENANCE_FEE_INCOME_ACCOUNT,
        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
        OVERDRAFT_FEE_INCOME_ACCOUNT,
    ],
}

# required constants for product schedules tests
SCHEDULE_TAGS_DIR = "library/us_products/account_schedule_tags/tests/"
PAUSED_SCHEDULE_TAG = SCHEDULE_TAGS_DIR + "paused_tag.resource.yaml"

# By default all schedules are paused
DEFAULT_TAGS = {
    "US_CHECKING_ACCRUE_INTEREST_AND_DAILY_FEES_AST": PAUSED_SCHEDULE_TAG,
    "US_CHECKING_APPLY_ACCRUED_DEPOSIT_INTEREST_AST": PAUSED_SCHEDULE_TAG,
    "US_CHECKING_APPLY_ACCRUED_OVERDRAFT_INTEREST_AST": PAUSED_SCHEDULE_TAG,
    "US_CHECKING_APPLY_ANNUAL_FEES_AST": PAUSED_SCHEDULE_TAG,
    "US_CHECKING_APPLY_MONTHLY_FEES_AST": PAUSED_SCHEDULE_TAG,
    "US_SAVINGS_ACCRUE_INTEREST_AST": PAUSED_SCHEDULE_TAG,
    "US_SAVINGS_APPLY_ACCRUED_INTEREST_AST": PAUSED_SCHEDULE_TAG,
    "US_SAVINGS_APPLY_ANNUAL_FEES_AST": PAUSED_SCHEDULE_TAG,
    "US_SAVINGS_APPLY_MONTHLY_FEES_AST": PAUSED_SCHEDULE_TAG,
}

# constants - checking account product
STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG = "STANDARD_OVERDRAFT_TRANSACTION_COVERAGE"


# constants used for the US savings account
BALANCE_TIER_RANGES = dumps(
    {
        "tier1": {"min": "0", "max": "5000.00"},
        "tier2": {"min": "5000.00", "max": "15000.00"},
        "tier3": {"min": "15000.00"},
    }
)

TIERED_INTEREST_RATES = {
    "flag_key": {
        "US_SAVINGS_ACCOUNT_TIER_UPPER": {
            "tier1": "0.02",
            "tier2": "0.015",
            "tier3": "-0.01",
        },
        "US_SAVINGS_ACCOUNT_TIER_MIDDLE": {
            "tier1": "0.0125",
            "tier2": "0.01",
            "tier3": "-0.015",
        },
        "US_SAVINGS_ACCOUNT_TIER_LOWER": {
            "tier1": "0",
            "tier2": "0.1485",
            "tier3": "-0.1485",
        },
    }
}

TIERED_MIN_BALANCE_THRESHOLD = {
    "flag_key": {
        "US_SAVINGS_ACCOUNT_TIER_UPPER": "25",
        "US_SAVINGS_ACCOUNT_TIER_MIDDLE": "75",
        "US_SAVINGS_ACCOUNT_TIER_LOWER": "100",
    }
}
ACCOUNT_TIER_NAMES = {
    "flag_key": [
        "US_SAVINGS_ACCOUNT_TIER_UPPER",
        "US_SAVINGS_ACCOUNT_TIER_MIDDLE",
        "US_SAVINGS_ACCOUNT_TIER_LOWER",
    ]
}

# all internal account parameters should use a dictionary with key "internal account key"
# e.g. "accrued_interest_payable_account": {
#      "internal_account_key": ACCRUED_INTEREST_PAYABLE_ACCOUNT},

# US savings account template parameters
us_savings_account_template_params = {
    "denomination": "USD",
    "balance_tier_ranges": BALANCE_TIER_RANGES,
    "tiered_interest_rates": TIERED_INTEREST_RATES,
    "minimum_combined_balance_threshold": {
        "flag_key": {
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "3000",
            "US_SAVINGS_ACCOUNT_TIER_MIDDLE": "4000",
            "US_SAVINGS_ACCOUNT_TIER_LOWER": "5000",
        }
    },
    "minimum_deposit": "1",
    "maximum_balance": "10000",
    "maximum_daily_deposit": "1000",
    "maximum_daily_withdrawal": "100",
    "minimum_withdrawal": "1",
    "accrued_interest_payable_account": {
        "internal_account_key": ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    },
    "interest_paid_account": {
        "internal_account_key": INTEREST_PAID_ACCOUNT,
    },
    "accrued_interest_receivable_account": {
        "internal_account_key": ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    },
    "interest_received_account": {
        "internal_account_key": INTEREST_RECEIVED_ACCOUNT,
    },
    "maintenance_fee_income_account": {
        "internal_account_key": MAINTENANCE_FEE_INCOME_ACCOUNT,
    },
    "excess_withdrawal_fee_income_account": {
        "internal_account_key": EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
    },
    "minimum_balance_fee_income_account": {
        "internal_account_key": MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
    },
    "days_in_year": "365",
    "interest_accrual_hour": "0",
    "interest_accrual_minute": "0",
    "interest_accrual_second": "0",
    "interest_application_hour": "0",
    "interest_application_minute": "0",
    "interest_application_second": "0",
    "interest_application_frequency": "monthly",
    "monthly_withdrawal_limit": "1",
    "reject_excess_withdrawals": "true",
    "excess_withdrawal_fee": "10",
    "maintenance_fee_annual": "0",
    "maintenance_fee_monthly": {"flag_key": {"US_SAVINGS_ACCOUNT_TIER_LOWER": "0"}},
    "promotional_maintenance_fee_monthly": {"flag_key": {"US_SAVINGS_ACCOUNT_TIER_LOWER": "0"}},
    "fees_application_day": "1",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "tiered_minimum_balance_threshold": TIERED_MIN_BALANCE_THRESHOLD,
    "minimum_balance_fee": "0",
    "account_tier_names": ACCOUNT_TIER_NAMES,
    "automated_transfer_tag": "DEPOSIT_ACH_",
    "promotional_rates": TIERED_INTEREST_RATES,
}

# savings account template with increase daily deposit and balance limits for interest accrual test
# parameter used for test_us_savings_account_product_schedules/test_initial_accrual
us_savings_template_params_increased_daily_deposit = us_savings_account_template_params.copy()
us_savings_template_params_increased_daily_deposit["maximum_balance"] = "1000000"
us_savings_template_params_increased_daily_deposit["maximum_daily_deposit"] = "100000"

# savings account template parameters with allowance of excess withdrawals
# parameters used for test_us_savings_account_product/savings_account_product tests only
us_savings_account_template_params_allow_excess_withdrawals = (
    us_savings_account_template_params.copy()
)
us_savings_account_template_params_allow_excess_withdrawals["reject_excess_withdrawals"] = "false"

# first checking account template parameters used for checking_account_product tests
checking_account_template_params = {
    "denomination": "USD",
    "additional_denominations": dumps([]),
    "deposit_interest_application_frequency": "monthly",
    "deposit_tier_ranges": dumps(
        {
            "tier1": {"min": "0", "max": "3000.00"},
            "tier2": {"min": "3000.00", "max": "5000.00"},
            "tier3": {"min": "5000.00", "max": "7500.00"},
            "tier4": {"min": "7500.00", "max": "15000.00"},
            "tier5": {"min": "15000.00"},
        }
    ),
    "deposit_interest_rate_tiers": dumps(
        {
            "tier1": "0.05",
            "tier2": "0.04",
            "tier3": "0.02",
            "tier4": "0",
            "tier5": "-0.035",
        }
    ),
    "interest_accrual_days_in_year": "365",
    "overdraft_interest_rate": "0.14",
    "interest_free_buffer": {
        "flag_key": {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "500",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "300",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "50",
        }
    },
    "overdraft_interest_free_buffer_days": {
        "flag_key": {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "-1",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "21",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "-1",
        }
    },
    "standard_overdraft_per_transaction_fee": "34",
    "standard_overdraft_daily_fee": "5",
    "standard_overdraft_fee_cap": "80",
    "savings_sweep_fee": "0",
    "savings_sweep_fee_cap": "-1",
    "savings_sweep_transfer_unit": "0",
    "interest_accrual_hour": "1",
    "interest_accrual_minute": "2",
    "interest_accrual_second": "3",
    "interest_application_hour": "4",
    "interest_application_minute": "5",
    "interest_application_second": "6",
    "accrued_interest_receivable_account": {
        "internal_account_key": ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    },
    "interest_received_account": {
        "internal_account_key": INTEREST_RECEIVED_ACCOUNT,
    },
    "accrued_interest_payable_account": {
        "internal_account_key": ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    },
    "interest_paid_account": {
        "internal_account_key": INTEREST_PAID_ACCOUNT,
    },
    "overdraft_fee_income_account": {
        "internal_account_key": OVERDRAFT_FEE_INCOME_ACCOUNT,
    },
    "overdraft_fee_receivable_account": {
        "internal_account_key": OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
    },
    "maintenance_fee_income_account": {
        "internal_account_key": MAINTENANCE_FEE_INCOME_ACCOUNT,
    },
    "minimum_balance_fee_income_account": {
        "internal_account_key": MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
    },
    "annual_maintenance_fee_income_account": {
        "internal_account_key": ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
    },
    "inactivity_fee_income_account": {
        "internal_account_key": INACTIVITY_FEE_INCOME_ACCOUNT,
    },
    "maintenance_fee_annual": "0",
    "maintenance_fee_monthly": {"flag_key": {"US_CHECKING_ACCOUNT_TIER_LOWER": "0"}},
    "promotional_maintenance_fee_monthly": {"flag_key": {"US_CHECKING_ACCOUNT_TIER_LOWER": "0"}},
    "minimum_balance_threshold": {"flag_key": {"US_CHECKING_ACCOUNT_TIER_LOWER": "1500"}},
    "minimum_combined_balance_threshold": {"flag_key": {"US_CHECKING_ACCOUNT_TIER_LOWER": "5000"}},
    "minimum_deposit_threshold": {"flag_key": {"US_CHECKING_ACCOUNT_TIER_LOWER": "500"}},
    "account_inactivity_fee": "0",
    "tier_names": {
        "flag_key": [
            "US_CHECKING_ACCOUNT_TIER_UPPER",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE",
            "US_CHECKING_ACCOUNT_TIER_LOWER",
        ]
    },
    "minimum_balance_fee": "0",
    "fees_application_day": "1",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "maximum_daily_atm_withdrawal_limit": {
        "flag_key": {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "5000",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "2000",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "1000",
        }
    },
    "transaction_code_to_type_map": dumps({"6011": "ATM withdrawal", "3123": "eCommerce"}),
    "transaction_types": dumps(["purchase", "ATM withdrawal", "transfer"]),
    "autosave_rounding_amount": "1.00",
    "optional_standard_overdraft_coverage": dumps(["ATM withdrawal", "eCommerce"]),
}

# second checking account template parameters used for savings_account_product tests
checking_account_template_params_savings_tests = {
    "denomination": "USD",
    "additional_denominations": dumps([]),
    "deposit_interest_application_frequency": "monthly",
    "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
    "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
    "interest_accrual_days_in_year": "365",
    "overdraft_interest_rate": "0.14",
    "standard_overdraft_daily_fee": "5",
    "savings_sweep_fee": "0",
    "savings_sweep_fee_cap": "-1",
    "savings_sweep_transfer_unit": "0",
    "interest_free_buffer": {
        "flag_key": {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "500",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "300",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "50",
        }
    },
    "overdraft_interest_free_buffer_days": {
        "flag_key": {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "-1",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "21",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "-1",
        }
    },
    "standard_overdraft_per_transaction_fee": "0",
    "standard_overdraft_fee_cap": "80",
    "interest_accrual_hour": "1",
    "interest_accrual_minute": "2",
    "interest_accrual_second": "3",
    "interest_application_hour": "4",
    "interest_application_minute": "5",
    "interest_application_second": "6",
    "accrued_interest_receivable_account": {
        "internal_account_key": ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    },
    "interest_received_account": {
        "internal_account_key": INTEREST_RECEIVED_ACCOUNT,
    },
    "accrued_interest_payable_account": {
        "internal_account_key": ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    },
    "interest_paid_account": {
        "internal_account_key": INTEREST_PAID_ACCOUNT,
    },
    "overdraft_fee_income_account": {
        "internal_account_key": OVERDRAFT_FEE_INCOME_ACCOUNT,
    },
    "overdraft_fee_receivable_account": {
        "internal_account_key": OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
    },
    "maintenance_fee_income_account": {
        "internal_account_key": MAINTENANCE_FEE_INCOME_ACCOUNT,
    },
    "minimum_balance_fee_income_account": {
        "internal_account_key": MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
    },
    "annual_maintenance_fee_income_account": {
        "internal_account_key": ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
    },
    "inactivity_fee_income_account": {
        "internal_account_key": INACTIVITY_FEE_INCOME_ACCOUNT,
    },
    "maintenance_fee_annual": "0",
    "maintenance_fee_monthly": {"flag_key": {"US_CHECKING_ACCOUNT_TIER_LOWER": "0"}},
    "promotional_maintenance_fee_monthly": {"flag_key": {"US_CHECKING_ACCOUNT_TIER_LOWER": "0"}},
    "minimum_balance_threshold": {"flag_key": {"US_CHECKING_ACCOUNT_TIER_LOWER": "1500"}},
    "minimum_combined_balance_threshold": {"flag_key": {"US_CHECKING_ACCOUNT_TIER_LOWER": "5000"}},
    "minimum_deposit_threshold": {"flag_key": {"US_CHECKING_ACCOUNT_TIER_LOWER": "500"}},
    "account_inactivity_fee": "0",
    "tier_names": {
        "flag_key": [
            "US_CHECKING_ACCOUNT_TIER_UPPER",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE",
            "US_CHECKING_ACCOUNT_TIER_LOWER",
        ]
    },
    "minimum_balance_fee": "0",
    "fees_application_day": "1",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "maximum_daily_atm_withdrawal_limit": {
        "flag_key": {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "5000",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "2000",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "1000",
        }
    },
    "transaction_code_to_type_map": dumps({"6011": "ATM withdrawal", "3123": "eCommerce"}),
    "transaction_types": dumps(["purchase", "ATM withdrawal", "transfer"]),
    "autosave_rounding_amount": "1.00",
    "optional_standard_overdraft_coverage": dumps(["ATM withdrawal", "eCommerce"]),
}


# checking account template params where the per-transaction fee charged for any transaction
# that uses the standard overdraft is 0 - used in checking_account_product tests only
checking_account_template_params_for_close = checking_account_template_params.copy()
checking_account_template_params_for_close["standard_overdraft_per_transaction_fee"] = "0"

# checking account instance parameters - used for checking account product tests only
checking_account_instance_params = {
    "fee_free_overdraft_limit": "1000",
    "standard_overdraft_limit": "2000",
    "interest_application_day": "1",
    "daily_atm_withdrawal_limit": "1000",
}
