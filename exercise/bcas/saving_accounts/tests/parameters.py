# library
from decimal import Decimal
import projects.gundala_s.time_deposit.contracts.template.time_depo_mudharabah as time_deposit
import library.features.v4.shariah.profit_application as profit_application
import library.features.v4.shariah.fixed_profit_accrual as fixed_profit_accrual
import library.features.v4.deposit.deposit_maturity_mdh as deposit_maturity_mdh
import library.features.v4.deposit.deposit_parameters as deposit_parameters

# Constants
PRODUCT_NAME = "TIME_DEPOSIT"
TEST_DENOMINATION = "IDR"

# Default Parameters
time_deposit_instance_params: dict[str, str] = {
    deposit_parameters.PARAM_TERM:"6",
    deposit_parameters.PARAM_ACTIVATION_DATE:"2022-01-07",
    time_deposit.PARAM_SUBPRODUCT: "MDH MUTLAQ NB",
    profit_application.PARAM_ZAKAT_RATE:"0.1",
    fixed_profit_accrual.PARAM_NISBAH:"0.1",
    fixed_profit_accrual.PARAM_EXPECTED_DEPOSIT_AMOUNT:"8000000",
    deposit_maturity_mdh.PARAM_DISPOSITION_TYPE:"aro",
    fixed_profit_accrual.PARAM_EARLY_WITHDRAWAL_GROSS_DISTRIBUTION_RATE:"0.1",
    fixed_profit_accrual.PARAM_PENALTY_DAYS:"0",
}

time_deposit_template_params: dict[str, str] = {
    time_deposit.PARAM_NUMBER_OF_PROFIT_SHARING_DAYS_EARLY_WITHDRAWAL_FEE: "0",
    time_deposit.PARAM_DENOMINATION: TEST_DENOMINATION,
    profit_application.PARAM_APPLICATION_PRECISION:"2",
    profit_application.PARAM_PROFIT_PAID_ACCOUNT:"PROFIT_PAID_ACCOUNT",
    profit_application.PARAM_PROFIT_APPLICATION_FREQUENCY:"monthly",
    profit_application.PARAM_PROFIT_APPLICATION_HOUR:"0",
    profit_application.PARAM_PROFIT_APPLICATION_MINUTE:"1",
    profit_application.PARAM_PROFIT_APPLICATION_SECOND:"0",
    profit_application.PARAM_ZAKAT_RECEIVABLE_ACOUNT:"ZAKAT_RECEIVABLE_ACOUNT",
    profit_application.PARAM_TAX_RECEIVABLE_ACOUNT:"TAX_RECEIVABLE_ACOUNT",

    fixed_profit_accrual.PARAM_ACCRUAL_PRECISION:"6",
    fixed_profit_accrual.PARAM_ACCRUED_PROFIT_PAYABLE_ACCOUNT:"ACCRUED_PROFIT_PAYABLE_ACCOUNT",
    fixed_profit_accrual.PARAM_DAYS_IN_YEAR:"actual",
    fixed_profit_accrual.PARAM_PROFIT_ACCRUAL_HOUR:"0",
    fixed_profit_accrual.PARAM_PROFIT_ACCRUAL_MINUTE:"1",
    fixed_profit_accrual.PARAM_PROFIT_ACCRUAL_SECOND:"0",
    deposit_maturity_mdh.PARAM_MATURITY_NOTICE_PERIOD:"7",
    deposit_maturity_mdh.PARAM_DISBURSEMENT_ACCOUNT:"DISBURSEMENT_ACCOUNT",
    deposit_parameters.PARAM_TERM_UNIT:"months",
}