# library
from library.wallet.test import accounts

# inception sdk
from inception_sdk.test_framework.common.constants import LIABILITY

default_internal_accounts = {
    "1": LIABILITY,
    accounts.NOMINATED_ACCOUNT: LIABILITY,
}
