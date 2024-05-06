# standard lib
from datetime import datetime
from decimal import Decimal

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    ClientTransaction,
    Level,
    Parameter,
    Rejected,
    RejectedReason,
    Vault,
)
import library.features.common.utils as utils
import library.features.deposits.transaction_limits.common.utils as transaction_limit_utils

MAX_DAILY_DEPOSIT_PARAM = "maximum_daily_deposit"

parameters = [
    Parameter(
        name=MAX_DAILY_DEPOSIT_PARAM,
        level=Level.TEMPLATE,
        description="The maximum amount which can be consecutively deposited into the account over "
        "a given 24hr window.",
        display_name="Maximum daily deposit amount",
        shape=utils.LimitHundredthsShape,
        default_value=Decimal("10000"),
    ),
]


# this method requires 24hrs of postings e.g.
# @requires(parameters=True, balances="latest live", postings="1 day")
def validate(
    vault: Vault,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    client_transactions_excluding_proposed: dict[tuple[str, str], ClientTransaction],
    effective_date: datetime,
    denomination: str,
    net_batch: bool = False,
):
    """
    Reject the posting if it would cause the maximum daily deposit limit to be breached.
    If net_batch = False, only deposits in the batch will be considered when accepting/rejecting.
    If net_batch = True, the net of all postings in the batch is considered when determining
    accept/reject meaning if the net of the batch is negative, this will always be accepted
    even if the sum of deposits has exceeded the limit.
    """
    max_daily_deposit = utils.get_parameter(vault, MAX_DAILY_DEPOSIT_PARAM)

    # obtain the amount of deposits and withdrawals excluding the current proposed postings
    (
        amount_deposited_actual,
        amount_withdrawn_actual,
    ) = transaction_limit_utils.sum_client_transactions(
        denomination=denomination,
        cutoff_timestamp=datetime.combine(effective_date, datetime.min.time()),
        client_transactions=client_transactions_excluding_proposed,
    )

    # obtain the amount of deposits and withdrawals including the current proposed postings
    (
        amount_deposited_proposed,
        amount_withdrawn_proposed,
    ) = transaction_limit_utils.sum_client_transactions(
        denomination=denomination,
        cutoff_timestamp=datetime.combine(effective_date, datetime.min.time()),
        client_transactions=client_transactions,
    )

    # the difference between the deposit amounts gives the total deposits in the batch.
    posting_batch_deposited = amount_deposited_proposed - amount_deposited_actual

    # the difference between the withdrawals amounts gives the total withdrawals in the batch.
    posting_batch_withdrawn = amount_withdrawn_proposed - amount_withdrawn_actual

    # if the batch deposit amount is 0, then all of the postings are withdrawals which do not
    # need to be considered when checking against the deposit limit.
    if posting_batch_deposited == 0:
        return

    # in the case of netting the batch, if withdrawals are higher than or equal to the deposits,
    # the deposit limit is not considered to be breached.
    if net_batch and posting_batch_withdrawn >= posting_batch_deposited:
        return

    # total deposits for the day (including proposed)
    deposit_daily_spend = posting_batch_deposited + amount_deposited_actual

    # if netting the batch, include the withdrawal amounts in the posting batch.
    if net_batch:
        deposit_daily_spend -= posting_batch_withdrawn

    if deposit_daily_spend > max_daily_deposit:
        raise Rejected(
            "PIB would cause the maximum daily deposit limit of %s %s to be "
            "exceeded." % (max_daily_deposit, denomination),
            reason_code=RejectedReason.AGAINST_TNC,
        )
