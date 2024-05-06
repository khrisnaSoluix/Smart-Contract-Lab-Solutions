# CBF: Grace period

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional

# features
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    AccountNotificationDirective,
    BalanceDefaultDict,
    DateShape,
    NumberShape,
    Parameter,
    ParameterLevel,
    Rejection,
    RejectionReason,
    ScheduledEvent,
    SmartContractEventType,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Parameters
PARAM_GRACE_PERIOD = "grace_period"
PARAM_GRACE_PERIOD_END_DATE = "grace_period_end_date"

# notifications
GRACE_PERIOD_END_SUFFIX = "_GRACE_PERIOD_END"
# Schedule event names
GRACE_PERIOD_END_EVENT = "GRACE_PERIOD_END"

parameters = [
    Parameter(
        name=PARAM_GRACE_PERIOD,
        level=ParameterLevel.TEMPLATE,
        description="The number of days from the account creation datetime when a user can make "
        "amendments to a deposit account without incurring any fees or penalties.",
        display_name="Grace Period Length (days)",
        shape=NumberShape(min_value=0, step=1),
        default_value=5,
    ),
    # Derived Parameters
    Parameter(
        name=PARAM_GRACE_PERIOD_END_DATE,
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The grace period will end at 23:59:59.999999 (inclusive) on this day. If "
        "0001-01-01 is returned, this parameter is not valid for this account.",
        display_name="Grace Period End Date",
        shape=DateShape(),
    ),
]


def notification_type(*, product_name: str) -> str:
    """
    Returns a notification type
    :param product_name: The product name
    :return: notification type
    """
    return f"{product_name.upper()}{GRACE_PERIOD_END_SUFFIX}"


def event_types(*, product_name: str) -> list[SmartContractEventType]:
    """
    Returns a list of event types
    :param product_name: name of the product
    :return: list of SmartContractEventType
    """
    return [
        SmartContractEventType(
            name=GRACE_PERIOD_END_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{GRACE_PERIOD_END_EVENT}_AST"],
        )
    ]


def scheduled_events(*, vault: SmartContractVault) -> dict[str, ScheduledEvent]:
    """
    Creates one off scheduled event for grace period end balance check
    :param vault: Vault object to retrieve account creation datetime and grace period
    :return: dict of grace period end scheduled event
    """
    grace_period_end_datetime = get_grace_period_end_datetime(vault=vault)
    scheduled_event = ScheduledEvent(
        start_datetime=grace_period_end_datetime - relativedelta(seconds=1),
        expression=utils.one_off_schedule_expression(schedule_datetime=grace_period_end_datetime),
        end_datetime=grace_period_end_datetime,
    )
    return {GRACE_PERIOD_END_EVENT: scheduled_event}


def get_grace_period_end_datetime(*, vault: SmartContractVault) -> datetime:
    """
    Calculates and returns the grace period end datetime. This date will represent the
    midnight of the account creation datetime plus the number of days in the grace period,
    inclusive of the account creation datetime.
    :param vault: Vault object for the account
    :return: the datetime when the grace period ends
    """
    grace_period = get_grace_period_parameter(vault=vault)
    account_creation_datetime = vault.get_account_creation_datetime()
    grace_period_end = (account_creation_datetime + relativedelta(days=grace_period)).replace(
        hour=23, minute=59, second=59, microsecond=999999
    )
    return grace_period_end


def is_within_grace_period(*, vault: SmartContractVault, effective_datetime: datetime) -> bool:
    """
    Determines whether the effective datetime is within the grace period of an account

    :param vault: Vault object for the account
    :param effective_datetime: datetime to be checked whether is within the grace period
    :return: True if the effective datetime is less than or equal to the grace period end datetime
    """
    return effective_datetime <= get_grace_period_end_datetime(vault=vault)


def validate_deposit(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    posting_instructions: utils.PostingInstructionListAlias,
    denomination: Optional[str] = None,
) -> Optional[Rejection]:
    """
    Reject the posting instructions if deposits are sent after the end of grace period
    Accept deposits within the grace period

    :param vault: Vault object for the account against which this validation is applied
    :param effective_datetime: datetime at which this method is executed
    :param posting_instructions: list of posting instructions to validate
    :param denomination: the denomination of the account
    :return: rejection if any of the above conditions are met
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    is_deposit = utils.get_current_credit_balance(
        balances=utils.get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    ) > Decimal("0")

    if is_deposit and not is_within_grace_period(
        vault=vault, effective_datetime=effective_datetime
    ):
        # reject deposits after grace period
        return Rejection(
            message="No deposits are allowed after the grace period end",
            reason_code=RejectionReason.AGAINST_TNC,
        )

    return None


def is_withdrawal_subject_to_fees(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    posting_instructions: utils.PostingInstructionListAlias,
    denomination: Optional[str] = None,
) -> bool:
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    is_withdrawal = utils.get_available_balance(
        balances=utils.get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    ) < Decimal("0")

    if is_withdrawal and not is_within_grace_period(
        vault=vault, effective_datetime=effective_datetime
    ):
        return True

    return False


def validate_term_parameter_change(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
) -> Optional[Rejection]:
    """
    Allow changes to the 'term' parameter within grace period, reject change outside grace period

    :param vault: Vault object for the account
    :param effective_datetime: datetime of the parameter change
    :return: rejection if parameter changed outside the grace period
    """
    if not is_within_grace_period(vault=vault, effective_datetime=effective_datetime):
        return Rejection(
            message="Term length cannot be changed outside the grace period",
            reason_code=RejectionReason.AGAINST_TNC,
        )

    return None


def handle_account_closure_notification(
    *,
    vault: SmartContractVault,
    product_name: str,
    effective_datetime: datetime,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> list[AccountNotificationDirective]:
    """
    Send account closure notification when no funds are present in the account
    at the end of grace period
    :param vault: Vault object to retrieve account creation datetime and grace period
    :param product_name: the name of the product for notification type
    :param effective_datetime: datetime at which this method is executed
    :param denomination: the denomination of the account
    :param balances: effective account balances available, if not provided will be retrieved
    using the EFFECTIVE_OBSERVATION_FETCHER_ID fetcher id
    :return: account closure notification
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    net_balance = utils.get_current_net_balance(balances=balances, denomination=denomination)

    # no funds in the the account
    if net_balance == Decimal(0):
        return [
            AccountNotificationDirective(
                notification_type=notification_type(product_name=product_name),
                notification_details={
                    "account_id": vault.account_id,
                    "grace_period_end_datetime": str(effective_datetime),
                    "reason": "Close account due to lack of funds at the end of grace period",
                },
            )
        ]
    return []


def get_grace_period_parameter(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils.get_parameter(vault=vault, name=PARAM_GRACE_PERIOD, at_datetime=effective_datetime)
    )
