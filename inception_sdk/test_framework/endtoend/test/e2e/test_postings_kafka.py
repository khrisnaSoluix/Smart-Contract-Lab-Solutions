# standard libs
import logging
import os

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

endtoend.testhandle.CONTRACTS = {
    "test_contract": {
        "path": "inception_sdk/test_framework/endtoend/test/e2e/input/template/"
        "contract_template.py",
        "template_params": {},
    },
}


class TestPostingsKafka(endtoend.End2Endtest):
    """Tests our posting error response behaviour. Contract tests don't typically trigger this
    intentionally, as it is usually a mistake on the test writer or contract writer side, so we
    do not have any consistent usage that we can rely on to flag any breaking changes.
    """

    def test_pib_response_error_handling(self):
        endtoend.standard_setup()
        cust_id = endtoend.core_api_helper.create_customer()
        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="test_contract",
            status="ACCOUNT_STATUS_OPEN",
        )

        # This will always trigger an error as it violates Postings API validation
        with self.assertRaises(Exception) as ctx:
            endtoend.postings_helper.inbound_auth(
                amount="-1", account_id=account["id"], denomination="GBP"
            )
        self.assertRegex(
            ctx.exception.args[0],
            r"Posting request_id='[\d\-\w]+' resulted in error={'type': "
            r"'POSTING_INSTRUCTION_BATCH_ERROR_TYPE_INVALID_ARGUMENT', "
            r"'message': 'validation error: inbound_authorisation: invalid amount field'}",
        )

        pib_id = endtoend.postings_helper.inbound_auth(amount="1", account_id=account["id"])
        pib = endtoend.postings_helper.get_posting_batch(pib_id=pib_id)
        self.assertEqual(pib["status"], "POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED")

        pib_id = endtoend.postings_helper.settlement(
            amount="1", client_transaction_id="non-existent-cti"
        )
        pib = endtoend.postings_helper.get_posting_batch(pib_id=pib_id)
        self.assertEqual(pib["status"], "POSTING_INSTRUCTION_BATCH_STATUS_REJECTED")
