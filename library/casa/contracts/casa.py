# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.

api = "3.9.0"
version = "1.3.0"
display_name = "CASA"
summary = "An everyday banking account with optional overdraft facility"
" - great for those who like to bank on the go."
tside = Tside.LIABILITY

# this can be amended to whichever other currencies as needed
supported_denominations = ["EUR", "GBP", "USD"]

event_types = [
    EventType(
        name="APPLY_ANNUAL_FEES",
        scheduler_tag_ids=["CASA_APPLY_ANNUAL_FEES_AST"],
    ),
    EventType(
        name="APPLY_MONTHLY_FEES",
        scheduler_tag_ids=["CASA_APPLY_MONTHLY_FEES_AST"],
    ),
    EventType(
        name="ACCRUE_INTEREST_AND_DAILY_FEES",
        scheduler_tag_ids=["CASA_ACCRUE_INTEREST_AND_DAILY_FEES_AST"],
    ),
    EventType(
        name="APPLY_ACCRUED_INTEREST",
        scheduler_tag_ids=["CASA_APPLY_ACCRUED_INTEREST_AST"],
    ),
]

INTERNAL_CONTRA = "INTERNAL_CONTRA"
INTERNAL_POSTING = "INTERNAL_POSTING"

# Instruction Detail keys
DEFAULT_TRANSACTION_TYPE = "PURCHASE"
DORMANCY_FLAG = "&{ACCOUNT_DORMANT}"

MoneyShape = NumberShape(kind=NumberKind.MONEY, min_value=0, max_value=10000, step=0.01)

LimitShape = NumberShape(kind=NumberKind.MONEY, min_value=0, step=1)

InterestRateShape = NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.0001)

parameters = [
    # Instance parameters
    Parameter(
        name="arranged_overdraft_limit",
        level=Level.INSTANCE,
        description="The borrowing limit for the main denomination agreed between the bank and the"
        " customer, before a fee is applied.",
        display_name="Arranged overdraft limit",
        update_permission=UpdatePermission.OPS_EDITABLE,
        shape=OptionalShape(MoneyShape),
        default_value=OptionalValue(Decimal("0.00")),
    ),
    Parameter(
        name="unarranged_overdraft_limit",
        level=Level.INSTANCE,
        description="The maximum borrowing limit for the main denomination on the account."
        " Withdrawals that breach this limit will be rejected.",
        display_name="Unarranged overdraft limit",
        update_permission=UpdatePermission.OPS_EDITABLE,
        shape=OptionalShape(MoneyShape),
        default_value=OptionalValue(Decimal("0.00")),
    ),
    Parameter(
        name="interest_application_day",
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=Level.INSTANCE,
        description="The day of the month on which interest is applied. If day does not exist"
        " in application month, applies on last day of month.",
        display_name="Interest application day",
        update_permission=UpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name="daily_atm_withdrawal_limit",
        level=Level.INSTANCE,
        description="Daily amount from the main denomination that can be withdrawn by ATM."
        " This must less than or equal to the maximum daily ATM withdrawal limit",
        display_name="Daily ATM withdrawal limit",
        shape=OptionalShape(LimitShape),
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=OptionalValue(Decimal("1000.00")),
    ),
    Parameter(
        name="autosave_savings_account",
        level=Level.INSTANCE,
        description="The savings account used for Autosave",
        display_name="Autosave savings account",
        shape=OptionalShape(StringShape),
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=OptionalValue(""),
    ),
    # Derived Instance parameters
    Parameter(name="account_tier", level=Level.INSTANCE, shape=StringShape, derived=True),
    # Template parameters
    Parameter(
        name="denomination",
        shape=DenominationShape,
        level=Level.TEMPLATE,
        description="The main currency in which the product operates. The following features will"
        " only be available for the main denomination: Overdraft, deposit interest,"
        " minimum account balance and other fees. Contract defined limitations will"
        " also only apply to postings made in this currency.",
        display_name="Denomination",
        update_permission=UpdatePermission.FIXED,
        default_value="GBP",
    ),
    Parameter(
        name="additional_denominations",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="Currencies that are accepted for this product, formatted as a json list of"
        " currency codes. Transactions in these currencies will act as simple pots,"
        " and will not have an overdraft or other features available to them.",
        display_name="Additional denominations",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=json_dumps(["USD", "EUR"]),
    ),
    Parameter(
        name="account_tier_names",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="JSON encoded list of account tiers used as keys in map-type parameters."
        " Flag definitions must be configured for each used tier."
        " If the account is missing a flag the final tier in this list is used.",
        display_name="Tier names",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=json_dumps(
            [
                "CASA_TIER_UPPER",
                "CASA_TIER_MIDDLE",
                "CASA_TIER_LOWER",
            ]
        ),
    ),
    Parameter(
        name="deposit_interest_application_frequency",
        shape=UnionShape(
            UnionItem(key="monthly", display_name="Monthly"),
            UnionItem(key="quarterly", display_name="Quarterly"),
            UnionItem(key="annually", display_name="Annually"),
        ),
        level=Level.TEMPLATE,
        description="The frequency at which deposit interest is applied to deposits in the main"
        ' denomination. Valid values are "monthly", "quarterly", "annually".',
        display_name="Interest application frequency",
        default_value=UnionItemValue(key="monthly"),
    ),
    Parameter(
        name="deposit_interest_rate_tiers",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="Tiered interest rates applicable to the main denomination as determined by the"
        " tier ranges. "
        "This is the gross interest rate (per annum) used to calculate interest on "
        "customers deposits. "
        "This is accrued daily and applied according to the schedule.",
        display_name="Interest rate (p.a.) tiers",
        default_value=json_dumps(
            {
                "tier1": "0.01",
                "tier2": "0.03",
                "tier3": "0.04",
                "tier4": "0.05",
                "tier5": "0.06",
            }
        ),
    ),
    Parameter(
        name="deposit_tier_ranges",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="Deposit balance ranges used to determine applicable interest rate."
        "A tier's upper bound is implicitly defined as the upper tier's lower bound."
        "E.g. tier1 has bounds of tier1.min(0)<=VALUE<tier2.min(3000)."
        "The last tier has an unbounded max limit.",
        display_name="Deposit balance interest tiers",
        default_value=json_dumps(
            {
                "tier1": {"min": "0"},
                "tier2": {"min": "3000.00"},
                "tier3": {"min": "5000.00"},
                "tier4": {"min": "7500.00"},
                "tier5": {"min": "15000.00"},
            }
        ),
    ),
    Parameter(
        name="interest_free_buffer",
        level=Level.TEMPLATE,
        description="The overdraft amount that can be used before charges apply for each account"
        " type/tier.",
        display_name="Arranged overdraft buffer amount",
        shape=OptionalShape(StringShape),
        default_value=OptionalValue(
            json_dumps(
                {
                    "CASA_TIER_UPPER": "500",
                    "CASA_TIER_MIDDLE": "300",
                    "CASA_TIER_LOWER": "200",
                }
            )
        ),
    ),
    Parameter(
        name="overdraft_interest_free_buffer_days",
        level=Level.TEMPLATE,
        description="The number of days in the grace period before the interest free buffer amount "
        "expires for each account type/tier. -1 will grant a perpetual interest "
        "free buffer. 0 is zero days, implying no overdraft buffer amount. There "
        "is a max of 31 days.",
        display_name="Arranged overdraft buffer days",
        shape=OptionalShape(StringShape),
        default_value=OptionalValue(
            json_dumps(
                {
                    "CASA_TIER_UPPER": "-1",
                    "CASA_TIER_MIDDLE": "21",
                    "CASA_TIER_LOWER": "14",
                }
            )
        ),
    ),
    Parameter(
        name="overdraft_interest_rate",
        level=Level.TEMPLATE,
        description="The gross interest rate (per annum) used to calculate"
        " interest on the customer’s overdraft."
        " This is accrued daily and applied monthly."
        " The same rate is used for arranged and unarranged overdraft.",
        display_name="Overdraft interest rate (p.a.)",
        shape=OptionalShape(InterestRateShape),
        default_value=OptionalValue(Decimal("0.1485")),
    ),
    Parameter(
        name="unarranged_overdraft_fee",
        level=Level.TEMPLATE,
        description="The daily fee charged for being in unarranged overdraft.",
        display_name="Unarranged overdraft fee",
        shape=OptionalShape(MoneyShape),
        default_value=OptionalValue(Decimal("5.00")),
    ),
    Parameter(
        name="unarranged_overdraft_fee_cap",
        level=Level.TEMPLATE,
        description="A monthly cap on accumulated fees for entering an unarranged overdraft.",
        display_name="Unarranged overdraft fee cap",
        shape=OptionalShape(MoneyShape),
        default_value=OptionalValue(Decimal("80.00")),
    ),
    Parameter(
        name="interest_accrual_days_in_year",
        shape=UnionShape(
            UnionItem(key="actual", display_name="Actual"),
            UnionItem(key="365", display_name="365"),
            UnionItem(key="360", display_name="360"),
        ),
        level=Level.TEMPLATE,
        description="The days in the year for interest accrual calculation."
        ' Valid values are "actual", "365", "360"',
        display_name="Interest accrual days in year",
        default_value=UnionItemValue(key="365"),
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
        name="maintenance_fee_annual",
        level=Level.TEMPLATE,
        description="The annual fee charged for account maintenance.",
        display_name="Annual maintenance fee",
        shape=MoneyShape,
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name="maintenance_fee_monthly",
        level=Level.TEMPLATE,
        description="The monthly fee charged for account maintenance.",
        display_name="Monthly maintenance fee",
        shape=MoneyShape,
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name="minimum_balance_threshold",
        level=Level.TEMPLATE,
        description="The minimum balance required for each account tier. If the mean"
        " daily balance in the main denomination falls below this, the fee will be"
        " charged. The calculation is performed every month on the anniversary of the"
        " account opening day, for each day since the last calculation. It takes"
        " samples of the balance at the fee application time.",
        display_name="Minimum balance threshold",
        shape=StringShape,
        default_value=json_dumps(
            {
                "CASA_TIER_UPPER": "25",
                "CASA_TIER_MIDDLE": "75",
                "CASA_TIER_LOWER": "100",
            }
        ),
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
        name="account_inactivity_fee",
        level=Level.TEMPLATE,
        description="The monthly fee charged while the account is inactive. While inactive this fee"
        " replaces other minimum balance and periodic maintenance fees.",
        display_name="Account inactivity fee",
        shape=MoneyShape,
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name="fees_application_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which fees are applied.",
        display_name="Fees application hour",
        default_value=0,
    ),
    Parameter(
        name="fees_application_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the hour at which fees are applied.",
        display_name="Fees application minute",
        default_value=1,
    ),
    Parameter(
        name="fees_application_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the minute at which fees are applied.",
        display_name="Fees application second",
        default_value=0,
    ),
    # transaction limits
    Parameter(
        name="minimum_deposit",
        level=Level.TEMPLATE,
        description="The minimum amount that can be deposited into the account"
        " in a single transaction.",
        display_name="Minimum deposit amount",
        shape=OptionalShape(MoneyShape),
        default_value=OptionalValue(Decimal("0.01")),
    ),
    Parameter(
        name="minimum_withdrawal",
        level=Level.TEMPLATE,
        description="The minimum amount that can be withdrawn from the account"
        " in a single transaction.",
        display_name="Minimum withdrawal amount",
        shape=OptionalShape(LimitShape),
        default_value=OptionalValue(Decimal("0.01")),
    ),
    Parameter(
        name="maximum_daily_deposit",
        level=Level.TEMPLATE,
        description="The maximum amount which can be consecutively deposited into"
        " the account over a given 24hr window.",
        display_name="Maximum daily deposit amount",
        shape=OptionalShape(LimitShape),
        default_value=OptionalValue(Decimal("1000")),
    ),
    Parameter(
        name="maximum_daily_withdrawal",
        level=Level.TEMPLATE,
        description="The maximum amount that can be consecutively withdrawn"
        " from an account over a given 24hr window.",
        display_name="Maximum daily withdrawal amount",
        shape=OptionalShape(LimitShape),
        default_value=OptionalValue(Decimal("100")),
    ),
    Parameter(
        name="maximum_balance",
        level=Level.TEMPLATE,
        description="The maximum deposited balance amount for the account."
        " Deposits that breach this amount will be rejected.",
        display_name="Maximum balance amount",
        shape=OptionalShape(LimitShape),
        default_value=OptionalValue(Decimal("100000")),
    ),
    Parameter(
        name="maximum_daily_atm_withdrawal_limit",
        level=Level.TEMPLATE,
        description="Maximum daily amount from the main denomination that can be withdrawn by ATM",
        display_name="Maximum daily ATM withdrawal limit",
        shape=OptionalShape(StringShape),
        default_value=OptionalValue(
            json_dumps(
                {
                    "CASA_TIER_UPPER": "5000",
                    "CASA_TIER_MIDDLE": "2000",
                    "CASA_TIER_LOWER": "1000",
                }
            )
        ),
    ),
    Parameter(
        name="transaction_code_to_type_map",
        level=Level.TEMPLATE,
        description="Map of transaction codes to transaction types" " (map format - encoded json).",
        display_name="Map of transaction types",
        shape=OptionalShape(StringShape),
        default_value=OptionalValue(json_dumps({"6011": "ATM withdrawal"})),
    ),
    Parameter(
        name="monthly_withdrawal_limit",
        shape=OptionalShape(NumberShape(min_value=-1, step=1)),
        level=Level.TEMPLATE,
        description="The number of withdrawals allowed per month. -1 means unlimited",
        display_name="Number of withdrawals allowed per month",
        default_value=OptionalValue(Decimal("3")),
    ),
    Parameter(
        name="reject_excess_withdrawals",
        shape=OptionalShape(
            UnionShape(
                UnionItem(key="true", display_name="True"),
                UnionItem(key="false", display_name="False"),
            )
        ),
        level=Level.TEMPLATE,
        description="If true, excess withdrawals will be rejected, otherwise "
        "they will be allowed, but incur an excess withdrawal fee.",
        display_name="Reject excess withdrawals",
        default_value=OptionalValue(UnionItemValue(key="true")),
    ),
    Parameter(
        name="excess_withdrawal_fee",
        shape=OptionalShape(MoneyShape),
        level=Level.TEMPLATE,
        description="Fee charged for excess withdrawals if they are not rejected outright.",
        display_name="Excess withdrawal fee",
        default_value=OptionalValue(Decimal("10.00")),
    ),
    Parameter(
        name="autosave_rounding_amount",
        level=Level.TEMPLATE,
        description="For any given spend with the primary denomination, this is the figure to "
        "round up to: the nearest multiple higher than the purchase amount. "
        "Only used if autosave_savings_account is defined.",
        display_name="Autosave rounding amount",
        shape=OptionalShape(MoneyShape),
        default_value=OptionalValue(Decimal("1.00")),
    ),
    # internal accounts
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
        name="overdraft_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for overdraft fee income balance.",
        display_name="Overdraft fee income account",
        shape=OptionalShape(AccountIdShape),
        default_value=OptionalValue("OVERDRAFT_FEE_INCOME"),
    ),
    Parameter(
        name="overdraft_fee_receivable_account",
        level=Level.TEMPLATE,
        description="Internal account for overdraft fee receivable balance.",
        display_name="Overdraft fee receivable account",
        shape=OptionalShape(AccountIdShape),
        default_value=OptionalValue("OVERDRAFT_FEE_RECEIVABLE"),
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
        name="minimum_balance_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for minimum balance fee income balance.",
        display_name="Minimum balance income account",
        shape=AccountIdShape,
        default_value="MINIMUM_BALANCE_FEE_INCOME",
    ),
    Parameter(
        name="annual_maintenance_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for annual maintenance fee income balance.",
        display_name="Annual maintenance fee income account",
        shape=AccountIdShape,
        default_value="ANNUAL_MAINTENANCE_FEE_INCOME",
    ),
    Parameter(
        name="inactivity_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for account inactivity fee income balance.",
        display_name="Account inactivity fee income account",
        shape=AccountIdShape,
        default_value="INACTIVITY_FEE_INCOME",
    ),
    Parameter(
        name="excess_withdrawal_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for excess withdrawal fee income balance.",
        display_name="Excess withdrawal fee income account",
        shape=OptionalShape(AccountIdShape),
        default_value=OptionalValue("EXCESS_WITHDRAWAL_FEE_INCOME"),
    ),
]

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
            SharedFunction(name="get_balance_sum"),
            SharedFunction(name="get_parameter"),
            SharedFunction(name="get_transaction_type"),
            SharedFunction(name="are_optional_parameters_set"),
        ],
    ),
]


@requires(modules=["utils"], parameters=True)
def execution_schedules():
    account_creation_date = vault.get_account_creation_date()
    interest_application_frequency = vault.modules["utils"].get_parameter(
        vault,
        "deposit_interest_application_frequency",
        at=account_creation_date,
        union=True,
    )

    # Every day at time set by template parameters
    accrue_interest_schedule = _get_accrue_interest_schedule(vault)

    # Whole schedule is defined by template parameters. Can be monthly, quarterly or annually
    apply_accrued_interest_schedule = _get_next_apply_accrued_interest_schedule(
        vault, account_creation_date, interest_application_frequency
    )
    # Every month anniversary from account opening at time set by template parameters
    apply_monthly_fees_schedule = _get_next_fee_schedule(
        vault, account_creation_date, timedelta(months=1)
    )
    # Every year anniversary from account opening at time set by template parameters
    apply_annual_fees_schedule = _get_next_fee_schedule(
        vault, account_creation_date, timedelta(years=1)
    )
    return [
        ("ACCRUE_INTEREST_AND_DAILY_FEES", accrue_interest_schedule),
        ("APPLY_ACCRUED_INTEREST", apply_accrued_interest_schedule),
        ("APPLY_MONTHLY_FEES", apply_monthly_fees_schedule),
        ("APPLY_ANNUAL_FEES", apply_annual_fees_schedule),
    ]


@requires(
    modules=["interest", "utils"],
    event_type="APPLY_ANNUAL_FEES",
    flags=True,
    parameters=True,
)
@requires(
    modules=["interest", "utils"],
    event_type="APPLY_MONTHLY_FEES",
    flags=True,
    parameters=True,
    balances="32 days",
)
@requires(
    modules=["interest", "utils"],
    event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
    flags=True,
    parameters=True,
    balances="31 days",
)
@requires(
    modules=["interest", "utils"],
    event_type="APPLY_ACCRUED_INTEREST",
    parameters=True,
    balances="latest",
)
def scheduled_code(event_type: str, effective_date: datetime):

    posting_instructions = []
    new_schedule = None
    if event_type == "ACCRUE_INTEREST_AND_DAILY_FEES":
        effective_date = effective_date - timedelta(microseconds=1)
        use_overdraft_facility = _are_overdraft_facility_parameters_set(vault)

        posting_instructions.extend(
            _accrue_interest(vault, effective_date, event_type, use_overdraft_facility)
        )
        if use_overdraft_facility:
            posting_instructions.extend(_accrue_fees(vault, event_type))

    elif event_type == "APPLY_ACCRUED_INTEREST":
        posting_instructions.extend(_apply_accrued_interest(vault, "DEPOSIT", event_type))
        if _are_overdraft_facility_parameters_set(vault):
            posting_instructions.extend(_apply_accrued_interest(vault, "OVERDRAFT", event_type))

        account_creation_date = vault.get_account_creation_date()
        deposit_interest_application_frequency = vault.modules["utils"].get_parameter(
            vault,
            "deposit_interest_application_frequency",
            at=account_creation_date,
            union=True,
        )

        new_schedule = _get_next_apply_accrued_interest_schedule(
            vault, effective_date, deposit_interest_application_frequency
        )

    elif event_type == "APPLY_MONTHLY_FEES":
        posting_instructions.extend(_apply_accrued_fees(vault, event_type))
        posting_instructions.extend(_apply_monthly_fees(vault, effective_date))
        new_schedule = _get_next_fee_schedule(vault, effective_date, timedelta(months=1))

    elif event_type == "APPLY_ANNUAL_FEES":
        posting_instructions.extend(_apply_annual_fees(vault))
        new_schedule = _get_next_fee_schedule(vault, effective_date, timedelta(years=1))

    if posting_instructions:
        _instruct_posting_batch(vault, posting_instructions, effective_date, event_type)

    if new_schedule:
        vault.update_event_type(
            event_type=event_type, schedule=_create_event_type_schedule_from_dict(new_schedule)
        )


@requires(
    modules=["utils"],
    parameters=True,
    flags=True,
    balances="latest live",
    postings="1 month",
)
def pre_posting_code(incoming_posting_batch: PostingInstructionBatch, effective_date: datetime):

    is_account_dormant = vault.get_flag_timeseries(flag=DORMANCY_FLAG).latest()

    if is_account_dormant is True:
        raise Rejected(
            'Account flagged "Dormant" does not accept external transactions.',
            reason_code=RejectedReason.AGAINST_TNC,
        )

    main_denomination = vault.modules["utils"].get_parameter(vault, "denomination")
    additional_denominations = vault.modules["utils"].get_parameter(
        vault, "additional_denominations", is_json=True
    )
    additional_denominations.append(main_denomination)
    accepted_denominations = set(additional_denominations)

    maximum_balance = vault.modules["utils"].get_parameter(vault, "maximum_balance", optional=True)

    minimum_withdrawal = vault.modules["utils"].get_parameter(
        vault, "minimum_withdrawal", optional=True
    )
    minimum_deposit = vault.modules["utils"].get_parameter(vault, "minimum_deposit", optional=True)

    posting_denominations = _check_posting_denominations(
        incoming_posting_batch, accepted_denominations
    )

    use_overdraft_facility = _are_overdraft_facility_parameters_set(vault)

    # Check available balances across denomination
    balances = vault.get_balance_timeseries().latest()
    for denomination in posting_denominations:
        available_balance = _get_outgoing_available_balance(balances, denomination)
        deposit_balance = _get_incoming_balance(balances, denomination)

        withdrawal_balance_delta = _get_outgoing_available_balance(
            incoming_posting_batch.balances(), denomination
        )
        deposit_balance_delta = _get_incoming_balance(
            incoming_posting_batch.balances(), denomination
        )

        _check_transaction_limits(
            denomination,
            withdrawal_balance_delta,
            deposit_balance_delta,
            minimum_withdrawal,
            minimum_deposit,
        )

        if (
            maximum_balance is not None
            and deposit_balance + deposit_balance_delta > maximum_balance
        ):
            raise Rejected(
                f"Posting would exceed maximum balance {maximum_balance}.",
                reason_code=RejectedReason.AGAINST_TNC,
            )

        _check_balance_limits(
            vault,
            denomination,
            main_denomination,
            withdrawal_balance_delta,
            available_balance,
            use_overdraft_facility,
        )

    # Do this after overall available balance checks as it is much more expensive
    client_transactions = vault.get_client_transactions(include_proposed=True)
    _check_daily_limits(vault, client_transactions, main_denomination, effective_date)

    _check_monthly_withdrawal_limit(vault, effective_date, incoming_posting_batch)


@requires(modules=["utils"], parameters=True, balances="latest live", postings="1 month")
def post_posting_code(incoming_posting_batch: PostingInstructionBatch, effective_date: datetime):
    main_denomination = vault.modules["utils"].get_parameter(name="denomination", vault=vault)

    _handle_excess_withdrawals(vault, incoming_posting_batch, effective_date, main_denomination)

    if _are_autosave_parameters_set(vault):
        autosave_rounding_amount = vault.modules["utils"].get_parameter(
            name="autosave_rounding_amount", vault=vault, optional=True
        )
        autosave_savings_account = vault.modules["utils"].get_parameter(
            name="autosave_savings_account", vault=vault, optional=True
        )
        posting_instructions = _autosave_from_purchase(
            vault,
            incoming_posting_batch,
            main_denomination,
            autosave_savings_account,
            autosave_rounding_amount,
        )
        _instruct_posting_batch(vault, posting_instructions, effective_date, "AUTOSAVE")


@requires(modules=["utils"], flags=True, parameters=True)
def pre_parameter_change_code(parameters, effective_date: datetime):
    if "daily_atm_withdrawal_limit" in parameters:
        max_atm = vault.modules["utils"].get_parameter(
            vault, "maximum_daily_atm_withdrawal_limit", is_json=True, optional=True
        )
        if max_atm is not None:
            max_atm = _get_dict_value_based_on_account_tier_flag(
                vault=vault,
                tiered_param=max_atm,
                convert=Decimal,
            )
            parameters["daily_atm_withdrawal_limit"].shape.shape.max_value = max_atm
    return parameters


@requires(modules=["utils"], parameters=True)
def post_parameter_change_code(old_parameters, new_parameters, effective_date):
    if vault.modules["utils"].has_parameter_value_changed(
        "interest_application_day", old_parameters, new_parameters
    ):
        _reschedule_apply_accrued_interest_event(vault, effective_date)


@requires(modules=["utils"], flags=True, parameters=True)
def derived_parameters(effective_date):
    params = {"account_tier": get_account_tier(vault=vault)}

    return params


@requires(modules=["interest", "utils"], parameters=True, balances="latest")
def close_code(effective_date: datetime):
    posting_instructions = []
    denomination = vault.modules["utils"].get_parameter(vault, "denomination")
    # DEPOSIT interest is always reversed on closure, but OVERDRAFT is applied
    posting_instructions.extend(_apply_accrued_interest(vault, "OVERDRAFT", "CLOSE_ACCOUNT"))
    posting_instructions.extend(_reverse_interest(vault, denomination, "CLOSE_ACCOUNT"))
    posting_instructions.extend(_apply_accrued_fees(vault, "CLOSE_ACCOUNT"))

    if posting_instructions:
        _instruct_posting_batch(vault, posting_instructions, effective_date, "CLOSE")


def _check_balance_limits(
    vault,
    posting_denomination: str,
    main_denomination: str,
    withdrawal_balance_delta: Decimal,
    available_balance: Decimal,
    use_overdraft_facility: bool,
) -> None:
    # Main denomination has the ability to support an overdraft
    if posting_denomination == main_denomination and use_overdraft_facility:
        unarranged_overdraft_limit = vault.modules["utils"].get_parameter(
            vault, "unarranged_overdraft_limit", optional=True
        )
        if withdrawal_balance_delta + available_balance < -unarranged_overdraft_limit:
            raise Rejected(
                "Posting exceeds unarranged_overdraft_limit.",
                reason_code=RejectedReason.INSUFFICIENT_FUNDS,
            )
    elif 0 > withdrawal_balance_delta and 0 > withdrawal_balance_delta + available_balance:
        raise Rejected(
            f"Postings total {posting_denomination} {withdrawal_balance_delta}, which exceeds the"
            f" available balance of {posting_denomination} {available_balance}.",
            reason_code=RejectedReason.INSUFFICIENT_FUNDS,
        )


def _check_transaction_limits(
    denomination: str,
    withdrawal_balance_delta: Decimal,
    deposit_balance_delta: Decimal,
    minimum_withdrawal: Optional[Decimal] = None,
    minimum_deposit: Optional[Decimal] = None,
):
    if minimum_withdrawal is not None and 0 > withdrawal_balance_delta > -minimum_withdrawal:
        raise Rejected(
            f"Transaction amount {withdrawal_balance_delta} is less than the "
            f"minimum withdrawal amount {minimum_withdrawal} {denomination}.",
            reason_code=RejectedReason.AGAINST_TNC,
        )

    if minimum_deposit is not None and 0 < deposit_balance_delta < minimum_deposit:
        raise Rejected(
            f"Transaction amount {deposit_balance_delta} is less than the "
            f"minimum deposit amount {minimum_deposit} {denomination}.",
            reason_code=RejectedReason.AGAINST_TNC,
        )


def _check_daily_limits(
    vault,
    client_transactions: Dict[Tuple[str, str], ClientTransaction],
    denomination: str,
    effective_date: datetime,
):

    """
    Rejects any postings that breach their transaction type credit limit (e.g.
    cash advances may be limited to 1000 of local currency unit even though
    overall credit limit may be 2000 of local currency unit)
    Note: this should be done last in pre-posting hook as it is more intensive than standard checks
    :param vault:
    :param client_transactions: dict, keyed by (client_id, client_transaction_id)
    :param denomination: account denomination
    :param effective_date: date the postings are being processed on
    :return: none - raises a Rejected exception if any posting has breached its transaction type
    limit
    """

    daily_atm_withdrawal_limit = vault.modules["utils"].get_parameter(
        vault, "daily_atm_withdrawal_limit", optional=True
    )
    max_daily_withdrawal = vault.modules["utils"].get_parameter(
        vault, "maximum_daily_withdrawal", optional=True
    )
    max_daily_deposit = vault.modules["utils"].get_parameter(
        vault, "maximum_daily_deposit", optional=True
    )
    txn_code_to_type_map = vault.modules["utils"].get_parameter(
        vault, "transaction_code_to_type_map", is_json=True, optional=True
    )

    # get total amount in batch per transaction type
    daily_txn_amount = _sum_daily_txn_amount(
        vault,
        denomination,
        client_transactions,
        effective_date + timedelta(hour=0, minute=0, second=0, microsecond=0),
        txn_code_to_type_map,
        inscope_txn_type="ATM withdrawal",
    )

    if (
        daily_atm_withdrawal_limit is not None
        and abs(daily_txn_amount["inscope_txn_amount"][0]) > daily_atm_withdrawal_limit
    ):
        raise Rejected(
            f"Transaction would cause the ATM daily withdrawal limit "
            f"of {daily_atm_withdrawal_limit} {denomination} to be exceeded.",
            reason_code=RejectedReason.AGAINST_TNC,
        )

    if (
        max_daily_withdrawal is not None
        and abs(daily_txn_amount["total_txn_amount"][0]) > max_daily_withdrawal
    ):
        raise Rejected(
            f"Transaction would cause the maximum"
            f" daily withdrawal limit of {max_daily_withdrawal} {denomination} to be exceeded.",
            reason_code=RejectedReason.AGAINST_TNC,
        )

    if (
        max_daily_deposit is not None
        and abs(daily_txn_amount["total_txn_amount"][1]) > max_daily_deposit
    ):
        raise Rejected(
            f"Transaction would cause the maximum"
            f" daily deposit limit of {max_daily_deposit} {denomination} to be exceeded.",
            reason_code=RejectedReason.AGAINST_TNC,
        )


def _sum_daily_txn_amount(
    vault,
    denomination: str,
    client_transactions: Dict[Tuple[str, str], ClientTransaction],
    cutoff_timestamp: datetime,
    txn_code_to_type_map: Dict[str, str],
    inscope_txn_type: Optional[str] = None,
) -> Dict[str, Tuple[Decimal, Decimal]]:
    """
    Sum all ATM and general withdrawals for default address in client_transactions
    since cutoff, excluding any cancelled or the current transaction.

    :param denomination: string
    :param client_transactions: dict, keyed by (client_id, client_transaction_id)
    :param cutoff_timestamp: datetime
    :param txn_code_to_type_map: dict
    :param inscope_txn_type: transaction type of postings to be counted selectively
    :return: Sum of inscope withdrawal amount and deposit amount
    """

    total_withdrawal_today = Decimal("0")
    total_deposit_today = Decimal("0")
    inscope_withdrawal_today = Decimal("0")
    inscope_deposit_today = Decimal("0")

    for transaction in client_transactions.values():
        if not transaction.cancelled:
            txn_amount = _get_txn_amount_since_cutoff(transaction, denomination, cutoff_timestamp)

            if txn_amount > Decimal("0"):
                total_deposit_today += txn_amount
            else:
                total_withdrawal_today += txn_amount

            if txn_code_to_type_map is not None and inscope_txn_type == vault.modules[
                "utils"
            ].get_transaction_type(
                # assuming all postings in a single txn must have the same txn code
                transaction[0].instruction_details,
                txn_code_to_type_map,
                DEFAULT_TRANSACTION_TYPE,
            ):
                if txn_amount > Decimal("0"):
                    inscope_deposit_today += txn_amount
                else:
                    inscope_withdrawal_today += txn_amount

    return {
        "total_txn_amount": (total_withdrawal_today, total_deposit_today),
        "inscope_txn_amount": (inscope_withdrawal_today, inscope_deposit_today),
    }


def _get_txn_amount_since_cutoff(
    transaction: ClientTransaction, denomination: str, cutoff_timestamp: datetime
) -> Decimal:
    amount_now = (
        transaction.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].settled
        + transaction.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].unsettled
    )
    # We can't do `.before()` on transaction effects, so we get 'at' the latest timestamp
    # before the cutoff timestamp instead (max granularity is 1 us)
    cutoff_timestamp -= timedelta(microseconds=1)
    amount_before_cutoff = (
        transaction.effects(timestamp=cutoff_timestamp)[
            (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)
        ].settled
        + transaction.effects(timestamp=cutoff_timestamp)[
            (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)
        ].unsettled
    )
    return amount_now - amount_before_cutoff


def _accrue_interest(
    vault, effective_date: datetime, event_type: str, use_overdraft_facility: bool
) -> List[PostingInstruction]:
    """
    Negative Committed Balances: If the balance is below the interest free buffer, overdraft
    interest will be accrued to the outgoing address.
    Positive Committed Balances: If the balance is above 0, and there is a deposit interest rate
    set, interest will be accrued to the incoming address for positive deposit interest
    rates, and the outgoing address for negative interest rates.

    :param vault: Vault object
    :param effective_date: date and time of hook being run

    :return: posting instructions
    """

    days_in_year = (
        vault.modules["utils"].get_parameter(name="interest_accrual_days_in_year", vault=vault).key
    )

    denomination = vault.modules["utils"].get_parameter(name="denomination", vault=vault)

    payable_account = vault.modules["utils"].get_parameter(
        vault, "accrued_interest_payable_account"
    )
    paid_account = vault.modules["utils"].get_parameter(vault, "interest_paid_account")
    receivable_account = vault.modules["utils"].get_parameter(
        vault, "accrued_interest_receivable_account"
    )
    received_account = vault.modules["utils"].get_parameter(vault, "interest_received_account")

    # Load balances
    effective_balance = vault.modules["utils"].get_balance_sum(
        vault=vault, addresses=[DEFAULT_ADDRESS], denomination=denomination
    )

    accrual_details = []

    if effective_balance > 0:
        deposit_tier_ranges = vault.modules["utils"].get_parameter(
            vault=vault, name="deposit_tier_ranges", is_json=True
        )
        deposit_interest_rate_tiers = vault.modules["utils"].get_parameter(
            vault=vault, name="deposit_interest_rate_tiers", is_json=True
        )

        deposit_tier_ranges_list = list(deposit_tier_ranges.values())
        combined_deposit_tier_info = {
            tier_name: {
                "min": tier_range.get("min"),
                "max": (
                    # retrieve the following tier's lower bound
                    # and set as this tier's upper bound
                    deposit_tier_ranges_list[index + 1].get("min")
                    if (index + 1) < len(deposit_tier_ranges_list)
                    else None
                ),
                "rate": deposit_interest_rate_tiers.get(tier_name, 0),
            }
            for index, (tier_name, tier_range) in enumerate(deposit_tier_ranges.items())
        }

        payable_receivable_mapping_deposit = vault.modules[
            "interest"
        ].construct_payable_receivable_mapping(
            payable_address="ACCRUED_DEPOSIT_PAYABLE",
            receivable_address="ACCRUED_DEPOSIT_RECEIVABLE",
            payable_internal_account=payable_account,
            paid_internal_account=paid_account,
            receivable_internal_account=receivable_account,
            received_internal_account=received_account,
        )

        accrual_details.append(
            vault.modules["interest"].construct_accrual_details(
                payable_receivable_mapping=payable_receivable_mapping_deposit,
                denomination=denomination,
                balance=effective_balance,
                rates={**combined_deposit_tier_info},
                base=days_in_year,
                net_postings=False,
            )
        )

    if use_overdraft_facility and effective_balance < 0:
        # Overdraft specific parameters
        interest_free_buffer_amount_tiers = vault.modules["utils"].get_parameter(
            name="interest_free_buffer", is_json=True, vault=vault, optional=True
        )
        interest_free_buffer_days_tiers = vault.modules["utils"].get_parameter(
            name="overdraft_interest_free_buffer_days",
            is_json=True,
            vault=vault,
            optional=True,
        )
        overdraft_interest_rate = vault.modules["utils"].get_parameter(
            name="overdraft_interest_rate", vault=vault, optional=True
        )
        # Load tier information
        tier_name = get_account_tier(vault=vault)
        interest_free_buffer_amount = _get_dict_value_based_on_account_tier_flag(
            vault=vault,
            tiered_param=interest_free_buffer_amount_tiers,
            convert=Decimal,
            tier_name=tier_name,
        )
        interest_free_buffer_days = _get_dict_value_based_on_account_tier_flag(
            vault=vault,
            tiered_param=interest_free_buffer_days_tiers,
            convert=Decimal,
            tier_name=tier_name,
        )

        outside_overdraft_buffer_period = _is_outside_overdraft_buffer_period(
            vault, interest_free_buffer_days, effective_date, denomination
        )
        # Remove interest free buffer amount if outside of the interest free buffer period
        if outside_overdraft_buffer_period:
            interest_free_buffer_amount = Decimal("0.00")

        # Construct overdraft accrual details
        payable_receivable_mapping_overdraft = vault.modules[
            "interest"
        ].construct_payable_receivable_mapping(
            payable_address="ACCRUED_OVERDRAFT_PAYABLE",
            receivable_address="ACCRUED_OVERDRAFT_RECEIVABLE",
            payable_internal_account=payable_account,
            paid_internal_account=paid_account,
            receivable_internal_account=receivable_account,
            received_internal_account=received_account,
        )

        accrual_details.append(
            vault.modules["interest"].construct_accrual_details(
                payable_receivable_mapping=payable_receivable_mapping_overdraft,
                denomination=denomination,
                balance=effective_balance,
                rates={
                    "": {
                        "max": f"-{interest_free_buffer_amount}",
                        "rate": overdraft_interest_rate,
                    }
                },
                base=days_in_year,
                net_postings=False,
            )
        )

    return vault.modules["interest"].accrue_interest(
        vault,
        accrual_details=accrual_details,
        account_tside="LIABILITY",
        effective_date=effective_date,
        event_type=event_type,
    )


def _reverse_interest(vault, denomination: str, event_type: str) -> List[PostingInstruction]:

    payable_account = vault.modules["utils"].get_parameter(
        vault, "accrued_interest_payable_account"
    )
    paid_account = vault.modules["utils"].get_parameter(vault, "interest_paid_account")
    receivable_account = vault.modules["utils"].get_parameter(
        vault, "accrued_interest_receivable_account"
    )
    received_account = vault.modules["utils"].get_parameter(vault, "interest_received_account")

    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        payable_address="ACCRUED_DEPOSIT_PAYABLE",
        receivable_address="ACCRUED_DEPOSIT_RECEIVABLE",
        payable_internal_account=payable_account,
        paid_internal_account=paid_account,
        receivable_internal_account=receivable_account,
        received_internal_account=received_account,
    )
    accrual_details = vault.modules["interest"].construct_accrual_details(
        payable_receivable_mapping=payable_receivable_mapping,
        denomination=denomination,
        balance=Decimal("0"),
        rates={},
        instruction_description="Reverse ACCRUED_DEPOSIT interest due to account closure",
    )

    return vault.modules["interest"].reverse_interest(
        vault,
        balances=vault.get_balance_timeseries().latest(),
        interest_dimensions=[accrual_details],
        account_tside="LIABILITY",
        event_type=event_type,
    )


def _apply_monthly_fees(vault, effective_date: datetime) -> List[PostingInstruction]:
    """
    Applies maintenance fees to the account. By design these are not accrued
    daily on a pro-rata basis but applied when due monthly. When the account is
    closed they are not prorated.

    :param vault: Vault object
    :param effective_date: date and time of hook being run

    :return: posting instructions
    """
    maintenance_fee_income_account = vault.modules["utils"].get_parameter(
        vault, "maintenance_fee_income_account"
    )
    inactivity_fee_income_account = vault.modules["utils"].get_parameter(
        vault, "inactivity_fee_income_account"
    )
    monthly_fee = vault.modules["utils"].get_parameter(vault, "maintenance_fee_monthly")
    denomination = vault.modules["utils"].get_parameter(vault, "denomination")
    minimum_balance_fee = vault.modules["utils"].get_parameter(vault, "minimum_balance_fee")
    account_inactivity_fee = vault.modules["utils"].get_parameter(vault, "account_inactivity_fee")
    is_account_dormant = vault.get_flag_timeseries(flag=DORMANCY_FLAG).latest()

    posting_instructions = []

    # Post monthly maintenance fee if set for this account
    if not is_account_dormant and monthly_fee > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=monthly_fee,
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=maintenance_fee_income_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"APPLY_MONTHLY_FEES"
                f"_MAINTENANCE"
                f"_{vault.get_hook_execution_id()}"
                f"_{denomination}_INTERNAL",
                instruction_details={
                    "description": "Monthly maintenance fee",
                    "event": "APPLY_MONTHLY_FEES",
                },
            )
        )

    # Post inactivity fee if set for this account and account is dormant
    if is_account_dormant and account_inactivity_fee > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=account_inactivity_fee,
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=inactivity_fee_income_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"APPLY_MONTHLY_FEES"
                f"_INACTIVITY"
                f"_{vault.get_hook_execution_id()}"
                f"_{denomination}_INTERNAL",
                instruction_details={
                    "description": "Account inactivity fee",
                    "event": "APPLY_MONTHLY_FEES",
                },
            )
        )

    # If minimum balance fee is enabled, and balance fell below threshold, apply it
    if not is_account_dormant and minimum_balance_fee != 0:
        minimum_balance_fee_income_account = vault.modules["utils"].get_parameter(
            vault, name="minimum_balance_fee_income_account"
        )
        # Threshold is a tier parameter driven by an account-level flag
        minimum_balance_threshold = vault.modules["utils"].get_parameter(
            vault, "minimum_balance_threshold", is_json=True
        )

        minimum_balance_threshold = _get_dict_value_based_on_account_tier_flag(
            vault=vault,
            tiered_param=minimum_balance_threshold,
            convert=Decimal,
        )

        monthly_mean_balance = _monthly_mean_balance(vault, denomination, effective_date)
        if monthly_mean_balance < minimum_balance_threshold:
            posting_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=minimum_balance_fee,
                    denomination=denomination,
                    from_account_id=vault.account_id,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=minimum_balance_fee_income_account,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id=f"APPLY_MONTHLY_FEES"
                    f"_MEAN_BALANCE"
                    f"_{vault.get_hook_execution_id()}"
                    f"_{denomination}_INTERNAL",
                    instruction_details={
                        "description": "Minimum balance fee",
                        "event": "APPLY_MONTHLY_FEES",
                    },
                )
            )

    return posting_instructions


def _apply_annual_fees(vault) -> List[PostingInstruction]:
    """
    Applies maintenance fees to the account. By design these are not accrued
    daily on a pro-rata basis but applied when due yearly. When the account is
    closed they are not prorated.
    :param vault: Vault object
    :return: posting instructions
    """
    annual_maintenance_fee_income_account = vault.modules["utils"].get_parameter(
        vault, "annual_maintenance_fee_income_account"
    )
    annual_fee = vault.modules["utils"].get_parameter(vault, "maintenance_fee_annual")
    denomination = vault.modules["utils"].get_parameter(vault, "denomination")

    is_account_dormant = vault.get_flag_timeseries(flag=DORMANCY_FLAG).latest()

    posting_instructions = []

    # Post annual fee if set for this account
    if not is_account_dormant and annual_fee > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=annual_fee,
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=annual_maintenance_fee_income_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"APPLY_ANNUAL_FEES"
                f"_{vault.get_hook_execution_id()}"
                f"_{denomination}_INTERNAL",
                instruction_details={
                    "description": "Annual maintenance fee",
                    "event": "APPLY_ANNUAL_FEES",
                },
            )
        )

    return posting_instructions


def _accrue_fees(vault, event_type: str) -> List[PostingInstruction]:
    """
    Accrues to the accrued outgoing address an overdraft fee if balance is below
    arranged overdraft limit, up to overdraft fee cap.

    :param vault: Vault object
    :param event_type: type of event triggered by the hook

    :return: posting instructions
    """
    arranged_overdraft_limit = vault.modules["utils"].get_parameter(
        vault, "arranged_overdraft_limit", optional=True
    )
    unarranged_overdraft_fee = vault.modules["utils"].get_parameter(
        vault, "unarranged_overdraft_fee", optional=True
    )
    unarranged_overdraft_fee_cap = vault.modules["utils"].get_parameter(
        vault, "unarranged_overdraft_fee_cap", optional=True
    )
    denomination = vault.modules["utils"].get_parameter(vault, "denomination")

    effective_balance = vault.modules["utils"].get_balance_sum(
        vault=vault, addresses=[DEFAULT_ADDRESS], denomination=denomination
    )

    unarranged_overdraft_fee_balance = vault.modules["utils"].get_balance_sum(
        vault=vault,
        addresses=["ACCRUED_OVERDRAFT_FEE_RECEIVABLE"],
        denomination=denomination,
    )

    if effective_balance < -arranged_overdraft_limit and (
        (unarranged_overdraft_fee_balance - unarranged_overdraft_fee)
        >= -unarranged_overdraft_fee_cap
    ):
        receivable_account = vault.modules["utils"].get_parameter(
            vault, "overdraft_fee_receivable_account", optional=True
        )
        received_account = vault.modules["utils"].get_parameter(
            vault, "overdraft_fee_income_account", optional=True
        )

        payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
            receivable_address="ACCRUED_OVERDRAFT_FEE_RECEIVABLE",
            receivable_internal_account=receivable_account,
            received_internal_account=received_account,
        )
        fee_details = vault.modules["interest"].construct_fee_details(
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=denomination,
            fee={"overdraft_fee": -unarranged_overdraft_fee},
            instruction_description="Unarranged overdraft fee accrued.",
        )

        return vault.modules["interest"].accrue_fees(
            vault,
            fee_details=[fee_details],
            account_tside="LIABILITY",
            event_type=event_type,
        )
    return []


def _apply_accrued_interest(vault, interest_type: str, event_type: str) -> List[PostingInstruction]:
    """
    Processes any accrued interest by applying it to the customer account,
    and reversing any remainders

    :param vault: Vault object
    :param effective_date: date and time of hook being run
    :param interest_type: either "OVERDRAFT" or "DEPOSIT" to identify the type of
                          posting being made
    :return: posting instructions
    """
    denomination = vault.modules["utils"].get_parameter(vault, "denomination")
    balances = vault.get_balance_timeseries().latest()

    payable_account = vault.modules["utils"].get_parameter(
        vault, "accrued_interest_payable_account"
    )
    paid_account = vault.modules["utils"].get_parameter(vault, "interest_paid_account")
    receivable_account = vault.modules["utils"].get_parameter(
        vault, "accrued_interest_receivable_account"
    )
    received_account = vault.modules["utils"].get_parameter(vault, "interest_received_account")

    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        payable_address=f"ACCRUED_{interest_type}_PAYABLE",
        receivable_address=f"ACCRUED_{interest_type}_RECEIVABLE",
        payable_internal_account=payable_account,
        paid_internal_account=paid_account,
        receivable_internal_account=receivable_account,
        received_internal_account=received_account,
    )

    charge_details = vault.modules["interest"].construct_charge_application_details(
        payable_receivable_mapping=payable_receivable_mapping,
        denomination=denomination,
        zero_out_remainder=True,
    )

    return vault.modules["interest"].apply_charges(
        vault,
        balances=balances,
        charge_details=[charge_details],
        account_tside="LIABILITY",
        event_type=event_type,
    )


def _apply_accrued_fees(vault, event_type: str) -> List[PostingInstruction]:
    """
    Applies any accrued overdraft fees to the customer account's default address

    :param vault: Vault object
    :param event_type: type of event triggered by the hook
    :return: List of posting instructions
    """
    denomination = vault.modules["utils"].get_parameter(vault, "denomination")
    balances = vault.get_balance_timeseries().latest()

    receivable_account = vault.modules["utils"].get_parameter(
        vault, "overdraft_fee_receivable_account", optional=True
    )
    received_account = vault.modules["utils"].get_parameter(
        vault, "overdraft_fee_income_account", optional=True
    )

    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        receivable_address="ACCRUED_OVERDRAFT_FEE_RECEIVABLE",
        receivable_internal_account=receivable_account,
        received_internal_account=received_account,
    )

    charge_details = vault.modules["interest"].construct_charge_application_details(
        payable_receivable_mapping=payable_receivable_mapping,
        denomination=denomination,
        instruction_description="Overdraft fees applied.",
        charge_type="FEES",
    )

    return vault.modules["interest"].apply_charges(
        vault,
        balances=balances,
        charge_details=[charge_details],
        account_tside="LIABILITY",
        event_type=event_type,
    )


def _instruct_posting_batch(
    vault,
    instructions: List[PostingInstruction],
    effective_date: datetime,
    event_type: str,
) -> None:
    """
    Instructs posting batch if instructions variable contains any posting instructions.

    :param vault: Vault object
    :param instructions: posting instructions
    :param effective_date: date and time of hook being run
    :param event_type: type of event triggered by the hook
    """
    if instructions:
        vault.instruct_posting_batch(
            posting_instructions=instructions,
            effective_date=effective_date,
            client_batch_id=f"{event_type}_{vault.get_hook_execution_id()}",
        )


def _monthly_mean_balance(vault, denomination: str, effective_date: datetime) -> Decimal:
    """
    Determine whether the average balance for the preceding month fell below the account threshold
    The sampling time is the same time as the fee application time
    The sampling period is from one month ago until yesterday, inclusive
    i.e. not including today/now. If the sampling time is before the account
    was opened then skip that day.

    :param vault: Vault object
    :param denomination: Account denomination
    :param effective_date: date and time of hook being run
    :return: mean balance at sampling time for previous month
    """
    creation_date = vault.get_account_creation_date()
    period_start = effective_date - timedelta(months=1)
    if period_start < creation_date:
        period_start += timedelta(days=1)
    num_days = (effective_date - period_start).days
    total = sum(
        [
            vault.get_balance_timeseries()
            .at(timestamp=period_start + timedelta(days=i))[
                (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
            ]
            .net
            for i in range(num_days)
        ]
    )
    mean_balance = total / num_days
    return mean_balance


def _get_outgoing_available_balance(
    balances: Dict[Tuple[str, str, str, Phase], Balance], denomination: str
) -> Decimal:
    """
    Get the available balance on account for outgoing postings. Only settled funds are considered.
    Phase.PENDING_OUT net amount will be negative for outbound authorisations.

    :param balances: defaultdict of balance dimensions to balance object
    :return: Decimal, available outgoing balance
    """
    return (
        balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
        + balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)].net
    )


def _get_incoming_balance(
    balances: Dict[Tuple[str, str, str, Phase], Balance], denomination: str
) -> Decimal:
    """
    Get the available balance on account for outgoing postings. Only settled funds are considered.
    Phase.PENDING_OUT net amount will be negative for outbound authorisations.

    :param balances: defaultdict of balance dimensions to balance object
    :return: Decimal, available outgoing balance
    """
    return (
        balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
        + balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN)].net
    )


def _get_total_savings_amount(
    vault,
    postings: List[PostingInstruction],
    denomination: str,
    autosave_rounding_amount: Decimal,
) -> Decimal:
    """
    Get total savings amount from postings made on the account.

    :param vault: Vault object
    :param postings: postings to process
    :param denomination: account denomination
    :param autosave_rounding_amount: the amount to round up to and save

    :return: total amount of calculated savings
    """

    txn_code_to_type_map = vault.modules["utils"].get_parameter(
        vault, "transaction_code_to_type_map", is_json=True, optional=True
    )

    total_savings = 0
    if txn_code_to_type_map is not None:
        pi_transaction_ids = {
            (posting.client_id, posting.client_transaction_id)
            for posting in postings
            if vault.modules["utils"].get_transaction_type(
                posting.instruction_details, txn_code_to_type_map, DEFAULT_TRANSACTION_TYPE
            )
            == "PURCHASE"
        }

        proposed = vault.get_client_transactions(include_proposed=True)
        current = vault.get_client_transactions(include_proposed=False)

        for pi_id in pi_transaction_ids:
            proposed_transactions = proposed.get(pi_id)
            proposed_settled = proposed_transactions.effects()[
                (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)
            ].settled

            current_transactions = current.get(pi_id)
            current_settled = (
                0
                if current_transactions is None
                else current_transactions.effects()[
                    (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)
                ].settled
            )

            delta = proposed_settled - current_settled
            if delta < 0:
                save_amount = 0
                remainder = Decimal(abs(delta) % autosave_rounding_amount)
                if remainder > 0:
                    save_amount = autosave_rounding_amount - remainder

                total_savings += save_amount
    return total_savings


# Helper functions for accruing and applying interest


def _is_outside_overdraft_buffer_period(
    vault, interest_free_buffer_days: int, effective_date: datetime, denomination: str
) -> bool:
    """
    Check balances at midnight to see how long we have been in our overdraft buffer period for.
    If interest_free_buffer_days are set to -1, we will treat this as unlimited, leaving it up to
    the overdraft buffer amount to determine whether or not to accrue interest.

    :param vault: The vault object
    :param interest_free_buffer_days: the amount of buffer days
    :param effective_date: the current date of execution
    :param denomination: the denomination of this account
    :return: True if we are outside of the buffer period, False if inside
    """
    # Treat -1 days as infinite/Not applicable
    if interest_free_buffer_days == -1:
        return False

    for i in range(int(interest_free_buffer_days) + 1):
        balance_at_midnight = (
            vault.get_balance_timeseries()
            .at(timestamp=effective_date - timedelta(days=i))[
                (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
            ]
            .net
        )
        if balance_at_midnight >= Decimal("0.00"):
            return False

    return True


# Helper functions for creating event schedules
def _get_accrue_interest_schedule(vault):
    """
    Sets up dictionary of ACCRUE_INTEREST schedule based on parameters

    :param vault: Vault object
    :return: dict, representation of ACCRUE_INTEREST schedule
    """
    interest_accrual_hour = vault.modules["utils"].get_parameter(vault, "interest_accrual_hour")
    interest_accrual_minute = vault.modules["utils"].get_parameter(vault, "interest_accrual_minute")
    interest_accrual_second = vault.modules["utils"].get_parameter(vault, "interest_accrual_second")

    interest_accrual_schedule = _create_schedule_dict_from_params(
        hour=interest_accrual_hour,
        minute=interest_accrual_minute,
        second=interest_accrual_second,
    )

    return interest_accrual_schedule


def _get_next_apply_accrued_interest_schedule(
    vault,
    effective_date: datetime,
    interest_application_frequency: str = "monthly",
) -> Dict[str, str]:
    """
    Sets up dictionary for the next interest application day, for both overdraft and deposit.
    :param vault: Vault object
    :param effective_date: datetime, date and time of hook being run
    :param interest_application_frequency: str, Either 'monthly', 'quarterly',
                                           or 'annually'. Defaults to monthly.
    :return: dict, representation of APPLY_ACCRUED_INTEREST schedule
    """

    interest_application_day = vault.modules["utils"].get_parameter(
        vault, "interest_application_day"
    )

    apply_accrued_interest_date = _get_next_apply_accrued_interest_date(
        vault,
        interest_application_frequency,
        interest_application_day,
        effective_date,
    )

    return vault.modules["utils"].create_schedule_dict_from_datetime(apply_accrued_interest_date)


def _get_next_apply_accrued_interest_date(
    vault,
    interest_application_frequency: str,
    interest_application_day: int,
    effective_date: datetime,
) -> datetime:
    """
    Gets next scheduled interest application event based on parameters

    :param vault: Vault object
    :param interest_application_frequency: str, Either 'monthly', 'quarterly',
                                           or 'annually'.
    :param interest_application_day: int, intended day of month for interest application
    :param effective_date: datetime, date and time of hook being run
    :return: dict, representation of APPLY_ACCRUED_INTEREST schedule
    """
    interest_application_hour = vault.modules["utils"].get_parameter(
        vault, "interest_application_hour"
    )
    interest_application_minute = vault.modules["utils"].get_parameter(
        vault, "interest_application_minute"
    )
    interest_application_second = vault.modules["utils"].get_parameter(
        vault, "interest_application_second"
    )

    apply_accrued_interest_date = _get_next_schedule_date(
        effective_date, interest_application_frequency, interest_application_day
    )

    apply_accrued_interest_datetime = apply_accrued_interest_date.replace(
        hour=interest_application_hour,
        minute=interest_application_minute,
        second=interest_application_second,
    )

    return apply_accrued_interest_datetime


def _get_next_fee_schedule(vault, start_date: datetime, offset: timedelta) -> Dict[str, str]:
    """
    Sets up dictionary for next run time of APPLY_???_FEES, taking the hh:mm:ss
    from contract parameters and the period from the "offset" parameter.

    :param vault: Vault object
    :param start_date: datetime, date from which to calculate next event datetime
    :param offset: timedelta, offset to add to start_date
    :return: dict, representation of schedule
    """

    fees_application_hour = vault.modules["utils"].get_parameter(vault, "fees_application_hour")
    fees_application_minute = vault.modules["utils"].get_parameter(vault, "fees_application_minute")
    fees_application_second = vault.modules["utils"].get_parameter(vault, "fees_application_second")

    next_schedule_date = start_date + offset

    next_schedule_date = next_schedule_date.replace(
        hour=fees_application_hour,
        minute=fees_application_minute,
        second=fees_application_second,
    )

    return vault.modules["utils"].create_schedule_dict_from_datetime(next_schedule_date)


def _reschedule_apply_accrued_interest_event(vault, effective_date):
    account_creation_date = vault.get_account_creation_date()
    interest_application_frequency = vault.modules["utils"].get_parameter(
        vault,
        "deposit_interest_application_frequency",
        at=account_creation_date,
        union=True,
    )
    apply_interest_schedule_deposit = _get_next_apply_accrued_interest_schedule(
        vault, effective_date, interest_application_frequency
    )

    vault.update_event_type(
        event_type="APPLY_ACCRUED_INTEREST",
        schedule=_create_event_type_schedule_from_dict(apply_interest_schedule_deposit),
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


def _create_schedule_dict_from_params(
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    hour: Optional[int] = None,
    minute: Optional[int] = None,
    second: Optional[int] = None,
) -> Dict[str, str]:
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


def _get_next_schedule_date(
    start_date: datetime, schedule_frequency: str, intended_day: int
) -> datetime:
    """
    Calculate next valid date for schedule based on required frequency and day of month.
    Falls to last valid day of month if intended day is not in calculated month

    :param start_date: datetime, from which schedule frequency is calculated from
    :param interest_application_frequency: str, Either 'monthly', 'quarterly',
                                           or 'annually'.
    :param intended_day: int, day of month the scheduled date should fall on
    :return: datetime, next occurrence of schedule
    """
    frequency_map = {"monthly": 1, "quarterly": 3, "annually": 12}

    number_of_months = frequency_map[schedule_frequency]
    if schedule_frequency == "monthly" and start_date + timedelta(day=intended_day) > start_date:
        next_schedule_date = start_date + timedelta(day=intended_day)
    else:
        next_schedule_date = start_date + timedelta(months=number_of_months, day=intended_day)
    return next_schedule_date


def _get_dict_value_based_on_account_tier_flag(
    vault,
    tiered_param: Dict[str, str],
    tier_name: str = "",
    convert=lambda x: x,
) -> Any:
    """
    Use the account tier flags to get a corresponding value from a
    dictionary keyed by account tier.
    If no recognised flags are present then the last value in tiered_param
    will be used by default.
    If multiple flags are present then uses the one nearest the start of
    account_tier_names.

    :param tiered_param: Dict[str, str], dictionary mapping tier names to their corresponding.
                         parameter values.
    :param convert: Callable, function to convert the resulting value before returning e.g Decimal.
    :return: Any - as per convert function, value for tiered_param corresponding to account tier.
    """
    tier = tier_name or get_account_tier(vault=vault)

    # Ensure tier is present in the tiered parameter
    if tier in tiered_param:
        value = tiered_param[tier]
        return convert(value)

    # Should only get here if tiered_param was missing a key for active account tier
    raise InvalidContractParameter("No valid account tiers have been configured for this product.")


@requires(modules=["utils"])
def get_account_tier(vault) -> str:
    """
    Use the account tier flags to get a corresponding value from the account tiers list. If no
    recognised flags are present then the last value in account_tier_names will be used by default.
    If multiple flags are present then the nearest one to the start of account_tier_names will be
    used.
    :param vault: Vault object
    :return: account tier name assigned to account
    """
    account_tier_names = vault.modules["utils"].get_parameter(
        vault, "account_tier_names", is_json=True
    )

    for tier_param in account_tier_names:
        if vault.get_flag_timeseries(flag=tier_param).latest():
            return tier_param

    return account_tier_names[-1]


def _check_posting_denominations(
    postings: List[PostingInstruction], accepted_denominations: Set[str]
) -> Set[str]:
    posting_denominations = set()
    for posting in postings:
        if posting.denomination not in accepted_denominations:
            raise Rejected(
                f"Postings received in unauthorised denomination {posting.denomination}."
                f' Authorised denominations are {", ".join(accepted_denominations)}',
                reason_code=RejectedReason.WRONG_DENOMINATION,
            )
        posting_denominations.add(posting.denomination)
    return posting_denominations


def _autosave_from_purchase(
    vault,
    postings: List[PostingInstruction],
    denomination: str,
    autosave_savings_account: Decimal,
    autosave_rounding_amount: Decimal,
) -> List[PostingInstruction]:
    """
    Automatically save into the assigned savings account after every purchase from the default
    denomination, the amount rounded up according to the parameter autosave_rounding_amount.
    The autosave_rounding_amount sets the nearest multiple higher than the purchase amount
    E.g. if autosave_rounding_amount = 1 and amount spent = 1.5
        then amount saved = 0.5
    Or,  if autosave_rounding_amount = 0.8 and amount spent = 1.8
        then amount saved = 0.6
    Or,  if autosave_rounding_amount = 100 and amount spent = 3,123
        then amount saved = 77
    :param vault: Vault object
    :param postings: postings to process
    :param effective_date: date the postings are being processed on
    :param denomination: account denomination
    :param autosave_savings_account: the chosen savings account for autosave
    :param autosave_rounding_amount: the amount to round up to and save
    :return: posting instructions
    """
    minimum_balance_fee = vault.modules["utils"].get_parameter(
        name="minimum_balance_fee", vault=vault
    )
    balances = vault.get_balance_timeseries().latest()
    available_balance = _get_outgoing_available_balance(balances, denomination)
    autosave_rounding_amount = Decimal(autosave_rounding_amount)
    posting_instructions = []
    if available_balance <= 0 or minimum_balance_fee > 0 or not autosave_savings_account:
        return posting_instructions

    total_savings = _get_total_savings_amount(
        vault, postings, denomination, autosave_rounding_amount
    )

    if total_savings > 0 and available_balance - total_savings > 0:
        posting_instructions = vault.make_internal_transfer_instructions(
            amount=total_savings,
            denomination=denomination,
            client_transaction_id=f"AUTOSAVE_{vault.get_hook_execution_id()}",
            from_account_id=vault.account_id,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=autosave_savings_account,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            instruction_details={
                "description": f"Autosave {total_savings}",
                "event": "AUTOSAVE",
            },
        )

    return posting_instructions


def _are_overdraft_facility_parameters_set(vault) -> bool:
    """
    returns True if all overdraft parameters are set, else false

    Overdraft facility specific parameters:
        PRE_POSTING
            unarranged_overdraft_limit
        FEES
            overdraft_fee_income_account
            overdraft_fee_receivable_account
            arranged_overdraft_limit
            unarranged_overdraft_fee
            unarranged_overdraft_fee_cap

        INTEREST
            interest_free_buffer - JSON
            overdraft_interest_free_buffer_days - JSON
            overdraft_interest_rate
    """
    parameters = [
        "unarranged_overdraft_limit",
        "overdraft_fee_income_account",
        "overdraft_fee_receivable_account",
        "arranged_overdraft_limit",
        "unarranged_overdraft_fee",
        "unarranged_overdraft_fee_cap",
        "interest_free_buffer",
        "overdraft_interest_free_buffer_days",
        "overdraft_interest_rate",
    ]
    return vault.modules["utils"].are_optional_parameters_set(vault, parameters)


def _are_autosave_parameters_set(vault):
    """
    returns True if all autosave parameters are set, else false

    Autosave specific parameters
        autosave_savings_account
        autosave_rounding_amount
    """
    parameters = ["autosave_savings_account", "autosave_rounding_amount"]
    return vault.modules["utils"].are_optional_parameters_set(vault, parameters)


######
# Withdrawal Limits and Excess Withdrawal Fees
#####


def _check_monthly_withdrawal_limit(
    vault,
    effective_date: datetime,
    postings: List[PostingInstruction],
):

    reject_excess_withdrawals = vault.modules["utils"].get_parameter(
        vault, "reject_excess_withdrawals", union=True, is_boolean=True, optional=True
    )
    monthly_withdrawal_limit = vault.modules["utils"].get_parameter(
        vault, "monthly_withdrawal_limit", optional=True
    )

    number_of_withdrawals = _count_monthly_withdrawal_transactions(vault, effective_date, postings)

    if (
        reject_excess_withdrawals
        and monthly_withdrawal_limit >= 0
        and _count_excess_withdrawals(number_of_withdrawals, monthly_withdrawal_limit) > 0
    ):
        raise Rejected(
            f"Exceeding monthly allowed withdrawal number: {monthly_withdrawal_limit}",
            reason_code=RejectedReason.AGAINST_TNC,
        )


def _handle_excess_withdrawals(
    vault,
    postings: List[PostingInstruction],
    effective_date: datetime,
    denomination: str,
):
    """
    Send excess withdrawal notifications and charge associated fees if excess withdrawals
    aren't rejected
    """
    # Allow a withdrawal_override to bypass fee charges
    if vault.modules["utils"].str_to_bool(
        postings.batch_details.get("withdrawal_override", "false")
    ):
        return

    reject_excess_withdrawals = vault.modules["utils"].get_parameter(
        vault, "reject_excess_withdrawals", union=True, is_boolean=True, optional=True
    )
    monthly_withdrawal_limit = vault.modules["utils"].get_parameter(
        vault, "monthly_withdrawal_limit", optional=True
    )
    excess_withdrawal_fee = vault.modules["utils"].get_parameter(
        vault, "excess_withdrawal_fee", optional=True
    )
    excess_withdrawal_fee_income_account = vault.modules["utils"].get_parameter(
        vault, "excess_withdrawal_fee_income_account", optional=True
    )

    number_of_withdrawals = _count_monthly_withdrawal_transactions(vault, effective_date, postings)

    # Send notifications the first time the limit is breached for a given window
    if (
        number_of_withdrawals["total"] >= monthly_withdrawal_limit
        and number_of_withdrawals["previous"] < monthly_withdrawal_limit
    ):
        limit_message = (
            (
                "Warning: Reached monthly withdrawal transaction limit, "
                "no further withdrawals will be allowed for the current period."
            )
            if reject_excess_withdrawals
            else (
                "Warning: Reached monthly withdrawal transaction limit, "
                "charges will be applied for the next withdrawal."
            )
        )

        vault.start_workflow(
            workflow="CASA_TRANSACTION_LIMIT_WARNING",
            context={
                "account_id": str(vault.account_id),
                "limit_type": "Monthly Withdrawal Limit",
                "limit": str(monthly_withdrawal_limit),
                "value": str(number_of_withdrawals["total"]),
                "message": limit_message,
            },
        )

    # Rejected PIBs don't normally trigger the post-posting hook, but as it is
    # a configurable platform feature we check as a safety measure
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
                    client_transaction_id=f"{INTERNAL_POSTING}_APPLY_EXCESS_WITHDRAWAL_FEE_"
                    f"{vault.get_hook_execution_id()}",
                    from_account_id=vault.account_id,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=excess_withdrawal_fee_income_account,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": f"Excess withdrawal fee on exceeding monthly withdrawal "
                        f"limit of {monthly_withdrawal_limit}",
                        "event": "APPLY_EXCESS_WITHDRAWAL_FEE",
                    },
                ),
                effective_date=effective_date,
            )


def _count_excess_withdrawals(
    number_of_withdrawals: Dict[str, int],
    monthly_withdrawal_limit: int,
) -> int:
    """
    Determine how many withdrawals are in excess of the monthly withdrawal limit.
    The number_of_withdrawals is the output of _count_monthly_withdrawal_transactions.
    """

    return (
        0
        if (
            monthly_withdrawal_limit < 0
            or number_of_withdrawals["total"] <= monthly_withdrawal_limit
        )
        else (
            number_of_withdrawals["current"]
            if number_of_withdrawals["previous"] >= monthly_withdrawal_limit
            else number_of_withdrawals["total"] - monthly_withdrawal_limit
        )
    )


def _count_monthly_withdrawal_transactions(
    vault, effective_date: datetime, postings: List[PostingInstruction]
) -> Dict[str, int]:
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

    for (client_id, client_txn_id), client_txn in client_transactions.items():
        if (
            INTERNAL_POSTING not in client_txn_id
            and client_txn.start_time >= start_of_monthly_window
            and not client_txn.cancelled
            and client_txn.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].settled < 0
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

    # This logic uses relativedelta to convert the time between now and
    # account creation date into years, months and days. The 'days' part
    # are the elapsed days since the last monthly reset, therefore
    # current day minus the days elapsed gives the start date of the
    # current monthly window.
    creation_date = vault.get_account_creation_date()
    days_since_last_monthly_anniversary = timedelta(
        effective_date.date(), creation_date.date()
    ).days
    return effective_date + timedelta(
        days=-days_since_last_monthly_anniversary, hour=0, minute=0, second=0
    )
