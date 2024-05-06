# Code auto-generated using Inception Smart Contract Renderer Version 2.0.1


# Objects below have been imported from:
#    time_deposit.py
# md5:db11fbb572c9721db6586d8afda2e065

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
    DenominationShape,
    Parameter,
    ParameterLevel,
    UnionItem,
    UnionShape,
    BalancesObservationFetcher,
    DefinedDateTime,
    Override,
    PostingsIntervalFetcher,
    RelativeDateTime,
    Shift,
    DateShape,
    NumberShape,
    ParameterUpdatePermission,
    AccountNotificationDirective,
    OptionalShape,
    SmartContractEventType,
    BalancesFilter,
    AccountIdShape,
    ActivationHookArguments,
    ActivationHookResult,
    ConversionHookArguments,
    ConversionHookResult,
    DeactivationHookArguments,
    DeactivationHookResult,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    PostingInstructionsDirective,
    PostParameterChangeHookArguments,
    PostParameterChangeHookResult,
    PostPostingHookArguments,
    PostPostingHookResult,
    PreParameterChangeHookArguments,
    PreParameterChangeHookResult,
    PrePostingHookArguments,
    PrePostingHookResult,
    ScheduledEventHookArguments,
    ScheduledEventHookResult,
    fetch_account_data,
    requires,
)
from calendar import isleap
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
from json import loads
from typing import Optional, Any, Iterable, Mapping, Union, Callable, NamedTuple
from zoneinfo import ZoneInfo

api = "4.0.0"
version = "2.0.0"
display_name = "Time Deposit"
summary = "A savings account paying a fixed rate of interest when money is put awayfor a defined period of time."
tside = Tside.LIABILITY
supported_denominations = ["GBP"]


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def activation_hook(
    vault: Any, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    schedule_start_datetime = effective_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + relativedelta(days=1)
    scheduled_events: dict[str, ScheduledEvent] = {}
    if _is_renewed_time_deposit(vault=vault, effective_datetime=effective_datetime):
        interest_application_start_datetime = grace_period_get_grace_period_end_datetime(
            vault=vault
        )
        scheduled_events.update(grace_period_scheduled_events(vault=vault))
        scheduled_events[
            deposit_period_DEPOSIT_PERIOD_END_EVENT
        ] = utils_create_end_of_time_schedule(start_datetime=schedule_start_datetime)
    else:
        interest_application_start_datetime = max(
            deposit_period_get_deposit_period_end_datetime(vault=vault),
            cooling_off_period_get_cooling_off_period_end_datetime(vault=vault),
        )
        scheduled_events.update(deposit_period_scheduled_events(vault=vault))
        scheduled_events[grace_period_GRACE_PERIOD_END_EVENT] = utils_create_end_of_time_schedule(
            start_datetime=schedule_start_datetime
        )
    scheduled_events.update(
        fixed_interest_accrual_scheduled_events(vault=vault, start_datetime=schedule_start_datetime)
    )
    scheduled_events.update(
        interest_application_scheduled_events(
            vault=vault, reference_datetime=interest_application_start_datetime
        )
    )
    scheduled_events.update(deposit_maturity_scheduled_events(vault=vault))
    return ActivationHookResult(scheduled_events_return_value=scheduled_events)


def conversion_hook(
    vault: Any, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    scheduled_events = utils_update_completed_schedules(
        scheduled_events=hook_arguments.existing_schedules,
        effective_datetime=hook_arguments.effective_datetime,
        potentially_completed_schedules=[
            deposit_period_DEPOSIT_PERIOD_END_EVENT,
            grace_period_GRACE_PERIOD_END_EVENT,
            deposit_maturity_ACCOUNT_MATURITY_EVENT,
            deposit_maturity_NOTIFY_UPCOMING_MATURITY_EVENT,
        ],
    )
    return ConversionHookResult(scheduled_events_return_value=scheduled_events)


@requires(parameters=True)
@fetch_account_data(balances=["live_balances_bof", "EARLY_WITHDRAWALS_TRACKER_LIVE_FETCHER"])
def deactivation_hook(
    vault: Any, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    custom_instructions: list[CustomInstruction] = []
    custom_instructions.extend(
        fixed_interest_accrual_get_interest_reversal_postings(
            vault=vault,
            event_name=ACCOUNT_CLOSURE_EVENT,
            account_type=PRODUCT_NAME,
            balances=balances,
        )
    )
    custom_instructions.extend(
        _reset_applied_interest_tracker(
            balances=balances, account_id=vault.account_id, denomination=denomination
        )
    )
    custom_instructions.extend(
        withdrawal_fees_reset_withdrawals_tracker(
            vault=vault, balances=balances, denomination=denomination
        )
    )
    if custom_instructions:
        return DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=custom_instructions, value_datetime=effective_datetime
                )
            ]
        )
    return None


@requires(parameters=True)
@fetch_account_data(balances=["EFFECTIVE_FETCHER"])
def derived_parameter_hook(
    vault: Any, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    effective_datetime = hook_arguments.effective_datetime
    min_datetime = datetime.min.replace(tzinfo=ZoneInfo("UTC"))
    if _is_renewed_time_deposit(vault=vault, effective_datetime=effective_datetime):
        grace_period_end_datetime = grace_period_get_grace_period_end_datetime(vault=vault)
        deposit_period_end_datetime = min_datetime
        cooling_off_period_end_datetime = min_datetime
    else:
        deposit_period_end_datetime = deposit_period_get_deposit_period_end_datetime(vault=vault)
        cooling_off_period_end_datetime = cooling_off_period_get_cooling_off_period_end_datetime(
            vault=vault
        )
        grace_period_end_datetime = min_datetime
    maximum_withdrawal_limit = withdrawal_fees_get_maximum_withdrawal_limit_derived_parameter(
        vault=vault,
        effective_datetime=effective_datetime,
        balance_adjustments=TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
    )
    fee_free_withdrawal_limit = withdrawal_fees_get_fee_free_withdrawal_limit_derived_parameter(
        vault=vault,
        effective_datetime=effective_datetime,
        balance_adjustments=TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
    )
    derived_parameters: dict[str, utils_ParameterValueTypeAlias] = {
        deposit_period_PARAM_DEPOSIT_PERIOD_END_DATE: deposit_period_end_datetime,
        cooling_off_period_PARAM_COOLING_OFF_PERIOD_END_DATE: cooling_off_period_end_datetime,
        grace_period_PARAM_GRACE_PERIOD_END_DATE: grace_period_end_datetime,
        withdrawal_fees_PARAM_MAXIMUM_WITHDRAWAL_LIMIT: maximum_withdrawal_limit,
        withdrawal_fees_PARAM_FEE_FREE_WITHDRAWAL_LIMIT: fee_free_withdrawal_limit,
    }
    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def post_parameter_change_hook(
    vault: Any, hook_arguments: PostParameterChangeHookArguments
) -> Optional[PostParameterChangeHookResult]:
    updated_parameters = hook_arguments.updated_parameter_values
    update_event_directives: list[UpdateAccountEventTypeDirective] = []
    if deposit_parameters_PARAM_TERM in updated_parameters:
        update_event_directives.extend(deposit_maturity_handle_term_parameter_change(vault=vault))
    if update_event_directives:
        return PostParameterChangeHookResult(
            update_account_event_type_directives=update_event_directives
        )
    return None


@requires(parameters=True)
@fetch_account_data(balances=["live_balances_bof"])
def post_posting_hook(
    vault: Any, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    posting_instructions: utils_PostingInstructionListAlias = hook_arguments.posting_instructions
    if utils_is_force_override(posting_instructions=posting_instructions):
        return None
    custom_instructions: list[CustomInstruction] = []
    notification_directives: list[AccountNotificationDirective] = []
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    posting_amount = utils_get_available_balance(
        balances=utils_get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    )
    if posting_amount < Decimal("0"):
        withdrawal_amount = abs(posting_amount)
        is_renewed = _is_renewed_time_deposit(vault=vault, effective_datetime=effective_datetime)
        if (
            is_renewed
            and grace_period_is_withdrawal_subject_to_fees(
                vault=vault,
                effective_datetime=effective_datetime,
                posting_instructions=posting_instructions,
                denomination=denomination,
            )
            or (
                not is_renewed
                and cooling_off_period_is_withdrawal_subject_to_fees(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    posting_instructions=posting_instructions,
                    denomination=denomination,
                )
            )
        ):
            (
                withdrawal_fee_instructions,
                withdrawal_fee_notifications,
            ) = withdrawal_fees_handle_withdrawals(
                vault=vault,
                effective_datetime=effective_datetime,
                posting_instructions=posting_instructions,
                product_name=PRODUCT_NAME,
                denomination=denomination,
                balances=balances,
                balance_adjustments=TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
            )
            withdrawal_fee_notification = withdrawal_fee_notifications[0]
            withdrawal_fee_notifications = _handle_withdrawal_fees_with_number_of_interest_days_fee(
                vault=vault,
                withdrawal_fee_notification=withdrawal_fee_notification,
                withdrawal_amount=withdrawal_amount,
                effective_datetime=effective_datetime,
                balances=balances,
                denomination=denomination,
            )
            custom_instructions.extend(withdrawal_fee_instructions)
            notification_directives.extend(withdrawal_fee_notifications)
        else:
            zero_fee_notification = withdrawal_fees_generate_withdrawal_fee_notification(
                account_id=vault.account_id,
                denomination=denomination,
                withdrawal_amount=withdrawal_amount,
                flat_fee_amount=Decimal("0"),
                percentage_fee_amount=Decimal("0"),
                product_name=PRODUCT_NAME,
                client_batch_id=posting_instructions[0].client_batch_id,
            )
            zero_fee_notification = _update_notification_with_number_of_interest_days_fee(
                withdrawal_fee_notification=zero_fee_notification,
                number_of_interest_days_fee=Decimal("0"),
            )
            notification_directives.append(zero_fee_notification)
        custom_instructions.extend(
            _handle_partial_interest_forfeiture(
                vault=vault,
                effective_datetime=effective_datetime,
                balances=balances,
                withdrawal_amount=withdrawal_amount,
            )
        )
        notification_directives.extend(
            _handle_full_withdrawal_notification(
                vault=vault,
                effective_datetime=effective_datetime,
                balances=balances,
                denomination=denomination,
            )
        )
    if custom_instructions or notification_directives:
        return PostPostingHookResult(
            account_notification_directives=notification_directives,
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=custom_instructions, value_datetime=effective_datetime
                )
            ]
            if custom_instructions
            else [],
        )
    return None


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def pre_parameter_change_hook(
    vault: Any, hook_arguments: PreParameterChangeHookArguments
) -> Optional[PreParameterChangeHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    updated_parameters = hook_arguments.updated_parameter_values
    if proposed_term_value := updated_parameters.get(deposit_parameters_PARAM_TERM):
        if rejection := _validate_term_parameter_change(
            vault=vault,
            effective_datetime=effective_datetime,
            proposed_term_value=int(proposed_term_value),
        ):
            return PreParameterChangeHookResult(rejection=rejection)
    return None


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
@fetch_account_data(balances=["live_balances_bof"])
def pre_posting_hook(
    vault: Any, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    """
    Performs the following posting checks:
    - Force override postings bypass checks
    - Reject any instructions that are not a single Hard Settlement or Transfer
    - Invalid denomination is rejected
    - Validates deposits outside the grace period (Renewed TD only)
    - Reject any initial deposit below the minimum amount (New TD only)
    - Reject any deposit(s) after the end of deposit period (New TD only)
    - Reject additional deposits if configured for single deposit (New TD only)
    - Reject any postings that pushes the current balance above the maximum balance limit
    - Reject any postings after account maturity
    - Reject applicable withdrawals if they violate fee-charging conditions
    """
    posting_instructions: utils_PostingInstructionListAlias = hook_arguments.posting_instructions
    effective_datetime = hook_arguments.effective_datetime
    if utils_is_force_override(posting_instructions=posting_instructions):
        return None
    if posting_type_rejections := utils_validate_single_hard_settlement_or_transfer(
        posting_instructions=posting_instructions
    ):
        return PrePostingHookResult(rejection=posting_type_rejections)
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    if invalid_denomination_rejection := utils_validate_denomination(
        posting_instructions=posting_instructions, accepted_denominations=[denomination]
    ):
        return PrePostingHookResult(rejection=invalid_denomination_rejection)
    account_balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    if _is_renewed_time_deposit(vault=vault, effective_datetime=effective_datetime):
        if grace_period_rejection := grace_period_validate_deposit(
            vault=vault,
            effective_datetime=effective_datetime,
            posting_instructions=posting_instructions,
            denomination=denomination,
        ):
            return PrePostingHookResult(rejection=grace_period_rejection)
    else:
        if minimum_initial_deposit_rejection := minimum_initial_deposit_validate(
            vault=vault,
            denomination=denomination,
            balances=account_balances,
            postings=posting_instructions,
        ):
            return PrePostingHookResult(rejection=minimum_initial_deposit_rejection)
        if deposit_period_rejection := deposit_period_validate(
            vault=vault,
            effective_datetime=effective_datetime,
            posting_instructions=posting_instructions,
            denomination=denomination,
            balances=account_balances,
        ):
            return PrePostingHookResult(rejection=deposit_period_rejection)
    if maximum_balance_rejection := maximum_balance_limit_validate(
        vault=vault,
        postings=posting_instructions,
        denomination=denomination,
        balances=account_balances,
    ):
        return PrePostingHookResult(rejection=maximum_balance_rejection)
    if transaction_after_maturity_rejection := deposit_maturity_validate_postings(
        vault=vault, effective_datetime=effective_datetime
    ):
        return PrePostingHookResult(rejection=transaction_after_maturity_rejection)
    if withdrawals_rejection := withdrawal_fees_validate(
        vault=vault,
        effective_datetime=effective_datetime,
        posting_instructions=posting_instructions,
        denomination=denomination,
        balances=account_balances,
        balance_adjustments=TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
    ):
        return PrePostingHookResult(rejection=withdrawals_rejection)
    if withdrawal_fees_rejection := _validate_withdrawals_with_number_of_interest_days_fee(
        vault=vault,
        effective_datetime=effective_datetime,
        posting_instructions=posting_instructions,
        denomination=denomination,
        balances=account_balances,
        balance_adjustments=TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
    ):
        return PrePostingHookResult(rejection=withdrawal_fees_rejection)
    return None


@requires(event_type="ACCRUE_INTEREST", parameters=True)
@fetch_account_data(event_type="ACCRUE_INTEREST", balances=["EOD_FETCHER"])
@requires(event_type="APPLY_INTEREST", parameters=True)
@fetch_account_data(event_type="APPLY_INTEREST", balances=["EFFECTIVE_FETCHER"])
@requires(event_type="DEPOSIT_PERIOD_END", parameters=True)
@fetch_account_data(event_type="DEPOSIT_PERIOD_END", balances=["EFFECTIVE_FETCHER"])
@requires(event_type="GRACE_PERIOD_END", parameters=True)
@fetch_account_data(event_type="GRACE_PERIOD_END", balances=["EFFECTIVE_FETCHER"])
@requires(event_type="ACCOUNT_MATURITY", parameters=True)
@requires(event_type="NOTIFY_UPCOMING_MATURITY", parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def scheduled_event_hook(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    event_type = hook_arguments.event_type
    effective_datetime = hook_arguments.effective_datetime
    custom_instructions: list[CustomInstruction] = []
    notification_directives: list[AccountNotificationDirective] = []
    update_event_directives: list[UpdateAccountEventTypeDirective] = []
    if event_type == fixed_interest_accrual_ACCRUAL_EVENT:
        custom_instructions.extend(
            fixed_interest_accrual_accrue_interest(
                vault=vault, effective_datetime=effective_datetime, account_type=PRODUCT_NAME
            )
        )
    elif event_type == interest_application_APPLICATION_EVENT:
        if application_custom_instructions := interest_application_apply_interest(
            vault=vault, account_type=PRODUCT_NAME
        ):
            custom_instructions.extend(application_custom_instructions)
            custom_instructions.extend(
                _update_tracked_applied_interest(
                    application_custom_instructions=application_custom_instructions,
                    account_id=vault.account_id,
                    denomination=common_parameters_get_denomination_parameter(vault=vault),
                )
            )
        if update_event_result := interest_application_update_next_schedule_execution(
            vault=vault, effective_datetime=effective_datetime
        ):
            update_event_directives.extend([update_event_result])
    elif event_type == deposit_period_DEPOSIT_PERIOD_END_EVENT:
        balances: BalanceDefaultDict = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
        notification_directives.extend(
            deposit_period_handle_account_closure_notification(
                product_name=PRODUCT_NAME,
                balances=balances,
                denomination=common_parameters_get_denomination_parameter(vault=vault),
                account_id=vault.account_id,
                effective_datetime=effective_datetime,
            )
        )
    elif event_type == deposit_maturity_ACCOUNT_MATURITY_EVENT:
        (
            maturity_notifications,
            schedules_to_skip_indefinitely,
        ) = deposit_maturity_handle_account_maturity_event(
            product_name=PRODUCT_NAME,
            account_id=vault.account_id,
            effective_datetime=effective_datetime,
            schedules_to_skip_indefinitely=[
                fixed_interest_accrual_ACCRUAL_EVENT,
                interest_application_APPLICATION_EVENT,
            ],
        )
        notification_directives.extend(maturity_notifications)
        update_event_directives.extend(schedules_to_skip_indefinitely)
    elif event_type == deposit_maturity_NOTIFY_UPCOMING_MATURITY_EVENT:
        (
            maturity_reminder_notifications,
            updated_maturity_schedule_directives,
        ) = deposit_maturity_handle_notify_upcoming_maturity_event(
            vault=vault, product_name=PRODUCT_NAME
        )
        update_event_directives.extend(updated_maturity_schedule_directives)
        notification_directives.extend(maturity_reminder_notifications)
    elif event_type == grace_period_GRACE_PERIOD_END_EVENT:
        notification_directives.extend(
            grace_period_handle_account_closure_notification(
                vault=vault,
                product_name=PRODUCT_NAME,
                denomination=common_parameters_get_denomination_parameter(vault=vault),
                effective_datetime=effective_datetime,
            )
        )
    if custom_instructions or notification_directives or update_event_directives:
        return ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=custom_instructions,
                    value_datetime=effective_datetime,
                    client_batch_id=f"{vault.get_hook_execution_id()}_{event_type}",
                )
            ]
            if custom_instructions
            else [],
            account_notification_directives=notification_directives,
            update_account_event_type_directives=update_event_directives,
        )
    return None


# Objects below have been imported from:
#    addresses.py
# md5:860f50af37f2fe98540f540fa6394eb7

addresses_INTERNAL_CONTRA = "INTERNAL_CONTRA"

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
utils_END_OF_TIME = datetime(2099, 1, 1, 0, 0, 0, 0, tzinfo=ZoneInfo("UTC"))


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


utils_END_OF_TIME_EXPRESSION = utils_one_off_schedule_expression(utils_END_OF_TIME)
utils_END_OF_TIME_SCHEDULED_EVENT = ScheduledEvent(
    end_datetime=utils_END_OF_TIME - relativedelta(seconds=1),
    expression=utils_END_OF_TIME_EXPRESSION,
)


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


def utils_get_next_datetime_after_calendar_events(
    effective_datetime: datetime, calendar_events: CalendarEvents
) -> datetime:
    """
    Calculate the next datetime after the given calendar events. If the effective
    datetime falls on a calendar day, the datetime will be incremented by one day
    until this condition is met.
    :param effective_datetime: the datetime to be pushed to after calendar events
    :param calendar_events: events that the schedule date should not fall on
    :return: the next non-calendar day
    """
    while utils_falls_on_calendar_events(effective_datetime, calendar_events):
        effective_datetime += relativedelta(days=1)
    return effective_datetime


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


def utils_validate_single_hard_settlement_or_transfer(
    posting_instructions: utils_PostingInstructionListAlias,
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
    if len(posting_instructions) != 1 or posting_instructions[0].type not in accepted_posting_types:
        return Rejection(
            message="Only batches with a single hard settlement or transfer posting are supported",
            reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
        )
    return None


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


def utils_get_posting_instructions_balances(
    *, posting_instructions: utils_PostingInstructionListAlias
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


def utils_create_end_of_time_schedule(start_datetime: datetime) -> ScheduledEvent:
    """
    Sets up a dummy schedule with the End of Time expression, that will never produce any
    jobs and is skipped indefinitely.

    :param start_time: the start time of the schedule. This should be linked to the
    account opening datetime
    :return: returns a dummy scheduled event
    """
    return ScheduledEvent(
        start_datetime=start_datetime, skip=True, expression=utils_END_OF_TIME_EXPRESSION
    )


def utils_update_completed_schedules(
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
            scheduled_events[schedule_name] = utils_END_OF_TIME_SCHEDULED_EVENT
    return scheduled_events


def utils_update_schedules_to_skip_indefinitely(
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
                expression=utils_END_OF_TIME_EXPRESSION,
                end_datetime=utils_END_OF_TIME,
                skip=True,
            )
        )
    return updated_events


# Objects below have been imported from:
#    common_parameters.py
# md5:11b3b3b4a92b1dc6ec77a2405fb2ca6d

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

# Objects below have been imported from:
#    cooling_off_period.py
# md5:c21aa92af260befceeb34389f9019a7f

cooling_off_period_PARAM_COOLING_OFF_PERIOD = "cooling_off_period"
cooling_off_period_PARAM_COOLING_OFF_PERIOD_END_DATE = "cooling_off_period_end_date"
cooling_off_period_parameters = [
    Parameter(
        name=cooling_off_period_PARAM_COOLING_OFF_PERIOD,
        level=ParameterLevel.TEMPLATE,
        description="The number of days from the account creation datetime when a user can make a full withdrawal without penalties.",
        display_name="Cooling-off Period Length (days)",
        shape=NumberShape(min_value=0, step=1),
        default_value=5,
    ),
    Parameter(
        name=cooling_off_period_PARAM_COOLING_OFF_PERIOD_END_DATE,
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The cooling-off period will end at 23:59:59.999999 on this day. If 0001-01-01 is returned, this parameter is not valid for this account.",
        display_name="Cooling-off Period End Date",
        shape=DateShape(),
    ),
]


def cooling_off_period_get_cooling_off_period_end_datetime(*, vault: Any) -> datetime:
    """
    Calculates and returns the cooling-off period end datetime. This date will represent the
    midnight of the account creation datetime plus the number of days in the cooling-off period,
    inclusive of the account creation datetime.
    :param vault: Vault object for the account
    :return: the datetime when the cooling-off period ends
    """
    cooling_off_period = cooling_off_period__get_cooling_off_period_parameter(vault=vault)
    account_creation_datetime = vault.get_account_creation_datetime()
    cooling_off_period_end = (
        account_creation_datetime + relativedelta(days=cooling_off_period)
    ).replace(hour=23, minute=59, second=59, microsecond=999999)
    return cooling_off_period_end


def cooling_off_period_is_within_cooling_off_period(
    *, vault: Any, effective_datetime: datetime
) -> bool:
    """
    Determines whether an effective datetime is within the cooling-off period of an account

    :param vault: Vault object for the account
    :param effective_datetime: datetime to be checked whether is within the cooling-off period
    :return: True if the effective datetime is less than or equal to the
    cooling-off period end datetime
    """
    return effective_datetime <= cooling_off_period_get_cooling_off_period_end_datetime(vault=vault)


def cooling_off_period__get_cooling_off_period_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils_get_parameter(
            vault=vault,
            name=cooling_off_period_PARAM_COOLING_OFF_PERIOD,
            at_datetime=effective_datetime,
        )
    )


def cooling_off_period_is_withdrawal_subject_to_fees(
    *,
    vault: Any,
    effective_datetime: datetime,
    posting_instructions: utils_PostingInstructionListAlias,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> bool:
    """
    For use in the post_posting_hook.
    Determine if a withdrawal is subject to fees. If a full withdrawal is made during the
    cooling-off period, then no fees will be charged, otherwise the withdrawal is subject to fees.
    Deposits are not subject to fees.

    :param vault: Vault object for the account
    :param effective_datetime: datetime to be checked whether is within the cooling-off period
    :param posting_instructions: posting instructions from the post_posting_hook
    :param denomination: the denomination of the account
    :param balances: the balances to determine if it's a full withdrawal. If no balances are
    provided, live balances are used.
    :return: True if the withdrawal is subject to fees, False otherwise
    """
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    is_withdrawal = utils_get_available_balance(
        balances=utils_get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    ) < Decimal("0")
    if not is_withdrawal:
        return False
    is_full_withdrawal = is_withdrawal and utils_get_available_balance(
        balances=balances, denomination=denomination
    ) == Decimal("0")
    if is_full_withdrawal and cooling_off_period_is_within_cooling_off_period(
        vault=vault, effective_datetime=effective_datetime
    ):
        return False
    return True


# Objects below have been imported from:
#    deposit_interfaces.py
# md5:c5f8eb9ed8ba4721d20e372f17c73863

deposit_interfaces_DefaultBalanceAdjustment = NamedTuple(
    "DefaultBalanceAdjustment", [("calculate_balance_adjustment", Callable[..., Decimal])]
)

# Objects below have been imported from:
#    deposit_parameters.py
# md5:18dd17fac871fd4f6eb6848f99daa5ae

deposit_parameters_DAYS = "days"
deposit_parameters_MONTHS = "months"
deposit_parameters_PARAM_TERM = "term"
deposit_parameters_term_param = Parameter(
    name=deposit_parameters_PARAM_TERM,
    shape=NumberShape(min_value=1, step=1),
    level=ParameterLevel.INSTANCE,
    description="The term length of the product.",
    display_name="Term",
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    default_value=12,
)
deposit_parameters_PARAM_TERM_UNIT = "term_unit"
deposit_parameters_term_unit_param = Parameter(
    name=deposit_parameters_PARAM_TERM_UNIT,
    shape=UnionShape(
        items=[
            UnionItem(key=deposit_parameters_DAYS, display_name="Days"),
            UnionItem(key=deposit_parameters_MONTHS, display_name="Months"),
        ]
    ),
    level=ParameterLevel.TEMPLATE,
    description="The unit at which the term is applied.",
    display_name="Term Unit (days or months)",
    default_value=UnionItemValue(key="months"),
)
deposit_parameters_term_parameters = [
    deposit_parameters_term_param,
    deposit_parameters_term_unit_param,
]


def deposit_parameters_get_term_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils_get_parameter(
            vault=vault, name=deposit_parameters_PARAM_TERM, at_datetime=effective_datetime
        )
    )


def deposit_parameters_get_term_unit_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    return str(
        utils_get_parameter(
            vault=vault,
            name=deposit_parameters_PARAM_TERM_UNIT,
            at_datetime=effective_datetime,
            is_union=True,
        )
    )


# Objects below have been imported from:
#    deposit_maturity.py
# md5:244ee07e9599e1ebcf28e8c86b314185

deposit_maturity_ACCOUNT_MATURITY_SUFFIX = "_ACCOUNT_MATURITY"
deposit_maturity_NOTIFY_UPCOMING_MATURITY_SUFFIX = "_NOTIFY_UPCOMING_MATURITY"
deposit_maturity_ACCOUNT_MATURITY_EVENT = "ACCOUNT_MATURITY"
deposit_maturity_NOTIFY_UPCOMING_MATURITY_EVENT = "NOTIFY_UPCOMING_MATURITY"
deposit_maturity_PARAM_DESIRED_MATURITY_DATE = "desired_maturity_date"
deposit_maturity_desired_maturity_date = Parameter(
    name=deposit_maturity_PARAM_DESIRED_MATURITY_DATE,
    level=ParameterLevel.INSTANCE,
    shape=OptionalShape(
        shape=DateShape(
            min_date=datetime.min.replace(tzinfo=ZoneInfo("UTC")),
            max_date=datetime.max.replace(tzinfo=ZoneInfo("UTC")),
        )
    ),
    description="Optional override for the account maturity datetime. If not set, the maturity datetime is derived from the term and term unit. If set, the account will mature at 00:00:00 on the next day of this parameter value.",
    display_name="Account Maturity Date",
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    default_value=OptionalValue(datetime.min.replace(tzinfo=ZoneInfo("UTC"))),
)
deposit_maturity_PARAM_MATURITY_NOTICE_PERIOD = "maturity_notice_period"
deposit_maturity_maturity_notice_period = Parameter(
    name=deposit_maturity_PARAM_MATURITY_NOTICE_PERIOD,
    level=ParameterLevel.TEMPLATE,
    shape=NumberShape(min_value=1, step=1),
    description="The number of days prior to the account maturingto send a notification regarding upcoming maturity.",
    display_name="Maturity Notification Days",
    default_value=1,
)
deposit_maturity_maturity_parameters = [
    deposit_maturity_desired_maturity_date,
    deposit_maturity_maturity_notice_period,
]


def deposit_maturity_notification_type_at_account_maturity(*, product_name: str) -> str:
    """
    Returns a notification type for account maturity
    :param product_name: The product name
    :return: notification type
    """
    return f"{product_name.upper()}{deposit_maturity_ACCOUNT_MATURITY_SUFFIX}"


def deposit_maturity_notification_type_notify_upcoming_maturity(*, product_name: str) -> str:
    """
    Returns a notification type for notify upcoming maturity
    :param product_name: The product name
    :return: notification type
    """
    return f"{product_name.upper()}{deposit_maturity_NOTIFY_UPCOMING_MATURITY_SUFFIX}"


def deposit_maturity_event_types(*, product_name: str) -> list[SmartContractEventType]:
    """
    Returns a list of event types
    :param product_name: name of the product
    :return: list of SmartContractEventType
    """
    return [
        SmartContractEventType(
            name=deposit_maturity_ACCOUNT_MATURITY_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{deposit_maturity_ACCOUNT_MATURITY_EVENT}_AST"
            ],
        ),
        SmartContractEventType(
            name=deposit_maturity_NOTIFY_UPCOMING_MATURITY_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{deposit_maturity_NOTIFY_UPCOMING_MATURITY_EVENT}_AST"
            ],
        ),
    ]


def deposit_maturity_scheduled_events(*, vault: Any) -> dict[str, ScheduledEvent]:
    """
    Creates one off scheduled events for sending notifications:
    - to notify of upcoming maturity
    - at account maturity

    :param vault: Vault object to retrieve account creation datetime and notice period
    :return: dict of account maturity notifications scheduled events
    """
    (
        maturity_datetime,
        notify_upcoming_maturity_datetime,
    ) = deposit_maturity_get_account_maturity_and_notify_upcoming_maturity_datetimes(vault=vault)
    account_maturity_scheduled_event = ScheduledEvent(
        start_datetime=maturity_datetime - relativedelta(seconds=1),
        expression=utils_one_off_schedule_expression(schedule_datetime=maturity_datetime),
        end_datetime=maturity_datetime,
    )
    notify_upcoming_maturity_scheduled_event = ScheduledEvent(
        start_datetime=notify_upcoming_maturity_datetime - relativedelta(seconds=1),
        expression=utils_one_off_schedule_expression(
            schedule_datetime=notify_upcoming_maturity_datetime
        ),
        end_datetime=notify_upcoming_maturity_datetime,
    )
    return {
        deposit_maturity_ACCOUNT_MATURITY_EVENT: account_maturity_scheduled_event,
        deposit_maturity_NOTIFY_UPCOMING_MATURITY_EVENT: notify_upcoming_maturity_scheduled_event,
    }


def deposit_maturity_handle_account_maturity_event(
    *,
    product_name: str,
    account_id: str,
    effective_datetime: datetime,
    schedules_to_skip_indefinitely: Optional[list[str]] = None,
) -> tuple[list[AccountNotificationDirective], list[UpdateAccountEventTypeDirective]]:
    """
    - Creates account maturity notification directive
    - Creates account update directive to skip the given schedules indefinitely

    :param product_name: the name of the product for notification type
    :param account_id: vault account id for which this notification is sent
    :param effective_datetime: datetime at which this method is executed
    :param schedules_to_skip_indefinitely: list of schedule names to skip forever
    :return: tuple containing a list of maturity notification directive
    and a list of account update directive to skip schedules indefinitely
    """
    updated_schedules: list[UpdateAccountEventTypeDirective] = []
    if schedules_to_skip_indefinitely:
        updated_schedules = deposit_maturity__handle_skipping_schedules_indefinitely_at_maturity(
            schedules_to_skip_indefinitely=schedules_to_skip_indefinitely
        )
    maturity_notification: list[AccountNotificationDirective] = [
        AccountNotificationDirective(
            notification_type=deposit_maturity_notification_type_at_account_maturity(
                product_name=product_name
            ),
            notification_details={
                "account_id": account_id,
                "account_maturity_datetime": str(effective_datetime),
                "reason": "Account has now reached maturity",
            },
        )
    ]
    return (maturity_notification, updated_schedules)


def deposit_maturity_handle_notify_upcoming_maturity_event(
    *, vault: Any, product_name: str
) -> tuple[list[AccountNotificationDirective], list[UpdateAccountEventTypeDirective]]:
    """
    - Creates notification directive prior to account maturity as a reminder
    - Creates account update directive for maturity schedule if it falls on a holiday

    Note: Calendars only have a 3 month visibility from the effective datetime.
    The maturity date is checked on account opening but unlikely to fall within the
    first 3 months. Therefore maturity date is checked again and updated if it falls
    on a holiday.

    :param vault: Vault object for the account
    :param product_name: the name of the product for notification type
    :return: tuple containing a list of maturity reminder notification directives
    and a list of account update directives for maturity schedule
    """
    updated_maturity_schedule: list[UpdateAccountEventTypeDirective] = []
    maturity_datetime_without_calendars = deposit_maturity_get_maturity_datetime_without_calendars(
        vault=vault
    )
    maturity_datetime_with_calendars = deposit_maturity_get_maturity_datetime_with_calendars(
        vault=vault, maturity_datetime=maturity_datetime_without_calendars
    )
    if maturity_datetime_with_calendars != maturity_datetime_without_calendars:
        updated_maturity_schedule = [
            deposit_maturity__update_account_maturity_schedule(
                maturity_datetime=maturity_datetime_with_calendars
            )
        ]
    notification_maturity_notice_period: list[AccountNotificationDirective] = [
        AccountNotificationDirective(
            notification_type=deposit_maturity_notification_type_notify_upcoming_maturity(
                product_name=product_name
            ),
            notification_details={
                "account_id": vault.account_id,
                "account_maturity_datetime": str(maturity_datetime_with_calendars),
            },
        )
    ]
    return (notification_maturity_notice_period, updated_maturity_schedule)


def deposit_maturity__handle_skipping_schedules_indefinitely_at_maturity(
    schedules_to_skip_indefinitely: list[str],
) -> list[UpdateAccountEventTypeDirective]:
    """
    Update provided list of schedules to a skip indefinitely on account maturity

    :param schedules_to_skip_indefinitely: list of schedule names to skip forever
    :return: list of updated scheduled events
    """
    return utils_update_schedules_to_skip_indefinitely(schedules=schedules_to_skip_indefinitely)


def deposit_maturity_get_account_maturity_and_notify_upcoming_maturity_datetimes(
    *, vault: Any
) -> tuple[datetime, datetime]:
    """
    Get the datetimes for the account maturity and notify account maturity events.

    :param vault: Vault object of the account
    :return: tuple of account maturity datetime and notify account maturity datetime
    """
    maturity_datetime_without_calendars = deposit_maturity_get_maturity_datetime_without_calendars(
        vault=vault
    )
    maturity_datetime = deposit_maturity_get_maturity_datetime_with_calendars(
        vault=vault, maturity_datetime=maturity_datetime_without_calendars
    )
    notify_upcoming_maturity_datetime = deposit_maturity__get_notify_upcoming_maturity_datetime(
        vault=vault, maturity_datetime=maturity_datetime
    )
    return (maturity_datetime, notify_upcoming_maturity_datetime)


def deposit_maturity_get_maturity_datetime_without_calendars(*, vault: Any) -> datetime:
    """
    Calculates the account maturity datetime based on the following conditions:
    - if desired_maturity_date is set and is before the account creation date, then the
      account is assumed to mature on account creation itself and no notification is sent
    - if desired_maturity_date is set and is after the account creation date, this value is used
    - if desired_maturity_date is not provided, the maturity datetime is derived from term and unit

    :param vault: Vault object for the account
    :return: the datetime when the account matures
    """
    if maturity_datetime := deposit_maturity_get_desired_maturity_datetime(vault=vault):
        maturity_datetime = max(vault.get_account_creation_datetime(), maturity_datetime)
    else:
        maturity_datetime = deposit_maturity_get_maturity_datetime_from_term_and_unit(vault=vault)
    return (maturity_datetime + relativedelta(days=1)).replace(hour=0, minute=0, second=0)


def deposit_maturity_get_maturity_datetime_from_term_and_unit(
    *, vault: Any, term: Optional[int] = None, term_unit: Optional[str] = None
) -> datetime:
    """
    Derive maturity datetime from term and term unit, starting at account opening.

    :param vault: Vault object for the account
    :param term: the term of the product, if not provided the 'term' parameter is retrieved
    :param term_unit: the term unit of the product, if not provided the
    'term_unit' parameter is retrieved
    :return: the maturity datetime using the term and term unit
    """
    account_creation_datetime = vault.get_account_creation_datetime()
    if term is None:
        term = deposit_parameters_get_term_parameter(vault=vault)
    if term_unit is None:
        term_unit = deposit_parameters_get_term_unit_parameter(vault=vault)
    add_timedelta = (
        relativedelta(days=term)
        if term_unit == deposit_parameters_DAYS
        else relativedelta(months=term)
    )
    return account_creation_datetime + add_timedelta


def deposit_maturity_get_maturity_datetime_with_calendars(
    vault: Any, maturity_datetime: datetime
) -> datetime:
    """
    Get maturity datetime, adjusting for calendar events

    :param vault: Vault object for the account
    :param maturity_datetime: maturity datetime of the account before calendar adjustments
    :return: maturity datetime
    """
    calendar_events = vault.get_calendar_events(calendar_ids=["&{PUBLIC_HOLIDAYS}"])
    return utils_get_next_datetime_after_calendar_events(
        effective_datetime=maturity_datetime, calendar_events=calendar_events
    )


def deposit_maturity__get_notify_upcoming_maturity_datetime(
    *, vault: Any, maturity_datetime: datetime
) -> datetime:
    """
     Get notify upcoming maturity datetime, which is the start of the notice period before
     the maturity datetime, which is defined by the `maturity_notice_period` parameter.

    :param vault: Vault object for the account
    :param maturity_datetime: maturity datetime of the account
    :return: maturity datetime
    """
    deposit_maturity_maturity_notice_period = deposit_maturity_get_maturity_notice_period_parameter(
        vault=vault
    )
    return maturity_datetime - relativedelta(days=deposit_maturity_maturity_notice_period)


def deposit_maturity_validate_postings(
    *, vault: Any, effective_datetime: datetime
) -> Optional[Rejection]:
    """
    Reject any postings after the account has matured

    :param vault: Vault object for the account
    :param effective_datetime: datetime of the posting
    :return Rejection: no transaction after account maturity
    """
    maturity_datetime_without_calendars = deposit_maturity_get_maturity_datetime_without_calendars(
        vault=vault
    )
    maturity_datetime = deposit_maturity_get_maturity_datetime_with_calendars(
        vault=vault, maturity_datetime=maturity_datetime_without_calendars
    )
    if effective_datetime >= maturity_datetime:
        return Rejection(
            message="No transactions are allowed at or after account maturity",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


def deposit_maturity__update_account_maturity_schedule(
    *, maturity_datetime: datetime
) -> UpdateAccountEventTypeDirective:
    """
    Updates account maturity schedule based on the provided maturity datetime

    :param maturity_datetime: maturity datetime of the account
    :return UpdateAccountEventTypeDirective: updated account schedule event
    """
    expression = utils_one_off_schedule_expression(schedule_datetime=maturity_datetime)
    return UpdateAccountEventTypeDirective(
        event_type=deposit_maturity_ACCOUNT_MATURITY_EVENT,
        expression=expression,
        end_datetime=maturity_datetime,
    )


def deposit_maturity_validate_term_parameter_change(
    *, vault: Any, effective_datetime: datetime, proposed_term_value: int
) -> Optional[Rejection]:
    """
    Accepts a change to the 'term' parameter if it satisfies:
    - the `desired_maturity_date` parameter is not set, since this takes precedence if set
    - the notice period start date is in the future (and hence the maturity date is in the
      future since notice period will always occur before maturity)

    :param vault: Vault object for the account
    :param effective_datetime: effective datetime of the proposed parameter change
    :param proposed_term_value: the proposed value for the `term` value
    :return: a Rejection if the change is invalid
    """
    if (
        deposit_maturity_get_desired_maturity_datetime(
            vault=vault, effective_datetime=effective_datetime
        )
        is not None
    ):
        return Rejection(
            message="Term length cannot be changed if the desired maturity datetime is set.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    current_term_value = deposit_parameters_get_term_parameter(vault=vault)
    if proposed_term_value >= current_term_value:
        return None
    else:
        maturity_datetime_without_calendars = (
            deposit_maturity_get_maturity_datetime_from_term_and_unit(
                vault=vault, term=proposed_term_value
            )
        )
        maturity_datetime = deposit_maturity_get_maturity_datetime_with_calendars(
            vault=vault, maturity_datetime=maturity_datetime_without_calendars
        )
        notify_upcoming_maturity_datetime = deposit_maturity__get_notify_upcoming_maturity_datetime(
            vault=vault, maturity_datetime=maturity_datetime
        )
        if notify_upcoming_maturity_datetime < effective_datetime:
            return Rejection(
                message="Term length cannot be changed such that the maturity notification period starts in the past.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
    return None


def deposit_maturity_handle_term_parameter_change(
    *, vault: Any
) -> list[UpdateAccountEventTypeDirective]:
    """
    Update the ACCOUNT_MATURITY_EVENT and NOTIFY_UPCOMING_MATURITY_EVENT schedules after the term
    length has changed. The pre-parameter-change validation ensures that the notice period begins
    in the future.

    :param vault: the Vault object of the account
    :return: list of update event directives for the maturity and notify maturity events
    """
    (
        maturity_datetime,
        notify_upcoming_maturity_datetime,
    ) = deposit_maturity_get_account_maturity_and_notify_upcoming_maturity_datetimes(vault=vault)
    account_maturity_update_event = UpdateAccountEventTypeDirective(
        event_type=deposit_maturity_ACCOUNT_MATURITY_EVENT,
        expression=utils_one_off_schedule_expression(schedule_datetime=maturity_datetime),
        end_datetime=maturity_datetime,
    )
    notify_upcoming_maturity_update_event = UpdateAccountEventTypeDirective(
        event_type=deposit_maturity_NOTIFY_UPCOMING_MATURITY_EVENT,
        expression=utils_one_off_schedule_expression(
            schedule_datetime=notify_upcoming_maturity_datetime
        ),
        end_datetime=notify_upcoming_maturity_datetime,
    )
    return [account_maturity_update_event, notify_upcoming_maturity_update_event]


def deposit_maturity_get_maturity_notice_period_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils_get_parameter(
            vault=vault,
            name=deposit_maturity_PARAM_MATURITY_NOTICE_PERIOD,
            at_datetime=effective_datetime,
        )
    )


def deposit_maturity_get_desired_maturity_datetime(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> datetime:
    return utils_get_parameter(
        vault=vault,
        name=deposit_maturity_PARAM_DESIRED_MATURITY_DATE,
        at_datetime=effective_datetime,
        is_optional=True,
    )


# Objects below have been imported from:
#    deposit_period.py
# md5:2041b0ada6824008e57b2cfd52502564

deposit_period_SINGLE = "single"
deposit_period_UNLIMITED = "unlimited"
deposit_period_DEPOSIT_PERIOD_END_SUFFIX = "_DEPOSIT_PERIOD_END"
deposit_period_DEPOSIT_PERIOD_END_EVENT = "DEPOSIT_PERIOD_END"
deposit_period_PARAM_DEPOSIT_PERIOD = "deposit_period"
deposit_period_PARAM_NUMBER_OF_PERMITTED_DEPOSITS = "number_of_permitted_deposits"
deposit_period_PARAM_DEPOSIT_PERIOD_END_DATE = "deposit_period_end_date"
deposit_period_parameters = [
    Parameter(
        name=deposit_period_PARAM_DEPOSIT_PERIOD,
        shape=NumberShape(min_value=0, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The number of calendar days from account creation to allow depositing funds",
        display_name="Deposit Period Length (days)",
        default_value=7,
    ),
    Parameter(
        name=deposit_period_PARAM_NUMBER_OF_PERMITTED_DEPOSITS,
        shape=UnionShape(
            items=[
                UnionItem(key=deposit_period_SINGLE, display_name="Single Deposit"),
                UnionItem(key=deposit_period_UNLIMITED, display_name="Unlimited Deposits"),
            ]
        ),
        level=ParameterLevel.TEMPLATE,
        description="Number of deposits allowed during the deposit period. This can be single or unlimited.",
        display_name="Number Of Deposits",
        default_value=UnionItemValue(key="unlimited"),
    ),
    Parameter(
        name=deposit_period_PARAM_DEPOSIT_PERIOD_END_DATE,
        shape=DateShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The deposit period will end at 23:59:59.999999 on this day. If 0001-01-01 is returned, this parameter is not valid for this account.",
        display_name="Deposit Period End Date",
    ),
]


def deposit_period_notification_type(*, product_name: str) -> str:
    """
    Returns a notification type
    :param product_name: The product name
    :return: notification type
    """
    return f"{product_name.upper()}{deposit_period_DEPOSIT_PERIOD_END_SUFFIX}"


def deposit_period_event_types(*, product_name: str) -> list[SmartContractEventType]:
    """
    Returns a list of event types
    :param product_name: name of the product
    :return: list of SmartContractEventType
    """
    return [
        SmartContractEventType(
            name=deposit_period_DEPOSIT_PERIOD_END_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{deposit_period_DEPOSIT_PERIOD_END_EVENT}_AST"
            ],
        )
    ]


def deposit_period_scheduled_events(*, vault: Any) -> dict[str, ScheduledEvent]:
    """
    Creates one off scheduled event for deposit period end balance check
    :param vault: Vault object to retrieve account creation datetime and deposit period
    :return: dict of deposit period end scheduled event
    """
    deposit_period_end_datetime = deposit_period_get_deposit_period_end_datetime(vault=vault)
    scheduled_event = ScheduledEvent(
        start_datetime=deposit_period_end_datetime - relativedelta(seconds=1),
        expression=utils_one_off_schedule_expression(schedule_datetime=deposit_period_end_datetime),
        end_datetime=deposit_period_end_datetime,
    )
    return {deposit_period_DEPOSIT_PERIOD_END_EVENT: scheduled_event}


def deposit_period_validate(
    *,
    vault: Any,
    effective_datetime: datetime,
    posting_instructions: utils_PostingInstructionListAlias,
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
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    deposit_proposed_amount = utils_get_current_credit_balance(
        balances=utils_get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    )
    if deposit_proposed_amount > Decimal("0"):
        if not deposit_period_is_within_deposit_period(
            vault=vault, effective_datetime=effective_datetime
        ):
            return Rejection(
                message="No deposits are allowed after the deposit period end datetime",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        number_of_permitted_deposits = deposit_period__get_number_of_permitted_deposits_parameter(
            vault=vault
        )
        if number_of_permitted_deposits == deposit_period_SINGLE:
            if balances is None:
                balances = vault.get_balances_observation(
                    fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
                ).balances
            credit_default_balance = utils_get_current_credit_balance(
                balances=balances, denomination=denomination
            )
            if credit_default_balance > Decimal(0):
                return Rejection(
                    message="Only a single deposit is allowed",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
    return None


def deposit_period_handle_account_closure_notification(
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
    net_balance = utils_get_current_net_balance(balances=balances, denomination=denomination)
    if net_balance == Decimal(0):
        return [
            AccountNotificationDirective(
                notification_type=deposit_period_notification_type(product_name=product_name),
                notification_details={
                    "account_id": account_id,
                    "deposit_balance": str(net_balance),
                    "deposit_period_end_datetime": str(effective_datetime),
                    "reason": "Close account due to lack of deposits at the end of deposit period",
                },
            )
        ]
    return []


def deposit_period_get_deposit_period_end_datetime(*, vault: Any) -> datetime:
    """
    Calculates and returns the deposit period end datetime. This date will represent the
    midnight of the account creation datetime plus the number of days in the deposit period,
    inclusive of the account creation datetime.
    :param vault: Vault object for the account
    :return: the datetime when the deposit period ends
    """
    account_creation_datetime = vault.get_account_creation_datetime()
    deposit_period = deposit_period__get_deposit_period_parameter(vault=vault)
    return (account_creation_datetime + relativedelta(days=deposit_period)).replace(
        hour=23, minute=59, second=59, microsecond=999999, tzinfo=ZoneInfo("UTC")
    )


def deposit_period_is_within_deposit_period(*, vault: Any, effective_datetime: datetime) -> bool:
    """
    Determines whether an effective datetime is within the deposit period of an account

    :param deposit_period_end_datetime: the end datetime of the deposit period
    :param effective_datetime: datetime to be checked whether is within the deposit period
    :return: bool, True if the effective datetime is less than or equal to the
    deposit period end datetime
    """
    return effective_datetime <= deposit_period_get_deposit_period_end_datetime(vault=vault)


def deposit_period__get_deposit_period_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils_get_parameter(
            vault=vault, name=deposit_period_PARAM_DEPOSIT_PERIOD, at_datetime=effective_datetime
        )
    )


def deposit_period__get_number_of_permitted_deposits_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    return str(
        utils_get_parameter(
            vault=vault,
            name=deposit_period_PARAM_NUMBER_OF_PERMITTED_DEPOSITS,
            at_datetime=effective_datetime,
            is_union=True,
        )
    )


# Objects below have been imported from:
#    withdrawal_fees.py
# md5:92a281b30ad429065c1ce58e4b457e47

withdrawal_fees_EARLY_WITHDRAWALS_TRACKER = "EARLY_WITHDRAWALS_TRACKER"
withdrawal_fees_EARLY_WITHDRAWALS_TRACKER_LIVE_BOF_ID = "EARLY_WITHDRAWALS_TRACKER_LIVE_FETCHER"
withdrawal_fees_EARLY_WITHDRAWALS_TRACKER_LIVE_FETCHER = BalancesObservationFetcher(
    fetcher_id=withdrawal_fees_EARLY_WITHDRAWALS_TRACKER_LIVE_BOF_ID,
    at=DefinedDateTime.LIVE,
    filter=BalancesFilter(addresses=[withdrawal_fees_EARLY_WITHDRAWALS_TRACKER]),
)
withdrawal_fees_WITHDRAWAL_FEE_SUFFIX = "_WITHDRAWAL_FEE"
withdrawal_fees_PARAM_EARLY_WITHDRAWAL_FLAT_FEE = "early_withdrawal_flat_fee"
withdrawal_fees_PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE = "early_withdrawal_percentage_fee"
withdrawal_fees_PARAM_MAXIMUM_WITHDRAWAL_PERCENTAGE_LIMIT = "maximum_withdrawal_percentage_limit"
withdrawal_fees_PARAM_FEE_FREE_WITHDRAWAL_PERCENTAGE_LIMIT = "fee_free_withdrawal_percentage_limit"
withdrawal_fees_PARAM_MAXIMUM_WITHDRAWAL_LIMIT = "maximum_withdrawal_limit"
withdrawal_fees_PARAM_FEE_FREE_WITHDRAWAL_LIMIT = "fee_free_withdrawal_limit"
withdrawal_fees_early_withdrawal_flat_fee_parameter = Parameter(
    name=withdrawal_fees_PARAM_EARLY_WITHDRAWAL_FLAT_FEE,
    shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
    level=ParameterLevel.TEMPLATE,
    description="A flat fee applied when making an early withdrawal.",
    display_name="Early Withdrawal Flat Fee",
    default_value=Decimal("10.00"),
)
withdrawal_fees_early_withdrawal_percentage_fee_parameter = Parameter(
    name=withdrawal_fees_PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE,
    shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1")),
    level=ParameterLevel.TEMPLATE,
    description="A percentage fee applied when making an early withdrawal.",
    display_name="Early Withdrawal Percentage Fee",
    default_value=Decimal("0"),
)
withdrawal_fees_maximum_withdrawal_percentage_limit_parameter = Parameter(
    name=withdrawal_fees_PARAM_MAXIMUM_WITHDRAWAL_PERCENTAGE_LIMIT,
    shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1")),
    level=ParameterLevel.TEMPLATE,
    description="The percentage of the total funds deposited by the customer that can be withdrawn.",
    display_name="Maximum Withdrawal Percentage Limit",
    default_value=Decimal("0"),
)
withdrawal_fees_fee_free_withdrawal_percentage_limit_parameter = Parameter(
    name=withdrawal_fees_PARAM_FEE_FREE_WITHDRAWAL_PERCENTAGE_LIMIT,
    shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1"), step=Decimal("0.0001")),
    level=ParameterLevel.INSTANCE,
    description="The percentage of the total funds deposited by the customer which can be withdrawn without incurring fees.",
    display_name="Fee Free Withdrawal Percentage Limit",
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    default_value=Decimal("0"),
)
withdrawal_fees_maximum_withdrawal_limit_parameter = Parameter(
    name=withdrawal_fees_PARAM_MAXIMUM_WITHDRAWAL_LIMIT,
    shape=NumberShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    display_name="Maximum Withdrawal Limit",
    description="The total sum of withdrawals cannot exceed this limit.",
)
withdrawal_fees_fee_free_withdrawal_limit_parameter = Parameter(
    name=withdrawal_fees_PARAM_FEE_FREE_WITHDRAWAL_LIMIT,
    shape=NumberShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    display_name="Fee Free Withdrawal Limit",
    description="The amount which can be withdrawn without incurring fees.",
)
withdrawal_fees_parameters = [
    withdrawal_fees_early_withdrawal_flat_fee_parameter,
    withdrawal_fees_early_withdrawal_percentage_fee_parameter,
    withdrawal_fees_maximum_withdrawal_percentage_limit_parameter,
    withdrawal_fees_fee_free_withdrawal_percentage_limit_parameter,
    withdrawal_fees_maximum_withdrawal_limit_parameter,
    withdrawal_fees_fee_free_withdrawal_limit_parameter,
]


def withdrawal_fees_notification_type(*, product_name: str) -> str:
    """
    Returns a notification type
    :param product_name: the product name
    :return: notification type
    """
    return f"{product_name.upper()}{withdrawal_fees_WITHDRAWAL_FEE_SUFFIX}"


def withdrawal_fees_validate(
    *,
    vault: Any,
    effective_datetime: datetime,
    posting_instructions: utils_PostingInstructionListAlias,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    balance_adjustments: Optional[list[deposit_interfaces_DefaultBalanceAdjustment]] = None,
) -> Optional[Rejection]:
    """
    For use in the pre_posting_hook.
    Deposits are accepted with no validation.
    Reject the posting instructions if any of the following conditions are met:
    - The withdrawal amount exceeds the available balance
    - A partial withdrawal causes the total withdrawal amount to exceed the maximum withdrawal limit
    - The withdrawal occurs on a public holiday and the posting does not include
      `"calendar_override": "true"` in the metadata
    - The withdrawal amount is less than the incurred withdrawal fee amount

    :param vault: the Vault object for the account against which this validation is applied
    :param effective_datetime: datetime at which this method is executed
    :param posting_instructions: list of posting instructions to validate
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the LIVE_BALANCES_BOF_ID
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    For example, interest application adjustment should be negative, and a fee
    charge adjustment should be positive.
    :return: rejection if any of the above conditions are met
    """
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    posting_amount = utils_get_available_balance(
        balances=utils_get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    )
    is_withdrawal = posting_amount < Decimal("0")
    if not is_withdrawal:
        return None
    withdrawal_amount = abs(posting_amount)
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    current_balance = utils_get_current_net_balance(balances=balances, denomination=denomination)
    if withdrawal_amount > current_balance:
        return Rejection(
            message=f"The withdrawal amount of {withdrawal_amount} {denomination} exceeds the available balance of {current_balance} {denomination}.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
    is_partial_withdrawal = withdrawal_amount != current_balance
    maximum_withdrawal_limit = withdrawal_fees__calculate_maximum_withdrawal_limit(
        vault=vault,
        effective_datetime=effective_datetime,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )
    available_withdrawal_limit = maximum_withdrawal_limit - utils_balance_at_coordinates(
        balances=balances,
        address=withdrawal_fees_EARLY_WITHDRAWALS_TRACKER,
        denomination=denomination,
    )
    if is_partial_withdrawal and withdrawal_amount > available_withdrawal_limit:
        return Rejection(
            message=f"The withdrawal amount of {withdrawal_amount} {denomination} would exceed the available withdrawal limit of {available_withdrawal_limit} {denomination}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    calendar_events = vault.get_calendar_events(calendar_ids=["&{PUBLIC_HOLIDAYS}"])
    is_calendar_override = utils_is_key_in_instruction_details(
        key="calendar_override", posting_instructions=posting_instructions
    )
    if utils_falls_on_calendar_events(
        effective_datetime=effective_datetime, calendar_events=calendar_events
    ) and (not is_calendar_override):
        return Rejection(
            message="Cannot withdraw on public holidays.", reason_code=RejectionReason.AGAINST_TNC
        )
    (flat_fee_amount, percentage_fee_amount) = withdrawal_fees_calculate_withdrawal_fee_amounts(
        vault=vault,
        effective_datetime=effective_datetime,
        withdrawal_amount=withdrawal_amount,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )
    total_fee_amount = flat_fee_amount + percentage_fee_amount
    if withdrawal_amount < total_fee_amount:
        return Rejection(
            message=f"The withdrawal fees of {total_fee_amount} {denomination} are not covered by the withdrawal amount of {withdrawal_amount} {denomination}.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
    return None


def withdrawal_fees_handle_withdrawals(
    *,
    vault: Any,
    effective_datetime: datetime,
    posting_instructions: utils_PostingInstructionListAlias,
    product_name: str,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    balance_adjustments: Optional[list[deposit_interfaces_DefaultBalanceAdjustment]] = None,
) -> tuple[list[CustomInstruction], list[AccountNotificationDirective]]:
    """
    For use in the post_posting_hook.
    For a withdrawal:
    - Create instruction to track the withdrawal on the EARLY_WITHDRAWALS_TRACKER address
    - Generate the withdrawal fee notification to be used by the bank to orchestrate the
      fee charging externally

    :param vault: the Vault object for the account
    :param effective_datetime: datetime at which this method is executed
    :param posting_instructions: list of posting instructions containing the withdrawal
    :param product_name: the product name
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the LIVE_BALANCES_BOF_ID
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    For example, interest application adjustment should be negative, and a fee
    charge adjustment should be positive.
    :return: tuple of the withdrawals tracker instructions and the fee notification
    """
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    posting_amount = utils_get_available_balance(
        balances=utils_get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    )
    is_withdrawal = posting_amount < Decimal("0")
    if not is_withdrawal:
        return ([], [])
    withdrawal_amount = abs(posting_amount)
    withdrawal_tracker_instructions = withdrawal_fees__update_tracked_withdrawals(
        account_id=vault.account_id, withdrawal_amount=withdrawal_amount, denomination=denomination
    )
    current_withdrawal_amount_adjustment = (
        withdrawal_fees_get_current_withdrawal_amount_default_balance_adjustment(
            withdrawal_amount=withdrawal_amount
        )
    )
    balance_adjustments = balance_adjustments.copy() if balance_adjustments else []
    balance_adjustments.append(current_withdrawal_amount_adjustment)
    (flat_fee_amount, percentage_fee_amount) = withdrawal_fees_calculate_withdrawal_fee_amounts(
        vault=vault,
        effective_datetime=effective_datetime,
        withdrawal_amount=withdrawal_amount,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )
    withdrawal_fee_notifications = [
        withdrawal_fees_generate_withdrawal_fee_notification(
            account_id=vault.account_id,
            denomination=denomination,
            withdrawal_amount=withdrawal_amount,
            flat_fee_amount=flat_fee_amount,
            percentage_fee_amount=percentage_fee_amount,
            product_name=product_name,
            client_batch_id=posting_instructions[0].client_batch_id,
        )
    ]
    return (withdrawal_tracker_instructions, withdrawal_fee_notifications)


def withdrawal_fees_get_current_withdrawal_amount_default_balance_adjustment(
    *, withdrawal_amount: Decimal
) -> deposit_interfaces_DefaultBalanceAdjustment:
    """

    The customer deposited amount is the sum of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER
    and the returned amount of each adjustment. However, in post-posting the DEFAULT balance has
    current withdrawal deducted, and the EARLY_WITHDRAWALS_TRACKER has not yet been updated to
    reflect the impact of this withdrawal.
    When calculating the fee amounts, we take previous withdrawals into consideration, so updating
    the withdrawals tracker to reflect the current withdrawal would incorrectly imply that the
    current withdrawal has already been processed, hence updating the balances with the
    withdrawal_tracker_instructions is not suitable.
    Instead, we provide a Default Balance Adjustment which returns the withdrawal amount, which
    will allow the customer deposited amount to be calculated correctly.

    :param withdrawal_amount: the absolute amount withdrawn from the account in this transaction
    :return: the default balance adjustment which accounts for the current withdrawal amount
    """
    return deposit_interfaces_DefaultBalanceAdjustment(
        calculate_balance_adjustment=lambda **_: withdrawal_amount
    )


def withdrawal_fees_get_maximum_withdrawal_limit_derived_parameter(
    *,
    vault: Any,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    balance_adjustments: Optional[list[deposit_interfaces_DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Get the maximum withdrawal limit for the derived parameter value

    :param vault: the Vault object for the account
    :param effective_datetime: effective datetime of the hook used for parameter fetching
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the EFFECTIVE_OBSERVATION_FETCHER_ID
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    For example, interest application adjustment should be negative, and a fee
    charge adjustment should be positive.
    :return: the maximum withdrawal limit
    """
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    return withdrawal_fees__calculate_maximum_withdrawal_limit(
        vault=vault,
        balances=balances,
        denomination=denomination,
        effective_datetime=effective_datetime,
        balance_adjustments=balance_adjustments,
    )


def withdrawal_fees_get_fee_free_withdrawal_limit_derived_parameter(
    *,
    vault: Any,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    balance_adjustments: Optional[list[deposit_interfaces_DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Get the fee free withdrawal limit for the derived parameter value

    :param vault: the Vault object for the account
    :param effective_datetime: effective datetime of the hook used for parameter fetching
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the EFFECTIVE_OBSERVATION_FETCHER_ID
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    For example, interest application adjustment should be negative, and a fee
    charge adjustment should be positive.
    :return: the fee free withdrawal limit
    """
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    return withdrawal_fees__calculate_fee_free_withdrawal_limit(
        vault=vault,
        balances=balances,
        denomination=denomination,
        effective_datetime=effective_datetime,
        balance_adjustments=balance_adjustments,
    )


def withdrawal_fees_reset_withdrawals_tracker(
    *, vault: Any, balances: Optional[BalanceDefaultDict] = None, denomination: Optional[str] = None
) -> list[CustomInstruction]:
    """
    Create postings to net-off the withdrawals tracker balance.

    :param vault: the Vault object for the account
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the EARLY_WITHDRAWALS_TRACKER_LIVE_BOF_ID
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :return: list of posting instructions for netting off the withdrawals tracker
    """
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=withdrawal_fees_EARLY_WITHDRAWALS_TRACKER_LIVE_BOF_ID
        ).balances
    tracker_balance = utils_balance_at_coordinates(
        balances=balances,
        address=withdrawal_fees_EARLY_WITHDRAWALS_TRACKER,
        denomination=denomination,
    )
    if tracker_balance > Decimal("0"):
        return [
            CustomInstruction(
                postings=utils_create_postings(
                    amount=tracker_balance,
                    debit_account=vault.account_id,
                    credit_account=vault.account_id,
                    debit_address=withdrawal_fees_EARLY_WITHDRAWALS_TRACKER,
                    credit_address=addresses_INTERNAL_CONTRA,
                    denomination=denomination,
                ),
                instruction_details={"description": "Resetting the withdrawals tracker"},
                override_all_restrictions=True,
            )
        ]
    return []


def withdrawal_fees__update_tracked_withdrawals(
    *, account_id: str, withdrawal_amount: Decimal, denomination: str
) -> list[CustomInstruction]:
    """
    Create posting instructions to update the withdrawals tracker balance.

    :param account_id: id of the customer account
    :param withdrawal_amount: the absolute amount withdrawn from the account in this transaction
    :param denomination: the denomination of the account
    :return: list of custom instructions
    """
    if withdrawal_amount > Decimal("0"):
        return [
            CustomInstruction(
                postings=utils_create_postings(
                    amount=withdrawal_amount,
                    debit_account=account_id,
                    credit_account=account_id,
                    debit_address=addresses_INTERNAL_CONTRA,
                    credit_address=withdrawal_fees_EARLY_WITHDRAWALS_TRACKER,
                    denomination=denomination,
                ),
                instruction_details={"description": "Updating the withdrawals tracker balance"},
                override_all_restrictions=True,
            )
        ]
    return []


def withdrawal_fees_generate_withdrawal_fee_notification(
    *,
    account_id: str,
    denomination: str,
    withdrawal_amount: Decimal,
    flat_fee_amount: Decimal,
    percentage_fee_amount: Decimal,
    product_name: str,
    client_batch_id: str,
) -> AccountNotificationDirective:
    """
    Generate the notification containing the respective fee amounts for a withdrawal

    :param account_id: vault account id for which this notification is sent
    :param denomination: the denomination of the account
    :param withdrawal_amount: the absolute amount withdrawn from the account in this transaction
    :param flat_fee_amount: the flat fee amount chargeable
    :param percentage_fee_amount: the percentage fee amount chargeable
    :param product_name: the product name
    :param client_batch_id: the client_batch_id of the batch containing the withdrawal
    :return: the withdrawal fee account notification directive
    """
    return AccountNotificationDirective(
        notification_type=withdrawal_fees_notification_type(product_name=product_name),
        notification_details={
            "account_id": account_id,
            "denomination": denomination,
            "withdrawal_amount": str(withdrawal_amount),
            "flat_fee_amount": str(flat_fee_amount),
            "percentage_fee_amount": str(percentage_fee_amount),
            "total_fee_amount": str(flat_fee_amount + percentage_fee_amount),
            "client_batch_id": client_batch_id,
        },
    )


def withdrawal_fees_calculate_withdrawal_fee_amounts(
    *,
    vault: Any,
    effective_datetime: datetime,
    withdrawal_amount: Decimal,
    denomination: str,
    balances: BalanceDefaultDict,
    balance_adjustments: Optional[list[deposit_interfaces_DefaultBalanceAdjustment]] = None,
) -> tuple[Decimal, Decimal]:
    """
    Calculate the flat fee and percentage fee amounts that are chargeable against a withdrawal

    :param vault: the Vault object for the account
    :param effective_datetime: datetime of the withdrawal
    :param withdrawal_amount: the absolute amount withdrawn from the account in this transaction
    :param denomination: the denomination of the account
    :param balances: the balances to determine the customer's deposited amount
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    :return: a tuple of the flat fee amount and the percentage fee amount
    """
    amount_subject_to_fee = withdrawal_fees__calculate_withdrawal_amount_subject_to_fees(
        vault=vault,
        effective_datetime=effective_datetime,
        withdrawal_amount=withdrawal_amount,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )
    if amount_subject_to_fee == Decimal("0"):
        return (Decimal("0"), Decimal("0"))
    flat_fee = withdrawal_fees__get_early_withdrawal_flat_fee(
        vault=vault, effective_datetime=effective_datetime
    )
    percentage_fee = utils_round_decimal(
        amount=amount_subject_to_fee
        * withdrawal_fees__get_early_withdrawal_percentage_fee(
            vault=vault, effective_datetime=effective_datetime
        ),
        decimal_places=2,
    )
    return (flat_fee, percentage_fee)


def withdrawal_fees_get_customer_deposit_amount(
    *,
    vault: Any,
    balances: BalanceDefaultDict,
    denomination: str,
    balance_adjustments: Optional[list[deposit_interfaces_DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Calculate the amount the customer has deposited in the account. The customer deposited amount
    is the sum of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and any adjustments to the
    default balance.

    For example, interest application adjustment should be negative, and a fee
    charge adjustment should be positive.

    :param vault: the Vault object for the account
    :param balances: the balances to determine the customer's deposited amount
    :param denomination: the denomination of the account
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount.
    :return: the amount the customer has deposited in the account
    """
    default_balance = utils_balance_at_coordinates(balances=balances, denomination=denomination)
    withdrawals_tracker_balance = utils_balance_at_coordinates(
        balances=balances,
        address=withdrawal_fees_EARLY_WITHDRAWALS_TRACKER,
        denomination=denomination,
    )
    default_balance_adjustment = (
        sum(
            (
                balance_adjustment.calculate_balance_adjustment(
                    vault=vault, balances=balances, denomination=denomination
                )
                for balance_adjustment in balance_adjustments
            )
        )
        if balance_adjustments is not None
        else Decimal("0")
    )
    return default_balance + withdrawals_tracker_balance + default_balance_adjustment


def withdrawal_fees__calculate_withdrawal_amount_subject_to_fees(
    *,
    vault: Any,
    effective_datetime: datetime,
    withdrawal_amount: Decimal,
    denomination: str,
    balances: BalanceDefaultDict,
    balance_adjustments: Optional[list[deposit_interfaces_DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Calculate the withdrawal amount subject to fee. This is the portion of the withdrawal amount
    that exceeds the fee free limit.

    :param vault: the Vault object for the account
    :param effective_datetime: datetime of the withdrawal
    :param withdrawal_amount: the absolute amount withdrawn from the account in this transaction
    :param denomination: the denomination of the account
    :param balances: the balances to determine the customer's deposited amount
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    :return: the amount of the withdrawal which is subject to fees
    """
    withdrawals_tracker_balance = utils_balance_at_coordinates(
        balances=balances,
        address=withdrawal_fees_EARLY_WITHDRAWALS_TRACKER,
        denomination=denomination,
    )
    fee_free_withdrawal_limit = withdrawal_fees__calculate_fee_free_withdrawal_limit(
        vault=vault,
        effective_datetime=effective_datetime,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )
    fee_free_withdrawal_limit_remaining = max(
        fee_free_withdrawal_limit - withdrawals_tracker_balance, Decimal("0")
    )
    return max(withdrawal_amount - fee_free_withdrawal_limit_remaining, Decimal("0"))


def withdrawal_fees__calculate_maximum_withdrawal_limit(
    *,
    vault: Any,
    effective_datetime: datetime,
    balances: BalanceDefaultDict,
    denomination: str,
    balance_adjustments: Optional[list[deposit_interfaces_DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Calculate the maximum withdrawal limit as a percentage of the customer's deposited amount

    :param vault: the Vault object for the account
    :param effective_datetime: effective datetime of the hook used for parameter fetching
    :param balances: the balances to determine the customer's deposited amount
    :param denomination: the denomination of the account
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    :return: the maximum withdrawal limit
    """
    customer_deposit_amount = withdrawal_fees_get_customer_deposit_amount(
        vault=vault,
        balances=balances,
        denomination=denomination,
        balance_adjustments=balance_adjustments,
    )
    return utils_round_decimal(
        amount=customer_deposit_amount
        * withdrawal_fees__get_maximum_withdrawal_percentage_limit(
            vault=vault, effective_datetime=effective_datetime
        ),
        decimal_places=2,
    )


def withdrawal_fees__calculate_fee_free_withdrawal_limit(
    *,
    vault: Any,
    effective_datetime: datetime,
    balances: BalanceDefaultDict,
    denomination: str,
    balance_adjustments: Optional[list[deposit_interfaces_DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Calculate the fee free withdrawal limit as a percentage of the customer's deposited amount

    :param vault: the Vault object for the account
    :param effective_datetime: effective datetime of the hook used for parameter fetching
    :param balances: the balances to determine the customer's deposited amount
    :param denomination: the denomination of the account
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, EARLY_WITHDRAWALS_TRACKER and the returned amount of each adjustment.
    :return: the fee free withdrawal limit
    """
    customer_deposit_amount = withdrawal_fees_get_customer_deposit_amount(
        vault=vault,
        balances=balances,
        denomination=denomination,
        balance_adjustments=balance_adjustments,
    )
    return utils_round_decimal(
        amount=customer_deposit_amount
        * withdrawal_fees__get_fee_free_withdrawal_percentage_limit(
            vault=vault, effective_datetime=effective_datetime
        ),
        decimal_places=2,
    )


def withdrawal_fees__get_early_withdrawal_flat_fee(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return Decimal(
        utils_get_parameter(
            vault=vault,
            name=withdrawal_fees_PARAM_EARLY_WITHDRAWAL_FLAT_FEE,
            at_datetime=effective_datetime,
        )
    )


def withdrawal_fees__get_early_withdrawal_percentage_fee(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return Decimal(
        utils_get_parameter(
            vault=vault,
            name=withdrawal_fees_PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE,
            at_datetime=effective_datetime,
        )
    )


def withdrawal_fees__get_maximum_withdrawal_percentage_limit(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return Decimal(
        utils_get_parameter(
            vault=vault,
            name=withdrawal_fees_PARAM_MAXIMUM_WITHDRAWAL_PERCENTAGE_LIMIT,
            at_datetime=effective_datetime,
        )
    )


def withdrawal_fees__get_fee_free_withdrawal_percentage_limit(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return Decimal(
        utils_get_parameter(
            vault=vault,
            name=withdrawal_fees_PARAM_FEE_FREE_WITHDRAWAL_PERCENTAGE_LIMIT,
            at_datetime=effective_datetime,
        )
    )


# Objects below have been imported from:
#    grace_period.py
# md5:4f0810e74f5d91e4e179e7c7ded567b1

grace_period_PARAM_GRACE_PERIOD = "grace_period"
grace_period_PARAM_GRACE_PERIOD_END_DATE = "grace_period_end_date"
grace_period_GRACE_PERIOD_END_SUFFIX = "_GRACE_PERIOD_END"
grace_period_GRACE_PERIOD_END_EVENT = "GRACE_PERIOD_END"
grace_period_parameters = [
    Parameter(
        name=grace_period_PARAM_GRACE_PERIOD,
        level=ParameterLevel.TEMPLATE,
        description="The number of days from the account creation datetime when a user can make amendments to a deposit account without incurring any fees or penalties.",
        display_name="Grace Period Length (days)",
        shape=NumberShape(min_value=0, step=1),
        default_value=5,
    ),
    Parameter(
        name=grace_period_PARAM_GRACE_PERIOD_END_DATE,
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The grace period will end at 23:59:59.999999 (inclusive) on this day. If 0001-01-01 is returned, this parameter is not valid for this account.",
        display_name="Grace Period End Date",
        shape=DateShape(),
    ),
]


def grace_period_notification_type(*, product_name: str) -> str:
    """
    Returns a notification type
    :param product_name: The product name
    :return: notification type
    """
    return f"{product_name.upper()}{grace_period_GRACE_PERIOD_END_SUFFIX}"


def grace_period_event_types(*, product_name: str) -> list[SmartContractEventType]:
    """
    Returns a list of event types
    :param product_name: name of the product
    :return: list of SmartContractEventType
    """
    return [
        SmartContractEventType(
            name=grace_period_GRACE_PERIOD_END_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{grace_period_GRACE_PERIOD_END_EVENT}_AST"],
        )
    ]


def grace_period_scheduled_events(*, vault: Any) -> dict[str, ScheduledEvent]:
    """
    Creates one off scheduled event for grace period end balance check
    :param vault: Vault object to retrieve account creation datetime and grace period
    :return: dict of grace period end scheduled event
    """
    grace_period_end_datetime = grace_period_get_grace_period_end_datetime(vault=vault)
    scheduled_event = ScheduledEvent(
        start_datetime=grace_period_end_datetime - relativedelta(seconds=1),
        expression=utils_one_off_schedule_expression(schedule_datetime=grace_period_end_datetime),
        end_datetime=grace_period_end_datetime,
    )
    return {grace_period_GRACE_PERIOD_END_EVENT: scheduled_event}


def grace_period_get_grace_period_end_datetime(*, vault: Any) -> datetime:
    """
    Calculates and returns the grace period end datetime. This date will represent the
    midnight of the account creation datetime plus the number of days in the grace period,
    inclusive of the account creation datetime.
    :param vault: Vault object for the account
    :return: the datetime when the grace period ends
    """
    grace_period = grace_period_get_grace_period_parameter(vault=vault)
    account_creation_datetime = vault.get_account_creation_datetime()
    grace_period_end = (account_creation_datetime + relativedelta(days=grace_period)).replace(
        hour=23, minute=59, second=59, microsecond=999999
    )
    return grace_period_end


def grace_period_is_within_grace_period(*, vault: Any, effective_datetime: datetime) -> bool:
    """
    Determines whether the effective datetime is within the grace period of an account

    :param vault: Vault object for the account
    :param effective_datetime: datetime to be checked whether is within the grace period
    :return: True if the effective datetime is less than or equal to the grace period end datetime
    """
    return effective_datetime <= grace_period_get_grace_period_end_datetime(vault=vault)


def grace_period_validate_deposit(
    *,
    vault: Any,
    effective_datetime: datetime,
    posting_instructions: utils_PostingInstructionListAlias,
    denomination: Optional[str] = None,
) -> Optional[Rejection]:
    """
    Reject the posting instructions if deposits are sent after the end of grace period
    Accept deposits within the grace period

    :param vault: Vault object for the account against which this validation is applied
    :param effective_datetime: datetime at which this method is executed
    :param posting_instructions: list of posting instructions to validate
    :param denomination: the denomination of the account
    :return: rejection if any of the above conditions are met
    """
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    is_deposit = utils_get_current_credit_balance(
        balances=utils_get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    ) > Decimal("0")
    if is_deposit and (
        not grace_period_is_within_grace_period(vault=vault, effective_datetime=effective_datetime)
    ):
        return Rejection(
            message="No deposits are allowed after the grace period end",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


def grace_period_is_withdrawal_subject_to_fees(
    *,
    vault: Any,
    effective_datetime: datetime,
    posting_instructions: utils_PostingInstructionListAlias,
    denomination: Optional[str] = None,
) -> bool:
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    is_withdrawal = utils_get_available_balance(
        balances=utils_get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    ) < Decimal("0")
    if is_withdrawal and (
        not grace_period_is_within_grace_period(vault=vault, effective_datetime=effective_datetime)
    ):
        return True
    return False


def grace_period_validate_term_parameter_change(
    *, vault: Any, effective_datetime: datetime
) -> Optional[Rejection]:
    """
    Allow changes to the 'term' parameter within grace period, reject change outside grace period

    :param vault: Vault object for the account
    :param effective_datetime: datetime of the parameter change
    :return: rejection if parameter changed outside the grace period
    """
    if not grace_period_is_within_grace_period(vault=vault, effective_datetime=effective_datetime):
        return Rejection(
            message="Term length cannot be changed outside the grace period",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


def grace_period_handle_account_closure_notification(
    *,
    vault: Any,
    product_name: str,
    effective_datetime: datetime,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> list[AccountNotificationDirective]:
    """
    Send account closure notification when no funds are present in the account
    at the end of grace period
    :param vault: Vault object to retrieve account creation datetime and grace period
    :param product_name: the name of the product for notification type
    :param effective_datetime: datetime at which this method is executed
    :param denomination: the denomination of the account
    :param balances: effective account balances available, if not provided will be retrieved
    using the EFFECTIVE_OBSERVATION_FETCHER_ID fetcher id
    :return: account closure notification
    """
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    net_balance = utils_get_current_net_balance(balances=balances, denomination=denomination)
    if net_balance == Decimal(0):
        return [
            AccountNotificationDirective(
                notification_type=grace_period_notification_type(product_name=product_name),
                notification_details={
                    "account_id": vault.account_id,
                    "grace_period_end_datetime": str(effective_datetime),
                    "reason": "Close account due to lack of funds at the end of grace period",
                },
            )
        ]
    return []


def grace_period_get_grace_period_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils_get_parameter(
            vault=vault, name=grace_period_PARAM_GRACE_PERIOD, at_datetime=effective_datetime
        )
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


def deposit_interest_accrual_common_get_target_customer_address_and_internal_account(
    *,
    vault: Any,
    accrual_amount: Decimal,
    accrued_interest_payable_account: Optional[str] = None,
    accrued_interest_receivable_account: Optional[str] = None,
) -> tuple[str, str]:
    """
    Return the payable or receivable customer address and internal account based on the
    sign of the accrual amount

    :param vault: the vault object used to fetch parameter values
    :param accrual_amount: the amount of interest to accrue
    :param accrued_interest_payable_account: the accrued interest payable account, defaults
    to the value in the parameter if not provided
    :param accrued_interest_receivable_account: the accrued interest receivable account, defaults
    to the value in the parameter if not provided
    :return: target customer address, target internal account
    """
    if accrued_interest_payable_account is None:
        accrued_interest_payable_account = (
            interest_accrual_common_get_accrued_interest_payable_account_parameter(vault=vault)
        )
    if accrued_interest_receivable_account is None:
        accrued_interest_receivable_account = (
            interest_accrual_common_get_accrued_interest_receivable_account_parameter(vault=vault)
        )
    return (
        (interest_accrual_common_ACCRUED_INTEREST_PAYABLE, accrued_interest_payable_account)
        if accrual_amount >= 0
        else (
            interest_accrual_common_ACCRUED_INTEREST_RECEIVABLE,
            accrued_interest_receivable_account,
        )
    )


# Objects below have been imported from:
#    fixed_interest_accrual.py
# md5:a0c55a82cd86845e93a7fdcdb488f9d4

fixed_interest_accrual_ACCRUAL_EVENT = interest_accrual_common_ACCRUAL_EVENT
fixed_interest_accrual_ACCRUED_INTEREST_PAYABLE = interest_accrual_common_ACCRUED_INTEREST_PAYABLE
fixed_interest_accrual_PARAM_FIXED_INTEREST_RATE = "fixed_interest_rate"
fixed_interest_accrual_positive_fixed_interest_parameter = Parameter(
    name=fixed_interest_accrual_PARAM_FIXED_INTEREST_RATE,
    level=ParameterLevel.INSTANCE,
    description="The fixed annual rate of the product",
    display_name="Fixed Interest Rate",
    shape=NumberShape(min_value=Decimal("0")),
    default_value=Decimal("0.00"),
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)
fixed_interest_accrual_positive_fixed_interest_parameters = [
    fixed_interest_accrual_positive_fixed_interest_parameter,
    interest_accrual_common_accrued_interest_payable_account_param,
    interest_accrual_common_accrued_interest_receivable_account_param,
    *interest_accrual_common_accrual_parameters,
    *interest_accrual_common_schedule_parameters,
]
fixed_interest_accrual_event_types = interest_accrual_common_event_types
fixed_interest_accrual_scheduled_events = interest_accrual_common_scheduled_events
fixed_interest_accrual_get_accrual_capital = deposit_interest_accrual_common_get_accrual_capital
fixed_interest_accrual_get_interest_reversal_postings = (
    deposit_interest_accrual_common_get_interest_reversal_postings
)


def fixed_interest_accrual_get_fixed_interest_rate_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return Decimal(
        utils_get_parameter(
            vault=vault,
            name=fixed_interest_accrual_PARAM_FIXED_INTEREST_RATE,
            at_datetime=effective_datetime,
        )
    )


def fixed_interest_accrual_get_daily_interest_rate(
    *, vault: Any, effective_datetime: datetime
) -> Decimal:
    annual_rate = fixed_interest_accrual_get_fixed_interest_rate_parameter(vault=vault)
    days_in_year = interest_accrual_common_get_days_in_year_parameter(vault=vault)
    return utils_yearly_to_daily_rate(
        effective_date=effective_datetime, yearly_rate=annual_rate, days_in_year=days_in_year
    )


def fixed_interest_accrual_accrue_interest(
    *,
    vault: Any,
    effective_datetime: datetime,
    account_type: str,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    accrued_interest_payable_account: Optional[str] = None,
    accrued_interest_receivable_account: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Accrue interest on the sum of EOD balances held at the capital addresses.

    :param vault: the vault object to use to for retrieving data and instructing directives
    :param effective_datetime: the effective date to retrieve capital balances to accrue on
    :param account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :param denomination: the denomination of the account
    :param balances: balances to accrue interest on. EOD balances are fetched if not provided
    :param accrued_interest_payable_account: the accrued interest payable account, defaults
    to the value in the parameter if not provided
    :param accrued_interest_receivable_account: the accrued interest receivable account, defaults
    to the value in the parameter if not provided
    :return: the accrual posting custom instructions
    """
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    rounding_precision = interest_accrual_common_get_accrual_precision_parameter(vault=vault)
    daily_rate = fixed_interest_accrual_get_daily_interest_rate(
        vault=vault, effective_datetime=effective_datetime
    )
    effective_balance = fixed_interest_accrual_get_accrual_capital(vault=vault, balances=balances)
    accrual_amount = utils_round_decimal(
        amount=effective_balance * daily_rate, decimal_places=rounding_precision
    )
    instruction_details = utils_standard_instruction_details(
        description=f"Daily interest accrued at {daily_rate * 100:0.5f}% on balance of {effective_balance:0.2f}",
        event_type=interest_accrual_common_ACCRUAL_EVENT,
        gl_impacted=True,
        account_type=account_type,
    )
    (
        target_customer_address,
        target_internal_account,
    ) = deposit_interest_accrual_common_get_target_customer_address_and_internal_account(
        vault=vault,
        accrual_amount=accrual_amount,
        accrued_interest_payable_account=accrued_interest_payable_account,
        accrued_interest_receivable_account=accrued_interest_receivable_account,
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


fixed_interest_accrual_get_accrued_interest_payable_account_parameter = (
    interest_accrual_common_get_accrued_interest_payable_account_parameter
)
fixed_interest_accrual_get_interest_accrual_precision = (
    interest_accrual_common_get_accrual_precision_parameter
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
#    time_deposit.py
# md5:db11fbb572c9721db6586d8afda2e065

PRODUCT_NAME = "TIME_DEPOSIT"
APPLIED_INTEREST_TRACKER = "APPLIED_INTEREST_TRACKER"
ACCOUNT_CLOSURE_EVENT = "ACCOUNT_CLOSURE"
data_fetchers = [
    fetchers_LIVE_BALANCES_BOF,
    fetchers_EFFECTIVE_OBSERVATION_FETCHER,
    fetchers_EOD_FETCHER,
    withdrawal_fees_EARLY_WITHDRAWALS_TRACKER_LIVE_FETCHER,
]
ACCOUNT_MATURITY_NOTIFICATION = deposit_maturity_notification_type_at_account_maturity(
    product_name=PRODUCT_NAME
)
DEPOSIT_PERIOD_NOTIFICATION = deposit_period_notification_type(product_name=PRODUCT_NAME)
FULL_WITHDRAWAL_NOTIFICATION = f"{PRODUCT_NAME}_FULL_WITHDRAWAL"
GRACE_PERIOD_NOTIFICATION = grace_period_notification_type(product_name=PRODUCT_NAME)
NOTIFY_UPCOMING_MATURITY_NOTIFICATION = deposit_maturity_notification_type_notify_upcoming_maturity(
    product_name=PRODUCT_NAME
)
WITHDRAWAL_FEES_NOTIFICATION = withdrawal_fees_notification_type(product_name=PRODUCT_NAME)
notification_types = [
    ACCOUNT_MATURITY_NOTIFICATION,
    DEPOSIT_PERIOD_NOTIFICATION,
    FULL_WITHDRAWAL_NOTIFICATION,
    GRACE_PERIOD_NOTIFICATION,
    NOTIFY_UPCOMING_MATURITY_NOTIFICATION,
    WITHDRAWAL_FEES_NOTIFICATION,
]
event_types = [
    *interest_application_event_types(product_name=PRODUCT_NAME),
    *fixed_interest_accrual_event_types(product_name=PRODUCT_NAME),
    *deposit_period_event_types(product_name=PRODUCT_NAME),
    *grace_period_event_types(product_name=PRODUCT_NAME),
    *deposit_maturity_event_types(product_name=PRODUCT_NAME),
]
PARAM_NUMBER_OF_INTEREST_DAYS_EARLY_WITHDRAWAL_FEE = "number_of_interest_days_early_withdrawal_fee"
number_of_interest_days_early_withdrawal_fee_parameter = Parameter(
    name=PARAM_NUMBER_OF_INTEREST_DAYS_EARLY_WITHDRAWAL_FEE,
    shape=OptionalShape(shape=NumberShape(min_value=Decimal("0"), step=Decimal("1"))),
    level=ParameterLevel.TEMPLATE,
    description="The number of days of interest to be charged as a fee when making an early withdrawal. If this is configured, the Early Withdrawal Percentage Fee is ignored.",
    display_name="Number Of Days Of Interest To Be Charged As An Early Withdrawal Fee",
    default_value=OptionalValue(Decimal("0")),
)
parameters = [
    number_of_interest_days_early_withdrawal_fee_parameter,
    common_parameters_denomination_parameter,
    *deposit_parameters_term_parameters,
    *cooling_off_period_parameters,
    *deposit_maturity_maturity_parameters,
    *deposit_period_parameters,
    *fixed_interest_accrual_positive_fixed_interest_parameters,
    *grace_period_parameters,
    *interest_application_parameters,
    *maximum_balance_limit_parameters,
    *minimum_initial_deposit_parameters,
    *withdrawal_fees_parameters,
]


def _is_renewed_time_deposit(vault: Any, effective_datetime: datetime) -> bool:
    """
    A time deposit account with a grace period greater than 1 is assumed to be a renewed time
    deposit
    """
    return (
        grace_period_get_grace_period_parameter(vault=vault, effective_datetime=effective_datetime)
        > 0
    )


def _validate_term_parameter_change(
    *, vault: Any, effective_datetime: datetime, proposed_term_value: int
) -> Optional[Rejection]:
    if _is_renewed_time_deposit(vault=vault, effective_datetime=effective_datetime):
        if grace_period_rejection := grace_period_validate_term_parameter_change(
            vault=vault, effective_datetime=effective_datetime
        ):
            return grace_period_rejection
        if deposit_maturity_rejection := deposit_maturity_validate_term_parameter_change(
            vault=vault,
            effective_datetime=effective_datetime,
            proposed_term_value=proposed_term_value,
        ):
            return deposit_maturity_rejection
    else:
        return Rejection(
            message="Term length can only be changed on Renewed Time Deposit accounts",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


def _update_tracked_applied_interest(
    application_custom_instructions: list[CustomInstruction], account_id: str, denomination: str
) -> list[CustomInstruction]:
    """
    Create posting instructions to update the applied interest tracker balance.

    :param application_custom_instructions: the list of custom instructions for the application
    of interest to the DEFAULT balance
    :param account_id: the id of the deposit account
    :param denomination: the denomination the posting should be made in
    :return: list of applied interest tracking posting instructions
    """
    application_amount = Decimal(
        sum(
            (
                utils_get_current_net_balance(
                    balances=instruction.balances(account_id=account_id, tside=Tside.LIABILITY),
                    denomination=denomination,
                )
                for instruction in application_custom_instructions
            )
        )
    )
    if application_amount > Decimal("0"):
        return [
            CustomInstruction(
                postings=utils_create_postings(
                    amount=application_amount,
                    debit_account=account_id,
                    credit_account=account_id,
                    debit_address=addresses_INTERNAL_CONTRA,
                    credit_address=APPLIED_INTEREST_TRACKER,
                    denomination=denomination,
                ),
                instruction_details={
                    "description": "Updating the applied interest tracker balance"
                },
                override_all_restrictions=True,
            )
        ]
    return []


def _reset_applied_interest_tracker(
    balances: BalanceDefaultDict, account_id: str, denomination: str
) -> list[CustomInstruction]:
    """
    Create postings to net-off the applied interest tracker balance.

    :param balances: the balances of the account
    :param account_id: the id of the deposit account
    :param denomination: the denomination the posting should be made in
    :return: list of posting instructions for netting off the tracked applied interest
    """
    tracker_balance = utils_balance_at_coordinates(
        balances=balances, address=APPLIED_INTEREST_TRACKER, denomination=denomination
    )
    if tracker_balance > Decimal("0"):
        return [
            CustomInstruction(
                postings=utils_create_postings(
                    amount=tracker_balance,
                    debit_account=account_id,
                    credit_account=account_id,
                    debit_address=APPLIED_INTEREST_TRACKER,
                    credit_address=addresses_INTERNAL_CONTRA,
                    denomination=denomination,
                ),
                instruction_details={"description": "Resetting the applied interest tracker"},
                override_all_restrictions=True,
            )
        ]
    return []


def _handle_partial_interest_forfeiture(
    vault: Any,
    effective_datetime: datetime,
    balances: BalanceDefaultDict,
    withdrawal_amount: Decimal,
) -> list[CustomInstruction]:
    """
    This function determines the amount of accrued interest to be forfeited as a result of a
    withdrawal. The forfeited interest is simply calculated as the ratio of
    withdrawal_amount:balance_before_withdrawal. This is only possible because the interest accrual
    feature used is flat interest.

    :param vault: Vault object of the account
    :param effective_datetime: datetime of the withdrawal
    :param balances: account balances
    :param withdrawal_amount: The absolute amount withdrawn from the account in this transaction
    :return: interest forfeiture instructions
    """
    accrual_precision = fixed_interest_accrual_get_interest_accrual_precision(
        vault=vault, effective_datetime=effective_datetime
    )
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    accrual_address = fixed_interest_accrual_ACCRUED_INTEREST_PAYABLE
    accrued_interest_balance = utils_balance_at_coordinates(
        balances=balances, denomination=denomination, address=accrual_address
    )
    account_deposit_balance = utils_balance_at_coordinates(
        balances=balances, denomination=denomination, address=DEFAULT_ADDRESS
    )
    account_balance_before_withdrawal = account_deposit_balance + withdrawal_amount
    forfeited_interest_amount = utils_round_decimal(
        amount=withdrawal_amount / account_balance_before_withdrawal * accrued_interest_balance,
        decimal_places=accrual_precision,
    )
    if forfeited_interest_amount > Decimal("0"):
        accrual_internal_account = (
            fixed_interest_accrual_get_accrued_interest_payable_account_parameter(
                vault=vault, effective_datetime=effective_datetime
            )
        )
        return [
            CustomInstruction(
                postings=utils_create_postings(
                    amount=forfeited_interest_amount,
                    debit_account=vault.account_id,
                    credit_account=accrual_internal_account,
                    debit_address=accrual_address,
                    credit_address=DEFAULT_ADDRESS,
                    denomination=denomination,
                ),
                override_all_restrictions=True,
            )
        ]
    return []


def _handle_full_withdrawal_notification(
    *, vault: Any, effective_datetime: datetime, balances: BalanceDefaultDict, denomination: str
) -> list[AccountNotificationDirective]:
    """
    For use in the post-posting hook.
    Return a notification if a full withdrawal occurs outside of the grace
    period (for renewed TDs), or outside of the deposit period (for new TDs).

    :param vault: Vault object of the account
    :param effective_datetime: datetime of the withdrawal
    :param balances: the balances of the account
    :param denomination: the denomination of the account
    :return: list of account notification directives
    """
    if utils_get_available_balance(balances=balances, denomination=denomination) == Decimal("0"):
        is_renewed = _is_renewed_time_deposit(vault=vault, effective_datetime=effective_datetime)
        if (
            is_renewed
            and (
                not grace_period_is_within_grace_period(
                    vault=vault, effective_datetime=effective_datetime
                )
            )
            or (
                not is_renewed
                and (
                    not deposit_period_is_within_deposit_period(
                        vault=vault, effective_datetime=effective_datetime
                    )
                )
            )
        ):
            return [
                AccountNotificationDirective(
                    notification_type=FULL_WITHDRAWAL_NOTIFICATION,
                    notification_details={
                        "account_id": vault.account_id,
                        "reason": "The account balance has been fully withdrawn.",
                    },
                )
            ]
    return []


def _handle_withdrawal_fees_with_number_of_interest_days_fee(
    *,
    vault: Any,
    withdrawal_fee_notification: AccountNotificationDirective,
    withdrawal_amount: Decimal,
    effective_datetime: datetime,
    balances: BalanceDefaultDict,
    denomination: str,
) -> list[AccountNotificationDirective]:
    """
    For use in the post_posting_hook.
    Calculate the number of interest days fee, and update the existing WITHDRAWAL_FEES_NOTIFICATION
    to include the `number_of_interest_days_fee` key.

    :param vault: the Vault object for the account
    :param withdrawal_fee_notification: the existing withdrawals fee notification
    :param withdrawal_amount: the absolute amount withdrawn from the account in this transaction
    :param effective_datetime: datetime at which this method is executed
    :param balances: latest account balances available
    :param denomination: the denomination of the account
    :return: a list containing the updated notification
    """
    number_of_interest_days_fee = _calculate_number_of_interest_days_fee(
        vault=vault,
        effective_datetime=effective_datetime,
        denomination=denomination,
        balances=balances,
        balance_adjustments=[
            *TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
            withdrawal_fees_get_current_withdrawal_amount_default_balance_adjustment(
                withdrawal_amount=withdrawal_amount
            ),
        ],
    )
    withdrawal_fee_notification = _update_notification_with_number_of_interest_days_fee(
        withdrawal_fee_notification=withdrawal_fee_notification,
        number_of_interest_days_fee=number_of_interest_days_fee,
    )
    return [withdrawal_fee_notification]


def _calculate_number_of_interest_days_fee(
    *,
    vault: Any,
    effective_datetime: datetime,
    denomination: str,
    balances: BalanceDefaultDict,
    balance_adjustments: Optional[list[deposit_interfaces_DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Calculate the number of interest days fee that is chargeable against a withdrawal

    :param vault: the Vault object for the account
    :param effective_datetime: datetime of the withdrawal
    :param denomination: the denomination of the account
    :param balances: the balances to determine the customer's deposited amount
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, WITHDRAWALS_TRACKER balance and the returned amount of each adjustment.
    :return: the number of interest days fee
    """
    if (
        number_of_interest_days := _get_number_of_interest_days_early_withdrawal_fee_parameter(
            vault=vault, effective_datetime=effective_datetime
        )
    ) == Decimal("0"):
        return Decimal("0")
    daily_interest_rate = fixed_interest_accrual_get_daily_interest_rate(
        vault=vault, effective_datetime=effective_datetime
    )
    customer_deposited_amount = withdrawal_fees_get_customer_deposit_amount(
        vault=vault,
        balances=balances,
        denomination=denomination,
        balance_adjustments=balance_adjustments,
    )
    return utils_round_decimal(
        amount=customer_deposited_amount * daily_interest_rate * number_of_interest_days,
        decimal_places=2,
    )


def _update_notification_with_number_of_interest_days_fee(
    *,
    withdrawal_fee_notification: AccountNotificationDirective,
    number_of_interest_days_fee: Decimal,
) -> AccountNotificationDirective:
    """
    Update the existing WITHDRAWAL_FEES_NOTIFICATION to include the `number_of_interest_days_fee`
    key. If the `number_of_interest_days_fee` is non-zero, it overrides the percentage fee amount
    and the `total_fee_amount` is updated to reflect the final fee amounts.

    :param withdrawal_fee_notification: the existing withdrawals fee notification
    :param number_of_interest_days_fee: the amount to charge as the number of interest days fee
    :return: the updated notification
    """
    notification_details = withdrawal_fee_notification.notification_details
    notification_details.update(
        {
            "number_of_interest_days_fee": str(number_of_interest_days_fee),
            "percentage_fee_amount": "0",
        }
        if number_of_interest_days_fee != Decimal("0")
        else {"number_of_interest_days_fee": "0"}
    )
    notification_details.update(
        {
            "total_fee_amount": str(
                Decimal(notification_details["flat_fee_amount"])
                + Decimal(notification_details["percentage_fee_amount"])
                + Decimal(notification_details["number_of_interest_days_fee"])
            )
        }
    )
    return AccountNotificationDirective(
        notification_type=WITHDRAWAL_FEES_NOTIFICATION, notification_details=notification_details
    )


def _validate_withdrawals_with_number_of_interest_days_fee(
    *,
    vault: Any,
    effective_datetime: datetime,
    posting_instructions: utils_PostingInstructionListAlias,
    denomination: str,
    balances: BalanceDefaultDict,
    balance_adjustments: Optional[list[deposit_interfaces_DefaultBalanceAdjustment]] = None,
) -> Optional[Rejection]:
    """
    For use in the pre_posting_hook.
    Deposits are accepted with no validation.
    Reject the posting instructions if the withdrawal amount is less than the incurred
    withdrawal fee amount, considering the number of interest days fee if configured

    :param vault: the Vault object for the account against which this validation is applied
    :param effective_datetime: datetime at which this method is executed
    :param posting_instructions: list of posting instructions to validate
    :param denomination: the denomination of the account
    :param balances: latest account balances available
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, WITHDRAWALS_TRACKER balance and the returned amount of each adjustment.
    For example, interest application adjustment should be negative, and a fee
    charge adjustment should be positive.
    :return: rejection if any of the above conditions are met
    """
    posting_amount = utils_get_available_balance(
        balances=utils_get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    )
    if posting_amount >= Decimal("0"):
        return None
    withdrawal_amount = abs(posting_amount)
    number_of_interest_days_fee_amount = _calculate_number_of_interest_days_fee(
        vault=vault,
        effective_datetime=effective_datetime,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )
    if number_of_interest_days_fee_amount == Decimal("0"):
        return None
    (flat_fee_amount, percentage_fee_amount) = withdrawal_fees_calculate_withdrawal_fee_amounts(
        vault=vault,
        effective_datetime=effective_datetime,
        withdrawal_amount=withdrawal_amount,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )
    total_fee_amount = (
        flat_fee_amount + number_of_interest_days_fee_amount
        if number_of_interest_days_fee_amount
        else flat_fee_amount + percentage_fee_amount
    )
    if withdrawal_amount < total_fee_amount:
        return Rejection(
            message=f"The withdrawal fees of {total_fee_amount} {denomination} are not covered by the withdrawal amount of {withdrawal_amount} {denomination}.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
    return None


def _get_number_of_interest_days_early_withdrawal_fee_parameter(
    *, vault: Any, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils_get_parameter(
            vault=vault,
            name=PARAM_NUMBER_OF_INTEREST_DAYS_EARLY_WITHDRAWAL_FEE,
            at_datetime=effective_datetime,
            is_optional=True,
            default_value=0,
        )
    )


def _calculate_applied_interest_balance_adjustment(
    vault: Any, balances: Optional[BalanceDefaultDict] = None, denomination: Optional[str] = None
) -> Decimal:
    """
    Return the negative of the APPLIED_INTEREST_TRACKER total, to be used by the
    DefaultBalanceAdjustment interface.

    Since applying interest increases the DEFAULT balance, the adjustment must be
    negative, and since the APPLIED_INTEREST_TRACKER is always positive by design,
    we can simply negate the fetched value.

    :param vault: the Vault object for the account
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the LIVE_BALANCES_BOF_ID
    :return: the negative of the APPLIED_INTEREST_TRACKER value
    """
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    tracker_balance = utils_balance_at_coordinates(
        balances=balances, address=APPLIED_INTEREST_TRACKER, denomination=denomination
    )
    return -tracker_balance


applied_interest_balance_adjustment = deposit_interfaces_DefaultBalanceAdjustment(
    calculate_balance_adjustment=_calculate_applied_interest_balance_adjustment
)
TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS: list[deposit_interfaces_DefaultBalanceAdjustment] = [
    applied_interest_balance_adjustment
]
