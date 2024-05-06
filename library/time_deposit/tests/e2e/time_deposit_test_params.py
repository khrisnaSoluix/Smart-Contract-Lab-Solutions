# constants for account names
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
DUMMY_CONTRA = "DUMMY_CONTRA"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
WITHDRAWAL_FEE_INCOME_ACCOUNT = "WITHDRAWAL_FEE_INCOME"

# required internal accounts dictionary
internal_accounts_tside = {
    "TSIDE_ASSET": [
        INTEREST_PAID_ACCOUNT,
    ],
    "TSIDE_LIABILITY": [
        ACCRUED_INTEREST_PAYABLE_ACCOUNT,
        DUMMY_CONTRA,
        WITHDRAWAL_FEE_INCOME_ACCOUNT,
    ],
}

# all internal account parameters should use a dictionary with key "internal account key"
# e.g. "accrued_interest_payable_account": {
#      "internal_account_key": ACCRUED_INTEREST_PAYABLE_ACCOUNT},

# time deposit parameters
td_instance_params = {
    "interest_application_frequency": "quarterly",
    "interest_application_day": "6",
    "gross_interest_rate": "0.145",
    "term_unit": "months",
    "term": "6",
    "deposit_period": "7",
    "grace_period": "0",
    "cool_off_period": "3",
    "fee_free_percentage_limit": "0",
    "withdrawal_fee": "0",
    "withdrawal_percentage_fee": "0",
    "period_end_hour": "0",
    "account_closure_period": "0",
    "auto_rollover_type": "no_rollover",
    "partial_principal_amount": "0",
    "rollover_interest_application_frequency": "quarterly",
    "rollover_interest_application_day": "6",
    "rollover_gross_interest_rate": "0.145",
    "rollover_term_unit": "months",
    "rollover_term": "6",
    "rollover_grace_period": "7",
    "rollover_period_end_hour": "0",
    "rollover_account_closure_period": "0",
}


td_template_params = {
    "denomination": "GBP",
    "interest_accrual_hour": "23",
    "interest_accrual_minute": "58",
    "interest_accrual_second": "59",
    "interest_application_hour": "23",
    "interest_application_minute": "59",
    "interest_application_second": "59",
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "minimum_first_deposit": "50",
    "maximum_balance": "1000",
    "single_deposit": "unlimited",
    "accrued_interest_payable_account": {
        "internal_account_key": ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    },
    "interest_paid_account": {
        "internal_account_key": INTEREST_PAID_ACCOUNT,
    },
}


td_template_params_2 = {
    "denomination": "GBP",
    "interest_accrual_hour": "23",
    "interest_accrual_minute": "58",
    "interest_accrual_second": "59",
    "interest_application_hour": "23",
    "interest_application_minute": "59",
    "interest_application_second": "59",
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "minimum_first_deposit": "100",
    "maximum_balance": "1000",
    "single_deposit": "single",
    "accrued_interest_payable_account": {"internal_account_key": ACCRUED_INTEREST_PAYABLE_ACCOUNT},
    "interest_paid_account": {
        "internal_account_key": INTEREST_PAID_ACCOUNT,
    },
}

instance_params_with_grace_period = {
    "interest_application_frequency": "quarterly",
    "interest_application_day": "6",
    "gross_interest_rate": "0.145",
    "term_unit": "months",
    "term": "12",
    "account_closure_period": "7",
    "period_end_hour": "21",
    "grace_period": "10",
    "cool_off_period": "0",
    "deposit_period": "0",
    "fee_free_percentage_limit": "0",
    "withdrawal_fee": "10",
    "withdrawal_percentage_fee": "0",
    "auto_rollover_type": "no_rollover",
    "partial_principal_amount": "0",
    "rollover_interest_application_frequency": "quarterly",
    "rollover_interest_application_day": "6",
    "rollover_gross_interest_rate": "0.145",
    "rollover_term_unit": "months",
    "rollover_term": "12",
    "rollover_period_end_hour": "21",
    "rollover_account_closure_period": "7",
    "rollover_grace_period": "12",
}

instance_params_with_cool_off_period = {
    "interest_application_frequency": "quarterly",
    "interest_application_day": "6",
    "gross_interest_rate": "0.145",
    "term_unit": "months",
    "term": "12",
    "account_closure_period": "7",
    "period_end_hour": "21",
    "grace_period": "0",
    "cool_off_period": "12",
    "deposit_period": "7",
    "fee_free_percentage_limit": "0",
    "withdrawal_fee": "10",
    "withdrawal_percentage_fee": "0",
    "auto_rollover_type": "no_rollover",
    "partial_principal_amount": "0",
    "rollover_interest_application_frequency": "quarterly",
    "rollover_interest_application_day": "6",
    "rollover_gross_interest_rate": "0.145",
    "rollover_term_unit": "months",
    "rollover_term": "12",
    "rollover_period_end_hour": "21",
    "rollover_account_closure_period": "7",
    "rollover_grace_period": "12",
}

instance_params_without_grace_and_cool_off_period = {
    "interest_application_frequency": "quarterly",
    "interest_application_day": "6",
    "gross_interest_rate": "0.145",
    "term_unit": "months",
    "term": "12",
    "account_closure_period": "7",
    "period_end_hour": "21",
    "grace_period": "0",
    "cool_off_period": "0",
    "deposit_period": "0",
    "fee_free_percentage_limit": "0",
    "withdrawal_fee": "10",
    "withdrawal_percentage_fee": "0",
    "auto_rollover_type": "no_rollover",
    "partial_principal_amount": "0",
    "rollover_interest_application_frequency": "quarterly",
    "rollover_interest_application_day": "6",
    "rollover_gross_interest_rate": "0.145",
    "rollover_term_unit": "months",
    "rollover_term": "12",
    "rollover_account_closure_period": "7",
    "rollover_period_end_hour": "21",
    "rollover_grace_period": "0",
}
