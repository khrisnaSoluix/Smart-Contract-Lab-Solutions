# CBF: Maximum Balance Limit

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

PARAM_MAXIMUM_BALANCE = "maximum_balance"

parameters = [
    Parameter(
        name=PARAM_MAXIMUM_BALANCE,
        level=ParameterLevel.TEMPLATE,
        description="The maximum deposited balance amount for the account."
        " Deposits that breach this amount will be rejected.",
        display_name="Maximum Balance Amount",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("10000"),
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
    Reject the posting if the deposit will cause the current balance to exceed the maximum
    permitted balance.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions that are being processed and might cause
    the account's balance to go over the limit
    :param denomination: the denomination of the account
    :param balances: latest account balances available, if not provided will be retrieved
    using the LIVE_BALANCES_BOF_ID fetcher id
    :return: rejection if the limit conditions are not met
    """
    balances = (
        balances
        or vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances
    )

    current_balance = utils.get_current_net_balance(balances=balances, denomination=denomination)

    deposit_proposed_amount = Decimal(0)
    for posting in postings:
        postings_balances = posting.balances()
        deposit_proposed_amount += utils.get_current_net_balance(
            balances=postings_balances, denomination=denomination
        )

    maximum_balance: Decimal = utils.get_parameter(vault, PARAM_MAXIMUM_BALANCE)
    if maximum_balance is not None and current_balance + deposit_proposed_amount > maximum_balance:
        return Rejection(
            message=f"Posting would exceed maximum permitted balance {maximum_balance} "
            f"{denomination}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

    return None
