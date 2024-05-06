# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.

# third party
import requests

# library
from library.bnpl.constants import dimensions, files, test_parameters
from library.bnpl.contracts.template import bnpl

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = test_parameters.internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "bnpl": {
        "path": files.BNPL_CONTRACT,
        "template_params": test_parameters.bnpl_template_params_for_e2e,
    },
    "dummy_account": {"path": DUMMY_CONTRACT},
}


class BNPLTest(endtoend.End2Endtest):
    def test_check_principal_disbursement_and_emi_in_advance(self):
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = {
            **test_parameters.bnpl_instance_params,
            bnpl.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
        }

        bnpl_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="bnpl",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        bnpl_account = endtoend.contracts_helper.get_account(bnpl_account_id)

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                bnpl_account_id: [
                    (dimensions.DEFAULT, "0"),
                    (dimensions.PRINCIPAL, "90"),
                    (dimensions.PRINCIPAL_DUE, "30"),
                    (dimensions.INTEREST_DUE, "0"),
                    (dimensions.EMI, "30"),
                    (dimensions.INTEREST_OVERDUE, "0"),
                    (dimensions.PRINCIPAL_OVERDUE, "0"),
                    (dimensions.PENALTIES, "0"),
                ],
                dummy_account_id: [(dimensions.DEFAULT, "120")],
            }
        )
        self.assertEqual("ACCOUNT_STATUS_OPEN", bnpl_account["status"])

    def test_overpayment_is_rejected(self):
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = {
            **test_parameters.bnpl_instance_params,
            bnpl.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
        }

        bnpl_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="bnpl",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        bnpl_account = endtoend.contracts_helper.get_account(bnpl_account_id)

        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=bnpl_account_id,
            amount="31",
            denomination=test_parameters.default_denomination,
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])
        self.assertEqual("ACCOUNT_STATUS_OPEN", bnpl_account["status"])

    def test_restricted_parameter_change_is_rejected(self):
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = {
            **test_parameters.bnpl_instance_params,
            bnpl.disbursement.PARAM_DEPOSIT_ACCOUNT: dummy_account_id,
        }

        bnpl_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="bnpl",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        endtoend.contracts_helper.get_account(bnpl_account_id)

        # Update principal value of loan
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            endtoend.core_api_helper.update_account_instance_parameters(
                bnpl_account_id,
                instance_param_vals={"principal": "1000"},
            )

        self.assertEqual(400, context.exception.response.status_code)
