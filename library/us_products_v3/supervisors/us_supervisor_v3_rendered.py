# Code auto-generated using Inception Smart Contract Renderer Version 2.0.1


# Objects below have been imported from:
#    us_supervisor_v3.py
# md5:52b43e98c4a3c5e8adf4cb19f58b24db

api = "3.12.0"
version = "1.3.4"
supervised_smart_contracts = [
    SmartContractDescriptor(
        alias="us_checking",
        smart_contract_version_id="&{us_checking_account_v3}",
        supervise_post_posting_hook=True,
        supervised_hooks=SupervisedHooks(pre_posting_code=SupervisionExecutionMode.INVOKED),
    ),
    SmartContractDescriptor(
        alias="us_savings",
        smart_contract_version_id="&{us_savings_account_v3}",
        supervise_post_posting_hook=False,
    ),
]


@requires(data_scope="all", parameters=True)
def execution_schedules() -> list[tuple[str, dict[str, Any]]]:
    plan_creation_date = vault.get_plan_creation_date()
    first_schedule_date = plan_creation_date + timedelta(seconds=30)
    first_schedule = _create_schedule_dict_from_datetime(first_schedule_date)
    paused_schedule_date = plan_creation_date + timedelta(year=2099)
    paused_schedule = utils_create_schedule_dict_from_datetime(paused_schedule_date)
    return [
        ("SUPERVISOR_CHECKING_APPLY_MONTHLY_FEES", first_schedule),
        ("SUPERVISOR_SAVINGS_APPLY_MONTHLY_FEES", first_schedule),
        ("SETUP_ODP_LINK", first_schedule),
        ("ODP_SWEEP", paused_schedule),
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
@requires(
    event_type="SETUP_ODP_LINK",
    data_scope="all",
    parameters=True,
    balances="latest",
    supervisee_hook_directives="all",
)
@requires(
    event_type="ODP_SWEEP",
    data_scope="all",
    parameters=True,
    balances="latest",
    supervisee_hook_directives="all",
)
def scheduled_code(event_type: str, effective_date: datetime) -> None:
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
    elif event_type == "SETUP_ODP_LINK":
        _setup_supervisor_schedules(vault, event_type, effective_date)
    elif event_type == "ODP_SWEEP":
        checking_account = supervisor_utils_get_supervisees_for_alias(vault, "us_checking", 1).pop()
        savings_account = supervisor_utils_get_supervisees_for_alias(vault, "us_savings")
        if savings_account:
            (_, posting_instructions) = overdraft_protection_sweep_funds(vault, effective_date)
            utils_instruct_posting_batch(
                checking_account, posting_instructions, effective_date, "ODP_SWEEP"
            )


@fetch_account_data(balances={"us_savings": ["live_balance"], "us_checking": ["live_balance"]})
@requires(data_scope="all", parameters=True)
def pre_posting_code(postings: PostingInstructionBatch, effective_date: datetime) -> None:
    if utils_is_force_override(postings):
        return
    checking_account = supervisor_utils_get_supervisees_for_alias(vault, "us_checking", 1).pop()
    savings_accounts = supervisor_utils_get_supervisees_for_alias(vault, "us_savings")
    overdraft_protection_validate(vault, checking_account, savings_accounts)


@requires(
    parameters=True,
    balances="latest live",
    last_execution_time=["APPLY_MONTHLY_FEES"],
    data_scope="all",
    supervisee_hook_directives="invoked",
)
def post_posting_code(postings: PostingInstructionBatch, effective_date: datetime) -> None:
    savings_accounts = _get_supervisees_for_alias(vault, "us_savings")
    postings = _filter_non_supervisee_postings(vault, postings)
    checking_accounts = {
        vault.supervisees.get(posting.account_id)
        for posting in postings
        if vault.supervisees.get(posting.account_id).get_alias() == "us_checking"
    }
    if len(checking_accounts) > 1:
        raise Rejected(
            "Multiple checking accounts not supported.", reason_code=RejectedReason.AGAINST_TNC
        )
    if len(savings_accounts) > 1:
        raise Rejected(
            "Multiple savings accounts not supported.", reason_code=RejectedReason.AGAINST_TNC
        )
    postings_by_supervisee = vault.get_posting_instructions_by_supervisee()
    checking_account = checking_accounts.pop()
    directives = checking_account.get_hook_directives()
    main_denomination = _get_parameter(name="denomination", vault=checking_account)
    postings = postings_by_supervisee[checking_account.account_id]
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
    offset_amount = -autosave_amount
    if standard_overdraft_instructions:
        posting_instructions.extend(
            overdraft_protection_remove_unnecessary_overdraft_fees(
                checking_account,
                postings,
                offset_amount,
                main_denomination,
                effective_date,
                standard_overdraft_instructions,
            )
        )
    _instruct_posting_batch(checking_account, posting_instructions, effective_date, "POST_POSTING")


# Objects below have been imported from:
#    utils_common.py
# md5:de6b6736b40134e0b26f408a2ee12531


def utils_common_str_to_bool(string: str) -> bool:
    """
    Convert a string true to bool True, default value of False.
    :param string:
    :return:
    """
    return str(string).lower() == "true"


def utils_common_round_decimal(
    amount: Decimal, decimal_places: int, rounding: str = ROUND_HALF_UP
) -> Decimal:
    """
    Round an amount to specified number of decimal places
    :param amount: Decimal, amount to round
    :param decimal_places: int, number of places to round to
    :param rounding: the type of rounding strategy to use
    :return: Decimal, rounded amount
    """
    return amount.quantize(Decimal((0, (1,), -int(decimal_places))), rounding=rounding)


# Objects below have been imported from:
#    utils.py
# md5:c2fb4c0b88915a39e035ec66dd7af335

utils_round_decimal = utils_common_round_decimal
utils_str_to_bool = utils_common_str_to_bool


def utils_get_parameter(
    vault: Any,
    name: str,
    at: Optional[datetime] = None,
    is_json: bool = False,
    is_boolean: bool = False,
    union: bool = False,
    optional: bool = False,
) -> Any:
    """
    Get the parameter value for a given parameter
    :param vault:
    :param name: name of the parameter to retrieve
    :param at: datetime, time at which to retrieve the parameter value. If not
    specified the latest value is retrieved
    :param is_json: if true json_loads is called on the retrieved parameter value
    :param is_boolean: if true str_to_bool is called on the retrieved parameter value
    :param union: if True parameter will be treated as a UnionItem
    :param optional: if true we treat the parameter as optional
    :return:
    """
    if at:
        parameter = vault.get_parameter_timeseries(name=name).at(timestamp=at)
    else:
        parameter = vault.get_parameter_timeseries(name=name).latest()
    if optional:
        parameter = parameter.value if parameter.is_set() else None
    if union and parameter is not None:
        parameter = parameter.key
    if is_boolean and parameter is not None:
        return utils_str_to_bool(parameter)
    if is_json and parameter is not None:
        parameter = json_loads(parameter)
    return parameter


def utils_get_available_balance(
    balances: BalanceDefaultDict,
    denomination: str,
    address: str = DEFAULT_ADDRESS,
    asset: str = DEFAULT_ASSET,
) -> Decimal:
    """
    Returns the sum of net balances including COMMITTED and PENDING_OUT only.

    :param balances: balances for an account
    :param denomination: balance denomination
    :param address: balance address
    :param asset: balance asset
    :return: Decimal
    """
    return Decimal(balances[address, asset, denomination, Phase.COMMITTED].net) + Decimal(
        balances[address, asset, denomination, Phase.PENDING_OUT].net
    )


def utils_create_schedule_dict_from_datetime(
    schedule_datetime: datetime, one_off: bool = True
) -> dict[str, str]:
    """
    Creates a dict representing a schedule from datetime as function input
    :param schedule_datetime: the datetime to convert to schedule format
    :param one_off: if true, the `year` key is included in the dictionary, making this a one-off
    schedule. This is only suitable if the schedule will only be updated before completion, or
    during processing of its own job(s). Otherwise, set to False so that the schedule does not
    complete and can be updated
    """
    schedule = {
        "month": str(schedule_datetime.month),
        "day": str(schedule_datetime.day),
        "hour": str(schedule_datetime.hour),
        "minute": str(schedule_datetime.minute),
        "second": str(schedule_datetime.second),
    }
    if one_off:
        schedule["year"] = str(schedule_datetime.year)
    return schedule


def utils_create_schedule_dict(
    start_date: Optional[datetime] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    hour: Optional[int] = None,
    minute: Optional[int] = None,
    second: Optional[int] = None,
) -> dict[str, str]:
    """
    Creates a dictionary representing a schedule from datetime parameters.
    :param start_date: starting date for the schedule
    :param year: year for schedule to run
    :param month: month for schedule to run
    :param day: day of month for schedule to run
    :param hour: hour of day for schedule to run
    :param minute: minute of hour for schedule to run
    :param second: second of minute for schedule to run
    :return: representation of schedule
    """
    schedule_dict = {}
    if start_date is not None:
        schedule_dict["start_date"] = start_date.isoformat()
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


def utils_instruct_posting_batch(
    vault: Any,
    posting_instructions: list[PostingInstruction],
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


def utils_is_force_override(pib: PostingInstructionBatch) -> bool:
    return utils_str_to_bool(pib.batch_details.get("force_override"))


# Objects below have been imported from:
#    supervisor_utils.py
# md5:2651a8b5af4c5599991225f311936c1c


def supervisor_utils_get_supervisees_for_alias(
    vault: Any, alias: str, num_requested: Optional[int] = None
) -> list[Any]:
    """
    Returns a list of supervisee vault objects for the given alias, ordered by account creation date
    :param vault: vault, supervisor vault object
    :param alias: str, the supervisee alias to filter for
    :param num_requested: int, the exact number of expected supervisees
    :raises Rejected: if num_requested is specified and the exact amount of supervisees for the
    alias does not match
    :return: list, supervisee vault objects for given alias, ordered by account creation date
    """
    sorted_supervisees = supervisor_utils_sort_supervisees(
        [supervisee for supervisee in vault.supervisees.values() if supervisee.get_alias() == alias]
    )
    if num_requested:
        if not len(sorted_supervisees) == num_requested:
            raise Rejected(
                f"Requested {num_requested} {alias} accounts but found {len(sorted_supervisees)}.",
                reason_code=RejectedReason.AGAINST_TNC,
            )
    return sorted_supervisees


def supervisor_utils_sort_supervisees(supervisees: list[Any]) -> list[Any]:
    """
    Sorts supervisees first by creation date, and then alphabetically by id if
    numerous supervisees share the same creation date and creates a list of ordered
    vault objects.
    :param supervisees: list[Vault], list of supervisee vault objects
    :return sorted_supervisees: list[Vault], list of ordered vault objects
    """
    sorted_supervisees_by_id = sorted(supervisees, key=lambda vault: vault.account_id)
    sorted_supervisees_by_age_then_id = sorted(
        sorted_supervisees_by_id, key=lambda vault: vault.get_account_creation_date()
    )
    return sorted_supervisees_by_age_then_id


def supervisor_utils_create_supervisor_event_type_schedule_from_datetime(
    schedule_datetime: datetime, one_off: bool = True
) -> EventTypeSchedule:
    """
    Creates a supervisor contract EventTypeSchedule from a datetime object.

    :param schedule_datetime: datetime, object to be formatted
    :param one_off: if true, the `year` key is included in the dictionary, making this a one-off
    schedule. This is only suitable if the schedule will only be updated before completion, or
    during processing of its own job(s). Otherwise, set to False so that the schedule does not
    complete and can be updated
    :return: EventTypeSchedule representation of datetime
    """
    if one_off:
        return EventTypeSchedule(
            day=str(schedule_datetime.day),
            hour=str(schedule_datetime.hour),
            minute=str(schedule_datetime.minute),
            second=str(schedule_datetime.second),
            month=str(schedule_datetime.month),
            year=str(schedule_datetime.year),
        )
    else:
        return EventTypeSchedule(
            day=str(schedule_datetime.day),
            hour=str(schedule_datetime.hour),
            minute=str(schedule_datetime.minute),
            second=str(schedule_datetime.second),
            month=str(schedule_datetime.month),
        )


def supervisor_utils_create_supervisor_event_type_schedule_from_schedule_dict(
    schedule_dict: dict,
) -> EventTypeSchedule:
    """
    Creates a supervisor contract EventTypeSchedule from a schedule dictionary.

    :param schedule_datetime: datetime, object to be formatted
    :return: Supervisor EventTypeSchedule representation of the schedule
    """
    return EventTypeSchedule(
        day=schedule_dict.get("day", None),
        day_of_week=schedule_dict.get("day_of_week", None),
        hour=schedule_dict.get("hour", None),
        minute=schedule_dict.get("minute", None),
        second=schedule_dict.get("second", None),
        month=schedule_dict.get("month", None),
        year=schedule_dict.get("year", None),
    )


def supervisor_utils_sum_available_balances_across_supervisees(
    supervisees: list[Any],
    denomination: str,
    effective_date: Optional[datetime] = None,
    observation_fetcher_id: Optional[str] = None,
    rounding_precision: int = 2,
) -> Decimal:
    """
    Sums the net balance values for the committed and pending outgoing phases
    across multiple vault objects, rounding the balance sum at a per-vault level.
    Effective_date and observation_feature_id are both being offered here because optimised
    data fetching isn't supported in all supervisor hooks yet, in the future only
    observation_feature_id's will be supported.
    :param supervisees: the vault objects to get balances timeseries/observations from
    :param denomination: the denomination of the balances
    :param effective_date: the datetime as-of which to get the balances. If not specified
    latest is used. Not used if observation_fetcher_id is specified.
    :param observation_fetcher_id: the fetcher id to use to get the balances. If specified
    the effective_date is unused as the observation is already for a specific datetime
    :param rounding_precision: the precision to which each balance is individually rounded
    :return: the sum of balances across the specified supervisees
    """
    if observation_fetcher_id:
        return Decimal(
            sum(
                (
                    utils_round_decimal(
                        utils_get_available_balance(
                            supervisee.get_balances_observation(
                                fetcher_id=observation_fetcher_id
                            ).balances,
                            denomination,
                        ),
                        rounding_precision,
                    )
                    for supervisee in supervisees
                )
            )
        )
    else:
        return Decimal(
            sum(
                (
                    utils_round_decimal(
                        utils_get_available_balance(
                            supervisee.get_balance_timeseries().latest()
                            if effective_date is None
                            else supervisee.get_balance_timeseries().at(timestamp=effective_date),
                            denomination,
                        ),
                        rounding_precision,
                    )
                    for supervisee in supervisees
                )
            )
        )


# Objects below have been imported from:
#    overdraft_protection.py
# md5:5e0834e2cce3f73540c44b9f5e23491f


def overdraft_protection__check_for_savings_coverage(
    vault: Any, checking_account: Any, savings_account: Any
) -> None:
    """
    This function is checking that there is enough balance across
    the linked savings and checking accounts to cover the proposed
    transaction
    """
    standard_overdraft_limit = 0
    standard_overdraft_limit = utils_get_parameter(
        name="standard_overdraft_limit", vault=checking_account
    )
    denomination = utils_get_parameter(name="denomination", vault=checking_account)
    new_checking_account_postings = vault.get_posting_instructions_by_supervisee()[
        checking_account.account_id
    ]
    new_checking_account_postings_balance = utils_get_available_balance(
        new_checking_account_postings.balances(), denomination
    )
    combined_balance = supervisor_utils_sum_available_balances_across_supervisees(
        [checking_account, savings_account],
        denomination=denomination,
        observation_fetcher_id="live_balance",
        rounding_precision=2,
    )
    if combined_balance + new_checking_account_postings_balance + standard_overdraft_limit < 0:
        raise Rejected(
            f"Combined checking and savings account balance {combined_balance} insufficient to cover net transaction amount {new_checking_account_postings_balance}",
            reason_code=RejectedReason.INSUFFICIENT_FUNDS,
        )


def overdraft_protection_validate(
    vault: Any, checking_account: Any, savings_accounts: list[Any]
) -> None:
    """
    In this function we are checking to see if the proposed transaction is covered by ODP,
    this includes ensuring that the rejection raised on the checking is due to insufficient funds
    and we have a linked savings account with enough balance to cover the net transaction

    :param: vault: Vault object
    :param: checking_account:
    :param: checking_account:
    :raises: Rejected: Can raise the rejection fetched from the checking account, unless it is of
    type INSUFFICIENT_FUNDS and we have a linked savings account. If we have more than one linked
    savings account we will raise a separate rejection of type AGAINST_TNC
    :return: None
    """
    account_rejection = checking_account.get_hook_return_data()
    if not account_rejection:
        return
    if account_rejection.reason_code != RejectedReason.INSUFFICIENT_FUNDS:
        raise account_rejection
    if len(savings_accounts) == 0:
        raise account_rejection
    elif len(savings_accounts) > 1:
        raise Rejected(
            f"Requested 1 us_savings accounts but found {len(savings_accounts)}.",
            reason_code=RejectedReason.AGAINST_TNC,
        )
    savings_account = savings_accounts.pop()
    overdraft_protection__check_for_savings_coverage(vault, checking_account, savings_account)


def overdraft_protection_sweep_funds(
    vault: Any, effective_date: datetime
) -> tuple[Decimal, list[PostingInstruction]]:
    """
    sweep_funds is used to generate a posting that sweeps funds from a savings
    account to a checking account to avoid potential overdraft fees
    As we are making use of the .latest() balances we need to ensure that the
    balances provided are live.
    """
    savings_sweep_transfer_amount: Decimal = Decimal("0")
    posting_instructions = []
    savings_accounts = supervisor_utils_get_supervisees_for_alias(vault, "us_savings", 1)
    savings_account = savings_accounts.pop()
    checking_account = supervisor_utils_get_supervisees_for_alias(vault, "us_checking", 1).pop()
    denomination = utils_get_parameter(name="denomination", vault=checking_account)
    balances = checking_account.get_balance_timeseries().latest()
    checking_account_committed_balance = Decimal(
        balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
    )
    if checking_account_committed_balance < 0:
        savings_available_balance = utils_get_available_balance(
            savings_account.get_balance_timeseries().latest(), denomination
        )
        savings_sweep_transfer_amount = min(
            abs(checking_account_committed_balance), savings_available_balance
        )
        if savings_sweep_transfer_amount > Decimal("0"):
            posting_instructions.extend(
                checking_account.make_internal_transfer_instructions(
                    amount=savings_sweep_transfer_amount,
                    denomination=denomination,
                    client_transaction_id=f"INTERNAL_POSTING_SWEEP_WITHDRAWAL_FROM_{savings_account.account_id}_{checking_account.get_hook_execution_id()}",
                    from_account_id=savings_account.account_id,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=checking_account.account_id,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    pics=[],
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Sweep from savings account",
                        "event": "SWEEP",
                    },
                )
            )
    return (savings_sweep_transfer_amount, posting_instructions)


def overdraft_protection_remove_unnecessary_overdraft_fees(
    vault: Any,
    postings: list[PostingInstruction],
    offset_amount: Decimal,
    denomination: str,
    effective_date: datetime,
    standard_overdraft_instructions: list[PostingInstruction],
) -> list[PostingInstruction]:
    balances = vault.get_balance_timeseries().before(timestamp=effective_date)
    fee_free_overdraft_limit = vault.get_parameter_timeseries(
        name="fee_free_overdraft_limit"
    ).latest()
    balance_before = balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
    proposed_amount = postings.balances()[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
    ].net
    latest_balance = balance_before + proposed_amount
    effective_balance = latest_balance + offset_amount
    posting_instructions = []
    counter = 0
    for posting in sorted(
        postings,
        key=lambda posting: posting.balances()[
            DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
        ].net,
    ):
        if effective_balance < -fee_free_overdraft_limit:
            counter += 1
        effective_balance += posting.balances()[
            DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
        ].net
    for instruction in standard_overdraft_instructions:
        client_transaction_id = instruction.client_transaction_id.split("_")
        if int(client_transaction_id[-1]) < counter:
            posting_instructions.append(instruction)
    return posting_instructions


def overdraft_protection_get_odp_sweep_schedule(checking_account: Any) -> dict[str, str]:
    """
    Sets up dictionary of odp_sweep schedule based on parameters

    :param vault: Vault object
    :return: dict, representation of odp_sweep schedule
    """
    overdraft_protection_sweep_hour = utils_get_parameter(
        checking_account, name="overdraft_protection_sweep_hour"
    )
    overdraft_protection_sweep_minute = utils_get_parameter(
        checking_account, name="overdraft_protection_sweep_minute"
    )
    overdraft_protection_sweep_second = utils_get_parameter(
        checking_account, name="overdraft_protection_sweep_second"
    )
    overdraft_protection_sweep_schedule = utils_create_schedule_dict(
        hour=overdraft_protection_sweep_hour,
        minute=overdraft_protection_sweep_minute,
        second=overdraft_protection_sweep_second,
    )
    return overdraft_protection_sweep_schedule


# Objects below have been imported from:
#    us_supervisor_v3.py
# md5:52b43e98c4a3c5e8adf4cb19f58b24db

DEFAULT_TRANSACTION_TYPE = "PURCHASE"
DEFAULT_DENOMINATION = "USD"
INTERNAL_POSTING = "INTERNAL_POSTING"
EXTERNAL_POSTING = "EXTERNAL_POSTING"
TIER_PARAM_NAME = {"us_checking": "tier_names", "us_savings": "account_tier_names"}
data_fetchers = [BalancesObservationFetcher(fetcher_id="live_balance", at=DefinedDateTime.LIVE)]
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
    EventType(name="SETUP_ODP_LINK", scheduler_tag_ids=["SETUP_ODP_LINK_AST"]),
    EventType(name="ODP_SWEEP", scheduler_tag_ids=["SUPERVISOR_ODP_SWEEP_AST"]),
]


def _apply_checking_or_savings_monthly_fees(
    vault: Any, effective_date: datetime, account_type: str, accounts: Optional[list] = None
) -> None:
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
        creation_date = account.get_account_creation_date()
        first_schedule_date = _get_next_fee_datetime(account, creation_date)
        last_execution_time = account.get_last_execution_time(event_type="APPLY_MONTHLY_FEES")
        is_less_than_one_month_since_creation = (
            last_execution_time is None and effective_date < first_schedule_date
        )
        is_less_than_one_month_since_last_event_run = (
            last_execution_time is not None
            and last_execution_time < effective_date
            and (effective_date < _get_next_fee_datetime(account, last_execution_time))
        )
        if is_less_than_one_month_since_creation or is_less_than_one_month_since_last_event_run:
            continue
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
                    posting_instructions=posting_instructions, effective_date=effective_date
                )


def _get_supervisees_for_alias(vault: Any, alias: str) -> list[Any]:
    """
    Returns a list of supervisee vault objects for the given alias, ordered by account creation date
    :param vault: vault, supervisor vault object
    :param alias: the supervisee alias to filter for
    :return: supervisee vault objects for given alias, ordered by account creation date
    """
    return sorted(
        (
            supervisee
            for supervisee in vault.supervisees.values()
            if supervisee.get_alias() == alias
        ),
        key=lambda v: v.get_account_creation_date(),
    )


def _get_parameter(
    vault: Any,
    name: str,
    at: Optional[datetime] = None,
    is_json: bool = False,
    optional: bool = False,
    default_value: Any = None,
) -> Any:
    """
    Get the parameter value for a given parameter
    :param vault:
    :param name: name of the parameter to retrieve
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


def _instruct_posting_batch(
    vault: Any,
    posting_instructions: list[PostingInstruction],
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


def _create_schedule_dict_from_datetime(schedule_datetime: datetime) -> dict:
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


def _create_event_type_schedule_from_datetime(schedule_datetime: datetime) -> EventTypeSchedule:
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


def _get_next_fee_datetime(vault: Any, effective_date: datetime) -> datetime:
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


def _get_applicable_postings(
    vault: Any,
    pib: PostingInstructionBatch,
    account_type: str,
    monthly_mean_combined_balance: Decimal,
) -> list[PostingInstruction]:
    """
    Checks which postings should be filtered out based on waiver
    criteria, applies supervisor instruction details.
    :param vault: supervisee Vault object
    :param pib: posting instruction batch retrieved from supervisee directive
    :param account_type: string, us_checking or us_savings
    :param monthly_mean_combined_balance: Decimal

    :return: list[PostingInstruction], the posting instructions if not waivered
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
            post.custom_instruction_grouping_key = post.client_transaction_id
            post.client_transaction_id += "_SUPERVISOR"
            post.instruction_details["supervisor"] = "Applied by supervisor"
            posting_instructions.append(post)
    return posting_instructions


def _schedule_monthly_fees_events(
    vault: Any, effective_date: datetime, event_type: str, accounts: Optional[list] = None
) -> None:
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
    if not accounts:
        vault.update_event_type(
            event_type=event_type,
            schedule=_create_event_type_schedule_from_datetime(effective_date + timedelta(hours=1)),
        )
    else:
        next_schedule_date = _get_next_fee_datetime(accounts[0], effective_date)
        vault.update_event_type(
            event_type=event_type,
            schedule=_create_event_type_schedule_from_datetime(next_schedule_date),
        )
        for account in accounts:
            next_schedule_date = _get_next_fee_datetime(account, effective_date)
            account.update_event_type(
                event_type="APPLY_MONTHLY_FEES",
                schedule=_create_event_type_schedule_from_datetime(next_schedule_date),
            )


def _monthly_mean_balance(
    denomination: str, effective_date: datetime, all_accounts: list[Any]
) -> Decimal:
    """
    Determine the average combined balance for the preceding month. The sampling period is from one
    month before, until the effective_date, exclusive i.e. not including the effective_date day

    :param denomination: Account denomination
    :param effective_date: datetime, date and time of hook being run
    :param all_accounts: list[Vault objects], list of all accounts for combined balance
    :return: Decimal, mean combined balance at sampling time for previous month
    """
    period_start = effective_date - timedelta(months=1)
    num_days = max((effective_date - period_start).days, 1)
    total = sum(
        (
            sum(
                (
                    account.get_balance_timeseries()
                    .at(timestamp=period_start + timedelta(days=i))[
                        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
                    ]
                    .net
                    for i in range(num_days)
                    if account.get_account_creation_date() <= period_start + timedelta(days=i)
                )
            )
            for account in all_accounts
        )
    )
    return total / num_days


def _get_active_account_flags(vault: Any, interesting_flag_list: list[str]) -> list[str]:
    """
    Given a list of interesting flags, return the name of any that are active

    :param vault: Vault object
    :param interesting_flag_list: list[str], list of flags to check for in flag timeseries
    :return: list[str], list of flags from interesting_flag_list that are active
    """
    return [
        flag_name
        for flag_name in interesting_flag_list
        if vault.get_flag_timeseries(flag=flag_name).latest()
    ]


def _get_dict_value_based_on_account_tier_flag(
    account_tier_flags: list[str],
    tiered_param: dict[str, str],
    tier_names: list[str],
    convert: Callable = lambda x: x,
) -> Any:
    """
    Use the account tier flags to get a corresponding value from a
    dictionary keyed by account tier.
    If no recognised flags are present then the last value in tiered_param
    will be used by default.
    If multiple flags are present then uses the one nearest the start of
    tier_names.

    :param account_tier_flags: list[str], a subset of the tier names parameter, containing the flags
                                         which are active in the account.
    :param tiered_param: dict[str, str], dictionary mapping tier names to their corresponding.
                         parameter values.
    :param tier_names: list[str], names of tiers for this product.
    :param convert: Callable, function to convert the resulting value before returning e.g Decimal.
    :return: Any - as per convert function, value for tiered_param corresponding to account tier.
    """
    for tier in tier_names:
        if tier in account_tier_flags or tier == tier_names[-1]:
            if tier in tiered_param:
                value = tiered_param[tier]
                return convert(value)
    raise InvalidContractParameter("No valid account tiers have been configured for this product.")


def _is_maintenance_fee_posting(post: PostingInstruction, account_type: str) -> bool:
    """
    :param post: a Vault posting instruction object
    :param account_type: string, the account type (checking or savings)
    :return: Boolean
    """
    if account_type == "us_checking":
        return (
            post.type == PostingInstructionType.CUSTOM_INSTRUCTION
            and "INTERNAL_POSTING_APPLY_MONTHLY_FEES_MAINTENANCE_" in post.client_transaction_id
            and (post.instruction_details["description"] == "Monthly maintenance fee")
            and (post.instruction_details["event"] == "APPLY_MONTHLY_FEES")
        )
    elif account_type == "us_savings":
        return (
            post.type == PostingInstructionType.CUSTOM_INSTRUCTION
            and "INTERNAL_POSTING_APPLY_MAINTENANCE_FEE_MONTHLY" in post.client_transaction_id
            and (post.instruction_details["description"] == "Maintenance fee monthly")
            and (post.instruction_details["event"] == "APPLY_MAINTENANCE_FEE_MONTHLY")
        )
    return False


def _filter_non_supervisee_postings(
    vault: Any, postings: list[PostingInstruction]
) -> list[PostingInstruction]:
    """
    :param vault: the supervisor vault object
    :param postings: the original posting instruction batch from post_posting_code
    :returns: list of posting instructions for supervisee accounts only
    """
    return [posting for posting in postings if posting.account_id in vault.supervisees]


def _setup_supervisor_schedules(vault: Any, event_type: str, effective_date: datetime) -> None:
    """
    This method updates a dummy Event (SETUP_ODP_LINK) so that when the checking
    account is created, it then updates the other scheduled Events based on the
    respective schedule parameters of the checking account.
    :param vault: the supervisor vault object
    :param effective date: datetime, datetime of when the schedules are checked
    """
    checking_accounts = supervisor_utils_get_supervisees_for_alias(vault, "us_checking")
    if len(checking_accounts) == 0:
        vault.update_event_type(
            event_type=event_type,
            schedule=supervisor_utils_create_supervisor_event_type_schedule_from_datetime(
                effective_date + timedelta(minutes=1)
            ),
        )
    else:
        checking_account = checking_accounts.pop()
        odp_sweep_schedule = overdraft_protection_get_odp_sweep_schedule(checking_account)
        vault.update_event_type(
            event_type="ODP_SWEEP",
            schedule=supervisor_utils_create_supervisor_event_type_schedule_from_schedule_dict(
                odp_sweep_schedule
            ),
        )
