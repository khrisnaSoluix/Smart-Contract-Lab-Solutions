from datetime import datetime
from decimal import Decimal
from typing import Callable, NamedTuple, Optional

# inception lib
from inception_sdk.vault.contracts.types_extension import Level, Parameter, UpdatePermission, Vault
import library.features.common.utils as utils

parameters = [
    # Instance parameters
    Parameter(
        name="fixed_interest_rate",
        shape=utils.PositiveRateShape,
        level=Level.INSTANCE,
        description="Gross Interest Rate",
        display_name="Rate paid on positive balances",
        default_value=Decimal("0.135"),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
]


def calculate_daily_accrual_amount(
    vault: Vault, accrual_capital: Decimal, effective_date: datetime
) -> Decimal:
    daily_rate = get_daily_interest_rate(vault, effective_date)
    amount_to_accrue = utils.round_decimal(
        abs(accrual_capital * daily_rate),
        decimal_places=5,
    )
    return amount_to_accrue


def get_daily_interest_rate(vault: Vault, effective_date: datetime) -> Decimal:
    annual_rate = Decimal(utils.get_parameter(vault, "fixed_interest_rate"))
    days_in_year = str(utils.get_parameter(vault, "days_in_year", union=True))
    return utils.yearly_to_daily_rate(annual_rate, effective_date.year, days_in_year=days_in_year)


def get_monthly_interest_rate(vault: Vault) -> Decimal:
    return Decimal(utils.get_parameter(vault, "fixed_interest_rate")) / 12


def should_trigger_reamortisation(
    vault: Optional[Vault] = None,
    elapsed_term_in_months: Optional[int] = None,
    due_amount_schedule_details: Optional[utils.ScheduleDetails] = None,
    **kwargs
) -> bool:
    """
    Always returns False, but required to implement the interface

    :param vault: Vault object used to fetch balances/parameters
    :param elapsed_term_in_months: the number of elapsed terms in months
    :param due_amount_schedule_details: the details of the due amount schedule
    :param kwargs: unused
    :return: True if reamortisation is needed, False otherwise
    """
    return False


FixedRate = NamedTuple(
    "FixedRate",
    [
        ("parameters", list),
        ("calculate_daily_accrual_amount", Callable),
        ("get_daily_interest_rate", Callable),
        ("get_monthly_interest_rate", Callable),
        ("should_trigger_reamortisation", Callable),
    ],
)

feature = FixedRate(
    parameters=parameters,
    calculate_daily_accrual_amount=calculate_daily_accrual_amount,
    get_daily_interest_rate=get_daily_interest_rate,
    get_monthly_interest_rate=get_monthly_interest_rate,
    should_trigger_reamortisation=should_trigger_reamortisation,
)
