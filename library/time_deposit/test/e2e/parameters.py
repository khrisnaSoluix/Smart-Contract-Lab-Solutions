# standard libs
from datetime import datetime
from typing import Mapping, Union
from zoneinfo import ZoneInfo

# library
from library.time_deposit.contracts.template import time_deposit
from library.time_deposit.test import accounts, parameters

# inception sdk
from inception_sdk.test_framework.endtoend.contracts_helper import prepare_parameters_for_e2e

default_e2e_start_date = datetime(year=2023, month=1, day=1, tzinfo=ZoneInfo("UTC"))

e2e_internal_account_params: dict[str, str] = {
    time_deposit.fixed_interest_accrual.PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT
    ),
    time_deposit.fixed_interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    ),
    time_deposit.interest_application.PARAM_INTEREST_PAID_ACCOUNT: (accounts.INTEREST_PAID_ACCOUNT),
    time_deposit.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTEREST_RECEIVED_ACCOUNT
    ),
}

e2e_flag_params: Mapping[str, Union[list[str], Mapping[str, str]]] = {}

default_instance = parameters.time_deposit_instance_params
default_template = prepare_parameters_for_e2e(
    parameters=parameters.time_deposit_template_params,
    internal_account_param_mapping=e2e_internal_account_params,
    flag_param_mapping=e2e_flag_params,
)

default_renewed_template = prepare_parameters_for_e2e(
    parameters=parameters.renewed_time_deposit_template_params,
    internal_account_param_mapping=e2e_internal_account_params,
    flag_param_mapping=e2e_flag_params,
)
