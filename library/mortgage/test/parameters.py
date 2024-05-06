# standard libs
from json import dumps

# library
import library.mortgage.contracts.template.mortgage as mortgage
from library.mortgage.test import accounts

TEST_DENOMINATION = "GBP"
DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE: list[str] = ["REPAYMENT_HOLIDAY"]
DELINQUENCY_FLAG_PARAMETER_VALUE: list[str] = ["ACCOUNT_DELINQUENT"]
DEFAULT_BLOCKING_FLAGS: str = dumps(DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE)
DEFAULT_DELINQUENCY_FLAGS: str = dumps(DELINQUENCY_FLAG_PARAMETER_VALUE)


mortgage_instance_params: dict[str, str] = {
    mortgage.PARAM_INTEREST_ONLY_TERM: "0",
    mortgage.disbursement.PARAM_DEPOSIT_ACCOUNT: accounts.DEPOSIT_ACCOUNT,
    mortgage.disbursement.PARAM_PRINCIPAL: "300000",
    mortgage.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "28",
    mortgage.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.01",
    mortgage.fixed_to_variable.PARAM_FIXED_INTEREST_TERM: "12",
    mortgage.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
    mortgage.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "-0.001",
}

mortgage_template_params: dict[str, str] = {
    mortgage.PARAM_DENOMINATION: TEST_DENOMINATION,
    # Late Repayment
    mortgage.PARAM_GRACE_PERIOD: "1",
    mortgage.PARAM_LATE_REPAYMENT_FEE: "15",
    mortgage.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: (
        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT
    ),
    # Delinquency check
    mortgage.PARAM_DELINQUENCY_FLAG: DEFAULT_DELINQUENCY_FLAGS,
    mortgage.PARAM_CHECK_DELINQUENCY_HOUR: "0",
    mortgage.PARAM_CHECK_DELINQUENCY_MINUTE: "0",
    mortgage.PARAM_CHECK_DELINQUENCY_SECOND: "2",
    # Penalty Interest
    mortgage.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "True",
    mortgage.PARAM_PENALTY_INCLUDES_BASE_RATE: "True",
    mortgage.PARAM_PENALTY_INTEREST_RATE: "0.24",
    mortgage.PARAM_PENALTY_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT
    ),
    # Early Repayment
    mortgage.PARAM_EARLY_REPAYMENT_FEE: "0",
    mortgage.PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT: (
        accounts.INTERNAL_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT
    ),
    mortgage.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_term",
    mortgage.overpayment_allowance.PARAM_CHECK_OVERPAYMENT_ALLOWANCE_HOUR: "0",
    mortgage.overpayment_allowance.PARAM_CHECK_OVERPAYMENT_ALLOWANCE_MINUTE: "3",
    mortgage.overpayment_allowance.PARAM_CHECK_OVERPAYMENT_ALLOWANCE_SECOND: "0",
    mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT: (
        accounts.INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT
    ),
    mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE: ("0.01"),
    mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE: ("0.05"),
    mortgage.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_HOUR: "0",
    mortgage.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_MINUTE: "1",
    mortgage.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_SECOND: "0",
    mortgage.interest_accrual.PARAM_ACCRUAL_PRECISION: "5",
    mortgage.interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    ),
    mortgage.interest_accrual.PARAM_DAYS_IN_YEAR: "365",
    mortgage.interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "0",
    mortgage.interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "0",
    mortgage.interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "1",
    mortgage.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT
    ),
    mortgage.interest_application.PARAM_APPLICATION_PRECISION: "2",
    mortgage.interest_capitalisation.PARAM_CAPITALISE_PENALTY_INTEREST: "False",
    mortgage.interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT
    ),
    mortgage.interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT
    ),
    mortgage.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.032",
    # this has to be set for sim purposes only. See TM-60389
    mortgage.variable_rate.PARAM_ANNUAL_INTEREST_RATE_CAP: "inf",
    # this has to be set for sim purposes only. See TM-60389
    mortgage.variable_rate.PARAM_ANNUAL_INTEREST_RATE_FLOOR: "-inf",
    mortgage.repayment_holiday.PARAM_DELINQUENCY_BLOCKING_FLAGS: DEFAULT_BLOCKING_FLAGS,
    mortgage.repayment_holiday.PARAM_DUE_AMOUNT_CALCULATION_BLOCKING_FLAGS: DEFAULT_BLOCKING_FLAGS,
    mortgage.repayment_holiday.PARAM_OVERDUE_AMOUNT_CALCULATION_BLOCKING_FLAGS: (
        DEFAULT_BLOCKING_FLAGS
    ),
    mortgage.repayment_holiday.PARAM_REPAYMENT_BLOCKING_FLAGS: DEFAULT_BLOCKING_FLAGS,
    mortgage.repayment_holiday.PARAM_PENALTY_BLOCKING_FLAGS: DEFAULT_BLOCKING_FLAGS,
}
