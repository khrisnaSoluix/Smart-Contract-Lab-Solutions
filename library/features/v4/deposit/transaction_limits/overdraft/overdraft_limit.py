# CBF: Unarranged Overdraft and Unarranged Overdraft Fee
# CBF: Standard Overdraft (Arranged Overdraft)

# standard libs
from decimal import Decimal
from typing import Optional

# features
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.deposit.deposit_interfaces as deposit_interfaces

# contracts api
from contracts_api import (
    BalanceDefaultDict,
    NumberShape,
    OptionalShape,
    OptionalValue,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Rejection,
    RejectionReason,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Fetchers
data_fetchers = [fetchers.LIVE_BALANCES_BOF]

PARAM_ARRANGED_OVERDRAFT_AMOUNT = "arranged_overdraft_amount"
PARAM_UNARRANGED_OVERDRAFT_AMOUNT = "unarranged_overdraft_amount"


parameters = [
    Parameter(
        name=PARAM_ARRANGED_OVERDRAFT_AMOUNT,
        level=ParameterLevel.INSTANCE,
        description="An agreed amount which the customer may use to borrow funds",
        display_name="Arranged Overdraft Amount",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        shape=OptionalShape(shape=NumberShape(min_value=0, step=Decimal("0.01"))),
        default_value=OptionalValue(Decimal("0.00")),
    ),
    Parameter(
        name=PARAM_UNARRANGED_OVERDRAFT_AMOUNT,
        level=ParameterLevel.INSTANCE,
        description="An additional borrowing amount which may be used to validate balance"
        " checks when going beyond the agreed borrowing limit",
        display_name="Unarranged Overdraft Amount",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        shape=OptionalShape(shape=NumberShape(min_value=0, step=Decimal("0.01"))),
        default_value=OptionalValue(Decimal("0.00")),
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
    Return Rejection if the posting will cause the current balance to exceed the total overdraft
    amount.
    The total overdraft is calculated by summing the arranged and unarranged overdraft amounts.
    :param vault: Vault object for the account whose overdraft limit is being validated
    :param postings: posting instructions being processed
    :param denomination: denomination
    :param balances: latest account balances available, if not provided will be retrieved
    using the LIVE_BALANCES_BOF_ID fetcher id
    :return : rejection if criteria not satisfied
    """
    balances = (
        balances
        or vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances
    )

    posting_amount = Decimal(
        sum(
            utils.get_available_balance(balances=posting.balances(), denomination=denomination)
            for posting in postings
        )
    )
    total_available_balance = get_overdraft_available_balance(
        vault=vault, balances=balances, denomination=denomination
    )

    # check the posting amount is less than 0 as we want to always accept deposit amounts
    # (removing this would cause a rejection of a deposit if balance is in overdraft)
    if posting_amount < 0 and abs(posting_amount) > total_available_balance:
        return Rejection(
            message=f"Postings total {denomination} {posting_amount}, which exceeds the"
            f" available balance of {denomination} {total_available_balance}.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
    return None


def get_overdraft_available_balance(
    vault: SmartContractVault,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    return (
        utils.get_available_balance(balances=balances, denomination=denomination)
        + get_arranged_overdraft_amount(vault=vault)
        + get_unarranged_overdraft_amount(vault=vault)
    )


def get_arranged_overdraft_amount(vault: SmartContractVault) -> Decimal:
    return Decimal(
        utils.get_parameter(
            vault=vault,
            name=PARAM_ARRANGED_OVERDRAFT_AMOUNT,
            is_optional=True,
            default_value=Decimal("0"),
        )
    )


def get_unarranged_overdraft_amount(vault: SmartContractVault) -> Decimal:
    return Decimal(
        utils.get_parameter(
            vault=vault,
            name=PARAM_UNARRANGED_OVERDRAFT_AMOUNT,
            is_optional=True,
            default_value=Decimal("0"),
        )
    )


OverdraftLimitAvailableBalance = deposit_interfaces.AvailableBalance(
    calculate=get_overdraft_available_balance
)
