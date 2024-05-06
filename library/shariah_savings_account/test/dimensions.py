# library
from library.shariah_savings_account.contracts.template import shariah_savings_account
from library.shariah_savings_account.test.parameters import TEST_DENOMINATION

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

DEFAULT = BalanceDimensions(denomination=TEST_DENOMINATION)

EUR_DEFAULT = BalanceDimensions(denomination="EUR")

ACCRUED_PROFIT_PAYABLE = BalanceDimensions(
    address=shariah_savings_account.tiered_profit_accrual.ACCRUED_PROFIT_PAYABLE,
    denomination=TEST_DENOMINATION,
)

EARLY_CLOSURE_FEE = BalanceDimensions(
    address=shariah_savings_account.early_closure_fee.DEFAULT_EARLY_CLOSURE_FEE_ADDRESS,
    denomination=TEST_DENOMINATION,
)

INCOMING = BalanceDimensions(
    denomination=TEST_DENOMINATION,
    phase="POSTING_PHASE_PENDING_INCOMING",
)

OUTGOING = BalanceDimensions(
    denomination=TEST_DENOMINATION,
    phase="POSTING_PHASE_PENDING_OUTGOING",
)
