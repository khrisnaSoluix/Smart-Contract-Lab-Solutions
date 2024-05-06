# library
import library.mortgage.contracts.template.mortgage as mortgage
from library.mortgage.test.parameters import TEST_DENOMINATION

# features
import library.features.v4.lending.lending_addresses as lending_addresses

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

DEFAULT = BalanceDimensions(denomination=TEST_DENOMINATION)
USD_DEFAULT = BalanceDimensions(denomination="USD")
PRINCIPAL = BalanceDimensions(address=lending_addresses.PRINCIPAL, denomination=TEST_DENOMINATION)

ACCRUED_EXPECTED_INTEREST = BalanceDimensions(
    address=mortgage.overpayment.ACCRUED_EXPECTED_INTEREST, denomination=TEST_DENOMINATION
)
ACCRUED_INTEREST_RECEIVABLE = BalanceDimensions(
    address=lending_addresses.ACCRUED_INTEREST_RECEIVABLE, denomination=TEST_DENOMINATION
)
ACCRUED_INTEREST_PENDING_CAPITALISATION = BalanceDimensions(
    address=mortgage.ACCRUED_INTEREST_PENDING_CAPITALISATION, denomination=TEST_DENOMINATION
)
ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION = BalanceDimensions(
    address=mortgage.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
    denomination=TEST_DENOMINATION,
)
CAPITALISED_INTEREST_TRACKER = BalanceDimensions(
    address=mortgage.CAPITALISED_INTEREST_TRACKER,
    denomination=TEST_DENOMINATION,
)
DUE_CALCULATION_EVENT_COUNTER = BalanceDimensions(
    address=lending_addresses.DUE_CALCULATION_EVENT_COUNTER
)
EMI = BalanceDimensions(address=lending_addresses.EMI, denomination=TEST_DENOMINATION)
EMI_PRINCIPAL_EXCESS = BalanceDimensions(
    address=mortgage.overpayment.EMI_PRINCIPAL_EXCESS, denomination=TEST_DENOMINATION
)
INTEREST_DUE = BalanceDimensions(
    address=lending_addresses.INTEREST_DUE, denomination=TEST_DENOMINATION
)
INTEREST_OVERDUE = BalanceDimensions(
    address=lending_addresses.INTEREST_OVERDUE, denomination=TEST_DENOMINATION
)
INTERNAL_CONTRA = BalanceDimensions(
    address=lending_addresses.INTERNAL_CONTRA, denomination=TEST_DENOMINATION
)
OVERPAYMENT = BalanceDimensions(
    address=mortgage.overpayment.OVERPAYMENT, denomination=TEST_DENOMINATION
)
OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER = BalanceDimensions(
    address=mortgage.overpayment.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
    denomination=TEST_DENOMINATION,
)
REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER = BalanceDimensions(
    address=mortgage.overpayment_allowance.REMAINING_OVERPAYMENT_ALLOWANCE_TRACKER,
    denomination=TEST_DENOMINATION,
)
PENALTIES = BalanceDimensions(address=lending_addresses.PENALTIES, denomination=TEST_DENOMINATION)
PRINCIPAL_DUE = BalanceDimensions(
    address=lending_addresses.PRINCIPAL_DUE, denomination=TEST_DENOMINATION
)
PRINCIPAL_OVERDUE = BalanceDimensions(
    address=lending_addresses.PRINCIPAL_OVERDUE, denomination=TEST_DENOMINATION
)
