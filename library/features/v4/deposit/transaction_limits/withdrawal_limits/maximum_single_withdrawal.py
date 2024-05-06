# standard libs
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import NumberShape, Parameter, ParameterLevel, Rejection, RejectionReason

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_MAX_WITHDRAWAL = "maximum_withdrawal"

parameters = [
    Parameter(
        name=PARAM_MAX_WITHDRAWAL,
        level=ParameterLevel.TEMPLATE,
        description="The maximum amount that can be withdrawn from the account"
        " in a single transaction.",
        display_name="Maximum Withdrawal Amount",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("10000"),
    ),
]


def validate(
    *, vault: SmartContractVault, postings: utils.PostingInstructionListAlias, denomination: str
) -> Optional[Rejection]:
    """
    Reject if any posting amount is greater than the maximum allowed withdrawal limit.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions that are being processed and need to be reviewed
    to ensure they are under the single operation limit
    :param denomination: the denomination of the account
    :return: rejection if the limit conditions are not met
    """
    max_withdrawal: Decimal = utils.get_parameter(vault, PARAM_MAX_WITHDRAWAL)
    for posting in postings:
        posting_value = utils.get_available_balance(
            balances=posting.balances(), denomination=denomination
        )
        # The posting value will be negative for debits on liability accounts
        if posting_value > 0:
            continue
        elif abs(posting_value) > max_withdrawal:
            return Rejection(
                message=f"Transaction amount {abs(posting_value)} {denomination} is greater than "
                f"the maximum withdrawal amount {max_withdrawal} {denomination}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )

    return None
