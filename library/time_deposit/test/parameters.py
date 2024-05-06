# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test import accounts

# Constants
PRODUCT_NAME = "TIME_DEPOSIT"
TEST_DENOMINATION = "GBP"

# Default Parameters
time_deposit_instance_params: dict[str, str] = {
    time_deposit.deposit_parameters.PARAM_TERM: "4",
    time_deposit.fixed_interest_accrual.PARAM_FIXED_INTEREST_RATE: "0.01",
    time_deposit.interest_application.PARAM_INTEREST_APPLICATION_DAY: "12",
    time_deposit.withdrawal_fees.PARAM_FEE_FREE_WITHDRAWAL_PERCENTAGE_LIMIT: "0",
}

time_deposit_template_params: dict[str, str] = {
    time_deposit.PARAM_NUMBER_OF_INTEREST_DAYS_EARLY_WITHDRAWAL_FEE: "0",
    time_deposit.common_parameters.PARAM_DENOMINATION: TEST_DENOMINATION,
    time_deposit.cooling_off_period.PARAM_COOLING_OFF_PERIOD: "2",
    time_deposit.deposit_maturity.PARAM_MATURITY_NOTICE_PERIOD: "1",
    time_deposit.deposit_parameters.PARAM_TERM_UNIT: "months",
    time_deposit.deposit_period.PARAM_DEPOSIT_PERIOD: "5",
    time_deposit.deposit_period.PARAM_NUMBER_OF_PERMITTED_DEPOSITS: "unlimited",
    time_deposit.fixed_interest_accrual.PARAM_ACCRUAL_PRECISION: "5",
    time_deposit.fixed_interest_accrual.PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT
    ),
    time_deposit.fixed_interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    ),
    time_deposit.fixed_interest_accrual.PARAM_DAYS_IN_YEAR: "365",
    time_deposit.fixed_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "0",
    time_deposit.fixed_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "0",
    time_deposit.fixed_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "1",
    time_deposit.grace_period.PARAM_GRACE_PERIOD: "0",
    time_deposit.interest_application.PARAM_APPLICATION_PRECISION: "2",
    time_deposit.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: "monthly",
    time_deposit.interest_application.PARAM_INTEREST_APPLICATION_HOUR: "0",
    time_deposit.interest_application.PARAM_INTEREST_APPLICATION_MINUTE: "1",
    time_deposit.interest_application.PARAM_INTEREST_APPLICATION_SECOND: "0",
    time_deposit.interest_application.PARAM_INTEREST_PAID_ACCOUNT: accounts.INTEREST_PAID_ACCOUNT,
    time_deposit.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTEREST_RECEIVED_ACCOUNT
    ),
    time_deposit.maximum_balance_limit.PARAM_MAXIMUM_BALANCE: "50000.00",
    time_deposit.minimum_initial_deposit.PARAM_MIN_INITIAL_DEPOSIT: "40",
    time_deposit.withdrawal_fees.PARAM_EARLY_WITHDRAWAL_FLAT_FEE: "10",
    time_deposit.withdrawal_fees.PARAM_EARLY_WITHDRAWAL_PERCENTAGE_FEE: "0.01",
    time_deposit.withdrawal_fees.PARAM_MAXIMUM_WITHDRAWAL_PERCENTAGE_LIMIT: "1",
}

renewed_time_deposit_template_params = {
    **time_deposit_template_params,
    time_deposit.grace_period.PARAM_GRACE_PERIOD: "1",
}
