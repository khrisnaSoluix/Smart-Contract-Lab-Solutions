# Code auto-generated using Inception Smart Contract Renderer Version 1.0.3


# Objects below have been imported from:
#    murabahah.py
# md5:082578ac76b2dd87d9373beea963894b

api = "3.10.0"
version = "2.0.0"
display_name = "Murabahah"
summary = "A CASA account with a fixed profit rate."
tside = Tside.LIABILITY
supported_denominations = ["MYR"]


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def execution_schedules():
    return profit_accrual_get_execution_schedules(vault)


@requires(event_type="ACCRUE_PROFIT", flags=True, parameters=True, balances="1 day")
@requires(
    event_type="APPLY_ACCRUED_PROFIT",
    parameters=True,
    balances="latest",
    calendar=["&{PUBLIC_HOLIDAYS}"],
)
def scheduled_code(event_type, effective_date):
    posting_instructions = []
    denomination = utils_get_parameter(vault, "denomination")
    if event_type == "ACCRUE_PROFIT":
        posting_instructions.extend(
            profit_accrual_get_accrual_posting_instructions(
                vault, effective_date, denomination, tiered_profit_calculation_feature
            )
        )
    elif event_type == "APPLY_ACCRUED_PROFIT":
        posting_instructions.extend(
            profit_accrual_get_apply_accrual_posting_instructions(
                vault, effective_date, denomination
            )
        )
        _reschedule_apply_accrued_profit_event(vault, effective_date)
    if posting_instructions:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions,
            effective_date=effective_date,
            client_batch_id=f"{event_type}_{vault.get_hook_execution_id()}",
            batch_details={"event": event_type},
        )


@requires(parameters=True, balances="latest live")
def close_code(effective_date):
    denomination = utils_get_parameter(vault, "denomination")
    closure_fees = early_closure_fee_get_fees(vault, denomination, effective_date)
    residual_cleanups = profit_accrual_get_residual_cleanup_posting_instructions(
        vault,
        denomination,
        instruction_details={
            "description": "Reverse profit due to account closure",
            "event": "CLOSE_ACCOUNT",
            "account_type": "MURABAHAH",
        },
    )
    posting_instructions = closure_fees + residual_cleanups
    if posting_instructions:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions,
            effective_date=effective_date,
            client_batch_id=f"{vault.get_hook_execution_id()}",
            batch_details={"event": "CLOSE_CODE"},
        )


@requires(parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def post_parameter_change_code(old_parameters, new_parameters, effective_date):
    if utils_has_parameter_value_changed("profit_application_day", old_parameters, new_parameters):
        _reschedule_apply_accrued_profit_event(vault, effective_date)


@requires(parameters=True, balances="latest live", postings="1 day")
def pre_posting_code(postings, effective_date):
    if postings.batch_details.get("force_override", "false").lower() == "true":
        return
    utils_validate_denomination(vault, postings)
    denomination = utils_get_parameter(vault, "denomination")
    balances = vault.get_balance_timeseries().latest()
    client_transactions = vault.get_client_transactions(include_proposed=True)
    client_transactions_excluding_proposed = vault.get_client_transactions(include_proposed=False)
    maximum_balance_limit_validate(
        vault=vault, postings=postings, balances=balances, denomination=denomination
    )
    maximum_single_withdrawal_validate(vault=vault, postings=postings, denomination=denomination)
    minimum_initial_deposit_validate(
        vault=vault, postings=postings, balances=balances, denomination=denomination
    )
    minimum_balance_by_tier_validate(
        vault=vault, postings=postings, balances=balances, denomination=denomination
    )
    maximum_withdrawal_by_payment_type_validate(
        vault=vault, postings=postings, denomination=denomination
    )
    minimum_single_deposit_validate(vault=vault, postings=postings, denomination=denomination)
    maximum_single_deposit_validate(vault=vault, postings=postings, denomination=denomination)
    category_limit_mapping = utils_get_parameter(
        vault, "maximum_daily_payment_category_withdrawal", is_json=True
    )
    type_limit_mapping = utils_get_parameter(
        vault, "maximum_daily_payment_type_withdrawal", is_json=True
    )
    maximum_daily_deposit_validate(
        vault=vault,
        client_transactions=client_transactions,
        client_transactions_excluding_proposed=client_transactions_excluding_proposed,
        effective_date=effective_date,
        denomination=denomination,
        net_batch=False,
    )
    maximum_daily_withdrawal_validate(
        vault=vault,
        client_transactions=client_transactions,
        client_transactions_excluding_proposed=client_transactions_excluding_proposed,
        effective_date=effective_date,
        denomination=denomination,
        net_batch=False,
    )
    maximum_daily_withdrawal_by_category_validate(
        limit_mapping=category_limit_mapping,
        instruction_detail_key=PAYMENT_CATEGORY,
        postings=postings,
        client_transactions=client_transactions,
        effective_date=effective_date,
        denomination=denomination,
    )
    maximum_daily_withdrawal_by_category_validate(
        limit_mapping=type_limit_mapping,
        instruction_detail_key=PAYMENT_TYPE,
        postings=postings,
        client_transactions=client_transactions,
        effective_date=effective_date,
        denomination=denomination,
    )


@requires(parameters=True, postings="1 month")
def post_posting_code(postings, effective_date):
    denomination = utils_get_parameter(vault, "denomination")
    client_transactions = vault.get_client_transactions(include_proposed=True)
    flat_fees = payment_type_flat_fee_get_fees(
        vault=vault, postings=postings, denomination=denomination
    )
    threshold_fees = payment_type_threshold_fee_get_fees(
        vault=vault, postings=postings, denomination=denomination
    )
    monthly_limit_fees = monthly_limit_by_payment_type_get_fees(
        vault=vault,
        postings=postings,
        client_transactions=client_transactions,
        effective_date=effective_date,
        denomination=denomination,
    )
    posting_instructions = flat_fees + threshold_fees + monthly_limit_fees
    if posting_instructions:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions, effective_date=effective_date
        )


# Objects below have been imported from:
#    utils.py
# md5:1b2a39a9ec5d9b67766de5f40c622402

utils_VALID_DAYS_IN_YEAR = ["360", "365", "366", "actual"]
utils_DEFAULT_DAYS_IN_YEAR = "actual"
utils_FREQUENCY_TO_MONTHS_MAP = {"monthly": 1, "quarterly": 3, "annually": 12}
utils_DEFAULT_FREQUENCY = "monthly"
utils_MoneyShape = NumberShape(kind=NumberKind.MONEY, min_value=0, max_value=10000, step=0.01)
utils_LimitHundredthsShape = NumberShape(kind=NumberKind.MONEY, min_value=0, step=0.01)
utils_EventTuple = NamedTuple("EventTuple", [("event_type", str), ("schedule", dict[str, str])])


def utils_get_parameter(
    vault,
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


def utils_get_daily_schedule(vault, param_prefix: str, event_type: str) -> utils_EventTuple:
    """
    Creates an EventTuple to represent an event type's daily schedule based on the Vault
    object's parameters.
    :param vault: Vault object
    :param param_prefix: the prefix given to the schedule parameters, which should be named
    - <param_prefix>_hour, <param_prefix>_minute and <param_prefix>_second
    :param event_type: the schedule's event type
    :return: representation of event_type schedule
    """
    creation_date = vault.get_account_creation_date()
    schedule = utils_create_schedule_dict(
        hour=utils_get_parameter(vault, param_prefix + "_hour", at=creation_date),
        minute=utils_get_parameter(vault, param_prefix + "_minute", at=creation_date),
        second=utils_get_parameter(vault, param_prefix + "_second", at=creation_date),
    )
    return utils_EventTuple(event_type, schedule)


def utils_falls_on_calendar_events(
    vault, localised_effective_date: datetime, calendar_events: CalendarEvents
) -> bool:
    """
    Returns if true if the given date is on or between a calendar event's start and/or end
    timestamp, inclusive.
    """
    for calendar_event in calendar_events:
        localised_event_start = vault.localize_datetime(dt=calendar_event.start_timestamp)
        localised_event_end = vault.localize_datetime(dt=calendar_event.end_timestamp)
        if (
            localised_event_start <= localised_effective_date
            and localised_effective_date <= localised_event_end
        ):
            return True
    return False


def utils_get_balance_sum(
    vault,
    addresses: list[str],
    timestamp: Optional[datetime] = None,
    denomination: Optional[str] = None,
    phase: Phase = Phase.COMMITTED,
) -> Decimal:
    """
    Sum balance from a timeseries entry for a phase, denomination and list of given addresses.
    :param vault: balances, parameters
    :param addresses: list of addresses
    :param timestamp: optional datetime at which balances to be summed
    :param denomination: the denomination of the balance
    :param phase: phase of the balance
    :return: sum of the balances
    """
    balances = (
        vault.get_balance_timeseries().latest()
        if timestamp is None
        else vault.get_balance_timeseries().at(timestamp=timestamp)
    )
    denom: str = (
        utils_get_parameter(vault, "denomination") if denomination is None else denomination
    )
    return utils__sum_balances(balances, addresses, denom, phase)


def utils__sum_balances(
    balances: BalanceDefaultDict,
    addresses: list[str],
    denomination: str,
    phase: Phase = Phase.COMMITTED,
) -> Decimal:
    return Decimal(
        sum((balances[address, DEFAULT_ASSET, denomination, phase].net for address in addresses))
    )


def utils_str_to_bool(string: str) -> bool:
    """
    Convert a string true to bool True, default value of False.
    :param string:
    :return:
    """
    return str(string).lower() == "true"


def utils_yearly_to_daily_rate(
    yearly_rate: Decimal, year: int, days_in_year: str = "actual"
) -> Decimal:
    """
    Convert yearly rate to daily rate.
    """
    days_in_year = (
        days_in_year if days_in_year in utils_VALID_DAYS_IN_YEAR else utils_DEFAULT_DAYS_IN_YEAR
    )
    if days_in_year == "actual":
        num_days_in_year = Decimal("366") if calendar.isleap(year) else Decimal("365")
    else:
        num_days_in_year = Decimal(days_in_year)
    return yearly_rate / num_days_in_year


def utils_round_decimal(
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


def utils_remove_exponent(d: Decimal) -> Decimal:
    """
    Safely remove trailing zeros when dealing with exponents. This is useful when using a decimal
    value in a string used for informational purposes (e.g. instruction_details or logging).
    E.g: remove_exponent(Decimal("5E+3"))
    Returns: Decimal('5000')
    """
    return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()


def utils_get_schedule(
    vault,
    param_prefix: str,
    event_type: str,
    localised_effective_date: datetime,
    schedule_frequency: str,
    schedule_day_of_month: int,
    calendar_events: CalendarEvents,
) -> utils_EventTuple:
    """
    Get a schedule for monthly/quarterly/annually frequency
    :param vault:
    :param localised_effective_date: the localised date to use to base the calculation on
    :param param_prefix: the prefix given to the schedule parameters, which should be named
    - <param_prefix>_hour, <param_prefix>_minute and <param_prefix>_second
    :param schedule_frequency: the frequency of the schedule. One of `monthly`, `quarterly` or
    `annually`
    :param schedule_day_of_month: the desired day of the month for the schedule to fall on
    :param calendar_events: events that the schedule date should not fall on. The date will be
    increased by a day until this condition is met
    """
    next_schedule_date = utils_get_next_schedule_datetime(
        vault,
        localised_effective_date=localised_effective_date,
        param_prefix=param_prefix,
        schedule_frequency=schedule_frequency,
        schedule_day_of_month=schedule_day_of_month,
        calendar_events=calendar_events,
    )
    return utils_EventTuple(
        event_type,
        utils_create_schedule_dict(
            year=next_schedule_date.year,
            month=next_schedule_date.month,
            day=next_schedule_date.day,
            hour=next_schedule_date.hour,
            minute=next_schedule_date.minute,
            second=next_schedule_date.second,
        ),
    )


def utils_get_next_schedule_datetime(
    vault,
    localised_effective_date: datetime,
    param_prefix: str,
    schedule_frequency: str,
    schedule_day_of_month: int,
    calendar_events: CalendarEvents,
) -> datetime:
    """
    Gets next date for monthly/quarterly/annually schedules with parameterised time
    :param vault:
    :param localised_effective_date: the localised date to use to base the calculation on
    :param param_prefix: the prefix given to the schedule parameters, which should be named
    - <param_prefix>_hour, <param_prefix>_minute and <param_prefix>_second
    :param schedule_frequency: the frequency of the schedule. One of `monthly`, `quarterly` or
    `annually`
    :param schedule_day_of_month: the desired day of the month for the schedule to fall on
    :param calendar_events: events that the schedule date should not fall on. The date will be
    increased by a day until this condition is met
    """
    next_schedule_date = utils_get_next_schedule_day(
        vault, localised_effective_date, schedule_frequency, schedule_day_of_month, calendar_events
    )
    next_schedule_datetime = next_schedule_date.replace(
        hour=utils_get_parameter(vault, param_prefix + "_hour"),
        minute=utils_get_parameter(vault, param_prefix + "_minute"),
        second=utils_get_parameter(vault, param_prefix + "_second"),
    )
    return next_schedule_datetime


def utils_get_next_schedule_day(
    vault,
    localised_effective_date: datetime,
    schedule_frequency: str,
    schedule_day_of_month,
    calendar_events: CalendarEvents,
) -> datetime:
    """
    Calculate next valid date for schedule based on day of month. Timedelta (relativedelta) falls
    to last valid day of month if intended day is not in calculated month. This method returns the
    day part of the applications schedule, which will then be updated with the time part by the
    get_next_schedule_datetime method.
    :param vault:
    :param localised_effective_date: the localised date to use to base the calculation on
    :param schedule_frequency: the frequency of the schedule. One of `monthly`, `quarterly` or
    `annually`
    :param schedule_day_of_month: the desired day of the month for the schedule to fall on
    :param calendar_events: events that the schedule date should not fall on. The date will be
    increased by a day until this condition is met
    """
    if schedule_frequency not in utils_FREQUENCY_TO_MONTHS_MAP:
        schedule_frequency = utils_DEFAULT_FREQUENCY
    number_of_months = utils_FREQUENCY_TO_MONTHS_MAP[schedule_frequency]
    next_date = localised_effective_date + timedelta(day=schedule_day_of_month)
    if next_date <= localised_effective_date or schedule_frequency != "monthly":
        next_date += timedelta(months=number_of_months, day=schedule_day_of_month)
    while utils_falls_on_calendar_events(vault, next_date, calendar_events):
        next_date += timedelta(days=1)
    return next_date


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


def utils_has_parameter_value_changed(
    parameter_name: str,
    old_parameters: dict[str, Parameter],
    updated_parameters: dict[str, Parameter],
) -> bool:
    """
    Determines if a parameter has changed. To be used within post-parameter change hook.

    :param parameter_name: str, name of the parameter
    :param old_parameters: dict, map of parameter name -> old parameter value
    :param updated_parameters: dict, map of parameter name -> new parameter value
    :return: bool, True if parameter value has changed, False otherwise
    """
    return (
        parameter_name in updated_parameters
        and old_parameters[parameter_name] != updated_parameters[parameter_name]
    )


def utils_validate_denomination(
    vault, postings: PostingInstructionBatch, accepted_denominations: Optional[Iterable[str]] = None
) -> Union[None, Rejected]:
    """
    Reject if any postings do not match accepted denominations.
    The denomination parameter is added to accepted_denominations.
    If no accepted_denominations are provided, then just the denomination parameter is used.
    """
    accepted_denominations_set = (
        set(accepted_denominations) if accepted_denominations is not None else set()
    )
    accepted_denominations_set.add(utils_get_parameter(vault, "denomination"))
    sorted_accepted_denominations = sorted(accepted_denominations_set)
    if any((post.denomination not in sorted_accepted_denominations for post in postings)):
        raise Rejected(
            f"Cannot make transactions in the given denomination, transactions must be one of {sorted_accepted_denominations}",
            reason_code=RejectedReason.WRONG_DENOMINATION,
        )


# Objects below have been imported from:
#    account_tiers.py
# md5:40544c79de16883e34a662517cea8d81

account_tiers_parameters = [
    Parameter(
        name="account_tier_names",
        level=Level.TEMPLATE,
        description="JSON encoded list of account tiers used as keys in map-type parameters. Flag definitions must be configured for each used tier. If the account is missing a flag the final tier in this list is used.",
        display_name="Tier names",
        shape=StringShape,
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=json_dumps(["STANDARD"]),
    )
]


def account_tiers_get_account_tier(vault) -> str:
    """
    Use the account tier flags to get a corresponding value from the account tiers list. If no
    recognised flags are present then the last value in account_tier_names will be used by default.
    If multiple flags are present then the nearest one to the start of account_tier_names will be
    used.
    :param vault: Vault object
    :return: account tier name assigned to account
    """
    account_tier_names = utils_get_parameter(vault, "account_tier_names", is_json=True)
    for tier_param in account_tier_names:
        if vault.get_flag_timeseries(flag=tier_param).latest():
            return tier_param
    return account_tier_names[-1]


# Objects below have been imported from:
#    early_closure_fee.py
# md5:b6c056143eed85bab7e6981a4b8d7cc2

early_closure_fee_DEFAULT_EARLY_CLOSURE_FEE_ADDRESS = "EARLY_CLOSURE_FEE"
early_closure_fee_parameters = [
    Parameter(
        name="early_closure_fee",
        level=Level.TEMPLATE,
        description="The fee charged if the account is closed early.",
        display_name="Early closure fee",
        shape=NumberShape(kind=NumberKind.MONEY, min_value=0, step=0.01),
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name="early_closure_days",
        level=Level.TEMPLATE,
        description="The number of days that must be completed in order to avoid an early closure  fee, should the account be closed.",
        display_name="Early closure days",
        shape=NumberShape(min_value=0, max_value=90, step=1),
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=90,
    ),
    Parameter(
        name="early_closure_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for early closure fee income balance.",
        display_name="Early closure fee income account",
        shape=AccountIdShape,
        default_value="EARLY_CLOSURE_FEE_INCOME",
    ),
]


def early_closure_fee_get_fees(
    vault,
    denomination: str,
    effective_date: datetime,
    early_closure_fee_address: str = early_closure_fee_DEFAULT_EARLY_CLOSURE_FEE_ADDRESS,
) -> list[PostingInstruction]:
    """
    Applies the early closure fee if account is closed within 'early_closure_days' number of days
    (midnight inclusive) and if the fee hasn't been applied already
    """
    creation_date = vault.get_account_creation_date()
    early_closure_fee = Decimal(utils_get_parameter(vault, "early_closure_fee"))
    early_closure_days = int(utils_get_parameter(vault, "early_closure_days"))
    early_closure_fee_income_account = utils_get_parameter(
        vault, "early_closure_fee_income_account"
    )
    instructions = []
    if not early_closure_fee > 0:
        return instructions
    early_closure_cut_off_date = creation_date + timedelta(days=early_closure_days)
    fee_has_not_been_charged_before = (
        vault.get_balance_timeseries()
        .latest()[
            early_closure_fee_DEFAULT_EARLY_CLOSURE_FEE_ADDRESS,
            DEFAULT_ASSET,
            denomination,
            Phase.COMMITTED,
        ]
        .debit
        == 0
    )
    if fee_has_not_been_charged_before and effective_date <= early_closure_cut_off_date:
        instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=early_closure_fee,
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=early_closure_fee_income_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"APPLY_EARLY_CLOSURE_FEE_{vault.get_hook_execution_id()}_{denomination}",
                instruction_details={
                    "description": "EARLY CLOSURE FEE",
                    "event": "CLOSE_ACCOUNT",
                    "account_type": "MURABAHAH",
                },
            )
        )
        instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=early_closure_fee,
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=early_closure_fee_address,
                to_account_id=vault.account_id,
                to_account_address=early_closure_fee_address,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"APPLY_EARLY_CLOSURE_FEE_{vault.get_hook_execution_id()}_{denomination}_TRACKER",
                instruction_details={
                    "description": "EARLY CLOSURE FEE",
                    "event": "CLOSE_ACCOUNT",
                    "account_type": "MURABAHAH",
                },
            )
        )
    return instructions


# Objects below have been imported from:
#    transaction_utils.py
# md5:19e0bb2d7bfd9f57e49ef5a0eba17598


def transaction_utils__does_posting_match_criteria(
    posting: PostingInstruction,
    credit: bool,
    denomination: str,
    cutoff_timestamp: datetime,
    asset: str,
    instruction_detail_key: str,
    instruction_detail_value: str,
) -> bool:
    posting_balances = posting.balances()
    total_net = 0
    for pb in posting_balances.values():
        total_net += pb.net
    is_credit = total_net >= 0
    return (
        credit == is_credit
        and posting.denomination == denomination
        and (posting.value_timestamp >= cutoff_timestamp)
        and (posting.asset == asset)
        and (posting.instruction_details.get(instruction_detail_key) == instruction_detail_value)
    )


def transaction_utils_withdrawals_by_instruction_detail(
    denomination: str,
    postings: PostingInstructionBatch,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    cutoff_timestamp: datetime,
    instruction_detail_key: str,
    instruction_detail_value: str,
) -> tuple[list[PostingInstruction], list[PostingInstruction]]:
    """
    Get all withdrawals for current transaction and previous transactions up to cutoff_timestamp.
    return: Tuple: (list of previous withdrawal, list of current withdrawals)
    """
    client_transaction_ids_in_current_batch = {
        posting.client_transaction_id for posting in postings
    }
    previous_withdrawals = []
    current_withdrawals = []
    for ((_, transaction_id), transaction) in client_transactions.items():
        for posting in transaction:
            if not transaction.cancelled and transaction_utils__does_posting_match_criteria(
                posting=posting,
                credit=False,
                denomination=denomination,
                cutoff_timestamp=cutoff_timestamp,
                asset=DEFAULT_ASSET,
                instruction_detail_key=instruction_detail_key,
                instruction_detail_value=instruction_detail_value,
            ):
                if transaction_id in client_transaction_ids_in_current_batch:
                    current_withdrawals.append(posting)
                else:
                    previous_withdrawals.append(posting)
    return (previous_withdrawals, current_withdrawals)


# Objects below have been imported from:
#    monthly_limit_by_payment_type.py
# md5:ed164a5ffecf6656225fbc3008828992

monthly_limit_by_payment_type_PAYMENT_TYPE = "PAYMENT_TYPE"
monthly_limit_by_payment_type_INTERNAL_POSTING = "INTERNAL_POSTING"
monthly_limit_by_payment_type_parameters = [
    Parameter(
        name="maximum_monthly_payment_type_withdrawal_limit",
        level=Level.TEMPLATE,
        description="Fees required when the payment type hits the monthly limit",
        display_name="Monthly payment type withdrawal limit fees",
        shape=StringShape,
        default_value=json_dumps({"ATM": {"fee": "0.50", "limit": "8"}}),
    )
]


def monthly_limit_by_payment_type_get_fees(
    vault,
    postings: PostingInstructionBatch,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    effective_date: datetime,
    denomination: str,
) -> list[PostingInstruction]:
    """
    Check posting instruction details for PAYMENT_TYPE key and return any fees associated with that
    payment type. The fee is credited to the account defined by the payment_type_fee_income_account
    parameter.
    """
    maximum_monthly_payment_type_withdrawal_limit = utils_get_parameter(
        vault, "maximum_monthly_payment_type_withdrawal_limit", is_json=True
    )
    payment_type_fee_income_account = utils_get_parameter(vault, "payment_type_fee_income_account")
    start_of_monthly_window = effective_date.replace(day=1, hour=0, minute=0, second=0)
    posting_instructions = []
    total_fees_by_payment_type = {}
    for payment_type in maximum_monthly_payment_type_withdrawal_limit.keys():
        (
            previous_withdrawals,
            current_withdrawals,
        ) = transaction_utils_withdrawals_by_instruction_detail(
            denomination=denomination,
            postings=postings,
            client_transactions=client_transactions,
            cutoff_timestamp=start_of_monthly_window,
            instruction_detail_key=monthly_limit_by_payment_type_PAYMENT_TYPE,
            instruction_detail_value=payment_type,
        )
        current_payment_type_dict = maximum_monthly_payment_type_withdrawal_limit[payment_type]
        current_payment_type_fee = Decimal(current_payment_type_dict["fee"])
        current_payment_type_limit = Decimal(current_payment_type_dict["limit"])
        num_fees_to_incur = 0
        total_no_of_withdrawals = len(previous_withdrawals) + len(current_withdrawals)
        exceed_limit = total_no_of_withdrawals - current_payment_type_limit
        if exceed_limit > 0:
            num_fees_to_incur = min(exceed_limit, len(current_withdrawals))
        total_fee = num_fees_to_incur * current_payment_type_fee
        total_fees_by_payment_type.update({payment_type: total_fee})
    instruction_detail = "Total fees charged for limits on payment types: "
    instruction_detail += ",".join(
        [
            fee_by_type[0] + " " + str(fee_by_type[1]) + " " + denomination
            for fee_by_type in total_fees_by_payment_type.items()
        ]
    )
    total_fee = sum(total_fees_by_payment_type.values())
    if total_fee > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=total_fee,
                denomination=denomination,
                client_transaction_id=f"{monthly_limit_by_payment_type_INTERNAL_POSTING}_APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES_{vault.get_hook_execution_id()}",
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=payment_type_fee_income_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                instruction_details={
                    "description": instruction_detail,
                    "event": "APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
                },
            )
        )
    return posting_instructions


# Objects below have been imported from:
#    payment_type_flat_fee.py
# md5:5477ec5f9fa032908123434ec09aadfd

payment_type_flat_fee_PAYMENT_TYPE = "PAYMENT_TYPE"
payment_type_flat_fee_INTERNAL_POSTING = "INTERNAL_POSTING"
payment_type_flat_fee_parameters = [
    Parameter(
        name="payment_type_flat_fee",
        level=Level.TEMPLATE,
        description="The flat fees to apply for a given payment type.",
        display_name="Payment type flat fees",
        shape=StringShape,
        default_value=json_dumps({"ATM": "1"}),
    )
]


def payment_type_flat_fee_get_fees(
    vault, postings: PostingInstructionBatch, denomination: str
) -> list[PostingInstruction]:
    """
    Check posting instruction details for PAYMENT_TYPE key and return any fees associated with that
    payment type. The fee is credited to the account defined by the payment_type_fee_income_account
    parameter.
    """
    payment_type_flat_fees = utils_get_parameter(vault, "payment_type_flat_fee", is_json=True)
    payment_type_fee_income_account = utils_get_parameter(vault, "payment_type_fee_income_account")
    posting_instructions = []
    for posting in postings:
        posting_balances = posting.balances()
        posting_withdrawal_amount = (
            posting_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
            + posting_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT].net
        )
        if posting_withdrawal_amount >= 0:
            continue
        current_payment_type = posting.instruction_details.get(payment_type_flat_fee_PAYMENT_TYPE)
        if not current_payment_type or current_payment_type not in payment_type_flat_fees:
            continue
        payment_type_fee = Decimal(payment_type_flat_fees[current_payment_type])
        if payment_type_fee > 0:
            posting_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=payment_type_fee,
                    denomination=denomination,
                    client_transaction_id=f"{payment_type_flat_fee_INTERNAL_POSTING}_APPLY_PAYMENT_TYPE_FLAT_FEE_FOR_{current_payment_type}_{vault.get_hook_execution_id()}",
                    from_account_id=vault.account_id,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=payment_type_fee_income_account,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": f"payment fee applied for withdrawal using {current_payment_type}",
                        "payment_type": f"{current_payment_type}",
                        "event": "APPLY_PAYMENT_TYPE_FLAT_FEE",
                    },
                )
            )
    return posting_instructions


# Objects below have been imported from:
#    payment_type_threshold_fee.py
# md5:61a45e3924613437a74ceefd8ffb08ac

payment_type_threshold_fee_PAYMENT_TYPE = "PAYMENT_TYPE"
payment_type_threshold_fee_INTERNAL_POSTING = "INTERNAL_POSTING"
payment_type_threshold_fee_parameters = [
    Parameter(
        name="payment_type_threshold_fee",
        level=Level.TEMPLATE,
        description="Fees require when the payment amount hit the threshold for the payment type",
        display_name="Payment type threshold fee",
        shape=StringShape,
        default_value=json_dumps({"ATM": {"fee": "0.15", "threshold": "5000"}}),
    )
]


def payment_type_threshold_fee_get_fees(
    vault, postings: PostingInstructionBatch, denomination: str
) -> list[PostingInstruction]:
    """
    Check posting instruction details for PAYMENT_TYPE key and return any fees associated with that
    payment type if the posting value breaches the associated limit. The fee is credited to the
    account defined by the payment_type_fee_income_account parameter.
    """
    payment_type_threshold_fee_param = utils_get_parameter(
        vault, "payment_type_threshold_fee", is_json=True
    )
    payment_type_fee_income_account = utils_get_parameter(vault, "payment_type_fee_income_account")
    posting_instructions = []
    for posting in postings:
        current_payment_type = posting.instruction_details.get(
            payment_type_threshold_fee_PAYMENT_TYPE
        )
        if not current_payment_type or current_payment_type not in payment_type_threshold_fee_param:
            continue
        current_payment_type_dict = payment_type_threshold_fee_param[current_payment_type]
        payment_type_fee = Decimal(current_payment_type_dict["fee"])
        payment_type_threshold = Decimal(current_payment_type_dict["threshold"])
        posting_balances = posting.balances()
        available_balance_delta = (
            posting_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
            + posting_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT].net
        )
        if -payment_type_threshold > available_balance_delta:
            posting_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=payment_type_fee,
                    denomination=denomination,
                    client_transaction_id=f"{payment_type_threshold_fee_INTERNAL_POSTING}_APPLY_PAYMENT_TYPE_THRESHOLD_FEE_FOR_{current_payment_type}_{vault.get_hook_execution_id()}",
                    from_account_id=vault.account_id,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=payment_type_fee_income_account,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": f"payment fee on withdrawal more than {payment_type_threshold} for payment using {current_payment_type}",
                        "payment_type": f"{current_payment_type}",
                        "event": "APPLY_PAYMENT_TYPE_THRESHOLD_FEE",
                    },
                )
            )
    return posting_instructions


# Objects below have been imported from:
#    maximum_balance_limit.py
# md5:a30277a204a50aa87e7d2916459c42a5

maximum_balance_limit_MAXIMUM_BALANCE_PARAM = "maximum_balance"
maximum_balance_limit_parameters = [
    Parameter(
        name="maximum_balance",
        level=Level.TEMPLATE,
        description="The maximum deposited balance amount for the account. Deposits that breach this amount will be rejected.",
        display_name="Maximum balance amount",
        shape=utils_LimitHundredthsShape,
        default_value=Decimal("10000"),
    )
]


def maximum_balance_limit_validate(
    vault, postings: PostingInstructionBatch, balances: BalanceDefaultDict, denomination: str
):
    """
    Reject the posting if the deposit will cause the current balance to exceed the maximum
    permitted balance.
    """
    current_balance = (
        balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
        + balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN].net
    )
    postings_balances = postings.balances()
    deposit_proposed_amount = (
        postings_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
        + postings_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN].net
    )
    maximum_balance = utils_get_parameter(vault, maximum_balance_limit_MAXIMUM_BALANCE_PARAM)
    if maximum_balance is not None and current_balance + deposit_proposed_amount > maximum_balance:
        raise Rejected(
            f"Posting would exceed maximum permitted balance {maximum_balance} {denomination}.",
            reason_code=RejectedReason.AGAINST_TNC,
        )


# Objects below have been imported from:
#    utils.py
# md5:68d6ae4edbec13ca65bdeef59b87dbe9


def utils_sum_client_transactions(
    denomination: str,
    cutoff_timestamp: datetime,
    client_transactions: dict[tuple[str, str], ClientTransaction],
) -> tuple[Decimal, Decimal]:
    """
    Sum all transactions in client_transactions since a given cutoff point.
    Chainable transactions should be considered to ensure no duplicate counting.
    :param denomination: denomination
    :param cutoff_timestamp: used to scope which transactions should be considered for summing
    :param client_transactions: keyed by (client_id, client_transaction_id)
    :return: Sum of deposits, sum of withdrawals for given client transactions. Both values are
             returned as positive integers (or 0).
    """
    amount_withdrawn = Decimal(0)
    amount_deposited = Decimal(0)
    for transaction in client_transactions.values():
        transaction_amount = utils__get_total_transaction_impact(transaction, denomination)
        cutoff_timestamp -= timedelta(microseconds=1)
        amount_before_cutoff = utils__get_total_transaction_impact(
            transaction, denomination, cutoff_timestamp
        )
        amount = transaction_amount - amount_before_cutoff
        if amount > 0:
            amount_deposited += amount
        else:
            amount_withdrawn += abs(amount)
    return (amount_deposited, amount_withdrawn)


def utils_sum_withdrawals_by_instruction_details_key_for_day(
    denomination: str,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    client_transaction_id: str,
    cutoff_timestamp: datetime,
    key: str,
    value: str,
) -> Decimal:
    """
    Sum all withdrawals/payment of a type for default address in client_transactions since
    cutoff, excluding any cancelled or the current transaction.
    Return amount withdrawn/pay from the type since cutoff.
    :param denomination: denomination
    :param client_transactions: keyed by (client_id, client_transaction_id)
    :param client_transaction_id: the client_transaction_id for current posting
    :param cutoff_timestamp: the to cut off for client transaction
    :param key: key to reference in the instruction details
    :param value: value to lookup against the key in the instruction details
    :return: Sum of transactions of a payment type, which is -ve for withdrawals/payment
    """

    def _is_same_payment_type_today(posting):
        return (
            not posting.credit
            and posting.denomination == denomination
            and (posting.value_timestamp >= cutoff_timestamp)
            and (posting.asset == DEFAULT_ASSET)
            and (posting.instruction_details.get(key) == value)
        )

    return -sum(
        (
            sum((posting.amount for posting in transaction if _is_same_payment_type_today(posting)))
            for ((_, transaction_id), transaction) in client_transactions.items()
            if transaction_id != client_transaction_id and (not transaction.cancelled)
        )
    )


def utils__get_total_transaction_impact(
    transaction: ClientTransaction,
    denomination: str,
    timestamp: datetime = None,
    address: str = DEFAULT_ADDRESS,
    asset: str = DEFAULT_ASSET,
) -> Decimal:
    """
    For any financial movement, the total effect a ClientTransaction
    has had on the balances can be represents by the sum of
    settled and unsettled .effects.

    1. HardSettlement (-10):
        authorised: 0, settled: -10, unsettled: 0, released: 0
        sum = -10
    2. Authorisation (-10)
        authorisation:  authorised: -10, settled: 0, unsettled: -10, released: 0
        sum = -10
    3. Authorisation (-10) + Adjustment (-5)
        authorisation:  authorised: -10, settled: 0, unsettled: -10, released: 0
        adjustment:     authorised: -15, settled: 0, unsettled: -15, released: 0
        sum = -15
    4. Authorisation (-10) + Total Settlement (-10)
        authorisation: authorised: -10, settled: 0, unsettled: -10, released: 0
        settlement:    authorised: -10, settled: -10, unsettled: 0, released: 0
        sum = -10
    5. Authorisation (-10) + Partial Settlement Non-final (-5)
        authorisation: authorised: -10, settled: 0, unsettled: -10, released: 0
        settlement:    authorised: -10, settled: -5, unsettled: -5, released: 0
        # if the settlement was not final, then the total effect of the transaction
        # is the value of the initial auth.
        sum = -10
    6. Authorisation (-10) + Partial Settlement Final (-5)
        authorisation: authorised: -10, settled: 0, unsettled: -10, released: 0
        settlement:    authorised: -5, settled: -5, unsettled: 0, released: -5
        # as the settlement was final, the remaining funds were released. The impact
        # of this transaction is therefore only -5, i.e. even though the original auth
        # was -10, -5 of that was returned.
        sum = -5
    7. Authorisation (-10) + Oversettlement (auth -10 & an additional -5)
        authorisation: authorised: -10, settled: 0, unsettled: -10, released: 0
        settlement:    authorised: -10, settled: -15, unsettled: 0, released: 0
        # as an oversettlement has occured, the impact on the account is the
        # the settlement amount of -15
        sum = -15
    8. Authorisation (-10) + Release (-10)
        authorisation: authorised: -10, settled: 0, unsettled: -10, released: 0
        release:       authorised: -10, settled: 0, unsettled: 0, released: -10
        # as we have released all funds then this is expected to be 0, i.e. the
        # transaction has no overall impact on an account,
        sum = 0

    :param: transaction:
    :param denomination: denomination of the transaction
    :param timestamp: timestamp to determine which point of time to
    :param address: balance address
    :param asset: balance asset
    :return: The net of settled and unsettled effects.
    """
    amount = (
        transaction.effects(timestamp=timestamp)[address, asset, denomination].settled
        + transaction.effects(timestamp=timestamp)[address, asset, denomination].unsettled
    )
    return amount


# Objects below have been imported from:
#    maximum_daily_deposit.py
# md5:0356616950b0b2ae5ae61289f22385d6

maximum_daily_deposit_MAX_DAILY_DEPOSIT_PARAM = "maximum_daily_deposit"
maximum_daily_deposit_parameters = [
    Parameter(
        name=maximum_daily_deposit_MAX_DAILY_DEPOSIT_PARAM,
        level=Level.TEMPLATE,
        description="The maximum amount which can be consecutively deposited into the account over a given 24hr window.",
        display_name="Maximum daily deposit amount",
        shape=utils_LimitHundredthsShape,
        default_value=Decimal("10000"),
    )
]


def maximum_daily_deposit_validate(
    vault,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    client_transactions_excluding_proposed: dict[tuple[str, str], ClientTransaction],
    effective_date: datetime,
    denomination: str,
    net_batch: bool = False,
):
    """
    Reject the posting if it would cause the maximum daily deposit limit to be breached.
    If net_batch = False, only deposits in the batch will be considered when accepting/rejecting.
    If net_batch = True, the net of all postings in the batch is considered when determining
    accept/reject meaning if the net of the batch is negative, this will always be accepted
    even if the sum of deposits has exceeded the limit.
    """
    max_daily_deposit = utils_get_parameter(vault, maximum_daily_deposit_MAX_DAILY_DEPOSIT_PARAM)
    (amount_deposited_actual, amount_withdrawn_actual) = utils_sum_client_transactions(
        denomination=denomination,
        cutoff_timestamp=datetime.combine(effective_date, datetime.min.time()),
        client_transactions=client_transactions_excluding_proposed,
    )
    (amount_deposited_proposed, amount_withdrawn_proposed) = utils_sum_client_transactions(
        denomination=denomination,
        cutoff_timestamp=datetime.combine(effective_date, datetime.min.time()),
        client_transactions=client_transactions,
    )
    posting_batch_deposited = amount_deposited_proposed - amount_deposited_actual
    posting_batch_withdrawn = amount_withdrawn_proposed - amount_withdrawn_actual
    if posting_batch_deposited == 0:
        return
    if net_batch and posting_batch_withdrawn >= posting_batch_deposited:
        return
    deposit_daily_spend = posting_batch_deposited + amount_deposited_actual
    if net_batch:
        deposit_daily_spend -= posting_batch_withdrawn
    if deposit_daily_spend > max_daily_deposit:
        raise Rejected(
            "PIB would cause the maximum daily deposit limit of %s %s to be exceeded."
            % (max_daily_deposit, denomination),
            reason_code=RejectedReason.AGAINST_TNC,
        )


# Objects below have been imported from:
#    maximum_single_deposit.py
# md5:35929991a55f7806799d513fb55b7234

maximum_single_deposit_MAX_DEPOSIT_PARAM = "maximum_deposit"
maximum_single_deposit_parameters = [
    Parameter(
        name=maximum_single_deposit_MAX_DEPOSIT_PARAM,
        level=Level.TEMPLATE,
        description="The maximum amount that can be deposited into the account in a single transaction.",
        display_name="Maximum deposit amount",
        shape=utils_LimitHundredthsShape,
        default_value=Decimal("1000"),
    )
]


def maximum_single_deposit_validate(vault, postings: PostingInstructionBatch, denomination: str):
    """
    Reject the posting if the value is greater than the maximum allowed deposit.
    """
    max_deposit = utils_get_parameter(vault, maximum_single_deposit_MAX_DEPOSIT_PARAM)
    for posting in postings:
        posting_balances = posting.balances()
        deposit_value = (
            posting_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
            + posting_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN].net
        )
        if deposit_value > 0 and max_deposit is not None and (deposit_value > max_deposit):
            raise Rejected(
                f"Transaction amount {deposit_value} {denomination} is more than the maximum permitted deposit amount {max_deposit} {denomination}.",
                reason_code=RejectedReason.AGAINST_TNC,
            )


# Objects below have been imported from:
#    minimum_initial_deposit.py
# md5:f9ee10c2fb779f14b8753311de4ff146

minimum_initial_deposit_MIN_INITIAL_DEPOSIT_PARAM = "minimum_initial_deposit"
minimum_initial_deposit_parameters = [
    Parameter(
        name=minimum_initial_deposit_MIN_INITIAL_DEPOSIT_PARAM,
        level=Level.TEMPLATE,
        description="The minimun amount for the first deposit to the account",
        display_name="Minimum initial deposit",
        shape=utils_MoneyShape,
        default_value=Decimal("20.00"),
    )
]


def minimum_initial_deposit_validate(
    vault, postings: PostingInstructionBatch, balances: BalanceDefaultDict, denomination: str
):
    """
    Reject the posting if it does not meet the initial minimum deposit limit.
    """
    min_initial_deposit = utils_get_parameter(
        vault, minimum_initial_deposit_MIN_INITIAL_DEPOSIT_PARAM
    )
    available_balance = (
        balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
        + balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT].net
    )
    for posting in postings:
        posting_balances = posting.balances()
        deposit_value = (
            posting_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
            + posting_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN].net
        )
        if (
            min_initial_deposit is not None
            and available_balance == 0
            and (0 < deposit_value < min_initial_deposit)
        ):
            raise Rejected(
                f"Transaction amount {deposit_value:0.2f} {denomination} is less than the minimum initial deposit amount {min_initial_deposit:0.2f} {denomination}.",
                reason_code=RejectedReason.AGAINST_TNC,
            )


# Objects below have been imported from:
#    minimum_single_deposit.py
# md5:a231229daa836016bc9c12bb110edf28

minimum_single_deposit_MIN_DEPOSIT_PARAM = "minimum_deposit"
minimum_single_deposit_parameters = [
    Parameter(
        name="minimum_deposit",
        level=Level.TEMPLATE,
        description="The minimum amount that can be deposited into the account in a single transaction.",
        display_name="Minimum deposit amount",
        shape=utils_MoneyShape,
        default_value=Decimal("0.01"),
    )
]


def minimum_single_deposit_validate(vault, postings: PostingInstructionBatch, denomination: str):
    """
    Reject if the deposit amount does not meet the minimum deposit limit.
    """
    minimum_deposit = utils_get_parameter(vault, minimum_single_deposit_MIN_DEPOSIT_PARAM)
    for posting in postings:
        posting_balances = posting.balances()
        deposit_value = (
            posting_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
            + posting_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN].net
        )
        if minimum_deposit is not None and 0 < deposit_value < minimum_deposit:
            deposit_value = utils_round_decimal(deposit_value, 5)
            minimum_deposit = utils_round_decimal(minimum_deposit, 5)
            raise Rejected(
                f"Transaction amount {utils_remove_exponent(deposit_value)} {denomination} is less than the minimum deposit amount {utils_remove_exponent(minimum_deposit)} {denomination}.",
                reason_code=RejectedReason.AGAINST_TNC,
            )


# Objects below have been imported from:
#    maximum_daily_withdrawal.py
# md5:5df8e830976a6baec311b185c477896e

maximum_daily_withdrawal_MAX_DAILY_WITHDRAWAL_PARAM = "maximum_daily_withdrawal"
maximum_daily_withdrawal_parameters = [
    Parameter(
        name=maximum_daily_withdrawal_MAX_DAILY_WITHDRAWAL_PARAM,
        level=Level.TEMPLATE,
        description="The maximum amount that can be consecutively withdrawn from an account over a given 24hr window.",
        display_name="Maximum daily withdrawal amount",
        shape=utils_LimitHundredthsShape,
        default_value=Decimal("1000"),
    )
]


def maximum_daily_withdrawal_validate(
    vault,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    client_transactions_excluding_proposed: dict[tuple[str, str], ClientTransaction],
    effective_date: datetime,
    denomination: str,
    net_batch: bool = False,
):
    """
    Reject the posting if it would cause the maximum daily withdrawal limit to be breached.
    If net_batch = False, only withdrawals in the batch will be considered when accepting/rejecting.
    If net_batch = True, the net of all postings in the batch is considered when determining
    accept/reject meaning if the net of the batch is positive, this will always be accepted
    even if the sum of withdrawals has exceeded the limit.
    """
    max_daily_withdrawal = utils_get_parameter(
        vault, maximum_daily_withdrawal_MAX_DAILY_WITHDRAWAL_PARAM
    )
    (amount_deposited_actual, amount_withdrawn_actual) = utils_sum_client_transactions(
        denomination=denomination,
        cutoff_timestamp=datetime.combine(effective_date, datetime.min.time()),
        client_transactions=client_transactions_excluding_proposed,
    )
    (amount_deposited_proposed, amount_withdrawn_proposed) = utils_sum_client_transactions(
        denomination=denomination,
        cutoff_timestamp=datetime.combine(effective_date, datetime.min.time()),
        client_transactions=client_transactions,
    )
    posting_batch_deposited = amount_deposited_proposed - amount_deposited_actual
    posting_batch_withdrawn = amount_withdrawn_proposed - amount_withdrawn_actual
    if posting_batch_withdrawn == 0:
        return
    if net_batch and posting_batch_deposited >= posting_batch_withdrawn:
        return
    withdrawal_daily_spend = posting_batch_withdrawn + amount_withdrawn_actual
    if net_batch:
        withdrawal_daily_spend -= posting_batch_deposited
    if withdrawal_daily_spend > max_daily_withdrawal:
        raise Rejected(
            "PIB would cause the maximum daily withdrawal limit of %s %s to be exceeded."
            % (max_daily_withdrawal, denomination),
            reason_code=RejectedReason.AGAINST_TNC,
        )


# Objects below have been imported from:
#    maximum_daily_withdrawal_by_category.py
# md5:2f3398324743edc03b452aff5af87f2b


def maximum_daily_withdrawal_by_category_validate(
    limit_mapping: dict[str, str],
    instruction_detail_key: str,
    postings: PostingInstructionBatch,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    effective_date: datetime,
    denomination: str,
):
    """
    Reject the posting if it would cause the maximum daily withdrawal limit to be breached.
    """
    for posting in postings:
        instruction_detail_key_value = posting.instruction_details.get(instruction_detail_key)
        if not instruction_detail_key_value or instruction_detail_key_value not in limit_mapping:
            continue
        limit = Decimal(limit_mapping[instruction_detail_key_value])
        client_transaction = client_transactions.get(
            (posting.client_id, posting.client_transaction_id)
        )
        amount_authed = max(
            abs(
                client_transaction.effects()[
                    DEFAULT_ADDRESS, DEFAULT_ASSET, denomination
                ].authorised
                - client_transaction.effects()[
                    DEFAULT_ADDRESS, DEFAULT_ASSET, denomination
                ].released
            ),
            abs(client_transaction.effects()[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination].settled),
        )
        amount_withdrawn = utils_sum_withdrawals_by_instruction_details_key_for_day(
            denomination,
            client_transactions,
            posting.client_transaction_id,
            datetime.combine(effective_date, datetime.min.time()),
            instruction_detail_key,
            instruction_detail_key_value,
        )
        if not posting.credit and amount_authed - amount_withdrawn > limit:
            raise Rejected(
                f"Transaction would cause the maximum {instruction_detail_key_value} payment limit of {limit} {denomination} to be exceeded.",
                reason_code=RejectedReason.AGAINST_TNC,
            )


# Objects below have been imported from:
#    maximum_single_withdrawal.py
# md5:cc70d67bcd0d9a5546a1638edc9d55f0

maximum_single_withdrawal_MAX_WITHDRAWAL_PARAM = "maximum_withdrawal"
maximum_single_withdrawal_parameters = [
    Parameter(
        name=maximum_single_withdrawal_MAX_WITHDRAWAL_PARAM,
        level=Level.TEMPLATE,
        description="The maximum amount that can be withdrawn from the account in a single transaction.",
        display_name="Maximum withdrawal amount",
        shape=utils_LimitHundredthsShape,
        default_value=Decimal("10000"),
    )
]


def maximum_single_withdrawal_validate(vault, postings: PostingInstructionBatch, denomination: str):
    """
    Reject if any posting amount is greater than the maximum allowed withdrawal limit.
    """
    max_withdrawal = utils_get_parameter(vault, maximum_single_withdrawal_MAX_WITHDRAWAL_PARAM)
    for posting in postings:
        posting_balances = posting.balances()
        posting_value = (
            posting_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
            + posting_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT].net
        )
        if max_withdrawal is not None and posting_value < -max_withdrawal:
            raise Rejected(
                f"Transaction amount {abs(posting_value)} {denomination} is greater than the maximum withdrawal amount {max_withdrawal} {denomination}.",
                reason_code=RejectedReason.AGAINST_TNC,
            )


# Objects below have been imported from:
#    maximum_withdrawal_by_payment_type.py
# md5:146f226f87b6a5e30b9c467c8f7ee808

maximum_withdrawal_by_payment_type_PAYMENT_TYPE = "PAYMENT_TYPE"
maximum_withdrawal_by_payment_type_MAX_WITHDRAWAL_BY_TYPE_PARAM = "maximum_payment_type_withdrawal"
maximum_withdrawal_by_payment_type_parameters = [
    Parameter(
        name=maximum_withdrawal_by_payment_type_MAX_WITHDRAWAL_BY_TYPE_PARAM,
        level=Level.TEMPLATE,
        description="The maximum single withdrawal allowed for each payment type.",
        display_name="Payment type limits",
        shape=StringShape,
        default_value=json_dumps({"ATM": "30000"}),
    )
]


def maximum_withdrawal_by_payment_type_validate(
    vault, postings: PostingInstructionBatch, denomination: str
):
    """
    Reject the posting if the withdrawal value exceeds the PAYMENT_TYPE limit.
    """
    max_withdrawal_by_payment_type = utils_get_parameter(
        vault, maximum_withdrawal_by_payment_type_MAX_WITHDRAWAL_BY_TYPE_PARAM, is_json=True
    )
    for posting in postings:
        payment_type = posting.instruction_details.get(
            maximum_withdrawal_by_payment_type_PAYMENT_TYPE
        )
        if payment_type and payment_type in max_withdrawal_by_payment_type:
            withdrawal_limit = Decimal(max_withdrawal_by_payment_type[payment_type])
            posting_balances = posting.balances()
            posting_value = (
                posting_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
                + posting_balances[
                    DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT
                ].net
            )
            if posting_value < 0 and withdrawal_limit < abs(posting_value):
                raise Rejected(
                    f"Transaction amount {abs(posting_value):0.2f} {denomination} is more than the maximum withdrawal amount {withdrawal_limit} {denomination} allowed for the the payment type {payment_type}.",
                    reason_code=RejectedReason.AGAINST_TNC,
                )


# Objects below have been imported from:
#    minimum_balance_by_tier.py
# md5:a743a4187f5741757314abd8962b5c7f

minimum_balance_by_tier_MIN_BALANCE_THRESHOLD_PARAM = "tiered_minimum_balance_threshold"
minimum_balance_by_tier_parameters = [
    Parameter(
        name=minimum_balance_by_tier_MIN_BALANCE_THRESHOLD_PARAM,
        level=Level.TEMPLATE,
        description="The minimum balance allowed for each account tier.",
        display_name="Minimum balance threshold",
        shape=StringShape,
        default_value=json_dumps({"STANDARD": "10"}),
    )
]


def minimum_balance_by_tier_validate(
    vault, postings: PostingInstructionBatch, balances: BalanceDefaultDict, denomination: str
):
    """
    Reject if the net value of the posting instruction batch results in the account balance falling
    below the minimum threshold for the account tier.
    """
    available_balance = (
        balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
        + balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT].net
    )
    postings_balances = postings.balances()
    proposed_amount = (
        postings_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
        + postings_balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT].net
    )
    min_balance_threshold_by_tier = utils_get_parameter(
        vault, minimum_balance_by_tier_MIN_BALANCE_THRESHOLD_PARAM, is_json=True
    )
    current_account_tier = account_tiers_get_account_tier(vault)
    min_balance = Decimal(min_balance_threshold_by_tier[current_account_tier])
    if available_balance + proposed_amount < min_balance:
        raise Rejected(
            f"Transaction amount {proposed_amount} {denomination} will result in the account balance falling below the minimum permitted of {min_balance} {denomination}.",
            reason_code=RejectedReason.AGAINST_TNC,
        )


# Objects below have been imported from:
#    profit_accrual.py
# md5:44e2b11d19a255f17087b81958a32adc

profit_accrual_ACCRUAL_EVENT = "ACCRUE_PROFIT"
profit_accrual_ACCRUAL_APPLICATION_EVENT = "APPLY_ACCRUED_PROFIT"
profit_accrual_ACCRUED_PROFIT_PAYABLE_ADDRESS = "ACCRUED_PROFIT_PAYABLE"
profit_accrual_parameters = [
    Parameter(
        name="profit_application_day",
        level=Level.INSTANCE,
        description="The day of the month on which profit is applied. If day does not exist in application month, applies on last day of month.",
        display_name="Profit application day",
        shape=NumberShape(min_value=1, max_value=31, step=1),
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name="profit_accrual_hour",
        level=Level.TEMPLATE,
        description="The hour of the day at which profit is accrued.",
        display_name="Profit accrual hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=1,
    ),
    Parameter(
        name="profit_accrual_minute",
        level=Level.TEMPLATE,
        description="The minute of the hour at which profit is accrued.",
        display_name="Profit accrual minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name="profit_accrual_second",
        level=Level.TEMPLATE,
        description="The second of the minute at which profit is accrued.",
        display_name="Profit accrual second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name="profit_application_hour",
        level=Level.TEMPLATE,
        description="The hour of the day at which profit is applied.",
        display_name="Profit application hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        default_value=1,
    ),
    Parameter(
        name="profit_application_minute",
        level=Level.TEMPLATE,
        description="The minute of the hour at which profit is applied.",
        display_name="Profit application minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=5,
    ),
    Parameter(
        name="profit_application_second",
        level=Level.TEMPLATE,
        description="The second of the minute at which profit is applied.",
        display_name="Profit application second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        default_value=0,
    ),
    Parameter(
        name="profit_application_frequency",
        level=Level.TEMPLATE,
        description='The frequency at which deposit profit is applied to deposits in the main denomination. Valid values are "monthly", "quarterly", "annually".',
        display_name="Profit application frequency",
        shape=UnionShape(
            UnionItem(key="monthly", display_name="Monthly"),
            UnionItem(key="quarterly", display_name="Quarterly"),
            UnionItem(key="annually", display_name="Annually"),
        ),
        default_value=UnionItemValue(key="monthly"),
    ),
    Parameter(
        name="accrued_profit_payable_account",
        level=Level.TEMPLATE,
        description="Internal account for accrued profit payable balance.",
        display_name="Accrued profit payable account",
        shape=AccountIdShape,
        default_value="ACCRUED_PROFIT_PAYABLE",
    ),
    Parameter(
        name="profit_paid_account",
        level=Level.TEMPLATE,
        description="Internal account for profit paid balance.",
        display_name="Profit paid account",
        shape=AccountIdShape,
        default_value="PROFIT_PAID",
    ),
]


def profit_accrual_get_event_types(product_name):
    accrual_tags = [f"{product_name}_ACCRUE_PROFIT_AST"]
    apply_tag = [f"{product_name}_APPLY_ACCRUED_PROFIT_AST"]
    return [
        EventType(name=profit_accrual_ACCRUAL_EVENT, scheduler_tag_ids=accrual_tags),
        EventType(name=profit_accrual_ACCRUAL_APPLICATION_EVENT, scheduler_tag_ids=apply_tag),
    ]


def profit_accrual_get_execution_schedules(vault) -> list[tuple[str, dict[str, str]]]:
    account_creation_date = vault.get_account_creation_date()
    accrue_profit_schedule = utils_get_daily_schedule(
        vault, "profit_accrual", profit_accrual_ACCRUAL_EVENT
    )
    apply_accrued_profit_schedule = profit_accrual_get_next_apply_accrued_profit_schedule(
        vault, account_creation_date
    )
    return [accrue_profit_schedule, apply_accrued_profit_schedule]


def profit_accrual_get_accrual_posting_instructions(
    vault,
    effective_date: datetime,
    denomination: str,
    accrual_formula: NamedTuple,
    capital_address: str = DEFAULT_ADDRESS,
) -> list[PostingInstruction]:
    posting_instructions = []
    accrued_profit_payable_account = utils_get_parameter(vault, "accrued_profit_payable_account")
    profit_paid_account = utils_get_parameter(vault, "profit_paid_account")
    accrual_capital = profit_accrual__get_accrual_capital(
        vault, effective_date, denomination, capital_address
    )
    amount_to_accrue = accrual_formula.calculate(
        vault, accrual_capital, effective_date=effective_date
    )
    if amount_to_accrue > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=amount_to_accrue,
                denomination=denomination,
                client_transaction_id=f"INTERNAL_POSTING_ACCRUE_PROFIT_{vault.get_hook_execution_id()}_INTERNAL",
                from_account_id=profit_paid_account,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=accrued_profit_payable_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": f"Daily profit accrued on balance of {accrual_capital}",
                    "event": "ACCRUE_PROFIT",
                    "account_type": "MURABAHAH",
                },
            )
        )
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=amount_to_accrue,
                denomination=denomination,
                client_transaction_id=f"INTERNAL_POSTING_ACCRUE_PROFIT_{vault.get_hook_execution_id()}_CUSTOMER",
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=profit_accrual_ACCRUED_PROFIT_PAYABLE_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": f"Daily profit accrued on balance of {accrual_capital}",
                    "event": profit_accrual_ACCRUAL_EVENT,
                    "account_type": "MURABAHAH",
                },
            )
        )
    return posting_instructions


def profit_accrual_get_apply_accrual_posting_instructions(
    vault, effective_date: datetime, denomination: str
) -> list[PostingInstruction]:
    accrued_profit_payable_account = utils_get_parameter(vault, "accrued_profit_payable_account")
    accrued_profit_raw_payable = utils_get_balance_sum(
        vault,
        [profit_accrual_ACCRUED_PROFIT_PAYABLE_ADDRESS],
        denomination=denomination,
        timestamp=effective_date,
    )
    accrued_profit_rounded = utils_round_decimal(
        accrued_profit_raw_payable, decimal_places=2, rounding=ROUND_DOWN
    )
    posting_instructions = []
    if accrued_profit_rounded > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=accrued_profit_rounded,
                denomination=denomination,
                from_account_id=accrued_profit_payable_account,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=vault.account_id,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"INTERNAL_POSTING_APPLY_ACCRUED_PROFIT_{vault.get_hook_execution_id()}_{denomination}_INTERNAL",
                instruction_details={
                    "description": "Profit Applied",
                    "event": profit_accrual_ACCRUAL_APPLICATION_EVENT,
                    "account_type": "MURABAHAH",
                },
            )
        )
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(accrued_profit_rounded),
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=profit_accrual_ACCRUED_PROFIT_PAYABLE_ADDRESS,
                to_account_id=vault.account_id,
                to_account_address=INTERNAL_CONTRA,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"INTERNAL_POSTING_APPLY_ACCRUED_PROFIT_{vault.get_hook_execution_id()}_{denomination}_CUSTOMER",
                instruction_details={
                    "description": "Profit Applied",
                    "event": profit_accrual_ACCRUAL_APPLICATION_EVENT,
                    "account_type": "MURABAHAH",
                },
            )
        )
    remainder = accrued_profit_raw_payable - accrued_profit_rounded
    instruction_details = {
        "description": "Reversing accrued profit after application",
        "event": profit_accrual_ACCRUAL_APPLICATION_EVENT,
        "account_type": "MURABAHAH",
    }
    posting_instructions.extend(
        profit_accrual_get_residual_cleanup_posting_instructions(
            vault, denomination, instruction_details, remainder=remainder
        )
    )
    return posting_instructions


def profit_accrual_get_residual_cleanup_posting_instructions(
    vault,
    denomination: str,
    instruction_details: dict[str, str],
    remainder: Optional[Decimal] = None,
) -> list[PostingInstruction]:
    """
    Creates posting instructions to net off the account accrued profit address balance to zero and
    nets off any residual profit on the relevant internal account. After applying accrued profit or
    when closing the account. The remaining profit on the account address and the the type of
    profit determine the posting directions and what customer account address to use.

    If no remainder is given, defaults to cleaning out ACCRUED_PROFIT_PAYABLE_ADDRESS balance
    """
    posting_instructions = []
    accrued_profit_payable_account = utils_get_parameter(vault, "accrued_profit_payable_account")
    profit_paid_account = utils_get_parameter(vault, "profit_paid_account")
    if remainder is None:
        remainder = utils_get_balance_sum(vault, [profit_accrual_ACCRUED_PROFIT_PAYABLE_ADDRESS])
    if remainder < 0:
        internal_from_account_id = profit_paid_account
        internal_to_account_id = accrued_profit_payable_account
        cust_from_address = INTERNAL_CONTRA
        cust_to_address = profit_accrual_ACCRUED_PROFIT_PAYABLE_ADDRESS
    else:
        internal_from_account_id = accrued_profit_payable_account
        internal_to_account_id = profit_paid_account
        cust_from_address = profit_accrual_ACCRUED_PROFIT_PAYABLE_ADDRESS
        cust_to_address = INTERNAL_CONTRA
    if remainder != 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(remainder),
                denomination=denomination,
                from_account_id=internal_from_account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=internal_to_account_id,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"INTERNAL_POSTING_REVERSE_RESIDUAL_PROFIT_{vault.get_hook_execution_id()}_{denomination}_INTERNAL",
                instruction_details=instruction_details,
            )
        )
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(remainder),
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=cust_from_address,
                to_account_id=vault.account_id,
                to_account_address=cust_to_address,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"INTERNAL_POSTING_REVERSE_RESIDUAL_PROFIT_{vault.get_hook_execution_id()}_{denomination}_CUSTOMER",
                instruction_details=instruction_details,
            )
        )
    return posting_instructions


def profit_accrual__get_accrual_capital(
    vault, effective_date: datetime, denomination: str, capital_address: str = DEFAULT_ADDRESS
) -> Decimal:
    profit_accrual_hour = utils_get_parameter(vault, "profit_accrual_hour")
    profit_accrual_minute = utils_get_parameter(vault, "profit_accrual_minute")
    profit_accrual_second = utils_get_parameter(vault, "profit_accrual_second")
    balance_date = effective_date - timedelta(
        hours=int(profit_accrual_hour),
        minutes=int(profit_accrual_minute),
        seconds=int(profit_accrual_second),
        microseconds=1,
    )
    return utils_get_balance_sum(
        vault, [capital_address], denomination=denomination, timestamp=balance_date
    )


def profit_accrual_get_next_apply_accrued_profit_schedule(
    vault, effective_date: datetime
) -> utils_EventTuple:
    """
    Sets up dictionary for the next profit application day,
    """
    intended_profit_application_day = utils_get_parameter(vault, "profit_application_day")
    profit_application_frequency = utils_get_parameter(
        vault, "profit_application_frequency", union=True
    )
    calendar_events = vault.get_calendar_events(calendar_ids=["&{PUBLIC_HOLIDAYS}"])
    return utils_get_schedule(
        vault,
        param_prefix="profit_application",
        event_type=profit_accrual_ACCRUAL_APPLICATION_EVENT,
        localised_effective_date=vault.localize_datetime(dt=effective_date),
        schedule_frequency=profit_application_frequency,
        schedule_day_of_month=intended_profit_application_day,
        calendar_events=calendar_events,
    )


# Objects below have been imported from:
#    tiered_profit_calculation.py
# md5:6acbadd092bac5d9acdf1fae61dc361f

tiered_profit_calculation_parameters = [
    Parameter(
        name="balance_tier_ranges",
        level=Level.TEMPLATE,
        description="Deposit balance ranges used to determine applicable profit rate.minimum in range is exclusive and maximum is inclusive",
        display_name="Balance tiers",
        shape=StringShape,
        default_value=json_dumps(
            {
                "tier1": {"min": "0"},
                "tier2": {"min": "10000.00"},
                "tier3": {"min": "25000.00"},
                "tier4": {"min": "50000.00"},
                "tier5": {"min": "100000.00"},
            }
        ),
    ),
    Parameter(
        name="tiered_profit_rates",
        level=Level.TEMPLATE,
        description="Tiered profit rates applicable to the main denomination as determined by the both balance tier ranges and account tiers. This is the gross profit rate (per annum) used to calculate profit on customers deposits. This is accrued daily and applied according to the schedule.",
        display_name="Tiered profit rates (p.a.)",
        shape=StringShape,
        default_value=json_dumps(
            {
                "STANDARD": {
                    "tier1": "0.0025",
                    "tier2": "0.0075",
                    "tier3": "0.015",
                    "tier4": "0.02",
                    "tier5": "0.025",
                }
            }
        ),
    ),
    Parameter(
        name="days_in_year",
        level=Level.TEMPLATE,
        description='The days in the year for profit accrual calculation. Valid values are "actual", "365", "366", "360". Any invalid values will default to "actual".',
        display_name="Profit accrual days in year",
        shape=UnionShape(
            UnionItem(key="actual", display_name="Actual"),
            UnionItem(key="365", display_name="365"),
            UnionItem(key="366", display_name="366"),
            UnionItem(key="360", display_name="360"),
        ),
        default_value=UnionItemValue(key="actual"),
    ),
]


def tiered_profit_calculation_calculate(vault, accrual_capital: Decimal, effective_date: datetime):
    amount_to_accrue = Decimal("0")
    account_tier = account_tiers_get_account_tier(vault)
    balance_tier_ranges = utils_get_parameter(vault, "balance_tier_ranges", is_json=True)
    tiered_profit_rates = utils_get_parameter(vault, "tiered_profit_rates", is_json=True).get(
        account_tier, {}
    )
    days_in_year = utils_get_parameter(vault, "days_in_year", union=True)
    for (tier_name, tier_range) in reversed(balance_tier_ranges.items()):
        tier_min = Decimal(tier_range.get("min"))
        if accrual_capital > tier_min:
            effective_balance = accrual_capital - tier_min
            profit_rate = Decimal(tiered_profit_rates.get(tier_name, "0"))
            daily_rate = utils_yearly_to_daily_rate(
                profit_rate, effective_date.year, days_in_year=days_in_year
            )
            amount_to_accrue += utils_round_decimal(
                abs(effective_balance * daily_rate), decimal_places=5, rounding=ROUND_DOWN
            )
            accrual_capital -= effective_balance
    return amount_to_accrue


tiered_profit_calculation_TieredProfitCalculation = NamedTuple(
    "TieredProfitCalculation", [("parameters", list), ("calculate", Callable)]
)
tiered_profit_calculation_feature = tiered_profit_calculation_TieredProfitCalculation(
    parameters=tiered_profit_calculation_parameters, calculate=tiered_profit_calculation_calculate
)

# Objects below have been imported from:
#    murabahah.py
# md5:082578ac76b2dd87d9373beea963894b

LOCAL_UTC_OFFSET = 8
events_timezone = "Asia/Kuala_Lumpur"
event_types = profit_accrual_get_event_types("MURABAHAH")
PAYMENT_CATEGORY = "PAYMENT_CATEGORY"
PAYMENT_TYPE = "PAYMENT_TYPE"
INTERNAL_CONTRA = "INTERNAL_CONTRA"
parameters = [
    Parameter(
        name="maximum_daily_payment_category_withdrawal",
        level=Level.TEMPLATE,
        description="The maximum amount allowed for each payment category per day.",
        display_name="Maximum daily payment category withdrawal amount",
        shape=StringShape,
        update_permission=UpdatePermission.USER_EDITABLE,
        default_value=json_dumps({"CASH_ADVANCE": "5000"}),
    ),
    Parameter(
        name="maximum_daily_payment_type_withdrawal",
        level=Level.TEMPLATE,
        description="The maximum amount allowed for each payment type per day.",
        display_name="Maximum daily payment type withdrawal amount",
        shape=StringShape,
        default_value=json_dumps({"ATM": "500"}),
    ),
    Parameter(
        name="denomination",
        level=Level.TEMPLATE,
        description="Currency in which the product operates.",
        display_name="Denomination",
        shape=DenominationShape,
        default_value="MYR",
    ),
    Parameter(
        name="payment_type_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for payment type fee income balance.",
        display_name="Payment type fee income account",
        shape=AccountIdShape,
        default_value="PAYMENT_TYPE_FEE_INCOME",
    ),
    *early_closure_fee_parameters,
    *minimum_initial_deposit_parameters,
    *maximum_single_deposit_parameters,
    *minimum_single_deposit_parameters,
    *maximum_balance_limit_parameters,
    *maximum_daily_deposit_parameters,
    *maximum_daily_withdrawal_parameters,
    *maximum_single_withdrawal_parameters,
    *maximum_withdrawal_by_payment_type_parameters,
    *minimum_balance_by_tier_parameters,
    *account_tiers_parameters,
    *payment_type_flat_fee_parameters,
    *payment_type_threshold_fee_parameters,
    *monthly_limit_by_payment_type_parameters,
    *tiered_profit_calculation_parameters,
    *profit_accrual_parameters,
]


def _reschedule_apply_accrued_profit_event(vault, effective_date: datetime):
    """
    Calculate the next date for apply accrue profit and update the schedule.
    :param vault: Vault object
    :param effective_date: effective date
    :return: None
    """
    apply_profit_schedule = profit_accrual_get_next_apply_accrued_profit_schedule(
        vault, effective_date
    )
    vault.amend_schedule(
        event_type=apply_profit_schedule.event_type, new_schedule=apply_profit_schedule.schedule
    )
