from datetime import datetime
from json import dumps as json_dumps
from typing import Callable, Optional, NamedTuple

# imports from the inception library
from inception_sdk.vault.contracts.types_extension import (
    FlagTimeseries,
    Level,
    Parameter,
    StringShape,
    Vault,
)
import library.features.common.utils as utils

repayment_blocking_flag_param_name = "repayment_blocking_flags"

accrual_blocking_parameters = [
    Parameter(
        name="accrual_blocking_flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="The list of flag definitions that block interest accruals",
        display_name="Accrual blocking flags",
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
]
due_amount_calculation_blocking_parameters = [
    Parameter(
        name="due_amount_calculation_blocking_flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="The list of flag definitions that block due amount calculation",
        display_name="Due amount calculation blocking flags",
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
]
overdue_amount_calculation_blocking_parameters = [
    Parameter(
        name="overdue_amount_calculation_blocking_flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="The list of flag definitions that block overdue amount calculation",
        display_name="Overdue amount calculation blocking flags",
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
]
delinquency_blocking_parameters = [
    Parameter(
        name="delinquency_blocking_flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="The list of flag definitions that block an account becoming delinquent",
        display_name="Delinquency blocking flags",
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
]
repayment_blocking_parameters = [
    Parameter(
        name=repayment_blocking_flag_param_name,
        shape=StringShape,
        level=Level.TEMPLATE,
        description="The list of flag definitions which block repayments.",
        display_name="Repayment blocking flag",
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
]
notification_blocking_parameters = [
    Parameter(
        name="notification_blocking_flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="The list of flag definitions that block notifications",
        display_name="Notification blocking flags",
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
]

all_parameters = [
    *accrual_blocking_parameters,
    *due_amount_calculation_blocking_parameters,
    *overdue_amount_calculation_blocking_parameters,
    *delinquency_blocking_parameters,
    *repayment_blocking_parameters,
    *notification_blocking_parameters,
]


def should_trigger_reamortisation(
    vault: Vault,
    elapsed_term_in_months: Optional[int],
    due_amount_schedule_details: utils.ScheduleDetails,
    **kwargs,
) -> bool:

    """
    Determines whether to trigger reamortisation due to a repayment holiday
    ending since the last time the due amount calculation schedule ran. Only returns
    True if a repayment holiday was active at last due amount calculation schedule date
    and no longer is as of current date.

    :param vault: The vault object containing parameters, flags, balances, etc.
    :param elapsed_term_in_months: only required to maintain the `should_trigger_reamortisation`
     interface as per library/features/lending/interfaces.md
    :param due_amount_schedule_details: The date of the last run of the due amount
    calculation schedule
    :param kwargs: populate key `due_amount_calculation_blocking_flags` with a list[FlagTimeseries]
    if these can't be extracted from the supplied `vault` (e.g. split supervisor/supervisee)
    :return: A boolean that determines whether reamortisation is necessary.
    """
    flag_timeseries = kwargs.get("due_amount_calculation_blocking_flags")

    return utils.is_flag_in_list_applied(
        vault,
        "due_amount_calculation_blocking_flags",
        application_timestamp=due_amount_schedule_details.last_execution_time,
        flag_timeseries=flag_timeseries,
    ) and not utils.is_flag_in_list_applied(
        vault, "due_amount_calculation_blocking_flags", flag_timeseries=flag_timeseries
    )


# blocking flag helpers
def is_accrual_blocked(vault: Vault, effective_date: datetime) -> bool:
    return utils.is_flag_in_list_applied(vault, "accrual_blocking_flags", effective_date)


def is_due_amount_calculation_blocked(
    vault: Vault,
    effective_date: datetime,
    due_amount_blocking_flags: Optional[list[FlagTimeseries]] = None,
) -> bool:
    return utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name="due_amount_calculation_blocking_flags",
        application_timestamp=effective_date,
        flag_timeseries=due_amount_blocking_flags,
    )


def is_overdue_amount_calculation_blocked(
    vault: Vault,
    effective_date: datetime,
    overdue_amount_calculation_blocking_flags: Optional[list[FlagTimeseries]] = None,
) -> bool:
    return utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name="overdue_amount_calculation_blocking_flags",
        application_timestamp=effective_date,
        flag_timeseries=overdue_amount_calculation_blocking_flags,
    )


def is_delinquency_blocked(vault: Vault, effective_date: datetime) -> bool:
    return utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name="delinquency_blocking_flags",
        application_timestamp=effective_date,
    )


def is_repayment_blocked(vault: Vault, effective_date: datetime) -> bool:
    return utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=repayment_blocking_flag_param_name,
        application_timestamp=effective_date,
    )


RepaymentHoliday = NamedTuple(
    "RepaymentHoliday",
    [
        ("all_parameters", list[Parameter]),
        ("accrual_blocking_parameters", list[Parameter]),
        ("due_amount_calculation_blocking_parameters", list[Parameter]),
        ("should_trigger_reamortisation", Callable[..., bool]),
        ("is_accrual_blocked", Callable[..., bool]),
        ("is_due_amount_calculation_blocked", Callable[..., bool]),
        ("is_overdue_amount_calculation_blocked", Callable[..., bool]),
        ("is_delinquency_blocked", Callable[..., bool]),
        ("is_repayment_blocked", Callable[..., bool]),
    ],
)

feature = RepaymentHoliday(
    all_parameters=all_parameters,
    accrual_blocking_parameters=accrual_blocking_parameters,
    due_amount_calculation_blocking_parameters=due_amount_calculation_blocking_parameters,
    should_trigger_reamortisation=should_trigger_reamortisation,
    is_accrual_blocked=is_accrual_blocked,
    is_due_amount_calculation_blocked=is_due_amount_calculation_blocked,
    is_overdue_amount_calculation_blocked=is_overdue_amount_calculation_blocked,
    is_delinquency_blocked=is_delinquency_blocked,
    is_repayment_blocked=is_repayment_blocked,
)
