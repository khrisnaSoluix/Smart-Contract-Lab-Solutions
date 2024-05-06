# CBF: Deposit Period and Number of Deposits

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Optional
from zoneinfo import ZoneInfo

# features
import library.features.v4.common.utils as utils
import library.features.v4.deposit.deposit_parameters as deposit_parameters

# contracts api
from contracts_api import (
    AccountNotificationDirective,
    DateShape,
    NumberShape,
    OptionalShape,
    OptionalValue,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Rejection,
    RejectionReason,
    ScheduledEvent,
    SmartContractEventType,
    UpdateAccountEventTypeDirective,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# notifications
ACCOUNT_MATURITY_SUFFIX = "_ACCOUNT_MATURITY"
NOTIFY_UPCOMING_MATURITY_SUFFIX = "_NOTIFY_UPCOMING_MATURITY"

# Schedule event names
ACCOUNT_MATURITY_EVENT = "ACCOUNT_MATURITY"
NOTIFY_UPCOMING_MATURITY_EVENT = "NOTIFY_UPCOMING_MATURITY"


PARAM_DESIRED_MATURITY_DATE = "desired_maturity_date"
desired_maturity_date = Parameter(
    name=PARAM_DESIRED_MATURITY_DATE,
    level=ParameterLevel.INSTANCE,
    shape=OptionalShape(
        shape=DateShape(
            min_date=datetime.min.replace(tzinfo=ZoneInfo("UTC")),
            max_date=datetime.max.replace(tzinfo=ZoneInfo("UTC")),
        )
    ),
    description="Optional override for the account maturity datetime. If not set, the maturity "
    "datetime is derived from the term and term unit. If set, the account will mature at 00:00:00 "
    "on the next day of this parameter value.",
    display_name="Account Maturity Date",
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    default_value=OptionalValue(datetime.min.replace(tzinfo=ZoneInfo("UTC"))),
)

PARAM_MATURITY_NOTICE_PERIOD = "maturity_notice_period"
maturity_notice_period = Parameter(
    name=PARAM_MATURITY_NOTICE_PERIOD,
    level=ParameterLevel.TEMPLATE,
    shape=NumberShape(min_value=1, step=1),
    description="The number of days prior to the account maturing"
    "to send a notification regarding upcoming maturity.",
    display_name="Maturity Notification Days",
    default_value=1,
)
maturity_parameters = [desired_maturity_date, maturity_notice_period]


# Notifications
def notification_type_at_account_maturity(*, product_name: str) -> str:
    """
    Returns a notification type for account maturity
    :param product_name: The product name
    :return: notification type
    """
    return f"{product_name.upper()}{ACCOUNT_MATURITY_SUFFIX}"


def notification_type_notify_upcoming_maturity(*, product_name: str) -> str:
    """
    Returns a notification type for notify upcoming maturity
    :param product_name: The product name
    :return: notification type
    """
    return f"{product_name.upper()}{NOTIFY_UPCOMING_MATURITY_SUFFIX}"


# Schedule helpers
def event_types(*, product_name: str) -> list[SmartContractEventType]:
    """
    Returns a list of event types
    :param product_name: name of the product
    :return: list of SmartContractEventType
    """
    return [
        SmartContractEventType(
            name=ACCOUNT_MATURITY_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{ACCOUNT_MATURITY_EVENT}_AST"],
        ),
        SmartContractEventType(
            name=NOTIFY_UPCOMING_MATURITY_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{NOTIFY_UPCOMING_MATURITY_EVENT}_AST"],
        ),
    ]


def scheduled_events(*, vault: SmartContractVault) -> dict[str, ScheduledEvent]:
    """
    Creates one off scheduled events for sending notifications:
    - to notify of upcoming maturity
    - at account maturity

    :param vault: Vault object to retrieve account creation datetime and notice period
    :return: dict of account maturity notifications scheduled events
    """
    (
        maturity_datetime,
        notify_upcoming_maturity_datetime,
    ) = get_account_maturity_and_notify_upcoming_maturity_datetimes(vault=vault)

    account_maturity_scheduled_event = ScheduledEvent(
        start_datetime=maturity_datetime - relativedelta(seconds=1),
        expression=utils.one_off_schedule_expression(schedule_datetime=maturity_datetime),
        end_datetime=maturity_datetime,
    )
    notify_upcoming_maturity_scheduled_event = ScheduledEvent(
        start_datetime=notify_upcoming_maturity_datetime - relativedelta(seconds=1),
        expression=utils.one_off_schedule_expression(
            schedule_datetime=notify_upcoming_maturity_datetime
        ),
        end_datetime=notify_upcoming_maturity_datetime,
    )

    return {
        ACCOUNT_MATURITY_EVENT: account_maturity_scheduled_event,
        NOTIFY_UPCOMING_MATURITY_EVENT: notify_upcoming_maturity_scheduled_event,
    }


def handle_account_maturity_event(
    *,
    product_name: str,
    account_id: str,
    effective_datetime: datetime,
    schedules_to_skip_indefinitely: Optional[list[str]] = None,
) -> tuple[list[AccountNotificationDirective], list[UpdateAccountEventTypeDirective]]:
    """
    - Creates account maturity notification directive
    - Creates account update directive to skip the given schedules indefinitely

    :param product_name: the name of the product for notification type
    :param account_id: vault account id for which this notification is sent
    :param effective_datetime: datetime at which this method is executed
    :param schedules_to_skip_indefinitely: list of schedule names to skip forever
    :return: tuple containing a list of maturity notification directive
    and a list of account update directive to skip schedules indefinitely
    """
    updated_schedules: list[UpdateAccountEventTypeDirective] = []

    if schedules_to_skip_indefinitely:
        updated_schedules = _handle_skipping_schedules_indefinitely_at_maturity(
            schedules_to_skip_indefinitely=schedules_to_skip_indefinitely
        )

    maturity_notification: list[AccountNotificationDirective] = [
        AccountNotificationDirective(
            notification_type=notification_type_at_account_maturity(product_name=product_name),
            notification_details={
                "account_id": account_id,
                "account_maturity_datetime": str(effective_datetime),
                "reason": "Account has now reached maturity",
            },
        )
    ]
    return maturity_notification, updated_schedules


def handle_notify_upcoming_maturity_event(
    *,
    vault: SmartContractVault,
    product_name: str,
) -> tuple[list[AccountNotificationDirective], list[UpdateAccountEventTypeDirective]]:
    """
    - Creates notification directive prior to account maturity as a reminder
    - Creates account update directive for maturity schedule if it falls on a holiday

    Note: Calendars only have a 3 month visibility from the effective datetime.
    The maturity date is checked on account opening but unlikely to fall within the
    first 3 months. Therefore maturity date is checked again and updated if it falls
    on a holiday.

    :param vault: Vault object for the account
    :param product_name: the name of the product for notification type
    :return: tuple containing a list of maturity reminder notification directives
    and a list of account update directives for maturity schedule
    """
    updated_maturity_schedule: list[UpdateAccountEventTypeDirective] = []

    maturity_datetime_without_calendars = get_maturity_datetime_without_calendars(vault=vault)
    maturity_datetime_with_calendars = get_maturity_datetime_with_calendars(
        vault=vault, maturity_datetime=maturity_datetime_without_calendars
    )

    if maturity_datetime_with_calendars != maturity_datetime_without_calendars:
        updated_maturity_schedule = [
            _update_account_maturity_schedule(maturity_datetime=maturity_datetime_with_calendars)
        ]

    notification_maturity_notice_period: list[AccountNotificationDirective] = [
        AccountNotificationDirective(
            notification_type=notification_type_notify_upcoming_maturity(product_name=product_name),
            notification_details={
                "account_id": vault.account_id,
                "account_maturity_datetime": str(maturity_datetime_with_calendars),
            },
        )
    ]

    return notification_maturity_notice_period, updated_maturity_schedule


def _handle_skipping_schedules_indefinitely_at_maturity(
    schedules_to_skip_indefinitely: list[str],
) -> list[UpdateAccountEventTypeDirective]:
    """
    Update provided list of schedules to a skip indefinitely on account maturity

    :param schedules_to_skip_indefinitely: list of schedule names to skip forever
    :return: list of updated scheduled events
    """
    return utils.update_schedules_to_skip_indefinitely(schedules=schedules_to_skip_indefinitely)


# Datetime helpers
def get_account_maturity_and_notify_upcoming_maturity_datetimes(
    *, vault: SmartContractVault
) -> tuple[datetime, datetime]:
    """
    Get the datetimes for the account maturity and notify account maturity events.

    :param vault: Vault object of the account
    :return: tuple of account maturity datetime and notify account maturity datetime
    """
    maturity_datetime_without_calendars = get_maturity_datetime_without_calendars(vault=vault)
    maturity_datetime = get_maturity_datetime_with_calendars(
        vault=vault, maturity_datetime=maturity_datetime_without_calendars
    )
    notify_upcoming_maturity_datetime = _get_notify_upcoming_maturity_datetime(
        vault=vault, maturity_datetime=maturity_datetime
    )

    return maturity_datetime, notify_upcoming_maturity_datetime


def get_maturity_datetime_without_calendars(*, vault: SmartContractVault) -> datetime:
    """
    Calculates the account maturity datetime based on the following conditions:
    - if desired_maturity_date is set and is before the account creation date, then the
      account is assumed to mature on account creation itself and no notification is sent
    - if desired_maturity_date is set and is after the account creation date, this value is used
    - if desired_maturity_date is not provided, the maturity datetime is derived from term and unit

    :param vault: Vault object for the account
    :return: the datetime when the account matures
    """
    if maturity_datetime := get_desired_maturity_datetime(vault=vault):
        maturity_datetime = max(vault.get_account_creation_datetime(), maturity_datetime)
    else:
        maturity_datetime = get_maturity_datetime_from_term_and_unit(vault=vault)

    return (maturity_datetime + relativedelta(days=1)).replace(hour=0, minute=0, second=0)


def get_maturity_datetime_from_term_and_unit(
    *,
    vault: SmartContractVault,
    term: Optional[int] = None,
    term_unit: Optional[str] = None,
) -> datetime:
    """
    Derive maturity datetime from term and term unit, starting at account opening.

    :param vault: Vault object for the account
    :param term: the term of the product, if not provided the 'term' parameter is retrieved
    :param term_unit: the term unit of the product, if not provided the
    'term_unit' parameter is retrieved
    :return: the maturity datetime using the term and term unit
    """
    account_creation_datetime = vault.get_account_creation_datetime()

    if term is None:
        term = deposit_parameters.get_term_parameter(vault=vault)

    if term_unit is None:
        term_unit = deposit_parameters.get_term_unit_parameter(vault=vault)

    add_timedelta = (
        relativedelta(days=term)
        if term_unit == deposit_parameters.DAYS
        else relativedelta(months=term)
    )

    return account_creation_datetime + add_timedelta


def get_maturity_datetime_with_calendars(
    vault: SmartContractVault, maturity_datetime: datetime
) -> datetime:
    """
    Get maturity datetime, adjusting for calendar events

    :param vault: Vault object for the account
    :param maturity_datetime: maturity datetime of the account before calendar adjustments
    :return: maturity datetime
    """
    calendar_events = vault.get_calendar_events(calendar_ids=["&{PUBLIC_HOLIDAYS}"])
    return utils.get_next_datetime_after_calendar_events(
        effective_datetime=maturity_datetime, calendar_events=calendar_events
    )


def _get_notify_upcoming_maturity_datetime(
    *, vault: SmartContractVault, maturity_datetime: datetime
) -> datetime:
    """
     Get notify upcoming maturity datetime, which is the start of the notice period before
     the maturity datetime, which is defined by the `maturity_notice_period` parameter.

    :param vault: Vault object for the account
    :param maturity_datetime: maturity datetime of the account
    :return: maturity datetime
    """
    maturity_notice_period = get_maturity_notice_period_parameter(vault=vault)
    return maturity_datetime - relativedelta(days=maturity_notice_period)


def validate_postings(
    *, vault: SmartContractVault, effective_datetime: datetime
) -> Optional[Rejection]:
    """
    Reject any postings after the account has matured

    :param vault: Vault object for the account
    :param effective_datetime: datetime of the posting
    :return Rejection: no transaction after account maturity
    """
    maturity_datetime_without_calendars = get_maturity_datetime_without_calendars(vault=vault)
    maturity_datetime = get_maturity_datetime_with_calendars(
        vault=vault, maturity_datetime=maturity_datetime_without_calendars
    )
    if effective_datetime >= maturity_datetime:
        return Rejection(
            message="No transactions are allowed at or after account maturity",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


def _update_account_maturity_schedule(
    *, maturity_datetime: datetime
) -> UpdateAccountEventTypeDirective:
    """
    Updates account maturity schedule based on the provided maturity datetime

    :param maturity_datetime: maturity datetime of the account
    :return UpdateAccountEventTypeDirective: updated account schedule event
    """
    expression = utils.one_off_schedule_expression(schedule_datetime=maturity_datetime)
    return UpdateAccountEventTypeDirective(
        event_type=ACCOUNT_MATURITY_EVENT,
        expression=expression,
        end_datetime=maturity_datetime,
    )


# Parameter change helpers
def validate_term_parameter_change(
    *, vault: SmartContractVault, effective_datetime: datetime, proposed_term_value: int
) -> Optional[Rejection]:
    """
    Accepts a change to the 'term' parameter if it satisfies:
    - the `desired_maturity_date` parameter is not set, since this takes precedence if set
    - the notice period start date is in the future (and hence the maturity date is in the
      future since notice period will always occur before maturity)

    :param vault: Vault object for the account
    :param effective_datetime: effective datetime of the proposed parameter change
    :param proposed_term_value: the proposed value for the `term` value
    :return: a Rejection if the change is invalid
    """
    if (
        get_desired_maturity_datetime(vault=vault, effective_datetime=effective_datetime)
        is not None
    ):
        return Rejection(
            message="Term length cannot be changed if the desired maturity datetime is set.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

    current_term_value = deposit_parameters.get_term_parameter(vault=vault)
    if proposed_term_value >= current_term_value:
        # This will extend the term, and hence the notice period must start in the future
        return None

    else:
        maturity_datetime_without_calendars = get_maturity_datetime_from_term_and_unit(
            vault=vault, term=proposed_term_value
        )
        maturity_datetime = get_maturity_datetime_with_calendars(
            vault=vault, maturity_datetime=maturity_datetime_without_calendars
        )
        notify_upcoming_maturity_datetime = _get_notify_upcoming_maturity_datetime(
            vault=vault, maturity_datetime=maturity_datetime
        )

        if notify_upcoming_maturity_datetime < effective_datetime:
            return Rejection(
                message="Term length cannot be changed such that the maturity notification"
                " period starts in the past.",
                reason_code=RejectionReason.AGAINST_TNC,
            )

    return None


def handle_term_parameter_change(
    *, vault: SmartContractVault
) -> list[UpdateAccountEventTypeDirective]:
    """
    Update the ACCOUNT_MATURITY_EVENT and NOTIFY_UPCOMING_MATURITY_EVENT schedules after the term
    length has changed. The pre-parameter-change validation ensures that the notice period begins
    in the future.

    :param vault: the Vault object of the account
    :return: list of update event directives for the maturity and notify maturity events
    """
    (
        maturity_datetime,
        notify_upcoming_maturity_datetime,
    ) = get_account_maturity_and_notify_upcoming_maturity_datetimes(vault=vault)

    account_maturity_update_event = UpdateAccountEventTypeDirective(
        event_type=ACCOUNT_MATURITY_EVENT,
        expression=utils.one_off_schedule_expression(schedule_datetime=maturity_datetime),
        end_datetime=maturity_datetime,
    )
    notify_upcoming_maturity_update_event = UpdateAccountEventTypeDirective(
        event_type=NOTIFY_UPCOMING_MATURITY_EVENT,
        expression=utils.one_off_schedule_expression(
            schedule_datetime=notify_upcoming_maturity_datetime
        ),
        end_datetime=notify_upcoming_maturity_datetime,
    )
    return [account_maturity_update_event, notify_upcoming_maturity_update_event]


# Parameter getters
def get_maturity_notice_period_parameter(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils.get_parameter(
            vault=vault, name=PARAM_MATURITY_NOTICE_PERIOD, at_datetime=effective_datetime
        )
    )


def get_desired_maturity_datetime(
    *,
    vault: SmartContractVault,
    effective_datetime: Optional[datetime] = None,
) -> datetime:
    return utils.get_parameter(
        vault=vault,
        name=PARAM_DESIRED_MATURITY_DATE,
        at_datetime=effective_datetime,
        is_optional=True,
    )
