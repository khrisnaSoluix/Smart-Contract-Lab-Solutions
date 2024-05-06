# CBF: Minimum Withdrawal Amount per Transaction

# standard libs
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import NumberShape, Parameter, ParameterLevel, Rejection, RejectionReason

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_MIN_WITHDRAWAL = "minimum_withdrawal"

parameters = [
    Parameter(
        name=PARAM_MIN_WITHDRAWAL,
        level=ParameterLevel.TEMPLATE,
        description="The minimum amount that can be withdrawn from the account"
        " in a single transaction.",
        display_name="Minimum Withdrawal Amount",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("0.01"),
    ),
]


def validate(
    *, vault: SmartContractVault, postings: utils.PostingInstructionListAlias, denomination: str
) -> Optional[Rejection]:
    """
    Reject the posting if the value is less than the minimum allowed withdrawal limit.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions that are being processed and need to be reviewed
    to ensure each one is under the single withdrawal limit
    :param denomination: the denomination of the account
    :return: rejection if the limit conditions are not met
    """
    minimum_withdrawal: Decimal = utils.get_parameter(vault, PARAM_MIN_WITHDRAWAL)
    if minimum_withdrawal:
        for posting in postings:
            withdrawal_value = utils.get_available_balance(
                balances=posting.balances(), denomination=denomination
            )

            if withdrawal_value < 0 and abs(withdrawal_value) < minimum_withdrawal:
                minimum_withdrawal = Decimal(minimum_withdrawal).quantize(Decimal("1.e-3"))
                return Rejection(
                    message=f"Transaction amount {round(abs(withdrawal_value), 5).normalize()} "
                    f"{denomination} is less than the minimum withdrawal amount "
                    f"{str(minimum_withdrawal).rstrip('0').rstrip('.')} {denomination}.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )

    return None
