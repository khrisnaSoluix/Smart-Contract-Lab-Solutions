# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Optional
from decimal import Decimal

# features
import library.features.v4.common.accruals as accruals
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.shariah.fixed_profit_accrual as fixed_profit_accrual
import library.features.v4.deposit.deposit_maturity_mdh as deposit_maturity_mdh
import library.features.v4.deposit.deposit_parameters as deposit_parameters

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
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
    Phase, 
    Posting,
    DateShape
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Event
APPLICATION_EVENT = "APPLY_PROFIT"
REVERSAL_PROFIT_EVENT = "REVERSAL_PROFIT"
# Fetchers
data_fetchers = [fetchers.EOD_FETCHER]

# Balance Addresses
ACCRUED_PROFIT_PAYABLE = "&{fixed_profit_accrual.ACCRUED_PROFIT_PAYABLE}"
APPLIED_PROFIT = "APPLIED_PROFIT"
TAX_RECEIVABLE_ACOUNT = "TAX_RECEIVABLE_ACOUNT"
ZAKAT_RECEIVABLE_ACOUNT = "ZAKAT_RECEIVABLE_ACOUNT"

# Parameters
PROFIT_APPLICATION_PREFIX = "profit_application"
PARAM_LAST_PROFIT_APPLICATION_DATE = "last_profit_application_date"
PARAM_NEXT_PROFIT_APPLICATION_DATE = "next_profit_application_date"
PARAM_TAX_RATE = "tax_rate"
PARAM_PROFIT_APPLICATION_FREQUENCY = f"{PROFIT_APPLICATION_PREFIX}_frequency"
PARAM_PROFIT_APPLICATION_HOUR = f"{PROFIT_APPLICATION_PREFIX}_hour"
PARAM_PROFIT_APPLICATION_MINUTE = f"{PROFIT_APPLICATION_PREFIX}_minute"
PARAM_PROFIT_APPLICATION_SECOND = f"{PROFIT_APPLICATION_PREFIX}_second"
schedule_params = [
    Parameter(
        name=PARAM_PROFIT_APPLICATION_FREQUENCY,
        level=ParameterLevel.TEMPLATE,
        description="The frequency at which profit is applied.",
        display_name="Profit Application Frequency",
        shape=UnionShape(
            items=[
                UnionItem(key="monthly", display_name="Monthly"),
                UnionItem(key="quarterly", display_name="Quarterly"),
                UnionItem(key="annually", display_name="Annually"),
            ]
        ),
        default_value=UnionItemValue(key="monthly"),
    ),
    Parameter(
        name=PARAM_PROFIT_APPLICATION_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which profit is applied.",
        display_name="Profit Application Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_PROFIT_APPLICATION_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which profit is applied.",
        display_name="Profit Application Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=PARAM_PROFIT_APPLICATION_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which profit is applied.",
        display_name="Profit Application Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=1,
    ),
]

PARAM_APPLICATION_PRECISION = "application_precision"
PARAM_PROFIT_PAID_ACCOUNT = "profit_paid_account"

PARAM_TAX_RECEIVABLE_ACOUNT = "tax_receivable_account"
PARAM_ZAKAT_RECEIVABLE_ACOUNT = "zakat_receivable_account"
PARAM_ZAKAT_RATE = "zakat_rate"

parameters = [
    # Template parameters
    Parameter(
        name=PARAM_APPLICATION_PRECISION,
        level=ParameterLevel.TEMPLATE,
        description="Precision needed for profit applications.",
        display_name="Profit Application Precision",
        shape=NumberShape(min_value=0, max_value=15, step=1),
        default_value=2,
    ),
    # Internal accounts
    Parameter(
        name=PARAM_PROFIT_PAID_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for profit paid.",
        display_name="Profit Paid Account",
        shape=AccountIdShape(),
        default_value="APPLIED_PROFIT_PAID",
    ),
    *schedule_params,
]

additional_parameters=[
    # Instance parameters
    Parameter(
        name=PARAM_ZAKAT_RATE,
        level=ParameterLevel.INSTANCE,
         description="Percentage of zakat to be deducted from the net revenue sharing amount"
        " received by the customer every month.",
        display_name="Zakat rate",
        shape=NumberShape(min_value=0, max_value=100, step=Decimal('0.0001')),
        default_value=Decimal("0.00"),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    # Internal accounts
    Parameter(
        name=PARAM_ZAKAT_RECEIVABLE_ACOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for zakat receivable.",
        display_name="Zakat Receivable Account",
        shape=AccountIdShape(),
        default_value="ZAKAT_RECEIVABLE_ACCOUNT",
    ),
    Parameter(
        name=PARAM_TAX_RECEIVABLE_ACOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for tax receivable.",
        display_name="Tax Receivable Account",
        shape=AccountIdShape(),
        default_value="TAX_RECEIVABLE_ACCOUNT",
    ),
    Parameter(
        name=PARAM_LAST_PROFIT_APPLICATION_DATE,
        shape=DateShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The last profit application date schedule was run.",
        display_name="Last Profit Application Date",
    ),
    Parameter(
        name=PARAM_NEXT_PROFIT_APPLICATION_DATE,
        shape=DateShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The next profit application date schedule will run.",
        display_name="Next Profit Application Date",
    )
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
    start_datetime: datetime,
) -> dict[str, ScheduledEvent]:
    """
    Creates list of execution schedules for profit application
    :param vault: Vault object to retrieve application frequency and schedule params
    :param start_datetime: date to start schedules from e.g. account creation or loan start date
    :return: dict of profit application scheduled events
    """
    application_frequency: str = utils.get_parameter(
        vault, name=PARAM_PROFIT_APPLICATION_FREQUENCY, is_union=True
    )
    oncall_date = utils.get_parameter(vault, name=deposit_maturity_mdh.PARAM_DESIRED_MATURITY_DATE,is_optional=True)
    if oncall_date:
        schedule_day = int(oncall_date.day)
    else:
        deposit_date=utils.get_parameter(vault, name=deposit_parameters.PARAM_ACTIVATION_DATE)
        if deposit_date:
            schedule_day = int(deposit_date.day)
        else:
            schedule_day=int(start_datetime.day)

    schedule_hour, schedule_minute, schedule_second = utils.get_schedule_time_from_parameters(
        vault=vault, parameter_prefix=PROFIT_APPLICATION_PREFIX
    )

    calendar_events = vault.get_calendar_events(calendar_ids=["&{PUBLIC_HOLIDAYS}"])

    next_datetime = utils.get_next_schedule_date_calendar_aware(
        start_datetime=start_datetime,
        schedule_frequency=application_frequency,
        intended_day=schedule_day,
        calendar_events=calendar_events,
    )
    modified_expression = utils.one_off_schedule_expression(
        next_datetime
        + relativedelta(hour=schedule_hour, minute=schedule_minute, second=schedule_second)
    )

    scheduled_event = ScheduledEvent(start_datetime=start_datetime, expression=modified_expression)

    return {APPLICATION_EVENT: scheduled_event}


def get_next_profit_application_date(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
) -> datetime:
    """
    Creates list of execution schedules for profit application
    :param vault: Vault object to retrieve application frequency and schedule params
    :param start_datetime: date to start schedules from e.g. account creation or loan start date
    :return: dict of profit application scheduled events
    """
    application_frequency: str = utils.get_parameter(
        vault, name=PARAM_PROFIT_APPLICATION_FREQUENCY, is_union=True
    )
    oncall_date = utils.get_parameter(vault, name=deposit_maturity_mdh.PARAM_DESIRED_MATURITY_DATE,is_optional=True)
    if oncall_date:
        schedule_day = int(oncall_date.day)
    else:
        deposit_date=utils.get_parameter(vault, name=deposit_parameters.PARAM_ACTIVATION_DATE)
        if deposit_date:
            schedule_day = int(deposit_date.day)
        else:
            schedule_day=int(effective_datetime.day)

    schedule_hour, schedule_minute, schedule_second = utils.get_schedule_time_from_parameters(
        vault=vault, parameter_prefix=PROFIT_APPLICATION_PREFIX
    )

    calendar_events = vault.get_calendar_events(calendar_ids=["&{PUBLIC_HOLIDAYS}"])

    next_datetime = utils.get_next_schedule_date_calendar_aware(
        start_datetime=effective_datetime,
        schedule_frequency=application_frequency,
        intended_day=schedule_day,
        calendar_events=calendar_events,
    )
    next_datetime=next_datetime + relativedelta(hour=schedule_hour, minute=schedule_minute, second=schedule_second)
    
    return next_datetime

def apply_profit(
    *,
    vault: SmartContractVault,
    accrual_address: str = 'ACCRUED_PROFIT_PAYABLE',
    applied_profit_address: str =APPLIED_PROFIT,
    account_type: Optional[str] = None,
    denomination: str
) -> list[CustomInstruction]:
    """
    Creates the posting instructions to consolidate accrued profit.
    Debit the rounded amount from the customer accrued address and credit the internal account
    Debit the rounded amount from the internal account to the customer applied address
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param accrual_address: the address to check for profit that has accumulated
    :return: the accrual posting instructions
    """

    accrued_profit_payable_account: str = utils.get_parameter(
        vault, name=fixed_profit_accrual.PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT
    )

    zakat_receivable_acount: str = utils.get_parameter(
        vault, name=PARAM_ZAKAT_RECEIVABLE_ACOUNT
    )
    zakat_rate = utils.get_parameter(
        vault, name=PARAM_ZAKAT_RATE
    )
    zakat_rate = Decimal(zakat_rate) if zakat_rate else Decimal('0')

    tax_receivable_acount: str = utils.get_parameter(
        vault, name=PARAM_TAX_RECEIVABLE_ACOUNT
    )
    tax_rate = utils.get_parameter(
        vault, name=PARAM_TAX_RATE
    )
    tax_rate = Decimal(tax_rate) if tax_rate else Decimal('0')

    profit_paid_account: str = utils.get_parameter(vault, name=PARAM_PROFIT_PAID_ACCOUNT)

    application_precision: int = utils.get_parameter(vault, name=PARAM_APPLICATION_PRECISION)

    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances
    amount_accrued = utils.balance_at_coordinates(
        balances=balances,
        address=accrual_address,
        denomination=denomination,
    )

    rounded_accrual = utils.round_decimal(amount_accrued, application_precision)

    posting_instructions: list[CustomInstruction] = []

    # negative profit not supported
    if amount_accrued > 0:
        zakat_calculated= Decimal('0.00')
        tax_calculated= Decimal('0.00')
        if account_type is None:
            account_type = ""

        # Apply Zakat
        if zakat_rate>0:
            zakat_calculated = utils.round_decimal(
                (amount_accrued) * zakat_rate, application_precision
            )
            if zakat_calculated > 0:
                posting_instructions.extend(
                    addiitonal_application_custom_instruction(
                        customer_account=vault.account_id,
                        denomination=denomination,
                        application_amount=abs(zakat_calculated),
                        instruction_details=utils.standard_instruction_details(
                            description=f"Apply {zakat_calculated} {denomination} zakat of "
                            f"{amount_accrued} rounded to {application_precision}",
                            event_type=APPLICATION_EVENT,
                            gl_impacted=True,
                            account_type=account_type,
                        ),
                        application_customer_address=applied_profit_address,
                        application_internal_account=zakat_receivable_acount,
                        payable=False,
                    )
                )
        # Apply Tax
        if tax_rate>0:
            tax_calculated = utils.round_decimal(
                (amount_accrued) * tax_rate, application_precision
            )
            if tax_calculated > 0:
                posting_instructions.extend(
                    addiitonal_application_custom_instruction(
                        customer_account=vault.account_id,
                        denomination=denomination,
                        application_amount=abs(tax_calculated),
                        instruction_details=utils.standard_instruction_details(
                            description=f"Apply {tax_calculated} {denomination} tax of "
                            f"{amount_accrued} rounded to {application_precision}",
                            event_type=APPLICATION_EVENT,
                            gl_impacted=True,
                            account_type=account_type,
                        ),
                        application_customer_address=applied_profit_address,
                        application_internal_account=tax_receivable_acount,
                        payable=False,
                    )
                )

        posting_instructions.extend(
            accruals.accrual_application_custom_instruction(
                customer_account=vault.account_id,
                denomination=denomination,
                application_amount=abs(rounded_accrual),
                accrual_amount=abs(amount_accrued),
                instruction_details=utils.standard_instruction_details(
                    description=f"Apply {rounded_accrual} {denomination} profit of "
                    f"{amount_accrued} rounded to {application_precision} and "
                    f"consolidate {amount_accrued} {denomination} to {vault.account_id}",
                    event_type=APPLICATION_EVENT,
                    gl_impacted=True,
                    account_type=account_type,
                ),
                accrual_customer_address=accrual_address,
                accrual_internal_account=accrued_profit_payable_account,
                application_customer_address=applied_profit_address,
                application_internal_account=profit_paid_account,
                payable=True,
            )
        )

    return posting_instructions


def update_next_schedule_execution(
    *, vault: SmartContractVault, effective_datetime: datetime
) -> Optional[UpdateAccountEventTypeDirective]:
    """
    Update next scheduled execution.
    :param vault: Vault object to retrieve profit application params
    :param effective_datetime: datetime the schedule is running
    :return: update event directive
    """
    new_schedule = scheduled_events(vault=vault, start_datetime=effective_datetime)

    return UpdateAccountEventTypeDirective(
        event_type=APPLICATION_EVENT, expression=new_schedule[APPLICATION_EVENT].expression
    )


def get_profit_reversal_postings(
    *,
    vault: SmartContractVault,
    profit_address: str = APPLIED_PROFIT,
    event_name: str = REVERSAL_PROFIT_EVENT,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    account_type: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Reverse any accrued profit and apply back to the internal account.
    During account closure, any positively accrued profit that has not been applied
    should return back to the bank's internal account.
    :param vault: the vault object used to create profit reversal postings
    :param accrued_profit_address: the balance address used to store the accrued profit
    :param event_name: the name of the event reversing any accrue profit
    :param balances: balances to use to get profit to reverse. Defaults to previous EOD balances
    if not, relative to hook execution effective datetime
    :param denomination: the denomination of the profit accruals to reverse
    :param account_type: the account type to be populated on posting instruction details
    :return: the accrued profit reversal posting instructions
    """
    accrued_profit_payable_account: str = utils.get_parameter(
        vault, name=fixed_profit_accrual.PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT
    )
    if denomination is None:
        denomination = str(utils.get_parameter(vault, name="denomination"))
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    applied_profit = get_applied_profit(
        balances=balances,
        denomination=denomination,
        profit_address=profit_address,
    )

    instruction_details = utils.standard_instruction_details(
        description=f"Reversal of applied profit of value {applied_profit} {denomination}"
        " due to account closure.",
        event_type=f"{event_name}",
        gl_impacted=True,
        account_type=account_type or "",
    )

    # negative profit accruals are not supported
    if applied_profit > 0:
        return accruals.accrual_custom_instruction(
            customer_account=vault.account_id,
            customer_address=profit_address,
            denomination=denomination,
            amount=applied_profit,
            internal_account=accrued_profit_payable_account,
            payable=True,
            instruction_details=instruction_details,
            reversal=True,
        )
    else:
        return []


def get_applied_profit(
    *,
    balances: BalanceDefaultDict,
    denomination: str,
    profit_address: str = APPLIED_PROFIT,
) -> Decimal:
    """
    Retrieves the existing balance for accrued profit at a specific time
    :param balances: the balances to sum accrued profit
    :param denomination: the denomination of the capital balances and the profit accruals
    :param accrued_profit_address: the address name in which we are storing the accrued profit
    :return: the value of the balance at the requested time
    """
    return utils.balance_at_coordinates(
        balances=balances, address=profit_address, denomination=denomination
    )


def addiitonal_application_custom_instruction(
    customer_account: str,
    denomination: str,
    application_amount: Decimal,
    instruction_details: dict[str, str],
    application_customer_address: str,
    application_internal_account: str,
    payable: bool,
) -> list[CustomInstruction]:

    """
    Create a Custom Instruction containing customer and internal account postings for applying
    an accrued charge.
    :param customer_account: the customer account id to use
    :param denomination: the denomination of the application
    :param application_amount: the amount to apply. If <= 0 empty list is returned
    :param accrual_amount: the amount accrued prior to application
    :param instruction_details: instruction details to add to the postings
    :param accrual_customer_address: the address to use on the customer account for accruals
    :param accrual_internal_account: the internal account id to use for accruals. The default
     address is always used on this account
    :param application_customer_address: the address to use on the customer account for application
    :param application_internal_account: the internal account id to use for application.
    The default address is always used on this account
    :param payable: set to True if applying a payable charge, or False for a receivable charge
    :return: Custom instructions to apply interest, if required
    """

    if application_amount <= 0:
        return []

    if payable:
        debit_account = application_internal_account
        debit_address = DEFAULT_ADDRESS
        credit_account = customer_account
        credit_address = application_customer_address
    else:
        debit_account = customer_account
        debit_address = application_customer_address
        credit_account = application_internal_account
        credit_address = DEFAULT_ADDRESS

    postings = [
        Posting(
            credit=True,
            amount=application_amount,
            denomination=denomination,
            account_id=credit_account,
            account_address=credit_address,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=False,
            amount=application_amount,
            denomination=denomination,
            account_id=debit_account,
            account_address=debit_address,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
    ]
    if postings:
        return [
            CustomInstruction(
                postings=postings,
                instruction_details=instruction_details,
                override_all_restrictions=True,
            )
        ]
    else:
        return []

