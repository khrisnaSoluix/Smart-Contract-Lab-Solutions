# library
from library.loan.test import accounts

# inception sdk
from inception_sdk.test_framework.common import constants

# internal accounts for simulation
default_internal_accounts: dict[str, str] = {
    accounts.DEPOSIT: constants.LIABILITY,
    accounts.INTERNAL: constants.LIABILITY,
    accounts.INTERNAL_ACCRUED_INTEREST_RECEIVABLE: constants.ASSET,
    accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVABLE: constants.ASSET,
    accounts.INTERNAL_INTEREST_RECEIVED: constants.LIABILITY,
    accounts.INTERNAL_CAPITALISED_INTEREST_RECEIVED: constants.LIABILITY,
    accounts.INTERNAL_CAPITALISED_PENALTIES_RECEIVED: constants.LIABILITY,
    accounts.INTERNAL_PENALTY_INTEREST_RECEIVED: constants.LIABILITY,
    accounts.INTERNAL_EARLY_REPAYMENT_FEE_INCOME: constants.LIABILITY,
    accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME: constants.LIABILITY,
    accounts.INTERNAL_OVERPAYMENT_FEE_INCOME: constants.LIABILITY,
    accounts.INTERNAL_UPFRONT_FEE_INCOME: constants.LIABILITY,
}
