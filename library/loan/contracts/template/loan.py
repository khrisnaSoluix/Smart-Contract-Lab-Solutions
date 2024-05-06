# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from calendar import monthrange
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import ROUND_HALF_UP, Decimal
from json import dumps
from typing import Optional

# features
import library.features.v4.common.addresses as common_addresses
import library.features.common.common_parameters as common_parameters
import library.features.v4.common.events as events
import library.features.v4.common.fees as fees
import library.features.common.fetchers as fetchers
import library.features.v4.common.interest_accrual_common as interest_accrual_common
import library.features.v4.common.utils as utils
import library.features.v4.lending.amortisations.declining_principal as declining_principal
import library.features.v4.lending.amortisations.flat_interest as flat_interest
import library.features.v4.lending.amortisations.interest_only as interest_only
import library.features.v4.lending.amortisations.minimum_repayment as minimum_repayment
import library.features.v4.lending.amortisations.no_repayment as no_repayment
import library.features.v4.lending.amortisations.rule_of_78 as rule_of_78
import library.features.v4.lending.balloon_payments as balloon_payments
import library.features.v4.lending.close_loan as close_loan
import library.features.v4.lending.derived_params as derived_params
import library.features.v4.lending.disbursement as disbursement
import library.features.v4.lending.due_amount_calculation as due_amount_calculation
import library.features.v4.lending.early_repayment as early_repayment
import library.features.v4.lending.emi as emi
import library.features.v4.lending.interest_accrual as interest_accrual
import library.features.v4.lending.interest_application as interest_application
import library.features.v4.lending.interest_capitalisation as interest_capitalisation
import library.features.v4.lending.interest_rate.fixed as fixed_rate
import library.features.v4.lending.interest_rate.variable as variable_rate
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces
import library.features.v4.lending.lending_parameters as lending_parameters
import library.features.v4.lending.lending_utils as lending_utils
import library.features.v4.lending.overdue as overdue
import library.features.v4.lending.overpayment as overpayment
import library.features.v4.lending.payments as payments
import library.features.v4.lending.repayment_holiday as repayment_holiday

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
    UnionItem,
    UnionItemValue,
    UnionShape,
    UpdateAccountEventTypeDirective,
    fetch_account_data,
    requires,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

api = "4.0.0"
version = "5.0.2"
display_name = "Loan"
summary = "A new car, holiday or wedding? Our loan offers competitive rates and flexible terms."
tside = Tside.ASSET

# this can be amended to whichever other currencies as needed
supported_denominations = ["GBP"]

data_fetchers = [
    fetchers.EFFECTIVE_OBSERVATION_FETCHER,
    fetchers.LIVE_BALANCES_BOF,
    *interest_accrual.data_fetchers,
    interest_application.accrued_interest_eff_fetcher,
    interest_application.accrued_interest_one_month_ago_fetcher,
    overpayment.overpayment_tracker_eff_fetcher,
    overpayment.expected_interest_eod_fetcher,
]

# addresses
MONTHLY_REST_EFFECTIVE_PRINCIPAL = "MONTHLY_REST_EFFECTIVE_PRINCIPAL"
ACCRUED_INTEREST_PENDING_CAPITALISATION = "ACCRUED_INTEREST_PENDING_CAPITALISATION"
CAPITALISED_INTEREST_TRACKER = "CAPITALISED_INTEREST_TRACKER"
ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION = "ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION"
CAPITALISED_PENALTIES_TRACKER = "CAPITALISED_PENALTIES_TRACKER"


# parameters
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

# flag parameters
PARAM_DELINQUENCY_FLAG = "delinquency_flag"
# penalty parameters
PARAM_PENALTY_COMPOUNDS_OVERDUE_INTEREST = "penalty_compounds_overdue_interest"
PARAM_CAPITALISE_LATE_REPAYMENT_FEE = "capitalise_late_repayment_fee"
PARAM_PENALTY_INTEREST_RATE = "penalty_interest_rate"
PARAM_PENALTY_INCLUDES_BASE_RATE = "penalty_includes_base_rate"


# internal account parameters
PARAM_PENALTY_INTEREST_RECEIVED_ACCOUNT = "penalty_interest_received_account"
PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "late_repayment_fee_income_account"
PARAM_UPFRONT_FEE_INTERNAL_ACCOUNT = "upfront_fee_income_account"

# other constants
ACCOUNT_TYPE = "LOAN"
CHECK_DELINQUENCY = "CHECK_DELINQUENCY"
CHECK_DELINQUENCY_PREFIX = "check_delinquency"
DEFAULT_DELINQUENCY_FLAG = "ACCOUNT_DELINQUENT"
FIXED_RATE_FEATURE = fixed_rate.interest_rate_interface
INSTRUCTION_DETAILS_KEY_INTEREST_ADJUSTMENT = "interest_adjustment"
INSTRUCTION_DETAILS_KEY_FEE = "fee"
LOAN_TOP_UP = "LOAN_TOP_UP"
MARK_DELINQUENT_NOTIFICATION = f"{ACCOUNT_TYPE}_MARK_DELINQUENT"
REPAYMENT_OVERDUE_NOTIFICATION = f"{ACCOUNT_TYPE}_REPAYMENT_OVERDUE"
CLOSURE_NOTIFICATION = f"{ACCOUNT_TYPE}_CLOSURE"
REPAYMENT_DUE_NOTIFICATION = f"{ACCOUNT_TYPE}_REPAYMENT_DUE"
REPAYMENT_SCHEDULE_NOTIFICATION = f"{ACCOUNT_TYPE}_REPAYMENT_SCHEDULE"

VARIABLE_RATE_FEATURE = variable_rate.interest_rate_interface

EARLY_REPAYMENT_FEES: list[lending_interfaces.EarlyRepaymentFee] = [
    early_repayment.EarlyRepaymentFlatFee,
    early_repayment.EarlyRepaymentPercentageFee,
    overpayment.EarlyRepaymentOverpaymentFee,
]


event_types = [
    *due_amount_calculation.event_types(product_name=ACCOUNT_TYPE),
    *interest_accrual.event_types(product_name=ACCOUNT_TYPE),
    *overdue.event_types(product_name=ACCOUNT_TYPE),
    SmartContractEventType(
        name=CHECK_DELINQUENCY,
        scheduler_tag_ids=[f"{ACCOUNT_TYPE.upper()}_{CHECK_DELINQUENCY}_AST"],
    ),
    *balloon_payments.event_types(product_name=ACCOUNT_TYPE),
]

notification_types = [
    CLOSURE_NOTIFICATION,
    MARK_DELINQUENT_NOTIFICATION,
    REPAYMENT_DUE_NOTIFICATION,
    REPAYMENT_OVERDUE_NOTIFICATION,
    REPAYMENT_SCHEDULE_NOTIFICATION,
]

parameters = [
    # Instance Parameters
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
        shape=common_parameters.BooleanShape,
        level=ParameterLevel.INSTANCE,
        description="If True, upfront fee added to principal."
        " If False, upfront fee deducted from principal.",
        display_name="Amortise Upfront Fee",
        default_value=common_parameters.BooleanValueFalse,
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=PARAM_FIXED_RATE_LOAN,
        level=ParameterLevel.INSTANCE,
        description="Whether it is a fixed rate loan or not, if set to False variable "
        "rate will be used.",
        display_name="Fixed Rate Loan",
        shape=common_parameters.BooleanShape,
        default_value=common_parameters.BooleanValueTrue,
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=PARAM_CAPITALISE_LATE_REPAYMENT_FEE,
        shape=common_parameters.BooleanShape,
        level=ParameterLevel.INSTANCE,
        description="If True, late repayment fees are added to principal."
        " If False, they are added to penalties and repayable separately.",
        display_name="Capitalise Late Repayment Fee",
        default_value=common_parameters.BooleanValueFalse,
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
        description="The type of interest rest to apply to the loan (daily "
        "or monthly). A monthly rest interest will accrue interest based on "
        "the balance at the start of the repayment cycle. Whereas daily will "
        "accrue interest on the current outstanding principal balance as of that day.",
        display_name="Interest Rest Type (daily or monthly)",
        update_permission=ParameterUpdatePermission.FIXED,
        default_value=UnionItemValue(key="daily"),
    ),
    Parameter(
        name=PARAM_TOP_UP,
        shape=OptionalShape(shape=common_parameters.BooleanShape),
        description="When set to True, account product version upgrades are treated as "
        "a loan top up.",
        display_name="Top Up",
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
        name=PARAM_UPFRONT_FEE_INTERNAL_ACCOUNT,
        shape=AccountIdShape(),
        level=ParameterLevel.TEMPLATE,
        description="Internal account for upfront fee income balance.",
        display_name="Upfront Fee Income Account",
        default_value="UPFRONT_FEE_INCOME",
    ),
    Parameter(
        name=PARAM_ACCRUE_ON_DUE_PRINCIPAL,
        shape=common_parameters.BooleanShape,
        level=ParameterLevel.TEMPLATE,
        description="Allows interest accrual on due principal. "
        "If true, interest is accrued on remaining principal "
        "and any due principal, else interest is only accrued on "
        "remaining principal. Note, any overdue principal is handled"
        "separately.",
        display_name="Accrue Interest On Due Principal",
        default_value=common_parameters.BooleanValueFalse,
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
        shape=common_parameters.BooleanShape,
        level=ParameterLevel.TEMPLATE,
        description="Whether to add base interest rate on top of penalty interest rate.",
        display_name="Penalty Includes Base Rate",
        default_value=common_parameters.BooleanValueTrue,
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
        description="Options are: "
        "1. Declining Principal, interest is calculated on a declining balance. "
        "2. Flat Interest, interest is pre-determined at the start of the loan "
        "and distributed evenly across the loan term."
        "3. Rule of 78, this is a flat interest loan where the interest is distributed "
        "across the term in accordance with the rule of 78. "
        "4. Interest Only, interest is calculated on a declining balance but only interest "
        "is to be paid off each month, principal is paid off as a balloon payment at the "
        "end of the loan term."
        "5. No Repayment, interest is calculated on a declining balance but no payments "
        "are due throughout the loan, principal and accrued interest are paid off as a "
        "balloon payment at the end of the loan term."
        "6. Minimum Repayment with Balloon Payment, either pay a fixed (reduced) emi each month"
        "and pay any remaining principal and accrued interest at the end of the loan, or "
        "pay a fixed balloon payment at the end of the loan and pay a reduced emi each month.",
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
            ],
        ),
        level=ParameterLevel.TEMPLATE,
        description="Used for no_repayment amortised loans only."
        "Determines whether interest accrued is capitalised or not."
        "If daily, accrued interest added to principal daily. "
        "If monthly, accrued interest added to principal monthly."
        "If no_capitalisation then accrued interest is not added to principal.",
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
    # feature parameters
    *derived_params.all_parameters,
    *disbursement.parameters,
    *due_amount_calculation.schedule_parameters,
    due_amount_calculation.next_repayment_date_parameter,
    emi.equated_instalment_amount_parameter,
    *interest_accrual.schedule_parameters,
    *interest_accrual.accrual_parameters,
    *interest_accrual.account_parameters,
    interest_application.application_precision_param,
    *interest_application.account_parameters,
    *overdue.schedule_parameters,
    overdue.next_overdue_derived_parameter,
    *overpayment.fee_parameters,
    overpayment.overpayment_impact_preference_param,
    *fixed_rate.parameters,
    *variable_rate.parameters,
    lending_parameters.total_repayment_count_parameter,
    repayment_holiday.due_amount_calculation_blocking_param,
    repayment_holiday.overdue_amount_calculation_blocking_param,
    repayment_holiday.repayment_blocking_param,
    repayment_holiday.penalty_blocking_param,
    repayment_holiday.delinquency_blocking_param,
    repayment_holiday.repayment_holiday_impact_preference_param,
    *early_repayment.parameters,
    *balloon_payments.parameters,
    *interest_capitalisation.parameters,
]


@requires(parameters=True)
def activation_hook(
    vault: SmartContractVault, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    scheduled_events: dict[str, ScheduledEvent] = {}
    effective_datetime = hook_arguments.effective_datetime

    # schedule creation
    schedule_start_datetime = effective_datetime.replace(
        hour=0, minute=0, second=0
    ) + relativedelta(days=1)

    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    # standard interest accruals are not permitted on flat interest loans, so we should skip the
    # schedule indefinitely. It should only be un-skipped (in scheduled_event_hook) when penalty
    # interest is to be accrued, and then subsequently skipped again only once no more penalty
    # interest is accrued
    skip = flat_interest.is_flat_interest_loan(
        amortisation_method=amortisation_method
    ) or rule_of_78.is_rule_of_78_loan(amortisation_method=amortisation_method)

    scheduled_events.update(
        interest_accrual.scheduled_events(
            vault=vault, start_datetime=schedule_start_datetime, skip=skip
        )
    )

    is_balloon_payment_loan = balloon_payments.is_balloon_loan(
        amortisation_method=amortisation_method
    )

    if not is_balloon_payment_loan:
        scheduled_events.update(
            due_amount_calculation.scheduled_events(
                vault=vault, account_opening_datetime=effective_datetime
            )
        )
        # Use a dummy balloon payment schedule if no balloon payment schedule is required.
        scheduled_events.update(balloon_payments.disabled_balloon_schedule(effective_datetime))

    else:
        # Handle Balloon Payment loan
        # Balloon payment schedules will include the due day calculation schedule if the
        # amortisation is not a no repayment loan
        balloon_payment_schedules = balloon_payments.scheduled_events(
            vault=vault,
            account_opening_datetime=effective_datetime,
            amortisation_method=amortisation_method,
        )
        scheduled_events.update(balloon_payment_schedules)

    if no_repayment.is_no_repayment_loan(amortisation_method=amortisation_method):
        # the overdue and check delinquency schedules should be skipped indefinitely and only
        # updated as a result of the balloon payment event
        scheduled_events[overdue.CHECK_OVERDUE_EVENT] = utils.create_end_of_time_schedule(
            start_datetime=schedule_start_datetime
        )
        scheduled_events[CHECK_DELINQUENCY] = utils.create_end_of_time_schedule(
            start_datetime=schedule_start_datetime
        )
    else:
        due_amount_calculation_day = int(
            utils.get_parameter(
                vault=vault, name=due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
            )
        )

        overdue_schedule_start_datetime = schedule_start_datetime + relativedelta(
            months=1, day=due_amount_calculation_day
        )
        scheduled_events.update(
            overdue.scheduled_events(
                vault=vault,
                first_due_amount_calculation_datetime=overdue_schedule_start_datetime,
                skip=True,
            )
        )

        scheduled_events[CHECK_DELINQUENCY] = ScheduledEvent(
            start_datetime=schedule_start_datetime,
            expression=utils.get_schedule_expression_from_parameters(
                vault=vault, parameter_prefix=CHECK_DELINQUENCY_PREFIX
            ),
            skip=True,
        )

    # principal disbursement
    principal = utils.get_parameter(vault=vault, name=disbursement.PARAM_PRINCIPAL)
    deposit_account = utils.get_parameter(vault=vault, name=disbursement.PARAM_DEPOSIT_ACCOUNT)
    denomination = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)

    upfront_fee_account = utils.get_parameter(vault=vault, name=PARAM_UPFRONT_FEE_INTERNAL_ACCOUNT)
    upfront_fee = utils.get_parameter(vault=vault, name=PARAM_UPFRONT_FEE)
    amortise_upfront_fee = utils.get_parameter(
        vault=vault, name=PARAM_AMORTISE_UPFRONT_FEE, is_boolean=True
    )

    principal_adjustments: list[lending_interfaces.PrincipalAdjustment] = []
    if upfront_fee > Decimal("0"):
        if amortise_upfront_fee:
            # amortise on principal + fee
            principal_adjustments.append(
                lending_interfaces.PrincipalAdjustment(
                    calculate_principal_adjustment=_calculate_disbursement_principal_adjustment
                )
            )
        else:
            # principal less upfront fee is disbursed to the deposit account
            principal = principal - upfront_fee

    principal_custom_instructions = disbursement.get_disbursement_custom_instruction(
        account_id=vault.account_id,
        deposit_account_id=deposit_account,
        principal=principal,
        denomination=denomination,
    )
    if _is_monthly_rest_loan(vault=vault):
        # we update the principal tracker address now.
        # Since the interest_accrual_rest_type parameter is fixed, it makes sense to define the
        # tracker balance now and save a bit of complexity later on.
        principal_custom_instructions.extend(
            [
                CustomInstruction(
                    postings=utils.create_postings(
                        amount=principal,
                        debit_account=vault.account_id,
                        credit_account=vault.account_id,
                        debit_address=MONTHLY_REST_EFFECTIVE_PRINCIPAL,
                        credit_address=common_addresses.INTERNAL_CONTRA,
                        denomination=denomination,
                    ),
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Set principal at cycle start on activation",
                        "event": f"{ACCOUNT_TYPE}_SET_PRINCIPAL_AT_CYCLE_START_ON_ACTIVATION",
                    },
                ),
            ]
        )

    # charge fee
    # the fee is debited from the principal address regardless of whether the fee is amortised.
    # If amortised, the principal address needs to be equal to principal disbursement + fee.
    # If not amortised, principal - fee is disbursed to the customer and
    # therefore the principal balance address needs to increase by the fee offset.
    fee_custom_instructions = _get_activation_fee_custom_instruction(
        account_id=vault.account_id,
        amount=upfront_fee,
        denomination=denomination,
        fee_income_account=upfront_fee_account,
    )

    amortisation_custom_instruction = emi.amortise(
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
                client_batch_id=f"{ACCOUNT_TYPE}_{events.ACCOUNT_ACTIVATION}_"
                f"{vault.get_hook_execution_id()}",
                value_datetime=effective_datetime,
            )
        ],
        scheduled_events_return_value=scheduled_events,
    )


@requires(
    event_type=interest_accrual.ACCRUAL_EVENT,
    flags=True,
    last_execution_datetime=[due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT],
    parameters=True,
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
@requires(
    event_type=balloon_payments.BALLOON_PAYMENT_EVENT,
    flags=True,
    last_execution_datetime=[due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT],
    parameters=True,
)
@fetch_account_data(
    event_type=balloon_payments.BALLOON_PAYMENT_EVENT,
    balances=[
        fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID,
        interest_application.ACCRUED_INTEREST_EFF_FETCHER_ID,
        interest_application.ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID,
        overpayment.OVERPAYMENT_TRACKER_EFF_FETCHER_ID,
    ],
)
@requires(event_type=overdue.CHECK_OVERDUE_EVENT, flags=True, parameters=True)
@fetch_account_data(
    event_type=overdue.CHECK_OVERDUE_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@requires(event_type=CHECK_DELINQUENCY, flags=True, parameters=True)
@fetch_account_data(
    event_type=CHECK_DELINQUENCY, balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID]
)
def scheduled_event_hook(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    event_type = hook_arguments.event_type
    effective_datetime: datetime = hook_arguments.effective_datetime
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    custom_instructions: list[CustomInstruction] = []
    update_event_type_directives: list[UpdateAccountEventTypeDirective] = []
    account_notification_directives: list[AccountNotificationDirective] = []
    is_flat_interest_loan = flat_interest.is_flat_interest_loan(
        amortisation_method=amortisation_method
    )
    is_rule_of_78_loan = rule_of_78.is_rule_of_78_loan(amortisation_method=amortisation_method)

    if event_type == interest_accrual.ACCRUAL_EVENT:
        # accrue and process any penalty interest that should be accrued
        if penalty_accrual_postings := _get_penalty_interest_accrual_custom_instruction(
            vault=vault, hook_arguments=hook_arguments
        ):
            custom_instructions.extend(penalty_accrual_postings)

        # if no penalty interest postings then flat interest loans should skip daily accrual events
        # as it was only previously un-skipped as a result of a previous overdue event
        elif is_flat_interest_loan or is_rule_of_78_loan:
            update_event_type_directives.extend(
                interest_accrual_common.update_schedule_events_skip(skip=True)
            )

        # standard interest accruals and repayment holidays are not permitted
        # for flat interest and rule of 78 loans
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

    elif event_type == due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT:
        if repayment_holiday.is_due_amount_calculation_blocked(
            vault=vault, effective_datetime=hook_arguments.effective_datetime
        ):
            # We may need to increase the elapsed term, which is normally handled
            # inside due_amount_calculation's schedule_logic(), so that reamortisation at the end
            # of the holiday accounts for the due amount calculations that should have happened
            # during the repayment holiday
            if _should_repayment_holiday_increase_tracker_balance(
                vault=vault,
                effective_datetime=effective_datetime,
                amortisation_method=amortisation_method,
            ):
                denomination = _get_denomination_parameter(vault=vault)
                custom_instructions += [
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
                utils.get_parameter(vault=vault, name=overdue.PARAM_REPAYMENT_PERIOD)
            )
            update_event_type_directives.extend(
                _update_check_overdue_schedule(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    repayment_period=repayment_period,
                )
            )

        custom_instructions.extend(
            interest_capitalisation.handle_penalty_interest_capitalisation(
                vault=vault, account_type=ACCOUNT_TYPE
            )
        )
        if _should_enable_balloon_payment_schedule(
            vault=vault,
            effective_datetime=effective_datetime,
            amortisation_method=amortisation_method,
        ):
            update_event_type_directives.extend(
                balloon_payments.update_balloon_payment_schedule(
                    vault=vault, execution_timestamp=effective_datetime
                )
            )

        # if due amount calculation day was updated but the schedule had not run yet that month
        # and the day it was changed to is less than the effective_datetime.day,
        # then we need to update the schedule now to the new due amount calculation day next month
        due_amount_calculation_day = int(
            utils.get_parameter(
                vault=vault, name=due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
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

    elif event_type == overdue.CHECK_OVERDUE_EVENT:
        if not repayment_holiday.is_overdue_amount_calculation_blocked(
            vault=vault, effective_datetime=effective_datetime
        ):
            overdue_custom_instructions, _ = overdue.schedule_logic(
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
                    utils.get_parameter(vault=vault, name=PARAM_LATE_REPAYMENT_FEE)
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

                mark_delinquent_notification, delinquency_schedule_update = _handle_delinquency(
                    vault=vault,
                    hook_arguments=hook_arguments,
                    is_delinquency_schedule_event=False,
                    balances=posting_balances,
                )
                account_notification_directives.extend(mark_delinquent_notification)
                update_event_type_directives.extend(delinquency_schedule_update)

                # Daily accrual events are not permitted on flat interest or rule of 78 loans,
                # however penalty interest accrual is. Since we have overdue custom instructions
                # the accrual event should be un-skipped to accrue penalty interest
                if is_flat_interest_loan or is_rule_of_78_loan:
                    update_event_type_directives.extend(
                        interest_accrual_common.update_schedule_events_skip(
                            skip=False,
                        )
                    )

    elif event_type == CHECK_DELINQUENCY:
        mark_delinquent_notifications, delinquency_event_updates = _handle_delinquency(
            vault=vault, hook_arguments=hook_arguments, is_delinquency_schedule_event=True
        )
        account_notification_directives.extend(mark_delinquent_notifications)
        update_event_type_directives.extend(delinquency_event_updates)

    elif event_type == balloon_payments.BALLOON_PAYMENT_EVENT:
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

            repayment_period = overdue.get_repayment_period_parameter(vault=vault)
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


@fetch_account_data(balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID])
@requires(
    last_execution_datetime=[
        due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
    ],
    parameters=True,
)
def derived_parameter_hook(
    vault: SmartContractVault, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    effective_datetime: datetime = hook_arguments.effective_datetime

    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination = _get_denomination_parameter(vault=vault)

    # total outstanding debt
    total_outstanding_debt = derived_params.get_total_outstanding_debt(
        balances=balances,
        denomination=denomination,
    )

    # total outstanding payments
    total_outstanding_payments = derived_params.get_total_due_amount(
        balances=balances,
        denomination=denomination,
    )

    # total remaining principal
    total_remaining_principal = derived_params.get_total_remaining_principal(
        balances=balances,
        denomination=denomination,
    )

    total_early_repayment_amount = early_repayment.get_total_early_repayment_amount(
        vault=vault, early_repayment_fees=EARLY_REPAYMENT_FEES, balances=balances
    )

    interest_rate_feature = _get_interest_rate_feature(vault=vault)
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    # remaining_term
    elapsed_term, remaining_term = _get_amortisation_feature(vault=vault).term_details(
        vault=vault,
        effective_datetime=effective_datetime,
        use_expected_term=_use_expected_term(
            vault=vault, balances=balances, denomination=denomination
        ),
        interest_rate=interest_rate_feature,
        balances=balances,
        denomination=denomination,
    )
    if balloon_payments.is_balloon_loan(amortisation_method=amortisation_method):
        expected_balloon_payment_amount = balloon_payments.get_expected_balloon_payment_amount(
            vault=vault,
            effective_datetime=effective_datetime,
            balances=balances,
            interest_rate_feature=interest_rate_feature,
        )
    else:
        expected_balloon_payment_amount = Decimal("0")

    # next repayment date
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    if no_repayment.is_no_repayment_loan(amortisation_method):
        next_repayment_datetime = no_repayment.get_balloon_payment_datetime(vault=vault)
        next_overdue_datetime = overdue.get_next_overdue_derived_parameter(
            vault=vault,
            previous_due_amount_calculation_datetime=next_repayment_datetime,
        )
    else:
        # in the event of a balloon payment, the repayment date can be derived from the next
        # repayment date.
        next_repayment_datetime = due_amount_calculation.get_actual_next_repayment_date(
            vault=vault,
            effective_datetime=effective_datetime,
            elapsed_term=elapsed_term,
            remaining_term=remaining_term,
        )

        # next overdue date
        # Note: the next overdue date will not return correct values for backdated derived parameter
        # fetching
        previous_due_amount_calculation_datetime = vault.get_last_execution_datetime(
            event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
        )
        if previous_due_amount_calculation_datetime is None:
            previous_due_amount_calculation_datetime = (
                due_amount_calculation.get_first_due_amount_calculation_datetime(vault=vault)
            )

        next_overdue_datetime = overdue.get_next_overdue_derived_parameter(
            vault=vault,
            previous_due_amount_calculation_datetime=previous_due_amount_calculation_datetime,
        )

        if balloon_payments.is_balloon_loan(amortisation_method=amortisation_method):
            delta_days = balloon_payments._get_balloon_payment_delta_days(vault)
            # only apply this calculation when the effective time has surpassed the final due date
            # calculation.
            if next_repayment_datetime < effective_datetime and remaining_term == 0:
                next_repayment_datetime = next_repayment_datetime + relativedelta(days=delta_days)

            if next_overdue_datetime < effective_datetime and remaining_term == 0:
                next_overdue_datetime = next_overdue_datetime + relativedelta(days=delta_days)

    derived_parameters: dict[str, utils.ParameterValueTypeAlias] = {
        derived_params.PARAM_REMAINING_TERM: remaining_term,
        derived_params.PARAM_TOTAL_OUTSTANDING_DEBT: total_outstanding_debt,
        derived_params.PARAM_TOTAL_OUTSTANDING_PAYMENTS: total_outstanding_payments,
        derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL: total_remaining_principal,
        early_repayment.PARAM_TOTAL_EARLY_REPAYMENT_AMOUNT: total_early_repayment_amount,
        balloon_payments.PARAM_EXPECTED_BALLOON_PAYMENT_AMOUNT: expected_balloon_payment_amount,
        due_amount_calculation.PARAM_NEXT_REPAYMENT_DATE: next_repayment_datetime,
        # This will work for all types of loans except min_repayment with pre-defined emi,
        # we'll just have to add an if else to return either this balance or the parameter value
        emi.PARAM_EQUATED_INSTALMENT_AMOUNT: emi.get_expected_emi(
            balances=balances, denomination=denomination
        ),
        overdue.PARAM_NEXT_OVERDUE_DATE: next_overdue_datetime,
    }

    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


@requires(
    flags=True,
    last_execution_datetime=[due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT],
    parameters=True,
)
def pre_parameter_change_hook(
    vault: SmartContractVault, hook_arguments: PreParameterChangeHookArguments
) -> Optional[PreParameterChangeHookResult]:
    updated_parameter_values: dict[
        str, utils.ParameterValueTypeAlias
    ] = hook_arguments.updated_parameter_values

    if due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY in updated_parameter_values:
        amortisation_method: str = utils.get_parameter(
            vault=vault, name=PARAM_AMORTISATION_METHOD, is_union=True
        )
        if amortisation_method.upper() == "NO_REPAYMENT":
            return PreParameterChangeHookResult(
                rejection=Rejection(
                    message=(
                        "It is not possible to change the due amount calculation day for a "
                        "No Repayment (Balloon Payment) loan."
                    ),
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )

        if rejection := due_amount_calculation.validate_due_amount_calculation_day_change(
            vault=vault
        ):
            return PreParameterChangeHookResult(rejection=rejection)

        if repayment_holiday.is_due_amount_calculation_blocked(
            vault=vault, effective_datetime=hook_arguments.effective_datetime
        ):
            return PreParameterChangeHookResult(
                rejection=Rejection(
                    message=(
                        "It is not possible to change the due amount calculation day if "
                        "there are active due amount blocking flags."
                    ),
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )

    return None


@requires(parameters=True, flags=True)
@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    posting_instructions = hook_arguments.posting_instructions
    if utils.is_force_override(posting_instructions=posting_instructions):
        return None

    if posting_rejection := utils.validate_single_hard_settlement_or_transfer(
        posting_instructions=posting_instructions
    ):
        return PrePostingHookResult(rejection=posting_rejection)

    denomination = _get_denomination_parameter(vault=vault)
    if denomination_rejection := utils.validate_denomination(
        posting_instructions=posting_instructions, accepted_denominations=[denomination]
    ):
        return PrePostingHookResult(rejection=denomination_rejection)

    # we can use the first element in the posting instructions list here since the hook has
    # already validated the postings list is a single hard settlement
    posting_instruction = posting_instructions[0]
    posting_amount = _get_posting_amount(
        posting_instruction=posting_instruction, denomination=denomination
    )

    if posting_amount < Decimal("0"):
        # Then the posting is a repayment
        if repayment_holiday.is_repayment_blocked(
            vault=vault, effective_datetime=hook_arguments.effective_datetime
        ):
            return PrePostingHookResult(
                rejection=Rejection(
                    message="Repayments are blocked for this account.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )

        if early_repayment.is_posting_an_early_repayment(
            vault=vault,
            repayment_amount=posting_amount,
            early_repayment_fees=EARLY_REPAYMENT_FEES,
            denomination=denomination,
        ):
            # Validation is done within is_posting_an_early_repayment so we can return here
            return None

        if overpayment.is_posting_an_overpayment(
            vault=vault, repayment_amount=posting_amount, denomination=denomination
        ):
            amortisation_method = _get_amortisation_method_parameter(vault=vault)

            if (
                flat_interest.is_flat_interest_loan(amortisation_method)
                or rule_of_78.is_rule_of_78_loan(amortisation_method=amortisation_method)
                or minimum_repayment.is_minimum_repayment_loan(
                    amortisation_method=amortisation_method
                )
            ):
                return PrePostingHookResult(
                    rejection=Rejection(
                        message="Overpayments are not allowed for "
                        f"{amortisation_method.replace('_', ' ')} loans.",
                        reason_code=RejectionReason.AGAINST_TNC,
                    )
                )

            if overpayment.get_max_overpayment_amount(
                vault=vault, denomination=denomination
            ) == abs(posting_amount):
                total_early_repayment_amount = early_repayment.get_total_early_repayment_amount(
                    vault=vault,
                    early_repayment_fees=EARLY_REPAYMENT_FEES,
                    denomination=denomination,
                )
                return PrePostingHookResult(
                    rejection=Rejection(
                        message="Cannot repay remaining debt without paying early repayment fees, "
                        f"amount required is {total_early_repayment_amount}",
                        reason_code=RejectionReason.AGAINST_TNC,
                    )
                )

            if overpayment_rejection := overpayment.validate_overpayment(
                vault=vault, repayment_amount=posting_amount, denomination=denomination
            ):
                return PrePostingHookResult(rejection=overpayment_rejection)

    elif posting_amount > Decimal("0") and (
        not utils.str_to_bool(
            posting_instruction.instruction_details.get(INSTRUCTION_DETAILS_KEY_FEE, "false")
        )
        and not utils.str_to_bool(
            posting_instruction.instruction_details.get(
                INSTRUCTION_DETAILS_KEY_INTEREST_ADJUSTMENT, "false"
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


@requires(parameters=True)
@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
def post_posting_hook(
    vault: SmartContractVault, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    posting_instructions: utils.PostingInstructionListAlias = hook_arguments.posting_instructions
    if utils.is_force_override(posting_instructions=posting_instructions):
        return None

    effective_datetime = hook_arguments.effective_datetime

    # only single posting is accepted so we can just use the first element in the list
    posting = posting_instructions[0]

    denomination = _get_denomination_parameter(vault=vault)

    # only consider DEFAULT_ADDRESS since only hard settlements are accepted
    posting_balance: Decimal = utils.balance_at_coordinates(
        balances=posting.balances(), denomination=denomination
    )

    account_notification_directives: list[AccountNotificationDirective] = []
    custom_instructions: list[CustomInstruction] = []
    inflight_postings: list[Posting] = []

    if lending_utils.is_debit(amount=posting_balance):
        # debits only accepted when instruction details contains either fee/interest_adjustment
        is_interest_adjustment = _is_interest_adjustment(posting=posting)
        # if the debit is not an interest_adjustment it must be a fee hence use the PENALTIES
        # address
        balance_destination = (
            lending_addresses.INTEREST_DUE
            if is_interest_adjustment
            else lending_addresses.PENALTIES
        )

        # move posting amount into correct address
        inflight_postings.extend(
            utils.create_postings(
                amount=posting_balance,
                debit_account=vault.account_id,
                debit_address=balance_destination,
                credit_account=vault.account_id,
                credit_address=DEFAULT_ADDRESS,
                denomination=denomination,
            )
        )

        if is_interest_adjustment:
            # clear existing balance in interest due address so that the net is equal to the
            # posting_balance
            balances: BalanceDefaultDict = vault.get_balances_observation(
                fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
            ).balances
            interest_to_revert = _get_interest_to_revert(
                balances=balances, denomination=denomination
            )
            interest_received_account: str = utils.get_parameter(
                vault, name=interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT
            )

            inflight_postings.extend(
                utils.create_postings(
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

    elif lending_utils.is_credit(amount=posting_balance):
        repayment_custom_instructions, repayment_account_notification_directives = _process_payment(
            vault=vault,
            hook_arguments=hook_arguments,
            denomination=denomination,
        )
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


@requires(
    parameters=True,
    last_execution_datetime=[due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT],
)
@fetch_account_data(balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID])
def post_parameter_change_hook(
    vault: SmartContractVault, hook_arguments: PostParameterChangeHookArguments
) -> Optional[PostParameterChangeHookResult]:
    update_event_type_directives: list[UpdateAccountEventTypeDirective] = []

    effective_datetime = hook_arguments.effective_datetime
    updated_parameter_values: dict[
        str, utils.ParameterValueTypeAlias
    ] = hook_arguments.updated_parameter_values

    if updated_parameter_values.get(due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY):
        elapsed_term, remaining_term = _get_amortisation_feature(vault=vault).term_details(
            vault=vault,
            effective_datetime=effective_datetime,
            use_expected_term=True,
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


@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
@requires(parameters=True)
def deactivation_hook(
    vault: SmartContractVault, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances
    denomination = _get_denomination_parameter(vault=vault)

    if deactivation_rejection := close_loan.reject_closure_when_outstanding_debt(
        balances=balances,
        denomination=denomination,
        debt_addresses=lending_addresses.ALL_OUTSTANDING,
    ):
        return DeactivationHookResult(rejection=deactivation_rejection)

    custom_instructions = close_loan.net_balances(
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        residual_cleanup_features=[
            overpayment.OverpaymentResidualCleanupFeature,
            due_amount_calculation.DueAmountCalculationResidualCleanupFeature,
            lending_interfaces.ResidualCleanup(
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


@requires(parameters=True)
@fetch_account_data(balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID])
def conversion_hook(
    vault: SmartContractVault, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    effective_datetime = hook_arguments.effective_datetime

    # by default we must preserve all schedules
    scheduled_events = hook_arguments.existing_schedules
    posting_instructions: list[CustomInstruction] = []

    if utils.get_parameter(
        vault=vault,
        name=PARAM_TOP_UP,
        is_optional=True,
        is_boolean=True,
    ):
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
        denomination = _get_denomination_parameter(vault=vault)

        # we must reset trackers first so we can account for this in the reamortisation
        posting_instructions += close_loan.net_balances(
            balances=balances,
            denomination=denomination,
            account_id=vault.account_id,
            residual_cleanup_features=[
                overpayment.OverpaymentResidualCleanupFeature,
                lending_interfaces.ResidualCleanup(
                    get_residual_cleanup_postings=_get_residual_cleanup_postings
                ),
            ],
        )

        principal_timeseries = vault.get_parameter_timeseries(
            name=disbursement.PARAM_PRINCIPAL
        ).all()
        # we should safeguard against the scenario where the principal has not been updated
        # to prevent runtime errors
        if len(principal_timeseries) > 1:
            # we disburse the delta between the updated and previous principal value
            principal_to_disburse = principal_timeseries[-1].value - principal_timeseries[-2].value

            if principal_to_disburse > Decimal("0"):
                deposit_account = disbursement.get_deposit_account_parameter(vault=vault)
                posting_instructions += disbursement.get_disbursement_custom_instruction(
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

        principal_to_reamortise = utils.balance_at_coordinates(
            balances=inflight_balances,
            address=lending_addresses.PRINCIPAL,
            denomination=denomination,
        )
        # we need to reamortise the loan
        posting_instructions += emi.amortise(
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
                    postings=utils.create_postings(
                        amount=principal_to_reamortise,
                        debit_account=vault.account_id,
                        credit_account=vault.account_id,
                        debit_address=MONTHLY_REST_EFFECTIVE_PRINCIPAL,
                        credit_address=common_addresses.INTERNAL_CONTRA,
                        denomination=denomination,
                    ),
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Update principal at repayment cycle start balance",
                        "event": LOAN_TOP_UP,
                    },
                )
            ]
        if balloon_payments.is_balloon_loan(
            amortisation_method=_get_amortisation_method_parameter(vault=vault)
        ):
            scheduled_events.update(
                balloon_payments.update_no_repayment_balloon_schedule(vault=vault)
            )

    return ConversionHookResult(
        scheduled_events_return_value=scheduled_events,
        posting_instructions_directives=[
            PostingInstructionsDirective(
                posting_instructions=posting_instructions,
                value_datetime=effective_datetime,
            )
        ]
        if posting_instructions
        else [],
    )


## activation helpers
def _get_activation_fee_custom_instruction(
    account_id: str,
    amount: Decimal,
    denomination: str,
    fee_income_account: str,
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
                    account_address=lending_addresses.PRINCIPAL,
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
                "event": events.ACCOUNT_ACTIVATION,
            },
        )
    ]


def _calculate_disbursement_principal_adjustment(
    vault: SmartContractVault,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    """
    Signature required for the interface
    """
    return Decimal(utils.get_parameter(vault=vault, name=PARAM_UPFRONT_FEE))


def _get_repayment_schedule_notification(vault: SmartContractVault) -> AccountNotificationDirective:
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


def _get_repayment_schedule(vault: SmartContractVault) -> dict[str, list[str]]:
    """
    Gets a repayment schedule based on the loan amortisation type

    Currently, only declining principal amortisation loans are supported.
    If amortisation type is not declining principal, the return object will be empty.

    :param vault:
    :return: the repayment schedule
    """

    if declining_principal.is_declining_principal_loan(
        _get_amortisation_method_parameter(vault=vault)
    ):
        return _get_repayment_schedule_declining_principal(vault=vault)

    return {}


def _get_repayment_schedule_declining_principal(vault: SmartContractVault) -> dict[str, list[str]]:
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

    principal = utils.get_parameter(vault=vault, name=disbursement.PARAM_PRINCIPAL)
    total_term = int(
        utils.get_parameter(vault=vault, name=lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT)
    )

    amortise_upfront_fee = utils.get_parameter(
        vault=vault, name=PARAM_AMORTISE_UPFRONT_FEE, is_union=True
    )
    accrual_precision = int(
        utils.get_parameter(vault=vault, name=interest_accrual.PARAM_ACCRUAL_PRECISION)
    )
    application_precision = int(
        utils.get_parameter(vault=vault, name=interest_application.PARAM_APPLICATION_PRECISION)
    )

    interest_rate_feature = _get_interest_rate_feature(vault=vault)
    daily_interest_rate = interest_rate_feature.get_daily_interest_rate(
        vault=vault, effective_datetime=account_creation_dt
    )
    monthly_interest_rate = interest_rate_feature.get_monthly_interest_rate(
        vault=vault, effective_datetime=account_creation_dt
    )

    # If the upfront fee is to be amortised add it to principal
    if amortise_upfront_fee.upper() == "TRUE":
        principal += _calculate_disbursement_principal_adjustment(vault=vault)

    # TODO INC-8499:
    # Use apply_declining_principal_formula from declining_principal feature
    # when INC-8472 lands
    if monthly_interest_rate == 0:
        expected_emi = principal / total_term
    else:
        # Calculate EMI using formula:
        # EMI = P × r × (1 + r)^n / ((1 + r)^n – 1)
        expected_emi = (
            principal
            * monthly_interest_rate
            * ((1 + monthly_interest_rate) ** total_term)
            / (((1 + monthly_interest_rate) ** total_term) - 1)
        )
    expected_emi = utils.round_decimal(amount=expected_emi, decimal_places=application_precision)

    # Pre-calculate non-emi accrued interest which would affect first principal due amount
    first_repayment_date = due_amount_calculation.get_first_due_amount_calculation_datetime(
        vault=vault,
    )
    additional_payment = Decimal("0")
    if account_creation_dt + relativedelta(months=1) < first_repayment_date:
        additional_days = (
            first_repayment_date - relativedelta(months=1) - account_creation_dt
        ).days
        daily_additional_interest = utils.round_decimal(
            amount=principal * daily_interest_rate, decimal_places=accrual_precision
        )
        additional_interest = daily_additional_interest * additional_days
        additional_payment = utils.round_decimal(
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

        # TODO INC-8492:
        # Reexamine/fix the approach of only calculating the daily interest rate once at activation
        daily_interest_due = utils.round_decimal(
            amount=principal * daily_interest_rate, decimal_places=accrual_precision
        )

        interest_due = utils.round_decimal(
            amount=daily_interest_due * delta_days, decimal_places=application_precision
        )
        principal_due = utils.round_decimal(
            amount=expected_emi + additional_payment - interest_due,
            decimal_places=application_precision,
        )
        principal = utils.round_decimal(
            amount=principal - principal_due, decimal_places=application_precision
        )

        # Add remaining principal if final repayment
        if month == total_term:
            additional_payment = principal
            principal_due += principal
            principal = Decimal("0")

        # Calculate the total monthly repayment by adding any additional payment to EMI
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


def _get_amortisation_feature(vault: SmartContractVault) -> lending_interfaces.Amortisation:
    """
    Populates and returns an instance of lending_interfaces.Amortisation with the respective
    feature methods, depending on the amortisation method currently active on the account.

    :return amortisation:
    """
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    if rule_of_78.is_rule_of_78_loan(amortisation_method=amortisation_method):
        return rule_of_78.AmortisationFeature
    elif flat_interest.is_flat_interest_loan(amortisation_method=amortisation_method):
        return flat_interest.AmortisationFeature
    elif minimum_repayment.is_minimum_repayment_loan(amortisation_method=amortisation_method):
        return minimum_repayment.AmortisationFeature
    elif interest_only.is_interest_only_loan(amortisation_method=amortisation_method):
        return interest_only.AmortisationFeature
    elif no_repayment.is_no_repayment_loan(amortisation_method=amortisation_method):
        return no_repayment.AmortisationFeature
    else:
        return declining_principal.AmortisationFeature


## accrual helpers
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
    if repayment_holiday.is_penalty_accrual_blocked(
        vault=vault,
        effective_datetime=hook_arguments.effective_datetime,
    ):
        return []

    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.EOD_FETCHER_ID
    ).balances
    denomination = _get_denomination_parameter(vault=vault)
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
        annual_interest_rate += _get_interest_rate_feature(vault=vault).get_annual_interest_rate(
            vault=vault
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
        # Although we call it accrual, we immediately apply normal penalty interest and should
        # round accordingly
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


ACCRUED_INTEREST_PENDING_CAPITALISATION = "ACCRUED_INTEREST_PENDING_CAPITALISATION"


def _get_standard_interest_accrual_custom_instructions(
    vault: SmartContractVault,
    hook_arguments: ScheduledEventHookArguments,
    inflight_postings: list[CustomInstruction],
) -> list[CustomInstruction]:
    accrue_to_pending_capitalisation = repayment_holiday.is_due_amount_calculation_blocked(
        vault=vault, effective_datetime=hook_arguments.effective_datetime
    )
    interest_rate_feature = _get_interest_rate_feature(vault=vault)

    if accrue_to_pending_capitalisation or _no_repayment_to_be_capitalised(vault=vault):
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
            vault=vault, hook_arguments=hook_arguments, interest_rate_feature=interest_rate_feature
        )

    return (
        interest_accrual.daily_accrual_logic(
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


def _get_interest_rate_feature(vault: SmartContractVault) -> lending_interfaces.InterestRate:
    amortisation_method = _get_amortisation_method_parameter(vault=vault)
    return (
        FIXED_RATE_FEATURE
        if utils.get_parameter(vault=vault, name=PARAM_FIXED_RATE_LOAN, is_boolean=True)
        or rule_of_78.is_rule_of_78_loan(amortisation_method=amortisation_method)
        or flat_interest.is_flat_interest_loan(amortisation_method=amortisation_method)
        else VARIABLE_RATE_FEATURE
    )


def _get_interest_application_feature(
    vault: SmartContractVault,
) -> lending_interfaces.InterestApplication:
    amortisation_method = _get_amortisation_method_parameter(vault=vault)

    if rule_of_78.is_rule_of_78_loan(amortisation_method=amortisation_method):
        return rule_of_78.InterestApplication
    elif flat_interest.is_flat_interest_loan(amortisation_method=amortisation_method):
        return flat_interest.InterestApplication
    else:
        return interest_application.InterestApplication


def _get_loan_reamortisation_conditions(
    vault: SmartContractVault,
) -> list[lending_interfaces.ReamortisationCondition]:
    amortisation_method = utils.get_parameter(
        vault=vault, name=PARAM_AMORTISATION_METHOD, is_union=True
    )
    return (
        []
        if (
            rule_of_78.is_rule_of_78_loan(amortisation_method=amortisation_method)
            or flat_interest.is_flat_interest_loan(amortisation_method=amortisation_method)
        )
        else [
            overpayment.OverpaymentReamortisationCondition,
            repayment_holiday.ReamortisationConditionWithPreference,
            fixed_rate.FixedReamortisationCondition
            if utils.get_parameter(vault=vault, name=PARAM_FIXED_RATE_LOAN, is_boolean=True)
            else variable_rate.VariableReamortisationCondition,
        ]
    )


def _get_accrual_principal_addresses(vault: SmartContractVault) -> list[str]:
    principal_address = (
        [MONTHLY_REST_EFFECTIVE_PRINCIPAL]
        if _is_monthly_rest_loan(vault=vault)
        else [lending_addresses.PRINCIPAL]
    )
    return (
        principal_address
        if not utils.get_parameter(vault=vault, name=PARAM_ACCRUE_ON_DUE_PRINCIPAL, is_boolean=True)
        else principal_address + [lending_addresses.PRINCIPAL_DUE]
    )


def _is_monthly_rest_loan(vault: SmartContractVault) -> bool:
    return (
        utils.get_parameter(
            vault=vault, name=PARAM_INTEREST_ACCRUAL_REST_TYPE, is_union=True
        ).lower()
        == "monthly"
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


def _handle_interest_capitalisation(
    vault: SmartContractVault,
    effective_datetime: datetime,
    account_type: str,
    balances: Optional[BalanceDefaultDict] = None,
    interest_to_capitalise_address: str = lending_addresses.ACCRUED_INTEREST_PENDING_CAPITALISATION,
) -> list[CustomInstruction]:
    if not _should_handle_interest_capitalisation(
        vault=vault, effective_datetime=effective_datetime
    ):
        return []
    instructions = interest_capitalisation.handle_interest_capitalisation(
        vault=vault,
        account_type=account_type,
        balances=balances,
        interest_to_capitalise_address=interest_to_capitalise_address,
    )
    if _is_monthly_rest_loan(vault=vault):
        # Get the amount posted to Principal and use to credit MONTHLY_REST_EFFECTIVE_PRINCIPAL
        monthly_rest_postings = []
        if instructions:
            # handle_interest_capitalisation always returns up to 1 custom instruction
            custom_instruction = instructions[0]
            posting_balances: BalanceDefaultDict = custom_instruction.balances(
                account_id=vault.account_id, tside=Tside.ASSET
            )
            posting_amount = abs(
                utils.balance_at_coordinates(
                    balances=posting_balances,
                    address=lending_addresses.PRINCIPAL,
                    denomination=_get_denomination_parameter(vault=vault),
                )
            )
            monthly_rest_postings = utils.create_postings(
                amount=posting_amount,
                debit_account=vault.account_id,
                credit_account=vault.account_id,
                debit_address=MONTHLY_REST_EFFECTIVE_PRINCIPAL,
                credit_address=common_addresses.INTERNAL_CONTRA,
            )
            custom_instruction.postings.extend(monthly_rest_postings)
    return instructions


## due amount calculation event helpers
def _get_due_amount_custom_instructions(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
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
                postings=due_amount_calculation.update_due_amount_calculation_counter(
                    account_id=vault.account_id, denomination=denomination
                ),
                instruction_details=utils.standard_instruction_details(
                    description="Updating due amount calculation counter balance",
                    event_type=hook_arguments.event_type,
                    gl_impacted=False,
                    account_type=ACCOUNT_TYPE,
                ),
                override_all_restrictions=True,
            )
        ]

    # the check for a repayment holiday is handled outside of this function so no need to check here
    principal_adjustment_features: list[lending_interfaces.PrincipalAdjustment] = [
        overpayment.OverpaymentPrincipalAdjustment,
    ]
    interest_application_feature = _get_interest_application_feature(vault=vault)
    previous_application_datetime = (
        vault.get_last_execution_datetime(
            event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
        )
        or vault.get_account_creation_datetime()
    )

    amortisation_feature = _get_amortisation_feature(vault=vault)
    balances = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances

    custom_instructions = due_amount_calculation.schedule_logic(
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
    # for monthly rest loans we accrue on the principal at the start of the repayment cycle, so here
    # we need to update the principal at cycle start tracker address balance
    if _is_monthly_rest_loan(vault=vault):
        custom_instructions = _add_principal_at_cycle_start_tracker_postings(
            vault=vault, due_amount_postings=custom_instructions
        )

    return (
        custom_instructions
        + overpayment.reset_due_amount_calc_overpayment_trackers(vault=vault)
        + overpayment.track_emi_principal_excess(
            vault=vault,
            interest_application_feature=interest_application_feature,
            effective_datetime=hook_arguments.effective_datetime,
            previous_application_datetime=previous_application_datetime,
        )
    )


## balloon payment event helpers
def _get_balloon_payment_custom_instructions(
    vault: SmartContractVault,
    hook_arguments: ScheduledEventHookArguments,
) -> list[CustomInstruction]:
    # Previous application is done by the due amount calculation event in the
    # case of a minimal repayment or interest only event
    previous_application_datetime = (
        vault.get_last_execution_datetime(
            event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
        )
        or vault.get_account_creation_datetime()
    )
    denomination = _get_denomination_parameter(vault=vault)
    balances = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    interest_capitalisation_postings: list[CustomInstruction] = []
    merged_balances = BalanceDefaultDict()
    merged_balances += balances

    if _is_no_repayment_loan_interest_to_be_capitalised(
        vault=vault, effective_datetime=hook_arguments.effective_datetime
    ):
        interest_capitalisation_postings = interest_capitalisation.handle_interest_capitalisation(
            vault=vault, account_type=ACCOUNT_TYPE, balances=balances
        )
        for ci in interest_capitalisation_postings:
            merged_balances += ci.balances(account_id=vault.account_id, tside=Tside.ASSET)

    interest_application_feature = _get_interest_application_feature(vault=vault)

    custom_instructions = balloon_payments.schedule_logic(
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
        + overpayment.reset_due_amount_calc_overpayment_trackers(
            vault=vault, balances=balances, denomination=denomination
        )
        + overpayment.track_emi_principal_excess(
            vault=vault,
            interest_application_feature=interest_application_feature,
            effective_datetime=hook_arguments.effective_datetime,
            previous_application_datetime=previous_application_datetime,
        )
    )


def _should_enable_balloon_payment_schedule(
    vault: SmartContractVault, effective_datetime: datetime, amortisation_method: str
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
        balloon_payments.is_balloon_loan(amortisation_method=amortisation_method)
        and _get_amortisation_feature(vault=vault).term_details(
            vault=vault, effective_datetime=effective_datetime, use_expected_term=True
        )[1]
        == 1
        and balloon_payments._get_balloon_payment_delta_days(vault=vault) > 0
    )


def _should_execute_balloon_payment_schedule_logic(
    vault: SmartContractVault, effective_datetime: datetime, amortisation_method: str
) -> bool:
    """ "
    Determines whether the balloon payment schedule logic should be run instead of the
    due_amount_calculation logic during the due_amount_calculation scheduled_event.

    This should return true if the loan is a balloon loan and it is the final due amount event,
    with a balloon payment delta days equal to zero
    """
    if not balloon_payments.is_balloon_loan(amortisation_method=amortisation_method):
        return False

    _, remaining_term = _get_amortisation_feature(vault=vault).term_details(
        vault=vault, effective_datetime=effective_datetime, use_expected_term=True
    )
    return (
        remaining_term == 1 and balloon_payments._get_balloon_payment_delta_days(vault=vault) == 0
    )


def _add_principal_at_cycle_start_tracker_postings(
    vault: SmartContractVault, due_amount_postings: list[CustomInstruction]
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
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination = _get_denomination_parameter(vault=vault)

    existing_principal_tracker_balance = utils.balance_at_coordinates(
        balances=balances,
        address=MONTHLY_REST_EFFECTIVE_PRINCIPAL,
        denomination=denomination,
    )

    net_reduction_in_principal = _get_net_balance_change_for_address(
        custom_instructions=due_amount_postings,
        account_id=vault.account_id,
        address=lending_addresses.PRINCIPAL,
        denomination=denomination,
    )

    principal_balance = utils.balance_at_coordinates(
        balances=balances,
        address=lending_addresses.PRINCIPAL,
        denomination=denomination,
    )

    # We always expect the due_amount_calculation postings to reduce the principal balance,
    # therefore net_reduction_in_principal will always be negative
    posting_amount = existing_principal_tracker_balance - (
        principal_balance + net_reduction_in_principal
    )

    postings = []
    if posting_amount > Decimal("0"):
        postings.extend(
            utils.create_postings(
                amount=posting_amount,
                debit_account=vault.account_id,
                credit_account=vault.account_id,
                debit_address=common_addresses.INTERNAL_CONTRA,
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
                    "event": due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
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

    return utils.balance_at_coordinates(
        balances=merged_balances, address=address, denomination=denomination
    )


def _get_repayment_due_notification(
    vault: SmartContractVault,
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
    # TODO: this arguably should sit within the due_amount_calculation feature itself,
    # see INC-8226
    merged_balances = BalanceDefaultDict()
    for custom_instruction in due_amount_custom_instructions:
        merged_balances += custom_instruction.balances(
            account_id=vault.account_id, tside=Tside.ASSET
        )

    denomination = _get_denomination_parameter(vault=vault)
    repayment_period = int(utils.get_parameter(vault=vault, name=overdue.PARAM_REPAYMENT_PERIOD))

    total_due_amount = utils.sum_balances(
        balances=merged_balances,
        addresses=[lending_addresses.PRINCIPAL_DUE, lending_addresses.INTEREST_DUE],
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
    vault: SmartContractVault,
    effective_datetime: datetime,
    repayment_period: Optional[int] = None,
    skip: bool = False,
) -> list[UpdateAccountEventTypeDirective]:
    if skip:
        return [UpdateAccountEventTypeDirective(event_type=overdue.CHECK_OVERDUE_EVENT, skip=skip)]

    if repayment_period is None:
        repayment_period = int(
            utils.get_parameter(vault=vault, name=overdue.PARAM_REPAYMENT_PERIOD)
        )

    repayment_period_end = effective_datetime + relativedelta(days=repayment_period)
    return [
        UpdateAccountEventTypeDirective(
            event_type=overdue.CHECK_OVERDUE_EVENT,
            expression=utils.get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=overdue.CHECK_OVERDUE_PREFIX,
                day=repayment_period_end.day,
            ),
            skip=skip,
        )
    ]


def _should_repayment_holiday_increase_tracker_balance(
    vault: SmartContractVault, effective_datetime: datetime, amortisation_method: str
) -> bool:
    """
    We need to increase the elapsed term tracker address if the repayment holiday preference is to
    increase emi and that the loan is not either a flat interest loan or rule of 78 loan. Otherwise
    a repayment holiday will always increase the term of the loan.
    """
    return repayment_holiday.is_repayment_holiday_impact_increase_emi(
        vault=vault, effective_datetime=effective_datetime
    ) and not (
        rule_of_78.is_rule_of_78_loan(amortisation_method=amortisation_method)
        or flat_interest.is_flat_interest_loan(amortisation_method=amortisation_method)
    )


## overdue event helpers
def _charge_late_repayment_fee(
    vault: SmartContractVault,
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
    amount = amount or Decimal(utils.get_parameter(vault=vault, name=PARAM_LATE_REPAYMENT_FEE))
    denomination = denomination or str(utils.get_parameter(vault=vault, name=PARAM_DENOMINATION))
    late_repayment_fee_income_account: str = utils.get_parameter(
        vault=vault, name=PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT
    )
    customer_account_address = lending_addresses.PENALTIES
    capitalise_late_repayment_fee = utils.get_parameter(
        vault=vault,
        name=PARAM_CAPITALISE_LATE_REPAYMENT_FEE,
        is_boolean=True,
    )
    if capitalise_late_repayment_fee:
        customer_account_address = lending_addresses.PRINCIPAL
        late_repayment_fee_income_account = utils.get_parameter(
            vault=vault, name=interest_capitalisation.PARAM_CAPITALISED_PENALTIES_RECEIVED_ACCOUNT
        )
        postings += utils.create_postings(
            amount=amount,
            debit_account=vault.account_id,
            credit_account=vault.account_id,
            debit_address=CAPITALISED_PENALTIES_TRACKER,
            credit_address=common_addresses.INTERNAL_CONTRA,
        )

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


## delinquency helpers
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
        vault=vault,
        effective_datetime=effective_datetime,
    ) or utils.is_flag_in_list_applied(
        vault=vault, parameter_name=PARAM_DELINQUENCY_FLAG, effective_datetime=effective_datetime
    ):
        return []

    denomination = _get_denomination_parameter(vault=vault)
    balances = (
        balances
        or vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    )
    if _get_late_payment_balance(
        balances=balances,
        denomination=denomination,
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


## post parameter change hook helpers
def _handle_due_amount_calculation_day_change(
    vault: SmartContractVault, effective_datetime: datetime, elapsed_term: int, remaining_term: int
) -> list[UpdateAccountEventTypeDirective]:
    update_event_type_directives: list[UpdateAccountEventTypeDirective] = []

    last_execution_datetime = vault.get_last_execution_datetime(
        event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
    )
    next_due_amount_calculation_datetime = (
        due_amount_calculation.get_next_due_amount_calculation_datetime(
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
        # if next schedule datetime == last_execution_datetime + relativedelta(months=1)
        # then the schedule will be updated during due_amount_calculation schedule execution
        update_event_type_directives.extend(
            _update_due_amount_calculation_day_schedule(
                vault=vault,
                schedule_start_datetime=next_due_amount_calculation_datetime,
                due_amount_calculation_day=next_due_amount_calculation_datetime.day,
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
            # i.e. if we update the day to a day later in the month but the schedule
            # has already run that calendar month
            skip=ScheduleSkip(end=schedule_start_datetime - relativedelta(seconds=1)),
        )
    ]


## common helpers
def _get_late_payment_balance(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    return utils.sum_balances(
        balances=balances,
        addresses=lending_addresses.LATE_REPAYMENT_ADDRESSES,
        denomination=denomination,
        decimal_places=2,
    )


## derived parameter helpers
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


## parameter getter helpers
def _get_denomination_parameter(vault: SmartContractVault) -> str:
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    return denomination


def _get_amortisation_method_parameter(vault: SmartContractVault) -> str:
    amortisation_method: str = utils.get_parameter(
        vault=vault, name=PARAM_AMORTISATION_METHOD, is_union=True
    )
    return amortisation_method


## Posting helpers
def _is_interest_adjustment(posting: utils.PostingInstructionTypeAlias) -> bool:
    return utils.str_to_bool(
        posting.instruction_details.get(INSTRUCTION_DETAILS_KEY_INTEREST_ADJUSTMENT, "false")
    )


def _get_interest_to_revert(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    return utils.balance_at_coordinates(
        balances=balances,
        address=lending_addresses.INTEREST_DUE,
        denomination=denomination,
    )


def _get_posting_amount(
    posting_instruction: utils.PostingInstructionTypeAlias,
    denomination: str,
    address: str = DEFAULT_ADDRESS,
) -> Decimal:
    posting_balances = posting_instruction.balances()

    return utils.get_available_balance(
        balances=posting_balances, denomination=denomination, address=address
    )


def _process_payment(
    vault: SmartContractVault,
    hook_arguments: PostPostingHookArguments,
    denomination: str,
) -> tuple[list[CustomInstruction], list[AccountNotificationDirective]]:
    """
    Processes a payment received from the borrower, paying off the balance in different addresses
    in the correct order
    """
    account_notification_directives: list[AccountNotificationDirective] = []

    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances

    custom_instructions = payments.generate_repayment_postings(
        vault=vault,
        hook_arguments=hook_arguments,
        overpayment_features=[
            lending_interfaces.Overpayment(handle_overpayment=_handle_overpayment)
        ],
        early_repayment_fees=EARLY_REPAYMENT_FEES,
    )

    if close_loan.does_repayment_fully_repay_loan(
        repayment_posting_instructions=custom_instructions,
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        payment_addresses=lending_addresses.ALL_OUTSTANDING,
    ):
        account_notification_directives.append(
            AccountNotificationDirective(
                notification_type=CLOSURE_NOTIFICATION,
                notification_details={"account_id": str(vault.account_id)},
            )
        )

    return custom_instructions, account_notification_directives


def _handle_overpayment(
    vault: SmartContractVault,
    overpayment_amount: Decimal,
    denomination: str,
    balances: BalanceDefaultDict,
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

    # charge overpayment fee
    overpayment_fee_rate: Decimal = utils.get_parameter(
        vault=vault, name=overpayment.PARAM_OVERPAYMENT_FEE_RATE
    )
    overpayment_fee_income_account: str = utils.get_parameter(
        vault=vault, name=overpayment.PARAM_OVERPAYMENT_FEE_INCOME_ACCOUNT
    )

    overpayment_fee = min(
        overpayment.get_overpayment_fee(
            principal_repaid=overpayment_amount,
            overpayment_fee_rate=overpayment_fee_rate,
            precision=2,
        ),
        overpayment.get_max_overpayment_fee(
            fee_rate=overpayment_fee_rate, balances=balances, denomination=denomination, precision=2
        ),
    )

    postings.extend(
        overpayment.get_overpayment_fee_postings(
            overpayment_fee=overpayment_fee,
            denomination=denomination,
            customer_account_id=vault.account_id,
            customer_account_address=DEFAULT_ADDRESS,
            internal_account=overpayment_fee_income_account,
        )
    )
    # process overpayment
    overpayment_amount -= overpayment_fee
    postings.extend(
        overpayment.handle_overpayment(
            vault=vault,
            overpayment_amount=overpayment_amount,
            denomination=denomination,
            balances=balances,
        )
    )

    return postings


## deactivation helpers
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
        address_balance = utils.balance_at_coordinates(
            balances=balances, address=address, denomination=denomination
        )

        if address_balance > Decimal("0"):
            postings += utils.create_postings(
                amount=address_balance,
                debit_account=account_id,
                credit_account=account_id,
                debit_address=common_addresses.INTERNAL_CONTRA,
                credit_address=address,
                denomination=denomination,
            )

    return postings


def _no_repayment_to_be_capitalised(vault: SmartContractVault) -> bool:
    capitalise_no_repayment_loan: str = utils.get_parameter(
        vault=vault, name=PARAM_CAPITALISE_NO_REPAYMENT_ACCRUED_INTEREST, is_union=True
    ).upper()
    amortisation_method = _get_amortisation_method_parameter(vault=vault)

    return (
        no_repayment.is_no_repayment_loan(amortisation_method)
        and capitalise_no_repayment_loan != "NO_CAPITALISATION"
    )


def _is_no_repayment_loan_interest_to_be_capitalised(
    vault: SmartContractVault, effective_datetime: datetime
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
    capitalise_no_repayment_loan: str = utils.get_parameter(
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
            and effective_datetime.day == last_day_in_current_month
        ) or effective_datetime.day == loan_start_day

    return (
        no_repayment.is_no_repayment_loan(amortisation_method)
        and capitalise_no_repayment_loan != "NO_CAPITALISATION"
        and valid_day_to_capitalise is True
    )


def _should_handle_interest_capitalisation(
    vault: SmartContractVault,
    effective_datetime: datetime,
    is_penalty_interest_capitalisation: bool = False,
) -> bool:
    """
    Determine whether to do interest capitalisation
    """
    if no_repayment.is_no_repayment_loan(
        amortisation_method=_get_amortisation_method_parameter(vault=vault)
    ):
        return _is_no_repayment_loan_interest_to_be_capitalised(
            vault=vault, effective_datetime=effective_datetime
        )

    return (
        not repayment_holiday.is_penalty_accrual_blocked(
            vault=vault, effective_datetime=effective_datetime
        )
        or is_penalty_interest_capitalisation
    )
