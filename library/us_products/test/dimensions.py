# library
from library.us_products.contracts.template import us_checking_account as us_checking_account
from library.us_products.test.parameters import TEST_DENOMINATION

# features
from library.features.v4.deposit import deposit_addresses

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

DEFAULT = BalanceDimensions(denomination=TEST_DENOMINATION)
ACCRUED_INTEREST_PAYABLE = BalanceDimensions(
    address=deposit_addresses.ACCRUED_INTEREST_PAYABLE, denomination=TEST_DENOMINATION
)
ACCRUED_INTEREST_RECEIVABLE = BalanceDimensions(
    address=deposit_addresses.ACCRUED_INTEREST_RECEIVABLE, denomination=TEST_DENOMINATION
)
OUTSTANDING_MONTHLY_PAPER_STATEMENT_FEE_TRACKER = BalanceDimensions(
    address=us_checking_account.paper_statement_fee.OUTSTANDING_MONTHLY_PAPER_STATEMENT_FEE_TRACKER,
    denomination=TEST_DENOMINATION,
)

OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER = BalanceDimensions(
    address=us_checking_account.maintenance_fees.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER,
    denomination=TEST_DENOMINATION,
)

OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER = BalanceDimensions(
    address=us_checking_account.minimum_monthly_balance.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
    denomination=TEST_DENOMINATION,
)

OUTSTANDING_INACTIVITY_FEE_TRACKER = BalanceDimensions(
    address=us_checking_account.inactivity_fee.OUTSTANDING_INACTIVITY_FEE_TRACKER,
    denomination=TEST_DENOMINATION,
)

DIRECT_DEPOSIT_TRACKER = BalanceDimensions(
    us_checking_account.direct_deposit_tracker.DIRECT_DEPOSIT_TRACKING_ADDRESS,
    denomination=TEST_DENOMINATION,
)
