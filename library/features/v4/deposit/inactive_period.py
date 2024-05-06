# CBF: Deposit Period and Number of Deposits

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

# features
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils

# contracts api
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    BalanceDefaultDict,
    DateShape,
    NumberShape,
    OptionalShape,
    OptionalValue,
    Parameter,
    ParameterLevel,
    Rejection,
    RejectionReason,
    ScheduledEvent,
    SmartContractEventType,
    ParameterUpdatePermission,
    UnionItem,
    UnionItemValue,
    UnionShape,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# notifications
DEPOSIT_PERIOD_END_SUFFIX = "_DEPOSIT_PERIOD_END"
# Schedule event names
DEPOSIT_PERIOD_END_EVENT = "DEPOSIT_PERIOD_END"

# parameters
PARAM_DESIRED_COMMITMENT_DATE = "desired_commitment_date"
PARAM_DEPOSIT_PERIOD_END_DATE = "deposit_period_end_date"

parameters = [
]


def notification_type(*, product_name: str) -> str:
    """
    Returns a notification type
    :param product_name: The product name
    :return: notification type
    """
    return f"{product_name.upper()}{DEPOSIT_PERIOD_END_SUFFIX}"

def flag_inactive(
        *, 
        effective_datetime,
        account_id: str,
        ) -> AccountNotificationDirective:
    return AccountNotificationDirective(
                        notification_type="FLAG_INACTIVE",
                        notification_details={
                            "account_id": account_id,
                            "effective_date": str(effective_datetime.date()),
                            "description": str("flag as inactive upon opening")
                        },
                    )


def event_types(*, product_name: str) -> list[SmartContractEventType]:
    """
    Returns a list of event types
    :param product_name: name of the product
    :return: list of SmartContractEventType
    """
    return [
        SmartContractEventType(
            name=DEPOSIT_PERIOD_END_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{DEPOSIT_PERIOD_END_EVENT}_AST"],
        )
    ]


def scheduled_events(*, vault: SmartContractVault) -> dict[str, ScheduledEvent]:
    """
    Creates one off scheduled event for deposit period end balance check
    :param vault: Vault object to retrieve account creation datetime and deposit period
    :return: dict of deposit period end scheduled event
    """
    deposit_period_end_datetime = get_deposit_period_end_datetime(vault=vault)
    scheduled_event = ScheduledEvent(
        start_datetime=deposit_period_end_datetime - relativedelta(seconds=1),
        expression=utils.one_off_schedule_expression(schedule_datetime=deposit_period_end_datetime),
        end_datetime=deposit_period_end_datetime,
    )
    return {DEPOSIT_PERIOD_END_EVENT: scheduled_event}


def validate(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    posting_instructions: utils.PostingInstructionListAlias,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> Optional[Rejection]:
    """
    Reject the posting instructions if either of the following conditions are met;
        - Deposit posting is sent after the end of deposit period
        - Subsequent deposit postings are sent when only a single deposit is allowed

    :param vault: Vault object for the account against which this validation is applied
    :param effective_datetime: datetime at which this method is executed
    :param posting_instructions: list of posting_instructions to validate
    :param denomination: the denomination of the account
    :param balances: latest account balances available, if not provided will be retrieved
    using the LIVE_BALANCES_BOF_ID fetcher id
    :return: rejection if any of the above conditions are met
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    deposit_proposed_amount = utils.get_current_credit_balance(
        balances=utils.get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    )

    if deposit_proposed_amount > Decimal("0"):
        # reject deposits after deposit period
        if not is_within_deposit_period(
            vault=vault,
            effective_datetime=effective_datetime,
        ):
            return Rejection(
                message="No deposits are allowed after the deposit period end datetime",
                reason_code=RejectionReason.AGAINST_TNC,
            )

        # reject multiple deposits when only single is allowed
        number_of_permitted_deposits = _get_number_of_permitted_deposits_parameter(vault=vault)
        if number_of_permitted_deposits == SINGLE:
            if balances is None:
                balances = vault.get_balances_observation(
                    fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
                ).balances

            credit_default_balance = utils.get_current_credit_balance(
                balances=balances, denomination=denomination
            )

            if credit_default_balance > Decimal(0):
                return Rejection(
                    message="Only a single deposit is allowed",
                    reason_code=RejectionReason.AGAINST_TNC,
                )

    return None

# Not used
def handle_account_closure_notification(
    *,
    product_name: str,
    balances: BalanceDefaultDict,
    denomination: str,
    account_id: str,
    effective_datetime: datetime,
) -> list[AccountNotificationDirective]:
    """
    Send account closure notification when no funds are present in the account
    :param product_name: the name of the product for notification type
    :param balances: dict of BalanceCoordinate objects
    :param denomination: the denomination of the account
    :param account_id: vault account id for which this notification is sent
    :param effective_datetime: datetime at which this method is executed
    :return: account closure notification
    """
    net_balance = utils.get_current_net_balance(balances=balances, denomination=denomination)
    # no funds in the the account
    if net_balance == Decimal(0):
        return [
            AccountNotificationDirective(
                notification_type=notification_type(product_name=product_name),
                notification_details={
                    "account_id": account_id,
                    "deposit_balance": str(net_balance),
                    "deposit_period_end_datetime": str(effective_datetime),
                    "reason": "Close account due to lack of deposits at the end of deposit period",
                },
            )
        ]
    return []


def get_deposit_period_end_datetime(*, vault: SmartContractVault) -> datetime:
    """
    Calculates and returns the deposit period end datetime. This date will represent the
    midnight of the account creation datetime plus the number of days in the deposit period,
    inclusive of the account creation datetime.
    :param vault: Vault object for the account
    :return: the datetime when the deposit period ends
    """
    account_creation_datetime = vault.get_account_creation_datetime()
    deposit_period = _get_deposit_period_parameter(vault=vault)
    return (account_creation_datetime + relativedelta(days=deposit_period)).replace(
        hour=23, minute=59, second=59, microsecond=999999, tzinfo=ZoneInfo("UTC")
    )


def is_within_deposit_period(*, vault: SmartContractVault, effective_datetime: datetime) -> bool:
    """
    Determines whether an effective datetime is within the deposit period of an account

    :param deposit_period_end_datetime: the end datetime of the deposit period
    :param effective_datetime: datetime to be checked whether is within the deposit period
    :return: bool, True if the effective datetime is less than or equal to the
    deposit period end datetime
    """
    return effective_datetime <= get_deposit_period_end_datetime(vault=vault)


def _get_deposit_period_parameter(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils.get_parameter(vault=vault, name=PARAM_DEPOSIT_PERIOD, at_datetime=effective_datetime)
    )


def _get_number_of_permitted_deposits_parameter(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    return str(
        utils.get_parameter(
            vault=vault,
            name=PARAM_NUMBER_OF_PERMITTED_DEPOSITS,
            at_datetime=effective_datetime,
            is_union=True,
        )
    )
