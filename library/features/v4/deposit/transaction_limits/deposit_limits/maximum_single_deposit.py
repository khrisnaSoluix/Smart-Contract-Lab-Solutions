# standard libs
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import NumberShape, Parameter, ParameterLevel, Rejection, RejectionReason

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_MAX_DEPOSIT = "maximum_deposit"

parameters = [
    Parameter(
        name=PARAM_MAX_DEPOSIT,
        level=ParameterLevel.TEMPLATE,
        description="The maximum amount that can be deposited into the account"
        " in a single transaction.",
        display_name="Maximum Deposit Amount",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("1000"),
    ),
]


def validate(
    *,
    vault: SmartContractVault,
    postings: utils.PostingInstructionListAlias,
    denomination: str,
) -> Optional[Rejection]:
    """
    Reject the posting if the value is greater than the maximum allowed deposit.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions that are being processed and need to be reviewed
    to ensure they are under the single operation limit
    :param denomination: the denomination of the account
    :return: rejection if the limit conditions are not met
    """
    max_deposit: Decimal = utils.get_parameter(vault, PARAM_MAX_DEPOSIT)
    for posting in postings:
        posting_balances = posting.balances()
        deposit_value = utils.get_current_net_balance(
            balances=posting_balances, denomination=denomination
        )
        if deposit_value > 0 and max_deposit is not None and deposit_value > max_deposit:
            return Rejection(
                message=f"Transaction amount {deposit_value} {denomination} is more than "
                f"the maximum permitted deposit amount {max_deposit} {denomination}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )

    return None
