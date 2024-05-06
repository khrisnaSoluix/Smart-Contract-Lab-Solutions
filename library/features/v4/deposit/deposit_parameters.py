# standard libs
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

# features
import library.features.common.common_parameters as common_parameters
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    NumberShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    UnionItem,
    UnionItemValue,
    UnionShape,
    DateShape
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# feature constants
DAYS = "days"
MONTHS = "months"
PARAM_TERM = "term"
PARAM_ACTIVATION_DATE = "activation_date"

term_param = Parameter(
    name=PARAM_TERM,
    shape=NumberShape(min_value=1, step=1),
    level=ParameterLevel.INSTANCE,
    description="The term length of the product.",
    display_name="Term",
    update_permission=ParameterUpdatePermission.FIXED,
    default_value=3,
)
activation_date_param = [
    Parameter(
        name=PARAM_ACTIVATION_DATE,
        shape=DateShape(
                min_date=datetime.min.replace(tzinfo=ZoneInfo("UTC")),
                max_date=datetime.max.replace(tzinfo=ZoneInfo("UTC")),
            ),
        level=ParameterLevel.INSTANCE,
        description="The date of deposit account will be activated",
        display_name="Activation Date",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=datetime.min.replace(tzinfo=ZoneInfo("UTC")),
    )
]

PARAM_TERM_UNIT = "term_unit"
term_unit_param = Parameter(
    name=PARAM_TERM_UNIT,
    shape=UnionShape(
        items=[
            UnionItem(key=DAYS, display_name="Days"),
            UnionItem(key=MONTHS, display_name="Months"),
        ]
    ),
    level=ParameterLevel.TEMPLATE,
    description="The unit at which the term is applied.",
    display_name="Term Unit (days or months)",
    default_value=UnionItemValue(key="months"),
)

term_parameters = [term_param, term_unit_param]


def get_term_parameter(
    *,
    vault: SmartContractVault,
    effective_datetime: Optional[datetime] = None,
) -> int:
    return int(utils.get_parameter(vault=vault, name=PARAM_TERM, at_datetime=effective_datetime))


def get_term_unit_parameter(
    *,
    vault: SmartContractVault,
    effective_datetime: Optional[datetime] = None,
) -> str:
    return str(
        utils.get_parameter(
            vault=vault, name=PARAM_TERM_UNIT, at_datetime=effective_datetime, is_union=True
        )
    )
