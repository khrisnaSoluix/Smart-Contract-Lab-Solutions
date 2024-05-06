from datetime import datetime
from decimal import Decimal
from typing import Optional, Callable, NamedTuple

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    Level,
    NumberKind,
    NumberShape,
    Parameter,
    UpdatePermission,
    Vault,
)
import library.features.common.utils as utils

parameters = [
    # Instance Parameters
    Parameter(
        name="variable_rate_adjustment",
        shape=NumberShape(kind=NumberKind.PERCENTAGE, min_value=-1, max_value=1, step=0.0001),
        level=Level.INSTANCE,
        description="Account level adjustment to be added to variable interest rate, "
        "can be positive, negative or zero.",
        display_name="Variable rate adjustment",
        default_value=Decimal("0.00"),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    # Template Parameters
    Parameter(
        name="variable_interest_rate",
        shape=utils.PositiveRateShape,
        level=Level.TEMPLATE,
        description="The annual rate of the mortgage to be applied after the fixed rate term.",
        display_name="Variable interest rate (p.a.)",
        default_value=Decimal("0.129971"),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
]


def calculate_daily_accrual_amount(
    vault: Vault, accrual_capital: Decimal, effective_date: datetime
) -> Decimal:
    daily_rate = get_daily_interest_rate(vault, effective_date)
    amount_to_accrue = utils.round_decimal(abs(accrual_capital * daily_rate), decimal_places=5)
    return amount_to_accrue


def get_daily_interest_rate(vault: Vault, effective_date: datetime) -> Decimal:
    annual_rate = Decimal(utils.get_parameter(vault, "variable_interest_rate"))
    annual_rate += Decimal(utils.get_parameter(vault, "variable_rate_adjustment"))

    days_in_year = utils.get_parameter(vault, "days_in_year", union=True)
    return utils.yearly_to_daily_rate(annual_rate, effective_date.year, days_in_year=days_in_year)


def should_trigger_reamortisation(
    vault: Vault,
    elapsed_term_in_months: Optional[int],
    due_amount_schedule_details: utils.ScheduleDetails,
    **kwargs
) -> bool:
    """
    Determines if reamortisation is required by checking if the variable rate has changed since
    the last time the due amount schedule ran

    :param vault: Vault object used to fetch balances/parameters
    :param elapsed_term_in_months: the number of elapsed terms in months
    :param due_amount_schedule_details: the details of the due amount schedule
    :param kwargs: unused
    :return: True if reamortisation is needed, False otherwise
    """

    # During variable rate period the rate is adjusted after the last repayment date
    return _rate_adjusted_since_last_application(vault, due_amount_schedule_details)


def _rate_adjusted_since_last_application(
    vault: Vault, due_amount_schedule_details: utils.ScheduleDetails
) -> bool:
    last_application_execution_event = due_amount_schedule_details.last_execution_time

    loan_start_date: datetime = utils.get_parameter(vault, "loan_start_date")
    last_variable_rate_adjustment_change_date: datetime = vault.get_parameter_timeseries(
        name="variable_rate_adjustment"
    )[-1][0]
    last_variable_interest_rate_change_date: datetime = vault.get_parameter_timeseries(
        name="variable_interest_rate"
    )[-1][0]

    last_rate_change_date = max(
        loan_start_date,
        last_variable_rate_adjustment_change_date,
        last_variable_interest_rate_change_date,
    )

    return (
        last_application_execution_event is None
        or last_rate_change_date > last_application_execution_event
    )


VariableRate = NamedTuple(
    "VariableRate",
    [
        ("parameters", list),
        ("calculate_daily_accrual_amount", Callable),
        ("get_daily_interest_rate", Callable),
        ("should_trigger_reamortisation", Callable),
    ],
)

feature = VariableRate(
    parameters=parameters,
    calculate_daily_accrual_amount=calculate_daily_accrual_amount,
    get_daily_interest_rate=get_daily_interest_rate,
    should_trigger_reamortisation=should_trigger_reamortisation,
)
