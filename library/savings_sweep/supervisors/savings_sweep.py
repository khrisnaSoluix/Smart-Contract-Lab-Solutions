# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
api = "3.9.0"
version = "1.2.1"

DEFAULT_TRANSACTION_TYPE = "PURCHASE"
DEFAULT_DENOMINATION = "USD"
INTERNAL_POSTING = "INTERNAL_POSTING"
EXTERNAL_POSTING = "EXTERNAL_POSTING"
TIER_PARAM_NAME = {
    "us_checking": "tier_names",
    "us_savings": "account_tier_names",
}

supervised_smart_contracts = [
    SmartContractDescriptor(
        alias="us_checking",
        smart_contract_version_id="&{us_checking_account}",
        supervise_post_posting_hook=True,
    ),
    SmartContractDescriptor(
        alias="us_savings",
        smart_contract_version_id="&{us_savings_account}",
        supervise_post_posting_hook=False,
    ),
]

event_types = [
    EventType(
        name="SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES",
        overrides_event_types=[("us_checking", "APPLY_MONTHLY_FEES")],
        scheduler_tag_ids=["SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES_AST"],
    ),
    EventType(
        name="SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES",
        overrides_event_types=[("us_savings", "APPLY_MONTHLY_FEES")],
        scheduler_tag_ids=["SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES_AST"],
    ),
]


@requires(data_scope="all", parameters=True)
def execution_schedules():
    plan_creation_date = vault.get_plan_creation_date()
    # Currently
    # 1. supervisors do not have their own params (https://pennyworth.atlassian.net/browse/TM-13659)
    # 2. there is not a lifecycle hook for when an account is added to plan
    # as a result, once a supervisor plan has been created, it runs this schedule
    # event every hour until it sees a supervisee on plan;
    # from that point on, it will reschedule the event with the correct timing from
    # params of the supervisee;
    # adding 6 seconds before starting such hourly blind runs to give some leeway
    # for a typical account to be added to plan
    first_schedule_date = plan_creation_date + timedelta(seconds=6)
    first_schedule = _create_schedule_dict_from_datetime(first_schedule_date)
    return [
        ("SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES", first_schedule),
        ("SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES", first_schedule),
    ]


@requires(
    event_type="SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES",
    data_scope="all",
    supervisee_hook_directives="all",
    parameters=True,
    balances="31 days",
    last_execution_time=["APPLY_MONTHLY_FEES"],
)
@requires(
    event_type="SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES",
    data_scope="all",
    supervisee_hook_directives="all",
    parameters=True,
    balances="31 days",
    last_execution_time=["APPLY_MONTHLY_FEES"],
)
def scheduled_code(event_type, effective_date):
    if event_type == "SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES":
        account_type = "us_checking"
        accounts = _get_supervisees_for_alias(vault, account_type)
        _apply_checking_or_savings_monthly_fees(vault, effective_date, account_type, accounts)
        _schedule_monthly_fees_events(vault, effective_date, event_type, accounts)

    elif event_type == "SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES":
        account_type = "us_savings"
        accounts = _get_supervisees_for_alias(vault, account_type)
        _apply_checking_or_savings_monthly_fees(vault, effective_date, account_type, accounts)
        _schedule_monthly_fees_events(vault, effective_date, event_type, accounts)


@requires(
    parameters=True,
    balances="1 day",
    postings="1 days",
    last_execution_time=["APPLY_MONTHLY_FEES"],
    data_scope="all",
    supervisee_hook_directives="invoked",
)
def post_posting_code(postings, effective_date: datetime):

    on_plan_savings_accounts = _get_supervisees_for_alias(vault, "us_savings")

    # this is to work around a platform bug TM-41683
    # where supervisor does not filter Transfer posting types correctly
    # such that both debtor and creditor parts of the posting are included
    # regardless of them being on plan or not
    postings = _filter_non_supervisee_postings(vault, postings)

    checking_accounts = {vault.supervisees.get(posting.account_id) for posting in postings}

    if len(checking_accounts) > 1:
        raise Rejected(
            "Multiple checking accounts in post posting not supported.",
            reason_code=RejectedReason.AGAINST_TNC,
        )

    # current implementation does not support multiple checkings accounts in a single batch
    # in post posting. That may be implemented in future iterations
    checking_account = checking_accounts.pop()

    directives = checking_account.get_hook_directives()

    main_denomination = _get_parameter(name="denomination", vault=checking_account)

    autosave_amount = 0
    posting_instructions = []
    standard_overdraft_instructions = []
    if directives:
        for posting_directive in directives.posting_instruction_batch_directives:
            pib = posting_directive.posting_instruction_batch
            for posting in pib:
                if posting.instruction_details.get("event") == "AUTOSAVE":
                    autosave_amount = posting.amount
                if posting.instruction_details.get("event") != "STANDARD_OVERDRAFT":
                    posting_instructions.append(posting)
                else:
                    standard_overdraft_instructions.append(posting)

    offset_amount, savings_sweep_instructions = _handle_savings_sweep(
        checking_account,
        postings,
        main_denomination,
        effective_date,
        on_plan_savings_accounts,
    )

    posting_instructions.extend(savings_sweep_instructions)

    offset_amount -= autosave_amount

    if standard_overdraft_instructions:
        posting_instructions.extend(
            _charge_overdraft_per_transaction_fee(
                checking_account,
                postings,
                offset_amount,
                main_denomination,
                effective_date,
                standard_overdraft_instructions,
            )
        )

    _instruct_posting_batch(checking_account, posting_instructions, effective_date, "POST_POSTING")


def _apply_checking_or_savings_monthly_fees(
    vault, effective_date: datetime, account_type: str, accounts: Optional[List] = None
):
    """
    Supervisor Apply Monthly Fees for either Checking or Savings
    If no account is linked, return and keep running this event every hour

    :param vault: Vault object
    :param effective_date: date and time of hook being run
    :param account_type: us_checking or us_savings
    :param accounts: list of vault objects for the relevant supervisee accounts
    """
    if not accounts:
        return

    all_accounts = (v for v in vault.supervisees.values())

    monthly_mean_combined_balance = _monthly_mean_balance(
        DEFAULT_DENOMINATION, effective_date, all_accounts
    )

    for account in accounts:

        # Make sure that for any account this is only run at the appropriate scheduled time
        creation_date = account.get_account_creation_date()
        first_schedule_date = _get_next_fee_datetime(account, creation_date)
        last_execution_time = account.get_last_execution_time(event_type="APPLY_MONTHLY_FEES")
        is_less_than_one_month_since_creation = (
            last_execution_time is None and effective_date < first_schedule_date
        )
        is_less_than_one_month_since_last_event_run = (
            last_execution_time is not None
            and last_execution_time < effective_date
            and effective_date < _get_next_fee_datetime(account, last_execution_time)
        )
        if is_less_than_one_month_since_creation or is_less_than_one_month_since_last_event_run:
            continue

        # Need to ensure fees not waivered are still applied.
        # This can be done by reinstructing the supervisee pib hook directives
        hook_directives = account.get_hook_directives()
        if not hook_directives:
            continue
        pib_directives = hook_directives.posting_instruction_batch_directives

        for directive in pib_directives:
            pib = directive.posting_instruction_batch
            posting_instructions = _get_applicable_postings(
                vault=account,
                pib=pib,
                account_type=account_type,
                monthly_mean_combined_balance=monthly_mean_combined_balance,
            )
            if posting_instructions:
                account.instruct_posting_batch(
                    posting_instructions=posting_instructions,
                    effective_date=effective_date,
                )


def _get_available_balance(balances, denomination, address=DEFAULT_ADDRESS, asset=DEFAULT_ASSET):
    """
    Sum net balances including COMMITTED and PENDING_OUT only.

    :param balances: Balance timeseries
    :param denomination: string
    :param address: string, balance address
    :param asset: string, balance asset
    :return: Decimal
    """
    return (
        balances[(address, asset, denomination, Phase.COMMITTED)].net
        + balances[(address, asset, denomination, Phase.PENDING_OUT)].net
    )


def _get_committed_default_balance_from_postings(postings, denomination):
    """
    Get the committed balance from postings instead of balances

    TODO this helper usage should later be replaced by postings balance when this becomes available
    for supervisor post_posting

    :param postings: [List[PostingInstruction]]
    :param denomination: string
    :return: Decimal
    """
    return sum(
        posting.amount if posting.credit else -posting.amount
        for posting in postings
        if (posting.denomination == denomination and _is_settled_against_default_address(posting))
    )


def _get_supervisees_for_alias(vault, alias):
    """
    Returns a list of supervisee vault objects for the given alias, ordered by account creation date
    :param vault: vault, supervisor vault object
    :param alias: str, the supervisee alias to filter for
    :return: list, supervisee vault objects for given alias, ordered by account creation date
    """
    return sorted(
        (
            supervisee
            for supervisee in vault.supervisees.values()
            if supervisee.get_alias() == alias
        ),
        key=lambda v: v.get_account_creation_date(),
    )


def _get_parameter(vault, name, at=None, is_json=False, optional=False, default_value=None):
    """
    Get the parameter value for a given parameter
    :param vault:
    :param name: string, name of the parameter to retrieve
    :param at: Optional datetime, time at which to retrieve the parameter value. If not
    specified the latest value is retrieved
    :param is_json: Optional boolean, if true json_loads is called on the retrieved parameter value
    :param optional: Optional boolean, if true we treat the parameter as optional
    :param default_value: Optional, if the optional function parameter is True, and the optional
    parameter is not set, this value is returned
    :return:
    """

    if at:
        parameter = vault.get_parameter_timeseries(name=name).at(timestamp=at)
    else:
        parameter = vault.get_parameter_timeseries(name=name).latest()

    if optional:
        parameter = parameter.value if parameter.is_set() else default_value

    if is_json and parameter is not None:
        parameter = json_loads(parameter)

    return parameter


def _get_ordered_savings_sweep_savings_accounts(checking_account, on_plan_savings_accounts):
    savings_sweep_hierarchy = _get_parameter(
        checking_account,
        "savings_sweep_account_hierarchy",
        is_json=True,
        optional=True,
    )
    if savings_sweep_hierarchy is not None:
        return [
            savings_account
            for account_id in savings_sweep_hierarchy
            for savings_account in on_plan_savings_accounts
            if savings_account.account_id == account_id
        ]
    else:
        return on_plan_savings_accounts


def _get_available_savings_sweep_balances(
    checking_account, on_plan_savings_accounts, effective_date, denomination
):
    """
    This method leverages the guaranteed insertion order in dictionaries
    entries since CPython 3.7 onwards, so that a dict of
    savings account and their corresponding balances are returned in the
    order of hierarchy specified in the checking account.

    :param checking_account: vault object of checking account
    :param on_plan_savings_accounts:  list of vault objects of savings account
    :param effective_date: date the postings are being processed on
    :param denomination: account denomination
    :return: Dictionary of savings_account_id to available balance
    """
    return {
        savings_account.account_id: _get_available_balance(
            savings_account.get_balance_timeseries().at(timestamp=effective_date),
            denomination,
        )
        for savings_account in _get_ordered_savings_sweep_savings_accounts(
            checking_account, on_plan_savings_accounts
        )
    }


def _handle_savings_sweep(
    checking_account,
    postings: List[PostingInstruction],
    denomination: str,
    effective_date: datetime,
    on_plan_savings_accounts,
) -> Tuple[Decimal, List[PostingInstruction]]:
    overdraft_fee_income_account = _get_parameter(
        vault=checking_account, name="overdraft_fee_income_account"
    )
    has_settled_withdrawal = any(
        (not post.credit and _is_settled_against_default_address(post)) for post in postings
    )

    total_savings_sweep_transfer_amount = 0
    posting_instructions = []

    if len(on_plan_savings_accounts) > 0 and has_settled_withdrawal:

        balances = checking_account.get_balance_timeseries().before(timestamp=effective_date)
        balance_before = balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
        proposed_amount = _get_committed_default_balance_from_postings(postings, denomination)

        latest_checking_account_balance = balance_before + proposed_amount

        if latest_checking_account_balance < 0:

            applicable_savings_sweep_fee_amount = _get_applicable_savings_sweep_fee(
                checking_account, effective_date
            )

            savings_available_balances = _get_available_savings_sweep_balances(
                checking_account, on_plan_savings_accounts, effective_date, denomination
            )

            # only attempts savings sweep if total available balances in
            # savings accounts is above savings sweep transaction fee
            if sum(savings_available_balances.values()) > applicable_savings_sweep_fee_amount:

                latest_checking_account_balance -= applicable_savings_sweep_fee_amount

                for (
                    savings_account_id,
                    savings_available_balance,
                ) in savings_available_balances.items():

                    savings_available_balance = max(Decimal("0"), savings_available_balance)
                    savings_sweep_transfer_amount = (
                        _get_savings_sweep_transfer_amount_with_transfer_unit(
                            checking_account=checking_account,
                            savings_available_balance=savings_available_balance,
                            maximum_amount_required=abs(latest_checking_account_balance),
                        )
                    )

                    total_savings_sweep_transfer_amount += savings_sweep_transfer_amount

                    if savings_sweep_transfer_amount > Decimal("0"):

                        posting_instructions.extend(
                            checking_account.make_internal_transfer_instructions(
                                amount=savings_sweep_transfer_amount,
                                denomination=denomination,
                                client_transaction_id=f"{INTERNAL_POSTING}_SAVINGS_"
                                f"SWEEP_WITHDRAWAL_FROM_"
                                f"{savings_account_id}_"
                                f"{checking_account.get_hook_execution_id()}",
                                from_account_id=savings_account_id,
                                from_account_address=DEFAULT_ADDRESS,
                                to_account_id=checking_account.account_id,
                                to_account_address=DEFAULT_ADDRESS,
                                asset=DEFAULT_ASSET,
                                pics=[],
                                override_all_restrictions=True,
                                instruction_details={
                                    "description": "Savings Sweep from savings account",
                                    "event": "SAVINGS_SWEEP",
                                },
                            )
                        )

                        latest_checking_account_balance += savings_sweep_transfer_amount

                        if latest_checking_account_balance >= Decimal("0"):
                            break

                if applicable_savings_sweep_fee_amount > Decimal("0"):
                    posting_instructions.extend(
                        checking_account.make_internal_transfer_instructions(
                            amount=applicable_savings_sweep_fee_amount,
                            denomination=denomination,
                            client_transaction_id=f"{INTERNAL_POSTING}_SAVINGS_SWEEP_FEE"
                            f"_{checking_account.get_hook_execution_id()}",
                            from_account_id=checking_account.account_id,
                            from_account_address=DEFAULT_ADDRESS,
                            to_account_id=overdraft_fee_income_account,
                            to_account_address=DEFAULT_ADDRESS,
                            asset=DEFAULT_ASSET,
                            pics=[],
                            override_all_restrictions=True,
                            instruction_details={
                                "description": "Savings Sweep fee per transfer",
                                "event": "SAVINGS_SWEEP_FEE",
                            },
                        )
                    )

    return total_savings_sweep_transfer_amount, posting_instructions


def _charge_overdraft_per_transaction_fee(
    vault,
    postings: List[PostingInstruction],
    offset_amount: Decimal,
    denomination: str,
    effective_date: datetime,
    standard_overdraft_instructions: List[PostingInstruction],
) -> List[PostingInstruction]:

    balances = vault.get_balance_timeseries().before(timestamp=effective_date)
    fee_free_overdraft_limit = _get_parameter(vault, name="fee_free_overdraft_limit")

    balance_before = balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
    proposed_amount = _get_committed_default_balance_from_postings(postings, denomination)
    latest_balance = balance_before + proposed_amount
    effective_balance = latest_balance + offset_amount

    posting_instructions = []
    counter = 0
    for posting in sorted(postings, key=lambda posting: posting.amount):
        if effective_balance < -fee_free_overdraft_limit:
            counter += 1
        # TODO posting.credit should later be replaced by checking on posting.balance()
        # when it becomes available for supervisor post_posting
        effective_balance += -posting.amount if posting.credit else posting.amount

    # a list of STANDARD_OVERDRAFT posting instructions was created in supervisee.
    # in the supervisor, when funds are transferred into checking account
    # from the savings, it would no longer be in overdraft.
    # based on the counter above (the expected number of
    # STANDARD_OVERDRAFT posting instructions from all posting),
    # add only that number of STANDARD_OVERDRAFT posting instructions from
    # supervisee to the final list of posting instructions.
    for instruction in standard_overdraft_instructions:
        client_transaction_id = instruction.client_transaction_id.split("_")
        if int(client_transaction_id[-1]) < counter:
            posting_instructions.append(instruction)

    return posting_instructions


def _is_settled_against_default_address(posting):
    return posting.type in (
        PostingInstructionType.HARD_SETTLEMENT,
        PostingInstructionType.SETTLEMENT,
        PostingInstructionType.TRANSFER,
    ) or (
        posting.type == PostingInstructionType.CUSTOM_INSTRUCTION
        and posting.phase == Phase.COMMITTED
        and posting.asset == DEFAULT_ASSET
        and posting.account_address == DEFAULT_ADDRESS
    )


def _instruct_posting_batch(
    vault,
    posting_instructions: List[PostingInstruction],
    effective_date: datetime,
    event_type: str,
) -> None:
    """
    Instructs posting batch if posting_instructions variable contains any posting instructions.

    :param vault: Vault object
    :param posting_instructions: posting instructions
    :param effective_date: date and time of hook being run
    :param event_type: type of event triggered by the hook
    """
    if posting_instructions:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions,
            effective_date=effective_date,
            client_batch_id=f"{event_type}_{vault.get_hook_execution_id()}",
        )


def _get_applicable_savings_sweep_fee(checking_account, effective_date):
    """
    Determine how much savings sweep fee to be charged for a given transaction
    returns 0 if no fee should apply
    :param checking_account: Vault object for the supervisee checking account
    :param effective_date: datetime
    :return: Decimal, the amout of savings sweep fee that should be charged
    """
    savings_sweep_fee = _get_parameter(checking_account, "savings_sweep_fee")
    savings_sweep_fee_cap = _get_parameter(checking_account, "savings_sweep_fee_cap")
    return (
        savings_sweep_fee
        if (
            savings_sweep_fee > Decimal("0")
            and (
                savings_sweep_fee_cap < Decimal("0")
                or _count_savings_sweep_used(checking_account, effective_date) + 1
                <= savings_sweep_fee_cap
            )
        )
        else Decimal("0")
    )


def _count_savings_sweep_used(vault, effective_date):
    """
    Get a count of how many times savings sweep has been used in current day.
    :param vault: creation_date, postings
    :param effective_date: datetime
    :return: int
    """
    start_of_period = _get_start_of_daily_window(vault, effective_date)
    return sum(1 for e in _get_previous_transactions(vault, start_of_period, "SAVINGS_SWEEP_FEE"))


def _get_previous_transactions(vault, start_of_period, posting_instruction_event):
    """
    Returns a Generator for debit postings newer than start of period and have matching
    instruction details event
    :param vault: get_postings()
    :param start_of_period: datetime
    :param posting_instruction_event: str
    :return: Generator of in scope postings that can be iterated through
    """
    recent_postings = vault.get_postings(include_proposed=False)
    return (
        posting.amount
        for posting in recent_postings
        if (
            posting.value_timestamp > start_of_period
            and posting.instruction_details.get("event") == posting_instruction_event
            and posting.credit is False
        )
    )


def _create_schedule_dict_from_datetime(schedule_datetime):
    """
    Creates a dict representing a schedule from datetime as function input

    :param schedule_datetime: datetime, object to be formatted
    :return: dict, schedule representation of datetime
    """
    schedule_dict = {
        "year": str(schedule_datetime.year),
        "month": str(schedule_datetime.month),
        "day": str(schedule_datetime.day),
        "hour": str(schedule_datetime.hour),
        "minute": str(schedule_datetime.minute),
        "second": str(schedule_datetime.second),
    }
    return schedule_dict


def _create_event_type_schedule_from_datetime(schedule_datetime):
    """
    Creates an EventTypeSchedule from datetime as function input

    :param schedule_datetime: datetime, object to be formatted
    :return: dict, schedule representation of datetime
    """
    return EventTypeSchedule(
        day=str(schedule_datetime.day),
        hour=str(schedule_datetime.hour),
        minute=str(schedule_datetime.minute),
        second=str(schedule_datetime.second),
        month=str(schedule_datetime.month),
        year=str(schedule_datetime.year),
    )


def _get_next_fee_datetime(vault, effective_date):
    """
    Sets up dictionary for next run time of event, taking the day and hh:mm:ss
    from contract parameters. Should only be used for a supervised account

    :param vault: Vault object
    :param effective_date: datetime, date from which to calculate next event datetime
    :return: datetime
    """
    fees_application_day = _get_parameter(vault, "fees_application_day")
    fees_application_hour = _get_parameter(vault, "fees_application_hour")
    fees_application_minute = _get_parameter(vault, "fees_application_minute")
    fees_application_second = _get_parameter(vault, "fees_application_second")
    creation_date = vault.get_account_creation_date()

    next_schedule_timedelta = timedelta(
        day=fees_application_day,
        hour=fees_application_hour,
        minute=fees_application_minute,
        second=fees_application_second,
        microsecond=0,
    )

    next_schedule_date = effective_date + next_schedule_timedelta

    in_the_past = next_schedule_date <= effective_date
    if in_the_past:
        next_schedule_date += timedelta(months=1, day=fees_application_day)

    before_first_schedule_date = next_schedule_date < creation_date + timedelta(months=1)
    if before_first_schedule_date:
        next_schedule_date += timedelta(months=1, day=fees_application_day)

    return next_schedule_date


def _get_applicable_postings(vault, pib, account_type, monthly_mean_combined_balance):
    """
    Checks which postings should be filtered out based on waiver
    criteria, applies supervisor instruction details.
    :param vault: supervisee Vault object
    :param pib: posting instruction batch retrieved from supervisee directive
    :param account_type: string, us_checking or us_savings
    :param monthly_mean_combined_balance: Decimal

    :return: List[PostingInstruction], the posting instructions if not waivered
    """
    tier_param = TIER_PARAM_NAME[account_type]
    tier_names = _get_parameter(vault=vault, name=tier_param, is_json=True)
    this_account_flags = _get_active_account_flags(vault=vault, interesting_flag_list=tier_names)
    minimum_combined_balance_tiers = _get_parameter(
        vault=vault, name="minimum_combined_balance_threshold", is_json=True
    )
    minimum_combined_balance = _get_dict_value_based_on_account_tier_flag(
        account_tier_flags=this_account_flags,
        tiered_param=minimum_combined_balance_tiers,
        tier_names=tier_names,
        convert=Decimal,
    )

    posting_instructions = []
    for post in pib:
        should_be_applied = (
            monthly_mean_combined_balance < minimum_combined_balance
            or not _is_maintenance_fee_posting(post, account_type)
        )
        if should_be_applied:
            # needs to reassign the grouping key due to bug in contract language
            # where custom instruction grouping keys are wrongly assigned on the batch
            # level. This logic assumes that each custom instruction pair will have
            # a unique client transaction id
            post.custom_instruction_grouping_key = post.client_transaction_id
            post.client_transaction_id += "_SUPERVISOR"
            post.instruction_details["supervisor"] = "Applied by supervisor"
            posting_instructions.append(post)

    return posting_instructions


def _schedule_monthly_fees_events(
    vault, effective_date: datetime, event_type: str, accounts: Optional[List] = None
):
    """
    Set the next schedule date for the supervisor event and its supervisees.
    Setting supervisor to same time as oldest supervisee event.
    This works since we are using template params so all product account schedules will be the same.
    A different approach would be needed if a bank used the creation date for schedule times.

    :param vault: Vault object
    :param effective_date: date and time of hook being run
    :param event_type: schedule event type, e.g. SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES
    :param accounts: list of vault objects for the relevant supervisee accounts
    """
    accounts = accounts or []
    # If there is no supervisee account run again every hour
    if not accounts:
        vault.update_event_type(
            event_type=event_type,
            schedule=_create_event_type_schedule_from_datetime(effective_date + timedelta(hours=1)),
        )
    else:
        # Set the schedule time for the supervisor event
        next_schedule_date = _get_next_fee_datetime(accounts[0], effective_date)
        vault.update_event_type(
            event_type=event_type,
            schedule=_create_event_type_schedule_from_datetime(next_schedule_date),
        )

        # Set the schedule time for the supervisee accounts
        for account in accounts:
            next_schedule_date = _get_next_fee_datetime(account, effective_date)
            account.update_event_type(
                event_type="APPLY_MONTHLY_FEES",
                schedule=_create_event_type_schedule_from_datetime(next_schedule_date),
            )


def _monthly_mean_balance(denomination, effective_date, all_accounts):
    """
    Determine the average combined balance for the preceding month. The sampling period is from one
    month before, until the effective_date, exclusive i.e. not including the effective_date day

    :param denomination: Account denomination
    :param effective_date: datetime, date and time of hook being run
    :param all_accounts: List[Vault objects], list of all accounts for combined balance
    :return: Decimal, mean combined balance at sampling time for previous month
    """
    period_start = effective_date - timedelta(months=1)

    # if num_days is lower than 1 for whatever reason, use 1 instead
    num_days = max((effective_date - period_start).days, 1)

    total = sum(
        sum(
            account.get_balance_timeseries()
            .at(timestamp=period_start + timedelta(days=i))[
                (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
            ]
            .net
            for i in range(num_days)
            if (account.get_account_creation_date() <= period_start + timedelta(days=i))
        )
        for account in all_accounts
    )

    return total / num_days


def _get_active_account_flags(vault, interesting_flag_list):
    """
    Given a list of interesting flags, return the name of any that are active

    :param vault: Vault object
    :param interesting_flag_list: List[str], List of flags to check for in flag timeseries
    :return: List[str], List of flags from interesting_flag_list that are active
    """
    return [
        flag_name
        for flag_name in interesting_flag_list
        if vault.get_flag_timeseries(flag=flag_name).latest()
    ]


def _get_dict_value_based_on_account_tier_flag(
    account_tier_flags, tiered_param, tier_names, convert=lambda x: x
):
    """
    Use the account tier flags to get a corresponding value from a
    dictionary keyed by account tier.
    If no recognised flags are present then the last value in tiered_param
    will be used by default.
    If multiple flags are present then uses the one nearest the start of
    tier_names.

    :param account_tier_flags: List[str], a subset of the tier names parameter, containing the flags
                                         which are active in the account.
    :param tiered_param: Dict[str, str], dictionary mapping tier names to their corresponding.
                         parameter values.
    :param tier_names: List[str], names of tiers for this product.
    :param convert: Callable, function to convert the resulting value before returning e.g Decimal.
    :return: Any - as per convert function, value for tiered_param corresponding to account tier.
    """
    # Iterate over the tier_names to preserve tier order
    for tier in tier_names:
        # The last tier is used as the default if no flags match the tiers
        if tier in account_tier_flags or tier == tier_names[-1]:
            # Ensure tier is present in the tiered parameter
            if tier in tiered_param:
                value = tiered_param[tier]
                return convert(value)

    # Should only get here if tiered_param was missing a key for tier_names[-1]
    raise InvalidContractParameter("No valid account tiers have been configured for this product.")


def _get_start_of_daily_window(vault, effective_date):
    """
    returns either midnight of current day or creation date
    if account is opened for less than a day
    :param vault: get_account_creation_date()
    :param effective_date: datetime
    :return: datetime
    """
    return max(
        effective_date + timedelta(hour=0, minute=0, second=0),
        vault.get_account_creation_date(),
    )


def _is_maintenance_fee_posting(post, account_type):
    """
    :param post: a Vault posting instruction object
    :param account_type: string, the account type (checking or savings)
    :return: Boolean
    """

    if account_type == "us_checking":
        return (
            post.type == PostingInstructionType.CUSTOM_INSTRUCTION
            and "INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_" in post.client_transaction_id
            and post.instruction_details["description"] == "Monthly maintenance fee"
            and post.instruction_details["event"] == "APPLY_MONTHLY_FEES"
        )

    elif account_type == "us_savings":
        return (
            post.type == PostingInstructionType.CUSTOM_INSTRUCTION
            and "INTERNAL_POSTING_APPLY_MAINTENANCE_FEE_MONTHLY" in post.client_transaction_id
            and post.instruction_details["description"] == "Maintenance fee monthly"
            and post.instruction_details["event"] == "APPLY_MAINTENANCE_FEE_MONTHLY"
        )

    return False


def _get_savings_sweep_transfer_amount_with_transfer_unit(
    checking_account, savings_available_balance, maximum_amount_required
):
    """
    Using the savings_sweep_transfer_unit, find the amount that can be transferred with
    the savings balance to meet (or exceed) the maximum amount required. If this cannot be done
    without exceeding the the savings balance, get the highest amount available. The result must
    be a multiple of the value in savings_sweep_transfer_unit parameter.

    :param checking_account: vault object of checking account
    :param savings_available_balance: Decimal, the available balance of savings account
    :param maximum_amount_required: Decimal, the maximum required amount for savings_sweep transfer
    :return: Decimal
    """
    savings_sweep_transfer_unit = _get_parameter(checking_account, "savings_sweep_transfer_unit")
    savings_sweep_transfer_amount = min(savings_available_balance, maximum_amount_required)
    if savings_sweep_transfer_unit > 0:
        remainder = savings_sweep_transfer_amount % savings_sweep_transfer_unit
        if remainder > 0:
            savings_sweep_transfer_amount += savings_sweep_transfer_unit - remainder
            if savings_sweep_transfer_amount > savings_available_balance:
                savings_sweep_transfer_amount -= savings_sweep_transfer_unit
    return savings_sweep_transfer_amount


def _filter_non_supervisee_postings(vault, postings):
    """
    :param vault: the supervisor vault object
    :param postings: the original posting instruction batch from post_posting_code
    :returns: List of posting instructions for supervisee accounts only
    """
    return [posting for posting in postings if posting.account_id in vault.supervisees]
