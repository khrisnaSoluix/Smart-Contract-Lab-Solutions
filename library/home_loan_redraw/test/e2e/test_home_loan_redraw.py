# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.

# library
from library.home_loan_redraw.test import dimensions, files, parameters
from library.home_loan_redraw.test.e2e import accounts, parameters as e2e_parameters

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = accounts.internal_accounts_tside

HOME_LOAN_REDRAW = e2e_parameters.HOME_LOAN_REDRAW

endtoend.testhandle.CONTRACTS = {
    HOME_LOAN_REDRAW: {
        "path": files.HOME_LOAN_REDRAW_CONTRACT,
        "template_params": e2e_parameters.default_template,
    },
    "dummy_account": {"path": DUMMY_CONTRACT},
}


class HomeLoanRedrawTest(endtoend.End2Endtest):
    def test_principal_disbursement(self):
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = e2e_parameters.default_instance.copy()
        instance_params["deposit_account"] = dummy_account_id

        home_loan_redraw_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract=HOME_LOAN_REDRAW,
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                home_loan_redraw_account_id: [
                    (dimensions.PRINCIPAL, "800000"),
                    (dimensions.EMI, "67391.09"),
                ],
                dummy_account_id: [(dimensions.DEFAULT, "800000")],
            }
        )

    def test_pre_posting_validation_and_redraw(self):
        cust_id = endtoend.core_api_helper.create_customer()

        dummy_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        instance_params = e2e_parameters.default_instance.copy()
        instance_params["deposit_account"] = dummy_account_id

        home_loan_redraw_account_id = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract=HOME_LOAN_REDRAW,
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )["id"]

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                home_loan_redraw_account_id: [
                    (dimensions.PRINCIPAL, "800000"),
                    (dimensions.EMI, "67391.09"),
                ],
                dummy_account_id: [(dimensions.DEFAULT, "800000")],
            }
        )

        # validate wrong denominations are rejected
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=home_loan_redraw_account_id, amount="9001", denomination="GBP"
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # validate non hard settlements are rejected
        posting_id = endtoend.postings_helper.outbound_auth(
            account_id=home_loan_redraw_account_id,
            amount="9001",
            denomination=parameters.TEST_DENOMINATION,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # validate overpayment greater than the remaining debt is rejected
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=home_loan_redraw_account_id,
            amount="810000",
            denomination=parameters.TEST_DENOMINATION,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # make overpayment and ensure it is rebalanced into redraw
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=home_loan_redraw_account_id,
            amount="10000",
            denomination=parameters.TEST_DENOMINATION,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                home_loan_redraw_account_id: [(dimensions.REDRAW, "-10000")],
            }
        )

        # validate withdrawal < total redraw funds is accepted
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=home_loan_redraw_account_id,
            amount="1000",
            denomination=parameters.TEST_DENOMINATION,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                home_loan_redraw_account_id: [(dimensions.REDRAW, "-9000")],
            }
        )

        # validate withdrawal > total redraw funds is rejected
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=home_loan_redraw_account_id,
            amount="9001",
            denomination=parameters.TEST_DENOMINATION,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # validate withdrawal > total redraw funds with force_override is accepted
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=home_loan_redraw_account_id,
            amount="9001",
            denomination=parameters.TEST_DENOMINATION,
            instruction_details={"force_override": "true"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                home_loan_redraw_account_id: [(dimensions.REDRAW, "1")],
            }
        )
