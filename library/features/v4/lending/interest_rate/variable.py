# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_interfaces as lending_interfaces

# contracts api
from contracts_api import (
    BalanceDefaultDict,
    NumberShape,
    OptionalShape,
    OptionalValue,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_ANNUAL_INTEREST_RATE_CAP = "annual_interest_rate_cap"
PARAM_ANNUAL_INTEREST_RATE_FLOOR = "annual_interest_rate_floor"
PARAM_VARIABLE_RATE_ADJUSTMENT = "variable_rate_adjustment"
PARAM_VARIABLE_INTEREST_RATE = "variable_interest_rate"


parameters = [
    # Instance Parameters
    Parameter(
        name=PARAM_VARIABLE_RATE_ADJUSTMENT,
        level=ParameterLevel.INSTANCE,
        description="Account level adjustment to be added to variable interest rate, "
        "can be positive, negative or zero.",
        display_name="Variable Rate Adjustment",
        shape=NumberShape(step=Decimal("0.01")),
        default_value=Decimal("0.00"),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    # Template Parameters
    Parameter(
        name=PARAM_VARIABLE_INTEREST_RATE,
        level=ParameterLevel.TEMPLATE,
        description="The annual interest rate.",
        display_name="Variable Interest Rate (p.a.)",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.000001")),
        default_value=Decimal("0.129971"),
    ),
    Parameter(
        name=PARAM_ANNUAL_INTEREST_RATE_CAP,
        level=ParameterLevel.TEMPLATE,
        description="The maximum annual interest rate for a variable interest loan.",
        display_name="Variable Annual Interest Rate Cap (p.a.)",
        shape=OptionalShape(shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.000001"))),
        default_value=OptionalValue(value=Decimal("1")),
    ),
    Parameter(
        name=PARAM_ANNUAL_INTEREST_RATE_FLOOR,
        level=ParameterLevel.TEMPLATE,
        description="The minimum annual interest rate for a variable interest loan.",
        display_name="Variable Annual Interest Rate Floor (p.a.)",
        shape=OptionalShape(shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.000001"))),
        default_value=OptionalValue(value=Decimal("0")),
    ),
]


def get_daily_interest_rate(
    vault: SmartContractVault,
    effective_datetime: datetime,
    # required for interface
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    annual_rate = get_annual_interest_rate(vault=vault, effective_datetime=effective_datetime)
    days_in_year = utils.get_parameter(
        vault, "days_in_year", is_union=True, at_datetime=effective_datetime
    )
    return utils.yearly_to_daily_rate(effective_datetime, annual_rate, days_in_year)


def get_monthly_interest_rate(
    vault: SmartContractVault,
    effective_datetime: Optional[datetime] = None,
    # required for interface
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    annual_rate = get_annual_interest_rate(vault=vault, effective_datetime=effective_datetime)
    return utils.yearly_to_monthly_rate(annual_rate)


def get_annual_interest_rate(
    vault: SmartContractVault,
    effective_datetime: Optional[datetime] = None,
    # required for interface
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    """
    Determines the annual interest rate, including any variable rate adjustment and
    accounts for any maximum or minimum interest rate limits that may be set.
    """

    annual_rate = Decimal(
        utils.get_parameter(
            vault=vault, name=PARAM_VARIABLE_INTEREST_RATE, at_datetime=effective_datetime
        )
    ) + Decimal(
        utils.get_parameter(
            vault=vault, name=PARAM_VARIABLE_RATE_ADJUSTMENT, at_datetime=effective_datetime
        )
    )

    interest_rate_cap: Decimal = utils.get_parameter(
        vault=vault,
        name=PARAM_ANNUAL_INTEREST_RATE_CAP,
        is_optional=True,
        default_value=Decimal("inf"),
        at_datetime=effective_datetime,
    )
    interest_rate_floor: Decimal = utils.get_parameter(
        vault=vault,
        name=PARAM_ANNUAL_INTEREST_RATE_FLOOR,
        is_optional=True,
        default_value=Decimal("-inf"),
        at_datetime=effective_datetime,
    )

    return max(
        min(
            annual_rate,
            interest_rate_cap,
        ),
        interest_rate_floor,
    )


def should_trigger_reamortisation(
    vault: SmartContractVault,
    period_start_datetime: datetime,
    period_end_datetime: datetime,
    elapsed_term: Optional[int] = None,
) -> bool:
    """
    Determines whether the monthly interest rate at the period end differs from period start. If so,
    there must have been a change to the annual interest rate which will result in reamortisation.

    :param vault: vault object for the account
    :param period_start_datetime: datetime of the period start, typically this will be the datetime
    of the previous due amount calculation. This is intentionally not an Optional[] argument since
    period_start_datetime=None would result in comparing the monthly interest rate between latest()
    and period_end_datetime.
    :param period_end_datetime: datetime of the period end, typically the effective_datetime of the
    current due amount calculation event
    :param elapsed_term: Not used but required for the interface
    :return bool: Whether the monthly interest rate at the period end differs from period start
    """

    return get_monthly_interest_rate(
        vault=vault, effective_datetime=period_start_datetime
    ) != get_monthly_interest_rate(vault=vault, effective_datetime=period_end_datetime)


interest_rate_interface = lending_interfaces.InterestRate(
    get_daily_interest_rate=get_daily_interest_rate,
    get_monthly_interest_rate=get_monthly_interest_rate,
    get_annual_interest_rate=get_annual_interest_rate,
)

VariableReamortisationCondition = lending_interfaces.ReamortisationCondition(
    should_trigger_reamortisation=should_trigger_reamortisation
)
