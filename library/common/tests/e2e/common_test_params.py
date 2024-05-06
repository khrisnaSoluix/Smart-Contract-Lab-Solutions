from json import dumps

# constants for account names
ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INT_RECEIVABLE"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
OVERDRAFT_FEE_INCOME_ACCOUNT = "OVERDRAFT_FEE_INCOME"
OVERDRAFT_FEE_RECEIVABLE_ACCOUNT = "OVERDRAFT_FEE_RECEIVABLE"
MAINTENANCE_FEE_INCOME_ACCOUNT = "MAINTENANCE_FEE_INCOME"
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
        INTEREST_RECEIVED_ACCOUNT,
        ACCRUED_INTEREST_PAYABLE_ACCOUNT,
        MAINTENANCE_FEE_INCOME_ACCOUNT,
        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
        ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
        INACTIVITY_FEE_INCOME_ACCOUNT,
        OVERDRAFT_FEE_INCOME_ACCOUNT,
        EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
    ],
}

# all internal account parameters should use a dictionary with key "internal account key"
# e.g. "accrued_interest_payable_account": {
#      "internal_account_key": ACCRUED_INTEREST_PAYABLE_ACCOUNT},

ca_template_params = {
    "denomination": "GBP",
    "additional_denominations": dumps(["USD", "EUR"]),
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
    "interest_free_buffer": dumps(
        {
            "CASA_TIER_UPPER": "500",
            "CASA_TIER_MIDDLE": "300",
            "CASA_TIER_LOWER": "50",
        }
    ),
    "overdraft_interest_free_buffer_days": dumps(
        {
            "CASA_TIER_UPPER": "-1",
            "CASA_TIER_MIDDLE": "21",
            "CASA_TIER_LOWER": "-1",
        }
    ),
    "unarranged_overdraft_fee": "5",
    "unarranged_overdraft_fee_cap": "80",
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
    "excess_withdrawal_fee_income_account": {
        "internal_account_key": EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
    },
    "maintenance_fee_annual": "0",
    "maintenance_fee_monthly": "0",
    "account_inactivity_fee": "0",
    "tier_names": dumps(
        [
            "CASA_TIER_UPPER",
            "CASA_TIER_MIDDLE",
            "CASA_TIER_LOWER",
        ]
    ),
    "minimum_balance_threshold": dumps(
        {
            "CASA_TIER_UPPER": "25",
            "CASA_TIER_MIDDLE": "75",
            "CASA_TIER_LOWER": "100",
        }
    ),
    "minimum_balance_fee": "0",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "maximum_daily_atm_withdrawal_limit": dumps(
        {
            "CASA_TIER_UPPER": "5000",
            "CASA_TIER_MIDDLE": "2000",
            "CASA_TIER_LOWER": "1000",
        }
    ),
    "transaction_code_to_type_map": dumps({"6011": "ATM withdrawal"}),
    "autosave_rounding_amount": "1.00",
    "monthly_withdrawal_limit": "-1",
    "reject_excess_withdrawals": "false",
    "excess_withdrawal_fee": "0",
}
