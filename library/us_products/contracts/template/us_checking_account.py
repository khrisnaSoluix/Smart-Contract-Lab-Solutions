# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Optional

# features
import library.features.v4.common.account_tiers as account_tiers
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.deposit.deposit_parameters as deposit_parameters
import library.features.v4.deposit.direct_deposit_tracker as direct_deposit_tracker
import library.features.v4.deposit.dormancy as dormancy
import library.features.v4.deposit.fees.inactivity_fee as inactivity_fee
import library.features.v4.deposit.fees.maintenance_fees as maintenance_fees
import library.features.v4.deposit.fees.minimum_monthly_balance as minimum_monthly_balance
import library.features.v4.deposit.fees.paper_statement_fee as paper_statement_fee
import library.features.v4.deposit.fees.partial_fee as partial_fee
import library.features.v4.deposit.interest.interest_application as interest_application
import library.features.v4.deposit.interest.tiered_interest_accrual as tiered_interest_accrual
import library.features.v4.deposit.transaction_limits.overdraft.overdraft_coverage as overdraft_coverage  # noqa: E501
import library.features.v4.deposit.transaction_limits.withdrawal_limits.maximum_daily_withdrawal_by_transaction_type as maximum_daily_withdrawal_by_transaction_type  # noqa: E501
import library.features.v4.deposit.unlimited_fee_rebate as unlimited_fee_rebate

# contracts api
from contracts_api import (
    ActivationHookArguments,
    ActivationHookResult,
    CustomInstruction,
    DeactivationHookArguments,
    DeactivationHookResult,
    DenominationShape,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    Parameter,
    ParameterLevel,
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
    StringShape,
    Tside,
    UpdateAccountEventTypeDirective,
    fetch_account_data,
    requires,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

api = "4.0.0"
version = "2.0.0"
display_name = "Checking Account"
summary = "Checking Account Product"
tside = Tside.LIABILITY
supported_denominations = ["USD"]

PRODUCT_NAME = "CHECKING_ACCOUNT"

# Parameters
PARAM_DENOMINATION = "denomination"
PARAM_ACTIVE_ACCOUNT_TIER_NAME = "active_account_tier_name"

parameters = [
    # Template Parameters
    Parameter(
        name=PARAM_DENOMINATION,
        shape=DenominationShape(),
        level=ParameterLevel.TEMPLATE,
        description="Currency in which the product operates.",
        display_name="Denomination",
        default_value="USD",
    ),
    Parameter(
        name=PARAM_ACTIVE_ACCOUNT_TIER_NAME,
        shape=StringShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="Currently active account tier name of the account",
        display_name="Active Account Tier Name",
    ),
    # Feature Parameters
    *account_tiers.parameters,
    *dormancy.parameters,
    *inactivity_fee.parameters,
    *interest_application.parameters,
    *minimum_monthly_balance.parameters,
    *paper_statement_fee.parameters,
    *maximum_daily_withdrawal_by_transaction_type.parameters,
    *overdraft_coverage.parameters,
    *tiered_interest_accrual.parameters,
    *maintenance_fees.monthly_params,
    *maintenance_fees.schedule_params,
    *direct_deposit_tracker.parameters,
    deposit_parameters.capitalise_accrued_interest_on_account_closure_param,
    *unlimited_fee_rebate.parameters,
]

# Fetchers
data_fetchers = [
    fetchers.EOD_FETCHER,
    fetchers.EFFECTIVE_DATE_POSTINGS_FETCHER,
    fetchers.EFFECTIVE_OBSERVATION_FETCHER,
    fetchers.LIVE_BALANCES_BOF,
    *fetchers.PREVIOUS_EOD_OBSERVATION_FETCHERS,
]

# Events
event_types = [
    *inactivity_fee.event_types(product_name=PRODUCT_NAME),
    *interest_application.event_types(product_name=PRODUCT_NAME),
    *minimum_monthly_balance.event_types(product_name=PRODUCT_NAME),
    *tiered_interest_accrual.event_types(product_name=PRODUCT_NAME),
    *paper_statement_fee.event_types(product_name=PRODUCT_NAME),
    *maintenance_fees.event_types(product_name=PRODUCT_NAME, frequency=maintenance_fees.MONTHLY),
]

# Constants
CLOSE_ACCOUNT = "CLOSE_ACCOUNT"
FEE_HIERARCHY = [
    maintenance_fees.PARTIAL_FEE_DETAILS,
    minimum_monthly_balance.PARTIAL_FEE_DETAILS,
    inactivity_fee.PARTIAL_FEE_DETAILS,
    paper_statement_fee.PARTIAL_FEE_DETAILS,
]


@requires(parameters=True)
def activation_hook(
    vault: SmartContractVault, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    scheduled_events: dict[str, ScheduledEvent] = {}
    effective_datetime = hook_arguments.effective_datetime

    # schedule creation
    start_datetime_at_midnight = effective_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    scheduled_events.update(
        tiered_interest_accrual.scheduled_events(
            vault=vault,
            start_datetime=start_datetime_at_midnight + relativedelta(days=1),
        )
    )

    scheduled_events.update(
        interest_application.scheduled_events(
            vault=vault,
            reference_datetime=start_datetime_at_midnight,
        )
    )

    scheduled_events.update(
        minimum_monthly_balance.scheduled_events(
            vault=vault,
            start_datetime=start_datetime_at_midnight + relativedelta(months=1),
        )
    )

    scheduled_events.update(
        inactivity_fee.scheduled_events(
            vault=vault,
            start_datetime=start_datetime_at_midnight + relativedelta(months=1),
        )
    )

    scheduled_events.update(
        paper_statement_fee.scheduled_events(
            vault=vault,
            start_datetime=start_datetime_at_midnight + relativedelta(months=1),
        )
    )

    scheduled_events.update(
        maintenance_fees.scheduled_events(
            vault=vault,
            start_datetime=start_datetime_at_midnight,
            frequency=maintenance_fees.MONTHLY,
        ),
    )

    return ActivationHookResult(scheduled_events_return_value=scheduled_events)


@requires(event_type=paper_statement_fee.APPLICATION_EVENT, flags=True, parameters=True)
@fetch_account_data(
    event_type=paper_statement_fee.APPLICATION_EVENT,
    balances=[
        fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID,
    ],
)
@requires(
    event_type=maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
    flags=True,
    parameters=True,
)
@fetch_account_data(
    event_type=maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
    balances=[
        direct_deposit_tracker.DIRECT_DEPOSIT_EOD_FETCHER_ID,
        fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID,
        *fetchers.PREVIOUS_EOD_OBSERVATION_FETCHER_IDS,
    ],
)
@requires(
    event_type=inactivity_fee.APPLICATION_EVENT,
    flags=True,
    parameters=True,
)
@fetch_account_data(
    event_type=inactivity_fee.APPLICATION_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@requires(
    event_type=minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT,
    flags=True,
    parameters=True,
)
@fetch_account_data(
    event_type=minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT,
    balances=[
        fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID,
        fetchers.EOD_FETCHER_ID,
        *fetchers.PREVIOUS_EOD_OBSERVATION_FETCHER_IDS,
    ],
)
@requires(
    event_type=interest_application.APPLICATION_EVENT,
    parameters=True,
    flags=True,
)
@fetch_account_data(
    event_type=interest_application.APPLICATION_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@requires(
    event_type=tiered_interest_accrual.ACCRUAL_EVENT,
    parameters=True,
    flags=True,
)
@fetch_account_data(
    event_type=tiered_interest_accrual.ACCRUAL_EVENT,
    balances=[fetchers.EOD_FETCHER_ID],
)
def scheduled_event_hook(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    event_type = hook_arguments.event_type
    effective_datetime = hook_arguments.effective_datetime

    custom_instructions: list[CustomInstruction] = []
    posting_instruction_directives: list[PostingInstructionsDirective] = []
    update_account_event_directives: list[UpdateAccountEventTypeDirective] = []

    if dormancy.is_account_dormant(vault=vault, effective_datetime=effective_datetime):
        return None
    elif event_type == tiered_interest_accrual.ACCRUAL_EVENT:
        custom_instructions.extend(
            tiered_interest_accrual.accrue_interest(
                vault=vault, effective_datetime=effective_datetime
            )
        )
    elif event_type == interest_application.APPLICATION_EVENT:
        custom_instructions.extend(
            interest_application.apply_interest(vault=vault, account_type=PRODUCT_NAME)
        )
        if update_event_result := interest_application.update_next_schedule_execution(
            vault=vault, effective_datetime=effective_datetime
        ):
            update_account_event_directives.append(update_event_result)
    elif event_type == inactivity_fee.APPLICATION_EVENT:
        if inactivity_fee.is_account_inactive(vault=vault, effective_datetime=effective_datetime):
            custom_instructions.extend(
                inactivity_fee.apply(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    available_balance_feature=overdraft_coverage.OverdraftCoverageAvailableBalance,
                )
            )
    elif event_type == minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT:
        custom_instructions.extend(
            minimum_monthly_balance.apply_minimum_balance_fee(
                vault=vault,
                effective_datetime=effective_datetime,
                denomination=common_parameters.get_denomination_parameter(vault=vault),
                available_balance_feature=overdraft_coverage.OverdraftCoverageAvailableBalance,
            )
        )
    elif event_type == paper_statement_fee.APPLICATION_EVENT:
        custom_instructions.extend(
            paper_statement_fee.apply(
                vault=vault,
                effective_datetime=effective_datetime,
                available_balance_feature=overdraft_coverage.OverdraftCoverageAvailableBalance,
            )
        )
    elif event_type == maintenance_fees.APPLY_MONTHLY_FEE_EVENT:
        custom_instructions.extend(
            maintenance_fees.apply_monthly_fee(
                vault=vault,
                effective_datetime=effective_datetime,
                monthly_fee_waive_conditions=[
                    minimum_monthly_balance.WAIVE_FEE_WITH_MEAN_BALANCE_ABOVE_THRESHOLD,
                    direct_deposit_tracker.WAIVE_FEE_AFTER_SUFFICIENT_DEPOSITS,
                ],
                available_balance_feature=overdraft_coverage.OverdraftCoverageAvailableBalance,
            )
        )
        # Resets the direct deposit tracker for next period
        custom_instructions.extend(direct_deposit_tracker.reset_tracking_instructions(vault=vault))

    if custom_instructions:
        posting_instruction_directives.append(
            PostingInstructionsDirective(
                posting_instructions=custom_instructions,
                value_datetime=effective_datetime,
                client_batch_id=f"{vault.get_hook_execution_id()}_{event_type}",
            )
        )

    if posting_instruction_directives or update_account_event_directives:
        return ScheduledEventHookResult(
            posting_instructions_directives=posting_instruction_directives,
            update_account_event_type_directives=update_account_event_directives,
        )

    return None


@requires(parameters=True, flags=True)
def pre_parameter_change_hook(
    vault: SmartContractVault, hook_arguments: PreParameterChangeHookArguments
) -> Optional[PreParameterChangeHookResult]:
    if param_value := hook_arguments.updated_parameter_values.get(
        maximum_daily_withdrawal_by_transaction_type.PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION
    ):
        if daily_withdrawal_limit_rejection := (
            maximum_daily_withdrawal_by_transaction_type.validate_parameter_change(
                vault=vault,
                proposed_parameter_value=str(param_value),
            )
        ):
            return PreParameterChangeHookResult(rejection=daily_withdrawal_limit_rejection)

    return None


@fetch_account_data(
    balances=[fetchers.LIVE_BALANCES_BOF_ID],
    postings=[
        fetchers.EFFECTIVE_DATE_POSTINGS_FETCHER_ID,
    ],
)
@requires(flags=True, parameters=True)
def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    posting_instructions = hook_arguments.posting_instructions
    if utils.is_force_override(posting_instructions=posting_instructions):
        return None

    if account_dormant_rejection := dormancy.validate_account_transaction(
        vault=vault,
        effective_datetime=effective_datetime,
    ):
        return PrePostingHookResult(rejection=account_dormant_rejection)

    denomination = common_parameters.get_denomination_parameter(vault=vault)

    if invalid_denomination_rejection := utils.validate_denomination(
        posting_instructions=posting_instructions,
        accepted_denominations=[denomination],
    ):
        return PrePostingHookResult(rejection=invalid_denomination_rejection)

    if maximum_daily_withdrawal_by_transaction_rejection := (
        maximum_daily_withdrawal_by_transaction_type.validate(
            vault=vault,
            hook_arguments=hook_arguments,
            denomination=denomination,
        )
    ):
        return PrePostingHookResult(rejection=maximum_daily_withdrawal_by_transaction_rejection)

    posting_instructions_by_group = (
        unlimited_fee_rebate.group_posting_instructions_by_fee_eligibility(
            vault=vault,
            effective_datetime=effective_datetime,
            proposed_posting_instructions=posting_instructions,
            denomination=denomination,
        )
    )
    posting_instructions_in_scope_for_overdraft = (
        posting_instructions_by_group[unlimited_fee_rebate.NON_FEE_POSTINGS]
        + posting_instructions_by_group[unlimited_fee_rebate.FEES_INELIGIBLE_FOR_REBATE]
    )
    if overdraft_coverage_rejection := overdraft_coverage.validate(
        vault=vault,
        postings=posting_instructions_in_scope_for_overdraft,
        denomination=denomination,
        effective_datetime=effective_datetime,
    ):
        return PrePostingHookResult(rejection=overdraft_coverage_rejection)

    return None


@requires(parameters=True, flags=True)
def derived_parameter_hook(
    vault: SmartContractVault, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    effective_datetime: datetime = hook_arguments.effective_datetime

    derived_parameters: dict[str, utils.ParameterValueTypeAlias] = {
        PARAM_ACTIVE_ACCOUNT_TIER_NAME: account_tiers.get_account_tier(
            vault=vault, effective_datetime=effective_datetime
        )
    }

    return DerivedParameterHookResult(parameters_return_value=derived_parameters)


@requires(parameters=True)
@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
def post_posting_hook(
    vault: SmartContractVault, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    posting_instructions = hook_arguments.posting_instructions
    denomination = common_parameters.get_denomination_parameter(vault=vault)

    custom_instructions: list[CustomInstruction] = []
    posting_instruction_directives: list[PostingInstructionsDirective] = []

    if fee_rebate_instructions := unlimited_fee_rebate.rebate_fees(
        vault=vault,
        effective_datetime=effective_datetime,
        posting_instructions=posting_instructions,
        denomination=denomination,
    ):
        custom_instructions.extend(fee_rebate_instructions)

    # In the scenario where a charged fee is to be rebated, partial fee collection should account
    # for the increase in account funds
    account_balances = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances

    if fee_rebate_instructions:
        account_balances = utils.update_inflight_balances(
            account_id=vault.account_id,
            tside=tside,
            current_balances=account_balances,
            posting_instructions=fee_rebate_instructions,  # type: ignore
        )

    custom_instructions.extend(
        partial_fee.charge_outstanding_fees(
            vault=vault,
            effective_datetime=effective_datetime,
            fee_collection=FEE_HIERARCHY,
            balances=account_balances,
            denomination=denomination,
            available_balance_feature=overdraft_coverage.OverdraftCoverageAvailableBalance,
        )
    )

    # Track direct deposit postings
    custom_instructions.extend(
        direct_deposit_tracker.generate_tracking_instructions(
            vault=vault,
            posting_instructions=posting_instructions,
        )
    )

    if custom_instructions:
        posting_instruction_directives.append(
            PostingInstructionsDirective(
                posting_instructions=custom_instructions,
                value_datetime=effective_datetime,
            )
        )

    if posting_instruction_directives:
        return PostPostingHookResult(posting_instructions_directives=posting_instruction_directives)

    return None


@requires(parameters=True, flags=True)
@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
def deactivation_hook(
    vault: SmartContractVault, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    effective_datetime: datetime = hook_arguments.effective_datetime
    custom_instructions: list[CustomInstruction] = []
    posting_directives: list[PostingInstructionsDirective] = []

    if dormancy.is_account_dormant(vault=vault, effective_datetime=effective_datetime):
        return DeactivationHookResult(
            rejection=Rejection(
                message="Cannot close a dormant account.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

    balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    if partial_fee.has_outstanding_fees(
        vault=vault,
        fee_collection=FEE_HIERARCHY,
        balances=balances,
    ):
        return DeactivationHookResult(
            rejection=Rejection(
                message="Cannot close account with outstanding fees.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

    capitalise_accrued_interest_on_account_closure = (
        deposit_parameters.get_capitalise_accrued_interest_on_account_closure_parameter(vault=vault)
    )

    if capitalise_accrued_interest_on_account_closure:
        custom_instructions.extend(
            interest_application.apply_interest(
                vault=vault,
                account_type=PRODUCT_NAME,
                balances=balances,
            )
        )
    else:
        custom_instructions.extend(
            tiered_interest_accrual.get_interest_reversal_postings(
                vault=vault,
                event_name=CLOSE_ACCOUNT,
                account_type=PRODUCT_NAME,
                balances=balances,
            )
        )

    if custom_instructions:
        posting_directives.append(
            PostingInstructionsDirective(
                posting_instructions=custom_instructions,
                value_datetime=effective_datetime,
                client_batch_id=f"{vault.get_hook_execution_id()}_{CLOSE_ACCOUNT}",
            )
        )
        return DeactivationHookResult(posting_instructions_directives=posting_directives)

    return None
