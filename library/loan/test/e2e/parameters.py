# library
import library.loan.contracts.template.loan as loan
import library.loan.test.e2e.accounts as accounts
import library.loan.test.parameters as parameters

# inception sdk
from inception_sdk.test_framework.endtoend.contracts_helper import prepare_parameters_for_e2e

e2e_internal_account_params = {
    loan.early_repayment.PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT: (
        accounts.INTERNAL_EARLY_REPAYMENT_FEE_INCOME
    ),
    loan.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME,
    loan.PARAM_PENALTY_INTEREST_RECEIVED_ACCOUNT: accounts.INTERNAL_PENALTY_INTEREST_RECEIVED,
    loan.PARAM_UPFRONT_FEE_INTERNAL_ACCOUNT: accounts.INTERNAL_UPFRONT_FEE_INCOME,
    loan.interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE
    ),
    loan.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: accounts.INTERNAL_INTEREST_RECEIVED,
    loan.interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE
    ),
    loan.interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED
    ),
}

e2e_flag_params = {
    loan.PARAM_DELINQUENCY_FLAG: parameters.DELINQUENCY_FLAG_PARAMETER_VALUE,
    loan.repayment_holiday.PARAM_DELINQUENCY_BLOCKING_FLAGS: (
        parameters.DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE
    ),
    loan.repayment_holiday.PARAM_DUE_AMOUNT_CALCULATION_BLOCKING_FLAGS: (
        parameters.DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE
    ),
    loan.repayment_holiday.PARAM_OVERDUE_AMOUNT_CALCULATION_BLOCKING_FLAGS: (
        parameters.DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE
    ),
    loan.repayment_holiday.PARAM_PENALTY_BLOCKING_FLAGS: (
        parameters.DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE
    ),
    loan.repayment_holiday.PARAM_REPAYMENT_BLOCKING_FLAGS: (
        parameters.DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE
    ),
}

default_instance = parameters.loan_instance_params
default_template = prepare_parameters_for_e2e(
    parameters=parameters.loan_template_params,
    internal_account_param_mapping=e2e_internal_account_params,
    flag_param_mapping=e2e_flag_params,
)
