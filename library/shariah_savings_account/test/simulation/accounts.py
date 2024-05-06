# library
from library.shariah_savings_account.test import accounts

# inception sdk
from inception_sdk.test_framework.common.constants import ASSET, LIABILITY

default_internal_accounts = {
    "1": LIABILITY,
    accounts.DUMMY_DEPOSITING_ACCOUNT: LIABILITY,
    accounts.ACCRUED_PROFIT_PAYABLE_ACCOUNT: LIABILITY,
    accounts.PROFIT_PAID_ACCOUNT: ASSET,
    accounts.EARLY_CLOSURE_FEE_INCOME_ACCOUNT: LIABILITY,
    accounts.PAYMENT_TYPE_FEE_INCOME_ACCOUNT: LIABILITY,
}
