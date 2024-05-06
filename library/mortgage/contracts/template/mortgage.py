# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import ROUND_HALF_UP, Decimal
from json import dumps
from typing import Optional

# features
import library.features.common.common_parameters as common_parameters
import library.features.v4.common.fees as fees
import library.features.common.fetchers as fetchers
import library.features.v4.common.interest_accrual_common as interest_accrual_common
import library.features.v4.common.utils as utils
import library.features.v4.lending.amortisations.declining_principal as declining_principal
import library.features.v4.lending.close_loan as close_loan
import library.features.v4.lending.derived_params as derived_params
import library.features.v4.lending.disbursement as disbursement
import library.features.v4.lending.due_amount_calculation as due_amount_calculation
import library.features.v4.lending.emi as emi
import library.features.v4.lending.interest_accrual as interest_accrual
import library.features.v4.lending.interest_application as interest_application
import library.features.v4.lending.interest_capitalisation as interest_capitalisation
import library.features.v4.lending.interest_rate.fixed as fixed_rate
import library.features.v4.lending.interest_rate.fixed_to_variable as fixed_to_variable
import library.features.v4.lending.interest_rate.variable as variable_rate
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces
import library.features.v4.lending.lending_parameters as lending_parameters
import library.features.v4.lending.overdue as overdue
import library.features.v4.lending.overpayment as overpayment
import library.features.v4.lending.overpayment_allowance as overpayment_allowance
import library.features.v4.lending.payments as payments
import library.features.v4.lending.repayment_holiday as repayment_holiday
import library.features.v4.lending.term_helpers as term_helpers

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AccountIdShape,
    AccountNotificationDirective,
    ActivationHookArguments,
    ActivationHookResult,
    BalanceDefaultDict,
    ConversionHookArguments,
    ConversionHookResult,
    CustomInstruction,
    DeactivationHookArguments,
    DeactivationHookResult,
    DenominationShape,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    NumberShape,
    OptionalShape,
    OptionalValue,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Phase,
    Posting,
    PostingInstructionsDirective,
    PostParameterChangeHookArguments,
    PostParameterChangeHookResult,
    PostPostingHookArguments,
    PostPostingHookResult,
    PreParameterChangeHookArguments,
    PreParameterChangeHookResult,
    PrePostingHookArguments,
    PrePostingHookResult,
    Rejection,
    RejectionReason,
    ScheduledEvent,
    ScheduledEventHookArguments,
    ScheduledEventHookResult,
    ScheduleSkip,
    SmartContractEventType,
    StringShape,
    Tside,
    UpdateAccountEventTypeDirective,
    fetch_account_data,
    requires,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

api = "4.0.0"
version = "5.0.1"
display_name = "Mortgage"
summary = "Fixed and variable rate mortgage with configuration repayment options."
tside = Tside.ASSET

# this can be amended to whichever other currencies as needed
supported_denominations = ["GBP"]

ACCOUNT_TYPE = "MORTGAGE"

# addresses
CAPITALISED_INTEREST_TRACKER = "CAPITALISED_INTEREST_TRACKER"
ACCRUED_INTEREST_PENDING_CAPITALISATION = "ACCRUED_INTEREST_PENDING_CAPITALISATION"
ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION = "ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION"

# Constants
INSTRUCTION_DETAILS_KEY_FEE = "fee"
INSTRUCTION_DETAILS_KEY_INTEREST_ADJUSTMENT = "interest_adjustment"
INSTRUCTION_DETAILS_KEY_EARLY_REPAYMENT = "early_repayment"
INTEREST_APPLICATION_FEATURE = interest_application.InterestApplication

# Events
CHECK_DELINQUENCY = "CHECK_DELINQUENCY"

event_types = [
    *interest_accrual.event_types(ACCOUNT_TYPE),
    *due_amount_calculation.event_types(ACCOUNT_TYPE),
    *overpayment_allowance.event_types(ACCOUNT_TYPE),
    SmartContractEventType(
        name=CHECK_DELINQUENCY,
        scheduler_tag_ids=[f"{ACCOUNT_TYPE}_{CHECK_DELINQUENCY}_AST"],
    ),
]

# Data fetchers
data_fetchers = [
    fetchers.EFFECTIVE_OBSERVATION_FETCHER,
    fetchers.LIVE_BALANCES_BOF,
    *interest_accrual.data_fetchers,
    interest_application.accrued_interest_eff_fetcher,
    interest_application.accrued_interest_one_month_ago_fetcher,
    overpayment.overpayment_tracker_eff_fetcher,
    overpayment.expected_interest_eod_fetcher,
    overpayment_allowance.one_year_overpayment_allowance_interval_fetcher,
    overpayment_allowance.eod_overpayment_allowance_fetcher,
    overpayment_allowance.one_year_overpayment_allowance_fetcher,
]

# Notifications
MARK_DELINQUENT_NOTIFICATION = f"{ACCOUNT_TYPE}_MARK_DELINQUENT"
CLOSURE_NOTIFICATION = f"{ACCOUNT_TYPE}_CLOSURE"
notification_types = [MARK_DELINQUENT_NOTIFICATION, CLOSURE_NOTIFICATION]

# Parameters
PARAM_DENOMINATION = "denomination"
PARAM_GRACE_PERIOD = "grace_period"
PARAM_INTEREST_ONLY_TERM = "interest_only_term"
PARAM_PRODUCT_SWITCH = "product_switch"
PARAM_LATE_REPAYMENT_FEE = "late_repayment_fee"

## Penalty Parameters
PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST = "penalty_compounds_overdue_interest"
PARAM_PENALTY_INTEREST_RATE = "penalty_interest_rate"
PARAM_PENALTY_INCLUDES_BASE_RATE = "penalty_includes_base_rate"

## Flag Parameters
PARAM_DELINQUENCY_FLAG = "delinquency_flag"

## Internal Account Parameters
PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "accrued_interest_receivable_account"
PARAM_INTEREST_RECEIVED_ACCOUNT = "interest_received_account"
PARAM_PENALTY_INTEREST_RECEIVED_ACCOUNT = "penalty_interest_received_account"
PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT = "early_repayment_fee_income_account"
PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "late_repayment_fee_income_account"

## Schedule Parameters
CHECK_DELINQUENCY_PREFIX = "check_delinquency"
PARAM_CHECK_DELINQUENCY_HOUR = f"{CHECK_DELINQUENCY_PREFIX}_hour"
PARAM_CHECK_DELINQUENCY_MINUTE = f"{CHECK_DELINQUENCY_PREFIX}_minute"
PARAM_CHECK_DELINQUENCY_SECOND = f"{CHECK_DELINQUENCY_PREFIX}_second"

# Derived Parameters
PARAM_IS_INTEREST_ONLY_TERM = "is_interest_only_term"
PARAM_OUTSTANDING_PAYMENTS = "outstanding_payments"
PARAM_DERIVED_EARLY_REPAYMENT_FEE = "derived_early_repayment_fee"
PARAM_EARLY_REPAYMENT_FEE = "early_repayment_fee"
PARAM_TOTAL_EARLY_REPAYMENT_FEE = "total_early_repayment_fee"

parameters = [
    # Instance Parameters
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
        shape=OptionalShape(shape=common_parameters.BooleanShape),
        description="When set to True, account product version upgrades are treated as "
        "product switches.",
        display_name="Product Switch",
        level=ParameterLevel.INSTANCE,
        default_value=OptionalValue(common_parameters.BooleanValueFalse),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    # Template Parameters
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
        description="The number of days after which the account becomes delinquent "
        "if the overdue amounts and penalties are not paid in full.",
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
        shape=common_parameters.BooleanShape,
        level=ParameterLevel.TEMPLATE,
        description="If True, include both overdue interest and overdue principal in the "
        "penalty interest calculation. If False, only include overdue principal.",
        display_name="Penalty Compounds Overdue Interest",
        default_value=common_parameters.BooleanValueFalse,
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
        shape=common_parameters.BooleanShape,
        level=ParameterLevel.TEMPLATE,
        description="Whether to add base interest rate on top of penalty interest rate.",
        display_name="Penalty Includes Base Rate",
        default_value=common_parameters.BooleanValueTrue,
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
    # Derived Parameters
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
        description="Fee applied if the mortgage is completely repaid early. "
        "If this value is negative, the fee is calculated as the "
        "overpayment allowance fee percentage * the total remaining principal. "
        "If this value is non-negative, it represents a flat fee to be applied.",
        display_name="Early Repayment Fee",
        default_value=Decimal(0),
    ),
    Parameter(
        name=PARAM_DERIVED_EARLY_REPAYMENT_FEE,
        shape=NumberShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="Fee applied if the mortgage is completely repaid early. "
        "Calculated from the early_repayment_fee parameter.",
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
    derived_params.total_outstanding_debt_parameter,
    derived_params.total_remaining_principal_parameter,
    derived_params.remaining_term_parameter,
    # Flag definitions
    Parameter(
        name=PARAM_DELINQUENCY_FLAG,
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        description="Flag definition id to be used for account delinquency.",
        display_name="Account Delinquency Flag",
        default_value=dumps(["ACCOUNT_DELINQUENT"]),
    ),
    # Internal accounts
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
    # Feature Parameters
    *disbursement.parameters,
    *due_amount_calculation.schedule_parameters,
    due_amount_calculation.next_repayment_date_parameter,
    *fixed_rate.parameters,
    *fixed_to_variable.parameters,
    *interest_accrual.account_parameters,
    *interest_accrual.accrual_parameters,
    *interest_accrual.schedule_parameters,
    interest_application.application_precision_param,
    overpayment.overpayment_impact_preference_param,
    *overpayment_allowance.derived_parameters,
    *overpayment_allowance.allowance_fee_parameters,
    *overpayment_allowance.allowance_schedule_time_parameters,
    *variable_rate.parameters,
    lending_parameters.total_repayment_count_parameter,
    repayment_holiday.delinquency_blocking_param,
    repayment_holiday.repayment_blocking_param,
    repayment_holiday.due_amount_calculation_blocking_param,
    repayment_holiday.overdue_amount_calculation_blocking_param,
    repayment_holiday.penalty_blocking_param,
    interest_capitalisation.capitalised_interest_receivable_account_param,
    interest_capitalisation.capitalised_interest_received_account_param,
    interest_capitalisation.capitalise_penalty_interest_param,
]


@requires(parameters=True)
def activation_hook(
    vault: SmartContractVault, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    effective_datetime: datetime = hook_arguments.effective_datetime
    scheduled_events: dict[str, ScheduledEvent] = {}
    posting_instructions: list[CustomInstruction] = []

    schedules_start_datetime = effective_datetime.replace(
        hour=0, minute=0, second=0
    ) + relativedelta(days=1)

    scheduled_events.update(
        interest_accrual.scheduled_events(vault, start_datetime=schedules_start_datetime)
    )
    scheduled_events.update(
        due_amount_calculation.scheduled_events(vault, account_opening_datetime=effective_datetime)
    )
    scheduled_events.update(
        overpayment_allowance.scheduled_events(
            vault=vault, allowance_period_start_datetime=effective_datetime
        )
    )

    scheduled_events[CHECK_DELINQUENCY] = ScheduledEvent(
        skip=True,
        start_datetime=schedules_start_datetime,
        expression=utils.get_schedule_expression_from_parameters(
            vault, parameter_prefix=CHECK_DELINQUENCY_PREFIX
        ),
    )

    # principal disbursement
    principal: Decimal = utils.get_parameter(vault=vault, name=disbursement.PARAM_PRINCIPAL)
    deposit_account: str = utils.get_parameter(vault=vault, name=disbursement.PARAM_DEPOSIT_ACCOUNT)
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    principal_custom_instruction = disbursement.get_disbursement_custom_instruction(
        account_id=vault.account_id,
        deposit_account_id=deposit_account,
        principal=principal,
        denomination=denomination,
    )
    posting_instructions.extend(principal_custom_instruction)

    # initialise overpayment allowance amount
    posting_instructions += (
        overpayment_allowance.initialise_overpayment_allowance_from_principal_amount(
            vault=vault, principal=principal, denomination=denomination
        )
    )

    # emi disbursement
    if int(utils.get_parameter(vault=vault, name=PARAM_INTEREST_ONLY_TERM)) == 0:
        amortise_custom_instruction = emi.amortise(
            vault=vault,
            effective_datetime=effective_datetime,
            amortisation_feature=declining_principal.AmortisationFeature,
            interest_calculation_feature=fixed_to_variable.InterestRate,
        )
        posting_instructions += amortise_custom_instruction

    return ActivationHookResult(
        posting_instructions_directives=[
            PostingInstructionsDirective(
                posting_instructions=posting_instructions,
                value_datetime=effective_datetime,
            )
        ],
        scheduled_events_return_value=scheduled_events,
    )


@requires(
    event_type=interest_accrual.ACCRUAL_EVENT,
    parameters=True,
    flags=True,
)
@fetch_account_data(
    event_type=interest_accrual.ACCRUAL_EVENT,
    balances=[fetchers.EOD_FETCHER_ID, overpayment.EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID],
)
@requires(
    event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
    flags=True,
    last_execution_datetime=[due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT],
    parameters=True,
)
@fetch_account_data(
    event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
    balances=[
        fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID,
        interest_application.ACCRUED_INTEREST_EFF_FETCHER_ID,
        interest_application.ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID,
        overpayment.OVERPAYMENT_TRACKER_EFF_FETCHER_ID,
    ],
)
@requires(event_type=overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_EVENT, parameters=True)
@fetch_account_data(
    event_type=overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_EVENT,
    balances=[
        overpayment_allowance.EOD_OVERPAYMENT_ALLOWANCE_FETCHER_ID,
        overpayment_allowance.ONE_YEAR_OVERPAYMENT_ALLOWANCE_FETCHER_ID,
    ],
)
@requires(
    event_type=CHECK_DELINQUENCY,
    flags=True,
    parameters=True,
)
@fetch_account_data(
    event_type=CHECK_DELINQUENCY,
    balances=[
        fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID,
    ],
)
def scheduled_event_hook(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    event_type = hook_arguments.event_type
    effective_datetime = hook_arguments.effective_datetime

    custom_instructions: list[CustomInstruction] = []
    update_event_type_directives: list[UpdateAccountEventTypeDirective] = []
    account_notification_directives: list[AccountNotificationDirective] = []

    if event_type == interest_accrual.ACCRUAL_EVENT:
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

    elif event_type == due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT:
        # the mortgage marks due balances as overdue at the next due amount calculation, instead of
        # having a dedicated schedule like other loan variants
        if not repayment_holiday.is_overdue_amount_calculation_blocked(
            vault=vault, effective_datetime=effective_datetime
        ):
            overdue_custom_instructions, _ = overdue.schedule_logic(
                vault=vault, hook_arguments=hook_arguments
            )
            if overdue_custom_instructions:
                custom_instructions.extend(overdue_custom_instructions)
                custom_instructions.extend(_charge_late_repayment_fee(vault, event_type))

                mark_delinquent_notifications, delinquency_event_updates = _handle_delinquency(
                    vault=vault, hook_arguments=hook_arguments, is_delinquency_schedule_event=False
                )
                account_notification_directives.extend(mark_delinquent_notifications)
                update_event_type_directives.extend(delinquency_event_updates)

        custom_instructions.extend(
            _get_due_amount_custom_instructions(vault=vault, hook_arguments=hook_arguments)
        )
        custom_instructions.extend(
            interest_capitalisation.handle_penalty_interest_capitalisation(
                vault=vault, account_type=ACCOUNT_TYPE
            )
        )

    elif event_type == overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_EVENT:
        custom_instructions.extend(
            overpayment_allowance.handle_allowance_usage(vault=vault, account_type=ACCOUNT_TYPE)
        )

    elif event_type == CHECK_DELINQUENCY:
        mark_delinquent_notifications, delinquency_event_updates = _handle_delinquency(
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


@requires(
    parameters=True,
    # TODO: remove last execution datetime when implementing INC-8179
    last_execution_datetime=[
        due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
        overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_EVENT,
    ],
)
@fetch_account_data(
    balances=[
        fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID,
        overpayment_allowance.ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL_FETCHER_ID,
    ]
)
def derived_parameter_hook(
    vault: SmartContractVault, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    effective_datetime: datetime = hook_arguments.effective_datetime

    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination: str = utils.get_parameter(vault, name=PARAM_DENOMINATION)

    total_outstanding_debt = derived_params.get_total_outstanding_debt(
        balances=balances, denomination=denomination
    )

    is_fixed_interest = str(
        fixed_to_variable.is_within_fixed_rate_term(
            vault=vault,
            effective_datetime=effective_datetime,
            balances=balances,
            denomination=denomination,
        )
    )

    total_remaining_principal = _get_outstanding_principal(balances, denomination)

    outstanding_payments = _get_outstanding_payments_amount(balances, denomination)

    next_repayment_date = _get_actual_next_repayment_dateeter(vault, effective_datetime)

    _, remaining_term = declining_principal.term_details(
        vault=vault,
        effective_datetime=effective_datetime,
        use_expected_term=_use_expected_term(
            vault=vault, balances=balances, denomination=denomination
        ),
        interest_rate=fixed_to_variable.InterestRate,
        balances=balances,
        denomination=denomination,
    )

    is_interest_only_term = str(
        _is_within_interest_only_term(vault=vault, balances=balances, denomination=denomination)
    )

    original_allowance, used_allowance = overpayment_allowance.get_overpayment_allowance_status(
        vault=vault, effective_datetime=effective_datetime
    )
    # we let this go negative so customers know they'll be charged a fee
    remaining_allowance = original_allowance - used_allowance

    overpayment_allowance_fee_percentage: Decimal = utils.get_parameter(
        vault=vault, name=overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE
    )
    overpayment_allowance_fee = overpayment_allowance.get_allowance_usage_fee(
        allowance=original_allowance,
        used_allowance=used_allowance,
        overpayment_allowance_fee_percentage=overpayment_allowance_fee_percentage,
    )

    early_repayment_fee = _get_early_repayment_fee(
        vault=vault, balances=balances, denomination=denomination
    )

    early_repayment_overpayment_allowance_fee = (
        overpayment_allowance.get_overpayment_allowance_fee_for_early_repayment(
            vault=vault, denomination=denomination, balances=balances
        )
    )

    parameters: dict[str, utils.ParameterValueTypeAlias] = {
        derived_params.PARAM_TOTAL_OUTSTANDING_DEBT: total_outstanding_debt,
        fixed_to_variable.PARAM_IS_FIXED_INTEREST: is_fixed_interest,
        PARAM_IS_INTEREST_ONLY_TERM: is_interest_only_term,
        derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL: total_remaining_principal,
        PARAM_OUTSTANDING_PAYMENTS: outstanding_payments,
        due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE: next_repayment_date,
        derived_params.PARAM_REMAINING_TERM: remaining_term,
        overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_REMAINING: remaining_allowance,
        overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_USED: used_allowance,
        overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE: overpayment_allowance_fee,
        PARAM_DERIVED_EARLY_REPAYMENT_FEE: early_repayment_fee,
        PARAM_TOTAL_EARLY_REPAYMENT_FEE: early_repayment_overpayment_allowance_fee
        + early_repayment_fee,
    }

    return DerivedParameterHookResult(parameters_return_value=parameters)


@requires(parameters=True, flags=True)
@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    posting_instructions: utils.PostingInstructionListAlias = hook_arguments.posting_instructions

    if utils.is_force_override(posting_instructions):
        return None

    if posting_rejection := utils.validate_single_hard_settlement_or_transfer(
        posting_instructions=posting_instructions
    ):
        return PrePostingHookResult(rejection=posting_rejection)

    denomination: str = utils.get_parameter(vault, name=PARAM_DENOMINATION)
    if denomination_rejection := utils.validate_denomination(posting_instructions, [denomination]):
        return PrePostingHookResult(rejection=denomination_rejection)

    # we have validated this is a single hard settlement
    posting = posting_instructions[0]
    posting_amount = _get_posting_net_amount(posting_instruction=posting, denomination=denomination)

    if posting_amount < Decimal("0"):
        # this is a repayment
        if repayment_rejection := repayment_holiday.reject_repayment(
            vault=vault, effective_datetime=hook_arguments.effective_datetime
        ):
            return PrePostingHookResult(rejection=repayment_rejection)

        balances: BalanceDefaultDict = vault.get_balances_observation(
            fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
        ).balances
        outstanding_debt = derived_params.get_total_outstanding_debt(
            balances=balances, denomination=denomination
        )

        early_repayment_fee = _get_early_repayment_fee(
            vault=vault, balances=balances, denomination=denomination
        )

        overpayment_allowance_fee = (
            overpayment_allowance.get_overpayment_allowance_fee_for_early_repayment(
                vault=vault,
                denomination=denomination,
                balances=balances,
            )
        )
        total_early_repayment_amount = (
            outstanding_debt + overpayment_allowance_fee + early_repayment_fee
        )

        principal_amount = utils.balance_at_coordinates(
            balances=balances, address=lending_addresses.PRINCIPAL, denomination=denomination
        )

        # use abs() here since the posting amount is -ve
        if (
            abs(posting_amount) >= outstanding_debt
            and principal_amount > Decimal("0")
            and abs(posting_amount) != total_early_repayment_amount
        ):
            return PrePostingHookResult(
                rejection=Rejection(
                    message="Cannot pay more than is owed. To repay the full amount of the "
                    f"mortgage - including fees - a posting for {total_early_repayment_amount} "
                    f"{denomination} must be made.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
    elif (
        posting_amount > Decimal("0")
        and not utils.str_to_bool(
            posting.instruction_details.get(INSTRUCTION_DETAILS_KEY_FEE, "false")
        )
        and not utils.str_to_bool(
            posting.instruction_details.get(INSTRUCTION_DETAILS_KEY_INTEREST_ADJUSTMENT, "false")
        )
    ):
        # this is a debit
        return PrePostingHookResult(
            rejection=Rejection(
                message="Debiting is not allowed from this account.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

    return None


@requires(parameters=True, flags=True)
@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
def post_posting_hook(
    vault: SmartContractVault, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    posting_instructions: utils.PostingInstructionListAlias = hook_arguments.posting_instructions
    if utils.is_force_override(posting_instructions):
        return None

    effective_datetime = hook_arguments.effective_datetime

    # only single posting is accepted
    posting = posting_instructions[0]

    denomination: str = utils.get_parameter(vault, name=PARAM_DENOMINATION)

    # only consider DEFAULT_ADDRESS since posting is hard settlement
    posting_balance_delta: Decimal = utils.balance_at_coordinates(
        balances=posting.balances(), denomination=denomination
    )

    if posting_balance_delta > 0:
        is_interest_adjustment = _is_interest_adjustment(posting)
        # debits only accepted when instruction details contains either fee/interest_adjustment
        balance_destination = (
            lending_addresses.INTEREST_DUE
            if is_interest_adjustment
            else lending_addresses.PENALTIES
        )
        custom_instructions = _move_balance_custom_instructions(
            amount=posting_balance_delta,
            denomination=denomination,
            vault_account=vault.account_id,
            balance_address=balance_destination,
        )

        if is_interest_adjustment:
            balances: BalanceDefaultDict = vault.get_balances_observation(
                fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
            ).balances
            interest_to_revert = _get_interest_to_revert(balances, denomination)
            interest_received_account: str = utils.get_parameter(
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
        custom_instructions, account_notification_directives = _process_payment(
            vault=vault,
            hook_arguments=hook_arguments,
            denomination=denomination,
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


@requires(
    flags=True,
    last_execution_datetime=[due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT],
    parameters=True,
)
def pre_parameter_change_hook(
    vault: SmartContractVault, hook_arguments: PreParameterChangeHookArguments
) -> Optional[PreParameterChangeHookResult]:
    updated_parameter_values = hook_arguments.updated_parameter_values
    if due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY in updated_parameter_values:
        if repayment_holiday.is_due_amount_calculation_blocked(
            vault=vault, effective_datetime=hook_arguments.effective_datetime
        ):
            return PreParameterChangeHookResult(
                rejection=Rejection(
                    message=f"The {due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY} "
                    "parameter cannot be updated during a repayment holiday.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
        if rejection := due_amount_calculation.validate_due_amount_calculation_day_change(vault):
            return PreParameterChangeHookResult(rejection=rejection)

    return None


@requires(
    parameters=True,
    last_execution_datetime=[due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT],
)
def post_parameter_change_hook(
    vault: SmartContractVault, hook_arguments: PostParameterChangeHookArguments
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


@requires(
    last_execution_datetime=[overpayment_allowance.CHECK_OVERPAYMENT_ALLOWANCE_EVENT],
    parameters=True,
)
@fetch_account_data(
    balances=[
        fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID,
        overpayment_allowance.ONE_YEAR_OVERPAYMENT_ALLOWANCE_INTERVAL_FETCHER_ID,
    ]
)
def conversion_hook(
    vault: SmartContractVault, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    # by default we must preserve all schedules
    effective_datetime = hook_arguments.effective_datetime
    scheduled_events = hook_arguments.existing_schedules
    posting_instructions: list[CustomInstruction] = []

    if utils.get_parameter(
        vault=vault,
        name=PARAM_PRODUCT_SWITCH,
        is_optional=True,
        is_boolean=True,
    ):
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
        denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)

        # we must reset trackers first so we can account for this in the reamortisation
        posting_instructions += close_loan.net_balances(
            balances=balances,
            denomination=denomination,
            account_id=vault.account_id,
            residual_cleanup_features=[
                overpayment.OverpaymentResidualCleanupFeature,
                overpayment_allowance.OverpaymentAllowanceResidualCleanupFeature,
                due_amount_calculation.DueAmountCalculationResidualCleanupFeature,
                lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=_get_residual_cleanup_postings
                ),
            ],
        )

        # We don't need to consider reamortisation triggers as the product switch is a trigger
        # itself, but it's possible the new mortgage doesn't need amortising immediately
        if int(utils.get_parameter(vault=vault, name=PARAM_INTEREST_ONLY_TERM)) == 0:
            # the tracker updates will affect elapsed_term and therefore amortisation, so must
            # be accounted for
            # create a new BalanceDefaultDict to avoid mutating balances
            inflight_balances = BalanceDefaultDict(mapping=balances)
            for posting_instruction in posting_instructions:
                inflight_balances += posting_instruction.balances(
                    account_id=vault.account_id, tside=Tside.ASSET
                )

            posting_instructions += emi.amortise(
                vault=vault,
                effective_datetime=hook_arguments.effective_datetime,
                amortisation_feature=declining_principal.AmortisationFeature,
                principal_amount=utils.balance_at_coordinates(
                    balances=inflight_balances,
                    address=lending_addresses.PRINCIPAL,
                    denomination=denomination,
                ),
                interest_calculation_feature=fixed_to_variable.InterestRate,
                balances=inflight_balances,
                event="PRODUCT_SWITCH",
            )

        posting_instructions += overpayment_allowance.handle_allowance_usage_adhoc(
            vault=vault,
            account_type=ACCOUNT_TYPE,
            effective_datetime=effective_datetime,
        )

        scheduled_events.update(
            overpayment_allowance.update_scheduled_event(
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
@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
def deactivation_hook(
    vault: SmartContractVault, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    denomination: str = utils.get_parameter(vault, name=PARAM_DENOMINATION)
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances

    if deactivation_rejection := close_loan.reject_closure_when_outstanding_debt(
        balances=balances,
        denomination=denomination,
        debt_addresses=lending_addresses.ALL_OUTSTANDING,
    ):
        return DeactivationHookResult(rejection=deactivation_rejection)

    posting_instructions = close_loan.net_balances(
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        residual_cleanup_features=[
            overpayment.OverpaymentResidualCleanupFeature,
            overpayment_allowance.OverpaymentAllowanceResidualCleanupFeature,
            due_amount_calculation.DueAmountCalculationResidualCleanupFeature,
            lending_interfaces.ResidualCleanup(
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


## Hook helpers
# Scheduled hook helpers
def _handle_delinquency(
    vault: SmartContractVault,
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

    grace_period = int(utils.get_parameter(vault=vault, name=PARAM_GRACE_PERIOD))

    # the delinquency schedule needing to be updated when:
    # 1. executing the delinquency schedule OR the overdue schedule when grace_period == 0
    # => schedule updated to now + 1 month and skipped
    # 2. executing overdue schedule with +ve grace period => schedule updated to now + grace_period
    evaluate_delinquency_status = grace_period == 0 or is_delinquency_schedule_event

    if evaluate_delinquency_status:
        next_schedule_datetime = effective_datetime + relativedelta(months=1)
        delinquent_schedule_updates.extend(
            _update_delinquency_schedule(
                vault=vault,
                next_schedule_datetime=next_schedule_datetime,
                skip_schedule=True,
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
                vault=vault,
                next_schedule_datetime=grace_period_end,
                skip_schedule=False,
            )
        )

    return mark_delinquent_notifications, delinquent_schedule_updates


def _mark_account_delinquent(
    vault: SmartContractVault,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
) -> list[AccountNotificationDirective]:
    """
    Establish if account should be placed into delinquency

    :param vault: Vault object for the account that might be delinquent. Used to
    access balances, account_id, flags
    :param effective_datetime: datetime
    :return: list[AccountNotificationDirective]
    """
    if repayment_holiday.is_delinquency_blocked(
        vault=vault, effective_datetime=effective_datetime
    ) or utils.is_flag_in_list_applied(
        vault=vault, parameter_name=PARAM_DELINQUENCY_FLAG, effective_datetime=effective_datetime
    ):
        return []

    denomination: str = utils.get_parameter(vault, name=PARAM_DENOMINATION)
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances

    if _get_late_payment_balance(
        balances=balances, denomination=denomination  # type: ignore
    ) > Decimal("0"):
        return [
            AccountNotificationDirective(
                notification_type=MARK_DELINQUENT_NOTIFICATION,
                notification_details={"account_id": str(vault.account_id)},
            )
        ]

    return []


def _update_delinquency_schedule(
    vault: SmartContractVault, next_schedule_datetime: datetime, skip_schedule: bool
) -> list[UpdateAccountEventTypeDirective]:
    return [
        UpdateAccountEventTypeDirective(
            event_type=CHECK_DELINQUENCY,
            expression=utils.get_schedule_expression_from_parameters(
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
    vault: SmartContractVault,
    hook_arguments: ScheduledEventHookArguments,
    inflight_postings: list[CustomInstruction],
) -> list[CustomInstruction]:
    accrue_to_pending_capitalisation = repayment_holiday.is_due_amount_calculation_blocked(
        vault=vault, effective_datetime=hook_arguments.effective_datetime
    )

    if accrue_to_pending_capitalisation:
        # the types here handle the optional values in the else branch
        customer_accrual_address: Optional[str] = ACCRUED_INTEREST_PENDING_CAPITALISATION
        accrual_internal_account: Optional[str] = utils.get_parameter(
            vault=vault, name=interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT
        )
        # interest on expected principal is compared to regular accruals to determine emi principal
        # excess, so it is not needed if we are making capitalised accruals
        additional_postings = []
    else:
        # this will let the feature use its default non-capitalised values
        customer_accrual_address = None
        accrual_internal_account = None
        additional_postings = overpayment.track_interest_on_expected_principal(
            vault=vault,
            hook_arguments=hook_arguments,
            interest_rate_feature=fixed_to_variable.InterestRate,
        )

    return (
        interest_accrual.daily_accrual_logic(
            vault=vault,
            hook_arguments=hook_arguments,
            account_type=ACCOUNT_TYPE,
            interest_rate_feature=fixed_to_variable.InterestRate,
            principal_addresses=[lending_addresses.PRINCIPAL],
            inflight_postings=inflight_postings,
            customer_accrual_address=customer_accrual_address,
            accrual_internal_account=accrual_internal_account,
        )
        + additional_postings
    )


def _handle_interest_capitalisation(
    vault: SmartContractVault,
    effective_datetime: datetime,
    account_type: str,
    balances: Optional[BalanceDefaultDict] = None,
    interest_to_capitalise_address: str = lending_addresses.ACCRUED_INTEREST_PENDING_CAPITALISATION,
) -> list[CustomInstruction]:
    if _should_handle_interest_capitalisation(vault=vault, effective_datetime=effective_datetime):
        return interest_capitalisation.handle_interest_capitalisation(
            vault=vault,
            account_type=account_type,
            balances=balances,
            interest_to_capitalise_address=interest_to_capitalise_address,
        )
    else:
        return []


def _get_penalty_interest_accrual_custom_instruction(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
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
    if repayment_holiday.is_penalty_accrual_blocked(
        vault=vault, effective_datetime=effective_datetime
    ):
        return []

    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.EOD_FETCHER_ID
    ).balances
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    penalty_compounds_overdue_interest: bool = utils.get_parameter(
        vault=vault,
        name=PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST,
        is_boolean=True,
    )
    days_in_year: str = utils.get_parameter(
        vault=vault, name=interest_accrual.PARAM_DAYS_IN_YEAR, is_union=True
    )
    annual_interest_rate: Decimal = utils.get_parameter(
        vault=vault, name=PARAM_PENALTY_INTEREST_RATE
    )
    if utils.get_parameter(
        vault=vault,
        name=PARAM_PENALTY_INCLUDES_BASE_RATE,
        is_boolean=True,
    ):
        annual_interest_rate += fixed_to_variable.get_annual_interest_rate(
            vault=vault, effective_datetime=effective_datetime, balances=balances
        )

    if interest_capitalisation.is_capitalise_penalty_interest(vault=vault):
        precision: int = utils.get_parameter(
            vault=vault, name=interest_accrual.PARAM_ACCRUAL_PRECISION
        )
        customer_address = ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION
        internal_account = utils.get_parameter(
            vault=vault, name=interest_capitalisation.PARAM_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT
        )
    else:
        # Although we call it accrual, we immediately apply normal penalty interest
        # and should round accordingly
        precision = utils.get_parameter(
            vault=vault, name=interest_application.PARAM_APPLICATION_PRECISION
        )
        customer_address = lending_addresses.PENALTIES
        internal_account = utils.get_parameter(
            vault=vault, name=PARAM_PENALTY_INTEREST_RECEIVED_ACCOUNT
        )

    overdue_capital = _get_overdue_capital(
        balances=balances,
        denomination=denomination,
        include_overdue_interest=penalty_compounds_overdue_interest,
    )

    return interest_accrual_common.daily_accrual(
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
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
) -> list[CustomInstruction]:
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)

    if repayment_holiday.is_due_amount_calculation_blocked(
        vault=vault, effective_datetime=hook_arguments.effective_datetime
    ):
        # Increase the elapsed term, which is normally inside due_amount_calculation's
        # schedule_logic(), so that reamortisation at the end of the holiday accounts for the
        # due amount calculations that should have happened during the repayment holiday
        return [
            CustomInstruction(
                postings=due_amount_calculation.update_due_amount_calculation_counter(
                    account_id=vault.account_id, denomination=denomination
                ),
                instruction_details=utils.standard_instruction_details(
                    description="Updating due amount calculation counter",
                    event_type=hook_arguments.event_type,
                    gl_impacted=False,
                    account_type=ACCOUNT_TYPE,
                ),
                override_all_restrictions=True,
            )
        ]

    balances = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    previous_application_datetime = (
        vault.get_last_execution_datetime(
            event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
        )
        or vault.get_account_creation_datetime()
    )

    if _is_within_interest_only_term(vault=vault):
        # during the interest only term we should not be re-amortising, technically we have not
        # yet amortised at all and this will be done on the first due_calculation event after the
        # interest only term is finished
        reamortisation_condition_features: list[lending_interfaces.ReamortisationCondition] = []
    else:
        reamortisation_condition_features = [
            overpayment.OverpaymentReamortisationCondition,
            repayment_holiday.ReamortisationConditionWithoutPreference,
            fixed_to_variable.ReamortisationCondition,
            lending_interfaces.ReamortisationCondition(
                should_trigger_reamortisation=_is_end_of_interest_only_term
            ),
        ]

    return (
        due_amount_calculation.schedule_logic(
            vault=vault,
            hook_arguments=hook_arguments,
            account_type=ACCOUNT_TYPE,
            interest_application_feature=INTEREST_APPLICATION_FEATURE,
            reamortisation_condition_features=reamortisation_condition_features,
            amortisation_feature=declining_principal.AmortisationFeature,
            interest_rate_feature=fixed_to_variable.InterestRate,
            principal_adjustment_features=[overpayment.OverpaymentPrincipalAdjustment],
            balances=balances,
            denomination=denomination,
        )
        + overpayment.reset_due_amount_calc_overpayment_trackers(vault=vault)
        + overpayment.track_emi_principal_excess(
            vault=vault,
            interest_application_feature=INTEREST_APPLICATION_FEATURE,
            effective_datetime=hook_arguments.effective_datetime,
            previous_application_datetime=previous_application_datetime,
        )
    )


def _charge_late_repayment_fee(
    vault: SmartContractVault,
    event_type: str,
) -> list[CustomInstruction]:
    """Creates posting instructions to charge a late repayment fee, accounting for capitalisation
    if required.

    :param vault: the vault object for the contract being charged the fee
    :param event_type: the event where the fee is being charged. For use in posting metadata
    :return: the posting instructions to charge the fee.
    """

    postings: list[Posting] = []
    amount = Decimal(utils.get_parameter(vault=vault, name=PARAM_LATE_REPAYMENT_FEE))
    denomination = str(utils.get_parameter(vault=vault, name=PARAM_DENOMINATION))
    late_repayment_fee_income_account: str = utils.get_parameter(
        vault=vault, name=PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT
    )
    customer_account_address = lending_addresses.PENALTIES

    postings += fees.fee_postings(
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
                instruction_details=utils.standard_instruction_details(
                    description="Charge late repayment fee",
                    event_type=event_type,
                    gl_impacted=True,
                    account_type=ACCOUNT_TYPE,
                ),
            )
        ]
    return []


def _use_expected_term(
    vault: SmartContractVault, balances: BalanceDefaultDict, denomination: str
) -> bool:
    overpayment_preference = overpayment.get_overpayment_preference_parameter(vault=vault)
    overpayment_balance = utils.balance_at_coordinates(
        balances=balances, address=overpayment.OVERPAYMENT, denomination=denomination
    )
    # only overpayments that reduce term currently require calculated remaining term. Otherwise
    # we should always use expected term
    return not (overpayment_preference == "reduce_term" and overpayment_balance > Decimal(0))


# Deactivation hook helpers
def _get_residual_cleanup_postings(
    balances: BalanceDefaultDict, account_id: str, denomination: str
) -> list[Posting]:
    postings: list[Posting] = []

    addresses_to_clear = [CAPITALISED_INTEREST_TRACKER]

    for address in addresses_to_clear:
        address_balance = utils.balance_at_coordinates(
            balances=balances, address=address, denomination=denomination
        )

        if address_balance > Decimal("0"):
            postings += utils.create_postings(
                amount=address_balance,
                debit_account=account_id,
                credit_account=account_id,
                debit_address=lending_addresses.INTERNAL_CONTRA,
                credit_address=address,
                denomination=denomination,
            )

    return postings


# Post posting hook helpers
def _move_balance_custom_instructions(
    amount: Decimal, denomination: str, vault_account: str, balance_address: str
) -> list[CustomInstruction]:
    # TODO(sas): think of a better name here e.g. rebalance_posting_custom_instructions
    postings: list[Posting] = utils.create_postings(
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
    vault: SmartContractVault,
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
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    custom_instructions = payments.generate_repayment_postings(
        vault=vault,
        hook_arguments=hook_arguments,
        overpayment_features=[
            overpayment.OverpaymentFeature,
            overpayment_allowance.OverpaymentAllowanceFeature,
        ],
    )

    if close_loan.does_repayment_fully_repay_loan(
        repayment_posting_instructions=custom_instructions,
        balances=balances,  # type: ignore
        denomination=denomination,
        account_id=vault.account_id,
        payment_addresses=lending_addresses.ALL_OUTSTANDING,
    ):
        custom_instructions.extend(
            interest_capitalisation.handle_overpayments_to_penalties_pending_capitalisation(
                vault=vault,
                denomination=denomination,
                balances=balances,
            )
        )
        early_repayment_fee_income_account: str = utils.get_parameter(
            vault=vault, name=PARAM_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT
        )
        early_repayment_fee_custom_instructions = _handle_early_repayment_fee(
            repayment_posting_instructions=custom_instructions,
            balances=balances,  # type: ignore
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

    return custom_instructions, account_notification_directives


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
    # determine the net balance changes as a result of the repayment postings
    merged_balances = BalanceDefaultDict()
    merged_balances += balances
    for repayment_posting_instruction in repayment_posting_instructions:
        merged_balances += repayment_posting_instruction.balances(
            account_id=account_id, tside=Tside.ASSET
        )

    # Since the mortgage has been fully repaid, anything left in the
    # DEFAULT balance after accounting for the repayment posting instructions
    # must be the early repayment fee(s).
    early_repayment_fees = utils.balance_at_coordinates(
        balances=merged_balances, denomination=denomination
    )

    early_repayment_custom_instructions: list[CustomInstruction] = []
    if early_repayment_fees != Decimal("0"):
        early_repayment_custom_instructions.append(
            CustomInstruction(
                postings=fees.fee_postings(
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
    return utils.balance_at_coordinates(
        balances=balances,
        address=lending_addresses.INTEREST_DUE,
        denomination=denomination,
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
    postings = utils.create_postings(
        amount=amount,
        debit_account=interest_received_account,
        credit_account=vault_account,
        debit_address=DEFAULT_ADDRESS,
        credit_address=lending_addresses.INTEREST_DUE,
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


# Post parameter change hook helpers
def _handle_due_amount_calculation_day_change(
    vault: SmartContractVault, hook_arguments: PostParameterChangeHookArguments
) -> list[UpdateAccountEventTypeDirective]:
    update_event_type_directives: list[UpdateAccountEventTypeDirective] = []

    effective_datetime = hook_arguments.effective_datetime
    updated_parameter_values: dict[
        str, utils.ParameterValueTypeAlias
    ] = hook_arguments.updated_parameter_values

    if new_due_amount_calculation_day := updated_parameter_values.get(
        due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
    ):
        last_execution_datetime = vault.get_last_execution_datetime(
            event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
        )
        next_due_amount_calculation_datetime = _calculate_next_due_amount_calculation_datetime(
            vault,
            effective_datetime,
            last_execution_datetime,
            int(new_due_amount_calculation_day),  # type: ignore
        )
        update_event_type_directives.extend(
            _update_due_amount_calculation_day_schedule(
                vault=vault,
                schedule_start_datetime=next_due_amount_calculation_datetime,
                due_amount_calculation_day=int(new_due_amount_calculation_day),  # type: ignore
            )
        )
    return update_event_type_directives


def _update_due_amount_calculation_day_schedule(
    vault: SmartContractVault, schedule_start_datetime: datetime, due_amount_calculation_day: int
) -> list[UpdateAccountEventTypeDirective]:
    return [
        UpdateAccountEventTypeDirective(
            event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
            schedule_method=utils.get_end_of_month_schedule_from_parameters(
                vault=vault,
                parameter_prefix=due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX,
                day=due_amount_calculation_day,
            ),
            # we can't delay the start datetime in the Directive, so skipping until
            # 1 second before the updated start datetime to ensure we don't run a
            # monthly event before we anticipate
            skip=ScheduleSkip(end=schedule_start_datetime - relativedelta(seconds=1)),
        )
    ]


# Derived parameter helpers
def _get_actual_next_repayment_dateeter(
    vault: SmartContractVault, effective_datetime: datetime
) -> datetime:
    # TODO: INC-8179 this needs updating to get the relative last execution datetime
    # as derived parameters can be requested in the past, but
    # vault.get_last_execution_datetime() only returns the most recent
    # execution timestamp irrespective of the hook effective datetime
    last_execution_datetime = vault.get_last_execution_datetime(
        event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
    )
    due_amount_calculation_day = int(
        utils.get_parameter(
            vault,
            name=due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY,
            at_datetime=effective_datetime,
        )
    )
    return _calculate_next_due_amount_calculation_datetime(
        vault,
        effective_datetime,
        last_execution_datetime,
        due_amount_calculation_day=due_amount_calculation_day,
    )


## Balance helpers
def _get_late_payment_balance(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    return utils.sum_balances(
        balances=balances,
        addresses=lending_addresses.LATE_REPAYMENT_ADDRESSES,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        phase=Phase.COMMITTED,
    )


def _get_outstanding_principal(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    return utils.balance_at_coordinates(
        balances=balances,
        address=lending_addresses.PRINCIPAL,
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
    return utils.sum_balances(
        balances=balances,
        addresses=lending_addresses.REPAYMENT_HIERARCHY,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        phase=Phase.COMMITTED,
    )


def _get_posting_net_amount(
    posting_instruction: utils.PostingInstructionTypeAlias,
    denomination: str,
    address: str = DEFAULT_ADDRESS,
) -> Decimal:
    posting_balances = posting_instruction.balances()

    return utils.get_available_balance(
        balances=posting_balances, denomination=denomination, address=address
    )


def _get_overdue_capital(
    balances: BalanceDefaultDict, denomination: str, include_overdue_interest: bool
) -> Decimal:
    address_list = (
        lending_addresses.OVERDUE_ADDRESSES
        if include_overdue_interest
        else [lending_addresses.PRINCIPAL_OVERDUE]
    )

    return utils.sum_balances(
        balances=balances, addresses=address_list, denomination=denomination, decimal_places=2
    )


def _get_early_repayment_fee(
    vault: SmartContractVault, balances: BalanceDefaultDict, denomination: str
) -> Decimal:
    early_repayment_fee: Decimal = utils.get_parameter(vault=vault, name=PARAM_EARLY_REPAYMENT_FEE)

    if early_repayment_fee < 0:
        overpayment_allowance_fee_percentage: Decimal = utils.get_parameter(
            vault=vault, name=overpayment_allowance.PARAM_OVERPAYMENT_ALLOWANCE_FEE_PERCENTAGE
        )
        total_remaining_principal = _get_outstanding_principal(
            balances=balances, denomination=denomination
        )

        early_repayment_fee = utils.round_decimal(
            amount=overpayment_allowance_fee_percentage * total_remaining_principal,
            decimal_places=2,
        )

    return early_repayment_fee


## Posting helpers
def _is_interest_adjustment(posting: utils.PostingInstructionTypeAlias) -> bool:
    return utils.str_to_bool(
        posting.instruction_details.get(INSTRUCTION_DETAILS_KEY_INTEREST_ADJUSTMENT, "false")
    )


## Time calculation helpers
def _is_within_interest_only_term(
    vault: SmartContractVault,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> bool:
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)

    elapsed_term = term_helpers.calculate_elapsed_term(balances, denomination)

    return int(utils.get_parameter(vault=vault, name=PARAM_INTEREST_ONLY_TERM)) > elapsed_term


def _is_end_of_interest_only_term(
    vault: SmartContractVault,
    period_start_datetime: datetime,
    period_end_datetime: datetime,
    elapsed_term: int,
) -> bool:
    """
    This signature is required for the lending interface
    """
    interest_only_term = int(utils.get_parameter(vault=vault, name=PARAM_INTEREST_ONLY_TERM))
    if interest_only_term == 0:
        return False

    return elapsed_term == interest_only_term


def _calculate_next_due_amount_calculation_datetime(
    vault: SmartContractVault,
    effective_datetime: datetime,
    last_execution_datetime: Optional[datetime],
    due_amount_calculation_day: int,
) -> datetime:
    repayment_hour, repayment_minute, repayment_second = utils.get_schedule_time_from_parameters(
        vault, parameter_prefix=due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX
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
    vault: SmartContractVault,
    effective_datetime: datetime,
    is_penalty_interest_capitalisation: bool = False,
) -> bool:
    """
    Determine whether to do interest capitalisation
    """
    return (
        not repayment_holiday.is_due_amount_calculation_blocked(
            vault=vault, effective_datetime=effective_datetime
        )
        or is_penalty_interest_capitalisation
    )
