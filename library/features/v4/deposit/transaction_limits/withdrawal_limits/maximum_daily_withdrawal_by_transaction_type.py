# CBF: Maximum Daily Transaction Limit per Transaction Type

# standard libs
from decimal import Decimal
from json import dumps, loads
from typing import Optional

# features
import library.features.v4.common.account_tiers as account_tiers
import library.features.v4.common.client_transaction_utils as client_transaction_utils
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    ClientTransaction,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    PrePostingHookArguments,
    Rejection,
    RejectionReason,
    StringShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Fetchers
data_fetchers = [fetchers.EFFECTIVE_DATE_POSTINGS_FETCHER_ID]

# Parameters
PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION = "daily_withdrawal_limit_by_transaction_type"
PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT = "tiered_daily_withdrawal_limits"

parameters = [
    Parameter(
        name=PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION,
        level=ParameterLevel.INSTANCE,
        description="The maximum amount that can be withdrawn from an account "
        "over the current day by transaction type.",
        display_name="Maximum Daily Withdrawal Amount",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        shape=StringShape(),
        default_value=dumps({"ATM": "1000"}),
    ),
    Parameter(
        name=PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT,
        level=ParameterLevel.TEMPLATE,
        description="The daily withdrawal limits based on account tier. It defines the upper "
        "withdrawal limit that cannot be exceeded by Maximum Daily Withdrawal Amount."
        "If above it, the contract will consider the tiered limit as valid",
        display_name="Tiered Daily Withdrawal Limits",
        shape=StringShape(),
        default_value=dumps(
            {
                "UPPER_TIER": {"ATM": "5000"},
                "MIDDLE_TIER": {"ATM": "2000"},
                "LOWER_TIER": {"ATM": "1500"},
            }
        ),
    ),
]

INSTRUCTION_DETAILS_KEY = "TRANSACTION_TYPE"

# this method requires 1 complete day of postings e.g.
# @fetch_account_date(postings=[fetchers.EFFECTIVE_DATE_POSTINGS_FETCHER_ID])
def validate(
    *,
    vault: SmartContractVault,
    hook_arguments: PrePostingHookArguments,
    denomination: Optional[str] = None,
    effective_date_client_transactions: Optional[dict[str, ClientTransaction]] = None,
) -> Optional[Rejection]:
    """
    Reject the proposed client transactions if they would cause the maximum daily withdrawal limit
    by transaction type to be exceeded.
    Note: This function requires all the postings for the effective date to be retrieved, since
    this data requirement is shared across all daily transaction limit features, for optimization
    purposes the effective_datetime_client_transaction argument has been marked as optional.
    This allows the caller to retrieve the data once in the pre-posting-hook and using it in all
    the daily transactions limit features the contract uses avoiding redundant data fetching.

    :param vault: Vault object for the account whose daily withdrawal limit is being validated
    :param denomination: the denomination to be used in the validation
    :param hook_arguments: pre-posting hook argument that will contain:
    "proposed client transactions" that are being processed and need to be reviewed to ensure they
    are under the daily withdrawal limit
    "effective date": date for which the limit is being calculated
    :param effective_date_client_transactions: client transactions that have been processed
    during the period between <effective_date>T00:00:00 and <effective_date + 1 day>T00:00:00,
    if not provided the function will retrieve it using the EFFECTIVE_DATE_POSTINGS_FETCHER
    :return: rejection if the limit conditions are surpassed
    """
    account_tier = account_tiers.get_account_tier(vault)
    tiered_daily_limits: dict[str, dict[str, str]] = utils.get_parameter(
        vault, name=PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT, is_json=True
    )
    daily_limit_by_transaction = utils.get_parameter(
        vault, name=PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION, is_json=True
    )

    if denomination is None:
        denomination = utils.get_parameter(vault, name="denomination")

    if (
        not tiered_daily_limits and not daily_limit_by_transaction
    ) or not hook_arguments.client_transactions:
        return None

    limit_per_transaction_type: dict[str, str] = (
        _get_limit_per_transaction_type(
            tiered_daily_limits[account_tier], daily_limit_by_transaction
        )
        if account_tier in tiered_daily_limits.keys()
        else daily_limit_by_transaction
    )

    effective_date_client_transactions = (
        effective_date_client_transactions
        or vault.get_client_transactions(fetcher_id=fetchers.EFFECTIVE_DATE_POSTINGS_FETCHER_ID)
    )

    for transaction_type, transaction_type_limit in limit_per_transaction_type.items():
        # filter proposed client_transactions by transaction_type
        proposed_client_transactions = client_transaction_utils.filter_client_transactions(
            client_transactions=hook_arguments.client_transactions,
            client_transaction_ids_to_ignore=[""],
            denomination=denomination,
            key=INSTRUCTION_DETAILS_KEY,
            value=transaction_type,
        )

        if not proposed_client_transactions:
            continue

        # obtain the amount of deposits and withdrawals of the proposed postings
        (_, proposed_postings_withdrawn_amount) = client_transaction_utils.sum_client_transactions(
            cutoff_datetime=hook_arguments.effective_datetime,
            client_transactions=proposed_client_transactions,
            denomination=denomination,
        )

        # if the batch withdrawn amount is 0, then all of the postings are deposits which do not
        # need to be considered when checking against the withdrawal limit.
        if proposed_postings_withdrawn_amount == 0:
            continue

        # filter effective date client_transactions by transaction_type
        filtered_effective_date_client_transactions = (
            client_transaction_utils.filter_client_transactions(
                client_transactions=effective_date_client_transactions,
                client_transaction_ids_to_ignore=[""],
                denomination=denomination,
                key=INSTRUCTION_DETAILS_KEY,
                value=transaction_type,
            )
        )

        # obtain the amount of deposits and withdrawals for the day excluding proposed
        (_, amount_withdrawn_actual) = client_transaction_utils.sum_client_transactions(
            cutoff_datetime=(hook_arguments.effective_datetime).replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
            client_transactions=filtered_effective_date_client_transactions,
            denomination=denomination,
        )

        # total withdrawals for the day (including proposed)
        final_withdrawal_daily_spend = proposed_postings_withdrawn_amount + amount_withdrawn_actual

        if final_withdrawal_daily_spend > Decimal(transaction_type_limit):
            return Rejection(
                message=f"Transactions would cause the maximum daily {transaction_type} withdrawal "
                f"limit of {transaction_type_limit} {denomination} to be exceeded.",
                reason_code=RejectionReason.AGAINST_TNC,
            )

    return None


def _get_limit_per_transaction_type(
    tiered_limit_dict: dict[str, str], daily_limit_dict: dict[str, str]
) -> dict[str, str]:
    limit_per_transaction_type: dict[str, str] = tiered_limit_dict
    for transaction_type, limit in daily_limit_dict.items():
        limit_per_transaction_type[transaction_type] = (
            limit
            if transaction_type not in limit_per_transaction_type.keys()
            else str(min(Decimal(limit), Decimal(limit_per_transaction_type[transaction_type])))
        )

    return limit_per_transaction_type


def validate_parameter_change(
    *, vault: SmartContractVault, proposed_parameter_value: str
) -> Optional[Rejection]:
    """
    Validates daily_withdrawal_limit_by_transaction_type change.
    It returns rejection if the amount per transaction type is higher than the tiered one.

    :param vault: Vault object for the account whose limit is being validated
    :param proposed_parameter_value: updated string value of
    daily_withdrawal_limit_by_transaction_type param
    :return: rejection if any of new limits per transaction type is higher than the tiered one
    """
    account_tier = account_tiers.get_account_tier(vault)
    tiered_daily_limits: dict[str, dict[str, str]] = utils.get_parameter(
        vault, name=PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT, is_json=True
    )

    if not tiered_daily_limits or account_tier not in tiered_daily_limits:
        return None

    # daily_withdrawal_limit_by_transaction_type
    parameters_dict = loads(proposed_parameter_value)
    for transaction_type, transaction_type_value in parameters_dict.items():
        if transaction_type not in tiered_daily_limits[account_tier]:
            continue

        tiered_limit_value = Decimal(tiered_daily_limits[account_tier][transaction_type])
        proposed_transaction_type_value = Decimal(transaction_type_value)

        if proposed_transaction_type_value > tiered_limit_value:
            denomination = utils.get_parameter(vault, name="denomination")

            return Rejection(
                message=f"Cannot update {transaction_type} transaction type limit for Maximum "
                f"Daily Withdrawal Amount because {proposed_transaction_type_value} {denomination} "
                f"exceeds tiered limit of {tiered_limit_value} {denomination} "
                f"for active {account_tier}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )

    return None
