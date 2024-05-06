# standard lib
from decimal import Decimal

# inception lib
from inception_sdk.vault.contracts.types_extension import (
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

MAX_DEPOSIT_PARAM = "maximum_deposit"

parameters = [
    Parameter(
        name=MAX_DEPOSIT_PARAM,
        level=Level.TEMPLATE,
        description="The maximum amount that can be deposited into the account"
        " in a single transaction.",
        display_name="Maximum deposit amount",
        shape=utils.LimitHundredthsShape,
        default_value=Decimal("1000"),
    ),
]


def validate(vault: Vault, postings: PostingInstructionBatch, denomination: str):
    """
    Reject the posting if the value is greater than the maximum allowed deposit.
    """
    max_deposit = utils.get_parameter(vault, MAX_DEPOSIT_PARAM)
    for posting in postings:
        posting_balances = posting.balances()
        deposit_value = (
            posting_balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
            + posting_balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN)].net
        )
        if deposit_value > 0 and max_deposit is not None and deposit_value > max_deposit:
            raise Rejected(
                f"Transaction amount {deposit_value} {denomination} is more than "
                f"the maximum permitted deposit amount {max_deposit} {denomination}.",
                reason_code=RejectedReason.AGAINST_TNC,
            )
