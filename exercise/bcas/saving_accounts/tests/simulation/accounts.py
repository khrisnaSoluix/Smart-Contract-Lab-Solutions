from library.time_deposit.test import accounts
from inception_sdk.test_framework.common import constants

default_internal_accounts: dict[str, str] = {
    accounts.INTERNAL_ACCOUNT: constants.LIABILITY,
    accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: constants.LIABILITY,
    accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: constants.ASSET,
    accounts.INTEREST_PAID_ACCOUNT: constants.ASSET,
    accounts.INTEREST_RECEIVED_ACCOUNT: constants.LIABILITY,
}
