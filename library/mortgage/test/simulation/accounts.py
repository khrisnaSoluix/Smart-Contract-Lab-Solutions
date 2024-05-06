# library
from library.mortgage.test import accounts

# inception sdk
from inception_sdk.test_framework.common import constants

# internal accounts for simulation
default_internal_accounts: dict[str, str] = {
    accounts.DEPOSIT_ACCOUNT: constants.LIABILITY,
    accounts.INTERNAL_ACCOUNT: constants.LIABILITY,
    accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: constants.ASSET,
    accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE_ACCOUNT: constants.ASSET,
    accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT: constants.LIABILITY,
    accounts.INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT: constants.LIABILITY,
    accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: constants.LIABILITY,
    # accounts.INTERNAL_CAPITALISED_PENALTIES_RECEIVED_ACCOUNT: constants.LIABILITY,
    accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: constants.LIABILITY,
    accounts.INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT: constants.LIABILITY,
    accounts.INTERNAL_EARLY_REPAYMENT_FEE_INCOME_ACCOUNT: constants.LIABILITY,
}
