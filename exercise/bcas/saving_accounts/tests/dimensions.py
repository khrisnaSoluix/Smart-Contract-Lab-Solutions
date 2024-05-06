# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test.parameters import TEST_DENOMINATION

# features
import library.features.v4.common.addresses as common_addresses
import library.features.v4.deposit.deposit_addresses as deposit_addresses

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

# Dimensions
DEFAULT = BalanceDimensions(denomination=TEST_DENOMINATION)
ACCRUED_INTEREST_PAYABLE = BalanceDimensions(
    address=deposit_addresses.ACCRUED_INTEREST_PAYABLE, denomination=TEST_DENOMINATION
)
ACCRUED_INTEREST_RECEIVABLE = BalanceDimensions(
    address=deposit_addresses.ACCRUED_INTEREST_RECEIVABLE, denomination=TEST_DENOMINATION
)
APPLIED_INTEREST_TRACKER = BalanceDimensions(
    address=time_deposit.APPLIED_INTEREST_TRACKER, denomination=TEST_DENOMINATION
)
EARLY_WITHDRAWALS_TRACKER = BalanceDimensions(
    address=time_deposit.withdrawal_fees.EARLY_WITHDRAWALS_TRACKER,
    denomination=TEST_DENOMINATION,
)
INTERNAL_CONTRA = BalanceDimensions(
    common_addresses.INTERNAL_CONTRA, denomination=TEST_DENOMINATION
)

# Dimensions JPY
DEFAULT_JPY = BalanceDimensions(denomination="JPY")
