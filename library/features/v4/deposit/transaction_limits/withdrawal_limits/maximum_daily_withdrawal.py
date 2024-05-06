# CBF: Maximum Daily Withdrawal Limit

# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.client_transaction_utils as client_transaction_utils
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    ClientTransaction,
    NumberShape,
    Parameter,
    ParameterLevel,
    PrePostingHookArguments,
    Rejection,
    RejectionReason,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Fetchers
data_fetchers = [fetchers.EFFECTIVE_DATE_POSTINGS_FETCHER]

# Parameters
PARAM_MAX_DAILY_WITHDRAWAL = "maximum_daily_withdrawal"
parameters = [
    Parameter(
        name=PARAM_MAX_DAILY_WITHDRAWAL,
        level=ParameterLevel.TEMPLATE,
        description="The maximum amount that can be withdrawn from the account from"
        " start of day to end of day.",
        display_name="Maximum Daily Withdrawal Amount",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("10000"),
    ),
]


def validate(
    *,
    vault: SmartContractVault,
    hook_arguments: PrePostingHookArguments,
    denomination: str,
    effective_date_client_transactions: Optional[dict[str, ClientTransaction]] = None,
) -> Optional[Rejection]:
    """
    Reject the proposed client transactions if they would cause the maximum daily withdrawal limit
    to be exceeded.
    Note: This function requires all the postings for the hook argument's effective_datetime date to
    be retrieved, since this data requirement is shared across all daily transaction limit features,
    for optimization purposes the effective_date_client_transactions argument has been marked
    as optional. This allows the caller to retrieve the data once in the pre-posting-hook and using
    it in all the daily transactions limit features the contract uses avoiding redundant data
    fetching.

    :param vault: Vault object for the account whose daily withdrawal limit is being validated
    :param hook_arguments: pre-posting hook argument that will contain:
    "proposed client transactions" - that are being processed and need to be reviewed to ensure
    they are under the daily withdrawal limit
    "effective date" - date for which the limit is being calculated
    :param denomination: the denomination to be used in the validation
    :param effective_date_client_transactions: client transactions that have been processed
    during the period between <effective_date>T00:00:00 and <effective_date + 1 day>T00:00:00,
    if not provided the function will retrieve it using the EFFECTIVE_DATE_POSTINGS_FETCHER
    :return: rejection if the limit conditions are surpassed
    """

    # Obtain the impact of the proposed postings instructions
    (_, proposed_postings_withdrawn_amount) = client_transaction_utils.sum_client_transactions(
        cutoff_datetime=hook_arguments.effective_datetime,
        client_transactions=hook_arguments.client_transactions,
        denomination=denomination,
    )

    # if the withdrawn amount is 0, then all of the postings are deposits which do not
    # need to be considered when checking against the withdrawal limit.
    if proposed_postings_withdrawn_amount == 0:
        return None

    effective_date_client_transactions = (
        effective_date_client_transactions
        or vault.get_client_transactions(fetcher_id=fetchers.EFFECTIVE_DATE_POSTINGS_FETCHER_ID)
    )

    withdrawal_cutoff_datetime: datetime = hook_arguments.effective_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # obtain the amount of deposits and withdrawals for the day excluding proposed
    (_, amount_withdrawn_actual) = client_transaction_utils.sum_client_transactions(
        cutoff_datetime=withdrawal_cutoff_datetime,
        client_transactions=effective_date_client_transactions,
        denomination=denomination,
    )

    # total withdrawals for the day (including proposed)
    withdrawal_daily_spent = proposed_postings_withdrawn_amount + amount_withdrawn_actual

    max_daily_withdrawal: Decimal = utils.get_parameter(
        vault=vault, name=PARAM_MAX_DAILY_WITHDRAWAL
    )

    if withdrawal_daily_spent > max_daily_withdrawal:
        return Rejection(
            message=f"Transactions would cause the maximum daily withdrawal limit of "
            f"{max_daily_withdrawal} {denomination} to be exceeded.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

    return None
