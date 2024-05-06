# standard lib
from datetime import datetime
from decimal import Decimal

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    ClientTransaction,
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    PostingInstructionBatch,
    Rejected,
    RejectedReason,
)
import library.features.deposits.transaction_limits.common.utils as transaction_limit_utils

# this method requires 24hrs of postings e.g.
# @requires(parameters=True, balances="latest live", postings="1 day")
def validate(
    limit_mapping: dict[str, str],
    instruction_detail_key: str,
    postings: PostingInstructionBatch,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    effective_date: datetime,
    denomination: str,
):
    """
    Reject the posting if it would cause the maximum daily withdrawal limit to be breached.
    """
    for posting in postings:
        instruction_detail_key_value = posting.instruction_details.get(instruction_detail_key)
        if not instruction_detail_key_value or instruction_detail_key_value not in limit_mapping:
            continue

        limit = Decimal(limit_mapping[instruction_detail_key_value])
        client_transaction = client_transactions.get(
            (posting.client_id, posting.client_transaction_id)
        )
        amount_authed = max(
            abs(
                client_transaction.effects()[
                    (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)
                ].authorised
                - client_transaction.effects()[
                    (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)
                ].released
            ),
            abs(
                client_transaction.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].settled
            ),
        )
        # amount_withdrawn is -ve.
        amount_withdrawn = (
            transaction_limit_utils.sum_withdrawals_by_instruction_details_key_for_day(
                denomination,
                client_transactions,
                posting.client_transaction_id,
                datetime.combine(effective_date, datetime.min.time()),
                instruction_detail_key,
                instruction_detail_key_value,
            )
        )

        # check daily withdrawal/payment limit
        if not posting.credit and amount_authed - amount_withdrawn > limit:
            raise Rejected(
                f"Transaction would cause the maximum {instruction_detail_key_value} payment"
                f" limit of {limit} {denomination} to be exceeded.",
                reason_code=RejectedReason.AGAINST_TNC,
            )
