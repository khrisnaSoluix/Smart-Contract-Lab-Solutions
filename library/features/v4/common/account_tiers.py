# CBF: Account Tiers

# standard libs
from datetime import datetime
from json import dumps
from typing import Any, Callable, Optional

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import Parameter, ParameterLevel, ParameterUpdatePermission, StringShape

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_ACCOUNT_TIER_NAMES = "account_tier_names"
parameters = [
    Parameter(
        name=PARAM_ACCOUNT_TIER_NAMES,
        level=ParameterLevel.TEMPLATE,
        description="JSON encoded list of account tiers used as keys in map-type parameters."
        " Flag definitions must be configured for each used tier."
        " If the account is missing a flag the final tier in this list is used.",
        display_name="Tier Names",
        shape=StringShape(),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=dumps(
            [
                "STANDARD",
            ]
        ),
    ),
]


def get_account_tier(
    vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    """
    Use the account tier flags to get a corresponding value from the account tiers list. If no
    recognised flags are present then the last value in account_tier_names will be used by default.
    If multiple flags are present then the nearest one to the start of account_tier_names will be
    used.
    :param vault: vault object for the account whose tier is being retrieved
    :param effective_datetime: datetime at which to retrieve the flag_timeseries value. If not
    specified the latest value is retrieved
    :return: account tier name assigned to account
    """
    account_tier_names = utils.get_parameter(vault, "account_tier_names", is_json=True)

    for tier_param in account_tier_names:
        if effective_datetime is None:
            if vault.get_flag_timeseries(flag=tier_param).latest():
                return tier_param
        else:
            if vault.get_flag_timeseries(flag=tier_param).at(at_datetime=effective_datetime):
                return tier_param

    return account_tier_names[-1]


def get_tiered_parameter_value_based_on_account_tier(
    tiered_parameter: dict[str, str],
    tier: str,
    convert: Optional[Callable] = None,
) -> Optional[Any]:
    """
    Use the account tier flags to get a corresponding value from a
    dictionary keyed by account tier.
    If there is no value for the tier provided, None will be returned.
    :param tiered_parameter: dictionary mapping tier names to their corresponding.
    parameter values.
    :param tier: tier name of the account
    :param convert: function used to convert the resulting value before returning e.g Decimal.
    :return: as per convert function, value for tiered_param corresponding to account tier.
    """

    # Ensure tier is present in the tiered parameter
    if tier in tiered_parameter:
        value = tiered_parameter[tier]
        return convert(value) if convert else value

    # If tiered parameter was missing a key for active account tier returns None
    return None
