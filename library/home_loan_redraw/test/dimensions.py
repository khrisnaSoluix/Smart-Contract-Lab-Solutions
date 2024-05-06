# library
import library.home_loan_redraw.contracts.template.home_loan_redraw as home_loan_redraw
from library.home_loan_redraw.test.parameters import TEST_DENOMINATION

# features
import library.features.v4.lending.lending_addresses as lending_addresses

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

DEFAULT = BalanceDimensions(denomination=TEST_DENOMINATION)
USD_DEFAULT = BalanceDimensions(denomination="USD")
PRINCIPAL = BalanceDimensions(address=lending_addresses.PRINCIPAL, denomination=TEST_DENOMINATION)

ACCRUED_INTEREST_RECEIVABLE = BalanceDimensions(
    address=lending_addresses.ACCRUED_INTEREST_RECEIVABLE, denomination=TEST_DENOMINATION
)
EMI = BalanceDimensions(address=lending_addresses.EMI, denomination=TEST_DENOMINATION)
INTEREST_DUE = BalanceDimensions(
    address=lending_addresses.INTEREST_DUE, denomination=TEST_DENOMINATION
)
INTERNAL_CONTRA = BalanceDimensions(
    address=lending_addresses.INTERNAL_CONTRA, denomination=TEST_DENOMINATION
)
PRINCIPAL_DUE = BalanceDimensions(
    address=lending_addresses.PRINCIPAL_DUE, denomination=TEST_DENOMINATION
)

REDRAW = BalanceDimensions(
    address=home_loan_redraw.redraw.REDRAW_ADDRESS, denomination=TEST_DENOMINATION
)
