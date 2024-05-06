# Code auto-generated using Inception Smart Contract Renderer Version 2.0.1


# Objects below have been imported from:
#    us_savings_account_v3.py
# md5:3ed635eaa4e1c30df212493b4c9bf5a1

api = "3.12.0"
version = "1.8.4"
display_name = "US Savings Account"
summary = "A savings account with a fixed interest rate."
tside = Tside.LIABILITY
supported_denominations = ["USD"]
contract_module_imports = [
    ContractModule(
        alias="interest",
        expected_interface=[
            SharedFunction(name="construct_payable_receivable_mapping"),
            SharedFunction(name="construct_accrual_details"),
            SharedFunction(name="construct_fee_details"),
            SharedFunction(name="construct_charge_application_details"),
            SharedFunction(name="accrue_interest"),
            SharedFunction(name="accrue_fees"),
            SharedFunction(name="apply_charges"),
            SharedFunction(name="reverse_interest"),
        ],
    ),
    ContractModule(
        alias="utils",
        expected_interface=[
            SharedFunction(name="create_schedule_dict_from_datetime"),
            SharedFunction(name="get_parameter"),
            SharedFunction(name="get_transaction_type"),
            SharedFunction(name="str_to_bool"),
            SharedFunction(name="has_parameter_value_changed"),
        ],
    ),
]


@requires(modules=["utils"], parameters=True)
def execution_schedules() -> list[tuple[str, dict[str, Any]]]:
    account_creation_date = vault.get_account_creation_date()
    accrue_interest_schedule = _get_accrue_interest_schedule(vault)
    apply_accrued_interest_schedule = _get_next_apply_accrued_interest_schedule(
        vault, account_creation_date
    )
    apply_monthly_fees_schedule = _get_next_apply_fees_schedule(
        vault, account_creation_date, timedelta(months=1)
    )
    return [
        ("ACCRUE_INTEREST", accrue_interest_schedule),
        ("APPLY_ACCRUED_INTEREST", apply_accrued_interest_schedule),
        ("APPLY_MONTHLY_FEES", apply_monthly_fees_schedule),
    ]


@requires(
    modules=["interest", "utils"],
    event_type="ACCRUE_INTEREST",
    flags=True,
    parameters=True,
    balances="1 day",
)
@requires(
    modules=["interest", "utils"],
    event_type="APPLY_ACCRUED_INTEREST",
    parameters=True,
    balances="1 day",
)
@requires(
    modules=["interest", "utils"],
    event_type="APPLY_MONTHLY_FEES",
    flags=True,
    parameters=True,
    balances="32 days",
    postings="32 days",
)
def scheduled_code(event_type: str, effective_date: datetime) -> None:
    if event_type == "ACCRUE_INTEREST":
        end_of_day = effective_date - timedelta(microseconds=1)
        _accrue_interest(vault, end_of_day)
    elif event_type == "APPLY_ACCRUED_INTEREST":
        start_of_day = datetime(
            year=effective_date.year, month=effective_date.month, day=effective_date.day
        )
        _apply_accrued_interest(vault, start_of_day)
        _reschedule_apply_accrued_interest_event(vault, effective_date)
    elif event_type == "APPLY_MONTHLY_FEES":
        _apply_fees(vault, effective_date, ["maintenance_fee_monthly", "minimum_balance_fee"])
        new_schedule = _get_next_apply_fees_schedule(vault, effective_date, timedelta(months=1))
        vault.update_event_type(
            event_type="APPLY_MONTHLY_FEES",
            schedule=_create_event_type_schedule_from_dict(new_schedule),
        )


@requires(modules=["interest", "utils"], parameters=True, balances="latest")
def close_code(effective_date: datetime) -> None:
    _reverse_accrued_interest(vault, effective_date)


@requires(modules=["utils"], parameters=True, balances="latest")
def post_parameter_change_code(
    old_parameter_values: dict[str, Parameter],
    updated_parameter_values: dict[str, Parameter],
    effective_date: datetime,
) -> None:
    if vault.modules["utils"].has_parameter_value_changed(
        "interest_application_day", old_parameter_values, updated_parameter_values
    ):
        _reschedule_apply_accrued_interest_event(vault, effective_date)


@requires(modules=["utils"], parameters=True, balances="latest live", postings="1 month")
def pre_posting_code(postings: PostingInstructionBatch, effective_date: datetime) -> None:
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    if vault.modules["utils"].str_to_bool(postings.batch_details.get("force_override", "false")):
        return
    if any((post.denomination != denomination for post in postings)):
        raise Rejected(
            "Cannot make transactions in given denomination; transactions must be in {}".format(
                denomination
            ),
            reason_code=RejectedReason.WRONG_DENOMINATION,
        )
    min_withdrawal = vault.modules["utils"].get_parameter(vault, name="minimum_withdrawal")
    min_deposit = vault.modules["utils"].get_parameter(vault, name="minimum_deposit")
    proposed_amount = 0
    for posting in postings:
        committed_balance_net = posting.balances()[
            DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
        ].net
        pending_out_balance_net = posting.balances()[
            DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT
        ].net
        pending_in_balance_net = posting.balances()[
            DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN
        ].net
        posting_debit = pending_out_balance_net + committed_balance_net
        posting_credit = pending_in_balance_net + committed_balance_net
        if 0 > posting_debit > -min_withdrawal:
            raise Rejected(
                "Transaction amount is less than the minimum withdrawal amount %s %s."
                % (min_withdrawal, denomination),
                reason_code=RejectedReason.AGAINST_TNC,
            )
        if 0 < posting_credit < min_deposit:
            raise Rejected(
                "Transaction amount is less than the minimum deposit amount %s %s."
                % (min_deposit, denomination),
                reason_code=RejectedReason.AGAINST_TNC,
            )
    proposed_amount = _get_latest_available_balance(posting.balances(), denomination, None)
    balances = vault.get_balance_timeseries().latest()
    latest_outgoing_available_balance = _get_latest_available_balance(
        balances, denomination, Phase.PENDING_IN
    )
    latest_incoming_available_balance = _get_latest_available_balance(
        balances, denomination, Phase.PENDING_OUT
    )
    if latest_outgoing_available_balance + proposed_amount < 0:
        raise Rejected(
            "Insufficient funds for transaction.", reason_code=RejectedReason.INSUFFICIENT_FUNDS
        )
    max_balance = vault.modules["utils"].get_parameter(vault, name="maximum_balance")
    if latest_incoming_available_balance + proposed_amount > max_balance and max_balance != 0:
        raise Rejected(
            "Posting would cause the maximum balance to be exceeded.",
            reason_code=RejectedReason.AGAINST_TNC,
        )
    max_daily_withdrawal = vault.modules["utils"].get_parameter(
        vault, name="maximum_daily_withdrawal"
    )
    max_daily_deposit = vault.modules["utils"].get_parameter(vault, name="maximum_daily_deposit")
    client_transactions = vault.get_client_transactions(include_proposed=True)
    _check_daily_limits(
        postings,
        denomination,
        client_transactions,
        max_daily_withdrawal,
        max_daily_deposit,
        effective_date,
    )
    _check_monthly_withdrawal_limit(vault, effective_date, postings)


@requires(modules=["utils"], parameters=True, postings="1 month")
def post_posting_code(postings: PostingInstructionBatch, effective_date: datetime) -> None:
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    _handle_excess_withdrawals(vault, postings, effective_date, denomination)


# Objects below have been imported from:
#    us_savings_account_v3.py
# md5:3ed635eaa4e1c30df212493b4c9bf5a1

" Every dollar you save gets you closer to our savings goals."
ACCOUNT_TYPE = "US_SAVINGS"
notification_types = ["US_PRODUCTS_TRANSACTION_LIMIT_WARNING"]
INTERNAL_CONTRA = "INTERNAL_CONTRA"
INTERNAL_POSTING = "INTERNAL_POSTING"
EXTERNAL_POSTING = "EXTERNAL_POSTING"
VALID_DAYS_IN_YEAR = ["360", "365", "366", "actual"]
DEFAULT_DAYS_IN_YEAR = "actual"
DEFAULT_INTEREST_APPLICATION_FREQUENCY = "monthly"
INTEREST_APPLICATION_FREQUENCY_MAP = {"monthly": 1, "quarterly": 3, "annually": 12}
PROMOTIONAL_INTEREST_RATES_FLAG = "&{PROMOTIONAL_INTEREST_RATES}"
PROMOTIONAL_MAINTENANCE_FEE_FLAG = "&{PROMOTIONAL_MAINTENANCE_FEE}"
LimitsShape = NumberShape(kind=NumberKind.MONEY, min_value=0, step=0.01)
MoneyShape = NumberShape(kind=NumberKind.MONEY, min_value=0, step=0.01)
InterestRateShape = NumberShape(kind=NumberKind.PERCENTAGE, step=0.0001)
event_types = [
    EventType(name="ACCRUE_INTEREST", scheduler_tag_ids=["US_SAVINGS_ACCRUE_INTEREST_AST"]),
    EventType(
        name="APPLY_ACCRUED_INTEREST", scheduler_tag_ids=["US_SAVINGS_APPLY_ACCRUED_INTEREST_AST"]
    ),
    EventType(name="APPLY_MONTHLY_FEES", scheduler_tag_ids=["US_SAVINGS_APPLY_MONTHLY_FEES_AST"]),
]
parameters = [
    Parameter(
        name="interest_application_day",
        level=Level.INSTANCE,
        description="The day of the month on which interest is applied. If day does not exist in application month, applies on last day of month.",
        display_name="Interest application day",
        shape=NumberShape(min_value=1, max_value=31, step=1),
        update_permission=UpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name="denomination",
        shape=DenominationShape,
        level=Level.TEMPLATE,
        description="Currency in which the product operates.",
        display_name="Denomination",
        update_permission=UpdatePermission.FIXED,
        default_value="USD",
    ),
    Parameter(
        name="tiered_interest_rates",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="Tiered interest rates applicable to the main denomination as determined by the both balance tier ranges and account tiers. This is the gross interest rate (per annum) used to calculate interest on customers deposits. This is accrued daily and applied according to the schedule.",
        display_name="Tiered interest rates (p.a.)",
        default_value=json_dumps(
            {
                "UPPER_TIER": {"tier1": "0.02"},
                "MIDDLE_TIER": {"tier1": "0.0125"},
                "LOWER_TIER": {"tier1": "0.01"},
            }
        ),
    ),
    Parameter(
        name="balance_tier_ranges",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="Deposit balance ranges used to determine applicable interest rate.minimum in range is exclusive and maximum is inclusive",
        display_name="Balance tiers",
        default_value=json_dumps({"tier1": {"min": "0"}}),
    ),
    Parameter(
        name="minimum_combined_balance_threshold",
        level=Level.TEMPLATE,
        description="The minimum combined daily checking and savings account balance required for each account tier. If the mean combined daily balance in the main denomination falls below this, the monthly maintenance fee will be charged if no other waive criteria are satisfied. The calculation is performed every month, for each day since the last calculation. It takes samples of the balances at the fee application time. This check is only done when an account is under a supervisor plan, and this parameter is otherwise unused.",
        display_name="Minimum combined balance threshold",
        shape=StringShape,
        default_value=json_dumps(
            {"UPPER_TIER": "3000", "MIDDLE_TIER": "4000", "LOWER_TIER": "5000"}
        ),
    ),
    Parameter(
        name="minimum_deposit",
        level=Level.TEMPLATE,
        description="The minimum amount that can be deposited into the account in a single transaction.",
        display_name="Minimum deposit amount",
        shape=MoneyShape,
        default_value=Decimal("0.01"),
    ),
    Parameter(
        name="maximum_balance",
        level=Level.TEMPLATE,
        description="The maximum deposited balance amount for the account. Deposits that breach this amount will be rejected. If set to 0 this is treated as unlimited",
        display_name="Maximum balance amount",
        shape=LimitsShape,
        default_value=Decimal("0"),
    ),
    Parameter(
        name="maximum_daily_deposit",
        level=Level.TEMPLATE,
        description="The maximum amount which can be consecutively deposited into the account over a given 24hr window. If set to 0 this is treated as unlimited",
        display_name="Maximum daily deposit amount",
        shape=LimitsShape,
        default_value=Decimal("0"),
    ),
    Parameter(
        name="maximum_daily_withdrawal",
        level=Level.TEMPLATE,
        description="The maximum amount that can be consecutively withdrawn from an account over a given 24hr window. If set to 0 this is treated as unlimited",
        display_name="Maximum daily withdrawal amount",
        shape=LimitsShape,
        default_value=Decimal("0"),
    ),
    Parameter(
        name="minimum_withdrawal",
        level=Level.TEMPLATE,
        description="The minimum amount that can be withdrawn from the account in a single transaction.",
        display_name="Minimum withdrawal amount",
        shape=LimitsShape,
        default_value=Decimal("0.01"),
    ),
    Parameter(
        name="accrued_interest_payable_account",
        level=Level.TEMPLATE,
        description="Internal account for accrued interest payable balance.",
        display_name="Accrued interest payable account",
        shape=AccountIdShape,
        default_value="ACCRUED_INTEREST_PAYABLE",
    ),
    Parameter(
        name="interest_paid_account",
        level=Level.TEMPLATE,
        description="Internal account for interest paid balance.",
        display_name="Interest paid account",
        shape=AccountIdShape,
        default_value="INTEREST_PAID",
    ),
    Parameter(
        name="accrued_interest_receivable_account",
        level=Level.TEMPLATE,
        description="Internal account for accrued interest receivable balance.",
        display_name="Accrued interest receivable account",
        shape=AccountIdShape,
        default_value="ACCRUED_INTEREST_RECEIVABLE",
    ),
    Parameter(
        name="interest_received_account",
        level=Level.TEMPLATE,
        description="Internal account for interest received balance.",
        display_name="Interest received account",
        shape=AccountIdShape,
        default_value="INTEREST_RECEIVED",
    ),
    Parameter(
        name="maintenance_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for maintenance fee income balance.",
        display_name="Maintenance fee income account",
        shape=AccountIdShape,
        default_value="MAINTENANCE_FEE_INCOME",
    ),
    Parameter(
        name="excess_withdrawal_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for excess withdrawal fee income balance.",
        display_name="Excess withdrawal fee income account",
        shape=AccountIdShape,
        default_value="EXCESS_WITHDRAWAL_FEE_INCOME",
    ),
    Parameter(
        name="minimum_balance_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for minimum balance fee income balance.",
        display_name="Minimum balance fee income account",
        shape=AccountIdShape,
        default_value="MINIMUM_BALANCE_FEE_INCOME",
    ),
    Parameter(
        name="days_in_year",
        shape=UnionShape(
            UnionItem(key="actual", display_name="Actual"),
            UnionItem(key="365", display_name="365"),
            UnionItem(key="366", display_name="366"),
            UnionItem(key="360", display_name="360"),
        ),
        level=Level.TEMPLATE,
        description='The days in the year for interest accrual calculation. Valid values are "actual", "365", "366", "360". Any invalid values will default to "actual".',
        display_name="Interest accrual days in year",
        default_value=UnionItemValue(key="actual"),
    ),
    Parameter(
        name="interest_accrual_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which interest is accrued.",
        display_name="Interest accrual hour",
        default_value=0,
    ),
    Parameter(
        name="interest_accrual_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the hour at which interest is accrued.",
        display_name="Interest accrual minute",
        default_value=0,
    ),
    Parameter(
        name="interest_accrual_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the minute at which interest is accrued.",
        display_name="Interest accrual second",
        default_value=0,
    ),
    Parameter(
        name="interest_application_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which interest is applied.",
        display_name="Interest application hour",
        default_value=0,
    ),
    Parameter(
        name="interest_application_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the hour at which interest is applied.",
        display_name="Interest application minute",
        default_value=1,
    ),
    Parameter(
        name="interest_application_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the minute at which interest is applied.",
        display_name="Interest application second",
        default_value=0,
    ),
    Parameter(
        name="interest_application_frequency",
        shape=UnionShape(
            UnionItem(key="monthly", display_name="Monthly"),
            UnionItem(key="quarterly", display_name="Quarterly"),
            UnionItem(key="annually", display_name="Annually"),
        ),
        level=Level.TEMPLATE,
        description='The frequency at which deposit interest is applied to deposits in the main denomination. Valid values are "monthly", "quarterly", "annually".',
        display_name="Interest application frequency",
        default_value=UnionItemValue(key="monthly"),
    ),
    Parameter(
        name="monthly_withdrawal_limit",
        shape=NumberShape(min_value=-1, step=1),
        level=Level.TEMPLATE,
        description="The number of withdrawals allowed per month. -1 means unlimited",
        display_name="Number of withdrawals allowed per month",
        default_value=6,
    ),
    Parameter(
        name="reject_excess_withdrawals",
        shape=UnionShape(
            UnionItem(key="true", display_name="True"), UnionItem(key="false", display_name="False")
        ),
        level=Level.TEMPLATE,
        description="If true, excess withdrawals will be rejected, otherwise they will be allowed, but incur an excess withdrawal fee.",
        display_name="Reject excess withdrawals",
        default_value=UnionItemValue(key="true"),
    ),
    Parameter(
        name="excess_withdrawal_fee",
        shape=MoneyShape,
        level=Level.TEMPLATE,
        description="Fee charged for excess withdrawals if they are not rejected outright.",
        display_name="Excess withdrawal fee",
        default_value=Decimal("10.00"),
    ),
    Parameter(
        name="maintenance_fee_monthly",
        level=Level.TEMPLATE,
        description="The monthly fee charged for account maintenance for each account tier. This fee can be waived if one automated deposit transfer is made for the period.",
        display_name="Monthly maintenance fee",
        shape=StringShape,
        default_value=json_dumps({"UPPER_TIER": "15", "MIDDLE_TIER": "10", "LOWER_TIER": "5"}),
    ),
    Parameter(
        name="promotional_maintenance_fee_monthly",
        level=Level.TEMPLATE,
        description="The promotional monthly fee charged for account maintenance for each account tier.",
        display_name="Promotional monthly maintenance fee",
        shape=StringShape,
        default_value=json_dumps({"UPPER_TIER": "15", "MIDDLE_TIER": "10", "LOWER_TIER": "5"}),
    ),
    Parameter(
        name="automated_transfer_tag",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="The tag to check for in the client transaction id that identifies a qualifying automated transfer. Used in determining waive criteria for monthly maintenance fee.",
        display_name="Automated transfer tag",
        default_value="DEPOSIT_ACH_",
    ),
    Parameter(
        name="fees_application_day",
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=Level.TEMPLATE,
        description="The day of the month on which fees are applied. For months with fewer than the set value the last day of the month will be used",
        display_name="Fees application day",
        default_value=1,
    ),
    Parameter(
        name="fees_application_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which maintenance and minimum balance fees are applied",
        display_name="Fees application hour",
        default_value=0,
    ),
    Parameter(
        name="fees_application_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the hour at which maintenance and minimum balance fees are applied",
        display_name="Fees application minute",
        default_value=1,
    ),
    Parameter(
        name="fees_application_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the minute at which maintenance and minimum balance fees are applied.",
        display_name="Fees application second",
        default_value=0,
    ),
    Parameter(
        name="account_tier_names",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="JSON encoded list of account tiers used as keys in map-type parameters. Flag definitions must be configured for each used tier. If the account is missing a flag the final tier in this list is used.",
        display_name="Tier names",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=json_dumps(["UPPER_TIER", "MIDDLE_TIER", "LOWER_TIER"]),
    ),
    Parameter(
        name="tiered_minimum_balance_threshold",
        level=Level.TEMPLATE,
        description="The minimum balance allowed for each account tier. If the mean daily balance falls below this, the fee will be charged. The calculation is performed every month on the anniversary of the account opening day, for each day since the last calculation. It takes samples of the balance at the fee application time.",
        display_name="Minimum balance threshold",
        shape=StringShape,
        default_value=json_dumps({"UPPER_TIER": "25", "MIDDLE_TIER": "75", "LOWER_TIER": "100"}),
    ),
    Parameter(
        name="minimum_balance_fee",
        level=Level.TEMPLATE,
        description="The fee charged if the minimum balance falls below the threshold.",
        display_name="Minimum balance fee",
        shape=MoneyShape,
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name="promotional_rates",
        level=Level.TEMPLATE,
        description="Promotional interest rate",
        display_name="Promotional interest rate",
        shape=StringShape,
        default_value=json_dumps(
            {
                "UPPER_TIER": {"tier1": "0.02"},
                "MIDDLE_TIER": {"tier1": "0.0125"},
                "LOWER_TIER": {"tier1": "0.01"},
            }
        ),
    ),
]


def _get_accrue_interest_schedule(vault) -> dict[str, str]:
    """
    Sets up dictionary of ACCRUE_INTEREST schedule based on parameters

    :param vault: Vault parameters
    :return: dict[str, str], representation of ACCRUE_INTEREST schedule
    """
    creation_date = vault.get_account_creation_date()
    interest_accrual_hour = vault.modules["utils"].get_parameter(
        vault, "interest_accrual_hour", at=creation_date
    )
    interest_accrual_minute = vault.modules["utils"].get_parameter(
        vault, "interest_accrual_minute", at=creation_date
    )
    interest_accrual_second = vault.modules["utils"].get_parameter(
        vault, "interest_accrual_second", at=creation_date
    )
    interest_accrual_schedule = _create_schedule_dict(
        hour=interest_accrual_hour, minute=interest_accrual_minute, second=interest_accrual_second
    )
    return interest_accrual_schedule


def _accrue_interest(vault, effective_date: datetime) -> None:
    """
    Calculate interest due and round to 5DP. Generate posting instruction to credit client account
    from relevant internal account, then instruct batch with generated instruction.

    :param vault:
    :param effective_date: datetime
    """
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    balances = vault.get_balance_timeseries().at(timestamp=effective_date)
    balance = balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
    account_tier = _get_account_tier(vault)
    balance_tier_ranges = vault.modules["utils"].get_parameter(
        vault, "balance_tier_ranges", is_json=True
    )
    tiered_interest_rates = _get_tiered_interest_rates(vault)[account_tier]
    for (tier, rate) in tiered_interest_rates.items():
        balance_tier_ranges[tier]["rate"] = rate
    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        payable_address="ACCRUED_INTEREST_PAYABLE",
        receivable_address="ACCRUED_INTEREST_RECEIVABLE",
        payable_internal_account=vault.modules["utils"].get_parameter(
            vault, "accrued_interest_payable_account"
        ),
        paid_internal_account=vault.modules["utils"].get_parameter(vault, "interest_paid_account"),
        receivable_internal_account=vault.modules["utils"].get_parameter(
            vault, "accrued_interest_receivable_account"
        ),
        received_internal_account=vault.modules["utils"].get_parameter(
            vault, "interest_received_account"
        ),
    )
    accrual_details = vault.modules["interest"].construct_accrual_details(
        balance=balance,
        rates=balance_tier_ranges,
        denomination=denomination,
        payable_receivable_mapping=payable_receivable_mapping,
        base=vault.modules["utils"].get_parameter(name="days_in_year", vault=vault, union=True),
        net_postings=False,
    )
    posting_instructions = vault.modules["interest"].accrue_interest(
        vault,
        [accrual_details],
        "LIABILITY",
        effective_date,
        event_type="ACCRUE_INTEREST",
        account_type=ACCOUNT_TYPE,
    )
    if len(posting_instructions) > 0:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions, effective_date=effective_date
        )


def _create_schedule_dict(
    start_date: Optional[datetime] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    hour: Optional[int] = None,
    minute: Optional[int] = None,
    second: Optional[int] = None,
) -> dict[str, str]:
    """
    Creates a dict representing a schedule from datetime parameters as function input

    :param start_date: datetime, starting date for the schedule
    :param year: int, year for schedule to run
    :param month: int, month for schedule to run
    :param day: int, day of month for schedule to run
    :param hour: int, hour of day for schedule to run
    :param minute: int, minute of hour for schedule to run
    :param second: int, second of minute for schedule to run
    :return: dict[str, str], representation of schedule from function input
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


def _reschedule_apply_accrued_interest_event(vault, effective_date: datetime) -> None:
    apply_interest_schedule = _get_next_apply_accrued_interest_schedule(vault, effective_date)
    vault.update_event_type(
        event_type="APPLY_ACCRUED_INTEREST",
        schedule=_create_event_type_schedule_from_dict(apply_interest_schedule),
    )


def _apply_accrued_interest(vault, effective_date: datetime) -> None:
    """
    Get sum of committed ACCRUED_INTEREST balance at effective_date rounded to 2DP for each
    accrued interest address and generate
    instruction representing credit/debit to DEFAULT_ADDRESS address on client account and mirror
    this on relevant internal account, and create posting instruction to debit/credit customer
    internal addresses.Then create posting representing reversal of any remaining interest left
    after rounding.
    Instruct generated postings and update next schedule runtime if not called by close_code hook.

    :param vault:
    :param effective_date: datetime
    """
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    balances = vault.get_balance_timeseries().at(timestamp=effective_date)
    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        payable_address="ACCRUED_INTEREST_PAYABLE",
        receivable_address="ACCRUED_INTEREST_RECEIVABLE",
        payable_internal_account=vault.modules["utils"].get_parameter(
            vault, "accrued_interest_payable_account"
        ),
        paid_internal_account=vault.modules["utils"].get_parameter(vault, "interest_paid_account"),
        receivable_internal_account=vault.modules["utils"].get_parameter(
            vault, "accrued_interest_receivable_account"
        ),
        received_internal_account=vault.modules["utils"].get_parameter(
            vault, "interest_received_account"
        ),
    )
    charge_details = vault.modules["interest"].construct_charge_application_details(
        denomination=denomination,
        payable_receivable_mapping=payable_receivable_mapping,
        zero_out_remainder=True,
        instruction_description="Interest Applied.",
    )
    posting_instructions = vault.modules["interest"].apply_charges(
        vault,
        balances=balances,
        charge_details=[charge_details],
        account_tside="LIABILITY",
        event_type="APPLY_ACCRUED_INTEREST",
        account_type=ACCOUNT_TYPE,
    )
    if len(posting_instructions) > 0:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions,
            effective_date=effective_date,
            client_batch_id="APPLY_ACCRUED_INTEREST_{}_{}".format(
                vault.get_hook_execution_id(), denomination
            ),
        )


def _reverse_accrued_interest(vault, effective_date: datetime) -> None:
    """
    Reduce the currently accrued interest to zero when we don't want to apply the interest due
    to account closure.

    :param vault: parameters
    """
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    balances = vault.get_balance_timeseries().at(timestamp=effective_date)
    posting_instructions = []
    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        payable_address="ACCRUED_INTEREST_PAYABLE",
        receivable_address="ACCRUED_INTEREST_RECEIVABLE",
        payable_internal_account=vault.modules["utils"].get_parameter(
            vault, "accrued_interest_payable_account"
        ),
        paid_internal_account=vault.modules["utils"].get_parameter(vault, "interest_paid_account"),
        receivable_internal_account=vault.modules["utils"].get_parameter(
            vault, "accrued_interest_receivable_account"
        ),
        received_internal_account=vault.modules["utils"].get_parameter(
            vault, "interest_received_account"
        ),
    )
    accrual_details = vault.modules["interest"].construct_accrual_details(
        balance=0,
        rates={},
        denomination=denomination,
        payable_receivable_mapping=payable_receivable_mapping,
        instruction_description="Reverse accrued interest due to account closure",
    )
    posting_instructions.extend(
        vault.modules["interest"].reverse_interest(
            vault,
            balances=balances,
            interest_dimensions=[accrual_details],
            account_tside="LIABILITY",
            event_type="CLOSE_ACCOUNT",
            account_type=ACCOUNT_TYPE,
        )
    )
    if len(posting_instructions) > 0:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions,
            effective_date=effective_date,
            client_batch_id="REVERSE_ACCRUED_INTEREST_{}_{}".format(
                vault.get_hook_execution_id(), denomination
            ),
        )


def _apply_fees(vault, effective_date: datetime, fee_parameters: list[str]) -> None:
    """
    Applies maintenance fees to the account. By design these are not accrued
    daily on a pro-rata basis but applied when due. When the account is
    closed they are not prorated.

    The monthly maintenance fee may be waived if any of the following criteria are met:
    1) One automated deposit transfer is made for the period
    2) The minimum combined balance threshold is satisfied for the period. This check can
    only happen if the account is added to a supervisor plan.

    :param vault: parameters
    :param effective_date: datetime, date and time of hook being run
    :param fee_parameters: list<string>, names of fee template parameters that can
                           be applied ('maintenance_fee_monthly','minimum_balance_fee')
    """
    maintenance_fee_income_account = vault.modules["utils"].get_parameter(
        vault, "maintenance_fee_income_account"
    )
    minimum_balance_fee_income_account = vault.modules["utils"].get_parameter(
        vault, "minimum_balance_fee_income_account"
    )
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    posting_instructions = []
    for fee_parameter in fee_parameters:
        fee_amount = 0
        if fee_parameter == "minimum_balance_fee":
            to_account = minimum_balance_fee_income_account
            tiered_minimum_balance_threshold_params = vault.modules["utils"].get_parameter(
                vault, "tiered_minimum_balance_threshold", is_json=True
            )
            account_tier = _get_account_tier(vault)
            current_min_balance_threshold = Decimal(
                tiered_minimum_balance_threshold_params[account_tier]
            )
            fee_amount = Decimal(vault.modules["utils"].get_parameter(vault, "minimum_balance_fee"))
            monthly_mean_balance = _get_monthly_mean_balance(vault, denomination, effective_date)
            if (
                monthly_mean_balance is None
                or monthly_mean_balance >= current_min_balance_threshold
                or (not fee_amount)
            ):
                continue
        elif fee_parameter == "maintenance_fee_monthly":
            to_account = maintenance_fee_income_account
            monthly_fee_tiers = _get_monthly_maintenance_fee_tiers(vault)
            account_tier = _get_account_tier(vault)
            fee_amount = Decimal(monthly_fee_tiers[account_tier])
            if fee_amount <= 0:
                continue
            monthly_deposits = _count_automated_deposit_transactions(vault, effective_date)
            if monthly_deposits > 0:
                continue
        else:
            to_account = maintenance_fee_income_account
            fee_amount = Decimal(vault.modules["utils"].get_parameter(vault, fee_parameter))
        if fee_amount > 0:
            posting_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=fee_amount,
                    denomination=denomination,
                    from_account_id=vault.account_id,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=to_account,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"{INTERNAL_POSTING}_APPLY_{fee_parameter.upper()}_{vault.get_hook_execution_id()}_{denomination}",
                    instruction_details={
                        "description": f"{fee_parameter.capitalize().replace('_', ' ')}",
                        "event": f"APPLY_{fee_parameter.upper()}",
                    },
                )
            )
    if posting_instructions:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions, effective_date=effective_date
        )


def _get_account_tier(vault) -> str:
    """
    Use the account tier flags to get a corresponding value from the account tiers list.
    If no recognised flags are present then the last value in account_tier_names
    will be used by default.
    If multiple flags are present then the nearest one to the start of account_tier_names
    will be used.

    :param vault: Vault flags and parameters
    :return: string, account tier name assigned to savings account
    """
    account_tier_names = vault.modules["utils"].get_parameter(
        vault, "account_tier_names", is_json=True
    )
    for tier_param in account_tier_names:
        if vault.get_flag_timeseries(flag=tier_param).latest():
            return tier_param
    return account_tier_names[-1]


def _get_monthly_mean_balance(
    vault, denomination: str, effective_date: datetime
) -> Union[Decimal, None]:
    """
    Determine whether the average balance for the preceding month fell below the account threshold
    The sampling time is the same time as the fee application time
    The sampling period is from one month ago until yesterday, inclusive
    i.e. not including today/now. If the sampling time is before the account
    was opened then skip that day.

    :param vault: Vault creation date and balances
    :param denomination: string, account denomination
    :param effective_date: datetime, date and time of hook being run
    :return: decimal, mean balance at sampling time for previous month
    """
    creation_date = vault.get_account_creation_date()
    period_start = effective_date - timedelta(months=1)
    if period_start < creation_date:
        period_start = creation_date
    period_start.replace(hour=0, minute=0, second=0)
    num_days = (effective_date - period_start).days
    if num_days == 0:
        return None
    total = sum(
        (
            vault.get_balance_timeseries()
            .at(timestamp=period_start + timedelta(days=i))[
                DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
            ]
            .net
            for i in range(num_days)
        )
    )
    return Decimal(total / num_days)


def _check_daily_limits(
    postings: PostingInstructionBatch,
    denomination: str,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    max_daily_withdrawal: Decimal,
    max_daily_deposit: Decimal,
    effective_date: datetime,
) -> None:
    """
    Check that each posting does not breach maximum daily restrictions on deposit or withdrawal and
    raise a relevant exception if a breach occurs.

    :param postings: PostingInstructionBatch
    :param denomination: string
    :param client_transactions: dict, keyed by (client_id, client_transaction_id)
    :param max_daily_withdrawal: Decimal
    :param max_daily_deposit: Decimal
    :param effective_date: datetime
    """
    for posting in postings:
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
        (amount_deposit, amount_withdrawal) = _sum_without_current_client_trans(
            denomination,
            client_transactions,
            posting.client_transaction_id,
            datetime.combine(effective_date, datetime.min.time()),
        )
        if not posting.credit:
            if (
                amount_authed - amount_withdrawal > max_daily_withdrawal
                and max_daily_withdrawal != 0
            ):
                raise Rejected(
                    "Transaction would cause the maximum daily withdrawal limit of %s %s to be exceeded."
                    % (max_daily_withdrawal, denomination),
                    reason_code=RejectedReason.AGAINST_TNC,
                )
        elif abs(amount_deposit + amount_authed) > max_daily_deposit and max_daily_deposit != 0:
            raise Rejected(
                "Transaction would cause the maximum daily deposit limit of %s %s to be exceeded."
                % (max_daily_deposit, denomination),
                reason_code=RejectedReason.AGAINST_TNC,
            )


def _get_latest_available_balance(
    balances: dict[tuple[str, str, str, Phase], Balance],
    denomination: str,
    excluded_phase: Optional[Phase] = None,
    address: str = DEFAULT_ADDRESS,
    asset: str = DEFAULT_ASSET,
) -> Decimal:
    """
    Net of balance for a specific address ignoring one specified phase.

    :param balances: Balance timeseries
    :param denomination: string
    :param excluded_phase: string
    :param address: string, balance address
    :param asset: string, balance asset
    :return: Decimal
    """
    return Decimal(
        sum(
            (
                balance.net
                for ((address, asset, denom, phase), balance) in balances.items()
                if address == DEFAULT_ADDRESS
                and asset == DEFAULT_ASSET
                and (phase != excluded_phase)
                and (denom == denomination)
            )
        )
    )


def _get_next_interest_application_day(vault, effective_date: datetime) -> datetime:
    """
    Calculate next valid date for schedule based on day of month.
    Timedelta (Relativedelta) falls to last valid day of month
    if intended day is not in calculated month.
    This method returns the date part of the applications schedule,
    which will then be updated with the time part by the
    _get_next_apply_interest_datetime method

    :param vault: parameters
    :param effective_date: datetime, date which next schedule is calculated from
    :return: datetime, next occurrence of schedule
    """
    account_creation_date = vault.get_account_creation_date()
    intended_interest_application_day = vault.modules["utils"].get_parameter(
        vault, "interest_application_day"
    )
    interest_application_frequency = vault.modules["utils"].get_parameter(
        vault, "interest_application_frequency", at=account_creation_date, union=True
    )
    if interest_application_frequency not in INTEREST_APPLICATION_FREQUENCY_MAP:
        interest_application_frequency = DEFAULT_INTEREST_APPLICATION_FREQUENCY
    number_of_months = INTEREST_APPLICATION_FREQUENCY_MAP.get(interest_application_frequency)
    next_application_date = effective_date + timedelta(day=intended_interest_application_day)
    if next_application_date <= effective_date or interest_application_frequency != "monthly":
        next_application_date += timedelta(months=number_of_months)
    return next_application_date


def _get_next_apply_accrued_interest_schedule(vault, effective_date: datetime) -> dict[str, str]:
    """
    Sets up dictionary for the next interest application day,

    :param vault: parameters
    :param effective_date: datetime, date which next schedule is calculated from
    :return: dict, representation of APPLY_ACCRUED_INTEREST schedule
    """
    apply_accrued_interest_date = _get_next_apply_interest_datetime(vault, effective_date)
    return _create_schedule_dict(
        year=apply_accrued_interest_date.year,
        month=apply_accrued_interest_date.month,
        day=apply_accrued_interest_date.day,
        hour=apply_accrued_interest_date.hour,
        minute=apply_accrued_interest_date.minute,
        second=apply_accrued_interest_date.second,
    )


def _get_next_apply_interest_datetime(vault, effective_date: datetime) -> datetime:
    """
    Gets next scheduled interest application event based on parameters

    :param vault: Vault object
    :param effective_date: datetime, date and time of hook being run
    :return: datetime, next occurrence of schedule
    """
    creation_date = vault.get_account_creation_date()
    interest_application_hour = vault.modules["utils"].get_parameter(
        vault, "interest_application_hour", at=creation_date
    )
    interest_application_minute = vault.modules["utils"].get_parameter(
        vault, "interest_application_minute", at=creation_date
    )
    interest_application_second = vault.modules["utils"].get_parameter(
        vault, "interest_application_second", at=creation_date
    )
    apply_accrued_interest_date = _get_next_interest_application_day(vault, effective_date)
    apply_accrued_interest_datetime = apply_accrued_interest_date.replace(
        hour=interest_application_hour,
        minute=interest_application_minute,
        second=interest_application_second,
    )
    return apply_accrued_interest_datetime


def _get_next_apply_fees_schedule(
    vault, effective_date: datetime, period: timedelta
) -> dict[str, str]:
    """
    Sets up dictionary for next run time of APPLY_???_FEES, taking the day and hh:mm:ss
    from contract parameters and the period from the "period" parameter.

    :param vault: Vault object
    :param effective_date: datetime, date from which to calculate next event datetime
    :param period: timedelta, fee period
    :return: dict, representation of schedule
    """
    fees_application_day = vault.modules["utils"].get_parameter(vault, name="fees_application_day")
    fees_application_hour = vault.modules["utils"].get_parameter(
        vault, name="fees_application_hour"
    )
    fees_application_minute = vault.modules["utils"].get_parameter(
        vault, name="fees_application_minute"
    )
    fees_application_second = vault.modules["utils"].get_parameter(
        vault, name="fees_application_second"
    )
    creation_date = vault.get_account_creation_date()
    next_schedule_timedelta = timedelta(
        day=fees_application_day,
        hour=fees_application_hour,
        minute=fees_application_minute,
        second=fees_application_second,
    )
    next_schedule_date = effective_date + period + next_schedule_timedelta
    if next_schedule_date < creation_date + period:
        next_schedule_date += timedelta(months=1, day=fees_application_day)
    return vault.modules["utils"].create_schedule_dict_from_datetime(next_schedule_date)


def _sum_without_current_client_trans(
    denomination: str,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    client_transaction_id: str,
    cutoff_timestamp: datetime,
) -> tuple[Decimal, Decimal]:
    """
    Sum all settled and unsettled transactions for default address in client_transactions since
    cutoff, excluding any canceled or the current transaction.
    Return amount deposited and withdrawn since cutoff.

    :param denomination: string
    :param client_transactions: dict, keyed by (client_id, client_transaction_id)
    :param client_transaction_id: string
    :param cutoff_timestamp: datetime
    :return: Decimal, Decimal
    """
    amount_withdrawal = Decimal(0)
    amount_deposit = Decimal(0)
    for ((_, transaction_id), transaction) in client_transactions.items():
        if transaction_id == client_transaction_id:
            continue
        if transaction.cancelled:
            continue
        amount_now = (
            transaction.effects()[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination].settled
            + transaction.effects()[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination].unsettled
        )
        amount_before_cutoff = (
            transaction.effects(timestamp=cutoff_timestamp)[
                DEFAULT_ADDRESS, DEFAULT_ASSET, denomination
            ].settled
            + transaction.effects(timestamp=cutoff_timestamp)[
                DEFAULT_ADDRESS, DEFAULT_ASSET, denomination
            ].unsettled
        )
        amount = amount_now - amount_before_cutoff
        if amount > 0:
            amount_deposit += amount
        else:
            amount_withdrawal += amount
    return (amount_deposit, amount_withdrawal)


def _count_automated_deposit_transactions(vault, effective_date: datetime) -> int:
    """
    Count all automated deposit transactions for all given client_transactions in the monthly
    deposit window. Monthly deposit window is the last month, starting from account creation date.

    :param vault: Vault object
    :param effective_date: datetime
    :return: count of automated deposit transactions for monthly deposit window
    """
    denomination = vault.modules["utils"].get_parameter(vault, "denomination")
    automated_transfer_tag = vault.modules["utils"].get_parameter(
        vault, name="automated_transfer_tag"
    )
    client_transactions = vault.get_client_transactions()
    creation_date = vault.get_account_creation_date()
    period_start = effective_date - timedelta(months=1)
    if period_start < creation_date:
        period_start = creation_date
    number_of_deposits = 0
    for ((_, client_txn_id), client_txn) in client_transactions.items():
        if (
            automated_transfer_tag in client_txn_id
            and client_txn.start_time >= period_start
            and (client_txn.effects()[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination].settled > 0)
        ):
            number_of_deposits += 1
    return number_of_deposits


def _get_tiered_interest_rates(vault) -> dict:
    """
    Returns normal or promotional tiered interest rates in accordance
    to the promotion status
    :param vault: parameter
    :return: Dict
    """
    interest_rate_to_use = (
        "promotional_rates"
        if vault.get_flag_timeseries(flag=PROMOTIONAL_INTEREST_RATES_FLAG).latest()
        else "tiered_interest_rates"
    )
    return vault.modules["utils"].get_parameter(vault, interest_rate_to_use, is_json=True)


def _get_monthly_maintenance_fee_tiers(vault) -> dict:
    fee_to_use = (
        "promotional_maintenance_fee_monthly"
        if vault.get_flag_timeseries(flag=PROMOTIONAL_MAINTENANCE_FEE_FLAG).latest()
        else "maintenance_fee_monthly"
    )
    return vault.modules["utils"].get_parameter(vault=vault, name=fee_to_use, is_json=True)


def _check_monthly_withdrawal_limit(
    vault, effective_date: datetime, postings: list[PostingInstruction]
) -> None:
    reject_excess_withdrawals = vault.modules["utils"].get_parameter(
        vault, "reject_excess_withdrawals", union=True, is_boolean=True
    )
    monthly_withdrawal_limit = vault.modules["utils"].get_parameter(
        vault, "monthly_withdrawal_limit"
    )
    number_of_withdrawals = _count_monthly_withdrawal_transactions(vault, effective_date, postings)
    if (
        reject_excess_withdrawals
        and monthly_withdrawal_limit >= 0
        and (_count_excess_withdrawals(number_of_withdrawals, monthly_withdrawal_limit) > 0)
    ):
        raise Rejected(
            f"Exceeding monthly allowed withdrawal number: {monthly_withdrawal_limit}",
            reason_code=RejectedReason.AGAINST_TNC,
        )


def _handle_excess_withdrawals(
    vault, postings: PostingInstructionBatch, effective_date: datetime, denomination: str
) -> None:
    """
    Send excess withdrawal notifications and charge associated fees if excess withdrawals
    aren't rejected
    """
    if vault.modules["utils"].str_to_bool(
        postings.batch_details.get("withdrawal_override", "false")
    ):
        return
    reject_excess_withdrawals = vault.modules["utils"].get_parameter(
        vault, "reject_excess_withdrawals", union=True, is_boolean=True
    )
    monthly_withdrawal_limit = vault.modules["utils"].get_parameter(
        vault, "monthly_withdrawal_limit"
    )
    excess_withdrawal_fee = vault.modules["utils"].get_parameter(vault, "excess_withdrawal_fee")
    excess_withdrawal_fee_income_account = vault.modules["utils"].get_parameter(
        vault, "excess_withdrawal_fee_income_account"
    )
    number_of_withdrawals = _count_monthly_withdrawal_transactions(vault, effective_date, postings)
    if (
        number_of_withdrawals["total"] >= monthly_withdrawal_limit
        and number_of_withdrawals["previous"] < monthly_withdrawal_limit
    ):
        limit_message = (
            "Warning: Reached monthly withdrawal transaction limit, no further withdrawals will be allowed for the current period."
            if reject_excess_withdrawals
            else "Warning: Reached monthly withdrawal transaction limit, charges will be applied for the next withdrawal."
        )
        vault.instruct_notification(
            notification_type="US_PRODUCTS_TRANSACTION_LIMIT_WARNING",
            notification_details={
                "account_id": str(vault.account_id),
                "limit_type": "Monthly Withdrawal Limit",
                "limit": str(monthly_withdrawal_limit),
                "value": str(number_of_withdrawals["total"]),
                "message": limit_message,
            },
        )
    if not reject_excess_withdrawals and excess_withdrawal_fee > 0:
        number_of_excess_withdrawals = _count_excess_withdrawals(
            number_of_withdrawals, monthly_withdrawal_limit
        )
        total_excess_withdrawal_fee = Decimal(number_of_excess_withdrawals * excess_withdrawal_fee)
        if total_excess_withdrawal_fee > 0:
            vault.instruct_posting_batch(
                posting_instructions=vault.make_internal_transfer_instructions(
                    amount=total_excess_withdrawal_fee,
                    denomination=denomination,
                    client_transaction_id=f"{INTERNAL_POSTING}_APPLY_EXCESS_WITHDRAWAL_FEE_{vault.get_hook_execution_id()}",
                    from_account_id=vault.account_id,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=excess_withdrawal_fee_income_account,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": f"Excess withdrawal fee on exceeding monthly withdrawal limit of {monthly_withdrawal_limit}",
                        "event": "APPLY_EXCESS_WITHDRAWAL_FEE",
                    },
                ),
                effective_date=effective_date,
            )


def _count_excess_withdrawals(
    number_of_withdrawals: dict[str, int], monthly_withdrawal_limit: int
) -> int:
    """
    Determine how many withdrawals are in excess of the monthly withdrawal limit.
    The number_of_withdrawals is the output of _count_monthly_withdrawal_transactions.
    """
    return (
        0
        if monthly_withdrawal_limit < 0
        or number_of_withdrawals["total"] <= monthly_withdrawal_limit
        else number_of_withdrawals["current"]
        if number_of_withdrawals["previous"] >= monthly_withdrawal_limit
        else number_of_withdrawals["total"] - monthly_withdrawal_limit
    )


def _count_monthly_withdrawal_transactions(
    vault, effective_date: datetime, postings: list[PostingInstruction]
) -> dict[str, int]:
    """
    Counts the withdrawal transactions within a monthly window based on
    the account creation date, categorising them in dict with integer values for keys:
    - 'previous': number of withdrawals in the last month not in `postings`
    - 'current': number of withdrawals in `postings`
    - 'total': sum of the above
    """
    denomination = vault.modules["utils"].get_parameter(vault, "denomination")
    start_of_monthly_window = _get_start_of_monthly_withdrawal_window(vault, effective_date)
    client_transactions = vault.get_client_transactions()
    client_transaction_ids_in_current_batch = {
        f"{posting.client_id}_{posting.client_transaction_id}" for posting in postings
    }
    number_of_current_withdrawals = 0
    number_of_previous_withdrawals = 0
    for ((client_id, client_txn_id), client_txn) in client_transactions.items():
        if (
            INTERNAL_POSTING not in client_txn_id
            and client_txn.start_time >= start_of_monthly_window
            and (not client_txn.cancelled)
            and (client_txn.effects()[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination].settled < 0)
        ):
            if f"{client_id}_{client_txn_id}" in client_transaction_ids_in_current_batch:
                number_of_current_withdrawals += 1
            else:
                number_of_previous_withdrawals += 1
    return {
        "previous": number_of_previous_withdrawals,
        "current": number_of_current_withdrawals,
        "total": number_of_previous_withdrawals + number_of_current_withdrawals,
    }


def _get_start_of_monthly_withdrawal_window(vault, effective_date: datetime) -> datetime:
    """
    Determine the start of the latest monthly withdrawal window, based on effective date
    and the account creation date.
    """
    creation_date = vault.get_account_creation_date()
    days_since_last_monthly_anniversary = timedelta(
        effective_date.date(), creation_date.date()
    ).days
    return effective_date + timedelta(
        days=-days_since_last_monthly_anniversary, hour=0, minute=0, second=0
    )


def _create_event_type_schedule_from_dict(schedule_dict: dict[str, str]) -> EventTypeSchedule:
    """
    Creates a dict representing a schedule from datetime parameters as function input
    :param schedule_dict: the dictionary representing schedule details.  Recognised key-value-pairs:
    - year: str, year for schedule to run
    - month: str, month for schedule to run
    - day: str, day of month for schedule to run
    - day_of_week: str, day of week for schedule to run
    - hour: str, hour of day for schedule to run
    - minute: str, minute of hour for schedule to run
    - second: str, second of minute for schedule to run
    :return: Corresponding EventTypeSchedule
    """
    return EventTypeSchedule(
        year=schedule_dict.get("year"),
        month=schedule_dict.get("month"),
        day=schedule_dict.get("day"),
        day_of_week=schedule_dict.get("day_of_week"),
        hour=schedule_dict.get("hour"),
        minute=schedule_dict.get("minute"),
        second=schedule_dict.get("second"),
    )
