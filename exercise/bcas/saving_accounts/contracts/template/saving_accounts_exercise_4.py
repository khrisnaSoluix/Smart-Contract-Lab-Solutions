# standard libs
from decimal import Decimal
from typing import Optional,Union
from dateutil.relativedelta import relativedelta

from contracts_api import (
    BalancesObservationFetcher,
    DefinedDateTime,
    DenominationShape,
    fetch_account_data,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    PrePostingHookArguments,
    PrePostingHookResult,
    Rejection,
    RejectionReason,
    requires,
    Tside,

    AccountIdShape,
    NumberShape,

    ActivationHookArguments,
    ActivationHookResult,
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    PostingInstructionsDirective,

    TransactionCode,
    CustomInstruction,
    Posting,
    Phase,
    SmartContractEventType,
    ScheduledEventHookArguments,
    BalanceCoordinate,
    UpdateAccountEventTypeDirective,
    ScheduledEventHookResult,
    ScheduleExpression,
    ScheduledEvent,
    PreParameterChangeHookArguments,
    PreParameterChangeHookResult,
    BalanceDefaultDict,
    AuthorisationAdjustment,
    InboundAuthorisation,
    InboundHardSettlement,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Release,
    Settlement,
    Transfer,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
)

from inception_sdk.vault.contracts.extensions.contracts_api_extensions.vault_types import SmartContractVault


api = "4.0.0"
version = "1.0.0"
display_name = "Saving Account"
summary = "Personal Savings Account Product"
tside = Tside.LIABILITY
supported_denominations = ["IDR"]

# CONSTANTS
PARAM_DENOMINATION = "denomination"
PARAM_BONUS_PAYABLE_INTERNAL_ACCOUNT = "deposit_bonus_payout_internal_account"
PARAM_ZAKAT_INTERNAL_ACCOUNT = "zakat_internal_account"
PARAM_OPENING_BONUS = 'opening_bonus'
PARAM_ZAKAT_RATE = 'zakat_rate'
PARAM_AVAILABLE_DEPOSIT_LIMIT = 'available_deposit_limit'
PARAM_MAXIMUM_BALANCE_LIMIT = 'maximum_balance_limit'

EVENT_ACCOUNT_OPENING_BONUS = "ACCOUNT_OPENING_BONUS"

parameters = [
    Parameter(
        name=PARAM_DENOMINATION,
        shape=DenominationShape(),
        level=ParameterLevel.TEMPLATE,
        display_name="Denomination",
        description="The default denomination of the account.",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value="IDR",
    ),
    Parameter(
        name=PARAM_MAXIMUM_BALANCE_LIMIT,
        display_name="Maximum Deposit Limit",
        description="The maximum balance possible for this account.",
        level=ParameterLevel.TEMPLATE,
        shape=NumberShape(min_value=0, max_value=100000, step=Decimal("0.01")),
        default_value=Decimal("100000"),
    ),
    Parameter(
        name=PARAM_BONUS_PAYABLE_INTERNAL_ACCOUNT,
        display_name="Deposit Bonus Payout Internal Account",
        description="The internal account to debit bonus payments from.",
        level=ParameterLevel.TEMPLATE,
        shape=AccountIdShape(),
        default_value="BONUS_PAYABLE_INTERNAL_ACCOUNT",
    ),
    Parameter(
        name=PARAM_ZAKAT_INTERNAL_ACCOUNT,
        display_name="Zakat Internal Account",
        description="The internal account to credit zakat from customer.",
        level=ParameterLevel.TEMPLATE,
        shape=AccountIdShape(),
        default_value="ZAKAT_INTERNAL_ACCOUNT",
    ),
    # instance parameters
    Parameter(
        name=PARAM_OPENING_BONUS,
        display_name="Opening Bonus",
        description="The bonus amount to credit the account upon opening.",
        level=ParameterLevel.INSTANCE,
        shape=NumberShape(min_value=0, max_value=100, step=Decimal("0.01")),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=Decimal("100.00"),
    ),
    Parameter(
        name=PARAM_ZAKAT_RATE,
        display_name="Zakat Rate",
        description="Percentage of zakat rate to be deducted from the net bonus amount (after tax)"
        " received by the customer every month.",
        level=ParameterLevel.INSTANCE,
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        shape=NumberShape(min_value=0, max_value=1, step=Decimal("0.001")),
        default_value=Decimal("0.01"),
    ),
    # derived parameters
    Parameter(
        name=PARAM_AVAILABLE_DEPOSIT_LIMIT,
        display_name="Available Deposit Limit",
        description="The available deposit limit remaining based on current account balance.",
        level=ParameterLevel.INSTANCE,
        shape=NumberShape(min_value=0, step=1),
        derived=True,
    ),
]

data_fetchers = [
    BalancesObservationFetcher(
        fetcher_id="live_balances",
        at=DefinedDateTime.LIVE,
    ),
]

@requires(parameters=True)
@fetch_account_data(balances=["live_balances"])
def pre_posting_hook(vault: SmartContractVault, hook_arguments: PrePostingHookArguments):
    denomination = vault.get_parameter_timeseries(name=PARAM_DENOMINATION).latest()

    # check denomination
    posting_instructions = hook_arguments.posting_instructions

    posting_denominations_used = set(post.denomination for post in posting_instructions)
    disallowed_denominations_used = posting_denominations_used.difference(
        [denomination]
    )
    if disallowed_denominations_used:
        return PrePostingHookResult(
            rejection=Rejection(
                message=f"Postings are not allowed. Only postings in {denomination} are accepted.",
                reason_code=RejectionReason.WRONG_DENOMINATION,
            )
        )
    
    # check deposit limit
    deposit_limit = Decimal(
        vault.get_parameter_timeseries(name="maximum_balance_limit").latest()
    )
    # check existing account balance on the DEFAULT address using the fetcher
    balances = vault.get_balances_observation(fetcher_id="live_balances").balances
    default_balance = balances[
        BalanceCoordinate(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net

    # check expected total balance taking into account existing balance and incoming postings
    incoming_postings_amount = total_balances(hook_arguments.posting_instructions)[
        BalanceCoordinate(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    expected_balance_total = incoming_postings_amount + default_balance

    if expected_balance_total > deposit_limit:
        return PrePostingHookResult(
            rejection=Rejection(
                message=f"Incoming deposit breaches deposit limit of {deposit_limit}.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
    

@requires(parameters=True)
def activation_hook(
    vault: SmartContractVault, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    denomination = vault.get_parameter_timeseries(name=PARAM_DENOMINATION).latest()
    opening_bonus = Decimal(
        vault.get_parameter_timeseries(name=PARAM_OPENING_BONUS).latest()
    )
    zakat_rate = Decimal(
        vault.get_parameter_timeseries(name=PARAM_ZAKAT_RATE).latest()
    )
    bonus_internal_account = vault.get_parameter_timeseries(
        name=PARAM_BONUS_PAYABLE_INTERNAL_ACCOUNT
    ).latest()
    zakat_internal_account = vault.get_parameter_timeseries(
        name=PARAM_ZAKAT_INTERNAL_ACCOUNT
    ).latest()
    zakat = opening_bonus * zakat_rate
    
    posting_instruction = _move_funds_between_vault_accounts(
        from_account_id=bonus_internal_account,
        from_account_address=DEFAULT_ADDRESS,
        to_account_id=vault.account_id,
        to_account_address=DEFAULT_ADDRESS,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        amount=opening_bonus,
        instruction_details={
            "ext_client_transaction_id": f"OPENING_BONUS_{vault.get_hook_execution_id()}",
            "description": f"Opening bonus of {opening_bonus} {denomination} paid.",
            "event_type": f"{EVENT_ACCOUNT_OPENING_BONUS}",
        },
        override_all_restrictions=True,
    )
    posting_instruction.extend(
        _move_funds_between_vault_accounts(
            from_account_id=vault.account_id,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=zakat_internal_account,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            denomination=denomination,
            amount=zakat,
            instruction_details={
                "ext_client_transaction_id": f"ZAKAT_{vault.get_hook_execution_id()}",
                "description": f"Zakat of {zakat} {denomination} paid.",
                "event_type": f"{EVENT_ACCOUNT_OPENING_BONUS}",
            },
            override_all_restrictions=True,
        )
    )
   
    return ActivationHookResult(
        posting_instructions_directives=[
            PostingInstructionsDirective(
                posting_instructions=posting_instruction,
                value_datetime=hook_arguments.effective_datetime,
            )
        ],
    )


@requires(parameters=True)
def pre_parameter_change_hook(vault: SmartContractVault, hook_arguments: PreParameterChangeHookArguments):
    restricted_parameters = [PARAM_ZAKAT_RATE]
    updated_parameters = hook_arguments.updated_parameter_values
    if any(restricted_param in updated_parameters for restricted_param in restricted_parameters):
        return PreParameterChangeHookResult(
            rejection=Rejection(
                message="Cannot update the zakat rate after account creation",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
    

@requires(parameters=True)
@fetch_account_data(balances=["live_balances"])
def derived_parameter_hook(vault, hook_arguments: DerivedParameterHookArguments):
    denomination = vault.get_parameter_timeseries(name=PARAM_DENOMINATION).latest()
    deposit_limit = Decimal(
        vault.get_parameter_timeseries(name=PARAM_MAXIMUM_BALANCE_LIMIT).latest()
    )

    balances = vault.get_balances_observation(fetcher_id="live_balances").balances
    default_balance = balances[
        BalanceCoordinate(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net

    available_deposit_limit = deposit_limit - default_balance

    return DerivedParameterHookResult(
        parameters_return_value={PARAM_AVAILABLE_DEPOSIT_LIMIT: available_deposit_limit}
    )


def total_balances(
    input_posting_instructions: list[
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
) -> BalanceDefaultDict:
    total_balances = BalanceDefaultDict()
    for posting_instruction in input_posting_instructions:
        total_balances += posting_instruction.balances()
    return total_balances

def _move_funds_between_vault_accounts(
    amount: Decimal,
    denomination: str,
    from_account_id: str,
    from_account_address: str,
    to_account_id: str,
    to_account_address: str,
    instruction_details: dict[str, str],
    asset: str = DEFAULT_ASSET,
    transaction_code: Optional[TransactionCode] = None,
    override_all_restrictions: Optional[bool] = None,
) -> list[CustomInstruction]:
    postings = [
        Posting(
            credit=True,
            amount=amount,
            denomination=denomination,
            account_id=to_account_id,
            account_address=to_account_address,
            asset=asset,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=False,
            amount=amount,
            denomination=denomination,
            account_id=from_account_id,
            account_address=from_account_address,
            asset=asset,
            phase=Phase.COMMITTED,
        ),
    ]
    custom_instruction = CustomInstruction(
        postings=postings,
        instruction_details=instruction_details,
        transaction_code=transaction_code,
        override_all_restrictions=override_all_restrictions,
    )

    return [custom_instruction]