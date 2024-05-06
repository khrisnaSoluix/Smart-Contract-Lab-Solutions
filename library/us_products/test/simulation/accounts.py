# library
from library.us_products.test import accounts

# inception sdk
from inception_sdk.test_framework.common.constants import ASSET, LIABILITY

default_internal_accounts = {
    accounts.DEPOSIT_ACCOUNT: LIABILITY,
    accounts.INACTIVITY_FEE_INCOME_ACCOUNT: LIABILITY,
    accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: LIABILITY,
    accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: ASSET,
    accounts.INTEREST_PAID_ACCOUNT: ASSET,
    accounts.INTEREST_RECEIVED_ACCOUNT: LIABILITY,
    accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: LIABILITY,
    accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: LIABILITY,
    accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: LIABILITY,
    accounts.OUT_OF_NETWORK_ATM_FEE_REBATE_ACCOUNT: ASSET,
}
