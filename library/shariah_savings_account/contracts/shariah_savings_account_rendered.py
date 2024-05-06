# Code auto-generated using Inception Smart Contract Renderer Version 2.0.1


# Objects below have been imported from:
#    shariah_savings_account.py
# md5:b1dad3bdaa4ea4c8d942aa2eadf3bc4c

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
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    StringShape,
    BalancesObservationFetcher,
    DefinedDateTime,
    Override,
    PostingsIntervalFetcher,
    RelativeDateTime,
    Shift,
    NumberShape,
    AccountIdShape,
    ClientTransaction,
    PrePostingHookArguments,
    SmartContractEventType,
    UnionItem,
    UnionShape,
    ActivationHookArguments,
    ActivationHookResult,
    ConversionHookArguments,
    ConversionHookResult,
    DeactivationHookArguments,
    DeactivationHookResult,
    DenominationShape,
    PostingInstructionsDirective,
    PostParameterChangeHookArguments,
    PostParameterChangeHookResult,
    PostPostingHookArguments,
    PostPostingHookResult,
    PrePostingHookResult,
    ScheduledEventHookArguments,
    ScheduledEventHookResult,
    fetch_account_data,
    requires,
)
from calendar import isleap
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import ROUND_HALF_UP, Decimal
from json import dumps, loads
from typing import Optional, Any, Callable, Iterable, Mapping, Union, NamedTuple
from zoneinfo import ZoneInfo

api = "4.0.0"
version = "3.0.1"
display_name = "Shariah Savings Account"
tside = Tside.LIABILITY
supported_denominations = ["MYR"]


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def activation_hook(
    vault: Any, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    scheduled_events: dict[str, ScheduledEvent] = {}
    effective_datetime = hook_arguments.effective_datetime
    scheduled_events.update(
        tiered_profit_accrual_scheduled_events(vault=vault, start_datetime=effective_datetime)
    )
    scheduled_events.update(
        profit_application_scheduled_events(vault=vault, start_datetime=effective_datetime)
    )
    return ActivationHookResult(scheduled_events_return_value=scheduled_events)


def conversion_hook(
    vault: Any, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    return ConversionHookResult(scheduled_events_return_value=hook_arguments.existing_schedules)


@requires(parameters=True)
@fetch_account_data(balances=["live_balances_bof"])
def deactivation_hook(
    vault: Any, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    posting_instructions: list[CustomInstruction] = []
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    live_balances = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    posting_instructions.extend(
        early_closure_fee_apply_fees(
            vault=vault,
            denomination=denomination,
            balances=live_balances,
            effective_datetime=hook_arguments.effective_datetime,
            account_type=ACCOUNT_TYPE,
        )
    )
    posting_instructions.extend(
        tiered_profit_accrual_get_profit_reversal_postings(
            vault=vault,
            event_name="CLOSE_ACCOUNT",
            denomination=denomination,
            balances=live_balances,
            account_type=ACCOUNT_TYPE,
        )
    )
    if posting_instructions:
        return DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=posting_instructions,
                    value_datetime=hook_arguments.effective_datetime,
                    client_batch_id=f"{vault.get_hook_execution_id()}",
                )
            ]
        )
    return None


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def post_parameter_change_hook(
    vault: Any, hook_arguments: PostParameterChangeHookArguments
) -> Optional[PostParameterChangeHookResult]:
    old_parameter_values = hook_arguments.old_parameter_values
    updated_parameter_values = hook_arguments.updated_parameter_values
    if utils_has_parameter_value_changed(
        parameter_name=profit_application_PARAM_PROFIT_APPLICATION_DAY,
        old_parameters=old_parameter_values,
        updated_parameters=updated_parameter_values,
    ):
        schedule_event = profit_application_scheduled_events(
            vault=vault, start_datetime=hook_arguments.effective_datetime
        )[profit_application_APPLICATION_EVENT]
        return PostParameterChangeHookResult(
            update_account_event_type_directives=[
                UpdateAccountEventTypeDirective(
                    event_type=profit_application_APPLICATION_EVENT,
                    expression=schedule_event.expression,
                    schedule_method=schedule_event.schedule_method,
                )
            ]
        )
    return None


@requires(parameters=True)
@fetch_account_data(postings=["MONTH_TO_EFFECTIVE_POSTINGS_FETCHER"])
def post_posting_hook(
    vault: Any, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    postings: utils_PostingInstructionListAlias = hook_arguments.posting_instructions
    effective_datetime = hook_arguments.effective_datetime
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    client_transactions = vault.get_client_transactions(
        fetcher_id=fetchers_MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID
    )
    flat_fees = payment_type_flat_fee_apply_fees(
        vault=vault, postings=postings, denomination=denomination
    )
    threshold_fees = payment_type_threshold_fee_apply_fees(
        vault=vault, postings=postings, denomination=denomination
    )
    monthly_limit_fees = payment_type_monthly_limit_fee_apply_fees(
        vault=vault,
        effective_datetime=effective_datetime,
        denomination=denomination,
        updated_client_transactions=hook_arguments.client_transactions,
        historic_client_transactions=client_transactions,
    )
    custom_instructions = flat_fees + threshold_fees + monthly_limit_fees
    if custom_instructions:
        return PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=custom_instructions, value_datetime=effective_datetime
                )
            ]
        )
    else:
        return None


@requires(parameters=True)
@fetch_account_data(balances=["live_balances_bof"], postings=["EFFECTIVE_DATE_POSTINGS_FETCHER"])
def pre_posting_hook(
    vault: Any, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    posting_instructions = hook_arguments.posting_instructions
    if utils_is_force_override(posting_instructions=posting_instructions):
        return None
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    if denomination_rejection := utils_validate_denomination(
        posting_instructions=posting_instructions, accepted_denominations=[denomination]
    ):
        return PrePostingHookResult(rejection=denomination_rejection)
    balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    if maximum_balance_limit_rejection := maximum_balance_limit_validate(
        vault=vault, postings=posting_instructions, denomination=denomination, balances=balances
    ):
        return PrePostingHookResult(rejection=maximum_balance_limit_rejection)
    if minimum_single_deposit_rejection := minimum_single_deposit_validate(
        vault=vault, postings=posting_instructions, denomination=denomination
    ):
        return PrePostingHookResult(rejection=minimum_single_deposit_rejection)
    if maximum_single_deposit_rejection := maximum_single_deposit_validate(
        vault=vault, postings=posting_instructions, denomination=denomination
    ):
        return PrePostingHookResult(rejection=maximum_single_deposit_rejection)
    if minimum_initial_deposit_rejection := minimum_initial_deposit_validate(
        vault=vault, postings=posting_instructions, denomination=denomination, balances=balances
    ):
        return PrePostingHookResult(rejection=minimum_initial_deposit_rejection)
    if maximum_single_withdrawal_rejection := maximum_single_withdrawal_validate(
        vault=vault, postings=posting_instructions, denomination=denomination
    ):
        return PrePostingHookResult(rejection=maximum_single_withdrawal_rejection)
    if minimum_balance_by_tier_rejection := minimum_balance_by_tier_validate(
        vault=vault, postings=posting_instructions, balances=balances, denomination=denomination
    ):
        return PrePostingHookResult(rejection=minimum_balance_by_tier_rejection)
    if maximum_withdrawal_by_payment_type_rejection := maximum_withdrawal_by_payment_type_validate(
        vault=vault, postings=posting_instructions, denomination=denomination
    ):
        return PrePostingHookResult(rejection=maximum_withdrawal_by_payment_type_rejection)
    if maximum_daily_deposit_rejection := maximum_daily_deposit_validate(
        vault=vault, hook_arguments=hook_arguments, denomination=denomination
    ):
        return PrePostingHookResult(rejection=maximum_daily_deposit_rejection)
    if maximum_daily_withdrawal_rejection := maximum_daily_withdrawal_validate(
        vault=vault, hook_arguments=hook_arguments, denomination=denomination
    ):
        return PrePostingHookResult(rejection=maximum_daily_withdrawal_rejection)
    if max_daily_withdrawal_type_rejection := maximum_daily_withdrawal_by_transaction_type_validate(
        vault=vault, hook_arguments=hook_arguments, denomination=denomination
    ):
        return PrePostingHookResult(rejection=max_daily_withdrawal_type_rejection)
    return None


@requires(event_type="ACCRUE_PROFIT", flags=True, parameters=True)
@fetch_account_data(event_type="ACCRUE_PROFIT", balances=["EOD_FETCHER"])
@requires(event_type="APPLY_PROFIT", parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
@fetch_account_data(event_type="APPLY_PROFIT", balances=["EOD_FETCHER"])
def scheduled_event_hook(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    event_type = hook_arguments.event_type
    effective_datetime = hook_arguments.effective_datetime
    custom_instructions: list[CustomInstruction] = []
    update_event_directives: list[UpdateAccountEventTypeDirective] = []
    posting_instructions_directives: list[PostingInstructionsDirective] = []
    if event_type == tiered_profit_accrual_ACCRUAL_EVENT:
        account_tier = account_tiers_get_account_tier(
            vault=vault, effective_datetime=effective_datetime
        )
        custom_instructions.extend(
            tiered_profit_accrual_accrue_profit(
                vault=vault,
                effective_datetime=effective_datetime,
                account_tier=account_tier,
                account_type=ACCOUNT_TYPE,
            )
        )
    elif event_type == profit_application_APPLICATION_EVENT:
        custom_instructions.extend(
            profit_application_apply_profit(vault=vault, account_type=ACCOUNT_TYPE)
        )
        if update_event_result := profit_application_update_next_schedule_execution(
            vault=vault, effective_datetime=effective_datetime
        ):
            update_event_directives.extend([update_event_result])
    if custom_instructions:
        posting_instructions_directives.append(
            PostingInstructionsDirective(
                posting_instructions=custom_instructions,
                client_batch_id=f"{event_type}_{vault.get_hook_execution_id()}",
                value_datetime=hook_arguments.effective_datetime,
            )
        )
    if posting_instructions_directives or update_event_directives:
        return ScheduledEventHookResult(
            posting_instructions_directives=posting_instructions_directives,
            update_account_event_type_directives=update_event_directives,
        )
    return None


# Objects below have been imported from:
#    utils.py
# md5:b4718e1c735d11f6848158f777e7084f

utils_PostingInstructionTypeAlias = Union[
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
utils_PostingInstructionListAlias = list[
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
utils_ParameterValueTypeAlias = Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]
utils_VALID_DAYS_IN_YEAR = ["360", "365", "366", "actual"]
utils_DEFAULT_DAYS_IN_YEAR = "actual"
utils_RATE_DECIMAL_PLACES = 10


def utils_str_to_bool(string: str) -> bool:
    """
    Convert a string true to bool True, default value of False.
    :param string:
    :return:
    """
    return str(string).lower() == "true"


def utils_round_decimal(
    amount: Decimal, decimal_places: int, rounding: str = ROUND_HALF_UP
) -> Decimal:
    """
    Round an amount to specified number of decimal places
    :param amount: Decimal, amount to round
    :param decimal_places: int, number of places to round to
    :param rounding: the type of rounding strategy to use
    :return: Decimal, rounded amount
    """
    return amount.quantize(Decimal((0, (1,), -int(decimal_places))), rounding=rounding)


def utils_yearly_to_daily_rate(
    effective_date: datetime, yearly_rate: Decimal, days_in_year: str = "actual"
) -> Decimal:
    """
    Calculate the daily rate from a yearly rate, for a given `days_in_year` convention and date
    :param effective_date: the date as of which the conversion happens. This may affect the outcome
    based on the `days_in_year` value.
    :param yearly_rate: the rate to convert
    :param days_in_year: the number of days in the year to assume for the calculation. One of `360`,
    `365`, `366` or `actual`. If actual is used, the number of days is based on effective_date's
    year
    :return: the corresponding daily rate
    """
    days_in_year = (
        days_in_year if days_in_year in utils_VALID_DAYS_IN_YEAR else utils_DEFAULT_DAYS_IN_YEAR
    )
    if days_in_year == "actual":
        num_days_in_year = Decimal("366") if isleap(effective_date.year) else Decimal("365")
    else:
        num_days_in_year = Decimal(days_in_year)
    return utils_round_decimal(
        yearly_rate / num_days_in_year, decimal_places=utils_RATE_DECIMAL_PLACES
    )


def utils_remove_exponent(d: Decimal) -> Decimal:
    """
    Safely remove trailing zeros when dealing with exponents. This is useful when using a decimal
    value in a string used for informational purposes (e.g. instruction_details or logging).
    E.g: remove_exponent(Decimal("5E+3"))
    Returns: Decimal('5000')
    """
    return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()


def utils_get_parameter(
    vault: Any,
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
    if is_optional:
        parameter = parameter.value if parameter.is_set() else default_value
    if is_union and parameter is not None:
        parameter = parameter.key
    if is_boolean and parameter is not None:
        parameter = utils_str_to_bool(parameter.key)
    if is_json and parameter is not None:
        parameter = loads(parameter)
    return parameter


def utils_has_parameter_value_changed(
    parameter_name: str,
    old_parameters: dict[str, utils_ParameterValueTypeAlias],
    updated_parameters: dict[str, utils_ParameterValueTypeAlias],
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


def utils_daily_scheduled_event(
    vault: Any,
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
    hour = int(utils_get_parameter(vault, name=f"{parameter_prefix}_hour"))
    minute = int(utils_get_parameter(vault, name=f"{parameter_prefix}_minute"))
    second = int(utils_get_parameter(vault, name=f"{parameter_prefix}_second"))
    return ScheduledEvent(
        start_datetime=start_datetime,
        expression=ScheduleExpression(hour=hour, minute=minute, second=second),
        skip=skip,
    )


def utils_one_off_schedule_expression(schedule_datetime: datetime) -> ScheduleExpression:
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


def utils_get_schedule_time_from_parameters(
    vault: Any, parameter_prefix: str
) -> tuple[int, int, int]:
    hour = int(utils_get_parameter(vault=vault, name=f"{parameter_prefix}_hour"))
    minute = int(utils_get_parameter(vault=vault, name=f"{parameter_prefix}_minute"))
    second = int(utils_get_parameter(vault=vault, name=f"{parameter_prefix}_second"))
    return (hour, minute, second)


def utils_get_next_schedule_date_calendar_aware(
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
    while utils_falls_on_calendar_events(next_date, calendar_events):
        next_date += relativedelta(days=1)
    return next_date


def utils_falls_on_calendar_events(
    effective_datetime: datetime, calendar_events: CalendarEvents
) -> bool:
    """
    Returns if true if the given date is on or between a calendar event's start and/or end
    timestamp, inclusive.
    """
    return any(
        (
            calendar_event.start_datetime <= effective_datetime <= calendar_event.end_datetime
            for calendar_event in calendar_events
        )
    )


def utils_validate_denomination(
    posting_instructions: list[utils_PostingInstructionTypeAlias],
    accepted_denominations: Iterable[str],
) -> Optional[Rejection]:
    """
    Return a Rejection if any postings do not match accepted denominations.
    """
    return_rejection = False
    accepted_denominations_set = set(accepted_denominations)
    for posting_instruction in posting_instructions:
        if posting_instruction.type == PostingInstructionType.CUSTOM_INSTRUCTION:
            for posting in posting_instruction.postings:
                if posting.denomination not in accepted_denominations_set:
                    return_rejection = True
                    break
        elif posting_instruction.denomination not in accepted_denominations_set:
            return_rejection = True
            break
    if return_rejection:
        return Rejection(
            message=f"Cannot make transactions in the given denomination, transactions must be one of {sorted(accepted_denominations_set)}",
            reason_code=RejectionReason.WRONG_DENOMINATION,
        )
    return None


def utils_create_postings(
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


def utils_is_key_in_instruction_details(
    *, key: str, posting_instructions: utils_PostingInstructionListAlias
) -> bool:
    return all(
        (
            utils_str_to_bool(posting_instruction.instruction_details.get(key, "false"))
            for posting_instruction in posting_instructions
        )
    )


def utils_is_force_override(posting_instructions: utils_PostingInstructionListAlias) -> bool:
    return utils_is_key_in_instruction_details(
        key="force_override", posting_instructions=posting_instructions
    )


def utils_standard_instruction_details(
    description: str, event_type: str, gl_impacted: bool = False, account_type: str = ""
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


def utils_sum_balances(
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
            (
                balances[BalanceCoordinate(address, asset, denomination, phase)].net
                for address in addresses
            )
        )
    )
    return (
        balance_sum
        if decimal_places is None
        else utils_round_decimal(amount=balance_sum, decimal_places=decimal_places)
    )


def utils_balance_at_coordinates(
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
        else utils_round_decimal(amount=balance_net, decimal_places=decimal_places)
    )


def utils_get_available_balance(
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


def utils_get_current_net_balance(
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
    (committed_coordinate, pending_in_coordinate) = utils__get_current_balance_coordinates(
        denomination=denomination, address=address, asset=asset
    )
    return balances[committed_coordinate].net + balances[pending_in_coordinate].net


def utils_get_current_credit_balance(
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
    (committed_coordinate, pending_in_coordinate) = utils__get_current_balance_coordinates(
        denomination=denomination, address=address, asset=asset
    )
    return balances[committed_coordinate].credit + balances[pending_in_coordinate].credit


def utils__get_current_balance_coordinates(
    *, denomination: str, address: str, asset: str
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
    return (committed_coordinate, pending_in_coordinate)


# Objects below have been imported from:
#    account_tiers.py
# md5:dc120010ded3a60288646bc9643611dc

account_tiers_PARAM_ACCOUNT_TIER_NAMES = "account_tier_names"
account_tiers_parameters = [
    Parameter(
        name=account_tiers_PARAM_ACCOUNT_TIER_NAMES,
        level=ParameterLevel.TEMPLATE,
        description="JSON encoded list of account tiers used as keys in map-type parameters. Flag definitions must be configured for each used tier. If the account is missing a flag the final tier in this list is used.",
        display_name="Tier Names",
        shape=StringShape(),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=dumps(["STANDARD"]),
    )
]


def account_tiers_get_account_tier(
    vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    """
    Use the account tier flags to get a corresponding value from the account tiers list. If no
    recognised flags are present then the last value in account_tier_names will be used by default.
    If multiple flags are present then the nearest one to the start of account_tier_names will be
    used.
    :param vault: vault object for the account whose tier is being retrieved
    :param effective_datetime: datetime at which to retrieve the flag_timeseries value. If not
    specified the latest value is retrieved
    :return: account tier name assigned to account
    """
    account_tier_names = utils_get_parameter(vault, "account_tier_names", is_json=True)
    for tier_param in account_tier_names:
        if effective_datetime is None:
            if vault.get_flag_timeseries(flag=tier_param).latest():
                return tier_param
        elif vault.get_flag_timeseries(flag=tier_param).at(at_datetime=effective_datetime):
            return tier_param
    return account_tier_names[-1]


def account_tiers_get_tiered_parameter_value_based_on_account_tier(
    tiered_parameter: dict[str, str], tier: str, convert: Optional[Callable] = None
) -> Optional[Any]:
    """
    Use the account tier flags to get a corresponding value from a
    dictionary keyed by account tier.
    If there is no value for the tier provided, None will be returned.
    :param tiered_parameter: dictionary mapping tier names to their corresponding.
    parameter values.
    :param tier: tier name of the account
    :param convert: function used to convert the resulting value before returning e.g Decimal.
    :return: as per convert function, value for tiered_param corresponding to account tier.
    """
    if tier in tiered_parameter:
        value = tiered_parameter[tier]
        return convert(value) if convert else value
    return None


# Objects below have been imported from:
#    fetchers.py
# md5:dcba39f23bd6808d7c243d6f0f8ff8d0

fetchers_EOD_FETCHER_ID = "EOD_FETCHER"
fetchers_EOD_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_EOD_FETCHER_ID,
    at=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME, find=Override(hour=0, minute=0, second=0)
    ),
)
fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID = "EFFECTIVE_FETCHER"
fetchers_LIVE_BALANCES_BOF_ID = "live_balances_bof"
fetchers_LIVE_BALANCES_BOF = BalancesObservationFetcher(
    fetcher_id=fetchers_LIVE_BALANCES_BOF_ID, at=DefinedDateTime.LIVE
)
fetchers_EFFECTIVE_DATE_POSTINGS_FETCHER_ID = "EFFECTIVE_DATE_POSTINGS_FETCHER"
fetchers_EFFECTIVE_DATE_POSTINGS_FETCHER = PostingsIntervalFetcher(
    fetcher_id=fetchers_EFFECTIVE_DATE_POSTINGS_FETCHER_ID,
    start=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME, find=Override(hour=0, minute=0, second=0)
    ),
    end=DefinedDateTime.EFFECTIVE_DATETIME,
)
fetchers_MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID = "MONTH_TO_EFFECTIVE_POSTINGS_FETCHER"
fetchers_MONTH_TO_EFFECTIVE_POSTINGS_FETCHER = PostingsIntervalFetcher(
    fetcher_id=fetchers_MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID,
    start=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME, find=Override(day=1, hour=0, minute=0, second=0)
    ),
    end=DefinedDateTime.EFFECTIVE_DATETIME,
)

# Objects below have been imported from:
#    fees.py
# md5:b2610b34eacbb6d4fad8d66a53bdd6e9


def fees_fee_custom_instruction(
    customer_account_id: str,
    denomination: str,
    amount: Decimal,
    internal_account: str,
    customer_account_address: str = DEFAULT_ADDRESS,
    instruction_details: Optional[dict[str, str]] = None,
    reversal: bool = False,
) -> list[CustomInstruction]:
    """
    Create a Custom Instruction containing customer and internal
    account postings for applying a fee.
    :param customer_account_id: the customer account id to use
    :param denomination: the denomination of the fee
    :param amount: the fee amount. If this is amount is <= 0 an empty list is returned
    :param internal_account: the internal account id to use. The DEFAULT address is always
    used on this account
    :param customer_account_address: the address on the customer account to debit, defaults to the
    DEFAULT address
    :param instruction_details: instruction details to add to the postings
    Useful if more than one fee affects a given balance (e.g. un-netted tiered interest)
    :return: Custom instructions to apply fee, if required
    """
    if amount <= 0:
        return []
    postings = fees_fee_postings(
        customer_account_id=customer_account_id,
        customer_account_address=customer_account_address,
        denomination=denomination,
        amount=amount,
        internal_account=internal_account,
        reversal=reversal,
    )
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


def fees_fee_postings(
    customer_account_id: str,
    customer_account_address: str,
    denomination: str,
    amount: Decimal,
    internal_account: str,
    reversal: bool = False,
) -> list[Posting]:
    """
    Create customer and internal account postings for applying a fee.
    :param customer_account_id: the customer account id to use
    :param customer_account_address: the address on the customer account to debit
    :param denomination: the denomination of the fee
    :param amount: the fee amount. If this is amount is <= 0 an empty list is returned.
    :param internal_account: the internal account id to use. The default address is always
    used on this account
    :return: the fee postings
    """
    if amount <= 0:
        return []
    return [
        Posting(
            credit=True,
            amount=amount,
            denomination=denomination,
            account_id=customer_account_id if reversal else internal_account,
            account_address=customer_account_address if reversal else DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=False,
            amount=amount,
            denomination=denomination,
            account_id=internal_account if reversal else customer_account_id,
            account_address=DEFAULT_ADDRESS if reversal else customer_account_address,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
    ]


# Objects below have been imported from:
#    early_closure_fee.py
# md5:3f29d9cfc2b948119dca1578086ec1e9

early_closure_fee_DEFAULT_EARLY_CLOSURE_FEE_ADDRESS = "EARLY_CLOSURE_FEE"
early_closure_fee_PARAM_EARLY_CLOSURE_FEE = "early_closure_fee"
early_closure_fee_PARAM_EARLY_CLOSURE_DAYS = "early_closure_days"
early_closure_fee_PARAM_EARLY_CLOSURE_FEE_INCOME_ACCOUNT = "early_closure_fee_income_account"
early_closure_fee_parameters = [
    Parameter(
        name=early_closure_fee_PARAM_EARLY_CLOSURE_FEE,
        level=ParameterLevel.TEMPLATE,
        description="The fee charged if the account is closed early.",
        display_name="Early Closure Fee",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name=early_closure_fee_PARAM_EARLY_CLOSURE_DAYS,
        level=ParameterLevel.TEMPLATE,
        description="The number of days that must be completed in order to avoid an early closure  fee, should the account be closed.",
        display_name="Early Closure Days",
        shape=NumberShape(min_value=0, max_value=90, step=1),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=Decimal("90"),
    ),
    Parameter(
        name=early_closure_fee_PARAM_EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for early closure fee income balance.",
        display_name="Early Closure Fee Income Account",
        shape=AccountIdShape(),
        default_value="EARLY_CLOSURE_FEE_INCOME",
    ),
]


def early_closure_fee_apply_fees(
    vault: Any,
    effective_datetime: datetime,
    account_type: str,
    early_closure_fee_tracker_address: str = early_closure_fee_DEFAULT_EARLY_CLOSURE_FEE_ADDRESS,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> list[CustomInstruction]:
    """
    Applies the early closure fee if account is closed within 'early_closure_days' number of days
    (midnight inclusive) and if the fee hasn't been applied already.

    :param vault: The vault object containing parameters, balances, etc.
    :param denomination: The denomination of the fee.
    :param effective_datetime: The effective datetime for fee application.
    :param account_type: The account type to be noted in the custom instruction detail.
    :param early_closure_fee_tracker_address: The address used to track if fee was applied.
    :return: Returns the Custom Instruction for charging the fee and tracking the fee.
    """
    creation_datetime: datetime = vault.get_account_creation_datetime()
    early_closure_fee = Decimal(
        utils_get_parameter(vault, early_closure_fee_PARAM_EARLY_CLOSURE_FEE)
    )
    early_closure_days = int(utils_get_parameter(vault, early_closure_fee_PARAM_EARLY_CLOSURE_DAYS))
    early_closure_fee_income_account: str = utils_get_parameter(
        vault, early_closure_fee_PARAM_EARLY_CLOSURE_FEE_INCOME_ACCOUNT
    )
    instructions: list[CustomInstruction] = []
    if early_closure_fee <= 0:
        return instructions
    early_closure_cut_off_datetime = creation_datetime + relativedelta(days=early_closure_days)
    if denomination is None:
        denomination = str(
            utils_get_parameter(vault, name="denomination", at_datetime=effective_datetime)
        )
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    early_closure_fee_coord = BalanceCoordinate(
        account_address=early_closure_fee_tracker_address,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        phase=Phase.COMMITTED,
    )
    fee_has_not_been_charged_before = balances[early_closure_fee_coord].debit == 0
    if fee_has_not_been_charged_before and effective_datetime <= early_closure_cut_off_datetime:
        fee_postings = fees_fee_postings(
            customer_account_id=vault.account_id,
            customer_account_address=DEFAULT_ADDRESS,
            denomination=denomination,
            amount=early_closure_fee,
            internal_account=early_closure_fee_income_account,
        )
        tracker_postings = early_closure_fee__update_closure_fee_tracker(
            denomination=denomination,
            account_id=vault.account_id,
            account_tracker_address=early_closure_fee_tracker_address,
        )
        postings = [*fee_postings, *tracker_postings]
        instructions = [
            CustomInstruction(
                postings=postings,
                instruction_details=utils_standard_instruction_details(
                    description="EARLY CLOSURE FEE",
                    event_type="CLOSE_ACCOUNT",
                    gl_impacted=True,
                    account_type=account_type,
                ),
                override_all_restrictions=True,
            )
        ]
    return instructions


def early_closure_fee__update_closure_fee_tracker(
    denomination: str, account_id: str, account_tracker_address: str
) -> list[Posting]:
    """
    Create postings to track early closure fee applied. Whereas other trackers
    normally make non-zero net postings, here the postings net zero so as to
    not leave custom balance definitions with non-zero balances since it is
    intended for use in the close code hook. Since the sole purpose is to track
    if a fee was applied, the amount can be hardcoded to 1.

    :param denomination: The denomination of this instruction.
    :param account_id: Account id.
    :param account_tracker_address: Address for tracking purposes.
    :return: Returns debit and credit entries for early closure fee tracking.
    """
    postings = utils_create_postings(
        amount=Decimal("1"),
        debit_account=account_id,
        debit_address=account_tracker_address,
        credit_account=account_id,
        credit_address=account_tracker_address,
        denomination=denomination,
    )
    return postings


# Objects below have been imported from:
#    payment_type_flat_fee.py
# md5:a2ce85c873debc7d847abea1516c4e7e

payment_type_flat_fee_PAYMENT_TYPE = "PAYMENT_TYPE"
payment_type_flat_fee_PARAM_PAYMENT_TYPE_FLAT_FEE = "payment_type_flat_fee"
payment_type_flat_fee_parameters = [
    Parameter(
        name=payment_type_flat_fee_PARAM_PAYMENT_TYPE_FLAT_FEE,
        level=ParameterLevel.TEMPLATE,
        description="The flat fees to apply for a given payment type.",
        display_name="Payment Type Flat Fees",
        shape=StringShape(),
        default_value=dumps({"ATM": "1"}),
    )
]


def payment_type_flat_fee_apply_fees(
    vault: Any, postings: utils_PostingInstructionListAlias, denomination: str
) -> list[CustomInstruction]:
    """
    Check posting instruction details for PAYMENT_TYPE key and return any fees associated with that
    payment type. The fee is credited to the account defined by the payment_type_fee_income_account
    parameter.
    """
    payment_type_flat_fees = utils_get_parameter(
        vault, payment_type_flat_fee_PARAM_PAYMENT_TYPE_FLAT_FEE, is_json=True
    )
    payment_type_fee_income_account = utils_get_parameter(vault, "payment_type_fee_income_account")
    posting_instructions: list[CustomInstruction] = []
    for posting in postings:
        current_payment_type = posting.instruction_details.get(payment_type_flat_fee_PAYMENT_TYPE)
        if not current_payment_type or current_payment_type not in payment_type_flat_fees:
            continue
        posting_balances = posting.balances()
        posting_withdrawal_amount = utils_get_available_balance(
            balances=posting_balances, denomination=denomination
        )
        if posting_withdrawal_amount >= 0:
            continue
        payment_type_fee = Decimal(payment_type_flat_fees[current_payment_type])
        if payment_type_fee > 0:
            instruction_details = utils_standard_instruction_details(
                description=f"payment fee applied for withdrawal using {current_payment_type}",
                event_type="APPLY_PAYMENT_TYPE_FLAT_FEE",
                gl_impacted=True,
            )
            instruction_details["payment_type"] = current_payment_type
            posting_instructions.extend(
                fees_fee_custom_instruction(
                    customer_account_id=vault.account_id,
                    denomination=denomination,
                    amount=payment_type_fee,
                    internal_account=payment_type_fee_income_account,
                    instruction_details=instruction_details,
                )
            )
    return posting_instructions


# Objects below have been imported from:
#    client_transaction_utils.py
# md5:9df207f005346ae0eb108bed3183c21a


def client_transaction_utils_sum_client_transactions(
    *,
    cutoff_datetime: datetime,
    client_transactions: dict[str, ClientTransaction],
    denomination: str,
) -> tuple[Decimal, Decimal]:
    """
    Sum the net amount credited to and debited from an account by the given client_transactions
    since a given cut off point in a specific denomination. The impact of chainable instructions is
    considered in the Auth, unless the subsequent instructions increase the auth'd amount.
    For example:
    - an inbound auth before cut off and settlement for same amount X after cut off will result in 0
      credit and debit.
    - an inbound auth and settlement for same amount X, both after cut off will result in the amount
      in credit = X and debit = 0
    - an inbound auth before cut off for amount X and settlement after cut off for Y, where Y > X,
      will result in credit = Y - X and debit = 0

    :param cutoff_datetime: postings value timestamped before this datetime are excluded from the
    totals.
    :param client_transactions: ClientTransaction dictionary, keyed by unique client transaction id
    :param denomination: denomination for which the sums are being calculated, client transactions
    in other denomination will be ignored
    :return: Sum of credits, sum of debits for given client transactions since the cut-off in the
    specified denomination. Both values are >= 0
    """
    amount_debited = Decimal(0)
    amount_credited = Decimal(0)
    for transaction in client_transactions.values():
        if transaction.denomination == denomination:
            transaction_amount = client_transaction_utils__get_total_transaction_impact(
                transaction=transaction
            )
            cutoff_datetime -= relativedelta(microseconds=1)
            amount_before_cutoff = client_transaction_utils__get_total_transaction_impact(
                transaction=transaction, effective_datetime=cutoff_datetime
            )
            amount = transaction_amount - amount_before_cutoff
            if amount > 0:
                amount_credited += amount
            else:
                amount_debited += abs(amount)
    return (amount_credited, amount_debited)


def client_transaction_utils_filter_client_transactions(
    *,
    client_transactions: dict[str, ClientTransaction],
    denomination: str,
    key: str,
    value: str,
    client_transaction_ids_to_ignore: Optional[list[str]] = None,
) -> dict[str, ClientTransaction]:
    """
    Filters client transactions to only include client transactions with:
    - the specified denomination
    - no custom instructions
    - non-released status
    - the specified key-value pair on the first posting instruction

    :param client_transactions: the client transactions to filter
    :param denomination: the denomination to match
    :param key: key to reference in the instruction details
    :param value: value to lookup against the key in the instruction details
    :param client_transaction_ids_to_ignore: list of specific client transaction ids to filter out
    :return: the filtered client transactions. Could be empty
    """
    if client_transaction_ids_to_ignore is None:
        client_transaction_ids_to_ignore = []
    return {
        client_transaction_id: client_transaction
        for (client_transaction_id, client_transaction) in client_transactions.items()
        if client_transaction_id not in client_transaction_ids_to_ignore
        and client_transaction.denomination == denomination
        and (not client_transaction.released())
        and (
            client_transaction.posting_instructions[0].type
            != PostingInstructionType.CUSTOM_INSTRUCTION
        )
        and (client_transaction.posting_instructions[0].instruction_details.get(key) == value)
    }


def client_transaction_utils_extract_debits_by_instruction_details_key(
    *,
    denomination: str,
    client_transactions: dict[str, ClientTransaction],
    cutoff_datetime: datetime,
    key: str,
    value: str,
    client_transaction_ids_to_ignore: Optional[list[str]] = None,
) -> utils_PostingInstructionListAlias:
    """
    Extracts all posting instructions in the client transactions that resulted in a net debit
    since the cutoff
    - debit amount includes any debit impact to the available balance at the DEFAULT address and
    specified denomination, which includes unsettled authorisations.
    - type is determined by the specified key-value pair on the first posting instruction of a
    given client transaction.
    - Released client transactions are ignored.
    - Client transactions with a CustomInstruction are ignored.

    :param denomination: denomination to consider
    :param client_transactions: historic and new client transactions to consider
    :param cutoff_datetime: datetime from which to include client transaction postings, inclusive
    :param key: key to reference in the instruction details
    :param value: value to lookup against the key in the instruction details
    :param client_transaction_ids_to_ignore: list of specific client transaction ids to filter out
    :return the list of instructions
    """
    debit_instructions: utils_PostingInstructionListAlias = []
    in_scope_transactions = client_transaction_utils_filter_client_transactions(
        client_transactions=client_transactions,
        denomination=denomination,
        client_transaction_ids_to_ignore=client_transaction_ids_to_ignore,
        key=key,
        value=value,
    )
    for transaction in in_scope_transactions.values():
        amount_before_posting = client_transaction_utils__get_total_transaction_impact(
            transaction=transaction,
            effective_datetime=cutoff_datetime - relativedelta(microseconds=1),
        )
        for posting_instruction in transaction.posting_instructions:
            if posting_instruction.value_datetime < cutoff_datetime:
                continue
            amount_after_posting = client_transaction_utils__get_total_transaction_impact(
                transaction=transaction, effective_datetime=posting_instruction.value_datetime
            )
            if amount_after_posting < amount_before_posting:
                debit_instructions.append(posting_instruction)
            amount_before_posting = amount_after_posting
    return debit_instructions


def client_transaction_utils__get_total_transaction_impact(
    *, transaction: ClientTransaction, effective_datetime: Optional[datetime] = None
) -> Decimal:
    """
    For any financial movement, the total effect a ClientTransaction has had on the balances can be
    represented by the sum of settled and unsettled effects.
    WARNING: ClientTransaction effects are always None in the platform if they are based on a
    CustomInstruction. This method will return Decimal(0) if such a ClientTransaction is provided

    1. HardSettlement (-10):
        authorised: 0, settled: -10, unsettled: 0
        sum = -10
    2. Authorisation (-10)
        authorised: -10, settled: 0, unsettled: -10
        sum = -10
    3. Authorisation (-10) + Adjustment (-5)
        authorisation:  authorised: -10, settled: 0, unsettled: -10
        adjustment:     authorised: -15, settled: 0, unsettled: -15
        sum = -15
    4. Authorisation (-10) + Total Settlement (-10)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        settlement:    authorised: -10, settled: -10, unsettled: 0
        sum = -10
    5. Authorisation (-10) + Partial Settlement Non-final (-5)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        settlement:    authorised: -10, settled: -5, unsettled: -5
        # if the settlement was not final, then the total effect of the transaction
        # is the value of the initial auth.
        sum = -10
    6. Authorisation (-10) + Partial Settlement Final (-5)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        settlement:    authorised: -5, settled: -5, unsettled: 0
        # as the settlement was final, the remaining funds were released. The impact
        # of this transaction is therefore only -5, i.e. even though the original auth
        # was -10, -5 of that was returned.
        sum = -5
    7. Authorisation (-10) + Oversettlement (auth -10 & an additional -5)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        settlement:    authorised: -10, settled: -15, unsettled: 0
        # as an oversettlement has occurred, the impact on the account is the
        # the settlement amount of -15
        sum = -15
    8. Authorisation (-10) + Release (-10)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        release:       authorised: -10, settled: 0, unsettled: 0
        # as we have released all funds then this is expected to be 0, i.e. the
        # transaction has no overall impact on an account,
        sum = 0

    :param transaction: client transaction to process
    :param effective_datetime: effective datetime to determine which point of time to
    :return: The net of settled and unsettled effects.
    """
    if (
        effective_datetime is not None
        and transaction.start_datetime is not None
        and (effective_datetime < transaction.start_datetime)
    ):
        return Decimal(0)
    transaction_effects = transaction.effects(effective_datetime=effective_datetime)
    if transaction_effects is None:
        return Decimal(0)
    return transaction_effects.settled + transaction_effects.unsettled


# Objects below have been imported from:
#    payment_type_monthly_limit_fee.py
# md5:076c094243fa9c4471097a0777e9b50f

payment_type_monthly_limit_fee_PAYMENT_TYPE = "PAYMENT_TYPE"
payment_type_monthly_limit_fee_PARAM_MAXIMUM_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT = (
    "maximum_monthly_payment_type_withdrawal_limit"
)
payment_type_monthly_limit_fee_parameters = [
    Parameter(
        name=payment_type_monthly_limit_fee_PARAM_MAXIMUM_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT,
        level=ParameterLevel.TEMPLATE,
        description="Fees required when the number of payments exceeds the monthly limit for that payment type.",
        display_name="Monthly Payment Type Withdrawal Limit Fees",
        shape=StringShape(),
        default_value=dumps({"ATM": {"fee": "0.50", "limit": "8"}}),
    )
]


def payment_type_monthly_limit_fee_apply_fees(
    vault: Any,
    effective_datetime: datetime,
    denomination: str,
    updated_client_transactions: dict[str, ClientTransaction],
    historic_client_transactions: Optional[dict[str, ClientTransaction]] = None,
) -> list[CustomInstruction]:
    """
    From the client transactions, check posting instruction details for PAYMENT_TYPE key and return
    any fees associated with that payment type. The fee is credited to the internal account defined
    by the payment_type_fee_income_account parameter.

    :param vault: The vault object containing parameters, balances, etc.
    :param effective_datetime: The effective datetime for fee application.
    :param denomination: The denomination of the fee.
    :param updated_client_transactions: new or updated client transactions that may count towards
    the limit. Typically from PostPostingHookArguments.client_transactions.
    :param historic_client_transactions: Historic client transactions that may count towards the
    limit. Should cover the period from start-of-month to effective datetime. If not provided,
    fetched using MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID fetcher.

    :return: Returns the Custom Instruction for charging the fee.
    """
    if historic_client_transactions is None:
        historic_client_transactions = vault.get_client_transactions(
            fetcher_id=fetchers_MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID
        )
    maximum_monthly_payment_type_withdrawal_limit: dict[str, dict[str, str]] = utils_get_parameter(
        vault,
        payment_type_monthly_limit_fee_PARAM_MAXIMUM_MONTHLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT,
        is_json=True,
    )
    payment_type_fee_income_account = utils_get_parameter(vault, "payment_type_fee_income_account")
    start_of_monthly_window = effective_datetime.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    posting_instructions: list[CustomInstruction] = []
    total_fees_by_payment_type: dict[str, Decimal] = {}
    for (
        payment_type,
        payment_type_config,
    ) in maximum_monthly_payment_type_withdrawal_limit.items():
        payment_type_fee = Decimal(payment_type_config.get("fee", 0))
        payment_type_limit = int(payment_type_config.get("limit", -1))
        if payment_type_fee <= 0 or payment_type_limit < 0:
            continue
        historic_withdrawals = client_transaction_utils_extract_debits_by_instruction_details_key(
            denomination=denomination,
            client_transactions=historic_client_transactions,
            client_transaction_ids_to_ignore=[],
            cutoff_datetime=start_of_monthly_window,
            key=payment_type_monthly_limit_fee_PAYMENT_TYPE,
            value=payment_type,
        )
        new_withdrawals = client_transaction_utils_extract_debits_by_instruction_details_key(
            denomination=denomination,
            client_transactions=updated_client_transactions,
            client_transaction_ids_to_ignore=[],
            cutoff_datetime=effective_datetime,
            key=payment_type_monthly_limit_fee_PAYMENT_TYPE,
            value=payment_type,
        )
        remaining_limit = max(payment_type_limit - len(historic_withdrawals), 0)
        num_fees_to_incur = max(len(new_withdrawals) - remaining_limit, 0)
        if num_fees_to_incur > 0:
            total_fees_by_payment_type[payment_type] = num_fees_to_incur * payment_type_fee
    total_fee = sum(total_fees_by_payment_type.values())
    if total_fee > 0:
        instruction_detail = "Total fees charged for limits on payment types: "
        instruction_detail += ",".join(
            [
                fee_by_type[0] + " " + str(fee_by_type[1]) + " " + denomination
                for fee_by_type in total_fees_by_payment_type.items()
            ]
        )
        posting_instructions.extend(
            fees_fee_custom_instruction(
                customer_account_id=vault.account_id,
                denomination=denomination,
                amount=Decimal(total_fee),
                internal_account=payment_type_fee_income_account,
                instruction_details=utils_standard_instruction_details(
                    description=instruction_detail,
                    event_type="APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
                    gl_impacted=True,
                ),
            )
        )
    return posting_instructions


# Objects below have been imported from:
#    payment_type_threshold_fee.py
# md5:d8dc0686cffb83b8bc1433f7a9ad993e

payment_type_threshold_fee_PAYMENT_TYPE = "PAYMENT_TYPE"
payment_type_threshold_fee_PARAM_PAYMENT_TYPE_THRESHOLD_FEE = "payment_type_threshold_fee"
payment_type_threshold_fee_parameters = [
    Parameter(
        name=payment_type_threshold_fee_PARAM_PAYMENT_TYPE_THRESHOLD_FEE,
        level=ParameterLevel.TEMPLATE,
        description="Fees required when the payment amount exceeds the threshold for the payment type",
        display_name="Payment Type Threshold Fee",
        shape=StringShape(),
        default_value=dumps({"ATM": {"fee": "0.15", "threshold": "5000"}}),
    )
]


def payment_type_threshold_fee_apply_fees(
    vault: Any, postings: utils_PostingInstructionListAlias, denomination: str
) -> list[CustomInstruction]:
    """
    Check posting instruction details for PAYMENT_TYPE key and return any fees associated with that
    payment type if the posting value breaches the associated limit. The fee is credited to the
    account defined by the payment_type_fee_income_account parameter.
    """
    payment_type_threshold_fee_param = utils_get_parameter(
        vault, payment_type_threshold_fee_PARAM_PAYMENT_TYPE_THRESHOLD_FEE, is_json=True
    )
    payment_type_fee_income_account = utils_get_parameter(vault, "payment_type_fee_income_account")
    posting_instructions: list[CustomInstruction] = []
    for posting in postings:
        current_payment_type = posting.instruction_details.get(
            payment_type_threshold_fee_PAYMENT_TYPE
        )
        if not current_payment_type or current_payment_type not in payment_type_threshold_fee_param:
            continue
        current_payment_type_dict = payment_type_threshold_fee_param[current_payment_type]
        payment_type_fee = Decimal(current_payment_type_dict["fee"])
        payment_type_threshold = Decimal(current_payment_type_dict["threshold"])
        posting_balances = posting.balances()
        available_balance_delta = utils_get_available_balance(
            balances=posting_balances, denomination=denomination
        )
        if -payment_type_threshold > available_balance_delta:
            instruction_details = utils_standard_instruction_details(
                description=f"payment fee on withdrawal more than {payment_type_threshold} for payment with type {current_payment_type}",
                event_type="APPLY_PAYMENT_TYPE_THRESHOLD_FEE",
                gl_impacted=True,
            )
            instruction_details["payment_type"] = current_payment_type
            posting_instructions.extend(
                fees_fee_custom_instruction(
                    customer_account_id=vault.account_id,
                    denomination=denomination,
                    amount=payment_type_fee,
                    internal_account=payment_type_fee_income_account,
                    instruction_details=instruction_details,
                )
            )
    return posting_instructions


# Objects below have been imported from:
#    maximum_balance_limit.py
# md5:d63323cb515a5617b5f9d82fbd7d4579

maximum_balance_limit_PARAM_MAXIMUM_BALANCE = "maximum_balance"
maximum_balance_limit_parameters = [
    Parameter(
        name=maximum_balance_limit_PARAM_MAXIMUM_BALANCE,
        level=ParameterLevel.TEMPLATE,
        description="The maximum deposited balance amount for the account. Deposits that breach this amount will be rejected.",
        display_name="Maximum Balance Amount",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("10000"),
    )
]


def maximum_balance_limit_validate(
    *,
    vault: Any,
    postings: utils_PostingInstructionListAlias,
    denomination: str,
    balances: Optional[BalanceDefaultDict] = None,
) -> Optional[Rejection]:
    """
    Reject the posting if the deposit will cause the current balance to exceed the maximum
    permitted balance.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions that are being processed and might cause
    the account's balance to go over the limit
    :param denomination: the denomination of the account
    :param balances: latest account balances available, if not provided will be retrieved
    using the LIVE_BALANCES_BOF_ID fetcher id
    :return: rejection if the limit conditions are not met
    """
    balances = (
        balances
        or vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    )
    current_balance = utils_get_current_net_balance(balances=balances, denomination=denomination)
    deposit_proposed_amount = Decimal(0)
    for posting in postings:
        postings_balances = posting.balances()
        deposit_proposed_amount += utils_get_current_net_balance(
            balances=postings_balances, denomination=denomination
        )
    maximum_balance: Decimal = utils_get_parameter(
        vault, maximum_balance_limit_PARAM_MAXIMUM_BALANCE
    )
    if maximum_balance is not None and current_balance + deposit_proposed_amount > maximum_balance:
        return Rejection(
            message=f"Posting would exceed maximum permitted balance {maximum_balance} {denomination}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


# Objects below have been imported from:
#    maximum_daily_deposit.py
# md5:d273363f518ac0bf05299c5f8caea1a3

maximum_daily_deposit_PARAM_MAX_DAILY_DEPOSIT = "maximum_daily_deposit"
maximum_daily_deposit_parameters = [
    Parameter(
        name=maximum_daily_deposit_PARAM_MAX_DAILY_DEPOSIT,
        level=ParameterLevel.TEMPLATE,
        description="The maximum amount which can be deposited into the account from start of day to end of day.",
        display_name="Maximum Daily Deposit Amount",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("10000"),
    )
]


def maximum_daily_deposit_validate(
    *,
    vault: Any,
    hook_arguments: PrePostingHookArguments,
    denomination: str,
    effective_date_client_transactions: Optional[dict[str, ClientTransaction]] = None,
) -> Optional[Rejection]:
    """
    Reject the proposed client transactions if they cause the maximum daily deposit amount limit
    to be exceeded.
    Note: This function requires all the postings for the hook argument's effective_datetime date to
    be retrieved, since this data requirement is shared across all daily transaction limit features,
    for optimization purposes the effective_date_client_transactions argument has been marked
    as optional. This allows the caller to retrieve the data once in the pre-posting-hook and using
    it in all the daily transactions limit features the contract uses avoiding redundant data
    fetching.

    :param vault: Vault object for the account whose daily deposit limit is being validated
    :param hook_arguments: pre-posting hook argument that will contain:
    "proposed client transactions" - transactions that are being processed and need to be reviewed
    to ensure they are under the daily deposit limit
    "effective date" - date for which the limit is being calculated
    :param denomination: the denomination to be used in the validation
    :param effective_date_client_transactions: client transactions that have been processed
    during the period between <effective_date>T00:00:00 and <effective_date + 1 day>T00:00:00,
    if not provided the function will retrieve it using the EFFECTIVE_DATE_POSTINGS_FETCHER
    :return: rejection if the limit conditions are surpassed
    """
    (proposed_postings_deposited_amount, _) = client_transaction_utils_sum_client_transactions(
        cutoff_datetime=hook_arguments.effective_datetime,
        client_transactions=hook_arguments.client_transactions,
        denomination=denomination,
    )
    if proposed_postings_deposited_amount == 0:
        return None
    effective_date_client_transactions = (
        effective_date_client_transactions
        or vault.get_client_transactions(fetcher_id=fetchers_EFFECTIVE_DATE_POSTINGS_FETCHER_ID)
    )
    deposit_cutoff_datetime: datetime = hook_arguments.effective_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    (amount_deposited_actual, _) = client_transaction_utils_sum_client_transactions(
        cutoff_datetime=deposit_cutoff_datetime,
        client_transactions=effective_date_client_transactions,
        denomination=denomination,
    )
    deposit_daily_spent = proposed_postings_deposited_amount + amount_deposited_actual
    max_daily_deposit: Decimal = utils_get_parameter(
        vault=vault, name=maximum_daily_deposit_PARAM_MAX_DAILY_DEPOSIT
    )
    if deposit_daily_spent > max_daily_deposit:
        return Rejection(
            message=f"Transactions would cause the maximum daily deposit limit of {max_daily_deposit} {denomination} to be exceeded.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


# Objects below have been imported from:
#    maximum_single_deposit.py
# md5:439a93a74f353de3d9247dc5be61bd6f

maximum_single_deposit_PARAM_MAX_DEPOSIT = "maximum_deposit"
maximum_single_deposit_parameters = [
    Parameter(
        name=maximum_single_deposit_PARAM_MAX_DEPOSIT,
        level=ParameterLevel.TEMPLATE,
        description="The maximum amount that can be deposited into the account in a single transaction.",
        display_name="Maximum Deposit Amount",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("1000"),
    )
]


def maximum_single_deposit_validate(
    *, vault: Any, postings: utils_PostingInstructionListAlias, denomination: str
) -> Optional[Rejection]:
    """
    Reject the posting if the value is greater than the maximum allowed deposit.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions that are being processed and need to be reviewed
    to ensure they are under the single operation limit
    :param denomination: the denomination of the account
    :return: rejection if the limit conditions are not met
    """
    max_deposit: Decimal = utils_get_parameter(vault, maximum_single_deposit_PARAM_MAX_DEPOSIT)
    for posting in postings:
        posting_balances = posting.balances()
        deposit_value = utils_get_current_net_balance(
            balances=posting_balances, denomination=denomination
        )
        if deposit_value > 0 and max_deposit is not None and (deposit_value > max_deposit):
            return Rejection(
                message=f"Transaction amount {deposit_value} {denomination} is more than the maximum permitted deposit amount {max_deposit} {denomination}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
    return None


# Objects below have been imported from:
#    minimum_initial_deposit.py
# md5:31d956bec008b737720e0fae7049dc3d

minimum_initial_deposit_PARAM_MIN_INITIAL_DEPOSIT = "minimum_initial_deposit"
minimum_initial_deposit_parameters = [
    Parameter(
        name=minimum_initial_deposit_PARAM_MIN_INITIAL_DEPOSIT,
        level=ParameterLevel.TEMPLATE,
        description="The minimum amount for the first deposit to the account",
        display_name="Minimum Initial Deposit",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("20.00"),
    )
]


def minimum_initial_deposit_validate(
    *,
    vault: Any,
    postings: utils_PostingInstructionListAlias,
    denomination: str,
    balances: Optional[BalanceDefaultDict] = None,
) -> Optional[Rejection]:
    """
    Reject the list of postings if their net affect does not meet the minimum initial deposit limit
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions being checked to ensure they meet the initial
    deposit limit
    :param denomination: the denomination of the account
    :param balances: latest account balances available, if not provided will retrieve the latest
    balances
    :return: rejection if the limit conditions are not met
    """
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    min_initial_deposit: Decimal = utils_get_parameter(
        vault, minimum_initial_deposit_PARAM_MIN_INITIAL_DEPOSIT
    )
    available_credit_balance = utils_get_current_credit_balance(
        balances=balances, denomination=denomination
    )
    if available_credit_balance > Decimal("0"):
        return None
    posting_balances = BalanceDefaultDict()
    for posting in postings:
        posting_balances += posting.balances()
    deposit_value = utils_get_current_net_balance(
        balances=posting_balances, denomination=denomination
    )
    if Decimal(0) < deposit_value < min_initial_deposit:
        return Rejection(
            message=f"Transaction amount {deposit_value:0.2f} {denomination} is less than the minimum initial deposit amount {min_initial_deposit:0.2f} {denomination}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


# Objects below have been imported from:
#    minimum_single_deposit.py
# md5:1c82c8073f0837f129682eb520c8cf3b

minimum_single_deposit_PARAM_MIN_DEPOSIT = "minimum_deposit"
minimum_single_deposit_parameters = [
    Parameter(
        name=minimum_single_deposit_PARAM_MIN_DEPOSIT,
        level=ParameterLevel.TEMPLATE,
        description="The minimum amount that can be deposited into the account in a single transaction.",
        display_name="Minimum Deposit Amount",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("0.01"),
    )
]


def minimum_single_deposit_validate(
    *, vault: Any, postings: utils_PostingInstructionListAlias, denomination: str
) -> Optional[Rejection]:
    """
    Reject if the deposit amount does not meet the minimum deposit limit.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions being checked
    :param denomination: the denomination of the account
    :return: rejection if the limit conditions are not met
    """
    minimum_deposit: Decimal = utils_get_parameter(vault, minimum_single_deposit_PARAM_MIN_DEPOSIT)
    for posting in postings:
        posting_balances = posting.balances()
        deposit_value = utils_get_current_net_balance(
            balances=posting_balances, denomination=denomination
        )
        if minimum_deposit is not None and 0 < deposit_value < minimum_deposit:
            deposit_value = utils_round_decimal(deposit_value, 5)
            minimum_deposit = utils_round_decimal(minimum_deposit, 5)
            return Rejection(
                message=f"Transaction amount {utils_remove_exponent(deposit_value)} {denomination} is less than the minimum deposit amount {utils_remove_exponent(minimum_deposit)} {denomination}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
    return None


# Objects below have been imported from:
#    maximum_daily_withdrawal.py
# md5:4b7db5d29b76ee0f3a83bf7a04cec605

maximum_daily_withdrawal_PARAM_MAX_DAILY_WITHDRAWAL = "maximum_daily_withdrawal"
maximum_daily_withdrawal_parameters = [
    Parameter(
        name=maximum_daily_withdrawal_PARAM_MAX_DAILY_WITHDRAWAL,
        level=ParameterLevel.TEMPLATE,
        description="The maximum amount that can be withdrawn from the account from start of day to end of day.",
        display_name="Maximum Daily Withdrawal Amount",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("10000"),
    )
]


def maximum_daily_withdrawal_validate(
    *,
    vault: Any,
    hook_arguments: PrePostingHookArguments,
    denomination: str,
    effective_date_client_transactions: Optional[dict[str, ClientTransaction]] = None,
) -> Optional[Rejection]:
    """
    Reject the proposed client transactions if they would cause the maximum daily withdrawal limit
    to be exceeded.
    Note: This function requires all the postings for the hook argument's effective_datetime date to
    be retrieved, since this data requirement is shared across all daily transaction limit features,
    for optimization purposes the effective_date_client_transactions argument has been marked
    as optional. This allows the caller to retrieve the data once in the pre-posting-hook and using
    it in all the daily transactions limit features the contract uses avoiding redundant data
    fetching.

    :param vault: Vault object for the account whose daily withdrawal limit is being validated
    :param hook_arguments: pre-posting hook argument that will contain:
    "proposed client transactions" - that are being processed and need to be reviewed to ensure
    they are under the daily withdrawal limit
    "effective date" - date for which the limit is being calculated
    :param denomination: the denomination to be used in the validation
    :param effective_date_client_transactions: client transactions that have been processed
    during the period between <effective_date>T00:00:00 and <effective_date + 1 day>T00:00:00,
    if not provided the function will retrieve it using the EFFECTIVE_DATE_POSTINGS_FETCHER
    :return: rejection if the limit conditions are surpassed
    """
    (_, proposed_postings_withdrawn_amount) = client_transaction_utils_sum_client_transactions(
        cutoff_datetime=hook_arguments.effective_datetime,
        client_transactions=hook_arguments.client_transactions,
        denomination=denomination,
    )
    if proposed_postings_withdrawn_amount == 0:
        return None
    effective_date_client_transactions = (
        effective_date_client_transactions
        or vault.get_client_transactions(fetcher_id=fetchers_EFFECTIVE_DATE_POSTINGS_FETCHER_ID)
    )
    withdrawal_cutoff_datetime: datetime = hook_arguments.effective_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    (_, amount_withdrawn_actual) = client_transaction_utils_sum_client_transactions(
        cutoff_datetime=withdrawal_cutoff_datetime,
        client_transactions=effective_date_client_transactions,
        denomination=denomination,
    )
    withdrawal_daily_spent = proposed_postings_withdrawn_amount + amount_withdrawn_actual
    max_daily_withdrawal: Decimal = utils_get_parameter(
        vault=vault, name=maximum_daily_withdrawal_PARAM_MAX_DAILY_WITHDRAWAL
    )
    if withdrawal_daily_spent > max_daily_withdrawal:
        return Rejection(
            message=f"Transactions would cause the maximum daily withdrawal limit of {max_daily_withdrawal} {denomination} to be exceeded.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


# Objects below have been imported from:
#    maximum_daily_withdrawal_by_transaction_type.py
# md5:ad18ff61dde49e18e678295a7d90560a

maximum_daily_withdrawal_by_transaction_type_PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION = (
    "daily_withdrawal_limit_by_transaction_type"
)
maximum_daily_withdrawal_by_transaction_type_PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT = (
    "tiered_daily_withdrawal_limits"
)
maximum_daily_withdrawal_by_transaction_type_parameters = [
    Parameter(
        name=maximum_daily_withdrawal_by_transaction_type_PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION,
        level=ParameterLevel.INSTANCE,
        description="The maximum amount that can be withdrawn from an account over the current day by transaction type.",
        display_name="Maximum Daily Withdrawal Amount",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        shape=StringShape(),
        default_value=dumps({"ATM": "1000"}),
    ),
    Parameter(
        name=maximum_daily_withdrawal_by_transaction_type_PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT,
        level=ParameterLevel.TEMPLATE,
        description="The daily withdrawal limits based on account tier. It defines the upper withdrawal limit that cannot be exceeded by Maximum Daily Withdrawal Amount.If above it, the contract will consider the tiered limit as valid",
        display_name="Tiered Daily Withdrawal Limits",
        shape=StringShape(),
        default_value=dumps(
            {
                "UPPER_TIER": {"ATM": "5000"},
                "MIDDLE_TIER": {"ATM": "2000"},
                "LOWER_TIER": {"ATM": "1500"},
            }
        ),
    ),
]
maximum_daily_withdrawal_by_transaction_type_INSTRUCTION_DETAILS_KEY = "TRANSACTION_TYPE"


def maximum_daily_withdrawal_by_transaction_type_validate(
    *,
    vault: Any,
    hook_arguments: PrePostingHookArguments,
    denomination: Optional[str] = None,
    effective_date_client_transactions: Optional[dict[str, ClientTransaction]] = None,
) -> Optional[Rejection]:
    """
    Reject the proposed client transactions if they would cause the maximum daily withdrawal limit
    by transaction type to be exceeded.
    Note: This function requires all the postings for the effective date to be retrieved, since
    this data requirement is shared across all daily transaction limit features, for optimization
    purposes the effective_datetime_client_transaction argument has been marked as optional.
    This allows the caller to retrieve the data once in the pre-posting-hook and using it in all
    the daily transactions limit features the contract uses avoiding redundant data fetching.

    :param vault: Vault object for the account whose daily withdrawal limit is being validated
    :param denomination: the denomination to be used in the validation
    :param hook_arguments: pre-posting hook argument that will contain:
    "proposed client transactions" that are being processed and need to be reviewed to ensure they
    are under the daily withdrawal limit
    "effective date": date for which the limit is being calculated
    :param effective_date_client_transactions: client transactions that have been processed
    during the period between <effective_date>T00:00:00 and <effective_date + 1 day>T00:00:00,
    if not provided the function will retrieve it using the EFFECTIVE_DATE_POSTINGS_FETCHER
    :return: rejection if the limit conditions are surpassed
    """
    account_tier = account_tiers_get_account_tier(vault)
    tiered_daily_limits: dict[str, dict[str, str]] = utils_get_parameter(
        vault,
        name=maximum_daily_withdrawal_by_transaction_type_PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT,
        is_json=True,
    )
    daily_limit_by_transaction = utils_get_parameter(
        vault,
        name=maximum_daily_withdrawal_by_transaction_type_PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION,
        is_json=True,
    )
    if denomination is None:
        denomination = utils_get_parameter(vault, name="denomination")
    if (
        not tiered_daily_limits
        and (not daily_limit_by_transaction)
        or not hook_arguments.client_transactions
    ):
        return None
    limit_per_transaction_type: dict[str, str] = (
        maximum_daily_withdrawal_by_transaction_type__get_limit_per_transaction_type(
            tiered_daily_limits[account_tier], daily_limit_by_transaction
        )
        if account_tier in tiered_daily_limits.keys()
        else daily_limit_by_transaction
    )
    effective_date_client_transactions = (
        effective_date_client_transactions
        or vault.get_client_transactions(fetcher_id=fetchers_EFFECTIVE_DATE_POSTINGS_FETCHER_ID)
    )
    for (transaction_type, transaction_type_limit) in limit_per_transaction_type.items():
        proposed_client_transactions = client_transaction_utils_filter_client_transactions(
            client_transactions=hook_arguments.client_transactions,
            client_transaction_ids_to_ignore=[""],
            denomination=denomination,
            key=maximum_daily_withdrawal_by_transaction_type_INSTRUCTION_DETAILS_KEY,
            value=transaction_type,
        )
        if not proposed_client_transactions:
            continue
        (_, proposed_postings_withdrawn_amount) = client_transaction_utils_sum_client_transactions(
            cutoff_datetime=hook_arguments.effective_datetime,
            client_transactions=proposed_client_transactions,
            denomination=denomination,
        )
        if proposed_postings_withdrawn_amount == 0:
            continue
        filtered_effective_date_client_transactions = (
            client_transaction_utils_filter_client_transactions(
                client_transactions=effective_date_client_transactions,
                client_transaction_ids_to_ignore=[""],
                denomination=denomination,
                key=maximum_daily_withdrawal_by_transaction_type_INSTRUCTION_DETAILS_KEY,
                value=transaction_type,
            )
        )
        (_, amount_withdrawn_actual) = client_transaction_utils_sum_client_transactions(
            cutoff_datetime=hook_arguments.effective_datetime.replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
            client_transactions=filtered_effective_date_client_transactions,
            denomination=denomination,
        )
        final_withdrawal_daily_spend = proposed_postings_withdrawn_amount + amount_withdrawn_actual
        if final_withdrawal_daily_spend > Decimal(transaction_type_limit):
            return Rejection(
                message=f"Transactions would cause the maximum daily {transaction_type} withdrawal limit of {transaction_type_limit} {denomination} to be exceeded.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
    return None


def maximum_daily_withdrawal_by_transaction_type__get_limit_per_transaction_type(
    tiered_limit_dict: dict[str, str], daily_limit_dict: dict[str, str]
) -> dict[str, str]:
    limit_per_transaction_type: dict[str, str] = tiered_limit_dict
    for (transaction_type, limit) in daily_limit_dict.items():
        limit_per_transaction_type[transaction_type] = (
            limit
            if transaction_type not in limit_per_transaction_type.keys()
            else str(min(Decimal(limit), Decimal(limit_per_transaction_type[transaction_type])))
        )
    return limit_per_transaction_type


# Objects below have been imported from:
#    maximum_single_withdrawal.py
# md5:438aed27c8737fe9c00e4db7080f9c8f

maximum_single_withdrawal_PARAM_MAX_WITHDRAWAL = "maximum_withdrawal"
maximum_single_withdrawal_parameters = [
    Parameter(
        name=maximum_single_withdrawal_PARAM_MAX_WITHDRAWAL,
        level=ParameterLevel.TEMPLATE,
        description="The maximum amount that can be withdrawn from the account in a single transaction.",
        display_name="Maximum Withdrawal Amount",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("10000"),
    )
]


def maximum_single_withdrawal_validate(
    *, vault: Any, postings: utils_PostingInstructionListAlias, denomination: str
) -> Optional[Rejection]:
    """
    Reject if any posting amount is greater than the maximum allowed withdrawal limit.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions that are being processed and need to be reviewed
    to ensure they are under the single operation limit
    :param denomination: the denomination of the account
    :return: rejection if the limit conditions are not met
    """
    max_withdrawal: Decimal = utils_get_parameter(
        vault, maximum_single_withdrawal_PARAM_MAX_WITHDRAWAL
    )
    for posting in postings:
        posting_value = utils_get_available_balance(
            balances=posting.balances(), denomination=denomination
        )
        if posting_value > 0:
            continue
        elif abs(posting_value) > max_withdrawal:
            return Rejection(
                message=f"Transaction amount {abs(posting_value)} {denomination} is greater than the maximum withdrawal amount {max_withdrawal} {denomination}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
    return None


# Objects below have been imported from:
#    maximum_withdrawal_by_payment_type.py
# md5:73ea29085f8e2d5a600a29bea95e5929

maximum_withdrawal_by_payment_type_PAYMENT_TYPE = "PAYMENT_TYPE"
maximum_withdrawal_by_payment_type_PARAM_MAX_WITHDRAWAL_BY_TYPE = "maximum_payment_type_withdrawal"
maximum_withdrawal_by_payment_type_parameters = [
    Parameter(
        name=maximum_withdrawal_by_payment_type_PARAM_MAX_WITHDRAWAL_BY_TYPE,
        level=ParameterLevel.TEMPLATE,
        description="The maximum single withdrawal allowed for each payment type.",
        display_name="Payment Type Limits",
        shape=StringShape(),
        default_value=dumps({"ATM": "30000"}),
    )
]


def maximum_withdrawal_by_payment_type_validate(
    *, vault: Any, postings: utils_PostingInstructionListAlias, denomination: str
) -> Optional[Rejection]:
    """
    Reject the posting if the withdrawal value exceeds the PAYMENT_TYPE limit.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions that are being processed and need to be reviewed
    to ensure they are under the limit by payment type
    :param denomination: the denomination of the account
    :return: rejection if the limit conditions are not met
    """
    max_withdrawal_by_payment_type: dict[str, str] = utils_get_parameter(
        vault, maximum_withdrawal_by_payment_type_PARAM_MAX_WITHDRAWAL_BY_TYPE, is_json=True
    )
    for posting in postings:
        payment_type = posting.instruction_details.get(
            maximum_withdrawal_by_payment_type_PAYMENT_TYPE
        )
        if payment_type:
            if payment_type in max_withdrawal_by_payment_type:
                withdrawal_limit = Decimal(max_withdrawal_by_payment_type[payment_type])
                posting_value = utils_get_available_balance(
                    balances=posting.balances(), denomination=denomination
                )
                if posting_value > 0:
                    continue
                elif withdrawal_limit < abs(posting_value):
                    return Rejection(
                        message=f"Transaction amount {abs(posting_value):0.2f} {denomination} is more than the maximum withdrawal amount {withdrawal_limit} {denomination} allowed for the the payment type {payment_type}.",
                        reason_code=RejectionReason.AGAINST_TNC,
                    )
            else:
                continue
    return None


# Objects below have been imported from:
#    minimum_balance_by_tier.py
# md5:484f4774031a54467334b581637efe15

minimum_balance_by_tier_PARAM_MIN_BALANCE_THRESHOLD = "tiered_minimum_balance_threshold"
minimum_balance_by_tier_parameters = [
    Parameter(
        name=minimum_balance_by_tier_PARAM_MIN_BALANCE_THRESHOLD,
        level=ParameterLevel.TEMPLATE,
        description="The minimum balance allowed for each account tier.",
        display_name="Minimum Balance Threshold",
        shape=StringShape(),
        default_value=dumps({"STANDARD": "10"}),
    )
]


def minimum_balance_by_tier_validate(
    *,
    vault: Any,
    postings: utils_PostingInstructionListAlias,
    denomination: str,
    balances: Optional[BalanceDefaultDict] = None,
) -> Optional[Rejection]:
    """
    Reject if the net value of the posting instruction batch results in the account balance falling
    below the minimum threshold for the account tier.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of posting instructions that are being processed
    to ensure that the balance of the account still meets the minimum balance limit
    :param denomination: the denomination of the account
    :param balances: latest account balances available, if not provided will be retrieved
    using the LIVE_BALANCES_BOF_ID fetcher id
    :return: rejection if the minimum balance limit conditions are not met
    """
    balances = (
        balances
        or vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    )
    available_balance = utils_get_available_balance(balances=balances, denomination=denomination)
    proposed_amount = sum(
        (
            utils_get_available_balance(balances=posting.balances(), denomination=denomination)
            for posting in postings
        )
    )
    min_balance_threshold_by_tier: dict[str, str] = utils_get_parameter(
        vault, minimum_balance_by_tier_PARAM_MIN_BALANCE_THRESHOLD, is_json=True
    )
    current_account_tier = account_tiers_get_account_tier(vault)
    min_balance = account_tiers_get_tiered_parameter_value_based_on_account_tier(
        tiered_parameter=min_balance_threshold_by_tier, tier=current_account_tier, convert=Decimal
    )
    if available_balance + proposed_amount < min_balance:
        return Rejection(
            message=f"Transaction amount {proposed_amount} {denomination} will result in the account balance falling below the minimum permitted of {min_balance} {denomination}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


# Objects below have been imported from:
#    accruals.py
# md5:becbe7f07a49ad9560c9d05985a2e3ab


def accruals_accrual_custom_instruction(
    customer_account: str,
    customer_address: str,
    denomination: str,
    amount: Decimal,
    internal_account: str,
    payable: bool,
    instruction_details: Optional[dict[str, str]] = None,
    reversal: bool = False,
) -> list[CustomInstruction]:
    """
    Create a Custom Instruction containing customer and internal account postings for accruing a
    charge.
    :param customer_account: the customer account id to use
    :param customer_address: the address to use on the customer account
    :param denomination: the denomination of the accrual
    :param amount: the accrual amount. If this is amount is <= 0 an empty list is returned
    :param internal_account: the internal account id to use. The default address is always
    used on this account
    :param payable: set to True if accruing a payable charge, or False for a receivable charge
    :param instruction_details: instruction details to add to the postings
    Useful if more than one accrual affects a given balance (e.g. un-netted tiered interest)
    :param reversal: set to True if reversing the accrual, or False otherwise
    :return: Custom instructions to accrue interest, if required
    """
    if amount <= 0:
        return []
    postings = accruals_accrual_postings(
        customer_account=customer_account,
        denomination=denomination,
        amount=amount,
        internal_account=internal_account,
        customer_address=customer_address,
        payable=payable,
        reversal=reversal,
    )
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


def accruals_accrual_postings(
    customer_account: str,
    customer_address: str,
    denomination: str,
    amount: Decimal,
    internal_account: str,
    payable: bool,
    reversal: bool = False,
) -> list[Posting]:
    """
    Create customer and internal account postings for accruing a charge.
    :param customer_account: the customer account id to use
    :param customer_address: the address to use on the customer account
    :param denomination: the denomination of the accrual
    :param amount: the accrual amount. If this is amount is <= 0 an empty list is returned.
    :param internal_account: the internal account id to use. The default address is always
    used on this account
    :param payable: set to True if accruing a payable charge, or False for a receivable charge
    :param reversal: set to True if reversing the accrual, or False otherwise
    :return: the accrual postings
    """
    if amount <= 0:
        return []
    if payable and reversal or (not payable and (not reversal)):
        debit_account = customer_account
        debit_address = customer_address
        credit_account = internal_account
        credit_address = DEFAULT_ADDRESS
    else:
        debit_account = internal_account
        debit_address = DEFAULT_ADDRESS
        credit_account = customer_account
        credit_address = customer_address
    return [
        Posting(
            credit=True,
            amount=amount,
            denomination=denomination,
            account_id=credit_account,
            account_address=credit_address,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=False,
            amount=amount,
            denomination=denomination,
            account_id=debit_account,
            account_address=debit_address,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
    ]


def accruals_accrual_application_custom_instruction(
    customer_account: str,
    denomination: str,
    application_amount: Decimal,
    accrual_amount: Decimal,
    instruction_details: dict[str, str],
    accrual_customer_address: str,
    accrual_internal_account: str,
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
    postings = accruals_accrual_application_postings(
        customer_account=customer_account,
        denomination=denomination,
        application_amount=application_amount,
        accrual_amount=accrual_amount,
        accrual_customer_address=accrual_customer_address,
        accrual_internal_account=accrual_internal_account,
        application_customer_address=application_customer_address,
        application_internal_account=application_internal_account,
        payable=payable,
    )
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


def accruals_accrual_application_postings(
    customer_account: str,
    denomination: str,
    application_amount: Decimal,
    accrual_amount: Decimal,
    accrual_customer_address: str,
    accrual_internal_account: str,
    application_customer_address: str,
    application_internal_account: str,
    payable: bool,
) -> list[Posting]:
    """
    Create customer and internal account postings for applying an accrued charge, including any
    postings required to zero the accrued interest remainders.
    :param customer_account: the customer account id to use
    :param denomination: the denomination of the application
    :param application_amount: the amount to apply. If <= 0 an empty list is returned
    :param accrual_amount: the amount accrued prior to application. This will be zeroed out
    :param accrual_customer_address: the address to use on the customer account for accruals
    :param accrual_internal_account: the internal account id to use for accruals. The default
     address is always used on this account
    :param application_customer_address: the address to use on the customer account for application
    :param application_internal_account: the internal account id to use for application.
    The default address is always used on this account
    :param payable: set to True if applying a payable charge, or False for a receivable charge
    :return: the accrual application postings
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
    postings += accruals_accrual_postings(
        customer_account=customer_account,
        customer_address=accrual_customer_address,
        denomination=denomination,
        amount=accrual_amount,
        internal_account=accrual_internal_account,
        payable=payable,
        reversal=True,
    )
    return postings


# Objects below have been imported from:
#    tiered_profit_accrual.py
# md5:ac104b00774095785ec71dbff0af277f

tiered_profit_accrual_ACCRUAL_EVENT = "ACCRUE_PROFIT"
tiered_profit_accrual_ACCRUED_PROFIT_PAYABLE = "ACCRUED_PROFIT_PAYABLE"
tiered_profit_accrual_PROFIT_ACCRUAL_PREFIX = "profit_accrual"
tiered_profit_accrual_PARAM_ACCRUAL_PRECISION = "accrual_precision"
tiered_profit_accrual_PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT = "accrued_profit_payable_account"
tiered_profit_accrual_PARAM_DAYS_IN_YEAR = "days_in_year"
tiered_profit_accrual_PARAM_PROFIT_ACCRUAL_HOUR = (
    f"{tiered_profit_accrual_PROFIT_ACCRUAL_PREFIX}_hour"
)
tiered_profit_accrual_PARAM_PROFIT_ACCRUAL_MINUTE = (
    f"{tiered_profit_accrual_PROFIT_ACCRUAL_PREFIX}_minute"
)
tiered_profit_accrual_PARAM_PROFIT_ACCRUAL_SECOND = (
    f"{tiered_profit_accrual_PROFIT_ACCRUAL_PREFIX}_second"
)
tiered_profit_accrual_PARAM_TIERED_PROFIT_RATES = "tiered_profit_rates"
tiered_profit_accrual_days_in_year_parameter = Parameter(
    name=tiered_profit_accrual_PARAM_DAYS_IN_YEAR,
    shape=UnionShape(
        items=[
            UnionItem(key="actual", display_name="Actual"),
            UnionItem(key="366", display_name="366"),
            UnionItem(key="365", display_name="365"),
            UnionItem(key="360", display_name="360"),
        ]
    ),
    level=ParameterLevel.TEMPLATE,
    description='The days in the year for profit accrual calculation. Valid values are "actual", "366", "365", "360"',
    display_name="Profit Accrual Days In Year",
    default_value=UnionItemValue(key="365"),
)
tiered_profit_accrual_accrual_precision_parameter = Parameter(
    name=tiered_profit_accrual_PARAM_ACCRUAL_PRECISION,
    level=ParameterLevel.TEMPLATE,
    description="Precision needed for profit accruals.",
    display_name="Profit Accrual Precision",
    shape=NumberShape(min_value=0, max_value=15, step=1),
    default_value=Decimal(5),
)
tiered_profit_accrual_schedule_parameters = [
    Parameter(
        name=tiered_profit_accrual_PARAM_PROFIT_ACCRUAL_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which profit is accrued.",
        display_name="Profit Accrual Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=tiered_profit_accrual_PARAM_PROFIT_ACCRUAL_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which profit is accrued.",
        display_name="Profit Accrual Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=tiered_profit_accrual_PARAM_PROFIT_ACCRUAL_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which profit is accrued.",
        display_name="Profit Accrual Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
]
tiered_profit_accrual_tiered_parameter = Parameter(
    name=tiered_profit_accrual_PARAM_TIERED_PROFIT_RATES,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    display_name="Tiered Gross Profit Rate",
    description="Tiered profit rates applicable to the main denomination as determined by both the account tier and gross balance. The account tier is determined by flags and is mapped to a dictionary of gross balance to profit rate",
    default_value=dumps(
        {
            "STANDARD": {
                "0.00": "0.01",
                "1000.00": "0.02",
                "3000.00": "0.035",
                "7500.00": "0.05",
                "10000.00": "0.06",
            }
        }
    ),
)
tiered_profit_accrual_accrued_profit_payable_account_parameter = Parameter(
    name=tiered_profit_accrual_PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for accrued profit payable balance.",
    display_name="Accrued Profit Payable Account",
    shape=AccountIdShape(),
    default_value=tiered_profit_accrual_ACCRUED_PROFIT_PAYABLE,
)
tiered_profit_accrual_all_parameters = [
    tiered_profit_accrual_accrual_precision_parameter,
    tiered_profit_accrual_accrued_profit_payable_account_parameter,
    tiered_profit_accrual_days_in_year_parameter,
    tiered_profit_accrual_tiered_parameter,
    *tiered_profit_accrual_schedule_parameters,
]


def tiered_profit_accrual_event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=tiered_profit_accrual_ACCRUAL_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{tiered_profit_accrual_ACCRUAL_EVENT}_AST"],
        )
    ]


def tiered_profit_accrual_scheduled_events(
    vault: Any, start_datetime: datetime
) -> dict[str, ScheduledEvent]:
    return {
        tiered_profit_accrual_ACCRUAL_EVENT: utils_daily_scheduled_event(
            vault=vault,
            start_datetime=start_datetime,
            parameter_prefix=tiered_profit_accrual_PROFIT_ACCRUAL_PREFIX,
        )
    }


def tiered_profit_accrual_accrue_profit(
    *,
    vault: Any,
    effective_datetime: datetime,
    account_tier: str,
    accrual_address: str = tiered_profit_accrual_ACCRUED_PROFIT_PAYABLE,
    account_type: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Creates the posting instructions to accrue profit on the balances specified by
    the denomination and capital addresses parameters
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param effective_datetime: the effective date to retrieve capital balances to accrue on
    :param accrual_address: balance address for the accrual amount to be assigned
    :return: the accrual posting custom instructions
    """
    denomination = utils_get_parameter(vault, name="denomination")
    accrued_profit_payable_account: str = utils_get_parameter(
        vault, name=tiered_profit_accrual_PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT
    )
    days_in_year: str = utils_get_parameter(
        vault, name=tiered_profit_accrual_PARAM_DAYS_IN_YEAR, is_union=True
    )
    rounding_precision: int = utils_get_parameter(
        vault, name=tiered_profit_accrual_PARAM_ACCRUAL_PRECISION
    )
    tiered_rates: dict[str, str] = utils_get_parameter(
        vault,
        name=tiered_profit_accrual_PARAM_TIERED_PROFIT_RATES,
        at_datetime=effective_datetime,
        is_json=True,
    ).get(account_tier, {})
    if not tiered_rates:
        return []
    (amount_to_accrue, instruction_detail) = tiered_profit_accrual_get_tiered_accrual_amount(
        effective_balance=tiered_profit_accrual_get_accrual_capital(vault),
        effective_datetime=effective_datetime,
        tiered_profit_rates=tiered_rates,
        days_in_year=days_in_year,
        precision=rounding_precision,
    )
    if account_type is None:
        account_type = ""
    instruction_details = utils_standard_instruction_details(
        description=instruction_detail.strip(),
        event_type=f"{tiered_profit_accrual_ACCRUAL_EVENT}",
        account_type=account_type,
    )
    if amount_to_accrue > 0:
        return accruals_accrual_custom_instruction(
            customer_account=vault.account_id,
            customer_address=accrual_address,
            denomination=denomination,
            amount=amount_to_accrue,
            internal_account=accrued_profit_payable_account,
            payable=True,
            instruction_details=instruction_details,
        )
    else:
        return []


def tiered_profit_accrual_get_tiered_accrual_amount(
    *,
    effective_balance: Decimal,
    effective_datetime: datetime,
    tiered_profit_rates: dict[str, str],
    days_in_year: str,
    precision: int = 5,
) -> tuple[Decimal, str]:
    """
    Calculate the amount to accrue on each balance portion by tier rate (to defined precision).
    Provide instruction details highlighting the breakdown of the tiered accrual.
    :param effective_balance: balance to accrue on
    :param effective_datetime: the date to accrue as-of. This will affect the conversion of yearly
    to daily rates if `days_in_year` is set to `actual`
    :param tiered_profit_rates: tiered profit rates parameter
    :param days_in_year: days in year parameter
    :param accrual_precision: accrual precision parameter
    :return: rounded accrual_amount and instruction_details
    """
    daily_accrual_amount = Decimal("0")
    instruction_detail = ""
    tiered_profit_rates = dict(sorted(tiered_profit_rates.items(), key=lambda x: x[1]))
    for (index, (tier_min, tier_rate)) in enumerate(tiered_profit_rates.items()):
        rate = Decimal(tier_rate)
        tier_max = tiered_profit_accrual_determine_tier_max(list(tiered_profit_rates.keys()), index)
        tier_balances = tiered_profit_accrual_determine_tier_balance(
            effective_balance=effective_balance, tier_min=Decimal(tier_min), tier_max=tier_max
        )
        if tier_balances != Decimal(0):
            daily_rate = utils_yearly_to_daily_rate(
                effective_date=effective_datetime, yearly_rate=rate, days_in_year=days_in_year
            )
            daily_accrual_amount += tier_balances * daily_rate
            instruction_detail = f"{instruction_detail}Accrual on {tier_balances:.2f} at annual rate of {rate * 100:.2f}%. "
    return (
        utils_round_decimal(amount=daily_accrual_amount, decimal_places=precision),
        instruction_detail,
    )


def tiered_profit_accrual_determine_tier_max(
    tier_range_list: list[str], index: int
) -> Optional[Decimal]:
    return Decimal(tier_range_list[index + 1]) if index + 1 < len(tier_range_list) else None


def tiered_profit_accrual_determine_tier_balance(
    effective_balance: Decimal,
    tier_min: Optional[Decimal] = None,
    tier_max: Optional[Decimal] = None,
) -> Decimal:
    """
    Determines a tier's balance based on min and max. Min and max must be of same sign or
    zero is returned (use Decimal("-0") if required). If neither are provided, zero is returned
    :param tier_min: the minimum balance included in the tier. Any amount below is excluded.
    Defaults to 0 if tier_max is +ve or unbounded if tier_max is -ve
    :param tier_max: the maximum balance included in the tier, exclusive. Any amount greater is
    excluded. Defaults to Decimal("-0") if tier_min is -ve or unbounded if tier_min is +ve
    :param effective_balance: the balance to check against the tier min/max
    :return: the portion of the effective balance that is included in the tier
    """
    if tier_min is None:
        if tier_max is None:
            return Decimal("0")
        if tier_max.is_signed():
            tier_min = effective_balance
        else:
            tier_min = Decimal("0")
    if tier_max is None:
        if tier_min.is_signed():
            tier_max = Decimal("-0")
        else:
            tier_max = effective_balance
    if tier_max.is_signed() ^ tier_min.is_signed():
        return Decimal("0")
    if tier_max.is_signed():
        if tier_min >= tier_max:
            return Decimal("0")
        return max(effective_balance, tier_min) - max(effective_balance, tier_max)
    else:
        if tier_max <= tier_min:
            return Decimal("0")
        return min(effective_balance, tier_max) - min(effective_balance, tier_min)


def tiered_profit_accrual_get_accrual_capital(
    vault: Any, *, capital_addresses: Optional[list[str]] = None
) -> Decimal:
    """
    Calculates the sum of balances that will be used to accrue profit on.
    We should check the last possible time capital could accrue
    (i.e. at 23:59:59.999999 on the day before effective_datetime)
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param capital_addresses: list of balance addresses that will be summed up to provide
    the amount to accrue profit on. Defaults to the DEFAULT_ADDRESS
    :return: the sum of balances on which profit will be accrued on
    """
    denomination = utils_get_parameter(vault, name="denomination")
    balances = vault.get_balances_observation(fetcher_id=fetchers_EOD_FETCHER_ID).balances
    accrual_balance = utils_sum_balances(
        balances=balances,
        addresses=capital_addresses or [DEFAULT_ADDRESS],
        denomination=denomination,
    )
    return accrual_balance if accrual_balance > 0 else Decimal(0)


def tiered_profit_accrual_get_accrued_profit(
    *,
    balances: BalanceDefaultDict,
    denomination: str,
    accrued_profit_address: str = tiered_profit_accrual_ACCRUED_PROFIT_PAYABLE,
) -> Decimal:
    """
    Retrieves the existing balance for accrued profit at a specific time
    :param balances: the balances to sum accrued profit
    :param denomination: the denomination of the capital balances and the profit accruals
    :param accrued_profit_address: the address name in which we are storing the accrued profit
    :return: the value of the balance at the requested time
    """
    return utils_balance_at_coordinates(
        balances=balances, address=accrued_profit_address, denomination=denomination
    )


def tiered_profit_accrual_get_profit_reversal_postings(
    *,
    vault: Any,
    accrued_profit_address: str = tiered_profit_accrual_ACCRUED_PROFIT_PAYABLE,
    event_name: str,
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
    accrued_profit_payable_account: str = utils_get_parameter(
        vault, name=tiered_profit_accrual_PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT
    )
    if denomination is None:
        denomination = str(utils_get_parameter(vault, name="denomination"))
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_EOD_FETCHER_ID).balances
    accrued_profit = tiered_profit_accrual_get_accrued_profit(
        balances=balances, denomination=denomination, accrued_profit_address=accrued_profit_address
    )
    instruction_details = utils_standard_instruction_details(
        description=f"Reversal of accrued profit of value {accrued_profit} {denomination} due to account closure.",
        event_type=f"{event_name}",
        gl_impacted=True,
        account_type=account_type or "",
    )
    if accrued_profit > 0:
        return accruals_accrual_custom_instruction(
            customer_account=vault.account_id,
            customer_address=accrued_profit_address,
            denomination=denomination,
            amount=accrued_profit,
            internal_account=accrued_profit_payable_account,
            payable=True,
            instruction_details=instruction_details,
            reversal=True,
        )
    else:
        return []


# Objects below have been imported from:
#    profit_application.py
# md5:149ec1c2e01bb85079b70a3b00bac833

profit_application_APPLICATION_EVENT = "APPLY_PROFIT"
profit_application_ACCRUED_PROFIT_PAYABLE = tiered_profit_accrual_ACCRUED_PROFIT_PAYABLE
profit_application_PROFIT_APPLICATION_PREFIX = "profit_application"
profit_application_PARAM_PROFIT_APPLICATION_DAY = (
    f"{profit_application_PROFIT_APPLICATION_PREFIX}_day"
)
profit_application_PARAM_PROFIT_APPLICATION_FREQUENCY = (
    f"{profit_application_PROFIT_APPLICATION_PREFIX}_frequency"
)
profit_application_PARAM_PROFIT_APPLICATION_HOUR = (
    f"{profit_application_PROFIT_APPLICATION_PREFIX}_hour"
)
profit_application_PARAM_PROFIT_APPLICATION_MINUTE = (
    f"{profit_application_PROFIT_APPLICATION_PREFIX}_minute"
)
profit_application_PARAM_PROFIT_APPLICATION_SECOND = (
    f"{profit_application_PROFIT_APPLICATION_PREFIX}_second"
)
profit_application_schedule_params = [
    Parameter(
        name=profit_application_PARAM_PROFIT_APPLICATION_DAY,
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=ParameterLevel.INSTANCE,
        description="The day of the month on which profit is applied. If day does not exist in application month, applies on last day of month.",
        display_name="Profit Application Day",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name=profit_application_PARAM_PROFIT_APPLICATION_FREQUENCY,
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
        name=profit_application_PARAM_PROFIT_APPLICATION_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which profit is applied.",
        display_name="Profit Application Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=profit_application_PARAM_PROFIT_APPLICATION_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which profit is applied.",
        display_name="Profit Application Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=profit_application_PARAM_PROFIT_APPLICATION_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which profit is applied.",
        display_name="Profit Application Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=1,
    ),
]
profit_application_PARAM_APPLICATION_PRECISION = "application_precision"
profit_application_PARAM_PROFIT_PAID_ACCOUNT = "profit_paid_account"
profit_application_parameters = [
    Parameter(
        name=profit_application_PARAM_APPLICATION_PRECISION,
        level=ParameterLevel.TEMPLATE,
        description="Precision needed for profit applications.",
        display_name="Profit Application Precision",
        shape=NumberShape(min_value=0, max_value=15, step=1),
        default_value=2,
    ),
    Parameter(
        name=profit_application_PARAM_PROFIT_PAID_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for profit paid.",
        display_name="Profit Paid Account",
        shape=AccountIdShape(),
        default_value="APPLIED_PROFIT_PAID",
    ),
    *profit_application_schedule_params,
]


def profit_application_event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=profit_application_APPLICATION_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{profit_application_APPLICATION_EVENT}_AST"
            ],
        )
    ]


def profit_application_scheduled_events(
    *, vault: Any, start_datetime: datetime
) -> dict[str, ScheduledEvent]:
    """
    Creates list of execution schedules for profit application
    :param vault: Vault object to retrieve application frequency and schedule params
    :param start_datetime: date to start schedules from e.g. account creation or loan start date
    :return: dict of profit application scheduled events
    """
    application_frequency: str = utils_get_parameter(
        vault, name=profit_application_PARAM_PROFIT_APPLICATION_FREQUENCY, is_union=True
    )
    schedule_day = int(
        utils_get_parameter(vault, name=profit_application_PARAM_PROFIT_APPLICATION_DAY)
    )
    (schedule_hour, schedule_minute, schedule_second) = utils_get_schedule_time_from_parameters(
        vault=vault, parameter_prefix=profit_application_PROFIT_APPLICATION_PREFIX
    )
    calendar_events = vault.get_calendar_events(calendar_ids=["&{PUBLIC_HOLIDAYS}"])
    next_datetime = utils_get_next_schedule_date_calendar_aware(
        start_datetime=start_datetime,
        schedule_frequency=application_frequency,
        intended_day=schedule_day,
        calendar_events=calendar_events,
    )
    modified_expression = utils_one_off_schedule_expression(
        next_datetime
        + relativedelta(hour=schedule_hour, minute=schedule_minute, second=schedule_second)
    )
    scheduled_event = ScheduledEvent(start_datetime=start_datetime, expression=modified_expression)
    return {profit_application_APPLICATION_EVENT: scheduled_event}


def profit_application_apply_profit(
    *,
    vault: Any,
    accrual_address: str = profit_application_ACCRUED_PROFIT_PAYABLE,
    account_type: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Creates the posting instructions to consolidate accrued profit.
    Debit the rounded amount from the customer accrued address and credit the internal account
    Debit the rounded amount from the internal account to the customer applied address
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param accrual_address: the address to check for profit that has accumulated
    :return: the accrual posting instructions
    """
    accrued_profit_payable_account: str = utils_get_parameter(
        vault, name=tiered_profit_accrual_PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT
    )
    profit_paid_account: str = utils_get_parameter(
        vault, name=profit_application_PARAM_PROFIT_PAID_ACCOUNT
    )
    application_precision: int = utils_get_parameter(
        vault, name=profit_application_PARAM_APPLICATION_PRECISION
    )
    denomination: str = utils_get_parameter(vault, name="denomination")
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_EOD_FETCHER_ID
    ).balances
    amount_accrued = utils_balance_at_coordinates(
        balances=balances, address=accrual_address, denomination=denomination
    )
    rounded_accrual = utils_round_decimal(amount_accrued, application_precision)
    posting_instructions: list[CustomInstruction] = []
    if amount_accrued > 0:
        if account_type is None:
            account_type = ""
        posting_instructions.extend(
            accruals_accrual_application_custom_instruction(
                customer_account=vault.account_id,
                denomination=denomination,
                application_amount=abs(rounded_accrual),
                accrual_amount=abs(amount_accrued),
                instruction_details=utils_standard_instruction_details(
                    description=f"Apply {rounded_accrual} {denomination} profit of {amount_accrued} rounded to {application_precision} and consolidate {amount_accrued} {denomination} to {vault.account_id}",
                    event_type=profit_application_APPLICATION_EVENT,
                    gl_impacted=True,
                    account_type=account_type,
                ),
                accrual_customer_address=accrual_address,
                accrual_internal_account=accrued_profit_payable_account,
                application_customer_address=DEFAULT_ADDRESS,
                application_internal_account=profit_paid_account,
                payable=True,
            )
        )
    return posting_instructions


def profit_application_update_next_schedule_execution(
    *, vault: Any, effective_datetime: datetime
) -> Optional[UpdateAccountEventTypeDirective]:
    """
    Update next scheduled execution.
    :param vault: Vault object to retrieve profit application params
    :param effective_datetime: datetime the schedule is running
    :return: update event directive
    """
    new_schedule = profit_application_scheduled_events(
        vault=vault, start_datetime=effective_datetime
    )
    return UpdateAccountEventTypeDirective(
        event_type=profit_application_APPLICATION_EVENT,
        expression=new_schedule[profit_application_APPLICATION_EVENT].expression,
    )


# Objects below have been imported from:
#    shariah_savings_account.py
# md5:b1dad3bdaa4ea4c8d942aa2eadf3bc4c

ACCOUNT_TYPE = "SHARIAH_SAVINGS_ACCOUNT"
event_types = [
    *profit_application_event_types(ACCOUNT_TYPE),
    *tiered_profit_accrual_event_types(ACCOUNT_TYPE),
]
PARAM_DENOMINATION = "denomination"
PARAM_PAYMENT_TYPE_FEE_INCOME_ACCOUNT = "payment_type_fee_income_account"
parameters = [
    Parameter(
        name=PARAM_DENOMINATION,
        level=ParameterLevel.TEMPLATE,
        description="Currency in which the product operates.",
        display_name="Denomination",
        shape=DenominationShape(),
        default_value="MYR",
    ),
    Parameter(
        name=PARAM_PAYMENT_TYPE_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for payment type fee income balance.",
        display_name="Payment Type Fee Income Account",
        shape=AccountIdShape(),
        default_value="PAYMENT_TYPE_FEE_INCOME",
    ),
    *minimum_initial_deposit_parameters,
    *maximum_single_deposit_parameters,
    *minimum_single_deposit_parameters,
    *maximum_balance_limit_parameters,
    *profit_application_parameters,
    *tiered_profit_accrual_all_parameters,
    *payment_type_flat_fee_parameters,
    *payment_type_threshold_fee_parameters,
    *payment_type_monthly_limit_fee_parameters,
    *early_closure_fee_parameters,
    *maximum_single_withdrawal_parameters,
    *maximum_withdrawal_by_payment_type_parameters,
    *minimum_balance_by_tier_parameters,
    *account_tiers_parameters,
    *maximum_daily_deposit_parameters,
    *maximum_daily_withdrawal_parameters,
    *maximum_daily_withdrawal_by_transaction_type_parameters,
]
data_fetchers = [
    fetchers_EOD_FETCHER,
    fetchers_LIVE_BALANCES_BOF,
    fetchers_MONTH_TO_EFFECTIVE_POSTINGS_FETCHER,
    fetchers_EFFECTIVE_DATE_POSTINGS_FETCHER,
]
