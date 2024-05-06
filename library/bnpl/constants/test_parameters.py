# standard libs
from datetime import datetime
from zoneinfo import ZoneInfo

# library
import library.bnpl.constants.accounts as accounts
import library.bnpl.contracts.template.bnpl as bnpl

# inception sdk
from inception_sdk.test_framework.common import constants

# constants
default_simulation_start_date = datetime(year=2020, month=1, day=5, tzinfo=ZoneInfo("UTC"))

# for sim tests
default_internal_accounts = {
    "1": constants.LIABILITY,
    accounts.DUMMY_DEPOSITING: constants.LIABILITY,
    accounts.DEPOSIT: constants.LIABILITY,
    accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT: constants.LIABILITY,
}

# for e2e tests
internal_accounts_tside = {
    "TSIDE_ASSET": [],
    "TSIDE_LIABILITY": [
        "1",
        accounts.DUMMY_DEPOSITING,
        accounts.DEPOSIT,
        accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
    ],
}

# default parameters
bnpl_instance_params = {
    bnpl.disbursement.PARAM_PRINCIPAL: "120",
    bnpl.disbursement.PARAM_DEPOSIT_ACCOUNT: accounts.DEPOSIT,
    bnpl.lending_params.PARAM_TOTAL_REPAYMENT_COUNT: "4",
    bnpl.config_repayment_frequency.PARAM_REPAYMENT_FREQUENCY: "monthly",
}

bnpl_template_params = {
    bnpl.common_parameters.PARAM_DENOMINATION: constants.DEFAULT_DENOMINATION,
    bnpl.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_HOUR: "0",
    bnpl.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_MINUTE: "1",
    bnpl.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_SECOND: "0",
    bnpl.due_amount_notification.PARAM_NOTIFICATION_PERIOD: "2",
    bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_HOUR: "1",
    bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_MINUTE: "2",
    bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_SECOND: "3",
    bnpl.overdue.PARAM_REPAYMENT_PERIOD: "3",
    bnpl.overdue.PARAM_CHECK_OVERDUE_HOUR: "0",
    bnpl.overdue.PARAM_CHECK_OVERDUE_MINUTE: "1",
    bnpl.overdue.PARAM_CHECK_OVERDUE_SECOND: "0",
    bnpl.late_repayment.PARAM_LATE_REPAYMENT_FEE: "25",
    bnpl.late_repayment.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: (
        accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT
    ),
    bnpl.late_repayment.PARAM_CHECK_LATE_REPAYMENT_CHECK_HOUR: "0",
    bnpl.late_repayment.PARAM_CHECK_LATE_REPAYMENT_CHECK_MINUTE: "1",
    bnpl.late_repayment.PARAM_CHECK_LATE_REPAYMENT_CHECK_SECOND: "0",
    bnpl.delinquency.PARAM_GRACE_PERIOD: "2",
    bnpl.delinquency.PARAM_CHECK_DELINQUENCY_HOUR: "0",
    bnpl.delinquency.PARAM_CHECK_DELINQUENCY_MINUTE: "1",
    bnpl.delinquency.PARAM_CHECK_DELINQUENCY_SECOND: "0",
}

default_denomination = bnpl_template_params[bnpl.common_parameters.PARAM_DENOMINATION]


def replace_internal_account_with_dict_for_e2e(param_dict: dict) -> dict:
    """
    used for the e2e tests where the internal_account_key is needed
    """
    return {
        param: {"internal_account_key": value} if "_account" in param else value
        for param, value in param_dict.items()
    }


bnpl_template_params_for_e2e = replace_internal_account_with_dict_for_e2e(
    bnpl_template_params.copy()
)
