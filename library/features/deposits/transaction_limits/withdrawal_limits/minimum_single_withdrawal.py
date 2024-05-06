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

MIN_WITHDRAWAL_PARAM = "minimum_withdrawal"

parameters = [
    Parameter(
        name=MIN_WITHDRAWAL_PARAM,
        level=Level.TEMPLATE,
        description="The minimum amount that can be withdrawn from the account"
        " in a single transaction.",
        display_name="Minimum withdrawal amount",
        shape=utils.LimitShape,
        default_value=Decimal("0.01"),
    ),
]


def validate(vault: Vault, postings: PostingInstructionBatch, denomination: str):
    """
    Reject the posting if the value is less than the minimum allowed withdrawal limit.
    """
    minimum_withdrawal = utils.get_parameter(vault, MIN_WITHDRAWAL_PARAM)
    if minimum_withdrawal:
        for posting in postings:
            posting_balances = posting.balances()
            withdrawal_value = (
                posting_balances[
                    (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
                ].net
                + posting_balances[
                    (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)
                ].net
            )
            if withdrawal_value < 0 and abs(withdrawal_value) < minimum_withdrawal:
                minimum_withdrawal = Decimal(minimum_withdrawal).quantize(Decimal("1.e-3"))
                raise Rejected(
                    f"Transaction amount {round(abs(withdrawal_value), 5).normalize()} "
                    f"{denomination} is less than the minimum withdrawal amount "
                    f"{str(minimum_withdrawal).rstrip('0').rstrip('.')} {denomination}.",
                    reason_code=RejectedReason.AGAINST_TNC,
                )
