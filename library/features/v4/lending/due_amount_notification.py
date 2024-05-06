# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    AccountNotificationDirective,
    NumberShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    ScheduledEvent,
    SmartContractEventType,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Schedule event names
NOTIFY_DUE_AMOUNT_EVENT = "NOTIFY_DUE_AMOUNT"

# Prefixes
DUE_AMOUNT_NOTIFICATION_PREFIX = "due_amount_notification"
CHECK_OVERDUE_PREFIX = "check_overdue"

# Parameter Names
PARAM_DUE_NOTIFICATION_HOUR = f"{DUE_AMOUNT_NOTIFICATION_PREFIX}_hour"
PARAM_DUE_NOTIFICATION_MINUTE = f"{DUE_AMOUNT_NOTIFICATION_PREFIX}_minute"
PARAM_DUE_NOTIFICATION_SECOND = f"{DUE_AMOUNT_NOTIFICATION_PREFIX}_second"
PARAM_NOTIFICATION_PERIOD = "notification_period"
PARAM_DENOMINATION = "denomination"

# Notifications
REPAYMENT_NOTIFICATION_SUFFIX = "_REPAYMENT"

due_amount_notification_period_parameter = Parameter(
    name=PARAM_NOTIFICATION_PERIOD,
    shape=NumberShape(min_value=1, max_value=28, step=1),
    level=ParameterLevel.TEMPLATE,
    description="The number of days prior to a payment becoming due,"
    " send a due notification reminder to the user.",
    display_name="Due Notification Days",
    default_value=Decimal("2"),
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)

schedule_time_parameters = [
    Parameter(
        name=PARAM_DUE_NOTIFICATION_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which due notifications are sent.",
        display_name="Due Notification Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_DUE_NOTIFICATION_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which due notifications are sent.",
        display_name="Due Notification Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_DUE_NOTIFICATION_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which due notifications are sent.",
        display_name="Due Notification Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
]
due_amount_notification_schedule_parameters = [
    due_amount_notification_period_parameter,
    *schedule_time_parameters,
]


def get_notification_period_parameter(vault: SmartContractVault) -> int:
    return int(utils.get_parameter(vault, name=PARAM_NOTIFICATION_PERIOD))


def event_types(product_name: str) -> list[SmartContractEventType]:
    """
    Creates event_types metadata for NOTIFY_DUE_AMOUNT schedule
    :param product_name: The name of the product
    :return: list[SmartContractEventType]
    """
    return [
        SmartContractEventType(
            name=NOTIFY_DUE_AMOUNT_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{NOTIFY_DUE_AMOUNT_EVENT}_AST"],
        )
    ]


def notification_type(product_name: str) -> str:
    """
    Creates the notification type
    :param product_name: The product name
    :return: str
    """
    return f"{product_name.upper()}{REPAYMENT_NOTIFICATION_SUFFIX}"


def get_next_due_amount_notification_schedule(
    vault: SmartContractVault, next_due_amount_calc_datetime: datetime
) -> datetime:
    notification_period = int(utils.get_parameter(vault, name=PARAM_NOTIFICATION_PERIOD))
    hour, minute, second = utils.get_schedule_time_from_parameters(
        vault, parameter_prefix=DUE_AMOUNT_NOTIFICATION_PREFIX
    )

    return next_due_amount_calc_datetime - relativedelta(
        days=notification_period, hour=hour, minute=minute, second=second
    )


def get_next_due_amount_notification_datetime(
    vault: SmartContractVault,
    current_due_amount_notification_datetime: datetime,
    repayment_frequency_delta: relativedelta,
) -> datetime:
    """
    returns the next due amount notification datetime given the current due amount
    notification date
    :param vault: vault object
    :param current_due_amount_notification: the current due amount notification date
    :param repayment_frequency_delta: the relative delta for the repayment frequency
    :return: datetime
    """
    notification_period = int(utils.get_parameter(vault, name=PARAM_NOTIFICATION_PERIOD))
    # get the due_amount_calc for previous date.
    current_due_amount_calc_date_time = current_due_amount_notification_datetime + relativedelta(
        days=notification_period
    )
    # get next_due_amount_calc
    next_due_amount_calc_datetime = current_due_amount_calc_date_time + repayment_frequency_delta

    next_due_amount_notification_datetime = get_next_due_amount_notification_schedule(
        vault=vault, next_due_amount_calc_datetime=next_due_amount_calc_datetime
    )
    return next_due_amount_notification_datetime


def scheduled_events(
    vault: SmartContractVault, next_due_amount_calc_datetime: datetime
) -> dict[str, ScheduledEvent]:
    """
    Creates execution schedule for NOTIFY_DUE_AMOUNT schedule to run `notification_period` days
    before the first due amount calculation date
    :param vault: Vault object for the account containing schedule time and notification_period
    parameters
    :param next_due_amount_calc_datetime: date when the next due_amount_calc_datetime will happen.
    due amount calculation should occur. Time component will be ignored
    :return: list[SmartContractEventType]
    """
    scheduled_events: dict[str, ScheduledEvent] = {}
    notification_datetime = get_next_due_amount_notification_schedule(
        vault=vault, next_due_amount_calc_datetime=next_due_amount_calc_datetime
    )
    scheduled_events = {
        NOTIFY_DUE_AMOUNT_EVENT: ScheduledEvent(
            start_datetime=notification_datetime - relativedelta(seconds=1),
            expression=utils.one_off_schedule_expression(notification_datetime),
        )
    }
    return scheduled_events


# Scheduled hook helpers
def schedule_logic(
    vault: SmartContractVault,
    product_name: str,
    overdue_datetime: datetime,
    due_interest: Decimal = Decimal("0"),
    due_principal: Decimal = Decimal("0"),
) -> list[AccountNotificationDirective]:
    """
    Sends notification prior to a payment becoming due.
    :param vault: vault object to instruct any notifications from
    :param product_name: The product name
    :param overdue_datetime: the date that the repayment amount will become overdue
    :param due_interest: the due_interest.
    :param due_principal: the due_principal
    :return: list[AccountNotificationDirective]
    """

    if due_principal + due_interest > 0:
        return [
            send_due_amount_notification(
                account_id=vault.account_id,
                due_principal=due_principal,
                due_interest=due_interest,
                overdue_datetime=overdue_datetime,
                product_name=product_name,
            )
        ]
    return []


# notification helpers
def send_due_amount_notification(
    account_id: str,
    due_principal: Decimal,
    due_interest: Decimal,
    overdue_datetime: datetime,
    product_name: str,
) -> AccountNotificationDirective:
    """
    Instruct a notification.

    :param account_id: vault account id
    :param due_principal: Calculated due principal
    :param due_interest: Calculated due interest
    :param overdue_datetime: the date that the repayment amount will become overdue
    :param product_name: the name of the product for the notification prefix
    :return: AccountNotificationDirective
    """
    return AccountNotificationDirective(
        notification_type=notification_type(product_name),
        notification_details={
            "account_id": account_id,
            "due_principal": str(due_principal),
            "due_interest": str(due_interest),
            "overdue_date": str(overdue_datetime.date()),
        },
    )
