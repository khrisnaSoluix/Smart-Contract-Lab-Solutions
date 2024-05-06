# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# library
from library.shariah_savings_account.contracts.template import shariah_savings_account
from library.shariah_savings_account.test import dimensions, files
from library.shariah_savings_account.test.e2e import accounts, parameters

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.core_api_helper import AccountStatus

SHARIAH_SAVINGS_ACCOUNT = parameters.SAVINGS_ACCOUNT

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = accounts.internal_accounts_tside

endtoend.testhandle.CONTRACTS = {
    SHARIAH_SAVINGS_ACCOUNT: {
        "path": files.CONTRACT_FILE,
        "template_params": parameters.default_template.copy(),
    },
    "shariah_savings_account_with_early_closure_fees": {
        "path": files.CONTRACT_FILE,
        "template_params": {
            **parameters.default_template,
            shariah_savings_account.early_closure_fee.PARAM_EARLY_CLOSURE_FEE: "100",
        },
    },
}

endtoend.testhandle.CALENDARS = {
    "PUBLIC_HOLIDAYS": ("library/common/calendars/public_holidays.resource.yaml")
}


class ShariahSavingsAccountTest(endtoend.End2Endtest):
    def test_account_rejects_large_deposit(self):
        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract=SHARIAH_SAVINGS_ACCOUNT,
            instance_param_vals=parameters.default_instance,
            status="ACCOUNT_STATUS_OPEN",
        )
        shariah_savings_account_id = account["id"]

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=shariah_savings_account_id, amount="20001", denomination="MYR"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=shariah_savings_account_id, amount="200", denomination="MYR"
        )

        pib = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # clear account for teardown
        force_override = {"force_override": "true"}
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=shariah_savings_account_id,
            amount="200",
            denomination="MYR",
            batch_details=force_override,
        )

    def test_account_apply_payment_type_flat_fee(self):
        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract=SHARIAH_SAVINGS_ACCOUNT,
            instance_param_vals=parameters.default_instance,
            status="ACCOUNT_STATUS_OPEN",
        )
        shariah_savings_account_id = account["id"]

        postingID_1 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=shariah_savings_account_id,
            amount="500",
            denomination="MYR",
        )

        pib_1 = endtoend.postings_helper.get_posting_batch(postingID_1)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_1["status"])

        postingID_2 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=shariah_savings_account_id,
            amount="100",
            denomination="MYR",
            instruction_details={"PAYMENT_TYPE": "ATM_MEPS"},
        )

        pib_2 = endtoend.postings_helper.get_posting_batch(postingID_2)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_2["status"])

        endtoend.balances_helper.wait_for_account_balances(
            shariah_savings_account_id,
            expected_balances=[(dimensions.DEFAULT, "399")],
        )

    def test_early_closure_fees_do_not_get_reapplied(self):
        """
        Testing this scenario in e2e because we cannot retry closure_update in simulator
        """
        cust_id = endtoend.core_api_helper.create_customer()

        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="shariah_savings_account_with_early_closure_fees",
            instance_param_vals=parameters.default_instance,
            status="ACCOUNT_STATUS_OPEN",
        )
        shariah_savings_account_id = account["id"]

        postingID_1 = endtoend.postings_helper.inbound_hard_settlement(
            account_id=shariah_savings_account_id,
            amount="500",
            denomination="MYR",
        )

        pib_1 = endtoend.postings_helper.get_posting_batch(postingID_1)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_1["status"])

        endtoend.core_api_helper.update_account(
            shariah_savings_account_id, status=AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE
        )
        endtoend.accounts_helper.wait_for_account_update(
            shariah_savings_account_id, account_update_type="closure_update"
        )

        # fee is set to 100 and was charged just once
        endtoend.balances_helper.wait_for_account_balances(
            shariah_savings_account_id,
            expected_balances=[(dimensions.DEFAULT, "400")],
        )

        closure_update_2 = endtoend.core_api_helper.create_account_update(
            shariah_savings_account_id, account_update={"closure_update": {}}
        )
        endtoend.accounts_helper.wait_for_account_update(
            shariah_savings_account_id, account_update_id=closure_update_2["id"]
        )

        # Can't use kafka helpers here as there's no change
        endtoend.balances_helper.compare_balances(
            shariah_savings_account_id,
            expected_balances=[(dimensions.DEFAULT, "400")],
        )

        # Because we've already run closure_update we must zero the balances due to our teardown
        postingID_2 = endtoend.postings_helper.outbound_hard_settlement(
            account_id=shariah_savings_account_id,
            amount="400",
            denomination="MYR",
            instruction_details={"force_override": "true"},
        )

        pib_2 = endtoend.postings_helper.get_posting_batch(postingID_2)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib_2["status"])
