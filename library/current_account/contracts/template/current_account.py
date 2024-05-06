# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from json import dumps
from typing import Optional

# features
import library.features.v4.common.account_tiers as account_tiers
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.deposit.available_balance as available_balance
import library.features.v4.deposit.dormancy as dormancy
import library.features.v4.deposit.fees.inactivity_fee as inactivity_fee
import library.features.v4.deposit.fees.maintenance_fees as maintenance_fees
import library.features.v4.deposit.fees.minimum_monthly_balance as minimum_monthly_balance
import library.features.v4.deposit.fees.partial_fee as partial_fee
import library.features.v4.deposit.fees.unarranged_overdraft_fee as unarranged_overdraft_fee
import library.features.v4.deposit.fees.withdrawal.excess_fee as excess_fee
import library.features.v4.deposit.interest.interest_application as interest_application
import library.features.v4.deposit.interest.overdraft_interest as overdraft_interest
import library.features.v4.deposit.interest.tiered_interest_accrual as tiered_interest_accrual
import library.features.v4.deposit.roundup_autosave as roundup_autosave
import library.features.v4.deposit.transaction_limits.deposit_limits.maximum_balance_limit as maximum_balance_limit  # noqa: E501
import library.features.v4.deposit.transaction_limits.deposit_limits.maximum_daily_deposit as maximum_daily_deposit_limit  # noqa: E501
import library.features.v4.deposit.transaction_limits.deposit_limits.minimum_single_deposit as minimum_single_deposit_limit  # noqa: E501
import library.features.v4.deposit.transaction_limits.overdraft.overdraft_limit as overdraft_limit
import library.features.v4.deposit.transaction_limits.withdrawal_limits.maximum_daily_withdrawal as maximum_daily_withdrawal  # noqa: E501
import library.features.v4.deposit.transaction_limits.withdrawal_limits.maximum_daily_withdrawal_by_transaction_type as maximum_daily_withdrawal_by_transaction_type  # noqa: E501
import library.features.v4.deposit.transaction_limits.withdrawal_limits.minimum_single_withdrawal as minimum_single_withdrawal_limit  # noqa: E501

# contracts api
from contracts_api import (
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
version = "1.1.0"
display_name = "Personal Current Account"
summary = "Personal Current Account Product"
tside = Tside.LIABILITY

# this can be amended to whichever other currencies as needed
supported_denominations = ["EUR", "GBP", "USD"]

PRODUCT_NAME = "CURRENT_ACCOUNT"

FEE_HIERARCHY = [
    maintenance_fees.PARTIAL_FEE_DETAILS,
    minimum_monthly_balance.PARTIAL_FEE_DETAILS,
    inactivity_fee.PARTIAL_FEE_DETAILS,
]

# Parameters
PREFIX_FEES_APPLICATION = "fees_application"
PARAM_ADDITIONAL_DENOMINATIONS = "additional_denominations"
PARAM_ACCOUNT_TIER_NAME = "account_tier_name"
parameters = [
    Parameter(
        name=PARAM_ADDITIONAL_DENOMINATIONS,
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        description="Currencies that are accepted for this account, "
        "formatted as a json list of currency codes",
        display_name="Additional Denominations",
        default_value=dumps(["EUR", "USD"]),
    ),
    Parameter(
        name=PARAM_ACCOUNT_TIER_NAME,
        shape=StringShape(),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="Account tier name of the account",
        display_name="Account Tier Name",
    ),
    *account_tiers.parameters,
    common_parameters.denomination_parameter,
    *dormancy.parameters,
    *excess_fee.parameters,
    *inactivity_fee.parameters,
    *interest_application.parameters,
    *maintenance_fees.parameters,
    *maximum_balance_limit.parameters,
    *maximum_daily_withdrawal_by_transaction_type.parameters,
    *maximum_daily_deposit_limit.parameters,
    *maximum_daily_withdrawal.parameters,
    *minimum_monthly_balance.parameters,
    *minimum_single_deposit_limit.parameters,
    *minimum_single_withdrawal_limit.parameters,
    *overdraft_interest.parameters,
    *overdraft_limit.parameters,
    *roundup_autosave.parameters,
    *tiered_interest_accrual.parameters,
    *unarranged_overdraft_fee.feature_parameters,
    *unarranged_overdraft_fee.application_schedule_parameters,
]

# Fetchers
data_fetchers = [
    fetchers.EOD_FETCHER,
    fetchers.EFFECTIVE_DATE_POSTINGS_FETCHER,
    fetchers.EFFECTIVE_OBSERVATION_FETCHER,
    fetchers.LIVE_BALANCES_BOF,
    fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER,
    *fetchers.PREVIOUS_EOD_OBSERVATION_FETCHERS,
]

# Events

event_types = [
    *inactivity_fee.event_types(product_name=PRODUCT_NAME),
    *interest_application.event_types(PRODUCT_NAME),
    *maintenance_fees.event_types(product_name=PRODUCT_NAME, frequency=maintenance_fees.MONTHLY),
    *maintenance_fees.event_types(product_name=PRODUCT_NAME, frequency=maintenance_fees.ANNUALLY),
    *tiered_interest_accrual.event_types(PRODUCT_NAME),
    *minimum_monthly_balance.event_types(PRODUCT_NAME),
    *unarranged_overdraft_fee.application_event_types(PRODUCT_NAME),
]
CLOSE_ACCOUNT = "CLOSE_ACCOUNT"


# Vault hooks
@requires(parameters=True)
def activation_hook(
    vault: SmartContractVault, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    scheduled_events: dict[str, ScheduledEvent] = {}
    start_datetime_at_midnight = hook_arguments.effective_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    scheduled_events = {
        **inactivity_fee.scheduled_events(
            vault=vault, start_datetime=start_datetime_at_midnight + relativedelta(months=1)
        ),
        **interest_application.scheduled_events(
            vault=vault, reference_datetime=start_datetime_at_midnight
        ),
        **maintenance_fees.scheduled_events(
            vault=vault,
            start_datetime=start_datetime_at_midnight,
            frequency=maintenance_fees.MONTHLY,
        ),
        **maintenance_fees.scheduled_events(
            vault=vault,
            start_datetime=start_datetime_at_midnight,
            frequency=maintenance_fees.ANNUALLY,
        ),
        **minimum_monthly_balance.scheduled_events(
            vault=vault, start_datetime=start_datetime_at_midnight + relativedelta(months=1)
        ),
        **tiered_interest_accrual.scheduled_events(
            vault=vault, start_datetime=start_datetime_at_midnight + relativedelta(days=1)
        ),
        **unarranged_overdraft_fee.application_scheduled_events(
            vault=vault,
            start_datetime=start_datetime_at_midnight,
        ),
    }

    return ActivationHookResult(scheduled_events_return_value=scheduled_events)


@fetch_account_data(
    event_type=inactivity_fee.APPLICATION_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@fetch_account_data(
    event_type=tiered_interest_accrual.ACCRUAL_EVENT,
    balances=[
        fetchers.EOD_FETCHER_ID,
        fetchers.PREVIOUS_EOD_1_FETCHER_ID,
        fetchers.PREVIOUS_EOD_2_FETCHER_ID,
        fetchers.PREVIOUS_EOD_3_FETCHER_ID,
        fetchers.PREVIOUS_EOD_4_FETCHER_ID,
        fetchers.PREVIOUS_EOD_5_FETCHER_ID,
    ],
)
@fetch_account_data(
    event_type=interest_application.APPLICATION_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@fetch_account_data(
    event_type=maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@fetch_account_data(
    event_type=minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT,
    balances=[
        fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID,
        fetchers.EOD_FETCHER_ID,
        *fetchers.PREVIOUS_EOD_OBSERVATION_FETCHER_IDS,
    ],
)
@fetch_account_data(
    event_type=unarranged_overdraft_fee.APPLICATION_EVENT,
    balances=[fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID],
)
@requires(event_type=inactivity_fee.APPLICATION_EVENT, flags=True, parameters=True)
@requires(event_type=tiered_interest_accrual.ACCRUAL_EVENT, parameters=True)
@requires(event_type=interest_application.APPLICATION_EVENT, parameters=True)
@requires(event_type=maintenance_fees.APPLY_MONTHLY_FEE_EVENT, flags=True, parameters=True)
@requires(event_type=maintenance_fees.APPLY_ANNUAL_FEE_EVENT, flags=True, parameters=True)
@requires(
    event_type=minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT,
    flags=True,
    parameters=True,
)
@requires(event_type=unarranged_overdraft_fee.APPLICATION_EVENT, flags=True, parameters=True)
def scheduled_event_hook(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    event_type: str = hook_arguments.event_type
    effective_datetime: datetime = hook_arguments.effective_datetime

    posting_directives: list[PostingInstructionsDirective] = []
    posting_instructions: list[CustomInstruction] = []
    update_event_directives: list[UpdateAccountEventTypeDirective] = []

    if event_type == tiered_interest_accrual.ACCRUAL_EVENT:
        posting_instructions.extend(
            tiered_interest_accrual.accrue_interest(
                vault=vault, effective_datetime=effective_datetime
            )
        )
        posting_instructions.extend(
            overdraft_interest.accrue_interest(
                vault=vault, effective_datetime=effective_datetime, account_type=PRODUCT_NAME
            )
        )

        posting_instructions.extend(unarranged_overdraft_fee.accrue_fee(vault=vault))

    elif event_type == interest_application.APPLICATION_EVENT:
        posting_instructions.extend(
            interest_application.apply_interest(vault=vault, account_type=PRODUCT_NAME)
        )
        posting_instructions.extend(
            overdraft_interest.apply_interest(vault=vault, account_type=PRODUCT_NAME)
        )
        if update_event_result := interest_application.update_next_schedule_execution(
            vault=vault, effective_datetime=effective_datetime
        ):
            update_event_directives.extend([update_event_result])

    elif event_type == inactivity_fee.APPLICATION_EVENT:
        if inactivity_fee.is_account_inactive(vault=vault, effective_datetime=effective_datetime):
            posting_instructions.extend(
                inactivity_fee.apply(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    available_balance_feature=overdraft_limit.OverdraftLimitAvailableBalance,
                )
            )

    elif event_type == maintenance_fees.APPLY_MONTHLY_FEE_EVENT:
        if not dormancy.is_account_dormant(vault=vault, effective_datetime=effective_datetime):
            posting_instructions.extend(
                maintenance_fees.apply_monthly_fee(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    available_balance_feature=overdraft_limit.OverdraftLimitAvailableBalance,
                )
            )

    elif event_type == maintenance_fees.APPLY_ANNUAL_FEE_EVENT:
        if not dormancy.is_account_dormant(vault=vault, effective_datetime=effective_datetime):
            posting_instructions.extend(
                maintenance_fees.apply_annual_fee(
                    vault=vault, effective_datetime=effective_datetime
                )
            )

        if update_event_result := maintenance_fees.update_next_annual_schedule_execution(
            vault=vault, effective_datetime=effective_datetime
        ):
            update_event_directives.extend([update_event_result])

    elif event_type == minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT:
        if not dormancy.is_account_dormant(vault=vault, effective_datetime=effective_datetime):
            denomination = common_parameters.get_denomination_parameter(
                vault=vault, effective_datetime=effective_datetime
            )
            posting_instructions.extend(
                minimum_monthly_balance.apply_minimum_balance_fee(
                    vault=vault,
                    effective_datetime=effective_datetime,
                    denomination=denomination,
                    available_balance_feature=overdraft_limit.OverdraftLimitAvailableBalance,
                )
            )
    elif event_type == unarranged_overdraft_fee.APPLICATION_EVENT:
        if not dormancy.is_account_dormant(vault=vault, effective_datetime=effective_datetime):
            posting_instructions.extend(unarranged_overdraft_fee.apply_fee(vault=vault))

    if posting_instructions:
        posting_directives.append(
            PostingInstructionsDirective(
                posting_instructions=posting_instructions,
                value_datetime=effective_datetime,
                client_batch_id=f"{vault.get_hook_execution_id()}_{event_type}",
            )
        )

    if posting_directives or update_event_directives:
        return ScheduledEventHookResult(
            posting_instructions_directives=posting_directives,
            update_account_event_type_directives=update_event_directives,
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


@requires(parameters=True, flags=True)
@fetch_account_data(
    balances=[fetchers.LIVE_BALANCES_BOF_ID],
    postings=[fetchers.EFFECTIVE_DATE_POSTINGS_FETCHER_ID],
)
def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    if utils.is_force_override(posting_instructions=hook_arguments.posting_instructions):
        return None

    effective_datetime = hook_arguments.effective_datetime

    if account_dormant_rejection := dormancy.validate_account_transaction(
        vault=vault,
        effective_datetime=effective_datetime,
    ):
        return PrePostingHookResult(rejection=account_dormant_rejection)

    denomination = common_parameters.get_denomination_parameter(
        vault=vault, effective_datetime=effective_datetime
    )
    additional_denominations: list[str] = utils.get_parameter(
        vault=vault, name=PARAM_ADDITIONAL_DENOMINATIONS, is_json=True
    )
    allowed_denominations = additional_denominations + [denomination]

    if invalid_denomination_rejection := utils.validate_denomination(
        posting_instructions=hook_arguments.posting_instructions,
        accepted_denominations=allowed_denominations,
    ):
        return PrePostingHookResult(rejection=invalid_denomination_rejection)

    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances

    # Available balance checks if the postings exceed balances for other denominations.
    if exceeding_balance_rejection := available_balance.validate(
        balances=balances,
        denominations=additional_denominations,
        posting_instructions=hook_arguments.posting_instructions,
    ):
        return PrePostingHookResult(rejection=exceeding_balance_rejection)

    # Overdraft limit only applies to the main denomination
    if overdraft_limit_rejection := overdraft_limit.validate(
        vault=vault,
        postings=hook_arguments.posting_instructions,
        denomination=denomination,
        balances=balances,
    ):
        return PrePostingHookResult(rejection=overdraft_limit_rejection)

    if minimum_single_deposit_rejection := minimum_single_deposit_limit.validate(
        vault=vault,
        postings=hook_arguments.posting_instructions,
        denomination=denomination,
    ):
        return PrePostingHookResult(rejection=minimum_single_deposit_rejection)

    if minimum_single_withdrawal_rejection := minimum_single_withdrawal_limit.validate(
        vault=vault,
        postings=hook_arguments.posting_instructions,
        denomination=denomination,
    ):
        return PrePostingHookResult(rejection=minimum_single_withdrawal_rejection)

    if maximum_balance_rejection := maximum_balance_limit.validate(
        vault=vault,
        postings=hook_arguments.posting_instructions,
        denomination=denomination,
        balances=balances,
    ):
        return PrePostingHookResult(rejection=maximum_balance_rejection)

    # retrieve all the relevant client transactions and re-use across all daily transaction limits
    effective_date_client_transactions = vault.get_client_transactions(
        fetcher_id=fetchers.EFFECTIVE_DATE_POSTINGS_FETCHER_ID
    )

    if maximum_daily_withdrawal_rejection := maximum_daily_withdrawal.validate(
        vault=vault,
        hook_arguments=hook_arguments,
        denomination=denomination,
        effective_date_client_transactions=effective_date_client_transactions,
    ):
        return PrePostingHookResult(rejection=maximum_daily_withdrawal_rejection)

    if maximum_daily_deposit_rejection := maximum_daily_deposit_limit.validate(
        vault=vault,
        hook_arguments=hook_arguments,
        denomination=denomination,
        effective_date_client_transactions=effective_date_client_transactions,
    ):
        return PrePostingHookResult(rejection=maximum_daily_deposit_rejection)

    if maximum_daily_withdrawal_by_transaction_rejection := (
        maximum_daily_withdrawal_by_transaction_type.validate(
            vault=vault,
            hook_arguments=hook_arguments,
            denomination=denomination,
            effective_date_client_transactions=effective_date_client_transactions,
        )
    ):
        return PrePostingHookResult(rejection=maximum_daily_withdrawal_by_transaction_rejection)

    return None


@fetch_account_data(
    balances=[fetchers.LIVE_BALANCES_BOF_ID],
    postings=[fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID],
)
@requires(parameters=True)
def post_posting_hook(
    vault: SmartContractVault, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    posting_instructions_directives: list[PostingInstructionsDirective] = []
    posting_instructions: list[CustomInstruction] = []

    effective_datetime = hook_arguments.effective_datetime
    denomination = common_parameters.get_denomination_parameter(
        vault=vault, effective_datetime=effective_datetime
    )
    balances: BalanceDefaultDict = vault.get_balances_observation(
        fetcher_id=fetchers.LIVE_BALANCES_BOF_ID
    ).balances

    if autosave_posting_instructions := roundup_autosave.apply(
        vault=vault,
        postings=hook_arguments.posting_instructions,
        denomination=denomination,
        balances=balances,
    ):

        # Auto save postings are special case as the failure of auto save
        # shouldn't impact rest of posting instructions.
        # Also remaining features should be consolidated into a single PostingInstructionsDirective
        posting_instructions_directives.append(
            PostingInstructionsDirective(
                posting_instructions=autosave_posting_instructions,
                value_datetime=effective_datetime,
            )
        )
        balances = utils.update_inflight_balances(
            account_id=vault.account_id,
            tside=tside,
            current_balances=balances,
            posting_instructions=autosave_posting_instructions,  # type: ignore
        )

    if excess_fee_instructions := excess_fee.apply(
        vault=vault,
        proposed_client_transactions=hook_arguments.client_transactions,
        effective_datetime=effective_datetime,
        denomination=denomination,
        account_type=PRODUCT_NAME,
    ):
        posting_instructions.extend(excess_fee_instructions)
        balances = utils.update_inflight_balances(
            account_id=vault.account_id,
            tside=tside,
            current_balances=balances,
            posting_instructions=excess_fee_instructions,  # type: ignore
        )

    posting_instructions.extend(
        partial_fee.charge_outstanding_fees(
            vault=vault,
            effective_datetime=effective_datetime,
            fee_collection=FEE_HIERARCHY,
            balances=balances,
            denomination=denomination,
            available_balance_feature=overdraft_limit.OverdraftLimitAvailableBalance,
        )
    )

    if posting_instructions:
        posting_instructions_directives.append(
            PostingInstructionsDirective(
                posting_instructions=posting_instructions,
                value_datetime=effective_datetime,
            )
        )
    if posting_instructions_directives:
        return PostPostingHookResult(
            posting_instructions_directives=posting_instructions_directives
        )

    return None


def conversion_hook(
    vault: SmartContractVault, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    return ConversionHookResult(scheduled_events_return_value=hook_arguments.existing_schedules)


@fetch_account_data(balances=[fetchers.LIVE_BALANCES_BOF_ID])
@requires(parameters=True, flags=True)
def deactivation_hook(
    vault: SmartContractVault, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    effective_datetime: datetime = hook_arguments.effective_datetime

    posting_directives: list[PostingInstructionsDirective] = []

    if dormancy.is_account_dormant(vault=vault, effective_datetime=effective_datetime):
        return DeactivationHookResult(
            rejection=Rejection(
                message="Cannot close a dormant account.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

    balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances
    denomination = common_parameters.get_denomination_parameter(
        vault=vault, effective_datetime=effective_datetime
    )

    if partial_fee.has_outstanding_fees(
        vault=vault, fee_collection=FEE_HIERARCHY, balances=balances, denomination=denomination
    ):
        return DeactivationHookResult(
            rejection=Rejection(
                message="Cannot close account with outstanding fees.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

    posting_instructions = _clean_up_accrued_and_overdraft_interest(
        vault=vault, balances=balances, denomination=denomination
    )

    posting_instructions.extend(
        unarranged_overdraft_fee.apply_fee(
            vault=vault, balances=balances, denomination=denomination
        )
    )

    if posting_instructions:
        posting_directives.append(
            PostingInstructionsDirective(
                posting_instructions=posting_instructions,
                value_datetime=effective_datetime,
                client_batch_id=f"{vault.get_hook_execution_id()}_{CLOSE_ACCOUNT}",
            )
        )
        return DeactivationHookResult(posting_instructions_directives=posting_directives)

    return None


def _clean_up_accrued_and_overdraft_interest(
    vault: SmartContractVault, balances: BalanceDefaultDict, denomination: str
) -> list[CustomInstruction]:
    """
    Applies/reverses all accrued interest during account closure.
    Any interest accrued should be returned to the bank's internal account.

    :param vault: vault object used to create interest postings for account closure
    :param balances: Account balances
    :param denomination: The denomination of the account
    :return: The application/reversal posting instructions
    """
    clean_up_posting_instructions: list[CustomInstruction] = []

    clean_up_posting_instructions.extend(
        tiered_interest_accrual.get_interest_reversal_postings(
            vault=vault,
            event_name=CLOSE_ACCOUNT,
            account_type=PRODUCT_NAME,
            balances=balances,
            denomination=denomination,
        )
    )
    clean_up_posting_instructions.extend(
        overdraft_interest.get_interest_reversal_postings(
            vault=vault,
            event_name=CLOSE_ACCOUNT,
            account_type=PRODUCT_NAME,
            balances=balances,
            denomination=denomination,
        )
    )
    return clean_up_posting_instructions


@requires(parameters=True, flags=True)
def derived_parameter_hook(
    vault: SmartContractVault, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:
    effective_datetime: datetime = hook_arguments.effective_datetime

    derived_parameters: dict[str, utils.ParameterValueTypeAlias] = {
        PARAM_ACCOUNT_TIER_NAME: account_tiers.get_account_tier(
            vault=vault, effective_datetime=effective_datetime
        )
    }

    return DerivedParameterHookResult(parameters_return_value=derived_parameters)
