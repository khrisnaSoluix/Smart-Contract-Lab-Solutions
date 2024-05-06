# library
from library.us_products.test import accounts

internal_accounts_tside: dict[str, list[str]] = {
    "TSIDE_ASSET": [
        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
        accounts.INTEREST_PAID_ACCOUNT,
        accounts.OUT_OF_NETWORK_ATM_FEE_REBATE_ACCOUNT,
    ],
    "TSIDE_LIABILITY": [
        accounts.DEPOSIT_ACCOUNT,
        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT,
        accounts.INTEREST_RECEIVED_ACCOUNT,
        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT,
        accounts.INACTIVITY_FEE_INCOME_ACCOUNT,
    ],
}
