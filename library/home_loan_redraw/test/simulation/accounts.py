# library
from library.home_loan_redraw.test import accounts

# inception sdk
from inception_sdk.test_framework.common import constants

# internal accounts
default_internal_accounts = {
    accounts.INTERNAL: constants.LIABILITY,
    accounts.DEPOSIT: constants.LIABILITY,
    accounts.ACCRUED_INTEREST_RECEIVABLE: constants.LIABILITY,
    accounts.INTEREST_RECEIVED: constants.ASSET,
}
