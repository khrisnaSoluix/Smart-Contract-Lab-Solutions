# library
from library.home_loan_redraw.test import accounts

# shortening names that are longer than 32 characters for e2e
E2E_ACCRUED_INT_RECEIVABLE = "ACCRUED_INT_RECEIVABLE"
internal_accounts_tside = {
    "TSIDE_ASSET": [accounts.INTEREST_RECEIVED],
    "TSIDE_LIABILITY": [
        accounts.INTERNAL,
        accounts.DEPOSIT,
        E2E_ACCRUED_INT_RECEIVABLE,
    ],
}
