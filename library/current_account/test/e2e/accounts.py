# library
from library.current_account.test import accounts

internal_accounts_tside = {
    "TSIDE_ASSET": [
        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
        accounts.INTEREST_PAID_ACCOUNT,
        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT,
        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
    ],
    "TSIDE_LIABILITY": [
        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT,
        accounts.ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
        accounts.EXCESS_FEE_INCOME_ACCOUNT,
        accounts.INACTIVITY_FEE_INCOME_ACCOUNT,
        accounts.INTEREST_RECEIVED_ACCOUNT,
        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT,
        accounts.UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT,
    ],
}
