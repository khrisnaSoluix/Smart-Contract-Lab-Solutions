# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from time import time

# common
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions
from inception_sdk.test_framework.endtoend.core_api_helper import AccountStatus
from library.murabahah.tests.e2e.murabahah_test_params import (
    DEFAULT_TAGS,
    internal_accounts_tside,
    murabahah_instance_params,
    murabahah_template_params,
    murabahah_template_params_with_early_closure_fees,
)

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    "murabahah": {
        "path": "library/murabahah/contracts/template/murabahah.py",
        "template_params": murabahah_template_params,
    },
    "murabahah_with_early_closure_fees": {
        "path": "library/murabahah/contracts/template/murabahah.py",
        "template_params": murabahah_template_params_with_early_closure_fees,
    },
}

endtoend.testhandle.ACCOUNT_SCHEDULE_TAGS = DEFAULT_TAGS

endtoend.testhandle.CALENDARS = {
    "PUBLIC_HOLIDAYS": ("library/common/calendars/public_holidays.resource.yaml")
}


class MurabahahTest(endtoend.End2Endtest):
    def setUp(self):
        self._started_at = time()

    def tearDown(self):
        self._elapsed_time = time() - self._started_at

    def test_account_rejects_large_deposit(self):
        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="murabahah",
            instance_param_vals=murabahah_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        murabahah_account_id = account["id"]

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=murabahah_account_id, amount="5000", denomination="MYR"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=murabahah_account_id, amount="200", denomination="MYR"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # clear account for teardown
        force_override = {"force_override": "true"}
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=murabahah_account_id,
            amount="200",
            denomination="MYR",
            batch_details=force_override,
        )

    def test_account_apply_payment_type_flat_fee(self):
        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="murabahah",
            instance_param_vals=murabahah_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        murabahah_account_id = account["id"]

        postingID_1 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=murabahah_account_id,
            amount="500",
            denomination="MYR",
        )

        pib_1 = endtoend.postings_helper.get_posting_batch(postingID_1)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_1["status"])

        postingID_2 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=murabahah_account_id,
            amount="100",
            denomination="MYR",
            instruction_details={"PAYMENT_TYPE": "ATM_MEPS"},
        )

        pib_2 = endtoend.postings_helper.get_posting_batch(postingID_2)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_2["status"])

        endtoend.balances_helper.wait_for_account_balances(
            murabahah_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="MYR"), "399")],
        )

    def test_early_closure_fees_do_not_get_reapplied(self):
        """
        Testing this scenario in e2e because we cannot retry closure_update in simulator
        """
        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="murabahah_with_early_closure_fees",
            instance_param_vals=murabahah_instance_params,
            status="ACCOUNT_STATUS_OPEN",
        )
        murabahah_account_id = account["id"]

        postingID_1 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=murabahah_account_id,
            amount="500",
            denomination="MYR",
        )

        pib_1 = endtoend.postings_helper.get_posting_batch(postingID_1)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_1["status"])

        endtoend.core_api_helper.update_account(
            murabahah_account_id, status=AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE
        )
        endtoend.accounts_helper.wait_for_account_update(
            murabahah_account_id, account_update_type="closure_update"
        )

        # fee is set to 100 and was charged just once
        endtoend.balances_helper.wait_for_account_balances(
            murabahah_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="MYR"), "400")],
        )

        closure_update_2 = endtoend.core_api_helper.create_account_update(
            murabahah_account_id, account_update={"closure_update": {}}
        )
        endtoend.accounts_helper.wait_for_account_update(
            murabahah_account_id, account_update_id=closure_update_2["id"]
        )

        # Can't use kafka helpers here as there's no change
        endtoend.balances_helper.compare_balances(
            murabahah_account_id,
            expected_balances=[(BalanceDimensions(address="DEFAULT", denomination="MYR"), "400")],
        )

        # Because we've already run closure_update we must zero the balances due to our teardown
        postingID_2 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=murabahah_account_id,
            amount="400",
            denomination="MYR",
            batch_details={"force_override": "true"},
        )

        pib_2 = endtoend.postings_helper.get_posting_batch(postingID_2)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_2["status"])
