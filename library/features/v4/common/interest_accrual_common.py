# standard libs
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Union

# features
import library.features.v4.common.accruals as accruals
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    AccountIdShape,
    CustomInstruction,
    NumberShape,
    Parameter,
    ParameterLevel,
    ScheduledEvent,
    ScheduleSkip,
    SmartContractEventType,
    UnionItem,
    UnionItemValue,
    UnionShape,
    UpdateAccountEventTypeDirective,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Events
ACCRUAL_EVENT = "ACCRUE_INTEREST"

# Balance Addresses
ACCRUED_INTEREST_PAYABLE = "ACCRUED_INTEREST_PAYABLE"
ACCRUED_INTEREST_RECEIVABLE = "ACCRUED_INTEREST_RECEIVABLE"

# Parameters
PARAM_DAYS_IN_YEAR = "days_in_year"
PARAM_ACCRUAL_PRECISION = "accrual_precision"
INTEREST_ACCRUAL_PREFIX = "interest_accrual"
PARAM_INTEREST_ACCRUAL_HOUR = f"{INTEREST_ACCRUAL_PREFIX}_hour"
PARAM_INTEREST_ACCRUAL_MINUTE = f"{INTEREST_ACCRUAL_PREFIX}_minute"
PARAM_INTEREST_ACCRUAL_SECOND = f"{INTEREST_ACCRUAL_PREFIX}_second"
PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT = "accrued_interest_payable_account"
PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "accrued_interest_receivable_account"

days_in_year_param = Parameter(
    name=PARAM_DAYS_IN_YEAR,
    shape=UnionShape(
        items=[
            UnionItem(key="actual", display_name="Actual"),
            UnionItem(key="366", display_name="366"),
            UnionItem(key="365", display_name="365"),
            UnionItem(key="360", display_name="360"),
        ]
    ),
    level=ParameterLevel.TEMPLATE,
    description="The days in the year for interest accrual calculation."
    ' Valid values are "actual", "366", "365", "360"',
    display_name="Interest Accrual Days In Year",
    default_value=UnionItemValue(key="365"),
)
accrual_precision_param = Parameter(
    name=PARAM_ACCRUAL_PRECISION,
    level=ParameterLevel.TEMPLATE,
    description="Precision needed for interest accruals.",
    display_name="Interest Accrual Precision",
    shape=NumberShape(min_value=0, max_value=15, step=1),
    default_value=Decimal(5),
)

accrual_parameters = [days_in_year_param, accrual_precision_param]

schedule_parameters = [
    # Template parameters
    Parameter(
        name=PARAM_INTEREST_ACCRUAL_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which interest is accrued.",
        display_name="Interest Accrual Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=Decimal("0"),
    ),
    Parameter(
        name=PARAM_INTEREST_ACCRUAL_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which interest is accrued.",
        display_name="Interest Accrual Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=Decimal("0"),
    ),
    Parameter(
        name=PARAM_INTEREST_ACCRUAL_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which interest is accrued.",
        display_name="Interest Accrual Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=Decimal("0"),
    ),
]

accrued_interest_payable_account_param = Parameter(
    name=PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for accrued interest payable balance.",
    display_name="Accrued Interest Payable Account",
    shape=AccountIdShape(),
    default_value=ACCRUED_INTEREST_PAYABLE,
)
accrued_interest_receivable_account_param = Parameter(
    name=PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for accrued interest receivable balance.",
    display_name="Accrued Interest Receivable Account",
    shape=AccountIdShape(),
    default_value=ACCRUED_INTEREST_RECEIVABLE,
)


def event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=ACCRUAL_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{ACCRUAL_EVENT}_AST"],
        )
    ]


def scheduled_events(
    vault: SmartContractVault,
    start_datetime: datetime,
    skip: Optional[Union[bool, ScheduleSkip]] = None,
) -> dict[str, ScheduledEvent]:
    skip = skip or False
    return {
        ACCRUAL_EVENT: utils.daily_scheduled_event(
            vault=vault,
            start_datetime=start_datetime,
            parameter_prefix=INTEREST_ACCRUAL_PREFIX,
            skip=skip,
        )
    }


def update_schedule_events_skip(
    skip: Union[bool, ScheduleSkip]
) -> list[UpdateAccountEventTypeDirective]:
    return [
        UpdateAccountEventTypeDirective(
            event_type=ACCRUAL_EVENT,
            skip=skip,
        )
    ]


def daily_accrual(
    customer_account: str,
    customer_address: str,
    denomination: str,
    internal_account: str,
    payable: bool,
    effective_balance: Decimal,
    effective_datetime: datetime,
    yearly_rate: Decimal,
    days_in_year: str,
    precision: int,
    rounding: str,
    account_type: str,
    event_type: str = ACCRUAL_EVENT,
) -> list[CustomInstruction]:
    """
    Calculates daily accrual amount and returns a CustomInstruction with the relevant customer and
    internal account postings. Note: if an income/expense account is used for the internal account
    and the customer address is set accordingly, this function can be used to apply a charge on a
    cash basis
    :param customer_account: the customer account id to use
    :param customer_address: the address to use on the customer account
    :param denomination: the denomination of the accrual
    :param internal_account: the internal account id to use. The default address is always
    used on this account
    :param payable: set to True if accruing a payable charge, or False for a receivable charge
    :param effective_balance: the balance to accrue on
    :param effective_datetime: the datetime to accrue as of. This may impact the actual rate
    depending on the `days_in_year` value
    :param yearly_rate: the yearly rate to use, which will be converted to a daily rate
    :param days_in_year: the number of days in the year to assume for the calculation. One of `360`,
    `365`, `366` or `actual`. If actual is used, the number of days is based on effective_date's
    year.
    :param precision: the number of decimal places to round to
    :param rounding: the type of rounding to use, as per decimal's supported options
    :param account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :param event_type: event type name that resulted in the instruction the eg "ACCRUE_INTEREST"
    :return: Custom instructions to accrue interest, if required
    """

    accrual_detail = calculate_daily_accrual(
        effective_balance=effective_balance,
        effective_datetime=effective_datetime,
        yearly_rate=yearly_rate,
        days_in_year=days_in_year,
        rounding=rounding,
        precision=precision,
    )
    if accrual_detail is None:
        return []

    return accruals.accrual_custom_instruction(
        customer_account=customer_account,
        customer_address=customer_address,
        denomination=denomination,
        amount=accrual_detail.amount,
        internal_account=internal_account,
        payable=payable,
        instruction_details=utils.standard_instruction_details(
            description=accrual_detail.description,
            event_type=event_type,
            gl_impacted=True,
            account_type=account_type,
        ),
    )


def calculate_daily_accrual(
    effective_balance: Decimal,
    effective_datetime: datetime,
    yearly_rate: Decimal,
    days_in_year: str,
    rounding: str = ROUND_HALF_UP,
    precision: int = 5,
) -> Optional[accruals.AccrualDetail]:
    """
    Calculate the amount to accrue on a daily basis
    :param effective_balance: the balance to accrue on
    :param effective_datetime: accruals are calculated as of this datetime, which may impact the
    actual rate depending on the `days_in_year` value
    :param yearly_rate: the yearly rate to use, which will be converted to a daily rate
    :param days_in_year: the number of days in the year to assume for the calculation. One of `360`,
    `365`, `366` or `actual`. If actual is used, the number of days is based on effective_date's
    year.
    :param rounding: the type of rounding to use, as per decimal's supported options
    :param precision: the number of decimal places to round to
    :return: the daily accrual details, which may be None if no accruals are needed
    """

    if effective_balance == Decimal("0"):
        return None

    daily_rate = utils.yearly_to_daily_rate(
        days_in_year=days_in_year,
        yearly_rate=yearly_rate,
        effective_date=effective_datetime,
    )

    accrual_amount = utils.round_decimal(
        amount=effective_balance * daily_rate,
        decimal_places=precision,
        rounding=rounding,
    )

    if accrual_amount == 0:
        return None

    return accruals.AccrualDetail(
        amount=accrual_amount,
        description=f"Daily interest accrued at {(daily_rate * 100):0.5f}%"
        f" on balance of {effective_balance:0.2f}",
    )


def get_days_in_year_parameter(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    return str(
        utils.get_parameter(
            vault=vault,
            name=PARAM_DAYS_IN_YEAR,
            at_datetime=effective_datetime,
            is_union=True,
        )
    )


def get_accrual_precision_parameter(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils.get_parameter(
            vault=vault,
            name=PARAM_ACCRUAL_PRECISION,
            at_datetime=effective_datetime,
        )
    )


def get_accrued_interest_payable_account_parameter(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    return str(
        utils.get_parameter(
            vault,
            name=PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            at_datetime=effective_datetime,
        )
    )


def get_accrued_interest_receivable_account_parameter(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    return str(
        utils.get_parameter(
            vault,
            name=PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            at_datetime=effective_datetime,
        )
    )
