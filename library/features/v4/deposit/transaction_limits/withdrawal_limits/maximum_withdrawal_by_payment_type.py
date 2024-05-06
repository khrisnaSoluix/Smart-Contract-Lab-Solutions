# standard libs
from decimal import Decimal
from json import dumps
from typing import Optional

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import Parameter, ParameterLevel, Rejection, RejectionReason, StringShape

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# String constants
PAYMENT_TYPE = "PAYMENT_TYPE"
PARAM_MAX_WITHDRAWAL_BY_TYPE = "maximum_payment_type_withdrawal"

parameters = [
    Parameter(
        name=PARAM_MAX_WITHDRAWAL_BY_TYPE,
        level=ParameterLevel.TEMPLATE,
        description="The maximum single withdrawal allowed for each payment type.",
        display_name="Payment Type Limits",
        shape=StringShape(),
        default_value=dumps(
            {
                "ATM": "30000",
            }
        ),
    ),
]


def validate(
    *, vault: SmartContractVault, postings: utils.PostingInstructionListAlias, denomination: str
) -> Optional[Rejection]:
    """
    Reject the posting if the withdrawal value exceeds the PAYMENT_TYPE limit.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions that are being processed and need to be reviewed
    to ensure they are under the limit by payment type
    :param denomination: the denomination of the account
    :return: rejection if the limit conditions are not met
    """
    max_withdrawal_by_payment_type: dict[str, str] = utils.get_parameter(
        vault, PARAM_MAX_WITHDRAWAL_BY_TYPE, is_json=True
    )
    for posting in postings:
        payment_type = posting.instruction_details.get(PAYMENT_TYPE)

        if payment_type:
            # Payment type has a max withdrawal limit defined
            if payment_type in max_withdrawal_by_payment_type:
                withdrawal_limit = Decimal(max_withdrawal_by_payment_type[payment_type])
                posting_value = utils.get_available_balance(
                    balances=posting.balances(), denomination=denomination
                )
                # The posting value will be negative for debits on liability accounts
                if posting_value > 0:
                    continue
                elif withdrawal_limit < abs(posting_value):
                    return Rejection(
                        message=f"Transaction amount {abs(posting_value):0.2f} {denomination} is "
                        f"more than the maximum withdrawal amount {withdrawal_limit} "
                        f"{denomination} allowed for the the payment type {payment_type}.",
                        reason_code=RejectionReason.AGAINST_TNC,
                    )
            else:
                # If Payment type doesnt have a max withdrawal limit defined by default no limit
                # will be applied
                continue

    return None
