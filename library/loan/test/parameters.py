# standard libs
from json import dumps

# library
import library.loan.contracts.template.loan as loan
from library.loan.test import accounts

TEST_DENOMINATION = "GBP"
DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE: list[str] = ["REPAYMENT_HOLIDAY"]
DELINQUENCY_FLAG_PARAMETER_VALUE: list[str] = ["ACCOUNT_DELINQUENT"]
DEFAULT_BLOCKING_FLAGS: str = dumps(DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE)
DEFAULT_DELINQUENCY_FLAGS: str = dumps(DELINQUENCY_FLAG_PARAMETER_VALUE)


loan_instance_params: dict[str, str] = {
    # Accrual Rest
    loan.PARAM_INTEREST_ACCRUAL_REST_TYPE: "daily",
    # Upfront Fee
    loan.PARAM_UPFRONT_FEE: "0",
    loan.PARAM_AMORTISE_UPFRONT_FEE: "False",
    # Late repayment Fee
    loan.PARAM_CAPITALISE_LATE_REPAYMENT_FEE: "False",
    # Fixed Rate
    loan.PARAM_FIXED_RATE_LOAN: "False",
    loan.disbursement.PARAM_DEPOSIT_ACCOUNT: accounts.DEPOSIT,
    loan.disbursement.PARAM_PRINCIPAL: "3000",
    loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "28",
    loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.01",
    loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
    loan.repayment_holiday.PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE: (
        loan.repayment_holiday.INCREASE_EMI
    ),
    loan.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "-0.001",
}

loan_template_params: dict[str, str] = {
    loan.PARAM_DENOMINATION: TEST_DENOMINATION,
    loan.PARAM_AMORTISATION_METHOD: "declining_principal",
    loan.PARAM_ACCRUE_ON_DUE_PRINCIPAL: "False",
    loan.PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST: "no_capitalisation",
    # Late Repayment
    loan.PARAM_GRACE_PERIOD: "1",
    loan.PARAM_LATE_REPAYMENT_FEE: "10",
    loan.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME,
    # Delinquency check
    loan.PARAM_DELINQUENCY_FLAG: DEFAULT_DELINQUENCY_FLAGS,
    loan.PARAM_CHECK_DELINQUENCY_HOUR: "0",
    loan.PARAM_CHECK_DELINQUENCY_MINUTE: "0",
    loan.PARAM_CHECK_DELINQUENCY_SECOND: "2",
    # Penalty Interest
    loan.PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST: "True",
    loan.PARAM_PENALTY_INCLUDES_BASE_RATE: "True",
    loan.PARAM_PENALTY_INTEREST_RATE: "0.24",
    loan.PARAM_PENALTY_INTEREST_RECEIVED_ACCOUNT: accounts.INTERNAL_PENALTY_INTEREST_RECEIVED,
    # Upfront Fee
    loan.PARAM_UPFRONT_FEE_INTERNAL_ACCOUNT: accounts.INTERNAL_UPFRONT_FEE_INCOME,
    loan.early_repayment.PARAM_EARLY_REPAYMENT_FEE_RATE: "0",
    loan.early_repayment.PARAM_EARLY_REPAYMENT_FLAT_FEE: "0",
    loan.early_repayment.PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT: (
        accounts.INTERNAL_EARLY_REPAYMENT_FEE_INCOME
    ),
    loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_HOUR: "0",
    loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_MINUTE: "1",
    loan.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_SECOND: "0",
    loan.interest_accrual.PARAM_ACCRUAL_PRECISION: "5",
    loan.interest_accrual.PARAM_DAYS_IN_YEAR: "365",
    loan.interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "0",
    loan.interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "0",
    loan.interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "1",
    loan.interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE
    ),
    loan.interest_application.PARAM_APPLICATION_PRECISION: "2",
    loan.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: accounts.INTERNAL_INTEREST_RECEIVED,
    loan.interest_capitalisation.PARAM_CAPITALISE_PENALTY_INTEREST: "False",
    loan.interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE
    ),
    loan.interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED
    ),
    loan.interest_capitalisation.PARAM_CAPITALISED_PENALTIES_RECEIVED_ACCOUNT: (
        accounts.INTERNAL_CAPITALISED_PENALTIES_RECEIVED
    ),
    loan.overdue.PARAM_REPAYMENT_PERIOD: "7",
    loan.overdue.PARAM_CHECK_OVERDUE_HOUR: "0",
    loan.overdue.PARAM_CHECK_OVERDUE_MINUTE: "0",
    loan.overdue.PARAM_CHECK_OVERDUE_SECOND: "2",
    loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0.05",
    loan.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_term",
    loan.overpayment.PARAM_OVERPAYMENT_FEE_INCOME_ACCOUNT: accounts.INTERNAL_OVERPAYMENT_FEE_INCOME,
    loan.repayment_holiday.PARAM_DELINQUENCY_BLOCKING_FLAGS: DEFAULT_BLOCKING_FLAGS,
    loan.repayment_holiday.PARAM_DUE_AMOUNT_CALCULATION_BLOCKING_FLAGS: DEFAULT_BLOCKING_FLAGS,
    loan.repayment_holiday.PARAM_OVERDUE_AMOUNT_CALCULATION_BLOCKING_FLAGS: (
        DEFAULT_BLOCKING_FLAGS
    ),
    loan.repayment_holiday.PARAM_REPAYMENT_BLOCKING_FLAGS: DEFAULT_BLOCKING_FLAGS,
    loan.repayment_holiday.PARAM_PENALTY_BLOCKING_FLAGS: DEFAULT_BLOCKING_FLAGS,
    loan.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.032",
    # this has to be set for sim purposes only. See TM-60389
    loan.variable_rate.PARAM_ANNUAL_INTEREST_RATE_CAP: "inf",
    # this has to be set for sim purposes only. See TM-60389
    loan.variable_rate.PARAM_ANNUAL_INTEREST_RATE_FLOOR: "-inf",
}
