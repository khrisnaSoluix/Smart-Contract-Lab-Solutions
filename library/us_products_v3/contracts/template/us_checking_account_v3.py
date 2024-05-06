# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.

# common imports
from library.features.v3.common.common_imports import *  # noqa: F403

# features
import library.features.v3.common.utils as utils

api = "3.12.0"
version = "1.9.4"
display_name = "US Checking Account"
summary = "An everyday banking account with optional standard overdraft facility"
" - great for those who like to bank on the go."
tside = Tside.LIABILITY

# this can be amended to whichever other currencies as needed
supported_denominations = ["USD"]
# account type
ACCOUNT_TYPE = "US_CHECKING"


# Instruction Detail keys
DEFAULT_TRANSACTION_TYPE = "PURCHASE"
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
        name="APPLY_ACCRUED_DEPOSIT_INTEREST",
        scheduler_tag_ids=["US_CHECKING_APPLY_ACCRUED_DEPOSIT_INTEREST_AST"],
    ),
    EventType(
        name="APPLY_MONTHLY_FEES",
        scheduler_tag_ids=["US_CHECKING_APPLY_MONTHLY_FEES_AST"],
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
        default_value=json_dumps(["DEFAULT_TIER"]),
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
        default_value=json_dumps({"DEFAULT_TIER": "10"}),
    ),
    Parameter(
        name="promotional_maintenance_fee_monthly",
        level=Level.TEMPLATE,
        description="The promotional monthly fee charged for account maintenance "
        "for each account tier. This fee can be "
        "waived subject to the same criteria as normal monthly maintenance fee.",
        display_name="Promotional monthly maintenance fee",
        shape=StringShape,
        default_value=json_dumps({"DEFAULT_TIER": "5"}),
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
        default_value=json_dumps({"DEFAULT_TIER": "1500"}),
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
        default_value=json_dumps({"DEFAULT_TIER": "5000"}),
    ),
    Parameter(
        name="minimum_deposit_threshold",
        level=Level.TEMPLATE,
        description="The minimum deposit amount required for each account tier. If the minimum "
        " deposit is reached the monthly maintenance fee will not be charged.",
        display_name="Minimum deposit threshold",
        shape=StringShape,
        default_value=json_dumps({"DEFAULT_TIER": "500"}),
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
        default_value=json_dumps({"DEFAULT_TIER": "0"}),
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
    Parameter(
        name="overdraft_protection_sweep_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which the overdraft protection sweep occurs.",
        display_name="Overdraft protection sweep hour",
        default_value=0,
    ),
    Parameter(
        name="overdraft_protection_sweep_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the hour at which the overdraft protection sweep occurs.",
        display_name="Overdraft protection sweep minute",
        default_value=1,
    ),
    Parameter(
        name="overdraft_protection_sweep_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the minute at which the overdraft protection sweep occurs.",
        display_name="Overdraft protection sweep second",
        default_value=0,
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
]


@requires(parameters=True)
def execution_schedules() -> list[tuple[str, dict[str, Any]]]:
    account_creation_date = vault.get_account_creation_date()
    interest_application_frequency = utils.get_parameter(
        vault, "deposit_interest_application_frequency", union=True
    )

    # Every day at time set by template parameters
    accrue_interest_schedule = _get_accrue_interest_schedule(vault)

    # Whole schedule is defined by template parameters. Can be monthly, quarterly or annually
    apply_accrued_deposit_interest_schedule = _get_next_apply_accrued_interest_schedule(
        vault, account_creation_date, interest_application_frequency
    )
    # Every month at day and time set by template parameters
    apply_monthly_fees_schedule = _get_next_fee_schedule(
        vault, account_creation_date, timedelta(months=1)
    )

    return [
        (accrue_interest_schedule.event_type, accrue_interest_schedule.schedule),
        ("APPLY_ACCRUED_DEPOSIT_INTEREST", apply_accrued_deposit_interest_schedule),
        ("APPLY_MONTHLY_FEES", apply_monthly_fees_schedule),
    ]


@requires(
    modules=["interest"],
    event_type="APPLY_MONTHLY_FEES",
    flags=True,
    parameters=True,
    balances="32 days",
    postings="32 days",
)
@requires(
    modules=["interest"],
    event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
    flags=True,
    parameters=True,
    balances="31 days",
    postings="31 days",
    last_execution_time=["APPLY_MONTHLY_FEES"],
)
@requires(
    modules=["interest"],
    event_type="APPLY_ACCRUED_DEPOSIT_INTEREST",
    parameters=True,
    balances="latest",
)
def scheduled_code(event_type: str, effective_date: datetime) -> None:
    if event_type == "ACCRUE_INTEREST_AND_DAILY_FEES":
        end_of_day = effective_date - timedelta(microseconds=1)
        instructions = _accrue_interest(vault, end_of_day)
        instructions.extend(_accrue_fees(vault, end_of_day))
        _instruct_posting_batch(vault, instructions, end_of_day, event_type)

    elif event_type == "APPLY_ACCRUED_DEPOSIT_INTEREST":
        instructions = _process_accrued_interest(vault)
        _instruct_posting_batch(vault, instructions, effective_date, event_type)

        deposit_interest_application_frequency = utils.get_parameter(
            vault, "deposit_interest_application_frequency", union=True
        )

        new_schedule = _get_next_apply_accrued_interest_schedule(
            vault, effective_date, deposit_interest_application_frequency
        )

        vault.update_event_type(
            event_type="APPLY_ACCRUED_DEPOSIT_INTEREST",
            schedule=utils.create_event_type_schedule_from_schedule_dict(new_schedule),
        )

    elif event_type == "APPLY_MONTHLY_FEES":
        instructions = _apply_accrued_fees(vault, effective_date)
        instructions.extend(_apply_monthly_fees(vault, effective_date))
        _instruct_posting_batch(vault, instructions, effective_date, event_type)

        new_schedule = _get_next_fee_schedule(vault, effective_date, timedelta(months=1))

        vault.update_event_type(
            event_type="APPLY_MONTHLY_FEES",
            schedule=utils.create_event_type_schedule_from_schedule_dict(new_schedule),
        )


@requires(
    parameters=True,
    flags=True,
    balances="latest live",
    postings="1 day",
)
def pre_posting_code(postings: PostingInstructionBatch, effective_date: datetime) -> None:
    is_account_dormant = vault.get_flag_timeseries(flag=DORMANCY_FLAG).latest()

    if is_account_dormant is True:
        raise Rejected(
            'Account flagged "Dormant" does not accept external transactions.',
            reason_code=RejectedReason.AGAINST_TNC,
        )

    main_denomination = utils.get_parameter(vault, "denomination")
    additional_denominations = utils.get_parameter(vault, "additional_denominations", is_json=True)
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
        available_balance = utils.get_available_balance(balances, denomination)
        proposed_delta = utils.get_available_balance(postings.balances(), denomination)
        # Main denomination has the ability to support an overdraft
        if denomination == main_denomination:
            standard_overdraft_limit = utils.get_parameter(vault, "standard_overdraft_limit")
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
    parameters=True,
    balances="1 day",
    postings="31 days",
    last_execution_time=["APPLY_MONTHLY_FEES"],
)
def post_posting_code(postings: PostingInstructionBatch, effective_date: datetime) -> None:
    main_denomination = utils.get_parameter(name="denomination", vault=vault)
    autosave_rounding_amount = utils.get_parameter(name="autosave_rounding_amount", vault=vault)
    autosave_savings_account = utils.get_parameter(name="autosave_savings_account", vault=vault)

    offset_amount = Decimal(0)
    instructions = []

    if autosave_savings_account.is_set():
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
    vault,
    postings: PostingInstructionBatch,
    offset_amount: Decimal,
    denomination: str,
    effective_date: datetime,
) -> list[PostingInstruction]:
    balances = vault.get_balance_timeseries().before(timestamp=effective_date)
    overdraft_per_transaction_fee = utils.get_parameter(
        vault, name="standard_overdraft_per_transaction_fee"
    )
    fee_free_overdraft_limit = utils.get_parameter(vault, name="fee_free_overdraft_limit")
    overdraft_fee_income_account = utils.get_parameter(vault, name="overdraft_fee_income_account")

    standard_overdraft_fee_cap = utils.get_parameter(vault, name="standard_overdraft_fee_cap")
    if not standard_overdraft_fee_cap == 0:
        standard_overdraft_daily_fee_balance = balances[
            (
                "ACCRUED_OVERDRAFT_FEE_RECEIVABLE",
                DEFAULT_ASSET,
                denomination,
                Phase.COMMITTED,
            )
        ].net
        od_per_transaction_fee_charged = _get_overdraft_per_transaction_fee_charged(
            vault, denomination
        )
        total_overdraft_fees_charged = (
            -od_per_transaction_fee_charged + standard_overdraft_daily_fee_balance
        )

    balance_before = balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
    proposed_amount = postings.balances()[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    latest_balance = balance_before + proposed_amount
    effective_balance = latest_balance + offset_amount
    posting_instructions = []
    if overdraft_per_transaction_fee > 0:
        counter = 0
        sorted_postings = sorted(
            postings,
            key=lambda posting: posting.balances()[
                DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
            ].net,
        )
        for posting in sorted_postings:
            posting_against_default_address = posting.balances()[
                DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
            ].net
            if not standard_overdraft_fee_cap == 0:
                total_proposed_od_fees = (
                    total_overdraft_fees_charged - overdraft_per_transaction_fee
                )
            if (
                posting_against_default_address < 0
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
            effective_balance += posting_against_default_address

    return posting_instructions


def _autosave_from_purchase(
    vault,
    postings: list[PostingInstruction],
    effective_date: datetime,
    denomination: str,
    autosave_savings_account: Decimal,
    autosave_rounding_amount: Decimal,
) -> tuple[Decimal, list[PostingInstruction]]:
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
    minimum_balance_fee = utils.get_parameter(name="minimum_balance_fee", vault=vault)
    balances = vault.get_balance_timeseries().before(timestamp=effective_date)
    available_balance_before = utils.get_available_balance(balances, denomination)
    proposed_amount = postings.balances()[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    available_balance = available_balance_before + proposed_amount
    autosave_rounding_amount = Decimal(autosave_rounding_amount)
    posting_instructions = []

    if available_balance <= 0 or minimum_balance_fee > 0 or not autosave_savings_account:
        return total_savings, posting_instructions

    txn_code_to_type_map = utils.get_parameter(
        name="transaction_code_to_type_map", is_json=True, vault=vault
    )
    for posting in postings:
        posting_net = posting.balances()[
            (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
        ].net
        txn_type = utils.get_transaction_type(
            posting.instruction_details,
            txn_code_to_type_map,
            DEFAULT_TRANSACTION_TYPE,
        )
        remainder = abs(posting_net % autosave_rounding_amount)
        save_amount = Decimal(0)
        if remainder > 0:
            save_amount = autosave_rounding_amount - remainder
        if (
            txn_type == "PURCHASE"
            and posting.denomination == denomination
            and posting.account_address == "DEFAULT"
            and posting_net < 0
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
        total_savings = Decimal(0)
    return total_savings, posting_instructions


def _check_transaction_type_limits(
    vault,
    postings: PostingInstructionBatch,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    denomination: str,
    effective_date: datetime,
) -> None:

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

    daily_atm_withdrawal_limit = utils.get_parameter(vault, name="daily_atm_withdrawal_limit")
    txn_code_to_type_map = utils.get_parameter(
        name="transaction_code_to_type_map", is_json=True, vault=vault
    )

    # get total amount in batch per transaction type
    for posting in postings:
        txn_type = utils.get_transaction_type(
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

            if (
                posting.balances()[
                    DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
                ].net
                + posting.balances()[
                    DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT
                ].net
            ) < 0:
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
    denomination: str,
    client_transactions: dict[tuple[str, str], ClientTransaction],
    client_transaction_id: str,
    cutoff_timestamp: datetime,
    txn_code_to_type_map: dict,
) -> Decimal:
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

    def _get_atm_withdrawal_amount(posting: PostingInstruction) -> Decimal:
        balance = posting.balances()[
            DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
        ].net
        if (
            balance < 0
            and posting.value_timestamp >= cutoff_timestamp
            and utils.get_transaction_type(
                posting.instruction_details,
                txn_code_to_type_map,
                DEFAULT_TRANSACTION_TYPE,
            )
            == "ATM withdrawal"
        ):
            return balance
        else:
            return Decimal(0)

    return sum(
        sum(_get_atm_withdrawal_amount(posting) for posting in transaction)
        for (_, transaction_id), transaction in client_transactions.items()
        if transaction_id != client_transaction_id and not transaction.cancelled
    )


@requires(flags=True, parameters=True)
def pre_parameter_change_code(
    parameters: dict[str, Parameter], effective_date: datetime
) -> Union[dict[str, Parameter], None]:
    if "daily_atm_withdrawal_limit" in parameters:
        max_atm = utils.get_parameter(
            vault, name="maximum_daily_atm_withdrawal_limit", is_json=True
        )

        tier_names = utils.get_parameter(vault, name="tier_names", is_json=True)
        this_account_flags = utils.get_active_account_flags(vault, tier_names)
        max_atm = utils.get_dict_value_based_on_account_tier_flag(
            active_flags=this_account_flags,
            tiered_param=max_atm,
            tier_names=tier_names,
            convert=Decimal,
        )
        parameters["daily_atm_withdrawal_limit"].shape.max_value = max_atm
    return parameters


@requires(modules=["interest"], parameters=True, balances="latest")
def close_code(effective_date: datetime) -> None:
    instructions = _apply_accrued_fees(vault, effective_date)
    instructions.extend(_reverse_accrued_interest_on_account_closure(vault, effective_date))
    _instruct_posting_batch(vault, instructions, effective_date, "CLOSE")


def _accrue_interest(vault, effective_date: datetime) -> list[PostingInstruction]:
    """
    Positive Committed Balances: If the balance is above 0, and there is a deposit interest rate
    set, interest will be accrued to the incoming address for positive deposit interest
    rates, and the outgoing address for negative interest rates.

    :param vault: Vault object
    :param effective_date: date and time of hook being run

    :return: posting instructions
    """
    # Load parameters and flags

    denomination = utils.get_parameter(name="denomination", vault=vault)

    # Load balances
    balances = vault.get_balance_timeseries().at(timestamp=effective_date)
    effective_balance = balances[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net

    if effective_balance > Decimal("0"):
        # Deposit Check
        balance_tier_ranges = utils.get_parameter(vault, "deposit_tier_ranges", is_json=True)
        deposit_interest_rate_tiers = utils.get_parameter(
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
        payable_internal_account=utils.get_parameter(vault, "accrued_interest_payable_account"),
        paid_internal_account=utils.get_parameter(vault, "interest_paid_account"),
        receivable_internal_account=utils.get_parameter(
            vault, "accrued_interest_receivable_account"
        ),
        received_internal_account=utils.get_parameter(vault, "interest_received_account"),
    )
    accrual_details = vault.modules["interest"].construct_accrual_details(
        balance=effective_balance,
        rates=balance_tier_ranges,
        denomination=denomination,
        payable_receivable_mapping=payable_receivable_mapping,
        base=utils.get_parameter(name="interest_accrual_days_in_year", vault=vault, union=True),
        net_postings=False,
    )

    return vault.modules["interest"].accrue_interest(
        vault,
        [accrual_details],
        "LIABILITY",
        effective_date,
        event_type="ACCRUE_INTEREST_AND_DAILY_FEES",
        account_type=ACCOUNT_TYPE,
    )


def _reverse_accrued_interest_on_account_closure(
    vault,
    effective_date: datetime,
) -> list[PostingInstruction]:
    denomination = utils.get_parameter(vault, name="denomination")
    balances = vault.get_balance_timeseries().at(timestamp=effective_date)

    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        payable_address="ACCRUED_DEPOSIT_PAYABLE",
        receivable_address="ACCRUED_DEPOSIT_RECEIVABLE",
        payable_internal_account=utils.get_parameter(vault, "accrued_interest_payable_account"),
        paid_internal_account=utils.get_parameter(vault, "interest_paid_account"),
        receivable_internal_account=utils.get_parameter(
            vault, "accrued_interest_receivable_account"
        ),
        received_internal_account=utils.get_parameter(vault, "interest_received_account"),
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
        account_type=ACCOUNT_TYPE,
    )


def _apply_monthly_fees(vault, effective_date: datetime) -> list[PostingInstruction]:
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
    maintenance_fee_income_account = utils.get_parameter(
        vault, name="maintenance_fee_income_account"
    )
    inactivity_fee_income_account = utils.get_parameter(vault, name="inactivity_fee_income_account")
    minimum_balance_fee_income_account = utils.get_parameter(
        vault, name="minimum_balance_fee_income_account"
    )

    denomination = utils.get_parameter(vault, name="denomination")
    minimum_balance_fee = utils.get_parameter(vault, name="minimum_balance_fee")
    account_inactivity_fee = utils.get_parameter(vault, name="account_inactivity_fee")
    tier_names = utils.get_parameter(name="tier_names", is_json=True, vault=vault)
    monthly_fee_tiers = _get_monthly_maintenance_fee_tiers(vault)
    minimum_balance_tiers = utils.get_parameter(
        name="minimum_balance_threshold", is_json=True, vault=vault
    )
    minimum_deposit_tiers = utils.get_parameter(
        name="minimum_deposit_threshold", is_json=True, vault=vault
    )

    # Load flags
    this_account_flags = utils.get_active_account_flags(vault, tier_names)
    is_account_dormant = vault.get_flag_timeseries(flag=DORMANCY_FLAG).latest()

    # Load tier information
    monthly_fee = utils.get_dict_value_based_on_account_tier_flag(
        active_flags=this_account_flags,
        tiered_param=monthly_fee_tiers,
        tier_names=tier_names,
        convert=Decimal,
    )
    minimum_balance = utils.get_dict_value_based_on_account_tier_flag(
        active_flags=this_account_flags,
        tiered_param=minimum_balance_tiers,
        tier_names=tier_names,
        convert=Decimal,
    )
    minimum_deposit = utils.get_dict_value_based_on_account_tier_flag(
        active_flags=this_account_flags,
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


def _accrue_fees(vault, effective_date: datetime) -> list[PostingInstruction]:
    """
    Accrues to the accrued outgoing address an overdraft fee if balance is below
    fee free overdraft limit, up to overdraft fee cap.

    :param vault: Vault object
    :param effective_date: date and time of hook being run

    :return: posting instructions
    """
    overdraft_fee_income_account = utils.get_parameter(vault, name="overdraft_fee_income_account")
    overdraft_fee_receivable_account = utils.get_parameter(
        vault, name="overdraft_fee_receivable_account"
    )
    fee_free_overdraft_limit = utils.get_parameter(vault, name="fee_free_overdraft_limit")
    standard_overdraft_daily_fee = utils.get_parameter(vault, name="standard_overdraft_daily_fee")
    standard_overdraft_fee_cap = utils.get_parameter(vault, name="standard_overdraft_fee_cap")
    denomination = utils.get_parameter(vault, name="denomination")
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
        od_per_transaction_fee_charged = _get_overdraft_per_transaction_fee_charged(
            vault, denomination
        )
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
                account_type=ACCOUNT_TYPE,
            )
        )
    return posting_instructions


def _process_accrued_interest(vault) -> list[PostingInstruction]:
    """
    Processes any accrued interest by either applying it to the customers default account,
    or reversing and returning the accrued amounts back to the bank.

    :param vault: Vault object
    :return: posting instructions
    """
    interest_type = "DEPOSIT"
    payable_address = "ACCRUED_DEPOSIT_PAYABLE"
    receivable_address = "ACCRUED_DEPOSIT_RECEIVABLE"

    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        payable_address=payable_address,
        receivable_address=receivable_address,
        payable_internal_account=utils.get_parameter(vault, "accrued_interest_payable_account"),
        paid_internal_account=utils.get_parameter(vault, "interest_paid_account"),
        receivable_internal_account=utils.get_parameter(
            vault, "accrued_interest_receivable_account"
        ),
        received_internal_account=utils.get_parameter(vault, "interest_received_account"),
    )

    denomination = utils.get_parameter(vault, name="denomination")
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
        account_type=ACCOUNT_TYPE,
    )


def _apply_accrued_fees(vault, effective_date: datetime) -> list[PostingInstruction]:
    """
    Applies any accrued overdraft fees to the customer account's default address

    :param vault: Vault object
    :param effective_date: date and time of hook being run

    :return: posting instructions
    """
    denomination = utils.get_parameter(vault, name="denomination")

    balances = vault.get_balance_timeseries().latest()
    overdraft_fee_receivable_account = utils.get_parameter(
        vault, name="overdraft_fee_receivable_account"
    )
    overdraft_fee_income_account = utils.get_parameter(vault, name="overdraft_fee_income_account")
    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        receivable_address="ACCRUED_OVERDRAFT_FEE_RECEIVABLE",
        receivable_internal_account=overdraft_fee_receivable_account,
        payable_internal_account="Main account",
        received_internal_account=overdraft_fee_income_account,
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
        account_type=ACCOUNT_TYPE,
    )


def _instruct_posting_batch(
    vault,
    instructions: list[PostingInstruction],
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
    vault, denomination: str, effective_date: datetime, addresses: Optional[list[str]] = None
) -> Decimal:
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

    return Decimal(total / num_days)


def _sum_deposit_transactions(vault, effective_date: datetime) -> Decimal:
    """
    Sum all deposit transactions for all given client_transactions in the monthly deposit window.
    Monthly deposit window is the last month, starting from account creation date.

    :param vault: Vault object
    :param effective_date: datetime
    :return: Decimal, sum of deposit transactions for monthly deposit window
    """
    denomination = utils.get_parameter(vault, "denomination")
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

    return Decimal(total_deposit)


# Helper functions for accruing and applying interest


# Helper functions for creating event schedules
def _get_accrue_interest_schedule(vault) -> utils.EventTuple:
    """
    Sets up dictionary of ACCRUE_INTEREST schedule based on parameters

    :param vault: Vault object
    :return: dict, representation of ACCRUE_INTEREST schedule
    """

    return utils.get_daily_schedule(
        vault=vault, param_prefix="interest_accrual", event_type="ACCRUE_INTEREST_AND_DAILY_FEES"
    )


def _get_next_apply_accrued_interest_schedule(
    vault, effective_date: datetime, interest_application_frequency: str = "monthly"
) -> dict[str, str]:
    """
    Sets up dictionary for the next interest application day, for both overdraft and deposit.
    :param vault: Vault object
    :param effective_date: datetime, date and time of hook being run
    :param interest_application_frequency: str, Either 'monthly', 'quarterly',
                                           or 'annually'. Defaults to monthly.
    :return: dict, representation of APPLY_ACCRUED_INTEREST schedule
    """
    interest_application_day = utils.get_parameter(vault, name="interest_application_day")

    apply_accrued_interest_date = utils.get_next_schedule_datetime(
        vault=vault,
        # no timezones on this contract so localised_effective_date == effective_date
        localised_effective_date=effective_date,
        param_prefix="interest_application",
        schedule_frequency=interest_application_frequency,
        schedule_day_of_month=interest_application_day,
        calendar_events=[],
    )

    apply_accrued_interest_schedule = utils.create_schedule_dict_from_datetime(
        apply_accrued_interest_date
    )

    return apply_accrued_interest_schedule


def _get_next_fee_schedule(vault, effective_date: datetime, period: timedelta) -> dict[str, str]:
    """
    Sets up dictionary for next run time of APPLY_???_FEES, taking the day and hh:mm:ss
    from contract parameters and ensuring the first run is at least `period` away from creation
    date.

    :param vault: Vault object
    :param effective_date: datetime, date from which to calculate next event datetime
    :param period: timedelta, fee period
    :return: dict, representation of schedule
    """
    fees_application_day = utils.get_parameter(vault, name="fees_application_day")

    fees_application_hour = utils.get_parameter(vault, name="fees_application_hour")

    fees_application_minute = utils.get_parameter(vault, name="fees_application_minute")

    fees_application_second = utils.get_parameter(vault, name="fees_application_second")
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

    return utils.create_schedule_dict_from_datetime(next_schedule_date)


def _get_overdraft_per_transaction_fee_charged(vault, denomination: str) -> Decimal:
    """
    Get the amount of standard overdraft per-transaction fee that has been charged in the current
    period.
    :param vault: Vault object
    :param denomination
    :return: Decimal, the total amount charged in the current period.
    """
    daily_fee_charged = Decimal("0")
    start_of_period = vault.get_last_execution_time(event_type="APPLY_MONTHLY_FEES")
    if not start_of_period:
        start_of_period = vault.get_account_creation_date()

    recent_postings = vault.get_postings(include_proposed=False)

    daily_fee_charged = sum(
        posting.balances()[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
        for posting in recent_postings
        if (
            posting.value_timestamp > start_of_period
            and posting.balances()[
                DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
            ].net
            < 0
            and posting.instruction_details.get("event") == "STANDARD_OVERDRAFT"
        )
    )

    return Decimal(-daily_fee_charged)


def _get_monthly_maintenance_fee_tiers(vault) -> Any:
    fee_to_use = (
        "promotional_maintenance_fee_monthly"
        if vault.get_flag_timeseries(flag=PROMOTIONAL_MAINTENANCE_FEE_FLAG).latest()
        else "maintenance_fee_monthly"
    )

    return utils.get_parameter(name=fee_to_use, is_json=True, vault=vault)


def _has_transaction_type_not_covered_by_standard_overdraft(
    vault, postings: PostingInstructionBatch
) -> bool:
    """
    Checks whether the transaction has a type that is not covered by standard overdraft

    :param vault: Vault object
    :param postings: postings to process
    :return: Boolean
    """
    txn_code_to_type_map = utils.get_parameter(vault, "transaction_code_to_type_map", is_json=True)
    optional_standard_overdraft_coverage = utils.get_parameter(
        vault, "optional_standard_overdraft_coverage", is_json=True
    )
    should_include_optional_standard_overdraft_coverage = vault.get_flag_timeseries(
        flag=STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG
    ).latest()
    return not should_include_optional_standard_overdraft_coverage and any(
        utils.get_transaction_type(
            posting.instruction_details,
            txn_code_to_type_map,
            DEFAULT_TRANSACTION_TYPE,
        )
        in optional_standard_overdraft_coverage
        for posting in postings
        if utils.get_available_balance(posting.balances(), posting.denomination) < 0
    )
