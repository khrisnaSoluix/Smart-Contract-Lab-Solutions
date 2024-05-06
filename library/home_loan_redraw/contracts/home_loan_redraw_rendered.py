# Code auto-generated using Inception Smart Contract Renderer Version 2.0.1


# Objects below have been imported from:
#    home_loan_redraw.py
# md5:c860dd069ccdda5216ef301f51351669

from contracts_api import (
    BalancesObservationFetcher,
    DefinedDateTime,
    Override,
    PostingsIntervalFetcher,
    RelativeDateTime,
    Shift,
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
    NumberShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    AccountNotificationDirective,
    AccountIdShape,
    DateShape,
    ScheduledEventHookArguments,
    SmartContractEventType,
    SupervisorContractEventType,
    SupervisorScheduledEventHookArguments,
    UnionItem,
    UnionShape,
    BalancesFilter,
    BalancesObservation,
    OptionalShape,
    DenominationShape,
    PostingInstructionsDirective,
    PostPostingHookResult,
    ScheduledEventHookResult,
    UpdatePlanEventTypeDirective,
    PostPostingHookArguments,
    SupervisorPostPostingHookArguments,
    ActivationHookArguments,
    ActivationHookResult,
    ConversionHookArguments,
    ConversionHookResult,
    DeactivationHookArguments,
    DeactivationHookResult,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    PrePostingHookArguments,
    PrePostingHookResult,
    StringShape,
    fetch_account_data,
    requires,
)
from calendar import isleap
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from json import loads
import math
from typing import Optional, Any, Iterable, Mapping, Union, Callable, NamedTuple
from zoneinfo import ZoneInfo

api = "4.0.0"
version = "2.0.2"
display_name = "Home Loan Redraw"
summary = "A loan suitable for Australian market"
tside = Tside.ASSET
supported_denominations = ["AUD"]


@requires(parameters=True)
def activation_hook(
    vault: Any, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    effective_datetime: datetime = hook_arguments.effective_datetime
    scheduled_events: dict[str, ScheduledEvent] = {
        **interest_accrual_scheduled_events(
            vault=vault, start_datetime=hook_arguments.effective_datetime
        )
    }
    principal = utils_get_parameter(vault=vault, name=disbursement_PARAM_PRINCIPAL)
    deposit_account_id = utils_get_parameter(vault=vault, name=disbursement_PARAM_DEPOSIT_ACCOUNT)
    disbursement_posting_instructions = disbursement_get_disbursement_custom_instruction(
        account_id=vault.account_id,
        deposit_account_id=deposit_account_id,
        principal=principal,
        denomination=denomination,
    )
    emi_posting_instructions = emi_amortise(
        vault=vault,
        effective_datetime=effective_datetime,
        amortisation_feature=declining_principal_AmortisationFeature,
        interest_calculation_feature=variable_interest_rate_interface,
    )
    pi_directives = PostingInstructionsDirective(
        posting_instructions=[*disbursement_posting_instructions, *emi_posting_instructions],
        client_batch_id=f"{events_ACCOUNT_ACTIVATION}_{vault.get_hook_execution_id()}",
        value_datetime=effective_datetime,
    )
    scheduled_events = {
        **interest_accrual_scheduled_events(
            vault=vault, start_datetime=hook_arguments.effective_datetime
        ),
        **due_amount_calculation_scheduled_events(
            vault=vault, account_opening_datetime=hook_arguments.effective_datetime
        ),
    }
    return ActivationHookResult(
        posting_instructions_directives=[pi_directives],
        scheduled_events_return_value=scheduled_events,
    )


def conversion_hook(
    vault: Any, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    return ConversionHookResult(scheduled_events_return_value=hook_arguments.existing_schedules)


@fetch_account_data(balances=["live_balances_bof"])
@requires(parameters=True)
def deactivation_hook(
    vault: Any, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    if outstanding_debt_rejection := close_loan_reject_closure_when_outstanding_debt(
        balances=balances, denomination=denomination
    ):
        return DeactivationHookResult(rejection=outstanding_debt_rejection)
    if outstanding_redraw_funds_rejection := redraw_reject_closure_when_outstanding_redraw_funds(
        balances=balances, denomination=denomination
    ):
        return DeactivationHookResult(rejection=outstanding_redraw_funds_rejection)
    posting_instructions_to_net_balances = close_loan_net_balances(
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        residual_cleanup_features=[
            due_amount_calculation_DueAmountCalculationResidualCleanupFeature
        ],
    )
    if posting_instructions_to_net_balances:
        return DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=posting_instructions_to_net_balances,
                    value_datetime=hook_arguments.effective_datetime,
                )
            ]
        )
    return None


@fetch_account_data(balances=["EFFECTIVE_FETCHER"])
@requires(last_execution_datetime=["DUE_AMOUNT_CALCULATION"], parameters=True)
def derived_parameter_hook(
    vault: Any, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    available_redraw_funds = redraw_get_available_redraw_funds(
        balances=balances, denomination=denomination
    )
    next_repayment_datetime = _calculate_next_repayment_date(
        vault=vault, derived_parameter_hook_args=hook_arguments
    )
    total_outstanding_debt = derived_params_get_total_outstanding_debt(
        balances=balances, denomination=denomination
    )
    total_outstanding_payments = derived_params_get_total_due_amount(
        balances=balances, denomination=denomination
    )
    total_remaining_principal = derived_params_get_total_remaining_principal(
        balances=balances, denomination=denomination
    )
    (_, remaining_term) = declining_principal_term_details(
        vault=vault,
        effective_datetime=hook_arguments.effective_datetime,
        use_expected_term=False,
        interest_rate=variable_interest_rate_interface,
        principal_adjustments=[
            lending_interfaces_PrincipalAdjustment(
                calculate_principal_adjustment=lambda vault, balances, denomination: available_redraw_funds
                * -1
            )
        ],
        balances=balances,
        denomination=denomination,
    )
    derived_parameters: dict[str, utils_ParameterValueTypeAlias] = {
        redraw_PARAM_AVAILABLE_REDRAW_FUNDS: available_redraw_funds,
        due_amount_calculation_PARAM_NEXT_REPAYMENT_DATE: next_repayment_datetime,
        derived_params_PARAM_REMAINING_TERM: remaining_term,
        derived_params_PARAM_TOTAL_OUTSTANDING_DEBT: total_outstanding_debt,
        derived_params_PARAM_TOTAL_OUTSTANDING_PAYMENTS: total_outstanding_payments,
        derived_params_PARAM_TOTAL_REMAINING_PRINCIPAL: total_remaining_principal,
    }
    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


@fetch_account_data(balances=["live_balances_bof"])
@requires(parameters=True)
def post_posting_hook(
    vault: Any, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    posting_amount: Decimal = (
        hook_arguments.posting_instructions[0]
        .balances()[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED]
        .net
    )
    posting_instructions: list[CustomInstruction] = []
    account_notification_directives: list[AccountNotificationDirective] = []
    if posting_amount < 0:
        posting_instructions += payments_generate_repayment_postings(
            vault=vault,
            hook_arguments=hook_arguments,
            repayment_hierarchy=REPAYMENT_HIERARCHY,
            overpayment_features=[redraw_OverpaymentFeature],
        )
        account_notification_directives += _check_and_send_closure_notification(
            repayment_posting_instructions=posting_instructions,
            balances=vault.get_balances_observation(
                fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
            ).balances,
            denomination=denomination,
            account_id=vault.account_id,
        )
    elif posting_amount > 0:
        posting_instructions += _process_withdrawal(
            account_id=vault.account_id, withdrawal_amount=posting_amount, denomination=denomination
        )
    if posting_instructions:
        return PostPostingHookResult(
            account_notification_directives=account_notification_directives,
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=posting_instructions,
                    client_batch_id=f"{vault.get_hook_execution_id()}",
                    value_datetime=hook_arguments.effective_datetime,
                )
            ],
        )
    return None


@fetch_account_data(balances=["live_balances_bof"])
@requires(parameters=True)
def pre_posting_hook(
    vault: Any, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    posting_instructions = hook_arguments.posting_instructions
    if utils_is_force_override(posting_instructions=posting_instructions):
        return None
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    if invalid_denomination_rejection := utils_validate_denomination(
        posting_instructions=posting_instructions, accepted_denominations=[denomination]
    ):
        return PrePostingHookResult(rejection=invalid_denomination_rejection)
    if invalid_posting_instructions_rejection := utils_validate_single_hard_settlement_or_transfer(
        posting_instructions=posting_instructions
    ):
        return PrePostingHookResult(rejection=invalid_posting_instructions_rejection)
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    posting_amount: Decimal = (
        hook_arguments.posting_instructions[0]
        .balances()[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED]
        .net
    )
    if invalid_redraw_funds_rejection := redraw_validate_redraw_funds(
        balances=balances, posting_amount=posting_amount, denomination=denomination
    ):
        return PrePostingHookResult(rejection=invalid_redraw_funds_rejection)
    total_outstanding_debt = derived_params_get_total_outstanding_debt(
        balances=balances, denomination=denomination
    )
    remaining_redraw_balance = redraw_get_available_redraw_funds(
        balances=balances, denomination=denomination
    )
    if (
        posting_amount < 0
        and abs(posting_amount) > total_outstanding_debt - remaining_redraw_balance
    ):
        return PrePostingHookResult(
            rejection=Rejection(
                message=f"Cannot make a payment of {abs(posting_amount)} {denomination} greater than the net difference of the total outstanding debt of {total_outstanding_debt} {denomination} and the remaining redraw balance of {remaining_redraw_balance} {denomination}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
    return None


@requires(event_type="ACCRUE_INTEREST", parameters=True)
@fetch_account_data(event_type="ACCRUE_INTEREST", balances=["EOD_FETCHER"])
@requires(
    event_type="DUE_AMOUNT_CALCULATION",
    last_execution_datetime=["DUE_AMOUNT_CALCULATION"],
    parameters=True,
)
@fetch_account_data(
    event_type="DUE_AMOUNT_CALCULATION",
    balances=[
        "EFFECTIVE_FETCHER",
        "ACCRUED_INTEREST_EFFECTIVE_DATETIME_FETCHER",
        "ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER",
    ],
)
def scheduled_event_hook(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    posting_instructions: list[CustomInstruction] = []
    account_notification_directives: list[AccountNotificationDirective] = []
    if hook_arguments.event_type == interest_accrual_ACCRUAL_EVENT:
        posting_instructions += interest_accrual_daily_accrual_logic(
            vault=vault,
            interest_rate_feature=variable_interest_rate_interface,
            hook_arguments=hook_arguments,
            account_type=PRODUCT_NAME,
            principal_addresses=[lending_addresses_PRINCIPAL, redraw_REDRAW_ADDRESS],
        )
    elif hook_arguments.event_type == due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT:
        (due_postings, returned_account_notification_directives) = _calculate_due_amounts(
            vault=vault, hook_arguments=hook_arguments
        )
        account_notification_directives += returned_account_notification_directives
        posting_instructions += due_postings
    if posting_instructions:
        return ScheduledEventHookResult(
            account_notification_directives=account_notification_directives,
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=posting_instructions,
                    value_datetime=hook_arguments.effective_datetime,
                )
            ],
        )
    return None


# Objects below have been imported from:
#    events.py
# md5:ee964ddec320f22b8eeab458a02a6835

events_ACCOUNT_ACTIVATION = "ACCOUNT_ACTIVATION"

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


# Objects below have been imported from:
#    addresses.py
# md5:860f50af37f2fe98540f540fa6394eb7

addresses_DEFAULT = "DEFAULT"
addresses_INTERNAL_CONTRA = "INTERNAL_CONTRA"
addresses_PENALTIES = "PENALTIES"

# Objects below have been imported from:
#    lending_addresses.py
# md5:d546448643732336308da8f52c0901d4

lending_addresses_ACCRUED_INTEREST_RECEIVABLE = "ACCRUED_INTEREST_RECEIVABLE"
lending_addresses_DUE_CALCULATION_EVENT_COUNTER = "DUE_CALCULATION_EVENT_COUNTER"
lending_addresses_EMI = "EMI"
lending_addresses_INTERNAL_CONTRA = addresses_INTERNAL_CONTRA
lending_addresses_INTEREST_DUE = "INTEREST_DUE"
lending_addresses_INTEREST_OVERDUE = "INTEREST_OVERDUE"
lending_addresses_PENALTIES = addresses_PENALTIES
lending_addresses_PRINCIPAL = "PRINCIPAL"
lending_addresses_PRINCIPAL_DUE = "PRINCIPAL_DUE"
lending_addresses_PRINCIPAL_OVERDUE = "PRINCIPAL_OVERDUE"
lending_addresses_CAPITALISED_INTEREST_TRACKER = "CAPITALISED_INTEREST_TRACKER"
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
lending_addresses_DEBT_ADDRESSES = lending_addresses_REPAYMENT_HIERARCHY + [
    lending_addresses_PRINCIPAL
]
lending_addresses_ALL_OUTSTANDING = [
    *lending_addresses_DEBT_ADDRESSES,
    lending_addresses_ACCRUED_INTEREST_RECEIVABLE,
    lending_addresses_ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
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
lending_interfaces_Overpayment = NamedTuple(
    "Overpayment", [("handle_overpayment", Callable[..., list[Posting]])]
)
lending_interfaces_PrincipalAdjustment = NamedTuple(
    "PrincipalAdjustment", [("calculate_principal_adjustment", Callable[..., Decimal])]
)
lending_interfaces_ResidualCleanup = NamedTuple(
    "ResidualCleanup", [("get_residual_cleanup_postings", Callable[..., list[Posting]])]
)
lending_interfaces_Amortisation = NamedTuple(
    "Amortisation",
    [
        ("calculate_emi", Callable[..., Decimal]),
        ("term_details", Callable[..., tuple[int, int]]),
        ("override_final_event", bool),
    ],
)
lending_interfaces_ReamortisationCondition = NamedTuple(
    "ReamortisationCondition", [("should_trigger_reamortisation", Callable[..., bool])]
)

# Objects below have been imported from:
#    lending_parameters.py
# md5:7faccb9f85f49b8f7dea97327cbece56

lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT = "total_repayment_count"
lending_parameters_total_repayment_count_parameter = Parameter(
    name=lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT,
    shape=NumberShape(min_value=Decimal(1), step=Decimal(1)),
    level=ParameterLevel.INSTANCE,
    description="The total number of repayments to be made, at a monthly frequency unless a repayment_frequency parameter is present.",
    display_name="Total Repayment Count",
    default_value=Decimal(12),
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)

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


def declining_principal_term_details(
    vault: Any,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    interest_rate: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> tuple[int, int]:
    """Calculate the elapsed and remaining term for a loan

    :param vault: the vault object for the loan account
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
        utils_get_parameter(vault=vault, name=lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT)
    )
    if effective_datetime == vault.get_account_creation_datetime():
        return (0, original_total_term)
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name="denomination")
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
            vault=vault,
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
                    vault=vault, balances=balances, denomination=denomination
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


def declining_principal_calculate_emi(
    vault: Any,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> Decimal:
    """
    Extracts relevant data required and calculates declining principal EMI.
    :param vault: Vault object
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
        vault=vault,
        effective_datetime=effective_datetime,
        principal_amount=principal_amount,
        interest_calculation_feature=interest_calculation_feature,
    )
    (_, remaining_term) = declining_principal_term_details(
        vault=vault,
        effective_datetime=effective_datetime,
        use_expected_term=use_expected_term,
        interest_rate=interest_calculation_feature,
        principal_adjustments=principal_adjustments,
        balances=balances,
    )
    if principal_adjustments:
        denomination: str = utils_get_parameter(vault=vault, name="denomination")
        principal += Decimal(
            sum(
                (
                    adjustment.calculate_principal_adjustment(
                        vault=vault, balances=balances, denomination=denomination
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


declining_principal_AmortisationFeature = lending_interfaces_Amortisation(
    calculate_emi=declining_principal_calculate_emi,
    term_details=declining_principal_term_details,
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


def close_loan_net_balances(
    balances: BalanceDefaultDict,
    denomination: str,
    account_id: str,
    residual_cleanup_features: Optional[list[lending_interfaces_ResidualCleanup]] = None,
) -> list[CustomInstruction]:
    """
    Nets off the EMI, and any other accounting addresses from other features, that should be
    cleared before the loan is closed

    :param balances: The current balances for the account
    :param denomination: The denomination of the account
    :param account_id: The id of the account
    :param residual_cleanup_features: list of features to get residual cleanup postings
    :return: A list of custom instructions used to net all remaining balances
    """
    net_postings: list[Posting] = []
    emi_amount = utils_balance_at_coordinates(
        balances=balances, address=lending_addresses_EMI, denomination=denomination
    )
    if emi_amount > Decimal("0"):
        net_postings += utils_create_postings(
            amount=emi_amount,
            debit_account=account_id,
            credit_account=account_id,
            debit_address=lending_addresses_INTERNAL_CONTRA,
            credit_address=lending_addresses_EMI,
            denomination=denomination,
        )
    if residual_cleanup_features is not None:
        for feature in residual_cleanup_features:
            net_postings += feature.get_residual_cleanup_postings(
                balances=balances, account_id=account_id, denomination=denomination
            )
    posting_instructions: list[CustomInstruction] = []
    if net_postings:
        posting_instructions += [
            CustomInstruction(
                postings=net_postings,
                instruction_details={
                    "description": "Clearing all residual balances",
                    "event": "END_OF_LOAN",
                },
            )
        ]
    return posting_instructions


def close_loan_reject_closure_when_outstanding_debt(
    balances: BalanceDefaultDict,
    denomination: str,
    debt_addresses: list[str] = close_loan_DEBT_ADDRESSES,
) -> Optional[Rejection]:
    """
    Returns a rejection if the debt addresses sum to a non-zero amount

    :param balances: The current balances for the loan account
    :param denomination: The denomination of the account
    :param debt_addresses: A list of debt addresses to sum
    :return: A rejection if the debt addresses sum to a non-zero value
    """
    if utils_sum_balances(
        balances=balances, addresses=debt_addresses, denomination=denomination
    ) != Decimal("0"):
        return Rejection(
            message="The loan cannot be closed until all outstanding debt is repaid",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


# Objects below have been imported from:
#    derived_params.py
# md5:e5e42c2b86af0ad211853bcc16ea1854

derived_params_PARAM_TOTAL_OUTSTANDING_DEBT = "total_outstanding_debt"
derived_params_PARAM_TOTAL_OUTSTANDING_PAYMENTS = "total_outstanding_payments"
derived_params_PARAM_TOTAL_REMAINING_PRINCIPAL = "total_remaining_principal"
derived_params_PARAM_REMAINING_TERM = "remaining_term"
derived_params_total_outstanding_debt_parameter = Parameter(
    name=derived_params_PARAM_TOTAL_OUTSTANDING_DEBT,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Remaining total balance on this account",
    display_name="Total Outstanding Debt",
)
derived_params_total_outstanding_payments_parameter = Parameter(
    name=derived_params_PARAM_TOTAL_OUTSTANDING_PAYMENTS,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Remaining total payments to be made on this account",
    display_name="Total Outstanding Payments",
)
derived_params_total_remaining_principal_parameter = Parameter(
    name=derived_params_PARAM_TOTAL_REMAINING_PRINCIPAL,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Remaining total principal balance on the account",
    display_name="Total Remaining Principal",
)
derived_params_remaining_term_parameter = Parameter(
    name=derived_params_PARAM_REMAINING_TERM,
    shape=NumberShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Remaining total term in months",
    display_name="Remaining Term In Months",
)
derived_params_all_parameters = [
    derived_params_total_outstanding_debt_parameter,
    derived_params_total_outstanding_payments_parameter,
    derived_params_total_remaining_principal_parameter,
    derived_params_remaining_term_parameter,
]


def derived_params_get_total_due_amount(
    balances: BalanceDefaultDict, denomination: str, precision: int = 2
) -> Decimal:
    """
    Sums the balances across all due addresses
    :param balances: a dictionary of balances in the account
    :param denomination: the denomination of the balances to be summed
    :param precision: the number of decimal places to round to
    :return: due balance in Decimal
    """
    return utils_sum_balances(
        balances=balances,
        addresses=lending_addresses_REPAYMENT_HIERARCHY,
        denomination=denomination,
        decimal_places=precision,
    )


def derived_params_get_total_outstanding_debt(
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int = 2,
    debt_addresses: list[str] = lending_addresses_ALL_OUTSTANDING,
) -> Decimal:
    """
    Sums the balances across all outstanding debt addresses
    :param balances: a dictionary of balances in the account
    :param denomination: the denomination of the balances to be summed
    :param precision: the number of decimal places to round to
    :param debt_addresses: outstanding debt addresses
    :return: outstanding debt balance in Decimal
    """
    return utils_sum_balances(
        balances=balances,
        addresses=debt_addresses,
        denomination=denomination,
        decimal_places=precision,
    )


def derived_params_get_total_remaining_principal(
    balances: BalanceDefaultDict, denomination: str, precision: int = 2
) -> Decimal:
    """
    Sums the balances across all principal addresses
    :param balances: A dictionary of balances in the account
    :param denomination: The denomination of the balances to be summed
    :param precision: The number of decimal places to round to
    :return: The total principal remaining on the account
    """
    return utils_sum_balances(
        balances=balances,
        addresses=lending_addresses_ALL_PRINCIPAL,
        denomination=denomination,
        decimal_places=precision,
    )


# Objects below have been imported from:
#    disbursement.py
# md5:54aa49cf8e9b9c7684c275bf28a818d3

disbursement_DISBURSEMENT_EVENT = "PRINCIPAL_DISBURSEMENT"
disbursement_PARAM_PRINCIPAL = "principal"
disbursement_PARAM_DEPOSIT_ACCOUNT = "deposit_account"
disbursement_parameters = [
    Parameter(
        name=disbursement_PARAM_PRINCIPAL,
        shape=NumberShape(min_value=Decimal("1")),
        level=ParameterLevel.INSTANCE,
        description="The agreed amount the customer will borrow from the bank.",
        display_name="Loan Principal",
        default_value=Decimal("1000"),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=disbursement_PARAM_DEPOSIT_ACCOUNT,
        shape=AccountIdShape(),
        level=ParameterLevel.INSTANCE,
        description="The account to which the principal borrowed amount will be transferred.",
        display_name="Deposit Account",
        default_value="00000000-0000-0000-0000-000000000000",
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
]


def disbursement_get_disbursement_custom_instruction(
    account_id: str,
    deposit_account_id: str,
    principal: Decimal,
    denomination: str,
    principal_address: str = lending_addresses_PRINCIPAL,
) -> list[CustomInstruction]:
    return [
        CustomInstruction(
            postings=[
                Posting(
                    credit=False,
                    amount=principal,
                    denomination=denomination,
                    account_id=account_id,
                    account_address=principal_address,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=True,
                    amount=principal,
                    denomination=denomination,
                    account_id=deposit_account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
            override_all_restrictions=True,
            instruction_details={
                "description": f"Principal disbursement of {principal}",
                "event": disbursement_DISBURSEMENT_EVENT,
            },
        )
    ]


# Objects below have been imported from:
#    emi.py
# md5:6fd652b0be2b953dfaf528e599cb7c8b


def emi_amortise(
    vault: Any,
    effective_datetime: datetime,
    amortisation_feature: lending_interfaces_Amortisation,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    event: Optional[str] = events_ACCOUNT_ACTIVATION,
) -> list[CustomInstruction]:
    """
    Amortises a loan by calculating EMI and creating a custom instruction to update the balance
    value at the EMI address. Suitable for initial amortisation, and reamortisation if the
    `balances` argument is populated.

    :param vault: Vault object
    :param effective_datetime: effective dt for calculating the emi
    :param amortisation_feature: contains the emi calculation method for the desired amortisation
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the amortisation feature calculate_emi method is expected to set
        principal amount to the value set on parameter level.
    :param interest_calculation_feature: an interest calculation feature
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param event: event string to be included in the CustomInstruction instruction_details.
        If not provided, value defaults to ACCOUNT_ACTIVATION.
    :param balances: balances used to calculate emi and determine whether postings are required to
    update it. If balances are None, emi and elapsed term both assumed to be 0. This
    is suitable for scenarios such as initial amortisation on account activation
    :return: list of custom instructions, empty if no changes to the EMI
    """
    updated_emi = amortisation_feature.calculate_emi(
        vault=vault,
        effective_datetime=effective_datetime,
        principal_amount=principal_amount,
        interest_calculation_feature=interest_calculation_feature,
        principal_adjustments=principal_adjustments,
        balances=balances,
    )
    denomination: str = utils_get_parameter(
        vault, name="denomination", at_datetime=effective_datetime
    )
    if balances is None:
        current_emi = Decimal("0")
    else:
        current_emi = utils_balance_at_coordinates(
            balances=balances, address=lending_addresses_EMI, denomination=denomination
        )
    update_emi_postings = emi_update_emi(
        account_id=vault.account_id,
        denomination=denomination,
        current_emi=current_emi,
        updated_emi=updated_emi,
    )
    if not update_emi_postings:
        return []
    return [
        CustomInstruction(
            postings=update_emi_postings,
            instruction_details={
                "description": f"Updating EMI to {updated_emi}",
                "event": f"{event}",
            },
        )
    ]


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


def due_amount_calculation_schedule_logic(
    vault: Any,
    hook_arguments: ScheduledEventHookArguments,
    account_type: str,
    amortisation_feature: lending_interfaces_Amortisation,
    interest_application_feature: Optional[lending_interfaces_InterestApplication] = None,
    reamortisation_condition_features: Optional[
        list[lending_interfaces_ReamortisationCondition]
    ] = None,
    interest_rate_feature: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustment_features: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Calculate due amounts and create CustomInstructions to effect any required balance updates
    :param vault: vault object for the account
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
    customer_account = vault.account_id
    effective_datetime = hook_arguments.effective_datetime
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name="denomination")
    current_principal = due_amount_calculation_get_principal(
        balances=balances, denomination=denomination
    )
    (elapsed_term, remaining_term) = amortisation_feature.term_details(
        vault=vault,
        effective_datetime=effective_datetime,
        use_expected_term=True,
        interest_rate=interest_rate_feature,
        balances=balances,
    )
    last_execution_effective_datetime = (
        vault.get_account_creation_datetime()
        if elapsed_term == 0
        else vault.get_last_execution_datetime(
            event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
        )
    )
    if interest_application_feature is not None:
        interest_amounts = interest_application_feature.get_interest_to_apply(
            vault=vault,
            effective_datetime=effective_datetime,
            previous_application_datetime=last_execution_effective_datetime,
            balances_at_application=balances,
        )
        emi_interest_to_apply = (
            interest_amounts.total_rounded - interest_amounts.non_emi_rounded_accrued
        )
        postings += interest_application_feature.apply_interest(
            vault=vault,
            effective_datetime=effective_datetime,
            previous_application_datetime=last_execution_effective_datetime,
            balances_at_application=balances,
        )
    else:
        emi_interest_to_apply = Decimal(0)
    requires_reamortisation = any(
        (
            reamortisation_interface.should_trigger_reamortisation(
                vault=vault,
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
            vault=vault,
            effective_datetime=effective_datetime,
            use_expected_term=True,
            principal_amount=current_principal,
            interest_calculation_feature=interest_rate_feature,
            principal_adjustments=principal_adjustment_features,
            balances=balances,
        )
        postings += emi_update_emi(
            account_id=vault.account_id,
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


def due_amount_calculation_get_residual_cleanup_postings(
    balances: BalanceDefaultDict, account_id: str, denomination: str
) -> list[Posting]:
    return utils_reset_tracker_balances(
        balances=balances,
        account_id=account_id,
        tracker_addresses=[lending_addresses_DUE_CALCULATION_EVENT_COUNTER],
        contra_address=lending_addresses_INTERNAL_CONTRA,
        denomination=denomination,
        tside=Tside.ASSET,
    )


due_amount_calculation_DueAmountCalculationResidualCleanupFeature = (
    lending_interfaces_ResidualCleanup(
        get_residual_cleanup_postings=due_amount_calculation_get_residual_cleanup_postings
    )
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
interest_accrual_common_PARAM_INTEREST_ACCRUAL_HOUR = (
    f"{interest_accrual_common_INTEREST_ACCRUAL_PREFIX}_hour"
)
interest_accrual_common_PARAM_INTEREST_ACCRUAL_MINUTE = (
    f"{interest_accrual_common_INTEREST_ACCRUAL_PREFIX}_minute"
)
interest_accrual_common_PARAM_INTEREST_ACCRUAL_SECOND = (
    f"{interest_accrual_common_INTEREST_ACCRUAL_PREFIX}_second"
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
#    interest_accrual.py
# md5:07236706e076b2c0568b51146520a313

interest_accrual_ACCRUED_INTEREST_RECEIVABLE = interest_accrual_common_ACCRUED_INTEREST_RECEIVABLE
interest_accrual_ACCRUAL_EVENT = interest_accrual_common_ACCRUAL_EVENT
interest_accrual_event_types = interest_accrual_common_event_types
interest_accrual_scheduled_events = interest_accrual_common_scheduled_events
interest_accrual_data_fetchers = [fetchers_EOD_FETCHER]
interest_accrual_PARAM_DAYS_IN_YEAR = interest_accrual_common_PARAM_DAYS_IN_YEAR
interest_accrual_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "accrued_interest_receivable_account"
interest_accrual_accrued_interest_receivable_account_param = Parameter(
    name=interest_accrual_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for accrued interest receivable balance.",
    display_name="Accrued Interest Receivable Account",
    shape=AccountIdShape(),
    default_value="ACCRUED_INTEREST_RECEIVABLE",
)
interest_accrual_schedule_parameters = interest_accrual_common_schedule_parameters
interest_accrual_accrual_parameters = interest_accrual_common_accrual_parameters
interest_accrual_account_parameters = [interest_accrual_accrued_interest_receivable_account_param]


def interest_accrual_daily_accrual_logic(
    vault: Union[Any, Any],
    hook_arguments: Union[ScheduledEventHookArguments, SupervisorScheduledEventHookArguments],
    interest_rate_feature: lending_interfaces_InterestRate,
    account_type: str,
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
    :param customer_accrual_address: the address to accrue to. If None, accrual address is
    ACCRUED_INTEREST_RECEIVABLE otherwise
    :return: The custom instructions to accrue interest, if required
    """
    midnight = hook_arguments.effective_datetime - relativedelta(hour=0, minute=0, second=0)
    principal_addresses = principal_addresses or [lending_addresses_PRINCIPAL]
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name="denomination")
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_EOD_FETCHER_ID).balances
    if inflight_postings:
        for custom_instruction in inflight_postings:
            balances += custom_instruction.balances(account_id=vault.account_id, tside=Tside.ASSET)
    effective_balance = Decimal(
        sum(
            (
                utils_balance_at_coordinates(
                    balances=balances, address=principal_address, denomination=denomination
                )
                for principal_address in principal_addresses
            )
        )
    )
    if customer_accrual_address is None:
        customer_accrual_address = interest_accrual_ACCRUED_INTEREST_RECEIVABLE
    if accrual_internal_account is None:
        accrual_internal_account = utils_get_parameter(
            vault=vault, name=interest_accrual_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
        )
    return interest_accrual_common_daily_accrual(
        customer_account=vault.account_id,
        customer_address=customer_accrual_address,
        denomination=denomination,
        internal_account=accrual_internal_account,
        days_in_year=utils_get_parameter(
            vault=vault, name=interest_accrual_PARAM_DAYS_IN_YEAR, is_union=True
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


def interest_accrual_get_accrual_internal_account(vault: Any) -> str:
    accrual_internal_account: str = utils_get_parameter(
        vault=vault, name=interest_accrual_PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    )
    return accrual_internal_account


# Objects below have been imported from:
#    interest_application.py
# md5:b206c2a889540dba58282c6ec772665e

interest_application_ACCRUED_INTEREST_RECEIVABLE = (
    interest_accrual_common_ACCRUED_INTEREST_RECEIVABLE
)
interest_application_INTEREST_DUE = "INTEREST_DUE"
interest_application_ACCRUED_INTEREST_EFF_FETCHER_ID = "ACCRUED_INTEREST_EFFECTIVE_DATETIME_FETCHER"
interest_application_accrued_interest_eff_fetcher = BalancesObservationFetcher(
    fetcher_id=interest_application_ACCRUED_INTEREST_EFF_FETCHER_ID,
    at=DefinedDateTime.EFFECTIVE_DATETIME,
    filter=BalancesFilter(addresses=[interest_application_ACCRUED_INTEREST_RECEIVABLE]),
)
interest_application_ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID = (
    "ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER"
)
interest_application_accrued_interest_one_month_ago_fetcher = BalancesObservationFetcher(
    fetcher_id=interest_application_ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID,
    at=RelativeDateTime(origin=DefinedDateTime.EFFECTIVE_DATETIME, shift=Shift(months=-1)),
    filter=BalancesFilter(addresses=[interest_application_ACCRUED_INTEREST_RECEIVABLE]),
)
interest_application_PARAM_INTEREST_RECEIVED_ACCOUNT = "interest_received_account"
interest_application_PARAM_APPLICATION_PRECISION = "application_precision"
interest_application_application_precision_param = Parameter(
    name=interest_application_PARAM_APPLICATION_PRECISION,
    level=ParameterLevel.TEMPLATE,
    description="Number of decimal places accrued interest is rounded to when applying interest.",
    display_name="Interest Application Precision",
    shape=NumberShape(max_value=15, step=1),
    default_value=Decimal(2),
)
interest_application_interest_received_account_param = Parameter(
    name=interest_application_PARAM_INTEREST_RECEIVED_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for interest received balance.",
    display_name="Interest Received Account",
    shape=AccountIdShape(),
    default_value="INTEREST_RECEIVED",
)
interest_application_account_parameters = [interest_application_interest_received_account_param]


def interest_application_apply_interest(
    *,
    vault: Any,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances_at_application: Optional[BalanceDefaultDict] = None,
) -> list[Posting]:
    application_internal_account = interest_application_get_application_internal_account(
        vault=vault
    )
    application_interest_address = interest_application_INTEREST_DUE
    accrual_internal_account = interest_accrual_get_accrual_internal_account(vault=vault)
    denomination = utils_get_parameter(vault, "denomination")
    application_precision = interest_application_get_application_precision(vault=vault)
    effective_datetime_observation: BalancesObservation = vault.get_balances_observation(
        fetcher_id=interest_application_ACCRUED_INTEREST_EFF_FETCHER_ID
    )
    one_month_ago_observation: BalancesObservation = vault.get_balances_observation(
        fetcher_id=interest_application_ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID
    )
    interest_application_amounts = interest_application__get_interest_to_apply(
        balances_at_application=effective_datetime_observation.balances,
        balances_one_repayment_period_ago=one_month_ago_observation.balances,
        denomination=denomination,
        application_precision=application_precision,
        effective_datetime=effective_datetime,
        previous_application_datetime=previous_application_datetime,
    )
    return accruals_accrual_application_postings(
        customer_account=vault.account_id,
        denomination=denomination,
        application_amount=interest_application_amounts.total_rounded,
        accrual_amount=interest_application_amounts.emi_accrued
        + interest_application_amounts.non_emi_accrued,
        accrual_customer_address=interest_application_ACCRUED_INTEREST_RECEIVABLE,
        accrual_internal_account=accrual_internal_account,
        application_customer_address=application_interest_address,
        application_internal_account=application_internal_account,
        payable=False,
    )


def interest_application__interest_amounts(
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int = 2,
    rounding: str = ROUND_HALF_UP,
) -> tuple[Decimal, Decimal]:
    """
    Determine the amount of interest in balances, un-rounded and rounded
    :param balances: balances for the account that interest is being applied on
    :param denomination: denomination of the accrued interest to apply
    :param precision: the number of decimal places to round to
    :param rounding: the Decimal rounding strategy to use
    :return: the un-rounded and rounded amounts
    """
    accrued_amount = balances[
        BalanceCoordinate(
            interest_application_ACCRUED_INTEREST_RECEIVABLE,
            DEFAULT_ASSET,
            denomination,
            phase=Phase.COMMITTED,
        )
    ].net
    return (
        accrued_amount,
        utils_round_decimal(accrued_amount, decimal_places=precision, rounding=rounding),
    )


def interest_application__get_interest_to_apply(
    *,
    balances_at_application: BalanceDefaultDict,
    balances_one_repayment_period_ago: BalanceDefaultDict,
    denomination: str,
    application_precision: int,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
) -> lending_interfaces_InterestAmounts:
    (effective_unrounded, effective_rounded) = interest_application__interest_amounts(
        balances=balances_at_application, denomination=denomination, precision=application_precision
    )
    if effective_datetime - relativedelta(months=1) < previous_application_datetime:
        (one_period_ago_unrounded, one_period_ago_rounded) = (Decimal("0"), Decimal("0"))
    else:
        (one_period_ago_unrounded, one_period_ago_rounded) = interest_application__interest_amounts(
            balances=balances_one_repayment_period_ago,
            denomination=denomination,
            precision=application_precision,
        )
    return lending_interfaces_InterestAmounts(
        emi_accrued=effective_unrounded - one_period_ago_unrounded,
        emi_rounded_accrued=effective_rounded - one_period_ago_rounded,
        non_emi_accrued=one_period_ago_unrounded,
        non_emi_rounded_accrued=one_period_ago_rounded,
        total_rounded=effective_rounded,
    )


def interest_application_get_interest_to_apply(
    *,
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
    :param effective_datetime: the effective datetime for interest application
    :param previous_application_datetime: the previous datetime of interest application
    :param balances_at_application: balances at the time of application, before application has
    been processed. If None, fetched using the ACCRUED_INTEREST_EFF_FETCHER_ID fetcher
    :param balances_one_repayment_period_ago: balances one repayment period before application. If
    None, fetched using the ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID fetcher
    :param denomination: the denomination to use for accrual. If None, the latest value of the
    `denomination` parameter is used.
    :param application_precision: number of places that accrued interest is rounded to before
    application. If None, the latest value of the PARAM_APPLICATION_PRECISION parameter is used.
    :return: the interest amounts
    """
    if balances_at_application is None:
        balances_at_application = vault.get_balances_observation(
            fetcher_id=interest_application_ACCRUED_INTEREST_EFF_FETCHER_ID
        ).balances
    if balances_one_repayment_period_ago is None:
        balances_one_repayment_period_ago = vault.get_balances_observation(
            fetcher_id=interest_application_ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID
        ).balances
    if application_precision is None:
        application_precision = interest_application_get_application_precision(vault=vault)
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name="denomination")
    return interest_application__get_interest_to_apply(
        balances_at_application=balances_at_application,
        balances_one_repayment_period_ago=balances_one_repayment_period_ago,
        denomination=denomination,
        application_precision=application_precision,
        effective_datetime=effective_datetime,
        previous_application_datetime=previous_application_datetime,
    )


def interest_application_get_application_precision(vault: Any) -> int:
    return int(
        utils_get_parameter(vault=vault, name=interest_application_PARAM_APPLICATION_PRECISION)
    )


def interest_application_get_application_internal_account(vault: Any) -> str:
    application_internal_account: str = utils_get_parameter(
        vault=vault, name=interest_application_PARAM_INTEREST_RECEIVED_ACCOUNT
    )
    return application_internal_account


interest_application_InterestApplication = lending_interfaces_InterestApplication(
    apply_interest=interest_application_apply_interest,
    get_interest_to_apply=interest_application_get_interest_to_apply,
    get_application_precision=interest_application_get_application_precision,
)

# Objects below have been imported from:
#    variable.py
# md5:8bdd1a99e6d1305e392203f5e65c2065

variable_PARAM_ANNUAL_INTEREST_RATE_CAP = "annual_interest_rate_cap"
variable_PARAM_ANNUAL_INTEREST_RATE_FLOOR = "annual_interest_rate_floor"
variable_PARAM_VARIABLE_RATE_ADJUSTMENT = "variable_rate_adjustment"
variable_PARAM_VARIABLE_INTEREST_RATE = "variable_interest_rate"
variable_parameters = [
    Parameter(
        name=variable_PARAM_VARIABLE_RATE_ADJUSTMENT,
        level=ParameterLevel.INSTANCE,
        description="Account level adjustment to be added to variable interest rate, can be positive, negative or zero.",
        display_name="Variable Rate Adjustment",
        shape=NumberShape(step=Decimal("0.01")),
        default_value=Decimal("0.00"),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=variable_PARAM_VARIABLE_INTEREST_RATE,
        level=ParameterLevel.TEMPLATE,
        description="The annual interest rate.",
        display_name="Variable Interest Rate (p.a.)",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.000001")),
        default_value=Decimal("0.129971"),
    ),
    Parameter(
        name=variable_PARAM_ANNUAL_INTEREST_RATE_CAP,
        level=ParameterLevel.TEMPLATE,
        description="The maximum annual interest rate for a variable interest loan.",
        display_name="Variable Annual Interest Rate Cap (p.a.)",
        shape=OptionalShape(shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.000001"))),
        default_value=OptionalValue(value=Decimal("1")),
    ),
    Parameter(
        name=variable_PARAM_ANNUAL_INTEREST_RATE_FLOOR,
        level=ParameterLevel.TEMPLATE,
        description="The minimum annual interest rate for a variable interest loan.",
        display_name="Variable Annual Interest Rate Floor (p.a.)",
        shape=OptionalShape(shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.000001"))),
        default_value=OptionalValue(value=Decimal("0")),
    ),
]


def variable_get_daily_interest_rate(
    vault: Any,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    annual_rate = variable_get_annual_interest_rate(
        vault=vault, effective_datetime=effective_datetime
    )
    days_in_year = utils_get_parameter(
        vault, "days_in_year", is_union=True, at_datetime=effective_datetime
    )
    return utils_yearly_to_daily_rate(effective_datetime, annual_rate, days_in_year)


def variable_get_monthly_interest_rate(
    vault: Any,
    effective_datetime: Optional[datetime] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    annual_rate = variable_get_annual_interest_rate(
        vault=vault, effective_datetime=effective_datetime
    )
    return utils_yearly_to_monthly_rate(annual_rate)


def variable_get_annual_interest_rate(
    vault: Any,
    effective_datetime: Optional[datetime] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    """
    Determines the annual interest rate, including any variable rate adjustment and
    accounts for any maximum or minimum interest rate limits that may be set.
    """
    annual_rate = Decimal(
        utils_get_parameter(
            vault=vault, name=variable_PARAM_VARIABLE_INTEREST_RATE, at_datetime=effective_datetime
        )
    ) + Decimal(
        utils_get_parameter(
            vault=vault,
            name=variable_PARAM_VARIABLE_RATE_ADJUSTMENT,
            at_datetime=effective_datetime,
        )
    )
    interest_rate_cap: Decimal = utils_get_parameter(
        vault=vault,
        name=variable_PARAM_ANNUAL_INTEREST_RATE_CAP,
        is_optional=True,
        default_value=Decimal("inf"),
        at_datetime=effective_datetime,
    )
    interest_rate_floor: Decimal = utils_get_parameter(
        vault=vault,
        name=variable_PARAM_ANNUAL_INTEREST_RATE_FLOOR,
        is_optional=True,
        default_value=Decimal("-inf"),
        at_datetime=effective_datetime,
    )
    return max(min(annual_rate, interest_rate_cap), interest_rate_floor)


variable_interest_rate_interface = lending_interfaces_InterestRate(
    get_daily_interest_rate=variable_get_daily_interest_rate,
    get_monthly_interest_rate=variable_get_monthly_interest_rate,
    get_annual_interest_rate=variable_get_annual_interest_rate,
)

# Objects below have been imported from:
#    early_repayment.py
# md5:f999fa0e14d31eabc867091bfbd3904d


def early_repayment_is_posting_an_early_repayment(
    vault: Any,
    repayment_amount: Decimal,
    early_repayment_fees: Optional[list[lending_interfaces_EarlyRepaymentFee]],
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    precision: int = 2,
) -> bool:
    """
    Determine whether the repayment amount is equal to the total amount required to fully pay off
    and close the account. A repayment posting amount will be less than 0 since this is for
    asset/lending products.

    :param vault: vault object for the relevant account
    :param repayment_amount: the amount being repaid
    :param early_repayment_fees: early repayment fee features
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :param precision: the number of decimal places to round to
    :return: true if the repayment amount matches the required amount to do a full early repayment
    """
    if repayment_amount >= Decimal("0"):
        return False
    balances = early_repayment__get_balances(vault=vault, balances=balances)
    denomination = early_repayment__get_denomination(vault=vault, denomination=denomination)
    if early_repayment__is_zero_principal(balances=balances, denomination=denomination):
        return False
    return abs(repayment_amount) == early_repayment_get_total_early_repayment_amount(
        vault=vault,
        denomination=denomination,
        early_repayment_fees=early_repayment_fees,
        balances=balances,
        precision=precision,
    )


def early_repayment_get_total_early_repayment_amount(
    vault: Any,
    early_repayment_fees: Optional[list[lending_interfaces_EarlyRepaymentFee]],
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    precision: int = 2,
    debt_addresses: list[str] = lending_addresses_ALL_OUTSTANDING,
    check_for_outstanding_accrued_interest_on_zero_principal: bool = False,
) -> Decimal:
    """
    Get the exact repayment amount required for a full early repayment.

    :param vault: vault object for the relevant account
    :param early_repayment_fees: early repayment fee features
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :param precision: the number of decimal places to round to
    :param debt_addresses: outstanding debt addresses
    :param check_for_outstanding_accrued_interest_on_zero_principal: if outstanding balances on
    loans that have zero principal should count as early repayment
    :return: the exact repayment amount required for a full early repayment
    """
    balances = early_repayment__get_balances(vault=vault, balances=balances)
    denomination = early_repayment__get_denomination(vault=vault, denomination=denomination)
    if (
        not check_for_outstanding_accrued_interest_on_zero_principal
        and early_repayment__is_zero_principal(balances=balances, denomination=denomination)
    ):
        return utils_round_decimal(Decimal("0"), precision)
    return early_repayment__get_sum_of_early_repayment_fees_and_outstanding_debt(
        vault=vault,
        early_repayment_fees=early_repayment_fees or [],
        balances=balances,
        denomination=denomination,
        precision=precision,
        debt_addresses=debt_addresses,
    )


def early_repayment__is_zero_principal(denomination: str, balances: BalanceDefaultDict) -> bool:
    """
    Return true if there is a zero principal balance.

    :param denomination: denomination of the relevant loan
    :param balances: balances to base calculations on
    :return: true if there is a zero principal balance
    """
    return utils_sum_balances(
        balances=balances, addresses=[lending_addresses_PRINCIPAL], denomination=denomination
    ) <= Decimal("0")


def early_repayment__get_denomination(vault: Any, denomination: Optional[str] = None) -> str:
    """
    Get the denomination of the account, allowing for a None to be passed in.

    :param vault: vault object for the relevant account
    :param denomination: denomination of the relevant loan
    :return: the denomination
    """
    return (
        utils_get_parameter(vault=vault, name="denomination")
        if denomination is None
        else denomination
    )


def early_repayment__get_balances(
    vault: Any, balances: Optional[BalanceDefaultDict] = None
) -> BalanceDefaultDict:
    """
    Return the balances that are passed in or get the live balances of the account.

    :param vault: vault object for the relevant account
    :param balances: balances to base calculations on
    :return: the balances
    """
    return (
        vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
        if balances is None
        else balances
    )


def early_repayment__get_sum_of_early_repayment_fees_and_outstanding_debt(
    vault: Any,
    early_repayment_fees: list[lending_interfaces_EarlyRepaymentFee],
    balances: BalanceDefaultDict,
    denomination: str,
    precision: int,
    debt_addresses: list[str],
) -> Decimal:
    """
    Get the exact repayment amount required for a full early repayment.

    :param vault: vault object for the relevant account
    :param early_repayment_fees: early repayment fee features
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :param precision: the number of decimal places to round to
    :param debt_addresses: outstanding debt addresses
    :return: the exact repayment amount required for a full early repayment
    """
    early_repayment_fees_sum = Decimal("0")
    for early_repayment_fee in early_repayment_fees:
        early_repayment_fees_sum += early_repayment_fee.get_early_repayment_fee_amount(
            vault=vault, balances=balances, denomination=denomination, precision=precision
        )
    total_outstanding_debt = derived_params_get_total_outstanding_debt(
        balances=balances, denomination=denomination, debt_addresses=debt_addresses
    )
    return total_outstanding_debt + early_repayment_fees_sum


# Objects below have been imported from:
#    interest_capitalisation.py
# md5:6bf6cc7379aed3c7edf993397ba50d01

interest_capitalisation_PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT = (
    "capitalised_interest_receivable_account"
)
interest_capitalisation_PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT = (
    "capitalised_interest_received_account"
)


def interest_capitalisation_handle_overpayments_to_penalties_pending_capitalisation(
    vault: Any, denomination: str, balances: BalanceDefaultDict
) -> list[CustomInstruction]:
    if (
        utils_balance_at_coordinates(
            balances=balances,
            address=lending_addresses_ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
            denomination=denomination,
        )
        <= 0
    ):
        return []
    application_precision = interest_application_get_application_precision(vault=vault)
    capitalised_interest_received_account = (
        interest_capitalisation_get_capitalised_interest_received_account(vault=vault)
    )
    capitalised_interest_receivable_account = (
        interest_capitalisation_get_capitalised_interest_receivable_account(vault=vault)
    )
    return interest_capitalisation_capitalise_interest(
        account_id=vault.account_id,
        application_precision=application_precision,
        balances=balances,
        capitalised_interest_receivable_account=capitalised_interest_receivable_account,
        capitalised_interest_received_account=capitalised_interest_received_account,
        denomination=denomination,
        interest_address_pending_capitalisation=lending_addresses_ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
        application_customer_address=addresses_DEFAULT,
    )


def interest_capitalisation_capitalise_interest(
    account_id: str,
    application_precision: int,
    balances: BalanceDefaultDict,
    capitalised_interest_receivable_account: str,
    capitalised_interest_received_account: str,
    denomination: str,
    interest_address_pending_capitalisation: str,
    account_type: str = "",
    application_customer_address: str = lending_addresses_PRINCIPAL,
) -> list[CustomInstruction]:
    """
    Create postings to apply any accrued interest pending capitalisation and track capitalised
    amount. Uses standard accrual posting format for application
    """
    event_type = "END_OF_REPAYMENT_HOLIDAY"
    accrued_capitalised_interest = utils_balance_at_coordinates(
        balances=balances,
        address=interest_address_pending_capitalisation,
        denomination=denomination,
    )
    interest_to_apply = utils_round_decimal(
        amount=accrued_capitalised_interest, decimal_places=application_precision
    )
    if interest_to_apply <= 0:
        return []
    else:
        postings = accruals_accrual_application_postings(
            customer_account=account_id,
            denomination=denomination,
            accrual_amount=accrued_capitalised_interest,
            application_amount=interest_to_apply,
            accrual_customer_address=interest_address_pending_capitalisation,
            accrual_internal_account=capitalised_interest_receivable_account,
            application_customer_address=application_customer_address,
            application_internal_account=capitalised_interest_received_account,
            payable=False,
        ) + utils_create_postings(
            amount=interest_to_apply,
            debit_account=account_id,
            credit_account=account_id,
            debit_address=lending_addresses_CAPITALISED_INTEREST_TRACKER,
            credit_address=addresses_INTERNAL_CONTRA,
        )
        return [
            CustomInstruction(
                postings=postings,
                instruction_details={
                    "description": "Capitalise interest accrued to principal",
                    "event": event_type,
                    "gl_impacted": "True",
                    "account_type": account_type,
                },
            )
        ]


def interest_capitalisation_get_capitalised_interest_received_account(vault: Any) -> str:
    return utils_get_parameter(
        vault=vault, name=interest_capitalisation_PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT
    )


def interest_capitalisation_get_capitalised_interest_receivable_account(vault: Any) -> str:
    return utils_get_parameter(
        vault=vault, name=interest_capitalisation_PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT
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


def payments_generate_repayment_postings(
    vault: Any,
    hook_arguments: PostPostingHookArguments,
    repayment_hierarchy: Optional[list[str]] = None,
    overpayment_features: Optional[list[lending_interfaces_Overpayment]] = None,
    early_repayment_fees: Optional[list[lending_interfaces_EarlyRepaymentFee]] = None,
) -> list[CustomInstruction]:
    """
    A top level wrapper that generates a list of custom instructions to spread a regular payment
    across different balance addresses based on the repayment hierarchy and debit addresses.
    Optionally handles overpayments if any overpayment features are passed in.

    :param vault: Vault object used for data extraction
    :param hook_arguments: The post posting hook arguments
    :param repayment_hierarchy: Order in which a repayment amount is to be
    distributed across addresses. Defaults to standard lending repayment hierarchy
    :param overpayment_features: List of features responsible for handling any excess
    overpayment amount after all repayments have been made. This can be omitted if
    overpayments can be disregarded. Note that handle_overpayment will be called for
    each feature passed into the list.
    :param early_repayment_fees: List of early repayment fee features for handling the amounts of
    early repayment fees that are being charged, but only applicable if the repayment amount is
    correct for making an early repayment to fully pay off and close the account.
    """
    denomination: str = utils_get_parameter(vault=vault, name="denomination")
    if repayment_hierarchy is None:
        repayment_hierarchy = lending_addresses_REPAYMENT_HIERARCHY
    repayment_amount: Decimal = (
        hook_arguments.posting_instructions[0]
        .balances()[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED]
        .net
    )
    balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    posting_instructions: list[CustomInstruction] = []
    repayment_postings: list[Posting] = []
    overpayment_amount = Decimal("0")
    if repayment_amount < 0:
        (
            repayment_per_address,
            overpayment_amount,
        ) = payments_distribute_repayment_for_single_target(
            balances=balances,
            repayment_amount=abs(repayment_amount),
            denomination=denomination,
            repayment_hierarchy=repayment_hierarchy,
        )
        for (repayment_address, repayment_address_amount) in repayment_per_address.items():
            if repayment_address_amount[1] == Decimal(0):
                continue
            repayment_postings += payments_redistribute_postings(
                debit_account=vault.account_id,
                amount=repayment_address_amount[1],
                denomination=denomination,
                credit_account=vault.account_id,
                credit_address=repayment_address,
            )
        if repayment_postings:
            posting_instructions += [
                CustomInstruction(
                    postings=repayment_postings,
                    instruction_details={
                        "description": "Process a repayment",
                        "event": "PROCESS_REPAYMENTS",
                    },
                )
            ]
    if overpayment_amount > 0 and overpayment_features is not None:
        for overpayment_feature in overpayment_features:
            overpayment_postings = overpayment_feature.handle_overpayment(
                vault=vault,
                overpayment_amount=overpayment_amount,
                balances=balances,
                denomination=denomination,
            )
            if overpayment_postings:
                posting_instructions += [
                    CustomInstruction(
                        postings=overpayment_postings,
                        instruction_details={
                            "description": "Process repayment overpayment",
                            "event": "PROCESS_REPAYMENTS",
                        },
                    )
                ]
    if early_repayment_is_posting_an_early_repayment(
        vault=vault,
        repayment_amount=repayment_amount,
        early_repayment_fees=early_repayment_fees,
        balances=balances,
        denomination=denomination,
    ):
        posting_instructions.extend(
            interest_capitalisation_handle_overpayments_to_penalties_pending_capitalisation(
                vault=vault, denomination=denomination, balances=balances
            )
        )
        if early_repayment_fees:
            for early_repayment_fee in early_repayment_fees:
                amount_to_charge = early_repayment_fee.get_early_repayment_fee_amount(
                    vault=vault, balances=balances, denomination=denomination
                )
                posting_instructions.extend(
                    early_repayment_fee.charge_early_repayment_fee(
                        vault=vault,
                        account_id=vault.account_id,
                        amount_to_charge=amount_to_charge,
                        fee_name=early_repayment_fee.fee_name,
                        denomination=denomination,
                    )
                )
    return posting_instructions


# Objects below have been imported from:
#    redraw.py
# md5:0e855ce1173611f98393b0fb4ca14b9b

redraw_PARAM_AVAILABLE_REDRAW_FUNDS = "available_redraw_funds"
redraw_REDRAW_ADDRESS = "REDRAW"
redraw_derived_parameters = [
    Parameter(
        name=redraw_PARAM_AVAILABLE_REDRAW_FUNDS,
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="Total available redraw funds",
        display_name="Available Redraw Funds",
    )
]


def redraw_handle_overpayment(
    vault: Any,
    overpayment_amount: Decimal,
    denomination: str,
    balances: Optional[BalanceDefaultDict] = None,
) -> list[Posting]:
    """Handle overpayments by rebalancing the amount to the REDRAW address
    :param vault: the vault object for the account receiving the overpayment
    :param overpayment_amount: the amount being overpaid
    :param denomination: the denomination of the overpayment
    :param balances: unused, but required to satisfy the overpayment interface
    :return: postings to handle the overpayment
    """
    return utils_create_postings(
        debit_account=vault.account_id,
        denomination=denomination,
        amount=overpayment_amount,
        credit_account=vault.account_id,
        credit_address=redraw_REDRAW_ADDRESS,
    )


redraw_OverpaymentFeature = lending_interfaces_Overpayment(
    handle_overpayment=redraw_handle_overpayment
)


def redraw_auto_repayment(
    balances: BalanceDefaultDict,
    due_amount_posting_instructions: list[CustomInstruction],
    denomination: str,
    account_id: str,
    repayment_hierarchy: list[str],
) -> list[CustomInstruction]:
    """
    Creates posting instructions to automatically repay due balances from the redraw balance

    :param balances: The balances that include the current redraw balance
    :param due_amount_posting_instructions: The postings for any due amounts
    to be committed to the ledger
    :param denomination: The denomination of the account
    :param account_id: The id of the account
    :param repayment_hierarchy: Order in which a repayment amount is to be
    distributed across due addresses
    :return: The custom instructions that automatically repay any due balances
    """
    redraw_balance = utils_balance_at_coordinates(
        balances=balances, address=redraw_REDRAW_ADDRESS, denomination=denomination
    )
    if redraw_balance >= Decimal("0") or not due_amount_posting_instructions:
        return []
    due_amount_mapping = {}
    for due_instruction in due_amount_posting_instructions:
        balance_dict = due_instruction.balances(account_id=account_id, tside=Tside.ASSET)
        for balance in balance_dict.keys():
            if balance.account_address in repayment_hierarchy:
                due_amount_mapping.update({balance.account_address: balance_dict[balance].net})
    auto_repayment_postings: list[Posting] = []
    remaining_redraw_balance = abs(redraw_balance)
    for address in repayment_hierarchy:
        if remaining_redraw_balance == Decimal("0"):
            break
        repayment_amount = min(
            remaining_redraw_balance, due_amount_mapping.get(address, Decimal("0"))
        )
        if repayment_amount > Decimal("0"):
            auto_repayment_postings += payments_redistribute_postings(
                debit_account=account_id,
                denomination=denomination,
                amount=repayment_amount,
                credit_account=account_id,
                credit_address=address,
                debit_address=redraw_REDRAW_ADDRESS,
            )
            remaining_redraw_balance -= repayment_amount
    if auto_repayment_postings:
        return [
            CustomInstruction(
                postings=auto_repayment_postings,
                instruction_details={
                    "description": "Auto repay due balances from the redraw balance",
                    "event": "PROCESS_AUTO_REPAYMENT_FROM_REDRAW_BALANCE",
                },
                override_all_restrictions=True,
            )
        ]
    return []


def redraw_get_available_redraw_funds(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    """
    Returns the available redraw amount

    :param balances: The current balances for the loan account
    which should include the redraw balance
    :param denomination: The denomination of the account
    :return: The remaining amount in the redraw balance (always positive)
    """
    return abs(
        utils_balance_at_coordinates(
            balances=balances,
            address=redraw_REDRAW_ADDRESS,
            denomination=denomination,
            decimal_places=2,
        )
    )


def redraw_reject_closure_when_outstanding_redraw_funds(
    balances: BalanceDefaultDict, denomination: str
) -> Optional[Rejection]:
    """
    Returns a rejection if the redraw balance still contains funds

    :param balances: The current balances for the loan account
    which should include the redraw balance
    :param denomination: The denomination of the account
    :return: A rejection if the redraw balance contains a non-zero amount
    """
    if utils_balance_at_coordinates(
        balances=balances, address=redraw_REDRAW_ADDRESS, denomination=denomination
    ) != Decimal("0"):
        return Rejection(
            message="The loan cannot be closed until all remaining redraw funds are cleared.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
    return None


def redraw_validate_redraw_funds(
    balances: BalanceDefaultDict, posting_amount: Decimal, denomination: str
) -> Optional[Rejection]:
    """
    Reject a posting if the withdrawal amount is greater than the current redraw balance.

    :param balances: The balances, which should contain the balances for the redraw address
    :param posting_amount: The amount to validate against the current redraw amount
    :param denomination: The denomination of the posting
    """
    redraw_balance = utils_balance_at_coordinates(
        balances=balances, address=redraw_REDRAW_ADDRESS, denomination=denomination
    )
    if posting_amount > 0 and posting_amount > abs(redraw_balance):
        return Rejection(
            message=f"Transaction amount {posting_amount} {denomination} is greater than the available redraw funds of {abs(redraw_balance)} {denomination}.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
    return None


# Objects below have been imported from:
#    home_loan_redraw.py
# md5:c860dd069ccdda5216ef301f51351669

PRODUCT_NAME = "HOME_LOAN_REDRAW"
REPAYMENT_HIERARCHY = [lending_addresses_PRINCIPAL_DUE, lending_addresses_INTEREST_DUE]
DEBT_ADDRESSES = REPAYMENT_HIERARCHY + [lending_addresses_PRINCIPAL]
data_fetchers = [
    *interest_accrual_data_fetchers,
    interest_application_accrued_interest_eff_fetcher,
    interest_application_accrued_interest_one_month_ago_fetcher,
    fetchers_EFFECTIVE_OBSERVATION_FETCHER,
    fetchers_LIVE_BALANCES_BOF,
]
PARAM_DENOMINATION = "denomination"
parameters = [
    Parameter(
        name=PARAM_DENOMINATION,
        level=ParameterLevel.TEMPLATE,
        description="Denomination",
        display_name="Denomination",
        shape=StringShape(),
        default_value="GBP",
    ),
    *derived_params_all_parameters,
    *disbursement_parameters,
    *due_amount_calculation_schedule_parameters,
    due_amount_calculation_next_repayment_date_parameter,
    *interest_accrual_account_parameters,
    *interest_accrual_accrual_parameters,
    *interest_accrual_schedule_parameters,
    *variable_parameters,
    interest_application_application_precision_param,
    *interest_application_account_parameters,
    lending_parameters_total_repayment_count_parameter,
    *redraw_derived_parameters,
]
event_types = [
    *interest_accrual_event_types(PRODUCT_NAME),
    *due_amount_calculation_event_types(PRODUCT_NAME),
]
PAID_OFF_NOTIFICATION = f"{PRODUCT_NAME}_PAID_OFF"
notification_types = [PAID_OFF_NOTIFICATION]


def _calculate_due_amounts(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> tuple[list[CustomInstruction], list[AccountNotificationDirective]]:
    """
    A top level wrapper that creates posting instructions for any due amounts
    and any auto-repayments that pay off some or all of those due amounts
    from the current redraw balance.

    :param vault: The vault object from the scheduled event hook
    :param hook_arguments: The hook arguments from the scheduled event hook
    :return: A tuple containing the list of due posting instructions and
    a list of account notifications
    """
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    due_amount_posting_instructions = due_amount_calculation_schedule_logic(
        vault=vault,
        hook_arguments=hook_arguments,
        account_type=PRODUCT_NAME,
        interest_application_feature=interest_application_InterestApplication,
        amortisation_feature=declining_principal_AmortisationFeature,
    )
    auto_repayment_posting_instructions = redraw_auto_repayment(
        balances=balances,
        due_amount_posting_instructions=due_amount_posting_instructions,
        denomination=denomination,
        account_id=vault.account_id,
        repayment_hierarchy=REPAYMENT_HIERARCHY,
    )
    account_notification_directives = _check_and_send_closure_notification(
        repayment_posting_instructions=auto_repayment_posting_instructions,
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
    )
    return (
        due_amount_posting_instructions + auto_repayment_posting_instructions,
        account_notification_directives,
    )


def _calculate_next_repayment_date(
    vault: Any, derived_parameter_hook_args: DerivedParameterHookArguments
) -> datetime:
    """
    Determines the next repayment date based on the due amount calculation date and the
    effective datetime from the derived parameter hook.
    IMPORTANT: This function assumes that the due amount calculation date does not change,
    which is true for the current version of home loan redraw.

    :param vault: The vault object from the derived parameter hook
    :param derived_parameter_hook_args: The hook arguments from the derived parameter hook
    :return: The next repayment date
    """
    effective_datetime: datetime = derived_parameter_hook_args.effective_datetime
    first_due_datetime = due_amount_calculation_get_first_due_amount_calculation_datetime(
        vault=vault
    )
    if effective_datetime.date() <= first_due_datetime.date():
        return first_due_datetime
    due_amount_calc_day = utils_get_parameter(
        vault=vault, name=due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY
    )
    potential_next_due_amount_calc = datetime(
        year=effective_datetime.year,
        month=effective_datetime.month,
        day=due_amount_calc_day,
        tzinfo=ZoneInfo("UTC"),
    )
    return (
        potential_next_due_amount_calc
        if effective_datetime.date() <= potential_next_due_amount_calc.date()
        else potential_next_due_amount_calc + relativedelta(months=1)
    )


def _check_and_send_closure_notification(
    repayment_posting_instructions: list[CustomInstruction],
    balances: BalanceDefaultDict,
    denomination: str,
    account_id: str,
) -> list[AccountNotificationDirective]:
    """
    Determines whether the repayment(s) clear(s) the outstanding debt
    and returns an account notification directive if so.
    Handles both auto-repayments via redraw funds and customer initiated repayments.

    :param repayment_posting_instructions: The repayment posting instructions
    :param balances: The current balances used to check the outstanding debt and redraw amounts
    :param denomination: The denomination of the account and the repayment
    :param account_id: The id of the account the repayment is for
    :return: A list of account closure notifications
    """
    account_notification_directives: list[AccountNotificationDirective] = []
    if close_loan_does_repayment_fully_repay_loan(
        repayment_posting_instructions=repayment_posting_instructions,
        balances=balances,
        denomination=denomination,
        account_id=account_id,
    ):
        account_notification_directives += [
            AccountNotificationDirective(
                notification_type=PAID_OFF_NOTIFICATION,
                notification_details={"account_id": account_id},
            )
        ]
    return account_notification_directives


def _process_withdrawal(
    account_id: str, withdrawal_amount: Decimal, denomination: str
) -> list[CustomInstruction]:
    """
    Creates posting instructions to redraw the withdrawal amount from the redraw balance

    :param account_id: The id of the account
    :param withdrawal_amount: The amount to withdrawal from the redraw balance
    :param denomination: The denomination of the account
    :return: A list of posting instructions that will withdrawal from the redraw balance
    """
    postings = utils_create_postings(
        debit_account=account_id,
        debit_address=redraw_REDRAW_ADDRESS,
        denomination=denomination,
        amount=withdrawal_amount,
        credit_account=account_id,
        credit_address=DEFAULT_ADDRESS,
    )
    return [
        CustomInstruction(
            postings=postings,
            instruction_details={
                "description": "Redraw funds from the redraw account",
                "event": "REDRAW_FUNDS_WITHDRAWAL",
            },
        )
    ]
