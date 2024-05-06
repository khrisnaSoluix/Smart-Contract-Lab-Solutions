# library
from library.shariah_savings_account.test import accounts

# required internal accounts dictionary
internal_accounts_tside = {
    "TSIDE_ASSET": [
        accounts.PROFIT_PAID_ACCOUNT,
    ],
    "TSIDE_LIABILITY": [
        accounts.ACCRUED_PROFIT_PAYABLE_ACCOUNT,
        accounts.EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
        accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT,
    ],
}
