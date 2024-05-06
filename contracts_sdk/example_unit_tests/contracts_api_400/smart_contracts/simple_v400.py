from datetime import timedelta

from contracts_api import (  # type: ignore
    ActivationHookResult,
    ScheduledEvent,
    ScheduleExpression,
    SmartContractEventType,
    UpdateAccountEventTypeDirective,
    ScheduledEventHookResult,
)


api = "4.0.0"
version = "1.0.0"


event_types = [
    SmartContractEventType(name="EXAMPLE_EVENT"),
]


# This hook demonstrated how to configure account scheduled events schedules
def activation_hook(vault, hook_arguments):
    scheduled_events = {
        "EXAMPLE_EVENT": ScheduledEvent(
            start_datetime=vault.get_account_creation_datetime(),
            end_datetime=(vault.get_account_creation_datetime() + timedelta(minutes=1)),
            expression=ScheduleExpression(minute="*"),
        ),
    }
    return ActivationHookResult(scheduled_events_return_value=scheduled_events)


# This hook demonstrated how to implement an account scheduled event processing logic
def scheduled_event_hook(vault, hook_arguments):
    update_account_event_type_directives = []
    if hook_arguments.event_type == "EXAMPLE_EVENT":
        update_event_directive = UpdateAccountEventTypeDirective(
            event_type=hook_arguments.event_type,
            skip=True,
        )
        update_account_event_type_directives.append(update_event_directive)
    return ScheduledEventHookResult(
        update_account_event_type_directives=update_account_event_type_directives,
    )
