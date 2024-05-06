# Code auto-generated using Inception Smart Contract Renderer Version 2.0.1


# Objects below have been imported from:
#    line_of_credit.py
# md5:06d08acc879c2c1282a60675115a0c46

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
    SmartContractEventType,
    DateShape,
    ScheduledEventHookArguments,
    AccountIdShape,
    OptionalShape,
    BalancesFilter,
    BalancesObservation,
    StringShape,
    ActivationHookArguments,
    ActivationHookResult,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    PreParameterChangeHookArguments,
    PreParameterChangeHookResult,
    PrePostingHookArguments,
    PrePostingHookResult,
    fetch_account_data,
    requires,
)
from calendar import isleap
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
from json import loads, dumps
from typing import Optional, Any, Iterable, Mapping, Union, Callable, NamedTuple
from zoneinfo import ZoneInfo

api = "4.0.0"
version = "2.0.1"
display_name = "Line of Credit"
tside = Tside.ASSET
supported_denominations = ["GBP"]


@requires(parameters=True)
def activation_hook(
    vault: Any, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    return ActivationHookResult(
        scheduled_events_return_value=due_amount_calculation_scheduled_events(
            vault=vault, account_opening_datetime=hook_arguments.effective_datetime
        )
    )


@fetch_account_data(balances=["EFFECTIVE_FETCHER"])
@requires(last_execution_datetime=["DUE_AMOUNT_CALCULATION"], parameters=True)
def derived_parameter_hook(
    vault: Any, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    last_execution_datetime = vault.get_last_execution_datetime(
        event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
    )
    next_due_calc_datetime = due_amount_calculation_get_actual_next_repayment_date(
        vault=vault,
        effective_datetime=hook_arguments.effective_datetime,
        elapsed_term=1 if last_execution_datetime else 0,
        remaining_term=1,
    )
    total_outstanding_principal = _get_total_outstanding_principal(
        denomination=denomination, balances=balances
    )
    derived_parameters: dict[str, utils_ParameterValueTypeAlias] = {
        PARAM_TOTAL_ARREARS_AMOUNT: _get_total_arrears_amount(
            denomination=denomination, balances=balances
        ),
        early_repayment_PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT: _get_total_early_repayment_amount(
            vault=vault, denomination=denomination, balances=balances
        ),
        PARAM_TOTAL_MONTHLY_REPAYMENT_AMOUNT: _get_total_monthly_repayment_amount(
            denomination=denomination, balances=balances
        ),
        PARAM_TOTAL_ORIGINAL_PRINCIPAL: _get_total_original_principal(
            denomination=denomination, balances=balances
        ),
        PARAM_TOTAL_OUTSTANDING_DUE_AMOUNT: _get_total_outstanding_due_amount(
            denomination=denomination, balances=balances
        ),
        PARAM_TOTAL_OUTSTANDING_PRINCIPAL: total_outstanding_principal,
        PARAM_TOTAL_AVAILABLE_CREDIT: _get_total_available_credit(
            vault=vault, total_outstanding_principal=total_outstanding_principal
        ),
        due_amount_calculation_PARAM_NEXT_REPAYMENT_DATE: next_due_calc_datetime,
    }
    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


@fetch_account_data(balances=["live_balances_bof"])
@requires(flags=True, last_execution_datetime=["DUE_AMOUNT_CALCULATION"], parameters=True)
def pre_parameter_change_hook(
    vault: Any, hook_arguments: PreParameterChangeHookArguments
) -> Optional[PreParameterChangeHookResult]:
    updated_parameter_values: dict[
        str, utils_ParameterValueTypeAlias
    ] = hook_arguments.updated_parameter_values
    if credit_limit_PARAM_CREDIT_LIMIT in updated_parameter_values:
        if rejection := credit_limit_validate_credit_limit_parameter_change(
            vault=vault,
            proposed_credit_limit=updated_parameter_values[credit_limit_PARAM_CREDIT_LIMIT],
            principal_addresses=[f"TOTAL_{address}" for address in lending_addresses_ALL_PRINCIPAL],
        ):
            return PreParameterChangeHookResult(rejection=rejection)
    if due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY in updated_parameter_values:
        if rejection := due_amount_calculation_validate_due_amount_calculation_day_change(
            vault=vault
        ):
            return PreParameterChangeHookResult(rejection=rejection)
    return None


@requires(parameters=True, flags=True)
def pre_posting_hook(
    vault: Any, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    posting_instructions = hook_arguments.posting_instructions
    if utils_is_force_override(posting_instructions=posting_instructions):
        return None
    if posting_rejection := utils_validate_single_hard_settlement_or_transfer(
        posting_instructions=posting_instructions
    ):
        return PrePostingHookResult(rejection=posting_rejection)
    posting_instruction = posting_instructions[0]
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    if denomination_rejection := utils_validate_denomination(
        posting_instructions=posting_instructions, accepted_denominations=[denomination]
    ):
        return PrePostingHookResult(rejection=denomination_rejection)
    posting_amount = utils_get_available_balance(
        balances=posting_instruction.balances(), denomination=denomination
    )
    if posting_rejection := utils_validate_amount_precision(amount=posting_amount):
        return PrePostingHookResult(rejection=posting_rejection)
    if posting_amount <= 0:
        if repayment_holiday_is_repayment_blocked(
            vault=vault, effective_datetime=hook_arguments.effective_datetime
        ):
            return PrePostingHookResult(
                rejection=Rejection(
                    message="Repayments blocked for this account",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
    else:
        if rejection := minimum_loan_principal_validate(
            vault=vault, posting_instruction=posting_instruction
        ):
            return PrePostingHookResult(rejection=rejection)
        if rejection := maximum_loan_principal_validate(
            vault=vault, posting_instruction=posting_instruction
        ):
            return PrePostingHookResult(rejection=rejection)
        pass
    return None


def scheduled_event_hook(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
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


def utils_validate_amount_precision(amount: Decimal, max_precision: int = 2) -> Optional[Rejection]:
    """
    Return a Rejection if the amount has non-zero digits after the specified number of
    decimal places
    :param amount: the amount to check
    :param max_precision: the max integer number of non-zero decimal places
    :return Rejection: when amount has non-zero digits after max_precision decimal places
    """
    if utils_round_decimal(amount, max_precision) != amount:
        return Rejection(
            message=f"Amount {amount} has non-zero digits after {max_precision} decimal places",
            reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
        )
    return None


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

fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID = "EFFECTIVE_FETCHER"
fetchers_EFFECTIVE_OBSERVATION_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID, at=DefinedDateTime.EFFECTIVE_DATETIME
)
fetchers_LIVE_BALANCES_BOF_ID = "live_balances_bof"
fetchers_LIVE_BALANCES_BOF = BalancesObservationFetcher(
    fetcher_id=fetchers_LIVE_BALANCES_BOF_ID, at=DefinedDateTime.LIVE
)

# Objects below have been imported from:
#    addresses.py
# md5:860f50af37f2fe98540f540fa6394eb7

addresses_PENALTIES = "PENALTIES"

# Objects below have been imported from:
#    lending_addresses.py
# md5:d546448643732336308da8f52c0901d4

lending_addresses_ACCRUED_INTEREST_RECEIVABLE = "ACCRUED_INTEREST_RECEIVABLE"
lending_addresses_EMI = "EMI"
lending_addresses_INTEREST_DUE = "INTEREST_DUE"
lending_addresses_INTEREST_OVERDUE = "INTEREST_OVERDUE"
lending_addresses_NON_EMI_ACCRUED_INTEREST_RECEIVABLE = "NON_EMI_ACCRUED_INTEREST_RECEIVABLE"
lending_addresses_PENALTIES = addresses_PENALTIES
lending_addresses_PRINCIPAL = "PRINCIPAL"
lending_addresses_PRINCIPAL_DUE = "PRINCIPAL_DUE"
lending_addresses_PRINCIPAL_OVERDUE = "PRINCIPAL_OVERDUE"
lending_addresses_ALL_PRINCIPAL = (
    [lending_addresses_PRINCIPAL]
    + [lending_addresses_PRINCIPAL_DUE]
    + [lending_addresses_PRINCIPAL_OVERDUE]
)

# Objects below have been imported from:
#    credit_limit.py
# md5:06cc025017d33083dafbee6058c4d1f7

credit_limit_PARAM_CREDIT_LIMIT = "credit_limit"
credit_limit_PARAM_CREDIT_LIMIT_APPLICABLE_PRINCIPAL = "credit_limit_applicable_principal"
credit_limit_PARAM_DENOMINATION = "denomination"
credit_limit_CREDIT_LIMIT_ORIGINAL = "original"
credit_limit_CREDIT_LIMIT_OUTSTANDING = "outstanding"
credit_limit_parameters = [
    Parameter(
        name=credit_limit_PARAM_CREDIT_LIMIT,
        level=ParameterLevel.INSTANCE,
        description="Maximum credit limit available to the customer",
        display_name="Customer Credit Limit",
        shape=NumberShape(min_value=Decimal("0")),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=Decimal("1000"),
    ),
    Parameter(
        name=credit_limit_PARAM_CREDIT_LIMIT_APPLICABLE_PRINCIPAL,
        shape=UnionShape(
            items=[
                UnionItem(key=credit_limit_CREDIT_LIMIT_ORIGINAL, display_name="Original"),
                UnionItem(key=credit_limit_CREDIT_LIMIT_OUTSTANDING, display_name="Outstanding"),
            ]
        ),
        level=ParameterLevel.TEMPLATE,
        description="Defines whether the available credit limit is calculated using the original or outstanding principal for all open loans.",
        display_name="Available Credit Limit Definition",
        default_value=UnionItemValue(key=credit_limit_CREDIT_LIMIT_OUTSTANDING),
    ),
]


def credit_limit__get_denomination_parameter(vault: Union[Any, Any]) -> str:
    denomination: str = utils_get_parameter(vault=vault, name=credit_limit_PARAM_DENOMINATION)
    return denomination


def credit_limit_validate_credit_limit_parameter_change(
    vault: Union[Any, Any],
    proposed_credit_limit: Decimal,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    principal_addresses: list[str] = lending_addresses_ALL_PRINCIPAL,
) -> Optional[Rejection]:
    """
    Returns a rejection if the proposed credit limit is below the total
    outstanding principal

    :param vault: The vault object containing the live balances to use in the validation
    :param proposed_credit_limit: The new proposed credit limit
    :param balances: The balances used to determine the total outstanding principal
    :param denomination: The denomination of the account
    :param principal_addresses: The addresses that contain all the outstanding principal
    :return: A rejection if the proposed credit limit is invalid, otherwise None
    """
    if not balances:
        balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    if not denomination:
        denomination = credit_limit__get_denomination_parameter(vault=vault)
    total_outstanding_principal = utils_sum_balances(
        balances=balances, denomination=denomination, addresses=principal_addresses
    )
    if proposed_credit_limit < total_outstanding_principal:
        return Rejection(
            message=f"Cannot set proposed credit limit {proposed_credit_limit} to a value below the total outstanding debt of {total_outstanding_principal}",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


# Objects below have been imported from:
#    delinquency.py
# md5:b99b0ef48bb663761488c57823bac9f4

delinquency_CHECK_DELINQUENCY_PREFIX = "check_delinquency"
delinquency_PARAM_CHECK_DELINQUENCY_HOUR = f"{delinquency_CHECK_DELINQUENCY_PREFIX}_hour"
delinquency_PARAM_CHECK_DELINQUENCY_MINUTE = f"{delinquency_CHECK_DELINQUENCY_PREFIX}_minute"
delinquency_PARAM_CHECK_DELINQUENCY_SECOND = f"{delinquency_CHECK_DELINQUENCY_PREFIX}_second"
delinquency_PARAM_GRACE_PERIOD = "grace_period"
delinquency_schedule_parameters = [
    Parameter(
        name=delinquency_PARAM_GRACE_PERIOD,
        shape=NumberShape(max_value=27, min_value=0, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The number of days after which the account becomes delinquent.",
        display_name="Grace Period (days)",
        default_value=Decimal(15),
    ),
    Parameter(
        name=delinquency_PARAM_CHECK_DELINQUENCY_HOUR,
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which delinquency is checked.",
        display_name="Check Delinquency Hour",
        default_value=0,
    ),
    Parameter(
        name=delinquency_PARAM_CHECK_DELINQUENCY_MINUTE,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The minute of the day at which delinquency is checked.",
        display_name="Check Delinquency Minute",
        default_value=0,
    ),
    Parameter(
        name=delinquency_PARAM_CHECK_DELINQUENCY_SECOND,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The second of the day at which delinquency is checked.",
        display_name="Check Delinquency Second",
        default_value=2,
    ),
]

# Objects below have been imported from:
#    due_amount_calculation.py
# md5:764e3e5a69ae8c7f97be1c0a65a16ddf

due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT = "DUE_AMOUNT_CALCULATION"
due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX = "due_amount_calculation"
due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_HOUR = (
    f"{due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX}_hour"
)
due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_MINUTE = (
    f"{due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX}_minute"
)
due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_SECOND = (
    f"{due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX}_second"
)
due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY = "due_amount_calculation_day"
due_amount_calculation_PARAM_NEXT_REPAYMENT_DATE = "next_repayment_date"
due_amount_calculation_due_amount_calculation_day_parameter = Parameter(
    name=due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY,
    shape=NumberShape(min_value=1, max_value=31, step=1),
    level=ParameterLevel.INSTANCE,
    description="The day of the month that the monthly due amount calculations takes place on. If the day isn't available in a given month, the previous available day is used instead",
    display_name="Due Amount Calculation Day",
    default_value=Decimal(28),
    update_permission=ParameterUpdatePermission.USER_EDITABLE,
)
due_amount_calculation_next_repayment_date_parameter = Parameter(
    name=due_amount_calculation_PARAM_NEXT_REPAYMENT_DATE,
    shape=DateShape(
        min_date=datetime.min.replace(tzinfo=ZoneInfo("UTC")),
        max_date=datetime.max.replace(tzinfo=ZoneInfo("UTC")),
    ),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Next scheduled repayment date",
    display_name="Next Repayment Date",
)
due_amount_calculation_schedule_time_parameters = [
    Parameter(
        name=due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which due amounts are calculated.",
        display_name="Due Amount Calculation Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which due amounts are calculated.",
        display_name="Due Amount Calculation Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which due amounts are calculated.",
        display_name="Due Amount Calculation Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
]
due_amount_calculation_schedule_parameters = [
    due_amount_calculation_due_amount_calculation_day_parameter,
    *due_amount_calculation_schedule_time_parameters,
]


def due_amount_calculation_event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT}_AST"
            ],
        )
    ]


def due_amount_calculation_scheduled_events(
    vault: Any, account_opening_datetime: datetime
) -> dict[str, ScheduledEvent]:
    """
    Create monthly scheduled event for due amount calculation, starting one month from account
    opening
    :param vault: vault object for the account that requires the schedule
    :param account_opening_datetime: when the account is opened/activated
    :return: event type to scheduled event
    """
    return {
        due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT: utils_monthly_scheduled_event(
            vault=vault,
            start_datetime=account_opening_datetime
            + relativedelta(hour=0, minute=0, second=0)
            + relativedelta(months=1),
            parameter_prefix=due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX,
        )
    }


def due_amount_calculation_validate_due_amount_calculation_day_change(
    vault: Any,
) -> Optional[Rejection]:
    last_execution_datetime = vault.get_last_execution_datetime(
        event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
    )
    if last_execution_datetime is None:
        return Rejection(
            message="It is not possible to change the monthly repayment day if the first repayment date has not passed.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


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


# Objects below have been imported from:
#    early_repayment.py
# md5:f999fa0e14d31eabc867091bfbd3904d

early_repayment_PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT = "total_early_repayment_amount"
early_repayment_total_early_repayment_amount_parameter = Parameter(
    name=early_repayment_PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
    shape=NumberShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Total early repayment amount required to fully repay and close the account",
    display_name="Total Early Repayment Amount",
)

# Objects below have been imported from:
#    interest_accrual_common.py
# md5:162f41e06e859ca63b416be0f14ea285

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

# Objects below have been imported from:
#    interest_accrual.py
# md5:07236706e076b2c0568b51146520a313

interest_accrual_schedule_parameters = interest_accrual_common_schedule_parameters

# Objects below have been imported from:
#    late_repayment.py
# md5:626b94d9efd00829169cb818da10c167

late_repayment_PARAM_LATE_REPAYMENT_FEE = "late_repayment_fee"
late_repayment_PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "late_repayment_fee_income_account"
late_repayment_fee_parameters = [
    Parameter(
        name=late_repayment_PARAM_LATE_REPAYMENT_FEE,
        shape=NumberShape(min_value=Decimal("0")),
        level=ParameterLevel.TEMPLATE,
        description="Fee to apply due to late repayment.",
        display_name="Late Repayment Fee",
        default_value=Decimal("25"),
    ),
    Parameter(
        name=late_repayment_PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for late repayment fee income balance.",
        display_name="Late Repayment Fee Income Account",
        shape=AccountIdShape(),
        default_value="LATE_REPAYMENT_FEE_INCOME",
    ),
]

# Objects below have been imported from:
#    maximum_loan_principal.py
# md5:41816a4fec212dd558a485b2b7121d71

maximum_loan_principal_PARAM_MAXIMUM_LOAN_PRINCIPAL = "maximum_loan_principal"
maximum_loan_principal_parameters = [
    Parameter(
        name=maximum_loan_principal_PARAM_MAXIMUM_LOAN_PRINCIPAL,
        shape=OptionalShape(shape=NumberShape(min_value=Decimal("0"))),
        level=ParameterLevel.TEMPLATE,
        description="The maximum principal amount for each loan.",
        display_name="Maximum Loan Principal",
        default_value=OptionalValue(Decimal("1000")),
    )
]


def maximum_loan_principal_validate(
    vault: Any, posting_instruction: utils_PostingInstructionTypeAlias
) -> Optional[Rejection]:
    if maximum_loan_amount := utils_get_parameter(
        vault=vault, name=maximum_loan_principal_PARAM_MAXIMUM_LOAN_PRINCIPAL, is_optional=True
    ):
        denomination = utils_get_parameter(vault=vault, name="denomination")
        posting_amount = utils_get_available_balance(
            balances=posting_instruction.balances(), denomination=denomination
        )
        if posting_amount > maximum_loan_amount:
            return Rejection(
                message=f"Cannot create loan larger than maximum loan amount limit of: {maximum_loan_amount}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
    return None


# Objects below have been imported from:
#    maximum_outstanding_loans.py
# md5:157347f1b1a3437252b5c24436767f95

maximum_outstanding_loans_PARAM_MAXIMUM_NUMBER_OF_OUTSTANDING_LOANS = (
    "maximum_number_of_outstanding_loans"
)
maximum_outstanding_loans_parameters = [
    Parameter(
        name=maximum_outstanding_loans_PARAM_MAXIMUM_NUMBER_OF_OUTSTANDING_LOANS,
        shape=NumberShape(min_value=1, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The maximum number of loans allowed to be open concurrently.",
        display_name="Maximum Number Of Outstanding Loans.",
        default_value=1,
    )
]

# Objects below have been imported from:
#    minimum_loan_principal.py
# md5:dc8def658f5d772ce9ca6da0d167550a

minimum_loan_principal_PARAM_MINIMUM_LOAN_PRINCIPAL = "minimum_loan_principal"
minimum_loan_principal_parameters = [
    Parameter(
        name=minimum_loan_principal_PARAM_MINIMUM_LOAN_PRINCIPAL,
        shape=OptionalShape(shape=NumberShape(min_value=Decimal("0"))),
        level=ParameterLevel.TEMPLATE,
        description="The minimum principal amount for each loan.",
        display_name="Minimum Loan Principal",
        default_value=OptionalValue(Decimal("50")),
    )
]


def minimum_loan_principal_validate(
    vault: Any, posting_instruction: utils_PostingInstructionTypeAlias
) -> Optional[Rejection]:
    if minimum_loan_amount := utils_get_parameter(
        vault=vault, name=minimum_loan_principal_PARAM_MINIMUM_LOAN_PRINCIPAL, is_optional=True
    ):
        denomination = utils_get_parameter(vault=vault, name="denomination")
        posting_amount = utils_get_available_balance(
            balances=posting_instruction.balances(), denomination=denomination
        )
        if 0 < posting_amount < minimum_loan_amount:
            return Rejection(
                message=f"Cannot create loan smaller than minimum loan amount limit of: {minimum_loan_amount}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
    return None


# Objects below have been imported from:
#    overdue.py
# md5:11cacf1a6c91093b7cdfbea3281b9f19

overdue_CHECK_OVERDUE_PREFIX = "check_overdue"
overdue_PARAM_CHECK_OVERDUE_HOUR = f"{overdue_CHECK_OVERDUE_PREFIX}_hour"
overdue_PARAM_CHECK_OVERDUE_MINUTE = f"{overdue_CHECK_OVERDUE_PREFIX}_minute"
overdue_PARAM_CHECK_OVERDUE_SECOND = f"{overdue_CHECK_OVERDUE_PREFIX}_second"
overdue_PARAM_REPAYMENT_PERIOD = "repayment_period"
overdue_schedule_parameters = [
    Parameter(
        name=overdue_PARAM_CHECK_OVERDUE_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which overdue is checked.",
        display_name="Check Overdue Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=overdue_PARAM_CHECK_OVERDUE_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which overdue is checked.",
        display_name="Check Overdue Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=overdue_PARAM_CHECK_OVERDUE_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which overdue is checked.",
        display_name="Check Overdue Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=overdue_PARAM_REPAYMENT_PERIOD,
        level=ParameterLevel.TEMPLATE,
        description="The number of days after which due amounts are made overdue.",
        display_name="Repayment Period (Days)",
        shape=NumberShape(min_value=1, max_value=27, step=1),
        default_value=1,
    ),
]

# Objects below have been imported from:
#    overpayment.py
# md5:a8cb4d2f6f955706d1b72f5c93822334

overpayment_REDUCE_EMI = "reduce_emi"
overpayment_REDUCE_TERM = "reduce_term"
overpayment_PARAM_OVERPAYMENT_FEE_RATE = "overpayment_fee_rate"
overpayment_PARAM_OVERPAYMENT_FEE_INCOME_ACCOUNT = "overpayment_fee_income_account"
overpayment_PARAM_OVERPAYMENT_IMPACT_PREFERENCE = "overpayment_impact_preference"
overpayment_overpayment_fee_rate_param = Parameter(
    name=overpayment_PARAM_OVERPAYMENT_FEE_RATE,
    shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1"), step=Decimal("0.0001")),
    level=ParameterLevel.TEMPLATE,
    description="Percentage fee charged on the overpayment amount.",
    display_name="Overpayment Fee Rate",
    default_value=Decimal("0.05"),
)
overpayment_overpayment_fee_income_account_param = Parameter(
    name=overpayment_PARAM_OVERPAYMENT_FEE_INCOME_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for overpayment fee income balance.",
    display_name="Overpayment Fee Income Account",
    shape=AccountIdShape(),
    default_value="OVERPAYMENT_FEE_INCOME",
)
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


def overpayment_get_overpayment_fee_rate_parameter(vault: Any) -> Decimal:
    overpayment_fee_rate: Decimal = utils_get_parameter(
        vault=vault, name=overpayment_PARAM_OVERPAYMENT_FEE_RATE
    )
    return overpayment_fee_rate


# Objects below have been imported from:
#    repayment_holiday.py
# md5:8ab69326d0731879f6300743f6dbefd4

repayment_holiday_REPAYMENT_HOLIDAY = "REPAYMENT_HOLIDAY"
repayment_holiday_PARAM_DELINQUENCY_BLOCKING_FLAGS = "delinquency_blocking_flags"
repayment_holiday_PARAM_DUE_AMOUNT_CALCULATION_BLOCKING_FLAGS = (
    "due_amount_calculation_blocking_flags"
)
repayment_holiday_PARAM_INTEREST_ACCRUAL_BLOCKING_FLAGS = "interest_accrual_blocking_flags"
repayment_holiday_PARAM_NOTIFICATION_BLOCKING_FLAGS = "notification_blocking_flags"
repayment_holiday_PARAM_OVERDUE_AMOUNT_CALCULATION_BLOCKING_FLAGS = (
    "overdue_amount_calculation_blocking_flags"
)
repayment_holiday_PARAM_PENALTY_BLOCKING_FLAGS = "penalty_blocking_flags"
repayment_holiday_PARAM_REPAYMENT_BLOCKING_FLAGS = "repayment_blocking_flags"
repayment_holiday_delinquency_blocking_param = Parameter(
    name=repayment_holiday_PARAM_DELINQUENCY_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block an account becoming delinquent. Expects a string representation of a JSON list.",
    display_name="Delinquency Blocking Flags",
    default_value=dumps([repayment_holiday_REPAYMENT_HOLIDAY]),
)
repayment_holiday_due_amount_calculation_blocking_param = Parameter(
    name=repayment_holiday_PARAM_DUE_AMOUNT_CALCULATION_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block due amount calculation. Expects a string representation of a JSON list.",
    display_name="Due Amount Calculation Blocking Flags",
    default_value=dumps([repayment_holiday_REPAYMENT_HOLIDAY]),
)
repayment_holiday_interest_accrual_blocking_param = Parameter(
    name=repayment_holiday_PARAM_INTEREST_ACCRUAL_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block interest accruals. Expects a string representation of a JSON list.",
    display_name="Interest Accrual Blocking Flags",
    default_value=dumps([repayment_holiday_REPAYMENT_HOLIDAY]),
)
repayment_holiday_notification_blocking_param = Parameter(
    name=repayment_holiday_PARAM_NOTIFICATION_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block notifications. Expects a string representation of a JSON list.",
    display_name="Notification Blocking Flags",
    default_value=dumps([repayment_holiday_REPAYMENT_HOLIDAY]),
)
repayment_holiday_overdue_amount_calculation_blocking_param = Parameter(
    name=repayment_holiday_PARAM_OVERDUE_AMOUNT_CALCULATION_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block overdue amount calculation. Expects a string representation of a JSON list.",
    display_name="Overdue Amount Calculation Blocking Flags",
    default_value=dumps([repayment_holiday_REPAYMENT_HOLIDAY]),
)
repayment_holiday_penalty_blocking_param = Parameter(
    name=repayment_holiday_PARAM_PENALTY_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block penalty interest accrual. Expects a string representation of a JSON list.",
    display_name="Penalty Blocking Flags",
    default_value=dumps([repayment_holiday_REPAYMENT_HOLIDAY]),
)
repayment_holiday_repayment_blocking_param = Parameter(
    name=repayment_holiday_PARAM_REPAYMENT_BLOCKING_FLAGS,
    shape=StringShape(),
    level=ParameterLevel.TEMPLATE,
    description="The list of flag definitions that block repayments. Expects a string representation of a JSON list.",
    display_name="Repayment Blocking Flag",
    default_value=dumps([repayment_holiday_REPAYMENT_HOLIDAY]),
)
repayment_holiday_all_parameters_excluding_preference = [
    repayment_holiday_delinquency_blocking_param,
    repayment_holiday_due_amount_calculation_blocking_param,
    repayment_holiday_interest_accrual_blocking_param,
    repayment_holiday_notification_blocking_param,
    repayment_holiday_overdue_amount_calculation_blocking_param,
    repayment_holiday_penalty_blocking_param,
    repayment_holiday_repayment_blocking_param,
]


def repayment_holiday_is_repayment_blocked(vault: Any, effective_datetime: datetime) -> bool:
    return utils_is_flag_in_list_applied(
        vault=vault,
        parameter_name=repayment_holiday_PARAM_REPAYMENT_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


# Objects below have been imported from:
#    addresses.py
# md5:dd8f6d82cd93140051659a35e4e1246c

addresses_TOTAL = "TOTAL"
addresses_TOTAL_EMI = f"{addresses_TOTAL}_{lending_addresses_EMI}"
addresses_TOTAL_PRINCIPAL = f"{addresses_TOTAL}_{lending_addresses_PRINCIPAL}"
addresses_TOTAL_ORIGINAL_PRINCIPAL = f"{addresses_TOTAL}_ORIGINAL_{lending_addresses_PRINCIPAL}"
addresses_TOTAL_PRINCIPAL_DUE = f"{addresses_TOTAL}_{lending_addresses_PRINCIPAL_DUE}"
addresses_TOTAL_INTEREST_DUE = f"{addresses_TOTAL}_{lending_addresses_INTEREST_DUE}"
addresses_TOTAL_PRINCIPAL_OVERDUE = f"{addresses_TOTAL}_{lending_addresses_PRINCIPAL_OVERDUE}"
addresses_TOTAL_INTEREST_OVERDUE = f"{addresses_TOTAL}_{lending_addresses_INTEREST_OVERDUE}"
addresses_TOTAL_ACCRUED_INTEREST_RECEIVABLE = (
    f"{addresses_TOTAL}_{lending_addresses_ACCRUED_INTEREST_RECEIVABLE}"
)
addresses_TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE = (
    f"{addresses_TOTAL}_{lending_addresses_NON_EMI_ACCRUED_INTEREST_RECEIVABLE}"
)
addresses_TOTAL_PENALTIES = f"{addresses_TOTAL}_{lending_addresses_PENALTIES}"
addresses_OUTSTANDING_DEBT_ADDRESSES = [
    addresses_TOTAL_PRINCIPAL_OVERDUE,
    addresses_TOTAL_INTEREST_OVERDUE,
    addresses_TOTAL_PENALTIES,
    addresses_TOTAL_PRINCIPAL_DUE,
    addresses_TOTAL_INTEREST_DUE,
    addresses_TOTAL_PRINCIPAL,
    addresses_TOTAL_ACCRUED_INTEREST_RECEIVABLE,
    addresses_TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
    lending_addresses_PENALTIES,
]

# Objects below have been imported from:
#    line_of_credit.py
# md5:06d08acc879c2c1282a60675115a0c46

data_fetchers = [fetchers_EFFECTIVE_OBSERVATION_FETCHER, fetchers_LIVE_BALANCES_BOF]
LOC_ACCOUNT_TYPE = "LOC"
REPAYMENT_DUE_NOTIFICATION = "LOC_REPAYMENT_DUE"
OVERDUE_REPAYMENT_NOTIFICATION = "LOC_OVERDUE_REPAYMENT"
DELINQUENT_NOTIFICATION = "LOC_DELINQUENT"
LOANS_PAID_OFF_NOTIFICATION = "LOC_LOANS_PAID_OFF"
notification_types = [
    REPAYMENT_DUE_NOTIFICATION,
    OVERDUE_REPAYMENT_NOTIFICATION,
    DELINQUENT_NOTIFICATION,
    LOANS_PAID_OFF_NOTIFICATION,
]
event_types = [*due_amount_calculation_event_types(product_name=LOC_ACCOUNT_TYPE)]
PARAM_TOTAL_ARREARS_AMOUNT = "total_arrears"
PARAM_TOTAL_MONTHLY_REPAYMENT_AMOUNT = "total_monthly_repayment"
PARAM_TOTAL_ORIGINAL_PRINCIPAL = "total_original_principal"
PARAM_TOTAL_OUTSTANDING_DUE_AMOUNT = "total_outstanding_due"
PARAM_TOTAL_OUTSTANDING_PRINCIPAL = "total_outstanding_principal"
PARAM_TOTAL_AVAILABLE_CREDIT = "total_available_credit"
parameters = [
    *late_repayment_fee_parameters,
    *maximum_loan_principal_parameters,
    *minimum_loan_principal_parameters,
    *interest_accrual_schedule_parameters,
    *due_amount_calculation_schedule_parameters,
    due_amount_calculation_next_repayment_date_parameter,
    *credit_limit_parameters,
    *overdue_schedule_parameters,
    *delinquency_schedule_parameters,
    *maximum_outstanding_loans_parameters,
    *repayment_holiday_all_parameters_excluding_preference,
    common_parameters_denomination_parameter,
    overpayment_overpayment_fee_income_account_param,
    overpayment_overpayment_fee_rate_param,
    overpayment_overpayment_impact_preference_param,
    early_repayment_total_early_repayment_amount_parameter,
    Parameter(
        name=PARAM_TOTAL_ARREARS_AMOUNT,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The amount in arrears.",
        display_name="Arrears Amount",
    ),
    Parameter(
        name=PARAM_TOTAL_MONTHLY_REPAYMENT_AMOUNT,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The monthly repayment amount across all open loans.",
        display_name="Monthly Repayment Amount",
    ),
    Parameter(
        name=PARAM_TOTAL_ORIGINAL_PRINCIPAL,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The total original principal taken out across all open loans.",
        display_name="Original Principal",
    ),
    Parameter(
        name=PARAM_TOTAL_OUTSTANDING_DUE_AMOUNT,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The outstanding amount due to be paid.",
        display_name="Outstanding Due Amount",
    ),
    Parameter(
        name=PARAM_TOTAL_OUTSTANDING_PRINCIPAL,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The outstanding principal not yet repaid.",
        display_name="Outstanding Principal Remaining",
    ),
    Parameter(
        name=PARAM_TOTAL_AVAILABLE_CREDIT,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The credit available to be taken as loans.",
        display_name="Available Credit",
    ),
]


def _get_total_arrears_amount(denomination: str, balances: BalanceDefaultDict) -> Decimal:
    return utils_sum_balances(
        balances=balances,
        addresses=[addresses_TOTAL_PRINCIPAL_OVERDUE, addresses_TOTAL_INTEREST_OVERDUE],
        denomination=denomination,
    )


def _get_total_early_repayment_amount(
    vault: Any, denomination: str, balances: BalanceDefaultDict
) -> Decimal:
    overpayment_fee_rate = overpayment_get_overpayment_fee_rate_parameter(vault=vault)
    max_overpayment_fee = overpayment_get_max_overpayment_fee(
        fee_rate=overpayment_fee_rate,
        balances=balances,
        denomination=denomination,
        precision=2,
        principal_address=addresses_TOTAL_PRINCIPAL,
    )
    total_outstanding_amount = utils_sum_balances(
        balances=balances,
        addresses=addresses_OUTSTANDING_DEBT_ADDRESSES,
        denomination=denomination,
        decimal_places=2,
    )
    return total_outstanding_amount + max_overpayment_fee


def _get_total_monthly_repayment_amount(denomination: str, balances: BalanceDefaultDict) -> Decimal:
    return utils_sum_balances(
        balances=balances,
        addresses=[addresses_TOTAL_EMI],
        denomination=denomination,
        decimal_places=2,
    )


def _get_total_outstanding_due_amount(denomination: str, balances: BalanceDefaultDict) -> Decimal:
    return utils_sum_balances(
        balances=balances,
        addresses=[addresses_TOTAL_PRINCIPAL_DUE, addresses_TOTAL_INTEREST_DUE],
        denomination=denomination,
    )


def _get_total_original_principal(denomination: str, balances: BalanceDefaultDict) -> Decimal:
    return utils_sum_balances(
        balances=balances,
        addresses=[addresses_TOTAL_ORIGINAL_PRINCIPAL],
        denomination=denomination,
        decimal_places=2,
    )


def _get_total_outstanding_principal(denomination: str, balances: BalanceDefaultDict) -> Decimal:
    return utils_sum_balances(
        balances=balances,
        addresses=[
            addresses_TOTAL_PRINCIPAL,
            addresses_TOTAL_PRINCIPAL_DUE,
            addresses_TOTAL_PRINCIPAL_OVERDUE,
        ],
        denomination=denomination,
    )


def _get_total_available_credit(vault: Any, total_outstanding_principal: Decimal) -> Decimal:
    credit_limit_amount: Decimal = utils_get_parameter(
        vault=vault, name=credit_limit_PARAM_CREDIT_LIMIT
    )
    return credit_limit_amount - total_outstanding_principal
