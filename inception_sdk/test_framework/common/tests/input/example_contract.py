# fmt: off
# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
"""
An example that shows required Calendars being declared in a Smart Contract
"""
# standard libs
from decimal import Decimal

# contracts api
from contracts_api import (
    ActivationHookArguments,
    ActivationHookResult,
    DenominationShape,
    NumberShape,
    Parameter,
    ParameterLevel,
    PrePostingHookArguments,
    PrePostingHookResult,
    ScheduledEvent,
    ScheduledEventHookArguments,
    ScheduledEventHookResult,
    ScheduleExpression,
    SmartContractEventType,
    requires,
)

display_name = "Contract with Calendar declarations"
api = "4.0.0"
version = "1.0.0"
summary = "Contract with calendars"
parameters = [
    Parameter(
        name="denomination",  # noqa: CTR007
        shape=DenominationShape(),
        level=ParameterLevel.TEMPLATE,
        description="Default denomination for the contract.",
        display_name="Default Denomination.",
    ),
    Parameter(
        name="interest_rate",  # noqa: CTR007
        shape=NumberShape(min_value=0, max_value=1, step=Decimal("0.01")),
        level=ParameterLevel.TEMPLATE,
        description="Rate paid on positive balances",
        display_name="Gross Interest Rate",
    ),
]

pnl_account = "1"
DORMANCY_FLAG = "&{ACCOUNT_DORMANT}"
EVENT_WITH_SINGLE_TAG = "EVENT_WITH_SINGLE_TAG"
event_types = [
    SmartContractEventType(
        name=EVENT_WITH_SINGLE_TAG, scheduler_tag_ids=["AST_1"],
    ),
    SmartContractEventType(
        name="EVENT_WITH_MULTIPLE_TAGS", scheduler_tag_ids=["AST_2", "AST_3"],
    ),
    SmartContractEventType(name="EVENT_WITHOUT_TAGS"),
]


def activation_hook(vault, hook_arguments: ActivationHookArguments) -> ActivationHookResult | None:
    return ActivationHookResult(
        scheduled_events_return_value={
            "ACCRUE_INTEREST": ScheduledEvent(
                expression=ScheduleExpression(hour=0, minute=0, second=0)
            )
        }
    )


@requires(
    event_type="ACCRUE_INTEREST",
    parameters=True,
    calendar=["&{CALENDAR_1}", "&{CALENDAR_2}", "&{CALENDAR_3}"],
    flags=True,
)
def scheduled_hook(
    vault,
    hook_arguments: ScheduledEventHookArguments
) -> ScheduledEventHookResult | None:
    vault.get_calendar_events(
        calendar_ids=["&{CALENDAR_1}", "&{CALENDAR_2}", "&{CALENDAR_3}"]  # noqa: E501
    )

    #parameter should be replaced
    _get_flag_duration_in_months(
        vault, "&{REPAYMENT_HOLIDAY}", include_active=True
    )
    # flag parameter should not be replaced below
    vault.get_flag_timeseries(flag=DORMANCY_FLAG).latest()
    if hook_arguments.event_type == "ACCRUE_INTEREST":
        pass

    return None

@requires(parameters=True, calendar=["&{CALENDAR_1}"])
def pre_posting_hook(vault, hook_arguments: PrePostingHookArguments) -> PrePostingHookResult | None:
    vault.get_calendar_events(calendar_ids=["&{CALENDAR_1}"])

def _get_flag_duration_in_months(
        vault, flag_id: str, include_active: bool
) -> None:
    pass
# fmt: on
