# library
from library.time_deposit.test import accounts

internal_accounts_tside: dict[str, list[str]] = {
    "TSIDE_ASSET": [
        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
        accounts.INTEREST_PAID_ACCOUNT,
    ],
    "TSIDE_LIABILITY": [
        accounts.INTERNAL_ACCOUNT,
        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT,
        accounts.INTEREST_RECEIVED_ACCOUNT,
    ],
}
