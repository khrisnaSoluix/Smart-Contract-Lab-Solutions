# standard libs
from datetime import datetime
from typing import Optional

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    DenominationShape,
    Parameter,
    ParameterLevel,
    UnionItem,
    UnionItemValue,
    UnionShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

BooleanShape = UnionShape(
    items=[
        UnionItem(key="True", display_name="True"),
        UnionItem(key="False", display_name="False"),
    ]
)

BooleanValueTrue = UnionItemValue(key="True")
BooleanValueFalse = UnionItemValue(key="False")


PARAM_DENOMINATION = "denomination"

denomination_parameter = Parameter(
    name=PARAM_DENOMINATION,
    shape=DenominationShape(),
    level=ParameterLevel.TEMPLATE,
    description="Currency in which the product operates.",
    display_name="Denomination",
    default_value="GBP",
)


def get_denomination_parameter(
    vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    denomination: str = utils.get_parameter(
        vault=vault, name=PARAM_DENOMINATION, at_datetime=effective_datetime
    )
    return denomination
