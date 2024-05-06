# standard libs
import json

# library
from library.wallet.contracts.template import wallet
from library.wallet.test import accounts

TEST_DENOMINATION = "SGD"
ADDITIONAL_DENOMINATIONS = ["GBP", "USD"]

default_instance = {
    wallet.PARAM_DENOMINATION: TEST_DENOMINATION,
    wallet.PARAM_CUSTOMER_WALLET_LIMIT: "1000",
    wallet.PARAM_NOMINATED_ACCOUNT: accounts.NOMINATED_ACCOUNT,
    wallet.PARAM_SPENDING_LIMIT: "2000",
    wallet.PARAM_ADDITIONAL_DENOMINATIONS: json.dumps(ADDITIONAL_DENOMINATIONS),
}

default_template = {
    wallet.PARAM_ZERO_OUT_DAILY_SPEND_HOUR: "23",
    wallet.PARAM_ZERO_OUT_DAILY_SPEND_MINUTE: "59",
    wallet.PARAM_ZERO_OUT_DAILY_SPEND_SECOND: "59",
}
