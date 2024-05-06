# library
import library.home_loan_redraw.contracts.template.home_loan_redraw as home_loan_redraw
import library.home_loan_redraw.test.e2e.accounts as accounts
import library.home_loan_redraw.test.parameters as parameters

# inception sdk
from inception_sdk.test_framework.endtoend.contracts_helper import prepare_parameters_for_e2e

HOME_LOAN_REDRAW = "home_loan_redraw"

e2e_internal_account_params = {
    home_loan_redraw.interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.E2E_ACCRUED_INT_RECEIVABLE
    ),
    home_loan_redraw.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: (
        accounts.accounts.INTEREST_RECEIVED
    ),
}

default_instance = parameters.default_instance
default_template = prepare_parameters_for_e2e(
    parameters=parameters.default_template,
    internal_account_param_mapping=e2e_internal_account_params,
)
