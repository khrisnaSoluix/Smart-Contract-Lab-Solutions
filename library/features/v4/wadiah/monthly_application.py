# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Optional

# contracts api
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ADDRESS,
    AccountIdShape,
    BalanceDefaultDict,
    CustomInstruction,
    NumberShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    ScheduledEvent,
    SmartContractEventType,
    UnionItem,
    UnionItemValue,
    UnionShape,
    UpdateAccountEventTypeDirective,
)

APPLICATION_EVENT = "MONTHLY_APPLICATION"

# Monthly application
MONTHLY_APPLICATION_EVENT = "MONTHLY_APPLICATION"

MONTHLY_APPLICATION_PREFIX = "monthly_application"
PARAM_MONTHLY_APPLICATION_DAY = (
    f"{MONTHLY_APPLICATION_PREFIX}_day"
)
PARAM_MONTHLY_APPLICATION_HOUR = (
    f"{MONTHLY_APPLICATION_PREFIX}_hour"
)
PARAM_MONTHLY_APPLICATION_MINUTE = (
    f"{MONTHLY_APPLICATION_PREFIX}_minute"
)
PARAM_MONTHLY_APPLICATION_SECOND = (
    f"{MONTHLY_APPLICATION_PREFIX}_second"
)

monthly_application_schedule_parameters = [
    Parameter(
        name=PARAM_MONTHLY_APPLICATION_DAY,
        shape=NumberShape(min_value=1, max_value=28, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The day of the month on which bonus is distributed and fees are applied."
        " The day can be within 1 and 28, inclusive of both",
        display_name="Monthly application day",
        default_value=1,
    ),
    Parameter(
        name=PARAM_MONTHLY_APPLICATION_HOUR,
        shape=NumberShape(min_value=0, max_value=6, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which bonus is distributed and fees are applied. "
        "The hour can be within 0 and 6, inclusive of both",
        display_name="Monthly application hour",
        default_value=0,
    ),
    Parameter(
        name=PARAM_MONTHLY_APPLICATION_MINUTE,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which bonus is distributed and fees are applied.",
        display_name="Monthly application minute",
        default_value=1,
    ),
    Parameter(
        name=PARAM_MONTHLY_APPLICATION_SECOND,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which bonus is distributed and fees are applied.",
        display_name="Monthly application second",
        default_value=0,
    ),
]

parameters = [*monthly_application_schedule_parameters]

def event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=APPLICATION_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{APPLICATION_EVENT}_AST"],
        )
    ]