# Code auto-generated using Inception Smart Contract Renderer Version 2.0.1


# Objects below have been imported from:
#    line_of_credit_supervisor.py
# md5:f1caa8160814498877fb6ca7e7ab7eee

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
    AccountNotificationDirective,
    PostingInstructionsDirective,
    PostPostingHookResult,
    ScheduledEventHookResult,
    SupervisorContractEventType,
    SupervisorScheduledEventHookArguments,
    UpdatePlanEventTypeDirective,
    NumberShape,
    ParameterUpdatePermission,
    AccountIdShape,
    DateShape,
    ScheduledEventHookArguments,
    SmartContractEventType,
    BalancesFilter,
    BalancesObservation,
    ActivationHookArguments,
    ActivationHookResult,
    DeactivationHookArguments,
    DeactivationHookResult,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    PrePostingHookArguments,
    PrePostingHookResult,
    fetch_account_data,
    requires,
    PostPostingHookArguments,
    SupervisorPostPostingHookArguments,
    StringShape,
    SmartContractDescriptor,
    SupervisedHooks,
    SupervisionExecutionMode,
    SupervisorActivationHookArguments,
    SupervisorActivationHookResult,
    SupervisorPostPostingHookResult,
    SupervisorPrePostingHookArguments,
    SupervisorPrePostingHookResult,
    SupervisorScheduledEventHookResult,
)
from calendar import isleap
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import ROUND_HALF_UP, Decimal, ROUND_CEILING
from json import dumps, loads
import math
from typing import Optional, Union, Any, Iterable, Mapping, Callable, NamedTuple
from zoneinfo import ZoneInfo

api = "4.0.0"
version = "2.0.0"
supervised_smart_contracts = [
    SmartContractDescriptor(
        alias="line_of_credit",
        smart_contract_version_id="&{line_of_credit}",
        supervise_post_posting_hook=True,
        supervised_hooks=SupervisedHooks(pre_posting_hook=SupervisionExecutionMode.INVOKED),
    ),
    SmartContractDescriptor(alias="drawdown_loan", smart_contract_version_id="&{drawdown_loan}"),
]


def activation_hook(
    vault: Any, hook_arguments: SupervisorActivationHookArguments
) -> Optional[SupervisorActivationHookResult]:
    scheduled_events: dict[str, ScheduledEvent] = {}
    plan_opening_datetime = vault.get_plan_opening_datetime()
    month_after_opening = plan_opening_datetime.replace(hour=0, minute=0, second=0) + relativedelta(
        months=1
    )
    scheduled_events.update(supervisor_utils_supervisee_schedule_sync_scheduled_event(vault=vault))
    scheduled_events[interest_accrual_supervisor_ACCRUAL_EVENT] = utils_create_end_of_time_schedule(
        start_datetime=plan_opening_datetime
    )
    scheduled_events[
        due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
    ] = utils_create_end_of_time_schedule(start_datetime=month_after_opening)
    scheduled_events[overdue_CHECK_OVERDUE_EVENT] = utils_create_end_of_time_schedule(
        start_datetime=month_after_opening
    )
    scheduled_events[delinquency_CHECK_DELINQUENCY_EVENT] = utils_create_end_of_time_schedule(
        start_datetime=plan_opening_datetime
    )
    return SupervisorActivationHookResult(scheduled_events_return_value=scheduled_events)


@requires(parameters=True, data_scope="all", balances="1 days")
def post_posting_hook(
    vault: Any, hook_arguments: SupervisorPostPostingHookArguments
) -> Optional[SupervisorPostPostingHookResult]:
    supervisee_posting_directives: dict[str, list[PostingInstructionsDirective]] = {}
    account_notification_directives: dict[str, list[AccountNotificationDirective]] = {}
    (loc_vault, loan_vaults) = _get_loc_and_loan_supervisee_vault_objects(vault=vault)
    denomination = common_parameters_get_denomination_parameter(vault=loc_vault)
    posting_instructions = hook_arguments.supervisee_posting_instructions[loc_vault.account_id]
    if utils_is_force_override(posting_instructions=posting_instructions):
        return None
    posting_instruction: Union[
        InboundHardSettlement, OutboundHardSettlement, Transfer
    ] = posting_instructions[0]
    posting_amount = utils_balance_at_coordinates(
        balances=posting_instruction.balances(), denomination=denomination
    )
    if posting_amount < 0:
        repayment_targets = [loc_vault] + _get_loan_vaults_for_repayment_distribution(
            loan_vaults=loan_vaults, posting_instruction=posting_instruction
        )
        sorted_repayment_targets = supervisor_utils_sort_supervisees(supervisees=repayment_targets)
        (repayment_posting_directives, repayment_notification_directives) = _handle_repayment(
            hook_arguments=hook_arguments,
            sorted_repayment_targets=sorted_repayment_targets,
            loc_vault=loc_vault,
            denomination=denomination,
        )
        supervisee_posting_directives.update(repayment_posting_directives)
        account_notification_directives.update(repayment_notification_directives)
    return SupervisorPostPostingHookResult(
        supervisee_posting_instructions_directives=supervisee_posting_directives,
        supervisee_account_notification_directives=account_notification_directives,
    )


@requires(parameters=True, data_scope="all")
@fetch_account_data(
    balances={"line_of_credit": ["live_balances_bof"], "drawdown_loan": ["live_balances_bof"]}
)
def pre_posting_hook(
    vault: Any, hook_arguments: SupervisorPrePostingHookArguments
) -> Optional[SupervisorPrePostingHookResult]:
    (loc_vault, loan_vaults) = _get_loc_and_loan_supervisee_vault_objects(vault=vault)
    if loc_vault is None:
        return SupervisorPrePostingHookResult(
            rejection=Rejection(
                message=f"Cannot process postings until a supervisee with an alias {LOC_ALIAS} is associated to the plan",
                reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
            )
        )
    posting_instructions = hook_arguments.supervisee_posting_instructions[loc_vault.account_id]
    if utils_is_force_override(posting_instructions=posting_instructions):
        return None
    if supervisee_rejection := loc_vault.get_hook_result().rejection:
        return SupervisorPrePostingHookResult(rejection=supervisee_rejection)
    posting_instruction = posting_instructions[0]
    denomination = common_parameters_get_denomination_parameter(vault=loc_vault)
    posting_amount = utils_balance_at_coordinates(
        balances=posting_instruction.balances(), denomination=denomination
    )
    if posting_amount <= 0:
        loan_vaults_for_repayment_distribution = _get_loan_vaults_for_repayment_distribution(
            loan_vaults=loan_vaults, posting_instruction=posting_instruction
        )
        if loan_vaults and (not loan_vaults_for_repayment_distribution):
            return SupervisorPrePostingHookResult(
                rejection=Rejection(
                    message=f"The target account id {posting_instruction.instruction_details.get('target_account_id')} does not exist",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
        all_supervisee_balances = [
            vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
            for vault in [loc_vault, *loan_vaults_for_repayment_distribution]
        ]
        if repayment_rejection := _validate_repayment(
            loc_vault=loc_vault,
            all_supervisee_balances=all_supervisee_balances,
            repayment_amount=abs(posting_amount),
            denomination=denomination,
            rounding_precision=_get_application_precision_parameter(loan_vaults=loan_vaults),
        ):
            return SupervisorPrePostingHookResult(rejection=repayment_rejection)
    else:
        if rejection := maximum_outstanding_loans_validate(main_vault=loc_vault, loans=loan_vaults):
            return SupervisorPrePostingHookResult(rejection=rejection)
        if rejection := credit_limit_validate(
            main_vault=loc_vault,
            loans=loan_vaults,
            posting_instruction=posting_instruction,
            non_repayable_addresses=NON_REPAYABLE_ADDRESSES,
        ):
            return SupervisorPrePostingHookResult(rejection=rejection)
    return None


@requires(event_type="SUPERVISEE_SCHEDULE_SYNC", data_scope="all", parameters=True)
@requires(
    event_type="ACCRUE_INTEREST",
    data_scope="all",
    parameters=True,
    balances="1 days",
    last_execution_datetime=["DUE_AMOUNT_CALCULATION"],
    flags=True,
)
@requires(
    event_type="DUE_AMOUNT_CALCULATION",
    data_scope="all",
    parameters=True,
    balances="1 days",
    last_execution_datetime=["DUE_AMOUNT_CALCULATION"],
    flags=True,
)
@requires(event_type="CHECK_OVERDUE", data_scope="all", parameters=True, balances="1 days")
@requires(event_type="CHECK_DELINQUENCY", data_scope="all", parameters=True, balances="1 days")
def scheduled_event_hook(
    vault: Any, hook_arguments: SupervisorScheduledEventHookArguments
) -> Optional[SupervisorScheduledEventHookResult]:
    event_type = hook_arguments.event_type
    supervisee_pi_directives: dict[str, list[PostingInstructionsDirective]] = {}
    update_plan_event_type_directives: list[UpdatePlanEventTypeDirective] = []
    update_account_event_type_directives: dict[str, list[UpdateAccountEventTypeDirective]] = {}
    supervisee_notification_directives: dict[str, list[AccountNotificationDirective]] = {}
    (loc_vault, loan_vaults) = _get_loc_and_loan_supervisee_vault_objects(vault=vault)
    if event_type == supervisor_utils_SUPERVISEE_SCHEDULE_SYNC_EVENT:
        update_plan_event_type_directives = supervisor_utils_get_supervisee_schedule_sync_updates(
            vault=vault,
            supervisee_alias=LOC_ALIAS,
            hook_arguments=hook_arguments,
            schedule_updates_when_supervisees=_schedule_updates_when_supervisees,
        )
    elif loc_vault and event_type == interest_accrual_supervisor_ACCRUAL_EVENT:
        if not repayment_holiday_is_interest_accrual_blocked(
            vault=loc_vault, effective_datetime=hook_arguments.effective_datetime
        ):
            supervisee_pi_directives.update(
                _handle_accrue_interest(
                    vault=vault,
                    hook_arguments=hook_arguments,
                    loc_vault=loc_vault,
                    loan_vaults=loan_vaults,
                )
            )
        (
            update_plan_event_type_directives,
            update_account_event_type_directives,
        ) = _handle_due_amount_calculation_day_change(
            loc_vault=loc_vault, hook_arguments=hook_arguments
        )
    elif loc_vault and event_type == due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT:
        if repayment_holiday_is_due_amount_calculation_blocked(
            vault=loc_vault, effective_datetime=hook_arguments.effective_datetime
        ):
            supervisee_pi_directives.update(
                _update_due_amount_calculation_counters(
                    loan_vaults=loan_vaults,
                    hook_arguments=hook_arguments,
                    denomination=common_parameters_get_denomination_parameter(vault=loc_vault),
                )
            )
        else:
            (
                due_amount_custom_instructions,
                repayment_amount,
            ) = _get_due_amount_custom_instructions(
                hook_arguments=hook_arguments, loc_vault=loc_vault, loan_vaults=loan_vaults
            )
            supervisee_pi_directives.update(due_amount_custom_instructions)
            supervisee_notification_directives.update(
                _get_repayment_due_notification(
                    loc_vault=loc_vault,
                    repayment_amount=repayment_amount,
                    hook_arguments=hook_arguments,
                )
            )
            update_plan_event_type_directives = _update_check_overdue_schedule(
                loc_vault=loc_vault, hook_arguments=hook_arguments
            )
        due_amount_calculation_day = _get_due_amount_calculation_day_parameter(loc_vault=loc_vault)
        if due_amount_calculation_day != hook_arguments.effective_datetime.day:
            schedule_start_datetime = hook_arguments.effective_datetime + relativedelta(
                months=1, day=due_amount_calculation_day
            )
            (
                due_calc_update_event_type_directives,
                update_account_event_type_directives,
            ) = _update_due_amount_calculation_day_schedule(
                loc_vault=loc_vault,
                schedule_start_datetime=schedule_start_datetime,
                due_amount_calculation_day=due_amount_calculation_day,
            )
            update_plan_event_type_directives += due_calc_update_event_type_directives
    elif loc_vault and event_type == overdue_CHECK_OVERDUE_EVENT:
        if not repayment_holiday_is_overdue_amount_calculation_blocked(
            vault=loc_vault, effective_datetime=hook_arguments.effective_datetime
        ):
            overdue_custom_instructions = _get_overdue_custom_instructions(
                hook_arguments=hook_arguments, loc_vault=loc_vault, loan_vaults=loan_vaults
            )
            (
                overdue_principal_amount,
                overdue_interest_amount,
            ) = _get_overdue_amounts_from_instructions(
                loc_account_id=loc_vault.account_id,
                instructions_directives=overdue_custom_instructions,
                denomination=common_parameters_get_denomination_parameter(vault=loc_vault),
            )
            grace_period = delinquency_get_grace_period_parameter(vault=loc_vault)
            if overdue_principal_amount or overdue_interest_amount:
                supervisee_pi_directives.update(overdue_custom_instructions)
                supervisee_notification_directives[
                    loc_vault.account_id
                ] = overdue_get_overdue_repayment_notification(
                    account_id=loc_vault.account_id,
                    product_name=LOC_ACCOUNT_TYPE,
                    effective_datetime=hook_arguments.effective_datetime,
                    overdue_principal_amount=overdue_principal_amount,
                    overdue_interest_amount=overdue_interest_amount,
                    late_repayment_fee=late_repayment_get_late_repayment_fee_parameter(
                        vault=loc_vault
                    ),
                )
                if grace_period == 0:
                    supervisee_notification_directives[
                        loc_vault.account_id
                    ] += _get_delinquency_notification(account_id=loc_vault.account_id)
            skip_delinquency = (
                overdue_principal_amount <= Decimal("0")
                and overdue_interest_amount <= Decimal("0")
                or grace_period == 0
            )
            update_plan_event_type_directives = _update_check_delinquency_schedule(
                loc_vault=loc_vault,
                hook_arguments=hook_arguments,
                grace_period=grace_period,
                skip=skip_delinquency,
            )
        update_plan_event_type_directives += _update_check_overdue_schedule(
            loc_vault=loc_vault, hook_arguments=hook_arguments, skip=True
        )
    elif loc_vault and event_type == delinquency_CHECK_DELINQUENCY_EVENT:
        if not repayment_holiday_is_delinquency_blocked(
            vault=loc_vault, effective_datetime=hook_arguments.effective_datetime
        ):
            supervisee_notification_directives.update(
                _handle_delinquency(
                    hook_arguments=hook_arguments, loc_vault=loc_vault, loan_vaults=loan_vaults
                )
            )
        update_plan_event_type_directives = _update_check_delinquency_schedule(
            loc_vault=loc_vault,
            hook_arguments=hook_arguments,
            grace_period=delinquency_get_grace_period_parameter(vault=loc_vault),
            skip=True,
        )
    if (
        update_plan_event_type_directives
        or supervisee_pi_directives
        or supervisee_notification_directives
        or update_account_event_type_directives
    ):
        return SupervisorScheduledEventHookResult(
            supervisee_posting_instructions_directives=supervisee_pi_directives,
            update_plan_event_type_directives=update_plan_event_type_directives,
            supervisee_account_notification_directives=supervisee_notification_directives,
            supervisee_update_account_event_type_directives=update_account_event_type_directives,
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
utils_VALID_DAYS_IN_YEAR = ["360", "365", "366", "actual"]
utils_DEFAULT_DAYS_IN_YEAR = "actual"
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


def utils_yearly_to_monthly_rate(yearly_rate: Decimal) -> Decimal:
    return utils_round_decimal(yearly_rate / 12, decimal_places=utils_RATE_DECIMAL_PLACES)


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


def utils_reset_tracker_balances(
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
        address_balance = utils_balance_at_coordinates(
            balances=balances, address=address, denomination=denomination
        )
        if address_balance > Decimal("0"):
            postings += utils_create_postings(
                amount=address_balance,
                debit_account=account_id,
                credit_account=account_id,
                debit_address=contra_address if tside == Tside.ASSET else address,
                credit_address=address if tside == Tside.ASSET else contra_address,
                denomination=denomination,
            )
    return postings


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


def utils_get_balance_default_dict_from_mapping(
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
        coord: ts.at(at_datetime=effective_datetime) if effective_datetime else ts.latest()
        for (coord, ts) in mapping.items()
    }
    return BalanceDefaultDict(mapping=balance_mapping)


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


# Objects below have been imported from:
#    common_parameters.py
# md5:11b3b3b4a92b1dc6ec77a2405fb2ca6d

common_parameters_PARAM_DENOMINATION = "denomination"


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
fetchers_LIVE_BALANCES_BOF_ID = "live_balances_bof"
fetchers_LIVE_BALANCES_BOF = BalancesObservationFetcher(
    fetcher_id=fetchers_LIVE_BALANCES_BOF_ID, at=DefinedDateTime.LIVE
)

# Objects below have been imported from:
#    accruals.py
# md5:becbe7f07a49ad9560c9d05985a2e3ab

accruals_AccrualDetail = NamedTuple("AccrualDetail", [("amount", Decimal), ("description", str)])


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
interest_accrual_common_ACCRUED_INTEREST_RECEIVABLE = "ACCRUED_INTEREST_RECEIVABLE"
interest_accrual_common_PARAM_DAYS_IN_YEAR = "days_in_year"
interest_accrual_common_PARAM_ACCRUAL_PRECISION = "accrual_precision"
interest_accrual_common_INTEREST_ACCRUAL_PREFIX = "interest_accrual"


def interest_accrual_common_daily_accrual(
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
    event_type: str = interest_accrual_common_ACCRUAL_EVENT,
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
    accrual_detail = interest_accrual_common_calculate_daily_accrual(
        effective_balance=effective_balance,
        effective_datetime=effective_datetime,
        yearly_rate=yearly_rate,
        days_in_year=days_in_year,
        rounding=rounding,
        precision=precision,
    )
    if accrual_detail is None:
        return []
    return accruals_accrual_custom_instruction(
        customer_account=customer_account,
        customer_address=customer_address,
        denomination=denomination,
        amount=accrual_detail.amount,
        internal_account=internal_account,
        payable=payable,
        instruction_details=utils_standard_instruction_details(
            description=accrual_detail.description,
            event_type=event_type,
            gl_impacted=True,
            account_type=account_type,
        ),
    )


def interest_accrual_common_calculate_daily_accrual(
    effective_balance: Decimal,
    effective_datetime: datetime,
    yearly_rate: Decimal,
    days_in_year: str,
    rounding: str = ROUND_HALF_UP,
    precision: int = 5,
) -> Optional[accruals_AccrualDetail]:
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
    daily_rate = utils_yearly_to_daily_rate(
        days_in_year=days_in_year, yearly_rate=yearly_rate, effective_date=effective_datetime
    )
    accrual_amount = utils_round_decimal(
        amount=effective_balance * daily_rate, decimal_places=precision, rounding=rounding
    )
    if accrual_amount == 0:
        return None
    return accruals_AccrualDetail(
        amount=accrual_amount,
        description=f"Daily interest accrued at {daily_rate * 100:0.5f}% on balance of {effective_balance:0.2f}",
    )


# Objects below have been imported from:
#    addresses.py
# md5:860f50af37f2fe98540f540fa6394eb7

addresses_INTERNAL_CONTRA = "INTERNAL_CONTRA"
addresses_PENALTIES = "PENALTIES"

# Objects below have been imported from:
#    supervisor_utils.py
# md5:badd574e398fc715274627e947d1a001

supervisor_utils_SUPERVISEE_SCHEDULE_SYNC_EVENT = "SUPERVISEE_SCHEDULE_SYNC"


def supervisor_utils_schedule_sync_event_types(
    product_name: str,
) -> list[SupervisorContractEventType]:
    return [
        SupervisorContractEventType(
            name=supervisor_utils_SUPERVISEE_SCHEDULE_SYNC_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{supervisor_utils_SUPERVISEE_SCHEDULE_SYNC_EVENT}_AST"
            ],
        )
    ]


def supervisor_utils_get_supervisees_for_alias(vault: Any, alias: str) -> list[Any]:
    """
    Returns a list of supervisee vault objects for the given alias, ordered by account creation date
    TODO: (INC-8671) reintroduce num_requested logic from v3

    :param vault: supervisor vault object
    :param alias: the supervisee alias to filter for
    :return: supervisee vault objects for given alias, ordered by account creation date

    """
    return supervisor_utils_sort_supervisees(
        [supervisee for supervisee in vault.supervisees.values() if supervisee.get_alias() == alias]
    )


def supervisor_utils_sort_supervisees(supervisees: list[Any]) -> list[Any]:
    """
    Sorts supervisees first by creation date, and then alphabetically by id if
    numerous supervisees share the same creation date and creates a list of ordered
    vault objects.

    :param supervisees: list of supervisee vault objects
    :return sorted_supervisees: list of ordered vault objects
    """
    sorted_supervisees_by_id = sorted(supervisees, key=lambda vault: vault.account_id)
    sorted_supervisees_by_age_then_id = sorted(
        sorted_supervisees_by_id, key=lambda vault: vault.get_account_creation_datetime()
    )
    return sorted_supervisees_by_age_then_id


def supervisor_utils_get_balance_default_dicts_for_supervisees(
    supervisees: list[Any], fetcher_id: str
) -> list[BalanceDefaultDict]:
    """
    Returns a list of the supervisee balances at the datetime defined in a fetcher
    :param supervisees: the vault objects to get balances observations from
    :param fetcher_id: the id of the fetcher used to get balances observations
    :return: the list of balances of the specified supervisees
    """
    return [
        supervisee.get_balances_observation(fetcher_id=fetcher_id).balances
        for supervisee in supervisees
    ]


def supervisor_utils_get_balances_default_dicts_from_timeseries(
    supervisees: list[Any], effective_datetime: datetime
) -> dict[str, BalanceDefaultDict]:
    """
    Returns supervisee balances at the provided datetime, using balances timeseries.
    This is intended to be used where a fetcher cannot be used (e.g. post posting hook).
    :param supervisees: the vault objects to get balances timeseries from
    :param effective_datetime: the datetime at which the balances should be retrieved
    :return: a dictionary that maps the supervisees account ID to the retrieved balances
    """
    return {
        supervisee.account_id: utils_get_balance_default_dict_from_mapping(
            mapping=supervisee.get_balances_timeseries(), effective_datetime=effective_datetime
        )
        for supervisee in supervisees
    }


def supervisor_utils_sum_balances_across_supervisees(
    balances: list[BalanceDefaultDict],
    denomination: str,
    addresses: list[str],
    rounding_precision: int = 2,
) -> Decimal:
    """
    Sums the net balance values for the addresses across multiple vault objects,
    rounding the balance sum at a per-vault level. Default asset and phase are used.
    :param balances: the list of balances to sum
    :param denomination: the denomination of the balances
    :param addresses: the addresses of the balances
    :param rounding_precision: the precision to which each balance is individually rounded
    :return: the sum of balances across the specified supervisees
    """
    return Decimal(
        sum(
            (
                utils_round_decimal(
                    utils_sum_balances(
                        balances=balance, addresses=addresses, denomination=denomination
                    ),
                    rounding_precision,
                )
                for balance in balances
            )
        )
    )


def supervisor_utils_create_aggregate_posting_instructions(
    aggregate_account_id: str,
    posting_instructions_by_supervisee: dict[str, list[CustomInstruction]],
    prefix: str,
    balances: BalanceDefaultDict,
    addresses_to_aggregate: list[str],
    tside: Tside = Tside.ASSET,
    force_override: bool = True,
    rounding_precision: int = 2,
) -> list[CustomInstruction]:
    """
    Used for supervisor contracts to aggregate multiple posting instructions that arise
    from supervisee accounts. This util is helpful when you have a "main" supervisee
    account that is responsible for holding aggregate balances (i.e. an account where
    aggregate postings are made).

    Any postings targeting the same balance address name will be aggregated. e.g. If supervisee 1
    and supervisee 2 both have postings to address PRINCIPAL_DUE, the aggregate value of these will
    be calculated into a new posting instruction of length 1 to a balance address:
    <prefix>_<balance_address> (e.g. TOTAL_PRINCIPAL_DUE).

    :param aggregate_account_id: The account id of the vault object where the aggregate postings
    are made (i.e. the "main" account)
    :param posting_instructions_by_supervisee: A mapping of supervisee account id to posting
    instructions to derive the aggregate posting instructions from
    :param prefix: The prefix of the aggregated balances
    :param balances: The balances of the account where the aggregate postings are made (i.e. the
    "main" account). Typically these are the latest balances for the account, but in theory any
    balances can be passed in.
    :param addresses_to_aggregate: A list of addresses to get aggregate postings for
    :param tside: The Tside of the account
    :param force_override: boolean to pass into instruction details to force override hooks
    :param rounding_precision: The rounding precision to correct for
    :return: The aggregated custom instructions
    """
    aggregate_balances = BalanceDefaultDict()
    for (supervisee_account_id, posting_instructions) in posting_instructions_by_supervisee.items():
        for posting_instruction in posting_instructions:
            aggregate_balances += posting_instruction.balances(
                account_id=supervisee_account_id, tside=tside
            )
    filtered_aggregate_balances = supervisor_utils_filter_aggregate_balances(
        aggregate_balances=aggregate_balances,
        balances=balances,
        addresses_to_aggregate=addresses_to_aggregate,
        rounding_precision=rounding_precision,
    )
    aggregate_postings: list[Posting] = []
    for (balance_coordinate, balance) in filtered_aggregate_balances.items():
        amount: Decimal = balance.net
        prefixed_address = f"{prefix}_{balance_coordinate.account_address}"
        debit_address = (
            prefixed_address
            if tside == Tside.ASSET
            and amount > Decimal("0")
            or (tside == Tside.LIABILITY and amount < Decimal("0"))
            else addresses_INTERNAL_CONTRA
        )
        credit_address = (
            prefixed_address
            if tside == Tside.ASSET
            and amount < Decimal("0")
            or (tside == Tside.LIABILITY and amount > Decimal("0"))
            else addresses_INTERNAL_CONTRA
        )
        aggregate_postings += utils_create_postings(
            amount=abs(amount),
            debit_account=aggregate_account_id,
            credit_account=aggregate_account_id,
            debit_address=debit_address,
            credit_address=credit_address,
            denomination=balance_coordinate.denomination,
            asset=balance_coordinate.asset,
        )
    aggregate_posting_instructions: list[CustomInstruction] = []
    if aggregate_postings:
        aggregate_posting_instructions.append(
            CustomInstruction(
                postings=aggregate_postings,
                instruction_details={"force_override": str(force_override).lower()},
            )
        )
    return aggregate_posting_instructions


def supervisor_utils_filter_aggregate_balances(
    aggregate_balances: BalanceDefaultDict,
    balances: BalanceDefaultDict,
    addresses_to_aggregate: list[str],
    rounding_precision: int = 2,
) -> BalanceDefaultDict:
    """
    Removes aggregate balances that would cause discrepancies between the supervisor
    and the supervisee(s) due to rounding errors.
    Only aggregates given addresses to avoid unnecessary aggregations (e.g. INTERNAL_CONTRA)

    For instance, assume the rounding precision is 2. If account 1 has a balance A with a current
    value of 0.123 and the aggregate amount is 0.001, no aggregate posting needs to be created as
    the rounded absolute amount is unchanged (round(0.123, 2) == round(0.124, 2)). If account 1 has
    a balance A with a current value of 0.123 and there is a posting to increase this by 0.002,
    an aggregate posting is needed as the rounded absolute amount has changed from 0.12 to 0.13.

    Normally this filtering only needs to be applied to the accrued interest balance address,
    but we simply check all addresses being aggregated to guard against this edge case.

    This util is mainly for use in the create_aggregate_posting_instructions util, but in theory
    it could be used independently.

    :param aggregate_balances: The aggregate balances to filter
    :param balances: The balances of the account where the aggregate postings are made (i.e. the
    "main" account). Typically these are the latest balances for the account, but in theory any
    balances can be passed in.
    :param addresses_to_aggregate: A list of addresses to aggregate balances for
    :param rounding_precision: The rounding precision to correct for
    :return: A filtered dict of aggregated balances
    """
    filtered_aggregate_balance_mapping = aggregate_balances.copy()
    new_balance_mapping = aggregate_balances + balances
    for balance_coordinate in aggregate_balances:
        if balance_coordinate.account_address in addresses_to_aggregate:
            current_amount = balances[balance_coordinate].net
            new_amount = new_balance_mapping[balance_coordinate].net
            if utils_round_decimal(
                amount=new_amount, decimal_places=rounding_precision
            ) == utils_round_decimal(amount=current_amount, decimal_places=rounding_precision):
                del filtered_aggregate_balance_mapping[balance_coordinate]
        else:
            del filtered_aggregate_balance_mapping[balance_coordinate]
    return filtered_aggregate_balance_mapping


def supervisor_utils_supervisee_schedule_sync_scheduled_event(
    vault: Any, delay_seconds: int = 30
) -> dict[str, ScheduledEvent]:
    """
    Return a one-off event for synchronising schedules in a supervisor from a supervisee
    schedule, to be run after plan opening date based on the delay seconds.
    The delay seconds needs to allow for plan activation to complete after opening, as well as
    adequate time for supervisee accounts to be added to the plan.
    """
    plan_opening_datetime = vault.get_plan_opening_datetime()
    first_schedule_date = plan_opening_datetime + relativedelta(seconds=delay_seconds)
    return {
        supervisor_utils_SUPERVISEE_SCHEDULE_SYNC_EVENT: ScheduledEvent(
            start_datetime=plan_opening_datetime,
            expression=utils_one_off_schedule_expression(first_schedule_date),
        )
    }


def supervisor_utils_get_supervisee_schedule_sync_updates(
    vault: Any,
    supervisee_alias: str,
    hook_arguments: SupervisorScheduledEventHookArguments,
    schedule_updates_when_supervisees: Callable[
        [Any, SupervisorScheduledEventHookArguments], list[UpdatePlanEventTypeDirective]
    ],
    delay_seconds: int = 60,
) -> list[UpdatePlanEventTypeDirective]:
    """
    Get schedule updates needed when synchronising schedules with supervisee schedules based on
    their parameters. If the SUPERVISEE_SCHEDULE_SYNC_EVENT runs on a plan with no associated
    supervisee accounts we reschedule to run this event again after the delay seconds have elapsed.

    :param vault: supervisor vault object
    :param supervisee_alias: the supervisee product alias that must be associated to the plan
    :param hook_arguments: the scheduled event's hook arguments
    :param schedule_updates_when_supervisees: a function to get the required schedule updates, given
    the Vault object of the supervisee
    :param delay_seconds: the number of seconds to delay before rerunning the supervisee schedule
    sync event
    :return: the required schedule updates
    """
    supervisee_vaults = supervisor_utils_get_supervisees_for_alias(
        vault=vault, alias=supervisee_alias
    )
    if supervisee_vaults:
        return schedule_updates_when_supervisees(supervisee_vaults[0], hook_arguments)
    else:
        return [
            UpdatePlanEventTypeDirective(
                event_type=supervisor_utils_SUPERVISEE_SCHEDULE_SYNC_EVENT,
                expression=utils_one_off_schedule_expression(
                    schedule_datetime=hook_arguments.effective_datetime
                    + relativedelta(seconds=delay_seconds)
                ),
            )
        ]


# Objects below have been imported from:
#    lending_addresses.py
# md5:d546448643732336308da8f52c0901d4

lending_addresses_ACCRUED_INTEREST_RECEIVABLE = "ACCRUED_INTEREST_RECEIVABLE"
lending_addresses_DUE_CALCULATION_EVENT_COUNTER = "DUE_CALCULATION_EVENT_COUNTER"
lending_addresses_EMI = "EMI"
lending_addresses_INTERNAL_CONTRA = addresses_INTERNAL_CONTRA
lending_addresses_INTEREST_DUE = "INTEREST_DUE"
lending_addresses_INTEREST_OVERDUE = "INTEREST_OVERDUE"
lending_addresses_NON_EMI_ACCRUED_INTEREST_RECEIVABLE = "NON_EMI_ACCRUED_INTEREST_RECEIVABLE"
lending_addresses_PENALTIES = addresses_PENALTIES
lending_addresses_PRINCIPAL = "PRINCIPAL"
lending_addresses_PRINCIPAL_DUE = "PRINCIPAL_DUE"
lending_addresses_PRINCIPAL_OVERDUE = "PRINCIPAL_OVERDUE"
lending_addresses_ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION = (
    "ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION"
)
lending_addresses_DUE_ADDRESSES = [lending_addresses_PRINCIPAL_DUE, lending_addresses_INTEREST_DUE]
lending_addresses_OVERDUE_ADDRESSES = [
    lending_addresses_PRINCIPAL_OVERDUE,
    lending_addresses_INTEREST_OVERDUE,
]
lending_addresses_LATE_REPAYMENT_ADDRESSES = lending_addresses_OVERDUE_ADDRESSES + [
    lending_addresses_PENALTIES
]
lending_addresses_REPAYMENT_HIERARCHY = (
    lending_addresses_LATE_REPAYMENT_ADDRESSES + lending_addresses_DUE_ADDRESSES
)
lending_addresses_OVERPAYMENT_HIERARCHY_SUPERVISOR = [
    [
        lending_addresses_PRINCIPAL,
        lending_addresses_ACCRUED_INTEREST_RECEIVABLE,
        lending_addresses_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
    ]
]
lending_addresses_DEBT_ADDRESSES = lending_addresses_REPAYMENT_HIERARCHY + [
    lending_addresses_PRINCIPAL
]
lending_addresses_ALL_OUTSTANDING = [
    *lending_addresses_DEBT_ADDRESSES,
    lending_addresses_ACCRUED_INTEREST_RECEIVABLE,
    lending_addresses_ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
]
lending_addresses_ALL_OUTSTANDING_SUPERVISOR = lending_addresses_ALL_OUTSTANDING + [
    lending_addresses_NON_EMI_ACCRUED_INTEREST_RECEIVABLE
]
lending_addresses_ALL_PRINCIPAL = (
    [lending_addresses_PRINCIPAL]
    + [lending_addresses_PRINCIPAL_DUE]
    + [lending_addresses_PRINCIPAL_OVERDUE]
)

# Objects below have been imported from:
#    lending_interfaces.py
# md5:a0df1ba0adcd14fa7f99308269ad58a7

lending_interfaces_EarlyRepaymentFee = NamedTuple(
    "EarlyRepaymentFee",
    [
        ("get_early_repayment_fee_amount", Callable[..., Decimal]),
        ("charge_early_repayment_fee", Callable[..., list[CustomInstruction]]),
        ("fee_name", str),
    ],
)
lending_interfaces_InterestAmounts = NamedTuple(
    "InterestAmounts",
    [
        ("emi_rounded_accrued", Decimal),
        ("emi_accrued", Decimal),
        ("non_emi_rounded_accrued", Decimal),
        ("non_emi_accrued", Decimal),
        ("total_rounded", Decimal),
    ],
)
lending_interfaces_InterestApplication = NamedTuple(
    "InterestApplication",
    [
        ("apply_interest", Callable[..., list[Posting]]),
        ("get_interest_to_apply", Callable[..., lending_interfaces_InterestAmounts]),
        ("get_application_precision", Callable[..., int]),
    ],
)
lending_interfaces_InterestRate = NamedTuple(
    "InterestRate",
    [
        ("get_daily_interest_rate", Callable[..., Decimal]),
        ("get_monthly_interest_rate", Callable[..., Decimal]),
        ("get_annual_interest_rate", Callable[..., Decimal]),
    ],
)
lending_interfaces_MultiTargetOverpayment = NamedTuple(
    "MultiTargetOverpayment", [("handle_overpayment", Callable[..., dict[str, list[Posting]]])]
)
lending_interfaces_SupervisorPrincipalAdjustment = NamedTuple(
    "SupervisorPrincipalAdjustment", [("calculate_principal_adjustment", Callable[..., Decimal])]
)
lending_interfaces_SupervisorAmortisation = NamedTuple(
    "SupervisorAmortisation",
    [
        ("calculate_emi", Callable[..., Decimal]),
        ("term_details", Callable[..., tuple[int, int]]),
        ("override_final_event", bool),
    ],
)
lending_interfaces_SupervisorReamortisationCondition = NamedTuple(
    "SupervisorReamortisationCondition", [("should_trigger_reamortisation", Callable[..., bool])]
)

# Objects below have been imported from:
#    lending_parameters.py
# md5:7faccb9f85f49b8f7dea97327cbece56

lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT = "total_repayment_count"

# Objects below have been imported from:
#    term_helpers.py
# md5:daf4d2c8e08d1b80a139d4905726ffff


def term_helpers_calculate_elapsed_term(balances: BalanceDefaultDict, denomination: str) -> int:
    return int(
        utils_balance_at_coordinates(
            balances=balances,
            address=lending_addresses_DUE_CALCULATION_EVENT_COUNTER,
            denomination=denomination,
        )
    )


# Objects below have been imported from:
#    declining_principal.py
# md5:9a0b5e3b9bdf8a8ca9b57a0a01a29e54


def declining_principal_supervisor_term_details(
    loan_vault: Any,
    main_vault: Any,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    interest_rate: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_SupervisorPrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> tuple[int, int]:
    """Calculate the elapsed and remaining term for a loan when using a supervisor

    :param loan_vault: the supervisee vault object for the loan account
    :param main_vault: the supervisee vault object that principal adjustments are associated with
    :param effective_datetime: datetime as of which the calculations are performed
    :param use_expected_term: if True, the remaining term is purely based on original and
        elapsed term, ignoring any adjustments etc. If false, it is calculated based on
        principal, interest rate and emi
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the principal set on parameter level is used.
    :param interest_rate: interest rate feature, if no value is provided, 0 is used.
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param balances: balances to use instead of the effective datetime balances
    :param denomination: denomination to use instead of the effective datetime parameter value
    :return: the elapsed and remaining term
    """
    original_total_term = int(
        utils_get_parameter(vault=loan_vault, name=lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT)
    )
    if effective_datetime == loan_vault.get_account_creation_datetime():
        return (0, original_total_term)
    if balances is None:
        balances = loan_vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = utils_get_parameter(vault=loan_vault, name="denomination")
    principal_balance = utils_balance_at_coordinates(
        balances=balances, address=lending_addresses_PRINCIPAL, denomination=denomination
    )
    elapsed = term_helpers_calculate_elapsed_term(balances=balances, denomination=denomination)
    expected_remaining_term = (
        original_total_term - elapsed if principal_balance > Decimal("0") else 0
    )
    if use_expected_term:
        return (elapsed, expected_remaining_term)
    emi = utils_balance_at_coordinates(
        balances=balances, address=lending_addresses_EMI, denomination=denomination
    )
    if emi == 0:
        return (elapsed, expected_remaining_term)
    monthly_interest_rate = (
        interest_rate.get_monthly_interest_rate(
            vault=loan_vault,
            effective_datetime=effective_datetime,
            balances=balances,
            denomination=denomination,
        )
        if interest_rate is not None
        else Decimal(0)
    )
    adjusted_principal = principal_balance + Decimal(
        sum(
            (
                adjustment.calculate_principal_adjustment(
                    main_vault=main_vault,
                    loan_vault=loan_vault,
                    balances=balances,
                    denomination=denomination,
                )
                for adjustment in principal_adjustments or []
            )
        )
    )
    remaining = declining_principal_calculate_remaining_term(
        emi=emi, remaining_principal=adjusted_principal, monthly_interest_rate=monthly_interest_rate
    )
    remaining = min(remaining, expected_remaining_term)
    return (elapsed, remaining)


def declining_principal_calculate_remaining_term(
    emi: Decimal,
    remaining_principal: Decimal,
    monthly_interest_rate: Decimal,
    decimal_places: int = 2,
    rounding: str = ROUND_HALF_UP,
) -> int:
    """
    The remaining term calculated using the amortisation formula
    math.log((EMI/(EMI - P*R)), (1+R)), where:

    EMI is the equated monthly instalment
    P is the remaining principal
    R is the monthly interest rate

    Note that, when the monthly interest rate R is 0, the remaining term
    is calculated using P / EMI. When the EMI is 0, this function will
    return 0.

    The term is rounded using specified arguments and then ceil'd to ensure that partial
    terms are treated as a full term (e.g. rounded remaining term as 16.4 results in 17)

    :param emi: The equated monthly instalment
    :param remaining_principal: The remaining principal
    :param monthly_interest_rate: The monthly interest rate
    :param decimal_places: The number of decimal places to round to
    :param rounding: The type of rounding strategy to use
    :return: The remaining term left on the loan
    """
    if emi == Decimal("0"):
        return 0
    remaining_term = (
        Decimal(
            math.log(
                emi / (emi - remaining_principal * monthly_interest_rate), 1 + monthly_interest_rate
            )
        )
        if monthly_interest_rate > Decimal("0")
        else remaining_principal / emi
    )
    return int(
        utils_round_decimal(
            amount=remaining_term, decimal_places=decimal_places, rounding=rounding
        ).to_integral_exact(rounding=ROUND_CEILING)
    )


def declining_principal_supervisor_calculate_emi(
    loan_vault: Any,
    main_vault: Any,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_SupervisorPrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> Decimal:
    """
    Extracts relevant data required and calculates declining principal EMI. Intended to be used
    with the supervisor due amount calculation feature
    :param loan_vault: vault object for which EMI must be calculated
    :param main_vault: the supervisee vault object that principal adjustments are associated with
    :param effective_datetime: the datetime as of which the calculation is performed
    :param use_expected_term: if True, the remaining term is purely based on original and
        elapsed term, ignoring any adjustments etc. If false, it is calculated based on
        principal, interest rate and emi
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the principal set on parameter level is used.
    :param interest_calculation_feature: interest calculation feature, if no value is
        provided, 0 is used.
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param balances: balances to use instead of the effective datetime balances
    :return: emi amount
    """
    (principal, interest_rate) = declining_principal__get_declining_principal_formula_terms(
        vault=loan_vault,
        effective_datetime=effective_datetime,
        principal_amount=principal_amount,
        interest_calculation_feature=interest_calculation_feature,
    )
    (_, remaining_term) = declining_principal_supervisor_term_details(
        loan_vault=loan_vault,
        main_vault=main_vault,
        effective_datetime=effective_datetime,
        use_expected_term=use_expected_term,
        interest_rate=interest_calculation_feature,
        principal_adjustments=principal_adjustments,
        balances=balances,
    )
    if principal_adjustments:
        denomination: str = utils_get_parameter(vault=main_vault, name="denomination")
        principal += Decimal(
            sum(
                (
                    adjustment.calculate_principal_adjustment(
                        loan_vault=loan_vault,
                        main_vault=main_vault,
                        balances=balances,
                        denomination=denomination,
                    )
                    for adjustment in principal_adjustments
                )
            )
        )
    return declining_principal_apply_declining_principal_formula(
        remaining_principal=principal, interest_rate=interest_rate, remaining_term=remaining_term
    )


def declining_principal_apply_declining_principal_formula(
    remaining_principal: Decimal,
    interest_rate: Decimal,
    remaining_term: int,
    fulfillment_precision: int = 2,
    lump_sum_amount: Optional[Decimal] = None,
) -> Decimal:
    """
    Calculates the EMI according to the following formula:
    EMI = (P-(L/(1+R)^(N)))*R*(((1+R)^N)/((1+R)^N-1))
    P is principal remaining
    R is the interest rate, which should match the term unit (i.e. monthly rate if
    remaining term is also in months)
    N is term remaining
    L is the lump sum
    Formula can be used for a standard declining principal loan or a
    minimum repayment loan which includes a lump_sum_amount to be paid at the
    end of the term that is > 0.
    When the lump sum amount L is 0, the formula is reduced to:
    EMI = [P x R x (1+R)^N]/[(1+R)^N-1]
    :param remaining_principal: principal remaining
    :param interest_rate: interest rate appropriate for the term unit
    :param remaining_term: the number of integer term units remaining
    :param fulfillment_precision: precision needed for interest fulfillment
    :param lump_sum_amount: an optional one-off repayment amount
    :return: emi amount
    """
    lump_sum_amount = lump_sum_amount or Decimal("0")
    if remaining_term <= Decimal("0"):
        return remaining_principal
    elif interest_rate == Decimal("0"):
        return utils_round_decimal(remaining_principal / remaining_term, fulfillment_precision)
    else:
        return utils_round_decimal(
            (remaining_principal - lump_sum_amount / (1 + interest_rate) ** remaining_term)
            * interest_rate
            * (1 + interest_rate) ** remaining_term
            / ((1 + interest_rate) ** remaining_term - 1),
            fulfillment_precision,
        )


def declining_principal__get_declining_principal_formula_terms(
    vault: Union[Any, Any],
    effective_datetime: datetime,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces_InterestRate] = None,
) -> tuple[Decimal, Decimal]:
    principal = (
        utils_get_parameter(vault=vault, name="principal")
        if principal_amount is None
        else principal_amount
    )
    interest_rate = (
        Decimal(0)
        if not interest_calculation_feature
        else interest_calculation_feature.get_monthly_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )
    )
    return (principal, interest_rate)


declining_principal_SupervisorAmortisationFeature = lending_interfaces_SupervisorAmortisation(
    calculate_emi=declining_principal_supervisor_calculate_emi,
    term_details=declining_principal_supervisor_term_details,
    override_final_event=False,
)

# Objects below have been imported from:
#    close_loan.py
# md5:7b4a8d8a8438235415310d37d216ac7f

close_loan_DUE_ADDRESSES = [lending_addresses_PRINCIPAL_DUE, lending_addresses_INTEREST_DUE]
close_loan_OVERDUE_ADDRESSES = [
    lending_addresses_PRINCIPAL_OVERDUE,
    lending_addresses_INTEREST_OVERDUE,
]
close_loan_PENALTIES_ADDRESSES = [lending_addresses_PENALTIES]
close_loan_PRINCIPAL_ADDRESSES = [lending_addresses_PRINCIPAL]
close_loan_PAYMENT_ADDRESSES = (
    close_loan_OVERDUE_ADDRESSES + close_loan_PENALTIES_ADDRESSES + close_loan_DUE_ADDRESSES
)
close_loan_DEBT_ADDRESSES = close_loan_PAYMENT_ADDRESSES + close_loan_PRINCIPAL_ADDRESSES


def close_loan_does_repayment_fully_repay_loan(
    repayment_posting_instructions: list[CustomInstruction],
    balances: BalanceDefaultDict,
    denomination: str,
    account_id: str,
    debt_addresses: Optional[list[str]] = None,
    payment_addresses: Optional[list[str]] = None,
) -> bool:
    """
    Determines whether the repayment posting instructions fully repay the outstanding debt
    on the loan

    :param repayment_posting_instructions: The repayment posting instructions
    :param balances: The current balances used to check the outstanding debt
    :param denomination: The denomination of the account and the repayment
    :param account_id: The id of the account the repayment is for
    :param debt_addresses: The balance addresses that hold the debt for the account
    :param payment_addresses: The balance addresses that are expected to be paid off during
    the lifecycle of the account
    :return: A boolean that indicates whether the repayment has paid off the loan
    """
    if debt_addresses is None:
        debt_addresses = close_loan_DEBT_ADDRESSES
    if payment_addresses is None:
        payment_addresses = close_loan_PAYMENT_ADDRESSES
    outstanding_debt = utils_sum_balances(
        balances=balances, addresses=debt_addresses, denomination=denomination
    )
    merged_repayment_balances = BalanceDefaultDict()
    for posting_instruction in repayment_posting_instructions:
        merged_repayment_balances += posting_instruction.balances(
            account_id=account_id, tside=Tside.ASSET
        )
    repayment_amount = abs(
        utils_sum_balances(
            balances=merged_repayment_balances,
            addresses=payment_addresses,
            denomination=denomination,
        )
    )
    return repayment_amount >= outstanding_debt


# Objects below have been imported from:
#    credit_limit.py
# md5:06cc025017d33083dafbee6058c4d1f7

credit_limit_LIVE_BALANCES_BOF_ID = "live_balances_bof"
credit_limit_PARAM_CREDIT_LIMIT = "credit_limit"
credit_limit_PARAM_CREDIT_LIMIT_APPLICABLE_PRINCIPAL = "credit_limit_applicable_principal"
credit_limit_PARAM_DENOMINATION = "denomination"
credit_limit_CREDIT_LIMIT_ORIGINAL = "original"


def credit_limit_validate(
    main_vault: Any,
    loans: list[Any],
    posting_instruction: utils_PostingInstructionTypeAlias,
    non_repayable_addresses: Optional[list[str]] = None,
) -> Optional[Rejection]:
    main_vault_balances = main_vault.get_balances_observation(
        fetcher_id=credit_limit_LIVE_BALANCES_BOF_ID
    ).balances
    loan_balances = supervisor_utils_get_balance_default_dicts_for_supervisees(
        supervisees=loans, fetcher_id=credit_limit_LIVE_BALANCES_BOF_ID
    )
    denomination = credit_limit__get_denomination_parameter(vault=main_vault)
    associated_original_principal = credit_limit_calculate_associated_original_principal(
        loans=loans
    )
    unassociated_principal = credit_limit_calculate_unassociated_principal(
        main_vault_balances=main_vault_balances,
        loan_balances=loan_balances,
        denomination=denomination,
        associated_original_principal=associated_original_principal,
        non_repayable_addresses=non_repayable_addresses,
    )
    credit_limit = credit_limit__get_credit_limit_parameter(vault=main_vault)
    applicable_principal = credit_limit__get_applicable_principal_parameter(vault=main_vault)
    available_credit_limit = credit_limit_calculate_available_credit_limit(
        loan_balances=loan_balances,
        credit_limit=credit_limit,
        applicable_principal=applicable_principal,
        denomination=denomination,
        associated_original_principal=associated_original_principal,
        unassociated_principal=unassociated_principal,
    )
    posting_amount = utils_get_available_balance(
        balances=posting_instruction.balances(), denomination=denomination
    )
    if posting_amount > available_credit_limit:
        return Rejection(
            message=f"Incoming posting of {posting_amount} exceeds available credit limit of {available_credit_limit}",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


def credit_limit_calculate_associated_original_principal(loans: list[Any]) -> Decimal:
    associated_original_principal = sum(
        (Decimal(utils_get_parameter(loan_vault, "principal")) for loan_vault in loans)
    )
    return Decimal(associated_original_principal)


def credit_limit_calculate_unassociated_principal(
    main_vault_balances: BalanceDefaultDict,
    loan_balances: list[BalanceDefaultDict],
    denomination: str,
    associated_original_principal: Decimal,
    non_repayable_addresses: Optional[list[str]] = None,
) -> Decimal:
    non_repayable_addresses = non_repayable_addresses or []
    if lending_addresses_INTERNAL_CONTRA not in non_repayable_addresses:
        non_repayable_addresses.append(lending_addresses_INTERNAL_CONTRA)
    associated_repayments = supervisor_utils_sum_balances_across_supervisees(
        balances=loan_balances, denomination=denomination, addresses=non_repayable_addresses
    )
    main_vault_default_net = utils_balance_at_coordinates(
        balances=main_vault_balances, denomination=denomination
    )
    unassociated_original_principal = (
        main_vault_default_net - associated_original_principal + associated_repayments
    )
    return unassociated_original_principal


def credit_limit_calculate_available_credit_limit(
    loan_balances: list[BalanceDefaultDict],
    credit_limit: Decimal,
    applicable_principal: str,
    denomination: str,
    associated_original_principal: Decimal,
    unassociated_principal: Decimal,
) -> Decimal:
    available_credit_limit = credit_limit - unassociated_principal
    if applicable_principal == credit_limit_CREDIT_LIMIT_ORIGINAL:
        available_credit_limit -= associated_original_principal
    else:
        associated_outstanding_principal = supervisor_utils_sum_balances_across_supervisees(
            balances=loan_balances,
            denomination=denomination,
            addresses=lending_addresses_ALL_PRINCIPAL,
        )
        available_credit_limit -= associated_outstanding_principal
    return available_credit_limit


def credit_limit__get_denomination_parameter(vault: Union[Any, Any]) -> str:
    denomination: str = utils_get_parameter(vault=vault, name=credit_limit_PARAM_DENOMINATION)
    return denomination


def credit_limit__get_credit_limit_parameter(vault: Any) -> Decimal:
    credit_limit: Decimal = utils_get_parameter(vault=vault, name=credit_limit_PARAM_CREDIT_LIMIT)
    return credit_limit


def credit_limit__get_applicable_principal_parameter(vault: Any) -> str:
    applicable_principal: str = utils_get_parameter(
        vault=vault, name=credit_limit_PARAM_CREDIT_LIMIT_APPLICABLE_PRINCIPAL, is_union=True
    )
    return applicable_principal


# Objects below have been imported from:
#    delinquency.py
# md5:b99b0ef48bb663761488c57823bac9f4

delinquency_CHECK_DELINQUENCY_EVENT = "CHECK_DELINQUENCY"
delinquency_CHECK_DELINQUENCY_PREFIX = "check_delinquency"
delinquency_PARAM_GRACE_PERIOD = "grace_period"


def delinquency_get_grace_period_parameter(vault: Any) -> int:
    return int(utils_get_parameter(vault=vault, name=delinquency_PARAM_GRACE_PERIOD))


def delinquency_supervisor_event_types(product_name: str) -> list[SupervisorContractEventType]:
    """
    Returns the a list of event types for delinquency for a supervisor contract
    """
    return [
        SupervisorContractEventType(
            name=delinquency_CHECK_DELINQUENCY_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{delinquency_CHECK_DELINQUENCY_EVENT}_AST"],
        )
    ]


# Objects below have been imported from:
#    emi.py
# md5:6fd652b0be2b953dfaf528e599cb7c8b


def emi_update_emi(
    account_id: str, denomination: str, current_emi: Decimal, updated_emi: Decimal
) -> list[Posting]:
    emi_delta = current_emi - updated_emi
    if emi_delta == Decimal("0"):
        return []
    if emi_delta < Decimal("0"):
        credit_address = lending_addresses_INTERNAL_CONTRA
        debit_address = lending_addresses_EMI
        emi_delta = abs(emi_delta)
    else:
        credit_address = lending_addresses_EMI
        debit_address = lending_addresses_INTERNAL_CONTRA
    return utils_create_postings(
        amount=emi_delta,
        debit_account=account_id,
        debit_address=debit_address,
        credit_account=account_id,
        credit_address=credit_address,
        denomination=denomination,
    )


# Objects below have been imported from:
#    due_amount_calculation.py
# md5:764e3e5a69ae8c7f97be1c0a65a16ddf

due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT = "DUE_AMOUNT_CALCULATION"
due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX = "due_amount_calculation"
due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY = "due_amount_calculation_day"


def due_amount_calculation_supervisor_event_types(
    product_name: str,
) -> list[SupervisorContractEventType]:
    return [
        SupervisorContractEventType(
            name=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT}_AST"
            ],
        )
    ]


def due_amount_calculation_supervisor_schedule_logic(
    loan_vault: Any,
    main_vault: Any,
    hook_arguments: SupervisorScheduledEventHookArguments,
    account_type: str,
    amortisation_feature: lending_interfaces_SupervisorAmortisation,
    interest_application_feature: Optional[lending_interfaces_InterestApplication] = None,
    reamortisation_condition_features: Optional[
        list[lending_interfaces_SupervisorReamortisationCondition]
    ] = None,
    interest_rate_feature: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustment_features: Optional[
        list[lending_interfaces_SupervisorPrincipalAdjustment]
    ] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Calculate due amounts and create CustomInstructions to affect any required balance updates
    :param loan_vault: vault object for the account that stores balances
    :param main_vault: supervisee vault object that some features are associated with
    :param hook_arguments: the scheduled event's hook arguments
    :param account_type: the account type, used for GL posting metadata purposes
    :param amortisation_feature: feature responsible for recalculating the emi if
    reamortisation is required (determined by the reamortisation_condition_features), and
    determining term details
    :param interest_application_feature: feature that is responsible for applying interest
    as part of the due amount calculation. This can be omitted if no interest is charged for
    a product (e.g. a 0% interest Pay-In-X loan)
    :param reamortisation_condition_features: a list of features used to determine whether
    reamortisation is required
    :param interest_rate_feature: feature responsible for providing relevant interest information
    to the amortisation feature
    :param principal_adjustment_features: feature responsible for providing relevant principal
    adjustments to the amortisation feature
    :param balances: balances to use for due amount calculation. If not provided balances fetched
    as of effective datetime are used
    :param denomination: denomination to use for due amount calculation. If not provided, parameter
    values as of effective datetime are used
    :return: the custom instructions. Empty if none are required
    """
    postings: list[Posting] = []
    customer_account = loan_vault.account_id
    effective_datetime = hook_arguments.effective_datetime
    if balances is None:
        balances_mapping = loan_vault.get_balances_timeseries()
        balances = utils_get_balance_default_dict_from_mapping(
            mapping=balances_mapping, effective_datetime=hook_arguments.effective_datetime
        )
    if denomination is None:
        denomination = utils_get_parameter(vault=loan_vault, name="denomination")
    current_principal = due_amount_calculation_get_principal(
        balances=balances, denomination=denomination
    )
    (elapsed_term, remaining_term) = amortisation_feature.term_details(
        loan_vault=loan_vault,
        main_vault=main_vault,
        effective_datetime=effective_datetime,
        use_expected_term=True,
        interest_rate=interest_rate_feature,
        balances=balances,
    )
    last_execution_effective_datetime = (
        due_amount_calculation_get_supervisee_last_execution_effective_datetime(
            loan_vault=loan_vault,
            main_vault=main_vault,
            event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT,
            effective_datetime=effective_datetime,
            elapsed_term=elapsed_term,
        )
    )
    if interest_application_feature is not None:
        interest_amounts = interest_application_feature.get_interest_to_apply(
            vault=loan_vault,
            effective_datetime=effective_datetime,
            previous_application_datetime=last_execution_effective_datetime,
            balances_at_application=balances,
        )
        emi_interest_to_apply = (
            interest_amounts.total_rounded - interest_amounts.non_emi_rounded_accrued
        )
        postings += interest_application_feature.apply_interest(
            vault=loan_vault,
            effective_datetime=effective_datetime,
            previous_application_datetime=last_execution_effective_datetime,
            balances_at_application=balances,
        )
    else:
        emi_interest_to_apply = Decimal(0)
    requires_reamortisation = any(
        (
            reamortisation_interface.should_trigger_reamortisation(
                loan_vault=loan_vault,
                main_vault=main_vault,
                period_start_datetime=last_execution_effective_datetime,
                period_end_datetime=effective_datetime,
                elapsed_term=elapsed_term,
            )
            for reamortisation_interface in reamortisation_condition_features or []
        )
    )
    current_emi = due_amount_calculation_get_emi(balances=balances, denomination=denomination)
    if requires_reamortisation:
        new_emi = amortisation_feature.calculate_emi(
            loan_vault=loan_vault,
            main_vault=main_vault,
            effective_datetime=effective_datetime,
            use_expected_term=True,
            principal_amount=current_principal,
            interest_calculation_feature=interest_rate_feature,
            principal_adjustments=principal_adjustment_features,
            balances=balances,
        )
        postings += emi_update_emi(
            account_id=loan_vault.account_id,
            denomination=denomination,
            current_emi=current_emi,
            updated_emi=new_emi,
        )
    else:
        new_emi = current_emi
    return due_amount_calculation__calculate_due_amounts(
        current_principal=current_principal,
        emi_interest_to_apply=emi_interest_to_apply,
        new_emi=new_emi,
        remaining_term=remaining_term,
        override_final_event=amortisation_feature.override_final_event,
        customer_account=customer_account,
        denomination=denomination,
        event_type=hook_arguments.event_type,
        account_type=account_type,
        postings=postings,
    )


def due_amount_calculation__calculate_due_amounts(
    current_principal: Decimal,
    emi_interest_to_apply: Decimal,
    new_emi: Decimal,
    remaining_term: int,
    override_final_event: bool,
    customer_account: str,
    denomination: str,
    event_type: str,
    account_type: str,
    postings: list[Posting],
) -> list[CustomInstruction]:
    """
    Calculate the due principal amounts from the supplied current principal, EMI interest and other
    parameters.
    :param current_principal: the current principal
    :param emi_interest_to_apply: the amount of interest to apply as a portion of the EMI
    :param new_emi: the new EMI value
    :param remaining_term: the remaining terms of the loan (total - elapsed)
    :param override_final_event: whether to override the due principal final event logic
    :param customer_account: the account where principal is due
    :param denomination: denomination to use for due amount calculation
    :param event_type: schedule event type
    :param account_type: the account type to be populated on posting instruction details
    :param postings: postings to include in the custom instruction
    :return: the due amount custom instructions
    """
    principal_due = due_amount_calculation_calculate_due_principal(
        remaining_principal=current_principal,
        emi_interest_to_apply=emi_interest_to_apply,
        emi=new_emi,
        is_final_due_event=remaining_term == 1 and (not override_final_event),
    )
    postings += due_amount_calculation_transfer_principal_due(
        customer_account=customer_account, principal_due=principal_due, denomination=denomination
    )
    postings += due_amount_calculation_update_due_amount_calculation_counter(
        account_id=customer_account, denomination=denomination
    )
    if postings:
        return [
            CustomInstruction(
                postings=postings,
                override_all_restrictions=True,
                instruction_details=utils_standard_instruction_details(
                    description="Updating due balances",
                    event_type=event_type,
                    gl_impacted=True,
                    account_type=account_type,
                ),
            )
        ]
    else:
        return []


def due_amount_calculation_transfer_principal_due(
    customer_account: str, principal_due: Decimal, denomination: str
) -> list[Posting]:
    """
    Create postings to transfer amount from principal to principal due address
    :param customer_account: the account where principal is due
    :param principal_due: the amount that is due
    :param denomination: the amount's denomination
    :return: the relevant postings. Empty if amount <= 0
    """
    if principal_due <= 0:
        return []
    return [
        Posting(
            credit=True,
            account_id=customer_account,
            amount=principal_due,
            account_address=lending_addresses_PRINCIPAL,
            asset=DEFAULT_ASSET,
            denomination=denomination,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=False,
            account_id=customer_account,
            amount=principal_due,
            account_address=lending_addresses_PRINCIPAL_DUE,
            asset=DEFAULT_ASSET,
            denomination=denomination,
            phase=Phase.COMMITTED,
        ),
    ]


def due_amount_calculation_calculate_due_principal(
    remaining_principal: Decimal,
    emi_interest_to_apply: Decimal,
    emi: Decimal,
    is_final_due_event: bool,
) -> Decimal:
    """
    Calculate due principal for a given repayment, ensuring it does not exceed remaining principal
    :param remaining_principal: Remaining principal at the point of the due amount calculation
    :param emi_interest_to_apply: emi portion of interest to apply for this repayment
    :param emi: emi for this repayment
    :return: the due principal for this repayment
    """
    if emi == Decimal("0"):
        return Decimal("0")
    if is_final_due_event:
        return remaining_principal
    return min(emi - emi_interest_to_apply, remaining_principal)


def due_amount_calculation_update_due_amount_calculation_counter(
    account_id: str, denomination: str
) -> list[Posting]:
    return utils_create_postings(
        amount=Decimal("1"),
        debit_account=account_id,
        debit_address=lending_addresses_DUE_CALCULATION_EVENT_COUNTER,
        credit_account=account_id,
        credit_address=lending_addresses_INTERNAL_CONTRA,
        denomination=denomination,
    )


def due_amount_calculation_get_principal(
    balances: BalanceDefaultDict, denomination: str
) -> Decimal:
    return balances[
        BalanceCoordinate(lending_addresses_PRINCIPAL, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net


def due_amount_calculation_get_emi(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    return balances[
        BalanceCoordinate(lending_addresses_EMI, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net


def due_amount_calculation_get_first_due_amount_calculation_datetime(vault: Any) -> datetime:
    due_amount_calculation_day = int(
        utils_get_parameter(
            vault=vault, name=due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY
        )
    )
    (schedule_hour, schedule_minute, schedule_second) = utils_get_schedule_time_from_parameters(
        vault=vault, parameter_prefix=due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX
    )
    account_creation_datetime = vault.get_account_creation_datetime()
    return due_amount_calculation__get_next_due_amount_calculation_datetime(
        start_datetime=account_creation_datetime,
        due_amount_calculation_day=due_amount_calculation_day,
        due_amount_calculation_hour=schedule_hour,
        due_amount_calculation_minute=schedule_minute,
        due_amount_calculation_second=schedule_second,
        effective_datetime=account_creation_datetime,
        last_execution_datetime=None,
    )


def due_amount_calculation_get_actual_next_repayment_date(
    vault: Any, effective_datetime: datetime, elapsed_term: int, remaining_term: int
) -> datetime:
    """
    A wrapper to the main function to get the date of the next due amount calculation datetime.

    This should be used for the derived parameter as this can be called between events which means
    parameter value changes can affect the derived parameter being shown.

    This helper is only intended for use by lending products that require exactly one due
    calculation event per calendar month.

    :param vault:
    :param effective_datetime: effective dt of the calculation
    :param elapsed_term: the number of elapsed terms of the loan. Only used to verify as non-zero.
    :param remaining_term: the remaining terms of the loan (total - elapsed). Only used to verify as
     non-zero.
    :return next_due_amount_calculation_date: next expected date as of effective_datetime
    """
    next_due_calc_datetime = due_amount_calculation_get_next_due_amount_calculation_datetime(
        vault=vault,
        effective_datetime=effective_datetime,
        elapsed_term=elapsed_term,
        remaining_term=remaining_term,
    )
    last_execution_datetime = vault.get_last_execution_datetime(
        event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
    )
    count = 0
    param_timeseries = vault.get_parameter_timeseries(
        name=due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY
    ).all()
    while (
        last_execution_datetime is not None
        and next_due_calc_datetime < effective_datetime
        and (next_due_calc_datetime == last_execution_datetime + relativedelta(months=1))
    ):
        count += 1
        param_update_position = -(1 + count)
        if (
            len(param_timeseries) > count
            and param_timeseries[param_update_position].at_datetime > last_execution_datetime
        ):
            prev_due_amount_calculation_day = param_timeseries[param_update_position].value
            next_due_calc_datetime = (
                due_amount_calculation_get_next_due_amount_calculation_datetime(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    elapsed_term=elapsed_term,
                    remaining_term=remaining_term,
                    due_amount_calculation_day=prev_due_amount_calculation_day,
                )
            )
        else:
            return next_due_calc_datetime
    return next_due_calc_datetime


def due_amount_calculation_get_next_due_amount_calculation_datetime(
    vault: Any,
    effective_datetime: datetime,
    elapsed_term: int,
    remaining_term: int,
    due_amount_calculation_day: Optional[int] = None,
) -> datetime:
    """
    Calculates the next due amount calculation date, assuming a fixed monthly schedule frequency.

    If called during the opening month, next due amount calculation dt falls on the
    due amount calculation day at least one month after account opening dt.

    Subsequent calculations are exactly one month apart.

    If the due amount calculation day parameter value changes:
        - If a due amount calculation has already occurred this month,
        the new day is reflected in the due amount calculation date for the next month.

        - If a due amount calculation hasn't already occurred in the current month
        and the new due amount calculation day is greater than the day of the change,
        the new day is reflected in the due amount calculation date for the current month.

        - If a due amount calculation hasn't already occurred this month
        and the new day is lower than the current day,
        the new day is reflected in the due amount calculation date for the next month

    The elapsed and remaining terms must be used instead of the last_execution_datetime of the
    DUE_AMOUNT_CALCULATION_EVENT since last_execution_datetime always returns the most recent
    datetime, as of live. Therefore using last_execution_datetime when requesting the next
    DUE_AMOUNT_CALCULATION_EVENT in the past (e.g the derived parameter hook) will result in
    incorrect results

    :param vault:
    :param effective_datetime: effective dt of the calculation
    :param elapsed_term: the number of elapsed terms of the loan. Only used to verify as non-zero.
    :param remaining_term: the remaining terms of the loan (total - elapsed). Only used to verify as
     non-zero.
    :param due_amount_calculation_day: optional due amount calculation day, which will be obtained
    from the parameter if left as None.
    :return next_due_amount_calculation_date: next expected date as of effective_datetime
    """
    if elapsed_term == 0:
        return due_amount_calculation_get_first_due_amount_calculation_datetime(vault=vault)
    last_execution_datetime = vault.get_last_execution_datetime(
        event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
    )
    if remaining_term == 0:
        return last_execution_datetime
    if due_amount_calculation_day is None:
        due_amount_calculation_day = int(
            utils_get_parameter(
                vault=vault, name=due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY
            )
        )
    (schedule_hour, schedule_minute, schedule_second) = utils_get_schedule_time_from_parameters(
        vault=vault, parameter_prefix=due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX
    )
    if last_execution_datetime > effective_datetime:
        last_execution_datetime = None
    return due_amount_calculation__get_next_due_amount_calculation_datetime(
        start_datetime=vault.get_account_creation_datetime(),
        due_amount_calculation_day=due_amount_calculation_day,
        due_amount_calculation_hour=schedule_hour,
        due_amount_calculation_minute=schedule_minute,
        due_amount_calculation_second=schedule_second,
        effective_datetime=effective_datetime,
        last_execution_datetime=last_execution_datetime,
    )


def due_amount_calculation__get_next_due_amount_calculation_datetime(
    start_datetime: datetime,
    due_amount_calculation_day: int,
    due_amount_calculation_hour: int,
    due_amount_calculation_minute: int,
    due_amount_calculation_second: int,
    effective_datetime: datetime,
    last_execution_datetime: Optional[datetime],
) -> datetime:
    """
    Calculates the next due amount calculation date, assuming a fixed monthly schedule frequency.

    :param start_datetime: the anchor point to determine the next datetime if the last execution
    datetime is None, e.g. the account creation datetime to determine the first due amount
    calculation datetime
    :param due_amount_calculation_day:
    :param due_amount_calculation_hour:
    :param due_amount_calculation_minute:
    :param due_amount_calculation_second:
    :param effective_datetime: effective dt of the calculation
    :param last_execution_datetime: Optional, last execution dt of DUE_AMOUNT_CALCULATION
    :return next_due_amount_calculation_date: next expected date as of effective_datetime
    """
    if last_execution_datetime is None:
        earliest_datetime = start_datetime.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + relativedelta(months=1)
        next_due_amount_calculation_datetime = start_datetime.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        next_due_amount_calculation_datetime += relativedelta(
            day=due_amount_calculation_day, months=1
        )
        while (
            earliest_datetime > next_due_amount_calculation_datetime
            or next_due_amount_calculation_datetime < effective_datetime
        ):
            next_due_amount_calculation_datetime += relativedelta(months=1)
    elif due_amount_calculation__due_amount_calculation_day_changed(
        last_execution_datetime, due_amount_calculation_day
    ) and (
        last_execution_datetime.month == effective_datetime.month
        or due_amount_calculation_day > effective_datetime.day
    ):
        next_due_amount_calculation_datetime = last_execution_datetime + relativedelta(
            months=1, day=due_amount_calculation_day
        )
    else:
        next_due_amount_calculation_datetime = last_execution_datetime + relativedelta(months=1)
    return next_due_amount_calculation_datetime.replace(
        hour=due_amount_calculation_hour,
        minute=due_amount_calculation_minute,
        second=due_amount_calculation_second,
    )


def due_amount_calculation__due_amount_calculation_day_changed(
    last_execution_datetime: Optional[datetime], due_amount_calculation_day: int
) -> bool:
    if last_execution_datetime is None:
        return False
    return last_execution_datetime.day != due_amount_calculation_day


def due_amount_calculation_get_supervisee_last_execution_effective_datetime(
    loan_vault: Any,
    main_vault: Any,
    event_type: str,
    effective_datetime: datetime,
    elapsed_term: int,
) -> datetime:
    last_execution_datetime = (
        loan_vault.get_account_creation_datetime()
        if elapsed_term == 0
        else main_vault.get_last_execution_datetime(event_type=event_type)
    )
    if last_execution_datetime is None:
        last_execution_datetime = loan_vault.get_account_creation_datetime()
    if last_execution_datetime == effective_datetime:
        last_execution_datetime -= relativedelta(months=1)
    return last_execution_datetime


# Objects below have been imported from:
#    interest_accrual_supervisor.py
# md5:6439c8659553bf8e916d1c3df8357902

interest_accrual_supervisor_ACCRUED_INTEREST_RECEIVABLE = (
    interest_accrual_common_ACCRUED_INTEREST_RECEIVABLE
)
interest_accrual_supervisor_NON_EMI_ACCRUED_INTEREST_RECEIVABLE = (
    f"NON_EMI_{interest_accrual_supervisor_ACCRUED_INTEREST_RECEIVABLE}"
)
interest_accrual_supervisor_ACCRUAL_EVENT = interest_accrual_common_ACCRUAL_EVENT
interest_accrual_supervisor_INTEREST_ACCRUAL_PREFIX = (
    interest_accrual_common_INTEREST_ACCRUAL_PREFIX
)
interest_accrual_supervisor_data_fetchers = [fetchers_EOD_FETCHER]
interest_accrual_supervisor_PARAM_DAYS_IN_YEAR = interest_accrual_common_PARAM_DAYS_IN_YEAR
interest_accrual_supervisor_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = (
    "accrued_interest_receivable_account"
)


def interest_accrual_supervisor_daily_accrual_logic(
    vault: Any,
    hook_arguments: ScheduledEventHookArguments,
    next_due_amount_calculation_datetime: datetime,
    interest_rate_feature: lending_interfaces_InterestRate,
    account_type: str = "",
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    principal_addresses: Optional[list[str]] = None,
    inflight_postings: Optional[list[CustomInstruction]] = None,
    customer_accrual_address: Optional[str] = None,
    accrual_internal_account: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Accrue receivable interest on the sum of EOD balances held at the principal addresses.
    :param vault: Vault object for the account accruing interest
    :param hook_args: scheduled event hook arguments
    :param next_due_amount_calculation_datetime: if the accrual effective date is a month or more
    away from this date, the accrued interest is considered to be non-emi
    :param interest_rate_feature: interest rate feature to get the yearly interest rate
    :param account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :param balances: the eod balances to use for accrual. If None, EOD_FETCHER_ID is used to
    fetch the balances.
    :param denomination: the denomination to use for accrual. If None, the latest value of the
    `denomination` parameter is used.
    :param principal_addresses: the addresses of balances to accrue on. Defaults to `PRINCIPAL`
    :param inflight_postings: Any inflight postings that are to be merged with the EOD balances,
    common use case is when interest is capitalised at the end of a repayment holiday and so the
    accrual effective balance needs to be adjusted
    :param customer_accrual_address: the address to accrue to. If None, accrual address is either:
    - NON_EMI_ACCRUED_INTEREST_RECEIVABLE, if the midnight we're accruing for is more than a month
    from the next interest calculation due date, and the interest should not be considered as part
    of EMI
    - ACCRUED_INTEREST_RECEIVABLE otherwise
    :return: The custom instructions to accrue interest, if required
    """
    midnight = hook_arguments.effective_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    principal_addresses = principal_addresses or [lending_addresses_PRINCIPAL]
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name="denomination")
    if balances is None:
        balances_mapping = vault.get_balances_timeseries()
        balances = utils_get_balance_default_dict_from_mapping(
            mapping=balances_mapping, effective_datetime=midnight
        )
    if inflight_postings:
        balances = utils_update_inflight_balances(
            account_id=vault.account_id,
            tside=Tside.ASSET,
            current_balances=balances,
            posting_instructions=inflight_postings,
        )
    effective_balance = Decimal(
        sum(
            (
                balances[
                    BalanceCoordinate(
                        principal_address, DEFAULT_ASSET, denomination, phase=Phase.COMMITTED
                    )
                ].net
                for principal_address in principal_addresses
            )
        )
    )
    if customer_accrual_address is None:
        if midnight <= next_due_amount_calculation_datetime - relativedelta(months=1):
            customer_accrual_address = (
                interest_accrual_supervisor_NON_EMI_ACCRUED_INTEREST_RECEIVABLE
            )
        else:
            customer_accrual_address = interest_accrual_supervisor_ACCRUED_INTEREST_RECEIVABLE
    if accrual_internal_account is None:
        accrual_internal_account = utils_get_parameter(
            vault=vault, name=interest_accrual_supervisor_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
        )
    return interest_accrual_common_daily_accrual(
        customer_account=vault.account_id,
        customer_address=customer_accrual_address,
        denomination=denomination,
        internal_account=accrual_internal_account,
        days_in_year=utils_get_parameter(
            vault=vault, name=interest_accrual_supervisor_PARAM_DAYS_IN_YEAR, is_union=True
        ),
        yearly_rate=interest_rate_feature.get_annual_interest_rate(
            vault=vault,
            effective_datetime=hook_arguments.effective_datetime,
            balances=balances,
            denomination=denomination,
        ),
        effective_balance=effective_balance,
        account_type=account_type,
        event_type=hook_arguments.event_type,
        effective_datetime=midnight,
        payable=False,
        precision=utils_get_parameter(
            vault=vault, name=interest_accrual_common_PARAM_ACCRUAL_PRECISION
        ),
        rounding=ROUND_HALF_UP,
    )


# Objects below have been imported from:
#    interest_application.py
# md5:b206c2a889540dba58282c6ec772665e

interest_application_PARAM_APPLICATION_PRECISION = "application_precision"

# Objects below have been imported from:
#    interest_application_supervisor.py
# md5:3c63151ca9afffc901dceca33d329a3b

interest_application_supervisor_ACCRUED_INTEREST_RECEIVABLE = (
    interest_accrual_common_ACCRUED_INTEREST_RECEIVABLE
)
interest_application_supervisor_NON_EMI_ACCRUED_INTEREST_RECEIVABLE = (
    interest_accrual_supervisor_NON_EMI_ACCRUED_INTEREST_RECEIVABLE
)
interest_application_supervisor_INTEREST_DUE = "INTEREST_DUE"
interest_application_supervisor_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = (
    interest_accrual_supervisor_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
)
interest_application_supervisor_PARAM_INTEREST_RECEIVED_ACCOUNT = "interest_received_account"
interest_application_supervisor_PARAM_APPLICATION_PRECISION = "application_precision"


def interest_application_supervisor_apply_interest(
    vault: Any,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances_at_application: Optional[BalanceDefaultDict] = None,
) -> list[Posting]:
    application_internal_account = utils_get_parameter(
        vault, interest_application_supervisor_PARAM_INTEREST_RECEIVED_ACCOUNT
    )
    application_interest_address = interest_application_supervisor_INTEREST_DUE
    accrual_internal_account = utils_get_parameter(
        vault, interest_application_supervisor_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    )
    denomination = utils_get_parameter(vault, "denomination")
    application_precision: int = utils_get_parameter(
        vault=vault, name=interest_application_supervisor_PARAM_APPLICATION_PRECISION
    )
    if balances_at_application is None:
        balances_at_application = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    interest_application_amounts = interest_application_supervisor__get_interest_to_apply(
        balances=balances_at_application,
        denomination=denomination,
        application_precision=application_precision,
    )
    return accruals_accrual_application_postings(
        customer_account=vault.account_id,
        denomination=denomination,
        application_amount=interest_application_amounts.emi_rounded_accrued,
        accrual_amount=interest_application_amounts.emi_accrued,
        accrual_customer_address=interest_application_supervisor_ACCRUED_INTEREST_RECEIVABLE,
        accrual_internal_account=accrual_internal_account,
        application_customer_address=application_interest_address,
        application_internal_account=application_internal_account,
        payable=False,
    ) + accruals_accrual_application_postings(
        customer_account=vault.account_id,
        denomination=denomination,
        application_amount=interest_application_amounts.total_rounded
        - interest_application_amounts.emi_rounded_accrued,
        accrual_amount=interest_application_amounts.non_emi_accrued,
        accrual_customer_address=interest_application_supervisor_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
        accrual_internal_account=accrual_internal_account,
        application_customer_address=application_interest_address,
        application_internal_account=application_internal_account,
        payable=False,
    )


def interest_application_supervisor__get_interest_to_apply(
    balances: BalanceDefaultDict, denomination: str, application_precision: int
) -> lending_interfaces_InterestAmounts:
    (
        emi_accrued_amount,
        emi_rounded_accrued_amount,
    ) = interest_application_supervisor__get_emi_interest_to_apply(
        balances=balances, denomination=denomination, precision=application_precision
    )
    (
        non_emi_accrued_amount,
        non_emi_rounded_accrued_amount,
    ) = interest_application_supervisor__get_non_emi_interest_to_apply(
        balances=balances, denomination=denomination, precision=application_precision
    )
    total_rounded_amount = utils_round_decimal(
        amount=emi_accrued_amount + non_emi_accrued_amount,
        decimal_places=application_precision,
        rounding=ROUND_HALF_UP,
    )
    return lending_interfaces_InterestAmounts(
        emi_accrued=emi_accrued_amount,
        emi_rounded_accrued=emi_rounded_accrued_amount,
        non_emi_accrued=non_emi_accrued_amount,
        non_emi_rounded_accrued=non_emi_rounded_accrued_amount,
        total_rounded=total_rounded_amount,
    )


def interest_application_supervisor_get_interest_to_apply(
    vault: Any,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances_at_application: Optional[BalanceDefaultDict] = None,
    balances_one_repayment_period_ago: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    application_precision: Optional[int] = None,
) -> lending_interfaces_InterestAmounts:
    """Determine the interest amounts for application, handling emi/non-emi considerations.

    :param vault: vault object for the account with interest to apply
    :param effective_datetime: not used but required by the interface signature
    :param previous_application_datetime: not used but required by the interface signature
    :param balances_at_application: balances to extract current accrued amounts from.
    :param balances_one_repayment_period_ago: not used but required by the interface signature,
    since we have the separate addresses needed available in balances_at_application.
    :param denomination: accrual denomination. Only pass in to override the feature's default
    fetching
    :param application_precision: number of places that accrued interest is rounded to before
    application. Only pass in to override the feature's default fetching
    :return: the interest amounts
    """
    if balances_at_application is None:
        balances_mapping = vault.get_balances_timeseries()
        balances_at_application = utils_get_balance_default_dict_from_mapping(
            mapping=balances_mapping, effective_datetime=effective_datetime
        )
    if application_precision is None:
        application_precision = utils_get_parameter(
            vault=vault, name=interest_application_supervisor_PARAM_APPLICATION_PRECISION
        )
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name="denomination")
    return interest_application_supervisor__get_interest_to_apply(
        balances=balances_at_application,
        denomination=denomination,
        application_precision=application_precision,
    )


def interest_application_supervisor__get_emi_interest_to_apply(
    balances: BalanceDefaultDict,
    denomination: str,
    accrual_addresses: Optional[list[str]] = None,
    precision: int = 2,
    rounding: str = ROUND_HALF_UP,
) -> tuple[Decimal, Decimal]:
    """
    Determine the amount of interest to apply that should be included in EMI, before and after
    rounding.
    :param balances: balances for the account that interest is being applied on
    :param denomination: denomination of the accrued interest to apply
    :param accrual_address: balance addresses to consider. Defaults to
    and ACCRUED_INTEREST_RECEIVABLE, which excludes non-emi interest
    :param precision: the number of decimal places to round to
    :param rounding: the Decimal rounding strategy to use
    :return: the unrounded and rounded amounts
    """
    accrual_addresses = accrual_addresses or [
        interest_application_supervisor_ACCRUED_INTEREST_RECEIVABLE
    ]
    accrued_amount = Decimal(
        sum(
            (
                balances[
                    BalanceCoordinate(
                        accrual_address, DEFAULT_ASSET, denomination, phase=Phase.COMMITTED
                    )
                ].net
                for accrual_address in accrual_addresses
            )
        )
    )
    return (
        accrued_amount,
        utils_round_decimal(accrued_amount, decimal_places=precision, rounding=rounding),
    )


def interest_application_supervisor__get_non_emi_interest_to_apply(
    balances: BalanceDefaultDict,
    denomination: str,
    accrual_addresses: Optional[list[str]] = None,
    precision: int = 2,
    rounding: str = ROUND_HALF_UP,
) -> tuple[Decimal, Decimal]:
    """
    Determine the amount of interest to apply that should not be included in EMI, before and after
    rounding.
    :param balances: balances for the account that interest is being applied on
    :param denomination: denomination of the accrued interest to apply
    :param accrual_address: balance addresses to consider. Defaults to
    and NON_EMI_ACCRUED_INTEREST_RECEIVABLE, which excludes non-emi interest
    :param precision: the number of decimal places to round to
    :param rounding: the Decimal rounding strategy to use
    :return: the unrounded and rounded amounts
    """
    accrual_addresses = accrual_addresses or [
        interest_application_supervisor_NON_EMI_ACCRUED_INTEREST_RECEIVABLE
    ]
    accrued_amount = Decimal(
        sum(
            (
                balances[
                    BalanceCoordinate(
                        accrual_address, DEFAULT_ASSET, denomination, phase=Phase.COMMITTED
                    )
                ].net
                for accrual_address in accrual_addresses
            )
        )
    )
    return (
        accrued_amount,
        utils_round_decimal(accrued_amount, decimal_places=precision, rounding=rounding),
    )


def interest_application_supervisor_repay_accrued_interest(
    vault: Any,
    repayment_amount: Decimal,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
    application_customer_address: str = DEFAULT_ADDRESS,
) -> list[Posting]:
    """Creates postings to repay accrued interest. This is typically for overpayment scenarios.
    In order to recognise interest income, repaying accrued interest is modelled as
    interest application + immediate repayment.

    :param vault: the vault object for the account holding the accrued interest to be repaid
    :param repayment_amount: the repayment amount that can be allocated to accrued interest
    :param application_customer_address: the address to use on the customer account for interest
    application. Applying to the DEFAULT_ADDRESS will rebalance the repayment that credits
    DEFAULT_ADDRESS, which makes this equivalent to applying the interest and repaying the applied
    interest
    :return: the postings for repaying accrued interest. Empty list if no repayment is possible
    (e.g. repayment amount is insufficient, or no accrued interest to repay)
    """
    if repayment_amount <= 0:
        return []
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name="denomination")
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    accrual_internal_account: str = utils_get_parameter(
        vault=vault, name=interest_application_supervisor_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    )
    application_internal_account: str = utils_get_parameter(
        vault=vault, name=interest_application_supervisor_PARAM_INTEREST_RECEIVED_ACCOUNT
    )
    application_precision: int = utils_get_parameter(
        vault=vault, name=interest_application_supervisor_PARAM_APPLICATION_PRECISION
    )
    repayment_amount_remaining = repayment_amount
    postings: list[Posting] = []
    for (interest_address, interest_to_apply) in (
        (
            interest_application_supervisor_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
            interest_application_supervisor__get_non_emi_interest_to_apply,
        ),
        (
            interest_application_supervisor_ACCRUED_INTEREST_RECEIVABLE,
            interest_application_supervisor__get_emi_interest_to_apply,
        ),
    ):
        (accrued_amount, rounded_accrued_amount) = interest_to_apply(
            balances=balances, denomination=denomination, precision=application_precision
        )
        if rounded_accrued_amount <= repayment_amount_remaining:
            application_amount = rounded_accrued_amount
            accrual_amount = accrued_amount
        else:
            application_amount = repayment_amount_remaining
            accrual_amount = repayment_amount_remaining
        if application_amount > 0:
            repayment_amount_remaining -= application_amount
            postings.extend(
                accruals_accrual_application_postings(
                    customer_account=vault.account_id,
                    denomination=denomination,
                    application_amount=application_amount,
                    accrual_amount=accrual_amount,
                    accrual_customer_address=interest_address,
                    accrual_internal_account=accrual_internal_account,
                    application_customer_address=application_customer_address,
                    application_internal_account=application_internal_account,
                    payable=False,
                )
            )
        if repayment_amount_remaining == 0:
            return postings
    return postings


def interest_application_supervisor_get_application_precision(vault: Any) -> int:
    return int(
        utils_get_parameter(
            vault=vault, name=interest_application_supervisor_PARAM_APPLICATION_PRECISION
        )
    )


interest_application_supervisor_interest_application_interface = (
    lending_interfaces_InterestApplication(
        apply_interest=interest_application_supervisor_apply_interest,
        get_interest_to_apply=interest_application_supervisor_get_interest_to_apply,
        get_application_precision=interest_application_supervisor_get_application_precision,
    )
)

# Objects below have been imported from:
#    fixed.py
# md5:f2f9eef46e1a533911ac0476c6df2d10


def fixed_get_annual_interest_rate(
    vault: Any,
    effective_datetime: Optional[datetime] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    return Decimal(
        utils_get_parameter(vault, "fixed_interest_rate", at_datetime=effective_datetime)
    )


def fixed_get_daily_interest_rate(
    vault: Any,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    annual_rate = fixed_get_annual_interest_rate(vault=vault)
    days_in_year = utils_get_parameter(vault, "days_in_year", is_union=True)
    return utils_yearly_to_daily_rate(effective_datetime, annual_rate, days_in_year)


def fixed_get_monthly_interest_rate(
    vault: Any,
    effective_datetime: Optional[datetime] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    annual_rate = fixed_get_annual_interest_rate(vault=vault, effective_datetime=effective_datetime)
    return utils_yearly_to_monthly_rate(annual_rate)


fixed_interest_rate_interface = lending_interfaces_InterestRate(
    get_daily_interest_rate=fixed_get_daily_interest_rate,
    get_monthly_interest_rate=fixed_get_monthly_interest_rate,
    get_annual_interest_rate=fixed_get_annual_interest_rate,
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
#    late_repayment.py
# md5:626b94d9efd00829169cb818da10c167

late_repayment_PARAM_LATE_REPAYMENT_FEE = "late_repayment_fee"
late_repayment_PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "late_repayment_fee_income_account"
late_repayment_PARAM_DENOMINATION = "denomination"


def late_repayment_get_late_repayment_fee_parameter(vault: Any) -> Decimal:
    return Decimal(utils_get_parameter(vault=vault, name=late_repayment_PARAM_LATE_REPAYMENT_FEE))


def late_repayment_get_total_overdue_amount(vault: Any, precision: int = 2) -> Decimal:
    """
    Sums the balances across all overdue addresses
    :param vault: the vault object to get the balances
    :param precision: the number of decimal places to round to
    :return: due balance in Decimal
    """
    denomination: str = utils_get_parameter(vault=vault, name=late_repayment_PARAM_DENOMINATION)
    balances = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    return utils_sum_balances(
        balances=balances,
        addresses=lending_addresses_OVERDUE_ADDRESSES,
        denomination=denomination,
        decimal_places=precision,
    )


def late_repayment_schedule_logic(
    vault: Any,
    hook_arguments: Union[ScheduledEventHookArguments, SupervisorScheduledEventHookArguments],
    denomination: str,
    account_type: str = "",
    check_total_overdue_amount: bool = True,
) -> list[CustomInstruction]:
    """
    Create postings to charge the late repayment fee if there is a late repayment fee configured,
    And: There is an outstanding overdue amount
    Or: The check on the overdue amount is skipped (check_total_overdue_amount set to False).
    :param vault: the vault object for the account to check late repayment
    :param hook_arguments: the hook arguments as received from the contract
    :param denomination: the denomination as used in vault
    :param account_type: the account type as to be noted in custom instruction detail
    :param check_total_overdue_amount: whether to check the total overdue amount is gt zero.
    If True (default) check total overdue amount is gt zero, and if it isn't then do not charge a
    late repayment fee.
    If False, skip the check on total overdue amount and go ahead to charge the late repayment fee
    :return: list of the late repayment fee custom instruction
    """
    fee_amount: Decimal = utils_get_parameter(vault, name=late_repayment_PARAM_LATE_REPAYMENT_FEE)
    late_repayment_fee_income_account: str = utils_get_parameter(
        vault, name=late_repayment_PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT
    )
    if (
        check_total_overdue_amount
        and late_repayment_get_total_overdue_amount(vault) <= 0
        or not fee_amount
    ):
        return []
    return fees_fee_custom_instruction(
        customer_account_id=vault.account_id,
        denomination=denomination,
        amount=fee_amount,
        internal_account=late_repayment_fee_income_account,
        customer_account_address=lending_addresses_PENALTIES,
        instruction_details=utils_standard_instruction_details(
            description="Charge late payment",
            event_type=hook_arguments.event_type,
            account_type=account_type,
        ),
    )


# Objects below have been imported from:
#    maximum_outstanding_loans.py
# md5:157347f1b1a3437252b5c24436767f95

maximum_outstanding_loans_PARAM_MAXIMUM_NUMBER_OF_OUTSTANDING_LOANS = (
    "maximum_number_of_outstanding_loans"
)


def maximum_outstanding_loans_validate(main_vault: Any, loans: list[Any]) -> Optional[Rejection]:
    """
    Validate the number of outstanding loans is below the amount specified by a parameter
    :param main_vault: the supervisee vault object that defines the max number of loans allowed
    :param loans: a list of supervised loan vaults
    :return: rejection if the number of loan vaults is greater than or equal to the allowed number
    """
    maximum_number_of_outstanding_loans = (
        maximum_outstanding_loans__get_max_outstanding_loans_parameter(vault=main_vault)
    )
    if len(loans) >= maximum_number_of_outstanding_loans:
        return Rejection(
            message="Cannot create new loan due to outstanding loan limit being exceeded. "
            + f"Current number of loans: {len(loans)}, "
            + f"maximum loan limit: {maximum_number_of_outstanding_loans}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


def maximum_outstanding_loans__get_max_outstanding_loans_parameter(vault: Any) -> int:
    max_outstanding_loans: int = utils_get_parameter(
        vault=vault, name=maximum_outstanding_loans_PARAM_MAXIMUM_NUMBER_OF_OUTSTANDING_LOANS
    )
    return max_outstanding_loans


# Objects below have been imported from:
#    overdue.py
# md5:11cacf1a6c91093b7cdfbea3281b9f19

overdue_CHECK_OVERDUE_EVENT = "CHECK_OVERDUE"
overdue_CHECK_OVERDUE_PREFIX = "check_overdue"
overdue_PARAM_REPAYMENT_PERIOD = "repayment_period"
overdue_OVERDUE_REPAYMENT_NOTIFICATION_SUFFIX = "_OVERDUE_REPAYMENT"
overdue_FUND_MOVEMENT_MAP = {
    lending_addresses_PRINCIPAL_DUE: lending_addresses_PRINCIPAL_OVERDUE,
    lending_addresses_INTEREST_DUE: lending_addresses_INTEREST_OVERDUE,
}


def overdue_supervisor_event_types(product_name: str) -> list[SupervisorContractEventType]:
    return [
        SupervisorContractEventType(
            name=overdue_CHECK_OVERDUE_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{overdue_CHECK_OVERDUE_EVENT}_AST"],
        )
    ]


def overdue_notification_type(product_name: str) -> str:
    """
    Creates the notification type
    :param product_name: The product name
    :return: str
    """
    return f"{product_name.upper()}{overdue_OVERDUE_REPAYMENT_NOTIFICATION_SUFFIX}"


def overdue_schedule_logic(
    vault: Any,
    hook_arguments: Union[ScheduledEventHookArguments, SupervisorScheduledEventHookArguments],
    balances: Optional[BalanceDefaultDict] = None,
    account_type: str = "",
    late_repayment_fee: Decimal = Decimal("0"),
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
    denomination: str = utils_get_parameter(vault=vault, name="denomination")
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    account_id = vault.account_id
    due_amounts = {}
    for (due_address, overdue_address) in overdue_FUND_MOVEMENT_MAP.items():
        due_amounts[due_address] = utils_balance_at_coordinates(
            balances=balances, address=due_address, denomination=denomination
        )
        postings += utils_create_postings(
            amount=due_amounts[due_address],
            debit_account=account_id,
            credit_account=account_id,
            debit_address=overdue_address,
            credit_address=due_address,
            denomination=denomination,
            asset=DEFAULT_ASSET,
        )
    if not postings:
        return ([], [])
    custom_instructions = [
        CustomInstruction(
            postings=postings,
            override_all_restrictions=True,
            instruction_details=utils_standard_instruction_details(
                description="Move outstanding due debt into overdue debt.",
                event_type=hook_arguments.event_type,
                gl_impacted=False,
                account_type=account_type,
            ),
        )
    ]
    notifications: list[AccountNotificationDirective] = []
    notifications.extend(
        overdue_get_overdue_repayment_notification(
            account_id=account_id,
            product_name=account_type,
            effective_datetime=hook_arguments.effective_datetime,
            overdue_principal_amount=due_amounts[lending_addresses_PRINCIPAL_DUE],
            overdue_interest_amount=due_amounts[lending_addresses_INTEREST_DUE],
            late_repayment_fee=late_repayment_fee,
        )
    )
    return (custom_instructions, notifications)


def overdue_get_overdue_repayment_notification(
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
                notification_type=overdue_notification_type(product_name),
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


# Objects below have been imported from:
#    overpayment.py
# md5:a8cb4d2f6f955706d1b72f5c93822334

overpayment_ACCRUED_EXPECTED_INTEREST = "ACCRUED_EXPECTED_INTEREST"
overpayment_EMI_PRINCIPAL_EXCESS = "EMI_PRINCIPAL_EXCESS"
overpayment_OVERPAYMENT = "OVERPAYMENT"
overpayment_OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER = (
    "OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER"
)
overpayment_EXPECTED_PRINCIPAL = [
    lending_addresses_PRINCIPAL,
    overpayment_OVERPAYMENT,
    overpayment_EMI_PRINCIPAL_EXCESS,
]
overpayment_EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID = "EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER"
overpayment_OVERPAYMENT_TRACKER_EFF_FETCHER_ID = "OVERPAYMENT_TRACKER_EFF_FETCHER"
overpayment_REDUCE_EMI = "reduce_emi"
overpayment_REDUCE_TERM = "reduce_term"
overpayment_PARAM_OVERPAYMENT_FEE_RATE = "overpayment_fee_rate"
overpayment_PARAM_OVERPAYMENT_FEE_INCOME_ACCOUNT = "overpayment_fee_income_account"
overpayment_PARAM_OVERPAYMENT_IMPACT_PREFERENCE = "overpayment_impact_preference"
overpayment_overpayment_impact_preference_param = Parameter(
    name=overpayment_PARAM_OVERPAYMENT_IMPACT_PREFERENCE,
    shape=UnionShape(
        items=[
            UnionItem(key=overpayment_REDUCE_EMI, display_name="Reduce EMI"),
            UnionItem(key=overpayment_REDUCE_TERM, display_name="Reduce Term"),
        ]
    ),
    level=ParameterLevel.TEMPLATE,
    description="Defines how to handle an overpayment: Reduce EMI but preserve the term.Reduce term but preserve monthly repayment amount.",
    display_name="Overpayment Impact Preference",
    default_value=UnionItemValue(key=overpayment_REDUCE_TERM),
)


def overpayment_get_max_overpayment_fee(
    fee_rate: Decimal,
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int = 2,
    principal_address: str = lending_addresses_PRINCIPAL,
) -> Decimal:
    """
    The maximum overpayment fee is equal to the maximum_overpayment_amount * overpayment_fee_rate,

    Maximum Overpayment Amount Proof:
        X = maximum_overpayment_amount
        R = overpayment_fee_rate
        P = remaining_principal
        F = overpayment_fee

        overpayment_fee = overpayment_amount * overpayment_fee_rate
        principal_repaid = overpayment_amount - overpayment_fee
        maximum_overpayment_amount is when principal_repaid == remaining_principal, therefore

        P = X - F
        but F = X*R
        => P = X - XR => X(1-R)
        and so:
        X = P / (1-R)
        and so F_max = PR / (1-R)
    """
    if fee_rate >= 1:
        return Decimal("0")
    principal = utils_balance_at_coordinates(
        balances=balances, address=principal_address, denomination=denomination
    )
    maximum_overpayment = utils_round_decimal(
        amount=principal / (1 - fee_rate), decimal_places=precision
    )
    overpayment_fee = overpayment_get_overpayment_fee(
        principal_repaid=maximum_overpayment, overpayment_fee_rate=fee_rate, precision=precision
    )
    return overpayment_fee


def overpayment_get_overpayment_fee(
    principal_repaid: Decimal, overpayment_fee_rate: Decimal, precision: int
) -> Decimal:
    """Determines the overpayment fee for a given amount of principal being repaid

    :param principal_repaid: the amount of principal repaid by the repayment
    :param overpayment_fee_rate: the percentage of principal to include in the fee. Must be
    < 1, or 0 is returned
    :param precision: decimal places to round the fee to
    :return: the overpayment fee
    """
    if overpayment_fee_rate >= 1:
        return Decimal("0")
    return utils_round_decimal(
        amount=principal_repaid * overpayment_fee_rate, decimal_places=precision
    )


def overpayment_get_overpayment_fee_postings(
    overpayment_fee: Decimal,
    denomination: str,
    customer_account_id: str,
    customer_account_address: str,
    internal_account: str,
) -> list[Posting]:
    return fees_fee_postings(
        customer_account_id=customer_account_id,
        customer_account_address=customer_account_address,
        denomination=denomination,
        amount=overpayment_fee,
        internal_account=internal_account,
    )


def overpayment_validate_overpayment_across_supervisees(
    main_vault: Any,
    repayment_amount: Decimal,
    denomination: str,
    all_supervisee_balances: list[BalanceDefaultDict],
    rounding_precision: int = 2,
) -> Optional[Rejection]:
    """Rejects repayments if the repayment amount across all supervisees exceeds
    the total outstanding amount + the maximum overpayment amount

    :param main_vault: The vault object that stores the overpayment fee rate parameter
    :param repayment_amount: The repayment amount
    :param denomination: The denomination of the loan
    :param all_supervisee_balances: All of the supervisee balances used
    to validate the repayment
    :param rounding_precision: The rounding precision for the maximum overpayment
    amount. Defaults to 2
    :return: A rejection if the repayment amount exceeds the total
    outstanding amount + maximum overpayment amount, otherwise None
    """
    overpayment_fee_rate = overpayment_get_overpayment_fee_rate_parameter(vault=main_vault)
    merged_supervisee_balances = BalanceDefaultDict()
    for balance in all_supervisee_balances:
        merged_supervisee_balances += balance
    max_overpayment_fee = overpayment_get_max_overpayment_fee(
        fee_rate=overpayment_fee_rate,
        balances=merged_supervisee_balances,
        denomination=denomination,
    )
    total_outstanding_amount = utils_sum_balances(
        balances=merged_supervisee_balances,
        addresses=lending_addresses_ALL_OUTSTANDING_SUPERVISOR,
        denomination=denomination,
        decimal_places=rounding_precision,
    )
    max_overpayment_amount = utils_round_decimal(
        amount=max_overpayment_fee + total_outstanding_amount, decimal_places=rounding_precision
    )
    if repayment_amount > max_overpayment_amount:
        return Rejection(
            message=f"The repayment amount {repayment_amount} {denomination} exceeds the total maximum repayment amount of {max_overpayment_amount} {denomination}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


def overpayment_track_emi_principal_excess(
    vault: Any,
    interest_application_feature: lending_interfaces_InterestApplication,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """Creates posting instructions to track the emi principal excess as a result of overpayments.
    This function is intended for use as part of due amount calculation schedule.

    The emi principal excess comes from the reduced accruals as a result of an overpayment. These
    result in a lower than expected due interest, which in turn increases the portion of principal
    in subsequent emis. Tracking this means we can avoid reamortisation for non-overpayment reasons
    (e.g. variable rate change) from accidentally including the impact of overpayments that are
    meant to reduce the term.

    :param vault: vault object for the relevant account
    :param interest_application_feature: feature used by the account to apply interest
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :return: list of posting instruction. May be empty (e.g. if no additional excess needs tracking)
    """
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name="denomination")
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=overpayment_OVERPAYMENT_TRACKER_EFF_FETCHER_ID
        ).balances
    precision = interest_application_feature.get_application_precision(vault=vault)
    actual_interest_to_apply = interest_application_feature.get_interest_to_apply(
        vault=vault,
        effective_datetime=effective_datetime,
        previous_application_datetime=previous_application_datetime,
        denomination=denomination,
        application_precision=precision,
    ).total_rounded
    expected_interest_to_apply = utils_balance_at_coordinates(
        balances=balances,
        address=overpayment_ACCRUED_EXPECTED_INTEREST,
        denomination=denomination,
        decimal_places=precision,
    )
    additional_emi_principal_excess = expected_interest_to_apply - actual_interest_to_apply
    postings = utils_create_postings(
        amount=additional_emi_principal_excess,
        debit_account=vault.account_id,
        debit_address=overpayment_EMI_PRINCIPAL_EXCESS,
        credit_account=vault.account_id,
        credit_address=lending_addresses_INTERNAL_CONTRA,
        denomination=denomination,
    )
    if postings:
        return [
            CustomInstruction(
                postings=postings,
                override_all_restrictions=True,
                instruction_details={
                    "description": f"Increase principal excess due to expected_interest_to_apply={expected_interest_to_apply!r} being larger than actual_interest_to_apply={actual_interest_to_apply!r}"
                },
            )
        ]
    return []


def overpayment_track_interest_on_expected_principal(
    vault: Any,
    hook_arguments: Union[ScheduledEventHookArguments, SupervisorScheduledEventHookArguments],
    interest_rate_feature: lending_interfaces_InterestRate,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """Creates posting instructions to track interest on expected principal, which excludes the
    impact of overpayments. This function is intended for use as part of daily interest accrual.

    Expected interest helps determine the additional principal indirectly paid off after an
    overpayment due to subsequent accruals having a reduced principal, which in turn increases the
    portion of principal in the corresponding emi payments. This in turn avoids reamortisation for
    non-overpayment reasons (e.g. variable rate change) from accidentally including the impact of
    overpayments that are meant to reduce the term.
    :param vault: vault object for the account
    :param hook_arguments: hook arguments for the interest accrual event
    :param interest_rate_feature: feature used to determine the interest rate as of the
    hook_arguments' effective_datetime
    :param balances: Optional balances. Defaults to latest EOD balances before the hook_arguments'
    effective_datetime
    :param denomination: denomination to track in. Defaults to the `denomination` parameter
    :return: postings to track expected interest. Empty list if not required (e.g. 0 principal or 0
    interest rate)
    """
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=overpayment_EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = str(utils_get_parameter(vault=vault, name="denomination"))
    precision = int(
        utils_get_parameter(vault=vault, name=interest_accrual_common_PARAM_ACCRUAL_PRECISION)
    )
    days_in_year: str = utils_get_parameter(
        vault=vault, name=interest_accrual_common_PARAM_DAYS_IN_YEAR, is_union=True
    )
    expected_principal = utils_sum_balances(
        balances=balances, denomination=denomination, addresses=overpayment_EXPECTED_PRINCIPAL
    )
    yearly_rate = interest_rate_feature.get_annual_interest_rate(
        vault, hook_arguments.effective_datetime, balances=balances, denomination=denomination
    )
    accrual = interest_accrual_common_calculate_daily_accrual(
        effective_balance=expected_principal,
        effective_datetime=hook_arguments.effective_datetime,
        yearly_rate=yearly_rate,
        days_in_year=days_in_year,
        precision=precision,
    )
    if accrual and accrual.amount > 0:
        return [
            CustomInstruction(
                postings=utils_create_postings(
                    amount=accrual.amount,
                    debit_account=vault.account_id,
                    debit_address=overpayment_ACCRUED_EXPECTED_INTEREST,
                    credit_account=vault.account_id,
                    credit_address=lending_addresses_INTERNAL_CONTRA,
                    denomination=denomination,
                ),
                instruction_details={
                    "description": f"Tracking expected interest at yearly rate {yearly_rate} on expected principal {expected_principal}"
                },
                override_all_restrictions=True,
            )
        ]
    return []


def overpayment_reset_due_amount_calc_overpayment_trackers(
    vault: Any, balances: Optional[BalanceDefaultDict] = None, denomination: Optional[str] = None
) -> list[CustomInstruction]:
    """Resets accrued expected and overpayment since prev due amount calc tracker balances to 0.
    Intended for use in due amount calculation schedule.

    :param vault: vault object for the account
    :param balances: balances to base calculations on
    :param denomination: tracker denomination
    :return: custom instructions to reset tracker balances. May be empty list (e.g. no trackers to
    reset)
    """
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=overpayment_OVERPAYMENT_TRACKER_EFF_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = str(utils_get_parameter(vault=vault, name="denomination"))
    reset_postings = utils_reset_tracker_balances(
        balances=balances,
        account_id=vault.account_id,
        tracker_addresses=[
            overpayment_ACCRUED_EXPECTED_INTEREST,
            overpayment_OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
        ],
        contra_address=lending_addresses_INTERNAL_CONTRA,
        denomination=denomination,
        tside=Tside.ASSET,
    )
    if reset_postings:
        return [
            CustomInstruction(
                postings=reset_postings,
                instruction_details={"description": "Resetting overpayment trackers"},
                override_all_restrictions=True,
            )
        ]
    return []


def overpayment_supervisor_should_trigger_reamortisation(
    loan_vault: Any,
    main_vault: Any,
    period_start_datetime: datetime,
    period_end_datetime: datetime,
    elapsed_term: Optional[int],
    balances: Optional[BalanceDefaultDict] = None,
) -> bool:
    """Indicates if reamortisation is required for supervisees if there has been
    an overpayment since the previous due amount calculation and the overpayment
    impact preference is to reduce emi.

    :param loan_vault: supervisee vault object for the account, used to fetch the denomination
    and balances if necessary
    :param main_vault: supervisee vault object, used to fetch the overpayment impact preference
    :param period_start_datetime: start of period to evaluate reamortisation condition. Unused
    in this implementation
    :param period_end_datetime: start of period to evaluate reamortisation condition. Unused
    in this implementation
    :param elapsed_term: elapsed term on the loan. Unused in this implementation
    :param balances: balances used to calculate the overpayment since the previous due amount
    calculation. Defaults to the latest balances if not passed in
    :return: boolean indicating whether reamortisation is required (True) or not (False).
    """
    if balances is None:
        balances_mapping = loan_vault.get_balances_timeseries()
        balances = utils_get_balance_default_dict_from_mapping(mapping=balances_mapping)
    denomination: str = utils_get_parameter(vault=loan_vault, name="denomination")
    overpayment_overpayment_impact_preference_param = (
        overpayment_get_overpayment_preference_parameter(vault=main_vault)
    )
    return (
        overpayment_overpayment_impact_preference_param == overpayment_REDUCE_EMI
        and utils_balance_at_coordinates(
            balances=balances,
            address=overpayment_OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
            denomination=denomination,
        )
        > 0
    )


def overpayment_supervisor_calculate_principal_adjustment(
    loan_vault: Any,
    main_vault: Any,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    """
    Determines the adjustment as a result of overpayments that should be made to the principal,
    intended to be used inside the supervisor_due_amount_calculation event. Gets parameters from
    both the loan_vault and main_vault. Functionally behaves like calculate_principal_adjustment
    :param loan_vault: supervisee vault object for the account, used to fetch balances
    :param main_vault: supervisee vault object, used to fetch the overpayment impact preference
    :param balances: Optional balances. Defaults to latest EOD balances' effective_datetime
    :param denomination: denomination to track in. Defaults to the `denomination` parameter
    """
    if balances is None:
        balances = loan_vault.get_balances_observation(
            fetcher_id=overpayment_EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = utils_get_parameter(vault=loan_vault, name="denomination")
    overpayment_preference = overpayment_get_overpayment_preference_parameter(vault=main_vault)
    return (
        Decimal("0")
        if overpayment_preference == overpayment_REDUCE_EMI
        else utils_balance_at_coordinates(
            balances=balances,
            address=overpayment_OVERPAYMENT,
            asset=DEFAULT_ASSET,
            denomination=denomination,
            phase=Phase.COMMITTED,
        )
        + utils_balance_at_coordinates(
            balances=balances,
            address=overpayment_EMI_PRINCIPAL_EXCESS,
            asset=DEFAULT_ASSET,
            denomination=denomination,
            phase=Phase.COMMITTED,
        )
    )


def overpayment_get_overpayment_preference_parameter(vault: Any) -> str:
    return str(
        utils_get_parameter(
            vault=vault, name=overpayment_PARAM_OVERPAYMENT_IMPACT_PREFERENCE, is_union=True
        )
    )


def overpayment_get_overpayment_fee_rate_parameter(vault: Any) -> Decimal:
    overpayment_fee_rate: Decimal = utils_get_parameter(
        vault=vault, name=overpayment_PARAM_OVERPAYMENT_FEE_RATE
    )
    return overpayment_fee_rate


def overpayment_get_overpayment_fee_income_account_parameter(vault: Any) -> str:
    overpayment_fee_income_account: str = utils_get_parameter(
        vault=vault, name=overpayment_PARAM_OVERPAYMENT_FEE_INCOME_ACCOUNT
    )
    return overpayment_fee_income_account


overpayment_SupervisorOverpaymentReamortisationCondition = (
    lending_interfaces_SupervisorReamortisationCondition(
        should_trigger_reamortisation=overpayment_supervisor_should_trigger_reamortisation
    )
)
overpayment_SupervisorOverpaymentPrincipalAdjustment = (
    lending_interfaces_SupervisorPrincipalAdjustment(
        calculate_principal_adjustment=overpayment_supervisor_calculate_principal_adjustment
    )
)

# Objects below have been imported from:
#    payments.py
# md5:c8020a38a72304fb2f82b95b605625fe

payments_RepaymentAmounts = NamedTuple(
    "RepaymentAmounts", [("unrounded_amount", Decimal), ("rounded_amount", Decimal)]
)


def payments_redistribute_postings(
    debit_account: str,
    denomination: str,
    amount: Decimal,
    credit_account: str,
    credit_address: str,
    debit_address: str = DEFAULT_ADDRESS,
) -> list[Posting]:
    """
    Redistribute a lump sum of payment into another account / address
    :param debit_account: the account id that receives initial sum and initiates the redistribution
    :param denomination: the denomination of the application
    :param amount: the amount to pay. If <= 0 an empty list is returned
    :param credit_account: the account id that receives the redistributed amount
    :param credit_address: the address to receive the redistributed amount in the credit_account
    :param debit_address: the address from which to move the amount
    :return: the payment postings, in credit-debit pair
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


def payments_distribute_repayment_for_single_target(
    balances: BalanceDefaultDict,
    repayment_amount: Decimal,
    denomination: str,
    repayment_hierarchy: Optional[list[str]] = None,
    phase: Phase = Phase.COMMITTED,
) -> tuple[dict[str, payments_RepaymentAmounts], Decimal]:
    """
    Determines how a repayment amount is distributed across balances based on the repayment
    hierarchy and the outstanding balances. Each repayment hierarchy address' balance is
    rounded to 2 decimal points for repayment purposes. Both rounded and unrounded amounts are
    returned so that the consumer can decide how to handle remainders. For example, a repayment of
    0.01 distributed to a balance of 0.0052 or to a balance of 0.0012

    :param balances: The balances to distribute the repayment amount across
    :param repayment_amount: The 2 decimal point repayment amount to distribute
    :param denomination: The denomination of the repayment
    :param repayment_hierarchy: Order in which a repayment amount is to be
    distributed across addresses. Defaults to standard lending repayment hierarchy
    :param phase: The balance phase of the balances fetched to get amounts from
    :return: A dictionary of addresses to repayment amounts to be repaid and the remaining
    repayment amount
    """
    remaining_repayment_amount = repayment_amount
    if repayment_hierarchy is None:
        repayment_hierarchy = lending_addresses_REPAYMENT_HIERARCHY
    repayment_per_address: dict[str, payments_RepaymentAmounts] = {}
    for repayment_address in repayment_hierarchy:
        balance_address = BalanceCoordinate(repayment_address, DEFAULT_ASSET, denomination, phase)
        unrounded_address_amount = balances[balance_address].net
        rounded_address_amount = utils_round_decimal(unrounded_address_amount, 2)
        rounded_address_repayment_amount = min(rounded_address_amount, remaining_repayment_amount)
        if rounded_address_repayment_amount == Decimal(0):
            continue
        unrounded_address_repayment_amount = (
            unrounded_address_amount
            if rounded_address_amount <= remaining_repayment_amount
            else remaining_repayment_amount
        )
        repayment_per_address[repayment_address] = payments_RepaymentAmounts(
            unrounded_amount=unrounded_address_repayment_amount,
            rounded_amount=rounded_address_repayment_amount,
        )
        remaining_repayment_amount -= rounded_address_repayment_amount
    return (repayment_per_address, remaining_repayment_amount)


def payments_distribute_repayment_for_multiple_targets(
    balances_per_target: dict[str, BalanceDefaultDict],
    repayment_amount: Decimal,
    denomination: str,
    repayment_hierarchy: list[list[str]],
) -> tuple[dict[str, dict[str, payments_RepaymentAmounts]], Decimal]:
    """
    Determines how a repayment amount should be distributed across a number of repayment targets
    (loans), based on the repayment hierarchy and the outstanding balances. This is intended to
    only be used by a supervisor.
    :param balances_per_target: a dictionary where the key is the repayment target account id and
    the value is its balances. This should be sorted in order of which target should be repaid
    first.
    :param repayment_amount: repayment amount to distribute
    :param denomination: the denomination of the repayment
    :param repayment_hierarchy: The order in which a repayment amount is to be distributed across
    addresses for one or more targets. The outer list represents ordering across accounts and the
    the inner lists represent ordering within an account.
    For example, the hierarchy [[ADDRESS_1],[ADDRESS_2, ADDRESS_3]] would result in a distribution
    in this order, assuming two loans loan_1 and loan_2:
    # ADDRESS_1 paid on loan_1 and then loan_2
    ADDRESS_1 loan_1
    ADDRESS_1 loan_2
    # ADDRESS_2 and ADDRESS_3 paid on loan 1 and then loan 2
    ADDRESS_2 loan_1
    ADDRESS_3 loan_1
    ADDRESS_2 loan_2
    ADDRESS_3 loan_2
    :return: A tuple containing
        - a dictionary where the key is the target account id and the value is the repayment
    amounts for each address.
        - the remaining repayment amount.
    """
    remaining_repayment_amount = repayment_amount
    repayments_per_target: dict[str, dict[str, payments_RepaymentAmounts]] = {
        target: {} for target in balances_per_target.keys()
    }
    for address_list in repayment_hierarchy:
        for target_account_id in balances_per_target.keys():
            (
                repayment_per_address,
                remaining_repayment_amount,
            ) = payments_distribute_repayment_for_single_target(
                balances=balances_per_target[target_account_id],
                repayment_amount=remaining_repayment_amount,
                denomination=denomination,
                repayment_hierarchy=address_list,
            )
            repayments_per_target[target_account_id].update(repayment_per_address)
            if remaining_repayment_amount == Decimal("0"):
                return (repayments_per_target, Decimal("0"))
    return (repayments_per_target, remaining_repayment_amount)


def payments_generate_repayment_postings_for_multiple_targets(
    main_vault: Any,
    sorted_repayment_targets: list[Any],
    hook_arguments: SupervisorPostPostingHookArguments,
    repayment_hierarchy: Optional[list[list[str]]] = None,
    overpayment_features: Optional[list[lending_interfaces_MultiTargetOverpayment]] = None,
    early_repayment_fees: Optional[list[lending_interfaces_EarlyRepaymentFee]] = None,
) -> dict[str, list[CustomInstruction]]:
    """
    A top level wrapper that generates a list of custom instructions per repayment target to spread
    a regular payment across different targets and balance addresses based on the repayment
    hierarchy and debit addresses. Optionally handles overpayments if any overpayment features are
    passed in.

    It is assumed that the repayment amount will always be in the DEFAULT balance address
    associated with the first posting instruction, which should be enforced in the pre_posting hook

    :param main_vault: The supervisee vault object to instruct the repayment instructions from
    :param sorted_repayment_targets: The repayment targets sorted by the required order of repayment
    :param hook_arguments: The post posting hook arguments
    :param repayment_hierarchy: The order in which a repayment amount is to be distributed across
    addresses for one or more targets. The outer list represents ordering across accounts and the
    the inner lists represent ordering within an account.
    :param overpayment_features: List of features responsible for handling any excess
    overpayment amount after all repayments have been made. This can be omitted if
    overpayments can be disregarded. Note that handle_overpayment will be called for
    each feature passed into the list.
    :param early_repayment_fees: List of early repayment fee features for handling the amounts of
    early repayment fees that are being charged, but only applicable if the repayment amount is
    correct for making an early repayment to fully pay off one or more loans.
    :return: The repayment instructions for each repayment target
    """
    denomination: str = common_parameters_get_denomination_parameter(vault=main_vault)
    if repayment_hierarchy is None:
        repayment_hierarchy = [[address] for address in lending_addresses_REPAYMENT_HIERARCHY]
    posting_instructions_per_target: dict[str, list[CustomInstruction]] = {
        target.account_id: [] for target in sorted_repayment_targets
    }
    if (
        repayment_amount := utils_balance_at_coordinates(
            balances=hook_arguments.supervisee_posting_instructions[main_vault.account_id][
                0
            ].balances(),
            denomination=denomination,
        )
    ) >= 0:
        return posting_instructions_per_target
    balances_per_target = supervisor_utils_get_balances_default_dicts_from_timeseries(
        supervisees=sorted_repayment_targets, effective_datetime=hook_arguments.effective_datetime
    )
    (
        repayments_per_target,
        overpayment_amount,
    ) = payments_distribute_repayment_for_multiple_targets(
        balances_per_target=balances_per_target,
        repayment_amount=abs(repayment_amount),
        denomination=denomination,
        repayment_hierarchy=repayment_hierarchy,
    )
    for (target_account_id, repayment_amounts_per_address) in repayments_per_target.items():
        repayment_postings: list[Posting] = []
        for (address, repayment_amounts) in repayment_amounts_per_address.items():
            if repayment_amounts.rounded_amount == Decimal(0):
                continue
            repayment_postings += payments_redistribute_postings(
                debit_account=target_account_id,
                amount=repayment_amounts.rounded_amount,
                denomination=denomination,
                credit_account=target_account_id,
                credit_address=address,
                debit_address=DEFAULT_ADDRESS
                if target_account_id == main_vault.account_id
                else lending_addresses_INTERNAL_CONTRA,
            )
        if repayment_postings:
            posting_instructions_per_target[target_account_id] += [
                CustomInstruction(
                    postings=repayment_postings,
                    instruction_details={
                        "description": "Process a repayment",
                        "event": "PROCESS_REPAYMENTS",
                    },
                )
            ]
    if overpayment_amount > 0 and overpayment_features is not None:
        overpayment_postings_per_target: dict[str, list[Posting]] = {
            target.account_id: [] for target in sorted_repayment_targets
        }
        for overpayment_feature in overpayment_features:
            for (target_account_id, postings) in overpayment_feature.handle_overpayment(
                main_vault=main_vault,
                overpayment_amount=overpayment_amount,
                denomination=denomination,
                balances_per_target_vault={
                    target: balances_per_target[target.account_id]
                    for target in sorted_repayment_targets
                },
            ).items():
                overpayment_postings_per_target[target_account_id] += postings
        for (target_account_id, postings) in overpayment_postings_per_target.items():
            if postings:
                posting_instructions_per_target[target_account_id] += [
                    CustomInstruction(
                        postings=postings,
                        instruction_details={
                            "description": "Process repayment overpayment",
                            "event": "PROCESS_REPAYMENTS",
                        },
                    )
                ]
    return posting_instructions_per_target


# Objects below have been imported from:
#    repayment_holiday.py
# md5:8ab69326d0731879f6300743f6dbefd4

repayment_holiday_PARAM_DELINQUENCY_BLOCKING_FLAGS = "delinquency_blocking_flags"
repayment_holiday_PARAM_DUE_AMOUNT_CALCULATION_BLOCKING_FLAGS = (
    "due_amount_calculation_blocking_flags"
)
repayment_holiday_PARAM_INTEREST_ACCRUAL_BLOCKING_FLAGS = "interest_accrual_blocking_flags"
repayment_holiday_PARAM_OVERDUE_AMOUNT_CALCULATION_BLOCKING_FLAGS = (
    "overdue_amount_calculation_blocking_flags"
)


def repayment_holiday_is_delinquency_blocked(vault: Any, effective_datetime: datetime) -> bool:
    return utils_is_flag_in_list_applied(
        vault=vault,
        parameter_name=repayment_holiday_PARAM_DELINQUENCY_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def repayment_holiday_is_due_amount_calculation_blocked(
    vault: Any, effective_datetime: datetime
) -> bool:
    return utils_is_flag_in_list_applied(
        vault=vault,
        parameter_name=repayment_holiday_PARAM_DUE_AMOUNT_CALCULATION_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def repayment_holiday_is_interest_accrual_blocked(vault: Any, effective_datetime: datetime) -> bool:
    return utils_is_flag_in_list_applied(
        vault=vault,
        parameter_name=repayment_holiday_PARAM_INTEREST_ACCRUAL_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def repayment_holiday_is_overdue_amount_calculation_blocked(
    vault: Any, effective_datetime: datetime
) -> bool:
    return utils_is_flag_in_list_applied(
        vault=vault,
        parameter_name=repayment_holiday_PARAM_OVERDUE_AMOUNT_CALCULATION_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def repayment_holiday_supervisor_should_trigger_reamortisation_no_impact_preference(
    loan_vault: Any,
    main_vault: Any,
    period_start_datetime: datetime,
    period_end_datetime: datetime,
    elapsed_term: Optional[int] = None,
) -> bool:
    """
    Determines whether to trigger reamortisation due to a repayment holiday ending.
    Only returns True if a repayment holiday was active at period start datetime
    and no longer is as of period end datetime the repayment holiday impact preference is not
    considered, useful for loans which mandate a repayment holiday increasing emi and therefore do
    not define the parameter.

    :param vault: Not used but required for the interface
    :param main_vault: supervisee vault object that stores flag timeseries
    :param period_start_datetime: datetime of the period start, typically this will be the datetime
    of the previous due amount calculation. This is intentionally not an Optional[] argument since
    period_start_datetime=None would result in comparing the monthly interest rate between latest()
    and period_end_datetime.
    :param period_end_datetime: datetime of the period end, typically the effective_datetime of the
    current due amount calculation event
    :param elapsed_term: Not used but required for the interface
    :return bool: Whether reamortisation is required
    """
    return repayment_holiday__has_repayment_holiday_ended(
        vault=main_vault,
        period_start_datetime=period_start_datetime,
        period_end_datetime=period_end_datetime,
    )


def repayment_holiday__has_repayment_holiday_ended(
    vault: Union[Any, Any], period_start_datetime: datetime, period_end_datetime: datetime
) -> bool:
    return repayment_holiday_is_due_amount_calculation_blocked(
        vault=vault, effective_datetime=period_start_datetime
    ) and (
        not repayment_holiday_is_due_amount_calculation_blocked(
            vault=vault, effective_datetime=period_end_datetime
        )
    )


repayment_holiday_SupervisorReamortisationConditionWithoutPreference = lending_interfaces_SupervisorReamortisationCondition(
    should_trigger_reamortisation=repayment_holiday_supervisor_should_trigger_reamortisation_no_impact_preference
)

# Objects below have been imported from:
#    drawdown_loan.py
# md5:99ca9e037d17294ee87de4e62ea71bb2

drawdown_loan_PARAM_PENALTY_INTEREST_RATE = "penalty_interest_rate"
drawdown_loan_PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE = "include_base_rate_in_penalty_rate"
drawdown_loan_PARAM_PENALTY_INTEREST_INCOME_ACCOUNT = "penalty_interest_income_account"

# Objects below have been imported from:
#    line_of_credit_supervisor.py
# md5:f1caa8160814498877fb6ca7e7ab7eee

PLAN_TYPE = "LINE_OF_CREDIT_SUPERVISOR"
LOC_ACCOUNT_TYPE = "LOC"
DRAWDOWN_LOAN_ACCOUNT_TYPE = "DRAWDOWN_LOAN"
LOC_ALIAS = "line_of_credit"
DRAWDOWN_LOAN_ALIAS = "drawdown_loan"
REPAYMENT_DUE_NOTIFICATION = "LOC_REPAYMENT_DUE"
DELINQUENT_NOTIFICATION = "LOC_DELINQUENT"
LOANS_PAID_OFF_NOTIFICATION = "LOC_LOANS_PAID_OFF"
data_fetchers = [fetchers_LIVE_BALANCES_BOF, *interest_accrual_supervisor_data_fetchers]
event_types = [
    SupervisorContractEventType(
        name=interest_accrual_supervisor_ACCRUAL_EVENT,
        scheduler_tag_ids=[f"{PLAN_TYPE}_{interest_accrual_supervisor_ACCRUAL_EVENT}_AST"],
    ),
    *supervisor_utils_schedule_sync_event_types(product_name=PLAN_TYPE),
    *due_amount_calculation_supervisor_event_types(product_name=PLAN_TYPE),
    *overdue_supervisor_event_types(product_name=PLAN_TYPE),
    *delinquency_supervisor_event_types(product_name=PLAN_TYPE),
]
NON_REPAYABLE_ADDRESSES = [lending_addresses_EMI, lending_addresses_DUE_CALCULATION_EVENT_COUNTER]
FIXED_RATE_FEATURE = fixed_interest_rate_interface


def _get_loan_vaults_for_repayment_distribution(
    loan_vaults: list[Any], posting_instruction: utils_PostingInstructionTypeAlias
) -> list[Any]:
    target_account_id = posting_instruction.instruction_details.get("target_account_id")
    return (
        list(filter(lambda vault: vault.account_id == target_account_id, loan_vaults))
        if target_account_id
        else loan_vaults
    )


def _validate_repayment(
    loc_vault: Any,
    all_supervisee_balances: list[BalanceDefaultDict],
    repayment_amount: Decimal,
    denomination: str,
    rounding_precision: int = 2,
) -> Optional[Rejection]:
    """
    Checks whether the repayment amount should be committed
    to the ledger, and returns a rejection if the
    repayment amount is invalid.

    :param loc_vault: The vault object for the loc supervisee
    :param all_supervisee_balances: All of the supervisee balances used
    to validate the repayment
    :param repayment_amount: The repayment amount
    :param denomination: The denomination of the repayment
    :param rounding_precision: The decimal places to use for the amounts to validate.
    Defaults to 2
    :return: A rejection if the repayment amount is invalid,
    otherwise None
    """
    if overpayment_rejection := overpayment_validate_overpayment_across_supervisees(
        main_vault=loc_vault,
        repayment_amount=repayment_amount,
        denomination=denomination,
        all_supervisee_balances=all_supervisee_balances,
        rounding_precision=rounding_precision,
    ):
        return overpayment_rejection
    return None


def _handle_repayment(
    hook_arguments: SupervisorPostPostingHookArguments,
    sorted_repayment_targets: list[Any],
    loc_vault: Any,
    denomination: str,
) -> tuple[
    dict[str, list[PostingInstructionsDirective]], dict[str, list[AccountNotificationDirective]]
]:
    """
    Processes repayment and handles the following:
        - Distributing the repayment amount and returning the repayment instructions for the
        individual loans.
        - Checking if loans have been fully paid off and returning the relevant loan closure
        notification(s).
    :param hook_arguments: the post posting hook arguments
    :param sorted_repayment_targets: line of credit and/or loans to be repaid. This should be
    sorted in the required order of repayment
    :param loc_vault: the vault object of the Line of Credit account
    :param denomination: the posting instructions denomination
    :return a tuple containing:
        - Posting instructions for the line of credit account or individual loan accounts.
        - Notifications for the closure of individual loans.
    """
    balances_per_target = supervisor_utils_get_balances_default_dicts_from_timeseries(
        supervisees=sorted_repayment_targets, effective_datetime=hook_arguments.effective_datetime
    )
    repayments_custom_instructions_per_target = (
        payments_generate_repayment_postings_for_multiple_targets(
            main_vault=loc_vault,
            sorted_repayment_targets=sorted_repayment_targets,
            hook_arguments=hook_arguments,
            repayment_hierarchy=[[address] for address in lending_addresses_REPAYMENT_HIERARCHY],
            overpayment_features=[
                lending_interfaces_MultiTargetOverpayment(handle_overpayment=_handle_overpayment)
            ],
        )
    )
    posting_directives: dict[str, list[PostingInstructionsDirective]] = {
        target_vault.account_id: [
            PostingInstructionsDirective(
                posting_instructions=repayments_custom_instructions_per_target[
                    target_vault.account_id
                ],
                client_batch_id="REPAYMENT_"
                + f"{target_vault.account_id}_{target_vault.get_hook_execution_id()}",
                value_datetime=hook_arguments.effective_datetime,
            )
        ]
        if repayments_custom_instructions_per_target[target_vault.account_id]
        else []
        for target_vault in sorted_repayment_targets
        if target_vault != loc_vault
    }
    aggregated_repayments_custom_instructions = _aggregate_repayment_postings(
        repayments_custom_instructions_per_target=repayments_custom_instructions_per_target,
        loc_vault=loc_vault,
        loc_balances=balances_per_target[loc_vault.account_id],
    )
    if loc_posting_instructions := (
        repayments_custom_instructions_per_target[loc_vault.account_id]
        + aggregated_repayments_custom_instructions
    ):
        posting_directives[loc_vault.account_id] = [
            PostingInstructionsDirective(
                posting_instructions=loc_posting_instructions,
                client_batch_id="REPAYMENT_"
                + f"{loc_vault.account_id}_{loc_vault.get_hook_execution_id()}",
                value_datetime=hook_arguments.effective_datetime,
            )
        ]
    closure_notification_directives = _get_loans_closure_notification_directives(
        loc_vault=loc_vault,
        repayments_custom_instructions_per_target=repayments_custom_instructions_per_target,
        balances_per_target=balances_per_target,
        denomination=denomination,
    )
    return (posting_directives, closure_notification_directives)


def _handle_overpayment(
    main_vault: Any,
    overpayment_amount: Decimal,
    denomination: str,
    balances_per_target_vault: dict[Any, BalanceDefaultDict],
) -> dict[str, list[Posting]]:
    """
    Processes overpayment and handles the following:
        - Charging the overpayment fee.
        - Updating the overpayment trackers.
        - Distributing the overpayment amount across the individual loans.

    :param main_vault: The supervisee to instruct the overpayment fee from
    :param overpayment_amount: The overpayment amount
    :param denomination: The overpayment denomination
    :param balances_per_target_vault: The balances for each target
    :return: The postings required for each target
    """
    merged_balances = BalanceDefaultDict()
    for balances in balances_per_target_vault.values():
        merged_balances += balances
    overpayment_fee_rate = overpayment_get_overpayment_fee_rate_parameter(vault=main_vault)
    overpayment_fee = min(
        overpayment_get_overpayment_fee(
            principal_repaid=overpayment_amount,
            overpayment_fee_rate=overpayment_fee_rate,
            precision=2,
        ),
        overpayment_get_max_overpayment_fee(
            fee_rate=overpayment_fee_rate,
            balances=merged_balances,
            denomination=denomination,
            precision=2,
        ),
    )
    overpayment_excluding_fee = overpayment_amount - overpayment_fee
    overpayment_postings_per_target = _distribute_overpayment(
        overpayment_amount=overpayment_excluding_fee,
        denomination=denomination,
        balances_per_loan_vault={
            loan_vault: balances
            for (loan_vault, balances) in balances_per_target_vault.items()
            if loan_vault != main_vault
        },
    )
    overpayment_postings_per_target[
        main_vault.account_id
    ] = overpayment_get_overpayment_fee_postings(
        overpayment_fee=overpayment_fee,
        denomination=denomination,
        customer_account_id=main_vault.account_id,
        customer_account_address=DEFAULT_ADDRESS,
        internal_account=overpayment_get_overpayment_fee_income_account_parameter(vault=main_vault),
    )
    return overpayment_postings_per_target


def _distribute_overpayment(
    overpayment_amount: Decimal,
    denomination: str,
    balances_per_loan_vault: dict[Any, BalanceDefaultDict],
) -> dict[str, list[Posting]]:
    """
    Creates the required postings to distribute an overpayment across the loans and update the
    relevant trackers.

    :param overpayment_amount: The overpayment amount
    :param denomination: The overpayment denomination
    :param balances_per_loan_vault: The balances for each loan
    :return: The postings required to distribute the overpayment correctly
    """
    overpayment_postings_per_loan: dict[str, list[Posting]] = {}
    overpayment_hierarchy = lending_addresses_OVERPAYMENT_HIERARCHY_SUPERVISOR
    (overpayments_per_loan, _) = payments_distribute_repayment_for_multiple_targets(
        balances_per_target={
            loan_vault.account_id: balances
            for (loan_vault, balances) in balances_per_loan_vault.items()
        },
        repayment_amount=overpayment_amount,
        denomination=denomination,
        repayment_hierarchy=overpayment_hierarchy,
    )
    overpayments_per_loan_vault = {
        loan_vault: overpayments_per_loan[loan_vault.account_id]
        for loan_vault in balances_per_loan_vault.keys()
    }
    accrued_interest_addresses = [
        lending_addresses_ACCRUED_INTEREST_RECEIVABLE,
        lending_addresses_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
    ]
    for (loan_vault, overpayment_amounts_per_address) in overpayments_per_loan_vault.items():
        overpayment_postings_per_loan[loan_vault.account_id] = []
        accrued_interest_repayment_amount = Decimal("0")
        for (address, amounts) in overpayment_amounts_per_address.items():
            if address == lending_addresses_PRINCIPAL and amounts.rounded_amount > Decimal("0"):
                overpayment_postings_per_loan[
                    loan_vault.account_id
                ] += payments_redistribute_postings(
                    debit_account=loan_vault.account_id,
                    amount=amounts.rounded_amount,
                    denomination=denomination,
                    credit_account=loan_vault.account_id,
                    credit_address=address,
                    debit_address=lending_addresses_INTERNAL_CONTRA,
                )
                overpayment_postings_per_loan[loan_vault.account_id] += utils_create_postings(
                    amount=amounts.rounded_amount,
                    debit_account=loan_vault.account_id,
                    debit_address=overpayment_OVERPAYMENT,
                    credit_account=loan_vault.account_id,
                    credit_address=lending_addresses_INTERNAL_CONTRA,
                    denomination=denomination,
                )
                overpayment_postings_per_loan[loan_vault.account_id] += utils_create_postings(
                    amount=amounts.rounded_amount,
                    debit_account=loan_vault.account_id,
                    debit_address=overpayment_OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                    credit_account=loan_vault.account_id,
                    credit_address=lending_addresses_INTERNAL_CONTRA,
                    denomination=denomination,
                )
            elif address in accrued_interest_addresses:
                accrued_interest_repayment_amount += amounts.unrounded_amount
        overpayment_postings_per_loan[
            loan_vault.account_id
        ] += interest_application_supervisor_repay_accrued_interest(
            vault=loan_vault,
            repayment_amount=accrued_interest_repayment_amount,
            denomination=denomination,
            balances=balances_per_loan_vault[loan_vault],
            application_customer_address=lending_addresses_INTERNAL_CONTRA,
        )
    return overpayment_postings_per_loan


def _aggregate_repayment_postings(
    repayments_custom_instructions_per_target: dict[str, list[CustomInstruction]],
    loc_vault: Any,
    loc_balances: BalanceDefaultDict,
) -> list[CustomInstruction]:
    instructions_per_loan = {
        target_account_id: instructions
        for (target_account_id, instructions) in repayments_custom_instructions_per_target.items()
        if target_account_id != loc_vault.account_id
    }
    flat_overpayment_hierarchy = [
        address
        for address_list in lending_addresses_OVERPAYMENT_HIERARCHY_SUPERVISOR
        for address in address_list
    ]
    if aggregate_posting_instructions := supervisor_utils_create_aggregate_posting_instructions(
        aggregate_account_id=loc_vault.account_id,
        posting_instructions_by_supervisee=instructions_per_loan,
        prefix="TOTAL",
        balances=loc_balances,
        addresses_to_aggregate=[
            *lending_addresses_REPAYMENT_HIERARCHY,
            *flat_overpayment_hierarchy,
        ],
        force_override=False,
    ):
        return aggregate_posting_instructions
    return []


def _get_loans_closure_notification_directives(
    loc_vault: Any,
    repayments_custom_instructions_per_target: dict[str, list[CustomInstruction]],
    balances_per_target: dict[str, BalanceDefaultDict],
    denomination: str,
) -> dict[str, list[AccountNotificationDirective]]:
    notification_directives: dict[str, list[AccountNotificationDirective]] = {}
    repayments_custom_instructions_per_loan = {
        account_id: instructions
        for (account_id, instructions) in repayments_custom_instructions_per_target.items()
        if account_id != loc_vault.account_id
    }
    if paid_off_loans_notification := _get_paid_off_loans_notification(
        repayment_custom_instructions_per_loan=repayments_custom_instructions_per_loan,
        balances_per_target=balances_per_target,
        denomination=denomination,
    ):
        notification_directives.update({loc_vault.account_id: paid_off_loans_notification})
    return notification_directives


def _schedule_updates_when_supervisees(
    loc_vault: Any, hook_arguments: SupervisorScheduledEventHookArguments
) -> list[UpdatePlanEventTypeDirective]:
    """
    Used to determine required schedule updates when the supervisee line of credit account is
    first associated to the plan.
    """
    return [
        UpdatePlanEventTypeDirective(
            event_type=interest_accrual_supervisor_ACCRUAL_EVENT,
            expression=utils_get_schedule_expression_from_parameters(
                vault=loc_vault,
                parameter_prefix=interest_accrual_supervisor_INTEREST_ACCRUAL_PREFIX,
            ),
            skip=False,
        ),
        UpdatePlanEventTypeDirective(
            event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT,
            schedule_method=utils_get_end_of_month_schedule_from_parameters(
                vault=loc_vault,
                parameter_prefix=due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX,
            ),
            skip=False,
        ),
    ]


def _handle_accrue_interest(
    vault: Any,
    hook_arguments: SupervisorScheduledEventHookArguments,
    loc_vault: Any,
    loan_vaults: list[Any],
) -> dict[str, list[PostingInstructionsDirective]]:
    supervisee_pi_directives = {}
    posting_instructions_by_supervisee = {}
    denomination = common_parameters_get_denomination_parameter(vault=loc_vault)
    last_execution_datetime = loc_vault.get_last_execution_datetime(
        event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
    )
    next_due_calc_datetime = due_amount_calculation_get_actual_next_repayment_date(
        vault=loc_vault,
        effective_datetime=hook_arguments.effective_datetime,
        elapsed_term=1 if last_execution_datetime else 0,
        remaining_term=1,
    )
    for loan in loan_vaults:
        next_due_calc_datetime_loan = (
            next_due_calc_datetime + relativedelta(months=1)
            if (loan.get_account_creation_datetime() + relativedelta(months=1)).date()
            > next_due_calc_datetime.date()
            else next_due_calc_datetime
        )
        accrual_instructions = _get_standard_interest_accrual_custom_instructions(
            vault=loan,
            hook_arguments=hook_arguments,
            next_due_amount_calculation_datetime=next_due_calc_datetime_loan,
            denomination=denomination,
        )
        accrual_instructions += _get_penalty_interest_accrual_custom_instructions(
            loan_vault=loan, hook_arguments=hook_arguments, denomination=denomination
        )
        if accrual_instructions:
            supervisee_pi_directives.update(
                {
                    loan.account_id: [
                        PostingInstructionsDirective(
                            posting_instructions=accrual_instructions,
                            value_datetime=hook_arguments.effective_datetime,
                        )
                    ]
                }
            )
            posting_instructions_by_supervisee.update({loan.account_id: accrual_instructions})
    if not supervisee_pi_directives:
        return supervisee_pi_directives
    midnight = hook_arguments.effective_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    balances_mapping = loc_vault.get_balances_timeseries()
    balances = utils_get_balance_default_dict_from_mapping(
        mapping=balances_mapping, effective_datetime=midnight
    )
    if interest_aggregate_custom_instructions := supervisor_utils_create_aggregate_posting_instructions(
        aggregate_account_id=loc_vault.account_id,
        posting_instructions_by_supervisee=posting_instructions_by_supervisee,
        prefix="TOTAL",
        balances=balances,
        addresses_to_aggregate=[
            lending_addresses_ACCRUED_INTEREST_RECEIVABLE,
            lending_addresses_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
            lending_addresses_PENALTIES,
        ],
        rounding_precision=_get_application_precision_parameter(loan_vaults=loan_vaults),
    ):
        supervisee_pi_directives.update(
            {
                loc_vault.account_id: [
                    PostingInstructionsDirective(
                        posting_instructions=interest_aggregate_custom_instructions,
                        client_batch_id=f"AGGREGATE_LOC_{LOC_ACCOUNT_TYPE}_INTEREST_ACCRUAL_{vault.get_hook_execution_id()}",
                        value_datetime=hook_arguments.effective_datetime,
                    )
                ]
            }
        )
    return supervisee_pi_directives


def _get_standard_interest_accrual_custom_instructions(
    vault: Any,
    hook_arguments: SupervisorScheduledEventHookArguments,
    next_due_amount_calculation_datetime: datetime,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    midnight = hook_arguments.effective_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    balances_mapping = vault.get_balances_timeseries()
    balances = utils_get_balance_default_dict_from_mapping(
        mapping=balances_mapping, effective_datetime=midnight
    )
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
    return interest_accrual_supervisor_daily_accrual_logic(
        vault=vault,
        hook_arguments=hook_arguments,
        next_due_amount_calculation_datetime=next_due_amount_calculation_datetime,
        account_type=DRAWDOWN_LOAN_ACCOUNT_TYPE,
        interest_rate_feature=FIXED_RATE_FEATURE,
        balances=balances,
        denomination=denomination,
    ) + overpayment_track_interest_on_expected_principal(
        vault=vault,
        hook_arguments=hook_arguments,
        interest_rate_feature=FIXED_RATE_FEATURE,
        balances=balances,
        denomination=denomination,
    )


def _get_penalty_interest_accrual_custom_instructions(
    loan_vault: Any,
    hook_arguments: SupervisorScheduledEventHookArguments,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Accrues penalty interest on the drawdown loan passed into the loan_vault argument
    based on the penality interest rate and the overdue amounts on the loan

    :param loan_vault: The loan to accrue penality interest on
    :param hook_arguments: The supervisor schedule event hook arguments
    :param denomination: The denomination of the loan
    :return: A list of penalty accrual custom instructions for the loan
    """
    midnight = hook_arguments.effective_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    balances = utils_get_balance_default_dict_from_mapping(
        mapping=loan_vault.get_balances_timeseries(), effective_datetime=midnight
    )
    if denomination is None:
        denomination = common_parameters_get_denomination_parameter(vault=loan_vault)
    penalty_interest_rate = _get_penalty_interest_rate_parameter(loan_vault=loan_vault)
    if _get_penalty_includes_base_rate_parameter(loan_vault=loan_vault):
        penalty_interest_rate += FIXED_RATE_FEATURE.get_annual_interest_rate(
            vault=loan_vault,
            effective_datetime=hook_arguments.effective_datetime,
            balances=balances,
            denomination=denomination,
        )
    penalties_internal_account = _get_penalty_interest_income_account_parameter(
        loan_vault=loan_vault
    )
    balance_to_accrue_on = utils_sum_balances(
        balances=balances,
        addresses=[lending_addresses_INTEREST_OVERDUE, lending_addresses_PRINCIPAL_OVERDUE],
        denomination=denomination,
    )
    return interest_accrual_common_daily_accrual(
        customer_account=loan_vault.account_id,
        customer_address=lending_addresses_PENALTIES,
        denomination=denomination,
        internal_account=penalties_internal_account,
        days_in_year=_get_days_in_year_parameter(loan_vault=loan_vault),
        yearly_rate=penalty_interest_rate,
        effective_balance=balance_to_accrue_on,
        account_type=DRAWDOWN_LOAN_ACCOUNT_TYPE,
        event_type=hook_arguments.event_type,
        effective_datetime=midnight,
        payable=False,
        precision=_get_application_precision_parameter(loan_vaults=[loan_vault]),
        rounding=ROUND_HALF_UP,
    )


def _get_due_amount_custom_instructions(
    hook_arguments: SupervisorScheduledEventHookArguments, loc_vault: Any, loan_vaults: list[Any]
) -> tuple[dict[str, list[PostingInstructionsDirective]], Decimal]:
    """
    Gets transfer due instructions for each loan supervisee and instructs the transfer
    due PIB for each loan. It also aggregates the due instructions across all loans
    and updates the Line of Credit supervisee total balances.
    Returns the total repayment amount across all loans in addition to the supervisee instructions.
    """
    supervisee_pi_directives: dict[str, list[PostingInstructionsDirective]] = {}
    denomination = common_parameters_get_denomination_parameter(vault=loc_vault)
    total_repayment_amount = Decimal("0")
    application_precision = _get_application_precision_parameter(loan_vaults=loan_vaults)
    instructions_for_aggregation: dict[str, list[CustomInstruction]] = {}
    supervisees_balances = supervisor_utils_get_balances_default_dicts_from_timeseries(
        supervisees=[loc_vault] + loan_vaults, effective_datetime=hook_arguments.effective_datetime
    )
    for loan_vault in loan_vaults:
        if (
            loan_vault.get_account_creation_datetime() + relativedelta(months=1)
        ).date() > hook_arguments.effective_datetime.date():
            continue
        loan_balances = supervisees_balances[loan_vault.account_id]
        application_feature = interest_application_supervisor_interest_application_interface
        supervisee_instructions = due_amount_calculation_supervisor_schedule_logic(
            loan_vault=loan_vault,
            main_vault=loc_vault,
            hook_arguments=hook_arguments,
            account_type=LOC_ACCOUNT_TYPE,
            interest_application_feature=application_feature,
            reamortisation_condition_features=[
                repayment_holiday_SupervisorReamortisationConditionWithoutPreference,
                overpayment_SupervisorOverpaymentReamortisationCondition,
            ],
            amortisation_feature=declining_principal_SupervisorAmortisationFeature,
            interest_rate_feature=FIXED_RATE_FEATURE,
            principal_adjustment_features=[overpayment_SupervisorOverpaymentPrincipalAdjustment],
            balances=loan_balances,
            denomination=denomination,
        )
        (elapsed_term, _) = declining_principal_supervisor_term_details(
            main_vault=loc_vault,
            loan_vault=loan_vault,
            effective_datetime=hook_arguments.effective_datetime,
            interest_rate=FIXED_RATE_FEATURE,
            balances=loan_balances,
        )
        previous_application_datetime = (
            due_amount_calculation_get_supervisee_last_execution_effective_datetime(
                main_vault=loc_vault,
                loan_vault=loan_vault,
                event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT,
                effective_datetime=hook_arguments.effective_datetime,
                elapsed_term=elapsed_term,
            )
        )
        supervisee_instructions += overpayment_track_emi_principal_excess(
            vault=loan_vault,
            interest_application_feature=application_feature,
            effective_datetime=hook_arguments.effective_datetime,
            previous_application_datetime=previous_application_datetime,
            balances=loan_balances,
            denomination=denomination,
        )
        supervisee_instructions += overpayment_reset_due_amount_calc_overpayment_trackers(
            vault=loan_vault,
            balances=supervisees_balances[loan_vault.account_id],
            denomination=denomination,
        )
        if supervisee_instructions:
            total_repayment_amount += _get_total_repayment_amount_for_loan(
                loan_account_id=loan_vault.account_id,
                custom_instructions=supervisee_instructions,
                denomination=denomination,
            )
            instructions_for_aggregation[loan_vault.account_id] = supervisee_instructions
            supervisee_pi_directives[loan_vault.account_id] = [
                PostingInstructionsDirective(
                    posting_instructions=supervisee_instructions,
                    value_datetime=hook_arguments.effective_datetime,
                    client_batch_id=f"{due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT}_{loan_vault.get_hook_execution_id()}",
                    batch_details={
                        "event": f"{due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT}"
                    },
                )
            ]
    loc_balances = supervisees_balances[loc_vault.account_id]
    if aggregated_instructions := supervisor_utils_create_aggregate_posting_instructions(
        aggregate_account_id=loc_vault.account_id,
        posting_instructions_by_supervisee=instructions_for_aggregation,
        prefix="TOTAL",
        balances=loc_balances,
        addresses_to_aggregate=[
            lending_addresses_PRINCIPAL,
            lending_addresses_PRINCIPAL_DUE,
            lending_addresses_INTEREST_DUE,
            lending_addresses_EMI,
            lending_addresses_ACCRUED_INTEREST_RECEIVABLE,
            lending_addresses_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
        ],
        rounding_precision=application_precision,
    ):
        supervisee_pi_directives[loc_vault.account_id] = [
            PostingInstructionsDirective(
                posting_instructions=aggregated_instructions,
                value_datetime=hook_arguments.effective_datetime,
                client_batch_id=f"{due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT}_{loc_vault.get_hook_execution_id()}",
                batch_details={"event": f"{due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT}"},
            )
        ]
    return (supervisee_pi_directives, total_repayment_amount)


def _get_total_repayment_amount_for_loan(
    loan_account_id: str, custom_instructions: list[CustomInstruction], denomination: str
) -> Decimal:
    """
    Sum the new due amounts from the repayment postings for a given draw down loan.
    The fetched balances themselves wouldn't reflect the latest changes.
    """
    return Decimal(
        sum(
            (
                utils_sum_balances(
                    balances=instruction.balances(account_id=loan_account_id, tside=Tside.ASSET),
                    addresses=[lending_addresses_PRINCIPAL_DUE, lending_addresses_INTEREST_DUE],
                    denomination=denomination,
                )
                for instruction in custom_instructions
            )
        )
    )


def _get_repayment_due_notification(
    loc_vault: Any, repayment_amount: Decimal, hook_arguments: SupervisorScheduledEventHookArguments
) -> dict[str, list[AccountNotificationDirective]]:
    """
    Generates an account notification for the monthly due amounts
    """
    repayment_period = _get_repayment_period_parameter(loc_vault=loc_vault)
    overdue_date = hook_arguments.effective_datetime + relativedelta(days=repayment_period)
    return {
        loc_vault.account_id: [
            AccountNotificationDirective(
                notification_type=REPAYMENT_DUE_NOTIFICATION,
                notification_details={
                    "account_id": loc_vault.account_id,
                    "repayment_amount": str(repayment_amount),
                    "overdue_date": str(overdue_date.date()),
                },
            )
        ]
    }


def _update_check_overdue_schedule(
    loc_vault: Any, hook_arguments: SupervisorScheduledEventHookArguments, skip: bool = False
) -> list[UpdatePlanEventTypeDirective]:
    """
    If skip is True, return a simple event update to skip the check overdue event.
    Otherwise, schedule the check overdue event according the repayment period number of days.
    """
    if skip:
        return [UpdatePlanEventTypeDirective(event_type=overdue_CHECK_OVERDUE_EVENT, skip=skip)]
    repayment_period = _get_repayment_period_parameter(loc_vault=loc_vault)
    overdue_date = hook_arguments.effective_datetime + relativedelta(days=repayment_period)
    return [
        UpdatePlanEventTypeDirective(
            event_type=overdue_CHECK_OVERDUE_EVENT,
            expression=utils_get_schedule_expression_from_parameters(
                vault=loc_vault, parameter_prefix=overdue_CHECK_OVERDUE_PREFIX, day=overdue_date.day
            ),
            skip=skip,
        )
    ]


def _update_check_delinquency_schedule(
    loc_vault: Any,
    hook_arguments: SupervisorScheduledEventHookArguments,
    grace_period: int,
    skip: bool = False,
) -> list[UpdatePlanEventTypeDirective]:
    """
    If skip is True, return a simple event update to skip the delinquency event.
    Otherwise, schedule the delinquency event according the grace period number of days.
    """
    if skip:
        return [
            UpdatePlanEventTypeDirective(event_type=delinquency_CHECK_DELINQUENCY_EVENT, skip=True)
        ]
    else:
        delinquency_date = hook_arguments.effective_datetime + relativedelta(days=grace_period)
        return [
            UpdatePlanEventTypeDirective(
                event_type=delinquency_CHECK_DELINQUENCY_EVENT,
                expression=utils_get_schedule_expression_from_parameters(
                    vault=loc_vault,
                    parameter_prefix=delinquency_CHECK_DELINQUENCY_PREFIX,
                    day=delinquency_date.day,
                ),
                skip=False,
            )
        ]


def _get_overdue_custom_instructions(
    hook_arguments: SupervisorScheduledEventHookArguments, loc_vault: Any, loan_vaults: list[Any]
) -> dict[str, list[PostingInstructionsDirective]]:
    """
    Gets overdue instructions for each loan supervisee and instructs the transfer overdue PIB
    for each loan. It also aggregates the overdue instructions across all loans and updates the
    Line of Credit supervisee total balances.
    """
    supervisee_pi_directives: dict[str, list[PostingInstructionsDirective]] = {}
    denomination = common_parameters_get_denomination_parameter(vault=loc_vault)
    application_precision = _get_application_precision_parameter(loan_vaults=loan_vaults)
    instructions_for_aggregation: dict[str, list[CustomInstruction]] = {}
    supervisees_balances = supervisor_utils_get_balances_default_dicts_from_timeseries(
        supervisees=[loc_vault] + loan_vaults, effective_datetime=hook_arguments.effective_datetime
    )
    for loan_vault in loan_vaults:
        loan_balances = supervisees_balances[loan_vault.account_id]
        (supervisee_instructions, _) = overdue_schedule_logic(
            vault=loan_vault,
            hook_arguments=hook_arguments,
            balances=loan_balances,
            account_type=LOC_ACCOUNT_TYPE,
        )
        if not supervisee_instructions:
            continue
        instructions_for_aggregation[loan_vault.account_id] = supervisee_instructions
        supervisee_pi_directives[loan_vault.account_id] = [
            PostingInstructionsDirective(
                posting_instructions=supervisee_instructions,
                value_datetime=hook_arguments.effective_datetime,
                client_batch_id=f"{hook_arguments.event_type}_{loan_vault.get_hook_execution_id()}",
                batch_details={"event": f"{hook_arguments.event_type}"},
            )
        ]
    if not instructions_for_aggregation:
        return {}
    loc_balances = supervisees_balances[loc_vault.account_id]
    if aggregated_instructions := supervisor_utils_create_aggregate_posting_instructions(
        aggregate_account_id=loc_vault.account_id,
        posting_instructions_by_supervisee=instructions_for_aggregation,
        prefix="TOTAL",
        balances=loc_balances,
        addresses_to_aggregate=[
            lending_addresses_PRINCIPAL_DUE,
            lending_addresses_PRINCIPAL_OVERDUE,
            lending_addresses_INTEREST_DUE,
            lending_addresses_INTEREST_OVERDUE,
        ],
        rounding_precision=application_precision,
    ):
        late_repayment_fee_instructions = late_repayment_schedule_logic(
            vault=loc_vault,
            hook_arguments=hook_arguments,
            denomination=denomination,
            account_type=LOC_ACCOUNT_TYPE,
            check_total_overdue_amount=False,
        )
        supervisee_pi_directives[loc_vault.account_id] = [
            PostingInstructionsDirective(
                posting_instructions=aggregated_instructions + late_repayment_fee_instructions,
                value_datetime=hook_arguments.effective_datetime,
                client_batch_id=f"{hook_arguments.event_type}_{loc_vault.get_hook_execution_id()}",
                batch_details={"event": f"{hook_arguments.event_type}"},
            )
        ]
    return supervisee_pi_directives


def _get_overdue_amounts_from_instructions(
    loc_account_id: str,
    instructions_directives: dict[str, list[PostingInstructionsDirective]],
    denomination: str,
) -> tuple[Decimal, Decimal]:
    """
    Sum the new principal and interest overdue amounts from a list of aggregated posting
    instructions. The fetched balances themselves wouldn't reflect the latest changes.
    """
    loc_posting_instructions = (
        instructions_directives[loc_account_id][0].posting_instructions
        if loc_account_id in instructions_directives
        else []
    )
    if not loc_posting_instructions:
        return (Decimal("0"), Decimal("0"))
    overdue_principal_amount = Decimal(
        sum(
            (
                utils_balance_at_coordinates(
                    balances=instruction.balances(account_id=loc_account_id, tside=Tside.ASSET),
                    address=f"TOTAL_{lending_addresses_PRINCIPAL_OVERDUE}",
                    denomination=denomination,
                )
                for instruction in loc_posting_instructions
            )
        )
    )
    overdue_interest_amount = Decimal(
        sum(
            (
                utils_balance_at_coordinates(
                    balances=instruction.balances(account_id=loc_account_id, tside=Tside.ASSET),
                    address=f"TOTAL_{lending_addresses_INTEREST_OVERDUE}",
                    denomination=denomination,
                )
                for instruction in loc_posting_instructions
            )
        )
    )
    return (overdue_principal_amount, overdue_interest_amount)


def _handle_delinquency(
    hook_arguments: SupervisorScheduledEventHookArguments, loc_vault: Any, loan_vaults: list[Any]
) -> dict[str, list[AccountNotificationDirective]]:
    """
    A Line of Credit is considered delinquent if any of the loans have overdue amounts for a
    duration beyond grace period. Here we check any of the loans to see if they still have an
    overdue balance, and return the delinquency notification if so. No further action is needed
    in the contract, as this would reside within downstream services that would consume this
    notification.
    """
    denomination = common_parameters_get_denomination_parameter(vault=loc_vault)
    for loan_vault in loan_vaults:
        loan_vault_balances = utils_get_balance_default_dict_from_mapping(
            mapping=loan_vault.get_balances_timeseries(),
            effective_datetime=hook_arguments.effective_datetime,
        )
        if utils_sum_balances(
            balances=loan_vault_balances,
            addresses=lending_addresses_OVERDUE_ADDRESSES,
            denomination=denomination,
        ) > Decimal("0"):
            return {
                loc_vault.account_id: _get_delinquency_notification(account_id=loc_vault.account_id)
            }
    return {}


def _get_delinquency_notification(account_id: str) -> list[AccountNotificationDirective]:
    return [
        AccountNotificationDirective(
            notification_type=DELINQUENT_NOTIFICATION,
            notification_details={"account_id": account_id},
        )
    ]


def _get_loc_and_loan_supervisee_vault_objects(vault: Any) -> tuple[Optional[Any], list[Any]]:
    loc_vault = _get_loc_vault(vault=vault)
    loan_vaults = supervisor_utils_get_supervisees_for_alias(vault=vault, alias=DRAWDOWN_LOAN_ALIAS)
    return (loc_vault, loan_vaults)


def _get_loc_vault(vault: Any) -> Optional[Any]:
    supervisees = supervisor_utils_get_supervisees_for_alias(vault=vault, alias=LOC_ALIAS)
    return supervisees[0] if len(supervisees) == 1 else None


def _get_paid_off_loans_notification(
    repayment_custom_instructions_per_loan: dict[str, list[CustomInstruction]],
    balances_per_target: dict[str, BalanceDefaultDict],
    denomination: str,
) -> list[AccountNotificationDirective]:
    """
    Given the repayment custom instructions per loan, this function calculates which drawdown
    loans have been fully paid and returns a notification directive with the ids of those drawdown
    loans.

    This function assumes that the custom instructions provided are only for drawdown loan (i.e.
    not the line of credit account).

    :param repayment_custom_instructions_per_loan: the repayment custom instructions for each loan.
    :param balances_per_target: the balances before repayment for each loan.
    :param denomination: the denomination of the repayments.
    :return: a list containing one notification directive with the ids of the paid off drawdown
    loans, or an empty list if no loans have been repaid.
    """
    paid_off_loans_ids: list[str] = []
    for (loan_account_id, repayment_instructions) in repayment_custom_instructions_per_loan.items():
        if close_loan_does_repayment_fully_repay_loan(
            repayment_posting_instructions=repayment_instructions,
            balances=balances_per_target[loan_account_id],
            denomination=denomination,
            account_id=loan_account_id,
            debt_addresses=lending_addresses_ALL_OUTSTANDING_SUPERVISOR,
            payment_addresses=lending_addresses_ALL_OUTSTANDING_SUPERVISOR,
        ):
            paid_off_loans_ids.append(loan_account_id)
    if paid_off_loans_ids:
        return [
            AccountNotificationDirective(
                notification_type=LOANS_PAID_OFF_NOTIFICATION,
                notification_details={"account_ids": dumps(paid_off_loans_ids)},
            )
        ]
    return []


def _handle_due_amount_calculation_day_change(
    loc_vault: Any, hook_arguments: SupervisorScheduledEventHookArguments
) -> tuple[list[UpdatePlanEventTypeDirective], dict[str, list[UpdateAccountEventTypeDirective]]]:
    """
    Check whether due amount calculation day has changed and determine how to handle associated
    schedule updates of the due amount calculation event.
    Since post_parameter_change_hook is not available in the supervisor we handle this within the
    accrual event, which runs daily and will handle a changed parameter within a day after it was
    changed.
    We need to guarantee the due calculation event runs exactly once per calendar month.
    If changing the schedule now would result in the due calc event being missed this month,
    then do nothing here, as this will be handled within the next due calc event execution.
    For example if the today is the 15th, but the event has not yet happened this month, and the day
    is changed to the 10th.
    :param loc_vault: the vault object of the Line of Credit account
    :param hook_arguments: the supervisor scheduled event hook arguments
    :return a tuple for the due amount calculation event updates, containing:
        - a list of schedule update directives for the supervisor plan, which will either be an
        empty list for no updates, or a single directive.
        - a mirror of the schedule update directive for the supervisor plan, but for the dummy event
         that runs on the Line of Credit account. This is a dict where the key is the account ID and
         the value is the directive.
    """
    last_execution_datetime = loc_vault.get_last_execution_datetime(
        event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
    )
    param_timeseries = loc_vault.get_parameter_timeseries(
        name=due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY
    ).all()
    if not last_execution_datetime or len(param_timeseries) == 1:
        return ([], {})
    latest_param_update_datetime = param_timeseries[-1].at_datetime
    latest_due_amount_calculation_day = param_timeseries[-1].value
    if latest_param_update_datetime <= last_execution_datetime:
        return ([], {})
    next_due_calc_datetime = due_amount_calculation_get_next_due_amount_calculation_datetime(
        vault=loc_vault,
        effective_datetime=hook_arguments.effective_datetime,
        elapsed_term=1,
        remaining_term=1,
    )
    if next_due_calc_datetime != last_execution_datetime + relativedelta(months=1):
        return _update_due_amount_calculation_day_schedule(
            loc_vault=loc_vault,
            schedule_start_datetime=next_due_calc_datetime,
            due_amount_calculation_day=latest_due_amount_calculation_day,
        )
    return ([], {})


def _update_due_amount_calculation_day_schedule(
    loc_vault: Any, schedule_start_datetime: datetime, due_amount_calculation_day: int
) -> tuple[list[UpdatePlanEventTypeDirective], dict[str, list[UpdateAccountEventTypeDirective]]]:
    """
    Create event update directives for the due amount calculation event for both the plan schedule
    and the line of credit account schedule. The latter is a dummy event which is only used to
    enable the last execution datetime to be used by the supervisor.
    """
    end_of_month_schedule = utils_get_end_of_month_schedule_from_parameters(
        vault=loc_vault,
        parameter_prefix=due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX,
        day=due_amount_calculation_day,
    )
    schedule_skip = ScheduleSkip(end=schedule_start_datetime - relativedelta(seconds=1))
    return (
        [
            UpdatePlanEventTypeDirective(
                event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT,
                schedule_method=end_of_month_schedule,
                skip=schedule_skip,
            )
        ],
        {
            loc_vault.account_id: [
                UpdateAccountEventTypeDirective(
                    event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT,
                    schedule_method=end_of_month_schedule,
                    skip=schedule_skip,
                )
            ]
        },
    )


def _update_due_amount_calculation_counters(
    loan_vaults: list[Any], hook_arguments: SupervisorScheduledEventHookArguments, denomination: str
) -> dict[str, list[PostingInstructionsDirective]]:
    """
    Updates the counter of number of due amount calculation events which is used to
    calculate the elapsed term
    Intended to be used during a repayment holiday as this is already accounted for
    during normal due amount calculation
    """
    supervisee_pi_directives = {}
    for loan_vault in loan_vaults:
        counter_update_ci = [
            CustomInstruction(
                postings=due_amount_calculation_update_due_amount_calculation_counter(
                    account_id=loan_vault.account_id, denomination=denomination
                ),
                instruction_details=utils_standard_instruction_details(
                    description="Updating due amount calculation counter",
                    event_type=hook_arguments.event_type,
                    gl_impacted=False,
                    account_type=DRAWDOWN_LOAN_ACCOUNT_TYPE,
                ),
                override_all_restrictions=True,
            )
        ]
        supervisee_pi_directives.update(
            {
                loan_vault.account_id: [
                    PostingInstructionsDirective(
                        posting_instructions=counter_update_ci,
                        value_datetime=hook_arguments.effective_datetime,
                    )
                ]
            }
        )
    return supervisee_pi_directives


def _get_application_precision_parameter(
    *, loan_vaults: list[Any], effective_datetime: Optional[datetime] = None
) -> int:
    return (
        int(
            utils_get_parameter(
                vault=loan_vaults[0],
                name=interest_application_PARAM_APPLICATION_PRECISION,
                at_datetime=effective_datetime,
            )
        )
        if loan_vaults
        else 2
    )


def _get_days_in_year_parameter(
    *, loan_vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    return utils_get_parameter(
        vault=loan_vault,
        name=interest_accrual_common_PARAM_DAYS_IN_YEAR,
        at_datetime=effective_datetime,
    )


def _get_penalty_includes_base_rate_parameter(
    *, loan_vault: Any, effective_datetime: Optional[datetime] = None
) -> bool:
    return utils_get_parameter(
        vault=loan_vault,
        name=drawdown_loan_PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE,
        is_boolean=True,
        at_datetime=effective_datetime,
    )


def _get_penalty_interest_income_account_parameter(
    *, loan_vault: Any, effective_datetime: Optional[datetime] = None
) -> str:
    return utils_get_parameter(
        vault=loan_vault,
        name=drawdown_loan_PARAM_PENALTY_INTEREST_INCOME_ACCOUNT,
        at_datetime=effective_datetime,
    )


def _get_penalty_interest_rate_parameter(
    *, loan_vault: Any, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return utils_get_parameter(
        vault=loan_vault,
        name=drawdown_loan_PARAM_PENALTY_INTEREST_RATE,
        at_datetime=effective_datetime,
    )


def _get_repayment_period_parameter(
    *, loc_vault: Any, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils_get_parameter(
            vault=loc_vault, name=overdue_PARAM_REPAYMENT_PERIOD, at_datetime=effective_datetime
        )
    )


def _get_due_amount_calculation_day_parameter(
    *, loc_vault: Any, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils_get_parameter(
            vault=loc_vault,
            name=due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY,
            at_datetime=effective_datetime,
        )
    )
