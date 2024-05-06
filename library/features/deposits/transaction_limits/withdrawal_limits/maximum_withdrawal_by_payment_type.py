# standard lib
from decimal import Decimal
from json import dumps as json_dumps

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
    StringShape,
    Vault,
)
import library.features.common.utils as utils


# String constants
PAYMENT_TYPE = "PAYMENT_TYPE"
MAX_WITHDRAWAL_BY_TYPE_PARAM = "maximum_payment_type_withdrawal"

parameters = [
    Parameter(
        name=MAX_WITHDRAWAL_BY_TYPE_PARAM,
        level=Level.TEMPLATE,
        description="The maximum single withdrawal allowed for each payment type.",
        display_name="Payment type limits",
        shape=StringShape,
        default_value=json_dumps(
            {
                "ATM": "30000",
            }
        ),
    ),
]


def validate(vault: Vault, postings: PostingInstructionBatch, denomination: str):
    """
    Reject the posting if the withdrawal value exceeds the PAYMENT_TYPE limit.
    """
    max_withdrawal_by_payment_type = utils.get_parameter(
        vault, MAX_WITHDRAWAL_BY_TYPE_PARAM, is_json=True
    )
    for posting in postings:
        payment_type = posting.instruction_details.get(PAYMENT_TYPE)

        if payment_type and payment_type in max_withdrawal_by_payment_type:
            withdrawal_limit = Decimal(max_withdrawal_by_payment_type[payment_type])
            posting_balances = posting.balances()
            posting_value = (
                posting_balances[
                    (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
                ].net
                + posting_balances[
                    (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)
                ].net
            )

            if posting_value < 0 and withdrawal_limit < abs(posting_value):
                raise Rejected(
                    f"Transaction amount {abs(posting_value):0.2f} {denomination} is more than "
                    f"the maximum withdrawal amount {withdrawal_limit} "
                    f"{denomination} allowed for the the payment type {payment_type}.",
                    reason_code=RejectedReason.AGAINST_TNC,
                )
