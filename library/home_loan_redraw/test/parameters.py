# library
from library.home_loan_redraw.contracts.template import home_loan_redraw
from library.home_loan_redraw.test import accounts

TEST_DENOMINATION = "AUD"

default_instance: dict[str, str] = {
    home_loan_redraw.disbursement.PARAM_DEPOSIT_ACCOUNT: accounts.DEPOSIT,
    home_loan_redraw.disbursement.PARAM_PRINCIPAL: "800000",
    home_loan_redraw.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "11",
    home_loan_redraw.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
    home_loan_redraw.variable_rate.PARAM_VARIABLE_RATE_ADJUSTMENT: "0.0001",
}

default_template: dict[str, str] = {
    home_loan_redraw.PARAM_DENOMINATION: TEST_DENOMINATION,
    home_loan_redraw.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_HOUR: "0",
    home_loan_redraw.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_MINUTE: "1",
    home_loan_redraw.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_SECOND: "0",
    home_loan_redraw.interest_accrual.PARAM_ACCRUAL_PRECISION: "5",
    home_loan_redraw.interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_RECEIVABLE
    ),
    home_loan_redraw.interest_accrual.PARAM_DAYS_IN_YEAR: "365",
    home_loan_redraw.interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "0",
    home_loan_redraw.interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "0",
    home_loan_redraw.interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "0",
    home_loan_redraw.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTEREST_RECEIVED
    ),
    home_loan_redraw.interest_application.PARAM_APPLICATION_PRECISION: "2",
    home_loan_redraw.variable_rate.PARAM_VARIABLE_INTEREST_RATE: "0.0199",
    # this has to be set for sim purposes only. See TM-60389
    home_loan_redraw.variable_rate.PARAM_ANNUAL_INTEREST_RATE_CAP: "inf",
    # this has to be set for sim purposes only. See TM-60389
    home_loan_redraw.variable_rate.PARAM_ANNUAL_INTEREST_RATE_FLOOR: "-inf",
}
