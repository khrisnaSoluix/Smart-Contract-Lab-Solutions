# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
api = "3.9.0"
version = "4.16.5"
display_name = "Loan"
summary = "A new car, holiday or wedding? Our loan offers "
"competitive rates and flexible terms."
tside = Tside.ASSET

# this can be amended to whichever other currencies as needed
supported_denominations = ["GBP"]

# Schedule events
ACCRUE_INTEREST = "ACCRUE_INTEREST"
REPAYMENT_DAY_SCHEDULE = "REPAYMENT_DAY_SCHEDULE"
BALLOON_PAYMENT_SCHEDULE = "BALLOON_PAYMENT_SCHEDULE"
CHECK_OVERDUE = "CHECK_OVERDUE"
CHECK_DELINQUENCY = "CHECK_DELINQUENCY"

event_types = [
    EventType(name=ACCRUE_INTEREST, scheduler_tag_ids=["LOAN_ACCRUE_INTEREST_AST"]),
    EventType(
        name=BALLOON_PAYMENT_SCHEDULE,
        scheduler_tag_ids=["LOAN_BALLOON_PAYMENT_SCHEDULE_AST"],
    ),
    EventType(
        name=REPAYMENT_DAY_SCHEDULE,
        scheduler_tag_ids=["LOAN_REPAYMENT_DAY_SCHEDULE_AST"],
    ),
    EventType(name=CHECK_OVERDUE, scheduler_tag_ids=["LOAN_CHECK_OVERDUE_AST"]),
    EventType(name=CHECK_DELINQUENCY, scheduler_tag_ids=["LOAN_CHECK_DELINQUENCY_AST"]),
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
ACCRUED_INTEREST_PENDING_CAPITALISATION = "ACCRUED_INTEREST_PENDING_CAPITALISATION"
ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION = "ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION"
PRINCIPAL_CAPITALISED_INTEREST = "PRINCIPAL_CAPITALISED_INTEREST"
PRINCIPAL_CAPITALISED_PENALTIES = "PRINCIPAL_CAPITALISED_PENALTIES"
INTERNAL_CONTRA = "INTERNAL_CONTRA"

DAYS_IN_A_WEEK = 7
DAYS_IN_A_YEAR = 365
WEEKS_IN_YEAR = 52
MONTHS_IN_A_YEAR = 12

OVERDUE_ADDRESSES = [PRINCIPAL_OVERDUE, INTEREST_OVERDUE]
LATE_PAYMENT_ADDRESSES = OVERDUE_ADDRESSES + [PENALTIES]
REPAYMENT_ORDER = LATE_PAYMENT_ADDRESSES + [PRINCIPAL_DUE, INTEREST_DUE]
PRINCIPAL_WITH_CAPITALISED = [
    PRINCIPAL,
    PRINCIPAL_CAPITALISED_INTEREST,
    PRINCIPAL_CAPITALISED_PENALTIES,
]
REMAINING_PRINCIPAL = [
    PRINCIPAL,
    OVERPAYMENT,
    EMI_PRINCIPAL_EXCESS,
    PRINCIPAL_CAPITALISED_INTEREST,
    PRINCIPAL_CAPITALISED_PENALTIES,
]
ALL_ADDRESSES = (
    REPAYMENT_ORDER
    + REMAINING_PRINCIPAL
    + [ACCRUED_INTEREST, ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION]
)

RateShape = NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.0001)

parameters = [
    # Instance Parameters
    Parameter(
        name="fixed_interest_rate",
        shape=RateShape,
        level=Level.INSTANCE,
        description="The fixed annual rate of the loan.",
        display_name="Fixed interest rate (p.a.)",
        default_value=Decimal("0.135"),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="upfront_fee",
        shape=NumberShape(kind=NumberKind.MONEY),
        level=Level.INSTANCE,
        description="A flat fee charged for opening an account.",
        display_name="Upfront fee",
        default_value=Decimal("0"),
        update_permission=UpdatePermission.FIXED,
    ),
    Parameter(
        name="amortise_upfront_fee",
        shape=UnionShape(
            UnionItem(key="True", display_name="True"),
            UnionItem(key="False", display_name="False"),
        ),
        level=Level.INSTANCE,
        description="If True, upfront fee added to principal."
        " If False, upfront fee deducted from principal.",
        display_name="Amortise upfront fee",
        default_value=UnionItemValue(key="False"),
        update_permission=UpdatePermission.FIXED,
    ),
    Parameter(
        name="fixed_interest_loan",
        level=Level.INSTANCE,
        description="Whether it is a fixed rate loan or not, if set to False variable "
        "rate will be used.",
        display_name="Fixed rate Loan",
        shape=UnionShape(
            UnionItem(key="True", display_name="True"),
            UnionItem(key="False", display_name="False"),
        ),
        default_value=UnionItemValue(key="True"),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="total_term",
        shape=NumberShape(min_value=Decimal(12), max_value=Decimal(60), step=Decimal(1)),
        level=Level.INSTANCE,
        description="The agreed length of the loan (in months).",
        display_name="Loan term (months)",
        default_value=Decimal(12),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="principal",
        shape=NumberShape(
            min_value=Decimal(1000),
            max_value=Decimal(20000),
            step=Decimal(1),
            kind=NumberKind.MONEY,
        ),
        level=Level.INSTANCE,
        description="The agreed amount the customer will borrow from the bank.",
        display_name="Loan principal",
        default_value=Decimal(1000),
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
        name="loan_start_date",
        shape=DateShape(min_date=datetime.min, max_date=datetime.max),
        level=Level.INSTANCE,
        description="Start of the loan contract terms, either after account opening " "or top up.",
        display_name="Contract effective date",
        default_value=datetime.utcnow(),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="repayment_holiday_impact_preference",
        shape=UnionShape(
            UnionItem(key="increase_term", display_name="Increase term"),
            UnionItem(key="increase_emi", display_name="Increase EMI"),
        ),
        level=Level.INSTANCE,
        description="Defines how to handle a repayment holiday on a loan: "
        "Increase EMI but keep the term of the loan the same. "
        "Increase term but keep the monthly repayments the same. ",
        display_name="Repayment holiday impact preference",
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=UnionItemValue(key="increase_emi"),
    ),
    Parameter(
        name="capitalise_late_repayment_fee",
        shape=UnionShape(
            UnionItem(key="True", display_name="True"),
            UnionItem(key="False", display_name="False"),
        ),
        level=Level.INSTANCE,
        description="If True, late repayment fee added to principal."
        " If False, repayable as separate fee.",
        display_name="Capitalise late repayment fee",
        default_value=UnionItemValue(key="False"),
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="interest_accrual_rest_type",
        level=Level.INSTANCE,
        description="The type of interest rest to apply to the loan (daily "
        "or monthly). A monthly rest interest will accrue interest based on "
        "the previous months balances. Whereas daily will accrue interest on the "
        "current outstanding principal balance as of that day.",
        display_name="Interest rest type (daily or monthly)",
        shape=UnionShape(
            UnionItem(key="daily", display_name="Daily"),
            UnionItem(key="monthly", display_name="Monthly"),
        ),
        update_permission=UpdatePermission.FIXED,
        default_value=UnionItemValue(key="daily"),
    ),
    Parameter(
        name="balloon_payment_days_delta",
        shape=OptionalShape(NumberShape(min_value=0, step=1)),
        level=Level.INSTANCE,
        description="The number of days between the final repayment event and "
        "the balloon payment event.",
        display_name="Balloon Payment Days Delta",
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="balloon_payment_amount",
        shape=OptionalShape(
            NumberShape(
                min_value=Decimal(1000),
                max_value=Decimal(20000),
                step=Decimal(1),
                kind=NumberKind.MONEY,
            ),
        ),
        level=Level.INSTANCE,
        description="The balloon payment amount the customer has chosen to pay on the balloon"
        " payment day. If set, this determines the customer has chosen a fixed balloon payment.",
        display_name="Balloon Payment Amount",
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    Parameter(
        name="balloon_emi_amount",
        shape=OptionalShape(
            NumberShape(
                min_value=Decimal(0),
                max_value=Decimal(20000),
                step=Decimal(1),
                kind=NumberKind.MONEY,
            ),
        ),
        level=Level.INSTANCE,
        description="The fixed balloon emi amount the customer has chosen to pay each "
        "month. If set, this determines the customer has chosen a fixed emi payment.",
        display_name="Balloon Payment EMI Amount",
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
        description="Remaining total term of the loan in months",
        display_name="Remaining term in months",
    ),
    Parameter(
        # EMI is not relevant for interest_only and no_repayment amortisation types
        # so is set to zero by default
        name="expected_emi",
        shape=NumberShape(),
        level=Level.INSTANCE,
        derived=True,
        description="Expected EMI (Equated Monthly Installment)",
        display_name="Expected EMI",
    ),
    Parameter(
        name="next_repayment_date",
        shape=DateShape(min_date=datetime.min, max_date=datetime.max),
        level=Level.INSTANCE,
        derived=True,
        description="Next scheduled repayment date",
        display_name="Next Repayment date",
    ),
    Parameter(
        name="next_overdue_date",
        shape=DateShape(min_date=datetime.min, max_date=datetime.max),
        level=Level.INSTANCE,
        derived=True,
        description="The date on which current due principal and interest will become overdue.",
        display_name="Overdue date",
    ),
    Parameter(
        name="total_early_repayment_amount",
        shape=NumberShape(kind=NumberKind.MONEY),
        level=Level.INSTANCE,
        derived=True,
        description="The amount needed to fully repay loan, taking into account any repayment "
        "fees.",
        display_name="Total early repayment amount",
    ),
    Parameter(
        name="expected_balloon_payment_amount",
        shape=NumberShape(kind=NumberKind.MONEY),
        level=Level.INSTANCE,
        derived=True,
        description="The expected balloon payment amount to be paid on the balloon payment date. "
        "This is only relevant for no_repayment, interest_only and "
        "minimum_repayment_with_balloon_payment loans.",
        display_name="Expected Balloon Payment Amount",
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
        description="The annual rate for a variable interest loan.",
        display_name="Variable interest rate (p.a.)",
        default_value=Decimal("0.129971"),
    ),
    Parameter(
        name="annual_interest_rate_cap",
        shape=RateShape,
        level=Level.TEMPLATE,
        description="The maximum annual interest rate for a variable interest loan.",
        display_name="Variable annual interest rate cap (p.a.)",
        default_value=Decimal("1"),
    ),
    Parameter(
        name="annual_interest_rate_floor",
        shape=RateShape,
        level=Level.TEMPLATE,
        description="The minimum annual interest rate for a variable interest loan.",
        display_name="Variable annual interest rate floor (p.a.)",
        default_value=Decimal("0"),
    ),
    Parameter(
        name="late_repayment_fee",
        shape=NumberShape(kind=NumberKind.MONEY),
        level=Level.TEMPLATE,
        description="Fee to apply due to late repayment.",
        display_name="Late repayment fee",
        default_value=Decimal("25"),
    ),
    Parameter(
        name="penalty_interest_rate",
        shape=RateShape,
        level=Level.TEMPLATE,
        description="The annual interest rate to be applied to overdues.",
        display_name="Penalty interest rate (p.a.)",
        default_value=Decimal("0.1"),
    ),
    Parameter(
        name="capitalise_no_repayment_accrued_interest",
        shape=UnionShape(
            UnionItem(key="daily", display_name="Daily"),
            UnionItem(key="monthly", display_name="Monthly"),
            UnionItem(key="no_capitalisation", display_name="No Capitalisation"),
        ),
        level=Level.TEMPLATE,
        description="Used for no_repayment amortised loans only."
        "Determines whether interest accrued is capitalised or not."
        "If daily, accrued interest added to principal daily. "
        "If monthly, accrued interest added to principal monthly."
        "If no_capitalisation then accrued interest is not added to principal.",
        display_name="Capitalise penalty interest",
        default_value=UnionItemValue(key="no_capitalisation"),
    ),
    Parameter(
        name="capitalise_penalty_interest",
        shape=UnionShape(
            UnionItem(key="True", display_name="True"),
            UnionItem(key="False", display_name="False"),
        ),
        level=Level.TEMPLATE,
        description="If True, penalty interest added to principal at the next repayment date."
        " If False, repayable as separate fee.",
        display_name="Capitalise penalty interest",
        default_value=UnionItemValue(key="False"),
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
        default_value=UnionItemValue(key="True"),
    ),
    Parameter(
        name="grace_period",
        shape=NumberShape(
            max_value=27,
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
        name="repayment_period",
        shape=NumberShape(max_value=27, min_value=1, step=1),
        level=Level.TEMPLATE,
        description="The number of days to repay due amount before incurring penalties.",
        display_name="Repayment period (days)",
        default_value=1,
    ),
    Parameter(
        name="penalty_compounds_overdue_interest",
        level=Level.TEMPLATE,
        description="If True, include both overdue interest and overdue principal in the "
        "penalty interest calculation. If False, only include overdue principal.",
        display_name="Penalty compounds overdue interest",
        shape=UnionShape(
            UnionItem(key="True", display_name="True"),
            UnionItem(key="False", display_name="False"),
        ),
        default_value=UnionItemValue(key="False"),
    ),
    Parameter(
        name="overpayment_impact_preference",
        shape=UnionShape(
            UnionItem(key="reduce_term", display_name="Reduce term"),
            UnionItem(key="reduce_emi", display_name="Reduce EMI"),
        ),
        level=Level.TEMPLATE,
        description="Defines how to handle an overpayment on a loan:"
        "Reduce EMI but keep the term of the loan the same."
        "Reduce term but keep the monthly repayments the same.",
        display_name="Overpayment impact preference",
        default_value=UnionItemValue(key="reduce_term"),
    ),
    Parameter(
        name="accrue_interest_on_due_principal",
        level=Level.TEMPLATE,
        description="Allows interest accrual on due principal "
        "If true, interest is accrued on all unpaid principal.",
        display_name="Accrue interest on due principal",
        shape=UnionShape(
            UnionItem(key="True", display_name="True"),
            UnionItem(key="False", display_name="False"),
        ),
        default_value=UnionItemValue(key="False"),
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
        name="check_overdue_hour",
        shape=NumberShape(min_value=0, max_value=23, step=1),
        level=Level.TEMPLATE,
        description="The hour of the day at which overdue is checked.",
        display_name="Check overdue hour",
        default_value=0,
    ),
    Parameter(
        name="check_overdue_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the day at which overdue is checked.",
        display_name="Check overdue minute",
        default_value=0,
    ),
    Parameter(
        name="check_overdue_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the day at which overdue is checked.",
        display_name="Check overdue second",
        default_value=2,
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
        display_name="Repayment hour",
        default_value=0,
    ),
    Parameter(
        name="repayment_minute",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The minute of the day at which which due amount is calculated.",
        display_name="Repayment minute",
        default_value=1,
    ),
    Parameter(
        name="repayment_second",
        shape=NumberShape(min_value=0, max_value=59, step=1),
        level=Level.TEMPLATE,
        description="The second of the day at which which due amount is calculated.",
        display_name="Repayment second",
        default_value=0,
    ),
    Parameter(
        name="amortisation_method",
        level=Level.TEMPLATE,
        description="Options are: "
        "1. Declining Principal, interest is calculated on a declining balance. "
        "2. Flat Interest, interest is pre-determined at the start of the loan "
        "and distributed evenly across the loan term."
        "3. Rule of 78, this is a flat interest loan where the interest is distributed "
        "across the term in accordance with the rule of 78. "
        "4. Interest Only, interest is calculated on a declining balance but only interest "
        "is to be paid off each month, principal is paid off as a balloon payment at the "
        "end of the loan term."
        "5. No Repayment, interest is calculated on a declining balance but no payments "
        "are due throughout the loan, principal and accrued interest are paid off as a "
        "balloon payment at the end of the loan term."
        "6. Minimum Repayment with Balloon Payment, either pay a fixed (reduced) emi each month"
        "and pay any remaining principal and accrued interest at the end of the loan, or "
        "pay a fixed balloon payment at the end of the loan and pay a reduced emi each month.",
        display_name="Amortisation method",
        shape=UnionShape(
            UnionItem(key="declining_principal", display_name="Declining Principal"),
            UnionItem(key="flat_interest", display_name="Flat Interest"),
            UnionItem(key="rule_of_78", display_name="Rule of 78"),
            UnionItem(key="interest_only", display_name="Interest Only"),
            UnionItem(key="no_repayment", display_name="No Repayment"),
            UnionItem(
                key="minimum_repayment_with_balloon_payment",
                display_name="Minimum Repayment with Balloon Payment",
            ),
        ),
        default_value=UnionItemValue(key="declining_principal"),
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
    Parameter(
        name="overpayment_fee_rate",
        level=Level.TEMPLATE,
        description="Percentage fee charged on overpaid amount for overpayments.",
        display_name="Overpayment fee rate",
        shape=RateShape,
        default_value=Decimal("0.05"),
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
        name="capitalised_interest_receivable_account",
        level=Level.TEMPLATE,
        description="Internal account for unrealised capitalised interest receivable balance.",
        display_name="Capitalised interest receivable account",
        shape=AccountIdShape,
        default_value="CAPITALISED_INTEREST_RECEIVABLE",
    ),
    Parameter(
        name="capitalised_penalties_received_account",
        level=Level.TEMPLATE,
        description="Internal account for capitalised penalties received balance.",
        display_name="Capitalised penalties received account",
        shape=AccountIdShape,
        default_value="CAPITALISED_PENALTIES_RECEIVED",
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
        name="overpayment_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for overpayment fee income balance.",
        display_name="Overpayment fee income account",
        shape=AccountIdShape,
        default_value="OVERPAYMENT_FEE_INCOME",
    ),
    Parameter(
        name="upfront_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for upfront fee income balance.",
        display_name="Upfront fee income account",
        shape=AccountIdShape,
        default_value="UPFRONT_FEE_INCOME",
    ),
]

contract_module_imports = [
    ContractModule(
        alias="amortisation",
        expected_interface=[
            SharedFunction(name="construct_declining_principal_amortisation_input"),
            SharedFunction(name="construct_emi_recalculation_condition_input"),
            SharedFunction(name="construct_flat_interest_amortisation_input"),
            SharedFunction(name="construct_interest_only_amortisation_input"),
            SharedFunction(name="calculate_declining_principal_repayment"),
            SharedFunction(name="calculate_flat_interest_repayment"),
            SharedFunction(name="calculate_interest_only_repayment"),
        ],
    ),
    ContractModule(
        alias="utils",
        expected_interface=[
            SharedFunction(name="get_balance_sum"),
            SharedFunction(name="get_parameter"),
            SharedFunction(name="has_parameter_value_changed"),
            SharedFunction(name="is_flag_in_list_applied"),
            SharedFunction(name="str_to_bool"),
        ],
    ),
]


# Vault hooks
@requires(modules=["utils"], parameters=True)
def execution_schedules():
    repayment_day_param = vault.modules["utils"].get_parameter(vault, "repayment_day")
    loan_start_date = vault.modules["utils"].get_parameter(vault, "loan_start_date").date()
    loan_start_date_plus_day = loan_start_date + timedelta(days=1)

    accrue_interest_schedule = _get_accrue_interest_schedule(vault)
    repayment_day_schedule = _get_initial_repayment_day_schedule(vault, repayment_day_param)
    check_overdue_schedule = {
        "hour": str(vault.modules["utils"].get_parameter(vault, "check_overdue_hour")),
        "minute": str(vault.modules["utils"].get_parameter(vault, "check_overdue_minute")),
        "second": str(vault.modules["utils"].get_parameter(vault, "check_overdue_second")),
        "end_date": str(loan_start_date_plus_day),
        "start_date": str(loan_start_date_plus_day),
    }
    check_delinquency_schedule = {
        "hour": str(vault.modules["utils"].get_parameter(vault, "check_delinquency_hour")),
        "minute": str(vault.modules["utils"].get_parameter(vault, "check_delinquency_minute")),
        "second": str(vault.modules["utils"].get_parameter(vault, "check_delinquency_second")),
        "end_date": str(loan_start_date_plus_day),
        "start_date": str(loan_start_date_plus_day),
    }
    schedules = [
        (ACCRUE_INTEREST, accrue_interest_schedule),
        (REPAYMENT_DAY_SCHEDULE, repayment_day_schedule),
        (CHECK_OVERDUE, check_overdue_schedule),
        (CHECK_DELINQUENCY, check_delinquency_schedule),
    ]

    if _is_balloon_payment_loan(vault):
        schedules.append(_get_balloon_payment_schedule(vault))

    return schedules


@requires(
    modules=["utils"],
    event_type="ACCRUE_INTEREST",
    parameters=True,
    balances="2 months",
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
    event_type="BALLOON_PAYMENT_SCHEDULE",
    parameters=True,
    balances="latest live",
    last_execution_time=["REPAYMENT_DAY_SCHEDULE"],
    flags=True,
)
@requires(
    modules=["utils"],
    event_type="CHECK_OVERDUE",
    parameters=True,
    balances="latest live",
    flags=True,
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
        _handle_accrue_interest(vault, effective_date)
    elif event_type == REPAYMENT_DAY_SCHEDULE:
        _handle_repayment_due(vault, effective_date)
    elif event_type == BALLOON_PAYMENT_SCHEDULE:
        _handle_balloon_payment(vault, effective_date)
    elif event_type == CHECK_OVERDUE:
        _handle_overdue(vault, effective_date)
    elif event_type == CHECK_DELINQUENCY:
        _check_delinquency(vault, effective_date)


@requires(
    modules=["amortisation", "utils"],
    parameters=True,
    balances="1 year",
    last_execution_time=["REPAYMENT_DAY_SCHEDULE"],
    flags=True,
)
def derived_parameters(effective_date):
    total_outstanding_debt = _get_all_outstanding_debt(vault)
    next_repayment_date = _calculate_next_repayment_date(vault, effective_date)

    repayment_period = vault.modules["utils"].get_parameter(vault, "repayment_period")
    next_overdue_date = next_repayment_date + timedelta(days=int(repayment_period))
    sum_outstanding_dues = _sum_outstanding_dues(vault)
    outstanding_actual_principal = _get_outstanding_actual_principal(vault)
    max_overpayment_fee = _get_overpayment_fee(
        vault, sum_outstanding_dues + _get_maximum_overpayment(vault)
    )
    total_early_repayment_amount = total_outstanding_debt + max_overpayment_fee
    return {
        "total_outstanding_debt": total_outstanding_debt,
        "remaining_principal": outstanding_actual_principal,
        "outstanding_payments": sum_outstanding_dues,
        "total_early_repayment_amount": total_early_repayment_amount,
        "next_repayment_date": next_repayment_date,
        "next_overdue_date": next_overdue_date,
        "remaining_term": _get_remaining_term_in_months(vault, effective_date, "total_term"),
        "expected_emi": _get_expected_emi(vault, effective_date),
        "expected_balloon_payment_amount": _get_expected_balloon_payment_amount(
            vault, effective_date
        ),
    }


@requires(modules=["utils"], parameters=True)
def post_activate_code():
    # using account creation date instead of loan start date to:
    # avoid back dating time component (date param will default to midnight)
    # this logic will only run for initial disbursement, not subsequent topups
    # therefore creation_date and loan_start_date are equivalent here
    start_date = vault.modules["utils"].get_parameter(vault, name="loan_start_date")
    principal = vault.modules["utils"].get_parameter(vault, name="principal")
    deposit_account_id = vault.modules["utils"].get_parameter(vault, name="deposit_account")
    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")

    upfront_fee_account = vault.modules["utils"].get_parameter(
        vault, name="upfront_fee_income_account"
    )

    upfront_fee = vault.modules["utils"].get_parameter(vault, "upfront_fee")
    amortise_upfront_fee = vault.modules["utils"].get_parameter(
        vault, "amortise_upfront_fee", union=True
    )

    if amortise_upfront_fee.upper() == "FALSE" and upfront_fee > 0:
        principal = principal - upfront_fee

    posting_ins = []
    posting_ins.extend(
        vault.make_internal_transfer_instructions(
            amount=principal,
            denomination=denomination,
            client_transaction_id=vault.get_hook_execution_id() + "_PRINCIPAL_DISBURSMENT",
            from_account_id=vault.account_id,
            from_account_address=PRINCIPAL,
            to_account_id=deposit_account_id,
            to_account_address=DEFAULT_ADDRESS,
            instruction_details={
                "description": f"Payment of {principal} of loan principal",
                "event": "PRINCIPAL_PAYMENT",
            },
            asset=DEFAULT_ASSET,
        )
    )

    if upfront_fee > 0:
        posting_ins.extend(
            vault.make_internal_transfer_instructions(
                amount=upfront_fee,
                denomination=denomination,
                client_transaction_id=vault.get_hook_execution_id() + "_UPFRONT_FEE_DISBURSMENT",
                from_account_id=vault.account_id,
                from_account_address=PRINCIPAL,
                to_account_id=upfront_fee_account,
                to_account_address=DEFAULT_ADDRESS,
                instruction_details={
                    "description": f"Applying upfront fee of {upfront_fee}",
                    "event": "TRANSFER_UPFRONT_FEE",
                },
                asset=DEFAULT_ASSET,
            )
        )

    vault.instruct_posting_batch(
        posting_instructions=posting_ins,
        effective_date=start_date,
        client_batch_id=f"BATCH_{vault.get_hook_execution_id()}_INITIAL_LOAN_DISBURSMENT",
    )


@requires(
    modules=["utils"],
    parameters=True,
    last_execution_time=["REPAYMENT_DAY_SCHEDULE"],
    flags=True,
    balances="latest live",
)
def post_parameter_change_code(
    old_parameter_values: Dict[str, Parameter],
    updated_parameter_values: Dict[str, Parameter],
    effective_date: datetime,
):
    _handle_repayment_day_change(
        vault, old_parameter_values, updated_parameter_values, effective_date
    )
    _handle_top_up(vault, updated_parameter_values, effective_date)


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
        proposed_amount = _get_posting_amount(posting)
        if proposed_amount <= 0:
            if vault.modules["utils"].is_flag_in_list_applied(
                vault, "repayment_blocking_flags", effective_date
            ):
                raise Rejected(
                    "Repayments blocked for this account.",
                    reason_code=RejectedReason.AGAINST_TNC,
                )
            outstanding_debt = _get_all_outstanding_debt(vault)
            overpayment_fee = _get_overpayment_fee(vault, abs(proposed_amount))
            if abs(proposed_amount) > outstanding_debt + overpayment_fee:
                raise Rejected(
                    "Cannot pay more than is owed",
                    reason_code=RejectedReason.AGAINST_TNC,
                )
            amortisation_type = (
                vault.modules["utils"]
                .get_parameter(vault, "amortisation_method", union=True)
                .replace("_", " ")
            )
            if (
                abs(proposed_amount) > _sum_outstanding_dues(vault)
                and not postings.batch_details.get("event") == "early_repayment"
                and (
                    _is_flat_interest_amortisation_method(vault)
                    or _is_minimum_repayment_amortisation_method(vault)
                )
            ):
                raise Rejected(
                    f"Overpayments are not allowed for {amortisation_type} loans",
                    reason_code=RejectedReason.AGAINST_TNC,
                )

        elif (
            postings.batch_details.get("fee") != "True"
            and postings.batch_details.get("interest_adjustment") != "True"
        ):
            raise Rejected(
                "Debiting not allowed from this account",
                reason_code=RejectedReason.AGAINST_TNC,
            )


@requires(modules=["utils"], parameters=True, balances="latest live", flags=True)
def post_posting_code(postings: PostingInstructionBatch, effective_date: datetime):
    if postings.batch_details.get("event") == "PRINCIPAL_PAYMENT_TOP_UP":
        return

    effective_date = effective_date + timedelta(microseconds=1)
    for i, posting in enumerate(postings):
        posting_amount = _get_posting_amount(posting)
        if posting_amount == 0:
            continue
        if posting_amount < 0:
            client_transaction_id = (
                f"{posting.client_transaction_id}_{vault.get_hook_execution_id()}_{i}"
            )
            _process_payment(vault, effective_date, posting, client_transaction_id, postings)

        else:
            balance_destination = (
                PENALTIES
                if vault.modules["utils"].str_to_bool(postings.batch_details.get("fee"))
                else INTEREST_DUE
            )
            posting_ins = vault.make_internal_transfer_instructions(
                amount=posting_amount,
                denomination=posting.denomination,
                client_transaction_id=vault.get_hook_execution_id() + "_" + balance_destination,
                from_account_id=vault.account_id,
                from_account_address=balance_destination,
                to_account_id=vault.account_id,
                to_account_address=DEFAULT_ADDRESS,
                instruction_details={
                    "description": f"Move {posting_amount} of balance"
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
    _handle_end_of_loan(vault, effective_date)


# Hook functions
def _handle_accrue_interest(vault, effective_date: datetime):
    posting_instructions = _get_accrue_penalty_interest_instructions(vault, effective_date)
    if not _is_flat_interest_amortisation_method(vault):
        amount_transferred, postings = _handle_interest_capitalisation(vault, effective_date)
        posting_instructions.extend(postings)
        posting_instructions.extend(
            _get_accrue_interest_instructions(
                vault, effective_date, extra_capitalised_interest=amount_transferred
            )
        )

    _instruct_posting_batch(vault, posting_instructions, effective_date, ACCRUE_INTEREST)


def _handle_repayment_due(vault, effective_date: datetime) -> None:
    monthly_due_amounts = _calculate_monthly_due_amounts(vault, effective_date)
    posting_instructions = _get_transfer_due_instructions(
        vault=vault,
        effective_date=effective_date,
        monthly_due_amounts=monthly_due_amounts,
        event_type="CALCULATE_AND_TRANSFER_DUE_AMOUNT",
    )
    posting_instructions.extend(
        _get_transfer_capitalised_interest_instructions(
            vault, ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION
        )
    )
    repayment_day = vault.modules["utils"].get_parameter(vault, "repayment_day")
    if effective_date.day != repayment_day:
        _schedule_repayment_day_change(vault, repayment_day, effective_date)

    _instruct_posting_batch(vault, posting_instructions, effective_date, REPAYMENT_DAY_SCHEDULE)
    _send_repayment_notification(vault, effective_date, monthly_due_amounts)

    if _is_balloon_payment_loan(vault) and _should_enable_balloon_payment_schedule(
        vault, effective_date
    ):
        _replace_repayment_day_schedule_with_balloon_payment(vault, effective_date)


def _handle_balloon_payment(vault, effective_date: datetime) -> None:
    """
    Calculates the due amounts for the balloon payment schedule and then
    instructs the PostingInstructions.

    There may be interest in the ACCRUED_INTEREST_PENDING_CAPITALISATION
    address, this gets capitalised and then moved to principal due
    """

    (
        additional_capitalised_interest,
        posting_instructions,
    ) = _handle_interest_capitalisation(vault, effective_date)

    fulfillment_precision = vault.modules["utils"].get_parameter(
        vault, name="fulfillment_precision"
    )

    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")

    accrued_interest = vault.modules["utils"].get_balance_sum(
        vault=vault,
        addresses=[ACCRUED_INTEREST],
        denomination=denomination,
    )
    interest_due = _round_to_precision(precision=fulfillment_precision, amount=accrued_interest)

    accrued_expected_interest = vault.modules["utils"].get_balance_sum(
        vault=vault, addresses=[ACCRUED_EXPECTED_INTEREST], denomination=denomination
    )

    # Include any additional accrued interest that is yet to be capitalised
    remaining_principal = (
        vault.modules["utils"].get_balance_sum(
            vault=vault,
            addresses=REMAINING_PRINCIPAL,
            denomination=denomination,
        )
        + additional_capitalised_interest
    )

    principal_due = _round_to_precision(precision=fulfillment_precision, amount=remaining_principal)
    expected_interest = _round_to_precision(fulfillment_precision, accrued_expected_interest)
    principal_excess = Decimal("0") if _is_no_repayment_loan else expected_interest - interest_due

    due_amounts = {
        "interest_due": interest_due,
        "accrued_interest": accrued_interest,
        "accrued_interest_excluding_overpayment": accrued_expected_interest,
        "principal_due_excluding_overpayment": principal_due,
        "principal_excess": principal_excess,
    }

    posting_instructions.extend(
        _get_transfer_due_instructions(
            vault=vault,
            effective_date=effective_date,
            monthly_due_amounts=due_amounts,
            event_type=BALLOON_PAYMENT_SCHEDULE,
        )
    )
    _instruct_posting_batch(vault, posting_instructions, effective_date, BALLOON_PAYMENT_SCHEDULE)
    _send_repayment_notification(
        vault, effective_date, {"principal": principal_due, "interest": interest_due}
    )


def _get_accrue_interest_instructions(
    vault, effective_date: datetime, extra_capitalised_interest: Decimal = 0
) -> List[PostingInstruction]:
    accrual_precision = vault.modules["utils"].get_parameter(vault, name="accrual_precision")

    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")

    accrued_interest_receivable_account = vault.modules["utils"].get_parameter(
        vault, name="accrued_interest_receivable_account"
    )

    interest_received_account = vault.modules["utils"].get_parameter(
        vault, name="interest_received_account"
    )

    # monthly rest uses previous repayment due balances which will include the already capitalised
    # interest as of the previous repayment cycle, so zero the extra_capitalised_interest
    if _is_monthly_rest_interest(vault):
        extra_capitalised_interest = 0

    interest_accrual_date = _get_balance_date_for_interest_accrual(vault)

    interest_rate = _get_interest_rate(vault, effective_date)

    daily_interest_rate = _get_daily_interest_rate(interest_rate)

    # the day after repayment holiday ends or when we are capitalising accrued interest daily,
    # PRINCIPAL_CAPITALISED_INTEREST address will not include
    # amount being transferred to PRINCIPAL_CAPITALISED_INTEREST in same contract execution
    # so we need to add extra_capitalised_interest to it
    principal_with_capitalised_interest = (
        vault.modules["utils"].get_balance_sum(
            vault, PRINCIPAL_WITH_CAPITALISED, interest_accrual_date, denomination
        )
        + extra_capitalised_interest
    )
    principal_with_capitalised_interest = (
        principal_with_capitalised_interest + _get_due_principal(vault, interest_accrual_date)
        if _is_accrue_interest_on_due_principal(vault)
        else principal_with_capitalised_interest
    )
    outstanding_principal = (
        _get_outstanding_actual_principal(vault, interest_accrual_date) + extra_capitalised_interest
    )
    outstanding_principal = (
        outstanding_principal + _get_due_principal(vault, interest_accrual_date)
        if _is_accrue_interest_on_due_principal(vault)
        else outstanding_principal
    )

    expected_interest_to_accrue = _round_to_precision(
        accrual_precision, principal_with_capitalised_interest * daily_interest_rate
    )
    interest_to_accrue = _round_to_precision(
        accrual_precision, outstanding_principal * daily_interest_rate
    )

    posting_instructions = []

    # If on due amount blocking flag OR it is a no_repayment_loan and
    # we want to capitalise interest accrue on a different address
    if vault.modules["utils"].is_flag_in_list_applied(
        vault, "due_amount_blocking_flags", effective_date
    ) or (
        _is_no_repayment_loan(vault)
        and vault.modules["utils"]
        .get_parameter(vault, name="capitalise_no_repayment_accrued_interest", union=True)
        .upper()
        != "NO_CAPITALISATION"
    ):

        if interest_to_accrue > 0:
            capitalised_interest_received_account = vault.modules["utils"].get_parameter(
                vault, name="capitalised_interest_received_account"
            )

            capitalised_interest_receivable_account = vault.modules["utils"].get_parameter(
                vault, name="capitalised_interest_receivable_account"
            )

            posting_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=interest_to_accrue,
                    denomination=denomination,
                    client_transaction_id=f"{vault.get_hook_execution_id()}_INTEREST_ACCRUAL"
                    f"_CUSTOMER",
                    from_account_id=vault.account_id,
                    from_account_address=ACCRUED_INTEREST_PENDING_CAPITALISATION,
                    to_account_id=vault.account_id,
                    to_account_address=INTERNAL_CONTRA,
                    instruction_details={
                        "description": f"Daily capitalised interest accrued at "
                        f"{daily_interest_rate * 100:0.6f}% "
                        f"on outstanding principal of {outstanding_principal}",
                        "event_type": "ACCRUE_INTEREST_PENDING_CAPITALISATION",
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
                    from_account_id=capitalised_interest_receivable_account,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=capitalised_interest_received_account,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": f"Daily capitalised interest accrued at "
                        f"{daily_interest_rate * 100:0.6f}% "
                        f"on outstanding principal of {outstanding_principal}",
                        "event_type": "ACCRUE_INTEREST_PENDING_CAPITALISATION",
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
                        "description": f"Daily interest accrued at "
                        f"{daily_interest_rate * 100:0.6f}% on outstanding principal"
                        f" of {outstanding_principal}",
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
                        "description": f"Daily interest accrued at "
                        f"{daily_interest_rate * 100:0.6f}% on outstanding principal"
                        f" of {outstanding_principal}",
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
                        "description": f"Expected daily interest accrued at "
                        f"{daily_interest_rate * 100:0.6f}% "
                        f"on principal_with_capitalised_interest of "
                        f"{principal_with_capitalised_interest} "
                        f"and outstanding_principal of {outstanding_principal}",
                        "event_type": ACCRUE_INTEREST,
                        "daily_interest_rate": f"{daily_interest_rate}",
                    },
                    asset=DEFAULT_ASSET,
                )
            )

    return posting_instructions


def _handle_interest_capitalisation(
    vault, effective_date: datetime
) -> Tuple[Decimal, List[PostingInstruction]]:
    """
    Move capitalised interest to principal. This occurs in 2 scenarios:
        1. due amount blocking flag expiry.
        2. no_repayment loan with capitalisation of accrued_interest

    :param vault: parameters, flags, balances
    :param effective_date: datetime of hook execution
    :return: interest to capitalise, associated posting instructions
    """
    due_amount_blocking_flag = vault.modules["utils"].is_flag_in_list_applied(
        vault, "due_amount_blocking_flags", effective_date
    )
    no_repayment_capitalise_interest = _is_no_repayment_loan_interest_to_be_capitalised(
        vault, effective_date
    )

    if (
        not due_amount_blocking_flag and not _is_no_repayment_loan(vault)
    ) or no_repayment_capitalise_interest:
        return (
            _get_capitalised_interest_amount(vault),
            _get_transfer_capitalised_interest_instructions(
                vault, ACCRUED_INTEREST_PENDING_CAPITALISATION
            ),
        )
    return 0, []


def _handle_overdue(vault, effective_date: datetime) -> None:
    """
    Move unpaid due amount to overdue, charge penalty fee
    and schedule for delinquency check after grace period
    :param vault: parameters, balances
    :param effective_date: datetime
    :return: None
    """
    effective_date = effective_date + timedelta(microseconds=1)
    if vault.modules["utils"].is_flag_in_list_applied(
        vault, "overdue_amount_blocking_flags", effective_date
    ):
        return
    posting_instructions = _get_overdue_postings(vault, PRINCIPAL_DUE, PRINCIPAL_OVERDUE)

    posting_instructions.extend(_get_overdue_postings(vault, INTEREST_DUE, INTEREST_OVERDUE))

    if len(posting_instructions) > 0:
        posting_instructions.extend(_get_late_repayment_fee_posting(vault))
        vault.instruct_posting_batch(
            posting_instructions=posting_instructions, effective_date=effective_date
        )
        _schedule_delinquency_check(vault, effective_date)
        _send_overdue_repayment_notification(vault, effective_date)
        if _is_flat_interest_amortisation_method(vault):
            _toggle_accrue_interest_schedule(vault, effective_date, active=True)


# part of repayment day schedule
def _get_transfer_due_instructions(
    vault,
    effective_date: datetime,
    monthly_due_amounts: Dict[str, Decimal],
    event_type: str,
) -> List[PostingInstruction]:
    """
    Return a list of PostingInstructions to transfer
    funds based on the monthly due amounts.
    """
    effective_date = effective_date + timedelta(microseconds=2)
    _schedule_overdue_check(vault, effective_date)
    if vault.modules["utils"].is_flag_in_list_applied(
        vault, "due_amount_blocking_flags", effective_date
    ):
        return []

    denomination = vault.modules["utils"].get_parameter(vault, "denomination")
    accrued_interest_receivable_account = vault.modules["utils"].get_parameter(
        vault, "accrued_interest_receivable_account"
    )
    interest_received_account = vault.modules["utils"].get_parameter(
        vault, "interest_received_account"
    )

    emi = monthly_due_amounts.get("emi", Decimal("0"))
    principal_due = monthly_due_amounts.get("principal_due_excluding_overpayment", Decimal("0"))
    interest_due = monthly_due_amounts.get("interest_due", Decimal("0"))
    accrued_interest = monthly_due_amounts.get("accrued_interest", Decimal("0"))
    accrued_expected_interest = monthly_due_amounts.get(
        "accrued_interest_excluding_overpayment", Decimal("0")
    )
    principal_excess = monthly_due_amounts.get("principal_excess", Decimal("0"))

    stored_emi = _get_effective_balance_by_address(vault, EMI_ADDRESS)

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
                to_account_id=accrued_interest_receivable_account,
                to_account_address=DEFAULT_ADDRESS,
                instruction_details={
                    "description": f"Monthly interest added to due address: {interest_due}",
                    "event": event_type,
                },
                asset=DEFAULT_ASSET,
            )
        )

        if not _is_flat_interest_amortisation_method(vault):
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

    # Were EMI is pre-defined, but is less than the value of the interest accrued any remaining
    # accrued interest should not be reversed unless this is the final repayment.
    if not (
        _is_minimum_repayment_amortisation_method(vault) and 0 < emi < accrued_interest
    ) or _should_handle_balloon_payment(vault, effective_date):

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

    denomination = vault.modules["utils"].get_parameter(vault, "denomination")
    penalty = _calculate_daily_penalty(vault, effective_date)
    posting_instructions = []

    if penalty["amount_accrued"] > Decimal("0"):
        if _is_capitalise_penalty_interest(vault):
            capitalised_interest_received_account = vault.modules["utils"].get_parameter(
                vault, name="capitalised_interest_received_account"
            )

            capitalised_interest_receivable_account = vault.modules["utils"].get_parameter(
                vault, name="capitalised_interest_receivable_account"
            )

            posting_instructions = vault.make_internal_transfer_instructions(
                amount=penalty["amount_accrued"],
                denomination=denomination,
                client_transaction_id=vault.get_hook_execution_id()
                + "_ACCRUE_AND_CAPITALISE_PENALTY_INTEREST_CUSTOMER",
                from_account_id=vault.account_id,
                from_account_address=ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                to_account_id=vault.account_id,
                to_account_address=INTERNAL_CONTRA,
                instruction_details={
                    "description": "Penalty interest accrual on overdue amount capitalised "
                    "to principal",
                    "event": "ACCRUE_AND_CAPITALISE_PENALTY_INTEREST",
                },
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
            )

            posting_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=penalty["amount_accrued"],
                    denomination=denomination,
                    client_transaction_id=vault.get_hook_execution_id()
                    + "_ACCRUE_AND_CAPITALISE_PENALTY_INTEREST_INTERNAL",
                    from_account_id=capitalised_interest_receivable_account,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=capitalised_interest_received_account,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": "Penalty interest accrual on overdue amount capitalised "
                        "to principal",
                        "event": "ACCRUE_AND_CAPITALISE_PENALTY_INTEREST",
                    },
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                )
            )

        else:
            penalty_interest_received_account = vault.modules["utils"].get_parameter(
                vault, "penalty_interest_received_account"
            )
            fulfillment_precision = vault.modules["utils"].get_parameter(
                vault, "fulfillment_precision"
            )
            penalty_interest = _round_to_precision(fulfillment_precision, penalty["amount_accrued"])
            if penalty_interest > 0:
                posting_instructions = vault.make_internal_transfer_instructions(
                    amount=penalty_interest,
                    denomination=denomination,
                    client_transaction_id=vault.get_hook_execution_id()
                    + "_ACCRUE_PENALTY_INTEREST",
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

    if penalty["amount_overdue"] == Decimal("0") and _is_flat_interest_amortisation_method(vault):
        _toggle_accrue_interest_schedule(vault, effective_date, active=False)

    return posting_instructions


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
            workflow="LOAN_MARK_DELINQUENT",
            context={"account_id": str(vault.account_id)},
        )


def _send_repayment_notification(vault, effective_date, monthly_due):
    """
    Start workflow for sending repayment notification.

    :param vault: Vault object
    :param effective_date: datetime, effective date of scheduled event
    :param monthly_due: Dict[str, Decimal], monthly due values
    :return: None
    """
    repayment_amount = (
        monthly_due.get("principal_due_excluding_overpayment", Decimal("0"))
        + monthly_due.get("principal_excess", Decimal("0"))
        + monthly_due.get("interest_due", Decimal("0"))
    )
    repayment_period = vault.modules["utils"].get_parameter(vault, "repayment_period")
    overdue_date = effective_date + timedelta(days=int(repayment_period))

    vault.start_workflow(
        workflow="LOAN_REPAYMENT_NOTIFICATION",
        context={
            "account_id": vault.account_id,
            "repayment_amount": str(repayment_amount),
            "overdue_date": str(overdue_date.date()),
        },
    )


def _send_overdue_repayment_notification(vault, effective_date):
    """
    Start workflow for sending overdue repayment notification.

    :param vault: Vault object
    :param effective_date: datetime, effective date of scheduled event
    """
    principal_due = _get_effective_balance_by_address(vault, PRINCIPAL_DUE)
    interest_due = _get_effective_balance_by_address(vault, INTEREST_DUE)

    late_repayment_fee = vault.modules["utils"].get_parameter(vault, "late_repayment_fee")

    vault.start_workflow(
        workflow="LOAN_OVERDUE_REPAYMENT_NOTIFICATION",
        context={
            "account_id": vault.account_id,
            "repayment_amount": str(principal_due + interest_due),
            "late_repayment_fee": str(late_repayment_fee),
            "overdue_date": str(effective_date.date()),
        },
    )


def _process_payment(vault, effective_date, posting, client_transaction_id, postings):
    """
    Processes a payment received from the borrower, paying off the balance in different addresses
    in the correct order
    """

    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")

    fulfillment_precision = vault.modules["utils"].get_parameter(
        vault, name="fulfillment_precision"
    )

    accrued_interest_receivable_account = vault.modules["utils"].get_parameter(
        vault, name="accrued_interest_receivable_account"
    )

    interest_received_account = vault.modules["utils"].get_parameter(
        vault, name="interest_received_account"
    )

    repayment_amount_remaining = posting.balances()[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    repayment_amount_remaining = abs(repayment_amount_remaining)
    original_repayment_amount = repayment_amount_remaining
    overpayment_fee = _get_overpayment_fee(vault, original_repayment_amount)
    overpayment_fee_income_account = vault.modules["utils"].get_parameter(
        vault, "overpayment_fee_income_account"
    )

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

    max_overpayment = _get_maximum_overpayment(vault)

    posting_amount = min(repayment_amount_remaining, max_overpayment)
    if posting_amount > 0:
        # We have an overpayment. Let's put it in the overpayment address
        overpayment_after_fee = posting_amount - overpayment_fee
        repayment_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=overpayment_after_fee,
                denomination=denomination,
                client_transaction_id=f"OVERPAYMENT_BALANCE_{client_transaction_id}",
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=vault.account_id,
                to_account_address=OVERPAYMENT,
                instruction_details={
                    "description": f"Upon repayment, {overpayment_after_fee}"
                    " of the repayment has been transfered to the OVERPAYMENT balance.",
                    "event": "OVERPAYMENT_BALANCE_INCREASE",
                },
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
            )
        )
        if overpayment_fee > Decimal("0"):
            repayment_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=overpayment_fee,
                    denomination=denomination,
                    client_transaction_id=f"OVERPAYMENT_FEE_{client_transaction_id}",
                    from_account_id=vault.account_id,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=overpayment_fee_income_account,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": f"Upon repayment, {overpayment_fee} of the "
                        "repayment has been transfered to the overpayment_fee_income_account.",
                        "event": "OVERPAYMENT_FEE",
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
                to_account_id=accrued_interest_receivable_account,
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
                    True,
                )
            )
        repayment_amount_remaining -= posting_amount

    # We may also need to repay the ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION
    capitalised_interest_balance = _get_effective_balance_by_address(
        vault, ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION
    )
    capitalised_interest_repayable = _round_to_precision(
        fulfillment_precision, capitalised_interest_balance
    )
    posting_amount = min(repayment_amount_remaining, capitalised_interest_repayable)
    if posting_amount > 0:
        capitalised_interest_received_account = vault.modules["utils"].get_parameter(
            vault, name="capitalised_interest_received_account"
        )

        capitalised_interest_receivable_account = vault.modules["utils"].get_parameter(
            vault, name="capitalised_interest_receivable_account"
        )

        repayment_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=posting_amount,
                denomination=denomination,
                client_transaction_id=f"REPAY_{ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION}_"
                f"{client_transaction_id}_CUSTOMER",
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                instruction_details={
                    "description": f"Paying off {posting_amount} "
                    f"from {ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION}"
                    f", which was at {capitalised_interest_repayable} - {effective_date}",
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
                client_transaction_id=f"REPAY_{ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION}_"
                f"{client_transaction_id}_INTERNAL",
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=capitalised_interest_receivable_account,
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
        if posting_amount == capitalised_interest_repayable:
            repayment_instructions.extend(
                _create_interest_remainder_posting(
                    vault,
                    ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
                    capitalised_interest_balance,
                    capitalised_interest_repayable,
                    "REPAYMENT",
                    capitalised_interest_received_account,
                    capitalised_interest_receivable_account,
                    denomination,
                    True,
                )
            )
    if len(repayment_instructions) > 0:
        vault.instruct_posting_batch(
            posting_instructions=repayment_instructions, effective_date=effective_date
        )

    outstanding_debt = _get_all_outstanding_debt(vault)

    # We need to do this in this way as outstanding_debt WONT include the postings made above.
    if (
        outstanding_debt - original_repayment_amount + overpayment_fee == 0
        or postings.batch_details.get("event") == "early_repayment"
    ):
        # We are done with this loan and should close.
        vault.start_workflow(workflow="LOAN_CLOSURE", context={"account_id": str(vault.account_id)})


def _handle_end_of_loan(vault, effective_date: datetime) -> None:
    """
    Nets off PRINCIPAL_CAPITALISED_INTEREST, OVERPAYMENT AND EMI_PRINCIPAL_EXCESS with
    PRINCIPAL to reflect actual principal while closing the account
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
                    "event": "END_OF_LOAN",
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
                    "event": "END_OF_LOAN",
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
                    "event": "END_OF_LOAN",
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
                    "event": "END_OF_LOAN",
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
                    "event": "END_OF_LOAN",
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
    if _is_declining_principal_amortisation_method(
        vault
    ) or _is_minimum_repayment_amortisation_method(vault):
        return _calculate_monthly_payment_interest_and_principal(
            vault, effective_date, _get_interest_rate(vault, effective_date)
        )
    elif _is_interest_only_amortisation_method(vault):
        return _calculate_interest_only_repayment(vault, effective_date)
    elif _is_flat_interest_amortisation_method(vault):
        return _calculate_monthly_payment_flat_interest(vault, effective_date)


def _calculate_interest_only_repayment(vault, effective_date: datetime) -> Dict[str, Decimal]:
    fulfillment_precision = int(
        vault.modules["utils"].get_parameter(vault, name="fulfillment_precision")
    )
    remaining_principal = _get_outstanding_actual_principal(vault)
    monthly_expected_interest_accrued = _get_effective_balance_by_address(
        vault, ACCRUED_EXPECTED_INTEREST
    )
    monthly_interest_accrued = _get_accrued_interest(vault)

    is_final_repayment_event = (
        _should_handle_balloon_payment(vault, effective_date)
        if _is_balloon_payment_loan(vault)
        else _is_last_payment_date(vault, effective_date)
    )
    interest_only_amortisation_input = vault.modules[
        "amortisation"
    ].construct_interest_only_amortisation_input(
        remaining_principal,
        monthly_interest_accrued,
        monthly_expected_interest_accrued,
        fulfillment_precision,
        is_final_repayment_event,
    )

    return vault.modules["amortisation"].calculate_interest_only_repayment(
        interest_only_amortisation_input
    )


def _get_capitalised_interest_amount(vault) -> Decimal:
    fulfillment_precision = vault.modules["utils"].get_parameter(vault, "fulfillment_precision")
    accrued_capitalised_interest = _get_effective_balance_by_address(
        vault, ACCRUED_INTEREST_PENDING_CAPITALISATION
    )
    principal_capitalised_interest = _round_to_precision(
        fulfillment_precision, accrued_capitalised_interest
    )

    return principal_capitalised_interest


def _get_transfer_capitalised_interest_instructions(
    vault, interest_address_pending_capitalisation: str
) -> List[PostingInstruction]:
    """
    Transfer accrued interest to principal capitalised interest balance.
    """
    denomination = vault.modules["utils"].get_parameter(vault, "denomination")
    fulfillment_precision = vault.modules["utils"].get_parameter(vault, "fulfillment_precision")
    capitalised_interest_received_account = vault.modules["utils"].get_parameter(
        vault, name="capitalised_interest_received_account"
    )
    capitalised_interest_receivable_account = vault.modules["utils"].get_parameter(
        vault, name="capitalised_interest_receivable_account"
    )

    event_type = (
        f"TRANSFER_{interest_address_pending_capitalisation}_"
        f"TO_{PRINCIPAL_CAPITALISED_INTEREST}"
    )
    accrued_capitalised_interest = _get_effective_balance_by_address(
        vault, interest_address_pending_capitalisation
    )
    principal_capitalised_interest = _round_to_precision(
        fulfillment_precision, accrued_capitalised_interest
    )
    posting_instructions = []
    if principal_capitalised_interest > 0:
        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=principal_capitalised_interest,
                denomination=denomination,
                client_transaction_id=f"{vault.get_hook_execution_id()}_TRANSFER"
                f"_{interest_address_pending_capitalisation}_INTERNAL",
                from_account_id=vault.account_id,
                from_account_address=PRINCIPAL_CAPITALISED_INTEREST,
                to_account_id=capitalised_interest_receivable_account,
                to_account_address=DEFAULT_ADDRESS,
                instruction_details={
                    "description": "Capitalise interest accrued to principal",
                    "event": event_type,
                },
                asset=DEFAULT_ASSET,
            )
        )

        posting_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=principal_capitalised_interest,
                denomination=denomination,
                client_transaction_id=f"{vault.get_hook_execution_id()}_TRANSFER"
                f"_{interest_address_pending_capitalisation}_CUSTOMER",
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=interest_address_pending_capitalisation,
                instruction_details={
                    "description": "Capitalise interest accrued to principal",
                    "event": event_type,
                },
                asset=DEFAULT_ASSET,
            )
        )
        posting_instructions.extend(
            _create_interest_remainder_posting(
                vault=vault,
                interest_address=interest_address_pending_capitalisation,
                actual_balance=accrued_capitalised_interest,
                rounded_balance=principal_capitalised_interest,
                event_type=event_type,
                interest_received_account=capitalised_interest_received_account,
                accrued_interest_receivable_account=capitalised_interest_receivable_account,
                denomination=denomination,
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
    if fee_amount == 0:
        return []

    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")

    if _is_capitalise_late_repayment_fee(vault):
        capitalised_penalties_received_account = vault.modules["utils"].get_parameter(
            vault, "capitalised_penalties_received_account"
        )

        return vault.make_internal_transfer_instructions(
            amount=fee_amount,
            denomination=denomination,
            client_transaction_id=vault.get_hook_execution_id() + "_CAPITALISE_LATE_REPAYMENT_FEE",
            from_account_id=vault.account_id,
            from_account_address=PRINCIPAL_CAPITALISED_PENALTIES,
            to_account_id=capitalised_penalties_received_account,
            to_account_address=DEFAULT_ADDRESS,
            instruction_details={
                "description": f"Capitalise late repayment fees of {fee_amount}",
                "event": "CAPITALISE_LATE_REPAYMENT_FEE",
            },
            asset=DEFAULT_ASSET,
        )
    else:
        late_repayment_fee_income_account = vault.modules["utils"].get_parameter(
            vault, "late_repayment_fee_income_account"
        )
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


def _get_overdue_postings(vault, due_address, overdue_address):
    amount_to_transfer = _get_effective_balance_by_address(vault, due_address)
    if amount_to_transfer == 0:
        return []

    denomination = vault.modules["utils"].get_parameter(vault, name="denomination")

    return vault.make_internal_transfer_instructions(
        amount=amount_to_transfer,
        denomination=denomination,
        client_transaction_id=vault.get_hook_execution_id() + "_" + overdue_address,
        from_account_id=vault.account_id,
        from_account_address=overdue_address,
        to_account_id=vault.account_id,
        to_account_address=due_address,
        instruction_details={
            "description": f"Mark oustanding due amount of "
            f"{amount_to_transfer} as {overdue_address}.",
            "event": "MOVE_BALANCE_INTO_" + overdue_address,
        },
        asset=DEFAULT_ASSET,
    )


# Interest rate helper functions
def _get_interest_rate(vault, effective_date: datetime) -> Dict[str, Union[str, Decimal]]:
    is_fixed_interest = vault.modules["utils"].get_parameter(
        vault, "fixed_interest_loan", at=effective_date, union=True, is_boolean=True
    )

    interest_rate_type = "fixed_interest_rate" if is_fixed_interest else "variable_interest_rate"
    annual_interest_rate = vault.modules["utils"].get_parameter(
        vault, interest_rate_type, at=effective_date
    )
    if not is_fixed_interest:
        variable_rate_adjustment = vault.modules["utils"].get_parameter(
            vault, "variable_rate_adjustment", at=effective_date
        )
        annual_interest_rate_cap = vault.modules["utils"].get_parameter(
            vault, "annual_interest_rate_cap", at=effective_date
        )
        annual_interest_rate_floor = vault.modules["utils"].get_parameter(
            vault, "annual_interest_rate_floor", at=effective_date
        )

        annual_interest_rate = max(
            min(
                annual_interest_rate + variable_rate_adjustment,
                annual_interest_rate_cap,
            ),
            annual_interest_rate_floor,
        )

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


def _get_penalty_daily_rate(vault, effective_date: datetime):
    """
    :param vault: parameters
    :param effective_date: Run date
    :return: Decimal
    """
    penalty_interest_rate = vault.modules["utils"].get_parameter(vault, "penalty_interest_rate")
    base_rate = _get_interest_rate(vault, effective_date)["interest_rate"]

    if (
        vault.modules["utils"]
        .get_parameter(vault, "penalty_includes_base_rate", union=True)
        .upper()
        == "TRUE"
    ):
        penalty_interest_rate += base_rate

    return _interest_rate_precision(penalty_interest_rate / DAYS_IN_A_YEAR)


# Time calculation helper functions
def _calculate_next_repayment_date(vault, effective_date: datetime) -> datetime:
    loan_start_date = vault.modules["utils"].get_parameter(vault, "loan_start_date")

    last_execution_time = vault.get_last_execution_time(event_type=REPAYMENT_DAY_SCHEDULE)

    if _is_no_repayment_loan(vault):
        total_term = vault.modules["utils"].get_parameter(vault, name="total_term")
        return loan_start_date + timedelta(months=total_term)
    elif (
        effective_date.date() != loan_start_date.date()
        and _is_balloon_payment_loan(vault)
        and _should_enable_balloon_payment_schedule(vault, last_execution_time)
    ):
        balloon_payment_delta = vault.modules["utils"].get_parameter(
            vault, name="balloon_payment_days_delta", optional=True
        )
        return last_execution_time + timedelta(days=int(balloon_payment_delta))

    repayment_day = vault.modules["utils"].get_parameter(vault, "repayment_day")
    repayment_hour = vault.modules["utils"].get_parameter(vault, "repayment_hour")
    repayment_minute = vault.modules["utils"].get_parameter(vault, "repayment_minute")
    repayment_second = vault.modules["utils"].get_parameter(vault, "repayment_second")

    previous_repayment_day = (
        last_execution_time.day
        if last_execution_time and effective_date != loan_start_date
        else repayment_day
    )
    if previous_repayment_day != repayment_day:
        # then we've had a repayment day change
        if last_execution_time.month == effective_date.month or repayment_day > effective_date.day:
            # then repayment event has either occured this month
            # or it has not AND the new repayment day is in the future
            # so next repayment event is the following month from the last execution
            # on the new repayment day
            next_repayment_date = last_execution_time + timedelta(
                months=1,
                day=repayment_day,
                hour=repayment_hour,
                minute=repayment_minute,
                second=repayment_second,
                microsecond=0,
            )
        else:
            # the repayment day has not occured this month yet
            next_repayment_date = last_execution_time + timedelta(months=1)
        return next_repayment_date

    earliest_event_start_date = loan_start_date + timedelta(months=1)
    if last_execution_time and loan_start_date < last_execution_time <= effective_date:
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


def _get_days_elapsed_since_last_repayment_date(vault, effective_date: datetime) -> int:
    previous_repayment_date = vault.get_last_execution_time(event_type=REPAYMENT_DAY_SCHEDULE)
    if previous_repayment_date is None:
        previous_repayment_date = vault.modules["utils"].get_parameter(
            vault, name="loan_start_date"
        )
    return timedelta(effective_date.date(), previous_repayment_date.date()).days


def _get_remaining_term_in_months(vault, effective_date: datetime, term_name: str) -> int:
    """
    Returns the remaining loan term in months, taking into account past over-payments.
    Since we are using remaining principal, the cutoff point for months is at transfer due.
    This is essentially a forecast given the current account state and so does
    not consider future late repayments or over-payments. Fees are assumed to be settled before
    the end of the loan and are not influential. It is assumed that there can be a due balance
    remaining at the end of the loan.
    """
    expected_remaining_term = _get_expected_remaining_term(vault, effective_date, term_name)

    if _is_declining_principal_amortisation_method(vault):
        calculated_remaining_term = _get_calculated_remaining_term(vault, effective_date)

        holiday_impact_preference = (
            vault.modules["utils"]
            .get_parameter(vault, "repayment_holiday_impact_preference", union=True)
            .upper()
        )
        if holiday_impact_preference == "INCREASE_TERM" and _get_flag_duration_in_months(
            vault, effective_date, "&{REPAYMENT_HOLIDAY}", include_active=True
        ):
            # Note that remaining term will only be corrected after a repayment holiday is complete
            return calculated_remaining_term
        else:
            return min(calculated_remaining_term, expected_remaining_term)

    else:
        return expected_remaining_term


def _get_expected_remaining_term(vault, effective_date: datetime, term_name: str) -> int:
    """
    The remaining term according to the natural end date of the loan.
    """
    term = vault.modules["utils"].get_parameter(vault, name=term_name)
    loan_start_date = vault.modules["utils"].get_parameter(vault, name="loan_start_date")
    first_repayment_date = _calculate_next_repayment_date(vault, loan_start_date)

    if _is_no_repayment_loan(vault):
        return _get_remaining_term_no_repayment_loan(vault, effective_date, loan_start_date)

    # If repayment holiday and repayment_holiday_impact_preference = increase_term
    # effective_date needs to be set as if there was no repayment holiday
    # checking for past holidays only.
    holiday_impact_preference = (
        vault.modules["utils"]
        .get_parameter(vault, "repayment_holiday_impact_preference", union=True)
        .upper()
    )

    # the additional check on amortisation_method ensures that for a flat_interest or
    # rule of 78 amortised loan repayment holiday duration is always accounted for when
    #  calculating remaining term.
    # Since we only support increase_term as the result of a repayment holiday for
    # flat interest and rule of 78 loans, this acts as an 'override' incase
    # repayment_holiday_impact_preference parameter is set incorrectly
    if (
        holiday_impact_preference == "INCREASE_TERM"
        or not _is_declining_principal_amortisation_method(vault)
    ):
        repayment_holiday_months = _get_flag_duration_in_months(
            vault, effective_date, "&{REPAYMENT_HOLIDAY}"
        )
        effective_date = effective_date - timedelta(months=repayment_holiday_months)

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
    """
    loan_start_date = vault.modules["utils"].get_parameter(vault, name="loan_start_date")

    total_term = vault.modules["utils"].get_parameter(vault, name="total_term")

    principal_balance = _get_outstanding_actual_principal(vault) + vault.modules[
        "utils"
    ].get_balance_sum(vault, [ACCRUED_INTEREST_PENDING_CAPITALISATION])
    overpayment_balance = vault.modules["utils"].get_balance_sum(vault, [OVERPAYMENT])

    term_precision = 2 if overpayment_balance else 0

    # Check if loan has not yet disbursed at start of loan
    if principal_balance <= 0:
        if effective_date + timedelta(
            hour=0, minute=0, second=0, microsecond=0
        ) <= loan_start_date + timedelta(hour=0, minute=0, second=0, microsecond=0):
            return total_term
        else:
            return Decimal(0)

    emi = _get_expected_emi(vault, effective_date)
    annual_interest_rate = _get_interest_rate(vault, effective_date)
    monthly_rate = _get_monthly_interest_rate(annual_interest_rate)

    remaining_term = _round_to_precision(
        term_precision,
        Decimal(math.log((emi / (emi - principal_balance * monthly_rate)), (1 + monthly_rate))),
    )

    return math.ceil(remaining_term)


def _get_remaining_term_no_repayment_loan(
    vault, effective_date: datetime, loan_start_date: datetime
) -> int:
    total_term = vault.modules["utils"].get_parameter(vault, "total_term")
    delta = timedelta(effective_date, loan_start_date)
    delta_months = delta.years * 12 + delta.months
    return total_term - delta_months


def _is_last_payment_date(vault, effective_date: datetime) -> bool:
    holiday_impact_preference = (
        vault.modules["utils"]
        .get_parameter(vault, "repayment_holiday_impact_preference", union=True)
        .upper()
    )
    if holiday_impact_preference == "INCREASE_TERM" and _get_flag_duration_in_months(
        vault, effective_date, "&{REPAYMENT_HOLIDAY}"
    ):
        return False
    else:
        return _get_expected_remaining_term(vault, effective_date, "total_term") == 1


def _calculate_monthly_payment_flat_interest(vault, effective_date: datetime) -> Dict[str, Decimal]:

    fulfillment_precision = int(
        vault.modules["utils"].get_parameter(vault, "fulfillment_precision")
    )

    P_original = _get_P_with_upfront_fee(vault)
    P_actual = _get_outstanding_actual_principal(vault)
    R = vault.modules["utils"].get_parameter(vault, "fixed_interest_rate")
    N = vault.modules["utils"].get_parameter(vault, "total_term")

    flat_interest_amortisation_input = vault.modules[
        "amortisation"
    ].construct_flat_interest_amortisation_input(
        remaining_principal=P_actual,
        original_principal=P_original,
        annual_interest_rate=R,
        precision=fulfillment_precision,
        total_term=N,
        remaining_term=_get_expected_remaining_term(vault, effective_date, "total_term"),
        use_rule_of_78=_is_rule_of_78_amortisation_method(vault),
    )

    return vault.modules["amortisation"].calculate_flat_interest_repayment(
        flat_interest_amortisation_input
    )


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
        6. Monthly payments will not be calculated if the account is on a repayment holiday

    actual_principal is the actual remaining principal from balances (including overpayment)

    """

    # Get the last change date to interest/variables rates - if they haven't changed
    # then this is just when the rate was set (i.e. loan start date)
    # Obtain the last repayment date (if one has occurred)
    # Use this date to check if the the interest loan was fixed at that time
    # Check if the current rate is fixed

    loan_start_date = vault.modules["utils"].get_parameter(vault, name="loan_start_date")
    last_variable_rate_adjustment_change_date = vault.get_parameter_timeseries(
        name="variable_rate_adjustment"
    )[-1][0]
    last_variable_interest_rate_change_date = vault.get_parameter_timeseries(
        name="variable_interest_rate"
    )[-1][0]

    last_rate_change_date = max(
        loan_start_date,
        last_variable_rate_adjustment_change_date,
        last_variable_interest_rate_change_date,
    )

    previous_repayment_day_schedule_date = vault.modules[
        "utils"
    ].get_previous_schedule_execution_date(vault, REPAYMENT_DAY_SCHEDULE, loan_start_date)

    was_previous_interest_rate_fixed = vault.modules["utils"].get_parameter(
        vault,
        "fixed_interest_loan",
        at=previous_repayment_day_schedule_date,
        union=True,
        is_boolean=True,
    )
    is_current_interest_rate_fixed = vault.modules["utils"].get_parameter(
        vault, "fixed_interest_loan", at=effective_date, union=True, is_boolean=True
    )

    fulfillment_precision = int(
        vault.modules["utils"].get_parameter(vault, name="fulfillment_precision")
    )
    monthly_interest_rate = _get_monthly_interest_rate(annual_interest_rate)

    actual_principal = _get_outstanding_actual_principal(vault)
    principal_with_capitalised_interest = vault.modules["utils"].get_balance_sum(
        vault, PRINCIPAL_WITH_CAPITALISED
    )
    principal_excess = Decimal("0")

    balloon_payment_amount = vault.modules["utils"].get_parameter(
        vault, name="balloon_payment_amount", optional=True
    )

    remaining_term = _get_expected_remaining_term(vault, effective_date, "total_term")

    balloon_fixed_emi_amount = vault.modules["utils"].get_parameter(
        vault, "balloon_emi_amount", optional=True, at=effective_date
    )
    if balloon_fixed_emi_amount is not None:
        emi = balloon_fixed_emi_amount
        predefined_emi = True
    else:
        emi = _get_effective_balance_by_address(vault, EMI_ADDRESS)
        predefined_emi = False

    is_final_repayment_event = (
        _should_handle_balloon_payment(vault, effective_date)
        if _is_balloon_payment_loan(vault)
        else _is_last_payment_date(vault, effective_date)
    )

    # accrued additional interest relates to a circumstance where repayment dates
    # are more than a month apart and interest is accrued across the "additional"
    # days that occur

    interest_accrued = _get_accrued_interest(vault)
    accrued_additional_interest = _get_additional_interest(vault, effective_date)
    accrued_expected_interest = _get_effective_balance_by_address(vault, ACCRUED_EXPECTED_INTEREST)

    previous_overpayment_amount = _get_effective_balance_by_address(
        vault, OVERPAYMENT, previous_repayment_day_schedule_date
    )
    current_overpayment_amount = _get_effective_balance_by_address(
        vault, OVERPAYMENT, effective_date
    )
    overpayment_impact_preference = vault.modules["utils"].get_parameter(
        vault, "overpayment_impact_preference", union=True
    )

    previous_due_amount_blocked = vault.modules["utils"].is_flag_in_list_applied(
        vault,
        "due_amount_blocking_flags",
        previous_repayment_day_schedule_date,
    )
    holiday_impact_preference = vault.modules["utils"].get_parameter(
        vault, "repayment_holiday_impact_preference", union=True
    )

    emi_recalculation_condition = vault.modules[
        "amortisation"
    ].construct_emi_recalculation_condition_input(
        holiday_impact_preference,
        overpayment_impact_preference,
        previous_due_amount_blocked,
        previous_overpayment_amount,
        was_previous_interest_rate_fixed,
        is_current_interest_rate_fixed,
        previous_repayment_day_schedule_date,
        last_rate_change_date,
    )

    declining_principal_amortisation_input = vault.modules[
        "amortisation"
    ].construct_declining_principal_amortisation_input(
        fulfillment_precision,
        actual_principal,
        principal_with_capitalised_interest,
        remaining_term,
        monthly_interest_rate,
        emi,
        current_overpayment_amount,
        is_final_repayment_event,
        principal_excess,
        interest_accrued,
        accrued_expected_interest,
        accrued_additional_interest,
        emi_recalculation_condition,
        balloon_payment_amount,
        predefined_emi,
    )

    return vault.modules["amortisation"].calculate_declining_principal_repayment(
        declining_principal_amortisation_input
    )


def _get_total_interest_plus_principal_term(vault):
    return vault.modules["utils"].get_parameter(vault, "total_term")


def _calculate_daily_penalty(vault, effective_date: datetime) -> Decimal:
    """
    :param vault: parameters, balances
    """
    accrual_precision = vault.modules["utils"].get_parameter(vault, "accrual_precision")
    penalty_capital = _get_capital_for_penalty_accrual(vault)
    daily_penalty_rate = _get_penalty_daily_rate(vault, effective_date)
    return {
        "amount_accrued": _round_to_precision(
            accrual_precision, penalty_capital * daily_penalty_rate
        ),
        "amount_overdue": penalty_capital,
        "penalty_interest_rate": daily_penalty_rate,
    }


# Overpayment helper functions
def _get_overpayment_fee(vault, repayment_amount: Decimal) -> Decimal:
    outstanding_dues = _sum_outstanding_dues(vault)
    if repayment_amount <= outstanding_dues:
        return Decimal("0")

    overpayment_fee_rate = vault.modules["utils"].get_parameter(vault, "overpayment_fee_rate")
    fulfillment_precision = vault.modules["utils"].get_parameter(vault, "fulfillment_precision")
    max_overpayment = _get_maximum_overpayment(vault)
    amount_above_due = repayment_amount - outstanding_dues
    overpayment_amount = min(max_overpayment, amount_above_due)
    overpayment_fee = _round_to_precision(
        fulfillment_precision,
        overpayment_amount * overpayment_fee_rate,
    )

    return overpayment_fee


def _get_maximum_overpayment(vault) -> Decimal:
    outstanding_actual_principal = _get_outstanding_actual_principal(vault)
    overpayment_fee_rate = vault.modules["utils"].get_parameter(vault, "overpayment_fee_rate")
    fulfillment_precision = vault.modules["utils"].get_parameter(vault, "fulfillment_precision")
    return _round_to_precision(
        fulfillment_precision, outstanding_actual_principal / (1 - overpayment_fee_rate)
    )


# Schedule helper functions
def _schedule_delinquency_check(vault, effective_date: datetime):
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


def _schedule_overdue_check(vault, effective_date: datetime):
    repayment_period = vault.modules["utils"].get_parameter(vault, "repayment_period")
    repayment_period_end = effective_date + timedelta(days=int(repayment_period))
    vault.amend_schedule(
        event_type=CHECK_OVERDUE,
        new_schedule={
            "month": str(repayment_period_end.month),
            "day": str(repayment_period_end.day),
            "hour": str(vault.modules["utils"].get_parameter(vault, "check_overdue_hour")),
            "minute": str(vault.modules["utils"].get_parameter(vault, "check_overdue_minute")),
            "second": str(vault.modules["utils"].get_parameter(vault, "check_overdue_second")),
            "year": str(repayment_period_end.year),
        },
    )


def _toggle_accrue_interest_schedule(vault, effective_date: datetime, active: bool = False):
    effective_date += timedelta(minutes=1)
    new_schedule = {
        "hour": str(vault.modules["utils"].get_parameter(vault, "accrue_interest_hour")),
        "minute": str(vault.modules["utils"].get_parameter(vault, "accrue_interest_minute")),
        "second": str(vault.modules["utils"].get_parameter(vault, "accrue_interest_second")),
        "start_date": str(effective_date),
    }
    if active is False:
        new_schedule["end_date"] = str(effective_date)

    vault.amend_schedule(
        event_type=ACCRUE_INTEREST,
        new_schedule=new_schedule,
    )


def _handle_repayment_day_change(
    vault,
    previous_values: Dict[str, Parameter],
    updated_values: Dict[str, Parameter],
    effective_date: datetime,
) -> None:
    if vault.modules["utils"].has_parameter_value_changed(
        "repayment_day",
        previous_values,
        updated_values,
    ):
        next_repayment_date = _calculate_next_repayment_date(vault, effective_date)

        last_repayment_day_schedule_event = vault.get_last_execution_time(
            event_type=REPAYMENT_DAY_SCHEDULE
        )
        if (
            last_repayment_day_schedule_event
            and next_repayment_date != last_repayment_day_schedule_event + timedelta(months=1)
        ):
            _schedule_repayment_day_change(vault, next_repayment_date.day, next_repayment_date)


def _handle_top_up(vault, updated_values: Dict[str, Any], effective_date: datetime) -> None:
    """
    Consolidates balances in principal tracking addresses at the end of previous
    loan/start of new loan
    Reschedules annual overpayment allowance check anchoring on new loan
    start date
    """
    if "loan_start_date" in updated_values:
        # currently, the contract can only set the date when top up loan wf is run
        # as the new loan start date, therefore using effective_date is
        # equivalent as the new loan_start_date
        # in the future, should the two diverge, this should be revisited so that correct
        # date and time components are used for end of life postings
        _handle_end_of_loan(vault, effective_date)


def _schedule_repayment_day_change(vault, repayment_day: int, effective_date: datetime):
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


def _get_initial_repayment_day_schedule(vault, repayment_day: int) -> Tuple[str, Dict[str, str]]:
    loan_start_date = vault.modules["utils"].get_parameter(vault, name="loan_start_date").date()
    loan_start_date_plus_month = loan_start_date + timedelta(months=1)

    repayment_day_schedule = {
        "day": str(repayment_day),
        "hour": str(vault.modules["utils"].get_parameter(vault, "repayment_hour")),
        "minute": str(vault.modules["utils"].get_parameter(vault, "repayment_minute")),
        "second": str(vault.modules["utils"].get_parameter(vault, "repayment_second")),
        "start_date": str(loan_start_date_plus_month),
    }

    if _is_no_repayment_loan(vault):
        repayment_day_schedule["end_date"] = str(loan_start_date_plus_month)

    return repayment_day_schedule


def _get_accrue_interest_schedule(vault) -> Tuple[str, Dict[str, str]]:
    loan_start_date = vault.modules["utils"].get_parameter(vault, "loan_start_date").date()
    loan_start_date_plus_day = loan_start_date + timedelta(days=1)
    accrue_interest_schedule = {
        "hour": str(vault.modules["utils"].get_parameter(vault, "accrue_interest_hour")),
        "minute": str(vault.modules["utils"].get_parameter(vault, "accrue_interest_minute")),
        "second": str(vault.modules["utils"].get_parameter(vault, "accrue_interest_second")),
        "start_date": str(loan_start_date_plus_day),
    }
    if _is_flat_interest_amortisation_method(vault):
        accrue_interest_schedule["end_date"] = str(loan_start_date_plus_day)

    return accrue_interest_schedule


def _get_balloon_payment_schedule(vault) -> Tuple[str, Dict[str, str]]:
    """
    Defines the initial balloon payment schedule:
        1. No Repayment balloon loan, the balloon payment event will always
        be on the theoretical last repayment day (i.e. term -1 from the initial repayment day event)
        2. Any other balloon loan, the schedule is created in a 'disabled' state, it will be amended
        by the final repayment event so that it runs in balloon_payment_days_delta days from the
        final repayment event.
    """
    loan_start_date = balloon_payment_start_date = (
        vault.modules["utils"].get_parameter(vault, "loan_start_date").date()
    )

    if _is_no_repayment_loan(vault):
        total_term = vault.modules["utils"].get_parameter(vault, "total_term")
        balloon_payment_start_date = loan_start_date + timedelta(months=total_term)

        disable_schedule = False

    else:
        balloon_payment_start_date = loan_start_date + timedelta(days=1)
        disable_schedule = True

    schedule = {
        "year": str(balloon_payment_start_date.year),
        "month": str(balloon_payment_start_date.month),
        "day": str(balloon_payment_start_date.day),
        "hour": str(vault.modules["utils"].get_parameter(vault, "repayment_hour")),
        "minute": str(vault.modules["utils"].get_parameter(vault, "repayment_minute")),
        "second": str(vault.modules["utils"].get_parameter(vault, "repayment_second")),
    }

    if disable_schedule:
        schedule["start_date"] = str(balloon_payment_start_date)
        schedule["end_date"] = str(balloon_payment_start_date)

    return (BALLOON_PAYMENT_SCHEDULE, schedule)


# Balance helper functions
def _get_effective_balance_by_address(vault, address: str, timestamp: datetime = None) -> Decimal:
    return vault.modules["utils"].get_balance_sum(vault, [address], timestamp)


def _get_additional_interest(vault, effective_date: datetime) -> Decimal:
    """
    Retrieves any additional interest by getting the balance of the ACCRUED_EXPECTED_INTEREST
    address, at the previous repayment day event execution time,
    or one month prior to the effective date if there has not been a repayment day event.
    If there are any additional days since the account creation, then the days at the
    beginning of the period are considered extra and hence will have interest accrued here.
    """
    last_repayment_day_schedule_event = vault.get_last_execution_time(
        event_type=REPAYMENT_DAY_SCHEDULE
    )

    previous_month = (
        last_repayment_day_schedule_event + timedelta(microseconds=2)
        if last_repayment_day_schedule_event
        else effective_date - timedelta(months=1)
    )

    return _get_effective_balance_by_address(vault, ACCRUED_EXPECTED_INTEREST, previous_month)


def _get_accrued_interest(vault, timestamp: datetime = None) -> Decimal:
    return vault.modules["utils"].get_balance_sum(vault, [ACCRUED_INTEREST], timestamp)


def _get_due_principal(vault, timestamp: datetime = None) -> Decimal:
    return vault.modules["utils"].get_balance_sum(vault, [PRINCIPAL_DUE], timestamp)


def _get_outstanding_actual_principal(vault, timestamp: datetime = None) -> Decimal:
    return vault.modules["utils"].get_balance_sum(vault, REMAINING_PRINCIPAL, timestamp)


def _get_capital_for_penalty_accrual(vault, timestamp: datetime = None) -> Decimal:
    """
    Returns the appropriate capital balance over which penalty interest accrues
    """
    penalty_compounds_overdue_interest = vault.modules["utils"].get_parameter(
        vault, "penalty_compounds_overdue_interest", union=True
    )
    capitalised_overdues = (
        OVERDUE_ADDRESSES
        if penalty_compounds_overdue_interest.upper() == "TRUE"
        else [PRINCIPAL_OVERDUE]
    )
    return vault.modules["utils"].get_balance_sum(vault, capitalised_overdues, timestamp)


def _get_late_payment_balance(vault, timestamp: datetime = None) -> Decimal:
    return vault.modules["utils"].get_balance_sum(vault, LATE_PAYMENT_ADDRESSES, timestamp)


def _get_all_outstanding_debt(vault, timestamp: datetime = None) -> Decimal:
    fulfillment_precision = vault.modules["utils"].get_parameter(
        vault, name="fulfillment_precision"
    )
    return _round_to_precision(
        fulfillment_precision,
        vault.modules["utils"].get_balance_sum(
            vault,
            ALL_ADDRESSES,
            timestamp,
        ),
    )


def _sum_outstanding_dues(vault, timestamp: datetime = None) -> Decimal:
    return vault.modules["utils"].get_balance_sum(vault, REPAYMENT_ORDER, timestamp)


def _get_expected_emi(vault, effective_date: datetime) -> Decimal:
    emi = _get_effective_balance_by_address(vault, EMI_ADDRESS)
    if emi == 0 and not _is_no_repayment_loan(vault):
        next_repayment_date = _calculate_next_repayment_date(vault, effective_date)
        amount_due = _calculate_monthly_due_amounts(vault, next_repayment_date)
        emi = amount_due.get("emi", Decimal("0")) if amount_due is not None else Decimal("0")

    return emi


# Flag helper functions
def _get_flag_duration_in_months(
    vault, effective_date: datetime, flag_name: str, include_active: bool = False
) -> int:
    """
    Return the number of total months a flag has been active for in the past.
    If include_active is True, any flags that are currently active will be counted,
    as number of months from flag activation timestamp until effective_date.
    Otherwise, flags that are currently active will be discounted.
    """
    total_duration = 0
    start_timestamp = None
    for timestamp, flag_applied in vault.get_flag_timeseries(flag=flag_name).all():
        timestamp = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        if flag_applied is True and timestamp < effective_date:
            start_timestamp = timestamp
        elif flag_applied is False and start_timestamp and timestamp <= effective_date:
            td = timedelta(timestamp, start_timestamp)
            duration = td.years * 12 + td.months
            total_duration += duration
            start_timestamp = None
    if include_active and start_timestamp is not None:
        # The flag is currently active
        td = timedelta(effective_date, start_timestamp)
        rounded_month = 1 if (td.days or td.minutes or td.seconds or td.microseconds) else 0
        duration = td.years * 12 + td.months + rounded_month
        total_duration += duration
    return total_duration


# Generic helper functions
def _is_accrue_interest_on_due_principal(vault) -> bool:
    accrue_interest_on_due_principal = vault.modules["utils"].get_parameter(
        vault, "accrue_interest_on_due_principal", union=True
    )
    return accrue_interest_on_due_principal.upper() == "TRUE"


def _is_declining_principal_amortisation_method(vault) -> bool:
    return (
        vault.modules["utils"].get_parameter(vault, "amortisation_method", union=True).upper()
        == "DECLINING_PRINCIPAL"
    )


def _is_interest_only_amortisation_method(vault) -> bool:
    return (
        vault.modules["utils"].get_parameter(vault, "amortisation_method", union=True).upper()
        == "INTEREST_ONLY"
    )


def _is_minimum_repayment_amortisation_method(vault) -> bool:
    return (
        vault.modules["utils"].get_parameter(vault, "amortisation_method", union=True).upper()
        == "MINIMUM_REPAYMENT_WITH_BALLOON_PAYMENT"
    )


def _should_handle_balloon_payment(vault, effective_date: datetime) -> bool:
    """
    Check whether the repayment event should be treated as the balloon
    payment event, this is true if:
        it is theoretical final repayment event and either the
        balloon payment days delta has been omitted from the instance params
        or it is equal to 0
    """
    balloon_payment_delta = vault.modules["utils"].get_parameter(
        vault, name="balloon_payment_days_delta", optional=True
    )

    return _is_last_payment_date(vault, effective_date) and (
        balloon_payment_delta is None or int(balloon_payment_delta) == 0
    )


def _is_flat_interest_amortisation_method(vault) -> bool:
    return vault.modules["utils"].get_parameter(vault, "amortisation_method", union=True) in [
        "flat_interest",
        "rule_of_78",
    ]


def _is_monthly_rest_interest(vault) -> bool:
    interest_accrual_rest_type = vault.modules["utils"].get_parameter(
        vault, "interest_accrual_rest_type", union=True
    )

    return interest_accrual_rest_type.upper() == "MONTHLY"


def _get_balance_date_for_interest_accrual(vault) -> datetime:
    last_repayment_due_date = vault.get_last_execution_time(event_type=REPAYMENT_DAY_SCHEDULE)
    # If there hasn't been a repayment event, use balances from loan start date
    if last_repayment_due_date is None:
        last_repayment_due_date = vault.modules["utils"].get_parameter(
            vault, name="loan_start_date"
        )
    # Effective date of the transfer postings is 2 microseconds after repayment due event
    return (
        last_repayment_due_date + timedelta(microseconds=2)
        if _is_monthly_rest_interest(vault)
        else None
    )


def _has_schedule_run_today(vault, effective_date: datetime, schedule_name: str) -> bool:
    last_run_time = vault.get_last_execution_time(event_type=schedule_name)
    if last_run_time:
        return True if effective_date.date() == last_run_time.date() else False
    return False


def _is_rule_of_78_amortisation_method(vault) -> bool:
    return (
        vault.modules["utils"].get_parameter(vault, "amortisation_method", union=True).upper()
        == "RULE_OF_78"
    )


def _is_capitalise_penalty_interest(vault) -> bool:
    capitalise_penalty_interest = vault.modules["utils"].get_parameter(
        vault, "capitalise_penalty_interest", union=True
    )

    return capitalise_penalty_interest.upper() == "TRUE"


def _is_capitalise_late_repayment_fee(vault) -> bool:
    capitalise_late_repayment_fee = vault.modules["utils"].get_parameter(
        vault, "capitalise_late_repayment_fee", union=True
    )

    return capitalise_late_repayment_fee.upper() == "TRUE"


def _get_P_with_upfront_fee(vault) -> Decimal:
    P = vault.modules["utils"].get_parameter(vault, "principal")
    amortise_upfront_fee = vault.modules["utils"].get_parameter(
        vault, "amortise_upfront_fee", union=True
    )
    upfront_fee = vault.modules["utils"].get_parameter(vault, "upfront_fee")

    return P + upfront_fee if amortise_upfront_fee.upper() == "TRUE" and upfront_fee > 0 else P


def _get_posting_amount(posting: PostingInstruction, include_pending_out: bool = True) -> Decimal:
    posting_amount = posting.balances()[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, posting.denomination, Phase.COMMITTED)
    ].net
    if include_pending_out:
        posting_amount += posting.balances()[
            (DEFAULT_ADDRESS, DEFAULT_ASSET, posting.denomination, Phase.PENDING_OUT)
        ].net

    return Decimal(posting_amount)


def _is_balloon_payment_loan(vault) -> bool:
    amortisation_method = vault.modules["utils"].get_parameter(
        vault, name="amortisation_method", union=True
    )
    return amortisation_method in [
        "interest_only",
        "no_repayment",
        "minimum_repayment_with_balloon_payment",
    ]


def _is_no_repayment_loan(vault) -> bool:
    return (
        vault.modules["utils"].get_parameter(vault, name="amortisation_method", union=True).upper()
        == "NO_REPAYMENT"
    )


def _is_no_repayment_loan_interest_to_be_capitalised(vault, effective_date: datetime) -> bool:
    """
    Determine whether interest needs to be capitalised for a no_repayment
    amortised loan. Interest should be capitalised if:
    the loan is a no_repayment amortised loan AND capitalise_no_repayment_accrued_interest
    is True, if the above condition is met we capitalise interest under the following
    scenarios:
        1. is monthly capitalisation AND effective_date.day is equal to
        loan_start_date.day() (therefore we capitalise the interest monthly)
        2. is daily capitalisation (therefore we capitalise the interest daily)

    """
    capitalise_no_repayment_loan = (
        vault.modules["utils"]
        .get_parameter(vault, name="capitalise_no_repayment_accrued_interest", union=True)
        .upper()
    )
    loan_start_date = vault.modules["utils"].get_parameter(vault=vault, name="loan_start_date")
    loan_start_day = loan_start_date.day

    valid_day_to_capitalise = True

    if capitalise_no_repayment_loan == "MONTHLY":
        last_day_in_current_month = calendar.monthrange(effective_date.year, effective_date.month)[
            1
        ]
        valid_day_to_capitalise = (
            loan_start_day >= 29
            and last_day_in_current_month < loan_start_day
            and effective_date.day == last_day_in_current_month
        ) or effective_date.day == loan_start_day

    return (
        _is_no_repayment_loan(vault)
        and capitalise_no_repayment_loan != "NO_CAPITALISATION"
        and valid_day_to_capitalise is True
    )


def _should_enable_balloon_payment_schedule(vault, effective_date: datetime) -> bool:
    """
    checks whether the balloon payment schedule needs to be enabled on a balloon payment
    loan, the conditions for this are:
        1. It is the theoretical final repayment event and balloon_payment_days_delta is defined
        and greater than zero

    note that for a no_repayment balloon loan the balloon payment schedule is enabled by default
    """
    balloon_payment_delta = vault.modules["utils"].get_parameter(
        vault, name="balloon_payment_days_delta", optional=True
    )
    return (
        not _is_no_repayment_loan(vault)
        and _is_last_payment_date(vault, effective_date)
        and balloon_payment_delta is not None
        and int(balloon_payment_delta) != 0
    )


def _replace_repayment_day_schedule_with_balloon_payment(vault, effective_date: datetime) -> None:

    balloon_payment_delta = vault.modules["utils"].get_parameter(
        vault, name="balloon_payment_days_delta", optional=True
    )
    balloon_schedule_start_date = effective_date.date() + timedelta(days=int(balloon_payment_delta))
    vault.amend_schedule(
        event_type=BALLOON_PAYMENT_SCHEDULE,
        new_schedule={
            "year": str(balloon_schedule_start_date.year),
            "month": str(balloon_schedule_start_date.month),
            "day": str(balloon_schedule_start_date.day),
            "hour": str(vault.modules["utils"].get_parameter(vault, "repayment_hour")),
            "minute": str(vault.modules["utils"].get_parameter(vault, "repayment_minute")),
            "second": str(vault.modules["utils"].get_parameter(vault, "repayment_second")),
        },
    )
    # disable the repayment day schedule to prevent it from running
    vault.amend_schedule(
        event_type=REPAYMENT_DAY_SCHEDULE,
        new_schedule={
            "hour": str(vault.modules["utils"].get_parameter(vault, "repayment_hour")),
            "minute": str(vault.modules["utils"].get_parameter(vault, "repayment_minute")),
            "second": str(vault.modules["utils"].get_parameter(vault, "repayment_second")),
            "start_date": str(effective_date.date()),
            "end_date": str(effective_date.date()),
        },
    )


def _get_expected_balloon_payment_amount(vault, effective_date: datetime) -> Decimal:
    """
    Returns the expected balloon payment amount for a balloon payment loan, else returns Decimal(0)

    This assumes that the interest rate remains the same throughout the lifetime of the loan

    Amortisation Formula:
        EMI = (P-(L/(1+R)^(N)))*R*(((1+R)^N)/((1+R)^N-1))

    Re-arranging for L:
        L = (1+R)^(N)*(P - EMI/R) + EMI/R

    P is principal
    R is the monthly interest rate
    N is total term
    L is the lump sum
    """

    if _is_balloon_payment_loan(vault):
        if _is_no_repayment_loan(vault) or _is_interest_only_amortisation_method(vault):
            return _get_outstanding_actual_principal(vault)

        elif _is_minimum_repayment_amortisation_method(vault):
            # it is therefore a minimum repayment balloon loan
            balloon_payment_amount = vault.modules["utils"].get_parameter(
                vault, "balloon_payment_amount", optional=True
            )
            emi = vault.modules["utils"].get_parameter(vault, "balloon_emi_amount", optional=True)
            if balloon_payment_amount is not None:
                # we do not allow overpayments for minimum repayment the balloon payment
                # amount will remain fixed so we can just return the
                # balloon_payment_amount parameter if it's set
                return balloon_payment_amount

            elif emi is not None:
                # the emi is predefined so we calculate the balloon payment amount by
                # rearranging the amortisation formula
                total_term = vault.modules["utils"].get_parameter(vault, "total_term")
                principal = vault.modules["utils"].get_parameter(vault, "principal")
                monthly_interest_rate = _get_monthly_interest_rate(
                    _get_interest_rate(vault, effective_date)
                )
                fulfillment_precision = vault.modules["utils"].get_parameter(
                    vault, "fulfillment_precision"
                )

                return _round_to_precision(
                    fulfillment_precision,
                    (1 + monthly_interest_rate) ** (total_term)
                    * (principal - emi / monthly_interest_rate)
                    + emi / monthly_interest_rate,
                )

    return Decimal("0")


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
