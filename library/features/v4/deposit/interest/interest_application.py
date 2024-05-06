# CBF:  Scheduled Deposit Interest Application

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Optional

# features
import library.features.v4.common.accruals as accruals
import library.features.common.fetchers as fetchers
import library.features.v4.common.interest_accrual_common as interest_accrual_common
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
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

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Event
APPLICATION_EVENT = "APPLY_INTEREST"

# Fetchers
data_fetchers = [fetchers.EFFECTIVE_OBSERVATION_FETCHER]

# Balance Addresses
ACCRUED_INTEREST_PAYABLE_ADDRESS = "ACCRUED_INTEREST_PAYABLE"
ACCRUED_INTEREST_RECEIVABLE_ADDRESS = "ACCRUED_INTEREST_RECEIVABLE"

# Parameters
INTEREST_APPLICATION_PREFIX = "interest_application"
PARAM_INTEREST_APPLICATION_DAY = f"{INTEREST_APPLICATION_PREFIX}_day"
PARAM_INTEREST_APPLICATION_FREQUENCY = f"{INTEREST_APPLICATION_PREFIX}_frequency"
PARAM_INTEREST_APPLICATION_HOUR = f"{INTEREST_APPLICATION_PREFIX}_hour"
PARAM_INTEREST_APPLICATION_MINUTE = f"{INTEREST_APPLICATION_PREFIX}_minute"
PARAM_INTEREST_APPLICATION_SECOND = f"{INTEREST_APPLICATION_PREFIX}_second"
schedule_params = [
    Parameter(
        name=PARAM_INTEREST_APPLICATION_DAY,
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=ParameterLevel.INSTANCE,
        description="The day of the month on which interest is applied. If day does not exist"
        " in application month, applies on last day of month.",
        display_name="Interest Application Day",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name=PARAM_INTEREST_APPLICATION_FREQUENCY,
        level=ParameterLevel.TEMPLATE,
        description="The frequency at which interest is applied.",
        display_name="Interest Application Frequency",
        shape=UnionShape(
            items=[
                UnionItem(key=utils.MONTHLY, display_name="Monthly"),
                UnionItem(key=utils.QUARTERLY, display_name="Quarterly"),
                UnionItem(key=utils.ANNUALLY, display_name="Annually"),
            ]
        ),
        default_value=UnionItemValue(key=utils.MONTHLY),
    ),
    Parameter(
        name=PARAM_INTEREST_APPLICATION_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which interest is applied.",
        display_name="Interest Application Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_INTEREST_APPLICATION_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which interest is applied.",
        display_name="Interest Application Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_INTEREST_APPLICATION_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which interest is applied.",
        display_name="Interest Application Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=1,
    ),
]

PARAM_APPLICATION_PRECISION = "application_precision"
PARAM_INTEREST_PAID_ACCOUNT = "interest_paid_account"
PARAM_INTEREST_RECEIVED_ACCOUNT = "interest_received_account"
parameters = [
    # Template parameters
    Parameter(
        name=PARAM_APPLICATION_PRECISION,
        level=ParameterLevel.TEMPLATE,
        description="Precision needed for interest applications.",
        display_name="Interest Application Precision",
        shape=NumberShape(min_value=0, max_value=15, step=1),
        default_value=2,
    ),
    # Internal accounts
    Parameter(
        name=PARAM_INTEREST_PAID_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for interest paid.",
        display_name="Interest Paid Account",
        shape=AccountIdShape(),
        default_value="APPLIED_INTEREST_PAID",
    ),
    Parameter(
        name=PARAM_INTEREST_RECEIVED_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for interest received.",
        display_name="Interest Received Account",
        shape=AccountIdShape(),
        default_value="APPLIED_INTEREST_RECEIVED",
    ),
    *schedule_params,
]


def event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=APPLICATION_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{APPLICATION_EVENT}_AST"],
        )
    ]


def scheduled_events(
    *,
    vault: SmartContractVault,
    reference_datetime: datetime,
) -> dict[str, ScheduledEvent]:
    """
    Creates list of execution schedules for interest application
    :param vault: Vault object to retrieve application frequency and schedule params
    :param reference_datetime: Anchor datetime to determine when schedules should start from
    e.g. account creation datetime
    :return: dict of interest application scheduled events
    """
    application_frequency: str = utils.get_parameter(
        vault, name=PARAM_INTEREST_APPLICATION_FREQUENCY, is_union=True
    )
    start_datetime = reference_datetime.replace(hour=0, minute=0, second=0, microsecond=0)

    if application_frequency == utils.MONTHLY:
        start_datetime = start_datetime + relativedelta(days=1)
        scheduled_event = utils.monthly_scheduled_event(
            vault=vault, start_datetime=start_datetime, parameter_prefix=INTEREST_APPLICATION_PREFIX
        )
    else:
        schedule_day = int(utils.get_parameter(vault, name=PARAM_INTEREST_APPLICATION_DAY))
        next_datetime = utils.get_next_schedule_date(
            start_date=start_datetime,
            schedule_frequency=application_frequency,
            intended_day=schedule_day,
        )

        # TODO: opened INC-8478 to investigate the issue with year=None
        schedule_expression = utils.get_schedule_expression_from_parameters(
            vault=vault,
            parameter_prefix=INTEREST_APPLICATION_PREFIX,
            day=next_datetime.day,
            month=next_datetime.month,
            year=(
                None
                if (
                    application_frequency == utils.ANNUALLY
                    and (
                        int(next_datetime.month) != 2
                        or (int(next_datetime.month) == 2 and schedule_day < 29)
                    )
                )
                else next_datetime.year
            ),
        )

        # adding a month to start_datetime param to apply interest for the first time
        # on the following year and not on the current one
        if application_frequency == utils.ANNUALLY:
            start_datetime = start_datetime + relativedelta(months=1)
        else:
            # the schedule frequency is quarterly and thus we need to ensure the start datetime is
            # not in the past
            start_datetime = start_datetime + relativedelta(days=1)

        scheduled_event = ScheduledEvent(
            start_datetime=start_datetime, expression=schedule_expression
        )

    return {APPLICATION_EVENT: scheduled_event}


def apply_interest(
    *,
    vault: SmartContractVault,
    account_type: str = "",
    balances: Optional[BalanceDefaultDict] = None,
) -> list[CustomInstruction]:
    """
    Creates the posting instructions to consolidate accrued interest.
    Debit the rounded amount from the customer accrued address and credit the internal account
    Debit the rounded amount from the internal account to the customer applied address

    :param vault: the vault object to use for retrieving data and instructing directives
    :param account_type: the account type used to apply interest
    :param balances: balances to pass through to function. If not passed in, defaults to None
    and the function will fetch balances using EFFECTIVE_OBSERVATION_FETCHER

    :return: the accrual posting instructions
    """
    posting_instructions: list[CustomInstruction] = []

    interest_paid_account: str = utils.get_parameter(vault, name=PARAM_INTEREST_PAID_ACCOUNT)
    interest_received_account: str = utils.get_parameter(
        vault, name=PARAM_INTEREST_RECEIVED_ACCOUNT
    )
    accrued_interest_payable_account = (
        interest_accrual_common.get_accrued_interest_payable_account_parameter(vault=vault)
    )
    accrued_interest_receivable_account = (
        interest_accrual_common.get_accrued_interest_receivable_account_parameter(vault=vault)
    )

    application_precision: int = utils.get_parameter(vault, name=PARAM_APPLICATION_PRECISION)
    denomination: str = utils.get_parameter(vault, name="denomination")

    balances = (
        balances
        or vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    )

    if amount_accrued_receivable := utils.sum_balances(
        balances=balances,
        addresses=[ACCRUED_INTEREST_RECEIVABLE_ADDRESS],
        denomination=denomination,
    ):
        rounded_accrual = utils.round_decimal(amount_accrued_receivable, application_precision)

        posting_instructions.extend(
            accruals.accrual_application_custom_instruction(
                customer_account=vault.account_id,
                denomination=denomination,
                application_amount=abs(rounded_accrual),
                accrual_amount=abs(amount_accrued_receivable),
                instruction_details=utils.standard_instruction_details(
                    description=f"Apply {rounded_accrual} {denomination} interest of "
                    f"{amount_accrued_receivable} rounded to {application_precision} and "
                    f"consolidate {amount_accrued_receivable} {denomination} to {vault.account_id}",
                    event_type=APPLICATION_EVENT,
                    gl_impacted=True,
                    account_type=account_type,
                ),
                accrual_customer_address=ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                accrual_internal_account=accrued_interest_receivable_account,
                application_customer_address=DEFAULT_ADDRESS,
                application_internal_account=interest_received_account,
                payable=False,
            )
        )

    if amount_accrued_payable := utils.sum_balances(
        balances=balances,
        addresses=[ACCRUED_INTEREST_PAYABLE_ADDRESS],
        denomination=denomination,
    ):
        rounded_accrual = utils.round_decimal(amount_accrued_payable, application_precision)

        posting_instructions.extend(
            accruals.accrual_application_custom_instruction(
                customer_account=vault.account_id,
                denomination=denomination,
                application_amount=abs(rounded_accrual),
                accrual_amount=abs(amount_accrued_payable),
                instruction_details=utils.standard_instruction_details(
                    description=f"Apply {rounded_accrual} {denomination} interest of "
                    f"{amount_accrued_payable} rounded to {application_precision} and "
                    f"consolidate {amount_accrued_payable} {denomination} to {vault.account_id}",
                    event_type=APPLICATION_EVENT,
                    gl_impacted=True,
                    account_type=account_type,
                ),
                accrual_customer_address=ACCRUED_INTEREST_PAYABLE_ADDRESS,
                accrual_internal_account=accrued_interest_payable_account,
                application_customer_address=DEFAULT_ADDRESS,
                application_internal_account=interest_paid_account,
                payable=True,
            )
        )

    return posting_instructions


def update_next_schedule_execution(
    *, vault: SmartContractVault, effective_datetime: datetime
) -> Optional[UpdateAccountEventTypeDirective]:
    """
    Update next scheduled execution if frequency not monthly or annually with
    intended month not february

    :param vault: Vault object to retrieve interest application params
    :param effective_datetime: datetime the schedule is running
    :return: optional update event directive
    """
    # No need to reschedule these as the scheduler knows the next runtime from creation
    application_frequency: str = utils.get_parameter(
        vault, PARAM_INTEREST_APPLICATION_FREQUENCY, is_union=True
    )
    if application_frequency == utils.MONTHLY:
        return None
    else:
        schedule_day = int(utils.get_parameter(vault, name=PARAM_INTEREST_APPLICATION_DAY))
        # no need to reschedule if annual frequency and application month not february or
        # schedule day < 29 since there's no leap year logic to adapt
        if application_frequency == utils.ANNUALLY and (
            int(effective_datetime.month) != 2
            or (int(effective_datetime.month) == 2 and schedule_day < 29)
        ):
            return None

        new_schedule = scheduled_events(vault=vault, reference_datetime=effective_datetime)

        return UpdateAccountEventTypeDirective(
            event_type=APPLICATION_EVENT, expression=new_schedule[APPLICATION_EVENT].expression
        )
