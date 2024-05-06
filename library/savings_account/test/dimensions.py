# library
from library.savings_account.contracts.template import savings_account
from library.savings_account.test.parameters import TEST_DENOMINATION

# features
import library.features.v4.common.addresses as common_addresses

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

# Dimensions
ACCRUED_INTEREST_PAYABLE = BalanceDimensions(
    address=savings_account.tiered_interest_accrual.ACCRUED_INTEREST_PAYABLE,
    denomination=TEST_DENOMINATION,
)
ACCRUED_INTEREST_RECEIVABLE = BalanceDimensions(
    address=savings_account.tiered_interest_accrual.ACCRUED_INTEREST_RECEIVABLE,
    denomination=TEST_DENOMINATION,
)
OUTSTANDING_INACTIVITY_FEE_TRACKER = BalanceDimensions(
    address=savings_account.inactivity_fee.OUTSTANDING_INACTIVITY_FEE_TRACKER,
    denomination=TEST_DENOMINATION,
)
OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER = BalanceDimensions(
    address=savings_account.minimum_monthly_balance.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
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
