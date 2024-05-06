# standard libs
from datetime import datetime
from json import dumps
from typing import Optional

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import Parameter, ParameterLevel, Rejection, RejectionReason, StringShape

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Parameters
PARAM_DORMANCY_FLAGS = "dormancy_flags"

parameters = [
    # Template params
    Parameter(
        name=PARAM_DORMANCY_FLAGS,
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        description="The list of flag definitions that indicate an account is dormant. "
        "Dormant accounts may incur fees and have their transactions blocked. "
        "Expects a string representation of a JSON list.",
        display_name="Dormancy Flags",
        default_value=dumps(["ACCOUNT_DORMANT"]),
    ),
]


def is_account_dormant(vault: SmartContractVault, effective_datetime: datetime) -> bool:
    return utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_DORMANCY_FLAGS,
        effective_datetime=effective_datetime,
    )


def validate_account_transaction(
    vault: SmartContractVault, effective_datetime: datetime
) -> Optional[Rejection]:
    """
    This function is used to validate account transactions in the pre posting hook only.

    :param vault: SmartContractVault object
    :param effective_datetime: datetime object
    :return: Rejection to be used in PrePostingHookResult
    """
    if is_account_dormant(vault=vault, effective_datetime=effective_datetime):
        return Rejection(
            message="Account flagged 'Dormant' does not accept external transactions.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None
