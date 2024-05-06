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

MINIMUM_LOAN_AMOUNT = "minimum_loan_amount"

parameters = [
    Parameter(
        name=MINIMUM_LOAN_AMOUNT,
        shape=OptionalShape(NumberShape(min_value=0)),
        level=Level.TEMPLATE,
        description="The minimum value amount for each loan.",
        display_name="Minimum loan amount",
        default_value=OptionalValue(Decimal("50")),
    )
]


def validate(vault: Vault, postings: PostingInstructionBatch, denomination: str):
    """
    Reject a posting if the minimum loan amount limit is subceeded.
    Current implementation considers the net of the batch for Tside = Asset only.
    Recommended to be used for batches with a single posting instruction that ia outbound only
    (e.g. loan creation).
    """
    minimum_loan_amount = utils.get_parameter(vault, MINIMUM_LOAN_AMOUNT, optional=True)

    settled_amount = postings.balances()[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    pending_amount = postings.balances()[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)
    ].net

    postings_amount = settled_amount + pending_amount

    # 0 comparison required for inbound hard settlements (repayments).
    if minimum_loan_amount is not None and 0 < postings_amount < minimum_loan_amount:
        raise Rejected(
            f"Cannot create loan smaller than minimum loan amount limit of: "
            f"{minimum_loan_amount}.",
            reason_code=RejectedReason.AGAINST_TNC,
        )
