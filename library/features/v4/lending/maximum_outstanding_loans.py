# standard libs
from typing import Optional

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import NumberShape, Parameter, ParameterLevel, Rejection, RejectionReason

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SuperviseeContractVault,
)

PARAM_MAXIMUM_NUMBER_OF_OUTSTANDING_LOANS = "maximum_number_of_outstanding_loans"

parameters = [
    Parameter(
        name=PARAM_MAXIMUM_NUMBER_OF_OUTSTANDING_LOANS,
        shape=NumberShape(min_value=1, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The maximum number of loans allowed to be open concurrently.",
        display_name="Maximum Number Of Outstanding Loans.",
        default_value=1,
    ),
]


def validate(
    main_vault: SuperviseeContractVault,
    loans: list[SuperviseeContractVault],
) -> Optional[Rejection]:
    """
    Validate the number of outstanding loans is below the amount specified by a parameter
    :param main_vault: the supervisee vault object that defines the max number of loans allowed
    :param loans: a list of supervised loan vaults
    :return: rejection if the number of loan vaults is greater than or equal to the allowed number
    """

    maximum_number_of_outstanding_loans = _get_max_outstanding_loans_parameter(
        vault=main_vault,
    )
    if len(loans) >= maximum_number_of_outstanding_loans:
        return Rejection(
            message="Cannot create new loan due to outstanding loan limit being exceeded. "
            + f"Current number of loans: {len(loans)}, "
            + f"maximum loan limit: {maximum_number_of_outstanding_loans}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


def _get_max_outstanding_loans_parameter(vault: SuperviseeContractVault) -> int:
    max_outstanding_loans: int = utils.get_parameter(
        vault=vault, name=PARAM_MAXIMUM_NUMBER_OF_OUTSTANDING_LOANS
    )
    return max_outstanding_loans
