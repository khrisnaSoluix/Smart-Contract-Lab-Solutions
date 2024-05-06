# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# library
from library.savings_account.contracts.template import savings_account as savings_account_template
from library.savings_account.test import dimensions, files, parameters
from library.savings_account.test.e2e import accounts as e2e_accounts, parameters as e2e_parameters

# inception sdk
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.contracts.files import DUMMY_CONTRACT

SAVINGS_ACCOUNT = e2e_parameters.SAVINGS_ACCOUNT
endtoend.testhandle.CONTRACTS = {
    SAVINGS_ACCOUNT: {
        "path": files.SAVINGS_ACCOUNT_CONTRACT,
        "template_params": e2e_parameters.default_template.copy(),
    },
    "dummy_account": {"path": DUMMY_CONTRACT},
}
endtoend.testhandle.FLAG_DEFINITIONS = {
    parameters.DORMANCY_FLAG: ("library/common/flag_definitions/account_dormant.resource.yaml")
}
endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = e2e_accounts.internal_accounts_tside


class SavingsAccountTest(endtoend.End2Endtest):
    def test_dormancy_scenarios(self):
        endtoend.standard_setup()
        opening_date = e2e_parameters.default_start_date

        customer_id = endtoend.core_api_helper.create_customer()
        savings_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=SAVINGS_ACCOUNT,
            instance_param_vals=parameters.default_instance.copy(),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        savings_account_id = savings_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", savings_account["status"])

        # Make transaction before dormancy
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="1000", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id, expected_balances=[(dimensions.DEFAULT, "1000")]
        )

        # Flag account as dormant
        dormancy_flag_id = endtoend.core_api_helper.create_flag(
            endtoend.testhandle.flag_definition_id_mapping[parameters.DORMANCY_FLAG],
            account_id=savings_account_id,
        )["id"]

        # Expect further transactions to be rejected, credit and debit
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="1000", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="1000", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Remove the dormancy flag
        endtoend.core_api_helper.remove_flag(dormancy_flag_id)

        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="1000", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id, expected_balances=[(dimensions.DEFAULT, "0")]
        )

    def test_dormancy_scenarios_closure_rejected(self):
        endtoend.standard_setup()
        opening_date = e2e_parameters.default_start_date

        customer_id = endtoend.core_api_helper.create_customer()
        savings_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=SAVINGS_ACCOUNT,
            instance_param_vals=parameters.default_instance.copy(),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        savings_account_id = savings_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", savings_account["status"])

        # Flag account as dormant
        dormancy_flag_id = endtoend.core_api_helper.create_flag(
            endtoend.testhandle.flag_definition_id_mapping[parameters.DORMANCY_FLAG],
            account_id=savings_account_id,
        )["id"]

        endtoend.core_api_helper.update_account(
            savings_account_id,
            endtoend.core_api_helper.AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE,
        )

        endtoend.accounts_helper.wait_for_account_update(
            account_id=savings_account_id,
            account_update_type="closure_update",
            target_status="ACCOUNT_UPDATE_STATUS_REJECTED",
        )

        # Remove the dormancy flag
        endtoend.core_api_helper.remove_flag(dormancy_flag_id)

        endtoend.core_api_helper.create_account_update(
            savings_account_id, account_update={"closure_update": {}}
        )
        endtoend.accounts_helper.wait_for_account_update(
            account_id=savings_account_id,
            account_update_type="closure_update",
            target_status="ACCOUNT_UPDATE_STATUS_COMPLETED",
        )

    def test_transaction_limits_scenarios(self):
        endtoend.standard_setup()
        opening_date = e2e_parameters.default_start_date

        customer_id = endtoend.core_api_helper.create_customer()
        savings_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=SAVINGS_ACCOUNT,
            instance_param_vals=parameters.default_instance.copy(),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        savings_account_id = savings_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", savings_account["status"])

        # Make transaction to fund the account
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="1000", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id, expected_balances=[(dimensions.DEFAULT, "1000")]
        )

        # Deposit transaction above minimum amount is accepted
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="30000", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id, expected_balances=[(dimensions.DEFAULT, "31000")]
        )

        # Withdrawal transaction above minimum amount gets accepted
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="100", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id, expected_balances=[(dimensions.DEFAULT, "30900")]
        )

        # Withdrawal transaction within daily withdrawal limit
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="10900", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id, expected_balances=[(dimensions.DEFAULT, "20000")]
        )

        # Deposit transaction below minimum amount gets rejected
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="0.50", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Deposit transaction causing the balance to go over the allowed limit gets rejected
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="45000", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Withdrawal transaction below minimum amount gets rejected
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="1.75", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Withdrawal transaction goes over the maximum daily withdrawal limit
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="10000", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Withdrawal transaction within daily withdrawal limit
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="9000", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id, expected_balances=[(dimensions.DEFAULT, "11000")]
        )

        # Deposit transaction goes over the maximum daily deposit limit
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="10000", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Deposit transaction within daily deposit limit
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="9000", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id, expected_balances=[(dimensions.DEFAULT, "20000")]
        )

        # Withdrawal ATM transaction above maximum amount gets rejected
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="2000",
            account_id=savings_account_id,
            denomination=parameters.TEST_DENOMINATION,
            instruction_details={"TRANSACTION_TYPE": "ATM"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

    def test_excess_withdrawal_fee(self):
        endtoend.standard_setup()
        opening_date = e2e_parameters.default_start_date

        customer_id = endtoend.core_api_helper.create_customer()
        savings_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=SAVINGS_ACCOUNT,
            instance_param_vals=parameters.default_instance.copy(),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        savings_account_id = savings_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", savings_account["status"])

        # Make transaction to fund the account
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="1000", account_id=savings_account_id, denomination=parameters.TEST_DENOMINATION
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id, expected_balances=[(dimensions.DEFAULT, "1000")]
        )

        # Limit set for transaction type "ATM"
        for _ in range(
            int(
                e2e_parameters.default_template[
                    savings_account_template.excess_fee.PARAM_PERMITTED_WITHDRAWALS
                ]
            )
        ):
            posting_id = endtoend.postings_helper.outbound_hard_settlement(
                amount="25",
                account_id=savings_account_id,
                denomination=parameters.TEST_DENOMINATION,
                instruction_details={"TRANSACTION_TYPE": "ATM"},
            )
            pib = endtoend.postings_helper.get_posting_batch(posting_id)
            self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # No excess withdrawal fees when the limit is reached
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id, expected_balances=[(dimensions.DEFAULT, "850")]
        )

        # One ATM Withdrawal transactions over the limit generates a fee
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="25",
            account_id=savings_account_id,
            denomination=parameters.TEST_DENOMINATION,
            instruction_details={"TRANSACTION_TYPE": "ATM"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # One excess withdrawal fees is charged
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id, expected_balances=[(dimensions.DEFAULT, "822.50")]
        )

        # Clear out current balance so the account can be closed
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="822.5",
            account_id=savings_account_id,
            denomination=parameters.TEST_DENOMINATION,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Final balance of the account should be zero
        endtoend.balances_helper.wait_for_account_balances(
            account_id=savings_account_id, expected_balances=[(dimensions.DEFAULT, "0")]
        )
