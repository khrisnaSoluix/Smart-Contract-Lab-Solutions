# standard lib
from decimal import Decimal

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    BalanceDefaultDict,
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Phase,
    PostingInstructionBatch,
    Level,
    Parameter,
    Rejected,
    RejectedReason,
    Vault,
)
import library.features.common.utils as utils

MAXIMUM_BALANCE_PARAM = "maximum_balance"

parameters = [
    Parameter(
        name="maximum_balance",
        level=Level.TEMPLATE,
        description="The maximum deposited balance amount for the account."
        " Deposits that breach this amount will be rejected.",
        display_name="Maximum balance amount",
        shape=utils.LimitHundredthsShape,
        default_value=Decimal("10000"),
    ),
]


def validate(
    vault: Vault, postings: PostingInstructionBatch, balances: BalanceDefaultDict, denomination: str
):
    """
    Reject the posting if the deposit will cause the current balance to exceed the maximum
    permitted balance.
    """
    current_balance = (
        balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
        + balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN)].net
    )

    postings_balances = postings.balances()
    deposit_proposed_amount = (
        postings_balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
        + postings_balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN)].net
    )

    maximum_balance = utils.get_parameter(vault, MAXIMUM_BALANCE_PARAM)
    if maximum_balance is not None and current_balance + deposit_proposed_amount > maximum_balance:
        raise Rejected(
            f"Posting would exceed maximum permitted balance {maximum_balance} {denomination}.",
            reason_code=RejectedReason.AGAINST_TNC,
        )
