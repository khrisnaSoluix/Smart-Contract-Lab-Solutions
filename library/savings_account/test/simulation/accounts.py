# library
import library.savings_account.test.accounts as accounts

# inception sdk
from inception_sdk.test_framework.common.constants import ASSET, LIABILITY

default_internal_accounts = {
    accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: LIABILITY,
    accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: ASSET,
    accounts.DEPOSIT_ACCOUNT: LIABILITY,
    accounts.EXCESS_FEE_INCOME_ACCOUNT: LIABILITY,
    accounts.INACTIVITY_FEE_INCOME_ACCOUNT: LIABILITY,
    accounts.INTEREST_PAID_ACCOUNT: ASSET,
    accounts.INTEREST_RECEIVED_ACCOUNT: LIABILITY,
    accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: LIABILITY,
}
