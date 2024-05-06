# CBF: Minimum Deposit Amount per Transaction

# standard libs
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import NumberShape, Parameter, ParameterLevel, Rejection, RejectionReason

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_MIN_DEPOSIT = "minimum_deposit"

parameters = [
    Parameter(
        name=PARAM_MIN_DEPOSIT,
        level=ParameterLevel.TEMPLATE,
        description="The minimum amount that can be deposited into the account"
        " in a single transaction.",
        display_name="Minimum Deposit Amount",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("0.01"),
    ),
]


def validate(
    *,
    vault: SmartContractVault,
    postings: utils.PostingInstructionListAlias,
    denomination: str,
) -> Optional[Rejection]:
    """
    Reject if the deposit amount does not meet the minimum deposit limit.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions being checked
    :param denomination: the denomination of the account
    :return: rejection if the limit conditions are not met
    """
    minimum_deposit: Decimal = utils.get_parameter(vault, PARAM_MIN_DEPOSIT)
    for posting in postings:
        posting_balances = posting.balances()
        deposit_value = utils.get_current_net_balance(
            balances=posting_balances, denomination=denomination
        )
        if minimum_deposit is not None and 0 < deposit_value < minimum_deposit:
            deposit_value = utils.round_decimal(deposit_value, 5)
            minimum_deposit = utils.round_decimal(minimum_deposit, 5)
            return Rejection(
                message=f"Transaction amount {utils.remove_exponent(deposit_value)} {denomination} "
                f"is less than the minimum deposit amount {utils.remove_exponent(minimum_deposit)} "
                f"{denomination}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )

    return None
