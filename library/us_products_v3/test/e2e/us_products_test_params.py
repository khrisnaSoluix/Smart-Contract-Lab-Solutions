# standard libs
from json import dumps

# library
import library.common.flag_definitions.files as common_flag_definition_files
import library.us_products_v3.constants.files as files

# constants for account names
ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INT_RECEIVABLE"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
OVERDRAFT_FEE_INCOME_ACCOUNT = "OVERDRAFT_FEE_INCOME"
MAINTENANCE_FEE_INCOME_ACCOUNT = "MAINTENANCE_FEE_INCOME"
OVERDRAFT_FEE_RECEIVABLE_ACCOUNT = "OVERDRAFT_FEE_RECEIVABLE"
MINIMUM_BALANCE_FEE_INCOME_ACCOUNT = "MINIMUM_BALANCE_FEE_INCOME"
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
        INTEREST_RECEIVED_ACCOUNT,
        ACCRUED_INTEREST_PAYABLE_ACCOUNT,
        EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
        INACTIVITY_FEE_INCOME_ACCOUNT,
        MAINTENANCE_FEE_INCOME_ACCOUNT,
        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
        OVERDRAFT_FEE_INCOME_ACCOUNT,
    ],
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
}

TIERED_MIN_BALANCE_THRESHOLD = {
    "flag_key": {
        "UPPER_TIER": "25",
        "MIDDLE_TIER": "75",
        "LOWER_TIER": "100",
    }
}
ACCOUNT_TIER_NAMES = {
    "flag_key": [
        "UPPER_TIER",
        "MIDDLE_TIER",
        "LOWER_TIER",
    ]
}

# all internal account parameters should use a dictionary with key "internal account key"
# e.g. "accrued_interest_payable_account": {
#      "internal_account_key": ACCRUED_INTEREST_PAYABLE_ACCOUNT},

# US savings account template parameters
us_savings_account_template_params = {
    "denomination": "USD",
    "balance_tier_ranges": dumps(
        {
            "tier1": {
                "min": "0",
            },
            "tier2": {
                "min": "5000.00",
            },
            "tier3": {"min": "15000.00"},
        }
    ),
    "tiered_interest_rates": {
        "flag_key": {
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
    },
    "minimum_combined_balance_threshold": {
        "flag_key": {
            "UPPER_TIER": "3000",
            "MIDDLE_TIER": "4000",
            "LOWER_TIER": "5000",
        }
    },
    "minimum_deposit": "1",
    "maximum_balance": "10000",
    "maximum_daily_deposit": "5000",
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
    "maintenance_fee_monthly": {
        "flag_key": {
            "UPPER_TIER": "15",
            "MIDDLE_TIER": "10",
            "LOWER_TIER": "5",
        }
    },
    "promotional_maintenance_fee_monthly": {
        "flag_key": {
            "UPPER_TIER": "10",
            "MIDDLE_TIER": "5",
            "LOWER_TIER": "1",
        }
    },
    "fees_application_day": "1",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "tiered_minimum_balance_threshold": {
        "flag_key": {
            "UPPER_TIER": "25",
            "MIDDLE_TIER": "75",
            "LOWER_TIER": "100",
        }
    },
    "minimum_balance_fee": "0",
    "account_tier_names": {
        "flag_key": [
            "UPPER_TIER",
            "MIDDLE_TIER",
            "LOWER_TIER",
        ]
    },
    "automated_transfer_tag": "DEPOSIT_ACH_",
    "promotional_rates": {
        "flag_key": {
            "UPPER_TIER": {
                "tier1": "0.04",
                "tier2": "0.03",
                "tier3": "0.02",
            },
            "MIDDLE_TIER": {
                "tier1": "0.03",
                "tier2": "0.02",
                "tier3": "0.01",
            },
            "LOWER_TIER": {
                "tier1": "0.2",
                "tier2": "0.1",
                "tier3": "0",
            },
        }
    },
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
    "standard_overdraft_per_transaction_fee": "34",
    "standard_overdraft_daily_fee": "5",
    "standard_overdraft_fee_cap": "80",
    "savings_sweep_fee": "12",
    "savings_sweep_fee_cap": "2",
    "savings_sweep_transfer_unit": "50",
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
    "inactivity_fee_income_account": {
        "internal_account_key": INACTIVITY_FEE_INCOME_ACCOUNT,
    },
    "maintenance_fee_monthly": {
        "flag_key": {
            "UPPER_TIER": "15",
            "MIDDLE_TIER": "10",
            "LOWER_TIER": "5",
        }
    },
    "promotional_maintenance_fee_monthly": {
        "flag_key": {
            "UPPER_TIER": "10",
            "MIDDLE_TIER": "5",
            "LOWER_TIER": "1",
        }
    },
    "minimum_balance_threshold": {
        "flag_key": {
            "UPPER_TIER": "25",
            "MIDDLE_TIER": "75",
            "LOWER_TIER": "100",
        }
    },
    "minimum_combined_balance_threshold": {
        "flag_key": {
            "UPPER_TIER": "3000",
            "MIDDLE_TIER": "4000",
            "LOWER_TIER": "5000",
        }
    },
    "minimum_deposit_threshold": {
        "flag_key": {
            "UPPER_TIER": "10",
            "MIDDLE_TIER": "5",
            "LOWER_TIER": "1",
        }
    },
    "account_inactivity_fee": "0",
    "tier_names": {
        "flag_key": [
            "UPPER_TIER",
            "MIDDLE_TIER",
            "LOWER_TIER",
        ]
    },
    "minimum_balance_fee": "0",
    "fees_application_day": "1",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "maximum_daily_atm_withdrawal_limit": {
        "flag_key": {
            "UPPER_TIER": "5000",
            "MIDDLE_TIER": "2000",
            "LOWER_TIER": "1000",
        }
    },
    "transaction_code_to_type_map": dumps({"6011": "ATM withdrawal", "3123": "eCommerce"}),
    "transaction_types": dumps(["purchase", "ATM withdrawal", "transfer"]),
    "autosave_rounding_amount": "1.00",
    "optional_standard_overdraft_coverage": dumps(["ATM withdrawal", "eCommerce"]),
    "overdraft_protection_sweep_hour": "0",
    "overdraft_protection_sweep_minute": "1",
    "overdraft_protection_sweep_second": "0",
}

# second checking account template parameters used for savings_account_product tests
checking_account_template_params_savings_tests = {
    "denomination": "USD",
    "additional_denominations": dumps([]),
    "deposit_interest_application_frequency": "monthly",
    "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
    "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
    "interest_accrual_days_in_year": "365",
    "standard_overdraft_daily_fee": "5",
    "savings_sweep_fee": "0",
    "savings_sweep_fee_cap": "-1",
    "savings_sweep_transfer_unit": "0",
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
    "inactivity_fee_income_account": {
        "internal_account_key": INACTIVITY_FEE_INCOME_ACCOUNT,
    },
    "maintenance_fee_monthly": {"flag_key": {"LOWER_TIER": "0"}},
    "promotional_maintenance_fee_monthly": {"flag_key": {"LOWER_TIER": "0"}},
    "minimum_balance_threshold": {"flag_key": {"LOWER_TIER": "1500"}},
    "minimum_combined_balance_threshold": {"flag_key": {"LOWER_TIER": "5000"}},
    "minimum_deposit_threshold": {"flag_key": {"LOWER_TIER": "500"}},
    "account_inactivity_fee": "0",
    "tier_names": {
        "flag_key": [
            "UPPER_TIER",
            "MIDDLE_TIER",
            "LOWER_TIER",
        ]
    },
    "minimum_balance_fee": "0",
    "fees_application_day": "1",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "maximum_daily_atm_withdrawal_limit": {
        "flag_key": {
            "UPPER_TIER": "5000",
            "MIDDLE_TIER": "2000",
            "LOWER_TIER": "1000",
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

DEFAULT_CHECKING_CONTRACT = {
    "us_checking_account_v3": {
        "path": files.US_CHECKING_TEMPLATE,
        "template_params": checking_account_template_params,
        "supervisee_alias": "us_checking",
    },
}
DEFAULT_SAVINGS_CONTRACT = {
    "us_savings_account_v3": {
        "path": files.US_SAVINGS_TEMPLATE,
        "template_params": us_savings_account_template_params,
        "supervisee_alias": "us_savings",
    }
}
DEFAULT_CONTRACTS = {
    **DEFAULT_CHECKING_CONTRACT,
    **DEFAULT_SAVINGS_CONTRACT,
}

DEFAULT_SUPERVISORCONTRACTS = {"us_v3": {"path": files.US_SUPERVISOR_TEMPLATE}}

# Any Flag used in a CLU reference needs to be set up by the test, or the framework's id
# replacement mechanism will raise an exception. We need to include flag definition ids with a CLU
# dependency in smart contracts, supervisor smart contracts and workflows

COMMON_FLAG_DEFINITIONS = {
    "PROMOTIONAL_MAINTENANCE_FEE": (
        "library/us_products_v3/flag_definitions/promotional_maintenance_fee.resource.yaml"
    ),
}

US_SAVINGS_FLAG_DEFINITIONS = {
    "PROMOTIONAL_INTEREST_RATES": (
        "library/us_products_v3/flag_definitions/promotional_interest_rates.resource.yaml"
    ),
    **COMMON_FLAG_DEFINITIONS,
}

US_CHECKING_FLAG_DEFINITIONS = {
    "ACCOUNT_DORMANT": common_flag_definition_files.ACCOUNT_DORMANT,
    STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG: (
        "library/us_products_v3/flag_definitions/overdraft_transaction_coverage.resource.yaml"
    ),
    **COMMON_FLAG_DEFINITIONS,
}

APPLICATION_WORKFLOW_FLAG_DEFINITIONS = {
    # application workflow is aware of tiers
    "UPPER_TIER": common_flag_definition_files.UPPER_TIER,
    "MIDDLE_TIER": common_flag_definition_files.MIDDLE_TIER,
    "LOWER_TIER": common_flag_definition_files.LOWER_TIER,
}

# Useful for supervisor scenarios that include workflows and all products
ALL_FLAG_DEFINITIONS = {
    **APPLICATION_WORKFLOW_FLAG_DEFINITIONS,
    **US_CHECKING_FLAG_DEFINITIONS,
    **US_SAVINGS_FLAG_DEFINITIONS,
}
