# standard libs
from datetime import datetime

# common
import library.mortgage.constants.accounts as accounts

# required internal accounts dictionary
internal_accounts_tside = {
    "TSIDE_ASSET": [
        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    ],
    "TSIDE_LIABILITY": [
        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
        accounts.INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT,
        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
        accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT,
        accounts.DEPOSIT_ACCOUNT,
        accounts.INTERNAL_UPFRONT_FEE_INCOME_ACCOUNT,
    ],
}

# constants
DEFAULT_PENALTY_BLOCKING_FLAG = {"flag_key": ["REPAYMENT_HOLIDAY"]}
DEFAULT_DUE_AMOUNT_BLOCKING_FLAG = {"flag_key": ["REPAYMENT_HOLIDAY"]}
DEFAULT_DELINQUENCY_BLOCKING_FLAG = {"flag_key": ["REPAYMENT_HOLIDAY"]}
DEFAULT_DELINQUENCY_FLAG = {"flag_key": ["ACCOUNT_DELINQUENT"]}
DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG = {"flag_key": ["REPAYMENT_HOLIDAY"]}
DEFAULT_REPAYMENT_BLOCKING_FLAG = {"flag_key": ["REPAYMENT_HOLIDAY"]}

# constants for test_mortgage only
SCHEDULE_TAGS_DIR = "library/mortgage/account_schedule_tags/"
POSTING_BATCH_ACCEPTED = "POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED"

# constants for test_mortgage_product_schedules only
SCHEDULE_TAGS_DIR_SCHEDULE_TESTS = "library/mortgage/account_schedule_tags/schedules_tests/"
PAUSED_SCHEDULE_TAG = (
    "library/common/tests/e2e/account_schedule_tags/"
    "common_paused_account_schedule_tag.resource.yaml"
)

# By default all schedules are paused
DEFAULT_TAGS = {
    "MORTGAGE_ACCRUE_INTEREST_AST": PAUSED_SCHEDULE_TAG,
    "MORTGAGE_REPAYMENT_DAY_SCHEDULE_AST": PAUSED_SCHEDULE_TAG,
    "MORTGAGE_HANDLE_OVERPAYMENT_ALLOWANCE_AST": PAUSED_SCHEDULE_TAG,
    "MORTGAGE_CHECK_DELINQUENCY_AST": PAUSED_SCHEDULE_TAG,
}

AUSTRALIAN_MORTGAGE_ACCRUE_INTEREST_AST = "AUSTRALIAN_MORTGAGE_ACCRUE_INTEREST_AST"
AUSTRALIAN_MORTGAGE_DUE_AMOUNT_CALCULATION_AST = "AUSTRALIAN_MORTGAGE_DUE_AMOUNT_CALCULATION_AST"
AUSTRALIAN_MORTGAGE_CHECK_OVERDUE_AST = "AUSTRALIAN_MORTGAGE_CHECK_OVERDUE_AST"

AUSTRALIAN_DEFAULT_TAGS = {
    AUSTRALIAN_MORTGAGE_ACCRUE_INTEREST_AST: PAUSED_SCHEDULE_TAG,
    AUSTRALIAN_MORTGAGE_DUE_AMOUNT_CALCULATION_AST: PAUSED_SCHEDULE_TAG,
    AUSTRALIAN_MORTGAGE_CHECK_OVERDUE_AST: PAUSED_SCHEDULE_TAG,
}

mortgage_template_params = {
    "denomination": "GBP",
    "variable_interest_rate": "0.129971",
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
        "internal_account_key": accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    },
    "capitalised_interest_received_account": {
        "internal_account_key": accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
    },
    "interest_received_account": {
        "internal_account_key": accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
    },
    "penalty_interest_received_account": {
        "internal_account_key": accounts.INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT,
    },
    "late_repayment_fee_income_account": {
        "internal_account_key": accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
    },
    "overpayment_allowance_fee_income_account": {
        "internal_account_key": accounts.INTERNAL_OVERPAYMENT_FEE_INCOME_ACCOUNT,
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

mortgage_instance_params = {
    "total_term": "12",
    "fixed_interest_term": "12",
    "fixed_interest_rate": "0.034544",
    "overpayment_percentage": "0.1",
    "overpayment_fee_percentage": "0.05",
    "interest_only_term": "12",
    "principal": "100000",
    "repayment_day": "1",
    "deposit_account": accounts.DEPOSIT_ACCOUNT,
    "variable_rate_adjustment": "0.00",
    "mortgage_start_date": datetime.strftime(datetime.utcnow(), "%Y-%m-%d"),
}
