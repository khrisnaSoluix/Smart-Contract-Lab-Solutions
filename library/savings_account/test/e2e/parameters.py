# standard libs
from datetime import datetime
from typing import Any, Union
from zoneinfo import ZoneInfo

# library
import library.savings_account.contracts.template.savings_account as savings_account
from library.savings_account.test import accounts, parameters

# inception sdk
from inception_sdk.test_framework.endtoend.contracts_helper import prepare_parameters_for_e2e

e2e_internal_account_params = {
    savings_account.excess_fee.PARAM_EXCESS_FEE_ACCOUNT: accounts.EXCESS_FEE_INCOME_ACCOUNT,
    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_INCOME_ACCOUNT: (
        accounts.INACTIVITY_FEE_INCOME_ACCOUNT
    ),
    savings_account.interest_application.PARAM_INTEREST_PAID_ACCOUNT: (
        accounts.INTEREST_PAID_ACCOUNT
    ),
    savings_account.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTEREST_RECEIVED_ACCOUNT
    ),
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: (
        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT
    ),
    savings_account.tiered_interest_accrual.PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT
    ),
    savings_account.tiered_interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    ),
}
maximum_daily_withdrawal_by_transaction_type = (
    savings_account.maximum_daily_withdrawal_by_transaction_type
)
e2e_flag_params: dict[str, Union[list[str], dict[str, Any]]] = {
    savings_account.dormancy.PARAM_DORMANCY_FLAGS: parameters.DORMANCY_FLAGS,
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER: (
        parameters.MINIMUM_BALANCE_THRESHOLD_BY_TIER
    ),
    maximum_daily_withdrawal_by_transaction_type.PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT: (
        parameters.WITHDRAWAL_LIMIT_BY_TIER
    ),
}

default_instance = parameters.default_instance
default_template = prepare_parameters_for_e2e(
    parameters=parameters.default_template,
    internal_account_param_mapping=e2e_internal_account_params,
    flag_param_mapping=e2e_flag_params,
)

default_start_date = datetime(
    year=2023, month=1, day=1, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
)

SAVINGS_ACCOUNT = "savings_account"
