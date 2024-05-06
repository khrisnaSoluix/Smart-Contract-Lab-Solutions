# standard library
from datetime import datetime
from decimal import Decimal

# third party
from dateutil.relativedelta import relativedelta as timedelta

# inception imports
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    ClientTransaction,
)


def sum_client_transactions(
    denomination: str,
    cutoff_timestamp: datetime,
    client_transactions: dict[tuple[str, str], ClientTransaction],
) -> tuple[Decimal, Decimal]:
    """
    Sum all transactions in client_transactions since a given cutoff point.
    Chainable transactions should be considered to ensure no duplicate counting.
    :param denomination: denomination
    :param cutoff_timestamp: used to scope which transactions should be considered for summing
    :param client_transactions: keyed by (client_id, client_transaction_id)
    :return: Sum of deposits, sum of withdrawals for given client transactions. Both values are
             returned as positive integers (or 0).
    """
    amount_withdrawn = Decimal(0)
    amount_deposited = Decimal(0)

    for transaction in client_transactions.values():
        transaction_amount = _get_total_transaction_impact(transaction, denomination)

        # We can't do `.before()` on transaction effects, so we get 'at' the latest timestamp
        # before the cutoff timestamp instead (max granularity is 1 us)
        cutoff_timestamp -= timedelta(microseconds=1)

        amount_before_cutoff = _get_total_transaction_impact(
            transaction, denomination, cutoff_timestamp
        )
        # TODO: INC-5712 to consider Tside as current implementation
        # only considers Tside = Liability
        amount = transaction_amount - amount_before_cutoff
        if amount > 0:
            amount_deposited += amount
        else:
            amount_withdrawn += abs(amount)

    return amount_deposited, amount_withdrawn


def sum_withdrawals_by_instruction_details_key_for_day(
    denomination: str,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    client_transaction_id: str,
    cutoff_timestamp: datetime,
    key: str,
    value: str,
) -> Decimal:
    """
    Sum all withdrawals/payment of a type for default address in client_transactions since
    cutoff, excluding any cancelled or the current transaction.
    Return amount withdrawn/pay from the type since cutoff.
    :param denomination: denomination
    :param client_transactions: keyed by (client_id, client_transaction_id)
    :param client_transaction_id: the client_transaction_id for current posting
    :param cutoff_timestamp: the to cut off for client transaction
    :param key: key to reference in the instruction details
    :param value: value to lookup against the key in the instruction details
    :return: Sum of transactions of a payment type, which is -ve for withdrawals/payment
    """

    def _is_same_payment_type_today(posting):
        return (
            not posting.credit
            and posting.denomination == denomination
            and posting.value_timestamp >= cutoff_timestamp
            and posting.asset == DEFAULT_ASSET
            and posting.instruction_details.get(key) == value
        )

    return -sum(
        sum(posting.amount for posting in transaction if _is_same_payment_type_today(posting))
        for (_, transaction_id), transaction in client_transactions.items()
        if transaction_id != client_transaction_id and not transaction.cancelled
    )


def _get_total_transaction_impact(
    transaction: ClientTransaction,
    denomination: str,
    timestamp: datetime = None,
    address: str = DEFAULT_ADDRESS,
    asset: str = DEFAULT_ASSET,
) -> Decimal:
    """
    For any financial movement, the total effect a ClientTransaction
    has had on the balances can be represents by the sum of
    settled and unsettled .effects.

    1. HardSettlement (-10):
        authorised: 0, settled: -10, unsettled: 0, released: 0
        sum = -10
    2. Authorisation (-10)
        authorisation:  authorised: -10, settled: 0, unsettled: -10, released: 0
        sum = -10
    3. Authorisation (-10) + Adjustment (-5)
        authorisation:  authorised: -10, settled: 0, unsettled: -10, released: 0
        adjustment:     authorised: -15, settled: 0, unsettled: -15, released: 0
        sum = -15
    4. Authorisation (-10) + Total Settlement (-10)
        authorisation: authorised: -10, settled: 0, unsettled: -10, released: 0
        settlement:    authorised: -10, settled: -10, unsettled: 0, released: 0
        sum = -10
    5. Authorisation (-10) + Partial Settlement Non-final (-5)
        authorisation: authorised: -10, settled: 0, unsettled: -10, released: 0
        settlement:    authorised: -10, settled: -5, unsettled: -5, released: 0
        # if the settlement was not final, then the total effect of the transaction
        # is the value of the initial auth.
        sum = -10
    6. Authorisation (-10) + Partial Settlement Final (-5)
        authorisation: authorised: -10, settled: 0, unsettled: -10, released: 0
        settlement:    authorised: -5, settled: -5, unsettled: 0, released: -5
        # as the settlement was final, the remaining funds were released. The impact
        # of this transaction is therefore only -5, i.e. even though the original auth
        # was -10, -5 of that was returned.
        sum = -5
    7. Authorisation (-10) + Oversettlement (auth -10 & an additional -5)
        authorisation: authorised: -10, settled: 0, unsettled: -10, released: 0
        settlement:    authorised: -10, settled: -15, unsettled: 0, released: 0
        # as an oversettlement has occured, the impact on the account is the
        # the settlement amount of -15
        sum = -15
    8. Authorisation (-10) + Release (-10)
        authorisation: authorised: -10, settled: 0, unsettled: -10, released: 0
        release:       authorised: -10, settled: 0, unsettled: 0, released: -10
        # as we have released all funds then this is expected to be 0, i.e. the
        # transaction has no overall impact on an account,
        sum = 0

    :param: transaction:
    :param denomination: denomination of the transaction
    :param timestamp: timestamp to determine which point of time to
    :param address: balance address
    :param asset: balance asset
    :return: The net of settled and unsettled effects.
    """
    amount = (
        transaction.effects(timestamp=timestamp)[(address, asset, denomination)].settled
        + transaction.effects(timestamp=timestamp)[(address, asset, denomination)].unsettled
    )
    return amount
