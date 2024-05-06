# standard lib
from decimal import Decimal

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    BalanceDefaultDict,
    Phase,
    PostingInstructionBatch,
    Level,
    Parameter,
    Rejected,
    RejectedReason,
    Vault,
)
import library.features.common.utils as utils

MIN_INITIAL_DEPOSIT_PARAM = "minimum_initial_deposit"

parameters = [
    Parameter(
        name=MIN_INITIAL_DEPOSIT_PARAM,
        level=Level.TEMPLATE,
        description="The minimun amount for the first deposit to the account",
        display_name="Minimum initial deposit",
        shape=utils.MoneyShape,
        default_value=Decimal("20.00"),
    ),
]


def validate(
    vault: Vault, postings: PostingInstructionBatch, balances: BalanceDefaultDict, denomination: str
):
    """
    Reject the posting if it does not meet the initial minimum deposit limit.
    """
    min_initial_deposit = utils.get_parameter(vault, MIN_INITIAL_DEPOSIT_PARAM)

    available_balance = (
        balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
        + balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)].net
    )

    for posting in postings:
        posting_balances = posting.balances()
        deposit_value = (
            posting_balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
            + posting_balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN)].net
        )
        if (
            min_initial_deposit is not None
            and available_balance == 0
            and 0 < deposit_value < min_initial_deposit
        ):
            raise Rejected(
                f"Transaction amount {deposit_value:0.2f} {denomination} is less than the "
                f"minimum initial deposit amount {min_initial_deposit:0.2f} {denomination}.",
                reason_code=RejectedReason.AGAINST_TNC,
            )
