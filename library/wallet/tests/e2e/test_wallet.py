# standard libs
import time

# common
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT
import inception_sdk.test_framework.endtoend as endtoend
import inception_sdk.test_framework.endtoend.core_api_helper as core_api_helper
from inception_sdk.test_framework.endtoend.helper import COMMON_ACCOUNT_SCHEDULE_TAG_PATH

from library.wallet.tests.e2e.wallet_test_params import (
    wallet_template_params,
    BASE_WALLET_FLAG_DEF_FOLDER,
    POSTING_BATCH_ACCEPTED,
    POSTING_BATCH_REJECTED,
    AUTO_TOP_UP_WALLET_FLAG,
)

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = {}

endtoend.testhandle.CONTRACTS = {
    "dummy_account": {
        "path": DUMMY_CONTRACT,
    },
    "wallet": {
        "path": "library/wallet/contracts/wallet.py",
        "template_params": wallet_template_params,
    },
}
endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"},
    "interest": {"path": "library/common/contract_modules/interest.py"},
}

endtoend.testhandle.WORKFLOWS = {
    "WALLET_APPLICATION": "library/wallet/workflows/wallet_application.yaml",
    "WALLET_AUTO_TOP_UP_SWITCH": "library/wallet/workflows/wallet_auto_top_up_switch.yaml",
    "WALLET_CLOSURE": "library/wallet/workflows/wallet_closure.yaml",
}

endtoend.testhandle.ACCOUNT_SCHEDULE_TAGS = {
    "WALLET_ZERO_OUT_DAILY_SPEND_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "AUTO_TOP_UP_WALLET": (BASE_WALLET_FLAG_DEF_FOLDER + "/auto_top_up_wallet.resource.yaml")
}


class WalletTest(endtoend.End2Endtest):
    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at
        # Uncomment this for timing info.
        # print('\n{} ({}s)'.format(self.id().rpartition('.')[2],
        # round(self._elapsed_time, 2)))

    def test_apply_wallet_failure_without_nominated_account(self):
        """
        Application of Wallet through workflow without
        nominated account should be rejected.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # Apply for Wallet account
        wf_id = endtoend.workflows_helper.start_workflow(
            "WALLET_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["wallet"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_nominated_account")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_nominated_account",
            event_name="no_nominated_account",
            context=None,
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "no_nominated_account")

        # check that the workflow reach closed instead of stuck
        wf_status = endtoend.workflows_helper.is_instance_stuck(wf_id)

        self.assertEqual(False, wf_status)

    def test_apply_wallet_via_workflow_with_dummy_account(self):
        """
        Create a customer with a dummy account,
        Apply Wallet through workflow for the
        customer and nominate the dummy account.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # Create a dummy account to be the nominated_account of wallet
        dummy_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )
        dummy_account_id = dummy_account["id"]

        self.assertEqual("ACCOUNT_STATUS_OPEN", dummy_account["status"])

        # Apply for Wallet account
        wf_id = endtoend.workflows_helper.start_workflow(
            "WALLET_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["wallet"],
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "select_nominated_account")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="select_nominated_account",
            event_name="nominated_account_specified",
            context={"nominated_account_id": dummy_account_id},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_additional_denominations",
            event_name="confirm_denominations",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "choose_instance_params")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="choose_instance_params",
            event_name="instance_parameters_set",
            context={"daily_spending_limit": "1000", "customer_wallet_limit": "1500"},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        wallet_account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]

        wallet_account = endtoend.contracts_helper.get_account(wallet_account_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", wallet_account["status"])

        self.assertEqual("1000", wallet_account["instance_param_vals"]["daily_spending_limit"])

        self.assertEqual("1500", wallet_account["instance_param_vals"]["customer_wallet_limit"])

        self.assertEqual("GBP", wallet_account["instance_param_vals"]["denomination"])

    def test_postings_into_wallet_with_allowed_and_disallowed_denomination(self):
        """
        Open a wallet and transfer to the account with
        different denomination. The post with denomination
        not belong to the wallet should be rejected.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # Create a dummy account to be the nominated_account of wallet
        dummy_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )
        dummy_account_id = dummy_account["id"]

        # Create a Wallet nominated above dummy account,
        # and add additional denomination SGD.
        instance_params = {
            "customer_wallet_limit": "1000",
            "daily_spending_limit": "500",
            "denomination": "GBP",
            "additional_denominations": '["SGD"]',
            "nominated_account": dummy_account_id,
        }

        wallet_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="wallet",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        wallet_account_id = wallet_account["id"]

        self.assertEqual("ACCOUNT_STATUS_OPEN", wallet_account["status"])

        # Reject inbound posting with denomination not allowed for this wallet
        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=wallet_account_id,
            amount="100",
            denomination="CNY",
        )
        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_REJECTED, pib["status"])

        # Accept inbound posting with main denomination
        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=wallet_account_id,
            amount="100",
            denomination="GBP",
        )
        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            wallet_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "100",
                )
            ],
        )

        # Accept inbound posting with additional denomination
        postingID2 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=wallet_account_id,
            amount="200",
            denomination="SGD",
        )
        pib2 = endtoend.postings_helper.get_posting_batch(postingID2)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib2["status"])

        endtoend.balances_helper.wait_for_account_balances(
            wallet_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="SGD"
                    ),
                    "200",
                )
            ],
        )

    def test_postings_into_wallet_within_and_above_limit(self):
        """
        Open a wallet and transfer to it within and
        above wallet_limit. The part above wallet_limit should
        be auto transfer to the nominated account.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # Create a dummy account to be the nominated_account of wallet
        dummy_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )
        dummy_account_id = dummy_account["id"]

        # Create a Wallet nominated above dummy account,
        # and add additional denomination SGD.
        instance_params = {
            "customer_wallet_limit": "1000",
            "daily_spending_limit": "500",
            "denomination": "GBP",
            "additional_denominations": '["SGD"]',
            "nominated_account": dummy_account_id,
        }

        wallet_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="wallet",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        wallet_account_id = wallet_account["id"]

        self.assertEqual("ACCOUNT_STATUS_OPEN", wallet_account["status"])

        # Accept inbound posting within limit
        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=wallet_account_id,
            amount="800",
            denomination="GBP",
        )
        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            wallet_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "800",
                )
            ],
        )

        # Accept the extra inbound posting and cap at limit
        postingID2 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=wallet_account_id,
            amount="800",
            denomination="GBP",
        )
        pib2 = endtoend.postings_helper.get_posting_batch(postingID2)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib2["status"])

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                wallet_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "1000",
                    )
                ],
                # after posting, the part above limit should go to the nominated dummy account
                dummy_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "600",
                    )
                ],
            }
        )

        # Fully over limit posting is transferred to dummy account
        postingID3 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=wallet_account_id,
            amount="800",
            denomination="GBP",
        )
        pib3 = endtoend.postings_helper.get_posting_batch(postingID3)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib3["status"])

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                wallet_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "1000",
                    )
                ],
                # after posting, the part above limit should go to the nominated dummy account
                dummy_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "1400",
                    )
                ],
            }
        )

    def test_postings_out_from_wallet_within_and_above_limit(self):
        """
        Open a wallet and transfer out within and above
        daily_limit, the transfer above daily_limit should
        be rejected.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # Create a dummy account to be the nominated_account of wallet
        dummy_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )
        dummy_account_id = dummy_account["id"]

        # Create a Wallet nominated above dummy account,
        # and add additional denomination SGD.
        instance_params = {
            "customer_wallet_limit": "1000",
            "daily_spending_limit": "500",
            "denomination": "GBP",
            "additional_denominations": '["SGD"]',
            "nominated_account": dummy_account_id,
        }

        wallet_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="wallet",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        wallet_account_id = wallet_account["id"]

        self.assertEqual("ACCOUNT_STATUS_OPEN", wallet_account["status"])

        # Accept inbound posting within limit
        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=wallet_account_id,
            amount="800",
            denomination="GBP",
        )
        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            wallet_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "800",
                )
            ],
        )

        # Accept outbound posting within limit and with enough balance
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=wallet_account_id,
            amount="500",
            denomination="GBP",
        )
        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            wallet_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "300",
                ),
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="todays_spending", denomination="GBP"
                    ),
                    "-500",
                ),
            ],
        )

        # Reject outbound posting above limit and with enough balance
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=wallet_account_id,
            amount="100",
            denomination="GBP",
        )
        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_REJECTED, pib["status"])

    def test_postings_out_from_wallet_with_and_without_auto_top_up(self):
        """
        Open a wallet and transfer out with and without
        AUTO_TOP_UP_WALLET flag. When wallet balance is
        not enough, it should be rejected when the flag
        is off, and accepted and trigger top up from the
        nominated account when the flag is on.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # Create a dummy account to be the nominated_account of wallet
        dummy_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )
        dummy_account_id = dummy_account["id"]

        # Create a Wallet nominated above dummy account.
        instance_params = {
            "customer_wallet_limit": "1000",
            "daily_spending_limit": "1000",
            "denomination": "GBP",
            "additional_denominations": '["SGD"]',
            "nominated_account": dummy_account_id,
        }

        wallet_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="wallet",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        wallet_account_id = wallet_account["id"]

        self.assertEqual("ACCOUNT_STATUS_OPEN", wallet_account["status"])

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=wallet_account_id,
            amount="50",
            denomination="GBP",
        )
        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            wallet_account_id,
            expected_balances=[
                (
                    endtoend.balances_helper.BalanceDimensions(
                        address="DEFAULT", denomination="GBP"
                    ),
                    "50",
                )
            ],
        )

        # Outbound posting without enough balance in wallet, and auto top up disabled
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=wallet_account_id,
            amount="500",
            denomination="GBP",
        )
        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_REJECTED, pib["status"])

        # Known issue (INC-2750): Without enough balance in nominated account,
        # wallet still able to top up.
        # Wallet with auto top up enabled
        core_api_helper.create_flag(
            endtoend.testhandle.flag_definition_id_mapping[AUTO_TOP_UP_WALLET_FLAG],
            account_id=wallet_account_id,
        )

        # Post balance into dummy account
        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=dummy_account_id,
            amount="200",
            denomination="GBP",
        )
        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        # Outbound posting without enough balance in wallet
        # And with enough balance in nominated account
        # 150 = 50 (in wallet) + 100 (from top up)
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=wallet_account_id,
            amount="150",
            denomination="GBP",
        )
        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(POSTING_BATCH_ACCEPTED, pib["status"])

        # Original 50 GBP in wallet are used.
        endtoend.balances_helper.wait_for_all_account_balances(
            {
                wallet_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "0",
                    )
                ],
                # After auto top up 100 to wallet, nominated dummy account
                # have 200-100=100 GBP left.
                dummy_account_id: [
                    (
                        endtoend.balances_helper.BalanceDimensions(
                            address="DEFAULT", denomination="GBP"
                        ),
                        "100",
                    )
                ],
            }
        )

    def test_workflow_auto_top_up_switch(self):
        """
        Create a customer with a dummy account and a linked Wallet account,
        Apply the Auto Top-Up flag to the Wallet account using the workflow,
        Check that the flag is enabled, then disable it by re-running the workflow.
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # Create a dummy account to be the nominated_account of wallet
        dummy_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )
        dummy_account_id = dummy_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", dummy_account["status"])

        # Create a Wallet nominated above dummy account,
        # and add additional denomination SGD.
        instance_params = {
            "customer_wallet_limit": "1000",
            "daily_spending_limit": "500",
            "denomination": "GBP",
            "additional_denominations": '["SGD"]',
            "nominated_account": dummy_account_id,
        }

        wallet_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="wallet",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        wallet_account_id = wallet_account["id"]

        self.assertEqual("ACCOUNT_STATUS_OPEN", wallet_account["status"])

        # Run Auto Top-Up workflow
        wf_id = endtoend.workflows_helper.start_workflow(
            "WALLET_AUTO_TOP_UP_SWITCH", context={"account_id": wallet_account_id}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "auto_top_up_changed")

        # Ensure the flag has been added to the account
        account_flags = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping[AUTO_TOP_UP_WALLET_FLAG],
            account_ids=[wallet_account_id],
        )

        self.assertEqual(
            account_flags[0]["flag_definition_id"],
            endtoend.testhandle.flag_definition_id_mapping[AUTO_TOP_UP_WALLET_FLAG],
        )
        self.assertEqual(account_flags[0]["is_active"], True)
        self.assertEqual(account_flags[0]["account_id"], wallet_account_id)

        # Run Auto Top-Up workflow again, to disable the flag
        wf_id = endtoend.workflows_helper.start_workflow(
            "WALLET_AUTO_TOP_UP_SWITCH", context={"account_id": wallet_account_id}
        )
        endtoend.workflows_helper.wait_for_state(wf_id, "auto_top_up_changed")

        # Ensure the flag has been removed from the account
        account_flags = endtoend.core_api_helper.get_flag(
            flag_name=endtoend.testhandle.flag_definition_id_mapping[AUTO_TOP_UP_WALLET_FLAG],
            account_ids=[wallet_account_id],
        )

        self.assertEqual(account_flags, [])

    def test_close_wallet(self):
        """
        Create a customer with a linked wallet account.
        1. attempt to close the account when there is a balance in DEFAULT ADDRESS (fail to close)
        2. close the account when the balance in DEFAULT ADDRESS is 0 (succeed to close)
        3. attempt to close an account which has already been closed (fail as already closed)
        """
        cust_id = endtoend.core_api_helper.create_customer()

        # Create a dummy account to be the nominated_account of wallet
        dummy_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="dummy_account",
            status="ACCOUNT_STATUS_OPEN",
        )
        dummy_account_id = dummy_account["id"]

        # Create a Wallet nominated above dummy account.
        instance_params = {
            "customer_wallet_limit": "1000",
            "daily_spending_limit": "500",
            "denomination": "GBP",
            "additional_denominations": '["SGD"]',
            "nominated_account": dummy_account_id,
        }

        wallet_account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="wallet",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        wallet_account_id = wallet_account["id"]

        # Outbound and inbound postings that do not balance each other out
        endtoend.postings_helper.inbound_hard_settlement(
            account_id=wallet_account_id,
            amount="200",
            denomination="GBP",
        )

        endtoend.postings_helper.outbound_hard_settlement(
            account_id=wallet_account_id,
            amount="150",
            denomination="GBP",
        )
        # (1) account should fail to close as balances amount on DEFAULT ADDRESS != 0
        wf_id = endtoend.workflows_helper.start_workflow(
            "WALLET_CLOSURE",
            context={
                "account_id": wallet_account_id,
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="authorise_account_closure",
            event_name="autotrigger_ticket_close",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closure_failure")

        account = endtoend.contracts_helper.get_account(wallet_account_id)

        self.assertEqual("ACCOUNT_STATUS_OPEN", account["status"])

        # an outbound posting to balance the account so DEFAULT ADDRESS amount == 0
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=wallet_account_id,
            amount="50",
            denomination="GBP",
        )

        # (2) Start workflow to close the account
        wf_id = endtoend.workflows_helper.start_workflow(
            "WALLET_CLOSURE",
            context={
                "account_id": wallet_account_id,
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="authorise_account_closure",
            event_name="autotrigger_ticket_close",
            context={},
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_closed_successfully")

        # account details are required again to refresh the status
        account = endtoend.contracts_helper.get_account(wallet_account_id)

        # check that the account status has been updated and therefore closed
        self.assertEqual("ACCOUNT_STATUS_CLOSED", account["status"])

        #  (3) attempt to close the wallet account that is already closed - should fail
        wf_id = endtoend.workflows_helper.start_workflow(
            "WALLET_CLOSURE",
            context={
                "account_id": wallet_account_id,
            },
        )

        endtoend.workflows_helper.wait_for_state(wf_id, "account_already_closed")
        account = endtoend.contracts_helper.get_account(wallet_account_id)
        self.assertEqual("ACCOUNT_STATUS_CLOSED", account["status"])
