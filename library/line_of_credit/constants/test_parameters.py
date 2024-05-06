# standard libs
import json
from datetime import datetime, timezone

# library
import library.line_of_credit.constants.accounts as accounts
import library.line_of_credit.contracts.template.drawdown_loan as drawdown_loan
import library.line_of_credit.contracts.template.line_of_credit as line_of_credit

# inception sdk
from inception_sdk.test_framework.common.constants import DEFAULT_DENOMINATION

REPAYMENT_HOLIDAY = line_of_credit.repayment_holiday.REPAYMENT_HOLIDAY

default_simulation_start_date = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)

# these addresses are longer than 32 characters so they need a shorter name for e2e tests
E2E_ACCRUED_INT_RECEIVABLE = "ACCRUED_INT_RECEIVABLE"
E2E_PENALTY_INTEREST_INCOME = "PENALTY_INT_INCOME"
E2E_LATE_REPAYMENT_INCOME = "LATE_REPAYMENT_FEE_INCOME"

internal_accounts_tside = {
    "TSIDE_ASSET": ["DUMMY_CONTRA", E2E_ACCRUED_INT_RECEIVABLE],
    "TSIDE_LIABILITY": [
        "1",
        accounts.DEPOSIT_ACCOUNT,
        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT,
        E2E_PENALTY_INTEREST_INCOME,
        E2E_LATE_REPAYMENT_INCOME,
        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT,
    ],
}


def replace_internal_account_with_dict_for_e2e(param_dict: dict) -> dict:
    """
    used for the e2e tests where the internal_account_key is needed
    """
    if drawdown_loan.interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT in param_dict:
        param_dict[
            drawdown_loan.interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
        ] = E2E_ACCRUED_INT_RECEIVABLE
    if drawdown_loan.PARAM_PENALTY_INTEREST_INCOME_ACCOUNT in param_dict:
        param_dict[
            drawdown_loan.PARAM_PENALTY_INTEREST_INCOME_ACCOUNT
        ] = E2E_PENALTY_INTEREST_INCOME
    if line_of_credit.late_repayment.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT in param_dict:
        param_dict[
            line_of_credit.late_repayment.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT
        ] = E2E_LATE_REPAYMENT_INCOME
    return {
        param: {"internal_account_key": value} if "_account" in param else value
        for param, value in param_dict.items()
    }


# default parameters to be used in test files
drawdown_loan_instance_params: dict[str, str] = {
    drawdown_loan.disbursement.PARAM_PRINCIPAL: "1000",
    drawdown_loan.disbursement.PARAM_DEPOSIT_ACCOUNT: accounts.DEPOSIT_ACCOUNT,
    drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.149",
    drawdown_loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
    drawdown_loan.PARAM_LOC_ACCOUNT_ID: "LINE_OF_CREDIT_ACCOUNT_0",
}

drawdown_loan_template_params: dict[str, str] = {
    drawdown_loan.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
    drawdown_loan.interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_RECEIVABLE
    ),
    drawdown_loan.interest_accrual.PARAM_DAYS_IN_YEAR: "365",
    drawdown_loan.interest_accrual.PARAM_ACCRUAL_PRECISION: "5",
    drawdown_loan.interest_application.PARAM_APPLICATION_PRECISION: "2",
    drawdown_loan.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT
    ),
    drawdown_loan.PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE: "True",
    drawdown_loan.PARAM_PENALTY_INTEREST_INCOME_ACCOUNT: (
        accounts.INTERNAL_PENALTY_INTEREST_INCOME_ACCOUNT
    ),
    drawdown_loan.PARAM_PENALTY_INTEREST_RATE: "0.05",
    drawdown_loan.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0.05",
}

loc_instance_params: dict[str, str] = {
    line_of_credit.credit_limit.PARAM_CREDIT_LIMIT: "5000",
    line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "5",
}

loc_template_params: dict[str, str] = {
    line_of_credit.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
    line_of_credit.credit_limit.PARAM_CREDIT_LIMIT_APPLICABLE_PRINCIPAL: "outstanding",
    line_of_credit.maximum_outstanding_loans.PARAM_MAXIMUM_NUMBER_OF_OUTSTANDING_LOANS: "6",
    line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_HOUR: "0",
    line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_MINUTE: "0",
    line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_SECOND: "2",
    line_of_credit.interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "0",
    line_of_credit.interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "0",
    line_of_credit.interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "0",
    line_of_credit.maximum_loan_principal.PARAM_MAXIMUM_LOAN_PRINCIPAL: "1000",
    line_of_credit.minimum_loan_principal.PARAM_MINIMUM_LOAN_PRINCIPAL: "50",
    line_of_credit.overdue.PARAM_CHECK_OVERDUE_HOUR: "0",
    line_of_credit.overdue.PARAM_CHECK_OVERDUE_MINUTE: "0",
    line_of_credit.overdue.PARAM_CHECK_OVERDUE_SECOND: "2",
    line_of_credit.overdue.PARAM_REPAYMENT_PERIOD: "7",
    line_of_credit.late_repayment.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: (
        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT
    ),
    line_of_credit.late_repayment.PARAM_LATE_REPAYMENT_FEE: "25",
    line_of_credit.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0.05",
    line_of_credit.overpayment.PARAM_OVERPAYMENT_FEE_INCOME_ACCOUNT: (
        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT
    ),
    line_of_credit.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_term",
    line_of_credit.repayment_holiday.PARAM_INTEREST_ACCRUAL_BLOCKING_FLAGS: json.dumps(
        [REPAYMENT_HOLIDAY]
    ),
    line_of_credit.repayment_holiday.PARAM_REPAYMENT_BLOCKING_FLAGS: json.dumps(
        [REPAYMENT_HOLIDAY]
    ),
    line_of_credit.repayment_holiday.PARAM_DUE_AMOUNT_CALCULATION_BLOCKING_FLAGS: json.dumps(
        [REPAYMENT_HOLIDAY]
    ),
    line_of_credit.repayment_holiday.PARAM_OVERDUE_AMOUNT_CALCULATION_BLOCKING_FLAGS: json.dumps(
        [REPAYMENT_HOLIDAY]
    ),
    line_of_credit.repayment_holiday.PARAM_DELINQUENCY_BLOCKING_FLAGS: json.dumps(
        [REPAYMENT_HOLIDAY]
    ),
    line_of_credit.repayment_holiday.PARAM_PENALTY_BLOCKING_FLAGS: json.dumps([REPAYMENT_HOLIDAY]),
    line_of_credit.repayment_holiday.PARAM_NOTIFICATION_BLOCKING_FLAGS: json.dumps(
        [REPAYMENT_HOLIDAY]
    ),
    line_of_credit.delinquency.PARAM_GRACE_PERIOD: "2",
    line_of_credit.delinquency.PARAM_CHECK_DELINQUENCY_HOUR: "0",
    line_of_credit.delinquency.PARAM_CHECK_DELINQUENCY_MINUTE: "1",
    line_of_credit.delinquency.PARAM_CHECK_DELINQUENCY_SECOND: "0",
}


e2e_drawdown_loan_instance_params = replace_internal_account_with_dict_for_e2e(
    drawdown_loan_instance_params.copy()
)
e2e_drawdown_loan_template_params = replace_internal_account_with_dict_for_e2e(
    drawdown_loan_template_params.copy()
)
e2e_loc_instance_params = replace_internal_account_with_dict_for_e2e(loc_instance_params.copy())
e2e_loc_template_params = replace_internal_account_with_dict_for_e2e(loc_template_params.copy())
