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

MIN_DEPOSIT_PARAM = "minimum_deposit"

parameters = [
    Parameter(
        name="minimum_deposit",
        level=Level.TEMPLATE,
        description="The minimum amount that can be deposited into the account"
        " in a single transaction.",
        display_name="Minimum deposit amount",
        shape=utils.MoneyShape,
        default_value=Decimal("0.01"),
    ),
]


def validate(vault: Vault, postings: PostingInstructionBatch, denomination: str):
    """
    Reject if the deposit amount does not meet the minimum deposit limit.
    """
    minimum_deposit = utils.get_parameter(vault, MIN_DEPOSIT_PARAM)
    for posting in postings:
        posting_balances = posting.balances()
        deposit_value = (
            posting_balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
            + posting_balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN)].net
        )
        if minimum_deposit is not None and 0 < deposit_value < minimum_deposit:
            deposit_value = utils.round_decimal(deposit_value, 5)
            minimum_deposit = utils.round_decimal(minimum_deposit, 5)
            raise Rejected(
                f"Transaction amount {utils.remove_exponent(deposit_value)} {denomination} is less"
                f" than the minimum deposit amount {utils.remove_exponent(minimum_deposit)} "
                f"{denomination}.",
                reason_code=RejectedReason.AGAINST_TNC,
            )
