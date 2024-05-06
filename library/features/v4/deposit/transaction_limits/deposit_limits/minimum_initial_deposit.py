# standard libs
from decimal import Decimal
from typing import Optional

# features
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    BalanceDefaultDict,
    NumberShape,
    Parameter,
    ParameterLevel,
    Rejection,
    RejectionReason,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Fetchers
data_fetchers = [fetchers.LIVE_BALANCES_BOF]

PARAM_MIN_INITIAL_DEPOSIT = "minimum_initial_deposit"

parameters = [
    Parameter(
        name=PARAM_MIN_INITIAL_DEPOSIT,
        level=ParameterLevel.TEMPLATE,
        description="The minimum amount for the first deposit to the account",
        display_name="Minimum Initial Deposit",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("20.00"),
    ),
]


def validate(
    *,
    vault: SmartContractVault,
    postings: utils.PostingInstructionListAlias,
    denomination: str,
    balances: Optional[BalanceDefaultDict] = None,
) -> Optional[Rejection]:
    """
    Reject the list of postings if their net affect does not meet the minimum initial deposit limit
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions being checked to ensure they meet the initial
    deposit limit
    :param denomination: the denomination of the account
    :param balances: latest account balances available, if not provided will retrieve the latest
    balances
    :return: rejection if the limit conditions are not met
    """
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    min_initial_deposit: Decimal = utils.get_parameter(vault, PARAM_MIN_INITIAL_DEPOSIT)
    available_credit_balance = utils.get_current_credit_balance(
        balances=balances, denomination=denomination
    )

    # current posting is not the initial posting due to existing credit
    if available_credit_balance > Decimal("0"):
        return None

    # calculate the net affect of postings
    posting_balances = BalanceDefaultDict()
    for posting in postings:
        posting_balances += posting.balances()

    deposit_value = utils.get_current_net_balance(
        balances=posting_balances, denomination=denomination
    )

    # ignore debits and reject if the net effect is below the min threhsold
    if Decimal(0) < deposit_value < min_initial_deposit:
        return Rejection(
            message=f"Transaction amount {deposit_value:0.2f} {denomination} is less than the "
            f"minimum initial deposit amount {min_initial_deposit:0.2f} {denomination}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

    return None
