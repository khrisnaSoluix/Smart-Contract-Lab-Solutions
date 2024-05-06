# library
import library.mortgage.contracts.template.mortgage as mortgage
import library.mortgage.test.e2e.accounts as accounts
import library.mortgage.test.parameters as parameters

# inception sdk
from inception_sdk.test_framework.endtoend.contracts_helper import prepare_parameters_for_e2e

e2e_internal_account_params = {
    mortgage.PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT: accounts.E2E_EARLY_REPAYMENT_FEE_INCOME,
    mortgage.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: accounts.E2E_LATE_REPAYMENT_FEE_INCOME,
    mortgage.PARAM_PENALTY_INTEREST_RECEIVED_ACCOUNT: accounts.E2E_PENALTY_INT_RECEIVED,
    mortgage.interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.E2E_ACCRUED_INT_RECEIVABLE
    ),
    mortgage.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: accounts.E2E_INTEREST_RECEIVED,
    mortgage.interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.E2E_CAPITALISED_INT_RECEIVABLE
    ),
    mortgage.interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: (
        accounts.E2E_CAPITALISED_INT_RECEIVED
    ),
    mortgage.overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT: (
        accounts.E2E_OP_ALLOWANCE_FEE_INCOME
    ),
}

e2e_flag_params = {
    mortgage.PARAM_DELINQUENCY_FLAG: parameters.DELINQUENCY_FLAG_PARAMETER_VALUE,
    mortgage.repayment_holiday.PARAM_DELINQUENCY_BLOCKING_FLAGS: (
        parameters.DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE
    ),
    mortgage.repayment_holiday.PARAM_DUE_AMOUNT_CALCULATION_BLOCKING_FLAGS: (
        parameters.DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE
    ),
    mortgage.repayment_holiday.PARAM_OVERDUE_AMOUNT_CALCULATION_BLOCKING_FLAGS: (
        parameters.DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE
    ),
    mortgage.repayment_holiday.PARAM_PENALTY_BLOCKING_FLAGS: (
        parameters.DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE
    ),
    mortgage.repayment_holiday.PARAM_REPAYMENT_BLOCKING_FLAGS: (
        parameters.DEFAULT_BLOCKING_FLAG_PARAMETER_VALUE
    ),
}

default_instance = parameters.mortgage_instance_params
default_template = prepare_parameters_for_e2e(
    parameters=parameters.mortgage_template_params,
    internal_account_param_mapping=e2e_internal_account_params,
    flag_param_mapping=e2e_flag_params,
)
