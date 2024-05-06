# standard lib
from decimal import Decimal


# inception lib
from inception_sdk.vault.contracts.types_extension import (
    Rejected,
    RejectedReason,
    Parameter,
    Level,
    OptionalValue,
    OptionalShape,
    NumberShape,
    Vault,
    PostingInstructionBatch,
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Phase,
)

import library.features.common.utils as utils

MAXIMUM_LOAN_AMOUNT = "maximum_loan_amount"

parameters = [
    Parameter(
        name=MAXIMUM_LOAN_AMOUNT,
        shape=OptionalShape(NumberShape(min_value=0)),
        level=Level.TEMPLATE,
        description="The maximum value amount for each loan.",
        display_name="Maximum loan amount",
        default_value=OptionalValue(Decimal("1000")),
    )
]


def validate(vault: Vault, postings: PostingInstructionBatch, denomination: str):
    """
    Reject a posting batch if the maximum loan amount limit is exceeded.
    Current implementation looks at the net the batch for Tside = Asset only.
    Recommended to be used for batches with a single posting instruction that is outbound only
    (e.g. loan creation).
    """

    maximum_loan_amount = utils.get_parameter(vault, MAXIMUM_LOAN_AMOUNT, optional=True)

    settled_amount = postings.balances()[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    pending_amount = postings.balances()[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)
    ].net

    postings_amount = settled_amount + pending_amount

    if maximum_loan_amount is not None and postings_amount > maximum_loan_amount:
        raise Rejected(
            f"Cannot create loan larger than maximum loan amount limit of: "
            f"{maximum_loan_amount}.",
            reason_code=RejectedReason.AGAINST_TNC,
        )
