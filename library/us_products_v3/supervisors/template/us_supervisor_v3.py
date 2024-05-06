# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.

# standard libs
from typing import Callable, Optional

# common imports
from library.features.v3.common.supervisor_imports import *  # noqa: F403

# features
import library.features.v3.common.supervisor_utils as supervisor_utils
import library.features.v3.common.utils as utils
import library.features.v3.deposits.overdraft_protection as odp

api = "3.12.0"
version = "1.3.4"

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

data_fetchers = [
    BalancesObservationFetcher(
        fetcher_id="live_balance",
        at=DefinedDateTime.LIVE,
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
    EventType(
        name="SETUP_ODP_LINK",
        scheduler_tag_ids=["SETUP_ODP_LINK_AST"],
    ),
    EventType(
        name="ODP_SWEEP",
        scheduler_tag_ids=["SUPERVISOR_ODP_SWEEP_AST"],
    ),
]


@requires(data_scope="all", parameters=True)
def execution_schedules() -> list[tuple[str, dict[str, Any]]]:
    plan_creation_date = vault.get_plan_creation_date()
    # Currently
    # 1. supervisors do not have their own params (https://pennyworth.atlassian.net/browse/TM-13659)
    # 2. there is not a lifecycle hook for when an account is added to plan
    # as a result, once a supervisor plan has been created, it runs this schedule
    # event every hour until it sees a supervisee on plan;
    # from that point on, it will reschedule the event with the correct timing from
    # params of the supervisee;
    # adding 30 seconds before starting such hourly blind runs to give some leeway
    # for a typical account to be added to plan and for activation to be completed after opening
    first_schedule_date = plan_creation_date + timedelta(seconds=30)
    first_schedule = _create_schedule_dict_from_datetime(first_schedule_date)
    paused_schedule_date = plan_creation_date + timedelta(year=2099)
    paused_schedule = utils.create_schedule_dict_from_datetime(paused_schedule_date)
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
        checking_account = supervisor_utils.get_supervisees_for_alias(vault, "us_checking", 1).pop()
        savings_account = supervisor_utils.get_supervisees_for_alias(vault, "us_savings")
        if savings_account:
            _, posting_instructions = odp.sweep_funds(vault, effective_date)
            utils.instruct_posting_batch(
                checking_account, posting_instructions, effective_date, "ODP_SWEEP"
            )


@fetch_account_data(balances={"us_savings": ["live_balance"], "us_checking": ["live_balance"]})
@requires(data_scope="all", parameters=True)
def pre_posting_code(
    postings: PostingInstructionBatch, effective_date: datetime
) -> None:  # allow a force_override to bypass all pre-posting checks
    if utils.is_force_override(postings):
        return

    checking_account = supervisor_utils.get_supervisees_for_alias(vault, "us_checking", 1).pop()

    savings_accounts = supervisor_utils.get_supervisees_for_alias(vault, "us_savings")

    odp.validate(vault, checking_account, savings_accounts)


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
            "Multiple checking accounts not supported.",
            reason_code=RejectedReason.AGAINST_TNC,
        )
    if len(savings_accounts) > 1:
        raise Rejected(
            "Multiple savings accounts not supported.",
            reason_code=RejectedReason.AGAINST_TNC,
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
                    # postings are created in the contract so we are safe to use amount
                    autosave_amount = posting.amount
                if posting.instruction_details.get("event") != "STANDARD_OVERDRAFT":
                    posting_instructions.append(posting)
                else:
                    standard_overdraft_instructions.append(posting)

    offset_amount = -autosave_amount

    if standard_overdraft_instructions:
        posting_instructions.extend(
            odp.remove_unnecessary_overdraft_fees(
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
    vault: Vault,
    effective_date: datetime,
    account_type: str,
    accounts: Optional[list] = None,
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


def _get_supervisees_for_alias(vault: Vault, alias: str) -> list[Vault]:
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
    vault: Vault,
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
    vault: Vault,
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


def _get_next_fee_datetime(vault: Vault, effective_date: datetime) -> datetime:
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
    vault: Vault,
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
    vault: Vault,
    effective_date: datetime,
    event_type: str,
    accounts: Optional[list] = None,
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


def _monthly_mean_balance(
    denomination: str, effective_date: datetime, all_accounts: list[Vault]
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


def _get_active_account_flags(vault: Vault, interesting_flag_list: list[str]) -> list[str]:
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


def _filter_non_supervisee_postings(
    vault: Vault, postings: list[PostingInstruction]
) -> list[PostingInstruction]:
    """
    :param vault: the supervisor vault object
    :param postings: the original posting instruction batch from post_posting_code
    :returns: list of posting instructions for supervisee accounts only
    """
    # this is to work around a platform bug TM-41683
    return [posting for posting in postings if posting.account_id in vault.supervisees]


def _setup_supervisor_schedules(
    vault: SupervisorVault, event_type: str, effective_date: datetime
) -> None:
    """
    This method updates a dummy Event (SETUP_ODP_LINK) so that when the checking
    account is created, it then updates the other scheduled Events based on the
    respective schedule parameters of the checking account.
    :param vault: the supervisor vault object
    :param effective date: datetime, datetime of when the schedules are checked
    """
    checking_accounts = supervisor_utils.get_supervisees_for_alias(vault, "us_checking")
    if len(checking_accounts) == 0:
        vault.update_event_type(
            event_type=event_type,
            schedule=supervisor_utils.create_supervisor_event_type_schedule_from_datetime(
                effective_date + timedelta(minutes=1)
            ),
        )
    else:
        checking_account = checking_accounts.pop()
        odp_sweep_schedule = odp.get_odp_sweep_schedule(checking_account)
        vault.update_event_type(
            event_type="ODP_SWEEP",
            schedule=supervisor_utils.create_supervisor_event_type_schedule_from_schedule_dict(
                odp_sweep_schedule
            ),
        )
