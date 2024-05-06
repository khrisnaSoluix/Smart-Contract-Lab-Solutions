# common
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

import inception_sdk.test_framework.common.constants as constants
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
)
import library.loan.constants.addresses as address

# Dimensions
PRINCIPAL = BalanceDimensions(
    address=address.PRINCIPAL, denomination=constants.DEFAULT_DENOMINATION
)
PRINCIPAL_CAPITALISED_INTEREST = BalanceDimensions(
    address=address.PRINCIPAL_CAPITALISED_INTEREST,
    denomination=constants.DEFAULT_DENOMINATION,
)
PRINCIPAL_CAPITALISED_PENALTIES = BalanceDimensions(
    address=address.PRINCIPAL_CAPITALISED_PENALTIES,
    denomination=constants.DEFAULT_DENOMINATION,
)
ACCRUED_EXPECTED_INTEREST = BalanceDimensions(
    address=address.ACCRUED_EXPECTED_INTEREST,
    denomination=constants.DEFAULT_DENOMINATION,
)
ACCRUED_INTEREST = BalanceDimensions(
    address=address.ACCRUED_INTEREST, denomination=constants.DEFAULT_DENOMINATION
)
CAPITALISED_INTEREST = BalanceDimensions(
    address=address.CAPITALISED_INTEREST, denomination=constants.DEFAULT_DENOMINATION
)
ACCRUED_INTEREST_PENDING_CAPITALISATION = BalanceDimensions(
    address=address.ACCRUED_INTEREST_PENDING_CAPITALISATION,
    denomination=constants.DEFAULT_DENOMINATION,
)
ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION = BalanceDimensions(
    address=address.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
    denomination=constants.DEFAULT_DENOMINATION,
)
INTEREST_DUE = BalanceDimensions(
    address=address.INTEREST_DUE, denomination=constants.DEFAULT_DENOMINATION
)
PRINCIPAL_DUE = BalanceDimensions(
    address=address.PRINCIPAL_DUE, denomination=constants.DEFAULT_DENOMINATION
)
OVERPAYMENT = BalanceDimensions(
    address=address.OVERPAYMENT, denomination=constants.DEFAULT_DENOMINATION
)
EMI_PRINCIPAL_EXCESS = BalanceDimensions(
    address=address.EMI_PRINCIPAL_EXCESS, denomination=constants.DEFAULT_DENOMINATION
)
INTEREST_OVERDUE = BalanceDimensions(
    address=address.INTEREST_OVERDUE, denomination=constants.DEFAULT_DENOMINATION
)
PRINCIPAL_OVERDUE = BalanceDimensions(
    address=address.PRINCIPAL_OVERDUE, denomination=constants.DEFAULT_DENOMINATION
)
PENALTIES = BalanceDimensions(
    address=address.PENALTIES, denomination=constants.DEFAULT_DENOMINATION
)
EMI_ADDRESS = BalanceDimensions(
    address=address.EMI_ADDRESS, denomination=constants.DEFAULT_DENOMINATION
)
INTERNAL_CONTRA = BalanceDimensions(
    address=address.INTERNAL_CONTRA, denomination=constants.DEFAULT_DENOMINATION
)
DEFAULT = BalanceDimensions(denomination=constants.DEFAULT_DENOMINATION)
OUTGOING = BalanceDimensions(
    address=DEFAULT_ADDRESS,
    asset=DEFAULT_ASSET,
    denomination=constants.DEFAULT_DENOMINATION,
    phase="POSTING_PHASE_PENDING_OUTGOING",
)

INCOMING = BalanceDimensions(
    address=DEFAULT_ADDRESS,
    asset=DEFAULT_ASSET,
    denomination=constants.DEFAULT_DENOMINATION,
    phase="POSTING_PHASE_PENDING_INCOMING",
)
