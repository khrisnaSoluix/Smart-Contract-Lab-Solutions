# standard libs
from decimal import Decimal

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import NumberShape, Parameter, ParameterLevel, ParameterUpdatePermission

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_TOTAL_REPAYMENT_COUNT = "total_repayment_count"
total_repayment_count_parameter = Parameter(
    name=PARAM_TOTAL_REPAYMENT_COUNT,
    shape=NumberShape(min_value=Decimal(1), step=Decimal(1)),
    level=ParameterLevel.INSTANCE,
    description="The total number of repayments to be made, at a monthly frequency"
    " unless a repayment_frequency parameter is present.",
    display_name="Total Repayment Count",
    default_value=Decimal(12),
    # editable to support loan top-ups
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)


def get_total_repayment_count_parameter(vault: SmartContractVault) -> int:
    return int(utils.get_parameter(vault, name=PARAM_TOTAL_REPAYMENT_COUNT))
