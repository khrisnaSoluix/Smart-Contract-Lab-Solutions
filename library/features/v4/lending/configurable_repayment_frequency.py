# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

# features
import library.features.v4.common.utils as utils
import library.features.v4.lending.due_amount_calculation as due_amount_calculation

# contracts api
from contracts_api import (
    DateShape,
    EndOfMonthSchedule,
    OptionalShape,
    OptionalValue,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    ScheduledEvent,
    ScheduleExpression,
    ScheduleFailover,
    StringShape,
    UnionItem,
    UnionItemValue,
    UnionShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

LoanTerms = NamedTuple(
    "LoanTerms",
    [
        ("elapsed", int),
        ("remaining", int),
    ],
)

# Frequencies
MONTHLY = "monthly"
WEEKLY = "weekly"
FORTNIGHTLY = "fortnightly"

FREQUENCY_MAP = {
    WEEKLY: relativedelta(days=7),
    FORTNIGHTLY: relativedelta(days=14),
    MONTHLY: relativedelta(months=1),
}
TERM_UNIT_MAP = {
    WEEKLY: "week(s)",
    FORTNIGHTLY: "fortnight(s)",
    MONTHLY: "month(s)",
}
DATETIME_MIN_UTC = datetime.min.replace(tzinfo=ZoneInfo("UTC"))
DATETIME_MAX_UTC = datetime.max.replace(tzinfo=ZoneInfo("UTC"))

PARAM_REPAYMENT_FREQUENCY = "repayment_frequency"
PARAM_LOAN_END_DATE = "loan_end_date"
PARAM_NEXT_REPAYMENT_DATE = "next_repayment_date"
PARAM_REMAINING_TERM = "remaining_term"

repayment_frequency_parameter = Parameter(
    name=PARAM_REPAYMENT_FREQUENCY,
    shape=OptionalShape(
        shape=UnionShape(
            items=[
                UnionItem(key="weekly", display_name="Weekly"),
                UnionItem(key="fortnightly", display_name="Fortnightly"),
                UnionItem(key="monthly", display_name="Monthly"),
            ]
        ),
    ),
    level=ParameterLevel.INSTANCE,
    description="The frequency at which repayments are made.",
    display_name="Repayment Frequency",
    update_permission=ParameterUpdatePermission.FIXED,
    default_value=OptionalValue(UnionItemValue(key="monthly")),
)

loan_end_date_parameter = Parameter(
    name=PARAM_LOAN_END_DATE,
    shape=DateShape(min_date=DATETIME_MIN_UTC, max_date=DATETIME_MAX_UTC),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Contractual end date of the loan",
    display_name="Loan End Date",
)

next_repayment_date_parameter = Parameter(
    name=PARAM_NEXT_REPAYMENT_DATE,
    shape=DateShape(min_date=DATETIME_MIN_UTC, max_date=DATETIME_MAX_UTC),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Next repayment date",
    display_name="Next Repayment Date",
)

remaining_term_parameter = Parameter(
    name=PARAM_REMAINING_TERM,
    shape=StringShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="The remaining term for the loan",
    display_name="Remaining Term",
)

derived_parameters = [
    loan_end_date_parameter,
    next_repayment_date_parameter,
    remaining_term_parameter,
]

all_parameters = [
    *derived_parameters,
    repayment_frequency_parameter,
]


def get_repayment_frequency_parameter(vault: SmartContractVault) -> str:
    return str(
        utils.get_parameter(
            vault=vault,
            name=PARAM_REPAYMENT_FREQUENCY,
            is_union=True,
            is_optional=True,
            default_value=UnionItemValue(key="monthly"),
        )
    )


def get_due_amount_calculation_schedule(
    vault: SmartContractVault,
    first_due_amount_calculation_datetime: datetime,
    repayment_frequency: str = "monthly",
) -> dict[str, ScheduledEvent]:
    """
    Get a due amount calculation schedule that occurs at the specified frequency, starting at the
    specified date, and using the `due_amount_calculation_<>` schedule time parameters. The schedule
    will require amending only for `fortnightly` schedules using the
    `get_next_fortnightly_schedule_expression` function.
    :param vault: the Vault object
    :param first_due_amount_calculation_datetime: datetime representing the date on which the first
    due amount calculation should occur. Time component will be ignored
    :param repayment_frequency: the frequency at which repayments occur. One of monthly, weekly or
    fortnightly
    :return: a dictionary containing the due amount calculation schedule
    """

    hour, minute, second = utils.get_schedule_time_from_parameters(
        vault,
        parameter_prefix=due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX,
    )
    # the start_datetime is exclusive when using the EndOfMonthSchedule, so it must be set to before
    # the earliest first due amount calc which is 1s before 00:00:00 due to scheduler granularity
    start_datetime = first_due_amount_calculation_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - relativedelta(seconds=1)

    if repayment_frequency == "monthly":
        due_amount_calculation_schedule = ScheduledEvent(
            start_datetime=start_datetime,
            schedule_method=EndOfMonthSchedule(
                day=first_due_amount_calculation_datetime.day,
                hour=hour,
                minute=minute,
                second=second,
                failover=ScheduleFailover.FIRST_VALID_DAY_BEFORE,
            ),
        )
    else:
        schedule_expression = ScheduleExpression(
            hour=hour,
            minute=minute,
            second=second,
        )

        if repayment_frequency == "weekly":
            schedule_expression.day_of_week = first_due_amount_calculation_datetime.weekday()
        elif repayment_frequency == "fortnightly":
            # fortnightly schedules are just regular schedules
            # that will need amending after each run
            schedule_expression.day = first_due_amount_calculation_datetime.day

        due_amount_calculation_schedule = ScheduledEvent(
            start_datetime=start_datetime, expression=schedule_expression
        )

    return {due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT: due_amount_calculation_schedule}


def get_next_fortnightly_schedule_expression(effective_date: datetime) -> ScheduleExpression:
    """
    Get the next fortnightly schedule expression for the account.
    :param effective_date: date as of which the next repayment date is calculated
    :return: the next fortnightly schedule expression
    """
    next_due_date = effective_date + FREQUENCY_MAP[FORTNIGHTLY]
    return utils.one_off_schedule_expression(next_due_date)


def get_next_due_amount_calculation_date(
    vault: SmartContractVault,
    effective_date: datetime,
    total_repayment_count: int,
    repayment_frequency: str,
) -> datetime:
    """
    Determine the next repayment date for the account. If there are no more repayments left,
    the last repayment date is returned.

    :param vault: Vault object for the account in question
    :param effective_date: date as of which the next repayment date is calculated
    :param total_repayment_count: the number of expected repayments at account creation
    :param repayment_frequency: the account's due amount calculation schedule frequency
    :return: datetime representing the next repayment date
    """
    account_creation_date = vault.get_account_creation_datetime().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    next_repayment_date = account_creation_date

    while next_repayment_date < effective_date and total_repayment_count > 0:
        next_repayment_date += FREQUENCY_MAP[repayment_frequency]
        total_repayment_count -= 1

    return next_repayment_date


def get_elapsed_and_remaining_terms(
    account_creation_date: datetime,
    effective_date: datetime,
    total_repayment_count: int,
    repayment_frequency: str,
) -> LoanTerms:
    """
    Calculates the elapsed and remaining terms for a loan at a given date, based on the total
    repayment count and the repayment frequency.
    :param account_creation_date: date on which the loan was created
    :param effective_date: date as of which the calculation is made
    :param total_repayment_count: total number of repayments at the start of the loan
    :param repayment_frequency: repayment frequency
    return: a dictionary with keys elapsed and remaining, providing number of elapsed and remaining
    terms according to the T&Cs at the start of the loan.
    """
    if repayment_frequency == MONTHLY:
        elapsed_terms = relativedelta(effective_date.date(), account_creation_date.date()).months
    else:
        elapsed_days = (effective_date.date() - account_creation_date.date()).days
        elapsed_terms = elapsed_days // FREQUENCY_MAP[repayment_frequency].days
    return LoanTerms(elapsed=elapsed_terms, remaining=total_repayment_count - elapsed_terms)
