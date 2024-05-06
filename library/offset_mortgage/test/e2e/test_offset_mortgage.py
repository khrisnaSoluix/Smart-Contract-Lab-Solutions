# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# library
import library.mortgage.test.e2e.accounts as mortgage_test_accounts
import library.mortgage.test.e2e.parameters as mortgage_test_parameters
import library.offset_mortgage.test.files as files
from library.current_account.test.e2e import (
    accounts as ca_accounts,
    parameters as ca_test_parameters,
)
from library.mortgage.contracts.template import mortgage
from library.savings_account.test.e2e import (
    accounts as sa_accounts,
    parameters as sa_test_parameters,
)

# inception sdk
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = {
    "TSIDE_ASSET": [
        *mortgage_test_accounts.internal_accounts_tside["TSIDE_ASSET"],
        *ca_accounts.internal_accounts_tside["TSIDE_ASSET"],
        *sa_accounts.internal_accounts_tside["TSIDE_ASSET"],
    ],
    "TSIDE_LIABILITY": [
        *mortgage_test_accounts.internal_accounts_tside["TSIDE_LIABILITY"],
        *ca_accounts.internal_accounts_tside["TSIDE_LIABILITY"],
        *sa_accounts.internal_accounts_tside["TSIDE_LIABILITY"],
    ],
}

endtoend.testhandle.CONTRACTS = {
    "mortgage": {
        "path": files.MORTGAGE_CONTRACT,
        "template_params": mortgage_test_parameters.default_template.copy(),
    },
    "current_account": {
        "path": files.CURRENT_ACCOUNT_CONTRACT,
        "template_params": ca_test_parameters.default_template.copy(),
    },
    "savings_account": {
        "path": files.SAVINGS_ACCOUNT_CONTRACT,
        "template_params": sa_test_parameters.default_template.copy(),
    },
    "dummy_account": {
        "path": DUMMY_CONTRACT,
    },
}

endtoend.testhandle.SUPERVISORCONTRACTS = {
    "offset_mortgage": {"path": files.OFFSET_MORTGAGE_SUPERVISOR_CONTRACT}
}


endtoend.testhandle.FLAG_DEFINITIONS = {
    # Mortgage
    "ACCOUNT_DELINQUENT": "library/common/flag_definitions/account_delinquent.resource.yaml",
    "REPAYMENT_HOLIDAY": "library/common/flag_definitions/repayment_holiday.resource.yaml",
    # CA/SA
    "ACCOUNT_DORMANT": "library/common/flag_definitions/account_dormant.resource.yaml",
}


class OffsetMortgageTest(endtoend.End2Endtest):
    def test_offset_mortgage_creation(self):
        cust_id = endtoend.core_api_helper.create_customer()
        deposit_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        mortgage_instance_params = {
            **mortgage_test_parameters.default_instance,
            mortgage.disbursement.PARAM_DEPOSIT_ACCOUNT: deposit_account_id,
        }

        mortgage_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="mortgage",
            instance_param_vals=mortgage_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        mortgage_account_id = mortgage_account["id"]

        current_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="current_account",
            instance_param_vals=ca_test_parameters.default_instance,
            status="ACCOUNT_STATUS_OPEN",
        )
        current_account_id = current_account["id"]

        savings_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="savings_account",
            instance_param_vals=sa_test_parameters.default_instance,
            status="ACCOUNT_STATUS_OPEN",
        )
        savings_account_id = savings_account["id"]

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "offset_mortgage", [mortgage_account_id, current_account_id, savings_account_id]
        )

        endtoend.supervisors_helper.check_plan_associations(
            self, plan_id, [mortgage_account_id, current_account_id, savings_account_id]
        )
