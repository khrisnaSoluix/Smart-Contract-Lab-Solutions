# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional

# contracts api
from contracts_api import ClientTransaction, PostingInstructionType


def sum_client_transactions(
    *,
    cutoff_datetime: datetime,
    client_transactions: dict[str, ClientTransaction],
) -> tuple[Decimal, Decimal]:
    """
    Sum the net amount credited to and debited from an account by the given client_transactions
    since a given cut off point. The impact of chainable instructions is considered in the Auth,
    unless the subsequent instructions increase the auth'd amount. For example:
    - an inbound auth before cut off and settlement for same amount X after cut off will result in 0
      credit and debit.
    - an inbound auth and settlement for same amount X, both after cut off will result in the amount
      in credit = X and debit = 0
    - an inbound auth before cut off for amount X and settlement after cut off for Y, where Y > X,
      will result in credit = Y - X and debit = 0

    :param cutoff_datetime: postings value timestamped before this datetime are excluded from the
    totals.
    :param client_transactions: ClientTransaction dictionary, keyed by unique client transaction id
    :return: Sum of credits, sum of debits for given client transactions since the cut-off.
    Both values are >= 0
    """
    amount_debited = Decimal(0)
    amount_credited = Decimal(0)

    for transaction in client_transactions.values():
        transaction_amount = _get_total_transaction_impact(transaction=transaction)

        # We can't do `.before()` on transaction effects, so we get 'at' the latest timestamp
        # before the cutoff timestamp instead (max granularity is 1 us)
        cutoff_datetime -= relativedelta(microseconds=1)

        amount_before_cutoff = _get_total_transaction_impact(
            transaction=transaction, effective_datetime=cutoff_datetime
        )

        amount = transaction_amount - amount_before_cutoff
        if amount > 0:
            amount_credited += amount
        else:
            amount_debited += abs(amount)

    return amount_credited, amount_debited


def sum_debits_by_instruction_details_key(
    *,
    denomination: str,
    client_transactions: dict[str, ClientTransaction],
    client_transaction_id_to_ignore: str,
    cutoff_datetime: datetime,
    key: str,
    value: str,
) -> Decimal:
    """
    Determines the net debit amount for a given transaction type since the cut off:
    - debit amount includes any debit impact to the available balance at the DEFAULT address and
    specified denomination, which includes unsettled authorisations.
    - type is determined by the specified key-value pair on the first posting instruction of a
    given client transaction.
    - Released client transactions are ignored.
    - Client transactions with a CustomInstruction are ignored.

    :param denomination: denomination to consider
    :param client_transactions: ClientTransaction dictionary, keyed by unique client transaction id
    :param client_transaction_id_to_ignore: a client_transaction_id to ignore (e.g. the current
    posting being processed)
    :param cutoff_datetime: the to cut off for client transaction
    :param key: key to reference in the instruction details
    :param value: value to lookup against the key in the instruction details.
    :return: the net withdrawal amount, filtered according to the arguments. This number is <= 0
    """

    in_scope_transactions = {
        client_transaction_id: client_transaction
        for client_transaction_id, client_transaction in client_transactions.items()
        if client_transaction_id != client_transaction_id_to_ignore
        and client_transaction.denomination == denomination
        and not client_transaction.released()
        # custom instructions aren't chainable so we only need to check the first posting
        and client_transaction.posting_instructions[0].type
        != PostingInstructionType.CUSTOM_INSTRUCTION
        and client_transaction.posting_instructions[0].instruction_details.get(key) == value
    }

    return sum_client_transactions(
        cutoff_datetime=cutoff_datetime,
        client_transactions=in_scope_transactions,
    )[1]


def _get_total_transaction_impact(
    *,
    transaction: ClientTransaction,
    effective_datetime: Optional[datetime] = None,
) -> Decimal:
    """
    For any financial movement, the total effect a ClientTransaction
    has had on the balances can be represents by the sum of
    settled and unsettled .effects.

    1. HardSettlement (-10):
        authorised: 0, settled: -10, unsettled: 0
        sum = -10
    2. Authorisation (-10)
        authorised: -10, settled: 0, unsettled: -10
        sum = -10
    3. Authorisation (-10) + Adjustment (-5)
        authorisation:  authorised: -10, settled: 0, unsettled: -10
        adjustment:     authorised: -15, settled: 0, unsettled: -15
        sum = -15
    4. Authorisation (-10) + Total Settlement (-10)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        settlement:    authorised: -10, settled: -10, unsettled: 0
        sum = -10
    5. Authorisation (-10) + Partial Settlement Non-final (-5)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        settlement:    authorised: -10, settled: -5, unsettled: -5
        # if the settlement was not final, then the total effect of the transaction
        # is the value of the initial auth.
        sum = -10
    6. Authorisation (-10) + Partial Settlement Final (-5)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        settlement:    authorised: -5, settled: -5, unsettled: 0
        # as the settlement was final, the remaining funds were released. The impact
        # of this transaction is therefore only -5, i.e. even though the original auth
        # was -10, -5 of that was returned.
        sum = -5
    7. Authorisation (-10) + Oversettlement (auth -10 & an additional -5)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        settlement:    authorised: -10, settled: -15, unsettled: 0
        # as an oversettlement has occured, the impact on the account is the
        # the settlement amount of -15
        sum = -15
    8. Authorisation (-10) + Release (-10)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        release:       authorised: -10, settled: 0, unsettled: 0
        # as we have released all funds then this is expected to be 0, i.e. the
        # transaction has no overall impact on an account,
        sum = 0

    :param transaction: client transaction to process
    :param effective_datetime: effective datetime to determine which point of time to
    :return: The net of settled and unsettled effects.
    """
    # This is required to circumvent TM-80295 whereby the contracts_api wrongly raises an exception
    # instead of returning 0 if effects are queried before the start_datetime
    if (
        effective_datetime is not None
        and transaction.start_datetime is not None
        and effective_datetime < transaction.start_datetime
    ):
        return Decimal(0)

    return (
        transaction.effects(effective_datetime=effective_datetime).settled  # type: ignore
        + transaction.effects(effective_datetime=effective_datetime).unsettled  # type: ignore
    )
