# standard libs
from datetime import datetime
from decimal import Decimal

# features
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_addresses as lending_addresses

# contracts api
from contracts_api import (
    AccountNotificationDirective,
    NumberShape,
    Parameter,
    ParameterLevel,
    ScheduledEvent,
    SmartContractEventType,
    SupervisorContractEventType,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Schedule event names
CHECK_DELINQUENCY_EVENT = "CHECK_DELINQUENCY"

# Prefixes
CHECK_DELINQUENCY_PREFIX = "check_delinquency"

# Parameter Names
PARAM_CHECK_DELINQUENCY_HOUR = f"{CHECK_DELINQUENCY_PREFIX}_hour"
PARAM_CHECK_DELINQUENCY_MINUTE = f"{CHECK_DELINQUENCY_PREFIX}_minute"
PARAM_CHECK_DELINQUENCY_SECOND = f"{CHECK_DELINQUENCY_PREFIX}_second"
PARAM_GRACE_PERIOD = "grace_period"
PARAM_DENOMINATION = "denomination"

# Notifications
MARK_DELINQUENT_NOTIFICATION_SUFFIX = "_DELINQUENT_NOTIFICATION"

schedule_parameters = [
    Parameter(
        name=PARAM_GRACE_PERIOD,
        shape=NumberShape(max_value=27, min_value=0, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The number of days after which the account becomes delinquent.",
        display_name="Grace Period (days)",
        default_value=Decimal(15),
    ),
    Parameter(
        name=PARAM_CHECK_DELINQUENCY_HOUR,
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which delinquency is checked.",
        display_name="Check Delinquency Hour",
        default_value=0,
    ),
    Parameter(
        name=PARAM_CHECK_DELINQUENCY_MINUTE,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The minute of the day at which delinquency is checked.",
        display_name="Check Delinquency Minute",
        default_value=0,
    ),
    Parameter(
        name=PARAM_CHECK_DELINQUENCY_SECOND,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The second of the day at which delinquency is checked.",
        display_name="Check Delinquency Second",
        default_value=2,
    ),
]


def get_grace_period_parameter(vault: SmartContractVault) -> int:
    return int(utils.get_parameter(vault=vault, name=PARAM_GRACE_PERIOD))


def event_types(product_name: str) -> list[SmartContractEventType]:
    """
    Returns the a list of event types for delinquency
    :param product_name: The name of the product
    :return: list[SmartContractEventType]
    """
    return [
        SmartContractEventType(
            name=CHECK_DELINQUENCY_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{CHECK_DELINQUENCY_EVENT}_AST"],
        )
    ]


def supervisor_event_types(product_name: str) -> list[SupervisorContractEventType]:
    """
    Returns the a list of event types for delinquency for a supervisor contract
    """
    return [
        SupervisorContractEventType(
            name=CHECK_DELINQUENCY_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{CHECK_DELINQUENCY_EVENT}_AST"],
        )
    ]


def notification_type(product_name: str) -> str:
    """
    Creates the notification type
    :param product_name: The product name
    :return: str
    """
    return f"{product_name.upper()}{MARK_DELINQUENT_NOTIFICATION_SUFFIX}"


def scheduled_events(
    vault: SmartContractVault,
    start_datetime: datetime,
    is_one_off: bool = False,
    skip: bool = False,
) -> dict[str, ScheduledEvent]:
    """
    Create a check delinquency schedule, starting at the specified date, and using the
    `check_delinquency_<>` schedule time parameters. This schedule can either be a monthly recurring
    schedule or executed once.
    :param vault: The Vault object
    :param start_datetime: the date on which the delinquency check schedule starts, ignores the time
    component
    :param is_one_off: whether the schedule is recurring or a one-off schedule
    :return: a dictionary containing the check delinquency schedule
    """
    year = start_datetime.year if is_one_off else None
    month = start_datetime.month if is_one_off else None

    return {
        CHECK_DELINQUENCY_EVENT: ScheduledEvent(
            start_datetime=start_datetime.replace(hour=0, minute=0, second=0),
            expression=utils.get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=CHECK_DELINQUENCY_PREFIX,
                day=start_datetime.day,
                month=month,
                year=year,
            ),
            skip=skip,
        ),
    }


# Scheduled hook helpers
def schedule_logic(
    vault: SmartContractVault,
    product_name: str,
    denomination: str,
    addresses: list[str] = lending_addresses.LATE_REPAYMENT_ADDRESSES,
) -> list[AccountNotificationDirective]:
    """
    Instruct a notification to inform the customer of their account delinquency.
    :param vault: Vault object
    :param product_name: the name of the product for the workflow prefix
    :param addresses: list of balance addresses to be checked to determine whether an account is
    delinquent
    :param denomination: the denomination of the balance addresses
    :return: list[AccountNotificationDirective]
    """
    balances = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    total_balance = utils.sum_balances(
        balances=balances,
        addresses=addresses,
        denomination=denomination,
        decimal_places=2,
    )

    if total_balance > 0:
        return [
            AccountNotificationDirective(
                notification_type=notification_type(product_name),
                notification_details={"account_id": str(vault.account_id)},
            )
        ]
    return []
