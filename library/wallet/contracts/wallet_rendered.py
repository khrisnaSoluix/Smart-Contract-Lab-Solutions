# Code auto-generated using Inception Smart Contract Renderer Version 2.0.1


# Objects below have been imported from:
#    wallet.py
# md5:c2f7282e542c68334dee406c4fc3ca65

from contracts_api import (
    BalancesObservationFetcher,
    DefinedDateTime,
    Override,
    PostingsIntervalFetcher,
    RelativeDateTime,
    Shift,
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
    AccountIdShape,
    ActivationHookArguments,
    ActivationHookResult,
    DeactivationHookArguments,
    DeactivationHookResult,
    DenominationShape,
    NumberShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    PostingInstructionsDirective,
    PostParameterChangeHookArguments,
    PostParameterChangeHookResult,
    PostPostingHookArguments,
    PostPostingHookResult,
    PrePostingHookArguments,
    PrePostingHookResult,
    ScheduledEventHookArguments,
    ScheduledEventHookResult,
    SmartContractEventType,
    StringShape,
    fetch_account_data,
    requires,
)
from calendar import isleap
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP
from json import dumps, loads
from typing import Optional, Any, Iterable, Mapping, Union
from zoneinfo import ZoneInfo

api = "4.0.0"
version = "3.0.1"
display_name = "Wallet Account"
tside = Tside.LIABILITY
supported_denominations = ["GBP", "SGD", "USD"]


@requires(parameters=True)
def activation_hook(
    vault: Any, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    scheduled_events: dict[str, ScheduledEvent] = {}
    scheduled_events[ZERO_OUT_DAILY_SPEND_EVENT] = ScheduledEvent(
        start_datetime=effective_datetime, expression=_get_zero_out_daily_spend_schedule(vault)
    )
    return ActivationHookResult(scheduled_events_return_value=scheduled_events)


@requires(parameters=True)
@fetch_account_data(balances=["live_balances_bof"])
def deactivation_hook(
    vault: Any, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    zero_out_daily_spend_directives = _get_zero_out_daily_spend_instructions(
        vault,
        effective_datetime=hook_arguments.effective_datetime,
        balance_fetcher=fetchers_LIVE_BALANCES_BOF_ID,
    )
    if zero_out_daily_spend_directives:
        return DeactivationHookResult(
            posting_instructions_directives=zero_out_daily_spend_directives
        )
    return None


@requires(parameters=True)
@fetch_account_data(balances=["live_balances_bof"])
def post_parameter_change_hook(
    vault: Any, hook_arguments: PostParameterChangeHookArguments
) -> Optional[PostParameterChangeHookResult]:
    """
    Checks if the customer or bank wallet limit has been lowered and sweep
    to the nominated account if so.
    """
    old_parameter_values = hook_arguments.old_parameter_values
    updated_parameter_values = hook_arguments.updated_parameter_values
    old_limit: Decimal = old_parameter_values.get(PARAM_CUSTOMER_WALLET_LIMIT, Decimal(0))
    new_limit: Decimal = updated_parameter_values.get(PARAM_CUSTOMER_WALLET_LIMIT, old_limit)
    if old_limit > new_limit:
        denomination = utils_get_parameter(vault, name=PARAM_DENOMINATION)
        live_balances = vault.get_balances_observation(
            fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
        ).balances
        current_balance = utils_get_available_balance(
            balances=live_balances, denomination=denomination
        )
        if current_balance > new_limit:
            delta = current_balance - new_limit
            nominated_account = utils_get_parameter(vault, name=PARAM_NOMINATED_ACCOUNT)
            posting_instructions = _sweep_excess_funds(
                account_id=vault.account_id,
                amount=delta,
                denomination=denomination,
                nominated_account=nominated_account,
            )
            pi_directive = PostingInstructionsDirective(
                posting_instructions=posting_instructions,
                value_datetime=hook_arguments.effective_datetime,
            )
            return PostParameterChangeHookResult(posting_instructions_directives=[pi_directive])
    return None


@requires(parameters=True, flags=True)
@fetch_account_data(balances=["live_balances_bof"])
def post_posting_hook(
    vault: Any, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    """
    If the posting is a Spend, duplicates the spending to TODAYS_SPENDING to keep track
    of the remaining spending limit.
    If the posting is a refund or a release/decreased auth,
    the previously duplicated amount is unduplicated
    If the posting is a Deposit, checks if we have reached our limit then posts the
    remainder to the nominated account if we breach it.
    """
    postings: utils_PostingInstructionListAlias = hook_arguments.posting_instructions
    effective_datetime = hook_arguments.effective_datetime
    denomination = utils_get_parameter(vault, name=PARAM_DENOMINATION)
    postings_balances = [posting.balances() for posting in postings]
    postings_delta = Decimal(
        sum(
            (
                utils_get_available_balance(balances=balances, denomination=denomination)
                for balances in postings_balances
            )
        )
    )
    auto_top_up_status = vault.get_flag_timeseries(flag=AUTO_TOP_UP_FLAG).latest()
    nominated_account = utils_get_parameter(vault, name=PARAM_NOMINATED_ACCOUNT)
    balances = vault.get_balances_observation(fetcher_id=fetchers_LIVE_BALANCES_BOF_ID).balances
    current_balance = utils_get_available_balance(balances=balances, denomination=denomination)
    release_and_decreased_auth_amount = _get_release_and_decreased_auth_amount(
        postings, denomination
    )
    posting_ins = []
    if current_balance < 0 and auto_top_up_status:
        amount_required_from_nominated = abs(current_balance)
        posting_ins += _top_up_balance(
            account_id=vault.account_id,
            amount=amount_required_from_nominated,
            denomination=denomination,
            nominated_account=nominated_account,
        )
    force_override = any(extract_bool_from_postings(postings, "force_override"))
    refund = any(extract_bool_from_postings(postings, "refund"))
    transfer_to_nominated_acct = any(
        extract_bool_from_postings(postings, "withdrawal_to_nominated_account")
    )
    if (
        postings_delta < 0
        and (not (force_override or transfer_to_nominated_acct))
        or (postings_delta > 0 and refund)
    ):
        posting_ins += _update_tracked_spend(
            account_id=vault.account_id, amount=postings_delta, denomination=denomination
        )
    elif postings_delta > 0 and release_and_decreased_auth_amount > 0:
        posting_ins += _update_tracked_spend(
            account_id=vault.account_id,
            amount=release_and_decreased_auth_amount,
            denomination=denomination,
        )
    if postings_delta > 0:
        wallet_limit = utils_get_parameter(vault, name=PARAM_CUSTOMER_WALLET_LIMIT)
        if current_balance > wallet_limit:
            nominated_account = utils_get_parameter(vault, name=PARAM_NOMINATED_ACCOUNT)
            difference = current_balance - wallet_limit
            posting_ins += _sweep_excess_funds(
                account_id=vault.account_id,
                amount=difference,
                denomination=denomination,
                nominated_account=nominated_account,
            )
    if posting_ins:
        return PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=posting_ins, value_datetime=effective_datetime
                )
            ]
        )
    return None


@requires(parameters=True, flags=True)
@fetch_account_data(balances=["live_balances_bof"])
def pre_posting_hook(
    vault: Any, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    if utils_is_force_override(posting_instructions=hook_arguments.posting_instructions):
        return None
    posting_instructions: utils_PostingInstructionListAlias = hook_arguments.posting_instructions
    spending_limit = utils_get_parameter(vault, name=PARAM_SPENDING_LIMIT)
    default_denomination = utils_get_parameter(vault, name=PARAM_DENOMINATION)
    account_balances = vault.get_balances_observation(
        fetcher_id=fetchers_LIVE_BALANCES_BOF_ID
    ).balances
    todays_spending_balance_coordinate = BalanceCoordinate(
        account_address=TODAYS_SPENDING,
        asset=DEFAULT_ASSET,
        denomination=default_denomination,
        phase=Phase.COMMITTED,
    )
    todays_spending = account_balances[todays_spending_balance_coordinate].net
    postings_balances = [posting.balances() for posting in posting_instructions]
    proposed_spend = sum(
        (
            utils_get_available_balance(balances=balances, denomination=default_denomination)
            for balances in postings_balances
        )
    )
    auto_top_up_status = vault.get_flag_timeseries(flag=AUTO_TOP_UP_FLAG).latest()
    additional_denominations = utils_get_parameter(
        vault, name=PARAM_ADDITIONAL_DENOMINATIONS, is_json=True
    )
    posting_denominations = set(
        (
            coord.denomination
            for posting in posting_instructions
            for coord in posting.balances().keys()
        )
    )
    allowed_denominations = additional_denominations + [default_denomination]
    unallowed_denominations = posting_denominations.difference(allowed_denominations)
    if unallowed_denominations:
        return PrePostingHookResult(
            rejection=Rejection(
                message="Postings received in unauthorised denominations",
                reason_code=RejectionReason.WRONG_DENOMINATION,
            )
        )
    if any(extract_bool_from_postings(posting_instructions, "withdrawal_override")):
        return None
    if proposed_spend < 0:
        if proposed_spend + todays_spending < -spending_limit and (
            not any(
                extract_value_from_postings(posting_instructions, "withdrawal_to_nominated_account")
            )
        ):
            return PrePostingHookResult(
                rejection=Rejection(
                    message="Transaction would exceed daily spending limit",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            )
    for denomination in posting_denominations:
        available_balance = utils_get_available_balance(
            balances=account_balances, denomination=denomination
        )
        proposed_delta = sum(
            (
                utils_get_available_balance(balances=balances, denomination=denomination)
                for balances in postings_balances
            )
        )
        if 0 > proposed_delta and 0 > proposed_delta + available_balance:
            if denomination == default_denomination and (not auto_top_up_status):
                return PrePostingHookResult(
                    rejection=Rejection(
                        message=f"Postings total {denomination} {proposed_delta}, which exceeds the available balance of {denomination} {available_balance} and auto top up is disabled",
                        reason_code=RejectionReason.INSUFFICIENT_FUNDS,
                    )
                )
            elif denomination != default_denomination:
                return PrePostingHookResult(
                    rejection=Rejection(
                        message=f"Postings total {denomination} {proposed_delta}, which exceeds the available balance of {denomination} {available_balance}",
                        reason_code=RejectionReason.INSUFFICIENT_FUNDS,
                    )
                )
    return None


@requires(event_type="ZERO_OUT_DAILY_SPEND", parameters=True)
@fetch_account_data(event_type="ZERO_OUT_DAILY_SPEND", balances=["EFFECTIVE_FETCHER"])
def scheduled_event_hook(
    vault: Any, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    pi_directives: list[PostingInstructionsDirective] = []
    if hook_arguments.event_type == ZERO_OUT_DAILY_SPEND_EVENT:
        pi_directives.extend(
            _get_zero_out_daily_spend_instructions(
                vault,
                effective_datetime=effective_datetime,
                balance_fetcher=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID,
            )
        )
    if pi_directives:
        return ScheduledEventHookResult(posting_instructions_directives=pi_directives)
    return None


# Objects below have been imported from:
#    fetchers.py
# md5:dcba39f23bd6808d7c243d6f0f8ff8d0

fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID = "EFFECTIVE_FETCHER"
fetchers_EFFECTIVE_OBSERVATION_FETCHER = BalancesObservationFetcher(
    fetcher_id=fetchers_EFFECTIVE_OBSERVATION_FETCHER_ID, at=DefinedDateTime.EFFECTIVE_DATETIME
)
fetchers_LIVE_BALANCES_BOF_ID = "live_balances_bof"
fetchers_LIVE_BALANCES_BOF = BalancesObservationFetcher(
    fetcher_id=fetchers_LIVE_BALANCES_BOF_ID, at=DefinedDateTime.LIVE
)

# Objects below have been imported from:
#    utils.py
# md5:b4718e1c735d11f6848158f777e7084f

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


def utils_str_to_bool(string: str) -> bool:
    """
    Convert a string true to bool True, default value of False.
    :param string:
    :return:
    """
    return str(string).lower() == "true"


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


# Objects below have been imported from:
#    wallet.py
# md5:c2f7282e542c68334dee406c4fc3ca65

DUPLICATION = "duplication"
TODAYS_SPENDING = "todays_spending"
LIMIT_SHAPE_MIN_VALUE = 0
LIMIT_SHAPE_MAX_VALUE = 2000
LIMIT_SHAPE_STEP_VALUE = Decimal("0.01")
LimitShape = NumberShape(
    min_value=LIMIT_SHAPE_MIN_VALUE, max_value=LIMIT_SHAPE_MAX_VALUE, step=LIMIT_SHAPE_STEP_VALUE
)
AUTO_TOP_UP_FLAG = "&{AUTO_TOP_UP_WALLET}"
PARAM_CUSTOMER_WALLET_LIMIT = "customer_wallet_limit"
PARAM_DENOMINATION = "denomination"
PARAM_ADDITIONAL_DENOMINATIONS = "additional_denominations"
PARAM_NOMINATED_ACCOUNT = "nominated_account"
PARAM_SPENDING_LIMIT = "daily_spending_limit"
ZERO_OUT_DAILY_SPEND_PREFIX = "zero_out_daily_spend"
PARAM_ZERO_OUT_DAILY_SPEND_HOUR = f"{ZERO_OUT_DAILY_SPEND_PREFIX}_hour"
PARAM_ZERO_OUT_DAILY_SPEND_MINUTE = f"{ZERO_OUT_DAILY_SPEND_PREFIX}_minute"
PARAM_ZERO_OUT_DAILY_SPEND_SECOND = f"{ZERO_OUT_DAILY_SPEND_PREFIX}_second"
parameters = [
    Parameter(
        name=PARAM_CUSTOMER_WALLET_LIMIT,
        level=ParameterLevel.INSTANCE,
        description="Maximum balance set by the customer.Validation against Bank Wallet Limit must happen outside Vault",
        display_name="Customer Wallet Limit",
        shape=LimitShape,
        default_value=Decimal("1000"),
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
    ),
    Parameter(
        name=PARAM_DENOMINATION,
        level=ParameterLevel.INSTANCE,
        description="Wallet denomination",
        display_name="Wallet Denomination",
        shape=DenominationShape(),
        default_value="SGD",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
    ),
    Parameter(
        name=PARAM_NOMINATED_ACCOUNT,
        level=ParameterLevel.INSTANCE,
        description="Nominated CASA account for top up",
        display_name="Nominated Account",
        shape=AccountIdShape(),
        default_value="0",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
    ),
    Parameter(
        name=PARAM_SPENDING_LIMIT,
        level=ParameterLevel.INSTANCE,
        description="Allowed daily spending amount. Resets at midnight",
        display_name="Spending Limit",
        shape=LimitShape,
        default_value=Decimal("999"),
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
    ),
    Parameter(
        name=PARAM_ADDITIONAL_DENOMINATIONS,
        shape=StringShape(),
        level=ParameterLevel.INSTANCE,
        description="Currencies that are accepted for this account, formatted as a json list of currency codes",
        display_name="Additional Denominations",
        default_value=dumps(["GBP", "USD"]),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name=PARAM_ZERO_OUT_DAILY_SPEND_HOUR,
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The hour of the day at which the spending is reset.",
        display_name="Spending Reset Hour",
        default_value=23,
    ),
    Parameter(
        name=PARAM_ZERO_OUT_DAILY_SPEND_MINUTE,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The minute of the hour at which the spending is reset.",
        display_name="Spending Reset Minute",
        default_value=59,
    ),
    Parameter(
        name=PARAM_ZERO_OUT_DAILY_SPEND_SECOND,
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=ParameterLevel.TEMPLATE,
        description="The second of the minute at which the spending is reset.",
        display_name="Spending Reset Second",
        default_value=59,
    ),
]
ZERO_OUT_DAILY_SPEND_EVENT = "ZERO_OUT_DAILY_SPEND"
ZERO_OUT_DAILY_SPEND_AST = "WALLET_ZERO_OUT_DAILY_SPEND_AST"
event_types = [
    SmartContractEventType(
        name=ZERO_OUT_DAILY_SPEND_EVENT, scheduler_tag_ids=[ZERO_OUT_DAILY_SPEND_AST]
    )
]
data_fetchers = [fetchers_LIVE_BALANCES_BOF, fetchers_EFFECTIVE_OBSERVATION_FETCHER]


def _get_zero_out_daily_spend_schedule(vault: Any) -> ScheduleExpression:
    """
    Sets up ScheduleExpression of ZERO_OUT_DAILY_SPEND schedule based on H/M/S parameters

    :param vault: SmartContractVault object
    :return: ScheduleExpression, representation of ZERO_OUT_DAILY_SPEND schedule
    """
    schedule_hour = str(utils_get_parameter(vault=vault, name=PARAM_ZERO_OUT_DAILY_SPEND_HOUR))
    schedule_minute = str(utils_get_parameter(vault=vault, name=PARAM_ZERO_OUT_DAILY_SPEND_MINUTE))
    schedule_second = str(utils_get_parameter(vault=vault, name=PARAM_ZERO_OUT_DAILY_SPEND_SECOND))
    return ScheduleExpression(hour=schedule_hour, minute=schedule_minute, second=schedule_second)


def _get_zero_out_daily_spend_instructions(
    vault: Any, balance_fetcher: str, effective_datetime: datetime
) -> list[PostingInstructionsDirective]:
    """
    Resets TODAYS_SPENDING back to zero.

    :param vault: SmartContractVault object
    :param effective_datetime: effective_datetime of the schedule runtime
    :return: list of PostingInstructionsDirective objects
    """
    denomination: str = utils_get_parameter(vault=vault, name=PARAM_DENOMINATION)
    todays_spending = (
        vault.get_balances_observation(fetcher_id=balance_fetcher)
        .balances[TODAYS_SPENDING, DEFAULT_ASSET, denomination, Phase.COMMITTED]
        .net
    )
    if todays_spending >= 0:
        return []
    posting_instructions = _update_tracked_spend(
        account_id=vault.account_id,
        amount=-todays_spending,
        denomination=denomination,
        zero_out_daily_spend=True,
    )
    return [
        PostingInstructionsDirective(
            posting_instructions=posting_instructions,
            client_batch_id=f"ZERO_OUT_DAILY_SPENDING-{vault.get_hook_execution_id()}",
            value_datetime=effective_datetime,
        )
    ]


def _get_release_and_decreased_auth_amount(
    postings: utils_PostingInstructionListAlias, denomination: str
) -> Decimal:
    """
    Calculate the impact to available balance due to releases and decreased auth amounts
    """
    total = Decimal(0)
    for posting in postings:
        delta = utils_get_available_balance(balances=posting.balances(), denomination=denomination)
        if (
            posting.type == PostingInstructionType.AUTHORISATION_ADJUSTMENT
            and delta > 0
            or posting.type == PostingInstructionType.RELEASE
        ):
            total += delta
    return total


def extract_bool_from_postings(
    postings: utils_PostingInstructionListAlias, instruction_details_key: str
) -> list[bool]:
    return [
        utils_str_to_bool(posting.instruction_details.get(instruction_details_key, "false"))
        for posting in postings
    ]


def extract_value_from_postings(
    postings: utils_PostingInstructionListAlias, instruction_details_key: str
) -> list[str]:
    return [posting.instruction_details.get(instruction_details_key, "") for posting in postings]


def _sweep_excess_funds(
    account_id: str, amount: Decimal, denomination: str, nominated_account: str
) -> list[CustomInstruction]:
    """
    Create postings to sweep excess funds to nominated account.
    Amount is expected to be positive.

    :param account_id: The id for wallet account
    :param amount: The delta amount to sweep to nominated account
    :param denomination: The denomination of this instruction
    :param nominated_account: The id of the account to sweep funds to
    """
    if amount <= 0:
        return []
    postings = [
        Posting(
            credit=True,
            amount=amount,
            denomination=denomination,
            account_id=nominated_account,
            account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=False,
            amount=amount,
            denomination=denomination,
            account_id=account_id,
            account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
    ]
    custom_instruction = CustomInstruction(
        postings=postings,
        instruction_details={"description": "RETURNING_EXCESS_BALANCE"},
        transaction_code=None,
        override_all_restrictions=True,
    )
    return [custom_instruction]


def _update_tracked_spend(
    account_id: str, amount: Decimal, denomination: str, zero_out_daily_spend: bool = False
) -> list[CustomInstruction]:
    """
    Create postings to update the spend tracking balance.

    :param account_id: The id for wallet account
    :param amount: The delta amount to update the balance by.
    Can be positive, negative or zero. A positive amount credits the TODAYS_SPENDING balance.
    :param denomination: The denomination of this instruction
    :param zero_out_daily_spend: Is this a zero out spend event
    """
    if amount == Decimal("0"):
        return []
    from_address = DUPLICATION if amount > 0 else TODAYS_SPENDING
    to_address = TODAYS_SPENDING if amount > 0 else DUPLICATION
    amount = abs(amount)
    postings = [
        Posting(
            credit=True,
            amount=amount,
            denomination=denomination,
            account_id=account_id,
            account_address=to_address,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=False,
            amount=amount,
            denomination=denomination,
            account_id=account_id,
            account_address=from_address,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
    ]
    custom_instruction = CustomInstruction(
        postings=postings,
        instruction_details={"event_type": "ZERO_OUT_DAILY_SPENDING"}
        if zero_out_daily_spend
        else {"description": "UPDATING_TRACKED_SPEND"},
        override_all_restrictions=True if zero_out_daily_spend else None,
    )
    return [custom_instruction]


def _top_up_balance(
    account_id: str, amount: Decimal, denomination: str, nominated_account: str
) -> list[CustomInstruction]:
    """
    Create postings to top up balance from nominated account.
    Amount is expected to be positive.

    :param account_id: The id for wallet account
    :param amount: The delta amount to sweep to nominated account
    :param denomination: The denomination of this instruction
    :param nominated_account: The id of the account to get funds from
    """
    if amount <= 0:
        return []
    postings = [
        Posting(
            credit=True,
            amount=amount,
            denomination=denomination,
            account_id=account_id,
            account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=False,
            amount=amount,
            denomination=denomination,
            account_id=nominated_account,
            account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
    ]
    custom_instruction = CustomInstruction(
        postings=postings,
        instruction_details={
            "description": f"Auto top up transferred from nominated account:{amount}"
        },
        override_all_restrictions=None,
    )
    return [custom_instruction]
