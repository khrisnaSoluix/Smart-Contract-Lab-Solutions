# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
display_name = "Credit Card"
api = "3.8.0"
version = "4.4.0"
tside = Tside.ASSET
supported_denominations = ["GBP"]

EVENT_ANNUAL_FEE = "ANNUAL_FEE"
EVENT_ACCRUE = "ACCRUE_INTEREST"
EVENT_PDD = "PAYMENT_DUE"
EVENT_SCOD = "STATEMENT_CUT_OFF"

event_types = [
    EventType(name=EVENT_ACCRUE, scheduler_tag_ids=["CREDIT_CARD_ACCRUE_INTEREST_AST"]),
    EventType(name=EVENT_SCOD, scheduler_tag_ids=["CREDIT_CARD_STATEMENT_CUT_OFF_AST"]),
    EventType(name=EVENT_ANNUAL_FEE, scheduler_tag_ids=["CREDIT_CARD_ANNUAL_FEE_AST"]),
    EventType(name=EVENT_PDD, scheduler_tag_ids=["CREDIT_CARD_PAYMENT_DUE_AST"]),
]

event_types_groups = [
    EventTypesGroup(name="GROUP_INTEREST", event_types_order=[EVENT_ACCRUE, EVENT_PDD, EVENT_SCOD])
]

####################################################################################################

# Commonly used abbreviations
# CTI       Client Transaction Id
# MAD       Minimum Amount Due
# Off-BS    Off-Balance Sheet
# PDD       Payment Due Date
# SCOD      Statement Cut Off Date
# TXN       Transaction
#
#
# Balance direction
#
# PURCHASE |
# INTEREST | - positive for money spent/owed by the customer
# FEES     |
#
# DEPOSIT - positive for repayments made by the customer
#
# AVAILABLE_BALANCE positive for balance available to be spent, negative when overlimit
#
# MAD - positive
#
# FULL_OUTSTANDING_BALANCE | - positive for money owed by the customer
# OUTSTANDING_BALANCE      |

LOCAL_UTC_OFFSET = 0  # +ve if ahead of UTC, -ve if behind UTC

# Transactions and charges can be in one of the following statuses
BILLED = "BILLED"
CHARGED = "CHARGED"
AUTH = "AUTH"
UNPAID = "UNPAID"
UNCHARGED = "UNCHARGED"

# Principal balances per spending type
CHARGED_BALANCE_STATES = [
    BILLED,  # Balance that was billed in the latest statement
    CHARGED,  # Balance that has been charged but not yet billed
    UNPAID,  # Balance that was billed in previous statements
]

ACCRUAL_BALANCE_STATES = CHARGED_BALANCE_STATES

# Sub principal balances per type which construct statement balance per type
# Fees/Interest cannot be overlimit
STATEMENT_BALANCE_STATES = [BILLED, UNPAID]

PRINCIPAL = "PRINCIPAL"
INTEREST = "INTEREST"
BANK_CHARGE = "BANK_CHARGE"
FEES = "FEES"
OVERDUE = "OVERDUE"
CHARGED_INTEREST = INTEREST + "_" + CHARGED
UNCHARGED_INTEREST_BALANCE = INTEREST + "_" + UNCHARGED
BILLED_INTEREST = INTEREST + "_" + BILLED
UNPAID_INTEREST = INTEREST + "_" + UNPAID
CHARGED_FEES = FEES + "_" + CHARGED
BILLED_FEES = FEES + "_" + BILLED
UNPAID_FEES = FEES + "_" + UNPAID

BANK_CHARGES = [INTEREST, FEES]

DEFAULT_TXN_TYPE = "purchase"

REPAYMENT_HIERARCHY = [
    # Process all statuses per transaction type, cycling through transaction type by decreasing AER
    dict(repayment_type=BANK_CHARGE, bank_charge_type=INTEREST, statuses=[UNPAID]),
    dict(repayment_type=BANK_CHARGE, bank_charge_type=INTEREST, statuses=[BILLED]),
    dict(repayment_type=BANK_CHARGE, bank_charge_type=FEES, statuses=[UNPAID]),
    dict(repayment_type=BANK_CHARGE, bank_charge_type=FEES, statuses=[BILLED]),
    dict(repayment_type=PRINCIPAL, statuses=[UNPAID, BILLED]),
    dict(repayment_type=PRINCIPAL, statuses=[CHARGED]),
    dict(repayment_type=BANK_CHARGE, bank_charge_type=INTEREST, statuses=[CHARGED]),
    dict(repayment_type=BANK_CHARGE, bank_charge_type=FEES, statuses=[CHARGED]),
]

PRE_SCOD = "PRE_SCOD"
POST_SCOD = "POST_SCOD"
ACCRUAL_TYPES = [PRE_SCOD, POST_SCOD]

# Balance addresses
INTEREST_FREE_PERIOD = "INTEREST_FREE_PERIOD"
INTEREST_FREE_PERIOD_UNCHARGED_INTEREST_BALANCE = (
    f"{INTEREST_FREE_PERIOD}_{UNCHARGED_INTEREST_BALANCE}"
)
AVAILABLE_BALANCE = "AVAILABLE_BALANCE"
DEPOSIT_BALANCE = "DEPOSIT"
FULL_OUTSTANDING_BALANCE = "FULL_OUTSTANDING_BALANCE"
INTERNAL_BALANCE = "INTERNAL"
MAD_BALANCE = "MAD_BALANCE"
OUTSTANDING_BALANCE = "OUTSTANDING_BALANCE"
REVOLVER_BALANCE = "REVOLVER"
STATEMENT_BALANCE = "STATEMENT_BALANCE"
TRACK_STATEMENT_REPAYMENTS = "TOTAL_REPAYMENTS_LAST_STATEMENT"

address_details = [
    AddressDetails(
        account_address=AVAILABLE_BALANCE,
        description="Remaining credit-limit to spend, excluding any over-limit facilities",
        tags=[],
    ),
    AddressDetails(
        account_address=DEPOSIT_BALANCE,
        description="Tracks repayments into the account",
        tags=[],
    ),
    AddressDetails(
        account_address=FULL_OUTSTANDING_BALANCE,
        description="Outstanding balance + charged interest",
        tags=[],
    ),
    AddressDetails(
        account_address=INTERNAL_BALANCE,
        description="Used for double-entry bookkeeping when making postings to adjust other "
        "balances (unless there is a defined internal account for the posting).",
        tags=[],
    ),
    AddressDetails(
        account_address=MAD_BALANCE,
        description="Minimum amount that the customer must repay before the end of the payment due "
        "date (incl grace) to avoid becoming delinquent",
        tags=[],
    ),
    AddressDetails(
        account_address=OUTSTANDING_BALANCE,
        description="The sum of all outstanding settled transactions, charged/billed fees and "
        "billed interest",
        tags=[],
    ),
    AddressDetails(
        account_address=REVOLVER_BALANCE,
        description="Defines whether the account is revolver or not. Set to 1 if revolver and 0 "
        "if transactor.",
        tags=[],
    ),
    AddressDetails(
        account_address=STATEMENT_BALANCE,
        description="Amount billed to the client for the statement. Note this is equivalent to "
        "outstanding/full outstanding at the time of statement processing, as all charged "
        "transactions and bank charges will have been billed.",
        tags=[],
    ),
    AddressDetails(
        account_address=TRACK_STATEMENT_REPAYMENTS,
        description="Sum of all repayments that were made during a statement cycle. This is reset "
        " to 0 at the end of each SCOD",
        tags=[],
    ),
]

# Fee Types
ANNUAL_FEE = "ANNUAL_FEE"
LATE_REPAYMENT_FEE = "LATE_REPAYMENT_FEE"
OVERLIMIT_FEE = "OVERLIMIT_FEE"
INTERNAL_FEE_TYPES = [ANNUAL_FEE, LATE_REPAYMENT_FEE, OVERLIMIT_FEE]
# no constant for transaction type fees as name is constructed dynamically using transaction type

# Parameter names
ACCOUNT_CLOSURE_FLAGS = "account_closure_flags"
ACCOUNT_WRITE_OFF_FLAGS = "account_write_off_flags"
ACCRUAL_BLOCKING_FLAGS = "accrual_blocking_flags"
ACCRUE_INTEREST_FROM_TXN_DAY = "accrue_interest_from_txn_day"
ACCRUE_INTEREST_ON_UNPAID_INTEREST = "accrue_interest_on_unpaid_interest"
ACCRUE_INTEREST_ON_UNPAID_FEES = "accrue_interest_on_unpaid_fees"
INTEREST_ON_FEES_INTERNAL_ACCOUNTS_MAP = "interest_on_fees_internal_accounts_map"
ALLOWED_DAYS_AFTER_OPENING = "allowed_days_after_opening"
ANNUAL_FEE_INTERNAL_ACCOUNTS = "annual_fee_internal_accounts"
ANNUAL_FEE_PARAM = "annual_fee"
APR = "annual_percentage_rate"
BASE_INTEREST_RATES = "base_interest_rates"
BILLED_TO_UNPAID_TRANSFER_BLOCKING_FLAGS = "billed_to_unpaid_transfer_blocking_flags"
CREDIT_LIMIT = "credit_limit"
DENOMINATION = "denomination"
DISPUTE_FEE_INTERNAL_ACCOUNTS = "dispute_fee_internal_accounts"
DISPUTE_FEE_PARAM = "dispute_fee"
EXTERNAL_FEE_INTERNAL_ACCOUNTS = "external_fee_internal_accounts"
EXTERNAL_FEE_TYPES = "external_fee_types"
INTEREST_FREE_EXPIRY = "interest_free_expiry"
INTEREST_WRITE_OFF_INTERNAL_ACCOUNT = "interest_write_off_internal_account"
LATE_REPAYMENT_FEE_INTERNAL_ACCOUNTS = "late_repayment_fee_internal_accounts"
LATE_REPAYMENT_FEE_PARAM = "late_repayment_fee"
MAD = "minimum_amount_due"
MAD_AS_STATEMENT_FLAGS = "mad_as_full_statement_flags"
MAD_EQUAL_TO_ZERO_FLAGS = "mad_equal_to_zero_flags"
MINIMUM_PERCENTAGE_DUE = "minimum_percentage_due"
OFF_BALANCE_SHEET_CONTRA_INTERNAL_ACCOUNT = "off_balance_sheet_contra_internal_account"
OTHER_LIABILITY_INTERNAL_ACCOUNT = "other_liability_internal_account"
OVERDUE_AMOUNT_BLOCKING_FLAGS = "overdue_amount_blocking_flags"
OVERLIMIT = "overlimit"
OVERLIMIT_FEE_PARAM = "overlimit_fee"
OVERLIMIT_FEE_INTERNAL_ACCOUNTS = "overlimit_fee_internal_accounts"
OVERLIMIT_OPT_IN = "overlimit_opt_in"
PAYMENT_DUE_PERIOD = "payment_due_period"
PRINCIPAL_WRITE_OFF_INTERNAL_ACCOUNT = "principal_write_off_internal_account"
REVOCABLE_COMMITMENT_INTERNAL_ACCOUNT = "revocable_commitment_internal_account"
TXN_CODE_TO_TYPE_MAP = "transaction_code_to_type_map"
TXN_APR = "transaction_annual_percentage_rate"
TXN_BASE_INTEREST_RATES = "transaction_base_interest_rates"
TXN_INTEREST_FREE_EXPIRY = "transaction_interest_free_expiry"
TXN_REFS = "transaction_references"
TXN_TYPE_LIMITS = "transaction_type_limits"
TXN_TYPE_FEES = "transaction_type_fees"
TXN_TYPE_FEES_INTERNAL_ACCOUNTS_MAP = "transaction_type_fees_internal_accounts_map"
TXN_TYPE_INTERNAL_ACCOUNTS_MAP = "transaction_type_internal_accounts_map"
TXN_TYPE_INTEREST_INTERNAL_ACCOUNTS_MAP = "transaction_type_interest_internal_accounts_map"
TXN_TYPES = "transaction_types"
ACCRUAL_SCHEDULE_HOUR = "accrual_schedule_hour"
ACCRUAL_SCHEDULE_MINUTE = "accrual_schedule_minute"
ACCRUAL_SCHEDULE_SECOND = "accrual_schedule_second"
SCOD_SCHEDULE_HOUR = "scod_schedule_hour"
SCOD_SCHEDULE_MINUTE = "scod_schedule_minute"
SCOD_SCHEDULE_SECOND = "scod_schedule_second"
PDD_SCHEDULE_HOUR = "pdd_schedule_hour"
PDD_SCHEDULE_MINUTE = "pdd_schedule_minute"
PDD_SCHEDULE_SECOND = "pdd_schedule_second"
ANNUAL_FEE_SCHEDULE_HOUR = "annual_fee_schedule_hour"
ANNUAL_FEE_SCHEDULE_MINUTE = "annual_fee_schedule_minute"
ANNUAL_FEE_SCHEDULE_SECOND = "annual_fee_schedule_second"

# Event Types - Beware that we cannot use constants in @require hooks, so check these too
EVENT_ANNUAL_FEE = "ANNUAL_FEE"
EVENT_ACCRUE = "ACCRUE_INTEREST"
EVENT_PDD = "PAYMENT_DUE"
EVENT_SCOD = "STATEMENT_CUT_OFF"

# Instruction Detail keys
TXN_CODE = "transaction_code"
FEE_TYPE = "fee_type"

# Workflows
EXPIRE_INTEREST_FREE_PERIODS_WORKFLOW = "CREDIT_CARD_EXPIRE_INTEREST_FREE_PERIODS"
PUBLISH_STATEMENT_DATA_WORKFLOW = "CREDIT_CARD_PUBLISH_STATEMENT_DATA"

AGGREGATE_BALANCE_DEFINITIONS = {
    AVAILABLE_BALANCE: {
        PRINCIPAL: [AUTH, CHARGED, BILLED, UNPAID],
        INTEREST: [BILLED, UNPAID],
        FEES: [CHARGED, BILLED, UNPAID],
    },
    OUTSTANDING_BALANCE: {
        PRINCIPAL: [CHARGED, BILLED, UNPAID],
        INTEREST: [BILLED, UNPAID],
        FEES: [CHARGED, BILLED, UNPAID],
    },
    FULL_OUTSTANDING_BALANCE: {
        PRINCIPAL: [CHARGED, BILLED, UNPAID],
        INTEREST: [CHARGED, BILLED, UNPAID],
        FEES: [CHARGED, BILLED, UNPAID],
    },
}

MoneyShape = NumberShape(kind=NumberKind.MONEY, min_value=0, step=0.01)

parameters = [
    Parameter(
        name=DENOMINATION,
        shape=DenominationShape,
        level=Level.TEMPLATE,
        description="Default denomination.",
        display_name="Default denomination for the contract.",
        default_value="GBP",
    ),
    Parameter(
        name=OVERLIMIT,
        level=Level.INSTANCE,
        description="Additional limit on top of credit limit available to spend. "
        "Might involve fees.",
        display_name="Additional limit on top of credit limit",
        default_value=OptionalValue(Decimal(0)),
        shape=OptionalShape(MoneyShape),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=OVERLIMIT_OPT_IN,
        level=Level.INSTANCE,
        description="Indicates whether the customer has opted in to the overlimit facility. If"
        ' "True" the customer can exceed the credit limit by the overlimit for regular'
        " transactions and stand-in/offline transactions. Otherwise, the customer can "
        "only exceed the credit limit for stand-in/offline transactions.",
        display_name="Overlimit Opt In",
        default_value=OptionalValue("False"),
        shape=OptionalShape(StringShape),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=CREDIT_LIMIT,
        level=Level.INSTANCE,
        description="Credit limit",
        display_name="Credit limit",
        default_value=Decimal(0),
        shape=MoneyShape,
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=TXN_CODE_TO_TYPE_MAP,
        level=Level.TEMPLATE,
        description="Map of transaction codes to transaction types" " (map format - encoded json).",
        display_name="Map of transaction types",
        shape=StringShape,
        default_value=json_dumps(
            {
                "xxx": "purchase",
                "aaa": "cash_advance",
                "cc": "transfer",
                "bb": "balance_transfer",
            }
        ),
    ),
    Parameter(
        name=TXN_TYPES,
        level=Level.TEMPLATE,
        description="Map of maps of supported transaction types for the account, with any "
        "non-default parameters specified. All default to False. "
        "(map format - encoded json).",
        display_name="Account supported transaction types",
        shape=StringShape,
        default_value=json_dumps(
            {
                "purchase": {},
                "cash_advance": {"charge_interest_from_transaction_date": "True"},
                "transfer": {},
                "balance_transfer": {
                    "charge_interest_from_transaction_date": "True",
                },
            }
        ),
    ),
    Parameter(
        name=TXN_REFS,
        level=Level.INSTANCE,
        description="Map of lists of Transaction types and their associated references "
        "(map format - encoded json).",
        display_name="Transaction References",
        shape=StringShape,
        default_value=json_dumps({"balance_transfer": ["REF1", "REF2"]}),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=TXN_TYPE_LIMITS,
        level=Level.INSTANCE,
        description="Map of limits per transaction type (map format - encoded json). A "
        "transaction must respect overall limits and transaction type limits. "
        "For credit limit checks the sum of authorised and outstanding amounts for a "
        'given transaction type can be subject to an absolute limit, using the "flat" key, '
        'and/or a relative limit with respect to the credit limit, using the "percentage" key. '
        "If both are specified, the lowest of the two is applied. If either is "
        "missing it is assumed to not apply. If a transaction type has no entry, "
        'no specific limits apply. "allowed_days_after_opening" is a time-based check '
        "that permits transactions only in a window after the account is activated.",
        display_name="Limits per transaction type",
        shape=StringShape,
        default_value=json_dumps(
            {
                "cash_advance": {"flat": "250", "percentage": "0.01"},
                "balance_transfer": {"allowed_days_after_opening": "14"},
            }
        ),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=TXN_TYPE_FEES,
        level=Level.INSTANCE,
        description="Map of map of fees per transaction type (map format - encoded json). Allows a "
        '"over_deposit_only", "percentage_fee" and "flat_fee" to be specified'
        "for transactions of the given type. The highest fee will be selected based on "
        "the transaction amount and charged on the next statement. If a transaction "
        'type does not have an entry, no fees apply. If "over_deposit_only" is '
        "set to True, the associated type will only charge a fee if the transaction "
        "amount exceeds the deposit balance",
        display_name="Fees per transaction type",
        shape=StringShape,
        default_value=json_dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.01",
                    "flat_fee": "10",
                },
                "transfer": {
                    "over_deposit_only": "True",
                    "percentage_fee": "0.025",
                    "flat_fee": "25",
                    "combine": "True",
                    "fee_cap": "100",
                },
                "balance_transfer": {
                    "over_deposit_only": "True",
                    "percentage_fee": "0.025",
                    "flat_fee": "25",
                    "combine": "True",
                    "fee_cap": "100",
                },
            }
        ),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=TXN_TYPE_FEES_INTERNAL_ACCOUNTS_MAP,
        description="Internal accounts used for Credit Card Transaction Type Fees",
        display_name="Map of transaction type to internal account id for transaction type fee"
        " purposes (map format - encoded json).",
        level=Level.TEMPLATE,
        shape=StringShape,
        default_value=json_dumps(
            {
                "cash_advance": {
                    "loan": "FEE_LOAN",
                    "income": "FEE_INCOME",
                },
                "purchase": {
                    "loan": "FEE_LOAN",
                    "income": "FEE_INCOME",
                },
                "transfer": {
                    "loan": "FEE_LOAN",
                    "income": "FEE_INCOME",
                },
                "balance_transfer": {
                    "loan": "FEE_LOAN",
                    "income": "FEE_INCOME",
                },
            }
        ),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=TXN_TYPE_INTEREST_INTERNAL_ACCOUNTS_MAP,
        level=Level.TEMPLATE,
        description="Map of transaction type to internal account id for interest purposes. Contains"
        "both Accrued Interest Receivable (AIR) and Interest Income accounts for each"
        " transaction type (map format - encoded json).",
        display_name="Internal Accounts per transaction type",
        shape=StringShape,
        default_value=json_dumps(
            {
                "cash_advance": {"air": "INTEREST_AIR", "income": "INTEREST_INCOME"},
                "purchase": {"air": "INTEREST_AIR", "income": "INTEREST_INCOME"},
                "transfer": {"air": "INTEREST_AIR", "income": "INTEREST_INCOME"},
                "balance_transfer": {
                    "air": "INTEREST_AIR",
                    "income": "INTEREST_INCOME",
                },
            }
        ),
    ),
    Parameter(
        name=TXN_TYPE_INTERNAL_ACCOUNTS_MAP,
        level=Level.TEMPLATE,
        description="Map of transaction type to internal loan account id for principal spend"
        " purposes"
        "(map format - encoded json).",
        display_name="Internal Accounts per transaction type",
        shape=StringShape,
        default_value=json_dumps(
            {
                "purchase": "LOAN",
                "cash_advance": "LOAN",
                "transfer": "LOAN",
                "balance_transfer": "LOAN",
            }
        ),
    ),
    Parameter(
        name=OFF_BALANCE_SHEET_CONTRA_INTERNAL_ACCOUNT,
        level=Level.TEMPLATE,
        description="Off Balance Sheet Contra Internal Account Id",
        display_name="Off Balance Sheet Contra Internal Account Id",
        shape=StringShape,
        default_value="OTHER_LIABILITY",
    ),
    Parameter(
        name=REVOCABLE_COMMITMENT_INTERNAL_ACCOUNT,
        level=Level.TEMPLATE,
        description="Revocable Commitment Internal Account Id",
        display_name="Revocable Commitment Internal Account Id",
        shape=StringShape,
        default_value="REVOCABLE_COMMITMENT",
    ),
    Parameter(
        name=OTHER_LIABILITY_INTERNAL_ACCOUNT,
        level=Level.TEMPLATE,
        description="Other Liability Internal Account Id",
        display_name="Other Liability Internal Account Id",
        shape=StringShape,
        default_value="OTHER_LIABILITY",
    ),
    Parameter(
        name=BASE_INTEREST_RATES,
        level=Level.TEMPLATE,
        description="Per annum gross interest rate per transaction type "
        "(map format - encoded json)",
        display_name="Per annum gross interest rate per transaction type",
        shape=StringShape,
        default_value=json_dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0.02",
                "transfer": "0.03",
                "fees": "0.01",
            }
        ),
    ),
    Parameter(
        name=ACCRUE_INTEREST_ON_UNPAID_INTEREST,
        description='Interest accrual on unpaid interest. If set to "False", interest will not be '
        "calculated and applied on unpaid interest.",
        display_name="Accrue Interest on unpaid interest",
        level=Level.TEMPLATE,
        default_value=OptionalValue("False"),
        shape=OptionalShape(StringShape),
    ),
    Parameter(
        name=ACCRUE_INTEREST_ON_UNPAID_FEES,
        description='Interest accrual on unpaid fees. If set to "False", interest will not be '
        "accrued on unpaid fees.",
        display_name="Accrue Interest on unpaid fees",
        level=Level.TEMPLATE,
        default_value=OptionalValue("False"),
        shape=OptionalShape(StringShape),
    ),
    Parameter(
        name=ACCRUE_INTEREST_FROM_TXN_DAY,
        level=Level.TEMPLATE,
        description="For transactions that are not affected by specific interest behaviours "
        "(i.e. an active Interest Free Period or transaction types that always charge interest "
        "from the transaction date), determines the start point for interest accrual on "
        "transactions charged when entering Revolver status. For more informantion please refer "
        "to the product documentation.",
        display_name="Accrue interest from day of transaction. ",
        default_value="True",
        shape=StringShape,
    ),
    Parameter(
        name=INTEREST_WRITE_OFF_INTERNAL_ACCOUNT,
        description="Internal account used to write-off any outstanding interest",
        display_name="Interest Write-off Internal Account",
        level=Level.TEMPLATE,
        shape=AccountIdShape,
        default_value="INTEREST_WRITEOFF",
    ),
    Parameter(
        name=PRINCIPAL_WRITE_OFF_INTERNAL_ACCOUNT,
        description="Internal account used to write-off any outstanding fees and transactions. "
        "The name follows the accounting definition of Principal",
        display_name="Principal Write-off Internal Account",
        level=Level.TEMPLATE,
        shape=AccountIdShape,
        default_value="PRINCIPAL_WRITEOFF",
    ),
    Parameter(
        name=INTEREST_ON_FEES_INTERNAL_ACCOUNTS_MAP,
        level=Level.TEMPLATE,
        description="Map of internal account id for interest on fees. Contains "
        "both Accrued Interest Receivable (AIR) and Interest Income accounts for all "
        "fees (map format - encoded json).",
        display_name="Interest on fees Internal Accounts per transaction type",
        shape=StringShape,
        default_value=json_dumps(
            {"air": "FEES_INTEREST", "income": "FEES_INTEREST", "loan": "FEES_INTEREST"}
        ),
    ),
    Parameter(
        name=APR,
        level=Level.TEMPLATE,
        description="Annual Percentage Rate per transaction type (map format - encoded json)",
        display_name="Annual Percentage Rate per transaction type",
        shape=StringShape,
        default_value=json_dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0.02",
                "transfer": "0.03",
            }
        ),
    ),
    Parameter(
        name=TXN_APR,
        level=Level.INSTANCE,
        description="Map of maps of Annual Percentage Rate per transaction ref "
        "(map format - encoded json)",
        display_name="Annual Percentage Rate per transaction ref",
        shape=StringShape,
        default_value=json_dumps({"balance_transfer": {"REF1": "0.02", "REF2": "0.03"}}),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=TXN_BASE_INTEREST_RATES,
        level=Level.INSTANCE,
        description="Map of maps of Per annum gross interest rate per transaction ref "
        "(map format - encoded json)",
        display_name="Per annum gross interest rate per transaction ref",
        shape=StringShape,
        default_value=json_dumps({"balance_transfer": {"REF1": "0.022", "REF2": "0.035"}}),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=MAD,
        level=Level.TEMPLATE,
        description="Minimum amount repayment due (higher value of minimum_amount_due or "
        "minimum_percentage_due used)",
        display_name="Minimum Amount Due",
        default_value=Decimal(0),
        shape=MoneyShape,
    ),
    Parameter(
        name=MINIMUM_PERCENTAGE_DUE,
        level=Level.TEMPLATE,
        description="Percentage of statement balance per transaction type used to calculate the "
        "minimum amount due (higher value of minimum_amount_due or "
        "minimum_percentage_due is used)",
        display_name="Percentage of statement balance per transaction type"
        " (map format - encoded json) ",
        default_value=json_dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0.01",
                "transfer": "0.01",
                "balance_transfer": "0.01",
                "interest": "1.0",
                "fees": "1.0",
            }
        ),
        shape=StringShape,
    ),
    Parameter(
        name=PAYMENT_DUE_PERIOD,
        level=Level.INSTANCE,
        description="Number of days after SCOD that payment is due by. Minimum Amount Due must be "
        "paid back by then to avoid Late Repayment fees. Full outstanding balance must"
        " be paid back by then to avoid becoming revolver.",
        display_name="Payment Due Period",
        shape=NumberShape(
            kind=NumberKind.PLAIN,
            min_value=21,
            max_value=27,
            step=1,
        ),
        default_value=Decimal(21),
        update_permission=UpdatePermission.USER_EDITABLE,
    ),
    Parameter(
        name=LATE_REPAYMENT_FEE_PARAM,
        level=Level.INSTANCE,
        description="Fee charged if the MAD is not paid",
        display_name="Fee charged if the MAD is not paid",
        shape=MoneyShape,
        default_value=Decimal(100),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=LATE_REPAYMENT_FEE_INTERNAL_ACCOUNTS,
        description="Loan and Income internal accounts for the late repayment fee",
        display_name="Credit Card Late Fee Account",
        level=Level.TEMPLATE,
        shape=StringShape,
        default_value=json_dumps({"income": "FEE_INCOME", "loan": "FEE_LOAN"}),
    ),
    Parameter(
        name=ANNUAL_FEE_PARAM,
        level=Level.INSTANCE,
        description="Fee charged annually on the account anniversary",
        display_name="Annual Credit Card Fee",
        shape=MoneyShape,
        default_value=Decimal(100),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=ANNUAL_FEE_INTERNAL_ACCOUNTS,
        description="Loan and Income internal accounts for the annual fee",
        display_name="Credit Card Annual Fee Account",
        level=Level.TEMPLATE,
        shape=StringShape,
        default_value=json_dumps({"income": "FEE_INCOME", "loan": "FEE_LOAN"}),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=OVERLIMIT_FEE_PARAM,
        level=Level.INSTANCE,
        description="Fee charged on SCOD if outstanding principal exceeds the credit limit",
        display_name="Overlimit Fee",
        shape=MoneyShape,
        default_value=Decimal(100),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=OVERLIMIT_FEE_INTERNAL_ACCOUNTS,
        description="Loan and Income internal accounts for the overlimit fee",
        display_name="Credit Card Over Limit Fee Account",
        level=Level.TEMPLATE,
        shape=StringShape,
        default_value=json_dumps({"income": "FEE_INCOME", "loan": "FEE_LOAN"}),
    ),
    Parameter(
        name=EXTERNAL_FEE_TYPES,
        description="External fees that can be initiated from outside the contract, but "
        "need to be stored in separate addresses. Stored as an encoded json list.",
        display_name="External Fee Types",
        level=Level.TEMPLATE,
        shape=StringShape,
        default_value=json_dumps(["dispute_fee", "withdrawal_fee"]),
    ),
    Parameter(
        name=EXTERNAL_FEE_INTERNAL_ACCOUNTS,
        description="Loan and Income internal accounts for each external fee type. Stored as an "
        "encoded json map of fee type to json map of account type to account id. The "
        'account types can be "income" or "loan".',
        display_name="Credit Card Dispute Fee Account",
        level=Level.TEMPLATE,
        shape=StringShape,
        default_value=json_dumps(
            {
                "dispute_fee": {"income": "FEE_INCOME", "loan": "FEE_LOAN"},
                "withdrawal_fee": {"income": "FEE_INCOME", "loan": "FEE_LOAN"},
            }
        ),
    ),
    Parameter(
        name=ACCRUAL_BLOCKING_FLAGS,
        description="List of flags applied to customer or account that prevent interest accrual",
        display_name="Accrual Blocking Flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        default_value=json_dumps(["OVER_90_DPD"]),
    ),
    Parameter(
        name=ACCOUNT_CLOSURE_FLAGS,
        description="List of flags applied to customer or account when account closure has been"
        "requested or imposed (i.e. customer or bank initiated)",
        display_name="Account Closure Flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        default_value=json_dumps(["ACCOUNT_CLOSURE_REQUESTED"]),
    ),
    Parameter(
        name=ACCOUNT_WRITE_OFF_FLAGS,
        description="List of flags applied to customer or account which, when applied will generate"
        "postings to zero out FULL_OUTSTANDING_BALANCE on request of account closure",
        display_name="Account Write Off Flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        default_value=json_dumps(["MANUAL_WRITE_OFF", "OVER_150_DPD"]),
    ),
    Parameter(
        name=BILLED_TO_UNPAID_TRANSFER_BLOCKING_FLAGS,
        description="List of flags applied to customer or account which, when applied will suspend "
        "the internal address transfers from billed to unpaid balances on PDD",
        display_name="Billed to Unpaid Transfer Blocking Flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
    Parameter(
        name=MAD_AS_STATEMENT_FLAGS,
        description="List of flags applied to customer or account which, when applied will set MAD"
        "equal to statement balance",
        display_name="MAD as Full Statement Flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        default_value=json_dumps(["ACCOUNT_CLOSURE_REQUESTED", "OVER_90_DPD"]),
    ),
    Parameter(
        name=MAD_EQUAL_TO_ZERO_FLAGS,
        description="List of flags applied to customer or account which, when applied will set MAD"
        "to zero by the next SCOD/PDD event. In effect, the customer will not have to pay any MAD"
        "for the statement periods where this is active, and no late repayment fees will be charged"
        'Note that this takes precedence over the "MAD as Full Statement Flags" parameter.',
        display_name="MAD Equal to Zero Flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
    Parameter(
        name=OVERDUE_AMOUNT_BLOCKING_FLAGS,
        description="List of flags applied to customer or account which, when applied will suspend "
        "the internal address updates on PDD that age the overdue balance buckets",
        display_name="Overdue amount blocking flags",
        shape=StringShape,
        level=Level.TEMPLATE,
        default_value=json_dumps(["REPAYMENT_HOLIDAY"]),
    ),
    Parameter(
        name=INTEREST_FREE_EXPIRY,
        description="List of interest free period expiry times associated with transaction types."
        "This is for transaction types that do not use transaction references",
        display_name="Interest Free Periods Per Transaction Type",
        shape=StringShape,
        level=Level.INSTANCE,
        default_value=json_dumps({"purchase": "", "cash_advance": "", "transfer": ""}),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=TXN_INTEREST_FREE_EXPIRY,
        description="List of interest free period expiry times associated with transaction "
        "references.",
        display_name="Interest Free Periods Per Transaction Ref",
        shape=StringShape,
        level=Level.INSTANCE,
        default_value=json_dumps({"balance_transfer": {"REF1": "", "REF2": ""}}),
        update_permission=UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=ACCRUAL_SCHEDULE_HOUR,
        description="The hour at which the ACCRUE_INTEREST schedule should execute for all "
        "CC accounts.",
        display_name="Accrual Schedule Execution Hour",
        shape=NumberShape(
            kind=NumberKind.PLAIN,
            min_value=0,
            max_value=23,
            step=1,
        ),
        level=Level.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=ACCRUAL_SCHEDULE_MINUTE,
        description="The minute at which the ACCRUE_INTEREST schedule should execute for all "
        "CC accounts.",
        display_name="Accrual Schedule Execution Minute",
        shape=NumberShape(
            kind=NumberKind.PLAIN,
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=Level.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=ACCRUAL_SCHEDULE_SECOND,
        description="The second at which the ACCRUE_INTEREST schedule should execute for all "
        "CC accounts.",
        display_name="Accrual Schedule Execution Second",
        shape=NumberShape(
            kind=NumberKind.PLAIN,
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=Level.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=SCOD_SCHEDULE_HOUR,
        description="The hour at which the STATEMENT_CUT_OFF schedule should execute for all "
        "CC accounts.",
        display_name="Statement Cutoff Schedule Execution Hour",
        shape=NumberShape(
            kind=NumberKind.PLAIN,
            min_value=0,
            max_value=23,
            step=1,
        ),
        level=Level.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=SCOD_SCHEDULE_MINUTE,
        description="The minute at which the STATEMENT_CUT_OFF schedule should execute for all "
        "CC accounts.",
        display_name="Statement Cutoff Schedule Execution Minute",
        shape=NumberShape(
            kind=NumberKind.PLAIN,
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=Level.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=SCOD_SCHEDULE_SECOND,
        description="The second at which the STATEMENT_CUT_OFF schedule should execute for all "
        "CC accounts.",
        display_name="Statement Cutoff Schedule Execution Second",
        shape=NumberShape(
            kind=NumberKind.PLAIN,
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=Level.TEMPLATE,
        default_value=Decimal(2),
    ),
    Parameter(
        name=PDD_SCHEDULE_HOUR,
        description="The hour at which the PAYMENT_DUE schedule should execute for all "
        "CC accounts.",
        display_name="Payment Due Schedule Execution Hour",
        shape=NumberShape(
            kind=NumberKind.PLAIN,
            min_value=0,
            max_value=23,
            step=1,
        ),
        level=Level.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=PDD_SCHEDULE_MINUTE,
        description="The minute at which the PAYMENT_DUE schedule should execute for all "
        "CC accounts.",
        display_name="Payment Due Schedule Execution Minute",
        shape=NumberShape(
            kind=NumberKind.PLAIN,
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=Level.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=PDD_SCHEDULE_SECOND,
        description="The second at which the PAYMENT_DUE schedule should execute for all "
        "CC accounts.",
        display_name="Payment Due Schedule Execution Second",
        shape=NumberShape(
            kind=NumberKind.PLAIN,
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=Level.TEMPLATE,
        default_value=Decimal(1),
    ),
    Parameter(
        name=ANNUAL_FEE_SCHEDULE_HOUR,
        description="The hour at which the ANNUAL_FEE schedule should execute for all "
        "CC accounts.",
        display_name="Annual Fee Schedule Execution Hour",
        shape=NumberShape(
            kind=NumberKind.PLAIN,
            min_value=0,
            max_value=23,
            step=1,
        ),
        level=Level.TEMPLATE,
        default_value=Decimal(23),
    ),
    Parameter(
        name=ANNUAL_FEE_SCHEDULE_MINUTE,
        description="The minute at which the ANNUAL_FEE schedule should execute for all "
        "CC accounts.",
        display_name="Annual Fee Schedule Execution Minute",
        shape=NumberShape(
            kind=NumberKind.PLAIN,
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=Level.TEMPLATE,
        default_value=Decimal(50),
    ),
    Parameter(
        name=ANNUAL_FEE_SCHEDULE_SECOND,
        description="The second at which the ANNUAL_FEE schedule should execute for all "
        "CC accounts.",
        display_name="Annual Fee Schedule Execution Second",
        shape=NumberShape(
            kind=NumberKind.PLAIN,
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=Level.TEMPLATE,
        default_value=Decimal(0),
    ),
]


@requires(parameters=True)
def execution_schedules():
    account_creation_dt = vault.get_account_creation_date()
    payment_due_period = int(_get_parameter(name="payment_due_period", vault=vault))
    # We include transactions on SCOD and PDD day itself, so schedules run at the end of the day
    local_scod_start, local_scod_end = _get_first_scod(account_creation_dt, localize_datetime=True)
    _, local_pdd_end = _get_first_pdd(payment_due_period, local_scod_start)

    scod_schedule = _convert_to_utc_schedule(
        {
            "month": str(local_scod_end.month),
            "day": str(local_scod_end.day),
            "hour": str(_get_parameter(name=SCOD_SCHEDULE_HOUR, vault=vault)),
            "minute": str(_get_parameter(name=SCOD_SCHEDULE_MINUTE, vault=vault)),
            "second": str(_get_parameter(name=SCOD_SCHEDULE_SECOND, vault=vault)),
        }
    )
    annual_fee_schedule = _convert_to_utc_schedule(
        {
            "hour": str(_get_parameter(name=ANNUAL_FEE_SCHEDULE_HOUR, vault=vault)),
            "minute": str(_get_parameter(name=ANNUAL_FEE_SCHEDULE_MINUTE, vault=vault)),
            "second": str(_get_parameter(name=ANNUAL_FEE_SCHEDULE_SECOND, vault=vault)),
        }
    )
    pdd_schedule = _convert_to_utc_schedule(
        {
            "month": str(local_pdd_end.month),
            "day": str(local_pdd_end.day),
            "hour": str(_get_parameter(name=PDD_SCHEDULE_HOUR, vault=vault)),
            "minute": str(_get_parameter(name=PDD_SCHEDULE_MINUTE, vault=vault)),
            "second": str(_get_parameter(name=PDD_SCHEDULE_SECOND, vault=vault)),
        }
    )
    accrue_schedule = _convert_to_utc_schedule(
        {
            "hour": str(_get_parameter(name=ACCRUAL_SCHEDULE_HOUR, vault=vault)),
            "minute": str(_get_parameter(name=ACCRUAL_SCHEDULE_MINUTE, vault=vault)),
            "second": str(_get_parameter(name=ACCRUAL_SCHEDULE_SECOND, vault=vault)),
        }
    )
    return [
        (EVENT_SCOD, scod_schedule),
        # We need to charge annual fee on account opening day every year
        (EVENT_ANNUAL_FEE, annual_fee_schedule),
        (EVENT_PDD, pdd_schedule),
        # Accrual scheduled before PDD/SCOD to ensure they account for latest accrual
        (EVENT_ACCRUE, accrue_schedule),
    ]


# Accrual effective date is guaranteed to be < 24h after accrual cut-off date.
@requires(
    event_type="ACCRUE_INTEREST",
    parameters=True,
    balances="1 day",
    flags=True,
    last_execution_time=["STATEMENT_CUT_OFF"],
)
# We only need balances at cut-off, which will be within 24hrs and live to handle postings arriving
# between cut-off and schedule execution
@requires(
    event_type="STATEMENT_CUT_OFF",
    balances="1 day live",
    flags=True,
    parameters=True,
    last_execution_time=["STATEMENT_CUT_OFF", "PAYMENT_DUE"],
)
@requires(event_type="ANNUAL_FEE", parameters=True, balances="latest live")
# We only need balances at cut-off, which will be within 24hrs, and live to handle postings arriving
# between cut-off and schedule execution
@requires(event_type="PAYMENT_DUE", parameters=True, balances="1 day live", flags=True)
def scheduled_code(event_type, effective_date):

    if event_type == EVENT_ACCRUE:
        _process_interest_accrual_and_charging(vault, effective_date)
    elif event_type == EVENT_SCOD:
        _process_statement_cut_off(vault, effective_date)
    elif event_type == EVENT_ANNUAL_FEE:
        _charge_annual_fee(vault, effective_date)
        account_creation_dt = vault.get_account_creation_date()
        annual_fee_day = (
            "last"
            if (account_creation_dt.month == 2 and account_creation_dt.day == 29)
            else account_creation_dt.day
        )

        annual_fee_utc_schedule = _convert_to_utc_schedule(
            {
                # Explicitly declare next year to prevent infinity loop
                "year": str(effective_date.year + 1),
                "month": str(account_creation_dt.month),
                "day": str(annual_fee_day),
                "hour": str(_get_parameter(name=ANNUAL_FEE_SCHEDULE_HOUR, vault=vault)),
                "minute": str(_get_parameter(name=ANNUAL_FEE_SCHEDULE_MINUTE, vault=vault)),
                "second": str(_get_parameter(name=ANNUAL_FEE_SCHEDULE_SECOND, vault=vault)),
            }
        )

        vault.update_event_type(
            event_type=EVENT_ANNUAL_FEE,
            schedule=EventTypeSchedule(
                year=annual_fee_utc_schedule["year"],
                month=annual_fee_utc_schedule["month"],
                day=annual_fee_utc_schedule["day"],
                hour=annual_fee_utc_schedule["hour"],
                minute=annual_fee_utc_schedule["minute"],
                second=annual_fee_utc_schedule["second"],
            ),
        )
    elif event_type == EVENT_PDD:
        _process_payment_due_date(vault, effective_date)
        # Set next PDD and corresponding SCOD schedules
        account_creation_dt = vault.get_account_creation_date()
        payment_due_period = int(
            _get_parameter(name="payment_due_period", at=account_creation_dt, vault=vault)
        )
        local_next_pdd_start, local_next_pdd_end = _get_next_pdd(
            payment_due_period,
            account_creation_dt,
            last_pdd_execution_datetime=effective_date,
            localize_datetime=True,
        )
        _, local_next_scod_end = _get_scod_for_pdd(payment_due_period, local_next_pdd_start)

        pdd_utc_schedule = _convert_to_utc_schedule(
            {
                "month": str(local_next_pdd_end.month),
                "day": str(local_next_pdd_end.day),
                "hour": str(_get_parameter(name=PDD_SCHEDULE_HOUR, vault=vault)),
                "minute": str(_get_parameter(name=PDD_SCHEDULE_MINUTE, vault=vault)),
                "second": str(_get_parameter(name=PDD_SCHEDULE_SECOND, vault=vault)),
            }
        )

        vault.update_event_type(
            event_type=EVENT_PDD,
            schedule=EventTypeSchedule(
                month=pdd_utc_schedule["month"],
                day=pdd_utc_schedule["day"],
                hour=pdd_utc_schedule["hour"],
                minute=pdd_utc_schedule["minute"],
                second=pdd_utc_schedule["second"],
            ),
        )

        scod_utc_schedule = _convert_to_utc_schedule(
            {
                "month": str(local_next_scod_end.month),
                "day": str(local_next_scod_end.day),
                "hour": str(_get_parameter(name=SCOD_SCHEDULE_HOUR, vault=vault)),
                "minute": str(_get_parameter(name=SCOD_SCHEDULE_MINUTE, vault=vault)),
                "second": str(_get_parameter(name=SCOD_SCHEDULE_SECOND, vault=vault)),
            }
        )

        vault.update_event_type(
            event_type=EVENT_SCOD,
            schedule=EventTypeSchedule(
                month=scod_utc_schedule["month"],
                day=scod_utc_schedule["day"],
                hour=scod_utc_schedule["hour"],
                minute=scod_utc_schedule["minute"],
                second=scod_utc_schedule["second"],
            ),
        )


# Having live DEFAULT means we won't double spend/exceed available balance
@requires(parameters=True, balances="latest live")
def pre_posting_code(postings, effective_date):
    denomination = _get_parameter(name=DENOMINATION, vault=vault)
    if any(post.denomination != denomination for post in postings):
        raise Rejected(
            "Cannot make transactions in given denomination; "
            "transactions must be in {}".format(denomination),
            reason_code=RejectedReason.WRONG_DENOMINATION,
        )

    latest_balances = vault.get_balance_timeseries().latest()
    supported_txn_types = _get_supported_txn_types(vault)
    txn_code_to_type_map = _get_parameter(
        name=TXN_CODE_TO_TYPE_MAP, at=effective_date, is_json=True, vault=vault
    )

    _validate_txn_type_and_refs(
        vault,
        latest_balances,
        postings,
        supported_txn_types,
        txn_code_to_type_map,
        effective_date,
    )

    non_advice_postings = _get_non_advice_postings(postings)
    _check_account_has_sufficient_funds(vault, latest_balances, denomination, non_advice_postings)
    _check_txn_type_credit_limits(
        vault,
        latest_balances,
        non_advice_postings,
        denomination,
        effective_date,
        txn_code_to_type_map,
    )
    _check_txn_type_time_limits(vault, non_advice_postings, effective_date)


@requires(parameters=True)
def post_parameter_change_code(old_parameter_values, updated_parameter_values, effective_date):

    ins = []

    _handle_credit_limit_change(vault, old_parameter_values, updated_parameter_values, ins)

    if ins:
        vault.instruct_posting_batch(
            posting_instructions=ins,
            effective_date=effective_date,
            client_batch_id=f"POST_PARAMETER_CHANGE-{vault.get_hook_execution_id()}",
        )


@requires(parameters=True)
def post_activate_code():
    """
    Initialise specific balances on account activation
    :return:
    """
    effective_date = vault.get_account_creation_date()
    _check_txn_type_parameter_configuration(vault, effective_date)

    credit_limit = Decimal(_get_parameter(name=CREDIT_LIMIT, vault=vault))
    denomination = _get_parameter(name=DENOMINATION, vault=vault)

    instructions = []

    if credit_limit > Decimal(0):
        _make_internal_address_transfer(
            vault,
            abs(credit_limit),
            denomination,
            credit_internal=True,
            custom_address=AVAILABLE_BALANCE,
            action=f"INITIALISE_{AVAILABLE_BALANCE}",
            trigger="ACCOUNT_OPENED",
            instructions_to_extend=instructions,
        )

        _make_credit_limit_change_gl_postings(
            vault=vault,
            denomination=denomination,
            new_credit_limit=credit_limit,
            old_credit_limit=0,
            instructions=instructions,
        )

    vault.instruct_posting_batch(
        posting_instructions=instructions,
        effective_date=effective_date,
        client_batch_id=f"POST_ACTIVATION-{vault.get_hook_execution_id()}",
    )


# Having live means we won't rebalance on stale balances (e.g. spending DEPOSIT twice)
@requires(parameters=True, balances="latest live")
def post_posting_code(postings, effective_date):

    denomination = _get_parameter(name=DENOMINATION, vault=vault)
    credit_limit = _get_parameter(name=CREDIT_LIMIT, vault=vault)
    latest_balances = vault.get_balance_timeseries().latest()
    in_flight_balances = _deep_copy_balances(latest_balances)
    instructions = []

    _rebalance_postings(vault, postings, in_flight_balances, effective_date, instructions)

    _charge_txn_type_fees(
        vault,
        postings,
        latest_balances,
        in_flight_balances,
        denomination,
        instructions,
        effective_date,
    )

    _adjust_aggregate_balances(
        denomination,
        in_flight_balances,
        instructions,
        vault,
        trigger=f"POST_POSTING_{postings.batch_id}",
        effective_datetime=effective_date,
        credit_limit=credit_limit,
    )

    if instructions:
        vault.instruct_posting_batch(
            posting_instructions=instructions,
            effective_date=effective_date,
            client_batch_id=f"POST_POSTING-{vault.get_hook_execution_id()}",
        )


# See STATEMENT_CUT_OFF, except balances are 'latest live' as cut-off and effective date are
# identical for final statements
@requires(
    parameters=True,
    balances="latest live",
    flags=True,
    last_execution_time=["STATEMENT_CUT_OFF"],
)
def close_code(effective_date):

    in_flight_balances = _deep_copy_balances(vault.get_balance_timeseries().latest())
    txn_types = _get_supported_txn_types(vault, effective_date)
    # Make sure the _INTEREST_FREE_PERIOD_INTEREST_UNCHARGED addresses get zeroed out as well
    for txn_type in set(txn_types):
        txn_types[f"{txn_type}_{INTEREST_FREE_PERIOD}"] = txn_types[txn_type]
    denomination = _get_parameter(vault, name="denomination", at=effective_date)
    instructions = []

    account_closure_flags_applied = _is_flag_in_list_applied(
        vault, ACCOUNT_CLOSURE_FLAGS, effective_date
    )
    write_off_flags_applied = _is_flag_in_list_applied(
        vault, ACCOUNT_WRITE_OFF_FLAGS, effective_date
    )

    _can_final_statement_be_generated(
        in_flight_balances,
        account_closure_flags_applied,
        write_off_flags_applied,
        denomination,
    )

    if write_off_flags_applied:
        _process_write_off(denomination, in_flight_balances, effective_date, instructions, vault)

    _process_statement_cut_off(vault, effective_date, in_flight_balances, is_final=True)

    zero_out_instructions = _zero_out_balances_for_account_closure(
        vault, effective_date, in_flight_balances, txn_types
    )

    vault.instruct_posting_batch(
        posting_instructions=instructions + zero_out_instructions,
        effective_date=effective_date,
        client_batch_id=f"CLOSE_ACCOUNT-{vault.get_hook_execution_id()}",
    )


#  Helper functions
def _zero_out_balances_for_account_closure(vault, effective_date, in_flight_balances, txn_types):
    """
    Create postings to zero out remaining balances that aren't written off or paid-back when an
    account is being closed or written off. All balances other than
    - AVAILABLE_BALANCE,
    - <transaction_type>_INTEREST_UNCHARGED,
    - <transaction_type>_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED
    - INTERNAL
    must be 0 as the full outstanding balance has either been paid off or written off
    :param vault:
    :param effective_date: datetime, date and time at which the closure is requested
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance] account balances
    updated with posting instructions created within the current hook execution
    :param txn_types: List[str] supported transaction types
    :return: List[PostingInstruction], posting instructions that zero out remaining balances
    """

    denomination = _get_parameter(name=DENOMINATION, at=effective_date, vault=vault)
    # Find out whether we accrue interest from transaction day
    accrue_interest_from_txn_day = _is_txn_interest_accrual_from_txn_day(vault)

    accrued_interest_instructions = _reverse_uncharged_interest(
        vault, in_flight_balances, denomination, txn_types, "ACCOUNT_CLOSED"
    )

    if accrue_interest_from_txn_day:
        accrued_interest_instructions += _reverse_uncharged_interest(
            vault,
            in_flight_balances,
            denomination,
            txn_types,
            "ACCOUNT_CLOSED",
            PRE_SCOD,
        )
        accrued_interest_instructions += _reverse_uncharged_interest(
            vault,
            in_flight_balances,
            denomination,
            txn_types,
            "ACCOUNT_CLOSED",
            POST_SCOD,
        )

    available_balance_instructions = []
    # close_code can be re-run, so override ensures we don't re-zero-out in case
    _override_info_balance(
        balance_address=AVAILABLE_BALANCE,
        amount=0,
        trigger="ACCOUNT_CLOSED",
        vault=vault,
        in_flight_balances=in_flight_balances,
        denomination=denomination,
        instructions=available_balance_instructions,
    )

    return accrued_interest_instructions + available_balance_instructions


def _process_write_off(denomination, in_flight_balances, effective_date, instructions, vault):
    """
    Calculate accounting principal (principal + fees) and interest write-off amounts and create
    postings to transfer them from write-off accounts to the current account
    :param denomination: str, the account denomination
    :param in_flight_balances: DefaultDict[Tuple(str, str, str, Phase), Balance], the balances used
    to determine write-off amounts. Updated with write-off postings
    :param effective_date: datetime, when the write-off is being processed
    :param instructions: List[PostingInstruction], list of postings to be extended with write-off
    postings
    :param vault:
    :return: None
    """

    write_off_instructions = []
    repayment_instructions = []
    trigger = "ACCOUNT_CHARGED_OFF"

    txn_types = _get_supported_txn_types(vault, effective_date)
    fee_types = _get_supported_fee_types(vault, txn_types)

    finance_principal = _calculate_aggregate_balance(
        in_flight_balances,
        denomination,
        fee_types,
        balance_def={PRINCIPAL: CHARGED_BALANCE_STATES, FEES: CHARGED_BALANCE_STATES},
        txn_type_map=txn_types,
        include_deposit=False,
    )

    interest = _calculate_aggregate_balance(
        in_flight_balances,
        denomination,
        fee_types,
        balance_def={INTEREST: CHARGED_BALANCE_STATES},
        txn_type_map=txn_types,
        include_deposit=False,
    )

    principal_write_off_account = _get_parameter(vault, name=PRINCIPAL_WRITE_OFF_INTERNAL_ACCOUNT)
    interest_write_off_account = _get_parameter(vault, name=INTEREST_WRITE_OFF_INTERNAL_ACCOUNT)

    credit_limit = _get_parameter(name=CREDIT_LIMIT, at=effective_date, vault=vault)
    instruction_details = _gl_posting_metadata("LOAN_CHARGE_OFF", vault.account_id)

    _create_postings(
        vault,
        amount=abs(finance_principal),
        denomination=denomination,
        from_account_id=principal_write_off_account,
        to_account_id=vault.account_id,
        instructions=write_off_instructions,
        instruction_details=instruction_details,
        action="CHARGE_OFF_PRINCIPAL",
        trigger="ACCOUNT_CHARGED_OFF",
    )

    _create_postings(
        vault,
        amount=abs(interest),
        denomination=denomination,
        from_account_id=interest_write_off_account,
        to_account_id=vault.account_id,
        instructions=write_off_instructions,
        instruction_details=instruction_details,
        action="CHARGE_OFF_INTEREST",
        trigger="ACCOUNT_CHARGED_OFF",
    )

    write_off_count = 0
    for posting in write_off_instructions:
        # _create_postings will returns postings for internal account and customer account
        if posting.account_id == vault.account_id:
            # Posting instructions get assigned an id when their batch is commited, so we mock the
            # id as it is used to generate unique client transaction ids in _process_repayment
            posting.id = f"write_off_{write_off_count}"
            write_off_count += 1
            _process_repayment(
                vault,
                posting,
                in_flight_balances,
                effective_date,
                repayment_instructions,
            )

    _adjust_aggregate_balances(
        denomination,
        in_flight_balances,
        instructions,
        vault,
        trigger=trigger,
        effective_datetime=effective_date,
        credit_limit=credit_limit,
    )

    instructions.extend(write_off_instructions + repayment_instructions)


def _can_final_statement_be_generated(
    balances, are_closure_flags_applied, are_write_off_flags_applied, denomination
):
    """
    Determines whether the final statement can safely be generated by checking that:
    - a closure or write-off flag has been applied
    - full outstanding balance is 0
    - there are no open authorisations
    :param balances: DefaultDict[Tuple(str, str, str, Phase), Balance], balances at the time the
    closure request is made
    :param are_closure_flags_applied: bool, set to True if any of the flags in the
    ACCOUNT_CLOSURE_FLAGS parameter are applied to the account/customer
    :param are_write_off_flags_applied: bool, set to True if any of the flags in the
    ACCOUNT_WRITE_OFF_FLAGS parameter are applied to the account/customer
    :param denomination: str, the account denomination
    :return: None, a Rejected exception is raised if any of the checks fail. This ensures the
    closure_update account-update fails
    """

    if not are_closure_flags_applied and not are_write_off_flags_applied:
        raise Rejected(
            "No account closure or write-off flags on the account",
            reason_code=RejectedReason.CLIENT_CUSTOM_REASON,
        )

    # write-off account will by definition have non-zero outstanding balance
    if not are_write_off_flags_applied:

        full_outstanding_balance = _get_balance(
            balances, address=FULL_OUTSTANDING_BALANCE, denomination=denomination
        )
        if full_outstanding_balance != Decimal(0):
            raise Rejected(
                "Full Outstanding Balance is not zero",
                reason_code=RejectedReason.CLIENT_CUSTOM_REASON,
            )

        auth_balances = sum(
            [
                balance.net
                for (address, _, _, _), balance in balances.items()
                if address.endswith(AUTH)
            ]
        )
        if auth_balances != Decimal(0):
            raise Rejected(
                "Outstanding authorisations on the account",
                reason_code=RejectedReason.CLIENT_CUSTOM_REASON,
            )


def _check_txn_type_parameter_configuration(vault, effective_timestamp=None):
    """
    Check that parameters with transaction types are configured consistently.

    Transaction types that specify details at the transaction reference level
    should not also specify them at the template level. e.g. Balance transfers
    set the interest rate in txn_type_apr, and there should not be a
    'balance_transfer' entry in the template-level 'apr' parameter.

    Note: any error found in the configuration will result in an exception
    being raised

    :param vault:
    :param effective_timestamp: Optional[datetime], the datetime as of which to retrieve parameters.
    """
    error_list = []

    def _compare_parameter_keys(
        main_list: set,
        compare_list_name: str,
        effective_timestamp: datetime,
        match_type: str = "match",
        values: bool = False,
    ):
        """
        Check whether a set of strings from a parameter are not found in another set.

        :param main_list: set of keys to check against
        :param compare_list_name: name of a parameter to check against main_list
        :param effective_timestamp: timestamp at which to fetch the parameter with compare_list_name
        :param match_type: Optional string,
         'match' - keys in the compare_list_name parameter must exactly match main_list
         'subset' - keys in the compare_list_name parameter must be a subset of main_list
         'superset' - keys in main_list must be in compare_list
        :param values: whether to use the values of the compare_list, rather than the keys
        to match with
        :return: the contents of the compare_list_name
        """
        compare_list = _get_parameter(
            vault, compare_list_name, at=effective_timestamp, is_json=True
        )
        if values:
            compare_list = compare_list.values()
        compare_list = set(compare_list)

        if match_type == "subset":
            if compare_list.difference(main_list):
                error_list.append(
                    f"Types in {compare_list_name} = {sorted(compare_list)}"
                    + f" are not present in {sorted(main_list)}."
                )
        elif match_type == "superset":
            if main_list.difference(compare_list):
                error_list.append(
                    f"Types in {sorted(main_list)} are not present in"
                    f" {compare_list_name} = {sorted(compare_list)}."
                )
        elif compare_list != main_list:
            error_list.append(
                f"Mismatch between txn types:"
                f" '{compare_list_name}' = {sorted(compare_list)}"
                f" does not match {sorted(main_list)}."
            )
        return compare_list

    # Find out whether we charge interest on fees, for later checks
    accrue_interest_on_unpaid_fees = _str_to_bool(
        _get_parameter(
            vault,
            name=ACCRUE_INTEREST_ON_UNPAID_FEES,
            optional=True,
            default_value="False",
        )
    )

    # Explicit definition of the transaction types - all types should be in here
    supported_txn_types = set(
        _get_parameter(vault, name=TXN_TYPES, at=effective_timestamp, is_json=True)
    )
    supported_txn_types_with_interest_and_fees = supported_txn_types | {
        "interest",
        "fees",
    }

    # The types that correspond to txn codes - all types should be in here
    _compare_parameter_keys(
        supported_txn_types, TXN_CODE_TO_TYPE_MAP, effective_timestamp, values=True
    )

    # Minimum percentage due - all types should be in here, as well as "interest" and "fees"
    _compare_parameter_keys(
        supported_txn_types_with_interest_and_fees,
        MINIMUM_PERCENTAGE_DUE,
        effective_timestamp,
    )

    # The transaction types where things are done at the transaction level
    # through references - should be in supported_txn_types
    types_with_refs = _compare_parameter_keys(
        supported_txn_types, TXN_REFS, effective_timestamp, match_type="subset"
    )

    # The types that don't use refs
    types_without_refs = supported_txn_types.difference(types_with_refs)

    # Template level APR parameter should only have types that don't use refs
    # Template level base rates should only have types that don't use refs
    # They should also include 'fees' if those are interest-bearing
    template_level_interest_types = types_without_refs.copy()
    if accrue_interest_on_unpaid_fees:
        template_level_interest_types.add("fees")

    _compare_parameter_keys(template_level_interest_types, APR, effective_timestamp)

    _compare_parameter_keys(template_level_interest_types, BASE_INTEREST_RATES, effective_timestamp)

    _compare_parameter_keys(types_with_refs, TXN_APR, effective_timestamp)

    _compare_parameter_keys(types_with_refs, TXN_BASE_INTEREST_RATES, effective_timestamp)

    # All types should have an internal account for principal spend and interest
    _compare_parameter_keys(
        supported_txn_types, TXN_TYPE_INTERNAL_ACCOUNTS_MAP, effective_timestamp
    )
    _compare_parameter_keys(
        supported_txn_types,
        TXN_TYPE_INTEREST_INTERNAL_ACCOUNTS_MAP,
        effective_timestamp,
    )

    # These don't need to have all types included, but any here must be in supported_txn_types
    _compare_parameter_keys(
        supported_txn_types, TXN_TYPE_LIMITS, effective_timestamp, match_type="subset"
    )

    fee_types = _compare_parameter_keys(
        supported_txn_types, TXN_TYPE_FEES, effective_timestamp, match_type="subset"
    )

    # Interest free expiry types, if specified, must be in types_without_refs / types_with_refs
    _compare_parameter_keys(
        types_without_refs,
        INTEREST_FREE_EXPIRY,
        effective_timestamp,
        match_type="subset",
    )

    _compare_parameter_keys(
        types_with_refs,
        TXN_INTEREST_FREE_EXPIRY,
        effective_timestamp,
        match_type="subset",
    )

    # All types that use fees must be included in the internal account map, but we are not strict
    # if more are configured than currently have fees
    _compare_parameter_keys(
        fee_types,
        TXN_TYPE_FEES_INTERNAL_ACCOUNTS_MAP,
        effective_timestamp,
        match_type="superset",
    )

    # Return an error if there were any problems found
    if error_list:
        message = " ".join(error_list)
        message += f" Parameters valued at {effective_timestamp}."
        raise InvalidContractParameter(message)


def _validate_txn_type_and_refs(
    vault, balances, postings, supported_txn_types, txn_code_to_type_map, effective_date
):
    """
    Check that a posting contains a transaction level reference if one is required and that it is
    present in params. Additionally check reference is unique and has not been used previously, by
    checking posting metadata against existing _CHARGED balance addresses.
    :param vault:
    :param balances: DefaultDict[Tuple[str, str, str, Phase], Balance], current balances of account
    :param postings: List[PostingInstruction], postings that need to be validated
    :param supported_txn_types: Dict[str, List[str]], the transaction types supported by the account
    :param txn_code_to_type_map: Dict[str, str], map of transaction codes to transaction types
    :param effective_date: datetime, when the postings are being processed as-of. Used for parameter
    retrieval
    """
    txn_types_with_refs = {
        None if attributes is None else txn_type.upper(): attributes
        for txn_type, attributes in supported_txn_types.items()
    }

    for posting in postings:
        # if posting is of type credit, no validation assumed
        if posting.credit:
            continue

        txn_type, txn_ref = _get_txn_type_and_ref_from_posting(
            vault,
            posting.instruction_details,
            effective_date,
            supported_txn_types=supported_txn_types,
            txn_code_to_type_map=txn_code_to_type_map,
        )

        # Check reference exists first, if a non-ref transaction type we can skip the other checks.
        if not txn_ref:
            if txn_type.upper() in txn_types_with_refs:
                raise Rejected(
                    f"Transaction type {txn_type} requires a transaction level reference and none "
                    f"has been specified.",
                    reason_code=RejectedReason.AGAINST_TNC,
                )
            else:
                continue

        elif txn_ref not in txn_types_with_refs.get(txn_type.upper(), [None]):
            raise Rejected(
                f"{txn_ref} undefined in parameters for {txn_type}. Please update parameters.",
                reason_code=RejectedReason.AGAINST_TNC,
            )

        for dimensions in balances.keys():
            if dimensions[0] == _principal_address(txn_type, CHARGED, txn_ref=txn_ref):
                raise Rejected(
                    f"{txn_ref} already in use for {txn_type}. Please select a unique reference.",
                    reason_code=RejectedReason.AGAINST_TNC,
                )


def _check_account_has_sufficient_funds(vault, balances, denomination, postings):
    """
    Checks whether the account has sufficient funds for the proposed postings by
    considering the account's current usage of credit limit and overlimit (if opted in)
    :param vault:
    :param balances: DefaultDict[Tuple(str, str, str, Phase), Balance], the balances used to
    validate the postings
    :param denomination: str, the account denomination
    :param postings: List[PostingInstruction], postings that need to be validated
    :return: None
    """

    postings_balances = BalanceDefaultDict(lambda *_: Balance())
    _update_balances(vault.account_id, postings_balances, postings)

    # Set credit limit param to 0 and txn_type to [] to isolate the postings delta
    available_balance_delta = _get_available_balance(0, postings_balances, {}, denomination)
    if available_balance_delta >= 0:
        # Account balance is increasing so we don't need to check the available funds
        return

    txn_types = _get_supported_txn_types(vault, None)
    credit_limit = _get_parameter(name=CREDIT_LIMIT, vault=vault)
    available_balance = _get_available_balance(credit_limit, balances, txn_types, denomination)
    overlimit_amount = _get_overlimit_amount(balances, credit_limit, denomination, txn_types)

    # Once customer is overlimit due to principal spend, they cannot transact further
    if overlimit_amount > 0:
        raise Rejected(
            f"Insufficient funds for {denomination} {-available_balance_delta} transaction."
            f" Overlimit already in use",
            reason_code=RejectedReason.INSUFFICIENT_FUNDS,
        )

    # Inbound/Outbound Auth Settlements do not go through pre_posting_code so it is possible
    # to over settle past overlimit regardless of opt-in
    opt_in = _str_to_bool(
        _get_parameter(vault, OVERLIMIT_OPT_IN, optional=True, default_value="False")
    )
    if opt_in:
        overlimit = _get_parameter(vault, OVERLIMIT, optional=True, default_value=Decimal(0))
        available_balance += overlimit

    if available_balance + available_balance_delta < 0:
        raise Rejected(
            f"Insufficient funds {denomination} {available_balance} for "
            f"{denomination} {-available_balance_delta} transaction (excl advice instructions)",
            reason_code=RejectedReason.INSUFFICIENT_FUNDS,
        )


def _check_txn_type_time_limits(vault, postings, effective_date):
    """
    Rejects any postings that are outside of a time window,
    e.g. within a certain number of days after account opening

    :param vault:
    :param postings: List[PostingInstruction], postings to check against transaction time limits
    :param effective_date: datetime, when the postings are being processed as-of. Used for parameter
    retrieval and to check the limit
    :return: None, Raises Rejected exception if any transaction time limit is breached by a posting
    """

    txn_type_limits: dict[str, dict[str, str]] = _get_parameter(
        name=TXN_TYPE_LIMITS, at=effective_date, is_json=True, vault=vault
    )

    time_limit_keys = {ALLOWED_DAYS_AFTER_OPENING}

    # find the types that have time-related keys in txn_type_limits
    txn_types_with_time_limits = [
        txn_type
        for txn_type, limits in txn_type_limits.items()
        if set(limits.keys()) & time_limit_keys
    ]
    if txn_types_with_time_limits == []:
        return

    txn_code_to_type_map = _get_parameter(
        name=TXN_CODE_TO_TYPE_MAP, at=effective_date, is_json=True, vault=vault
    )

    # Find postings that match the ones that have time limit(s)
    for posting in postings:
        this_txn_type, _ = _get_txn_type_and_ref_from_posting(
            vault,
            posting.instruction_details,
            effective_date,
            txn_code_to_type_map=txn_code_to_type_map,
        )
        if this_txn_type not in txn_types_with_time_limits:
            continue
        limits = txn_type_limits.get(this_txn_type, {})
        allowed_days_after = limits.get(ALLOWED_DAYS_AFTER_OPENING)

        if allowed_days_after is not None:
            # The cutoff works from creation time-of-day to current time-of-day,
            end_of_allowed_period = vault.get_account_creation_date() + timedelta(
                days=int(allowed_days_after)
            )
            if effective_date >= end_of_allowed_period:
                raise Rejected(
                    f"Transaction not permitted outside of configured window "
                    f"{allowed_days_after} days from account opening",
                    reason_code=RejectedReason.AGAINST_TNC,
                )


def _handle_credit_limit_change(
    vault, old_parameter_values, updated_parameter_values, instructions
):
    """
    Determine if credit limit has been updated and create postings to update address balance
     and GL accordingly
    :param vault:
    :param old_parameter_values: Dict[str, str], map of parameter name -> old parameter value
    :param updated_parameter_values: Dict[str, str], map of parameter name -> new parameter value
    :param instructions: List[PostingInstruction], list of posting instructions that will be
    extended with the postings to change the credit limit
    :return: None
    """

    if not _has_parameter_value_changed(
        parameter_name=CREDIT_LIMIT,
        old_parameter_values=old_parameter_values,
        updated_parameter_values=updated_parameter_values,
    ):
        return

    new_credit_limit = updated_parameter_values[CREDIT_LIMIT]
    old_credit_limit = old_parameter_values[CREDIT_LIMIT]
    denomination = _get_parameter(name=DENOMINATION, vault=vault)

    amount = abs(new_credit_limit - old_credit_limit)
    # For a credit limit increase, to make the credit limit address more
    # positive, we debit it, because it's an asset tside. So we credit the internal
    credit_internal = new_credit_limit > old_credit_limit

    _make_internal_address_transfer(
        amount=amount,
        credit_internal=credit_internal,
        custom_address=AVAILABLE_BALANCE,
        vault=vault,
        denomination=denomination,
        instructions_to_extend=instructions,
        action="ADJUST_AVAILABLE_BALANCE",
        trigger="NEW_CREDIT_LIMIT",
    )

    _make_credit_limit_change_gl_postings(
        vault=vault,
        denomination=denomination,
        new_credit_limit=new_credit_limit,
        old_credit_limit=old_credit_limit,
        instructions=instructions,
    )


def _has_parameter_value_changed(parameter_name, old_parameter_values, updated_parameter_values):
    """
    Determines if a parameter has changed. To be used within post-parameter change hook
    :param parameter_name: str, name of the parameter
    :param old_parameter_values: Dict[str, str], map of parameter name -> old parameter value
    :param updated_parameter_values: Dict[str, str], map of parameter name -> new parameter value
    :return: bool, True if parameter value has changed, False otherwise
    """

    if parameter_name not in updated_parameter_values:
        return False

    if old_parameter_values[parameter_name] == updated_parameter_values[parameter_name]:
        return False

    return True


def _get_available_balance(credit_limit, balances, txn_types, denomination):
    """
    Determine the available balance for the account, taking into account postings that haven't yet
    been rebalanced.
    :param credit_limit: Decimal, credit limit for the account
    :param balances: DefaultDict[Tuple[str, str, str, Phase], Balance], the balances to use to
    calculate the available balance
    :param txn_types: List[str], the transaction types supported by the account
    :param denomination: str, denomination of the available balance to get
    :return: Decimal, available balance
    """

    # Using AVAILABLE_BALANCE address exposes us to race conditions if post-posting is held up.
    # DEFAULT is the earliest updated balance for all postings (spend, fees, interest) so we use it.
    settled_amount = balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
    pending_amount = balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)].net

    # Charged interest does not impact available balance but it is included in DEFAULT, so it must
    # be added
    charged_interest = _calculate_aggregate_balance(
        balances=balances,
        denomination=denomination,
        txn_type_map=txn_types,
        fee_types=[],
        balance_def={INTEREST: [CHARGED]},
        include_deposit=False,  # deposit is already included in DEFAULT
    )
    available_balance = credit_limit - (settled_amount + pending_amount) + charged_interest

    return available_balance


def _rebalance_postings(vault, postings, in_flight_balances, effective_date, instructions):
    """
    Takes postings from post-posting hook and creates postings to rebalance account addresses based
    on the instruction type, amount and current balances
    :param vault:
    :param postings: List[PostingInstruction], postings to rebalance
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest balances
    adjusted for any postings made during the current hook execution. Will be adjusted with
     rebalancing postings
    :param effective_date: datetime, datetime as of which we are rebalancing
    :param instructions: List[PostingInstruction], list of posting instructions to be extended with
    rebalancing postings
    :return: None
    """

    for post in postings:
        if post.type in (
            PostingInstructionType.SETTLEMENT,
            PostingInstructionType.HARD_SETTLEMENT,
            PostingInstructionType.TRANSFER,
        ):
            if post.credit:
                _process_repayment(vault, post, in_flight_balances, effective_date, instructions)
            else:
                _rebalance_settlement(vault, post, in_flight_balances, effective_date, instructions)

        elif post.type == PostingInstructionType.AUTHORISATION and not post.credit:
            _rebalance_outbound_auth(vault, post, in_flight_balances, effective_date, instructions)

        elif post.type == PostingInstructionType.AUTHORISATION_ADJUSTMENT:
            _rebalance_auth_adjust(vault, post, in_flight_balances, effective_date, instructions)

        elif post.type == PostingInstructionType.RELEASE and not post.credit:
            _rebalance_release(vault, post, in_flight_balances, effective_date, instructions)


def _localize_datetime(input_datetime):
    """
    Converts timezone-naive datetime from UTC to Local
    :param input_datetime: datetime, timezone naive UTC datetime to convert
    :return: datetime, timezone naive local equivalent
    """
    return input_datetime + timedelta(hours=LOCAL_UTC_OFFSET)


def _delocalize_datetime(input_datetime):
    """
    Converts timezone-naive datetime back to UTC.
    :param input_datetime: datetime, timezone naive local datetime to convert
    :return: datetime, timezone naive UTC equivalent
    """

    return input_datetime - timedelta(hours=LOCAL_UTC_OFFSET)


def _convert_to_utc_schedule(schedule):
    """
    Converts a non-UTC schedule to UTC-schedule, assuming fixed local-UTC offset. Only supports:
    - second, minute, hour, day, month, year parameters
    - integer schedule parameters (i.e. no *, last)
    - positive integer hour offsets from UTC
    WARNING: Does not validate schedule (e.g. if you try and pass in year and day it will not reject
    despite day being a day of month and no month being specified.
    Support for 'last' will only be possible when native non-UTC schedule is available, in which
    case this method can be removed
    :param schedule: Dict[str, str], local schedule to be adjusted to UTC
    :return: Dict[str, str], UTC-adjusted schedule
    """

    schedule = _default_schedule_values(schedule)

    local_hour = schedule.get("hour", None)
    local_day = schedule.get("day", None)
    local_month = schedule.get("month", None)
    local_year = schedule.get("year", None)
    local_start_date = schedule.get("start_date", None)

    utc_schedule = schedule
    utc_changed_fields = {}

    if local_hour:
        local_hour = int(local_hour)
        # UTC date = Local date if local time greater than offset from UTC
        date_offset_required = local_hour < LOCAL_UTC_OFFSET
        utc_changed_fields["hour"] = str(int((local_hour + 24 - LOCAL_UTC_OFFSET) % 24))

        # Because we have defaulted values, we can only have 2 scenarios: day and month, or day,
        # month and year specified.
        if (local_day or local_month or local_year) and date_offset_required:

            if int(local_day) == 1:
                utc_changed_fields["day"] = "last"
                # only offset month if it's been specified and day has wrapped around
                if int(local_month) == 1:
                    # only offset year if it's been specified and month has wrapped around
                    utc_changed_fields["month"] = "12"
                    if local_year:
                        utc_changed_fields["year"] = str(int(local_year) - 1)
                else:
                    utc_changed_fields["month"] = str(int(local_month) - 1)
            else:
                utc_changed_fields["day"] = str(int(local_day) - 1)

        if local_start_date:
            offset_start_date = parse_to_datetime(local_start_date) - timedelta(
                hours=LOCAL_UTC_OFFSET
            )
            utc_changed_fields["start_date"] = "{}-{}-{}".format(
                offset_start_date.year, offset_start_date.month, offset_start_date.day
            )

    for field, new_value in utc_changed_fields.items():
        utc_schedule[field] = new_value

    return utc_schedule


def _default_schedule_values(schedule):
    """
    For a given schedule, determines which fields will be defaulted to non-* values
    Replicates scheduler logic
    Slightly modified version of apscheduler code
    :param schedule: Dict[str, str], schedule as per execution_schedules
    :return: Dict[str, str], copy of the schedule with non-* default values set
    """

    field_names = (
        "start_date",
        "year",
        "month",
        "day",
        "week",
        "hour",
        "minute",
        "second",
    )
    default_values = {
        "start_date": "*",
        "year": "*",
        "month": 1,
        "day": 1,
        "week": "*",
        "day_of_week": "*",
        "hour": 0,
        "minute": 0,
        "second": 0,
    }

    defaulted_schedule = {}
    assign_defaults = False
    for field_name in field_names:
        if field_name in schedule:
            value = schedule.pop(field_name)
            assign_defaults = not schedule
        elif assign_defaults:
            value = default_values[field_name]
        else:
            value = "*"
        # we don't need any * value fields as the utc schedule will be passed to apscheduler
        if value != "*":
            defaulted_schedule[field_name] = value

    return defaulted_schedule


def _charge_txn_type_fees(
    vault,
    postings,
    latest_balances,
    in_flight_balances,
    denomination,
    instructions,
    effective_date,
):
    """
    For a list of committed postings, checks whether any transaction-type fees exist and applies the
     highest out of the %-based or flat fee. Only applied to settlement, hard_settlement and
     transfer instructions
    :param vault:
    :param postings: List[PostingInstruction], postings to check for fees
    :param latest_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest balances as of
    beginning of hook execution
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest balances
    adjusted for any postings made during the current hook execution
    :param denomination: str, denomination for the fees
    :param instructions: List[PostingInstruction], extended with posting instructions for applicable
     fees
    :param effective_date: datetime, when the postings are being processed as-of. Used for parameter
    retrieval
    :return: None
    """

    supported_txn_types = _get_supported_txn_types(vault)
    txn_code_to_type_map = _get_parameter(name=TXN_CODE_TO_TYPE_MAP, is_json=True, vault=vault)
    txn_type_fees = _get_parameter(name=TXN_TYPE_FEES, is_json=True, vault=vault)

    # 'over_deposit_only' fees are charged if the txn amount exceeded deposit when txn was made
    # so we must get the deposit balance before we rebalanced any transactions and update it with
    # the txn amounts as we go
    deposit_balance_before_txn = _get_balance(
        latest_balances, address=DEPOSIT_BALANCE, denomination=denomination
    )

    for posting in postings:
        if posting.credit:
            continue

        # We're assuming fees are charged only on instructions that move settled funds.
        if posting.type not in (
            PostingInstructionType.SETTLEMENT,
            PostingInstructionType.HARD_SETTLEMENT,
            PostingInstructionType.TRANSFER,
        ):
            continue

        txn_type, _ = _get_txn_type_and_ref_from_posting(
            vault,
            posting.instruction_details,
            effective_date,
            supported_txn_types=supported_txn_types,
            txn_code_to_type_map=txn_code_to_type_map,
        )
        fees = txn_type_fees.get(txn_type, None)
        if not fees:
            continue

        income_account, loan_account = _get_fee_internal_accounts(vault, txn_type=txn_type)

        percentage_fee = Decimal(fees.get("percentage_fee", 0))
        flat_fee = Decimal(fees.get("flat_fee", 0))
        fee_cap = Decimal(fees.get("fee_cap", 0))
        fee_amount = 0

        combine_flat_and_percentage = _str_to_bool(fees.get("combine", "False"))
        over_deposit_only = _str_to_bool(fees.get("over_deposit_only", "False"))
        if not over_deposit_only or deposit_balance_before_txn < posting.amount:
            if combine_flat_and_percentage:
                fee_amount = sum((flat_fee, percentage_fee * posting.amount))
            else:
                fee_amount = max(flat_fee, percentage_fee * posting.amount)

        if fee_cap > 0:
            fee_amount = min(fee_amount, fee_cap)

        if fee_amount > Decimal(0):
            fee_type = f"{txn_type.upper()}_FEE"
            trigger = f"{posting.id}"

            _rebalance_fees(
                vault,
                fee_amount,
                denomination,
                in_flight_balances,
                income_account,
                loan_account,
                supported_txn_types,
                trigger,
                instructions,
                fee_type,
                txn_type=txn_type,
            )

        deposit_balance_before_txn -= posting.amount


def _check_txn_type_credit_limits(
    vault, balances, postings, denomination, effective_date, txn_code_to_type_map
):
    """
    Rejects any postings that breach their transaction type credit limit, which can be an absolute
    number or a percentage of the overall credit limit (e.g. cash advances may be limited to 25% of
    the credit limit, or a flat amount of 2000 in the relevant denomination). Accounts for existing
    charged, billed on unpaid transactions
    Note: this should be done last in pre-posting hook as it is more intensive than standard checks
    and we assume overall credit limit checks have passed
    :param vault:
    :param balances: DefaultDict[Tuple[str, str, str, Phase], Balance], balances to be used for
    limit checks. These should be live balances unless there is a specific reason otherwise
    :param postings: List[PostingInstruction], postings to check against transaction type limits
    :param denomination: str, account denomination
    :param effective_date: datetime, when the postings are being processed as-of. Used for parameter
    retrieval
    :param txn_code_to_type_map: Dict[str, str], map of transaction codes to transaction types
    :return: None, Raises Rejected exception if any transaction type limit is breached by a posting
    """

    txn_type_credit_limits = _get_parameter(
        name=TXN_TYPE_LIMITS, at=effective_date, is_json=True, vault=vault
    )
    if txn_type_credit_limits == {}:
        return

    credit_limit = _get_parameter(name=CREDIT_LIMIT, at=effective_date, vault=vault)
    # Defaulting the limits to the overall limit is safe as we've already done overall limit checks
    final_txn_type_credit_limits = {
        txn_type: min(
            Decimal(txn_type_credit_limits[txn_type].get("flat", credit_limit)),
            credit_limit * Decimal(txn_type_credit_limits[txn_type].get("percentage", 1)),
        )
        for txn_type in txn_type_credit_limits
    }

    proposed_amount_by_txn_type = defaultdict(lambda: 0)

    # get total amount in batch per transaction type
    for posting in postings:
        txn_type, _ = _get_txn_type_and_ref_from_posting(
            vault,
            posting.instruction_details,
            effective_date,
            txn_code_to_type_map=txn_code_to_type_map,
        )
        txn_type_credit_limit = final_txn_type_credit_limits.get(txn_type, 0)

        if txn_type_credit_limit and txn_type_credit_limit != credit_limit:
            # We assume a single denomination and asset across the account
            proposed_amount_by_txn_type[txn_type] += sum(
                balance.net
                for dimensions, balance in posting.balances().items()
                if dimensions[0] == DEFAULT_ADDRESS and dimensions[1] == DEFAULT_ASSET
            )

    # Get transaction types with references to ensure all relevant balances are checked
    txn_types_with_refs = _get_parameter(
        vault, TXN_REFS, at=effective_date, is_json=True, upper_case_list_values=True
    )

    # compare total amount per transaction type + existing balances to the transaction type limit
    for txn_type, proposed_amount in proposed_amount_by_txn_type.items():
        txn_type_map = {txn_type: txn_types_with_refs.get(txn_type, None)}
        current_txn_type_balance = _calculate_aggregate_balance(
            balances,
            denomination,
            fee_types=[],
            balance_def={PRINCIPAL: CHARGED_BALANCE_STATES},
            include_deposit=False,
            txn_type_map=txn_type_map,
        )
        # There will only be proposed amounts for txn types that have credit limits
        if (proposed_amount + current_txn_type_balance) > final_txn_type_credit_limits[txn_type]:
            raise Rejected(
                f"Insufficient funds for {denomination} {abs(proposed_amount)} transaction due to "
                f"{denomination} {final_txn_type_credit_limits[txn_type]:.2f} limit on transaction"
                f" type {txn_type}. Outstanding transactions amount to {denomination}"
                f" {abs(current_txn_type_balance)}",
                reason_code=RejectedReason.INSUFFICIENT_FUNDS,
            )


def _process_repayment(vault, posting, in_flight_balances, effective_date, instructions):
    """
    Creates instructions to process a repayment by updating:
     - principal and bank charge addresses
     - overdue addresses
     - deposit address
     - repayment tracker
    :param vault:
    :param posting: PostingInstruction, the repayment posting
    :param in_flight_balances: Dict[Tuple[str, str, str, Phase], Balance], balances including
    in-flight updates from postings made in the current hook execution, to be updated with postings
    :param effective_date: datetime, repayment effective date
    :param instructions: List[PostingInstruction], list of posting instructions to be extended with
    postings to handle repayment
    :return: None
    """
    total_repayment_amount, _ = _get_settlement_info(vault, posting)
    if total_repayment_amount == 0:
        return

    remaining_repayment_amount = _repay_spend_and_charges(
        in_flight_balances,
        effective_date,
        instructions,
        posting,
        total_repayment_amount,
        vault,
    )

    _repay_overdue_buckets(
        vault,
        posting.denomination,
        in_flight_balances,
        instructions,
        total_repayment_amount,
    )

    _make_deposit_postings(
        vault,
        posting.denomination,
        remaining_repayment_amount,
        in_flight_balances,
        {},
        instructions,
        trigger=f"REPAYMENT_RECEIVED_{posting.id}",
        gl_event="LOAN_DISBURSEMENT",
        is_repayment=True,
    )

    _update_total_repayment_tracker(
        in_flight_balances, instructions, posting, total_repayment_amount, vault
    )


def _update_total_repayment_tracker(in_flight_balances, instructions, post, amount_repaid, vault):
    """
    Create postings to update repayment address with current amount repaid in statement period.
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances, to be updated with posting instructions
    :param instructions: List[PostingInstruction], posting instructions to be extended
    :param post: PostingInstruction, the repayment posting
    :param amount_repaid: +ve Decimal, total amount repaid
    :param vault:
    :return: None
    """
    # Save how much we repaid before PDD - will be used to see if we repaid MAD
    if amount_repaid > 0:
        _make_internal_address_transfer(
            vault,
            amount=amount_repaid,
            denomination=post.denomination,
            credit_internal=True,
            custom_address=TRACK_STATEMENT_REPAYMENTS,
            instructions_to_extend=instructions,
            action="UPDATE_REPAYMENT_TRACKER",
            trigger=f"REPAYMENT_RECEIVED_{post.id}",
            in_flight_balances=in_flight_balances,
        )


def _repay_spend_and_charges(
    in_flight_balances,
    effective_date,
    instructions,
    posting,
    remaining_repayment_amount,
    vault,
):
    """
    Create postings to distribute the repayment amount using the repayment hierarchy
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution, to be
     updated with posting instructions
    :param effective_date: datetime, when the repayment is been made
    :param instructions: List[PostingInstruction], to be extended with repayment instructions
    :param posting: PostingInstruction, the repayment posting instruction
    :param remaining_repayment_amount: Decimal, total repayment to distribute
    :param vault:
    :return: Decimal, remaining repayment amount that has not been distributed
    """
    # Get supported spending types
    txn_types = _get_supported_txn_types(vault, effective_date)
    fee_types = _get_supported_fee_types(vault, txn_types)
    txn_stems = _construct_stems(txn_types)
    txn_repayment_hierarchy = _get_parameter(
        vault, TXN_APR, is_json=True, upper_case_dict_values=True
    )
    txn_type_repayment_hierarchy = _get_parameter(vault, APR, is_json=True)
    ordered_stems = _order_stems_by_repayment_hierarchy(
        txn_stems,
        txn_hierarchy=txn_repayment_hierarchy,
        txn_type_hierarchy=txn_type_repayment_hierarchy,
    )
    repayment_addresses = _get_repayment_addresses(REPAYMENT_HIERARCHY, ordered_stems, fee_types)
    denomination = posting.denomination
    total_repaid = 0
    # repay count for unique-enough CTIs as a repayment can be distributed to multiple addresses
    repay_count = 0

    # Track whether outstanding balance exceeds credit limit as this determines whether GL revocable
    # commitment postings need to be made or not
    credit_limit = _get_parameter(name=CREDIT_LIMIT, at=effective_date, vault=vault)
    outstanding_balance = _calculate_aggregate_balance(
        in_flight_balances,
        denomination,
        fee_types,
        balance_def=AGGREGATE_BALANCE_DEFINITIONS[OUTSTANDING_BALANCE],
        txn_type_map=txn_types,
        include_deposit=True,
    )
    remaining_credit_limit = credit_limit - outstanding_balance

    for (category, sub_category, address) in repayment_addresses:
        if remaining_repayment_amount > 0:
            balance = _get_balance(in_flight_balances, address=address, denomination=denomination)
            if balance > 0:
                parent_txn_type = _extract_txn_type_from_stem(vault, sub_category)
                balance_repayment = min(balance, remaining_repayment_amount)
                total_repaid += balance_repayment
                remaining_repayment_amount -= balance_repayment
                trigger = f"{posting.id}_{repay_count}"
                _make_internal_address_transfer(
                    vault,
                    balance_repayment,
                    denomination,
                    credit_internal=False,
                    custom_address=address,
                    action=f"REPAY_{address}",
                    trigger=f"REPAYMENT_RECEIVED_{trigger}",
                    instructions_to_extend=instructions,
                    in_flight_balances=in_flight_balances,
                )

                _make_repayment_gl_postings(
                    address,
                    denomination,
                    remaining_credit_limit,
                    balance_repayment,
                    category,
                    instructions,
                    trigger,
                    parent_txn_type,
                    vault,
                )
                remaining_credit_limit += balance_repayment
                repay_count += 1

    return remaining_repayment_amount


def _make_repayment_gl_postings(
    address,
    denomination,
    remaining_credit_limit,
    balance_repayment,
    charge_type,
    instructions,
    trigger,
    sub_type,
    vault,
):
    """
    Create gl postings for repayments. This excludes deposit postings as they are handled
    separately once all repayments have been processed
    :param address: str, address of the balance being repaid
    :param denomination: str, denomination for repayment posting to be created
    :param remaining_credit_limit: Decimal, remaining credit line that hasn't been spent,
    normally +ve
    :param balance_repayment: Decimal, amount repaid to the specific address, . <= balance amount
    :param charge_type: str, one of PRINCIPAL, FEES or INTEREST
    :param instructions: List[PostingInstruction], to be extended with repayment postings
    :param trigger: str, used as part of client transaction id to make it unique enough
    :param sub_type: str, for PRINCIPAL and INTEREST charge_type this is the transaction type,
     for FEES charge_type the fee type
    :param vault:
    :return: None
    """
    if remaining_credit_limit < 0:
        extra_limit_amount = min(-remaining_credit_limit, balance_repayment)
        credit_limit_amount = balance_repayment - extra_limit_amount
    else:
        extra_limit_amount = 0
        credit_limit_amount = balance_repayment

    if charge_type == PRINCIPAL:
        _make_principal_gl_postings(
            vault,
            credit_limit_amount,
            denomination,
            extra_limit_amount,
            instructions,
            trigger,
            sub_type,
            repayment=True,
        )
    if charge_type == INTEREST:
        # BILLED and UNPAID are identical from GL perspective, only need to check if it is CHARGED
        charge = address.endswith(CHARGED)
        is_fee = sub_type.endswith("_FEE")

        _make_interest_gl_postings(
            vault,
            credit_limit_amount,
            denomination,
            extra_limit_amount,
            instructions,
            charge_type=FEES if is_fee else charge_type,
            sub_type=sub_type,
            trigger=f'{"CHARGED" if charge else "BILLED"}_INTEREST_REPAID_{sub_type}_{trigger}',
            bill=not charge,
            repayment=True,
        )
    if charge_type == FEES:
        txn_type = _get_fee_txn_type(sub_type)
        external_fee_types = _get_parameter(vault, name=EXTERNAL_FEE_TYPES, is_json=True)
        is_external_fee = sub_type.lower() in external_fee_types
        income_account, loan_account = _get_fee_internal_accounts(
            vault, sub_type, txn_type, is_external_fee
        )
        _make_fee_gl_postings(
            vault,
            credit_limit_amount,
            denomination,
            extra_limit_amount,
            f"FEES_REPAID_{sub_type}_{trigger}",
            income_account,
            instructions,
            loan_account,
            txn_type=None,
            is_external_fee=is_external_fee,
            is_repayment=True,
        )


def _get_repayment_addresses(repayment_hierarchy, txn_types, fee_types):
    """
    Get a list of balance addresses that will be posted to for repayment.
    :param repayment_hierarchy: List[Dict[str, str]], list of entries that constitute the hierarchy.
    Each entry has:
    - 'repayment_type' key-value pair (BANK_CHARGE or PRINCIPAL)
    - an optional 'bank_charge_type' key-value pair (FEES or INTEREST) to clarify the bank charge
     type if the repayment type is BANK_CHARGE
    - 'statuses' key-value pair (List of balance statuses) to indicate which balance statuses are
    in-scope
    :param txn_types: List[str], list of transaction types ordered by decreasing APR
    :param fee_types: List[str], list of fee types
    :return: List[Tuple[str, str, str]], ordered list of (category, sub-category, address) tuples
    to repay to
    """
    addresses = []

    def construct_addresses(address_callback, category, supported_sub_categories, balance_status):
        """
        Build list of addresses for repayment.
        :param address_callback:
        :param category:
        :param supported_sub_categories:
        :param balance_status:
        :return:
        """
        return [
            (category, sub_category, address_callback(sub_category, status))
            for sub_category in supported_sub_categories
            for status in balance_status
        ]

    for entry in repayment_hierarchy:
        repayment_type = entry["repayment_type"]
        statuses = entry["statuses"]
        bank_charge_type = None if repayment_type == PRINCIPAL else entry["bank_charge_type"]

        if repayment_type == PRINCIPAL:
            addresses.extend(
                construct_addresses(_principal_address, repayment_type, txn_types, statuses)
            )
        elif repayment_type == BANK_CHARGE:
            if bank_charge_type == INTEREST:
                addresses.extend(
                    construct_addresses(_interest_address, bank_charge_type, txn_types, statuses)
                )
                addresses.extend(
                    construct_addresses(_interest_address, bank_charge_type, fee_types, statuses)
                )
            elif bank_charge_type == FEES:
                addresses.extend(
                    construct_addresses(_fee_address, bank_charge_type, fee_types, statuses)
                )

    return addresses


def _repay_overdue_buckets(vault, denomination, in_flight_balances, instructions, repayment_amount):
    """
    Create postings to distribute repayment from oldest overdue bucket to newest overdue bucket.
    :param vault:
    :param denomination: str, denomination for repayment
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], the balances to
    use to determine overdue amounts and to be updated with the resulting instructions
    :param instructions: List[PostingInstruction], list of instructions to be extended
    :param repayment_amount: +ve Decimal, repayment amount to distribute
    :return: None
    """

    existing_overdue_addresses = {
        dimensions[0]: amount.net
        for dimensions, amount in in_flight_balances.items()
        if dimensions[0].startswith(OVERDUE)
    }

    # the oldest bucket should be paid off first, as this will decrease the days past due if repaid
    # in full
    overdue_addresses = sorted(
        existing_overdue_addresses.keys(), key=lambda x: -_get_overdue_address_age(x)
    )
    for overdue_address in overdue_addresses:
        amount = min(repayment_amount, existing_overdue_addresses[overdue_address])
        if amount != 0:
            repayment_amount -= amount
            _make_internal_address_transfer(
                amount=amount,
                denomination=denomination,
                credit_internal=False,
                custom_address=overdue_address,
                action=f"REPAY_{overdue_address}",
                trigger="REPAYMENT_RECEIVED",
                vault=vault,
                instructions_to_extend=instructions,
                in_flight_balances=in_flight_balances,
            )
        if repayment_amount == 0:
            break


def _create_postings(
    vault,
    amount,
    instructions,
    from_account_id,
    to_account_id,
    action="",
    denomination=None,
    from_address=DEFAULT_ADDRESS,
    instruction_details=None,
    to_address=DEFAULT_ADDRESS,
    trigger="",
    in_flight_balances=None,
):
    """
    Generic wrapper around vault.make_internal_transfer_instructions to ensure consistency in
    client transaction ids, restriction overrides, and updating in_flight_balances.
    :param vault:
    :param amount: Decimal, amount to debit/credit from the accounts
    :param instructions: List[PostingInstruction], instructions to be extended with the created
    postings
    :param from_account_id: str, account being debited
    :param to_account_id: str, account being credited
    :param action: str, describes the action performed by the postings. Preferably a business
    relevant term
    :param denomination: str, posting denomination
    :param from_address: str, balance address for the from_account_id posting
    :param instruction_details: Optional[Dict[str, str]], metadata for the postings
    :param to_address: str, balance address for the to_account_id posting
    :param trigger: str, describes what is causing the action. Must make the client-transaction-id
     unique enough
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], the balances to
    be updated with the resulting instructions
    return: None
    """
    if amount == 0:
        return

    denomination = denomination or _get_parameter(vault, "denomination")
    instruction_details = instruction_details or {}
    client_txn_id = _cti(vault, action=action, trigger=trigger)

    new_instructions = vault.make_internal_transfer_instructions(
        amount=amount,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        from_account_id=from_account_id,
        from_account_address=from_address,
        to_account_id=to_account_id,
        to_account_address=to_address,
        client_transaction_id=client_txn_id,
        instruction_details=instruction_details,
        override_all_restrictions=True,
    )

    if in_flight_balances:
        _update_balances(vault.account_id, in_flight_balances, new_instructions)

    instructions.extend(new_instructions)


def _make_internal_address_transfer(
    vault,
    amount,
    denomination,
    credit_internal,
    custom_address,
    instruction_details=None,
    instructions_to_extend=None,
    action=None,
    trigger=None,
    in_flight_balances=None,
):
    """
    Create postings that move funds between current account's INTERNAL address and another address
    :param vault:
    :param amount: Decimal, amount to transfer
    :param denomination: str, the account denomination
    :param credit_internal: bool, True if crediting INTERNAL and false if debiting INTERNAL
    :param custom_address: str,  address to transfer to/from the INTERNAL address.
    :param instruction_details: Optional[Dict[str, str]], metadata to be added to the instructions
    :param instructions_to_extend: Optional[List[PostingInstruction], list of posting instructions
     to be extended with postings to handle transfer
    :param action: str, describes the action performed by the fund movement
    :param trigger: str, describes what triggered the action. Must make the client-transaction-id
     unique enough
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], the balances to
    be updated with the resulting instructions
    :return: None
    """
    if amount <= 0:
        return

    to_address = INTERNAL_BALANCE if credit_internal else custom_address
    from_address = custom_address if credit_internal else INTERNAL_BALANCE
    action = action or f"{from_address}_TO_{to_address}"

    _create_postings(
        vault,
        amount,
        instructions_to_extend,
        from_account_id=vault.account_id,
        to_account_id=vault.account_id,
        action=action,
        denomination=denomination,
        from_address=from_address,
        instruction_details=instruction_details,
        to_address=to_address,
        trigger=trigger,
        in_flight_balances=in_flight_balances,
    )


def _calculate_aggregate_balance(
    balances, denomination, fee_types, balance_def, include_deposit, txn_type_map=None
):
    """
    Sums up individual balances based on a definition that specifies which balance states are
    in-scope for principal, fees and interest balances, and a list of relevant transaction types
    and fee types
    :param balances: DefaultDict[Tuple[str, str, str, Phase], Balance], balances to calculate the
    aggregate from
    :param denomination: str, the balance denomination
    :param fee_types: List[str], list of fee types to be included for fees
    :param balance_def: Dict[str, Any], Valid key-value pairs:
        -  balance type (PRINCIPAL, FEES, INTEREST) to list of balance states (AUTH, CHARGED,
         UNCHARGED, BILLED, UNPAID) to be included in the aggregate calculation
        - 'offset' to name of kwarg whose value can be included in the aggregate calculation as an
        offset
    :param include_deposit: bool, if True the deposit balance is included in the calculation
    :param txn_type_map: Optional[Dict[str, Optional[List[str]]]], map of transaction types to list
    of refs to be included for Principal and Interest
    :return: Decimal, the value of the aggregate balance
    """
    txn_states = balance_def.get(PRINCIPAL, [])
    fee_states = balance_def.get(FEES, [])
    interest_states = balance_def.get(INTEREST, [])

    principal_addresses = []
    interest_addresses = []
    fee_addresses = []
    txn_type_map = txn_type_map or {}

    def _build_addresses_for_states(method_name, addresses, states, txn_type, txn_refs=None):
        """
        Append formed addresses to provided list for later use.
        :param method_name: str, name of method to be called for address creation
        :param addresses: List[str], list of addresses to be appended to
        :param states: List[str], list of states to be iterated
        :param txn_type: str, transaction type
        :param txn_refs: Optional[List[str]], list of transaction references (if present)
        """
        for state in states:
            if txn_refs:
                for ref in txn_refs:
                    addresses.append(method_name(txn_type.upper(), state, txn_ref=ref))
            else:
                addresses.append(method_name(txn_type.upper(), state))

    for txn_type, txn_refs in txn_type_map.items():
        _build_addresses_for_states(
            _principal_address, principal_addresses, txn_states, txn_type, txn_refs
        )
        _build_addresses_for_states(
            _interest_address, interest_addresses, interest_states, txn_type, txn_refs
        )

    for fee_type in fee_types:
        _build_addresses_for_states(_fee_address, fee_addresses, fee_states, fee_type)
        _build_addresses_for_states(
            _interest_address, interest_addresses, interest_states, fee_type
        )

    offset = 0
    if include_deposit:
        # Deposit balance is subtracted as it's money owed to the customer rather than owed by them
        offset -= balances[DEPOSIT_BALANCE, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
    aggregate_balance = offset + sum(
        [
            v.net
            for (k, v) in balances.items()
            if k[0] in principal_addresses + fee_addresses + interest_addresses
            and k[2] == denomination
        ]
    )

    return aggregate_balance


def _adjust_aggregate_balances(
    denomination,
    in_flight_balances,
    instructions,
    vault,
    trigger="",
    effective_datetime=None,
    available=True,
    outstanding=True,
    full_outstanding=True,
    **kwargs,
):
    """
    Helper to adjust aggregate balances for available, outstanding and full outstanding addresses
    :param denomination: str, account denomination
    :param in_flight_balances: Dict[Tuple[str, str, str, Phase], Balance], latest balances to be
    updated with instructions
    :param instructions, List[PostingInstruction], list of posting instructions to be extended with
    revolver postings
    :param vault:
    :param trigger: str, describes what is causing the postings. Must make the client-transaction-id
     unique enough
    :param effective_datetime: datetime, datetime to fetch parameter values as of
    :param available: bool, set to True to adjust available balance
    :param outstanding: bool, set to True to adjust outstanding balance
    :param full_outstanding: bool, set to True to adjust full outstanding balance
    :param kwargs: additional kwargs to pass into the aggregate balance calculation
    """

    txn_types = _get_supported_txn_types(vault, effective_datetime)
    fee_types = _get_supported_fee_types(vault, txn_types)

    scope = {
        AVAILABLE_BALANCE: available,
        OUTSTANDING_BALANCE: outstanding,
        FULL_OUTSTANDING_BALANCE: full_outstanding,
    }

    for aggregate_address, is_in_scope in scope.items():
        if not is_in_scope:
            continue
        else:
            new_amount = _calculate_aggregate_balance(
                in_flight_balances,
                denomination,
                fee_types,
                balance_def=AGGREGATE_BALANCE_DEFINITIONS[aggregate_address],
                include_deposit=True,
                txn_type_map=txn_types,
            )

            # For available balance include the credit limit
            if aggregate_address in ["AVAILABLE_BALANCE"]:
                credit_limit = kwargs.get("credit_limit", 0)
                new_amount = credit_limit - new_amount

            _override_info_balance(
                vault,
                in_flight_balances=in_flight_balances,
                balance_address=aggregate_address,
                denomination=denomination,
                amount=new_amount,
                instructions=instructions,
                trigger=trigger,
            )

    if (
        _get_balance(
            in_flight_balances,
            denomination=denomination,
            address=FULL_OUTSTANDING_BALANCE,
        )
        <= 0
        and scope[FULL_OUTSTANDING_BALANCE]
    ):
        _change_revolver_status(
            vault,
            denomination,
            in_flight_balances,
            revolver=False,
            instructions=instructions,
            trigger="FULL_OUTSTANDING_REPAID",
        )


def _change_revolver_status(
    vault, denomination, in_flight_balances, revolver, instructions, trigger=None
):
    """
    Creates instructions to set or unset an account as revolving
    :param vault:
    :param denomination: str, account denomination
    :param in_flight_balances: Dict[Tuple[str, str, str, Phase], Balance], latest balances to be
    updated with instructions
    :param revolver: bool, set to True to set an account as revolving, False to unset revolving
    :param instructions, List[PostingInstruction], list of posting instructions to be extended with
    revolver postings
    :return: None
    """
    # guarantee we don't 'overset/underset' the Revolver balance
    if revolver == _is_revolver(in_flight_balances, denomination):
        return

    action = "SET_REVOLVER" if revolver else "UNSET_REVOLVER"

    _make_internal_address_transfer(
        vault,
        amount=Decimal(1),
        denomination=denomination,
        custom_address=REVOLVER_BALANCE,
        credit_internal=not revolver,
        instructions_to_extend=instructions,
        action=action,
        trigger=trigger,
        in_flight_balances=in_flight_balances,
    )


def _rebalance_release(vault, post, in_flight_balances, effective_timestamp, instructions):
    """
    When an outbound authorisation is released, create postings to:
    - zero out corresponding _AUTH balances
    :param vault:
    :param post: PostingInstruction, the release posting to rebalance
    :param in_flight_balances: Dict[Tuple[str, str, str, Phase], Balance], latest balances to be
    updated with instructions
    :param effective_timestamp: datetime, datetime as of which rebalancing is happening
    :param instructions: List[PostingInstruction], list of posting instructions to be extended
    :return: None
    """
    # Get remaining authorised amount from client_transaction and remove this from Auth balance
    amount = _get_unsettled_amount(vault, post)
    if amount == 0:
        return []

    txn_type, _ = _get_txn_type_and_ref_from_posting(
        vault, post.instruction_details, effective_timestamp, upper_case_type=True
    )
    balance_address = _principal_address(txn_type, AUTH)

    _make_internal_address_transfer(
        vault,
        amount=amount,
        denomination=post.denomination,
        credit_internal=False,
        custom_address=balance_address,
        action="RELEASE_AUTH",
        trigger=f"RELEASE_{post.id}",
        instruction_details=post.instruction_details,
        instructions_to_extend=instructions,
        in_flight_balances=in_flight_balances,
    )


def _rebalance_auth_adjust(vault, post, in_flight_balances, effective_timestamp, instructions):
    """
    When an outbound authorisation is adjusted, create postings to:
    - adjust any corresponding _AUTH balances, increasing absolute value for increased auths and
    decreasing absolute value for decreased auths
    :param vault:
    :param post: PostingInstruction, the outbound auth adjust posting to rebalance
    :param in_flight_balances: Dict[Tuple[str, str, str, Phase], Balance], latest balances to be
    updated with instructions
    :param effective_timestamp: datetime, datetime as of which rebalancing is happening
    :param instructions: List[PostingInstruction], list of posting instructions to be extended
    :return: None
    """
    txn_type, _ = _get_txn_type_and_ref_from_posting(
        vault, post.instruction_details, effective_timestamp, upper_case_type=True
    )
    balance_address = _principal_address(txn_type, AUTH)

    if post.credit:
        # auth less spend
        credit_internal = False
        action = "DECREASE_AUTH"
    else:
        # auth more spend
        credit_internal = True
        action = "INCREASE_AUTH"

    _make_internal_address_transfer(
        vault,
        amount=post.amount,
        denomination=post.denomination,
        credit_internal=credit_internal,
        custom_address=balance_address,
        action=action,
        trigger=f"AUTH_ADJUST_{post.client_transaction_id}",
        instruction_details=post.instruction_details,
        instructions_to_extend=instructions,
        in_flight_balances=in_flight_balances,
    )


def _rebalance_outbound_auth(vault, post, in_flight_balances, effective_timestamp, instructions):
    """
    When a transaction is authorised create postings to:
    - adjust any corresponding _AUTH balances
    :param vault:
    :param post: PostingInstruction, the outbound auth posting to rebalance
    :param in_flight_balances: Dict[Tuple[str, str, str, Phase], Balance], latest balances to be
    updated with instructions
    :param effective_timestamp: datetime, datetime as of which rebalancing is happening
    :param instructions: List[PostingInstruction], list of posting instructions to be extended
    :return: None
    """
    txn_type, txn_ref = _get_txn_type_and_ref_from_posting(
        vault, post.instruction_details, effective_timestamp, upper_case_type=True
    )
    balance_address = _principal_address(txn_type, AUTH, txn_ref=txn_ref)

    _make_internal_address_transfer(
        amount=post.amount,
        denomination=post.denomination,
        custom_address=balance_address,
        credit_internal=True,
        action="AUTH_TXN",
        trigger=f"AUTH_{post.id}",
        instruction_details=post.instruction_details,
        instructions_to_extend=instructions,
        vault=vault,
        in_flight_balances=in_flight_balances,
    )


def _rebalance_settlement(vault, posting, in_flight_balances, effective_timestamp, instructions):
    """
    When a transaction is settled create postings to:
    - adjust any corresponding _AUTH balances
    - take the spend out of either DEPOSIT or _CHARGED balances
    :param vault:
    :param posting: PostingInstruction, the settlement to rebalance
    :param in_flight_balances: Dict[Tuple[str, str, str, Phase], Balance], latest balances to be
    updated with instructions
    :param effective_timestamp: datetime, datetime as of which rebalancing is happening
    :param instructions: List[PostingInstruction], list of posting instructions to be extended with
    postings to handle settlement
    :return: None
    """
    txn_types = _get_supported_txn_types(vault, effective_timestamp)
    external_fee_types = _get_parameter(vault, name=EXTERNAL_FEE_TYPES, is_json=True)
    fee_type = posting.instruction_details.get(FEE_TYPE, "")
    if fee_type.lower() in external_fee_types:
        _charge_fee(
            vault,
            posting.denomination,
            in_flight_balances,
            instructions,
            fee_type,
            txn_types,
            posting.amount,
            is_external_fee=True,
            trigger=posting.id,
        )
        return

    fee_types = _get_supported_fee_types(vault, txn_types)
    txn_type, txn_ref = _get_txn_type_and_ref_from_posting(
        vault,
        posting.instruction_details,
        effective_timestamp,
        supported_txn_types=txn_types,
        upper_case_type=True,
    )

    credit_limit = _get_parameter(name=CREDIT_LIMIT, at=effective_timestamp, vault=vault)

    amount_to_settle, unsettled_amount = _get_settlement_info(vault, posting)

    credit_line_spend, extra_limit_spend, deposit_spend = _determine_amount_breakdown(
        amount_to_settle,
        credit_limit,
        posting.denomination,
        fee_types,
        in_flight_balances,
        txn_types,
    )

    if posting.type == PostingInstructionType.SETTLEMENT:
        _update_auth_bucket_for_settlement(
            vault,
            posting,
            credit_line_spend + extra_limit_spend + deposit_spend,
            unsettled_amount,
            in_flight_balances,
            txn_type,
            txn_ref,
            instructions,
        )
    trigger = f"PRINCIPAL_SPENT_{txn_type}_{posting.id}"

    if credit_line_spend + extra_limit_spend > 0:
        # We only debit the principal address (e.g. PURCHASE_CHARGED) and make gl postings if the
        # posting amount exceeds the available deposit
        address = _principal_address(txn_type, CHARGED, txn_ref=txn_ref)
        stem = f"{txn_type}_{txn_ref}" if txn_ref else txn_type
        action = f"CHARGE_{stem}_TO_{address}"
        _make_internal_address_transfer(
            vault,
            amount=credit_line_spend + extra_limit_spend,
            denomination=posting.denomination,
            custom_address=address,
            credit_internal=True,
            action=action,
            trigger=trigger,
            instruction_details=posting.instruction_details,
            instructions_to_extend=instructions,
            in_flight_balances=in_flight_balances,
        )

        _make_principal_gl_postings(
            credit_line_spend=credit_line_spend,
            denomination=posting.denomination,
            extra_limit_spend=extra_limit_spend,
            instructions=instructions,
            trigger=posting.id,
            repayment=False,
            stem=stem,
            vault=vault,
        )

    _make_deposit_postings(
        vault,
        posting.denomination,
        deposit_spend,
        in_flight_balances,
        {},
        instructions,
        trigger,
        "LOAN_DISBURSEMENT",
        txn_type,
    )


def _make_deposit_postings(
    vault,
    denomination,
    amount,
    in_flight_balances,
    instruction_details,
    instructions,
    trigger,
    gl_event=None,
    txn_type=None,
    is_repayment=False,
):
    """
    Make postings to rebalance the deposit address and update GL when spending from/repaying to
    the deposit balance
    :param vault:
    :param denomination: str, denomination of the deposit balance
    :param amount: Decimal, +ve amount being spent/repaid
    :param in_flight_balances: Dict[Tuple[str, str, str, Phase], Balance], latest balances to be
    updated with postings
    :param instruction_details: Dict[str, str], metadata to add to postings
    :param instructions: List[PostingInstruction], instructions to be extended with the postings
    :param trigger: str, describes what is causing the postings. Must make the client-transaction-id
     unique enough
    :param gl_event: Optional[str], the GL event associated to the deposit spend/repay. Not required
    if is_repayment is True
    :param txn_type: Optional[str], transaction type associated to the deposit spend
    :param is_repayment: Optional[bool], True if repaying to deposit, False if spending from deposit
    :return: None
    """

    if amount == 0:
        return

    _make_internal_address_transfer(
        amount=amount,
        denomination=denomination,
        credit_internal=is_repayment,  # if repaying, debit DEPOSIT_BALANCE to make it more positive
        custom_address=DEPOSIT_BALANCE,
        action=f"REBALANCE_{DEPOSIT_BALANCE}",
        trigger=trigger,
        in_flight_balances=in_flight_balances,
        instruction_details=instruction_details,
        instructions_to_extend=instructions,
        vault=vault,
    )

    instruction_details = _gl_posting_metadata(
        gl_event, vault.account_id, repayment=is_repayment, txn_type=txn_type
    )
    other_liability_account = _get_parameter(name=OTHER_LIABILITY_INTERNAL_ACCOUNT, vault=vault)

    if is_repayment:
        from_account_id = vault.account_id
        from_address = INTERNAL_BALANCE
        to_account_id = other_liability_account
        to_address = DEFAULT_ADDRESS
        action = "CUSTOMER_TO_OTHER_LIABILITY_GL"
    else:
        from_account_id = other_liability_account
        from_address = DEFAULT_ADDRESS
        to_account_id = vault.account_id
        to_address = INTERNAL_BALANCE
        action = "OTHER_LIABILITY_TO_CUSTOMER_GL"

    _create_postings(
        vault,
        amount,
        instructions,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        action=action,
        denomination=denomination,
        from_address=from_address,
        instruction_details=instruction_details,
        to_address=to_address,
        trigger=trigger,
    )


def _make_principal_gl_postings(
    vault,
    credit_line_spend,
    denomination,
    extra_limit_spend,
    instructions,
    trigger,
    stem,
    repayment=False,
):
    """
    Creates correct internal account postings that feed the GL for settled spend:
    - DR transaction-type specific account and CR local INTERNAL address for any credit line spend
    - DR off b/s contra and CR Revocable Commitment for any credit line spend
    - for deposit spend: TBC
    :param vault:
    :param credit_line_spend: Decimal, amount being spent/repaid within credit line
    :param denomination: str, account denomination
    :param extra_limit_spend: Decimal, amount being spent/repaid beyond credit limit
    :param instructions: List[PostingInstruction], to be extended with internal account postings
    :param trigger: str, describes what is causing the postings. Must make the client-transaction-id
     unique enough
    :param stem: str, transaction type for the spend/repayment (with reference appended if present)
    :param repayment: bool, set to True if creating postings for principal repayment
    :return:
    """
    # Check to see if provided sub_category (and address) has a transaction reference
    parent_txn_type = _extract_txn_type_from_stem(vault, stem)

    txn_type_internal_account_map = _get_parameter(
        name=TXN_TYPE_INTERNAL_ACCOUNTS_MAP, is_json=True, vault=vault
    )

    txn_type_internal_account = txn_type_internal_account_map[parent_txn_type.lower()]
    gl_event = "LOAN_DISBURSEMENT"
    instruction_details = _gl_posting_metadata(
        gl_event, vault.account_id, repayment=repayment, txn_type=parent_txn_type
    )

    trigger = (
        f'{"PRINCIPAL_REPAID" if repayment else "PRINCIPAL_SPENT"}' f"_{parent_txn_type}_{trigger}"
    )

    if credit_line_spend + extra_limit_spend > 0:
        _make_off_bs_internal_account_postings(
            vault,
            credit_line_spend,
            denomination,
            instructions,
            instruction_details,
            trigger,
            increase_commitment=repayment,
        )

        _make_loan_balance_to_customer_account_postings(
            vault,
            credit_line_spend + extra_limit_spend,
            denomination,
            trigger,
            instruction_details,
            instructions,
            repayment,
            txn_type_internal_account,
        )


def _make_loan_balance_to_customer_account_postings(
    vault,
    credit_line_spend,
    denomination,
    trigger,
    instruction_details,
    instructions,
    repayment=False,
    loan_account="",
):
    """
    DR Customer INTERNAL CR Loan Account, or vice-versa for repayment
    :param vault:
    :param credit_line_spend: Decimal, amount being spent from credit line(or repaid to outstanding
     balance for repayments)
    :param denomination: str, account denomination
    :param trigger: str, describes what is causing the postings. Must make the client-transaction-id
     unique enough
    :param instruction_details: Dict[str, str], metadata for the internal account postings
    :param instructions: List[PostingInstruction], to be extended with internal account postings
    :param repayment: bool, true if repayment
    :param loan_account: str, account id for the relevant loan account
    :return: None
    """

    if repayment:
        from_account_id = vault.account_id
        from_account_address = INTERNAL_BALANCE
        to_account_id = loan_account
        to_account_address = DEFAULT_ADDRESS
        action = "LOAN_TO_CUSTOMER_GL"
    else:
        # The finance requirement is DR transaction-type specific account and CR suspense account
        # The original posting is CR suspense and DR local DEFAULT, so we mirror via local INTERNAL
        from_account_id = loan_account
        from_account_address = DEFAULT_ADDRESS
        to_account_id = vault.account_id
        to_account_address = INTERNAL_BALANCE
        action = "CUSTOMER_TO_LOAN_GL"

    _create_postings(
        vault,
        credit_line_spend,
        instructions,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        action=action,
        denomination=denomination,
        from_address=from_account_address,
        instruction_details=instruction_details,
        to_address=to_account_address,
        trigger=trigger,
    )


def _make_interest_gl_postings(
    vault,
    credit_line_amount,
    denomination,
    extra_limit_amount,
    instructions,
    charge_type,
    sub_type,
    trigger="",
    local_accrual_cut_off_date=None,
    bill=False,
    repayment=False,
):
    """
    Creates postings that feed the GL for interest
    :param vault:
    :param credit_line_amount: Decimal, interest drawn from credit line
    :param denomination: str, interest accrual denomination
    :param extra_limit_amount: Decimal, interest drawn beyond credit line, not necessarily overlimit
    :param instructions: List[PostingInstruction], list of instructions to extend with internal
    account postings
    :param trigger: str, describes what is causing the postings. Must make the client-transaction-id
     unique enough
    :param charge_type: str, one of PRINCIPAL, FEES or INTEREST
    :param sub_type: str, the transaction or fee type for the charged interest we're processing
    :param local_accrual_cut_off_date: Optional[date], the local accrual cut off - used to populate
    the interest value date on GL posting metadata
    :param bill: bool, True if dealing with billed or unpaid interest. False if charged interest
    :param repayment: bool, True if the interest is being repaid
    :return: None
    """

    total_amount = credit_line_amount + extra_limit_amount
    if total_amount == 0:
        return

    air_account, income_account, loan_account = _get_interest_internal_accounts(
        charge_type, sub_type, vault
    )
    instruction_details = _gl_posting_metadata(
        "LOAN_CHARGED_INTEREST",
        vault.account_id,
        repayment=repayment,
        txn_type=sub_type,
        interest_value_date=local_accrual_cut_off_date,
    )

    to_address = DEFAULT_ADDRESS
    if not bill:
        if repayment:
            from_account_id = vault.account_id
            from_address = INTERNAL_BALANCE
            to_account_id = air_account
            action = "CUSTOMER_TO_AIR"
        else:
            from_account_id = air_account
            from_address = DEFAULT_ADDRESS
            to_account_id = income_account
            action = "AIR_TO_INCOME_GL"
    else:
        if repayment:
            from_account_id = vault.account_id
            from_address = INTERNAL_BALANCE
            to_account_id = loan_account
            action = "CUSTOMER_TO_LOAN_GL"
        else:
            from_account_id = loan_account
            from_address = DEFAULT_ADDRESS
            to_account_id = air_account
            action = "LOAN_TO_AIR_GL"

        # only needed for billed interest as charged interest doesn't affect available balance
        _make_off_bs_internal_account_postings(
            vault,
            credit_line_amount,
            denomination,
            instructions,
            instruction_details,
            trigger,
            increase_commitment=repayment,
        )

    _create_postings(
        vault,
        total_amount,
        denomination=denomination,
        from_account_id=from_account_id,
        from_address=from_address,
        to_account_id=to_account_id,
        to_address=to_address,
        instruction_details=instruction_details,
        instructions=instructions,
        action=action,
        trigger=trigger,
    )


def _get_interest_internal_accounts(charge_type, sub_type, vault):
    """
    Helper to retrieve the air, income and loan principal accounts for a given transaction type
    :param charge_type: str, one of PRINCIPAL, FEES or INTEREST
    :param txn_type: str, transaction type or fee type to retrieve accounts for
    :param vault:
    :return: Tuple[str, str, str], the air, income and loan principal account ids
    """
    if charge_type == FEES:
        fees_interest_internal_accounts = _get_parameter(
            name=INTEREST_ON_FEES_INTERNAL_ACCOUNTS_MAP, is_json=True, vault=vault
        )
        air_account = fees_interest_internal_accounts["air"]
        income_account = fees_interest_internal_accounts["income"]
        loan_internal_account = fees_interest_internal_accounts["loan"]

    else:
        txn_type_interest_internal_account_map = _get_parameter(
            name=TXN_TYPE_INTEREST_INTERNAL_ACCOUNTS_MAP, is_json=True, vault=vault
        )
        txn_type_interest_internal_accounts = txn_type_interest_internal_account_map[
            sub_type.lower()
        ]

        air_account = txn_type_interest_internal_accounts["air"]
        income_account = txn_type_interest_internal_accounts["income"]

        txn_type_internal_accounts_map = _get_parameter(
            name=TXN_TYPE_INTERNAL_ACCOUNTS_MAP, is_json=True, vault=vault
        )

        loan_internal_account = txn_type_internal_accounts_map[sub_type.lower()]

    return air_account, income_account, loan_internal_account


def _gl_posting_metadata(
    event, account_id, repayment=False, txn_type=None, interest_value_date=None
):
    """
    Helper to create GL posting metadata consistently
    :param event: str, GL event
    :param account_id: str, the customer account id the GL posting is made for
    :param repayment: bool, True if this is a repayment
    :param txn_type: Optional[str], transaction type for posting if applicable
    :param interest_value_date: Optional[date], interest value date for the posting if applicable
    :return: Dict[str, str], the GL posting metadata
    """

    instruction_details = {
        "accounting_event": "LOAN_REPAYMENT" if repayment else event,
        "account_id": account_id,
    }

    if txn_type:
        instruction_details["inst_type"] = txn_type.lower()

    if interest_value_date:
        instruction_details["interest_value_date"] = str(interest_value_date)

    return instruction_details


def _get_fee_txn_type(fee_type):
    """
    Determine whether a fee type is transaction related and returns the transaction type if relevant
    :param fee_type: str, the fee type to check
    :return: Union[str, None], transaction_type if applicable or None otherwise
    """
    # FEE_TYPES constant doesn't include transaction type fees as these are parameterised
    if fee_type in INTERNAL_FEE_TYPES:
        return None

    return fee_type.replace("_FEE", "")


def _make_fee_gl_postings(
    vault,
    credit_line_amount,
    denomination,
    extra_limit_amount,
    trigger,
    income_account,
    instructions,
    loan_account,
    txn_type=None,
    is_external_fee=False,
    is_repayment=False,
):
    """
    Creates postings that feed the GL for fees.
    :param vault:
    :param credit_line_amount: Decimal, amount of interest being charged from credit limit
    :param denomination: str, fee denomination
    :param extra_limit_amount: Decimal, amount of interest being charged beyond credit limit
    :param trigger: str, describes what is causing the postings. Must make the client-transaction-id
     unique enough
    :param income_account: str, the income account id for the fee type
    :param instructions: List[PostingInstruction], to be extended with postings
    :param loan_account: str, the loan account id for the fee type
    :param txn_type: Optional[str], the transaction type for the fee, if applicable
    :param is_external_fee: bool, set to True if this is an external fee, False otherwise
    :param is_repayment: bool, True if the fee is being repaid
    :return: None
    """

    total_amount = credit_line_amount + extra_limit_amount
    if total_amount == 0:
        return

    instruction_details = _gl_posting_metadata(
        "LOAN_FEES", vault.account_id, repayment=is_repayment, txn_type=txn_type
    )

    if is_repayment:
        # internal contra to loan
        from_account_id = vault.account_id
        from_address = INTERNAL_BALANCE
        to_account_id = loan_account
        to_address = DEFAULT_ADDRESS
        action = "CUSTOMER_TO_LOAN_GL"
    else:
        from_account_id = loan_account
        from_address = DEFAULT_ADDRESS
        if is_external_fee:
            # Fees initiated externally follow the same GL posting flows as transactions
            # Finance requirement is DR loan account and CR income account
            # Original posting is CR income and DR local DEFAULT, so we mirror via local INTERNAL
            to_account_id = vault.account_id
            to_address = INTERNAL_BALANCE
            action = "LOAN_TO_CUSTOMER_GL"
        else:
            to_account_id = income_account
            to_address = DEFAULT_ADDRESS
            action = "LOAN_TO_INCOME_GL"

    _create_postings(
        vault,
        total_amount,
        denomination=denomination,
        instructions=instructions,
        from_account_id=from_account_id,
        from_address=from_address,
        to_account_id=to_account_id,
        to_address=to_address,
        action=action,
        trigger=trigger,
        instruction_details=instruction_details,
    )

    _make_off_bs_internal_account_postings(
        vault,
        credit_line_amount,
        denomination,
        instructions,
        instruction_details,
        trigger,
        increase_commitment=is_repayment,
    )


def _make_credit_limit_change_gl_postings(
    vault, denomination, new_credit_limit, old_credit_limit, instructions
):
    """
    Create GL postings that feed the GL for credit limit changes
    - When increasing credit limit, increase the commitment
    - When decreasing credit limit: decrease the commitment
    :param vault:
    :param denomination: str, credit limit denomination
    :param new_credit_limit: Decimal, the new credit limit
    :param old_credit_limit: Decimal, the old credit limit
    :param instructions: List[PostingInstruction], extended with internal account postings
    :return: None
    """

    delta = new_credit_limit - old_credit_limit
    if delta == 0:
        return
    amount = abs(delta)
    increase_commitment = delta > 0

    # It is not possible to schedule an instance parameter change, so this is unique enough
    trigger = f'CREDIT_LIMIT_{"INCREASED" if increase_commitment else "DECREASED"}'
    instruction_details = _gl_posting_metadata("LOAN_LIMIT", vault.account_id)

    _make_off_bs_internal_account_postings(
        vault,
        amount,
        denomination,
        instructions,
        instruction_details,
        trigger,
        increase_commitment,
    )


def _make_off_bs_internal_account_postings(
    vault,
    amount,
    denomination,
    instructions,
    instruction_details,
    trigger,
    increase_commitment=False,
):
    """
    Create off-balance sheet/revocable commitment GL postings
    :param vault:
    :param amount: Decimal, posting amount
    :param denomination: str, account denomination
    :param increase_commitment: bool, true if the commitment should be increased
    :param instructions: List[PostingInstruction], to be extended with off-bs postings
    :param instruction_details: Dict[str, str], metadata to add to off-bs postings
    :param trigger: str, describes what is causing the postings. Must make the client-transaction-id
    unique enough
    :return: None
    """
    contra_account_id = _get_parameter(vault, name=OFF_BALANCE_SHEET_CONTRA_INTERNAL_ACCOUNT)
    commitment_account_id = _get_parameter(vault, name=REVOCABLE_COMMITMENT_INTERNAL_ACCOUNT)
    if increase_commitment:
        from_account_id = contra_account_id
        to_account_id = commitment_account_id
        action = "INCREASE_COMMITMENT_GL"
    else:
        from_account_id = commitment_account_id
        to_account_id = contra_account_id
        action = "DECREASE_COMMITMENT_GL"

    _create_postings(
        vault,
        amount,
        instructions,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        action=action,
        denomination=denomination,
        instruction_details=instruction_details,
        trigger=trigger,
    )


def _determine_amount_breakdown(
    amount_to_charge,
    credit_limit,
    denomination,
    fee_types,
    in_flight_balances,
    txn_types,
):
    """
    For a given amount charged (settled transaction, bank charges), determine how much is coming
    from different categories. Extra limit is different to overlimit, as the latter accounts for
    principals vs fees, whereas extra limit is any charged amount beyond the credit limit
    :param amount_to_charge: Decimal, the amount that is being charged
    :param credit_limit: +ve Decimal, the account's credit limit
    :param denomination: str, account denomination
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
    balances
    :return: Tuple[Decimal, Decimal, Decimal], amount to settle from credit limit, amount to settle
     beyond credit limit and amount to settle from deposit
    """
    available_deposit = _get_balance(
        in_flight_balances, address=DEPOSIT_BALANCE, denomination=denomination
    )
    if available_deposit > 0:
        deposit_amount = min(amount_to_charge, available_deposit)
    else:
        deposit_amount = Decimal(0)
    non_deposit_amount = amount_to_charge - deposit_amount

    outstanding_balance = _calculate_aggregate_balance(
        in_flight_balances,
        denomination,
        fee_types,
        balance_def=AGGREGATE_BALANCE_DEFINITIONS[OUTSTANDING_BALANCE],
        txn_type_map=txn_types,
        include_deposit=True,
    )

    credit_limit_amount, extra_limit_amount = _determine_non_deposit_breakdown(
        non_deposit_amount, credit_limit - outstanding_balance
    )

    return credit_limit_amount, extra_limit_amount, deposit_amount


def _determine_non_deposit_breakdown(amount, remaining_credit_limit):
    """
    Given an amount and the remaining credit limit determine how much falls within the limit.
    :param amount: Decimal, the amount being spent
    :param remaining_credit_limit: +ve Decimal, the remaining credit limit on the account
    :return: Tuple[Decimal, Decimal], the amount spent from credit limit and the amount that is
    extra limit
    """
    if remaining_credit_limit < 0:
        return 0, amount

    if remaining_credit_limit > amount:
        extra_limit_amount = 0
        credit_limit_amount = amount
    else:
        extra_limit_amount = amount - max(remaining_credit_limit, 0)
        credit_limit_amount = amount - extra_limit_amount

    return credit_limit_amount, extra_limit_amount


def _update_auth_bucket_for_settlement(
    vault,
    posting,
    amount_to_settle,
    unsettled_amount,
    in_flight_balances,
    txn_type,
    txn_ref,
    instructions,
):
    """
    Creates postings to update the _AUTH balance when processing a settlement posting
    :param vault:
    :param posting: PostingInstruction, the settlement posting
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], account balances
     to be updated with created postings
    :param txn_type: str, the posting's transaction type
    :param txn_ref: Optional[str], posting's transaction ref
    :param instructions: List[PostingInstruction], list of posting instructions to extend
    :return: None
    """

    client_txn = vault.get_client_transactions(include_proposed=False)[
        (posting.client_id, posting.client_transaction_id)
    ]

    if client_txn[0].type == PostingInstructionType.AUTHORISATION:

        # Need to adjust AUTH spending bucket to reflect authorised funds being settled. Note
        # AUTH bucket shouldn't go +ve
        # | Settle >= Auth | Settle is Final | Desired outcome             |
        # |----------------|-----------------|-----------------------------|
        # | True           | True            | Zero out Auth bucket        |
        # | False          | True            | Zero out Auth bucket        |
        # | True           | False           | Zero out Auth bucket        |
        # | False          | False           | Reduce Auth by Settle amount|
        if posting.final or amount_to_settle >= unsettled_amount:
            adjust_auth = unsettled_amount  # Zero out Auth bucket
        else:
            adjust_auth = amount_to_settle  # Reduce auth by settle amount

        if adjust_auth > 0:
            # Negate previously authed amount if any
            balance_address = _principal_address(txn_type, AUTH, txn_ref=txn_ref)

            _make_internal_address_transfer(
                amount=adjust_auth,
                denomination=posting.denomination,
                credit_internal=False,
                custom_address=balance_address,
                vault=vault,
                instruction_details=posting.instruction_details,
                action="REDUCE_AUTHORISATION",
                trigger=f"SETTLEMENT_{posting.id}",
                instructions_to_extend=instructions,
                in_flight_balances=in_flight_balances,
            )


def _get_settlement_info(vault, posting):
    """
    Extracts settled/unsettled info for a posting. This abstracts away postings API behaviour like
    not having to specify an amount when making a 'final' settlement
    :param vault:
    :param posting: PostingInstruction, the posting to get settlement information for
    :return: Tuple[Decimal, Decimal], The amount the posting is settling and the unsettled amount on
    the posting's client transaction *prior* to the settlement posting
    """
    unsettled_amount = _get_unsettled_amount(vault, posting=posting)

    # amount is None for a final settlement, in which case we settle remaining unsettled amount
    amount_to_settle = posting.amount if posting.amount else unsettled_amount

    return amount_to_settle, unsettled_amount


def _get_unsettled_amount(vault, posting, include_proposed=False):
    """
    Get the unsettled amount for a posting's client transaction. For example, if the transaction
    starts with an £100 auth, there has been a £30 settlement, and we are currently processing a
    £20 settlement, this will return £70 with include_proposed=False and £50 with
    include_proposed=True
    :param vault:
    :param posting: PostingInstruction, posting to retrieve client transaction unsettled amount for.
    :param include_proposed: bool, if True the current posting's impact is included.
    :return: Decimal, unsettled amount on the client transaction

    """

    if posting.type in [
        PostingInstructionType.SETTLEMENT,
        PostingInstructionType.RELEASE,
        PostingInstructionType.AUTHORISATION_ADJUSTMENT,
    ]:
        client_txn = vault.get_client_transactions(include_proposed=include_proposed)[
            (posting.client_id, posting.client_transaction_id)
        ]

        unsettled_amount = abs(
            client_txn.effects()[
                (posting.account_address, posting.asset, posting.denomination)
            ].unsettled
        )
    else:
        unsettled_amount = 0

    return unsettled_amount


def _is_revolver(balances, denomination):
    """
    Check if the revolver balance is 1 (revolver) or 0 (not revolver)
    :param balances: DefaultDict[Tuple[str, str, str, Phase], Balance], account balances to use for
    revolver check
    :param denomination: str, account denomination
    :return: bool, True if the account is currently revolver, False otherwise
    """
    revolver_balance = balances[
        (REVOLVER_BALANCE, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    if revolver_balance == 0:
        return False
    return True


def _rebalance_interest(
    vault,
    amount,
    denomination,
    in_flight_balances,
    local_accrual_cut_off_date,
    supported_txn_types,
    charge_type,
    sub_type,
    instructions,
    txn_ref=None,
    trigger_base=INTEREST,
):
    """
    Rebalance interest by creating relevant GL postings and postings to update the account addresses
     based on whether the interest is coming from deposit or credit line
    :param vault:
    :param amount: Decimal, the bank charge amount
    :param denomination: str, the bank charge denomination
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
    balances updated with posting instructions created within the current hook execution
    :param local_accrual_cut_off_date: datetime, the accrual cut off date in local timezone to
    populate in GL posting metadata
    :param supported_txn_types: List[str], the transaction types supported by the contract
    :param sub_type: str, the transaction or fee type that the interest is being accrued on
    :param instructions: List[PostingInstruction], list of posting instructions to be extended with
    postings to handle rebalancing
    :param txn_ref: Optional[str], transaction level reference
    :param trigger_base: str, the base string which we will use to construct our trigger
    :return: None
    """
    fee_types = _get_supported_fee_types(vault, supported_txn_types)
    credit_limit = _get_parameter(name=CREDIT_LIMIT, vault=vault)
    (credit_line_amount, extra_limit_amount, deposit_amount,) = _determine_amount_breakdown(
        amount_to_charge=amount,
        credit_limit=credit_limit,
        denomination=denomination,
        in_flight_balances=in_flight_balances,
        fee_types=fee_types,
        txn_types=supported_txn_types,
    )
    stem = f"{sub_type}_{txn_ref}" if txn_ref else sub_type
    trigger = f"{trigger_base}_CHARGED_{stem}"

    # All charged interest must be reflected in default
    if credit_line_amount + extra_limit_amount + deposit_amount > 0:
        _make_internal_address_transfer(
            amount=credit_line_amount + extra_limit_amount + deposit_amount,
            denomination=denomination,
            credit_internal=True,
            custom_address=DEFAULT_ADDRESS,
            action=f"REBALANCE_{DEFAULT_ADDRESS}",
            trigger=trigger,
            in_flight_balances=in_flight_balances,
            instructions_to_extend=instructions,
            vault=vault,
        )

    if credit_line_amount + extra_limit_amount > 0:
        balance_address = _interest_address(sub_type, CHARGED, txn_ref=txn_ref)
        # Debit DEFAULT and Interest bucket, credit INTERNAL bucket + make GL postings
        _make_internal_address_transfer(
            amount=credit_line_amount + extra_limit_amount,
            denomination=denomination,
            credit_internal=True,
            custom_address=balance_address,
            action=f"REBALANCE_{balance_address}",
            trigger=trigger,
            in_flight_balances=in_flight_balances,
            instructions_to_extend=instructions,
            vault=vault,
        )

        _make_interest_gl_postings(
            vault=vault,
            credit_line_amount=credit_line_amount,
            denomination=denomination,
            extra_limit_amount=extra_limit_amount,
            instructions=instructions,
            charge_type=charge_type,
            sub_type=sub_type,
            trigger=trigger,
            local_accrual_cut_off_date=local_accrual_cut_off_date,
            bill=False,
        )

    _make_deposit_postings(
        vault,
        denomination,
        deposit_amount,
        in_flight_balances,
        {},
        instructions,
        trigger,
        "LOAN_CHARGED_INTEREST",
        sub_type,
    )


def _rebalance_fees(
    vault,
    amount,
    denomination,
    in_flight_balances,
    income_account,
    loan_account,
    supported_txn_types,
    trigger,
    instructions,
    fee_type,
    txn_type=None,
    is_external_fee=False,
):
    """
    Rebalance fees by creating postings to update the account addresses based on whether the fees
    are coming from deposit or credit line, and creating relevant GL postings
    :param vault:
    :param amount: Decimal, the bank charge amount
    :param denomination: str, the bank charge denomination
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution
    :param income_account: str, the GL income account id for the fee type
    :param loan_account: str, the GL loan account id for the fee type
    :param trigger: str, describes what is causing the action. Must make the client-transaction-id
    :param instructions: List[PostingInstruction], list of posting instructions to be extended with
     postings to handle rebalancing
    :param fee_type: str, the fee type being charged. Used to populate metadata + cti
    :param txn_type: Optional[str], the transaction type associated to the fee, if applicable.
    :param is_external_fee: bool, set to True if fee is initiated outside of the contract
    :return: None
    """

    # regardless of percentage or flat fee parameter values, we always want balances to 2 dp
    amount = _round(amount, 2)
    if amount == 0:
        return

    external_fee_types = [
        fee.upper() for fee in _get_parameter(vault, name=EXTERNAL_FEE_TYPES, is_json=True)
    ]
    fee_types = _get_supported_fee_types(None, supported_txn_types, external_fee_types)
    credit_limit = _get_parameter(name=CREDIT_LIMIT, vault=vault)
    (credit_line_amount, extra_limit_amount, deposit_amount,) = _determine_amount_breakdown(
        amount_to_charge=amount,
        credit_limit=credit_limit,
        denomination=denomination,
        in_flight_balances=in_flight_balances,
        fee_types=fee_types,
        txn_types=supported_txn_types,
    )

    instruction_details = {"fee_type": fee_type}
    trigger = f'{FEES}_CHARGED_{fee_type}{("_" + trigger) if trigger else ""}'

    # All charged fee amounts must be debited from DEFAULT
    if credit_line_amount + extra_limit_amount + deposit_amount > 0:
        # Dispute fees have already been debited from DEFAULT as they are initiated externally
        if fee_type not in external_fee_types:
            _make_internal_address_transfer(
                amount=credit_line_amount + extra_limit_amount + deposit_amount,
                denomination=denomination,
                credit_internal=True,
                custom_address=DEFAULT_ADDRESS,
                instruction_details=instruction_details,
                action=f"REBALANCE_{DEFAULT_ADDRESS}",
                trigger=trigger,
                in_flight_balances=in_flight_balances,
                instructions_to_extend=instructions,
                vault=vault,
            )

    # Only rebalance buckets and fee buckets if we're actually drawing from credit
    if credit_line_amount + extra_limit_amount > 0:
        balance_address = _fee_address(fee_type, CHARGED)
        _make_internal_address_transfer(
            amount=credit_line_amount + extra_limit_amount,
            denomination=denomination,
            credit_internal=True,
            custom_address=balance_address,
            instruction_details=instruction_details,
            action=f"REBALANCE_{balance_address}",
            trigger=trigger,
            in_flight_balances=in_flight_balances,
            instructions_to_extend=instructions,
            vault=vault,
        )
        _make_fee_gl_postings(
            vault,
            credit_line_amount,
            denomination,
            extra_limit_amount,
            trigger,
            income_account,
            instructions,
            loan_account,
            txn_type,
            is_external_fee,
        )

    _make_deposit_postings(
        vault,
        denomination,
        deposit_amount,
        in_flight_balances,
        instruction_details,
        instructions,
        trigger,
        "LOAN_FEES",
        txn_type,
    )


def _get_supported_txn_types(vault, effective_timestamp=None):
    """
    Determine the list of transaction types that are supported. This is the
    TXN_TYPES keys plus the "<txn_type>_<ref>" combinations for those types
    that use refs and are in TXN_REFS.

    :param vault:
    :param effective_timestamp: Optional[datetime], the datetime as of which to retrieve parameters.
    :return: Dict[str, List[str]], Map of supported transaction types to transaction references.
    Note these are upper case versions of the types in the TXN_TYPES and TXN_REFS
    """

    supported_txn_types = set(
        _get_parameter(vault, name=TXN_TYPES, at=effective_timestamp, is_json=True)
    )
    supported_txn_types = dict.fromkeys(supported_txn_types)

    txn_types_with_txn_level_refs = _get_parameter(
        vault,
        name=TXN_REFS,
        at=effective_timestamp,
        is_json=True,
        upper_case_list_values=True,
    )

    supported_txn_types.update(txn_types_with_txn_level_refs)

    return {k.upper(): v for k, v in supported_txn_types.items()}


def _construct_stems(txn_types):
    """
    Given a Map of txn_types with any nested txn_level refs, construct a full list of stems by
    appending _TXN_REF (if present).
    :param txn_types: Dict[str, Optional[List[str]]], Map of txn_type -> txn_level_refs
    :return: List[str], list of stems
    """
    txn_stems = []
    for txn_type, txn_ref in txn_types.items():
        if txn_ref is None:
            txn_stems.append(txn_type)
        else:
            for ref in txn_ref:
                txn_stems.append(f"{txn_type}_{ref}")

    return txn_stems


def _extract_txn_type_from_stem(vault, txn_stem):
    """
    Takes a stem which may have a transaction reference, returns the transaction type without ref.
    This is more secure than using startsWith() as allows overlapping names ie CASH and CASH_ADVANCE
    :param vault:
    :param txn_stem: str, transaction type appended with transaction ref if present
    :return:
    """
    supported_txn_types = _get_supported_txn_types(vault)

    if txn_stem in supported_txn_types:
        return txn_stem

    txn_types_with_refs = _get_parameter(vault, TXN_REFS, is_json=True, upper_case_list_values=True)
    for txn_type, refs in txn_types_with_refs.items():
        for ref in refs:
            if txn_stem == f"{txn_type.upper()}_{ref}":
                return txn_type.upper()

    # Bit of a safety net, though should never be triggered
    return txn_stem


def _order_stems_by_repayment_hierarchy(txn_stems, txn_hierarchy, txn_type_hierarchy):
    """
    Given a list of stems, order by repayment hierarchy accounting for type and level rates.
    :param txn_stems: List[str], list of transaction stems
    :param txn_hierarchy: Dict[str, Dict[str, str]], map defining repayment order by transaction ref
    :param txn_type_hierarchy: Dict[str, str], map defining repayment order by transaction type
    :return: List[str], transaction types. Any transaction level references prefixed with parent
    type, then parent removed.
    """
    combined_repayment_hierarchy = _combine_txn_and_type_rates(txn_hierarchy, txn_type_hierarchy)

    # Sort all_txn_types by repayment hierarchy. Highest first, then in reverse alphabetical order.
    return sorted(
        txn_stems,
        key=lambda item: (Decimal(combined_repayment_hierarchy[item.lower()]), item),
        reverse=True,
    )


def _combine_txn_and_type_rates(txn_level_rate, txn_type_rate):
    """
    Extract rates for each transaction level reference and merge with transaction type rate dict.
    Refs are converted to lowercase to match txn_types.
    :param txn_level_rate: Dict[str, Dict[str, str]], map of reference to rate by transaction type
    :param txn_type_rate: Dict[str, str], map of transaction type to rate
    :return: Dict[str, str], map of transaction type (with reference, if applicable) to rate
    """
    stem_to_rate = {
        f"{txn_type}_{ref.lower()}": rates[ref]
        for txn_type, rates in txn_level_rate.items()
        for ref in rates
    }

    txn_type_rate.update(stem_to_rate)

    return txn_type_rate


def _get_supported_fee_types(vault=None, supported_txn_types=None, external_fee_types=None):
    """
    Determines all possible fees we can charge. Done dynamically as it depends on parameter values
    :param vault: Optional[vault] populate this if one or both fee and txn types aren't populated
    :param supported_txn_types: Optional[List[str]], transaction types we support
    :param external_fee_types: Optional[List[str]], external fee types we support
    :return: List[str], supported fee types
    """

    external_fee_types = external_fee_types or [
        fee.upper() for fee in _get_parameter(vault, name=EXTERNAL_FEE_TYPES, is_json=True)
    ]

    transaction_fee_types = [
        f"{txn_type}_FEE" for txn_type in supported_txn_types or _get_supported_txn_types(vault)
    ]

    # Shallow copy is OK as it's just a list of str
    return sorted(INTERNAL_FEE_TYPES.copy() + external_fee_types + transaction_fee_types)


def _get_txn_type_and_ref_from_posting(
    vault,
    instruction_details: dict[str, str],
    effective_timestamp: datetime,
    supported_txn_types: Optional[dict[str, Optional[list[str]]]] = None,
    txn_code_to_type_map: Optional[dict[str, str]] = None,
    upper_case_type: bool = False,
) -> Tuple[str, Optional[str]]:
    """
    Extract the transaction type from a posting based on its metadata and the contract supported
    transaction types. Return the transaction reference as well if there is one.
    :param vault:
    :param instruction_details: posting metadata containing transaction code
    :param effective_timestamp: timestamp to get required parameters as-of
    :param supported_txn_types: the contract's supported transaction types
    :param txn_code_to_type_map: map of transaction type code -> transaction_type
    :param upper_case_type: if true we will return txn_type in upper case
    :return: the transaction type and the reference (which may be None)
    """
    if not txn_code_to_type_map:
        txn_code_to_type_map = _get_parameter(
            name=TXN_CODE_TO_TYPE_MAP, at=effective_timestamp, is_json=True, vault=vault
        )
    if not supported_txn_types:
        supported_txn_types = _get_supported_txn_types(vault, effective_timestamp)

    txn_code = instruction_details.get(TXN_CODE)
    txn_type = txn_code_to_type_map.get(txn_code, DEFAULT_TXN_TYPE)

    if txn_type.upper() not in supported_txn_types:
        txn_type = DEFAULT_TXN_TYPE

    if upper_case_type:
        txn_type = txn_type.upper()

    txn_ref = instruction_details.get("transaction_ref", None)
    if txn_ref:
        # We want to always parse the transaction reference in lower case,
        # no matter what case it is defined on the instance param level
        txn_ref = txn_ref.upper()

    return txn_type, txn_ref


def _process_interest_accrual_and_charging(vault, effective_date):
    """
    Determines what interest needs accruing and optionally charging, and instructs corresponding
    posting instructions
    :param vault:
    :param effective_date: datetime, when to get account state as of for accrual purposes
    :return: None
    """

    accrual_cut_off_dt = _determine_accrual_balance_datetime(effective_date)
    if _is_flag_in_list_applied(vault, ACCRUAL_BLOCKING_FLAGS, accrual_cut_off_dt):
        return

    instructions = []
    balances = vault.get_balance_timeseries().at(timestamp=accrual_cut_off_dt)
    in_flight_balances = _deep_copy_balances(balances)
    denomination = _get_parameter(vault, name="denomination", at=effective_date)
    supported_txn_types = _get_supported_txn_types(vault, effective_date)
    txn_types_with_params = _get_parameter(vault, name=TXN_TYPES, at=effective_date, is_json=True)

    txn_types_to_charge_interest_from_txn_date = [
        txn_type
        for txn_type, params in txn_types_with_params.items()
        if _str_to_bool(params.get("charge_interest_from_transaction_date", "False"))
    ]

    is_revolver = _is_revolver(in_flight_balances, denomination)

    txn_types_in_interest_free_period = {}
    interest_free_expiry = _get_parameter(
        vault, INTEREST_FREE_EXPIRY, accrual_cut_off_dt, is_json=True
    )
    txn_interest_free_expiry = _get_parameter(
        vault, TXN_INTEREST_FREE_EXPIRY, accrual_cut_off_dt, is_json=True
    )

    for txn_type in interest_free_expiry:
        if (
            interest_free_expiry[txn_type]
            and parse_to_datetime(interest_free_expiry[txn_type]) > accrual_cut_off_dt
        ):
            txn_types_in_interest_free_period[txn_type] = None

    for txn_type in txn_interest_free_expiry:
        txn_types_in_interest_free_period[txn_type] = []
        for ref in txn_interest_free_expiry[txn_type]:
            if (
                txn_interest_free_expiry[txn_type][ref]
                and parse_to_datetime(txn_interest_free_expiry[txn_type][ref]) > accrual_cut_off_dt
            ):
                txn_types_in_interest_free_period[txn_type].append(ref.upper())

    interest_accruals_by_sub_type = _accrue_interest(
        vault,
        accrual_cut_off_dt,
        supported_txn_types,
        balances,
        denomination,
        txn_types_to_charge_interest_from_txn_date,
        is_revolver,
        instructions,
        txn_types_in_interest_free_period,
    )

    _charge_interest(
        vault,
        is_revolver,
        denomination,
        interest_accruals_by_sub_type,
        txn_types_to_charge_interest_from_txn_date,
        in_flight_balances,
        instructions,
        accrual_cut_off_dt,
        supported_txn_types,
        txn_types_in_interest_free_period=txn_types_in_interest_free_period,
    )

    # Only full outstanding is affected by charged interest
    _adjust_aggregate_balances(
        denomination,
        in_flight_balances,
        instructions,
        vault,
        trigger=EVENT_ACCRUE,
        effective_datetime=effective_date,
        available=False,
        outstanding=False,
    )

    if instructions:
        vault.instruct_posting_batch(
            posting_instructions=instructions,
            effective_date=accrual_cut_off_dt,
            client_batch_id=f"ACCRUE_INTEREST-{vault.get_hook_execution_id()}",
        )


def _accrue_interest(
    vault,
    accrual_cut_off_date,
    supported_txn_types,
    balances,
    denomination,
    txn_types_to_charge_interest_from_txn_date,
    is_revolver,
    instructions,
    txn_types_in_interest_free_period,
):
    """
    Decide whether to accrue interest for each transaction type:
     - if the transaction type has an active interest free period:
            we will accrue interest free period uncharged interest if we are before PDD
     - elif account is in revolver or the txn type is marked out to be charged interest
       from the transaction date:
            we will charge interest
     - elif accrue_interest_from_txn_day is True:
            we will accrue uncharged interest from day of transaction
     - elif the account has outstanding statement balance from previous SCOD:
            we will accrue uncharged interest

    For both uncharged interest cases, we will also set up the relevant accrual postings
    No need to set up accrual postings for the charge interest case, we will just pass on the
    information so that the _charge_interest function can take care of it
    :param vault:
    :param accrual_cut_off_date: datetime, accrual cut-off
    :param supported_txn_types: Dict[str, Optional[List[str]]], map of transaction types to refs
    :param balances: DefaultDict[Tuple[str, str, str, Phase], Balance], the balances at the
    accrual cut-off
    :param denomination: str, account denomination
    :param txn_types_to_charge_interest_from_txn_date: List[str], list of transaction types that
    get charged interest straight away from the date of transaction
    :param is_revolver: bool, True if account is currently revolver
    :param instructions: List[PostingInstruction], postings to be extended by this method
    :param txn_types_in_interest_free_period: Dict[str, Optional[List[str]]], transaction types
    and refs that have an active interest free period
    :return: Dict[str, Dict[str, Decimal]], map of accrued interest by transaction type and ref
    """
    supported_fee_types = _get_supported_fee_types(vault, supported_txn_types)

    accrue_interest_on_unpaid_interest = _str_to_bool(
        _get_parameter(
            vault,
            name=ACCRUE_INTEREST_ON_UNPAID_INTEREST,
            optional=True,
            default_value="False",
        )
    )

    accrue_interest_on_unpaid_fees = _str_to_bool(
        _get_parameter(
            vault,
            name=ACCRUE_INTEREST_ON_UNPAID_FEES,
            optional=True,
            default_value="False",
        )
    )

    # Find out whether we accrue interest from transaction day, to be used later
    accrue_interest_from_txn_day = _is_txn_interest_accrual_from_txn_day(vault)

    balances_to_accrue_on = _get_balances_to_accrue_on(
        balances,
        denomination,
        supported_txn_types,
        supported_fee_types,
        txn_types_to_charge_interest_from_txn_date,
        accrue_interest_on_unpaid_interest,
        accrue_interest_on_unpaid_fees,
        txn_types_in_interest_free_period,
        accrue_interest_from_txn_day,
    )

    if not balances_to_accrue_on:
        return {}

    base_interest_rates = _get_parameter(
        vault, BASE_INTEREST_RATES, accrual_cut_off_date, is_json=True
    )
    txn_base_interest_rates = _get_parameter(
        vault,
        TXN_BASE_INTEREST_RATES,
        accrual_cut_off_date,
        is_json=True,
        upper_case_dict_values=True,
    )
    account_creation_dt = vault.get_account_creation_date()
    payment_due_period = int(_get_parameter(vault, PAYMENT_DUE_PERIOD, accrual_cut_off_date))

    # For transaction types/ refs that have an active interest free period,
    # simply don't accrue interest if we are past PDD.
    # We still want to accrue interest if we are before PDD, and the interest accrued in this case
    # will be zeroed out on PDD only if MAD is repaid. If MAD is not repaid, we will charge the
    # accrued interest.
    if _is_between_pdd_and_scod(
        vault, payment_due_period, account_creation_dt, accrual_cut_off_date
    ):
        (base_interest_rates, txn_base_interest_rates,) = _determine_txns_currently_interest_free(
            txn_types_in_interest_free_period,
            base_interest_rates,
            txn_base_interest_rates,
        )

    combined_base_rates = _combine_txn_and_type_rates(txn_base_interest_rates, base_interest_rates)
    leap_year = _is_leap_year(accrual_cut_off_date.year)
    interest_accruals_by_sub_type = _calculate_accruals_and_create_instructions(
        vault,
        balances_to_accrue_on,
        denomination,
        combined_base_rates,
        instructions,
        leap_year,
        is_revolver=is_revolver,
        txn_types_to_charge_interest_from_txn_date=txn_types_to_charge_interest_from_txn_date,
        txn_types_in_interest_free_period=txn_types_in_interest_free_period,
    )

    return interest_accruals_by_sub_type


def _get_balances_to_accrue_on(
    balances: DefaultDict[tuple[str, str, str, Phase], Balance],
    denomination: str,
    supported_txn_types: dict[str, list[str]],
    supported_fee_types: list[str],
    txn_types_to_charge_interest_from_txn_date: list[str],
    accrue_interest_on_unpaid_interest: bool,
    accrue_interest_on_unpaid_fees: bool,
    txn_types_in_interest_free_period: dict[str, Optional[list[str]]],
    accrue_interest_from_txn_day: bool,
) -> dict[str, dict[str, Decimal]]:
    """
    Determine which balance addresses we need to accrue on and the corresponding amounts.
    Accruals are required if:
     - Customer is revolver and interest is charged daily
     - OR there is outstanding statement balance, and we need to start accruing in case repayment
       is missed and interest is retrospectively charged
     - OR there are transaction types that are marked out to be charged interest from the
       transaction date, and they are not in active interest free periods
    :param balances: the balances at the accrual cut-off
    :param denomination: the account denomination
    :param supported_txn_types: the transaction types supported by the account
    :param supported_fee_types: the fee types supported by the account
    :param txn_types_to_charge_interest_from_txn_date: list of transaction types that
    get charged interest straight away from the date of transaction
    :param accrue_interest_on_unpaid_interest: if true interest is accrued on unpaid interest
    :param accrue_interest_on_unpaid_fees: if true interest is accrued on unpaid fees
    :param txn_types_in_interest_free_period: transaction types and refs that have an active
    interest free period
    :param accrue_interest_from_txn_day: marks the interest accrual approach in this product
    :return: map of transaction type -> map of transaction ref ('' if no ref) -> balance to accrue
    on
    """

    balances_to_accrue_on = {}
    outstanding_statement_amount = _get_outstanding_statement_amount(
        balances, denomination, supported_fee_types, supported_txn_types
    )

    def _update_balances_to_accrue_on(charge_type, sub_type, ref=None):
        """
        Form dict of balances which should be accrued on as per their individual interest rates.
        :param charge_type: str, one of PRINCIPAL or INTEREST or FEES
        :param sub_type: str, transaction or fee type
        :param ref: Optional[str], transaction reference
        """
        addresses_to_accrue_on = []

        if charge_type == PRINCIPAL:
            addresses_to_accrue_on = [
                _principal_address(sub_type, balance_state, txn_ref=ref)
                for balance_state in ACCRUAL_BALANCE_STATES
            ]
        elif charge_type == INTEREST and accrue_interest_on_unpaid_interest:
            addresses_to_accrue_on = [_interest_address(sub_type, UNPAID, txn_ref=ref)]
        elif charge_type == FEES and accrue_interest_on_unpaid_fees:
            addresses_to_accrue_on = [_fee_address(sub_type, UNPAID)]

        amount_to_accrue_on = sum(
            [
                balance.net
                for dimensions, balance in balances.items()
                if dimensions[0] in addresses_to_accrue_on
            ]
        )

        if amount_to_accrue_on == Decimal(0):
            return

        # interest on interest merges with principal balance
        charge_type = PRINCIPAL if charge_type == INTEREST else charge_type

        # make sure to mark that interest needs to be accrued to the POST_SCOD or PRE_SCOD interest
        # uncharged balance addresses respectively from a <transaction_type>_BILLED or
        # <transaction_type>_CHARGED address IF:
        # - charge_interest_from_transaction_date is not already set to true on the txn type.
        #   In this case no need to accrue as interest will be charged directly.
        # - Txn is not in an interest free period
        # - Account is not in revolver mode
        if (
            accrue_interest_from_txn_day
            and charge_type == PRINCIPAL
            and sub_type.lower() not in txn_types_to_charge_interest_from_txn_date
            and not _is_txn_type_in_interest_free_period(
                txn_types_in_interest_free_period, sub_type, ref
            )
            and not _is_revolver(balances, denomination)
        ):
            # <transaction_type>_BILLED accrues to <transaction_type>_INTEREST_POST_SCOD_UNCHARGED
            billed_amount_to_accrue_on = sum(
                [
                    balance.net
                    for dimensions, balance in balances.items()
                    if dimensions[0] in addresses_to_accrue_on and dimensions[0].endswith(BILLED)
                ]
            )
            # <transaction_type>_CHARGED accrues to <transaction_type>_INTEREST_PRE_SCOD_UNCHARGED
            charged_amount_to_accrue_on = sum(
                [
                    balance.net
                    for dimensions, balance in balances.items()
                    if dimensions[0] in addresses_to_accrue_on and dimensions[0].endswith(CHARGED)
                ]
            )
            _set_accruals_by_sub_type(
                balances_to_accrue_on,
                charge_type,
                sub_type,
                ref,
                billed_amount_to_accrue_on,
                accrual_type=POST_SCOD,
            )
            _set_accruals_by_sub_type(
                balances_to_accrue_on,
                charge_type,
                sub_type,
                ref,
                charged_amount_to_accrue_on,
                accrual_type=PRE_SCOD,
            )

        else:
            _set_accruals_by_sub_type(
                balances_to_accrue_on, charge_type, sub_type, ref, amount_to_accrue_on
            )

    # Accrue interest on all balances if we are in revolver, or if the account is projected to go
    # into revolver by next PDD
    # We will decide further down whether the interest is accrued to UNCHARGED address or CHARGED
    # directly
    accrue_on_all_balances = (
        _is_revolver(balances, denomination) or outstanding_statement_amount > 0
    )
    for txn_type, refs in supported_txn_types.items():
        for ref in refs or [None]:
            charge_interest_on_txn_type_from_txn_date = (
                txn_type.lower() in txn_types_to_charge_interest_from_txn_date
                and not _is_txn_type_in_interest_free_period(
                    txn_types_in_interest_free_period, txn_type, ref
                )
            )
            accrue_interest_on_txn_type_from_txn_day = (
                accrue_interest_from_txn_day
                and not _is_txn_type_in_interest_free_period(
                    txn_types_in_interest_free_period, txn_type, ref
                )
            )

            if (
                accrue_on_all_balances
                or charge_interest_on_txn_type_from_txn_date
                or accrue_interest_on_txn_type_from_txn_day
            ):
                # If account is not in revolver and outstanding statement amount is zero,
                # accrue interest on a transaction only if:
                # The transaction type has charge_interest_from_transaction_date=True,
                # and the transaction type/ ref does not have an active interest free period
                # or if we're accruing interest from day of txn
                _update_balances_to_accrue_on(charge_type=PRINCIPAL, sub_type=txn_type, ref=ref)
                _update_balances_to_accrue_on(charge_type=INTEREST, sub_type=txn_type, ref=ref)

    for fee_type in supported_fee_types:
        _update_balances_to_accrue_on(charge_type=FEES, sub_type=fee_type)

    return balances_to_accrue_on


def _calculate_accruals_and_create_instructions(
    vault,
    balances_to_accrue_on,
    denomination,
    base_interest_rates,
    instructions,
    leap_year,
    is_revolver,
    txn_types_to_charge_interest_from_txn_date,
    txn_types_in_interest_free_period,
):
    """
    Calculate the interest to accrue on each transaction type and create corresponding postings,
    unless the interest will be charged immediately anyway
    :param vault:
    :param balances_to_accrue_on: Dict[str, Dict[str, Decimal]], map of ref (or empty string) to
     amount to accrue on, mapped to transaction type.
    :param denomination: str, account denomination
    :param base_interest_rates: Dict[str, Decimal], txn type to gross annual interest rate
    :param instructions: List[PostingInstruction], postings to be extended by this method
    :param leap_year: bool, True if interest value date is on leap year
    :param is_revolver: bool, True if account is currently revolver and interest should be
    charged immediately, unless the txn type has an active interest free period
    :param txn_types_to_charge_interest_from_txn_date: List[str], list of transaction types that
    get charged interest straight away from the date of transaction
    :param txn_types_in_interest_free_period: Dict[str, Optional[List[str]]], txn types/
    refs for which we enforce accruals to be strictly on a specific address ending with
    INTEREST_FREE_PERIOD_UNCHARGED, so that it will be possible to reverse this charge on PDD
    given that the MAD is repaid
    :return: Dict[str, Decimal], transaction type to accrual amounts
    """
    interest_by_charge_sub_and_accrual_type = {}

    def _create_accrual_instructions(charge_type, sub_type, amount, ref, accrual_type):
        """
        Create accrual instructions for transaction type provided
        :param charge_type: str, one of PRINCIPAL, FEES or INTEREST
        :param sub_type: str, transaction or fee type
        :param amount: Decimal, amount to accrue on
        :param ref: Optional[str], transaction level reference
        :param accrual_type: str, either '', PRE_SCOD or POST_SCOD applicable for interest accrual
        to _UNCHARGED balances from txn day
        """
        stem = f"{sub_type}_{ref}" if ref else sub_type
        interest_stem = stem if charge_type != FEES else FEES

        daily_rate = _yearly_to_daily_rate(
            Decimal(base_interest_rates[interest_stem.lower()]), leap_year
        )
        accrual_amount = _round(daily_rate * amount, decimal_places=2)

        if accrual_amount > 0:
            is_txn_type_in_interest_free_period = _is_txn_type_in_interest_free_period(
                txn_types_in_interest_free_period, sub_type, ref
            )
            if is_txn_type_in_interest_free_period:
                sub_type = f"{sub_type}_{INTEREST_FREE_PERIOD}"
                stem = f"{stem}_{INTEREST_FREE_PERIOD}"
            else:
                # We do not attempt to charge interest on transactions that have active interest
                # free periods even in revolver
                _set_accruals_by_sub_type(
                    interest_by_charge_sub_and_accrual_type,
                    charge_type,
                    sub_type,
                    ref,
                    accrual_amount,
                    accrual_type,
                )

            # If the account is revolver or the txn type has charge_interest_from_transaction_date
            # as True, interest will be charged immediately unless the txn type has an active
            # interest free period.
            # If the interest will be charged immediately there is no point making accrual postings
            if (
                not (is_revolver or sub_type.lower() in txn_types_to_charge_interest_from_txn_date)
                or is_txn_type_in_interest_free_period
            ):
                stem_with_accrual_type = f"{stem}_{accrual_type}" if accrual_type else stem
                daily_rate_percent = daily_rate * 100
                instruction_details = {
                    "description": f"Daily interest accrued at {daily_rate_percent:.7f}% on balance"
                    f" of {abs(amount):.2f}, for transaction type {stem_with_accrual_type}"
                }
                _make_accrual_posting(
                    vault,
                    accrual_amount,
                    denomination,
                    stem,
                    instructions,
                    instruction_details=instruction_details,
                    accrual_type=accrual_type,
                )

    for charge_and_sub_and_accrual_type, ref_to_amount in balances_to_accrue_on.items():
        charge_type, sub_type, accrual_type = charge_and_sub_and_accrual_type
        for ref, amount in ref_to_amount.items():
            _create_accrual_instructions(charge_type, sub_type, amount, ref, accrual_type)

    return interest_by_charge_sub_and_accrual_type


def _make_accrual_posting(
    vault,
    accrual_amount: Decimal,
    denomination: str,
    stem: str,
    instructions: list[PostingInstruction],
    instruction_details: Optional[dict[str, str]] = None,
    reverse: bool = False,
    accrual_type: Optional[str] = None,
):
    """
    Creates posting instructions for interest accrual
    :param vault:
    :param accrual_amount: amount to accrue
    :param denomination: denomination to accrue in
    :param stem: transaction type being accrued on (with reference appended if present)
    :param instructions: to be extended with accrual posting instructions
    :param instruction_details: metadata to attach to the postings
    :param reverse: used to reverse accrual postings (e.g. zeroing out accrued interest)
    :param accrual_type: either '' or PRE_SCOD or POST_SCOD applicable for interest
    accrual to _UNCHARGED balances from txn day
    :return: None
    """
    action = "ACCRUE_INTEREST" if not reverse else "REVERSE_UNCHARGED_INTEREST"
    stem_with_accrual_type = f"{stem}_{accrual_type}" if accrual_type else stem
    _make_internal_address_transfer(
        amount=abs(accrual_amount),
        denomination=denomination,
        credit_internal=not reverse,
        custom_address=_interest_address(stem, UNCHARGED, accrual_type=accrual_type),
        action=action,
        trigger=stem_with_accrual_type,
        instruction_details=instruction_details,
        instructions_to_extend=instructions,
        vault=vault,
    )


def _determine_accrual_balance_datetime(scheduled_datetime):
    """
    Determines the datetime to use for retrieving the effective balance for accrual purposes.
    Accrual should always use the effective balance from <Day>T23:59:59.99999+0800, but
    accrual can only be scheduled for <Day+1>T00:00:00+0800 or later
    :param scheduled_datetime: UTC schedule accrual datetime
    :return: datetime, UTC accrual cut-off
    """

    # Due to accruals using balance as of 23:59:59.99999, the accrual schedule will always be the
    # next day from an Local TZ perspective as the closest scheduleable time after is 00:00:00.
    # In UTC there will be a day offset between cut-off and schedule time if either
    # - Local TZ is ahead of UTC and the local schedule time is greater than the offset
    # - Local TZ is behind UTC and the local schedule time is greater than 24-offset
    # |Local Schedule |Local Effective Balance| UTC Schedule    |UTC Effective Balance |Day Offset?|
    # |---------------|-----------------------|-----------------|----------------------|-----------|
    # |<Day>T00:00:00 |<Day-1>T23:59:59.99999 |<Day-1>T16:00:00 |<Day-1>T15:59:59.99999|No         |
    # |<Day>T04:00:00 |<Day-1>T23:59:59.99999 |<Day-1>T20:00:00 |<Day-1>T15:59:59.99999|No         |
    # |<Day>T08:00:00 |<Day-1>T23:59:59.99999 |<Day>00:00:00    |<Day-1>T15:59:59.99999|Yes        |
    # |<Day>T15:00:00 |<Day-1>T23:59:59.99999 |<Day>07:00:00    |<Day-1>T15:59:59.99999|Yes        |
    # |<Day>T23:00:00 |<Day-1>T23:59:59.99999 |<Day>15:00:00    |<Day-1>T15:59:59.99999|Yes        |

    offset = (24 - LOCAL_UTC_OFFSET) % 24

    offset_cutoff = scheduled_datetime.replace(hour=offset, minute=0, second=0)

    # First determine <Day-1>T16:00:00, offsetting if required
    if scheduled_datetime >= offset_cutoff:
        end_of_day = scheduled_datetime.replace(hour=offset, minute=0, second=0)
    else:
        # This handles month/year changes for us and guarantees we get D-1 at 16:00:00
        # Only works when no DST
        end_of_day = scheduled_datetime.replace(hour=0, minute=0, second=0) - timedelta(
            hours=LOCAL_UTC_OFFSET
        )

    # Then offset by 1 us to get <Day-1>T15:59:59.99999
    end_of_day -= timedelta(microseconds=1)

    return end_of_day


def _yearly_to_daily_rate(yearly_rate, leap_year):
    """
    Convert a yearly rate to daily rate, accounting for leap years
    :param yearly_rate: Decimal, gross yearly interest rate
    :param leap_year: bool, true if is a leap year
    :return: Decimal
    """
    days_in_year = 366 if leap_year else 365

    return yearly_rate / days_in_year


def _is_leap_year(year):
    """
    Determine whether year is a leap year
    :param year: int, year extracted from date
    :return: bool, true if leap year
    """
    if year % 400 == 0:
        return True
    elif year % 100 == 0:
        return False
    elif year % 4 == 0:
        return True
    else:
        return False


def _round(amount, decimal_places):
    """
    Round an amount to specified number of decimal places
    :param amount: Decimal, amount to round
    :param decimal_places: int, number of places to round to
    :return: Decimal, rounded amount
    """

    return amount.quantize(Decimal((0, (1,), -decimal_places)), rounding=ROUND_HALF_UP)


def _zero_out_time(input_datetime):
    """
    Takes a given datetime and zeros out all time attributes (e.g. hour, min, sec etc)
    :param input_datetime: datetime, datetime whose time component we want to zero out
    :return: datetime, datetime with 0 time attributes
    """
    return datetime(input_datetime.year, input_datetime.month, input_datetime.day)


def _get_first_scod(account_creation_date, localize_datetime=False):
    """
    Calculates first SCOD using account creation date
    :param account_creation_date: datetime, utc account creation date
    :param localize_datetime: boolean, set to True if the return should be localised.
    :return: Tuple[datetime, datetime], start date and end date for SCOD. Timezone is UTC unless
     localize_datetime is True
    """

    # Even if we want UTC outputs we have to get local midnight and then convert back
    # Handle leap years gracefully for the fixed annual fee schedule. Until BL-111 is implemented,
    # this will only works if the annual fee hour is > Local to UTC offset
    local_account_creation_date = _zero_out_time(_localize_datetime(account_creation_date))
    local_scod_start = local_account_creation_date + timedelta(months=1) - timedelta(days=1)
    if localize_datetime:
        return local_scod_start, local_scod_start + timedelta(days=1)
    else:
        scod_start = _delocalize_datetime(local_scod_start)
        return scod_start, scod_start + timedelta(days=1)


def _get_previous_scod(
    vault,
    account_creation_date: datetime,
) -> Tuple[datetime, datetime]:
    """
    Determines the last scod before the current date
    :param vault:
    :param account_creation_date: utc account creation date
    :return:  utc start and end of last SCOD. If no SCOD has taken place
    both will be equal to account_creation_date
    """

    last_scod_execution_time = vault.get_last_execution_time(event_type=EVENT_SCOD)
    if last_scod_execution_time:
        prev_scod_end = last_scod_execution_time - timedelta(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        prev_scod_start = prev_scod_end - timedelta(days=1)
    else:
        # If an account is closed before first SCOD, we use the account creation date
        prev_scod_end = account_creation_date
        prev_scod_start = account_creation_date

    return prev_scod_start, prev_scod_end


def _get_first_pdd(payment_due_period, first_scod_start):
    """
    Calculates first Payment Due Date (PDD) on the basis of the first Statement Cut-Off
    Date (SCOD) where PDD(0) = SCOD(0) + Payment Due Period.
    :param payment_due_period: int, number of days between SCOD and PDD
    :param first_scod_start: datetime, start of first SCOD.
    :return: Tuple[datetime, datetime] start of PDD, end of PDD. first_scod_start timezone is
    preserved
    """

    first_pdd_start = first_scod_start + timedelta(days=payment_due_period)

    return first_pdd_start, first_pdd_start + timedelta(days=1)


def _get_next_pdd(
    payment_due_period,
    account_creation_date,
    last_pdd_execution_datetime=None,
    localize_datetime=False,
):
    """
    Calculate next PDD, maintaining the day of the month of the first PDD. If PDD schedule has
    never been executed (last_pdd_execution_datetime is None), this will return the first pdd.
    :param payment_due_period: int, number of days between SCOD and PDD
    :param account_creation_date: datetime, UTC account opening date
    :param last_pdd_execution_datetime: datetime, UTC last pdd logical execution time. Optional
    :param localize_datetime: boolean, set to True if the return should be localised. If True,
    last_pdd_execution_datetime is assumed to be localised already
    :return: Tuple[datetime, datetime] start of next PDD, end of next PDD. latest_pdd_start
    timezone is preserved unless localize_datetime is set to True
    """

    # always calculate next PDD from first PDD to preserve the day of month where possible. We must
    # perform calculations with localised datetime as a result, and then delocalise if requested
    local_first_scod_start, _ = _get_first_scod(account_creation_date, localize_datetime=True)
    local_first_pdd_start, local_first_pdd_end = _get_first_pdd(
        payment_due_period, local_first_scod_start
    )

    # if PDD hasn't ever executed, the next PDD must be the first PDD
    if last_pdd_execution_datetime is None:
        if not localize_datetime:
            return (
                _delocalize_datetime(local_first_pdd_start),
                _delocalize_datetime(local_first_pdd_end),
            )
        return local_first_pdd_start, local_first_pdd_end
    # PDD schedule runs at the end of the actual PDD

    local_last_pdd_start = _localize_datetime(
        last_pdd_execution_datetime
        - timedelta(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            days=1,
        )
    )
    # Add 1 as the calculation uses last pdd and first pdd but we want delta to next pdd
    month_delta = (
        1
        + local_last_pdd_start.month
        - local_first_pdd_start.month
        + 12 * (local_last_pdd_start.year - local_first_pdd_start.year)
    )
    local_next_pdd_start = local_first_pdd_start + timedelta(months=month_delta)

    if localize_datetime:
        return local_next_pdd_start, local_next_pdd_start + timedelta(days=1)
    else:
        next_pdd_start = _delocalize_datetime(local_next_pdd_start)
        return next_pdd_start, next_pdd_start + timedelta(days=1)


def _get_scod_for_pdd(payment_due_period, pdd_start):
    """
    Calculates SCOD for a given PDD by subtracting payment due period from PDD.
    :param payment_due_period: int, number representing the difference between SCOD and PDD
    :param pdd_start: datetime, start of payment due date.
    :return: Tuple[datetime, datetime], start and end of SCOD. Same timezone as pdd_start
    """

    scod_start = pdd_start - timedelta(days=payment_due_period)

    return scod_start, scod_start + timedelta(days=1)


def _is_between_pdd_and_scod(
    vault,
    payment_due_period: int,
    account_creation_date: datetime,
    current_date: datetime,
) -> bool:
    """
    Determines whether we are after or before the PDD in the current statement cycle.
    There is no PDD in the first statement cycle, we will return false if current_date is within
    first statement cycle.
    :param vault:
    :param payment_due_period: number of days between SCOD and PDD
    :param account_creation_date: utc account creation date
    :param current_date: the utc time at which the check happens
    :return: True if we are after the PDD in the current statement cycle, and False if not
    """

    _, previous_scod = _get_previous_scod(vault, account_creation_date)

    if previous_scod == account_creation_date:
        # We are within one month of account creation, there hasn't been a PDD yet.
        return False

    return previous_scod < current_date - timedelta(days=payment_due_period)


def _charge_annual_fee(vault, effective_date):
    """
    Create postings to charge annual fee if set.
    :param vault:
    :param effective_date: datetime, the datetime we are charging the annual fee on
    :return:
    """
    instructions = []
    denomination = _get_parameter(name=DENOMINATION, at=effective_date, vault=vault)
    credit_limit = _get_parameter(name=CREDIT_LIMIT, at=effective_date, vault=vault)
    in_flight_balances = _deep_copy_balances(vault.get_balance_timeseries().latest())
    supported_txn_types = _get_supported_txn_types(vault, effective_date)

    annual_fee = _charge_fee(
        vault,
        denomination,
        in_flight_balances=in_flight_balances,
        instructions=instructions,
        fee_type=ANNUAL_FEE,
        supported_txn_types=supported_txn_types,
    )
    if annual_fee == 0:
        return

    _adjust_aggregate_balances(
        denomination,
        in_flight_balances,
        instructions,
        vault,
        trigger=ANNUAL_FEE,
        effective_datetime=effective_date,
        credit_limit=credit_limit,
    )

    if instructions:
        vault.instruct_posting_batch(
            posting_instructions=instructions,
            effective_date=effective_date,
            client_batch_id=f"{ANNUAL_FEE}-{vault.get_hook_execution_id()}",
        )


def _process_statement_cut_off(vault, effective_date, in_flight_balances=None, is_final=False):
    """
    Statement cut off event:
     - move 'CHARGED' balances to 'BILLED'
     - move 'INTEREST_PRE_SCOD_UNCHARGED' balances to 'INTEREST_POST_SCOD_UNCHARGED'
     - charge overlimit fees if applicable
     - adjust aggregate balances
     - trigger statement workflow with data for integration services
    :param vault:
    :param effective_date: datetime, SCOD schedule datetime
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution
    :param is_final: boolean, set to true if generating the final statement
    :return:
    """
    # Take balances from SCOD effective date minus a microsecond to capture all transactions
    # up until that point. For example, if we assume the schedule is run at SCOD+1T00:00:00,
    # all balances up until SCODT23:59:59.99999 are included in the statement.
    # This includes interest accrual
    if is_final:
        scod_cut_off_dt = effective_date
        scod_effective_dt = effective_date
    else:
        scod_effective_dt = effective_date - timedelta(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        scod_cut_off_dt = scod_effective_dt - timedelta(
            microseconds=1,
        )

    # May already be initialised if statement processing is triggered by write-off
    in_flight_balances = in_flight_balances or _deep_copy_balances(
        vault.get_balance_timeseries().at(timestamp=scod_cut_off_dt)
    )
    denomination = _get_parameter(name=DENOMINATION, at=scod_effective_dt, vault=vault)
    credit_limit = _get_parameter(name=CREDIT_LIMIT, at=scod_effective_dt, vault=vault)
    supported_txn_types = _get_supported_txn_types(vault, scod_effective_dt)
    supported_fee_types = _get_supported_fee_types(vault, supported_txn_types)

    # Find out whether we accrue interest from transaction day, for later checks
    accrue_interest_from_txn_day = _is_txn_interest_accrual_from_txn_day(vault)

    txn_types_with_params = _get_parameter(vault, name=TXN_TYPES, at=effective_date, is_json=True)

    txn_types_to_charge_interest_from_txn_date = [
        txn_type
        for txn_type, params in txn_types_with_params.items()
        if _str_to_bool(params.get("charge_interest_from_transaction_date", "False"))
    ]

    # some instructions must be effective as of just before end of SCOD (e.g. over-limit fee) to
    # fall in the statement, so we group them based on their value timestamp
    instructions_ts = {scod_cut_off_dt: [], scod_effective_dt: []}

    # Overlimit fee is charged as of balances cut-off as it should be included in SCOD
    _charge_overlimit_fee(
        vault,
        in_flight_balances,
        denomination,
        supported_txn_types,
        instructions_ts[scod_cut_off_dt],
        credit_limit,
    )

    _bill_charged_txns_and_bank_charges(
        vault,
        supported_txn_types,
        denomination,
        instructions_ts[scod_effective_dt],
        in_flight_balances,
        credit_limit,
    )

    if accrue_interest_from_txn_day and not is_final:
        _adjust_interest_uncharged_balances(
            vault,
            supported_txn_types,
            txn_types_to_charge_interest_from_txn_date,
            denomination,
            instructions_ts[scod_effective_dt],
            in_flight_balances,
        )

    total_statement_amount = _get_outstanding_statement_amount(
        in_flight_balances, denomination, supported_fee_types, supported_txn_types
    )

    mad = _calculate_mad(
        vault,
        in_flight_balances,
        denomination,
        supported_txn_types,
        scod_effective_dt,
        total_statement_amount,
        mad_eq_statement=_is_flag_in_list_applied(vault, MAD_AS_STATEMENT_FLAGS, scod_effective_dt),
    )

    _update_info_balances(
        vault,
        in_flight_balances,
        denomination,
        total_statement_amount,
        mad,
        instructions_ts[scod_effective_dt],
    )

    _handle_live_balance_changes(vault, denomination, scod_cut_off_dt, instructions_ts)

    for index, (value_timestamp, instruction_list) in enumerate(instructions_ts.items()):
        if instruction_list:
            vault.instruct_posting_batch(
                posting_instructions=instruction_list,
                effective_date=value_timestamp,
                client_batch_id=f"SCOD_{index}-{vault.get_hook_execution_id()}",
            )

    _publish_statement_workflow(vault, scod_effective_dt, total_statement_amount, mad, is_final)


def _adjust_interest_uncharged_balances(
    vault,
    supported_txn_types,
    txn_types_to_charge_interest_from_txn_date,
    denomination,
    scod_instructions,
    in_flight_balances,
):
    """
    Rebalances uncharged interest balances. Flow at SCOD for non revolver accounts is :
    <transaction_type>_INTEREST_PRE_SCOD_UNCHARGED moves to
    <transaction_type>_INTEREST_POST_SCOD_UNCHARGED
    :param vault:
    :param supported_txn_types: Dict[str, Optional[List[str]]], map of supported transaction types
    :param txn_types_to_charge_interest_from_txn_date: List[str], list of transaction types that
     get charged interest straight away from the date of transaction
    :param scod_instructions: List[PostingInstruction], extended with instructions to be instructed
     as of the SCOD effective datetime
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution
    :return: None
    """
    for txn_type, refs in supported_txn_types.items():
        if txn_type.lower() not in txn_types_to_charge_interest_from_txn_date:
            for txn_ref in refs or [None]:
                from_balance_address = _interest_address(
                    txn_type, UNCHARGED, txn_ref=txn_ref, accrual_type=PRE_SCOD
                )
                to_balance_address = _interest_address(
                    txn_type, UNCHARGED, txn_ref=txn_ref, accrual_type=POST_SCOD
                )
                _rebalance_balance_buckets(
                    vault,
                    in_flight_balances,
                    from_balance_address,
                    to_balance_address,
                    denomination,
                    trigger=EVENT_SCOD,
                    instructions=scod_instructions,
                )


def _bill_charged_txns_and_bank_charges(
    vault,
    supported_txn_types,
    denomination,
    scod_instructions,
    in_flight_balances,
    credit_limit,
):
    """
    Determine what is billed for this statement cycle and create corresponding posting instructions
    :param vault:
    :param supported_txn_types: Dict[str, Optional[List[str]]], map of supported transaction types
    :param denomination: str, statement denomination
    :param scod_instructions: List[PostingInstruction], extended with instructions to be instructed
    as of the SCOD effective datetime
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution
    :param credit_limit: Decimal, the account's credit limit at SCOD cut-off
    :return: None
    """

    def _construct_statement_breakdown(sub_type, charge_type, txn_ref=None):
        """
        Create addresses on a per-charge-type basis, calculate amount and add to Dict for return
        :param sub_type: str, transaction or fee type
        :param charge_type: str, type of transaction (BILLED etc)
        :param txn_ref: Optional[str], transaction level reference
        """
        if charge_type == PRINCIPAL:
            from_balance_address = _principal_address(sub_type, CHARGED, txn_ref=txn_ref)
            to_balance_address = _principal_address(sub_type, BILLED, txn_ref=txn_ref)
        elif charge_type == FEES:
            from_balance_address = _fee_address(fee_type=sub_type, fee_status=CHARGED)
            to_balance_address = _fee_address(fee_type=sub_type, fee_status=BILLED)

        _rebalance_balance_buckets(
            vault,
            in_flight_balances,
            from_balance_address,
            to_balance_address,
            denomination,
            trigger=EVENT_SCOD,
            instructions=scod_instructions,
        )

    for txn_type, refs in supported_txn_types.items():
        for ref in refs or [None]:
            _construct_statement_breakdown(txn_type, PRINCIPAL, txn_ref=ref)

    # Bill charged Fees
    supported_fee_types = _get_supported_fee_types(vault, supported_txn_types)
    for fee_type in supported_fee_types:
        _construct_statement_breakdown(fee_type, FEES)

    _bill_charged_interest(
        vault,
        supported_fee_types,
        supported_txn_types,
        denomination,
        scod_instructions,
        in_flight_balances,
    )

    # Charged interest that has just been billed was not previously deducted from available balance
    _adjust_aggregate_balances(
        denomination,
        in_flight_balances,
        scod_instructions,
        vault,
        trigger="billed_interest",
        outstanding=False,
        full_outstanding=False,
        credit_limit=credit_limit,
    )


def _bill_charged_interest(
    vault,
    supported_fee_types,
    supported_txn_types,
    denomination,
    scod_instructions,
    in_flight_balances,
):
    """
    Creates instructions to move spend from transaction_type_INTEREST_CHARGED to
    transaction_type_INTEREST_BILLED at SCOD. Also makes postings to DEFAULT balance so that
    available balance is affected.
    :param vault:
    :param supported_fee_types: List[str], list of supported fee types
    :param supported_txn_types: List[str], list of supported transaction types as per parameters
    :param denomination: str, the account denomination
    :param scod_instructions: List[PostingInstruction], extended with instructions to be instructed
    as of the SCOD effective datetime
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution
    :return: None
    """
    credit_limit = _get_parameter(name=CREDIT_LIMIT, vault=vault)
    outstanding_balance = _calculate_aggregate_balance(
        in_flight_balances,
        denomination,
        supported_fee_types,
        balance_def=AGGREGATE_BALANCE_DEFINITIONS[OUTSTANDING_BALANCE],
        txn_type_map=supported_txn_types,
        include_deposit=True,
    )
    remaining_credit_line = credit_limit - outstanding_balance

    def move_interest_to_billed(remaining_credit_line, charge_type, sub_type, txn_ref=None):
        """
        Move interest from charged to billed address
        :param remaining_credit_line: Decimal, amount of money left that can be spent
        :param charge_type: str, one of PRINCIPAL, FEES or INTEREST
        :param sub_type: str, transaction or fee type
        :param txn_ref: Optional[str], transaction level reference
        """
        from_balance_address = _interest_address(sub_type, CHARGED, txn_ref=txn_ref)
        to_balance_address = _interest_address(sub_type, BILLED, txn_ref=txn_ref)
        stem = f"{sub_type}_{txn_ref}" if txn_ref else sub_type
        amount = _rebalance_balance_buckets(
            vault,
            in_flight_balances,
            from_balance_address,
            to_balance_address,
            denomination,
            EVENT_SCOD,
            instructions=scod_instructions,
        )

        if amount != 0:
            # amount must be non-deposit as it wouldn't still be outstanding if covered by deposit
            credit_line_amount, extra_limit_amount = _determine_non_deposit_breakdown(
                amount, remaining_credit_line
            )
            _make_interest_gl_postings(
                vault,
                credit_line_amount,
                denomination,
                extra_limit_amount,
                scod_instructions,
                charge_type=charge_type,
                sub_type=sub_type,
                trigger=f"INTEREST_BILLED_{stem}",
                bill=True,
            )
            remaining_credit_line += amount

    for txn_type, txn_refs in supported_txn_types.items():
        for txn_ref in txn_refs or [None]:
            move_interest_to_billed(
                remaining_credit_line,
                charge_type=None,
                sub_type=txn_type,
                txn_ref=txn_ref,
            )

    for fee_type in supported_fee_types:
        move_interest_to_billed(remaining_credit_line, charge_type=FEES, sub_type=fee_type)


def _update_info_balances(
    vault, in_flight_balances, denomination, statement_amount, mad, instructions
):
    """
    Create the posting instructions required to update statement info balances (statement,
    outstanding, full outstanding, mad) and reset total repayments balance
    :param vault:
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution
    :param denomination: str, the account denomination
    :param statement_amount: Decimal, new statement amount
    :param mad: Decimal, minimum amount due for the new statement
    :param instructions: List[PostingInstruction], list of posting instructions to be extended with
    postings to handle updating info balances
    :return: None
    """
    # Update statement, outstanding and full outstanding balances with new amount
    for info_balance in [
        STATEMENT_BALANCE,
        OUTSTANDING_BALANCE,
        FULL_OUTSTANDING_BALANCE,
    ]:
        _override_info_balance(
            vault,
            in_flight_balances,
            info_balance,
            denomination,
            statement_amount,
            instructions,
        )

    _override_info_balance(
        vault,
        in_flight_balances,
        TRACK_STATEMENT_REPAYMENTS,
        denomination,
        0,
        instructions,
    )

    _override_info_balance(vault, in_flight_balances, MAD_BALANCE, denomination, mad, instructions)


def _handle_live_balance_changes(vault, denomination, cut_off_dt, instructions_ts, is_pdd=False):
    """
    Ensures that post-schedule balances are consistent even balances have changed since cut-off
    :param vault:
    :param denomination: Str
    :param cut_off_dt: datetime, cut-off for the schedule. This will help determine if live balances
    changed after the cut-off, in which case there may be inconsistencies
    :param instructions_ts: map(dt->list(PostingInstruction)), instructions to be made as part of
    PDD processing. Updated with postings to handle live balance change
    :return:
    """
    live_balance_dt, live_balances = vault.get_balance_timeseries().all()[-1]
    in_flight_live_balances = _deep_copy_balances(live_balances)
    for instructions in instructions_ts.values():
        _update_balances(vault.account_id, in_flight_live_balances, instructions)

    # it's possible that cut_off balances are live balances, in which case we don't want to
    # do anything
    if live_balance_dt > cut_off_dt:
        balance_pairs = (BILLED, UNPAID) if is_pdd else (CHARGED, BILLED)
        trigger = EVENT_PDD if is_pdd else EVENT_SCOD
        clean_up_postings, repaid_amount = _clean_up_balance_inconsistencies(
            vault, denomination, in_flight_live_balances, balance_pairs, trigger
        )

        if repaid_amount > 0 and is_pdd:
            _repay_overdue_buckets(
                vault,
                denomination,
                in_flight_live_balances,
                clean_up_postings,
                repaid_amount,
            )
        if live_balance_dt in instructions_ts:
            instructions_ts[live_balance_dt].extend(clean_up_postings)
        else:
            instructions_ts[live_balance_dt] = clean_up_postings


def _clean_up_balance_inconsistencies(
    vault, denomination, updated_live_balances, address_suffix_pair, event
):
    """
    Given a pair of balance suffixes (e.g. _CHARGED and _BILLED), determines whether the updated
    live balances have any inconsistencies and creates the postings to address them. These postings
    should be instructed as of the live_balance datetime.
    :param vault:
    :param denomination: Str
    :param updated_live_balances: This should contain the live balances, updated with the
    impact of proposed postings made by the contract.
    :param address_suffix_pair: tuple(str, str): pair of suffixes to correct inconsistencies for.
    The addresses with the first suffix will be debited and the  addresses with the second suffix
    will be credited to correct any detected inconsistencies.
    :return: list(PostingInstruction), Decimal: the posting instructions to correct the
    inconsistencies, and the total rectification amount
    """
    clean_up_instructions = []

    suffix_1 = address_suffix_pair[0]
    suffix_2 = address_suffix_pair[1]

    address_stems = set(
        [
            dimensions[0].replace(f"_{suffix_1}", "").replace(f"_{suffix_2}", "")
            for dimensions in updated_live_balances.keys()
            if dimensions[0].endswith(suffix_1) or dimensions[0].endswith(suffix_2)
        ]
    )

    total_rectified_amount = 0

    for address_stem in address_stems:
        from_address = _principal_address(address_stem, suffix_1)
        from_amount = _get_balance(
            updated_live_balances, address=from_address, denomination=denomination
        )
        # we always expect the balances to be +ve, so if they are -ve we must clean-up
        if from_amount < 0:
            to_address = _principal_address(address_stem, suffix_2)
            to_amount = _get_balance(
                updated_live_balances, address=to_address, denomination=denomination
            )
            rectified_amount = min(abs(to_amount), abs(from_amount))
            if rectified_amount > 0:
                total_rectified_amount += rectified_amount
                _move_funds_internally(
                    vault,
                    rectified_amount,
                    from_address,
                    to_address,
                    denomination,
                    f"CLEANUP_{event}",
                    clean_up_instructions,
                    in_flight_balances=None,
                )

    return clean_up_instructions, total_rectified_amount


def _publish_statement_workflow(vault, statement_end, final_statement, mad, is_final):
    """
    Publishes the statement workflow with required context.
    :param vault:
    :param statement_end: datetime, the utc end of the statement period, exclusive. For
    example, if SCOD is on 2020-02-03T16:00:00Z, end of SCOD is 2020-02-04T16:00:00Z. For final
    statements, no adjustments are needed.
    :param final_statement: Decimal, statement balance
    :param mad: Decimal, minimum amount due
    :param is_final: boolean, true when this is the final statement
    :return:
    """

    account_creation_dt = vault.get_account_creation_date()
    payment_due_period = int(
        _get_parameter(name="payment_due_period", at=account_creation_dt, vault=vault)
    )
    _, prev_scod_end = _get_previous_scod(vault, account_creation_dt)
    local_statement_end = _localize_datetime(statement_end)
    local_prev_statement_end = _localize_datetime(prev_scod_end)
    if not is_final:
        last_pdd_execution_datetime = vault.get_last_execution_time(event_type=EVENT_PDD)
        # get_last_execution_time() excludes the current scod execution, so _get_next_pdd actually
        # returns the pdd for the current scod
        current_pdd_start, current_pdd_end = _get_next_pdd(
            payment_due_period,
            account_creation_dt,
            last_pdd_execution_datetime,
            localize_datetime=True,
        )
        current_pdd_execution_datetime = current_pdd_end
        next_pdd_start, _ = _get_next_pdd(
            payment_due_period,
            account_creation_dt,
            current_pdd_execution_datetime,
            localize_datetime=True,
        )
        next_scod_start, _ = _get_scod_for_pdd(payment_due_period, next_pdd_start)

        # workflow end of statement refers to SCOD, but we typically consider statement to end at
        # end of SCOD
        local_statement_end -= timedelta(days=1)

    # The workflow provides the dates of the SCOD/PDD/Next SCOD, which will always be one day prior
    # to the actual schedules
    vault.start_workflow(
        workflow=PUBLISH_STATEMENT_DATA_WORKFLOW,
        context={
            "account_id": str(vault.account_id),
            "start_of_statement_period": str(local_prev_statement_end.date()),
            "end_of_statement_period": str(local_statement_end.date()),
            "current_statement_balance": "%0.2f" % final_statement,
            "minimum_amount_due": "%0.2f" % mad,
            "current_payment_due_date": "" if is_final else str(current_pdd_start.date()),
            "next_payment_due_date": "" if is_final else str(next_pdd_start.date()),
            "next_statement_cut_off": "" if is_final else str(next_scod_start.date()),
            "is_final": str(is_final),
        },
    )


def _override_info_balance(
    vault,
    in_flight_balances,
    balance_address,
    denomination,
    amount,
    instructions,
    trigger=EVENT_SCOD,
):
    """
    Set a specific balance to an absolute amount
    :param vault:
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution
    :param denomination: str, the balance denomination
    :param amount: Decimal, the new absolute balance amount
    :param instructions: List[PostingInstruction], extended with instructions to override the
    relevant balance
    :return: None
    """
    current_balance = _get_balance(
        in_flight_balances, address=balance_address, denomination=denomination
    )
    if current_balance == amount:
        return

    # If the new amount is more than the old amount that is a +ve on the address
    # So a -ve on the internal, which is a credit for an asset
    credit_internal = amount > current_balance

    _make_internal_address_transfer(
        custom_address=balance_address,
        credit_internal=credit_internal,
        denomination=denomination,
        amount=abs(amount - current_balance),
        instructions_to_extend=instructions,
        action=f"OVERRIDE_{balance_address}",
        trigger=trigger,
        instruction_details={"description": f"Set {balance_address} to {amount:.2f}"},
        vault=vault,
        in_flight_balances=in_flight_balances,
    )


def _get_outstanding_statement_amount(balances, denomination, fee_types, txn_types):
    """
    Calculates current outstanding statement amount by summing all principal and bank charges
    statement balances.
    Note that outstanding statement amount = statement amount when run during the statement cut-off
    calculations
    :param balances: DefaultDict[Tuple[str, str, str, Phase], Balance] the account balances to use
    when calculating the outstanding statement amount
    :param denomination: str, the statement denomination
    :param fee_types: List[str], fee types supported by the account
    :param txn_types: List[str], transaction types supported by the account
    :return: Decimal, the outstanding statement amount. Will be +ve if the account has deposit > 0
    """
    return _calculate_aggregate_balance(
        balances,
        denomination,
        fee_types,
        balance_def={
            PRINCIPAL: STATEMENT_BALANCE_STATES,
            INTEREST: STATEMENT_BALANCE_STATES,
            FEES: STATEMENT_BALANCE_STATES,
        },
        include_deposit=True,
        txn_type_map=txn_types,
    )


def _calculate_mad(
    vault,
    in_flight_balances,
    denomination,
    txn_types,
    effective_date,
    statement_amount,
    mad_eq_statement=False,
):
    """
    Calculate the MAD for the current statement. This is usually the greatest of the fixed and
    percentage-based MAD (see _calculate_percentage_mad), ensuring that MAD <= statement.
     A few exceptions apply:
    - if the statement amount is negative (i.e. deposit balance), the MAD is 0
    - if there is an active flag amongst mad_equal_to_zero_flags, the MAD is 0
    - otherwise, the MAD can be set to be equal to statement amount via the mad_eq_statement flag
    (e.g. last statement before closure)
    :param vault:
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution
    :param denomination: str, account denomination
    :param txn_types: List[str], list of transaction types
    :param effective_date: datetime, the end of SCOD
    :param statement_amount: Decimal, the full statement amount
    :param mad_eq_statement: bool, if True the MAD is set to the full statement amount
    :return: Decimal, the Minimum Amount Due for the latest statement, >= 0 and rounded to 2 dp
    """

    # If we have a negative statement amount due to over repayments MAD should be 0.
    # We also return 0 in the MAD calculation if indicated by the relevant flag, e.g. if there is an
    # active repayment holiday.
    if statement_amount <= 0 or _is_flag_in_list_applied(
        vault, MAD_EQUAL_TO_ZERO_FLAGS, effective_date
    ):
        return Decimal(0)
    elif mad_eq_statement:
        return statement_amount

    fee_types = _get_supported_fee_types(vault, txn_types)
    mad_percentages = _get_parameter(vault, MINIMUM_PERCENTAGE_DUE, effective_date, is_json=True)
    fixed_mad = _get_parameter(vault, MAD, effective_date)
    credit_limit = _get_parameter(vault, CREDIT_LIMIT, at=effective_date)

    percentage_mad = _calculate_percentage_mad(
        in_flight_balances,
        denomination,
        mad_percentages,
        txn_types,
        fee_types,
        credit_limit,
    )

    mad = max(percentage_mad, fixed_mad)

    # Cap MAD to the statement balance as customer can't repay more than what is owed
    mad = min(mad, statement_amount)

    return _round(mad, 2)


def _calculate_percentage_mad(
    in_flight_balances,
    denomination,
    mad_percentages,
    txn_types,
    fee_types,
    credit_limit,
):
    """
    Calculate MAD based on statement amounts and mad percentages. Interest and Fees percentages are
     hardcoded to 100%. 100% of overdue/overlimit amount (whichever is greater) is also added
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution,
    :param denomination: str, the account denomination
    :param mad_percentages: Dict[str, Decimal], mad percentages per transaction type
    :param txn_types: Dict[str, Optional[Dict[str, str]]], supported transaction types
    :param fee_types: List[str], supported fee types
    :param credit_limit: Decimal, the credit limit for the account. Used to determine overlimit amt
    :return: Decimal, the minimum amount due, <= 0
    """
    mad = Decimal(0)

    overlimit_amount = _get_overlimit_amount(
        in_flight_balances, credit_limit, denomination, txn_types
    )
    overdue_amount = sum(_get_overdue_balances(in_flight_balances).values())

    # Full overdue or overlimit, whichever is greatest (they are both +ve numbers)
    mad += max(overdue_amount, overlimit_amount)

    def get_mad_component(charge_type, percentage, sub_type, txn_ref=None):
        """
        calculate the contribution towards MAD of a specific component sub-type
        :param charge_type: str, PRINCIPAL, INTEREST or FEES
        :param percentage: Decimal, the percentage of the component sub-type that should be included
        in the MAD
        :param sub_type: str, the component sub-type (e.g. for PRINCIPAL this might be PURCHASE)
        :param txn_ref: Optional[str], transaction level reference
        :return: Decimal, the contribution towards MAD of a specific component sub-type
        """
        if charge_type == PRINCIPAL:
            unpaid_address = _principal_address(sub_type, UNPAID, txn_ref=txn_ref)
            billed_address = _principal_address(sub_type, BILLED, txn_ref=txn_ref)
        elif charge_type == INTEREST:
            unpaid_address = _interest_address(sub_type, UNPAID, txn_ref=txn_ref)
            billed_address = _interest_address(sub_type, BILLED, txn_ref=txn_ref)
        elif charge_type == FEES:
            unpaid_address = _fee_address(sub_type, UNPAID)
            billed_address = _fee_address(sub_type, BILLED)

        unpaid = _get_balance(in_flight_balances, address=unpaid_address, denomination=denomination)
        billed = _get_balance(in_flight_balances, address=billed_address, denomination=denomination)

        return _round(percentage * (unpaid + billed), 2)

    interest_percentage = Decimal(mad_percentages[INTEREST.lower()])
    fees_percentage = Decimal(mad_percentages[FEES.lower()])

    for txn_type, refs in txn_types.items():
        principal_percentage = Decimal(mad_percentages[txn_type.lower()])

        # If there are no refs, run loop once with txn_ref = None
        for ref in refs or [None]:
            mad += get_mad_component(
                charge_type=PRINCIPAL,
                sub_type=txn_type,
                percentage=principal_percentage,
                txn_ref=ref,
            )
            mad += get_mad_component(
                charge_type=INTEREST,
                sub_type=txn_type,
                percentage=interest_percentage,
                txn_ref=ref,
            )

    for fee_type in fee_types:
        mad += get_mad_component(charge_type=FEES, sub_type=fee_type, percentage=fees_percentage)

    return mad


def _rebalance_balance_buckets(
    vault,
    in_flight_balances,
    from_address,
    to_address,
    denomination,
    trigger,
    instructions=None,
):
    """
    Move positive balance from one bucket (from_address) to another (to_balance)
    :param vault:
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution
    :param from_address: str, the address to rebalance from
    :param to_address: str, the address to rebalance to
    :param denomination: str, the balance denomination
    :param trigger: str, describes what is causing the action. Must make the client-transaction-id
    unique enough
    :param instructions: list(PostingInstruction), to be extended by the method with postings to
    rebalance buckets
    :return: None
    """
    amount = _get_balance(in_flight_balances, address=from_address, denomination=denomination)

    if abs(amount) > 0:
        _move_funds_internally(
            vault,
            abs(amount),
            to_address,
            from_address,
            denomination,
            trigger,
            instructions,
            in_flight_balances,
        )
        return amount

    return Decimal(0)


def _charge_fee(
    vault,
    denomination,
    in_flight_balances,
    instructions,
    fee_type,
    supported_txn_types,
    amount=None,
    is_external_fee=False,
    trigger="",
):
    """
    Create postings to charge and rebalance a fee and update internal accounts.
    No postings created if amount is not >0
    :param vault:
    :param denomination: str, denomination to charge the fee amount in
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance] account balances
    updated with posting instructions created within the current hook execution
    :param instructions: List[PostingInstruction], to be extended by the method with postings to
    charge interest and rebalance
    :param fee_type: str, the fee type to be added to metadata
    :param supported_txn_types: List[str], the transaction types supported by the contract
    :param is_external_fee: bool, set to True if fee is initiated outside of the contract
    :param amount: Optional[Decimal], the fee amount. Only required for external fees
    :return: Decimal, fee amount
    """

    if not is_external_fee:
        amount = _get_parameter(name=fee_type.lower(), vault=vault)
    if amount == 0:
        return Decimal(0)

    income_account, loan_account = _get_fee_internal_accounts(vault, fee_type, "", is_external_fee)

    _rebalance_fees(
        vault,
        amount,
        denomination,
        in_flight_balances,
        income_account,
        loan_account,
        supported_txn_types,
        trigger,
        instructions,
        fee_type,
        is_external_fee=is_external_fee,
    )

    return amount


def _get_fee_internal_accounts(vault, fee_type=None, txn_type=None, is_external_fee=False):
    """
    Helper to retrieve the income and loan principal accounts for either a transaction type
    fee or a regular fee
    :param vault:
    :param fee_type: Optional[str], fee type to retrieve accounts for. None if charging a
     non-transaction fee
    :param txn_type: Optional[str], transaction type to retrieve accounts for. Must be non-None if
     charging a transaction fee
    :param is_external_fee: bool, True if the fee is initiated outside the contract
    :return: Tuple[str, str], income and loan principal accounts
    """

    if is_external_fee:
        fee_internal_accounts = _get_parameter(
            name=EXTERNAL_FEE_INTERNAL_ACCOUNTS, is_json=True, vault=vault
        )[fee_type.lower()]
    elif txn_type:
        fee_internal_accounts = _get_parameter(
            name=TXN_TYPE_FEES_INTERNAL_ACCOUNTS_MAP, is_json=True, vault=vault
        )[txn_type.lower()]
    else:
        fee_internal_accounts = _get_parameter(
            name=f"{fee_type.lower()}_internal_accounts", is_json=True, vault=vault
        )

    return fee_internal_accounts["income"], fee_internal_accounts["loan"]


def _charge_interest(
    vault,
    is_revolver,
    denomination,
    accruals_by_sub_type,
    txn_types_to_charge_interest_from_txn_date,
    in_flight_balances,
    instructions,
    accrual_cut_off_dt,
    supported_txn_types,
    txn_types_in_interest_free_period=None,
    is_pdd=False,
    charge_interest_free_period=False,
):
    """
    Creates postings to charge accrued interest and rebalance accordingly
    :param vault:
    :param is_revolver: bool, indicates whether the account is currently revolver or not
    :param denomination: str, account denomination
    :param accruals_by_sub_type: Dict[str: Dict[str: Decimal]], when no transaction refs are present
     or fees
    for a transaction type the nested Dict is replaced by a standalone Decimal. Represents accruals
    for each transaction type.
    :param txn_types_to_charge_interest_from_txn_date: List[str], list of transaction types that
    get charged interest straight away from the date of transaction
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution
    :param instructions: List[PostingInstruction], to be extended by the method with postings to
    charge interest and rebalance
    :param accrual_cut_off_dt: datetime, the cut-off for the last accrual included in the charge.
    :param supported_txn_types: List[str], supported transaction types from parameters
    :param txn_types_in_interest_free_period: Dict[str, Optional[List[str]]], transaction types
    and refs that have an active interest free period
    :param is_pdd: bool, true if we are charging interest from PDD
    :param charge_interest_free_period: bool, indicates whether code is called on PDD given that MAD
    was unpaid, which means interests charged under interest free periods will now be chargeable
    :return:
    """

    txn_types_in_interest_free_period = txn_types_in_interest_free_period or {}

    if is_revolver:
        accruals_to_charge = accruals_by_sub_type
    else:
        accruals_to_charge = {
            (charge_type, sub_type, accrual_type): accrual_amount
            for (
                charge_type,
                sub_type,
                accrual_type,
            ), accrual_amount in accruals_by_sub_type.items()
            if sub_type.lower() in txn_types_to_charge_interest_from_txn_date
        }

    local_accrual_cut_off_date = _localize_datetime(accrual_cut_off_dt).date()

    def _charge_interest_per_txn_type(
        charge_type, sub_type, txn_charge_amount, txn_ref="", accrual_type=None
    ):
        """
        :param charge_type: str, one of PRINCIPAL, FEES or INTEREST
        :param sub_type: str, transaction or fee type
        :param txn_charge_amount: Decimal, amount to charge for transaction type
        :param txn_ref: Optional[str], transaction reference
        :param accrual_type: Optional[str], either '' or PRE_SCOD or POST_SCOD applicable for
        interest accrual to _UNCHARGED balances from txn day
        :return:
        """
        if txn_charge_amount == 0:
            return
        txn_charge_amount = abs(txn_charge_amount)
        txn_stem = f"{sub_type}_{txn_ref}" if txn_ref else sub_type

        # This block is used on PDD if we dip into revolver balance,
        # where we cancel out the existing UNCHARGED balance so that we can move it to CHARGED.
        # If _charge_interest is called during normal interest accrual events,
        # interest will be charged immediately so we have no need for this reversing call.
        # For the charge_interest_free_period case, we will rely on specific code under
        # _process_payment_due_date to reverse uncharged interest.
        if is_pdd and not charge_interest_free_period:
            txn_stem_with_accrual_type = f"{txn_stem}_{accrual_type}" if accrual_type else txn_stem
            _make_accrual_posting(
                vault,
                accrual_amount=txn_charge_amount,
                denomination=denomination,
                stem=txn_stem,
                instructions=instructions,
                reverse=True,
                instruction_details={
                    "description": f"Uncharged interest reversed for "
                    f"{txn_stem_with_accrual_type} - INTEREST_CHARGED"
                },
                accrual_type=accrual_type,
            )

        trigger_base = INTEREST
        if charge_interest_free_period:
            trigger_base = f"{INTEREST_FREE_PERIOD}_{trigger_base}"
        elif accrual_type:
            # need to make trigger for pre/post uncharged interest addresses unique
            trigger_base = f"{accrual_type.upper()}_{trigger_base}"

        _rebalance_interest(
            vault,
            txn_charge_amount,
            denomination,
            in_flight_balances,
            local_accrual_cut_off_date,
            supported_txn_types,
            charge_type,
            sub_type,
            instructions,
            txn_ref=txn_ref,
            trigger_base=trigger_base,
        )

    for charge_sub_and_accrual_type, ref_to_amount in accruals_to_charge.items():
        charge_type, sub_type, accrual_type = charge_sub_and_accrual_type
        for ref, amounts in ref_to_amount.items():
            # If there is an active interest free period and _charge_interest is called by
            # EVENT_ACCRUE, i.e. is_pdd=False, we don't want to charge interest for the txn type
            # Instead we will make sure it's accrued as uncharged interest to be realised or wiped
            # out during PDD.
            if is_pdd or not _is_txn_type_in_interest_free_period(
                txn_types_in_interest_free_period, sub_type, ref
            ):
                _charge_interest_per_txn_type(
                    charge_type,
                    sub_type.upper(),
                    amounts,
                    txn_ref=ref,
                    accrual_type=accrual_type,
                )


def _process_payment_due_date(vault, effective_date):
    """
    Based on repayments received since SCOD, check if Customer repaid:
    - Less than MAD -> charge late repayment
    - More than MAD but less than full statement amount -> set account to revolver and charge
      uncharged interest
    - All statement -> reverse any uncharged interest
    :param vault:
    :param effective_date: datetime, the PDD logical schedule execution datetime
    :return: None
    """

    denomination = _get_parameter(name=DENOMINATION, vault=vault)
    credit_limit = _get_parameter(name=CREDIT_LIMIT, vault=vault)
    # We use live balances as there is no cut-off for PDD.
    live_balance_dt, live_balances = vault.get_balance_timeseries().all()[-1]
    in_flight_balances = _deep_copy_balances(live_balances)
    # live_balance_dt could be < effective_date if there have been no postings recently
    effective_date = max(live_balance_dt, effective_date)
    supported_txn_types = _get_supported_txn_types(vault, effective_date)
    supported_fee_types = _get_supported_fee_types(vault, supported_txn_types)

    # Find out whether we accrue interest from transaction day, for later checks
    accrue_interest_from_txn_day = _is_txn_interest_accrual_from_txn_day(vault)

    outstanding_statement_balance = _get_outstanding_statement_amount(
        in_flight_balances, denomination, supported_fee_types, supported_txn_types
    )

    # We always want to have all INTEREST_FREE_PERIOD_INTEREST_UNCHARGED addresses zeroed on PDD
    # Depending on conditions, we may be moving this balance to the CHARGED address
    interest_free_txn_types = {
        f"{txn_type}_{INTEREST_FREE_PERIOD}": supported_txn_types[txn_type]
        for txn_type in set(supported_txn_types)
    }
    instructions = _reverse_uncharged_interest(
        vault,
        in_flight_balances,
        denomination,
        interest_free_txn_types,
        "REVERSE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED",
    )

    # If not revolving and the full statement balance was paid off, zero out all uncharged interest
    if outstanding_statement_balance <= 0 and not _is_revolver(in_flight_balances, denomination):
        if accrue_interest_from_txn_day:
            # <txn_type>_INTEREST_POST_SCOD_UNCHARGED is zeroed out
            # <txn_type>_INTEREST_PRE_SCOD_UNCHARGED is untouched since it's zeroed out at scod
            instructions.extend(
                _reverse_uncharged_interest(
                    vault,
                    in_flight_balances,
                    denomination,
                    supported_txn_types,
                    "OUTSTANDING_REPAID",
                    POST_SCOD,
                )
            )
        else:
            instructions.extend(
                _reverse_uncharged_interest(
                    vault,
                    in_flight_balances,
                    denomination,
                    supported_txn_types,
                    "OUTSTANDING_REPAID",
                )
            )
        if instructions:
            vault.instruct_posting_batch(
                posting_instructions=instructions,
                effective_date=effective_date,
                client_batch_id=f"ZERO_OUT_ACCRUED_INTEREST-{vault.get_hook_execution_id()}",
            )
        return

    new_overdue_amount = 0
    accrual_cut_off = effective_date - timedelta(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
        microseconds=1,
    )
    if not _is_revolver(in_flight_balances, denomination):
        # Outstanding statement balance was not paid so the account is now revolver
        _change_revolver_status(
            vault,
            denomination,
            in_flight_balances,
            revolver=True,
            instructions=instructions,
            trigger="STATEMENT_BALANCE_NOT_PAID",
        )

        accruals_by_sub_type = {}
        for dimensions, amount in in_flight_balances.items():
            address = dimensions[0]
            if address.endswith(INTEREST_FREE_PERIOD_UNCHARGED_INTEREST_BALANCE):
                # We have separate code to deal with the charging interest free period interest case
                pass
            elif address.endswith(UNCHARGED):
                # These balance addresses look like this:
                # For non-reference based transactions - PUCHASE_INTEREST_UNCHARGED
                # For reference based transactions - BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED
                # If accrue_interest_from_txn_day is enabled, balance addresses look like:
                # For non-reference based transactions - PUCHASE_INTEREST_POST/PRE_SCOD_UNCHARGED
                # For reference based transactions
                #  - BALANCE_TRANSFER_REF1_INTEREST_POST / PRE_SCOD_UNCHARGED
                charge_type = PRINCIPAL
                if accrue_interest_from_txn_day:
                    # to accommodate the PRE/POST_SCOD part of the address, build out the
                    # appropriate address type below
                    for accrual_type in ACCRUAL_TYPES:
                        if address.endswith(f"{accrual_type}_{UNCHARGED}"):
                            # If entering revolver, both PRE & POST address are moved to
                            # INTEREST_CHARGED
                            sub_type, ref = _get_txn_type_and_ref_from_address(
                                address,
                                supported_txn_types.keys(),
                                f"{INTEREST}_{accrual_type}_{UNCHARGED}",
                            )
                            _set_accruals_by_sub_type(
                                accruals_by_sub_type,
                                charge_type,
                                sub_type,
                                ref,
                                amount.net,
                                accrual_type=accrual_type,
                            )

                else:
                    sub_type, ref = _get_txn_type_and_ref_from_address(
                        address, supported_txn_types.keys(), UNCHARGED_INTEREST_BALANCE
                    )
                    _set_accruals_by_sub_type(
                        accruals_by_sub_type, charge_type, sub_type, ref, amount.net
                    )

        _charge_interest(
            vault,
            is_revolver=True,
            denomination=denomination,
            txn_types_to_charge_interest_from_txn_date=[],
            in_flight_balances=in_flight_balances,
            accruals_by_sub_type=accruals_by_sub_type,
            instructions=instructions,
            accrual_cut_off_dt=accrual_cut_off,
            supported_txn_types=supported_txn_types,
            is_pdd=True,
        )

    repayments = _get_balance(
        in_flight_balances,
        address=TRACK_STATEMENT_REPAYMENTS,
        denomination=denomination,
    )

    mad = _get_balance(in_flight_balances, address=MAD_BALANCE, denomination=denomination)
    if _is_flag_in_list_applied(vault, MAD_EQUAL_TO_ZERO_FLAGS, effective_date):
        # MAD zero out flag active, e.g. there is an active repayment holiday.
        # We do not require any MAD payment, and will zero out existing MAD balance.
        instructions.extend(_zero_out_mad_balance(vault, mad, denomination))
    elif mad > repayments:
        # If the repayment did not cover the MAD
        new_overdue_total = mad - repayments
        # new_overdue_amount should not double count what was already overdue in MAD
        # (e.g missed MAD based on overdue of 100 and fees of 100 only adds extra 100 to overdue)
        current_overdue_total = sum(_get_overdue_balances(in_flight_balances).values())
        # We need to prevent overdue total from being negative if repayments + current overdue
        # amount exceed MAD
        new_overdue_amount = max(new_overdue_total - current_overdue_total, 0)

        _charge_fee(
            vault,
            denomination,
            in_flight_balances,
            instructions,
            LATE_REPAYMENT_FEE,
            supported_txn_types,
        )

        # Expire all interest free periods
        # Interest accrued from this statement period will be charged
        vault.start_workflow(
            workflow=EXPIRE_INTEREST_FREE_PERIODS_WORKFLOW,
            context={"account_id": str(vault.account_id)},
        )

        accruals_by_sub_type = {}
        for dimensions, amount in in_flight_balances.items():
            address = dimensions[0]

            charge_type = PRINCIPAL
            if address.endswith(INTEREST_FREE_PERIOD_UNCHARGED_INTEREST_BALANCE):
                # These balance addresses look like this:
                # For non-reference based transactions
                # - PUCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED
                # For reference based transactions
                # - BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED
                sub_type, ref = _get_txn_type_and_ref_from_address(
                    address,
                    supported_txn_types.keys(),
                    INTEREST_FREE_PERIOD_UNCHARGED_INTEREST_BALANCE,
                )

                _set_accruals_by_sub_type(
                    accruals_by_sub_type, charge_type, sub_type, ref, amount.net
                )

        # The interest accrued on the INTEREST_FREE_PERIOD_INTEREST_UNCHARGED address will now be
        # charged. Supply charge_interest_free_period=True into our _charge_interest call to avoid
        # duplicated client transaction IDs out of the _charge_interest call in the revolver logic.
        _charge_interest(
            vault,
            is_revolver=True,
            denomination=denomination,
            txn_types_to_charge_interest_from_txn_date=[],
            in_flight_balances=in_flight_balances,
            accruals_by_sub_type=accruals_by_sub_type,
            instructions=instructions,
            accrual_cut_off_dt=accrual_cut_off,
            supported_txn_types=supported_txn_types,
            is_pdd=True,
            charge_interest_free_period=True,
        )

    _adjust_aggregate_balances(
        denomination,
        in_flight_balances,
        instructions,
        vault,
        trigger=EVENT_PDD,
        effective_datetime=effective_date,
        credit_limit=credit_limit,
    )

    # This takes care of moving any outstanding statement balances to overdue or past due
    _move_outstanding_statement(
        vault,
        in_flight_balances,
        denomination,
        new_overdue_amount,
        supported_txn_types,
        instructions,
        effective_date,
    )

    if instructions:
        vault.instruct_posting_batch(
            posting_instructions=instructions,
            effective_date=effective_date,
            client_batch_id=f"PDD-{vault.get_hook_execution_id()}",
        )


def _move_outstanding_statement(
    vault,
    in_flight_balances,
    denomination,
    overdue_total,
    supported_txn_types,
    instructions,
    effective_date,
):
    """
    Update overdue and unpaid buckets based on balances at PDD cut-off.
    :param vault:
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution
    :param denomination: str, account denomination
    :param overdue_total: Decimal, MAD - total repayments as of the PDD cut-off
    :param supported_txn_types: List[str], supported transaction types from parameters
    :param instructions: List[PostingInstruction], posting instructions to be extended with
    postings to adjust outstanding statement balances
    :param effective_date: datetime, the PDD logical schedule execution datetime
    :return: None
    """

    if not _is_flag_in_list_applied(vault, OVERDUE_AMOUNT_BLOCKING_FLAGS, effective_date):
        _update_overdue_buckets(
            vault, overdue_total, in_flight_balances, denomination, instructions
        )

    if not _is_flag_in_list_applied(
        vault, BILLED_TO_UNPAID_TRANSFER_BLOCKING_FLAGS, effective_date
    ):
        supported_fee_types = _get_supported_fee_types(vault, supported_txn_types)

        _move_outstanding_statement_balances_to_unpaid(
            vault,
            in_flight_balances,
            denomination,
            supported_txn_types,
            supported_fee_types,
            instructions,
        )

    return instructions


def _update_overdue_buckets(
    vault,
    overdue_total: Decimal,
    in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance],
    denomination: str,
    instructions: list[PostingInstruction],
):
    """
    Cycles existing overdue buckets and populates latest overdue bucket if required.
    :param vault:
    :param overdue_total: overdue amount for this cycle, i.e. MAD not covered by repayments
     (which are both -ve)
    :param in_flight_balances: latest account
     balances updated with posting instructions created within the current hook execution
    :param denomination: account denomination
    :param instructions: posting instructions to be extended with
    postings to adjust overdue buckets
    :return: None
    """

    # The latest overdue bucket is populated with what hasn't been repaid in the last cycle
    new_overdue_buckets = {OVERDUE + "_1": overdue_total}

    # if any existing overdue buckets, shift them down as they've now aged by a cycle
    existing_overdue_balances = _get_overdue_balances(in_flight_balances)

    if existing_overdue_balances:
        new_overdue_buckets.update(
            {
                _age_overdue_address(overdue_address): amount
                for overdue_address, amount in existing_overdue_balances.items()
            }
        )

    for overdue_bucket, amount in new_overdue_buckets.items():
        _override_info_balance(
            vault,
            in_flight_balances,
            overdue_bucket,
            denomination,
            amount,
            instructions,
            trigger=EVENT_PDD,
        )


def _get_overdue_balances(balances):
    """
    For a given set of vault balances, get all the overdue buckets and corresponding amounts.
    :param balances: DefaultDict[Tuple[str, str, str, Phase], Balance], balances to use
    :return: Dict[str, str], overdue address to overdue amount
    """

    return {
        dimensions[0]: amount.net
        for dimensions, amount in balances.items()
        if dimensions[0].startswith(OVERDUE)
    }


def _get_overdue_address_age(overdue_address):
    """
    Given an overdue address get the age from the name.
    :param overdue_address: str, the address to get the age for
    :return:
    """
    return int(overdue_address.replace(OVERDUE + "_", ""))


def _age_overdue_address(overdue_address):
    """
    Creates the new address for an overdue balance when it has aged by a cycle
    :param overdue_address: str, current address (e.g. OVERDUE_1)
    :return: str, aged overdue address (e.g. OVERDUE_2 if the input was OVERDUE_1)
    """

    new_age = _get_overdue_address_age(overdue_address) + 1

    return OVERDUE + "_" + str(new_age)


def _get_balance(
    balances,
    address=DEFAULT_ADDRESS,
    asset=DEFAULT_ASSET,
    denomination=None,
    phase=Phase.COMMITTED,
):
    """
    Given a Balance, get the net amount.
    :param balances:
    :param address:
    :param asset:
    :param denomination:
    :param phase:
    :return:
    """
    return balances[address, asset, denomination, phase].net


def _move_outstanding_statement_balances_to_unpaid(
    vault,
    in_flight_balances,
    denomination,
    supported_txn_types,
    supported_fee_types,
    instructions,
):
    """
    Move any unpaid statement amount to past_due.
    :param vault:
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution
    :param denomination: str, account denomination
    :param supported_txn_types: List[str], supported transaction types
    :param supported_fee_types: List[str], supported fee types
    :param instructions: List[PostingInstruction], list of posting instructions to be made for PDD.
    Extended by this method
    :return: None
    """

    def move_statement_balance_to_unpaid(charge_type, sub_type, txn_ref=None):
        """
        Move from billed to unpaid for a given charge type
        :param charge_type: str, one of PRINCIPAL, FEES or INTEREST
        :param sub_type: str, name of txn_type or fee_type to be passed for address creation
        :param txn_ref: Optional(str), transaction level reference
        """
        if charge_type == PRINCIPAL:
            statement_address = _principal_address(sub_type, BILLED, txn_ref=txn_ref)
            past_due_address = _principal_address(sub_type, UNPAID, txn_ref=txn_ref)
        elif charge_type == INTEREST:
            statement_address = _interest_address(sub_type, BILLED, txn_ref=txn_ref)
            past_due_address = _interest_address(sub_type, UNPAID, txn_ref=txn_ref)
        elif charge_type == FEES:
            statement_address = _fee_address(sub_type, BILLED)
            past_due_address = _fee_address(sub_type, UNPAID)

        statement_to_past_due = _get_balance(
            in_flight_balances, address=statement_address, denomination=denomination
        )
        if statement_to_past_due > 0:
            _move_funds_internally(
                vault,
                amount=statement_to_past_due,
                from_account_address=past_due_address,
                to_account_address=statement_address,
                denomination=denomination,
                trigger=EVENT_PDD,
                instructions=instructions,
                in_flight_balances=in_flight_balances,
            )

    for txn_type, refs in supported_txn_types.items():
        for ref in refs or [None]:
            move_statement_balance_to_unpaid(charge_type=PRINCIPAL, sub_type=txn_type, txn_ref=ref)
            move_statement_balance_to_unpaid(charge_type=INTEREST, sub_type=txn_type, txn_ref=ref)

    for fee_type in supported_fee_types:
        move_statement_balance_to_unpaid(charge_type=FEES, sub_type=fee_type)
        move_statement_balance_to_unpaid(charge_type=INTEREST, sub_type=fee_type)


def _move_funds_internally(
    vault,
    amount,
    from_account_address,
    to_account_address,
    denomination,
    trigger,
    instructions,
    in_flight_balances,
):
    """
    Assumes positive fund move - if need to move negative number - swap from and to account
    :param vault:
    :param amount: Decimal, amount to transfer
    :param from_account_address: address on the current account to transfer from
    :param to_account_address: address on the current account to transfer to
    :param denomination: str, denomination of the amount to transfer
    :param trigger: str, describes what is causing the postings. Must make the client-transaction-id
    unique enough
    :param instructions: List[PostingInstruction], list of posting instructions to be made.
    Extended by this method
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], latest account
     balances updated with posting instructions created within the current hook execution
    :return: None
    """
    if amount <= 0:
        return

    _create_postings(
        vault,
        amount,
        instructions,
        from_account_id=vault.account_id,
        to_account_id=vault.account_id,
        action=f"REBALANCE_{from_account_address}_TO_{to_account_address}",
        denomination=denomination,
        from_address=from_account_address,
        instruction_details={
            "description": f"Move balance from {from_account_address} to " f"{to_account_address}"
        },
        to_address=to_account_address,
        trigger=trigger,
        in_flight_balances=in_flight_balances,
    )


def _reverse_uncharged_interest(
    vault,
    in_flight_balances,
    denomination,
    supported_txn_types,
    trigger,
    accrual_type=None,
):
    """
    Creates posting instructions to reverse all uncharged interest.
    :param vault:
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance] account balances
    updated with posting instructions created within the current hook execution
    :param denomination: str, the account denomination
    :param supported_txn_types: Dict[str, Optional[List[str]]], supported transaction types
    :param trigger: str, explains why the action needs performing. Used to make
     client-transaction-id unique enough and populate instruction details
    :param accrual_type: Optional[str], either '' or PRE_SCOD or POST_SCOD applicable for interest
     accrual to _UNCHARGED balances from txn day
    :return: List[PostingInstruction], list of postings to zero out accrued interest
    """

    def _execute_reversal(txn_type, txn_ref=None):
        """
        Instruct posting for interest reversal.
        :param txn_type: str, transaction type
        :param txn_ref: Optional[str], transaction level reference
        """
        address = _interest_address(txn_type, UNCHARGED, txn_ref=txn_ref, accrual_type=accrual_type)
        accrued_outgoing = _get_balance(
            in_flight_balances, address=address, denomination=denomination
        )
        if accrued_outgoing > 0:
            if txn_ref:
                if txn_type.endswith(INTEREST_FREE_PERIOD):
                    stem = (
                        f"{txn_type[:-(len(INTEREST_FREE_PERIOD)+1)]}_"
                        f"{txn_ref}_{INTEREST_FREE_PERIOD}"
                    )
                else:
                    stem = f"{txn_type}_{txn_ref}"
            else:
                stem = txn_type
            stem_with_accrual_type = f"{stem}_{accrual_type}" if accrual_type else stem
            _make_accrual_posting(
                vault,
                accrual_amount=accrued_outgoing,
                denomination=denomination,
                stem=stem,
                instruction_details={
                    "description": f"Uncharged interest reversed for "
                    f"{stem_with_accrual_type} - {trigger}"
                },
                instructions=instructions,
                reverse=True,
                accrual_type=accrual_type,
            )

    instructions = []
    for txn_type, txn_refs in supported_txn_types.items():
        for txn_ref in txn_refs or [None]:
            _execute_reversal(txn_type, txn_ref=txn_ref)

    return instructions


def _zero_out_mad_balance(vault, mad_balance, denomination):
    """
    Creates posting instructions to zero out the MAD_BALANCE address.
    :param vault:
    :param mad_balance: Decimal, the amount in the MAD_BALANCE address.
    :param denomination: str, the account denomination
    :return: List[PostingInstruction], list of postings to zero out MAD_BALANCE
    """
    instructions = []
    if mad_balance > 0:
        _make_internal_address_transfer(
            amount=mad_balance,
            denomination=denomination,
            credit_internal=False,
            custom_address=MAD_BALANCE,
            action="ZERO_OUT_MAD_BALANCE",
            trigger="MAD_BALANCE",
            instruction_details={"description": "MAD balance zeroed out"},
            instructions_to_extend=instructions,
            vault=vault,
        )
    return instructions


def _principal_address(txn_type, txn_type_status, txn_ref=None):
    """
    get the balance address that contains transaction type for a given status, injecting reference
    if present.
    :param txn_type: str, a supported transaction type
    :param txn_type_status: str, a supported transaction type status.
    One of: AUTH, CHARGED, BILLED, UNPAID
    :param txn_ref: Optional[str], Reference only populated for types tracked at a transaction level
    :return: str, balance address. For example, CASH_ADVANCE_AUTH or BALANCE_TRANSFER_REF1_BILLED
    """
    return (
        (f"{txn_type.upper()}_{txn_ref}_{txn_type_status}")
        if txn_ref
        else f"{txn_type}_{txn_type_status}"
    )


def _interest_address(txn_type, interest_status, txn_ref=None, accrual_type=None):
    """
    Get the balance address for transaction type's interest of a specific status  E.g. UNCHARGED
    interest for PURCHASE transactions.
    :param txn_type: str, a supported transaction type
    :param interest_status: str, a supported interest status. One of: UNCHARGED, CHARGED, BILLED
    :param txn_ref: str, Reference only populated for types tracked at a transaction level.
    :param accrual_type: Optional[str], either '' or PRE_SCOD or POST_SCOD applicable for interest
     accrual to _UNCHARGED balances from txn day
    :return: str, balance address. For example, PURCHASE_INTEREST_BILLED
    """
    address_deconstructed = [
        txn_type.upper(),
        txn_ref,
        INTEREST,
        accrual_type,
        interest_status,
    ]

    # Account for transaction types with Interest Free period enabled (reflected in txn_type)
    if txn_ref and txn_type.upper().endswith(INTEREST_FREE_PERIOD):
        return (
            f"{txn_type.upper()[:-(len(INTEREST_FREE_PERIOD)+1)]}_{txn_ref}_"
            f"{INTEREST_FREE_PERIOD}_{INTEREST}_{interest_status}"
        )

    # Construct the full address by filtering out the attributes which have a value of None
    # (weren't passed in the function)
    interest_address = "_".join(
        [address_element for address_element in address_deconstructed if address_element]
    )
    return interest_address


def _fee_address(fee_type, fee_status):
    """
    get the balance address that contains fees for a certain type (e.g. CASH_ADVANCE_FEES_BILLED).
    Fees always charged at a type level, so references not considered.
    :param fee_type: str, a supported fee type. See FEE_TYPES constant
    :param fee_status: str, a supported fee status. One of: CHARGED, BILLED, UNPAID
    :return: str, balance address. For example, FEES_CHARGED
    """
    return f"{fee_type}S_{fee_status}"


def _charge_overlimit_fee(
    vault,
    in_flight_balances,
    denomination,
    supported_txn_types,
    instructions,
    credit_limit,
):
    """
    Charge over limit fee if there is any over limit balance at SCOD
    :param vault:
    :param in_flight_balances: DefaultDict[Tuple[str, str, str, Phase], Balance], balances used to
     check if the account is overlimit or not
    :param denomination: str, denomination for the over limit fee
    :param supported_txn_types: List[str], list of supported transaction types
    :param instructions: List[PostingInstruction], list of posting instructions to be extended with
    any over limit fee postings
    :param credit_limit: Decimal, the account's credit limit at SCOD cut-off
    :return: None
    """

    opt_in = _str_to_bool(
        _get_parameter(vault, OVERLIMIT_OPT_IN, optional=True, default_value="False")
    )
    overlimit_amount = _get_overlimit_amount(
        in_flight_balances, credit_limit, denomination, supported_txn_types
    )

    # We don't charge a fee if customer has gone overlimit due to stand-in/offline transaction but
    # never explicitly opted-in to the overlimit facility
    if overlimit_amount > 0 and opt_in:
        fee = _charge_fee(
            vault,
            denomination,
            in_flight_balances,
            instructions,
            OVERLIMIT_FEE,
            supported_txn_types,
        )
        if fee == 0:
            return

        _adjust_aggregate_balances(
            denomination,
            in_flight_balances,
            instructions,
            vault,
            trigger=OVERLIMIT_FEE,
            outstanding=False,
            full_outstanding=False,
            credit_limit=credit_limit,
        )


def _get_overlimit_amount(balances, credit_limit, denomination, supported_txn_types):
    """
    Determines how much the account is overlimit by. A customer is considered overlimit if the
    total principal amount is greater than the customer's credit limit. Principal only includes
     charged, billed or unpaid transactions.
    :param balances: Dict[Tuple[str, str, str, Phase], Balance]
    :param credit_limit: Decimal, account's credit limit (positive),
    :param denomination: str, the account denomination
    :param supported_txn_types: Dict[str, Optional[List[str]], Map of supported transaction types
    :return: Decimal, how much the account is over limit by. This number is >= 0
    """

    return max(
        _calculate_aggregate_balance(
            balances,
            denomination,
            fee_types=[],
            balance_def={PRINCIPAL: CHARGED_BALANCE_STATES},
            include_deposit=False,  # we want to return >=0 but including deposit could make it -ve
            txn_type_map=supported_txn_types,
        )
        - credit_limit,
        0,
    )


def _get_parameter(
    vault,
    name: str,
    at: Optional[datetime] = None,
    is_json: bool = False,
    optional: bool = False,
    default_value: Optional[Any] = None,
    upper_case_dict_values: bool = False,
    upper_case_list_values: bool = False,
) -> Any:
    """
    Get the parameter value for a given parameter
    :param vault:
    :param name: string, name of the parameter to retrieve
    :param at: Optional datetime, time at which to retrieve the parameter value. If not
    specified the latest value is retrieved
    :param is_json: if true json_loads is called on the retrieved parameter value
    :param optional: if true we treat the parameter as optional
    :param default_value: Optional, if the optional function parameter is True, and the optional
    parameter is not set, this value is returned
    :param upper_case_dict_values: if is_json is True and we are expecting the parameter to take
    shape dict[str, dict[str,str]], we will convert the dict[str,str] values to upper case
    :param upper_case_list_values: if is_json is True and we are expecting the parameter to take
    shape dict[str:list[str]], we will convert the list[str] values to upper case then we will
    return the dict values in upper case, whether these values are str/list/dict
    :return:
    """
    if at:
        parameter = vault.get_parameter_timeseries(name=name).at(timestamp=at)
    else:
        parameter = vault.get_parameter_timeseries(name=name).latest()

    if optional:
        parameter = parameter.value if parameter.is_set() else default_value

    if is_json:
        try:
            parameter = json_loads(parameter)
        except:  # noqa: E722 - we don't have access to the correct exception
            raise InvalidContractParameter(
                f"Exception while JSON loading parameter {name}\nValue {parameter}"
            )

        # We convert dictionary values to upper case based on the date type shape.
        # The converted values often represent transaction references, which we always
        # want to parse in upper case.
        # The dictionary keys often represent transaction types, which we want to
        # keep in the original case.
        if upper_case_dict_values:
            parameter = {
                key: {str(i).upper(): str(j).upper() for i, j in value.items()}
                for key, value in parameter.items()
            }
        elif upper_case_list_values:
            parameter = {key: [str(i).upper() for i in value] for key, value in parameter.items()}

    return parameter


def _is_flag_in_list_applied(vault, parameter_name, effective_date):
    """
    Determine if a flag is set and active for a customer from a given list of flag names
    :param vault:
    :param parameter_name: string, name of the parameter to retrieve
    :param effective_date: datetime, time at which to retrieve the flag value. If not
    specified the latest value is retrieved
    :return: bool, true if parameter exists in list
    """
    list_of_flag_names = _get_parameter(vault, name=parameter_name, at=effective_date, is_json=True)
    for flag_name in list_of_flag_names:
        if vault.get_flag_timeseries(flag=flag_name).at(timestamp=effective_date):
            return True

    return False


def _cti(vault, action="", trigger=""):
    """
    Create client transaction id.
    :param vault:
    :param action:
    :param trigger:
    :return:
    """
    when = vault.get_hook_execution_id()
    # client transaction ids tell us action happened, when/where and trigger
    return f"{action}-{when}-{trigger}"


def _str_to_bool(string):
    """
    Convert a string true to bool True, default value of False.
    :param string:
    :return:
    """
    return str(string).lower() == "true"


def _get_non_advice_postings(postings):
    """
    Filters out postings that have no advice attribute or advice set to false. This is needed as
    the advice attribute is not populated on instructions that do not support it.
    :param postings: List[PostingInstruction]
    :return: List[PostingInstruction], filtered postings. If a PostingInstructionBatch is passed in
    the returned object will not have any of the batch's attributes/methods
    """

    return [
        posting
        for posting in postings
        if posting.type
        in [
            PostingInstructionType.RELEASE,
            PostingInstructionType.TRANSFER,
            PostingInstructionType.CUSTOM_INSTRUCTION,
        ]
        or posting.advice is False
    ]


def _deep_copy_balances(balances):
    """
    Makes a deep copy of the input balances
    :param balances: Dict[Tuple[str, str, str, Phase], Balance] balances to copy
    :return: DefaultDict[Tuple[str, str, str, Phase], Balance], deep copy of the balances
    """

    new_balances = BalanceDefaultDict(lambda *_: Balance())
    new_balances += balances
    return new_balances


def _update_balances(account_id, balances, postings):
    """
    Updates the balances for an account based on new postings that are made.
    :param account_id: str, account id in question. Optional if postings is not used
    :param balances: DefaultDict[Tuple[str, str, str, str], Balance] the balances to
     update
    :param postings: List[PostingInstruction], new postings to adjust balances with
    :return: None
    """

    for posting in postings:
        if account_id == posting.account_id:
            # For release/settlements there could be more than one key-value pair in .balances()
            balances += posting.balances()


def _get_txn_type_and_ref_from_address(address, base_txn_types, address_type):
    """
    Extract the transaction type & reference given a transaction balance address
    Example addresses:
    - CASH_PURCHASE_INTEREST_UNCHARGED
    - BALANCE_TRANSFER_REF1_INTEREST_CHARGED
    - BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED

    - PURCHASE_INTEREST_POST_SCOD_UNCHARGED
    - BALANCE_TRANSFER_REF1_INTEREST_PRE_SCOD_UNCHARGED

    :param address: str, the address to split into (type, ref) pairs (upper case)
    :param base_txn_types: List[str], transaction types without any references appended (upper case)
    :param address_type: str, the string at the end of address that we slice off to obtain our
    TXN_TYPE_REF stem
    :return: (str, str): transaction type, reference. Reference may be None
    """
    stem = address[: -(len(address_type) + 1)]
    if stem in base_txn_types:
        return stem, None
    else:
        for txn_type in base_txn_types:
            if stem.startswith(txn_type):
                return txn_type, stem[len(txn_type) + 1 :]

    # We should have found a matching txn_type by now, but return original stem if we failed to
    return stem, None


def _is_txn_type_in_interest_free_period(txn_types_in_interest_free_period, sub_type, ref):
    """
    Given the dictionary of transaction types/ refs that have an active interest free period,
    work out whether the supplied txn_type/ ref combo has an active interest free period

    :param txn_types_in_interest_free_period: Dict[str, Optional[List[str]]], transaction types
    and refs that have an active interest free period
    :param sub_type: str, transaction type
    :param ref: str or None, transaction reference
    :return: bool, True if the txn_type/ ref has an active interest free period, False otherwise
    """
    if not ref:
        return sub_type.lower() in txn_types_in_interest_free_period
    else:
        return ref in txn_types_in_interest_free_period.get(sub_type.lower(), [])


def _determine_txns_currently_interest_free(
    txn_types_in_interest_free_period, base_interest_rates, txn_base_interest_rates
):
    """
    Given the dictionary of transaction types/ refs that have an active interest free period,
    set the corresponding base interest rates to zero

    :param txn_types_in_interest_free_period: Dict[str, Optional[List[str]]], transaction types
    and refs that have an active interest free period
    :param base_interest_rates: Dict[str, str], base interest rates per transaction type that
    does not use transaction references
    :param txn_base_interest_rates: Dict[str, [Optional[Dict[str,str]]]], base interest rates per
    transaction reference, for transaction types that use transaction references
    :return: (str, str), updated base interest rates
    """
    for txn_type in set.intersection(
        set(base_interest_rates), set(txn_types_in_interest_free_period)
    ):
        base_interest_rates[txn_type] = "0.0"

    for txn_type in set.intersection(
        set(txn_base_interest_rates), set(txn_types_in_interest_free_period)
    ):
        for ref in set.intersection(
            set(txn_base_interest_rates[txn_type]),
            set(txn_types_in_interest_free_period[txn_type]),
        ):
            txn_base_interest_rates[txn_type][ref] = "0.0"

    return base_interest_rates, txn_base_interest_rates


def _set_accruals_by_sub_type(
    accruals_by_sub_type: dict[Tuple[str, str, str], dict[str, str]],
    charge_type: str,
    sub_type: str,
    ref: str,
    accrual_amount: Decimal,
    accrual_type: Optional[str] = None,
):
    """
    Construct accruals information based on charge_type, sub_type, accrual_type, ref
    and accrual_amount

    :param accruals_by_sub_type:  the dictionary that we add information to
    Examples:
    {(PRINCIPAL, 'balance_transfer', ''): {'REF1': 1.23, 'REF2': 4.56}}
    {(PRINCIPAL, 'purchase', 'PRE_SCOD'): {'': 7.89}}

    :param charge_type: either PRINCIPAL or FEE
    :param sub_type: the transaction type which doesn't contain a reference
    :param ref: the transaction reference if there is one
    :param accrual_amount: the amount to accrue
    :param accrual_type:  either '' or PRE_SCOD or POST_SCOD applicable for interest
    accrual to _UNCHARGED balances from txn day
    """

    # ref for transactions with reference or blank for transactions without reference
    ref_or_blank = ref or ""
    accrual_type_or_blank = accrual_type or ""

    accrual_address_data = (charge_type, sub_type, accrual_type_or_blank)

    accruals_by_sub_type.setdefault(accrual_address_data, {})
    accruals_by_sub_type[accrual_address_data].setdefault(ref_or_blank, Decimal("0.0"))
    accruals_by_sub_type[accrual_address_data][ref_or_blank] += accrual_amount


def _is_txn_interest_accrual_from_txn_day(vault, at_dt: Optional[datetime] = None) -> bool:
    """
    Returns current state of the accrue_interest_from_txn_day flag.

    :param vault:
    :param at_dt: the date time at which param needs to be returned, defaults
    to latest
    """
    accrue_interest_from_txn_day = _str_to_bool(
        _get_parameter(vault, name=ACCRUE_INTEREST_FROM_TXN_DAY, at=at_dt)
    )
    return accrue_interest_from_txn_day
