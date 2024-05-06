# Code auto-generated using Inception Smart Contract Renderer Version 2.0.1


# Objects below have been imported from:
#    current_account.py
# md5:feb2444ab103a3a87f10561af91c7055

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
    DenominationShape,
    UnionItem,
    UnionShape,
    BalancesObservationFetcher,
    DefinedDateTime,
    Override,
    PostingsIntervalFetcher,
    RelativeDateTime,
    Shift,
    NumberShape,
    AccountIdShape,
    OptionalShape,
    SmartContractEventType,
    ClientTransaction,
    BalancesObservation,
    PrePostingHookArguments,
    ActivationHookArguments,
    ActivationHookResult,
    ConversionHookArguments,
    ConversionHookResult,
    DeactivationHookArguments,
    DeactivationHookResult,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    PostingInstructionsDirective,
    PostPostingHookArguments,
    PostPostingHookResult,
    PreParameterChangeHookArguments,
    PreParameterChangeHookResult,
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
version = "1.1.0"
display_name = "Personal Current Account"
summary = "Personal Current Account Product"
tside = Tside.LIABILITY
supported_denominations = ["EUR", "GBP", "USD"]


@requires(parameters=True)
def activation_hook(
    vault: Any, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    scheduled_events: dict[str, ScheduledEvent] = {}
    start_datetime_at_midnight = hook_arguments.effective_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    scheduled_events = {
        **inactivity_fee_scheduled_events(
            vault=vault, start_datetime=start_datetime_at_midnight + relativedelta(months=1)
        ),
        **interest_application_scheduled_events(
            vault=vault, reference_datetime=start_datetime_at_midnight
        ),
        **maintenance_fees_scheduled_events(
            vault=vault,
            start_datetime=start_datetime_at_midnight,
            frequency=maintenance_fees_MONTHLY,
        ),
        **maintenance_fees_scheduled_events(
            vault=vault,
            start_datetime=start_datetime_at_midnight,
            frequency=maintenance_fees_ANNUALLY,
        ),
        **minimum_monthly_balance_scheduled_events(
            vault=vault, start_datetime=start_datetime_at_midnight + relativedelta(months=1)
        ),
        **tiered_interest_accrual_scheduled_events(
            vault=vault, start_datetime=start_datetime_at_midnight + relativedelta(days=1)
        ),
        **unarranged_overdraft_fee_application_scheduled_events(
            vault=vault, start_datetime=start_datetime_at_midnight
        ),
    }
    return ActivationHookResult(scheduled_events_return_value=scheduled_events)


def conversion_hook(
    vault: Any, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    return ConversionHookResult(scheduled_events_return_value=hook_arguments.existing_schedules)


@fetch_account_data(balances=["live_balances_bof"])
@requires(parameters=True, flags=True)
def deactivation_hook(
    vault: Any, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    effective_datetime: datetime = hook_arguments.effective_datetime
    posting_directives: list[PostingInstructionsDirective] = []
    if dormancy_is_account_dormant(vault=vault, effective_datetime=effective_datetime):
        return DeactivationHookResult(
            rejection=Rejection(
                message="Cannot close a dormant account.", reason_code=RejectionReason.AGAINST_TNC
            )
        )
    balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    denomination = common_parameters_get_denomination_parameter(
        vault=vault, effective_datetime=effective_datetime
    )
    if partial_fee_has_outstanding_fees(
        vault=vault, fee_collection=FEE_HIERARCHY, balances=balances, denomination=denomination
    ):
        return DeactivationHookResult(
            rejection=Rejection(
                message="Cannot close account with outstanding fees.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
    posting_instructions = _clean_up_accrued_and_overdraft_interest(
        vault=vault, balances=balances, denomination=denomination
    )
    posting_instructions.extend(
        unarranged_overdraft_fee_apply_fee(
            vault=vault, balances=balances, denomination=denomination
        )
    )
    if posting_instructions:
        posting_directives.append(
            PostingInstructionsDirective(
                posting_instructions=posting_instructions,
                value_datetime=effective_datetime,
                client_batch_id=f"{vault.get_hook_execution_id()}_{CLOSE_ACCOUNT}",
            )
        )
        return DeactivationHookResult(posting_instructions_directives=posting_directives)
    return None


@requires(parameters=True, flags=True)
def derived_parameter_hook(
    vault: Any, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    effective_datetime: datetime = hook_arguments.effective_datetime
    derived_parameters: dict[str, utils_ParameterValueTypeAlias] = {
        PARAM_ACCOUNT_TIER_NAME: account_tiers_get_account_tier(
            vault=vault, effective_datetime=effective_datetime
        )
    }
    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


@fetch_account_data(
    balances=["live_balances_bof"], postings=["MONTH_TO_EFFECTIVE_POSTINGS_FETCHER"]
)
@requires(parameters=True)
def post_posting_hook(
    vault: Any, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    posting_instructions_directives: list[PostingInstructionsDirective] = []
    posting_instructions: list[CustomInstruction] = []
    effective_datetime = hook_arguments.effective_datetime
    denomination = common_parameters_get_denomination_parameter(
        vault=vault, effective_datetime=effective_datetime
    )
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    if autosave_posting_instructions := roundup_autosave_apply(
        vault=vault,
        postings=hook_arguments.posting_instructions,
        denomination=denomination,
        balances=balances,
    ):
        posting_instructions_directives.append(
            PostingInstructionsDirective(
                posting_instructions=autosave_posting_instructions,
                value_datetime=effective_datetime,
            )
        )
        balances = utils_update_inflight_balances(
            account_id=vault.account_id,
            tside=tside,
            current_balances=balances,
            posting_instructions=autosave_posting_instructions,
        )
    if excess_fee_instructions := excess_fee_apply(
        vault=vault,
        proposed_client_transactions=hook_arguments.client_transactions,
        effective_datetime=effective_datetime,
        denomination=denomination,
        account_type=PRODUCT_NAME,
    ):
        posting_instructions.extend(excess_fee_instructions)
        balances = utils_update_inflight_balances(
            account_id=vault.account_id,
            tside=tside,
            current_balances=balances,
            posting_instructions=excess_fee_instructions,
        )
    posting_instructions.extend(
        partial_fee_charge_outstanding_fees(
            vault=vault,
            effective_datetime=effective_datetime,
            fee_collection=FEE_HIERARCHY,
            balances=balances,
            denomination=denomination,
            available_balance_feature=overdraft_limit_OverdraftLimitAvailableBalance,
        )
    )
    if posting_instructions:
        posting_instructions_directives.append(
            PostingInstructionsDirective(
                posting_instructions=posting_instructions, value_datetime=effective_datetime
            )
        )
    if posting_instructions_directives:
        return PostPostingHookResult(
            posting_instructions_directives=posting_instructions_directives
        )
    return None


@requires(parameters=True, flags=True)
def pre_parameter_change_hook(
    vault: Any, hook_arguments: PreParameterChangeHookArguments
) -> Optional[PreParameterChangeHookResult]:
    if param_value := hook_arguments.updated_parameter_values.get(
        maximum_daily_withdrawal_by_transaction_type_PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION
    ):
        if daily_withdrawal_limit_rejection := maximum_daily_withdrawal_by_transaction_type_validate_parameter_change(
            vault=vault, proposed_parameter_value=str(param_value)
        ):
            return PreParameterChangeHookResult(rejection=daily_withdrawal_limit_rejection)
    return None


@requires(parameters=True, flags=True)
@fetch_account_data(balances=["live_balances_bof"], postings=["EFFECTIVE_DATE_POSTINGS_FETCHER"])
def pre_posting_hook(
    vault: Any, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    if utils_is_force_override(posting_instructions=hook_arguments.posting_instructions):
        return None
    effective_datetime = hook_arguments.effective_datetime
    if account_dormant_rejection := dormancy_validate_account_transaction(
        vault=vault, effective_datetime=effective_datetime
    ):
        return PrePostingHookResult(rejection=account_dormant_rejection)
    denomination = common_parameters_get_denomination_parameter(
        vault=vault, effective_datetime=effective_datetime
    )
    additional_denominations: list[str] = utils_get_parameter(
        vault=vault, name=PARAM_ADDITIONAL_DENOMINATIONS, is_json=True
    )
    allowed_denominations = additional_denominations + [denomination]
    if invalid_denomination_rejection := utils_validate_denomination(
        posting_instructions=hook_arguments.posting_instructions,
        accepted_denominations=allowed_denominations,
    ):
        return PrePostingHookResult(rejection=invalid_denomination_rejection)
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    if exceeding_balance_rejection := available_balance_validate(
        balances=balances,
        denominations=additional_denominations,
        posting_instructions=hook_arguments.posting_instructions,
    ):
        return PrePostingHookResult(rejection=exceeding_balance_rejection)
    if overdraft_limit_rejection := overdraft_limit_validate(
        vault=vault,
        postings=hook_arguments.posting_instructions,
        denomination=denomination,
        balances=balances,
    ):
        return PrePostingHookResult(rejection=overdraft_limit_rejection)
    if minimum_single_deposit_rejection := minimum_single_deposit_validate(
        vault=vault, postings=hook_arguments.posting_instructions, denomination=denomination
    ):
        return PrePostingHookResult(rejection=minimum_single_deposit_rejection)
    if minimum_single_withdrawal_rejection := minimum_single_withdrawal_validate(
        vault=vault, postings=hook_arguments.posting_instructions, denomination=denomination
    ):
        return PrePostingHookResult(rejection=minimum_single_withdrawal_rejection)
    if maximum_balance_rejection := maximum_balance_limit_validate(
        vault=vault,
        postings=hook_arguments.posting_instructions,
        denomination=denomination,
        balances=balances,
    ):
        return PrePostingHookResult(rejection=maximum_balance_rejection)
    effective_date_client_transactions = vault.get_client_transactions(
        fetcher_id=fetchers_EFFECTIVE_DATE_POSTINGS_FETCHER_ID
    )
    if maximum_daily_withdrawal_rejection := maximum_daily_withdrawal_validate(
        vault=vault,
        hook_arguments=hook_arguments,
        denomination=denomination,
        effective_date_client_transactions=effective_date_client_transactions,
    ):
        return PrePostingHookResult(rejection=maximum_daily_withdrawal_rejection)
    if maximum_daily_deposit_rejection := maximum_daily_deposit_validate(
        vault=vault,
        hook_arguments=hook_arguments,
        denomination=denomination,
        effective_date_client_transactions=effective_date_client_transactions,
    ):
        return PrePostingHookResult(rejection=maximum_daily_deposit_rejection)
    if maximum_daily_withdrawal_by_transaction_rejection := maximum_daily_withdrawal_by_transaction_type_validate(
        vault=vault,
        hook_arguments=hook_arguments,
        denomination=denomination,
        effective_date_client_transactions=effective_date_client_transactions,
    ):
        return PrePostingHookResult(rejection=maximum_daily_withdrawal_by_transaction_rejection)
    return None


@fetch_account_data(event_type="APPLY_INACTIVITY_FEE", balances=["EFFECTIVE_FETCHER"])
@fetch_account_data(
    event_type="ACCRUE_INTEREST",
    balances=[
        "EOD_FETCHER",
        "PREVIOUS_EOD_1_FETCHER_ID",
        "PREVIOUS_EOD_2_FETCHER_ID",
        "PREVIOUS_EOD_3_FETCHER_ID",
        "PREVIOUS_EOD_4_FETCHER_ID",
        "PREVIOUS_EOD_5_FETCHER_ID",
    ],
)
@fetch_account_data(event_type="APPLY_INTEREST", balances=["EFFECTIVE_FETCHER"])
@fetch_account_data(event_type="APPLY_MONTHLY_FEE", balances=["EFFECTIVE_FETCHER"])
@fetch_account_data(
    event_type="APPLY_MINIMUM_BALANCE_FEE",
    balances=[
        "EFFECTIVE_FETCHER",
        "EOD_FETCHER",
        "PREVIOUS_EOD_1_FETCHER_ID",
        "PREVIOUS_EOD_2_FETCHER_ID",
        "PREVIOUS_EOD_3_FETCHER_ID",
        "PREVIOUS_EOD_4_FETCHER_ID",
        "PREVIOUS_EOD_5_FETCHER_ID",
        "PREVIOUS_EOD_6_FETCHER_ID",
        "PREVIOUS_EOD_7_FETCHER_ID",
        "PREVIOUS_EOD_8_FETCHER_ID",
        "PREVIOUS_EOD_9_FETCHER_ID",
        "PREVIOUS_EOD_10_FETCHER_ID",
        "PREVIOUS_EOD_11_FETCHER_ID",
        "PREVIOUS_EOD_12_FETCHER_ID",
        "PREVIOUS_EOD_13_FETCHER_ID",
        "PREVIOUS_EOD_14_FETCHER_ID",
        "PREVIOUS_EOD_15_FETCHER_ID",
        "PREVIOUS_EOD_16_FETCHER_ID",
        "PREVIOUS_EOD_17_FETCHER_ID",
        "PREVIOUS_EOD_18_FETCHER_ID",
        "PREVIOUS_EOD_19_FETCHER_ID",
        "PREVIOUS_EOD_20_FETCHER_ID",
        "PREVIOUS_EOD_21_FETCHER_ID",
        "PREVIOUS_EOD_22_FETCHER_ID",
        "PREVIOUS_EOD_23_FETCHER_ID",
        "PREVIOUS_EOD_24_FETCHER_ID",
        "PREVIOUS_EOD_25_FETCHER_ID",
        "PREVIOUS_EOD_26_FETCHER_ID",
        "PREVIOUS_EOD_27_FETCHER_ID",
        "PREVIOUS_EOD_28_FETCHER_ID",
        "PREVIOUS_EOD_29_FETCHER_ID",
        "PREVIOUS_EOD_30_FETCHER_ID",
        "PREVIOUS_EOD_31_FETCHER_ID",
    ],
)
@fetch_account_data(event_type="APPLY_UNARRANGED_OVERDRAFT_FEE", balances=["EFFECTIVE_FETCHER"])
@requires(event_type="APPLY_INACTIVITY_FEE", flags=True, parameters=True)
@requires(event_type="ACCRUE_INTEREST", parameters=True)
@requires(event_type="APPLY_INTEREST", parameters=True)
@requires(event_type="APPLY_MONTHLY_FEE", flags=True, parameters=True)
@requires(event_type="APPLY_ANNUAL_FEE", flags=True, parameters=True)
@requires(event_type="APPLY_MINIMUM_BALANCE_FEE", flags=True, parameters=True)
@requires(event_type="APPLY_UNARRANGED_OVERDRAFT_FEE", flags=True, parameters=True)
def scheduled_event_hook(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    event_type: str = hook_arguments.event_type
    effective_datetime: datetime = hook_arguments.effective_datetime
    posting_directives: list[PostingInstructionsDirective] = []
    posting_instructions: list[CustomInstruction] = []
    update_event_directives: list[UpdateAccountEventTypeDirective] = []
    if event_type == tiered_interest_accrual_ACCRUAL_EVENT:
        posting_instructions.extend(
            tiered_interest_accrual_accrue_interest(
                vault=vault, effective_datetime=effective_datetime
            )
        )
        posting_instructions.extend(
            overdraft_interest_accrue_interest(
                vault=vault, effective_datetime=effective_datetime, account_type=PRODUCT_NAME
            )
        )
        posting_instructions.extend(unarranged_overdraft_fee_accrue_fee(vault=vault))
    elif event_type == interest_application_APPLICATION_EVENT:
        posting_instructions.extend(
            interest_application_apply_interest(vault=vault, account_type=PRODUCT_NAME)
        )
        posting_instructions.extend(
            overdraft_interest_apply_interest(vault=vault, account_type=PRODUCT_NAME)
        )
        if update_event_result := interest_application_update_next_schedule_execution(
            vault=vault, effective_datetime=effective_datetime
        ):
            update_event_directives.extend([update_event_result])
    elif event_type == inactivity_fee_APPLICATION_EVENT:
        if inactivity_fee_is_account_inactive(vault=vault, effective_datetime=effective_datetime):
            posting_instructions.extend(
                inactivity_fee_apply(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    available_balance_feature=overdraft_limit_OverdraftLimitAvailableBalance,
                )
            )
    elif event_type == maintenance_fees_APPLY_MONTHLY_FEE_EVENT:
        if not dormancy_is_account_dormant(vault=vault, effective_datetime=effective_datetime):
            posting_instructions.extend(
                maintenance_fees_apply_monthly_fee(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    available_balance_feature=overdraft_limit_OverdraftLimitAvailableBalance,
                )
            )
    elif event_type == maintenance_fees_APPLY_ANNUAL_FEE_EVENT:
        if not dormancy_is_account_dormant(vault=vault, effective_datetime=effective_datetime):
            posting_instructions.extend(
                maintenance_fees_apply_annual_fee(
                    vault=vault, effective_datetime=effective_datetime
                )
            )
        if update_event_result := maintenance_fees_update_next_annual_schedule_execution(
            vault=vault, effective_datetime=effective_datetime
        ):
            update_event_directives.extend([update_event_result])
    elif event_type == minimum_monthly_balance_APPLY_MINIMUM_MONTHLY_BALANCE_EVENT:
        if not dormancy_is_account_dormant(vault=vault, effective_datetime=effective_datetime):
            denomination = common_parameters_get_denomination_parameter(
                vault=vault, effective_datetime=effective_datetime
            )
            posting_instructions.extend(
                minimum_monthly_balance_apply_minimum_balance_fee(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    denomination=denomination,
                    available_balance_feature=overdraft_limit_OverdraftLimitAvailableBalance,
                )
            )
    elif event_type == unarranged_overdraft_fee_APPLICATION_EVENT:
        if not dormancy_is_account_dormant(vault=vault, effective_datetime=effective_datetime):
            posting_instructions.extend(unarranged_overdraft_fee_apply_fee(vault=vault))
    if posting_instructions:
        posting_directives.append(
            PostingInstructionsDirective(
                posting_instructions=posting_instructions,
                value_datetime=effective_datetime,
                client_batch_id=f"{vault.get_hook_execution_id()}_{event_type}",
            )
        )
    if posting_directives or update_event_directives:
        return ScheduledEventHookResult(
            posting_instructions_directives=posting_directives,
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
utils_MONTHLY = "monthly"
utils_QUARTERLY = "quarterly"
utils_ANNUALLY = "annually"
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


def utils_are_optional_parameters_set(vault: Any, parameters: list[str]) -> bool:
    """
    Determines whether the list of optional parameter names are set

    :param vault:
    :param parameters: List of vault parameter names

    :return: bool, True if all parameters are set, False otherwise
    """
    return all(
        (
            utils_get_parameter(vault, parameter, is_optional=True) is not None
            for parameter in parameters
        )
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


def utils_monthly_scheduled_event(
    vault: Any,
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
    start_datetime = start_datetime - relativedelta(seconds=1)
    if start_datetime < account_creation_datetime:
        start_datetime = account_creation_datetime
    return ScheduledEvent(
        start_datetime=start_datetime,
        schedule_method=utils_get_end_of_month_schedule_from_parameters(
            vault=vault, parameter_prefix=parameter_prefix, failover=failover, day=day
        ),
    )


def utils_get_end_of_month_schedule_from_parameters(
    vault: Any,
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
        day = int(utils_get_parameter(vault, name=f"{parameter_prefix}_day"))
    hour = int(utils_get_parameter(vault, name=f"{parameter_prefix}_hour"))
    minute = int(utils_get_parameter(vault, name=f"{parameter_prefix}_minute"))
    second = int(utils_get_parameter(vault, name=f"{parameter_prefix}_second"))
    return EndOfMonthSchedule(day=day, hour=hour, minute=minute, second=second, failover=failover)


def utils_get_schedule_time_from_parameters(
    vault: Any, parameter_prefix: str
) -> tuple[int, int, int]:
    hour = int(utils_get_parameter(vault=vault, name=f"{parameter_prefix}_hour"))
    minute = int(utils_get_parameter(vault=vault, name=f"{parameter_prefix}_minute"))
    second = int(utils_get_parameter(vault=vault, name=f"{parameter_prefix}_second"))
    return (hour, minute, second)


def utils_get_schedule_expression_from_parameters(
    vault: Any,
    parameter_prefix: str,
    *,
    day: Optional[Union[int, str]] = None,
    month: Optional[Union[int, str]] = None,
    year: Optional[Union[int, str]] = None,
    day_of_week: Optional[Union[int, str]] = None,
) -> ScheduleExpression:
    (hour, minute, second) = utils_get_schedule_time_from_parameters(vault, parameter_prefix)
    return ScheduleExpression(
        hour=str(hour),
        minute=str(minute),
        second=str(second),
        day=None if not day else str(day),
        month=None if not month else str(month),
        year=None if not year else str(year),
        day_of_week=None if not day_of_week else str(day_of_week),
    )


def utils_get_next_schedule_date(
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
    frequency_map = {utils_MONTHLY: 1, utils_QUARTERLY: 3, utils_ANNUALLY: 12}
    number_of_months = frequency_map[schedule_frequency]
    if (
        schedule_frequency == utils_MONTHLY
        and start_date + relativedelta(day=intended_day) > start_date
    ):
        return start_date + relativedelta(day=intended_day)
    else:
        return start_date + relativedelta(months=number_of_months, day=intended_day)


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


def utils_is_flag_in_list_applied(
    *, vault: Any, parameter_name: str, effective_datetime: Optional[datetime] = None
) -> bool:
    """
    Determine if a flag in the list provided is set and active

    :param vault:
    :param parameter_name: str, name of the parameter to retrieve
    :param effective_datetime: datetime at which to retrieve the flag timeseries value. If not
    specified the latest value is retrieved
    :return: bool, True if any of the flags in the list are applied at the given datetime
    """
    flag_names: list[str] = utils_get_parameter(vault, name=parameter_name, is_json=True)
    return any(
        (
            vault.get_flag_timeseries(flag=flag_name).at(at_datetime=effective_datetime)
            if effective_datetime
            else vault.get_flag_timeseries(flag=flag_name).latest()
            for flag_name in flag_names
        )
    )


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


def utils_average_balance(*, balances: list[Decimal]) -> Decimal:
    """
    Calculate the average balance
    :param balances: List of the values of balances to calculate the average balance
    :return: Decimal average balance calculated
    """
    if balances:
        return Decimal(sum(balances) / len(balances))
    return Decimal(0)


def utils_update_inflight_balances(
    account_id: str,
    tside: Tside,
    current_balances: BalanceDefaultDict,
    posting_instructions: utils_PostingInstructionListAlias,
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
    inflight_balances = BalanceDefaultDict(mapping=current_balances)
    for posting_instruction in posting_instructions:
        inflight_balances += posting_instruction.balances(account_id=account_id, tside=tside)
    return inflight_balances


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
#    common_parameters.py
# md5:11b3b3b4a92b1dc6ec77a2405fb2ca6d

common_parameters_BooleanShape = UnionShape(
    items=[UnionItem(key="True", display_name="True"), UnionItem(key="False", display_name="False")]
)
common_parameters_BooleanValueTrue = UnionItemValue(key="True")
common_parameters_BooleanValueFalse = UnionItemValue(key="False")
common_parameters_PARAM_DENOMINATION = "denomination"
common_parameters_denomination_parameter = Parameter(
    name=common_parameters_PARAM_DENOMINATION,
    shape=DenominationShape(),
    level=ParameterLevel.TEMPLATE,
    description="Currency in which the product operates.",
    display_name="Denomination",
    default_value="GBP",
)


def common_parameters_get_denomination_parameter(
    vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    denomination: str = utils_get_parameter(
        vault=vault, name=common_parameters_PARAM_DENOMINATION, at_datetime=effective_datetime
    )
    return denomination


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
fetchers_EFFECTIVE_OBSERVATION_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID, at=DefinedDateTime.EFFECTIVE_DATETIME
)
fetchers_LIVE_BALANCES_BOF_ID = "live_balances_bof"
fetchers_LIVE_BALANCES_BOF = BalancesObservationFetcher(
    fetcher_id=fetchers_LIVE_BALANCES_BOF_ID, at=DefinedDateTime.LIVE
)
fetchers_PREVIOUS_EOD_1_FETCHER_ID = "PREVIOUS_EOD_1_FETCHER_ID"
fetchers_PREVIOUS_EOD_1_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_1_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-1),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_2_FETCHER_ID = "PREVIOUS_EOD_2_FETCHER_ID"
fetchers_PREVIOUS_EOD_2_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_2_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-2),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_3_FETCHER_ID = "PREVIOUS_EOD_3_FETCHER_ID"
fetchers_PREVIOUS_EOD_3_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_3_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-3),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_4_FETCHER_ID = "PREVIOUS_EOD_4_FETCHER_ID"
fetchers_PREVIOUS_EOD_4_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_4_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-4),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_5_FETCHER_ID = "PREVIOUS_EOD_5_FETCHER_ID"
fetchers_PREVIOUS_EOD_5_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_5_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-5),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_6_FETCHER_ID = "PREVIOUS_EOD_6_FETCHER_ID"
fetchers_PREVIOUS_EOD_6_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_6_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-6),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_7_FETCHER_ID = "PREVIOUS_EOD_7_FETCHER_ID"
fetchers_PREVIOUS_EOD_7_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_7_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-7),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_8_FETCHER_ID = "PREVIOUS_EOD_8_FETCHER_ID"
fetchers_PREVIOUS_EOD_8_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_8_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-8),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_9_FETCHER_ID = "PREVIOUS_EOD_9_FETCHER_ID"
fetchers_PREVIOUS_EOD_9_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_9_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-9),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_10_FETCHER_ID = "PREVIOUS_EOD_10_FETCHER_ID"
fetchers_PREVIOUS_EOD_10_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_10_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-10),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_11_FETCHER_ID = "PREVIOUS_EOD_11_FETCHER_ID"
fetchers_PREVIOUS_EOD_11_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_11_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-11),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_12_FETCHER_ID = "PREVIOUS_EOD_12_FETCHER_ID"
fetchers_PREVIOUS_EOD_12_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_12_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-12),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_13_FETCHER_ID = "PREVIOUS_EOD_13_FETCHER_ID"
fetchers_PREVIOUS_EOD_13_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_13_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-13),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_14_FETCHER_ID = "PREVIOUS_EOD_14_FETCHER_ID"
fetchers_PREVIOUS_EOD_14_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_14_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-14),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_15_FETCHER_ID = "PREVIOUS_EOD_15_FETCHER_ID"
fetchers_PREVIOUS_EOD_15_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_15_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-15),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_16_FETCHER_ID = "PREVIOUS_EOD_16_FETCHER_ID"
fetchers_PREVIOUS_EOD_16_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_16_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-16),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_17_FETCHER_ID = "PREVIOUS_EOD_17_FETCHER_ID"
fetchers_PREVIOUS_EOD_17_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_17_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-17),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_18_FETCHER_ID = "PREVIOUS_EOD_18_FETCHER_ID"
fetchers_PREVIOUS_EOD_18_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_18_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-18),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_19_FETCHER_ID = "PREVIOUS_EOD_19_FETCHER_ID"
fetchers_PREVIOUS_EOD_19_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_19_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-19),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_20_FETCHER_ID = "PREVIOUS_EOD_20_FETCHER_ID"
fetchers_PREVIOUS_EOD_20_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_20_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-20),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_21_FETCHER_ID = "PREVIOUS_EOD_21_FETCHER_ID"
fetchers_PREVIOUS_EOD_21_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_21_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-21),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_22_FETCHER_ID = "PREVIOUS_EOD_22_FETCHER_ID"
fetchers_PREVIOUS_EOD_22_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_22_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-22),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_23_FETCHER_ID = "PREVIOUS_EOD_23_FETCHER_ID"
fetchers_PREVIOUS_EOD_23_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_23_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-23),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_24_FETCHER_ID = "PREVIOUS_EOD_24_FETCHER_ID"
fetchers_PREVIOUS_EOD_24_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_24_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-24),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_25_FETCHER_ID = "PREVIOUS_EOD_25_FETCHER_ID"
fetchers_PREVIOUS_EOD_25_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_25_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-25),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_26_FETCHER_ID = "PREVIOUS_EOD_26_FETCHER_ID"
fetchers_PREVIOUS_EOD_26_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_26_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-26),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_27_FETCHER_ID = "PREVIOUS_EOD_27_FETCHER_ID"
fetchers_PREVIOUS_EOD_27_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_27_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-27),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_28_FETCHER_ID = "PREVIOUS_EOD_28_FETCHER_ID"
fetchers_PREVIOUS_EOD_28_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_28_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-28),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_29_FETCHER_ID = "PREVIOUS_EOD_29_FETCHER_ID"
fetchers_PREVIOUS_EOD_29_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_29_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-29),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_30_FETCHER_ID = "PREVIOUS_EOD_30_FETCHER_ID"
fetchers_PREVIOUS_EOD_30_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_30_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-30),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_31_FETCHER_ID = "PREVIOUS_EOD_31_FETCHER_ID"
fetchers_PREVIOUS_EOD_31_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_PREVIOUS_EOD_31_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-31),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)
fetchers_PREVIOUS_EOD_OBSERVATION_FETCHERS = [
    fetchers_PREVIOUS_EOD_1_FETCHER,
    fetchers_PREVIOUS_EOD_2_FETCHER,
    fetchers_PREVIOUS_EOD_3_FETCHER,
    fetchers_PREVIOUS_EOD_4_FETCHER,
    fetchers_PREVIOUS_EOD_5_FETCHER,
    fetchers_PREVIOUS_EOD_6_FETCHER,
    fetchers_PREVIOUS_EOD_7_FETCHER,
    fetchers_PREVIOUS_EOD_8_FETCHER,
    fetchers_PREVIOUS_EOD_9_FETCHER,
    fetchers_PREVIOUS_EOD_10_FETCHER,
    fetchers_PREVIOUS_EOD_11_FETCHER,
    fetchers_PREVIOUS_EOD_12_FETCHER,
    fetchers_PREVIOUS_EOD_13_FETCHER,
    fetchers_PREVIOUS_EOD_14_FETCHER,
    fetchers_PREVIOUS_EOD_15_FETCHER,
    fetchers_PREVIOUS_EOD_16_FETCHER,
    fetchers_PREVIOUS_EOD_17_FETCHER,
    fetchers_PREVIOUS_EOD_18_FETCHER,
    fetchers_PREVIOUS_EOD_19_FETCHER,
    fetchers_PREVIOUS_EOD_20_FETCHER,
    fetchers_PREVIOUS_EOD_21_FETCHER,
    fetchers_PREVIOUS_EOD_22_FETCHER,
    fetchers_PREVIOUS_EOD_23_FETCHER,
    fetchers_PREVIOUS_EOD_24_FETCHER,
    fetchers_PREVIOUS_EOD_25_FETCHER,
    fetchers_PREVIOUS_EOD_26_FETCHER,
    fetchers_PREVIOUS_EOD_27_FETCHER,
    fetchers_PREVIOUS_EOD_28_FETCHER,
    fetchers_PREVIOUS_EOD_29_FETCHER,
    fetchers_PREVIOUS_EOD_30_FETCHER,
    fetchers_PREVIOUS_EOD_31_FETCHER,
]
fetchers_PREVIOUS_EOD_OBSERVATION_FETCHER_IDS = [
    fetchers_PREVIOUS_EOD_1_FETCHER_ID,
    fetchers_PREVIOUS_EOD_2_FETCHER_ID,
    fetchers_PREVIOUS_EOD_3_FETCHER_ID,
    fetchers_PREVIOUS_EOD_4_FETCHER_ID,
    fetchers_PREVIOUS_EOD_5_FETCHER_ID,
    fetchers_PREVIOUS_EOD_6_FETCHER_ID,
    fetchers_PREVIOUS_EOD_7_FETCHER_ID,
    fetchers_PREVIOUS_EOD_8_FETCHER_ID,
    fetchers_PREVIOUS_EOD_9_FETCHER_ID,
    fetchers_PREVIOUS_EOD_10_FETCHER_ID,
    fetchers_PREVIOUS_EOD_11_FETCHER_ID,
    fetchers_PREVIOUS_EOD_12_FETCHER_ID,
    fetchers_PREVIOUS_EOD_13_FETCHER_ID,
    fetchers_PREVIOUS_EOD_14_FETCHER_ID,
    fetchers_PREVIOUS_EOD_15_FETCHER_ID,
    fetchers_PREVIOUS_EOD_16_FETCHER_ID,
    fetchers_PREVIOUS_EOD_17_FETCHER_ID,
    fetchers_PREVIOUS_EOD_18_FETCHER_ID,
    fetchers_PREVIOUS_EOD_19_FETCHER_ID,
    fetchers_PREVIOUS_EOD_20_FETCHER_ID,
    fetchers_PREVIOUS_EOD_21_FETCHER_ID,
    fetchers_PREVIOUS_EOD_22_FETCHER_ID,
    fetchers_PREVIOUS_EOD_23_FETCHER_ID,
    fetchers_PREVIOUS_EOD_24_FETCHER_ID,
    fetchers_PREVIOUS_EOD_25_FETCHER_ID,
    fetchers_PREVIOUS_EOD_26_FETCHER_ID,
    fetchers_PREVIOUS_EOD_27_FETCHER_ID,
    fetchers_PREVIOUS_EOD_28_FETCHER_ID,
    fetchers_PREVIOUS_EOD_29_FETCHER_ID,
    fetchers_PREVIOUS_EOD_30_FETCHER_ID,
    fetchers_PREVIOUS_EOD_31_FETCHER_ID,
]
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
#    available_balance.py
# md5:f120b4a4f74fee55fb679c9b49411e4f


def available_balance_validate(
    balances: BalanceDefaultDict,
    denominations: list[str],
    posting_instructions: utils_PostingInstructionListAlias,
) -> Optional[Rejection]:
    """
    Returns rejection if the posting instructions balance is gt available balance for each
    denomination. Logic applies only on withdrawal and for Tside.LIABILITY

    :param balances: balances used to retrieve available balances
    :param denominations: list of denominations to check
    :param posting_instructions: list of posting instructions to process
    :return: the rejection of posting instruction amount exceeding available balance
    """
    for denomination in denominations:
        available_balance = utils_get_available_balance(
            balances=balances, denomination=denomination
        )
        posting_instruction_amount = Decimal(
            sum(
                (
                    utils_get_available_balance(
                        balances=posting_instruction.balances(), denomination=denomination
                    )
                    for posting_instruction in posting_instructions
                )
            )
        )
        if posting_instruction_amount < 0 and abs(posting_instruction_amount) > available_balance:
            return Rejection(
                message=f"Posting amount of {abs(posting_instruction_amount)} {denomination} is exceeding available balance of {available_balance} {denomination}.",
                reason_code=RejectionReason.INSUFFICIENT_FUNDS,
            )
    return None


# Objects below have been imported from:
#    dormancy.py
# md5:11c5bd771f56c5b8e92f2cff36b03cac

dormancy_PARAM_DORMANCY_FLAGS = "dormancy_flags"
dormancy_parameters = [
    Parameter(
        name=dormancy_PARAM_DORMANCY_FLAGS,
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        description="The list of flag definitions that indicate an account is dormant. Dormant accounts may incur fees and have their transactions blocked. Expects a string representation of a JSON list.",
        display_name="Dormancy Flags",
        default_value=dumps(["ACCOUNT_DORMANT"]),
    )
]


def dormancy_is_account_dormant(vault: Any, effective_datetime: datetime) -> bool:
    return utils_is_flag_in_list_applied(
        vault=vault,
        parameter_name=dormancy_PARAM_DORMANCY_FLAGS,
        effective_datetime=effective_datetime,
    )


def dormancy_validate_account_transaction(
    vault: Any, effective_datetime: datetime
) -> Optional[Rejection]:
    """
    This function is used to validate account transactions in the pre posting hook only.

    :param vault: SmartContractVault object
    :param effective_datetime: datetime object
    :return: Rejection to be used in PrePostingHookResult
    """
    if dormancy_is_account_dormant(vault=vault, effective_datetime=effective_datetime):
        return Rejection(
            message="Account flagged 'Dormant' does not accept external transactions.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


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
#    deposit_interfaces.py
# md5:c5f8eb9ed8ba4721d20e372f17c73863

deposit_interfaces_PartialFeeCollection = NamedTuple(
    "PartialFeeCollection",
    [
        ("outstanding_fee_address", str),
        ("fee_type", str),
        ("get_internal_account_parameter", Callable[..., str]),
    ],
)
deposit_interfaces_AvailableBalance = NamedTuple(
    "AvailableBalance", [("calculate", Callable[..., Decimal])]
)
deposit_interfaces_WaiveFeeCondition = NamedTuple(
    "WaiveFeeCondition", [("waive_fees", Callable[..., bool])]
)

# Objects below have been imported from:
#    addresses.py
# md5:860f50af37f2fe98540f540fa6394eb7

addresses_INTERNAL_CONTRA = "INTERNAL_CONTRA"

# Objects below have been imported from:
#    lending_addresses.py
# md5:d546448643732336308da8f52c0901d4

lending_addresses_INTERNAL_CONTRA = addresses_INTERNAL_CONTRA

# Objects below have been imported from:
#    partial_fee.py
# md5:add41b363d22dd11201120af5f757a56


def partial_fee_charge_partial_fee(
    vault: Any,
    effective_datetime: datetime,
    fee_custom_instruction: CustomInstruction,
    fee_details: deposit_interfaces_PartialFeeCollection,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    available_balance_feature: Optional[deposit_interfaces_AvailableBalance] = None,
) -> list[CustomInstruction]:
    """
    Charge a Partial fee, intended to wrap an existing fee custom instruction.
    Fees are generally charged from a scheduled event.
    :param vault: Vault Object
    :param effective_datetime: the datetime at which to fetch the fee account parameters.
    :param fee_custom_instruction: The custom fee instruction to wrap
    :param fee_details: The associated fee details, implemented in a common feature definition
    :param balances: Account balances, if not provided then then balances will be retrieved using
    the EFFECTIVE_OBSERVATION_FETCHER_ID
    :param denomination: the denomination of the fee, if not provided the 'denomination' parameter
    is retrieved
    :param available_balance_feature: Interface to calculate the available balance for the account
    using a custom definition
    :return: A augmented list of CustomInstructions containing the partial fee instructions
    if required.
    """
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    incoming_fee_balances = fee_custom_instruction.balances(
        account_id=vault.account_id, tside=vault.tside
    )
    fee_amount = utils_balance_at_coordinates(
        balances=incoming_fee_balances, address=DEFAULT_ADDRESS, denomination=denomination
    )
    fee_amount = -fee_amount
    available_amount = (
        available_balance_feature.calculate(
            vault=vault, balances=balances, denomination=denomination
        )
        if available_balance_feature
        else utils_get_available_balance(balances=balances, denomination=denomination)
    )
    if available_amount >= fee_amount:
        return [fee_custom_instruction]
    chargeable_fee = min(fee_amount, available_amount)
    outstanding_fee = fee_amount - chargeable_fee
    partial_fee_address = fee_details.outstanding_fee_address
    fee_internal_account = fee_details.get_internal_account_parameter(
        vault=vault, effective_datetime=effective_datetime
    )
    custom_instructions: list[CustomInstruction] = []
    incoming_fee_details = fee_custom_instruction.instruction_details
    if "description" in incoming_fee_details:
        incoming_fee_details["description"] += f" Partially charged, remaining {outstanding_fee}"
        " to be charged when the account has sufficient balance"
    else:
        incoming_fee_details["description"] = fee_details.fee_type
    if chargeable_fee > 0:
        custom_instructions.extend(
            fees_fee_custom_instruction(
                customer_account_id=vault.account_id,
                denomination=denomination,
                amount=chargeable_fee,
                customer_account_address=DEFAULT_ADDRESS,
                internal_account=fee_internal_account,
                instruction_details=incoming_fee_details,
            )
        )
    if outstanding_fee > 0:
        custom_instructions.extend(
            partial_fee_modify_tracking_balance(
                account_id=vault.account_id,
                denomination=denomination,
                tracking_address=partial_fee_address,
                fee_type=fee_details.fee_type,
                value=outstanding_fee,
            )
        )
    return custom_instructions


def partial_fee_charge_outstanding_fees(
    vault: Any,
    effective_datetime: datetime,
    fee_collection: list[deposit_interfaces_PartialFeeCollection],
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    available_balance_feature: Optional[deposit_interfaces_AvailableBalance] = None,
) -> list[CustomInstruction]:
    """
    Charge outstanding fees is intended to be called from the post posting hook in order to address
    charging of outstanding partial amounts based on a pre-defined static repayment hierarchy.
    will reduce the tracking balance by the amount charged.
    :param vault: The SmartContractVault object,
    :param effective_datetime: the datetime at which to fetch the fee account parameter.
    :param fee_collection: The list of partial fees to collect from. The order will define
        the repayment hierarchy.
    :param balances: Account balances, if not provided then then balances will be retrieved using
    the LIVE_BALANCES_BOF_ID
    :param denomination: the denomination of the fee, if not provided the 'denomination' parameter
    is retrieved
    :param available_balance_feature: Interface to calculate the available balance for the account
    using a custom definition
    :return: a list of CustomInstructions to execute due to outstanding fees.
    """
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    custom_instructions: list[CustomInstruction] = []
    account_available_balance = (
        available_balance_feature.calculate(
            vault=vault, balances=balances, denomination=denomination
        )
        if available_balance_feature
        else utils_get_available_balance(balances=balances, denomination=denomination)
    )
    for fee in fee_collection:
        if account_available_balance <= Decimal("0"):
            break
        outstanding_fee_address = fee.outstanding_fee_address
        outstanding_fee_amount = utils_balance_at_coordinates(
            address=outstanding_fee_address, balances=balances, denomination=denomination
        )
        amount_to_charge = min(outstanding_fee_amount, account_available_balance)
        fee_internal_account = fee.get_internal_account_parameter(
            vault=vault, effective_datetime=effective_datetime
        )
        if amount_to_charge > Decimal("0"):
            custom_instructions.extend(
                fees_fee_custom_instruction(
                    customer_account_id=vault.account_id,
                    denomination=denomination,
                    amount=amount_to_charge,
                    customer_account_address=DEFAULT_ADDRESS,
                    internal_account=fee_internal_account,
                    instruction_details={
                        "description": f"Charge outstanding partial fee: {fee.fee_type}",
                        "event": f"Charge {fee.fee_type}",
                    },
                )
            )
            custom_instructions.extend(
                partial_fee_modify_tracking_balance(
                    account_id=vault.account_id,
                    denomination=denomination,
                    tracking_address=outstanding_fee_address,
                    fee_type=fee.fee_type,
                    value=amount_to_charge,
                    payment_deduction=True,
                )
            )
            account_available_balance -= amount_to_charge
    return custom_instructions


def partial_fee_has_outstanding_fees(
    vault: Any,
    fee_collection: list[deposit_interfaces_PartialFeeCollection],
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> bool:
    """
    Check for any outstanding fees.
    This can be used in the Deactivation Hook to block account closure.

    :param vault: The SmartContractVault object
    :param fee_collection: The list of partial fees to collect from.
    :param balances: The balance that will be used for the fee calculations.
    Defaults to Live Balances if none provided.
    :param denomination: The denomination that the fees will be addressed in.
    Defaults to the Denomination Parameter Value.
    :return: True if any of the fees have an outstanding balance.
    """
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    return any(
        (
            utils_balance_at_coordinates(
                address=fee.outstanding_fee_address, balances=balances, denomination=denomination
            )
            > Decimal(0)
            for fee in fee_collection
        )
    )


def partial_fee_modify_tracking_balance(
    account_id: str,
    denomination: str,
    tracking_address: str,
    fee_type: str,
    value: Decimal,
    payment_deduction: bool = False,
) -> list[CustomInstruction]:
    instruction_details = {"description": fee_type, "event": f"Update {fee_type} amount owed"}
    return partial_fee_modify_tracking_balance_utils(
        account_id=account_id,
        denomination=denomination,
        tracking_address=tracking_address,
        value=value,
        payment_deduction=payment_deduction,
        instruction_details=instruction_details,
    )


def partial_fee_modify_tracking_balance_utils(
    account_id: str,
    denomination: str,
    tracking_address: str,
    value: Decimal,
    payment_deduction: bool = False,
    instruction_details: dict = {},
) -> list[CustomInstruction]:
    """
    This function is intended to increase the tracking balance used for a partial payment address
    by a given value.

    To decrease the value on the tracking, set the payment_deduction argument to True to imply the
    tracking balance has been decreased due to the amount owed being paid.

    :param account_id: the account ID to modify the tracking balance for
    :param denomination: the denomination of the account.
    :param tracking_address: the Partial Payment Tracking Address
    :param fee_type: the description of the fee type.
    :param value: The amount to INCREASE the tracking balance by, or DECREASE if PAYMENT DEDUCTION
        is TRUE.
    :param payment_deduction: Whether or not to reverse the instruction by the amount.
    :return: returns the resulting custom instruction.
    """
    debit_address = lending_addresses_INTERNAL_CONTRA
    credit_address = tracking_address
    if value <= 0:
        return []
    if payment_deduction:
        credit_address = debit_address
        debit_address = tracking_address
    return [
        CustomInstruction(
            postings=utils_create_postings(
                amount=value,
                debit_account=account_id,
                debit_address=debit_address,
                credit_account=account_id,
                credit_address=credit_address,
                denomination=denomination,
            ),
            instruction_details=instruction_details,
        )
    ]


# Objects below have been imported from:
#    inactivity_fee.py
# md5:38c30b49921953a64a8cd6768b090dd0

inactivity_fee_APPLICATION_EVENT = "APPLY_INACTIVITY_FEE"
inactivity_fee_OUTSTANDING_INACTIVITY_FEE_TRACKER = "outstanding_inactivity_fee_tracker"
inactivity_fee_PARAM_INACTIVITY_FLAGS = "inactivity_flags"
inactivity_fee_PARAM_INACTIVITY_FEE = "inactivity_fee"
inactivity_fee_PARAM_INACTIVITY_FEE_INCOME_ACCOUNT = "inactivity_fee_income_account"
inactivity_fee_PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED = "partial_inactivity_fee_enabled"
inactivity_fee_inactivity_flags_parameter = Parameter(
    name=inactivity_fee_PARAM_INACTIVITY_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that indicate an account is inactive. Inactive accounts may incur an inactivity fee. Expects a string representation of a JSON list.",
    display_name="Inactivity Flags",
    default_value=dumps(["ACCOUNT_INACTIVE"]),
)
inactivity_fee_fee_parameters = [
    Parameter(
        name=inactivity_fee_PARAM_INACTIVITY_FEE,
        level=ParameterLevel.TEMPLATE,
        description="The monthly fee charged for inactivity on an account.",
        display_name="Monthly Inactivity Fee",
        shape=NumberShape(min_value=0, step=Decimal("0.01")),
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name=inactivity_fee_PARAM_INACTIVITY_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for inactivity fee income balance.",
        display_name="Inactivity Fee Income Account",
        shape=AccountIdShape(),
        default_value="INACTIVITY_FEE_INCOME",
    ),
    Parameter(
        name=inactivity_fee_PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED,
        shape=OptionalShape(shape=common_parameters_BooleanShape),
        level=ParameterLevel.TEMPLATE,
        description="Toggles partial payments for inactivity fee",
        display_name="Inactivity Partial Fees Enabled",
        default_value=OptionalValue(common_parameters_BooleanValueFalse),
    ),
]
inactivity_fee_INACTIVITY_FEE_APPLICATION_PREFIX = "inactivity_fee_application"
inactivity_fee_PARAM_INACTIVITY_FEE_APPLICATION_DAY = (
    f"{inactivity_fee_INACTIVITY_FEE_APPLICATION_PREFIX}_day"
)
inactivity_fee_PARAM_INACTIVITY_FEE_APPLICATION_HOUR = (
    f"{inactivity_fee_INACTIVITY_FEE_APPLICATION_PREFIX}_hour"
)
inactivity_fee_PARAM_INACTIVITY_FEE_APPLICATION_MINUTE = (
    f"{inactivity_fee_INACTIVITY_FEE_APPLICATION_PREFIX}_minute"
)
inactivity_fee_PARAM_INACTIVITY_FEE_APPLICATION_SECOND = (
    f"{inactivity_fee_INACTIVITY_FEE_APPLICATION_PREFIX}_second"
)
inactivity_fee_schedule_parameters = [
    Parameter(
        name=inactivity_fee_PARAM_INACTIVITY_FEE_APPLICATION_DAY,
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=ParameterLevel.INSTANCE,
        description="The day of the month on which inactivity fee is applied. If day does not exist in application month, applies on last day of month.",
        display_name="Inactivity Fee Application Day",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name=inactivity_fee_PARAM_INACTIVITY_FEE_APPLICATION_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which inactivity fee is applied.",
        display_name="Inactivity Fee Application Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=inactivity_fee_PARAM_INACTIVITY_FEE_APPLICATION_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which inactivity fee is applied.",
        display_name="Inactivity Fee Application Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=inactivity_fee_PARAM_INACTIVITY_FEE_APPLICATION_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which inactivity fee is applied.",
        display_name="Inactivity Fee Application Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=1,
    ),
]
inactivity_fee_parameters = [
    *inactivity_fee_fee_parameters,
    *inactivity_fee_schedule_parameters,
    inactivity_fee_inactivity_flags_parameter,
]


def inactivity_fee_get_inactivity_fee_amount(
    vault: Any, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return Decimal(
        utils_get_parameter(
            vault=vault, name=inactivity_fee_PARAM_INACTIVITY_FEE, at_datetime=effective_datetime
        )
    )


def inactivity_fee__get_inactivity_internal_income_account(
    vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    return utils_get_parameter(
        vault=vault,
        name=inactivity_fee_PARAM_INACTIVITY_FEE_INCOME_ACCOUNT,
        at_datetime=effective_datetime,
    )


def inactivity_fee__are_inactivity_partial_payments_enabled(
    vault: Any, effective_datetime: Optional[datetime] = None
) -> bool:
    return utils_get_parameter(
        vault=vault,
        name=inactivity_fee_PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED,
        is_boolean=True,
        is_optional=True,
        default_value=False,
        at_datetime=effective_datetime,
    )


def inactivity_fee_event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=inactivity_fee_APPLICATION_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{inactivity_fee_APPLICATION_EVENT}_AST"],
        )
    ]


def inactivity_fee_scheduled_events(
    *, vault: Any, start_datetime: datetime
) -> dict[str, ScheduledEvent]:
    """
    Creates monthly scheduled event for inactivity fee application
    :param vault: Vault object to retrieve application frequency and schedule params
    :param start_datetime: date to start schedules from e.g. account creation
    :return: dict of inactivity fee application scheduled events
    """
    scheduled_event = utils_monthly_scheduled_event(
        vault=vault,
        start_datetime=start_datetime,
        parameter_prefix=inactivity_fee_INACTIVITY_FEE_APPLICATION_PREFIX,
    )
    return {inactivity_fee_APPLICATION_EVENT: scheduled_event}


def inactivity_fee_apply(
    vault: Any,
    effective_datetime: datetime,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    available_balance_feature: Optional[deposit_interfaces_AvailableBalance] = None,
) -> list[CustomInstruction]:
    """
    Gets inactivity fees to apply on the account.

    :param vault: vault object of the account whose fee is being assessed
    :param effective_datetime: date and time of hook being run
    :param denomination: the denomination of the paper statement fee, if not provided the
    'denomination' parameter is retrieved
    :param balances: Account balances, if not provided balances will be retrieved using the
    EFFECTIVE_OBSERVATION_FETCHER
    :param available_balance_feature: Interface to calculate the available balance for the account
    using a custom definition
    :return: Custom Instruction to apply the inactivity fee
    """
    inactivity_fee_amount = inactivity_fee_get_inactivity_fee_amount(
        vault=vault, effective_datetime=effective_datetime
    )
    posting_instructions: list[CustomInstruction] = []
    if Decimal(inactivity_fee_amount) > 0:
        inactivity_fee_income_account = inactivity_fee__get_inactivity_internal_income_account(
            vault=vault
        )
        if denomination is None:
            denomination = common_parameters_get_denomination_parameter(vault=vault)
        fee_instructions = fees_fee_custom_instruction(
            customer_account_id=vault.account_id,
            denomination=denomination,
            amount=inactivity_fee_amount,
            internal_account=inactivity_fee_income_account,
            instruction_details={
                "description": "Monthly Inactivity Fee Application",
                "event": inactivity_fee_APPLICATION_EVENT,
            },
        )
        if (
            inactivity_fee__are_inactivity_partial_payments_enabled(
                vault=vault, effective_datetime=effective_datetime
            )
            and fee_instructions
        ):
            if balances is None:
                balances = vault.get_balances_observation(
                    fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
                ).balances
            posting_instructions.extend(
                partial_fee_charge_partial_fee(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    fee_custom_instruction=fee_instructions[0],
                    fee_details=inactivity_fee_PARTIAL_FEE_DETAILS,
                    balances=balances,
                    denomination=denomination,
                    available_balance_feature=available_balance_feature,
                )
            )
        else:
            posting_instructions.extend(fee_instructions)
    return posting_instructions


def inactivity_fee_is_account_inactive(vault: Any, effective_datetime: datetime) -> bool:
    return utils_is_flag_in_list_applied(
        vault=vault,
        parameter_name=inactivity_fee_PARAM_INACTIVITY_FLAGS,
        effective_datetime=effective_datetime,
    )


inactivity_fee_PARTIAL_FEE_DETAILS = deposit_interfaces_PartialFeeCollection(
    outstanding_fee_address=inactivity_fee_OUTSTANDING_INACTIVITY_FEE_TRACKER,
    fee_type="Partial Inactivity Fee",
    get_internal_account_parameter=inactivity_fee__get_inactivity_internal_income_account,
)

# Objects below have been imported from:
#    maintenance_fees.py
# md5:456e15ca85c98e6672f750a126c306ad

maintenance_fees_APPLY_MONTHLY_FEE_EVENT = "APPLY_MONTHLY_FEE"
maintenance_fees_APPLY_ANNUAL_FEE_EVENT = "APPLY_ANNUAL_FEE"
maintenance_fees_MONTHLY = "monthly"
maintenance_fees_ANNUALLY = "annually"
maintenance_fees_MAINTENANCE_FEE_APPLICATION_PREFIX = "maintenance_fee_application"
maintenance_fees_OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER = (
    "outstanding_monthly_maintenance_fee_tracker"
)
maintenance_fees_PARAM_MAINTENANCE_FEE_APPLICATION_DAY = (
    f"{maintenance_fees_MAINTENANCE_FEE_APPLICATION_PREFIX}_day"
)
maintenance_fees_PARAM_MAINTENANCE_FEE_APPLICATION_HOUR = (
    f"{maintenance_fees_MAINTENANCE_FEE_APPLICATION_PREFIX}_hour"
)
maintenance_fees_PARAM_MAINTENANCE_FEE_APPLICATION_MINUTE = (
    f"{maintenance_fees_MAINTENANCE_FEE_APPLICATION_PREFIX}_minute"
)
maintenance_fees_PARAM_MAINTENANCE_FEE_APPLICATION_SECOND = (
    f"{maintenance_fees_MAINTENANCE_FEE_APPLICATION_PREFIX}_second"
)
maintenance_fees_PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER = "monthly_maintenance_fee_by_tier"
maintenance_fees_PARAM_MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT = (
    "monthly_maintenance_fee_income_account"
)
maintenance_fees_PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED = (
    "partial_maintenance_fee_enabled"
)
maintenance_fees_PARAM_ANNUAL_MAINTENANCE_FEE_BY_TIER = "annual_maintenance_fee_by_tier"
maintenance_fees_PARAM_ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT = (
    "annual_maintenance_fee_income_account"
)
maintenance_fees_schedule_params = [
    Parameter(
        name=maintenance_fees_PARAM_MAINTENANCE_FEE_APPLICATION_DAY,
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=ParameterLevel.INSTANCE,
        description="The day of the month on which maintenance fee is applied.If day does not exist in application month, applies on last day of month.",
        display_name="Maintenance Fees Application Day",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name=maintenance_fees_PARAM_MAINTENANCE_FEE_APPLICATION_HOUR,
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which maintenance fees are applied.",
        display_name="Maintenance Fees Application Hour",
        default_value=0,
    ),
    Parameter(
        name=maintenance_fees_PARAM_MAINTENANCE_FEE_APPLICATION_MINUTE,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which fees are applied.",
        display_name="Maintenance Fees Application Minute",
        default_value=1,
    ),
    Parameter(
        name=maintenance_fees_PARAM_MAINTENANCE_FEE_APPLICATION_SECOND,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which fees are applied.",
        display_name="Maintenance Fees Application Second",
        default_value=0,
    ),
]
maintenance_fees_annual_params = [
    Parameter(
        name=maintenance_fees_PARAM_ANNUAL_MAINTENANCE_FEE_BY_TIER,
        level=ParameterLevel.TEMPLATE,
        description="The annual fee charged for account maintenance for different tiers.",
        display_name="Annual Maintenance Fee By Tier",
        shape=StringShape(),
        default_value=dumps({"UPPER_TIER": "20", "MIDDLE_TIER": "10", "LOWER_TIER": "0"}),
    ),
    Parameter(
        name=maintenance_fees_PARAM_ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for annual maintenance fee income balance.",
        display_name="Annual Maintenance Fee Income Account",
        shape=AccountIdShape(),
        default_value="ANNUAL_MAINTENANCE_FEE_INCOME",
    ),
]
maintenance_fees_monthly_params = [
    Parameter(
        name=maintenance_fees_PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER,
        level=ParameterLevel.TEMPLATE,
        description="The monthly maintenance fee by account tier",
        display_name="Monthly Maintenance Fee By Tier",
        shape=StringShape(),
        default_value=dumps({"UPPER_TIER": "20", "MIDDLE_TIER": "10", "LOWER_TIER": "5"}),
    ),
    Parameter(
        name=maintenance_fees_PARAM_MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for monthly maintenance fee income balance.",
        display_name="Monthly Maintenance Fee Income Account",
        shape=AccountIdShape(),
        default_value="MONTHLY_MAINTENANCE_FEE_INCOME",
    ),
    Parameter(
        name=maintenance_fees_PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED,
        shape=OptionalShape(shape=common_parameters_BooleanShape),
        level=ParameterLevel.TEMPLATE,
        description="Toggles partial payments for monthly maintenance fee",
        display_name="Monthly Maintenance Partial Fees Enabled",
        default_value=OptionalValue(common_parameters_BooleanValueFalse),
    ),
]
maintenance_fees_parameters = [
    *maintenance_fees_annual_params,
    *maintenance_fees_monthly_params,
    *maintenance_fees_schedule_params,
]


def maintenance_fees_event_types(
    *, product_name: str, frequency: str
) -> list[SmartContractEventType]:
    """
    Creates monthly or annual event to apply maintenance fees
    :param product_name: the name of the product to create the event
    :param frequency: the frequency to create the monthly or annual event
    :return: Smart contract event type to scheduled event
    """
    if frequency == maintenance_fees_MONTHLY:
        event_name = maintenance_fees_APPLY_MONTHLY_FEE_EVENT
    elif frequency == maintenance_fees_ANNUALLY:
        event_name = maintenance_fees_APPLY_ANNUAL_FEE_EVENT
    else:
        return []
    return [
        SmartContractEventType(
            name=event_name, scheduler_tag_ids=[f"{product_name.upper()}_{event_name}_AST"]
        )
    ]


def maintenance_fees_scheduled_events(
    *, vault: Any, start_datetime: datetime, frequency: str
) -> dict[str, ScheduledEvent]:
    """
    Create monthly or annual scheduled event to apply maintenance fees
    :param vault: vault object for the account that requires the schedule
    :param start_datetime: Start datetime to create the schedule event
    :param frequency: frequency to create the monthly or annual schedule event
    :return: Schedule events for the monthly or annual maintenance fees
    """
    schedule_day = int(
        utils_get_parameter(vault, name=maintenance_fees_PARAM_MAINTENANCE_FEE_APPLICATION_DAY)
    )
    if frequency == maintenance_fees_MONTHLY:
        event_name = maintenance_fees_APPLY_MONTHLY_FEE_EVENT
        maintenance_fee_schedule = {
            event_name: utils_monthly_scheduled_event(
                vault=vault,
                start_datetime=start_datetime + relativedelta(months=1),
                parameter_prefix=maintenance_fees_MAINTENANCE_FEE_APPLICATION_PREFIX,
                day=schedule_day,
            )
        }
    elif frequency == maintenance_fees_ANNUALLY:
        event_name = maintenance_fees_APPLY_ANNUAL_FEE_EVENT
        next_schedule_datetime = utils_get_next_schedule_date(
            start_date=start_datetime,
            schedule_frequency=maintenance_fees_ANNUALLY,
            intended_day=schedule_day,
        )
        schedule_expression = utils_get_schedule_expression_from_parameters(
            vault=vault,
            parameter_prefix=maintenance_fees_MAINTENANCE_FEE_APPLICATION_PREFIX,
            day=next_schedule_datetime.day,
            month=next_schedule_datetime.month,
            year=None
            if int(next_schedule_datetime.month) != 2
            or (int(next_schedule_datetime.month) == 2 and schedule_day < 29)
            else next_schedule_datetime.year,
        )
        maintenance_fee_schedule = {
            event_name: ScheduledEvent(
                start_datetime=start_datetime + relativedelta(years=1),
                expression=schedule_expression,
            )
        }
    else:
        return {}
    return maintenance_fee_schedule


def maintenance_fees_apply_monthly_fee(
    *,
    vault: Any,
    effective_datetime: datetime,
    monthly_fee_waive_conditions: Optional[list[deposit_interfaces_WaiveFeeCondition]] = None,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    available_balance_feature: Optional[deposit_interfaces_AvailableBalance] = None,
) -> list[CustomInstruction]:
    """
    Gets monthly maintenance fees and the account where it will be credited.
    :param vault: Vault object for the account getting the fee assessed
    :param denomination: the denomination of the paper statement fee, if not provided the
    'denomination' parameter is retrieved
    :param balances: Account balances, if not provided balances will be retrieved using the
    EFFECTIVE_OBSERVATION_FETCHER_ID
    :param available_balance_feature: Interface to calculate the available balance for the account
    using a custom definition
    :return: Custom instructions to generate posting for monthly maintenance fees
    """
    if any(
        (
            f.waive_fees(vault=vault, effective_datetime=effective_datetime)
            for f in monthly_fee_waive_conditions or []
        )
    ):
        return []
    maintenance_fee_income_account = maintenance_fees__get_monthly_internal_income_account(
        vault=vault, effective_datetime=effective_datetime
    )
    monthly_maintenance_fee_tiers = maintenance_fees__get_monthly_maintenance_fee_tiers(
        vault=vault, effective_datetime=effective_datetime
    )
    tier = account_tiers_get_account_tier(vault)
    maintenance_fee_monthly = Decimal(
        account_tiers_get_tiered_parameter_value_based_on_account_tier(
            tiered_parameter=monthly_maintenance_fee_tiers, tier=tier, convert=Decimal
        )
        or 0
    )
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(
            vault=vault, effective_datetime=effective_datetime
        )
    fee_custom_instructions = fees_fee_custom_instruction(
        customer_account_id=vault.account_id,
        denomination=denomination,
        amount=maintenance_fee_monthly,
        internal_account=maintenance_fee_income_account,
        instruction_details={
            "description": "Monthly maintenance fee",
            "event": maintenance_fees_APPLY_MONTHLY_FEE_EVENT,
        },
    )
    if (
        maintenance_fees__are_monthly_partial_payments_enabled(
            vault=vault, effective_datetime=effective_datetime
        )
        and fee_custom_instructions
    ):
        if balances is None:
            balances = vault.get_balances_observation(
                fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
            ).balances
        return partial_fee_charge_partial_fee(
            vault=vault,
            effective_datetime=effective_datetime,
            fee_custom_instruction=fee_custom_instructions[0],
            fee_details=maintenance_fees_PARTIAL_FEE_DETAILS,
            balances=balances,
            denomination=denomination,
            available_balance_feature=available_balance_feature,
        )
    return fee_custom_instructions


def maintenance_fees_apply_annual_fee(
    *, vault: Any, effective_datetime: datetime
) -> list[CustomInstruction]:
    """
    Gets annual maintenance fees and the account where it will be credited.
    :param vault: Vault object for the account getting the fee assessed
    :return: Custom instructions to generate posting for annual maintenance fees
    """
    annual_maintenance_fee_income_account = maintenance_fees__get_annual_internal_income_account(
        vault=vault, effective_datetime=effective_datetime
    )
    annual_maintenance_fee_tiers = maintenance_fees__get_annual_maintenance_fee_tiers(
        vault=vault, effective_datetime=effective_datetime
    )
    tier = account_tiers_get_account_tier(vault)
    maintenance_fee_annual = Decimal(
        account_tiers_get_tiered_parameter_value_based_on_account_tier(
            tiered_parameter=annual_maintenance_fee_tiers, tier=tier, convert=Decimal
        )
        or 0
    )
    denomination = common_parameters_get_denomination_parameter(
        vault=vault, effective_datetime=effective_datetime
    )
    return fees_fee_custom_instruction(
        customer_account_id=vault.account_id,
        denomination=denomination,
        amount=maintenance_fee_annual,
        internal_account=annual_maintenance_fee_income_account,
        instruction_details={
            "description": "Annual maintenance fee",
            "event": maintenance_fees_APPLY_ANNUAL_FEE_EVENT,
        },
    )


def maintenance_fees_update_next_annual_schedule_execution(
    *, vault: Any, effective_datetime: datetime
) -> Optional[UpdateAccountEventTypeDirective]:
    """
    Update next annual scheduled execution with intended month not february

    :param vault: Vault object to retrieve interest application params
    :param effective_datetime: datetime the schedule is running
    :return: optional update event directive
    """
    schedule_day = int(
        utils_get_parameter(vault, name=maintenance_fees_PARAM_MAINTENANCE_FEE_APPLICATION_DAY)
    )
    if int(effective_datetime.month) != 2 or (
        int(effective_datetime.month) == 2 and schedule_day < 29
    ):
        return None
    new_schedule = maintenance_fees_scheduled_events(
        vault=vault, start_datetime=effective_datetime, frequency=maintenance_fees_ANNUALLY
    )
    return UpdateAccountEventTypeDirective(
        event_type=maintenance_fees_APPLY_ANNUAL_FEE_EVENT,
        expression=new_schedule[maintenance_fees_APPLY_ANNUAL_FEE_EVENT].expression,
    )


def maintenance_fees__get_monthly_internal_income_account(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    return utils_get_parameter(
        vault=vault,
        name=maintenance_fees_PARAM_MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
        at_datetime=effective_datetime,
    )


def maintenance_fees__get_monthly_maintenance_fee_tiers(
    vault: Any, effective_datetime: Optional[datetime]
) -> dict[str, str]:
    return utils_get_parameter(
        vault=vault,
        name=maintenance_fees_PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER,
        at_datetime=effective_datetime,
        is_json=True,
    )


def maintenance_fees__get_annual_internal_income_account(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    return utils_get_parameter(
        vault=vault,
        name=maintenance_fees_PARAM_ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
        at_datetime=effective_datetime,
    )


def maintenance_fees__get_annual_maintenance_fee_tiers(
    vault: Any, effective_datetime: Optional[datetime]
) -> dict[str, str]:
    return utils_get_parameter(
        vault=vault,
        name=maintenance_fees_PARAM_ANNUAL_MAINTENANCE_FEE_BY_TIER,
        at_datetime=effective_datetime,
        is_json=True,
    )


def maintenance_fees__are_monthly_partial_payments_enabled(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> bool:
    return utils_get_parameter(
        vault=vault,
        name=maintenance_fees_PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED,
        at_datetime=effective_datetime,
        is_boolean=True,
        is_optional=True,
        default_value=False,
    )


maintenance_fees_PARTIAL_FEE_DETAILS = deposit_interfaces_PartialFeeCollection(
    outstanding_fee_address=maintenance_fees_OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER,
    fee_type="Partial Monthly Maintenance Fee",
    get_internal_account_parameter=maintenance_fees__get_monthly_internal_income_account,
)

# Objects below have been imported from:
#    minimum_monthly_balance.py
# md5:81fe207637feb88594e4bccd69d4149e

minimum_monthly_balance_APPLY_MINIMUM_MONTHLY_BALANCE_EVENT = "APPLY_MINIMUM_BALANCE_FEE"
minimum_monthly_balance_OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER = (
    "outstanding_minimum_balance_fee_tracker"
)
minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE = "minimum_balance_fee"
minimum_monthly_balance_PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER = (
    "minimum_balance_threshold_by_tier"
)
minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE_INCOME_ACCOUNT = (
    "minimum_balance_fee_income_account"
)
minimum_monthly_balance_MINIMUM_BALANCE_FEE_PREFIX = "minimum_balance_fee_application"
minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE_DAY = (
    f"{minimum_monthly_balance_MINIMUM_BALANCE_FEE_PREFIX}_day"
)
minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE_HOUR = (
    f"{minimum_monthly_balance_MINIMUM_BALANCE_FEE_PREFIX}_hour"
)
minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE_MINUTE = (
    f"{minimum_monthly_balance_MINIMUM_BALANCE_FEE_PREFIX}_minute"
)
minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE_SECOND = (
    f"{minimum_monthly_balance_MINIMUM_BALANCE_FEE_PREFIX}_second"
)
minimum_monthly_balance_PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED = (
    f"partial_{minimum_monthly_balance_MINIMUM_BALANCE_FEE_PREFIX}_enabled"
)
minimum_monthly_balance_parameters = [
    Parameter(
        name=minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE,
        level=ParameterLevel.TEMPLATE,
        description="The fee charged if the minimum balance falls below the threshold.",
        display_name="Minimum Balance Fee",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name=minimum_monthly_balance_PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER,
        level=ParameterLevel.TEMPLATE,
        description="The monthly minimum mean balance threshold by account tier",
        display_name="Minimum Balance Threshold By Tier",
        shape=StringShape(),
        default_value=dumps({"UPPER_TIER": "25", "MIDDLE_TIER": "75", "LOWER_TIER": "100"}),
    ),
    Parameter(
        name=minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for minimum balance fee income balance.",
        display_name="Minimum Balance Fee Income Account",
        shape=AccountIdShape(),
        default_value="MINIMUM_BALANCE_FEE_INCOME",
    ),
    Parameter(
        name=minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE_DAY,
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=ParameterLevel.INSTANCE,
        description="The day of the month on which minimum balance fee is applied.If day does not exist in application month, applies on last day of month.",
        display_name="Minimum Balance Fee Application Day",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name=minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which minimum balance fee is applied.",
        display_name="Minimum Balance Fee Application Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which minimum balance fee is applied.",
        display_name="Minimum Balance Fee Application Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which minimum balance fee is applied.",
        display_name="Minimum Balance Fee Application Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=1,
    ),
    Parameter(
        name=minimum_monthly_balance_PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED,
        shape=OptionalShape(shape=common_parameters_BooleanShape),
        level=ParameterLevel.TEMPLATE,
        description="Enables / Disables partial payments for the Minimum Balance Fee.",
        display_name="Partial Minimum Balance Fees Enabled",
        default_value=OptionalValue(common_parameters_BooleanValueFalse),
    ),
]


def minimum_monthly_balance_event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=minimum_monthly_balance_APPLY_MINIMUM_MONTHLY_BALANCE_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{minimum_monthly_balance_APPLY_MINIMUM_MONTHLY_BALANCE_EVENT}_AST"
            ],
        )
    ]


def minimum_monthly_balance_scheduled_events(
    *, vault: Any, start_datetime: datetime
) -> dict[str, ScheduledEvent]:
    """
    Creates scheduled event for minimum balance fee application
    :param vault: Vault object to retrieve application frequency and schedule params
    :param start_datetime: date to start schedules from e.g. account creation or loan start date
    :return: dict of minimum balance fee application scheduled events
    """
    scheduled_event = utils_monthly_scheduled_event(
        vault=vault,
        start_datetime=start_datetime,
        parameter_prefix=minimum_monthly_balance_MINIMUM_BALANCE_FEE_PREFIX,
    )
    return {minimum_monthly_balance_APPLY_MINIMUM_MONTHLY_BALANCE_EVENT: scheduled_event}


def minimum_monthly_balance_apply_minimum_balance_fee(
    *,
    vault: Any,
    effective_datetime: datetime,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    available_balance_feature: Optional[deposit_interfaces_AvailableBalance] = None,
) -> list[CustomInstruction]:
    """
    Retrieves the minimum balance fee, minimum balance fee income account,
    and minimum balance threshold.
    The balance is calculated by averaging the monthly balance
    of the account in the currency at the point when the fee is charged.

    :param vault: vault object of the account whose fee is being assessed
    :param effective_datetime: date and time of hook being run
    :param denomination: the denomination of the paper statement fee, if not provided the
    'denomination' parameter is retrieved
    :param balances: Account balances, if not provided balances will be retrieved using the
    PREVIOUS_EOD_OBSERVATION_FETCHERS ids for the average balance calculations and the
    EFFECTIVE_OBSERVATION_FETCHER_ID for partial fee charging considerations.
    :param available_balance_feature: Callable to calculate the available balance for the account
    using a custom definition
    :return: Custom Instruction to apply the minimum monthly balance fee
    """
    fee_custom_instructions: list[CustomInstruction] = []
    minimum_balance_fee = minimum_monthly_balance__get_minimum_balance_fee(
        vault=vault, effective_datetime=effective_datetime
    )
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    if minimum_balance_fee > Decimal("0") and (
        not minimum_monthly_balance__is_monthly_mean_balance_above_threshold(
            vault=vault, effective_datetime=effective_datetime, denomination=denomination
        )
    ):
        minimum_balance_fee_income_account = (
            minimum_monthly_balance_get_minimum_balance_fee_income_account(
                vault=vault, effective_datetime=effective_datetime
            )
        )
        fee_custom_instructions = fees_fee_custom_instruction(
            customer_account_id=vault.account_id,
            denomination=denomination,
            amount=minimum_balance_fee,
            internal_account=minimum_balance_fee_income_account,
            instruction_details={
                "description": "Minimum balance fee",
                "event": minimum_monthly_balance_APPLY_MINIMUM_MONTHLY_BALANCE_EVENT,
            },
        )
        if (
            minimum_monthly_balance_are_partial_payments_enabled(
                vault=vault, effective_datetime=effective_datetime
            )
            and fee_custom_instructions
        ):
            if balances is None:
                balances = vault.get_balances_observation(
                    fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
                ).balances
            return partial_fee_charge_partial_fee(
                vault=vault,
                effective_datetime=effective_datetime,
                fee_custom_instruction=fee_custom_instructions[0],
                fee_details=minimum_monthly_balance_PARTIAL_FEE_DETAILS,
                balances=balances,
                denomination=denomination,
                available_balance_feature=available_balance_feature,
            )
    return fee_custom_instructions


def minimum_monthly_balance__is_monthly_mean_balance_above_threshold(
    *, vault: Any, effective_datetime: datetime, denomination: Optional[str] = None
) -> bool:
    """
    Retrieves the minimum balance fee, minimum balance fee income account,
    and minimum balance threshold.
    The balance is calculated by averaging the monthly balance
    of the account in the currency at the point when the fee is charged.
    :param vault: vault object of the account whose fee is being assessed
    :param effective_datetime: date and time of hook being run
    :param denomination: the denomination of the minimum monthly fee
    :return: bool True if balance is above requirement
    """
    minimum_balance_threshold_tiers = (
        minimum_monthly_balance__get_minimum_balance_threshold_by_tier(
            vault=vault, effective_datetime=effective_datetime
        )
    )
    tier = account_tiers_get_account_tier(vault, effective_datetime)
    minimum_balance_threshold = Decimal(
        account_tiers_get_tiered_parameter_value_based_on_account_tier(
            tiered_parameter=minimum_balance_threshold_tiers, tier=tier, convert=Decimal
        )
        or Decimal("0")
    )
    if minimum_balance_threshold > Decimal("0"):
        creation_date = vault.get_account_creation_datetime().date()
        period_start = (effective_datetime - relativedelta(months=1)).date()
        if period_start <= creation_date:
            period_start = creation_date + relativedelta(days=1)
        num_days = (effective_datetime.date() - period_start).days
        balances_to_average = [
            utils_balance_at_coordinates(
                balances=vault.get_balances_observation(
                    fetcher_id=fetchers_PREVIOUS_EOD_OBSERVATION_FETCHERS[i].fetcher_id
                ).balances,
                denomination=denomination
                or common_parameters_get_denomination_parameter(vault=vault),
            )
            for i in range(num_days)
        ]
        monthly_mean_balance = utils_average_balance(balances=balances_to_average)
        if monthly_mean_balance >= minimum_balance_threshold:
            return True
        return False
    return True


def minimum_monthly_balance_get_minimum_balance_fee_income_account(
    vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    return str(
        utils_get_parameter(
            vault,
            name=minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
            at_datetime=effective_datetime,
        )
    )


def minimum_monthly_balance_are_partial_payments_enabled(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> bool:
    return utils_get_parameter(
        vault=vault,
        name=minimum_monthly_balance_PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED,
        at_datetime=effective_datetime,
        is_boolean=True,
        default_value=False,
        is_optional=True,
    )


def minimum_monthly_balance__get_minimum_balance_fee(
    vault: Any, effective_datetime: datetime
) -> Decimal:
    return Decimal(
        utils_get_parameter(
            vault,
            name=minimum_monthly_balance_PARAM_MINIMUM_BALANCE_FEE,
            at_datetime=effective_datetime,
        )
    )


def minimum_monthly_balance__get_minimum_balance_threshold_by_tier(
    vault: Any, effective_datetime: datetime
) -> dict[str, str]:
    return utils_get_parameter(
        vault=vault,
        name=minimum_monthly_balance_PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER,
        at_datetime=effective_datetime,
        is_json=True,
    )


minimum_monthly_balance_PARTIAL_FEE_DETAILS = deposit_interfaces_PartialFeeCollection(
    outstanding_fee_address=minimum_monthly_balance_OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
    fee_type="Partial Minimum Balance Fee",
    get_internal_account_parameter=minimum_monthly_balance_get_minimum_balance_fee_income_account,
)

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
#    overdraft_limit.py
# md5:3d738630f9d3c485ceaa99c0f1ca7da5

overdraft_limit_PARAM_ARRANGED_OVERDRAFT_AMOUNT = "arranged_overdraft_amount"
overdraft_limit_PARAM_UNARRANGED_OVERDRAFT_AMOUNT = "unarranged_overdraft_amount"
overdraft_limit_parameters = [
    Parameter(
        name=overdraft_limit_PARAM_ARRANGED_OVERDRAFT_AMOUNT,
        level=ParameterLevel.INSTANCE,
        description="An agreed amount which the customer may use to borrow funds",
        display_name="Arranged Overdraft Amount",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        shape=OptionalShape(shape=NumberShape(min_value=0, step=Decimal("0.01"))),
        default_value=OptionalValue(Decimal("0.00")),
    ),
    Parameter(
        name=overdraft_limit_PARAM_UNARRANGED_OVERDRAFT_AMOUNT,
        level=ParameterLevel.INSTANCE,
        description="An additional borrowing amount which may be used to validate balance checks when going beyond the agreed borrowing limit",
        display_name="Unarranged Overdraft Amount",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        shape=OptionalShape(shape=NumberShape(min_value=0, step=Decimal("0.01"))),
        default_value=OptionalValue(Decimal("0.00")),
    ),
]


def overdraft_limit_validate(
    *,
    vault: Any,
    postings: utils_PostingInstructionListAlias,
    denomination: str,
    balances: Optional[BalanceDefaultDict] = None,
) -> Optional[Rejection]:
    """
    Return Rejection if the posting will cause the current balance to exceed the total overdraft
    amount.
    The total overdraft is calculated by summing the arranged and unarranged overdraft amounts.
    :param vault: Vault object for the account whose overdraft limit is being validated
    :param postings: posting instructions being processed
    :param denomination: denomination
    :param balances: latest account balances available, if not provided will be retrieved
    using the LIVE_BALANCES_BOF_ID fetcher id
    :return : rejection if criteria not satisfied
    """
    balances = (
        balances
        or vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    )
    posting_amount = Decimal(
        sum(
            (
                utils_get_available_balance(balances=posting.balances(), denomination=denomination)
                for posting in postings
            )
        )
    )
    total_available_balance = overdraft_limit_get_overdraft_available_balance(
        vault=vault, balances=balances, denomination=denomination
    )
    if posting_amount < 0 and abs(posting_amount) > total_available_balance:
        return Rejection(
            message=f"Postings total {denomination} {posting_amount}, which exceeds the available balance of {denomination} {total_available_balance}.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
    return None


def overdraft_limit_get_overdraft_available_balance(
    vault: Any, balances: Optional[BalanceDefaultDict] = None, denomination: Optional[str] = None
) -> Decimal:
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    return (
        utils_get_available_balance(balances=balances, denomination=denomination)
        + overdraft_limit_get_arranged_overdraft_amount(vault=vault)
        + overdraft_limit_get_unarranged_overdraft_amount(vault=vault)
    )


def overdraft_limit_get_arranged_overdraft_amount(vault: Any) -> Decimal:
    return Decimal(
        utils_get_parameter(
            vault=vault,
            name=overdraft_limit_PARAM_ARRANGED_OVERDRAFT_AMOUNT,
            is_optional=True,
            default_value=Decimal("0"),
        )
    )


def overdraft_limit_get_unarranged_overdraft_amount(vault: Any) -> Decimal:
    return Decimal(
        utils_get_parameter(
            vault=vault,
            name=overdraft_limit_PARAM_UNARRANGED_OVERDRAFT_AMOUNT,
            is_optional=True,
            default_value=Decimal("0"),
        )
    )


overdraft_limit_OverdraftLimitAvailableBalance = deposit_interfaces_AvailableBalance(
    calculate=overdraft_limit_get_overdraft_available_balance
)

# Objects below have been imported from:
#    unarranged_overdraft_fee.py
# md5:86f7cac57a4c97b1ce6cb02f63653806

unarranged_overdraft_fee_ACCRUAL_EVENT = "ACCRUE_UNARRANGED_OVERDRAFT_FEE"
unarranged_overdraft_fee_APPLICATION_EVENT = "APPLY_UNARRANGED_OVERDRAFT_FEE"
unarranged_overdraft_fee_OVERDRAFT_FEE = "UNARRANGED_OVERDRAFT_FEE"
unarranged_overdraft_fee_FEE_APPLICATION_PREFIX = "unarranged_overdraft_fee_application"
unarranged_overdraft_fee_PARAM_FEE_APPLICATION_DAY = (
    f"{unarranged_overdraft_fee_FEE_APPLICATION_PREFIX}_day"
)
unarranged_overdraft_fee_PARAM_FEE_APPLICATION_HOUR = (
    f"{unarranged_overdraft_fee_FEE_APPLICATION_PREFIX}_hour"
)
unarranged_overdraft_fee_PARAM_FEE_APPLICATION_MINUTE = (
    f"{unarranged_overdraft_fee_FEE_APPLICATION_PREFIX}_minute"
)
unarranged_overdraft_fee_PARAM_FEE_APPLICATION_SECOND = (
    f"{unarranged_overdraft_fee_FEE_APPLICATION_PREFIX}_second"
)
unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE = "unarranged_overdraft_fee"
unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_CAP = "unarranged_overdraft_fee_cap"
unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT = (
    "unarranged_overdraft_fee_income_account"
)
unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT = (
    "unarranged_overdraft_fee_receivable_account"
)
unarranged_overdraft_fee_application_schedule_parameters = [
    Parameter(
        name=unarranged_overdraft_fee_PARAM_FEE_APPLICATION_DAY,
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=ParameterLevel.INSTANCE,
        description="The day of the month on which unarranged overdraft fee is applied. If day does not exist in application month, applies on last day of month.",
        display_name="Interest Application Day",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name=unarranged_overdraft_fee_PARAM_FEE_APPLICATION_HOUR,
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which unarranged overdraft fee is applied.",
        display_name="Unarranged Overdraft Fee Application Hour",
        default_value=0,
    ),
    Parameter(
        name=unarranged_overdraft_fee_PARAM_FEE_APPLICATION_MINUTE,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which unarranged overdraft fee is applied.",
        display_name="Unarranged Overdraft Fee Application Minute",
        default_value=1,
    ),
    Parameter(
        name=unarranged_overdraft_fee_PARAM_FEE_APPLICATION_SECOND,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which unarranged overdraft fee is applied.",
        display_name="Unarranged Overdraft Fee Application Second",
        default_value=0,
    ),
]
unarranged_overdraft_fee_feature_parameters = [
    Parameter(
        name=unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE,
        level=ParameterLevel.TEMPLATE,
        description="The daily fee charged for being in unarranged overdraft.",
        display_name="Unarranged Overdraft Fee",
        shape=OptionalShape(shape=NumberShape(min_value=0, step=Decimal("0.01"))),
        default_value=OptionalValue(Decimal("5.00")),
    ),
    Parameter(
        name=unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_CAP,
        level=ParameterLevel.TEMPLATE,
        description="A monthly cap on accumulated fees for entering an unarranged overdraft.",
        display_name="Unarranged Overdraft Fee Cap",
        shape=OptionalShape(shape=NumberShape(min_value=0, step=Decimal("0.01"))),
        default_value=OptionalValue(Decimal("15.00")),
    ),
    Parameter(
        name=unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for overdraft fee income balance.",
        display_name="Unarranged Overdraft Fee Income Account",
        shape=OptionalShape(shape=AccountIdShape()),
        default_value=OptionalValue("UNARRANGED_OVERDRAFT_FEE_INCOME"),
    ),
    Parameter(
        name=unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for overdraft fee receivable account.",
        display_name="Unarranged Overdraft Fee Receivable Account",
        shape=OptionalShape(shape=AccountIdShape()),
        default_value=OptionalValue("UNARRANGED_OVERDRAFT_FEE_RECEIVABLE"),
    ),
]


def unarranged_overdraft_fee_application_event_types(
    product_name: str,
) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=unarranged_overdraft_fee_APPLICATION_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{unarranged_overdraft_fee_APPLICATION_EVENT}_AST"
            ],
        )
    ]


def unarranged_overdraft_fee_application_scheduled_events(
    vault: Any, start_datetime: datetime
) -> dict[str, ScheduledEvent]:
    start_datetime_midnight = start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        unarranged_overdraft_fee_APPLICATION_EVENT: utils_monthly_scheduled_event(
            vault=vault,
            start_datetime=start_datetime_midnight + relativedelta(months=1),
            parameter_prefix=unarranged_overdraft_fee_FEE_APPLICATION_PREFIX,
        )
    }


def unarranged_overdraft_fee_accrue_fee(*, vault: Any) -> list[CustomInstruction]:
    """
    Returns posting instructions to accrue unarranged overdraft fee
    or empty list if no fee should be accrued or any of the feature parameters not set.
    Overdraft fee is fully accrued if there is no overdraft fee cap or the cap doesn't exceeded
    or  partially accrued if part of new fee sums up to the overdraft fee cap.
    :param vault: Vault object for the account whose overdraft limit is being validated
    :return: posting instructions or empty list
    """
    if not utils_are_optional_parameters_set(
        vault=vault,
        parameters=[
            overdraft_limit_PARAM_ARRANGED_OVERDRAFT_AMOUNT,
            overdraft_limit_PARAM_UNARRANGED_OVERDRAFT_AMOUNT,
            unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE,
            unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT,
            unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
        ],
    ):
        return []
    denomination: str = utils_get_parameter(vault=vault, name="denomination")
    balances = vault.get_balances_observation(fetcher_id=fetchers_EOD_FETCHER_ID).balances
    effective_balance = utils_balance_at_coordinates(balances=balances, denomination=denomination)
    if effective_balance > 0:
        return []
    arranged_overdraft_amount: Decimal = utils_get_parameter(
        vault=vault,
        name=overdraft_limit_PARAM_ARRANGED_OVERDRAFT_AMOUNT,
        is_optional=True,
        default_value=Decimal("0"),
    )
    if abs(effective_balance) <= arranged_overdraft_amount:
        return []
    overdraft_fee: Decimal = utils_get_parameter(
        vault=vault,
        name=unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE,
        is_optional=True,
        default_value=Decimal("0"),
    )
    overdraft_fee_cap: Decimal = utils_get_parameter(
        vault=vault,
        name=unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_CAP,
        is_optional=True,
        default_value=None,
    )
    overdraft_fee_receivable_account: str = utils_get_parameter(
        vault=vault,
        name=unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
        is_optional=True,
        default_value="",
    )
    unarranged_overdraft_fee_balance = utils_balance_at_coordinates(
        balances=balances, address=unarranged_overdraft_fee_OVERDRAFT_FEE, denomination=denomination
    )
    if overdraft_fee_cap:
        unarranged_overdraft_fee_balance = abs(unarranged_overdraft_fee_balance)
        if unarranged_overdraft_fee_balance >= overdraft_fee_cap:
            return []
        if unarranged_overdraft_fee_balance + overdraft_fee > overdraft_fee_cap:
            overdraft_fee = overdraft_fee_cap - unarranged_overdraft_fee_balance
    return accruals_accrual_custom_instruction(
        customer_account=vault.account_id,
        customer_address=unarranged_overdraft_fee_OVERDRAFT_FEE,
        amount=Decimal(overdraft_fee),
        internal_account=overdraft_fee_receivable_account,
        payable=False,
        denomination=denomination,
        instruction_details={
            "description": f"Daily unarranged overdraft fee of {overdraft_fee} {denomination}",
            "event": unarranged_overdraft_fee_ACCRUAL_EVENT,
        },
    )


def unarranged_overdraft_fee_apply_fee(
    *, vault: Any, balances: Optional[BalanceDefaultDict] = None, denomination: Optional[str] = None
) -> list[CustomInstruction]:
    """
    Creates posting instructions to to apply the fees, if required.
    Empty list if there is no fee to apply or feature parameters aren't set
    :param vault: Vault object
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the EFFECTIVE_OBSERVATION_FETCHER_ID
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :return: posting instructions
    """
    if not utils_are_optional_parameters_set(
        vault=vault,
        parameters=[
            overdraft_limit_PARAM_ARRANGED_OVERDRAFT_AMOUNT,
            overdraft_limit_PARAM_UNARRANGED_OVERDRAFT_AMOUNT,
            unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE,
            unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT,
            unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
        ],
    ):
        return []
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    unarranged_overdraft_fee_balance = utils_balance_at_coordinates(
        balances=balances, address=unarranged_overdraft_fee_OVERDRAFT_FEE, denomination=denomination
    )
    posting_instructions: list[CustomInstruction] = []
    if unarranged_overdraft_fee_balance != 0:
        overdraft_fee_receivable_account: str = utils_get_parameter(
            vault=vault,
            name=unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
            is_optional=True,
            default_value="",
        )
        overdraft_fee_income_account: str = utils_get_parameter(
            vault=vault,
            name=unarranged_overdraft_fee_PARAM_UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT,
            is_optional=True,
            default_value="",
        )
        unarranged_overdraft_fee_balance = abs(unarranged_overdraft_fee_balance)
        posting_instructions.extend(
            accruals_accrual_application_custom_instruction(
                customer_account=vault.account_id,
                denomination=denomination,
                application_amount=Decimal(unarranged_overdraft_fee_balance),
                accrual_amount=Decimal(unarranged_overdraft_fee_balance),
                accrual_customer_address=unarranged_overdraft_fee_OVERDRAFT_FEE,
                accrual_internal_account=overdraft_fee_receivable_account,
                application_internal_account=overdraft_fee_income_account,
                application_customer_address=DEFAULT_ADDRESS,
                payable=False,
                instruction_details={
                    "description": f"Unarranged overdraft fee of {unarranged_overdraft_fee_balance} {denomination} applied.",
                    "event": unarranged_overdraft_fee_APPLICATION_EVENT,
                },
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
#    excess_fee.py
# md5:40f00431a2d3490cbafb177c369b6dfe

excess_fee_INSTRUCTION_DETAIL_KEY = "TRANSACTION_TYPE"
excess_fee_PARAM_EXCESS_FEE = "excess_fee"
excess_fee_PARAM_PERMITTED_WITHDRAWALS = "permitted_withdrawals"
excess_fee_PARAM_EXCESS_FEE_MONITORED_TRANSACTION_TYPE = "excess_fee_monitored_transaction_type"
excess_fee_PARAM_EXCESS_FEE_ACCOUNT = "excess_fee_income_account"
excess_fee_parameters = [
    Parameter(
        name=excess_fee_PARAM_EXCESS_FEE,
        level=ParameterLevel.TEMPLATE,
        description="Fee charged for every withdrawal that exceeds the monthly withdrawal limit.",
        display_name="Excess Fee",
        shape=OptionalShape(shape=NumberShape(min_value=0, step=Decimal("0.01"))),
        default_value=OptionalValue(Decimal("0.00")),
    ),
    Parameter(
        name=excess_fee_PARAM_PERMITTED_WITHDRAWALS,
        level=ParameterLevel.TEMPLATE,
        description="Number of monthly permitted withdrawals. Please note that only transactions with the specified transaction type are counted towards this excess fee.",
        display_name="Permitted Withdrawals",
        shape=OptionalShape(shape=NumberShape(min_value=0, step=1)),
        default_value=OptionalValue(0),
    ),
    Parameter(
        name=excess_fee_PARAM_EXCESS_FEE_MONITORED_TRANSACTION_TYPE,
        level=ParameterLevel.TEMPLATE,
        description="Transaction type being monitored to determine how many operations of this type occurred in the current calendar month period. This parameter will only be used for the  assessment of the excessive withdrawal fee.",
        display_name="Monitored Transaction Type",
        shape=OptionalShape(shape=StringShape()),
        default_value=OptionalValue(""),
    ),
    Parameter(
        name=excess_fee_PARAM_EXCESS_FEE_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for excess fee income balance.",
        display_name="Withdrawal Excess Fee Account",
        shape=AccountIdShape(),
        default_value="EXCESS_FEE_INCOME_ACCOUNT",
    ),
]


def excess_fee_apply(
    *,
    vault: Any,
    proposed_client_transactions: dict[str, ClientTransaction],
    monthly_client_transactions: Optional[dict[str, ClientTransaction]] = None,
    effective_datetime: datetime,
    denomination: str,
    account_type: str = "",
) -> list[CustomInstruction]:
    """
    Check number of posting instructions have occurred month to date and return fees if the
    withdrawal limit has been exceeded.
    Only transactions with instruction details that has a key matching "INSTRUCTION_DETAIL_KEY"
    parameter, with a value matching "PARAM_MONITORED_TRANSACTION_TYPE" param are eligible for
    this excess withdrawal fee.

    :param vault: vault object used to retrieve parameters
    :param proposed_client_transactions: proposed client transactions to process
    :param monthly_client_transactions: monthly client transactions to process
    :param effective_datetime: datetime used to filter client transactions
    :param denomination: denomination used to filter posting instructions
    :param account_type: the account type
    :return: excess fee posting instructions
    """
    transaction_type: str = utils_get_parameter(
        vault,
        excess_fee_PARAM_EXCESS_FEE_MONITORED_TRANSACTION_TYPE,
        is_optional=True,
        default_value="",
    )
    if not transaction_type:
        return []
    filtered_proposed_posting_instructions = (
        client_transaction_utils_extract_debits_by_instruction_details_key(
            denomination=denomination,
            client_transactions=proposed_client_transactions,
            client_transaction_ids_to_ignore=[],
            cutoff_datetime=effective_datetime,
            key=excess_fee_INSTRUCTION_DETAIL_KEY,
            value=transaction_type,
        )
    )
    if not filtered_proposed_posting_instructions:
        return []
    excess_fee_amount = Decimal(
        utils_get_parameter(vault, excess_fee_PARAM_EXCESS_FEE, is_optional=True, default_value=0)
    )
    permitted_withdrawals = int(
        utils_get_parameter(
            vault, excess_fee_PARAM_PERMITTED_WITHDRAWALS, is_optional=True, default_value=-1
        )
    )
    if excess_fee_amount <= Decimal("0") or permitted_withdrawals < 0:
        return []
    if not monthly_client_transactions:
        monthly_client_transactions = vault.get_client_transactions(
            fetcher_id=fetchers_MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID
        )
    filtered_monthly_posting_instructions = (
        client_transaction_utils_extract_debits_by_instruction_details_key(
            denomination=denomination,
            client_transactions=monthly_client_transactions,
            client_transaction_ids_to_ignore=list(proposed_client_transactions.keys()),
            cutoff_datetime=effective_datetime
            + relativedelta(day=1, hour=0, minute=0, second=0, microsecond=0),
            key=excess_fee_INSTRUCTION_DETAIL_KEY,
            value=transaction_type,
        )
    )
    current_withdrawals = len(filtered_monthly_posting_instructions)
    proposed_withdrawals = len(filtered_proposed_posting_instructions)
    proposed_exceeding_withdrawals = (
        proposed_withdrawals + current_withdrawals - permitted_withdrawals
    )
    if proposed_exceeding_withdrawals <= 0:
        return []
    if current_withdrawals > permitted_withdrawals:
        proposed_exceeding_withdrawals = proposed_withdrawals
    excess_fee_income_account = utils_get_parameter(vault, excess_fee_PARAM_EXCESS_FEE_ACCOUNT)
    return fees_fee_custom_instruction(
        customer_account_id=vault.account_id,
        denomination=denomination,
        amount=excess_fee_amount * proposed_exceeding_withdrawals,
        internal_account=excess_fee_income_account,
        instruction_details=utils_standard_instruction_details(
            description=f"Proposed withdrawals exceeded permitted limit by {proposed_exceeding_withdrawals}",
            event_type="APPLY_EXCESS_FEES",
            gl_impacted=True,
            account_type=account_type,
        ),
    )


# Objects below have been imported from:
#    interest_accrual_common.py
# md5:162f41e06e859ca63b416be0f14ea285

interest_accrual_common_ACCRUAL_EVENT = "ACCRUE_INTEREST"
interest_accrual_common_ACCRUED_INTEREST_PAYABLE = "ACCRUED_INTEREST_PAYABLE"
interest_accrual_common_ACCRUED_INTEREST_RECEIVABLE = "ACCRUED_INTEREST_RECEIVABLE"
interest_accrual_common_PARAM_DAYS_IN_YEAR = "days_in_year"
interest_accrual_common_PARAM_ACCRUAL_PRECISION = "accrual_precision"
interest_accrual_common_INTEREST_ACCRUAL_PREFIX = "interest_accrual"
interest_accrual_common_PARAM_INTEREST_ACCRUAL_HOUR = (
    f"{interest_accrual_common_INTEREST_ACCRUAL_PREFIX}_hour"
)
interest_accrual_common_PARAM_INTEREST_ACCRUAL_MINUTE = (
    f"{interest_accrual_common_INTEREST_ACCRUAL_PREFIX}_minute"
)
interest_accrual_common_PARAM_INTEREST_ACCRUAL_SECOND = (
    f"{interest_accrual_common_INTEREST_ACCRUAL_PREFIX}_second"
)
interest_accrual_common_PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT = "accrued_interest_payable_account"
interest_accrual_common_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = (
    "accrued_interest_receivable_account"
)
interest_accrual_common_days_in_year_param = Parameter(
    name=interest_accrual_common_PARAM_DAYS_IN_YEAR,
    shape=UnionShape(
        items=[
            UnionItem(key="actual", display_name="Actual"),
            UnionItem(key="366", display_name="366"),
            UnionItem(key="365", display_name="365"),
            UnionItem(key="360", display_name="360"),
        ]
    ),
    level=ParameterLevel.TEMPLATE,
    description='The days in the year for interest accrual calculation. Valid values are "actual", "366", "365", "360"',
    display_name="Interest Accrual Days In Year",
    default_value=UnionItemValue(key="365"),
)
interest_accrual_common_accrual_precision_param = Parameter(
    name=interest_accrual_common_PARAM_ACCRUAL_PRECISION,
    level=ParameterLevel.TEMPLATE,
    description="Precision needed for interest accruals.",
    display_name="Interest Accrual Precision",
    shape=NumberShape(min_value=0, max_value=15, step=1),
    default_value=Decimal(5),
)
interest_accrual_common_accrual_parameters = [
    interest_accrual_common_days_in_year_param,
    interest_accrual_common_accrual_precision_param,
]
interest_accrual_common_schedule_parameters = [
    Parameter(
        name=interest_accrual_common_PARAM_INTEREST_ACCRUAL_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which interest is accrued.",
        display_name="Interest Accrual Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=Decimal("0"),
    ),
    Parameter(
        name=interest_accrual_common_PARAM_INTEREST_ACCRUAL_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which interest is accrued.",
        display_name="Interest Accrual Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=Decimal("0"),
    ),
    Parameter(
        name=interest_accrual_common_PARAM_INTEREST_ACCRUAL_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which interest is accrued.",
        display_name="Interest Accrual Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=Decimal("0"),
    ),
]
interest_accrual_common_accrued_interest_payable_account_param = Parameter(
    name=interest_accrual_common_PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for accrued interest payable balance.",
    display_name="Accrued Interest Payable Account",
    shape=AccountIdShape(),
    default_value=interest_accrual_common_ACCRUED_INTEREST_PAYABLE,
)
interest_accrual_common_accrued_interest_receivable_account_param = Parameter(
    name=interest_accrual_common_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for accrued interest receivable balance.",
    display_name="Accrued Interest Receivable Account",
    shape=AccountIdShape(),
    default_value=interest_accrual_common_ACCRUED_INTEREST_RECEIVABLE,
)


def interest_accrual_common_event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=interest_accrual_common_ACCRUAL_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{interest_accrual_common_ACCRUAL_EVENT}_AST"
            ],
        )
    ]


def interest_accrual_common_scheduled_events(
    vault: Any, start_datetime: datetime, skip: Optional[Union[bool, ScheduleSkip]] = None
) -> dict[str, ScheduledEvent]:
    skip = skip or False
    return {
        interest_accrual_common_ACCRUAL_EVENT: utils_daily_scheduled_event(
            vault=vault,
            start_datetime=start_datetime,
            parameter_prefix=interest_accrual_common_INTEREST_ACCRUAL_PREFIX,
            skip=skip,
        )
    }


def interest_accrual_common_get_days_in_year_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    return str(
        utils_get_parameter(
            vault=vault,
            name=interest_accrual_common_PARAM_DAYS_IN_YEAR,
            at_datetime=effective_datetime,
            is_union=True,
        )
    )


def interest_accrual_common_get_accrual_precision_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils_get_parameter(
            vault=vault,
            name=interest_accrual_common_PARAM_ACCRUAL_PRECISION,
            at_datetime=effective_datetime,
        )
    )


def interest_accrual_common_get_accrued_interest_payable_account_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    return str(
        utils_get_parameter(
            vault,
            name=interest_accrual_common_PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT,
            at_datetime=effective_datetime,
        )
    )


def interest_accrual_common_get_accrued_interest_receivable_account_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    return str(
        utils_get_parameter(
            vault,
            name=interest_accrual_common_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            at_datetime=effective_datetime,
        )
    )


# Objects below have been imported from:
#    interest_application.py
# md5:74a54e31869154fa3fa44450d229ebbf

interest_application_APPLICATION_EVENT = "APPLY_INTEREST"
interest_application_ACCRUED_INTEREST_PAYABLE_ADDRESS = "ACCRUED_INTEREST_PAYABLE"
interest_application_ACCRUED_INTEREST_RECEIVABLE_ADDRESS = "ACCRUED_INTEREST_RECEIVABLE"
interest_application_INTEREST_APPLICATION_PREFIX = "interest_application"
interest_application_PARAM_INTEREST_APPLICATION_DAY = (
    f"{interest_application_INTEREST_APPLICATION_PREFIX}_day"
)
interest_application_PARAM_INTEREST_APPLICATION_FREQUENCY = (
    f"{interest_application_INTEREST_APPLICATION_PREFIX}_frequency"
)
interest_application_PARAM_INTEREST_APPLICATION_HOUR = (
    f"{interest_application_INTEREST_APPLICATION_PREFIX}_hour"
)
interest_application_PARAM_INTEREST_APPLICATION_MINUTE = (
    f"{interest_application_INTEREST_APPLICATION_PREFIX}_minute"
)
interest_application_PARAM_INTEREST_APPLICATION_SECOND = (
    f"{interest_application_INTEREST_APPLICATION_PREFIX}_second"
)
interest_application_schedule_params = [
    Parameter(
        name=interest_application_PARAM_INTEREST_APPLICATION_DAY,
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=ParameterLevel.INSTANCE,
        description="The day of the month on which interest is applied. If day does not exist in application month, applies on last day of month.",
        display_name="Interest Application Day",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name=interest_application_PARAM_INTEREST_APPLICATION_FREQUENCY,
        level=ParameterLevel.TEMPLATE,
        description="The frequency at which interest is applied.",
        display_name="Interest Application Frequency",
        shape=UnionShape(
            items=[
                UnionItem(key=utils_MONTHLY, display_name="Monthly"),
                UnionItem(key=utils_QUARTERLY, display_name="Quarterly"),
                UnionItem(key=utils_ANNUALLY, display_name="Annually"),
            ]
        ),
        default_value=UnionItemValue(key=utils_MONTHLY),
    ),
    Parameter(
        name=interest_application_PARAM_INTEREST_APPLICATION_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which interest is applied.",
        display_name="Interest Application Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=interest_application_PARAM_INTEREST_APPLICATION_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which interest is applied.",
        display_name="Interest Application Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=interest_application_PARAM_INTEREST_APPLICATION_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which interest is applied.",
        display_name="Interest Application Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=1,
    ),
]
interest_application_PARAM_APPLICATION_PRECISION = "application_precision"
interest_application_PARAM_INTEREST_PAID_ACCOUNT = "interest_paid_account"
interest_application_PARAM_INTEREST_RECEIVED_ACCOUNT = "interest_received_account"
interest_application_parameters = [
    Parameter(
        name=interest_application_PARAM_APPLICATION_PRECISION,
        level=ParameterLevel.TEMPLATE,
        description="Precision needed for interest applications.",
        display_name="Interest Application Precision",
        shape=NumberShape(min_value=0, max_value=15, step=1),
        default_value=2,
    ),
    Parameter(
        name=interest_application_PARAM_INTEREST_PAID_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for interest paid.",
        display_name="Interest Paid Account",
        shape=AccountIdShape(),
        default_value="APPLIED_INTEREST_PAID",
    ),
    Parameter(
        name=interest_application_PARAM_INTEREST_RECEIVED_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for interest received.",
        display_name="Interest Received Account",
        shape=AccountIdShape(),
        default_value="APPLIED_INTEREST_RECEIVED",
    ),
    *interest_application_schedule_params,
]


def interest_application_event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=interest_application_APPLICATION_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{interest_application_APPLICATION_EVENT}_AST"
            ],
        )
    ]


def interest_application_scheduled_events(
    *, vault: Any, reference_datetime: datetime
) -> dict[str, ScheduledEvent]:
    """
    Creates list of execution schedules for interest application
    :param vault: Vault object to retrieve application frequency and schedule params
    :param reference_datetime: Anchor datetime to determine when schedules should start from
    e.g. account creation datetime
    :return: dict of interest application scheduled events
    """
    application_frequency: str = utils_get_parameter(
        vault, name=interest_application_PARAM_INTEREST_APPLICATION_FREQUENCY, is_union=True
    )
    start_datetime = reference_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    if application_frequency == utils_MONTHLY:
        start_datetime = start_datetime + relativedelta(days=1)
        scheduled_event = utils_monthly_scheduled_event(
            vault=vault,
            start_datetime=start_datetime,
            parameter_prefix=interest_application_INTEREST_APPLICATION_PREFIX,
        )
    else:
        schedule_day = int(
            utils_get_parameter(vault, name=interest_application_PARAM_INTEREST_APPLICATION_DAY)
        )
        next_datetime = utils_get_next_schedule_date(
            start_date=start_datetime,
            schedule_frequency=application_frequency,
            intended_day=schedule_day,
        )
        schedule_expression = utils_get_schedule_expression_from_parameters(
            vault=vault,
            parameter_prefix=interest_application_INTEREST_APPLICATION_PREFIX,
            day=next_datetime.day,
            month=next_datetime.month,
            year=None
            if application_frequency == utils_ANNUALLY
            and (
                int(next_datetime.month) != 2
                or (int(next_datetime.month) == 2 and schedule_day < 29)
            )
            else next_datetime.year,
        )
        if application_frequency == utils_ANNUALLY:
            start_datetime = start_datetime + relativedelta(months=1)
        else:
            start_datetime = start_datetime + relativedelta(days=1)
        scheduled_event = ScheduledEvent(
            start_datetime=start_datetime, expression=schedule_expression
        )
    return {interest_application_APPLICATION_EVENT: scheduled_event}


def interest_application_apply_interest(
    *, vault: Any, account_type: str = "", balances: Optional[BalanceDefaultDict] = None
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
    interest_paid_account: str = utils_get_parameter(
        vault, name=interest_application_PARAM_INTEREST_PAID_ACCOUNT
    )
    interest_received_account: str = utils_get_parameter(
        vault, name=interest_application_PARAM_INTEREST_RECEIVED_ACCOUNT
    )
    accrued_interest_payable_account = (
        interest_accrual_common_get_accrued_interest_payable_account_parameter(vault=vault)
    )
    accrued_interest_receivable_account = (
        interest_accrual_common_get_accrued_interest_receivable_account_parameter(vault=vault)
    )
    application_precision: int = utils_get_parameter(
        vault, name=interest_application_PARAM_APPLICATION_PRECISION
    )
    denomination: str = utils_get_parameter(vault, name="denomination")
    balances = (
        balances
        or vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    )
    if amount_accrued_receivable := utils_sum_balances(
        balances=balances,
        addresses=[interest_application_ACCRUED_INTEREST_RECEIVABLE_ADDRESS],
        denomination=denomination,
    ):
        rounded_accrual = utils_round_decimal(amount_accrued_receivable, application_precision)
        posting_instructions.extend(
            accruals_accrual_application_custom_instruction(
                customer_account=vault.account_id,
                denomination=denomination,
                application_amount=abs(rounded_accrual),
                accrual_amount=abs(amount_accrued_receivable),
                instruction_details=utils_standard_instruction_details(
                    description=f"Apply {rounded_accrual} {denomination} interest of {amount_accrued_receivable} rounded to {application_precision} and consolidate {amount_accrued_receivable} {denomination} to {vault.account_id}",
                    event_type=interest_application_APPLICATION_EVENT,
                    gl_impacted=True,
                    account_type=account_type,
                ),
                accrual_customer_address=interest_application_ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                accrual_internal_account=accrued_interest_receivable_account,
                application_customer_address=DEFAULT_ADDRESS,
                application_internal_account=interest_received_account,
                payable=False,
            )
        )
    if amount_accrued_payable := utils_sum_balances(
        balances=balances,
        addresses=[interest_application_ACCRUED_INTEREST_PAYABLE_ADDRESS],
        denomination=denomination,
    ):
        rounded_accrual = utils_round_decimal(amount_accrued_payable, application_precision)
        posting_instructions.extend(
            accruals_accrual_application_custom_instruction(
                customer_account=vault.account_id,
                denomination=denomination,
                application_amount=abs(rounded_accrual),
                accrual_amount=abs(amount_accrued_payable),
                instruction_details=utils_standard_instruction_details(
                    description=f"Apply {rounded_accrual} {denomination} interest of {amount_accrued_payable} rounded to {application_precision} and consolidate {amount_accrued_payable} {denomination} to {vault.account_id}",
                    event_type=interest_application_APPLICATION_EVENT,
                    gl_impacted=True,
                    account_type=account_type,
                ),
                accrual_customer_address=interest_application_ACCRUED_INTEREST_PAYABLE_ADDRESS,
                accrual_internal_account=accrued_interest_payable_account,
                application_customer_address=DEFAULT_ADDRESS,
                application_internal_account=interest_paid_account,
                payable=True,
            )
        )
    return posting_instructions


def interest_application_update_next_schedule_execution(
    *, vault: Any, effective_datetime: datetime
) -> Optional[UpdateAccountEventTypeDirective]:
    """
    Update next scheduled execution if frequency not monthly or annually with
    intended month not february

    :param vault: Vault object to retrieve interest application params
    :param effective_datetime: datetime the schedule is running
    :return: optional update event directive
    """
    application_frequency: str = utils_get_parameter(
        vault, interest_application_PARAM_INTEREST_APPLICATION_FREQUENCY, is_union=True
    )
    if application_frequency == utils_MONTHLY:
        return None
    else:
        schedule_day = int(
            utils_get_parameter(vault, name=interest_application_PARAM_INTEREST_APPLICATION_DAY)
        )
        if application_frequency == utils_ANNUALLY and (
            int(effective_datetime.month) != 2
            or (int(effective_datetime.month) == 2 and schedule_day < 29)
        ):
            return None
        new_schedule = interest_application_scheduled_events(
            vault=vault, reference_datetime=effective_datetime
        )
        return UpdateAccountEventTypeDirective(
            event_type=interest_application_APPLICATION_EVENT,
            expression=new_schedule[interest_application_APPLICATION_EVENT].expression,
        )


# Objects below have been imported from:
#    overdraft_interest.py
# md5:51604abdf6ccc34cab443e3a6294dc11

overdraft_interest_OVERDRAFT_ACCRUED_INTEREST = "OVERDRAFT_ACCRUED_INTEREST"
overdraft_interest_OVERDRAFT_ACCRUAL_EVENT = "ACCRUE_OVERDRAFT_DAILY_FEE"
overdraft_interest_OVERDRAFT_APPLICATION_EVENT = "APPLY_OVERDRAFT_DAILY_FEE"
overdraft_interest_overdraft_interest_free_buffer_days_fetchers = [
    fetchers_PREVIOUS_EOD_1_FETCHER,
    fetchers_PREVIOUS_EOD_2_FETCHER,
    fetchers_PREVIOUS_EOD_3_FETCHER,
    fetchers_PREVIOUS_EOD_4_FETCHER,
    fetchers_PREVIOUS_EOD_5_FETCHER,
]
overdraft_interest_overdraft_accrual_data_fetchers = [
    fetchers_EOD_FETCHER,
    *overdraft_interest_overdraft_interest_free_buffer_days_fetchers,
]
overdraft_interest_PARAM_OVERDRAFT_INTEREST_RATE = "overdraft_interest_rate"
overdraft_interest_PARAM_OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT = (
    "overdraft_interest_receivable_account"
)
overdraft_interest_PARAM_OVERDRAFT_INTEREST_RECEIVED_ACCOUNT = "overdraft_interest_received_account"
overdraft_interest_PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_DAYS = "interest_free_buffer_days"
overdraft_interest_PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_AMOUNT = "interest_free_buffer_amount"
overdraft_interest_parameters = [
    Parameter(
        name=overdraft_interest_PARAM_OVERDRAFT_INTEREST_RATE,
        level=ParameterLevel.TEMPLATE,
        description="The yearly rate at which overdraft interest is accrued.",
        display_name="Overdraft Interest Rate",
        shape=OptionalShape(
            shape=NumberShape(
                min_value=Decimal("0"), max_value=Decimal("1"), step=Decimal("0.0001")
            )
        ),
        default_value=OptionalValue(Decimal("0.05")),
    ),
    Parameter(
        name=overdraft_interest_PARAM_OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for overdraft accrued interest receivable balance.",
        display_name="Overdraft Accrued Interest Receivable Account",
        shape=OptionalShape(shape=AccountIdShape()),
        default_value=OptionalValue("accrued_interest_receivable_account"),
    ),
    Parameter(
        name=overdraft_interest_PARAM_OVERDRAFT_INTEREST_RECEIVED_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for overdraft accrued interest received balance.",
        display_name="Overdraft Accrued Interest Received Account",
        shape=OptionalShape(shape=AccountIdShape()),
        default_value=OptionalValue("accrued_interest_received_account"),
    ),
    Parameter(
        name=overdraft_interest_PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_DAYS,
        level=ParameterLevel.TEMPLATE,
        description="Maximum number of consecutive days that the account can benefit from the interest free buffer. If the number is exceeded, the buffer no longer applies and overdraft interest is accrued on the entire overdrawn balance. The count is reset by the account balance being positive at end of day. When not defined, the buffer amount always applies. See Interest Free Buffer Amount for more details.",
        display_name="Interest Free Buffer Days",
        shape=OptionalShape(shape=NumberShape(min_value=0, max_value=5, step=1)),
        default_value=OptionalValue(0),
    ),
    Parameter(
        name=overdraft_interest_PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_AMOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Courtesy amount that will be added to the customer’s EOD overdraft balance reducing or eliminating the overdraft interest accrued. If it is not explicitly set, the buffer amount will be equal to the overdraft balance for the duration of the buffer period. See Interest Free Buffer Days for more details.",
        display_name="Interest Free Buffer Amount",
        shape=OptionalShape(shape=NumberShape(min_value=0, step=1)),
        default_value=OptionalValue(0),
    ),
]


def overdraft_interest_accrue_interest(
    *, vault: Any, effective_datetime: datetime, account_type: str = ""
) -> list[CustomInstruction]:
    """
    Creates the posting instructions to accrue overdraft interest on the balances specified by
    the denomination and addresses parameters.

    This requires 6 days of balances for the interest_free_buffer_days comparison.
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param effective_datetime: the effective date and time to use for retrieving balances to accrue
    overdraft interest on
    :account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :return: the overdraft accrual posting instructions
    """
    yearly_interest_rate: Decimal = utils_get_parameter(
        vault=vault,
        name=overdraft_interest_PARAM_OVERDRAFT_INTEREST_RATE,
        is_optional=True,
        default_value=Decimal("0"),
    )
    overdraft_interest_receivable_account: str = utils_get_parameter(
        vault=vault,
        name=overdraft_interest_PARAM_OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT,
        is_optional=True,
        default_value="",
    )
    if yearly_interest_rate > 0 and overdraft_interest_receivable_account:
        interest_free_amount = Decimal(
            utils_get_parameter(
                vault=vault,
                name=overdraft_interest_PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_AMOUNT,
                is_optional=True,
                default_value=0,
            )
        )
        interest_free_days = int(
            utils_get_parameter(
                vault=vault,
                name=overdraft_interest_PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_DAYS,
                is_optional=True,
                default_value=0,
            )
        )
        denomination = common_parameters_get_denomination_parameter(
            vault=vault, effective_datetime=effective_datetime
        )
        accrual_balance = overdraft_interest__calculate_accrual_balance(
            interest_free_amount=interest_free_amount,
            interest_free_days=interest_free_days,
            denomination=denomination,
            observations=overdraft_interest__retrieve_eod_observations(vault=vault),
        )
        if accrual_balance < 0:
            days_in_year = str(utils_get_parameter(vault, "days_in_year", is_union=True))
            rounding_precision: int = utils_get_parameter(vault, "accrual_precision")
            day_rate = utils_yearly_to_daily_rate(
                effective_date=effective_datetime,
                yearly_rate=yearly_interest_rate,
                days_in_year=days_in_year,
            )
            accrual_amount_rounded = utils_round_decimal(
                abs(accrual_balance) * day_rate, decimal_places=rounding_precision
            )
            return accruals_accrual_custom_instruction(
                customer_account=vault.account_id,
                customer_address=overdraft_interest_OVERDRAFT_ACCRUED_INTEREST,
                denomination=denomination,
                amount=accrual_amount_rounded,
                internal_account=overdraft_interest_receivable_account,
                payable=False,
                instruction_details=utils_standard_instruction_details(
                    description=f"Accrual on overdraft balance of {accrual_balance:.2f} {denomination} at {yearly_interest_rate * 100:.2f}%",
                    event_type=overdraft_interest_OVERDRAFT_ACCRUAL_EVENT,
                    gl_impacted=True,
                    account_type=account_type,
                ),
            )
    return []


def overdraft_interest__retrieve_eod_observations(*, vault: Any) -> list[BalancesObservation]:
    """
    Retrieves the last 6 End-Of-Day Observations balances to be used in the determination of what
    should be the overdraft balance used in the interest calculation.
    Positions:[0] - current EOD, [1] - Previous Day, [2] - 2 Days Ago, ... , [5] - 5 Days Ago

    :param vault: the vault object used to for retrieving the balance data
    :return: list of observation balances ordered in reverse chronological order
    """
    return [
        vault.get_balances_observation(fetcher_id=fetcher.fetcher_id)
        for fetcher in overdraft_interest_overdraft_accrual_data_fetchers
    ]


def overdraft_interest__calculate_accrual_balance(
    *,
    interest_free_amount: Decimal,
    interest_free_days: int,
    denomination: str,
    observations: list[BalancesObservation],
) -> Decimal:
    """
    Factor in optional interest free buffer days and amount to determine the balance on which the
    customer should be charged overdraft interest. Returns 0 if calculated amount is positive.
    :param interest_free_amount: positive amount to be added to EOD balance, if set to zero the
    buffer amount is considered disabled.
    :param interest_free_days: number of consecutive days that the interest free buffer amount
    should be applied, if set to zero this restriction is disabled and the interest free buffer
    amount will always added to the overdraft balance.
    :param denomination: the denomination of the balances and the interest accruals
    :param observations: EOD observation balances, in a reverse chronological order
    :return: the balance to use in overdraft interest accruals, should always be less or equal zero
    """
    end_of_day_balance = utils_balance_at_coordinates(
        balances=observations[0].balances, denomination=denomination
    )
    if end_of_day_balance >= 0:
        return Decimal("0")
    buffered_end_of_day_balance = end_of_day_balance + interest_free_amount
    if interest_free_days == 0:
        if buffered_end_of_day_balance >= 0:
            return Decimal("0")
        else:
            return buffered_end_of_day_balance
    highest_amount = max(
        (
            utils_balance_at_coordinates(balances=observation.balances, denomination=denomination)
            for observation in observations[1 : interest_free_days + 1]
        )
    )
    if highest_amount >= 0:
        if buffered_end_of_day_balance >= 0 or interest_free_amount == 0:
            return Decimal("0")
        else:
            return buffered_end_of_day_balance
    else:
        return end_of_day_balance


def overdraft_interest_apply_interest(
    *, vault: Any, account_type: str = ""
) -> list[CustomInstruction]:
    """
    Creates the postings instructions to apply the accrued overdraft interest and additional
    postings required to zero the accrued overdraft interest remainders.
    Note: The standard interest application parameters are followed for overdraft interest
    application (frequency, day, hour, minute, second and precision)

    :param vault: the vault object to use to for retrieving data and instructing directives
    :param account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :return: the overdraft interest application related posting instructions
    """
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    balance_observation = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    )
    accrued_overdraft_interest = utils_balance_at_coordinates(
        balances=balance_observation.balances,
        address=overdraft_interest_OVERDRAFT_ACCRUED_INTEREST,
        denomination=denomination,
    )
    if accrued_overdraft_interest == 0:
        return []
    overdraft_interest_receivable_account: str = utils_get_parameter(
        vault=vault,
        name=overdraft_interest_PARAM_OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT,
        is_optional=True,
        default_value="",
    )
    overdraft_interest_received_account: str = utils_get_parameter(
        vault=vault,
        name=overdraft_interest_PARAM_OVERDRAFT_INTEREST_RECEIVED_ACCOUNT,
        is_optional=True,
        default_value="",
    )
    if overdraft_interest_receivable_account and overdraft_interest_received_account:
        application_precision: int = utils_get_parameter(vault, "application_precision")
        application_amount_rounded = utils_round_decimal(
            amount=accrued_overdraft_interest, decimal_places=application_precision
        )
        return accruals_accrual_application_custom_instruction(
            customer_account=vault.account_id,
            denomination=denomination,
            accrual_amount=abs(accrued_overdraft_interest),
            accrual_customer_address=overdraft_interest_OVERDRAFT_ACCRUED_INTEREST,
            accrual_internal_account=overdraft_interest_receivable_account,
            application_amount=abs(application_amount_rounded),
            application_customer_address=DEFAULT_ADDRESS,
            application_internal_account=overdraft_interest_received_account,
            payable=False,
            instruction_details=utils_standard_instruction_details(
                description=f"Apply {application_amount_rounded} {denomination} overdraft interest of {accrued_overdraft_interest} rounded to {application_precision} DP to {vault.account_id}.",
                event_type=overdraft_interest_OVERDRAFT_APPLICATION_EVENT,
                gl_impacted=True,
                account_type=account_type,
            ),
        )
    return []


def overdraft_interest_get_interest_reversal_postings(
    *,
    vault: Any,
    event_name: str,
    account_type: str = "",
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Reverse any accrued overdraft interest and apply back to the internal account.
    During account closure, any overdraft interest that has not been applied should return back to
    the bank's internal account.
    :param vault: the vault object used to create interest reversal posting instruction
    :param event_name: the name of the event reversing any accrue interest
    :param account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the EFFECTIVE_OBSERVATION_FETCHER_ID
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :return: the accrued interest reversal posting instructions
    """
    overdraft_interest_receivable_account: str = utils_get_parameter(
        vault=vault,
        name=overdraft_interest_PARAM_OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT,
        is_optional=True,
        default_value="",
    )
    if not overdraft_interest_receivable_account:
        return []
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    accrued_overdraft_interest = utils_balance_at_coordinates(
        balances=balances,
        address=overdraft_interest_OVERDRAFT_ACCRUED_INTEREST,
        denomination=denomination,
    )
    if accrued_overdraft_interest == 0:
        return []
    return accruals_accrual_custom_instruction(
        customer_account=vault.account_id,
        customer_address=overdraft_interest_OVERDRAFT_ACCRUED_INTEREST,
        denomination=denomination,
        amount=abs(accrued_overdraft_interest),
        internal_account=overdraft_interest_receivable_account,
        payable=False,
        instruction_details=utils_standard_instruction_details(
            description=f"Reversing {accrued_overdraft_interest} {denomination} of accrued overdraft interest.",
            event_type=event_name,
            gl_impacted=True,
            account_type=account_type,
        ),
        reversal=True,
    )


# Objects below have been imported from:
#    deposit_interest_accrual_common.py
# md5:ea292c7687b8c4bbde10425c6a0ee4df


def deposit_interest_accrual_common_get_accrual_capital(
    vault: Any,
    *,
    balances: Optional[BalanceDefaultDict] = None,
    capital_addresses: Optional[list[str]] = None,
) -> Decimal:
    """
    Calculates the sum of balances at EOD that will be used to accrue interest on.

    :param vault: the vault object to use to for retrieving data and instructing directives
    :param balances: the balances to sum, EOD balances will be fetched if not provided
    :param capital_addresses: list of balance addresses that will be summed up to provide
    the amount to accrue interest on. Defaults to the DEFAULT_ADDRESS
    :return: the sum of balances on which interest will be accrued on
    """
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_EOD_FETCHER_ID).balances
    accrual_balance = utils_sum_balances(
        balances=balances,
        addresses=capital_addresses or [DEFAULT_ADDRESS],
        denomination=denomination,
    )
    return accrual_balance if accrual_balance > 0 else Decimal(0)


def deposit_interest_accrual_common_get_interest_reversal_postings(
    *,
    vault: Any,
    event_name: str,
    account_type: str = "",
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Reverse any accrued interest and apply back to the internal account.
    During account closure, any positively accrued interest that has not been applied
    should return back to the bank's internal account.

    :param vault: the vault object used to create interest reversal posting instructions
    :param event_name: the name of the event reversing any accrue interest
    :param account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :param balances: balances to pass through to function. If not passed in, defaults to None
    and the function will fetch balances using EFFECTIVE_OBSERVATION_FETCHER
    :param denomination:
    :return: the accrued interest reversal posting instructions
    """
    posting_instructions: list[CustomInstruction] = []
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    balances = (
        balances
        or vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    )
    accrued_interest_payable_account = (
        interest_accrual_common_get_accrued_interest_payable_account_parameter(vault=vault)
    )
    accrued_interest_receivable_account = (
        interest_accrual_common_get_accrued_interest_receivable_account_parameter(vault=vault)
    )
    if accrued_interest_receivable := utils_sum_balances(
        balances=balances,
        addresses=[interest_accrual_common_ACCRUED_INTEREST_RECEIVABLE],
        denomination=denomination,
    ):
        posting_instructions.extend(
            accruals_accrual_custom_instruction(
                customer_account=vault.account_id,
                customer_address=interest_accrual_common_ACCRUED_INTEREST_RECEIVABLE,
                denomination=denomination,
                amount=abs(accrued_interest_receivable),
                internal_account=accrued_interest_receivable_account,
                payable=False,
                instruction_details=utils_standard_instruction_details(
                    description=f"Reversing {accrued_interest_receivable} {denomination} of accrued interest",
                    event_type=event_name,
                    gl_impacted=True,
                    account_type=account_type,
                ),
                reversal=True,
            )
        )
    if accrued_interest_payable := utils_sum_balances(
        balances=balances,
        addresses=[interest_accrual_common_ACCRUED_INTEREST_PAYABLE],
        denomination=denomination,
    ):
        posting_instructions.extend(
            accruals_accrual_custom_instruction(
                customer_account=vault.account_id,
                customer_address=interest_accrual_common_ACCRUED_INTEREST_PAYABLE,
                denomination=denomination,
                amount=abs(accrued_interest_payable),
                internal_account=accrued_interest_payable_account,
                payable=True,
                instruction_details=utils_standard_instruction_details(
                    description=f"Reversing {accrued_interest_payable} {denomination} of accrued interest",
                    event_type=event_name,
                    gl_impacted=True,
                    account_type=account_type,
                ),
                reversal=True,
            )
        )
    return posting_instructions


# Objects below have been imported from:
#    tiered_interest_accrual.py
# md5:42e81e49adb9094924c5216142bcecae

tiered_interest_accrual_ACCRUAL_EVENT = interest_accrual_common_ACCRUAL_EVENT
tiered_interest_accrual_ACCRUED_INTEREST_PAYABLE = interest_accrual_common_ACCRUED_INTEREST_PAYABLE
tiered_interest_accrual_ACCRUED_INTEREST_RECEIVABLE = (
    interest_accrual_common_ACCRUED_INTEREST_RECEIVABLE
)
tiered_interest_accrual_PARAM_TIERED_INTEREST_RATES = "tiered_interest_rates"
tiered_interest_accrual_tiered_interest_rates_parameter = Parameter(
    name=tiered_interest_accrual_PARAM_TIERED_INTEREST_RATES,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="Map Of Minimum Balance To Gross Interest Rate For Positive Balances.",
    display_name="Tiered Gross Interest Rate",
    default_value=dumps(
        {
            "0.00": "0.01",
            "1000.00": "0.02",
            "3000.00": "0.035",
            "7500.00": "0.05",
            "10000.00": "0.06",
        }
    ),
)
tiered_interest_accrual_parameters = [
    tiered_interest_accrual_tiered_interest_rates_parameter,
    interest_accrual_common_accrued_interest_payable_account_param,
    interest_accrual_common_accrued_interest_receivable_account_param,
    *interest_accrual_common_accrual_parameters,
    *interest_accrual_common_schedule_parameters,
]
tiered_interest_accrual_event_types = interest_accrual_common_event_types
tiered_interest_accrual_scheduled_events = interest_accrual_common_scheduled_events
tiered_interest_accrual_get_accrual_capital = deposit_interest_accrual_common_get_accrual_capital
tiered_interest_accrual_get_interest_reversal_postings = (
    deposit_interest_accrual_common_get_interest_reversal_postings
)


def tiered_interest_accrual_get_tiered_interest_rates_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> dict[str, str]:
    return utils_get_parameter(
        vault=vault,
        name=tiered_interest_accrual_PARAM_TIERED_INTEREST_RATES,
        at_datetime=effective_datetime,
        is_json=True,
    )


def tiered_interest_accrual_accrue_interest(
    *, vault: Any, effective_datetime: datetime
) -> list[CustomInstruction]:
    """
    Creates the posting instructions to accrue interest on the balances specified by
    the denomination and capital addresses parameters
    :param vault: the vault object to use to for retrieving data and instructing directives
    :param effective_datetime: the effective date to retrieve capital balances to accrue on
    :return: the accrual posting custom instructions
    """
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    accrued_interest_payable_account = (
        interest_accrual_common_get_accrued_interest_payable_account_parameter(vault=vault)
    )
    accrued_interest_receivable_account = (
        interest_accrual_common_get_accrued_interest_receivable_account_parameter(vault=vault)
    )
    days_in_year = interest_accrual_common_get_days_in_year_parameter(vault=vault)
    rounding_precision = interest_accrual_common_get_accrual_precision_parameter(vault=vault)
    tiered_rates = tiered_interest_accrual_get_tiered_interest_rates_parameter(vault=vault)
    (accrual_amount, instruction_detail) = tiered_interest_accrual_get_tiered_accrual_amount(
        effective_balance=tiered_interest_accrual_get_accrual_capital(vault),
        effective_datetime=effective_datetime,
        tiered_interest_rates=tiered_rates,
        days_in_year=days_in_year,
        precision=rounding_precision,
    )
    instruction_details = {
        "description": instruction_detail.strip(),
        "event": tiered_interest_accrual_ACCRUAL_EVENT,
    }
    (target_customer_address, target_internal_account) = (
        (tiered_interest_accrual_ACCRUED_INTEREST_PAYABLE, accrued_interest_payable_account)
        if accrual_amount >= 0
        else (
            tiered_interest_accrual_ACCRUED_INTEREST_RECEIVABLE,
            accrued_interest_receivable_account,
        )
    )
    return accruals_accrual_custom_instruction(
        customer_account=vault.account_id,
        customer_address=target_customer_address,
        denomination=denomination,
        amount=abs(accrual_amount),
        internal_account=target_internal_account,
        payable=accrual_amount >= 0,
        instruction_details=instruction_details,
    )


def tiered_interest_accrual_get_tiered_accrual_amount(
    *,
    effective_balance: Decimal,
    effective_datetime: datetime,
    tiered_interest_rates: dict[str, str],
    days_in_year: str,
    precision: int = 5,
) -> tuple[Decimal, str]:
    """
    Calculate the amount to accrue on each balance portion by tier rate (to defined precision).
    Provide instruction details highlighting the breakdown of the tiered accrual.
    :param effective_balance: balance to accrue on
    :param effective_datetime: the date to accrue as-of. This will affect the conversion of yearly
    to daily rates if `days_in_year` is set to `actual`
    :param tiered_interest_rates: tiered interest rates parameter
    :param days_in_year: days in year parameter
    :param accrual_precision: accrual precision parameter
    :return: rounded accrual_amount and instruction_details
    """
    daily_accrual_amount = Decimal("0")
    instruction_detail = ""
    tiered_interest_rates = dict(sorted(tiered_interest_rates.items(), key=lambda x: x[1]))
    for (index, (tier_min, tier_rate)) in enumerate(tiered_interest_rates.items()):
        rate = Decimal(tier_rate)
        tier_max = tiered_interest_accrual_determine_tier_max(
            list(tiered_interest_rates.keys()), index
        )
        tier_balances = tiered_interest_accrual_determine_tier_balance(
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


def tiered_interest_accrual_determine_tier_max(
    tier_range_list: list[str], index: int
) -> Optional[Decimal]:
    return Decimal(tier_range_list[index + 1]) if index + 1 < len(tier_range_list) else None


def tiered_interest_accrual_determine_tier_balance(
    effective_balance: Decimal,
    tier_min: Optional[Decimal] = None,
    tier_max: Optional[Decimal] = None,
) -> Decimal:
    """
    Determines a tier's balance based on min and max. Min and max must be of same sign or
    zero is returned (use Decimal("-0") if required). If neither are provided, zero is returned
    :param tier_min: the minimum balance in the tier, exclusive. Any amount at or below is excluded.
    Defaults to 0 if tier_max is +ve, unbounded is tier_max is -ve
    :param tier_max: the maximum balance included in the tier, inclusive. Any amount greater is
    excluded. Defaults to Decimal("-0") if tier_min is -ve,  unbounded if tier_min is +ve
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


# Objects below have been imported from:
#    roundup_autosave.py
# md5:3564483a2719ba33b687d6d5467502e9

roundup_autosave_TRANSACTION_TYPE = "TRANSACTION_TYPE"
roundup_autosave_DEFAULT_TRANSACTION_TYPE = "PURCHASE"
roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT = "roundup_autosave_rounding_amount"
roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_ACCOUNT = "roundup_autosave_account"
roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_TRANSACTION_TYPES = "roundup_autosave_transaction_types"
roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_ACTIVE = "roundup_autosave_active"
roundup_autosave_parameters = [
    Parameter(
        name=roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT,
        level=ParameterLevel.TEMPLATE,
        description="For any given spend with the primary denomination, this is the figure to round up to: the nearest multiple higher than the transaction amount. Only used if autosave_savings_account is defined and if the transaction type is eligible (see Autosave Transaction Types)",
        display_name="Autosave Rounding Amount",
        shape=OptionalShape(shape=NumberShape(min_value=0, step=Decimal("0.01"))),
        default_value=OptionalValue(Decimal("1.00")),
    ),
    Parameter(
        name=roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_TRANSACTION_TYPES,
        level=ParameterLevel.TEMPLATE,
        description="The list of transaction types eligible for autosave. Expects a JSON-encoded list",
        display_name="Autosave Transaction Types",
        shape=OptionalShape(shape=StringShape()),
        default_value=OptionalValue(dumps([roundup_autosave_DEFAULT_TRANSACTION_TYPE])),
    ),
    Parameter(
        name=roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_ACCOUNT,
        level=ParameterLevel.INSTANCE,
        description="The account credited with Round-up Autosave amounts",
        display_name="Autosave Account",
        shape=OptionalShape(shape=AccountIdShape()),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=OptionalValue(""),
    ),
    Parameter(
        name=roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_ACTIVE,
        level=ParameterLevel.INSTANCE,
        description="Switch that controls if the Round-up autosave feature is active or disabled.",
        display_name="Round-up Autosave Active",
        shape=common_parameters_BooleanShape,
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value=common_parameters_BooleanValueTrue,
    ),
]


def roundup_autosave_apply(
    *,
    vault: Any,
    postings: utils_PostingInstructionListAlias,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> list[CustomInstruction]:
    """
    Creates the postings instructions required to perform auto save for the committed amounts.
    The feature requires the autosave_rounding_amount and autosave_savings_account to be set
    :param vault: The vault object containing parameters, etc.
    :param postings: posting instructions
    :param denomination: the default denomination of the account
    :param balances: Balances used to determine the available balance
    :return: List of CustomInstruction with postings to perform auto save transaction
    """
    if not utils_str_to_bool(
        utils_get_parameter(
            vault=vault, name=roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_ACTIVE, is_union=True
        )
    ):
        return []
    if not utils_are_optional_parameters_set(
        vault=vault,
        parameters=[
            roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT,
            roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_ACCOUNT,
        ],
    ):
        return []
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name="denomination")
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    available_balance: Decimal = utils_get_available_balance(
        balances=balances, denomination=denomination
    )
    if available_balance <= 0:
        return []
    autosave_rounding_amount: Decimal = utils_get_parameter(
        name=roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT, vault=vault, is_optional=True
    )
    autosave_savings_account: str = utils_get_parameter(
        name=roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_ACCOUNT, vault=vault, is_optional=True
    )
    autosave_transaction_types: list[str] = utils_get_parameter(
        name=roundup_autosave_PARAM_ROUNDUP_AUTOSAVE_TRANSACTION_TYPES,
        vault=vault,
        is_json=True,
        is_optional=True,
        default_value=[roundup_autosave_DEFAULT_TRANSACTION_TYPE],
    )
    autosave_amount = Decimal("0")
    instruction_description = ""
    posting_result: list[Posting] = []
    for posting in postings:
        posting_transaction_type = posting.instruction_details.get(
            roundup_autosave_TRANSACTION_TYPE
        )
        if posting_transaction_type not in autosave_transaction_types:
            continue
        posting_balance = utils_balance_at_coordinates(
            balances=posting.balances(), denomination=denomination, phase=Phase.COMMITTED
        )
        if posting_balance >= 0:
            continue
        posting_balance = abs(posting_balance)
        remainder = posting_balance % autosave_rounding_amount
        if remainder > 0:
            debit_amount = autosave_rounding_amount - remainder
            if autosave_amount + debit_amount <= available_balance:
                autosave_amount += debit_amount
                posting_result.extend(
                    utils_create_postings(
                        amount=debit_amount,
                        denomination=denomination,
                        debit_account=vault.account_id,
                        credit_account=autosave_savings_account,
                    )
                )
                instruction_description += f"Roundup Autosave: {denomination} {debit_amount} using round up to {denomination} {autosave_rounding_amount} for transfer of {denomination} {posting_balance}\n "
    if posting_result:
        return [
            CustomInstruction(
                postings=posting_result,
                instruction_details={
                    "description": instruction_description,
                    "event": "ROUNDUP_AUTOSAVE",
                },
                override_all_restrictions=True,
            )
        ]
    return []


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


def maximum_daily_withdrawal_by_transaction_type_validate_parameter_change(
    *, vault: Any, proposed_parameter_value: str
) -> Optional[Rejection]:
    """
    Validates daily_withdrawal_limit_by_transaction_type change.
    It returns rejection if the amount per transaction type is higher than the tiered one.

    :param vault: Vault object for the account whose limit is being validated
    :param proposed_parameter_value: updated string value of
    daily_withdrawal_limit_by_transaction_type param
    :return: rejection if any of new limits per transaction type is higher than the tiered one
    """
    account_tier = account_tiers_get_account_tier(vault)
    tiered_daily_limits: dict[str, dict[str, str]] = utils_get_parameter(
        vault,
        name=maximum_daily_withdrawal_by_transaction_type_PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT,
        is_json=True,
    )
    if not tiered_daily_limits or account_tier not in tiered_daily_limits:
        return None
    parameters_dict = loads(proposed_parameter_value)
    for (transaction_type, transaction_type_value) in parameters_dict.items():
        if transaction_type not in tiered_daily_limits[account_tier]:
            continue
        tiered_limit_value = Decimal(tiered_daily_limits[account_tier][transaction_type])
        proposed_transaction_type_value = Decimal(transaction_type_value)
        if proposed_transaction_type_value > tiered_limit_value:
            denomination = utils_get_parameter(vault, name="denomination")
            return Rejection(
                message=f"Cannot update {transaction_type} transaction type limit for Maximum Daily Withdrawal Amount because {proposed_transaction_type_value} {denomination} exceeds tiered limit of {tiered_limit_value} {denomination} for active {account_tier}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
    return None


# Objects below have been imported from:
#    minimum_single_withdrawal.py
# md5:cf088b0a75e785949433a17855d0fb2b

minimum_single_withdrawal_PARAM_MIN_WITHDRAWAL = "minimum_withdrawal"
minimum_single_withdrawal_parameters = [
    Parameter(
        name=minimum_single_withdrawal_PARAM_MIN_WITHDRAWAL,
        level=ParameterLevel.TEMPLATE,
        description="The minimum amount that can be withdrawn from the account in a single transaction.",
        display_name="Minimum Withdrawal Amount",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("0.01"),
    )
]


def minimum_single_withdrawal_validate(
    *, vault: Any, postings: utils_PostingInstructionListAlias, denomination: str
) -> Optional[Rejection]:
    """
    Reject the posting if the value is less than the minimum allowed withdrawal limit.
    :param vault: Vault object for the account whose limits are being validated
    :param postings: list of postings instructions that are being processed and need to be reviewed
    to ensure each one is under the single withdrawal limit
    :param denomination: the denomination of the account
    :return: rejection if the limit conditions are not met
    """
    minimum_withdrawal: Decimal = utils_get_parameter(
        vault, minimum_single_withdrawal_PARAM_MIN_WITHDRAWAL
    )
    if minimum_withdrawal:
        for posting in postings:
            withdrawal_value = utils_get_available_balance(
                balances=posting.balances(), denomination=denomination
            )
            if withdrawal_value < 0 and abs(withdrawal_value) < minimum_withdrawal:
                minimum_withdrawal = Decimal(minimum_withdrawal).quantize(Decimal("1.e-3"))
                return Rejection(
                    message=f"Transaction amount {round(abs(withdrawal_value), 5).normalize()} {denomination} is less than the minimum withdrawal amount {str(minimum_withdrawal).rstrip('0').rstrip('.')} {denomination}.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
    return None


# Objects below have been imported from:
#    current_account.py
# md5:feb2444ab103a3a87f10561af91c7055

PRODUCT_NAME = "CURRENT_ACCOUNT"
FEE_HIERARCHY = [
    maintenance_fees_PARTIAL_FEE_DETAILS,
    minimum_monthly_balance_PARTIAL_FEE_DETAILS,
    inactivity_fee_PARTIAL_FEE_DETAILS,
]
PREFIX_FEES_APPLICATION = "fees_application"
PARAM_ADDITIONAL_DENOMINATIONS = "additional_denominations"
PARAM_ACCOUNT_TIER_NAME = "account_tier_name"
parameters = [
    Parameter(
        name=PARAM_ADDITIONAL_DENOMINATIONS,
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        description="Currencies that are accepted for this account, formatted as a json list of currency codes",
        display_name="Additional Denominations",
        default_value=dumps(["EUR", "USD"]),
    ),
    Parameter(
        name=PARAM_ACCOUNT_TIER_NAME,
        shape=StringShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="Account tier name of the account",
        display_name="Account Tier Name",
    ),
    *account_tiers_parameters,
    common_parameters_denomination_parameter,
    *dormancy_parameters,
    *excess_fee_parameters,
    *inactivity_fee_parameters,
    *interest_application_parameters,
    *maintenance_fees_parameters,
    *maximum_balance_limit_parameters,
    *maximum_daily_withdrawal_by_transaction_type_parameters,
    *maximum_daily_deposit_parameters,
    *maximum_daily_withdrawal_parameters,
    *minimum_monthly_balance_parameters,
    *minimum_single_deposit_parameters,
    *minimum_single_withdrawal_parameters,
    *overdraft_interest_parameters,
    *overdraft_limit_parameters,
    *roundup_autosave_parameters,
    *tiered_interest_accrual_parameters,
    *unarranged_overdraft_fee_feature_parameters,
    *unarranged_overdraft_fee_application_schedule_parameters,
]
data_fetchers = [
    fetchers_EOD_FETCHER,
    fetchers_EFFECTIVE_DATE_POSTINGS_FETCHER,
    fetchers_EFFECTIVE_OBSERVATION_FETCHER,
    fetchers_LIVE_BALANCES_BOF,
    fetchers_MONTH_TO_EFFECTIVE_POSTINGS_FETCHER,
    *fetchers_PREVIOUS_EOD_OBSERVATION_FETCHERS,
]
event_types = [
    *inactivity_fee_event_types(product_name=PRODUCT_NAME),
    *interest_application_event_types(PRODUCT_NAME),
    *maintenance_fees_event_types(product_name=PRODUCT_NAME, frequency=maintenance_fees_MONTHLY),
    *maintenance_fees_event_types(product_name=PRODUCT_NAME, frequency=maintenance_fees_ANNUALLY),
    *tiered_interest_accrual_event_types(PRODUCT_NAME),
    *minimum_monthly_balance_event_types(PRODUCT_NAME),
    *unarranged_overdraft_fee_application_event_types(PRODUCT_NAME),
]
CLOSE_ACCOUNT = "CLOSE_ACCOUNT"


def _clean_up_accrued_and_overdraft_interest(
    vault: Any, balances: BalanceDefaultDict, denomination: str
) -> list[CustomInstruction]:
    """
    Applies/reverses all accrued interest during account closure.
    Any interest accrued should be returned to the bank's internal account.

    :param vault: vault object used to create interest postings for account closure
    :param balances: Account balances
    :param denomination: The denomination of the account
    :return: The application/reversal posting instructions
    """
    clean_up_posting_instructions: list[CustomInstruction] = []
    clean_up_posting_instructions.extend(
        tiered_interest_accrual_get_interest_reversal_postings(
            vault=vault,
            event_name=CLOSE_ACCOUNT,
            account_type=PRODUCT_NAME,
            balances=balances,
            denomination=denomination,
        )
    )
    clean_up_posting_instructions.extend(
        overdraft_interest_get_interest_reversal_postings(
            vault=vault,
            event_name=CLOSE_ACCOUNT,
            account_type=PRODUCT_NAME,
            balances=balances,
            denomination=denomination,
        )
    )
    return clean_up_posting_instructions
