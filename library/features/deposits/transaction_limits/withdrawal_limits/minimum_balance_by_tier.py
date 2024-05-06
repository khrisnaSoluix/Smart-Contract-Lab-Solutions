# standard lib
from decimal import Decimal
from json import dumps as json_dumps

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    BalanceDefaultDict,
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Phase,
    PostingInstructionBatch,
    StringShape,
    Level,
    Parameter,
    Rejected,
    RejectedReason,
    Vault,
)
import library.features.common.utils as utils
import library.features.common.account_tiers as account_tiers

MIN_BALANCE_THRESHOLD_PARAM = "tiered_minimum_balance_threshold"

parameters = [
    Parameter(
        name=MIN_BALANCE_THRESHOLD_PARAM,
        level=Level.TEMPLATE,
        description="The minimum balance allowed for each account tier.",
        display_name="Minimum balance threshold",
        shape=StringShape,
        default_value=json_dumps(
            {
                "STANDARD": "10",
            }
        ),
    ),
]


def validate(
    vault: Vault,
    postings: PostingInstructionBatch,
    balances: BalanceDefaultDict,
    denomination: str,
):
    """
    Reject if the net value of the posting instruction batch results in the account balance falling
    below the minimum threshold for the account tier.
    """
    available_balance = (
        balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
        + balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)].net
    )

    postings_balances = postings.balances()
    proposed_amount = (
        postings_balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
        + postings_balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)].net
    )

    min_balance_threshold_by_tier = utils.get_parameter(
        vault, MIN_BALANCE_THRESHOLD_PARAM, is_json=True
    )
    current_account_tier = account_tiers.get_account_tier(vault)
    min_balance = Decimal(min_balance_threshold_by_tier[current_account_tier])

    if available_balance + proposed_amount < min_balance:
        raise Rejected(
            f"Transaction amount {proposed_amount} {denomination} will result in the account "
            f"balance falling below the minimum permitted of {min_balance} {denomination}.",
            reason_code=RejectedReason.AGAINST_TNC,
        )
