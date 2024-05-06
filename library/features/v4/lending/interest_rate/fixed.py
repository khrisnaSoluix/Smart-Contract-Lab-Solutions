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
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PARAM_FIXED_INTEREST_RATE = "fixed_interest_rate"
parameters = [
    Parameter(
        name=PARAM_FIXED_INTEREST_RATE,
        level=ParameterLevel.INSTANCE,
        description="The fixed annual rate of the loan (p.a).",
        display_name="Fixed Interest Rate",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("0.00"),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
]


def get_annual_interest_rate(
    vault: SmartContractVault,
    effective_datetime: Optional[datetime] = None,
    # required for interface
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    return Decimal(
        utils.get_parameter(vault, "fixed_interest_rate", at_datetime=effective_datetime)
    )


def get_daily_interest_rate(
    vault: SmartContractVault,
    effective_datetime: datetime,
    # required for interface
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    annual_rate = get_annual_interest_rate(vault=vault)
    days_in_year = utils.get_parameter(vault, "days_in_year", is_union=True)
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


interest_rate_interface = lending_interfaces.InterestRate(
    get_daily_interest_rate=get_daily_interest_rate,
    get_monthly_interest_rate=get_monthly_interest_rate,
    get_annual_interest_rate=get_annual_interest_rate,
)

FixedReamortisationCondition = lending_interfaces.ReamortisationCondition(
    should_trigger_reamortisation=lambda vault, period_start_datetime, period_end_datetime, elapsed_term: False  # noqa: E501
)
