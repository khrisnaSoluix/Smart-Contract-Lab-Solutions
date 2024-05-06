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

PARAM_MINIMUM_LOAN_PRINCIPAL = "minimum_loan_principal"

parameters = [
    Parameter(
        name=PARAM_MINIMUM_LOAN_PRINCIPAL,
        shape=OptionalShape(shape=NumberShape(min_value=Decimal("0"))),
        level=ParameterLevel.TEMPLATE,
        description="The minimum principal amount for each loan.",
        display_name="Minimum Loan Principal",
        default_value=OptionalValue(Decimal("50")),
    ),
]


def validate(
    vault: SmartContractVault, posting_instruction: utils.PostingInstructionTypeAlias
) -> Optional[Rejection]:
    if minimum_loan_amount := utils.get_parameter(
        vault=vault, name=PARAM_MINIMUM_LOAN_PRINCIPAL, is_optional=True
    ):
        denomination = utils.get_parameter(vault=vault, name="denomination")
        posting_amount = utils.get_available_balance(
            balances=posting_instruction.balances(), denomination=denomination
        )
        if 0 < posting_amount < minimum_loan_amount:
            return Rejection(
                message=f"Cannot create loan smaller than minimum loan amount limit of: "
                f"{minimum_loan_amount}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
    return None
