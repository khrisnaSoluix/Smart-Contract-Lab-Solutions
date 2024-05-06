# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# contracts api
from contracts_api import (
    AccountIdShape,
    ActivationHookArguments,
    ActivationHookResult,
    ConversionHookArguments,
    ConversionHookResult,
    DenominationShape,
    NumberShape,
    Parameter,
    ParameterLevel,
    PreParameterChangeHookArguments,
    PreParameterChangeHookResult,
    PrePostingHookArguments,
    PrePostingHookResult,
    ScheduledEventHookArguments,
    ScheduledEventHookResult,
    SmartContractEventType,
    fetch_account_data,
    requires,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

display_name = "V4 Contract"
summary = "Contract"
api = "4.0.0"
version = "1.0.0"
PARAM_SPENDING_LIMIT = "spending_limit"
NOMINATED_ACCOUNT = nominated_account
parameters = [
    Parameter(
        name="denomination",
        level=ParameterLevel.INSTANCE,
        description="Wallet denomination",
        display_name="Wallet denomination",
        shape=DenominationShape(),
        default_value="SGD",
    ),
    Parameter(
        name=NOMINATED_ACCOUNT,
        level=ParameterLevel.INSTANCE,
        description="Nominated CASA account for top up",
        display_name="Nominated Account (some unconformative blob)",
        shape=AccountIdShape(),
        default_value="0",
    ),
    Parameter(
        name=PARAM_SPENDING_LIMIT,
        level=ParameterLevel.INSTANCE,
        description="Allowed daily spending amount. Resets at midnight",
        display_name="Spending Limit",
        shape=NumberShape(),
        default_value=Decimal("999"),
    ),
]


@requires(event_type="ACCRUE_INTEREST", parameters=True)
@fetch_account_data(event_type="ACCRUE_INTEREST", balances=["daily_spend_balances"])
def scheduled_event_hook(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    now = datetime.now()
    utcnow = datetime.utcnow()


@requires(parameters=True, flags=True)
@fetch_account_data(balances=["latest_live_balances"])
def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    now = datetime.now()
    utcnow = datetime.utcnow()


event_types = [SmartContractEventType(name="name1", scheduler_tag_ids=["tag1"])]
event_types.append(SmartContractEventType(name="name2", scheduler_tag_ids=["tag2"]))
event_types += [SmartContractEventType(name="name3", scheduler_tag_ids=["tag3"])]
event_types[len(event_types) :] = [SmartContractEventType(name="name4", scheduler_tag_ids=["tag4"])]


def extend_event_types() -> None:
    # this function is *not* a hook/helper function, so error should be raised
    event_types.extend([SmartContractEventType(name="name5", scheduler_tag_ids=["tag5"])])


extend_event_types()

global_parameters = []
global_parameters.extend([""])

parameters += [""]

supported_denominations = []
supported_denominations.append("")

event_types_groups = []
event_types_groups.extend([""])

contract_module_imports = []
contract_module_imports += [""]

data_fetchers = []
data_fetchers.append("")


@requires(parameters=True, balances="latest")
def post_parameter_change_hook(vault, hook_arguments):
    length = _pre_parameter_change_code_helper_function(parameters)
    if length:
        print(parameters)  # this is local 'parameters', so no error raised


def _pre_parameter_change_code_helper_function(parameters):
    if _pre_parameter_change_code_nested_helper_function(parameters):
        return len(parameters)  # this is within hook helper function, so no error raised


def _pre_parameter_change_code_nested_helper_function(parameters) -> int:
    return len(parameters)  # this is within hook helper function, so no error raised


# vault should have typehint
def _helper_function(*, vault) -> bool:
    return True


@requires(parameters=True, balances="latest")
def pre_parameter_change_hook(
    vault: SmartContractVault, hook_arguments: PreParameterChangeHookArguments
) -> Optional[PreParameterChangeHookResult]:
    pass


@requires(parameters=True, balances="latest")
def conversion_hook(
    vault: SmartContractVault, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    return


@requires(parameters=True, balances="latest")
def activation_hook(
    vault: SmartContractVault, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    return ActivationHookResult()


# flake8: noqa
