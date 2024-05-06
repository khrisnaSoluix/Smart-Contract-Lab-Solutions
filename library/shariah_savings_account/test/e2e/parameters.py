# standard libs
from datetime import datetime
from typing import Any, Union
from zoneinfo import ZoneInfo

# library
from library.shariah_savings_account.contracts.template import shariah_savings_account
from library.shariah_savings_account.test import accounts, parameters

# inception sdk
from inception_sdk.test_framework.endtoend.contracts_helper import prepare_parameters_for_e2e

e2e_internal_account_params = {
    shariah_savings_account.PARAM_PAYMENT_TYPE_FEE_INCOME_ACCOUNT: (
        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT
    ),
    shariah_savings_account.early_closure_fee.PARAM_EARLY_CLOSURE_FEE_INCOME_ACCOUNT: (
        accounts.EARLY_CLOSURE_FEE_INCOME_ACCOUNT
    ),
    shariah_savings_account.profit_application.PARAM_PROFIT_PAID_ACCOUNT: (
        accounts.PROFIT_PAID_ACCOUNT
    ),
    shariah_savings_account.tiered_profit_accrual.PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT: (
        accounts.ACCRUED_PROFIT_PAYABLE_ACCOUNT
    ),
}

max_daily_withdrawal_by_txn_type = (
    shariah_savings_account.maximum_daily_withdrawal_by_transaction_type
)
e2e_flag_params: dict[str, Union[list[str], dict[str, Any]]] = {
    shariah_savings_account.account_tiers.PARAM_ACCOUNT_TIER_NAMES: parameters.ACCOUNT_TIER_NAMES,
    shariah_savings_account.minimum_balance_by_tier.PARAM_MIN_BALANCE_THRESHOLD: (
        parameters.TIERED_MIN_BALANCE_THRESHOLD
    ),
    shariah_savings_account.tiered_profit_accrual.PARAM_TIERED_PROFIT_RATES: (
        parameters.TIERED_PROFIT_RATES
    ),
    max_daily_withdrawal_by_txn_type.PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT: (
        parameters.TIERED_DAILY_WITHDRAWAL_LIMITS
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

SAVINGS_ACCOUNT = "shariah_savings_account"
