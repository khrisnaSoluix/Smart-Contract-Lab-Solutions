# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import ROUND_HALF_UP, Decimal
from json import dumps
from typing import Optional, Union

# library
import library.line_of_credit.contracts.template.drawdown_loan as drawdown_loan

# features
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.interest_accrual_common as interest_accrual_common
import library.features.v4.common.supervisor_utils as supervisor_utils
import library.features.v4.common.utils as utils
import library.features.v4.lending.amortisations.declining_principal as declining_principal
import library.features.v4.lending.close_loan as close_loan
import library.features.v4.lending.credit_limit as credit_limit
import library.features.v4.lending.delinquency as delinquency
import library.features.v4.lending.due_amount_calculation as due_amount_calculation
import library.features.v4.lending.interest_accrual_supervisor as interest_accrual_supervisor
import library.features.v4.lending.interest_application as interest_application
import library.features.v4.lending.interest_application_supervisor as interest_application_supervisor  # noqa: E501
import library.features.v4.lending.interest_rate.fixed as fixed_rate
import library.features.v4.lending.late_repayment as late_repayment
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces
import library.features.v4.lending.maximum_outstanding_loans as maximum_outstanding_loans
import library.features.v4.lending.overdue as overdue
import library.features.v4.lending.overpayment as overpayment
import library.features.v4.lending.payments as payments
import library.features.v4.lending.repayment_holiday as repayment_holiday

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    AccountNotificationDirective,
    BalanceDefaultDict,
    CustomInstruction,
    InboundHardSettlement,
    OutboundHardSettlement,
    Posting,
    PostingInstructionsDirective,
    Rejection,
    RejectionReason,
    ScheduledEvent,
    ScheduleSkip,
    SmartContractDescriptor,
    SupervisedHooks,
    SupervisionExecutionMode,
    SupervisorActivationHookArguments,
    SupervisorActivationHookResult,
    SupervisorContractEventType,
    SupervisorPostPostingHookArguments,
    SupervisorPostPostingHookResult,
    SupervisorPrePostingHookArguments,
    SupervisorPrePostingHookResult,
    SupervisorScheduledEventHookArguments,
    SupervisorScheduledEventHookResult,
    Transfer,
    Tside,
    UpdateAccountEventTypeDirective,
    UpdatePlanEventTypeDirective,
    fetch_account_data,
    requires,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SuperviseeContractVault,
    SupervisorContractVault,
)

api = "4.0.0"
version = "2.0.0"

PLAN_TYPE = "LINE_OF_CREDIT_SUPERVISOR"
LOC_ACCOUNT_TYPE = "LOC"
DRAWDOWN_LOAN_ACCOUNT_TYPE = "DRAWDOWN_LOAN"

# supervisees
LOC_ALIAS = "line_of_credit"
DRAWDOWN_LOAN_ALIAS = "drawdown_loan"

REPAYMENT_DUE_NOTIFICATION = "LOC_REPAYMENT_DUE"
DELINQUENT_NOTIFICATION = "LOC_DELINQUENT"
LOANS_PAID_OFF_NOTIFICATION = "LOC_LOANS_PAID_OFF"

supervised_smart_contracts = [
    SmartContractDescriptor(
        alias="line_of_credit",
        smart_contract_version_id="&{line_of_credit}",
        supervise_post_posting_hook=True,
        supervised_hooks=SupervisedHooks(pre_posting_hook=SupervisionExecutionMode.INVOKED),
    ),
    SmartContractDescriptor(
        alias="drawdown_loan",
        smart_contract_version_id="&{drawdown_loan}",
    ),
]

# data fetchers
data_fetchers = [
    fetchers.LIVE_BALANCES_BOF,
    *interest_accrual_supervisor.data_fetchers,
]

# events
event_types = [
    SupervisorContractEventType(
        name=interest_accrual_supervisor.ACCRUAL_EVENT,
        scheduler_tag_ids=[f"{PLAN_TYPE}_{interest_accrual_supervisor.ACCRUAL_EVENT}_AST"],
    ),
    *supervisor_utils.schedule_sync_event_types(product_name=PLAN_TYPE),
    *due_amount_calculation.supervisor_event_types(product_name=PLAN_TYPE),
    *overdue.supervisor_event_types(product_name=PLAN_TYPE),
    *delinquency.supervisor_event_types(product_name=PLAN_TYPE),
]

# balance address constants
NON_REPAYABLE_ADDRESSES = [
    lending_addresses.EMI,
    lending_addresses.DUE_CALCULATION_EVENT_COUNTER,
]

# other constants
FIXED_RATE_FEATURE = fixed_rate.interest_rate_interface


def activation_hook(
    vault: SupervisorContractVault, hook_arguments: SupervisorActivationHookArguments
) -> Optional[SupervisorActivationHookResult]:
    scheduled_events: dict[str, ScheduledEvent] = {}
    plan_opening_datetime = vault.get_plan_opening_datetime()
    month_after_opening = plan_opening_datetime.replace(hour=0, minute=0, second=0) + relativedelta(
        months=1
    )

    scheduled_events.update(supervisor_utils.supervisee_schedule_sync_scheduled_event(vault=vault))

    # here we schedule far in the future so that if the line of credit account has not been created
    # yet, we are safe that this schedule won't run until it has been created and reschedule
    # accordingly
    scheduled_events[interest_accrual_supervisor.ACCRUAL_EVENT] = utils.create_end_of_time_schedule(
        start_datetime=plan_opening_datetime
    )
    scheduled_events[
        due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
    ] = utils.create_end_of_time_schedule(start_datetime=month_after_opening)
    scheduled_events[overdue.CHECK_OVERDUE_EVENT] = utils.create_end_of_time_schedule(
        start_datetime=month_after_opening
    )
    scheduled_events[delinquency.CHECK_DELINQUENCY_EVENT] = utils.create_end_of_time_schedule(
        start_datetime=plan_opening_datetime
    )

    return SupervisorActivationHookResult(scheduled_events_return_value=scheduled_events)


@requires(
    event_type=supervisor_utils.SUPERVISEE_SCHEDULE_SYNC_EVENT,
    data_scope="all",
    parameters=True,
)
@requires(
    event_type=interest_accrual_supervisor.ACCRUAL_EVENT,
    data_scope="all",
    parameters=True,
    balances="1 days",
    last_execution_datetime=[due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT],
    flags=True,
)
@requires(
    event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
    data_scope="all",
    parameters=True,
    balances="1 days",
    last_execution_datetime=[due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT],
    flags=True,
)
@requires(
    event_type=overdue.CHECK_OVERDUE_EVENT,
    data_scope="all",
    parameters=True,
    balances="1 days",
)
@requires(
    event_type=delinquency.CHECK_DELINQUENCY_EVENT,
    data_scope="all",
    parameters=True,
    balances="1 days",
)
def scheduled_event_hook(
    vault: SupervisorContractVault, hook_arguments: SupervisorScheduledEventHookArguments
) -> Optional[SupervisorScheduledEventHookResult]:
    event_type = hook_arguments.event_type
    supervisee_pi_directives: dict[str, list[PostingInstructionsDirective]] = {}
    update_plan_event_type_directives: list[UpdatePlanEventTypeDirective] = []
    update_account_event_type_directives: dict[str, list[UpdateAccountEventTypeDirective]] = {}
    supervisee_notification_directives: dict[str, list[AccountNotificationDirective]] = {}
    loc_vault, loan_vaults = _get_loc_and_loan_supervisee_vault_objects(vault=vault)

    if event_type == supervisor_utils.SUPERVISEE_SCHEDULE_SYNC_EVENT:
        update_plan_event_type_directives = supervisor_utils.get_supervisee_schedule_sync_updates(
            vault=vault,
            supervisee_alias=LOC_ALIAS,
            hook_arguments=hook_arguments,
            schedule_updates_when_supervisees=_schedule_updates_when_supervisees,
        )

    elif loc_vault and event_type == interest_accrual_supervisor.ACCRUAL_EVENT:
        if not repayment_holiday.is_interest_accrual_blocked(
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

        # Since post_parameter_change_hook is not available in the supervisor we handle this within
        # the accrual event
        (
            update_plan_event_type_directives,
            update_account_event_type_directives,
        ) = _handle_due_amount_calculation_day_change(
            loc_vault=loc_vault,
            hook_arguments=hook_arguments,
        )

    elif loc_vault and event_type == due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT:
        if repayment_holiday.is_due_amount_calculation_blocked(
            vault=loc_vault,
            effective_datetime=hook_arguments.effective_datetime,
        ):
            # This is done by default because the line of credit will always increase emi rather
            # than term
            supervisee_pi_directives.update(
                _update_due_amount_calculation_counters(
                    loan_vaults=loan_vaults,
                    hook_arguments=hook_arguments,
                    denomination=common_parameters.get_denomination_parameter(vault=loc_vault),
                )
            )
        else:
            due_amount_custom_instructions, repayment_amount = _get_due_amount_custom_instructions(
                hook_arguments=hook_arguments,
                loc_vault=loc_vault,
                loan_vaults=loan_vaults,
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

        # capture schedule updates to due amount calculation event after a param change to the
        # calculation day, that were not already handled within the accrual event.
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

    elif loc_vault and event_type == overdue.CHECK_OVERDUE_EVENT:
        if not repayment_holiday.is_overdue_amount_calculation_blocked(
            vault=loc_vault, effective_datetime=hook_arguments.effective_datetime
        ):
            overdue_custom_instructions = _get_overdue_custom_instructions(
                hook_arguments=hook_arguments,
                loc_vault=loc_vault,
                loan_vaults=loan_vaults,
            )
            (
                overdue_principal_amount,
                overdue_interest_amount,
            ) = _get_overdue_amounts_from_instructions(
                loc_account_id=loc_vault.account_id,
                instructions_directives=overdue_custom_instructions,
                denomination=common_parameters.get_denomination_parameter(vault=loc_vault),
            )
            grace_period = delinquency.get_grace_period_parameter(vault=loc_vault)
            if overdue_principal_amount or overdue_interest_amount:
                supervisee_pi_directives.update(overdue_custom_instructions)
                supervisee_notification_directives[
                    loc_vault.account_id
                ] = overdue.get_overdue_repayment_notification(
                    account_id=loc_vault.account_id,
                    product_name=LOC_ACCOUNT_TYPE,
                    effective_datetime=hook_arguments.effective_datetime,
                    overdue_principal_amount=overdue_principal_amount,
                    overdue_interest_amount=overdue_interest_amount,
                    late_repayment_fee=late_repayment.get_late_repayment_fee_parameter(
                        vault=loc_vault
                    ),
                )
                if grace_period == 0:
                    supervisee_notification_directives[
                        loc_vault.account_id
                    ] += _get_delinquency_notification(account_id=loc_vault.account_id)

            skip_delinquency = (
                overdue_principal_amount <= Decimal("0") and overdue_interest_amount <= Decimal("0")
            ) or grace_period == 0
            update_plan_event_type_directives = _update_check_delinquency_schedule(
                loc_vault=loc_vault,
                hook_arguments=hook_arguments,
                grace_period=grace_period,
                skip=skip_delinquency,
            )

        update_plan_event_type_directives += _update_check_overdue_schedule(
            loc_vault=loc_vault, hook_arguments=hook_arguments, skip=True
        )

    elif loc_vault and event_type == delinquency.CHECK_DELINQUENCY_EVENT:
        if not repayment_holiday.is_delinquency_blocked(
            vault=loc_vault, effective_datetime=hook_arguments.effective_datetime
        ):
            supervisee_notification_directives.update(
                _handle_delinquency(
                    hook_arguments=hook_arguments,
                    loc_vault=loc_vault,
                    loan_vaults=loan_vaults,
                )
            )
        update_plan_event_type_directives = _update_check_delinquency_schedule(
            loc_vault=loc_vault,
            hook_arguments=hook_arguments,
            grace_period=delinquency.get_grace_period_parameter(vault=loc_vault),
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


@requires(parameters=True, data_scope="all")
@fetch_account_data(
    balances={
        LOC_ALIAS: [fetchers.LIVE_BALANCES_BOF_ID],
        DRAWDOWN_LOAN_ALIAS: [fetchers.LIVE_BALANCES_BOF_ID],
    }
)
def pre_posting_hook(
    vault: SupervisorContractVault, hook_arguments: SupervisorPrePostingHookArguments
) -> Optional[SupervisorPrePostingHookResult]:
    loc_vault, loan_vaults = _get_loc_and_loan_supervisee_vault_objects(vault=vault)

    if loc_vault is None:
        return SupervisorPrePostingHookResult(
            rejection=Rejection(
                message=f"Cannot process postings until a supervisee with an alias {LOC_ALIAS} is "
                "associated to the plan",
                reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
            )
        )

    # note that we only run the supervisor pre_posting hook for the line of credit supervisee
    posting_instructions = hook_arguments.supervisee_posting_instructions[loc_vault.account_id]

    if utils.is_force_override(posting_instructions=posting_instructions):
        return None

    # there are no use cases to override the line of credit supervisee rejection
    # the type ignore is needed because .get_hook_result() returns
    # Union[PostPostingHookResult, PrePostingHookResult, ScheduledEventHookResult], and
    # only the PrePostingHookResult has the .rejection attribute
    if supervisee_rejection := loc_vault.get_hook_result().rejection:  # type: ignore
        return SupervisorPrePostingHookResult(rejection=supervisee_rejection)

    # The line of credit supervisee has already asserted we have a single hard settlement
    # in the posting instructions
    posting_instruction = posting_instructions[0]
    denomination = common_parameters.get_denomination_parameter(vault=loc_vault)
    posting_amount = utils.balance_at_coordinates(
        balances=posting_instruction.balances(), denomination=denomination
    )

    # repayment
    if posting_amount <= 0:
        loan_vaults_for_repayment_distribution = _get_loan_vaults_for_repayment_distribution(
            loan_vaults=loan_vaults, posting_instruction=posting_instruction
        )
        # if you pass in a non-empty list of loan_vaults to
        # _get_loan_vaults_for_repayment_distribution and get back an empty list,
        # the only possibility is that there is a target account id on the posting
        # instruction that does not exist
        if loan_vaults and not loan_vaults_for_repayment_distribution:
            return SupervisorPrePostingHookResult(
                rejection=Rejection(
                    message="The target account id "
                    f"{posting_instruction.instruction_details.get('target_account_id')} "
                    "does not exist",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
        all_supervisee_balances = [
            vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances
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
        if rejection := maximum_outstanding_loans.validate(main_vault=loc_vault, loans=loan_vaults):
            return SupervisorPrePostingHookResult(rejection=rejection)
        if rejection := credit_limit.validate(
            main_vault=loc_vault,
            loans=loan_vaults,
            posting_instruction=posting_instruction,
            non_repayable_addresses=NON_REPAYABLE_ADDRESSES,
        ):
            return SupervisorPrePostingHookResult(rejection=rejection)

    return None


@requires(parameters=True, data_scope="all", balances="1 days")
def post_posting_hook(
    vault: SupervisorContractVault, hook_arguments: SupervisorPostPostingHookArguments
) -> Optional[SupervisorPostPostingHookResult]:
    supervisee_posting_directives: dict[str, list[PostingInstructionsDirective]] = {}
    account_notification_directives: dict[str, list[AccountNotificationDirective]] = {}

    loc_vault, loan_vaults = _get_loc_and_loan_supervisee_vault_objects(vault=vault)

    denomination = common_parameters.get_denomination_parameter(vault=loc_vault)

    posting_instructions = hook_arguments.supervisee_posting_instructions[loc_vault.account_id]
    if utils.is_force_override(posting_instructions=posting_instructions):
        # The pre_posting checks have been skipped; therefore, the assumptions made here may no
        # longer hold and the post_posting_hook should also be skipped.
        return None

    # The line of credit supervisee has already asserted we have a single settlement or transfer in
    # the posting instructions
    posting_instruction: Union[
        InboundHardSettlement, OutboundHardSettlement, Transfer
    ] = posting_instructions[0]
    posting_amount = utils.balance_at_coordinates(
        balances=posting_instruction.balances(), denomination=denomination
    )

    if posting_amount < 0:
        # The line of credit account tracks charges that are not associated with a specific drawdown
        # loan (e.g. missed payment flat penalty). It is included in the repayment distribution to
        # ensure that it is at the right level of the repayment hierarchy.
        repayment_targets = [loc_vault] + _get_loan_vaults_for_repayment_distribution(
            loan_vaults=loan_vaults, posting_instruction=posting_instruction
        )

        # Prioritise targets for repayment
        sorted_repayment_targets = supervisor_utils.sort_supervisees(supervisees=repayment_targets)

        repayment_posting_directives, repayment_notification_directives = _handle_repayment(
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


# helper functions


def _get_loan_vaults_for_repayment_distribution(
    loan_vaults: list[SuperviseeContractVault],
    posting_instruction: utils.PostingInstructionTypeAlias,
) -> list[SuperviseeContractVault]:
    target_account_id = posting_instruction.instruction_details.get("target_account_id")
    return (
        list(filter(lambda vault: vault.account_id == target_account_id, loan_vaults))
        if target_account_id
        else loan_vaults
    )


def _validate_repayment(
    loc_vault: SuperviseeContractVault,
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

    if overpayment_rejection := overpayment.validate_overpayment_across_supervisees(
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
    sorted_repayment_targets: list[SuperviseeContractVault],
    loc_vault: SuperviseeContractVault,
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
    balances_per_target = supervisor_utils.get_balances_default_dicts_from_timeseries(
        supervisees=sorted_repayment_targets,
        effective_datetime=hook_arguments.effective_datetime,
    )

    (
        repayments_custom_instructions_per_target
    ) = payments.generate_repayment_postings_for_multiple_targets(
        main_vault=loc_vault,
        sorted_repayment_targets=sorted_repayment_targets,
        hook_arguments=hook_arguments,
        repayment_hierarchy=[[address] for address in lending_addresses.REPAYMENT_HIERARCHY],
        overpayment_features=[
            lending_interfaces.MultiTargetOverpayment(handle_overpayment=_handle_overpayment)
        ],
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
        # Line of Credit postings will be handled separately with the aggregated postings
        if target_vault != loc_vault
    }

    aggregated_repayments_custom_instructions = _aggregate_repayment_postings(
        repayments_custom_instructions_per_target=repayments_custom_instructions_per_target,
        loc_vault=loc_vault,
        loc_balances=balances_per_target[loc_vault.account_id],
    )

    if (
        loc_posting_instructions := repayments_custom_instructions_per_target[loc_vault.account_id]
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

    return posting_directives, closure_notification_directives


def _handle_overpayment(
    main_vault: SuperviseeContractVault,
    overpayment_amount: Decimal,
    denomination: str,
    balances_per_target_vault: dict[SuperviseeContractVault, BalanceDefaultDict],
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

    overpayment_fee_rate = overpayment.get_overpayment_fee_rate_parameter(vault=main_vault)

    # If the overpayment amount covers the principal as well as the accrued interest, then
    # overpayment.get_overpayment_fee() will return a value that exceeds that maximum overpayment
    # fee
    overpayment_fee = min(
        overpayment.get_overpayment_fee(
            principal_repaid=overpayment_amount,
            overpayment_fee_rate=overpayment_fee_rate,
            precision=2,  # TODO: change after INC-9649
        ),
        overpayment.get_max_overpayment_fee(
            fee_rate=overpayment_fee_rate,
            balances=merged_balances,
            denomination=denomination,
            precision=2,  # TODO: change after INC-9649
        ),
    )

    overpayment_excluding_fee = overpayment_amount - overpayment_fee

    overpayment_postings_per_target = _distribute_overpayment(
        overpayment_amount=overpayment_excluding_fee,
        denomination=denomination,
        balances_per_loan_vault={
            loan_vault: balances
            for loan_vault, balances in balances_per_target_vault.items()
            if loan_vault != main_vault
        },
    )

    overpayment_postings_per_target[
        main_vault.account_id
    ] = overpayment.get_overpayment_fee_postings(
        overpayment_fee=overpayment_fee,
        denomination=denomination,
        customer_account_id=main_vault.account_id,
        customer_account_address=DEFAULT_ADDRESS,
        internal_account=overpayment.get_overpayment_fee_income_account_parameter(vault=main_vault),
    )

    return overpayment_postings_per_target


def _distribute_overpayment(
    overpayment_amount: Decimal,
    denomination: str,
    balances_per_loan_vault: dict[SuperviseeContractVault, BalanceDefaultDict],
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
    overpayment_hierarchy = lending_addresses.OVERPAYMENT_HIERARCHY_SUPERVISOR

    overpayments_per_loan, _ = payments.distribute_repayment_for_multiple_targets(
        balances_per_target={
            loan_vault.account_id: balances
            for loan_vault, balances in balances_per_loan_vault.items()
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
        lending_addresses.ACCRUED_INTEREST_RECEIVABLE,
        lending_addresses.NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
    ]

    for loan_vault, overpayment_amounts_per_address in overpayments_per_loan_vault.items():
        overpayment_postings_per_loan[loan_vault.account_id] = []
        accrued_interest_repayment_amount = Decimal("0")
        for address, amounts in overpayment_amounts_per_address.items():
            if (address == lending_addresses.PRINCIPAL) and (amounts.rounded_amount > Decimal("0")):
                overpayment_postings_per_loan[
                    loan_vault.account_id
                ] += payments.redistribute_postings(
                    debit_account=loan_vault.account_id,
                    amount=amounts.rounded_amount,
                    denomination=denomination,
                    credit_account=loan_vault.account_id,
                    credit_address=address,
                    debit_address=lending_addresses.INTERNAL_CONTRA,
                )

                # Update trackers
                overpayment_postings_per_loan[loan_vault.account_id] += utils.create_postings(
                    amount=amounts.rounded_amount,
                    debit_account=loan_vault.account_id,
                    debit_address=overpayment.OVERPAYMENT,
                    credit_account=loan_vault.account_id,
                    credit_address=lending_addresses.INTERNAL_CONTRA,
                    denomination=denomination,
                )
                overpayment_postings_per_loan[loan_vault.account_id] += utils.create_postings(
                    amount=amounts.rounded_amount,
                    debit_account=loan_vault.account_id,
                    debit_address=overpayment.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
                    credit_account=loan_vault.account_id,
                    credit_address=lending_addresses.INTERNAL_CONTRA,
                    denomination=denomination,
                )

            elif address in accrued_interest_addresses:
                accrued_interest_repayment_amount += amounts.unrounded_amount

        overpayment_postings_per_loan[
            loan_vault.account_id
        ] += interest_application_supervisor.repay_accrued_interest(
            vault=loan_vault,
            repayment_amount=accrued_interest_repayment_amount,
            denomination=denomination,
            balances=balances_per_loan_vault[loan_vault],
            application_customer_address=lending_addresses.INTERNAL_CONTRA,
        )

    return overpayment_postings_per_loan


def _aggregate_repayment_postings(
    repayments_custom_instructions_per_target: dict[str, list[CustomInstruction]],
    loc_vault: SuperviseeContractVault,
    loc_balances: BalanceDefaultDict,
) -> list[CustomInstruction]:
    # Aggregate postings for drawdown loans only
    instructions_per_loan = {
        target_account_id: instructions
        for target_account_id, instructions in repayments_custom_instructions_per_target.items()
        if target_account_id != loc_vault.account_id
    }

    flat_overpayment_hierarchy = [
        address
        for address_list in lending_addresses.OVERPAYMENT_HIERARCHY_SUPERVISOR
        for address in address_list
    ]
    if aggregate_posting_instructions := supervisor_utils.create_aggregate_posting_instructions(
        aggregate_account_id=loc_vault.account_id,
        posting_instructions_by_supervisee=instructions_per_loan,
        prefix="TOTAL",
        balances=loc_balances,
        addresses_to_aggregate=[
            *lending_addresses.REPAYMENT_HIERARCHY,
            *flat_overpayment_hierarchy,
        ],
        # This is an internal posting so the hooks are not triggered
        force_override=False,
    ):
        return aggregate_posting_instructions

    return []


def _get_loans_closure_notification_directives(
    loc_vault: SuperviseeContractVault,
    repayments_custom_instructions_per_target: dict[str, list[CustomInstruction]],
    balances_per_target: dict[str, BalanceDefaultDict],
    denomination: str,
) -> dict[str, list[AccountNotificationDirective]]:
    notification_directives: dict[str, list[AccountNotificationDirective]] = {}

    # Extract instructions for drawdown loans only
    repayments_custom_instructions_per_loan = {
        account_id: instructions
        for account_id, instructions in repayments_custom_instructions_per_target.items()
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
    loc_vault: SuperviseeContractVault,
    hook_arguments: SupervisorScheduledEventHookArguments,
) -> list[UpdatePlanEventTypeDirective]:
    """
    Used to determine required schedule updates when the supervisee line of credit account is
    first associated to the plan.
    """
    return [
        # schedule for daily interest accrual
        UpdatePlanEventTypeDirective(
            event_type=interest_accrual_supervisor.ACCRUAL_EVENT,
            expression=utils.get_schedule_expression_from_parameters(
                vault=loc_vault,
                parameter_prefix=interest_accrual_supervisor.INTEREST_ACCRUAL_PREFIX,
            ),
            skip=False,
        ),
        # schedule for monthly due amount calculation
        UpdatePlanEventTypeDirective(
            event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
            schedule_method=utils.get_end_of_month_schedule_from_parameters(
                vault=loc_vault,
                parameter_prefix=due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX,
            ),
            skip=False,
        ),
    ]


def _handle_accrue_interest(
    vault: SupervisorContractVault,
    hook_arguments: SupervisorScheduledEventHookArguments,
    loc_vault: SuperviseeContractVault,
    loan_vaults: list[SuperviseeContractVault],
) -> dict[str, list[PostingInstructionsDirective]]:
    supervisee_pi_directives = {}
    posting_instructions_by_supervisee = {}

    denomination = common_parameters.get_denomination_parameter(vault=loc_vault)
    last_execution_datetime = loc_vault.get_last_execution_datetime(
        event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
    )
    next_due_calc_datetime = due_amount_calculation.get_actual_next_repayment_date(
        vault=loc_vault,
        effective_datetime=hook_arguments.effective_datetime,
        # Hardcode elapsed_term to 1 if the event has run previously, and remaining_term to 1,
        # since both are only checked for non zero. There is no concept of remaining_term here.
        elapsed_term=1 if last_execution_datetime else 0,
        remaining_term=1,
    )
    for loan in loan_vaults:
        # there must be a minimum of 1 month from loan opening before amounts are made due for
        # each loan
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
    balances = utils.get_balance_default_dict_from_mapping(
        mapping=balances_mapping,
        effective_datetime=midnight,
    )

    if interest_aggregate_custom_instructions := (
        supervisor_utils.create_aggregate_posting_instructions(
            aggregate_account_id=loc_vault.account_id,
            posting_instructions_by_supervisee=posting_instructions_by_supervisee,
            prefix="TOTAL",
            balances=balances,
            addresses_to_aggregate=[
                lending_addresses.ACCRUED_INTEREST_RECEIVABLE,
                lending_addresses.NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
                lending_addresses.PENALTIES,
            ],
            rounding_precision=_get_application_precision_parameter(loan_vaults=loan_vaults),
        )
    ):
        supervisee_pi_directives.update(
            {
                loc_vault.account_id: [
                    PostingInstructionsDirective(
                        posting_instructions=interest_aggregate_custom_instructions,
                        client_batch_id=f"AGGREGATE_LOC_{LOC_ACCOUNT_TYPE}_INTEREST_ACCRUAL_"
                        f"{vault.get_hook_execution_id()}",
                        value_datetime=hook_arguments.effective_datetime,
                    )
                ]
            }
        )

    return supervisee_pi_directives


def _get_standard_interest_accrual_custom_instructions(
    vault: SuperviseeContractVault,
    hook_arguments: SupervisorScheduledEventHookArguments,
    next_due_amount_calculation_datetime: datetime,
    denomination: Optional[str] = None,
) -> list[CustomInstruction]:
    midnight = hook_arguments.effective_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    balances_mapping = vault.get_balances_timeseries()
    balances = utils.get_balance_default_dict_from_mapping(
        mapping=balances_mapping,
        effective_datetime=midnight,
    )

    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    return interest_accrual_supervisor.daily_accrual_logic(
        vault=vault,
        hook_arguments=hook_arguments,
        next_due_amount_calculation_datetime=next_due_amount_calculation_datetime,
        account_type=DRAWDOWN_LOAN_ACCOUNT_TYPE,
        interest_rate_feature=FIXED_RATE_FEATURE,
        balances=balances,
        denomination=denomination,
    ) + overpayment.track_interest_on_expected_principal(
        vault=vault,
        hook_arguments=hook_arguments,
        interest_rate_feature=FIXED_RATE_FEATURE,
        balances=balances,
        denomination=denomination,
    )


# TODO: the interface for this function and _get_standard_interest_accrual_custom_instructions
# above should more closely conform to the inception guidance for feature interfaces
# e.g. passing in an optional balances param and interest rate feature
# this should be considered when implementing https://pennyworth.atlassian.net/browse/INC-9624
def _get_penalty_interest_accrual_custom_instructions(
    loan_vault: SuperviseeContractVault,
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
    balances = utils.get_balance_default_dict_from_mapping(
        mapping=loan_vault.get_balances_timeseries(),
        effective_datetime=midnight,
    )

    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=loan_vault)

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

    balance_to_accrue_on = utils.sum_balances(
        balances=balances,
        addresses=[lending_addresses.INTEREST_OVERDUE, lending_addresses.PRINCIPAL_OVERDUE],
        denomination=denomination,
    )

    return interest_accrual_common.daily_accrual(
        customer_account=loan_vault.account_id,
        customer_address=lending_addresses.PENALTIES,
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
    hook_arguments: SupervisorScheduledEventHookArguments,
    loc_vault: SuperviseeContractVault,
    loan_vaults: list[SuperviseeContractVault],
) -> tuple[dict[str, list[PostingInstructionsDirective]], Decimal]:
    """
    Gets transfer due instructions for each loan supervisee and instructs the transfer
    due PIB for each loan. It also aggregates the due instructions across all loans
    and updates the Line of Credit supervisee total balances.
    Returns the total repayment amount across all loans in addition to the supervisee instructions.
    """
    supervisee_pi_directives: dict[str, list[PostingInstructionsDirective]] = {}

    denomination = common_parameters.get_denomination_parameter(vault=loc_vault)
    total_repayment_amount = Decimal("0")
    application_precision = _get_application_precision_parameter(loan_vaults=loan_vaults)
    instructions_for_aggregation: dict[str, list[CustomInstruction]] = {}

    supervisees_balances = supervisor_utils.get_balances_default_dicts_from_timeseries(
        supervisees=[loc_vault] + loan_vaults, effective_datetime=hook_arguments.effective_datetime
    )

    for loan_vault in loan_vaults:
        # Exclude loans that are less than a month old as they haven't completed a
        # cycle yet. Using account_creation_date as loan_start_date value can change over time.
        # .date() is used so that time components do not affect this logic:
        # - the cut-off for inclusion is at midnight of the due amount calculation day, regardless
        #  of when the schedule runs
        # - all accounts created between 00:00:00 and 23:59:59 of a given day will have the same
        # number of accruals by due amount calculation date, so this shouldn't affect inclusion
        if (
            loan_vault.get_account_creation_datetime() + relativedelta(months=1)
        ).date() > hook_arguments.effective_datetime.date():
            continue

        loan_balances = supervisees_balances[loan_vault.account_id]
        application_feature = interest_application_supervisor.interest_application_interface
        supervisee_instructions = due_amount_calculation.supervisor_schedule_logic(
            loan_vault=loan_vault,
            main_vault=loc_vault,
            hook_arguments=hook_arguments,
            account_type=LOC_ACCOUNT_TYPE,
            interest_application_feature=application_feature,
            reamortisation_condition_features=[
                repayment_holiday.SupervisorReamortisationConditionWithoutPreference,
                overpayment.SupervisorOverpaymentReamortisationCondition,
            ],
            amortisation_feature=declining_principal.SupervisorAmortisationFeature,
            interest_rate_feature=FIXED_RATE_FEATURE,
            principal_adjustment_features=[overpayment.SupervisorOverpaymentPrincipalAdjustment],
            balances=loan_balances,
            denomination=denomination,
        )
        (elapsed_term, _,) = declining_principal.supervisor_term_details(
            main_vault=loc_vault,
            loan_vault=loan_vault,
            effective_datetime=hook_arguments.effective_datetime,
            interest_rate=FIXED_RATE_FEATURE,
            balances=loan_balances,
        )
        previous_application_datetime = (
            due_amount_calculation.get_supervisee_last_execution_effective_datetime(
                main_vault=loc_vault,
                loan_vault=loan_vault,
                event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                effective_datetime=hook_arguments.effective_datetime,
                elapsed_term=elapsed_term,
            )
        )

        supervisee_instructions += overpayment.track_emi_principal_excess(
            vault=loan_vault,
            interest_application_feature=application_feature,
            effective_datetime=hook_arguments.effective_datetime,
            previous_application_datetime=previous_application_datetime,
            balances=loan_balances,
            denomination=denomination,
        )
        supervisee_instructions += overpayment.reset_due_amount_calc_overpayment_trackers(
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
                    client_batch_id=f"{due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT}_"
                    f"{loan_vault.get_hook_execution_id()}",
                    batch_details={
                        "event": f"{due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT}"
                    },
                )
            ]

    # get the aggregate postings
    loc_balances = supervisees_balances[loc_vault.account_id]
    if aggregated_instructions := supervisor_utils.create_aggregate_posting_instructions(
        aggregate_account_id=loc_vault.account_id,
        posting_instructions_by_supervisee=instructions_for_aggregation,
        prefix="TOTAL",
        balances=loc_balances,
        addresses_to_aggregate=[
            lending_addresses.PRINCIPAL,
            lending_addresses.PRINCIPAL_DUE,
            lending_addresses.INTEREST_DUE,
            lending_addresses.EMI,
            lending_addresses.ACCRUED_INTEREST_RECEIVABLE,
            lending_addresses.NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
        ],
        rounding_precision=application_precision,
    ):
        supervisee_pi_directives[loc_vault.account_id] = [
            PostingInstructionsDirective(
                posting_instructions=aggregated_instructions,
                value_datetime=hook_arguments.effective_datetime,
                client_batch_id=f"{due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT}_"
                f"{loc_vault.get_hook_execution_id()}",
                batch_details={"event": f"{due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT}"},
            )
        ]

    return supervisee_pi_directives, total_repayment_amount


def _get_total_repayment_amount_for_loan(
    loan_account_id: str, custom_instructions: list[CustomInstruction], denomination: str
) -> Decimal:
    """
    Sum the new due amounts from the repayment postings for a given draw down loan.
    The fetched balances themselves wouldn't reflect the latest changes.
    """
    return Decimal(
        sum(
            utils.sum_balances(
                balances=instruction.balances(account_id=loan_account_id, tside=Tside.ASSET),
                addresses=[lending_addresses.PRINCIPAL_DUE, lending_addresses.INTEREST_DUE],
                denomination=denomination,
            )
            for instruction in custom_instructions
        )
    )


def _get_repayment_due_notification(
    loc_vault: SuperviseeContractVault,
    repayment_amount: Decimal,
    hook_arguments: SupervisorScheduledEventHookArguments,
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
    loc_vault: SuperviseeContractVault,
    hook_arguments: SupervisorScheduledEventHookArguments,
    skip: bool = False,
) -> list[UpdatePlanEventTypeDirective]:
    """
    If skip is True, return a simple event update to skip the check overdue event.
    Otherwise, schedule the check overdue event according the repayment period number of days.
    """
    if skip:
        return [UpdatePlanEventTypeDirective(event_type=overdue.CHECK_OVERDUE_EVENT, skip=skip)]

    repayment_period = _get_repayment_period_parameter(loc_vault=loc_vault)
    overdue_date = hook_arguments.effective_datetime + relativedelta(days=repayment_period)
    return [
        UpdatePlanEventTypeDirective(
            event_type=overdue.CHECK_OVERDUE_EVENT,
            expression=utils.get_schedule_expression_from_parameters(
                vault=loc_vault,
                parameter_prefix=overdue.CHECK_OVERDUE_PREFIX,
                day=overdue_date.day,
            ),
            skip=skip,
        )
    ]


def _update_check_delinquency_schedule(
    loc_vault: SuperviseeContractVault,
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
            UpdatePlanEventTypeDirective(event_type=delinquency.CHECK_DELINQUENCY_EVENT, skip=True)
        ]
    else:
        delinquency_date = hook_arguments.effective_datetime + relativedelta(days=grace_period)
        return [
            UpdatePlanEventTypeDirective(
                event_type=delinquency.CHECK_DELINQUENCY_EVENT,
                expression=utils.get_schedule_expression_from_parameters(
                    vault=loc_vault,
                    parameter_prefix=delinquency.CHECK_DELINQUENCY_PREFIX,
                    day=delinquency_date.day,
                ),
                skip=False,
            )
        ]


def _get_overdue_custom_instructions(
    hook_arguments: SupervisorScheduledEventHookArguments,
    loc_vault: SuperviseeContractVault,
    loan_vaults: list[SuperviseeContractVault],
) -> dict[str, list[PostingInstructionsDirective]]:
    """
    Gets overdue instructions for each loan supervisee and instructs the transfer overdue PIB
    for each loan. It also aggregates the overdue instructions across all loans and updates the
    Line of Credit supervisee total balances.
    """
    supervisee_pi_directives: dict[str, list[PostingInstructionsDirective]] = {}

    # TODO INC-8842 implement repayment holiday
    # if repayment_holiday.is_due_amount_calculation_blocked(
    #     loc_vault, hook_arguments.effective_datetime
    # ):
    #     return {}, Decimal("0")

    denomination = common_parameters.get_denomination_parameter(vault=loc_vault)
    application_precision = _get_application_precision_parameter(loan_vaults=loan_vaults)
    instructions_for_aggregation: dict[str, list[CustomInstruction]] = {}

    supervisees_balances = supervisor_utils.get_balances_default_dicts_from_timeseries(
        supervisees=[loc_vault] + loan_vaults, effective_datetime=hook_arguments.effective_datetime
    )

    for loan_vault in loan_vaults:
        loan_balances = supervisees_balances[loan_vault.account_id]
        supervisee_instructions, _ = overdue.schedule_logic(
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
                client_batch_id=f"{hook_arguments.event_type}_"
                f"{loan_vault.get_hook_execution_id()}",
                batch_details={"event": f"{hook_arguments.event_type}"},
            )
        ]
    if not instructions_for_aggregation:
        return {}

    loc_balances = supervisees_balances[loc_vault.account_id]
    if aggregated_instructions := supervisor_utils.create_aggregate_posting_instructions(
        aggregate_account_id=loc_vault.account_id,
        posting_instructions_by_supervisee=instructions_for_aggregation,
        prefix="TOTAL",
        balances=loc_balances,
        addresses_to_aggregate=[
            lending_addresses.PRINCIPAL_DUE,
            lending_addresses.PRINCIPAL_OVERDUE,
            lending_addresses.INTEREST_DUE,
            lending_addresses.INTEREST_OVERDUE,
        ],
        rounding_precision=application_precision,
    ):
        late_repayment_fee_instructions = late_repayment.schedule_logic(
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
                client_batch_id=f"{hook_arguments.event_type}_"
                f"{loc_vault.get_hook_execution_id()}",
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
        return Decimal("0"), Decimal("0")
    overdue_principal_amount = Decimal(
        sum(
            utils.balance_at_coordinates(
                balances=instruction.balances(account_id=loc_account_id, tside=Tside.ASSET),
                address=f"TOTAL_{lending_addresses.PRINCIPAL_OVERDUE}",
                denomination=denomination,
            )
            for instruction in loc_posting_instructions
        )
    )
    overdue_interest_amount = Decimal(
        sum(
            utils.balance_at_coordinates(
                balances=instruction.balances(account_id=loc_account_id, tside=Tside.ASSET),
                address=f"TOTAL_{lending_addresses.INTEREST_OVERDUE}",
                denomination=denomination,
            )
            for instruction in loc_posting_instructions
        )
    )
    return overdue_principal_amount, overdue_interest_amount


def _handle_delinquency(
    hook_arguments: SupervisorScheduledEventHookArguments,
    loc_vault: SuperviseeContractVault,
    loan_vaults: list[SuperviseeContractVault],
) -> dict[str, list[AccountNotificationDirective]]:
    """
    A Line of Credit is considered delinquent if any of the loans have overdue amounts for a
    duration beyond grace period. Here we check any of the loans to see if they still have an
    overdue balance, and return the delinquency notification if so. No further action is needed
    in the contract, as this would reside within downstream services that would consume this
    notification.
    """
    denomination = common_parameters.get_denomination_parameter(vault=loc_vault)
    for loan_vault in loan_vaults:
        loan_vault_balances = utils.get_balance_default_dict_from_mapping(
            mapping=loan_vault.get_balances_timeseries(),
            effective_datetime=hook_arguments.effective_datetime,
        )
        if utils.sum_balances(
            balances=loan_vault_balances,
            addresses=lending_addresses.OVERDUE_ADDRESSES,
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
            notification_details={
                "account_id": account_id,
            },
        )
    ]


def _get_loc_and_loan_supervisee_vault_objects(
    vault: SupervisorContractVault,
) -> tuple[Optional[SuperviseeContractVault], list[SuperviseeContractVault]]:
    loc_vault = _get_loc_vault(vault=vault)
    loan_vaults = supervisor_utils.get_supervisees_for_alias(vault=vault, alias=DRAWDOWN_LOAN_ALIAS)
    return loc_vault, loan_vaults


def _get_loc_vault(
    vault: SupervisorContractVault,
) -> Optional[SuperviseeContractVault]:
    supervisees = supervisor_utils.get_supervisees_for_alias(vault=vault, alias=LOC_ALIAS)
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
    for (
        loan_account_id,
        repayment_instructions,
    ) in repayment_custom_instructions_per_loan.items():
        if close_loan.does_repayment_fully_repay_loan(
            repayment_posting_instructions=repayment_instructions,
            balances=balances_per_target[loan_account_id],
            denomination=denomination,
            account_id=loan_account_id,
            debt_addresses=lending_addresses.ALL_OUTSTANDING_SUPERVISOR,
            payment_addresses=lending_addresses.ALL_OUTSTANDING_SUPERVISOR,
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
    loc_vault: SuperviseeContractVault,
    hook_arguments: SupervisorScheduledEventHookArguments,
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
        event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT
    )
    param_timeseries = loc_vault.get_parameter_timeseries(
        name=due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
    ).all()
    if not last_execution_datetime or len(param_timeseries) == 1:
        # the parameter shouldn't be allowed to change before the first due amount calculation
        # (i.e. len(param_timeseries) > 1 and last_execution_datetime not None), and as a fail-safe
        # we exit early if it was allowed
        return [], {}

    latest_param_update_datetime = param_timeseries[-1].at_datetime
    latest_due_amount_calculation_day = param_timeseries[-1].value

    if latest_param_update_datetime <= last_execution_datetime:
        # since the param was updated before the last execution of the due calc event, this param
        # change would have already been handled.
        return [], {}

    next_due_calc_datetime = due_amount_calculation.get_next_due_amount_calculation_datetime(
        vault=loc_vault,
        effective_datetime=hook_arguments.effective_datetime,
        # Hardcode elapsed_term and remaining_term to 1 since they are only checked for non zero.
        # We already know elapsed_term is > 0 since it is not allowed to change the param before
        # the first due calc event, and there is no concept of remaining_term on the line of credit.
        elapsed_term=1,
        remaining_term=1,
    )

    if next_due_calc_datetime != last_execution_datetime + relativedelta(months=1):
        return _update_due_amount_calculation_day_schedule(
            loc_vault=loc_vault,
            schedule_start_datetime=next_due_calc_datetime,
            due_amount_calculation_day=latest_due_amount_calculation_day,
        )

    return [], {}


def _update_due_amount_calculation_day_schedule(
    loc_vault: SuperviseeContractVault,
    schedule_start_datetime: datetime,
    due_amount_calculation_day: int,
) -> tuple[list[UpdatePlanEventTypeDirective], dict[str, list[UpdateAccountEventTypeDirective]],]:
    """
    Create event update directives for the due amount calculation event for both the plan schedule
    and the line of credit account schedule. The latter is a dummy event which is only used to
    enable the last execution datetime to be used by the supervisor.
    """
    end_of_month_schedule = utils.get_end_of_month_schedule_from_parameters(
        vault=loc_vault,
        parameter_prefix=due_amount_calculation.DUE_AMOUNT_CALCULATION_PREFIX,
        day=due_amount_calculation_day,
    )
    # we can't delay the start datetime in the Directive, so we skip until 1 second before the
    # updated start datetime to ensure we don't run a monthly event before we anticipate.
    schedule_skip = ScheduleSkip(end=schedule_start_datetime - relativedelta(seconds=1))
    return [
        UpdatePlanEventTypeDirective(
            event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
            schedule_method=end_of_month_schedule,
            skip=schedule_skip,
        )
    ], {
        loc_vault.account_id: [
            UpdateAccountEventTypeDirective(
                event_type=due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                schedule_method=end_of_month_schedule,
                skip=schedule_skip,
            )
        ]
    }


def _update_due_amount_calculation_counters(
    loan_vaults: list[SuperviseeContractVault],
    hook_arguments: SupervisorScheduledEventHookArguments,
    denomination: str,
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
                postings=due_amount_calculation.update_due_amount_calculation_counter(
                    account_id=loan_vault.account_id, denomination=denomination
                ),
                instruction_details=utils.standard_instruction_details(
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


# parameter getters
def _get_application_precision_parameter(
    *, loan_vaults: list[SuperviseeContractVault], effective_datetime: Optional[datetime] = None
) -> int:
    return (
        int(
            utils.get_parameter(
                vault=loan_vaults[0],
                name=interest_application.PARAM_APPLICATION_PRECISION,
                at_datetime=effective_datetime,
            )
        )
        if loan_vaults
        else 2
    )


def _get_days_in_year_parameter(
    *, loan_vault: SuperviseeContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    return utils.get_parameter(
        vault=loan_vault,
        name=interest_accrual_common.PARAM_DAYS_IN_YEAR,
        at_datetime=effective_datetime,
    )


def _get_penalty_includes_base_rate_parameter(
    *, loan_vault: SuperviseeContractVault, effective_datetime: Optional[datetime] = None
) -> bool:
    return utils.get_parameter(
        vault=loan_vault,
        name=drawdown_loan.PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE,
        is_boolean=True,
        at_datetime=effective_datetime,
    )


def _get_penalty_interest_income_account_parameter(
    *, loan_vault: SuperviseeContractVault, effective_datetime: Optional[datetime] = None
) -> str:
    return utils.get_parameter(
        vault=loan_vault,
        name=drawdown_loan.PARAM_PENALTY_INTEREST_INCOME_ACCOUNT,
        at_datetime=effective_datetime,
    )


def _get_penalty_interest_rate_parameter(
    *, loan_vault: SuperviseeContractVault, effective_datetime: Optional[datetime] = None
) -> Decimal:
    return utils.get_parameter(
        vault=loan_vault,
        name=drawdown_loan.PARAM_PENALTY_INTEREST_RATE,
        at_datetime=effective_datetime,
    )


def _get_repayment_period_parameter(
    *, loc_vault: SuperviseeContractVault, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils.get_parameter(
            vault=loc_vault, name=overdue.PARAM_REPAYMENT_PERIOD, at_datetime=effective_datetime
        )
    )


def _get_due_amount_calculation_day_parameter(
    *, loc_vault: SuperviseeContractVault, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils.get_parameter(
            vault=loc_vault,
            name=due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY,
            at_datetime=effective_datetime,
        )
    )
