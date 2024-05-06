# Code auto-generated using Inception Smart Contract Renderer Version 2.0.1


# Objects below have been imported from:
#    bnpl.py
# md5:1c311e1e5e630194d820e9ea87946e18

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
    NumberShape,
    ParameterUpdatePermission,
    AccountNotificationDirective,
    DateShape,
    ScheduledEventHookArguments,
    SmartContractEventType,
    SupervisorContractEventType,
    SupervisorScheduledEventHookArguments,
    OptionalShape,
    StringShape,
    AccountIdShape,
    PostingInstructionsDirective,
    PostPostingHookResult,
    ScheduledEventHookResult,
    UpdatePlanEventTypeDirective,
    BalancesFilter,
    BalancesObservation,
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
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from json import loads
import math
from typing import Optional, Any, Iterable, Mapping, Union, Callable, NamedTuple
from zoneinfo import ZoneInfo

api = "4.0.0"
version = "2.0.2"
display_name = "Buy Now Pay Later"
summary = "A no-interest short term loan repaid in equal instalments"
tside = Tside.ASSET
supported_denominations = ["GBP"]


@requires(parameters=True)
def activation_hook(
    vault: Any, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    """
    Performs the following actions when opening an account:
    - Disburse the loan principal to the specified deposit account
    - Charge the first instalment
    - Generate the schedules
    """

    def _get_activation_postings(vault: Any) -> list[PostingInstructionsDirective]:
        denomination = common_parameters_get_denomination_parameter(vault=vault)
        principal = disbursement_get_principal_parameter(vault=vault)
        deposit_account_id = disbursement_get_deposit_account_parameter(vault=vault)
        effective_datetime = hook_arguments.effective_datetime
        posting_instructions: list[CustomInstruction] = []
        posting_instructions += disbursement_get_disbursement_custom_instruction(
            account_id=vault.account_id,
            deposit_account_id=deposit_account_id,
            principal=principal,
            denomination=denomination,
            principal_address=lending_addresses_PRINCIPAL,
        )
        posting_instructions += emi_in_advance_charge(
            vault=vault,
            effective_datetime=effective_datetime,
            amortisation_feature=declining_principal_AmortisationFeature,
        )
        posting_instructions += [
            CustomInstruction(
                postings=due_amount_calculation_update_due_amount_calculation_counter(
                    account_id=vault.account_id, denomination=denomination
                ),
                instruction_details={
                    "description": "Update due amount calculation counter on account activation",
                    "event": events_ACCOUNT_ACTIVATION,
                },
            )
        ]
        posting_instruction_directive = PostingInstructionsDirective(
            posting_instructions=posting_instructions,
            client_batch_id=f"{events_ACCOUNT_ACTIVATION}_{vault.get_hook_execution_id()}",
            value_datetime=effective_datetime,
        )
        return [posting_instruction_directive]

    def _get_scheduled_events(vault: Any) -> dict[str, ScheduledEvent]:
        first_due_amount_calc_datetime = vault.get_account_creation_datetime()
        repayment_period = overdue_get_repayment_period_parameter(vault=vault)
        grace_period = delinquency_get_grace_period_parameter(vault=vault)
        late_repayment_period = repayment_period + grace_period
        total_repayment_count = lending_parameters_get_total_repayment_count_parameter(vault=vault)
        repayment_frequency = configurable_repayment_frequency_get_repayment_frequency_parameter(
            vault=vault
        )
        repayment_frequency_delta = _get_repayment_frequency_delta(vault=vault)
        second_due_amount_calc_datetime = first_due_amount_calc_datetime + repayment_frequency_delta
        first_repayment_offset = emi_in_advance_EMI_IN_ADVANCE_OFFSET
        total_repayment_period_delta = repayment_frequency_delta * (
            total_repayment_count - first_repayment_offset
        )
        delinquency_check_datetime = (
            first_due_amount_calc_datetime
            + total_repayment_period_delta
            + relativedelta(days=repayment_period + grace_period)
        )
        scheduled_events: dict[str, ScheduledEvent] = {
            **configurable_repayment_frequency_get_due_amount_calculation_schedule(
                vault=vault,
                first_due_amount_calculation_datetime=second_due_amount_calc_datetime,
                repayment_frequency=repayment_frequency,
            ),
            **overdue_scheduled_events(
                vault=vault, first_due_amount_calculation_datetime=first_due_amount_calc_datetime
            ),
            **late_repayment_scheduled_events(
                vault=vault,
                start_datetime=first_due_amount_calc_datetime
                + relativedelta(days=late_repayment_period),
                skip=True if grace_period == 0 else False,
            ),
            **delinquency_scheduled_events(
                vault=vault, start_datetime=delinquency_check_datetime, is_one_off=True
            ),
            **due_amount_notification_scheduled_events(
                vault=vault, next_due_amount_calc_datetime=second_due_amount_calc_datetime
            ),
        }
        return scheduled_events

    return ActivationHookResult(
        posting_instructions_directives=_get_activation_postings(vault=vault),
        scheduled_events_return_value=_get_scheduled_events(vault=vault),
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
    """
    Perform the following actions when an account is being closed:
    - Reject if there is outstanding debt
    - Nets off the EMI, and any other accounting addresses from other features,
    that should be cleared before the loan is closed
    """
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    if outstanding_debt_rejection := close_loan_reject_closure_when_outstanding_debt(
        balances=balances, denomination=denomination
    ):
        return DeactivationHookResult(rejection=outstanding_debt_rejection)
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


@requires(parameters=True)
@fetch_account_data(balances=["EFFECTIVE_FETCHER"])
def derived_parameter_hook(
    vault: Any, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    """
    Calculate the values of the derived parameters.
    """
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    total_repayment_count = (
        lending_parameters_get_total_repayment_count_parameter(vault=vault)
        - emi_in_advance_EMI_IN_ADVANCE_OFFSET
    )
    repayment_frequency = configurable_repayment_frequency_get_repayment_frequency_parameter(
        vault=vault
    )
    account_creation_datetime = vault.get_account_creation_datetime()
    principal = disbursement_get_principal_parameter(vault=vault)
    equated_instalment_amount = due_amount_calculation_get_emi(
        balances=balances, denomination=denomination
    )
    loan_end_datetime = configurable_repayment_frequency_get_next_due_amount_calculation_date(
        vault=vault,
        effective_date=datetime.max.replace(tzinfo=UTC_ZONE),
        total_repayment_count=total_repayment_count,
        repayment_frequency=repayment_frequency,
    )
    next_repayment_datetime = configurable_repayment_frequency_get_next_due_amount_calculation_date(
        vault=vault,
        effective_date=hook_arguments.effective_datetime,
        total_repayment_count=total_repayment_count,
        repayment_frequency=repayment_frequency,
    )
    remaining_term = configurable_repayment_frequency_get_elapsed_and_remaining_terms(
        account_creation_date=account_creation_datetime,
        effective_date=hook_arguments.effective_datetime,
        total_repayment_count=total_repayment_count,
        repayment_frequency=repayment_frequency,
    ).remaining
    remaining_term_str = f"{str(remaining_term)} {configurable_repayment_frequency_TERM_UNIT_MAP[repayment_frequency]}"
    total_outstanding_debt = derived_params_get_total_outstanding_debt(
        balances=balances, denomination=denomination
    )
    total_remaining_principal = derived_params_get_total_remaining_principal(
        balances=balances, denomination=denomination
    )
    principal_paid_to_date = derived_params_get_principal_paid_to_date(
        original_principal=principal, balances=balances, denomination=denomination
    )
    derived_parameters: dict[str, utils_ParameterValueTypeAlias] = {
        PARAM_EQUATED_INSTALMENT_AMOUNT: equated_instalment_amount,
        PARAM_LOAN_END_DATE: loan_end_datetime,
        PARAM_NEXT_REPAYMENT_DATE: next_repayment_datetime,
        PARAM_REMAINING_TERM: remaining_term_str,
        PARAM_TOTAL_OUTSTANDING_DEBT: total_outstanding_debt,
        PARAM_TOTAL_REMAINING_PRINCIPAL: total_remaining_principal,
        PARAM_PRINCIPAL_PAID_TO_DATE: principal_paid_to_date,
    }
    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


@requires(parameters=True)
@fetch_account_data(balances=["live_balances_bof"])
def post_posting_hook(
    vault: Any, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    """
    Perform the following actions after a posting is accepted:
    - Skip processing of force override postings
    - Rebalance payment postings from the DEFAULT address to the corresponding repayment addresses
    (e.g. due and penalties)
    - Send notification if repayment fully repays loan
    """
    hook_posting_instructions: utils_PostingInstructionListAlias = (
        hook_arguments.posting_instructions
    )
    if utils_is_force_override(hook_posting_instructions):
        return None
    posting_instructions = payments_generate_repayment_postings(
        vault=vault,
        hook_arguments=hook_arguments,
        repayment_hierarchy=lending_addresses_REPAYMENT_HIERARCHY,
    )
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    account_notification_directives: list[AccountNotificationDirective] = []
    posting_instructions_directives: list[PostingInstructionsDirective] = []
    if close_loan_does_repayment_fully_repay_loan(
        repayment_posting_instructions=posting_instructions,
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        payment_addresses=lending_addresses_ALL_OUTSTANDING,
    ):
        account_notification_directives.append(
            close_loan_send_loan_paid_off_notification(
                account_id=vault.account_id, product_name=PRODUCT_NAME
            )
        )
    if posting_instructions:
        posting_instructions_directives.append(
            PostingInstructionsDirective(
                posting_instructions=posting_instructions,
                client_batch_id=f"REPAYMENT_{vault.get_hook_execution_id()}",
                value_datetime=hook_arguments.effective_datetime,
            )
        )
    if account_notification_directives or posting_instructions_directives:
        return PostPostingHookResult(
            account_notification_directives=account_notification_directives,
            posting_instructions_directives=posting_instructions_directives,
        )
    return None


def pre_parameter_change_hook(
    vault: Any, hook_arguments: PreParameterChangeHookArguments
) -> Optional[PreParameterChangeHookResult]:
    """
    Reject any change to the restricted parameters.
    """
    updated_parameter_values = hook_arguments.updated_parameter_values
    if any((parameter in updated_parameter_values for parameter in RESTRICTED_PARAMETERS)):
        return PreParameterChangeHookResult(
            rejection=Rejection(
                message="T&Cs of this loan cannot be changed once opened.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
    return None


@requires(parameters=True)
@fetch_account_data(balances=["live_balances_bof"])
def pre_posting_hook(
    vault: Any, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    """
    Perform the following posting checks:
    - Force override postings bypass checks
    - Invalid denomination is rejected
    - Only single hard settlement postings are allowed
    - Reject overpayments on total outstanding debt
    - Reject overpayments on current due
    - Debits are not allowed
    - Zero posting is not allowed
    """
    posting_instructions: utils_PostingInstructionListAlias = hook_arguments.posting_instructions
    if utils_is_force_override(posting_instructions):
        return None
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    if denomination_rejection := utils_validate_denomination(
        posting_instructions, accepted_denominations=[denomination]
    ):
        return PrePostingHookResult(rejection=denomination_rejection)
    if posting_rejection := utils_validate_single_hard_settlement_or_transfer(
        posting_instructions=posting_instructions
    ):
        return PrePostingHookResult(rejection=posting_rejection)
    posting = posting_instructions[0]
    posting_amount = utils_get_available_balance(
        balances=posting.balances(), denomination=denomination
    )
    if lending_utils_is_credit(posting_amount):
        posting_amount = abs(posting_amount)
        balances: BalanceDefaultDict = vault.get_balances_observation(
            fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
        ).balances
        total_outstanding_debt = derived_params_get_total_outstanding_debt(
            balances=balances, denomination=denomination
        )
        total_due_amount = derived_params_get_total_due_amount(
            balances=balances, denomination=denomination
        )
        if posting_amount > total_outstanding_debt:
            return PrePostingHookResult(
                rejection=Rejection(
                    message="Cannot pay more than what is owed.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
        if posting_amount > total_due_amount:
            return PrePostingHookResult(
                rejection=Rejection(
                    message="Cannot pay more than what is due.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
        return None
    elif lending_utils_is_debit(posting_amount):
        return PrePostingHookResult(
            rejection=Rejection(
                message="Debiting from this account is not allowed.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
    else:
        return PrePostingHookResult(
            rejection=Rejection(
                message="Cannot post zero amount.", reason_code=RejectionReason.CLIENT_CUSTOM_REASON
            )
        )


@requires(event_type="NOTIFY_DUE_AMOUNT", parameters=True)
@fetch_account_data(event_type="NOTIFY_DUE_AMOUNT", balances=["EFFECTIVE_FETCHER"])
@requires(event_type="CHECK_DELINQUENCY", parameters=True)
@fetch_account_data(event_type="CHECK_DELINQUENCY", balances=["EFFECTIVE_FETCHER"])
@requires(
    event_type="DUE_AMOUNT_CALCULATION",
    last_execution_datetime=["DUE_AMOUNT_CALCULATION"],
    parameters=True,
)
@fetch_account_data(event_type="DUE_AMOUNT_CALCULATION", balances=["EFFECTIVE_FETCHER"])
@requires(event_type="CHECK_OVERDUE", parameters=True)
@fetch_account_data(event_type="CHECK_OVERDUE", balances=["EFFECTIVE_FETCHER"])
@requires(event_type="CHECK_LATE_REPAYMENT", parameters=True)
@fetch_account_data(event_type="CHECK_LATE_REPAYMENT", balances=["EFFECTIVE_FETCHER"])
def scheduled_event_hook(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    """
    Handle the scheduled events for the account when any of the specified events are triggered.
    """
    event_type = hook_arguments.event_type
    custom_instructions: list[CustomInstruction] = []
    notification_directives: list[AccountNotificationDirective] = []
    posting_instructions_directives: list[PostingInstructionsDirective] = []
    update_account_event_type_directives: list[UpdateAccountEventTypeDirective] = []

    def _handle_due_amount_calculation() -> None:
        custom_instructions.extend(
            due_amount_calculation_schedule_logic(
                vault=vault,
                hook_arguments=hook_arguments,
                account_type=PRODUCT_NAME,
                amortisation_feature=declining_principal_AmortisationFeature,
            )
        )
        update_account_event_type_directives.extend(
            _schedule_fortnightly_repayment_frequency(vault=vault, hook_arguments=hook_arguments)
        )

    def _handle_overdue_check() -> None:
        late_repayment_fee = late_repayment_get_late_repayment_fee_parameter(vault=vault)
        (overdue_custom_instructions, overdue_notification_directives) = overdue_schedule_logic(
            vault=vault,
            hook_arguments=hook_arguments,
            account_type=PRODUCT_NAME,
            late_repayment_fee=late_repayment_fee,
        )
        custom_instructions.extend(overdue_custom_instructions)
        notification_directives.extend(overdue_notification_directives)
        update_account_event_type_directives.extend(
            _schedule_overdue_check_event(
                vault=vault, effective_datetime=hook_arguments.effective_datetime
            )
        )
        grace_period = delinquency_get_grace_period_parameter(vault=vault)
        if grace_period == 0:
            custom_instructions.extend(
                late_repayment_schedule_logic(
                    vault=vault,
                    hook_arguments=hook_arguments,
                    denomination=common_parameters_get_denomination_parameter(vault=vault),
                )
            )

    def _handle_late_repayment_check() -> None:
        custom_instructions.extend(
            late_repayment_schedule_logic(
                vault=vault,
                hook_arguments=hook_arguments,
                denomination=common_parameters_get_denomination_parameter(vault=vault),
            )
        )
        update_account_event_type_directives.extend(
            _schedule_check_late_repayment_event(
                vault=vault, effective_datetime=hook_arguments.effective_datetime
            )
        )

    def _handle_delinquency_check() -> None:
        notification_directives.extend(
            delinquency_schedule_logic(
                vault=vault,
                product_name=PRODUCT_NAME,
                addresses=lending_addresses_ALL_OUTSTANDING,
                denomination=common_parameters_get_denomination_parameter(vault=vault),
            )
        )

    def _handle_due_amount_notification() -> None:
        notification_directives.extend(
            _get_repayment_notification(
                vault=vault, due_amount_notification_datetime=hook_arguments.effective_datetime
            )
        )
        repayment_frequency = configurable_repayment_frequency_get_repayment_frequency_parameter(
            vault=vault
        )
        next_due_amount_notification_datetime = (
            due_amount_notification_get_next_due_amount_notification_datetime(
                vault=vault,
                current_due_amount_notification_datetime=hook_arguments.effective_datetime,
                repayment_frequency_delta=configurable_repayment_frequency_FREQUENCY_MAP[
                    repayment_frequency
                ],
            )
        )
        update_account_event_type_directives.append(
            UpdateAccountEventTypeDirective(
                event_type=due_amount_notification_NOTIFY_DUE_AMOUNT_EVENT,
                expression=utils_get_schedule_expression_from_parameters(
                    vault=vault,
                    parameter_prefix=due_amount_notification_DUE_AMOUNT_NOTIFICATION_PREFIX,
                    day=next_due_amount_notification_datetime.day,
                    month=next_due_amount_notification_datetime.month,
                    year=next_due_amount_notification_datetime.year,
                ),
            )
        )

    if event_type == due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT:
        _handle_due_amount_calculation()
    elif event_type == overdue_CHECK_OVERDUE_EVENT:
        _handle_overdue_check()
    elif event_type == late_repayment_CHECK_LATE_REPAYMENT_EVENT:
        _handle_late_repayment_check()
    elif event_type == delinquency_CHECK_DELINQUENCY_EVENT:
        _handle_delinquency_check()
    elif event_type == due_amount_notification_NOTIFY_DUE_AMOUNT_EVENT:
        _handle_due_amount_notification()
    if custom_instructions:
        posting_instructions_directives.append(
            PostingInstructionsDirective(
                posting_instructions=custom_instructions,
                client_batch_id=f"{PRODUCT_NAME}_{event_type}_{vault.get_hook_execution_id()}",
                value_datetime=hook_arguments.effective_datetime,
            )
        )
    if (
        notification_directives
        or posting_instructions_directives
        or update_account_event_type_directives
    ):
        return ScheduledEventHookResult(
            account_notification_directives=notification_directives,
            posting_instructions_directives=posting_instructions_directives,
            update_account_event_type_directives=update_account_event_type_directives,
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
#    events.py
# md5:ee964ddec320f22b8eeab458a02a6835

events_ACCOUNT_ACTIVATION = "ACCOUNT_ACTIVATION"

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


def lending_parameters_get_total_repayment_count_parameter(vault: Any) -> int:
    return int(utils_get_parameter(vault, name=lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT))


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

close_loan_LOAN_PAID_OFF_NOTIFICATION_SUFFIX = "_LOAN_PAID_OFF"
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


def close_loan_notification_type(product_name: str) -> str:
    """
    Creates the notification type
    :param product_name: The product name
    :return: str
    """
    return f"{product_name.upper()}{close_loan_LOAN_PAID_OFF_NOTIFICATION_SUFFIX}"


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


def close_loan_send_loan_paid_off_notification(
    account_id: str, product_name: str
) -> AccountNotificationDirective:
    """
    Instruct a loan paid off notification.

    :param account_id: vault account id
    :param product_name: the name of the product for the notification prefix
    :return: AccountNotificationDirective
    """
    return AccountNotificationDirective(
        notification_type=close_loan_notification_type(product_name),
        notification_details={"account_id": account_id},
    )


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
#    emi.py
# md5:6fd652b0be2b953dfaf528e599cb7c8b

emi_PARAM_EQUATED_INSTALMENT_AMOUNT = "equated_instalment_amount"
emi_equated_instalment_amount_parameter = Parameter(
    name=emi_PARAM_EQUATED_INSTALMENT_AMOUNT,
    shape=NumberShape(min_value=0, step=Decimal("0.01")),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="The amount customer is expected to pay per repayment period.",
    display_name="Equated Instalment Amount",
)
emi_derived_parameters = [emi_equated_instalment_amount_parameter]


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


def due_amount_calculation_event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT}_AST"
            ],
        )
    ]


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

# Objects below have been imported from:
#    configurable_repayment_frequency.py
# md5:3e64c126d8f0c460291c7c3ec6b25284

configurable_repayment_frequency_LoanTerms = NamedTuple(
    "LoanTerms", [("elapsed", int), ("remaining", int)]
)
configurable_repayment_frequency_MONTHLY = "monthly"
configurable_repayment_frequency_WEEKLY = "weekly"
configurable_repayment_frequency_FORTNIGHTLY = "fortnightly"
configurable_repayment_frequency_FREQUENCY_MAP = {
    configurable_repayment_frequency_WEEKLY: relativedelta(days=7),
    configurable_repayment_frequency_FORTNIGHTLY: relativedelta(days=14),
    configurable_repayment_frequency_MONTHLY: relativedelta(months=1),
}
configurable_repayment_frequency_TERM_UNIT_MAP = {
    configurable_repayment_frequency_WEEKLY: "week(s)",
    configurable_repayment_frequency_FORTNIGHTLY: "fortnight(s)",
    configurable_repayment_frequency_MONTHLY: "month(s)",
}
configurable_repayment_frequency_DATETIME_MIN_UTC = datetime.min.replace(tzinfo=ZoneInfo("UTC"))
configurable_repayment_frequency_DATETIME_MAX_UTC = datetime.max.replace(tzinfo=ZoneInfo("UTC"))
configurable_repayment_frequency_PARAM_REPAYMENT_FREQUENCY = "repayment_frequency"
configurable_repayment_frequency_PARAM_LOAN_END_DATE = "loan_end_date"
configurable_repayment_frequency_PARAM_NEXT_REPAYMENT_DATE = "next_repayment_date"
configurable_repayment_frequency_PARAM_REMAINING_TERM = "remaining_term"
configurable_repayment_frequency_repayment_frequency_parameter = Parameter(
    name=configurable_repayment_frequency_PARAM_REPAYMENT_FREQUENCY,
    shape=OptionalShape(
        shape=UnionShape(
            items=[
                UnionItem(key="weekly", display_name="Weekly"),
                UnionItem(key="fortnightly", display_name="Fortnightly"),
                UnionItem(key="monthly", display_name="Monthly"),
            ]
        )
    ),
    level=ParameterLevel.INSTANCE,
    description="The frequency at which repayments are made.",
    display_name="Repayment Frequency",
    update_permission=ParameterUpdatePermission.FIXED,
    default_value=OptionalValue(UnionItemValue(key="monthly")),
)
configurable_repayment_frequency_loan_end_date_parameter = Parameter(
    name=configurable_repayment_frequency_PARAM_LOAN_END_DATE,
    shape=DateShape(
        min_date=configurable_repayment_frequency_DATETIME_MIN_UTC,
        max_date=configurable_repayment_frequency_DATETIME_MAX_UTC,
    ),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Contractual end date of the loan",
    display_name="Loan End Date",
)
configurable_repayment_frequency_next_repayment_date_parameter = Parameter(
    name=configurable_repayment_frequency_PARAM_NEXT_REPAYMENT_DATE,
    shape=DateShape(
        min_date=configurable_repayment_frequency_DATETIME_MIN_UTC,
        max_date=configurable_repayment_frequency_DATETIME_MAX_UTC,
    ),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Next repayment date",
    display_name="Next Repayment Date",
)
configurable_repayment_frequency_remaining_term_parameter = Parameter(
    name=configurable_repayment_frequency_PARAM_REMAINING_TERM,
    shape=StringShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="The remaining term for the loan",
    display_name="Remaining Term",
)
configurable_repayment_frequency_derived_parameters = [
    configurable_repayment_frequency_loan_end_date_parameter,
    configurable_repayment_frequency_next_repayment_date_parameter,
    configurable_repayment_frequency_remaining_term_parameter,
]


def configurable_repayment_frequency_get_repayment_frequency_parameter(vault: Any) -> str:
    return str(
        utils_get_parameter(
            vault=vault,
            name=configurable_repayment_frequency_PARAM_REPAYMENT_FREQUENCY,
            is_union=True,
            is_optional=True,
            default_value=UnionItemValue(key="monthly"),
        )
    )


def configurable_repayment_frequency_get_due_amount_calculation_schedule(
    vault: Any,
    first_due_amount_calculation_datetime: datetime,
    repayment_frequency: str = "monthly",
) -> dict[str, ScheduledEvent]:
    """
    Get a due amount calculation schedule that occurs at the specified frequency, starting at the
    specified date, and using the `due_amount_calculation_<>` schedule time parameters. The schedule
    will require amending only for `fortnightly` schedules using the
    `get_next_fortnightly_schedule_expression` function.
    :param vault: the Vault object
    :param first_due_amount_calculation_datetime: datetime representing the date on which the first
    due amount calculation should occur. Time component will be ignored
    :param repayment_frequency: the frequency at which repayments occur. One of monthly, weekly or
    fortnightly
    :return: a dictionary containing the due amount calculation schedule
    """
    (hour, minute, second) = utils_get_schedule_time_from_parameters(
        vault, parameter_prefix=due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX
    )
    start_datetime = first_due_amount_calculation_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - relativedelta(seconds=1)
    if repayment_frequency == "monthly":
        due_amount_calculation_schedule = ScheduledEvent(
            start_datetime=start_datetime,
            schedule_method=EndOfMonthSchedule(
                day=first_due_amount_calculation_datetime.day,
                hour=hour,
                minute=minute,
                second=second,
                failover=ScheduleFailover.FIRST_VALID_DAY_BEFORE,
            ),
        )
    else:
        schedule_expression = ScheduleExpression(hour=hour, minute=minute, second=second)
        if repayment_frequency == "weekly":
            schedule_expression.day_of_week = first_due_amount_calculation_datetime.weekday()
        elif repayment_frequency == "fortnightly":
            schedule_expression.day = first_due_amount_calculation_datetime.day
        due_amount_calculation_schedule = ScheduledEvent(
            start_datetime=start_datetime, expression=schedule_expression
        )
    return {due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT: due_amount_calculation_schedule}


def configurable_repayment_frequency_get_next_fortnightly_schedule_expression(
    effective_date: datetime,
) -> ScheduleExpression:
    """
    Get the next fortnightly schedule expression for the account.
    :param effective_date: date as of which the next repayment date is calculated
    :return: the next fortnightly schedule expression
    """
    next_due_date = (
        effective_date
        + configurable_repayment_frequency_FREQUENCY_MAP[
            configurable_repayment_frequency_FORTNIGHTLY
        ]
    )
    return utils_one_off_schedule_expression(next_due_date)


def configurable_repayment_frequency_get_next_due_amount_calculation_date(
    vault: Any, effective_date: datetime, total_repayment_count: int, repayment_frequency: str
) -> datetime:
    """
    Determine the next repayment date for the account. If there are no more repayments left,
    the last repayment date is returned.

    :param vault: Vault object for the account in question
    :param effective_date: date as of which the next repayment date is calculated
    :param total_repayment_count: the number of expected repayments at account creation
    :param repayment_frequency: the account's due amount calculation schedule frequency
    :return: datetime representing the next repayment date
    """
    account_creation_date = vault.get_account_creation_datetime().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    next_repayment_date = account_creation_date
    while next_repayment_date < effective_date and total_repayment_count > 0:
        next_repayment_date += configurable_repayment_frequency_FREQUENCY_MAP[repayment_frequency]
        total_repayment_count -= 1
    return next_repayment_date


def configurable_repayment_frequency_get_elapsed_and_remaining_terms(
    account_creation_date: datetime,
    effective_date: datetime,
    total_repayment_count: int,
    repayment_frequency: str,
) -> configurable_repayment_frequency_LoanTerms:
    """
    Calculates the elapsed and remaining terms for a loan at a given date, based on the total
    repayment count and the repayment frequency.
    :param account_creation_date: date on which the loan was created
    :param effective_date: date as of which the calculation is made
    :param total_repayment_count: total number of repayments at the start of the loan
    :param repayment_frequency: repayment frequency
    return: a dictionary with keys elapsed and remaining, providing number of elapsed and remaining
    terms according to the T&Cs at the start of the loan.
    """
    if repayment_frequency == configurable_repayment_frequency_MONTHLY:
        elapsed_terms = relativedelta(effective_date.date(), account_creation_date.date()).months
    else:
        elapsed_days = (effective_date.date() - account_creation_date.date()).days
        elapsed_terms = (
            elapsed_days // configurable_repayment_frequency_FREQUENCY_MAP[repayment_frequency].days
        )
    return configurable_repayment_frequency_LoanTerms(
        elapsed=elapsed_terms, remaining=total_repayment_count - elapsed_terms
    )


# Objects below have been imported from:
#    delinquency.py
# md5:b99b0ef48bb663761488c57823bac9f4

delinquency_CHECK_DELINQUENCY_EVENT = "CHECK_DELINQUENCY"
delinquency_CHECK_DELINQUENCY_PREFIX = "check_delinquency"
delinquency_PARAM_CHECK_DELINQUENCY_HOUR = f"{delinquency_CHECK_DELINQUENCY_PREFIX}_hour"
delinquency_PARAM_CHECK_DELINQUENCY_MINUTE = f"{delinquency_CHECK_DELINQUENCY_PREFIX}_minute"
delinquency_PARAM_CHECK_DELINQUENCY_SECOND = f"{delinquency_CHECK_DELINQUENCY_PREFIX}_second"
delinquency_PARAM_GRACE_PERIOD = "grace_period"
delinquency_MARK_DELINQUENT_NOTIFICATION_SUFFIX = "_DELINQUENT_NOTIFICATION"
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


def delinquency_get_grace_period_parameter(vault: Any) -> int:
    return int(utils_get_parameter(vault=vault, name=delinquency_PARAM_GRACE_PERIOD))


def delinquency_event_types(product_name: str) -> list[SmartContractEventType]:
    """
    Returns the a list of event types for delinquency
    :param product_name: The name of the product
    :return: list[SmartContractEventType]
    """
    return [
        SmartContractEventType(
            name=delinquency_CHECK_DELINQUENCY_EVENT,
            scheduler_tag_ids=[f"{product_name.upper()}_{delinquency_CHECK_DELINQUENCY_EVENT}_AST"],
        )
    ]


def delinquency_notification_type(product_name: str) -> str:
    """
    Creates the notification type
    :param product_name: The product name
    :return: str
    """
    return f"{product_name.upper()}{delinquency_MARK_DELINQUENT_NOTIFICATION_SUFFIX}"


def delinquency_scheduled_events(
    vault: Any, start_datetime: datetime, is_one_off: bool = False, skip: bool = False
) -> dict[str, ScheduledEvent]:
    """
    Create a check delinquency schedule, starting at the specified date, and using the
    `check_delinquency_<>` schedule time parameters. This schedule can either be a monthly recurring
    schedule or executed once.
    :param vault: The Vault object
    :param start_datetime: the date on which the delinquency check schedule starts, ignores the time
    component
    :param is_one_off: whether the schedule is recurring or a one-off schedule
    :return: a dictionary containing the check delinquency schedule
    """
    year = start_datetime.year if is_one_off else None
    month = start_datetime.month if is_one_off else None
    return {
        delinquency_CHECK_DELINQUENCY_EVENT: ScheduledEvent(
            start_datetime=start_datetime.replace(hour=0, minute=0, second=0),
            expression=utils_get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=delinquency_CHECK_DELINQUENCY_PREFIX,
                day=start_datetime.day,
                month=month,
                year=year,
            ),
            skip=skip,
        )
    }


def delinquency_schedule_logic(
    vault: Any,
    product_name: str,
    denomination: str,
    addresses: list[str] = lending_addresses_LATE_REPAYMENT_ADDRESSES,
) -> list[AccountNotificationDirective]:
    """
    Instruct a notification to inform the customer of their account delinquency.
    :param vault: Vault object
    :param product_name: the name of the product for the workflow prefix
    :param addresses: list of balance addresses to be checked to determine whether an account is
    delinquent
    :param denomination: the denomination of the balance addresses
    :return: list[AccountNotificationDirective]
    """
    balances = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    total_balance = utils_sum_balances(
        balances=balances, addresses=addresses, denomination=denomination, decimal_places=2
    )
    if total_balance > 0:
        return [
            AccountNotificationDirective(
                notification_type=delinquency_notification_type(product_name),
                notification_details={"account_id": str(vault.account_id)},
            )
        ]
    return []


# Objects below have been imported from:
#    derived_params.py
# md5:e5e42c2b86af0ad211853bcc16ea1854

derived_params_PARAM_TOTAL_OUTSTANDING_DEBT = "total_outstanding_debt"
derived_params_PARAM_TOTAL_REMAINING_PRINCIPAL = "total_remaining_principal"
derived_params_PARAM_PRINCIPAL_PAID_TO_DATE = "principal_paid_to_date"
derived_params_total_outstanding_debt_parameter = Parameter(
    name=derived_params_PARAM_TOTAL_OUTSTANDING_DEBT,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Remaining total balance on this account",
    display_name="Total Outstanding Debt",
)
derived_params_total_remaining_principal_parameter = Parameter(
    name=derived_params_PARAM_TOTAL_REMAINING_PRINCIPAL,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Remaining total principal balance on the account",
    display_name="Total Remaining Principal",
)
derived_params_principal_paid_to_date_parameter = Parameter(
    name=derived_params_PARAM_PRINCIPAL_PAID_TO_DATE,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Principal paid so far on this account.",
    display_name="Principal Paid To Date",
)


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


def derived_params_get_principal_paid_to_date(
    original_principal: Decimal, balances: BalanceDefaultDict, denomination: str, precision: int = 2
) -> Decimal:
    """
    Returns the amount of the original principal paid off
    :param original_principal: the original principal amount
    :param balances: A dictionary of balances in the account
    :param denomination: The denomination of the remaining principal amount
    :param precision: The number of decimal places to round to, defaults to 2
    :return: The principal paid to date
    """
    return original_principal - derived_params_get_total_remaining_principal(
        balances=balances, denomination=denomination, precision=precision
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


def disbursement_get_principal_parameter(vault: Any) -> Decimal:
    return Decimal(utils_get_parameter(vault=vault, name=disbursement_PARAM_PRINCIPAL))


def disbursement_get_deposit_account_parameter(vault: Any) -> str:
    return str(utils_get_parameter(vault=vault, name=disbursement_PARAM_DEPOSIT_ACCOUNT))


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
#    due_amount_notification.py
# md5:d00e2764f198f1e015c1a04dc67b1efe

due_amount_notification_NOTIFY_DUE_AMOUNT_EVENT = "NOTIFY_DUE_AMOUNT"
due_amount_notification_DUE_AMOUNT_NOTIFICATION_PREFIX = "due_amount_notification"
due_amount_notification_PARAM_DUE_NOTIFICATION_HOUR = (
    f"{due_amount_notification_DUE_AMOUNT_NOTIFICATION_PREFIX}_hour"
)
due_amount_notification_PARAM_DUE_NOTIFICATION_MINUTE = (
    f"{due_amount_notification_DUE_AMOUNT_NOTIFICATION_PREFIX}_minute"
)
due_amount_notification_PARAM_DUE_NOTIFICATION_SECOND = (
    f"{due_amount_notification_DUE_AMOUNT_NOTIFICATION_PREFIX}_second"
)
due_amount_notification_PARAM_NOTIFICATION_PERIOD = "notification_period"
due_amount_notification_REPAYMENT_NOTIFICATION_SUFFIX = "_REPAYMENT"
due_amount_notification_due_amount_notification_period_parameter = Parameter(
    name=due_amount_notification_PARAM_NOTIFICATION_PERIOD,
    shape=NumberShape(min_value=1, max_value=28, step=1),
    level=ParameterLevel.TEMPLATE,
    description="The number of days prior to a payment becoming due, send a due notification reminder to the user.",
    display_name="Due Notification Days",
    default_value=Decimal("2"),
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)
due_amount_notification_schedule_time_parameters = [
    Parameter(
        name=due_amount_notification_PARAM_DUE_NOTIFICATION_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which due notifications are sent.",
        display_name="Due Notification Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=due_amount_notification_PARAM_DUE_NOTIFICATION_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which due notifications are sent.",
        display_name="Due Notification Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=due_amount_notification_PARAM_DUE_NOTIFICATION_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which due notifications are sent.",
        display_name="Due Notification Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
]
due_amount_notification_due_amount_notification_schedule_parameters = [
    due_amount_notification_due_amount_notification_period_parameter,
    *due_amount_notification_schedule_time_parameters,
]


def due_amount_notification_get_notification_period_parameter(vault: Any) -> int:
    return int(utils_get_parameter(vault, name=due_amount_notification_PARAM_NOTIFICATION_PERIOD))


def due_amount_notification_event_types(product_name: str) -> list[SmartContractEventType]:
    """
    Creates event_types metadata for NOTIFY_DUE_AMOUNT schedule
    :param product_name: The name of the product
    :return: list[SmartContractEventType]
    """
    return [
        SmartContractEventType(
            name=due_amount_notification_NOTIFY_DUE_AMOUNT_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{due_amount_notification_NOTIFY_DUE_AMOUNT_EVENT}_AST"
            ],
        )
    ]


def due_amount_notification_notification_type(product_name: str) -> str:
    """
    Creates the notification type
    :param product_name: The product name
    :return: str
    """
    return f"{product_name.upper()}{due_amount_notification_REPAYMENT_NOTIFICATION_SUFFIX}"


def due_amount_notification_get_next_due_amount_notification_schedule(
    vault: Any, next_due_amount_calc_datetime: datetime
) -> datetime:
    notification_period = int(
        utils_get_parameter(vault, name=due_amount_notification_PARAM_NOTIFICATION_PERIOD)
    )
    (hour, minute, second) = utils_get_schedule_time_from_parameters(
        vault, parameter_prefix=due_amount_notification_DUE_AMOUNT_NOTIFICATION_PREFIX
    )
    return next_due_amount_calc_datetime - relativedelta(
        days=notification_period, hour=hour, minute=minute, second=second
    )


def due_amount_notification_get_next_due_amount_notification_datetime(
    vault: Any,
    current_due_amount_notification_datetime: datetime,
    repayment_frequency_delta: relativedelta,
) -> datetime:
    """
    returns the next due amount notification datetime given the current due amount
    notification date
    :param vault: vault object
    :param current_due_amount_notification: the current due amount notification date
    :param repayment_frequency_delta: the relative delta for the repayment frequency
    :return: datetime
    """
    notification_period = int(
        utils_get_parameter(vault, name=due_amount_notification_PARAM_NOTIFICATION_PERIOD)
    )
    current_due_amount_calc_date_time = current_due_amount_notification_datetime + relativedelta(
        days=notification_period
    )
    next_due_amount_calc_datetime = current_due_amount_calc_date_time + repayment_frequency_delta
    next_due_amount_notification_datetime = (
        due_amount_notification_get_next_due_amount_notification_schedule(
            vault=vault, next_due_amount_calc_datetime=next_due_amount_calc_datetime
        )
    )
    return next_due_amount_notification_datetime


def due_amount_notification_scheduled_events(
    vault: Any, next_due_amount_calc_datetime: datetime
) -> dict[str, ScheduledEvent]:
    """
    Creates execution schedule for NOTIFY_DUE_AMOUNT schedule to run `notification_period` days
    before the first due amount calculation date
    :param vault: Vault object for the account containing schedule time and notification_period
    parameters
    :param next_due_amount_calc_datetime: date when the next due_amount_calc_datetime will happen.
    due amount calculation should occur. Time component will be ignored
    :return: list[SmartContractEventType]
    """
    due_amount_notification_scheduled_events: dict[str, ScheduledEvent] = {}
    notification_datetime = due_amount_notification_get_next_due_amount_notification_schedule(
        vault=vault, next_due_amount_calc_datetime=next_due_amount_calc_datetime
    )
    due_amount_notification_scheduled_events = {
        due_amount_notification_NOTIFY_DUE_AMOUNT_EVENT: ScheduledEvent(
            start_datetime=notification_datetime - relativedelta(seconds=1),
            expression=utils_one_off_schedule_expression(notification_datetime),
        )
    }
    return due_amount_notification_scheduled_events


def due_amount_notification_schedule_logic(
    vault: Any,
    product_name: str,
    overdue_datetime: datetime,
    due_interest: Decimal = Decimal("0"),
    due_principal: Decimal = Decimal("0"),
) -> list[AccountNotificationDirective]:
    """
    Sends notification prior to a payment becoming due.
    :param vault: vault object to instruct any notifications from
    :param product_name: The product name
    :param overdue_datetime: the date that the repayment amount will become overdue
    :param due_interest: the due_interest.
    :param due_principal: the due_principal
    :return: list[AccountNotificationDirective]
    """
    if due_principal + due_interest > 0:
        return [
            due_amount_notification_send_due_amount_notification(
                account_id=vault.account_id,
                due_principal=due_principal,
                due_interest=due_interest,
                overdue_datetime=overdue_datetime,
                product_name=product_name,
            )
        ]
    return []


def due_amount_notification_send_due_amount_notification(
    account_id: str,
    due_principal: Decimal,
    due_interest: Decimal,
    overdue_datetime: datetime,
    product_name: str,
) -> AccountNotificationDirective:
    """
    Instruct a notification.

    :param account_id: vault account id
    :param due_principal: Calculated due principal
    :param due_interest: Calculated due interest
    :param overdue_datetime: the date that the repayment amount will become overdue
    :param product_name: the name of the product for the notification prefix
    :return: AccountNotificationDirective
    """
    return AccountNotificationDirective(
        notification_type=due_amount_notification_notification_type(product_name),
        notification_details={
            "account_id": account_id,
            "due_principal": str(due_principal),
            "due_interest": str(due_interest),
            "overdue_date": str(overdue_datetime.date()),
        },
    )


# Objects below have been imported from:
#    emi_in_advance.py
# md5:616c50c57685ecd9c762470fd30ec287

emi_in_advance_EMI_IN_ADVANCE_OFFSET = 1


def emi_in_advance_charge(
    vault: Any, effective_datetime: datetime, amortisation_feature: lending_interfaces_Amortisation
) -> list[CustomInstruction]:
    """
    Calculates emi and instructs postings for due amounts during account activation.
    Works only for zero interest products and thus instructs only principal_due postings
    :param vault: Vault object
    param effective_datetime: effective date of the charge
    :param amortisation_feature: contains the emi calculation method for the desired amortisation
    :return: list of custom instructions including emi and due transfer
    """
    custom_instructions: list[CustomInstruction] = []
    custom_instructions += emi_amortise(
        vault=vault,
        effective_datetime=effective_datetime,
        amortisation_feature=amortisation_feature,
    )
    principal: Decimal = utils_get_parameter(vault, name="principal")
    denomination: str = utils_get_parameter(vault, name="denomination")
    principal_due = amortisation_feature.calculate_emi(
        vault=vault, effective_datetime=effective_datetime, principal_amount=principal
    )
    custom_instructions += [
        CustomInstruction(
            postings=due_amount_calculation_transfer_principal_due(
                customer_account=vault.account_id,
                principal_due=principal_due,
                denomination=denomination,
            ),
            instruction_details={
                "description": "Principal due on activation",
                "event": events_ACCOUNT_ACTIVATION,
            },
        )
    ]
    return custom_instructions


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

late_repayment_CHECK_LATE_REPAYMENT_EVENT = "CHECK_LATE_REPAYMENT"
late_repayment_CHECK_LATE_REPAYMENT_PREFIX = "check_late_repayment"
late_repayment_PARAM_CHECK_LATE_REPAYMENT_CHECK_HOUR = (
    f"{late_repayment_CHECK_LATE_REPAYMENT_PREFIX}_hour"
)
late_repayment_PARAM_CHECK_LATE_REPAYMENT_CHECK_MINUTE = (
    f"{late_repayment_CHECK_LATE_REPAYMENT_PREFIX}_minute"
)
late_repayment_PARAM_CHECK_LATE_REPAYMENT_CHECK_SECOND = (
    f"{late_repayment_CHECK_LATE_REPAYMENT_PREFIX}_second"
)
late_repayment_PARAM_LATE_REPAYMENT_FEE = "late_repayment_fee"
late_repayment_PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "late_repayment_fee_income_account"
late_repayment_PARAM_DENOMINATION = "denomination"
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
late_repayment_schedule_parameters = [
    Parameter(
        name=late_repayment_PARAM_CHECK_LATE_REPAYMENT_CHECK_HOUR,
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which late repayment is checked.",
        display_name="Check Late Repayment Hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=0,
    ),
    Parameter(
        name=late_repayment_PARAM_CHECK_LATE_REPAYMENT_CHECK_MINUTE,
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which late repayment is checked.",
        display_name="Check Late Repayment Minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name=late_repayment_PARAM_CHECK_LATE_REPAYMENT_CHECK_SECOND,
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which late repayment is checked.",
        display_name="Check Late Repayment Second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
]


def late_repayment_get_late_repayment_fee_parameter(vault: Any) -> Decimal:
    return Decimal(utils_get_parameter(vault=vault, name=late_repayment_PARAM_LATE_REPAYMENT_FEE))


def late_repayment_event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=late_repayment_CHECK_LATE_REPAYMENT_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{late_repayment_CHECK_LATE_REPAYMENT_EVENT}_AST"
            ],
        )
    ]


def late_repayment_scheduled_events(
    vault: Any, start_datetime: datetime, skip: bool = False
) -> dict[str, ScheduledEvent]:
    """
    Create a check late repayment schedule, starting at the specified date, and using the
    `check_late_repayment_<>` schedule time parameters. This is a monthly schedule starting on the
    specified start_datetime.
    :param vault: the Vault object
    :param start_datetime: the date on which the schedule will initially run, ignores the time
    component
    :param skip: if True, schedule will be skipped indefinitely until this field is updated,
    defaults to False
    :return: a dictionary containing the check late repayment schedule
    """
    return {
        late_repayment_CHECK_LATE_REPAYMENT_EVENT: ScheduledEvent(
            start_datetime=start_datetime.replace(hour=0, minute=0, second=0),
            expression=utils_get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=late_repayment_CHECK_LATE_REPAYMENT_PREFIX,
                day=start_datetime.day,
            ),
            skip=skip,
        )
    }


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
#    lending_utils.py
# md5:37cd57713eed8f189835207a80381f6c


def lending_utils_is_credit(amount: Decimal) -> bool:
    return amount < Decimal("0")


def lending_utils_is_debit(amount: Decimal) -> bool:
    return amount > Decimal("0")


# Objects below have been imported from:
#    overdue.py
# md5:11cacf1a6c91093b7cdfbea3281b9f19

overdue_CHECK_OVERDUE_EVENT = "CHECK_OVERDUE"
overdue_CHECK_OVERDUE_PREFIX = "check_overdue"
overdue_PARAM_CHECK_OVERDUE_HOUR = f"{overdue_CHECK_OVERDUE_PREFIX}_hour"
overdue_PARAM_CHECK_OVERDUE_MINUTE = f"{overdue_CHECK_OVERDUE_PREFIX}_minute"
overdue_PARAM_CHECK_OVERDUE_SECOND = f"{overdue_CHECK_OVERDUE_PREFIX}_second"
overdue_PARAM_REPAYMENT_PERIOD = "repayment_period"
overdue_OVERDUE_REPAYMENT_NOTIFICATION_SUFFIX = "_OVERDUE_REPAYMENT"
overdue_FUND_MOVEMENT_MAP = {
    lending_addresses_PRINCIPAL_DUE: lending_addresses_PRINCIPAL_OVERDUE,
    lending_addresses_INTEREST_DUE: lending_addresses_INTEREST_OVERDUE,
}
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


def overdue_get_repayment_period_parameter(vault: Any) -> int:
    return int(utils_get_parameter(vault=vault, name=overdue_PARAM_REPAYMENT_PERIOD))


def overdue_event_types(product_name: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
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


def overdue_scheduled_events(
    vault: Any,
    first_due_amount_calculation_datetime: datetime,
    is_one_off: bool = False,
    skip: bool = False,
) -> dict[str, ScheduledEvent]:
    """
    Create a check overdue schedule by calculating the date on which the schedule will run
    from the first due amount calculation date and the repayment period. The time component is
    determined by the `check_overdue_<>` schedule time parameters. This schedule can either be a
    monthly recurring schedule, executed once or initially skipped.
    :param vault: the Vault object
    :param first_due_amount_calculation_datetime: the datetime on which the first due amount is
    calculated, used to determine the next overdue check date ignoring the time component
    :param is_one_off: whether the schedule is recurring or a one-off schedule
    :param skip: if True, schedule will be skipped indefinitely until this field is updated,
    defaults to False
    :return: a dictionary containing the check late repayment schedule
    """
    repayment_period = int(utils_get_parameter(vault=vault, name=overdue_PARAM_REPAYMENT_PERIOD))
    next_overdue_check_datetime = first_due_amount_calculation_datetime + relativedelta(
        days=repayment_period
    )
    year = next_overdue_check_datetime.year if is_one_off else None
    month = next_overdue_check_datetime.month if is_one_off else None
    return {
        overdue_CHECK_OVERDUE_EVENT: ScheduledEvent(
            start_datetime=next_overdue_check_datetime.replace(hour=0, minute=0, second=0),
            expression=utils_get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=overdue_CHECK_OVERDUE_PREFIX,
                day=next_overdue_check_datetime.day,
                month=month,
                year=year,
            ),
            skip=skip,
        )
    }


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


def overdue_get_overdue_datetime(
    due_amount_notification_datetime: datetime, repayment_period: int, notification_period: int
) -> datetime:
    """
    returns the overdue datetime (hour, minute and second are not considered) given the
    due amount notification date
    :param vault: vault object
    :param due_amount_notification_datetime: the date when the due amount
    notification will take place.
    :param repayment_period: The number of days after which due amounts are made overdue.
    :param notification_period: The number of days prior to a payment becoming due,
    send a due notification reminder to the user.
    :return: datetime
    """
    return due_amount_notification_datetime + relativedelta(
        days=int(notification_period + repayment_period)
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
#    accruals.py
# md5:becbe7f07a49ad9560c9d05985a2e3ab


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
#    interest_application.py
# md5:b206c2a889540dba58282c6ec772665e

interest_application_PARAM_APPLICATION_PRECISION = "application_precision"


def interest_application_get_application_precision(vault: Any) -> int:
    return int(
        utils_get_parameter(vault=vault, name=interest_application_PARAM_APPLICATION_PRECISION)
    )


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
#    bnpl.py
# md5:1c311e1e5e630194d820e9ea87946e18

PRODUCT_NAME = "BUY_NOW_PAY_LATER"
UTC_ZONE = ZoneInfo("UTC")
PARAM_EQUATED_INSTALMENT_AMOUNT = emi_PARAM_EQUATED_INSTALMENT_AMOUNT
PARAM_LOAN_END_DATE = configurable_repayment_frequency_PARAM_LOAN_END_DATE
PARAM_NEXT_REPAYMENT_DATE = configurable_repayment_frequency_PARAM_NEXT_REPAYMENT_DATE
PARAM_REMAINING_TERM = configurable_repayment_frequency_PARAM_REMAINING_TERM
PARAM_TOTAL_OUTSTANDING_DEBT = derived_params_PARAM_TOTAL_OUTSTANDING_DEBT
PARAM_TOTAL_REMAINING_PRINCIPAL = derived_params_PARAM_TOTAL_REMAINING_PRINCIPAL
PARAM_PRINCIPAL_PAID_TO_DATE = derived_params_PARAM_PRINCIPAL_PAID_TO_DATE
DELINQUENCY_NOTIFICATION = delinquency_notification_type(PRODUCT_NAME)
LOAN_PAID_OFF_NOTIFICATION = close_loan_notification_type(PRODUCT_NAME)
DUE_AMOUNT_NOTIFICATION = due_amount_notification_notification_type(PRODUCT_NAME)
OVERDUE_REPAYMENT_NOTIFICATION = overdue_notification_type(PRODUCT_NAME)
notification_types = [
    DELINQUENCY_NOTIFICATION,
    LOAN_PAID_OFF_NOTIFICATION,
    DUE_AMOUNT_NOTIFICATION,
    OVERDUE_REPAYMENT_NOTIFICATION,
]
event_types = [
    *delinquency_event_types(PRODUCT_NAME),
    *due_amount_calculation_event_types(PRODUCT_NAME),
    *due_amount_notification_event_types(PRODUCT_NAME),
    *overdue_event_types(PRODUCT_NAME),
    *late_repayment_event_types(PRODUCT_NAME),
]
data_fetchers = [fetchers_EFFECTIVE_OBSERVATION_FETCHER, fetchers_LIVE_BALANCES_BOF]
parameters = [
    common_parameters_denomination_parameter,
    *configurable_repayment_frequency_derived_parameters,
    configurable_repayment_frequency_repayment_frequency_parameter,
    *delinquency_schedule_parameters,
    derived_params_principal_paid_to_date_parameter,
    derived_params_total_outstanding_debt_parameter,
    derived_params_total_remaining_principal_parameter,
    *disbursement_parameters,
    *due_amount_calculation_schedule_time_parameters,
    *due_amount_notification_due_amount_notification_schedule_parameters,
    *emi_derived_parameters,
    *late_repayment_fee_parameters,
    *late_repayment_schedule_parameters,
    lending_parameters_total_repayment_count_parameter,
    *overdue_schedule_parameters,
]
RESTRICTED_PARAMETERS = [
    disbursement_PARAM_PRINCIPAL,
    lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT,
]


def _schedule_fortnightly_repayment_frequency(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> list[UpdateAccountEventTypeDirective]:
    repayment_frequency = configurable_repayment_frequency_get_repayment_frequency_parameter(
        vault=vault
    )
    if repayment_frequency == configurable_repayment_frequency_FORTNIGHTLY:
        next_fortnightly_due_amount_calc_datetime = (
            configurable_repayment_frequency_get_next_fortnightly_schedule_expression(
                effective_date=hook_arguments.effective_datetime
            )
        )
        return [
            UpdateAccountEventTypeDirective(
                event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT,
                expression=next_fortnightly_due_amount_calc_datetime,
            )
        ]
    return []


def _schedule_overdue_check_event(
    vault: Any, effective_datetime: datetime
) -> list[UpdateAccountEventTypeDirective]:
    repayment_period = overdue_get_repayment_period_parameter(vault=vault)
    repayment_frequency_delta = _get_repayment_frequency_delta(vault=vault)
    previous_due_amount_calc_datetime = effective_datetime.replace(
        hour=0, minute=0, second=0
    ) - relativedelta(days=repayment_period)
    next_due_amount_calc_datetime = previous_due_amount_calc_datetime + repayment_frequency_delta
    next_check_overdue_datetime = next_due_amount_calc_datetime + relativedelta(
        days=repayment_period
    )
    return [
        UpdateAccountEventTypeDirective(
            event_type=overdue_CHECK_OVERDUE_EVENT,
            expression=utils_get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=overdue_CHECK_OVERDUE_PREFIX,
                day=next_check_overdue_datetime.day,
                month=next_check_overdue_datetime.month,
                year=next_check_overdue_datetime.year,
            ),
        )
    ]


def _schedule_check_late_repayment_event(
    vault: Any, effective_datetime: datetime
) -> list[UpdateAccountEventTypeDirective]:
    repayment_period = overdue_get_repayment_period_parameter(vault=vault)
    grace_period = delinquency_get_grace_period_parameter(vault=vault)
    late_repayment_period = repayment_period + grace_period
    repayment_frequency_delta = _get_repayment_frequency_delta(vault=vault)
    previous_due_amount_calc_datetime = effective_datetime.replace(
        hour=0, minute=0, second=0
    ) - relativedelta(days=late_repayment_period)
    next_due_amount_calc_datetime = previous_due_amount_calc_datetime + repayment_frequency_delta
    next_check_late_repayment_datetime = next_due_amount_calc_datetime + relativedelta(
        days=late_repayment_period
    )
    return [
        UpdateAccountEventTypeDirective(
            event_type=late_repayment_CHECK_LATE_REPAYMENT_EVENT,
            expression=utils_get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=late_repayment_CHECK_LATE_REPAYMENT_PREFIX,
                day=next_check_late_repayment_datetime.day,
                month=next_check_late_repayment_datetime.month,
                year=next_check_late_repayment_datetime.year,
            ),
        )
    ]


def _get_repayment_frequency_delta(vault: Any) -> relativedelta:
    repayment_frequency = configurable_repayment_frequency_get_repayment_frequency_parameter(
        vault=vault
    )
    return configurable_repayment_frequency_FREQUENCY_MAP[repayment_frequency]


def _get_repayment_notification(
    vault: Any, due_amount_notification_datetime: datetime
) -> list[AccountNotificationDirective]:
    denomination = common_parameters_get_denomination_parameter(vault=vault)
    repayment_period = overdue_get_repayment_period_parameter(vault=vault)
    notification_period = due_amount_notification_get_notification_period_parameter(vault=vault)
    balances = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    current_emi = due_amount_calculation_get_emi(balances=balances, denomination=denomination)
    due_amount_calculation_datetime = due_amount_notification_datetime + relativedelta(
        days=notification_period
    )
    (_, remaining_term) = declining_principal_term_details(
        vault=vault, effective_datetime=due_amount_calculation_datetime, use_expected_term=True
    )
    due_principal = due_amount_calculation_calculate_due_principal(
        remaining_principal=due_amount_calculation_get_principal(
            balances=balances, denomination=denomination
        ),
        emi_interest_to_apply=Decimal("0"),
        emi=current_emi,
        is_final_due_event=remaining_term == 1,
    )
    repayment_period = overdue_get_repayment_period_parameter(vault=vault)
    notification_period = due_amount_notification_get_notification_period_parameter(vault=vault)
    return due_amount_notification_schedule_logic(
        vault=vault,
        product_name=PRODUCT_NAME,
        overdue_datetime=overdue_get_overdue_datetime(
            due_amount_notification_datetime=due_amount_notification_datetime,
            repayment_period=repayment_period,
            notification_period=notification_period,
        ),
        due_interest=Decimal("0"),
        due_principal=due_principal,
    )
