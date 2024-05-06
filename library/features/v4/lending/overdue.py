# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional, Union

# features
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_addresses as lending_addresses

# contracts api
from contracts_api import (
    DEFAULT_ASSET,
    AccountNotificationDirective,
    BalanceDefaultDict,
    CustomInstruction,
    DateShape,
    NumberShape,
    Parameter,
    ParameterLevel,
    Posting,
    ScheduledEvent,
    ScheduledEventHookArguments,
    SmartContractEventType,
    SupervisorContractEventType,
    SupervisorScheduledEventHookArguments,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

CHECK_OVERDUE_EVENT = "CHECK_OVERDUE"
CHECK_OVERDUE_PREFIX = "check_overdue"

PARAM_CHECK_OVERDUE_HOUR = f"{CHECK_OVERDUE_PREFIX}_hour"
PARAM_CHECK_OVERDUE_MINUTE = f"{CHECK_OVERDUE_PREFIX}_minute"
PARAM_CHECK_OVERDUE_SECOND = f"{CHECK_OVERDUE_PREFIX}_second"
PARAM_NEXT_OVERDUE_DATE = "next_overdue_date"
PARAM_REPAYMENT_PERIOD = "repayment_period"

# Notifications
OVERDUE_REPAYMENT_NOTIFICATION_SUFFIX = "_OVERDUE_REPAYMENT"

FUND_MOVEMENT_MAP = {
    lending_addresses.PRINCIPAL_DUE: lending_addresses.PRINCIPAL_OVERDUE,
    lending_addresses.INTEREST_DUE: lending_addresses.INTEREST_OVERDUE,
}

schedule_parameters = [
    Parameter(
        name=PARAM_CHECK_OVERDUE_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which overdue is checked.",
        display_name="Check Overdue Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_CHECK_OVERDUE_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which overdue is checked.",
        display_name="Check Overdue Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_CHECK_OVERDUE_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which overdue is checked.",
        display_name="Check Overdue Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_REPAYMENT_PERIOD,
        level=ParameterLevel.TEMPLATE,
        description="The number of days after which due amounts are made overdue.",
        display_name="Repayment Period (Days)",
        shape=NumberShape(min_value=1, max_value=27, step=1),
        default_value=1,
    ),
]

next_overdue_derived_parameter = Parameter(
    name=PARAM_NEXT_OVERDUE_DATE,
    shape=DateShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="The date on which current due principal and interest will become overdue.",
    display_name="Next Overdue Date",
)


def get_repayment_period_parameter(vault: SmartContractVault) -> int:
    return int(utils.get_parameter(vault=vault, name=PARAM_REPAYMENT_PERIOD))


def get_next_overdue_derived_parameter(
    vault: SmartContractVault,
    previous_due_amount_calculation_datetime: datetime,
) -> datetime:
    return previous_due_amount_calculation_datetime + relativedelta(
        days=get_repayment_period_parameter(vault=vault)
    )


def event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=CHECK_OVERDUE_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{CHECK_OVERDUE_EVENT}_AST"],
        )
    ]


def supervisor_event_types(product_name: str) -> list[SupervisorContractEventType]:
    return [
        SupervisorContractEventType(
            name=CHECK_OVERDUE_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{CHECK_OVERDUE_EVENT}_AST"],
        )
    ]


def notification_type(product_name: str) -> str:
    """
    Creates the notification type
    :param product_name: The product name
    :return: str
    """
    return f"{product_name.upper()}{OVERDUE_REPAYMENT_NOTIFICATION_SUFFIX}"


def scheduled_events(
    vault: SmartContractVault,
    first_due_amount_calculation_datetime: datetime,
    is_one_off: bool = False,
    skip: bool = False,
) -> dict[str, ScheduledEvent]:
    """
    Create a check overdue schedule by calculating the date on which the schedule will run
    from the first due amount calculation date and the repayment period. The time component is
    determined by the `check_overdue_<>` schedule time parameters. This schedule can either be a
    monthly recurring schedule, executed once or initially skipped.
    :param vault: the Vault object
    :param first_due_amount_calculation_datetime: the datetime on which the first due amount is
    calculated, used to determine the next overdue check date ignoring the time component
    :param is_one_off: whether the schedule is recurring or a one-off schedule
    :param skip: if True, schedule will be skipped indefinitely until this field is updated,
    defaults to False
    :return: a dictionary containing the check late repayment schedule
    """
    repayment_period = int(utils.get_parameter(vault=vault, name=PARAM_REPAYMENT_PERIOD))
    next_overdue_check_datetime = first_due_amount_calculation_datetime + relativedelta(
        days=repayment_period
    )

    year = next_overdue_check_datetime.year if is_one_off else None
    month = next_overdue_check_datetime.month if is_one_off else None
    return {
        CHECK_OVERDUE_EVENT: ScheduledEvent(
            start_datetime=next_overdue_check_datetime.replace(hour=0, minute=0, second=0),
            expression=utils.get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=CHECK_OVERDUE_PREFIX,
                day=next_overdue_check_datetime.day,
                month=month,
                year=year,
            ),
            skip=skip,
        )
    }


def schedule_logic(
    vault: SmartContractVault,
    hook_arguments: Union[
        ScheduledEventHookArguments,
        SupervisorScheduledEventHookArguments,
    ],
    balances: Optional[BalanceDefaultDict] = None,
    account_type: str = "",
    late_repayment_fee: Decimal = Decimal("0")
    # TODO: other flags for possible admin blockings, and the passing of date
) -> tuple[list[CustomInstruction], list[AccountNotificationDirective]]:
    """
    Creates postings to credit principal or interest due amounts and debit the
    corresponding overdue addresses at the end of the repayment period.
    :param vault: the vault object for the account to perform overdue amount updates for
    :param hook_arguments: the hook arguments as received from the contract
    :param balances: balances to use for overdue amounts. If not provided balances fetched
    as of effective datetime are used
    :param account_type: the account type as to be noted in custom instruction detail
    :param late_repayment_fee: Fee to apply due to late repayment.
    :return: tuple list of overdue amount custom instructions and overdue repayment notifications
    """
    postings: list[Posting] = []
    denomination: str = utils.get_parameter(vault=vault, name="denomination")
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances

    account_id = vault.account_id
    due_amounts = {}
    for due_address, overdue_address in FUND_MOVEMENT_MAP.items():
        due_amounts[due_address] = utils.balance_at_coordinates(
            balances=balances,
            address=due_address,
            denomination=denomination,
        )
        postings += utils.create_postings(
            amount=due_amounts[due_address],
            debit_account=account_id,
            credit_account=account_id,
            debit_address=overdue_address,
            credit_address=due_address,
            denomination=denomination,
            asset=DEFAULT_ASSET,
        )

    if not postings:
        return [], []
    custom_instructions = [
        CustomInstruction(
            postings=postings,
            override_all_restrictions=True,
            instruction_details=utils.standard_instruction_details(
                description="Move outstanding due debt into overdue debt.",
                event_type=hook_arguments.event_type,
                gl_impacted=False,
                account_type=account_type,
            ),
        )
    ]
    notifications: list[AccountNotificationDirective] = []
    # getting the due amounts since they will become overdue
    notifications.extend(
        get_overdue_repayment_notification(
            account_id=account_id,
            product_name=account_type,
            effective_datetime=hook_arguments.effective_datetime,
            overdue_principal_amount=due_amounts[lending_addresses.PRINCIPAL_DUE],
            overdue_interest_amount=due_amounts[lending_addresses.INTEREST_DUE],
            late_repayment_fee=late_repayment_fee,
        )
    )
    return custom_instructions, notifications


def get_overdue_repayment_notification(
    account_id: str,
    product_name: str,
    effective_datetime: datetime,
    overdue_principal_amount: Decimal,
    overdue_interest_amount: Decimal,
    late_repayment_fee: Decimal = Decimal("0"),
) -> list[AccountNotificationDirective]:
    """
    Instruct overdue repayment notification.

    :param account_id: vault account_id
    :param product_name: the name of the product for the workflow prefix
    :param effective_datetime: datetime, the effective date overdue schedule executes
    :param overdue_principal_amount: Decimal, The amount from PRINCIPAL_DUE
    that will become overdue.
    :param overdue_interest_amount: Decimal, The amount from INTEREST_DUE that will become overdue.
    :param late_repayment_fee: Fee to apply due to late repayment.
    :return: list[AccountNotificationDirective]
    """
    if overdue_principal_amount + overdue_interest_amount > 0:
        return [
            AccountNotificationDirective(
                notification_type=notification_type(product_name),
                notification_details={
                    "account_id": account_id,
                    "overdue_principal": str(overdue_principal_amount),
                    "overdue_interest": str(overdue_interest_amount),
                    "late_repayment_fee": str(late_repayment_fee),
                    "overdue_date": str(effective_datetime.date()),
                },
            )
        ]
    return []


def get_overdue_datetime(
    due_amount_notification_datetime: datetime,
    repayment_period: int,
    notification_period: int,
) -> datetime:
    """
    returns the overdue datetime (hour, minute and second are not considered) given the
    due amount notification date
    :param vault: vault object
    :param due_amount_notification_datetime: the date when the due amount
    notification will take place.
    :param repayment_period: The number of days after which due amounts are made overdue.
    :param notification_period: The number of days prior to a payment becoming due,
    send a due notification reminder to the user.
    :return: datetime
    """
    return due_amount_notification_datetime + relativedelta(
        days=int(notification_period + repayment_period)
    )
