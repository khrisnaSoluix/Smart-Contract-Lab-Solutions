# standard libs
from typing import Any, Union

# library
from library.us_products.contracts.template import us_checking_account
from library.us_products.test import accounts, parameters

# inception sdk
from inception_sdk.test_framework.endtoend.contracts_helper import prepare_parameters_for_e2e

e2e_internal_account_params: dict[str, str] = {
    us_checking_account.tiered_interest_accrual.PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT
    ),
    us_checking_account.tiered_interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    ),
    us_checking_account.interest_application.PARAM_INTEREST_PAID_ACCOUNT: (
        accounts.INTEREST_PAID_ACCOUNT
    ),
    us_checking_account.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTEREST_RECEIVED_ACCOUNT
    ),
    us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: (
        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT
    ),
    us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: (
        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT
    ),
    us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_INCOME_ACCOUNT: (
        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT
    ),
}

nested_e2e_internal_account_params: dict[str, dict[str, str]] = {
    us_checking_account.unlimited_fee_rebate.PARAM_FEE_REBATE_INTERNAL_ACCOUNTS: parameters.FEE_REBATE_INTERNAL_ACCOUNTS  # noqa: E501
}

e2e_flag_params: dict[str, Union[list[str], dict[str, Any]]] = {
    us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER: (
        parameters.MINIMUM_BALANCE_THRESHOLD_BY_TIER
    ),
    us_checking_account.dormancy.PARAM_DORMANCY_FLAGS: parameters.DORMANCY_FLAGS,
    us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: (
        parameters.MONTHLY_MAINTENANCE_FEE_BY_TIER
    ),
}

default_instance = parameters.checking_account_instance_params
default_template = prepare_parameters_for_e2e(
    parameters=parameters.checking_account_template_params,
    internal_account_param_mapping=e2e_internal_account_params,
    nested_internal_account_param_mapping=nested_e2e_internal_account_params,
    flag_param_mapping=e2e_flag_params,
)
