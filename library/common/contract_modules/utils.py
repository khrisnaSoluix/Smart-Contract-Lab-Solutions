# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
"""
Utils module
"""


api = "3.9.0"
display_name = "Utils module"
description = "A series of common functions that are frequently used by multiple smart contracts"

# yearly_to_daily_rate
VALID_DAYS_IN_YEAR = ["360", "365", "366", "actual"]
DEFAULT_DAYS_IN_YEAR = "actual"

# misc
ROUNDING_TYPES = Union[
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_05UP,
]


def get_parameter(
    vault,
    name: str,
    at: datetime = None,
    is_json: bool = False,
    is_boolean: bool = False,
    union: bool = False,
    optional: bool = False,
    upper_case_dict_values: bool = False,
    upper_case_list_values: bool = False,
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
    :param upper_case_dict_values: if is_json is True and we are expecting the
    parameter to take shape dict[str:dict[str,str]], we will convert the dict[str,str] values to
    upper case
    :param upper_case_list_values: if is_json is True and we are expecting the
    parameter to take shape dict[str:list[str]], we will convert the list[str] values to upper case
    then we will return the dict values in upper case, whether these values are str/list/dict
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
        try:
            parameter = json_loads(parameter)
        except:  # noqa: E722, B001
            raise InvalidContractParameter(
                f"Exception while JSON loading parameter {name}\nValue {parameter}"
            )

        # We convert dictionary values to upper case based on the date type shape.
        # The converted values often represent transaction references, which we always
        # want to parse in upper case.
        # The dictionary keys often represent transaction types, which we want to
        # keep in the original case.
        if upper_case_dict_values:
            parameter = {
                key: {str(i).upper(): str(j).upper() for i, j in value.items()}
                for key, value in parameter.items()
            }
        elif upper_case_list_values:
            parameter = {key: [str(i).upper() for i in value] for key, value in parameter.items()}

    return parameter


def str_to_bool(string: str) -> bool:
    """
    Convert a string true to bool True, default value of False.
    :param string:
    :return:
    """
    return str(string).lower() == "true"


def yearly_to_daily_rate(yearly_rate: Decimal, year: int, days_in_year: str = "actual") -> Decimal:
    """
    Convert yearly rate to daily rate.
    """
    days_in_year = days_in_year if days_in_year in VALID_DAYS_IN_YEAR else DEFAULT_DAYS_IN_YEAR
    if days_in_year == "actual":
        days_in_year = Decimal("366") if is_leap_year(year) else Decimal("365")
    else:
        days_in_year = Decimal(days_in_year)

    return yearly_rate / days_in_year


def is_leap_year(year: int) -> bool:
    """
    Determine if given year is a leap year (i.e. has 366 days in the year)
    """
    if year % 400 == 0:
        return True
    elif year % 100 == 0:
        return False
    elif year % 4 == 0:
        return True
    else:
        return False


def round_decimal(
    amount: Decimal,
    decimal_places: int,
    rounding: ROUNDING_TYPES = ROUND_HALF_UP,
) -> Decimal:
    """
    Round an amount to specified number of decimal places
    :param amount: Decimal, amount to round
    :param decimal_places: int, number of places to round to
    :param rounding: the type of rounding strategy to use
    :return: Decimal, rounded amount
    """
    return amount.quantize(Decimal((0, (1,), -decimal_places)), rounding=rounding)


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


def is_flag_in_list_applied(
    vault, parameter_name: str, application_timestamp: datetime = None
) -> bool:
    """
    Determine if a flag is set and active for a customer from a given list of flag names
    :param vault:
    :param parameter_name: str, name of the parameter to retrieve
    :param application_timestamp: datetime, optional time at which to check if any flags
    were applied. If not specified latest is used.
    :return: bool, True if any of the flags in the parameterised list are applied at the
    timestamp
    """
    list_of_flag_names = get_parameter(vault, name=parameter_name, is_json=True)

    return any(
        vault.get_flag_timeseries(flag=flag_name).at(timestamp=application_timestamp)
        if application_timestamp
        else vault.get_flag_timeseries(flag=flag_name).latest()
        for flag_name in list_of_flag_names
    )


def create_schedule_dict_from_datetime(schedule_datetime: datetime) -> dict[str, str]:
    """
    Creates a dict representing a schedule from datetime as function input
    """
    return {
        "year": str(schedule_datetime.year),
        "month": str(schedule_datetime.month),
        "day": str(schedule_datetime.day),
        "hour": str(schedule_datetime.hour),
        "minute": str(schedule_datetime.minute),
        "second": str(schedule_datetime.second),
    }


def has_parameter_value_changed(
    parameter_name: str,
    old_parameters: dict[str, str],
    updated_parameters: dict[str, str],
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


def are_optional_parameters_set(vault, parameters: list[str]) -> bool:
    """
    Determines whether the list of optional parameter names are set

    :param vault:
    :param parameters: List of vault parameter names

    :return: bool, True if all parameters are set, False otherwise
    """
    return all(
        get_parameter(vault, parameter, optional=True) is not None for parameter in parameters
    )


def get_balance_sum(
    vault,
    addresses: list[str],
    timestamp: datetime = None,
    denomination: str = None,
    phase: Phase = Phase.COMMITTED,
    balances: BalanceDefaultDict = None,
) -> Decimal:
    """
    Sum balances for list of given addresses.
    :param vault: balances, parameters
    :param addresses: list of addresses
    :param timestamp: optional datetime at which balances to be summed
    :param denomination: the denomination of the balance
    :param phase: phase of the balance
    :return: sum of the balances
    """
    balances = balances or (
        vault.get_balance_timeseries().latest()
        if timestamp is None
        else vault.get_balance_timeseries().at(timestamp=timestamp)
    )

    if denomination is None:
        denomination = get_parameter(vault, "denomination")

    return Decimal(
        sum(balances[(address, DEFAULT_ASSET, denomination, phase)].net for address in addresses)
    )


def get_transaction_type(
    instruction_details: dict[str, str],
    txn_code_to_type_map: dict[str, str],
    default_txn_type: str,
) -> str:
    """
    Gets the transaction type from Posting instruction metadata.
    :param instruction_details: mapping containing instruction-level metadata for the Posting
    :param txn_code_to_type_map: map of transaction code to transaction type
    :param default_txn_type: transaction type to default to if code not found in the map
    :return: the transaction type of the Posting instruction
    """
    txn_code = instruction_details.get("transaction_code")
    return txn_code_to_type_map.get(txn_code, default_txn_type)


def get_previous_schedule_execution_date(
    vault, event_type: str, account_start_date: datetime = None
) -> datetime:
    """
    Gets the last execution time of an event (if it exists) else returns the start date
    of the account
    :param event_type: a string of the schedule event type
    :param account_start_date: the start date of the account
    :return: the last execution time of a schedule else the account start date
    """

    last_schedule_event_date = vault.get_last_execution_time(event_type=event_type)
    return last_schedule_event_date if last_schedule_event_date is not None else account_start_date
