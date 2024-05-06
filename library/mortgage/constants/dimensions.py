# common
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
)

# other
import library.mortgage.constants.addresses as address

# Default Denomination
DEFAULT_DENOMINATION = "AUD"

# Dimensions
PRINCIPAL = BalanceDimensions(address=address.PRINCIPAL, denomination=DEFAULT_DENOMINATION)
ACCRUED_EXPECTED_INTEREST = BalanceDimensions(
    address=address.ACCRUED_EXPECTED_INTEREST,
    denomination=DEFAULT_DENOMINATION,
)
ACCRUED_INTEREST_RECEIVABLE = BalanceDimensions(
    address=address.ACCRUED_INTEREST_RECEIVABLE, denomination=DEFAULT_DENOMINATION
)
INTEREST_DUE = BalanceDimensions(address=address.INTEREST_DUE, denomination=DEFAULT_DENOMINATION)
PRINCIPAL_DUE = BalanceDimensions(address=address.PRINCIPAL_DUE, denomination=DEFAULT_DENOMINATION)
OVERPAYMENT = BalanceDimensions(address=address.OVERPAYMENT, denomination=DEFAULT_DENOMINATION)
EMI_PRINCIPAL_EXCESS = BalanceDimensions(
    address=address.EMI_PRINCIPAL_EXCESS, denomination=DEFAULT_DENOMINATION
)
INTEREST_OVERDUE = BalanceDimensions(
    address=address.INTEREST_OVERDUE, denomination=DEFAULT_DENOMINATION
)
PRINCIPAL_OVERDUE = BalanceDimensions(
    address=address.PRINCIPAL_OVERDUE, denomination=DEFAULT_DENOMINATION
)
PENALTIES = BalanceDimensions(address=address.PENALTIES, denomination=DEFAULT_DENOMINATION)
EMI_ADDRESS = BalanceDimensions(address=address.EMI_ADDRESS, denomination=DEFAULT_DENOMINATION)
INTERNAL_CONTRA = BalanceDimensions(
    address=address.INTERNAL_CONTRA, denomination=DEFAULT_DENOMINATION
)
DEFAULT = BalanceDimensions(denomination=DEFAULT_DENOMINATION)
OUTGOING = BalanceDimensions(
    address=DEFAULT_ADDRESS,
    asset=DEFAULT_ASSET,
    denomination=DEFAULT_DENOMINATION,
    phase="POSTING_PHASE_PENDING_OUTGOING",
)

INCOMING = BalanceDimensions(
    address=DEFAULT_ADDRESS,
    asset=DEFAULT_ASSET,
    denomination=DEFAULT_DENOMINATION,
    phase="POSTING_PHASE_PENDING_INCOMING",
)
