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

MAX_WITHDRAWAL_PARAM = "maximum_withdrawal"

parameters = [
    Parameter(
        name=MAX_WITHDRAWAL_PARAM,
        level=Level.TEMPLATE,
        description="The maximum amount that can be withdrawn from the account"
        " in a single transaction.",
        display_name="Maximum withdrawal amount",
        shape=utils.LimitHundredthsShape,
        default_value=Decimal("10000"),
    ),
]


def validate(vault: Vault, postings: PostingInstructionBatch, denomination: str):
    """
    Reject if any posting amount is greater than the maximum allowed withdrawal limit.
    """
    max_withdrawal = utils.get_parameter(vault, MAX_WITHDRAWAL_PARAM)
    for posting in postings:
        posting_balances = posting.balances()
        posting_value = (
            posting_balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
            + posting_balances[
                (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)
            ].net
        )
        if max_withdrawal is not None and posting_value < -max_withdrawal:
            raise Rejected(
                f"Transaction amount {abs(posting_value)} {denomination} is greater than "
                f"the maximum withdrawal amount {max_withdrawal} {denomination}.",
                reason_code=RejectedReason.AGAINST_TNC,
            )
