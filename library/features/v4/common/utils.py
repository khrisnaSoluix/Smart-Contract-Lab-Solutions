# CBF: Supported Denominations
# CBF: Permitted Primary Denomination

"""
Provides commonly used Contracts API v4 helper methods for use with smart contracts
"""
# standard libs
from calendar import isleap
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import ROUND_HALF_UP, Decimal
from json import loads
from typing import Any, Iterable, Mapping, Optional, Union
from zoneinfo import ZoneInfo

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AuthorisationAdjustment,
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    BalanceTimeseries,
    CalendarEvents,
    CustomInstruction,
    EndOfMonthSchedule,
    FlagTimeseries,
    InboundAuthorisation,
    InboundHardSettlement,
    OptionalValue,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Phase,
    Posting,
    PostingInstructionType,
    Rejection,
    RejectionReason,
    Release,
    ScheduledEvent,
    ScheduleExpression,
    ScheduleFailover,
    ScheduleSkip,
    Settlement,
    Transfer,
    Tside,
    UnionItemValue,
    UpdateAccountEventTypeDirective,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PostingInstructionTypeAlias = Union[
    AuthorisationAdjustment,
    CustomInstruction,
    InboundAuthorisation,
    InboundHardSettlement,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Release,
    Settlement,
    Transfer,
]

PostingInstructionListAlias = list[
    Union[
        AuthorisationAdjustment,
        CustomInstruction,
        InboundAuthorisation,
        InboundHardSettlement,
        OutboundAuthorisation,
        OutboundHardSettlement,
        Release,
        Settlement,
        Transfer,
    ]
]

PostingsTypeAlias = Union[
    AuthorisationAdjustment,
    InboundAuthorisation,
    InboundHardSettlement,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Posting,
    Release,
    Settlement,
    Transfer,
]

ParameterValueTypeAlias = Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]


# yearly_to_daily_rate
VALID_DAYS_IN_YEAR = ["360", "365", "366", "actual"]
DEFAULT_DAYS_IN_YEAR = "actual"
# Frequency
MONTHLY = "monthly"
QUARTERLY = "quarterly"
ANNUALLY = "annually"
FREQUENCY_MAP = {
    "days": {"weekly": 7, "every_two_weeks": 14, "every_four_weeks": 28},
    "months": {"monthly": 1, "quarterly": 3, "every_two_quarters": 6, "annually": 12},
}
RATE_DECIMAL_PLACES = 10
END_OF_TIME = datetime(2099, 1, 1, 0, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
# END_OF_TIME_EXPRESSION is defined below `one_off_schedule_expression` due to function usage


## Miscellaneous helpers
def str_to_bool(string: str) -> bool:
    """
    Convert a string true to bool True, default value of False.
    :param string:
    :return:
    """
    return str(string).lower() == "true"


def round_decimal(
    amount: Decimal,
    decimal_places: int,
    rounding: str = ROUND_HALF_UP,
) -> Decimal:
    """
    Round an amount to specified number of decimal places
    :param amount: Decimal, amount to round
    :param decimal_places: int, number of places to round to
    :param rounding: the type of rounding strategy to use
    :return: Decimal, rounded amount
    """
    return amount.quantize(Decimal((0, (1,), -int(decimal_places))), rounding=rounding)


def yearly_to_daily_rate(
    effective_date: datetime, yearly_rate: Decimal, days_in_year: str = "actual"
) -> Decimal:
    """
    Calculate the number of days in year
    :param effective_date: the date as of which the conversion happens. This may affect the outcome
    based on the `days_in_year` value.
    :param days_in_year: the number of days in the year to assume for the calculation. One of `360`,
    `365`, `366` or `actual`. If actual is used, the number of days is based on effective_date's
    year
    :return: the corresponding number of days in year
    """

    days_in_year = days_in_year if days_in_year in VALID_DAYS_IN_YEAR else DEFAULT_DAYS_IN_YEAR
    if days_in_year == "actual":
        num_days_in_year = Decimal("366") if isleap(effective_date.year) else Decimal("365")
    else:
        num_days_in_year = Decimal(days_in_year)
    return round_decimal(yearly_rate / num_days_in_year, decimal_places=RATE_DECIMAL_PLACES)


def get_days_in_year(
    effective_date: datetime, days_in_year: str = "actual"
) -> Decimal:
    """
    Calculate the daily rate from a yearly rate, for a given `days_in_year` convention and date
    :param effective_date: the date as of which the conversion happens. This may affect the outcome
    based on the `days_in_year` value.
    :param days_in_year: the number of days in the year to assume for the calculation. One of `360`,
    `365`, `366` or `actual`. If actual is used, the number of days is based on effective_date's
    year
    :return: the corresponding daily rate
    """

    days_in_year = days_in_year if days_in_year in VALID_DAYS_IN_YEAR else DEFAULT_DAYS_IN_YEAR
    if days_in_year == "actual":
        num_days_in_year = Decimal("366") if isleap(effective_date.year) else Decimal("365")
    else:
        num_days_in_year = Decimal(days_in_year)
    return num_days_in_year


def yearly_to_monthly_rate(yearly_rate: Decimal) -> Decimal:
    return round_decimal(yearly_rate / 12, decimal_places=RATE_DECIMAL_PLACES)


def remove_exponent(d: Decimal) -> Decimal:
    """
    Safely remove trailing zeros when dealing with exponents. This is useful when using a decimal
    value in a string used for informational purposes (e.g. instruction_details or logging).
    E.g: remove_exponent(Decimal("5E+3"))
    Returns: Decimal('5000')
    """
    return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()


def rounded_days_between(start_date: datetime, end_date: datetime) -> int:
    """
    Calculates the rounded up number of days between two dates, positive or negative.

    :param start_date: datetime, date from which to start counting days
    :param end_date: datetime, date until which to count
    :return: int, number of days
    """
    delta = relativedelta(end_date, start_date) + start_date - start_date
    one_day = relativedelta(days=1) + start_date - start_date
    days = delta.total_seconds() / one_day.total_seconds()
    rounding = "ROUND_CEILING" if days > 0 else "ROUND_FLOOR"
    return int(Decimal(days).quantize(Decimal("1"), rounding=rounding))


def validate_amount_precision(amount: Decimal, max_precision: int = 2) -> Optional[Rejection]:
    """
    Return a Rejection if the amount has non-zero digits after the specified number of
    decimal places
    :param amount: the amount to check
    :param max_precision: the max integer number of non-zero decimal places
    :return Rejection: when amount has non-zero digits after max_precision decimal places
    """
    if round_decimal(amount, max_precision) != amount:
        return Rejection(
            message=f"Amount {amount} has non-zero digits after {max_precision} decimal places",
            reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
        )

    return None


## Parameter helpers
def get_parameter(
    vault: SmartContractVault,
    name: str,
    at_datetime: Optional[datetime] = None,
    is_json: bool = False,
    is_boolean: bool = False,
    is_union: bool = False,
    is_optional: bool = False,
    default_value: Optional[Any] = None,
) -> Any:
    """
    Get the parameter value for a given parameter
    :param vault:
    :param name: name of the parameter to retrieve
    :param at_datetime: datetime, time at which to retrieve the parameter value. If not
    specified the latest value is retrieved
    :param is_json: if true json_loads is called on the retrieved parameter value
    :param is_boolean: boolean parameters are treated as union parameters before calling
    str_to_bool on the retrieved parameter value
    :param is_union: if True parameter will be treated as a UnionItem
    :param is_optional: if true we treat the parameter as optional
    :param default_value: only used in conjunction with the is_optional arg, the value to use if the
    parameter is not set.
    :return: the parameter value, this is type hinted as Any because the parameter could be
    json loaded, therefore it value can be any json serialisable type and we gain little benefit
    from having an extensive Union list
    """
    if at_datetime:
        parameter = vault.get_parameter_timeseries(name=name).at(at_datetime=at_datetime)
    else:
        parameter = vault.get_parameter_timeseries(name=name).latest()

    if is_union and parameter is not None:
        parameter = parameter.key

    if is_boolean and parameter is not None:
        # since boolean parameters are defined by the UnionShape() parameter shape, the key must be
        # accessed
        # parameter = str_to_bool(parameter.key)
        parameter = str_to_bool(parameter)

    if is_json and parameter is not None:
        parameter = loads(parameter)

    if is_optional:
        parameter = parameter.value if parameter.is_set() else default_value
        
    return parameter


def has_parameter_value_changed(
    parameter_name: str,
    old_parameters: dict[str, ParameterValueTypeAlias],
    updated_parameters: dict[str, ParameterValueTypeAlias],
) -> bool:
    """
    Determines if a parameter has changed. To be used within post-parameter change hook.

    :param parameter_name: str, name of the parameter
    :param old_parameters: dict, map of parameter name -> old parameter value
    :param updated_parameters: dict, map of parameter name -> new parameter value
    :return: bool, True if parameter value has changed, False otherwise
    """

    return (
        parameter_name in updated_parameters
        and old_parameters[parameter_name] != updated_parameters[parameter_name]
    )


def are_optional_parameters_set(vault: SmartContractVault, parameters: list[str]) -> bool:
    """
    Determines whether the list of optional parameter names are set

    :param vault:
    :param parameters: List of vault parameter names

    :return: bool, True if all parameters are set, False otherwise
    """
    return all(
        get_parameter(vault, parameter, is_optional=True) is not None for parameter in parameters
    )


## Schedule helpers
def daily_scheduled_event(
    vault: SmartContractVault,
    start_datetime: datetime,
    parameter_prefix: str,
    skip: Optional[Union[bool, ScheduleSkip]] = None,
) -> ScheduledEvent:
    """
    Creates a daily scheduled event, with support for hour, minute and second parameters whose names
    should be prefixed with `parameter_prefix`
    :param vault: the vault object holding the parameters
    :param start_datetime: when the schedule should start from
    :param parameter_prefix: the prefix for the parameter names
    :param skip: Skip a schedule until a given datetime. If set to True, the schedule will
                 be skipped indefinitely until this field is updated.
    :return: the desired scheduled event
    """
    skip = skip or False
    hour = int(get_parameter(vault, name=f"{parameter_prefix}_hour"))
    minute = int(get_parameter(vault, name=f"{parameter_prefix}_minute"))
    second = int(get_parameter(vault, name=f"{parameter_prefix}_second"))

    return ScheduledEvent(
        start_datetime=start_datetime,
        expression=ScheduleExpression(hour=hour, minute=minute, second=second),
        skip=skip,
    )


def monthly_scheduled_event(
    vault: SmartContractVault,
    start_datetime: datetime,
    parameter_prefix: str,
    failover: ScheduleFailover = ScheduleFailover.FIRST_VALID_DAY_BEFORE,
    day: Optional[int] = None,
) -> ScheduledEvent:
    """
    Creates a monthly scheduled event, with support for day, hour, minute and second parameters
    whose names should be prefixed with `parameter_prefix`.
    :param vault: the vault object holding the parameters
    :param start_datetime: when the schedule should start from (inclusive)
    :param parameter_prefix: the prefix for the parameter names
    :param failover: the desired behaviour if the day does not exist in a given month
    :param day: the desired day of the month to create the schedule
    :return: the desired scheduled event
    """

    account_creation_datetime = vault.get_account_creation_datetime()
    # Schedule DSL expressions (e.g. EndOfMonthSchedule) are exclusive of start_datetime, but
    # inclusive for non DSL.
    start_datetime = start_datetime - relativedelta(seconds=1)
    if start_datetime < account_creation_datetime:
        start_datetime = account_creation_datetime

    return ScheduledEvent(
        start_datetime=start_datetime,
        schedule_method=get_end_of_month_schedule_from_parameters(
            vault=vault, parameter_prefix=parameter_prefix, failover=failover, day=day
        ),
    )


def get_end_of_month_schedule_from_parameters(
    vault: SmartContractVault,
    parameter_prefix: str,
    failover: ScheduleFailover = ScheduleFailover.FIRST_VALID_DAY_BEFORE,
    day: Optional[int] = None,
) -> EndOfMonthSchedule:
    """
    Creates an EndOfMonthSchedule object, extracting the day, hour, minute and second information
    from the parameters whose names are prefixed with `parameter_prefix`
    :param vault: the vault object holding the parameters
    :param parameter_prefix: the prefix for the parameter names
    :param failover: the desired behaviour if the day does not exist in a given month
    :param day: the desired day of the month to create the schedule
    :return: the desired EndOfMonthSchedule
    """
    if day is None:
        day = int(get_parameter(vault, name=f"{parameter_prefix}_day"))
    hour = int(get_parameter(vault, name=f"{parameter_prefix}_hour"))
    minute = int(get_parameter(vault, name=f"{parameter_prefix}_minute"))
    second = int(get_parameter(vault, name=f"{parameter_prefix}_second"))

    return EndOfMonthSchedule(
        day=day,
        hour=hour,
        minute=minute,
        second=second,
        failover=failover,
    )


def one_off_schedule_expression(schedule_datetime: datetime) -> ScheduleExpression:
    """
    Creates a ScheduleExpression representing a schedule from datetime as function input

    :param schedule_datetime: datetime of one of schedule
    :return: ScheduleExpression
    """
    return ScheduleExpression(
        year=str(schedule_datetime.year),
        month=str(schedule_datetime.month),
        day=str(schedule_datetime.day),
        hour=str(schedule_datetime.hour),
        minute=str(schedule_datetime.minute),
        second=str(schedule_datetime.second),
    )


END_OF_TIME_EXPRESSION = one_off_schedule_expression(END_OF_TIME)
END_OF_TIME_SCHEDULED_EVENT = ScheduledEvent(
    end_datetime=END_OF_TIME - relativedelta(seconds=1),
    expression=END_OF_TIME_EXPRESSION,
)


def get_schedule_time_from_parameters(
    vault: SmartContractVault, parameter_prefix: str
) -> tuple[int, int, int]:
    hour = int(get_parameter(vault=vault, name=f"{parameter_prefix}_hour"))
    minute = int(get_parameter(vault=vault, name=f"{parameter_prefix}_minute"))
    second = int(get_parameter(vault=vault, name=f"{parameter_prefix}_second"))
    return hour, minute, second


def get_schedule_expression_from_parameters(
    vault: SmartContractVault,
    parameter_prefix: str,
    *,
    day: Optional[Union[int, str]] = None,
    month: Optional[Union[int, str]] = None,
    year: Optional[Union[int, str]] = None,
    day_of_week: Optional[Union[int, str]] = None,
) -> ScheduleExpression:
    hour, minute, second = get_schedule_time_from_parameters(vault, parameter_prefix)

    return ScheduleExpression(
        hour=str(hour),
        minute=str(minute),
        second=str(second),
        day=None if not day else str(day),
        month=None if not month else str(month),
        year=None if not year else str(year),
        day_of_week=None if not day_of_week else str(day_of_week),
    )


def get_next_schedule_date(
    start_date: datetime, schedule_frequency: str, intended_day: int
) -> datetime:
    """
    Calculate next valid date for schedule based on required frequency and day of month.
    Falls to last valid day of month if intended day is not in calculated month

    :param start_date: datetime, from which schedule frequency is calculated from
    :param schedule_frequency: str, either 'monthly', 'quarterly' or 'annually'
    :param intended_day: int, day of month the scheduled date should fall on
    :return: datetime, next occurrence of schedule
    """
    frequency_map = {MONTHLY: 1, QUARTERLY: 3, ANNUALLY: 12}

    number_of_months = frequency_map[schedule_frequency]

    if schedule_frequency == MONTHLY and start_date + relativedelta(day=intended_day) > start_date:
        return start_date + relativedelta(day=intended_day)
    else:
        return start_date + relativedelta(months=number_of_months, day=intended_day)


def get_previous_schedule_execution_date(
    vault: SmartContractVault, event_type: str, account_start_date: Optional[datetime] = None
) -> Union[datetime, None]:
    """
    Gets the last execution time of an event (if it exists) else returns the start date
    of the account
    :param event_type: a string of the schedule event type
    :param account_start_date: the start date of the account
    :return: the last execution time of a schedule else the account start date
    """

    last_schedule_event_date = vault.get_last_execution_datetime(event_type=event_type)
    return last_schedule_event_date if last_schedule_event_date is not None else account_start_date


def get_next_schedule_date_calendar_aware(
    start_datetime: datetime,
    schedule_frequency: str,
    intended_day: int,
    calendar_events: CalendarEvents,
) -> datetime:
    """
    Calculate next valid date for schedule based on required frequency; day of month; and calendar.
    If the date falls on a calendar RED day, adjust the date to the next non-"calendar event" day.
    :param start_datetime: datetime, date after which the next schedule datetime must be
    :param schedule_frequency: str, either 'monthly', 'quarterly' or 'annually'
    :param intended_day: int, day of month the scheduled date should fall on
    :return: datetime, next occurrence of schedule
    """
    frequency_map = {"monthly": 1, "quarterly": 3, "annually": 12}
    number_of_months = frequency_map[schedule_frequency]

    if (
        schedule_frequency == "monthly"
        and start_datetime + relativedelta(day=intended_day) > start_datetime
    ):
        next_date = start_datetime + relativedelta(day=intended_day)
    else:
        next_date = start_datetime + relativedelta(months=number_of_months, day=intended_day)

    while falls_on_calendar_events(next_date, calendar_events):
        next_date += relativedelta(days=1)
    return next_date


def get_next_datetime_after_calendar_events(
    effective_datetime: datetime,
    calendar_events: CalendarEvents,
) -> datetime:
    """
    Calculate the next datetime after the given calendar events. If the effective
    datetime falls on a calendar day, the datetime will be incremented by one day
    until this condition is met.
    :param effective_datetime: the datetime to be pushed to after calendar events
    :param calendar_events: events that the schedule date should not fall on
    :return: the next non-calendar day
    """
    while falls_on_calendar_events(effective_datetime, calendar_events):
        effective_datetime += relativedelta(days=1)
    return effective_datetime


def falls_on_calendar_events(effective_datetime: datetime, calendar_events: CalendarEvents) -> bool:
    """
    Returns if true if the given date is on or between a calendar event's start and/or end
    timestamp, inclusive.
    """
    return any(
        calendar_event.start_datetime <= effective_datetime <= calendar_event.end_datetime
        for calendar_event in calendar_events
    )


## Denomination helpers
def validate_denomination(
    posting_instructions: list[PostingInstructionTypeAlias],
    accepted_denominations: Iterable[str],
) -> Optional[Rejection]:
    """
    Return a Rejection if any postings do not match accepted denominations.
    """
    return_rejection = False
    denomination=""
    accepted_denominations_set = set(accepted_denominations)
    for posting_instruction in posting_instructions:
        if posting_instruction.type == PostingInstructionType.CUSTOM_INSTRUCTION:
            # mypy won't recognise that .type actually determines the class of the instruction
            # and we can't use type() or isinstance() in contracts
            for posting in posting_instruction.postings:  # type: ignore
                if posting.denomination not in accepted_denominations_set:
                    return_rejection = True
                    denomination=posting.denomination
                    break
        else:
            if posting_instruction.denomination not in accepted_denominations_set:  # type: ignore
                return_rejection = True
                denomination=posting_instruction.denomination
                break

    if return_rejection:
        return Rejection(
            message=
                f"Postings received in unauthorised denomination {denomination}."
                f" Authorised denomination is {accepted_denominations}",
            reason_code=RejectionReason.WRONG_DENOMINATION,
        )
    return None


## Posting helpers
def create_postings(
    amount: Decimal,
    debit_account: str,
    credit_account: str,
    debit_address: str = DEFAULT_ADDRESS,
    credit_address: str = DEFAULT_ADDRESS,
    denomination: str = "GBP",
    asset: str = DEFAULT_ASSET,
) -> list[Posting]:
    """
    Creates a pair of postings to debit the debit_address on debit_account
    and credit the credit_address on credit_account by the specified amount

    :param amount: The amount to pay. If the amount is <= 0, an empty list is returned
    :param debit_account: The account from which to debit the amount
    :param credit_account: The account to which to credit the amount
    :param debit_address: The address from which to move the amount
    :param credit_address: The address to which to move the amount
    :param denomination: The denomination of the postings
    :param asset: The asset of the postings
    :return: The credit-debit pair of postings
    """
    if amount <= Decimal("0"):
        return []
    return [
        Posting(
            credit=True,
            amount=amount,
            denomination=denomination,
            account_id=credit_account,
            account_address=credit_address,
            asset=asset,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=False,
            amount=amount,
            denomination=denomination,
            account_id=debit_account,
            account_address=debit_address,
            asset=asset,
            phase=Phase.COMMITTED,
        ),
    ]


def reset_tracker_balances(
    balances: BalanceDefaultDict,
    account_id: str,
    tracker_addresses: list[str],
    contra_address: str,
    denomination: str,
    tside: Tside,
) -> list[Posting]:
    """
    Resets the balance of the tracking addresses on an account back to zero. It is assumed the
    tracking addresses will always have a balance >= 0 and that the contra_address has been used
    for double entry bookkeeping purposes for all of the addresses in the tracker_addresses list.

    :param balances: balances of the account to be reset
    :param account_id: id of the customer account
    :param tracker_addresses: list of addresses to be cleared (balance assumed >= 0)
    :param contra_address: address that has been used for double entry bookkeeping purposes when
    originally updating the tracker address balances
    :param denomination: denomination of the account
    :param tside: Tside of the account, this is used to determine whether the tracker address is
    debited or credited since the tracker address is always assumed to have a balance >0
    """
    postings: list[Posting] = []
    for address in tracker_addresses:
        address_balance = balance_at_coordinates(
            balances=balances, address=address, denomination=denomination
        )
        if address_balance > Decimal("0"):
            postings += create_postings(
                amount=address_balance,
                debit_account=account_id,
                credit_account=account_id,
                debit_address=contra_address if tside == Tside.ASSET else address,
                credit_address=address if tside == Tside.ASSET else contra_address,
                denomination=denomination,
            )

    return postings


def validate_single_hard_settlement_or_transfer(
    posting_instructions: PostingInstructionListAlias,
) -> Optional[Rejection]:
    """
    Return a Rejection if the posting instructions being processed has more than one instruction
    or if the posting instruction type is not a hard settlement or transfer
    """
    accepted_posting_types = [
        PostingInstructionType.INBOUND_HARD_SETTLEMENT,
        PostingInstructionType.OUTBOUND_HARD_SETTLEMENT,
        PostingInstructionType.TRANSFER,
    ]
    # Check posting instruction is valid
    if len(posting_instructions) != 1 or posting_instructions[0].type not in accepted_posting_types:
        return Rejection(
            message="Only batches with a single hard settlement or transfer posting are supported",
            reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
        )

    return None


def is_key_in_instruction_details(
    *, key: str, posting_instructions: PostingInstructionListAlias
) -> bool:
    return all(
        str_to_bool(posting_instruction.instruction_details.get(key, "false"))
        for posting_instruction in posting_instructions
    )


def is_force_override(posting_instructions: PostingInstructionListAlias) -> bool:
    return is_key_in_instruction_details(
        key="force_override", posting_instructions=posting_instructions
    )


def is_withdrawal_override(posting_instructions: PostingInstructionListAlias) -> bool:
    return is_key_in_instruction_details(
        key="withdrawal_override", posting_instructions=posting_instructions
    )


def standard_instruction_details(
    description: str,
    event_type: str,
    gl_impacted: bool = False,
    account_type: str = "",
) -> dict[str, str]:
    """
    Generates standard posting instruction details
    :param description: a description of the instruction, usually for human consumption
    :param event_type: event type name that resulted in the instruction the eg "ACCRUE_INTEREST"
    :param gl_impacted: indicates if this posting instruction has GL implications
    :param account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :return: the instruction details
    """

    return {
        "description": description,
        "event": event_type,
        "gl_impacted": str(gl_impacted),
        "account_type": account_type,
    }


def get_transaction_type(
    instruction_details: dict[str, str],
    txn_code_to_type_map: dict[str, str],
    default_txn_type: str,
) -> str:
    # TODO(sas): consider refactoring to take actual PI rather than details
    """
    Gets the transaction type from Posting instruction metadata.
    :param instruction_details: mapping containing instruction-level metadata for the Posting
    :param txn_code_to_type_map: map of transaction code to transaction type
    :param default_txn_type: transaction type to default to if code not found in the map
    :return: the transaction type of the Posting instruction
    """
    txn_code = instruction_details.get("transaction_code", "None")
    return txn_code_to_type_map.get(txn_code, default_txn_type)


## Flag helpers
def is_flag_in_list_applied(
    *,
    vault: SmartContractVault,
    parameter_name: str,
    effective_datetime: Optional[datetime] = None,
) -> bool:
    """
    Determine if a flag in the list provided is set and active

    :param vault:
    :param parameter_name: str, name of the parameter to retrieve
    :param effective_datetime: datetime at which to retrieve the flag timeseries value. If not
    specified the latest value is retrieved
    :return: bool, True if any of the flags in the list are applied at the given datetime
    """
    flag_names: list[str] = get_parameter(vault, name=parameter_name, is_json=True)

    return any(
        vault.get_flag_timeseries(flag=flag_name).at(at_datetime=effective_datetime)
        if effective_datetime
        else vault.get_flag_timeseries(flag=flag_name).latest()
        for flag_name in flag_names
    )


def is_flag_in_timeseries_applied(
    *,
    flag_timeseries_iterable: Iterable[FlagTimeseries],
    effective_datetime: Optional[datetime] = None,
) -> bool:
    """
    Determine if a flag is set and active

    :param flag_timeseries: iterable containing the FlagTimeseries objects for each flag, for use
    in the validation
    :param effective_datetime: datetime at which to retrieve the flag timeseries value. If not
    specified the latest value is retrieved
    :return: bool, True if any of the flags in the parameterised list are applied at the
    timestamp
    """
    return any(
        flag_timeseries_.at(at_datetime=effective_datetime)
        if effective_datetime
        else flag_timeseries_.latest()
        # flag_timeseries could still be None if wrong combination of params are passed in
        for flag_timeseries_ in flag_timeseries_iterable or []
    )


def get_flag_timeseries_list_for_parameter(
    vault: SmartContractVault,
    parameter_name: str,
) -> list[FlagTimeseries]:
    """
    Get the flag timeseries for each flag in the list provided

    :param vault: the Vault object
    :param parameter_name: name of the parameter that contains the list of flags stored in
    JSON format
    :return: a list of FlagTimeseries objects
    """
    return [
        vault.get_flag_timeseries(flag=flag_definition_id)
        for flag_definition_id in get_parameter(vault, name=parameter_name, is_json=True)
    ]


## Balance helpers
def sum_balances(
    *,
    balances: BalanceDefaultDict,
    addresses: list[str],
    denomination: str,
    asset: str = DEFAULT_ASSET,
    phase: Phase = Phase.COMMITTED,
    decimal_places: Optional[int] = None,
) -> Decimal:
    balance_sum = Decimal(
        sum(
            balances[BalanceCoordinate(address, asset, denomination, phase)].net
            for address in addresses
        )
    )

    return (
        balance_sum
        if decimal_places is None
        else round_decimal(amount=balance_sum, decimal_places=decimal_places)
    )


def balance_at_coordinates(
    *,
    balances: BalanceDefaultDict,
    address: str = DEFAULT_ADDRESS,
    denomination: str,
    asset: str = DEFAULT_ASSET,
    phase: Phase = Phase.COMMITTED,
    decimal_places: Optional[int] = None,
) -> Decimal:
    balance_net = balances[BalanceCoordinate(address, asset, denomination, phase)].net
    return (
        balance_net
        if decimal_places is None
        else round_decimal(amount=balance_net, decimal_places=decimal_places)
    )


def get_available_balance(
    *,
    balances: BalanceDefaultDict,
    denomination: str,
    address: str = DEFAULT_ADDRESS,
    asset: str = DEFAULT_ASSET,
) -> Decimal:
    """
    Returns the sum of net balances including COMMITTED and PENDING_OUT only.

    The function serves two different purposes, depending on the type of balances provided:
    1. When account balances (absolute balances) are used, it returns the available balance
    of the account
    2. When posting balances (relative balances) are used, it calculates the impact of the
    posting on the available balance of the account, providing insights into how the posting
    will affect the account balance

    :param balances: BalanceDefaultDict, account balances or posting balances
    :param denomination: balance denomination
    :param address: balance address
    :param asset: balance asset
    :return: sum of committed and pending out balance coordinates
    """
    committed_coordinate = BalanceCoordinate(
        account_address=address, asset=asset, denomination=denomination, phase=Phase.COMMITTED
    )
    pending_out_coordinate = BalanceCoordinate(
        account_address=address, asset=asset, denomination=denomination, phase=Phase.PENDING_OUT
    )
    return balances[committed_coordinate].net + balances[pending_out_coordinate].net


def get_latest_available_balance_from_mapping(
    mapping: Mapping[BalanceCoordinate, BalanceTimeseries],
    denomination: str,
    address: str = DEFAULT_ADDRESS,
    asset: str = DEFAULT_ASSET,
) -> Decimal:
    """
    Returns the sum of net balances including COMMITTED and PENDING_OUT only.
    The latest value in the Balance Timeseries is used.
    The balances mapping is fetched from `vault.get_balances_timeseries()`

    :param mapping: map of balance coordinates to balance timeseries
    :param denomination: balance denomination
    :param address: balance address
    :param asset: balance asset
    :return: sum of committed and pending out balance coordinates
    """
    committed_coordinate = BalanceCoordinate(
        account_address=address, asset=asset, denomination=denomination, phase=Phase.COMMITTED
    )
    committed_balance: Balance = mapping[committed_coordinate].latest()

    pending_out_coordinate = BalanceCoordinate(
        account_address=address, asset=asset, denomination=denomination, phase=Phase.PENDING_OUT
    )
    pending_out_balance: Balance = mapping[pending_out_coordinate].latest()

    return committed_balance.net + pending_out_balance.net


def get_current_net_balance(
    *,
    balances: BalanceDefaultDict,
    denomination: str,
    address: str = DEFAULT_ADDRESS,
    asset: str = DEFAULT_ASSET,
) -> Decimal:
    """
    Returns the sum of net balances for COMMITTED and PENDING_IN only.
    Used for depositing scenarios.

    :param balances: BalanceDefaultDict for an account
    :param denomination: balance denomination
    :param address: balance address
    :param asset: balance asset
    :return: sum of net attribute of committed and pending_in balance coordinates
    """
    committed_coordinate, pending_in_coordinate = _get_current_balance_coordinates(
        denomination=denomination, address=address, asset=asset
    )
    return balances[committed_coordinate].net + balances[pending_in_coordinate].net


def get_current_credit_balance(
    *,
    balances: BalanceDefaultDict,
    denomination: str,
    address: str = DEFAULT_ADDRESS,
    asset: str = DEFAULT_ASSET,
) -> Decimal:
    """
    Returns the sum of credit balances for COMMITTED and PENDING_IN only.

    :param balances: BalanceDefaultDict for an account
    :param denomination: balance denomination
    :param address: balance address
    :param asset: balance asset
    :return: sum of credit attribute of committed and pending_in balance coordinates
    """
    committed_coordinate, pending_in_coordinate = _get_current_balance_coordinates(
        denomination=denomination, address=address, asset=asset
    )
    return balances[committed_coordinate].credit + balances[pending_in_coordinate].credit


def get_current_debit_balance(
    *,
    balances: BalanceDefaultDict,
    denomination: str,
    address: str = DEFAULT_ADDRESS,
    asset: str = DEFAULT_ASSET,
) -> Decimal:
    """
    Returns the sum of debit balances for COMMITTED and PENDING_OUT only.

    :param balances: BalanceDefaultDict for an account
    :param denomination: balance denomination
    :param address: balance address
    :param asset: balance asset
    :return: sum of debit attribute of committed and pending_out balance coordinates
    """
    committed_coordinate = BalanceCoordinate(
        account_address=address, asset=asset, denomination=denomination, phase=Phase.COMMITTED
    )
    pending_out_coordinate = BalanceCoordinate(
        account_address=address, asset=asset, denomination=denomination, phase=Phase.PENDING_OUT
    )
    return balances[committed_coordinate].debit + balances[pending_out_coordinate].debit


def _get_current_balance_coordinates(
    *,
    denomination: str,
    address: str,
    asset: str,
) -> tuple[BalanceCoordinate, BalanceCoordinate]:
    """
    Returns the COMMITTED and PENDING_IN balance coordinates .

    :param denomination: balance denomination
    :param address: balance address
    :param asset: balance asset
    :return: the committed and pending balance coordinates
    """
    committed_coordinate = BalanceCoordinate(
        account_address=address, asset=asset, denomination=denomination, phase=Phase.COMMITTED
    )
    pending_in_coordinate = BalanceCoordinate(
        account_address=address, asset=asset, denomination=denomination, phase=Phase.PENDING_IN
    )
    return committed_coordinate, pending_in_coordinate


def get_balance_default_dict_from_mapping(
    mapping: Mapping[BalanceCoordinate, BalanceTimeseries],
    effective_datetime: Optional[datetime] = None,
) -> BalanceDefaultDict:
    """
    Converts the balances mapping fetched from `vault.get_balances_timeseries()` into a
    BalanceDefaultDict, taking either the latest or at_datetime entry of the timeseries

    :param mapping: map of balance coordinates to balance timeseries
    :param effective_datetime: if provided, the timeseries value at that timestamp will be used,
    otherwise the latest value will be used
    :return: BalanceDefaultDict from the timeseries mapping
    """
    balance_mapping: dict[BalanceCoordinate, Balance] = {
        coord: (ts.at(at_datetime=effective_datetime) if effective_datetime else ts.latest())
        for coord, ts in mapping.items()
    }
    return BalanceDefaultDict(mapping=balance_mapping)


def average_balance(
    *,
    balances: list[Decimal],
) -> Decimal:
    """
    Calculate the average balance
    :param balances: List of the values of balances to calculate the average balance
    :return: Decimal average balance calculated
    """
    if balances:
        return Decimal(sum(balances) / len(balances))
    return Decimal(0)


def get_posting_instructions_balances(
    *, posting_instructions: PostingInstructionListAlias
) -> BalanceDefaultDict:
    """
    Gets the combined balances for a list of posting instructions.
    Can only be used on fetched or hook argument posting instructions as the balances
    method is called without arguments. Contract generated posting instructions will not
    have the required output attributes (_tside and _own_account_id) defined and thus
    have to be provided as arguments to the balances method

    :param posting_instructions: list of posting instructions
    :return: BalanceDefaultDict populated with the balances from the provided posting instructions
    """

    posting_balances = BalanceDefaultDict()
    for posting_instruction in posting_instructions:
        posting_balances += posting_instruction.balances()
    return posting_balances


def update_inflight_balances(
    account_id: str,
    tside: Tside,
    current_balances: BalanceDefaultDict,
    posting_instructions: PostingInstructionListAlias,
) -> BalanceDefaultDict:
    """
    Returns a new BalanceDefaultDict, merging the current balances with the posting balances

    :param account_id: id of the vault account, required for the .balances() method
    :param tside: tside of the account, required for the .balances() method
    :param current_balances: the current balances to be merged with the posting balances
    :param posting_instructions: list of posting instruction objects to get the balances of to
    merge with the current balances
    :return: A new BalanceDefaultDict with the merged balances
    """
    # A new BalanceDefaultDict object is created to avoid mutating the current balances
    inflight_balances = BalanceDefaultDict(mapping=current_balances)
    for posting_instruction in posting_instructions:
        inflight_balances += posting_instruction.balances(account_id=account_id, tside=tside)

    return inflight_balances


def create_end_of_time_schedule(start_datetime: datetime) -> ScheduledEvent:
    """
    Sets up a dummy schedule with the End of Time expression, that will never produce any
    jobs and is skipped indefinitely.

    :param start_time: the start time of the schedule. This should be linked to the
    account opening datetime
    :return: returns a dummy scheduled event
    """
    return ScheduledEvent(
        start_datetime=start_datetime,
        skip=True,
        expression=END_OF_TIME_EXPRESSION,
    )


def update_completed_schedules(
    scheduled_events: dict[str, ScheduledEvent],
    effective_datetime: datetime,
    potentially_completed_schedules: list[str],
) -> dict[str, ScheduledEvent]:
    """
    To be used in conversion to redefine completed schedules with an end of time expression.
    If the schedule has an end_datetime set which is in the past, the schedule must be completed.
    See `documentation/implementation/hooks.md` for more information.

    :param scheduled_events: list of existing scheduled events from the ConversionHookArguments
    :param effective_datetime: effective_datetime of the conversion hook
    :param potentially_completed_schedules: list of scheduled event names which could
    potentially be completed at the point of conversion
    :return: updated scheduled events mapping
    """
    for schedule_name in potentially_completed_schedules:
        existing_event_scheduled_event = scheduled_events[schedule_name]

        if (
            existing_event_scheduled_event.end_datetime is not None
            and existing_event_scheduled_event.end_datetime < effective_datetime
        ):
            scheduled_events[schedule_name] = END_OF_TIME_SCHEDULED_EVENT

    return scheduled_events


def update_schedules_to_skip_indefinitely(
    schedules: list[str],
) -> list[UpdateAccountEventTypeDirective]:
    """
    Update schedules to skip indefinitely, by pushing to end of time
    and skipping the final execution, thus preventing the schedule
    from running again. Ideally we would set the end_datetime to before
    the end-of-time expression, but the simulator fails to update schedules
    when the next runtime is after end_datetime
    :param scheduled_events: list of scheduled events to update
    :return: list of update account event directives for given schedules
    """
    updated_events: list[UpdateAccountEventTypeDirective] = []
    for schedule_name in schedules:
        updated_events.append(
            UpdateAccountEventTypeDirective(
                event_type=schedule_name,
                expression=END_OF_TIME_EXPRESSION,
                end_datetime=END_OF_TIME,
                skip=True,
            )
        )

    return updated_events
