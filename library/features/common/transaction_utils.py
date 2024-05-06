from datetime import datetime

from inception_sdk.vault.contracts.types_extension import (
    ClientTransaction,
    DEFAULT_ASSET,
    PostingInstruction,
    PostingInstructionBatch,
)


def _does_posting_match_criteria(
    posting: PostingInstruction,
    credit: bool,
    denomination: str,
    cutoff_timestamp: datetime,
    asset: str,
    instruction_detail_key: str,
    instruction_detail_value: str,
) -> bool:
    posting_balances = posting.balances()
    total_net = 0
    for pb in posting_balances.values():
        total_net += pb.net
    is_credit = total_net >= 0

    return (
        credit == is_credit
        and posting.denomination == denomination
        and posting.value_timestamp >= cutoff_timestamp
        and posting.asset == asset
        and posting.instruction_details.get(instruction_detail_key) == instruction_detail_value
    )


def withdrawals_by_instruction_detail(
    denomination: str,
    postings: PostingInstructionBatch,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    cutoff_timestamp: datetime,
    instruction_detail_key: str,
    instruction_detail_value: str,
) -> tuple[list[PostingInstruction], list[PostingInstruction]]:
    """
    Get all withdrawals for current transaction and previous transactions up to cutoff_timestamp.
    return: Tuple: (list of previous withdrawal, list of current withdrawals)
    """
    client_transaction_ids_in_current_batch = {
        posting.client_transaction_id for posting in postings
    }
    previous_withdrawals = []
    current_withdrawals = []
    for (_, transaction_id), transaction in client_transactions.items():
        for posting in transaction:
            if not transaction.cancelled and _does_posting_match_criteria(
                posting=posting,
                credit=False,
                denomination=denomination,
                cutoff_timestamp=cutoff_timestamp,
                asset=DEFAULT_ASSET,
                instruction_detail_key=instruction_detail_key,
                instruction_detail_value=instruction_detail_value,
            ):
                if transaction_id in client_transaction_ids_in_current_batch:
                    current_withdrawals.append(posting)
                else:
                    previous_withdrawals.append(posting)

    return previous_withdrawals, current_withdrawals
