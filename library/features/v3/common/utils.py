# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
"""
Provides commonly used Contracts API v3 helper methods for use with smart contracts
"""

# standard libs
import calendar
from datetime import datetime
from dateutil.relativedelta import relativedelta as timedelta
from decimal import Decimal
from json import loads as json_loads
from typing import Any, Callable, Iterable, NamedTuple, Optional, Union

# features
import library.features.common.utils_common as utils_common

# inception sdk
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    BalanceDefaultDict,
    CalendarEvents,
    EventTypeSchedule,
    FlagTimeseries,
    InvalidContractParameter,
    NumberKind,
    NumberShape,
    Parameter,
    Phase,
    PostingInstruction,
    PostingInstructionBatch,
    PostingInstructionType,
    Rejected,
    RejectedReason,
    UnionItem,
    UnionShape,
    Vault,
)

round_decimal = utils_common.round_decimal
str_to_bool = utils_common.str_to_bool
get_transaction_type = utils_common.get_transaction_type
yearly_to_monthly_rate = utils_common.yearly_to_monthly_rate
remove_exponent = utils_common.remove_exponent
DEFAULT_DAYS_IN_YEAR = utils_common.DEFAULT_DAYS_IN_YEAR
VALID_DAYS_IN_YEAR = utils_common.VALID_DAYS_IN_YEAR

FREQUENCY_TO_MONTHS_MAP = {"monthly": 1, "quarterly": 3, "annually": 12}
DEFAULT_FREQUENCY = "monthly"

# common parameter defs
FlagShape = UnionShape(
    UnionItem(key="true", display_name="True"), UnionItem(key="false", display_name="False")
)
MoneyShape = NumberShape(kind=NumberKind.MONEY, min_value=0, max_value=10000, step=0.01)
LimitShape = NumberShape(kind=NumberKind.MONEY, min_value=0, step=1)
PositiveRateShape = NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.0001)
LimitHundredthsShape = NumberShape(
    kind=NumberKind.MONEY,
    min_value=0,
    step=0.01,
)

EventTuple = NamedTuple(
    "EventTuple",
    [
        ("event_type", str),
        ("schedule", dict[str, str]),
    ],
)

ScheduleDetails = NamedTuple(
    "ScheduleDetails",
    [
        ("hour", int),
        ("minute", int),
        ("second", int),
        ("day", Optional[int]),
        ("month", Optional[int]),
        ("year", Optional[int]),
        ("last_execution_time", Optional[datetime]),
    ],
)


def yearly_to_daily_rate(yearly_rate: Decimal, year: int, days_in_year: str = "actual") -> Decimal:
    """
    Convert yearly rate to daily rate.
    """
    days_in_year = days_in_year if days_in_year in VALID_DAYS_IN_YEAR else DEFAULT_DAYS_IN_YEAR
    if days_in_year == "actual":
        num_days_in_year = Decimal("366") if calendar.isleap(year) else Decimal("365")
    else:
        num_days_in_year = Decimal(days_in_year)

    return yearly_rate / num_days_in_year


def rounded_days_between(start_date: datetime, end_date: datetime) -> int:
    """
    Calculates the rounded up number of days between two dates, positive or negative.

    :param start_date: datetime, date from which to start counting days
    :param end_date: datetime, date until which to count
    :return: int, number of days
    """
    # timedelta is actually dateutil.relativedelta, apply to arbitrary date to get real timedelta
    delta = timedelta(end_date, start_date) + start_date - start_date
    one_day = timedelta(days=1) + start_date - start_date
    days = delta.total_seconds() / one_day.total_seconds()
    rounding = "ROUND_CEILING" if days > 0 else "ROUND_FLOOR"
    return int(Decimal(days).quantize(Decimal("1"), rounding=rounding))


def get_parameter(
    vault: Vault,
    name: str,
    at: Optional[datetime] = None,
    is_json: bool = False,
    is_boolean: bool = False,
    union: bool = False,
    optional: bool = False,
) -> Any:
    """
    Get the parameter value for a given parameter
    :param vault:
    :param name: name of the parameter to retrieve
    :param at: datetime, time at which to retrieve the parameter value. If not
    specified the latest value is retrieved
    :param is_json: if true json_loads is called on the retrieved parameter value
    :param is_boolean: if true str_to_bool is called on the retrieved parameter value
    :param union: if True parameter will be treated as a UnionItem
    :param optional: if true we treat the parameter as optional
    :return:
    """
    if at:
        parameter = vault.get_parameter_timeseries(name=name).at(timestamp=at)
    else:
        parameter = vault.get_parameter_timeseries(name=name).latest()

    if optional:
        parameter = parameter.value if parameter.is_set() else None

    if union and parameter is not None:
        parameter = parameter.key

    if is_boolean and parameter is not None:
        return str_to_bool(parameter)

    if is_json and parameter is not None:
        parameter = json_loads(parameter)

    return parameter


def is_flag_in_list_applied(
    vault: Optional[Vault] = None,
    parameter_name: Optional[str] = None,
    application_timestamp: Optional[datetime] = None,
    flag_timeseries: Optional[Iterable[FlagTimeseries]] = None,
) -> bool:
    """
    Determine if a flag is set and active for a customer from a given list of flag names
    :param vault: vault object used to retrieve parameters and flags. Optional if
    flag_timeseries is used
    :param parameter_name: str, name of the parameter to retrieve, which must be a json
    encoded list of flag definition ids. Optional if flag_timeseries is used
    :param application_timestamp: datetime, optional time at which to check if any flags
    were applied. If not specified latest is used.
    :param flag_timeseries: optional flag timeseries to use if already fetched from a
    vault object (e.g. for use in other functions)
    :return: bool, True if any of the flags in the parameterised list are applied at the
    timestamp
    """
    if flag_timeseries is None and vault is not None and parameter_name:
        # As we use this once in any() a generator is optimal
        flag_timeseries = (
            vault.get_flag_timeseries(flag=flag_definition_id)
            for flag_definition_id in get_parameter(vault, name=parameter_name, is_json=True)
        )

    return any(
        flag_timeseries_.at(timestamp=application_timestamp)
        if application_timestamp
        else flag_timeseries_.latest()
        # flag_timeseries could still be None if wrong combination of params are passed in
        for flag_timeseries_ in flag_timeseries or []
    )


def blocking_flags_applied(
    vault: Vault,
    effective_date: Optional[datetime] = None,
    flag_timeseries: Optional[list[FlagTimeseries]] = None,
    parameter_name: Optional[str] = "",
) -> bool:
    """
    Determine if any flags blocking a behaviour are active for the customer.

    :param vault: vault object used to retrieve parameters and flags. Optional if
    flag_timeseries is used
    :param effective_date: optional time at which to check if any flags were applied.
    If not specified latest is used.
    :param parameter_name: name of the parameter to retrieve, which must be a json
    encoded list of flag definition ids. Optional if flag_timeseries is used
    :param flag_timeseries: optional flag timeseries to use if already fetched from a
    vault object (e.g. for use in other functions)
    :return: True if any of the flags in the parameterised list are applied at the
    timestamp
    """
    return is_flag_in_list_applied(
        vault=vault,
        application_timestamp=effective_date,
        flag_timeseries=flag_timeseries,
        parameter_name=parameter_name,
    )


def get_active_account_flags(vault: Vault, interesting_flag_list: list[str]) -> list[str]:
    """
    Given a list of interesting flags, return the name of any that are active

    :param vault: Vault object
    :param interesting_flag_list: list of flags to check for in flag timeseries
    :return: list of flags from interesting_flag_list that are active
    """
    return [
        flag_name
        for flag_name in interesting_flag_list
        if vault.get_flag_timeseries(flag=flag_name).latest()
    ]


def get_flag_timeseries_list_for_parameter(vault: Vault, parameter: str) -> list[FlagTimeseries]:
    return [
        vault.get_flag_timeseries(flag=flag_definition_id)
        for flag_definition_id in get_parameter(vault, name=parameter, is_json=True)
    ]


def get_daily_schedule(vault: Vault, param_prefix: str, event_type: str) -> EventTuple:
    """
    Creates an EventTuple to represent an event type's daily schedule based on the Vault
    object's parameters.
    :param vault: Vault object
    :param param_prefix: the prefix given to the schedule parameters, which should be named
    - <param_prefix>_hour, <param_prefix>_minute and <param_prefix>_second
    :param event_type: the schedule's event type
    :return: representation of event_type schedule
    """
    creation_date = vault.get_account_creation_date()

    schedule = create_schedule_dict(
        hour=get_parameter(vault, param_prefix + "_hour", at=creation_date),
        minute=get_parameter(vault, param_prefix + "_minute", at=creation_date),
        second=get_parameter(vault, param_prefix + "_second", at=creation_date),
    )

    return EventTuple(event_type, schedule)


def create_daily_schedule_from_datetime(schedule_datetime: datetime) -> dict:
    """
    Creates a daily schedule dictionary based on a provided datetime object.
    """
    return {
        "hour": str(schedule_datetime.hour),
        "minute": str(schedule_datetime.minute),
        "second": str(schedule_datetime.second),
    }


# Note this uses the contract EventTypeSchedule and should not be used with supervisors
# because the supervisor EventTypeSchedule may diverge from the contract one. There is an
# equivalent method to this in supervisor_utils.py
def create_event_type_schedule_from_datetime(
    schedule_datetime: datetime, one_off: bool = True
) -> EventTypeSchedule:
    """
    Creates a contract EventTypeSchedule from a datetime object.

    :param schedule_datetime: datetime, object to be formatted
    :param one_off: if true, the `year` key is included in the dictionary, making this a one-off
    schedule. This is only suitable if the schedule will only be updated before completion, or
    during processing of its own job(s). Otherwise, set to False so that the schedule does not
    complete and can be updated
    :return: EventTypeSchedule representation of datetime
    """
    if one_off:
        return EventTypeSchedule(
            day=str(schedule_datetime.day),
            hour=str(schedule_datetime.hour),
            minute=str(schedule_datetime.minute),
            second=str(schedule_datetime.second),
            month=str(schedule_datetime.month),
            year=str(schedule_datetime.year),
        )
    else:
        return EventTypeSchedule(
            day=str(schedule_datetime.day),
            hour=str(schedule_datetime.hour),
            minute=str(schedule_datetime.minute),
            second=str(schedule_datetime.second),
            month=str(schedule_datetime.month),
        )


def create_event_type_schedule_from_schedule_dict(
    schedule_dict: dict,
) -> EventTypeSchedule:
    """
    Creates a contract EventTypeSchedule from a schedule dictionary.

    :param schedule_datetime: datetime, object to be formatted
    :return: EventTypeSchedule representation of the schedule
    """
    return EventTypeSchedule(
        day=schedule_dict.get("day", None),
        day_of_week=schedule_dict.get("day_of_week", None),
        hour=schedule_dict.get("hour", None),
        minute=schedule_dict.get("minute", None),
        second=schedule_dict.get("second", None),
        month=schedule_dict.get("month", None),
        year=schedule_dict.get("year", None),
    )


def falls_on_calendar_events(
    vault: Vault, localised_effective_date: datetime, calendar_events: CalendarEvents
) -> bool:
    """
    Returns if true if the given date is on or between a calendar event's start and/or end
    timestamp, inclusive.
    """
    for calendar_event in calendar_events:
        localised_event_start = vault.localize_datetime(dt=calendar_event.start_timestamp)
        localised_event_end = vault.localize_datetime(dt=calendar_event.end_timestamp)
        if (localised_event_start <= localised_effective_date) and (
            localised_effective_date <= localised_event_end
        ):
            return True
    return False


def sum_balances(
    vault: Vault,
    addresses: list[str],
    timestamp: Optional[datetime] = None,
    denomination: Optional[str] = None,
    phase: Phase = Phase.COMMITTED,
    fetcher_id: Optional[str] = None,
    is_balance_observation: bool = True,
) -> Decimal:
    """
    Sum balance of an for a phase, denomination and list of given addresses. Can handle balance
    observations, balance intervals and balance timeseries
    :param vault: balances, parameters
    :param addresses: list of addresses
    :param timestamp: optional datetime at which balances to be summed
    :param denomination: the denomination of the balance
    :param phase: phase of the balance
    :param fetcher_id: fetcher id of the optimised balances fetcher, if not passed in then
    non-optimised balance fetching is assumed
    :param is_balance_observation: bool whether balance observation fetcher has been used to obtain
    balances, only used if fetcher_id is passed in
    :return: sum of the balances
    """
    if fetcher_id and is_balance_observation:
        return get_balance_observation_sum(
            vault=vault,
            fetcher_id=fetcher_id,
            addresses=addresses,
            denomination=denomination,
            phase=phase,
        )
    else:
        return get_balance_sum(
            vault=vault,
            addresses=addresses,
            timestamp=timestamp,
            denomination=denomination,
            phase=phase,
            fetcher_id=fetcher_id,
        )


def get_balance_sum(
    vault: Vault,
    addresses: list[str],
    timestamp: Optional[datetime] = None,
    denomination: Optional[str] = None,
    phase: Phase = Phase.COMMITTED,
    fetcher_id: Optional[str] = None,
) -> Decimal:
    """
    Sum balance from a timeseries entry for a phase, denomination and list of given addresses.
    :param vault: balances, parameters
    :param addresses: list of addresses
    :param timestamp: optional datetime at which balances to be summed
    :param denomination: the denomination of the balance
    :param phase: phase of the balance
    :param fetcher_id: fetcher id of the balance interval, only required if using balance interval
    :return: sum of the balances
    """
    balances = (
        vault.get_balance_timeseries(fetcher_id=fetcher_id).latest()
        if timestamp is None
        else vault.get_balance_timeseries(fetcher_id=fetcher_id).at(timestamp=timestamp)
    )
    denom: str = get_parameter(vault, "denomination") if denomination is None else denomination

    return _sum_balances(balances, addresses, denom, phase)


def get_balance_observation_sum(
    vault: Vault,
    fetcher_id: str,
    addresses: list[str],
    denomination: Optional[str] = None,
    phase: Phase = Phase.COMMITTED,
) -> Decimal:
    """
    Sum a balance observation for a phase, denomination and list list of given addresses.
    :param vault: balances observation, parameters
    :param fetcher_id: id of the balance observation fetcher
    :param addresses: list of addresses
    :param denomination: the denomination of the balance
    :param phase: phase of the balance
    :param fetcher_id: fetcher id of the balance observation
    :return: sum of the balances
    """
    balances = vault.get_balances_observation(fetcher_id=fetcher_id).balances
    denom: str = get_parameter(vault, "denomination") if denomination is None else denomination

    return _sum_balances(balances, addresses, denom, phase)


def _sum_balances(
    balances: BalanceDefaultDict,
    addresses: list[str],
    denomination: str,
    phase: Phase = Phase.COMMITTED,
) -> Decimal:

    return Decimal(
        sum(balances[(address, DEFAULT_ASSET, denomination, phase)].net for address in addresses)
    )


def get_available_balance(
    balances: BalanceDefaultDict,
    denomination: str,
    address: str = DEFAULT_ADDRESS,
    asset: str = DEFAULT_ASSET,
) -> Decimal:
    """
    Returns the sum of net balances including COMMITTED and PENDING_OUT only.

    :param balances: balances for an account
    :param denomination: balance denomination
    :param address: balance address
    :param asset: balance asset
    :return: Decimal
    """
    return Decimal(balances[(address, asset, denomination, Phase.COMMITTED)].net) + Decimal(
        balances[(address, asset, denomination, Phase.PENDING_OUT)].net
    )


def get_previous_schedule_execution_date(
    vault: Vault, event_type: str, account_start_date: Optional[datetime] = None
) -> Union[datetime, None]:
    """
    Gets the last execution time of an event (if it exists) else returns the start date
    of the account
    :param event_type: a string of the schedule event type
    :param account_start_date: the start date of the account
    :return: the last execution time of a schedule else the account start date
    """

    last_schedule_event_date = vault.get_last_execution_time(event_type=event_type)
    return last_schedule_event_date if last_schedule_event_date is not None else account_start_date


# Flag helper functions
def get_dict_value_based_on_account_tier_flag(
    active_flags: list[str],
    tiered_param: dict[str, str],
    tier_names: list[str],
    convert: Callable = lambda x: x,
) -> Any:
    """
    Use the account tier flags to get a corresponding value from a
    dictionary keyed by account tier.
    If no recognised flags are present then the last value in tiered_param
    will be used by default.
    If multiple flags are present then uses the one nearest the start of
    tier_names.

    :param active_flags: contains the flags which are active in the account.
    :param tiered_param: dictionary mapping tier names to their corresponding parameter values.
    :param tier_names: names of tiers for this product.
    :param convert: function to convert the resulting value before returning e.g Decimal.
    :raises InvalidContractParameter: when no elements of tier_names are found in tiered_param keys
    :return: Any - as per convert function, value for tiered_param corresponding to account tier.
    """
    # Iterate over the tier_names to preserve tier order
    for tier in tier_names:
        # The last tier is used as the default if no flags match the tiers
        if tier in active_flags or tier == tier_names[-1]:
            # Ensure tier is present in the tiered parameter
            if tier in tiered_param:
                value = tiered_param[tier]
                return convert(value)

    # Should only get here if tiered_param was missing a key for tier_names[-1]
    raise InvalidContractParameter("No valid account tiers have been configured for this product.")


# Schedule helper functions
def get_schedule(
    vault: Vault,
    param_prefix: str,
    event_type: str,
    localised_effective_date: datetime,
    schedule_frequency: str,
    schedule_day_of_month: int,
    calendar_events: CalendarEvents,
) -> EventTuple:

    """
    Get a schedule for monthly/quarterly/annually frequency
    :param vault:
    :param localised_effective_date: the localised date to use to base the calculation on
    :param param_prefix: the prefix given to the schedule parameters, which should be named
    - <param_prefix>_hour, <param_prefix>_minute and <param_prefix>_second
    :param schedule_frequency: the frequency of the schedule. One of `monthly`, `quarterly` or
    `annually`
    :param schedule_day_of_month: the desired day of the month for the schedule to fall on
    :param calendar_events: events that the schedule date should not fall on. The date will be
    increased by a day until this condition is met
    """

    next_schedule_date = get_next_schedule_datetime(
        vault,
        localised_effective_date=localised_effective_date,
        param_prefix=param_prefix,
        schedule_frequency=schedule_frequency,
        schedule_day_of_month=schedule_day_of_month,
        calendar_events=calendar_events,
    )

    return EventTuple(
        event_type,
        create_schedule_dict(
            year=next_schedule_date.year,
            month=next_schedule_date.month,
            day=next_schedule_date.day,
            hour=next_schedule_date.hour,
            minute=next_schedule_date.minute,
            second=next_schedule_date.second,
        ),
    )


def get_next_schedule_datetime(
    vault: Vault,
    localised_effective_date: datetime,
    param_prefix: str,
    schedule_frequency: str,
    schedule_day_of_month: int,
    calendar_events: CalendarEvents,
) -> datetime:
    """
    Gets next date for monthly/quarterly/annually schedules with parameterised time
    :param vault:
    :param localised_effective_date: the localised date to use to base the calculation on
    :param param_prefix: the prefix given to the schedule parameters, which should be named
    - <param_prefix>_hour, <param_prefix>_minute and <param_prefix>_second
    :param schedule_frequency: the frequency of the schedule. One of `monthly`, `quarterly` or
    `annually`
    :param schedule_day_of_month: the desired day of the month for the schedule to fall on
    :param calendar_events: events that the schedule date should not fall on. The date will be
    increased by a day until this condition is met
    """

    next_schedule_date = get_next_schedule_day(
        vault, localised_effective_date, schedule_frequency, schedule_day_of_month, calendar_events
    )

    next_schedule_datetime = next_schedule_date.replace(
        hour=get_parameter(vault, param_prefix + "_hour"),
        minute=get_parameter(vault, param_prefix + "_minute"),
        second=get_parameter(vault, param_prefix + "_second"),
    )

    return next_schedule_datetime


def get_next_schedule_day(
    vault: Vault,
    localised_effective_date: datetime,
    schedule_frequency: str,
    schedule_day_of_month: int,
    calendar_events: CalendarEvents,
) -> datetime:
    """
    Calculate next valid date for schedule based on day of month. Timedelta (relativedelta) falls
    to last valid day of month if intended day is not in calculated month. This method returns the
    day part of the applications schedule, which will then be updated with the time part by the
    get_next_schedule_datetime method.
    :param vault:
    :param localised_effective_date: the localised date to use to base the calculation on
    :param schedule_frequency: the frequency of the schedule. One of `monthly`, `quarterly` or
    `annually`
    :param schedule_day_of_month: the desired day of the month for the schedule to fall on
    :param calendar_events: events that the schedule date should not fall on. The date will be
    increased by a day until this condition is met
    """

    if schedule_frequency not in FREQUENCY_TO_MONTHS_MAP:
        schedule_frequency = DEFAULT_FREQUENCY

    number_of_months = FREQUENCY_TO_MONTHS_MAP[schedule_frequency]
    next_date = localised_effective_date + timedelta(day=schedule_day_of_month)
    if next_date <= localised_effective_date or schedule_frequency != "monthly":
        next_date += timedelta(
            months=number_of_months,
            # the day needs to be added again along with month to swap available & correct day
            # after addition of month
            day=schedule_day_of_month,
        )
    while falls_on_calendar_events(vault, next_date, calendar_events):
        next_date += timedelta(days=1)

    return next_date


def create_schedule_dict_from_datetime(
    schedule_datetime: datetime, one_off: bool = True
) -> dict[str, str]:
    """
    Creates a dict representing a schedule from datetime as function input
    :param schedule_datetime: the datetime to convert to schedule format
    :param one_off: if true, the `year` key is included in the dictionary, making this a one-off
    schedule. This is only suitable if the schedule will only be updated before completion, or
    during processing of its own job(s). Otherwise, set to False so that the schedule does not
    complete and can be updated
    """
    schedule = {
        "month": str(schedule_datetime.month),
        "day": str(schedule_datetime.day),
        "hour": str(schedule_datetime.hour),
        "minute": str(schedule_datetime.minute),
        "second": str(schedule_datetime.second),
    }
    if one_off:
        schedule["year"] = str(schedule_datetime.year)

    return schedule


def create_schedule_dict(
    start_date: Optional[datetime] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    hour: Optional[int] = None,
    minute: Optional[int] = None,
    second: Optional[int] = None,
) -> dict[str, str]:
    """
    Creates a dictionary representing a schedule from datetime parameters.
    :param start_date: starting date for the schedule
    :param year: year for schedule to run
    :param month: month for schedule to run
    :param day: day of month for schedule to run
    :param hour: hour of day for schedule to run
    :param minute: minute of hour for schedule to run
    :param second: second of minute for schedule to run
    :return: representation of schedule
    """
    schedule_dict = {}
    if start_date is not None:
        schedule_dict["start_date"] = start_date.isoformat()
    if year is not None:
        schedule_dict["year"] = str(year)
    if month is not None:
        schedule_dict["month"] = str(month)
    if day is not None:
        schedule_dict["day"] = str(day)
    if hour is not None:
        schedule_dict["hour"] = str(hour)
    if minute is not None:
        schedule_dict["minute"] = str(minute)
    if second is not None:
        schedule_dict["second"] = str(second)
    return schedule_dict


# Parameter helper functions
def has_parameter_value_changed(
    parameter_name: str,
    old_parameters: dict[str, Parameter],
    updated_parameters: dict[str, Parameter],
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


def are_optional_parameters_set(vault: Vault, parameters: list[str]) -> bool:
    """
    Determines whether the list of optional parameter names are set

    :param vault:
    :param parameters: list of vault parameter names

    :return: bool, True if all parameters are set, False otherwise
    """
    return all(
        get_parameter(vault, parameter, optional=True) is not None for parameter in parameters
    )


def instruct_posting_batch(
    vault: Vault,
    posting_instructions: list[PostingInstruction],
    effective_date: datetime,
    event_type: str,
) -> None:
    """
    Instructs posting batch if posting_instructions variable contains any posting instructions.

    :param vault: Vault object
    :param posting_instructions: posting instructions
    :param effective_date: date and time of hook being run
    :param event_type: type of event triggered by the hook
    """
    if posting_instructions:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions,
            effective_date=effective_date,
            client_batch_id=f"{event_type}_{vault.get_hook_execution_id()}",
        )


# Denomination helper functions
def validate_denomination(
    vault: Vault,
    postings: PostingInstructionBatch,
    accepted_denominations: Optional[Iterable[str]] = None,
) -> Union[None, Rejected]:
    """
    Reject if any postings do not match accepted denominations.
    The denomination parameter is added to accepted_denominations.
    If no accepted_denominations are provided, then just the denomination parameter is used.
    """

    accepted_denominations_set = (
        set(accepted_denominations) if accepted_denominations is not None else set()
    )

    accepted_denominations_set.add((get_parameter(vault, "denomination")))

    sorted_accepted_denominations = sorted(accepted_denominations_set)

    if any(post.denomination not in sorted_accepted_denominations for post in postings):
        raise Rejected(
            "Cannot make transactions in the given denomination, transactions must be one of "
            f"{sorted_accepted_denominations}",
            reason_code=RejectedReason.WRONG_DENOMINATION,
        )


def get_posting_amount(
    posting: PostingInstruction, include_pending_out: bool = True, address: str = DEFAULT_ADDRESS
) -> Decimal:
    posting_amount = posting.balances()[
        (address, DEFAULT_ASSET, posting.denomination, Phase.COMMITTED)
    ].net
    if include_pending_out:
        posting_amount += posting.balances()[
            (address, DEFAULT_ASSET, posting.denomination, Phase.PENDING_OUT)
        ].net

    return Decimal(posting_amount)


def is_force_override(pib: PostingInstructionBatch) -> bool:
    return str_to_bool(pib.batch_details.get("force_override"))


def validate_amount_precision(amount: Decimal, max_precision: int = 2) -> None:
    """
    Raise a Rejection exception if the amount has non-zero digits after the specified number of
    decimal places
    :param amount: the amount to check
    :param max_precision: the max integer number of non-zero decimal places
    :raises Rejected: when amount has non-zero digits after max_precision decimal places
    """
    if round_decimal(amount, max_precision) != amount:
        raise Rejected(
            message=f"Amount {amount} has non-zero digits after {max_precision} decimal places",
            reason_code=RejectedReason.CLIENT_CUSTOM_REASON,
        )


def validate_single_hard_settlement(postings_batch: PostingInstructionBatch) -> None:
    """
    Raise a Rejection exception if the postings batch has more than one instruction or if any
    the instruction type is not a hard settlement
    :param postings_batch: the postings batch to process
    :raises Rejected:
    """
    # Check posting batch is valid
    if len(postings_batch) > 1 or any(
        posting.type != PostingInstructionType.HARD_SETTLEMENT for posting in postings_batch
    ):
        raise Rejected(
            "Only batches with a single hard settlement are supported",
            reason_code=RejectedReason.CLIENT_CUSTOM_REASON,
        )


def instruct_aggregate_postings(
    vault: Vault,
    effective_date: datetime,
    postings: list[PostingInstruction],
    prefix: str,
    delta_addresses: Optional[list[str]] = None,
    absolute_addresses: Optional[list[str]] = None,
    aggregated_vaults: Optional[dict[str, Vault]] = None,
    contra_address: str = "INTERNAL_CONTRA",
) -> None:
    """
    Used for supervisor contracts to aggregate multiple posting instructions that arise
    from supervisee accounts. Assumes TSIDE asset.
    Any postings targeting the same balance address name will be aggregated. e.g. If supervisee 1
    and supervisee 2 both have postings to address PRINCIPAL_DUE, the aggregate value of these will
    be calculated into a new posting instruction of length 1 to a balance address:
    <prefix>_<balance_address> (e.g. TOTAL_PRINCIPAL_DUE).
    The feature assumes that all posting instructions are of the same denomination.
    The debit/credit attribute on each instruction is used to determine whether the supervisee
    address and contra address should be debited or credited.
    A posting instruction batch is instructed from the `vault` object with the relevant instructions

    :param vault: the vault object for the account where the aggregate postings are made
    :param effective_date: date and time of hook being run
    :param postings: the posting instructions to derive aggregate posting instructions from
    :param prefix: The prefix of the aggregation balance.
    :param delta_addresses: Optional list of addresses that are aggregated based on delta amounts
    from the posting instructions
    :param absolute_addresses: Optional list of addresses that are aggregated based on the sum of
    rounded absolute address amounts, including impact of the `postings`. For example, if account 1
    has balance A value 0.123 and there is a posting to increase this by 0.001, no aggregate posting
    is created as the rounded absolute amount is unchanged (round(0.123, 2) == round(0.124, 2)). If
    account 1 has balance A value 0.123 and there is a posting to increase this by 0.002, an
    aggregate posting is created with amount 0.001 as the rounded absolute amount has changed from
    0.12 to 0.13. If used, `aggregated_vaults` must be populated
    :param aggregated_vaults: vault objects for the accounts whose postings are being aggregated.
    Only required if using `absolute_addresses`.
    :param contra_address: The contra balance address to use for aggregate postings on the account
    represented by the `vault` parameter. Used for double entry bookkeeping purposes
    """

    if not postings:
        return
    delta_addresses = delta_addresses or []
    absolute_addresses = absolute_addresses or []
    aggregated_vaults = aggregated_vaults or {}

    totals_per_address = {address: Decimal("0") for address in delta_addresses + absolute_addresses}

    # Note: Posting Instructions that are created via the make_internal_transfer_instructions are
    # advised not to be inspected. In this case, the attributes being inspected are those that were
    # defined within the contract and are therefore, relatively safe to use.

    # The debit/credit attribute is being used in this function which is also generally advised
    # against. As these are CustomInstructions that are created via the contract, this is a rarity
    # where the debit/credit should be considered.

    for instruction in postings:

        instruction_amount = instruction.amount
        instruction_credit = instruction.credit
        instruction_denomination = instruction.denomination
        instruction_address = instruction.account_address
        instruction_account_id = instruction.account_id

        # tracking the aggregate balance by defining a debit as increasing the balance
        # and credits as decreasing the balance.
        if instruction_address in delta_addresses:
            # Assuming asset tside so credit decreases balance
            if instruction_credit is False:
                totals_per_address[instruction_address] += instruction_amount
            else:
                totals_per_address[instruction_address] -= instruction_amount

        # when using absolute amount deltas, we compare:
        # - round (delta amount from posting + current balance),2)
        # - round (current balance, 2)
        # postings are only instructed if the difference is != 0
        elif instruction_address in absolute_addresses:
            current_balance = get_balance_sum(
                vault=aggregated_vaults[instruction_account_id],
                addresses=[instruction_address],
                denomination=instruction_denomination,
            )
            # Assuming asset tside so credit decreases balance
            new_balance = (
                current_balance - instruction_amount
                if instruction_credit
                else current_balance + instruction_amount
            )
            absolute_diff = round_decimal(new_balance, 2) - round_decimal(current_balance, 2)
            # this could be +ve or -ve
            totals_per_address[instruction_address] += absolute_diff

    aggregate_instructions = _create_aggregate_postings(
        vault, totals_per_address, instruction_denomination, contra_address, prefix
    )

    if aggregate_instructions:
        vault.instruct_posting_batch(
            posting_instructions=aggregate_instructions,
            effective_date=effective_date,
            client_batch_id=f"AGGREGATE_LOC_{vault.get_hook_execution_id()}",
            # ensure aggregates don't get rebalanced by accident
            batch_details={"force_override": "True"},
        )


def _create_aggregate_postings(
    vault: Vault,
    address_amounts: dict[str, Decimal],
    denomination: str,
    contra_address: str,
    prefix: str,
) -> list[PostingInstruction]:
    aggregate_instructions = []

    for address, value in address_amounts.items():

        # posting instruction is not required for an amount of net 0.
        if value == 0:
            continue

        prefix_address = prefix + "_" + address

        # determine whether we are debiting or crediting the relevant address
        # based on the aggregate value.
        from_account_address, to_address = (
            (prefix_address, contra_address) if value > 0 else (contra_address, prefix_address)
        )

        aggregate_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(value),
                denomination=denomination,
                client_transaction_id=f"AGGREGATE_{prefix_address}_{vault.get_hook_execution_id()}",
                from_account_id=vault.account_id,
                from_account_address=from_account_address,
                to_account_id=vault.account_id,
                to_account_address=to_address,
                override_all_restrictions=True,
                instruction_details={"description": "aggregate balances"},
            )
        )

    return aggregate_instructions
