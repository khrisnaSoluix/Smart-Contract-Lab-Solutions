# Code auto-generated using Inception Smart Contract Renderer Version 2.0.1


# Objects below have been imported from:
#    mortgage.py
# md5:8a7cf699780f6b2d531008e089e9e374

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
    NumberShape,
    BalancesObservationFetcher,
    DefinedDateTime,
    Override,
    PostingsIntervalFetcher,
    RelativeDateTime,
    Shift,
    AccountIdShape,
    SmartContractEventType,
    ParameterUpdatePermission,
    AccountNotificationDirective,
    DateShape,
    ScheduledEventHookArguments,
    SupervisorContractEventType,
    SupervisorScheduledEventHookArguments,
    BalancesFilter,
    BalancesObservation,
    OptionalShape,
    StringShape,
    BalancesIntervalFetcher,
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
    PostParameterChangeHookArguments,
    PostParameterChangeHookResult,
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
from decimal import ROUND_HALF_UP, Decimal, ROUND_CEILING
from json import dumps, loads
import math
from typing import Optional, Any, Iterable, Mapping, Union, NamedTuple, Callable
from zoneinfo import ZoneInfo

api = "4.0.0"
version = "5.0.1"
display_name = "Mortgage"
summary = "Fixed and variable rate mortgage with configuration repayment options."
tside = Tside.ASSET
supported_denominations = ["GBP"]


@requires(parameters=True)
def activation_hook(
    vault: Any, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    effective_datetime: datetime = hook_arguments.effective_datetime
    scheduled_events: dict[str, ScheduledEvent] = {}
    posting_instructions: list[CustomInstruction] = []
    schedules_start_datetime = effective_datetime.replace(
        hour=0, minute=0, second=0
    ) + relativedelta(days=1)
    scheduled_events.update(
        interest_accrual_scheduled_events(vault, start_datetime=schedules_start_datetime)
    )
    scheduled_events.update(
        due_amount_calculation_scheduled_events(vault, account_opening_datetime=effective_datetime)
    )
    scheduled_events.update(
        overpayment_allowance_scheduled_events(
            vault=vault, allowance_period_start_datetime=effective_datetime
        )
    )
    scheduled_events[CHECK_DELINQUENCY] = ScheduledEvent(
        skip=True,
        start_datetime=schedules_start_datetime,
        expression=utils_get_schedule_expression_from_parameters(
            vault, parameter_prefix=CHECK_DELINQUENCY_PREFIX
        ),
    )
    principal: Decimal = utils_get_parameter(vault=vault, name=disbursement_PARAM_PRINCIPAL)
    deposit_account: str = utils_get_parameter(vault=vault, name=disbursement_PARAM_DEPOSIT_ACCOUNT)
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    principal_custom_instruction = disbursement_get_disbursement_custom_instruction(
        account_id=vault.account_id,
        deposit_account_id=deposit_account,
        principal=principal,
        denomination=denomination,
    )
    posting_instructions.extend(principal_custom_instruction)
    posting_instructions += (
        overpayment_allowance_initialise_overpayment_allowance_from_principal_amount(
            vault=vault, principal=principal, denomination=denomination
        )
    )
    if int(utils_get_parameter(vault=vault, name=PARAM_INTEREST_ONLY_TERM)) == 0:
        amortise_custom_instruction = emi_amortise(
            vault=vault,
            effective_datetime=effective_datetime,
            amortisation_feature=declining_principal_AmortisationFeature,
            interest_calculation_feature=fixed_to_variable_InterestRate,
        )
        posting_instructions += amortise_custom_instruction
    return ActivationHookResult(
        posting_instructions_directives=[
            PostingInstructionsDirective(
                posting_instructions=posting_instructions, value_datetime=effective_datetime
            )
        ],
        scheduled_events_return_value=scheduled_events,
    )


@requires(last_execution_datetime=["CHECK_OVERPAYMENT_ALLOWANCE"], parameters=True)
@fetch_account_data(balances=["EFFECTIVE_FETCHER", "ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL"])
def conversion_hook(
    vault: Any, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    scheduled_events = hook_arguments.existing_schedules
    posting_instructions: list[CustomInstruction] = []
    if utils_get_parameter(
        vault=vault, name=PARAM_PRODUCT_SWITCH, is_optional=True, is_boolean=True
    ):
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
        denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
        posting_instructions += close_loan_net_balances(
            balances=balances,
            denomination=denomination,
            account_id=vault.account_id,
            residual_cleanup_features=[
                overpayment_OverpaymentResidualCleanupFeature,
                overpayment_allowance_OverpaymentAllowanceResidualCleanupFeature,
                due_amount_calculation_DueAmountCalculationResidualCleanupFeature,
                lending_interfaces_ResidualCleanup(
                    get_residual_cleanup_postings=_get_residual_cleanup_postings
                ),
            ],
        )
        if int(utils_get_parameter(vault=vault, name=PARAM_INTEREST_ONLY_TERM)) == 0:
            inflight_balances = BalanceDefaultDict(mapping=balances)
            for posting_instruction in posting_instructions:
                inflight_balances += posting_instruction.balances(
                    account_id=vault.account_id, tside=Tside.ASSET
                )
            posting_instructions += emi_amortise(
                vault=vault,
                effective_datetime=hook_arguments.effective_datetime,
                amortisation_feature=declining_principal_AmortisationFeature,
                principal_amount=utils_balance_at_coordinates(
                    balances=inflight_balances,
                    address=lending_addresses_PRINCIPAL,
                    denomination=denomination,
                ),
                interest_calculation_feature=fixed_to_variable_InterestRate,
                balances=inflight_balances,
                event="PRODUCT_SWITCH",
            )
        posting_instructions += overpayment_allowance_handle_allowance_usage_adhoc(
            vault=vault, account_type=ACCOUNT_TYPE, effective_datetime=effective_datetime
        )
        scheduled_events.update(
            overpayment_allowance_update_scheduled_event(
                vault=vault, effective_datetime=effective_datetime
            )
        )
    return ConversionHookResult(
        scheduled_events_return_value=scheduled_events,
        posting_instructions_directives=[
            PostingInstructionsDirective(
                posting_instructions=posting_instructions,
                value_datetime=hook_arguments.effective_datetime,
            )
        ]
        if posting_instructions
        else [],
    )


@requires(parameters=True)
@fetch_account_data(balances=["live_balances_bof"])
def deactivation_hook(
    vault: Any, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    denomination: str = utils_get_parameter(vault, name=PARAM_DENOMINATION)
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    if deactivation_rejection := close_loan_reject_closure_when_outstanding_debt(
        balances=balances,
        denomination=denomination,
        debt_addresses=lending_addresses_ALL_OUTSTANDING,
    ):
        return DeactivationHookResult(rejection=deactivation_rejection)
    posting_instructions = close_loan_net_balances(
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        residual_cleanup_features=[
            overpayment_OverpaymentResidualCleanupFeature,
            overpayment_allowance_OverpaymentAllowanceResidualCleanupFeature,
            due_amount_calculation_DueAmountCalculationResidualCleanupFeature,
            lending_interfaces_ResidualCleanup(
                get_residual_cleanup_postings=_get_residual_cleanup_postings
            ),
        ],
    )
    if posting_instructions:
        return DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=posting_instructions,
                    value_datetime=hook_arguments.effective_datetime,
                )
            ]
        )
    return None


@requires(
    parameters=True,
    last_execution_datetime=["DUE_AMOUNT_CALCULATION", "CHECK_OVERPAYMENT_ALLOWANCE"],
)
@fetch_account_data(balances=["EFFECTIVE_FETCHER", "ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL"])
def derived_parameter_hook(
    vault: Any, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    effective_datetime: datetime = hook_arguments.effective_datetime
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination: str = utils_get_parameter(vault, name=PARAM_DENOMINATION)
    total_outstanding_debt = derived_params_get_total_outstanding_debt(
        balances=balances, denomination=denomination
    )
    is_fixed_interest = str(
        fixed_to_variable_is_within_fixed_rate_term(
            vault=vault,
            effective_datetime=effective_datetime,
            balances=balances,
            denomination=denomination,
        )
    )
    total_remaining_principal = _get_outstanding_principal(balances, denomination)
    outstanding_payments = _get_outstanding_payments_amount(balances, denomination)
    next_repayment_date = _get_actual_next_repayment_dateeter(vault, effective_datetime)
    (_, remaining_term) = declining_principal_term_details(
        vault=vault,
        effective_datetime=effective_datetime,
        use_expected_term=_use_expected_term(
            vault=vault, balances=balances, denomination=denomination
        ),
        interest_rate=fixed_to_variable_InterestRate,
        balances=balances,
        denomination=denomination,
    )
    is_interest_only_term = str(
        _is_within_interest_only_term(vault=vault, balances=balances, denomination=denomination)
    )
    (original_allowance, used_allowance) = overpayment_allowance_get_overpayment_allowance_status(
        vault=vault, effective_datetime=effective_datetime
    )
    remaining_allowance = original_allowance - used_allowance
    overpayment_allowance_fee_percentage: Decimal = utils_get_parameter(
        vault=vault, name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE
    )
    overpayment_allowance_fee = overpayment_allowance_get_allowance_usage_fee(
        allowance=original_allowance,
        used_allowance=used_allowance,
        overpayment_allowance_fee_percentage=overpayment_allowance_fee_percentage,
    )
    early_repayment_fee = _get_early_repayment_fee(
        vault=vault, balances=balances, denomination=denomination
    )
    early_repayment_overpayment_allowance_fee = (
        overpayment_allowance_get_overpayment_allowance_fee_for_early_repayment(
            vault=vault, denomination=denomination, balances=balances
        )
    )
    parameters: dict[str, utils_ParameterValueTypeAlias] = {
        derived_params_PARAM_TOTAL_OUTSTANDING_DEBT: total_outstanding_debt,
        fixed_to_variable_PARAM_IS_FIXED_INTEREST: is_fixed_interest,
        PARAM_IS_INTEREST_ONLY_TERM: is_interest_only_term,
        derived_params_PARAM_TOTAL_REMAINING_PRINCIPAL: total_remaining_principal,
        PARAM_OUTSTANDING_PAYMENTS: outstanding_payments,
        due_amount_calculation_PARAM_NEXT_REPAYMENT_DATE: next_repayment_date,
        derived_params_PARAM_REMAINING_TERM: remaining_term,
        overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_REMAINING: remaining_allowance,
        overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_USED: used_allowance,
        overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE: overpayment_allowance_fee,
        PARAM_DERIVED_EARLY_REPAYMENT_FEE: early_repayment_fee,
        PARAM_TOTAL_EARLY_REPAYMENT_FEE: early_repayment_overpayment_allowance_fee
        + early_repayment_fee,
    }
    return DerivedParameterHookResult(parameters_return_value=parameters)


@requires(parameters=True, last_execution_datetime=["DUE_AMOUNT_CALCULATION"])
def post_parameter_change_hook(
    vault: Any, hook_arguments: PostParameterChangeHookArguments
) -> Optional[PostParameterChangeHookResult]:
    update_event_type_directives: list[UpdateAccountEventTypeDirective] = []
    update_event_type_directives.extend(
        _handle_due_amount_calculation_day_change(vault, hook_arguments)
    )
    if update_event_type_directives:
        return PostParameterChangeHookResult(
            update_account_event_type_directives=update_event_type_directives
        )
    return None


@requires(parameters=True, flags=True)
@fetch_account_data(balances=["live_balances_bof"])
def post_posting_hook(
    vault: Any, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    posting_instructions: utils_PostingInstructionListAlias = hook_arguments.posting_instructions
    if utils_is_force_override(posting_instructions):
        return None
    effective_datetime = hook_arguments.effective_datetime
    posting = posting_instructions[0]
    denomination: str = utils_get_parameter(vault, name=PARAM_DENOMINATION)
    posting_balance_delta: Decimal = utils_balance_at_coordinates(
        balances=posting.balances(), denomination=denomination
    )
    if posting_balance_delta > 0:
        is_interest_adjustment = _is_interest_adjustment(posting)
        balance_destination = (
            lending_addresses_INTEREST_DUE
            if is_interest_adjustment
            else lending_addresses_PENALTIES
        )
        custom_instructions = _move_balance_custom_instructions(
            amount=posting_balance_delta,
            denomination=denomination,
            vault_account=vault.account_id,
            balance_address=balance_destination,
        )
        if is_interest_adjustment:
            balances: BalanceDefaultDict = vault.get_balances_observation(
                fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
            ).balances
            interest_to_revert = _get_interest_to_revert(balances, denomination)
            interest_received_account: str = utils_get_parameter(
                vault, name=PARAM_INTEREST_RECEIVED_ACCOUNT
            )
            custom_instructions.extend(
                _get_interest_adjustment_custom_instructions(
                    amount=interest_to_revert,
                    denomination=denomination,
                    vault_account=vault.account_id,
                    interest_received_account=interest_received_account,
                )
            )
        return PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=custom_instructions, value_datetime=effective_datetime
                )
            ]
        )
    elif posting_balance_delta < 0:
        (custom_instructions, account_notification_directives) = _process_payment(
            vault=vault, hook_arguments=hook_arguments, denomination=denomination
        )
        posting_instruction_directives: list[PostingInstructionsDirective] = []
        if custom_instructions:
            posting_instruction_directives.append(
                PostingInstructionsDirective(
                    posting_instructions=custom_instructions, value_datetime=effective_datetime
                )
            )
        return PostPostingHookResult(
            posting_instructions_directives=posting_instruction_directives,
            account_notification_directives=account_notification_directives,
        )
    return None


@requires(flags=True, last_execution_datetime=["DUE_AMOUNT_CALCULATION"], parameters=True)
def pre_parameter_change_hook(
    vault: Any, hook_arguments: PreParameterChangeHookArguments
) -> Optional[PreParameterChangeHookResult]:
    updated_parameter_values = hook_arguments.updated_parameter_values
    if due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY in updated_parameter_values:
        if repayment_holiday_is_due_amount_calculation_blocked(
            vault=vault, effective_datetime=hook_arguments.effective_datetime
        ):
            return PreParameterChangeHookResult(
                rejection=Rejection(
                    message=f"The {due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY} parameter cannot be updated during a repayment holiday.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
        if rejection := due_amount_calculation_validate_due_amount_calculation_day_change(vault):
            return PreParameterChangeHookResult(rejection=rejection)
    return None


@requires(parameters=True, flags=True)
@fetch_account_data(balances=["live_balances_bof"])
def pre_posting_hook(
    vault: Any, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    posting_instructions: utils_PostingInstructionListAlias = hook_arguments.posting_instructions
    if utils_is_force_override(posting_instructions):
        return None
    if posting_rejection := utils_validate_single_hard_settlement_or_transfer(
        posting_instructions=posting_instructions
    ):
        return PrePostingHookResult(rejection=posting_rejection)
    denomination: str = utils_get_parameter(vault, name=PARAM_DENOMINATION)
    if denomination_rejection := utils_validate_denomination(posting_instructions, [denomination]):
        return PrePostingHookResult(rejection=denomination_rejection)
    posting = posting_instructions[0]
    posting_amount = _get_posting_net_amount(posting_instruction=posting, denomination=denomination)
    if posting_amount < Decimal("0"):
        if repayment_rejection := repayment_holiday_reject_repayment(
            vault=vault, effective_datetime=hook_arguments.effective_datetime
        ):
            return PrePostingHookResult(rejection=repayment_rejection)
        balances: BalanceDefaultDict = vault.get_balances_observation(
            fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
        ).balances
        outstanding_debt = derived_params_get_total_outstanding_debt(
            balances=balances, denomination=denomination
        )
        early_repayment_fee = _get_early_repayment_fee(
            vault=vault, balances=balances, denomination=denomination
        )
        overpayment_allowance_fee = (
            overpayment_allowance_get_overpayment_allowance_fee_for_early_repayment(
                vault=vault, denomination=denomination, balances=balances
            )
        )
        total_early_repayment_amount = (
            outstanding_debt + overpayment_allowance_fee + early_repayment_fee
        )
        principal_amount = utils_balance_at_coordinates(
            balances=balances, address=lending_addresses_PRINCIPAL, denomination=denomination
        )
        if (
            abs(posting_amount) >= outstanding_debt
            and principal_amount > Decimal("0")
            and (abs(posting_amount) != total_early_repayment_amount)
        ):
            return PrePostingHookResult(
                rejection=Rejection(
                    message=f"Cannot pay more than is owed. To repay the full amount of the mortgage - including fees - a posting for {total_early_repayment_amount} {denomination} must be made.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
    elif (
        posting_amount > Decimal("0")
        and (
            not utils_str_to_bool(
                posting.instruction_details.get(INSTRUCTION_DETAILS_KEY_FEE, "false")
            )
        )
        and (
            not utils_str_to_bool(
                posting.instruction_details.get(
                    INSTRUCTION_DETAILS_KEY_INTEREST_ADJUSTMENT, "false"
                )
            )
        )
    ):
        return PrePostingHookResult(
            rejection=Rejection(
                message="Debiting is not allowed from this account.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
    return None


@requires(event_type="ACCRUE_INTEREST", parameters=True, flags=True)
@fetch_account_data(
    event_type="ACCRUE_INTEREST", balances=["EOD_FETCHER", "EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER"]
)
@requires(
    event_type="DUE_AMOUNT_CALCULATION",
    flags=True,
    last_execution_datetime=["DUE_AMOUNT_CALCULATION"],
    parameters=True,
)
@fetch_account_data(
    event_type="DUE_AMOUNT_CALCULATION",
    balances=[
        "EFFECTIVE_FETCHER",
        "ACCRUED_INTEREST_EFFECTIVE_DATETIME_FETCHER",
        "ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER",
        "OVERPAYMENT_TRACKER_EFF_FETCHER",
    ],
)
@requires(event_type="CHECK_OVERPAYMENT_ALLOWANCE", parameters=True)
@fetch_account_data(
    event_type="CHECK_OVERPAYMENT_ALLOWANCE",
    balances=["EFFECTIVE_OVERPAYMENT_ALLOWANCE", "ONE_YEAR_OVERPAYMENT_ALLOWANCE"],
)
@requires(event_type="CHECK_DELINQUENCY", flags=True, parameters=True)
@fetch_account_data(event_type="CHECK_DELINQUENCY", balances=["EFFECTIVE_FETCHER"])
def scheduled_event_hook(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    event_type = hook_arguments.event_type
    effective_datetime = hook_arguments.effective_datetime
    custom_instructions: list[CustomInstruction] = []
    update_event_type_directives: list[UpdateAccountEventTypeDirective] = []
    account_notification_directives: list[AccountNotificationDirective] = []
    if event_type == interest_accrual_ACCRUAL_EVENT:
        custom_instructions.extend(
            _get_penalty_interest_accrual_custom_instruction(
                vault=vault, hook_arguments=hook_arguments
            )
        )
        capitalised_interest_postings = _handle_interest_capitalisation(
            vault=vault, effective_datetime=effective_datetime, account_type=ACCOUNT_TYPE
        )
        custom_instructions.extend(capitalised_interest_postings)
        custom_instructions.extend(
            _get_standard_interest_accrual_custom_instructions(
                vault, hook_arguments, inflight_postings=capitalised_interest_postings
            )
        )
    elif event_type == due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT:
        if not repayment_holiday_is_overdue_amount_calculation_blocked(
            vault=vault, effective_datetime=effective_datetime
        ):
            (overdue_custom_instructions, _) = overdue_schedule_logic(
                vault=vault, hook_arguments=hook_arguments
            )
            if overdue_custom_instructions:
                custom_instructions.extend(overdue_custom_instructions)
                custom_instructions.extend(_charge_late_repayment_fee(vault, event_type))
                (mark_delinquent_notifications, delinquency_event_updates) = _handle_delinquency(
                    vault=vault, hook_arguments=hook_arguments, is_delinquency_schedule_event=False
                )
                account_notification_directives.extend(mark_delinquent_notifications)
                update_event_type_directives.extend(delinquency_event_updates)
        custom_instructions.extend(
            _get_due_amount_custom_instructions(vault=vault, hook_arguments=hook_arguments)
        )
        custom_instructions.extend(
            interest_capitalisation_handle_penalty_interest_capitalisation(
                vault=vault, account_type=ACCOUNT_TYPE
            )
        )
    elif event_type == overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_EVENT:
        custom_instructions.extend(
            overpayment_allowance_handle_allowance_usage(vault=vault, account_type=ACCOUNT_TYPE)
        )
    elif event_type == CHECK_DELINQUENCY:
        (mark_delinquent_notifications, delinquency_event_updates) = _handle_delinquency(
            vault=vault, hook_arguments=hook_arguments, is_delinquency_schedule_event=True
        )
        account_notification_directives.extend(mark_delinquent_notifications)
        update_event_type_directives.extend(delinquency_event_updates)
    if custom_instructions or update_event_type_directives or account_notification_directives:
        return ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=custom_instructions,
                    client_batch_id=f"{ACCOUNT_TYPE}_{event_type}_{vault.get_hook_execution_id()}",
                    value_datetime=effective_datetime,
                )
            ]
            if custom_instructions
            else [],
            update_account_event_type_directives=update_event_type_directives,
            account_notification_directives=account_notification_directives,
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

common_parameters_BooleanShape = UnionShape(
    items=[UnionItem(key="True", display_name="True"), UnionItem(key="False", display_name="False")]
)
common_parameters_BooleanValueTrue = UnionItemValue(key="True")
common_parameters_BooleanValueFalse = UnionItemValue(key="False")

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
lending_addresses_ACCRUED_INTEREST_PENDING_CAPITALISATION = (
    "ACCRUED_INTEREST_PENDING_CAPITALISATION"
)
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
#    events.py
# md5:ee964ddec320f22b8eeab458a02a6835

events_ACCOUNT_ACTIVATION = "ACCOUNT_ACTIVATION"

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
#    interest_accrual.py
# md5:07236706e076b2c0568b51146520a313

interest_accrual_ACCRUED_INTEREST_RECEIVABLE = interest_accrual_common_ACCRUED_INTEREST_RECEIVABLE
interest_accrual_ACCRUAL_EVENT = interest_accrual_common_ACCRUAL_EVENT
interest_accrual_event_types = interest_accrual_common_event_types
interest_accrual_scheduled_events = interest_accrual_common_scheduled_events
interest_accrual_data_fetchers = [fetchers_EOD_FETCHER]
interest_accrual_PARAM_DAYS_IN_YEAR = interest_accrual_common_PARAM_DAYS_IN_YEAR
interest_accrual_PARAM_ACCRUAL_PRECISION = interest_accrual_common_PARAM_ACCRUAL_PRECISION
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


def interest_application_repay_accrued_interest(
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
    :param denomination: repayment denomination. If None, the latest value of the
    `denomination` parameter is used.
    :param balances: account balances to determine repayment allocation. If None, fetched using the
    ACCRUED_INTEREST_EFF_FETCHER_ID fetcher
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
            fetcher_id=interest_application_ACCRUED_INTEREST_EFF_FETCHER_ID
        ).balances
    accrual_internal_account = interest_accrual_get_accrual_internal_account(vault=vault)
    application_internal_account = interest_application_get_application_internal_account(
        vault=vault
    )
    application_precision = interest_application_get_application_precision(vault=vault)
    postings: list[Posting] = []
    (accrued_amount, rounded_accrued_amount) = interest_application__interest_amounts(
        balances=balances, denomination=denomination, precision=application_precision
    )
    if rounded_accrued_amount <= repayment_amount:
        application_amount = rounded_accrued_amount
        accrual_amount = accrued_amount
    else:
        application_amount = repayment_amount
        accrual_amount = repayment_amount
    if application_amount > 0:
        postings.extend(
            accruals_accrual_application_postings(
                customer_account=vault.account_id,
                denomination=denomination,
                application_amount=application_amount,
                accrual_amount=accrual_amount,
                accrual_customer_address=interest_application_ACCRUED_INTEREST_RECEIVABLE,
                accrual_internal_account=accrual_internal_account,
                application_customer_address=application_customer_address,
                application_internal_account=application_internal_account,
                payable=False,
            )
        )
    return postings


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
#    interest_capitalisation.py
# md5:6bf6cc7379aed3c7edf993397ba50d01

interest_capitalisation_PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT = (
    "capitalised_interest_receivable_account"
)
interest_capitalisation_PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT = (
    "capitalised_interest_received_account"
)
interest_capitalisation_PARAM_CAPITALISE_PENALTY_INTEREST = "capitalise_penalty_interest"
interest_capitalisation_capitalised_interest_receivable_account_param = Parameter(
    name=interest_capitalisation_PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT,
    shape=AccountIdShape(),
    level=ParameterLevel.TEMPLATE,
    description="Internal account for unrealised capitalised interest receivable balance.",
    display_name="Capitalised Interest Receivable Account",
    default_value="CAPITALISED_INTEREST_RECEIVABLE",
)
interest_capitalisation_capitalised_interest_received_account_param = Parameter(
    name=interest_capitalisation_PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
    shape=AccountIdShape(),
    level=ParameterLevel.TEMPLATE,
    description="Internal account for capitalised interest received balance.",
    display_name="Capitalised Interest Received Account",
    default_value="CAPITALISED_INTEREST_RECEIVED",
)
interest_capitalisation_capitalise_penalty_interest_param = Parameter(
    name=interest_capitalisation_PARAM_CAPITALISE_PENALTY_INTEREST,
    shape=common_parameters_BooleanShape,
    level=ParameterLevel.TEMPLATE,
    description="Determines if penalty interest is immediately added to Penalties (False) or  accrued and capitalised at next due amount calculation.",
    display_name="Capitalise Penalty Interest",
    default_value=common_parameters_BooleanValueFalse,
)


def interest_capitalisation_is_capitalise_penalty_interest(vault: Any) -> bool:
    return utils_get_parameter(
        vault=vault, name=interest_capitalisation_PARAM_CAPITALISE_PENALTY_INTEREST, is_boolean=True
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


def interest_capitalisation_handle_penalty_interest_capitalisation(
    vault: Any, account_type: str
) -> list[CustomInstruction]:
    if interest_capitalisation_is_capitalise_penalty_interest(vault=vault):
        return interest_capitalisation_handle_interest_capitalisation(
            vault=vault,
            account_type=account_type,
            balances=vault.get_balances_observation(
                fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
            ).balances,
            interest_to_capitalise_address=lending_addresses_ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
        )
    return []


def interest_capitalisation_handle_interest_capitalisation(
    vault: Any,
    account_type: str,
    balances: Optional[BalanceDefaultDict] = None,
    interest_to_capitalise_address: str = lending_addresses_ACCRUED_INTEREST_PENDING_CAPITALISATION,
) -> list[CustomInstruction]:
    """
    Capitalises any accrued interest pending capitalisation interest after a repayment holiday ends.
    This may result in debit to PRINCIPAL and to the tracker balance for Capitalised
    Interest.
    This function needs running as frequently as the end of the repayment holiday needs detecting
    (e.g. run daily if you need to know by EOD) as we can't explicitly trigger any logic when a
    i.e. when a flag is removed (i.e. when a repayment holiday ends).

    :param vault: Vault object for the relevant account. Requires parameters, flags, balances
    :param account_type: The type of account, e.g. LOAN or MORTGAGE
    :param balances: Balances to use. Defaults to EOD balances
    :param interest_to_capitalise_address: the address that the interest to capitalise is held at
    :param is_penalty_interest_capitalisation: whether or not it is penalty interest being
    capitalised
    :return: posting instructions to capitalise the interest
    """
    balances = (
        balances or vault.get_balances_observation(fetcher_id=fetchers_EOD_FETCHER_ID).balances
    )
    denomination = interest_capitalisation__get_denomination(vault=vault)
    capitalised_interest_received_account = (
        interest_capitalisation_get_capitalised_interest_received_account(vault=vault)
    )
    capitalised_interest_receivable_account = (
        interest_capitalisation_get_capitalised_interest_receivable_account(vault=vault)
    )
    application_precision = interest_application_get_application_precision(vault=vault)
    return interest_capitalisation_capitalise_interest(
        account_id=vault.account_id,
        application_precision=application_precision,
        balances=balances,
        capitalised_interest_receivable_account=capitalised_interest_receivable_account,
        capitalised_interest_received_account=capitalised_interest_received_account,
        denomination=denomination,
        interest_address_pending_capitalisation=interest_to_capitalise_address,
        account_type=account_type,
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


def interest_capitalisation__get_denomination(
    vault: Any, denomination: Optional[str] = None
) -> str:
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


def interest_capitalisation_get_capitalised_interest_received_account(vault: Any) -> str:
    return utils_get_parameter(
        vault=vault, name=interest_capitalisation_PARAM_CAPITALISED_INTEREST_RECEIVED_ACCOUNT
    )


def interest_capitalisation_get_capitalised_interest_receivable_account(vault: Any) -> str:
    return utils_get_parameter(
        vault=vault, name=interest_capitalisation_PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT
    )


# Objects below have been imported from:
#    fixed.py
# md5:f2f9eef46e1a533911ac0476c6df2d10

fixed_PARAM_FIXED_INTEREST_RATE = "fixed_interest_rate"
fixed_parameters = [
    Parameter(
        name=fixed_PARAM_FIXED_INTEREST_RATE,
        level=ParameterLevel.INSTANCE,
        description="The fixed annual rate of the loan (p.a).",
        display_name="Fixed Interest Rate",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("0.00"),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    )
]


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


def variable_should_trigger_reamortisation(
    vault: Any,
    period_start_datetime: datetime,
    period_end_datetime: datetime,
    elapsed_term: Optional[int] = None,
) -> bool:
    """
    Determines whether the monthly interest rate at the period end differs from period start. If so,
    there must have been a change to the annual interest rate which will result in reamortisation.

    :param vault: vault object for the account
    :param period_start_datetime: datetime of the period start, typically this will be the datetime
    of the previous due amount calculation. This is intentionally not an Optional[] argument since
    period_start_datetime=None would result in comparing the monthly interest rate between latest()
    and period_end_datetime.
    :param period_end_datetime: datetime of the period end, typically the effective_datetime of the
    current due amount calculation event
    :param elapsed_term: Not used but required for the interface
    :return bool: Whether the monthly interest rate at the period end differs from period start
    """
    return variable_get_monthly_interest_rate(
        vault=vault, effective_datetime=period_start_datetime
    ) != variable_get_monthly_interest_rate(vault=vault, effective_datetime=period_end_datetime)


# Objects below have been imported from:
#    fixed_to_variable.py
# md5:fccd6dae2d8a9d9fc1483b1b267d8570

fixed_to_variable_PARAM_FIXED_INTEREST_TERM = "fixed_interest_term"
fixed_to_variable_PARAM_IS_FIXED_INTEREST = "is_fixed_interest"
fixed_to_variable_is_fixed_interest_param = Parameter(
    name=fixed_to_variable_PARAM_IS_FIXED_INTEREST,
    shape=StringShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Is this account within the fixed interest period.",
    display_name="In Fixed Interest Period",
)
fixed_to_variable_fixed_interest_term_param = Parameter(
    name=fixed_to_variable_PARAM_FIXED_INTEREST_TERM,
    shape=NumberShape(min_value=Decimal(0), step=Decimal(1)),
    level=ParameterLevel.INSTANCE,
    description="The agreed length of the fixed rate portion (in months).",
    display_name="Fixed Rate Term (months)",
    default_value=Decimal(0),
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)
fixed_to_variable_parameters = [
    fixed_to_variable_is_fixed_interest_param,
    fixed_to_variable_fixed_interest_term_param,
]


def fixed_to_variable_is_within_fixed_rate_term(
    vault: Any,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> bool:
    fixed_rate_term = int(utils_get_parameter(vault, "fixed_interest_term"))
    if fixed_rate_term == 0:
        return False
    if effective_datetime == vault.get_account_creation_datetime():
        elapsed_term = 0
    else:
        if balances is None:
            balances = vault.get_balances_observation(
                fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
            ).balances
        if denomination is None:
            denomination = utils_get_parameter(vault=vault, name="denomination")
        elapsed_term = term_helpers_calculate_elapsed_term(
            balances=balances, denomination=denomination
        )
    return elapsed_term < fixed_rate_term


def fixed_to_variable_get_daily_interest_rate(
    vault: Any,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    is_fixed_interest = fixed_to_variable_is_within_fixed_rate_term(
        vault=vault,
        effective_datetime=effective_datetime,
        balances=balances,
        denomination=denomination,
    )
    if is_fixed_interest:
        return fixed_get_daily_interest_rate(vault=vault, effective_datetime=effective_datetime)
    else:
        return variable_get_daily_interest_rate(vault=vault, effective_datetime=effective_datetime)


def fixed_to_variable_get_monthly_interest_rate(
    vault: Any,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    is_fixed_interest = fixed_to_variable_is_within_fixed_rate_term(
        vault=vault,
        effective_datetime=effective_datetime,
        balances=balances,
        denomination=denomination,
    )
    if is_fixed_interest:
        return fixed_get_monthly_interest_rate(vault=vault, effective_datetime=effective_datetime)
    else:
        return variable_get_monthly_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )


def fixed_to_variable_get_annual_interest_rate(
    vault: Any,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    is_fixed_interest = fixed_to_variable_is_within_fixed_rate_term(
        vault=vault,
        effective_datetime=effective_datetime,
        balances=balances,
        denomination=denomination,
    )
    if is_fixed_interest:
        return fixed_get_annual_interest_rate(vault=vault, effective_datetime=effective_datetime)
    else:
        return variable_get_annual_interest_rate(vault=vault, effective_datetime=effective_datetime)


def fixed_to_variable_should_trigger_reamortisation(
    vault: Any, period_start_datetime: datetime, period_end_datetime: datetime, elapsed_term: int
) -> bool:
    """
    Determines if re-amortisation is required by checking if we have changed interest rates between
    the period start and end. This can be because:
    - rate type is variable and rate has changed
    - rate type has gone from fixed to variable and the fixed rate and variable rate differ

    :param vault: Vault object used to fetch balances/parameters
    :param period_start_datetime: datetime of the period start, typically this will be the datetime
    of the previous due amount calculation. This is intentionally not an Optional[] argument since
    period_start_datetime=None would result in comparing the monthly interest rate between latest()
    and period_end_datetime.
    :param period_end_datetime: datetime of the period end, typically the effective_datetime of the
    current due amount calculation event
    :param elapsed_term: the number of months that have elapsed as of the period_end_datetime
    :return: True if re-amortisation is needed, False otherwise
    """
    if fixed_to_variable_is_within_fixed_rate_term(
        vault=vault, effective_datetime=period_end_datetime
    ):
        return False
    elif elapsed_term == int(utils_get_parameter(vault, "fixed_interest_term")):
        return variable_get_annual_interest_rate(
            vault=vault, effective_datetime=period_end_datetime
        ) != fixed_get_annual_interest_rate(vault=vault, effective_datetime=period_end_datetime)
    else:
        return variable_should_trigger_reamortisation(
            vault, period_start_datetime, period_end_datetime, elapsed_term
        )


fixed_to_variable_InterestRate = lending_interfaces_InterestRate(
    get_daily_interest_rate=fixed_to_variable_get_daily_interest_rate,
    get_monthly_interest_rate=fixed_to_variable_get_monthly_interest_rate,
    get_annual_interest_rate=fixed_to_variable_get_annual_interest_rate,
)
fixed_to_variable_ReamortisationCondition = lending_interfaces_ReamortisationCondition(
    should_trigger_reamortisation=fixed_to_variable_should_trigger_reamortisation
)

# Objects below have been imported from:
#    overdue.py
# md5:11cacf1a6c91093b7cdfbea3281b9f19

overdue_OVERDUE_REPAYMENT_NOTIFICATION_SUFFIX = "_OVERDUE_REPAYMENT"
overdue_FUND_MOVEMENT_MAP = {
    lending_addresses_PRINCIPAL_DUE: lending_addresses_PRINCIPAL_OVERDUE,
    lending_addresses_INTEREST_DUE: lending_addresses_INTEREST_OVERDUE,
}


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
overpayment_expected_interest_eod_fetcher = BalancesObservationFetcher(
    fetcher_id=overpayment_EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID,
    at=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME, find=Override(hour=0, minute=0, second=0)
    ),
    filter=BalancesFilter(
        addresses=overpayment_EXPECTED_PRINCIPAL + [lending_addresses_DUE_CALCULATION_EVENT_COUNTER]
    ),
)
overpayment_OVERPAYMENT_TRACKER_EFF_FETCHER_ID = "OVERPAYMENT_TRACKER_EFF_FETCHER"
overpayment_overpayment_tracker_eff_fetcher = BalancesObservationFetcher(
    fetcher_id=overpayment_OVERPAYMENT_TRACKER_EFF_FETCHER_ID,
    at=DefinedDateTime.EFFECTIVE_DATETIME,
    filter=BalancesFilter(
        addresses=[
            overpayment_ACCRUED_EXPECTED_INTEREST,
            overpayment_OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
        ]
    ),
)
overpayment_REDUCE_EMI = "reduce_emi"
overpayment_REDUCE_TERM = "reduce_term"
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


def overpayment_get_outstanding_principal(
    balances: BalanceDefaultDict, denomination: str
) -> Decimal:
    return utils_balance_at_coordinates(
        balances=balances, address=lending_addresses_PRINCIPAL, denomination=denomination
    )


def overpayment_handle_overpayment(
    vault: Any, overpayment_amount: Decimal, denomination: str, balances: BalanceDefaultDict
) -> list[Posting]:
    """Creates postings to handle standard overpayments to principal and accrued interest,
    updating any required trackers.

    :param vault: Vault object for the account receiving the overpayment
    :param overpayment_amount: the amount to go towards principal and accrued interest
    :param denomination: denomination of the repayment / loan being repaid
    :param balances: balances at the point of overpayment
    :return: the corresponding postings. Empty list if the overpayment amount isn't greater
    than 0, or if there is nothing to overpay
    """
    if overpayment_amount <= 0:
        return []
    postings: list[Posting] = []
    repayment_amount_remaining = overpayment_amount
    actual_outstanding_principal = overpayment_get_outstanding_principal(balances, denomination)
    if (overpayment_posting_amount := min(overpayment_amount, actual_outstanding_principal)) > 0:
        postings += utils_create_postings(
            amount=overpayment_posting_amount,
            debit_account=vault.account_id,
            debit_address=DEFAULT_ADDRESS,
            credit_account=vault.account_id,
            credit_address=lending_addresses_PRINCIPAL,
            denomination=denomination,
        )
        postings += utils_create_postings(
            amount=overpayment_posting_amount,
            debit_account=vault.account_id,
            debit_address=overpayment_OVERPAYMENT,
            credit_account=vault.account_id,
            credit_address=lending_addresses_INTERNAL_CONTRA,
            denomination=denomination,
        )
        postings += utils_create_postings(
            amount=overpayment_posting_amount,
            debit_account=vault.account_id,
            debit_address=overpayment_OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
            credit_account=vault.account_id,
            credit_address=lending_addresses_INTERNAL_CONTRA,
            denomination=denomination,
        )
        repayment_amount_remaining -= overpayment_posting_amount
    postings += interest_application_repay_accrued_interest(
        vault=vault,
        repayment_amount=repayment_amount_remaining,
        balances=balances,
        denomination=denomination,
    )
    return postings


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


def overpayment_get_residual_cleanup_postings(
    balances: BalanceDefaultDict, account_id: str, denomination: str
) -> list[Posting]:
    return utils_reset_tracker_balances(
        balances=balances,
        account_id=account_id,
        tracker_addresses=[
            overpayment_ACCRUED_EXPECTED_INTEREST,
            overpayment_EMI_PRINCIPAL_EXCESS,
            overpayment_OVERPAYMENT,
            overpayment_OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
        ],
        contra_address=lending_addresses_INTERNAL_CONTRA,
        denomination=denomination,
        tside=Tside.ASSET,
    )


def overpayment_should_trigger_reamortisation(
    vault: Any, period_start_datetime: datetime, period_end_datetime: datetime, elapsed_term: int
) -> bool:
    """Indicates reamortisation is required if there has been an overpayment since the previous due
    amount calculation and the overpayment impact preference is to reduce emi.

    :param vault: vault object for the account
    :param period_start_datetime: start of period to evaluate reamortisation condition. Unused
    in this implementation
    :param period_end_datetime: start of period to evaluate reamortisation condition. Unused
    in this implementation
    :param elapsed_term: elapsed term on the loan. Unused in this implementation
    :return: boolean indicating whether reamortisation is required (True) or not (False).
    """
    balances = vault.get_balances_observation(
        fetcher_id=overpayment_OVERPAYMENT_TRACKER_EFF_FETCHER_ID
    ).balances
    denomination: str = utils_get_parameter(vault=vault, name="denomination")
    overpayment_overpayment_impact_preference_param = (
        overpayment_get_overpayment_preference_parameter(vault=vault)
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


def overpayment_calculate_principal_adjustment(
    vault: Any, balances: Optional[BalanceDefaultDict] = None, denomination: Optional[str] = None
) -> Decimal:
    """
    Determines the adjustment as a result of overpayments that should be made to the principal,
    intended to be used inside the due_amount_calculation event
    :param vault: Vault object for the account, used to fetch the overpayment impact preference
    :param balances: Optional balances. Defaults to latest EOD balances'
    effective_datetime
    :param denomination: denomination to track in. Defaults to the `denomination` parameter
    """
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=overpayment_EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name="denomination")
    overpayment_preference = overpayment_get_overpayment_preference_parameter(vault=vault)
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


overpayment_OverpaymentFeature = lending_interfaces_Overpayment(
    handle_overpayment=overpayment_handle_overpayment
)
overpayment_OverpaymentReamortisationCondition = lending_interfaces_ReamortisationCondition(
    should_trigger_reamortisation=overpayment_should_trigger_reamortisation
)
overpayment_OverpaymentPrincipalAdjustment = lending_interfaces_PrincipalAdjustment(
    calculate_principal_adjustment=overpayment_calculate_principal_adjustment
)
overpayment_OverpaymentResidualCleanupFeature = lending_interfaces_ResidualCleanup(
    get_residual_cleanup_postings=overpayment_get_residual_cleanup_postings
)

# Objects below have been imported from:
#    overpayment_allowance.py
# md5:557090a4d93866e39f9454f6a1e1967a

overpayment_allowance_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER = (
    "REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER"
)
overpayment_allowance_PARAM_DENOMINATION = "denomination"
overpayment_allowance_ONE_YEAR_OVERPAYMENT_ALLOWANCE_FETCHER_ID = "ONE_YEAR_OVERPAYMENT_ALLOWANCE"
overpayment_allowance_ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL_FETCHER_ID = (
    "ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL"
)
overpayment_allowance_EOD_OVERPAYMENT_ALLOWANCE_FETCHER_ID = "EFFECTIVE_OVERPAYMENT_ALLOWANCE"
overpayment_allowance_one_year_overpayment_allowance_interval_fetcher = BalancesIntervalFetcher(
    fetcher_id=overpayment_allowance_ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL_FETCHER_ID,
    start=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        shift=Shift(years=-1),
        find=Override(hour=0, minute=0, second=0),
    ),
    end=DefinedDateTime.EFFECTIVE_DATETIME,
    filter=BalancesFilter(addresses=[overpayment_OVERPAYMENT, lending_addresses_PRINCIPAL]),
)
overpayment_allowance_one_year_overpayment_allowance_fetcher = BalancesObservationFetcher(
    fetcher_id=overpayment_allowance_ONE_YEAR_OVERPAYMENT_ALLOWANCE_FETCHER_ID,
    at=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        shift=Shift(years=-1),
        find=Override(hour=0, minute=0, second=0),
    ),
    filter=BalancesFilter(addresses=[overpayment_OVERPAYMENT, lending_addresses_PRINCIPAL]),
)
overpayment_allowance_eod_overpayment_allowance_fetcher = BalancesObservationFetcher(
    fetcher_id=overpayment_allowance_EOD_OVERPAYMENT_ALLOWANCE_FETCHER_ID,
    at=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME, find=Override(hour=0, minute=0, second=0)
    ),
    filter=BalancesFilter(
        addresses=[
            overpayment_allowance_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            lending_addresses_PRINCIPAL,
            overpayment_OVERPAYMENT,
        ]
    ),
)
overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_EVENT = "CHECK_OVERPAYMENT_ALLOWANCE"
overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE = "overpayment_allowance_percentage"
overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_REMAINING = "overpayment_allowance_remaining"
overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_USED = "overpayment_allowance_used"
overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE = "overpayment_allowance_fee"
overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE = (
    "overpayment_allowance_fee_percentage"
)
overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT = (
    "overpayment_allowance_fee_income_account"
)
overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_PREFIX = "check_overpayment_allowance"
overpayment_allowance_PARAM_CHECK_OVERPAYMENT_ALLOWANCE_HOUR = (
    f"{overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_PREFIX}_hour"
)
overpayment_allowance_PARAM_CHECK_OVERPAYMENT_ALLOWANCE_MINUTE = (
    f"{overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_PREFIX}_minute"
)
overpayment_allowance_PARAM_CHECK_OVERPAYMENT_ALLOWANCE_SECOND = (
    f"{overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_PREFIX}_second"
)
overpayment_allowance_overpayment_allowance_percentage_param = Parameter(
    name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE,
    shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1"), step=Decimal("0.0001")),
    level=ParameterLevel.TEMPLATE,
    description="Percent of outstanding principal that can be paid off per year without charge.",
    display_name="Allowed Overpayment Percentage",
    default_value=Decimal("0.1"),
)
overpayment_allowance_overpayment_allowance_fee_percentage_param = Parameter(
    name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE,
    shape=NumberShape(min_value=Decimal("0"), max_value=Decimal("1"), step=Decimal("0.0001")),
    level=ParameterLevel.TEMPLATE,
    description="Percentage of excess allowance charged as a fee when going over overpayment allowance.",
    display_name="Overpayment Fee Percentage",
    default_value=Decimal("0.05"),
)
overpayment_allowance_overpayment_allowance_fee_income_account_param = Parameter(
    name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    shape=AccountIdShape(),
    description="Internal account for overpayment allowance fee income balance.",
    display_name="Overpayment Allowance Fee Income Account",
    default_value="OVERPAYMENT_ALLOWANCE_FEE_INCOME",
)
overpayment_allowance_check_overpayment_allowance_hour_param = Parameter(
    name=overpayment_allowance_PARAM_CHECK_OVERPAYMENT_ALLOWANCE_HOUR,
    shape=NumberShape(min_value=0, max_value=23, step=1),
    level=ParameterLevel.TEMPLATE,
    description="The hour of the day at which the overpayment allowance usage is checked.",
    display_name="Check Overpayment Allowance Hour",
    default_value=0,
)
overpayment_allowance_check_overpayment_allowance_minute_param = Parameter(
    name=overpayment_allowance_PARAM_CHECK_OVERPAYMENT_ALLOWANCE_MINUTE,
    shape=NumberShape(min_value=0, max_value=59, step=1),
    level=ParameterLevel.TEMPLATE,
    description="The minute of the day at which which overpayment allowance usage is checked.",
    display_name="Check Overpayment Allowance Minute",
    default_value=0,
)
overpayment_allowance_check_overpayment_allowance_second_param = Parameter(
    name=overpayment_allowance_PARAM_CHECK_OVERPAYMENT_ALLOWANCE_SECOND,
    shape=NumberShape(min_value=0, max_value=59, step=1),
    level=ParameterLevel.TEMPLATE,
    description="The second of the day at which which overpayment allowance usage is checked.",
    display_name="Check Overpayment Allowance Second",
    default_value=0,
)
overpayment_allowance_overpayment_allowance_remaining_param = Parameter(
    name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_REMAINING,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Remaining overpayment allowance that can be used without incurring a fee in the current allowance period.",
    display_name="Overpayment Allowance Remaining",
)
overpayment_allowance_overpayment_allowance_used_param = Parameter(
    name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_USED,
    shape=NumberShape(min_value=0),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="The overpayment allowance used in the current allowance period.",
    display_name="Overpayment Allowance Used This Period",
)
overpayment_allowance_overpayment_allowance_fee_param = Parameter(
    name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE,
    shape=NumberShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Overpayment allowance fee charged on the current overpayment balance",
    display_name="Overpayment Allowance Fee",
)
overpayment_allowance_allowance_schedule_time_parameters = [
    overpayment_allowance_check_overpayment_allowance_hour_param,
    overpayment_allowance_check_overpayment_allowance_minute_param,
    overpayment_allowance_check_overpayment_allowance_second_param,
]
overpayment_allowance_allowance_fee_parameters = [
    overpayment_allowance_overpayment_allowance_percentage_param,
    overpayment_allowance_overpayment_allowance_fee_percentage_param,
    overpayment_allowance_overpayment_allowance_fee_income_account_param,
]
overpayment_allowance_derived_parameters = [
    overpayment_allowance_overpayment_allowance_used_param,
    overpayment_allowance_overpayment_allowance_remaining_param,
    overpayment_allowance_overpayment_allowance_fee_param,
]


def overpayment_allowance_event_types(account_type: str) -> list[SmartContractEventType]:
    return [
        SmartContractEventType(
            name=overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_EVENT,
            scheduler_tag_ids=[
                f"{account_type.upper()}_{overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_EVENT}_AST"
            ],
        )
    ]


def overpayment_allowance_scheduled_events(
    vault: Any, allowance_period_start_datetime: datetime
) -> dict[str, ScheduledEvent]:
    """
    Create scheduled event to check the overpayment allowance on account opening anniversary
    :param vault: vault object for the account that requires the schedule
    :param allowance_period_start_datetime: the datetime on which the yearly allowance
    starts. The time components are ignored. The schedule will run one year from this
    :return: Schedule events for the yearly overpayment allowance check
    """
    one_year_from_period_start = allowance_period_start_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + relativedelta(years=1)
    return {
        overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_EVENT: ScheduledEvent(
            start_datetime=one_year_from_period_start - relativedelta(seconds=1),
            expression=utils_get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_PREFIX,
                day=one_year_from_period_start.day,
                month=one_year_from_period_start.month,
            ),
        )
    }


def overpayment_allowance_update_scheduled_event(
    vault: Any, effective_datetime: datetime
) -> dict[str, ScheduledEvent]:
    """
    Re-anchor the schedule event to check the overpayment allowance on the anniversary of the
    effective datetime. This must only be used in the conversion hook as start_datetime is omitted

    :param vault: vault object for the account that requires the schedule
    :param effective_datetime: the datetime on which the yearly allowance is anchored on.
    The time components are ignored. The schedule will run one year from this
    :return: Schedule events for the yearly overpayment allowance check
    """
    one_year_from_effective_datetime = effective_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + relativedelta(years=1)
    return {
        overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_EVENT: ScheduledEvent(
            expression=utils_get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_PREFIX,
                day=one_year_from_effective_datetime.day,
                month=one_year_from_effective_datetime.month,
            ),
            skip=ScheduleSkip(end=one_year_from_effective_datetime + relativedelta(seconds=-1)),
        )
    }


def overpayment_allowance_get_allowance_for_period(
    start_of_period_balances: BalanceDefaultDict, allowance_percentage: Decimal, denomination: str
) -> Decimal:
    """Determine the allowance for the period

    :param start_of_period_balances: balances at start of the allowance period
    :param allowance_percentage: percentage of principal at start of allowance period that can be
    overpaid
    :param denomination: denomination of the account
    :return: the allowance for the period
    """
    return overpayment_allowance_get_allowance(
        principal=utils_balance_at_coordinates(
            balances=start_of_period_balances,
            address=lending_addresses_PRINCIPAL,
            denomination=denomination,
        ),
        allowance_percentage=allowance_percentage,
    )


def overpayment_allowance_get_allowance(
    principal: Decimal, allowance_percentage: Decimal
) -> Decimal:
    """Determine the allowance for a given principal

    :param principal: the principal to use in the allowance calculation
    :param allowance_percentage: the percentage of principal included in the allowance
    :return: the allowance for the period
    """
    return utils_round_decimal(amount=allowance_percentage * principal, decimal_places=2)


def overpayment_allowance_get_allowance_usage(
    start_of_period_balances: BalanceDefaultDict,
    end_of_period_balances: BalanceDefaultDict,
    denomination: str,
) -> Decimal:
    """Determine the allowance usage over the allowance period

    :param start_of_period_balances: balances at start of the allowance period
    :param end_of_period_balances: balances at end of the allowance period
    :param denomination: denomination of the account
    :return: the allowance usage over the allowance period
    """
    used_allowance = utils_balance_at_coordinates(
        balances=end_of_period_balances, address=overpayment_OVERPAYMENT, denomination=denomination
    ) - utils_balance_at_coordinates(
        balances=start_of_period_balances,
        address=overpayment_OVERPAYMENT,
        denomination=denomination,
    )
    used_allowance = max(used_allowance, Decimal(0))
    return used_allowance


def overpayment_allowance_get_allowance_usage_fee(
    allowance: Decimal, used_allowance: Decimal, overpayment_allowance_fee_percentage: Decimal
) -> Decimal:
    """Determine the fee amount to charge

    :param allowance: the allowance for the period
    :param used_allowance: the used allowance for the period
    :param overpayment_allowance_fee_percentage: the percentage of excess used allowance to charge
    :return: the fee amount, which can be 0
    """
    if used_allowance <= allowance:
        return Decimal(0)
    return utils_round_decimal(
        overpayment_allowance_fee_percentage * (used_allowance - allowance), decimal_places=2
    )


def overpayment_allowance_handle_allowance_usage(
    vault: Any, account_type: str
) -> list[CustomInstruction]:
    """Checks the overpayments in the past year and charges a fee if the total exceeds the
    allowance. For use inside the annual schedule when the start of allowance is at
    a fixed delta from the effective date.

    :param vault: vault object for the account with an overpayment allowance to check
    :param account_type: the account's type, used for posting metadata purposes
    :return: CustomInstructions for any required fees
    """
    posting_instructions: list[CustomInstruction] = []
    denomination: str = utils_get_parameter(vault=vault, name="denomination")
    overpayment_percentage: Decimal = utils_get_parameter(
        vault=vault, name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE
    )
    overpayment_allowance_fee_percentage: Decimal = utils_get_parameter(
        vault=vault, name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE
    )
    overpayment_allowance_fee_income_account: str = utils_get_parameter(
        vault=vault, name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT
    )
    start_of_period_balances = vault.get_balances_observation(
        fetcher_id=overpayment_allowance_ONE_YEAR_OVERPAYMENT_ALLOWANCE_FETCHER_ID
    ).balances
    end_of_period_balances = vault.get_balances_observation(
        fetcher_id=overpayment_allowance_EOD_OVERPAYMENT_ALLOWANCE_FETCHER_ID
    ).balances
    current_overpayment_allowance = utils_balance_at_coordinates(
        balances=end_of_period_balances,
        address=overpayment_allowance_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
        denomination=denomination,
    )
    updated_overpayment_allowance = overpayment_allowance_get_allowance_for_period(
        start_of_period_balances=end_of_period_balances,
        allowance_percentage=overpayment_percentage,
        denomination=denomination,
    )
    posting_instructions += overpayment_allowance_set_overpayment_allowance_for_period(
        current_overpayment_allowance=current_overpayment_allowance,
        updated_overpayment_allowance=updated_overpayment_allowance,
        denomination=denomination,
        account_id=vault.account_id,
    )
    posting_instructions += overpayment_allowance__handle_allowance_usage_inner(
        account_id=vault.account_id,
        account_type=account_type,
        start_of_period_balances=start_of_period_balances,
        end_of_period_balances=end_of_period_balances,
        denomination=denomination,
        overpayment_percentage=overpayment_percentage,
        overpayment_allowance_fee_percentage=overpayment_allowance_fee_percentage,
        overpayment_allowance_fee_income_account=overpayment_allowance_fee_income_account,
    )
    return posting_instructions


def overpayment_allowance_handle_allowance_usage_adhoc(
    vault: Any, account_type: str, effective_datetime: datetime
) -> list[CustomInstruction]:
    """Checks the overpayments in the past year and charges a fee if the total exceeds the
    allowance. For use inside ad-hoc hook executions, such as conversion or deactivation,
    where the start_of_period is not at a fixed delta from the effective date.

    :param vault: vault object for the account with an overpayment allowance to check
    :param account_type: the account's type, used for posting metadata purposes
    :param effective_datetime: when the request to handle the usage is made
    """
    denomination: str = utils_get_parameter(vault=vault, name="denomination")
    overpayment_percentage: Decimal = utils_get_parameter(
        vault=vault, name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE
    )
    overpayment_allowance_fee_percentage: Decimal = utils_get_parameter(
        vault=vault, name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE
    )
    overpayment_allowance_fee_income_account: str = utils_get_parameter(
        vault=vault, name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT
    )
    one_year_balances = vault.get_balances_timeseries(
        fetcher_id=overpayment_allowance_ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL_FETCHER_ID
    )
    start_of_period_datetime = overpayment_allowance_get_start_of_current_allowance_period(
        effective_datetime=effective_datetime,
        account_creation_datetime=vault.get_account_creation_datetime(),
        check_overpayment_allowance_last_execution_datetime=vault.get_last_execution_datetime(
            event_type=overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_EVENT
        ),
    )
    start_of_period_balances = overpayment_allowance__extract_balance_default_dict_from_interval(
        denomination=denomination,
        balance_interval=one_year_balances,
        effective_datetime=start_of_period_datetime,
    )
    end_of_period_balances = overpayment_allowance__extract_balance_default_dict_from_interval(
        denomination=denomination,
        balance_interval=one_year_balances,
        effective_datetime=effective_datetime,
    )
    return overpayment_allowance__handle_allowance_usage_inner(
        account_id=vault.account_id,
        account_type=account_type,
        start_of_period_balances=start_of_period_balances,
        end_of_period_balances=end_of_period_balances,
        denomination=denomination,
        overpayment_percentage=overpayment_percentage,
        overpayment_allowance_fee_percentage=overpayment_allowance_fee_percentage,
        overpayment_allowance_fee_income_account=overpayment_allowance_fee_income_account,
    )


def overpayment_allowance__handle_allowance_usage_inner(
    account_id: str,
    account_type: str,
    start_of_period_balances: BalanceDefaultDict,
    end_of_period_balances: BalanceDefaultDict,
    denomination: str,
    overpayment_percentage: Decimal,
    overpayment_allowance_fee_percentage: Decimal,
    overpayment_allowance_fee_income_account: str,
) -> list[CustomInstruction]:
    used_allowance = overpayment_allowance_get_allowance_usage(
        start_of_period_balances=start_of_period_balances,
        end_of_period_balances=end_of_period_balances,
        denomination=denomination,
    )
    allowance = overpayment_allowance_get_allowance_for_period(
        start_of_period_balances=start_of_period_balances,
        allowance_percentage=overpayment_percentage,
        denomination=denomination,
    )
    fee_amount = overpayment_allowance_get_allowance_usage_fee(
        used_allowance=used_allowance,
        allowance=allowance,
        overpayment_allowance_fee_percentage=overpayment_allowance_fee_percentage,
    )
    return fees_fee_custom_instruction(
        customer_account_id=account_id,
        denomination=denomination,
        amount=fee_amount,
        internal_account=overpayment_allowance_fee_income_account,
        customer_account_address=lending_addresses_PENALTIES,
        instruction_details=utils_standard_instruction_details(
            description=f"Overpayment fee charged due to used allowance {used_allowance} {denomination} exceeding allowance {allowance} {denomination}",
            event_type="CHARGE_OVERPAYMENT_FEE",
            gl_impacted=True,
            account_type=account_type,
        ),
    )


def overpayment_allowance__extract_balance_default_dict_from_interval(
    denomination: str,
    balance_interval: Mapping[BalanceCoordinate, BalanceTimeseries],
    effective_datetime: datetime,
) -> BalanceDefaultDict:
    overpayment_coordinate = BalanceCoordinate(
        account_address=overpayment_OVERPAYMENT,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        phase=Phase.COMMITTED,
    )
    principal_coordinate = BalanceCoordinate(
        account_address=lending_addresses_PRINCIPAL,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        phase=Phase.COMMITTED,
    )
    overpayment_at_effective_datetime = balance_interval[overpayment_coordinate].at(
        at_datetime=effective_datetime
    )
    principal_at_effective_datetime = balance_interval[principal_coordinate].at(
        at_datetime=effective_datetime
    )
    return BalanceDefaultDict(
        mapping={
            overpayment_coordinate: overpayment_at_effective_datetime,
            principal_coordinate: principal_at_effective_datetime,
        }
    )


def overpayment_allowance_get_overpayment_allowance_status(
    vault: Any, effective_datetime: datetime
) -> tuple[Decimal, Decimal]:
    """Determines the original and used overpayment allowance for the current allowance period.
    For use in adhoc situations (e.g. derived parameters)
    Both numbers should be >= 0, but there is no strict relationship between the two (i.e.
    used allowance can be >,=, < original allowance).

    :param vault: vault object for the relevant account
    :param effective_datetime: datetime for which the overpayment status is calculated
    :return: the original and used overpayment allowance
    """
    denomination: str = utils_get_parameter(vault=vault, name="denomination")
    one_year_balances = vault.get_balances_timeseries(
        fetcher_id=overpayment_allowance_ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL_FETCHER_ID
    )
    start_of_period_datetime = overpayment_allowance_get_start_of_current_allowance_period(
        effective_datetime=effective_datetime,
        account_creation_datetime=vault.get_account_creation_datetime(),
        check_overpayment_allowance_last_execution_datetime=vault.get_last_execution_datetime(
            event_type=overpayment_allowance_CHECK_OVERPAYMENT_ALLOWANCE_EVENT
        ),
    )
    allowance_percentage = utils_get_parameter(
        vault=vault,
        name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE,
        at_datetime=start_of_period_datetime,
    )
    start_of_period_balances = overpayment_allowance__extract_balance_default_dict_from_interval(
        denomination=denomination,
        balance_interval=one_year_balances,
        effective_datetime=start_of_period_datetime,
    )
    end_of_period_balances = overpayment_allowance__extract_balance_default_dict_from_interval(
        denomination=denomination,
        balance_interval=one_year_balances,
        effective_datetime=effective_datetime,
    )
    overpayment_allowance_used = overpayment_allowance_get_allowance_usage(
        start_of_period_balances=start_of_period_balances,
        end_of_period_balances=end_of_period_balances,
        denomination=denomination,
    )
    overpayment_allowance = overpayment_allowance_get_allowance_for_period(
        start_of_period_balances=start_of_period_balances,
        allowance_percentage=allowance_percentage,
        denomination=denomination,
    )
    return (overpayment_allowance, overpayment_allowance_used)


def overpayment_allowance_get_start_of_current_allowance_period(
    effective_datetime: datetime,
    account_creation_datetime: datetime,
    check_overpayment_allowance_last_execution_datetime: Optional[datetime] = None,
) -> datetime:
    """Determines the start of the allowance period in progress. The initial allowance period
    starts on account creation date and then restarts at midnight on the account creation
    anniversary.

    :param effective_datetime: defines
    :param account_creation_datetime: datetime that the account was created on
    :param handle_allowance_usage_last_execution_datetime: when the handle allowance usage schedule
    last ran, if ever
    :return: the start of the allowance period
    """
    if check_overpayment_allowance_last_execution_datetime is not None:
        return check_overpayment_allowance_last_execution_datetime.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    one_year_ago = effective_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - relativedelta(years=1)
    return max(account_creation_datetime, one_year_ago)


def overpayment_allowance_set_overpayment_allowance_for_period(
    current_overpayment_allowance: Decimal,
    updated_overpayment_allowance: Decimal,
    denomination: str,
    account_id: str,
) -> list[CustomInstruction]:
    """
    Sets the overpayment allowance amount for the current period by initialising the overpayment
    allowance tracker balance with this amount.

    NOTE: This function uses the overpayment allowance tracker balance to track the overpayment
    allowance, and so it likely duplicates work that exists in other functions in this feature.
    This feature should be refactored to remove this duplication by relying only on the
    overpayment allowance tracker balance.
    See https://pennyworth.atlassian.net/browse/INC-8754

    :param current_overpayment_allowance: The overpayment allowance amount
    currently in the overpayment allowance tracker balance.
    :param updated_overpayment_allowance: The overpayment allowance amount for the next period
    :param denomination: The denomination of the loan being repaid
    :param account_id: The id of the loan account
    :return: The list of postings to set the overpayment allowance tracker balance
    to the overpayment allowance amount
    """
    postings: list[Posting] = []
    overpayment_allowance_delta = current_overpayment_allowance - updated_overpayment_allowance
    if overpayment_allowance_delta == Decimal("0"):
        return []
    if overpayment_allowance_delta < Decimal("0"):
        credit_address = addresses_INTERNAL_CONTRA
        debit_address = overpayment_allowance_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER
        overpayment_allowance_delta = abs(overpayment_allowance_delta)
    else:
        credit_address = overpayment_allowance_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER
        debit_address = addresses_INTERNAL_CONTRA
    postings = utils_create_postings(
        amount=overpayment_allowance_delta,
        debit_account=account_id,
        debit_address=debit_address,
        credit_account=account_id,
        credit_address=credit_address,
        denomination=denomination,
    )
    return [
        CustomInstruction(
            postings=postings,
            instruction_details={
                "description": "Resetting the overpayment allowance tracker balance",
                "event": "RESET_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER",
            },
        )
    ]


def overpayment_allowance_reduce_overpayment_allowance(
    vault: Any, overpayment_amount: Decimal, denomination: str, balances: BalanceDefaultDict
) -> list[Posting]:
    """
    Creates postings to update the overpayment allowance tracker by removing
    the overpayment amount from the overpayment allowance for the
    current allowance period.

    NOTE: This function uses the overpayment allowance tracker balance to track the overpayment
    allowance, and so it likely duplicates work that exists in other functions in this feature.
    This feature should be refactored to remove this duplication by relying only on the
    overpayment allowance tracker balance.
    See https://pennyworth.atlassian.net/browse/INC-8754

    :param vault: The vault object for the account receiving the overpayment
    :param overpayment_amount: The amount overpaid
    :param denomination: The denomination of the repayment / loan being repaid
    :param balances: The balances at the point of overpayment
    :return: The corresponding postings to update the overpayment allowance tracker balance
    """
    postings: list[Posting] = []
    outstanding_principal = utils_balance_at_coordinates(
        balances=balances, address=lending_addresses_PRINCIPAL, denomination=denomination
    )
    if (overpayment_posting_amount := min(overpayment_amount, outstanding_principal)) > Decimal(
        "0"
    ):
        postings += utils_create_postings(
            amount=overpayment_posting_amount,
            debit_account=vault.account_id,
            debit_address=addresses_INTERNAL_CONTRA,
            credit_account=vault.account_id,
            credit_address=overpayment_allowance_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=denomination,
        )
    return postings


def overpayment_allowance_get_overpayment_allowance_fee_for_early_repayment(
    vault: Any, denomination: Optional[str] = None, balances: Optional[BalanceDefaultDict] = None
) -> Decimal:
    """
    Calculates the overpayment allowance fee if the total amount on the loan were to be repaid.

    NOTE: This function uses the overpayment allowance tracker balance to calculate the
    overpayment allowance fee, and so it likely duplicates work that exists in other
    functions in this feature. This feature should be refactored to remove this duplication
    by relying only on the overpayment allowance tracker balance.
    See https://pennyworth.atlassian.net/browse/INC-8754

    :param overpayment_allowance_fee_percentage: The percentage of the exceeded overpayment
    allowance amount that gets charged as a fee
    :param denomination: The denomination of the loan being repaid
    :param balances: The balances at the time of overpayment
    :return: The overpayment allowance fee
    """
    if denomination is None:
        denomination = utils_get_parameter(
            vault=vault, name=overpayment_allowance_PARAM_DENOMINATION
        )
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    overpayment_allowance_fee_percentage = utils_get_parameter(
        vault=vault, name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE
    )
    total_outstanding_debt = utils_sum_balances(
        balances=balances, addresses=lending_addresses_ALL_OUTSTANDING, denomination=denomination
    )
    due_amount = utils_sum_balances(
        balances=balances,
        addresses=lending_addresses_REPAYMENT_HIERARCHY,
        denomination=denomination,
    )
    overpayment_needed_to_completely_repay_loan = total_outstanding_debt - due_amount
    inflight_overpayment_allowance_amount = (
        utils_balance_at_coordinates(
            balances=balances,
            address=overpayment_allowance_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
            denomination=denomination,
        )
        - overpayment_needed_to_completely_repay_loan
    )
    overpayment_allowance_exceeded_amount = (
        abs(inflight_overpayment_allowance_amount)
        if inflight_overpayment_allowance_amount < Decimal("0")
        else Decimal("0")
    )
    return utils_round_decimal(
        amount=overpayment_allowance_fee_percentage * overpayment_allowance_exceeded_amount,
        decimal_places=2,
    )


def overpayment_allowance_initialise_overpayment_allowance_from_principal_amount(
    vault: Any, principal: Decimal, denomination: Optional[str] = None
) -> list[CustomInstruction]:
    """
    Returns the postings needed to set the overpayment allowance amount to the
    principal * the overpayment allowance percentage and assumes no previous
    overpayment allowance tracker balance exists. In other words, this function
    is intended to be used in the activation hook.

    NOTE: This function uses the overpayment allowance tracker balance to calculate the
    overpayment allowance fee, and so it likely duplicates work that exists in other
    functions in this feature. This feature should be refactored to remove this duplication
    by relying only on the overpayment allowance tracker balance.
    See https://pennyworth.atlassian.net/browse/INC-8754

    :param vault: The vault object
    :param principal: The principal from which to calculate the overpayment allowance
    :param denomination: The denomination of the loan being repaid
    :return: The postings to set the overpayment allowance as a percent of the principal
    """
    if denomination is None:
        denomination = utils_get_parameter(
            vault=vault, name=overpayment_allowance_PARAM_DENOMINATION
        )
    overpayment_allowance_percentage: Decimal = utils_get_parameter(
        vault=vault, name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_PERCENTAGE
    )
    return overpayment_allowance_set_overpayment_allowance_for_period(
        current_overpayment_allowance=Decimal("0"),
        updated_overpayment_allowance=principal * overpayment_allowance_percentage,
        denomination=denomination,
        account_id=vault.account_id,
    )


def overpayment_allowance_get_residual_cleanup_postings(
    balances: BalanceDefaultDict, account_id: str, denomination: str
) -> list[Posting]:
    """
    Returns the postings needed to cleanup the overpayment allowance tracker balance.

    :param balances: The balances, including the overpayment allowance tracker balance,
    that need to be cleared.
    :param account_id: The id of the loan account
    :param denomination: The denomination of the loan being repaid
    :return: A list of postings to net out the overpayment allowance tracker balance
    """
    overpayment_allowance_amount = utils_balance_at_coordinates(
        balances=balances,
        address=overpayment_allowance_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
        denomination=denomination,
    )
    return utils_create_postings(
        amount=abs(overpayment_allowance_amount),
        debit_account=account_id,
        credit_account=account_id,
        debit_address=addresses_INTERNAL_CONTRA
        if overpayment_allowance_amount > 0
        else overpayment_allowance_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
        credit_address=overpayment_allowance_REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER
        if overpayment_allowance_amount > 0
        else addresses_INTERNAL_CONTRA,
        denomination=denomination,
    )


overpayment_allowance_OverpaymentAllowanceFeature = lending_interfaces_Overpayment(
    handle_overpayment=overpayment_allowance_reduce_overpayment_allowance
)
overpayment_allowance_OverpaymentAllowanceResidualCleanupFeature = (
    lending_interfaces_ResidualCleanup(
        get_residual_cleanup_postings=overpayment_allowance_get_residual_cleanup_postings
    )
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
#    repayment_holiday.py
# md5:8ab69326d0731879f6300743f6dbefd4

repayment_holiday_REPAYMENT_HOLIDAY = "REPAYMENT_HOLIDAY"
repayment_holiday_PARAM_DELINQUENCY_BLOCKING_FLAGS = "delinquency_blocking_flags"
repayment_holiday_PARAM_DUE_AMOUNT_CALCULATION_BLOCKING_FLAGS = (
    "due_amount_calculation_blocking_flags"
)
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


def repayment_holiday_is_overdue_amount_calculation_blocked(
    vault: Any, effective_datetime: datetime
) -> bool:
    return utils_is_flag_in_list_applied(
        vault=vault,
        parameter_name=repayment_holiday_PARAM_OVERDUE_AMOUNT_CALCULATION_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def repayment_holiday_is_penalty_accrual_blocked(vault: Any, effective_datetime: datetime) -> bool:
    return utils_is_flag_in_list_applied(
        vault=vault,
        parameter_name=repayment_holiday_PARAM_PENALTY_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def repayment_holiday_is_repayment_blocked(vault: Any, effective_datetime: datetime) -> bool:
    return utils_is_flag_in_list_applied(
        vault=vault,
        parameter_name=repayment_holiday_PARAM_REPAYMENT_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    )


def repayment_holiday_reject_repayment(
    vault: Any, effective_datetime: datetime
) -> Optional[Rejection]:
    return (
        Rejection(
            message="Repayments are blocked for this account.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        if repayment_holiday_is_repayment_blocked(
            vault=vault, effective_datetime=effective_datetime
        )
        else None
    )


def repayment_holiday_should_trigger_reamortisation_no_impact_preference(
    vault: Any,
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

    :param vault: vault object for the account
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
        vault=vault,
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


repayment_holiday_ReamortisationConditionWithoutPreference = lending_interfaces_ReamortisationCondition(
    should_trigger_reamortisation=repayment_holiday_should_trigger_reamortisation_no_impact_preference
)

# Objects below have been imported from:
#    mortgage.py
# md5:8a7cf699780f6b2d531008e089e9e374

ACCOUNT_TYPE = "MORTGAGE"
CAPITALISED_INTEREST_TRACKER = "CAPITALISED_INTEREST_TRACKER"
ACCRUED_INTEREST_PENDING_CAPITALISATION = "ACCRUED_INTEREST_PENDING_CAPITALISATION"
ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION = "ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION"
INSTRUCTION_DETAILS_KEY_FEE = "fee"
INSTRUCTION_DETAILS_KEY_INTEREST_ADJUSTMENT = "interest_adjustment"
INSTRUCTION_DETAILS_KEY_EARLY_REPAYMENT = "early_repayment"
INTEREST_APPLICATION_FEATURE = interest_application_InterestApplication
CHECK_DELINQUENCY = "CHECK_DELINQUENCY"
event_types = [
    *interest_accrual_event_types(ACCOUNT_TYPE),
    *due_amount_calculation_event_types(ACCOUNT_TYPE),
    *overpayment_allowance_event_types(ACCOUNT_TYPE),
    SmartContractEventType(
        name=CHECK_DELINQUENCY, scheduler_tag_ids=[f"{ACCOUNT_TYPE}_{CHECK_DELINQUENCY}_AST"]
    ),
]
data_fetchers = [
    fetchers_EFFECTIVE_OBSERVATION_FETCHER,
    fetchers_LIVE_BALANCES_BOF,
    *interest_accrual_data_fetchers,
    interest_application_accrued_interest_eff_fetcher,
    interest_application_accrued_interest_one_month_ago_fetcher,
    overpayment_overpayment_tracker_eff_fetcher,
    overpayment_expected_interest_eod_fetcher,
    overpayment_allowance_one_year_overpayment_allowance_interval_fetcher,
    overpayment_allowance_eod_overpayment_allowance_fetcher,
    overpayment_allowance_one_year_overpayment_allowance_fetcher,
]
MARK_DELINQUENT_NOTIFICATION = f"{ACCOUNT_TYPE}_MARK_DELINQUENT"
CLOSURE_NOTIFICATION = f"{ACCOUNT_TYPE}_CLOSURE"
notification_types = [MARK_DELINQUENT_NOTIFICATION, CLOSURE_NOTIFICATION]
PARAM_DENOMINATION = "denomination"
PARAM_GRACE_PERIOD = "grace_period"
PARAM_INTEREST_ONLY_TERM = "interest_only_term"
PARAM_PRODUCT_SWITCH = "product_switch"
PARAM_LATE_REPAYMENT_FEE = "late_repayment_fee"
PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST = "penalty_compounds_overdue_interest"
PARAM_PENALTY_INTEREST_RATE = "penalty_interest_rate"
PARAM_PENALTY_INCLUDES_BASE_RATE = "penalty_includes_base_rate"
PARAM_DELINQUENCY_FLAG = "delinquency_flag"
PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "accrued_interest_receivable_account"
PARAM_INTEREST_RECEIVED_ACCOUNT = "interest_received_account"
PARAM_PENALTY_INTEREST_RECEIVED_ACCOUNT = "penalty_interest_received_account"
PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT = "early_repayment_fee_income_account"
PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "late_repayment_fee_income_account"
CHECK_DELINQUENCY_PREFIX = "check_delinquency"
PARAM_CHECK_DELINQUENCY_HOUR = f"{CHECK_DELINQUENCY_PREFIX}_hour"
PARAM_CHECK_DELINQUENCY_MINUTE = f"{CHECK_DELINQUENCY_PREFIX}_minute"
PARAM_CHECK_DELINQUENCY_SECOND = f"{CHECK_DELINQUENCY_PREFIX}_second"
PARAM_IS_INTEREST_ONLY_TERM = "is_interest_only_term"
PARAM_OUTSTANDING_PAYMENTS = "outstanding_payments"
PARAM_DERIVED_EARLY_REPAYMENT_FEE = "derived_early_repayment_fee"
PARAM_EARLY_REPAYMENT_FEE = "early_repayment_fee"
PARAM_TOTAL_EARLY_REPAYMENT_FEE = "total_early_repayment_fee"
parameters = [
    Parameter(
        name=PARAM_INTEREST_ONLY_TERM,
        shape=NumberShape(min_value=Decimal(0), step=Decimal(1)),
        level=ParameterLevel.INSTANCE,
        description="The agreed length of the interest only portion of the mortgage (in months).",
        display_name="Interest Only Mortgage Term (months)",
        default_value=Decimal(0),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=PARAM_PRODUCT_SWITCH,
        shape=OptionalShape(shape=common_parameters_BooleanShape),
        description="When set to True, account product version upgrades are treated as product switches.",
        display_name="Product Switch",
        level=ParameterLevel.INSTANCE,
        default_value=OptionalValue(common_parameters_BooleanValueFalse),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=PARAM_DENOMINATION,
        shape=DenominationShape(),
        level=ParameterLevel.TEMPLATE,
        description="Currency in which the product operates.",
        display_name="Denomination",
        default_value="GBP",
    ),
    Parameter(
        name=PARAM_GRACE_PERIOD,
        shape=NumberShape(min_value=0, max_value=27, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The number of days after which the account becomes delinquent if the overdue amounts and penalties are not paid in full.",
        display_name="Grace Period (days)",
        default_value=15,
    ),
    Parameter(
        name=PARAM_CHECK_DELINQUENCY_HOUR,
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which delinquency is checked.",
        display_name="Check Delinquency Hour",
        default_value=0,
    ),
    Parameter(
        name=PARAM_CHECK_DELINQUENCY_MINUTE,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The minute of the day at which delinquency is checked.",
        display_name="Check Delinquency Minute",
        default_value=0,
    ),
    Parameter(
        name=PARAM_CHECK_DELINQUENCY_SECOND,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The second of the day at which delinquency is checked.",
        display_name="Check Delinquency Second",
        default_value=2,
    ),
    Parameter(
        name=PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST,
        shape=common_parameters_BooleanShape,
        level=ParameterLevel.TEMPLATE,
        description="If True, include both overdue interest and overdue principal in the penalty interest calculation. If False, only include overdue principal.",
        display_name="Penalty Compounds Overdue Interest",
        default_value=common_parameters_BooleanValueFalse,
    ),
    Parameter(
        name=PARAM_PENALTY_INTEREST_RATE,
        shape=NumberShape(step=Decimal("0.01")),
        level=ParameterLevel.TEMPLATE,
        description="The annual interest rate to be applied when accruing penalty interest.",
        display_name="Penalty Interest Rate (p.a)",
        default_value=Decimal("0.24"),
    ),
    Parameter(
        name=PARAM_PENALTY_INCLUDES_BASE_RATE,
        shape=common_parameters_BooleanShape,
        level=ParameterLevel.TEMPLATE,
        description="Whether to add base interest rate on top of penalty interest rate.",
        display_name="Penalty Includes Base Rate",
        default_value=common_parameters_BooleanValueTrue,
    ),
    Parameter(
        name=PARAM_LATE_REPAYMENT_FEE,
        shape=NumberShape(min_value=0),
        level=ParameterLevel.TEMPLATE,
        description="Fee to be charged as a result of late repayment.",
        display_name="Late Repayment Fee",
        default_value=Decimal("25"),
    ),
    Parameter(
        name=PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT,
        shape=AccountIdShape(),
        level=ParameterLevel.TEMPLATE,
        description="Internal account for early repayment fee income balance.",
        display_name="Early Repayment Fee Income Account",
        default_value="EARLY_REPAYMENT_FEE_INCOME",
    ),
    Parameter(
        name=PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
        shape=AccountIdShape(),
        level=ParameterLevel.TEMPLATE,
        description="Internal account for late repayment fee income balance.",
        display_name="Late Repayment Fee Income Account",
        default_value="LATE_REPAYMENT_FEE_INCOME",
    ),
    Parameter(
        name=PARAM_IS_INTEREST_ONLY_TERM,
        shape=StringShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="Is this account within the interest only term period.",
        display_name="In Interest Only Term Period",
    ),
    Parameter(
        name=PARAM_OUTSTANDING_PAYMENTS,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="Unpaid dues, overdues and penalties",
        display_name="Outstanding Payments",
    ),
    Parameter(
        name=PARAM_EARLY_REPAYMENT_FEE,
        shape=NumberShape(),
        level=ParameterLevel.TEMPLATE,
        description="Fee applied if the mortgage is completely repaid early. If this value is negative, the fee is calculated as the overpayment allowance fee percentage * the total remaining principal. If this value is non-negative, it represents a flat fee to be applied.",
        display_name="Early Repayment Fee",
        default_value=Decimal(0),
    ),
    Parameter(
        name=PARAM_DERIVED_EARLY_REPAYMENT_FEE,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="Fee applied if the mortgage is completely repaid early. Calculated from the early_repayment_fee parameter.",
        display_name="Early Repayment Fee",
    ),
    Parameter(
        name=PARAM_TOTAL_EARLY_REPAYMENT_FEE,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="Combination of the overpayment allowance fee and the early repayment fee.",
        display_name="Total Early Repayment Fee",
    ),
    derived_params_total_outstanding_debt_parameter,
    derived_params_total_remaining_principal_parameter,
    derived_params_remaining_term_parameter,
    Parameter(
        name=PARAM_DELINQUENCY_FLAG,
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        description="Flag definition id to be used for account delinquency.",
        display_name="Account Delinquency Flag",
        default_value=dumps(["ACCOUNT_DELINQUENT"]),
    ),
    Parameter(
        name=PARAM_INTEREST_RECEIVED_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for interest received balance.",
        display_name="Interest Received Account",
        shape=AccountIdShape(),
        default_value="INTEREST_RECEIVED",
    ),
    Parameter(
        name=PARAM_PENALTY_INTEREST_RECEIVED_ACCOUNT,
        shape=AccountIdShape(),
        level=ParameterLevel.TEMPLATE,
        description="Internal account for penalty interest received balance.",
        display_name="Penalty Interest Received Account",
        default_value="PENALTY_INTEREST_RECEIVED",
    ),
    *disbursement_parameters,
    *due_amount_calculation_schedule_parameters,
    due_amount_calculation_next_repayment_date_parameter,
    *fixed_parameters,
    *fixed_to_variable_parameters,
    *interest_accrual_account_parameters,
    *interest_accrual_accrual_parameters,
    *interest_accrual_schedule_parameters,
    interest_application_application_precision_param,
    overpayment_overpayment_impact_preference_param,
    *overpayment_allowance_derived_parameters,
    *overpayment_allowance_allowance_fee_parameters,
    *overpayment_allowance_allowance_schedule_time_parameters,
    *variable_parameters,
    lending_parameters_total_repayment_count_parameter,
    repayment_holiday_delinquency_blocking_param,
    repayment_holiday_repayment_blocking_param,
    repayment_holiday_due_amount_calculation_blocking_param,
    repayment_holiday_overdue_amount_calculation_blocking_param,
    repayment_holiday_penalty_blocking_param,
    interest_capitalisation_capitalised_interest_receivable_account_param,
    interest_capitalisation_capitalised_interest_received_account_param,
    interest_capitalisation_capitalise_penalty_interest_param,
]


def _handle_delinquency(
    vault: Any,
    hook_arguments: ScheduledEventHookArguments,
    is_delinquency_schedule_event: bool,
    balances: Optional[BalanceDefaultDict] = None,
) -> tuple[list[AccountNotificationDirective], list[UpdateAccountEventTypeDirective]]:
    """
    Handle delinquency for the loan, expected to be called from the overdue or delinquency events.
    If called from the overdue event and the grace period is zero, then the account
    should be marked as delinquent immediately, else schedule a delinquency check grace period
    number of days in the future.
    If called from the delinquency event then the account should be marked as delinquent
    immediately and the delinquency schedule is updated to be skipped

    :param vault: Vault object for the account
    :param hook_arguments: scheduled_event_hook arguments
    :param is_delinquency_schedule_event: bool to determine whether the function is called from
    the delinquency schedule event or not
    :param balances: optional BalanceDefaultDict, used to determine if overdue balances exist, if
    not passed in the latest balances observation is retrieved from the vault object
    :return: tuple of 2 lists, the account notification directives and schedule update directives
    """
    mark_delinquent_notifications: list[AccountNotificationDirective] = []
    delinquent_schedule_updates: list[UpdateAccountEventTypeDirective] = []
    effective_datetime = hook_arguments.effective_datetime
    grace_period = int(utils_get_parameter(vault=vault, name=PARAM_GRACE_PERIOD))
    evaluate_delinquency_status = grace_period == 0 or is_delinquency_schedule_event
    if evaluate_delinquency_status:
        next_schedule_datetime = effective_datetime + relativedelta(months=1)
        delinquent_schedule_updates.extend(
            _update_delinquency_schedule(
                vault=vault, next_schedule_datetime=next_schedule_datetime, skip_schedule=True
            )
        )
        mark_delinquent_notifications.extend(
            _mark_account_delinquent(
                vault=vault, effective_datetime=effective_datetime, balances=balances
            )
        )
    else:
        grace_period_end = effective_datetime + relativedelta(days=grace_period)
        delinquent_schedule_updates.extend(
            _update_delinquency_schedule(
                vault=vault, next_schedule_datetime=grace_period_end, skip_schedule=False
            )
        )
    return (mark_delinquent_notifications, delinquent_schedule_updates)


def _mark_account_delinquent(
    vault: Any, effective_datetime: datetime, balances: Optional[BalanceDefaultDict] = None
) -> list[AccountNotificationDirective]:
    """
    Establish if account should be placed into delinquency

    :param vault: Vault object for the account that might be delinquent. Used to
    access balances, account_id, flags
    :param effective_datetime: datetime
    :return: list[AccountNotificationDirective]
    """
    if repayment_holiday_is_delinquency_blocked(
        vault=vault, effective_datetime=effective_datetime
    ) or utils_is_flag_in_list_applied(
        vault=vault, parameter_name=PARAM_DELINQUENCY_FLAG, effective_datetime=effective_datetime
    ):
        return []
    denomination: str = utils_get_parameter(vault, name=PARAM_DENOMINATION)
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if _get_late_payment_balance(balances=balances, denomination=denomination) > Decimal("0"):
        return [
            AccountNotificationDirective(
                notification_type=MARK_DELINQUENT_NOTIFICATION,
                notification_details={"account_id": str(vault.account_id)},
            )
        ]
    return []


def _update_delinquency_schedule(
    vault: Any, next_schedule_datetime: datetime, skip_schedule: bool
) -> list[UpdateAccountEventTypeDirective]:
    return [
        UpdateAccountEventTypeDirective(
            event_type=CHECK_DELINQUENCY,
            expression=utils_get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=CHECK_DELINQUENCY_PREFIX,
                day=next_schedule_datetime.day,
                month=next_schedule_datetime.month,
                year=next_schedule_datetime.year,
            ),
            skip=skip_schedule,
        )
    ]


def _get_standard_interest_accrual_custom_instructions(
    vault: Any,
    hook_arguments: ScheduledEventHookArguments,
    inflight_postings: list[CustomInstruction],
) -> list[CustomInstruction]:
    accrue_to_pending_capitalisation = repayment_holiday_is_due_amount_calculation_blocked(
        vault=vault, effective_datetime=hook_arguments.effective_datetime
    )
    if accrue_to_pending_capitalisation:
        customer_accrual_address: Optional[str] = ACCRUED_INTEREST_PENDING_CAPITALISATION
        accrual_internal_account: Optional[str] = utils_get_parameter(
            vault=vault, name=interest_capitalisation_PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT
        )
        additional_postings = []
    else:
        customer_accrual_address = None
        accrual_internal_account = None
        additional_postings = overpayment_track_interest_on_expected_principal(
            vault=vault,
            hook_arguments=hook_arguments,
            interest_rate_feature=fixed_to_variable_InterestRate,
        )
    return (
        interest_accrual_daily_accrual_logic(
            vault=vault,
            hook_arguments=hook_arguments,
            account_type=ACCOUNT_TYPE,
            interest_rate_feature=fixed_to_variable_InterestRate,
            principal_addresses=[lending_addresses_PRINCIPAL],
            inflight_postings=inflight_postings,
            customer_accrual_address=customer_accrual_address,
            accrual_internal_account=accrual_internal_account,
        )
        + additional_postings
    )


def _handle_interest_capitalisation(
    vault: Any,
    effective_datetime: datetime,
    account_type: str,
    balances: Optional[BalanceDefaultDict] = None,
    interest_to_capitalise_address: str = lending_addresses_ACCRUED_INTEREST_PENDING_CAPITALISATION,
) -> list[CustomInstruction]:
    if _should_handle_interest_capitalisation(vault=vault, effective_datetime=effective_datetime):
        return interest_capitalisation_handle_interest_capitalisation(
            vault=vault,
            account_type=account_type,
            balances=balances,
            interest_to_capitalise_address=interest_to_capitalise_address,
        )
    else:
        return []


def _get_penalty_interest_accrual_custom_instruction(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> list[CustomInstruction]:
    """
    Processes penalty interest accrual which is accrued on overdue balance. Penalty interest is
    prevented by any penalty accrual blocking flags. It will optionally:
    - compound on overdue interest
    - accrue for capitalisation in the next due amount calc
    - include the base rate in the penalty rate
    If not capitalised, penalty interest is immediately applied
    """
    effective_datetime: datetime = hook_arguments.effective_datetime
    if repayment_holiday_is_penalty_accrual_blocked(
        vault=vault, effective_datetime=effective_datetime
    ):
        return []
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_EOD_FETCHER_ID
    ).balances
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    penalty_compounds_overdue_interest: bool = utils_get_parameter(
        vault=vault, name=PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST, is_boolean=True
    )
    days_in_year: str = utils_get_parameter(
        vault=vault, name=interest_accrual_PARAM_DAYS_IN_YEAR, is_union=True
    )
    annual_interest_rate: Decimal = utils_get_parameter(
        vault=vault, name=PARAM_PENALTY_INTEREST_RATE
    )
    if utils_get_parameter(vault=vault, name=PARAM_PENALTY_INCLUDES_BASE_RATE, is_boolean=True):
        annual_interest_rate += fixed_to_variable_get_annual_interest_rate(
            vault=vault, effective_datetime=effective_datetime, balances=balances
        )
    if interest_capitalisation_is_capitalise_penalty_interest(vault=vault):
        precision: int = utils_get_parameter(
            vault=vault, name=interest_accrual_PARAM_ACCRUAL_PRECISION
        )
        customer_address = ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION
        internal_account = utils_get_parameter(
            vault=vault, name=interest_capitalisation_PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT
        )
    else:
        precision = utils_get_parameter(
            vault=vault, name=interest_application_PARAM_APPLICATION_PRECISION
        )
        customer_address = lending_addresses_PENALTIES
        internal_account = utils_get_parameter(
            vault=vault, name=PARAM_PENALTY_INTEREST_RECEIVED_ACCOUNT
        )
    overdue_capital = _get_overdue_capital(
        balances=balances,
        denomination=denomination,
        include_overdue_interest=penalty_compounds_overdue_interest,
    )
    return interest_accrual_common_daily_accrual(
        customer_account=vault.account_id,
        customer_address=customer_address,
        denomination=denomination,
        internal_account=internal_account,
        payable=False,
        effective_balance=overdue_capital,
        effective_datetime=hook_arguments.effective_datetime,
        yearly_rate=annual_interest_rate,
        days_in_year=days_in_year,
        precision=precision,
        rounding=ROUND_HALF_UP,
        account_type=ACCOUNT_TYPE,
        event_type=hook_arguments.event_type,
    )


def _get_due_amount_custom_instructions(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> list[CustomInstruction]:
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    if repayment_holiday_is_due_amount_calculation_blocked(
        vault=vault, effective_datetime=hook_arguments.effective_datetime
    ):
        return [
            CustomInstruction(
                postings=due_amount_calculation_update_due_amount_calculation_counter(
                    account_id=vault.account_id, denomination=denomination
                ),
                instruction_details=utils_standard_instruction_details(
                    description="Updating due amount calculation counter",
                    event_type=hook_arguments.event_type,
                    gl_impacted=False,
                    account_type=ACCOUNT_TYPE,
                ),
                override_all_restrictions=True,
            )
        ]
    balances = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    previous_application_datetime = (
        vault.get_last_execution_datetime(
            event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
        )
        or vault.get_account_creation_datetime()
    )
    if _is_within_interest_only_term(vault=vault):
        reamortisation_condition_features: list[lending_interfaces_ReamortisationCondition] = []
    else:
        reamortisation_condition_features = [
            overpayment_OverpaymentReamortisationCondition,
            repayment_holiday_ReamortisationConditionWithoutPreference,
            fixed_to_variable_ReamortisationCondition,
            lending_interfaces_ReamortisationCondition(
                should_trigger_reamortisation=_is_end_of_interest_only_term
            ),
        ]
    return (
        due_amount_calculation_schedule_logic(
            vault=vault,
            hook_arguments=hook_arguments,
            account_type=ACCOUNT_TYPE,
            interest_application_feature=INTEREST_APPLICATION_FEATURE,
            reamortisation_condition_features=reamortisation_condition_features,
            amortisation_feature=declining_principal_AmortisationFeature,
            interest_rate_feature=fixed_to_variable_InterestRate,
            principal_adjustment_features=[overpayment_OverpaymentPrincipalAdjustment],
            balances=balances,
            denomination=denomination,
        )
        + overpayment_reset_due_amount_calc_overpayment_trackers(vault=vault)
        + overpayment_track_emi_principal_excess(
            vault=vault,
            interest_application_feature=INTEREST_APPLICATION_FEATURE,
            effective_datetime=hook_arguments.effective_datetime,
            previous_application_datetime=previous_application_datetime,
        )
    )


def _charge_late_repayment_fee(vault: Any, event_type: str) -> list[CustomInstruction]:
    """Creates posting instructions to charge a late repayment fee, accounting for capitalisation
    if required.

    :param vault: the vault object for the contract being charged the fee
    :param event_type: the event where the fee is being charged. For use in posting metadata
    :return: the posting instructions to charge the fee.
    """
    postings: list[Posting] = []
    amount = Decimal(utils_get_parameter(vault=vault, name=PARAM_LATE_REPAYMENT_FEE))
    denomination = str(utils_get_parameter(vault=vault, name=PARAM_DENOMINATION))
    late_repayment_fee_income_account: str = utils_get_parameter(
        vault=vault, name=PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT
    )
    customer_account_address = lending_addresses_PENALTIES
    postings += fees_fee_postings(
        customer_account_id=vault.account_id,
        customer_account_address=customer_account_address,
        denomination=denomination,
        amount=amount,
        internal_account=late_repayment_fee_income_account,
    )
    if postings:
        return [
            CustomInstruction(
                postings=postings,
                instruction_details=utils_standard_instruction_details(
                    description="Charge late repayment fee",
                    event_type=event_type,
                    gl_impacted=True,
                    account_type=ACCOUNT_TYPE,
                ),
            )
        ]
    return []


def _use_expected_term(vault: Any, balances: BalanceDefaultDict, denomination: str) -> bool:
    overpayment_preference = overpayment_get_overpayment_preference_parameter(vault=vault)
    overpayment_balance = utils_balance_at_coordinates(
        balances=balances, address=overpayment_OVERPAYMENT, denomination=denomination
    )
    return not (overpayment_preference == "reduce_term" and overpayment_balance > Decimal(0))


def _get_residual_cleanup_postings(
    balances: BalanceDefaultDict, account_id: str, denomination: str
) -> list[Posting]:
    postings: list[Posting] = []
    addresses_to_clear = [CAPITALISED_INTEREST_TRACKER]
    for address in addresses_to_clear:
        address_balance = utils_balance_at_coordinates(
            balances=balances, address=address, denomination=denomination
        )
        if address_balance > Decimal("0"):
            postings += utils_create_postings(
                amount=address_balance,
                debit_account=account_id,
                credit_account=account_id,
                debit_address=lending_addresses_INTERNAL_CONTRA,
                credit_address=address,
                denomination=denomination,
            )
    return postings


def _move_balance_custom_instructions(
    amount: Decimal, denomination: str, vault_account: str, balance_address: str
) -> list[CustomInstruction]:
    postings: list[Posting] = utils_create_postings(
        amount=amount,
        debit_account=vault_account,
        debit_address=balance_address,
        credit_account=vault_account,
        credit_address=DEFAULT_ADDRESS,
        denomination=denomination,
    )
    return [
        CustomInstruction(
            postings=postings,
            instruction_details={
                "description": f"Move {amount} of balance into {balance_address}",
                "event": f"MOVE_BALANCE_INTO_{balance_address}",
            },
            override_all_restrictions=True,
        )
    ]


def _process_payment(
    vault: Any,
    hook_arguments: PostPostingHookArguments,
    denomination: str,
    balances: Optional[BalanceDefaultDict] = None,
) -> tuple[list[CustomInstruction], list[AccountNotificationDirective]]:
    """
    Processes a payment received from the borrower, paying off the balance in different addresses
    in the correct order
    """
    account_notification_directives: list[AccountNotificationDirective] = []
    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    custom_instructions = payments_generate_repayment_postings(
        vault=vault,
        hook_arguments=hook_arguments,
        overpayment_features=[
            overpayment_OverpaymentFeature,
            overpayment_allowance_OverpaymentAllowanceFeature,
        ],
    )
    if close_loan_does_repayment_fully_repay_loan(
        repayment_posting_instructions=custom_instructions,
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        payment_addresses=lending_addresses_ALL_OUTSTANDING,
    ):
        custom_instructions.extend(
            interest_capitalisation_handle_overpayments_to_penalties_pending_capitalisation(
                vault=vault, denomination=denomination, balances=balances
            )
        )
        early_repayment_fee_income_account: str = utils_get_parameter(
            vault=vault, name=PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT
        )
        early_repayment_fee_custom_instructions = _handle_early_repayment_fee(
            repayment_posting_instructions=custom_instructions,
            balances=balances,
            account_id=vault.account_id,
            early_repayment_fee_account=early_repayment_fee_income_account,
            denomination=denomination,
        )
        custom_instructions.extend(early_repayment_fee_custom_instructions)
        account_notification_directives.append(
            AccountNotificationDirective(
                notification_type=CLOSURE_NOTIFICATION,
                notification_details={"account_id": str(vault.account_id)},
            )
        )
    return (custom_instructions, account_notification_directives)


def _handle_early_repayment_fee(
    repayment_posting_instructions: list[CustomInstruction],
    balances: BalanceDefaultDict,
    account_id: str,
    early_repayment_fee_account: str,
    denomination: str,
) -> list[CustomInstruction]:
    """
    When a mortgage is repaid in full early, this function generates
    the posting instructions to move the fee from the mortgage account
    to an early repayment fee account.

    :param repayment_posting_instructions: The repayment posting instructions
    :param balances: The current balances for the account
    :param account_id: The mortgage account id
    :param early_repayment_fee_account: The early repayment fee internal account
    :param denomination: The denomination of the mortgage account
    :return: The posting instructions to move the fee to the early repayment account
    """
    merged_balances = BalanceDefaultDict()
    merged_balances += balances
    for repayment_posting_instruction in repayment_posting_instructions:
        merged_balances += repayment_posting_instruction.balances(
            account_id=account_id, tside=Tside.ASSET
        )
    early_repayment_fees = utils_balance_at_coordinates(
        balances=merged_balances, denomination=denomination
    )
    early_repayment_custom_instructions: list[CustomInstruction] = []
    if early_repayment_fees != Decimal("0"):
        early_repayment_custom_instructions.append(
            CustomInstruction(
                postings=fees_fee_postings(
                    customer_account_id=account_id,
                    customer_account_address=DEFAULT_ADDRESS,
                    denomination=denomination,
                    amount=abs(early_repayment_fees),
                    internal_account=early_repayment_fee_account,
                )
            )
        )
    return early_repayment_custom_instructions


def _get_interest_to_revert(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    return utils_balance_at_coordinates(
        balances=balances, address=lending_addresses_INTEREST_DUE, denomination=denomination
    )


def _get_interest_adjustment_custom_instructions(
    amount: Decimal, denomination: str, vault_account: str, interest_received_account: str
) -> list[CustomInstruction]:
    """
    If a posting is received with {"interest_adjustment": "true"} in the metadata, we waive
    the current interest due and the rebalancing updates the adjusted interest due

    :param amount: amount currently in INTEREST_DUE address
    :param denomination: the denomination of the interest due
    :param vault_account: the vault account id
    :param interest_received_account: internal interest received account id
    :return: custom instructions to waive interest due
    """
    postings = utils_create_postings(
        amount=amount,
        debit_account=interest_received_account,
        credit_account=vault_account,
        debit_address=DEFAULT_ADDRESS,
        credit_address=lending_addresses_INTEREST_DUE,
        denomination=denomination,
    )
    if postings:
        return [
            CustomInstruction(
                postings=postings,
                instruction_details={
                    "description": f"Waive monthly interest due: {amount}",
                    "event": "EARLY_REPAYMENT_INTEREST_ADJUSTMENT",
                },
            )
        ]
    return []


def _handle_due_amount_calculation_day_change(
    vault: Any, hook_arguments: PostParameterChangeHookArguments
) -> list[UpdateAccountEventTypeDirective]:
    update_event_type_directives: list[UpdateAccountEventTypeDirective] = []
    effective_datetime = hook_arguments.effective_datetime
    updated_parameter_values: dict[
        str, utils_ParameterValueTypeAlias
    ] = hook_arguments.updated_parameter_values
    if new_due_amount_calculation_day := updated_parameter_values.get(
        due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY
    ):
        last_execution_datetime = vault.get_last_execution_datetime(
            event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
        )
        next_due_amount_calculation_datetime = _calculate_next_due_amount_calculation_datetime(
            vault, effective_datetime, last_execution_datetime, int(new_due_amount_calculation_day)
        )
        update_event_type_directives.extend(
            _update_due_amount_calculation_day_schedule(
                vault=vault,
                schedule_start_datetime=next_due_amount_calculation_datetime,
                due_amount_calculation_day=int(new_due_amount_calculation_day),
            )
        )
    return update_event_type_directives


def _update_due_amount_calculation_day_schedule(
    vault: Any, schedule_start_datetime: datetime, due_amount_calculation_day: int
) -> list[UpdateAccountEventTypeDirective]:
    return [
        UpdateAccountEventTypeDirective(
            event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT,
            schedule_method=utils_get_end_of_month_schedule_from_parameters(
                vault=vault,
                parameter_prefix=due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX,
                day=due_amount_calculation_day,
            ),
            skip=ScheduleSkip(end=schedule_start_datetime - relativedelta(seconds=1)),
        )
    ]


def _get_actual_next_repayment_dateeter(vault: Any, effective_datetime: datetime) -> datetime:
    last_execution_datetime = vault.get_last_execution_datetime(
        event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
    )
    due_amount_calculation_day = int(
        utils_get_parameter(
            vault,
            name=due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY,
            at_datetime=effective_datetime,
        )
    )
    return _calculate_next_due_amount_calculation_datetime(
        vault,
        effective_datetime,
        last_execution_datetime,
        due_amount_calculation_day=due_amount_calculation_day,
    )


def _get_late_payment_balance(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    return utils_sum_balances(
        balances=balances,
        addresses=lending_addresses_LATE_REPAYMENT_ADDRESSES,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        phase=Phase.COMMITTED,
    )


def _get_outstanding_principal(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    return utils_balance_at_coordinates(
        balances=balances,
        address=lending_addresses_PRINCIPAL,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        phase=Phase.COMMITTED,
    )


def _get_outstanding_payments_amount(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    """
    :param vault: balances, parameters
    :param timestamp: datetime
    :return: Decimal
    """
    return utils_sum_balances(
        balances=balances,
        addresses=lending_addresses_REPAYMENT_HIERARCHY,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        phase=Phase.COMMITTED,
    )


def _get_posting_net_amount(
    posting_instruction: utils_PostingInstructionTypeAlias,
    denomination: str,
    address: str = DEFAULT_ADDRESS,
) -> Decimal:
    posting_balances = posting_instruction.balances()
    return utils_get_available_balance(
        balances=posting_balances, denomination=denomination, address=address
    )


def _get_overdue_capital(
    balances: BalanceDefaultDict, denomination: str, include_overdue_interest: bool
) -> Decimal:
    address_list = (
        lending_addresses_OVERDUE_ADDRESSES
        if include_overdue_interest
        else [lending_addresses_PRINCIPAL_OVERDUE]
    )
    return utils_sum_balances(
        balances=balances, addresses=address_list, denomination=denomination, decimal_places=2
    )


def _get_early_repayment_fee(
    vault: Any, balances: BalanceDefaultDict, denomination: str
) -> Decimal:
    early_repayment_fee: Decimal = utils_get_parameter(vault=vault, name=PARAM_EARLY_REPAYMENT_FEE)
    if early_repayment_fee < 0:
        overpayment_allowance_fee_percentage: Decimal = utils_get_parameter(
            vault=vault, name=overpayment_allowance_PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE
        )
        total_remaining_principal = _get_outstanding_principal(
            balances=balances, denomination=denomination
        )
        early_repayment_fee = utils_round_decimal(
            amount=overpayment_allowance_fee_percentage * total_remaining_principal,
            decimal_places=2,
        )
    return early_repayment_fee


def _is_interest_adjustment(posting: utils_PostingInstructionTypeAlias) -> bool:
    return utils_str_to_bool(
        posting.instruction_details.get(INSTRUCTION_DETAILS_KEY_INTEREST_ADJUSTMENT, "false")
    )


def _is_within_interest_only_term(
    vault: Any, balances: Optional[BalanceDefaultDict] = None, denomination: Optional[str] = None
) -> bool:
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    elapsed_term = term_helpers_calculate_elapsed_term(balances, denomination)
    return int(utils_get_parameter(vault=vault, name=PARAM_INTEREST_ONLY_TERM)) > elapsed_term


def _is_end_of_interest_only_term(
    vault: Any, period_start_datetime: datetime, period_end_datetime: datetime, elapsed_term: int
) -> bool:
    """
    This signature is required for the lending interface
    """
    interest_only_term = int(utils_get_parameter(vault=vault, name=PARAM_INTEREST_ONLY_TERM))
    if interest_only_term == 0:
        return False
    return elapsed_term == interest_only_term


def _calculate_next_due_amount_calculation_datetime(
    vault: Any,
    effective_datetime: datetime,
    last_execution_datetime: Optional[datetime],
    due_amount_calculation_day: int,
) -> datetime:
    (repayment_hour, repayment_minute, repayment_second) = utils_get_schedule_time_from_parameters(
        vault, parameter_prefix=due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX
    )
    account_creation_datetime = vault.get_account_creation_datetime()
    earliest_start_datetime = account_creation_datetime + relativedelta(months=1)
    if last_execution_datetime and last_execution_datetime <= effective_datetime:
        earliest_start_datetime = last_execution_datetime + relativedelta(months=1)
    next_payment_datetime = effective_datetime + relativedelta(
        day=due_amount_calculation_day,
        hour=repayment_hour,
        minute=repayment_minute,
        second=repayment_second,
        microsecond=0,
    )
    if next_payment_datetime <= effective_datetime:
        next_payment_datetime += relativedelta(months=1)
    if effective_datetime < earliest_start_datetime:
        next_payment_datetime = earliest_start_datetime + relativedelta(
            day=due_amount_calculation_day,
            hour=repayment_hour,
            minute=repayment_minute,
            second=repayment_second,
            microsecond=0,
        )
        if next_payment_datetime < earliest_start_datetime:
            next_payment_datetime += relativedelta(months=1)
    return next_payment_datetime


def _should_handle_interest_capitalisation(
    vault: Any, effective_datetime: datetime, is_penalty_interest_capitalisation: bool = False
) -> bool:
    """
    Determine whether to do interest capitalisation
    """
    return (
        not repayment_holiday_is_due_amount_calculation_blocked(
            vault=vault, effective_datetime=effective_datetime
        )
        or is_penalty_interest_capitalisation
    )
