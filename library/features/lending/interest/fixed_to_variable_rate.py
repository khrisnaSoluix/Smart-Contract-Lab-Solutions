from datetime import datetime
from decimal import Decimal
from typing import Callable, NamedTuple

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    Level,
    NumberShape,
    Parameter,
    UpdatePermission,
    Vault,
)
import library.features.common.utils as utils
import library.features.lending.interest.fixed_rate as fixed_rate
import library.features.lending.interest.variable_rate as variable_rate

parameters = [
    Parameter(
        name="fixed_interest_term",
        shape=NumberShape(min_value=Decimal(0), step=Decimal(1)),
        level=Level.INSTANCE,
        description="The agreed length of the fixed rate portion of the mortgage (in months).",
        display_name="Fixed rate Mortgage term (months)",
        default_value=Decimal(0),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    *fixed_rate.parameters,
    *variable_rate.parameters,
]


def calculate_daily_accrual_amount(
    vault: Vault, accrual_capital: Decimal, effective_date: datetime, elapsed_term_in_month: int
) -> Decimal:
    is_fixed_interest = is_within_fixed_rate_term(vault, elapsed_term_in_month)
    if is_fixed_interest:
        return fixed_rate.calculate_daily_accrual_amount(vault, accrual_capital, effective_date)
    else:
        return variable_rate.calculate_daily_accrual_amount(vault, accrual_capital, effective_date)


def get_daily_interest_rate(vault: Vault, effective_date: datetime, elapsed_term_in_month: int):
    is_fixed_interest = is_within_fixed_rate_term(vault, elapsed_term_in_month)
    if is_fixed_interest:
        return fixed_rate.get_daily_interest_rate(vault, effective_date)
    else:
        return variable_rate.get_daily_interest_rate(vault, effective_date)


def is_within_fixed_rate_term(vault: Vault, elapsed_term_in_months: int) -> bool:
    fixed_rate_term: int = int(utils.get_parameter(vault, "fixed_interest_term"))
    return elapsed_term_in_months <= fixed_rate_term


def should_trigger_reamortisation(
    vault: Vault,
    elapsed_term_in_months: int,
    due_amount_schedule_details: utils.ScheduleDetails,
    **kwargs
) -> bool:
    """
    Determines if reamortisation is required by checking if we have flipped from fixed to
    variable rates or if the variable rate has changed since the last due amount schedule run

    :param vault: Vault object used to fetch balances/parameters
    :param elapsed_term_in_months: the number of elapsed terms in months
    :param due_amount_schedule_details: the details of the due amount schedule
    :param kwargs: unused
    :return: True if reamortisation is needed, False otherwise
    """
    is_rate_type_changed = not is_within_fixed_rate_term(
        vault, elapsed_term_in_months
    ) and is_within_fixed_rate_term(vault, elapsed_term_in_months - 1)

    is_rate_value_changed = not is_within_fixed_rate_term(
        vault, elapsed_term_in_months
    ) and variable_rate.should_trigger_reamortisation(
        vault, elapsed_term_in_months, due_amount_schedule_details, **kwargs
    )
    # TODO: should we also be checking whether the fixed rate == variable rate?
    return is_rate_type_changed or is_rate_value_changed


FixedToVariableRate = NamedTuple(
    "FixedToVariableRate",
    [
        ("parameters", list),
        ("calculate_daily_accrual_amount", Callable),
        ("get_daily_interest_rate", Callable),
        ("should_trigger_reamortisation", Callable),
    ],
)

feature = FixedToVariableRate(
    parameters=parameters,
    calculate_daily_accrual_amount=calculate_daily_accrual_amount,
    get_daily_interest_rate=get_daily_interest_rate,
    should_trigger_reamortisation=should_trigger_reamortisation,
)
