from json import dumps
from datetime import datetime

# constants for account names
DEPOSIT_ACCOUNT = "1"
ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INT_RECEIVABLE"
CAPITALISED_INTEREST_RECEIVED_ACCOUNT = "CAPITALISED_INT_RECEIVED"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
PENALTY_INTEREST_RECEIVED_ACCOUNT = "PENALTY_INTEREST_RECV"
LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "LATE_REPAYMENT_FEE_INCOME"
OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT = "OVERPAYMENT_ALLOWANCE_FEE"
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
MAINTENANCE_FEE_INCOME_ACCOUNT = "MAINTENANCE_FEE_INCOME"
EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT = "EXCESS_WITHDRAWAL_FEE_INC"
MINIMUM_BALANCE_FEE_INCOME_ACCOUNT = "MINIMUM_BALANCE_FEE_INCOME"
OVERDRAFT_FEE_INCOME_ACCOUNT = "OVERDRAFT_FEE_INCOME"
OVERDRAFT_FEE_RECEIVABLE_ACCOUNT = "OVERDRAFT_FEE_RECEIVABLE"
ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT = "ANNUAL_MAINTENANCE_FEE_INC"
INACTIVITY_FEE_INCOME_ACCOUNT = "INACTIVITY_FEE_INCOME"

# required internal accounts dictionary
internal_accounts_tside = {
    "TSIDE_ASSET": [
        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
        INTEREST_PAID_ACCOUNT,
        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
    ],
    "TSIDE_LIABILITY": [
        ACCRUED_INTEREST_PAYABLE_ACCOUNT,
        ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
        CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
        EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
        INACTIVITY_FEE_INCOME_ACCOUNT,
        INTEREST_RECEIVED_ACCOUNT,
        MAINTENANCE_FEE_INCOME_ACCOUNT,
        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
        OVERDRAFT_FEE_INCOME_ACCOUNT,
        PENALTY_INTEREST_RECEIVED_ACCOUNT,
        LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
        OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT,
        DEPOSIT_ACCOUNT,
    ],
}

# flag constants
DEFAULT_PENALTY_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DUE_AMOUNT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_FLAG = dumps(["ACCOUNT_DELINQUENT"])
DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_REPAYMENT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])


# constants used for easy access saver account
BALANCE_TIER_RANGES = dumps(
    {
        "tier1": {"min": "0"},
        "tier2": {"min": "15000.00"},
    }
)
TIERED_INTEREST_RATES = dumps(
    {
        "EASY_ACCESS_SAVER_TIER_UPPER": {"tier1": "0.02", "tier2": "0.015"},
        "EASY_ACCESS_SAVER_TIER_MIDDLE": {"tier1": "0.0125", "tier2": "0.01"},
        "EASY_ACCESS_SAVER_TIER_LOWER": {"tier1": "0.149", "tier2": "-0.1485"},
    }
)

TIERED_MIN_BALANCE_THRESHOLD = dumps(
    {
        "EASY_ACCESS_SAVER_TIER_UPPER": "25",
        "EASY_ACCESS_SAVER_TIER_MIDDLE": "75",
        "EASY_ACCESS_SAVER_TIER_LOWER": "100",
    }
)
ACCOUNT_TIER_NAMES = dumps(
    [
        "EASY_ACCESS_SAVER_TIER_UPPER",
        "EASY_ACCESS_SAVER_TIER_MIDDLE",
        "EASY_ACCESS_SAVER_TIER_LOWER",
    ]
)
ZERO_TIERED_INTEREST_RATES = dumps(
    {
        "EASY_ACCESS_SAVER_TIER_UPPER": {"tier1": "0", "tier2": "0"},
        "EASY_ACCESS_SAVER_TIER_MIDDLE": {"tier1": "0", "tier2": "0"},
        "EASY_ACCESS_SAVER_TIER_LOWER": {"tier1": "0", "tier2": "0"},
    }
)
NEGATIVE_TIERED_INTEREST_RATES = dumps(
    {
        "EASY_ACCESS_SAVER_TIER_UPPER": {"tier1": "-0.02", "tier2": "-0.015"},
        "EASY_ACCESS_SAVER_TIER_MIDDLE": {"tier1": "-0.0125", "tier2": "-0.01"},
        "EASY_ACCESS_SAVER_TIER_LOWER": {"tier1": "-0.149", "tier2": "-0.1485"},
    }
)
# mortgage instance parameters
default_mortgage_instance_params = {
    "fixed_interest_rate": "0.129971",
    "fixed_interest_term": "0",
    "total_term": "120",
    "overpayment_fee_percentage": "0.05",
    "interest_only_term": "0",
    "principal": "300000",
    "repayment_day": "12",
    "deposit_account": DEPOSIT_ACCOUNT,
    "overpayment_percentage": "0.1",
    "variable_rate_adjustment": "0",
    "mortgage_start_date": datetime.strftime(datetime.utcnow(), "%Y-%m-%d"),
}

# mortgage template parameters
default_mortgage_template_params = {
    "variable_interest_rate": "0.032",
    "denomination": "GBP",
    "late_repayment_fee": "15",
    "penalty_interest_rate": "0.24",
    "penalty_includes_base_rate": "True",
    "grace_period": "5",
    "penalty_blocking_flags": DEFAULT_PENALTY_BLOCKING_FLAG,
    "due_amount_blocking_flags": DEFAULT_DUE_AMOUNT_BLOCKING_FLAG,
    "delinquency_blocking_flags": DEFAULT_DELINQUENCY_BLOCKING_FLAG,
    "delinquency_flags": DEFAULT_DELINQUENCY_FLAG,
    "overdue_amount_blocking_flags": DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG,
    "repayment_blocking_flags": DEFAULT_REPAYMENT_BLOCKING_FLAG,
    "accrued_interest_receivable_account": {
        "internal_account_key": ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    },
    "capitalised_interest_received_account": {
        "internal_account_key": CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
    },
    "interest_received_account": {
        "internal_account_key": INTEREST_RECEIVED_ACCOUNT,
    },
    "penalty_interest_received_account": {
        "internal_account_key": PENALTY_INTEREST_RECEIVED_ACCOUNT,
    },
    "late_repayment_fee_income_account": {
        "internal_account_key": LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
    },
    "overpayment_allowance_fee_income_account": {
        "internal_account_key": OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT,
    },
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "overpayment_impact_preference": "reduce_term",
    "accrue_interest_hour": "0",
    "accrue_interest_minute": "0",
    "accrue_interest_second": "1",
    "check_delinquency_hour": "0",
    "check_delinquency_minute": "0",
    "check_delinquency_second": "2",
    "repayment_hour": "0",
    "repayment_minute": "1",
    "repayment_second": "0",
    "overpayment_hour": "0",
    "overpayment_minute": "0",
    "overpayment_second": "0",
}
# mortgage parameters for offset mortgage
default_new_mortgage_params_for_offset_mortgage = {
    "new_mortgage_fixed_interest_rate": "0.0275",
    "new_mortgage_overpayment_percentage": "0.1",
    "new_mortgage_overpayment_fee_percentage": "0.01",
    "new_mortgage_fixed_interest_term": "0",
    "new_mortgage_total_term": "12",
    "new_mortgage_principal": "100000",
    "new_mortgage_repayment_day": "22",
    "new_mortgage_deposit_account": "1",
    "new_mortgage_variable_rate_adjustment": "0",
}

# current account template parameters
default_ca_template_params = {
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
            "CURRENT_ACCOUNT_TIER_UPPER": "500",
            "CURRENT_ACCOUNT_TIER_MIDDLE": "300",
            "CURRENT_ACCOUNT_TIER_LOWER": "50",
        }
    ),
    "overdraft_interest_free_buffer_days": dumps(
        {
            "CURRENT_ACCOUNT_TIER_UPPER": "-1",
            "CURRENT_ACCOUNT_TIER_MIDDLE": "21",
            "CURRENT_ACCOUNT_TIER_LOWER": "-1",
        }
    ),
    "unarranged_overdraft_fee": "5",
    "unarranged_overdraft_fee_cap": "80",
    "interest_application_hour": "0",
    "interest_application_minute": "1",
    "interest_application_second": "0",
    "interest_accrual_hour": "0",
    "interest_accrual_minute": "0",
    "interest_accrual_second": "0",
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
    "maintenance_fee_monthly": "0",
    "account_inactivity_fee": "0",
    "account_tier_names": dumps(
        [
            "CURRENT_ACCOUNT_TIER_UPPER",
            "CURRENT_ACCOUNT_TIER_MIDDLE",
            "CURRENT_ACCOUNT_TIER_LOWER",
        ]
    ),
    "minimum_balance_threshold": dumps(
        {
            "CURRENT_ACCOUNT_TIER_UPPER": "25",
            "CURRENT_ACCOUNT_TIER_MIDDLE": "75",
            "CURRENT_ACCOUNT_TIER_LOWER": "100",
        }
    ),
    "minimum_balance_fee": "0",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "maximum_daily_atm_withdrawal_limit": dumps(
        {
            "CURRENT_ACCOUNT_TIER_UPPER": "5000",
            "CURRENT_ACCOUNT_TIER_MIDDLE": "2000",
            "CURRENT_ACCOUNT_TIER_LOWER": "1000",
        }
    ),
    "transaction_code_to_type_map": dumps({"6011": "ATM withdrawal"}),
    "autosave_rounding_amount": "1.00",
}

# current account instance parameters
default_ca_instance_params = {
    "arranged_overdraft_limit": "1000",
    "unarranged_overdraft_limit": "2000",
    "interest_application_day": "1",
    "daily_atm_withdrawal_limit": "1000",
}

default_ca_template_params = {
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
    "account_tier_names": dumps(
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
    "maximum_daily_atm_withdrawal_limit": {
        "flag_key": {
            "CASA_TIER_UPPER": "5000",
            "CASA_TIER_MIDDLE": "2000",
            "CASA_TIER_LOWER": "1000",
        }
    },
    "transaction_code_to_type_map": dumps({"6011": "ATM withdrawal"}),
    "autosave_rounding_amount": "1.00",
    "monthly_withdrawal_limit": "-1",
    "reject_excess_withdrawals": "false",
    "excess_withdrawal_fee": "0",
}

# current account instance parameters
default_ca_instance_params = {
    "arranged_overdraft_limit": "1000",
    "unarranged_overdraft_limit": "2000",
    "interest_application_day": "1",
    "daily_atm_withdrawal_limit": "1000",
}

default_eas_template_params = {
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
    "account_tier_names": {"flag_key": ["CASA_TIER_UPPER", "CASA_TIER_MIDDLE", "CASA_TIER_LOWER"]},
    "minimum_balance_threshold": {
        "flag_key": {
            "CASA_TIER_UPPER": "25",
            "CASA_TIER_MIDDLE": "75",
            "CASA_TIER_LOWER": "100",
        }
    },
    "minimum_balance_fee": "0",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "maximum_daily_atm_withdrawal_limit": {
        "flag_key": {
            "CASA_TIER_UPPER": "5000",
            "CASA_TIER_MIDDLE": "2000",
            "CASA_TIER_LOWER": "1000",
        }
    },
    "transaction_code_to_type_map": dumps({"6011": "ATM withdrawal"}),
    "monthly_withdrawal_limit": "-1",
    "reject_excess_withdrawals": "false",
    "excess_withdrawal_fee": "0",
}

default_eas_instance_params = {"interest_application_day": "1"}
