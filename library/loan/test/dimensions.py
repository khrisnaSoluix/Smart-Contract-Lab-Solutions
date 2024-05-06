# library
import library.loan.contracts.template.loan as loan
from library.loan.test.parameters import TEST_DENOMINATION

# features
import library.features.v4.lending.lending_addresses as lending_addresses

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

DEFAULT = BalanceDimensions(denomination=TEST_DENOMINATION)
USD_DEFAULT = BalanceDimensions(denomination="USD")
PRINCIPAL = BalanceDimensions(address=lending_addresses.PRINCIPAL, denomination=TEST_DENOMINATION)

ACCRUED_EXPECTED_INTEREST = BalanceDimensions(
    address=loan.overpayment.ACCRUED_EXPECTED_INTEREST, denomination=TEST_DENOMINATION
)
ACCRUED_INTEREST_RECEIVABLE = BalanceDimensions(
    address=lending_addresses.ACCRUED_INTEREST_RECEIVABLE, denomination=TEST_DENOMINATION
)
ACCRUED_INTEREST_PENDING_CAPITALISATION = BalanceDimensions(
    address=loan.ACCRUED_INTEREST_PENDING_CAPITALISATION, denomination=TEST_DENOMINATION
)
ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION = BalanceDimensions(
    address=loan.ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION,
    denomination=TEST_DENOMINATION,
)
CAPITALISED_INTEREST_TRACKER = BalanceDimensions(
    address=loan.CAPITALISED_INTEREST_TRACKER,
    denomination=TEST_DENOMINATION,
)
CAPITALISED_PENALTIES_TRACKER = BalanceDimensions(
    address=loan.CAPITALISED_PENALTIES_TRACKER,
    denomination=TEST_DENOMINATION,
)
DUE_CALCULATION_EVENT_COUNTER = BalanceDimensions(
    address=lending_addresses.DUE_CALCULATION_EVENT_COUNTER, denomination=TEST_DENOMINATION
)
EMI = BalanceDimensions(address=lending_addresses.EMI, denomination=TEST_DENOMINATION)
EMI_PRINCIPAL_EXCESS = BalanceDimensions(
    address=loan.overpayment.EMI_PRINCIPAL_EXCESS, denomination=TEST_DENOMINATION
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
MONTHLY_REST_EFFECTIVE_PRINCIPAL = BalanceDimensions(
    address=loan.MONTHLY_REST_EFFECTIVE_PRINCIPAL,
    denomination=TEST_DENOMINATION,
)
OVERPAYMENT = BalanceDimensions(
    address=loan.overpayment.OVERPAYMENT, denomination=TEST_DENOMINATION
)
OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER = BalanceDimensions(
    address=loan.overpayment.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
    denomination=TEST_DENOMINATION,
)
PENALTIES = BalanceDimensions(address=lending_addresses.PENALTIES, denomination=TEST_DENOMINATION)
PRINCIPAL_DUE = BalanceDimensions(
    address=lending_addresses.PRINCIPAL_DUE, denomination=TEST_DENOMINATION
)
PRINCIPAL_OVERDUE = BalanceDimensions(
    address=lending_addresses.PRINCIPAL_OVERDUE, denomination=TEST_DENOMINATION
)
