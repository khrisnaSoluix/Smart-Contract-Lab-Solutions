# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from typing import Optional

# features
import library.features.v4.common.account_tiers as account_tiers
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.deposit.fees.early_closure_fee as early_closure_fee
import library.features.v4.deposit.fees.withdrawal.payment_type_flat_fee as payment_type_flat_fee
import library.features.v4.deposit.fees.withdrawal.payment_type_monthly_limit_fee as payment_type_monthly_limit_fee  # noqa: E501
import library.features.v4.deposit.fees.withdrawal.payment_type_threshold_fee as payment_type_threshold_fee  # noqa: E501
import library.features.v4.deposit.transaction_limits.deposit_limits.maximum_balance_limit as maximum_balance_limit  # noqa: E501
import library.features.v4.deposit.transaction_limits.deposit_limits.maximum_daily_deposit as maximum_daily_deposit  # noqa: E501
import library.features.v4.deposit.transaction_limits.deposit_limits.maximum_single_deposit as maximum_single_deposit  # noqa: E501
import library.features.v4.deposit.transaction_limits.deposit_limits.minimum_initial_deposit as minimum_initial_deposit  # noqa: E501
import library.features.v4.deposit.transaction_limits.deposit_limits.minimum_single_deposit as minimum_single_deposit  # noqa: E501
import library.features.v4.deposit.transaction_limits.withdrawal_limits.maximum_daily_withdrawal as maximum_daily_withdrawal  # noqa: E501
import library.features.v4.deposit.transaction_limits.withdrawal_limits.maximum_daily_withdrawal_by_transaction_type as maximum_daily_withdrawal_by_transaction_type  # noqa: E501
import library.features.v4.deposit.transaction_limits.withdrawal_limits.maximum_single_withdrawal as maximum_single_withdrawal  # noqa: E501
import library.features.v4.deposit.transaction_limits.withdrawal_limits.maximum_withdrawal_by_payment_type as maximum_withdrawal_by_payment_type  # noqa: E501
import library.features.v4.deposit.transaction_limits.withdrawal_limits.minimum_balance_by_tier as minimum_balance_by_tier  # noqa: E501
import library.features.v4.shariah.profit_application as profit_application
import library.features.v4.shariah.tiered_profit_accrual as tiered_profit_accrual

# contracts api
from contracts_api import (
    AccountIdShape,
    ActivationHookArguments,
    ActivationHookResult,
    ConversionHookArguments,
    ConversionHookResult,
    CustomInstruction,
    DeactivationHookArguments,
    DeactivationHookResult,
    DenominationShape,
    Parameter,
    ParameterLevel,
    PostingInstructionsDirective,
    PostParameterChangeHookArguments,
    PostParameterChangeHookResult,
    PostPostingHookArguments,
    PostPostingHookResult,
    PrePostingHookArguments,
    PrePostingHookResult,
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
version = "3.0.1"
display_name = "Shariah Savings Account"
tside = Tside.LIABILITY
supported_denominations = ["MYR"]

# Constants
ACCOUNT_TYPE = "SHARIAH_SAVINGS_ACCOUNT"

# Events
event_types = [
    *profit_application.event_types(ACCOUNT_TYPE),
    *tiered_profit_accrual.event_types(ACCOUNT_TYPE),
]

# Parameters
PARAM_DENOMINATION = "denomination"
PARAM_PAYMENT_TYPE_FEE_INCOME_ACCOUNT = "payment_type_fee_income_account"
parameters = [
    # Template Parameters
    Parameter(
        name=PARAM_DENOMINATION,
        level=ParameterLevel.TEMPLATE,
        description="Currency in which the product operates.",
        display_name="Denomination",
        shape=DenominationShape(),
        default_value="MYR",
    ),
    # Account below used for flat fee, threshold fee, and monthly limit fee.
    Parameter(
        name=PARAM_PAYMENT_TYPE_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for payment type fee income balance.",
        display_name="Payment Type Fee Income Account",
        shape=AccountIdShape(),
        default_value="PAYMENT_TYPE_FEE_INCOME",
    ),
    # Feature Parameters
    *minimum_initial_deposit.parameters,
    *maximum_single_deposit.parameters,
    *minimum_single_deposit.parameters,
    *maximum_balance_limit.parameters,
    *profit_application.parameters,
    *tiered_profit_accrual.all_parameters,
    *payment_type_flat_fee.parameters,
    *payment_type_threshold_fee.parameters,
    *payment_type_monthly_limit_fee.parameters,
    *early_closure_fee.parameters,
    *maximum_single_withdrawal.parameters,
    *maximum_withdrawal_by_payment_type.parameters,
    *minimum_balance_by_tier.parameters,
    *account_tiers.parameters,
    *maximum_daily_deposit.parameters,
    *maximum_daily_withdrawal.parameters,
    *maximum_daily_withdrawal_by_transaction_type.parameters,
]

# Fetchers
data_fetchers = [
    fetchers.EOD_FETCHER,
    fetchers.LIVE_BALANCES_BOF,
    fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER,
    fetchers.EFFECTIVE_DATE_POSTINGS_FETCHER,
]


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def activation_hook(
    vault: SmartContractVault, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    scheduled_events: dict[str, ScheduledEvent] = {}
    effective_datetime = hook_arguments.effective_datetime

    scheduled_events.update(
        tiered_profit_accrual.scheduled_events(vault=vault, start_datetime=effective_datetime)
    )
    scheduled_events.update(
        profit_application.scheduled_events(vault=vault, start_datetime=effective_datetime)
    )

    return ActivationHookResult(scheduled_events_return_value=scheduled_events)


@requires(
    event_type=tiered_profit_accrual.ACCRUAL_EVENT,
    flags=True,
    parameters=True,
)
@fetch_account_data(
    event_type=tiered_profit_accrual.ACCRUAL_EVENT,
    balances=[fetchers.EOD_FETCHER_ID],
)
@requires(
    event_type=profit_application.APPLICATION_EVENT,
    parameters=True,
    calendar=["&{PUBLIC_HOLIDAYS}"],
)
@fetch_account_data(
    event_type=profit_application.APPLICATION_EVENT,
    balances=[fetchers.EOD_FETCHER_ID],
)
def scheduled_event_hook(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    event_type = hook_arguments.event_type
    effective_datetime = hook_arguments.effective_datetime
    custom_instructions: list[CustomInstruction] = []
    update_event_directives: list[UpdateAccountEventTypeDirective] = []
    posting_instructions_directives: list[PostingInstructionsDirective] = []

    if event_type == tiered_profit_accrual.ACCRUAL_EVENT:
        account_tier = account_tiers.get_account_tier(
            vault=vault, effective_datetime=effective_datetime
        )
        custom_instructions.extend(
            tiered_profit_accrual.accrue_profit(
                vault=vault,
                effective_datetime=effective_datetime,
                account_tier=account_tier,
                account_type=ACCOUNT_TYPE,
            )
        )
    elif event_type == profit_application.APPLICATION_EVENT:
        custom_instructions.extend(
            profit_application.apply_profit(vault=vault, account_type=ACCOUNT_TYPE)
        )
        if update_event_result := profit_application.update_next_schedule_execution(
            vault=vault, effective_datetime=effective_datetime
        ):
            update_event_directives.extend([update_event_result])

    if custom_instructions:
        posting_instructions_directives.append(
            PostingInstructionsDirective(
                posting_instructions=custom_instructions,
                client_batch_id=f"{event_type}_{vault.get_hook_execution_id()}",
                value_datetime=hook_arguments.effective_datetime,
            )
        )
    if posting_instructions_directives or update_event_directives:
        return ScheduledEventHookResult(
            posting_instructions_directives=posting_instructions_directives,
            update_account_event_type_directives=update_event_directives,
        )

    return None


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def post_parameter_change_hook(
    vault: SmartContractVault, hook_arguments: PostParameterChangeHookArguments
) -> Optional[PostParameterChangeHookResult]:
    old_parameter_values = hook_arguments.old_parameter_values
    updated_parameter_values = hook_arguments.updated_parameter_values

    if utils.has_parameter_value_changed(
        parameter_name=profit_application.PARAM_PROFIT_APPLICATION_DAY,
        old_parameters=old_parameter_values,
        updated_parameters=updated_parameter_values,
    ):
        schedule_event = profit_application.scheduled_events(
            vault=vault, start_datetime=hook_arguments.effective_datetime
        )[profit_application.APPLICATION_EVENT]

        return PostParameterChangeHookResult(
            update_account_event_type_directives=[
                UpdateAccountEventTypeDirective(
                    event_type=profit_application.APPLICATION_EVENT,
                    expression=schedule_event.expression,
                    schedule_method=schedule_event.schedule_method,
                )
            ],
        )

    return None


@requires(parameters=True)
@fetch_account_data(
    balances=[fetchers.LIVE_BALANCES_BOF_ID],
    postings=[fetchers.EFFECTIVE_DATE_POSTINGS_FETCHER_ID],
)
def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    posting_instructions = hook_arguments.posting_instructions

    if utils.is_force_override(posting_instructions=posting_instructions):
        return None

    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    if denomination_rejection := utils.validate_denomination(
        posting_instructions=posting_instructions, accepted_denominations=[denomination]
    ):
        return PrePostingHookResult(rejection=denomination_rejection)

    balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    # One-off limit checks
    if maximum_balance_limit_rejection := maximum_balance_limit.validate(
        vault=vault,
        postings=posting_instructions,
        denomination=denomination,
        balances=balances,
    ):
        return PrePostingHookResult(rejection=maximum_balance_limit_rejection)

    if minimum_single_deposit_rejection := minimum_single_deposit.validate(
        vault=vault, postings=posting_instructions, denomination=denomination
    ):
        return PrePostingHookResult(rejection=minimum_single_deposit_rejection)

    if maximum_single_deposit_rejection := maximum_single_deposit.validate(
        vault=vault, postings=posting_instructions, denomination=denomination
    ):
        return PrePostingHookResult(rejection=maximum_single_deposit_rejection)

    if minimum_initial_deposit_rejection := minimum_initial_deposit.validate(
        vault=vault,
        postings=posting_instructions,
        denomination=denomination,
        balances=balances,
    ):
        return PrePostingHookResult(rejection=minimum_initial_deposit_rejection)

    if maximum_single_withdrawal_rejection := maximum_single_withdrawal.validate(
        vault=vault, postings=posting_instructions, denomination=denomination
    ):
        return PrePostingHookResult(rejection=maximum_single_withdrawal_rejection)

    if minimum_balance_by_tier_rejection := minimum_balance_by_tier.validate(
        vault=vault,
        postings=posting_instructions,
        balances=balances,
        denomination=denomination,
    ):
        return PrePostingHookResult(rejection=minimum_balance_by_tier_rejection)

    if maximum_withdrawal_by_payment_type_rejection := maximum_withdrawal_by_payment_type.validate(
        vault=vault, postings=posting_instructions, denomination=denomination
    ):
        return PrePostingHookResult(rejection=maximum_withdrawal_by_payment_type_rejection)

    # Daily limit checks
    if maximum_daily_deposit_rejection := maximum_daily_deposit.validate(
        vault=vault, hook_arguments=hook_arguments, denomination=denomination
    ):
        return PrePostingHookResult(rejection=maximum_daily_deposit_rejection)

    if maximum_daily_withdrawal_rejection := maximum_daily_withdrawal.validate(
        vault=vault, hook_arguments=hook_arguments, denomination=denomination
    ):
        return PrePostingHookResult(rejection=maximum_daily_withdrawal_rejection)

    if max_daily_withdrawal_type_rejection := maximum_daily_withdrawal_by_transaction_type.validate(
        vault=vault, hook_arguments=hook_arguments, denomination=denomination
    ):
        return PrePostingHookResult(rejection=max_daily_withdrawal_type_rejection)

    return None


@requires(parameters=True)
@fetch_account_data(postings=[fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID])
def post_posting_hook(
    vault: SmartContractVault, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    postings: utils.PostingInstructionListAlias = hook_arguments.posting_instructions
    effective_datetime = hook_arguments.effective_datetime
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    client_transactions = vault.get_client_transactions(
        fetcher_id=fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID
    )

    flat_fees = payment_type_flat_fee.apply_fees(
        vault=vault, postings=postings, denomination=denomination
    )

    threshold_fees = payment_type_threshold_fee.apply_fees(
        vault=vault, postings=postings, denomination=denomination
    )

    monthly_limit_fees = payment_type_monthly_limit_fee.apply_fees(
        vault=vault,
        effective_datetime=effective_datetime,
        denomination=denomination,
        updated_client_transactions=hook_arguments.client_transactions,
        historic_client_transactions=client_transactions,
    )

    custom_instructions = flat_fees + threshold_fees + monthly_limit_fees

    if custom_instructions:
        return PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=custom_instructions, value_datetime=effective_datetime
                )
            ]
        )
    else:
        return None


def conversion_hook(
    vault: SmartContractVault, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    return ConversionHookResult(scheduled_events_return_value=hook_arguments.existing_schedules)


@requires(parameters=True)
@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
def deactivation_hook(
    vault: SmartContractVault, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    posting_instructions: list[CustomInstruction] = []
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    live_balances = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances
    posting_instructions.extend(
        early_closure_fee.apply_fees(
            vault=vault,
            denomination=denomination,
            balances=live_balances,
            effective_datetime=hook_arguments.effective_datetime,
            account_type=ACCOUNT_TYPE,
        )
    )

    posting_instructions.extend(
        tiered_profit_accrual.get_profit_reversal_postings(
            vault=vault,
            event_name="CLOSE_ACCOUNT",
            denomination=denomination,
            balances=live_balances,
            account_type=ACCOUNT_TYPE,
        )
    )

    if posting_instructions:
        return DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=posting_instructions,
                    value_datetime=hook_arguments.effective_datetime,
                    client_batch_id=f"{vault.get_hook_execution_id()}",
                )
            ],
        )

    return None
