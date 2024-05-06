# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
api = "3.9.0"
version = "1.6.0"
display_name = "US Checking Account"
summary = "An everyday banking account with optional standard overdraft facility"
" - great for those who like to bank on the go."
tside = Tside.LIABILITY

# this can be amended to whichever other currencies as needed
supported_denominations = ["USD"]


# Instruction Detail keys
DEFAULT_TRANSACTION_TYPE = "PURCHASE"
CONTRACT_POSTING_CLIENT_ID = "CoreContracts"
DORMANCY_FLAG = "&{ACCOUNT_DORMANT}"
INTERNAL_POSTING = "INTERNAL_POSTING"
EXTERNAL_POSTING = "EXTERNAL_POSTING"
INTERNAL_CONTRA = "INTERNAL_CONTRA"
PROMOTIONAL_MAINTENANCE_FEE_FLAG = "&{PROMOTIONAL_MAINTENANCE_FEE}"
STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG = "&{STANDARD_OVERDRAFT_TRANSACTION_COVERAGE}"

MoneyShape = NumberShape(kind=NumberKind.MONEY, min_value=0, max_value=10000, step=0.01)

LimitShape = NumberShape(kind=NumberKind.MONEY, min_value=-1, step=1)

InterestRateShape = NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.0001)

event_types = [
    EventType(
        name="ACCRUE_INTEREST_AND_DAILY_FEES",
        scheduler_tag_ids=["US_CHECKING_ACCRUE_INTEREST_AND_DAILY_FEES_AST"],
    ),
    EventType(
        name="APPLY_ACCRUED_OVERDRAFT_INTEREST",
        scheduler_tag_ids=["US_CHECKING_APPLY_ACCRUED_OVERDRAFT_INTEREST_AST"],
    ),
    EventType(
        name="APPLY_ACCRUED_DEPOSIT_INTEREST",
        scheduler_tag_ids=["US_CHECKING_APPLY_ACCRUED_DEPOSIT_INTEREST_AST"],
    ),
    EventType(
        name="APPLY_MONTHLY_FEES",
        scheduler_tag_ids=["US_CHECKING_APPLY_MONTHLY_FEES_AST"],
    ),
    EventType(
        name="APPLY_ANNUAL_FEES",
        scheduler_tag_ids=["US_CHECKING_APPLY_ANNUAL_FEES_AST"],
    ),
]


parameters = [
    # Instance parameters
    Parameter(
        name="fee_free_overdraft_limit",
        level=Level.INSTANCE,
        description="The borrowing limit for the main denomination agreed between the bank and the"
        " customer, before a fee is applied. Setting to 0 will disable this feature.",
        display_name="Fee free overdraft limit",
        update_permission=UpdatePermission.OPS_EDITABLE,
        shape=MoneyShape,
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name="standard_overdraft_limit",
        level=Level.INSTANCE,
        description="Standard Overdraft is the maximum borrowing limit for the main "
        "denomination on the account. "
        "Withdrawals that breach this limit will be rejected.",
        display_name="Standard overdraft limit",
        update_permission=UpdatePermission.OPS_EDITABLE,
        shape=MoneyShape,
        default_value=Decimal("0.00"),
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
        " This must less than or equal to the maximum daily ATM withdrawal limit."
        " If set to -1 this is treated as unlimited and overrides the maximum.",
        display_name="Daily ATM withdrawal limit",
        shape=LimitShape,
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=Decimal("-1"),
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
    Parameter(
        name="savings_sweep_account_hierarchy",
        level=Level.INSTANCE,
        description="The order of savings accounts to be used for savings sweep."
        "From left to right.",
        display_name="Savings sweep account hierarchy",
        shape=OptionalShape(StringShape),
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=OptionalValue(json_dumps([])),
    ),
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
        default_value="USD",
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
        default_value=json_dumps([]),
    ),
    Parameter(
        name="tier_names",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="JSON encoded list of account tiers used as keys in map-type parameters."
        " Flag definitions must be configured for each used tier."
        " If the account is missing a flag the final tier in this list is used.",
        display_name="Tier names",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=json_dumps(["US_CHECKING_ACCOUNT_TIER_DEFAULT"]),
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
        default_value=json_dumps({"tier1": "0"}),
    ),
    Parameter(
        name="deposit_tier_ranges",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="Deposit balance ranges used to determine applicable interest rate.",
        display_name="Deposit balance interest tiers",
        default_value=json_dumps({"tier1": {"min": "0"}}),
    ),
    Parameter(
        name="interest_free_buffer",
        level=Level.TEMPLATE,
        description="The overdraft amount that can be used before interest applies for each account"
        " type/tier. Setting a single tier to 0 will disable this feature.",
        display_name="Overdraft buffer amount",
        shape=StringShape,
        default_value=json_dumps({"US_CHECKING_ACCOUNT_TIER_DEFAULT": "0"}),
    ),
    Parameter(
        name="overdraft_interest_free_buffer_days",
        level=Level.TEMPLATE,
        description="The number of days in the grace period before the interest free buffer amount "
        "expires for each account type/tier. -1 will grant a perpetual interest "
        "free buffer. 0 is zero days, implying no overdraft buffer amount.",
        display_name="Overdraft buffer days",
        shape=StringShape,
        default_value=json_dumps({"US_CHECKING_ACCOUNT_TIER_DEFAULT": "0"}),
    ),
    Parameter(
        name="overdraft_interest_rate",
        level=Level.TEMPLATE,
        description="The gross interest rate (per annum) used to calculate"
        " interest on the customer’s overdraft."
        " This is accrued daily and applied monthly.",
        display_name="Overdraft interest rate (p.a.)",
        shape=InterestRateShape,
        default_value=Decimal("0.1485"),
    ),
    Parameter(
        name="standard_overdraft_per_transaction_fee",
        level=Level.TEMPLATE,
        description="The per-transaction fee charged for any transaction that uses"
        " the standard overdraft.",
        display_name="standard overdraft per-transaction fee",
        shape=MoneyShape,
        default_value=Decimal("5.00"),
    ),
    Parameter(
        name="standard_overdraft_daily_fee",
        level=Level.TEMPLATE,
        description="The daily fee charged for being in standard overdraft.",
        display_name="standard overdraft daily fee",
        shape=MoneyShape,
        default_value=Decimal("0"),
    ),
    Parameter(
        name="standard_overdraft_fee_cap",
        level=Level.TEMPLATE,
        description="A monthly cap on accumulated standard overdraft daily fee "
        "and standard overdraft per-transaction fee for entering an overdraft. "
        "If set to 0 this is treated as unlimited.",
        display_name="standard overdraft fee cap",
        shape=MoneyShape,
        default_value=Decimal("0"),
    ),
    Parameter(
        name="savings_sweep_fee",
        level=Level.TEMPLATE,
        description="The fee charged per savings sweep transaction. "
        "Applicable only when the account is setup for savings sweep.",
        display_name="Savings sweep fee",
        shape=MoneyShape,
        default_value=Decimal("0"),
    ),
    Parameter(
        name="savings_sweep_fee_cap",
        level=Level.TEMPLATE,
        description="A daily cap on how many times savings sweep fee "
        "can be charged to the customer. "
        "If set to -1 this is treated as unlimited. "
        "Applicable only when the account is setup for savings sweep.",
        display_name="Savings sweep fee cap",
        shape=NumberShape,
        default_value=Decimal("-1"),
    ),
    Parameter(
        name="savings_sweep_transfer_unit",
        level=Level.TEMPLATE,
        description="The multiple that funds can be swept in for savings sweep. If set to "
        "50, funds are transferred from savings account(s) in multiples of 50 only. "
        "If set to 0, the exact amount required (or available) is transferred.",
        display_name="Savings sweep transfer unit",
        shape=MoneyShape,
        default_value=Decimal("0"),
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
        description="The monthly fee charged for account maintenance for each account tier. This"
        " fee can be waived if any of the following criteria are satisfied:"
        " 1) The minimum daily balance threshold is satisfied for the period"
        " 2) The account has been added to a supervisor plan and the minimum combined"
        " balance threshold is satisfied across plan accounts for the period"
        " 3) The minimum deposit threshold is satisfied for the period",
        display_name="Monthly maintenance fee",
        shape=StringShape,
        default_value=json_dumps({"US_CHECKING_ACCOUNT_TIER_DEFAULT": "10"}),
    ),
    Parameter(
        name="promotional_maintenance_fee_monthly",
        level=Level.TEMPLATE,
        description="The promotional monthly fee charged for account maintenance "
        "for each account tier. This fee can be "
        "waived subject to the same criteria as normal monthly maintenance fee.",
        display_name="Promotional monthly maintenance fee",
        shape=StringShape,
        default_value=json_dumps({"US_CHECKING_ACCOUNT_TIER_DEFAULT": "5"}),
    ),
    Parameter(
        name="minimum_balance_threshold",
        level=Level.TEMPLATE,
        description="The minimum daily balance required for each account tier. If the mean"
        " daily balance in the main denomination falls below this, the monthly"
        " maintenance fee will be charged if no other waive criteria are satisfied."
        " The calculation is performed every month on the anniversary of the account"
        " opening day, for each day since the last calculation. It takes samples of"
        " the balance at the fee application time. If set a minimum balance fee will"
        " also be applied.",
        display_name="Minimum balance threshold",
        shape=StringShape,
        default_value=json_dumps({"US_CHECKING_ACCOUNT_TIER_DEFAULT": "1500"}),
    ),
    Parameter(
        name="minimum_combined_balance_threshold",
        level=Level.TEMPLATE,
        description=" Only applicable if the account has been added to a supervisor plan."
        " The minimum combined daily checking and savings account balance required for"
        " each account tier. If the mean combined daily balance in the main"
        " denomination falls below this, the monthly maintenance fee will be charged if"
        " no other waive criteria are satisfied. The calculation is performed every"
        " month, for each day since the last calculation. It takes samples of the"
        " balances at the fee application time.",
        display_name="Minimum combined balance threshold",
        shape=StringShape,
        default_value=json_dumps({"US_CHECKING_ACCOUNT_TIER_DEFAULT": "5000"}),
    ),
    Parameter(
        name="minimum_deposit_threshold",
        level=Level.TEMPLATE,
        description="The minimum deposit amount required for each account tier. If the minimum "
        " deposit is reached the monthly maintenance fee will not be charged.",
        display_name="Minimum deposit threshold",
        shape=StringShape,
        default_value=json_dumps({"US_CHECKING_ACCOUNT_TIER_DEFAULT": "500"}),
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
        name="fees_application_day",
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=Level.TEMPLATE,
        description="The day of the month on which fees are applied. For months with fewer than the"
        " set value the last day of the month will be used",
        display_name="Fees application day",
        default_value=1,
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
    Parameter(
        name="maximum_daily_atm_withdrawal_limit",
        level=Level.TEMPLATE,
        description="Maximum daily amount from the main denomination that can be withdrawn by ATM."
        " If daily_atm_withdrawal_limit is set to -1 however then it is unlimited.",
        display_name="Maximum daily ATM withdrawal limit",
        shape=StringShape,
        default_value=json_dumps({"US_CHECKING_ACCOUNT_TIER_DEFAULT": "0"}),
    ),
    Parameter(
        name="transaction_code_to_type_map",
        level=Level.TEMPLATE,
        description="Map of transaction codes to transaction types" " (map format - encoded json).",
        display_name="Map of transaction types",
        shape=StringShape,
        default_value=json_dumps({"6011": "ATM withdrawal", "3123": "eCommerce"}),
    ),
    Parameter(
        name="transaction_types",
        level=Level.TEMPLATE,
        description="List of supported transaction types for account (list format - encoded json).",
        display_name="Account supported transaction types",
        shape=StringShape,
        default_value=json_dumps(["purchase", "ATM withdrawal", "transfer"]),
    ),
    Parameter(
        name="autosave_rounding_amount",
        level=Level.TEMPLATE,
        description="For any given spend with the primary denomination, this is the figure to "
        "round up to: the nearest multiple higher than the purchase amount. "
        "Only used if autosave_savings_account is defined.",
        display_name="Autosave rounding amount",
        shape=MoneyShape,
        default_value=Decimal("1.00"),
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
        shape=AccountIdShape,
        default_value="OVERDRAFT_FEE_INCOME",
    ),
    Parameter(
        name="overdraft_fee_receivable_account",
        level=Level.TEMPLATE,
        description="Internal account for overdraft fee receivable balance.",
        display_name="Overdraft fee receivable account",
        shape=AccountIdShape,
        default_value="OVERDRAFT_FEE_RECEIVABLE",
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
        display_name="Minimum balance fee income account",
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
        name="optional_standard_overdraft_coverage",
        level=Level.TEMPLATE,
        description="The transaction types that are covered by the standard overdraft if "
        "enabled with STANDARD_OVERDRAFT_TRANSACTION_COVERAGE flag. If a customer does not "
        "opt into standard overdraft transaction coverage, then transactions of these types "
        "will be rejected if standard overdraft is required for them. All "
        "other transaction types can use standard overdraft.",
        display_name="Optional standard overdraft Coverage",
        shape=StringShape,
        default_value=json_dumps(["ATM withdrawal", "eCommerce"]),
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
            SharedFunction(name="get_parameter"),
            SharedFunction(name="get_transaction_type"),
        ],
    ),
]


@requires(modules=["utils"], parameters=True)
def execution_schedules():
    account_creation_date = vault.get_account_creation_date()
    interest_application_frequency = vault.modules["utils"].get_parameter(
        vault, "deposit_interest_application_frequency", union=True
    )

    # Every day at time set by template parameters
    accrue_interest_schedule = _get_accrue_interest_schedule(vault)

    # Every month on day and time set by template parameters
    apply_accrued_overdraft_interest_schedule = _get_next_apply_accrued_interest_schedule(
        vault, account_creation_date
    )
    # Whole schedule is defined by template parameters. Can be monthly, quarterly or annually
    apply_accrued_deposit_interest_schedule = _get_next_apply_accrued_interest_schedule(
        vault, account_creation_date, interest_application_frequency
    )
    # Every month at day and time set by template parameters
    apply_monthly_fees_schedule = _get_next_fee_schedule(
        vault, account_creation_date, timedelta(months=1)
    )
    # Every year at day and time set by template parameters
    apply_annual_fees_schedule = _get_next_fee_schedule(
        vault, account_creation_date, timedelta(years=1)
    )
    return [
        ("ACCRUE_INTEREST_AND_DAILY_FEES", accrue_interest_schedule),
        ("APPLY_ACCRUED_OVERDRAFT_INTEREST", apply_accrued_overdraft_interest_schedule),
        ("APPLY_ACCRUED_DEPOSIT_INTEREST", apply_accrued_deposit_interest_schedule),
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
    postings="32 days",
)
@requires(
    modules=["interest", "utils"],
    event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
    flags=True,
    parameters=True,
    balances="31 days",
    postings="31 days",
    last_execution_time=["APPLY_MONTHLY_FEES"],
)
@requires(
    modules=["interest", "utils"],
    event_type="APPLY_ACCRUED_OVERDRAFT_INTEREST",
    parameters=True,
    balances="latest",
)
@requires(
    modules=["interest", "utils"],
    event_type="APPLY_ACCRUED_DEPOSIT_INTEREST",
    parameters=True,
    balances="latest",
)
def scheduled_code(event_type, effective_date):
    if event_type == "ACCRUE_INTEREST_AND_DAILY_FEES":
        end_of_day = effective_date - timedelta(microseconds=1)
        instructions = _accrue_interest(vault, end_of_day)
        instructions.extend(_accrue_fees(vault, end_of_day))
        _instruct_posting_batch(vault, instructions, end_of_day, event_type)

    elif event_type == "APPLY_ACCRUED_OVERDRAFT_INTEREST":
        instructions = _process_accrued_interest(
            vault,
            "OVERDRAFT",
        )
        _instruct_posting_batch(vault, instructions, effective_date, event_type)

        vault.amend_schedule(
            event_type="APPLY_ACCRUED_OVERDRAFT_INTEREST",
            new_schedule=_get_next_apply_accrued_interest_schedule(vault, effective_date),
        )

    elif event_type == "APPLY_ACCRUED_DEPOSIT_INTEREST":
        instructions = _process_accrued_interest(
            vault,
            "DEPOSIT",
        )
        _instruct_posting_batch(vault, instructions, effective_date, event_type)

        deposit_interest_application_frequency = vault.modules["utils"].get_parameter(
            vault, "deposit_interest_application_frequency", union=True
        )

        vault.amend_schedule(
            event_type="APPLY_ACCRUED_DEPOSIT_INTEREST",
            new_schedule=_get_next_apply_accrued_interest_schedule(
                vault, effective_date, deposit_interest_application_frequency
            ),
        )

    elif event_type == "APPLY_MONTHLY_FEES":
        instructions = _apply_accrued_fees(vault, effective_date)
        instructions.extend(_apply_monthly_fees(vault, effective_date))
        _instruct_posting_batch(vault, instructions, effective_date, event_type)

        vault.amend_schedule(
            event_type="APPLY_MONTHLY_FEES",
            new_schedule=_get_next_fee_schedule(vault, effective_date, timedelta(months=1)),
        )

    elif event_type == "APPLY_ANNUAL_FEES":
        instructions = _apply_annual_fees(vault, effective_date)
        _instruct_posting_batch(vault, instructions, effective_date, event_type)

        vault.amend_schedule(
            event_type="APPLY_ANNUAL_FEES",
            new_schedule=_get_next_fee_schedule(vault, effective_date, timedelta(years=1)),
        )


@requires(
    modules=["utils"],
    parameters=True,
    flags=True,
    balances="latest live",
    postings="1 day",
)
def pre_posting_code(postings, effective_date):
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
    # Ensure the main denomination is included in the check
    additional_denominations.append(main_denomination)
    accepted_denominations = set(additional_denominations)

    # Check denominations
    posting_denominations = {posting.denomination for posting in postings}
    unallowed_denominations = sorted(posting_denominations.difference(accepted_denominations))

    if unallowed_denominations:
        raise Rejected(
            f'Postings received in unauthorised denominations {", ".join(unallowed_denominations)}.'
            f' Authorised denominations are {", ".join(accepted_denominations)}',
            reason_code=RejectedReason.WRONG_DENOMINATION,
        )

    # Check available balances across denomination
    balances = vault.get_balance_timeseries().latest()
    for denomination in posting_denominations:
        available_balance = _get_outgoing_available_balance(balances, denomination)
        proposed_delta = _get_outgoing_available_balance(postings.balances(), denomination)
        # Main denomination has the ability to support an overdraft
        if denomination == main_denomination:
            standard_overdraft_limit = vault.modules["utils"].get_parameter(
                vault, "standard_overdraft_limit"
            )
            proposed_outgoing_balance = available_balance + proposed_delta
            if (
                proposed_outgoing_balance < 0
                and _has_transaction_type_not_covered_by_standard_overdraft(vault, postings)
            ):
                raise Rejected(
                    "Posting requires standard overdraft yet transaction type is not covered.",
                    reason_code=RejectedReason.INSUFFICIENT_FUNDS,
                )
            elif proposed_delta <= 0 and proposed_outgoing_balance < -standard_overdraft_limit:
                raise Rejected(
                    "Posting exceeds standard_overdraft_limit.",
                    reason_code=RejectedReason.INSUFFICIENT_FUNDS,
                )
        elif 0 > proposed_delta and 0 > proposed_delta + available_balance:
            raise Rejected(
                f"Postings total {denomination} {proposed_delta}, which exceeds the available"
                f" balance of {denomination} {available_balance}",
                reason_code=RejectedReason.INSUFFICIENT_FUNDS,
            )

    # Do this after overall available balance checks as it is much more expensive
    client_transactions = vault.get_client_transactions(include_proposed=True)
    _check_transaction_type_limits(
        vault, postings, client_transactions, main_denomination, effective_date
    )


@requires(
    modules=["utils"],
    parameters=True,
    balances="1 day",
    postings="31 days",
    last_execution_time=["APPLY_MONTHLY_FEES"],
)
def post_posting_code(postings, effective_date):
    main_denomination = vault.modules["utils"].get_parameter(name="denomination", vault=vault)
    autosave_rounding_amount = vault.modules["utils"].get_parameter(
        name="autosave_rounding_amount", vault=vault
    )
    autosave_savings_account = vault.modules["utils"].get_parameter(
        name="autosave_savings_account", vault=vault
    )

    offset_amount = 0
    instructions = []

    if _valid_linked_account(autosave_savings_account):
        offset_amount, instructions = _autosave_from_purchase(
            vault,
            postings,
            effective_date,
            main_denomination,
            autosave_savings_account.value,
            autosave_rounding_amount,
        )

    instructions.extend(
        _charge_overdraft_per_transaction_fee(
            vault, postings, -offset_amount, main_denomination, effective_date
        )
    )
    _instruct_posting_batch(vault, instructions, effective_date, "POST_POSTING")


def _charge_overdraft_per_transaction_fee(
    vault, postings, offset_amount, denomination, effective_date
):
    balances = vault.get_balance_timeseries().before(timestamp=effective_date)
    overdraft_per_transaction_fee = vault.modules["utils"].get_parameter(
        vault, name="standard_overdraft_per_transaction_fee"
    )
    fee_free_overdraft_limit = vault.modules["utils"].get_parameter(
        vault, name="fee_free_overdraft_limit"
    )
    overdraft_fee_income_account = vault.modules["utils"].get_parameter(
        vault, name="overdraft_fee_income_account"
    )

    standard_overdraft_fee_cap = vault.modules["utils"].get_parameter(
        vault, name="standard_overdraft_fee_cap"
    )
    if not standard_overdraft_fee_cap == 0:
        standard_overdraft_daily_fee_balance = balances[
            (
                "ACCRUED_OVERDRAFT_FEE_RECEIVABLE",
                DEFAULT_ASSET,
                denomination,
                Phase.COMMITTED,
            )
        ].net
        od_per_transaction_fee_charged = _get_overdraft_per_transaction_fee_charged(vault)
        total_overdraft_fees_charged = (
            -od_per_transaction_fee_charged + standard_overdraft_daily_fee_balance
        )

    balance_before = balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
    proposed_amount = _get_committed_default_balance_from_postings(postings, denomination)
    latest_balance = balance_before + proposed_amount
    effective_balance = latest_balance + offset_amount
    posting_instructions = []
    if overdraft_per_transaction_fee > 0:
        counter = 0
        for posting in sorted(postings, key=lambda posting: posting.amount):
            posting_against_default_address = posting.type in (
                PostingInstructionType.HARD_SETTLEMENT,
                PostingInstructionType.SETTLEMENT,
                PostingInstructionType.TRANSFER,
            ) or (
                posting.type == PostingInstructionType.CUSTOM_INSTRUCTION
                and posting.account_address == DEFAULT_ADDRESS
            )
            if not standard_overdraft_fee_cap == 0:
                total_proposed_od_fees = (
                    total_overdraft_fees_charged - overdraft_per_transaction_fee
                )
            if (
                posting_against_default_address
                and posting.credit is False
                and effective_balance < -fee_free_overdraft_limit
                and (
                    standard_overdraft_fee_cap == 0
                    or total_proposed_od_fees >= -standard_overdraft_fee_cap
                )
            ):
                if not standard_overdraft_fee_cap == 0:
                    total_overdraft_fees_charged = total_proposed_od_fees
                posting_instructions.extend(
                    vault.make_internal_transfer_instructions(
                        amount=overdraft_per_transaction_fee,
                        denomination=denomination,
                        client_transaction_id=f"{INTERNAL_POSTING}_STANDARD_OVERDRAFT_"
                        f"TRANSACTION_FEE_{vault.get_hook_execution_id()}_"
                        f"{denomination}_{posting.client_transaction_id}_"
                        f"{counter}",
                        from_account_id=vault.account_id,
                        from_account_address=DEFAULT_ADDRESS,
                        to_account_id=overdraft_fee_income_account,
                        to_account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        instruction_details={
                            "description": "Applying standard overdraft transaction fee for"
                            f" {posting.client_transaction_id}",
                            "event": "STANDARD_OVERDRAFT",
                        },
                    )
                )
                counter += 1
            effective_balance += -posting.amount if posting.credit else posting.amount

    return posting_instructions


def _autosave_from_purchase(
    vault,
    postings: List[PostingInstruction],
    effective_date: datetime,
    denomination: str,
    autosave_savings_account: Decimal,
    autosave_rounding_amount: Decimal,
) -> Tuple[Decimal, List[PostingInstruction]]:
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
    :param vault:
    :param postings: postings to process
    :param effective_date: date the postings are being processed on
    :param denomination: account denomination
    :param autosave_savings_account: the chosen savings account for autosave
    :param autosave_rounding_amount: the amount to round up to and save
    :return: amount saved, posting instructions
    """
    total_savings = Decimal(0)
    minimum_balance_fee = vault.modules["utils"].get_parameter(
        name="minimum_balance_fee", vault=vault
    )
    balances = vault.get_balance_timeseries().before(timestamp=effective_date)
    available_balance_before = _get_available_balance(balances, denomination)
    proposed_amount = _get_committed_default_balance_from_postings(postings, denomination)
    available_balance = available_balance_before + proposed_amount
    autosave_rounding_amount = Decimal(autosave_rounding_amount)
    posting_instructions = []

    if available_balance <= 0 or minimum_balance_fee > 0 or not autosave_savings_account:
        return total_savings, posting_instructions

    txn_code_to_type_map = vault.modules["utils"].get_parameter(
        name="transaction_code_to_type_map", is_json=True, vault=vault
    )
    for posting in postings:
        txn_type = vault.modules["utils"].get_transaction_type(
            posting.instruction_details,
            txn_code_to_type_map,
            DEFAULT_TRANSACTION_TYPE,
        )
        remainder = posting.amount % autosave_rounding_amount
        save_amount = 0
        if remainder > 0:
            save_amount = autosave_rounding_amount - remainder
        if (
            txn_type == "PURCHASE"
            and posting.denomination == denomination
            and posting.account_address == "DEFAULT"
            and not posting.credit
            and save_amount > 0
        ):
            total_savings += save_amount
    if total_savings > 0 and available_balance - total_savings > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=total_savings,
                denomination=denomination,
                client_transaction_id=f"{EXTERNAL_POSTING}_AUTOSAVE_"
                f"{vault.get_hook_execution_id()}",
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
        )
    else:
        total_savings = 0
    return total_savings, posting_instructions


def _valid_linked_account(linked_account_id_param):
    if linked_account_id_param.is_set():
        return True
    else:
        return False


def _check_transaction_type_limits(
    vault, postings, client_transactions, denomination, effective_date
):

    """
    Rejects any postings that breach their transaction type credit limit (e.g.
    cash advances may be limited to 1000 of local currency unit even though
    overall credit limit may be 2000 of local currency unit)
    Note: this should be done last in pre-posting hook as it is more intensive than standard checks
    :param vault:
    :param postings:  postings to process
    :param client_transactions: dict, keyed by (client_id, client_transaction_id)
    :param denomination: account denomination
    :param effective_date: date the postings are being processed on
    :return: none - raises a Rejected exception if any posting has breached its transaction type
    limit
    """

    daily_atm_withdrawal_limit = vault.modules["utils"].get_parameter(
        vault, name="daily_atm_withdrawal_limit"
    )
    txn_code_to_type_map = vault.modules["utils"].get_parameter(
        name="transaction_code_to_type_map", is_json=True, vault=vault
    )

    # get total amount in batch per transaction type
    for posting in postings:
        txn_type = vault.modules["utils"].get_transaction_type(
            posting.instruction_details,
            txn_code_to_type_map,
            DEFAULT_TRANSACTION_TYPE,
        )
        # Check ONLY Primary Denomination
        if txn_type == "ATM withdrawal" and posting.denomination == denomination:
            client_transaction = client_transactions.get(
                (posting.client_id, posting.client_transaction_id)
            )
            effects = client_transaction.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)]
            amount_authed = max(abs(effects.authorised - effects.released), abs(effects.settled))

            # amount_withdrawal is -ve.
            amount_withdrawal = _sum_other_atm_transactions_today(
                vault,
                denomination,
                client_transactions,
                posting.client_transaction_id,
                effective_date + timedelta(hour=0, minute=0, second=0, microsecond=0),
                txn_code_to_type_map,
            )

            if not posting.credit:
                # Check daily withdrawal limit
                if (
                    daily_atm_withdrawal_limit != -1
                    and amount_authed - amount_withdrawal > daily_atm_withdrawal_limit
                ):
                    raise Rejected(
                        "Transaction would cause the ATM"
                        " daily withdrawal limit of %s %s to be exceeded."
                        % (daily_atm_withdrawal_limit, denomination),
                        reason_code=RejectedReason.AGAINST_TNC,
                    )


def _sum_other_atm_transactions_today(
    vault,
    denomination,
    client_transactions,
    client_transaction_id,
    cutoff_timestamp,
    txn_code_to_type_map,
):
    """
    Sum all ATM withdrawals for default address in client_transactions since
    cutoff, excluding any cancelled or the current transaction.
    Return amount withdrawn from ATM since cutoff.

    :param denomination: string
    :param client_transactions: dict, keyed by (client_id, client_transaction_id)
    :param client_transaction_id: string
    :param cutoff_timestamp: datetime
    :param txn_code_to_type_map: dict
    :return: Sum of ATM transactions, which is -ve for withdrawals
    """

    def _is_atm_posting_today(posting):
        return (
            not posting.credit
            and posting.denomination == denomination
            and posting.value_timestamp >= cutoff_timestamp
            and posting.asset == DEFAULT_ASSET
            and vault.modules["utils"].get_transaction_type(
                posting.instruction_details,
                txn_code_to_type_map,
                DEFAULT_TRANSACTION_TYPE,
            )
            == "ATM withdrawal"
        )

    return -sum(
        sum(posting.amount for posting in transaction if _is_atm_posting_today(posting))
        for (_, transaction_id), transaction in client_transactions.items()
        if transaction_id != client_transaction_id and not transaction.cancelled
    )


@requires(modules=["utils"], flags=True, parameters=True)
def pre_parameter_change_code(parameters, effective_date):
    if "daily_atm_withdrawal_limit" in parameters:
        max_atm = vault.modules["utils"].get_parameter(
            vault, name="maximum_daily_atm_withdrawal_limit", is_json=True
        )

        tier_names = vault.modules["utils"].get_parameter(vault, name="tier_names", is_json=True)
        this_account_flags = _get_active_account_flags(vault, tier_names)
        max_atm = _get_dict_value_based_on_account_tier_flag(
            account_tier_flags=this_account_flags,
            tiered_param=max_atm,
            tier_names=tier_names,
            convert=Decimal,
        )
        parameters["daily_atm_withdrawal_limit"].shape.max_value = max_atm
    return parameters


@requires(modules=["interest", "utils"], parameters=True, balances="latest")
def close_code(effective_date: datetime):
    instructions = _process_accrued_interest(vault, "OVERDRAFT")
    instructions.extend(_reverse_accrued_interest_on_account_closure(vault, effective_date))
    instructions.extend(_apply_accrued_fees(vault, effective_date))
    _instruct_posting_batch(vault, instructions, effective_date, "CLOSE")


def _accrue_interest(vault, effective_date: datetime) -> List[PostingInstruction]:
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
    # Load parameters and flags

    interest_free_buffer_amount_tiers = vault.modules["utils"].get_parameter(
        name="interest_free_buffer", is_json=True, vault=vault
    )
    interest_free_buffer_days_tiers = vault.modules["utils"].get_parameter(
        name="overdraft_interest_free_buffer_days", is_json=True, vault=vault
    )
    tier_names = vault.modules["utils"].get_parameter(name="tier_names", is_json=True, vault=vault)
    this_account_flags = _get_active_account_flags(vault, tier_names)
    denomination = vault.modules["utils"].get_parameter(name="denomination", vault=vault)

    # Load balances
    balances = vault.get_balance_timeseries().at(timestamp=effective_date)
    effective_balance = balances[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net

    # Load tier information
    interest_free_buffer_amount = _get_dict_value_based_on_account_tier_flag(
        account_tier_flags=this_account_flags,
        tiered_param=interest_free_buffer_amount_tiers,
        tier_names=tier_names,
        convert=Decimal,
    )
    interest_free_buffer_days = _get_dict_value_based_on_account_tier_flag(
        account_tier_flags=this_account_flags,
        tiered_param=interest_free_buffer_days_tiers,
        tier_names=tier_names,
        convert=Decimal,
    )

    outside_overdraft_buffer_period = _is_outside_overdraft_buffer_period(
        vault, interest_free_buffer_days, effective_date, denomination
    )
    # Remove interest free buffer amount if outside of the interest free buffer period
    if outside_overdraft_buffer_period:
        interest_free_buffer_amount = Decimal("0.00")

    # Overdraft Check
    if effective_balance < -interest_free_buffer_amount or outside_overdraft_buffer_period:

        overdraft_rate = vault.modules["utils"].get_parameter(
            name="overdraft_interest_rate",
            vault=vault,
        )
        balance_tier_ranges = {
            "overdraft": {
                "rate": overdraft_rate,
                "max": -interest_free_buffer_amount,
            }
        }
        receivable_address = "ACCRUED_OVERDRAFT_RECEIVABLE"
        payable_address = None

    elif effective_balance > Decimal("0"):
        # Deposit Check
        balance_tier_ranges = vault.modules["utils"].get_parameter(
            vault, "deposit_tier_ranges", is_json=True
        )
        deposit_interest_rate_tiers = vault.modules["utils"].get_parameter(
            vault, name="deposit_interest_rate_tiers", is_json=True
        )
        for tier, rate in deposit_interest_rate_tiers.items():
            balance_tier_ranges[tier]["rate"] = rate

        receivable_address = "ACCRUED_DEPOSIT_RECEIVABLE"
        payable_address = "ACCRUED_DEPOSIT_PAYABLE"
    else:
        return []

    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        payable_address=payable_address,
        receivable_address=receivable_address,
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
        balance=effective_balance,
        rates=balance_tier_ranges,
        denomination=denomination,
        payable_receivable_mapping=payable_receivable_mapping,
        base=vault.modules["utils"].get_parameter(
            name="interest_accrual_days_in_year", vault=vault, union=True
        ),
        net_postings=False,
    )

    return vault.modules["interest"].accrue_interest(
        vault,
        [accrual_details],
        "LIABILITY",
        effective_date,
        event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
    )


def _reverse_accrued_interest_on_account_closure(
    vault,
    effective_date: datetime,
) -> List[PostingInstruction]:
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    balances = vault.get_balance_timeseries().at(timestamp=effective_date)

    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        payable_address="ACCRUED_DEPOSIT_PAYABLE",
        receivable_address="ACCRUED_DEPOSIT_RECEIVABLE",
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

    return vault.modules["interest"].reverse_interest(
        vault,
        balances=balances,
        interest_dimensions=[accrual_details],
        account_tside="LIABILITY",
        event_type="CLOSE_ACCOUNT",
    )


def _apply_monthly_fees(vault, effective_date: datetime) -> List[PostingInstruction]:
    """
    Applies maintenance fees to the account. By design these are not accrued
    daily on a pro-rata basis but applied when due monthly. When the account is
    closed they are not prorated.
    The monthly maintenance fee may be waived if any of the following criteria are met:
    1) The minimum daily balance threshold is satisfied for the period
    2) The minimum deposit threshold is satisfied for the period
    Other fees that may be applied include:
    * Account inactivity fee
    * Minimum balance fee

    :param vault: Vault object
    :param effective_date: date and time of hook being run

    :return: posting instructions
    """

    # Load parameters
    maintenance_fee_income_account = vault.modules["utils"].get_parameter(
        vault, name="maintenance_fee_income_account"
    )
    inactivity_fee_income_account = vault.modules["utils"].get_parameter(
        vault, name="inactivity_fee_income_account"
    )
    minimum_balance_fee_income_account = vault.modules["utils"].get_parameter(
        vault, name="minimum_balance_fee_income_account"
    )

    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    minimum_balance_fee = vault.modules["utils"].get_parameter(vault, name="minimum_balance_fee")
    account_inactivity_fee = vault.modules["utils"].get_parameter(
        vault, name="account_inactivity_fee"
    )
    tier_names = vault.modules["utils"].get_parameter(name="tier_names", is_json=True, vault=vault)
    monthly_fee_tiers = _get_monthly_maintenance_fee_tiers(vault)
    minimum_balance_tiers = vault.modules["utils"].get_parameter(
        name="minimum_balance_threshold", is_json=True, vault=vault
    )
    minimum_deposit_tiers = vault.modules["utils"].get_parameter(
        name="minimum_deposit_threshold", is_json=True, vault=vault
    )

    # Load flags
    this_account_flags = _get_active_account_flags(vault, tier_names)
    is_account_dormant = vault.get_flag_timeseries(flag=DORMANCY_FLAG).latest()

    # Load tier information
    monthly_fee = _get_dict_value_based_on_account_tier_flag(
        account_tier_flags=this_account_flags,
        tiered_param=monthly_fee_tiers,
        tier_names=tier_names,
        convert=Decimal,
    )
    minimum_balance = _get_dict_value_based_on_account_tier_flag(
        account_tier_flags=this_account_flags,
        tiered_param=minimum_balance_tiers,
        tier_names=tier_names,
        convert=Decimal,
    )
    minimum_deposit = _get_dict_value_based_on_account_tier_flag(
        account_tier_flags=this_account_flags,
        tiered_param=minimum_deposit_tiers,
        tier_names=tier_names,
        convert=Decimal,
    )

    # Determine if maintenance fee should be applied
    monthly_mean_balance = _monthly_mean_balance(vault, denomination, effective_date)
    apply_maintenance_fee = (
        not is_account_dormant
        and monthly_fee > 0
        and monthly_mean_balance < minimum_balance
        and _sum_deposit_transactions(vault, effective_date) < minimum_deposit
    )

    # Post monthly maintenance fee if applicable
    posting_instructions = []
    if apply_maintenance_fee:
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
                client_transaction_id=f"{INTERNAL_POSTING}_APPLY_MONTHLY_FEES"
                f"_MAINTENANCE"
                f"_{vault.get_hook_execution_id()}"
                f"_{denomination}",
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
                client_transaction_id=f"{INTERNAL_POSTING}_APPLY_MONTHLY_FEES"
                f"_INACTIVITY"
                f"_{vault.get_hook_execution_id()}"
                f"_{denomination}",
                instruction_details={
                    "description": "Account inactivity fee",
                    "event": "APPLY_MONTHLY_FEES",
                },
            )
        )

    # If minimum balance fee is enabled, and balance fell below threshold, apply it
    if not is_account_dormant and minimum_balance_fee != 0:
        if monthly_mean_balance < minimum_balance:
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
                    client_transaction_id=f"{INTERNAL_POSTING}_APPLY_MONTHLY_FEES"
                    f"_MEAN_BALANCE"
                    f"_{vault.get_hook_execution_id()}"
                    f"_{denomination}",
                    instruction_details={
                        "description": "Minimum balance fee",
                        "event": "APPLY_MONTHLY_FEES",
                    },
                )
            )

    return posting_instructions


def _apply_annual_fees(vault, effective_date: datetime) -> List[PostingInstruction]:
    """
    Applies maintenance fees to the account. By design these are not accrued
    daily on a pro-rata basis but applied when due yearly. When the account is
    closed they are not prorated.

    :param vault: Vault object
    :param effective_date: date and time of hook being run

    :return: posting instructions
    """
    annual_maintenance_fee_income_account = vault.modules["utils"].get_parameter(
        vault, name="annual_maintenance_fee_income_account"
    )
    annual_fee = vault.modules["utils"].get_parameter(vault, name="maintenance_fee_annual")
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
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
                client_transaction_id=f"{INTERNAL_POSTING}_APPLY_ANNUAL_FEES"
                f"_{vault.get_hook_execution_id()}"
                f"_{denomination}",
                instruction_details={
                    "description": "Annual maintenance fee",
                    "event": "APPLY_ANNUAL_FEES",
                },
            )
        )

    return posting_instructions


def _accrue_fees(vault, effective_date: datetime) -> List[PostingInstruction]:
    """
    Accrues to the accrued outgoing address an overdraft fee if balance is below
    fee free overdraft limit, up to overdraft fee cap.

    :param vault: Vault object
    :param effective_date: date and time of hook being run

    :return: posting instructions
    """
    overdraft_fee_income_account = vault.modules["utils"].get_parameter(
        vault, name="overdraft_fee_income_account"
    )
    overdraft_fee_receivable_account = vault.modules["utils"].get_parameter(
        vault, name="overdraft_fee_receivable_account"
    )
    fee_free_overdraft_limit = vault.modules["utils"].get_parameter(
        vault, name="fee_free_overdraft_limit"
    )
    standard_overdraft_daily_fee = vault.modules["utils"].get_parameter(
        vault, name="standard_overdraft_daily_fee"
    )
    standard_overdraft_fee_cap = vault.modules["utils"].get_parameter(
        vault, name="standard_overdraft_fee_cap"
    )
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    balances = vault.get_balance_timeseries().latest()

    effective_balance = balances[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net

    if not standard_overdraft_fee_cap == 0:
        standard_overdraft_daily_fee_balance = balances[
            (
                "ACCRUED_OVERDRAFT_FEE_RECEIVABLE",
                DEFAULT_ASSET,
                denomination,
                Phase.COMMITTED,
            )
        ].net
        od_per_transaction_fee_charged = _get_overdraft_per_transaction_fee_charged(vault)
        total_overdraft_fees_charged = (
            -od_per_transaction_fee_charged + standard_overdraft_daily_fee_balance
        )
        total_proposed_od_fees = total_overdraft_fees_charged - standard_overdraft_daily_fee

    posting_instructions = []
    if (
        standard_overdraft_daily_fee > 0
        and effective_balance < -fee_free_overdraft_limit
        and (
            standard_overdraft_fee_cap == 0 or total_proposed_od_fees >= -standard_overdraft_fee_cap
        )
    ):
        payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
            receivable_address="ACCRUED_OVERDRAFT_FEE_RECEIVABLE",
            receivable_internal_account=overdraft_fee_receivable_account,
            received_internal_account=overdraft_fee_income_account,
        )
        fee_details = vault.modules["interest"].construct_fee_details(
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=denomination,
            fee={"Standard Overdraft": -standard_overdraft_daily_fee},
        )
        posting_instructions.extend(
            vault.modules["interest"].accrue_fees(
                vault,
                fee_details=[fee_details],
                account_tside="LIABILITY",
                event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
            )
        )
    return posting_instructions


def _process_accrued_interest(
    vault,
    interest_type: str,
) -> List[PostingInstruction]:
    """
    Processes any accrued interest by either applying it to the customers default account,
    or reversing and returning the accrued amounts back to the bank.

    :param vault: Vault object
    :param interest_type: either "OVERDRAFT" or "DEPOSIT"
                          to identify the type of posting being made

    :return: posting instructions
    """
    if interest_type == "DEPOSIT":
        payable_address = "ACCRUED_DEPOSIT_PAYABLE"
        receivable_address = "ACCRUED_DEPOSIT_RECEIVABLE"
    else:
        payable_address = None
        receivable_address = "ACCRUED_OVERDRAFT_RECEIVABLE"

    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        payable_address=payable_address,
        receivable_address=receivable_address,
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

    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    balances = vault.get_balance_timeseries().latest()

    charge_details = vault.modules["interest"].construct_charge_application_details(
        denomination=denomination,
        payable_receivable_mapping=payable_receivable_mapping,
        zero_out_remainder=True,
        instruction_description=f"Accrued {interest_type.lower()} interest applied.",
    )
    return vault.modules["interest"].apply_charges(
        vault,
        balances=balances,
        charge_details=[charge_details],
        account_tside="LIABILITY",
        event_type=f"APPLY_ACCRUED_{interest_type}_INTEREST",
    )


def _apply_accrued_fees(vault, effective_date: datetime) -> List[PostingInstruction]:
    """
    Applies any accrued overdraft fees to the customer account's default address

    :param vault: Vault object
    :param effective_date: date and time of hook being run

    :return: posting instructions
    """
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")

    balances = vault.get_balance_timeseries().latest()
    overdraft_fee_receivable_account = vault.modules["utils"].get_parameter(
        vault, name="overdraft_fee_receivable_account"
    )
    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        receivable_address="ACCRUED_OVERDRAFT_FEE_RECEIVABLE",
        receivable_internal_account=overdraft_fee_receivable_account,
        payable_internal_account="Main account",
    )
    charge_details = vault.modules["interest"].construct_charge_application_details(
        payable_receivable_mapping=payable_receivable_mapping,
        denomination=denomination,
        charge_type="FEES",
        instruction_description="Overdraft fees applied.",
        apply_address=DEFAULT_ADDRESS,
    )
    return vault.modules["interest"].apply_charges(
        vault,
        balances=balances,
        charge_details=[charge_details],
        account_tside="LIABILITY",
        event_type="APPLY_MONTHLY_FEES",
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


def _monthly_mean_balance(
    vault, denomination: str, effective_date: datetime, addresses: List[str] = None
):
    """
    Determine the average combined balance for the preceding month. The sampling period is from one
    month before, until the effective_date, exclusive i.e. not including the effective_date day,
    If the sampling time is before the account was opened then skip that day. Multiple addresses
    can be specified for the calculation.

    :param vault: Vault object
    :param denomination: Account denomination
    :param effective_date: datetime, date and time of hook being run
    :param addresses: list(str), list of addresses to sample and combine the balance for
    :return: Decimal, mean combined balance at sampling time for previous month
    """
    creation_date = vault.get_account_creation_date()
    addresses = addresses or [DEFAULT_ADDRESS]

    period_start = effective_date - timedelta(months=1)
    # Schedule should prevent period_start < creation_date but this guards against supervisor exec
    if period_start < creation_date:
        # Ensure we don't sample on creation date exactly and maintain sample hour, min, second
        period_start = creation_date + timedelta(
            hour=effective_date.hour,
            minute=effective_date.minute,
            second=effective_date.second,
        )
        # Should sample hour, min, second be before creation, skip to next day at the same time
        if period_start < creation_date:
            period_start += timedelta(days=1)

    # set num_days to 1 if it is smaller than 1 for whatever reason
    num_days = max((effective_date - period_start).days, 1)

    total = sum(
        sum(
            vault.get_balance_timeseries()
            .at(timestamp=period_start + timedelta(days=i))[
                (address, DEFAULT_ASSET, denomination, Phase.COMMITTED)
            ]
            .net
            for address in addresses
        )
        for i in range(num_days)
    )

    return total / num_days


def _get_outgoing_available_balance(balances, denomination):
    """
    Get the available balance on account for outgoing postings. Only settled funds are considered.
    Phase.PENDING_OUT net amount will be negative for outbound authorisations.

    :param balances: defaultdict of balance dimensions to balance object
    :param effective_date: datetime, date and time of hook being run
    :return: Decimal, available outgoing balance
    """
    committed_balance_net = balances[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    pending_out_balance_net = balances[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)
    ].net

    return committed_balance_net + pending_out_balance_net


def _sum_deposit_transactions(vault, effective_date: datetime):
    """
    Sum all deposit transactions for all given client_transactions in the monthly deposit window.
    Monthly deposit window is the last month, starting from account creation date.

    :param vault: Vault object
    :param effective_date: datetime
    :return: Decimal, sum of deposit transactions for monthly deposit window
    """
    denomination = vault.modules["utils"].get_parameter(vault, "denomination")
    client_transactions = vault.get_client_transactions()
    creation_date = vault.get_account_creation_date()
    period_start = effective_date - timedelta(months=1)
    if period_start < creation_date:
        period_start = creation_date

    total_deposit = sum(
        client_txn.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].settled
        for (_, client_txn_id), client_txn in client_transactions.items()
        if (
            INTERNAL_POSTING not in client_txn_id
            and EXTERNAL_POSTING not in client_txn_id
            and client_txn.start_time >= period_start
            and client_txn.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].settled > 0
        )
    )

    return total_deposit


# Helper functions for accruing and applying interest


def _is_outside_overdraft_buffer_period(
    vault, interest_free_buffer_days, effective_date, denomination
):
    """
    Check balances at midnight to see how long we have been in our overdraft buffer period for.
    If interest_free_buffer_days are set to -1, we will treat this as unlimited, leaving it up to
    the overdraft buffer amount to determine whether or not to accrue interest.

    :param vault: The vault object
    :param interest_free_buffer_days: int, the amount of buffer days
    :param effective_date: datetime, the current date of execution
    :param denomination: string, the denomination of this account
    :return: boolean, True if we are outside of the buffer period, False if inside
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
    interest_accrual_hour = vault.modules["utils"].get_parameter(
        vault, name="interest_accrual_hour"
    )

    interest_accrual_minute = vault.modules["utils"].get_parameter(
        vault, name="interest_accrual_minute"
    )

    interest_accrual_second = vault.modules["utils"].get_parameter(
        vault, name="interest_accrual_second"
    )

    interest_accrual_schedule = _create_schedule_dict_from_params(
        hour=interest_accrual_hour,
        minute=interest_accrual_minute,
        second=interest_accrual_second,
    )

    return interest_accrual_schedule


def _get_next_apply_accrued_interest_schedule(
    vault, effective_date, interest_application_frequency="monthly"
):
    """
    Sets up dictionary for the next interest application day, for both overdraft and deposit.
    :param vault: Vault object
    :param effective_date: datetime, date and time of hook being run
    :param interest_application_frequency: str, Either 'monthly', 'quarterly',
                                           or 'annually'. Defaults to monthly.
    :return: dict, representation of APPLY_ACCRUED_INTEREST schedule
    """
    interest_application_day = vault.modules["utils"].get_parameter(
        vault, name="interest_application_day"
    )

    apply_accrued_interest_date = _get_next_apply_accrued_interest_date(
        vault, interest_application_frequency, interest_application_day, effective_date
    )

    apply_accrued_interest_schedule = vault.modules["utils"].create_schedule_dict_from_datetime(
        apply_accrued_interest_date
    )

    return apply_accrued_interest_schedule


def _get_next_apply_accrued_interest_date(
    vault, interest_application_frequency, interest_application_day, effective_date
):
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
        vault, name="interest_application_hour"
    )

    interest_application_minute = vault.modules["utils"].get_parameter(
        vault, name="interest_application_minute"
    )

    interest_application_second = vault.modules["utils"].get_parameter(
        vault, name="interest_application_second"
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


def _get_next_fee_schedule(vault, effective_date, period):
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

    # First fees application event must be 1 period from creation
    next_schedule_date = effective_date + period + next_schedule_timedelta
    if next_schedule_date < creation_date + period:
        next_schedule_date += timedelta(months=1, day=fees_application_day)

    return vault.modules["utils"].create_schedule_dict_from_datetime(next_schedule_date)


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


def _get_next_schedule_date(start_date, schedule_frequency, intended_day):
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


def _get_overdraft_per_transaction_fee_charged(vault):
    """
    Get the amount of standard overdraft per-transaction fee that has been charged in the current
    period.
    :param vault: Vault object
    :return: Decimal, the total amount charged in the current period.
    """
    daily_fee_charged = Decimal("0")
    start_of_period = vault.get_last_execution_time(event_type="APPLY_MONTHLY_FEES")
    if not start_of_period:
        start_of_period = vault.get_account_creation_date()

    recent_postings = vault.get_postings(include_proposed=False)
    for posting in recent_postings:
        if (
            posting.value_timestamp > start_of_period
            and not posting.credit
            and posting.instruction_details.get("event") == "STANDARD_OVERDRAFT"
        ):
            daily_fee_charged += posting.amount

    return daily_fee_charged


def _get_monthly_maintenance_fee_tiers(vault):
    fee_to_use = (
        "promotional_maintenance_fee_monthly"
        if vault.get_flag_timeseries(flag=PROMOTIONAL_MAINTENANCE_FEE_FLAG).latest()
        else "maintenance_fee_monthly"
    )

    return vault.modules["utils"].get_parameter(name=fee_to_use, is_json=True, vault=vault)


def _has_transaction_type_not_covered_by_standard_overdraft(vault, postings):
    """
    Checks whether the transaction has a type that is not covered by standard overdraft

    :param vault: Vault object
    :param postings: postings to process
    :return: Boolean
    """
    txn_code_to_type_map = vault.modules["utils"].get_parameter(
        vault, "transaction_code_to_type_map", is_json=True
    )
    optional_standard_overdraft_coverage = vault.modules["utils"].get_parameter(
        vault, "optional_standard_overdraft_coverage", is_json=True
    )
    should_include_optional_standard_overdraft_coverage = vault.get_flag_timeseries(
        flag=STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG
    ).latest()
    return not should_include_optional_standard_overdraft_coverage and any(
        vault.modules["utils"].get_transaction_type(
            posting.instruction_details,
            txn_code_to_type_map,
            DEFAULT_TRANSACTION_TYPE,
        )
        in optional_standard_overdraft_coverage
        for posting in postings
        if _get_outgoing_available_balance(posting.balances(), posting.denomination) < 0
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
