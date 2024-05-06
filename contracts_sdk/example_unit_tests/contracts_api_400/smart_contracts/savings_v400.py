from decimal import Decimal

from contracts_api import (  # type: ignore
    Parameter,
    ParameterLevel,
    OptionalShape,
    NumberShape,
    OptionalValue,
    ParameterUpdatePermission,
    ScheduledEvent,
    ScheduleExpression,
    SmartContractEventType,
    ActivationHookResult,
)
from contract_modules import interest_utils_v400  # type: ignore


display_name = "Instant Saver"
api = "4.0.0"
version = "1.0.0"

parameters = [
    Parameter(
        name="key_date",
        level=ParameterLevel.INSTANCE,
        description="Do you want to choose the day you are paid interest?",
        display_name="Elected day of month to pay interest on",
        shape=OptionalShape(
            shape=NumberShape(
                min_value=1,
                max_value=31,
                step=1,
            )
        ),
        default_value=OptionalValue(Decimal(28)),
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
    ),
]

event_types = [
    SmartContractEventType(name="APPLY_ACCRUED_INTEREST"),
    SmartContractEventType(name="ACCRUE_INTEREST"),
]


# This hook demonstrated how to configure account scheduled events schedules
def activation_hook(vault, hook_arguments):
    start_date = vault.get_account_creation_datetime()
    key_date_timeseries = vault.get_parameter_timeseries(name="key_date")
    selected_day = interest_utils_v400.get_selected_interest_payday(
        key_date_timeseries, effective_datetime=start_date
    )
    if selected_day is None:
        selected_day = start_date.day
    payday = interest_utils_v400.get_interest_payday(selected_day, start_date)
    scheduled_events = {
        "APPLY_ACCRUED_INTEREST": ScheduledEvent(
            start_datetime=start_date,
            expression=ScheduleExpression(day=payday, hour=0, minute=1),
        ),
        "ACCRUE_INTEREST": ScheduledEvent(
            start_datetime=start_date,
            expression=ScheduleExpression(hour=0),
        ),
    }
    return ActivationHookResult(scheduled_events_return_value=scheduled_events)
