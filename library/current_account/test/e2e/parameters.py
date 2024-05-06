# standard libs
from datetime import datetime
from typing import Any, Union
from zoneinfo import ZoneInfo

# library
import library.current_account.contracts.template.current_account as current_account
from library.current_account.test import accounts, parameters

# inception sdk
from inception_sdk.test_framework.endtoend.contracts_helper import prepare_parameters_for_e2e

e2e_internal_account_params = {
    current_account.excess_fee.PARAM_EXCESS_FEE_ACCOUNT: accounts.EXCESS_FEE_INCOME_ACCOUNT,
    current_account.inactivity_fee.PARAM_INACTIVITY_FEE_INCOME_ACCOUNT: (
        accounts.INACTIVITY_FEE_INCOME_ACCOUNT
    ),
    current_account.interest_application.PARAM_INTEREST_PAID_ACCOUNT: (
        accounts.INTEREST_PAID_ACCOUNT
    ),
    current_account.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTEREST_RECEIVED_ACCOUNT
    ),
    current_account.maintenance_fees.PARAM_ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: (
        accounts.ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT
    ),
    current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: (
        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT
    ),
    current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: (
        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT
    ),
    current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT
    ),
    current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: (
        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT
    ),
    current_account.tiered_interest_accrual.PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT
    ),
    current_account.tiered_interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    ),
    current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT: (
        accounts.UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT
    ),
    current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: (
        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT
    ),
}
maximum_daily_withdrawal_by_transaction_type = (
    current_account.maximum_daily_withdrawal_by_transaction_type
)
e2e_flag_params: dict[str, Union[list[str], dict[str, Any]]] = {
    current_account.dormancy.PARAM_DORMANCY_FLAGS: parameters.DORMANCY_FLAGS,
    current_account.maintenance_fees.PARAM_ANNUAL_MAINTENANCE_FEE_BY_TIER: (
        parameters.ANNUAL_MAINTENANCE_FEE_BY_TIER
    ),
    current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: (
        parameters.MONTHLY_MAINTENANCE_FEE_BY_TIER
    ),
    current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER: (
        parameters.MINIMUM_BALANCE_THRESHOLD_BY_TIER
    ),
    maximum_daily_withdrawal_by_transaction_type.PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT: (
        parameters.WITHDRAWAL_LIMIT_BY_TIER
    ),
}

default_instance = {
    **parameters.default_instance,
    current_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "2",
}

default_template = prepare_parameters_for_e2e(
    parameters={
        **parameters.default_template,
        current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
    },
    internal_account_param_mapping=e2e_internal_account_params,
    flag_param_mapping=e2e_flag_params,
)

default_start_date = datetime(
    year=2023, month=1, day=1, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
)

CURRENT_ACCOUNT = "current_account"
