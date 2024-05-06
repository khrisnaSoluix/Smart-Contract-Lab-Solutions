# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import time

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
    "INTERNAL_TRANSFER": "library/common/workflows/internal_transfer.yaml"
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

    def test_internal_transfer(self):
        """
        Test transfering funds between a customer's account using INTERNAL_TRANSFER WF
        """

        cust_id = endtoend.core_api_helper.create_customer()

        account_1 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )

        account_1_id = account_1["id"]

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=account_1_id, amount="400", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        account_2 = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )

        account_2_id = account_2["id"]

        # Check balances are as expected
        endtoend.balances_helper.wait_for_account_balances(
            account_1_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "400",
                )
            ],
        )

        # Start INTERNAL_TRANSFER WF
        wf_id = endtoend.workflows_helper.start_workflow(
            "INTERNAL_TRANSFER", context={"user_id": cust_id}
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_source_account",
            event_name="source_account_specified",
            context={"from_account_id": account_1_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_destination_account",
            event_name="destination_account_specified",
            context={"destination_account_id": account_2_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="specify_amount",
            event_name="external_transfer_info_specified",
            context={"transfer_amount": "200", "transfer_reference": "Test"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="validate_transfer_details",
            event_name="transfer_info_confirmed",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "transfer_successful")
        # Finished with INTERNAL_TRANSFER WF

        # Check balances are as expected
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                account_1_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "200",
                    )
                ],
                # Finish balance checks
                account_2_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "200",
                    )
                ],
            }
        )

    def test_rejected_internal_transfer(self):
        """
        Test transfering funds between a customer's account using INTERNAL_TRANSFER WF ends up in
        transfer_rejected state when trying to transfer between accounts that have a restriction
        """

        cust_id = endtoend.core_api_helper.create_customer()

        source_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )

        source_account_id = source_account["id"]

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=source_account_id, amount="400", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        destination_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )

        destination_account_id = destination_account["id"]

        # Put a restriction to ensure the posting is rejected
        # This is relying on a fixed request_id to avoid recreating the restriction set repeatedly
        # and be self-sufficient. We may want to add restriction set definitions to the framework
        endtoend.core_api_helper.create_restriction_set_definition_version(
            restriction_set_definition_id="test_rejected_internal_transfer_prevent_credits",
            restriction_levels=["RESTRICTION_LEVEL_ACCOUNT"],
            restriction_type="RESTRICTION_TYPE_PREVENT_CREDITS",
            description="test_rejected_internal_transfer_prevent_credits",
            request_id="test_rejected_internal_transfer_prevent_credits",
        )
        endtoend.core_api_helper.create_restriction_set(
            account_id=destination_account_id,
            restriction_set_definition_id="test_rejected_internal_transfer_prevent_credits",
        )

        # Check balances are as expected
        endtoend.balances_helper.wait_for_account_balances(
            source_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "400",
                )
            ],
        )

        # Start INTERNAL_TRANSFER WF
        wf_id = endtoend.workflows_helper.start_workflow(
            "INTERNAL_TRANSFER", context={"user_id": cust_id}
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_source_account",
            event_name="source_account_specified",
            context={"from_account_id": source_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_destination_account",
            event_name="destination_account_specified",
            context={"destination_account_id": destination_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="specify_amount",
            event_name="external_transfer_info_specified",
            context={"transfer_amount": "500", "transfer_reference": "Test"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="validate_transfer_details",
            event_name="transfer_info_confirmed",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "transfer_rejected")

        # Check balances are as expected
        self.assertEqual(
            endtoend.balances_helper.compare_balances(
                source_account_id,
                [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "400",
                    )
                ],
            ),
            {},
        )

        # Finish balance checks
        self.assertEqual(
            endtoend.balances_helper.compare_balances(
                destination_account_id,
                [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "0",
                    )
                ],
            ),
            {},
        )


if __name__ == "__main__":
    endtoend.runtests()
