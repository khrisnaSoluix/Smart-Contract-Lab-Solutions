# library
from library.wallet.contracts.template import wallet
from library.wallet.test.parameters import TEST_DENOMINATION

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

USD_DEFAULT_DIMENSIONS = BalanceDimensions(denomination="USD")
GBP_DEFAULT_DIMENSIONS = BalanceDimensions(denomination="GBP")
DEFAULT_DIMENSIONS = BalanceDimensions(denomination=TEST_DENOMINATION)
PENDING_OUT_DIMENSIONS = BalanceDimensions(
    denomination=TEST_DENOMINATION, phase="POSTING_PHASE_PENDING_OUTGOING"
)
TODAYS_SPENDING_DIMENSIONS = BalanceDimensions(
    address=wallet.TODAYS_SPENDING, denomination=TEST_DENOMINATION
)
