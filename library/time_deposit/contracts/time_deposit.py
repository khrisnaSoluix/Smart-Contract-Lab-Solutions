# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
api = "3.9.0"
version = "1.8.3"
display_name = "Time Deposit"
summary = "A savings account paying a fixed rate of interest when money is put away for a defined"
" period of time."
tside = Tside.LIABILITY

# this can be amended to whichever other currencies as needed
supported_denominations = ["GBP"]

event_types = [
    EventType(name="ACCRUE_INTEREST", scheduler_tag_ids=["TIME_DEPOSIT_ACCRUE_INTEREST_AST"]),
    EventType(
        name="APPLY_ACCRUED_INTEREST",
        scheduler_tag_ids=["TIME_DEPOSIT_APPLY_ACCRUED_INTEREST_AST"],
    ),
    EventType(name="ACCOUNT_MATURITY", scheduler_tag_ids=["TIME_DEPOSIT_ACCOUNT_MATURITY_AST"]),
    EventType(name="ACCOUNT_CLOSE", scheduler_tag_ids=["TIME_DEPOSIT_ACCOUNT_CLOSE_AST"]),
]


parameters = [
    # Instance parameters
    Parameter(
        name="interest_application_frequency",
        shape=UnionShape(
            UnionItem(key="monthly", display_name="Monthly"),
            UnionItem(key="quarterly", display_name="Quarterly"),
            UnionItem(key="annually", display_name="Annually"),
            UnionItem(key="maturity", display_name="Maturity"),
            UnionItem(key="weekly", display_name="Weekly"),
            UnionItem(key="fortnightly", display_name="Fortnightly"),
            UnionItem(key="four_weekly", display_name="Four Weekly"),
            UnionItem(key="semi_annually", display_name="Semi Annually"),
        ),
        level=Level.INSTANCE,
        description="The frequency at which interest is applied.",
        display_name="Interest application frequency",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=UnionItemValue(key="monthly"),
    ),
    Parameter(
        name="interest_application_day",
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=Level.INSTANCE,
        description="The day of the month on which interest is applied. If day does not exist in"
        " application month, applies on last day of month. This doesn't apply to the"
        " frequencies Weekly, Fortnightly, Four Weekly and Maturity, as the interest"
        " is applied per the time range set.",
        display_name="Interest application day",
        update_permission=UpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name="gross_interest_rate",
        shape=NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, step=0.0001),
        level=Level.INSTANCE,
        description="The annual interest rate set on the account before taxes and fees.",
        display_name="Interest rate (p.a.)",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=Decimal("0.149"),
    ),
    Parameter(
        name="term_unit",
        shape=UnionShape(
            UnionItem(key="days", display_name="Days"),
            UnionItem(key="months", display_name="Months"),
        ),
        level=Level.INSTANCE,
        description="The unit at which the term is applied.",
        display_name="Term unit (days or months)",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=UnionItemValue(key="months"),
    ),
    Parameter(
        name="term",
        shape=NumberShape(min_value=1, step=1),
        level=Level.INSTANCE,
        description="The agreed length of time based on Term unit, that the customer will"
        " receive interest on the deposit.",
        display_name="Term",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=12,
    ),
    Parameter(
        name="deposit_period",
        shape=NumberShape(kind=NumberKind.PLAIN, min_value=0, step=1),
        level=Level.INSTANCE,
        description="The number of days to deposit funds into the account.",
        display_name="Deposit period length (days)",
        update_permission=UpdatePermission.FIXED,
        default_value=7,
    ),
    Parameter(
        name="cool_off_period",
        shape=NumberShape(kind=NumberKind.PLAIN, min_value=0, step=1),
        level=Level.INSTANCE,
        description="A period of time when a user can withdraw and deposit money without penalties"
        " for new time deposits only",
        display_name="Cool off period (days)",
        update_permission=UpdatePermission.FIXED,
        default_value=0,
    ),
    Parameter(
        name="period_end_hour",
        shape=NumberShape(kind=NumberKind.PLAIN, min_value=0, max_value=23, step=1),
        level=Level.INSTANCE,
        description="The hour for all the time period expiry (deposit period, cool off period and"
        " grace period).",
        display_name="Period end hour",
        update_permission=UpdatePermission.FIXED,
        default_value=21,
    ),
    Parameter(
        name="grace_period",
        shape=NumberShape(kind=NumberKind.PLAIN, min_value=0, step=1),
        level=Level.INSTANCE,
        description="A period for renewed time deposits to make changes to the account without"
        " penalties, only applies to renewed time deposit.",
        display_name="Grace period (days)",
        update_permission=UpdatePermission.FIXED,
        default_value=0,
    ),
    Parameter(
        name="rollover_period_end_hour",
        shape=NumberShape(kind=NumberKind.PLAIN, min_value=0, max_value=23, step=1),
        level=Level.INSTANCE,
        description="The hour at which rollover grace period will expire."
        " Only applies to the next time deposit not the current one.",
        display_name="Rollover period end hour",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=21,
    ),
    Parameter(
        name="rollover_interest_application_frequency",
        shape=UnionShape(
            UnionItem(key="monthly", display_name="Monthly"),
            UnionItem(key="quarterly", display_name="Quarterly"),
            UnionItem(key="annually", display_name="Annually"),
            UnionItem(key="maturity", display_name="Maturity"),
            UnionItem(key="weekly", display_name="Weekly"),
            UnionItem(key="fortnightly", display_name="Fortnightly"),
            UnionItem(key="four_weekly", display_name="Four Weekly"),
            UnionItem(key="semi_annually", display_name="Semi Annually"),
        ),
        level=Level.INSTANCE,
        description="When renewing the account, The frequency at which interest is applied for.",
        display_name="Rollover Interest application frequency",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=UnionItemValue(key="monthly"),
    ),
    Parameter(
        name="rollover_interest_application_day",
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=Level.INSTANCE,
        description="When renewing the account, The day of the month on which interest is applied."
        " If day does not exist in application month, applies on last day of month. This doesn't"
        " apply to the frequencies Weekly, Fortnightly, Four Weekly and Maturity, as the interest"
        " is applied per the time range set.",
        display_name="Rollover Interest application day",
        update_permission=UpdatePermission.USER_EDITABLE,
        default_value=1,
    ),
    Parameter(
        name="rollover_gross_interest_rate",
        shape=NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, step=0.0001),
        level=Level.INSTANCE,
        description="When renewing the account, The annual interest rate set on the account before"
        " taxes and fees.",
        display_name="Rollover Interest rate (p.a.)",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=Decimal("0.149"),
    ),
    Parameter(
        name="rollover_term_unit",
        shape=UnionShape(
            UnionItem(key="days", display_name="Days"),
            UnionItem(key="months", display_name="Months"),
        ),
        level=Level.INSTANCE,
        description="When renewing the account, The unit at which the term is applied.",
        display_name="Rollover Term unit (days or months)",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=UnionItemValue(key="months"),
    ),
    Parameter(
        name="rollover_term",
        shape=NumberShape(min_value=1, step=1),
        level=Level.INSTANCE,
        description="When renewing the account, The agreed length of time based on Term unit, that"
        " the customer will receive interest on the deposit.",
        display_name="Rollover term",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=12,
    ),
    Parameter(
        name="rollover_grace_period",
        shape=NumberShape(kind=NumberKind.PLAIN, min_value=0, step=1),
        level=Level.INSTANCE,
        description="A period for renewed time deposits to make changes to the account without"
        " penalties. Only applies to the next time deposit not the current one.",
        display_name="Rollover Grace period (days)",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=0,
    ),
    Parameter(
        name="rollover_account_closure_period",
        shape=NumberShape(kind=NumberKind.PLAIN, min_value=0, step=1),
        level=Level.INSTANCE,
        description="The number of days after the grace period"
        " before an unfunded account is closed,  only applies to the next time deposit not the"
        " current one.",
        display_name="Rollover Account closure Period (days)",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=7,
    ),
    Parameter(
        name="account_closure_period",
        shape=NumberShape(kind=NumberKind.PLAIN, min_value=0, step=1),
        level=Level.INSTANCE,
        description="The number of days after the deposit period, cool off period, grace period"
        " (whichever is higher depending if account is a renewed or new time deposit)."
        " before an unfunded account is closed",
        display_name="Account closure Period (days)",
        update_permission=UpdatePermission.FIXED,
        default_value=7,
    ),
    Parameter(
        name="fee_free_percentage_limit",
        shape=NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.0001),
        level=Level.INSTANCE,
        description="The fee free percentage limit allowed for withdrawal on the account before"
        " maturity",
        display_name="Withdrawal percentage limit",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=0,
    ),
    Parameter(
        name="withdrawal_fee",
        shape=NumberShape(kind=NumberKind.MONEY, min_value=0, step=0.01),
        level=Level.INSTANCE,
        description="The flat fee applied when making a withdrawal before account maturity and the"
        " daily withdrawal limit is exceeded. Note, this fee can be applied with the withdrawal"
        " percentage fee if defined. With this fee being applied after",
        display_name="Withdrawal fee",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=10,
    ),
    Parameter(
        name="withdrawal_percentage_fee",
        shape=NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.0001),
        level=Level.INSTANCE,
        description="The percentage fee applied when making a withdrawal before account maturity.",
        display_name="Withdrawal percentage fee",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=0,
    ),
    Parameter(
        name="auto_rollover_type",
        shape=UnionShape(
            UnionItem(key="principal_and_interest", display_name="Principal & Interest"),
            UnionItem(key="principal", display_name="Principal Only"),
            UnionItem(key="no_rollover", display_name="No Rollover"),
            UnionItem(key="partial_principal", display_name="Partial Principal"),
        ),
        level=Level.INSTANCE,
        description="Type of autoroll over to be applied after maturity.",
        display_name="Auto rollover type",
        update_permission=UpdatePermission.USER_EDITABLE,
        default_value=UnionItemValue(key="no_rollover"),
    ),
    Parameter(
        name="partial_principal_amount",
        shape=NumberShape(kind=NumberKind.MONEY, min_value=Decimal("0"), step=Decimal("0.01")),
        level=Level.INSTANCE,
        description="The amount to auto renew if partial principal was selected in Auto rollover"
        " type",
        display_name="Partial Rollover Amount",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=Decimal("0"),
    ),
    # Derived parameters
    Parameter(
        name="maturity_date",
        shape=StringShape,
        level=Level.INSTANCE,
        derived=True,
        description="The date and time that the product ends (UTC)."
        " This is calculated using the term and the account opening date.",
        display_name="Maturity date",
    ),
    Parameter(
        name="deposit_period_end_date",
        shape=StringShape,
        level=Level.INSTANCE,
        derived=True,
        description="The date and time that the deposit period ends (UTC).",
        display_name="Deposit period end date",
    ),
    Parameter(
        name="grace_period_end_date",
        shape=StringShape,
        level=Level.INSTANCE,
        derived=True,
        description="The date and time that the grace period ends (UTC).",
        display_name="Grace period end date",
    ),
    Parameter(
        name="cool_off_period_end_date",
        shape=StringShape,
        level=Level.INSTANCE,
        derived=True,
        description="The date and time that the cool period ends (UTC). If the cool off period"
        " value is 0 then no date and time will be defined",
        display_name="Cool off period end date",
    ),
    Parameter(
        name="fee_free_withdrawal_limit",
        shape=StringShape,
        level=Level.INSTANCE,
        derived=True,
        description="The fee free withdrawal limit allowed on the account.",
        display_name="Fee free withdrawal limit",
    ),
    Parameter(
        name="account_closure_period_end_date",
        shape=StringShape,
        level=Level.INSTANCE,
        derived=True,
        description="The date and time that the account close period ends (UTC).",
        display_name="Account closure period end date",
    ),
    # Template parameters
    Parameter(
        name="interest_accrual_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which interest is accrued (UTC).",
        display_name="Interest accrual hour",
        default_value=23,
    ),
    Parameter(
        name="interest_accrual_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the hour at which interest is accrued.",
        display_name="Interest accrual minute",
        default_value=59,
    ),
    Parameter(
        name="interest_accrual_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the minute at which interest is accrued.",
        display_name="Interest accrual second",
        default_value=59,
    ),
    Parameter(
        name="interest_application_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which interest is applied (UTC).",
        display_name="Interest application hour",
        default_value=23,
    ),
    Parameter(
        name="interest_application_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the hour at which interest is applied.",
        display_name="Interest application minute",
        default_value=59,
    ),
    Parameter(
        name="interest_application_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the minute at which interest is applied.",
        display_name="Interest application second",
        default_value=59,
    ),
    Parameter(
        name="denomination",
        shape=DenominationShape,
        level=Level.TEMPLATE,
        description="Currency in which the product operates.",
        display_name="Denomination",
        default_value="GBP",
    ),
    Parameter(
        name="accrual_precision",
        shape=NumberShape(kind=NumberKind.PLAIN, min_value=0, max_value=15, step=1),
        level=Level.TEMPLATE,
        description="Precision needed for interest accruals.",
        display_name="Interest accrual precision",
        default_value=5,
    ),
    Parameter(
        name="fulfillment_precision",
        shape=NumberShape(kind=NumberKind.PLAIN, min_value=0, max_value=4, step=1),
        level=Level.TEMPLATE,
        description="Precision needed for interest application.",
        display_name="Interest application precision",
        default_value=2,
    ),
    Parameter(
        name="minimum_first_deposit",
        shape=NumberShape(kind=NumberKind.MONEY, min_value=Decimal("0"), step=Decimal("0.01")),
        level=Level.TEMPLATE,
        description="The minimum amount for the first deposit into the account.",
        display_name="Minimum first deposit",
        default_value=Decimal("50"),
    ),
    Parameter(
        name="maximum_balance",
        shape=NumberShape(kind=NumberKind.MONEY, min_value=Decimal("0"), step=Decimal("0.01")),
        level=Level.TEMPLATE,
        description="The maximum deposited balnce amount for the account."
        " Deposits that breach this amount will be rejected.",
        display_name="Maximum balance",
        default_value=Decimal("100000"),
    ),
    Parameter(
        name="single_deposit",
        shape=UnionShape(
            UnionItem(key="single", display_name="Single deposit"),
            UnionItem(key="unlimited", display_name="Unlimited deposits"),
        ),
        level=Level.TEMPLATE,
        description="Number of deposits allowed during the deposit period."
        " This can be single or unlimited.",
        display_name="Deposit number",
        default_value=UnionItemValue(key="unlimited"),
    ),
    # Internal accounts
    Parameter(
        name="accrued_interest_payable_account",
        level=Level.TEMPLATE,
        description="Internal account to track interest accrued but not yet applied to the customer"
        " account.",
        display_name="Accrued interest payable account",
        shape=AccountIdShape,
        default_value="ACCRUED_INTEREST_PAYABLE",
    ),
    Parameter(
        name="interest_paid_account",
        level=Level.TEMPLATE,
        description="Internal account to debit interest at the point it's accrued.",
        display_name="Interest paid account",
        shape=AccountIdShape,
        default_value="INTEREST_PAID",
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
            SharedFunction(name="has_parameter_value_changed"),
            SharedFunction(name="round_decimal"),
        ],
    ),
]

# Addresses
CAPITALISED_INTEREST = "CAPITALISED_INTEREST"
ACCRUED_INTEREST_PAYABLE = "ACCRUED_INTEREST_PAYABLE"
INTERNAL_CONTRA = "INTERNAL_CONTRA"

# Hooks
@requires(modules=["utils"], parameters=True, calendar=["&{PUBLIC_HOLIDAYS}"])
def execution_schedules():
    calendar_events = vault.get_calendar_events(calendar_ids=["&{PUBLIC_HOLIDAYS}"])
    account_creation_date = vault.get_account_creation_date()
    deposit_period = int(vault.modules["utils"].get_parameter(vault, name="deposit_period"))
    cool_off_period = int(vault.modules["utils"].get_parameter(vault, name="cool_off_period"))
    grace_period = int(vault.modules["utils"].get_parameter(vault, name="grace_period"))
    account_closure_period = int(
        vault.modules["utils"].get_parameter(vault, name="account_closure_period")
    )
    period_end_hour = int(vault.modules["utils"].get_parameter(vault, name="period_end_hour"))
    term_unit = vault.modules["utils"].get_parameter(vault, name="term_unit", union=True)
    term = int(vault.modules["utils"].get_parameter(vault, name="term"))
    interest_application_frequency = vault.modules["utils"].get_parameter(
        vault, name="interest_application_frequency", union=True
    )

    interest_application_day = vault.modules["utils"].get_parameter(
        vault, name="interest_application_day"
    )

    accrue_interest_schedule = _get_accrue_interest_schedule(vault)
    apply_accrued_interest_schedule = _get_apply_accrued_interest_schedule(
        vault,
        interest_application_frequency,
        interest_application_day,
        account_creation_date,
    )
    account_maturity_schedule = _get_account_maturity_schedule(
        vault, term_unit, term, account_creation_date, calendar_events
    )
    days_for_closure_check = max(
        cool_off_period,
        grace_period,
        deposit_period,
    )
    account_close_schedule = _get_account_close_schedule(
        vault,
        account_creation_date,
        days_for_closure_check,
        period_end_hour,
        account_closure_period,
    )

    schedules = [
        ("ACCRUE_INTEREST", accrue_interest_schedule),
        ("ACCOUNT_MATURITY", account_maturity_schedule),
        ("ACCOUNT_CLOSE", account_close_schedule),
    ]
    if interest_application_frequency != "maturity":
        schedules.append(("APPLY_ACCRUED_INTEREST", apply_accrued_interest_schedule))
    return schedules


@requires(
    modules=["interest", "utils"],
    event_type="ACCRUE_INTEREST",
    parameters=True,
    balances="latest live",
)
@requires(
    modules=["interest", "utils"],
    event_type="APPLY_ACCRUED_INTEREST",
    parameters=True,
    balances="latest live",
)
@requires(
    modules=["interest", "utils"],
    event_type="ACCOUNT_MATURITY",
    parameters=True,
    balances="latest live",
)
@requires(
    modules=["utils"],
    event_type="ACCOUNT_CLOSE",
    parameters=True,
    balances="latest live",
)
def scheduled_code(event_type, effective_date):
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    if event_type == "ACCRUE_INTEREST":
        _accrue_interest(vault, denomination, effective_date, event_type)
    elif event_type == "APPLY_ACCRUED_INTEREST":
        _apply_accrued_interest(vault, denomination, effective_date, event_type)
    elif event_type == "ACCOUNT_MATURITY":
        _initiate_account_maturity_process(vault, denomination, effective_date, event_type)
    elif event_type == "ACCOUNT_CLOSE":
        _check_account_closure_period_end(vault, denomination)


@requires(modules=["utils"], parameters=True, last_execution_time=["APPLY_ACCRUED_INTEREST"])
def post_parameter_change_code(old_parameters, new_parameters, effective_date):
    if vault.modules["utils"].has_parameter_value_changed(
        "interest_application_day", old_parameters, new_parameters
    ):
        interest_application_frequency = vault.modules["utils"].get_parameter(
            vault, name="interest_application_frequency", union=True, at=effective_date
        )
        interest_application_day = _get_parameter_value(
            "interest_application_day", old_parameters, new_parameters
        )

        next_interest_application_reference_date = vault.get_last_execution_time(
            event_type="APPLY_ACCRUED_INTEREST"
        )

        if not next_interest_application_reference_date:
            next_interest_application_reference_date = vault.get_account_creation_date()

        apply_accrued_interest_date = _get_apply_accrued_interest_date(
            vault,
            interest_application_frequency,
            interest_application_day,
            next_interest_application_reference_date,
        )

        if apply_accrued_interest_date <= effective_date:
            apply_accrued_interest_date = _get_next_schedule_date(
                apply_accrued_interest_date,
                interest_application_frequency,
                interest_application_day,
            )

        apply_accrued_interest_schedule = vault.modules["utils"].create_schedule_dict_from_datetime(
            apply_accrued_interest_date
        )

        vault.amend_schedule(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule=apply_accrued_interest_schedule,
        )


@requires(
    modules=["utils"],
    parameters=True,
    balances="latest live",
    calendar=["&{PUBLIC_HOLIDAYS}"],
)
def pre_posting_code(postings: PostingInstructionBatch, effective_date: datetime):
    calendar_events = vault.get_calendar_events(calendar_ids=["&{PUBLIC_HOLIDAYS}"])
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    if any(post.denomination != denomination for post in postings):
        raise Rejected(
            f"Cannot make transactions in given denomination; "
            f"transactions must be in {denomination}",
            reason_code=RejectedReason.WRONG_DENOMINATION,
        )
    deposit_period = vault.modules["utils"].get_parameter(vault, name="deposit_period")
    term_unit = vault.modules["utils"].get_parameter(vault, name="term_unit", union=True)
    term = int(vault.modules["utils"].get_parameter(vault, name="term"))

    cool_off_period = int(vault.modules["utils"].get_parameter(vault, name="cool_off_period"))

    grace_period = int(vault.modules["utils"].get_parameter(vault, name="grace_period"))
    period_end_hour = vault.modules["utils"].get_parameter(vault, name="period_end_hour")
    account_creation_date = vault.get_account_creation_date()

    deposit_period_end_date = (
        _get_period_end_date(account_creation_date, deposit_period, period_end_hour)
        or account_creation_date
    )

    account_maturity_date = _get_account_maturity_date(
        term_unit, term, account_creation_date, calendar_events
    )

    posting_committed_amount = postings.balances()[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
    ].net
    posting_pending_outbound_amount = postings.balances()[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT
    ].net
    posting_pending_inbound_amount = postings.balances()[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN
    ].net

    latest_available_balance = _get_available_balance(
        vault,
        DEFAULT_ADDRESS,
        [Phase.COMMITTED, Phase.PENDING_OUT],
        denomination,
    )

    if latest_available_balance + posting_committed_amount + posting_pending_outbound_amount < 0:
        raise Rejected(
            "Transaction cannot bring available balance below 0",
            reason_code=RejectedReason.INSUFFICIENT_FUNDS,
        )

    withdrawal_end_date = account_creation_date + timedelta(
        days=int(max(cool_off_period, grace_period)),
        hour=int(period_end_hour),
    )
    # deposits are allowed, during period when withdrawals are allowed
    deposit_end_date = max(withdrawal_end_date, deposit_period_end_date)

    proposed_amount = posting_committed_amount + posting_pending_inbound_amount
    if proposed_amount > 0:
        _validate_deposits(
            vault,
            effective_date,
            denomination,
            deposit_end_date,
            proposed_amount,
            latest_available_balance,
        )

    if proposed_amount < 0:
        _validate_withdrawals(
            vault,
            effective_date,
            account_maturity_date,
            withdrawal_end_date,
            proposed_amount,
            calendar_events,
            postings,
        )


@requires(modules=["utils"], parameters=True, balances="latest live")
def post_posting_code(postings: PostingInstructionBatch, effective_date: datetime):
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    postings_net_amount = postings.balances()[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
    ].net

    # If withdrawal adjust capitalised interest amount
    if postings_net_amount < 0:
        auto_rollover_type = postings.batch_details.get("auto_rollover_type")
        _adjust_capitalised_interest(vault, denomination, effective_date, auto_rollover_type)


@requires(
    modules=["utils"],
    parameters=True,
    balances="1 day live",
    postings="1 day live",
    calendar=["&{PUBLIC_HOLIDAYS}"],
)
def derived_parameters(effective_date: datetime):
    account_creation_date = vault.get_account_creation_date().replace(microsecond=0)
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    cool_off_period = int(vault.modules["utils"].get_parameter(vault, name="cool_off_period"))
    deposit_period = int(
        vault.modules["utils"].get_parameter(vault, name="deposit_period", at=effective_date)
    )
    period_end_hour = int(
        vault.modules["utils"].get_parameter(vault, name="period_end_hour", at=effective_date)
    )
    grace_period = int(
        vault.modules["utils"].get_parameter(vault, name="grace_period", at=effective_date)
    )
    term_unit = vault.modules["utils"].get_parameter(vault, name="term_unit", union=True)
    term = int(vault.modules["utils"].get_parameter(vault, name="term", at=effective_date))
    fee_free_percentage_limit = vault.modules["utils"].get_parameter(
        vault, name="fee_free_percentage_limit", at=effective_date
    )

    latest_available_balance = _get_available_balance(
        vault, DEFAULT_ADDRESS, [Phase.COMMITTED], denomination
    )

    deposit_period_end_date = _get_period_end_date(
        account_creation_date, deposit_period, period_end_hour
    )
    cool_off_period_end_date = _get_period_end_date(
        account_creation_date, cool_off_period, period_end_hour
    )
    grace_period_end_date = _get_period_end_date(
        account_creation_date, grace_period, period_end_hour
    )

    calendar_events = vault.get_calendar_events(calendar_ids=["&{PUBLIC_HOLIDAYS}"])
    account_maturity_date = _get_account_maturity_date(
        term_unit, term, account_creation_date, calendar_events
    )

    available_fee_free_limit = _get_available_fee_free_limit(
        latest_available_balance, fee_free_percentage_limit
    )
    delta_days = max(
        cool_off_period,
        grace_period,
        deposit_period,
    )

    account_closure_period = int(
        vault.modules["utils"].get_parameter(
            vault, name="account_closure_period", at=effective_date
        )
    )

    account_closure_period_end_date = _get_account_close_date(
        account_creation_date,
        delta_days,
        period_end_hour,
        account_closure_period,
    )
    return {
        "cool_off_period_end_date": str(cool_off_period_end_date),
        "deposit_period_end_date": str(deposit_period_end_date),
        "grace_period_end_date": str(grace_period_end_date),
        "account_closure_period_end_date": str(account_closure_period_end_date),
        "maturity_date": str(account_maturity_date),
        "fee_free_withdrawal_limit": str(available_fee_free_limit),
    }


# Scheduled events code
def _accrue_interest(vault, denomination: str, effective_date: datetime, event_type: str):
    """
    Accrue interest. If the account is in the cool period or grace period (where customer has the
    option to withdraw/deposit funds and close), then it will NOT accrue interest.
    :param vault: Vault object
    :param denomination: Denomination parameter to be used
    :param effective_date: Datetime of time of accrual
    :param event_type: Scheduled code event being processed
    """
    account_creation_date = vault.get_account_creation_date()
    gross_interest_rate = vault.modules["utils"].get_parameter(vault, name="gross_interest_rate")
    grace_period = int(vault.modules["utils"].get_parameter(vault, name="grace_period"))
    cool_off_period = int(vault.modules["utils"].get_parameter(vault, name="cool_off_period"))
    period_end_hour = int(
        vault.modules["utils"].get_parameter(vault, name="period_end_hour", at=effective_date)
    )
    payable_account = vault.modules["utils"].get_parameter(
        vault, "accrued_interest_payable_account"
    )
    paid_account = vault.modules["utils"].get_parameter(vault, "interest_paid_account")

    payable_receivable_mapping_interest = vault.modules[
        "interest"
    ].construct_payable_receivable_mapping(
        payable_address=ACCRUED_INTEREST_PAYABLE,
        payable_internal_account=payable_account,
        paid_internal_account=paid_account,
    )
    accrual_precision = int(vault.modules["utils"].get_parameter(vault, name="accrual_precision"))

    delta_days = max(cool_off_period, grace_period)

    withdrawal_end_date = (
        account_creation_date
        + timedelta(
            days=int(delta_days),
            hour=int(period_end_hour),
            minute=0,
            second=0,
        )
        if delta_days > 0
        else None
    )

    # No interest is accrued during the cool off period/ grace period
    if withdrawal_end_date and effective_date < withdrawal_end_date:
        return

    latest_available_balance = _get_available_balance(
        vault,
        DEFAULT_ADDRESS,
        [Phase.COMMITTED, Phase.PENDING_OUT],
        denomination,
    )

    # calculate backdated interest as withdrawal end date has ended
    # since accrual happens everyday, if withdrawal end date is the same as effective date,
    # backdating is required.
    # reset the day by calling .date()  so only the year, month and day are checked.
    yearly_interest_rate = {"tier1": {"rate": gross_interest_rate}}
    if withdrawal_end_date and effective_date.date() == withdrawal_end_date.date():
        delta = effective_date - account_creation_date
        number_of_days = delta.days + 1
    else:
        number_of_days = 1

    accrual_details = vault.modules["interest"].construct_accrual_details(
        payable_receivable_mapping=payable_receivable_mapping_interest,
        denomination=denomination,
        balance=latest_available_balance,
        base="365",
        rates=yearly_interest_rate,
        precision=accrual_precision,
        net_postings=True,
    )

    posting_instructions = vault.modules["interest"].accrue_interest(
        vault,
        accrual_details=[accrual_details],
        account_tside="LIABILITY",
        effective_date=effective_date,
        event_type=event_type,
        number_of_days=number_of_days,
    )

    if posting_instructions:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions, effective_date=effective_date
        )


def _apply_accrued_interest(
    vault,
    denomination: str,
    effective_date: datetime,
    event_type: str,
    start_workflow: bool = True,
    amend_schedule: bool = True,
):
    denomination = vault.modules["utils"].get_parameter(vault, "denomination")
    fulfillment_precision = int(
        vault.modules["utils"].get_parameter(vault, name="fulfillment_precision", at=effective_date)
    )
    interest_application_frequency = vault.modules["utils"].get_parameter(
        vault, name="interest_application_frequency", union=True, at=effective_date
    )
    interest_application_day = vault.modules["utils"].get_parameter(
        vault, name="interest_application_day", at=effective_date
    )
    accrued_interest_balance = _get_available_balance(
        vault, ACCRUED_INTEREST_PAYABLE, [Phase.COMMITTED], denomination
    )

    balances = vault.get_balance_timeseries().at(timestamp=effective_date)

    accrued_incoming_fulfillment = vault.modules["utils"].round_decimal(
        accrued_interest_balance, fulfillment_precision
    )
    payable_account = vault.modules["utils"].get_parameter(
        vault, "accrued_interest_payable_account"
    )
    paid_account = vault.modules["utils"].get_parameter(vault, "interest_paid_account")

    payable_receivable_mapping = vault.modules["interest"].construct_payable_receivable_mapping(
        payable_address=ACCRUED_INTEREST_PAYABLE,
        payable_internal_account=payable_account,
        paid_internal_account=paid_account,
    )
    posting_instructions = []

    charge_details = vault.modules["interest"].construct_charge_application_details(
        payable_receivable_mapping=payable_receivable_mapping,
        denomination=denomination,
        zero_out_remainder=True,
        instruction_description="Interest Applied.",
    )

    posting_instructions.extend(
        vault.modules["interest"].apply_charges(
            vault,
            balances=balances,
            charge_details=[charge_details],
            account_tside="LIABILITY",
            event_type=event_type,
        )
    )

    if accrued_incoming_fulfillment > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=accrued_incoming_fulfillment,
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=CAPITALISED_INTEREST,
                asset=DEFAULT_ASSET,
                client_transaction_id=f"{event_type}_TO_CAPITALISED_"
                f"{vault.get_hook_execution_id()}_"
                f"{denomination}_CUSTOMER",
                instruction_details={
                    "description": "Interest Applied.",
                    "event": f"{event_type}",
                },
            )
        )

    if posting_instructions:
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions,
            effective_date=effective_date,
            client_batch_id=f"{event_type}_{vault.get_hook_execution_id()}_{denomination}",
        )

    if accrued_incoming_fulfillment and start_workflow:
        vault.start_workflow(
            workflow="TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
            context={
                "account_id": vault.account_id,
                "applied_interest_amount": str(accrued_incoming_fulfillment),
            },
        )

    if amend_schedule:
        next_interest_application_schedule = _get_apply_accrued_interest_schedule(
            vault,
            interest_application_frequency,
            interest_application_day,
            effective_date,
        )
        vault.amend_schedule(
            event_type=f"{event_type}",
            new_schedule=next_interest_application_schedule,
        )

    return accrued_incoming_fulfillment


def _initiate_account_maturity_process(vault, denomination, effective_date, event_type):
    applied_interest = _apply_accrued_interest(
        vault,
        denomination,
        effective_date,
        event_type,
        start_workflow=False,
        amend_schedule=False,
    )
    # TODO: remove_schedule not usable with integration tests (TM-8461)
    # vault.remove_schedule(event_type="ACCRUE_INTEREST")
    vault.amend_schedule(
        event_type="ACCRUE_INTEREST",
        new_schedule={
            "year": "1971",
            "start_date": "1970-01-01",
            "end_date": "1970-01-01",
        },
    )
    # vault.remove_schedule(event_type="APPLY_ACCRUED_INTEREST")
    vault.amend_schedule(
        event_type="APPLY_ACCRUED_INTEREST",
        new_schedule={
            "year": "1971",
            "start_date": "1970-01-01",
            "end_date": "1970-01-01",
        },
    )
    vault.start_workflow(
        workflow="TIME_DEPOSIT_MATURITY",
        context={
            "account_id": vault.account_id,
            "applied_interest_amount": str(applied_interest),
        },
    )


def _check_account_closure_period_end(vault, denomination: str):
    """
    Triggers time deposit account closure workflow if the balance on the account
    is zero. The check happens after set number of days of grace period / deposit
    window / cool off period end date.
    """
    available_balance = _get_available_balance(
        vault,
        DEFAULT_ADDRESS,
        [Phase.PENDING_IN, Phase.COMMITTED],
        denomination,
    )

    if available_balance == 0:
        vault.start_workflow(
            workflow="TIME_DEPOSIT_CLOSURE",
            context={"account_id": vault.account_id},
        )


# Helper functions
def _get_period_end_date(
    account_creation_date: datetime, delta_days: int, period_end_hour: int
) -> Union[datetime, None]:
    """
    Calculate correct period close datetime

    :param account_creation_date: account creation date and time
    :param delta_days: period length in days
    :param period_end_hour: hour at which period ends (24-hour)
    :return: period end date
    """
    if delta_days <= 0:
        return None

    end_date = account_creation_date + timedelta(
        days=int(delta_days),
        hour=int(period_end_hour),
        minute=0,
        second=0,
    )

    return end_date


def _get_available_balance(
    vault,
    balance_address: str,
    phases_to_include: str,
    denomination: str,
) -> Decimal:
    """
    Retrieve available balance for provided balance address and list of phases.
    Note: Ringfencing funds in Phase.PENDING_OUT is opposite sign to committed, e.g. for liability
          account to get available balance should be Phase.COMMITTED + Phase.PENDING_OUT as
          Phase.PENDING_OUT will be negative

    :param vault:
    :param balance_address: address of the balance
    :param phases_to_include: phase of the balance
    :return: available balance on the address
    """
    return sum(
        vault.modules["utils"].get_balance_sum(
            vault=vault,
            addresses=[balance_address],
            denomination=denomination,
            phase=phase,
        )
        for phase in phases_to_include
    )


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

    interest_accrual_schedule = {
        "hour": str(interest_accrual_hour),
        "minute": str(interest_accrual_minute),
        "second": str(interest_accrual_second),
    }

    return interest_accrual_schedule


def _get_apply_accrued_interest_date(
    vault, interest_application_frequency, interest_application_day, effective_date
):
    """
    Gets next scheduled APPLY_ACCRUED_INTEREST event based on parameters

    :param vault: Vault object
    :param interest_application_frequency: str, One of "monthly", "quarterly",
                                           or "annually" or required frequency
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


def _get_apply_accrued_interest_schedule(
    vault, interest_application_frequency, interest_application_day, effective_date
):
    """
    Sets up dictionary of next scheduled APPLY_ACCRUED_INTEREST schedule based on parameters

    :param vault: Vault object
    :param interest_application_frequency: str, One of "monthly", "quarterly",
                                           or "annually" or required frequency
    :param interest_application_day: int, intended day of month for interest application
    :param effective_date: datetime, date and time of hook being run
    :return: dict, representation of APPLY_ACCRUED_INTEREST schedule
    """
    apply_accrued_interest_date = _get_apply_accrued_interest_date(
        vault, interest_application_frequency, interest_application_day, effective_date
    )

    return vault.modules["utils"].create_schedule_dict_from_datetime(apply_accrued_interest_date)


def _adjust_capitalised_interest(
    vault, denomination: str, effective_date: datetime, auto_rollover_type: Optional[str] = None
):
    """
    Moves capitalised interest to internal contra address for rebalancing if the default
    is less than capitalised interest

    :param: vault: Vault object
    :param: denomination: denomination parameter to be used
    :param: effective_date: date and time of hook being run
    :param: auto_rollover_type: type of autoroll over to be applied after maturity. If
                                auto_rollover_type == "principal_and_interest", we assume
                                DEFAULT balance is being transferred to new TD account, and
                                thus we want to flatten capitalised interest to close the
                                original TD account.
    """
    default_balance = (
        _get_available_balance(
            vault,
            DEFAULT_ADDRESS,
            [Phase.COMMITTED, Phase.PENDING_OUT],
            denomination,
        )
        if auto_rollover_type != "principal_and_interest"
        else 0
    )

    capitalised_interest_balance = _get_available_balance(
        vault,
        CAPITALISED_INTEREST,
        [Phase.COMMITTED, Phase.PENDING_OUT],
        denomination,
    )

    adjustment_amount = default_balance - capitalised_interest_balance

    if adjustment_amount < 0:
        posting_instructions = vault.make_internal_transfer_instructions(
            amount=abs(adjustment_amount),
            denomination=denomination,
            from_account_id=vault.account_id,
            from_account_address=CAPITALISED_INTEREST,
            to_account_id=vault.account_id,
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            client_transaction_id=f"MOVE_CAPITALISED_INTEREST_TO_INTERNAL_CONTRA_"
            f"{vault.get_hook_execution_id()}_"
            f"{denomination}_CUSTOMER",
            instruction_details={"description": "Moving capitalised interest to internal contra"},
        )

        vault.instruct_posting_batch(
            posting_instructions=posting_instructions, effective_date=effective_date
        )


def _get_account_close_schedule(
    vault,
    account_creation_date: datetime,
    delta_days: int,
    period_end_hour: int,
    account_closure_period: int,
) -> dict:
    """
    Sets up dictionary of account close schedule from
    deposit period, grace period or cool_off_period

    :param vault:
    :param account_creation_date: account creation in Vault
    :param delta_days: offset number of days
    :param period_end_hour: close close hour (24-hour)
    :param account_closure_period: number of days before account gets closed
    :return: schedule of account close date
    """
    account_close_datetime = _get_account_close_date(
        account_creation_date,
        delta_days,
        period_end_hour,
        account_closure_period,
    )
    return vault.modules["utils"].create_schedule_dict_from_datetime(account_close_datetime)


def _get_account_close_date(
    account_creation_date: datetime,
    delta_days: int,
    period_end_hour: int,
    account_closure_period: int,
) -> datetime:
    """
    Calculates account close date.
    :param account_creation_date: account creation in Vault
    :param delta_days: number of days from account creation date
    :param period_end_hour: close close hour (24-hour)
    :param account_closure_period: number of days before account gets closed
    :return: account close date
    """
    account_close_datetime = account_creation_date + timedelta(
        days=int(delta_days) + int(account_closure_period),
        hour=int(period_end_hour),
    )
    if account_close_datetime < account_creation_date:
        account_close_datetime = account_creation_date

    return account_close_datetime


def _get_account_maturity_schedule(
    vault,
    term_unit: str,
    term: int,
    account_creation_date: datetime,
    calendar_events: List[CalendarEvent],
) -> Dict:
    """
    Sets up dictionary of account maturity schedule
    """
    account_maturity_date = _get_account_maturity_date(
        term_unit, term, account_creation_date, calendar_events
    )
    return vault.modules["utils"].create_schedule_dict_from_datetime(account_maturity_date)


def _get_account_maturity_date(
    term_unit: str,
    term: int,
    account_creation_date: datetime,
    calendar_events: List[CalendarEvent],
) -> datetime:
    """
    Calculates account maturity date.
    """
    add_timedelta = timedelta(days=term) if term_unit == "days" else timedelta(months=term)
    account_maturity_date = account_creation_date + add_timedelta
    account_maturity_date = _get_maturity_date_base_on_calendar_events(
        account_maturity_date, calendar_events
    )

    return account_maturity_date


def _get_next_schedule_date(start_date, schedule_frequency, intended_day):
    """
    Calculate next valid date for schedule based on required frequency and day of month.
    Falls to last valid day of month if intended day is not in calculated month

    :param start_date: datetime, from which schedule frequency is calculated from
    :param schedule_frequency: str, One of "monthly", "quarterly",
                                    or "annually" or required frequency
    :param intended_day: int, day of month the scheduled date should fall on
    :return: datetime, next occurrence of schedule
    """
    frequency_map = {
        "months": {"monthly": 1, "quarterly": 3, "semi_annually": 6, "annually": 12},
        "days": {"fortnightly": 14, "four_weekly": 28, "weekly": 7},
    }

    # used set default over get since this is faster and it will only add 1 record at most
    number_of_months = frequency_map["months"].setdefault(schedule_frequency, 0)
    number_of_days = frequency_map["days"].setdefault(schedule_frequency, 0)

    delta = None
    if number_of_days != 0:
        # set the timedelta to add the number of days
        delta = timedelta(days=number_of_days)
    else:
        # set the intended day of the month since it is incrementing by months
        delta = timedelta(day=intended_day)

    if (schedule_frequency == "monthly") and (start_date + delta > start_date):
        # check for monthly if next schedule is this month or next month.
        next_schedule_date = start_date + delta
    else:
        # apply the months and days depending on the frequency selected.
        next_schedule_date = start_date + timedelta(months=number_of_months) + delta
    return next_schedule_date


def _get_parameter_value(parameter_name, old_parameter_values, updated_parameter_values):
    """
    Returns value of a parameter - updated value if changed, otherwise takes original value.
    To be used in post_parameter_change hook
    :param parameter_name: str, name of the parameter
    :param old_parameter_values: dict, map of parameter name -> old parameter value
    :param updated_parameter_values: dict, map of parameter name -> new parameter value
    :return: Value of parameter
    """

    if parameter_name in updated_parameter_values:
        return updated_parameter_values[parameter_name]
    else:
        return old_parameter_values[parameter_name]


def _falls_on_calendar_events(
    effective_date: datetime, calendar_events: List[CalendarEvent] = None
) -> bool:
    """
    Returns if true if the given date lands on a events in the calendar
    """
    return any(
        True
        if (calendar_event.start_timestamp <= effective_date)
        and (effective_date <= calendar_event.end_timestamp)
        else False
        for calendar_event in calendar_events or []
    )


def _get_maturity_date_base_on_calendar_events(
    account_maturity_date: datetime, calendar_events: List[CalendarEvent] = None
) -> datetime:
    """
    Returns the next account_maturity_date if the account_maturity_date
    lands on a events in the calendar
    """
    while _falls_on_calendar_events(account_maturity_date, calendar_events):
        account_maturity_date = account_maturity_date + timedelta(days=1)
    return account_maturity_date


def _get_available_fee_free_limit(
    latest_available_balance: Decimal, fee_free_percentage_limit: float
) -> Decimal:
    """
    Retrieves the available fee free limit.
    :param latest_available_balance: Latest available balance on the account
    :param fee_free_percentage_limit: fee free fee free percentage limit on the account
    :param daily_withdrawn_amount: Daily withdrawn amount so far
    :return: The daily limit availble for fee free
    """
    available_fee_free_limit = latest_available_balance * fee_free_percentage_limit

    return available_fee_free_limit.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def _validate_deposits(
    vault,
    effective_date: datetime,
    denomination: str,
    deposit_end_date: datetime,
    proposed_amount: Decimal,
    latest_available_balance: Decimal,
):

    if effective_date >= deposit_end_date:
        raise Rejected(
            f"Deposit value_timestamp {effective_date} is greater than "
            f"maximum deposit date {deposit_end_date}",
            reason_code=RejectedReason.AGAINST_TNC,
        )

    minimum_deposit_amount = vault.modules["utils"].get_parameter(
        vault, name="minimum_first_deposit"
    )
    maximum_balance = vault.modules["utils"].get_parameter(vault, name="maximum_balance")
    single_deposit = vault.modules["utils"].get_parameter(vault, name="single_deposit", union=True)

    if proposed_amount < minimum_deposit_amount and not latest_available_balance > 0:
        raise Rejected(
            f"Deposit amount less than minimum first deposit amount "
            f"{minimum_deposit_amount} {denomination}",
            reason_code=RejectedReason.AGAINST_TNC,
        )
    if single_deposit == "single" and latest_available_balance > 0:
        raise Rejected(
            "No deposits allowed after initial deposit",
            reason_code=RejectedReason.AGAINST_TNC,
        )

    if latest_available_balance + proposed_amount > maximum_balance:
        raise Rejected(
            "Posting would cause maximum balance to be exceeded",
            reason_code=RejectedReason.AGAINST_TNC,
        )


def _validate_withdrawals(
    vault,
    effective_date: datetime,
    account_maturity_date: datetime,
    withdrawal_end_date: datetime,
    proposed_amount: Decimal,
    calendar_events: CalendarEvents,
    postings,
):
    if _falls_on_calendar_events(effective_date, calendar_events) and not vault.modules[
        "utils"
    ].str_to_bool(postings.batch_details.get("calendar_override")):
        raise Rejected(
            "Withdrawals not allowed on holiday",
            reason_code=RejectedReason.AGAINST_TNC,
        )

    if not vault.modules["utils"].str_to_bool(postings.batch_details.get("withdrawal_override")):
        if (
            withdrawal_end_date
            and effective_date >= withdrawal_end_date
            and effective_date < account_maturity_date
        ):
            raise Rejected(
                f"Withdrawal value_timestamp {effective_date} is greater than "
                f"maximum withdrawal date {withdrawal_end_date}",
                reason_code=RejectedReason.AGAINST_TNC,
            )
