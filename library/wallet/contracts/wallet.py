# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
api = "3.9.0"
version = "2.5.3"
display_name = "Wallet Account"
tside = Tside.LIABILITY

MoneyShape = NumberShape(kind=NumberKind.MONEY, min_value=0, max_value=10000, step=0.01)

LimitShape = NumberShape(kind=NumberKind.MONEY, min_value=0, max_value=2000, step=0.01)

CUSTOMER_WALLET_LIMIT = "customer_wallet_limit"
DENOMINATION = "denomination"
ADDITIONAL_DENOMINATIONS = "additional_denominations"
NOMINATED_ACCOUNT = "nominated_account"
SPENDING_LIMIT = "daily_spending_limit"
DUPLICATION = "duplication"

# Balances
TODAYS_SPENDING = "todays_spending"
AUTO_TOP_UP_FLAG = "&{AUTO_TOP_UP_WALLET}"
DEFAULT_ASSET = "COMMERCIAL_BANK_MONEY"

# this can be amended to whichever other currencies as needed
supported_denominations = ["GBP", "SGD", "USD"]

event_types = [
    EventType(
        name="ZERO_OUT_DAILY_SPEND",
        scheduler_tag_ids=["WALLET_ZERO_OUT_DAILY_SPEND_AST"],
    )
]

parameters = [
    # Instance parameters
    Parameter(
        name=CUSTOMER_WALLET_LIMIT,
        level=Level.INSTANCE,
        description="Maximum balance set by the customer."
        "Validation against Bank Wallet Limit must happen outside Vault",
        display_name="Customer Wallet Limit",
        update_permission=UpdatePermission.USER_EDITABLE,
        shape=LimitShape,
        default_value=Decimal("1000"),
    ),
    Parameter(
        name=DENOMINATION,
        level=Level.INSTANCE,
        description="Wallet denomination",
        display_name="Wallet denomination",
        update_permission=UpdatePermission.USER_EDITABLE,
        shape=DenominationShape,
        default_value="SGD",
    ),
    Parameter(
        name=NOMINATED_ACCOUNT,
        level=Level.INSTANCE,
        description="Nominated CASA account for top up",
        display_name="Nominated Account",
        update_permission=UpdatePermission.USER_EDITABLE,
        shape=AccountIdShape,
        default_value="0",
    ),
    Parameter(
        name=SPENDING_LIMIT,
        level=Level.INSTANCE,
        description="Allowed daily spending amount. Resets at midnight",
        display_name="Spending Limit",
        update_permission=UpdatePermission.USER_EDITABLE,
        shape=LimitShape,
        default_value=Decimal("999"),
    ),
    Parameter(
        name="additional_denominations",
        shape=StringShape,
        level=Level.INSTANCE,
        description="Currencies that are accepted for this account, "
        "formatted as a json list of currency codes",
        display_name="Additional denominations",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=json_dumps(["GBP", "USD"]),
    ),
    # Template parameters
    Parameter(
        name="zero_out_daily_spend_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which the spending is reset.",
        display_name="Spending reset hour",
        default_value=23,
    ),
    Parameter(
        name="zero_out_daily_spend_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the hour at which the spending is reset.",
        display_name="Spending reset minute",
        default_value=59,
    ),
    Parameter(
        name="zero_out_daily_spend_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the minute at which the spending is reset.",
        display_name="Spending reset second",
        default_value=59,
    ),
]

contract_module_imports = [
    ContractModule(
        alias="utils",
        expected_interface=[
            SharedFunction(name="str_to_bool"),
            SharedFunction(name="get_parameter"),
        ],
    ),
]


@requires(modules=["utils"], parameters=True)
def execution_schedules():
    # Every day at time set by template parameters
    zero_out_daily_spend_schedule = _get_zero_out_daily_spend_schedule(vault)

    return [("ZERO_OUT_DAILY_SPEND", zero_out_daily_spend_schedule)]


@requires(
    modules=["utils"],
    event_type="ZERO_OUT_DAILY_SPEND",
    parameters=True,
    balances="latest live",
)
def scheduled_code(event_type: str, effective_date: datetime):
    if event_type == "ZERO_OUT_DAILY_SPEND":
        _zero_out_daily_spend(vault, effective_date)


@requires(modules=["utils"], parameters=True, balances="latest live", flags=True)
def pre_posting_code(postings: PostingInstructionBatch, effective_date: datetime):
    spending_limit = vault.modules["utils"].get_parameter(vault, name=SPENDING_LIMIT)
    default_denomination = vault.modules["utils"].get_parameter(vault, name=DENOMINATION)
    account_balances = vault.get_balance_timeseries().latest()
    todays_spending = account_balances[
        (TODAYS_SPENDING, DEFAULT_ASSET, default_denomination, Phase.COMMITTED)
    ].net
    proposed_spend = _available_balance(postings.balances(), default_denomination)
    auto_top_up_status = vault.get_flag_timeseries(flag=AUTO_TOP_UP_FLAG).latest()
    additional_denominations = vault.modules["utils"].get_parameter(
        vault, name=ADDITIONAL_DENOMINATIONS, is_json=True
    )

    posting_denominations = set([posting.denomination for posting in postings])
    unallowed_denominations = posting_denominations.difference(
        additional_denominations + [default_denomination]
    )

    if unallowed_denominations:
        raise Rejected(
            "Postings received in unauthorised denominations",
            reason_code=RejectedReason.WRONG_DENOMINATION,
        )

    if vault.modules["utils"].str_to_bool(
        postings.batch_details.get("withdrawal_override", "false")
    ):
        # Allow this posting by returning straight away
        return

    if proposed_spend < 0:
        if proposed_spend + todays_spending < -spending_limit and not postings.batch_details.get(
            "withdrawal_to_nominated_account"
        ):
            raise Rejected(
                "Transaction would exceed daily spending limit",
                RejectedReason.AGAINST_TNC,
            )

    # Check available balance across each denomination
    for denomination in posting_denominations:
        available_balance = _available_balance(account_balances, denomination)
        proposed_delta = _available_balance(postings.balances(), denomination)
        if 0 > proposed_delta and 0 > proposed_delta + available_balance:
            if denomination == default_denomination and not auto_top_up_status:
                raise Rejected(
                    f"Postings total {denomination} {proposed_delta},"
                    f" which exceeds the available balance of {denomination}"
                    f" {available_balance} and auto top up is disabled",
                    reason_code=RejectedReason.INSUFFICIENT_FUNDS,
                )
            elif denomination != default_denomination:
                raise Rejected(
                    f"Postings total {denomination} {proposed_delta},"
                    f" which exceeds the available"
                    f" balance of {denomination} {available_balance}",
                    reason_code=RejectedReason.INSUFFICIENT_FUNDS,
                )


@requires(modules=["utils"], parameters=True, balances="1 day", flags=True)
def post_posting_code(postings: PostingInstructionBatch, effective_date: datetime):
    """
    If the posting is a Spend, duplicates the spending to TODAYS_SPENDING to keep track
    of the remaining spending limit.
    If the posting is a refund or a release/decreased auth,
    the previously duplicated amount is unduplicated
    If the posting is a Deposit, checks if we have reached our limit then posts the
    remainder to the nominated account if we breach it.
    """
    default_denomination = vault.modules["utils"].get_parameter(vault, name=DENOMINATION)
    postings_delta = _available_balance(postings.balances(), default_denomination)

    auto_top_up_status = vault.get_flag_timeseries(flag=AUTO_TOP_UP_FLAG).latest()
    nominated_account = vault.modules["utils"].get_parameter(vault, name=NOMINATED_ACCOUNT)

    previous_balance = _available_balance(
        vault.get_balance_timeseries().before(timestamp=effective_date),
        default_denomination,
    )
    current_balance = previous_balance + postings_delta

    release_and_decreased_auth_amount = _get_release_and_decreased_auth_amount(
        postings, default_denomination
    )

    posting_ins = []
    if current_balance < 0 and auto_top_up_status:
        amount_required_from_nominated = abs(current_balance)
        posting_ins += vault.make_internal_transfer_instructions(
            amount=amount_required_from_nominated,
            denomination=default_denomination,
            client_transaction_id=f"{vault.get_hook_execution_id()}_AUTO_TOP_UP",
            from_account_id=nominated_account,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=vault.account_id,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            instruction_details={
                "description": f"Auto top up transfered from nominated account:"
                f"{amount_required_from_nominated}"
            },
        )

    if (
        postings_delta < 0
        and not vault.modules["utils"].str_to_bool(
            postings.batch_details.get("withdrawal_override", "false")
        )
    ) or (postings_delta > 0 and postings.batch_details.get("refund")):
        posting_ins += _update_tracked_spend(vault, postings_delta, default_denomination)
    # auths/releases aren't refunds but we still need to
    # decrease the tracked spend accordingly
    elif postings_delta > 0 and release_and_decreased_auth_amount > 0:
        posting_ins += _update_tracked_spend(
            vault, release_and_decreased_auth_amount, default_denomination
        )

    if postings_delta > 0:
        wallet_limit = vault.modules["utils"].get_parameter(vault, name=CUSTOMER_WALLET_LIMIT)

        if current_balance > wallet_limit:
            nominated_account = vault.modules["utils"].get_parameter(vault, name=NOMINATED_ACCOUNT)
            difference = wallet_limit - current_balance
            posting_ins += vault.make_internal_transfer_instructions(
                amount=abs(difference),
                denomination=default_denomination,
                client_transaction_id=f"RETURNING_EXCESS_BALANCE_"
                f"{vault.get_hook_execution_id()}",
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=nominated_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
            )

    if posting_ins:
        vault.instruct_posting_batch(
            posting_instructions=posting_ins, effective_date=effective_date
        )


@requires(modules=["utils"], parameters=True, balances="latest live")
def post_parameter_change_code(
    old_parameter_values: Dict[str, Parameter],
    updated_parameter_values: Dict[str, Parameter],
    effective_date: datetime,
):
    """
    Checks if the customer or bank wallet limit has been lowered and sweep
    to the nominated account if so.
    """

    old_limit = old_parameter_values.get(CUSTOMER_WALLET_LIMIT, 0)
    # updated_parameter_values only contains changed parameters
    new_limit = updated_parameter_values.get(CUSTOMER_WALLET_LIMIT, old_limit)

    if old_limit > new_limit:
        denomination = vault.modules["utils"].get_parameter(vault, name=DENOMINATION)
        nominated_account = vault.modules["utils"].get_parameter(vault, name=NOMINATED_ACCOUNT)
        current_balance = _available_balance(vault.get_balance_timeseries().latest(), denomination)
        if current_balance > new_limit:
            delta = current_balance - new_limit

            posting_ins = vault.make_internal_transfer_instructions(
                amount=delta,
                denomination=denomination,
                client_transaction_id=f"SWEEP_EXCESS_FUNDS_" f"{vault.get_hook_execution_id()}",
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=nominated_account,
                to_account_address=DEFAULT_ADDRESS,
                instruction_details={"description": "Sweeping excess funds after limit change"},
                asset=DEFAULT_ASSET,
            )

            vault.instruct_posting_batch(
                client_batch_id="POST_PARAMETER_CHANGE-" + vault.get_hook_execution_id(),
                posting_instructions=posting_ins,
                effective_date=effective_date,
            )


@requires(modules=["utils"], parameters=True, balances="latest live")
def close_code(effective_date: datetime):
    _zero_out_daily_spend(vault, effective_date)


def _available_balance(balances: BalanceDefaultDict, denomination: str) -> Decimal:
    """
    Calculates the available balance, which excludes
    incoming and outgoing ringfenced funds, for a
    given set of balances. If used on a PIB's balances, this provides the
    delta to the available balance that the PIB results in.
    """

    # PENDING_OUT balance is negative for outbound auths,
    # so addition subtracts the amount from the
    # COMMITTED balance
    return (
        balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
        + balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)].net
    )


def _get_release_and_decreased_auth_amount(
    postings: PostingInstructionBatch, denomination: str
) -> Decimal:
    """
    Calculate the impact to available balance due to releases and decreased auth amounts
    """
    total = Decimal(0)

    for posting in postings:
        delta = _available_balance(posting.balances(), denomination)
        if (
            posting.type == PostingInstructionType.AUTHORISATION_ADJUSTMENT and delta > 0
        ) or posting.type == PostingInstructionType.RELEASE:
            total += delta

    return total


def _update_tracked_spend(vault, amount: Decimal, denomination: str) -> List[PostingInstruction]:
    """
    Create postings to update the spend tracking balance
    :param amount: the delta amount to update the balance by.
    Can be positive, negative or zero.
    A positive amount credits the TODAYS_SPENDING balance
    """
    if amount == 0:
        return []

    if amount > 0:
        from_address = DUPLICATION
        to_address = TODAYS_SPENDING
    else:
        to_address = DUPLICATION
        from_address = TODAYS_SPENDING

    return vault.make_internal_transfer_instructions(
        amount=abs(amount),
        denomination=denomination,
        client_transaction_id=f"UPDATING_TRACKED_SPEND-{vault.get_hook_execution_id()}",
        from_account_id=vault.account_id,
        from_account_address=from_address,
        to_account_id=vault.account_id,
        to_account_address=to_address,
        asset=DEFAULT_ASSET,
    )


def _zero_out_daily_spend(vault, effective_date: datetime):
    """
    Resets TODAYS_SPENDING back to zero.
    """
    denomination = vault.modules["utils"].get_parameter(vault, name=DENOMINATION)
    todays_spending = (
        vault.get_balance_timeseries()
        .latest()[(TODAYS_SPENDING, DEFAULT_ASSET, denomination, Phase.COMMITTED)]
        .net
    )

    if todays_spending < 0:
        posting_ins = _update_tracked_spend(vault, -todays_spending, denomination)
        vault.instruct_posting_batch(
            client_batch_id="ZERO_OUT_DAILY_SPENDING-" + vault.get_hook_execution_id(),
            posting_instructions=posting_ins,
            effective_date=effective_date,
            batch_details={"event_type": "ZERO_OUT_DAILY_SPENDING"},
        )


# Helper functions for creating event schedules
def _get_zero_out_daily_spend_schedule(vault):
    """
    Sets up dictionary of ZERO_OUT_DAILY_SPEND schedule based on parameters

    :param vault: Vault object
    :return: dict, representation of ZERO_OUT_DAILY_SPEND schedule
    """
    zero_out_daily_spend_hour = vault.modules["utils"].get_parameter(
        vault, name="zero_out_daily_spend_hour"
    )
    zero_out_daily_spend_minute = vault.modules["utils"].get_parameter(
        vault, name="zero_out_daily_spend_minute"
    )
    zero_out_daily_spend_second = vault.modules["utils"].get_parameter(
        vault, name="zero_out_daily_spend_second"
    )

    zero_out_daily_spend_schedule = _create_schedule_dict_from_params(
        hour=zero_out_daily_spend_hour,
        minute=zero_out_daily_spend_minute,
        second=zero_out_daily_spend_second,
    )

    return zero_out_daily_spend_schedule


def _create_schedule_dict_from_params(
    year=None, month=None, day=None, hour=None, minute=None, second=None
):
    """
    Creates a dict representing a schedule from datetime parameters as function input

    :param year: int, year for schedule to run
    :param month: int, month for schedule to run
    :param day: int, day of month for schedule to run
    :param hour: int, hour of day for schedule to run
    :param minute: int, minute of hour for schedule to run
    :param second: int, second of minute for schedule to run
    :return: dict, representation of schedule from function input
    """
    schedule_dict = {}
    if year is not None:
        schedule_dict["year"] = str(year)
    if month is not None:
        schedule_dict["month"] = str(month)
    if day is not None:
        schedule_dict["day"] = str(day)
    if hour is not None:
        schedule_dict["hour"] = str(hour)
    if minute is not None:
        schedule_dict["minute"] = str(minute)
    if second is not None:
        schedule_dict["second"] = str(second)
    return schedule_dict
