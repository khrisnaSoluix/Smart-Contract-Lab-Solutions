# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

# features
import library.features.common.common_parameters as common_parameters
import library.features.v4.common.events as events
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.amortisations.declining_principal as declining_principal
import library.features.v4.lending.close_loan as close_loan
import library.features.v4.lending.configurable_repayment_frequency as config_repayment_frequency
import library.features.v4.lending.delinquency as delinquency
import library.features.v4.lending.derived_params as derived_params
import library.features.v4.lending.disbursement as disbursement
import library.features.v4.lending.due_amount_calculation as due_amount_calculation
import library.features.v4.lending.due_amount_notification as due_amount_notification
import library.features.v4.lending.emi as emi
import library.features.v4.lending.emi_in_advance as emi_in_advance
import library.features.v4.lending.late_repayment as late_repayment
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_parameters as lending_params
import library.features.v4.lending.lending_utils as lending_utils
import library.features.v4.lending.overdue as overdue
import library.features.v4.lending.payments as payments

# contracts api
from contracts_api import (
    AccountNotificationDirective,
    ActivationHookArguments,
    ActivationHookResult,
    BalanceDefaultDict,
    ConversionHookArguments,
    ConversionHookResult,
    CustomInstruction,
    DeactivationHookArguments,
    DeactivationHookResult,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    PostingInstructionsDirective,
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
    Tside,
    UpdateAccountEventTypeDirective,
    fetch_account_data,
    requires,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# contract metadata
api = "4.0.0"
version = "2.0.2"
display_name = "Buy Now Pay Later"
summary = "A no-interest short term loan repaid in equal instalments"
tside = Tside.ASSET

# product constants
PRODUCT_NAME = "BUY_NOW_PAY_LATER"
UTC_ZONE = ZoneInfo("UTC")

# parameter constants
PARAM_EQUATED_INSTALMENT_AMOUNT = emi.PARAM_EQUATED_INSTALMENT_AMOUNT
PARAM_LOAN_END_DATE = config_repayment_frequency.PARAM_LOAN_END_DATE
PARAM_NEXT_REPAYMENT_DATE = config_repayment_frequency.PARAM_NEXT_REPAYMENT_DATE
PARAM_REMAINING_TERM = config_repayment_frequency.PARAM_REMAINING_TERM
PARAM_TOTAL_OUTSTANDING_DEBT = derived_params.PARAM_TOTAL_OUTSTANDING_DEBT
PARAM_TOTAL_REMAINING_PRINCIPAL = derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL
PARAM_PRINCIPAL_PAID_TO_DATE = derived_params.PARAM_PRINCIPAL_PAID_TO_DATE

# notification constants
DELINQUENCY_NOTIFICATION = delinquency.notification_type(PRODUCT_NAME)
LOAN_PAID_OFF_NOTIFICATION = close_loan.notification_type(PRODUCT_NAME)
DUE_AMOUNT_NOTIFICATION = due_amount_notification.notification_type(PRODUCT_NAME)
OVERDUE_REPAYMENT_NOTIFICATION = overdue.notification_type(PRODUCT_NAME)

# other contract metadata
notification_types = [
    DELINQUENCY_NOTIFICATION,
    LOAN_PAID_OFF_NOTIFICATION,
    DUE_AMOUNT_NOTIFICATION,
    OVERDUE_REPAYMENT_NOTIFICATION,
]

supported_denominations = ["GBP"]

event_types = [
    *delinquency.event_types(PRODUCT_NAME),
    *due_amount_calculation.event_types(PRODUCT_NAME),
    *due_amount_notification.event_types(PRODUCT_NAME),
    *overdue.event_types(PRODUCT_NAME),
    *late_repayment.event_types(PRODUCT_NAME),
]

data_fetchers = [fetchers.EFFECTIVE_OBSERVATION_FETCHER, fetchers.LIVE_BALANCES_BOF]

parameters = [
    # feature parameters
    common_parameters.denomination_parameter,
    *config_repayment_frequency.derived_parameters,
    config_repayment_frequency.repayment_frequency_parameter,
    *delinquency.schedule_parameters,
    derived_params.principal_paid_to_date_parameter,
    derived_params.total_outstanding_debt_parameter,
    derived_params.total_remaining_principal_parameter,
    *disbursement.parameters,
    *due_amount_calculation.schedule_time_parameters,
    *due_amount_notification.due_amount_notification_schedule_parameters,
    *emi.derived_parameters,
    *late_repayment.fee_parameters,
    *late_repayment.schedule_parameters,
    lending_params.total_repayment_count_parameter,
    *overdue.schedule_parameters,
]

# These parameters are editable to support features not required in BNPL
# In the future we may want to overload the parameter definitions
RESTRICTED_PARAMETERS = [
    disbursement.PARAM_PRINCIPAL,
    lending_params.PARAM_TOTAL_REPAYMENT_COUNT,
]

# hooks
@requires(parameters=True)
def activation_hook(
    vault: SmartContractVault, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    """
    Performs the following actions when opening an account:
    - Disburse the loan principal to the specified deposit account
    - Charge the first instalment
    - Generate the schedules
    """

    def _get_activation_postings(vault: SmartContractVault) -> list[PostingInstructionsDirective]:
        denomination = common_parameters.get_denomination_parameter(vault=vault)
        principal = disbursement.get_principal_parameter(vault=vault)
        deposit_account_id = disbursement.get_deposit_account_parameter(vault=vault)
        effective_datetime = hook_arguments.effective_datetime
        posting_instructions: list[CustomInstruction] = []
        posting_instructions += disbursement.get_disbursement_custom_instruction(
            account_id=vault.account_id,
            deposit_account_id=deposit_account_id,
            principal=principal,
            denomination=denomination,
            principal_address=lending_addresses.PRINCIPAL,
        )
        posting_instructions += emi_in_advance.charge(
            vault=vault,
            effective_datetime=effective_datetime,
            amortisation_feature=declining_principal.AmortisationFeature,
        )

        posting_instructions += [
            CustomInstruction(
                postings=due_amount_calculation.update_due_amount_calculation_counter(
                    account_id=vault.account_id, denomination=denomination
                ),
                instruction_details={
                    "description": "Update due amount calculation counter on account activation",
                    "event": events.ACCOUNT_ACTIVATION,
                },
            )
        ]

        posting_instruction_directive = PostingInstructionsDirective(
            posting_instructions=posting_instructions,
            client_batch_id=f"{events.ACCOUNT_ACTIVATION}_{vault.get_hook_execution_id()}",
            value_datetime=effective_datetime,
        )
        return [posting_instruction_directive]

    def _get_scheduled_events(vault: SmartContractVault) -> dict[str, ScheduledEvent]:
        first_due_amount_calc_datetime = vault.get_account_creation_datetime()
        repayment_period = overdue.get_repayment_period_parameter(vault=vault)
        grace_period = delinquency.get_grace_period_parameter(vault=vault)
        late_repayment_period = repayment_period + grace_period
        total_repayment_count = lending_params.get_total_repayment_count_parameter(vault=vault)
        repayment_frequency = config_repayment_frequency.get_repayment_frequency_parameter(
            vault=vault
        )
        repayment_frequency_delta = _get_repayment_frequency_delta(vault=vault)
        second_due_amount_calc_datetime = first_due_amount_calc_datetime + repayment_frequency_delta
        first_repayment_offset = emi_in_advance.EMI_IN_ADVANCE_OFFSET
        total_repayment_period_delta = repayment_frequency_delta * (
            total_repayment_count - first_repayment_offset
        )
        delinquency_check_datetime = (
            first_due_amount_calc_datetime
            + total_repayment_period_delta
            + relativedelta(days=repayment_period + grace_period)
        )

        scheduled_events: dict[str, ScheduledEvent] = {
            **config_repayment_frequency.get_due_amount_calculation_schedule(
                vault=vault,
                # Schedule will run on second due amount calculation date as first due amount
                # is calculated at account opening due to EMI in advance
                first_due_amount_calculation_datetime=second_due_amount_calc_datetime,
                repayment_frequency=repayment_frequency,
            ),
            **overdue.scheduled_events(
                vault=vault,
                first_due_amount_calculation_datetime=first_due_amount_calc_datetime,
            ),
            **late_repayment.scheduled_events(
                vault=vault,
                start_datetime=first_due_amount_calc_datetime
                + relativedelta(days=late_repayment_period),
                # Run late repayment check logic in overdue schedule if grace period is 0
                skip=True if grace_period == 0 else False,
            ),
            **delinquency.scheduled_events(
                vault=vault,
                start_datetime=delinquency_check_datetime,
                is_one_off=True,
            ),
            **due_amount_notification.scheduled_events(
                vault=vault, next_due_amount_calc_datetime=second_due_amount_calc_datetime
            ),
        }

        return scheduled_events

    return ActivationHookResult(
        posting_instructions_directives=_get_activation_postings(vault=vault),
        scheduled_events_return_value=_get_scheduled_events(vault=vault),
    )


@requires(event_type=due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT, parameters=True)
@fetch_account_data(
    event_type=due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@requires(event_type=delinquency.CHECK_DELINQUENCY_EVENT, parameters=True)
@fetch_account_data(
    event_type=delinquency.CHECK_DELINQUENCY_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@requires(
    event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
    last_execution_datetime=[due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT],
    parameters=True,
)
@fetch_account_data(
    event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@requires(event_type=overdue.CHECK_OVERDUE_EVENT, parameters=True)
@fetch_account_data(
    event_type=overdue.CHECK_OVERDUE_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@requires(event_type=late_repayment.CHECK_LATE_REPAYMENT_EVENT, parameters=True)
@fetch_account_data(
    event_type=late_repayment.CHECK_LATE_REPAYMENT_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
def scheduled_event_hook(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
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
            due_amount_calculation.schedule_logic(
                vault=vault,
                hook_arguments=hook_arguments,
                account_type=PRODUCT_NAME,
                amortisation_feature=declining_principal.AmortisationFeature,
            )
        )
        update_account_event_type_directives.extend(
            _schedule_fortnightly_repayment_frequency(
                vault=vault,
                hook_arguments=hook_arguments,
            )
        )

    def _handle_overdue_check() -> None:
        late_repayment_fee = late_repayment.get_late_repayment_fee_parameter(vault=vault)
        overdue_custom_instructions, overdue_notification_directives = overdue.schedule_logic(
            vault=vault,
            hook_arguments=hook_arguments,
            account_type=PRODUCT_NAME,
            late_repayment_fee=late_repayment_fee,
        )
        custom_instructions.extend(overdue_custom_instructions)
        notification_directives.extend(overdue_notification_directives)
        update_account_event_type_directives.extend(
            # Schedule the next overdue check considering the chosen repayment frequency
            _schedule_overdue_check_event(
                vault=vault, effective_datetime=hook_arguments.effective_datetime
            )
        )

        grace_period = delinquency.get_grace_period_parameter(vault=vault)
        if grace_period == 0:
            custom_instructions.extend(
                late_repayment.schedule_logic(
                    vault=vault,
                    hook_arguments=hook_arguments,
                    denomination=common_parameters.get_denomination_parameter(vault=vault),
                )
            )

    def _handle_late_repayment_check() -> None:
        custom_instructions.extend(
            late_repayment.schedule_logic(
                vault=vault,
                hook_arguments=hook_arguments,
                denomination=common_parameters.get_denomination_parameter(vault=vault),
            )
        )
        update_account_event_type_directives.extend(
            # Schedule the next late repayment check considering the chosen repayment frequency
            _schedule_check_late_repayment_event(
                vault=vault, effective_datetime=hook_arguments.effective_datetime
            )
        )

    def _handle_delinquency_check() -> None:
        notification_directives.extend(
            delinquency.schedule_logic(
                vault=vault,
                product_name=PRODUCT_NAME,
                addresses=lending_addresses.ALL_OUTSTANDING,
                denomination=common_parameters.get_denomination_parameter(vault=vault),
            )
        )

    def _handle_due_amount_notification() -> None:
        # This gets/creates the notification to be sent later
        notification_directives.extend(
            _get_repayment_notification(
                vault=vault, due_amount_notification_datetime=hook_arguments.effective_datetime
            )
        )
        # Update the schedule
        repayment_frequency = config_repayment_frequency.get_repayment_frequency_parameter(
            vault=vault
        )
        next_due_amount_notification_datetime = (
            due_amount_notification.get_next_due_amount_notification_datetime(
                vault=vault,
                current_due_amount_notification_datetime=hook_arguments.effective_datetime,
                repayment_frequency_delta=config_repayment_frequency.FREQUENCY_MAP[
                    repayment_frequency
                ],
            )
        )

        update_account_event_type_directives.append(
            UpdateAccountEventTypeDirective(
                event_type=due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT,
                expression=utils.get_schedule_expression_from_parameters(
                    vault=vault,
                    parameter_prefix=due_amount_notification.DUE_AMOUNT_NOTIFICATION_PREFIX,
                    day=next_due_amount_notification_datetime.day,
                    month=next_due_amount_notification_datetime.month,
                    year=next_due_amount_notification_datetime.year,
                ),
            )
        )

    if event_type == due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT:
        _handle_due_amount_calculation()
    elif event_type == overdue.CHECK_OVERDUE_EVENT:
        _handle_overdue_check()
    elif event_type == late_repayment.CHECK_LATE_REPAYMENT_EVENT:
        _handle_late_repayment_check()
    elif event_type == delinquency.CHECK_DELINQUENCY_EVENT:
        _handle_delinquency_check()
    elif event_type == due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT:
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


@requires(parameters=True)
@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
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
    posting_instructions: utils.PostingInstructionListAlias = hook_arguments.posting_instructions
    if utils.is_force_override(posting_instructions):
        return None

    denomination = common_parameters.get_denomination_parameter(vault=vault)
    if denomination_rejection := utils.validate_denomination(
        posting_instructions, accepted_denominations=[denomination]
    ):
        return PrePostingHookResult(rejection=denomination_rejection)

    if posting_rejection := utils.validate_single_hard_settlement_or_transfer(
        posting_instructions=posting_instructions
    ):
        return PrePostingHookResult(rejection=posting_rejection)

    posting = posting_instructions[0]
    posting_amount = utils.get_available_balance(
        balances=posting.balances(),
        denomination=denomination,
    )

    if lending_utils.is_credit(posting_amount):
        posting_amount = abs(posting_amount)
        balances: BalanceDefaultDict = vault.get_balances_observation(
            fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
        ).balances
        total_outstanding_debt = derived_params.get_total_outstanding_debt(
            balances=balances, denomination=denomination
        )
        total_due_amount = derived_params.get_total_due_amount(
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
    elif lending_utils.is_debit(posting_amount):
        return PrePostingHookResult(
            rejection=Rejection(
                message="Debiting from this account is not allowed.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
    else:
        return PrePostingHookResult(
            rejection=Rejection(
                message="Cannot post zero amount.",
                reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
            )
        )


@requires(parameters=True)
@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
def post_posting_hook(
    vault: SmartContractVault, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    """
    Perform the following actions after a posting is accepted:
    - Skip processing of force override postings
    - Rebalance payment postings from the DEFAULT address to the corresponding repayment addresses
    (e.g. due and penalties)
    - Send notification if repayment fully repays loan
    """
    hook_posting_instructions: utils.PostingInstructionListAlias = (
        hook_arguments.posting_instructions
    )

    if utils.is_force_override(hook_posting_instructions):
        return None

    posting_instructions = payments.generate_repayment_postings(
        vault=vault,
        hook_arguments=hook_arguments,
        repayment_hierarchy=lending_addresses.REPAYMENT_HIERARCHY,
    )

    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances

    denomination = common_parameters.get_denomination_parameter(vault=vault)
    account_notification_directives: list[AccountNotificationDirective] = []
    posting_instructions_directives: list[PostingInstructionsDirective] = []

    if close_loan.does_repayment_fully_repay_loan(
        repayment_posting_instructions=posting_instructions,
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        payment_addresses=lending_addresses.ALL_OUTSTANDING,
    ):
        account_notification_directives.append(
            close_loan.send_loan_paid_off_notification(
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


def conversion_hook(
    vault: SmartContractVault, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    return ConversionHookResult(scheduled_events_return_value=hook_arguments.existing_schedules)


@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
@requires(parameters=True)
def deactivation_hook(
    vault: SmartContractVault, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    """
    Perform the following actions when an account is being closed:
    - Reject if there is outstanding debt
    - Nets off the EMI, and any other accounting addresses from other features,
    that should be cleared before the loan is closed
    """

    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances
    denomination = common_parameters.get_denomination_parameter(vault=vault)

    if outstanding_debt_rejection := close_loan.reject_closure_when_outstanding_debt(
        balances=balances,
        denomination=denomination,
    ):
        return DeactivationHookResult(rejection=outstanding_debt_rejection)

    posting_instructions_to_net_balances = close_loan.net_balances(
        balances=balances,
        denomination=denomination,
        account_id=vault.account_id,
        residual_cleanup_features=[
            due_amount_calculation.DueAmountCalculationResidualCleanupFeature
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
@fetch_account_data(balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID])
def derived_parameter_hook(
    vault: SmartContractVault, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    """
    Calculate the values of the derived parameters.
    """
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    denomination = common_parameters.get_denomination_parameter(vault=vault)
    total_repayment_count = (
        lending_params.get_total_repayment_count_parameter(vault=vault)
        - emi_in_advance.EMI_IN_ADVANCE_OFFSET
    )
    repayment_frequency = config_repayment_frequency.get_repayment_frequency_parameter(vault=vault)
    account_creation_datetime = vault.get_account_creation_datetime()
    principal = disbursement.get_principal_parameter(vault=vault)

    equated_instalment_amount = due_amount_calculation.get_emi(
        balances=balances, denomination=denomination
    )
    loan_end_datetime = config_repayment_frequency.get_next_due_amount_calculation_date(
        vault=vault,
        effective_date=datetime.max.replace(tzinfo=UTC_ZONE),
        total_repayment_count=total_repayment_count,
        repayment_frequency=repayment_frequency,
    )
    next_repayment_datetime = config_repayment_frequency.get_next_due_amount_calculation_date(
        vault=vault,
        effective_date=hook_arguments.effective_datetime,
        total_repayment_count=total_repayment_count,
        repayment_frequency=repayment_frequency,
    )
    remaining_term = config_repayment_frequency.get_elapsed_and_remaining_terms(
        account_creation_date=account_creation_datetime,
        effective_date=hook_arguments.effective_datetime,
        total_repayment_count=total_repayment_count,
        repayment_frequency=repayment_frequency,
    ).remaining
    remaining_term_str = (
        f"{str(remaining_term)} {config_repayment_frequency.TERM_UNIT_MAP[repayment_frequency]}"
    )

    total_outstanding_debt = derived_params.get_total_outstanding_debt(
        balances=balances,
        denomination=denomination,
    )
    total_remaining_principal = derived_params.get_total_remaining_principal(
        balances=balances, denomination=denomination
    )
    principal_paid_to_date = derived_params.get_principal_paid_to_date(
        original_principal=principal, balances=balances, denomination=denomination
    )

    derived_parameters: dict[str, utils.ParameterValueTypeAlias] = {
        PARAM_EQUATED_INSTALMENT_AMOUNT: equated_instalment_amount,
        PARAM_LOAN_END_DATE: loan_end_datetime,
        PARAM_NEXT_REPAYMENT_DATE: next_repayment_datetime,
        PARAM_REMAINING_TERM: remaining_term_str,
        PARAM_TOTAL_OUTSTANDING_DEBT: total_outstanding_debt,
        PARAM_TOTAL_REMAINING_PRINCIPAL: total_remaining_principal,
        PARAM_PRINCIPAL_PAID_TO_DATE: principal_paid_to_date,
    }

    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


def pre_parameter_change_hook(
    vault: SmartContractVault,
    hook_arguments: PreParameterChangeHookArguments,
) -> Optional[PreParameterChangeHookResult]:
    """
    Reject any change to the restricted parameters.
    """
    updated_parameter_values = hook_arguments.updated_parameter_values

    if any(parameter in updated_parameter_values for parameter in RESTRICTED_PARAMETERS):
        return PreParameterChangeHookResult(
            rejection=Rejection(
                message="T&Cs of this loan cannot be changed once opened.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

    return None


# helper functions
def _schedule_fortnightly_repayment_frequency(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
) -> list[UpdateAccountEventTypeDirective]:
    repayment_frequency = config_repayment_frequency.get_repayment_frequency_parameter(vault=vault)
    if repayment_frequency == config_repayment_frequency.FORTNIGHTLY:
        next_fortnightly_due_amount_calc_datetime = (
            config_repayment_frequency.get_next_fortnightly_schedule_expression(
                effective_date=hook_arguments.effective_datetime
            )
        )
        return [
            UpdateAccountEventTypeDirective(
                event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                expression=next_fortnightly_due_amount_calc_datetime,
            )
        ]

    return []


def _schedule_overdue_check_event(
    vault: SmartContractVault, effective_datetime: datetime
) -> list[UpdateAccountEventTypeDirective]:
    repayment_period = overdue.get_repayment_period_parameter(vault=vault)
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
            event_type=overdue.CHECK_OVERDUE_EVENT,
            expression=utils.get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=overdue.CHECK_OVERDUE_PREFIX,
                day=next_check_overdue_datetime.day,
                month=next_check_overdue_datetime.month,
                year=next_check_overdue_datetime.year,
            ),
        ),
    ]


def _schedule_check_late_repayment_event(
    vault: SmartContractVault, effective_datetime: datetime
) -> list[UpdateAccountEventTypeDirective]:
    repayment_period = overdue.get_repayment_period_parameter(vault=vault)
    grace_period = delinquency.get_grace_period_parameter(vault=vault)
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
            event_type=late_repayment.CHECK_LATE_REPAYMENT_EVENT,
            expression=utils.get_schedule_expression_from_parameters(
                vault=vault,
                parameter_prefix=late_repayment.CHECK_LATE_REPAYMENT_PREFIX,
                day=next_check_late_repayment_datetime.day,
                month=next_check_late_repayment_datetime.month,
                year=next_check_late_repayment_datetime.year,
            ),
        )
    ]


def _get_repayment_frequency_delta(vault: SmartContractVault) -> relativedelta:
    repayment_frequency = config_repayment_frequency.get_repayment_frequency_parameter(vault=vault)
    return config_repayment_frequency.FREQUENCY_MAP[repayment_frequency]


def _get_repayment_notification(
    vault: SmartContractVault, due_amount_notification_datetime: datetime
) -> list[AccountNotificationDirective]:
    # Get principal
    denomination = common_parameters.get_denomination_parameter(vault=vault)
    repayment_period = overdue.get_repayment_period_parameter(vault=vault)
    notification_period = due_amount_notification.get_notification_period_parameter(vault=vault)
    balances = vault.get_balances_observation(
        fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
    ).balances
    current_emi = due_amount_calculation.get_emi(balances=balances, denomination=denomination)
    due_amount_calculation_datetime = due_amount_notification_datetime + relativedelta(
        days=notification_period
    )
    _, remaining_term = declining_principal.term_details(
        vault=vault,
        effective_datetime=due_amount_calculation_datetime,
        use_expected_term=True,
    )
    due_principal = due_amount_calculation.calculate_due_principal(
        remaining_principal=due_amount_calculation.get_principal(
            balances=balances, denomination=denomination
        ),
        emi_interest_to_apply=Decimal("0"),
        emi=current_emi,
        is_final_due_event=remaining_term == 1,
    )
    repayment_period = overdue.get_repayment_period_parameter(vault=vault)
    notification_period = due_amount_notification.get_notification_period_parameter(vault=vault)

    return due_amount_notification.schedule_logic(
        vault=vault,
        product_name=PRODUCT_NAME,
        overdue_datetime=overdue.get_overdue_datetime(
            due_amount_notification_datetime=due_amount_notification_datetime,
            repayment_period=repayment_period,
            notification_period=notification_period,
        ),
        due_interest=Decimal("0"),
        due_principal=due_principal,
    )
