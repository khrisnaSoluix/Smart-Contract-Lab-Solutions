# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import time
from uuid import uuid4

# common
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
import inception_sdk.test_framework.endtoend as endtoend

from library.common.tests.e2e.common_test_params import (
    internal_accounts_tside,
)

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "dummy_account": {"path": DUMMY_CONTRACT},
}

endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"},
    "interest": {"path": "library/common/contract_modules/interest.py"},
}

endtoend.testhandle.WORKFLOWS = {
    "ADJUSTMENT_CREATION": "library/common/workflows/adjustment_creation.yaml"
}

endtoend.testhandle.ACCOUNT_SCHEDULE_TAGS = {}

endtoend.testhandle.FLAG_DEFINITIONS = {}


class InceptionRegressionTest(endtoend.End2Endtest):
    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at
        # Uncomment this for timing info.
        # print('\n{} ({}s)'.format(self.id().rpartition('.')[2], round(self._elapsed_time, 2)))

    def test_workflow_adjustment_creation_credit_on_dummy_account(self):
        """
        Test ADJUSTMENT_CREATION can do credit adjustments
        """

        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )

        account_id = account["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "ADJUSTMENT_CREATION",
            context={
                "account_id": account_id,
                "bank_internal_account_id": "e2e_L_DUMMY_CONTRA",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_adjustment_direction",
            event_name="create_credit_request",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_posting_instruction_details",
            event_name="posting_details_entered",
            context={"payment_amount": "150.08", "note": "Test adjustment"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_adjustment_details",
            event_name="transfer_details_confirmed",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "success")

        # Check balances are as expected
        endtoend.balances_helper.wait_for_account_balances(
            account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "150.08",
                )
            ],
        )

    def test_workflow_adjustment_creation_debit_on_dummy_account(self):
        """
        Test ADJUSTMENT_CREATION can do debit adjustments
        """

        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )

        account_id = account["id"]

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=account_id, amount="400", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        wf_id = endtoend.workflows_helper.start_workflow(
            "ADJUSTMENT_CREATION",
            context={
                "account_id": account_id,
                "bank_internal_account_id": "e2e_L_DUMMY_CONTRA",
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_adjustment_direction",
            event_name="create_debit_request",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_posting_instruction_details",
            event_name="posting_details_entered",
            context={"payment_amount": "199.25", "note": "Test adjustment"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_adjustment_details",
            event_name="transfer_details_confirmed",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "success")

        # Check balances are as expected
        endtoend.balances_helper.wait_for_account_balances(
            account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "200.75",
                )
            ],
        )

    def test_workflow_adjustment_creation_rejected_posting(self):
        """
        Test ADJUSTMENT_CREATION ends in adjustment_rejected state when the adjustment posting
        is rejected
        """

        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )

        account_id = account["id"]

        wf_id = endtoend.workflows_helper.start_workflow(
            "ADJUSTMENT_CREATION",
            context={
                "account_id": account_id,
                # this internal account won't exist so the adjustment posting will be rejected
                "bank_internal_account_id": uuid4().hex,
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_adjustment_direction",
            event_name="create_debit_request",
            context={},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_posting_instruction_details",
            event_name="posting_details_entered",
            context={"payment_amount": "500", "note": "Test adjustment"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_adjustment_details",
            event_name="transfer_details_confirmed",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "adjustment_rejected")

        adjustment_rejected_context = endtoend.workflows_helper.get_state_local_context(
            wf_id, "adjustment_rejected"
        )

        self.assertDictContainsSubset(
            subset={
                "transfer_status": "POSTING_INSTRUCTION_BATCH_STATUS_REJECTED",
                "violation_type": "Account",
                "violation_type_subtype": "ACCOUNT_VIOLATION_ACCOUNT_NOT_PRESENT",
            },
            dictionary=adjustment_rejected_context,
        )


if __name__ == "__main__":
    endtoend.runtests()
