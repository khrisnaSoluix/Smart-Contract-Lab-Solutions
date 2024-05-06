# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from calendar import isleap
from collections import defaultdict
from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps
from typing import Callable, Optional, Union
from zoneinfo import ZoneInfo

# features
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AccountIdShape,
    AccountNotificationDirective,
    ActivationHookArguments,
    ActivationHookResult,
    AddressDetails,
    AuthorisationAdjustment,
    BalanceCoordinate,
    BalanceDefaultDict,
    BalancesIntervalFetcher,
    ClientTransaction,
    CustomInstruction,
    DeactivationHookArguments,
    DeactivationHookResult,
    DefinedDateTime,
    DenominationShape,
    EventTypesGroup,
    InboundAuthorisation,
    InboundHardSettlement,
    NumberShape,
    OptionalShape,
    OptionalValue,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Override,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Phase,
    Posting,
    PostingInstructionsDirective,
    PostingInstructionType,
    PostParameterChangeHookArguments,
    PostParameterChangeHookResult,
    PostPostingHookArguments,
    PostPostingHookResult,
    PrePostingHookArguments,
    PrePostingHookResult,
    Rejection,
    RejectionReason,
    RelativeDateTime,
    Release,
    ScheduledEvent,
    ScheduledEventHookArguments,
    ScheduledEventHookResult,
    ScheduleFailover,
    Settlement,
    Shift,
    SmartContractEventType,
    StringShape,
    TransactionCode,
    Transfer,
    Tside,
    UnionItemValue,
    UpdateAccountEventTypeDirective,
    fetch_account_data,
    requires,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

PostingInstruction = Union[
    AuthorisationAdjustment,
    CustomInstruction,
    InboundAuthorisation,
    InboundHardSettlement,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Release,
    Settlement,
    Transfer,
]

Postings = Union[
    AuthorisationAdjustment,
    InboundAuthorisation,
    InboundHardSettlement,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Posting,
    Release,
    Settlement,
    Transfer,
]

ParameterTypes = Union[
    datetime,
    Decimal,
    int,
    OptionalValue,
    str,
    UnionItemValue,
]

api = "4.0.0"
version = "5.0.0"
display_name = "Credit Card"
tside = Tside.ASSET
supported_denominations = ["GBP"]

# Transactions and charges can be in one of the following statuses
BILLED = "BILLED"
CHARGED = "CHARGED"
AUTH = "AUTH"
UNPAID = "UNPAID"
UNCHARGED = "UNCHARGED"
# account type
ACCOUNT_TYPE = "CREDIT_CARD"

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

REPAYMENT_HIERARCHY: list[dict[str, Union[str, list[str]]]] = [
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

# Instruction Detail keys
TXN_CODE = "transaction_code"
FEE_TYPE = "fee_type"

# Fetcher IDs
LIVE_BALANCES_BOF_ID = fetchers.LIVE_BALANCES_BOF_ID
ONE_SECOND_TO_MIDNIGHT_BIF_ID = "one_second_to_midnight_bif"
STATEMENT_CUTOFF_TO_LIVE_BALANCES_BIF_ID = "statement_cutoff_to_live_bif"

data_fetchers = [
    fetchers.LIVE_BALANCES_BOF,
    # For accrual purposes we use balances as of D-1T23:59:59.999999, which we can only get
    # using an interval from D-1T23:59:59 - DT00:00:00
    BalancesIntervalFetcher(
        fetcher_id=ONE_SECOND_TO_MIDNIGHT_BIF_ID,
        start=RelativeDateTime(
            origin=DefinedDateTime.EFFECTIVE_DATETIME,
            find=Override(hour=23, minute=59, second=59),
            shift=Shift(days=-1),
        ),
        end=RelativeDateTime(
            origin=DefinedDateTime.EFFECTIVE_DATETIME, find=Override(hour=0, minute=0, second=0)
        ),
    ),
    # For statement cut-off purposes we use balances from D-1T23:59:59.999999, which we can only get
    # using an interval from D-1T23:59:59 - DT00:00:00, up until live to handle postings after the
    # cut-off
    BalancesIntervalFetcher(
        fetcher_id=STATEMENT_CUTOFF_TO_LIVE_BALANCES_BIF_ID,
        start=RelativeDateTime(
            origin=DefinedDateTime.EFFECTIVE_DATETIME,
            find=Override(hour=23, minute=59, second=59),
            shift=Shift(days=-1),
        ),
        end=DefinedDateTime.LIVE,
    ),
]

# Parameters
PARAM_ACCOUNT_CLOSURE_FLAGS = "account_closure_flags"
PARAM_ACCOUNT_WRITE_OFF_FLAGS = "account_write_off_flags"
PARAM_ACCRUAL_BLOCKING_FLAGS = "accrual_blocking_flags"
PARAM_ACCRUE_INTEREST_FROM_TXN_DAY = "accrue_interest_from_txn_day"
PARAM_ACCRUE_INTEREST_ON_UNPAID_FEES = "accrue_interest_on_unpaid_fees"
PARAM_ACCRUE_INTEREST_ON_UNPAID_INTEREST = "accrue_interest_on_unpaid_interest"
ALLOWED_DAYS_AFTER_OPENING = "allowed_days_after_opening"
PARAM_ANNUAL_FEE_INTERNAL_ACCOUNT = "annual_fee_internal_account"
PARAM_ANNUAL_FEE = "annual_fee"
PARAM_APR = "annual_percentage_rate"
PARAM_BASE_INTEREST_RATES = "base_interest_rates"
PARAM_BILLED_TO_UNPAID_TRANSFER_BLOCKING_FLAGS = "billed_to_unpaid_transfer_blocking_flags"
PARAM_CREDIT_LIMIT = "credit_limit"
PARAM_DENOMINATION = "denomination"
DISPUTE_FEE_INTERNAL_ACCOUNTS = "dispute_fee_internal_accounts"
DISPUTE_FEE_PARAM = "dispute_fee"
PARAM_EXTERNAL_FEE_INTERNAL_ACCOUNTS = "external_fee_internal_accounts"
PARAM_EXTERNAL_FEE_TYPES = "external_fee_types"
PARAM_INTEREST_FREE_EXPIRY = "interest_free_expiry"
PARAM_INTEREST_ON_FEES_INTERNAL_ACCOUNT = "interest_on_fees_internal_account"
PARAM_INTEREST_WRITE_OFF_INTERNAL_ACCOUNT = "interest_write_off_internal_account"
PARAM_LATE_REPAYMENT_FEE_INTERNAL_ACCOUNT = "late_repayment_fee_internal_account"
PARAM_LATE_REPAYMENT_FEE = "late_repayment_fee"
PARAM_MAD = "minimum_amount_due"
PARAM_MAD_AS_STATEMENT_FLAGS = "mad_as_full_statement_flags"
PARAM_MAD_EQUAL_TO_ZERO_FLAGS = "mad_equal_to_zero_flags"
PARAM_MINIMUM_PERCENTAGE_DUE = "minimum_percentage_due"
PARAM_OVERDUE_AMOUNT_BLOCKING_FLAGS = "overdue_amount_blocking_flags"
PARAM_OVERLIMIT = "overlimit"
PARAM_OVERLIMIT_FEE_INTERNAL_ACCOUNT = "overlimit_fee_internal_account"
PARAM_OVERLIMIT_FEE = "overlimit_fee"
PARAM_OVERLIMIT_OPT_IN = "overlimit_opt_in"
PARAM_PAYMENT_DUE_PERIOD = "payment_due_period"
PARAM_PRINCIPAL_WRITE_OFF_INTERNAL_ACCOUNT = "principal_write_off_internal_account"
PARAM_TXN_APR = "transaction_annual_percentage_rate"
PARAM_TXN_BASE_INTEREST_RATES = "transaction_base_interest_rates"
PARAM_TXN_CODE_TO_TYPE_MAP = "transaction_code_to_type_map"
PARAM_TXN_INTEREST_FREE_EXPIRY = "transaction_interest_free_expiry"
PARAM_TXN_REFS = "transaction_references"
PARAM_TXN_TYPE_FEES = "transaction_type_fees"
PARAM_TXN_TYPE_FEES_INTERNAL_ACCOUNTS_MAP = "transaction_type_fees_internal_accounts_map"
PARAM_TXN_TYPE_INTEREST_INTERNAL_ACCOUNTS_MAP = "transaction_type_interest_internal_accounts_map"
PARAM_TXN_TYPE_LIMITS = "transaction_type_limits"
PARAM_TXN_TYPES = "transaction_types"

ACCRUAL_SCHEDULE_PREFIX = "accrual_schedule"
PARAM_ACCRUAL_SCHEDULE_HOUR = f"{ACCRUAL_SCHEDULE_PREFIX}_hour"
PARAM_ACCRUAL_SCHEDULE_MINUTE = f"{ACCRUAL_SCHEDULE_PREFIX}_minute"
PARAM_ACCRUAL_SCHEDULE_SECOND = f"{ACCRUAL_SCHEDULE_PREFIX}_second"
SCOD_SCHEDULE_PREFIX = "scod_schedule"
PARAM_SCOD_SCHEDULE_HOUR = f"{SCOD_SCHEDULE_PREFIX}_hour"
PARAM_SCOD_SCHEDULE_MINUTE = f"{SCOD_SCHEDULE_PREFIX}_minute"
PARAM_SCOD_SCHEDULE_SECOND = f"{SCOD_SCHEDULE_PREFIX}_second"
PDD_SCHEDULE_PREFIX = "pdd_schedule"
PARAM_PDD_SCHEDULE_HOUR = f"{PDD_SCHEDULE_PREFIX}_hour"
PARAM_PDD_SCHEDULE_MINUTE = f"{PDD_SCHEDULE_PREFIX}_minute"
PARAM_PDD_SCHEDULE_SECOND = f"{PDD_SCHEDULE_PREFIX}_second"
ANNUAL_FEE_SCHEDULE_PREFIX = "annual_fee_schedule"
PARAM_ANNUAL_FEE_SCHEDULE_HOUR = f"{ANNUAL_FEE_SCHEDULE_PREFIX}_hour"
PARAM_ANNUAL_FEE_SCHEDULE_MINUTE = f"{ANNUAL_FEE_SCHEDULE_PREFIX}_minute"
PARAM_ANNUAL_FEE_SCHEDULE_SECOND = f"{ANNUAL_FEE_SCHEDULE_PREFIX}_second"

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

MoneyShape = NumberShape(min_value=0, step=Decimal("0.01"))

parameters = [
    # Instance parameters
    Parameter(
        name=PARAM_OVERLIMIT,
        level=ParameterLevel.INSTANCE,
        description="Additional limit on top of credit limit available to spend. "
        "Might involve fees.",
        display_name="Additional Limit On Top Of Credit Limit",
        default_value=OptionalValue(Decimal(0)),
        shape=OptionalShape(shape=MoneyShape),
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_OVERLIMIT_OPT_IN,
        level=ParameterLevel.INSTANCE,
        description="Indicates whether the customer has opted in to the overlimit facility. If"
        ' "True" the customer can exceed the credit limit by the overlimit for regular'
        " transactions and stand-in/offline transactions. Otherwise, the customer can "
        "only exceed the credit limit for stand-in/offline transactions.",
        display_name="Overlimit Opt In",
        default_value=OptionalValue(common_parameters.BooleanValueFalse),
        shape=OptionalShape(shape=common_parameters.BooleanShape),
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_CREDIT_LIMIT,
        level=ParameterLevel.INSTANCE,
        description="Credit limit",
        display_name="Credit Limit",
        default_value=Decimal(0),
        shape=MoneyShape,
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_TXN_REFS,
        level=ParameterLevel.INSTANCE,
        description="Map of lists of Transaction types and their associated references "
        "(map format - encoded json).",
        display_name="Transaction References",
        shape=StringShape(),
        default_value=dumps({"balance_transfer": ["REF1", "REF2"]}),
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_TXN_TYPE_LIMITS,
        level=ParameterLevel.INSTANCE,
        description="Map of limits per transaction type (map format - encoded json). A "
        "transaction must respect overall limits and transaction type limits. "
        "For credit limit checks the sum of authorised and outstanding amounts for a "
        'given transaction type can be subject to an absolute limit, using the "flat" key, '
        'and/or a relative limit with respect to the credit limit, using the "percentage" key. '
        "If both are specified, the lowest of the two is applied. If either is "
        "missing it is assumed to not apply. If a transaction type has no entry, "
        'no specific limits apply. "allowed_days_after_opening" is a time-based check '
        "that permits transactions only in a window after the account is activated.",
        display_name="Limits Per Transaction Type",
        shape=StringShape(),
        default_value=dumps(
            {
                "cash_advance": {"flat": "250", "percentage": "0.01"},
                "balance_transfer": {"allowed_days_after_opening": "14"},
            }
        ),
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_TXN_TYPE_FEES,
        level=ParameterLevel.INSTANCE,
        description="Map of map of fees per transaction type (map format - encoded json). Allows a "
        '"over_deposit_only", "percentage_fee" and "flat_fee" to be specified'
        "for transactions of the given type. The highest fee will be selected based on "
        "the transaction amount and charged on the next statement. If a transaction "
        'type does not have an entry, no fees apply. If "over_deposit_only" is '
        "set to True, the associated type will only charge a fee if the transaction "
        "amount exceeds the deposit balance",
        display_name="Fees Per Transaction Type",
        shape=StringShape(),
        default_value=dumps(
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
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_TXN_APR,
        level=ParameterLevel.INSTANCE,
        description="Map of maps of Annual Percentage Rate per transaction ref "
        "(map format - encoded json)",
        display_name="Annual Percentage Rate Per Transaction Ref",
        shape=StringShape(),
        default_value=dumps({"balance_transfer": {"REF1": "0.02", "REF2": "0.03"}}),
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_TXN_BASE_INTEREST_RATES,
        level=ParameterLevel.INSTANCE,
        description="Map of maps of Per annum gross interest rate per transaction ref "
        "(map format - encoded json)",
        display_name="Per Annum Gross Interest Rate Per Transaction Ref",
        shape=StringShape(),
        default_value=dumps({"balance_transfer": {"REF1": "0.022", "REF2": "0.035"}}),
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_PAYMENT_DUE_PERIOD,
        level=ParameterLevel.INSTANCE,
        description="Number of days after SCOD that payment is due by. Minimum Amount Due must be "
        "paid back by then to avoid Late Repayment fees. Full outstanding balance must"
        " be paid back by then to avoid becoming revolver.",
        display_name="Payment Due Period",
        shape=NumberShape(
            min_value=21,
            max_value=27,
            step=1,
        ),
        default_value=Decimal(21),
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
    ),
    Parameter(
        name=PARAM_LATE_REPAYMENT_FEE,
        level=ParameterLevel.INSTANCE,
        description="Fee charged if the PARAM_MAD is not paid",
        display_name="Fee Charged If The Param_Mad Is Not Paid",
        shape=MoneyShape,
        default_value=Decimal(100),
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_ANNUAL_FEE,
        level=ParameterLevel.INSTANCE,
        description="Fee charged annually on the account anniversary",
        display_name="Annual Credit Card Fee",
        shape=MoneyShape,
        default_value=Decimal(100),
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_OVERLIMIT_FEE,
        level=ParameterLevel.INSTANCE,
        description="Fee charged on SCOD if outstanding principal exceeds the credit limit",
        display_name="Overlimit Fee",
        shape=MoneyShape,
        default_value=Decimal(100),
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_INTEREST_FREE_EXPIRY,
        description="List of interest free period expiry times associated with transaction types."
        "This is for transaction types that do not use transaction references",
        display_name="Interest Free Periods Per Transaction Type",
        shape=StringShape(),
        level=ParameterLevel.INSTANCE,
        default_value=dumps({"purchase": "", "cash_advance": "", "transfer": ""}),
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_TXN_INTEREST_FREE_EXPIRY,
        description="List of interest free period expiry times associated with transaction "
        "references.",
        display_name="Interest Free Periods Per Transaction Ref",
        shape=StringShape(),
        level=ParameterLevel.INSTANCE,
        default_value=dumps({"balance_transfer": {"REF1": "", "REF2": ""}}),
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    # Template parameters
    Parameter(
        name=PARAM_DENOMINATION,
        shape=DenominationShape(),
        level=ParameterLevel.TEMPLATE,
        description="Default denomination.",
        display_name="Default Denomination For The Contract.",
        default_value="GBP",
    ),
    Parameter(
        name=PARAM_TXN_CODE_TO_TYPE_MAP,
        level=ParameterLevel.TEMPLATE,
        description="Map of transaction codes to transaction types" " (map format - encoded json).",
        display_name="Map Of Transaction Types",
        shape=StringShape(),
        default_value=dumps(
            {
                "xxx": "purchase",
                "aaa": "cash_advance",
                "cc": "transfer",
                "bb": "balance_transfer",
            }
        ),
    ),
    Parameter(
        name=PARAM_TXN_TYPES,
        level=ParameterLevel.TEMPLATE,
        description="Map of maps of supported transaction types for the account, with any "
        "non-default parameters specified. All default to False. "
        "(map format - encoded json).",
        display_name="Account Supported Transaction Types",
        shape=StringShape(),
        default_value=dumps(
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
        name=PARAM_TXN_TYPE_FEES_INTERNAL_ACCOUNTS_MAP,
        display_name="Internal Accounts Used For Credit Card Transaction Type Fees",
        description="Map of transaction type to internal account id for transaction type fee"
        " purposes (map format - encoded json).",
        level=ParameterLevel.TEMPLATE,
        shape=StringShape(),
        default_value=dumps(
            {
                "cash_advance": "FEE_INCOME",
                "purchase": "FEE_INCOME",
                "transfer": "FEE_INCOME",
                "balance_transfer": "FEE_INCOME",
            }
        ),
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_TXN_TYPE_INTEREST_INTERNAL_ACCOUNTS_MAP,
        level=ParameterLevel.TEMPLATE,
        description="Map of transaction type to internal account id for interest purposes. Contains"
        "Interest Income account for each transaction type (map format - encoded json).",
        display_name="Internal Accounts Per Transaction Type",
        shape=StringShape(),
        default_value=dumps(
            {
                "cash_advance": "INTEREST_INCOME",
                "purchase": "INTEREST_INCOME",
                "transfer": "INTEREST_INCOME",
                "balance_transfer": "INTEREST_INCOME",
            }
        ),
    ),
    Parameter(
        name=PARAM_BASE_INTEREST_RATES,
        level=ParameterLevel.TEMPLATE,
        description="Per annum gross interest rate per transaction type "
        "(map format - encoded json)",
        display_name="Per Annum Gross Interest Rate Per Transaction Type",
        shape=StringShape(),
        default_value=dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0.02",
                "transfer": "0.03",
                "fees": "0.01",
            }
        ),
    ),
    Parameter(
        name=PARAM_ACCRUE_INTEREST_ON_UNPAID_INTEREST,
        description='Interest accrual on unpaid interest. If set to "False", interest will not be '
        "calculated and applied on unpaid interest.",
        display_name="Accrue Interest On Unpaid Interest",
        level=ParameterLevel.TEMPLATE,
        default_value=OptionalValue(common_parameters.BooleanValueFalse),
        shape=OptionalShape(shape=common_parameters.BooleanShape),
    ),
    Parameter(
        name=PARAM_ACCRUE_INTEREST_ON_UNPAID_FEES,
        description='Interest accrual on unpaid fees. If set to "False", interest will not be '
        "accrued on unpaid fees.",
        display_name="Accrue Interest On Unpaid Fees",
        level=ParameterLevel.TEMPLATE,
        default_value=OptionalValue(common_parameters.BooleanValueFalse),
        shape=OptionalShape(shape=common_parameters.BooleanShape),
    ),
    Parameter(
        name=PARAM_ACCRUE_INTEREST_FROM_TXN_DAY,
        level=ParameterLevel.TEMPLATE,
        description="For transactions that are not affected by specific interest behaviours "
        "(i.e. an active Interest Free Period or transaction types that always charge interest "
        "from the transaction date), determines the start point for interest accrual on "
        "transactions charged when entering Revolver status. For more information please refer "
        "to the product documentation.",
        display_name="Accrue Interest From Day Of Transaction",
        default_value=common_parameters.BooleanValueTrue,
        shape=common_parameters.BooleanShape,
    ),
    Parameter(
        name=PARAM_INTEREST_WRITE_OFF_INTERNAL_ACCOUNT,
        description="Internal account used to write-off any outstanding interest",
        display_name="Interest Write-Off Internal Account",
        level=ParameterLevel.TEMPLATE,
        shape=AccountIdShape(),
        default_value="INTEREST_WRITEOFF",
    ),
    Parameter(
        name=PARAM_PRINCIPAL_WRITE_OFF_INTERNAL_ACCOUNT,
        description="Internal account used to write-off any outstanding fees and transactions. "
        "The name follows the accounting definition of Principal",
        display_name="Principal Write-Off Internal Account",
        level=ParameterLevel.TEMPLATE,
        shape=AccountIdShape(),
        default_value="PRINCIPAL_WRITEOFF",
    ),
    Parameter(
        name=PARAM_INTEREST_ON_FEES_INTERNAL_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account id for interest on fees income.",
        display_name="Interest On Fees Internal Account",
        shape=StringShape(),
        default_value="FEES_INTEREST",
    ),
    Parameter(
        name=PARAM_APR,
        level=ParameterLevel.TEMPLATE,
        description="Annual Percentage Rate per transaction type (map format - encoded json)",
        display_name="Annual Percentage Rate Per Transaction Type",
        shape=StringShape(),
        default_value=dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0.02",
                "transfer": "0.03",
            }
        ),
    ),
    Parameter(
        name=PARAM_MAD,
        level=ParameterLevel.TEMPLATE,
        description="Minimum amount repayment due (higher value of minimum_amount_due or "
        "minimum_percentage_due used)",
        display_name="Minimum Amount Due",
        default_value=Decimal(0),
        shape=MoneyShape,
    ),
    Parameter(
        name=PARAM_MINIMUM_PERCENTAGE_DUE,
        level=ParameterLevel.TEMPLATE,
        description="Percentage of statement balance per transaction type used to calculate the "
        "minimum amount due (higher value of minimum_amount_due or "
        "minimum_percentage_due is used)",
        display_name="Percentage Of Statement Balance Per Transaction Type"
        " (map format - encoded json) ",
        default_value=dumps(
            {
                "purchase": "0.01",
                "cash_advance": "0.01",
                "transfer": "0.01",
                "balance_transfer": "0.01",
                "interest": "1.0",
                "fees": "1.0",
            }
        ),
        shape=StringShape(),
    ),
    Parameter(
        name=PARAM_LATE_REPAYMENT_FEE_INTERNAL_ACCOUNT,
        description="Income internal account for the late repayment fee",
        display_name="Credit Card Late Fee Income Account",
        level=ParameterLevel.TEMPLATE,
        shape=StringShape(),
        default_value="FEE_INCOME",
    ),
    Parameter(
        name=PARAM_ANNUAL_FEE_INTERNAL_ACCOUNT,
        description="Income internal account for the annual fee",
        display_name="Credit Card Annual Fee Income Account",
        level=ParameterLevel.TEMPLATE,
        shape=StringShape(),
        default_value="FEE_INCOME",
        update_permission=ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION,
    ),
    Parameter(
        name=PARAM_OVERLIMIT_FEE_INTERNAL_ACCOUNT,
        description="Income internal account for the overlimit fee",
        display_name="Credit Card Over Limit Fee Income Account",
        level=ParameterLevel.TEMPLATE,
        shape=StringShape(),
        default_value="FEE_INCOME",
    ),
    Parameter(
        name=PARAM_EXTERNAL_FEE_TYPES,
        description="External fees that can be initiated from outside the contract, but "
        "need to be stored in separate addresses. Stored as an encoded json list.",
        display_name="External Fee Types",
        level=ParameterLevel.TEMPLATE,
        shape=StringShape(),
        default_value=dumps(["dispute_fee", "withdrawal_fee"]),
    ),
    Parameter(
        name=PARAM_EXTERNAL_FEE_INTERNAL_ACCOUNTS,
        description="Income internal account for each external fee type. Stored as an "
        "encoded json map of fee type to json map of account type to account id. The "
        'account type is "income".',
        display_name="Credit Card Dispute Fee Account",
        level=ParameterLevel.TEMPLATE,
        shape=StringShape(),
        default_value=dumps(
            {
                "dispute_fee": "FEE_INCOME",
                "withdrawal_fee": "FEE_INCOME",
            }
        ),
    ),
    Parameter(
        name=PARAM_ACCRUAL_BLOCKING_FLAGS,
        description="List of flags applied to customer or account that prevent interest accrual",
        display_name="Accrual Blocking Flags",
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        default_value=dumps(["OVER_90_DPD"]),
    ),
    Parameter(
        name=PARAM_ACCOUNT_CLOSURE_FLAGS,
        description="List of flags applied to customer or account when account closure has been"
        "requested or imposed (i.e. customer or bank initiated)",
        display_name="Account Closure Flags",
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        default_value=dumps(["ACCOUNT_CLOSURE_REQUESTED"]),
    ),
    Parameter(
        name=PARAM_ACCOUNT_WRITE_OFF_FLAGS,
        description="List of flags applied to customer or account which, when applied will generate"
        "postings to zero out FULL_OUTSTANDING_BALANCE on request of account closure",
        display_name="Account Write Off Flags",
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        default_value=dumps(["MANUAL_WRITE_OFF", "OVER_150_DPD"]),
    ),
    Parameter(
        name=PARAM_BILLED_TO_UNPAID_TRANSFER_BLOCKING_FLAGS,
        description="List of flags applied to customer or account which, when applied will suspend "
        "the internal address transfers from billed to unpaid balances on PDD",
        display_name="Billed To Unpaid Transfer Blocking Flags",
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        default_value=dumps(["REPAYMENT_HOLIDAY"]),
    ),
    Parameter(
        name=PARAM_MAD_AS_STATEMENT_FLAGS,
        description="List of flags applied to customer or account which, when applied will set "
        "PARAM_MAD equal to statement balance",
        display_name="Param_Mad As Full Statement Flags",
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        default_value=dumps(["ACCOUNT_CLOSURE_REQUESTED", "OVER_90_DPD"]),
    ),
    Parameter(
        name=PARAM_MAD_EQUAL_TO_ZERO_FLAGS,
        description="List of flags applied to customer or account which, when applied will set "
        "PARAM_MAD to zero by the next SCOD/PDD event. In effect, the customer will not have to "
        "pay any PARAM_MAD for the statement periods where this is active, and no late repayment "
        "fees will be charged"
        'Note that this takes precedence over the "PARAM_MAD as Full Statement Flags" parameter.',
        display_name="Param_Mad Equal To Zero Flags",
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        default_value=dumps(["REPAYMENT_HOLIDAY"]),
    ),
    Parameter(
        name=PARAM_OVERDUE_AMOUNT_BLOCKING_FLAGS,
        description="List of flags applied to customer or account which, when applied will suspend "
        "the internal address updates on PDD that age the overdue balance buckets",
        display_name="Overdue Amount Blocking Flags",
        shape=StringShape(),
        level=ParameterLevel.TEMPLATE,
        default_value=dumps(["REPAYMENT_HOLIDAY"]),
    ),
    Parameter(
        name=PARAM_ACCRUAL_SCHEDULE_HOUR,
        description="The hour at which the ACCRUE_INTEREST schedule should execute for all "
        "CC accounts.",
        display_name="Accrual Schedule Execution Hour",
        shape=NumberShape(
            min_value=0,
            max_value=23,
            step=1,
        ),
        level=ParameterLevel.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=PARAM_ACCRUAL_SCHEDULE_MINUTE,
        description="The minute at which the ACCRUE_INTEREST schedule should execute for all "
        "CC accounts.",
        display_name="Accrual Schedule Execution Minute",
        shape=NumberShape(
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=ParameterLevel.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=PARAM_ACCRUAL_SCHEDULE_SECOND,
        description="The second at which the ACCRUE_INTEREST schedule should execute for all "
        "CC accounts.",
        display_name="Accrual Schedule Execution Second",
        shape=NumberShape(
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=ParameterLevel.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=PARAM_SCOD_SCHEDULE_HOUR,
        description="The hour at which the STATEMENT_CUT_OFF schedule should execute for all "
        "CC accounts.",
        display_name="Statement Cutoff Schedule Execution Hour",
        shape=NumberShape(
            min_value=0,
            max_value=23,
            step=1,
        ),
        level=ParameterLevel.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=PARAM_SCOD_SCHEDULE_MINUTE,
        description="The minute at which the STATEMENT_CUT_OFF schedule should execute for all "
        "CC accounts.",
        display_name="Statement Cutoff Schedule Execution Minute",
        shape=NumberShape(
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=ParameterLevel.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=PARAM_SCOD_SCHEDULE_SECOND,
        description="The second at which the STATEMENT_CUT_OFF schedule should execute for all "
        "CC accounts.",
        display_name="Statement Cutoff Schedule Execution Second",
        shape=NumberShape(
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=ParameterLevel.TEMPLATE,
        default_value=Decimal(2),
    ),
    Parameter(
        name=PARAM_PDD_SCHEDULE_HOUR,
        description="The hour at which the PAYMENT_DUE schedule should execute for all "
        "CC accounts.",
        display_name="Payment Due Schedule Execution Hour",
        shape=NumberShape(
            min_value=0,
            max_value=23,
            step=1,
        ),
        level=ParameterLevel.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=PARAM_PDD_SCHEDULE_MINUTE,
        description="The minute at which the PAYMENT_DUE schedule should execute for all "
        "CC accounts.",
        display_name="Payment Due Schedule Execution Minute",
        shape=NumberShape(
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=ParameterLevel.TEMPLATE,
        default_value=Decimal(0),
    ),
    Parameter(
        name=PARAM_PDD_SCHEDULE_SECOND,
        description="The second at which the PAYMENT_DUE schedule should execute for all "
        "CC accounts.",
        display_name="Payment Due Schedule Execution Second",
        shape=NumberShape(
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=ParameterLevel.TEMPLATE,
        default_value=Decimal(1),
    ),
    Parameter(
        name=PARAM_ANNUAL_FEE_SCHEDULE_HOUR,
        description="The hour at which the ANNUAL_FEE schedule should execute for all "
        "CC accounts.",
        display_name="Annual Fee Schedule Execution Hour",
        shape=NumberShape(
            min_value=0,
            max_value=23,
            step=1,
        ),
        level=ParameterLevel.TEMPLATE,
        default_value=Decimal(23),
    ),
    Parameter(
        name=PARAM_ANNUAL_FEE_SCHEDULE_MINUTE,
        description="The minute at which the ANNUAL_FEE schedule should execute for all "
        "CC accounts.",
        display_name="Annual Fee Schedule Execution Minute",
        shape=NumberShape(
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=ParameterLevel.TEMPLATE,
        default_value=Decimal(50),
    ),
    Parameter(
        name=PARAM_ANNUAL_FEE_SCHEDULE_SECOND,
        description="The second at which the ANNUAL_FEE schedule should execute for all "
        "CC accounts.",
        display_name="Annual Fee Schedule Execution Second",
        shape=NumberShape(
            min_value=0,
            max_value=59,
            step=1,
        ),
        level=ParameterLevel.TEMPLATE,
        default_value=Decimal(0),
    ),
]


# Events
EVENT_ACCRUE = "ACCRUE_INTEREST"
EVENT_SCOD = "STATEMENT_CUT_OFF"
EVENT_ANNUAL_FEE = "ANNUAL_FEE"
EVENT_PDD = "PAYMENT_DUE"

event_types = [
    SmartContractEventType(
        name=EVENT_ACCRUE, scheduler_tag_ids=["CREDIT_CARD_ACCRUE_INTEREST_AST"]
    ),
    SmartContractEventType(
        name=EVENT_SCOD, scheduler_tag_ids=["CREDIT_CARD_STATEMENT_CUT_OFF_AST"]
    ),
    SmartContractEventType(name=EVENT_ANNUAL_FEE, scheduler_tag_ids=["CREDIT_CARD_ANNUAL_FEE_AST"]),
    SmartContractEventType(name=EVENT_PDD, scheduler_tag_ids=["CREDIT_CARD_PAYMENT_DUE_AST"]),
]

event_types_groups = [
    EventTypesGroup(name="GROUP_INTEREST", event_types_order=[EVENT_ACCRUE, EVENT_PDD, EVENT_SCOD])
]

# Notification types
PUBLISH_STATEMENT_DATA_NOTIFICATION = "PUBLISH_STATEMENT_DATA_NOTIFICATION"
EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION = "EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION"

notification_types = [
    PUBLISH_STATEMENT_DATA_NOTIFICATION,
    EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION,
]


@requires(parameters=True)
def activation_hook(
    vault: SmartContractVault, hook_arguments: ActivationHookArguments
) -> Optional[ActivationHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    scheduled_events: dict[str, ScheduledEvent] = {}

    account_creation_dt = vault.get_account_creation_datetime()
    payment_due_period = int(utils.get_parameter(vault, name=PARAM_PAYMENT_DUE_PERIOD))
    # We include transactions on SCOD and PDD day itself, so schedules run at the end of the day
    scod_start, scod_end = _get_first_scod(account_creation_dt)
    _, pdd_end = _get_first_pdd(payment_due_period, scod_start)

    # Accrual scheduled before PDD/SCOD to ensure they account for latest accrual
    scheduled_events[EVENT_ACCRUE] = ScheduledEvent(
        start_datetime=effective_datetime,
        expression=utils.get_schedule_expression_from_parameters(vault, ACCRUAL_SCHEDULE_PREFIX),
    )
    scheduled_events[EVENT_SCOD] = ScheduledEvent(
        start_datetime=effective_datetime,
        expression=utils.get_schedule_expression_from_parameters(
            vault, SCOD_SCHEDULE_PREFIX, day=scod_end.day, month=scod_end.month
        ),
    )
    # We need to charge annual fee on account opening day every year
    scheduled_events[EVENT_ANNUAL_FEE] = ScheduledEvent(
        start_datetime=effective_datetime,
        expression=utils.get_schedule_expression_from_parameters(vault, ANNUAL_FEE_SCHEDULE_PREFIX),
    )
    scheduled_events[EVENT_PDD] = ScheduledEvent(
        start_datetime=pdd_end,
        schedule_method=utils.get_end_of_month_schedule_from_parameters(
            vault, PDD_SCHEDULE_PREFIX, ScheduleFailover.FIRST_VALID_DAY_BEFORE, day=pdd_end.day
        ),
    )

    ##TODO: enable this once we finish CPP to add rejection to activation_hook
    # _check_txn_type_parameter_configuration(vault, effective_datetime)

    # Set AVAILABLE_BALANCE to credit_limit upon account creation
    credit_limit = utils.get_parameter(name=PARAM_CREDIT_LIMIT, vault=vault)
    denomination = utils.get_parameter(name=PARAM_DENOMINATION, vault=vault)

    posting_instructions_directives: list[PostingInstructionsDirective] = []
    if credit_limit > Decimal(0):
        posting_instructions_directives = [
            PostingInstructionsDirective(
                posting_instructions=_make_internal_address_transfer(
                    vault,
                    credit_limit,
                    denomination,
                    credit_internal=True,
                    custom_address=AVAILABLE_BALANCE,
                ),
                value_datetime=effective_datetime,
            )
        ]

    return ActivationHookResult(
        scheduled_events_return_value=scheduled_events,
        posting_instructions_directives=posting_instructions_directives,
    )


@requires(
    event_type="ACCRUE_INTEREST",
    parameters=True,
    flags=True,
    last_execution_datetime=["STATEMENT_CUT_OFF"],
)
@fetch_account_data(event_type="ACCRUE_INTEREST", balances=[ONE_SECOND_TO_MIDNIGHT_BIF_ID])
@requires(
    event_type="STATEMENT_CUT_OFF",
    flags=True,
    parameters=True,
    last_execution_datetime=["STATEMENT_CUT_OFF", "PAYMENT_DUE"],
)
@fetch_account_data(
    event_type="STATEMENT_CUT_OFF", balances=[STATEMENT_CUTOFF_TO_LIVE_BALANCES_BIF_ID]
)
@requires(event_type="ANNUAL_FEE", parameters=True)
@fetch_account_data(event_type="ANNUAL_FEE", balances=[LIVE_BALANCES_BOF_ID])
@requires(event_type="PAYMENT_DUE", parameters=True, flags=True)
@fetch_account_data(event_type="PAYMENT_DUE", balances=[LIVE_BALANCES_BOF_ID])
def scheduled_event_hook(
    vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments
) -> Optional[ScheduledEventHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    event_type = hook_arguments.event_type
    pi_directives: list[PostingInstructionsDirective] = []
    update_event_types_directives: list[UpdateAccountEventTypeDirective] = []
    notification_directives: list[AccountNotificationDirective] = []

    if event_type == EVENT_ACCRUE:
        pi_directives.extend(_process_interest_accrual_and_charging(vault, effective_datetime))

    elif event_type == EVENT_SCOD:
        scod_notif_dir, scod_pi_dir = _process_statement_cut_off(vault, effective_datetime)
        pi_directives.extend(scod_pi_dir)
        notification_directives.extend(scod_notif_dir)

    elif event_type == EVENT_ANNUAL_FEE:
        pi_directives.extend(_charge_annual_fee(vault, effective_datetime))

        account_creation_dt = vault.get_account_creation_datetime()
        annual_fee_day = (
            "last"
            if (account_creation_dt.month == 2 and account_creation_dt.day == 29)
            else account_creation_dt.day
        )
        annual_fee_schedule_expression = utils.get_schedule_expression_from_parameters(
            vault,
            ANNUAL_FEE_SCHEDULE_PREFIX,
            day=str(annual_fee_day),
            month=str(account_creation_dt.month),
            # Explicitly declare next year to prevent infinity loop
            year=str(effective_datetime.year + 1),
        )

        update_event_types_directives.append(
            UpdateAccountEventTypeDirective(
                event_type=EVENT_ANNUAL_FEE, expression=annual_fee_schedule_expression
            )
        )

    elif event_type == EVENT_PDD:
        pdd_pi_dir, pdd_notif_dir = _process_payment_due_date(vault, effective_datetime)
        pi_directives.extend(pdd_pi_dir)
        notification_directives.extend(pdd_notif_dir)

        account_creation_dt = vault.get_account_creation_datetime()
        payment_due_period = int(
            utils.get_parameter(
                name=PARAM_PAYMENT_DUE_PERIOD, at_datetime=account_creation_dt, vault=vault
            )
        )
        local_next_pdd_start, local_next_pdd_end = _get_next_pdd(
            payment_due_period,
            account_creation_dt,
            last_pdd_execution_datetime=effective_datetime,
        )
        _, local_next_scod_end = _get_scod_for_pdd(payment_due_period, local_next_pdd_start)

        scod_schedule_expression = utils.get_schedule_expression_from_parameters(
            vault,
            SCOD_SCHEDULE_PREFIX,
            day=str(local_next_scod_end.day),
            month=str(local_next_scod_end.month),
        )
        update_event_types_directives.append(
            UpdateAccountEventTypeDirective(
                event_type=EVENT_SCOD, expression=scod_schedule_expression
            )
        )

    return ScheduledEventHookResult(
        posting_instructions_directives=pi_directives,
        update_account_event_type_directives=update_event_types_directives,
        account_notification_directives=notification_directives,
    )


@requires(parameters=True)
@fetch_account_data(balances=[LIVE_BALANCES_BOF_ID])
def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    effective_datetime: datetime = hook_arguments.effective_datetime
    posting_instructions: list[PostingInstruction] = hook_arguments.posting_instructions
    denomination: str = utils.get_parameter(name=PARAM_DENOMINATION, vault=vault)

    if denomination_rejection := utils.validate_denomination(
        posting_instructions=posting_instructions, accepted_denominations=[denomination]
    ):
        return PrePostingHookResult(rejection=denomination_rejection)

    live_balances = vault.get_balances_observation(fetcher_id=LIVE_BALANCES_BOF_ID).balances
    supported_txn_types = _get_supported_txn_types(vault)
    txn_code_to_type_map = utils.get_parameter(
        name=PARAM_TXN_CODE_TO_TYPE_MAP, at_datetime=effective_datetime, is_json=True, vault=vault
    )

    txn_type_validation_rejection = _validate_txn_type_and_refs(
        vault,
        live_balances,
        posting_instructions,
        supported_txn_types,
        txn_code_to_type_map,
        effective_datetime,
    )

    if txn_type_validation_rejection:
        return PrePostingHookResult(
            rejection=txn_type_validation_rejection,
        )

    # Not relevant in realistic bank testing, all postings are non-advice
    non_advice_postings = _get_non_advice_postings(posting_instructions)

    insufficient_fund_rejections = _check_account_has_sufficient_funds(
        vault, live_balances, denomination, non_advice_postings
    )
    if insufficient_fund_rejections:
        return PrePostingHookResult(
            rejection=insufficient_fund_rejections,
        )
    txn_type_credit_limit_rejections = _check_txn_type_credit_limits(
        vault,
        live_balances,
        non_advice_postings,
        denomination,
        effective_datetime,
        txn_code_to_type_map,
    )

    if txn_type_credit_limit_rejections:
        return PrePostingHookResult(
            rejection=txn_type_credit_limit_rejections,
        )
    txn_type_time_limit_rejections = _check_txn_type_time_limits(
        vault, non_advice_postings, effective_datetime
    )

    if txn_type_time_limit_rejections:
        return PrePostingHookResult(
            rejection=txn_type_time_limit_rejections,
        )
    return None


@requires(parameters=True)
def post_parameter_change_hook(
    vault: SmartContractVault, hook_arguments: PostParameterChangeHookArguments
) -> Optional[PostParameterChangeHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    old_parameter_values = hook_arguments.old_parameter_values
    updated_parameter_values = hook_arguments.updated_parameter_values
    credit_limit_change_posting_instructions = _handle_credit_limit_change(
        vault, old_parameter_values, updated_parameter_values
    )

    if credit_limit_change_posting_instructions:
        return PostParameterChangeHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=credit_limit_change_posting_instructions,
                    value_datetime=effective_datetime,
                )
            ]
        )
    return None


@requires(parameters=True)
@fetch_account_data(balances=[LIVE_BALANCES_BOF_ID])
def post_posting_hook(
    vault: SmartContractVault, hook_arguments: PostPostingHookArguments
) -> Optional[PostPostingHookResult]:
    denomination = utils.get_parameter(name=PARAM_DENOMINATION, vault=vault)
    credit_limit = utils.get_parameter(name=PARAM_CREDIT_LIMIT, vault=vault)

    effective_datetime = hook_arguments.effective_datetime
    posting_instructions = hook_arguments.posting_instructions
    client_transactions = hook_arguments.client_transactions

    live_balances = vault.get_balances_observation(fetcher_id=LIVE_BALANCES_BOF_ID).balances
    # Is deep copy still needed?
    in_flight_balances = _deep_copy_balances(live_balances)

    new_posting_instructions: list[CustomInstruction] = []

    new_posting_instructions.extend(
        _rebalance_postings(
            vault,
            denomination,
            posting_instructions,
            client_transactions,
            in_flight_balances,
            effective_datetime,
        )
    )

    new_posting_instructions.extend(
        _charge_txn_type_fees(
            vault,
            posting_instructions,
            live_balances,
            in_flight_balances,
            denomination,
            effective_datetime,
        )
    )

    new_posting_instructions.extend(
        _adjust_aggregate_balances(
            vault,
            denomination,
            in_flight_balances,
            effective_datetime=effective_datetime,
            credit_limit=credit_limit,
        )
    )

    if len(new_posting_instructions) > 0:
        return PostPostingHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=new_posting_instructions, value_datetime=effective_datetime
                )
            ]
        )
    return None


# Although Statement generation relies on STATEMENT_CUTOFF_TO_LIVE_BALANCES_BIF_ID by default,
# for closure we don't need to account for balance inconsistencies and override to live
@fetch_account_data(balances=[LIVE_BALANCES_BOF_ID])
@requires(parameters=True, flags=True, last_execution_datetime=["STATEMENT_CUT_OFF"])
def deactivation_hook(
    vault: SmartContractVault, hook_arguments: DeactivationHookArguments
) -> Optional[DeactivationHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    in_flight_balances = _deep_copy_balances(
        vault.get_balances_observation(fetcher_id=LIVE_BALANCES_BOF_ID).balances
    )
    txn_types = _get_supported_txn_types(vault, effective_datetime)
    # Make sure the _INTEREST_FREE_PERIOD_INTEREST_UNCHARGED addresses get zeroed out as well
    for txn_type in set(txn_types):
        txn_types[f"{txn_type}_{INTEREST_FREE_PERIOD}"] = txn_types[txn_type]
    denomination: str = utils.get_parameter(name=PARAM_DENOMINATION, vault=vault)

    account_closure_flags_applied = utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_ACCOUNT_CLOSURE_FLAGS,
        effective_datetime=effective_datetime,
    )
    write_off_flags_applied = utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_ACCOUNT_WRITE_OFF_FLAGS,
        effective_datetime=effective_datetime,
    )

    if rejection := _can_final_statement_be_generated(
        in_flight_balances,
        account_closure_flags_applied,
        write_off_flags_applied,
        denomination,
    ):
        return DeactivationHookResult(rejection=rejection)

    write_off_instructions = []
    if write_off_flags_applied:
        write_off_instructions.extend(
            _process_write_off(vault, denomination, in_flight_balances, effective_datetime)
        )

    notification_directives, posting_directives = _process_statement_cut_off(
        vault, effective_datetime, in_flight_balances, is_final=True
    )

    zero_out_instructions = _zero_out_balances_for_account_closure(
        vault, effective_datetime, in_flight_balances, txn_types
    )
    if posting_instructions := write_off_instructions + zero_out_instructions:
        posting_directives.append(
            PostingInstructionsDirective(
                posting_instructions=posting_instructions,
                value_datetime=effective_datetime,
                client_batch_id=f"CLOSE_ACCOUNT-{vault.get_hook_execution_id()}",
            )
        )

    return DeactivationHookResult(
        account_notification_directives=notification_directives,
        posting_instructions_directives=posting_directives,
    )


#  Helper functions
def _zero_out_balances_for_account_closure(
    vault: SmartContractVault,
    effective_datetime: datetime,
    in_flight_balances: BalanceDefaultDict,
    txn_types: dict[str, Optional[list[str]]],
) -> list[CustomInstruction]:
    """
    Create postings to zero out remaining balances that aren't written off or paid-back when an
    account is being closed or written off. All balances other than
    - AVAILABLE_BALANCE,
    - <transaction_type>_INTEREST_UNCHARGED,
    - <transaction_type>_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED
    - INTERNAL
    must be 0 as the full outstanding balance has either been paid off or written off

    :param vault: Vault object for the account
    :param effective_datetime: Datetime of the account closure request
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :return: List of CustomInstructions that zero out remaining balances
    """

    denomination = utils.get_parameter(
        name=PARAM_DENOMINATION, at_datetime=effective_datetime, vault=vault
    )
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

    # close_code can be re-run, so override ensures we don't re-zero-out in case
    available_balance_instructions = _override_info_balance(
        vault=vault,
        in_flight_balances=in_flight_balances,
        balance_address=AVAILABLE_BALANCE,
        amount=Decimal(0),
        denomination=denomination,
    )

    return accrued_interest_instructions + available_balance_instructions


def _process_write_off(
    vault: SmartContractVault,
    denomination: str,
    in_flight_balances: BalanceDefaultDict,
    effective_datetime: datetime,
) -> list[CustomInstruction]:
    """
    Calculate accounting principal (principal + fees) and interest write-off amounts and create
    postings to transfer them from write-off accounts to the credit account

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param effective_datetime: Datetime when the write-off is being processed
    :return: List of CustomInstructions to process write-off
    """

    write_off_instructions: list[CustomInstruction] = []
    repayment_instructions = []

    txn_types = _get_supported_txn_types(vault, effective_datetime)
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

    principal_write_off_account = utils.get_parameter(
        vault, name=PARAM_PRINCIPAL_WRITE_OFF_INTERNAL_ACCOUNT
    )
    interest_write_off_account = utils.get_parameter(
        vault, name=PARAM_INTEREST_WRITE_OFF_INTERNAL_ACCOUNT
    )

    credit_limit = utils.get_parameter(
        name=PARAM_CREDIT_LIMIT, at_datetime=effective_datetime, vault=vault
    )
    instruction_details = _gl_posting_metadata("LOAN_CHARGE_OFF", vault.account_id)

    write_off_instructions.extend(
        _create_custom_instructions(
            vault,
            amount=abs(finance_principal),
            denomination=denomination,
            debit_account_id=principal_write_off_account,
            credit_account_id=vault.account_id,
            instruction_details=instruction_details,
        )
    )

    write_off_instructions.extend(
        _create_custom_instructions(
            vault,
            amount=abs(interest),
            denomination=denomination,
            debit_account_id=interest_write_off_account,
            credit_account_id=vault.account_id,
            instruction_details=instruction_details,
        )
    )

    for posting in write_off_instructions:
        # _create_custom_instructions will return postings for internal account and customer account
        if posting.balances(vault.account_id, vault.tside):
            postings, _ = _process_repayment(
                vault,
                denomination,
                posting,
                in_flight_balances,
                effective_datetime,
                account_id=vault.account_id,
            )
            repayment_instructions.extend(postings)

    adjustment_posting_instructions = _adjust_aggregate_balances(
        vault,
        denomination,
        in_flight_balances,
        effective_datetime,
        credit_limit=credit_limit,
    )

    return write_off_instructions + repayment_instructions + adjustment_posting_instructions


def _can_final_statement_be_generated(
    balances: BalanceDefaultDict,
    are_closure_flags_applied: bool,
    are_write_off_flags_applied: bool,
    denomination: str,
) -> Optional[Rejection]:
    """
    Determines whether the final statement can safely be generated by checking that:
    - a closure or write-off flag has been applied
    - full outstanding balance is 0
    - there are no open authorisations

    :param balances: balances at the time the closure request is made
    :param are_closure_flags_applied: True if any of the flags in the
    PARAM_ACCOUNT_CLOSURE_FLAGS parameter are applied to the account/customer, else False
    :param are_write_off_flags_applied: True if any of the flags in the
    PARAM_ACCOUNT_WRITE_OFF_FLAGS parameter are applied to the account/customer, else False
    :param denomination: Denomination of the account
    :return: Rejection if the final statement cannot be generated, else None
    """

    if not are_closure_flags_applied and not are_write_off_flags_applied:
        return Rejection(
            message="No account closure or write-off flags on the account",
            reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
        )

    # write-off account will by definition have non-zero outstanding balance
    if not are_write_off_flags_applied:
        full_outstanding_balance = utils.balance_at_coordinates(
            balances=balances, address=FULL_OUTSTANDING_BALANCE, denomination=denomination
        )
        if full_outstanding_balance != Decimal(0):
            return Rejection(
                message="Full Outstanding Balance is not zero",
                reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
            )

        auth_balances = sum(
            [
                balance.net
                for (address, _, _, _), balance in balances.items()
                if address.endswith(AUTH)
            ]
        )
        if auth_balances != Decimal(0):
            return Rejection(
                message="Outstanding authorisations on the account",
                reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
            )
    return None


def _validate_txn_type_and_refs(
    vault: SmartContractVault,
    balances: BalanceDefaultDict,
    posting_instructions: list[PostingInstruction],
    supported_txn_types: dict[str, Optional[list[str]]],
    txn_code_to_type_map: dict[str, str],
    effective_datetime: datetime,
) -> Optional[Rejection]:
    """
    Check whether posting contains a transaction level reference if one is required. If so, ensure
    that it is present in the account parameter timeseries. Additionally, check reference is unique
    and has not been used previously, by checking posting metadata against existing
    _CHARGED balance addresses.

    :param vault: Vault object for the account
    :param balances: Current balances of account
    :param posting_instructions: Posting instructions that need to be validated
    :param supported_txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :param txn_code_to_type_map: Map of transaction codes to transaction types
    :param effective_datetime: datetime when the postings are being processed
    :return: Rejection if the transaction type is invalid, else None
    """
    txn_types_with_refs = {
        txn_type.upper(): attributes
        for txn_type, attributes in supported_txn_types.items()
        if attributes is not None
    }

    for posting_instruction in posting_instructions:
        # if posting is of type credit, no validation assumed
        if posting_instruction.type in [
            PostingInstructionType.INBOUND_AUTHORISATION,
            PostingInstructionType.INBOUND_HARD_SETTLEMENT,
        ]:
            continue

        txn_type, txn_ref = _get_txn_type_and_ref_from_posting(
            vault,
            posting_instruction.instruction_details,
            effective_datetime,
            supported_txn_types=supported_txn_types,
            txn_code_to_type_map=txn_code_to_type_map,
        )

        # Check reference exists first, if a non-ref transaction type we can skip the other checks.
        if not txn_ref:
            if txn_type.upper() in txn_types_with_refs:
                return Rejection(
                    message=f"Transaction type {txn_type} requires a transaction level reference "
                    "and none has been specified.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
            else:
                continue

        elif txn_ref not in txn_types_with_refs.get(txn_type.upper(), [""]):
            return Rejection(
                message=f"{txn_ref} undefined in parameters for {txn_type}. "
                "Please update parameters.",
                reason_code=RejectionReason.AGAINST_TNC,
            )

        for dimensions in balances.keys():
            if dimensions[0] == _principal_address(txn_type, CHARGED, txn_ref=txn_ref):
                return Rejection(
                    message=f"{txn_ref} already in use for {txn_type}. "
                    "Please select a unique reference.",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
    return None


def _check_account_has_sufficient_funds(
    vault: SmartContractVault,
    balances: BalanceDefaultDict,
    denomination: str,
    posting_instructions: list[PostingInstruction],
) -> Optional[Rejection]:
    """
    Checks whether the account has sufficient funds for the proposed postings by
    considering the account's current usage of credit limit and overlimit (if opted in)

    :param vault: Vault object for the account
    :param balances: The account balances used to validate the postings
    :param denomination: Denomination of the account
    :param posting_instructions: The posting instructions being validated
    :return: Rejection if the account has insufficient funds, else None
    """

    postings_balances = BalanceDefaultDict()
    _update_balances(vault.account_id, postings_balances, posting_instructions)

    # Set credit limit param to 0 and txn_type to [] to isolate the postings delta
    available_balance_delta = _get_available_balance(
        Decimal("0"), postings_balances, {}, denomination
    )

    if available_balance_delta >= 0:
        # Account balance is increasing so we don't need to check the available funds
        return None

    txn_types = _get_supported_txn_types(vault, None)
    credit_limit = utils.get_parameter(name=PARAM_CREDIT_LIMIT, vault=vault)
    available_balance = _get_available_balance(credit_limit, balances, txn_types, denomination)
    overlimit_amount = _get_overlimit_amount(balances, credit_limit, denomination, txn_types)

    # Once customer is overlimit due to principal spend, they cannot transact further
    if overlimit_amount > 0:
        return Rejection(
            message=f"Insufficient funds for {denomination} {-available_balance_delta} transaction."
            f" Overlimit already in use",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )

    # Inbound/Outbound Auth Settlements do not go through pre_posting_code so it is possible
    # to over settle past overlimit regardless of opt-in
    opt_in = utils.get_parameter(
        vault,
        name=PARAM_OVERLIMIT_OPT_IN,
        is_optional=True,
        is_boolean=True,
        default_value="False",
    )
    if opt_in:
        overlimit = utils.get_parameter(
            vault, name=PARAM_OVERLIMIT, is_optional=True, default_value=Decimal(0)
        )
        available_balance += overlimit

    if available_balance + available_balance_delta < 0:
        return Rejection(
            message=f"Insufficient funds {denomination} {available_balance} for "
            f"{denomination} {-available_balance_delta} transaction (excl advice instructions)",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
    return None


def _check_txn_type_time_limits(
    vault: SmartContractVault,
    posting_instructions: list[PostingInstruction],
    effective_datetime: datetime,
) -> Optional[Rejection]:
    """
    Rejects any postings that are outside of a time window,
    e.g. within a certain number of days after account opening

    :param vault: Vault object for the account
    :param posting_instructions: The posting instructions to check against transaction time limits
    :param effective_datetime: datetime of when the postings are being processed as-of
    :return: Rejection if any transaction time limit is breached by a posting instruction, else None
    """

    txn_type_limits: dict[str, dict[str, str]] = utils.get_parameter(
        name=PARAM_TXN_TYPE_LIMITS, at_datetime=effective_datetime, is_json=True, vault=vault
    )

    time_limit_keys = {ALLOWED_DAYS_AFTER_OPENING}

    # find the types that have time-related keys in txn_type_limits
    txn_types_with_time_limits = [
        txn_type
        for txn_type, limits in txn_type_limits.items()
        if set(limits.keys()) & time_limit_keys
    ]
    if txn_types_with_time_limits == []:
        return None

    txn_code_to_type_map = utils.get_parameter(
        name=PARAM_TXN_CODE_TO_TYPE_MAP, at_datetime=effective_datetime, is_json=True, vault=vault
    )

    # Find postings that match the ones that have time limit(s)
    for instruction in posting_instructions:
        this_txn_type, _ = _get_txn_type_and_ref_from_posting(
            vault,
            instruction.instruction_details,
            effective_datetime,
            txn_code_to_type_map=txn_code_to_type_map,
        )
        if this_txn_type not in txn_types_with_time_limits:
            continue
        limits = txn_type_limits.get(this_txn_type, {})
        allowed_days_after = limits.get(ALLOWED_DAYS_AFTER_OPENING)

        if allowed_days_after is not None:
            # The cutoff works from creation time-of-day to current time-of-day,
            end_of_allowed_period = vault.get_account_creation_datetime() + relativedelta(
                days=int(allowed_days_after)
            )
            if effective_datetime >= end_of_allowed_period:
                return Rejection(
                    message="Transaction not permitted outside of configured window "
                    f"{allowed_days_after} days from account opening",
                    reason_code=RejectionReason.AGAINST_TNC,
                )
    return None


def _handle_credit_limit_change(
    vault: SmartContractVault,
    old_parameter_values: dict[str, ParameterTypes],
    updated_parameter_values: dict[str, ParameterTypes],
) -> list[CustomInstruction]:
    """
    Determine if credit limit has been updated and created postings to update address balance
    and GL accordingly.

    :param vault: Vault object for the account
    :param old_parameter_values: Map of parameter name to old parameter value
    :param updated_parameter_values: Map of parameter name to new parameter value
    :return: List of CustomInstructions to update the credit limit
    """

    if not utils.has_parameter_value_changed(
        parameter_name=PARAM_CREDIT_LIMIT,
        old_parameters=old_parameter_values,
        updated_parameters=updated_parameter_values,
    ):
        return []

    new_credit_limit: Decimal = updated_parameter_values[PARAM_CREDIT_LIMIT]  # type: ignore
    old_credit_limit: Decimal = old_parameter_values[PARAM_CREDIT_LIMIT]  # type: ignore
    denomination = utils.get_parameter(name=PARAM_DENOMINATION, vault=vault)

    amount = abs(new_credit_limit - old_credit_limit)
    # For a credit limit increase, to make the credit limit address more
    # positive, we debit it, because it's an asset tside. So we credit the internal
    credit_internal = new_credit_limit > old_credit_limit

    return _make_internal_address_transfer(
        amount=amount,
        credit_internal=credit_internal,
        custom_address=AVAILABLE_BALANCE,
        vault=vault,
        denomination=denomination,
    )


def _get_available_balance(
    credit_limit: Decimal,
    balances: BalanceDefaultDict,
    txn_types: dict[str, Optional[list[str]]],
    denomination: str,
) -> Decimal:
    """
    Determine the available balance for the account, taking into account postings that haven't yet
    been rebalanced.

    :param credit_limit: Credit limit for the account
    :param balances: Account balances to use to calculate the available balance
    :param txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :param denomination: Denomination of the account
    :return: The available balance
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


def _rebalance_postings(
    vault: SmartContractVault,
    denomination: str,
    posting_instructions: list[PostingInstruction],
    client_transactions: dict[str, ClientTransaction],
    in_flight_balances: BalanceDefaultDict,
    effective_datetime: datetime,
) -> list[CustomInstruction]:
    """
    Takes posting instructions from post-posting hook and creates CustomInstructions to rebalance
    account addresses based on the instruction type, amount and current balances.

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param posting_instructions: The posting instructions to rebalance
    :param client_transactions: The client transactions affected by the posting instructions being
    processed
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param effective_datetime: Datetime as of which the posting instructions are being rebalanced
    :return: List of CustomInstructions to rebalance the processed posting instructions
    """
    new_posting_instructions = []
    for posting_instruction in posting_instructions:
        posting_instruction_balance = posting_instruction.balances()
        posting_instruction_committed_balance = posting_instruction_balance[
            BalanceCoordinate(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
        ].net
        posting_instruction_pending_out_balance = posting_instruction_balance[
            BalanceCoordinate(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)
        ].net

        # PostingInstruction.unique_client_transaction_id is typed as Optional but will always be
        # populated on committed PIs
        client_transaction = client_transactions[
            posting_instruction.unique_client_transaction_id  # type: ignore
        ]

        if posting_instruction.type in (
            PostingInstructionType.SETTLEMENT,
            PostingInstructionType.OUTBOUND_HARD_SETTLEMENT,
            PostingInstructionType.INBOUND_HARD_SETTLEMENT,
            PostingInstructionType.TRANSFER,
        ):
            # Check for PIs that credit account committed balance.
            if posting_instruction_committed_balance < Decimal(0):
                repayment_posting_instructions, in_flight_balances = _process_repayment(
                    vault,
                    denomination,
                    posting_instruction,
                    in_flight_balances,
                    effective_datetime,
                    client_transaction,
                )
                new_posting_instructions.extend(repayment_posting_instructions)
            # Check for PIs that debit account committed balance
            else:
                new_posting_instructions.extend(
                    _rebalance_outbound_settlement(
                        vault=vault,
                        client_transaction=client_transaction,
                        in_flight_balances=in_flight_balances,
                        effective_datetime=effective_datetime,
                    )
                )

        elif posting_instruction.type == PostingInstructionType.OUTBOUND_AUTHORISATION:
            new_posting_instructions.extend(
                _rebalance_outbound_auth(
                    vault, denomination, posting_instruction, in_flight_balances, effective_datetime
                )
            )

        elif posting_instruction.type == PostingInstructionType.AUTHORISATION_ADJUSTMENT:
            new_posting_instructions.extend(
                _rebalance_auth_adjust(
                    vault,
                    denomination,
                    posting_instruction,  # type: ignore
                    in_flight_balances,
                    effective_datetime,
                )
            )

        elif (
            posting_instruction.type == PostingInstructionType.RELEASE
            and posting_instruction_pending_out_balance < 0
        ):
            new_posting_instructions.extend(
                _rebalance_release(
                    vault,
                    denomination,
                    posting_instruction,  # type: ignore
                    client_transaction,
                    in_flight_balances,
                    effective_datetime,
                )
            )
    return new_posting_instructions


def _charge_txn_type_fees(
    vault: SmartContractVault,
    posting_instructions: list[PostingInstruction],
    latest_balances: BalanceDefaultDict,
    in_flight_balances: BalanceDefaultDict,
    denomination: str,
    effective_datetime: datetime,
) -> list[CustomInstruction]:
    """
    For a list of committed postings, checks whether any transaction-type fees exist and applies the
    highest out of the %-based or flat fee. Only applied to settlement, hard_settlement and
    transfer instructions.

    :param vault: Vault object for the account
    :param posting_instructions: The posting instructions to check for fees
    :param latest_balances: Account latest balances at the start of the hook execution
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param denomination: Denomination of the account
    :param effective_datetime: datetime of when the posting instructions are being processed
    :return: List of CustomInstructions to charge fees
    """

    supported_txn_types = _get_supported_txn_types(vault)
    txn_code_to_type_map = utils.get_parameter(
        name=PARAM_TXN_CODE_TO_TYPE_MAP, is_json=True, vault=vault
    )
    txn_type_fees = utils.get_parameter(name=PARAM_TXN_TYPE_FEES, is_json=True, vault=vault)

    # 'over_deposit_only' fees are charged if the txn amount exceeded deposit when txn was made
    # so we must get the deposit balance before we rebalanced any transactions and update it with
    # the txn amounts as we go
    deposit_balance_before_txn = utils.balance_at_coordinates(
        balances=latest_balances, address=DEPOSIT_BALANCE, denomination=denomination
    )

    txn_type_fees_posting_instructions: list[CustomInstruction] = []
    for posting_instruction in posting_instructions:
        # We're assuming fees are charged only on instructions that move settled funds.
        if posting_instruction.type not in (
            PostingInstructionType.SETTLEMENT,
            PostingInstructionType.OUTBOUND_HARD_SETTLEMENT,
            PostingInstructionType.TRANSFER,
        ):
            continue

        posting_instruction_balance: Decimal = posting_instruction.balances()[
            DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
        ].net

        # Skip posting instructions that credit account committed balance
        if posting_instruction_balance < Decimal("0"):
            continue

        txn_type, _ = _get_txn_type_and_ref_from_posting(
            vault,
            posting_instruction.instruction_details,
            effective_datetime,
            supported_txn_types=supported_txn_types,
            txn_code_to_type_map=txn_code_to_type_map,
        )
        fees = txn_type_fees.get(txn_type, None)
        if not fees:
            continue

        income_account = _get_fee_internal_account(vault, txn_type=txn_type)

        percentage_fee = Decimal(fees.get("percentage_fee", 0))
        flat_fee = Decimal(fees.get("flat_fee", 0))
        fee_cap = Decimal(fees.get("fee_cap", 0))
        fee_amount = Decimal("0")

        combine_flat_and_percentage = utils.str_to_bool(fees.get("combine", "False"))
        over_deposit_only = utils.str_to_bool(fees.get("over_deposit_only", "False"))
        if not over_deposit_only or deposit_balance_before_txn < posting_instruction_balance:
            if combine_flat_and_percentage:
                fee_amount = sum(
                    [flat_fee, percentage_fee * posting_instruction_balance]
                )  # type: ignore
            else:
                fee_amount = max(flat_fee, percentage_fee * posting_instruction_balance)

        if fee_cap > 0:
            fee_amount = min(fee_amount, fee_cap)

        if fee_amount > Decimal(0):
            fee_type = f"{txn_type.upper()}_FEE"
            txn_type_fees_posting_instructions.extend(
                _rebalance_fees(
                    vault,
                    Decimal(fee_amount),
                    denomination,
                    in_flight_balances,
                    income_account,
                    fee_type,
                )
            )

        deposit_balance_before_txn -= posting_instruction_balance

    return txn_type_fees_posting_instructions


def _check_txn_type_credit_limits(
    vault: SmartContractVault,
    balances: BalanceDefaultDict,
    posting_instructions: list[PostingInstruction],
    denomination: str,
    effective_datetime: datetime,
    txn_code_to_type_map: dict[str, str],
) -> Optional[Rejection]:
    """
    Rejects any postings that breach their transaction type credit limit, which can be an absolute
    number or a percentage of the overall credit limit (e.g. cash advances may be limited to 25% of
    the credit limit, or a flat amount of 2000 in the relevant denomination). Accounts for existing
    charged, billed on unpaid transactions
    Note: this should be done last in pre-posting hook as it is more intensive than standard checks
    and we assume overall credit limit checks have passed

    :param vault: Vault object for the account
    :param balances: Balances to be used for limit checks. These should be live balances unless
    there is a specific reason otherwise
    :param posting_instructions: The posting instructions to check against transaction type limits
    :param denomination: Denomination of the account
    :param effective_datetime: datetime of when the posting instructions are being processed
    :param txn_code_to_type_map: Map of transaction codes to transaction types
    :return: Rejection if any transaction type limit is breached by a posting, else None
    """

    txn_type_credit_limits = utils.get_parameter(
        name=PARAM_TXN_TYPE_LIMITS, at_datetime=effective_datetime, is_json=True, vault=vault
    )
    if txn_type_credit_limits == {}:
        return None

    credit_limit = utils.get_parameter(
        name=PARAM_CREDIT_LIMIT, at_datetime=effective_datetime, vault=vault
    )
    # Defaulting the limits to the overall limit is safe as we've already done overall limit checks
    final_txn_type_credit_limits = {
        txn_type: min(
            Decimal(txn_type_credit_limits[txn_type].get("flat", credit_limit)),
            credit_limit * Decimal(txn_type_credit_limits[txn_type].get("percentage", 1)),
        )
        for txn_type in txn_type_credit_limits
    }

    proposed_amount_by_txn_type: dict = defaultdict(lambda: 0)

    # get total amount in batch per transaction type
    for posting_instruction in posting_instructions:
        txn_type, _ = _get_txn_type_and_ref_from_posting(
            vault,
            posting_instruction.instruction_details,
            effective_datetime,
            txn_code_to_type_map=txn_code_to_type_map,
        )
        txn_type_credit_limit = final_txn_type_credit_limits.get(txn_type, 0)

        if txn_type_credit_limit and txn_type_credit_limit != credit_limit:
            # We assume a single denomination and asset across the account
            proposed_amount_by_txn_type[txn_type] += sum(
                balance.net
                for dimensions, balance in posting_instruction.balances().items()
                if dimensions[0] == DEFAULT_ADDRESS and dimensions[1] == DEFAULT_ASSET
            )

    # Get transaction types with references to ensure all relevant balances are checked
    txn_types_with_refs: dict[str, list[str]] = utils.get_parameter(
        vault,
        name=PARAM_TXN_REFS,
        at_datetime=effective_datetime,
        is_json=True,
    )

    # upper_case_list_values
    txn_types_with_refs = {
        key: [str(i).upper() for i in value] for key, value in txn_types_with_refs.items()
    }

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
            return Rejection(
                message=f"Insufficient funds for {denomination} {abs(proposed_amount)} transaction "
                f"due to {denomination} {final_txn_type_credit_limits[txn_type]:.2f} limit on "
                f"transaction type {txn_type}. Outstanding transactions amount to {denomination} "
                f"{abs(current_txn_type_balance)}",
                reason_code=RejectionReason.INSUFFICIENT_FUNDS,
            )
    return None


def _process_repayment(
    vault: SmartContractVault,
    denomination: str,
    posting_instruction: PostingInstruction,
    in_flight_balances: BalanceDefaultDict,
    effective_datetime: datetime,
    client_transaction: Optional[ClientTransaction] = None,
    account_id: Optional[str] = None,
) -> tuple[list[CustomInstruction], BalanceDefaultDict]:
    """
    Creates instructions to process a repayment by updating:
     - principal and bank charge addresses
     - overdue addresses
     - deposit address
     - repayment tracker

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param posting_instruction: The repayment posting
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param effective_datetime: Datetime of the repayment
    :param client_transaction: The client transaction the repayment posting belongs to
    :param account_id: account id of the vault account
    :return: Tuple of repayment rebalancing CustomInstructions and updated inflight balances
    """
    total_repayment_amount, _ = _get_settlement_info(
        vault, denomination, posting_instruction, client_transaction, account_id=account_id
    )
    if total_repayment_amount == 0:
        return [], in_flight_balances
    repayment_posting_instructions: list[CustomInstruction] = []

    posting_instruction_denomination = get_denomination_from_posting_instruction(
        posting_instruction
    )
    # Modifies repayment_posting_instructions and in_flight_balances
    remaining_repayment_amount = _repay_spend_and_charges(
        vault,
        in_flight_balances,
        effective_datetime,
        repayment_posting_instructions,
        posting_instruction,
        total_repayment_amount,
    )

    # Modifies repayment_posting_instructions and in_flight_balances
    _repay_overdue_buckets(
        vault,
        posting_instruction_denomination,
        in_flight_balances,
        repayment_posting_instructions,
        total_repayment_amount,
    )

    # Modifies in_flight_balances
    repayment_posting_instructions.extend(
        _make_deposit_postings(
            vault,
            posting_instruction_denomination,
            remaining_repayment_amount,
            in_flight_balances,
            {},
            is_repayment=True,
        )
    )

    # Modifies in_flight_balances
    repayment_posting_instructions.extend(
        _update_total_repayment_tracker(
            vault, in_flight_balances, posting_instruction_denomination, total_repayment_amount
        )
    )
    return repayment_posting_instructions, in_flight_balances


def _update_total_repayment_tracker(
    vault: SmartContractVault,
    in_flight_balances: BalanceDefaultDict,
    posting_instruction_denomination: str,
    amount_repaid: Decimal,
) -> list[CustomInstruction]:
    """
    Create postings to update repayment address with current amount repaid in statement period.

    :param vault: Vault object for the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param posting_instruction_denomination: Denomination of the repayment posting
    :param amount_repaid: Total amount repaid (+ve)
    :return: CustomInstructions to update the tracking address
    """
    # Save how much we repaid before PDD - will be used to see if we repaid PARAM_MAD
    if amount_repaid > 0:
        return _make_internal_address_transfer(
            vault,
            amount=amount_repaid,
            denomination=posting_instruction_denomination,
            credit_internal=True,
            custom_address=TRACK_STATEMENT_REPAYMENTS,
            in_flight_balances=in_flight_balances,
        )
    return []


def _repay_spend_and_charges(
    vault: SmartContractVault,
    in_flight_balances: BalanceDefaultDict,
    effective_datetime: datetime,
    repayment_posting_instructions: list[CustomInstruction],
    posting_instruction: PostingInstruction,
    remaining_repayment_amount: Decimal,
) -> Decimal:
    """
    Create postings to distribute the repayment amount using the repayment hierarchy

    :param vault: Vault object for the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param effective_datetime: Datetime of when the repayment is being processed
    :param repayment_posting_instructions: The inflight repayment rebalancing posting instructions
    that are to be extended
    :param posting_instruction: The repayment posting instruction
    :param remaining_repayment_amount: The remaining repayment amount to distribute at the start of
    this function execution
    :return: The remaining repayment amount that has not been distributed
    """
    # Get supported spending types
    txn_types = _get_supported_txn_types(vault, effective_datetime)
    fee_types = _get_supported_fee_types(vault, txn_types)
    txn_stems = _construct_stems(txn_types)
    txn_repayment_hierarchy: dict[str, dict[str, str]] = utils.get_parameter(
        vault,
        name=PARAM_TXN_APR,
        is_json=True,
    )

    # upper_case_dict_values
    txn_repayment_hierarchy = {
        key: {str(i).upper(): str(j).upper() for i, j in value.items()}
        for key, value in txn_repayment_hierarchy.items()
    }

    txn_type_repayment_hierarchy = utils.get_parameter(vault, name=PARAM_APR, is_json=True)
    ordered_stems: list[str] = _order_stems_by_repayment_hierarchy(
        txn_stems,
        txn_hierarchy=txn_repayment_hierarchy,
        txn_type_hierarchy=txn_type_repayment_hierarchy,
    )
    repayment_addresses = _get_repayment_addresses(
        REPAYMENT_HIERARCHY, ordered_stems, fee_types  # type: ignore
    )
    denomination = get_denomination_from_posting_instruction(posting_instruction)

    for _, _, address in repayment_addresses:
        if remaining_repayment_amount > 0:
            balance = utils.balance_at_coordinates(
                balances=in_flight_balances, address=address, denomination=denomination
            )
            if balance > 0:
                balance_repayment = min(balance, remaining_repayment_amount)
                remaining_repayment_amount -= balance_repayment
                repayment_posting_instructions.extend(
                    _make_internal_address_transfer(
                        vault,
                        balance_repayment,
                        denomination,
                        credit_internal=False,
                        custom_address=address,
                        in_flight_balances=in_flight_balances,
                    )
                )

    return remaining_repayment_amount


def _get_repayment_addresses(
    repayment_hierarchy: list[dict[str, Union[str, list[str]]]],
    txn_types: list[str],
    fee_types: list[str],
) -> list[tuple[str, str, str]]:
    """
    Get a list of balance addresses that will be posted to for repayment.

    :param repayment_hierarchy: List of entries that constitute the repayment hierarchy.
    Each entry has:
    - 'repayment_type' key-value pair (BANK_CHARGE or PRINCIPAL)
    - an optional 'bank_charge_type' key-value pair (FEES or INTEREST) to clarify the bank charge
     type if the repayment type is BANK_CHARGE
    - 'statuses' key-value pair (List of balance statuses) to indicate which balance statuses are
    in-scope
    :param txn_types: List of transaction types ordered by decreasing PARAM_APR
    :param fee_types: List of fee types
    :return: Ordered list of (category, sub-category, address) tuples to repay to
    """
    addresses = []

    def construct_addresses(
        address_callback: Callable,
        category: str,
        supported_sub_categories: list[str],
        balance_status: str,
    ) -> list[tuple[str, str, str]]:
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


def _repay_overdue_buckets(
    vault: SmartContractVault,
    denomination: str,
    in_flight_balances: BalanceDefaultDict,
    repayment_posting_instructions: list[CustomInstruction],
    repayment_amount: Decimal,
) -> None:
    """
    Create postings to distribute repayment from oldest overdue bucket to newest overdue bucket.

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param repayment_posting_instructions: The inflight repayment rebalancing posting instructions
    that are to be extended
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
            repayment_posting_instructions.extend(
                _make_internal_address_transfer(
                    amount=amount,
                    denomination=denomination,
                    credit_internal=False,
                    custom_address=overdue_address,
                    vault=vault,
                    in_flight_balances=in_flight_balances,
                )
            )
        if repayment_amount == 0:
            break


def _create_custom_instructions(
    vault: SmartContractVault,
    amount: Decimal,
    debit_account_id: str,
    credit_account_id: str,
    denomination: Optional[str] = None,
    debit_address: str = DEFAULT_ADDRESS,
    instruction_details: Optional[dict[str, str]] = None,
    credit_address: str = DEFAULT_ADDRESS,
    in_flight_balances: Optional[BalanceDefaultDict] = None,
) -> list[CustomInstruction]:
    """
    Generic Wrapper to create a list of CustomInstructions which ensure consistency with
    restriction overrides and when updating in-flight balances

    :param vault: Vault object for the account
    :param amount: Amount to debit/credit from the accounts
    :param debit_account_id: Account being debited
    :param credit_account_id: Account being credited
    :param denomination: Denomination of the accounts
    :param debit_address: Balance address to debit on the debit account
    :param instruction_details: Metadata for the postings
    :param credit_address: Balance address to credit on the credit account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :return: List containing the Custom Instruction
    """
    if amount == 0:
        return []

    denomination = denomination or utils.get_parameter(vault, name=PARAM_DENOMINATION)
    instruction_details = instruction_details or {}

    new_instructions = move_funds_between_vault_accounts(
        amount=amount,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        debit_account_id=debit_account_id,
        debit_address=debit_address,
        credit_account_id=credit_account_id,
        credit_address=credit_address,
        instruction_details=instruction_details,
        override_all_restrictions=True,
    )

    if in_flight_balances:
        _update_balances(vault.account_id, in_flight_balances, new_instructions)  # type: ignore

    return new_instructions


def _make_internal_address_transfer(
    vault: SmartContractVault,
    amount: Decimal,
    denomination: str,
    credit_internal: bool,
    custom_address: str,
    instruction_details: Optional[dict[str, str]] = None,
    in_flight_balances: Optional[BalanceDefaultDict] = None,
) -> list[CustomInstruction]:
    """
    Create CustomInstructions to move funds between the account's INTERNAL_CONTRA address and
    another address

    :param vault: Vault object for the account
    :param amount: Amount to transfer
    :param denomination: Denomination of the account
    :param credit_internal: True if crediting the INTERNAL_CONTRA address, False if debiting the
    INTERNAL_CONTRA address
    :param custom_address: Address to transfer to credit/debit from (depending on credit_internal).
    :param instruction_details: Metadata to be added to the instructions
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :return: List containing the Custom Instruction
    """
    if amount <= 0:
        return []

    credit_address = INTERNAL_BALANCE if credit_internal else custom_address
    debit_address = custom_address if credit_internal else INTERNAL_BALANCE

    new_posting_instructions = _create_custom_instructions(
        vault,
        amount,
        debit_account_id=vault.account_id,
        credit_account_id=vault.account_id,
        denomination=denomination,
        debit_address=debit_address,
        instruction_details=instruction_details,
        credit_address=credit_address,
        in_flight_balances=in_flight_balances,
    )

    return new_posting_instructions


def _calculate_aggregate_balance(
    balances: BalanceDefaultDict,
    denomination: str,
    fee_types: list[str],
    balance_def: dict[str, list[str]],
    include_deposit: bool,
    txn_type_map: Optional[dict[str, Optional[list[str]]]] = None,
) -> Decimal:
    """
    Sums up individual balances based on a definition that specifies which balance states are
    in-scope for principal, fees and interest balances, and a list of relevant transaction types
    and fee types.


    :param balances: Balances to calculate the aggregate from
    :param denomination: Denomination of the account
    :param fee_types: List of fee types to be included for fees
    :param balance_def: Valid key-value pairs:
        -  balance type (PRINCIPAL, FEES, INTEREST) to list of balance states (AUTH, CHARGED,
         UNCHARGED, BILLED, UNPAID) to be included in the aggregate calculation
    :param include_deposit: If True the deposit balance is included in the calculation
    :param txn_type_map: Map of transaction types to list of refs to be included for Principal and
    Interest
    :return: The value of the aggregate balance
    """
    # txn/fee/interest_states are list[str]
    txn_states = balance_def.get(PRINCIPAL, [])
    fee_states = balance_def.get(FEES, [])
    interest_states = balance_def.get(INTEREST, [])

    principal_addresses: list[str] = []
    interest_addresses: list[str] = []
    fee_addresses: list[str] = []
    txn_type_map = txn_type_map or {}

    def _build_addresses_for_states(
        address_creation_method: Callable,
        addresses: list[str],
        states: list[str],
        txn_type: str,
        txn_refs: Optional[list[str]] = None,
    ) -> None:
        """
        Append formed addresses to provided list for later use.

        :param address_creation_method: name of method to be called for address creation
        :param addresses: list of addresses to be appended to
        :param states: list of states to be iterated
        :param txn_type: transaction type
        :param txn_refs: returns None, updates list of transaction references (if present)
        """
        for state in states:
            if txn_refs:
                for ref in txn_refs:
                    addresses.append(address_creation_method(txn_type.upper(), state, txn_ref=ref))
            else:
                addresses.append(address_creation_method(txn_type.upper(), state))

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

    return Decimal(aggregate_balance)


def _adjust_aggregate_balances(
    vault: SmartContractVault,
    denomination: str,
    in_flight_balances: BalanceDefaultDict,
    effective_datetime: Optional[datetime] = None,
    available: bool = True,
    outstanding: bool = True,
    full_outstanding: bool = True,
    credit_limit: Decimal = Decimal("0"),
) -> list[CustomInstruction]:
    """
    Helper to adjust aggregate balances for available, outstanding and full outstanding addresses.

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param effective_datetime: Datetime to fetch parameter values, if not provided
    the latest values are retrieved
    :param available: If True the available balance will be adjusted
    :param outstanding: If True the outstanding balance will be adjusted
    :param full_outstanding: If True full outstanding balance will be adjusted
    :param credit_limit: Credit limit of the account
    :return: List containing the adjustment CustomInstructions
    """

    txn_types = _get_supported_txn_types(vault, effective_datetime)
    fee_types = _get_supported_fee_types(vault, txn_types)

    scope = {
        AVAILABLE_BALANCE: available,
        OUTSTANDING_BALANCE: outstanding,
        FULL_OUTSTANDING_BALANCE: full_outstanding,
    }
    adjustment_posting_instructions: list[CustomInstruction] = []

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
            if aggregate_address in [AVAILABLE_BALANCE]:
                new_amount = credit_limit - new_amount

            adjustment_posting_instructions.extend(
                _override_info_balance(
                    vault,
                    in_flight_balances=in_flight_balances,
                    balance_address=aggregate_address,
                    denomination=denomination,
                    amount=new_amount,
                )
            )

    if (
        utils.balance_at_coordinates(
            balances=in_flight_balances,
            denomination=denomination,
            address=FULL_OUTSTANDING_BALANCE,
        )
        <= 0
        and scope[FULL_OUTSTANDING_BALANCE]
    ):
        adjustment_posting_instructions.extend(
            _change_revolver_status(
                vault,
                denomination,
                in_flight_balances,
                revolver=False,
            )
        )

    return adjustment_posting_instructions


def _change_revolver_status(
    vault: SmartContractVault,
    denomination: str,
    in_flight_balances: BalanceDefaultDict,
    revolver: bool,
) -> list[CustomInstruction]:
    """
    Creates CustomInstructions to set or unset an account as revolving.

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param revolver: If True then the account will be set to revolving, else unset revolving
    :return: List of CustomInstructions to set or unset revolving status
    """
    # guarantee we don't 'overset/underset' the Revolver balance
    if revolver == _is_revolver(in_flight_balances, denomination):
        return []

    return _make_internal_address_transfer(
        vault,
        amount=Decimal(1),
        denomination=denomination,
        custom_address=REVOLVER_BALANCE,
        credit_internal=not revolver,
        in_flight_balances=in_flight_balances,
    )


def _rebalance_release(
    vault: SmartContractVault,
    denomination: str,
    posting_instruction: Release,
    client_transaction: ClientTransaction,
    in_flight_balances: BalanceDefaultDict,
    effective_datetime: datetime,
) -> list[CustomInstruction]:
    """
    When an outbound authorisation is released, create CustomInstructions to zero out the
    corresponding _AUTH balances.

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param posting_instruction: The Release posting to rebalance
    :param client_transaction: The client transaction the Release belongs to
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param effective_timestamp: Datetime as of which rebalancing is happening
    :return: List of CustomInstructions to rebalance the Release posting
    """
    # Get remaining authorised amount from client_transaction and remove this from Auth balance
    amount = _get_unsettled_amount(denomination, client_transaction)
    if amount == 0:
        return []

    txn_type, _ = _get_txn_type_and_ref_from_posting(
        vault, posting_instruction.instruction_details, effective_datetime, upper_case_type=True
    )
    balance_address = _principal_address(txn_type, AUTH)

    return _make_internal_address_transfer(
        vault,
        amount=amount,
        denomination=denomination,
        credit_internal=False,
        custom_address=balance_address,
        instruction_details=posting_instruction.instruction_details,
        in_flight_balances=in_flight_balances,
    )


def _rebalance_auth_adjust(
    vault: SmartContractVault,
    denomination: str,
    posting_instruction: AuthorisationAdjustment,
    in_flight_balances: BalanceDefaultDict,
    effective_datetime: datetime,
) -> list[CustomInstruction]:
    """
    When an outbound authorisation is adjusted, create CustomInstructions to adjust any
    corresponding _AUTH balances. Thus, increasing absolute value for increased auths and
    decreasing absolute value for decreased auths.

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param posting_instruction: The AuthorisationAdjustment posting to rebalance
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param effective_datetime: Datetime as of which rebalancing is happening
    :return: List of CustomInstructions to rebalance the AuthorisationAdjustment posting
    """
    txn_type, _ = _get_txn_type_and_ref_from_posting(
        vault, posting_instruction.instruction_details, effective_datetime, upper_case_type=True
    )
    balance_address = _principal_address(txn_type, AUTH)

    posting_instruction_pending_out_balance = posting_instruction.balances()[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT
    ].net
    if posting_instruction_pending_out_balance < 0:
        # auth less spend
        credit_internal = False
    else:
        # auth more spend
        credit_internal = True

    return _make_internal_address_transfer(
        vault,
        amount=abs(posting_instruction_pending_out_balance),
        denomination=denomination,
        credit_internal=credit_internal,
        custom_address=balance_address,
        instruction_details=posting_instruction.instruction_details,
        in_flight_balances=in_flight_balances,
    )


def _rebalance_outbound_auth(
    vault: SmartContractVault,
    denomination: str,
    posting_instruction: OutboundAuthorisation,
    in_flight_balances: BalanceDefaultDict,
    effective_datetime: datetime,
) -> list[CustomInstruction]:
    """
    When an outbound transaction is authorised create CustomInstructions to adjust any
    corresponding _AUTH balances.

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param posting_instruction: The OutboundAuthorisation posting to rebalance
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param effective_datetime: Datetime as of which rebalancing is happening
    :return: List of CustomInstructions to rebalance the OutboundAuthorisation posting
    """
    txn_type, txn_ref = _get_txn_type_and_ref_from_posting(
        vault, posting_instruction.instruction_details, effective_datetime, upper_case_type=True
    )
    balance_address = _principal_address(txn_type, AUTH, txn_ref=txn_ref)
    posting_instruction_amount = posting_instruction.balances()[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT
    ].net

    return _make_internal_address_transfer(
        amount=posting_instruction_amount,
        denomination=denomination,
        custom_address=balance_address,
        credit_internal=True,
        instruction_details=posting_instruction.instruction_details,
        vault=vault,
        in_flight_balances=in_flight_balances,
    )


def _rebalance_outbound_settlement(
    vault: SmartContractVault,
    client_transaction: ClientTransaction,
    in_flight_balances: BalanceDefaultDict,
    effective_datetime: datetime,
) -> list[CustomInstruction]:
    """
    When a transaction is settled create postings to:
    - charge external fees
    - adjust relevant _AUTH balances
    - take the spend amount of DEPOSIT and/or _CHARGED balances

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param client_transaction: the client transaction being settled. The settlement is assumed
    to be the newest posting instruction (i.e. last in the list)
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param effective_datetime: Datetime as of which rebalancing is happening
    :return: List of CustomInstructions to rebalance the Settlement posting May be an empty
    list if no change is required (e.g. no prior unsettled amount on the client transaction)
    """
    rebalance_posting_instructions: list[CustomInstruction] = []
    supported_txn_types = _get_supported_txn_types(vault, effective_datetime)
    external_fee_types = utils.get_parameter(vault, name=PARAM_EXTERNAL_FEE_TYPES, is_json=True)

    newest_posting_instruction = client_transaction.posting_instructions[-1]
    # the instruction types we support will all have a denomination on their client transaction
    client_transaction_denomination: str = client_transaction.denomination  # type: ignore
    amount_to_settle = _get_settlement_amount(
        account_id=vault.account_id,
        denomination=client_transaction_denomination,
        posting_instruction=newest_posting_instruction,
    )

    fee_type = newest_posting_instruction.instruction_details.get(FEE_TYPE, "")
    if fee_type.lower() in external_fee_types:
        _, rebalance_posting_instructions = _charge_fee(
            vault=vault,
            denomination=client_transaction_denomination,
            in_flight_balances=in_flight_balances,
            fee_type=fee_type,
            fee_amount=amount_to_settle,
            is_external_fee=True,
        )
        return rebalance_posting_instructions

    txn_type, txn_ref = _get_txn_type_and_ref_from_posting(
        vault=vault,
        instruction_details=newest_posting_instruction.instruction_details,
        effective_datetime=effective_datetime,
        supported_txn_types=supported_txn_types,
        upper_case_type=True,
    )

    # hard settlements/transfers will never be reflected in the _AUTH buckets
    if newest_posting_instruction.type == PostingInstructionType.SETTLEMENT:
        rebalance_posting_instructions.extend(
            _update_auth_bucket_for_outbound_settlement(
                vault=vault,
                client_transaction=client_transaction,
                in_flight_balances=in_flight_balances,
                txn_type=txn_type,
                txn_ref=txn_ref,
            )
        )

    credit_line_spend, deposit_spend = _determine_amount_breakdown(
        amount_to_settle,
        client_transaction_denomination,
        in_flight_balances,
    )
    if credit_line_spend > 0:
        # We only debit the principal address (e.g. PURCHASE_CHARGED) and make gl postings if the
        # posting amount exceeds the available deposit
        address = _principal_address(txn_type, CHARGED, txn_ref=txn_ref)
        rebalance_posting_instructions.extend(
            _make_internal_address_transfer(
                vault=vault,
                amount=credit_line_spend,
                denomination=client_transaction_denomination,
                custom_address=address,
                credit_internal=True,
                instruction_details=newest_posting_instruction.instruction_details,
                in_flight_balances=in_flight_balances,
            )
        )
    rebalance_posting_instructions.extend(
        _make_deposit_postings(
            vault=vault,
            denomination=client_transaction_denomination,
            amount=deposit_spend,
            in_flight_balances=in_flight_balances,
            instruction_details={},
        )
    )

    return rebalance_posting_instructions


def _make_deposit_postings(
    vault: SmartContractVault,
    denomination: str,
    amount: Decimal,
    in_flight_balances: BalanceDefaultDict,
    instruction_details: Optional[dict[str, str]],
    is_repayment: bool = False,
) -> list[CustomInstruction]:
    """
    Make postings to rebalance the deposit address when spending from/repaying to
    the deposit balance

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param amount: +ve amount being spent/repaid
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param instruction_details: Metadata to add to CustomInstructions
    :param is_repayment: True if repaying to deposit, False if spending from deposit
    :return: List of CustomInstructions to rebalance the deposit address
    """

    if amount == 0:
        return []

    return _make_internal_address_transfer(
        amount=amount,
        denomination=denomination,
        credit_internal=is_repayment,  # if repaying, debit DEPOSIT_BALANCE to make it more positive
        custom_address=DEPOSIT_BALANCE,
        in_flight_balances=in_flight_balances,
        instruction_details=instruction_details,
        vault=vault,
    )


def _get_interest_internal_accounts(
    vault: SmartContractVault,
    charge_type: str,
    sub_type: str,
) -> str:
    """
    Helper to retrieve income principal accounts for a given transaction type

    :param vault: Vault object for the account
    :param charge_type: One of PRINCIPAL, FEES or INTEREST
    :param sub_type: Transaction type or Fee type to retrieve accounts for
    :return: Income principal account id
    """
    if charge_type == FEES:
        income_account: str = utils.get_parameter(
            name=PARAM_INTEREST_ON_FEES_INTERNAL_ACCOUNT, vault=vault
        )

    else:
        txn_type_interest_internal_account_map: dict[str, str] = utils.get_parameter(
            name=PARAM_TXN_TYPE_INTEREST_INTERNAL_ACCOUNTS_MAP, is_json=True, vault=vault
        )
        income_account = txn_type_interest_internal_account_map[sub_type.lower()]

    return income_account


def _gl_posting_metadata(
    event: str,
    account_id: str,
    repayment: bool = False,
    txn_type: Optional[str] = None,
    interest_value_datetime: Optional[datetime] = None,
) -> dict[str, str]:
    """
    Helper to create GL posting metadata consistently

    :param event: GL event
    :param account_id: The customer account id the GL posting instruction is made for
    :param repayment: True if this is a repayment
    :param txn_type: Transaction type for posting if applicable
    :param interest_value_datetime: Interest value datetime for the posting instruction, if
    applicable
    :return: GL posting metadata
    """

    instruction_details = {
        "accounting_event": "LOAN_REPAYMENT" if repayment else event,
        "account_id": account_id,
    }

    if txn_type:
        instruction_details["inst_type"] = txn_type.lower()

    if interest_value_datetime:
        instruction_details["interest_value_datetime"] = str(interest_value_datetime)

    return instruction_details


def _determine_amount_breakdown(
    amount_to_charge: Decimal,
    denomination: str,
    in_flight_balances: BalanceDefaultDict,
) -> tuple[Decimal, Decimal]:
    """
    For a given amount charged (settled transaction, bank charges), determine how much is spent
    from deposit balance vs the credit line

    :param amount_to_charge: the >= 0 amount that is being charged
    :param denomination: Denomination of the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :return: Tuple containing amount to settle from credit limit and amount to settle from
    deposit
    """
    available_deposit = utils.balance_at_coordinates(
        balances=in_flight_balances, address=DEPOSIT_BALANCE, denomination=denomination
    )
    deposit_amount = min(amount_to_charge, available_deposit)
    credit_line_amount = amount_to_charge - deposit_amount
    return credit_line_amount, deposit_amount


def _update_auth_bucket_for_outbound_settlement(
    vault: SmartContractVault,
    client_transaction: ClientTransaction,
    in_flight_balances: BalanceDefaultDict,
    txn_type: str,
    txn_ref: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Creates posting instructions to update the _AUTH balance for the transaction type / ref
    when processing a settlement for an outbound authorisation.

    :param vault: Vault object for the account
    :param client_transaction: The client transaction being settled. The settlement is assumed
    to be the newest posting instruction (i.e. last in the list)
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param txn_type: The posting instruction's transaction type
    :param txn_ref: The posting instruction's transaction ref, if applicable
    :return: List of CustomInstructions to update the _AUTH balance. May be an empty list if no
    change is required (e.g. no prior unsettled amount on the client transaction)
    """
    update_auth_posting_instructions: list[CustomInstruction] = []
    if (
        client_transaction.posting_instructions[0].type
        is not PostingInstructionType.OUTBOUND_AUTHORISATION
    ):
        return update_auth_posting_instructions

    # type warnings below on client transaction are ignored as they are for attributes that
    # will be None for a client transaction based on a custom instruction, which we've already
    # checked isn't the case

    # unsettled will be <=0 for outbound auths
    prior_unsettled_amount = -client_transaction.effects(  # type: ignore
        # there must be 2+ posting instructions if we are processing a client transaction
        # with auth and settlement
        effective_datetime=client_transaction.posting_instructions[-2].value_datetime
    ).unsettled
    settled_amount = _get_settlement_amount(
        account_id=vault.account_id,
        denomination=client_transaction.denomination,  # type: ignore
        posting_instruction=client_transaction.posting_instructions[-1],  # type: ignore
    )

    # Need to adjust AUTH spending bucket to reflect authorised funds being settled. Note
    # AUTH bucket shouldn't go +ve
    # | Settle >= Prior Unsettled  | TXN is completed | Desired outcome              |
    # |----------------------------|------------------|------------------------------|
    # | True                       | True             | Zero out Auth bucket         |
    # | False                      | True             | Zero out Auth bucket         |
    # | True                       | False            | Zero out Auth bucket         |
    # | False                      | False            | Reduce Auth by Settle amount |
    if client_transaction.completed() or settled_amount >= prior_unsettled_amount:
        auth_bucket_delta = prior_unsettled_amount  # Zero out auth bucket
    else:
        auth_bucket_delta = settled_amount  # Reduce auth bucket by settle amount

    if auth_bucket_delta > 0:
        balance_address = _principal_address(txn_type, AUTH, txn_ref=txn_ref)
        update_auth_posting_instructions = _make_internal_address_transfer(
            amount=auth_bucket_delta,
            denomination=client_transaction.denomination,  # type: ignore
            credit_internal=False,
            custom_address=balance_address,
            vault=vault,
            instruction_details=client_transaction.posting_instructions[-1].instruction_details,
            in_flight_balances=in_flight_balances,
        )

    return update_auth_posting_instructions


def _get_settlement_amount(
    account_id: str,
    denomination: str,
    posting_instruction: PostingInstruction,
) -> Decimal:
    """
    Extracts the amount being settled (i.e. affecting default address, asset, Phase.COMMITTED and
    the specified denomination) by a posting instruction

    :param account_id: the account id affected by the settlement
    :param denomination: Denomination of the account
    :param posting_instruction: the PostingInstruction being processed
    ClientTransaction/ClientTransactionEffects are not used so that CustomInstructions can also be
    handled
    :return: the amount the posting instruction is settling.
    """

    return posting_instruction.balances(account_id=account_id, tside=tside)[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
    ].net


# TODO: Check logic inside of settled amount
def _get_settlement_info(
    vault: SmartContractVault,
    denomination: str,
    posting_instruction: PostingInstruction,
    client_transaction: Optional[ClientTransaction] = None,
    account_id: Optional[str] = None,
) -> tuple[Decimal, Decimal]:
    """
    Extracts settled/unsettled info for a posting. This abstracts away postings API behaviour such
    as not having to specify an amount when making a 'final' settlement

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param posting_instruction: The posting instruction to get settlement information for
    :param client_transaction: The client transaction the posting instruction being processed
    belongs to
    :param account_id: of the Vault account
    :return: Tuple of the amount the posting is settling and the unsettled amount on
    the posting's client transaction *prior* to the settlement posting
    """
    unsettled_amount = (
        _get_unsettled_amount(
            denomination,
            client_transaction,
        )
        if client_transaction is not None
        else Decimal("0")
    )

    # TODO: Changed how this code works - confirm if still works with final settlement
    # amount is None for a final settlement, in which case we settle remaining unsettled amount
    amount_to_settle = abs(
        posting_instruction.balances(account_id=account_id, tside=vault.tside)[
            DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
        ].net
    )

    return amount_to_settle, unsettled_amount


def _get_unsettled_amount(
    denomination: str,
    client_transaction: ClientTransaction,
) -> Decimal:
    """
    Get the unsettled amount for a posting's client transaction. For example, if the transaction
    starts with an £100 auth, there has been a £30 settlement, and we are currently processing a
    £20 settlement, this will return £70 with include_proposed=False and £50 with
    include_proposed=True

    :param denomination: Denomination of the account
    :param client_transaction: The Client Transaction to get the unsettled amount from
    :return: Unsettled amount on the client transaction

    """
    unsettled_amount: Decimal = Decimal(
        sum(
            [
                posting_instruction.balances()[
                    DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT
                ].net
                for posting_instruction in client_transaction.posting_instructions[:-1]
            ]
        )
    )

    return unsettled_amount


def _is_revolver(balances: BalanceDefaultDict, denomination: str) -> bool:
    """
    Check if the revolver balance is 1 (revolver) or 0 (not revolver)

    :param balances: Account balances to use for revolver check
    :param denomination: Denomination of the account
    :return: True if the account is currently revolver, False otherwise
    """
    revolver_balance = balances[
        (REVOLVER_BALANCE, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    if revolver_balance == 0:
        return False
    return True


def _rebalance_interest(
    vault: SmartContractVault,
    amount: Decimal,
    denomination: str,
    in_flight_balances: BalanceDefaultDict,
    charge_type: str,
    sub_type: str,
    instructions: list[CustomInstruction],
    txn_ref: Optional[str] = None,
) -> None:
    """
    Rebalance interest by creating relevant GL postings and postings to update the account addresses
    based on whether the interest is coming from deposit or credit line

    :param vault: Vault object for the account
    :param amount: The bank charge amount
    :param denomination: Denomination of the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param charge_type: One of PRINCIPAL, FEES or INTEREST
    :param sub_type: The transaction or fee type that the interest is being accrued on
    :param instructions: The inflight rebalancing custom instructions that are to be extended
    :param txn_ref: Transaction level reference
    :return: None
    """
    credit_line_amount, deposit_amount = _determine_amount_breakdown(
        amount_to_charge=amount,
        denomination=denomination,
        in_flight_balances=in_flight_balances,
    )
    income_account = _get_interest_internal_accounts(vault, charge_type, sub_type)
    instruction_details: dict = {}

    # All charged interest must be reflected in default
    if amount > 0:
        instructions.extend(
            _create_custom_instructions(
                vault,
                amount=amount,
                debit_account_id=vault.account_id,
                debit_address=DEFAULT_ADDRESS,
                credit_account_id=income_account,
                credit_address=DEFAULT_ADDRESS,
                denomination=denomination,
                in_flight_balances=in_flight_balances,
                instruction_details=instruction_details,
            )
        )

    if credit_line_amount > 0:
        balance_address = _interest_address(sub_type, CHARGED, txn_ref=txn_ref)
        # Debit DEFAULT and Interest bucket, credit INTERNAL bucket
        instructions.extend(
            _make_internal_address_transfer(
                vault,
                amount=credit_line_amount,
                denomination=denomination,
                credit_internal=True,
                custom_address=balance_address,
                instruction_details=instruction_details,
                in_flight_balances=in_flight_balances,
            )
        )

    instructions.extend(
        _make_deposit_postings(
            vault=vault,
            denomination=denomination,
            amount=deposit_amount,
            in_flight_balances=in_flight_balances,
            instruction_details={},
        )
    )


def _rebalance_fees(
    vault: SmartContractVault,
    amount: Decimal,
    denomination: str,
    in_flight_balances: BalanceDefaultDict,
    income_account: str,
    fee_type: str,
) -> list[CustomInstruction]:
    """
    Rebalance fees by creating custom instructions to update the account addresses based on whether
    the fees are coming from deposit or credit line

    :param vault: Vault object for the account
    :param amount: The fee amount
    :param denomination: Denomination of the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param income_account: the GL income account id for the fee type
    :param fee_type: the fee type being charged. Used to populate metadata
    :return: The CustomInstructions to rebalance the fee
    """

    # regardless of percentage or flat fee parameter values, we always want balances to 2 dp
    amount = utils.round_decimal(amount, 2)
    if amount == 0:
        return []

    rebalance_fees_posting_instructions: list[CustomInstruction] = []
    external_fee_types = [
        fee.upper()
        for fee in utils.get_parameter(vault, name=PARAM_EXTERNAL_FEE_TYPES, is_json=True)
    ]
    credit_line_amount, deposit_amount = _determine_amount_breakdown(
        amount_to_charge=amount,
        denomination=denomination,
        in_flight_balances=in_flight_balances,
    )
    instruction_details = {"fee_type": fee_type}

    # All charged fee amounts must be debited from DEFAULT
    if amount > 0:
        # Dispute fees have already been debited from DEFAULT as they are initiated externally
        if fee_type not in external_fee_types:
            instruction_details.update({"gl_impacted": "True", "account_type": ACCOUNT_TYPE})
            rebalance_fees_posting_instructions.extend(
                _create_custom_instructions(
                    vault,
                    amount,
                    debit_account_id=vault.account_id,
                    debit_address=DEFAULT_ADDRESS,
                    credit_account_id=income_account,
                    credit_address=DEFAULT_ADDRESS,
                    denomination=denomination,
                    instruction_details=instruction_details,
                    in_flight_balances=in_flight_balances,
                )
            )

    # Only rebalance buckets and fee buckets if we're actually drawing from credit
    if credit_line_amount > 0:
        balance_address = _fee_address(fee_type, CHARGED)
        rebalance_fees_posting_instructions.extend(
            _make_internal_address_transfer(
                amount=credit_line_amount,
                denomination=denomination,
                credit_internal=True,
                custom_address=balance_address,
                instruction_details=instruction_details,
                in_flight_balances=in_flight_balances,
                vault=vault,
            )
        )

    rebalance_fees_posting_instructions.extend(
        _make_deposit_postings(
            vault,
            denomination,
            deposit_amount,
            in_flight_balances,
            instruction_details,
        )
    )
    return rebalance_fees_posting_instructions


def _get_supported_txn_types(
    vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> dict[str, Optional[list[str]]]:
    """
    Determine the mapping of transaction types that are supported. This is the
    PARAM_TXN_TYPES keys plus the "<txn_type>_<ref>" combinations for those types
    that use refs and are in PARAM_TXN_REFS.

    :param vault: Vault object for the account
    :param effective_datetime: Datetime as of which to retrieve parameters, if not provided
    the latest values are retrieved
    :return: Map of supported transaction types to transaction references.
    Note these are upper case versions of the types in the PARAM_TXN_TYPES and PARAM_TXN_REFS
    """

    txn_types: dict[str, dict[str, str]] = utils.get_parameter(
        vault, name=PARAM_TXN_TYPES, at_datetime=effective_datetime, is_json=True
    )
    supported_txn_types: dict[str, Optional[list[str]]] = {
        k.upper(): None for k in txn_types.keys()
    }

    txn_refs: dict[str, list[str]] = utils.get_parameter(
        vault,
        name=PARAM_TXN_REFS,
        at_datetime=effective_datetime,
        is_json=True,
    )

    # upper_case_list_values
    txn_refs = {key.upper(): [str(i).upper() for i in value] for key, value in txn_refs.items()}

    supported_txn_types.update(txn_refs)

    return supported_txn_types


def _construct_stems(txn_types: dict[str, Optional[list[str]]]) -> list[str]:
    """
    Given a Map of txn_types with any nested txn_level refs, construct a full list of stems by
    appending _TXN_REF (if present).

    :param txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :return: List of stems
    """
    txn_stems = []
    for txn_type, txn_ref in txn_types.items():
        if not txn_ref:
            txn_stems.append(txn_type)
        else:
            for ref in txn_ref:
                txn_stems.append(f"{txn_type}_{ref}")

    return txn_stems


def _order_stems_by_repayment_hierarchy(
    txn_stems: list[str],
    txn_hierarchy: dict[str, dict[str, str]],
    txn_type_hierarchy: dict[str, str],
) -> list[str]:
    """
    Given a list of stems, order by repayment hierarchy accounting for type and level rates.

    :param txn_stems: List of transaction stems
    :param txn_hierarchy: Map defining repayment order by transaction ref
    :param txn_type_hierarchy: Map defining repayment order by transaction type
    :return: Transaction types. Any transaction level references prefixed with parent
    type, then parent removed.
    """
    combined_repayment_hierarchy = _combine_txn_and_type_rates(txn_hierarchy, txn_type_hierarchy)

    # Sort all_txn_types by repayment hierarchy. Highest first, then in reverse alphabetical order.
    # TODO: Check this works for all scenarios
    # Filters out txn_stems where they aren't in the combined repayment hierarchy.
    txn_stems = [
        txn_stem for txn_stem in txn_stems if txn_stem.lower() in combined_repayment_hierarchy
    ]
    return sorted(
        txn_stems,
        key=lambda item: (Decimal(combined_repayment_hierarchy[item.lower()]), item),
        reverse=True,
    )


def _combine_txn_and_type_rates(
    txn_level_rate: dict[str, dict[str, str]], txn_type_rate: dict[str, str]
) -> dict[str, str]:
    """
    Extract rates for each transaction level reference and merge with transaction type rate dict.
    Refs are converted to lowercase to match txn_types.

    :param txn_level_rate: Map of reference to rate by transaction type
    :param txn_type_rate: Map of transaction type to rate
    :return: Map of transaction type (with reference, if applicable) to rate
    """
    stem_to_rate = {
        f"{txn_type}_{ref.lower()}": rates[ref]
        for txn_type, rates in txn_level_rate.items()
        for ref in rates
    }

    txn_type_rate.update(stem_to_rate)

    return txn_type_rate


def _get_supported_fee_types(
    vault: SmartContractVault,
    supported_txn_types: Optional[dict[str, Optional[list[str]]]] = None,
    external_fee_types: Optional[list[str]] = None,
) -> list[str]:
    """
    Determines all possible fees we can charge. Done dynamically as it depends on parameter values.

    :param vault: Vault object for the account
    :param supported_txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :param external_fee_types: External fee types supported
    :return: Supported fee types
    """

    external_fee_types = external_fee_types or [
        fee.upper()
        for fee in utils.get_parameter(vault, name=PARAM_EXTERNAL_FEE_TYPES, is_json=True)
    ]

    transaction_fee_types = [
        f"{txn_type}_FEE" for txn_type in supported_txn_types or _get_supported_txn_types(vault)
    ]

    # Shallow copy is OK as it's just a list of str
    return sorted(INTERNAL_FEE_TYPES.copy() + external_fee_types + transaction_fee_types)


def _get_txn_type_and_ref_from_posting(
    vault: SmartContractVault,
    instruction_details: dict[str, str],
    effective_datetime: datetime,
    supported_txn_types: Optional[dict[str, Optional[list[str]]]] = None,
    txn_code_to_type_map: Optional[dict[str, str]] = None,
    upper_case_type: bool = False,
) -> tuple[str, Optional[str]]:
    """
    Extract the transaction type from a posting based on its metadata and the contract supported
    transaction types. Return the transaction reference as well if there is one.

    :param vault: Vault object for the account
    :param instruction_details: Posting metadata containing transaction code
    :param effective_datetime: Datetime to get required parameter values as-of, if not provided
    the latest values are retrieved
    :param supported_txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :param txn_code_to_type_map: Map of transaction codes to transaction types
    :param upper_case_type: If true we will return txn_type in upper case
    :return: The transaction type and the reference (which may be None)
    """
    if txn_code_to_type_map is None:
        txn_code_to_type_map = utils.get_parameter(
            name=PARAM_TXN_CODE_TO_TYPE_MAP,
            at_datetime=effective_datetime,
            is_json=True,
            vault=vault,
        )
    if supported_txn_types is None:
        supported_txn_types = _get_supported_txn_types(vault, effective_datetime)

    txn_code = instruction_details.get(TXN_CODE, "")
    txn_type = txn_code_to_type_map.get(txn_code, DEFAULT_TXN_TYPE)  # type:ignore

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


def _process_interest_accrual_and_charging(
    vault: SmartContractVault, effective_datetime: datetime
) -> list[PostingInstructionsDirective]:
    """
    Determines what interest needs accruing and optionally charging, and instructs corresponding
    posting instructions

    :param vault: Vault object for the account
    :param effective_datetime: Datetime when to get account state as of for accrual purposes
    :return: The PostingInstructionDirectives to process interest accrual and charging
    """

    if utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_ACCRUAL_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    ):
        return []

    accrual_instructions: list[CustomInstruction] = []
    accrual_cut_off_dt = effective_datetime.replace(hour=0, minute=0, second=0) - relativedelta(
        microseconds=1
    )

    balances = BalanceDefaultDict()
    balances.update(
        {
            coord: ts.at(at_datetime=accrual_cut_off_dt)
            for coord, ts in vault.get_balances_timeseries(
                fetcher_id=ONE_SECOND_TO_MIDNIGHT_BIF_ID
            ).items()
        }
    )
    in_flight_balances = _deep_copy_balances(balances)

    denomination = utils.get_parameter(
        vault, name=PARAM_DENOMINATION, at_datetime=effective_datetime
    )
    supported_txn_types = _get_supported_txn_types(vault, effective_datetime)
    supported_fee_types = _get_supported_fee_types(vault, supported_txn_types)

    txn_types_with_params: dict[str, dict[str, str]] = utils.get_parameter(
        vault, name=PARAM_TXN_TYPES, at_datetime=accrual_cut_off_dt, is_json=True
    )

    txn_types_to_charge_interest_from_txn_date = [
        txn_type
        for txn_type, params in txn_types_with_params.items()
        if utils.str_to_bool(params.get("charge_interest_from_transaction_date", "False"))
    ]

    is_revolver = _is_revolver(in_flight_balances, denomination)

    txn_types_in_interest_free_period: dict[str, list[str]] = {}
    interest_free_expiry = utils.get_parameter(
        vault, name=PARAM_INTEREST_FREE_EXPIRY, at_datetime=accrual_cut_off_dt, is_json=True
    )
    txn_interest_free_expiry = utils.get_parameter(
        vault, name=PARAM_TXN_INTEREST_FREE_EXPIRY, at_datetime=accrual_cut_off_dt, is_json=True
    )

    for txn_type in interest_free_expiry:
        if (
            interest_free_expiry[txn_type]
            and parse(interest_free_expiry[txn_type]).replace(tzinfo=ZoneInfo("UTC"))
            > accrual_cut_off_dt
        ):
            txn_types_in_interest_free_period[txn_type] = []

    for txn_type in txn_interest_free_expiry:
        txn_types_in_interest_free_period[txn_type] = []
        for ref in txn_interest_free_expiry[txn_type]:
            if (
                txn_interest_free_expiry[txn_type][ref]
                and parse(txn_interest_free_expiry[txn_type][ref]).replace(tzinfo=ZoneInfo("UTC"))
                > accrual_cut_off_dt
            ):
                txn_types_in_interest_free_period[txn_type].append(ref.upper())

    # TODO: `accrual_instructions` is updated within function, should pass it around
    interest_accruals_by_sub_type = _accrue_interest(
        vault,
        accrual_cut_off_dt,
        denomination,
        balances,
        accrual_instructions,
        supported_txn_types,
        supported_fee_types,
        txn_types_to_charge_interest_from_txn_date,
        txn_types_in_interest_free_period,
        is_revolver,
    )

    # TODO: `accrual_instructions` is updated within function, should pass it around
    _charge_interest(
        vault,
        is_revolver,
        denomination,
        interest_accruals_by_sub_type,
        txn_types_to_charge_interest_from_txn_date,
        in_flight_balances,
        accrual_instructions,
        txn_types_in_interest_free_period,
    )

    # # Only full outstanding is affected by charged interest
    accrual_instructions.extend(
        _adjust_aggregate_balances(
            vault,
            denomination,
            in_flight_balances,
            effective_datetime,
            available=False,
            outstanding=False,
            full_outstanding=True,
        )
    )

    if accrual_instructions:
        return [
            PostingInstructionsDirective(
                posting_instructions=accrual_instructions,
                client_batch_id=f"ACCRUE_INTEREST-{vault.get_hook_execution_id()}",
                value_datetime=accrual_cut_off_dt,
            )
        ]
    else:
        return []


def _accrue_interest(
    vault: SmartContractVault,
    accrual_cut_off_dt: datetime,
    denomination: str,
    balances: BalanceDefaultDict,
    instructions: list[CustomInstruction],
    supported_txn_types: dict[str, Optional[list[str]]],
    supported_fee_types: list[str],
    txn_types_to_charge_interest_from_txn_date: list[str],
    txn_types_in_interest_free_period: dict[str, list[str]],
    is_revolver: bool,
) -> dict[tuple[str, str, str], dict[str, Decimal]]:
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

    :param vault: Vault object for the account
    :param accrual_cut_off_dt: Accrual cut-off datetime
    :param denomination: Denomination of the account
    :param balances: Account balances at the accrual cut-off
    :param instructions: In-flight CustomInstructions to extend
    :param supported_txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :param supported_fee_types: List of supported fee types
    :param txn_types_to_charge_interest_from_txn_date: List of transaction types that
    get charged interest straight away from the date of transaction
    :param txn_types_in_interest_free_period: Transaction types and refs that have
    an active interest free period
    :param is_revolver: True if account is currently revolver
    :return: Map of accrued interest by transaction type and ref
    """
    accrue_interest_on_unpaid_interest = utils.get_parameter(
        vault,
        name=PARAM_ACCRUE_INTEREST_ON_UNPAID_INTEREST,
        is_optional=True,
        is_boolean=True,
        default_value="False",
    )

    accrue_interest_on_unpaid_fees = utils.get_parameter(
        vault,
        name=PARAM_ACCRUE_INTEREST_ON_UNPAID_FEES,
        is_optional=True,
        is_boolean=True,
        default_value="False",
    )

    accrue_interest_from_txn_day = utils.get_parameter(
        vault, name=PARAM_ACCRUE_INTEREST_FROM_TXN_DAY, is_boolean=True
    )

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

    base_interest_rates: dict[str, str] = utils.get_parameter(
        vault, name=PARAM_BASE_INTEREST_RATES, at_datetime=accrual_cut_off_dt, is_json=True
    )
    txn_base_interest_rates: dict[str, dict[str, str]] = utils.get_parameter(
        vault,
        name=PARAM_TXN_BASE_INTEREST_RATES,
        at_datetime=accrual_cut_off_dt,
        is_json=True,
    )

    # upper_case_dict_values
    txn_base_interest_rates = {
        key: {str(i).upper(): str(j).upper() for i, j in value.items()}
        for key, value in txn_base_interest_rates.items()
    }

    account_creation_dt = vault.get_account_creation_datetime()
    payment_due_period = int(
        utils.get_parameter(vault, name=PARAM_PAYMENT_DUE_PERIOD, at_datetime=accrual_cut_off_dt)
    )

    # For transaction types/ refs that have an active interest free period,
    # simply don't accrue interest if we are past PDD.
    # We still want to accrue interest if we are before PDD, and the interest accrued in this case
    # will be zeroed out on PDD only if PARAM_MAD is repaid. If PARAM_MAD is not repaid, we will
    # charge the accrued interest.
    if _is_between_pdd_and_scod(vault, payment_due_period, account_creation_dt, accrual_cut_off_dt):
        base_interest_rates, txn_base_interest_rates = _determine_txns_currently_interest_free(
            txn_types_in_interest_free_period,
            base_interest_rates,
            txn_base_interest_rates,
        )

    combined_base_rates = _combine_txn_and_type_rates(txn_base_interest_rates, base_interest_rates)
    leap_year = isleap(accrual_cut_off_dt.year)
    interest_accruals_by_sub_type = _calculate_accruals_and_create_instructions(
        vault,
        balances_to_accrue_on=balances_to_accrue_on,
        denomination=denomination,
        base_interest_rates=combined_base_rates,
        instructions=instructions,
        leap_year=leap_year,
        is_revolver=is_revolver,
        txn_types_to_charge_interest_from_txn_date=txn_types_to_charge_interest_from_txn_date,
        txn_types_in_interest_free_period=txn_types_in_interest_free_period,
    )

    return interest_accruals_by_sub_type


def _get_balances_to_accrue_on(
    balances: BalanceDefaultDict,
    denomination: str,
    supported_txn_types: dict[str, Optional[list[str]]],
    supported_fee_types: list[str],
    txn_types_to_charge_interest_from_txn_date: list[str],
    accrue_interest_on_unpaid_interest: bool,
    accrue_interest_on_unpaid_fees: bool,
    txn_types_in_interest_free_period: dict[str, list[str]],
    accrue_interest_from_txn_day: bool,
) -> dict[tuple[str, str, str], dict[str, Decimal]]:
    """
    Determine which balance addresses we need to accrue on and the corresponding amounts.
    Accruals are required if:
     - Customer is revolver and interest is charged daily
     - OR there is outstanding statement balance, and we need to start accruing in case repayment
       is missed and interest is retrospectively charged
     - OR there are transaction types that are marked out to be charged interest from the
       transaction date, and they are not in active interest free periods

    :param balances: Account balances at the accrual cut-off
    :param denomination: Denomination of the account
    :param supported_txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :param supported_fee_types: The fee types supported by the account
    :param txn_types_to_charge_interest_from_txn_date: List of transaction types that
    get charged interest straight away from the date of transaction
    :param accrue_interest_on_unpaid_interest: True if interest is to be accrued on unpaid interest
    :param accrue_interest_on_unpaid_fees: True if interest is to be accrued on unpaid fees
    :param txn_types_in_interest_free_period: Transaction types and refs that have an active
    interest free period
    :param accrue_interest_from_txn_day: Marks the interest accrual approach in this product
    :return: map of transaction type -> map of transaction ref ('' if no ref) -> balance to accrue
    on
    """
    balances_to_accrue_on: dict = {}
    outstanding_statement_amount = _get_outstanding_statement_amount(
        balances, denomination, supported_fee_types, supported_txn_types
    )

    def _update_balances_to_accrue_on(
        charge_type: str, sub_type: str, ref: Optional[str] = None
    ) -> None:
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

        amount_to_accrue_on = Decimal(
            sum(
                [
                    balance.net
                    for dimensions, balance in balances.items()
                    if dimensions[0] in addresses_to_accrue_on
                ]
            )
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
            billed_amount_to_accrue_on = Decimal(
                sum(
                    [
                        balance.net
                        for dimensions, balance in balances.items()
                        if dimensions[0] in addresses_to_accrue_on
                        and dimensions[0].endswith(BILLED)
                    ]
                )
            )
            # <transaction_type>_CHARGED accrues to <transaction_type>_INTEREST_PRE_SCOD_UNCHARGED
            charged_amount_to_accrue_on = Decimal(
                sum(
                    [
                        balance.net
                        for dimensions, balance in balances.items()
                        if dimensions[0] in addresses_to_accrue_on
                        and dimensions[0].endswith(CHARGED)
                    ]
                )
            )
            _set_accruals_by_sub_type(
                balances_to_accrue_on,
                charge_type=charge_type,
                sub_type=sub_type,
                accrual_amount=billed_amount_to_accrue_on,
                ref=ref,
                accrual_type=POST_SCOD,
            )
            _set_accruals_by_sub_type(
                balances_to_accrue_on,
                charge_type=charge_type,
                sub_type=sub_type,
                accrual_amount=charged_amount_to_accrue_on,
                ref=ref,
                accrual_type=PRE_SCOD,
            )

        else:
            _set_accruals_by_sub_type(
                balances_to_accrue_on,
                charge_type=charge_type,
                sub_type=sub_type,
                accrual_amount=amount_to_accrue_on,
                ref=ref,
            )

    # Accrue interest on all balances if we are in revolver, or if the account is projected to go
    # into revolver by next PDD
    # We will decide further down whether the interest is accrued to UNCHARGED address or CHARGED
    # directly
    accrue_on_all_balances = (
        _is_revolver(balances, denomination) or outstanding_statement_amount > 0
    )
    for txn_type, refs in supported_txn_types.items():
        for ref in refs or [""]:
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
    vault: SmartContractVault,
    balances_to_accrue_on: dict[tuple[str, str, str], dict[str, Decimal]],
    denomination: str,
    base_interest_rates: dict[str, str],
    instructions: list[CustomInstruction],
    leap_year: bool,
    is_revolver: bool,
    txn_types_to_charge_interest_from_txn_date: list[str],
    txn_types_in_interest_free_period: dict[str, list[str]],
) -> dict[tuple[str, str, str], dict[str, Decimal]]:
    """
    Calculate the interest to accrue on each transaction type and create corresponding postings,
    unless the interest will be charged immediately anyway

    :param vault: Vault object for the account
    :param balances_to_accrue_on: Map of ref (or empty string) to amount to accrue on, mapped to
    transaction type.
    :param denomination: Denomination of the account
    :param base_interest_rates: Txn type to gross annual interest rate
    :param instructions: In-flight postings to be extended by this method
    :param leap_year: True if interest value date is on leap year
    :param is_revolver: True if account is currently revolver and interest should be charged
    immediately, unless the txn type has an active interest free period
    :param txn_types_to_charge_interest_from_txn_date: List of transaction types that get charged
    interest straight away from the date of transaction
    :param txn_types_in_interest_free_period: Txn types/ refs for which we enforce accruals to be
    strictly on a specific address ending with
    INTEREST_FREE_PERIOD_UNCHARGED, so that it will be possible to reverse this charge on PDD
    given that the PARAM_MAD is repaid
    :return: Transaction type to accrual amounts
    """
    interest_by_charge_sub_and_accrual_type: dict[tuple[str, str, str], dict[str, Decimal]] = {}

    def _create_accrual_instructions(
        charge_type: str,
        sub_type: str,
        amount: Decimal,
        ref: Optional[str] = None,
        accrual_type: Optional[str] = None,
    ) -> None:
        """
        Create accrual instructions for transaction type provided

        :param charge_type: One of PRINCIPAL, FEES or INTEREST
        :param sub_type: Transaction or fee type
        :param amount: Amount to accrue on
        :param ref: Transaction level reference
        :param accrual_type: Either '', PRE_SCOD or POST_SCOD applicable for interest accrual
        to _UNCHARGED balances from txn day
        """
        stem = f"{sub_type}_{ref}" if ref else sub_type
        interest_stem = stem if charge_type != FEES else FEES

        daily_rate = yearly_to_daily_rate(
            Decimal(base_interest_rates[interest_stem.lower()]), leap_year
        )
        accrual_amount = utils.round_decimal(daily_rate * amount, decimal_places=2)
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
                    charge_type=charge_type,
                    sub_type=sub_type,
                    accrual_amount=accrual_amount,
                    ref=ref,
                    accrual_type=accrual_type,
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
                    "description": f"Daily interest accrued at {daily_rate_percent:.7f}%% on "
                    f"balance of {abs(amount):.2f}, for transaction type {stem_with_accrual_type}"
                }
                instructions.extend(
                    _make_accrual_posting(
                        vault,
                        accrual_amount,
                        denomination,
                        stem,
                        instruction_details=instruction_details,
                        accrual_type=accrual_type,
                    )
                )

    for charge_and_sub_and_accrual_type, ref_to_amount in balances_to_accrue_on.items():
        charge_type = charge_and_sub_and_accrual_type[0]
        sub_type = charge_and_sub_and_accrual_type[1]
        accrual_type = charge_and_sub_and_accrual_type[2]
        for ref, amount in ref_to_amount.items():
            _create_accrual_instructions(charge_type, sub_type, amount, ref, accrual_type)

    return interest_by_charge_sub_and_accrual_type


def _make_accrual_posting(
    vault: SmartContractVault,
    accrual_amount: Decimal,
    denomination: str,
    stem: str,
    instruction_details: Optional[dict[str, str]] = None,
    reverse: bool = False,
    accrual_type: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Creates posting instructions for interest accrual

    :param vault: Vault object for the account
    :param accrual_amount: Amount to accrue
    :param denomination: Denomination of the account
    :param stem: Transaction type being accrued on (with reference appended if present)
    :param instruction_details: metadata to attach to the posting instructions
    :param reverse: Set to True to reverse interest accrual (e.g. zeroing out accrued interest)
    :param accrual_type: Either '' or PRE_SCOD or POST_SCOD applicable for interest
    accrual to _UNCHARGED balances from txn day
    :return: List of CustomInstructions to accrue interest
    """
    return _make_internal_address_transfer(
        amount=abs(accrual_amount),
        denomination=denomination,
        credit_internal=not reverse,
        custom_address=_interest_address(stem, UNCHARGED, accrual_type=accrual_type),
        instruction_details=instruction_details,
        vault=vault,
    )


def yearly_to_daily_rate(yearly_rate: Decimal, leap_year: bool) -> Decimal:
    """
    Convert a yearly rate to daily rate, accounting for leap years

    :param yearly_rate: Gross yearly interest rate
    :param leap_year: True if is a leap year
    :return: Daily interest rate
    """
    days_in_year = 366 if leap_year else 365

    return utils.round_decimal(yearly_rate / days_in_year, decimal_places=10)


def _get_first_scod(account_creation_datetime: datetime) -> tuple[datetime, datetime]:
    """
    Calculates first SCOD using account creation date

    :param account_creation_datetime: UTC account creation date
    :return: Start date and end date for SCOD
    """

    account_creation_datetime_midnight = account_creation_datetime.replace(
        hour=0, minute=0, second=0
    )
    scod_start = (
        account_creation_datetime_midnight + relativedelta(months=1) - relativedelta(days=1)
    )
    return scod_start, scod_start + relativedelta(days=1)


def _get_previous_scod(
    vault: SmartContractVault,
    account_creation_datetime: datetime,
) -> tuple[datetime, datetime]:
    """
    Determines the last scod before the current datetime.

    :param vault: Vault object for the account
    :param account_creation_datetime: UTC account creation date
    :return:  UTC start and end of last SCOD. If no SCOD has taken place
    both will be equal to account_creation_datetime
    """

    last_scod_execution_time = vault.get_last_execution_datetime(event_type=EVENT_SCOD)
    if last_scod_execution_time:
        prev_scod_end = last_scod_execution_time - relativedelta(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        prev_scod_start = prev_scod_end - relativedelta(days=1)
    else:
        # If an account is closed before first SCOD, we use the account creation date
        prev_scod_end = account_creation_datetime
        prev_scod_start = account_creation_datetime

    return prev_scod_start, prev_scod_end


def _get_first_pdd(
    payment_due_period: int, first_scod_start: datetime
) -> tuple[datetime, datetime]:
    """
    Calculates first Payment Due Date (PDD) on the basis of the first Statement Cut-Off
    Date (SCOD) where PDD(0) = SCOD(0) + Payment Due Period.

    :param payment_due_period: Number of days between SCOD and PDD
    :param first_scod_start: Datetime of the first SCOD event
    :return: Start of PDD, end of PDD
    """

    first_pdd_start = first_scod_start + relativedelta(days=payment_due_period)
    return first_pdd_start, first_pdd_start + relativedelta(days=1)


def _get_next_pdd(
    payment_due_period: int,
    account_creation_datetime: datetime,
    last_pdd_execution_datetime: Optional[datetime] = None,
) -> tuple[datetime, datetime]:
    """
    Calculate next PDD, maintaining the day of the month of the first PDD. If PDD schedule has
    never been executed (last_pdd_execution_datetime is None), this will return the first PDD.

    :param payment_due_period: Number of days between SCOD and PDD
    :param account_creation_datetime: UTC account opening datetime
    :param last_pdd_execution_datetime: UTC last pdd logical execution time
    :return: Start of next PDD, end of next PDD.
    """

    # always calculate next PDD from first PDD to preserve the day of month where possible. We must
    # perform calculations with localised datetime as a result, and then delocalise if requested
    first_scod_start, _ = _get_first_scod(account_creation_datetime)
    first_pdd_start, first_pdd_end = _get_first_pdd(payment_due_period, first_scod_start)

    # if PDD hasn't ever executed, the next PDD must be the first PDD
    if last_pdd_execution_datetime is None:
        return first_pdd_start, first_pdd_end
    # PDD schedule runs at the end of the actual PDD

    last_pdd_start = last_pdd_execution_datetime - relativedelta(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
        days=1,
    )

    # Add 1 as the calculation uses last pdd and first pdd but we want delta to next pdd
    month_delta = (
        1
        + last_pdd_start.month
        - first_pdd_start.month
        + 12 * (last_pdd_start.year - first_pdd_start.year)
    )
    next_pdd_start = first_pdd_start + relativedelta(months=month_delta)

    return next_pdd_start, next_pdd_start + relativedelta(days=1)


def _get_scod_for_pdd(payment_due_period: int, pdd_start: datetime) -> tuple[datetime, datetime]:
    """
    Calculates SCOD for a given PDD by subtracting payment due period from PDD.

    :param payment_due_period: Number representing the day difference between SCOD and PDD
    :param pdd_start: Start of payment due date.
    :return: Start of SCOD, end of SCOD
    """

    scod_start = pdd_start - relativedelta(days=payment_due_period)

    return scod_start, scod_start + relativedelta(days=1)


def _is_between_pdd_and_scod(
    vault: SmartContractVault,
    payment_due_period: int,
    account_creation_datetime: datetime,
    current_datetime: datetime,
) -> bool:
    """
    Determines whether we are after or before the PDD in the current statement cycle.
    There is no PDD in the first statement cycle, we will return false if current_date is within
    first statement cycle.

    :param vault: Vault object for the account
    :param payment_due_period: Number of days between SCOD and PDD
    :param account_creation_datetime: UTC account creation datetime
    :param current_datetime: UTC datetime at which the check happens
    :return: True if we are after the PDD in the current statement cycle, and False if not
    """

    _, previous_scod = _get_previous_scod(vault, account_creation_datetime)

    if previous_scod == account_creation_datetime:
        # We are within one month of account creation, there hasn't been a PDD yet.
        return False

    return previous_scod < current_datetime - relativedelta(days=payment_due_period)


def _charge_annual_fee(
    vault: SmartContractVault, effective_datetime: datetime
) -> list[PostingInstructionsDirective]:
    """
    Create postings to charge annual fee if set.

    :param vault: Vault object for the account
    :param effective_datetime: Datetime of when the annual fee is being charged
    :return: The annual fee posting instruction directive
    """
    instructions: list[CustomInstruction] = []
    denomination = utils.get_parameter(
        name=PARAM_DENOMINATION, at_datetime=effective_datetime, vault=vault
    )
    credit_limit = utils.get_parameter(
        name=PARAM_CREDIT_LIMIT, at_datetime=effective_datetime, vault=vault
    )
    in_flight_balances = _deep_copy_balances(
        vault.get_balances_observation(fetcher_id=LIVE_BALANCES_BOF_ID).balances
    )

    annual_fee, fee_posting_instructions = _charge_fee(
        vault,
        denomination,
        in_flight_balances=in_flight_balances,
        fee_type=ANNUAL_FEE,
    )

    instructions.extend(fee_posting_instructions)
    if annual_fee == 0:
        return []

    instructions.extend(
        _adjust_aggregate_balances(
            vault,
            denomination,
            in_flight_balances,
            effective_datetime,
            credit_limit=credit_limit,
        )
    )
    if instructions:
        return [
            PostingInstructionsDirective(
                posting_instructions=instructions,
                client_batch_id=f"{ANNUAL_FEE}-{vault.get_hook_execution_id()}",
                value_datetime=effective_datetime,
            )
        ]
    else:
        return []


def _process_statement_cut_off(
    vault: SmartContractVault,
    effective_datetime: datetime,
    in_flight_balances: Optional[BalanceDefaultDict] = None,
    is_final: bool = False,
) -> tuple[list[AccountNotificationDirective], list[PostingInstructionsDirective]]:
    """
    Statement cut off event:
     - move 'CHARGED' balances to 'BILLED'
     - move 'INTEREST_PRE_SCOD_UNCHARGED' balances to 'INTEREST_POST_SCOD_UNCHARGED'
     - charge overlimit fees if applicable
     - adjust aggregate balances
     - trigger statement workflow with data for integration services

    :param vault: Vault object for the account
    :param effective_datetime: Datetime of the SCOD schedule
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution. This should always be populated
    when called outside of a SCOD schedule execution (e.g. during closure)
    :param is_final: Set to true if generating the final statement
    :return: Directives to commit
    """
    # Take balances from SCOD effective date minus a microsecond to capture all transactions
    # up until that point. For example, if we assume the schedule is run at SCOD+1T00:00:00,
    # all balances up until SCOD T23:59:59.99999 are included in the statement.
    # This includes interest accrual
    if is_final:
        scod_cut_off_dt = effective_datetime
        scod_effective_dt = effective_datetime
    else:
        scod_effective_dt = effective_datetime - relativedelta(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        scod_cut_off_dt = scod_effective_dt - relativedelta(
            microseconds=1,
        )

    # May already be initialised if statement processing is triggered by write-off
    if in_flight_balances is None:
        balances = BalanceDefaultDict()
        balances.update(
            {
                coord: ts.at(at_datetime=scod_cut_off_dt)
                for coord, ts in vault.get_balances_timeseries(
                    fetcher_id=STATEMENT_CUTOFF_TO_LIVE_BALANCES_BIF_ID
                ).items()
            }
        )
        in_flight_balances = _deep_copy_balances(balances)

    denomination = utils.get_parameter(
        name=PARAM_DENOMINATION, at_datetime=scod_effective_dt, vault=vault
    )
    credit_limit = utils.get_parameter(
        name=PARAM_CREDIT_LIMIT, at_datetime=scod_effective_dt, vault=vault
    )
    supported_txn_types = _get_supported_txn_types(vault, scod_effective_dt)
    supported_fee_types = _get_supported_fee_types(vault, supported_txn_types)

    # Find out whether we accrue interest from transaction day, for later checks
    accrue_interest_from_txn_day = _is_txn_interest_accrual_from_txn_day(vault)

    txn_types_with_params = utils.get_parameter(
        vault, name=PARAM_TXN_TYPES, at_datetime=effective_datetime, is_json=True
    )

    txn_types_to_charge_interest_from_txn_date = [
        txn_type
        for txn_type, params in txn_types_with_params.items()
        if utils.str_to_bool(params.get("charge_interest_from_transaction_date", "False"))
    ]

    # some instructions must be effective as of just before end of SCOD (e.g. over-limit fee) to
    # fall in the statement, so we group them based on their value timestamp
    instructions_ts: dict[datetime, list[CustomInstruction]] = {
        scod_cut_off_dt: [],
        scod_effective_dt: [],
    }
    # Overlimit fee is charged as of balances cut-off as it should be included in SCOD
    # in_flight_balances is directly modified inside this function
    instructions_ts[scod_cut_off_dt].extend(
        _charge_overlimit_fee(
            vault,
            in_flight_balances,
            denomination,
            supported_txn_types,
            credit_limit,
        )
    )

    instructions_ts[scod_effective_dt].extend(
        _bill_charged_txns_and_bank_charges(
            vault,
            supported_txn_types,
            denomination,
            in_flight_balances,
            credit_limit,
        )
    )

    if accrue_interest_from_txn_day and not is_final:
        instructions_ts[scod_effective_dt].extend(
            _adjust_interest_uncharged_balances(
                vault,
                supported_txn_types,
                txn_types_to_charge_interest_from_txn_date,
                denomination,
                in_flight_balances,
            )
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
        mad_eq_statement=utils.is_flag_in_list_applied(
            vault=vault,
            parameter_name=PARAM_MAD_AS_STATEMENT_FLAGS,
            effective_datetime=scod_effective_dt,
        ),
    )

    instructions_ts[scod_effective_dt].extend(
        _update_info_balances(
            vault,
            in_flight_balances,
            denomination,
            total_statement_amount,
            mad,
        )
    )

    # effective datetime <-> live changes handling is for schedules, so we do not apply this for
    # final statement generation from deactivation hook or elsewhere.
    if not is_final:
        # instructions_ts is directly modified inside this function
        _handle_live_balance_changes(vault, denomination, scod_cut_off_dt, instructions_ts)

    posting_directives: list[PostingInstructionsDirective] = []

    for index, (value_timestamp, instruction_list) in enumerate(instructions_ts.items()):
        if instruction_list:
            posting_directives.append(
                PostingInstructionsDirective(
                    posting_instructions=instruction_list,
                    client_batch_id=f"SCOD_{index}-{vault.get_hook_execution_id()}",
                    value_datetime=value_timestamp,
                )
            )

    notification_directives: list[AccountNotificationDirective] = []
    notification_directives.append(
        _create_statement_notification(
            vault, scod_effective_dt, total_statement_amount, mad, is_final
        )
    )

    return notification_directives, posting_directives


def _adjust_interest_uncharged_balances(
    vault: SmartContractVault,
    supported_txn_types: dict[str, Optional[list[str]]],
    txn_types_to_charge_interest_from_txn_date: list[str],
    denomination: str,
    in_flight_balances: BalanceDefaultDict,
) -> list[CustomInstruction]:
    """
    Rebalances uncharged interest balances. Flow at SCOD for non revolver accounts is :
    <transaction_type>_INTEREST_PRE_SCOD_UNCHARGED moves to
    <transaction_type>_INTEREST_POST_SCOD_UNCHARGED

    :param vault: Vault object for the account
    :param supported_txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :param txn_types_to_charge_interest_from_txn_date: List of transaction types that get charged
    interest straight away from the date of transaction
    :param denomination: Denomination of the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :return: CustomInstructions to rebalance the uncharged interest
    """

    uncharged_adjustment_postings = []

    for txn_type, refs in supported_txn_types.items():
        if txn_type.lower() not in txn_types_to_charge_interest_from_txn_date:
            for txn_ref in refs or [""]:
                from_balance_address = _interest_address(
                    txn_type, UNCHARGED, txn_ref=txn_ref, accrual_type=PRE_SCOD
                )
                to_balance_address = _interest_address(
                    txn_type, UNCHARGED, txn_ref=txn_ref, accrual_type=POST_SCOD
                )
                _, rebalance_postings = _rebalance_balance_buckets(
                    vault,
                    in_flight_balances,
                    from_balance_address,
                    to_balance_address,
                    denomination,
                )
                uncharged_adjustment_postings.extend(rebalance_postings)

    return uncharged_adjustment_postings


def _bill_charged_txns_and_bank_charges(
    vault: SmartContractVault,
    supported_txn_types: dict[str, Optional[list[str]]],
    denomination: str,
    in_flight_balances: BalanceDefaultDict,
    credit_limit: Decimal,
) -> list[CustomInstruction]:
    """
    Determine what is billed for this statement cycle and create corresponding posting instructions

    :param vault: Vault object for the account
    :param supported_txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :param denomination: Denomination of the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param credit_limit: Account credit limit at SCOD cut-off
    :return: List of CustomInstructions at SCOD cut-off to bill charged transactions
    """

    scod_instructions = []

    def _construct_statement_breakdown(
        sub_type: str, charge_type: str, txn_ref: Optional[str] = None
    ) -> None:
        """
        Create addresses on a per-charge-type basis, calculate amount and add to Dict for return
        :param sub_type: Transaction or fee type
        :param charge_type: Type of transaction (BILLED etc)
        :param txn_ref: Transaction level reference
        """
        if charge_type == PRINCIPAL:
            from_balance_address = _principal_address(sub_type, CHARGED, txn_ref=txn_ref)
            to_balance_address = _principal_address(sub_type, BILLED, txn_ref=txn_ref)
        elif charge_type == FEES:
            from_balance_address = _fee_address(fee_type=sub_type, fee_status=CHARGED)
            to_balance_address = _fee_address(fee_type=sub_type, fee_status=BILLED)

        _, rebalance_postings = _rebalance_balance_buckets(
            vault=vault,
            in_flight_balances=in_flight_balances,
            debit_address=from_balance_address,  # type: ignore
            credit_address=to_balance_address,  # type: ignore
            denomination=denomination,
        )
        scod_instructions.extend(rebalance_postings)

    for txn_type, refs in supported_txn_types.items():
        for ref in refs or [""]:
            _construct_statement_breakdown(txn_type, PRINCIPAL, txn_ref=ref)

    # Bill charged Fees
    supported_fee_types = _get_supported_fee_types(vault, supported_txn_types)
    for fee_type in supported_fee_types:
        _construct_statement_breakdown(fee_type, FEES)

    scod_instructions.extend(
        _bill_charged_interest(
            vault,
            supported_fee_types,
            supported_txn_types,
            denomination,
            in_flight_balances,
        )
    )

    # Charged interest that has just been billed was not previously deducted from available balance
    scod_instructions.extend(
        _adjust_aggregate_balances(
            vault,
            denomination,
            in_flight_balances,
            outstanding=False,
            full_outstanding=False,
            credit_limit=credit_limit,
        )
    )
    return scod_instructions


def _bill_charged_interest(
    vault: SmartContractVault,
    supported_fee_types: list[str],
    supported_txn_types: dict[str, Optional[list[str]]],
    denomination: str,
    in_flight_balances: BalanceDefaultDict,
) -> list[CustomInstruction]:
    """
    Creates instructions to move spend from transaction_type_INTEREST_CHARGED to
    transaction_type_INTEREST_BILLED at SCOD. Also makes postings to DEFAULT balance so that
    available balance is affected.

    :param vault: Vault object for the account
    :param supported_fee_types: List of supported fee types
    :param supported_txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :param denomination: Denomination of the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :return: CustomInstructions to bill charged interest
    """

    billed_posting_instructions = []

    def move_interest_to_billed(sub_type: str, txn_ref: Optional[str] = None) -> None:
        """
        Move interest from charged to billed address
        :param sub_type: Transaction or fee type
        :param txn_ref: Optional transaction level reference
        """
        # TODO: notify inception about these changes
        from_balance_address = _interest_address(sub_type, CHARGED, txn_ref=txn_ref)
        to_balance_address = _interest_address(sub_type, BILLED, txn_ref=txn_ref)

        _, rebalance_postings = _rebalance_balance_buckets(
            vault=vault,
            in_flight_balances=in_flight_balances,
            debit_address=from_balance_address,
            credit_address=to_balance_address,
            denomination=denomination,
        )

        billed_posting_instructions.extend(rebalance_postings)

    for txn_type, txn_refs in supported_txn_types.items():
        for txn_ref in txn_refs or [""]:
            move_interest_to_billed(
                sub_type=txn_type,
                txn_ref=txn_ref,
            )

    for fee_type in supported_fee_types:
        move_interest_to_billed(sub_type=fee_type)

    return billed_posting_instructions


def _update_info_balances(
    vault: SmartContractVault,
    in_flight_balances: BalanceDefaultDict,
    denomination: str,
    statement_amount: Decimal,
    mad: Decimal,
) -> list[CustomInstruction]:
    """
    Create the posting instructions required to update statement info balances (statement,
    outstanding, full outstanding, mad) and reset total repayments balance.

    :param vault: Vault object for the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param denomination: Denomination of the account
    :param statement_amount: Nw statement amount
    :param mad: Minimum amount due for the new statement
    :return: CustomInstructions to update the info balances
    """

    info_balance_postings = []

    # Update statement, outstanding and full outstanding balances with new amount
    for info_balance in [
        STATEMENT_BALANCE,
        OUTSTANDING_BALANCE,
        FULL_OUTSTANDING_BALANCE,
    ]:
        info_balance_postings.extend(
            _override_info_balance(
                vault,
                in_flight_balances,
                info_balance,
                denomination,
                statement_amount,
            )
        )

    info_balance_postings.extend(
        _override_info_balance(
            vault,
            in_flight_balances,
            TRACK_STATEMENT_REPAYMENTS,
            denomination,
            Decimal(0),
        )
    )
    info_balance_postings.extend(
        _override_info_balance(vault, in_flight_balances, MAD_BALANCE, denomination, mad)
    )

    return info_balance_postings


def _handle_live_balance_changes(
    vault: SmartContractVault,
    denomination: str,
    cut_off_datetime: datetime,
    instructions_timeseries: dict[datetime, list[CustomInstruction]],
) -> None:
    """
    Ensures that post-schedule balances are consistent even balances have changed since cut-off

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param cut_off_datetime: Cut-off for the schedule. This will help determine if live balances
    changed after the cut-off, in which case there may be inconsistencies
    :param instructions_timeseries: CustomInstructions to be made as part of PDD processing,
    updated with postings to handle live balance change
    :return: None
    """

    balance_coord_to_ts_dict = vault.get_balances_timeseries(
        fetcher_id=STATEMENT_CUTOFF_TO_LIVE_BALANCES_BIF_ID
    )
    # start live_balance_dt comparison at effective_datetime
    live_balance_dt = cut_off_datetime
    live_balances = BalanceDefaultDict()
    for coord, balance_ts in balance_coord_to_ts_dict.items():
        tsItem = balance_ts.all()[-1]
        live_ts_item_dt = tsItem.at_datetime
        live_ts_item_value = tsItem.value
        live_balances.update({coord: live_ts_item_value})

        # live_balance_dt could be < effective_datetime if there have been no postings recently
        # live_balance_dt could be > effective_datetime if there have been postings after eff_date
        # want to take the latest possible timestamp out of effective_datetime/any live_balance_dt
        live_balance_dt = max(live_balance_dt, live_ts_item_dt)

    in_flight_live_balances = _deep_copy_balances(live_balances)
    for instructions in instructions_timeseries.values():
        _update_balances(vault.account_id, in_flight_live_balances, instructions)  # type: ignore

    # it's possible that cut_off balances are live balances, in which case we don't want to
    # do anything
    if live_balance_dt > cut_off_datetime:
        balance_pairs = (CHARGED, BILLED)
        clean_up_postings = _clean_up_balance_inconsistencies(
            vault, denomination, in_flight_live_balances, balance_pairs
        )

        if live_balance_dt in instructions_timeseries:
            instructions_timeseries[live_balance_dt].extend(clean_up_postings)
        else:
            instructions_timeseries[live_balance_dt] = clean_up_postings


def _clean_up_balance_inconsistencies(
    vault: SmartContractVault,
    denomination: str,
    updated_live_balances: BalanceDefaultDict,
    address_suffix_pair: tuple[str, str],
) -> list[CustomInstruction]:
    """
    Given a pair of balance suffixes (e.g. _CHARGED and _BILLED), determines whether the updated
    live balances have any inconsistencies and creates the postings to address them. These postings
    should be instructed as of the live_balance datetime.

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param updated_live_balances: Account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param address_suffix_pair: Pair of suffixes to correct inconsistencies for. The addresses with
    the first suffix will be debited and the addresses with the second suffix will be credited to
    correct any detected inconsistencies.
    :return: Correction CustomInstructions
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

    for address_stem in address_stems:
        debit_address = _principal_address(address_stem, suffix_1)
        from_amount = utils.balance_at_coordinates(
            balances=updated_live_balances, address=debit_address, denomination=denomination
        )
        # we always expect the balances to be +ve, so if they are -ve we must clean-up
        if from_amount < 0:
            credit_address = _principal_address(address_stem, suffix_2)
            to_amount = utils.balance_at_coordinates(
                balances=updated_live_balances, address=credit_address, denomination=denomination
            )
            rectified_amount = min(abs(to_amount), abs(from_amount))
            if rectified_amount > 0:
                clean_up_instructions.extend(
                    _move_funds_internally(
                        vault,
                        rectified_amount,
                        debit_address,
                        credit_address,
                        denomination,
                        in_flight_balances=None,
                    )
                )

    return clean_up_instructions


def _create_statement_notification(
    vault: SmartContractVault,
    statement_end: datetime,
    final_statement: Decimal,
    mad: Decimal,
    is_final: bool,
) -> AccountNotificationDirective:
    """
    Creates a statement notification directive with required context.

    :param vault: Vault object for the account
    :param statement_end: UTC end of the statement period, exclusive. For
    example, if SCOD is on 2020-02-03T16:00:00Z, end of SCOD is 2020-02-04T16:00:00Z. For final
    statements, no adjustments are needed.
    :param final_statement: Statement balance
    :param mad: Minimum amount due
    :param is_final: True when this is the final statement
    :return: Statement notification directive
    """

    account_creation_dt = vault.get_account_creation_datetime()
    payment_due_period = int(
        utils.get_parameter(
            name=PARAM_PAYMENT_DUE_PERIOD, at_datetime=account_creation_dt, vault=vault
        )
    )
    _, prev_scod_end = _get_previous_scod(vault, account_creation_dt)
    local_statement_end = statement_end
    local_prev_statement_end = prev_scod_end
    if not is_final:
        last_pdd_execution_datetime = vault.get_last_execution_datetime(event_type=EVENT_PDD)
        # get_last_execution_datetime() excludes the current scod execution, so _get_next_pdd
        # actually returns the pdd for the current scod
        current_pdd_start, current_pdd_end = _get_next_pdd(
            payment_due_period,
            account_creation_dt,
            last_pdd_execution_datetime,
        )
        current_pdd_execution_datetime = current_pdd_end
        next_pdd_start, _ = _get_next_pdd(
            payment_due_period,
            account_creation_dt,
            current_pdd_execution_datetime,
        )
        next_scod_start, _ = _get_scod_for_pdd(payment_due_period, next_pdd_start)

        # notification end of statement refers to SCOD, but we typically consider statement to end
        # at end of SCOD
        local_statement_end -= relativedelta(days=1)

    # The notification provides the dates of the SCOD/PDD/Next SCOD, which will always be one day
    # prior to the actual schedules
    return AccountNotificationDirective(
        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
        notification_details={
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
    vault: SmartContractVault,
    in_flight_balances: BalanceDefaultDict,
    balance_address: str,
    denomination: str,
    amount: Decimal,
) -> list[CustomInstruction]:
    """
    Set a specific balance to an absolute amount.

    :param vault: Vault object for the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param balance_address: The info address
    :param denomination: Denomination of the account
    :param amount: The new absolute balance amount
    :return: CustomInstructions to update the info address
    """
    current_balance = utils.balance_at_coordinates(
        balances=in_flight_balances, address=balance_address, denomination=denomination
    )
    if current_balance == amount:
        return []

    # If the new amount is more than the old amount that is a +ve on the address
    # So a -ve on the internal, which is a credit for an asset
    credit_internal = amount > current_balance
    return _make_internal_address_transfer(
        custom_address=balance_address,
        credit_internal=credit_internal,
        denomination=denomination,
        amount=Decimal(abs(amount - current_balance)),
        instruction_details={"description": f"Set {balance_address} to {amount:.2f}"},
        vault=vault,
        in_flight_balances=in_flight_balances,
    )


def _get_outstanding_statement_amount(
    balances: BalanceDefaultDict,
    denomination: str,
    fee_types: list[str],
    txn_types: dict[str, Optional[list[str]]],
) -> Decimal:
    """
    Calculates current outstanding statement amount by summing all principal and bank charges
    statement balances. Note that outstanding statement amount = statement amount when run during
    the statement cut-off calculations.

    :param balances: The account balances to use when calculating the outstanding statement amount
    :param denomination: Denomination of the account
    :param fee_types: Fee types supported by the account
    :param txn_types:  Map of supported transaction types (txn_type to txn_level_refs)
    :return: The outstanding statement amount. Will be +ve if the account has deposit > 0
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
    vault: SmartContractVault,
    in_flight_balances: BalanceDefaultDict,
    denomination: str,
    txn_types: dict[str, Optional[list[str]]],
    effective_datetime: datetime,
    statement_amount: Decimal,
    mad_eq_statement: bool = False,
) -> Decimal:
    """
    Calculate the PARAM_MAD for the current statement. This is usually the greatest of the fixed and
    percentage-based PARAM_MAD (see _calculate_percentage_mad),
    ensuring that PARAM_MAD <= statement.
     A few exceptions apply:
    - if the statement amount is negative (i.e. deposit balance), the PARAM_MAD is 0
    - if there is an active flag amongst mad_equal_to_zero_flags, the PARAM_MAD is 0
    - otherwise, the PARAM_MAD can be set to be equal to statement amount via the mad_eq_statement
    flag (e.g. last statement before closure)

    :param vault: Vault object for the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param denomination: Denomination of the account
    :param txn_types:  Map of supported transaction types (txn_type to txn_level_refs)
    :param effective_datetime: Datetime of SCOD end
    :param statement_amount: The full statement amount
    :param mad_eq_statement: If True the PARAM_MAD is set to the full statement amount
    :return: The Minimum Amount Due for the latest statement, >= 0 and rounded to 2 dp
    """

    # If we have a negative statement amount due to over repayments PARAM_MAD should be 0.
    # We also return 0 in the PARAM_MAD calculation if indicated by the relevant flag, e.g. if
    # there is an active repayment holiday.
    if statement_amount <= 0 or utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_MAD_EQUAL_TO_ZERO_FLAGS,
        effective_datetime=effective_datetime,
    ):
        return Decimal(0)
    elif mad_eq_statement:
        return statement_amount

    fee_types = _get_supported_fee_types(vault, txn_types)
    mad_percentages = utils.get_parameter(
        vault, name=PARAM_MINIMUM_PERCENTAGE_DUE, at_datetime=effective_datetime, is_json=True
    )
    fixed_mad = utils.get_parameter(vault, name=PARAM_MAD, at_datetime=effective_datetime)
    credit_limit = utils.get_parameter(
        vault, name=PARAM_CREDIT_LIMIT, at_datetime=effective_datetime
    )

    percentage_mad = _calculate_percentage_mad(
        in_flight_balances,
        denomination,
        mad_percentages,
        txn_types,
        fee_types,
        credit_limit,
    )

    mad = max(percentage_mad, fixed_mad)

    # Cap PARAM_MAD to the statement balance as customer can't repay more than what is owed
    mad = min(mad, statement_amount)

    return utils.round_decimal(mad, 2)


def _calculate_percentage_mad(
    in_flight_balances: BalanceDefaultDict,
    denomination: str,
    mad_percentages: dict[str, Decimal],
    txn_types: dict[str, Optional[list[str]]],
    fee_types: list[str],
    credit_limit: Decimal,
) -> Decimal:
    """
    Calculate PARAM_MAD based on statement amounts and mad percentages. Interest and Fees
    percentages are hardcoded to 100%. 100% of overdue/overlimit amount (whichever is greater)
    is also added.

    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param denomination: Denomination of the account
    :param mad_percentages: Mad percentages per transaction type
    :param txn_types:  Map of supported transaction types (txn_type to txn_level_refs)
    :param fee_types: Supported fee types
    :param credit_limit: The credit limit for the account. Used to determine the overlimit amount
    :return: The minimum amount due
    """
    mad = Decimal(0)

    overlimit_amount = _get_overlimit_amount(
        in_flight_balances, credit_limit, denomination, txn_types
    )
    overdue_amount = sum(_get_overdue_balances(in_flight_balances).values())

    # Full overdue or overlimit, whichever is greatest (they are both +ve numbers)
    mad += max(overdue_amount, overlimit_amount)

    def get_mad_component(
        charge_type: str, percentage: Decimal, sub_type: str, txn_ref: Optional[str] = None
    ) -> Decimal:
        """
        calculate the contribution towards PARAM_MAD of a specific component sub-type
        :param charge_type: str, PRINCIPAL, INTEREST or FEES
        :param percentage: Decimal, the percentage of the component sub-type that should be included
        in the PARAM_MAD
        :param sub_type: str, the component sub-type (e.g. for PRINCIPAL this might be PURCHASE)
        :param txn_ref: Optional[str], transaction level reference
        :return: Decimal, the contribution towards PARAM_MAD of a specific component sub-type
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

        unpaid = utils.balance_at_coordinates(
            balances=in_flight_balances,
            address=unpaid_address,  # type: ignore
            denomination=denomination,
        )
        billed = utils.balance_at_coordinates(
            balances=in_flight_balances,
            address=billed_address,  # type: ignore
            denomination=denomination,
        )

        return utils.round_decimal(percentage * (unpaid + billed), 2)

    interest_percentage = Decimal(mad_percentages[INTEREST.lower()])
    fees_percentage = Decimal(mad_percentages[FEES.lower()])

    for txn_type, refs in txn_types.items():
        principal_percentage = Decimal(mad_percentages[txn_type.lower()])

        # If there are no refs, run loop once with txn_ref = None
        for ref in refs or [""]:
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
    vault: SmartContractVault,
    in_flight_balances: BalanceDefaultDict,
    debit_address: str,
    credit_address: str,
    denomination: str,
) -> tuple[Decimal, list[CustomInstruction]]:
    """
    Move positive balance from one bucket (debit_address) to another (credit_address).

    :param vault: Vault object for the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param debit_address: The address to debit
    :param credit_address: The address to credit
    :param denomination: Denomination of the account
    :return: Rebalance amount to rebalance CustomInstructions
    """
    amount = utils.balance_at_coordinates(
        balances=in_flight_balances, address=debit_address, denomination=denomination
    )

    rebalance_postings = []
    if abs(amount) > 0:
        rebalance_postings = _move_funds_internally(
            vault,
            abs(amount),
            credit_address,
            debit_address,
            denomination,
            in_flight_balances,
        )
        return amount, rebalance_postings

    return Decimal(0), []


def _charge_fee(
    vault: SmartContractVault,
    denomination: str,
    in_flight_balances: BalanceDefaultDict,
    fee_type: str,
    fee_amount: Optional[Decimal] = None,
    is_external_fee: bool = False,
) -> tuple[Decimal, list[CustomInstruction]]:
    """
    Create postings to charge and rebalance a fee and update internal accounts, no postings created
    if amount is not >0.

    :param vault: Vault object for the account
    :param denomination: Denomination of the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param fee_type: The fee type to be added to metadata
    :param fee_amount: The fee amount, only required for external fees
    :param is_external_fee: True if fee is initiated outside of the contract
    :return: Fee amount and CustomInstructions to charge the fee
    """

    if not is_external_fee:
        fee_amount = utils.get_parameter(name=fee_type.lower(), vault=vault)
    if fee_amount == 0:
        return Decimal(0), []

    income_account = _get_fee_internal_account(vault, fee_type, "", is_external_fee)

    fee_posting_instructions = _rebalance_fees(
        vault,
        fee_amount,  # type: ignore
        denomination,
        in_flight_balances,
        income_account,
        fee_type,
    )

    return fee_amount, fee_posting_instructions  # type: ignore


def _get_fee_internal_account(
    vault: SmartContractVault,
    fee_type: Optional[str] = None,
    txn_type: Optional[str] = None,
    is_external_fee: Optional[bool] = False,
) -> str:
    """
    Helper to retrieve the income account for either a transaction type
    fee or a regular fee.

    :param vault: Vault object for the account
    :param fee_type: Fee type to retrieve accounts for. None if charging a non-transaction fee
    :param txn_type: Transaction type to retrieve accounts for. Must be non-None if charging a
    transaction fee
    :param is_external_fee: True if the fee is initiated outside the contract
    :return: Income principal account
    """

    if fee_type:
        if is_external_fee:
            fee_internal_account = utils.get_parameter(
                name=PARAM_EXTERNAL_FEE_INTERNAL_ACCOUNTS, is_json=True, vault=vault
            )[fee_type.lower()]
        else:
            fee_internal_account = utils.get_parameter(
                name=f"{fee_type.lower()}_internal_account", vault=vault
            )
    elif txn_type:
        fee_internal_account = utils.get_parameter(
            name=PARAM_TXN_TYPE_FEES_INTERNAL_ACCOUNTS_MAP, is_json=True, vault=vault
        )[txn_type.lower()]

    # TODO: Potentially unbounded return value - refactor
    return fee_internal_account  # type: ignore


def _charge_interest(
    vault: SmartContractVault,
    is_revolver: bool,
    denomination: str,
    accruals_by_sub_type: dict[tuple[str, str, str], dict[str, Decimal]],
    txn_types_to_charge_interest_from_txn_date: list[str],
    in_flight_balances: BalanceDefaultDict,
    instructions: list[CustomInstruction],
    txn_types_in_interest_free_period: Optional[dict[str, list[str]]] = None,
    is_pdd: bool = False,
    charge_interest_free_period: bool = False,
) -> None:
    """
    Creates postings to charge accrued interest and rebalance accordingly

    :param vault: Vault object for the account
    :param is_revolver: indicates whether the account is currently revolver or not
    :param denomination: Denomination of the account
    :param accruals_by_sub_type: Dict of charge type, charge sub type, accrual type to dict of
    txn ref type to accrual amount. Ref type can be empty string if not applicable
    :param txn_types_to_charge_interest_from_txn_date: List of transaction types that
    get charged interest straight away from the date of transaction
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param instructions: In-flight CustomInstructions to be extended by the method with postings
    to charge interest and rebalance
    :param txn_types_in_interest_free_period: transaction types and refs that have an active
    interest free period
    :param is_pdd: True if we are charging interest from PDD
    :param charge_interest_free_period: indicates whether code is called on PDD given that
    PARAM_MAD was unpaid, which means interests charged under interest free periods will now be
    chargeable
    :return: None
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

    def _charge_interest_per_txn_type(
        charge_type: str,
        sub_type: str,
        txn_charge_amount: Decimal,
        txn_ref: Optional[str] = "",
        accrual_type: Optional[str] = None,
    ) -> None:
        """
        :param charge_type: One of PRINCIPAL, FEES or INTEREST
        :param sub_type: Transaction or fee type
        :param txn_charge_amount: Amount to charge for transaction type
        :param txn_ref: Transaction reference
        :param accrual_type: Either '' or PRE_SCOD or POST_SCOD applicable for
        interest accrual to _UNCHARGED balances from txn day
        :return: None
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
            instructions.extend(
                _make_accrual_posting(
                    vault,
                    accrual_amount=txn_charge_amount,
                    denomination=denomination,
                    stem=txn_stem,
                    reverse=True,
                    instruction_details={
                        "description": f"Uncharged interest reversed for "
                        f"{txn_stem_with_accrual_type} - INTEREST_CHARGED"
                    },
                    accrual_type=accrual_type,
                )
            )

        trigger_base = INTEREST
        if charge_interest_free_period:
            trigger_base = f"{INTEREST_FREE_PERIOD}_{trigger_base}"
        elif accrual_type:
            # need to make trigger for pre/post uncharged interest addresses unique
            trigger_base = f"{accrual_type.upper()}_{trigger_base}"

        _rebalance_interest(
            vault=vault,
            amount=txn_charge_amount,
            denomination=denomination,
            in_flight_balances=in_flight_balances,
            charge_type=charge_type,
            sub_type=sub_type,
            instructions=instructions,
            txn_ref=txn_ref,
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


def _process_payment_due_date(
    vault: SmartContractVault, effective_datetime: datetime
) -> tuple[list[PostingInstructionsDirective], list[AccountNotificationDirective]]:
    """
    Based on repayments received since SCOD, check if Customer repaid:
    - Less than PARAM_MAD -> charge late repayment
    - More than PARAM_MAD but less than full statement amount -> set account to revolver and charge
      uncharged interest
    - All statement -> reverse any uncharged interest

    :param vault: Vault object for the account
    :param effective_datetime: Datetime of the PDD schedule
    :return: Posting directives, notification directives
    """
    instructions: list[CustomInstruction] = []
    notification_directives: list[AccountNotificationDirective] = []
    denomination = utils.get_parameter(name=PARAM_DENOMINATION, vault=vault)
    credit_limit = utils.get_parameter(name=PARAM_CREDIT_LIMIT, vault=vault)

    # We use live balances as there is no cut-off for PDD.
    live_balances = vault.get_balances_observation(fetcher_id=LIVE_BALANCES_BOF_ID).balances
    in_flight_balances = _deep_copy_balances(live_balances)

    supported_txn_types = _get_supported_txn_types(vault, effective_datetime)
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
    instructions.extend(
        _reverse_uncharged_interest(
            vault,
            in_flight_balances,
            denomination,
            interest_free_txn_types,
            "REVERSE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED",
        )
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
            return [
                # We don't set a value_datetime as we want this to be inserted 'live' as we're
                # also using live balances
                PostingInstructionsDirective(  # noqa: CTR009
                    posting_instructions=instructions,
                    client_batch_id=f"ZERO_OUT_ACCRUED_INTEREST-{vault.get_hook_execution_id()}",
                )
            ], []
        return [], []

    new_overdue_amount = Decimal("0")
    if not _is_revolver(in_flight_balances, denomination):
        # Outstanding statement balance was not paid so the account is now revolver
        instructions.extend(
            _change_revolver_status(
                vault,
                denomination,
                in_flight_balances,
                revolver=True,
            )
        )

        accruals_by_sub_type: dict[tuple[str, str, str], dict[str, Decimal]] = {}
        for dimensions, amount in in_flight_balances.items():
            address = dimensions[0]
            if address.endswith(INTEREST_FREE_PERIOD_UNCHARGED_INTEREST_BALANCE):
                # We have separate code to deal with the charging interest free period interest case
                pass
            elif address.endswith(UNCHARGED):
                # These balance addresses look like this:
                # For non-reference based transactions - PURCHASE_INTEREST_UNCHARGED
                # For reference based transactions - BALANCE_TRANSFER_REF1_INTEREST_UNCHARGED
                # If accrue_interest_from_txn_day is enabled, balance addresses look like:
                # For non-reference based transactions - PURCHASE_INTEREST_POST/PRE_SCOD_UNCHARGED
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
                            sub_type, ref = _get_txn_type_and_ref_debit_address(
                                address,
                                list(supported_txn_types.keys()),
                                f"{INTEREST}_{accrual_type}_{UNCHARGED}",
                            )
                            _set_accruals_by_sub_type(
                                accruals_by_sub_type,
                                charge_type=charge_type,
                                sub_type=sub_type,
                                accrual_amount=amount.net,
                                ref=ref,
                                accrual_type=accrual_type,
                            )

                else:
                    sub_type, ref = _get_txn_type_and_ref_debit_address(
                        address, list(supported_txn_types.keys()), UNCHARGED_INTEREST_BALANCE
                    )
                    _set_accruals_by_sub_type(
                        accruals_by_sub_type,
                        charge_type=charge_type,
                        sub_type=sub_type,
                        accrual_amount=amount.net,
                        ref=ref,
                    )

        # TODO: `instructions` is update within function, should pass it around
        _charge_interest(
            vault,
            is_revolver=True,
            denomination=denomination,
            accruals_by_sub_type=accruals_by_sub_type,
            txn_types_to_charge_interest_from_txn_date=[],
            in_flight_balances=in_flight_balances,
            instructions=instructions,
            is_pdd=True,
        )

    repayments = utils.balance_at_coordinates(
        balances=in_flight_balances,
        denomination=denomination,
        address=TRACK_STATEMENT_REPAYMENTS,
    )

    mad = utils.balance_at_coordinates(
        balances=in_flight_balances, denomination=denomination, address=MAD_BALANCE
    )

    if utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_MAD_EQUAL_TO_ZERO_FLAGS,
        effective_datetime=effective_datetime,
    ):
        # PARAM_MAD zero out flag active, e.g. there is an active repayment holiday.
        # We do not require any PARAM_MAD payment, and will zero out existing PARAM_MAD balance.
        instructions.extend(_zero_out_mad_balance(vault, mad, denomination))

    elif mad > repayments:
        # If the repayment did not cover the PARAM_MAD
        new_overdue_total = mad - repayments
        # new_overdue_amount should not double count what was already overdue in PARAM_MAD
        # (e.g missed PARAM_MAD based on overdue of 100 and fees of 100 only adds extra 100 to
        # overdue)
        current_overdue_total = Decimal(sum(_get_overdue_balances(in_flight_balances).values()))
        # We need to prevent overdue total from being negative if repayments + current overdue
        # amount exceed PARAM_MAD
        new_overdue_amount = max(new_overdue_total - current_overdue_total, Decimal("0"))

        _, fee_posting_instructions = _charge_fee(
            vault,
            denomination,
            in_flight_balances,
            LATE_REPAYMENT_FEE,
        )
        instructions.extend(fee_posting_instructions)

        # Expire all interest free periods
        # Interest accrued from this statement period will be charged
        notification_directives.append(
            AccountNotificationDirective(
                notification_type=EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION,
                notification_details={"account_id": str(vault.account_id)},
            )
        )

        accruals_by_sub_type = {}
        for dimensions, amount in in_flight_balances.items():
            address = dimensions[0]

            charge_type = PRINCIPAL
            if address.endswith(INTEREST_FREE_PERIOD_UNCHARGED_INTEREST_BALANCE):
                # These balance addresses look like this:
                # For non-reference based transactions
                # - PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED
                # For reference based transactions
                # - BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED
                sub_type, ref = _get_txn_type_and_ref_debit_address(
                    address,
                    list(supported_txn_types.keys()),
                    INTEREST_FREE_PERIOD_UNCHARGED_INTEREST_BALANCE,
                )

                _set_accruals_by_sub_type(
                    accruals_by_sub_type,
                    charge_type=charge_type,
                    sub_type=sub_type,
                    accrual_amount=amount.net,
                    ref=ref,
                )

        # The interest accrued on the INTEREST_FREE_PERIOD_INTEREST_UNCHARGED address will now be
        # charged. Supply charge_interest_free_period=True into our _charge_interest call to avoid
        # duplicated client transaction IDs out of the _charge_interest call in the revolver logic.
        # TODO: `instructions` is update within function, should pass it around
        _charge_interest(
            vault,
            is_revolver=True,
            denomination=denomination,
            accruals_by_sub_type=accruals_by_sub_type,
            txn_types_to_charge_interest_from_txn_date=[],
            in_flight_balances=in_flight_balances,
            instructions=instructions,
            is_pdd=True,
            charge_interest_free_period=True,
        )

    instructions.extend(
        _adjust_aggregate_balances(
            vault,
            denomination,
            in_flight_balances,
            effective_datetime=effective_datetime,
            credit_limit=credit_limit,
        )
    )

    # This takes care of moving any outstanding statement balances to overdue or past due
    instructions.extend(
        _move_outstanding_statement(
            vault,
            in_flight_balances,
            denomination,
            new_overdue_amount,
            supported_txn_types,
            effective_datetime,
        )
    )

    posting_instructions_directives = []
    if instructions:
        posting_instructions_directives.append(
            PostingInstructionsDirective(
                posting_instructions=instructions,
                client_batch_id=f"PDD-{vault.get_hook_execution_id()}",
                value_datetime=effective_datetime,
            )
        )
    return posting_instructions_directives, notification_directives


def _move_outstanding_statement(
    vault: SmartContractVault,
    in_flight_balances: BalanceDefaultDict,
    denomination: str,
    overdue_total: Decimal,
    supported_txn_types: dict[str, Optional[list[str]]],
    effective_datetime: datetime,
) -> list[CustomInstruction]:
    """
    Update overdue and unpaid buckets based on balances at PDD cut-off.

    :param vault: Vault object for the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param denomination: Denomination of the account
    :param overdue_total: PARAM_MAD - total repayments as of the PDD cut-off
    :param supported_txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :param effective_datetime: Datetime of the PDD schedule
    :return: CustomInstructions to update outstanding buckets
    """
    posting_instructions: list[CustomInstruction] = []

    if not utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_OVERDUE_AMOUNT_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    ):
        posting_instructions.extend(
            _update_overdue_buckets(vault, overdue_total, in_flight_balances, denomination)
        )

    if not utils.is_flag_in_list_applied(
        vault=vault,
        parameter_name=PARAM_BILLED_TO_UNPAID_TRANSFER_BLOCKING_FLAGS,
        effective_datetime=effective_datetime,
    ):
        supported_fee_types = _get_supported_fee_types(vault, supported_txn_types)

        posting_instructions.extend(
            _move_outstanding_statement_balances_to_unpaid(
                vault,
                in_flight_balances,
                denomination,
                supported_txn_types,
                supported_fee_types,
            )
        )

    return posting_instructions


def _update_overdue_buckets(
    vault: SmartContractVault,
    overdue_total: Decimal,
    in_flight_balances: BalanceDefaultDict,
    denomination: str,
) -> list[CustomInstruction]:
    """
    Cycles existing overdue buckets and populates latest overdue bucket if required.

    :param vault: Vault object for the account
    :param overdue_total: Overdue amount for this cycle, i.e. PARAM_MAD not covered by repayments
     (which are both -ve)
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param denomination: Denomination of the account
    :return: CustomInstructions to update the overdue buckets
    """
    instructions: list[CustomInstruction] = []

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
        instructions.extend(
            _override_info_balance(
                vault,
                in_flight_balances,
                overdue_bucket,
                denomination,
                amount,
            )
        )

    return instructions


def _get_overdue_balances(balances: BalanceDefaultDict) -> dict[str, Decimal]:
    """
    For a given set of vault balances, get all the overdue buckets and corresponding amounts.

    :param balances: Balances to use
    :return: Overdue address to overdue amount
    """

    return {
        dimensions[0]: amount.net
        for dimensions, amount in balances.items()
        if dimensions[0].startswith(OVERDUE)
    }


def _get_overdue_address_age(overdue_address: str) -> int:
    """
    Given an overdue address get the age from the name.

    :param overdue_address: The address to get the age for
    :return: The age of the address
    """
    return int(overdue_address.replace(OVERDUE + "_", ""))


def _age_overdue_address(overdue_address: str) -> str:
    """
    Creates the new address for an overdue balance when it has aged by a cycle.

    :param overdue_address: Current address (e.g. OVERDUE_1)
    :return: Aged overdue address (e.g. OVERDUE_2 if the input was OVERDUE_1)
    """

    new_age = _get_overdue_address_age(overdue_address) + 1

    return OVERDUE + "_" + str(new_age)


def _move_outstanding_statement_balances_to_unpaid(
    vault: SmartContractVault,
    in_flight_balances: BalanceDefaultDict,
    denomination: str,
    supported_txn_types: dict[str, Optional[list[str]]],
    supported_fee_types: list[str],
) -> list[CustomInstruction]:
    """
    Move any unpaid statement amount to past_due.

    :param vault: Vault object for the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param denomination: Denomination of the account
    :param supported_txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :param supported_fee_types: Supported fee types
    :return: CustomInstructions to move balances to past_due
    """
    posting_instructions: list[CustomInstruction] = []

    def move_statement_balance_to_unpaid(
        charge_type: str, sub_type: str, txn_ref: Optional[str] = None
    ) -> None:
        """
        Move from billed to unpaid for a given charge type
        :param charge_type: str, one of PRINCIPAL, FEES or INTEREST
        :param sub_type: str, name of txn_type or fee_type to be passed for address creation
        :param txn_ref: Optional(str), transaction level reference
        """
        statement_address = ""
        past_due_address = ""
        if charge_type == PRINCIPAL:
            statement_address = _principal_address(sub_type, BILLED, txn_ref=txn_ref)
            past_due_address = _principal_address(sub_type, UNPAID, txn_ref=txn_ref)
        elif charge_type == INTEREST:
            statement_address = _interest_address(sub_type, BILLED, txn_ref=txn_ref)
            past_due_address = _interest_address(sub_type, UNPAID, txn_ref=txn_ref)
        elif charge_type == FEES:
            statement_address = _fee_address(sub_type, BILLED)
            past_due_address = _fee_address(sub_type, UNPAID)

        statement_to_past_due = utils.balance_at_coordinates(
            balances=in_flight_balances, address=statement_address, denomination=denomination
        )
        if statement_to_past_due > 0:
            posting_instructions.extend(
                _move_funds_internally(
                    vault,
                    amount=statement_to_past_due,
                    debit_address=past_due_address,
                    credit_address=statement_address,
                    denomination=denomination,
                    in_flight_balances=in_flight_balances,
                )
            )

    for txn_type, refs in supported_txn_types.items():
        for ref in refs or [""]:
            move_statement_balance_to_unpaid(charge_type=PRINCIPAL, sub_type=txn_type, txn_ref=ref)
            move_statement_balance_to_unpaid(charge_type=INTEREST, sub_type=txn_type, txn_ref=ref)

    for fee_type in supported_fee_types:
        move_statement_balance_to_unpaid(charge_type=FEES, sub_type=fee_type)
        move_statement_balance_to_unpaid(charge_type=INTEREST, sub_type=fee_type)

    return posting_instructions


def _move_funds_internally(
    vault: SmartContractVault,
    amount: Decimal,
    debit_address: str,
    credit_address: str,
    denomination: str,
    in_flight_balances: Optional[BalanceDefaultDict],
) -> list[CustomInstruction]:
    """
    Move an amount from one address to another on the vault account.

    :param vault: Vault object for the account
    :param amount: Decimal, amount to transfer
    :param debit_address: Address to debit
    :param credit_address: Address to credit
    :param denomination: Denomination of the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :return: CustomInstructions to transfer the funds
    """
    if amount <= 0:
        return []

    return _create_custom_instructions(
        vault,
        amount,
        debit_account_id=vault.account_id,
        credit_account_id=vault.account_id,
        denomination=denomination,
        debit_address=debit_address,
        instruction_details={
            "description": f"Move balance from {debit_address} to " f"{credit_address}"
        },
        credit_address=credit_address,
        in_flight_balances=in_flight_balances,
    )


def _reverse_uncharged_interest(
    vault: SmartContractVault,
    in_flight_balances: BalanceDefaultDict,
    denomination: str,
    supported_txn_types: dict[str, Optional[list[str]]],
    trigger: str,
    accrual_type: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Creates posting instructions to reverse all uncharged interest.

    :param vault: Vault object for the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param denomination: Denomination of the account
    :param supported_txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :param trigger: The trigger for reversing uncharged interest
    :param accrual_type: Either '' or PRE_SCOD or POST_SCOD applicable for interest accrual to
    _UNCHARGED balances from txn day
    :return: CustomInstructions to zero out accrued interest
    """

    def _execute_reversal(txn_type: str, txn_ref: Optional[str] = None) -> None:
        """
        Instruct posting for interest reversal.
        :param txn_type: Transaction type
        :param txn_ref: Transaction level reference
        """
        address = _interest_address(txn_type, UNCHARGED, txn_ref=txn_ref, accrual_type=accrual_type)
        accrued_outgoing = utils.balance_at_coordinates(
            balances=in_flight_balances, address=address, denomination=denomination
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
            instructions.extend(
                _make_accrual_posting(
                    vault,
                    accrual_amount=accrued_outgoing,
                    denomination=denomination,
                    stem=stem,
                    instruction_details={
                        "description": f"Uncharged interest reversed for "
                        f"{stem_with_accrual_type} - {trigger}"
                    },
                    reverse=True,
                    accrual_type=accrual_type,
                )
            )

    instructions: list[CustomInstruction] = []
    for txn_type, txn_refs in supported_txn_types.items():
        for txn_ref in txn_refs or [""]:
            _execute_reversal(txn_type, txn_ref=txn_ref)

    return instructions


def _zero_out_mad_balance(
    vault: SmartContractVault, mad_balance: Decimal, denomination: str
) -> list[CustomInstruction]:
    """
    Creates posting instructions to zero out the MAD_BALANCE address.

    :param vault: Vault object for the account
    :param mad_balance: The amount in the MAD_BALANCE address.
    :param denomination: Denomination of the account
    :return: CustomInstructions to zero out the MAD_BALANCE
    """
    instructions: list[CustomInstruction] = []

    if mad_balance > 0:
        instructions.extend(
            _make_internal_address_transfer(
                vault=vault,
                amount=mad_balance,
                denomination=denomination,
                credit_internal=False,
                custom_address=MAD_BALANCE,
                instruction_details={"description": "PARAM_MAD balance zeroed out"},
            )
        )
    return instructions


def _principal_address(txn_type: str, txn_type_status: str, txn_ref: Optional[str] = None) -> str:
    """
    get the balance address that contains transaction type for a given status, injecting reference
    if present.

    :param txn_type: A supported transaction type
    :param txn_type_status: A supported transaction type status.
    One of: AUTH, CHARGED, BILLED, UNPAID
    :param txn_ref: Reference only populated for types tracked at a transaction level
    :return: Balance address. For example, CASH_ADVANCE_AUTH or BALANCE_TRANSFER_REF1_BILLED
    """
    return (
        (f"{txn_type.upper()}_{txn_ref}_{txn_type_status}")
        if txn_ref
        else f"{txn_type}_{txn_type_status}"
    )


def _interest_address(
    txn_type: str,
    interest_status: str,
    txn_ref: Optional[str] = None,
    accrual_type: Optional[str] = None,
) -> str:
    """
    Get the balance address for transaction type's interest of a specific status  E.g. UNCHARGED
    interest for PURCHASE transactions.

    :param txn_type: A supported transaction type
    :param interest_status: A supported interest status. One of: UNCHARGED, CHARGED, BILLED
    :param txn_ref: Reference only populated for types tracked at a transaction level.
    :param accrual_type: Either '' or PRE_SCOD or POST_SCOD applicable for interest accrual to
    _UNCHARGED balances from txn day
    :return: Balance address. For example, PURCHASE_INTEREST_BILLED
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


def _fee_address(fee_type: str, fee_status: str) -> str:
    """
    get the balance address that contains fees for a certain type (e.g. CASH_ADVANCE_FEES_BILLED).
    Fees always charged at a type level, so references not considered.

    :param fee_type: A supported fee type. See FEE_TYPES constant
    :param fee_status: A supported fee status. One of: CHARGED, BILLED, UNPAID
    :return: Balance address. For example, FEES_CHARGED
    """
    return f"{fee_type}S_{fee_status}"


def _charge_overlimit_fee(
    vault: SmartContractVault,
    in_flight_balances: BalanceDefaultDict,
    denomination: str,
    supported_txn_types: dict[str, Optional[list[str]]],
    credit_limit: Decimal,
) -> list[CustomInstruction]:
    """
    Charge over limit fee if there is any over limit balance at SCOD

    :param vault: Vault object for the account
    :param in_flight_balances: Latest account balances updated with balances of the
    CustomInstructions created within the current hook execution
    :param denomination: Denomination of the account
    :param supported_txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :param credit_limit: The account's credit limit at SCOD cut-off
    :return: Fee and aggregation CustomInstructions (can return empty list)
    """

    opt_in = utils.get_parameter(
        vault,
        name=PARAM_OVERLIMIT_OPT_IN,
        is_optional=True,
        is_boolean=True,
        default_value="False",
    )
    overlimit_amount = _get_overlimit_amount(
        in_flight_balances, credit_limit, denomination, supported_txn_types
    )

    # We don't charge a fee if customer has gone overlimit due to stand-in/offline transaction but
    # never explicitly opted-in to the overlimit facility
    posting_instructions: list[CustomInstruction] = []
    if overlimit_amount > 0 and opt_in:
        fee, fee_instructions = _charge_fee(
            vault,
            denomination,
            in_flight_balances,
            OVERLIMIT_FEE,
        )
        if fee == 0:
            return []
        else:
            posting_instructions.extend(fee_instructions)

        posting_instructions.extend(
            _adjust_aggregate_balances(
                vault=vault,
                denomination=denomination,
                in_flight_balances=in_flight_balances,
                outstanding=False,
                full_outstanding=False,
                credit_limit=credit_limit,
            )
        )
    return posting_instructions


def _get_overlimit_amount(
    balances: BalanceDefaultDict,
    credit_limit: Decimal,
    denomination: str,
    supported_txn_types: dict[str, Optional[list[str]]],
) -> Decimal:
    """
    Determines how much the account is overlimit by. A customer is considered overlimit if the
    total principal amount is greater than the customer's credit limit. Principal only includes
    charged, billed or unpaid transactions.

    :param balances: Account balances
    :param credit_limit: Account's credit limit (positive),
    :param denomination: Denomination of the account
    :param supported_txn_types: Map of supported transaction types (txn_type to txn_level_refs)
    :return: Amount the account is over limit by (>=0)
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
        Decimal("0"),
    )


def _get_non_advice_postings(
    posting_instructions: list[PostingInstruction],
) -> list[PostingInstruction]:
    """
    Filters out postings that have no advice attribute or advice set to false. This is needed as
    the advice attribute is not populated on instructions that do not support it.

    :param posting_instructions: The invoking posting instructions
    :return: Filtered postings
    """

    return [
        posting_instruction
        for posting_instruction in posting_instructions
        if posting_instruction.type
        in [
            PostingInstructionType.RELEASE,
            PostingInstructionType.SETTLEMENT,
            PostingInstructionType.TRANSFER,
            PostingInstructionType.CUSTOM_INSTRUCTION,
        ]
        or posting_instruction.advice is False  # type: ignore
    ]


def _deep_copy_balances(balances: BalanceDefaultDict) -> BalanceDefaultDict:
    """
    Makes a deep copy of the input balances.

    :param balances: Balances to copy
    :return: Deep copy of the balances
    """

    new_balances = BalanceDefaultDict()
    new_balances += balances
    return new_balances


def _update_balances(
    account_id: str,
    balances: BalanceDefaultDict,
    posting_instructions: list[PostingInstruction],
) -> None:
    """
    Updates the balances for an account based on new postings that are made.

    :param account_id: Account id
    :param balances: Account balances to update
    :param posting_instructions: Posting Instructions to adjust the account balances
    :return: None
    """
    for posting_instruction in posting_instructions:
        # For release/settlements there could be more than one key-value pair in .balances()
        # account_id passed in for posting instructions created by SC
        balances += posting_instruction.balances(account_id=account_id, tside=tside)


def _get_txn_type_and_ref_debit_address(
    address: str, base_txn_types: list[str], address_type: str
) -> tuple[str, Optional[str]]:
    """
    Extract the transaction type & reference given a transaction balance address
    Example addresses:
    - CASH_PURCHASE_INTEREST_UNCHARGED
    - BALANCE_TRANSFER_REF1_INTEREST_CHARGED
    - BALANCE_TRANSFER_REF1_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED
    - PURCHASE_INTEREST_POST_SCOD_UNCHARGED
    - BALANCE_TRANSFER_REF1_INTEREST_PRE_SCOD_UNCHARGED

    :param address: The address to split into (type, ref) pairs (upper case)
    :param base_txn_types: Transaction types without any references appended (upper case)
    :param address_type: The string at the end of address that we slice off to obtain the
    TXN_TYPE_REF stem
    :return: Transaction type to reference. Reference may be None
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


def _is_txn_type_in_interest_free_period(
    txn_types_in_interest_free_period: dict[str, list[str]],
    sub_type: str,
    ref: Optional[str] = None,
) -> bool:
    """
    Given the dictionary of transaction types / refs that have an active interest free period,
    determine whether the supplied txn_type/ ref combo has an active interest free period

    :param txn_types_in_interest_free_period: Transaction types and refs that have an active
    interest free period
    :param sub_type: Transaction type
    :param ref: Transaction reference
    :return: True if the txn_type/ ref has an active interest free period, False otherwise
    """
    if not ref:
        return sub_type.lower() in txn_types_in_interest_free_period
    else:
        return ref in txn_types_in_interest_free_period.get(sub_type.lower(), [])


def _determine_txns_currently_interest_free(
    txn_types_in_interest_free_period: dict[str, list[str]],
    base_interest_rates: dict[str, str],
    txn_base_interest_rates: dict[str, dict[str, str]],
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """
    Given the dictionary of transaction types/ refs that have an active interest free period,
    set the corresponding base interest rates to zero

    :param txn_types_in_interest_free_period: Transaction types and refs that have an active
    interest free period
    :param base_interest_rates: Base interest rates per transaction type that does not use
    transaction references
    :param txn_base_interest_rates: Base interest rates per transaction reference, for transaction
    types that use transaction references
    :return: Updated base interest rates, updated txn_base_interest_rates rates
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
    accruals_by_sub_type: dict[tuple[str, str, str], dict[str, Decimal]],
    charge_type: str,
    sub_type: str,
    accrual_amount: Decimal,
    ref: Optional[str] = None,
    accrual_type: Optional[str] = None,
) -> None:
    """
    Construct accruals information based on charge_type, sub_type, accrual_type, ref
    and accrual_amount

    :param accruals_by_sub_type: The dictionary that we add information to, e.g.
        {(PRINCIPAL, 'balance_transfer', ''): {'REF1': 1.23, 'REF2': 4.56}}
        {(PRINCIPAL, 'purchase', 'PRE_SCOD'): {'': 7.89}}
    :param charge_type: either PRINCIPAL or FEE
    :param sub_type: The transaction type which doesn't contain a reference
    :param accrual_amount: The amount to accrue
    :param ref: The transaction reference if there is one
    :param accrual_type: Either '' or PRE_SCOD or POST_SCOD applicable for interest
    accrual to _UNCHARGED balances from txn day
    :return: None
    """

    # ref for transactions with reference or blank for transactions without reference
    ref_or_blank = ref or ""
    accrual_type_or_blank = accrual_type or ""

    accrual_address_data = (charge_type, sub_type, accrual_type_or_blank)

    accruals_by_sub_type.setdefault(accrual_address_data, {})
    accruals_by_sub_type[accrual_address_data].setdefault(ref_or_blank, Decimal("0.0"))
    accruals_by_sub_type[accrual_address_data][ref_or_blank] += accrual_amount


def _is_txn_interest_accrual_from_txn_day(
    vault: SmartContractVault, at_datetime: Optional[datetime] = None
) -> bool:
    """
    Returns current state of the accrue_interest_from_txn_day flag.

    :param vault: Vault object for the account
    :param at_datetime: the datetime at which param needs to be returned, defaults
    to latest
    """
    accrue_interest_from_txn_day = utils.get_parameter(
        vault, name=PARAM_ACCRUE_INTEREST_FROM_TXN_DAY, at_datetime=at_datetime, is_boolean=True
    )
    return accrue_interest_from_txn_day


def get_denomination_from_posting_instruction(posting_instruction: PostingInstruction) -> str:
    """
    Get denomination of posting instruction. CustomInstruction doesn't have denomination attribute
    so taking denomination of first posting. Type ignored due to not all PI's having the same
    attributes
    """
    return (
        posting_instruction.denomination  # type: ignore
        if posting_instruction.type is not PostingInstructionType.CUSTOM_INSTRUCTION
        # TODO: Currently assuming that all postings in CustomInstruction have same denomination
        else posting_instruction.postings[0].denomination  # type: ignore
    )  # type: ignore


def move_funds_between_vault_accounts(
    amount: Decimal,
    denomination: str,
    debit_account_id: str,
    debit_address: str,
    credit_account_id: str,
    credit_address: str,
    asset: str = DEFAULT_ASSET,
    instruction_details: Optional[dict[str, str]] = None,
    transaction_code: Optional[TransactionCode] = None,
    override_all_restrictions: Optional[bool] = None,
) -> list[CustomInstruction]:
    postings = [
        Posting(
            credit=True,
            amount=amount,
            denomination=denomination,
            account_id=credit_account_id,
            account_address=credit_address,
            asset=asset,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=False,
            amount=amount,
            denomination=denomination,
            account_id=debit_account_id,
            account_address=debit_address,
            asset=asset,
            phase=Phase.COMMITTED,
        ),
    ]
    custom_instruction = CustomInstruction(
        postings=postings,
        instruction_details=instruction_details,
        transaction_code=transaction_code,
        override_all_restrictions=override_all_restrictions,
    )

    return [custom_instruction]
