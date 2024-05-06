# standard libs
from datetime import datetime

# constants for account names
ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INT_RECEIVABLE"
CAPITALISED_INTEREST_RECEIVED_ACCOUNT = "CAPITALISED_INTEREST_REC"
CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT = "CAPITALISED_INT_RECEIVABLE"
CAPITALISED_PENALTIES_RECEIVED_ACCOUNT = "CAPITALISED_PENALTIES_REC"
DEPOSIT_ACCOUNT = "1"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "LATE_REPAYMENT_FEE_INCOME"
OVERPAYMENT_FEE_INCOME_ACCOUNT = "OVERPAYMENT_FEE_INCOME"
PENALTY_INTEREST_RECEIVED_ACCOUNT = "PENALTY_INTEREST_REC"
UPFRONT_FEE_INCOME_ACCOUNT = "UPFRONT_FEE_INCOME"

# required internal accounts dictionary
internal_accounts_tside = {
    "TSIDE_ASSET": [
        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
        CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT,
    ],
    "TSIDE_LIABILITY": [
        DEPOSIT_ACCOUNT,
        CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
        CAPITALISED_PENALTIES_RECEIVED_ACCOUNT,
        UPFRONT_FEE_INCOME_ACCOUNT,
        LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
        OVERPAYMENT_FEE_INCOME_ACCOUNT,
        PENALTY_INTEREST_RECEIVED_ACCOUNT,
        INTEREST_RECEIVED_ACCOUNT,
    ],
}

# constants
POSTING_BATCH_ACCEPTED = "POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED"
DEFAULT_PENALTY_BLOCKING_FLAG = {"flag_key": ["REPAYMENT_HOLIDAY"]}
DEFAULT_DUE_AMOUNT_BLOCKING_FLAG = {"flag_key": ["REPAYMENT_HOLIDAY"]}
DEFAULT_DELINQUENCY_BLOCKING_FLAG = {"flag_key": ["REPAYMENT_HOLIDAY"]}
DEFAULT_DELINQUENCY_FLAG = {"flag_key": ["ACCOUNT_DELINQUENT"]}
DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG = {"flag_key": ["ACCOUNT_DELINQUENT"]}
DEFAULT_REPAYMENT_BLOCKING_FLAG = {"flag_key": ["ACCOUNT_DELINQUENT"]}

# constants used only for schedules test
SCHEDULE_TAGS_DIR = "library/loan/account_schedule_tags/schedules_tests/"
PAUSED_SCHEDULE_TAG = SCHEDULE_TAGS_DIR + "paused_tag.resource.yaml"

# By default all schedules are paused
DEFAULT_TAGS = {
    "LOAN_ACCRUE_INTEREST_AST": PAUSED_SCHEDULE_TAG,
    "LOAN_REPAYMENT_DAY_SCHEDULE_AST": PAUSED_SCHEDULE_TAG,
    "LOAN_BALLOON_PAYMENT_SCHEDULE_AST": PAUSED_SCHEDULE_TAG,
    "LOAN_CHECK_DELINQUENCY_AST": PAUSED_SCHEDULE_TAG,
    "LOAN_CHECK_OVERDUE_AST": PAUSED_SCHEDULE_TAG,
}


# loan instance parameters
loan_instance_params = {
    "total_term": "12",
    "fixed_interest_loan": "True",
    "fixed_interest_rate": "0.034544",
    "upfront_fee": "0",
    "amortise_upfront_fee": "True",
    "principal": "1000",
    "repayment_day": "1",
    "deposit_account": DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.00",
    "loan_start_date": datetime.strftime(datetime.utcnow(), "%Y-%m-%d"),
    "repayment_holiday_impact_preference": "increase_emi",
    "capitalise_late_repayment_fee": "False",
    "interest_accrual_rest_type": "daily",
}

loan_instance_params_balloon_loan = loan_instance_params.copy()
loan_instance_params_balloon_loan["balloon_payment_days_delta"] = "0"


# loan template parameters
loan_template_params = {
    "denomination": "GBP",
    "variable_interest_rate": "0.129971",
    "annual_interest_rate_cap": "1.0",
    "annual_interest_rate_floor": "0.0",
    "late_repayment_fee": "15",
    "penalty_interest_rate": "0.24",
    "capitalise_penalty_interest": "False",
    "penalty_includes_base_rate": "True",
    "repayment_period": "10",
    "grace_period": "5",
    "penalty_compounds_overdue_interest": "True",
    "accrue_interest_on_due_principal": "False",
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
    "capitalised_interest_receivable_account": {
        "internal_account_key": CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT
    },
    "capitalised_penalties_received_account": {
        "internal_account_key": CAPITALISED_PENALTIES_RECEIVED_ACCOUNT,
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
    "overpayment_fee_income_account": {
        "internal_account_key": OVERPAYMENT_FEE_INCOME_ACCOUNT,
    },
    "overpayment_fee_rate": "0.05",
    "upfront_fee_income_account": {
        "internal_account_key": UPFRONT_FEE_INCOME_ACCOUNT,
    },
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "amortisation_method": "declining_principal",
    "capitalise_no_repayment_accrued_interest": "no_capitalisation",
    "overpayment_impact_preference": "reduce_term",
    "accrue_interest_hour": "0",
    "accrue_interest_minute": "0",
    "accrue_interest_second": "1",
    "check_overdue_hour": "0",
    "check_overdue_minute": "0",
    "check_overdue_second": "2",
    "check_delinquency_hour": "0",
    "check_delinquency_minute": "0",
    "check_delinquency_second": "2",
    "repayment_hour": "0",
    "repayment_minute": "1",
    "repayment_second": "0",
}

loan_balloon_min_repayment_template_params = loan_template_params.copy()
loan_balloon_min_repayment_template_params[
    "amortisation_method"
] = "minimum_repayment_with_balloon_payment"
loan_balloon_min_repayment_instance_params = loan_instance_params.copy()
loan_balloon_min_repayment_instance_params["balloon_payment_days_delta"] = "0"

loan_balloon_no_repayment_template_params = loan_template_params.copy()
loan_balloon_no_repayment_template_params["amortisation_method"] = "no_repayment"
loan_balloon_no_repayment_instance_params = loan_instance_params.copy()

loan_balloon_interest_only_template_params = loan_template_params.copy()
loan_balloon_interest_only_template_params["amortisation_method"] = "interest_only"
loan_balloon_interest_only_instance_params = loan_instance_params.copy()
