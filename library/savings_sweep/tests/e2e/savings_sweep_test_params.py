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
        INACTIVITY_FEE_INCOME_ACCOUNT,
        INTEREST_RECEIVED_ACCOUNT,
        ACCRUED_INTEREST_PAYABLE_ACCOUNT,
        EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
        OVERDRAFT_FEE_INCOME_ACCOUNT,
        MAINTENANCE_FEE_INCOME_ACCOUNT,
        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
    ],
}

# all internal account parameters should use a dictionary with key "internal account key"
# e.g. "accrued_interest_payable_account": {
#      "internal_account_key": ACCRUED_INTEREST_PAYABLE_ACCOUNT},

# savings template parameters
savings_template_params = {
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
    },
    "minimum_combined_balance_threshold": {
        "flag_key": {
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "3000",
            "US_SAVINGS_ACCOUNT_TIER_MIDDLE": "4000",
            "US_SAVINGS_ACCOUNT_TIER_LOWER": "5000",
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
    "maintenance_fee_annual": "0",
    "maintenance_fee_monthly": {
        "flag_key": {
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "15",
            "US_SAVINGS_ACCOUNT_TIER_MIDDLE": "10",
            "US_SAVINGS_ACCOUNT_TIER_LOWER": "5",
        }
    },
    "promotional_maintenance_fee_monthly": {
        "flag_key": {
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "10",
            "US_SAVINGS_ACCOUNT_TIER_MIDDLE": "5",
            "US_SAVINGS_ACCOUNT_TIER_LOWER": "1",
        }
    },
    "fees_application_day": "1",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "tiered_minimum_balance_threshold": {
        "flag_key": {
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "25",
            "US_SAVINGS_ACCOUNT_TIER_MIDDLE": "75",
            "US_SAVINGS_ACCOUNT_TIER_LOWER": "100",
        }
    },
    "minimum_balance_fee": "0",
    "account_tier_names": {
        "flag_key": [
            "US_SAVINGS_ACCOUNT_TIER_UPPER",
            "US_SAVINGS_ACCOUNT_TIER_MIDDLE",
            "US_SAVINGS_ACCOUNT_TIER_LOWER",
        ]
    },
    "automated_transfer_tag": "DEPOSIT_ACH_",
    "promotional_rates": {
        "flag_key": {
            "US_SAVINGS_ACCOUNT_TIER_UPPER": {
                "tier1": "0.04",
                "tier2": "0.03",
                "tier3": "0.02",
            },
            "US_SAVINGS_ACCOUNT_TIER_MIDDLE": {
                "tier1": "0.03",
                "tier2": "0.02",
                "tier3": "0.01",
            },
            "US_SAVINGS_ACCOUNT_TIER_LOWER": {
                "tier1": "0.2",
                "tier2": "0.1",
                "tier3": "0",
            },
        }
    },
}

# checking account template parameters
ca_template_params = {
    "denomination": "USD",
    "additional_denominations": dumps([]),
    "deposit_interest_application_frequency": "monthly",
    "deposit_tier_ranges": dumps(
        {
            "tier1": {"min": "0"},
            "tier2": {"min": "3000.00"},
            "tier3": {"min": "5000.00"},
            "tier4": {"min": "7500.00"},
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
    "annual_maintenance_fee_income_account": {
        "internal_account_key": ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
    },
    "inactivity_fee_income_account": {
        "internal_account_key": INACTIVITY_FEE_INCOME_ACCOUNT,
    },
    "maintenance_fee_annual": "0",
    "maintenance_fee_monthly": {
        "flag_key": {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "15",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "10",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "5",
        }
    },
    "promotional_maintenance_fee_monthly": {
        "flag_key": {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "10",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "5",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "1",
        }
    },
    "minimum_balance_threshold": {
        "flag_key": {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "25",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "75",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "100",
        }
    },
    "minimum_combined_balance_threshold": {
        "flag_key": {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "3000",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "4000",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "5000",
        }
    },
    "minimum_deposit_threshold": {
        "flag_key": {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "10",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "5",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "1",
        }
    },
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

# checking account instance parameters
ca_instance_params = {
    "fee_free_overdraft_limit": "1000",
    "standard_overdraft_limit": "2000",
    "interest_application_day": "1",
    "daily_atm_withdrawal_limit": "1000",
}
