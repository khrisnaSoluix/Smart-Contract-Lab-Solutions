# standard libs
from datetime import datetime
from zoneinfo import ZoneInfo

# library
from library.us_products.contracts.template import us_checking_account
from library.us_products.test import dimensions, files, parameters
from library.us_products.test.e2e import accounts as accounts, parameters as e2e_parameters

# inception sdk
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.common.utils import ac_coverage
from inception_sdk.vault.postings.posting_classes import OutboundHardSettlement, PostingInstruction
from inception_sdk.vault.postings.postings_helper import create_pib_from_posting_instructions

endtoend.testhandle.CONTRACTS = {
    us_checking_account.PRODUCT_NAME: {
        "path": files.CHECKING_ACCOUNT_CONTRACT,
        "template_params": e2e_parameters.default_template,
    }
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    parameters.DORMANCY_FLAG: ("library/common/flag_definitions/account_dormant.resource.yaml")
}

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = accounts.internal_accounts_tside


class USCheckingAccountTest(endtoend.End2Endtest):
    def test_primary_denomination(self):
        opening_date = datetime.now(tz=ZoneInfo("UTC"))

        customer_id = endtoend.core_api_helper.create_customer()
        checking_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=us_checking_account.PRODUCT_NAME,
            instance_param_vals=e2e_parameters.default_instance,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        checking_account_id = checking_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", checking_account["status"])

        # Make an invalid transaction
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="1000", account_id=checking_account_id, denomination="SGP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Make a valid transaction
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="1000", account_id=checking_account_id, denomination="USD"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=checking_account_id, expected_balances=[(dimensions.DEFAULT, "1000")]
        )

    @ac_coverage(["CPP-1911-AC01"])
    def test_dormancy_scenarios_closure_rejected(self):
        opening_date = datetime.now(tz=ZoneInfo("UTC"))

        customer_id = endtoend.core_api_helper.create_customer()
        checking_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=us_checking_account.PRODUCT_NAME,
            instance_param_vals=e2e_parameters.default_instance,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        checking_account_id = checking_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", checking_account["status"])

        # Flag account as dormant
        dormancy_flag_id = endtoend.core_api_helper.create_flag(
            endtoend.testhandle.flag_definition_id_mapping[parameters.DORMANCY_FLAG],
            account_id=checking_account_id,
        )["id"]

        endtoend.core_api_helper.update_account(
            checking_account_id,
            endtoend.core_api_helper.AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE,
        )

        endtoend.accounts_helper.wait_for_account_update(
            account_id=checking_account_id,
            account_update_type="closure_update",
            target_status="ACCOUNT_UPDATE_STATUS_REJECTED",
        )

        # Reject transactions when dormancy flag is active
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="1000", account_id=checking_account_id, denomination="USD"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Remove the dormancy flag
        endtoend.core_api_helper.remove_flag(dormancy_flag_id)

        # Accept transactions after dormancy flag is removed
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="1000", account_id=checking_account_id, denomination="USD"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=checking_account_id, expected_balances=[(dimensions.DEFAULT, "1000")]
        )

        # Clear account balances and close account
        endtoend.contracts_helper.clear_account_balances(account=checking_account)
        endtoend.core_api_helper.create_account_update(
            checking_account_id, account_update={"closure_update": {}}
        )
        endtoend.accounts_helper.wait_for_account_update(
            account_id=checking_account_id,
            account_update_type="closure_update",
            target_status="ACCOUNT_UPDATE_STATUS_COMPLETED",
        )

    def test_max_daily_withdrawal_by_transaction_type(self):
        opening_date = datetime.now(tz=ZoneInfo("UTC"))

        customer_id = endtoend.core_api_helper.create_customer()
        checking_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=us_checking_account.PRODUCT_NAME,
            instance_param_vals=e2e_parameters.default_instance.copy(),
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        checking_account_id = checking_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", checking_account["status"])

        # Fund the account
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="1000",
            account_id=checking_account_id,
            denomination=parameters.TEST_DENOMINATION,
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Make an invalid transaction
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="1001",
            account_id=checking_account_id,
            denomination=parameters.TEST_DENOMINATION,
            instruction_details={"TRANSACTION_TYPE": "ATM"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])
        self.assertEqual(
            "Transactions would cause the maximum daily ATM withdrawal limit of 1000 USD to be "
            "exceeded.",
            pib["posting_instructions"][0]["contract_violations"][0]["reason"],
        )

        # Make a valid transaction
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            amount="500",
            account_id=checking_account_id,
            denomination=parameters.TEST_DENOMINATION,
            instruction_details={"TRANSACTION_TYPE": "ATM"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            account_id=checking_account_id, expected_balances=[(dimensions.DEFAULT, "500")]
        )

    @ac_coverage(["CPP-1917-AC02", "CPP-1917-AC03", "CPP-1917-AC04"])
    def test_standard_overdraft_transaction_type_coverage_without_opt_in(self):
        opening_date = datetime.now(tz=ZoneInfo("UTC"))
        instance_params = {
            **e2e_parameters.default_instance,
            us_checking_account.overdraft_coverage.PARAM_OVERDRAFT_OPT_IN: "False",
        }
        customer_id = endtoend.core_api_helper.create_customer()
        checking_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract=us_checking_account.PRODUCT_NAME,
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            opening_timestamp=opening_date.isoformat(),
        )
        checking_account_id = checking_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", checking_account["status"])

        credit_posting = endtoend.postings_helper.inbound_hard_settlement(
            account_id=checking_account_id, amount="100", denomination="USD"
        )
        pib_1 = endtoend.postings_helper.get_posting_batch(credit_posting)
        self.assertEqual(
            "POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED",
            pib_1["status"],
            "Fund the acount",
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=checking_account_id, expected_balances=[(dimensions.DEFAULT, "100")]
        )

        # Try a transaction that would require specific overdraft coverage
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=checking_account_id,
            amount="200",
            denomination="USD",
            instruction_details={"type": "excluded_transaction_type"},
        )
        pib_2 = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(
            "POSTING_INSTRUCTION_BATCH_STATUS_REJECTED",
            pib_2["status"],
        )

        # excluded transaction type results in rejection as it would utilise the overdraft limit
        # but total batch amount is less than available balance + available overdraft
        posting_instructions = [
            PostingInstruction(
                instruction=OutboundHardSettlement(
                    amount="150", denomination="USD", target_account_id=checking_account_id
                ),
                instruction_details={"transaction_code": "other"},
            ),
            PostingInstruction(
                instruction=OutboundHardSettlement(
                    amount="5", denomination="USD", target_account_id=checking_account_id
                ),
                instruction_details={"type": "excluded_transaction_type"},
            ),
            PostingInstruction(
                instruction=OutboundHardSettlement(
                    amount="50", denomination="USD", target_account_id=checking_account_id
                ),
                instruction_details={"type": "other"},
            ),
        ]
        postingID = endtoend.postings_helper.send_and_wait_for_posting_instruction_batch(
            create_pib_from_posting_instructions(posting_instructions=posting_instructions)[
                "posting_instruction_batch"
            ]
        )
        pib_3 = endtoend.postings_helper.get_posting_batch(postingID)

        self.assertEqual(
            "POSTING_INSTRUCTION_BATCH_STATUS_REJECTED",
            pib_3["status"],
        )

        # excluded transaction type first in the batch is accepted
        posting_instructions = [
            PostingInstruction(
                instruction=OutboundHardSettlement(
                    amount="5", denomination="USD", target_account_id=checking_account_id
                ),
                instruction_details={"type": "excluded_transaction_type"},
            ),
            PostingInstruction(
                instruction=OutboundHardSettlement(
                    amount="150", denomination="USD", target_account_id=checking_account_id
                ),
                instruction_details={"transaction_code": "other"},
            ),
            PostingInstruction(
                instruction=OutboundHardSettlement(
                    amount="50", denomination="USD", target_account_id=checking_account_id
                ),
                instruction_details={"type": "other"},
            ),
        ]
        postingID = endtoend.postings_helper.send_and_wait_for_posting_instruction_batch(
            create_pib_from_posting_instructions(posting_instructions=posting_instructions)[
                "posting_instruction_batch"
            ]
        )
        pib_4 = endtoend.postings_helper.get_posting_batch(postingID)

        self.assertEqual(
            "POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED",
            pib_4["status"],
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=checking_account_id, expected_balances=[(dimensions.DEFAULT, "-105")]
        )

        # update opt in parameter to allow excluded transaction types to utilise the overdraft limit
        parameter_update_id = endtoend.core_api_helper.update_account_instance_parameters(
            account_id=checking_account_id,
            instance_param_vals={
                us_checking_account.overdraft_coverage.PARAM_OVERDRAFT_OPT_IN: "True"
            },
        )["id"]
        endtoend.accounts_helper.wait_for_account_update(account_update_id=parameter_update_id)

        # Try a transaction that would require specific overdraft coverage
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=checking_account_id,
            amount="45",
            denomination="USD",
            instruction_details={"type": "excluded_transaction_type"},
        )
        pib_5 = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(
            "POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED",
            pib_5["status"],
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=checking_account_id, expected_balances=[(dimensions.DEFAULT, "-150")]
        )

        credit_posting = endtoend.postings_helper.inbound_hard_settlement(
            account_id=checking_account_id, amount="250", denomination="USD"
        )
        pib_6 = endtoend.postings_helper.get_posting_batch(credit_posting)
        self.assertEqual(
            "POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED",
            pib_6["status"],
            "Re-Fund the acount",
        )
        endtoend.balances_helper.wait_for_account_balances(
            account_id=checking_account_id, expected_balances=[(dimensions.DEFAULT, "100")]
        )

        # Excluded transaction greater than total available balance is rejected, regardless of the
        # opt-in
        postingID = endtoend.postings_helper.outbound_hard_settlement(
            account_id=checking_account_id,
            amount="300",
            denomination="USD",
            instruction_details={"type": "excluded_transaction_type"},
        )
        pib_7 = endtoend.postings_helper.get_posting_batch(postingID)
        self.assertEqual(
            "POSTING_INSTRUCTION_BATCH_STATUS_REJECTED",
            pib_7["status"],
        )


def test_out_of_network_atm_fees_rebated(self):
    opening_date = datetime.now(tz=ZoneInfo("UTC"))

    customer_id = endtoend.core_api_helper.create_customer()
    checking_account = endtoend.contracts_helper.create_account(
        customer=customer_id,
        contract=us_checking_account.PRODUCT_NAME,
        instance_param_vals=e2e_parameters.default_instance,
        status="ACCOUNT_STATUS_OPEN",
        opening_timestamp=opening_date.isoformat(),
    )
    checking_account_id = checking_account["id"]
    self.assertEqual("ACCOUNT_STATUS_OPEN", checking_account["status"])
    # Fund the account
    posting_id = endtoend.postings_helper.inbound_hard_settlement(
        amount="1000", account_id=checking_account_id, denomination="USD"
    )

    pib = endtoend.postings_helper.get_posting_batch(posting_id)
    self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

    endtoend.balances_helper.wait_for_account_balances(
        account_id=checking_account_id, expected_balances=[(dimensions.DEFAULT, "1000")]
    )

    # Withdraw funds from an out of network ATM
    posting_instructions = [
        PostingInstruction(
            instruction=OutboundHardSettlement(
                amount="100", denomination="USD", target_account_id=checking_account_id
            ),
            instruction_details={"transaction_code": "out_of_network_ATM"},
        ),
        PostingInstruction(
            instruction=OutboundHardSettlement(
                amount="5", denomination="USD", target_account_id=checking_account_id
            ),
            instruction_details={
                us_checking_account.unlimited_fee_rebate.FEE_TYPE_METADATA_KEY: "out_of_network_ATM"  # noqa: E501
            },
        ),
    ]
    postingID = endtoend.postings_helper.send_and_wait_for_posting_instruction_batch(
        create_pib_from_posting_instructions(posting_instructions=posting_instructions)[
            "posting_instruction_batch"
        ]
    )
    pib = endtoend.postings_helper.get_posting_batch(postingID)

    self.assertEqual(
        "POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED",
        pib["status"],
    )

    endtoend.balances_helper.wait_for_account_balances(
        account_id=checking_account_id, expected_balances=[(dimensions.DEFAULT, "900")]
    )
