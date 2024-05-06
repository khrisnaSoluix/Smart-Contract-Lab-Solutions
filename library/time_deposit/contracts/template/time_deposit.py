# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

# features
import library.features.v4.common.addresses as common_addresses
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.deposit.cooling_off_period as cooling_off_period
import library.features.v4.deposit.deposit_interfaces as deposit_interfaces
import library.features.v4.deposit.deposit_maturity as deposit_maturity
import library.features.v4.deposit.deposit_parameters as deposit_parameters
import library.features.v4.deposit.deposit_period as deposit_period
import library.features.v4.deposit.fees.withdrawal.withdrawal_fees as withdrawal_fees
import library.features.v4.deposit.grace_period as grace_period
import library.features.v4.deposit.interest.fixed_interest_accrual as fixed_interest_accrual
import library.features.v4.deposit.interest.interest_application as interest_application
import library.features.v4.deposit.transaction_limits.deposit_limits.maximum_balance_limit as maximum_balance_limit  # noqa: E501
import library.features.v4.deposit.transaction_limits.deposit_limits.minimum_initial_deposit as minimum_initial_deposit  # noqa: E501

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
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
    NumberShape,
    OptionalShape,
    OptionalValue,
    Parameter,
    ParameterLevel,
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
    Tside,
    UpdateAccountEventTypeDirective,
    fetch_account_data,
    requires,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

api = "4.0.0"
version = "2.0.0"
display_name = "Time Deposit"
summary = (
    "A savings account paying a fixed rate of interest when money is put away"
    "for a defined period of time."
)
tside = Tside.LIABILITY

# this can be amended to whichever other currencies as needed
supported_denominations = ["GBP"]

# product constants
PRODUCT_NAME = "TIME_DEPOSIT"

# Addresses
APPLIED_INTEREST_TRACKER = "APPLIED_INTEREST_TRACKER"

# Events
ACCOUNT_CLOSURE_EVENT = "ACCOUNT_CLOSURE"

# Fetchers
data_fetchers = [
    fetchers.LIVE_BALANCES_BOF,
    fetchers.EFFECTIVE_OBSERVATION_FETCHER,
    fetchers.EOD_FETCHER,
    withdrawal_fees.EARLY_WITHDRAWALS_TRACKER_LIVE_FETCHER,
]

# Notifications
ACCOUNT_MATURITY_NOTIFICATION = deposit_maturity.notification_type_at_account_maturity(
    product_name=PRODUCT_NAME
)
DEPOSIT_PERIOD_NOTIFICATION = deposit_period.notification_type(product_name=PRODUCT_NAME)
FULL_WITHDRAWAL_NOTIFICATION = f"{PRODUCT_NAME}_FULL_WITHDRAWAL"
GRACE_PERIOD_NOTIFICATION = grace_period.notification_type(product_name=PRODUCT_NAME)
NOTIFY_UPCOMING_MATURITY_NOTIFICATION = deposit_maturity.notification_type_notify_upcoming_maturity(
    product_name=PRODUCT_NAME
)
WITHDRAWAL_FEES_NOTIFICATION = withdrawal_fees.notification_type(product_name=PRODUCT_NAME)

notification_types = [
    ACCOUNT_MATURITY_NOTIFICATION,
    DEPOSIT_PERIOD_NOTIFICATION,
    FULL_WITHDRAWAL_NOTIFICATION,
    GRACE_PERIOD_NOTIFICATION,
    NOTIFY_UPCOMING_MATURITY_NOTIFICATION,
    WITHDRAWAL_FEES_NOTIFICATION,
]

# Events
event_types = [
    *interest_application.event_types(product_name=PRODUCT_NAME),
    *fixed_interest_accrual.event_types(product_name=PRODUCT_NAME),
    *deposit_period.event_types(product_name=PRODUCT_NAME),
    *grace_period.event_types(product_name=PRODUCT_NAME),
    *deposit_maturity.event_types(product_name=PRODUCT_NAME),
]


# Parameters
PARAM_NUMBER_OF_INTEREST_DAYS_EARLY_WITHDRAWAL_FEE = "number_of_interest_days_early_withdrawal_fee"
number_of_interest_days_early_withdrawal_fee_parameter = Parameter(
    name=PARAM_NUMBER_OF_INTEREST_DAYS_EARLY_WITHDRAWAL_FEE,
    shape=OptionalShape(shape=NumberShape(min_value=Decimal("0"), step=Decimal("1"))),
    level=ParameterLevel.TEMPLATE,
    description="The number of days of interest to be charged as a fee when making an "
    "early withdrawal. If this is configured, the Early Withdrawal Percentage Fee is ignored.",
    display_name="Number Of Days Of Interest To Be Charged As An Early Withdrawal Fee",
    default_value=OptionalValue(Decimal("0")),
)

parameters = [
    # Instance parameters
    # Template parameters
    number_of_interest_days_early_withdrawal_fee_parameter,
    # Derived parameters
    # Common parameters
    common_parameters.denomination_parameter,
    *deposit_parameters.term_parameters,
    # Feature parameters
    *cooling_off_period.parameters,
    *deposit_maturity.maturity_parameters,
    *deposit_period.parameters,
    *fixed_interest_accrual.positive_fixed_interest_parameters,
    *grace_period.parameters,
    *interest_application.parameters,
    *maximum_balance_limit.parameters,
    *minimum_initial_deposit.parameters,
    *withdrawal_fees.parameters,
]


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def activation_hook(
    vault: SmartContractVault, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    schedule_start_datetime = effective_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + relativedelta(days=1)

    scheduled_events: dict[str, ScheduledEvent] = {}

    if _is_renewed_time_deposit(vault=vault, effective_datetime=effective_datetime):
        interest_application_start_datetime = grace_period.get_grace_period_end_datetime(
            vault=vault
        )
        # include grace period schedule
        scheduled_events.update(grace_period.scheduled_events(vault=vault))
        # deposit period is not valid for renewed time deposit and so an
        # end-of-time schedule is created that never runs
        scheduled_events[
            deposit_period.DEPOSIT_PERIOD_END_EVENT
        ] = utils.create_end_of_time_schedule(start_datetime=schedule_start_datetime)

    else:
        interest_application_start_datetime = max(
            deposit_period.get_deposit_period_end_datetime(vault=vault),
            cooling_off_period.get_cooling_off_period_end_datetime(vault=vault),
        )
        # include deposit period schedule as new time deposit
        scheduled_events.update(deposit_period.scheduled_events(vault=vault))
        # grace period is not valid for new time deposit and so an
        # end-of-time schedule is created that never runs
        scheduled_events[grace_period.GRACE_PERIOD_END_EVENT] = utils.create_end_of_time_schedule(
            start_datetime=schedule_start_datetime
        )

    scheduled_events.update(
        fixed_interest_accrual.scheduled_events(vault=vault, start_datetime=schedule_start_datetime)
    )
    scheduled_events.update(
        interest_application.scheduled_events(
            vault=vault, reference_datetime=interest_application_start_datetime
        )
    )
    scheduled_events.update(deposit_maturity.scheduled_events(vault=vault))

    return ActivationHookResult(scheduled_events_return_value=scheduled_events)


@requires(
    event_type=fixed_interest_accrual.ACCRUAL_EVENT,
    parameters=True,
)
@fetch_account_data(
    event_type=fixed_interest_accrual.ACCRUAL_EVENT,
    balances=[fetchers.EOD_FETCHER_ID],
)
@requires(
    event_type=interest_application.APPLICATION_EVENT,
    parameters=True,
)
@fetch_account_data(
    event_type=interest_application.APPLICATION_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@requires(
    event_type=deposit_period.DEPOSIT_PERIOD_END_EVENT,
    parameters=True,
)
@fetch_account_data(
    event_type=deposit_period.DEPOSIT_PERIOD_END_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@requires(
    event_type=grace_period.GRACE_PERIOD_END_EVENT,
    parameters=True,
)
@fetch_account_data(
    event_type=grace_period.GRACE_PERIOD_END_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@requires(
    event_type=deposit_maturity.ACCOUNT_MATURITY_EVENT,
    parameters=True,
)
@requires(
    event_type=deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
    parameters=True,
    calendar=["&{PUBLIC_HOLIDAYS}"],
)
def scheduled_event_hook(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    event_type = hook_arguments.event_type
    effective_datetime = hook_arguments.effective_datetime

    custom_instructions: list[CustomInstruction] = []
    notification_directives: list[AccountNotificationDirective] = []
    update_event_directives: list[UpdateAccountEventTypeDirective] = []

    if event_type == fixed_interest_accrual.ACCRUAL_EVENT:
        custom_instructions.extend(
            fixed_interest_accrual.accrue_interest(
                vault=vault,
                effective_datetime=effective_datetime,
                account_type=PRODUCT_NAME,
            )
        )

    elif event_type == interest_application.APPLICATION_EVENT:
        if application_custom_instructions := interest_application.apply_interest(
            vault=vault, account_type=PRODUCT_NAME
        ):
            custom_instructions.extend(application_custom_instructions)
            custom_instructions.extend(
                _update_tracked_applied_interest(
                    application_custom_instructions=application_custom_instructions,
                    account_id=vault.account_id,
                    denomination=common_parameters.get_denomination_parameter(vault=vault),
                )
            )

        if update_event_result := interest_application.update_next_schedule_execution(
            vault=vault, effective_datetime=effective_datetime
        ):
            update_event_directives.extend([update_event_result])

    # check balance and send notification for new time deposit
    elif event_type == deposit_period.DEPOSIT_PERIOD_END_EVENT:
        balances: BalanceDefaultDict = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
        notification_directives.extend(
            deposit_period.handle_account_closure_notification(
                product_name=PRODUCT_NAME,
                balances=balances,
                denomination=common_parameters.get_denomination_parameter(vault=vault),
                account_id=vault.account_id,
                effective_datetime=effective_datetime,
            )
        )

    # send notification at account maturity and skip specific schedules indefinitely
    elif event_type == deposit_maturity.ACCOUNT_MATURITY_EVENT:
        (
            maturity_notifications,
            schedules_to_skip_indefinitely,
        ) = deposit_maturity.handle_account_maturity_event(
            product_name=PRODUCT_NAME,
            account_id=vault.account_id,
            effective_datetime=effective_datetime,
            schedules_to_skip_indefinitely=[
                fixed_interest_accrual.ACCRUAL_EVENT,
                interest_application.APPLICATION_EVENT,
            ],
        )
        notification_directives.extend(maturity_notifications)
        update_event_directives.extend(schedules_to_skip_indefinitely)

    # send notification prior to account maturity and
    # update maturity schedule if required
    elif event_type == deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT:
        (
            maturity_reminder_notifications,
            updated_maturity_schedule_directives,
        ) = deposit_maturity.handle_notify_upcoming_maturity_event(
            vault=vault, product_name=PRODUCT_NAME
        )

        update_event_directives.extend(updated_maturity_schedule_directives)
        notification_directives.extend(maturity_reminder_notifications)

    # check balance and send notification for renewed time deposit
    elif event_type == grace_period.GRACE_PERIOD_END_EVENT:
        notification_directives.extend(
            grace_period.handle_account_closure_notification(
                vault=vault,
                product_name=PRODUCT_NAME,
                denomination=common_parameters.get_denomination_parameter(vault=vault),
                effective_datetime=effective_datetime,
            )
        )

    if custom_instructions or notification_directives or update_event_directives:
        return ScheduledEventHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=custom_instructions,
                    value_datetime=effective_datetime,
                    client_batch_id=f"{vault.get_hook_execution_id()}_{event_type}",
                ),
            ]
            if custom_instructions
            else [],
            account_notification_directives=notification_directives,
            update_account_event_type_directives=update_event_directives,
        )

    return None


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    """
    Performs the following posting checks:
    - Force override postings bypass checks
    - Reject any instructions that are not a single Hard Settlement or Transfer
    - Invalid denomination is rejected
    - Validates deposits outside the grace period (Renewed TD only)
    - Reject any initial deposit below the minimum amount (New TD only)
    - Reject any deposit(s) after the end of deposit period (New TD only)
    - Reject additional deposits if configured for single deposit (New TD only)
    - Reject any postings that pushes the current balance above the maximum balance limit
    - Reject any postings after account maturity
    - Reject applicable withdrawals if they violate fee-charging conditions
    """
    posting_instructions: utils.PostingInstructionListAlias = hook_arguments.posting_instructions
    effective_datetime = hook_arguments.effective_datetime

    # force override
    if utils.is_force_override(posting_instructions=posting_instructions):
        return None

    # reject anything except single hard settlement or transfer
    if posting_type_rejections := utils.validate_single_hard_settlement_or_transfer(
        posting_instructions=posting_instructions
    ):
        return PrePostingHookResult(rejection=posting_type_rejections)

    # reject invalid denomination
    denomination = common_parameters.get_denomination_parameter(vault=vault)
    if invalid_denomination_rejection := utils.validate_denomination(
        posting_instructions=posting_instructions,
        accepted_denominations=[denomination],
    ):
        return PrePostingHookResult(rejection=invalid_denomination_rejection)

    account_balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances
    # check whether this is a 'renewed' time deposit
    if _is_renewed_time_deposit(vault=vault, effective_datetime=effective_datetime):
        # since grace period is non-zero the product is therefore treated as a renewed time deposit
        if grace_period_rejection := grace_period.validate_deposit(
            vault=vault,
            effective_datetime=effective_datetime,
            posting_instructions=posting_instructions,
            denomination=denomination,
        ):
            return PrePostingHookResult(rejection=grace_period_rejection)

    else:
        # reject posting if below minimum initial deposit
        if minimum_initial_deposit_rejection := minimum_initial_deposit.validate(
            vault=vault,
            denomination=denomination,
            balances=account_balances,
            postings=posting_instructions,
        ):
            return PrePostingHookResult(rejection=minimum_initial_deposit_rejection)

        # reject any deposits after the deposit period end datetime
        # or scenario where more than a single deposit if configured
        if deposit_period_rejection := deposit_period.validate(
            vault=vault,
            effective_datetime=effective_datetime,
            posting_instructions=posting_instructions,
            denomination=denomination,
            balances=account_balances,
        ):
            return PrePostingHookResult(rejection=deposit_period_rejection)

    # regardless of whether this is a renewed or new time deposit, we must check
    #   - maximum balance is not exceeded
    #   - no transactions are allowed after account maturity
    #   - the withdrawal meets fee-charging requirements, if applicable

    # reject postings which cause the maximum allowed balance to be exceeded
    if maximum_balance_rejection := maximum_balance_limit.validate(
        vault=vault,
        postings=posting_instructions,
        denomination=denomination,
        balances=account_balances,
    ):
        return PrePostingHookResult(rejection=maximum_balance_rejection)

    # reject transactions after account maturity
    if transaction_after_maturity_rejection := deposit_maturity.validate_postings(
        vault=vault, effective_datetime=effective_datetime
    ):
        return PrePostingHookResult(rejection=transaction_after_maturity_rejection)

    # reject applicable withdrawals if they violate fee-charging conditions
    if withdrawals_rejection := withdrawal_fees.validate(
        vault=vault,
        effective_datetime=effective_datetime,
        posting_instructions=posting_instructions,
        denomination=denomination,
        balances=account_balances,
        balance_adjustments=TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
    ):
        return PrePostingHookResult(rejection=withdrawals_rejection)

    if withdrawal_fees_rejection := _validate_withdrawals_with_number_of_interest_days_fee(
        vault=vault,
        effective_datetime=effective_datetime,
        posting_instructions=posting_instructions,
        denomination=denomination,
        balances=account_balances,
        balance_adjustments=TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
    ):
        return PrePostingHookResult(rejection=withdrawal_fees_rejection)

    return None


@requires(parameters=True)
@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
def post_posting_hook(
    vault: SmartContractVault, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    posting_instructions: utils.PostingInstructionListAlias = hook_arguments.posting_instructions
    # force override
    if utils.is_force_override(posting_instructions=posting_instructions):
        return None

    custom_instructions: list[CustomInstruction] = []
    notification_directives: list[AccountNotificationDirective] = []

    denomination = common_parameters.get_denomination_parameter(vault=vault)

    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances

    posting_amount = utils.get_available_balance(
        balances=utils.get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    )

    # if this is a withdrawal
    if posting_amount < Decimal("0"):
        withdrawal_amount = abs(posting_amount)

        is_renewed = _is_renewed_time_deposit(vault=vault, effective_datetime=effective_datetime)
        if (
            is_renewed
            and grace_period.is_withdrawal_subject_to_fees(
                vault=vault,
                effective_datetime=effective_datetime,
                posting_instructions=posting_instructions,
                denomination=denomination,
            )
            or (
                not is_renewed
                and cooling_off_period.is_withdrawal_subject_to_fees(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    posting_instructions=posting_instructions,
                    denomination=denomination,
                )
            )
        ):
            (
                withdrawal_fee_instructions,
                withdrawal_fee_notifications,
            ) = withdrawal_fees.handle_withdrawals(
                vault=vault,
                effective_datetime=effective_datetime,
                posting_instructions=posting_instructions,
                product_name=PRODUCT_NAME,
                denomination=denomination,
                balances=balances,
                balance_adjustments=TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
            )

            # We can assume there is only 1 notification returned from the feature
            withdrawal_fee_notification = withdrawal_fee_notifications[0]
            # Update fee notification with Number of Interest Days Fee, if configured
            withdrawal_fee_notifications = _handle_withdrawal_fees_with_number_of_interest_days_fee(
                vault=vault,
                withdrawal_fee_notification=withdrawal_fee_notification,
                withdrawal_amount=withdrawal_amount,
                effective_datetime=effective_datetime,
                balances=balances,
                denomination=denomination,
            )

            custom_instructions.extend(withdrawal_fee_instructions)
            notification_directives.extend(withdrawal_fee_notifications)

        else:
            # Send a zero fee notification for withdrawals not subject to fees
            zero_fee_notification = withdrawal_fees.generate_withdrawal_fee_notification(
                account_id=vault.account_id,
                denomination=denomination,
                withdrawal_amount=withdrawal_amount,
                flat_fee_amount=Decimal("0"),
                percentage_fee_amount=Decimal("0"),
                product_name=PRODUCT_NAME,
                client_batch_id=posting_instructions[0].client_batch_id,  # type: ignore
            )

            # Include zero amount for Number of Interest Days Fee for notification consistency
            zero_fee_notification = _update_notification_with_number_of_interest_days_fee(
                withdrawal_fee_notification=zero_fee_notification,
                number_of_interest_days_fee=Decimal("0"),
            )

            notification_directives.append(zero_fee_notification)

        custom_instructions.extend(
            _handle_partial_interest_forfeiture(
                vault=vault,
                effective_datetime=effective_datetime,
                balances=balances,
                withdrawal_amount=withdrawal_amount,
            )
        )

        # if this withdrawal has resulted in 0 available balance, this was a full withdrawal
        # send notification if outside of deposit or grace period
        notification_directives.extend(
            _handle_full_withdrawal_notification(
                vault=vault,
                effective_datetime=effective_datetime,
                balances=balances,
                denomination=denomination,
            )
        )

    if custom_instructions or notification_directives:
        return PostPostingHookResult(
            account_notification_directives=notification_directives,
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=custom_instructions, value_datetime=effective_datetime
                )
            ]
            if custom_instructions
            else [],
        )

    return None


@requires(parameters=True)
@fetch_account_data(balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID])
def derived_parameter_hook(
    vault: SmartContractVault, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    effective_datetime = hook_arguments.effective_datetime
    min_datetime = datetime.min.replace(tzinfo=ZoneInfo("UTC"))

    if _is_renewed_time_deposit(vault=vault, effective_datetime=effective_datetime):
        grace_period_end_datetime = grace_period.get_grace_period_end_datetime(vault=vault)
        deposit_period_end_datetime = min_datetime
        cooling_off_period_end_datetime = min_datetime
    else:
        deposit_period_end_datetime = deposit_period.get_deposit_period_end_datetime(vault=vault)
        cooling_off_period_end_datetime = cooling_off_period.get_cooling_off_period_end_datetime(
            vault=vault
        )
        grace_period_end_datetime = min_datetime

    maximum_withdrawal_limit = withdrawal_fees.get_maximum_withdrawal_limit_derived_parameter(
        vault=vault,
        effective_datetime=effective_datetime,
        balance_adjustments=TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
    )
    fee_free_withdrawal_limit = withdrawal_fees.get_fee_free_withdrawal_limit_derived_parameter(
        vault=vault,
        effective_datetime=effective_datetime,
        balance_adjustments=TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
    )

    derived_parameters: dict[str, utils.ParameterValueTypeAlias] = {
        deposit_period.PARAM_DEPOSIT_PERIOD_END_DATE: deposit_period_end_datetime,
        cooling_off_period.PARAM_COOLING_OFF_PERIOD_END_DATE: cooling_off_period_end_datetime,
        grace_period.PARAM_GRACE_PERIOD_END_DATE: grace_period_end_datetime,
        withdrawal_fees.PARAM_MAXIMUM_WITHDRAWAL_LIMIT: maximum_withdrawal_limit,
        withdrawal_fees.PARAM_FEE_FREE_WITHDRAWAL_LIMIT: fee_free_withdrawal_limit,
    }

    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


@requires(parameters=True)
@fetch_account_data(
    balances=[
        fetchers.LIVE_BALANCES_BOF_ID,
        withdrawal_fees.EARLY_WITHDRAWALS_TRACKER_LIVE_BOF_ID,
    ]
)
def deactivation_hook(
    vault: SmartContractVault, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    denomination = common_parameters.get_denomination_parameter(vault=vault)
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances

    custom_instructions: list[CustomInstruction] = []

    # The following is applicable to both new and renewed time deposits
    # Clear any accrued interest - the maturity schedule will capitalise accrued interest and
    # in all other cases, accrued interest is forfeited.
    custom_instructions.extend(
        fixed_interest_accrual.get_interest_reversal_postings(
            vault=vault,
            event_name=ACCOUNT_CLOSURE_EVENT,
            account_type=PRODUCT_NAME,
            balances=balances,
        )
    )

    # Reset any tracking addresses
    custom_instructions.extend(
        _reset_applied_interest_tracker(
            balances=balances, account_id=vault.account_id, denomination=denomination
        )
    )
    custom_instructions.extend(
        withdrawal_fees.reset_withdrawals_tracker(
            vault=vault, balances=balances, denomination=denomination
        )
    )

    if custom_instructions:
        return DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=custom_instructions,
                    value_datetime=effective_datetime,
                )
            ]
        )

    return None


def conversion_hook(
    vault: SmartContractVault, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    scheduled_events = utils.update_completed_schedules(
        scheduled_events=hook_arguments.existing_schedules,
        effective_datetime=hook_arguments.effective_datetime,
        potentially_completed_schedules=[
            deposit_period.DEPOSIT_PERIOD_END_EVENT,
            grace_period.GRACE_PERIOD_END_EVENT,
            deposit_maturity.ACCOUNT_MATURITY_EVENT,
            deposit_maturity.NOTIFY_UPCOMING_MATURITY_EVENT,
        ],
    )

    return ConversionHookResult(
        scheduled_events_return_value=scheduled_events,
    )


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def pre_parameter_change_hook(
    vault: SmartContractVault, hook_arguments: PreParameterChangeHookArguments
) -> Optional[PreParameterChangeHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    updated_parameters = hook_arguments.updated_parameter_values

    if proposed_term_value := updated_parameters.get(deposit_parameters.PARAM_TERM):
        # proposed_term_value must be > 0 since the min_value of the parameter is 1
        if rejection := _validate_term_parameter_change(
            vault=vault,
            effective_datetime=effective_datetime,
            proposed_term_value=int(proposed_term_value),  # type: ignore
        ):
            return PreParameterChangeHookResult(rejection=rejection)

    return None


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def post_parameter_change_hook(
    vault: SmartContractVault, hook_arguments: PostParameterChangeHookArguments
) -> Optional[PostParameterChangeHookResult]:
    updated_parameters = hook_arguments.updated_parameter_values

    update_event_directives: list[UpdateAccountEventTypeDirective] = []

    if deposit_parameters.PARAM_TERM in updated_parameters:
        update_event_directives.extend(deposit_maturity.handle_term_parameter_change(vault=vault))

    if update_event_directives:
        return PostParameterChangeHookResult(
            update_account_event_type_directives=update_event_directives
        )

    return None


# New vs Renewed helpers
def _is_renewed_time_deposit(vault: SmartContractVault, effective_datetime: datetime) -> bool:
    """
    A time deposit account with a grace period greater than 1 is assumed to be a renewed time
    deposit
    """

    return (
        grace_period.get_grace_period_parameter(vault=vault, effective_datetime=effective_datetime)
        > 0
    )


# Parameter change helpers
def _validate_term_parameter_change(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    proposed_term_value: int,
) -> Optional[Rejection]:
    if _is_renewed_time_deposit(vault=vault, effective_datetime=effective_datetime):
        if grace_period_rejection := grace_period.validate_term_parameter_change(
            vault=vault, effective_datetime=effective_datetime
        ):
            return grace_period_rejection

        if deposit_maturity_rejection := deposit_maturity.validate_term_parameter_change(
            vault=vault,
            effective_datetime=effective_datetime,
            proposed_term_value=proposed_term_value,
        ):
            return deposit_maturity_rejection

    else:
        return Rejection(
            message="Term length can only be changed on Renewed Time Deposit accounts",
            reason_code=RejectionReason.AGAINST_TNC,
        )

    return None


# Tracking balance helpers
def _update_tracked_applied_interest(
    application_custom_instructions: list[CustomInstruction],
    account_id: str,
    denomination: str,
) -> list[CustomInstruction]:
    """
    Create posting instructions to update the applied interest tracker balance.

    :param application_custom_instructions: the list of custom instructions for the application
    of interest to the DEFAULT balance
    :param account_id: the id of the deposit account
    :param denomination: the denomination the posting should be made in
    :return: list of applied interest tracking posting instructions
    """

    application_amount = Decimal(
        sum(
            utils.get_current_net_balance(
                balances=instruction.balances(account_id=account_id, tside=Tside.LIABILITY),
                denomination=denomination,
            )
            for instruction in application_custom_instructions
        )
    )

    if application_amount > Decimal("0"):
        return [
            CustomInstruction(
                postings=utils.create_postings(
                    amount=application_amount,
                    debit_account=account_id,
                    credit_account=account_id,
                    debit_address=common_addresses.INTERNAL_CONTRA,
                    credit_address=APPLIED_INTEREST_TRACKER,
                    denomination=denomination,
                ),
                instruction_details={
                    "description": "Updating the applied interest tracker balance"
                },
                override_all_restrictions=True,
            )
        ]

    return []


def _reset_applied_interest_tracker(
    balances: BalanceDefaultDict,
    account_id: str,
    denomination: str,
) -> list[CustomInstruction]:
    """
    Create postings to net-off the applied interest tracker balance.

    :param balances: the balances of the account
    :param account_id: the id of the deposit account
    :param denomination: the denomination the posting should be made in
    :return: list of posting instructions for netting off the tracked applied interest
    """
    tracker_balance = utils.balance_at_coordinates(
        balances=balances, address=APPLIED_INTEREST_TRACKER, denomination=denomination
    )

    if tracker_balance > Decimal("0"):
        return [
            CustomInstruction(
                postings=utils.create_postings(
                    amount=tracker_balance,
                    debit_account=account_id,
                    credit_account=account_id,
                    debit_address=APPLIED_INTEREST_TRACKER,
                    credit_address=common_addresses.INTERNAL_CONTRA,
                    denomination=denomination,
                ),
                instruction_details={"description": "Resetting the applied interest tracker"},
                override_all_restrictions=True,
            )
        ]

    return []


# Post-posting helpers
def _handle_partial_interest_forfeiture(
    vault: SmartContractVault,
    effective_datetime: datetime,
    balances: BalanceDefaultDict,
    withdrawal_amount: Decimal,
) -> list[CustomInstruction]:
    """
    This function determines the amount of accrued interest to be forfeited as a result of a
    withdrawal. The forfeited interest is simply calculated as the ratio of
    withdrawal_amount:balance_before_withdrawal. This is only possible because the interest accrual
    feature used is flat interest.

    :param vault: Vault object of the account
    :param effective_datetime: datetime of the withdrawal
    :param balances: account balances
    :param withdrawal_amount: The absolute amount withdrawn from the account in this transaction
    :return: interest forfeiture instructions
    """
    accrual_precision = fixed_interest_accrual.get_interest_accrual_precision(
        vault=vault, effective_datetime=effective_datetime
    )
    denomination = common_parameters.get_denomination_parameter(vault=vault)
    accrual_address = fixed_interest_accrual.ACCRUED_INTEREST_PAYABLE
    accrued_interest_balance = utils.balance_at_coordinates(
        balances=balances,
        denomination=denomination,
        address=accrual_address,
    )
    account_deposit_balance = utils.balance_at_coordinates(
        balances=balances,
        denomination=denomination,
        address=DEFAULT_ADDRESS,
    )
    account_balance_before_withdrawal = account_deposit_balance + withdrawal_amount
    forfeited_interest_amount = utils.round_decimal(
        amount=((withdrawal_amount / account_balance_before_withdrawal) * accrued_interest_balance),
        decimal_places=accrual_precision,
    )

    if forfeited_interest_amount > Decimal("0"):
        accrual_internal_account = (
            fixed_interest_accrual.get_accrued_interest_payable_account_parameter(
                vault=vault, effective_datetime=effective_datetime
            )
        )
        return [
            CustomInstruction(
                postings=utils.create_postings(
                    amount=forfeited_interest_amount,
                    debit_account=vault.account_id,
                    credit_account=accrual_internal_account,
                    debit_address=accrual_address,
                    credit_address=DEFAULT_ADDRESS,
                    denomination=denomination,
                ),
                override_all_restrictions=True,
            ),
        ]
    return []


def _handle_full_withdrawal_notification(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    balances: BalanceDefaultDict,
    denomination: str,
) -> list[AccountNotificationDirective]:
    """
    For use in the post-posting hook.
    Return a notification if a full withdrawal occurs outside of the grace
    period (for renewed TDs), or outside of the deposit period (for new TDs).

    :param vault: Vault object of the account
    :param effective_datetime: datetime of the withdrawal
    :param balances: the balances of the account
    :param denomination: the denomination of the account
    :return: list of account notification directives
    """
    if utils.get_available_balance(balances=balances, denomination=denomination) == Decimal("0"):
        is_renewed = _is_renewed_time_deposit(vault=vault, effective_datetime=effective_datetime)
        if (
            is_renewed
            and not grace_period.is_within_grace_period(
                vault=vault, effective_datetime=effective_datetime
            )
        ) or (
            not is_renewed
            and not deposit_period.is_within_deposit_period(
                vault=vault, effective_datetime=effective_datetime
            )
        ):
            return [
                AccountNotificationDirective(
                    notification_type=FULL_WITHDRAWAL_NOTIFICATION,
                    notification_details={
                        "account_id": vault.account_id,
                        "reason": "The account balance has been fully withdrawn.",
                    },
                )
            ]

    return []


# Number of Interest Days Fee helpers
def _handle_withdrawal_fees_with_number_of_interest_days_fee(
    *,
    vault: SmartContractVault,
    withdrawal_fee_notification: AccountNotificationDirective,
    withdrawal_amount: Decimal,
    effective_datetime: datetime,
    balances: BalanceDefaultDict,
    denomination: str,
) -> list[AccountNotificationDirective]:
    """
    For use in the post_posting_hook.
    Calculate the number of interest days fee, and update the existing WITHDRAWAL_FEES_NOTIFICATION
    to include the `number_of_interest_days_fee` key.

    :param vault: the Vault object for the account
    :param withdrawal_fee_notification: the existing withdrawals fee notification
    :param withdrawal_amount: the absolute amount withdrawn from the account in this transaction
    :param effective_datetime: datetime at which this method is executed
    :param balances: latest account balances available
    :param denomination: the denomination of the account
    :return: a list containing the updated notification
    """
    number_of_interest_days_fee = _calculate_number_of_interest_days_fee(
        vault=vault,
        effective_datetime=effective_datetime,
        denomination=denomination,
        balances=balances,
        balance_adjustments=[
            *TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS,
            withdrawal_fees.get_current_withdrawal_amount_default_balance_adjustment(
                withdrawal_amount=withdrawal_amount
            ),
        ],
    )

    withdrawal_fee_notification = _update_notification_with_number_of_interest_days_fee(
        withdrawal_fee_notification=withdrawal_fee_notification,
        number_of_interest_days_fee=number_of_interest_days_fee,
    )

    return [withdrawal_fee_notification]


def _calculate_number_of_interest_days_fee(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    denomination: str,
    balances: BalanceDefaultDict,
    balance_adjustments: Optional[list[deposit_interfaces.DefaultBalanceAdjustment]] = None,
) -> Decimal:
    """
    Calculate the number of interest days fee that is chargeable against a withdrawal

    :param vault: the Vault object for the account
    :param effective_datetime: datetime of the withdrawal
    :param denomination: the denomination of the account
    :param balances: the balances to determine the customer's deposited amount
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, WITHDRAWALS_TRACKER balance and the returned amount of each adjustment.
    :return: the number of interest days fee
    """
    if (
        number_of_interest_days := _get_number_of_interest_days_early_withdrawal_fee_parameter(
            vault=vault, effective_datetime=effective_datetime
        )
    ) == Decimal("0"):
        return Decimal("0")

    daily_interest_rate = fixed_interest_accrual.get_daily_interest_rate(
        vault=vault, effective_datetime=effective_datetime
    )
    customer_deposited_amount = withdrawal_fees.get_customer_deposit_amount(
        vault=vault,
        balances=balances,
        denomination=denomination,
        balance_adjustments=balance_adjustments,
    )

    return utils.round_decimal(
        amount=(customer_deposited_amount * daily_interest_rate * number_of_interest_days),
        decimal_places=2,
    )


def _update_notification_with_number_of_interest_days_fee(
    *,
    withdrawal_fee_notification: AccountNotificationDirective,
    number_of_interest_days_fee: Decimal,
) -> AccountNotificationDirective:
    """
    Update the existing WITHDRAWAL_FEES_NOTIFICATION to include the `number_of_interest_days_fee`
    key. If the `number_of_interest_days_fee` is non-zero, it overrides the percentage fee amount
    and the `total_fee_amount` is updated to reflect the final fee amounts.

    :param withdrawal_fee_notification: the existing withdrawals fee notification
    :param number_of_interest_days_fee: the amount to charge as the number of interest days fee
    :return: the updated notification
    """
    notification_details = withdrawal_fee_notification.notification_details

    notification_details.update(
        {
            "number_of_interest_days_fee": str(number_of_interest_days_fee),
            "percentage_fee_amount": "0",
        }
        if number_of_interest_days_fee != Decimal("0")
        else {
            "number_of_interest_days_fee": "0",
        }
    )

    notification_details.update(
        {
            "total_fee_amount": str(
                Decimal(notification_details["flat_fee_amount"])
                + Decimal(notification_details["percentage_fee_amount"])
                + Decimal(notification_details["number_of_interest_days_fee"])
            )
        }
    )

    return AccountNotificationDirective(
        notification_type=WITHDRAWAL_FEES_NOTIFICATION,
        notification_details=notification_details,
    )


def _validate_withdrawals_with_number_of_interest_days_fee(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    posting_instructions: utils.PostingInstructionListAlias,
    denomination: str,
    balances: BalanceDefaultDict,
    balance_adjustments: Optional[list[deposit_interfaces.DefaultBalanceAdjustment]] = None,
) -> Optional[Rejection]:
    """
    For use in the pre_posting_hook.
    Deposits are accepted with no validation.
    Reject the posting instructions if the withdrawal amount is less than the incurred
    withdrawal fee amount, considering the number of interest days fee if configured

    :param vault: the Vault object for the account against which this validation is applied
    :param effective_datetime: datetime at which this method is executed
    :param posting_instructions: list of posting instructions to validate
    :param denomination: the denomination of the account
    :param balances: latest account balances available
    :param balance_adjustments: list of balance adjustments that impact the default balance,
    used when calculating the customer deposited amount. The customer deposited amount is the sum
    of the DEFAULT balance, WITHDRAWALS_TRACKER balance and the returned amount of each adjustment.
    For example, interest application adjustment should be negative, and a fee
    charge adjustment should be positive.
    :return: rejection if any of the above conditions are met
    """
    posting_amount = utils.get_available_balance(
        balances=utils.get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    )

    # Deposits are accepted with no validation.
    if posting_amount >= Decimal("0"):
        return None

    withdrawal_amount = abs(posting_amount)

    # Calculate fee amounts
    number_of_interest_days_fee_amount = _calculate_number_of_interest_days_fee(
        vault=vault,
        effective_datetime=effective_datetime,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )
    if number_of_interest_days_fee_amount == Decimal("0"):
        # If this is none, the withdrawal fees feature will have already validated if the
        # other fee amounts exceed the withdrawal amount
        return None

    flat_fee_amount, percentage_fee_amount = withdrawal_fees.calculate_withdrawal_fee_amounts(
        vault=vault,
        effective_datetime=effective_datetime,
        withdrawal_amount=withdrawal_amount,
        denomination=denomination,
        balances=balances,
        balance_adjustments=balance_adjustments,
    )

    # number_of_interest_days_fee_amount overrides percentage_fee_amount if it's configured
    total_fee_amount = (
        (flat_fee_amount + number_of_interest_days_fee_amount)
        if number_of_interest_days_fee_amount
        else (flat_fee_amount + percentage_fee_amount)
    )
    # Check if withdrawal amount is less than the incurred withdrawal fee amount
    if withdrawal_amount < total_fee_amount:
        return Rejection(
            message=f"The withdrawal fees of {total_fee_amount} {denomination} are not covered "
            f"by the withdrawal amount of {withdrawal_amount} {denomination}.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )

    return None


# Parameter getters
def _get_number_of_interest_days_early_withdrawal_fee_parameter(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils.get_parameter(
            vault=vault,
            name=PARAM_NUMBER_OF_INTEREST_DAYS_EARLY_WITHDRAWAL_FEE,
            at_datetime=effective_datetime,
            is_optional=True,
            default_value=0,
        )
    )


# Default Balance Adjustment helpers
def _calculate_applied_interest_balance_adjustment(
    vault: SmartContractVault,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> Decimal:
    """
    Return the negative of the APPLIED_INTEREST_TRACKER total, to be used by the
    DefaultBalanceAdjustment interface.

    Since applying interest increases the DEFAULT balance, the adjustment must be
    negative, and since the APPLIED_INTEREST_TRACKER is always positive by design,
    we can simply negate the fetched value.

    :param vault: the Vault object for the account
    :param denomination: the denomination of the account, if not provided the
    'denomination' parameter is retrieved
    :param balances: latest account balances available, if not provided balances will be retrieved
    using the LIVE_BALANCES_BOF_ID
    :return: the negative of the APPLIED_INTEREST_TRACKER value
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    tracker_balance = utils.balance_at_coordinates(
        balances=balances,
        address=APPLIED_INTEREST_TRACKER,
        denomination=denomination,
    )
    return -tracker_balance


applied_interest_balance_adjustment = deposit_interfaces.DefaultBalanceAdjustment(
    calculate_balance_adjustment=_calculate_applied_interest_balance_adjustment
)
# See the `Technical Logic` section of
# `documentation/design_decisions/cbf_design_docs/withdrawals_and_withdrawal_fees.md`
# for an explanation of the DefaultBalanceAdjustment interface and usage
TIME_DEPOSIT_DEFAULT_BALANCE_ADJUSTMENTS: list[deposit_interfaces.DefaultBalanceAdjustment] = [
    applied_interest_balance_adjustment
]
