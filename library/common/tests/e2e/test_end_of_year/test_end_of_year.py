# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
import inception_sdk.test_framework.endtoend as endtoend
import time
import uuid

from library.common.tests.e2e.common_test_params import (
    internal_accounts_tside,
)

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "dummy_account": {"path": DUMMY_CONTRACT},
    "pnl": {
        "path": "library/common/internal_accounts/contracts/liability_account_contract.py",
        "is_internal": True,
    },
}

endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"},
    "interest": {"path": "library/common/contract_modules/interest.py"},
}

endtoend.testhandle.WORKFLOWS = {
    "INTERNAL_ACCOUNT_CREATION": "library/common/workflows/internal_account_creation.yaml",
    "POSTING_CREATION": "library/common/workflows/posting_creation.yaml",
}

endtoend.testhandle.ACCOUNT_SCHEDULE_TAGS = {}

endtoend.testhandle.FLAG_DEFINITIONS = {}

DEFAULT_DIMENSIONS = endtoend.balances_helper.BalanceDimensions(
    address="DEFAULT", denomination="GBP"
)


class EndOfYearTesting(endtoend.End2Endtest):
    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at
        # Uncomment this for timing info.
        # print('\n{} ({}s)'.format(self.id().rpartition('.')[2], round(self._elapsed_time, 2)))

    def test_internal_account_creation_valid_input(self):
        """
        Tests that an internal account gets created successfully using the
        INTERNAL_ACCOUNT_CREATION workflow
        """

        # Create an internal account
        wf_id = endtoend.workflows_helper.start_workflow("INTERNAL_ACCOUNT_CREATION", context={})

        internal_account_id = str(uuid.uuid4())

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_account_parameters",
            event_name="account_input_captured",
            context={
                "internal_account_ID": internal_account_id,
                "product_ID": endtoend.testhandle.internal_contract_pid_to_uploaded_pid["pnl"],
                "permitted_denominations": "GBP",
                "account_tside": "TSIDE_LIABILITY",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_metadata_key_values",
            event_name="confirm_metadata",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        internal_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]

        internal_account = endtoend.contracts_helper.get_internal_account(internal_account_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", internal_account["status"])

    def test_transfer_funds_between_accounts(self):
        """
        Tests that a user can create a custom instruction for transferring funds between accounts
        """

        cust_id = endtoend.core_api_helper.create_customer()
        debitor_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=debitor_account["id"], amount="10", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        creditor_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            {debitor_account["id"]: [(DEFAULT_DIMENSIONS, "10")]}
        )

        wf_id = endtoend.workflows_helper.start_workflow("POSTING_CREATION", context={})

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_input",
            event_name="transfer_details_captured",
            context={
                "debtor_target_account_id": debitor_account["id"],
                "debtor_target_account_address": "DEFAULT",
                "creditor_target_account_id": creditor_account["id"],
                "creditor_target_account_address": "DEFAULT",
                "denomination": "GBP",
                "phase": "POSTING_PHASE_COMMITTED",
                "asset": "COMMERCIAL_BANK_MONEY",
                "amount": "10",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="add_metadata_key_values",
            event_name="confirm_metadata",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "transfer_completed_successfully")

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                debitor_account["id"]: [(DEFAULT_DIMENSIONS, "0")],
                creditor_account["id"]: [(DEFAULT_DIMENSIONS, "10")],
            }
        )


if __name__ == "__main__":
    endtoend.runtests()
