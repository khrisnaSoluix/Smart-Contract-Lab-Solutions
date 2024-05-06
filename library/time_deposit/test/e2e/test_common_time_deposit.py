# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# library
from library.time_deposit.test import dimensions, files, parameters
from library.time_deposit.test.e2e import accounts as e2e_accounts, parameters as e2e_parameters

# inception sdk
from inception_sdk.test_framework import endtoend
from inception_sdk.vault.postings.posting_classes import OutboundHardSettlement, PostingInstruction
from inception_sdk.vault.postings.postings_helper import create_pib_from_posting_instructions

endtoend.testhandle.CONTRACTS = {
    "time_deposit": {
        "path": files.TIME_DEPOSIT_CONTRACT,
        "template_params": e2e_parameters.default_template,
    },
}
endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = e2e_accounts.internal_accounts_tside

endtoend.testhandle.CALENDARS = {
    "PUBLIC_HOLIDAYS": ("library/common/calendars/public_holidays.resource.yaml")
}


class TimeDepositTest(endtoend.End2Endtest):
    def test_pre_posting_rejections(self):
        customer_id = endtoend.core_api_helper.create_customer()
        instance_params = {
            **e2e_parameters.default_instance,
        }

        time_deposit_account = endtoend.contracts_helper.create_account(
            customer=customer_id,
            contract="time_deposit",
            instance_param_vals=instance_params,
            status="ACCOUNT_STATUS_OPEN",
            wait_for_activation=True,
        )
        time_deposit_id = time_deposit_account["id"]
        self.assertEqual("ACCOUNT_STATUS_OPEN", time_deposit_account["status"])

        # initial deposit
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            amount="1000", account_id=time_deposit_id, denomination=parameters.TEST_DENOMINATION
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            account_id=time_deposit_id, expected_balances=[(dimensions.DEFAULT, "1000")]
        )

        # multiple postings in batch
        posting_instructions = [
            PostingInstruction(
                instruction=OutboundHardSettlement(
                    amount="10", denomination="GBP", target_account_id=time_deposit_id
                ),
            ),
            PostingInstruction(
                instruction=OutboundHardSettlement(
                    amount="5", denomination="GBP", target_account_id=time_deposit_id
                ),
            ),
        ]
        posting_id = endtoend.postings_helper.send_and_wait_for_posting_instruction_batch(
            create_pib_from_posting_instructions(posting_instructions=posting_instructions)[
                "posting_instruction_batch"
            ]
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # unsupported denomination
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=time_deposit_id, amount="50", denomination="USD"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # authorisation
        posting_id = endtoend.postings_helper.outbound_auth(
            account_id=time_deposit_id, amount="50", denomination="GBP"
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])
