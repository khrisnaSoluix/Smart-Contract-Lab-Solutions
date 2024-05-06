# Code auto-generated using Inception Smart Contract Renderer Version 2.0.1


# Objects below have been imported from:
#    loan.py
# md5:54706bea879a15272ef9d964edc2d429

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
    ScheduledEventHookArguments,
    SupervisorScheduledEventHookArguments,
    BalancesFilter,
    BalancesObservation,
    DateShape,
    SupervisorContractEventType,
    OptionalShape,
    AccountNotificationDirective,
    PostingInstructionsDirective,
    PostPostingHookResult,
    ScheduledEventHookResult,
    UpdatePlanEventTypeDirective,
    PostPostingHookArguments,
    SupervisorPostPostingHookArguments,
    StringShape,
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
from calendar import monthrange, isleap
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import ROUND_HALF_UP, Decimal, ROUND_CEILING
from json import dumps, loads
import math
from typing import Optional, Any, Iterable, Mapping, Union, NamedTuple, Callable
from zoneinfo import ZoneInfo

api = "4.0.0"
version = "5.0.2"
display_name = "KTA Payroll"
summary = f"Tanpa Agunan, Plafond sampai Rp200 Juta, Bunga Mulai 0.8 % Flat/bulan, Pembayaran angsuran bulanan auto debet dari rekening payroll dan Jangka Waktu Kredit sampai dengan 60 Bulan."
tside = Tside.ASSET
supported_denominations = ["IDR"]


@requires(parameters=True)
def activation_hook(
    vault: Any, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    scheduled_events: dict[str, ScheduledEvent] = {}
    effective_datetime = hook_arguments.effective_datetime
    schedule_start_datetime = effective_datetime.replace(
        hour=0, minute=0, second=0
    ) + relativedelta(days=1)
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    skip = flat_interest_is_flat_interest_loan(
        amortisation_method=amortisation_method
    ) or rule_of_78_is_rule_of_78_loan(amortisation_method=amortisation_method)
    scheduled_events.update(
        interest_accrual_scheduled_events(
            vault=vault, start_datetime=schedule_start_datetime, skip=skip
        )
    )
    is_balloon_payment_loan = balloon_payments_is_balloon_loan(
        amortisation_method=amortisation_method
    )
    if not is_balloon_payment_loan:
        scheduled_events.update(
            due_amount_calculation_scheduled_events(
                vault=vault, account_opening_datetime=effective_datetime
            )
        )
        scheduled_events.update(balloon_payments_disabled_balloon_schedule(effective_datetime))
    else:
        balloon_payment_schedules = balloon_payments_scheduled_events(
            vault=vault,
            account_opening_datetime=effective_datetime,
            amortisation_method=amortisation_method,
        )
        scheduled_events.update(balloon_payment_schedules)
    if no_repayment_is_no_repayment_loan(amortisation_method=amortisation_method):
        scheduled_events[overdue_CHECK_OVERDUE_EVENT] = utils_create_end_of_time_schedule(
            start_datetime=schedule_start_datetime
        )
        scheduled_events[CHECK_DELINQUENCY] = utils_create_end_of_time_schedule(
            start_datetime=schedule_start_datetime
        )
    else:
        due_amount_calculation_day = int(
            utils_get_parameter(
                vault=vault, name=due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY
            )
        )
        overdue_schedule_start_datetime = schedule_start_datetime + relativedelta(
            months=1, day=due_amount_calculation_day
        )
        scheduled_events.update(
            overdue_scheduled_events(
                vault=vault,
                first_due_amount_calculation_datetime=overdue_schedule_start_datetime,
                skip=True,
            )
        )
        scheduled_events[CHECK_DELINQUENCY] = ScheduledEvent(
            start_datetime=schedule_start_datetime,
            expression=utils_get_schedule_expression_from_parameters(
                vault=vault, parameter_prefix=CHECK_DELINQUENCY_PREFIX
            ),
            skip=True,
        )
    principal = utils_get_parameter(vault=vault, name=disbursement_PARAM_PRINCIPAL)
    deposit_account = utils_get_parameter(vault=vault, name=disbursement_PARAM_DEPOSIT_ACCOUNT)
    denomination = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    upfront_fee_account = utils_get_parameter(vault=vault, name=PARAM_UPFRONT_FEE_INTERNAL_ACCOUNT)
    upfront_fee = utils_get_parameter(vault=vault, name=PARAM_UPFRONT_FEE)
    amortise_upfront_fee = utils_get_parameter(
        vault=vault, name=PARAM_AMORTISE_UPFRONT_FEE, is_boolean=True
    )
    principal_adjustments: list[lending_interfaces_PrincipalAdjustment] = []
    if upfront_fee > Decimal("0"):
        if amortise_upfront_fee:
            principal_adjustments.append(
                lending_interfaces_PrincipalAdjustment(
                    calculate_principal_adjustment=_calculate_disbursement_principal_adjustment
                )
            )
        else:
            principal = principal - upfront_fee
    principal_custom_instructions = disbursement_get_disbursement_custom_instruction(
        account_id=vault.account_id,
        deposit_account_id=deposit_account,
        principal=principal,
        denomination=denomination,
    )
    if _is_monthly_rest_loan(vault=vault):
        principal_custom_instructions.extend(
            [
                CustomInstruction(
                    postings=utils_create_postings(
                        amount=principal,
                        debit_account=vault.account_id,
                        credit_account=vault.account_id,
                        debit_address=MONTHLY_REST_EFFECTIVE_PRINCIPAL,
                        credit_address=addresses_INTERNAL_CONTRA,
                        denomination=denomination,
                    ),
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Set principal at cycle start on activation",
                        "event": f"{ACCOUNT_TYPE}_SET_PRINCIPAL_AT_CYCLE_START_ON_ACTIVATION",
                    },
                )
            ]
        )
    fee_custom_instructions = _get_activation_fee_custom_instruction(
        account_id=vault.account_id,
        amount=upfront_fee,
        denomination=denomination,
        fee_income_account=upfront_fee_account,
    )
    amortisation_custom_instruction = emi_amortise(
        vault=vault,
        effective_datetime=effective_datetime,
        amortisation_feature=_get_amortisation_feature(vault=vault),
        interest_calculation_feature=_get_interest_rate_feature(vault=vault),
        principal_adjustments=principal_adjustments,
    )
    return ActivationHookResult(
        account_notification_directives=[_get_repayment_schedule_notification(vault=vault)],
        posting_instructions_directives=[
            PostingInstructionsDirective(
                posting_instructions=principal_custom_instructions
                + amortisation_custom_instruction
                + fee_custom_instructions,
                client_batch_id=f"{ACCOUNT_TYPE}_{events_ACCOUNT_ACTIVATION}_{vault.get_hook_execution_id()}",
                value_datetime=effective_datetime,
            )
        ],
        scheduled_events_return_value=scheduled_events,
    )


@requires(parameters=True)
@fetch_account_data(balances=["EFFECTIVE_FETCHER"])
def conversion_hook(
    vault: Any, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    scheduled_events = hook_arguments.existing_schedules
    posting_instructions: list[CustomInstruction] = []
    if utils_get_parameter(vault=vault, name=PARAM_TOP_UP, is_optional=True, is_boolean=True):
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
        denomination = _get_denomination_parameter(vault=vault)
        posting_instructions += close_loan_net_balances(
            balances=balances,
            denomination=denomination,
            account_id=vault.account_id,
            residual_cleanup_features=[
                overpayment_OverpaymentResidualCleanupFeature,
                lending_interfaces_ResidualCleanup(
                    get_residual_cleanup_postings=_get_residual_cleanup_postings
                ),
            ],
        )
        principal_timeseries = vault.get_parameter_timeseries(
            name=disbursement_PARAM_PRINCIPAL
        ).all()
        if len(principal_timeseries) > 1:
            principal_to_disburse = principal_timeseries[-1].value - principal_timeseries[-2].value
            if principal_to_disburse > Decimal("0"):
                deposit_account = disbursement_get_deposit_account_parameter(vault=vault)
                posting_instructions += disbursement_get_disbursement_custom_instruction(
                    account_id=vault.account_id,
                    deposit_account_id=deposit_account,
                    principal=principal_to_disburse,
                    denomination=denomination,
                )
        inflight_balances = BalanceDefaultDict(mapping=balances)
        for posting_instruction in posting_instructions:
            inflight_balances += posting_instruction.balances(
                account_id=vault.account_id, tside=Tside.ASSET
            )
        principal_to_reamortise = utils_balance_at_coordinates(
            balances=inflight_balances,
            address=lending_addresses_PRINCIPAL,
            denomination=denomination,
        )
        posting_instructions += emi_amortise(
            vault=vault,
            effective_datetime=effective_datetime,
            amortisation_feature=_get_amortisation_feature(vault=vault),
            principal_amount=principal_to_reamortise,
            interest_calculation_feature=_get_interest_rate_feature(vault=vault),
            event=LOAN_TOP_UP,
        )
        if _is_monthly_rest_loan(vault=vault):
            posting_instructions += [
                CustomInstruction(
                    postings=utils_create_postings(
                        amount=principal_to_reamortise,
                        debit_account=vault.account_id,
                        credit_account=vault.account_id,
                        debit_address=MONTHLY_REST_EFFECTIVE_PRINCIPAL,
                        credit_address=addresses_INTERNAL_CONTRA,
                        denomination=denomination,
                    ),
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Update principal at repayment cycle start balance",
                        "event": LOAN_TOP_UP,
                    },
                )
            ]
        if balloon_payments_is_balloon_loan(
            amortisation_method=_get_amortisation_method_parameter(vault=vault)
        ):
            scheduled_events.update(
                balloon_payments_update_no_repayment_balloon_schedule(vault=vault)
            )
    return ConversionHookResult(
        scheduled_events_return_value=scheduled_events,
        posting_instructions_directives=[
            PostingInstructionsDirective(
                posting_instructions=posting_instructions, value_datetime=effective_datetime
            )
        ]
        if posting_instructions
        else [],
    )


@fetch_account_data(balances=["live_balances_bof"])
@requires(parameters=True)
def deactivation_hook(
    vault: Any, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    denomination = _get_denomination_parameter(vault=vault)
    if deactivation_rejection := close_loan_reject_closure_when_outstanding_debt(
        balances=balances,
        denomination=denomination,
        debt_addresses=lending_addresses_ALL_OUTSTANDING,
    ):
        return DeactivationHookResult(rejection=deactivation_rejection)
    custom_instructions = close_loan_net_balances(
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        residual_cleanup_features=[
            overpayment_OverpaymentResidualCleanupFeature,
            due_amount_calculation_DueAmountCalculationResidualCleanupFeature,
            lending_interfaces_ResidualCleanup(
                get_residual_cleanup_postings=_get_residual_cleanup_postings
            ),
        ],
    )
    if custom_instructions:
        return DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=custom_instructions,
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
    effective_datetime: datetime = hook_arguments.effective_datetime
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination = _get_denomination_parameter(vault=vault)
    total_outstanding_debt = derived_params_get_total_outstanding_debt(
        balances=balances, denomination=denomination
    )
    total_outstanding_payments = derived_params_get_total_due_amount(
        balances=balances, denomination=denomination
    )
    total_remaining_principal = derived_params_get_total_remaining_principal(
        balances=balances, denomination=denomination
    )
    total_early_repayment_amount = early_repayment_get_total_early_repayment_amount(
        vault=vault, early_repayment_fees=EARLY_REPAYMENT_FEES, balances=balances
    )
    interest_rate_feature = _get_interest_rate_feature(vault=vault)
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    (elapsed_term, remaining_term) = _get_amortisation_feature(vault=vault).term_details(
        vault=vault,
        effective_datetime=effective_datetime,
        use_expected_term=_use_expected_term(
            vault=vault, balances=balances, denomination=denomination
        ),
        interest_rate=interest_rate_feature,
        balances=balances,
        denomination=denomination,
    )
    if balloon_payments_is_balloon_loan(amortisation_method=amortisation_method):
        expected_balloon_payment_amount = balloon_payments_get_expected_balloon_payment_amount(
            vault=vault,
            effective_datetime=effective_datetime,
            balances=balances,
            interest_rate_feature=interest_rate_feature,
        )
    else:
        expected_balloon_payment_amount = Decimal("0")
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    if no_repayment_is_no_repayment_loan(amortisation_method):
        next_repayment_datetime = no_repayment_get_balloon_payment_datetime(vault=vault)
        next_overdue_datetime = overdue_get_next_overdue_derived_parameter(
            vault=vault, previous_due_amount_calculation_datetime=next_repayment_datetime
        )
    else:
        next_repayment_datetime = due_amount_calculation_get_actual_next_repayment_date(
            vault=vault,
            effective_datetime=effective_datetime,
            elapsed_term=elapsed_term,
            remaining_term=remaining_term,
        )
        previous_due_amount_calculation_datetime = vault.get_last_execution_datetime(
            event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
        )
        if previous_due_amount_calculation_datetime is None:
            previous_due_amount_calculation_datetime = (
                due_amount_calculation_get_first_due_amount_calculation_datetime(vault=vault)
            )
        next_overdue_datetime = overdue_get_next_overdue_derived_parameter(
            vault=vault,
            previous_due_amount_calculation_datetime=previous_due_amount_calculation_datetime,
        )
        if balloon_payments_is_balloon_loan(amortisation_method=amortisation_method):
            delta_days = balloon_payments__get_balloon_payment_delta_days(vault)
            if next_repayment_datetime < effective_datetime and remaining_term == 0:
                next_repayment_datetime = next_repayment_datetime + relativedelta(days=delta_days)
            if next_overdue_datetime < effective_datetime and remaining_term == 0:
                next_overdue_datetime = next_overdue_datetime + relativedelta(days=delta_days)
    derived_parameters: dict[str, utils_ParameterValueTypeAlias] = {
        derived_params_PARAM_REMAINING_TERM: remaining_term,
        derived_params_PARAM_TOTAL_OUTSTANDING_DEBT: total_outstanding_debt,
        derived_params_PARAM_TOTAL_OUTSTANDING_PAYMENTS: total_outstanding_payments,
        derived_params_PARAM_TOTAL_REMAINING_PRINCIPAL: total_remaining_principal,
        early_repayment_PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT: total_early_repayment_amount,
        balloon_payments_PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT: expected_balloon_payment_amount,
        due_amount_calculation_PARAM_NEXT_REPAYMENT_DATE: next_repayment_datetime,
        emi_PARAM_EQUATED_INSTALMENT_AMOUNT: emi_get_expected_emi(
            balances=balances, denomination=denomination
        ),
        overdue_PARAM_NEXT_OVERDUE_DATE: next_overdue_datetime,
    }
    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


@requires(parameters=True, last_execution_datetime=["DUE_AMOUNT_CALCULATION"])
@fetch_account_data(balances=["EFFECTIVE_FETCHER"])
def post_parameter_change_hook(
    vault: Any, hook_arguments: PostParameterChangeHookArguments
) -> Optional[PostParameterChangeHookResult]:
    update_event_type_directives: list[UpdateAccountEventTypeDirective] = []
    effective_datetime = hook_arguments.effective_datetime
    updated_parameter_values: dict[
        str, utils_ParameterValueTypeAlias
    ] = hook_arguments.updated_parameter_values
    if updated_parameter_values.get(due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY):
        (elapsed_term, remaining_term) = _get_amortisation_feature(vault=vault).term_details(
            vault=vault, effective_datetime=effective_datetime, use_expected_term=True
        )
        update_event_type_directives.extend(
            _handle_due_amount_calculation_day_change(
                vault=vault,
                effective_datetime=effective_datetime,
                elapsed_term=elapsed_term,
                remaining_term=remaining_term,
            )
        )
    if update_event_type_directives:
        return PostParameterChangeHookResult(
            update_account_event_type_directives=update_event_type_directives
        )
    return None


@requires(parameters=True)
@fetch_account_data(balances=["live_balances_bof"])
def post_posting_hook(
    vault: Any, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    posting_instructions: utils_PostingInstructionListAlias = hook_arguments.posting_instructions
    if utils_is_force_override(posting_instructions=posting_instructions):
        return None
    effective_datetime = hook_arguments.effective_datetime
    posting = posting_instructions[0]
    denomination = _get_denomination_parameter(vault=vault)
    posting_balance: Decimal = utils_balance_at_coordinates(
        balances=posting.balances(), denomination=denomination
    )
    account_notification_directives: list[AccountNotificationDirective] = []
    custom_instructions: list[CustomInstruction] = []
    inflight_postings: list[Posting] = []
    if lending_utils_is_debit(amount=posting_balance):
        is_interest_adjustment = _is_interest_adjustment(posting=posting)
        balance_destination = (
            lending_addresses_INTEREST_DUE
            if is_interest_adjustment
            else lending_addresses_PENALTIES
        )
        inflight_postings.extend(
            utils_create_postings(
                amount=posting_balance,
                debit_account=vault.account_id,
                debit_address=balance_destination,
                credit_account=vault.account_id,
                credit_address=DEFAULT_ADDRESS,
                denomination=denomination,
            )
        )
        if is_interest_adjustment:
            balances: BalanceDefaultDict = vault.get_balances_observation(
                fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
            ).balances
            interest_to_revert = _get_interest_to_revert(
                balances=balances, denomination=denomination
            )
            interest_received_account: str = utils_get_parameter(
                vault, name=interest_application_PARAM_INTEREST_RECEIVED_ACCOUNT
            )
            inflight_postings.extend(
                utils_create_postings(
                    amount=interest_to_revert,
                    debit_account=interest_received_account,
                    debit_address=DEFAULT_ADDRESS,
                    credit_account=vault.account_id,
                    credit_address=balance_destination,
                    denomination=denomination,
                )
            )
        custom_instructions.append(
            CustomInstruction(
                postings=inflight_postings,
                instruction_details={
                    "description": f"Adjustment to {balance_destination.lower()}",
                    "event": f"ADJUSTMENT_TO_{balance_destination}",
                },
                override_all_restrictions=True,
            )
        )
    elif lending_utils_is_credit(amount=posting_balance):
        (
            repayment_custom_instructions,
            repayment_account_notification_directives,
        ) = _process_payment(vault=vault, hook_arguments=hook_arguments, denomination=denomination)
        custom_instructions.extend(repayment_custom_instructions)
        account_notification_directives.extend(repayment_account_notification_directives)
    if custom_instructions or account_notification_directives:
        return PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=custom_instructions, value_datetime=effective_datetime
                )
            ]
            if custom_instructions
            else [],
            account_notification_directives=account_notification_directives,
        )
    return None


@requires(flags=True, last_execution_datetime=["DUE_AMOUNT_CALCULATION"], parameters=True)
def pre_parameter_change_hook(
    vault: Any, hook_arguments: PreParameterChangeHookArguments
) -> Optional[PreParameterChangeHookResult]:
    updated_parameter_values: dict[
        str, utils_ParameterValueTypeAlias
    ] = hook_arguments.updated_parameter_values
    if due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY in updated_parameter_values:
        amortisation_method: str = utils_get_parameter(
            vault=vault, name=PARAM_AMORTISATION_METHOD, is_union=True
        )
        if amortisation_method.upper() == "NO_REPAYMENT":
            return PreParameterChangeHookResult(
                rejection=Rejection(
                    message="It is not possible to change the due amount calculation day for a No Repayment (Balloon Payment) loan.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
        if rejection := due_amount_calculation_validate_due_amount_calculation_day_change(
            vault=vault
        ):
            return PreParameterChangeHookResult(rejection=rejection)
        if repayment_holiday_is_due_amount_calculation_blocked(
            vault=vault, effective_datetime=hook_arguments.effective_datetime
        ):
            return PreParameterChangeHookResult(
                rejection=Rejection(
                    message="It is not possible to change the due amount calculation day if there are active due amount blocking flags.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
    return None


@requires(parameters=True, flags=True)
@fetch_account_data(balances=["live_balances_bof"])
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
    denomination = _get_denomination_parameter(vault=vault)
    if denomination_rejection := utils_validate_denomination(
        posting_instructions=posting_instructions, accepted_denominations=[denomination]
    ):
        return PrePostingHookResult(rejection=denomination_rejection)
    posting_instruction = posting_instructions[0]
    posting_amount = _get_posting_amount(
        posting_instruction=posting_instruction, denomination=denomination
    )
    if posting_amount < Decimal("0"):
        if repayment_holiday_is_repayment_blocked(
            vault=vault, effective_datetime=hook_arguments.effective_datetime
        ):
            return PrePostingHookResult(
                rejection=Rejection(
                    message="Repayments are blocked for this account.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
        if early_repayment_is_posting_an_early_repayment(
            vault=vault,
            repayment_amount=posting_amount,
            early_repayment_fees=EARLY_REPAYMENT_FEES,
            denomination=denomination,
        ):
            return None
        if overpayment_is_posting_an_overpayment(
            vault=vault, repayment_amount=posting_amount, denomination=denomination
        ):
            amortisation_method = _get_amortisation_method_parameter(vault=vault)
            if (
                flat_interest_is_flat_interest_loan(amortisation_method)
                or rule_of_78_is_rule_of_78_loan(amortisation_method=amortisation_method)
                or minimum_repayment_is_minimum_repayment_loan(
                    amortisation_method=amortisation_method
                )
            ):
                return PrePostingHookResult(
                    rejection=Rejection(
                        message=f"Overpayments are not allowed for {amortisation_method.replace('_', ' ')} loans.",
                        reason_code=RejectionReason.AGAINST_TNC,
                    )
                )
            if overpayment_get_max_overpayment_amount(
                vault=vault, denomination=denomination
            ) == abs(posting_amount):
                total_early_repayment_amount = early_repayment_get_total_early_repayment_amount(
                    vault=vault,
                    early_repayment_fees=EARLY_REPAYMENT_FEES,
                    denomination=denomination,
                )
                return PrePostingHookResult(
                    rejection=Rejection(
                        message=f"Cannot repay remaining debt without paying early repayment fees, amount required is {total_early_repayment_amount}",
                        reason_code=RejectionReason.AGAINST_TNC,
                    )
                )
            if overpayment_rejection := overpayment_validate_overpayment(
                vault=vault, repayment_amount=posting_amount, denomination=denomination
            ):
                return PrePostingHookResult(rejection=overpayment_rejection)
    elif posting_amount > Decimal("0") and (
        not utils_str_to_bool(
            posting_instruction.instruction_details.get(INSTRUCTION_DETAILS_KEY_FEE, "false")
        )
        and (
            not utils_str_to_bool(
                posting_instruction.instruction_details.get(
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


@requires(
    event_type="ACCRUE_INTEREST",
    flags=True,
    last_execution_datetime=["DUE_AMOUNT_CALCULATION"],
    parameters=True,
)
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
@requires(
    event_type="BALLOON_PAYMENT_EVENT",
    flags=True,
    last_execution_datetime=["DUE_AMOUNT_CALCULATION"],
    parameters=True,
)
@fetch_account_data(
    event_type="BALLOON_PAYMENT_EVENT",
    balances=[
        "EFFECTIVE_FETCHER",
        "ACCRUED_INTEREST_EFFECTIVE_DATETIME_FETCHER",
        "ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER",
        "OVERPAYMENT_TRACKER_EFF_FETCHER",
    ],
)
@requires(event_type="CHECK_OVERDUE", flags=True, parameters=True)
@fetch_account_data(event_type="CHECK_OVERDUE", balances=["EFFECTIVE_FETCHER"])
@requires(event_type="CHECK_DELINQUENCY", flags=True, parameters=True)
@fetch_account_data(event_type="CHECK_DELINQUENCY", balances=["EFFECTIVE_FETCHER"])
def scheduled_event_hook(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    event_type = hook_arguments.event_type
    effective_datetime: datetime = hook_arguments.effective_datetime
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    custom_instructions: list[CustomInstruction] = []
    update_event_type_directives: list[UpdateAccountEventTypeDirective] = []
    account_notification_directives: list[AccountNotificationDirective] = []
    is_flat_interest_loan = flat_interest_is_flat_interest_loan(
        amortisation_method=amortisation_method
    )
    is_rule_of_78_loan = rule_of_78_is_rule_of_78_loan(amortisation_method=amortisation_method)
    if event_type == interest_accrual_ACCRUAL_EVENT:
        if penalty_accrual_postings := _get_penalty_interest_accrual_custom_instruction(
            vault=vault, hook_arguments=hook_arguments
        ):
            custom_instructions.extend(penalty_accrual_postings)
        elif is_flat_interest_loan or is_rule_of_78_loan:
            update_event_type_directives.extend(
                interest_accrual_common_update_schedule_events_skip(skip=True)
            )
        if not (is_flat_interest_loan or is_rule_of_78_loan):
            capitalised_interest_postings = _handle_interest_capitalisation(
                vault=vault, effective_datetime=effective_datetime, account_type=ACCOUNT_TYPE
            )
            custom_instructions.extend(capitalised_interest_postings)
            custom_instructions.extend(
                _get_standard_interest_accrual_custom_instructions(
                    vault=vault,
                    hook_arguments=hook_arguments,
                    inflight_postings=capitalised_interest_postings,
                )
            )
    elif event_type == due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT:
        if repayment_holiday_is_due_amount_calculation_blocked(
            vault=vault, effective_datetime=hook_arguments.effective_datetime
        ):
            if _should_repayment_holiday_increase_tracker_balance(
                vault=vault,
                effective_datetime=effective_datetime,
                amortisation_method=amortisation_method,
            ):
                denomination = _get_denomination_parameter(vault=vault)
                custom_instructions += [
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
        elif due_amount_custom_instructions := _get_due_amount_custom_instructions(
            vault=vault, hook_arguments=hook_arguments
        ):
            custom_instructions.extend(due_amount_custom_instructions)
            account_notification_directives.extend(
                _get_repayment_due_notification(
                    vault=vault,
                    due_amount_custom_instructions=due_amount_custom_instructions,
                    effective_datetime=effective_datetime,
                )
            )
            repayment_period = int(
                utils_get_parameter(vault=vault, name=overdue_PARAM_REPAYMENT_PERIOD)
            )
            update_event_type_directives.extend(
                _update_check_overdue_schedule(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    repayment_period=repayment_period,
                )
            )
        custom_instructions.extend(
            interest_capitalisation_handle_penalty_interest_capitalisation(
                vault=vault, account_type=ACCOUNT_TYPE
            )
        )
        if _should_enable_balloon_payment_schedule(
            vault=vault,
            effective_datetime=effective_datetime,
            amortisation_method=amortisation_method,
        ):
            update_event_type_directives.extend(
                balloon_payments_update_balloon_payment_schedule(
                    vault=vault, execution_timestamp=effective_datetime
                )
            )
        due_amount_calculation_day = int(
            utils_get_parameter(
                vault=vault, name=due_amount_calculation_PARAM_DUE_AMOUNT_CALCULATION_DAY
            )
        )
        if due_amount_calculation_day != effective_datetime.day:
            schedule_start_datetime = effective_datetime + relativedelta(
                months=1, day=due_amount_calculation_day
            )
            update_event_type_directives.extend(
                _update_due_amount_calculation_day_schedule(
                    vault, schedule_start_datetime, due_amount_calculation_day
                )
            )
    elif event_type == overdue_CHECK_OVERDUE_EVENT:
        if not repayment_holiday_is_overdue_amount_calculation_blocked(
            vault=vault, effective_datetime=effective_datetime
        ):
            (overdue_custom_instructions, _) = overdue_schedule_logic(
                vault=vault, hook_arguments=hook_arguments
            )
            update_event_type_directives.extend(
                _update_check_overdue_schedule(
                    vault=vault, effective_datetime=effective_datetime, skip=True
                )
            )
            if overdue_custom_instructions:
                custom_instructions.extend(overdue_custom_instructions)
                late_repayment_fee = Decimal(
                    utils_get_parameter(vault=vault, name=PARAM_LATE_REPAYMENT_FEE)
                )
                denomination = _get_denomination_parameter(vault=vault)
                custom_instructions.extend(
                    _charge_late_repayment_fee(
                        vault=vault,
                        event_type=event_type,
                        amount=late_repayment_fee,
                        denomination=denomination,
                    )
                )
                posting_balances: BalanceDefaultDict = BalanceDefaultDict()
                for custom_instruction in overdue_custom_instructions:
                    posting_balances += custom_instruction.balances(
                        account_id=vault.account_id, tside=Tside.ASSET
                    )
                account_notification_directives.extend(
                    _get_overdue_repayment_notification(
                        account_id=vault.account_id,
                        balances=posting_balances,
                        denomination=denomination,
                        late_repayment_fee=late_repayment_fee,
                        effective_datetime=effective_datetime,
                    )
                )
                (mark_delinquent_notification, delinquency_schedule_update) = _handle_delinquency(
                    vault=vault,
                    hook_arguments=hook_arguments,
                    is_delinquency_schedule_event=False,
                    balances=posting_balances,
                )
                account_notification_directives.extend(mark_delinquent_notification)
                update_event_type_directives.extend(delinquency_schedule_update)
                if is_flat_interest_loan or is_rule_of_78_loan:
                    update_event_type_directives.extend(
                        interest_accrual_common_update_schedule_events_skip(skip=False)
                    )
    elif event_type == CHECK_DELINQUENCY:
        (mark_delinquent_notifications, delinquency_event_updates) = _handle_delinquency(
            vault=vault, hook_arguments=hook_arguments, is_delinquency_schedule_event=True
        )
        account_notification_directives.extend(mark_delinquent_notifications)
        update_event_type_directives.extend(delinquency_event_updates)
    elif event_type == balloon_payments_BALLOON_PAYMENT_EVENT:
        if balloon_payment_custom_instructions := _get_balloon_payment_custom_instructions(
            vault=vault, hook_arguments=hook_arguments
        ):
            custom_instructions.extend(balloon_payment_custom_instructions)
            account_notification_directives.extend(
                _get_repayment_due_notification(
                    vault=vault,
                    due_amount_custom_instructions=balloon_payment_custom_instructions,
                    effective_datetime=effective_datetime,
                )
            )
            repayment_period = overdue_get_repayment_period_parameter(vault=vault)
            update_event_type_directives.extend(
                _update_check_overdue_schedule(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    repayment_period=repayment_period,
                )
            )
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
    else:
        return None


# Objects below have been imported from:
#    addresses.py
# md5:860f50af37f2fe98540f540fa6394eb7

addresses_DEFAULT = "DEFAULT"
addresses_INTERNAL_CONTRA = "INTERNAL_CONTRA"
addresses_PENALTIES = "PENALTIES"

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

common_parameters_BooleanShape = UnionShape(
    items=[UnionItem(key="True", display_name="True"), UnionItem(key="False", display_name="False")]
)
common_parameters_BooleanValueTrue = UnionItemValue(key="True")
common_parameters_BooleanValueFalse = UnionItemValue(key="False")

# Objects below have been imported from:
#    events.py
# md5:ee964ddec320f22b8eeab458a02a6835

events_ACCOUNT_ACTIVATION = "ACCOUNT_ACTIVATION"

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


def interest_accrual_common_update_schedule_events_skip(
    skip: Union[bool, ScheduleSkip]
) -> list[UpdateAccountEventTypeDirective]:
    return [
        UpdateAccountEventTypeDirective(event_type=interest_accrual_common_ACCRUAL_EVENT, skip=skip)
    ]


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


def term_helpers_calculate_term_details_from_counter(
    vault: Any,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> tuple[int, int]:
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
    elapsed = term_helpers_calculate_elapsed_term(balances=balances, denomination=denomination)
    expected_remaining_term = original_total_term - elapsed
    return (elapsed, expected_remaining_term)


# Objects below have been imported from:
#    declining_principal.py
# md5:9a0b5e3b9bdf8a8ca9b57a0a01a29e54


def declining_principal_is_declining_principal_loan(amortisation_method: str) -> bool:
    return amortisation_method.upper() == "DECLINING_PRINCIPAL"


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
#    flat_interest.py
# md5:be86a2b74d05ce585809a69a2828acfa

flat_interest_PARAM_DENOMINATION = "denomination"
flat_interest_PARAM_FIXED_INTEREST_RATE = "fixed_interest_rate"
flat_interest_PARAM_PRINCIPAL = "principal"


def flat_interest_is_flat_interest_loan(amortisation_method: str) -> bool:
    return amortisation_method.upper() == "FLAT_INTEREST"


def flat_interest_term_details(
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
    :param use_expected_term:  Not used but required for the interface
    :param interest_rate:  Not used but required for the interface
    :param principal_adjustments:  Not used but required for the interface
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
    return (elapsed, expected_remaining_term)


def flat_interest_calculate_emi(
    vault: Any,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> Decimal:
    """
    :param vault: Vault object
    :param effective_datetime: the datetime as of which the calculation is performed
    :param use_expected_term: Not used but required for the interface
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the principal set on parameter level is used.
    :param interest_calculation_feature: interest calculation feature, if no value is
        provided, 0 is used.
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param balances: balances to use instead of the effective datetime balances
    :return: emi amount
    """
    fixed_interest_rate = (
        Decimal(0)
        if not interest_calculation_feature
        else interest_calculation_feature.get_annual_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )
    )
    total_term = lending_parameters_get_total_repayment_count_parameter(vault=vault)
    principal = (
        utils_get_parameter(vault=vault, name="principal")
        if principal_amount is None
        else principal_amount
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
    total_loan_interest = flat_interest_calculate_non_accruing_loan_total_interest(
        original_principal=principal,
        annual_interest_rate=fixed_interest_rate,
        total_term=total_term,
    )
    return utils_round_decimal((principal + total_loan_interest) / total_term, 2)


def flat_interest_apply_interest(
    vault: Any,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances_at_application: Optional[BalanceDefaultDict] = None,
) -> list[Posting]:
    """
    Creates the postings needed to apply interest for a flat interest amortised loan
    :param vault: vault object
    """
    application_internal_account: str = utils_get_parameter(
        vault=vault, name=interest_application_PARAM_INTEREST_RECEIVED_ACCOUNT
    )
    application_interest_address: str = interest_application_INTEREST_DUE
    denomination: str = utils_get_parameter(vault=vault, name=flat_interest_PARAM_DENOMINATION)
    precision = interest_application_get_application_precision(vault=vault)
    effective_balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    interest_application_amounts = flat_interest_get_interest_to_apply(
        vault=vault,
        balances_at_application=effective_balances,
        denomination=denomination,
        application_precision=precision,
        effective_datetime=effective_datetime,
        previous_application_datetime=previous_application_datetime,
    )
    return fees_fee_postings(
        customer_account_id=vault.account_id,
        customer_account_address=application_interest_address,
        denomination=denomination,
        amount=interest_application_amounts.total_rounded,
        internal_account=application_internal_account,
    )


def flat_interest_get_interest_to_apply(
    vault: Any,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances_at_application: Optional[BalanceDefaultDict] = None,
    balances_one_repayment_period_ago: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    application_precision: Optional[int] = None,
) -> lending_interfaces_InterestAmounts:
    """
    Determines the interest amount for application using flat interest amortisation.
    For flat and rule of 78 interest we don't have concept of emi vs non emi interest as the
    accrued amount is calculated for the month at the end of the month, instead of daily accruals.
    Hence, we do not use some of the args passed in for this implementation of the interface.

    :param vault: vault object for the account with interest to apply
    :param effective_datetime: not used but required by the interface signature
    :param previous_application_datetime: not used but required by the interface signature
    :param balances_at_application: balances to extract current accrued amounts from. Only pass in
    to override the feature's default fetching
    :param balances_one_repayment_period_ago: not used but required by the interface signature.
    :param denomination: accrual denomination. Only pass in to override the feature's default
    fetching
    :param precision: number of places that interest is rounded to during application.
     Only pass in to override the feature's default fetching
    :return: the interest amounts
    """
    if balances_at_application is None:
        balances_at_application = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if application_precision is None:
        application_precision = interest_application_get_application_precision(vault=vault)
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name=flat_interest_PARAM_DENOMINATION)
    principal: Decimal = utils_get_parameter(vault=vault, name=flat_interest_PARAM_PRINCIPAL)
    total_term = lending_parameters_get_total_repayment_count_parameter(vault=vault)
    fixed_interest_rate: Decimal = utils_get_parameter(
        vault=vault, name=flat_interest_PARAM_FIXED_INTEREST_RATE
    )
    total_interest = flat_interest_calculate_non_accruing_loan_total_interest(
        original_principal=principal,
        annual_interest_rate=fixed_interest_rate,
        total_term=total_term,
        precision=application_precision,
    )
    elapsed = term_helpers_calculate_elapsed_term(
        balances=balances_at_application, denomination=denomination
    )
    term_remaining = total_term - elapsed
    interest_due = flat_interest__calculate_interest_due(
        total_interest=total_interest,
        total_term=total_term,
        remaining_term=term_remaining,
        precision=application_precision,
    )
    return lending_interfaces_InterestAmounts(
        emi_accrued=Decimal("0"),
        emi_rounded_accrued=interest_due,
        non_emi_accrued=Decimal("0"),
        non_emi_rounded_accrued=Decimal("0"),
        total_rounded=interest_due,
    )


def flat_interest__calculate_interest_due(
    total_interest: Decimal, total_term: int, remaining_term: int, precision: int
) -> Decimal:
    monthly_interest_due = utils_round_decimal(
        amount=total_interest / total_term, decimal_places=precision
    )
    if remaining_term == 1:
        return total_interest - monthly_interest_due * (total_term - remaining_term)
    else:
        return monthly_interest_due


def flat_interest_calculate_non_accruing_loan_total_interest(
    original_principal: Decimal, annual_interest_rate: Decimal, total_term: int, precision: int = 2
) -> Decimal:
    """
    Returns the total loan interest for a flat interest
    :param original_principal: principal of the loan at loan start
    :param annual_interest_rate: yearly interest rate of the loan
    :param total_term: total term of the loan
    :param precision: number of places that interest is rounded to before application.
    """
    return utils_round_decimal(
        amount=original_principal
        * utils_yearly_to_monthly_rate(yearly_rate=annual_interest_rate)
        * Decimal(total_term),
        decimal_places=precision,
    )


flat_interest_InterestApplication = lending_interfaces_InterestApplication(
    apply_interest=flat_interest_apply_interest,
    get_interest_to_apply=flat_interest_get_interest_to_apply,
    get_application_precision=interest_application_get_application_precision,
)
flat_interest_AmortisationFeature = lending_interfaces_Amortisation(
    calculate_emi=flat_interest_calculate_emi,
    term_details=flat_interest_term_details,
    override_final_event=False,
)

# Objects below have been imported from:
#    interest_only.py
# md5:2354169a330ecc1120d170fb4d11da60

interest_only_AMORTISATION_METHOD = "INTEREST_ONLY"


def interest_only_is_interest_only_loan(amortisation_method: str) -> bool:
    return amortisation_method.upper() == interest_only_AMORTISATION_METHOD


def interest_only_term_details(
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
    :param use_expected_term: Not used but required for the interface
    :param interest_rate: Not used but required for the interface
    :param principal_adjustments: Not used but required for the interface
    :param balances: balances to use instead of the effective datetime balances
    :param denomination: denomination to use instead of the effective datetime parameter value
    :return: the elapsed and remaining term
    """
    return term_helpers_calculate_term_details_from_counter(
        vault=vault,
        effective_datetime=effective_datetime,
        balances=balances,
        denomination=denomination,
    )


def interest_only_calculate_emi(
    vault: Any,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> Decimal:
    """
    This signature is required to meet the interface definition only
    :param vault: Vault object
    :param effective_datetime: the datetime as of which the calculation is performed
    :param use_expected_term: Not used but required for the interface
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the principal set on parameter level is used.
    :param interest_calculation_feature: interest calculation feature, if no value is
        provided, 0 is used.
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param balances: balances to use instead of the effective datetime balances
    :return: emi amount
    """
    return Decimal("0")


interest_only_AmortisationFeature = lending_interfaces_Amortisation(
    calculate_emi=interest_only_calculate_emi,
    term_details=interest_only_term_details,
    override_final_event=True,
)

# Objects below have been imported from:
#    minimum_repayment.py
# md5:8b922702896f8ae10e8b5f47dbedecaf

minimum_repayment_AMORTISATION_METHOD = "MINIMUM_REPAYMENT_WITH_BALLOON_PAYMENT"


def minimum_repayment_is_minimum_repayment_loan(amortisation_method: str) -> bool:
    return amortisation_method.upper() == minimum_repayment_AMORTISATION_METHOD


def minimum_repayment_calculate_emi(
    vault: Any,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> Decimal:
    """
    Extracts relevant data required and calculates minimum repayment EMI.
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
    static_emi = utils_get_parameter(vault=vault, name="balloon_emi_amount", is_optional=True)
    if static_emi:
        return static_emi
    balloon_payment_amount = utils_get_parameter(
        vault=vault, name="balloon_payment_amount", is_optional=True, default_value=Decimal("0")
    )
    interest_rate = (
        Decimal(0)
        if not interest_calculation_feature
        else interest_calculation_feature.get_monthly_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )
    )
    principal = (
        utils_get_parameter(vault=vault, name="principal")
        if principal_amount is None
        else principal_amount
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
    (_, remaining_term) = minimum_repayment_term_details(
        vault=vault,
        use_expected_term=use_expected_term,
        effective_datetime=effective_datetime,
        interest_rate=interest_calculation_feature,
        principal_adjustments=principal_adjustments,
        balances=balances,
    )
    return declining_principal_apply_declining_principal_formula(
        remaining_principal=principal,
        interest_rate=interest_rate,
        remaining_term=remaining_term,
        lump_sum_amount=balloon_payment_amount,
    )


def minimum_repayment_term_details(
    vault: Any,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    interest_rate: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> tuple[int, int]:
    """Calculate the elapsed and remaining term for a loan
    Using a counter based approach to simplify the logic required
    when addressing static or derived EMI Repayment.

    :param vault: the vault object for the loan account
    :param effective_datetime: datetime as of which the calculations are performed
    :param use_expected_term: Not used but required for the interface
    :param interest_rate: Not used but required for the interface
    :param principal_adjustments: Not used but required for the interface
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
    elapsed = term_helpers_calculate_elapsed_term(balances=balances, denomination=denomination)
    expected_remaining_term = original_total_term - elapsed
    return (elapsed, expected_remaining_term)


minimum_repayment_AmortisationFeature = lending_interfaces_Amortisation(
    calculate_emi=minimum_repayment_calculate_emi,
    term_details=minimum_repayment_term_details,
    override_final_event=True,
)

# Objects below have been imported from:
#    no_repayment.py
# md5:715110c0eb42eb5834a9b617c5776b4e

no_repayment_AMORTISATION_METHOD = "NO_REPAYMENT"


def no_repayment_is_no_repayment_loan(amortisation_method: str) -> bool:
    return amortisation_method.upper() == no_repayment_AMORTISATION_METHOD


def no_repayment_calculate_emi(
    vault: Any,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> Decimal:
    """
    No Repayment amortisation will always return 0 EMI

    """
    return Decimal(0)


def no_repayment_term_details(
    vault: Any,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    interest_rate: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> tuple[int, int]:
    """Calculate the elapsed and remaining term for a loan. Given that this is a no repayment loan,
    the term is based on the difference in current datetime to the account opening time.

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
    loan_start_date = vault.get_account_creation_datetime()
    effective_datetime = max(loan_start_date, effective_datetime)
    delta = relativedelta(effective_datetime, loan_start_date)
    delta_months = delta.years * 12 + delta.months
    remaining_months = original_total_term - delta_months
    if remaining_months < 0:
        return (original_total_term, 0)
    return (delta_months, remaining_months)


def no_repayment_get_balloon_payment_datetime(vault: Any) -> datetime:
    balloon_payment_start_date = vault.get_account_creation_datetime()
    original_total_term = int(
        utils_get_parameter(vault=vault, name=lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT)
    )
    balloon_payment_delta_days = int(
        utils_get_parameter(
            vault=vault, name="balloon_payment_days_delta", is_optional=True, default_value=0
        )
    )
    return balloon_payment_start_date + relativedelta(
        days=balloon_payment_delta_days, months=original_total_term
    )


no_repayment_AmortisationFeature = lending_interfaces_Amortisation(
    calculate_emi=no_repayment_calculate_emi,
    term_details=no_repayment_term_details,
    override_final_event=True,
)

# Objects below have been imported from:
#    rule_of_78.py
# md5:a835da482d310b4f7127a7de16ba1f16

rule_of_78_PARAM_DENOMINATION = "denomination"
rule_of_78_PARAM_FIXED_INTEREST_RATE = "fixed_interest_rate"
rule_of_78_PARAM_PRINCIPAL = "principal"


def rule_of_78_is_rule_of_78_loan(amortisation_method: str) -> bool:
    return amortisation_method.upper() == "RULE_OF_78"


def rule_of_78_term_details(
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
    :param use_expected_term: Not used but required for the interface
    :param interest_rate: Not used but required for the interface
    :param principal_adjustments: Not used but required for the interface
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
    return (elapsed, expected_remaining_term)


def rule_of_78_calculate_emi(
    vault: Any,
    effective_datetime: datetime,
    use_expected_term: bool = True,
    principal_amount: Optional[Decimal] = None,
    interest_calculation_feature: Optional[lending_interfaces_InterestRate] = None,
    principal_adjustments: Optional[list[lending_interfaces_PrincipalAdjustment]] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> Decimal:
    """
    :param vault: Vault object
    :param effective_datetime: the datetime as of which the calculation is performed
    :param use_expected_term: Not used but required for the interface
    :param principal_amount: the principal amount used for amortisation
        If no value provided, the principal set on parameter level is used.
    :param interest_calculation_feature: interest calculation feature, if no value is
        provided, 0 is used.
    :param principal_adjustments: features used to adjust the principal that is amortised
        If no value provided, no adjustment is made to the principal.
    :param balances: balances to use instead of the effective datetime balances
    :return: emi amount
    """
    fixed_interest_rate = (
        Decimal(0)
        if not interest_calculation_feature
        else interest_calculation_feature.get_annual_interest_rate(
            vault=vault, effective_datetime=effective_datetime
        )
    )
    total_term = int(
        utils_get_parameter(vault=vault, name=lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT)
    )
    principal = (
        utils_get_parameter(vault=vault, name="principal")
        if principal_amount is None
        else principal_amount
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
    application_precision = utils_get_parameter(
        vault=vault, name=interest_application_PARAM_APPLICATION_PRECISION
    )
    total_loan_interest = rule_of_78_calculate_non_accruing_loan_total_interest(
        original_principal=principal,
        annual_interest_rate=fixed_interest_rate,
        total_term=total_term,
        precision=application_precision,
    )
    return utils_round_decimal(
        (principal + total_loan_interest) / total_term, application_precision
    )


def rule_of_78_apply_interest(
    *,
    vault: Any,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances_at_application: Optional[BalanceDefaultDict] = None,
) -> list[Posting]:
    """
    Creates the postings needed to apply interest for a loan using rule of 78 loan amortisation
    :param vault: vault object
    """
    application_internal_account: str = utils_get_parameter(
        vault, interest_application_PARAM_INTEREST_RECEIVED_ACCOUNT
    )
    application_interest_address: str = interest_application_INTEREST_DUE
    denomination: str = utils_get_parameter(vault, rule_of_78_PARAM_DENOMINATION)
    application_precision = interest_application_get_application_precision(vault=vault)
    effective_balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    interest_application_amounts = rule_of_78_get_interest_to_apply(
        vault=vault,
        effective_datetime=effective_datetime,
        previous_application_datetime=previous_application_datetime,
        balances_at_application=effective_balances,
        denomination=denomination,
        application_precision=application_precision,
    )
    return fees_fee_postings(
        customer_account_id=vault.account_id,
        customer_account_address=application_interest_address,
        denomination=denomination,
        amount=interest_application_amounts.emi_rounded_accrued,
        internal_account=application_internal_account,
    )


def rule_of_78_get_interest_to_apply(
    vault: Any,
    effective_datetime: datetime,
    previous_application_datetime: datetime,
    balances_at_application: Optional[BalanceDefaultDict] = None,
    balances_one_repayment_period_ago: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    application_precision: Optional[int] = None,
) -> lending_interfaces_InterestAmounts:
    """
    Determines the interest amount for application using rule of 78 amortisation.
    For flat and rule of 78 interest we don't have concept of emi vs non emi interest as the
    accrued amount is calculated for the month at the end of the month, instead of daily accruals.
    Hence, we do not use some of the args passed in for this implementation of the interface.

    :param vault: vault object for the account with interest to apply
    :param effective_datetime: not used but required by the interface signature
    :param previous_application_datetime: not used but required by the interface signature
    :param balances_at_application: balances to extract current accrued amounts from. Only pass in
    to override the feature's default fetching
    :param balances_one_repayment_period_ago: not used but required by the interface signature
    :param denomination: accrual denomination. Only pass in to override the feature's default
    fetching
    :param application_precision: number of places that interest is rounded to during application.
     Only pass in to override the feature's default fetching
    :return: the interest amounts
    """
    if balances_at_application is None:
        balances_at_application = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if application_precision is None:
        application_precision = interest_application_get_application_precision(vault=vault)
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name=rule_of_78_PARAM_DENOMINATION)
    principal: Decimal = utils_get_parameter(vault=vault, name=rule_of_78_PARAM_PRINCIPAL)
    total_term = int(
        utils_get_parameter(vault=vault, name=lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT)
    )
    elapsed = term_helpers_calculate_elapsed_term(
        balances=balances_at_application, denomination=denomination
    )
    term_remaining = total_term - elapsed
    fixed_interest_rate: Decimal = utils_get_parameter(
        vault=vault, name=rule_of_78_PARAM_FIXED_INTEREST_RATE
    )
    total_interest = rule_of_78_calculate_non_accruing_loan_total_interest(
        original_principal=principal,
        annual_interest_rate=fixed_interest_rate,
        total_term=total_term,
        precision=application_precision,
    )
    rule_of_78_denominator = rule_of_78__get_sum_1_to_N(total_term)
    interest_due = rule_of_78__calculate_interest_due(
        total_interest=total_interest,
        total_term=total_term,
        term_remaining=term_remaining,
        denominator=rule_of_78_denominator,
        application_precision=application_precision,
    )
    return lending_interfaces_InterestAmounts(
        emi_accrued=Decimal("0"),
        emi_rounded_accrued=interest_due,
        non_emi_accrued=Decimal("0"),
        non_emi_rounded_accrued=Decimal("0"),
        total_rounded=interest_due,
    )


def rule_of_78__calculate_interest_due(
    total_interest: Decimal,
    total_term: int,
    term_remaining: int,
    denominator: int,
    application_precision: int,
) -> Decimal:
    """
    Returns the amount of interest due for a rule of 78 loan accounting for any rounding issues
    on the final event.
    :param total_interest: total interest to be paid during the loan's tenure
    :param term_remaining: number of repayments remaining on the loan
    :param denominator: rule of 78 denominator,
    calculated by summing all integers from 1 to the total_term of the loan.
    :param application_precision: number of places that interest is rounded to during application.
    """
    if term_remaining == 1:
        return rule_of_78__calculate_final_month_interest(
            total_interest=total_interest,
            total_term=total_term,
            rule_of_78_denominator=denominator,
            application_precision=application_precision,
        )
    return utils_round_decimal(total_interest * term_remaining / denominator, application_precision)


def rule_of_78__calculate_final_month_interest(
    total_interest: Decimal,
    total_term: int,
    rule_of_78_denominator: int,
    application_precision: int,
) -> Decimal:
    """
    The final month interest will be equal to:
    total_interest - SUM(interest_month_n) from n = 0 to n = total_term - 1, where interest_month_n
    is given by total_interest * (total_term - n) / rule_of_78_denominator

    """
    return total_interest - Decimal(
        sum(
            (
                utils_round_decimal(
                    amount=total_interest * (total_term - n) / rule_of_78_denominator,
                    decimal_places=application_precision,
                )
                for n in range(0, total_term - 1)
            )
        )
    )


def rule_of_78__get_sum_1_to_N(N: int) -> int:
    """
    Returns the sum of integers from 1 to N.
    This is used to calculate the interest portion of a rule of 78 loan.
    :param N: The integer that we will sum to
    """
    return int(N * (N + 1) / 2)


def rule_of_78_calculate_non_accruing_loan_total_interest(
    original_principal: Decimal, annual_interest_rate: Decimal, total_term: int, precision: int
) -> Decimal:
    """
    Returns the total loan interest for a flat interest or rule of 78 amortised loan
    :param original_principal: principal of the loan at loan start
    :param annual_interest_rate: yearly interest rate of the loan
    :param total_term: total term of the loan
    :param precision: number of places that interest is rounded to before application.
    """
    return utils_round_decimal(
        original_principal
        * utils_yearly_to_monthly_rate(yearly_rate=annual_interest_rate)
        * Decimal(total_term),
        precision,
    )


rule_of_78_InterestApplication = lending_interfaces_InterestApplication(
    apply_interest=rule_of_78_apply_interest,
    get_interest_to_apply=rule_of_78_get_interest_to_apply,
    get_application_precision=interest_application_get_application_precision,
)
rule_of_78_AmortisationFeature = lending_interfaces_Amortisation(
    calculate_emi=rule_of_78_calculate_emi,
    term_details=rule_of_78_term_details,
    override_final_event=False,
)

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


def emi_get_expected_emi(
    balances: BalanceDefaultDict, denomination: str, decimal_places: Optional[int] = 2
) -> Decimal:
    return utils_balance_at_coordinates(
        balances=balances,
        address=lending_addresses_EMI,
        denomination=denomination,
        decimal_places=decimal_places,
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
#    balloon_payments.py
# md5:889f4fcc95c386d913c59ef7b695bae5

balloon_payments_BALLOON_PAYMENT_EVENT = "BALLOON_PAYMENT_EVENT"
balloon_payments_PARAM_BALLOON_PAYMENT_DAYS_DELTA = "balloon_payment_days_delta"
balloon_payments_PARAM_BALLOON_PAYMENT_AMOUNT = "balloon_payment_amount"
balloon_payments_PARAM_BALLOON_EMI_AMOUNT = "balloon_emi_amount"
balloon_payments_PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT = "expected_balloon_payment_amount"
balloon_payments_balloon_payment_days_delta_parameter = Parameter(
    name=balloon_payments_PARAM_BALLOON_PAYMENT_DAYS_DELTA,
    shape=OptionalShape(shape=NumberShape(min_value=0, step=1)),
    level=ParameterLevel.INSTANCE,
    description="The number of days between the final repayment event and the balloon payment event.",
    display_name="Balloon Payment Days Delta",
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)
balloon_payments_balloon_payment_amount_parameter = Parameter(
    name=balloon_payments_PARAM_BALLOON_PAYMENT_AMOUNT,
    shape=OptionalShape(shape=NumberShape(min_value=Decimal(100), step=Decimal("0.01"))),
    level=ParameterLevel.INSTANCE,
    description="The balloon payment amount the customer has chosen to pay on the balloon payment day. If set, this determines the customer has chosen a fixed balloon payment.",
    display_name="Balloon Payment Amount",
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)
balloon_payments_balloon_emi_amount_parameter = Parameter(
    name=balloon_payments_PARAM_BALLOON_EMI_AMOUNT,
    shape=OptionalShape(shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01"))),
    level=ParameterLevel.INSTANCE,
    description="The fixed balloon emi amount the customer has chosen to pay each month. If set, this determines the customer has chosen a fixed emi payment.",
    display_name="Balloon Payment EMI Amount",
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
)
balloon_payments_expected_balloon_payment_amount_parameter = Parameter(
    name=balloon_payments_PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT,
    shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="The expected balloon payment amount to be paid on the balloon payment date. This is only relevant for no_repayment, interest_only and minimum_repayment_with_balloon_payment loans.",
    display_name="Expected Balloon Payment Amount",
)
balloon_payments_parameters = [
    balloon_payments_balloon_payment_days_delta_parameter,
    balloon_payments_balloon_payment_amount_parameter,
    balloon_payments_balloon_emi_amount_parameter,
    balloon_payments_expected_balloon_payment_amount_parameter,
]


def balloon_payments_event_types(product_name: str) -> list[SmartContractEventType]:
    """
    event_types generate a list of schedules that will be referenced in the given smart contract.

    :param product_name: the product name
    :return: a slice of schedule event type references that will be used by this feature.
    """
    return [
        SmartContractEventType(
            name=balloon_payments_BALLOON_PAYMENT_EVENT,
            scheduler_tag_ids=[
                f"{product_name.upper()}_{balloon_payments_BALLOON_PAYMENT_EVENT}_AST"
            ],
        )
    ]


def balloon_payments_disabled_balloon_schedule(
    account_opening_datetime: datetime,
) -> dict[str, ScheduledEvent]:
    return {
        balloon_payments_BALLOON_PAYMENT_EVENT: utils_create_end_of_time_schedule(
            account_opening_datetime
        )
    }


def balloon_payments_scheduled_events(
    vault: Any, account_opening_datetime: datetime, amortisation_method: str
) -> dict[str, ScheduledEvent]:
    """
    Create monthly scheduled event for due amount calculation, starting one month from account
    opening. This will also return the due date schedule if the schedule is not a no-repayment loan
    :param vault: vault object for the account that requires the schedule
    :param account_opening_datetime: when the account is opened/activated
    :return: event type to scheduled event
    """
    balloon_payments_scheduled_events: dict[str, ScheduledEvent] = {}
    balloon_payment_start_date = account_opening_datetime + relativedelta(days=1)
    skip_due_date = no_repayment_is_no_repayment_loan(amortisation_method)
    balloon_payment_delta_days = balloon_payments__get_balloon_payment_delta_days(vault=vault)
    if skip_due_date:
        total_term = int(
            utils_get_parameter(vault=vault, name=lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT)
        )
        balloon_payment_datetime = account_opening_datetime + relativedelta(
            months=total_term, days=balloon_payment_delta_days
        )
        balloon_payment_datetime = balloon_payments_set_time_from_due_amount_parameter(
            vault=vault, from_datetime=balloon_payment_datetime
        )
        schedule_expr = utils_one_off_schedule_expression(balloon_payment_datetime)
        balloon_payments_scheduled_events[balloon_payments_BALLOON_PAYMENT_EVENT] = ScheduledEvent(
            start_datetime=balloon_payment_start_date, expression=schedule_expr
        )
        balloon_payments_scheduled_events[
            due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
        ] = utils_create_end_of_time_schedule(balloon_payment_start_date)
    else:
        balloon_payments_scheduled_events[balloon_payments_BALLOON_PAYMENT_EVENT] = ScheduledEvent(
            start_datetime=balloon_payment_start_date, expression=utils_END_OF_TIME_EXPRESSION
        )
        balloon_payments_scheduled_events.update(
            due_amount_calculation_scheduled_events(vault, account_opening_datetime)
        )
    return balloon_payments_scheduled_events


def balloon_payments_set_time_from_due_amount_parameter(
    vault: Any, from_datetime: datetime
) -> datetime:
    return balloon_payments__set_datetime_from_parameter(
        vault=vault,
        parameter_prefix=due_amount_calculation_DUE_AMOUNT_CALCULATION_PREFIX,
        from_datetime=from_datetime,
    )


def balloon_payments__set_datetime_from_parameter(
    vault: Any, parameter_prefix: str, from_datetime: datetime
) -> datetime:
    """
    replaces a datetime with the hours, minutes, and seconds set from a parameter config

    :param vault: smart contract vault object.
    :param parameter_prefix: the parameter prefix to replace the datetime object with.
    :param datetime: the datetime to mutate.
    :return: returns a datetime with the datetime set on a given parameter.
    """
    (param_hour, param_minute, param_second) = utils_get_schedule_time_from_parameters(
        vault=vault, parameter_prefix=parameter_prefix
    )
    return from_datetime.replace(hour=param_hour, minute=param_minute, second=param_second)


def balloon_payments_update_balloon_payment_schedule(
    vault: Any, execution_timestamp: datetime
) -> list[UpdateAccountEventTypeDirective]:
    """
    this function will schedule a balloon payment for the predetermined amount of days
    after the execution timestamp and will skip the due amount calculation schedule.
    The execution timestamp should be time of the last due payment event.

    :param vault: vault object for the account that requires the schedule
    :param execution_timestamp: the execution timestamp of the last due payment.
    """
    balloon_payment_delta_days = balloon_payments__get_balloon_payment_delta_days(vault=vault)
    balloon_payment_time = execution_timestamp + relativedelta(days=balloon_payment_delta_days)
    balloon_payment_time = balloon_payments_set_time_from_due_amount_parameter(
        vault=vault, from_datetime=balloon_payment_time
    )
    schedule_expr = utils_one_off_schedule_expression(balloon_payment_time)
    return [
        UpdateAccountEventTypeDirective(
            event_type=balloon_payments_BALLOON_PAYMENT_EVENT, expression=schedule_expr, skip=False
        ),
        UpdateAccountEventTypeDirective(
            event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT,
            expression=utils_END_OF_TIME_EXPRESSION,
            skip=True,
        ),
    ]


def balloon_payments__get_balloon_payment_delta_days(vault: Any) -> int:
    return int(
        utils_get_parameter(
            vault=vault,
            name=balloon_payments_PARAM_BALLOON_PAYMENT_DAYS_DELTA,
            is_optional=True,
            default_value=Decimal("0"),
        )
    )


def balloon_payments_schedule_logic(
    vault: Any,
    hook_arguments: ScheduledEventHookArguments,
    account_type: str = "",
    interest_application_feature: Optional[lending_interfaces_InterestApplication] = None,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    The schedule logic that is tied to the balloon payment event.
    This will transfer the existing outstanding principal to principal due.
    :param vault: vault object for the account
    :param hook_arguments: the scheduled event's hook arguments
    :param account_type: the account type, used for GL posting metadata purposes
    :param interest_application_feature: feature that is responsible for applying interest
    as part of the due amount calculation. This can be omitted if no interest is charged for
    a product (e.g. a 0% interest Pay-In-X loan)
    :param reamortisation_condition_features: a list of features used to determine whether
    reamortisation is required
    :param amortisation_feature: feature that is responsible for recalculating the emi if
    reamortisation is required (determined by the reamortisation_condition_features). To be provided
    if reamortisation_condition_features is also provided. If omitted and reamortisation is
    necessary then it will default to use the existing emi balance
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
    effective_datetime: datetime = hook_arguments.effective_datetime
    amortisation_method = utils_get_parameter(
        vault=vault, name="amortisation_method", is_union=True
    )
    if not balloon_payments_is_balloon_loan(amortisation_method=amortisation_method):
        return []
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = utils_get_parameter(vault=vault, name="denomination")
    current_principal = due_amount_calculation_get_principal(
        balances=balances, denomination=denomination
    )
    postings += due_amount_calculation_transfer_principal_due(
        customer_account=customer_account,
        principal_due=current_principal,
        denomination=denomination,
    )
    if interest_application_feature is not None:
        postings += interest_application_feature.apply_interest(
            vault=vault,
            effective_datetime=effective_datetime,
            previous_application_datetime=effective_datetime,
        )
    if postings:
        return [
            CustomInstruction(
                postings=postings,
                override_all_restrictions=True,
                instruction_details=utils_standard_instruction_details(
                    description="Updating due balances for final balloon payment.",
                    event_type=hook_arguments.event_type,
                    gl_impacted=True,
                    account_type=account_type,
                ),
            )
        ]
    else:
        return []


def balloon_payments_is_balloon_loan(amortisation_method: str) -> bool:
    return any(
        [
            no_repayment_is_no_repayment_loan(amortisation_method=amortisation_method),
            minimum_repayment_is_minimum_repayment_loan(amortisation_method=amortisation_method),
            interest_only_is_interest_only_loan(amortisation_method=amortisation_method),
        ]
    )


def balloon_payments_get_expected_balloon_payment_amount(
    vault: Any,
    effective_datetime: datetime,
    balances: BalanceDefaultDict,
    interest_rate_feature: Optional[lending_interfaces_InterestRate] = None,
) -> Decimal:
    """
    Returns the expected balloon payment amount for a balloon payment loan, else returns Decimal(0)

    This assumes that the interest rate remains the same throughout the lifetime of the loan

    If the interest rate or the EMI is not calculated yet then return 0.
    """
    amortisation_method = utils_get_parameter(
        vault=vault, name="amortisation_method", is_union=True
    )
    principal = utils_balance_at_coordinates(
        balances=balances,
        address=lending_addresses_PRINCIPAL,
        denomination=utils_get_parameter(vault=vault, name="denomination"),
    )
    if no_repayment_is_no_repayment_loan(
        amortisation_method=amortisation_method
    ) or interest_only_is_interest_only_loan(amortisation_method=amortisation_method):
        if principal == Decimal("0.00"):
            return Decimal("0.00")
        return principal
    elif minimum_repayment_is_minimum_repayment_loan(amortisation_method=amortisation_method):
        balloon_payment_amount = utils_get_parameter(
            vault=vault, name=balloon_payments_PARAM_BALLOON_PAYMENT_AMOUNT, is_optional=True
        )
        emi = utils_get_parameter(
            vault=vault, name=balloon_payments_PARAM_BALLOON_EMI_AMOUNT, is_optional=True
        )
        if balloon_payment_amount is not None:
            return balloon_payment_amount
        elif emi is not None:
            if interest_rate_feature is None:
                return Decimal("0")
            total_term = int(
                utils_get_parameter(
                    vault=vault, name=lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT
                )
            )
            monthly_interest_rate = interest_rate_feature.get_monthly_interest_rate(
                vault=vault, effective_datetime=effective_datetime
            )
            application_precision = int(
                utils_get_parameter(vault=vault, name="application_precision")
            )
            return balloon_payments_calculate_lump_sum(
                emi=emi,
                principal=principal,
                rate=monthly_interest_rate,
                terms=total_term,
                precision=application_precision,
            )
    return Decimal("0")


def balloon_payments_calculate_lump_sum(
    emi: Decimal, principal: Decimal, rate: Decimal, terms: int, precision: int = 2
) -> Decimal:
    """
     Amortisation Formula:
        EMI = (P-(L/(1+R)^(N)))*R*(((1+R)^N)/((1+R)^N-1))

    Re-arranging for L:
        L = (1+R)^(N)*(P - EMI/R) + EMI/R

    P is principal
    R is the monthly interest rate
    N is total term
    L is the lump sum
    """
    amount = (1 + rate) ** terms * (principal - emi / rate) + emi / rate
    return utils_round_decimal(amount=amount, decimal_places=precision)


def balloon_payments_update_no_repayment_balloon_schedule(vault: Any) -> dict[str, ScheduledEvent]:
    """
    to be called on a conversion hook only.
    will return the updated balloon payment schedule if the term length were ever to change
    """
    amortisation_method = utils_get_parameter(
        vault=vault, name="amortisation_method", is_union=True
    )
    _is_no_repayment_loan = no_repayment_is_no_repayment_loan(
        amortisation_method=amortisation_method
    )
    if not _is_no_repayment_loan:
        return {}
    term_length = utils_get_parameter(
        vault=vault, name=lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT
    )
    account_opening_time = vault.get_account_creation_datetime()
    balloon_payment_delta_days = balloon_payments__get_balloon_payment_delta_days(vault=vault)
    balloon_payment_datetime = balloon_payments_set_time_from_due_amount_parameter(
        vault=vault, from_datetime=account_opening_time
    )
    return {
        balloon_payments_BALLOON_PAYMENT_EVENT: ScheduledEvent(
            expression=utils_one_off_schedule_expression(
                balloon_payment_datetime
                + relativedelta(months=term_length, days=balloon_payment_delta_days)
            )
        )
    }


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
#    early_repayment.py
# md5:f999fa0e14d31eabc867091bfbd3904d

early_repayment_PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT = "early_repayment_fee_income_account"
early_repayment_PARAM_EARLY_REPAYMENT_FLAT_FEE = "early_repayment_flat_fee"
early_repayment_PARAM_EARLY_REPAYMENT_FEE_RATE = "early_repayment_fee_rate"
early_repayment_PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT = "total_early_repayment_amount"
early_repayment_early_repayment_fee_income_account_param = Parameter(
    name=early_repayment_PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT,
    shape=AccountIdShape(),
    level=ParameterLevel.TEMPLATE,
    description="Internal account for early repayment fee income balance.",
    display_name="Early Repayment Fee Income Account",
    default_value="EARLY_REPAYMENT_FEE_INCOME",
)
early_repayment_early_repayment_flat_fee_param = Parameter(
    name=early_repayment_PARAM_EARLY_REPAYMENT_FLAT_FEE,
    level=ParameterLevel.TEMPLATE,
    description="Flat fee to charge for an early repayment. Typically this would be used instead of Early Repayment Fee Rate, otherwise they will both be added together.",
    display_name="Early Repayment Flat Fee",
    shape=NumberShape(min_value=0),
    default_value=Decimal("0"),
)
early_repayment_early_repayment_fee_rate_param = Parameter(
    name=early_repayment_PARAM_EARLY_REPAYMENT_FEE_RATE,
    level=ParameterLevel.TEMPLATE,
    description="This rate will be used to calculate a fee to be charged for an early repayment, calculated as a percentage of the remaining principal. Typically this would be used instead of Early Repayment Flat Fee, otherwise they will both be added together.",
    display_name="Early Repayment Fee Rate",
    shape=NumberShape(min_value=0),
    default_value=Decimal("0.01"),
)
early_repayment_total_early_repayment_amount_parameter = Parameter(
    name=early_repayment_PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT,
    shape=NumberShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="Total early repayment amount required to fully repay and close the account",
    display_name="Total Early Repayment Amount",
)
early_repayment_parameters = [
    early_repayment_early_repayment_fee_income_account_param,
    early_repayment_early_repayment_flat_fee_param,
    early_repayment_early_repayment_fee_rate_param,
    early_repayment_total_early_repayment_amount_parameter,
]


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


def early_repayment_get_early_repayment_flat_fee(
    vault: Any,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    precision: int = 2,
) -> Decimal:
    """
    Get the early repayment flat fee amount from the parameter value. To be used as a
    get_early_repayment_fee_amount callable for an EarlyRepaymentFee interface.

    :param vault: vault object for the relevant account
    :param balances: only needed to satisfy the interface signature
    :param denomination: only needed to satisfy the interface signature
    :param precision: the number of decimal places to round to
    :return: the flat fee amount
    """
    early_repayment_flat_fee = utils_get_parameter(
        vault=vault, name=early_repayment_PARAM_EARLY_REPAYMENT_FLAT_FEE
    )
    return utils_round_decimal(early_repayment_flat_fee, precision)


def early_repayment_calculate_early_repayment_percentage_fee(
    vault: Any,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    precision: int = 2,
) -> Decimal:
    """
    Calculate the early repayment fee using the rate from the Early Repayment Fee Rate parameter
    with the total remaining principal. To be used as a get_early_repayment_fee_amount callable for
    an EarlyRepaymentFee interface.

    :param vault: vault object for the relevant account
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :param precision: the number of decimal places to round to
    :return: the percentage fee amount
    """
    balances = early_repayment__get_balances(vault=vault, balances=balances)
    denomination = early_repayment__get_denomination(vault=vault, denomination=denomination)
    total_remaining_principal = derived_params_get_total_remaining_principal(
        balances=balances, denomination=denomination
    )
    early_repayment_fee_rate = utils_get_parameter(
        vault=vault, name=early_repayment_PARAM_EARLY_REPAYMENT_FEE_RATE
    )
    return utils_round_decimal(total_remaining_principal * early_repayment_fee_rate, precision)


def early_repayment_charge_early_repayment_fee(
    vault: Any,
    account_id: str,
    amount_to_charge: Decimal,
    fee_name: str,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Handle the early repayment fee within post posting, returning the associated posting
    instructions for the fee. To be used as a charge_early_repayment_fee callable for
    an EarlyRepaymentFee interface.

    :param vault: vault object for the relevant account
    :param account_id: id of the customer account
    :param amount_to_charge: the amount to charge for the fee
    :param fee_name: the name of the early repayment fee type
    :param denomination: denomination of the relevant loan
    :return: custom instruction to handle the charge of the fee
    """
    denomination = early_repayment__get_denomination(vault=vault, denomination=denomination)
    early_repayment_fee_income_account: str = utils_get_parameter(
        vault=vault, name=early_repayment_PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT
    )
    return fees_fee_custom_instruction(
        customer_account_id=account_id,
        denomination=denomination,
        amount=amount_to_charge,
        internal_account=early_repayment_fee_income_account,
        instruction_details={"description": f"Early Repayment Fee: {fee_name}"},
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


early_repayment_EarlyRepaymentFlatFee = lending_interfaces_EarlyRepaymentFee(
    get_early_repayment_fee_amount=early_repayment_get_early_repayment_flat_fee,
    charge_early_repayment_fee=early_repayment_charge_early_repayment_fee,
    fee_name="Flat Fee",
)
early_repayment_EarlyRepaymentPercentageFee = lending_interfaces_EarlyRepaymentFee(
    get_early_repayment_fee_amount=early_repayment_calculate_early_repayment_percentage_fee,
    charge_early_repayment_fee=early_repayment_charge_early_repayment_fee,
    fee_name="Percentage Fee",
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
interest_capitalisation_PARAM_CAPITALISED_PENALTIES_RECEIVED_ACCOUNT = (
    "capitalised_penalties_received_account"
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
interest_capitalisation_capitalised_penalties_received_account_param = Parameter(
    name=interest_capitalisation_PARAM_CAPITALISED_PENALTIES_RECEIVED_ACCOUNT,
    shape=AccountIdShape(),
    level=ParameterLevel.TEMPLATE,
    description="Internal account for capitalised penalties received balance.",
    display_name="Capitalised Penalties Received Account",
    default_value="CAPITALISED_PENALTIES_RECEIVED",
)
interest_capitalisation_capitalise_penalty_interest_param = Parameter(
    name=interest_capitalisation_PARAM_CAPITALISE_PENALTY_INTEREST,
    shape=common_parameters_BooleanShape,
    level=ParameterLevel.TEMPLATE,
    description="Determines if penalty interest is immediately added to Penalties (False) or  accrued and capitalised at next due amount calculation.",
    display_name="Capitalise Penalty Interest",
    default_value=common_parameters_BooleanValueFalse,
)
interest_capitalisation_parameters = [
    interest_capitalisation_capitalised_interest_receivable_account_param,
    interest_capitalisation_capitalised_interest_received_account_param,
    interest_capitalisation_capitalised_penalties_received_account_param,
    interest_capitalisation_capitalise_penalty_interest_param,
]


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
        level=ParameterLevel.TEMPLATE,
        description="The fixed annual rate of the loan (p.a).",
        display_name="Fixed Interest Rate",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        default_value=Decimal("0.0008"),
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


fixed_interest_rate_interface = lending_interfaces_InterestRate(
    get_daily_interest_rate=fixed_get_daily_interest_rate,
    get_monthly_interest_rate=fixed_get_monthly_interest_rate,
    get_annual_interest_rate=fixed_get_annual_interest_rate,
)
fixed_FixedReamortisationCondition = lending_interfaces_ReamortisationCondition(
    should_trigger_reamortisation=lambda vault, period_start_datetime, period_end_datetime, elapsed_term: False
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


variable_interest_rate_interface = lending_interfaces_InterestRate(
    get_daily_interest_rate=variable_get_daily_interest_rate,
    get_monthly_interest_rate=variable_get_monthly_interest_rate,
    get_annual_interest_rate=variable_get_annual_interest_rate,
)
variable_VariableReamortisationCondition = lending_interfaces_ReamortisationCondition(
    should_trigger_reamortisation=variable_should_trigger_reamortisation
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
overdue_PARAM_NEXT_OVERDUE_DATE = "next_overdue_date"
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
overdue_next_overdue_derived_parameter = Parameter(
    name=overdue_PARAM_NEXT_OVERDUE_DATE,
    shape=DateShape(),
    level=ParameterLevel.INSTANCE,
    derived=True,
    description="The date on which current due principal and interest will become overdue.",
    display_name="Next Overdue Date",
)


def overdue_get_repayment_period_parameter(vault: Any) -> int:
    return int(utils_get_parameter(vault=vault, name=overdue_PARAM_REPAYMENT_PERIOD))


def overdue_get_next_overdue_derived_parameter(
    vault: Any, previous_due_amount_calculation_datetime: datetime
) -> datetime:
    return previous_due_amount_calculation_datetime + relativedelta(
        days=overdue_get_repayment_period_parameter(vault=vault)
    )


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
overpayment_fee_parameters = [
    overpayment_overpayment_fee_rate_param,
    overpayment_overpayment_fee_income_account_param,
]


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


def overpayment_is_posting_an_overpayment(
    vault: Any,
    repayment_amount: Decimal,
    denomination: str,
    fetcher_id: str = fetchers_LIVE_BALANCES_BOF_ID,
) -> bool:
    if repayment_amount >= 0:
        return False
    balances: BalanceDefaultDict = vault.get_balances_observation(fetcher_id=fetcher_id).balances
    due_amount = overpayment_get_total_due_amount(balances=balances, denomination=denomination)
    return abs(repayment_amount) > due_amount


def overpayment_validate_overpayment(
    vault: Any,
    repayment_amount: Decimal,
    denomination: str,
    fetcher_id: str = fetchers_LIVE_BALANCES_BOF_ID,
) -> Optional[Rejection]:
    """Rejects repayments if the amount exceeds total owed, including Principal, + overpayment fee

    :param vault: Vault object for the account being credited by the posting
    :param repayment_amount: the repayment amount. Expected to be negative as this function is for
    Tside.ASSET products.
    :param denomination: denomination of the loan
    :param fetcher_id: id of the fetcher to use, defaults to fetchers.LIVE_BALANCES_BOF_ID, which
    may not be suitable if used outside of pre_posting_hook
    :return: An optional rejection, only non-None if the amount repaid exceeds total owed + fee
    """
    if repayment_amount >= 0:
        return None
    max_overpayment_amount = overpayment_get_max_overpayment_amount(
        vault=vault, denomination=denomination, fetcher_id=fetcher_id
    )
    if abs(repayment_amount) > max_overpayment_amount:
        return Rejection(
            message="Cannot pay more than is owed.", reason_code=RejectionReason.AGAINST_TNC
        )
    return None


def overpayment_get_max_overpayment_amount(
    vault: Any, denomination: str, fetcher_id: str = fetchers_LIVE_BALANCES_BOF_ID
) -> Decimal:
    overpayment_fee_rate = overpayment_get_overpayment_fee_rate_parameter(vault=vault)
    balances: BalanceDefaultDict = vault.get_balances_observation(fetcher_id=fetcher_id).balances
    total_outstanding_debt = overpayment_get_total_outstanding_debt(
        balances=balances, denomination=denomination
    )
    max_overpayment_fee = overpayment_get_max_overpayment_fee(
        fee_rate=overpayment_fee_rate, balances=balances, denomination=denomination
    )
    return total_outstanding_debt + max_overpayment_fee


def overpayment_get_total_outstanding_debt(
    balances: BalanceDefaultDict, denomination: str, precision: int = 2
) -> Decimal:
    return utils_sum_balances(
        balances=balances,
        addresses=lending_addresses_ALL_OUTSTANDING,
        denomination=denomination,
        decimal_places=precision,
    )


def overpayment_get_total_due_amount(
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


def overpayment_get_overpayment_fee_rate_parameter(vault: Any) -> Decimal:
    overpayment_fee_rate: Decimal = utils_get_parameter(
        vault=vault, name=overpayment_PARAM_OVERPAYMENT_FEE_RATE
    )
    return overpayment_fee_rate


overpayment_OverpaymentReamortisationCondition = lending_interfaces_ReamortisationCondition(
    should_trigger_reamortisation=overpayment_should_trigger_reamortisation
)
overpayment_OverpaymentPrincipalAdjustment = lending_interfaces_PrincipalAdjustment(
    calculate_principal_adjustment=overpayment_calculate_principal_adjustment
)
overpayment_OverpaymentResidualCleanupFeature = lending_interfaces_ResidualCleanup(
    get_residual_cleanup_postings=overpayment_get_residual_cleanup_postings
)


def overpayment_get_early_repayment_overpayment_fee(
    vault: Any,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    precision: int = 2,
) -> Decimal:
    """
    Get the early repayment overpayment fee amount. This is always the maximum overpayment fee.
    To be used as a get_early_repayment_fee_amount callable for an EarlyRepaymentFee interface.

    :param vault: vault object for the relevant account
    :param balances: balances to base calculations on
    :param denomination: denomination of the relevant loan
    :param precision: the number of decimal places to round to
    :return: the flat fee amount
    """
    balances = (
        vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
        if balances is None
        else balances
    )
    denomination = (
        utils_get_parameter(vault=vault, name="denomination")
        if denomination is None
        else denomination
    )
    overpayment_fee_rate = overpayment_get_overpayment_fee_rate_parameter(vault=vault)
    max_overpayment_fee = overpayment_get_max_overpayment_fee(
        fee_rate=overpayment_fee_rate,
        balances=balances,
        denomination=denomination,
        precision=precision,
    )
    return max_overpayment_fee


def overpayment_skip_charge_early_repayment_fee_for_overpayment(
    vault: Any,
    account_id: str,
    amount_to_charge: Decimal,
    fee_name: str,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Skip the charge for the overpayment fee within an early repayment since this fee posting is
    already handled by the overpayment logic within post posting.  To be used as a
    charge_early_repayment_fee callable for an EarlyRepaymentFee interface.

    :param vault: only needed to satisfy the interface signature
    :param account_id: only needed to satisfy the interface signature
    :param amount_to_charge: only needed to satisfy the interface signature
    :param fee_name: only needed to satisfy the interface signature
    :param denomination: only needed to satisfy the interface signature
    :return: an empty list
    """
    return []


overpayment_EarlyRepaymentOverpaymentFee = lending_interfaces_EarlyRepaymentFee(
    get_early_repayment_fee_amount=overpayment_get_early_repayment_overpayment_fee,
    charge_early_repayment_fee=overpayment_skip_charge_early_repayment_fee_for_overpayment,
    fee_name="Overpayment Fee",
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
#    repayment_holiday.py
# md5:8ab69326d0731879f6300743f6dbefd4

repayment_holiday_INCREASE_EMI = "increase_emi"
repayment_holiday_INCREASE_TERM = "increase_term"
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
repayment_holiday_PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE = "repayment_holiday_impact_preference"
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
repayment_holiday_repayment_holiday_impact_preference_param = Parameter(
    name=repayment_holiday_PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE,
    shape=UnionShape(
        items=[
            UnionItem(key=repayment_holiday_INCREASE_TERM, display_name="Increase Term"),
            UnionItem(key=repayment_holiday_INCREASE_EMI, display_name="Increase EMI"),
        ]
    ),
    level=ParameterLevel.INSTANCE,
    description="Defines how to handle a repayment holiday: Increase EMI but keep the term of the loan the same. Increase term but keep the monthly repayments the same. ",
    display_name="Repayment Holiday Impact Preference",
    update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    default_value=UnionItemValue(key="increase_emi"),
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


def repayment_holiday_should_trigger_reamortisation_with_impact_preference(
    vault: Any,
    period_start_datetime: datetime,
    period_end_datetime: datetime,
    elapsed_term: Optional[int] = None,
) -> bool:
    """
    Determines whether to trigger reamortisation due to a repayment holiday ending.
    Only returns True if a repayment holiday was active at period start datetime
    and no longer is as of period end datetime and the repayment holiday impact preference to
    increase emi

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
    return repayment_holiday_is_repayment_holiday_impact_increase_emi(
        vault=vault, effective_datetime=period_end_datetime
    ) and repayment_holiday__has_repayment_holiday_ended(
        vault=vault,
        period_start_datetime=period_start_datetime,
        period_end_datetime=period_end_datetime,
    )


def repayment_holiday_is_repayment_holiday_impact_increase_emi(
    vault: Any, effective_datetime: datetime
) -> bool:
    return (
        utils_get_parameter(
            vault=vault,
            name=repayment_holiday_PARAM_REPAYMENT_HOLIDAY_IMPACT_PREFERENCE,
            at_datetime=effective_datetime,
            is_union=True,
        ).lower()
        == repayment_holiday_INCREASE_EMI
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


repayment_holiday_ReamortisationConditionWithPreference = lending_interfaces_ReamortisationCondition(
    should_trigger_reamortisation=repayment_holiday_should_trigger_reamortisation_with_impact_preference
)

# Objects below have been imported from:
#    loan.py
# md5:54706bea879a15272ef9d964edc2d429

data_fetchers = [
    fetchers_EFFECTIVE_OBSERVATION_FETCHER,
    fetchers_LIVE_BALANCES_BOF,
    *interest_accrual_data_fetchers,
    interest_application_accrued_interest_eff_fetcher,
    interest_application_accrued_interest_one_month_ago_fetcher,
    overpayment_overpayment_tracker_eff_fetcher,
    overpayment_expected_interest_eod_fetcher,
]
MONTHLY_REST_EFFECTIVE_PRINCIPAL = "MONTHLY_REST_EFFECTIVE_PRINCIPAL"
ACCRUED_INTEREST_PENDING_CAPITALISATION = "ACCRUED_INTEREST_PENDING_CAPITALISATION"
CAPITALISED_INTEREST_TRACKER = "CAPITALISED_INTEREST_TRACKER"
ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION = "ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION"
CAPITALISED_PENALTIES_TRACKER = "CAPITALISED_PENALTIES_TRACKER"
PARAM_ACCRUE_ON_DUE_PRINCIPAL = "accrue_interest_on_due_principal"
PARAM_AMORTISE_UPFRONT_FEE = "amortise_upfront_fee"
PARAM_CHECK_DELINQUENCY_HOUR = "check_delinquency_hour"
PARAM_CHECK_DELINQUENCY_MINUTE = "check_delinquency_minute"
PARAM_CHECK_DELINQUENCY_SECOND = "check_delinquency_second"
PARAM_DENOMINATION = "denomination"
PARAM_FIXED_RATE_LOAN = "fixed_interest_loan"
PARAM_GRACE_PERIOD = "grace_period"
PARAM_INTEREST_ACCRUAL_REST_TYPE = "interest_accrual_rest_type"
PARAM_LATE_REPAYMENT_FEE = "late_repayment_fee"
PARAM_TOP_UP = "top_up"
PARAM_UPFRONT_FEE = "upfront_fee"
PARAM_AMORTISATION_METHOD = "amortisation_method"
PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST = "capitalise_no_repayment_accrued_interest"
PARAM_DELINQUENCY_FLAG = "delinquency_flag"
PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST = "penalty_compounds_overdue_interest"
PARAM_CAPITALISE_LATE_REPAYMENT_FEE = "capitalise_late_repayment_fee"
PARAM_PENALTY_INTEREST_RATE = "penalty_interest_rate"
PARAM_PENALTY_INCLUDES_BASE_RATE = "penalty_includes_base_rate"
PARAM_PENALTY_INTEREST_RECEIVED_ACCOUNT = "penalty_interest_received_account"
PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "late_repayment_fee_income_account"
PARAM_UPFRONT_FEE_INTERNAL_ACCOUNT = "upfront_fee_income_account"
ACCOUNT_TYPE = "LOAN"
CHECK_DELINQUENCY = "CHECK_DELINQUENCY"
CHECK_DELINQUENCY_PREFIX = "check_delinquency"
DEFAULT_DELINQUENCY_FLAG = "ACCOUNT_DELINQUENT"
FIXED_RATE_FEATURE = fixed_interest_rate_interface
INSTRUCTION_DETAILS_KEY_INTEREST_ADJUSTMENT = "interest_adjustment"
INSTRUCTION_DETAILS_KEY_FEE = "fee"
LOAN_TOP_UP = "LOAN_TOP_UP"
MARK_DELINQUENT_NOTIFICATION = f"{ACCOUNT_TYPE}_MARK_DELINQUENT"
REPAYMENT_OVERDUE_NOTIFICATION = f"{ACCOUNT_TYPE}_REPAYMENT_OVERDUE"
CLOSURE_NOTIFICATION = f"{ACCOUNT_TYPE}_CLOSURE"
REPAYMENT_DUE_NOTIFICATION = f"{ACCOUNT_TYPE}_REPAYMENT_DUE"
REPAYMENT_SCHEDULE_NOTIFICATION = f"{ACCOUNT_TYPE}_REPAYMENT_SCHEDULE"
VARIABLE_RATE_FEATURE = variable_interest_rate_interface
EARLY_REPAYMENT_FEES: list[lending_interfaces_EarlyRepaymentFee] = [
    early_repayment_EarlyRepaymentFlatFee,
    early_repayment_EarlyRepaymentPercentageFee,
    overpayment_EarlyRepaymentOverpaymentFee,
]
event_types = [
    *due_amount_calculation_event_types(product_name=ACCOUNT_TYPE),
    *interest_accrual_event_types(product_name=ACCOUNT_TYPE),
    *overdue_event_types(product_name=ACCOUNT_TYPE),
    SmartContractEventType(
        name=CHECK_DELINQUENCY,
        scheduler_tag_ids=[f"{ACCOUNT_TYPE.upper()}_{CHECK_DELINQUENCY}_AST"],
    ),
    *balloon_payments_event_types(product_name=ACCOUNT_TYPE),
]
notification_types = [
    CLOSURE_NOTIFICATION,
    MARK_DELINQUENT_NOTIFICATION,
    REPAYMENT_DUE_NOTIFICATION,
    REPAYMENT_OVERDUE_NOTIFICATION,
    REPAYMENT_SCHEDULE_NOTIFICATION,
]
parameters = [
    Parameter(
        name=PARAM_UPFRONT_FEE,
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("1")),
        level=ParameterLevel.INSTANCE,
        description="A flat fee charged for opening an account.",
        display_name="Upfront Fee",
        default_value=Decimal("0"),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=PARAM_AMORTISE_UPFRONT_FEE,
        shape=common_parameters_BooleanShape,
        level=ParameterLevel.INSTANCE,
        description="If True, upfront fee added to principal. If False, upfront fee deducted from principal.",
        display_name="Amortise Upfront Fee",
        default_value=common_parameters_BooleanValueFalse,
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=PARAM_FIXED_RATE_LOAN,
        level=ParameterLevel.INSTANCE,
        description="Whether it is a fixed rate loan or not, if set to False variable rate will be used.",
        display_name="Fixed Rate Loan",
        shape=common_parameters_BooleanShape,
        default_value=common_parameters_BooleanValueTrue,
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=PARAM_CAPITALISE_LATE_REPAYMENT_FEE,
        shape=common_parameters_BooleanShape,
        level=ParameterLevel.INSTANCE,
        description="If True, late repayment fees are added to principal. If False, they are added to penalties and repayable separately.",
        display_name="Capitalise Late Repayment Fee",
        default_value=common_parameters_BooleanValueFalse,
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=PARAM_INTEREST_ACCRUAL_REST_TYPE,
        shape=UnionShape(
            items=[
                UnionItem(key="daily", display_name="Daily"),
                UnionItem(key="monthly", display_name="Monthly"),
            ]
        ),
        level=ParameterLevel.INSTANCE,
        description="The type of interest rest to apply to the loan (daily or monthly). A monthly rest interest will accrue interest based on the balance at the start of the repayment cycle. Whereas daily will accrue interest on the current outstanding principal balance as of that day.",
        display_name="Interest Rest Type (daily or monthly)",
        update_permission=ParameterUpdatePermission.FIXED,
        default_value=UnionItemValue(key="daily"),
    ),
    Parameter(
        name=PARAM_TOP_UP,
        shape=OptionalShape(shape=common_parameters_BooleanShape),
        description="When set to True, account product version upgrades are treated as a loan top up.",
        display_name="Top Up",
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
        name=PARAM_UPFRONT_FEE_INTERNAL_ACCOUNT,
        shape=AccountIdShape(),
        level=ParameterLevel.TEMPLATE,
        description="Internal account for upfront fee income balance.",
        display_name="Upfront Fee Income Account",
        default_value="UPFRONT_FEE_INCOME",
    ),
    Parameter(
        name=PARAM_ACCRUE_ON_DUE_PRINCIPAL,
        shape=common_parameters_BooleanShape,
        level=ParameterLevel.TEMPLATE,
        description="Allows interest accrual on due principal. If true, "
                    "interest is accrued on remaining principal and any due principal, "
                    "else interest is only accrued on remaining principal. Note, any overdue principal "
                    "is handledseparately.",
        display_name="Accrue Interest On Due Principal",
        default_value=common_parameters_BooleanValueFalse,
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
        name=PARAM_LATE_REPAYMENT_FEE,
        shape=NumberShape(min_value=0),
        level=ParameterLevel.TEMPLATE,
        description="Fee to be charged as a result of late repayment.",
        display_name="Late Repayment Fee",
        default_value=Decimal("25"),
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
        name=PARAM_PENALTY_INTEREST_RECEIVED_ACCOUNT,
        shape=AccountIdShape(),
        level=ParameterLevel.TEMPLATE,
        description="Internal account for penalty interest received balance.",
        display_name="Penalty Interest Received Account",
        default_value="PENALTY_INTEREST_RECEIVED",
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
        name=PARAM_AMORTISATION_METHOD,
        shape=UnionShape(
            items=[
                UnionItem(key="declining_principal", display_name="Declining Principal"),
                UnionItem(key="flat_interest", display_name="Flat Interest"),
                UnionItem(key="rule_of_78", display_name="Rule of 78"),
                UnionItem(key="interest_only", display_name="Interest Only"),
                UnionItem(key="no_repayment", display_name="No Repayment"),
                UnionItem(
                    key="minimum_repayment_with_balloon_payment",
                    display_name="Minimum Repayment with Balloon Payment",
                ),
            ]
        ),
        level=ParameterLevel.TEMPLATE,
        description="Options are: 1. Declining Principal, interest is calculated on a declining balance. 2. Flat Interest, interest is pre-determined at the start of the loan and distributed evenly across the loan term.3. Rule of 78, this is a flat interest loan where the interest is distributed across the term in accordance with the rule of 78. 4. Interest Only, interest is calculated on a declining balance but only interest is to be paid off each month, principal is paid off as a balloon payment at the end of the loan term.5. No Repayment, interest is calculated on a declining balance but no payments are due throughout the loan, principal and accrued interest are paid off as a balloon payment at the end of the loan term.6. Minimum Repayment with Balloon Payment, either pay a fixed (reduced) emi each monthand pay any remaining principal and accrued interest at the end of the loan, or pay a fixed balloon payment at the end of the loan and pay a reduced emi each month.",
        display_name="Amortisation Method",
        default_value=UnionItemValue(key="declining_principal"),
    ),
    Parameter(
        name=PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST,
        shape=UnionShape(
            items=[
                UnionItem(key="daily", display_name="Daily"),
                UnionItem(key="monthly", display_name="Monthly"),
                UnionItem(key="no_capitalisation", display_name="No Capitalisation"),
            ]
        ),
        level=ParameterLevel.TEMPLATE,
        description="Used for no_repayment amortised loans only.Determines whether interest accrued is capitalised or not.If daily, accrued interest added to principal daily. If monthly, accrued interest added to principal monthly.If no_capitalisation then accrued interest is not added to principal.",
        display_name="Capitalise Penalty Interest",
        default_value=UnionItemValue(key="no_capitalisation"),
    ),
    Parameter(
        name=PARAM_DELINQUENCY_FLAG,
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        description="Flag definition id to be used for account delinquency.",
        display_name="Account Delinquency Flag",
        default_value=dumps([DEFAULT_DELINQUENCY_FLAG]),
    ),
    *derived_params_all_parameters,
    *disbursement_parameters,
    *due_amount_calculation_schedule_parameters,
    due_amount_calculation_next_repayment_date_parameter,
    emi_equated_instalment_amount_parameter,
    *interest_accrual_schedule_parameters,
    *interest_accrual_accrual_parameters,
    *interest_accrual_account_parameters,
    interest_application_application_precision_param,
    *interest_application_account_parameters,
    *overdue_schedule_parameters,
    overdue_next_overdue_derived_parameter,
    *overpayment_fee_parameters,
    overpayment_overpayment_impact_preference_param,
    *fixed_parameters,
    *variable_parameters,
    lending_parameters_total_repayment_count_parameter,
    repayment_holiday_due_amount_calculation_blocking_param,
    repayment_holiday_overdue_amount_calculation_blocking_param,
    repayment_holiday_repayment_blocking_param,
    repayment_holiday_penalty_blocking_param,
    repayment_holiday_delinquency_blocking_param,
    repayment_holiday_repayment_holiday_impact_preference_param,
    *early_repayment_parameters,
    *balloon_payments_parameters,
    *interest_capitalisation_parameters,
]


def _get_activation_fee_custom_instruction(
    account_id: str, amount: Decimal, denomination: str, fee_income_account: str
) -> list[CustomInstruction]:
    if amount <= 0:
        return []
    return [
        CustomInstruction(
            postings=[
                Posting(
                    credit=False,
                    amount=amount,
                    denomination=denomination,
                    account_id=account_id,
                    account_address=lending_addresses_PRINCIPAL,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=True,
                    amount=amount,
                    denomination=denomination,
                    account_id=fee_income_account,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
            override_all_restrictions=True,
            instruction_details={
                "description": f"Charge activation fee of {amount}",
                "event": events_ACCOUNT_ACTIVATION,
            },
        )
    ]


def _calculate_disbursement_principal_adjustment(
    vault: Any, balances: Optional[BalanceDefaultDict] = None, denomination: Optional[str] = None
) -> Decimal:
    """
    Signature required for the interface
    """
    return Decimal(utils_get_parameter(vault=vault, name=PARAM_UPFRONT_FEE))


def _get_repayment_schedule_notification(vault: Any) -> AccountNotificationDirective:
    """
    Constructs an AccountNotificationDirective object to serve as a repayment schedule notification
    """
    return AccountNotificationDirective(
        notification_type=REPAYMENT_SCHEDULE_NOTIFICATION,
        notification_details={
            "account_id": vault.account_id,
            "repayment_schedule": dumps(_get_repayment_schedule(vault=vault)),
        },
    )


def _get_repayment_schedule(vault: Any) -> dict[str, list[str]]:
    """
    Gets a repayment schedule based on the loan amortisation type

    Currently, only declining principal amortisation loans are supported.
    If amortisation type is not declining principal, the return object will be empty.

    :param vault:
    :return: the repayment schedule
    """
    if declining_principal_is_declining_principal_loan(
        _get_amortisation_method_parameter(vault=vault)
    ):
        return _get_repayment_schedule_declining_principal(vault=vault)
    return {}


def _get_repayment_schedule_declining_principal(vault: Any) -> dict[str, list[str]]:
    """
    Gets repayment schedule for declining principal loans

    :param vault: Vault object
    :return: expected repayment schedule dict[str, list[str]]
    - k: datetime
    - v: [
            payment number,
            total remaining principal,
            total monthly repayment,
            principal due,
            interest due
        ]
    """
    account_creation_dt = vault.get_account_creation_datetime().replace(hour=0, minute=0, second=0)
    principal = utils_get_parameter(vault=vault, name=disbursement_PARAM_PRINCIPAL)
    total_term = int(
        utils_get_parameter(vault=vault, name=lending_parameters_PARAM_TOTAL_REPAYMENT_COUNT)
    )
    amortise_upfront_fee = utils_get_parameter(
        vault=vault, name=PARAM_AMORTISE_UPFRONT_FEE, is_union=True
    )
    accrual_precision = int(
        utils_get_parameter(vault=vault, name=interest_accrual_PARAM_ACCRUAL_PRECISION)
    )
    application_precision = int(
        utils_get_parameter(vault=vault, name=interest_application_PARAM_APPLICATION_PRECISION)
    )
    interest_rate_feature = _get_interest_rate_feature(vault=vault)
    daily_interest_rate = interest_rate_feature.get_daily_interest_rate(
        vault=vault, effective_datetime=account_creation_dt
    )
    monthly_interest_rate = interest_rate_feature.get_monthly_interest_rate(
        vault=vault, effective_datetime=account_creation_dt
    )
    if amortise_upfront_fee.upper() == "TRUE":
        principal += _calculate_disbursement_principal_adjustment(vault=vault)
    if monthly_interest_rate == 0:
        expected_emi = principal / total_term
    else:
        expected_emi = (
            principal
            * monthly_interest_rate
            * (1 + monthly_interest_rate) ** total_term
            / ((1 + monthly_interest_rate) ** total_term - 1)
        )
    expected_emi = utils_round_decimal(amount=expected_emi, decimal_places=application_precision)
    first_repayment_date = due_amount_calculation_get_first_due_amount_calculation_datetime(
        vault=vault
    )
    additional_payment = Decimal("0")
    if account_creation_dt + relativedelta(months=1) < first_repayment_date:
        additional_days = (
            first_repayment_date - relativedelta(months=1) - account_creation_dt
        ).days
        daily_additional_interest = utils_round_decimal(
            amount=principal * daily_interest_rate, decimal_places=accrual_precision
        )
        additional_interest = daily_additional_interest * additional_days
        additional_payment = utils_round_decimal(
            amount=additional_interest, decimal_places=application_precision
        )
    expected_repayment_schedule: dict[str, list[str]] = {}
    current_iteration_date = account_creation_dt
    for month in range(1, total_term + 1):
        if current_iteration_date == account_creation_dt:
            next_repayment_date = first_repayment_date
        else:
            next_repayment_date = current_iteration_date + relativedelta(months=1)
        delta_days = (next_repayment_date - current_iteration_date).days
        daily_interest_due = utils_round_decimal(
            amount=principal * daily_interest_rate, decimal_places=accrual_precision
        )
        interest_due = utils_round_decimal(
            amount=daily_interest_due * delta_days, decimal_places=application_precision
        )
        principal_due = utils_round_decimal(
            amount=expected_emi + additional_payment - interest_due,
            decimal_places=application_precision,
        )
        principal = utils_round_decimal(
            amount=principal - principal_due, decimal_places=application_precision
        )
        if month == total_term:
            additional_payment = principal
            principal_due += principal
            principal = Decimal("0")
        total_monthly_repayment = expected_emi + additional_payment
        expected_repayment_schedule[str(next_repayment_date)] = [
            str(month),
            str(principal),
            str(total_monthly_repayment),
            str(principal_due),
            str(interest_due),
        ]
        additional_payment = Decimal("0")
        current_iteration_date = next_repayment_date
    return expected_repayment_schedule


def _get_amortisation_feature(vault: Any) -> lending_interfaces_Amortisation:
    """
    Populates and returns an instance of lending_interfaces.Amortisation with the respective
    feature methods, depending on the amortisation method currently active on the account.

    :return amortisation:
    """
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    if rule_of_78_is_rule_of_78_loan(amortisation_method=amortisation_method):
        return rule_of_78_AmortisationFeature
    elif flat_interest_is_flat_interest_loan(amortisation_method=amortisation_method):
        return flat_interest_AmortisationFeature
    elif minimum_repayment_is_minimum_repayment_loan(amortisation_method=amortisation_method):
        return minimum_repayment_AmortisationFeature
    elif interest_only_is_interest_only_loan(amortisation_method=amortisation_method):
        return interest_only_AmortisationFeature
    elif no_repayment_is_no_repayment_loan(amortisation_method=amortisation_method):
        return no_repayment_AmortisationFeature
    else:
        return declining_principal_AmortisationFeature


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
    if repayment_holiday_is_penalty_accrual_blocked(
        vault=vault, effective_datetime=hook_arguments.effective_datetime
    ):
        return []
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_EOD_FETCHER_ID
    ).balances
    denomination = _get_denomination_parameter(vault=vault)
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
        annual_interest_rate += _get_interest_rate_feature(vault=vault).get_annual_interest_rate(
            vault=vault
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


ACCRUED_INTEREST_PENDING_CAPITALISATION = "ACCRUED_INTEREST_PENDING_CAPITALISATION"


def _get_standard_interest_accrual_custom_instructions(
    vault: Any,
    hook_arguments: ScheduledEventHookArguments,
    inflight_postings: list[CustomInstruction],
) -> list[CustomInstruction]:
    accrue_to_pending_capitalisation = repayment_holiday_is_due_amount_calculation_blocked(
        vault=vault, effective_datetime=hook_arguments.effective_datetime
    )
    interest_rate_feature = _get_interest_rate_feature(vault=vault)
    if accrue_to_pending_capitalisation or _no_repayment_to_be_capitalised(vault=vault):
        customer_accrual_address: Optional[str] = ACCRUED_INTEREST_PENDING_CAPITALISATION
        accrual_internal_account: Optional[str] = utils_get_parameter(
            vault=vault, name=interest_capitalisation_PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT
        )
        additional_postings = []
    else:
        customer_accrual_address = None
        accrual_internal_account = None
        additional_postings = overpayment_track_interest_on_expected_principal(
            vault=vault, hook_arguments=hook_arguments, interest_rate_feature=interest_rate_feature
        )
    return (
        interest_accrual_daily_accrual_logic(
            vault=vault,
            hook_arguments=hook_arguments,
            account_type=ACCOUNT_TYPE,
            interest_rate_feature=interest_rate_feature,
            principal_addresses=_get_accrual_principal_addresses(vault=vault),
            inflight_postings=inflight_postings,
            customer_accrual_address=customer_accrual_address,
            accrual_internal_account=accrual_internal_account,
        )
        + additional_postings
    )


def _get_interest_rate_feature(vault: Any) -> lending_interfaces_InterestRate:
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    return (
        FIXED_RATE_FEATURE
        if utils_get_parameter(vault=vault, name=PARAM_FIXED_RATE_LOAN, is_boolean=True)
        or rule_of_78_is_rule_of_78_loan(amortisation_method=amortisation_method)
        or flat_interest_is_flat_interest_loan(amortisation_method=amortisation_method)
        else VARIABLE_RATE_FEATURE
    )


def _get_interest_application_feature(vault: Any) -> lending_interfaces_InterestApplication:
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    if rule_of_78_is_rule_of_78_loan(amortisation_method=amortisation_method):
        return rule_of_78_InterestApplication
    elif flat_interest_is_flat_interest_loan(amortisation_method=amortisation_method):
        return flat_interest_InterestApplication
    else:
        return interest_application_InterestApplication


def _get_loan_reamortisation_conditions(
    vault: Any,
) -> list[lending_interfaces_ReamortisationCondition]:
    amortisation_method = utils_get_parameter(
        vault=vault, name=PARAM_AMORTISATION_METHOD, is_union=True
    )
    return (
        []
        if rule_of_78_is_rule_of_78_loan(amortisation_method=amortisation_method)
        or flat_interest_is_flat_interest_loan(amortisation_method=amortisation_method)
        else [
            overpayment_OverpaymentReamortisationCondition,
            repayment_holiday_ReamortisationConditionWithPreference,
            fixed_FixedReamortisationCondition
            if utils_get_parameter(vault=vault, name=PARAM_FIXED_RATE_LOAN, is_boolean=True)
            else variable_VariableReamortisationCondition,
        ]
    )


def _get_accrual_principal_addresses(vault: Any) -> list[str]:
    principal_address = (
        [MONTHLY_REST_EFFECTIVE_PRINCIPAL]
        if _is_monthly_rest_loan(vault=vault)
        else [lending_addresses_PRINCIPAL]
    )
    return (
        principal_address
        if not utils_get_parameter(vault=vault, name=PARAM_ACCRUE_ON_DUE_PRINCIPAL, is_boolean=True)
        else principal_address + [lending_addresses_PRINCIPAL_DUE]
    )


def _is_monthly_rest_loan(vault: Any) -> bool:
    return (
        utils_get_parameter(
            vault=vault, name=PARAM_INTEREST_ACCRUAL_REST_TYPE, is_union=True
        ).lower()
        == "monthly"
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


def _handle_interest_capitalisation(
    vault: Any,
    effective_datetime: datetime,
    account_type: str,
    balances: Optional[BalanceDefaultDict] = None,
    interest_to_capitalise_address: str = lending_addresses_ACCRUED_INTEREST_PENDING_CAPITALISATION,
) -> list[CustomInstruction]:
    if not _should_handle_interest_capitalisation(
        vault=vault, effective_datetime=effective_datetime
    ):
        return []
    instructions = interest_capitalisation_handle_interest_capitalisation(
        vault=vault,
        account_type=account_type,
        balances=balances,
        interest_to_capitalise_address=interest_to_capitalise_address,
    )
    if _is_monthly_rest_loan(vault=vault):
        monthly_rest_postings = []
        if instructions:
            custom_instruction = instructions[0]
            posting_balances: BalanceDefaultDict = custom_instruction.balances(
                account_id=vault.account_id, tside=Tside.ASSET
            )
            posting_amount = abs(
                utils_balance_at_coordinates(
                    balances=posting_balances,
                    address=lending_addresses_PRINCIPAL,
                    denomination=_get_denomination_parameter(vault=vault),
                )
            )
            monthly_rest_postings = utils_create_postings(
                amount=posting_amount,
                debit_account=vault.account_id,
                credit_account=vault.account_id,
                debit_address=MONTHLY_REST_EFFECTIVE_PRINCIPAL,
                credit_address=addresses_INTERNAL_CONTRA,
            )
            custom_instruction.postings.extend(monthly_rest_postings)
    return instructions


def _get_due_amount_custom_instructions(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> list[CustomInstruction]:
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    denomination = _get_denomination_parameter(vault=vault)
    if _should_execute_balloon_payment_schedule_logic(
        vault=vault,
        effective_datetime=hook_arguments.effective_datetime,
        amortisation_method=amortisation_method,
    ):
        return _get_balloon_payment_custom_instructions(
            vault=vault, hook_arguments=hook_arguments
        ) + [
            CustomInstruction(
                postings=due_amount_calculation_update_due_amount_calculation_counter(
                    account_id=vault.account_id, denomination=denomination
                ),
                instruction_details=utils_standard_instruction_details(
                    description="Updating due amount calculation counter balance",
                    event_type=hook_arguments.event_type,
                    gl_impacted=False,
                    account_type=ACCOUNT_TYPE,
                ),
                override_all_restrictions=True,
            )
        ]
    principal_adjustment_features: list[lending_interfaces_PrincipalAdjustment] = [
        overpayment_OverpaymentPrincipalAdjustment
    ]
    interest_application_feature = _get_interest_application_feature(vault=vault)
    previous_application_datetime = (
        vault.get_last_execution_datetime(
            event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
        )
        or vault.get_account_creation_datetime()
    )
    amortisation_feature = _get_amortisation_feature(vault=vault)
    balances = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    custom_instructions = due_amount_calculation_schedule_logic(
        vault=vault,
        hook_arguments=hook_arguments,
        account_type=ACCOUNT_TYPE,
        interest_application_feature=interest_application_feature,
        reamortisation_condition_features=_get_loan_reamortisation_conditions(vault=vault),
        amortisation_feature=amortisation_feature,
        interest_rate_feature=_get_interest_rate_feature(vault=vault),
        principal_adjustment_features=principal_adjustment_features,
        balances=balances,
        denomination=denomination,
    )
    if _is_monthly_rest_loan(vault=vault):
        custom_instructions = _add_principal_at_cycle_start_tracker_postings(
            vault=vault, due_amount_postings=custom_instructions
        )
    return (
        custom_instructions
        + overpayment_reset_due_amount_calc_overpayment_trackers(vault=vault)
        + overpayment_track_emi_principal_excess(
            vault=vault,
            interest_application_feature=interest_application_feature,
            effective_datetime=hook_arguments.effective_datetime,
            previous_application_datetime=previous_application_datetime,
        )
    )


def _get_balloon_payment_custom_instructions(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> list[CustomInstruction]:
    previous_application_datetime = (
        vault.get_last_execution_datetime(
            event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
        )
        or vault.get_account_creation_datetime()
    )
    denomination = _get_denomination_parameter(vault=vault)
    balances = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    interest_capitalisation_postings: list[CustomInstruction] = []
    merged_balances = BalanceDefaultDict()
    merged_balances += balances
    if _is_no_repayment_loan_interest_to_be_capitalised(
        vault=vault, effective_datetime=hook_arguments.effective_datetime
    ):
        interest_capitalisation_postings = interest_capitalisation_handle_interest_capitalisation(
            vault=vault, account_type=ACCOUNT_TYPE, balances=balances
        )
        for ci in interest_capitalisation_postings:
            merged_balances += ci.balances(account_id=vault.account_id, tside=Tside.ASSET)
    interest_application_feature = _get_interest_application_feature(vault=vault)
    custom_instructions = balloon_payments_schedule_logic(
        vault=vault,
        hook_arguments=hook_arguments,
        account_type=ACCOUNT_TYPE,
        interest_application_feature=interest_application_feature,
        balances=merged_balances,
        denomination=denomination,
    )
    return (
        custom_instructions
        + interest_capitalisation_postings
        + overpayment_reset_due_amount_calc_overpayment_trackers(
            vault=vault, balances=balances, denomination=denomination
        )
        + overpayment_track_emi_principal_excess(
            vault=vault,
            interest_application_feature=interest_application_feature,
            effective_datetime=hook_arguments.effective_datetime,
            previous_application_datetime=previous_application_datetime,
        )
    )


def _should_enable_balloon_payment_schedule(
    vault: Any, effective_datetime: datetime, amortisation_method: str
) -> bool:
    """
    checks whether the balloon payment schedule needs to be enabled on a balloon payment
    loan, the conditions for this are:
        1. The loan is a balloon amortised loan
        and
        2. It is the theoretical final repayment event and the balloon payment delta days is
        greater than zero

    note that for a no_repayment balloon loan the balloon payment schedule is enabled by default
    """
    return (
        balloon_payments_is_balloon_loan(amortisation_method=amortisation_method)
        and _get_amortisation_feature(vault=vault).term_details(
            vault=vault, effective_datetime=effective_datetime, use_expected_term=True
        )[1]
        == 1
        and (balloon_payments__get_balloon_payment_delta_days(vault=vault) > 0)
    )


def _should_execute_balloon_payment_schedule_logic(
    vault: Any, effective_datetime: datetime, amortisation_method: str
) -> bool:
    """ "
    Determines whether the balloon payment schedule logic should be run instead of the
    due_amount_calculation logic during the due_amount_calculation scheduled_event.

    This should return true if the loan is a balloon loan and it is the final due amount event,
    with a balloon payment delta days equal to zero
    """
    if not balloon_payments_is_balloon_loan(amortisation_method=amortisation_method):
        return False
    (_, remaining_term) = _get_amortisation_feature(vault=vault).term_details(
        vault=vault, effective_datetime=effective_datetime, use_expected_term=True
    )
    return (
        remaining_term == 1 and balloon_payments__get_balloon_payment_delta_days(vault=vault) == 0
    )


def _add_principal_at_cycle_start_tracker_postings(
    vault: Any, due_amount_postings: list[CustomInstruction]
) -> list[CustomInstruction]:
    """
    Adds an additional CustomInstruction to the due_amount_postings to update the
    MONTHLY_REST_EFFECTIVE_PRINCIPAL address, used only for monthly rest loans.
    Monthly rest loans accrue interest on the principal balance at repayment cycle start.

    :param vault:
    :param due_amount_postings: list of custom instructions to move balances to due
    :return: custom instructions to move balances to due plus additional custom instruction
    to update tracker address
    """
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination = _get_denomination_parameter(vault=vault)
    existing_principal_tracker_balance = utils_balance_at_coordinates(
        balances=balances, address=MONTHLY_REST_EFFECTIVE_PRINCIPAL, denomination=denomination
    )
    net_reduction_in_principal = _get_net_balance_change_for_address(
        custom_instructions=due_amount_postings,
        account_id=vault.account_id,
        address=lending_addresses_PRINCIPAL,
        denomination=denomination,
    )
    principal_balance = utils_balance_at_coordinates(
        balances=balances, address=lending_addresses_PRINCIPAL, denomination=denomination
    )
    posting_amount = existing_principal_tracker_balance - (
        principal_balance + net_reduction_in_principal
    )
    postings = []
    if posting_amount > Decimal("0"):
        postings.extend(
            utils_create_postings(
                amount=posting_amount,
                debit_account=vault.account_id,
                credit_account=vault.account_id,
                debit_address=addresses_INTERNAL_CONTRA,
                credit_address=MONTHLY_REST_EFFECTIVE_PRINCIPAL,
                denomination=denomination,
            )
        )
    return (
        due_amount_postings
        + [
            CustomInstruction(
                postings=postings,
                override_all_restrictions=True,
                instruction_details={
                    "description": "Update principal at repayment cycle start balance",
                    "event": due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT,
                },
            )
        ]
        if postings
        else due_amount_postings
    )


def _get_net_balance_change_for_address(
    custom_instructions: list[CustomInstruction], account_id: str, address: str, denomination: str
) -> Decimal:
    """
    Returns the net to the balance address from the provided postings
    """
    merged_balances = BalanceDefaultDict()
    for posting_instruction in custom_instructions:
        merged_balances += posting_instruction.balances(account_id=account_id, tside=Tside.ASSET)
    return utils_balance_at_coordinates(
        balances=merged_balances, address=address, denomination=denomination
    )


def _get_repayment_due_notification(
    vault: Any,
    due_amount_custom_instructions: list[CustomInstruction],
    effective_datetime: datetime,
) -> list[AccountNotificationDirective]:
    """
    Generates an account notification for the monthly due amounts

    :param vault: Vault object to obtain parameters
    :param due_amount_custom_instructions: list of due amount calculation custom instructions
    :param effective_datetime: datetime of the due calculation schedule
    :return: list of account notification directives
    """
    merged_balances = BalanceDefaultDict()
    for custom_instruction in due_amount_custom_instructions:
        merged_balances += custom_instruction.balances(
            account_id=vault.account_id, tside=Tside.ASSET
        )
    denomination = _get_denomination_parameter(vault=vault)
    repayment_period = int(utils_get_parameter(vault=vault, name=overdue_PARAM_REPAYMENT_PERIOD))
    total_due_amount = utils_sum_balances(
        balances=merged_balances,
        addresses=[lending_addresses_PRINCIPAL_DUE, lending_addresses_INTEREST_DUE],
        denomination=denomination,
    )
    overdue_date = effective_datetime + relativedelta(days=repayment_period)
    return [
        AccountNotificationDirective(
            notification_type=REPAYMENT_DUE_NOTIFICATION,
            notification_details={
                "account_id": vault.account_id,
                "repayment_amount": str(total_due_amount),
                "overdue_date": str(overdue_date.date()),
            },
        )
    ]


def _update_check_overdue_schedule(
    vault: Any,
    effective_datetime: datetime,
    repayment_period: Optional[int] = None,
    skip: bool = False,
) -> list[UpdateAccountEventTypeDirective]:
    if skip:
        return [UpdateAccountEventTypeDirective(event_type=overdue_CHECK_OVERDUE_EVENT, skip=skip)]
    if repayment_period is None:
        repayment_period = int(
            utils_get_parameter(vault=vault, name=overdue_PARAM_REPAYMENT_PERIOD)
        )
    repayment_period_end = effective_datetime + relativedelta(days=repayment_period)
    return [
        UpdateAccountEventTypeDirective(
            event_type=overdue_CHECK_OVERDUE_EVENT,
            expression=utils_get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=overdue_CHECK_OVERDUE_PREFIX,
                day=repayment_period_end.day,
            ),
            skip=skip,
        )
    ]


def _should_repayment_holiday_increase_tracker_balance(
    vault: Any, effective_datetime: datetime, amortisation_method: str
) -> bool:
    """
    We need to increase the elapsed term tracker address if the repayment holiday preference is to
    increase emi and that the loan is not either a flat interest loan or rule of 78 loan. Otherwise
    a repayment holiday will always increase the term of the loan.
    """
    return repayment_holiday_is_repayment_holiday_impact_increase_emi(
        vault=vault, effective_datetime=effective_datetime
    ) and (
        not (
            rule_of_78_is_rule_of_78_loan(amortisation_method=amortisation_method)
            or flat_interest_is_flat_interest_loan(amortisation_method=amortisation_method)
        )
    )


def _charge_late_repayment_fee(
    vault: Any,
    event_type: str,
    amount: Optional[Decimal] = None,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    """Creates posting instructions to charge a late repayment fee, accounting for capitalisation
    if required.

    :param vault: the vault object for the contract being charged the fee
    :param event_type: the event where the fee is being charged. For use in posting metadata
    :param amount: the fee amount. Defaults to the PARAM_LATE_REPAYMENT_FEE parameter value
    :param denomination: the fee denomination. Defaults to the PARAM_DENOMINATION parameter value
    :return: the posting instructions to charge the fee.
    """
    postings: list[Posting] = []
    amount = amount or Decimal(utils_get_parameter(vault=vault, name=PARAM_LATE_REPAYMENT_FEE))
    denomination = denomination or str(utils_get_parameter(vault=vault, name=PARAM_DENOMINATION))
    late_repayment_fee_income_account: str = utils_get_parameter(
        vault=vault, name=PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT
    )
    customer_account_address = lending_addresses_PENALTIES
    capitalise_late_repayment_fee = utils_get_parameter(
        vault=vault, name=PARAM_CAPITALISE_LATE_REPAYMENT_FEE, is_boolean=True
    )
    if capitalise_late_repayment_fee:
        customer_account_address = lending_addresses_PRINCIPAL
        late_repayment_fee_income_account = utils_get_parameter(
            vault=vault, name=interest_capitalisation_PARAM_CAPITALISED_PENALTIES_RECEIVED_ACCOUNT
        )
        postings += utils_create_postings(
            amount=amount,
            debit_account=vault.account_id,
            credit_account=vault.account_id,
            debit_address=CAPITALISED_PENALTIES_TRACKER,
            credit_address=addresses_INTERNAL_CONTRA,
        )
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
    else:
        return []


def _get_overdue_repayment_notification(
    account_id: str,
    balances: BalanceDefaultDict,
    denomination: str,
    late_repayment_fee: Decimal,
    effective_datetime: datetime,
) -> list[AccountNotificationDirective]:
    late_repayment_amount = _get_late_payment_balance(balances=balances, denomination=denomination)
    return [
        AccountNotificationDirective(
            notification_type=REPAYMENT_OVERDUE_NOTIFICATION,
            notification_details={
                "account_id": account_id,
                "repayment_amount": str(late_repayment_amount),
                "late_repayment_fee": str(late_repayment_fee),
                "overdue_date": str(effective_datetime.date()),
            },
        )
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
    denomination = _get_denomination_parameter(vault=vault)
    balances = (
        balances
        or vault.get_balances_observation(
            fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    )
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


def _handle_due_amount_calculation_day_change(
    vault: Any, effective_datetime: datetime, elapsed_term: int, remaining_term: int
) -> list[UpdateAccountEventTypeDirective]:
    update_event_type_directives: list[UpdateAccountEventTypeDirective] = []
    last_execution_datetime = vault.get_last_execution_datetime(
        event_type=due_amount_calculation_DUE_AMOUNT_CALCULATION_EVENT
    )
    next_due_amount_calculation_datetime = (
        due_amount_calculation_get_next_due_amount_calculation_datetime(
            vault=vault,
            effective_datetime=effective_datetime,
            elapsed_term=elapsed_term,
            remaining_term=remaining_term,
        )
    )
    if (
        last_execution_datetime
        and next_due_amount_calculation_datetime
        != last_execution_datetime + relativedelta(months=1)
    ):
        update_event_type_directives.extend(
            _update_due_amount_calculation_day_schedule(
                vault=vault,
                schedule_start_datetime=next_due_amount_calculation_datetime,
                due_amount_calculation_day=next_due_amount_calculation_datetime.day,
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


def _get_late_payment_balance(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    return utils_sum_balances(
        balances=balances,
        addresses=lending_addresses_LATE_REPAYMENT_ADDRESSES,
        denomination=denomination,
        decimal_places=2,
    )


def _use_expected_term(vault: Any, balances: BalanceDefaultDict, denomination: str) -> bool:
    overpayment_preference = overpayment_get_overpayment_preference_parameter(vault=vault)
    overpayment_balance = utils_balance_at_coordinates(
        balances=balances, address=overpayment_OVERPAYMENT, denomination=denomination
    )
    return not (overpayment_preference == "reduce_term" and overpayment_balance > Decimal(0))


def _get_denomination_parameter(vault: Any) -> str:
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    return denomination


def _get_amortisation_method_parameter(vault: Any) -> str:
    amortisation_method: str = utils_get_parameter(
        vault=vault, name=PARAM_AMORTISATION_METHOD, is_union=True
    )
    return amortisation_method


def _is_interest_adjustment(posting: utils_PostingInstructionTypeAlias) -> bool:
    return utils_str_to_bool(
        posting.instruction_details.get(INSTRUCTION_DETAILS_KEY_INTEREST_ADJUSTMENT, "false")
    )


def _get_interest_to_revert(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    return utils_balance_at_coordinates(
        balances=balances, address=lending_addresses_INTEREST_DUE, denomination=denomination
    )


def _get_posting_amount(
    posting_instruction: utils_PostingInstructionTypeAlias,
    denomination: str,
    address: str = DEFAULT_ADDRESS,
) -> Decimal:
    posting_balances = posting_instruction.balances()
    return utils_get_available_balance(
        balances=posting_balances, denomination=denomination, address=address
    )


def _process_payment(
    vault: Any, hook_arguments: PostPostingHookArguments, denomination: str
) -> tuple[list[CustomInstruction], list[AccountNotificationDirective]]:
    """
    Processes a payment received from the borrower, paying off the balance in different addresses
    in the correct order
    """
    account_notification_directives: list[AccountNotificationDirective] = []
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    custom_instructions = payments_generate_repayment_postings(
        vault=vault,
        hook_arguments=hook_arguments,
        overpayment_features=[
            lending_interfaces_Overpayment(handle_overpayment=_handle_overpayment)
        ],
        early_repayment_fees=EARLY_REPAYMENT_FEES,
    )
    if close_loan_does_repayment_fully_repay_loan(
        repayment_posting_instructions=custom_instructions,
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        payment_addresses=lending_addresses_ALL_OUTSTANDING,
    ):
        account_notification_directives.append(
            AccountNotificationDirective(
                notification_type=CLOSURE_NOTIFICATION,
                notification_details={"account_id": str(vault.account_id)},
            )
        )
    return (custom_instructions, account_notification_directives)


def _handle_overpayment(
    vault: Any, overpayment_amount: Decimal, denomination: str, balances: BalanceDefaultDict
) -> list[Posting]:
    """
    Handles a customer overpayment by first charging an overpayment fee (if applicable) and then
    handles the remaining overpayment amount by creating postings to principal and accrued interest

    :param vault: Vault object for the account receiving the overpayment
    :param overpayment_amount: the amount to go towards principal and accrued interest
    :param denomination: denomination of the repayment / loan being repaid
    :param balances: balances at the point of overpayment
    :return: the corresponding postings
    """
    postings: list[Posting] = []
    overpayment_fee_rate: Decimal = utils_get_parameter(
        vault=vault, name=overpayment_PARAM_OVERPAYMENT_FEE_RATE
    )
    overpayment_fee_income_account: str = utils_get_parameter(
        vault=vault, name=overpayment_PARAM_OVERPAYMENT_FEE_INCOME_ACCOUNT
    )
    overpayment_fee = min(
        overpayment_get_overpayment_fee(
            principal_repaid=overpayment_amount,
            overpayment_fee_rate=overpayment_fee_rate,
            precision=2,
        ),
        overpayment_get_max_overpayment_fee(
            fee_rate=overpayment_fee_rate, balances=balances, denomination=denomination, precision=2
        ),
    )
    postings.extend(
        overpayment_get_overpayment_fee_postings(
            overpayment_fee=overpayment_fee,
            denomination=denomination,
            customer_account_id=vault.account_id,
            customer_account_address=DEFAULT_ADDRESS,
            internal_account=overpayment_fee_income_account,
        )
    )
    overpayment_amount -= overpayment_fee
    postings.extend(
        overpayment_handle_overpayment(
            vault=vault,
            overpayment_amount=overpayment_amount,
            denomination=denomination,
            balances=balances,
        )
    )
    return postings


def _get_residual_cleanup_postings(
    balances: BalanceDefaultDict, account_id: str, denomination: str
) -> list[Posting]:
    postings: list[Posting] = []
    addresses_to_clear = [
        CAPITALISED_INTEREST_TRACKER,
        CAPITALISED_PENALTIES_TRACKER,
        MONTHLY_REST_EFFECTIVE_PRINCIPAL,
    ]
    for address in addresses_to_clear:
        address_balance = utils_balance_at_coordinates(
            balances=balances, address=address, denomination=denomination
        )
        if address_balance > Decimal("0"):
            postings += utils_create_postings(
                amount=address_balance,
                debit_account=account_id,
                credit_account=account_id,
                debit_address=addresses_INTERNAL_CONTRA,
                credit_address=address,
                denomination=denomination,
            )
    return postings


def _no_repayment_to_be_capitalised(vault: Any) -> bool:
    capitalise_no_repayment_loan: str = utils_get_parameter(
        vault=vault, name=PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST, is_union=True
    ).upper()
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    return (
        no_repayment_is_no_repayment_loan(amortisation_method)
        and capitalise_no_repayment_loan != "NO_CAPITALISATION"
    )


def _is_no_repayment_loan_interest_to_be_capitalised(
    vault: Any, effective_datetime: datetime
) -> bool:
    """
    Determine whether interest needs to be capitalised for a no_repayment
    amortised loan. Interest should be capitalised if:
    the loan is a no_repayment amortised loan AND capitalise_no_repayment_accrued_interest
    is True, if the above condition is met we capitalise interest under the following
    scenarios:
        1. is monthly capitalisation AND effective_date.day is equal to
        account_creation_datetime().day() (therefore we capitalise the interest monthly)
        2. is daily capitalisation (therefore we capitalise the interest daily)

    """
    capitalise_no_repayment_loan: str = utils_get_parameter(
        vault=vault, name=PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST, is_union=True
    ).upper()
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    loan_start_datetime = vault.get_account_creation_datetime()
    loan_start_day = loan_start_datetime.day
    valid_day_to_capitalise = True
    if capitalise_no_repayment_loan == "MONTHLY":
        last_day_in_current_month = monthrange(effective_datetime.year, effective_datetime.month)[1]
        valid_day_to_capitalise = (
            loan_start_day >= 29
            and last_day_in_current_month < loan_start_day
            and (effective_datetime.day == last_day_in_current_month)
            or effective_datetime.day == loan_start_day
        )
    return (
        no_repayment_is_no_repayment_loan(amortisation_method)
        and capitalise_no_repayment_loan != "NO_CAPITALISATION"
        and (valid_day_to_capitalise is True)
    )


def _should_handle_interest_capitalisation(
    vault: Any, effective_datetime: datetime, is_penalty_interest_capitalisation: bool = False
) -> bool:
    """
    Determine whether to do interest capitalisation
    """
    if no_repayment_is_no_repayment_loan(
        amortisation_method=_get_amortisation_method_parameter(vault=vault)
    ):
        return _is_no_repayment_loan_interest_to_be_capitalised(
            vault=vault, effective_datetime=effective_datetime
        )
    return (
        not repayment_holiday_is_penalty_accrual_blocked(
            vault=vault, effective_datetime=effective_datetime
        )
        or is_penalty_interest_capitalisation
    )
