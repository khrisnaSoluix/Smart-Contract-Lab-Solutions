# standard libs
from datetime import datetime
from typing import Optional

# features
import library.features.common.common_parameters as common_parameters
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    UnionItem,
    UnionItemValue,
    UnionShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# feature constants
DAYS = "days"
MONTHS = "months"

# Parameters
PARAM_CAPITALISE_ACCRUED_INTEREST_ON_ACCOUNT_CLOSURE = (
    "capitalise_accrued_interest_on_account_closure"
)
capitalise_accrued_interest_on_account_closure_param = Parameter(
    name=PARAM_CAPITALISE_ACCRUED_INTEREST_ON_ACCOUNT_CLOSURE,
    level=ParameterLevel.TEMPLATE,
    description="If true, on account closure accrued interest that has not yet been applied "
    "will be applied to a customer account. If false, the accrued interest will be forfeited.",
    display_name="Capitalise Accrued Interest On Account Closure",
    shape=common_parameters.BooleanShape,
    default_value=common_parameters.BooleanValueFalse,
)


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

PARAM_TERM = "term"
term_param = Parameter(
    name=PARAM_TERM,
    shape=UnionShape(
        items=[
            UnionItem(key="1", display_name="1"),
            UnionItem(key="3", display_name="3"),
            UnionItem(key="6", display_name="6"),
            UnionItem(key="12", display_name="12"),
            UnionItem(key="0", display_name="On call")
        ]
    ),
    level=ParameterLevel.TEMPLATE,
    description="The term of time deposit",
    display_name="Time Deposit Term",
    default_value=UnionItemValue(key="12"),
    update_permission=ParameterUpdatePermission.FIXED,
)


def get_capitalise_accrued_interest_on_account_closure_parameter(
    *,
    vault: SmartContractVault,
    effective_datetime: Optional[datetime] = None,
) -> bool:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_CAPITALISE_ACCRUED_INTEREST_ON_ACCOUNT_CLOSURE,
        at_datetime=effective_datetime,
        is_boolean=True,
    )


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