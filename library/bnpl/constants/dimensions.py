# library
from library.bnpl.constants.test_parameters import default_denomination

# features
import library.features.v4.lending.lending_addresses as lending_addresses

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

DEFAULT = BalanceDimensions(denomination=default_denomination)
USD_DEFAULT = BalanceDimensions(denomination="USD")
INTERNAL_CONTRA = BalanceDimensions(
    lending_addresses.INTERNAL_CONTRA, denomination=default_denomination
)

EMI = BalanceDimensions(lending_addresses.EMI, denomination=default_denomination)
PRINCIPAL = BalanceDimensions(lending_addresses.PRINCIPAL, denomination=default_denomination)
PRINCIPAL_OVERDUE = BalanceDimensions(
    lending_addresses.PRINCIPAL_OVERDUE, denomination=default_denomination
)
INTEREST_OVERDUE = BalanceDimensions(
    lending_addresses.INTEREST_OVERDUE, denomination=default_denomination
)
PENALTIES = BalanceDimensions(lending_addresses.PENALTIES, denomination=default_denomination)
PRINCIPAL_DUE = BalanceDimensions(
    lending_addresses.PRINCIPAL_DUE, denomination=default_denomination
)
INTEREST_DUE = BalanceDimensions(lending_addresses.INTEREST_DUE, denomination=default_denomination)
DUE_CALCULATION_EVENT_COUNTER = BalanceDimensions(
    address=lending_addresses.DUE_CALCULATION_EVENT_COUNTER, denomination=default_denomination
)
