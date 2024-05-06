# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
api = "3.9.0"
version = "4.8.4"
display_name = "Mortgage"
summary = "Fixed and variable rate mortgage with configuration repayment options."
tside = Tside.ASSET

# this can be amended to whichever other currencies as needed
supported_denominations = ["GBP"]

# Schedule events
ACCRUE_INTEREST = "ACCRUE_INTEREST"
REPAYMENT_DAY_SCHEDULE = "REPAYMENT_DAY_SCHEDULE"
HANDLE_OVERPAYMENT_ALLOWANCE = "HANDLE_OVERPAYMENT_ALLOWANCE"
CHECK_DELINQUENCY = "CHECK_DELINQUENCY"

event_types = [
    EventType(name=ACCRUE_INTEREST, scheduler_tag_ids=["MORTGAGE_ACCRUE_INTEREST_AST"]),
    EventType(
        name=REPAYMENT_DAY_SCHEDULE,
        scheduler_tag_ids=["MORTGAGE_REPAYMENT_DAY_SCHEDULE_AST"],
    ),
    EventType(
        name=HANDLE_OVERPAYMENT_ALLOWANCE,
        scheduler_tag_ids=["MORTGAGE_HANDLE_OVERPAYMENT_ALLOWANCE_AST"],
    ),
    EventType(name=CHECK_DELINQUENCY, scheduler_tag_ids=["MORTGAGE_CHECK_DELINQUENCY_AST"]),
]

PRINCIPAL_DUE = "PRINCIPAL_DUE"
EMI_PRINCIPAL_EXCESS = "EMI_PRINCIPAL_EXCESS"
INTEREST_DUE = "INTEREST_DUE"
PRINCIPAL = "PRINCIPAL"
OVERPAYMENT = "OVERPAYMENT"
PENALTIES = "PENALTIES"
EMI_ADDRESS = "EMI"
PRINCIPAL_OVERDUE = "PRINCIPAL_OVERDUE"
INTEREST_OVERDUE = "INTEREST_OVERDUE"
ACCRUED_INTEREST = "ACCRUED_INTEREST"
ACCRUED_EXPECTED_INTEREST = "ACCRUED_EXPECTED_INTEREST"
CAPITALISED_INTEREST = "CAPITALISED_INTEREST"
PRINCIPAL_CAPITALISED_INTEREST = "PRINCIPAL_CAPITALISED_INTEREST"
INTERNAL_CONTRA = "INTERNAL_CONTRA"

DAYS_IN_A_WEEK = 7
DAYS_IN_A_YEAR = 365
WEEKS_IN_YEAR = 52
MONTHS_IN_A_YEAR = 12

OVERDUE_ADDRESSES = [PRINCIPAL_OVERDUE, INTEREST_OVERDUE]
LATE_PAYMENT_ADDRESSES = OVERDUE_ADDRESSES + [PENALTIES]
REPAYMENT_ORDER = LATE_PAYMENT_ADDRESSES + [PRINCIPAL_DUE, INTEREST_DUE]
EXPECTED_PRINCIPAL = [PRINCIPAL, PRINCIPAL_CAPITALISED_INTEREST]
REMAINING_PRINCIPAL = [
    PRINCIPAL,
    OVERPAYMENT,
    EMI_PRINCIPAL_EXCESS,
    PRINCIPAL_CAPITALISED_INTEREST,
]
ALL_ADDRESSES = REPAYMENT_ORDER + REMAINING_PRINCIPAL + [ACCRUED_INTEREST]


RateShape = NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.0001)

parameters = [
    # Instance Parameters
    Parameter(
        name="fixed_interest_rate",
        shape=RateShape,
        level=Level.INSTANCE,
        description="The fixed annual rate of the mortgage.",
        display_name="Fixed interest rate (p.a.)",
        default_value=Decimal("0.129971"),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="overpayment_percentage",
        shape=RateShape,
        level=Level.INSTANCE,
        description="Percent of outstanding principal that can be paid off per year "
        "without charge.",
        display_name="Allowed overpayment percentage",
        default_value=Decimal("0.1"),
        update_permission=UpdatePermission.FIXED,
    ),
    Parameter(
        name="overpayment_fee_percentage",
        shape=RateShape,
        level=Level.INSTANCE,
        description="Percentage of overpaid principal to charge when going over "
        "overpayment allowance.",
        display_name="Overpayment fee percentage",
        default_value=Decimal("0.05"),
        update_permission=UpdatePermission.FIXED,
    ),
    Parameter(
        name="fixed_interest_term",
        shape=NumberShape(min_value=Decimal(0), step=Decimal(1)),
        level=Level.INSTANCE,
        description="The agreed length of the fixed rate portion of the mortgage (in months).",
        display_name="Fixed rate Mortgage term (months)",
        default_value=Decimal(0),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="interest_only_term",
        shape=NumberShape(min_value=Decimal(0), step=Decimal(1)),
        level=Level.INSTANCE,
        description="The agreed length of the interest only portion of the mortgage (in months).",
        display_name="Interest only Mortgage term (months)",
        default_value=Decimal(0),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="total_term",
        shape=NumberShape(min_value=Decimal(1), step=Decimal(1)),
        level=Level.INSTANCE,
        description="The agreed length of the mortgage (in months).",
        display_name="Mortgage term (months)",
        default_value=Decimal(1),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="principal",
        shape=NumberShape(kind=NumberKind.MONEY),
        level=Level.INSTANCE,
        description="The agreed amount the customer will borrow from the bank.",
        display_name="Mortgage principal",
        default_value=Decimal(100000),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="repayment_day",
        shape=NumberShape(
            min_value=1,
            max_value=28,
            step=1,
        ),
        level=Level.INSTANCE,
        description="The day of the month the customer will make monthly repayments."
        " This day must be between the 1st and 28th day of the month.",
        display_name="Repayment day",
        default_value=Decimal(28),
        update_permission=UpdatePermission.USER_EDITABLE,
    ),
    Parameter(
        name="deposit_account",
        shape=AccountIdShape,
        level=Level.INSTANCE,
        description="The account to which the principal borrowed amount will be transferred.",
        display_name="Deposit account",
        default_value="00000000-0000-0000-0000-000000000000",
        update_permission=UpdatePermission.FIXED,
    ),
    Parameter(
        name="variable_rate_adjustment",
        shape=NumberShape(kind=NumberKind.PERCENTAGE, min_value=-1, max_value=1, step=0.0001),
        level=Level.INSTANCE,
        description="Account level adjustment to be added to variable interest rate, "
        "can be positive, negative or zero.",
        display_name="Variable rate adjustment",
        default_value=Decimal("0.00"),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="mortgage_start_date",
        shape=DateShape(min_date=datetime.min, max_date=datetime.max),
        level=Level.INSTANCE,
        description="Start of the mortgage contract terms, either after account opening "
        "or product switching.",
        display_name="Contract effective date",
        default_value=datetime.utcnow(),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    # Derived Parameters
    Parameter(
        name="total_outstanding_debt",
        shape=NumberShape(kind=NumberKind.MONEY),
        level=Level.INSTANCE,
        derived=True,
        description="Remaining total balance on this account (including fees).",
        display_name="Total outstanding debt",
    ),
    Parameter(
        name="remaining_principal",
        shape=NumberShape(kind=NumberKind.MONEY),
        level=Level.INSTANCE,
        derived=True,
        description="Total remaining principal on this account.",
        display_name="Remaining Principal",
    ),
    Parameter(
        name="overpayment_allowance_remaining",
        shape=NumberShape(kind=NumberKind.MONEY),
        level=Level.INSTANCE,
        derived=True,
        description="Allowance remaining that can be overpaid during this period without fee.",
        display_name="Overpayment Allowance Remaining",
    ),
    Parameter(
        name="overpaid_this_period",
        shape=NumberShape(kind=NumberKind.MONEY),
        level=Level.INSTANCE,
        derived=True,
        description="Amount overpaid this period.",
        display_name="Overpaid this period",
    ),
    Parameter(
        name="is_fixed_interest",
        shape=StringShape,
        level=Level.INSTANCE,
        derived=True,
        description="Is this account within the fixed interest period.",
        display_name="In fixed interest Period",
    ),
    Parameter(
        name="is_interest_only_term",
        shape=StringShape,
        level=Level.INSTANCE,
        derived=True,
        description="Is this account within the interest only term period.",
        display_name="In interest only term period",
    ),
    Parameter(
        name="outstanding_payments",
        shape=NumberShape(kind=NumberKind.MONEY),
        level=Level.INSTANCE,
        derived=True,
        description="Unpaid dues, overdues and penalties",
        display_name="Outstanding payments",
    ),
    Parameter(
        name="remaining_term",
        shape=NumberShape(),
        level=Level.INSTANCE,
        derived=True,
        description="Remaining total term of the mortgage in months",
        display_name="Remaining term in months",
    ),
    Parameter(
        name="next_repayment_date",
        shape=DateShape(min_date=datetime.min, max_date=datetime.max),
        level=Level.INSTANCE,
        derived=True,
        description="Next scheduled repayment date",
        display_name="Next Repayment date",
    ),
    # Template Parameters
    Parameter(
        name="denomination",
        shape=DenominationShape,
        level=Level.TEMPLATE,
        description="Currency in which the product operates.",
        display_name="Denomination.",
        default_value="GBP",
    ),
    Parameter(
        name="variable_interest_rate",
        shape=RateShape,
        level=Level.TEMPLATE,
        description="The annual rate of the mortgage to be applied after the fixed rate term.",
        display_name="Variable interest rate (p.a.)",
        default_value=Decimal("0.129971"),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="late_repayment_fee",
        shape=NumberShape(kind=NumberKind.MONEY),
        level=Level.TEMPLATE,
        description="Fee to apply due to late repayment.",
        display_name="Late repayment fee",
        default_value=Decimal("15"),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="penalty_interest_rate",
        shape=RateShape,
        level=Level.TEMPLATE,
        description="The annual interest rate to be applied to overdues.",
        display_name="Penalty interest rate (p.a.)",
        default_value=Decimal("0.129971"),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="penalty_includes_base_rate",
        level=Level.TEMPLATE,
        description="Whether to add base interest rate on top of penalty interest rate.",
        display_name="Penalty includes base rate",
        shape=UnionShape(
            UnionItem(key="True", display_name="True"),
            UnionItem(key="False", display_name="False"),
        ),
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=UnionItemValue(key="True"),
    ),
    Parameter(
        name="grace_period",
        shape=NumberShape(
            max_value=28,
            min_value=0,
            step=1,
        ),
        level=Level.TEMPLATE,
        description="The number of days after which the account becomes delinquent "
        "if overdue amount and their penalties are not paid in full.",
        display_name="Grace period (days)",
        default_value=Decimal(15),
    ),
    Parameter(
        name="overpayment_impact_preference",
        shape=UnionShape(
            UnionItem(key="reduce_term", display_name="Reduce term"),
            UnionItem(key="reduce_emi", display_name="Reduce EMI"),
        ),
        level=Level.TEMPLATE,
        description="Defines how to handle an overpayment on a mortgage:"
        "Reduce EMI but keep the term of the mortgage the same."
        "Reduce term but keep the monthly repayments the same.",
        display_name="Overpayment impact preference",
        default_value=UnionItemValue(key="reduce_term"),
    ),
    Parameter(
        name="accrue_interest_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which interest is accrued.",
        display_name="Accrue interest hour",
        default_value=0,
    ),
    Parameter(
        name="accrue_interest_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the day at which interest is accrued.",
        display_name="Accrue interest minute",
        default_value=0,
    ),
    Parameter(
        name="accrue_interest_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the day at which interest is accrued.",
        display_name="Accrue interest second",
        default_value=1,
    ),
    Parameter(
        name="check_delinquency_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which delinquency is checked.",
        display_name="Check delinquency hour",
        default_value=0,
    ),
    Parameter(
        name="check_delinquency_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the day at which delinquency is checked.",
        display_name="Check delinquency minute",
        default_value=0,
    ),
    Parameter(
        name="check_delinquency_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the day at which delinquency is checked.",
        display_name="Check delinquency second",
        default_value=2,
    ),
    Parameter(
        name="repayment_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which due amount is calculated.",
        display_name="Check delinquency hour",
        default_value=0,
    ),
    Parameter(
        name="repayment_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the day at which which due amount is calculated.",
        display_name="Check delinquency minute",
        default_value=1,
    ),
    Parameter(
        name="repayment_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the day at which which due amount is calculated.",
        display_name="Check delinquency second",
        default_value=0,
    ),
    Parameter(
        name="overpayment_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which overpayment is checked.",
        display_name="Check delinquency hour",
        default_value=0,
    ),
    Parameter(
        name="overpayment_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the day at which which overpayment is checked.",
        display_name="Check delinquency minute",
        default_value=0,
    ),
    Parameter(
        name="overpayment_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the day at which which overpayment is checked.",
        display_name="Check delinquency second",
        default_value=0,
    ),
    Parameter(
        name="accrual_precision",
        shape=NumberShape(kind=NumberKind.PLAIN, min_value=0, max_value=15, step=1),
        level=Level.TEMPLATE,
        description="Precision needed for interest accruals.",
        display_name="Interest accrual precision",
        default_value=Decimal(5),
    ),
    Parameter(
        name="fulfillment_precision",
        shape=NumberShape(kind=NumberKind.PLAIN, min_value=0, max_value=4, step=1),
        level=Level.TEMPLATE,
        description="Precision needed for interest fulfillment.",
        display_name="Interest fulfillment precision",
        default_value=Decimal(2),
    ),
    # Flag definitions
    Parameter(
        name="delinquency_flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="Flag definition id to be used for account delinquency.",
        display_name="Account delinquency flag",
        default_value=json_dumps(["ACCOUNT_DELINQUENT"]),
    ),
    Parameter(
        name="delinquency_blocking_flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="The list of flag definitions which block an account becoming delinquent.",
        display_name="Delinquency blocking flag",
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
    Parameter(
        name="due_amount_blocking_flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="The list of flag definitions which block due amount transfers.",
        display_name="Due amount blocking flag",
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
    Parameter(
        name="overdue_amount_blocking_flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="The list of flag definitions which block overdue amount transfers.",
        display_name="Overdue amount blocking flag",
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
    Parameter(
        name="penalty_blocking_flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="The list of flag definitions which block interest penalties.",
        display_name="Penalty blocking flag",
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
    Parameter(
        name="repayment_blocking_flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        description="The list of flag definitions which block repayments.",
        display_name="Repayment blocking flag",
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
    # Internal Accounts
    Parameter(
        name="accrued_interest_receivable_account",
        level=Level.TEMPLATE,
        description="Internal account for accrued interest receivable balance.",
        display_name="Accrued interest receivable account",
        shape=AccountIdShape,
        default_value="ACCRUED_INTEREST_RECEIVABLE",
    ),
    Parameter(
        name="capitalised_interest_received_account",
        level=Level.TEMPLATE,
        description="Internal account for capitalised interest received balance.",
        display_name="Capitalised interest received account",
        shape=AccountIdShape,
        default_value="CAPITALISED_INTEREST_RECEIVED",
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
        name="penalty_interest_received_account",
        level=Level.TEMPLATE,
        description="Internal account for penalty interest received balance.",
        display_name="Penalty interest received account",
        shape=AccountIdShape,
        default_value="PENALTY_INTEREST_RECEIVED",
    ),
    Parameter(
        name="late_repayment_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for late repayment fee income balance.",
        display_name="Late repayment fee income account",
        shape=AccountIdShape,
        default_value="LATE_REPAYMENT_FEE_INCOME",
    ),
    Parameter(
        name="overpayment_allowance_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for overpayment allowance fee income balance.",
        display_name="Overpayment allowance fee income account",
        shape=AccountIdShape,
        default_value="OVERPAYMENT_ALLOWANCE_FEE_INCOME",
    ),
]

contract_module_imports = [
    ContractModule(
        alias="amortisation",
        expected_interface=[
            SharedFunction(name="construct_interest_only_amortisation_input"),
            SharedFunction(name="calculate_interest_only_repayment"),
        ],
    ),
    ContractModule(
        alias="utils",
        expected_interface=[
            SharedFunction(name="get_balance_sum"),
            SharedFunction(name="str_to_bool"),
            SharedFunction(name="get_parameter"),
            SharedFunction(name="has_parameter_value_changed"),
            SharedFunction(name="is_flag_in_list_applied"),
        ],
    ),
]


# Vault hooks
@requires(modules=["utils"], parameters=True)
def execution_schedules():
    repayment_day = vault.modules["utils"].get_parameter(vault, name="repayment_day")
    mortgage_start_date = (
        vault.modules["utils"].get_parameter(vault, name="mortgage_start_date").date()
    )
    mortgage_start_date_plus_day = mortgage_start_date + timedelta(days=1)
    repayment_day_schedule = _get_handle_repayment_day_schedule(vault, repayment_day)
    handle_overpayment_allowance_schedule = _get_handle_overpayment_allowance_schedule(vault)
    accrue_interest_schedule = {
        "hour": str(vault.modules["utils"].get_parameter(vault, "accrue_interest_hour")),
        "minute": str(vault.modules["utils"].get_parameter(vault, "accrue_interest_minute")),
        "second": str(vault.modules["utils"].get_parameter(vault, "accrue_interest_second")),
        "start_date": str(mortgage_start_date_plus_day),
    }
    check_delinquency_schedule = {
        "hour": str(vault.modules["utils"].get_parameter(vault, "check_delinquency_hour")),
        "minute": str(vault.modules["utils"].get_parameter(vault, "check_delinquency_minute")),
        "second": str(vault.modules["utils"].get_parameter(vault, "check_delinquency_second")),
        "end_date": str(mortgage_start_date_plus_day),
        "start_date": str(mortgage_start_date_plus_day),
    }
    return [
        (ACCRUE_INTEREST, accrue_interest_schedule),
        (REPAYMENT_DAY_SCHEDULE, repayment_day_schedule),
        (HANDLE_OVERPAYMENT_ALLOWANCE, handle_overpayment_allowance_schedule),
        (CHECK_DELINQUENCY, check_delinquency_schedule),
    ]


@requires(
    modules=["utils"],
    event_type="ACCRUE_INTEREST",
    parameters=True,
    balances="latest live",
    last_execution_time=["REPAYMENT_DAY_SCHEDULE"],
    flags=True,
)
@requires(
    modules=["amortisation", "utils"],
    event_type="REPAYMENT_DAY_SCHEDULE",
    parameters=True,
    balances="2 months",
    last_execution_time=["REPAYMENT_DAY_SCHEDULE"],
    flags=True,
)
@requires(
    modules=["utils"],
    event_type="HANDLE_OVERPAYMENT_ALLOWANCE",
    parameters=True,
    balances="1 year",
)
@requires(
    modules=["utils"],
    event_type="CHECK_DELINQUENCY",
    parameters=True,
    balances="latest live",
    flags=True,
)
def scheduled_code(event_type: str, effective_date: datetime):
    if event_type == ACCRUE_INTEREST:
        _accrue_interest(vault, effective_date)
    elif event_type == REPAYMENT_DAY_SCHEDULE:
        _handle_repayment_due(vault, effective_date)
    elif event_type == HANDLE_OVERPAYMENT_ALLOWANCE:
        _check_if_over_overpayment_allowance_and_charge_fee(vault, effective_date)
    elif event_type == CHECK_DELINQUENCY:
        _check_delinquency(vault, effective_date)


@requires(
    modules=["amortisation", "utils"],
    parameters=True,
    balances="1 year",
    last_execution_time=["HANDLE_OVERPAYMENT_ALLOWANCE", "REPAYMENT_DAY_SCHEDULE"],
)
def derived_parameters(effective_date):
    last_overpayment_allowance_check = vault.get_last_execution_time(
        event_type=HANDLE_OVERPAYMENT_ALLOWANCE
    )
    mortgage_start_date = vault.modules["utils"].get_parameter(vault, name="mortgage_start_date")

    # Using account_creation_date when no previous execution to avoid edge case
    # where mortgage_start_date has a timestamp that is slightly before
    # creation_date timestamp, as mortgage_start_date was set
    # during account opening workflow
    start_of_overpayment_period = (
        vault.get_account_creation_date()
        if last_overpayment_allowance_check is None
        else max(mortgage_start_date, last_overpayment_allowance_check)
    )

    overpayment_percentage = vault.modules["utils"].get_parameter(
        vault, name="overpayment_percentage", at=start_of_overpayment_period
    )

    last_period_overpayment_balance = _get_effective_balance_by_address(
        vault, OVERPAYMENT, start_of_overpayment_period
    )
    last_period_principal_balance = _get_effective_balance_by_address(
        vault, PRINCIPAL, start_of_overpayment_period
    )
    current_overpayment_balance = _get_effective_balance_by_address(vault, OVERPAYMENT)

    overpayment_allowance = last_period_principal_balance * overpayment_percentage
    overpaid_this_year = abs(current_overpayment_balance - last_period_overpayment_balance)
    overpayment_allowance_remaining = overpayment_allowance - overpaid_this_year

    return {
        "total_outstanding_debt": _get_all_outstanding_debt(vault),
        "remaining_principal": _get_outstanding_actual_principal(vault),
        "is_fixed_interest": str(_is_within_term(vault, effective_date, "fixed_interest_term")),
        "is_interest_only_term": str(_is_within_term(vault, effective_date, "interest_only_term")),
        "overpayment_allowance_remaining": overpayment_allowance_remaining,
        "overpaid_this_period": overpaid_this_year,
        "outstanding_payments": _sum_outstanding_dues(vault),
        "next_repayment_date": _calculate_next_repayment_date(vault, effective_date),
        "remaining_term": _get_remaining_term_in_months(vault, effective_date, "total_term"),
    }


@requires(modules=["utils"], parameters=True)
def post_activate_code():
    # using account creation date instead of loan start date to:
    # avoid back dating time component (date param will default to midnight)
    # this logic will only run for initial disbursement, not subsequent topups
    # therefore creation_date and loan_start_date are equivalent here
    start_date = vault.get_account_creation_date()
    principal = vault.modules["utils"].get_parameter(vault, name="principal")
    deposit_account_id = vault.modules["utils"].get_parameter(vault, name="deposit_account")
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")

    posting_ins = vault.make_internal_transfer_instructions(
        amount=principal,
        denomination=denomination,
        client_transaction_id=vault.get_hook_execution_id() + "_PRINCIPAL",
        from_account_id=vault.account_id,
        from_account_address=PRINCIPAL,
        to_account_id=deposit_account_id,
        to_account_address=DEFAULT_ADDRESS,
        instruction_details={
            "description": f"Payment of {principal} of mortgage principal",
            "event": "PRINCIPAL_PAYMENT",
        },
        asset=DEFAULT_ASSET,
    )
    vault.instruct_posting_batch(posting_instructions=posting_ins, effective_date=start_date)


@requires(
    modules=["utils"],
    parameters=True,
    last_execution_time=["REPAYMENT_DAY_SCHEDULE"],
    flags=True,
    balances="latest live",
)
def post_parameter_change_code(old_parameter_values, updated_parameter_values, effective_date):
    _handle_repayment_day_change(
        vault, old_parameter_values, updated_parameter_values, effective_date
    )
    _handle_product_switching(vault, updated_parameter_values, effective_date)


@requires(modules=["utils"], parameters=True, balances="latest live", flags=True)
def pre_posting_code(postings, effective_date):
    if len(postings) > 1:
        raise Rejected(
            "Multiple postings in batch not supported",
            reason_code=RejectedReason.CLIENT_CUSTOM_REASON,
        )

    if vault.modules["utils"].str_to_bool(postings.batch_details.get("withdrawal_override")):
        # Allow this posting by returning straight away
        return

    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    for posting in postings:
        if posting.denomination != denomination:
            raise Rejected(
                "Cannot make transactions in given denomination; "
                f"transactions must be in {denomination}",
                reason_code=RejectedReason.WRONG_DENOMINATION,
            )
        if posting.credit:
            if vault.modules["utils"].is_flag_in_list_applied(
                vault, "repayment_blocking_flags", effective_date
            ):
                raise Rejected(
                    "Repayments blocked for this account.",
                    reason_code=RejectedReason.AGAINST_TNC,
                )
            outstanding_debt = _get_all_outstanding_debt(vault)
            if posting.amount > outstanding_debt:
                raise Rejected(
                    "Cannot pay more than is owed",
                    reason_code=RejectedReason.AGAINST_TNC,
                )
        elif not vault.modules["utils"].str_to_bool(
            postings.batch_details.get("fee")
        ) and not vault.modules["utils"].str_to_bool(
            postings.batch_details.get("interest_adjustment")
        ):
            raise Rejected(
                "Debiting not allowed from this account",
                reason_code=RejectedReason.AGAINST_TNC,
            )


@requires(modules=["utils"], parameters=True, balances="latest live", flags=True)
def post_posting_code(postings, effective_date):

    effective_date = effective_date + timedelta(microseconds=1)
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    for i, posting in enumerate(postings):
        posting_balance_delta = posting.balances()[
            (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
        ].net
        if posting_balance_delta == 0:
            continue
        if posting_balance_delta < 0:
            client_transaction_id = (
                f"{posting.client_transaction_id}_{vault.get_hook_execution_id()}_{i}"
            )
            _process_payment(
                vault,
                effective_date,
                posting_balance_delta,
                client_transaction_id,
                postings,
                denomination,
            )

        else:
            balance_destination = (
                PENALTIES
                if vault.modules["utils"].str_to_bool(postings.batch_details.get("fee"))
                else INTEREST_DUE
            )

            amount_to_transfer = posting.amount
            posting_ins = vault.make_internal_transfer_instructions(
                amount=amount_to_transfer,
                denomination=posting.denomination,
                client_transaction_id=vault.get_hook_execution_id() + "_" + balance_destination,
                from_account_id=vault.account_id,
                from_account_address=balance_destination,
                to_account_id=vault.account_id,
                to_account_address=DEFAULT_ADDRESS,
                instruction_details={
                    "description": f"Move {amount_to_transfer} of balance"
                    f" into {balance_destination} on {effective_date}",
                    "event": "MOVE_BALANCE_INTO_" + balance_destination,
                },
                asset=DEFAULT_ASSET,
            )

            if vault.modules["utils"].str_to_bool(
                postings.batch_details.get("interest_adjustment")
            ):
                posting_ins.extend(_get_interest_waiver_posting(vault))

            vault.instruct_posting_batch(
                posting_instructions=posting_ins, effective_date=effective_date
            )


@requires(modules=["utils"], parameters=True, balances="latest live")
def close_code(effective_date):

    if _get_all_outstanding_debt(vault) != 0:
        raise Rejected(
            "Cannot close account until account balance nets to 0",
            reason_code=RejectedReason.AGAINST_TNC,
        )
    _handle_end_of_mortgage(vault, effective_date)


# Hook functions
def _accrue_interest(vault, effective_date: datetime) -> None:
    """
    Handle the ACCRUE_INTEREST schedule by generating postings for interest, penalty
    interest and end of repayment holiday capitalisation of interest.
    """
    posting_instructions = _get_accrue_penalty_interest_instructions(vault, effective_date)
    amount_transferred, postings = _handle_end_blocking_flags(vault, effective_date)
    posting_instructions.extend(postings)
    posting_instructions.extend(
        _get_accrue_interest_instructions(
            vault, effective_date, extra_capitalised_interest=amount_transferred
        )
    )

    _instruct_posting_batch(vault, posting_instructions, effective_date, ACCRUE_INTEREST)


def _handle_repayment_due(vault, effective_date: datetime) -> None:
    """
    Handle the REPAYMENT_DAY_SCHEDULE by generating postings for transferring accrued interest
    and principal to the due addreses and any unpaid due amounts to their overdue addresses
    (charging any late payment fees that apply).
    """
    posting_instructions = _get_overdue_postings(
        vault, effective_date, PRINCIPAL_DUE, PRINCIPAL_OVERDUE
    )
    posting_instructions.extend(
        _get_overdue_postings(vault, effective_date, INTEREST_DUE, INTEREST_OVERDUE)
    )

    if len(posting_instructions) > 0:
        posting_instructions.extend(_get_late_repayment_fee_posting(vault))
        _schedule_delinquency_check(vault, effective_date)

    posting_instructions.extend(_get_due_postings(vault, effective_date))

    _instruct_posting_batch(vault, posting_instructions, effective_date, REPAYMENT_DAY_SCHEDULE)


def _get_accrue_interest_instructions(
    vault, effective_date: datetime, extra_capitalised_interest: Decimal = 0
) -> List[PostingInstruction]:
    accrual_precision = vault.modules["utils"].get_parameter(vault, name="accrual_precision")
    fulfillment_precision = vault.modules["utils"].get_parameter(
        vault, name="fulfillment_precision"
    )
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    accrued_interest_receivable_account = vault.modules["utils"].get_parameter(
        vault, name="accrued_interest_receivable_account"
    )
    interest_received_account = vault.modules["utils"].get_parameter(
        vault, name="interest_received_account"
    )
    interest_rate = _get_interest_rate(vault, effective_date)
    daily_interest_rate = _get_daily_interest_rate(interest_rate)

    expected_principal = _get_expected_principal(vault) + extra_capitalised_interest
    outstanding_principal = _get_outstanding_actual_principal(vault) + extra_capitalised_interest

    expected_interest_to_accrue = _round_to_precision(
        accrual_precision, expected_principal * daily_interest_rate
    )
    interest_to_accrue = _round_to_precision(
        accrual_precision, outstanding_principal * daily_interest_rate
    )

    posting_instructions = []

    # If on due amount blocking flag accrue on a different address
    if vault.modules["utils"].is_flag_in_list_applied(
        vault, "due_amount_blocking_flags", effective_date
    ):

        if interest_to_accrue > 0:
            capitalised_interest_to_accrue = _round_to_precision(
                fulfillment_precision, outstanding_principal * daily_interest_rate
            )
            capitalised_interest_received_account = vault.modules["utils"].get_parameter(
                vault, name="capitalised_interest_received_account"
            )

            posting_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=capitalised_interest_to_accrue,
                    denomination=denomination,
                    client_transaction_id=f"{vault.get_hook_execution_id()}_INTEREST_ACCRUAL"
                    f"_CUSTOMER",
                    from_account_id=vault.account_id,
                    from_account_address=CAPITALISED_INTEREST,
                    to_account_id=capitalised_interest_received_account,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": f"Daily capitalised interest accrued at "
                        f"{daily_interest_rate*100:0.6f}%"
                        f" on outstanding principal of {outstanding_principal}",
                        "event_type": "ACCRUE_CAPITALISED_INTEREST",
                        "daily_interest_rate": f"{daily_interest_rate}",
                    },
                    asset=DEFAULT_ASSET,
                )
            )
    else:
        if interest_to_accrue > 0:
            posting_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=interest_to_accrue,
                    denomination=denomination,
                    client_transaction_id=f"{vault.get_hook_execution_id()}_INTEREST_ACCRUAL"
                    f"_CUSTOMER",
                    from_account_id=vault.account_id,
                    from_account_address=ACCRUED_INTEREST,
                    to_account_id=vault.account_id,
                    to_account_address=INTERNAL_CONTRA,
                    instruction_details={
                        "description": f"Daily interest accrued at {daily_interest_rate*100:0.6f}%"
                        f" on outstanding principal of {outstanding_principal}",
                        "event_type": ACCRUE_INTEREST,
                        "daily_interest_rate": f"{daily_interest_rate}",
                    },
                    asset=DEFAULT_ASSET,
                )
            )
            posting_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=interest_to_accrue,
                    denomination=denomination,
                    client_transaction_id=f"{vault.get_hook_execution_id()}_INTEREST_ACCRUAL"
                    f"_INTERNAL",
                    from_account_id=accrued_interest_receivable_account,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=interest_received_account,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": f"Daily interest accrued at {daily_interest_rate*100:0.6f}%"
                        f" on outstanding principal of {outstanding_principal}",
                        "event_type": ACCRUE_INTEREST,
                        "daily_interest_rate": f"{daily_interest_rate}",
                    },
                    asset=DEFAULT_ASSET,
                )
            )

        if expected_interest_to_accrue > 0:
            posting_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=expected_interest_to_accrue,
                    denomination=denomination,
                    client_transaction_id=f"{vault.get_hook_execution_id()}_INTEREST_ACCRUAL"
                    f"_EXPECTED",
                    from_account_id=vault.account_id,
                    from_account_address=ACCRUED_EXPECTED_INTEREST,
                    to_account_id=vault.account_id,
                    to_account_address=INTERNAL_CONTRA,
                    instruction_details={
                        "description": f"Expected daily interest accrued at"
                        f" {daily_interest_rate*100:0.6f}% on expected principal of"
                        f" {expected_principal} and outstanding principal of"
                        f" {outstanding_principal}",
                        "event_type": ACCRUE_INTEREST,
                        "daily_interest_rate": f"{daily_interest_rate}",
                    },
                    asset=DEFAULT_ASSET,
                )
            )

    return posting_instructions


def _handle_end_blocking_flags(
    vault, effective_date: datetime
) -> Tuple[Decimal, List[PostingInstruction]]:
    """
    Move capitalised interest to principal after due amount blocking flag expiry.
    :param vault: parameters, flags, balances
    :param effective_date: datetime
    :return: interest to capitalise, associated posting instructions
    """
    due_amount_blocking_flag = vault.modules["utils"].is_flag_in_list_applied(
        vault, "due_amount_blocking_flags", effective_date
    )

    if not due_amount_blocking_flag:
        return (
            _get_capitalised_interest_amount(vault),
            _get_transfer_capitalised_interest_instructions(vault, CAPITALISED_INTEREST),
        )
    return 0, []


def _get_accrue_penalty_interest_instructions(
    vault, effective_date: datetime
) -> List[PostingInstruction]:
    """
    :param vault: parameters, balances
    :param effective_date: Date for which interest is accrued
    :return: penalty interest posting instructions
    """
    if vault.modules["utils"].is_flag_in_list_applied(
        vault, "penalty_blocking_flags", effective_date
    ):
        return []
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    penalty_interest_received_account = vault.modules["utils"].get_parameter(
        vault, name="penalty_interest_received_account"
    )
    penalty = _calculate_daily_penalty(vault, effective_date)
    posting_instructions = []

    if penalty["amount_accrued"] > 0:
        posting_instructions = vault.make_internal_transfer_instructions(
            amount=penalty["amount_accrued"],
            denomination=denomination,
            client_transaction_id=vault.get_hook_execution_id() + "_ACCRUE_PENALTY_INTEREST",
            from_account_id=vault.account_id,
            from_account_address=PENALTIES,
            to_account_id=penalty_interest_received_account,
            to_account_address=DEFAULT_ADDRESS,
            instruction_details={
                "description": "Penalty interest accrual on overdue amount",
                "event": "ACCRUE_PENALTY_INTEREST",
            },
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
        )

    return posting_instructions


def _check_if_over_overpayment_allowance_and_charge_fee(vault, effective_date):
    """
    :param vault: parameters, balances(1 year)
    :param effective_date: Run date
    :return: None
    """
    overpayment_status = _get_overpayment_status(vault, effective_date)
    if overpayment_status["is_above_limit"]:
        overpayment_fee = _get_overpayment_fee(vault, overpayment_status)
        overpayment_allowance_fee_income_account = vault.modules["utils"].get_parameter(
            vault, name="overpayment_allowance_fee_income_account"
        )
        posting_ins = vault.make_internal_transfer_instructions(
            amount=overpayment_fee,
            denomination=vault.modules["utils"].get_parameter(vault, name="denomination"),
            client_transaction_id=vault.get_hook_execution_id() + "_OVERPAYMENT_fee",
            from_account_id=vault.account_id,
            from_account_address=PENALTIES,
            to_account_id=overpayment_allowance_fee_income_account,
            to_account_address=DEFAULT_ADDRESS,
            instruction_details={
                "description": f"Overpayment fee of {overpayment_fee} resulted from "
                f"excess of {overpayment_status['amount_above_limit']} "
                f"above allowance of {overpayment_status['overpayment_allowance']}.",
                "event": "CHECK_IF_OVER_OVERPAYMENT_ALLOWANCE",
            },
            asset=DEFAULT_ASSET,
        )
        vault.instruct_posting_batch(
            posting_instructions=posting_ins, effective_date=effective_date
        )


def _check_delinquency(vault, effective_date):
    """
    :param vault: balances, account id, flags
    :param effective_date: datetime
    :return: None
    """
    if vault.modules["utils"].is_flag_in_list_applied(
        vault, "delinquency_blocking_flags", effective_date
    ):
        return

    if _get_late_payment_balance(vault) > 0 and not vault.modules["utils"].is_flag_in_list_applied(
        vault, "delinquency_flags", effective_date
    ):
        vault.start_workflow(
            workflow="MORTGAGE_MARK_DELINQUENT",
            context={"account_id": str(vault.account_id)},
        )


def _process_payment(
    vault,
    effective_date,
    repayment_amount_remaining,
    client_transaction_id,
    postings,
    denomination,
):
    """
    Processes a payment received from the borrower, paying off the balance in different addresses
    in the correct order
    """
    fulfillment_precision = vault.modules["utils"].get_parameter(
        vault, name="fulfillment_precision"
    )
    accrued_interest_receivable_account = vault.modules["utils"].get_parameter(
        vault, name="accrued_interest_receivable_account"
    )
    interest_received_account = vault.modules["utils"].get_parameter(
        vault, name="interest_received_account"
    )

    repayment_amount_remaining = abs(repayment_amount_remaining)
    original_repayment_amount = repayment_amount_remaining

    repayment_instructions = []
    for debt_address in REPAYMENT_ORDER:
        debt_address_balance = _get_effective_balance_by_address(vault, debt_address)
        rounded_debt_address_balance = _round_to_precision(
            fulfillment_precision, debt_address_balance
        )
        if rounded_debt_address_balance and repayment_amount_remaining > 0:
            posting_amount = min(repayment_amount_remaining, rounded_debt_address_balance)
            posting_amount = _round_to_precision(fulfillment_precision, posting_amount)
            if posting_amount > 0:
                repayment_instructions.extend(
                    vault.make_internal_transfer_instructions(
                        amount=posting_amount,
                        denomination=denomination,
                        client_transaction_id=f"REPAY_{debt_address}_{client_transaction_id}",
                        from_account_id=vault.account_id,
                        from_account_address=DEFAULT_ADDRESS,
                        to_account_id=vault.account_id,
                        to_account_address=debt_address,
                        instruction_details={
                            "description": f"Paying off {posting_amount} from {debt_address}, "
                            f"which was at {rounded_debt_address_balance} - {effective_date}",
                            "event": "REPAYMENT",
                        },
                        asset=DEFAULT_ASSET,
                        override_all_restrictions=True,
                    )
                )
                repayment_amount_remaining -= posting_amount

    actual_outstanding_principal = _get_outstanding_actual_principal(vault)

    posting_amount = min(repayment_amount_remaining, actual_outstanding_principal)
    if posting_amount > 0:
        # We have an overpayment. Let's put it in the overpayment address
        repayment_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=posting_amount,
                denomination=denomination,
                client_transaction_id=f"OVERPAYMENT_BALANCE_{client_transaction_id}",
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=vault.account_id,
                to_account_address=OVERPAYMENT,
                instruction_details={
                    "description": f"Upon repayment, {repayment_amount_remaining}"
                    f" of the repayment has been transfered to the OVERPAYMENT balance.",
                    "event": "OVERPAYMENT_BALANCE_INCREASE",
                },
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
            )
        )
        repayment_amount_remaining -= posting_amount

    accrued_interest_balance = _get_accrued_interest(vault)
    accrued_interest_repayable = _round_to_precision(
        fulfillment_precision, accrued_interest_balance
    )
    posting_amount = min(repayment_amount_remaining, accrued_interest_repayable)
    if posting_amount > 0:
        repayment_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=posting_amount,
                denomination=denomination,
                client_transaction_id=f"OVERPAYMENT_ACCRUED_INTEREST_{client_transaction_id}_"
                "INTERNAL",
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=ACCRUED_INTEREST,
                instruction_details={
                    "description": "Repaying accrued interest balance",
                    "event": "REPAYMENT",
                },
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
            )
        )
        repayment_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=posting_amount,
                denomination=denomination,
                client_transaction_id=f"OVERPAYMENT_ACCRUED_INTEREST_{client_transaction_id}_"
                "CUSTOMER",
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=interest_received_account,
                to_account_address=DEFAULT_ADDRESS,
                instruction_details={
                    "description": "Repaying accrued interest balance",
                    "event": "REPAYMENT",
                },
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
            )
        )
        # If repayment has paid off all accrued interest after rounding to fulfillment precision,
        # clear out any remainder from rounding
        if posting_amount == accrued_interest_repayable:
            repayment_instructions.extend(
                _create_interest_remainder_posting(
                    vault,
                    ACCRUED_INTEREST,
                    accrued_interest_balance,
                    accrued_interest_repayable,
                    "REPAYMENT",
                    interest_received_account,
                    accrued_interest_receivable_account,
                    denomination,
                )
            )

    if len(repayment_instructions) > 0:
        vault.instruct_posting_batch(
            posting_instructions=repayment_instructions, effective_date=effective_date
        )

    outstanding_debt = _get_all_outstanding_debt(vault)

    # We need to do this in this way as outstanding_debt WONT include the postings made above.
    if (
        outstanding_debt - original_repayment_amount == 0
        or postings.batch_details.get("event") == "early_repayment"
    ):
        # We are done with this mortgage and should close.
        vault.start_workflow(
            workflow="MORTGAGE_CLOSURE",
            context={"account_id": str(vault.account_id)},
        )


def _handle_end_of_mortgage(vault, effective_date: datetime) -> None:
    """
    Nets off PRINCIPAL_CAPITALISED_INTEREST, OVERPAYMENT AND EMI_PRINCIPAL_EXCESS with
    PRINCIPAL to reflect actual principal while closing the account
    :param vault: parameters, balances
    :param effective_date: Datetime
    :return: None
    """
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    hook_execution_id = vault.get_hook_execution_id()
    repayment_instructions = []

    principal_capitalised_interest = _get_effective_balance_by_address(
        vault, PRINCIPAL_CAPITALISED_INTEREST
    )
    overpayment_balance = _get_effective_balance_by_address(vault, OVERPAYMENT)
    principal_excess = _get_effective_balance_by_address(vault, EMI_PRINCIPAL_EXCESS)
    emi_balance = _get_effective_balance_by_address(vault, EMI_ADDRESS)
    accrued_expected_interest_balance = _get_effective_balance_by_address(
        vault, ACCRUED_EXPECTED_INTEREST
    )

    if principal_capitalised_interest > 0:
        repayment_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(principal_capitalised_interest),
                denomination=denomination,
                client_transaction_id=f"TRANSFER_{PRINCIPAL_CAPITALISED_INTEREST}"
                f"_{hook_execution_id}",
                from_account_id=vault.account_id,
                from_account_address=PRINCIPAL_CAPITALISED_INTEREST,
                to_account_id=vault.account_id,
                to_account_address=PRINCIPAL,
                instruction_details={
                    "description": "Transferring PRINCIPAL_CAPITALISED_INTEREST "
                    "to PRINCIPAL address",
                    "event": "END_OF_MORTGAGE",
                },
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
            )
        )

    if overpayment_balance < 0:
        repayment_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(overpayment_balance),
                denomination=denomination,
                client_transaction_id=f"TRANSFER_{OVERPAYMENT}_{hook_execution_id}",
                from_account_id=vault.account_id,
                from_account_address=OVERPAYMENT,
                to_account_id=vault.account_id,
                to_account_address=PRINCIPAL,
                instruction_details={
                    "description": "Transferring overpayments to PRINCIPAL address",
                    "event": "END_OF_MORTGAGE",
                },
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
            )
        )

    if principal_excess < 0:
        repayment_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(principal_excess),
                denomination=denomination,
                client_transaction_id=f"TRANSFER_{EMI_PRINCIPAL_EXCESS}_{hook_execution_id}",
                from_account_id=vault.account_id,
                from_account_address=EMI_PRINCIPAL_EXCESS,
                to_account_id=vault.account_id,
                to_account_address=PRINCIPAL,
                instruction_details={
                    "description": "Transferring principal excess to PRINCIPAL address",
                    "event": "END_OF_MORTGAGE",
                },
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
            )
        )

    if emi_balance > 0:
        repayment_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=emi_balance,
                denomination=denomination,
                client_transaction_id=f"CLEAR_EMI_{hook_execution_id}",
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=EMI_ADDRESS,
                instruction_details={
                    "description": "Clearing EMI address balance",
                    "event": "END_OF_MORTGAGE",
                },
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
            )
        )

    if accrued_expected_interest_balance > 0:
        repayment_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=accrued_expected_interest_balance,
                denomination=denomination,
                client_transaction_id=f"CLEAR_ACCRUED_EXPECTED_INTEREST_{hook_execution_id}",
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=ACCRUED_EXPECTED_INTEREST,
                instruction_details={
                    "description": "Clearing accrued expected interest balance",
                    "event": "END_OF_MORTGAGE",
                },
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
            )
        )

    if len(repayment_instructions) > 0:
        vault.instruct_posting_batch(
            posting_instructions=repayment_instructions, effective_date=effective_date
        )


# Calculation helper functions
def _calculate_monthly_due_amounts(vault, effective_date: datetime) -> Dict[str, Decimal]:
    """
    :param vault: parameters, balances, get_last_execution_time()
    :param effective_date: datetime of hook execution
    :return: a dictionary containing monthly due amounts
    """
    annual_interest_rate = _get_interest_rate(vault, effective_date)

    is_interest_only_repayment = _is_within_term(vault, effective_date, "interest_only_term")

    return (
        _calculate_interest_only_repayment(vault, effective_date)
        if is_interest_only_repayment
        else _calculate_monthly_payment_interest_and_principal(
            vault, effective_date, annual_interest_rate
        )
    )


def _calculate_interest_only_repayment(vault, effective_date: datetime) -> Dict[str, Decimal]:

    fulfillment_precision = int(
        vault.modules["utils"].get_parameter(vault, name="fulfillment_precision")
    )
    remaining_principal = _get_outstanding_actual_principal(vault)
    monthly_expected_interest_accrued = _get_effective_balance_by_address(
        vault, ACCRUED_EXPECTED_INTEREST
    )
    monthly_interest_accrued = _get_accrued_interest(vault)

    interest_only_amortisation_input = vault.modules[
        "amortisation"
    ].construct_interest_only_amortisation_input(
        remaining_principal,
        monthly_interest_accrued,
        monthly_expected_interest_accrued,
        fulfillment_precision,
        _is_last_payment_date(vault, effective_date),
    )

    monthly_due = vault.modules["amortisation"].calculate_interest_only_repayment(
        interest_only_amortisation_input
    )

    return {
        "emi": monthly_due["emi"],
        "interest": monthly_due["interest_due"],
        "accrued_interest": monthly_due["accrued_interest"],
        "accrued_expected_interest": monthly_due["accrued_interest_excluding_overpayment"],
        "principal": monthly_due["principal_due_excluding_overpayment"],
        "principal_excess": monthly_due["principal_excess"],
    }


def _get_capitalised_interest_amount(vault) -> Decimal:
    fulfillment_precision = vault.modules["utils"].get_parameter(vault, "fulfillment_precision")
    accrued_capitalised_interest = _get_effective_balance_by_address(vault, CAPITALISED_INTEREST)
    principal_capitalised_interest = _round_to_precision(
        fulfillment_precision, accrued_capitalised_interest
    )

    return principal_capitalised_interest


def _get_transfer_capitalised_interest_instructions(
    vault, capitalised_interest_address: str
) -> List[PostingInstruction]:
    """
    Transfer accrued interest to principal capitalised interest balance.
    """
    denomination = vault.modules["utils"].get_parameter(vault, "denomination")
    fulfillment_precision = vault.modules["utils"].get_parameter(vault, "fulfillment_precision")
    event_type = f"TRANSFER_{capitalised_interest_address}_TO_{PRINCIPAL_CAPITALISED_INTEREST}"
    accrued_capitalised_interest = _get_effective_balance_by_address(
        vault, capitalised_interest_address
    )
    principal_capitalised_interest = _round_to_precision(
        fulfillment_precision, accrued_capitalised_interest
    )
    instructions = (
        vault.make_internal_transfer_instructions(
            amount=principal_capitalised_interest,
            denomination=denomination,
            client_transaction_id=f"{vault.get_hook_execution_id()}_TRANSFER_ACCRUED"
            f"_{capitalised_interest_address}_CUSTOMER",
            from_account_id=vault.account_id,
            from_account_address=PRINCIPAL_CAPITALISED_INTEREST,
            to_account_id=vault.account_id,
            to_account_address=capitalised_interest_address,
            instruction_details={
                "description": "Capitalise interest accrued after due amount blocking",
                "event": event_type,
            },
            asset=DEFAULT_ASSET,
        )
        if principal_capitalised_interest > 0
        else []
    )
    return instructions


def _get_due_postings(vault, effective_date: datetime) -> List[PostingInstruction]:
    """
    Generate posting instructions for moving due principal and due interest.
    """
    if vault.modules["utils"].is_flag_in_list_applied(
        vault, "due_amount_blocking_flags", effective_date
    ):
        return []

    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    accrued_interest_receivable_account = vault.modules["utils"].get_parameter(
        vault, name="accrued_interest_receivable_account"
    )
    interest_received_account = vault.modules["utils"].get_parameter(
        vault, name="interest_received_account"
    )

    monthly_due_amounts = _calculate_monthly_due_amounts(vault, effective_date)

    emi = monthly_due_amounts["emi"]
    principal_due = monthly_due_amounts["principal"]
    interest_due = monthly_due_amounts["interest"]
    accrued_interest = monthly_due_amounts["accrued_interest"]
    accrued_expected_interest = monthly_due_amounts["accrued_expected_interest"]
    principal_excess = monthly_due_amounts["principal_excess"]
    stored_emi = _get_effective_balance_by_address(vault, EMI_ADDRESS)

    event_type = "CALCULATE_AND_TRANSFER_DUE_AMOUNT"

    posting_instructions = []
    if emi > 0 and emi != stored_emi:
        if stored_emi > 0:
            posting_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=stored_emi,
                    denomination=denomination,
                    client_transaction_id=f"{vault.get_hook_execution_id()}_CLEAR_STORED_EMI",
                    from_account_id=vault.account_id,
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id=vault.account_id,
                    to_account_address=EMI_ADDRESS,
                    instruction_details={
                        "description": "Clearing stored EMI amount",
                        "event": event_type,
                    },
                    asset=DEFAULT_ASSET,
                )
            )
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=emi,
                denomination=denomination,
                client_transaction_id=f"{vault.get_hook_execution_id()}_UPDATE_STORED_EMI",
                from_account_id=vault.account_id,
                from_account_address=EMI_ADDRESS,
                to_account_id=vault.account_id,
                to_account_address=INTERNAL_CONTRA,
                instruction_details={
                    "description": "Updating stored EMI amount",
                    "event": event_type,
                },
                asset=DEFAULT_ASSET,
            )
        )

    if principal_due > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=principal_due,
                denomination=denomination,
                client_transaction_id=vault.get_hook_execution_id()
                + "_PAYMENT_PERIOD_PRINCIPAL_DUE",
                from_account_id=vault.account_id,
                from_account_address=PRINCIPAL_DUE,
                to_account_id=vault.account_id,
                to_account_address=PRINCIPAL,
                instruction_details={
                    "description": f"Monthly principal added to due address: {principal_due}",
                    "event": event_type,
                },
                asset=DEFAULT_ASSET,
            )
        )

    if principal_excess > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=principal_excess,
                denomination=denomination,
                client_transaction_id=vault.get_hook_execution_id()
                + "_PAYMENT_PERIOD_EMI_PRINCIPAL_EXCESS",
                from_account_id=vault.account_id,
                from_account_address=PRINCIPAL_DUE,
                to_account_id=vault.account_id,
                to_account_address=EMI_PRINCIPAL_EXCESS,
                instruction_details={
                    "description": f"Monthly principal excess added to "
                    f"excess address: {principal_excess}",
                    "event": event_type,
                },
                asset=DEFAULT_ASSET,
            )
        )

    if interest_due > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=interest_due,
                denomination=denomination,
                client_transaction_id=vault.get_hook_execution_id()
                + "_APPLY_ACCRUED_INTEREST_CUSTOMER",
                from_account_id=vault.account_id,
                from_account_address=INTEREST_DUE,
                to_account_id=interest_received_account,
                to_account_address=DEFAULT_ADDRESS,
                instruction_details={
                    "description": f"Monthly interest added to due address: {interest_due}",
                    "event": event_type,
                },
                asset=DEFAULT_ASSET,
            )
        )
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=interest_due,
                denomination=denomination,
                client_transaction_id=f"{vault.get_hook_execution_id()}_APPLY_ACCRUED_INTEREST"
                "_INTERNAL",
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=ACCRUED_INTEREST,
                instruction_details={
                    "description": f"Monthly interest added to due address: {interest_due}",
                    "event": event_type,
                },
                asset=DEFAULT_ASSET,
            )
        )

    posting_instructions.extend(
        _create_interest_remainder_posting(
            vault,
            ACCRUED_INTEREST,
            accrued_interest,
            interest_due,
            event_type,
            interest_received_account,
            accrued_interest_receivable_account,
            denomination,
        )
    )

    if accrued_expected_interest > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(accrued_expected_interest),
                denomination=denomination,
                client_transaction_id=f"{vault.get_hook_execution_id()}_APPLY_ACCRUED_EXPECTED"
                f"_INTEREST",
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=ACCRUED_EXPECTED_INTEREST,
                instruction_details={
                    "description": "Monthly interest excess added to principal excess",
                    "event": event_type,
                },
                asset=DEFAULT_ASSET,
            )
        )

    return posting_instructions


def _create_interest_remainder_posting(
    vault,
    interest_address,
    actual_balance,
    rounded_balance,
    event_type,
    interest_received_account,
    accrued_interest_receivable_account,
    denomination,
    include_address_in_client_transaction_id=False,
):
    """
    Creates and returns posting instructions for handling remainder on INTEREST address due to
    any difference in accrual and fulfilment precision.
    If positive, interest was rounded down and exra interest was charged to customer.
    If negative, interest was rounded up and extra interest was returned to customer.

    :param vault: Vault object
    :param interest_address: str, interest address on which to handle remainder
    :param actual_balance: Decimal, interest balance amount prior to application
    :param rounded_balance: Decimal, rounded interest amount that was applied
    :param event_type: str, event which triggered the interest application
    :param interest_received_account: str, Vault AccountID for bank's internal interest received
    account
    :param accrued_interest_receivable_account: str, Vault AccountID for bank's internal accrued
    interest receivable account
    :param denomination: str, denomination used for account
    :param include_address_in_client_transaction_id: bool, if True then we include the address
    when constructing the client transaction id, to ensure uniqueness.
    :return: list of posting instructions to handle interest remainder
    """
    hook_execution_id = vault.get_hook_execution_id()
    interest_remainder = actual_balance - rounded_balance
    interest_remainder_postings = []
    if include_address_in_client_transaction_id:
        client_transaction_id = (
            f"{event_type}_{interest_address}_REMAINDER_" f"{hook_execution_id}_{denomination}"
        )
    else:
        client_transaction_id = f"{event_type}_REMAINDER_{hook_execution_id}_{denomination}"
    if interest_remainder < 0:
        interest_remainder_postings.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(interest_remainder),
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=interest_address,
                to_account_id=vault.account_id,
                to_account_address=INTERNAL_CONTRA,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"{client_transaction_id}_CUSTOMER",
                instruction_details={
                    "description": f"Extra interest charged to customer from negative remainder"
                    f" due to repayable amount for {interest_address} rounded up",
                    "event_type": event_type,
                },
            )
        )
        interest_remainder_postings.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(interest_remainder),
                denomination=denomination,
                from_account_id=accrued_interest_receivable_account,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=interest_received_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"{client_transaction_id}_INTERNAL",
                instruction_details={
                    "description": f"Extra interest charged to account {vault.account_id}"
                    f" from negative remainder"
                    f" due to repayable amount for {interest_address} rounded up",
                    "event_type": event_type,
                },
            )
        )
    elif interest_remainder > 0:
        interest_remainder_postings.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(interest_remainder),
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=interest_address,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"{client_transaction_id}_CUSTOMER",
                instruction_details={
                    "description": f"Extra interest returned to customer from positive remainder"
                    f" due to repayable amount for {interest_address} rounded down",
                    "event_type": event_type,
                },
            )
        )
        interest_remainder_postings.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(interest_remainder),
                denomination=denomination,
                from_account_id=interest_received_account,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=accrued_interest_receivable_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"{client_transaction_id}_INTERNAL",
                instruction_details={
                    "description": f"Extra interest returned to account {vault.account_id}"
                    f" from positive remainder"
                    f" due to repayable amount for {interest_address} rounded down",
                    "event_type": event_type,
                },
            )
        )

    return interest_remainder_postings


# Posting retrieval helper functions
def _get_interest_waiver_posting(vault):
    monthly_interest_to_revert = _get_effective_balance_by_address(vault, INTEREST_DUE)
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")
    interest_received_account = vault.modules["utils"].get_parameter(
        vault, name="interest_received_account"
    )
    return (
        vault.make_internal_transfer_instructions(
            amount=monthly_interest_to_revert,
            denomination=denomination,
            client_transaction_id=vault.get_hook_execution_id() + "WAIVE_MONTLY_INTEREST_DUE",
            from_account_id=interest_received_account,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=vault.account_id,
            to_account_address=INTEREST_DUE,
            instruction_details={
                "description": f"Waive monthly interest due: {monthly_interest_to_revert}",
                "event": "EARLY_REPAYMENT_INTEREST_ADJUSTMENT",
            },
            asset=DEFAULT_ASSET,
        )
        if monthly_interest_to_revert > 0
        else []
    )


def _get_late_repayment_fee_posting(vault):
    fee_amount = vault.modules["utils"].get_parameter(vault, name="late_repayment_fee")
    late_repayment_fee_income_account = vault.modules["utils"].get_parameter(
        vault, name="late_repayment_fee_income_account"
    )
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")

    if fee_amount == 0:
        return []

    return vault.make_internal_transfer_instructions(
        amount=fee_amount,
        denomination=denomination,
        client_transaction_id=vault.get_hook_execution_id() + "_CHARGE_FEE",
        from_account_id=vault.account_id,
        from_account_address=PENALTIES,
        to_account_id=late_repayment_fee_income_account,
        to_account_address=DEFAULT_ADDRESS,
        instruction_details={
            "description": f"Incur late repayment fees of {fee_amount}",
            "event": "INCUR_PENALTY_FEES",
        },
        asset=DEFAULT_ASSET,
    )


def _get_overdue_postings(
    vault, effective_date: datetime, due_address: str, overdue_address: str
) -> List[PostingInstruction]:
    """
    Transfer the outstanding balance from DUE_ADDRESS to OVERDUE_ADDRESS.
    """
    if vault.modules["utils"].is_flag_in_list_applied(
        vault, "overdue_amount_blocking_flags", effective_date
    ):
        return []

    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")

    due_amount = _get_effective_balance_by_address(vault, due_address)
    overdue_posting = (
        vault.make_internal_transfer_instructions(
            amount=due_amount,
            denomination=denomination,
            client_transaction_id=vault.get_hook_execution_id() + "_" + overdue_address,
            from_account_id=vault.account_id,
            from_account_address=overdue_address,
            to_account_id=vault.account_id,
            to_account_address=due_address,
            instruction_details={
                "description": f"Mark oustanding due amount of "
                f"{due_amount} as {overdue_address}.",
                "event": "MOVE_BALANCE_INTO_" + overdue_address,
            },
            asset=DEFAULT_ASSET,
        )
        if due_amount > 0
        else []
    )

    return overdue_posting


# Interest rate helper functions
def _get_interest_rate(vault, effective_date):
    is_fixed_interest = _is_within_term(vault, effective_date, "fixed_interest_term")
    interest_rate_type = "fixed_interest_rate" if is_fixed_interest else "variable_interest_rate"
    annual_interest_rate = vault.modules["utils"].get_parameter(vault, name=interest_rate_type)
    if not is_fixed_interest:
        variable_rate_adjustment = vault.modules["utils"].get_parameter(
            vault, name="variable_rate_adjustment"
        )
        annual_interest_rate += variable_rate_adjustment
    return {
        "interest_rate_type": interest_rate_type,
        "interest_rate": annual_interest_rate,
    }


def _round_to_precision(precision, amount):
    """
    Round a decimal value to required precision

    :param precision: Decimal, number of decimal places to round to
    :param amount: Decimal, amount to round
    :return: Decimal, Rounded amount
    """
    decimal_string = str(1.0 / pow(10, precision))
    return amount.quantize(Decimal(decimal_string).normalize(), rounding=ROUND_HALF_UP)


def _interest_rate_precision(amount):
    return amount.quantize(Decimal(".0000000001"), rounding=ROUND_HALF_UP)


def _get_monthly_interest_rate(annual_interest_rate):
    """
    :param annual_interest_rate: Dict[str, Union[str, Decimal]]
    :return: Decimal
    """
    return _interest_rate_precision(annual_interest_rate["interest_rate"] / MONTHS_IN_A_YEAR)


def _get_daily_interest_rate(annual_interest_rate):
    """
    :param annual_interest_rate: Dict[str, Union[str, Decimal]]
    :return: Decimal
    """
    return _interest_rate_precision(annual_interest_rate["interest_rate"] / DAYS_IN_A_YEAR)


def _get_penalty_daily_rate(vault, effective_date):
    """
    :param vault: parameters
    :param effective_date: Run date
    :return: Decimal
    """
    penalty_interest_rate = vault.modules["utils"].get_parameter(
        vault, name="penalty_interest_rate"
    )
    base_rate = _get_interest_rate(vault, effective_date)["interest_rate"]

    if vault.modules["utils"].get_parameter(
        vault, name="penalty_includes_base_rate", union=True, is_boolean=True
    ):
        penalty_interest_rate += base_rate

    return _interest_rate_precision(penalty_interest_rate / DAYS_IN_A_YEAR)


# Time calculation helper functions
def _calculate_next_repayment_date(vault, effective_date):
    """
    :param vault: Vault object
    :param effective_date: datetime
    :return: datetime
    """
    mortgage_start_date = vault.modules["utils"].get_parameter(vault, name="mortgage_start_date")
    repayment_day = vault.modules["utils"].get_parameter(vault, name="repayment_day")
    last_execution_time = vault.get_last_execution_time(event_type=REPAYMENT_DAY_SCHEDULE)
    repayment_hour = vault.modules["utils"].get_parameter(vault, "repayment_hour")
    repayment_minute = vault.modules["utils"].get_parameter(vault, "repayment_minute")
    repayment_second = vault.modules["utils"].get_parameter(vault, "repayment_second")
    earliest_event_start_date = mortgage_start_date + timedelta(months=1)
    if last_execution_time and mortgage_start_date < last_execution_time <= effective_date:
        # The earliest time repayment event can run from effective_date
        earliest_event_start_date = last_execution_time + timedelta(months=1)

    next_payment_date = effective_date + timedelta(
        day=repayment_day,
        hour=repayment_hour,
        minute=repayment_minute,
        second=repayment_second,
        microsecond=0,
    )
    if next_payment_date <= effective_date:
        next_payment_date += timedelta(months=1)
    if effective_date < earliest_event_start_date:
        next_payment_date = earliest_event_start_date + timedelta(
            day=repayment_day,
            hour=repayment_hour,
            minute=repayment_minute,
            second=repayment_second,
            microsecond=0,
        )
        if next_payment_date < earliest_event_start_date:
            next_payment_date += timedelta(months=1)

    return next_payment_date


def _is_within_term(vault, effective_date: datetime, term_name: str) -> bool:
    return _get_expected_remaining_term(vault, effective_date, term_name) > 0


def _get_remaining_term_in_months(vault, effective_date: datetime, term_name: str) -> int:
    """
    Returns the remaining loan term in months, taking into account past over-payments.
    Since we are using remaining principal, the cutoff point for months is at transfer due.
    This is essentially a forecast given the current account state and so does
    not consider future late repayments or over-payments. Fees are assumed to be settled before
    the end of the loan and are not influential. It is assumed that there can be a due balance
    remaining at the end of the loan.

    :param vault: Vault object
    :param effective_date: date from which calculation is made
    :param term_name: name of the term i.e. total_term
    :return: number of months
    """
    calculated_remaining_term = _get_calculated_remaining_term(vault, effective_date)
    expected_remaining_term = _get_expected_remaining_term(vault, effective_date, term_name)
    return min(calculated_remaining_term, expected_remaining_term)


def _get_expected_remaining_term(vault, effective_date: datetime, term_name: str) -> int:
    """
    The remaining term according to the natural end date of the loan.

    :param vault: Vault object
    :param effective_date: date from which calculation is made
    :param term_name: name of the term i.e. total_term
    :return: number of months
    """
    term = vault.modules["utils"].get_parameter(vault, name=term_name)
    mortgage_start_date = vault.modules["utils"].get_parameter(vault, name="mortgage_start_date")
    first_repayment_date = _calculate_next_repayment_date(vault, mortgage_start_date)

    if effective_date < first_repayment_date:
        remaining_term = timedelta(months=term)
    else:
        remaining_term = timedelta(first_repayment_date.date(), effective_date.date()) + timedelta(
            months=term
        )
    if effective_date + remaining_term < effective_date + timedelta(months=1):
        return 0
    else:
        # negative days should reduce term by up to 1 month
        rounded_month = -1 if remaining_term.days < 0 else 0
        return remaining_term.years * 12 + remaining_term.months + rounded_month


def _get_calculated_remaining_term(vault, effective_date: datetime) -> int:
    """
    The remaining term calculated using the amortisation formula.

    Formula for EMI and Remaining Term calculation:
    EMI = [P x R x (1+R)^N]/[(1+R)^N-1]
    N = math.log((EMI/(EMI - P*R)), (1+R))
    P is Remaining Principal
    R is Monthly Rate
    N is Remaining Term

    :param vault: Vault object
    :param effective_date: date from which calculation is made
    :return: number of months
    """
    mortgage_start_date = vault.modules["utils"].get_parameter(vault, name="mortgage_start_date")
    total_term = vault.modules["utils"].get_parameter(vault, name="total_term")

    principal_balance = _get_outstanding_actual_principal(vault)
    overpayment_balance = vault.modules["utils"].get_balance_sum(vault, [OVERPAYMENT])
    term_precision = 2 if overpayment_balance else 0

    # Check if mortgage has not yet disbursed at start of mortgage
    if principal_balance <= 0:
        if effective_date + timedelta(
            hour=0, minute=0, second=0, microsecond=0
        ) <= mortgage_start_date + timedelta(hour=0, minute=0, second=0, microsecond=0):
            return total_term
        else:
            return 0

    emi = _get_effective_balance_by_address(vault, EMI_ADDRESS)
    if emi:
        annual_interest_rate = _get_interest_rate(vault, effective_date)
        monthly_rate = _get_monthly_interest_rate(annual_interest_rate)

        remaining_term = _round_to_precision(
            term_precision,
            Decimal(math.log((emi / (emi - principal_balance * monthly_rate)), (1 + monthly_rate))),
        )

        return math.ceil(remaining_term)
    else:
        return total_term


def _is_last_payment_date(vault, effective_date):
    return _get_expected_remaining_term(vault, effective_date, "total_term") == 1


# Amortisation calculation helper functions
def _calculate_monthly_payment_interest_and_principal(
    vault,
    effective_date: datetime,
    annual_interest_rate: Dict[str, Union[str, Decimal]],
) -> Dict[str, Decimal]:
    """
    Fixed interest rate period:
        in order to keep EMI (Equated Monthly Installment) constant
    even from floating by 0.01 due to rounding, it always uses the originally
    agreed Principal and Repayment Term.

    Variable rate period:
        1. EMI is calculated monthly using the latest rate value
        2. Overpayment changes the remaining principal
        3. As a result of point 2, principal and interest propotions of the EMI are also changed
        4. In order to exclude the overpayment effect on total EMI value, all impact on principal
        consequent to overpayments are kept in separate addresses
            a) actual overpayment amount in OVERPAYMENT
            b) difference in principal proportion of the EMI in EMI_PRINCIPAL_EXCESS
        5. This allows PRINCIPAL address to always have the expected principal amount as if there
        has never been any overpayment, and hence total EMI every month will not
        be affected by overpayment -- only interest rate value changes impact the total EMI value

    EMI = [P x R x (1+R)^N]/[(1+R)^N-1]

    P is principal remaining
    R is the Monthly Rate
    N is term remaining

    P_actual is the actual remaining principal from balances (including overpayment)
    P_expected is the expected remaining principal (excluding overpayment)
    P_original is the original principal stored in principal param

    N_original is the total repayment term as specified by params total_term - interest_only term
    N_expected is the expected remaining term without overpayment

    :param vault: balances
    :param effective_date: effective date time
    :param annual_interest_rate: annual interest rate
    :return: calculated values for emi, interest and principal
    """
    mortgage_start_date = vault.modules["utils"].get_parameter(vault, name="mortgage_start_date")
    fulfillment_precision = vault.modules["utils"].get_parameter(
        vault, name="fulfillment_precision"
    )
    last_repayment_day_schedule_event = vault.get_last_execution_time(
        event_type=REPAYMENT_DAY_SCHEDULE
    )
    last_variable_rate_adjustment_change_date = vault.get_parameter_timeseries(
        name="variable_rate_adjustment"
    )[-1][0]
    last_variable_interest_rate_change_date = vault.get_parameter_timeseries(
        name="variable_interest_rate"
    )[-1][0]
    last_rate_change_date = max(
        mortgage_start_date,
        last_variable_rate_adjustment_change_date,
        last_variable_interest_rate_change_date,
    )
    previous_due_amount_blocked = vault.modules["utils"].is_flag_in_list_applied(
        vault,
        "due_amount_blocking_flags",
        last_repayment_day_schedule_event,
    )
    N = _get_expected_remaining_term(vault, effective_date, "total_term")

    P_actual = _get_outstanding_actual_principal(vault)
    P_expected = _get_expected_principal(vault)

    R = _get_monthly_interest_rate(annual_interest_rate)

    overpayment_impact_preference = vault.modules["utils"].get_parameter(
        vault, "overpayment_impact_preference", union=True
    )

    emi = _get_effective_balance_by_address(vault, EMI_ADDRESS)

    P = (
        P_actual
        if (
            overpayment_impact_preference.upper() == "REDUCE_EMI"
            and _get_effective_balance_by_address(vault, OVERPAYMENT) != 0
        )
        else P_expected
    )

    rate_changed_since_last_repayment_day = (
        last_repayment_day_schedule_event is None
        or last_rate_change_date > last_repayment_day_schedule_event
        or (
            _is_within_term(vault, last_repayment_day_schedule_event, "fixed_interest_term")
            and not _is_within_term(vault, effective_date, "fixed_interest_term")
        )
        or (
            _is_within_term(vault, last_repayment_day_schedule_event, "interest_only_term")
            and not _is_within_term(vault, effective_date, "interest_only_term")
        )
    )

    emi = _get_effective_balance_by_address(vault, EMI_ADDRESS)
    principal_excess = Decimal(0)
    expected_interest = Decimal(0)
    interest_accrued = _get_accrued_interest(vault)
    accrued_expected_interest = _get_effective_balance_by_address(vault, ACCRUED_EXPECTED_INTEREST)
    interest_due = _round_to_precision(fulfillment_precision, interest_accrued)

    if N <= 0:
        principal_due = P_actual
        emi = principal_due
    elif annual_interest_rate["interest_rate"] == 0:
        principal_due = _round_to_precision(fulfillment_precision, P_actual / N)
        emi = principal_due
    else:
        # EMI will be recalculated in two cases:
        # 1. Variable interest rate has changed since last repayment day. EMI is recalculated
        #    using the new interest rate.
        # 2. Due amount blocking flag was applied until last repayment day. EMI is recalculated
        #    based on new PRINCIPAL + PRINCIPAL_CAPITALISED_INTEREST.
        if (
            emi == 0
            or (
                annual_interest_rate["interest_rate_type"] == "variable_interest_rate"
                and rate_changed_since_last_repayment_day
            )
            or (
                overpayment_impact_preference.upper() == "REDUCE_EMI"
                and _has_new_overpayment(vault)
            )
            or previous_due_amount_blocked
        ):
            emi = _round_to_precision(
                fulfillment_precision, P * R * ((1 + R) ** N) / ((1 + R) ** N - 1)
            )

        additional_interest = _round_to_precision(
            fulfillment_precision, _get_additional_interest(vault, effective_date)
        )

        expected_interest = _round_to_precision(fulfillment_precision, accrued_expected_interest)
        principal_due = emi - (expected_interest - additional_interest)
        principal_excess = expected_interest - interest_due
        if _is_last_payment_date(vault, effective_date) or principal_due > P_actual:
            principal_due = P_actual
            principal_excess = Decimal("0.00")

    return {
        "emi": emi,
        "interest": interest_due,
        "accrued_interest": interest_accrued,
        "accrued_expected_interest": accrued_expected_interest,
        "principal": principal_due,
        "principal_excess": principal_excess,
    }


def _calculate_daily_penalty(vault, effective_date):
    """
    :param vault: parameters, balances
    :param effective_date: Date for which interest is accrued
    :return: Decimal
    """
    fulfillment_precision = vault.modules["utils"].get_parameter(
        vault, name="fulfillment_precision"
    )
    overdue_balance = _get_overdue_balance(vault)
    daily_penalty_rate = _get_penalty_daily_rate(vault, effective_date)
    return {
        "amount_accrued": _round_to_precision(
            fulfillment_precision, overdue_balance * daily_penalty_rate
        ),
        "amount_overdue": overdue_balance,
        "penalty_interest_rate": daily_penalty_rate,
    }


# Overpayment helper functions
def _get_overpayment_status(vault, effective_date):
    """
    :param vault: parameters, balances (1 year)
    :param effective_date: current datetime when running overpayment limit check
    :return: Dict[str, Any]
    """
    mortgage_start_date = vault.modules["utils"].get_parameter(vault, name="mortgage_start_date")
    fulfillment_precision = vault.modules["utils"].get_parameter(
        vault, name="fulfillment_precision"
    )
    # This is the first check. We are slightly less than a year as the account wasn't opened
    # at midnight
    one_year_ago = max(effective_date + timedelta(years=-1), mortgage_start_date)
    overpayment_percentage = vault.modules["utils"].get_parameter(
        vault, name="overpayment_percentage", at=one_year_ago
    )

    last_period_overpayment_balance = _get_effective_balance_by_address(
        vault, OVERPAYMENT, one_year_ago
    )
    last_period_principal_balance = _get_effective_balance_by_address(
        vault, PRINCIPAL, one_year_ago
    )
    current_overpayment_balance = _get_effective_balance_by_address(vault, OVERPAYMENT)

    overpayment_allowance = last_period_principal_balance * overpayment_percentage
    overpaid_within_period = abs(current_overpayment_balance - last_period_overpayment_balance)

    return {
        "overpayment_allowance": _round_to_precision(fulfillment_precision, overpayment_allowance),
        "overpaid_within_period": overpaid_within_period,
        "amount_above_limit": overpaid_within_period - overpayment_allowance,
        "is_above_limit": overpaid_within_period > overpayment_allowance,
    }


def _get_overpayment_fee(vault, overpayment_status):
    """
    :param vault: parameters
    :param overpayment_status: Dict[str, Any]
    :return: Decimal
    """
    overpayment_fee_percentage = vault.modules["utils"].get_parameter(
        vault, name="overpayment_fee_percentage"
    )
    fulfillment_precision = vault.modules["utils"].get_parameter(
        vault, name="fulfillment_precision"
    )
    return _round_to_precision(
        fulfillment_precision,
        overpayment_status["amount_above_limit"] * overpayment_fee_percentage,
    )


# Schedule helper functions
def _schedule_delinquency_check(vault, effective_date):
    """
    :param vault: balances, account id, flags
    :param effective_date: datetime of when overdue occurs
    :return: None
    """
    grace_period = vault.modules["utils"].get_parameter(vault, name="grace_period")
    if grace_period == 0:
        _check_delinquency(vault, effective_date)
    else:
        grace_period_end = effective_date + timedelta(days=int(grace_period))
        vault.amend_schedule(
            event_type=CHECK_DELINQUENCY,
            new_schedule={
                "month": str(grace_period_end.month),
                "day": str(grace_period_end.day),
                "hour": str(vault.modules["utils"].get_parameter(vault, "check_delinquency_hour")),
                "minute": str(
                    vault.modules["utils"].get_parameter(vault, "check_delinquency_minute")
                ),
                "second": str(
                    vault.modules["utils"].get_parameter(vault, "check_delinquency_second")
                ),
                "year": str(grace_period_end.year),
            },
        )


def _handle_repayment_day_change(
    vault, previous_values: str, updated_values: str, effective_date: datetime
) -> None:

    if vault.modules["utils"].has_parameter_value_changed(
        "repayment_day",
        previous_values,
        updated_values,
    ):
        updated_repayment_day = updated_values.get("repayment_day")

        next_repayment_day = _calculate_next_repayment_date(vault, effective_date)

        _schedule_repayment_day_change(vault, updated_repayment_day, next_repayment_day)


def _handle_product_switching(
    vault, updated_values: Dict[str, Any], effective_date: datetime
) -> None:
    """
    Consolidates balances in principal tracking addresses at the end of previous
    mortgage/start of new mortgage
    Reschedules annual overpayment allowance check anchoring on new mortgage
    start date
    """
    if "mortgage_start_date" in updated_values:
        overpayment_schedule = _get_handle_overpayment_allowance_schedule(vault)
        vault.amend_schedule(
            event_type=HANDLE_OVERPAYMENT_ALLOWANCE, new_schedule=overpayment_schedule
        )
        # currently, the contract can only set the date when switch mortgage wf is run
        # as the new mortgage start date, therefore using effective_date is
        # equivalent as the new mortgage_start_date
        # in the future, should the two diverge, this should be revisited so that correct
        # date and time components are used for end of life postings
        _handle_end_of_mortgage(vault, effective_date)


def _schedule_repayment_day_change(vault, repayment_day, effective_date):
    """
    :param vault: amend_schedule(), parameters
    :param repayment_day: int
    :param effective_date: datetime
    :return: None
    """
    if _has_schedule_run_today(vault, effective_date, REPAYMENT_DAY_SCHEDULE):
        effective_date += timedelta(days=1)
    vault.amend_schedule(
        event_type=REPAYMENT_DAY_SCHEDULE,
        new_schedule={
            "day": str(repayment_day),
            "hour": str(vault.modules["utils"].get_parameter(vault, "repayment_hour")),
            "minute": str(vault.modules["utils"].get_parameter(vault, "repayment_minute")),
            "second": str(vault.modules["utils"].get_parameter(vault, "repayment_second")),
            "start_date": str(effective_date.date()),
        },
    )


def _get_handle_repayment_day_schedule(vault, repayment_day: int) -> Dict[str, str]:
    """
    :param vault: Vault object
    :param repayment_day: the day of every month on which a repayment should be made
    :return: repayment day schedule specifying the day of the month, the hour,
    the minute, and the second of the expected mortgage repayments, and the date on which the
    schedule starts.
    """
    mortgage_start_date = vault.get_parameter_timeseries(name="mortgage_start_date").latest().date()
    mortgage_start_date_plus_one_month = mortgage_start_date + timedelta(months=1)
    return {
        "day": str(repayment_day),
        "hour": str(vault.modules["utils"].get_parameter(vault, "repayment_hour")),
        "minute": str(vault.modules["utils"].get_parameter(vault, "repayment_minute")),
        "second": str(vault.modules["utils"].get_parameter(vault, "repayment_second")),
        "start_date": str(mortgage_start_date_plus_one_month),
    }


def _get_handle_overpayment_allowance_schedule(vault) -> Dict[str, str]:
    """
    :param vault: Vault object
    :return: overpayment allowance schedule as a dictionary
    """
    mortgage_start_date = vault.get_parameter_timeseries(name="mortgage_start_date").latest().date()
    mortgage_start_date_plus_day = mortgage_start_date + timedelta(days=1)
    return {
        "month": str(mortgage_start_date.month),
        "day": str(mortgage_start_date.day),
        "hour": str(vault.modules["utils"].get_parameter(vault, "overpayment_hour")),
        "minute": str(vault.modules["utils"].get_parameter(vault, "overpayment_minute")),
        "second": str(vault.modules["utils"].get_parameter(vault, "overpayment_second")),
        "start_date": str(mortgage_start_date_plus_day),
    }


# Balance helper functions
def _get_effective_balance_by_address(vault, address, timestamp=None):
    """
    :param vault: balances, parameters
    :param address: str
    :param timestamp: datetime
    :return: Decimal
    """
    return vault.modules["utils"].get_balance_sum(vault, [address], timestamp)


def _has_new_overpayment(vault) -> bool:
    mortgage_start_date = vault.modules["utils"].get_parameter(vault, name="mortgage_start_date")
    last_repayment_day_schedule_event = vault.get_last_execution_time(
        event_type=REPAYMENT_DAY_SCHEDULE
    )
    previous_date = (
        last_repayment_day_schedule_event
        if last_repayment_day_schedule_event
        else mortgage_start_date
    )
    previous_overpayments = _get_effective_balance_by_address(vault, OVERPAYMENT, previous_date)
    current_overpayments = _get_effective_balance_by_address(vault, OVERPAYMENT)
    return current_overpayments != previous_overpayments


def _get_additional_interest(vault, effective_date):
    """
    Retrieves any additional interest by getting the balance of the ACCRUED_EXPECTED_INTEREST
    address, one month prior to the effective date. If there are any additional days since the last
    repayment, then the days at the beginning of the period are considered extra and hence will
    have interest accrued here.
    :param vault: Vault object
    :param effective_date: effective datetime
    """
    previous_month = effective_date - timedelta(months=1)
    return _get_effective_balance_by_address(vault, ACCRUED_EXPECTED_INTEREST, previous_month)


def _get_accrued_interest(vault, timestamp=None):
    """
    :param vault: balances, parameters
    :param timestamp: datetime
    :return: Decimal
    """
    return vault.modules["utils"].get_balance_sum(vault, [ACCRUED_INTEREST], timestamp)


def _get_expected_principal(vault, timestamp=None):
    """
    :param vault: balances, parameters
    :param timestamp: datetime
    :return: Decimal
    """
    return vault.modules["utils"].get_balance_sum(vault, EXPECTED_PRINCIPAL, timestamp)


def _get_outstanding_actual_principal(vault, timestamp=None):
    """
    :param vault: balances, parameters
    :param timestamp: datetime
    :return: Decimal
    """
    return vault.modules["utils"].get_balance_sum(vault, REMAINING_PRINCIPAL, timestamp)


def _get_overdue_balance(vault, timestamp=None):
    """
    :param vault: balances, parameters
    :param timestamp: datetime
    :return: Decimal
    """
    return vault.modules["utils"].get_balance_sum(vault, OVERDUE_ADDRESSES, timestamp)


def _get_late_payment_balance(vault, timestamp=None):
    """
    :param vault: balances, parameters
    :param timestamp: datetime
    :return: Decimal
    """
    return vault.modules["utils"].get_balance_sum(vault, LATE_PAYMENT_ADDRESSES, timestamp)


def _get_all_outstanding_debt(vault, timestamp=None):
    """
    :param vault: balances, parameters
    :param timestamp: datetime
    :return: Decimal
    """
    fulfillment_precision = vault.modules["utils"].get_parameter(
        vault, name="fulfillment_precision"
    )

    return _round_to_precision(
        fulfillment_precision,
        vault.modules["utils"].get_balance_sum(vault, ALL_ADDRESSES, timestamp),
    )


def _sum_outstanding_dues(vault, timestamp=None):
    """
    :param vault: balances, parameters
    :param timestamp: datetime
    :return: Decimal
    """
    return vault.modules["utils"].get_balance_sum(vault, REPAYMENT_ORDER, timestamp)


# Generic helper functions
def _has_schedule_run_today(vault, effective_date: datetime, schedule_name: str) -> bool:
    last_run_time = vault.get_last_execution_time(event_type=schedule_name)
    if last_run_time:
        return True if effective_date.date() == last_run_time.date() else False
    return False


def _instruct_posting_batch(
    vault,
    posting_instructions: List[PostingInstruction],
    effective_date: datetime,
    event_type: str,
) -> None:
    """
    Instructs posting batch if instructions variable contains any posting instructions.

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
