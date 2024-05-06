from json import dumps as json_dumps

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    UpdatePermission,
    Level,
    Parameter,
    StringShape,
    Vault,
)
import library.features.common.utils as utils

parameters = [
    Parameter(
        name="account_tier_names",
        level=Level.TEMPLATE,
        description="JSON encoded list of account tiers used as keys in map-type parameters."
        " Flag definitions must be configured for each used tier."
        " If the account is missing a flag the final tier in this list is used.",
        display_name="Tier names",
        shape=StringShape,
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=json_dumps(
            [
                "STANDARD",
            ]
        ),
    ),
]


def get_account_tier(vault: Vault) -> str:
    """
    Use the account tier flags to get a corresponding value from the account tiers list. If no
    recognised flags are present then the last value in account_tier_names will be used by default.
    If multiple flags are present then the nearest one to the start of account_tier_names will be
    used.
    :param vault: Vault object
    :return: account tier name assigned to account
    """
    account_tier_names = utils.get_parameter(vault, "account_tier_names", is_json=True)
    for tier_param in account_tier_names:
        if vault.get_flag_timeseries(flag=tier_param).latest():
            return tier_param

    return account_tier_names[-1]
