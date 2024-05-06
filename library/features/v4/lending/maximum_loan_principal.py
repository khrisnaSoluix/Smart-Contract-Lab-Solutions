# standard libs
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    NumberShape,
    OptionalShape,
    OptionalValue,
    Parameter,
    ParameterLevel,
    Rejection,
    RejectionReason,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_MAXIMUM_LOAN_PRINCIPAL = "maximum_loan_principal"

parameters = [
    Parameter(
        name=PARAM_MAXIMUM_LOAN_PRINCIPAL,
        shape=OptionalShape(shape=NumberShape(min_value=Decimal("0"))),
        level=ParameterLevel.TEMPLATE,
        description="The maximum principal amount for each loan.",
        display_name="Maximum Loan Principal",
        default_value=OptionalValue(Decimal("1000")),
    ),
]


def validate(
    vault: SmartContractVault, posting_instruction: utils.PostingInstructionTypeAlias
) -> Optional[Rejection]:
    if maximum_loan_amount := utils.get_parameter(
        vault=vault, name=PARAM_MAXIMUM_LOAN_PRINCIPAL, is_optional=True
    ):
        denomination = utils.get_parameter(vault=vault, name="denomination")
        posting_amount = utils.get_available_balance(
            balances=posting_instruction.balances(), denomination=denomination
        )
        if posting_amount > maximum_loan_amount:
            return Rejection(
                message=f"Cannot create loan larger than maximum loan amount limit of: "
                f"{maximum_loan_amount}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
    return None
