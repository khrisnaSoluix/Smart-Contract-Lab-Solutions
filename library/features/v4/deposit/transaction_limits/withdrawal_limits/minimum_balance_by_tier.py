# standard libs
from decimal import Decimal
from json import dumps
from typing import Optional

# features
import library.features.v4.common.account_tiers as account_tiers
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    BalanceDefaultDict,
    Parameter,
    ParameterLevel,
    Rejection,
    RejectionReason,
    StringShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Fetchers
data_fetchers = [fetchers.LIVE_BALANCES_BOF]

PARAM_MIN_BALANCE_THRESHOLD = "tiered_minimum_balance_threshold"

parameters = [
    Parameter(
        name=PARAM_MIN_BALANCE_THRESHOLD,
        level=ParameterLevel.TEMPLATE,
        description="The minimum balance allowed for each account tier.",
        display_name="Minimum Balance Threshold",
        shape=StringShape(),
        default_value=dumps(
            {
                "STANDARD": "10",
            }
        ),
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
    Reject if the net value of the posting instruction batch results in the account balance falling
    below the minimum threshold for the account tier.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of posting instructions that are being processed
    to ensure that the balance of the account still meets the minimum balance limit
    :param denomination: the denomination of the account
    :param balances: latest account balances available, if not provided will be retrieved
    using the LIVE_BALANCES_BOF_ID fetcher id
    :return: rejection if the minimum balance limit conditions are not met
    """
    balances = (
        balances
        or vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances
    )

    available_balance = utils.get_available_balance(balances=balances, denomination=denomination)

    proposed_amount = sum(
        utils.get_available_balance(balances=posting.balances(), denomination=denomination)
        for posting in postings
    )

    min_balance_threshold_by_tier: dict[str, str] = utils.get_parameter(
        vault, PARAM_MIN_BALANCE_THRESHOLD, is_json=True
    )
    current_account_tier = account_tiers.get_account_tier(vault)
    min_balance = account_tiers.get_tiered_parameter_value_based_on_account_tier(
        tiered_parameter=min_balance_threshold_by_tier,
        tier=current_account_tier,
        convert=Decimal,
        # We don't have TypeVar that would solve this for us
    )  # type: ignore

    if available_balance + proposed_amount < min_balance:  # type: ignore
        return Rejection(
            message=f"Transaction amount {proposed_amount} {denomination} will result in the "
            f"account balance falling below the minimum permitted "
            f"of {min_balance} {denomination}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

    return None
