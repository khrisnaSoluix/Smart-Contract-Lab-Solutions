# standard libs
from json import dumps, loads
from typing import Union

# Balance Names
INTERNAL = "INTERNAL"
AVAILABLE = "AVAILABLE_BALANCE"
OUTSTANDING = "OUTSTANDING_BALANCE"
FULL_OUTSTANDING = "FULL_OUTSTANDING_BALANCE"
CASH_ADVANCE_NEW = "CASH_ADVANCE_CHARGED"
PURCHASE_NEW = "PURCHASE_CHARGED"
PURCHASE_AUTH = "PURCHASE_AUTH"
DEPOSIT = "DEPOSIT"
TOTAL_REPAYMENTS_LAST_STATEMENT = "TOTAL_REPAYMENTS_LAST_STATEMENT"
BALANCE_TRANSFER_CHARGED = "BALANCE_TRANSFER_CHARGED"

# Event names
EVENT_ANNUAL_FEE = "ANNUAL_FEE"
EVENT_ACCRUE = "ACCRUE_INTEREST"
EVENT_PDD = "PAYMENT_DUE"
EVENT_SCOD = "STATEMENT_CUT_OFF"

# Parameter names
TXN_TYPE_LIMITS = "transaction_type_limits"
TXN_TYPE_FEES = "transaction_type_fees"
TXN_CODE_TO_TYPE_MAP = "transaction_code_to_type_map"

# Internal Accounts
LATE_REPAYMENT_FEE_INCOME_INT = "1"
ANNUAL_FEE_INCOME_INT = "1"
DISPUTE_FEE_INCOME_INT = "1"
ATM_WITHDRAWAL_FEE_INCOME_INT = "1"
OVERLIMIT_FEE_INCOME_INT = "1"
CASH_ADVANCE_FEE_INCOME_INT = "1"
PURCHASE_FEE_INCOME_INT = "1"
TRANSFER_FEE_INCOME_INT = "1"
BALANCE_TRANSFER_FEE_INCOME_INT = "1"
PURCHASE_INTEREST_INCOME_INT = "1"
CASH_ADVANCE_INTEREST_INCOME_INT = "1"
TRANSFER_INTEREST_INCOME_INT = "1"
BALANCE_TRANSFER_INTEREST_INCOME_INT = "1"
OTHER_LIABILITY_INT = "1"
FEES_INTEREST_INCOME = "1"
PRINCIPAL_WRITE_OFF_INT = "1"
INTEREST_WRITE_OFF_INT = "1"

# Parameter values
DEFAULT_SUPPORTED_TRANS_TYPES = dumps(
    {
        "purchase": {},
        "cash_advance": {"charge_interest_from_transaction_date": "True"},
        "transfer": {},
        "balance_transfer": {},
    }
)

BASE_INTEREST_RATES = dumps({"purchase": "0.24", "cash_advance": "0.36", "transfer": "0.36"})
MAD_PERCENTAGE = dumps(
    {
        "balance_transfer": "0.01",
        "purchase": "0.01",
        "cash_advance": "0.01",
        "transfer": "0.01",
        "interest": "1.0",
        "fees": "1.0",
    }
)
TXN_CODE_MAP = dumps(
    {
        "xxx": "purchase",
        "aaa": "cash_advance",
        "cc": "transfer",
        "bb": "balance_transfer",
    }
)
TXN_TYPE_LIMITS = dumps({"cash_advance": {"flat": "200"}, "transfer": {"flat": "1000"}})

DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS: dict[str, str] = {
    "transaction_types": DEFAULT_SUPPORTED_TRANS_TYPES,
    "denomination": "GBP",
    "base_interest_rates": BASE_INTEREST_RATES,
    "annual_percentage_rate": dumps({"purchase": "1", "cash_advance": "2", "transfer": "3"}),
    "minimum_amount_due": "200",
    "minimum_percentage_due": MAD_PERCENTAGE,
    "transaction_code_to_type_map": TXN_CODE_MAP,
    "late_repayment_fee_internal_account": LATE_REPAYMENT_FEE_INCOME_INT,
    "annual_fee_internal_account": ANNUAL_FEE_INCOME_INT,
    "external_fee_types": dumps(["dispute_fee", "atm_withdrawal_fee"]),
    "external_fee_internal_accounts": dumps(
        {
            "dispute_fee": DISPUTE_FEE_INCOME_INT,
            "atm_withdrawal_fee": ATM_WITHDRAWAL_FEE_INCOME_INT,
        }
    ),
    "overlimit_fee_internal_account": OVERLIMIT_FEE_INCOME_INT,
    "transaction_type_fees_internal_accounts_map": dumps(
        {
            "cash_advance": CASH_ADVANCE_FEE_INCOME_INT,
            "purchase": PURCHASE_FEE_INCOME_INT,
            "transfer": TRANSFER_FEE_INCOME_INT,
            "balance_transfer": BALANCE_TRANSFER_FEE_INCOME_INT,
        }
    ),
    "accrue_interest_on_unpaid_interest": "False",
    "accrue_interest_on_unpaid_fees": "False",
    "accrue_interest_from_txn_day": "True",
    "interest_on_fees_internal_account": FEES_INTEREST_INCOME,
    "accrual_blocking_flags": dumps(["90_DPD"]),
    "account_closure_flags": dumps(["ACCOUNT_CLOSURE_REQUESTED"]),
    "account_write_off_flags": dumps(["MANUAL_WRITE_OFF", "150_DPD"]),
    "mad_as_full_statement_flags": dumps(["ACCOUNT_CLOSURE_REQUESTED", "90_DPD"]),
    "mad_equal_to_zero_flags": dumps(["REPAYMENT_HOLIDAY"]),
    "overdue_amount_blocking_flags": dumps(["REPAYMENT_HOLIDAY"]),
    "billed_to_unpaid_transfer_blocking_flags": dumps(["REPAYMENT_HOLIDAY"]),
    "principal_write_off_internal_account": PRINCIPAL_WRITE_OFF_INT,
    "interest_write_off_internal_account": INTEREST_WRITE_OFF_INT,
    "transaction_type_interest_internal_accounts_map": dumps(
        {
            "purchase": PURCHASE_INTEREST_INCOME_INT,
            "cash_advance": CASH_ADVANCE_INTEREST_INCOME_INT,
            "transfer": TRANSFER_INTEREST_INCOME_INT,
            "balance_transfer": BALANCE_TRANSFER_INTEREST_INCOME_INT,
        }
    ),
    "accrual_schedule_hour": "0",
    "accrual_schedule_minute": "0",
    "accrual_schedule_second": "0",
    "scod_schedule_hour": "0",
    "scod_schedule_minute": "0",
    "scod_schedule_second": "2",
    "pdd_schedule_hour": "0",
    "pdd_schedule_minute": "0",
    "pdd_schedule_second": "1",
    "annual_fee_schedule_hour": "23",
    "annual_fee_schedule_minute": "50",
    "annual_fee_schedule_second": "0",
}

DEFAULT_CREDIT_CARD_INSTANCE_PARAMS: dict[str, str] = {
    "overlimit": "500",
    "overlimit_opt_in": "True",
    "credit_limit": "2000",
    "payment_due_period": "24",
    "late_repayment_fee": "100",
    "annual_fee": "100",
    "overlimit_fee": "100",
    "transaction_type_fees": dumps(
        {
            "cash_advance": {
                "over_deposit_only": "False",
                "percentage_fee": "0.05",
                "flat_fee": "5",
            }
        }
    ),
    "transaction_type_limits": TXN_TYPE_LIMITS,
    "transaction_references": dumps({"balance_transfer": []}),
    "transaction_annual_percentage_rate": dumps({"balance_transfer": {}}),
    "transaction_base_interest_rates": dumps({"balance_transfer": {}}),
    "interest_free_expiry": dumps({}),
    "transaction_interest_free_expiry": dumps({}),
}


def default_template_update(key: str, update: dict[str, Union[str, dict[str, str]]]) -> str:
    """
    Update one of the JSON dictionary fields in the template parameters,
    returning the new parameter JSON

    :param key: Which JSON parameter to update
    :param update: new content to be added to the parameter
    :return: Updated parameter in JSON format
    """
    param = loads(DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS[key])
    param.update(update)
    return dumps(param)
