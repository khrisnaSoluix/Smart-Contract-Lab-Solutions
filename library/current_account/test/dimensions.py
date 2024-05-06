# library
from library.current_account.contracts.template import current_account
from library.current_account.test.parameters import TEST_DENOMINATION

# features
import library.features.v4.common.addresses as common_addresses

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

# Dimensions
ACCRUED_INTEREST_PAYABLE = BalanceDimensions(
    address=current_account.tiered_interest_accrual.ACCRUED_INTEREST_PAYABLE,
    denomination=TEST_DENOMINATION,
)
ACCRUED_INTEREST_RECEIVABLE = BalanceDimensions(
    address=current_account.tiered_interest_accrual.ACCRUED_INTEREST_RECEIVABLE,
    denomination=TEST_DENOMINATION,
)
UNARRANGED_OVERDRAFT_FEE = BalanceDimensions(
    address=current_account.unarranged_overdraft_fee.OVERDRAFT_FEE, denomination=TEST_DENOMINATION
)
OVERDRAFT_ACCRUED_INTEREST = BalanceDimensions(
    address=current_account.overdraft_interest.OVERDRAFT_ACCRUED_INTEREST,
    denomination=TEST_DENOMINATION,
)
OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER = BalanceDimensions(
    address=current_account.maintenance_fees.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER,
    denomination=TEST_DENOMINATION,
)
OUTSTANDING_INACTIVITY_FEE_TRACKER = BalanceDimensions(
    address=current_account.inactivity_fee.OUTSTANDING_INACTIVITY_FEE_TRACKER,
    denomination=TEST_DENOMINATION,
)
OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER = BalanceDimensions(
    address=current_account.minimum_monthly_balance.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
    denomination=TEST_DENOMINATION,
)

DEFAULT = BalanceDimensions(denomination=TEST_DENOMINATION)
PENDING_OUT = BalanceDimensions(
    denomination=TEST_DENOMINATION, phase="POSTING_PHASE_PENDING_OUTGOING"
)
INTERNAL_CONTRA = BalanceDimensions(
    address=common_addresses.INTERNAL_CONTRA, denomination=TEST_DENOMINATION
)
PENDING_IN = BalanceDimensions(
    denomination=TEST_DENOMINATION, phase="POSTING_PHASE_PENDING_INCOMING"
)
PENDING_OUT = BalanceDimensions(
    denomination=TEST_DENOMINATION, phase="POSTING_PHASE_PENDING_OUTGOING"
)

# Dimensions EUR
DEFAULT_EUR = BalanceDimensions(denomination="EUR")
# Dimensions USD
DEFAULT_USD = BalanceDimensions(denomination="USD")
ACCRUED_INTEREST_PAYABLE_USD = BalanceDimensions(
    address=current_account.tiered_interest_accrual.ACCRUED_INTEREST_PAYABLE,
    denomination="USD",
)
